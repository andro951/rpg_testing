"""Combined Run all uses real planning/persistence and simulated execution only."""
import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_perchance import FakeBackend, fixture
from workbench import perchance, preflight
from workbench.controller import Controller
from workbench.domain import load_tests as load_catalog, write_json
from workbench.planning import pending_plan, public_plan
from workbench.workflows import Cancelled


class RunAllPerchanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        test = fixture(); test['timeout_seconds'] = 120
        write_json(self.root / 'test_specs/fixture.json', test)
        self.app = Controller(self.root)
        self.app.settings['sync_source'] = False
        self.model = {'id': 'local-fixture', 'files': ['fixture.gguf'], 'required_vram_gb': 8,
                      'sha256': {'fixture.gguf': 'a' * 64}}
        self.app.catalog = lambda: [copy.deepcopy(self.model)]
        self.app.backend_version = lambda: 'SIMULATED'
        self.app.source_commit = lambda: None
        self.tier = 8; self.events = []; self.stop = False; self.cancel = False
        FakeBackend.created = []; FakeBackend.failure = None; FakeBackend.response = 'READY'
        patches = [
            patch.object(preflight, 'build', side_effect=self.native_preflight),
            patch('workbench.inventory.detect_gpus', side_effect=lambda: [{'name': 'TEST GPU', 'total_gib': self.tier}]),
            patch.object(perchance, 'browser_executable', return_value=__file__),
            patch.object(perchance.importlib.util, 'find_spec', return_value=object()),
            patch('workbench.scheduler.Session', side_effect=self.native_session),
        ]
        real_remote_run = perchance.run
        def remote_run(app, report, plan, **kwargs):
            if plan['pending']: self.events.append('perchance')
            return real_remote_run(app, report, plan, FakeBackend, **kwargs)
        patches.append(patch.object(perchance, 'run', side_effect=remote_run))
        for item in patches:
            item.start(); self.addCleanup(item.stop)

    def native_preflight(self, app, preparation=None, track_progress=True, selection=None):
        target = {'gpu_name': 'TEST GPU', 'vram_gb': self.tier, 'backend': 'SIMULATED'}
        plan = pending_plan([self.model], load_catalog(self.root / 'test_specs'), target, app.store, selection)
        report = {'ready': not preparation, 'prepared': bool(preparation), 'issues': [],
                  'plan': public_plan(plan), 'gpu': {'name': 'TEST GPU', 'total_gib': self.tier},
                  'note': 'Simulated native preflight.', 'selection': selection}
        return report, plan

    def native_session(self, app, report, plan, backend_factory):
        owner = self
        class Session:
            def run(self):
                app.run_total = plan['pending']; app.run_processed = 0
                for group in plan['groups']:
                    for job in group['jobs']:
                        owner.events.append('local')
                        app.store.save({'model_id': group['model']['id'], 'case_id': job['case_id'],
                                        'status': 'completed', 'score': {'exact_match': True}, 'simulated': True})
                        app.completed_now += 1; app.run_processed += 1
                app.stop_after_model = owner.stop
                if owner.cancel: app.cancel_event.set()
        return Session()

    def test_eight_gb_run_all_local_first_remote_last_and_resume(self):
        report, plan = self.app.build_preflight()
        self.assertTrue(report['ready'])
        self.assertEqual(plan['pending'], 4)
        self.assertEqual(report['plan']['groups'][-1]['model_id'], perchance.MODEL_ID)
        self.app.run()
        self.assertEqual(self.events, ['local', 'local', 'local', 'perchance'])
        self.assertEqual((self.app.run_total, self.app.run_processed, self.app.completed_now), (4, 4, 4))
        self.assertEqual(self.app.report['plan']['pending'], 0)
        remote = next(r for r in self.app.store.all() if r['model_id'] == perchance.MODEL_ID)
        self.assertEqual(remote['timeout_seconds'], 300)
        self.assertEqual(remote['aliases'][0]['requested_timeout_seconds'], 120)
        self.assertEqual(len(remote['aliases']), 3)
        self.app.run()
        self.assertEqual(self.app.completed_now, 0)
        self.assertEqual(len(FakeBackend.created), 1)

    def test_completed_locals_do_not_prevent_pending_perchance(self):
        self.stop = True; self.app.run()
        self.assertEqual(self.app.report['plan']['pending'], 1)
        self.stop = False; self.events.clear(); self.app.run()
        self.assertEqual(self.events, ['perchance'])
        self.assertEqual(self.app.completed_now, 1)

    def test_stop_and_cancel_before_remote_do_not_open_browser(self):
        for control in ('stop', 'cancel'):
            with self.subTest(control=control):
                setattr(self, control, True)
                self.app.run()
                self.assertFalse(FakeBackend.created)
                setattr(self, control, False)
                self.app.cancel_event.clear()

    def test_larger_workers_and_targeted_local_runs_exclude_remote(self):
        for tier in (11, 12, 16, 24):
            self.tier = tier
            self.assertNotIn('perchance_plan', self.app.build_preflight()[1])
        self.tier = 8
        for selection in ({'model_id': self.model['id']}, {'all_models': True, 'test_id': fixture()['id']}):
            self.assertNotIn('perchance_plan', self.app.build_preflight(selection=selection)[1])
        self.app.demo = True
        self.assertNotIn('perchance_plan', self.app.build_preflight()[1])

    def test_missing_remote_dependency_blocks_combined_run_before_execution(self):
        with patch.object(perchance.importlib.util, 'find_spec', return_value=None):
            self.app.run()
        self.assertEqual(self.app.state, 'idle')
        self.assertFalse(self.events)
        self.assertTrue(any(i['id'] == 'perchance_dependency' for i in self.app.report['issues']))

    def test_cancel_before_standalone_remote_open(self):
        plan = self.app.build_preflight()[1]['perchance_plan']
        self.app.cancel_event.set()
        with self.assertRaises(Cancelled):
            perchance.run(self.app, {}, plan)
        self.assertFalse(FakeBackend.created)

    def test_remote_deadline_is_fixed_when_local_deadline_changes(self):
        first = self.app.build_preflight()[1]['perchance_plan']
        test = fixture(); test['timeout_seconds'] = 600
        write_json(self.root / 'test_specs/fixture.json', test)
        second = self.app.build_preflight()[1]['perchance_plan']
        self.assertEqual(first['groups'][0]['case_id'], second['groups'][0]['case_id'])
        self.assertEqual(second['groups'][0]['test']['timeout_seconds'], 300)
        self.app.run(selection={'model_id': perchance.MODEL_ID})
        self.assertAlmostEqual(FakeBackend.created[0].deadline - time.monotonic(), 300, delta=3)


if __name__ == '__main__':
    unittest.main()
