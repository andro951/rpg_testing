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

    def test_core_research_specs_use_indexed_json_patch_not_semantic_patch(self):
        for name in ['inventory_net_stock_001.json','household_coat_remove_002.json','household_coat_add_003.json']:
            test=read_json(ROOT/'test_specs'/name);validate_test(test)
            self.assertEqual(test['state_presentation'],'indexed_arrays')
            self.assertTrue(all(v['state_presentation']=='indexed_arrays' for v in test['variants']))
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
            self.assertEqual(len(test['source']['initial_state']['tickets']),100)
            self.assertTrue(equal(apply(test['source']['initial_state'],patch,'json_patch'),test['expected_state']),name)
            self.assertEqual([v['state_presentation'] for v in test['variants']],['raw_json','indexed_arrays'])
            self.assertTrue(all(v['result']['required_ops']==ops for v in test['variants']))

if __name__=='__main__':unittest.main()
