import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workbench.controller import Controller
from workbench import perchance_setup as setup
from workbench.workflows import Cancelled


class BrowserSetupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.app = Controller(Path(temp.name))

    def test_missing_package_or_browser_and_failed_launch(self):
        with patch.object(setup.importlib.util, 'find_spec', return_value=None), patch.object(setup, 'process') as process:
            self.assertFalse(setup.health(self.app)['ready']); process.assert_not_called()
        with patch.object(setup.importlib.util, 'find_spec', return_value=object()), \
             patch.object(setup.perchance, 'browser_executable', return_value=None):
            self.assertFalse(setup.health(self.app)['ready'])
        with patch.object(setup.importlib.util, 'find_spec', return_value=object()), \
             patch.object(setup.perchance, 'browser_executable', return_value='fixture.exe'), \
             patch.object(setup, 'process', return_value=(1, '', 'broken driver')) as process:
            self.assertEqual(setup.health(self.app), {'ready': False, 'reason': 'broken driver'})
            self.assertIn('perchance_connection import probe', process.call_args.args[1][2])
        with patch.object(setup.importlib.util, 'find_spec', return_value=object()), \
             patch.object(setup.perchance, 'browser_executable', return_value='fixture.exe'), \
             patch.object(setup, 'process', side_effect=RuntimeError('launch timed out')):
            self.assertFalse(setup.health(self.app)['ready'])

    def test_install_uses_worker_python_and_keeps_working_existing_browser(self):
        with patch.object(setup, 'process', return_value=(0, 'installed', '')) as process, \
             patch.object(setup, 'health', return_value={'ready': True, 'reason': ''}):
            self.assertTrue(setup.install(self.app)['ready'])
            args = process.call_args.args[1]
            self.assertEqual(args[:4], [setup.sys.executable, '-m', 'pip', 'install'])
            self.assertIn(str(self.app.root / 'requirements-perchance.txt'), args)
            process.assert_called_once()
            self.assertEqual(self.app.settings['perchance_browser'], '')

    def test_installs_managed_browser_if_existing_browser_unusable_and_rechecks(self):
        with patch.object(setup, 'process', side_effect=[(0, '', ''), (0, '', ''), (0, 'managed.exe\n', '')]) as process, \
             patch.object(setup, 'health', side_effect=[{'ready': False, 'reason': 'no browser'}, {'ready': True, 'reason': ''}]) as health:
            self.assertTrue(setup.install(self.app)['ready'])
            self.assertEqual(process.call_args_list[1].args[1], [setup.sys.executable, '-m', 'playwright', 'install', 'chromium'])
            self.assertEqual(self.app.settings['perchance_browser'], 'managed.exe')
            self.assertEqual(health.call_count, 2)
            self.assertTrue(self.app.settings_path.exists())

    def test_failed_package_or_browser_install_is_not_ready(self):
        with patch.object(setup, 'process', return_value=(1, '', 'download failed')):
            with self.assertRaisesRegex(RuntimeError, 'dependency installation failed'):setup.install(self.app)
        with patch.object(setup, 'process', side_effect=[(0, '', ''), (1, '', 'browser download failed')]), \
             patch.object(setup, 'health', return_value={'ready': False, 'reason': 'missing browser'}):
            with self.assertRaisesRegex(RuntimeError, 'browser installation failed'):setup.install(self.app)

    def test_process_cancellation_kills_child(self):
        self.app.cancel_event.set()
        with patch.object(setup.subprocess, 'Popen') as factory:
            child = factory.return_value; child.poll.return_value = None
            with self.assertRaises(Cancelled):setup.process(self.app, ['fixture'])
            child.kill.assert_called_once(); child.communicate.assert_called_once()


if __name__ == '__main__':unittest.main()
