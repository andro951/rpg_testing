"""Immutable old builder artifacts exercise maintained workflow/evaluator contracts.

Old generation-only assertions are retained as .py.txt archival test data. These
regressions never regenerate legacy definitions or import the deleted builder.
"""
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation.core import assess
from optimization.templates import bindings, freeze
from reporting.grouping import row_grouping
from reporting.timing import expectations
from tests.helpers.frozen_prompts import INPUTS, REPO, definition, historical_suite, reference, snapshots
from workbench.domain import digest, experiment_spec, read_json, validate_test
from workbench.prompt_rendering import preview
from workbench.scoring import apply, at, pointer
from workbench.workflows import evaluate, execute, messages


class PatchPromptBuilderTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = read_json(INPUTS/'fixtures.json')['fixtures']
        self.by_id = {f['id']:f for f in self.fixtures}
        self.archive = historical_suite().parent

    def test_original_research_and_retired_regression_sources_keep_exact_bytes(self):
        archive = REPO/'archives/test-suite-2026-10-14'
        manifest = read_json(archive/'manifest.json')
        self.assertEqual(len(manifest['definitions']),61)
        for entry in manifest['definitions']:
            self.assertEqual(hashlib.sha256((archive/entry['file']).read_bytes()).hexdigest(),entry['sha256'])
        sources = REPO/'archives/pre-template-builder/regression-test-sources'
        entries = read_json(sources/'manifest.json')['files']
        self.assertEqual(len(entries),8)
        for entry in entries:
            self.assertTrue(entry['file'].endswith('.py.txt'))
            self.assertEqual(hashlib.sha256((sources/entry['file']).read_bytes()).hexdigest(),entry['sha256'])
        self.assertEqual(len(read_json(REPO/'docs/test-suite-v2/deferred-tests.json')['tests']),10)

    def test_frozen_review_exports_and_message_files_are_exact(self):
        self.assertEqual(len(self.fixtures),21)
        manifest = read_json(self.archive/'prompts/patch-suite/manifest.json')['prompts']
        self.assertEqual(len(manifest),62)
        paths = {self.archive/p['review_file'] for p in manifest}
        self.assertEqual(set((self.archive/'prompt-review').glob('*.txt')),paths)
        for entry in manifest:
            exported=self.archive/entry['file']
            self.assertEqual((self.archive/entry['review_file']).read_bytes(),exported.read_bytes())
            self.assertEqual(hashlib.sha256(exported.read_bytes()).hexdigest(),entry['prompt_sha256'])
            test=read_json(historical_suite()/(entry['test_id']+'.json'))
            variant=next(v for v in test['variants'] if v['id']==entry['presentation'])
            request=messages(test,variant['steps'][0],{},variant)
            self.assertEqual(exported.read_text(),preview(request))
            self.assertEqual(read_json(exported.with_suffix('.messages.json')),request)

    def test_frozen_value_requests_and_references_still_pass_both_evaluators(self):
        method=(INPUTS/'methods/value_patch.txt').read_text().strip();checked=0
        for fixture in self.fixtures:
            test=definition(fixture['id']);before=copy.deepcopy(test)
            validate_test(test)
            answer,expected=reference(fixture['id'])
            self.assertEqual(test['expected_state'],expected)
            for variant in test['variants']:
                with self.subTest(fixture=fixture['id'],presentation=variant['id']):
                    prompt=variant['steps'][0]['prompt']
                    request=messages(test,variant['steps'][0],{},variant)
                    self.assertEqual(request,[{'role':'system','content':test['instructions']},{'role':'user','content':prompt}])
                    self.assertEqual(prompt.count(method),1)
                    self.assertEqual(prompt.count('Current data:\n'),1)
                    self.assertEqual(prompt.count('Task:\n'),1)
                    self.assertEqual(variant['steps'][0]['output'],{'type':'text'})
                    values={'patch':json.dumps(answer)}
                    self.assertTrue(evaluate(test,variant,values)['exact_match'])
                    self.assertEqual(assess(test,variant,values)['objective_outcome'],'PASS')
                    if fixture['task']!='no_change':
                        self.assertFalse(evaluate(test,variant,{'patch':'[]'})['exact_match'])
                    checked+=1
            self.assertEqual(test,before)
        self.assertEqual(checked,62)

    def test_frozen_review_digest_includes_both_system_and_user_messages(self):
        for fixture in self.fixtures:
            test=read_json(historical_suite()/(fixture['id']+'__value_patch.json'))
            requests={v['id']:messages(test,v['steps'][0],{},v) for v in test['variants']}
            self.assertEqual(digest(requests),test['prompt_builder']['prompt_digest'])
            for role in (0,1):
                edited=copy.deepcopy(requests)
                edited[next(iter(edited))][role]['content']+=' changed'
                self.assertNotEqual(digest(edited),test['prompt_builder']['prompt_digest'])

    def test_task_schema_and_expected_state_stay_independent_of_method(self):
        for fixture in self.fixtures:
            baseline=definition(fixture['id'])
            for method in ('original_value_patch_v1','dot_patch_v1'):
                other=definition(fixture['id'],method)
                for key in ('source','state_schema','expected_state','repetitions','timeout_seconds'):
                    self.assertEqual(other[key],baseline[key])
                self.assertNotEqual(other['id'],baseline['id'])
                self.assertEqual([v['id'] for v in other['variants']],[v['id'] for v in baseline['variants']])
        self.assertNotIn('json_patch',snapshots()['methods'])
        self.assertFalse(any(v['id']=='indexed_arrays' for row in snapshots()['methods']['value_patch'].values() for v in row['definition']['variants']))

    def test_empty_collections_keep_complete_historical_structure_and_identity(self):
        test=definition('db_v3_append_record_empty')
        for variant in test['variants']:
            prompt=variant['steps'][0]['prompt']
            self.assertIn('unique "item_id" value',prompt)
            self.assertIn('"count": number.',prompt)

    def test_no_change_keeps_unrelated_information_and_strict_empty_response(self):
        test=definition('db_v3_no_change')
        self.assertEqual(reference('db_v3_no_change'),([],test['source']['initial_state']))
        for variant in test['variants']:
            self.assertEqual(variant['prompt_bindings']['new_information'],'The documentation uses blue headings and a serif font.')
            self.assertEqual(variant['result']['required_ops'],[])
            for text in ('[]','[ \n ]'):
                self.assertTrue(evaluate(test,variant,{'patch':text})['exact_match'])
                self.assertEqual(assess(test,variant,{'patch':text})['objective_outcome'],'PASS')
            for op in ('replace','test'):
                response=json.dumps([{'op':op,'path':'/items/2/count','value':2}])
                self.assertFalse(evaluate(test,variant,{'patch':response})['exact_match'])
                self.assertEqual(assess(test,variant,{'patch':response})['objective_outcome'],'FAIL')

    def test_contract_blocks_whole_collection_and_record_replacement(self):
        for key in ('db_v3_append_record','db_v3_update_record'):
            test=definition(key);variant=test['variants'][0]
            if key.endswith('append_record'):
                patch_value=[{'op':'replace','path':'/items','value':test['expected_state']['items']}]
            else:
                patch_value=[{'op':'replace','path':'/items/1','value':test['expected_state']['items'][1]}]
            self.assertEqual(apply(test['source']['initial_state'],patch_value,'json_patch'),test['expected_state'])
            values={'patch':json.dumps(patch_value)}
            score=evaluate(test,variant,values)
            self.assertFalse(score['exact_match']);self.assertFalse(score['valid'])
            report=assess(test,variant,values)
            self.assertTrue(any(c['status']=='failed' and c['code']=='patch.application_failed' for c in report['checks']))

    def test_append_targets_collection_and_move_preserves_both_collection_orders(self):
        test=definition('db_v3_append_record');variant=test['variants'][0]
        response=reference('db_v3_append_record')[0];response[0]['path']='/items/4'
        self.assertFalse(evaluate(test,variant,{'patch':json.dumps(response)})['exact_match'])
        response[0]['path']='/items'
        self.assertTrue(evaluate(test,variant,{'patch':json.dumps(response)})['exact_match'])
        for key in ('db_v3_move_record','db_v3_move_record_empty','db_v3_move_value'):
            fixture=self.by_id[key];_,after=reference(key);p=fixture['parameters']
            source=at(fixture['state'],pointer(p['array_path']))
            destination=at(fixture['state'],pointer(p['destination_array']))
            wanted=p.get('id_value',p.get('value'));field=p.get('id_field')
            index=next(n for n,e in enumerate(source) if (e[field] if field else e)==wanted)
            self.assertEqual(at(after,pointer(p['array_path'])),source[:index]+source[index+1:])
            self.assertEqual(at(after,pointer(p['destination_array'])),destination+[source[index]])

    def test_archived_metadata_and_optimizer_bindings_remain_exact(self):
        timing=expectations();operations=set()
        for path in historical_suite().glob('*.json'):
            test=read_json(path)
            for variant in test['variants']:
                group=row_grouping(test,variant,test['id'],variant['id'])
                self.assertNotIn('unreviewed',group['prompt_comparison_set']['key'])
                self.assertEqual(timing[test['id']][variant['id']]['definition_id'],digest(experiment_spec(test,variant)))
                operations.update(variant['result']['required_ops'])
                value=bindings({'test':test,'variant':variant,'presentation':variant['id']})
                for key,expected in variant['prompt_bindings'].items():self.assertEqual(value[key],expected)
                self.assertNotIn('expected_state',value)
        self.assertEqual(operations,{'replace','add','remove','move','copy'})

    def test_workflow_repeated_requests_are_identical_without_constrained_decoding(self):
        test=definition('db_v3_move_record');variant=test['variants'][0];captured=[]
        response=json.dumps(reference('db_v3_move_record')[0]);self_test=self
        class Backend:
            supports_cache=False
            supports_schema=False
            def generate(self,request,settings,schema,cache,cancel):
                captured.append(request);self_test.assertIsNone(schema)
                return {'text':response,'finish_reason':'stop'}
        self.assertTrue(execute(test,variant,Backend())['score']['exact_match'])
        self.assertTrue(execute(test,variant,Backend())['score']['exact_match'])
        self.assertEqual(captured[0],captured[1])

    def test_optimizer_freezes_archived_reviewed_cases_without_changing_contracts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            shutil.copytree(historical_suite(),root/'test_specs')
            from tools.build_prompt_sharing import build as sharing
            shutil.copytree(self.archive/'reporting',root/'reporting')
            data=sharing(root)
            with patch('optimization.templates.catalog',return_value=data):scope=freeze(root)
            self.assertEqual(len(scope['cases']),12)
            for case in scope['cases'].values():
                self.assertEqual(case['variant']['result']['representation'],'value_patch')
                self.assertIn('value-based paths',bindings(case)['task_requirements'])
