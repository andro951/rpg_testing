"""Reviewed suite relocation must preserve exact pinned evidence bytes."""
import hashlib
import json
from pathlib import Path
import unittest

from tests import test_template_migration_audit as fixtures
from scripts.audit_template_migration import SUITE_ARCHIVE, SUITE_ARCHIVE_SOURCE, BASELINE
from workbench.domain import write_json


class SuiteArchiveMigrationAuditTests(unittest.TestCase):
    setUp = fixtures.TemplateMigrationAuditTests.setUp
    run_audit = fixtures.TemplateMigrationAuditTests.run_audit

    def archive(self, names=None, keep_original=False):
        names = names or ['results/model/raw.json', 'coverage_results/job/state.json',
                          'optimization_results/session.json']
        files = []
        for name in names:
            original = self.root / name
            raw = original.read_bytes()
            target = self.root / SUITE_ARCHIVE / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            files.append({'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
            if not keep_original:
                original.unlink()
        manifest = {'source_commit': SUITE_ARCHIVE_SOURCE, 'reason': 'Reviewed preservation', 'files': files}
        self.write_manifest(manifest)
        return manifest

    def write_manifest(self, manifest):
        write_json(self.root / SUITE_ARCHIVE / 'manifest.json', manifest)

    def test_all_three_evidence_categories_relocate(self):
        self.archive()
        result = self.run_audit()
        self.assertEqual(result['immutable_evidence_files_checked'], 5)
        self.assertEqual(result['archived_suite_evidence_files_checked'], 3)
        self.assertFalse(result['files_modified'])
        self.assertFalse(result['inference_performed'])

    def test_newer_nonbaseline_metadata_does_not_authorize_other_relocations(self):
        manifest = self.archive()
        manifest['files'].append({'path': 'prompt_builder/templates/new.json', 'bytes': 0, 'sha256': '0'*64})
        manifest['files'].append({'path': 'results/new-model/new.json', 'bytes': 0, 'sha256': '0'*64})
        self.write_manifest(manifest)
        self.assertEqual(self.run_audit()['archived_suite_evidence_files_checked'], 3)
        (self.root/'experiments/frozen/response.txt').unlink()
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe.*experiments/frozen/response.txt'):
            self.run_audit()

    def test_wrong_source_commit_fails(self):
        manifest = self.archive()
        manifest['source_commit'] = BASELINE
        self.write_manifest(manifest)
        with self.assertRaisesRegex(AssertionError, 'Unexpected suite archive source commit'):
            self.run_audit()

    def test_missing_manifest_or_unlisted_evidence_fails(self):
        manifest = self.archive()
        path = self.root/SUITE_ARCHIVE/'manifest.json'
        path.unlink()
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe.*manifest.json'):
            self.run_audit()
        manifest['files'].pop()
        self.write_manifest(manifest)
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe.*optimization_results/session.json'):
            self.run_audit()

    def test_missing_archive_and_tampered_hash_or_size_fail(self):
        manifest = self.archive()
        path = self.root/SUITE_ARCHIVE/'results/model/raw.json'
        original = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe.*raw.json'):
            self.run_audit()
        path.write_bytes(original + b' ')
        with self.assertRaisesRegex(AssertionError, 'byte count changed'):
            self.run_audit()
        path.write_bytes(original.replace(b'unchanged', b'different'))
        with self.assertRaisesRegex(AssertionError, 'SHA-256 changed'):
            self.run_audit()

    def test_manifest_cannot_certify_changed_blob_or_normalize_newlines(self):
        manifest = self.archive()
        path = self.root/SUITE_ARCHIVE/'results/model/raw.json'
        original = path.read_bytes()
        for raw in (original.replace(b'unchanged', b'different'), original.replace(b'\n', b'\r\n')):
            with self.subTest(raw=raw):
                path.write_bytes(raw)
                manifest['files'][0].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                self.write_manifest(manifest)
                with self.assertRaisesRegex(AssertionError, 'differs from pinned baseline bytes'):
                    self.run_audit()

    def test_relocation_cannot_conceal_changed_original(self):
        self.archive(keep_original=True)
        (self.root/'coverage_results/job/state.json').write_bytes(b'{"status":"edited"}\n')
        with self.assertRaisesRegex(AssertionError, 'Immutable evidence changed'):
            self.run_audit()

    def test_invalid_or_duplicate_metadata_rejected_even_when_not_baseline(self):
        manifest = self.archive()
        original = dict(manifest['files'][0])
        for field, value, expected in [('bytes', True, 'byte count'), ('bytes', -1, 'byte count'),
                                        ('sha256', 'invalid', 'SHA-256'), ('redirect', 'elsewhere', 'manifest entry')]:
            with self.subTest(field=field, value=value):
                manifest['files'][0] = {**original, field: value}
                self.write_manifest(manifest)
                with self.assertRaisesRegex(AssertionError, expected):
                    self.run_audit()
        manifest['files'][0] = original
        manifest['files'].extend([{'path':'reporting/new.json','bytes':0,'sha256':'0'*64}]*2)
        self.write_manifest(manifest)
        with self.assertRaisesRegex(AssertionError, 'Duplicate suite archive path'):
            self.run_audit()

    def test_unsafe_paths_rejected_even_if_not_pinned(self):
        manifest = self.archive()
        original = dict(manifest['files'][0])
        for name in ('../results/a.json','/results/a.json','results/../a.json','results//a.json',
                     'results/./a.json','results\\a.json','C:/results/a.json','results/a.json:stream','.'):
            with self.subTest(name=name):
                manifest['files'][0] = {**original, 'path':name}
                self.write_manifest(manifest)
                with self.assertRaisesRegex(AssertionError, 'Unsafe suite archive path'):
                    self.run_audit()

    def test_symlinked_archive_file_and_internal_parent_rejected(self):
        self.archive()
        path = self.root/SUITE_ARCHIVE/'results/model/raw.json'
        backup = self.root/'unchanged.json'
        backup.write_bytes(path.read_bytes())
        path.unlink()
        try:
            path.symlink_to(backup)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(str(exc))
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe'):
            self.run_audit()
        path.unlink();path.write_bytes(backup.read_bytes())
        directory = path.parent
        moved = directory.with_name('actual-model')
        directory.rename(moved);directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe'):
            self.run_audit()

    def test_dangling_original_parent_symlink_cannot_be_hidden(self):
        self.archive()
        directory = self.root/'coverage_results/job'
        directory.rmdir()
        try:
            directory.symlink_to(self.root/'absent', target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(str(exc))
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe.*coverage_results/job/state.json'):
            self.run_audit()

    def test_duplicate_between_reviewed_archives_rejected(self):
        self.archive(keep_original=True)
        fixtures.TemplateMigrationAuditTests.archive_result(self)
        with self.assertRaisesRegex(AssertionError, 'Duplicate evidence relocation'):
            self.run_audit()

    def test_arbitrary_archive_is_not_searched(self):
        self.archive()
        (self.root/SUITE_ARCHIVE).rename(self.root/'archives/unreviewed-suite')
        with self.assertRaisesRegex(AssertionError, 'Missing or unsafe'):
            self.run_audit()


if __name__ == '__main__':
    unittest.main()
