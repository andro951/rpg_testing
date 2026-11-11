"""The intentional migration audit rejects data loss and stale active exports."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from prompt_builder.builder import ROOT, compile_test
from scripts.audit_template_migration import BASELINE, RESULT_ARCHIVE, RESULT_ARCHIVE_SOURCE, audit, blob_id
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

    def archive_result(self, name='results/model/raw.json', keep_original=False):
        original = self.root / name
        archived = self.root / RESULT_ARCHIVE / name
        archived.parent.mkdir(parents=True, exist_ok=True)
        raw = original.read_bytes()
        archived.write_bytes(raw)
        if not keep_original:
            original.unlink()
        manifest = {'source_commit': RESULT_ARCHIVE_SOURCE, 'files': [{
            'original_path': name, 'git_blob': blob_id(raw),
            'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}]}
        write_json(self.root / RESULT_ARCHIVE / 'manifest.json', manifest)
        return archived, manifest

    def write_archive_manifest(self, manifest):
        write_json(self.root / RESULT_ARCHIVE / 'manifest.json', manifest)

    def test_reviewed_result_relocation_preserves_pinned_bytes(self):
        self.archive_result()
        result = self.run_audit()
        self.assertEqual(result['baseline'], BASELINE)
        self.assertEqual(result['immutable_evidence_files_checked'], 5)
        self.assertEqual(result['archived_result_files_checked'], 1)
        self.assertFalse(result['inference_performed'])
        self.assertFalse(result['files_modified'])

    def test_missing_evidence_without_relocation_fails(self):
        (self.root / 'results/model/raw.json').unlink()
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe file: results/model/raw.json'):
            self.run_audit()

    def test_missing_relocation_manifest_fails(self):
        self.archive_result()
        (self.root / RESULT_ARCHIVE / 'manifest.json').unlink()
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe.*manifest.json'):
            self.run_audit()

    def test_missing_or_misplaced_archive_fails(self):
        archived, _ = self.archive_result()
        archived.rename(archived.with_name('wrong.json'))
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe.*raw.json'):
            self.run_audit()

    def test_unreviewed_archive_location_is_not_searched(self):
        self.archive_result()
        (self.root / RESULT_ARCHIVE).rename(self.root / 'archives/unreviewed-results')
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe file: results/model/raw.json'):
            self.run_audit()

    def test_unlisted_relocated_result_fails(self):
        self.archive_result()
        name = 'results/model/other.json'
        self.before[name] = b'{"raw":"other"}\n'
        (self.root / name).write_bytes(self.before[name])
        self.archive_result(name, keep_original=True)  # Manifest lists only the other result.
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe file: results/model/raw.json'):
            self.run_audit()

    def test_changed_relocated_result_fails_even_if_original_is_present(self):
        archived, _ = self.archive_result(keep_original=True)
        archived.write_bytes(archived.read_bytes().replace(b'unchanged', b'different'))
        with self.assertRaisesRegex(AssertionError, 'Archived result SHA-256 changed'):
            self.run_audit()

    def test_valid_archive_cannot_hide_changed_original(self):
        self.archive_result(keep_original=True)
        (self.root / 'results/model/raw.json').write_bytes(b'{"raw":"edited"}\n')
        with self.assertRaisesRegex(AssertionError, 'Immutable evidence changed'):
            self.run_audit()

    def test_wrong_relocation_source_commit_fails(self):
        _, manifest = self.archive_result()
        manifest['source_commit'] = BASELINE
        self.write_archive_manifest(manifest)
        with self.assertRaisesRegex(AssertionError, 'Unexpected result archive source commit'):
            self.run_audit()

    def test_wrong_relocation_paths_fail(self):
        _, manifest = self.archive_result()
        for name in ('results/model/missing.json', 'coverage_results/job/state.json',
                     '../results/model/raw.json', 'results/model/../model/raw.json',
                     'results\\model\\raw.json', '/results/model/raw.json'):
            with self.subTest(name=name):
                manifest['files'][0]['original_path'] = name
                self.write_archive_manifest(manifest)
                with self.assertRaisesRegex(AssertionError, 'not pinned baseline evidence'):
                    self.run_audit()

    def test_duplicate_relocation_paths_fail(self):
        _, manifest = self.archive_result()
        manifest['files'].append(dict(manifest['files'][0]))
        self.write_archive_manifest(manifest)
        with self.assertRaisesRegex(AssertionError, 'Duplicate result archive path'):
            self.run_audit()

    def test_incorrect_relocation_metadata_fails(self):
        _, manifest = self.archive_result()
        original_entry = dict(manifest['files'][0])
        for field, value, message in (
                ('git_blob', '0' * 40, 'blob differs from pinned baseline'),
                ('sha256', '0' * 64, 'Archived result SHA-256 changed'),
                ('sha256', 'bad hash', 'Invalid result archive SHA-256'),
                ('bytes', original_entry['bytes'] + 1, 'Archived result byte count changed'),
                ('bytes', True, 'Invalid result archive byte count')):
            with self.subTest(field=field, value=value):
                manifest['files'][0] = {**original_entry, field: value}
                self.write_archive_manifest(manifest)
                with self.assertRaisesRegex(AssertionError, message):
                    self.run_audit()

    def test_manifest_cannot_authorize_changed_bytes_or_newline_normalization(self):
        archived, manifest = self.archive_result()
        original = archived.read_bytes()
        for raw in (original.replace(b'unchanged', b'different'), original.replace(b'\n', b'\r\n')):
            with self.subTest(raw=raw):
                archived.write_bytes(raw)
                manifest['files'][0]['bytes'] = len(raw)
                manifest['files'][0]['sha256'] = hashlib.sha256(raw).hexdigest()
                self.write_archive_manifest(manifest)
                with self.assertRaisesRegex(AssertionError, 'differs from pinned baseline bytes'):
                    self.run_audit()
                manifest['files'][0]['git_blob'] = blob_id(raw)
                self.write_archive_manifest(manifest)
                with self.assertRaisesRegex(AssertionError, 'blob differs from pinned baseline'):
                    self.run_audit()
                manifest['files'][0]['git_blob'] = blob_id(original)

    def test_manifest_cannot_redirect_archive_destination(self):
        _, manifest = self.archive_result()
        manifest['files'][0]['archived_path'] = 'elsewhere/raw.json'
        self.write_archive_manifest(manifest)
        with self.assertRaisesRegex(AssertionError, 'Invalid result archive manifest entry'):
            self.run_audit()

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
