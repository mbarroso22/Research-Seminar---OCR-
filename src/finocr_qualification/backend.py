"""Owned loopback b6500 server adapter. Instantiated only behind the public pause."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import threading
import time
import urllib.request

from finocr_answer.backend import require_settings
from finocr_answer.contract import wire
from finocr_answer.feasibility import stop_process
from .resources import ResourceMonitor
from .evidence import write_json, sync_directory


def runtime_log(log: str) -> dict:
    result = require_settings(log)
    offloads = re.findall(r'offloaded\s+(\d+/\d+)\s+layers',log)
    if not offloads or offloads[-1] != '37/37' or re.search(
        r'out of (?:device |host )?memory|VK_ERROR_DEVICE_LOST|device lost|CPU fallback|falling back to CPU',log,re.I):
        raise ValueError('Runtime/offload/resource failure in backend log')
    return result


class WindowsBackend:
    def __init__(self, setup: dict, output: Path, campaign: Path):
        self.setup,self.output,self.campaign = setup,output,campaign
        self.process,self.monitor,self.stdout,self.stderr = None,None,None,None
        self.ready = False
        self.writer = None

    def start(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        self.base=f'http://127.0.0.1:{port}'
        command=[self.setup['server']['path'],'--model',self.setup['model']['path'],
            '--host','127.0.0.1','--port',str(port),'--ctx-size','6144','--parallel','1',
            '--batch-size','512','--ubatch-size','128','--threads','6','--n-gpu-layers','99',
            '--device','Vulkan0','--cache-type-k','f16','--cache-type-v','f16','--seed','0',
            '--temp','0','--flash-attn','off','--jinja','--no-context-shift','--no-webui','--no-warmup']
        environment={k:v for k,v in os.environ.items() if not k.startswith(('LLAMA_ARG_','GGML_','CUDA_'))}
        cache=self.campaign/'cache';cache.mkdir()
        environment.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
            HF_HOME=str(cache/'huggingface'),XDG_CACHE_HOME=str(cache),
            GGML_VK_DISABLE_COOPMAT='1',GGML_VK_DISABLE_COOPMAT2='1')
        write_json(self.output/'launch.json',{'command':command,'environment':{k:v for k,v in environment.items()
            if k.startswith(('HF_','TRANSFORMERS_','XDG_','GGML_'))}})
        start=time.monotonic()
        try:
            self.stdout=(self.output/'server.stdout.log').open('xb')
            self.stderr=(self.output/'server.stderr.log').open('xb')
            self.process=subprocess.Popen(command,stdout=self.stdout,stderr=self.stderr,
                env=environment,cwd=self.setup['asset_root'])
            self.monitor=ResourceMonitor(self.process,self.output/'resource-samples')
            self.monitor.start()
            while True:
                self.guard()
                if time.monotonic()-start>180:
                    raise TimeoutError('180-second startup deadline')
                try:
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(self.base+'/health',timeout=1) as response:
                        if json.load(response).get('status')=='ok':break
                except (OSError,ValueError):
                    pass
                time.sleep(.25)
            self.ready=True
            self.guard()
            write_json(self.output/'runtime_observed.json',{'observed':runtime_log(self.logs()),
                'startup_wall_seconds':time.monotonic()-start})
        except BaseException:
            self.close()
            raise

    def logs(self):
        return (self.output/'server.stderr.log').read_text(encoding='utf-8',errors='replace')

    def guard(self):
        if self.process is not None and self.process.poll() is not None:
            raise ValueError('Owned backend exited')
        if self.monitor is not None:self.monitor.guard()
        if self.ready:runtime_log(self.logs())

    def metadata(self, route, payload):
        if route not in {'/apply-template','/tokenize'}:
            raise ValueError('Only nongenerating metadata routes allowed')
        self.guard()
        request=urllib.request.Request(self.base+route,wire(payload),{'Content-Type':'application/json'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=30) as response:
            value=json.load(response)
        self.guard()
        return value

    def bracket(self):
        self.guard()
        return self.monitor.bracket()

    def complete(self, payload: dict, directory: Path):
        # Engine durably charges immediately before invoking this method.
        result={};start=time.monotonic()
        def receive():
            try:
                request=urllib.request.Request(self.base+'/completion',wire(payload),{'Content-Type':'application/json'})
                with (directory/'raw-response.sse').open('xb') as raw:
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=180) as response:
                        for line in response:
                            raw.write(line);raw.flush();os.fsync(raw.fileno())
                    raw.flush();os.fsync(raw.fileno())
                result['status']='received'
            except BaseException as exc:
                result.update(status='transport_failure',error=f'{type(exc).__name__}: {exc}')
            finally:
                try:sync_directory(directory)
                except OSError as exc:result.update(status='transport_failure',error=str(exc))
        worker=threading.Thread(target=receive,daemon=True)
        self.writer = worker
        worker.start()
        try:
            while worker.is_alive():
                self.guard()
                if time.monotonic()-start>180:
                    raise TimeoutError('180-second total completion wall deadline')
                worker.join(.05)
            self.guard()
            if result.get('status')!='received':raise ValueError(str(result))
            return result
        except BaseException as exc:
            result.update(status='terminal_failure',error=f'{type(exc).__name__}: {exc}')
            if self.process is not None:stop_process(self.process)
            worker.join(10)
            if worker.is_alive():result['writer_not_quiescent']=True
            raise
        finally:
            result['wall_seconds']=time.monotonic()-start
            write_json(directory/'transport.json',result)

    def close(self):
        if self.monitor is not None:self.monitor.stop()
        if self.process is not None:stop_process(self.process)
        if self.writer is not None:
            self.writer.join(10)
            if self.writer.is_alive():raise ValueError('Raw SSE writer is not quiescent; export remains pending')
        for handle in [self.stdout,self.stderr]:
            if handle is not None and not handle.closed:
                handle.flush();os.fsync(handle.fileno());handle.close()

    def summary(self):
        return self.monitor.summary() if self.monitor is not None else {'sample_count':0,'measurement_errors':['monitor not started']}
