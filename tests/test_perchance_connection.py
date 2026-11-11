import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from contextlib import redirect_stderr

from workbench import perchance, perchance_connection as connection
from workbench.controller import Controller
from workbench.workflows import Cancelled


class ControlledConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'profile'
        self.profile.mkdir()
        self.backend = connection.ControlledBrowserBackend({'perchance_profile': str(self.profile)})
        self.child = MagicMock(pid=123)
        self.child.poll.return_value = None

    def test_launch_is_normal_visible_browser_and_loopback_cdp(self):
        with patch.object(connection.subprocess, 'Popen') as child:
            connection.launch('edge.exe', self.profile, 9223, perchance.DEFAULT_URL)
        args = child.call_args.args[0]
        self.assertIn('--remote-debugging-address=127.0.0.1', args)
        self.assertIn('--remote-debugging-port=9223', args)
        self.assertIn('--user-data-dir=' + str(self.profile.resolve()), args)
        self.assertFalse(any('enable-automation' in arg or 'headless' in arg for arg in args))

    def test_port_validation_rejects_remote_addresses_boolean_and_invalid_values(self):
        self.assertEqual(connection.endpoint(9223), 'http://127.0.0.1:9223')
        for value in ('http://host:9222', '9223', True, 0, 65536, None):
            with self.assertRaises(ValueError):connection.endpoint(value)

    def test_legacy_profile_is_redirected_without_altering_files(self):
        old = Path(self.temp.name) / 'perchance-profile'
        backend = connection.ControlledBrowserBackend({'perchance_profile': str(old)})
        self.assertEqual(Path(backend.settings['perchance_profile']), old.with_name('perchance-controlled-profile'))
        self.assertFalse(old.exists())

    def fake_playwright(self):
        client = MagicMock()
        browser = client.chromium.connect_over_cdp.return_value
        browser.contexts = [MagicMock()]
        browser.new_browser_cdp_session.return_value.send.return_value = {'processInfo': [{'type': 'browser', 'id': self.child.pid}]}
        module = SimpleNamespace(sync_playwright=lambda: SimpleNamespace(start=lambda: client))
        return client, browser, patch.dict(sys.modules, {'playwright.sync_api': module})

    def open_mock(self, browser, module, *, existing=False, reset_error=None, wait_error=None):
        if existing:
            (self.profile / 'rpg-cdp-owner.json').write_text(json.dumps({'port': 9223, 'profile': str(self.profile.resolve())}))
        with module, patch.object(connection, 'listening', return_value=existing), \
             patch.object(connection, 'launch', return_value=self.child) as launch, \
             patch.object(connection, 'wait_for_browser', side_effect=wait_error), \
             patch.object(perchance, 'browser_executable', return_value='edge.exe'), \
             patch.object(self.backend, 'reset', side_effect=reset_error) as reset:
            self.backend.open()
        return launch, reset

    def test_new_run_closes_verified_browser_before_disconnect_and_keeps_profile(self):
        client, browser, module = self.fake_playwright()
        launch, reset = self.open_mock(browser, module)
        marker = self.profile / 'rpg-cdp-owner.json'
        self.assertEqual(json.loads(marker.read_text())['pid'], self.child.pid)
        cookie = self.profile / 'Cookies'; cookie.write_text('saved authentication')
        events = []
        browser.new_browser_cdp_session.return_value.send.side_effect = lambda command: events.append(command)
        self.child.wait.side_effect = lambda **kwargs: events.append('exited')
        client.stop.side_effect = lambda: events.append('disconnected')
        self.backend.close(); self.backend.close()
        self.assertEqual(events, ['Browser.close', 'exited', 'disconnected'])
        launch.assert_called_once(); reset.assert_called_once()
        client.chromium.connect_over_cdp.assert_called_once_with('http://127.0.0.1:9223', timeout=10000)
        browser.close.assert_not_called(); browser.contexts[0].close.assert_not_called()
        self.assertFalse(marker.exists()); self.assertEqual(cookie.read_text(), 'saved authentication')

    def test_existing_browser_is_never_claimed_or_closed(self):
        client, browser, module = self.fake_playwright()
        launch, _ = self.open_mock(browser, module, existing=True)
        owned = MagicMock(); owned.is_closed.return_value = False
        old_page = MagicMock(); browser.contexts[0].pages = [old_page, owned]
        self.backend._owned_pages = [owned]
        self.backend.close(); self.backend.close()
        launch.assert_not_called(); browser.close.assert_not_called()
        browser.new_browser_cdp_session.assert_not_called()
        browser.contexts[0].close.assert_not_called(); old_page.close.assert_not_called()
        owned.close.assert_called_once(); self.child.wait.assert_not_called()
        self.assertTrue((self.profile / 'rpg-cdp-owner.json').exists())

    def test_foreign_listener_is_not_attached_or_closed(self):
        client, browser, module = self.fake_playwright()
        with module, patch.object(connection, 'listening', return_value=True), \
             patch.object(connection, 'launch') as launch:
            with self.assertRaisesRegex(RuntimeError, 'already in use by another browser'):
                self.backend.open()
        launch.assert_not_called(); client.chromium.connect_over_cdp.assert_not_called()
        browser.close.assert_not_called(); self.child.wait.assert_not_called()

    def test_stale_marker_or_process_handoff_cannot_authorize_browser_close(self):
        for exited, pid in ((None, 999), (0, 123)):
            with self.subTest(exited=exited, pid=pid):
                self.child.poll.return_value = exited
                client, browser, module = self.fake_playwright()
                browser.new_browser_cdp_session.return_value.send.return_value = {'processInfo': [{'type': 'browser', 'id': pid}]}
                with self.assertRaisesRegex(RuntimeError, 'Cannot verify ownership'):
                    self.open_mock(browser, module)
                commands = [call.args[0] for call in browser.new_browser_cdp_session.return_value.send.call_args_list]
                self.assertEqual(commands, ['SystemInfo.getProcessInfo'])
                client.stop.assert_called_once()
        self.assertFalse((self.profile / 'rpg-cdp-owner.json').exists())

    def test_cdp_shutdown_error_falls_back_only_to_captured_process(self):
        client, browser, module = self.fake_playwright(); self.open_mock(browser, module)
        browser.new_browser_cdp_session.return_value.send.side_effect = RuntimeError('CDP lost')
        self.child.wait.side_effect = [connection.subprocess.TimeoutExpired('browser', 5),
                                      connection.subprocess.TimeoutExpired('browser', 5), None]
        self.backend.close()
        self.child.terminate.assert_called_once(); self.child.kill.assert_called_once()
        client.stop.assert_called_once(); self.assertFalse((self.profile / 'rpg-cdp-owner.json').exists())

    def test_launch_timeout_or_cancel_reaps_child_before_cdp_exists(self):
        for error in (RuntimeError('startup failed'), Cancelled('cancelled startup')):
            with self.subTest(error=error):
                client, browser, module = self.fake_playwright()
                with self.assertRaises(type(error)) as caught:
                    self.open_mock(browser, module, wait_error=error)
                self.assertIs(caught.exception, error)
                client.chromium.connect_over_cdp.assert_not_called(); browser.close.assert_not_called()
        self.assertEqual(self.child.wait.call_count, 2)

    def test_plugin_failure_or_cancel_closes_owned_browser(self):
        for error in (RuntimeError('plugin missing'), Cancelled('cancelled startup')):
            with self.subTest(error=error):
                client, browser, module = self.fake_playwright()
                with self.assertRaises(type(error)) as caught:
                    self.open_mock(browser, module, reset_error=error)
                self.assertIs(caught.exception, error)
                browser.new_browser_cdp_session.return_value.send.assert_any_call('Browser.close')
                client.stop.assert_called_once()
        self.assertEqual(self.child.wait.call_count, 2)

    def test_cleanup_failure_is_visible_and_does_not_mask_startup_error(self):
        client, browser, module = self.fake_playwright(); self.open_mock(browser, module)
        self.child.wait.side_effect = OSError('access denied')
        with self.assertRaisesRegex(RuntimeError, 'browser cleanup failed'):
            self.backend.close()
        client.stop.assert_called_once()
        client, browser, module = self.fake_playwright()
        error = RuntimeError('original failure')
        with redirect_stderr(io.StringIO()) as stderr, self.assertRaises(RuntimeError) as caught:
            self.open_mock(browser, module, reset_error=error)
        self.assertIs(caught.exception, error)
        self.assertIn('browser cleanup failed', stderr.getvalue())
        client.stop.assert_called_once()

    def test_cleanup_does_not_remove_another_sessions_marker(self):
        client, browser, module = self.fake_playwright(); self.open_mock(browser, module)
        marker = self.profile / 'rpg-cdp-owner.json'
        replacement = {'port': 9223, 'profile': str(self.profile), 'session': 'another owner'}
        marker.write_text(json.dumps(replacement))
        self.backend.close()
        self.assertEqual(json.loads(marker.read_text()), replacement)

    def test_tab_close_failure_still_disconnects_without_closing_existing_browser(self):
        client, browser, module = self.fake_playwright(); self.open_mock(browser, module, existing=True)
        bad, good = MagicMock(), MagicMock()
        bad.is_closed.return_value = good.is_closed.return_value = False
        bad.close.side_effect = RuntimeError('target failed')
        self.backend._owned_pages = [bad, good]
        with self.assertRaisesRegex(RuntimeError, 'run-owned tab'):
            self.backend.close()
        good.close.assert_called_once(); client.stop.assert_called_once()
        browser.new_browser_cdp_session.assert_not_called()

    def mock_page(self):
        frame = MagicMock(); frame.evaluate.side_effect = [True, None, {'ready': True}]
        page = MagicMock(); page.url = perchance.DEFAULT_URL; page.is_closed.return_value = False; page.frames = [frame]
        self.backend.context = MagicMock(); self.backend.context.pages = [page]
        return page, frame

    def test_reset_reuses_owned_launch_page_and_injects_exact_worker(self):
        page, frame = self.mock_page(); self.backend._owns_browser = True
        self.backend.reset()
        page.goto.assert_not_called(); page.close.assert_not_called()
        self.backend.context.new_page.assert_not_called()
        self.assertEqual(frame.evaluate.call_args_list[1].args[0], perchance.WORKER.read_text(encoding='utf-8'))
        self.assertEqual(self.backend.environment['browser_connection'], 'normal-browser-cdp-v1')
        self.assertEqual(self.backend.environment['readiness_scope'], 'plugin_availability_only')

    def test_reset_never_uses_existing_browser_pages(self):
        page, frame = self.mock_page()
        other = MagicMock(); self.backend.context.pages = [other]
        self.backend.context.new_page.return_value = page
        self.backend.reset()
        page.goto.assert_called_once_with(perchance.DEFAULT_URL, wait_until='domcontentloaded', timeout=60000)
        other.close.assert_not_called(); other.goto.assert_not_called()
        self.assertEqual(self.backend._owned_pages, [page])
        self.assertFalse(any('Start(' in str(call) for call in frame.evaluate.call_args_list))
        frame.evaluate.side_effect = [True, None, {'ready': True}]
        self.backend.reset()
        self.backend.context.new_page.assert_called_once()

    def test_challenge_startup_failure_does_not_touch_preexisting_page(self):
        page, _ = self.mock_page()
        self.backend.context.new_page.return_value = page
        page.title.return_value = 'Just a moment...'; page.frames = []
        self.backend.settings['perchance_ready_seconds'] = 0
        with self.assertRaisesRegex(RuntimeError, 'security verification blocked startup'):
            self.backend.reset()
        self.backend.close()
        page.close.assert_called_once()

    def test_cancellation_stops_startup_without_generating(self):
        page, frame = self.mock_page()
        self.backend.context.new_page.return_value = page
        self.backend.cancel()
        with self.assertRaises(Cancelled):self.backend.reset()
        self.backend.close(); page.close.assert_called_once(); frame.evaluate.assert_not_called()

    def test_request_serializer_deadline_and_raw_partials_are_inherited(self):
        self.assertIs(connection.ControlledBrowserBackend.generate, perchance.BrowserBackend.generate)
        snapshot = {'state': 'running', 'text': ' RAW\n', 'chunks': [{'text': ' RAW\n'}], 'firstVisibleMs': 5}
        self.backend.frame = MagicMock(); self.backend.frame.evaluate.return_value = snapshot
        page = MagicMock(); self.backend.page = page; self.backend.deadline = 0
        with self.assertRaises(perchance.PerchanceTimeout) as failure:
            self.backend.generate([{'role': 'user', 'content': 'Original prompt'}], {}, None, threading.Event())
        self.assertEqual(failure.exception.partial_response['text'], ' RAW\n')
        self.assertEqual(failure.exception.partial_response['effective_instruction'], 'USER:\nOriginal prompt')
        page.close.assert_called_once()

    def test_production_wrapper_uses_controlled_factory_without_new_generation(self):
        app = SimpleNamespace(backend='current')
        with patch.object(perchance, 'run', return_value='sentinel') as run:
            self.assertEqual(connection.run(app, 'report', 'pending', append=True), 'sentinel')
        run.assert_called_once_with(app, 'report', 'pending', backend_factory=connection.ControlledBrowserBackend, append=True)
        self.assertIsNone(app.backend)

    def test_production_wrapper_clears_backend_if_cleanup_fails(self):
        app = SimpleNamespace(backend='current')
        with patch.object(perchance, 'run', side_effect=RuntimeError('cleanup failed')):
            with self.assertRaises(RuntimeError):connection.run(app, 'report', 'pending')
        self.assertIsNone(app.backend)

    def test_verification_does_not_claim_generation_and_always_cleans_up(self):
        app = Controller(Path(self.temp.name))
        with patch.object(connection, 'ControlledBrowserBackend') as factory:
            backend = factory.return_value; backend.environment = {'ready': True}
            connection.verify_connection(app)
        backend.open.assert_called_once(); backend.close.assert_called_once(); backend.generate.assert_not_called()
        self.assertIsNone(app.backend)
        self.assertIn('generation has not been verified', app.message)

    def test_configured_port_is_validated_and_provider_identity_is_unchanged(self):
        app = Controller(Path(self.temp.name)); before = perchance.identity(app.settings)
        app.configure({'perchance_cdp_port': 9234})
        self.assertEqual(perchance.identity(app.settings), before)
        self.assertEqual(app.settings['perchance_cdp_port'], 9234)
        for value in (True, '9223', 65536):
            with self.assertRaises(ValueError):app.configure({'perchance_cdp_port': value})


class ProbeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.profile = Path(tempfile.gettempdir()).resolve() / 'rpg-cdp-probe-fixture'
        self.client = MagicMock()
        self.child = MagicMock()
        self.browser = self.client.chromium.connect_over_cdp.return_value
        context = MagicMock(); context.__enter__.return_value = self.client
        self.module = patch.dict(sys.modules, {'playwright.sync_api': SimpleNamespace(sync_playwright=lambda: context)})

    def run_probe(self, wait_error=None, cleanup_errors=None, launch_error=None):
        stderr = io.StringIO()
        with self.module, patch.object(connection.tempfile, 'mkdtemp', return_value=str(self.profile)), \
             patch.object(connection, 'launch', return_value=self.child, side_effect=launch_error), \
             patch.object(connection, 'wait_for_browser', return_value='http://127.0.0.1:9223', side_effect=wait_error), \
             patch.object(connection.shutil, 'rmtree', side_effect=cleanup_errors) as cleanup, \
             patch.object(connection.time, 'sleep'), redirect_stderr(stderr):
            connection.probe('edge.exe')
        return cleanup, stderr.getvalue()

    def test_success_closes_only_owned_probe_browser_before_profile_cleanup(self):
        cleanup, warning = self.run_probe()
        self.browser.new_browser_cdp_session.return_value.send.assert_called_once_with('Browser.close')
        self.browser.close.assert_not_called()
        self.child.wait.assert_called_once_with(timeout=5)
        self.child.terminate.assert_not_called()
        cleanup.assert_called_once_with(self.profile)
        self.assertEqual(warning, '')

    def test_transient_windows_profile_lock_is_retried_without_failing_probe(self):
        cleanup, warning = self.run_probe(cleanup_errors=[NotADirectoryError(267, 'Account Web Data'), None])
        self.assertEqual(cleanup.call_count, 2)
        self.assertEqual(warning, '')

    def test_persistent_windows_cleanup_error_is_warning_not_failed_readiness(self):
        cleanup, warning = self.run_probe(cleanup_errors=NotADirectoryError(267, 'Account Web Data'))
        self.assertEqual(cleanup.call_count, 6)
        self.assertIn('cleanup warning', warning)
        self.assertIn(str(self.profile), warning)

    def test_real_connection_error_survives_profile_cleanup_error(self):
        with self.assertRaisesRegex(RuntimeError, 'CDP unavailable'):
            self.run_probe(wait_error=RuntimeError('CDP unavailable'),
                           cleanup_errors=NotADirectoryError(267, 'Account Web Data'))
        self.client.chromium.connect_over_cdp.assert_not_called()
        self.child.wait.assert_called_once_with(timeout=5)

    def test_launch_failure_still_cleans_profile_and_preserves_failure(self):
        with self.assertRaisesRegex(OSError, 'browser missing'):
            self.run_probe(launch_error=OSError('browser missing'))
        self.child.wait.assert_not_called()

    def test_stubborn_probe_child_is_terminated_then_killed(self):
        self.child.wait.side_effect = [connection.subprocess.TimeoutExpired('probe', 5),
                                       connection.subprocess.TimeoutExpired('probe', 5), None]
        self.run_probe()
        self.child.terminate.assert_called_once()
        self.child.kill.assert_called_once()
        self.assertEqual(self.child.wait.call_count, 3)

    def test_shutdown_error_does_not_mask_real_connection_failure(self):
        self.child.wait.side_effect = OSError('shutdown failed')
        with self.assertRaisesRegex(RuntimeError, 'CDP unavailable'):
            self.run_probe(wait_error=RuntimeError('CDP unavailable'))

    def test_cdp_shutdown_error_falls_back_to_owned_child_cleanup(self):
        self.browser.new_browser_cdp_session.return_value.send.side_effect = RuntimeError('connection closed')
        cleanup, warning = self.run_probe()
        self.assertIn('shutdown warning', warning)
        self.child.wait.assert_called_once_with(timeout=5)
        cleanup.assert_called_once_with(self.profile)

    def test_cleanup_refuses_persistent_profile(self):
        with patch.object(connection.shutil, 'rmtree') as cleanup, redirect_stderr(io.StringIO()) as stderr:
            connection._cleanup_probe_profile(Path(tempfile.gettempdir()) / 'perchance-controlled-profile')
        cleanup.assert_not_called()
        self.assertIn('refusing unexpected profile', stderr.getvalue())


if __name__ == '__main__':unittest.main()
