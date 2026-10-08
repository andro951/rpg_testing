import copy
import json
import unittest
from pathlib import Path
from reporting.feedback import summarize
from reporting.report import build_report
from workbench.domain import code_fingerprint, digest, read_json
from tests.test_prompt_optimization import valid_move
from evaluation.core import PASS, FAIL

ROOT = Path(__file__).resolve().parents[1]


def record():
    test = read_json(ROOT / 'test_specs/array_patch_move_007.json')
    variant = test['variants'][0]
    patch = valid_move({'test': test})
    text = json.dumps(patch)
    return {'case_id': digest('feedback-fixture'), 'model_id': 'mock', 'test_id': test['id'], 'variant_id': variant['id'],
            'test_definition': test, 'variant_definition': variant, 'status': 'completed', 'repetition': 0,
            'score': {'exact_match': True}, 'outputs': {variant['result']['step']: text},
            'calls': [{'step': variant['result']['step'], 'text': text, 'finish_reason': 'stop', 'messages': []}],
            'provenance': {'workflow_code': code_fingerprint()}, 'simulated': True}


class ResultFeedbackTests(unittest.TestCase):
    def test_pass_has_detailed_checks_and_a_readable_reason(self):
        feedback = summarize(record())
        self.assertEqual(feedback['objective_outcome'], 'PASS')
        self.assertIn('Matches', feedback['reason'])
        self.assertEqual(feedback['score_comparison'], 'agrees')
        self.assertTrue(any(check['code'] == 'state.final' and check['status'] == PASS for check in feedback['checks']))

    def test_invalid_json_pointer_identifies_the_specific_defect(self):
        value = record()
        text = '[{"op":"move","from":"tickets.1","path":"tickets.2"}]'
        value['outputs'][value['variant_definition']['result']['step']] = text
        value['calls'][0]['text'] = text
        value['score']['exact_match'] = False
        feedback = summarize(value)
        self.assertEqual(feedback['objective_outcome'], 'FAIL')
        self.assertTrue(any('pointer' in check['code'] and check['status'] == FAIL for check in feedback['checks']))
        self.assertTrue(feedback['reason'])
        self.assertEqual(feedback['score_comparison'], 'agrees')

    def test_infrastructure_and_partial_timeout_do_not_claim_semantic_failure(self):
        for status, timed_out in [('error', False), ('completed', True)]:
            value = record()
            value.update(status=status, timed_out=timed_out, error='connection or watchdog')
            value['calls'][0]['finish_reason'] = None
            value['calls'][0]['text'] = '[{"op":"move"'
            value['outputs'] = {}
            feedback = summarize(value)
            self.assertEqual(feedback['objective_outcome'], 'INCONCLUSIVE')
            self.assertEqual(feedback['score_comparison'], 'not_comparable')
            self.assertTrue(feedback['reason'])

    def test_disagreement_is_visible_without_rewriting_scores_colors_or_raw_record(self):
        value = record()
        text = '[]'
        value['calls'][0]['text'] = text
        value['outputs'][value['variant_definition']['result']['step']] = text
        before = copy.deepcopy(value)
        report = build_report([value], [value['test_definition']])
        summary = report['matrix']['records'][value['case_id']]
        self.assertEqual(summary['outcome'], 'pass')
        self.assertEqual(summary['evaluation']['objective_outcome'], 'FAIL')
        self.assertEqual(summary['evaluation']['score_comparison'], 'disagreement')
        self.assertEqual(value, before)

    def test_evidence_disagreement_is_inconclusive_and_explained(self):
        value = record()
        value['outputs'][value['variant_definition']['result']['step']] = '[]'
        feedback = summarize(value)
        self.assertEqual(feedback['objective_outcome'], 'INCONCLUSIVE')
        self.assertIn('Evidence is inconclusive', feedback['reason'])
        self.assertTrue(any(check['scope'] == 'evidence' and check['status'] == FAIL for check in feedback['checks']))

    def test_missing_legacy_contract_and_bad_capture_are_explicit(self):
        self.assertEqual(summarize({'score': {'exact_match': False}})['objective_outcome'], 'UNAVAILABLE')
        value = record()
        value['variant_definition'] = {'id': 'broken', 'steps': None}
        self.assertEqual(summarize(value)['objective_outcome'], 'UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
