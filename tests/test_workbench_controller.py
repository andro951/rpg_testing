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
    def test_progress_snapshot_reports_completed_preflight_and_run(self):
        self.app.check()
        p=self.app.snapshot()['progress'];self.assertEqual(p['phase'],'preflight');self.assertEqual(p['overall_percent'],100)
        self.app.run()
        p=self.app.snapshot()['progress'];self.assertEqual(p['phase'],'run');self.assertEqual(p['overall_percent'],100)
    def test_preflight_no_inference(self):
        with patch('workbench.demo_native.DemoNative') as backend:
            self.assertTrue(self.app.check()['ready']);backend.assert_not_called()
    def test_configured_cases_and_resume(self):
        expected=configured_case_count(self.root/'test_specs')
        self.app.run();self.assertEqual(self.app.completed_now,expected)
        records=self.app.store.all();self.assertEqual(len(records),expected)
        self.assertTrue(all(r['simulated'] and r['score']['exact_match'] for r in records))
        self.assertTrue(all(r['load']['seed_reproducibility']['status']=='simulated' for r in records))
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
    def test_blocked_preflight_issues_are_recorded_in_evidence(self):
        shutil.rmtree(self.app.data/'logs')
        report=self.app.check()
        self.assertFalse(report['ready']);self.assertIn('folder_logs',[i['id'] for i in report['issues']])
        z=zipfile.ZipFile(io.BytesIO(self.app.export()))
        report_files=[n for n in z.namelist() if n.startswith('preflight_reports/') and n.endswith('.json')]
        self.assertTrue(report_files)
        saved=json.loads(z.read(report_files[-1]));self.assertIn('folder_logs',[i['id'] for i in saved['issues']])
        summary=json.loads(z.read('summary.json'))
        self.assertIn('folder_logs',[i['id'] for i in summary['latest_preflight']['issues']])
        logs=b'\n'.join(z.read(n) for n in z.namelist() if n.startswith('logs/') and n.endswith('.json'))
        self.assertIn(b'preflight_issue',logs);self.assertIn(b'folder_logs',logs)
    def test_run_blocked_logs_issue_details(self):
        shutil.rmtree(self.app.data/'logs')
        self.app.run();self.assertEqual(self.app.store.all(),[])
        z=zipfile.ZipFile(io.BytesIO(self.app.export()))
        logs=b'\n'.join(z.read(n) for n in z.namelist() if n.startswith('logs/') and n.endswith('.json'))
        self.assertIn(b'run_blocked',logs);self.assertIn(b'folder_logs',logs)

    def test_preparation_cannot_claim_gpu_ready(self):
        report=self.app.check({'gpu_name':'A100','vram_gb':80})
        self.assertTrue(report['preparation_only']);self.assertFalse(report['ready'])
    def test_preflight_and_benchmark_run_do_not_invoke_unit_tests(self):
        def fail():raise AssertionError('unit tests must be explicit, not part of preflight/run')
        self.app.selftest=fail
        self.assertTrue(self.app.check()['ready'])
        self.app.run()
        self.assertTrue(self.app.store.all())
    def test_explicit_unit_test_action_failure_is_separate(self):
        def fail():raise RuntimeError('selftest failed')
        self.app.selftest=fail
        self.app.start('unit_tests');self.app.thread.join(3)
        self.assertEqual(self.app.state,'error');self.assertEqual(self.app.store.all(),[])
    def test_cancel_can_interrupt_workflow(self):
        self.app.cancel_event.set()
        from workbench.workflows import Cancelled
        with self.assertRaises(Cancelled):self.app.run()
    def test_errors_saved_not_hidden_retry(self):
        from workbench.demo_native import DemoNative
        class Broken(DemoNative):
            load_metadata={}
            def __init__(self,*a):pass
            def load(self,*a,**kw):return {}
            def unload(self):pass
            supports_schema=True;supports_cache=True
            def generate(self,*a):return {'text':'not JSON','finish_reason':'stop'}
        with patch('workbench.demo_native.DemoNative',Broken):self.app.run()
        records=self.app.store.all();self.assertEqual(len(records),configured_case_count(self.root/'test_specs'))
        self.assertTrue(all(r['status']=='completed' and not r['score']['valid'] for r in records))
    def test_artifact_identity_from_results_needs_no_weights(self):
        self.app.run();m={'id':'demo-2b','files':['demo.gguf']}
        identity=self.app.with_known_artifacts([m])[0]['artifact_identity']
        self.assertEqual(identity['files'][0]['name'],'demo.gguf');self.assertEqual(identity['sha256'],{'demo.gguf':'a'*64})
if __name__=='__main__':unittest.main()
