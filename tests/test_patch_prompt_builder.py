"""Database task authoring, provider-neutral method contracts and prompt review gates."""
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
from test_builder.builder import ROOT, LABELS, METHODS, TASKS, TASK_TEMPLATES, at, build_prompt, compile_test, oracle, presentations, prompt_parts
from workbench.domain import digest, experiment_spec, load_tests as load_catalog, read_json, validate_test
from workbench.workflows import evaluate, execute, messages

REPO = ROOT.parent


class PatchPromptBuilderTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = read_json(ROOT/'fixtures.json')['fixtures']
        self.by_id = {f['id']:f for f in self.fixtures}

    def test_archive_keeps_original_bytes_and_deferred_tasks_remain_separate(self):
        archive = REPO/'archives/test-suite-2026-10-14'
        manifest = read_json(archive/'manifest.json')
        self.assertEqual(len(manifest['definitions']),61)
        for entry in manifest['definitions']:
            self.assertEqual(hashlib.sha256((archive/entry['file']).read_bytes()).hexdigest(),entry['sha256'])
            self.assertFalse((REPO/entry['file']).exists())
        self.assertEqual(len(read_json(REPO/'docs/test-suite-v2/deferred-tests.json')['tests']),10)

    def test_only_applicable_tasks_remain_and_review_directory_contains_only_exact_prompts(self):
        self.assertEqual(len(self.fixtures),21)
        self.assertEqual(set(TASKS),{f['task'] for f in self.fixtures})
        self.assertEqual({p.stem for p in (ROOT/'templates').glob('*.txt')},set(TASK_TEMPLATES.values()))
        self.assertFalse(any((REPO/'test_specs').glob('patch_v2*')))
        self.assertFalse(any((REPO/'prompts/patch-suite').glob('patch_v2*')))
        manifest = read_json(REPO/'prompts/patch-suite/manifest.json')['prompts']
        self.assertEqual(len(manifest),62)
        paths = {REPO/p['review_file'] for p in manifest}
        self.assertEqual(set((REPO/'prompt-review').iterdir()),paths)
        for entry in manifest:
            path=REPO/entry['review_file']
            self.assertEqual(path.suffix,'.txt')
            self.assertEqual(path.read_bytes(),(REPO/entry['file']).read_bytes())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),entry['prompt_sha256'])

    def test_every_fixture_has_exact_requests_and_independent_passing_oracles(self):
        method=(ROOT/'methods/value_patch.txt').read_text(encoding='utf-8').strip()
        for fixture in self.fixtures:
            with self.subTest(fixture=fixture['id']):
                before=copy.deepcopy(fixture)
                test=compile_test(fixture,read_json(ROOT/'reviews.json'))
                definition=REPO/'test_specs'/(test['id']+'.json')
                self.assertEqual(test,read_json(definition))
                self.assertNotIn(b'\r\n',definition.read_bytes())
                self.assertEqual([v['id'] for v in test['variants']],list(presentations(fixture)))
                answer=oracle(fixture)
                for variant in test['variants']:
                    prompt=variant['steps'][0]['prompt']
                    request=messages(test,variant['steps'][0],{},variant)
                    self.assertTrue(test['instructions'])
                    self.assertEqual(request,[{'role':'system','content':test['instructions']},{'role':'user','content':prompt}])
                    self.assertEqual(prompt.count(method),1)
                    self.assertEqual(prompt.count('Current data:\n'),1)
                    self.assertEqual(prompt.count('Task:\n'),1)
                    path=REPO/'prompts/patch-suite'/test['id']/(variant['id']+'.txt')
                    from test_builder.normal_prompt import preview
                    self.assertEqual(path.read_text(encoding='utf-8'),preview(request))
                    self.assertEqual(read_json(path.with_suffix('.messages.json')),request)
                    self.assertEqual(variant['steps'][0]['output'],{'type':'text'})
                    values={'patch':json.dumps(answer[0])}
                    self.assertTrue(evaluate(test,variant,values)['exact_match'])
                    self.assertEqual(assess(test,variant,values)['objective_outcome'],'PASS')
                    if fixture['task']!='no_change':
                        self.assertFalse(evaluate(test,variant,{'patch':'[]'})['exact_match'])
                self.assertEqual(fixture,before)

    def test_review_requires_both_people_and_invalidates_on_task_or_method_changes(self):
        fixture=self.by_id['db_v3_update_record']
        initial=compile_test(fixture)
        review={'status':'accepted','prompt_digest':initial['prompt_builder']['prompt_digest']}
        reviews={initial['id']:{'assistant':review}}
        self.assertFalse(compile_test(fixture,reviews)['enabled'])
        reviews[initial['id']]['isaac']=review
        self.assertTrue(compile_test(fixture,reviews)['enabled'])
        changed=copy.deepcopy(fixture);changed['parameters']['new_value']=11
        self.assertFalse(compile_test(changed,reviews)['enabled'])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'method.txt';path.write_text('Different method instructions')
            with patch.dict(METHODS,{'value_patch':{**METHODS['value_patch'],'file':str(path)}}):
                self.assertFalse(compile_test(fixture,reviews)['enabled'])
        self.assertEqual(len(load_catalog(REPO/'test_specs')),len(self.fixtures))
        self.assertEqual(len(freeze(REPO)['cases']),12)

    def test_task_schema_and_data_are_independent_of_method_selection(self):
        fixture=self.by_id['db_v3_update_record']
        original=prompt_parts(fixture,'normal_json')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'method.txt';path.write_text('Synthetic alternative method instructions')
            with patch.dict(METHODS,{'synthetic':{**METHODS['value_patch'],'name':'Synthetic method','file':str(path)}}):
                other=prompt_parts(fixture,'normal_json','synthetic')
                for key in ('current_state','new_information','presentation_notes'):
                    self.assertEqual(other[key],original[key])
                self.assertNotEqual(other['task_requirements'],original['task_requirements'])
                self.assertNotEqual(compile_test(fixture,method='synthetic')['id'],compile_test(fixture)['id'])
        with self.assertRaisesRegex(ValueError,'Unknown'):compile_test(fixture,method='unsupported')

    def test_positional_method_and_presentation_are_not_available_for_new_prompts(self):
        for f in self.fixtures:
            with self.subTest(fixture=f['id']):
                with self.assertRaisesRegex(ValueError,'Unknown operation method'):
                    compile_test(f,method='json_patch')
                with self.assertRaisesRegex(ValueError,'inapplicable presentation'):
                    build_prompt(f,'indexed_arrays')

    def test_nested_collection_task_parameters_use_value_paths_for_the_selected_method(self):
        f=copy.deepcopy(self.by_id['db_v3_update_record'])
        old_state,old_schema=f['state'],f['schema']
        f['state']={'groups':[{'group_id':'group/a','inventory':old_state}]}
        record={'type':'object','properties':{'group_id':{'type':'string'},'inventory':old_schema},
                'required':['group_id','inventory'],'additionalProperties':False}
        f['schema']={'type':'object','properties':{'groups':{'type':'array','items':record,'x-id-field':'group_id'}},
                     'required':['groups'],'additionalProperties':False}
        f['parameters']['array_path']='/groups/0/inventory/items'
        parts=prompt_parts(f,'full_paths')
        self.assertIn(json.dumps('/groups/"group/a"/inventory/items'),parts['new_information'])
        self.assertNotIn('/groups/0',parts['new_information'])
        test=compile_test(f);answer=oracle(f)[0]
        self.assertEqual(answer[0]['path'],'/groups/"group/a"/inventory/items/"item-17"/count')
        self.assertTrue(evaluate(test,test['variants'][0],{'patch':json.dumps(answer)})['exact_match'])

    def test_identifier_field_is_explicit_and_can_change_with_its_schema(self):
        fixture=copy.deepcopy(self.by_id['db_v3_update_record'])
        for item in fixture['state']['items']:item['object_key']=item.pop('item_id')
        node=fixture['schema']['properties']['items'];node['x-id-field']='object_key'
        row=node['items'];row['properties']['object_key']=row['properties'].pop('item_id')
        row['required']=[k if k!='item_id' else 'object_key' for k in row['required']]
        fixture['parameters']['id_field']='object_key'
        prompt=build_prompt(fixture,'normal_json')
        self.assertIn('whose "object_key" value is "item-17"',prompt)
        self.assertEqual(oracle(fixture)[0][0]['path'],'/items/"item-17"/count')

    def test_marker_like_input_is_substituted_once(self):
        fixture=copy.deepcopy(self.by_id['db_v3_append_record'])
        fixture['parameters']['new_record']['name']='${id_value} $unknown @{literal}'
        self.assertIn('${id_value} $unknown @{literal}',build_prompt(fixture,'normal_json'))

    def test_invalid_ids_fields_schemas_and_duplicate_or_incomplete_appends_fail_before_export(self):
        def check(fixture):
            with self.assertRaises((ValueError,KeyError)):build_prompt(fixture,'normal_json')
        base=self.by_id['db_v3_update_record']
        for kind in ('missing','duplicate','wrong_type','extra','field','schema'):
            f=copy.deepcopy(base)
            if kind=='missing':f['parameters']['id_value']='absent'
            elif kind=='duplicate':f['state']['items'][0]['item_id']='item-17'
            elif kind=='wrong_type':f['parameters']['id_value']=17
            elif kind=='extra':f['parameters']['expected_answer']='not allowed'
            elif kind=='field':f['parameters']['property_path']='/undefined'
            else:f['schema']['properties']['items'].pop('x-id-field')
            with self.subTest(kind=kind):check(f)
        for kind in ('duplicate','missing_field','extra_field'):
            f=copy.deepcopy(self.by_id['db_v3_append_record'])
            if kind=='duplicate':f['parameters']['new_record']['item_id']='item-17'
            elif kind=='missing_field':f['parameters']['new_record'].pop('count')
            else:f['parameters']['new_record']['weight']=1
            with self.subTest(kind=kind):check(f)
        f=copy.deepcopy(self.by_id['db_v3_append_value']);f['parameters']['new_value']='town-a';check(f)
        f=copy.deepcopy(self.by_id['db_v3_move_record']);f['state']['storage'][0]['item_id']='item-17';check(f)

    def test_empty_collections_still_declare_complete_record_structure_and_identity(self):
        fixture=self.by_id['db_v3_append_record_empty']
        for mode in presentations(fixture):
            prompt=build_prompt(fixture,mode)
            self.assertIn('unique "item_id" value',prompt)
            self.assertIn('"count": number.',prompt)
        f=copy.deepcopy(fixture);f['schema']['properties']['items'].pop('x-id-field')
        with self.assertRaises(ValueError):build_prompt(f,'normal_json')

    def test_no_change_uses_unrelated_information_in_every_presentation(self):
        f=self.by_id['db_v3_no_change']
        self.assertEqual(f['parameters'],{})
        self.assertEqual(TASK_TEMPLATES['no_change'],'no_change')
        for mode in presentations(f):
            self.assertEqual(prompt_parts(f,mode)['new_information'],
                'The documentation uses blue headings and a serif font.')
        changed=copy.deepcopy(f)
        changed['state']['items'][2]['count']=91
        self.assertEqual(oracle(changed),([],changed['state']))
        changed['parameters']['new_value']=2
        with self.assertRaisesRegex(ValueError,'task parameters'):
            compile_test(changed)

    def test_no_change_accepts_empty_json_with_whitespace_and_rejects_redundant_or_test_operations(self):
        f=self.by_id['db_v3_no_change'];test=compile_test(f);variant=test['variants'][0]
        self.assertEqual(variant['result']['required_ops'],[])
        self.assertEqual(oracle(f)[0],[])
        for text in ('[]','[ \n ]'):
            self.assertTrue(evaluate(test,variant,{'patch':text})['exact_match'])
            self.assertEqual(assess(test,variant,{'patch':text})['objective_outcome'],'PASS')
        for op in ('replace','test'):
            response=json.dumps([{'op':op,'path':'/items/2/count','value':2}])
            self.assertFalse(evaluate(test,variant,{'patch':response})['exact_match'])
            self.assertEqual(assess(test,variant,{'patch':response})['objective_outcome'],'FAIL')

    def test_post_response_contract_blocks_whole_collection_overwrites_and_whole_record_replacement(self):
        for key in ('db_v3_append_record','db_v3_update_record'):
            f=self.by_id[key];test=compile_test(f);variant=test['variants'][0]
            if key.endswith('append_record'):
                patch_value=[{'op':'replace','path':'/items','value':test['expected_state']['items']}]
            else:
                patch_value=[{'op':'replace','path':'/items/1','value':test['expected_state']['items'][1]}]
            from workbench.scoring import apply
            self.assertEqual(apply(f['state'],patch_value,'json_patch'),test['expected_state'])
            values={'patch':json.dumps(patch_value)}
            score=evaluate(test,variant,values)
            self.assertFalse(score['exact_match']);self.assertFalse(score['valid'])
            report=assess(test,variant,values)
            self.assertTrue(any(c['status']=='failed' and c['code']=='patch.application_failed' for c in report['checks']))

    def test_append_targets_collection_and_move_preserves_both_collection_orders(self):
        f=self.by_id['db_v3_append_record'];test=compile_test(f);variant=test['variants'][0]
        response=oracle(f)[0];response[0]['path']='/items/4'
        self.assertFalse(evaluate(test,variant,{'patch':json.dumps(response)})['exact_match'])
        response[0]['path']='/items'
        self.assertTrue(evaluate(test,variant,{'patch':json.dumps(response)})['exact_match'])
        for key in ('db_v3_move_record','db_v3_move_record_empty','db_v3_move_value'):
            f=self.by_id[key];response,after=oracle(f)
            p=f['parameters'];source=at(f['state'],p['array_path']);destination=at(f['state'],p['destination_array'])
            from test_builder.builder import locate
            index=locate(source,p.get('id_field'),p.get('id_value',p.get('value')))
            self.assertEqual(at(after,p['array_path']),source[:index]+source[index+1:])
            self.assertEqual(at(after,p['destination_array']),destination+[source[index]])

    def test_template_parameters_and_pointer_escaping_are_explicit(self):
        f=self.by_id['db_v3_update_record']
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'update_record.txt'
            for text in ('${unknown}','${array_path}','${array_path} ${'):
                path.write_text(text)
                with self.assertRaises(ValueError):build_prompt(f,'normal_json',Path(folder))
        f=copy.deepcopy(self.by_id['db_v3_update_field'])
        f['state']={'a/b':{'~key':1},'empty':[],'object':{}}
        f['schema']={'type':'object','properties':{'a/b':{'type':'object','properties':{'~key':{'type':'number'}},'required':['~key'],'additionalProperties':False},
            'empty':{'type':'array','items':{'type':'string'},'uniqueItems':True},'object':{'type':'object','properties':{},'required':[],'additionalProperties':False}},
            'required':['a/b','empty','object'],'additionalProperties':False}
        f['parameters']={'property_path':'/a~1b/~0key','new_value':2}
        prompt=build_prompt(f,'full_paths')
        self.assertIn('/a~1b/~0key:1',prompt);self.assertIn('/empty:[]',prompt)
        self.assertIn('/object:{}',prompt)
        self.assertEqual(oracle(f)[1]['a/b']['~key'],2)
        for path in ('/a/-1','/a/01','/a/2','/a~2'):
            with self.assertRaises(ValueError):at({'a':[1,2]},path)

    def test_current_metadata_and_optimizer_bindings_preserve_shared_rules_without_duplicate_data(self):
        timing=expectations();operations=set()
        for f in self.fixtures:
            test=compile_test(f,read_json(ROOT/'reviews.json'))
            for v in test['variants']:
                group=row_grouping(test,v,test['id'],v['id'])
                self.assertNotIn('unreviewed',group['prompt_comparison_set']['key'])
                self.assertEqual(timing[test['id']][v['id']]['definition_id'],digest(experiment_spec(test,v)))
                operations.update(v['result']['required_ops'])
                value=bindings({'test':test,'variant':v,'presentation':LABELS[v['id']]})
                expected=prompt_parts(f,v['id'])
                for key in ('current_state','new_information','task_requirements','presentation_notes'):
                    self.assertEqual(value[key],expected[key])
        self.assertEqual(operations,{'replace','add','remove','move','copy'})

    def test_generated_workflow_repeated_requests_are_identical_without_constrained_decoding(self):
        f=self.by_id['db_v3_move_record'];test=compile_test(f);v=test['variants'][0];captured=[]
        class Backend:
            supports_cache=False
            supports_schema=False
            def generate(self,request,settings,schema,cache,cancel):
                captured.append(request)
                self_test.assertIsNone(schema)
                return {'text':json.dumps(oracle(f)[0]),'finish_reason':'stop'}
        self_test=self
        self.assertTrue(execute(test,v,Backend())['score']['exact_match'])
        self.assertTrue(execute(test,v,Backend())['score']['exact_match'])
        self.assertEqual(captured[0],captured[1])

    def test_optimizer_can_freeze_reviewed_value_path_cases_without_mixing_standard_contracts(self):
        from tools.build_prompt_sharing import build as sharing
        from workbench.domain import write_json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            labels=read_json(REPO/'reporting/grouping_metadata.json')
            for f in self.fixtures:
                draft=compile_test(f)
                proof={'status':'accepted','prompt_digest':draft['prompt_builder']['prompt_digest']}
                test=compile_test(f,{draft['id']:{'assistant':proof,'isaac':proof}})
                write_json(root/'test_specs'/(test['id']+'.json'),test)
                for v in test['variants']:
                    labels[test['id']][v['id']]['reviewed_definition']=digest(experiment_spec(test,v))
            shutil.copytree(REPO/'reporting',root/'reporting')
            write_json(root/'reporting/grouping_metadata.json',labels)
            data=sharing(root)
            with patch('optimization.templates.catalog',return_value=data):
                scope=freeze(root)
            self.assertEqual(len(scope['cases']),12)
            for case in scope['cases'].values():
                self.assertEqual(case['variant']['result']['representation'],'value_patch')
                self.assertIn('value-based paths',bindings(case)['task_requirements'])

    def test_build_removes_only_managed_obsolete_exports_and_is_byte_stable(self):
        from test_builder.__main__ import build,write_json
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            shutil.copytree(REPO/'archives/test-suite-2026-10-14',root/'archives/test-suite-2026-10-14')
            write_json(root/'reporting/timing_expectations.json',{})
            write_json(root/'test_specs/obsolete.json',{})
            old=root/'prompts/patch-suite/obsolete/normal.txt';old.parent.mkdir(parents=True);old.write_text('old')
            old.with_suffix('.messages.json').write_text('[]')
            review=root/'prompt-review/00-obsolete.txt';review.parent.mkdir();review.write_text('old')
            write_json(root/'prompts/patch-suite/manifest.json',{'prompts':[{'test_id':'obsolete','file':old.relative_to(root).as_posix(),'review_file':review.relative_to(root).as_posix()}]})
            result=build(root)
            self.assertEqual(result['prompts'],62);self.assertEqual(result['enabled'],len(self.fixtures))
            self.assertFalse(old.exists());self.assertFalse(review.exists());self.assertFalse((root/'test_specs/obsolete.json').exists())
            before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
            build(root)
            self.assertEqual(before,{p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()})
            self.assertEqual(read_json(root/'prompts/patch-suite/manifest.json')['status'],'ready')
            with patch('test_builder.__main__.read_json',side_effect=lambda path: {} if Path(path)==ROOT/'reviews.json' else read_json(path)):
                pending=build(root)
            self.assertEqual(pending['enabled'],0)
            self.assertEqual(read_json(root/'prompts/patch-suite/manifest.json')['status'],'pending_joint_prompt_review')
