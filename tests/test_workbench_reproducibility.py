import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench.controller import Controller
from workbench.domain import ResultStore, case_id, read_json, digest
from workbench.analysis import summarize

ROOT = Path(__file__).resolve().parents[1]

class ReproducibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT/'test_specs', self.root/'test_specs')
        self.app = Controller(self.root, True); self.app.selftest = lambda: None
        self.test = read_json(self.root/'test_specs/time_only.json')
        self.model = self.app.catalog()[0]
    def identity(self, test=None, variant=None, rep=0):
        t = test or self.test
        return case_id(self.model,t,variant or t['variants'][0],rep,{'vram_gb':8})
    def test_adding_repetitions_keeps_existing_case_ids(self):
        t = copy.deepcopy(self.test); t['repetitions'] = 5
        self.assertEqual(self.identity(), self.identity(t))
        self.assertNotEqual(self.identity(rep=1), self.identity(rep=0))
    def test_neighboring_variant_does_not_invalidate(self):
        t = copy.deepcopy(self.test); t['variants'][1]['steps'][0]['prompt'] = 'different prompt'
        self.assertEqual(self.identity(), self.identity(t))
    def test_selected_variant_does_invalidate(self):
        t = copy.deepcopy(self.test); t['variants'][0]['steps'][0]['sampling']['seed'] = 7
        self.assertNotEqual(self.identity(), self.identity(t))
    def test_presentation_labels_do_not_invalidate(self):
        t=copy.deepcopy(self.test); t['name']='New label';t['description']='Display';t['enabled']=True
        self.assertEqual(self.identity(), self.identity(t))
    def test_source_changes_invalidate(self):
        t=copy.deepcopy(self.test);t['source']['new_information']='A different fact'
        self.assertNotEqual(self.identity(),self.identity(t))
    def test_retry_history_survives_completion(self):
        cid=self.identity();store=self.app.store
        for status,text in [('error','first transport failed'),('aborted','user stopped'),('completed','answer')]:
            store.save({'status':status,'model_id':self.model['id'],'case_id':cid,'raw':text})
        result=store.read(store.path(self.model['id'],cid))
        self.assertEqual(result['status'],'completed')
        self.assertEqual([r['status'] for r in result['attempts']],['error','aborted'])
        self.assertEqual(result['attempts'][0]['raw'],'first transport failed')
        self.assertNotIn('attempts', result['attempts'][1])
        self.assertTrue(store.done(self.model['id'],cid))
    def test_delete_removes_history_and_completion(self):
        self.test_retry_history_survives_completion();cid=self.identity()
        self.app.store.path(self.model['id'],cid).unlink()
        self.assertFalse(self.app.store.done(self.model['id'],cid))
    def test_resume_context_independent_of_pending_tests(self):
        large=read_json(self.root/'test_specs/clothing_append.json')
        large['shared_prefix']='Background library. '*1800
        (self.root/'test_specs/clothing_append.json').write_text(json.dumps(large))
        first=self.app.check();context=self.app.plan['groups'][0]['context']
        for j in self.app.plan['groups'][0]['jobs']:
            if j['test']['id']=='clothing_append':
                self.app.store.save({'status':'completed','model_id':self.model['id'],'case_id':j['case_id']})
        second=self.app.check()
        configured=[read_json(p) for p in (self.root/'test_specs').glob('*.json')]
        expected_remaining=sum(t.get('repetitions',1)*sum(v.get('enabled',True) for v in t['variants']) for t in configured if t.get('enabled',True) and t['id']!='clothing_append')
        self.assertEqual(second['plan']['pending'],expected_remaining)
        self.assertEqual(context,self.app.plan['groups'][0]['context'])
        self.assertEqual(first['plan']['target'],second['plan']['target'])
    def test_summary_separates_artifacts_test_versions_and_simulation(self):
        base={'case_id':'a','model_id':'m','variant_id':'v','test_id':'t','status':'completed',
              'artifact_hashes':{'m.gguf':'a'},'test_definition':self.test,'score':{'exact_match':True}}
        changed_artifact={**base,'case_id':'b','artifact_hashes':{'m.gguf':'b'}}
        changed_test={**base,'case_id':'c','test_definition':{**self.test,'source':{'event':'different'}}}
        sim={**base,'case_id':'d','simulated':True}
        self.assertEqual(len(summarize([base,changed_artifact,changed_test,sim])['groups']),4)
    def test_prior_errors_counted_without_regrading(self):
        r={'case_id':'a','model_id':'m','status':'completed','score':{'exact_match':False},
           'attempts':[{'status':'error'},{'status':'aborted'}]}
        g=summarize([r])['groups'][0]
        self.assertEqual(g['prior_infrastructure_errors'],1);self.assertEqual(g['prior_attempts'],2)
        self.assertEqual(g['scored'],1);self.assertEqual(g['exact_match_rate'],0)
    def test_corrupt_summary_is_not_internal_server_error(self):
        result=summarize([{'status':'corrupt','case_id':'broken','model_id':'m','error':'checksum'}])
        self.assertEqual(result['records'],0);self.assertEqual(len(result['corrupt_files']),1)

if __name__=='__main__':unittest.main()
