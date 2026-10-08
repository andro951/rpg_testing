import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evaluation.catalog import catalog, registration
from evaluation.core import assess, assess_record, resolve, ResolutionError
from evaluation.__main__ import replay, readable
from workbench.domain import ResultStore, code_fingerprint, read_json, digest
from workbench.workflows import evaluate

ROOT = Path(__file__).resolve().parents[1]


def contracts():
    for fixture in read_json(ROOT/'evaluation/fixtures.json')['fixtures']:
        test = read_json(ROOT/fixture['source_path'])
        variant = next(v for v in test['variants'] if v['id'] == fixture['variant_id'])
        yield fixture, test, variant


def failed_codes(assessment):
    return {c['code'] for c in assessment['checks'] if c['status'] == 'failed'}


class CoverageTests(unittest.TestCase):
    def test_every_current_definition_and_variant_registered(self):
        entries = catalog()['definitions']
        paths = {e['path'] for e in entries}
        expected = {p.relative_to(ROOT).as_posix() for base in ['test_specs', 'examples/test_specs'] for p in (ROOT/base).glob('*.json')}
        self.assertEqual(paths, expected)
        objective = set()
        for entry in entries:
            source = ROOT/entry['path']
            test = read_json(source)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), entry['source_sha256'])
            self.assertEqual(entry['variants'], [v['id'] for v in test['variants']])
            if entry['family'] != 'dialogue':
                objective.update((test['id'], v['id']) for v in test['variants'])
        self.assertEqual(objective, {(f['test_id'], f['variant_id']) for f, _, _ in contracts()})
        self.assertEqual(len(objective), 163)
        with self.assertRaises(ValueError): registration('time_only', 'made_up')

    def test_registration_requires_explicit_current_contract(self):
        self.assertEqual(registration('inventory_net_stock_001', 'direct_json_patch')['family'], 'inventory')
        with self.assertRaises(ValueError): registration('unknown-test', 'v')

    def test_every_variant_synthetic_pass_agrees_with_existing_oracle(self):
        for fixture, test, variant in contracts():
            with self.subTest(test=test['id'], variant=variant['id']):
                original = copy.deepcopy((test, variant, fixture))
                result = assess(test, variant, fixture['outputs'])
                self.assertEqual(result['objective_outcome'], 'PASS', result['checks'])
                self.assertTrue(evaluate(test, variant, fixture['outputs'])['exact_match'])
                self.assertEqual((test, variant, fixture), original)
                self.assertFalse(failed_codes(result))

    def test_each_variant_wrong_response_and_output_format(self):
        for fixture, test, variant in contracts():
            with self.subTest(test=test['id'], variant=variant['id']):
                values = copy.deepcopy(fixture['outputs'])
                if variant['result']['representation'] == 'answers':
                    key = next(iter(variant['expected_answers']))
                    wanted = values[key]
                    values[key] = 'Wrong answer' if isinstance(wanted, str) else 'true'
                    self.assertEqual(assess(test, variant, values)['objective_outcome'], 'FAIL')
                    self.assertFalse(evaluate(test, variant, values)['exact_match'])
                else:
                    key = variant['result']['step']
                    good = values[key]
                    values[key] = '```json\n' + good + '\n```'
                    result = assess(test, variant, values)
                    self.assertIn('json.document', failed_codes(result))
                    self.assertEqual(result['objective_outcome'], 'FAIL')
                    values[key] = good[:-1]
                    self.assertIn('json.document', failed_codes(assess(test, variant, values)))

    def test_each_patch_variant_missing_fields_bad_pointer_and_extra_changes(self):
        for fixture, test, variant in contracts():
            if variant['result']['representation'] == 'answers': continue
            with self.subTest(test=test['id'], variant=variant['id']):
                values = copy.deepcopy(fixture['outputs']); key = variant['result']['step']
                patch = json.loads(values[key])
                bad = copy.deepcopy(patch); del bad[0]['path']; values[key] = json.dumps(bad)
                result = assess(test, variant, values)
                self.assertIn('patch.structure', failed_codes(result))
                self.assertEqual(next(c['status'] for c in result['checks'] if c['code'] == 'state.final'), 'not_evaluated')
                bad = copy.deepcopy(patch); bad[0]['path'] = 'without-leading-slash'; values[key] = json.dumps(bad)
                self.assertIn('pointer.syntax', failed_codes(assess(test, variant, values)))
                extra = {'op': 'set' if variant['result']['representation'] == 'semantic' else 'replace', 'path': '/queue_name' if 'queue_name' in test['source']['initial_state'] else '/location', 'value': 'Unrequested change'}
                # Semantic set requires an existing field; all these states have location or queue_name except inventory/household.
                if extra['path'] not in ('/queue_name',) and 'location' not in test['source']['initial_state']:
                    first = next(iter(test['source']['initial_state']))
                    extra['path'] = '/' + first.replace('~', '~0').replace('/', '~1')
                values[key] = json.dumps(patch + [extra])
                result = assess(test, variant, values)
                self.assertEqual(result['objective_outcome'], 'FAIL')
                self.assertIn('state.preservation', failed_codes(result))

    def test_each_variant_wrong_task_value_or_target(self):
        for fixture, test, variant in contracts():
            if variant['result']['representation'] == 'answers': continue
            with self.subTest(test=test['id'], variant=variant['id']):
                values = copy.deepcopy(fixture['outputs']); key = variant['result']['step']
                patch = json.loads(values[key]); first = patch[0]
                if 'value' in first: first['value'] = 'Deliberately wrong value and type'
                elif 'from' in first: first['from'] = '/tickets/0'
                else: first['path'] = '/tickets/0' if first['path'].startswith('/tickets/') else '/missing_target'
                values[key] = json.dumps(patch)
                result = assess(test, variant, values)
                self.assertEqual(result['objective_outcome'], 'FAIL')
                self.assertFalse(evaluate(test, variant, values)['exact_match'])
                self.assertTrue(failed_codes(result))


