import copy
import unittest
from reporting.report import build_report
from reporting.matrix import outcome, totals, model_nickname
from tests.test_reporting import fixture
from workbench.domain import digest, experiment_spec, code_fingerprint


class ResultsMatrixTests(unittest.TestCase):
    def test_all_families_expected_missing_repetitions_and_unchanged_evidence(self):
        records, specs = fixture()
        test = {'id': 'non_array', 'name': 'No-op state test', 'repetitions': 3, 'variants': [{'id': 'noop', 'expected_answers': {'value': 'unchanged'}}]}
        specs.append(test)
        extra = copy.deepcopy(records[0])
        extra.update(case_id=digest('non-array'), test_id=test['id'], variant_id='noop', test_definition=test, variant_definition=test['variants'][0])
        records.append(extra)
        before = copy.deepcopy(records)
        matrix = build_report(records, specs)['matrix']
        self.assertEqual(len(matrix['records']), 37)
        rows = [r for r in matrix['rows'] if r['test_id'] == 'non_array']
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['name'], 'No-op state test')
        count = next(iter(matrix['totals'].values()))
        self.assertEqual((count['pass'], count['observations'], count['not_run']), (37, 37, 2))
        self.assertEqual(before, records)

    def test_history_multiple_results_and_simulated_native_remote_columns(self):
        records, specs = fixture()
        old = copy.deepcopy(records[0]); old['case_id'] = digest('old'); old['provenance']['workflow_code'] = 'old'
        duplicate = copy.deepcopy(records[0]); duplicate['case_id'] = digest('different-context'); duplicate['load']['context']['allocated'] = 900
        native = copy.deepcopy(records[0]); native.update(case_id=digest('real'), simulated=False)
        remote = copy.deepcopy(native); remote.update(case_id=digest('remote'), model_id='perchance-text-generator', model_name='Perchance Text Generator', execution_class='remote_service')
        matrix = build_report(records + [old, duplicate, native, remote], specs)['matrix']
        self.assertEqual(len(matrix['models']), 3)
        self.assertEqual(len([r for r in matrix['rows'] if not r['current']]), 1)
        self.assertTrue(any(len(c['primary_ids']) == 2 for r in matrix['rows'] for c in r['cells'].values()))
        self.assertEqual(sum(t['observations'] for t in matrix['totals'].values()), 40)

    def test_alias_references_never_add_trials_to_totals(self):
        records, specs = fixture()
        test = specs[0]; test['repetitions'] = 3
        record = records[0]
        record['aliases'] = [{'test_id': test['id'], 'variant_id': record['variant_id'], 'repetition': rep,
            'requested_id': digest(['request', rep]),
            'requested_definition': experiment_spec(test, record['variant_definition'])} for rep in range(3)]
        record['execution_class'] = 'remote_service'
        matrix = build_report([record], specs)['matrix']
        count = next(iter(matrix['totals'].values()))
        self.assertEqual((count['observations'], count['pass'], count['references']), (1, 1, 2))
        reference_cells = [c for r in matrix['rows'] for c in r['cells'].values() if c['reference_ids']]
        self.assertEqual(len(reference_cells), 2)
        self.assertEqual(totals(reference_cells, matrix['records'])['pass'], 0)

    def test_statuses_do_not_misclassify_missing_metrics_or_infrastructure(self):
        cases = [({'status':'completed','score':{'exact_match':True}}, 'pass'),
                 ({'status':'completed','score':{'exact_match':False}}, 'fail'),
                 ({'status':'completed','score':{'exact_match':None}}, 'unscored'),
                 ({'status':'completed','timed_out':True}, 'timeout'),
                 ({'status':'completed','measurement_valid':False,'score':{'exact_match':True}}, 'invalid')]
        cases += [({'status':s}, s) for s in ('error','aborted','skipped')]
        for record, expected in cases:
            with self.subTest(expected=expected):self.assertEqual(outcome(record), expected)

    def test_empty_and_unversioned_records_remain_visible(self):
        records = [{'case_id':digest('a'),'model_id':'m','test_id':'a','variant_id':'v','status':'skipped', 'score':{'exact_match':False}},
                   {'case_id':digest('b'),'model_id':'m','test_id':'b','variant_id':'v','status':'error', 'score':{'exact_match':False}}]
        matrix = build_report(records, [])['matrix']
        self.assertEqual(len(matrix['rows']), 2)
        self.assertEqual(len(matrix['records']), 2)
        self.assertEqual(build_report([], [])['matrix']['models'], [])


    def test_open_ended_dialogue_excluded_from_rows_columns_and_totals(self):
        records, specs = fixture()
        narrative = {'id': 'dialogue_test_0_0', 'repetitions': 3,
                     'variants': [{'id': 'response', 'result': {'representation': 'answers'}}]}
        generic = copy.deepcopy(narrative); generic['id'] = 'creative_scene'
        specs += [narrative, generic]
        extra = []
        for test in (narrative, generic):
            for status in ('completed', 'error'):
                record = copy.deepcopy(records[0])
                record.update(case_id=digest([test['id'], status]), test_id=test['id'], model_id='dialogue-only',
                              variant_id='response', test_definition=test, variant_definition=test['variants'][0],
                              status=status, score={'exact_match': False})
                extra.append(record)
        legacy = {'case_id':digest('legacy-dialogue'), 'model_id':'dialogue-only',
                  'test_id':'dialogue_test_old', 'variant_id':'response', 'status':'error', 'score':{'exact_match':False}}
        records[0]['aliases'] = [{'test_id': narrative['id'], 'variant_id': 'response', 'repetition': 0,
                                 'requested_definition': experiment_spec(narrative, narrative['variants'][0])}]
        before = copy.deepcopy(records + extra + [legacy])
        matrix = build_report(records + extra + [legacy], specs)['matrix']
        self.assertEqual(len(matrix['records']), 36)
        self.assertEqual(matrix['excluded_records'], 5)
        self.assertEqual({m['model_id'] for m in matrix['models']}, {'mock'})
        self.assertFalse(any(r['test_id'] in (narrative['id'], generic['id']) for r in matrix['rows']))
        count = next(iter(matrix['totals'].values()))
        self.assertEqual((count['observations'], count['pass'], count['fail'], count['references'], count['not_run']),
                         (36, 36, 0, 0, 0))
        self.assertEqual(before, records + extra + [legacy])

    def test_short_model_nicknames_preserve_identity_and_disambiguate(self):
        labels = ['Qwen3-VL-8B-Instruct-Q4_K_M.gguf', 'Qwen3.5-2B-Q8_0.gguf',
                  'Qwen3.5-4B-Q8_0.gguf', 'Qwen3.5-9B-Q4_K_M.gguf', 'Perchance Text Generator']
        self.assertEqual([model_nickname(label) for label in labels],
                         ['Q3-VL 8B', 'Q3.5 2B', 'Q3.5 4B', 'Q3.5 9B', 'Perchance'])
        self.assertLessEqual(len(model_nickname('UnknownModelWithAnExtremelyLongName.gguf')), 18)
        records, specs = fixture()
        first = records[0]; first['model_name'] = labels[0]
        second = copy.deepcopy(first)
        second.update(case_id=digest('nickname-collision'), model_name='Qwen3-VL-8B-Instruct-Q8_0.gguf', model_id='another-model')
        matrix = build_report([first, second], specs)['matrix']
        self.assertEqual({m['nickname'] for m in matrix['models']}, {'Q3-VL 8B #1', 'Q3-VL 8B #2'})
        self.assertEqual({m['label'] for m in matrix['models']}, {first['model_name'], second['model_name']})
        self.assertEqual(sum(t['observations'] for t in matrix['totals'].values()), 2)

    def test_named_comparison_keeps_actual_settings_and_separate_totals(self):
        records, specs = fixture()
        test = copy.deepcopy(specs[0]); test['timeout_seconds'] = 60
        specs[0]['timeout_seconds'] = 120
        test['name'] = 'Named 60-second deadline'
        variant = test['variants'][0]
        retained = []
        for model in range(4):
            record = copy.deepcopy(records[0])
            record.update(case_id=digest(['named-comparison', model]), model_id=f'm{model}',
                          test_definition=test, variant_definition=variant)
            retained.append(record)
        before = copy.deepcopy(retained)
        ordinary = build_report(retained, specs)['matrix']
        self.assertEqual(sum(not r['current'] for r in ordinary['rows']), 1)
        matrix = build_report(retained, specs, comparison_specs=[test])['matrix']
        self.assertFalse(any(not r['current'] for r in matrix['rows']))
        rows = [r for r in matrix['rows'] if r['test_id'] == test['id'] and r['variant_id'] == variant['id']]
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r['comparison_id'] for r in rows}), 2)
        self.assertEqual([r['name'] for r in rows if r['cells']], ['Named 60-second deadline'])
        self.assertEqual(sum(t['observations'] for t in matrix['totals'].values()), 4)
        old = copy.deepcopy(retained[0]); old['provenance']['workflow_code'] = 'older-runner'
        self.assertTrue(any(not r['current'] for r in build_report([old], specs, comparison_specs=[test])['matrix']['rows']))
        self.assertEqual(before, retained)