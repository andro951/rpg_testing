import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from workbench import perchance, perchance_connection as connection
from workbench.controller import Controller
from workbench.workflows import Cancelled


class ControlledConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / 'profile'
        self.profile.mkdir()
        self.backend = connection.ControlledBrowserBackend({'perchance_profile': str(self.profile)})

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
        module = SimpleNamespace(sync_playwright=lambda: SimpleNamespace(start=lambda: client))
        return client, browser, patch.dict(sys.modules, {'playwright.sync_api': module})

    def test_new_launch_attach_and_disconnect_leave_normal_browser_open(self):
        client, browser, module = self.fake_playwright()
        with module, patch.object(connection, 'listening', return_value=False), \
             patch.object(connection, 'launch') as launch, \
             patch.object(connection, 'wait_for_browser'), \
             patch.object(perchance, 'browser_executable', return_value='edge.exe'), \
             patch.object(self.backend, 'reset') as reset:
            self.backend.open(); self.backend.close()
        launch.assert_called_once()
        client.chromium.connect_over_cdp.assert_called_once_with('http://127.0.0.1:9223', timeout=10000)
        reset.assert_called_once(); client.stop.assert_called_once()
        browser.close.assert_not_called(); browser.contexts[0].close.assert_not_called()
        self.assertTrue((self.profile / 'rpg-cdp-owner.json').exists())

    def test_owned_existing_browser_reused_without_another_launch(self):
        (self.profile / 'rpg-cdp-owner.json').write_text(json.dumps({'port': 9223, 'profile': str(self.profile.resolve())}))
        client, browser, module = self.fake_playwright()
        with module, patch.object(connection, 'listening', return_value=True), \
             patch.object(connection, 'launch') as launch, patch.object(connection, 'wait_for_browser'), \
             patch.object(self.backend, 'reset'):
            self.backend.open(); self.backend.close()
        launch.assert_not_called(); browser.close.assert_not_called()

    def test_foreign_listener_is_not_attached_or_closed(self):
        client, browser, module = self.fake_playwright()
        with module, patch.object(connection, 'listening', return_value=True), \
             patch.object(connection, 'launch') as launch:
            with self.assertRaisesRegex(RuntimeError, 'already in use by another browser'):
                self.backend.open()
        launch.assert_not_called(); client.chromium.connect_over_cdp.assert_not_called()
        browser.close.assert_not_called()

    def test_reset_reuses_hosted_page_and_injects_exact_worker(self):
        frame = MagicMock()
        frame.evaluate.side_effect = [True, None, {'ready': True}]
        page = MagicMock(); page.url = perchance.DEFAULT_URL; page.is_closed.return_value = False; page.frames = [frame]
        self.backend.context = MagicMock(); self.backend.context.pages = [page]
        self.backend.reset()
        page.goto.assert_not_called(); page.close.assert_not_called()
        self.backend.context.new_page.assert_not_called()
        self.assertEqual(frame.evaluate.call_args_list[1].args[0], perchance.WORKER.read_text(encoding='utf-8'))
        self.assertEqual(self.backend.environment['browser_connection'], 'normal-browser-cdp-v1')
        self.assertEqual(self.backend.environment['readiness_scope'], 'plugin_availability_only')

    def test_reset_creates_missing_page_but_never_generates(self):
        frame = MagicMock(); frame.evaluate.side_effect = [True, None, {'ready': True}]
        page = MagicMock(); page.frames = [frame]
        self.backend.context = MagicMock(); self.backend.context.pages = []
        self.backend.context.new_page.return_value = page
        self.backend.reset()
        page.goto.assert_called_once_with(perchance.DEFAULT_URL, wait_until='domcontentloaded', timeout=60000)
        self.assertFalse(any('Start(' in str(call) for call in frame.evaluate.call_args_list))

    def test_challenge_startup_failure_keeps_host_page_open(self):
        page = MagicMock(); page.url = perchance.DEFAULT_URL; page.is_closed.return_value = False
        page.title.return_value = 'Just a moment...'; page.frames = []
        self.backend.context = MagicMock(); self.backend.context.pages = [page]
        self.backend.settings['perchance_ready_seconds'] = 0
        with self.assertRaisesRegex(RuntimeError, 'security verification blocked startup'):
            self.backend.reset()
        page.close.assert_not_called()

    def test_cancellation_stops_startup_without_generating(self):
        page = MagicMock(); page.url = perchance.DEFAULT_URL; page.is_closed.return_value = False
        self.backend.context = MagicMock(); self.backend.context.pages = [page]
        self.backend.cancel()
        with self.assertRaises(Cancelled):self.backend.reset()
        page.close.assert_not_called()

    def test_request_serializer_deadline_and_raw_partials_are_inherited(self):
        self.assertIs(connection.ControlledBrowserBackend.generate, perchance.BrowserBackend.generate)
        snapshot = {'state': 'running', 'text': ' RAW\n', 'chunks': [{'text': ' RAW\n'}], 'firstVisibleMs': 5}
        self.backend.frame = MagicMock(); self.backend.frame.evaluate.return_value = snapshot
        page = MagicMock(); self.backend.page = page; self.backend.deadline = 0
        with self.assertRaises(perchance.PerchanceTimeout) as failure:
            self.backend.generate([{'role': 'user', 'content': 'Original prompt'}], {}, None, threading.Event())
        partial = failure.exception.partial_response
        self.assertEqual(partial['text'], ' RAW\n')
        self.assertEqual(partial['effective_instruction'], 'USER:\nOriginal prompt')
        page.close.assert_called_once()

    def test_production_wrapper_uses_controlled_factory_without_new_generation(self):
        with patch.object(perchance, 'run', return_value='sentinel') as run:
            self.assertEqual(connection.run('app', 'report', 'pending', append=True), 'sentinel')
        run.assert_called_once_with('app', 'report', 'pending', backend_factory=connection.ControlledBrowserBackend, append=True)

    def test_verification_does_not_claim_generation_or_close_normal_browser(self):
        app = Controller(Path(self.temp.name))
        with patch.object(connection, 'ControlledBrowserBackend') as factory:
            backend = factory.return_value; backend.environment = {'ready': True}
            connection.verify_connection(app)
        backend.open.assert_called_once(); backend.close.assert_called_once(); backend.generate.assert_not_called()
        self.assertIn('generation has not been verified', app.message)

    def test_configured_port_is_validated_and_provider_identity_is_unchanged(self):
        app = Controller(Path(self.temp.name)); before = perchance.identity(app.settings)
        app.configure({'perchance_cdp_port': 9234})
        self.assertEqual(perchance.identity(app.settings), before)
        self.assertEqual(app.settings['perchance_cdp_port'], 9234)
        for value in (True, '9223', 65536):
            with self.assertRaises(ValueError):app.configure({'perchance_cdp_port': value})


if __name__ == '__main__':unittest.main()
