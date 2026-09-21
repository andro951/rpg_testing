"""Read-only NVML sampling. Never spawn commands or write files during a workflow.

The peak is a SAMPLED total-device peak (display/other processes included), not
per-process allocation accounting or a proof that every model tensor is on GPU.
"""
from __future__ import annotations
import ctypes
import ctypes.util
import os
import threading
import time
from collections import deque
from pathlib import Path

POLICY = 'nvml-device-memory-250ms-v1'
INTERVAL_SECONDS = 0.25


class TelemetryUnavailable(RuntimeError):
    pass


class Memory(ctypes.Structure):
    _fields_ = [('total', ctypes.c_ulonglong), ('free', ctypes.c_ulonglong), ('used', ctypes.c_ulonglong)]


class Utilization(ctypes.Structure):
    _fields_ = [('gpu', ctypes.c_uint), ('memory', ctypes.c_uint)]


class NvmlProvider:
    """Small read-only binding to the installed NVIDIA driver, no pip dependency."""
    def __init__(self, gpu_uuid: str):
        if not isinstance(gpu_uuid, str) or not gpu_uuid.startswith(('GPU-', 'MIG-')):
            raise TelemetryUnavailable('A real GPU UUID is required for NVML sampling.')
        if os.name == 'nt':
            system = Path(os.environ.get('SystemRoot', 'C:/Windows'))/'System32'
            program = Path(os.environ.get('ProgramW6432', os.environ.get('ProgramFiles', 'C:/Program Files')))
            candidates = [str(system/'nvml.dll'), str(program/'NVIDIA Corporation/NVSMI/nvml.dll')]
        else:
            candidates = [ctypes.util.find_library('nvidia-ml'), 'libnvidia-ml.so.1']
        self.lib = None; self.initialized = False
        for candidate in candidates:
            if not candidate: continue
            try:
                self.lib = ctypes.CDLL(candidate)
                break
            except OSError: continue
        if self.lib is None:
            raise TelemetryUnavailable('NVIDIA NVML library is not available on this host.')
        try:
            self._init = self._function('nvmlInit_v2', [])
            self._shutdown = self._function('nvmlShutdown', [])
            self._handle = self._function('nvmlDeviceGetHandleByUUID', [ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)])
            self._memory = self._function('nvmlDeviceGetMemoryInfo', [ctypes.c_void_p, ctypes.POINTER(Memory)])
            self._check(self._init()); self.initialized = True
            self.device = ctypes.c_void_p()
            self._check(self._handle(gpu_uuid.encode('ascii'), ctypes.byref(self.device)))
            self._util = self._optional('nvmlDeviceGetUtilizationRates', [ctypes.c_void_p, ctypes.POINTER(Utilization)])
            self._temperature = self._optional('nvmlDeviceGetTemperature', [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)])
            self._power = self._optional('nvmlDeviceGetPowerUsage', [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)])
        except Exception:
            self.close()
            raise

    def _function(self, name, args):
        function = getattr(self.lib, name)
        function.argtypes = args; function.restype = ctypes.c_int
        return function

    def _optional(self, name, args):
        try: return self._function(name, args)
        except AttributeError: return None

    @staticmethod
    def _check(status):
        if status != 0: raise TelemetryUnavailable(f'NVML query failed with status {status}.')

    def sample(self):
        memory = Memory()
        self._check(self._memory(self.device, ctypes.byref(memory)))
        if memory.total <= 0 or memory.used > memory.total or memory.free > memory.total:
            raise TelemetryUnavailable('NVML did not provide valid discrete-device memory counters.')
        result = {'total_bytes': memory.total, 'used_bytes': memory.used, 'free_bytes': memory.free,
                  'gpu_utilization_percent': None, 'temperature_c': None, 'power_w': None}
        util = Utilization(); temperature = ctypes.c_uint(); power = ctypes.c_uint()
        if self._util and self._util(self.device, ctypes.byref(util)) == 0:
            result['gpu_utilization_percent'] = util.gpu
        if self._temperature and self._temperature(self.device, 0, ctypes.byref(temperature)) == 0:
            result['temperature_c'] = temperature.value
        if self._power and self._power(self.device, ctypes.byref(power)) == 0:
            result['power_w'] = power.value/1000
        return result

    def close(self):
        if self.initialized:
            self._shutdown(); self.initialized = False


