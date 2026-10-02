"""Timing policies use original observations without changing scores or identity."""
import copy
import math
from pathlib import Path
import unittest
from reporting.timing import annotate, expectations
from reporting.matrix import has_objective_oracle
from workbench.domain import digest, experiment_spec, read_json


def sample(model, elapsed, outcome='pass', group='same-test'):
    return {'model': model, 'outcome': outcome, 'timing_group': group, 'definition_id': 'definition',
            'execution_class': 'local_gpu', 'metadata': {'test_id': 'test', 'variant_id': 'variant',
            'pipeline_seconds': elapsed, 'timeout_seconds': 300}}


class TimingTests(unittest.TestCase):
    def annotate(self, records, catalog=None):
        matrix = {'records': {str(index): record for index, record in enumerate(records)}}
        catalog = {'test': {'variant': {'seconds': 20, 'definition_id': 'definition'}}} if catalog is None else catalog
        return annotate(matrix, [{'id': 'test', 'timeout_seconds': 120}], catalog)

    def test_static_expectations_cover_every_current_objective_definition(self):
        catalog = expectations(); budgets = set(); count = 0
        for path in (Path(__file__).resolve().parents[1] / 'test_specs').glob('*.json'):
            test = read_json(path)
            for variant in test['variants']:
                if not has_objective_oracle(test, variant): continue
                entry = catalog[test['id']][variant['id']]
                self.assertEqual(entry['definition_id'], digest(experiment_spec(test, variant)))
                self.assertTrue(0 < entry['seconds'] < test['timeout_seconds'])
                self.assertTrue(entry['reason']); budgets.add(entry['seconds']); count += 1
        self.assertEqual(count, 159)
        self.assertGreater(len(budgets), 3)

    def test_equal_model_weight_and_both_completed_passes_and_failures(self):
        records = [sample('fast', 10) for _ in range(20)] + [sample('middle', 20, 'fail'), sample('slow', 100)]
        self.annotate(records)
        self.assertEqual(records[0]['timing']['peer_median_seconds'], 20)
        self.assertEqual(records[0]['timing']['relative_threshold_seconds'], 40)
        self.assertEqual(records[0]['timing']['expected_seconds'], 20)

    def test_timeout_errors_invalid_and_missing_times_do_not_bias_median(self):
        records = [sample('a', 10), sample('b', 20), sample('c', 30)]
        records += [sample('timeout', 300, 'timeout'), sample('error', 900, 'error'), sample('invalid', 800, 'invalid'),
                    sample('unknown', None), sample('infinite', math.inf), sample('negative', -1), sample('bool', True)]
        records[-1]['metadata']['timed_out'] = True
        self.annotate(records)
        self.assertEqual(records[0]['timing']['peer_models'], 3)
        self.assertEqual(records[0]['timing']['peer_median_seconds'], 20)
        self.assertTrue(records[-1]['timing']['timed_out'])
        for record in records[-4:]: self.assertIsNone(record['timing']['elapsed_seconds'])

    def test_fewer_than_three_models_and_different_revision_do_not_make_peer_claims(self):
        records = [sample('a', 10), sample('b', 100), sample('c', 15, group='different-revision')]
        self.annotate(records)
        for record in records: self.assertIsNone(record['timing']['peer_median_seconds'])

    def test_expectation_never_adapts_even_if_all_models_are_slow(self):
        records = [sample('a', 60), sample('b', 70), sample('c', 80)]
        self.annotate(records)
        self.assertTrue(all(record['timing']['expected_seconds'] == 20 for record in records))
        self.assertEqual(records[0]['timing']['peer_median_seconds'], 70)
        self.assertTrue(all(record['timing']['elapsed_seconds'] > 20 for record in records))

    def test_changed_definition_loses_stale_expectation_and_score_is_untouched(self):
        record = sample('a', 10); record['definition_id'] = 'edited'
        record['metadata']['score'] = {'exact_match': False}
        original = copy.deepcopy(record)
        self.annotate([record])
        self.assertIsNone(record['timing']['expected_seconds'])
        self.assertEqual({key: value for key, value in record.items() if key != 'timing'}, original)

    def test_current_deadline_is_separate_from_saved_deadline_and_remote_limit(self):
        records = [sample('local', 50), sample('remote', 50)]
        records[1]['execution_class'] = 'remote_service'
        self.annotate(records)
        self.assertEqual(records[0]['timing']['current_timeout_seconds'], 120)
        self.assertEqual(records[0]['timing']['saved_timeout_seconds'], 300)
        self.assertEqual(records[1]['timing']['current_timeout_seconds'], 300)

    def test_invalid_expectation_fails_instead_of_fabricating_budget(self):
        with self.assertRaises(ValueError):
            self.annotate([sample('a', 10)], {'test': {'variant': {'seconds': -1, 'definition_id': 'definition'}}})
