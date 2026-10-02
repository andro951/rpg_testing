import copy
import json
from pathlib import Path
import unittest
from reporting.grouping import AXES, catalog, row_grouping
from reporting.matrix import build_matrix, has_objective_oracle
from workbench.domain import code_fingerprint, digest, experiment_spec


ROOT = Path(__file__).resolve().parents[1]


class ReportGroupingTests(unittest.TestCase):
    def spec(self, name):
        return json.loads((ROOT / 'test_specs' / (name + '.json')).read_text(encoding='utf-8'))

    def grouping(self, test, variant):
        return row_grouping(test, variant, test['id'], variant['id'])

    def test_catalog_covers_every_current_objective_variant(self):
        count = 0
        for path in (ROOT / 'test_specs').glob('*.json'):
            test = json.loads(path.read_text(encoding='utf-8'))
            for variant in test['variants']:
                if has_objective_oracle(test, variant):
                    count += 1
                    entry = catalog()[test['id']][variant['id']]
                    self.assertEqual(set(entry), set(AXES) | {'reviewed_definition'})
                    self.assertTrue(all(isinstance(value, str) and value for value in entry.values()))
        self.assertEqual(count, 159)

    def test_presentations_share_a_version_and_comparison_set(self):
        for family in ('array_index_replace_010', 'array_patch_replace_004', 'prompt_calibration_002_boolean'):
            test = self.spec(family)
            if family.startswith('array_index'):
                pairs = [(test, variant) for variant in test['variants']]
            else:
                pairs = [(test, variant) for variant in test['variants'] if variant['id'].startswith('v2') or variant['id'].startswith('raw_array') or variant['id'].startswith('indexed_object')]
                full = self.spec(family + '_full_paths')
                pairs += [(full, variant) for variant in full['variants'] if variant['id'].startswith('v2') or variant['id'].startswith('full_paths')]
            with self.subTest(family=family):
                groupings = [self.grouping(t, v) for t, v in pairs]
                self.assertEqual(len(groupings), 3)
                self.assertEqual(len({g['prompt_comparison_set']['key'] for g in groupings}), 1)
                self.assertEqual(len({g['test_version']['key'] for g in groupings}), 1)
                self.assertEqual({g['input_presentation']['label'] for g in groupings}, {'Normal JSON', 'Indexed arrays', 'Full paths'})

    def test_wording_versions_share_fixture_but_keep_distinct_versions(self):
        pairs = [(self.spec(name), self.spec(name)['variants'][0]) for name in
                 ('array_index_replace_010', 'array_index_replace_minimal_016', 'array_index_replace_explicit_minimal_017')]
        groupings = [self.grouping(t, v) for t, v in pairs]
        self.assertEqual(len({g['prompt_comparison_set']['key'] for g in groupings}), 1)
        self.assertEqual(len({g['test_version']['key'] for g in groupings}), 3)

    def test_different_oracles_states_and_response_protocols_are_not_merged(self):
        test = self.spec('time_only')
        variant = test['variants'][0]
        original = self.grouping(test, variant)['prompt_comparison_set']['key']
        for field in ('source', 'expected_state'):
            changed = copy.deepcopy(test)
            changed[field] = {'different': True}
            self.assertNotEqual(original, self.grouping(changed, variant)['prompt_comparison_set']['key'])
        changed = copy.deepcopy(variant)
        changed['result'] = {'step': 'other', 'representation': 'semantic'}
        self.assertNotEqual(original, self.grouping(test, changed)['prompt_comparison_set']['key'])
        self.assertNotEqual(original, self.grouping(test, test['variants'][1])['prompt_comparison_set']['key'])

    def test_embedded_fixture_changes_require_metadata_review(self):
        test = self.spec('array_index_replace_010')
        variant = test['variants'][0]
        changed = copy.deepcopy(variant)
        changed['steps'][0]['prompt'] = changed['steps'][0]['prompt'].replace('SR-22345', 'SR-99999')
        self.assertNotEqual(self.grouping(test, variant)['prompt_comparison_set']['key'],
                            self.grouping(test, changed)['prompt_comparison_set']['key'])
        changed = copy.deepcopy(test)
        changed['timeout_seconds'] = 600
        self.assertEqual(self.grouping(test, variant), self.grouping(changed, variant))

    def test_metadata_does_not_change_definitions_or_row_identity(self):
        test = self.spec('array_index_replace_010')
        before = copy.deepcopy(test)
        identities = [digest(experiment_spec(test, variant)) for variant in test['variants']]
        first = build_matrix([], [test], code_fingerprint())
        second = build_matrix([], [test], code_fingerprint())
        self.assertEqual([row['id'] for row in first['rows']], [row['id'] for row in second['rows']])
        self.assertEqual(identities, [digest(experiment_spec(test, variant)) for variant in test['variants']])
        self.assertEqual(before, test)
        self.assertTrue(all(row['current'] for row in first['rows']))

    def test_unregistered_tests_keep_separate_comparisons_and_unknown_presentation(self):
        test = {'id': 'future', 'source': {'value': 1}}
        variant = {'id': 'v1', 'expected_answers': {'answer': '1'}}
        first = self.grouping(test, variant)
        self.assertEqual(first['input_presentation']['label'], 'Unspecified')
        changed = copy.deepcopy(variant)
        changed['expected_answers']['answer'] = '2'
        self.assertNotEqual(first['prompt_comparison_set']['key'], self.grouping(test, changed)['prompt_comparison_set']['key'])