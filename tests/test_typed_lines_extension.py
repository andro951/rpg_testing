"""New typed-line semantics do not modify published Ember semantics."""
import unittest
from evaluation import array_identities_intent as host
from evaluation import schema_free_intent as legacy
from evaluation.output_formats import decode

def records(raw):
    return decode(raw, "typed_lines", {})["operations"]


class TypedLineExtensionTests(unittest.TestCase):
    def apply(self, raw, state=None, declarations=None):
        return host.normalize_response(raw, state or {'items': []}, 'typed_lines', declarations if declarations is not None else [{'path': ['items'], 'id_field': 'key'}])['final_state']

    def test_order_append_update_remove_and_nested_selection(self):
        state = {'items': []}
        declarations = [{'path': ['items'], 'id_field': 'key'}, {'path': ['items', None, 'tags'], 'id_field': None}]
        raw = '''append: /items
object: {"key":"a/b","n":1,"tags":["x"]}
change: /items/"a/b"/n
number: 2
set: /items/"a/b"/n
number: 8
append: /items/"a/b"/tags
text: y
remove: /items/"a/b"/tags/"x"'''
        result = self.apply(raw, state, declarations)
        self.assertEqual(result, {'items': [{'key': 'a/b', 'n': 8, 'tags': ['y']}]})
        self.assertEqual(self.apply(raw+'\nremove: /items/"a/b"', state, declarations), state)

    def test_nullification_and_explicit_null(self):
        state = {'first': 1, 'second': 'x', 'items': [None]}
        self.assertEqual(self.apply('remove: /first\nset: /second\nnull:\nremove: /items/null', state, [{'path': ['items'], 'id_field': None}]), {'first': None, 'second': None, 'items': []})

    def test_wrong_payload_extra_lines_missing_paths_and_ids(self):
        invalid = ['append: /items\nobject: []', 'append: /items\nlist: {}',
                   'append: /items\nobject: {"key":"x","key":"y"}',
                   'remove: /items/"missing"', 'set: /missing\ntext: x',
                   'remove: /items/"a"\ntext: extra', 'change: /n\nboolean: true',
                   'set: /n\nnull: extra',
                   'append: /items\nobject: {"wrong":"b"}',
                   'append: /items\nobject: {"key":"a"}',
                   'set: /items/"a"\nobject: {"key":"b"}',
                   'remove: /items', 'remove: /items/0', 'set: /n\nnumber: NaN']
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.apply(raw, {'items': [{'key': 'a'}], 'n': 1})

    def test_safe_exponent_is_the_same_numeric_intent(self):
        self.assertEqual(self.apply('set: /n\nnumber: 1e3', {'n': 0}, []), {'n': 1000})
        with self.assertRaisesRegex(ValueError, 'underflow'):
            self.apply('set: /n\nnumber: 1e-1000', {'n': 0}, [])

    def test_ordered_repeated_updates(self):
        self.assertEqual(self.apply('set: /n\nnumber: 4\nchange: /n\nnumber: 1\nset: /n\nnumber: 2', {'n': 0}, []), {'n': 2})

    def test_retired_grouped_contract_cannot_receive_current_semantics(self):
        raw = 'change: /n\nnumber: 1\nset: /n\nnumber: 4'
        self.assertEqual(self.apply(raw, {'n': 0}, []), {'n': 4})
        with self.assertRaisesRegex(ValueError, 'Retired response contract schema-free-intent-v1'):
            legacy.normalize_response(raw, {'n': 0}, 'typed_lines')

    def test_reserved_field_names_remain_valid_array_identities(self):
        for name in ('constructor', '__proto__', 'prototype'):
            with self.subTest(name=name):
                state = {'items': [{'key': name, 'n': 0}]}
                self.assertEqual(self.apply('set: /items/"'+name+'"/n\nnumber: 1', state),
                                 {'items': [{'key': name, 'n': 1}]})
                self.assertEqual(self.apply('remove: /items/"'+name+'"', state), {'items': []})
                self.assertEqual(self.apply('remove: /items/"'+name+'"', {'items': [name]},
                                            [{'path': ['items'], 'id_field': None}]), {'items': []})
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    self.apply('set: /'+name+'\nnumber: 1', {name: 0}, [])
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    self.apply('set: /items/"a"/'+name+'\nnumber: 1',
                               {'items': [{'key': 'a', name: 0}]})

    def test_set_object_field_but_not_whole_collection(self):
        self.assertEqual(self.apply('set: /profile\nobject: {"status":"ready"}',
                                   {'profile': {'status': 'old'}}, []),
                         {'profile': {'status': 'ready'}})
        with self.assertRaises(ValueError):
            self.apply('set: /items\nlist: []', {'items': [{'key': 'a'}]})

    def test_empty_payloads_and_no_change(self):
        self.assertEqual(records('append: /items\nobject:')[0]['value'], {})
        self.assertEqual(records('append: /items\nlist: [1]')[0]['value'], [1])
        self.assertEqual(self.apply('none'), {'items': []})
        with self.assertRaises(ValueError):records(' \n')
