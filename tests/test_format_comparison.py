import csv
import tempfile
import unittest
from pathlib import Path
from reporting.format_comparison import format_pair, load_comparison
from reporting.report import build_report
from tests.test_reporting import fixture


class FormatComparisonTests(unittest.TestCase):
    def write_csv(self, root, rows):
        path = root / 'comparison.csv'
        with path.open('w', newline='', encoding='utf8') as stream:
            writer = csv.DictWriter(stream, fieldnames=['model', 'model_id', 'case', 'input_format', 'output_format', 'outcome', 'repetition'])
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_format_metadata_is_derived_not_a_fixed_catalog(self):
        self.assertEqual(format_pair({'prompt_builder': {'method': 'new_output'}}, {'id': 'new_input'}), {'input': 'new_input', 'output': 'new_output'})
        self.assertEqual(format_pair({}, {'state_presentation': 'full_paths', 'result': {'representation': 'dot_patch_v1'}}), {'input': 'full_paths', 'output': 'dot_patch_v1'})
        self.assertIsNone(format_pair({}, {}))
        records, specs = fixture()
        report = build_report(records, specs)
        self.assertTrue(all('formats' in row for row in report['matrix']['rows']))

    def test_import_preserves_outcomes_and_unknown_future_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = [dict(model='Example', model_id='m', case=str(index), input_format='new_input', output_format='new_output', outcome=state, repetition='0') for index, state in enumerate(['PASS', 'FAIL', 'TIMEOUT', 'PARSER_GAP'])]
            result = load_comparison(self.write_csv(Path(tmp), rows))
            self.assertEqual([row['outcome'] for row in result['observations']], ['pass', 'fail', 'timeout', 'parser_gap'])
            self.assertEqual(result['models'], [{'id': 'm', 'label': 'Example'}])
            self.assertEqual(len(result['source_sha256']), 64)

    def test_rejects_duplicate_and_invalid_rows_instead_of_cherry_picking(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = dict(model='Example', model_id='m', case='a', input_format='i', output_format='o', outcome='PASS', repetition='0')
            for rows in ([row, row], [dict(row, outcome='UNKNOWN')], [dict(row, input_format='')]):
                with self.assertRaises(ValueError):
                    load_comparison(self.write_csv(Path(tmp), rows))
