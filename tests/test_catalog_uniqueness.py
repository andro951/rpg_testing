"""Catch accidental duplicate benchmark requests under different display names."""
import unittest
from pathlib import Path

from workbench.domain import canonical, load_tests as load_catalog, validate_test
from workbench.workflows import messages

ROOT = Path(__file__).resolve().parents[1]


class CatalogUniquenessTests(unittest.TestCase):
    def test_distinct_cases_have_distinct_requests_or_scoring(self):
        seen = {}
        for test in load_catalog(ROOT / 'test_specs'):
            validate_test(test)
            for variant in test['variants']:
                # Current catalog workflows have straight-line generation steps.
                # Fail explicitly if richer control flow needs a new comparison.
                self.assertTrue(all(step['type'] == 'generate' for step in variant['steps']))
                calls = []
                for step in variant['steps']:
                    calls.append({
                        'messages': messages(test, step, {}, variant),
                        'sampling': {'temperature': 0.0, 'top_p': 1.0, 'top_k': 0,
                                     'min_p': 0.0, 'seed': 42, **step.get('sampling', {})},
                        'output': step.get('output'), 'when': step.get('when'),
                        'uses': step.get('uses', []),
                    })
                signature = canonical({
                    'calls': calls, 'cache': variant.get('cache', 'default'),
                    'source_state': test['source']['initial_state'],
                    'result': variant.get('result'), 'expected': test.get('expected_state'),
                    'answers': variant.get('expected_answers'), 'checks': variant.get('checks', []),
                })
                label = (test['id'], variant['id'])
                self.assertNotIn(signature, seen, f'{label} duplicates {seen.get(signature)}')
                seen[signature] = label


if __name__ == '__main__':
    unittest.main()
