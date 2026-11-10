"""New-build evaluator tests are deterministic; no inference or historical writes."""
import copy
import inspect
import json
import shutil
import subprocess
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluation import schema_free_intent as host
from evaluation.core import assess_record
from reporting.feedback import response_expectation, summarize
from reporting.matrix import build_matrix
from workbench.domain import validate_test
from workbench.workflows import evaluate, execute


def fixture(output_format='json_dot'):
    initial = {'items': [{'item_id': 'item.a', 'count': 1, 'name': 'old'},
                         {'item_id': 'item-b', 'count': 3, 'extra': {'tags': ['b', 'a']}}],
               'places': ['north', 'south'], 'empty': [], 'note': 'old'}
    expected = copy.deepcopy(initial)
    expected['items'][0]['count'] = 2
    variant = {'id': 'normal_json', 'prompt_style': 'direct_text_v1',
               'steps': [{'id': 'patch', 'type': 'generate', 'prompt': 'Change the count to 2.', 'output': {'type': 'text'}}],
               'result': {'step': 'patch', 'representation': 'dot_patch_v1',
                          'output_format': output_format, 'evaluator': host.configuration()},
               'expected_patch': [{'op': 'replace', 'path': 'items.item%2Ea.count', 'value': 2}]}
    return {'schema_version': 2, 'id': 'schema-free-example', 'workflow': 'steps', 'enabled': True,
            'repetitions': 1, 'timeout_seconds': 120, 'instructions': 'Use unique IDs; array order does not matter.',
            'source': {'initial_state': initial}, 'expected_state': expected, 'variants': [variant]}


class Backend:
    supports_schema = False
    supports_cache = False
    def __init__(self, raw):
        self.raw = raw
    def generate(self, messages, settings, schema, cache, cancel):
        if schema is not None:
            raise AssertionError('No per-case or output constraint schema')
        return {'text': self.raw, 'finish_reason': 'stop'}


def record_for(test, raw):
    variant = test['variants'][0]
    result = execute(test, variant, Backend(raw))
    return {**result, 'case_id': 'schema-free-record', 'status': 'completed', 'model_id': 'mock-model',
            'test_id': test['id'], 'variant_id': variant['id'], 'repetition': 0,
            'test_definition': test, 'variant_definition': variant,
            'provenance': {'workflow_code': 'test-fingerprint'}}


