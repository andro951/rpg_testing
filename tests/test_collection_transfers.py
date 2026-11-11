"""Five-operation collection semantics, deterministic examples, no inference."""
import copy
import json
import unittest
from unittest.mock import patch

from evaluation import array_identities_intent as host, schema_free_intent as legacy
from evaluation.hosts import selected
from prompt_builder.reference_output import encode
from workbench.domain import validate_test
from workbench.workflows import evaluate


def declaration(path, field=None):
    return {'path': path, 'id_field': field}


def fixture():
    return ({'source': [{'sku': 'a.b/~', 'name': 'complete', 'children': ['x', 'y'],
                         'details': {'count': 4}}, {'sku': 'keep', 'name': 'kept',
                         'children': [], 'details': {'count': 2}}],
             'destination': [], 'other': ['existing'], 'primitives': ['transfer', 4, False, None],
             'note': 'unchanged'},
            [declaration(['source'], 'sku'), declaration(['source', None, 'children']),
             declaration(['destination'], 'sku'), declaration(['destination', None, 'children']),
             declaration(['other']), declaration(['primitives'])])


class CollectionTransferTests(unittest.TestCase):
    def assert_roundtrip(self, initial, operations, declarations, expected):
        for output_format in host.OUTPUT_FORMATS:
            with self.subTest(output_format=output_format):
                before = copy.deepcopy(initial)
                raw = encode(initial, operations, output_format, declarations)
                result = host.normalize_response(raw, initial, output_format, declarations)
                self.assertEqual(result['final_state'], expected)
                self.assertEqual(result['normalized_patch'], operations)
                self.assertEqual(initial, before, 'Normalization must not mutate caller data')

    def test_move_and_copy_complete_elements_empty_and_nonempty_destinations(self):
        for verb in ('move', 'copy'):
            for primitive in (False, True):
                for empty in (False, True):
                    with self.subTest(verb=verb, primitive=primitive, empty=empty):
                        initial, declarations = fixture()
                        source, destination = ('primitives', 'other') if primitive else ('source', 'destination')
                        if primitive:
                            if empty:
                                initial[destination] = []
                        elif not empty:
                            initial[destination] = [{'sku': 'prior', 'name': 'prior', 'children': [],
                                                     'details': {'count': 0}}]
                        expected = copy.deepcopy(initial)
                        expected[destination].append(copy.deepcopy(expected[source][0]))
                        if verb == 'move':
                            del expected[source][0]
                        path = source + '.' + ('transfer' if primitive else 'a%2Eb%2F%7E')
                        self.assert_roundtrip(initial, [{'op': verb, 'from': path, 'path': destination}],
                                              declarations, expected)

    def test_typed_primitive_identities_and_escaped_component_transfers(self):
        for value in (4, False, None, 'a,] -> b.~/c', ''):
            for verb in ('move', 'copy'):
                initial = {'odd.destination': [], 'source': [value]}
                declarations = [declaration(['source']), declaration(['odd.destination'])]
                operation = {'op': verb, 'from': 'source.' + host.encode_part(host.scalar_text(value)),
                             'path': 'odd%2Edestination'}
                expected = {'odd.destination': [value], 'source': [] if verb == 'move' else [value]}
                self.assert_roundtrip(initial, [operation], declarations, expected)

    def test_copy_is_independent_and_operations_see_latest_state(self):
        initial, declarations = fixture()
        operations = [
            {'op': 'copy', 'from': 'source.a%2Eb%2F%7E', 'path': 'destination'},
            {'op': 'replace', 'path': 'destination.a%2Eb%2F%7E.details.count', 'value': 9},
            {'op': 'add', 'path': 'destination.a%2Eb%2F%7E.children', 'value': 'z'},
            {'op': 'remove', 'path': 'source.a%2Eb%2F%7E'},
            {'op': 'move', 'from': 'destination.a%2Eb%2F%7E', 'path': 'source'},
            {'op': 'replace', 'path': 'source.a%2Eb%2F%7E.name', 'value': 'changed'},
        ]
        expected = copy.deepcopy(initial)
        transferred = expected['source'].pop(0)
        transferred['details']['count'] = 9
        transferred['children'].append('z')
        transferred['name'] = 'changed'
        expected['source'].append(transferred)
        self.assert_roundtrip(initial, operations, declarations, expected)

        copied = host.apply_patch(initial, operations[:1], declarations)['final_state']
        self.assertIsNot(copied['source'][0], copied['destination'][0])
        self.assertIsNot(copied['source'][0]['children'], copied['destination'][0]['children'])
        self.assertIsNot(copied['source'][0]['details'], copied['destination'][0]['details'])
        copied['destination'][0]['children'].append('separate')
        self.assertEqual(copied['source'][0]['children'], ['x', 'y'])
        self.assertEqual(initial['source'][0]['children'], ['x', 'y'])

    def test_source_removal_does_not_shift_nested_destination_before_append(self):
        initial = {'groups': [{'key': 'take', 'children': []}, {'key': 'keep', 'children': []}]}
        declarations = [declaration(['groups'], 'key'), declaration(['groups', None, 'children'], 'key'),
                        declaration(['groups', None, 'children', None, 'children'], 'key')]
        operations = [{'op': 'move', 'from': 'groups.take', 'path': 'groups.keep.children'},
                      {'op': 'replace', 'path': 'groups.keep.children.take.key', 'value': 'moved'}]
        expected = {'groups': [{'key': 'keep', 'children': [{'key': 'moved', 'children': []}]}]}
        self.assert_roundtrip(initial, operations, declarations, expected)

    def test_transfer_guardrails_and_failure_leave_input_unchanged(self):
        initial, declarations = fixture()
        invalid = [
            ('source.missing', 'destination'), ('source.0', 'destination'),
            ('source', 'destination'), ('note', 'destination'),
            ('source.a%2Eb%2F%7E.name', 'other'), ('source.a%2Eb%2F%7E', 'source'),
            ('source.a%2Eb%2F%7E', 'source.a%2Eb%2F%7E.children'),
            ('source.a%2Eb%2F%7E', 'note'), ('source.a%2Eb%2F%7E', 'destination.-'),
            ('source.a%2Eb%2F%7E', 'other'), ('primitives.transfer', 'destination'),
        ]
        for verb in ('move', 'copy'):
            for source, destination in invalid:
                with self.subTest(verb=verb, source=source, destination=destination):
                    before = copy.deepcopy(initial)
                    with self.assertRaises(ValueError):
                        host.apply_patch(initial, [{'op': verb, 'from': source, 'path': destination}], declarations)
                    self.assertEqual(initial, before)
            for extra in ({'value': 1}, {'to': 'other'}):
                with self.assertRaises(ValueError):
                    host.apply_patch(initial, [{'op': verb, 'from': 'primitives.transfer',
                                                'path': 'other', **extra}], declarations)

    def test_duplicate_destination_identity_and_missing_destination_identity_rejected(self):
        initial, declarations = fixture()
        initial['destination'] = [copy.deepcopy(initial['source'][0])]
        initial['destination'][0]['name'] = 'different payload, same identity'
        for verb in ('move', 'copy'):
            with self.subTest(verb=verb), self.assertRaisesRegex(ValueError, 'Duplicate'):
                host.apply_patch(initial, [{'op': verb, 'from': 'source.a%2Eb%2F%7E',
                                            'path': 'destination'}], declarations)
        initial['destination'] = []
        declarations[2]['id_field'] = 'different_key'
        with self.assertRaisesRegex(ValueError, 'scalar field'):
            host.apply_patch(initial, [{'op': 'copy', 'from': 'source.a%2Eb%2F%7E',
                                        'path': 'destination'}], declarations)

    def test_unlabeled_transfer_paths_require_unique_current_data_roles(self):
        initial, declarations = fixture()
        for raw in ('move ["primitives","transfer"] ["other"]',
                    'move ["other"] ["primitives","transfer"]'):
            result = host.normalize_response(raw, initial, 'json_dot', declarations)
            self.assertEqual(result['normalized_patch'], [{'op': 'move', 'from': 'primitives.transfer', 'path': 'other'}])
        for raw in ('copy ["source"] ["destination"]',
                    'copy ["primitives","transfer"] ["primitives",4]'):
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                host.normalize_response(raw, initial, 'json_dot', declarations)

    def test_manual_transfer_syntax_and_invalid_record_payloads(self):
        initial, declarations = fixture()
        examples = {
            'json_dot': '[{"op":"copy","from":"primitives.transfer","path":"other"}]',
            'json_slash': '[{"op":"copy","from":"/primitives/\\"transfer\\"","path":"/other"}]',
            'path_list': 'copy [primitives, transfer] -> [other]',
            'literal_line': 'copy primitives.transfer -> other',
            'end_marked_line': 'copy primitives.transfer -> other',
            'two_line_text': 'copy: primitives.transfer\nto: other',
            'typed_lines': 'copy: /primitives/"transfer"\nto: /other',
            'free_format': 'copy from:primitives.transfer to:other',
        }
        for output_format, raw in examples.items():
            with self.subTest(output_format=output_format):
                result = host.normalize_response(raw, initial, output_format, declarations)
                self.assertEqual(result['final_state']['other'], ['existing', 'transfer'])
                self.assertEqual(result['final_state']['primitives'], initial['primitives'])
                with self.assertRaises(ValueError):
                    legacy.normalize_response(raw, initial, output_format)
        invalid = {
            'path_list': ['copy [primitives, transfer]', 'copy [primitives, transfer] -> [other]: null'],
            'literal_line': ['copy primitives.transfer', 'copy primitives.transfer -> other: json:null'],
            'two_line_text': ['copy: primitives.transfer', 'copy: primitives.transfer\nvalue: "other"',
                              'copy: primitives.transfer\nto: other\nvalue: 3'],
            'typed_lines': ['copy: /primitives/"transfer"', 'copy: /primitives/"transfer"\ntext: /other',
                            'copy: /primitives/"transfer"\nto: /other\nnull:'],
        }
        for output_format, records in invalid.items():
            for raw in records:
                with self.subTest(output_format=output_format, raw=raw), self.assertRaises(ValueError):
                    host.normalize_response(raw, initial, output_format, declarations)

    def test_typed_transfers_preserve_unsafe_field_guard_and_literal_ids(self):
        initial = {'source': ['constructor'], 'destination': [], 'constructor': []}
        declarations = [declaration([key]) for key in initial]
        result = host.normalize_response('copy: /source/"constructor"\nto: /destination',
                                         initial, 'typed_lines', declarations)
        self.assertEqual(result['final_state']['destination'], ['constructor'])
        with self.assertRaisesRegex(ValueError, 'Unsafe'):
            host.normalize_response('copy: /source/"constructor"\nto: /constructor',
                                    initial, 'typed_lines', declarations)

    def test_explicit_v3_contract_and_frozen_v1_rejected_before_normalization(self):
        from tests.test_array_identities_intent import fixture as scoring_fixture
        test = scoring_fixture()
        self.assertEqual(host.VERSION, 'array-identities-intent-v3')
        variant = test['variants'][0]
        variant['result']['evaluator']['version'] = 'array-identities-intent-v1'
        self.assertIs(selected(variant['result']), host)
        with self.assertRaisesRegex(ValueError, '[Rr]etired|stale'):
            validate_test(test)
        with patch.object(host, 'normalize_response', side_effect=AssertionError('Must not rescore v1')):
            result = evaluate(test, variant, {'patch': '[]'})
        self.assertEqual(result['status'], 'configuration_error')
        self.assertIsNone(result['exact_match'])


if __name__ == '__main__':
    unittest.main()
