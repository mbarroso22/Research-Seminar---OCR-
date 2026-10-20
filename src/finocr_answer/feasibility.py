"""Retained exhausted-v2 lifecycle and audit helpers; public run() is paused.

Current contract repairs are checked only by the separate offline conformance API.
Legacy lifecycle tests mock every process/transport and the unconditional guard.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path
from .historical_contract_v2 import canonical, digest, SCHEMA, MAX_INPUT, MAX_OUTPUT, CONTEXT, DEADLINE, validate_schema, VERSION, strict_json
from .contract import wire
from .pause import require_inference_authorized
from .setup import identity, tree, runtime, source_identity, verify_assets
from .synthetic import historical_cases_v2 as cases, pack_historical_v2 as pack
from finocr.io import write_json


def stop_process(process) -> None:
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=10)


def post(url: str, value: dict, timeout: float = 30) -> dict:
    request = urllib.request.Request(url, wire(value), {'Content-Type': 'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout) as response:
        return json.load(response)


def stream_completion(url: str, payload: dict, destination: Path, process, deadline: float = DEADLINE) -> dict:
    """Parent enforces total wall deadline, preserving every received SSE byte.

    No repair or retry. Terminate the owned server on timeout so work cannot
    continue unnoticed or overlap the next case.
    """
    outcome = {}
    def receive():
        try:
            request = urllib.request.Request(url, wire(payload), {'Content-Type': 'application/json'})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with destination.open('xb') as out, opener.open(request, timeout=deadline) as response:
                for line in response:
                    out.write(line); out.flush()
            outcome['status'] = 'received'
        except Exception as exc:
            outcome.update(status='transport_failure', error=f'{type(exc).__name__}: {exc}')
    thread = threading.Thread(target=receive, daemon=True)
    start = time.perf_counter(); thread.start(); thread.join(deadline)
    if thread.is_alive():
        stop_process(process)
        thread.join(10)
        outcome.update(status='deadline', error='Total request wall deadline exceeded; owned server stopped')
    outcome['wall_seconds'] = time.perf_counter()-start
    return outcome


def parse_stream(raw: bytes) -> tuple[str, dict]:
    content = []
    final = None
    for line in raw.decode('utf-8', errors='strict').splitlines():
        if not line.startswith('data: '): continue
        data = line[6:]
        if data == '[DONE]': continue
        item = strict_json(data)
        if 'error' in item: raise ValueError(str(item['error']))
        content.append(item.get('content', ''))
        if item.get('stop'): final = item
    if final is None: raise ValueError('No terminal backend response')
    return ''.join(content), final


class Monitor:
    """Sampled process RSS and device-wide VRAM, not an exact isolated GPU peak."""
    def __init__(self, pid, output):
        import psutil
        self.process = psutil.Process(pid)
        self.client = psutil.Process(os.getpid())
        self.output, self.done = output, threading.Event()
        self.peak_rss, self.os_peak, self.peak_gpu, self.samples, self.errors = 0, 0, None, 0, []
        self.peak_client, self.peak_sum, self.min_available, self.peak_system_used = 0, 0, None, 0
        self.thread = threading.Thread(target=self.run, daemon=True)
    def run(self):
        next_gpu = 0
        with self.output.open('x', encoding='utf-8') as out:
            while not self.done.is_set():
                try:
                    memory = self.process.memory_info()
                    self.peak_rss = max(self.peak_rss, memory.rss)
                    self.os_peak = max(self.os_peak, getattr(memory, 'peak_wset', 0))
                    client_memory = self.client.memory_info()
                    system = __import__('psutil').virtual_memory()
                    self.peak_client = max(self.peak_client, client_memory.rss)
                    self.peak_sum = max(self.peak_sum, memory.rss+client_memory.rss)
                    self.min_available = min(self.min_available if self.min_available is not None else system.available, system.available)
                    self.peak_system_used = max(self.peak_system_used, system.total-system.available)
                    sample = {'time_ns': time.time_ns(), 'server_rss_bytes': memory.rss,
                              'client_rss_bytes':client_memory.rss,'system_available_bytes':system.available,
                              'system_total_bytes':system.total}
                    if time.monotonic() >= next_gpu:
                        try:
                            raw = subprocess.check_output(['nvidia-smi', '--query-gpu=index,name,driver_version,memory.total,memory.used', '--format=csv,noheader,nounits'], text=True, timeout=5)
                            sample['gpu_device_wide'] = raw.strip()
                            rows = [r.strip().split(',') for r in raw.strip().splitlines()]
                            first = rows[0]
                            if len(rows) != 1 or '3070 Ti' not in first[1]: raise ValueError('Expected one RTX 3070 Ti')
                            value = int(first[-1].strip())
                            self.peak_gpu = max(self.peak_gpu or 0, value)
                        except Exception as exc: self.errors.append(str(exc))
                        next_gpu = time.monotonic()+1
                    out.write(json.dumps(sample)+'\n'); out.flush(); self.samples += 1
                except Exception as exc:
                    self.errors.append(str(exc)); break
                self.done.wait(.25)
    def start(self): self.thread.start()
    def stop(self): self.done.set(); self.thread.join(7)
    def summary(self):
        return {'server_sampled_peak_rss_bytes': self.peak_rss, 'server_windows_peak_working_set_bytes': self.os_peak or None,
                'client_sampled_peak_rss_bytes':self.peak_client,'sampled_peak_sum_rss_bytes':self.peak_sum,
                'minimum_system_available_bytes':self.min_available,'sampled_peak_system_used_bytes':self.peak_system_used,
                'device_wide_sampled_peak_used_mib': self.peak_gpu, 'sample_count': self.samples,
                'measurement_errors': sorted(set(self.errors)), 'vram_scope': 'whole GPU incl display/other processes; 1 second sampling, lower bound on peak',
                'rss_scope': 'server and client reported separately and summed; shared pages may be counted twice; conversion excluded',
                'system_scope':'whole system including other processes; total minus available, sampled, not an isolated process peak'}


from .historical_validation_v2 import functional_checks


def run(setup_path: Path, output: Path, repository: Path) -> dict:
    require_inference_authorized()  # unconditional offline pause, before I/O/model/server
    if output.exists(): raise ValueError('New empty output directory required; interrupted campaign preserved, no answer retries')
    setup = strict_json(setup_path.read_text())
    if setup.get('version')!=VERSION:
        raise ValueError('Preserve the v1 run/ledger. Audit it offline and prepare the separate bounded v2 follow-up; do not reseal/reset v1.')
    from .followup import validate_followup_setup, require_lineage
    from .backend import require_settings
    validate_followup_setup(setup,setup_path,output)
    root = Path(setup['asset_root'])
    verify_assets(setup['lock'], root)
    if identity(Path(setup['model']['path'])) != setup['model'] or identity(Path(setup['server']['path'])) != setup['server']:
        raise ValueError('Sealed model/backend changed')
    if source_identity(repository) != setup['source_sha256'] or runtime() != setup['runtime']:
        raise ValueError('Code/runtime changed since seal')
    if __import__('platform').system() != 'Windows': raise ValueError('Pinned Windows Vulkan check must run on Windows')
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(root/'official', local_files_only=True, trust_remote_code=False)
    campaign_path=Path(setup['campaign_root'])/'synthetic_campaign.json'
    campaign={'setup_sha256':identity(setup_path)['sha256'],'output':str(output.resolve()),'attempted':0,'requests':[]}
    # Exclusive creation prevents two runs or a new output name from silently
    # spending another six requests. Retain this ledger even after interruption.
    with campaign_path.open('x',encoding='utf-8') as handle:
        json.dump(campaign,handle,indent=2)
    output.mkdir(parents=True)
    manifest = {'kind':'synthetic_feasibility_only', 'status':'preflight', 'setup':identity(setup_path),
                'primary_requests':0, 'annotated_page_requests':0, 'request_budget':6, 'attempted':0, 'records':[], 'benchmark_generation_enabled':False,
                'execution':setup['execution'],'budget':setup['budget'],'original_lineage':setup['lineage']}
    write_json(output/'run_manifest.json', manifest)
    # Clear backend overrides inherited from interactive shells. Never modify global PATH/driver.
    environment = {k:v for k,v in os.environ.items() if not k.startswith(('LLAMA_ARG_', 'GGML_', 'CUDA_'))}
    environment.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HOME=str(Path(setup['cache_root'])/'huggingface'),
                       XDG_CACHE_HOME=setup['cache_root'], GGML_VK_DISABLE_COOPMAT='1', GGML_VK_DISABLE_COOPMAT2='1')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    command = [setup['server']['path'], '--model', setup['model']['path'], '--host','127.0.0.1','--port',str(port),
               '--ctx-size',str(CONTEXT),'--parallel','1','--batch-size','512','--ubatch-size','128', '--threads','6',
               '--n-gpu-layers','99','--device','Vulkan0','--cache-type-k','f16','--cache-type-v','f16',
               '--seed','0','--temp','0','--flash-attn','off','--jinja','--no-context-shift','--no-webui','--no-warmup']
    manifest.update(command=command, backend_environment={k:v for k,v in environment.items() if k.startswith(('HF_', 'TRANSFORMERS_', 'XDG_', 'GGML_'))})
    write_json(output/'run_manifest.json', manifest)
    process = None; monitor = None; start=time.perf_counter()
    base=f'http://127.0.0.1:{port}'
    try:
        with (output/'server.stdout.log').open('xb') as stdout, (output/'server.stderr.log').open('xb') as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=environment, cwd=root)
            monitor=Monitor(process.pid, output/'memory_samples.jsonl'); monitor.start()
            while True:
                if process.poll() is not None: raise ValueError('Backend exited during startup; inspect server logs')
                if time.perf_counter()-start > 180: raise ValueError('Startup deadline exceeded')
                try:
                    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(base+'/health', timeout=1) as response:
                        if json.load(response).get('status') == 'ok': break
                except (OSError, ValueError): pass
                time.sleep(.25)
            manifest['startup_wall_seconds']=time.perf_counter()-start
            logs=(output/'server.stderr.log').read_text(encoding='utf-8',errors='replace')
            manifest['runtime_observed']=require_settings(logs)
            planned=[]
            # Validate every prompt/template/token cap before any generation.
            for case in cases():
                case_id=case['task_id'].split(':')[1]
                turns,packed=pack(case,tokenizer)
                applied=post(base+'/apply-template',{'messages':turns})['prompt']
                if applied!=packed['prompt']:raise ValueError('Official tokenizer/backend chat templates disagree')
                tokens=post(base+'/tokenize',{'content':applied,'add_special':False,'parse_special':True})['tokens']
                if tokens!=packed['token_ids']:raise ValueError('Official tokenizer/backend token IDs disagree')
                if len(tokens)>MAX_INPUT or len(tokens)+MAX_OUTPUT>CONTEXT:raise ValueError('Token budget violation')
                control=setup['control_prompts'][case_id]
                if hashlib.sha256(applied.encode()).hexdigest()!=control['prompt_sha256'] or digest(tokens)!=control['token_ids_sha256']:
                    raise ValueError('Synthetic prompts/tokens changed versus original; no inference submitted')
                planned.append((case_id,applied,tokens,packed))
            manifest['all_six_prompt_controls_verified']=True
            write_json(output/'run_manifest.json',manifest)
            for case_id,applied,tokens,packed in planned:
                payload={'prompt':tokens,'n_predict':MAX_OUTPUT,'temperature':0,'seed':0,'top_k':1,'top_p':1.0,'min_p':0.0,
                         'repeat_penalty':1.0,'presence_penalty':0.0,'frequency_penalty':0.0,'cache_prompt':False,
                         'json_schema':SCHEMA,'stream':True,'id_slot':0}
                case_dir=output/case_id; case_dir.mkdir()
                (case_dir/'prompt.txt').write_bytes(applied.encode('utf-8'))
                write_json(case_dir/'packing.json',packed)
                (case_dir/'request.json').write_bytes(wire(payload))
                request_hash=digest({'model':setup['model']['sha256'],'instruction':setup['instruction_sha256'],
                                     'schema':setup['schema_sha256'],'backend':setup['server']['sha256'],
                                     'setup_sha256':identity(setup_path)['sha256'],'request':payload})
                record={'case_id':case_id,'request_sha256':request_hash,'status':'attempt_started','input_tokens':len(tokens)}
                manifest['records'].append(record); manifest['attempted']+=1
                write_json(output/'run_manifest.json',manifest) # charge before submission, never silently retry
                campaign['attempted']+=1; campaign['requests'].append(request_hash)
                write_json(campaign_path,campaign)
                transport=stream_completion(base+'/completion',payload,case_dir/'raw-response.sse',process)
                record.update(transport)
                if (case_dir/'raw-response.sse').exists():
                    record['response_sha256']=identity(case_dir/'raw-response.sse')['sha256']
                try:
                    raw=(case_dir/'raw-response.sse').read_bytes()
                    content, final=parse_stream(raw)
                    (case_dir/'raw-content.txt').write_bytes(content.encode('utf-8'))
                    write_json(case_dir/'backend-final.json',final)
                    record.update(response_sha256=hashlib.sha256(raw).hexdigest(), generated_tokens=final.get('tokens_predicted'),
                                  backend_timings=final.get('timings'), output_limit=final.get('stop_type')=='limit')
                    if transport['status'] != 'received': raise ValueError(transport['status'])
                    if record['output_limit'] or final.get('truncated') or not 0 < final.get('tokens_predicted',0) <= MAX_OUTPUT:
                        raise ValueError('Output truncated/limited or token count invalid')
                    value=strict_json(content)
                    packed_pages={p['page_id']:tokenizer.decode(p['retained_token_ids'], clean_up_tokenization_spaces=False) for p in packed['retained']}
                    record['checks']=functional_checks(value,case_id,packed_pages)
                    write_json(case_dir/'parsed.json',value)
                    record['status']='mechanically_valid_requires_manual_review' if record['checks']['mechanical_pass'] else 'validation_failed'
                except Exception as exc:
                    record.update(status='failed', error=f'{type(exc).__name__}: {exc}')
                write_json(output/'run_manifest.json',manifest)
                if transport['status'] != 'received': raise ValueError('Transport/deadline failure; campaign stopped, no retry')
                print(f"Synthetic {case_id}: {record['status']}",flush=True)
        manifest['status']='completed_requires_manual_review'
    except Exception as exc:
        manifest.update(status='stopped', error=f'{type(exc).__name__}: {exc}')
    finally:
        if monitor: monitor.stop(); manifest['memory']=monitor.summary()
        if process: stop_process(process)
        manifest['wall_seconds']=time.perf_counter()-start
        memory=manifest.get('memory',{})
        manifest['resource_checks_pass']=bool(memory.get('sample_count')) and memory.get('device_wide_sampled_peak_used_mib') is not None and not memory.get('measurement_errors',[])
        manifest['automated_checks_pass']=len(manifest['records'])==6 and all(
            r.get('checks',{}).get('mechanical_pass') is True for r in manifest['records']) and manifest['resource_checks_pass']
        try:
            require_lineage(setup); manifest['original_artifacts_unchanged']=True
        except Exception as exc:
            manifest['original_artifacts_unchanged']=False; manifest['preservation_error']=str(exc); manifest['automated_checks_pass']=False
        if manifest['status']!='stopped' and not manifest['automated_checks_pass']:manifest['status']='completed_validation_failed'
        manifest['feasibility_conclusion']='pending manual semantic/formula review' if manifest['automated_checks_pass'] else 'feasibility not established; preserve failures and stop'
        write_json(output/'run_manifest.json',manifest)
    return manifest
