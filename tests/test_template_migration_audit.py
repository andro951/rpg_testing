"""The intentional migration audit rejects data loss and stale active exports."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from prompt_builder.builder import ROOT, compile_test
from scripts.audit_template_migration import BASELINE, audit, blob_id
from workbench.domain import write_json


class TemplateMigrationAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copytree(ROOT, self.root / 'prompt_builder/templates')
        self.before = {
            'test_specs/old_case.json': b'{"id":"old_case","variants":[]}\n',
            'prompts/patch-suite/old_case.txt': b'Historical prompt\n',
            'prompt-review/old_case.txt': b'Historical review\n',
            'results/model/raw.json': b'{"raw":"unchanged"}\n',
            'coverage_results/job/state.json': b'{"status":"completed"}\n',
            'optimization_results/session.json': b'{"candidate":"unchanged"}\n',
            'experiments/frozen/definition.json': b'{"task":"unchanged"}\n',
            'experiments/frozen/response.txt': b'Original response\n',
            'experiments/frozen/build.py': b'import retired_builder\n',
        }
        for name, raw in self.before.items():
            target = self.root / ('archives/pre-template-builder/' + name if name.startswith(
                ('test_specs/', 'prompts/patch-suite/', 'prompt-review/')) else name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        (self.root / 'experiments/frozen/build.py').write_text('import current_renderer\n')
        templates = self.root / 'prompt_builder/templates'
        write_json(templates / 'common/selection.json', {'test_cases': ['update_field'],
                   'output_formats': ['json_dot'], 'input_formats': ['normal_json']})
        # This is an intentionally one-case synthetic repository, not the production catalog.
        for case in (templates / 'test_cases').iterdir():
            if case.is_dir() and case.name != 'update_field':shutil.rmtree(case)
        for form in (templates / 'output_format').iterdir():
            if form.is_dir() and form.name != 'json_dot':shutil.rmtree(form)
        write_json(templates / 'common/coverage.json', {'schema_version': 1,
                   'test_cases': ['update_field'], 'output_formats': ['json_dot'], 'input_formats': ['normal_json']})
        self.current = compile_test('update_field', 'json_dot', input_formats=['normal_json'],
                                    root=templates, promotion_root=self.root)
        path = self.root / 'test_specs' / (self.current['id'] + '.json')
        write_json(path, self.current)
        write_json(self.root / 'evaluation/catalog.json', {'definitions': [{
            'id': self.current['id'], 'path': path.relative_to(self.root).as_posix(), 'scope': 'active',
            'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'variants': [v['id'] for v in self.current['variants']]}]})

    def run_audit(self):
        entries = {name: blob_id(raw) for name, raw in self.before.items()}
        objects = {blob_id(raw): raw for raw in self.before.values()}
        with patch('scripts.audit_template_migration.git_tree', return_value=entries), \
             patch('scripts.audit_template_migration.GitObjects') as reader:
            reader.return_value.__enter__.return_value.read.side_effect = objects.__getitem__
            return audit(self.root, BASELINE)

    def test_preserved_data_and_new_semantics_pass_without_equivalence_claim(self):
        result = self.run_audit()
        self.assertEqual(result['immutable_evidence_files_checked'], 5)
        self.assertEqual(result['active_definitions_checked'], 1)
        self.assertFalse(result['source_equivalence_claimed'])
        self.assertFalse(result['inference_performed'])
        self.assertFalse(result['files_modified'])

    def test_checkout_crlf_only_difference_is_allowed(self):
        path = self.root / 'archives/pre-template-builder/prompt-review/old_case.txt'
        path.write_bytes(self.before['prompt-review/old_case.txt'].replace(b'\n', b'\r\n'))
        path = self.root / 'experiments/frozen/response.txt'
        path.write_bytes(self.before['experiments/frozen/response.txt'].replace(b'\n', b'\r\n'))
        self.assertEqual(self.run_audit()['immutable_evidence_files_checked'], 5)

    def test_normalized_catalog_hash_accepts_lf_and_crlf_checkout(self):
        path = self.root / 'test_specs' / (self.current['id'] + '.json')
        raw = path.read_bytes().replace(b'\r\n', b'\n')
        catpath = self.root / 'evaluation/catalog.json'
        catalog = json.loads(catpath.read_text())
        catalog['definitions'][0]['source_sha256'] = hashlib.sha256(raw).hexdigest()
        write_json(catpath, catalog)
        for ending in (raw, raw.replace(b'\n', b'\r\n')):
            with self.subTest(crlf=b'\r\n' in ending):
                path.write_bytes(ending)
                self.assertEqual(self.run_audit()['active_definitions_checked'], 1)

    def test_stale_crlf_hash_and_unhashed_formatting_change_still_fail(self):
        path = self.root / 'test_specs' / (self.current['id'] + '.json')
        raw = path.read_bytes().replace(b'\r\n', b'\n')
        path.write_bytes(raw)
        catpath = self.root / 'evaluation/catalog.json'
        catalog = json.loads(catpath.read_text())
        catalog['definitions'][0]['source_sha256'] = hashlib.sha256(raw.replace(b'\n', b'\r\n')).hexdigest()
        write_json(catpath, catalog)
        with self.assertRaisesRegex(AssertionError, 'Catalog source hash is stale'):
            self.run_audit()
        catalog['definitions'][0]['source_sha256'] = hashlib.sha256(raw).hexdigest()
        write_json(catpath, catalog)
        path.write_bytes(b' ' + raw)  # Same JSON semantics, different saved bytes.
        with self.assertRaisesRegex(AssertionError, 'Catalog source hash is stale'):
            self.run_audit()

    def test_changed_archived_bytes_fail(self):
        (self.root / 'archives/pre-template-builder/prompt-review/old_case.txt').write_text('Edited review\n')
        with self.assertRaisesRegex(AssertionError, 'Archived baseline bytes changed'):
            self.run_audit()

    def test_changed_existing_evidence_fails(self):
        (self.root / 'results/model/raw.json').write_text('{"raw":"edited"}\n')
        with self.assertRaisesRegex(AssertionError, 'Immutable evidence changed'):
            self.run_audit()

    def test_active_definition_mismatch_fails(self):
        self.current['instructions'] += '\nUncompiled edit.'
        write_json(self.root / 'test_specs' / (self.current['id'] + '.json'), self.current)
        with self.assertRaisesRegex(AssertionError, 'freshly compiled templates/evaluator'):
            self.run_audit()

    def test_new_case_schema_or_old_package_fails(self):
        schema = self.root / 'prompt_builder/templates/test_cases/update_field/schema.json'
        schema.write_text('{}')
        with self.assertRaisesRegex(AssertionError, 'Per-case schema'):
            self.run_audit()
        schema.unlink()
        (self.root / 'test_builder').mkdir()
        with self.assertRaisesRegex(AssertionError, 'Obsolete test_builder'):
            self.run_audit()

    def test_invalid_catalog_pointer_fails(self):
        path = self.root / 'evaluation/catalog.json'
        catalog = json.loads(path.read_text())
        catalog['definitions'][0]['path'] = 'test_specs/missing.json'
        write_json(path, catalog)
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe'):
            self.run_audit()


if __name__ == '__main__':
    unittest.main()
