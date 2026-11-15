"""Synthetic common-context protocol checks; never select a real study or run models."""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from workbench import study_protocol as protocol
from workbench.controller import Controller
from workbench.domain import ResultStore, case_id, digest, write_json, code_fingerprint
from workbench.inventory import automatic_context
from workbench.planning import _compatible_completed_result
from workbench import preflight, perchance
from optimization.coverage import scope
from optimization.coverage_unity import bundle
from tests.test_perchance import fixture as answer_fixture, FakeBackend


def sample(tokens=8192, study='synthetic-study'):
    return {'schema_version':1, 'study_id':study,
            'context':{'policy':protocol.VERSION,'tokens':tokens,'capacity_policy':protocol.CAPACITY_POLICY},
            'qualification_evidence':[{'reference':'synthetic-not-live-qualification','sha256':'a'*64}]}


class StudyProtocolTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.test=answer_fixture();self.test['variants'][0]['cache']='default'
        write_json(self.root/'test_specs/fixture.json',self.test)
        self.app=Controller(self.root,True)

    def select(self, value=None):
        value=sample() if value is None else value
        write_json(self.root/protocol.FILENAME,value)
        return value

    def test_absent_protocol_has_exact_automatic_context_and_scope(self):
        self.assertIsNone(protocol.load(self.root))
        meta={'model.context_length':65536}
        self.assertEqual(protocol.context_plan([self.test],meta),automatic_context([self.test],meta))
        report,plan=preflight.build(self.app,track_progress=False)
        self.assertNotIn('study_protocol',plan['target'])
        self.assertEqual(plan['target']['context_recipe'],automatic_context([self.test],{'x.context_length':2**63-1})['allocated_tokens'])
        with patch('prompt_builder.coverage.runtime_report',return_value={}):
            frozen=scope(self.root)
        self.assertEqual(set(frozen),{'workflow','definitions'})
        self.assertFalse((self.root/protocol.FILENAME).exists())

    def test_schema_and_limits_fail_closed(self):
        malformed=[]
        for value in (None,{},[],{'schema_version':1}):malformed.append(value)
        for tokens in (None,True,False,8192.0,'8192',0,511,2**31):
            value=sample();value['context']['tokens']=tokens;malformed.append(value)
        for mutate in (lambda v:v.update(schema_version=True),lambda v:v.update(study_id='../other'),
                       lambda v:v.update(extra=True),lambda v:v.update(qualification_evidence=[]),
                       lambda v:v['context'].update(policy='auto'),lambda v:v['context'].update(capacity_policy='expand'),
                       lambda v:v['qualification_evidence'][0].update(sha256='bad'),
                       lambda v:v['qualification_evidence'].append(dict(v['qualification_evidence'][0]))):
            value=sample();mutate(value);malformed.append(value)
        for value in malformed:
            with self.subTest(value=value),self.assertRaises(ValueError):protocol.validate(value)
        self.select({'schema_version':1})
        report,plan=preflight.build(self.app,track_progress=False)
        self.assertFalse(report['ready']);self.assertEqual(plan['pending'],0)
        self.assertEqual(report['issues'][0]['id'],'study_protocol')

    def test_duplicate_json_and_symlink_are_rejected(self):
        path=self.root/protocol.FILENAME
        path.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(ValueError,'Duplicate study protocol JSON field'):protocol.load(self.root)
        path.unlink()
        other=self.root/'elsewhere.json';write_json(other,sample())
        try:path.symlink_to(other)
        except (OSError,NotImplementedError) as exc:self.skipTest(str(exc))
        with self.assertRaisesRegex(ValueError,'regular file'):protocol.load(self.root)

    def test_explicit_common_value_is_exact_not_floor_round_or_native_override(self):
        value=sample(7168)
        test=copy.deepcopy(self.test);test['variants'][0]['steps'][0]['prompt']='large state '*10000
        before=copy.deepcopy(test)
        for native in (8192,16384,262144):
            result=protocol.context_plan([test],{'model.context_length':native},value)
            self.assertEqual(result['allocated_tokens'],7168)
            self.assertEqual(result['native_tokens'],native)
            self.assertTrue(result['input_may_exceed_allocated_context'])
            self.assertEqual(result['capacity_policy'],'fixed-case-local-v1')
            self.assertIsNone(result['output_cap'])
        self.assertEqual(test,before)
        for metadata in ({},{'model.context_length':4096}):
            with self.assertRaises(ValueError):protocol.context_plan([test],metadata,value)

    def test_preflight_target_and_actual_model_plan_share_exact_common_value(self):
        value=self.select(sample(7168))
        report,plan=preflight.build(self.app,track_progress=False)
        self.assertTrue(report['ready'],report['issues'])
        self.assertEqual(plan['target']['context_recipe'],7168)
        self.assertEqual(plan['target']['study_protocol'],protocol.snapshot(value))
        self.assertEqual(plan['groups'][0]['context']['allocated_tokens'],7168)
        self.assertEqual(plan['groups'][0]['context']['native_tokens'],65536)
        # Even a huge prompt must not silently enlarge the requested common C.
        self.test['variants'][0]['steps'][0]['prompt']='x'*50000
        write_json(self.root/'test_specs/fixture.json',self.test)
        _,again=preflight.build(self.app,track_progress=False)
        self.assertEqual(again['target']['context_recipe'],7168)
        self.assertEqual(again['groups'][0]['context']['allocated_tokens'],7168)
        self.select(sample(131072))
        report,_=preflight.build(self.app,track_progress=False)
        self.assertFalse(report['ready'])
        self.assertTrue(any(i['id'].startswith('context_') for i in report['issues']))

    def test_native_identity_and_exact_resume_include_protocol_even_at_same_allocation(self):
        variant=self.test['variants'][0];model={'id':'m','sha256':{'m.gguf':'a'*64}}
        auto={'context_recipe':8192};one={**auto,'study_protocol':protocol.snapshot(sample())}
        other={**auto,'study_protocol':protocol.snapshot(sample(12288))}
        ids=[case_id(model,self.test,variant,0,t) for t in (auto,one,other)]
        self.assertEqual(len(set(ids)),3)
        record={'model_id':'m','test_id':self.test['id'],'variant_id':variant['id'],'repetition':0,
                'target':one,'provenance':{'workflow_code':code_fingerprint()},'artifact_hashes':model['sha256'],
                'test_definition':self.test,'variant_definition':variant,'status':'completed'}
        self.assertIsNotNone(_compatible_completed_result([record],model,self.test,variant,0,one,code_fingerprint()))
        self.assertIsNone(_compatible_completed_result([record],model,self.test,variant,0,auto,code_fingerprint()))
        self.assertIsNone(_compatible_completed_result([record],model,self.test,variant,0,other,code_fingerprint()))

    def test_scope_changes_on_protocol_edits_and_includes_frozen_evidence(self):
        with patch('prompt_builder.coverage.runtime_report',return_value={}):
            before=scope(self.root);value=self.select();after=scope(self.root)
            self.assertNotEqual(digest(before),digest(after))
            self.assertEqual(after['study_protocol'],protocol.snapshot(value))
            value['qualification_evidence'][0]['sha256']='b'*64;self.select(value)
            self.assertNotEqual(digest(scope(self.root)),digest(after))

    def test_explicit_native_context_requires_positive_equal_runtime_evidence(self):
        explicit=protocol.context_plan([self.test],{'model.context_length':65536},sample())
        protocol.verify_native_context(explicit,8192)
        for actual in (None,0,True,'8192',4096,16384):
            with self.subTest(actual=actual),self.assertRaisesRegex(ValueError,'verify the exact common'):
                protocol.verify_native_context(explicit,actual)
        changed=copy.deepcopy(explicit);changed['allocated_tokens']=4096
        with self.assertRaisesRegex(ValueError,'differs from its frozen'):protocol.verify_native_context(changed,4096)
        # Preserve legacy behavior for callers without an explicit study.
        protocol.verify_native_context({'allocated_tokens':8192},None)
        with self.assertRaisesRegex(ValueError,'changed the context'):protocol.verify_native_context({'allocated_tokens':8192},4096)

    def worker(self):
        return {'model_id':'model','model':{'id':'model','files':['model.gguf'],'required_vram_gb':12},
                'model_path':'/models/model.gguf','runtime_path':'/runtime/llama-server','python':'/runtime/python',
                'ssh':['ssh','authorized-host'],'constraint':'titanx','qos':'normal','remote_base':'/runs',
                'inference_port':24321,'kind':'unity'}

    def packet(self):
        with patch('prompt_builder.coverage.runtime_report',return_value={}):frozen=scope(self.root)
        worker=self.worker();state={'id':'batch','scope':frozen,'suite_digest':digest(frozen),'workers':[worker]}
        return bundle(SimpleNamespace(root=self.root,settings={'backend':'llamacpp'}),state,worker),state

    def test_unity_bundle_freezes_same_protocol_and_rejects_changed_selection(self):
        value=self.select();packet,state=self.packet()
        self.assertIn(protocol.FILENAME,packet['manifest']['source_files'])
        with tarfile.open(fileobj=io.BytesIO(base64.b64decode(packet['archive'])),mode='r:gz') as archive:
            raw=archive.extractfile(protocol.FILENAME).read()
        self.assertEqual(json.loads(raw),value)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),packet['manifest']['source_files'][protocol.FILENAME])
        self.assertEqual(packet['manifest']['source_digest'],digest(packet['manifest']['source_files']))
        self.select(sample(12288))
        with self.assertRaisesRegex(ValueError,'differs from the frozen'):bundle(SimpleNamespace(root=self.root,settings={}),state,self.worker())

    def test_unity_worker_blocks_protocol_byte_tamper_before_controller(self):
        from workbench import coverage_worker
        self.select();packet,state=self.packet()
        with tempfile.TemporaryDirectory() as temp:
            destination=Path(temp)
            with tarfile.open(fileobj=io.BytesIO(base64.b64decode(packet['archive'])),mode='r:gz') as archive:archive.extractall(destination,filter="data")
            write_json(destination/protocol.FILENAME,sample(12288))
            with patch.dict(os.environ,{'SLURM_JOB_ID':'synthetic'}),patch.object(coverage_worker,'Controller') as controller:
                with self.assertRaisesRegex(ValueError,'Frozen worker source changed'):coverage_worker.run(destination)
            controller.assert_not_called()

    def test_remote_unsupported_context_never_splits_independent_observations(self):
        settings={};selection={'model_id':perchance.MODEL_ID};store=ResultStore(self.root/'remote-results')
        plain={'backend':'perchance','vram_gb':8}
        plans=[perchance.plan([self.test],settings,{**plain,**extra},store,selection)
               for extra in ({},{'context_request':protocol.remote_context(sample())},
                             {'context_request':protocol.remote_context(sample(12288))})]
        self.assertEqual([p['independent_observations'] for p in plans],[3,3,3])
        self.assertEqual([[g['case_id'] for g in p['groups']] for p in plans],[ [g['case_id'] for g in plans[0]['groups']] ]*3)
        self.assertEqual(len({g['case_id'] for g in plans[0]['groups']}),3) # repetitions are independent
        request=plans[1]['groups'][0]['aliases'][0]['context_request']
        self.assertEqual(request['requested_tokens'],8192)
        self.assertIsNone(request['applied_tokens']);self.assertIsNone(request['provider_context_limit'])
        self.assertEqual(request['control_status'],'unsupported');self.assertEqual(request['verification_status'],'unknown')
        self.assertNotIn('study_protocol',plans[1]['groups'][0]['effective'])
        for change in ('state','prompt','review'):
            other=copy.deepcopy(self.test)
            if change=='state':other['source']['initial_state']={'changed':True}
            elif change=='prompt':other['variants'][0]['steps'][0]['prompt']+=' changed'
            else:other['variants'][0]['retry_enabled']=True
            p=perchance.plan([other],settings,plain,store,selection)
            self.assertNotEqual(p['groups'][0]['case_id'],plans[0]['groups'][0]['case_id'])

    def test_perchance_preflight_reports_requested_context_not_applied(self):
        self.select();app=Controller(self.root);app.settings['sync_source']=False
        with patch.object(perchance,'browser_executable',return_value=__file__),patch.object(perchance.importlib.util,'find_spec',return_value=object()):
            report,plan=perchance.preflight(app,preparation={'gpu_name':'GTX 1080','vram_gb':8},selection={'model_id':perchance.MODEL_ID})
        self.assertEqual(plan['target']['context_request']['requested_tokens'],8192)
        self.assertIsNone(plan['target']['context_request']['applied_tokens'])
        self.assertFalse(report['ready']) # preparation is not a live ready claim


if __name__=='__main__':unittest.main()
