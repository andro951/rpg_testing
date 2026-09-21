import json
import unittest
from pathlib import Path
from workbench.domain import read_json,validate_test
from workbench.presentation import indexed_arrays,render_source,presentation_mode
from workbench.workflows import messages,evaluate

ROOT=Path(__file__).resolve().parents[1]

class StatePresentationTests(unittest.TestCase):
    def test_arrays_become_numeric_key_objects_recursively(self):
        value={'a':['x',{'b':[10,20]}],'real_numeric_object':{'0':'keep','1':'object'}}
        shown=indexed_arrays(value)
        self.assertEqual(shown['a'],{'0':'x','1':{'b':{'0':10,'1':20}}})
        self.assertEqual(shown['real_numeric_object'],{'0':'keep','1':'object'})

    def test_raw_and_indexed_variants_show_same_source_with_different_array_shape(self):
        test=read_json(ROOT/'test_specs/array_patch_replace_004.json')
        raw=messages(test,test['variants'][0]['steps'][0],{},test['variants'][0])
        indexed=messages(test,test['variants'][1]['steps'][0],{},test['variants'][1])
        raw_source=json.loads(raw[1]['content'].split('\nSOURCE\n',1)[1])
        indexed_source=json.loads(indexed[1]['content'].split('\nSOURCE\n',1)[1])
        self.assertIsInstance(raw_source['initial_state']['tickets'],list)
        self.assertIsInstance(indexed_source['initial_state']['tickets'],dict)
        self.assertEqual(indexed_source['initial_state']['tickets']['73'],raw_source['initial_state']['tickets'][73])
        self.assertNotIn('expected_state',raw[1]['content']);self.assertNotIn('expected_state',indexed[1]['content'])

    def test_default_presentation_is_indexed_arrays(self):
        test=read_json(ROOT/'test_specs/time_only.json')
        self.assertEqual(presentation_mode(test,{}),'indexed_arrays')

    def test_required_operation_is_part_of_task_success(self):
        test={'source':{'initial_state':{'x':1}},'expected_state':{'x':2}}
        variant={'result':{'step':'patch','representation':'json_patch','required_ops':['replace']}}
        right=evaluate(test,variant,{'patch':'[{"op":"replace","path":"/x","value":2}]'})
        wrong=evaluate(test,variant,{'patch':'[{"op":"add","path":"/x","value":2}]'})
        self.assertTrue(right['exact_match']);self.assertTrue(right['patch_ops_match'])
        self.assertTrue(wrong['state_exact_match']);self.assertFalse(wrong['patch_ops_match']);self.assertFalse(wrong['exact_match'])

    def test_validation_rejects_unknown_presentation_and_patch_operation(self):
        test=read_json(ROOT/'test_specs/array_patch_replace_004.json')
        test['variants'][0]['state_presentation']='mystery'
        with self.assertRaises(ValueError):validate_test(test)
        test=read_json(ROOT/'test_specs/array_patch_replace_004.json')
        test['variants'][0]['result']['required_ops']=['increment']
        with self.assertRaises(ValueError):validate_test(test)

if __name__=='__main__':unittest.main()