class GpuMonitor:
    """One sampler per loaded model; cached UI reads do not call the driver."""
    def __init__(self, gpu_uuid, simulated=False, provider_factory=NvmlProvider,
                 interval=INTERVAL_SECONDS, clock=time.perf_counter):
        self.uuid = gpu_uuid; self.simulated = simulated; self.factory = provider_factory
        self.interval = interval; self.clock = clock
        self.lock = threading.RLock(); self.query_lock = threading.Lock()
        self.stop_event = threading.Event(); self.thread = None; self.provider = None
        self.latest = None; self.error = None; self.active = False
        self.samples = deque(maxlen=4096); self.count = 0; self.peak = None; self.start_time = None

    def start(self):
        if self.simulated:
            self.error = 'Simulation has no hardware measurements.'
            return
        try:
            self.provider = self.factory(self.uuid)
            self._sample()
        except Exception as exc:
            self.error = str(exc)
            self.close()
            return
        if self.error:
            self.close(); return
        def loop():
            while not self.stop_event.wait(self.interval):
                self._sample()
                if self.error: break
        self.thread = threading.Thread(target=loop, name='gpu-memory-sampler', daemon=True)
        self.thread.start()

    def _sample(self):
        if not self.provider: return
        try:
            with self.query_lock:
                reading = self.provider.sample()
                stamp = self.clock()
            with self.lock:
                self.latest = {**reading, 'monotonic_seconds': stamp}
                if self.active:
                    self.count += 1
                    self.peak = max(self.peak or 0, reading['used_bytes'])
                    self.samples.append({**reading, 'elapsed_seconds': stamp-self.start_time})
        except Exception as exc:
            with self.lock: self.error = str(exc)

    def begin_case(self):
        with self.lock:
            self.samples.clear(); self.count = 0; self.peak = None
            self.start_time = self.clock(); self.active = True
        self._sample()  # Before the workflow timer; records a boundary sample.

    def end_case(self):
        self._sample()  # After the workflow timer; records a boundary sample.
        with self.lock:
            self.active = False
            return {'policy': POLICY, 'status': 'partial' if self.error and self.count else 'available' if self.count else 'unavailable',
                    'source': 'NVML', 'scope': 'total_device_including_other_processes',
                    'sample_interval_seconds': self.interval, 'sample_count': self.count,
                    'samples_dropped': max(0, self.count-len(self.samples)),
                    'sampled_peak_used_bytes': self.peak,
                    'sampled_peak_used_gib': self.peak/2**30 if self.peak is not None else None,
                    'samples': list(self.samples), 'error': self.error,
                    'note': 'Sampled peak with pre/post boundary samples. Brief peaks can be missed; not model-only VRAM or proof of full GPU residency.'}

    def snapshot(self):
        with self.lock:
            return {'latest': dict(self.latest) if self.latest else None, 'error': self.error,
                    'interval_seconds': self.interval, 'scope': 'total_device_including_other_processes'}

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                self.error = 'GPU telemetry thread did not finish; NVML was not shut down while busy.'
                return
            self.thread = None
        if self.provider:
            try: self.provider.close()
            except Exception as exc: self.error = str(exc)
            self.provider = None


def monitored_execute(test, variant, backend, cancel=None, on_stage=None, monitor=None, repetition=0):
    from .workflows import execute
    if monitor: monitor.begin_case()
    try:
        result = execute(test, variant, backend, cancel, on_stage, repetition)
    except Exception as exc:
        if monitor:
            exc.partial = {**getattr(exc, 'partial', {}), 'gpu_memory': monitor.end_case()}
        raise
    else:
        if monitor: result['gpu_memory'] = monitor.end_case()
        return result
