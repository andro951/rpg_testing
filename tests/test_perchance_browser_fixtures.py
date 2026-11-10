"""Exercise browser-smoke preflight fixtures without Chromium, sockets or inference."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.helpers.perchance_environment import simulated_eight_gb_gpu
from tests.test_perchance import fixture, FakeBackend
from workbench import inventory, perchance, perchance_setup, preflight
from workbench.controller import Controller
from workbench.domain import write_json


class PerchanceBrowserFixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        write_json(root / 'test_specs/fixture.json', fixture())
        self.app = Controller(root)
        self.app.settings.update(sync_source=False, publish_results=False, perchance_only=True)
        FakeBackend.created = []
        FakeBackend.response = 'READY'
        FakeBackend.failure = None
        real_run = perchance.run
        patches = (
            simulated_eight_gb_gpu(),
            patch.object(perchance, 'browser_executable', return_value=__file__),
            patch.object(perchance.importlib.util, 'find_spec', return_value=object()),
            patch.object(perchance_setup, 'health', return_value={'ready': True, 'reason': ''}),
            patch.object(self.app, 'backend_version', return_value='synthetic-readiness-only'),
            patch.object(self.app, 'source_commit', return_value=None),
            patch('workbench.controller.NativeBackend', side_effect=AssertionError('No native model may load')),
            patch.object(perchance, 'run', side_effect=lambda app, report, plan, **kwargs:
                real_run(app, report, plan, FakeBackend, **{k:v for k,v in kwargs.items() if k != 'backend_factory'})),
        )
        for context in patches:
            context.__enter__()
            self.addCleanup(context.__exit__, None, None, None)

    def test_gpu_fixture_covers_overview_and_provider_preflight_imports(self):
        self.assertEqual(inventory.detect_gpus(), preflight.detect_gpus())
        report = self.app.check()
        self.assertTrue(report['ready'], report['issues'])
        self.assertEqual(report['issues'], [])
        self.assertEqual(report['gpu']['total_gib'], 8)
        self.assertEqual(report['plan']['pending'], 3)
        self.assertEqual(report['plan']['groups'][-1]['model_id'], perchance.MODEL_ID)
        self.assertEqual(report['perchance_setup']['status'], 'ready')
        self.assertEqual(FakeBackend.created, [])

    def test_overview_then_targeted_resume_preserves_independent_trials(self):
        self.app.run()
        self.assertEqual(self.app.state, 'finished')
        self.assertEqual(len(self.app.store.all()), 3)
        self.assertEqual(len(FakeBackend.created), 1)
        self.assertEqual(len(FakeBackend.created[0].calls), 3)
        self.assertTrue(all(row['timeout_seconds'] == 300 for row in self.app.store.all()))
        before = {p: p.read_bytes() for p in self.app.store.root.glob('*/*.json')}
        report = self.app.check(selection={'model_id': perchance.MODEL_ID})
        self.assertTrue(report['ready'], report['issues'])
        self.assertEqual(report['plan']['pending'], 0)
        self.app.run(selection={'model_id': perchance.MODEL_ID})
        self.assertEqual(self.app.completed_now, 0)
        self.assertEqual(len(FakeBackend.created), 1)
        self.assertEqual(before, {p: p.read_bytes() for p in self.app.store.root.glob('*/*.json')})


if __name__ == '__main__':
    unittest.main()
