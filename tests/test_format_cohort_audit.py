import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit_format_cohort import (check_cohort, ensure_output_location,
                                        read_original, verify_unchanged, write_immutable)


class FormatCohortAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, result):
        path = self.root / 'source.json'
        data = json.dumps(result).encode()
        path.write_bytes(data)
        return {'result_file': str(path), 'result_sha256': hashlib.sha256(data).hexdigest()}

    def test_checksum_mismatch(self):
        row = self.source({'outputs': {'patch': 'none'}})
        row['result_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            read_original(row)

    def test_missing_and_nontext_output(self):
        for result in ({}, {'calls': [{'step': 'patch'}]},
                       {'outputs': {'patch': None}}):
            with self.subTest(result=result), self.assertRaises(ValueError):
                read_original(self.source(result))

    def test_mismatched_call_output(self):
        row = self.source({'outputs': {'patch': 'none'},
                           'calls': [{'step': 'patch', 'text': 'different'}]})
        with self.assertRaisesRegex(ValueError, 'text mismatch'):
            read_original(row)

    def test_saved_empty_output_is_preserved(self):
        row = self.source({'outputs': {'patch': ''}, 'score': {'exact_match': False},
                           'calls': [{'step': 'patch', 'text': ''}]})
        self.assertEqual(read_original(row), ('', {'exact_match': False}, 'outputs.patch'))

    def test_original_call_text_without_pipeline_output(self):
        row = self.source({'outputs': {}, 'calls': [{'step': 'patch', 'text': 'partial'}]})
        self.assertEqual(read_original(row), ('partial', None, 'calls:last_patch.text'))

    def test_exact_cohort_size(self):
        for size in (0, 2231, 2233):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, '2232-row'):
                check_cohort([{}] * size)

    def test_duplicate_cohort_rejected(self):
        row = dict(model_id='m', case='c', input_format='normal_json', output_format='json_dot')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            check_cohort([row] * 2232)

    def test_conflicting_artifact_never_replaced(self):
        output = self.root / 'output'
        write_immutable(output, {'a.json': 'original'})
        with self.assertRaises(FileExistsError):
            write_immutable(output, {'b.json': 'new', 'a.json': 'different'})
        self.assertEqual((output / 'a.json').read_text(), 'original')
        self.assertFalse((output / 'b.json').exists())
        write_immutable(output, {'a.json': 'original'})

    def test_evidence_directory_protection(self):
        package = self.root / 'package' / 'results.zip'
        source = self.root / 'source-run' / 'frozen' / 'results' / 'model' / 'result.json'
        rows = [dict(result_file=str(source), source_run='source-run')]
        for target in (package.parent, package.parent / 'audit', source.parent,
                       self.root / 'source-run' / 'reports'):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'original evidence'):
                ensure_output_location(target, package, rows)
        self.assertEqual(ensure_output_location(self.root / 'separate', package, rows),
                         (self.root / 'separate').resolve())

    def test_source_change_detected(self):
        row = self.source({'outputs': {'patch': 'none'}})
        sources = {Path(row['result_file']): row['result_sha256']}
        verify_unchanged(sources)
        Path(row['result_file']).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'changed during audit'):
            verify_unchanged(sources)


if __name__ == '__main__':
    unittest.main()
