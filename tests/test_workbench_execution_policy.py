import unittest
from workbench.execution_policy import *

class ExecutionPolicyTests(unittest.TestCase):
    def test_full(self):
        r=placement(['load_tensors: offloaded 33/33 layers to GPU'])
        self.assertEqual(r['status'],'full_gpu');self.assertEqual(r['cpu_layers'],0)
    def test_partial(self):
        r=placement(['offloaded 30/33 layers to GPU'])
        self.assertEqual(r['status'],'cpu_offloaded');self.assertEqual(r['cpu_layers'],3)
    def test_cpu_usage_is_not_placement(self):
        self.assertEqual(placement(['CPU load: 100%'])['status'],'unverified')
    def test_mapped_or_pinned_buffer_not_proof(self):
        r=placement(['CPU_Mapped model buffer size = 500 MiB','CUDA_Host compute buffer = 5 MiB','offloaded 33/33 layers to GPU'])
        self.assertEqual(r['status'],'full_gpu')
    def test_cpu_kv_gate(self):
        self.assertEqual(placement(['offloaded 33/33 layers to GPU','CPU KV buffer size = 64.00 MiB'])['status'],'cpu_offloaded')
    def test_impossible_ratios_not_trusted(self):
        for text in ['offloaded 34/33 layers to GPU','offloaded 0/0 layers to GPU']:
            self.assertEqual(placement([text])['status'],'unverified')
    def test_bounded_layer_recovery(self):
        self.assertEqual(recovery_layers(33),[24,16,8,3]);self.assertEqual(recovery_layers(2),[1]);self.assertEqual(recovery_layers(None),[])
    def test_classes_distinct_identity(self):
        self.assertNotEqual(fallback_id('a'*64),'a'*64);self.assertEqual(fallback_id('a'*64),fallback_id('a'*64))
    def test_growth_is_generous_but_finite(self):
        c={'allocated_tokens':8192,'native_tokens':32768}
        self.assertEqual(next_context(c)['allocated_tokens'],16384)
        self.assertEqual(next_context(c,20000)['allocated_tokens'],32768)
        self.assertIsNone(next_context({'allocated_tokens':32768,'native_tokens':32768}))
    def test_only_memory_failure_is_recovery_eligible(self):
        self.assertIsInstance(classify_load_failure('CUDA out of memory'),DoesNotFit)
        self.assertFalse(classify_load_failure('unknown model architecture').recoverable)

if __name__=='__main__':unittest.main()
