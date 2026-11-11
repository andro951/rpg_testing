"""Shared grammar/IR cases, independent of evaluator state or expected answers."""
import json
from pathlib import Path
import unittest

from intent_parser import IntentError, apply_patch, convert_intent, normalize_intent, parse_intent
from intent_parser.patch import equal

FIXTURES = Path(__file__).resolve().parents[1] / 'intent-parser-js' / 'unified-format-fixtures.json'


class UnifiedIntentGrammarTests(unittest.TestCase):
    def test_shared_format_ir_corpus(self):
        for case in json.loads(FIXTURES.read_text()):
            with self.subTest(name=case['name']):
                if case.get('reject'):
                    with self.assertRaises(IntentError):
                        parse_intent(case['text'], case.get('options'))
                else:
                    self.assertTrue(equal(parse_intent(case['text'], case.get('options')), case['expected']))

    def test_contextual_literal_add(self):
        for text in ('add path:x value:2', 'add x: json:2', 'add: /x\nnumber: 2', 'add ["x"] 2'):
            with self.subTest(text=text):
                ir = parse_intent(text)
                self.assertEqual(ir[0]['semantic'], 'literal_add')
                self.assertEqual(normalize_intent(text, {'x': 1}), [{'op': 'update', 'path': ['x'], 'value': 2}])
                self.assertEqual(normalize_intent(text, {'x': []}), [{'op': 'append', 'path': ['x'], 'value': 2}])
        for alias in ('append', 'insert'):
            with self.subTest(alias=alias), self.assertRaises(IntentError):
                normalize_intent(alias + ' path:x value:2', {'x': 1})
        for text, state in [('add path:[] value:2', 1), ('add path:["x","a"] value:2', {'x': [{'id': 'a'}]}),
                            ('add path:missing value:2', {'x': 1})]:
            with self.subTest(text=text), self.assertRaises(IntentError):
                normalize_intent(text, state)
        ir = parse_intent('add path:x value:2')
        with self.assertRaises(IntentError):
            apply_patch({'x': 1}, ir)
        for semantic, op in [('numeric_delta', 'update'), ('typed_remove', 'remove'), ('unknown', 'append')]:
            with self.subTest(semantic=semantic), self.assertRaises(IntentError):
                convert_intent([{'op': op, 'path': ['x'], 'value': 2, 'semantic': semantic}], {'x': 1})


if __name__ == '__main__':
    unittest.main()
