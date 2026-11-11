"""Full-model orchestration must enforce the same suite contract as Run all."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from optimization import coverage
from optimization.storage import Store
from prompt_builder.builder import ROOT, build, install, compile_test
from workbench.controller import Controller
from workbench.domain import digest, experiment_spec, read_json, write_json
from workbench.judgements import load_tests as load_suite_tests
from workbench.workflows import messages


class OproScopeGuardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'repo'
        self.root.mkdir()
        self.app = Controller(self.root, demo=True)
        self.templates = self.root / 'prompt_builder/templates'
        self.output = self.root.parent / 'build'

    def modern(self, partial=False):
        shutil.copytree(ROOT, self.templates)
        for name, value in {'evaluation/catalog.json': {'definitions': []},
                            'evaluation/fixtures.json': {'fixtures': []},
                            'reporting/grouping_metadata.json': {},
                            'reporting/timing_expectations.json': {}}.items():
            write_json(self.root / name, value)
        options = {'cases': ['update_field'], 'output_formats': ['json_dot']} if partial else {}
        build(self.output, root=self.templates, **options)
        install(self.output, self.root, allow_subset=partial)

    def test_markerless_legacy_scope_shape_and_digest_unchanged(self):
        write_json(self.root / 'test_specs/example.json', {**compile_test('update_field', 'json_dot'), 'id': 'example'})
        tests = load_suite_tests(self.root / 'test_specs')
        expected = {'workflow': coverage.code_fingerprint(), 'definitions': [
            {'test_id': t['id'], 'variant_id': v['id'], 'definition': digest(experiment_spec(t, v)),
             'messages': digest(messages(t, v['steps'][0], {}, v)), 'repetitions': t.get('repetitions', 1)}
            for t in tests for v in t['variants'] if v.get('enabled', True)]}
        with patch.object(coverage, 'load_tests', wraps=load_suite_tests) as read_tests:
            actual = coverage.scope(self.root)
        self.assertEqual(actual, expected)
        self.assertEqual(digest(actual), digest(expected))
        read_tests.assert_called_once_with(self.root / 'test_specs')

    def test_modern_subset_missing_and_stale_scope_rejected(self):
        self.modern(partial=True)
        with self.assertRaisesRegex(ValueError, 'Run all requires complete'):
            coverage.scope(self.root)
        path = self.root / 'prompts/current-suite/manifest.json'
        manifest = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'manifest is missing'):
            coverage.scope(self.root)
        path.write_bytes(manifest)
        source = self.templates / 'common/allowed_changes.txt'
        source.write_text(source.read_text() + '\nEdited after build.')
        with self.assertRaisesRegex(ValueError, 'sources are stale'):
            coverage.scope(self.root)

    def test_complete_scope_stays_same_shape_and_freezes_372_definitions(self):
        self.modern()
        frozen = coverage.scope(self.root)
        self.assertEqual(set(frozen), {'workflow', 'definitions'})
        self.assertEqual(len(frozen['definitions']), 372)
        self.assertEqual(sum(row['repetitions'] for row in frozen['definitions']), 372)

    def test_advance_persists_invalid_scope_without_advancing_workers(self):
        self.modern(partial=True)
        frozen = {'workflow': 'preserved', 'definitions': [{'original': 'scope'}]}
        state = {'id': 'blocked-scope', 'status': 'pending', 'scope': frozen,
                 'suite_digest': digest(frozen), 'workers': [
                     {'id': 'desktop', 'kind': 'local', 'models': ['model'], 'status': 'pending'},
                     {'id': 'unity', 'kind': 'unity', 'status': 'queued', 'receipt': {'job_id': '123'}}]}
        coverage.save(self.root, state)
        with patch.object(self.app, 'run') as run, \
             patch.object(coverage, 'summarize') as summarize, \
             patch('optimization.coverage_unity.advance') as remote:
            actual = coverage.resume(self.app, state['id'])
        run.assert_not_called()
        summarize.assert_not_called()
        remote.assert_not_called()
        self.assertEqual(actual['status'], 'blocked')
        self.assertIn('370 distinct prompts', actual['scope_validation_error'])
        self.assertEqual(actual['scope'], frozen)
        self.assertEqual(actual['suite_digest'], digest(frozen))
        self.assertEqual(actual['workers'], state['workers'])
        self.assertEqual(coverage.read_state(self.root, state['id']), actual)
        with patch.object(self.app, 'start') as start:
            self.assertIsNone(coverage.restore_pending(self.app))
        start.assert_not_called()

    def test_valid_but_changed_scope_requires_explicit_resume_after_restart(self):
        frozen = {'workflow': 'frozen', 'definitions': []}
        state = {'id': 'changed-scope', 'status': 'pending', 'scope': frozen,
                 'suite_digest': digest(frozen), 'workers': [
                     {'id': 'unity', 'kind': 'unity', 'status': 'queued', 'receipt': {'job_id': '123'}}]}
        coverage.save(self.root, state)
        with patch.object(coverage, 'scope', return_value={'workflow': 'changed', 'definitions': []}), \
             patch.object(self.app, 'run') as run, \
             patch('optimization.coverage_unity.advance') as remote:
            actual = coverage.resume(self.app, state['id'])
        run.assert_not_called()
        remote.assert_not_called()
        self.assertEqual(actual['status'], 'blocked')
        self.assertIn('differs from the frozen', actual['scope_validation_error'])
        self.assertEqual(actual['scope'], frozen)
        self.assertEqual(actual['suite_digest'], digest(frozen))
        self.assertEqual(actual['workers'], state['workers'])
        self.assertEqual(coverage.read_state(self.root, state['id']), actual)
        with patch.object(self.app, 'start') as start:
            self.assertIsNone(coverage.restore_pending(self.app))
        start.assert_not_called()

    def session(self):
        session = {'id': 'synthetic', 'cohort': {'models': []}, 'observations': []}
        Store(self.root).save(session)
        candidate = {'system': 'Synthetic', 'user': 'Synthetic'}
        return session, candidate, digest({'session': session['id'], 'candidate': candidate})

    def test_after_success_saves_scope_failure_without_retry_or_fabricated_snapshot(self):
        self.modern(partial=True)
        session, candidate, key = self.session()
        with patch.object(coverage, 'promote', side_effect=lambda *_: coverage.scope(self.root)), \
             patch.object(coverage, 'scope', wraps=coverage.scope) as scope, \
             patch('optimization.engine.top_three', return_value=[{'candidate': candidate}]):
            state = coverage.after_success(self.app, session['id'])
        self.assertEqual(scope.call_count, 1)
        self.assertEqual(state['status'], 'blocked')
        self.assertNotIn('scope', state)
        self.assertNotIn('suite_digest', state)
        self.assertEqual(state['workers'], [])
        self.assertEqual(self.app.coverage_id, key)
        self.assertEqual(coverage.read_state(self.root, key), state)

    def test_interrupted_transaction_and_receipts_preserved_for_explicit_resume(self):
        session, candidate, key = self.session()
        transaction = {'before': {}, 'after': {}, 'recipes': {}}
        original = {'id': key, 'status': 'promoting', 'promotion': transaction,
                    'workers': [{'id': 'unity', 'kind': 'unity', 'status': 'queued', 'receipt': {'job_id': '123'}}]}
        coverage.save(self.root, original)
        with patch.object(coverage, 'promote', side_effect=ValueError('coverage unavailable')), \
             patch.object(coverage, 'scope') as scope, \
             patch('optimization.engine.top_three', return_value=[{'candidate': candidate}]):
            state = coverage.after_success(self.app, session['id'])
        scope.assert_not_called()
        self.assertEqual(state['status'], 'blocked')
        self.assertTrue(state['promotion_incomplete'])
        self.assertEqual(state['promotion'], transaction)
        self.assertEqual(state['workers'], original['workers'])
        # A caller's explicit resume may recover the saved transaction after repair.
        with patch('optimization.promotion.rebuild') as rebuild, \
             patch.object(coverage, 'scope', return_value={'workflow': 'verified', 'definitions': []}):
            coverage.finish_promotion(self.root, state)
        rebuild.assert_called_once_with(self.root)
        self.assertEqual(state['status'], 'pending')
        self.assertNotIn('promotion_incomplete', state)
        self.assertNotIn('scope_validation_error', state)


if __name__ == '__main__':
    unittest.main()
