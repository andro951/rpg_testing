"""Catalog registrations are stable across Git's LF/CRLF checkout conversion."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.catalog import definition_source_sha256
from optimization.promotion import rebuild
from prompt_builder.builder import build, compile_test, install
from workbench.domain import read_json, write_json


def lf_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    path.write_bytes(text.encode('utf8'))


def crlf_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    path.write_bytes(text.replace('\n', '\r\n').encode('utf8'))


class CatalogSourceHashTests(unittest.TestCase):
    def test_only_physical_crlf_is_normalized_without_mutating_file(self):
        # Escaped newline data, Unicode and lone CR bytes are not rewritten.
        original = '{\n  "value": "é\\r\\n",\n  "other": 1\n}\n'.encode('utf8')
        expected = hashlib.sha256(original).hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'definition.json'
            for raw in (original, original.replace(b'\n', b'\r\n')):
                with self.subTest(raw=raw):
                    path.write_bytes(raw)
                    self.assertEqual(definition_source_sha256(path), expected)
                    self.assertEqual(path.read_bytes(), raw)
            for raw in (original.replace(b'  ', b' '), original.replace(b'1', b'2'),
                        b'\xef\xbb\xbf' + original, original.replace(b'\n', b'\r'),
                        original.replace(b'\\r\\n', b'\\n')):
                with self.subTest(changed=raw):
                    path.write_bytes(raw)
                    self.assertNotEqual(definition_source_sha256(path), expected)

    def test_installer_hashes_lf_and_crlf_definitions_identically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / 'build'
            build(output, cases=['update_field'], input_formats=['normal_json'])
            expected = None
            for ending, writer in [('lf', lf_write_json), ('crlf', crlf_write_json)]:
                with self.subTest(ending=ending):
                    repo = root / ending
                    repo.mkdir()
                    old = {'id': 'old', 'path': 'archives/old.json', 'scope': 'archived',
                           'source_sha256': 'saved-untouched-hash', 'variants': []}
                    for name, value in {'evaluation/catalog.json': {'definitions': [old]},
                            'evaluation/fixtures.json': {'fixtures': []},
                            'reporting/grouping_metadata.json': {},
                            'reporting/timing_expectations.json': {}}.items():
                        write_json(repo / name, value)
                    with patch('prompt_builder.builder.write_json', side_effect=writer):
                        install(output, repo, allow_subset=True)
                    entries = read_json(repo / 'evaluation/catalog.json')['definitions']
                    self.assertEqual(entries[0], old)
                    entry = entries[1]
                    source = repo / entry['path']
                    raw = source.read_bytes()
                    self.assertEqual(read_json(source), read_json(output / entry['path']))
                    self.assertEqual(entry['source_sha256'], hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest())
                    if ending == 'lf':
                        self.assertNotIn(b'\r\n', raw)
                    if ending == 'crlf':
                        self.assertIn(b'\r\n', raw)
                        self.assertNotEqual(entry['source_sha256'], hashlib.sha256(raw).hexdigest())
                        self.assertEqual(entry['source_sha256'], expected)
                    expected = entry['source_sha256']

    def test_promotion_catalog_writer_uses_same_lf_hash(self):
        # Isolate export bookkeeping; promotion semantics have separate tests.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            test = compile_test('update_field', 'json_dot', input_formats=['normal_json'], promotion_root=root)
            source = root / 'test_specs' / (test['id'] + '.json')
            write_json(source, test)
            write_json(root / 'optimization/active_promotions.json',
                       {'recipes': {'synthetic': {'base_test': test}}})
            old = {'id': 'old', 'path': 'archives/old.json', 'source_sha256': 'keep'}
            write_json(root / 'evaluation/catalog.json', {'definitions': [old,
                       {'id': test['id'], 'path': source.relative_to(root).as_posix(), 'source_sha256': 'stale'}]})
            with patch('optimization.promotion.apply', return_value=copy.deepcopy(test)), \
                 patch('workbench.domain.write_json', side_effect=crlf_write_json):
                rebuild(root)
            raw = source.read_bytes()
            self.assertIn(b'\r\n', raw)
            entries = read_json(root / 'evaluation/catalog.json')['definitions']
            self.assertEqual(entries[0], old)
            self.assertEqual(entries[1]['source_sha256'], hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest())
            self.assertEqual(read_json(source), test)


if __name__ == '__main__':
    unittest.main()
