import unittest
from pathlib import Path

from workbench.domain import load_tests as load_workflow_specs, read_json, validate_test
from workbench.inventory import automatic_context
from workbench.preflight import _context_planning_tests

ROOT=Path(__file__).resolve().parents[1]


class ThreeFormatMatrixTests(unittest.TestCase):
    def test_new_companions_do_not_change_context_recipe(self):
        tests=load_workflow_specs(ROOT/'test_specs')
        planned=_context_planning_tests(tests)
        self.assertEqual(
            automatic_context(planned,{'planning.context_length':2**63-1})['allocated_tokens'],
            65536,
        )

    def test_array_patch_tests_have_raw_indexed_and_one_full_path_companion(self):
        for n in range(4,10):
            stem={4:'replace',5:'remove',6:'add',7:'move',8:'copy',9:'test'}[n]
            base=read_json(ROOT/'test_specs'/f'array_patch_{stem}_{n:03d}.json')
            companion=read_json(ROOT/'test_specs'/f'array_patch_{stem}_{n:03d}_full_paths.json')
            validate_test(base);validate_test(companion)
            self.assertEqual({v['state_presentation'] for v in base['variants']},{'raw_json','indexed_arrays'})
            self.assertEqual(len(companion['variants']),1)
            self.assertEqual(companion['provenance']['presentation'],'full_paths')
            self.assertEqual(companion['provenance']['companion_test'],base['id'])
            self.assertEqual(companion['source'],base['source'])
            self.assertEqual(companion['expected_state'],base['expected_state'])
            self.assertEqual(companion['timeout_seconds'],base['timeout_seconds'])

    def test_array_lookup_tests_have_three_presentations_without_replacing_old_variants(self):
        for name in [
            'array_index_replace_010.json','array_index_remove_011.json','array_index_add_012.json',
            'array_index_move_013.json','array_index_copy_014.json','array_index_test_015.json',
            'array_index_replace_minimal_016.json','array_index_replace_explicit_minimal_017.json',
        ]:
            test=read_json(ROOT/'test_specs'/name);validate_test(test)
            self.assertEqual(len(test['variants']),3,name)
            self.assertEqual(len({str(v['expected_answers']) for v in test['variants']}),1)

    def test_core_workflows_have_two_json_presentations_plus_full_path_companion(self):
        cases={
            'inventory_net_stock_001.json':['direct_json_patch','analyze_json_patch'],
            'household_coat_remove_002.json':['direct_json_patch','analyze_json_patch'],
            'household_coat_add_003.json':['direct_json_patch','analyze_json_patch'],
            'clothing_append.json':['direct_json_patch','analyze_json_patch','direct_semantic','analyze_semantic'],
            'time_only.json':['direct_json_patch','analyze_json_patch','direct_semantic','analyze_semantic'],
        }
        for name,bases in cases.items():
            base=read_json(ROOT/'test_specs'/name);validate_test(base)
            companion=read_json(ROOT/'test_specs'/(Path(name).stem+'_full_paths.json'));validate_test(companion)
            ids={v['id'] for v in base['variants']}
            for logical in bases:
                self.assertIn(logical,ids)
                other=[x for x in ids if x.startswith(logical+'__')]
                self.assertEqual(len(other),1,(name,logical,other))
                self.assertIn(logical+'__full_paths',{v['id'] for v in companion['variants']})
            self.assertEqual(companion['provenance']['presentation'],'full_paths')
            self.assertEqual(companion['source'],base['source'])
            self.assertEqual(companion['expected_state'],base['expected_state'])

    def test_prompt_calibration_preserves_unique_prompts_in_three_formats(self):
        for name in [
            'prompt_calibration_001_time.json','prompt_calibration_002_boolean.json',
            'prompt_calibration_003_nested.json','prompt_calibration_004_array.json',
        ]:
            base=read_json(ROOT/'test_specs'/name);validate_test(base)
            original_ids=['v1_original_clinical','v1_raw_json_control','v2_conversational',
                          'v3_only_changed','v4_smallest_patch','v5_change_rule','v6_one_example']
            ids={v['id'] for v in base['variants']}
            is_time=name=='prompt_calibration_001_time.json'
            self.assertEqual(len(base['variants']),14 if is_time else 12)
            for logical in original_ids:
                self.assertIn(logical,ids)
                expected=1 if is_time or not logical.startswith('v1_') else 0
                self.assertEqual(len([x for x in ids if x.startswith(logical+'__')]),expected)
            stem=Path(name).stem
            modern=read_json(ROOT/'test_specs'/(stem+'_full_paths.json'));validate_test(modern)
            legacy=read_json(ROOT/'test_specs'/(stem+'_v1_full_paths.json'));validate_test(legacy)
            full_ids={v['id'] for v in modern['variants']+legacy['variants']}
            expected_full={x+'__full_paths' for x in original_ids}
            if not is_time:expected_full.remove('v1_raw_json_control__full_paths')
            self.assertEqual(full_ids,expected_full)
            for companion in (modern,legacy):
                self.assertEqual(companion['source'],base['source'])
                self.assertEqual(companion['expected_state'],base['expected_state'])
                self.assertEqual(companion['repetitions'],base['repetitions'])

    def test_dialogue_only_tests_are_not_triplicated(self):
        for path in (ROOT/'test_specs').glob('dialogue_test*.json'):
            test=read_json(path);validate_test(test)
            self.assertEqual(test['source'],{'initial_state':{},'new_information':''})
            self.assertEqual(len(test['variants']),1)


if __name__=='__main__':
    unittest.main()
