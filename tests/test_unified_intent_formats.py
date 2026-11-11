"""All current formats use one grammar; no model inference or result rewriting."""
import copy
import json
import unittest
from unittest.mock import patch

from evaluation import array_identities_intent as host
from evaluation import output_formats
from intent_parser.parse import parse_intent_with_diagnostics
from prompt_builder.builder import ROOT, compile_test, discover, load_case
from prompt_builder.reference_output import encode
from workbench.workflows import evaluate

FORMATS = ('json_dot', 'json_slash', 'path_list', 'literal_line', 'end_marked_line', 'typed_lines')


class UnifiedIntentFormatTests(unittest.TestCase):
    def setUp(self):
        self.state = {'items': [{'key': 'town-a', 'count': 1, 'note': 'old'}], 'archive': [], 'note': 'old', 'count': 1}
        self.ids = [{'path': ['items'], 'id_field': 'key'}, {'path': ['archive'], 'id_field': 'key'}]

    def apply(self, raw, form='typed_lines', state=None, ids=None):
        return host.normalize_response(raw, self.state if state is None else state, form,
                                       self.ids if ids is None else ids)

    def test_every_format_passes_through_exact_same_grammar_entry(self):
        canonical = [{'op': 'copy', 'from': 'items.town-a', 'path': 'archive'}]
        for form in FORMATS:
            raw = encode(self.state, canonical, form, self.ids)
            with self.subTest(form=form), patch.object(output_formats, 'parse_intent_with_diagnostics', wraps=parse_intent_with_diagnostics) as parser:
                result = self.apply(raw, form)
                self.assertEqual(parser.call_count, 1)
                self.assertEqual(parser.call_args.args[0], raw)
                self.assertEqual(result['normalized_patch'], canonical)
                self.assertEqual(result['diagnostics']['reader'], 'shared_intent_grammar')
                self.assertNotIn('initial_state', parser.call_args.args[1])
                self.assertNotIn('expected_state', parser.call_args.args[1])

    def test_requested_format_does_not_gate_structural_acceptance(self):
        for form in FORMATS:
            with self.subTest(form=form):
                result = self.apply('COPY: /items/town-a\nto: /archive', form)
                self.assertEqual(result['final_state']['archive'], self.state['items'])
                self.assertEqual(result['final_state']['items'], self.state['items'])

    def test_bare_unique_string_ids_all_operation_types(self):
        raw = 'set: /items/town-a/count\nnumber: 2\ncopy: /items/town-a\nto: /archive\nremove: /items/town-a'
        result = self.apply(raw)
        self.assertEqual(result['final_state']['items'], [])
        self.assertEqual(result['final_state']['archive'], [{'key': 'town-a', 'count': 2, 'note': 'old'}])
        self.assertEqual(self.state['items'][0]['count'], 1)

    def test_no_positional_fallback_or_typed_id_coercion(self):
        for raw in ('remove: /items/0', 'remove: /items/missing'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.apply(raw)
        state = {'numbers': [42], 'strings': ['42']}
        ids = [{'path': ['numbers'], 'id_field': None}, {'path': ['strings'], 'id_field': None}]
        for raw in ('remove: /numbers/"42"', 'remove: /strings/42'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.apply(raw, state=state, ids=ids)
        actual = self.apply('remove: /numbers/42\nremove: /strings/"42"', state=state, ids=ids)['final_state']
        self.assertEqual(actual, {'numbers': [], 'strings': []})

    def test_explicit_grouped_scalars_preserve_types(self):
        state = {'numbers': [42], 'strings': ['42'], 'booleans': [True]}
        ids = [{'path': [key], 'id_field': None} for key in state]
        for raw in ('remove path:["numbers","42"]', 'remove path:["strings",42]',
                    'remove path:["booleans","true"]', 'remove [numbers,"42"]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.apply(raw, 'path_list', state, ids)
        # The documented path-list style has unquoted, textual selectors.
        self.assertEqual(self.apply('remove [strings,42]', 'path_list', state, ids)['final_state']['strings'], [])
        self.assertEqual(self.apply('remove [true,42]', 'path_list', {'true': ['42']}, [{'path': ['true'], 'id_field': None}])['final_state'], {'true': []})
        self.assertEqual(self.apply('remove [42]', 'path_list', ['42'], [{'path': [], 'id_field': None}])['final_state'], [])

    def test_numeric_underflow_never_changes_an_identity(self):
        state = {'ids': [0]}
        ids = [{'path': ['ids'], 'id_field': None}]
        for raw, form in (('remove: /ids/1e-1000', 'typed_lines'),
                          ('[{"op":"remove","path":"/ids/1e-1000"}]', 'json_slash'),
                          ('remove path:["ids",1e-1000]', 'path_list')):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'underflow'):
                self.apply(raw, form, state, ids)
        self.assertEqual(state, {'ids': [0]})

    def test_slash_fields_and_quoted_id_slashes_preserve_spelling(self):
        state = {'a.b c': [{'key': 'x/y', 'd.e f': 1}]}
        ids = [{'path': ['a.b c'], 'id_field': 'key'}]
        result = self.apply('set: /a.b c/"x/y"/d.e f\nnumber: 2', state=state, ids=ids)
        self.assertEqual(result['final_state']['a.b c'][0]['d.e f'], 2)

    def test_json_values_and_text_keywords_remain_data(self):
        text = 'copy: /items/town-a to: /archive { ] " op:remove'
        result = self.apply('set: /note\ntext: ' + text)
        self.assertEqual(result['final_state']['note'], text)
        self.assertEqual(result['final_state']['archive'], [])
        payload = {'op': 'remove', 'path': '/items/town-a', 'nested': {'text': 'copy'}}
        raw = 'set: /note\nobject: ' + json.dumps(payload)
        self.assertEqual(self.apply(raw)['final_state']['note'], payload)

    def test_extra_information_and_ambiguous_paths_are_not_dropped(self):
        for raw in ('copy: /items/town-a\nto: /archive\ntext: extra',
                    'copy [items] [archive]',
                    'set: /note\nobject: {"x":1',
                    'remove: /items/town-a\nnumber: 2'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.apply(raw)
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            self.apply('set: a.b\nvalue: 3', 'two_line_text', {'a.b': 1, 'a': {'b': 2}}, [])

    def test_final_state_not_expected_patch_is_verdict(self):
        test = compile_test('update_field', 'typed_lines', input_formats=['normal_json'])
        variant = test['variants'][0]
        raw = encode(test['source']['initial_state'], variant['expected_patch'], 'typed_lines', test['source']['array_identities'])
        score = evaluate(test, variant, {'patch': raw})
        self.assertTrue(score['exact_match'], score)
        altered = copy.deepcopy(test)
        altered['expected_state']['profile']['hair'] = 'not-the-requested-answer'
        self.assertFalse(evaluate(altered, altered['variants'][0], {'patch': raw})['exact_match'])
        altered = copy.deepcopy(test)
        altered['variants'][0]['expected_patch'] = []
        self.assertTrue(evaluate(altered, altered['variants'][0], {'patch': raw})['exact_match'])

    def test_literal_add_uses_target_type_but_append_never_means_update(self):
        for raw in ('add path:"count" value:7', 'ADD: /count\nnumber: 7',
                    '[{"op":"add","path":"count","value":7}]'):
            self.assertEqual(self.apply(raw)['final_state']['count'], 7)
        result = self.apply('add: /archive\nobject: {"key":"new"}')
        self.assertEqual(result['final_state']['archive'], [{'key': 'new'}])
        for raw in ('append path:"count" value:7', 'insert path:"count" value:7',
                    'add path:["items","town-a"] value:{"key":"different"}',
                    'add path:[] value:{}', 'add path:"missing" value:7'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.apply(raw)
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            self.apply('add path:"a.b" value:3', 'json_dot', {'a.b': 1, 'a': {'b': 2}}, [])

    def test_all_current_case_format_input_references_372(self):
        count = 0
        for name in discover()['test_cases']:
            case = load_case(name)
            for form in FORMATS:
                test = compile_test(case, form, input_formats=['normal_json', 'id_keyed_arrays', 'full_paths'])
                for variant in test['variants']:
                    with self.subTest(case=name, form=form, input=variant['id']):
                        raw = encode(test['source']['initial_state'], variant['expected_patch'], form, test['source']['array_identities'])
                        score = evaluate(test, variant, {'patch': raw})
                        self.assertTrue(score['exact_match'], score)
                        self.assertTrue(score['expected_patch_match'], score)
                        count += 1
        self.assertEqual(count, 372)


if __name__ == '__main__':
    unittest.main()
