"""Check the CDP smoke's diagnostics without a browser, socket or inference."""
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import Mock, patch

from tests.perchance_connection_browser_smoke import launch_with_stderr, report_browser_failure
from workbench import perchance_connection as connection


class ConnectionBrowserFixtureTests(unittest.TestCase):
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
