import copy
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench.controller import Controller
from workbench.domain import ResultStore,read_json,validate_test
from workbench.workflows import execute,messages
from workbench.demo_native import DemoNative as DemoBackend
ROOT=Path(__file__).resolve().parents[1]

class EdgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);shutil.copytree(ROOT/'test_specs',self.root/'test_specs')
        self.app=Controller(self.root,True);self.app.selftest=lambda:None
    def test_corrupt_result_manual_fix(self):
        self.app.run();record=self.app.store.all()[0];path=self.app.store.path(record['model_id'],record['case_id'])
        path.write_text('[]')
        report=self.app.check();self.assertFalse(report['ready'])
        issue=next(i for i in report['issues'] if i['id'].startswith('corrupt_'))
        self.assertEqual(issue['label'],'Delete corrupted result');self.assertTrue(path.exists())
        self.app.fix({'issue_id':issue['id']});self.assertFalse(path.exists())
        self.assertTrue(self.app.check()['ready']);self.app.run();self.assertEqual(self.app.completed_now,1)
    def test_corrupt_result_inspectable(self):
        self.app.run();record=self.app.store.all()[0];path=self.app.store.path(record['model_id'],record['case_id'])
        path.write_text('broken')
        self.assertEqual(sum(r['status']=='corrupt' for r in self.app.result_records()),1)
    def test_corrupt_result_still_exports_logs_and_raw_file(self):
        import io,json,zipfile
        self.app.run();record=self.app.store.all()[0];path=self.app.store.path(record['model_id'],record['case_id'])
        path.write_text('broken')
        archive=zipfile.ZipFile(io.BytesIO(self.app.export()))
        summary=json.loads(archive.read('summary.json'))
        self.assertEqual(len(summary['corrupt_files']),1)
        self.assertTrue(any(n.startswith('logs/') for n in archive.namelist()))
        self.assertEqual(archive.read(path.relative_to(self.app.data).as_posix()),b'broken')
    def test_cached_prefix_included_in_automatic_context(self):
        from workbench.inventory import automatic_context
        t=read_json(self.root/'test_specs/time_only.json')
        small=automatic_context([t],{'x.context_length':65536})
        t['shared_prefix']='A much larger shared state. '*1500
        large=automatic_context([t],{'x.context_length':65536})
        self.assertGreater(large['allocated_tokens'],small['allocated_tokens'])
        self.assertGreater(large['input_estimate_bytes'],40000)
    def test_byte_estimate_not_claimed_as_exact_token_count(self):
        from workbench.inventory import automatic_context
        t=read_json(self.root/'test_specs/time_only.json');t['shared_prefix']=' hello'*2000
        result=automatic_context([t],{'x.context_length':4096})
        self.assertEqual(result['allocated_tokens'],4096)
        self.assertTrue(result['input_may_exceed_native_context'])
    def test_no_remote_schema_references(self):
        test=read_json(self.root/'test_specs/time_only.json')
        test['state_schema']={'$ref':'https://example.invalid/schema.json'}
        with self.assertRaises(ValueError):validate_test(test)
    def test_finite_sampler_ranges(self):
        for key,value in [('min_p',2),('top_k',-1),('repeat_penalty',0),('seed',1.5)]:
            test=read_json(self.root/'test_specs/time_only.json')
            test['variants'][0]['steps'][0]['sampling'][key]=value
            with self.assertRaises(ValueError):validate_test(test)
    def test_skipped_followup_safe_to_reference(self):
        t=read_json(self.root/'test_specs/time_only.json')
        prompt=messages(t,{'prompt':'Make patch','uses':['new_time']},{})
        self.assertIn('skipped',prompt[-2]['content'])
    def test_pause_and_resume(self):
        class Slow(DemoBackend):
            def generate(self,*a,**kw):time.sleep(.05);return super().generate(*a,**kw)
        with patch('workbench.demo_native.DemoNative',Slow):
            self.app.start('run')
            deadline=time.monotonic()+10
            while self.app.current is None and time.monotonic()<deadline:time.sleep(.01)
            self.app.control('pause')
            while self.app.state!='paused' and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(self.app.state,'paused')
            count=len(self.app.store.all());time.sleep(.15);self.assertEqual(len(self.app.store.all()),count)
            self.app.control('resume');self.app.thread.join(30)
            self.assertFalse(self.app.thread.is_alive(),'Resumed demo run did not finish')
            self.assertFalse(self.app.operation.locked());self.assertEqual(self.app.report['plan']['pending'],0)
    def test_stop_now_records_aborted_without_deadlock(self):
        class Slow(DemoBackend):
            def generate(self,*a,**kw):
                cancel=a[-1]
                for _ in range(100):
                    if cancel and cancel.is_set():
                        from workbench.workflows import Cancelled
                        raise Cancelled('test cancel')
                    time.sleep(.01)
                return super().generate(*a,**kw)
        with patch('workbench.demo_native.DemoNative',Slow):
            self.app.start('run');deadline=time.monotonic()+5
            while (not self.app.current or not self.app.current.get('test')) and time.monotonic()<deadline:time.sleep(.01)
            self.app.control('stop');self.app.thread.join(5)
            self.assertFalse(self.app.operation.locked());self.assertEqual(self.app.state,'stopped')
            self.assertTrue(any(r['status']=='aborted' for r in self.app.store.all()))
    def test_context_policy_part_of_result_identity(self):
        source=(ROOT/'workbench/domain.py').read_text()
        self.assertIn("'inventory.py'",source.split('def code_fingerprint():',1)[1].split('def case_id',1)[0])
    def test_health_check_not_semantic_readiness_gate(self):
        source=(ROOT/'workbench/native.py').read_text()
        self.assertIn("self.load_metadata['health_exact_ready']",source)
        self.assertNotIn("raise BackendError('Not READY')",source)
if __name__=='__main__':unittest.main()
