"""Operation-wide winners preserve the shared contract and unrelated identities."""
import copy
import unittest
from unittest.mock import patch
from test_builder.builder import ROOT,compile_test,build_messages,prompt_parts
from test_builder import normal_prompt
from workbench.domain import read_json


class OperationTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures=read_json(ROOT/'fixtures.json')['fixtures']
        cls.reviews=read_json(ROOT/'reviews.json')

    def test_only_declared_operations_select_override_candidate_and_provenance(self):
        config=normal_prompt.configuration()
        for fixture in self.fixtures:
            test=compile_test(fixture,self.reviews);operation=test['prompt_builder']['operation']
            candidate,provenance=normal_prompt.selected(config,operation)
            self.assertEqual(test['instructions'],candidate['system'])
            self.assertEqual(test['prompt_builder']['normal_template'],provenance)
            self.assertEqual(provenance['exact_winner_reuse'],operation in config.get('operation_templates',{}))

    def test_unrelated_definitions_and_exact_approvals_do_not_change_when_override_changes(self):
        config=normal_prompt.configuration();edited=copy.deepcopy(config)
        edited['operation_templates']['copy']['candidate']['system']+='\nAdditional source quoting reminder.'
        before={f['id']:compile_test(f,self.reviews) for f in self.fixtures}
        with patch('test_builder.normal_prompt.configuration',return_value=edited):
            after={f['id']:compile_test(f,self.reviews) for f in self.fixtures}
        for fixture in self.fixtures:
            first,second=before[fixture['id']],after[fixture['id']]
            if first['prompt_builder']['operation']=='copy':
                self.assertNotEqual(first['prompt_builder']['prompt_digest'],second['prompt_builder']['prompt_digest'])
                self.assertTrue(first['enabled']);self.assertFalse(second['enabled'])
            else:
                self.assertEqual(first,second)

    def test_invalid_operation_override_configuration_fails_closed(self):
        base=normal_prompt.configuration()
        for kind in ('unknown_operation','missing_candidate','missing_label','duplicate_label','empty_system'):
            config=copy.deepcopy(base);entry=config['operation_templates']['copy']
            if kind=='unknown_operation':config['operation_templates']['unexpected']=config['operation_templates'].pop('copy')
            elif kind=='missing_candidate':entry.pop('candidate')
            elif kind=='missing_label':entry['candidate']['user']=entry['candidate']['user'].replace('<{current_state}>','')
            elif kind=='duplicate_label':entry['candidate']['user']+=' <{current_state}>'
            else:entry['candidate']['system']=''
            with self.subTest(kind=kind),patch('test_builder.normal_prompt.read_json',return_value=config):
                with self.assertRaises(ValueError):normal_prompt.configuration()
        with self.assertRaises(ValueError):normal_prompt.selected(base,'unexpected')

    def test_marker_shaped_collection_data_stays_opaque_in_override(self):
        fixture=copy.deepcopy(next(f for f in self.fixtures if f['id']=='db_v3_copy_value'))
        literal='literal <{current_state}> (1{new_information}) ${id_value}'
        old=fixture['parameters']['value'];fixture['parameters']['value']=literal
        path=fixture['parameters']['array_path'].strip('/');values=fixture['state'][path]
        values[values.index(old)]=literal
        request=build_messages(fixture,'normal_json')
        self.assertIn(literal,request[1]['content'])
        self.assertEqual(request[0]['content'],normal_prompt.configuration()['operation_templates']['copy']['candidate']['system'])

    def test_all_presentations_retain_exact_shared_five_operation_method(self):
        method=(ROOT/'methods/value_patch.txt').read_text().strip();checked=0
        for fixture in self.fixtures:
            test=compile_test(fixture)
            for variant in test['variants']:
                request=build_messages(fixture,variant['id'])
                self.assertEqual(request[1]['content'].count(method),1)
                self.assertEqual(request[1]['content'].count('Only these five operations are allowed:'),1)
                self.assertNotIn('Operation method:',request[0]['content']+'\n'+request[1]['content'])
                self.assertIn(prompt_parts(fixture,variant['id'])['new_information'],request[1]['content'])
                checked+=1
        self.assertEqual(checked,62)
