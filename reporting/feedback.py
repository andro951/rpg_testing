"""Derived evaluator diagnostics; never rewrite saved scores or raw evidence."""
import copy
import json
from functools import lru_cache
from pathlib import Path
from evaluation.core import assess_record, FAIL, NOT_EVALUATED


@lru_cache(maxsize=1)
def _reference_fixtures():
    path = Path(__file__).resolve().parents[1] / 'evaluation' / 'fixtures.json'
    return json.loads(path.read_text(encoding='utf-8'))['fixtures']


def response_expectation(test, variant):
    """Display only authoritative response examples verified against captured contracts."""
    from workbench.workflows import evaluate
    result = variant.get('result', {})
    representation = result.get('representation', 'answers')
    if representation == 'answers':
        return {'kind': 'exact_answers', 'answers': copy.deepcopy(variant.get('expected_answers', {}))}
    step = result.get('step')
    candidates = []
    if 'expected_patch' in variant:
        value = variant['expected_patch']
        candidates.append(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))
    if representation == 'state' and 'expected_state' in test:
        candidates.append(json.dumps(test['expected_state'], ensure_ascii=False))
    try:
        candidates.extend(f['outputs'][step] for f in _reference_fixtures()
                          if f['test_id'] == test['id'] and f['variant_id'] == variant['id'] and step in f['outputs'])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    for text in candidates:
        try:
            if evaluate(test, variant, {step: text}).get('exact_match'):
                return {'kind': 'reference', 'text': text,
                        'label': 'Reference valid response; equivalent valid responses are accepted.'}
        except (ValueError, KeyError, TypeError):
            continue
    return {'kind': 'unavailable', 'reason': 'No reference response verified against this captured contract is available.'}


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
            'steps': assessment.get('steps', []),
            'expected_response': response_expectation(test, variant),
            'validation_states': {
                'expected': copy.deepcopy(test.get('expected_state')),
                'actual': copy.deepcopy(record.get('score', {}).get('actual_state')),
                'actual_available': 'actual_state' in record.get('score', {})}}
