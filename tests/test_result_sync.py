"""Deterministic local bare-remote tests. No network or model inference."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from workbench.controller import Controller
from workbench.domain import ResultStore, read_json, write_json
from workbench.result_sync import ResultSync, RecordingStore, git, sync_run, GIT_TIMEOUT
from workbench.workflows import Cancelled


class ResultSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.remote = self.base / 'remote.git'
        self.root = self.base / 'desktop'
        subprocess.run(['git', 'init', '--bare', str(self.remote)], check=True, capture_output=True)
        subprocess.run(['git', 'clone', str(self.remote), str(self.root)], check=True, capture_output=True)
        git(self.root, 'checkout', '-b', 'main')
        git(self.root, 'config', 'user.name', 'Test')
        git(self.root, 'config', 'user.email', 'test@example.invalid')
        git(self.root, 'config', 'core.autocrlf', 'false')
        (self.root / '.gitignore').write_text('.local/\n')
        (self.root / '.gitattributes').write_text('*.json text eol=lf\n')
        (self.root / 'source.py').write_text('original\n')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-m', 'initial')
        git(self.root, 'push', '-u', 'origin', 'main')
        self.sync = ResultSync(self.root)
        self.store = ResultStore(self.root / 'results')

    def record(self, digit='a', status='completed', **kwargs):
        return dict(model_id='model', case_id=digit * 64, status=status, simulated=False, **kwargs)

    def enroll(self, digit='a', status='completed'):
        batch = self.sync.begin()
        RecordingStore(self.store, self.sync, batch).save(self.record(digit, status))
        return batch

    def receipt(self, batch):
        return read_json(self.sync.directory / (batch['id'] + '.json'))

    def test_default_existing_saved_false_and_demo_exclusion(self):
        settings = self.root / '.local/workbench/settings.json'
        write_json(settings, {'models_folder_version': 1, 'publish_results': False})
        app = Controller(self.root)
        self.assertTrue(app.settings['publish_results'])
        self.assertEqual(app.result_sync_status['status'], 'idle')
        with patch('workbench.gitops.Publisher') as old:
            app.publish(force=True)
            old.assert_not_called()
        demo = Controller(self.root, demo=True)
        self.assertFalse(demo.settings['publish_results'])
        self.assertEqual(demo.retry_result_sync()['status'], 'disabled')

    def test_exact_run_paths_preserve_unrelated_staged_dirty_deleted_and_untracked(self):
        # Historic deletion and an untracked result are not from this run.
        old = self.store.save(self.record('c'))
        git(self.root, 'add', '--', str(old))
        git(self.root, 'commit', '-m', 'historic')
        git(self.root, 'push', 'origin', 'main')
        old.unlink()
        self.store.save(self.record('d'))
        (self.root / 'source.py').write_text('staged\n')
        git(self.root, 'add', 'source.py')
        (self.root / 'source.py').write_text('staged plus unstaged\n')
        (self.root / 'private.env').write_text('do not publish\n')
        before_index = git(self.root, 'diff', '--cached', binary=True)
        batch = self.enroll()
        result = self.sync.retry()
        self.assertEqual(result['status'], 'synced', result)
        self.assertEqual(git(self.root, 'diff', '--cached', binary=True), before_index)
        self.assertEqual((self.root / 'source.py').read_text(), 'staged plus unstaged\n')
        self.assertFalse(old.exists())
        self.assertTrue((self.root / 'private.env').exists())
        self.assertEqual(git(self.root, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'),
                         'results/model/' + 'a' * 64 + '.json')
        self.assertEqual(git(self.root, 'ls-remote', 'origin', 'refs/heads/main').split()[0],
                         git(self.root, 'rev-parse', 'HEAD'))
        self.assertEqual(self.receipt(batch)['status'], 'synced')

    def test_no_results_noop_and_repeated_retry_make_no_git_changes(self):
        head = git(self.root, 'rev-parse', 'HEAD')
        with patch('workbench.result_sync.git') as transport:
            self.assertEqual(self.sync.retry()['status'], 'idle')
            transport.assert_not_called()
        batch = self.enroll()
        self.assertEqual(self.sync.retry()['status'], 'synced')
        commit = git(self.root, 'rev-parse', 'HEAD')
        self.assertNotEqual(head, commit)
        with patch('workbench.result_sync.git') as transport:
            self.assertEqual(self.sync.retry()['status'], 'idle')
            transport.assert_not_called()
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), commit)

    def test_preexisting_same_path_edits_and_later_staging_block(self):
        self.store.save(self.record(status='error'))
        batch = self.enroll(status='completed')
        self.assertEqual(self.sync.retry()['status'], 'pending')
        self.assertIn('before this run', self.receipt(batch)['error'])

    def test_path_staged_after_recording_blocks_without_touching_index(self):
        batch = self.enroll()
        path = self.store.path('model', 'a' * 64)
        git(self.root, 'add', '--', str(path))
        staged = git(self.root, 'diff', '--cached', binary=True)
        self.assertEqual(self.sync.retry()['status'], 'pending')
        self.assertEqual(git(self.root, 'diff', '--cached', binary=True), staged)
        self.assertIn('other staged', self.receipt(batch)['error'])

    def test_changed_and_deleted_saved_files_block(self):
        batch = self.enroll()
        path = self.store.path('model', 'a' * 64)
        saved = path.read_bytes()
        path.write_bytes(saved + b' ')
        self.assertEqual(self.sync.retry()['status'], 'pending')
        self.assertIn('changed after', self.receipt(batch)['error'])
        path.unlink()
        self.assertEqual(self.sync.retry()['status'], 'pending')

    def test_push_failure_durable_retry_survives_restart_without_duplicate_commit(self):
        batch = self.enroll()
        actual = git
        def fail_push(root, *args, **kwargs):
            if args[0] == 'push':raise RuntimeError('offline')
            return actual(root, *args, **kwargs)
        with patch('workbench.result_sync.git', side_effect=fail_push):
            result = self.sync.retry()
        self.assertEqual(result['status'], 'pending')
        commit = git(self.root, 'rev-parse', 'HEAD')
        self.assertEqual(self.receipt(batch)['commit'], commit)
        restarted = ResultSync(self.root)
        self.assertEqual(restarted.status()['status'], 'pending')
        self.assertEqual(restarted.retry()['status'], 'synced')
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), commit)
        self.assertEqual(self.receipt(batch)['status'], 'synced')

    def test_commit_failure_preserves_unrelated_index_and_retries_owned_staging(self):
        (self.root / 'source.py').write_text('unrelated staged\n')
        git(self.root, 'add', 'source.py')
        staged = git(self.root, 'show', ':source.py')
        batch = self.enroll()
        actual = git
        def fail_commit(root, *args, **kwargs):
            if 'commit' in args:raise RuntimeError('commit hook failed')
            return actual(root, *args, **kwargs)
        with patch('workbench.result_sync.git', side_effect=fail_commit):
            self.assertEqual(self.sync.retry()['status'], 'pending')
        self.assertEqual(git(self.root, 'show', ':source.py'), staged)
        self.assertEqual(ResultSync(self.root).retry()['status'], 'synced')
        self.assertEqual(git(self.root, 'show', ':source.py'), staged)

    def test_uncertain_successful_commit_is_reconciled_before_retry(self):
        batch = self.enroll()
        actual = git
        def uncertain_commit(root, *args, **kwargs):
            result = actual(root, *args, **kwargs)
            if 'commit' in args:raise subprocess.TimeoutExpired('git commit', GIT_TIMEOUT)
            return result
        with patch('workbench.result_sync.git', side_effect=uncertain_commit):
            self.assertEqual(self.sync.retry()['status'], 'pending')
        commit = git(self.root, 'rev-parse', 'HEAD')
        self.assertEqual(ResultSync(self.root).retry()['status'], 'synced')
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), commit)

    def test_remote_divergence_does_not_merge_force_push_or_commit(self):
        batch = self.enroll()
        head = git(self.root, 'rev-parse', 'HEAD')
        other = self.base / 'other'
        subprocess.run(['git', 'clone', '-b', 'main', str(self.remote), str(other)], check=True, capture_output=True)
        git(other, 'config', 'user.name', 'Other')
        git(other, 'config', 'user.email', 'other@example.invalid')
        (other / 'other.txt').write_text('new remote work')
        git(other, 'add', 'other.txt');git(other, 'commit', '-m', 'remote work');git(other, 'push')
        self.assertEqual(self.sync.retry()['status'], 'pending')
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), head)
        self.assertIn('Reconcile', self.receipt(batch)['error'])

    def test_branch_switch_blocks_and_restoring_branch_allows_retry(self):
        batch = self.enroll()
        git(self.root, 'checkout', '-b', 'other')
        self.assertEqual(self.sync.retry()['status'], 'pending')
        self.assertIn('branch changed', self.receipt(batch)['error'])
        git(self.root, 'checkout', 'main')
        self.assertEqual(self.sync.retry()['status'], 'synced')

    def test_crlf_normalization_matches_commit_while_working_hash_stays_exact(self):
        batch = self.enroll()
        path = self.store.path('model', 'a' * 64)
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.sync.after_save(batch, path.relative_to(self.root).as_posix())
        self.assertEqual(self.sync.retry()['status'], 'synced')

    def test_secret_and_simulated_results_block_without_publishing(self):
        self.sync.secrets = ('private-value',)
        batch = self.sync.begin()
        path = RecordingStore(self.store, self.sync, batch).save(self.record(response='private-value'))
        self.assertTrue(path.exists())
        self.assertIn('credential', batch['recording_error'])
        self.assertEqual(self.sync.retry()['status'], 'pending')
        self.assertNotIn('private-value', json.dumps(self.receipt(batch)))
        with self.assertRaisesRegex(RuntimeError, 'Simulated'):
            self.sync.after_save(batch, self.store.save(dict(self.record('b'), simulated=True)).relative_to(self.root).as_posix())

    def test_large_batch_uses_pathspec_file_and_no_command_line_overflow(self):
        batch = self.sync.begin()
        store = RecordingStore(self.store, self.sync, batch)
        for i in range(160):
            store.save(dict(self.record(), case_id=format(i, '064x')))
        self.assertEqual(self.sync.retry()['status'], 'synced')
        self.assertEqual(len(git(self.root, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').splitlines()), 160)

    def test_interrupted_inference_flushes_only_saved_evidence_and_rethrows(self):
        app = Controller(self.root)
        @sync_run
        def run(app):
            app.store.save(self.record(status='aborted'))
            raise Cancelled('user stopped')
        with self.assertRaises(Cancelled):run(app)
        self.assertEqual(app.result_sync_status['status'], 'synced')
        self.assertFalse(app.result_sync_active)
        self.assertIsInstance(app.store, ResultStore)
        self.assertEqual(self.store.read(self.store.path('model', 'a' * 64))['status'], 'aborted')

    def test_inference_error_and_noop_completion_always_finalize(self):
        app = Controller(self.root)
        @sync_run
        def broken(app):
            app.store.save(self.record(status='error'))
            raise ValueError('inference failed')
        with self.assertRaisesRegex(ValueError, 'inference failed'):broken(app)
        self.assertEqual(app.result_sync_status['status'], 'synced')
        @sync_run
        def no_work(app):return 'finished'
        head = git(self.root, 'rev-parse', 'HEAD')
        self.assertEqual(no_work(app), 'finished')
        self.assertEqual(git(self.root, 'rev-parse', 'HEAD'), head)

    def test_actual_controller_run_enrolls_native_session_and_flushes(self):
        app = Controller(self.root)
        app.settings['sync_source'] = False
        app.plan = {'pending': 1, 'complete': 0, 'groups': []}
        report = {'ready': True, 'issues': []}
        with patch('workbench.perchance_setup.prepare'), \
             patch.object(app, 'check', return_value=report), \
             patch.object(app, 'backend_version', return_value='test-only'), \
             patch.object(app, 'workflow_code', return_value='test-only'), \
             patch.object(app, 'build_preflight', return_value=(report, app.plan)), \
             patch('workbench.scheduler.Session') as session:
            session.return_value.run.side_effect = lambda: app.store.save(self.record())
            app.run()
        self.assertEqual(app.state, 'finished')
        self.assertEqual(app.result_sync_status['status'], 'synced')
        self.assertEqual(git(self.root, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'),
                         'results/model/' + 'a' * 64 + '.json')

    def test_cli_loads_configured_credentials_for_pending_transport(self):
        from workbench.result_sync import main
        write_json(self.root / '.local/workbench/settings.json', {'hf_token': 'private-value'})
        with patch('workbench.result_sync.ResultSync') as sync:
            sync.return_value.retry.return_value = {'status': 'idle'}
            self.assertEqual(main(['--root', str(self.root)]), 0)
        self.assertEqual(sync.call_args.args[1], ('private-value', None))

    def test_pending_batches_keep_creation_order_after_failed_retries(self):
        first = self.enroll('a')
        second = self.enroll('b')
        actual = git
        def fail_push(root, *args, **kwargs):
            if args[0] == 'push':raise RuntimeError('offline')
            return actual(root, *args, **kwargs)
        with patch('workbench.result_sync.git', side_effect=fail_push):
            self.assertEqual(self.sync.retry()['status'], 'pending')
            self.assertEqual(self.sync.retry()['status'], 'pending')
        self.assertEqual(ResultSync(self.root).retry()['status'], 'synced')
        self.assertEqual(self.receipt(first)['status'], 'synced')
        self.assertEqual(self.receipt(second)['status'], 'synced')

    def test_changed_origin_destination_never_receives_recorded_results(self):
        batch = self.enroll()
        other = self.base / 'other.git'
        subprocess.run(['git', 'init', '--bare', str(other)], check=True, capture_output=True)
        git(self.root, 'remote', 'set-url', 'origin', str(other))
        self.assertEqual(self.sync.retry()['status'], 'pending')
        self.assertIn('destination changed', self.receipt(batch)['error'])
        self.assertNotIn(str(self.remote), json.dumps(self.receipt(batch)))

    def test_journal_write_failure_keeps_model_response_and_visible_status(self):
        app = Controller(self.root)
        @sync_run
        def run(app):
            return app.store.save(self.record())
        with patch.object(app.result_sync, 'save_receipt', side_effect=OSError('disk full')):
            path = run(app)
        self.assertEqual(self.store.read(path)['status'], 'completed')
        self.assertEqual(app.result_sync_status['status'], 'pending')
        self.assertIn('receipt', app.result_sync_status['message'])

    def test_empty_interrupted_receipt_is_not_pending_forever(self):
        batch = self.sync.begin()
        self.sync.save_receipt(batch)
        self.assertEqual(self.sync.status()['pending'], 0)
        self.assertEqual(self.sync.retry()['status'], 'idle')

    def test_interrupted_result_write_is_visible_and_not_blindly_committed(self):
        batch = self.sync.begin()
        self.sync.before_save(batch, self.store.path('model', 'a' * 64))
        self.assertEqual(self.sync.retry()['status'], 'pending')
        self.assertIn('Interrupted result save', self.receipt(batch)['error'])

    def test_git_timeout_no_prompts_and_redacted_transport_errors(self):
        with patch('workbench.result_sync.subprocess.run') as run:
            run.return_value = SimpleNamespace(returncode=1, stdout=b'', stderr=b'https://token-secret@remote/')
            with self.assertRaises(RuntimeError) as error:git(self.root, 'push', 'origin', 'main')
        self.assertNotIn('token-secret', str(error.exception))
        self.assertEqual(run.call_args.kwargs['timeout'], 45)
        self.assertEqual(run.call_args.kwargs['env']['GIT_TERMINAL_PROMPT'], '0')
        self.assertEqual(run.call_args.kwargs['env']['GCM_INTERACTIVE'], 'never')


if __name__ == '__main__':unittest.main()
