"""Check the CDP smoke's diagnostics without a browser, socket or inference."""
import errno
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import Mock, call, patch

from tests.perchance_connection_browser_smoke import launch_with_stderr, report_browser_failure, shutdown_fixture_browser, FixtureDirectory
from workbench import perchance_connection as connection


class ConnectionBrowserFixtureTests(unittest.TestCase):
    def test_graceful_browser_exit_precedes_disconnect_and_profile_cleanup(self):
        events = []
        backend, process = Mock(), Mock()
        backend.browser.new_browser_cdp_session.return_value.send.side_effect = lambda command: events.append(command)
        process.wait.side_effect = lambda **kwargs: events.append('browser exited')
        backend.close.side_effect = lambda: events.append('disconnect')
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / 'profile'
            profile.mkdir()
            shutdown_fixture_browser(backend, [process])
            self.assertTrue(profile.exists())
            self.assertEqual(events, ['Browser.close', 'browser exited', 'disconnect'])
        self.assertFalse(profile.exists())
        backend.browser.close.assert_not_called()
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    def test_stuck_owned_child_has_bounded_escalation_before_disconnect(self):
        backend, process = Mock(), Mock()
        events = Mock()
        events.attach_mock(process, 'process')
        events.attach_mock(backend.close, 'disconnect')
        process.wait.side_effect = [subprocess.TimeoutExpired('chromium', 10),
                                    subprocess.TimeoutExpired('chromium', 10), 0]
        shutdown_fixture_browser(backend, [process])
        self.assertEqual(events.mock_calls, [call.process.wait(timeout=10), call.process.terminate(),
                         call.process.wait(timeout=10), call.process.kill(),
                         call.process.wait(timeout=10), call.disconnect()])

    def test_shutdown_command_failure_waits_and_propagates(self):
        backend, process = Mock(), Mock()
        backend.browser.new_browser_cdp_session.return_value.send.side_effect = RuntimeError('CDP close failed')
        with self.assertRaisesRegex(RuntimeError, 'CDP close failed'):
            shutdown_fixture_browser(backend, [process])
        process.wait.assert_called_once_with(timeout=10)
        backend.close.assert_called_once_with()

    def test_unreaped_child_failure_is_not_suppressed(self):
        backend, process = Mock(), Mock()
        process.wait.side_effect = subprocess.TimeoutExpired('chromium', 10)
        with self.assertRaises(subprocess.TimeoutExpired):
            shutdown_fixture_browser(backend, [process])
        process.kill.assert_called_once_with()
        backend.close.assert_called_once_with()

    def test_profile_cleanup_retries_only_transient_errors(self):
        directory = object.__new__(FixtureDirectory)
        with patch.object(tempfile.TemporaryDirectory, 'cleanup',
                          side_effect=[OSError(errno.ENOTEMPTY, 'final profile write'), None]) as cleanup, \
             patch('tests.perchance_connection_browser_smoke.time.sleep') as sleep:
            directory.cleanup()
        self.assertEqual(cleanup.call_count, 2)
        sleep.assert_called_once_with(0.1)
        for error, attempts in ((OSError(errno.ENOTEMPTY, 'persistent writer'), 6),
                                (OSError(errno.EACCES, 'permissions'), 1)):
            with self.subTest(error=error), \
                 patch.object(tempfile.TemporaryDirectory, 'cleanup', side_effect=error) as cleanup, \
                 patch('tests.perchance_connection_browser_smoke.time.sleep'), \
                 self.assertRaises(OSError) as caught:
                directory.cleanup()
            self.assertIs(caught.exception, error)
            self.assertEqual(cleanup.call_count, attempts)

    def test_capture_keeps_production_launch_and_sandbox_arguments(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryFile() as stderr, \
             patch.object(connection.subprocess, 'Popen') as popen:
            process = launch_with_stderr(connection.launch, 'google-chrome',
                                        Path(tmp) / 'profile', 9223, 'http://127.0.0.1:8123/', stderr)
        self.assertIs(process, popen.return_value)
        popen.assert_called_once()
        args = popen.call_args.args[0]
        self.assertEqual(args[0], 'google-chrome')
        self.assertIn('--remote-debugging-address=127.0.0.1', args)
        self.assertIn('--remote-debugging-port=9223', args)
        self.assertIn('--headless=new', args)
        self.assertFalse(any('sandbox' in arg for arg in args))
        self.assertIs(popen.call_args.kwargs['stderr'], stderr)
        self.assertEqual(popen.call_args.kwargs['stdout'], connection.subprocess.DEVNULL)

    def test_failure_reports_stderr_and_actual_exit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'browser-stderr.log'
            path.write_bytes(b'Browser startup failed\n\xff')
            output = io.StringIO()
            with redirect_stderr(output):
                report_browser_failure('google-chrome', [Mock(poll=Mock(return_value=17))], path)
        text = output.getvalue()
        self.assertIn('Fixture browser executable: google-chrome', text)
        self.assertIn('exit status 17', text)
        self.assertIn('Browser startup failed', text)

    def test_failure_distinguishes_running_child_and_empty_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'browser-stderr.log'
            path.write_bytes(b'')
            output = io.StringIO()
            with redirect_stderr(output):
                report_browser_failure('google-chrome', [Mock(poll=Mock(return_value=None))], path)
        self.assertIn('still running', output.getvalue())
        self.assertIn('(empty)', output.getvalue())


if __name__ == '__main__':
    unittest.main()
