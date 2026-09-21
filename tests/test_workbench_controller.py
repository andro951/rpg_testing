import copy
import io
import json
import shutil
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from workbench.controller import Controller
from workbench.domain import read_json,write_json
from workbench import preflight

ROOT=Path(__file__).resolve().parents[1]

def configured_case_count(folder):
    tests=[read_json(p) for p in folder.glob('*.json')]
    return sum(t.get('repetitions',1)*sum(v.get('enabled',True) for v in t['variants']) for t in tests if t.get('enabled',True))

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);shutil.copytree(ROOT/'test_specs',self.root/'test_specs')
        self.app=Controller(self.root,demo=True);self.app.selftest=lambda:None
    def test_preflight_no_inference(self):
        with patch('workbench.controller.DemoBackend') as backend:
            self.assertTrue(self.app.check()['ready']);backend.assert_not_called()
    def test_configured_cases_and_resume(self):
        expected=configured_case_count(self.root/'test_specs')
        self.app.run();self.assertEqual(self.app.completed_now,expected)
        records=self.app.store.all();self.assertEqual(len(records),expected)
        self.assertTrue(all(r['simulated'] and r['score']['exact_match'] for r in records))
        self.app.run();self.assertEqual(self.app.completed_now,0)
        self.assertEqual(self.app.report['plan']['pending'],0)
        self.assertEqual(self.app.report['plan']['complete'],expected)
    def test_delete_result_reruns_one(self):
        self.app.run();r=self.app.store.all()[0]
        self.app.delete_result(r['model_id'],r['case_id']);self.app.run()
        self.assertEqual(self.app.completed_now,1)
    def test_export_no_settings_or_secrets(self):
        self.app.settings['model_api_token']='very-secret';self.app.log('test','very-secret')
        self.app.run();z=zipfile.ZipFile(io.BytesIO(self.app.export()))
        self.assertTrue(any(x.startswith('results/') for x in z.namelist()))
        self.assertFalse(any('settings' in x for x in z.namelist()))
        self.assertTrue(all(b'very-secret' not in z.read(n) for n in z.namelist()))
    def test_snapshot_no_token(self):
        self.app.settings['model_api_token']='secret';self.assertNotIn('secret',json.dumps(self.app.snapshot()))
    def test_unknown_settings(self):
        with self.assertRaises(ValueError):self.app.configure({'temperature':.5})
        with self.assertRaises(ValueError):self.app.configure({'context_tokens':4096})
    def test_state_after_background_preflight(self):
        self.app.start();self.app.thread.join(5)
        self.assertFalse(self.app.operation.locked());self.assertEqual(self.app.state,'idle')
        self.assertTrue(self.app.report['ready'])
    def test_busy_rejects_conflicting_ops(self):
        self.app.operation.acquire()
        try:
            for f in [lambda:self.app.start(),lambda:self.app.configure({'backend':'llamacpp'}),self.app.export]:
                with self.assertRaises(RuntimeError):f()
        finally:self.app.operation.release()
    def test_fix_must_be_current_issue(self):
        self.app.check()
        with self.assertRaises(ValueError):self.app.fix({'issue_id':'run_shell','cmd':'evil'})
    def test_missing_folder_fix_requires_click(self):
        shutil.rmtree(self.app.data/'logs');self.app.check()
        shutil.rmtree(self.app.data/'results');report=self.app.check()
        self.assertIn('folder_results',[i['id'] for i in report['issues']])
        self.app.fix({'issue_id':'folder_results'});self.assertTrue((self.app.data/'results').is_dir())
    def test_preparation_cannot_claim_gpu_ready(self):
        report=self.app.check({'gpu_name':'A100','vram_gb':80})
        self.assertTrue(report['preparation_only']);self.assertFalse(report['ready'])
    def test_selftests_failure_prevents_run(self):
        def fail():raise RuntimeError('selftest failed')
        self.app.selftest=fail
        self.app.start('run');self.app.thread.join(3)
        self.assertEqual(self.app.state,'error');self.assertEqual(self.app.store.all(),[])
    def test_cancel_can_interrupt_workflow(self):
        self.app.cancel_event.set()
        from workbench.workflows import Cancelled
        with self.assertRaises(Cancelled):self.app.run()
    def test_errors_saved_not_hidden_retry(self):
        class Broken:
            load_metadata={}
            def __init__(self,*a):pass
            def load(self,*a):return {}
            def unload(self):pass
            supports_schema=True;supports_cache=True
            def generate(self,*a):return {'text':'not JSON','finish_reason':'stop'}
        with patch('workbench.controller.DemoBackend',Broken):self.app.run()
        records=self.app.store.all();self.assertEqual(len(records),configured_case_count(self.root/'test_specs'))
        self.assertTrue(all(r['status']=='completed' and not r['score']['valid'] for r in records))
    def test_pins_from_results_no_weights(self):
        self.app.run();m={'id':'demo-2b','files':['demo.gguf']}
        self.assertEqual(self.app.with_known_pins([m])[0]['sha256'],{'demo.gguf':'a'*64})
if __name__=='__main__':unittest.main()
