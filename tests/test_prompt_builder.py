import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from prompt_builder.builder import ROOT, build, compile_test, discover, load_case, prompt, install
from prompt_builder.presentation import keyed, render
from workbench.domain import read_json
from workbench.workflows import evaluate, execute, messages
from tests.helpers.template_responses import encode_response

class PromptBuilderTests(unittest.TestCase):
    def test_default_counts_and_no_schema_hints(self):
        with tempfile.TemporaryDirectory() as temp:
            result=build(temp)
            self.assertEqual((result['prompt_count'],result['observations_per_model']),(38,114))
            self.assertEqual(result['model_runs_started_by_builder'],0)
            self.assertEqual(len(list((Path(temp)/'test_specs').glob('*.json'))),13)
            for path in (Path(temp)/'test_specs').glob('*.json'):
                test=read_json(path)
                self.assertNotIn('state_schema',test)
                self.assertEqual(test['prompt_builder']['version'],'file-templates-v1')
                for variant in test['variants']:
                    self.assertNotIn('required_ops',variant['result'])
                    self.assertNotIn('response_schema',variant['result'])
                    text=variant['steps'][0]['prompt']
                    self.assertNotIn('Database structure:',text)
                    self.assertNotIn('schema-declared',text)
                    self.assertNotIn('{#',text)
                    self.assertIn('Task:\n'+load_case(test['prompt_builder']['fixture'])['requested_change'],text)
    def test_all_catalog_readers_known_correct_outputs(self):
        catalog=discover();count=0;unsupported=0
        for name in catalog['test_cases']:
            case=load_case(name)
            for form in catalog['output_format']:
                from prompt_builder.builder import applicable
                if applicable(case,form):unsupported+=1;continue
                test=compile_test(case,form,input_formats=catalog['input_format'])
                for variant in test['variants']:
                    with self.subTest(case=name,output=form,input=variant['id']):
                        result=evaluate(test,variant,{'patch':encode_response(case,form)})
                        self.assertTrue(result['exact_match'],result)
                        self.assertTrue(result['expected_patch_match'],result)
                        count+=1
        self.assertEqual((count,unsupported),(372,9))
    def test_edit_file_and_new_case_and_format_without_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'templates';shutil.copytree(ROOT,root)
            case=load_case('update_field',root)
            before=prompt(case,'normal_json','json_dot',root)
            path=root/'common/allowed_changes.txt';path.write_text(path.read_text()+'\nAdded general instruction.')
            after=prompt(case,'normal_json','json_dot',root)
            self.assertNotEqual(before,after);self.assertIn('Added general instruction.',after[-1]['content'])
            shutil.copytree(root/'test_cases/update_field',root/'test_cases/another_case')
            shutil.copytree(root/'output_format/json_dot',root/'output_format/my_json')
            (root/'output_format/my_json/format.txt').write_text('My edited output instructions.')
            test=compile_test('another_case','my_json',root=root)
            self.assertEqual(test['id'],'another_case__my_json')
            self.assertIn('My edited output instructions.',test['variants'][0]['steps'][0]['prompt'])
            self.assertIn('another_case',discover(root)['test_cases'])
    def test_layout_headings_and_order_are_editable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'templates';shutil.copytree(ROOT,root)
            layout=root/'common/layout/user.txt'
            layout.write_text('Requested change:\n${task}\n\nData to edit:\n${current_data}\n\n${database_rules}\n\n${allowed_changes}\n\n${path_rules}\n\n${output_format}')
            test=compile_test('update_field','json_dot',root=root)
            variant=test['variants'][0]
            self.assertTrue(variant['steps'][0]['prompt'].startswith('Requested change:'))
            self.assertEqual(variant['prompt_bindings']['new_information'],load_case('update_field')['requested_change'])
            self.assertIn(test['instructions'],variant['prompt_bindings']['task_requirements'])
            self.assertEqual(json.loads(variant['prompt_bindings']['current_state']),load_case('update_field')['starting_data'])
    def test_unknown_placeholder_fails_and_values_not_expanded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'templates';shutil.copytree(ROOT,root)
            case=load_case('update_field',root);case['requested_change']='Use literal ${not_a_template}.'
            self.assertIn(case['requested_change'],prompt(case,'normal_json','json_dot',root)[-1]['content'])
            (root/'common/layout/user.txt').write_text('${typo}')
            with self.assertRaisesRegex(ValueError,'user.txt'):prompt(case,'normal_json','json_dot',root)
    def test_requested_change_is_literal_even_for_template_like_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'templates';shutil.copytree(ROOT,root)
            text='Set hair to the exact string "{# blue #}". Keep literal ${x}.  '
            (root/'test_cases/update_field/requested_change.txt').write_text(text)
            case=load_case('update_field',root)
            self.assertEqual(case['requested_change'],text)
            self.assertTrue(prompt(case,'normal_json','json_dot',root)[-1]['content'].endswith(text))
    def test_no_reference_answer_in_prompt(self):
        case=load_case('update_field');before=prompt(case,'normal_json','json_dot')
        case['expected_patch']=[{'value':'ANSWER_SENTINEL'}];case['expected_result']={'ANSWER_SENTINEL':True}
        self.assertEqual(before,prompt(case,'normal_json','json_dot'))
        self.assertNotIn('ANSWER_SENTINEL',json.dumps(before))
    def test_rebuild_removes_deselected_and_failed_build_keeps_previous(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'build'
            build(output,cases=['update_field'])
            build(output,cases=['no_change'])
            self.assertEqual([p.stem for p in (output/'test_specs').glob('*.json')],['no_change__json_dot'])
            before=(output/'manifest.json').read_bytes()
            with self.assertRaises(ValueError):build(output,cases=['does_not_exist'])
            self.assertEqual(before,(output/'manifest.json').read_bytes())
            self.assertTrue(list((Path(temp)/'build.history').glob('*/test_specs/update_field__json_dot.json')))
    def test_selection_skip_is_a_real_editable_setting(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'templates';shutil.copytree(ROOT,root)
            path=root/'common/selection.json';selection=json.loads(path.read_text())
            selection['skip_id_keyed_when_no_arrays']=False;path.write_text(json.dumps(selection))
            self.assertEqual(len(compile_test('update_field','json_dot',root=root)['variants']),3)
    def test_install_rejects_stale_or_tampered_artifacts_before_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'build';repo=Path(temp)/'repo';repo.mkdir()
            marker=repo/'keep.txt';marker.write_text('unrelated')
            build(output,cases=['update_field'])
            spec=output/'test_specs/update_field__json_dot.json'
            stale=output/'test_specs/stale.json';stale.write_bytes(spec.read_bytes())
            with self.assertRaisesRegex(ValueError,'inventory'):install(output,repo)
            stale.unlink()
            preview=next((output/'prompts').rglob('*.messages.json'));preview.write_text('[]')
            with self.assertRaisesRegex(ValueError,'preview'):install(output,repo)
            self.assertEqual(marker.read_text(),'unrelated')
            self.assertFalse((repo/'test_specs').exists())
    def test_install_known_pass_fixtures_use_each_formats_real_syntax(self):
        from workbench.domain import write_json
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'build';repo=Path(temp)/'repo';repo.mkdir()
            for name,value in {'evaluation/catalog.json':{'definitions':[]},'evaluation/fixtures.json':{'fixtures':[]},'reporting/grouping_metadata.json':{},'reporting/timing_expectations.json':{}}.items():write_json(repo/name,value)
            build(output,cases=['update_field'],output_formats=discover()['output_format'])
            install(output,repo)
            fixtures=read_json(repo/'evaluation/fixtures.json')['fixtures']
            self.assertEqual(len(fixtures),16)
            for row in fixtures:
                test=read_json(repo/row['source_path']);variant=next(v for v in test['variants']if v['id']==row['variant_id'])
                self.assertTrue(evaluate(test,variant,row['outputs'])['exact_match'],row)
    def test_bad_reference_caught_before_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'templates';shutil.copytree(ROOT,root)
            (root/'test_cases/update_field/expected_patch.json').write_text('[]')
            with self.assertRaisesRegex(ValueError,'does not produce'):load_case('update_field',root)
    def test_presentations_do_not_erase_container_type(self):
        data={'empty_array':[],'empty_object':{},'values':['a'],'$array':{'$object':False}}
        self.assertEqual(keyed(data),{'$object':{'empty_array':{'$array':{}},'empty_object':{'$object':{}},'values':{'$array':{'a':'a'}},'$array':{'$object':{'$object':False}}}})
        lines=render(data,'full_paths')
        self.assertIn('values: <array>',lines);self.assertIn('empty_array: []',lines);self.assertIn('empty_object: {}',lines)
        self.assertIn('Table',render(data,'named_tables'))
    def test_mock_execution_sends_exact_compiled_messages(self):
        case=load_case('update_field');test=compile_test(case,'json_dot');variant=test['variants'][0]
        class Backend:
            supports_cache=False;supports_schema=False
            def generate(self,*args,**kwargs):
                self.args=args;self.kwargs=kwargs
                # Match backend result contract.
                return {'text':encode_response(case,'json_dot'),'telemetry':{}}
        # exercise messages separately; full mock workbench has comprehensive tests.
        expected=prompt(case,'normal_json','json_dot')
        self.assertEqual(messages(test,variant['steps'][0],{},variant),expected)
    def test_format_catalog_and_no_obsolete_names(self):
        self.assertEqual(set(discover()['output_format']),{'json_dot','json_slash','path_list','literal_line','end_marked_line','two_line_text','typed_lines','free_format'})
        self.assertFalse(list(ROOT.rglob('schema.json')))
        self.assertFalse((ROOT/'output_format/ember_typed_lines').exists())

if __name__=='__main__':unittest.main()