class SchemaFreeIntentTests(unittest.TestCase):
    def score(self, raw, test=None):
        test = test or fixture()
        return evaluate(test, test['variants'][0], {'patch': raw})

    def test_opt_in_accepts_without_schema_and_default_retains_requirement(self):
        test = fixture()
        validate_test(test)
        self.assertNotIn('state_schema', test)
        del test['variants'][0]['result']['evaluator']
        with self.assertRaisesRegex(ValueError, 'predefined state_schema'):
            validate_test(test)

    def test_source_pin_is_portable_but_runtime_version_is_recorded(self):
        test=fixture();original=host.configuration()
        with patch.object(host.platform,'python_version',return_value='3.12.99'):
            self.assertEqual(host.configuration(),original)
            validate_test(test)
            result=host.normalize_response(json.dumps(test['variants'][0]['expected_patch']),test['source']['initial_state'])
            self.assertEqual(result['runtime']['python_version'],'3.12.99')
            self.assertEqual(host.identity_info()['python_version'],'3.12.99')
    def test_normalizer_boundary_has_no_expected_schema_prompt_or_task(self):
        self.assertEqual(list(inspect.signature(host.normalize_response).parameters), ['raw', 'initial_state', 'output_format'])
        test = fixture()
        raw = json.dumps(test['variants'][0]['expected_patch'])
        with patch.object(host, 'normalize_response', wraps=host.normalize_response) as normalizer:
            record = record_for(test, raw)
        self.assertEqual(normalizer.call_count, 1)
        self.assertEqual(normalizer.call_args.args, (raw, test['source']['initial_state'], 'json_dot'))
        self.assertTrue(record['score']['exact_match'])
        self.assertFalse(record['score']['expected_patch_mismatch'])
        self.assertEqual(record['outputs']['patch'], raw)
        self.assertTrue(all('Database structure' not in message['content'] for message in record['calls'][0]['messages']))

    def test_valid_extra_redundant_operations_pass_with_separate_mismatch(self):
        test = fixture()
        # Legacy required_ops cannot accidentally restore exact-op gating.
        test['variants'][0]['result']['required_ops'] = ['replace']
        test['variants'][0]['result']['response_schema'] = {'type': 'array', 'maxItems': 0}
        raw = json.dumps([{'op': 'replace', 'path': 'note', 'value': 'temporary'},
                          {'op': 'replace', 'path': 'note', 'value': 'old'},
                          *test['variants'][0]['expected_patch'],
                          *test['variants'][0]['expected_patch']])
        score = self.score(raw, test)
        self.assertTrue(score['valid'], score)
        self.assertTrue(score['exact_match'], score)
        self.assertFalse(score['patch_ops_match'])
        self.assertTrue(score['expected_patch_mismatch'])
        self.assertEqual(score['actual_state'], test['expected_state'])

    def test_wrong_final_state_fails_regardless_of_reference_patch_match(self):
        test = fixture()
        raw = '[{"op":"replace","path":"items.item%2Ea.count","value":99}]'
        self.assertFalse(self.score(raw, test)['exact_match'])
        test['variants'][0]['expected_patch'][0]['value'] = 99
        score = self.score(raw, test)
        self.assertFalse(score['exact_match'])
        self.assertIsNone(score['expected_patch_mismatch'])
        self.assertIn('does not produce', score['expected_patch_diagnostic'])

    def test_missing_broken_or_alternative_reference_cannot_change_pass(self):
        test = fixture()
        raw = json.dumps(test['variants'][0]['expected_patch'])
        for reference in (None, [{'op': 'remove', 'path': 'missing'}],
                          [{'op': 'replace', 'path': 'note', 'value': 'old'}, *test['variants'][0]['expected_patch']]):
            chosen = copy.deepcopy(test)
            chosen['variants'][0]['expected_patch'] = reference
            self.assertTrue(self.score(raw, chosen)['exact_match'])
        del test['variants'][0]['expected_patch']
        self.assertTrue(self.score(raw, test)['exact_match'])

    def test_normalization_unchanged_when_oracle_changes(self):
        test = fixture()
        raw = json.dumps(test['variants'][0]['expected_patch'])
        original = self.score(raw, test)
        test['expected_state']['items'][0]['count'] = 9
        changed = self.score(raw, test)
        self.assertEqual(original['evaluation'], changed['evaluation'])
        self.assertFalse(changed['exact_match'])

    def test_order_insensitive_at_all_depths_and_preserves_actual_order(self):
        test = fixture()
        test['expected_state']['items'].reverse()
        test['expected_state']['places'].reverse()
        test['expected_state']['items'][0]['extra']['tags'].reverse()
        score = self.score(json.dumps(test['variants'][0]['expected_patch']), test)
        self.assertTrue(score['exact_match'], score)
        self.assertEqual(score['correct_changes'], 1)
        self.assertEqual(score['actual_state']['places'], ['north', 'south'])
        self.assertEqual(score['actual_state']['items'][0]['item_id'], 'item.a')

    def test_remove_readd_reorders_but_correct_state_passes(self):
        test = fixture()
        raw = json.dumps([{'op': 'remove', 'path': 'places.north'},
                          {'op': 'add', 'path': 'places', 'value': 'north'}, *test['variants'][0]['expected_patch']])
        score = self.score(raw, test)
        self.assertTrue(score['exact_match'], score)
        self.assertTrue(score['expected_patch_mismatch'])

    def test_no_change_redundant_update_passes_despite_empty_reference(self):
        test = fixture()
        test['expected_state'] = copy.deepcopy(test['source']['initial_state'])
        test['variants'][0]['expected_patch'] = []
        self.assertTrue(self.score('[]', test)['exact_match'])
        score = self.score('[{"op":"replace","path":"note","value":"old"}]', test)
        self.assertTrue(score['exact_match'])
        self.assertTrue(score['expected_patch_mismatch'])

    def test_heterogeneous_shapes_complete_additions_and_new_nested_arrays(self):
        initial = {'records': [{'id': 'one', 'x': 1}, {'id': 'two', 'totally_different': True}], 'new': []}
        patch_value = {'id': 'three', 'nested': [{'child_id': 'child', 'items': ['x', 'y']}], 'extra': None}
        raw = json.dumps([{'op': 'add', 'path': 'records', 'value': patch_value},
                          {'op': 'add', 'path': 'new', 'value': {'person_id': 'new', 'fields': {'a': 1}}},
                          {'op': 'replace', 'path': 'new.new.fields.a', 'value': 'changed type'},
                          {'op': 'remove', 'path': 'records.three.nested.child.items.x'}])
        output = host.normalize_response(raw, initial)
        self.assertEqual(output['final_state']['new'][0]['fields']['a'], 'changed type')
        self.assertEqual(output['final_state']['records'][-1]['nested'][0]['items'], ['y'])
        self.assertEqual(initial['new'], [])

    def test_empty_array_does_not_borrow_expected_type(self):
        test = fixture()
        raw = '[{"op":"add","path":"empty","value":"new"}]'
        normalized = host.normalize_response(raw, test['source']['initial_state'])
        self.assertEqual(normalized['final_state']['empty'], ['new'])
        test['expected_state']['empty'] = [{'unusable': 'not a declared identity'}]
        self.assertEqual(host.normalize_response(raw, test['source']['initial_state']), normalized)

    def test_id_like_fields_only_and_no_ambiguity_guessing(self):
        for state in ({'items': [{'name': 'unique', 'count': 1}]},
                      {'items': [{'id': 'a', 'other_id': 'b'}]},
                      {'items': [{'id': 'a'}, {'id': 'a'}]},
                      {'items': [{'id': 'a'}, 'b']}, {'items': [[1]]},
                      {'items': [1, '1']}, {'items': [True, 'true']}, {'items': [1, 1.0]}):
            with self.subTest(state=state), self.assertRaises(ValueError):
                host.normalize_response('[]', state)
        self.assertEqual(host.identity({'person_id': 'p', 'name': 'a'}, [{'person_id': 'p', 'name': 'a'}]), 'p')

    def test_rejects_positions_duplicate_ids_and_invalid_operation_roles_atomically(self):
        initial = fixture()['source']['initial_state']
        snapshot = copy.deepcopy(initial)
        for raw in ('[{"op":"replace","path":"items.0.count","value":2}]',
                    '[{"op":"replace","path":"/items/0/count","value":2}]',
                    '[{"op":"add","path":"items","value":{"item_id":"item.a"}}]',
                    '[{"op":"remove","path":"items.item%2Ea.count"}]',
                    '[{"op":"replace","path":"items","value":[]}]',
                    '[{"op":"replace","path":"note","value":"x"},{"op":"remove","path":"missing"}]',
                    '[{"op":"replace","path":"missing","value":2}]',
                    '[{"op":"move","from":"items.item-b","path":"empty"}]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                host.normalize_response(raw, initial)
            self.assertEqual(initial, snapshot)

    def test_literal_separator_ambiguity_never_uses_oracle(self):
        initial = {'a.b': 1, 'a': {'b': 2}}
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            host.normalize_response('update path:"a.b" value:3', initial)
        self.assertEqual(host.normalize_response('update path:"a%2Eb" value:3', initial)['final_state']['a.b'], 3)
        self.assertEqual(host.normalize_response('update path:["a.b"] value:3', initial)['final_state']['a.b'], 3)

    def test_all_format_choices_are_real_readers(self):
        responses = {
            'json_dot': '[{"op":"replace","path":"items.item%2Ea.count","value":2}]',
            'json_slash': '[{"op":"replace","path":"/items/\\"item.a\\"/count","value":2}]',
            'path_list': 'set [items, item%2Ea, count]: 2',
            'literal_line': 'set items.item%2Ea.count: json:2',
            'end_marked_line': 'set items.item%2Ea.count: json:2',
            'two_line_text': 'set: items.item%2Ea.count\nvalue: 2',
            'free_format': 'update path:"items.item%2Ea.count" value:2',
            'typed_lines': 'set: /note\ntext: new'}
        self.assertEqual(set(responses), set(host.OUTPUT_FORMATS))
        for output_format, raw in responses.items():
            test = fixture(output_format)
            if output_format == 'typed_lines':
                test['expected_state'] = copy.deepcopy(test['source']['initial_state'])
                test['expected_state']['note'] = 'new'
                test['variants'][0]['expected_patch'] = [{'op': 'replace', 'path': 'note', 'value': 'new'}]
            with self.subTest(output_format=output_format):
                validate_test(test)
                score = self.score(raw, test)
                self.assertTrue(score['exact_match'], score)
                self.assertFalse(score['expected_patch_mismatch'], score)
                self.assertEqual(response_expectation(test, test['variants'][0])['kind'], 'reference')

    def test_text_escapes_and_end_markers_preserve_values(self):
        initial = {'note': '', 'records': []}
        for output_format, raw, value in (
            ('literal_line', r'set note: text: a\n\t\\n\s\s', ' a\n\t\\n  '),
            ('end_marked_line', r'set note: text: a\n\t\\n  ||', ' a\n\t\\n  |'),
            ('literal_line', 'set note: text:', ''),
            ('end_marked_line', 'set note: text:|', ''),
            ('literal_line', 'set note: text:"quoted":value', '"quoted":value')):
            with self.subTest(raw=raw):
                actual = host.normalize_response(raw, initial, output_format)
                self.assertEqual(actual['final_state']['note'], value)
        for mode, raw in (('end_marked_line', 'set note: text:missing marker'),
                          ('literal_line', 'set note: json:"a string"'),
                          ('literal_line', r'set note: text:bad\q'),
                          ('end_marked_line', r'set note: text:bad\s|'),
                          ('path_list', 'remove [records]: null')):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                host.normalize_response(raw, initial, mode)

    def test_slash_typed_selectors_escaped_properties_and_no_positions(self):
        initial = {'a/b': [{'id': 'x/y', 'a~b': 1}], 'numbers': [42, 99]}
        raw = json.dumps([{'op': 'replace', 'path': '/a~1b/"x/y"/a~0b', 'value': 2},
                          {'op': 'remove', 'path': '/numbers/42'}])
        actual = host.normalize_response(raw, initial, 'json_slash')['final_state']
        self.assertEqual(actual, {'a/b': [{'id': 'x/y', 'a~b': 2}], 'numbers': [99]})
        for path in ('/numbers/0', '/numbers/"42"'):
            with self.assertRaises(ValueError):
                host.normalize_response(json.dumps([{'op': 'remove', 'path': path}]), initial, 'json_slash')

    def test_typed_lines_retains_original_supported_subset_and_group_order(self):
        initial = {'count': 1, 'tags': ['a'], 'people': [{'person_id': 'p', 'name': 'old'}]}
        result = host.normalize_response('change: /count\nnumber: 2\nset: /count\nnumber: 5\nappend: /tags\ntext: b', initial, 'typed_lines')
        self.assertEqual(result['final_state']['count'], 7)
        self.assertEqual(result['final_state']['tags'], ['a', 'b'])
        for raw in ('set: /people/p/name\ntext: new', 'append: /people\nobject:', 'remove: /tags/a'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                host.normalize_response(raw, initial, 'typed_lines')

    def test_free_prose_reports_unknown_semantics_without_model_inference(self):
        test = fixture('free_format')
        score = self.score('The first sword now has two charges.', test)
        self.assertFalse(score['valid'])
        self.assertIn('semantic correctness is unknown', score['error'])
        self.assertEqual(score['evaluation']['semantic_status'], 'unknown')
        self.assertEqual(score['status'], 'parser_gap')
        self.assertIsNone(score['exact_match'])
        record = record_for(test, 'The first sword now has two charges.')
        report = assess_record(record)
        self.assertEqual(report['objective_outcome'], 'UNSCORED')
        self.assertEqual(report['steps'][0]['semantic_outcome'], 'UNSCORED')
        matrix = build_matrix([record], [test], 'test-fingerprint')
        self.assertEqual(matrix['records'][record['case_id']]['outcome'], 'parser_gap')
        self.assertIsNone(score['expected_patch_mismatch'])

    def test_no_change_spellings_by_format_and_empty_rejection(self):
        initial = {'x': 1}
        for mode in host.OUTPUT_FORMATS:
            raw = '[]' if mode in ('json_dot', 'json_slash') else 'none'
            self.assertEqual(host.normalize_response(raw, initial, mode)['final_state'], initial)
            with self.assertRaises(ValueError):
                host.normalize_response(' ', initial, mode)

    def test_stale_or_unknown_selection_is_rejected(self):
        test = fixture()
        test['variants'][0]['result']['evaluator']['fingerprint'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'stale'):
            validate_test(test)
        test = fixture('not-a-format')
        with self.assertRaisesRegex(ValueError, 'output_format'):
            validate_test(test)

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the results-table JavaScript test')
    def test_patch_mismatch_marker_preserves_color_counts_and_score(self):
        source = Path(__file__).resolve().parents[1] / 'reporting' / 'matrix.js'
        script = r"""
const fs = require('fs');
const assert = require('assert');
function element() { return {style: {}, dataset: {}, children: [], title: '',
    setAttribute(name, value) { this[name] = value; }, addEventListener() {}}; }
global.StatisticsReport = {
    Data: {matrix: {records: {one: {outcome: 'pass', metadata: {score: {expected_patch_mismatch: true}}}}}},
    Cell(row, text) {const child = element(); child.textContent = text; row.children.push(child); return child;},
    Element(tag, parent, text) {const child = element(); child.tag = tag; child.textContent = text; parent.children.push(child); return child;}
};
const body = fs.readFileSync(process.argv[1], 'utf8');
eval(body + `
 const row = element();
 ResultsMatrix.Cell(row, [{ids:['one'], primary_ids:['one'], reference_ids:[]}], 'example', true);
 const cell = row.children[0];
 assert.equal(cell.dataset.outcome, 'pass');
 assert.equal(cell.dataset.patchMismatch, 'true');
 assert(cell.title.includes('1 PASS / 0 FAIL'));
 assert(cell.title.includes('Diagnostic only'));
 assert.equal(cell.children.find(x => x.tag === 'span').textContent, '≠');
 assert.equal(cell.children.find(x => x.tag === 'button').textContent, '100%');
 assert.equal(ResultsMatrix.Counts([{ids:['one'], primary_ids:['one'], reference_ids:[]}]).pass, 1);
`);
"""
        subprocess.run([shutil.which('node'), '-e', script, str(source)], check=True, capture_output=True, text=True)

    def test_report_verdict_and_totals_ignore_reference_mismatch(self):
        test = fixture()
        raw = json.dumps([{'op': 'replace', 'path': 'note', 'value': 'old'}, *test['variants'][0]['expected_patch']])
        record = record_for(test, raw)
        assessment = assess_record(record)
        self.assertEqual(assessment['objective_outcome'], 'PASS', assessment)
        self.assertEqual(assessment['score_comparison'], 'agrees')
        self.assertEqual(assessment['steps'][0]['semantic_outcome'], 'PASS')
        comparison = next(check for check in assessment['checks'] if check['code'] == 'patch.expected_match')
        self.assertEqual(comparison['status'], 'failed')
        self.assertFalse(comparison['affects_verdict'])
        feedback = summarize(record)
        self.assertTrue(feedback['expected_patch_mismatch'])
        self.assertEqual(feedback['objective_outcome'], 'PASS')
        matrix = build_matrix([record], [test], 'test-fingerprint')
        self.assertEqual(matrix['records'][record['case_id']]['outcome'], 'pass')
        self.assertTrue(matrix['records'][record['case_id']]['metadata']['score']['expected_patch_mismatch'])


if __name__ == '__main__':
    unittest.main()
