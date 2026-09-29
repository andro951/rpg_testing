import unittest
from pathlib import Path
from workbench.domain import read_json, validate_test, load_tests as load_workflow_specs
from workbench.scoring import changes, apply, equal

ROOT=Path(__file__).resolve().parents[1]
FORMATS=('raw_json','indexed_arrays','full_paths')

def groups(test):
    out={}
    for variant in test['variants']:
        match=next((fmt for fmt in FORMATS if variant['id'].endswith('__'+fmt)),None)
        if not match:raise AssertionError('Variant is not format-suffixed: '+variant['id'])
        base=variant['id'][:-(len(match)+2)]
        out.setdefault(base,{})[match]=variant
    return out

class ResearchSpecTests(unittest.TestCase):
    def assert_balanced(self,test):
        validate_test(test)
        for base,items in groups(test).items():
            self.assertEqual(set(items),set(FORMATS),base)
            self.assertEqual({v['state_presentation'] for v in items.values()},set(FORMATS))

    def test_every_state_benchmark_is_balanced_across_three_presentations(self):
        for test in load_workflow_specs(ROOT/'test_specs'):
            if test['id'].startswith('dialogue_test'):continue
            with self.subTest(test=test['id']):
                self.assert_balanced(test)

    def test_dialogue_tests_are_not_duplicated_by_irrelevant_state_format(self):
        for path in ROOT.joinpath('test_specs').glob('dialogue_test*.json'):
            test=read_json(path);validate_test(test)
            self.assertEqual(test['source'],{'initial_state':{},'new_information':''})
            self.assertEqual(len(test['variants']),1)

    def test_inventory_net_stock_001_is_one_real_state_change(self):
        test=read_json(ROOT/'test_specs/inventory_net_stock_001.json');self.assert_balanced(test)
        delta=changes(test['source']['initial_state'],test['expected_state'])
        self.assertEqual(delta,{'/inventory/on_hand_units':{'value':49}})
        self.assertEqual(test['source']['initial_state']['product'],test['expected_state']['product'])
        self.assertEqual(test['source']['initial_state']['inventory']['reserved_units'],7)
        self.assertEqual(test['source']['initial_state']['inventory']['reorder_point_units'],12)

    def test_household_coat_tests_are_mirrored_and_balanced(self):
        remove=read_json(ROOT/'test_specs/household_coat_remove_002.json');self.assert_balanced(remove)
        add=read_json(ROOT/'test_specs/household_coat_add_003.json');self.assert_balanced(add)
        self.assertTrue(equal(remove['expected_state'],add['source']['initial_state']))
        self.assertTrue(equal(add['expected_state'],remove['source']['initial_state']))
        path='/household/members/evan_harper/clothing'
        self.assertTrue(equal(apply(remove['source']['initial_state'],[{'op':'remove','path':path+'/4'}],'json_patch'),remove['expected_state']))
        self.assertTrue(equal(apply(add['source']['initial_state'],[{'op':'add','path':path+'/-','value':'brown leather coat'}],'json_patch'),add['expected_state']))

    def test_100_item_array_patch_specs_have_three_presentations(self):
        cases={
            'array_patch_replace_004.json':([{'op':'replace','path':'/tickets/73/status','value':'resolved'}],['replace']),
            'array_patch_remove_005.json':([{'op':'remove','path':'/tickets/87'}],['remove']),
            'array_patch_add_006.json':([{'op':'add','path':'/tickets/64','value':{'ticket_id':'SR-99991','status':'open','priority':'urgent','subject':'VPN access failed after credential rotation','customer_contact':'new.user@example.test'}}],['add']),
            'array_patch_move_007.json':([{'op':'move','from':'/tickets/91','path':'/tickets/7'}],['move']),
            'array_patch_copy_008.json':([{'op':'copy','from':'/tickets/62','path':'/review_samples/-'}],['copy']),
            'array_patch_test_009.json':([{'op':'test','path':'/tickets/84/status','value':'waiting_customer'},{'op':'replace','path':'/tickets/84/status','value':'active'}],['test','replace']),
        }
        for name,(patch,ops) in cases.items():
            test=read_json(ROOT/'test_specs'/name);self.assert_balanced(test)
            self.assertEqual(test['timeout_seconds'],120)
            self.assertEqual(len(test['source']['initial_state']['tickets']),100)
            self.assertTrue(equal(apply(test['source']['initial_state'],patch,'json_patch'),test['expected_state']),name)
            trio=groups(test)['patch']
            self.assertTrue(all(v['result']['required_ops']==ops for v in trio.values()))

    def test_100_item_array_locating_specs_are_minimal_three_way_lookup_tests(self):
        cases={
            'array_index_replace_010.json':('73','SR-60432','What is the index of this ticket: SR-60432?'),
            'array_index_remove_011.json':('87','SR-81298','What is the index of this ticket: SR-81298?'),
            'array_index_add_012.json':('64','SR-79161','What is the index of this ticket: SR-79161?'),
            'array_index_move_013.json':('91, 7','SR-22974','What are the indexes of these tickets, in this order: SR-22974, SR-77778?'),
            'array_index_copy_014.json':('62','SR-63323','What is the index of this ticket: SR-63323?'),
            'array_index_test_015.json':('84','SR-57541','What is the index of this ticket: SR-57541?'),
        }
        for name,(expected,target,question) in cases.items():
            test=read_json(ROOT/'test_specs'/name);self.assert_balanced(test)
            self.assertEqual(test.get('instructions'),'')
            self.assertEqual(test['source'],{'initial_state':{},'new_information':''})
            trio=groups(test)['lookup']
            for mode,variant in trio.items():
                self.assertEqual(variant['prompt_style'],'direct_text_v1')
                self.assertEqual(variant['result'],{'step':'index','representation':'answers'})
                self.assertEqual(variant['expected_answers'],{'index':expected})
                prompt=variant['steps'][0]['prompt']
                self.assertTrue(prompt.endswith(question))
                self.assertNotIn('Current State:',prompt)
                self.assertNotIn('New Information:',prompt)
                self.assertNotIn('Task:',prompt)
                self.assertNotIn('json patch',prompt.lower())
            self.assertIn('"tickets": [',trio['raw_json']['steps'][0]['prompt'])
            self.assertIn('"tickets": {',trio['indexed_arrays']['steps'][0]['prompt'])
            self.assertIn('tickets.',trio['full_paths']['steps'][0]['prompt'])
            self.assertIn(target,trio['full_paths']['steps'][0]['prompt'])
            self.assertIn('review_samples: []',trio['full_paths']['steps'][0]['prompt'])

    def test_exploratory_replace_format_fixtures_were_folded_into_main_matrix(self):
        for name in ('array_index_replace_minimal_016.json','array_index_replace_explicit_minimal_017.json','array_index_replace_flat_paths_018.json'):
            self.assertFalse((ROOT/'test_specs'/name).exists())

    def test_prompt_calibration_suite_is_six_prompt_styles_times_three_formats(self):
        names=['prompt_calibration_001_time.json','prompt_calibration_002_boolean.json',
               'prompt_calibration_003_nested.json','prompt_calibration_004_array.json']
        bases={'v1_original_clinical','v2_conversational','v3_only_changed','v4_smallest_patch','v5_change_rule','v6_one_example'}
        for name in names:
            test=read_json(ROOT/'test_specs'/name);self.assert_balanced(test)
            self.assertEqual(test['timeout_seconds'],60)
            self.assertEqual(test['repetitions'],3)
            self.assertEqual(set(groups(test)),bases)
            self.assertEqual(len(test['variants']),18)
            self.assertEqual(len(changes(test['source']['initial_state'],test['expected_state'])),1)
            v1=groups(test)['v1_original_clinical']
            self.assertEqual(len({v.get('new_information_override') for v in v1.values()}),1)

    def test_runaway_generation_timeouts_stay_bounded(self):
        for name in ['household_coat_add_003.json','household_coat_remove_002.json']:
            self.assertEqual(read_json(ROOT/'test_specs'/name)['timeout_seconds'],60)
        self.assertEqual(read_json(ROOT/'test_specs'/'dialogue_test 1_4.json')['timeout_seconds'],600)

if __name__=='__main__':unittest.main()
