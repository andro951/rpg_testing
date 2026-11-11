import copy
import json
import unittest
from unittest.mock import patch

from prompt_builder.builder import compile_test, load_case, prompt
from prompt_builder.presentation import render


class DeclaredIdBoundaryTests(unittest.TestCase):
    def test_converters_never_guess_and_keep_exact_nested_paths(self):
        data = {
            'rows.list': [{'': 'a.b/%雪', 'id': 'decoy', 'empty': []}],
            'rows': {'list': [{'sku': False, 'id': 'another-decoy'}]},
        }
        declarations = [
            {'path': ['rows.list'], 'id_field': ''},
            {'path': ['rows.list', None, 'empty'], 'id_field': 'future sku'},
            {'path': ['rows', 'list'], 'id_field': 'sku'},
        ]
        original = copy.deepcopy((data, declarations))
        with patch('prompt_builder.presentation.id_field',
                   side_effect=AssertionError('Conversions must not guess IDs')):
            keyed = json.loads(render(data, 'id_keyed_arrays', declarations))
            paths = render(data, 'full_paths', declarations).splitlines()
        self.assertEqual(keyed, {'$object': {
            'rows.list': {'$array': {'a.b/%雪': {'$object': {
                '': 'a.b/%雪', 'id': 'decoy', 'empty': {'$array': {}}}}}},
            'rows': {'$object': {'list': {'$array': {'false': {'$object': {
                'sku': False, 'id': 'another-decoy'}}}}}},
        }})
        self.assertIn('rows%2Elist.a%2Eb%2F%25%E9%9B%AA.%_: "a.b/%雪"', paths)
        self.assertIn('rows%2Elist.a%2Eb%2F%25%E9%9B%AA.empty: []', paths)
        self.assertIn('rows.list.false.sku: false', paths)
        self.assertEqual((data, declarations), original)

    def test_failed_conversions_never_fall_back_to_guessed_ids(self):
        cases = [
            ([{'id': 'a'}], None),
            ([{'id': 'a'}], []),
            ([{'id': 'a'}], [{'path': [], 'id_field': 'missing'}]),
            ([True, 'true'], [{'path': [], 'id_field': None}]),
            ([None, 'null'], [{'path': [], 'id_field': None}]),
            ([1, '1'], [{'path': [], 'id_field': None}]),
            ([1, 1.0], [{'path': [], 'id_field': None}]),
            ([], []),
        ]
        with patch('prompt_builder.presentation.id_field',
                   side_effect=AssertionError('Invalid maps must not trigger guesses')):
            for data, declarations in cases:
                original = copy.deepcopy((data, declarations))
                for mode in ('id_keyed_arrays', 'full_paths'):
                    with self.subTest(data=data, declarations=declarations, mode=mode):
                        with self.assertRaises(ValueError):
                            render(data, mode, declarations)
                        self.assertEqual((data, declarations), original)

    def test_normal_json_and_tables_never_consume_mapping(self):
        class MapForbiddenCase(dict):
            def __getitem__(self, key):
                if key == 'array_identities':
                    raise AssertionError('This presentation cannot read the map')
                return super().__getitem__(key)

            def get(self, key, default=None):
                if key == 'array_identities':
                    raise AssertionError('This presentation cannot read the map')
                return super().get(key, default)

        case = MapForbiddenCase(load_case('update_record_field'))
        with patch('prompt_builder.presentation.IdentityMap',
                   side_effect=AssertionError('This presentation cannot inspect the map')):
            for mode in ('normal_json', 'named_tables'):
                expected = render(case['starting_data'], mode)
                self.assertEqual(render(case['starting_data'], mode, object()), expected)
                self.assertEqual(prompt(case, mode, 'json_dot', with_parts=True)[1]['current_state'], expected)

    def test_normal_json_still_requires_valid_map_for_evaluation(self):
        case = load_case('update_record_field')
        expected = prompt(case, 'normal_json', 'json_dot', with_parts=True)
        case['array_identities'] = []
        self.assertEqual(prompt(case, 'normal_json', 'json_dot', with_parts=True), expected)
        with self.assertRaisesRegex(ValueError, 'Missing array identity mapping'):
            compile_test(case, 'json_dot', input_formats=['normal_json'])


if __name__ == '__main__':
    unittest.main()
