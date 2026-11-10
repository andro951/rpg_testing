"""Literal separator acceptance without changing JSON or operation contracts."""
import json
import string
import unittest

from evaluation import dot_separators_v2 as dot_paths
from workbench.scoring import parse


def obj(properties):
    return {'type': 'object', 'properties': properties,
            'required': list(properties), 'additionalProperties': False}


TEXT = {'type': 'string'}
ELEMENT = obj({'id': TEXT, 'value': TEXT})
SCHEMA = obj({'elements': {'type': 'array', 'x-id-field': 'id', 'items': ELEMENT}})

# Derived from tokens/decode_part/encode_part, full_paths' colon delimiter,
# JSONDecoder's quoted-component grammar, and value_paths' slash delimiter.
GRAMMAR_CHARACTERS = {
    'dot component boundary': '.',
    'percent escape introducer': '%',
    'empty-component escape suffix': '_',
    'JSON string delimiter': '"',
    'JSON string escape': '\\',
    'full-path value delimiter': ':',
    'slash path delimiter': '/',
    'JSON element/field delimiter': ',',
    'JSON object delimiters': '{}',
    'JSON array delimiters': '[]',
    'JSON whitespace': ' \t\r\n',
}


class DotSeparatorResolutionTests(unittest.TestCase):
    def state(self, identifier):
        return {'elements': [{'id': identifier, 'value': 'old'}]}

    def test_each_grammar_character_has_encoded_and_quoted_coverage(self):
        for origin, characters in GRAMMAR_CHARACTERS.items():
            for character in characters:
                identifier = 'left' + character + 'right'
                for spelling in (dot_paths.encode_part(identifier), json.dumps(identifier)):
                    with self.subTest(origin=origin, character=character, spelling=spelling):
                        self.assertEqual(dot_paths.resolve(
                            self.state(identifier), SCHEMA, 'elements.' + spelling + '.value')[0], 'old')

    def test_printable_ascii_unicode_and_literal_characters_except_escape_syntax(self):
        for character in string.printable + '\u2603\u96ea':
            identifier = 'left' + character + 'right'
            state = self.state(identifier)
            path = 'elements.' + identifier + '.value'
            with self.subTest(character=character):
                if character == '%':
                    with self.assertRaisesRegex(ValueError, 'escape'):
                        dot_paths.resolve(state, SCHEMA, path)
                else:
                    self.assertEqual(dot_paths.resolve(state, SCHEMA, path)[0], 'old')
                    result = dot_paths.apply(state, [
                        {'op': 'replace', 'path': path, 'value': 'new'}], SCHEMA)
                    self.assertEqual(result['elements'][0]['value'], 'new')
                    self.assertEqual(state['elements'][0]['value'], 'old')

    def test_leading_trailing_and_repeated_literal_dots(self):
        for identifier in ('.', '..', '.first', 'last.', 'a..b', ' leading', 'trailing ', '\t', '\n'):
            with self.subTest(identifier=identifier):
                self.assertEqual(dot_paths.resolve(
                    self.state(identifier), SCHEMA, 'elements.' + identifier + '.value')[0], 'old')
        with self.assertRaises(ValueError):
            dot_paths.resolve(self.state(''), SCHEMA, 'elements..value')
        self.assertEqual(dot_paths.resolve(self.state(''), SCHEMA, 'elements.%_.value')[0], 'old')

    def test_literal_identity_and_structural_path_ambiguity_is_rejected(self):
        element = obj({'id': TEXT, 'b': obj({'note': TEXT}), 'note': TEXT})
        schema = obj({'elements': {'type': 'array', 'x-id-field': 'id', 'items': element}})
        state = {'elements': [
            {'id': 'a', 'b': {'note': 'structural'}, 'note': 'parent'},
            {'id': 'a.b', 'b': {'note': 'other'}, 'note': 'literal'},
        ]}
        with self.assertRaisesRegex(ValueError, 'Ambiguous dot path'):
            dot_paths.resolve(state, schema, 'elements.a.b.note')
        for path in ('elements.a%2Eb.note', 'elements."a.b".note'):
            self.assertEqual(dot_paths.resolve(state, schema, path)[0], 'literal')
        self.assertEqual(dot_paths.resolve(state, schema, 'elements.a.b.b.note')[0], 'other')

    def test_object_field_separator_ambiguity_is_also_rejected(self):
        leaf = obj({'value': TEXT})
        schema = obj({'group': obj({'a': leaf}), 'group.a': leaf})
        state = {'group': {'a': {'value': 'structural'}}, 'group.a': {'value': 'literal'}}
        with self.assertRaisesRegex(ValueError, 'Ambiguous dot path'):
            dot_paths.resolve(state, schema, 'group.a.value')
        for path in ('group%2Ea.value', '"group.a".value'):
            self.assertEqual(dot_paths.resolve(state, schema, path)[0], 'literal')

    def test_explicit_encoded_and_quoted_boundaries_are_never_reinterpreted(self):
        element = obj({'id': TEXT, 'c': TEXT})
        schema = obj({'elements': {'type': 'array', 'x-id-field': 'id', 'items': element}})
        state = {'elements': [{'id': 'a.b', 'c': 'first'}, {'id': 'a.b.c', 'c': 'second'}]}
        for path in ('elements.a%2Eb.c', 'elements.a%2eb.c', 'elements."a.b".c'):
            self.assertEqual(dot_paths.resolve(state, schema, path)[0], 'first')
        with self.assertRaises(ValueError):
            dot_paths.resolve({'a': {'b': 1}}, obj({'a': obj({'b': {'type': 'integer'}})}), 'a%2Eb')

    def test_nested_object_and_primitive_collection_identities(self):
        element = obj({'id': TEXT, 'children': {'type': 'array', 'uniqueItems': True, 'items': TEXT}})
        schema = obj({'teams': {'type': 'array', 'x-id-field': 'id', 'items': element}})
        children = ['n.b', 'n/b', 'n:b', 'n"b', 'n\\b', '[n]', '{n}', 'n,b']
        state = {'teams': [{'id': 'team.a', 'children': children}]}
        for parent in ('team.a', 'team%2Ea', '"team.a"'):
            for child in children:
                with self.subTest(parent=parent, child=child):
                    self.assertEqual(dot_paths.resolve(
                        state, schema, 'teams.' + parent + '.children.' + child)[0], child)
        result = dot_paths.apply(state, [
            {'op': 'remove', 'path': 'teams.team.a.children.n.b'},
            {'op': 'add', 'path': 'teams.team.a.children', 'value': 'new/value'},
        ], schema)
        self.assertEqual(result['teams'][0]['children'], children[1:] + ['new/value'])
        self.assertEqual(state['teams'][0]['children'], children)

    def test_malformed_percent_and_invalid_utf8_are_not_repaired(self):
        for identifier in ('a%', 'a%Z1', 'a%1Z', 'a%FF', 'a%_', 'a%2'):
            with self.subTest(identifier=identifier):
                with self.assertRaisesRegex(ValueError, 'escape'):
                    dot_paths.resolve(self.state(identifier), SCHEMA, 'elements.' + identifier + '.value')
                for spelling in (dot_paths.encode_part(identifier), json.dumps(identifier)):
                    self.assertEqual(dot_paths.resolve(
                        self.state(identifier), SCHEMA, 'elements.' + spelling + '.value')[0], 'old')

    def test_literal_percent_spelling_never_overrides_existing_escape_meaning(self):
        state = {'elements': [{'id': 'a.b', 'value': 'dot'},
                              {'id': 'a%2Eb', 'value': 'percent'}]}
        self.assertEqual(dot_paths.resolve(state, SCHEMA, 'elements.a%2Eb.value')[0], 'dot')
        self.assertEqual(dot_paths.resolve(state, SCHEMA, 'elements.a%252Eb.value')[0], 'percent')
        self.assertEqual(dot_paths.resolve(state, SCHEMA, 'elements."a%2Eb".value')[0], 'percent')

    def test_quoted_component_semantics_and_invalid_quoted_syntax_are_preserved(self):
        state = {'elements': [{'id': 'x', 'value': 'plain'},
                              {'id': '"x"', 'value': 'quoted'}]}
        self.assertEqual(dot_paths.resolve(state, SCHEMA, 'elements."x".value')[0], 'plain')
        self.assertEqual(dot_paths.resolve(state, SCHEMA, 'elements.%22x%22.value')[0], 'quoted')
        for path in ('elements."unterminated', 'elements."x"suffix.value'):
            with self.assertRaises(ValueError):
                dot_paths.resolve(state, SCHEMA, path)

    def test_numeric_identifiers_are_not_array_positions_or_bracket_access(self):
        for path in ('elements.0.value', 'elements[0].value', '/elements/actual/value'):
            with self.assertRaises(ValueError):
                dot_paths.resolve(self.state('actual'), SCHEMA, path)
        self.assertEqual(dot_paths.resolve(self.state('0'), SCHEMA, 'elements.0.value')[0], 'old')

    def test_literal_leading_quotes_are_allowed_when_not_explicit_quoted_syntax(self):
        for identifier in ('"leading', '"quoted"suffix', '"leading.dot'):
            with self.subTest(identifier=identifier):
                self.assertEqual(dot_paths.resolve(self.state(identifier), SCHEMA,
                                                   'elements.' + identifier + '.value')[0], 'old')

    def test_revalidation_preserves_original_scoring_and_operation_policy(self):
        from workbench.workflows import evaluate
        from evaluation.core import assess
        for identifier in ('a/b', 'a:b', 'a.b', '"leading'):
            with self.subTest(identifier=identifier):
                state = self.state(identifier)
                expected = self.state(identifier)
                expected['elements'][0]['value'] = 'new'
                test = {'id': 'separator-acceptance', 'source': {'initial_state': state},
                        'state_schema': SCHEMA, 'expected_state': expected}
                variant = {'id': 'plain', 'result': {'step': 'patch',
                           'representation': 'dot_patch_v1', 'required_ops': ['replace']}}
                operation = {'op': 'replace', 'path': 'elements.' + identifier + '.value', 'value': 'new'}
                response = json.dumps([operation])
                original = evaluate(test, variant, {'patch': response})
                self.assertFalse(original['exact_match'])
                current = assess(test, variant, {'patch': response}, original_score=original,
                                 validator='dot-separators-v2')
                self.assertEqual(current['objective_outcome'], 'PASS')
                self.assertEqual(current['original_score'], original)
                self.assertEqual(current['validator']['version'], 'dot-separators-v2')
                duplicate = assess(test, variant, {'patch': json.dumps([operation, operation])},
                                   validator='dot-separators-v2')
                self.assertEqual(duplicate['objective_outcome'], 'FAIL')
                self.assertTrue(any(c['code'] == 'patch.required_operations' and c['status'] == 'failed'
                                    for c in duplicate['checks']))

    def test_typed_identity_collisions_still_reject(self):
        schema = obj({'values': {'type': 'array', 'uniqueItems': True,
                                'items': {'type': ['string', 'number', 'boolean', 'null']}}})
        for values in ([1, '1'], [False, 'false'], [None, 'null']):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, 'Ambiguous'):
                dot_paths.apply({'values': values}, [], schema)
        state = {'values': [1, False, None, 'a.b']}
        for path, expected in [('1', 1), ('false', False), ('null', None), ('a.b', 'a.b')]:
            actual = dot_paths.resolve(state, schema, 'values.' + path)[0]
            self.assertIs(type(actual), type(expected))
            self.assertEqual(actual, expected)

    def test_operation_roles_and_values_are_not_normalized(self):
        state = self.state('id/a:b')
        value = '  literal \\n and actual\n"quote" %ZZ . / :  '
        result = dot_paths.apply(state, [
            {'op': 'replace', 'path': 'elements.id/a:b.value', 'value': value}], SCHEMA)
        self.assertEqual(result['elements'][0]['value'], value)
        for operation in (
            {'op': 'remove', 'path': 'elements.id/a:b.value'},
            {'op': 'replace', 'path': 'elements.id/a:b', 'value': state['elements'][0]},
            {'op': 'add', 'path': 'elements.id/a:b', 'value': state['elements'][0]},
            {'op': 'test', 'path': 'elements.id/a:b.value', 'value': 'old'},
        ):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                dot_paths.apply(state, [operation], SCHEMA)

    def test_resolution_tracks_identity_changes_and_independent_copy(self):
        collection = {'type': 'array', 'x-id-field': 'id', 'items': ELEMENT}
        schema = obj({'source': collection, 'dest': collection})
        initial = {'source': [{'id': 'old', 'value': 'keep'}], 'dest': []}
        result = dot_paths.apply(initial, [
            {'op': 'replace', 'path': 'source.old.id', 'value': 'new.id/a:b'},
            {'op': 'copy', 'from': 'source.new.id/a:b', 'path': 'dest'},
            {'op': 'replace', 'path': 'dest.new.id/a:b.value', 'value': 'changed'},
        ], schema)
        self.assertEqual(result['source'][0]['value'], 'keep')
        self.assertEqual(result['dest'][0]['value'], 'changed')
        self.assertEqual(initial['source'][0]['id'], 'old')

    def test_outer_json_parsing_is_unchanged(self):
        fence = chr(96) * 3
        for text in ('[{"op":"remove","path":"x","path":"y"}]',
                     '[{"op":"replace","path":"x","value":NaN}]',
                     fence + 'json\n[]\n' + fence, '[{"value":"unterminated}]'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse(text)


if __name__ == '__main__':
    unittest.main()
