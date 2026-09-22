import tempfile
import unittest
from pathlib import Path
from workbench.domain import ResultStore, eligibility
from workbench.planning import pending_plan, validate_catalog, requirements, public_plan


def model():
    return {'id':'demo-2b','files':['test.gguf'],'required_vram_gb':8,'sha256':{'test.gguf':'a'*64}}

def fixture():
    return {'schema_version':2,'id':'t1','workflow':'steps','timeout_seconds':60,'source':{'initial_state':{'time':'14:15'},'new_information':'Exactly five minutes pass.'},'expected_state':{'time':'14:20'},'variants':[{'id':'direct','steps':[{'id':'patch','type':'generate','prompt':'Return JSON patch.','output':{'type':'text'},'sampling':{'temperature':0,'seed':42}}],'result':{'step':'patch','representation':'json_patch'}}]}

class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ResultStore(Path(self.tmp.name));self.target={'gpu_name':'test','vram_gb':8,'backend':'demo'}
    def plan(self,m=None,t=None):return pending_plan(m or [model()],t or [fixture()],self.target,self.store)
    def test_pending_before_artifacts(self):self.assertEqual(self.plan()['pending'],1)
    def test_completed_model_needs_no_files(self):
        p=self.plan();j=p['groups'][0]['jobs'][0]
        self.store.save({'status':'completed','model_id':'demo-2b','case_id':j['case_id'],'score':{'exact_match':False}})
        self.assertEqual(self.plan()['pending'],0)
        self.assertEqual(self.plan()['model_loads'],0)
    def test_delete_is_rerun(self):
        j=self.plan()['groups'][0]['jobs'][0]
        path=self.store.save({'status':'completed','model_id':'demo-2b','case_id':j['case_id']})
        path.unlink();self.assertEqual(self.plan()['pending'],1)
    def test_abort_pending(self):
        j=self.plan()['groups'][0]['jobs'][0]
        self.store.save({'status':'aborted','model_id':'demo-2b','case_id':j['case_id']})
        self.assertEqual(self.plan()['pending'],1)
    def test_corrupt_not_completed(self):
        j=self.plan()['groups'][0]['jobs'][0];path=self.store.path('demo-2b',j['case_id']);path.parent.mkdir()
        path.write_text('{"status":"completed"}')
        with self.assertRaises(ValueError):self.plan()
    def test_tier_neighbors_only(self):
        for capacity in [8,11,12]:self.assertIsNotNone(eligibility(8,capacity))
        for capacity in [16,24,80]:self.assertIsNone(eligibility(8,capacity))
        self.assertIsNone(eligibility(12,11));self.assertIsNotNone(eligibility(12,16))
    def test_larger_gpu_not_universal(self):
        self.target['vram_gb']=80;self.assertEqual(self.plan()['pending'],0)
    def test_unassigned(self):
        m=model();m['required_vram_gb']=None;self.assertEqual(self.plan([m])['unassigned'],['demo-2b'])
    def test_repetitions(self):
        t=fixture();t['repetitions']=3;self.assertEqual(self.plan(t=[t])['pending'],3)
    def test_changed_test_identity(self):
        before=self.plan()['groups'][0]['jobs'][0]['case_id'];t=fixture();t['source']['new_information']='Ten minutes pass.'
        self.assertNotEqual(before,self.plan(t=[t])['groups'][0]['jobs'][0]['case_id'])
    def test_changed_model_identity(self):
        a=self.plan()['groups'][0]['jobs'][0]['case_id'];m=model();m['sha256']['test.gguf']='b'*64
        self.assertNotEqual(a,self.plan([m])['groups'][0]['jobs'][0]['case_id'])
    def test_report_does_not_expose_ground_truth(self):self.assertNotIn('expected_state',str(public_plan(self.plan())))
    def test_disabled_variant(self):
        t=fixture();t['variants'][0]['enabled']=False;self.assertEqual(self.plan(t=[t])['pending'],0)
    def test_nested_capability_requirements(self):
        t=fixture();v=t['variants'][0];v['cache']='on';v['steps']=[{'type':'loop','steps':[{'type':'generate','output':{'type':'boolean'}}]}]
        self.assertEqual(requirements(self.plan(t=[t])['groups'][0]),{'cache':True,'schema':True})
    def test_bad_catalogs(self):
        for key,value in [('required_vram_gb',11),('files',['../oops.gguf']),('sha256',{'test.gguf':'x'})]:
            m=model();m[key]=value
            with self.assertRaises(ValueError):validate_catalog([m])
        with self.assertRaises(ValueError):validate_catalog([model(),model()])
if __name__=='__main__':unittest.main()
