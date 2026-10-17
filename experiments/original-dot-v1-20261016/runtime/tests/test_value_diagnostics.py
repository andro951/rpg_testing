import copy
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from evaluation.core import assess
from reporting.feedback import response_expectation, summarize
from workbench.workflows import evaluate


def contracts():
    element = {'type': 'object', 'properties': {'key': {'type': 'string'}, 'count': {'type': 'number'}},
               'required': ['key', 'count'], 'additionalProperties': False}
    collection = {'type': 'array', 'x-id-field': 'key', 'items': element}
    schema = {'type': 'object', 'properties': {'elements': collection, 'storage': collection},
              'required': ['elements', 'storage'], 'additionalProperties': False}
    before = {'elements': [{'key': 'element-a', 'count': 2}], 'storage': []}
    after = {'elements': [{'key': 'element-a', 'count': 9}], 'storage': []}
    test = {'id': 'diagnostic-example', 'source': {'initial_state': before}, 'expected_state': after, 'state_schema': schema}
    variant = {'id': 'example', 'result': {'step': 'patch', 'representation': 'value_patch', 'required_ops': ['replace']}}
    return test, variant


class ValueDiagnosticTests(unittest.TestCase):
    def test_unquoted_selector_explains_exact_json_encoding_without_repair(self):
        test, variant = contracts()
        raw = json.dumps([{'op': 'replace', 'path': '/elements/element-a/count', 'value': 9}])
        original = copy.deepcopy(test)
        report = assess(test, variant, {'patch': raw})
        failure = next(c for c in report['checks'] if c['code'] == 'patch.application_failed')
        self.assertIn('string selector', failure['explanation'])
        self.assertIn(json.dumps({'path': '/elements/"element-a"/count'}), failure['explanation'])
        self.assertIn('not repaired or applied', failure['explanation'])
        self.assertEqual(report['objective_outcome'], 'FAIL')
        self.assertEqual(next(c['status'] for c in report['checks'] if c['code'] == 'state.final'), 'not_evaluated')
        self.assertFalse(evaluate(test, variant, {'patch': raw})['exact_match'])
        self.assertEqual(test, original)

    def test_copy_hint_identifies_from_field_and_keeps_failure(self):
        test, variant = contracts()
        variant['result']['required_ops'] = ['copy']
        raw = json.dumps([{'op': 'copy', 'from': '/elements/element-a', 'path': '/storage'}])
        report = assess(test, variant, {'patch': raw})
        failure = next(c for c in report['checks'] if c['code'] == 'patch.application_failed')
        self.assertIn('from: string selector', failure['explanation'])
        self.assertEqual(report['objective_outcome'], 'FAIL')

    def test_no_speculative_quote_hint_for_missing_or_numeric_selector(self):
        test, variant = contracts()
        for selector in ('missing', '42', '"missing"'):
            with self.subTest(selector=selector):
                raw = json.dumps([{'op': 'replace', 'path': '/elements/' + selector + '/count', 'value': 9}])
                report = assess(test, variant, {'patch': raw})
                explanation = next(c['explanation'] for c in report['checks'] if c['code'] == 'patch.application_failed')
                self.assertNotIn('Encode this field', explanation)
                self.assertEqual(report['objective_outcome'], 'FAIL')

    def test_remove_collection_explains_path_and_from_roles(self):
        test, variant = contracts()
        variant['result']['required_ops'] = ['remove']
        raw = json.dumps([{'op': 'remove', 'path': '/elements', 'from': 'element-a'}])
        report = assess(test, variant, {'patch': raw})
        reason = next(c['explanation'] for c in report['checks'] if c['code'] == 'patch.application_failed')
        self.assertIn('must select one element', reason)
        self.assertIn('from field does not select', reason)
        self.assertEqual(report['objective_outcome'], 'FAIL')

    def test_no_change_names_empty_response_even_with_another_path_failure(self):
        test, variant = contracts()
        test['expected_state'] = copy.deepcopy(test['source']['initial_state'])
        variant['result']['required_ops'] = []
        raw = json.dumps([{'op': 'replace', 'path': '/elements/element-a/count', 'value': 2}])
        report = assess(test, variant, {'patch': raw})
        self.assertIn('Return []', report['primary_reason'])
        self.assertEqual(report['objective_outcome'], 'FAIL')

    def test_reference_response_is_validated_and_states_are_separate(self):
        test, variant = contracts()
        patch = [{'op': 'replace', 'path': '/elements/"element-a"/count', 'value': 9}]
        variant['expected_patch'] = patch
        record = {'test_definition': test, 'variant_definition': variant, 'status': 'completed',
                  'outputs': {'patch': json.dumps(patch)}, 'score': {'exact_match': True, 'actual_state': test['expected_state']}}
        result = summarize(record)
        reference = result['expected_response']
        self.assertEqual(json.loads(reference['text']), patch)
        self.assertIn('equivalent valid responses', reference['label'])
        self.assertEqual(result['validation_states']['expected'], test['expected_state'])
        self.assertEqual(result['validation_states']['actual'], test['expected_state'])
        self.assertTrue(result['validation_states']['actual_available'])
        variant['expected_patch'][0]['value'] = 999
        self.assertEqual(response_expectation(test, variant)['kind'], 'unavailable')

    def test_fixture_reference_must_pass_captured_contract_and_does_not_invent_response(self):
        root = Path(__file__).resolve().parents[1]
        test = json.loads((root / 'test_specs/db_v3_update_record__value_patch.json').read_text())
        variant = next(v for v in test['variants'] if v['id'] == 'full_paths')
        reference = response_expectation(test, variant)
        self.assertEqual(reference['kind'], 'reference')
        self.assertTrue(evaluate(test, variant, {'patch': reference['text']})['exact_match'])
        test['expected_state']['items'][1]['count'] = 999
        self.assertEqual(response_expectation(test, variant)['kind'], 'unavailable')

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable for report rendering smoke')
    def test_render_expected_response_and_validation_states_in_separate_blocks(self):
        root = Path(__file__).resolve().parents[1]
        script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const element = tag => ({tag, children: [], style: {}, dataset: {}, attributes: {}, textContent: '',
    append(x) {this.children.push(x);}, replaceChildren() {this.children = [];},
    setAttribute(k,v) {this.attributes[k] = v;}});
