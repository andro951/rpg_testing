import unittest
from pathlib import Path
from workbench.domain import read_json, validate_test
from workbench.scoring import changes

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

if __name__=='__main__':unittest.main()
