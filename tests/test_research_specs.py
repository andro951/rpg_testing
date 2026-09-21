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
        self.assertTrue(equal(apply(before,[{'op':'list_remove','path':path,'value':'brown leather coat'}],'semantic'),expected))

    def test_household_coat_add_003_is_one_list_addition(self):
        test=read_json(ROOT/'test_specs/household_coat_add_003.json')
        validate_test(test)
        before=test['source']['initial_state'];expected=test['expected_state']
        path='/household/members/evan_harper/clothing'
        self.assertEqual(set(changes(before,expected)),{path})
        self.assertNotIn('brown leather coat',before['household']['members']['evan_harper']['clothing'])
        self.assertEqual(expected['household']['members']['evan_harper']['clothing'][-1],'brown leather coat')
        self.assertTrue(equal(apply(before,[{'op':'add','path':path+'/-','value':'brown leather coat'}],'json_patch'),expected))
        self.assertTrue(equal(apply(before,[{'op':'list_add','path':path,'value':'brown leather coat'}],'semantic'),expected))

    def test_coat_tests_are_exact_mirrors(self):
        remove=read_json(ROOT/'test_specs/household_coat_remove_002.json')
        add=read_json(ROOT/'test_specs/household_coat_add_003.json')
        self.assertTrue(equal(remove['expected_state'],add['source']['initial_state']))
        self.assertTrue(equal(add['expected_state'],remove['source']['initial_state']))

if __name__=='__main__':unittest.main()
