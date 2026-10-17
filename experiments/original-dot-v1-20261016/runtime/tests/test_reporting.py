import copy
import tempfile
import unittest
import zipfile
from pathlib import Path

from reporting.report import MAPPING, build_report, classify, load_evidence, write_report
from workbench.domain import ResultStore, code_fingerprint, digest


def fixture():
    records, specs = [], []
    for (test_id, variant_id), (kind, operation, representation) in MAPPING.items():
        test = next((test for test in specs if test['id'] == test_id), None)
        if test is None:
            test = {'id': test_id, 'repetitions': 1, 'variants': []}
            specs.append(test)
        variant = {'id': variant_id, 'expected_answers': {'index': '73'}}
        test['variants'].append(variant)
        record = {'case_id': digest([test_id, variant_id]), 'model_id': 'mock', 'status': 'completed',
                  'test_id': test_id, 'variant_id': variant_id, 'test_definition': test,
                  'variant_definition': variant, 'repetition': 0, 'simulated': True,
                  'provenance': {'workflow_code': code_fingerprint()}, 'score': {'exact_match': True},
                  'outputs': {'index': '73'}, 'pipeline_seconds': 1.0,
                  'calls': [{'text': '</script><script>alert(1)</script>'}],
                  'target': {'backend_version': 'log prefix\nversion: stable'},
                  'load': {'context': {'allocated': 100}}, 'policy': 'mock-v1'}
        records.append(record)
    return copy.deepcopy(records), specs


class ReportingTests(unittest.TestCase):
    def test_mapping_and_matched_denominator(self):
        records, specs = fixture()
        report = build_report(records, specs)
        self.assertEqual(len(MAPPING), 36)
        self.assertEqual(len(report['cohorts']), 1)
        self.assertEqual(len(report['cohorts'][0]['matched']['locate']), 6)
        records.pop()
        report = build_report(records, specs)
        self.assertEqual(len(report['cohorts'][0]['matched']['locate']), 5)
        self.assertEqual(sum(cell['outcome'] == 'missing' for cell in report['cohorts'][0]['cells']), 1)

    def test_failure_categories(self):
        records, _ = fixture()
        record = records[-1]
        record['score'] = {'exact_match': False}
        record['outputs']['index'] = 'The index is 73.'
        self.assertEqual(classify(record, 'locate'), 'correct_index_wrong_format')
        for value in ('-73', '73.2', '73 or 74', 'none'):
            record['outputs']['index'] = value
            self.assertEqual(classify(record, 'locate'), 'wrong_or_ambiguous_index')
        record['timed_out'] = True
        self.assertEqual(classify(record, 'locate'), 'timeout')
        record['status'] = 'error'
        self.assertEqual(classify(record, 'locate'), 'error')

    def test_history_protocol_artifacts_and_no_mutation(self):
        records, specs = fixture()
        original = copy.deepcopy(records)
        historical = copy.deepcopy(records[0])
        historical['case_id'] = digest('history')
        historical['provenance']['workflow_code'] = 'old'
        records.append(historical)
        records[1]['target']['backend_version'] = 'different log\nversion: stable'
        report = build_report(records, specs)
        self.assertEqual(len(report['historical']), 1)
        self.assertEqual(len(report['cohorts']), 1)
        self.assertEqual(records[0], original[0])
        records[1]['load']['context']['allocated'] = 200
        self.assertEqual(len(build_report(records, specs)['cohorts']), 2)
        records[1]['artifact_identity'] = {'files': [{'name': 'other.gguf'}]}
        self.assertEqual(len(build_report(records, specs)['models']), 2)

    def test_duplicates_conflicts_and_ambiguity(self):
        records, specs = fixture()
        report = build_report(records + [records[0]], specs)
        self.assertEqual(len(report['evidence']), 36)
        duplicate = copy.deepcopy(records[0])
        duplicate['score']['exact_match'] = False
        with self.assertRaises(ValueError):
            build_report(records + [duplicate], specs)
        duplicate['case_id'] = digest('another identity')
        report = build_report(records + [duplicate], specs)
        self.assertEqual(sum(cell['outcome'] == 'ambiguous' for cell in report['cohorts'][0]['cells']), 1)
        self.assertEqual(len(report['cohorts'][0]['matched']['patch']), 5)

    def test_timeout_timing_and_invalid_measurement(self):
        records, specs = fixture()
        records[0]['timed_out'] = True
        records[1]['measurement_valid'] = False
        report = build_report(records, specs)
        self.assertIsNone(report['cohorts'][0]['rows'][0]['seconds'])
        self.assertEqual(len(report['cohorts'][0]['matched']['patch']), 5)

    def test_unknown_scores_and_absent_latency_are_not_zero(self):
        records, specs = fixture()
        records[0]['score']['exact_match'] = None
        records[1].pop('pipeline_seconds')
        report = build_report(records, specs)
        self.assertEqual(report['cohorts'][0]['rows'][0]['outcome'], 'unscored')
        self.assertIsNone(report['cohorts'][0]['rows'][1]['seconds'])
        self.assertEqual(len(report['cohorts'][0]['matched']['patch']), 5)

    def test_simulation_policy_version_and_placement_stay_separate(self):
        for field in ('simulation', 'policy', 'version', 'placement'):
            records, specs = fixture()
            if field == 'simulation':
                records[0]['simulated'] = False
            elif field == 'policy':
                records[0]['policy'] = 'another-policy'
            elif field == 'version':
                records[0]['target']['backend_version'] = 'version: different'
            else:
                records[0]['load']['placement'] = {'gpu_layers': 2}
            report = build_report(records, specs)
            self.assertEqual(len(report['models']) if field == 'placement' else len(report['cohorts']), 2)

    def test_archive_duplicate_keys_rejected(self):
        records, _ = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'evidence.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('mock/' + records[0]['case_id'] + '.json', '{"status":"completed","status":"error"}')
            loaded, errors = load_evidence(path)
            self.assertEqual(loaded, [])
            self.assertIn('Duplicate JSON key', errors[0]['error'])

    def test_directory_zip_corruption_and_safe_export(self):
        records, specs = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'results'
            saved = ResultStore(source).save(records[0])
            before = saved.read_bytes()
            loaded, problems = load_evidence(source)
            self.assertFalse(problems)
            archive_path = root / 'evidence.zip'
            with zipfile.ZipFile(archive_path, 'w') as archive:
                archive.write(saved, 'results/' + saved.parent.name + '/' + saved.name)
            self.assertEqual(load_evidence(archive_path)[0], loaded)
            report = build_report(loaded, specs)
            output = write_report(report, root / 'report.html', (source,))
            html = output.read_text(encoding='utf-8')
            self.assertNotIn('</script><script>alert', html)
            self.assertIn('\\u003c/script>', html)
            self.assertEqual(saved.read_bytes(), before)
            with self.assertRaises(ValueError):
                write_report(report, source / 'report.html', (source,))
            saved.write_text('{}')
            self.assertEqual(len(load_evidence(source)[1]), 1)
            with zipfile.ZipFile(archive_path, 'w') as archive:
                archive.writestr('../unsafe.json', '{}')
            with self.assertRaises(ValueError):
                load_evidence(archive_path)