"""Measured runtime gates. Sampling is a lower bound, never an isolated GPU peak."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import threading
import time

from .evidence import write_json

GIB = 1024 ** 3


def device_reading(text: str) -> dict:
    rows = [line.split(',') for line in text.strip().splitlines()]
    if len(rows) != 1 or len(rows[0]) != 5:
        raise ValueError('Expected exactly one GPU and five nvidia-smi fields')
    index, name, driver, total, used = [v.strip() for v in rows[0]]
    result = {'index': int(index), 'name': name, 'driver': driver,
              'total_mib': int(total), 'used_mib': int(used)}
    if result['index'] != 0 or name != 'NVIDIA GeForce RTX 3070 Ti' or driver != '537.70' or int(total) != 8192:
        raise ValueError('GPU/driver identity differs from the fixed condition')
    if not 0 <= int(used) <= 7168:
        raise ValueError('Device-wide VRAM exceeds the 7168 MiB limit')
    return result


def read_device() -> dict:
    raw = subprocess.check_output(['nvidia-smi',
        '--query-gpu=index,name,driver_version,memory.total,memory.used',
        '--format=csv,noheader,nounits'], text=True, timeout=5)
    return device_reading(raw)


def check_sample(value: dict) -> None:
    if value['system_available_bytes'] < 2 * GIB:
        raise ValueError('Less than 2 GiB system-available RAM')
    if value['server_rss_bytes'] < 0 or value['client_rss_bytes'] <= 0:
        raise ValueError('Invalid process memory readings')
    if value['server_rss_bytes'] + value['client_rss_bytes'] > 8 * GIB:
        raise ValueError('Server plus client RSS exceeds 8 GiB')
    if value['system_total_bytes'] <= 0 or value['system_available_bytes'] > value['system_total_bytes']:
        raise ValueError('Invalid system memory readings')


def preflight_resources(directory: Path) -> dict:
    import psutil
    import shutil
    memory = psutil.virtual_memory()
    free = shutil.disk_usage(directory).free
    if free < 5 * GIB or memory.available < 2 * GIB:
        raise ValueError('Require 5 GiB disk and 2 GiB system-available RAM')
    return {'disk_free_bytes': free, 'system_available_bytes': memory.available,
            'system_total_bytes': memory.total, 'device': read_device()}


class ResourceMonitor:
    def __init__(self, process, output: Path):
        import psutil
        self.server = psutil.Process(process.pid)
        self.owned_process = process
        self.client = psutil.Process(os.getpid())
        self.output = output
        self.samples, self.errors = [], []
        self.lock = threading.Lock()
        self.done = threading.Event()
        self.worker = threading.Thread(target=self._loop, daemon=True)
        self.last_gpu, self.last_sample = 0.0, None

    def sample(self, *, gpu=False):
        import psutil
        with self.lock:
            now = time.monotonic()
            # Explicitly bounded allowed gaps distinguish jitter from lost coverage.
            if self.last_sample is not None and now - self.last_sample > 6:
                raise ValueError('Unexplained RAM sampling gap over six seconds')
            if self.last_gpu and now - self.last_gpu > 6:
                raise ValueError('Unexplained GPU sampling gap over six seconds')
            mem, client, system = self.server.memory_info(), self.client.memory_info(), psutil.virtual_memory()
            value = {'time_ns': time.time_ns(), 'monotonic': now,
                     'server_rss_bytes': mem.rss, 'client_rss_bytes': client.rss,
                     'server_os_peak_working_set_bytes': getattr(mem, 'peak_wset', None),
                     'system_total_bytes': system.total, 'system_available_bytes': system.available}
            check_sample(value)
            if gpu or now - self.last_gpu >= 1:
                value['device'] = read_device()
                self.last_gpu = time.monotonic()
            write_json(self.output / f'{len(self.samples):06d}.json', value)
            self.samples.append(value)
            self.last_sample = time.monotonic()
            return value

    def _loop(self):
        while not self.done.wait(.25):
            try:
                self.sample()
            except Exception as exc:
                self.errors.append(f'{type(exc).__name__}: {exc}')
                self.done.set()
                from finocr_answer.feasibility import stop_process
                stop_process(self.owned_process)

    def start(self):
        self.output.mkdir()
        self.sample(gpu=True)
        self.worker.start()

    def guard(self):
        if self.errors or not self.samples:
            raise ValueError('Resource monitor failed: ' + repr(self.errors))
        if self.last_sample is not None and time.monotonic() - self.last_sample > 6:
            raise ValueError('Resource monitor is stale')

    def bracket(self):
        self.guard()
        return self.sample(gpu=True)

    def stop(self):
        self.done.set()
        if self.worker.ident is not None:
            self.worker.join(7)
        if self.worker.is_alive():
            self.errors.append('Resource monitor did not terminate')

    def summary(self):
        return {'sample_count': len(self.samples), 'measurement_errors': list(self.errors),
            'server_sampled_peak_rss_bytes': max((s['server_rss_bytes'] for s in self.samples), default=None),
            'client_sampled_peak_rss_bytes': max((s['client_rss_bytes'] for s in self.samples), default=None),
            'sampled_peak_sum_rss_bytes': max((s['server_rss_bytes'] + s['client_rss_bytes'] for s in self.samples), default=None),
            'server_os_peak_working_set_bytes': max((s.get('server_os_peak_working_set_bytes') or 0 for s in self.samples), default=None),
            'minimum_system_available_bytes': min((s['system_available_bytes'] for s in self.samples), default=None),
            'device_wide_sampled_peak_used_mib': max((s['device']['used_mib'] for s in self.samples if 'device' in s), default=None),
            'scope': '0.25s RAM / 1s whole-device GPU, plus request brackets; sampled peaks are lower bounds; RSS sum may double-count shared pages'}
