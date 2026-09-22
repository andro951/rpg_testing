import os,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from workbench.native import NativeBackend,capabilities
from workbench.execution_policy import CPUOffload,RunFailure,RuntimeStall
ROOT=Path(__file__).resolve().parents[1]
class ProcessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.tmp_path=Path(self.tmp.name)
  self.b=NativeBackend({'backend':'llamacpp','llama_path':sys.executable,'runtime_cache':self.tmp.name},{'uuid':'GPU-SIMULATED'})
  self.addCleanup(self.b.unload)
  def args(exe,model,context,help_text,layers='all'):
   return [sys.executable,str(ROOT/'tests/helpers/native_stub.py'),'--port','1235','--alias',self.b.owned_id,'--ctx-size',str(context['allocated_tokens'])]
  self.patcher=patch.object(self.b,'launch_arguments',side_effect=args);self.patcher.start();self.addCleanup(self.patcher.stop)
  self.cap=patch('workbench.native.capabilities',return_value={'help':'','version':'SIMULATED STUB'});self.cap.start();self.addCleanup(self.cap.stop)
 def load(self):return self.b.load({'id':'integration-stub','paths':['not-used.gguf']},{'allocated_tokens':8192,'native_tokens':65536})
 def test_launch_requests_trace_verbosity_for_placement_evidence(self):
  backend=NativeBackend({'backend':'llamacpp','llama_path':'llama-server','runtime_cache':str(self.tmp_path)},{'uuid':'GPU-SIMULATED'})
  backend.owned_id='test'
  args=backend.launch_arguments('llama-server',{'paths':['model.gguf']},{'allocated_tokens':8192},
      '--reasoning MODE --log-verbosity N --slot-save-path PATH --jinja --no-webui --no-mmproj --op-offload --kv-offload')
  self.assertIn('--reasoning',args)
  self.assertEqual(args[args.index('--reasoning')+1],'off')
  self.assertIn('--log-verbosity',args)
  self.assertEqual(args[args.index('--log-verbosity')+1],'4')
  self.assertIn('--slot-save-path',args)
  slot_path=Path(args[args.index('--slot-save-path')+1])
  self.assertTrue(slot_path.is_dir())
  self.assertEqual(slot_path.resolve(),(self.tmp_path/'slots').resolve())
 def test_capabilities_require_reasoning_control(self):
  required='--ctx-size --n-predict --gpu-layers --parallel --no-context-shift --slots --fit --api-key --list-devices'
  with patch('workbench.native.diagnostic_command',side_effect=[required,'v']):
   with self.assertRaises(RunFailure) as cm:capabilities('llama-server',preparation=True)
  self.assertIn('--reasoning',str(cm.exception))
  with patch('workbench.native.diagnostic_command',side_effect=[required+' --reasoning MODE','v']):
   self.assertIn('--reasoning',capabilities('llama-server',preparation=True)['help'])
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