class DetailedTests(unittest.TestCase):
    def setUp(self):
        self.fixture, self.test, self.variant = next((f, t, v) for f, t, v in contracts() if t['id'] == 'prompt_calibration_003_nested_full_paths')

    def test_nested_display_path_is_syntactically_valid_but_missing(self):
        result = assess(self.test, self.variant, {'patch': '[{"op":"replace","path":"/characters.Tom.mood","value":"relaxed"}]'})
        self.assertEqual(result['objective_outcome'], 'FAIL')
        self.assertIn('pointer.missing_field', failed_codes(result))
        self.assertNotIn('pointer.syntax', failed_codes(result))
        self.assertTrue(any(c['code'] == 'task.proposed_value' and c['status'] == 'passed' for c in result['checks']))
        self.assertEqual(next(c['status'] for c in result['checks'] if c['code'] == 'state.final'), 'not_evaluated')

    def test_all_structure_checks_continue_but_application_stops(self):
        raw = '[{"op":"replace","path":"/absent","value":1},{"op":"replace","path":"broken","value":2}]'
        result = assess(self.test, self.variant, {'patch': raw})
        self.assertIn('pointer.syntax', failed_codes(result))
        self.assertTrue(any(c['operation'] == 1 and c['status'] == 'not_evaluated' for c in result['checks'] if c['code'] == 'patch.application'))

    def test_duplicate_keys_nonfinite_and_wrong_top_level(self):
        for raw in ['[{"op":"replace","op":"add","path":"/time","value":0}]', '[{"op":"replace","path":"/time","value":NaN}]']:
            self.assertIn('json.document', failed_codes(assess(self.test, self.variant, {'patch': raw})))
        self.assertIn('patch.array', failed_codes(assess(self.test, self.variant, {'patch': '{}'})))

    def test_equivalent_patch_extra_rfc_fields_and_numeric_equality(self):
        test = {'id': 'fixture', 'source': {'initial_state': {'n': 42}}, 'expected_state': {'n': 49}}
        variant = {'id': 'v', 'result': {'step': 'patch', 'representation': 'json_patch'}}
        self.assertEqual(assess(test, variant, {'patch': '[{"op":"add","path":"/n","value":49.0,"comment":"ignored RFC extension"}]'})['objective_outcome'], 'PASS')
        for value in ['"49"', 'true']:
            self.assertEqual(assess(test, variant, {'patch': '[{"op":"replace","path":"/n","value":'+value+'}]'})['objective_outcome'], 'FAIL')

    def test_resolution_categories_and_escaped_keys(self):
        for doc, parts, code in [({}, ['a', 'b'], 'missing_ancestor'), ({'a': 3}, ['a', 'b'], 'non_container'), ({'a': []}, ['a', '0'], 'array_bounds'), ({'a': [1]}, ['a', '-'], 'array_index')]:
            with self.subTest(code=code), self.assertRaises(ResolutionError) as caught:
                resolve(doc, parts)
            self.assertEqual(caught.exception.code, code)
        t = {'id': 'escaped', 'source': {'initial_state': {'a/b': {'~key': 1}}}, 'expected_state': {'a/b': {'~key': 2}}}
        v = {'id': 'v', 'result': {'step': 'patch', 'representation': 'json_patch'}}
        self.assertEqual(assess(t, v, {'patch': '[{"op":"replace","path":"/a~1b/~0key","value":2}]'})['objective_outcome'], 'PASS')

    def test_required_precondition_cannot_be_omitted(self):
        fixture, test, variant = next((f, t, v) for f, t, v in contracts() if t['id'] == 'array_patch_test_009')
        patch = json.loads(fixture['outputs']['patch'])
        result = assess(test, variant, {'patch': json.dumps(patch[1:])})
        self.assertIn('patch.required_operations', failed_codes(result))
        self.assertTrue(any(c['code'] == 'state.final' and c['status'] == 'passed' for c in result['checks']))
        patch[0]['value'] = 'wrong'
        result = assess(test, variant, {'patch': json.dumps(patch)})
        self.assertIn('patch.precondition', failed_codes(result))
        self.assertEqual(next(c['status'] for c in result['checks'] if c['code'] == 'state.final'), 'not_evaluated')

    def test_move_after_removal_and_copy_retains_source(self):
        for identifier in ['array_patch_move_007', 'array_patch_copy_008']:
            fixture, test, variant = next((f, t, v) for f, t, v in contracts() if t['id'] == identifier)
            patch = json.loads(fixture['outputs']['patch'])
            patch[0]['path'] = '/tickets/8' if 'move' in identifier else '/review_samples/-'
            if 'copy' in identifier: patch[0]['op'] = 'move'
            result = assess(test, variant, {'patch': json.dumps(patch)})
            self.assertEqual(result['objective_outcome'], 'FAIL')
            self.assertIn('array.order' if 'move' in identifier else 'array.membership', failed_codes(result))

    def test_index_correct_value_wrong_format_and_ambiguous_values(self):
        fixture, test, variant = next((f, t, v) for f, t, v in contracts() if t['id'] == 'array_index_replace_010')
        for text, numeric_good in [('The index is 73', True), ('73\n', True), ('-73', False), ('73.0', False), ('73 or 74', False)]:
            result = assess(test, variant, {'index': text})
            self.assertEqual(result['objective_outcome'], 'FAIL')
            self.assertEqual(next(c['status'] == 'passed' for c in result['checks'] if c['code'] == 'index.value'), numeric_good)

    def test_dialogue_unscored_and_supplementary_checks_preserved(self):
        test = read_json(ROOT/'test_specs/dialogue_test.json')
        self.assertEqual(assess(test, test['variants'][0], {})['objective_outcome'], 'UNSCORED')
        fixture, test, variant = next((f, t, v) for f, t, v in contracts() if t['id'] == 'narrate_then_update')
        values = {**fixture['outputs'], 'story': 'No explicit clock phrase'}
        result = assess(test, variant, values)
        self.assertEqual(result['objective_outcome'], 'PASS')
        self.assertIn('workflow.explicit_check', failed_codes(result))

    def test_timeout_never_invents_completed_success_or_failed_incomplete_json(self):
        for raw in [self.fixture['outputs']['patch'], '[{"op":', '']:
            result = assess(self.test, self.variant, {'patch': raw}, execution='timeout')
            self.assertEqual(result['objective_outcome'], 'INCONCLUSIVE')
            self.assertFalse(failed_codes(result))

    def test_semantic_removal_requires_one_unique_match(self):
        test = {'id': 'duplicates', 'source': {'initial_state': {'items': ['coat', 'coat']}}, 'expected_state': {'items': ['coat']}}
        variant = {'id': 'v', 'result': {'step': 'patch', 'representation': 'semantic'}}
        result = assess(test, variant, {'patch': '[{"op":"list_remove","path":"/items","value":"coat"}]'})
        self.assertIn('array.removal_match', failed_codes(result))
        self.assertEqual(result['objective_outcome'], 'FAIL')

    def test_no_external_schema_resolution(self):
        test = copy.deepcopy(self.test); test['state_schema'] = {'$ref': 'https://example.invalid/schema'}
        with self.assertRaisesRegex(ValueError, 'local #'):
            assess(test, self.variant, self.fixture['outputs'])


