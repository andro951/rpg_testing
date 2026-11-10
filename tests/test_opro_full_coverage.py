"""No inference: durable promotion, exact evidence, and submission recovery contracts."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench.controller import Controller
from workbench.domain import read_json, write_json, digest
from optimization.storage import Store
from optimization import coverage
from optimization.engine import trial_key
from test_builder.automatic_promotion import compiled

REPO=Path(__file__).resolve().parents[1]


class CoverageTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        shutil.copytree(REPO/'test_specs',self.root/'test_specs')
        shutil.copytree(REPO/'test_builder',self.root/'test_builder',ignore=shutil.ignore_patterns('__pycache__','active_opro_promotions.json'))
        self.app=Controller(self.root);self.app.catalog=lambda:[{'id':'native-a','files':['a.gguf'],'required_vram_gb':8}]
        tests=[read_json(p) for p in (self.root/'test_specs').glob('*.json')]
        tests=[t for t in tests if t['prompt_builder']['operation']=='move']
        cases={t['id']+'/'+v['id']:{'test':t,'variant':v} for t in tests for v in t['variants']}
        candidate=read_json(REPO/'test_builder/promotions/dot-root-prefix-move-v1.json')['candidate']
        candidate=copy.deepcopy(candidate);candidate['system']+='\nSynthetic validation marker.'
        self.model={'id':'native-a','identity':'a','provider':'native'}
        self.session={'id':'synthetic-session','status':'perfect','scope':{'cases':cases,'layers':[{'members':list(cases)}],
            'workflow_fingerprint':coverage.code_fingerprint()},'cohort':{'models':[self.model]},
            'attempts':[{'number':1,'status':'complete','candidate':candidate}],'observations':[]}
        for case in cases.values():
            for rep in range(case['test']['repetitions']):
                record={'trial_key':trial_key(self.session,candidate,self.model,case,rep),'status':'completed','pass':True}
                self.session['observations'].append(Store(self.root).evidence(self.session['id'],record))
        Store(self.root).save(self.session)

    def test_success_promotes_normal_builder_and_freezes_every_configured_model(self):
        write_json(self.app.data/'coverage-workers.json',{'unity':[{'model_id':'unity-a'}]})
        key=coverage.promote(self.app,self.session['id']);state=coverage.read_state(self.root,key)
        self.assertEqual(state['status'],'pending')
        self.assertEqual(state['workers'][0]['models'],['native-a','perchance-text-generator'])
        self.assertEqual(state['workers'][1]['models'],['unity-a'])
        fixtures=read_json(self.root/'test_builder/fixtures.json')['fixtures']
        for tid,test in state['promotion']['after'].items():
            fixture=next(f for f in fixtures if f['id']==test['prompt_builder']['fixture'])
            self.assertEqual(compiled(self.root,fixture,test['prompt_builder']['method']),test)
            before=state['promotion']['before'][tid]
            for field in ('source','expected_state','state_schema','repetitions','timeout_seconds'):
                self.assertEqual(test[field],before[field])
        self.assertEqual(coverage.promote(self.app,self.session['id']),key)
        self.assertEqual(len(list((self.root/'coverage_results').glob('*/state.json'))),1)

    def test_failed_incomplete_or_explicitly_nonaccepted_candidate_never_promotes(self):
        for field,value in [('status','attempt_limit'),('review_status','rejected'),('observations',[])]:
            session=copy.deepcopy(self.session)
            if field=='review_status':session['attempts'][0][field]=value
            else:session[field]=value
            Store(self.root).save(session)
            self.assertIsNone(coverage.promote(self.app,session['id']))
            self.assertFalse((self.root/'test_builder/active_opro_promotions.json').exists())

    def test_structural_review_rejects_fixture_specific_winner(self):
        candidate=self.session['attempts'][0]['candidate']
        candidate['system']+=' The source is item-17.'
        # Simulated successful trial keys are rebuilt; the independent structural review still rejects it.
        self.session['observations']=[]
        for case in self.session['scope']['cases'].values():
            for rep in range(case['test']['repetitions']):
                self.session['observations'].append(Store(self.root).evidence(self.session['id'],
                    {'trial_key':trial_key(self.session,candidate,self.model,case,rep),'status':'completed','pass':True}))
        Store(self.root).save(self.session)
        with self.assertRaisesRegex(ValueError,'literal fixture element ID'):coverage.promote(self.app,self.session['id'])

    def test_crash_mid_promotion_replays_without_overwriting_conflicts(self):
        from test_builder import automatic_promotion
        rebuild=automatic_promotion.rebuild
        with patch.object(automatic_promotion,'rebuild',side_effect=OSError('interrupted write')):
            with self.assertRaises(OSError):coverage.promote(self.app,self.session['id'])
        key=coverage.promote(self.app,self.session['id'])
        self.assertEqual(coverage.read_state(self.root,key)['status'],'pending')

    def test_interruption_after_first_definition_write_is_idempotent(self):
        from workbench import domain
        original=domain.write_json;written=[]
        def interrupted(path,value):
            original(path,value)
            if path.parent.name=='test_specs' and not written:
                written.append(str(path));raise OSError('crash after saved definition')
        with patch.object(domain,'write_json',side_effect=interrupted):
            with self.assertRaisesRegex(OSError,'crash after'):coverage.promote(self.app,self.session['id'])
        key=coverage.promote(self.app,self.session['id'])
        self.assertEqual(coverage.read_state(self.root,key)['status'],'pending')

    def test_normal_promotion_refreshes_definition_bound_sidecars(self):
        for folder in ('reporting','evaluation','optimization','prompts','prompt-review'):
            shutil.copytree(REPO/folder,self.root/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
        key=coverage.promote(self.app,self.session['id'])
        from optimization.catalog import validate
        result=validate(self.root,read_json(self.root/'optimization/sharing.json'))
        self.assertEqual(result['variants'],62)
        self.assertEqual(coverage.read_state(self.root,key)['status'],'pending')

    def test_changed_base_or_changed_current_suite_blocks(self):
        case=next(iter(self.session['scope']['cases'].values()));p=self.root/'test_specs'/(case['test']['id']+'.json')
        t=read_json(p);t['instructions']+='changed';write_json(p,t)
        with self.assertRaisesRegex(ValueError,'base definition changed'):coverage.promote(self.app,self.session['id'])
        write_json(p,case['test']);key=coverage.promote(self.app,self.session['id'])
        t=read_json(p);t['instructions']+='changed';write_json(p,t)
        self.assertEqual(coverage.advance_once(self.app,key)['status'],'blocked')

    def test_missing_model_and_provider_are_honestly_blocked(self):
        with patch.object(self.app,'build_preflight',return_value=({'issues':[]},{'groups':[]})):
            rows,_,_=coverage.summarize(self.app,['native-a','perchance-text-generator'])
        self.assertEqual([r['status'] for r in rows],['blocked','blocked'])

    def test_terminal_wrong_answer_reused_but_skipped_infrastructure_not_complete(self):
        key=coverage.promote(self.app,self.session['id'])
        test=next(iter(coverage.read_state(self.root,key)['promotion']['after'].values()))
        target={'vram_gb':8};model={'id':'native-a','files':['a.gguf'],'required_vram_gb':8}
        plan={'groups':[{'model':model,'jobs':[],'complete':999}], 'target':target}
        from workbench.domain import case_id
        for variant in test['variants']:
            for rep in range(test['repetitions']):
                record={'model_id':model['id'],'case_id':case_id(model,test,variant,rep,target),'status':'completed',
                    'test_id':test['id'],'variant_id':variant['id'],'repetition':rep,'target':target,
                    'test_definition':test,'variant_definition':variant,'provenance':{'workflow_code':coverage.code_fingerprint()},
                    'score':{'exact_match':False}}
                self.app.store.save(record)
        with patch.object(self.app,'build_preflight',return_value=({},plan)),patch.object(coverage,'load_tests',return_value=[test]):
            rows,_,_=coverage.summarize(self.app,['native-a']);self.assertEqual(rows[0]['status'],'completed')
            p=next(self.app.store.root.glob('*/*.json'));p.unlink()
            rows,_,_=coverage.summarize(self.app,['native-a']);self.assertEqual(rows[0]['status'],'partial')

    def test_blocked_worker_is_not_automatically_retried_while_siblings_run(self):
        key=coverage.promote(self.app,self.session['id']);state=coverage.read_state(self.root,key)
        state['workers'][0].update(status='blocked',error='storage fault');coverage.save(self.root,state)
        with patch.object(self.app,'run') as run:
            self.assertEqual(coverage.advance_once(self.app,key)['status'],'blocked')
            run.assert_not_called()

    def test_resume_stops_polling_without_cancelling_submitted_jobs(self):
        state={'id':'a','message':'queued','workers':[{'id':'unity-a','kind':'unity','status':'queued','receipt':{'job_id':'123'}}]}
        self.app.cancel_event.set()
        with patch.object(coverage,'advance_once',return_value=state),patch.object(coverage,'save') as save:
            self.assertEqual(coverage.resume(self.app,'a')['status'],'stopped')
        self.assertEqual(state['workers'][0]['receipt']['job_id'],'123')

    def test_completed_status_detects_deleted_or_changed_raw_evidence(self):
        key=coverage.promote(self.app,self.session['id']);state=coverage.read_state(self.root,key)
        p=self.root/'raw.json';p.write_text('original')
        state.update(status='completed');state['workers'][0].update(status='completed',rows=[{'status':'completed','evidence':[coverage.evidence_file(p)]}])
        coverage.save(self.root,state)
        self.assertEqual(coverage.read_state(self.root,key)['status'],'completed')
        p.unlink()
        self.assertEqual(coverage.read_state(self.root,key)['status'],'partial')

    def test_restart_recovers_monitoring_but_preserves_explicit_stop(self):
        key=coverage.promote(self.app,self.session['id'])
        with patch.object(self.app,'start') as start:
            self.assertEqual(coverage.restore_pending(self.app),key)
            start.assert_called_once_with('coverage',{'id':key})
        state=coverage.read_state(self.root,key);state['status']='stopped';coverage.save(self.root,state)
        with patch.object(self.app,'start') as start:coverage.restore_pending(self.app);start.assert_not_called()

    def test_unity_ambiguous_submit_stays_blocked_and_existing_receipt_never_resubmits(self):
        from optimization import coverage_unity as unity
        self.assertIn("intent.open('x')",unity.SUBMIT)
        self.assertIn('No resubmission',unity.SUBMIT)
        worker={'model_id':'unity-a','kind':'unity','receipt':{'job_id':'12','suite_digest':'s','model_id':'unity-a','root':'/r'}}
        with patch.object(unity,'bundle') as bundle,patch.object(unity,'ssh',return_value={'queue':'PENDING'}):
            unity.advance(self.app,{'suite_digest':'s'},worker)
            unity.advance(self.app,{'suite_digest':'s'},worker)
        bundle.assert_not_called();self.assertEqual(worker['status'],'queued')


if __name__=='__main__':unittest.main()
