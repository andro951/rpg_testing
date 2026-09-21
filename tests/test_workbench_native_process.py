import os,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from workbench.native import NativeBackend
from workbench.execution_policy import CPUOffload,RuntimeStall
ROOT=Path(__file__).resolve().parents[1]
class ProcessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.b=NativeBackend({'backend':'llamacpp','llama_path':sys.executable,'runtime_cache':self.tmp.name},{'uuid':'GPU-SIMULATED'})
  self.addCleanup(self.b.unload)
  def args(exe,model,context,help_text,layers='all'):
   return [sys.executable,str(ROOT/'tests/helpers/native_stub.py'),'--port','1235','--alias',self.b.owned_id,'--ctx-size',str(context['allocated_tokens'])]
  self.patcher=patch.object(self.b,'launch_arguments',side_effect=args);self.patcher.start();self.addCleanup(self.patcher.stop)
  self.cap=patch('workbench.native.capabilities',return_value={'help':'','version':'SIMULATED STUB'});self.cap.start();self.addCleanup(self.cap.stop)
 def load(self):return self.b.load({'id':'integration-stub','paths':['not-used.gguf']},{'allocated_tokens':8192,'native_tokens':65536})
 def test_owned_process_load_probe_generation_unload(self):
  metadata=self.load();process=self.b.process
  self.assertEqual(metadata['placement']['status'],'full_gpu');self.assertFalse(metadata['health_exact_ready'])
  r=self.b.generate([{'role':'user','content':'Test'}],{'seed':42,'temperature':0},None)
  self.assertEqual(r['text'],'[]');self.b.unload();self.assertIsNotNone(process.poll())
 def test_seed_reproducibility_diagnostic(self):
  self.load();result=self.b.seed_reproducibility_check()
  self.assertTrue(result['same_seed_exact_match'])
  self.assertTrue(result['different_seed_changes_output'])
  self.assertTrue(result['seed_behavior_verified'])
  self.assertEqual(result['runs'][0]['digest'],result['runs'][1]['digest'])
  self.assertNotEqual(result['runs'][0]['digest'],result['runs'][2]['digest'])
 def test_detected_cpu_placement_unloads_before_benchmark(self):
  with patch.dict(os.environ,{'STUB_LAYERS':'30/33'}):
   with self.assertRaises(CPUOffload) as cm:self.load()
  self.assertEqual(cm.exception.evidence['cpu_layers'],3);self.assertIsNone(self.b.process)
 def test_watchdog_cancels_stuck_call_and_owned_process(self):
  self.load();p=self.b.process;t=time.monotonic()
  with self.assertRaises(RuntimeStall):
   with self.b.budget(.15):self.b.generate([{'role':'user','content':'WAIT_FOREVER'}],{},None)
  self.b.unload();self.assertLess(time.monotonic()-t,3);self.assertIsNotNone(p.poll())
if __name__=='__main__':unittest.main()
