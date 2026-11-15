"""Catch accidental duplicate benchmark requests under different display names."""
import copy
import unittest
from pathlib import Path

from workbench.domain import canonical, read_json, validate_test
from workbench.workflows import messages

ROOT = Path(__file__).resolve().parents[1]


def trial_signature(test, variant):
    """Compare experimental behavior, never display names or variant IDs."""
    if not all(step['type'] == 'generate' for step in variant['steps']):
        raise AssertionError('Add explicit control-flow comparison for non-generation steps')
    calls = []
    for step in variant['steps']:
        calls.append({
            'messages': messages(test, step, {}, variant),
            'sampling': {'temperature': 0.0, 'top_p': 1.0, 'top_k': 0,
                         'min_p': 0.0, 'seed': 42, **step.get('sampling', {})},
            'output': step.get('output'), 'when': step.get('when'),
            'uses': step.get('uses', []),
        })
    return canonical({
        'calls': calls, 'cache': variant.get('cache', 'default'),
        'source_state': test['source']['initial_state'],
        'result': variant.get('result'), 'expected': test.get('expected_state'),
        'answers': variant.get('expected_answers'), 'checks': variant.get('checks', []),
        # The same initial request with model-controlled self-review is a
        # distinct experimental condition. Include actual workflow settings,
        # not an arbitrary identity suffix that could hide true duplicates.
        'self_check': variant.get('self_check'),
    })


class CatalogUniquenessTests(unittest.TestCase):
    def test_distinct_cases_have_distinct_requests_or_scoring(self):
        seen = {}
        for path in sorted((ROOT / 'test_specs').glob('*.json')):
            test = read_json(path)
            validate_test(test)
            for variant in test['variants']:
                signature = trial_signature(test, variant)
                label = (test['id'], variant['id'])
                self.assertNotIn(signature, seen, f'{label} duplicates {seen.get(signature)}')
                seen[signature] = label

    def test_renaming_does_not_hide_duplicate_workflow_but_real_self_check_differs(self):
        test = read_json(next((ROOT / 'test_specs').glob('*.json')))
        baseline = next(v for v in test['variants'] if not v.get('self_check'))
        original = trial_signature(test, baseline)
        renamed_test, renamed_variant = copy.deepcopy((test, baseline))
        renamed_test['id'] = 'cosmetic-name-only'
        renamed_variant['id'] = 'cosmetic-variant-only'
        self.assertEqual(original, trial_signature(renamed_test, renamed_variant))
        checked = next(v for v in test['variants'] if v.get('self_check')
                       and v['id'] == baseline['id'] + '__self_check')
        self.assertNotEqual(original, trial_signature(test, checked))
        changed_limit = copy.deepcopy(checked)
        changed_limit['self_check']['max_revisions'] += 1
        self.assertNotEqual(trial_signature(test, checked), trial_signature(test, changed_limit))


if __name__ == '__main__':
    unittest.main()
