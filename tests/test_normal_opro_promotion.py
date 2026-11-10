"""Frozen normal promotion preserves roles, operation boundaries and literal data."""
import copy
import json
import unittest
from tests.helpers.frozen_prompts import INPUTS, definition, reference
from workbench.domain import digest, read_json
from workbench.workflows import messages, evaluate
from optimization.templates import bindings, render, validate_lpil_candidate


class NormalOproPromotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures=read_json(INPUTS/'fixtures.json')['fixtures']
        cls.config=read_json(INPUTS/'normal_prompt.json')

    def test_all_operations_have_system_role_and_one_shared_operation_block(self):
        method=(INPUTS/'methods/value_patch.txt').read_text().strip()
        for fixture in self.fixtures:
            test=definition(fixture['id']);operation=test['prompt_builder']['operation']
            override=self.config.get('operation_templates',{}).get(operation)
            self.assertEqual(test['prompt_builder']['normal_template']['exact_winner_reuse'],bool(override))
            for variant in test['variants']:
                request=messages(test,variant['steps'][0],{},variant)
                self.assertEqual([m['role'] for m in request],['system','user'])
                if override:self.assertEqual(request[0]['content'],override['candidate']['system'])
                else:self.assertIn('At EVERY collection boundary',request[0]['content'])
                self.assertEqual(request[1]['content'].count(method),1)
                self.assertEqual(request[1]['content'].count('Only these five operations are allowed:'),1)
                self.assertIn('Return only a JSON array of operations.',request[1]['content'])
                self.assertTrue(evaluate(test,variant,{'patch':json.dumps(reference(fixture['id'])[0])})['exact_match'])

    def test_collection_update_guidance_does_not_force_other_operations(self):
        for fixture in self.fixtures:
            test=definition(fixture['id']);parts=test['variants'][0]['prompt_bindings']
            self.assertEqual('For an update described by a collection path' in parts['task_requirements'],fixture['task'] in ('update_record','update_record_nested'))
            self.assertNotIn('For an update described by a collection path',test['instructions'])

    def test_system_only_edit_changes_exact_frozen_request_digest(self):
        test=definition('db_v3_update_record')
        requests={v['id']:messages(test,v['steps'][0],{},v) for v in test['variants']}
        self.assertEqual(digest(requests),test['prompt_builder']['prompt_digest'])
        test['instructions']+='\nAdditional system instruction.'
        changed={v['id']:messages(test,v['steps'][0],{},v) for v in test['variants']}
        self.assertNotEqual(digest(changed),test['prompt_builder']['prompt_digest'])

    def test_marker_shaped_data_stays_literal_in_runtime_template_and_bindings(self):
        test=definition('db_v3_append_record');variant=test['variants'][0]
        literal='literal <{current_state}> (1{new_information}) ${id_value}'
        variant['prompt_bindings']['new_information']=literal
        values=bindings({'test':test,'variant':variant,'presentation':'Normal JSON'},{'earlier':literal})
        self.assertEqual(values['new_information'],literal)
        self.assertEqual(json.loads(values['prior_outputs']),{'earlier':literal})
        self.assertNotIn('expected_state',values)
        request=render(self.config['candidate'],values)
        self.assertIn(literal,request[-1]['content'])

    def test_invalid_shared_lpil_candidates_fail_closed(self):
        candidate=self.config['candidate'];validate_lpil_candidate(candidate)
        for kind in ('missing_label','unknown_label','empty_system'):
            edited=copy.deepcopy(candidate)
            if kind=='missing_label':edited['user']=edited['user'].replace('<{current_state}>','')
            elif kind=='unknown_label':edited['user']+=' <{unknown}>'
            else:edited['system']=''
            with self.subTest(kind=kind),self.assertRaises(ValueError):validate_lpil_candidate(edited)

    def test_promotion_does_not_relax_whole_response_json_grading(self):
        test=definition('db_v3_append_record');variant=test['variants'][0]
        text=json.dumps(reference('db_v3_append_record')[0])
        self.assertTrue(evaluate(test,variant,{'patch':text})['exact_match'])
        self.assertFalse(evaluate(test,variant,{'patch':'```json\n'+text+'\n```'})['exact_match'])
