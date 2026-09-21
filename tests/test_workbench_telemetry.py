import ctypes
import threading
import time
import unittest
from unittest.mock import patch
from workbench.telemetry import GpuMonitor, NvmlProvider, Memory, Utilization, TelemetryUnavailable, monitored_execute
from workbench.backends import DemoBackend
from workbench.domain import read_json
from pathlib import Path

class Provider:
    def __init__(self,uuid): self.i=0;self.closed=False
    def sample(self):
        self.i+=1
        return {'total_bytes':8*2**30,'used_bytes':self.i*1024,'free_bytes':8*2**30-self.i*1024}
    def close(self):self.closed=True

class TelemetryTests(unittest.TestCase):
    def test_simulation_never_fabricates_gpu_counters(self):
        m=GpuMonitor('demo',simulated=True,provider_factory=lambda x:self.fail('No driver in demo'))
        m.start();m.begin_case();r=m.end_case();m.close()
        self.assertEqual(r['status'],'unavailable');self.assertIsNone(r['sampled_peak_used_gib']);self.assertEqual(r['sample_count'],0)
    def test_sampled_peak_scope_and_boundaries(self):
        p=Provider('GPU-test');m=GpuMonitor('GPU-test',provider_factory=lambda x:p,interval=10)
        m.start();m.begin_case();m._sample();r=m.end_case();m.close()
        self.assertEqual(r['sample_count'],3);self.assertEqual(r['sampled_peak_used_bytes'],4096)
        self.assertIn('total_device',r['scope']);self.assertTrue(p.closed)
    def test_sampler_failure_keeps_collected_evidence(self):
        p=Provider('GPU-test');m=GpuMonitor('GPU-test',provider_factory=lambda x:p,interval=10)
        m.start();m.begin_case()
        p.sample=lambda:(_ for _ in ()).throw(RuntimeError('driver disappeared'))
        r=m.end_case();m.close()
        self.assertEqual(r['status'],'partial');self.assertEqual(r['sample_count'],1)
        self.assertIn('disappeared',r['error'])
    def test_factory_failure_nonfatal(self):
        m=GpuMonitor('GPU-test',provider_factory=lambda x:(_ for _ in ()).throw(OSError('no driver')))
        m.start();m.begin_case();r=m.end_case();m.close()
        self.assertEqual(r['status'],'unavailable')
    def test_snapshot_does_not_poll_driver(self):
        p=Provider('GPU-test');m=GpuMonitor('GPU-test',provider_factory=lambda x:p,interval=10)
        m.start();count=p.i
        for _ in range(10):m.snapshot()
        self.assertEqual(p.i,count);m.close()
    def test_sampler_uses_in_memory_provider_no_file_writes(self):
        p=Provider('GPU-test');m=GpuMonitor('GPU-test',provider_factory=lambda x:p,interval=.005)
        with patch('builtins.open',side_effect=AssertionError('No disk logging')):
            m.start();m.begin_case();time.sleep(.025);r=m.end_case();m.close()
        self.assertGreater(r['sample_count'],2)
    def test_case_state_is_reset(self):
        m=GpuMonitor('GPU-test',provider_factory=Provider,interval=10);m.start()
        m.begin_case();r1=m.end_case();m.begin_case();r2=m.end_case();m.close()
        self.assertEqual(r1['sample_count'],r2['sample_count'])
    def test_no_subprocess_in_telemetry_source(self):
        s=(Path(__file__).resolve().parents[1]/'workbench/telemetry.py').read_text()
        self.assertNotIn('subprocess.',s)
    def test_sample_record_bound_keeps_peak_and_count(self):
        m=GpuMonitor('GPU-test',provider_factory=Provider,interval=10);m.start();m.begin_case()
        for _ in range(4200):m._sample()
        r=m.end_case();m.close()
        self.assertEqual(len(r['samples']),4096);self.assertGreater(r['samples_dropped'],0)
        self.assertEqual(r['sampled_peak_used_bytes'],r['samples'][-1]['used_bytes'])
    def test_partial_workflow_records_telemetry_on_cancel(self):
        from workbench.workflows import Cancelled
        m=GpuMonitor('demo',simulated=True);m.start();cancel=threading.Event();cancel.set()
        test=read_json(Path(__file__).resolve().parents[1]/'test_specs/time_only.json')
        with self.assertRaises(Cancelled) as cm:monitored_execute(test,test['variants'][0],DemoBackend(),cancel,monitor=m)
        self.assertIn('gpu_memory',cm.exception.partial);m.close()
    def test_nvml_uuid_guard(self):
        with self.assertRaises(TelemetryUnavailable):NvmlProvider('0')
    def test_nvml_structure_layout(self):
        self.assertEqual(ctypes.sizeof(Memory),24);self.assertEqual(ctypes.sizeof(Utilization),8)

if __name__=='__main__':unittest.main()
