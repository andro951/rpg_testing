"""Synthetic schema-host regressions; approved oracles are test-only inputs."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluation.value_intent import replay_value_intent, encode_path
from tests.test_value_paths import obj, records

ROOT = Path(__file__).resolve().parents[1]


class ValueIntentTests(unittest.TestCase):
    def setUp(self):
        self.state = {'items': [{'key': 'a/b', 'count': 1}, {'key': 'b', 'count': 2}],
                      'storage': [], 'values': [1, '1', False, None]}
        self.schema = obj({'items': records(), 'storage': records(),
                           'values': {'type': 'array', 'items': {'type': ['string','number','boolean','null']}}})

    def run_raw(self, raw, options=None):
        before = copy.deepcopy((self.state, self.schema))
        result = replay_value_intent(raw, self.state, self.schema, options)
        self.assertEqual((self.state, self.schema), before)
        return result

    def test_every_historical_approved_fixture_matches_test_only_oracle(self):
        fixtures = json.loads((ROOT/'evaluation/fixtures.json').read_text())['fixtures']
        seen, count = set(), 0
        for fixture in fixtures:
            if not fixture['source_path'].startswith('archives/pre-template-builder/test_specs/'):
                continue
            definition = json.loads((ROOT/fixture['source_path']).read_text())
            if not definition.get('enabled'):
                continue
            variant = next(v for v in definition['variants'] if v['id'] == fixture['variant_id'])
            if variant['result'].get('representation') != 'value_patch':
                continue
            with self.subTest(test=definition['id'], variant=variant['id']):
                result = replay_value_intent(fixture['outputs'][variant['result']['step']],
                    definition['source']['initial_state'], definition['state_schema'])
                self.assertTrue(result['accepted'], result)
                self.assertEqual(result['finalState'], definition['expected_state'])
                seen.add(definition['id']); count += 1
        self.assertEqual(len(seen), 21)
        self.assertEqual(count, 62)

    def test_quoted_slash_and_typed_ids_and_exclusive_output_formats(self):
        raw = json.dumps([{'op':'replace','path':'/items/"a/b"/count','value':3},
                          {'op':'remove','path':'/values/1'}])
        custom = self.run_raw(raw)
        standard = self.run_raw(raw, {'json_patch': True})
        self.assertTrue(custom['accepted'], custom)
        self.assertTrue(standard['accepted'], standard)
        self.assertEqual(custom['patch'][0]['path'], ['items', 'a/b', 'count'])
        self.assertEqual(standard['patch'][0]['path'], '/items/0/count')
        self.assertEqual(custom['finalState']['values'], ['1', False, None])
        self.assertEqual(custom['finalState'], standard['finalState'])
        self.assertNotIn('rfcPatch', custom)
        self.assertNotIn('customPatch', standard)

    def test_per_collection_id_keys_and_schema_validation(self):
        self.state['other'] = [{'other_id':'z', 'count':8}]
        self.schema['properties']['other'] = {'type':'array','x-id-field':'other_id',
            'items':obj({'other_id':{'type':'string'},'count':{'type':'number'}})}
        self.schema['required'].append('other')
        result = self.run_raw('[{"op":"replace","path":"/other/\\"z\\"/count","value":9}]')
        self.assertTrue(result['accepted'], result)
        self.assertEqual(result['finalState']['other'][0]['count'], 9)

    def test_rejects_wrong_scopes_collisions_and_invalid_schema_changes(self):
        bad = [
            {'op':'remove','path':'/items/"a/b"/count'},
            {'op':'replace','path':'/items/"a/b"','value':{'key':'a/b','count':8}},
            {'op':'replace','path':'/items','value':[]},
            {'op':'add','path':'/items','value':{'key':'b','count':8}},
            {'op':'add','path':'/items','value':{'key':'new'}},
            {'op':'replace','path':'/items/"a/b"/count','value':'wrong type'},
            {'op':'move','from':'/items/"a/b"','path':'/items'},
            {'op':'replace','path':'/missing','value':1},
        ]
        for operation in bad:
            with self.subTest(operation=operation):
                self.assertFalse(self.run_raw(json.dumps([operation]))['accepted'])

    def test_literal_add_uses_existing_target_type_but_append_stays_strict(self):
        for spelling, accepted in (('add', True), ('append', False), ('insert', False)):
            raw = json.dumps([{'op': spelling, 'path': '/items/"a/b"/count', 'value': 8}])
            result = self.run_raw(raw)
            self.assertEqual(result['accepted'], accepted, result)
            if accepted:
                self.assertEqual(result['finalState']['items'][0]['count'], 8)

    def test_unlabeled_transfers_use_current_schema_state_not_order(self):
        result = self.run_raw('move ["storage"] ["items","a/b"]')
        self.assertTrue(result['accepted'], result)
        self.assertEqual(result['patch'][0], {'op':'move','from':['items','a/b'],'to':['storage']})
        ambiguous = self.run_raw('move ["storage"] ["items"]')
        self.assertFalse(ambiguous['accepted'])

    def test_numeric_property_serialization_and_utf16_hash_contract(self):
        self.assertEqual(encode_path([1.0, -0.0]), '/1/0')
        state, schema = {'1': 0}, obj({'1': {'type': 'number'}})
        result = replay_value_intent('update path:[1] value:2', state, schema)
        self.assertTrue(result['accepted'], result)
        self.assertEqual(result['finalState'], {'1': 2})
        raw = '\ud800'
        result = self.run_raw(raw)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['rawSha256'], hashlib.sha256('\ufffd'.encode()).hexdigest())

    def test_no_network_backend_or_oracle_input(self):
        with patch('socket.socket', side_effect=AssertionError('network prohibited')), \
             patch('subprocess.Popen', side_effect=AssertionError('backend prohibited')):
            result = self.run_raw('[]')
        self.assertTrue(result['accepted'])
        self.assertEqual(result['finalState'], self.state)


if __name__ == '__main__':
    unittest.main()
