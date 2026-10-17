"""Move OPRO promotion retains operation-specific source construction."""
import copy
import json
import unittest
from test_builder.builder import ROOT, compile_test, oracle, prompt_parts
from test_builder.normal_prompt import configuration, selected
from workbench.domain import read_json
from workbench.workflows import evaluate, messages


class MoveOproPromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures=read_json(ROOT/'fixtures.json')['fixtures']

    def test_element_construction_applies_only_to_the_corresponding_operations(self):
        for f in self.fixtures:
            t=compile_test(f)
            kind=t['prompt_builder']['operation']
            for v in t['variants']:
                guide=v['prompt_bindings']['task_requirements']
                with self.subTest(fixture=f['id'],presentation=v['id']):
                    self.assertEqual('apply this source-path construction silently:' in guide,kind in ('move','copy'))
                    self.assertEqual('apply this element-path construction silently:' in guide,kind=='remove')
                    if kind in ('move','copy'):
                        self.assertIn('JSON-encode the completed path for the "from" field',guide)
                    if kind=='remove':
                        self.assertIn('JSON-encode the completed path for the "path" field',guide)
                    self.assertEqual('For an update described by a collection path' in guide,kind=='update' and 'array_path' in f['parameters'])

    def test_two_serialization_steps_are_shared_by_all_actual_requests(self):
        systems=set()
        for f in self.fixtures:
            t=compile_test(f)
            for v in t['variants']:
                request=messages(t,v['steps'][0],{},v)
                if t['prompt_builder']['operation'] in configuration().get('operation_templates',{}):
                    candidate,_=selected(configuration(),t['prompt_builder']['operation'])
                    self.assertEqual(request[0]['content'],candidate['system'])
                    continue
                systems.add(request[0]['content'])
                self.assertIn('These are two separate serialization steps.',request[0]['content'])
                self.assertIn('Check both "from" and "path"',request[0]['content'])
                self.assertIn('at the very end of a source path',request[0]['content'])
        self.assertEqual(len(systems),1)

    def test_unquoted_string_selectors_still_fail_without_relaxed_grading(self):
        for f in self.fixtures:
            t=compile_test(f)
            kind=t['prompt_builder']['operation']
            if kind not in ('remove','move','copy'):
                continue
            valid=oracle(f)[0]
            malformed=copy.deepcopy(valid)
            field='path' if kind=='remove' else 'from'
            self.assertIn('"',malformed[0][field])
            malformed[0][field]=malformed[0][field].replace('"','')
            for v in t['variants']:
                with self.subTest(fixture=f['id'],presentation=v['id']):
                    self.assertTrue(evaluate(t,v,{'patch':json.dumps(valid)})['exact_match'])
                    self.assertFalse(evaluate(t,v,{'patch':json.dumps(malformed)})['exact_match'])

    def test_unrelated_information_no_change_has_no_element_construction(self):
        f=next(f for f in self.fixtures if f['task']=='no_change')
        self.assertEqual(oracle(f)[0],[])
        p=prompt_parts(f,'normal_json')
        self.assertEqual(p['new_information'],'The documentation uses blue headings and a serif font.')
        self.assertNotIn('Task-specific element path construction:',p['task_requirements'])
        for value in (configuration()['collection_transfer_guidance'],configuration()['collection_remove_guidance']):
            self.assertNotIn('item-17',value)
            self.assertNotIn('town-a',value)
