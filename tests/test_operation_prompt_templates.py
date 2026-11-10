"""Frozen operation-wide winners preserve shared contracts and exact provenance."""
import copy
import unittest
from optimization.templates import render, validate_lpil_candidate
from tests.helpers.frozen_prompts import INPUTS, definition
from workbench.domain import digest, read_json
from workbench.workflows import messages


class OperationTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures=read_json(INPUTS/'fixtures.json')['fixtures']
        cls.config=read_json(INPUTS/'normal_prompt.json')

    def test_frozen_operations_match_declared_candidate_and_provenance(self):
        self.assertLessEqual(set(self.config['operation_templates']),{'update','append','remove','move','copy','no_change'})
        for fixture in self.fixtures:
            test=definition(fixture['id']);operation=test['prompt_builder']['operation']
            selected=self.config['operation_templates'].get(operation,self.config)
            self.assertEqual(test['instructions'],selected['candidate']['system'])
            self.assertEqual(test['prompt_builder']['normal_template'],selected['provenance'])
            self.assertEqual(selected['provenance']['exact_winner_reuse'],operation in self.config['operation_templates'])
            for variant in test['variants']:
                request=render(selected['candidate'],{**variant['prompt_bindings'],'prior_outputs':'{}'})
                self.assertEqual(request,messages(test,variant['steps'][0],{},variant))

    def test_edited_candidate_changes_request_identity_without_mutating_frozen_controls(self):
        edited=copy.deepcopy(self.config['operation_templates']['copy']['candidate'])
        edited['system']+='\nAdditional source quoting reminder.'
        test=definition('db_v3_copy_record');before=copy.deepcopy(test)
        requests={v['id']:render(edited,{**v['prompt_bindings'],'prior_outputs':'{}'}) for v in test['variants']}
        self.assertNotEqual(digest(requests),test['prompt_builder']['prompt_digest'])
        self.assertEqual(test,before)
        for fixture in self.fixtures:
            control=definition(fixture['id'])
            original={v['id']:messages(control,v['steps'][0],{},v) for v in control['variants']}
            self.assertEqual(digest(original),control['prompt_builder']['prompt_digest'])

    def test_shared_runtime_validator_rejects_invalid_override_candidates(self):
        base=self.config['operation_templates']['copy']['candidate'];validate_lpil_candidate(base)
        for kind in ('missing_label','duplicate_label','empty_system','unknown_label','missing_candidate'):
            candidate=copy.deepcopy(base)
            if kind=='missing_label':candidate['user']=candidate['user'].replace('<{current_state}>','')
            elif kind=='duplicate_label':candidate['user']+=' <{current_state}>'
            elif kind=='empty_system':candidate['system']=''
            elif kind=='unknown_label':candidate['user']+=' <{unexpected}>'
            else:candidate=None
            with self.subTest(kind=kind),self.assertRaises(ValueError):validate_lpil_candidate(candidate)

    def test_marker_shaped_collection_data_stays_opaque_in_override_renderer(self):
        test=definition('db_v3_copy_value');variant=test['variants'][0]
        literal='literal <{current_state}> (1{new_information}) ${id_value}'
        values={**variant['prompt_bindings'],'current_state':literal,'prior_outputs':'{}'}
        request=render(self.config['operation_templates']['copy']['candidate'],values)
        self.assertIn(literal,request[1]['content'])
        self.assertEqual(request[0]['content'],self.config['operation_templates']['copy']['candidate']['system'])

    def test_frozen_presentations_retain_exact_shared_five_operation_method(self):
        method=(INPUTS/'methods/value_patch.txt').read_text().strip();checked=0
        for fixture in self.fixtures:
            test=definition(fixture['id'])
            for variant in test['variants']:
                request=messages(test,variant['steps'][0],{},variant)
                self.assertEqual(request[1]['content'].count(method),1)
                self.assertEqual(request[1]['content'].count('Only these five operations are allowed:'),1)
                self.assertNotIn('Operation method:',request[0]['content']+'\n'+request[1]['content'])
                self.assertIn(variant['prompt_bindings']['new_information'],request[1]['content'])
                checked+=1
        self.assertEqual(checked,62)
