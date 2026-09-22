import copy
import json
import tempfile
import unittest
from pathlib import Path
from workbench.domain import eligibility, recommend_vram, validate_test, case_id, ResultStore, safe_id, read_json


def tiny_test():
    return {'schema_version':2, 'workflow':'steps', 'id':'tiny', 'timeout_seconds':60, 'source':{'initial_state':{'time':'14:15'},'new_information':'Five minutes pass.'},
            'variants':[{'id':'direct','steps':[{'id':'patch','type':'generate','prompt':'Return a patch.'}], 'result':{'step':'patch','representation':'json_patch'}}]}


class DomainTests(unittest.TestCase):
    def test_tier_schedule(self):
        for required, capacity, yes in [(8,8,1),(8,11,1),(8,12,1),(8,16,0),(8,80,0),(12,11,0),(12,12,1),(12,16,1),(16,24,1),(16,32,0),(80,79.1,1)]:
            with self.subTest(required=required,capacity=capacity):self.assertEqual(bool(eligibility(required,capacity)),bool(yes))
    def test_unknown_capacity_does_not_guess(self):
        self.assertIsNone(eligibility(12,11.5));self.assertIsNone(eligibility(None,16))
    def test_recommendation(self):
        self.assertEqual(recommend_vram(2*2**30),8);self.assertEqual(recommend_vram(8*2**30),12)
        self.assertIsNone(recommend_vram(100*2**30))
    def test_no_caps(self):
        for key in ['context_tokens','max_output_tokens','context_length','max_tokens']:
            t=tiny_test();t[key]=10
            with self.assertRaises(ValueError):validate_test(t)
    def test_valid_workflow(self):validate_test(tiny_test())
    def test_invalid_references(self):
        t=tiny_test();t['variants'][0]['steps'][0]['uses']=['missing']
        with self.assertRaises(ValueError):validate_test(t)
    def test_no_truth_in_source(self):
        t=tiny_test();t['source']['expected_state']={}
        with self.assertRaises(ValueError):validate_test(t)
    def test_invalid_sampling(self):
        for setting in [{'seed':-1},{'temperature':float('nan')},{'top_p':0},{'max_tokens':512}]:
            t=tiny_test();t['variants'][0]['steps'][0]['sampling']=setting
            with self.assertRaises(ValueError):validate_test(t)
    def test_condition(self):
        t=tiny_test();t['variants'][0]['steps'] += [{'id':'next','type':'generate','prompt':'Next','when':{'step':'patch','equals':True}}]
        validate_test(t)
    def test_loop(self):
        t=tiny_test();t['variants'][0]['steps'] += [{'id':'repair','type':'loop','max_iterations':2,'until':{'step':'check','equals':True},'steps':[{'id':'check','type':'generate','prompt':'Correct?','output':{'type':'boolean'}}]}]
        validate_test(t)
    def test_no_infinite_loop(self):
        t=tiny_test();t['variants'][0]['steps']=[{'id':'loop','type':'loop','steps':[]}]
        with self.assertRaises(ValueError):validate_test(t)
    def test_timeout_required_and_positive(self):
        for value in [None,0,-1,1.5,'60']:
            t=tiny_test()
            if value is None:t.pop('timeout_seconds')
            else:t['timeout_seconds']=value
            with self.assertRaises(ValueError):validate_test(t)
        validate_test(tiny_test())
    def test_identity(self):
        t=tiny_test();m={'id':'qwen','sha256':{'x':'abc'}};a=case_id(m,t,t['variants'][0],0,{'gpu':'1080'})
        self.assertNotEqual(a,case_id(m,t,t['variants'][0],1,{'gpu':'1080'}))
        t['source']['new_information']='Ten minutes.'
        self.assertNotEqual(a,case_id(m,t,t['variants'][0],0,{'gpu':'1080'}))
    def test_results_resume_and_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=ResultStore(Path(tmp));cid='a'*64
            r={'status':'completed','model_id':'m','case_id':cid,'score':{'exact_match':False}}
            p=store.save(r);self.assertTrue(store.done('m',cid))
            self.assertEqual(p.read_text().splitlines()[1],'  "status": "completed",')
            with self.assertRaises(ValueError):store.save(r)
            p.unlink();self.assertFalse(store.done('m',cid));store.save(r)
    def test_error_is_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=ResultStore(Path(tmp));r={'status':'error','model_id':'m','case_id':'a'*64};s.save(r)
            self.assertFalse(s.done('m','a'*64));r['status']='completed';s.save(r)
            self.assertTrue(s.done('m','a'*64))
    def test_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=ResultStore(Path(tmp));p=s.save({'status':'completed','model_id':'m','case_id':'a'*64})
            p.write_text(p.read_text().replace('completed','aborted'))
            with self.assertRaises(ValueError):s.done('m','a'*64)
    def test_path_traversal(self):
        for value in ['../x','/etc','a/b','']:
            with self.assertRaises(ValueError):safe_id(value)
    def test_strict_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.json'
            for text in ['{"x":1,"x":2}','{"x":NaN}','{"x":1e900}']:
                p.write_text(text)
                with self.assertRaises(ValueError):read_json(p)
    def test_input_not_mutated(self):
        t=tiny_test();old=copy.deepcopy(t);validate_test(t);self.assertEqual(old,t)

if __name__=='__main__':unittest.main()
