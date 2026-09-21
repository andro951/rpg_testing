import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from workbench.domain import load_tests,validate_test,read_json,digest
from workbench.backends import DemoBackend
from workbench.workflows import execute,Unsupported,messages
from workbench.analysis import summarize
from workbench.locking import HostLock,WorkerBusy

ROOT=Path(__file__).resolve().parents[1]

class ExtraTests(unittest.TestCase):
    def test_example_specs_all_valid(self):
        tests=load_tests(ROOT/'examples/test_specs')
        self.assertEqual(len(tests),3)
        for test in tests:
            for v in test['variants']:
                out=execute(test,v,DemoBackend())
                self.assertTrue(out['score']['exact_match'],out)
    def test_cache_missing_measurements_not_success(self):
        class Missing(DemoBackend):
            def generate(self,*args):
                r=super().generate(*args);r['cached_tokens']=None;return r
        t=read_json(ROOT/'examples/test_specs/cached_questions.json')
        self.assertFalse(execute(t,t['variants'][0],Missing())['measurement_valid'])
    def test_lmstudio_cache_rejected(self):
        b=DemoBackend();b.supports_cache=False
        t=read_json(ROOT/'examples/test_specs/cached_questions.json')
        with self.assertRaises(Unsupported):execute(t,t['variants'][0],b)
    def test_unknown_step_parameters_rejected(self):
        t=read_json(ROOT/'test_specs/time_only.json');t['variants'][0]['steps'][0]['shell']='echo unsafe'
        with self.assertRaises(ValueError):validate_test(t)
    def test_ground_truth_not_sent(self):
        t=read_json(ROOT/'test_specs/time_only.json');t['expected_state']['SECRET']='do not send'
        m=messages(t,t['variants'][0]['steps'][0],{})
        self.assertNotIn('SECRET',json.dumps(m));self.assertNotIn('expected_state',json.dumps(m))
    def test_lock_refuses_second_owner_and_releases(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'lock'
            with HostLock(path):
                with self.assertRaises(WorkerBusy):
                    with HostLock(path):pass
            with HostLock(path):pass
    def test_analysis_keeps_simulation_separate(self):
        records=[{'case_id':digest(i),'model_id':'m','variant_id':'v','status':'completed','simulated':bool(i),
                  'score':{'exact_match':True},'pipeline_seconds':1.0,'target':{}} for i in range(2)]
        self.assertEqual(len(summarize(records)['groups']),2)
    def test_analysis_conflict_rejected(self):
        r={'case_id':'a','model_id':'m','status':'completed'}
        with self.assertRaises(ValueError):summarize([r,{**r,'status':'error'}])
    def test_analysis_invalid_cache_not_in_score(self):
        r={'case_id':'a','model_id':'m','status':'completed','measurement_valid':False,'score':{'exact_match':True}}
        g=summarize([r])['groups'][0]
        self.assertEqual(g['scored'],0);self.assertEqual(g['invalid_measurements'],1)
if __name__=='__main__':unittest.main()
