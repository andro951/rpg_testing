"""New-build evaluator tests are deterministic; no inference or historical writes."""
import copy
import inspect
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from evaluation import array_identities_intent as host
from evaluation import schema_free_intent as retired
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
            'source': {'initial_state': initial, 'array_identities': [
                {'path': ['items'], 'id_field': 'item_id'},
                {'path': ['items', None, 'extra', 'tags'], 'id_field': None},
                {'path': ['places'], 'id_field': None}, {'path': ['empty'], 'id_field': None}]}, 'expected_state': expected, 'variants': [variant]}


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
    def test_v1_has_no_runnable_decoder_or_fresh_configuration(self):
        for action in (retired.configuration, retired.identity_info,
                       lambda: retired.normalize_response('[]', {'x': 1}),
                       lambda: retired.validate_selection({}, {})):
            with self.assertRaisesRegex(ValueError, 'Retired response contract schema-free-intent-v1'):
                action()
        for obsolete in ('apply_patch', '_operation', '_choose', 'resolve'):
            self.assertFalse(hasattr(retired, obsolete), obsolete)

    def test_v1_rejected_before_generation_and_scoring(self):
        test = fixture()
        variant = test['variants'][0]
        variant['result']['evaluator'] = {'version': retired.VERSION, 'fingerprint': 'captured-historical-pin'}
        with self.assertRaisesRegex(ValueError, 'Retired response contract'):
            validate_test(test)
        with patch.object(Backend, 'generate', side_effect=AssertionError('No inference')):
            with self.assertRaisesRegex(ValueError, 'Retired response contract'):
                execute(test, variant, Backend('[]'))
        score = evaluate(test, variant, {'patch': '[]'})
        self.assertEqual(score['status'], 'configuration_error')
        self.assertIsNone(score['exact_match'])
        self.assertEqual(response_expectation(test, variant)['kind'], 'unavailable')

    def test_historical_score_survives_incompatible_text_and_changed_current_parser(self):
        for version in (retired.VERSION, 'array-identities-intent-v1', 'array-identities-intent-v2'):
            for exact in (True, False):
                test = fixture()
                variant = test['variants'][0]
                variant['result']['evaluator'] = {'version': version, 'fingerprint': 'immutable-old-pin'}
                raw = 'Historical response whose grammar is intentionally not replayed.'
                score = {'valid': True, 'exact_match': exact, 'actual_state': {'saved': 'evidence'},
                         'expected_patch_mismatch': True}
                record = {'status': 'completed', 'case_id': version + str(exact), 'model_id': 'historical-model',
                          'test_id': test['id'], 'variant_id': variant['id'], 'repetition': 0,
                          'test_definition': test, 'variant_definition': variant,
                          'score': score, 'outputs': {'patch': raw}, 'calls': [{'text': raw}]}
                snapshot = copy.deepcopy(record)
                with patch('evaluation.core.patch_checks', side_effect=AssertionError('No regrade')):
                    assessment = assess_record(record)
                    feedback = summarize(record)
                    matrix = build_matrix([record], [], 'current-fingerprint')
                self.assertEqual(assessment['objective_outcome'], 'PASS' if exact else 'FAIL')
                self.assertEqual(assessment['original_score'], score)
                self.assertEqual(assessment['raw_outputs']['patch'], raw)
                self.assertEqual(feedback['assessment_mode'], 'saved_score_only')
                self.assertIn('no regrading', feedback['reason'])
                self.assertEqual(matrix['records'][record['case_id']]['outcome'], 'pass' if exact else 'fail')
                self.assertEqual(record, snapshot)

    def test_explicit_offline_revalidation_reports_retired_contract_without_regrade(self):
        from evaluation.__main__ import revalidate
        test = fixture()
        variant = test['variants'][0]
        variant['result']['evaluator'] = {'version': retired.VERSION, 'fingerprint': 'captured-pin'}
        record = {'case_id': 'retired', 'test_id': test['id'], 'variant_id': variant['id'],
                  'test_definition': test, 'variant_definition': variant, 'score': {'exact_match': True}}
        before = copy.deepcopy(record)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'evidence'
            source.mkdir()
            with patch('evaluation.__main__.evidence_records', return_value=iter([record])), \
                    patch('evaluation.__main__.assess_record', side_effect=AssertionError('No retired regrade')):
                result = revalidate(source, Path(folder) / 'derived', None, 'dot-separators-v2')
        self.assertEqual(result['problems'], [])
        self.assertEqual(result['assessed_records'], 0)
        self.assertEqual(result['not_applicable'][0]['contract_status'], 'retired')
        self.assertIn('unsupported', result['not_applicable'][0]['reason'])
        self.assertEqual(record, before)

    def test_current_report_verdict_uses_live_intent_and_diagnostic_patch_mismatch(self):
        test = fixture()
        validate_test(test)
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


if __name__ == '__main__':
    unittest.main()
