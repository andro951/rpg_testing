import unittest
from pathlib import Path
from workbench.domain import read_json, validate_test
from workbench.scoring import changes, apply, equal

ROOT=Path(__file__).resolve().parents[1]

class ResearchSpecTests(unittest.TestCase):
    def test_inventory_net_stock_001_is_one_real_state_change(self):
        test=read_json(ROOT/'test_specs/inventory_net_stock_001.json')
        validate_test(test)
        delta=changes(test['source']['initial_state'],test['expected_state'])
        self.assertEqual(delta,{'/inventory/on_hand_units':{'value':49}})
        self.assertEqual(test['source']['initial_state']['product'],test['expected_state']['product'])
        self.assertEqual(test['source']['initial_state']['inventory']['reserved_units'],7)
        self.assertEqual(test['source']['initial_state']['inventory']['reorder_point_units'],12)
        self.assertEqual(test['provenance']['product_metadata_source'],'Anker manufacturer product and support pages')

    def test_household_coat_remove_002_is_one_list_removal(self):
        test=read_json(ROOT/'test_specs/household_coat_remove_002.json')
        validate_test(test)
        before=test['source']['initial_state'];expected=test['expected_state']
        path='/household/members/evan_harper/clothing'
        self.assertEqual(set(changes(before,expected)),{path})
        self.assertIn('brown leather coat',before['household']['members']['evan_harper']['clothing'])
        self.assertNotIn('brown leather coat',expected['household']['members']['evan_harper']['clothing'])
        self.assertTrue(equal(apply(before,[{'op':'remove','path':path+'/4'}],'json_patch'),expected))
        self.assertTrue(all(v['result']['representation']=='json_patch' for v in test['variants']))

    def test_household_coat_add_003_is_one_list_addition(self):
        test=read_json(ROOT/'test_specs/household_coat_add_003.json')
        validate_test(test)
        before=test['source']['initial_state'];expected=test['expected_state']
        path='/household/members/evan_harper/clothing'
        self.assertEqual(set(changes(before,expected)),{path})
        self.assertNotIn('brown leather coat',before['household']['members']['evan_harper']['clothing'])
        self.assertEqual(expected['household']['members']['evan_harper']['clothing'][-1],'brown leather coat')
        self.assertTrue(equal(apply(before,[{'op':'add','path':path+'/-','value':'brown leather coat'}],'json_patch'),expected))
        self.assertTrue(all(v['result']['representation']=='json_patch' for v in test['variants']))

    def test_coat_tests_are_exact_mirrors(self):
        remove=read_json(ROOT/'test_specs/household_coat_remove_002.json')
        add=read_json(ROOT/'test_specs/household_coat_add_003.json')
        self.assertTrue(equal(remove['expected_state'],add['source']['initial_state']))
        self.assertTrue(equal(add['expected_state'],remove['source']['initial_state']))

    def test_core_research_specs_preserve_original_indexed_workflows(self):
        for name in ['inventory_net_stock_001.json','household_coat_remove_002.json','household_coat_add_003.json']:
            test=read_json(ROOT/'test_specs'/name);validate_test(test)
            self.assertEqual(test['state_presentation'],'indexed_arrays')
            self.assertEqual(len(test['variants']),4)
            self.assertTrue(all(v['state_presentation']=='indexed_arrays' for v in test['variants'][:2]))
            self.assertTrue(all(v['state_presentation']=='raw_json' for v in test['variants'][2:]))
            self.assertTrue(all(v['result']['representation']=='json_patch' for v in test['variants']))

    def test_100_item_array_patch_pair_specs(self):
        cases={
            'array_patch_replace_004.json':([{'op':'replace','path':'/tickets/73/status','value':'resolved'}],['replace']),
            'array_patch_remove_005.json':([{'op':'remove','path':'/tickets/87'}],['remove']),
            'array_patch_add_006.json':([{'op':'add','path':'/tickets/64','value':{'ticket_id':'SR-99991','status':'open','priority':'urgent','subject':'VPN access failed after credential rotation','customer_contact':'new.user@example.test'}}],['add']),
            'array_patch_move_007.json':([{'op':'move','from':'/tickets/91','path':'/tickets/7'}],['move']),
            'array_patch_copy_008.json':([{'op':'copy','from':'/tickets/62','path':'/review_samples/-'}],['copy']),
            'array_patch_test_009.json':([{'op':'test','path':'/tickets/84/status','value':'waiting_customer'},{'op':'replace','path':'/tickets/84/status','value':'active'}],['test','replace']),
        }
        for name,(patch,ops) in cases.items():
            test=read_json(ROOT/'test_specs'/name);validate_test(test)
            self.assertEqual(test['timeout_seconds'],120)
            self.assertEqual(len(test['source']['initial_state']['tickets']),100)
            self.assertTrue(equal(apply(test['source']['initial_state'],patch,'json_patch'),test['expected_state']),name)
            self.assertEqual([v['state_presentation'] for v in test['variants']],['raw_json','indexed_arrays'])
            self.assertTrue(all(v['result']['required_ops']==ops for v in test['variants']))

    def test_100_item_array_locating_only_specs(self):
        cases={
            'array_index_replace_010.json':('array_patch_replace_004.json','73'),
            'array_index_remove_011.json':('array_patch_remove_005.json','87'),
            'array_index_add_012.json':('array_patch_add_006.json','64'),
            'array_index_move_013.json':('array_patch_move_007.json','91, 7'),
            'array_index_copy_014.json':('array_patch_copy_008.json','62'),
            'array_index_test_015.json':('array_patch_test_009.json','84'),
        }
        for name,(companion,expected) in cases.items():
            test=read_json(ROOT/'test_specs'/name);validate_test(test)
            original=read_json(ROOT/'test_specs'/companion)
            self.assertEqual(test['provenance']['companion_test'],original['id'])
            self.assertEqual(test['source'],{'initial_state':{},'new_information':''})
            self.assertEqual(test['timeout_seconds'],120)
            self.assertEqual(test['repetitions'],original.get('repetitions',1))
            self.assertEqual([v['id'] for v in test['variants']],['raw_array_index','indexed_object_index','full_paths_index'])
            self.assertEqual([v['state_presentation'] for v in test['variants']],['raw_json','indexed_arrays','raw_json'])
            for variant in test['variants']:
                self.assertEqual(variant['prompt_style'],'direct_text_v1')
                self.assertEqual(variant['result'],{'step':'index','representation':'answers'})
                self.assertEqual(variant['expected_answers'],{'index':expected})
                self.assertEqual(variant['steps'][0]['output'],{'type':'text'})
                model_facing=(test['instructions']+'\n'+variant['steps'][0]['prompt']).lower()
                self.assertNotIn('json patch',model_facing)
                self.assertNotIn('json pointer',model_facing)
            self.assertIn('"tickets": [',test['variants'][0]['steps'][0]['prompt'])
            self.assertIn('"tickets": {',test['variants'][1]['steps'][0]['prompt'])
            self.assertIn('review_samples: []',test['variants'][2]['steps'][0]['prompt'])

    def test_minimal_replace_index_prompt_has_no_test_framing(self):
        test=read_json(ROOT/'test_specs/array_index_replace_minimal_016.json');validate_test(test)
        self.assertEqual(test.get('instructions'),'')
        self.assertEqual(test['source'],{'initial_state':{},'new_information':''})
        self.assertEqual([v['expected_answers'] for v in test['variants']],[{'index':'73'}]*3)
        for variant in test['variants']:
            prompt=variant['steps'][0]['prompt']
            self.assertTrue(prompt.endswith('What is the zero-based index of this ticket: SR-60432?'))
            self.assertNotIn('Current State:',prompt)
            self.assertNotIn('New Information:',prompt)
            self.assertNotIn('Task:',prompt)
            self.assertNotIn('The tickets field is shown',prompt)
            self.assertNotIn('Arrays are shown as objects',prompt)
        self.assertIn('"tickets": [',test['variants'][0]['steps'][0]['prompt'])
        self.assertIn('"tickets": {',test['variants'][1]['steps'][0]['prompt'])

    def test_explicit_replace_plain_question_has_no_indexing_guidance(self):
        test=read_json(ROOT/'test_specs/array_index_replace_explicit_minimal_017.json');validate_test(test)
        self.assertEqual(test.get('instructions'),'')
        self.assertEqual(len(test['variants']),3)
        variant=test['variants'][0]
        prompt=variant['steps'][0]['prompt']
        self.assertTrue(prompt.endswith('What is the index of this ticket: SR-60432?'))
        self.assertNotIn('zero-based',prompt.lower())
        self.assertNotIn('Current State:',prompt)
        self.assertNotIn('New Information:',prompt)
        self.assertNotIn('Task:',prompt)
        self.assertIn('"73": {',prompt)
        self.assertIn('"ticket_id": "SR-60432"',prompt)
        self.assertEqual(variant['expected_answers'],{'index':'73'})

    def test_flattened_replace_paths_prompt_format(self):
        test=read_json(ROOT/'test_specs/array_index_replace_explicit_minimal_017.json');validate_test(test)
        self.assertEqual(test.get('instructions'),'')
        self.assertEqual(len(test['variants']),3)
        variant=next(v for v in test['variants'] if v['id']=='full_paths_index_plain_question')
        prompt=variant['steps'][0]['prompt']
        self.assertFalse('"' in prompt)
        self.assertIn('review_samples: []\n\nWhat is the index of this ticket: SR-60432?',prompt)
        self.assertTrue(prompt.startswith('queue_name: North Region Service Desk\n\nqueue_date: 2026-09-21\n\n'))
        self.assertIn('tickets.0.ticket_id: SR-22345\n',prompt)
        self.assertIn('tickets.73.ticket_id: SR-60432\n',prompt)
        self.assertIn('tickets.73.customer_contact: user73@example.test\n\ntickets.74.ticket_id:',prompt)
        self.assertTrue(prompt.endswith('What is the index of this ticket: SR-60432?'))
        self.assertEqual(variant['expected_answers'],{'index':'73'})

    def test_prompt_calibration_suite_is_balanced(self):
        names=['prompt_calibration_001_time.json','prompt_calibration_002_boolean.json',
               'prompt_calibration_003_nested.json','prompt_calibration_004_array.json']
        expected_ids=['v1_original_clinical','v1_raw_json_control','v2_conversational','v3_only_changed',
                      'v4_smallest_patch','v5_change_rule','v6_one_example']
        expected_timeouts={
            'prompt_calibration_001_time.json':120,
            'prompt_calibration_002_boolean.json':120,
            'prompt_calibration_003_nested.json':120,
            'prompt_calibration_004_array.json':120,
        }
        for name in names:
            test=read_json(ROOT/'test_specs'/name);validate_test(test)
            self.assertEqual(test['timeout_seconds'],expected_timeouts[name])
            self.assertEqual(test['repetitions'],3)
            self.assertEqual([v['id'] for v in test['variants'][:len(expected_ids)]],expected_ids)
            self.assertEqual(len(test['variants']),14 if name==names[0] else 12)
            self.assertEqual(len(changes(test['source']['initial_state'],test['expected_state'])),1)
            self.assertTrue(all(v['result']['representation']=='json_patch' for v in test['variants']))
        self.assertEqual(read_json(ROOT/'test_specs'/names[0])['variants'][0]['new_information_override'],
                         'Exactly five minutes pass. Nobody moves or changes clothing. Nothing else in the tracked state changes.')

    def test_all_local_benchmark_and_example_timeouts_are_two_minutes(self):
        for folder in (ROOT/'test_specs',ROOT/'examples/test_specs'):
            for path in folder.glob('*.json'):
                self.assertEqual(read_json(path)['timeout_seconds'],120,str(path))

if __name__=='__main__':unittest.main()