const document = {createElement: element, getElementById: () => ({textContent:'{}'})};
const context = {document, console}; vm.createContext(context);
let source = fs.readFileSync('reporting/report.js','utf8').replace('StatisticsReport.Initialize();','');
vm.runInContext(source + '\nthis.report = StatisticsReport;', context);
const report = context.report, root = element('main');
const expected = '[{"op":"replace","path":"/elements/\\"element-a\\"/count","value":9}]';
const state = {elements:[{key:'element-a',count:9}],storage:[]};
report.Content = root;
report.Data = {matrix:{records:{case:{outcome:'pass',metadata:{},evaluation:{
    expected_response:{kind:'reference',text:expected,label:'Reference valid response'},
    validation_states:{expected:state,actual:state,actual_available:true}}}}}};
report.EvaluationFeedback = () => {}; report.EvidenceSection = () => {};
report.ShowEvidence('case',{test_definition:{expected_state:state},variant_definition:{},calls:[]},true);
const block = label => root.children.find(x => x.dataset.evidenceBlock === label);
const response = block('Expected result'), validation = block('Resulting JSON states for validation');
assert(response && validation);
assert.strictEqual(response.children.find(x => x.tag === 'pre').textContent, expected);
assert(!response.children.some(x => x.textContent.includes('Expected final state')));
assert(validation.children.some(x => x.textContent === 'Expected resulting JSON state'));
assert(validation.children.some(x => x.textContent === 'Actual resulting JSON state'));
assert.strictEqual(validation.children.filter(x => x.tag === 'pre').length, 2);
console.log('Response text and state blocks rendered separately.');
'''
        completed = subprocess.run(['node', '-e', script], cwd=root, text=True, capture_output=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
