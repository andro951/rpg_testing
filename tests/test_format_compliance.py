"""Independent strict syntax checks. Synthetic tests only, never model inference."""
import copy
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluation.format_compliance import FORMATS, validate
from evaluation.core import assess
from prompt_builder.builder import compile_test, discover, load_case
from prompt_builder.reference_output import encode
from workbench.workflows import evaluate, execute
from tests.test_current_live_intent import Backend


class FormatComplianceTests(unittest.TestCase):
    def check(self, form, raw, expected=True):
        result = validate(raw, form)
        self.assertIs(result['compliant'], expected, (form, raw, result))
        self.assertFalse(result['affects_intent_verdict'])
        return result

    def test_all_current_reference_responses(self):
        count = 0
        for case_name in discover()['test_cases']:
            case = load_case(case_name)
            for form in FORMATS:
                with self.subTest(case=case_name, form=form):
                    raw = encode(case['starting_data'], case['expected_patch'], form, case['array_identities'])
                    self.check(form, raw)
                    count += 1
        self.assertEqual(count, 126)

    def test_json_is_exact_not_repaired(self):
        good = '[{"op":"replace","path":"note","value":"new"}]'
        for form in ('json_dot', 'json_slash'):
            raw = good if form == 'json_dot' else good.replace('"note"', '"/note"')
            self.check(form, raw)
            self.check(form, ' \n' + raw + '\t')
            for wrong in ('```json\n'+raw+'\n```', raw[1:], raw[:-1], raw[1:-1], 'Answer: '+raw,
                          raw.replace('replace', 'set'), raw.replace('"op":', '"extra":0,"op":'),
                          raw.replace('"op":', '"op":"remove","op":'), raw.replace('"new"', 'NaN'),
                          raw.replace('"new"', '{"a":1,"a":2}'), raw.replace('"new"', "'new'"),
                          raw[:-1]+',]', 'none', '{}', '', '[null]', '[{"op":[]}]'):
                with self.subTest(form=form, raw=wrong):
                    self.check(form, wrong, False)

    def test_paths_use_requested_lexical_syntax_only(self):
        for path in ('items.a%2Eb.name', '%_', 'a.%E2%98%83', 'a-b.c_d'):
            self.check('json_dot', json.dumps([{'op':'remove','path':path}]))
        for path in ('/items/a', '.items', 'items.', 'a..b', 'a."b"', 'a.b c', 'a.%GG', 'a.%FF', 'a.%'):
            self.check('json_dot', json.dumps([{'op':'remove','path':path}]), False)
        for path in ('', '/', '/items/"a/b"/value', '/a~1b/~0', '/items/""', '/unknown/01', '/unknown/unquoted-id', '/a"b', '/field\nwith\ttab', '/line\u2028separator'):
            self.check('json_slash', json.dumps([{'op':'remove','path':path}]))
        for path in ('items.a', '/a~2b', '/items/"a"extra', '/items/"unclosed'):
            self.check('json_slash', json.dumps([{'op':'remove','path':path}]), False)
        for path in ('/items/""', '/items/"constructor"', '/field with spaces.and.dots'):
            self.check('typed_lines', 'remove: '+path)
        for path in ('', '/', '/a//b', '/a/', '/a/constructor', '/prototype', '/__proto__'):
            self.check('typed_lines', 'remove: '+path, False)

    def test_json_numeric_syntax_has_no_binary_float_or_integer_size_limit(self):
        for number in ('1e10000', '1e-10000', '9' * 5000):
            self.check('json_dot', '[{"op":"replace","path":"count","value":' + number + '}]')
        self.check('typed_lines', 'set: /count\nnumber: ' + '9' * 5000)

    def test_json_operation_key_sets(self):
        for op, fields in [('replace',{'value':1}), ('add',{'value':1}), ('remove',{}),
                           ('move',{'from':'source'}), ('copy',{'from':'source'})]:
            raw = {'op':op,'path':'target',**fields}
            self.check('json_dot',json.dumps([raw]))
            self.check('json_dot',json.dumps([{**raw,'extra':None}]),False)
            self.check('json_dot',json.dumps([{**raw,'path':[]}]),False)

    def test_path_list_and_record_boundaries(self):
        for raw in ('set [a, b]: "value"', 'append [a]: {"id":"x"}', 'remove [a, %_]',
                    'move [a, x] -> [b]', 'copy [a, x] -> [b]', 'set []: null'):
            self.check('path_list',raw)
        for raw in ('set ["a"]: 1', 'set [a b]: 1', 'remove [a]: null', 'set [a]:',
                    'move [a] -> [b]: 1', 'set [a]: {"x":1}\n\nremove [b]', 'Set [a]: 1'):
            self.check('path_list',raw,False)
        for form, raw in [('typed_lines','set: /a\nnumber: 1\n\nremove: /b')]:
            self.check(form,raw)
            self.check(form,raw.replace('\n', '\r\n')+'\r\n')
            for wrong in (raw.replace('\n', '\n\n',1), raw+'\nvalue: 2', ' '+raw, raw.upper()):
                self.check(form,wrong,False)
        self.check('typed_lines','copy: /source/"x"\nto: /destination')
        for form,raw in [('typed_lines','copy: /source')]:
            self.check(form,raw,False)

    def test_literal_escape_contracts_and_data_are_not_inferred(self):
        for raw in ('set a: text:', 'set a: text:"quoted"', 'set a: text:  leading',
                    r'set a: text:a\n\r\t\s\\\"', 'append a: json:{"x":1}'):
            self.check('literal_line',raw)
        for raw in ('set a: text:trailing ', r'set a: text:\q', 'set a: text:bad\\', 'set a: json:"string"',
                    'set a: text:literal\ttab'):
            self.check('literal_line',raw,False)
        for raw in ('set a: text:|','set a: text:  value  |','set a: text:a|b||',r'set a: text:literal \\n|',
                    'set a: text:"copy: /items to: /elsewhere"|'):
            self.check('end_marked_line',raw)
        for raw in ('set a: text:no marker',r'set a: text:\s|',r'set a: text:\"|',r'set a: text:\||',
                    'move a -> b|'):
            self.check('end_marked_line',raw,False)

    def test_typed_labels_are_exact_without_application(self):
        for value in ('text:', 'text: {"x":1}', 'text: "literal"', 'text: literal\\n',
                      'number: +1','number: -0.5','boolean: true','boolean: false','null:',
                      'object:','list:','object: {"x":1}','list: [1,2]'):
            self.check('typed_lines','set: /missing\n'+value)
        for value in ('number: 1e2','number: 01','number: .5','number: 1.','number: NaN',
                      'boolean: True','null: ','null: null','object: []','list: {}','object: ', 'value: 1'):
            self.check('typed_lines','set: /missing\n'+value,False)
        self.check('typed_lines','change: /unknown\nnumber: 1')
        self.check('typed_lines','change: /unknown\ntext: 1',False)
        # Repeated operations and wrong targets are semantic questions, not syntax.
        self.check('typed_lines','remove: /unknown\nremove: /unknown')

    def test_no_change_and_no_special_cases(self):
        for form in FORMATS:
            noop = '[]' if form.startswith('json_') else 'none'
            self.check(form,noop)
            for bad in ('NONE',' none ','\ufeff'+noop,'```\n'+noop+'\n```','', '\n', noop+'\nexplanation'):
                self.check(form,bad,False)
        self.assertIsNone(validate('anything','free_format')['compliant'])
        self.assertEqual(validate('anything','free_format')['status'],'not_applicable')
        self.assertEqual(validate('anything','unknown')['status'],'not_evaluated')
        with patch('evaluation.output_formats.parse_intent_with_diagnostics',side_effect=AssertionError('Must not use intent parser')):
            self.check('path_list','set [unknown]: "unknown"')

    def test_same_response_has_independent_semantic_and_format_results(self):
        test = compile_test('update_field','json_dot',input_formats=['normal_json'])
        variant = test['variants'][0]
        raw = encode(test['source']['initial_state'],variant['expected_patch'],'json_dot',test['source']['array_identities'])
        original = copy.deepcopy(test)
        for response, semantic, compliance in ((raw,True,True),('```json\n'+raw+'\n```',True,False),
                                                ('[]',False,True),('nonsense',False,False)):
            with self.subTest(response=response):
                backend = Backend(response)
                result = execute(test,variant,backend)
                self.assertEqual(len(backend.calls),1)
                self.assertEqual(result['outputs']['patch'],response)
                score = result['score']
                self.assertIs(score['exact_match'],semantic,score)
                self.assertIs(score['format_compliance']['compliant'],compliance,score)
                report = assess(test,variant,{'patch':response})
                checks = [c for c in report['checks'] if c['code']=='format.compliance']
                self.assertEqual(len(checks),1)
                self.assertFalse(checks[0]['affects_verdict'])
                self.assertEqual(report['objective_outcome'],'PASS' if semantic else 'FAIL')
        self.assertEqual(test,original)

    def test_mock_run_records_both_metrics_and_resume_keeps_original_bytes(self):
        from workbench.controller import Controller
        from workbench.demo_native import DemoNative
        from workbench.domain import write_json
        test = compile_test('update_field', 'json_dot', input_formats=['normal_json'])
        variant = test['variants'][0]
        raw = encode(test['source']['initial_state'], variant['expected_patch'], 'json_dot', test['source']['array_identities'])
        response = '```json\n' + raw + '\n```'
        calls = []
        def generate(backend, messages, settings, schema, cache='default', cancel=None):
            calls.append(messages)
            return {'text': response, 'finish_reason': 'stop', 'cached_tokens': 0}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / 'test_specs/test.json', test)
            app = Controller(root, True)
            with patch.object(DemoNative, 'generate', generate):
                selection = {'model_id': 'demo-2b', 'test_id': test['id']}
                app.run(selection=selection)
                records = app.store.all()
                self.assertEqual(len(records), 1, app.message)
                score = records[0]['score']
                self.assertTrue(score['exact_match'])
                self.assertFalse(score['format_compliance']['compliant'])
                self.assertEqual(records[0]['outputs']['patch'], response)
                snapshots = {p: p.read_bytes() for p in app.store.root.rglob('*.json')}
                app.run(selection=selection)
                self.assertEqual(len(calls), 1)
                self.assertEqual(snapshots, {p: p.read_bytes() for p in app.store.root.rglob('*.json')})

    def test_oracle_does_not_change_format_compliance(self):
        test = compile_test('update_field','json_dot',input_formats=['normal_json'])
        variant = test['variants'][0]
        before = evaluate(test,variant,{'patch':'[]'})['format_compliance']
        test['expected_state'] = copy.deepcopy(test['source']['initial_state'])
        variant['expected_patch'] = []
        self.assertEqual(evaluate(test,variant,{'patch':'[]'})['format_compliance'],before)


if __name__ == '__main__':
    unittest.main()
