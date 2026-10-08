"""Derived evaluator diagnostics; never rewrite saved scores or raw evidence."""
import copy
from evaluation.core import assess_record, FAIL, NOT_EVALUATED


def summarize(record):
    test, variant = record.get('test_definition'), record.get('variant_definition')
    if not isinstance(test, dict) or not test.get('id') or not isinstance(variant, dict) or not variant.get('id'):
        return {'objective_outcome': 'UNAVAILABLE', 'reason': 'Detailed evaluation is unavailable: no captured test/variant contract.',
                'checks': [], 'score_comparison': 'not_comparable'}
    try:
        assessment = assess_record(record)
    except (KeyError, TypeError, ValueError) as exc:
        return {'objective_outcome': 'UNAVAILABLE', 'reason': 'Captured evidence cannot be evaluated: ' + str(exc),
                'checks': [], 'score_comparison': 'not_comparable'}
    checks = copy.deepcopy(assessment['checks'])
    relevant = [check for check in checks if check['status'] == FAIL and check.get('affects_verdict', True)]
    verdict = assessment['objective_outcome']
    if verdict == 'PASS':
        reason = 'Matches the required answer or final state and operation contract.'
    elif verdict == 'FAIL':
        reason = assessment.get('primary_reason') or (relevant[0]['explanation'] if relevant else 'The required answer did not pass.')
    elif relevant:
        evidence_error = next((check for check in relevant if check['scope'] == 'evidence'), relevant[0])
        reason = 'Evidence is inconclusive: ' + evidence_error['explanation']
    elif record.get('timed_out'):
        reason = 'The run timed out; an incomplete response does not establish semantic success or failure.'
    elif record.get('status') in ('error', 'aborted', 'skipped'):
        reason = 'Execution ' + record['status'] + ': ' + str(record.get('error') or record.get('reason') or 'No completed answer.')
    else:
        reason = next((check['explanation'] for check in checks if check['status'] == NOT_EVALUATED),
                      'No scored objective verdict is available.')
    return {'evaluator_version': assessment['evaluator_version'], 'objective_outcome': verdict,
            'execution_outcome': assessment['execution_outcome'], 'reason': reason,
            'score_comparison': assessment['score_comparison'], 'checks': checks,
            'steps': assessment.get('steps', [])}