class ReplayTests(unittest.TestCase):
    def record(self):
        fixture, test, variant = next(contracts())
        return {'status': 'completed', 'case_id': digest('synthetic-evaluator-smoke'), 'model_id': 'synthetic-model',
                'test_id': test['id'], 'variant_id': variant['id'], 'test_definition': test, 'variant_definition': variant,
                'outputs': fixture['outputs'], 'score': evaluate(test, variant, fixture['outputs']), 'simulated': True,
                'calls': [{'step': s['id'], 'iteration': 0, 'messages': [{'role': 'user', 'content': s['prompt']}],
                           'text': fixture['outputs'][s['id']], 'finish_reason': 'stop'} for s in variant['steps']]}

    def test_replay_is_read_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'results'; output = root/'evaluations'
            path = ResultStore(source).save(self.record()); before = path.read_bytes(); identity = code_fingerprint()
            first = replay(source, output); second = replay(source, output)
            self.assertEqual(first, second)
            self.assertEqual(first['outcomes'], {'PASS': 1})
            self.assertEqual(first['score_comparisons'], {'agrees': 1})
            self.assertEqual(first['problems'], [])
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(code_fingerprint(), identity)
            report = next((output/'assessments').glob('*.txt')).read_text(encoding='utf-8')
            self.assertIn('Result: PASS', report)
            with self.assertRaises(ValueError): replay(source, source/'assessments')

    def test_evidence_corruption_fails_without_repairing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'results'
            path = ResultStore(source).save(self.record()); value = json.loads(path.read_text()); value['outputs'] = {}
            path.write_text(json.dumps(value)); before = path.read_bytes()
            result = replay(source, root/'evaluations')
            self.assertEqual(len(result['problems']), 1)
            self.assertEqual(result['outcomes'], {})
            self.assertEqual(path.read_bytes(), before)

    def test_zip_replay_and_missing_source(self):
        import zipfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root/'results'
            path = ResultStore(source).save(self.record())
            archive = root/'evidence.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.write(path, path.relative_to(root).as_posix())
            result = replay(archive, root/'evaluations')
            self.assertEqual(result['outcomes'], {'PASS': 1})
            self.assertFalse(result['problems'])
            with self.assertRaises(ValueError): replay(root/'missing', root/'other')

    def test_captured_definition_used_and_raw_calls_checked(self):
        record = self.record(); record['test_definition']['id'] = 'captured-original-id'
        original = copy.deepcopy(record)
        result = assess_record(record)
        self.assertEqual(result['test_id'], 'captured-original-id')
        self.assertEqual(result['objective_outcome'], 'PASS')
        self.assertEqual(record, original)
        key = next(iter(record['outputs'])); record['outputs'][key] = 'altered'
        result = assess_record(record)
        self.assertEqual(result['execution_outcome'], 'evidence_error')
        self.assertIn('evidence.output_consistency', failed_codes(result))

    def test_perchance_completed_response_is_not_mistaken_for_incomplete(self):
        record = self.record()
        for call in record['calls']: call['finish_reason'] = 'provider_completed'
        result = assess_record(record)
        self.assertEqual(result['objective_outcome'], 'PASS')
        self.assertEqual(result['execution_outcome'], 'completed')
        record['calls'][0]['incomplete'] = True
        self.assertEqual(assess_record(record)['objective_outcome'], 'INCONCLUSIVE')

    def test_repair_history_reviews_each_patch_and_self_claim(self):
        fixture, test, variant = next((f, t, v) for f, t, v in contracts() if t['id'] == 'verify_repair')
        good = fixture['outputs']['patch']; bad = '[{"op":"replace","path":"/time","value":"wrong"}]'
        calls = [{'step': s, 'iteration': iteration, 'text': text, 'finish_reason': 'stop'} for s, iteration, text in
                 [('analysis', 0, 'A five-minute change.'), ('patch', 0, bad), ('correct', 0, 'false'), ('repair', 1, good), ('review', 1, 'true')]]
        record = {'status': 'completed', 'test_definition': test, 'variant_definition': variant,
                  'outputs': {'analysis': calls[0]['text'], 'patch': good, 'correct': True, 'repair': good, 'review': True}, 'calls': calls}
        result = assess_record(record)
        self.assertEqual(result['objective_outcome'], 'PASS')
        patches = [s['semantic_outcome'] for s in result['steps'] if s['step'] in ('patch', 'repair')]
        self.assertEqual(patches, ['FAIL', 'PASS'])
        initial_review = next(s for s in result['steps'] if s['step'] == 'correct')
        self.assertTrue(any(c['code'] == 'workflow.self_review' and c['status'] == 'passed' for c in initial_review['checks']))
        calls[2]['text'] = 'true'
        result = assess_record(record)
        self.assertEqual(result['objective_outcome'], 'INCONCLUSIVE')
        self.assertIn('workflow.unexpected_call', failed_codes(result))
        initial_review = next(s for s in result['steps'] if s['step'] == 'correct')
        self.assertTrue(any(c['code'] == 'workflow.self_review' and c['status'] == 'failed' for c in initial_review['checks']))

    def test_typed_cached_answers_branch_and_invalid_boolean(self):
        fixture, test, variant = next((f, t, v) for f, t, v in contracts() if t['id'] == 'cached_questions')
        calls = [{'step': s['id'], 'iteration': 0, 'text': json.dumps(fixture['outputs'][s['id']]), 'finish_reason': 'stop'} for s in variant['steps']]
        record = {'status': 'completed', 'test_definition': test, 'variant_definition': variant, 'calls': calls, 'outputs': fixture['outputs']}
        self.assertEqual(assess_record(record)['objective_outcome'], 'PASS')
        calls[0]['text'] = '"true"'
        result = assess_record(record)
        self.assertEqual(result['objective_outcome'], 'INCONCLUSIVE')
        self.assertEqual(result['execution_outcome'], 'evidence_error')
        self.assertTrue(any(c['code'] == 'workflow.output_type' and c['status'] == 'failed' for c in result['steps'][0]['checks']))


if __name__ == '__main__':
    unittest.main()
