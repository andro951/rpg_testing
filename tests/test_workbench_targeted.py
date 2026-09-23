"""Targeted scheduling uses real controller/planner/persistence and simulated inference only."""
import copy
import io
import json
import shutil
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from workbench.controller import Controller
from workbench.domain import load_tests as read_tests, read_json, write_json
from workbench.execution_policy import DoesNotFit, fallback_id
from workbench.planning import normalize_selection, pending_plan
from workbench.restarts import UpdateCoordinator, consume_request
from workbench.workflows import Cancelled

ROOT = Path(__file__).resolve().parents[1]


def configure_demo(app):
    """Two models make accidental broadening visible; no actual weights are used."""
    base = app.catalog()[0]
    models = [dict(copy.deepcopy(base), id=mid, base_model='Simulated ' + mid) for mid in ('alpha', 'beta')]
    item = app.demo_models()[0]
    inventory = [dict(copy.deepcopy(item), id=m['id'], name=m['base_model'], catalog=m) for m in models]
    app.catalog = lambda: copy.deepcopy(models)
    app.demo_models = lambda: copy.deepcopy(inventory)
    return models, inventory


class TargetedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(ROOT / 'test_specs', self.root / 'test_specs')
        self.app = Controller(self.root, True)
        self.models, self.inventory = configure_demo(self.app)
        self.tests = read_tests(self.root / 'test_specs')
        self.scope = {'model_id': 'beta', 'test_id': 'time_only', 'variant_id': 'direct_json_patch'}

    def jobs(self):
        return [j for g in self.app.plan['groups'] for j in g['jobs']]

    def wait(self):
        self.app.thread.join(15)
        self.assertFalse(self.app.operation.locked())
        self.assertNotEqual(self.app.state, 'error', self.app.message)

    def test_individual_case_is_exact_subset_of_full_plan(self):
        self.app.check()
        full = {j['case_id'] for j in self.jobs()}
        target = copy.deepcopy(self.app.plan['target'])
        context = copy.deepcopy(self.app.plan['groups'][1]['context'])
        self.assertTrue(self.app.check(selection=self.scope)['ready'])
        self.assertEqual(len(self.jobs()), 1)
        self.assertIn(self.jobs()[0]['case_id'], full)
        self.assertEqual(self.app.plan['target'], target)
        self.assertEqual(self.app.plan['groups'][0]['context'], context)
        self.assertEqual(self.app.report['selection'], self.scope)

    def test_context_recipe_still_includes_other_enabled_tests(self):
        path = self.root / 'test_specs/time_only.json'
        other = read_json(path); other['id'] = 'large_context_fixture'; other['shared_prefix'] = 'Safe synthetic context. ' * 1000
        write_json(self.root / 'test_specs/large_context_fixture.json', other)
        self.app.check(); full = {j['case_id'] for j in self.jobs()}
        recipe = self.app.plan['target']['context_recipe']
        self.app.check(selection=self.scope)
        self.assertEqual(self.app.plan['target']['context_recipe'], recipe)
        self.assertGreater(recipe, 16384)
        self.assertIn(self.jobs()[0]['case_id'], full)

    def test_single_variant_keeps_configured_repetitions(self):
        path = self.root / 'test_specs/time_only.json'; test = read_json(path)
        test['repetitions'] = 3; write_json(path, test)
        self.app.run(selection=self.scope)
        records = self.app.store.all()
        self.assertEqual(len(records), 3)
        self.assertEqual({r['model_id'] for r in records}, {'beta'})
        self.assertEqual({r['variant_id'] for r in records}, {'direct_json_patch'})
        self.assertEqual({r['repetition'] for r in records}, {0, 1, 2})
        self.assertTrue(all(r['status'] == 'completed' for r in records))
        self.app.run(selection=self.scope)
        self.assertEqual(self.app.completed_now, 0)
        self.assertEqual(len(self.app.store.all()), 3)

    def test_one_test_all_variants_and_global_resume(self):
        self.app.run(selection={'model_id': 'beta', 'test_id': 'time_only'})
        records = self.app.store.all()
        self.assertEqual(len(records), 4)
        self.assertEqual({r['test_id'] for r in records}, {'time_only'})
        saved = {p: p.read_bytes() for p in self.app.store.root.rglob('*.json')}
        self.app.check()
        self.assertEqual(self.app.report['plan']['complete'], 4)
        self.assertGreater(self.app.report['plan']['pending'], 0)
        self.assertTrue(all(p.read_bytes() == data for p, data in saved.items()))

    def test_one_test_all_models_is_explicit_scope(self):
        selection={'all_models':True,'test_id':'time_only','variant_id':'direct_json_patch'}
        self.app.run(selection=selection)
        records=self.app.store.all()
        self.assertEqual(len(records),2)
        self.assertEqual({r['model_id'] for r in records},{'alpha','beta'})
        self.assertEqual({r['test_id'] for r in records},{'time_only'})
        self.assertEqual({r['variant_id'] for r in records},{'direct_json_patch'})
        self.assertTrue(all(r['provenance']['selection']==selection for r in records))
        self.app.run(selection=selection)
        self.assertEqual(self.app.completed_now,0)
        self.assertEqual(len(self.app.store.all()),2)

    def test_one_model_selected_tests_only(self):
        selected=['time_only','clothing_append']
        expected=sum(t.get('repetitions',1)*sum(v.get('enabled',True) for v in t['variants'])
                     for t in self.tests if t['id'] in selected)
        selection={'model_id':'alpha','test_ids':selected}
        self.app.run(selection=selection)
        records=self.app.store.all()
        self.assertEqual(len(records),expected)
        self.assertEqual({r['model_id'] for r in records},{'alpha'})
        self.assertEqual({r['test_id'] for r in records},set(selected))
        self.assertEqual(self.app.report['selection'],{'model_id':'alpha','test_ids':sorted(selected)})
        self.app.run(selection=selection)
        self.assertEqual(self.app.completed_now,0)
        self.assertEqual(len(self.app.store.all()),expected)

    def test_one_model_all_tests_does_not_edit_configuration(self):
        before = {p: p.read_bytes() for p in (self.root / 'test_specs').glob('*.json')}
        expected = sum(t.get('repetitions', 1) * sum(v.get('enabled', True) for v in t['variants']) for t in self.tests)
        self.app.run(selection={'model_id': 'alpha'})
        records = self.app.store.all()
        self.assertEqual(len(records), expected)
        self.assertEqual({r['model_id'] for r in records}, {'alpha'})
        self.assertTrue(all(p.read_bytes() == data for p, data in before.items()))
        self.assertFalse((self.root / 'models.json').exists())
        self.app.check()
        self.assertEqual(self.app.report['plan']['pending'], expected)
        self.assertEqual(self.app.report['plan']['complete'], expected)

    def test_selected_preflight_ignores_missing_unassigned_and_corrupt_other_models(self):
        self.inventory[:] = [x for x in self.inventory if x['id'] == 'beta']
        extra = dict(copy.deepcopy(self.inventory[0]), id='uncatalogued', required_vram_gb=None, catalogued=False)
        self.inventory.append(extra)
        bad = self.app.store.path('alpha', 'a' * 64); bad.parent.mkdir(); bad.write_text('{bad')
        self.assertTrue(self.app.check(selection=self.scope)['ready'])
        self.assertEqual(len(self.app.last_models), 2, 'Scoped preflight must not hide other inventory cards')
        self.assertFalse(self.app.check()['ready'])

    def test_selected_missing_model_still_blocks(self):
        self.inventory[:] = [x for x in self.inventory if x['id'] != 'beta']
        report = self.app.check(selection=self.scope)
        self.assertFalse(report['ready'])
        self.assertIn('missing_beta', [i['id'] for i in report['issues']])

    def test_ineligible_model_is_not_silently_reported_ready(self):
        self.models[1]['required_vram_gb'] = 80
        report = self.app.check(selection=self.scope)
        self.assertFalse(report['ready'])
        self.assertIn('selected_model_tier', [i['id'] for i in report['issues']])
        self.assertEqual(self.app.store.all(), [])

    def test_invalid_or_stale_selection_never_runs_all(self):
        for selection in ({}, [], {'test_id': 'time_only'}, {'model_id': '../oops'},
                          {'model_id': 'beta', 'variant_id': 'direct_json_patch'},
                          {'model_id': 'missing'}, {'model_id': 'beta', 'test_id': 'missing'},
                          {'model_id':'beta','test_ids':[]},
                          {'model_id':'beta','test_ids':['time_only','time_only']},
                          {'model_id':'beta','test_ids':['missing']},
                          {'model_id':'beta','test_id':'time_only','test_ids':['clothing_append']},
                          {'model_id':'beta','test_ids':['time_only'],'variant_id':'direct_json_patch'},
                          {'all_models':False,'test_id':'time_only'},
                          {'all_models':True},
                          {'all_models':True,'test_ids':['time_only']},
                          {'model_id':'beta','all_models':True,'test_id':'time_only'},
                          {**self.scope, 'variant_id': 'missing'}, {**self.scope, 'force': True}):
            with self.subTest(selection=selection), self.assertRaises(ValueError):
                self.app.start('run', {'selection': selection})
            self.assertFalse(self.app.operation.locked())
        self.assertEqual(self.app.store.all(), [])
        self.assertIsNone(self.app.thread)

    def test_disabled_selections_are_rejected(self):
        self.models[1]['enabled'] = False
        with self.assertRaises(ValueError): self.app.check(selection=self.scope)
        self.models[1]['enabled'] = True
        path = self.root / 'test_specs/time_only.json'; test = read_json(path)
        test['variants'][0]['enabled'] = False; write_json(path, test)
        with self.assertRaises(ValueError): self.app.check(selection=self.scope)
        test['enabled'] = False; write_json(path, test)
        with self.assertRaises(ValueError): self.app.check(selection={'model_id': 'beta', 'test_id': 'time_only'})

    def test_options_have_no_answer_data_and_disabled_choices_are_excluded(self):
        self.models[0]['enabled'] = False
        options = self.app.run_options()
        self.assertEqual([m['id'] for m in options['models']], ['beta'])
        self.assertNotIn('expected_state', json.dumps(options))
        self.assertNotIn('initial_state', json.dumps(options))
        self.assertIn('time_only', [t['id'] for t in options['tests']])
        self.assertTrue(all(t['timeout_seconds']==60 for t in options['tests']))

    def test_auto_repair_rechecks_same_selection_without_inference(self):
        self.app.check(selection=self.scope)
        # Installers may clear the old report; the scope must already be captured.
        def fix(_): self.app.report = None
        with patch.object(self.app, 'fix', side_effect=fix):
            self.app.start('fix', {'issue_id': 'fixture'}); self.wait()
        self.assertEqual(self.app.report['selection'], self.scope)
        self.assertEqual(self.app.report['plan']['pending'], 1)
        self.assertEqual(self.app.store.all(), [])

    def test_selection_is_in_exported_report_and_result_provenance(self):
        self.app.run(selection=self.scope)
        self.assertEqual(self.app.store.all()[0]['provenance']['selection'], self.scope)
        with zipfile.ZipFile(io.BytesIO(self.app.export())) as z:
            summary = json.loads(z.read('summary.json'))
        self.assertEqual(summary['latest_preflight']['selection'], self.scope)

    def test_source_sync_captures_selection_before_restart(self):
        self.app.demo = False; self.app.settings['sync_source'] = True
        with patch('workbench.gitops.pull', return_value=True):
            with self.assertRaises(RuntimeError): self.app.run(selection=self.scope)
        self.assertTrue(self.app.restart_required)
        self.assertEqual(self.app.requested_run_selection, self.scope)
        self.assertEqual(self.app.store.all(), [])

    def test_scoped_recovery_keeps_same_model_and_case(self):
        self.app.check(selection=self.scope)
        from workbench.demo_native import DemoNative
        attempts = []
        original = DemoNative.load
        def load(backend, model, context, *a, **kw):
            attempts.append(model['id'])
            if len(attempts) == 1: raise DoesNotFit('fixture transient allocation failure')
            return original(backend, model, context, *a, **kw)
        with patch.object(DemoNative, 'load', load): self.app.run(selection=self.scope)
        self.assertEqual(attempts, ['beta', 'beta'])
        records = self.app.store.all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['status'], 'completed')
        self.assertEqual(records[0]['attempts'][0]['status'], 'skipped')

    def test_cancelled_scoped_run_resumes_only_its_case(self):
        self.app.cancel_event.set()
        with self.assertRaises(Cancelled): self.app.run(selection=self.scope)
        self.app.cancel_event.clear()
        self.app.run(selection=self.scope)
        self.assertEqual(len(self.app.store.all()), 1)
        self.assertEqual(self.app.report['selection'], self.scope)

    def test_terminal_skip_stays_terminal_until_explicit_delete(self):
        self.app.check(selection=self.scope); job = self.jobs()[0]
        path = self.app.store.save({'case_id': job['case_id'], 'model_id': 'beta', 'status': 'skipped',
                                    'reason': 'runtime_error', 'artifact_identity': self.app.plan['groups'][0]['model']['artifact_identity']})
        self.app.run(selection=self.scope)
        self.assertEqual(self.app.completed_now, 0)
        self.assertEqual(self.app.report['plan']['pending'], 0)
        self.app.delete_result('beta', job['case_id'])
        self.app.check(selection=self.scope)
        self.assertEqual(self.app.report['plan']['pending'], 1)


class TargetedRestartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.app = Controller(Path(self.tmp.name), True)
        self.scope = {'model_id': 'beta', 'test_id': 'time_only'}
        self.path = self.app.data / 'resume-after-update.json'

    def test_update_request_preserves_targeted_selection(self):
        app = self.app; closed = threading.Event()
        class Server:
            def __init__(self): self.app = app; self.exit_requested = False
            def close_all(self): closed.set()
        self.app.requested_run_selection = self.scope; self.app.restart_required = True
        coordinator = UpdateCoordinator(Server(), .01).start()
        self.addCleanup(coordinator.stop.set)
        self.assertTrue(closed.wait(2)); coordinator.thread.join(2)
        self.assertEqual(read_json(self.path)['selection'], self.scope)
        self.assertTrue(consume_request(self.app))
        self.assertEqual(self.app.requested_run_selection, self.scope)

    def test_restart_invokes_only_saved_selection(self):
        app = self.app
        class Server:
            def __init__(self): self.app = app
        write_json(self.path, {'operation': 'run', 'created_at': time.time(), 'restart_count': 1, 'selection': self.scope})
        with patch.object(app, 'start') as start:
            c = UpdateCoordinator(Server(), .01).start()
            c.stop.set(); c.thread.join(2)
            start.assert_called_once_with('run', {'selection': self.scope})

    def test_malformed_restart_scope_never_becomes_full_run(self):
        write_json(self.path, {'operation': 'run', 'created_at': time.time(), 'restart_count': 1, 'selection': {}})
        self.assertFalse(consume_request(self.app))
        self.assertIsNone(self.app.thread)


if __name__ == '__main__': unittest.main()
