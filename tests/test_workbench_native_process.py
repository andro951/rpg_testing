import os,sys,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from workbench.native import NativeBackend,capabilities,loading_phase
from workbench.execution_policy import CPUOffload,RunFailure,RuntimeStall
from workbench.workflows import Cancelled
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
 def test_legacy_load_timeout_is_ignored_and_no_watchdog_is_armed(self):
  self.b.settings['load_timeout_seconds']=.01
  with patch.object(self.b,'budget',side_effect=AssertionError('Loading must not arm a watchdog')), \
       patch.dict(os.environ,{'STUB_STARTUP_DELAY':'.2','STUB_PROBE_DELAY':'.2'}):
   metadata=self.load()
  self.assertIsNone(metadata['load_timeout_seconds'])
  self.assertEqual(metadata['load_timeout_policy'],'completion_manual_stop_or_runtime_error')
  self.assertEqual(self.b.transport.timeout,60)
  self.assertEqual(metadata['loading_diagnostics']['phase'],'Ready')
 def test_loading_readiness_has_unlimited_reads_but_health_polling_is_bounded(self):
  timeouts=[];request=self.b.transport.request
  def capture(path,*args,**kwargs):
   timeouts.append((path,self.b.transport.timeout));return request(path,*args,**kwargs)
  with patch.object(self.b.transport,'request',side_effect=capture):self.load()
  self.assertTrue(any(path=='/v1/chat/completions' and value is None for path,value in timeouts))
  self.assertTrue(all(value==1 for path,value in timeouts if path=='/health'))
  self.assertEqual(self.b.transport.timeout,60)
 def test_loading_reports_phase_elapsed_time_and_runtime_activity(self):
  events=[];progress=[];self.b.log=lambda category,message:events.append((category,message))
  self.b.progress=lambda *args:progress.append(args)
  with patch('workbench.native.LOAD_DIAGNOSTIC_INTERVAL',.05),patch.dict(os.environ,{'STUB_STARTUP_DELAY':'.3'}):
   metadata=self.load()
  status=[message for category,message in events if category=='model_loading']
  self.assertTrue(any(s['phase']=='Loading model weights' and s['seconds_since_runtime_output'] is not None for s in status))
  self.assertTrue(any(s['elapsed_seconds']>.1 for s in status))
  self.assertTrue(any('last runtime output' in str(item) for item in progress))
  self.assertNotIn(self.b.token,str(status))
 def test_manual_stop_interrupts_loading_and_unloads_only_owned_process(self):
  cancel=threading.Event();errors=[]
  def load():
   try:self.b.load({'id':'stopped-stub','paths':['unused']},{'allocated_tokens':8192},cancel)
   except Exception as exc:errors.append(exc)
  with patch.dict(os.environ,{'STUB_STARTUP_DELAY':'10'}):
   worker=threading.Thread(target=load);worker.start()
   until=time.monotonic()+3
   while not self.b.lines and time.monotonic()<until:time.sleep(.01)
   process=self.b.process
   try:cancel.set();self.b.cancel();worker.join(3)
   finally:
    if worker.is_alive():self.b.unload();worker.join(3)
  self.assertFalse(worker.is_alive());self.assertIsInstance(errors[0],Cancelled)
  self.assertIsNotNone(process.poll());self.assertIsNone(self.b.process)
  self.assertEqual(self.b.transport.timeout,60)
 def test_runtime_crash_during_loading_preserves_error_without_waiting_for_deadline(self):
  with patch.dict(os.environ,{'STUB_LOAD_ERROR':'Runtime failed: invalid model artifact'}):
   with self.assertRaisesRegex(RunFailure,'invalid model artifact'):self.load()
  self.assertIsNone(self.b.process);self.assertEqual(self.b.transport.timeout,60)
  self.assertIsNone(self.b.load_metadata['load_timeout_seconds'])
 def test_loading_phases_follow_runtime_evidence(self):
  self.assertEqual(loading_phase('llama_model_loader: loaded meta data'),'Reading model metadata')
  self.assertEqual(loading_phase('load_tensors: loading model tensors'),'Loading model weights')
  self.assertEqual(loading_phase('llama_context: constructing llama_context'),'Allocating context and runtime buffers')
  self.assertEqual(loading_phase('warming up the model with an empty run'),'Warming up model')
  self.assertIsNone(loading_phase('A silence is not proof of a hang'))
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
 def test_case_watchdog_preserves_partial_without_killing_model(self):
  self.load();p=self.b.process
  with self.assertRaises(RuntimeStall) as cm:
   with self.b.budget(.15,terminate_process=False):
    self.b.generate([{'role':'user','content':'PARTIAL_FOREVER'}],{},None)
  self.assertEqual(cm.exception.partial_response['text'],'PARTIAL')
  self.assertIsNone(p.poll());self.assertEqual(self.b.clear_cache()['n_erased'],0)
if __name__=='__main__':unittest.main()
