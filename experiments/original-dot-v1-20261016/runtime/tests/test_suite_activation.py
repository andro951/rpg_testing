"""Finalized prompts stay runnable while prior study evidence remains immutable."""
import hashlib
import unittest
from pathlib import Path
from optimization.storage import Store
from workbench.domain import load_tests as load_catalog, read_json

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/'archives/suite-before-activation-2026-10-15'


class SuiteActivationTests(unittest.TestCase):
    def test_archive_preserves_every_recorded_file_and_its_bytes(self):
        manifest=read_json(ARCHIVE/'manifest.json')
        self.assertEqual(manifest['status'],'archived')
        self.assertEqual(len(list((ARCHIVE/'results').glob('*/*.json'))),1740)
        self.assertEqual(len(list((ARCHIVE/'draft-suite/test_specs').glob('*.json'))),20)
        self.assertEqual(len(list((ARCHIVE/'draft-suite/prompt-review').glob('*.txt'))),59)
        seen=set()
        for entry in manifest['files']:
            path=(ARCHIVE/entry['file']).resolve()
            self.assertTrue(path.is_relative_to(ARCHIVE.resolve()))
            self.assertNotIn(entry['file'],seen)
            seen.add(entry['file'])
            self.assertEqual(path.stat().st_size,entry['bytes'])
            checksum=hashlib.sha256()
            with path.open('rb') as handle:
                for chunk in iter(lambda:handle.read(1024*1024),b''):checksum.update(chunk)
            self.assertEqual(checksum.hexdigest(),entry['sha256'],entry['file'])

    def test_default_catalog_contains_only_finalized_new_cases(self):
        tests=load_catalog(ROOT/'test_specs')
        self.assertEqual(len(tests),21)
        self.assertEqual(sum(len(t['variants'])*t['repetitions'] for t in tests),186)
        reviews=read_json(ROOT/'test_builder/reviews.json')
        for test in tests:
            self.assertEqual(test['prompt_builder']['method'],'value_patch')
            self.assertEqual(test['prompt_builder']['review_status'],'accepted')
            for role in ('assistant','isaac'):
                self.assertEqual(reviews[test['id']][role]['status'],'accepted')
                self.assertEqual(reviews[test['id']][role]['prompt_digest'],test['prompt_builder']['prompt_digest'])
        self.assertEqual(read_json(ROOT/'prompts/patch-suite/manifest.json')['status'],'ready')

    def test_archived_optimization_sessions_are_readable_but_not_in_active_store(self):
        archived=Store(ARCHIVE).list()
        self.assertEqual(len(archived),2)
        old_ids={session['id'] for session in archived}
        self.assertTrue(old_ids.isdisjoint(session['id'] for session in Store(ROOT).list()))
