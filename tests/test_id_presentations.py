"""Inspect every assembled prompt and exercise reusable ID-based renderers."""
import copy
import json
import re
import unittest
from unittest.mock import patch
from test_builder.builder import ROOT, LABELS, build_prompt, compile_test, oracle, presentations, prompt_parts
from test_builder.presentation import full_paths, id_keyed_arrays
from workbench.domain import read_json
from workbench.value_paths import from_pointer, resolve
from optimization.templates import bindings


class IdPresentationTests(unittest.TestCase):
    def setUp(self):
        self.fixtures = read_json(ROOT/'fixtures.json')['fixtures']
        self.by_id = {f['id']: f for f in self.fixtures}

    def test_every_actual_prompt_has_no_positional_instructions_or_index_answers(self):
        checked = 0
        for fixture in self.fixtures:
            for mode in presentations(fixture):
                with self.subTest(fixture=fixture['id'], presentation=mode):
                    prompt = build_prompt(fixture, mode)
                    self.assertIsNone(re.search(r'\b(index(?:es|ed|ing)?|indices|positions?|positional|zero.based)\b', prompt, re.I))
                    self.assertNotIn(' = ', prompt)
                    parts = prompt_parts(fixture, mode)
                    if mode == 'id_keyed_arrays':
                        self.check_dictionary(fixture['state'], fixture['schema'], json.loads(parts['current_state']))
                    elif mode == 'full_paths':
                        self.check_paths(fixture['state'], fixture['schema'], parts['current_state'].splitlines())
                    checked += 1
        self.assertEqual(checked, 62)

    def check_dictionary(self, original, schema, displayed):
        if isinstance(original, list):
            field = schema.get('x-id-field')
            ids = [element[field] if field else element for element in original]
            expected = [v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, separators=(',', ':')) for v in ids]
            self.assertEqual(list(displayed), expected)
            for key, element in zip(expected, original):
                self.check_dictionary(element, schema['items'], displayed[key])
        elif isinstance(original, dict):
            self.assertEqual(list(displayed), list(original))
            for key, element in original.items():
                self.check_dictionary(element, schema['properties'][key], displayed[key])
        else:
            self.assertEqual(type(displayed), type(original))
            self.assertEqual(displayed, original)

    def check_paths(self, original, schema, lines):
        expected = []
        def walk(value, pointer=''):
            if isinstance(value, dict) and value:
                for key, element in value.items():
                    walk(element, pointer + '/' + key.replace('~', '~0').replace('/', '~1'))
            elif isinstance(value, list) and value:
                for n, element in enumerate(value):
                    walk(element, pointer + '/' + str(n))
            else:
                path = from_pointer(original, schema, pointer)
                selected, _, _ = resolve(original, schema, path)
                self.assertEqual(selected, value)
                expected.append(path + ':' + json.dumps(value, ensure_ascii=False, separators=(',', ':')))
        walk(original)
        self.assertEqual(lines, expected)

    def test_full_path_matches_update_answer_literally_and_uses_compact_colon(self):
        f = self.by_id['db_v3_update_record']
        patch_value, _ = oracle(f)
        path = patch_value[0]['path']
        selected, _, _ = resolve(f['state'], f['schema'], path)
        lines = prompt_parts(f, 'full_paths')['current_state'].splitlines()
        self.assertIn(path + ':' + json.dumps(selected), lines)
        self.assertIn('/items/"item-17"/count:8', lines)
        self.assertNotIn('"/items/', '\n'.join(lines))

    def test_nested_collections_quotes_slashes_and_literal_string_data_survive(self):
        f = copy.deepcopy(self.by_id['db_v3_update_nested_collection'])
        # Reuse its arbitrary schema nesting; verify all leaves using the independent resolver.
        def alter(value, schema):
            if isinstance(value, dict):
                for key in value:
                    alter(value[key], schema['properties'][key])
            elif isinstance(value, list):
                field = schema.get('x-id-field')
                for n, element in enumerate(value):
                    if field:
                        element[field] = f'ID/{n}:"quoted"\\~\nvalue'
                    alter(element, schema['items'])
        alter(f['state'], f['schema'])
        before = copy.deepcopy(f['state'])
        self.check_dictionary(f['state'], f['schema'], id_keyed_arrays(f['state'], f['schema']))
        lines = full_paths(f['state'], f['schema'])
        self.check_paths(f['state'], f['schema'], lines)
        self.assertTrue(any('ID/' in line and '\\nvalue' in line for line in lines))
        self.assertEqual(f['state'], before)

    def test_primitive_ids_keep_types_and_dictionary_collisions_are_rejected(self):
        schema = {'type':'array', 'items':{'type':['string','number','boolean','null']}, 'uniqueItems':True}
        values = ['town/a', 42, True, None]
        converted = id_keyed_arrays(values, schema)
        self.assertEqual(converted, {'town/a':'town/a', '42':42, 'true':True, 'null':None})
        self.assertEqual(full_paths(values, schema), ['/"town/a":"town/a"', '/42:42', '/true:true', '/null:null'])
        for values in ([42, '42'], [True, 'true'], [None, 'null'], ['duplicate', 'duplicate']):
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, 'collide'):
                    id_keyed_arrays(values, schema)

    def test_schema_declared_custom_id_fields_work_inside_nested_collections(self):
        f = copy.deepcopy(self.by_id['db_v3_update_record'])
        group_schema = {'type':'object', 'properties':{'group_key':{'type':'string'}, 'inventory':f['schema']},
                        'required':['group_key','inventory'], 'additionalProperties':False}
        f['state'] = {'groups':[{'group_key':'group/a', 'inventory':f['state']}]}
        f['schema'] = {'type':'object', 'properties':{'groups':{'type':'array', 'x-id-field':'group_key', 'items':group_schema}},
                       'required':['groups'], 'additionalProperties':False}
        f['parameters']['array_path'] = '/groups/0/inventory/items'
        displayed = json.loads(prompt_parts(f, 'id_keyed_arrays')['current_state'])
        self.assertEqual(displayed['groups']['group/a']['group_key'], 'group/a')
        self.assertEqual(displayed['groups']['group/a']['inventory']['items']['item-17']['item_id'], 'item-17')
        self.check_dictionary(f['state'], f['schema'], displayed)
        lines = prompt_parts(f, 'full_paths')['current_state'].splitlines()
        self.assertIn('/groups/"group/a"/inventory/items/"item-17"/count:8', lines)
        self.check_paths(f['state'], f['schema'], lines)

    def test_empty_containers_and_quoted_field_names_are_unambiguous(self):
        schema = {'type':'object', 'properties':{'"field':{'type':'array','items':{'type':'string'}}, 'a/b':{'type':'object','properties':{}}}}
        state = {'"field':[], 'a/b':{}}
        self.assertEqual(full_paths(state, schema), ['/"\\"field":[]', '/a~1b:{}'])
        self.assertEqual(id_keyed_arrays(state, schema), {'"field':{}, 'a/b':{}})

    def test_optimizer_uses_exact_new_prompt_views_without_legacy_rendering(self):
        for f in self.fixtures:
            test = compile_test(f)
            for variant in test['variants']:
                case = {'test':test, 'variant':variant, 'presentation':LABELS[variant['id']]}
                with patch('optimization.templates._legacy_full_paths', side_effect=AssertionError('legacy view used')):
                    actual = bindings(case)
                expected = prompt_parts(f, variant['id'])
                for key in expected:
                    self.assertEqual(actual[key], expected[key])
