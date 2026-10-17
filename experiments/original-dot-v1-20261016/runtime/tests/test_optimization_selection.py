"""Selectable OPRO origins, immutable evidence handoff and host-aware routes."""
import copy
import io
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs
from urllib.request import Request, urlopen
from optimization.engine import create, generation_packet, packet_messages
from optimization.selection import targets, validate_target, from_result, fragment
from optimization.storage import Store
from optimization.templates import freeze
from reporting.report import build_report
from reporting.server import ReviewServer
from workbench.controller import Controller
from workbench.domain import ResultStore, code_fingerprint, digest, read_json, write_json
from workbench.judgements import JudgementStore
from workbench.server import WorkbenchServer
from tests.test_prompt_optimization import native

ROOT=Path(__file__).resolve().parents[1]


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for folder in ('test_specs','optimization/definitions','docs/prompt-optimization'):
            shutil.copytree(ROOT/folder,self.root/folder)
        self.app=Controller(self.root,demo=True)
        # Exercise the normal study-results routes using only synthetic records.
        self.app.store=ResultStore(self.root/'results')
        self.cohort={'models':[native()], 'gpu':{'name':'Mock GPU','total_gib':8},'simulated':False,'excluded':[],'default_generator':'local-a'}

    def target(self,operation='copy',variant='full_paths'):
        return next(t for t in targets(self.root) if t['test_id']=='db_v3_'+operation+'_record__value_patch' and t['variant_id']==variant)

    def record(self,operation='copy'):
        selected=self.target(operation)
        test=read_json(self.root/'test_specs'/(selected['test_id']+'.json'))
        variant=next(v for v in test['variants'] if v['id']==selected['variant_id'])
        record={'case_id':digest([selected,'synthetic']), 'model_id':'local-a','model_name':'Mock local model',
                'test_id':test['id'],'variant_id':variant['id'],'test_definition':test,'variant_definition':variant,
                'status':'completed','simulated':True,'repetition':0,'score':{'valid':True,'exact_match':False},
                'outputs':{'patch':'[]'},'pipeline_seconds':1,'provenance':{'workflow_code':code_fingerprint()},
                'calls':[{'step':'patch','request_messages':[{'role':'user','content':variant['steps'][0]['prompt']}],
                          'text':'[]','finish_reason':'stop'}]}
        store=ResultStore(self.root/'results')
        store.save(record)
        return store.read(store.path(record['model_id'],record['case_id']))

    def session(self,target,source=None):
        return create(self.app,{'generator_id':'local-a','target':{k:target[k] for k in ('test_id','variant_id','definition_id') if k in target},
                               **({'source_result':source} if source else {})},self.cohort)

    def test_all_current_presentations_are_selectable_and_each_operation_freezes_its_own_group(self):
        available=targets(self.root)
        self.assertEqual(len(available),62)
        for task_type in {item['task_type'] for item in available}:
            target=next(item for item in available if item['task_type']==task_type)
            with self.subTest(task_type=task_type):
                session=self.session(target)
                scope=session['scope']
                self.assertEqual(scope['target']['definition_id'],target['definition_id'])
                self.assertEqual(scope['layers'][0]['members'],[target['test_id']+'/'+target['variant_id']])
                self.assertEqual(len(scope['cases']),sum(item['task_type']==task_type for item in available))
                self.assertEqual(session['definition']['target']['test_id'],target['test_id'])
                self.assertEqual(session['definition']['scope_plan']['task_type'],task_type)
                self.assertIn('selected database task',session['prompt_builder']['task_definition'])
                self.assertNotIn('containing one move operation',session['prompt_builder']['task_definition'])

    def test_unknown_stale_disabled_and_rejected_targets_never_fall_back_to_move(self):
        target=self.target()
        for changed in ({**target,'definition_id':'0'*64},{'test_id':'missing','variant_id':'full_paths'}):
            with self.assertRaises(ValueError):self.session(changed)
        path=self.root/'test_specs'/(target['test_id']+'.json')
        test=read_json(path);test['enabled']=False;write_json(path,test)
        with self.assertRaisesRegex(ValueError,'unavailable'):self.session(target)
        test['enabled']=True;write_json(path,test)
        JudgementStore(self.root).update([target['definition_id']],'rejected','bad test','unit test')
        with self.assertRaisesRegex(ValueError,'unavailable'):self.session(target)

    def test_exact_result_handoff_preserves_selected_model_presentation_and_evidence(self):
        record=self.record()
        store=ResultStore(self.root/'results');path=store.path(record['model_id'],record['case_id']);before=path.read_bytes()
        selection,_=from_result(self.root,record['model_id'],record['case_id'])
        query=parse_qs(fragment(selection))
        self.assertEqual(query['variant_id'],['full_paths']);self.assertEqual(query['origin_model_id'],['local-a'])
        session=self.session(selection['target'],selection['source_result'])
        packet=generation_packet(session,self.cohort['models'],[],Store(self.root))
        self.assertEqual(packet['starting_result']['case_id'],record['case_id'])
        self.assertEqual(packet['starting_result']['evaluation']['objective_outcome'],'FAIL')
        self.assertEqual(packet['baseline_summary']['recorded'],0)
        self.assertEqual(session['observations'],[])
        self.assertIn('Saved result selected by the user',packet_messages(session,packet)[0]['content'])
        self.assertEqual(path.read_bytes(),before)
        archive=Store(self.root).export(session['id'])
        with tempfile.TemporaryDirectory() as folder:
            restored=Store(Path(folder));restored.import_archive(archive)
            self.assertEqual(restored.get_evidence(session['id'],session['source_result_evidence']),record)

    def test_result_reference_is_not_fed_to_an_unavailable_model_cohort(self):
        record=self.record();selection,_=from_result(self.root,record['model_id'],record['case_id'])
        session=self.session(selection['target'],selection['source_result'])
        packet=generation_packet(session,[native('another-model')],[],Store(self.root))
        self.assertNotIn('starting_result',packet)

    def test_changed_results_wrong_tests_and_old_workflows_are_rejected(self):
        record=self.record()
        with self.assertRaisesRegex(ValueError,'does not match'):
            self.session(self.target('move'),{'model_id':'local-a','case_id':record['case_id']})
        path=ResultStore(self.root/'results').path(record['model_id'],record['case_id'])
        for kind in ('definition','workflow'):
            changed=copy.deepcopy(record)
            if kind=='definition':changed['variant_definition']['steps'][0]['prompt']+=' Changed.'
            else:changed['provenance']['workflow_code']='old'
            changed.pop('sha256',None);changed['sha256']=digest(changed);write_json(path,changed)
            with self.subTest(kind=kind),self.assertRaises(ValueError):from_result(self.root,'local-a',record['case_id'])

    def test_saved_session_cannot_run_changed_tests_under_the_same_id(self):
        from optimization.engine import Engine
        selected=self.target();session=self.session(selected)
        path=self.root/'test_specs'/(selected['test_id']+'.json')
        test=read_json(path);test['variants'][0]['steps'][0]['prompt']+=' Changed.';write_json(path,test)
        with patch('optimization.engine.Runtime') as runtime:
            with self.assertRaisesRegex(ValueError,'has changed'):Engine(self.app,session['id']).run()
            runtime.assert_not_called()

    def serve(self,server):
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def close():server.shutdown();server.server_close();thread.join(5)
        self.addCleanup(close)
        return f'http://127.0.0.1:{server.server_port}'

    def test_workbench_results_and_handoff_use_same_host_and_csp_safe_scripts(self):
        record=self.record();base=self.serve(WorkbenchServer(('127.0.0.1',0),self.app))
        with urlopen(base+'/api/optimization/targets') as response:data=json.load(response)
        self.assertEqual(len(data['targets']),62)
        with urlopen(base+'/results/') as response:html=response.read().decode()
        self.assertIn('src="/report-report.js"',html)
        self.assertIn('"base_url":"/"',html)
        with urlopen(base+'/result/') as response:self.assertEqual(response.status,200)
        with urlopen(base+'/api/optimization/from-result?model_id=local-a&case_id='+record['case_id']) as response:
            selection=json.load(response)
        self.assertEqual(selection['target']['test_id'],record['test_id'])
        self.assertEqual(Store(self.root).list(),[])

    def test_review_handoff_requires_explicit_authorized_post_and_starts_no_session(self):
        record=self.record()
        report=build_report([record],[read_json(p) for p in (self.root/'test_specs').glob('*.json')])
        server=ReviewServer(('127.0.0.1',0),self.root,report);base=self.serve(server)
        payload=json.dumps({'model_id':'local-a','case_id':record['case_id']}).encode()
        request=Request(base+'/api/optimization/open',data=payload,headers={'Content-Type':'application/json'})
        with patch('optimization.handoff.open_local',return_value='http://127.0.0.1:8765/#selected') as launch:
            with self.assertRaises(HTTPError) as rejected:urlopen(request)
            self.assertEqual(rejected.exception.code,403);launch.assert_not_called()
            request.add_header('X-Judgement-Token',server.token)
            with urlopen(request) as response:self.assertEqual(json.load(response)['url'],'http://127.0.0.1:8765/#selected')
            launch.assert_called_once()
        self.assertEqual(Store(self.root).list(),[])

    def test_local_handoff_reuses_matching_worker_and_rejects_another_project(self):
        from optimization.handoff import open_local
        record=self.record();selection,_=from_result(self.root,'local-a',record['case_id'])
        def response(root):return io.BytesIO(json.dumps({'application':'rpg-workbench','root':str(root)}).encode())
        with patch('optimization.handoff.urlopen',side_effect=lambda *a,**k:response(self.root)),patch('optimization.handoff.subprocess.Popen') as launch:
            url=open_local(self.root,selection);launch.assert_not_called()
            self.assertIn('test_id=db_v3_copy_record',url)
        with patch('optimization.handoff.urlopen',side_effect=lambda *a,**k:response(ROOT)):
            with self.assertRaisesRegex(ValueError,'another project'):open_local(self.root,selection)

    def test_local_handoff_starts_worker_only_when_missing_and_reports_start_failure(self):
        from optimization.handoff import open_local
        record=self.record();selection,_=from_result(self.root,'local-a',record['case_id'])
        identity=json.dumps({'application':'rpg-workbench','root':str(self.root)}).encode()
        with patch('optimization.handoff.urlopen',side_effect=[URLError('not running'),io.BytesIO(identity)]),patch('optimization.handoff.subprocess.Popen') as launch:
            self.assertIn('#page=optimization',open_local(self.root,selection))
            self.assertEqual(launch.call_args.args[0][-1],'--no-browser')
            self.assertEqual(launch.call_args.kwargs['cwd'],self.root)
        with patch('optimization.handoff.urlopen',side_effect=URLError('not running')),patch('optimization.handoff.subprocess.Popen') as launch:
            launch.return_value.poll.return_value=1
            with self.assertRaisesRegex(ValueError,'could not open'):open_local(self.root,selection)

    def test_controller_rejects_invalid_selection_before_worker_or_inference(self):
        record=self.record();selected,_=from_result(self.root,'local-a',record['case_id'])
        payload={'target':{key:selected['target'][key] for key in ('test_id','variant_id','definition_id')},'source_result':selected['source_result']}
        for change in ({'target':{**payload['target'],'definition_id':'0'*64}},
                       {'source_result':{'model_id':'local-a'}},
                       {'target':{key:value for key,value in self.target('move').items() if key in ('test_id','variant_id','definition_id')}}):
            with self.subTest(change=change),patch('workbench.controller.threading.Thread') as worker:
                with self.assertRaises(ValueError):self.app.start('optimization',{**payload,**change})
                worker.assert_not_called()
                self.assertFalse(self.app.operation.locked())
        self.assertEqual(Store(self.root).list(),[])
