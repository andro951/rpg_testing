import copy
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from workbench.controller import Controller
from workbench.domain import ResultStore, code_fingerprint, read_json, write_json, digest
from workbench import perchance as provider


def fixture():
    return {'schema_version': 2, 'id': 'perchance_fixture', 'name': 'Text bridge fixture', 'workflow': 'steps',
            'repetitions': 3, 'timeout_seconds': 10, 'source': {'initial_state': {}, 'new_information': ''},
            'instructions': 'Follow the exact requested output format.', 'variants': [
                {'id': 'a', 'cache': 'on', 'prompt_style': 'direct_text_v1',
                 'steps': [{'id': 'answer', 'type': 'generate', 'prompt': 'Reply exactly with READY.',
                            'output': {'type': 'text'}, 'sampling': {'temperature': 0, 'top_p': 1, 'seed': 42}}],
                 'result': {'step': 'answer', 'representation': 'answers'}, 'expected_answers': {'answer': 'READY'}}]}


class FakeBackend:
    created = []
    response = 'READY'
    failure = None
    def __init__(self, settings):
        self.environment = {'simulated_transport': True}
        self.page = type('FakePage', (), {'close': lambda page: None})()
        self.calls = []
        self.closed = False
        self.created.append(self)
    def open(self):
        pass
    def reset(self):
        self.page = type('FakePage', (), {'close': lambda page: None})()
    def close(self):
        self.closed = True
    def cancel(self):
        pass
    def generate(self, messages, requested, schema, cancel):
        self.calls.append(messages)
        if self.failure:
            error = self.failure('test failure')
            error.partial_response = {'text': 'PARTIAL', 'raw_chunks': [{'text': 'PARTIAL'}]}
            raise error
        return {'text': self.response, 'finish_reason': 'provider_completed', 'sampling': None,
                'applied_sampling': None, 'requested_sampling': requested, 'cached_tokens': None,
                'request_seconds': .1, 'raw_chunks': [{'text': self.response}]}


class PerchanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.test = fixture()
        write_json(self.root / 'test_specs/fixture.json', self.test)
        self.app = Controller(self.root)
        self.app.settings['sync_source'] = False
        self.selection = {'model_id': provider.MODEL_ID}
        self.target = {'backend': 'perchance', 'vram_gb': 8}
        FakeBackend.created = []; FakeBackend.failure = None; FakeBackend.response = 'READY'
        # Unit preflight models installed prerequisites on browser-free CI workers.
        for prerequisite in (patch.object(provider, 'browser_executable', return_value=__file__),
                             patch.object(provider.importlib.util, 'find_spec', return_value=object())):
            prerequisite.start(); self.addCleanup(prerequisite.stop)
    def make_plan(self, tests=None, selection=None):
        return provider.plan(tests or [self.test], self.app.settings, self.target, self.app.store, selection or self.selection)

    def test_option_is_separate_from_gguf_catalog_and_fixed_tier(self):
        self.assertEqual(self.app.catalog(), [])
        option = self.app.run_options()['models'][0]
        self.assertEqual(option['id'], provider.MODEL_ID)
        self.assertEqual(option['required_vram_gb'], 8)
        self.assertFalse((self.root / 'models.json').exists())
        with self.assertRaisesRegex(ValueError, 'fixed 8'):
            self.app.assign_model(provider.MODEL_ID, 12)

    def test_collapse_settings_within_each_independent_repetition_and_subset_identity(self):
        alternate = copy.deepcopy(self.test['variants'][0])
        alternate.update(id='b', cache='off')
        alternate['steps'][0]['sampling'].update(temperature=1, top_p=.5, seed=100)
        self.test['variants'].append(alternate)
        full = self.make_plan()
        self.assertEqual((full['requested_cases'], full['independent_observations'], full['collapsed_cases']), (6, 3, 3))
        subset = self.make_plan(selection={**self.selection, 'test_id': self.test['id'], 'variant_id': 'b'})
        self.assertEqual(subset['groups'][0]['case_id'], full['groups'][0]['case_id'])
        self.assertEqual(subset['groups'][0]['variant']['id'], 'a')
        self.assertEqual(len(full['groups'][0]['aliases']), 2)

    def test_distinct_prompts_states_outputs_oracles_and_workflows(self):
        for field in ('prompt', 'state', 'schema', 'oracle', 'workflow', 'representation'):
            other = copy.deepcopy(self.test); other['id'] = 'other'
            if field == 'prompt':other['variants'][0]['steps'][0]['prompt'] += ' Different.'
            elif field == 'state':other['source']['initial_state'] = {'n': 1}
            elif field == 'schema':other['variants'][0]['steps'][0]['output'] = {'type': 'boolean'}
            elif field == 'oracle':other['variants'][0]['expected_answers']['answer'] = 'OTHER'
            elif field == 'representation':other['variants'][0]['state_presentation'] = 'raw_json'
            else:
                other['variants'][0]['steps'].append({'id':'second','type':'generate','prompt':'Another step','output':{'type':'text'},'uses':['answer']})
            with self.subTest(field=field):self.assertEqual(self.make_plan([self.test, other])['independent_observations'], 6)

    def test_remote_preflight_bypasses_native_and_larger_tiers(self):
        for tier in (8, 11, 12, 16):
            with patch('workbench.inventory.detect_gpus', return_value=[{'name':'GPU','total_gib':tier}]), patch.object(provider.BrowserBackend, 'open') as opened:
                report, plan = self.app.build_preflight(selection=self.selection)
            self.assertEqual(report['ready'], tier == 8)
            self.assertEqual(plan['pending'], 3)
            opened.assert_not_called()
            self.assertFalse(any(issue['id'] == 'backend' for issue in report['issues']))
        report, _ = self.app.build_preflight({'gpu_name': 'GPU', 'vram_gb': 8}, self.selection)
        self.assertTrue(report['prepared']); self.assertFalse(report['ready'])

    def test_preflight_missing_browser_dependency_and_corruption(self):
        with patch.object(provider, 'browser_executable', return_value=None), patch.object(provider.importlib.util, 'find_spec', return_value=None):
            report, _ = self.app.build_preflight({'gpu_name':'GPU','vram_gb':8}, self.selection)
        self.assertEqual({i['id'] for i in report['issues']}, {'perchance_browser','perchance_dependency'})
        pending = self.make_plan(); path = self.app.store.path(provider.MODEL_ID, pending['groups'][0]['case_id'])
        path.parent.mkdir(); path.write_text('{}')
        with self.assertRaises(ValueError):self.make_plan()

    def test_run_all_repetitions_resume_mapping_export_and_no_original_changes(self):
        pending = self.make_plan()
        before = (self.root/'test_specs/fixture.json').read_bytes()
        provider.run(self.app, {'gpu':{}}, pending, FakeBackend)
        self.assertEqual(len(FakeBackend.created[0].calls), 3)
        self.assertTrue(FakeBackend.created[0].closed)
        self.assertEqual(len(self.app.store.all()), 3)
        record = self.app.store.all()[0]
        self.assertEqual(len(record['aliases']), 1)
        self.assertIsNone(record['calls'][0]['applied_sampling'])
        self.assertEqual(record['execution_class'], 'remote_service')
        self.assertFalse(record['feature_applicability']['cache_control'])
        provider.run(self.app, {}, self.make_plan(), FakeBackend)
        self.assertEqual(len(FakeBackend.created), 1)
        self.assertEqual(before, (self.root/'test_specs/fixture.json').read_bytes())
        archive = zipfile.ZipFile(io.BytesIO(self.app.export()))
        self.assertTrue(any(n.startswith('perchance-plans/') for n in archive.namelist()))
        summary = json.loads(archive.read('summary.json'))
        self.assertEqual(summary['perchance']['independent_observations'], 3)
        self.assertEqual(summary['perchance']['mapped_requested_cases'], 3)
        self.assertEqual({r['repetition'] for r in self.app.store.all()}, {0, 1, 2})
        self.assertEqual(len({r['calls'][0]['requested_sampling']['seed'] for r in self.app.store.all()}), 3)

    def test_timeout_changes_watchdog_only_and_terminals_do_not_rerun(self):
        before = self.make_plan()
        changed = copy.deepcopy(self.test); changed['timeout_seconds'] = 120
        after = self.make_plan([changed])
        self.assertEqual(before['groups'][0]['case_id'], after['groups'][0]['case_id'])
        self.assertEqual(before['groups'][0]['aliases'][0]['requested_id'], after['groups'][0]['aliases'][0]['requested_id'])
        self.assertEqual(after['groups'][0]['test']['timeout_seconds'],300)
        self.assertEqual(after['groups'][0]['aliases'][0]['requested_timeout_seconds'],120)
        duplicate = copy.deepcopy(changed); duplicate['id'] = 'other'
        combined = self.make_plan([self.test, duplicate])
        self.assertEqual(combined['independent_observations'],3)
        self.assertEqual(combined['groups'][0]['test']['timeout_seconds'],300)
        self.assertEqual(self.test['timeout_seconds'],10)
        for failure in (None, provider.PerchanceTimeout):
            with self.subTest(failure=failure):
                tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
                self.app.store = ResultStore(Path(tmp.name))
                FakeBackend.response = 'WRONG'; FakeBackend.failure = failure
                pending = self.make_plan(); provider.run(self.app, {}, pending, FakeBackend)
                record = self.app.store.read(self.app.store.path(provider.MODEL_ID,pending['groups'][0]['case_id']))
                self.assertFalse(record['score']['exact_match'])
                self.assertEqual(self.make_plan([changed])['pending'],0)
                if failure:self.assertEqual(record['calls'][0]['text'],'PARTIAL')

    def test_cancellation_and_infrastructure_attempts(self):
        cid = self.make_plan()['groups'][0]['case_id']
        FakeBackend.failure = provider.Cancelled
        with self.assertRaises(provider.Cancelled):provider.run(self.app, {}, self.make_plan(), FakeBackend)
        self.assertEqual(self.app.store.all()[0]['status'], 'aborted')
        self.assertTrue(FakeBackend.created[0].closed)
        FakeBackend.failure = RuntimeError
        provider.run(self.app, {}, self.make_plan(), FakeBackend)
        self.assertEqual(len(self.app.store.read(self.app.store.path(provider.MODEL_ID, cid))['attempts']), 1)
        FakeBackend.failure = None
        provider.run(self.app, {}, self.make_plan(), FakeBackend)
        self.assertEqual(len(self.app.store.read(self.app.store.path(provider.MODEL_ID, cid))['attempts']), 2)

    def test_schema_baseline_validates_locally_and_multistep_is_not_collapsed(self):
        self.test['variants'][0]['steps'][0]['output'] = {'type':'boolean'}
        self.test['variants'][0]['expected_answers']['answer'] = True
        FakeBackend.response = 'true'
        pending=self.make_plan(); provider.run(self.app, {}, pending, FakeBackend)
        record=self.app.store.all()[0]
        self.assertTrue(record['score']['exact_match'])
        self.assertFalse(record['feature_applicability']['constrained_decoding'])
        self.test['variants'][0]['steps'].append({'id':'followup','type':'generate','prompt':'Followup','uses':['answer'],'output':{'type':'text'}})
        pending=self.make_plan(); provider.run(self.app, {}, pending, FakeBackend)
        self.assertEqual(len(FakeBackend.created[-1].calls), 6)
        self.assertIn('Previous output', str(FakeBackend.created[-1].calls[-1]))

    def test_settings_are_validated_and_identity_tracks_epoch(self):
        cid=self.make_plan()['groups'][0]['case_id']
        self.app.configure({'perchance_epoch':'new'})
        self.assertNotEqual(cid,self.make_plan()['groups'][0]['case_id'])
        for url in ('http://perchance.org/a','https://example.com/a','https://user:pass@perchance.org/a'):
            with self.assertRaises(ValueError):self.app.configure({'perchance_url':url})
        with self.assertRaises(ValueError):self.app.configure({'perchance_headless':'true'})

    def test_client_hardware_does_not_create_duplicate_remote_trials(self):
        first=self.make_plan()['groups'][0]['case_id']
        self.target.update(gpu_name='another 8 GB GPU',os='another OS')
        self.assertEqual(first,self.make_plan()['groups'][0]['case_id'])

    def test_default_representation_and_explicit_default_are_equivalent(self):
        other=copy.deepcopy(self.test);other['id']='other'
        other['variants'][0]['state_presentation']='indexed_arrays'
        self.assertEqual(self.make_plan([self.test,other])['independent_observations'],3)

    def test_browser_transport_preserves_final_text_and_timeout_cancel_partials(self):
        for mode in ('complete','timeout','cancel','error'):
            backend=provider.BrowserBackend({})
            snapshot={'state':'completed' if mode=='complete' else 'error' if mode=='error' else 'running',
                      'text':'  RAW\n','chunks':[{'text':'  RAW\n'}],'firstVisibleMs':5,'error':'provider error'}
            class Frame:
                def evaluate(self, expression, arg):
                    return snapshot
            class Page:
                closed=False
                def close(self):self.closed=True
                def wait_for_timeout(self, ms):pass
            page=Page();backend.page=page;backend.frame=Frame()
            backend.deadline=0 if mode=='timeout' else None
            event=threading.Event()
            if mode=='cancel':event.set()
            if mode=='complete':
                result=backend.generate([{'role':'user','content':'Prompt'}],{},None,event)
                self.assertEqual(result['text'],'  RAW\n')
                self.assertIsNone(result['sampling'])
                self.assertEqual(result['first_visible_text_seconds'],.005)
            else:
                expected=provider.PerchanceTimeout if mode=='timeout' else provider.Cancelled if mode=='cancel' else RuntimeError
                with self.assertRaises(expected) as caught:
                    backend.generate([{'role':'user','content':'Prompt'}],{},None,event)
                self.assertEqual(caught.exception.partial_response['text'],'  RAW\n')
                if mode!='error':self.assertTrue(page.closed)

    def test_native_identity_fingerprint_after_clean_reset(self):
        self.assertEqual(code_fingerprint(), '56502881bc3c89f6b58c8f5e755b32f58cbd675274ed5363293b598aaddf9787')

    def legacy_record(self):
        policy = copy.deepcopy(provider.identity(self.app.settings))
        policy.update(policy=provider.LEGACY_POLICY, adapter_hash=provider.LEGACY_ADAPTER_HASH)
        policy['capabilities']['seed'] = 'unavailable_in_adapter'
        definition = provider.effective(self.test, self.test['variants'][0])
        cid = digest({'provider': policy, 'effective': definition})
        aliases = [{'test_id': self.test['id'], 'variant_id': 'a', 'repetition': rep,
                    'requested_id': digest({'legacy': cid, 'repetition': rep}),
                    'requested_definition': {'test': {k: v for k, v in self.test.items() if k not in ('variants', 'repetitions', 'timeout_seconds', 'name')}, 'variant': self.test['variants'][0]}}
                   for rep in range(3)]
        return {'status': 'completed', 'model_id': provider.MODEL_ID, 'case_id': cid, 'repetition': 0,
                'test_id': self.test['id'], 'variant_id': 'a', 'test_definition': self.test,
                'variant_definition': self.test['variants'][0], 'effective_definition': definition,
                'capability_policy': policy, 'artifact_identity': policy, 'aliases': aliases,
                'execution_class': 'remote_service', 'simulated': False,
                'provenance': {'workflow_code': code_fingerprint()},
                'outputs': {'answer': 'READY'}, 'score': {'exact_match': True},
                'calls': [{'step': 'answer', 'text': 'READY', 'finish_reason': 'provider_completed'}]}

    def test_old_baseline_fulfills_only_first_trial_and_preserves_resume_and_matrix(self):
        from reporting.report import build_report
        legacy = self.legacy_record()
        path = self.app.store.save(legacy); raw = path.read_bytes()
        pending = self.make_plan()
        self.assertEqual((pending['complete'], pending['pending']), (1, 2))
        self.assertEqual(pending['groups'][0]['case_id'], legacy['case_id'])
        self.assertTrue(pending['groups'][0]['legacy_baseline_reused'])
        self.assertEqual({g['repetition'] for g in pending['groups'] if not g['done']}, {1, 2})
        provider.run(self.app, {}, pending, FakeBackend)
        self.assertEqual(len(FakeBackend.created[0].calls), 2)
        self.assertEqual(path.read_bytes(), raw)
        records = self.app.store.all()
        report = build_report(records, [self.test])
        self.assertEqual(len(report['matrix']['models']), 1)
        self.assertEqual(report['remote_statistics']['mapped_requested_cases'], 3)
        self.assertEqual(report['remote_statistics']['independent_observations'], 3)
        self.assertEqual(report['remote_statistics']['collapsed_cases'], 0)
        rows = report['matrix']['rows']; self.assertEqual(len(rows), 3)
        for row in rows:
            cell = next(iter(row['cells'].values()))
            self.assertEqual(len(cell['primary_ids']), 1)
            self.assertFalse(cell['reference_ids'])
        provider.run(self.app, {}, self.make_plan(), FakeBackend)
        self.assertEqual(len(FakeBackend.created), 1)
        self.assertEqual(self.make_plan()['pending'], 0)

    def test_legacy_terminal_failures_and_timeouts_are_not_rerolled(self):
        for timeout in (False, True):
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as directory:
                self.app.store = ResultStore(Path(directory))
                record = self.legacy_record(); record['score']['exact_match'] = False; record['timed_out'] = timeout
                path = self.app.store.save(record); raw = path.read_bytes()
                pending = self.make_plan()
                self.assertEqual(pending['complete'], 1)
                provider.run(self.app, {}, pending, FakeBackend)
                self.assertEqual(len(FakeBackend.created[-1].calls), 2)
                self.assertEqual(path.read_bytes(), raw)

    def test_migration_rejects_changed_prompt_epoch_url_and_unknown_adapter(self):
        record = self.legacy_record(); self.app.store.save(record)
        altered = copy.deepcopy(self.test); altered['variants'][0]['steps'][0]['prompt'] += ' changed'
        self.assertEqual(self.make_plan([altered])['complete'], 0)
        for settings in ({'perchance_epoch': '2'}, {'perchance_url': 'https://perchance.org/different'}):
            self.assertEqual(provider.plan([self.test], settings, self.target, self.app.store, self.selection)['complete'], 0)
        with tempfile.TemporaryDirectory() as directory:
            self.app.store = ResultStore(Path(directory))
            record['capability_policy']['adapter_hash'] = 'unknown'
            record['case_id'] = digest({'provider': record['capability_policy'], 'effective': record['effective_definition']})
            self.app.store.save(record)
            self.assertEqual(self.make_plan()['complete'], 0)

    def test_extra_repetitions_only_add_new_trials(self):
        provider.run(self.app, {}, self.make_plan(), FakeBackend)
        self.test['repetitions'] = 4
        pending = self.make_plan()
        self.assertEqual((pending['complete'], pending['pending']), (3, 1))
        provider.run(self.app, {}, pending, FakeBackend)
        self.assertEqual(len(FakeBackend.created[-1].calls), 1)
        self.assertEqual({r['repetition'] for r in self.app.store.all()}, {0, 1, 2, 3})

    def test_full_active_suite_keeps_repetitions_but_collapses_unavailable_settings(self):
        from workbench.judgements import load_tests
        tests = load_tests(Path(__file__).resolve().parents[1] / 'test_specs')
        plan = provider.plan(tests, self.app.settings, self.target, self.app.store, self.selection)
        self.assertEqual((plan['requested_cases'], plan['independent_observations'], plan['collapsed_cases']), (357, 312, 45))
        self.assertTrue(all({a['repetition'] for a in g['aliases']} == {g['repetition']} for g in plan['groups']))

    def test_full_suite_160_compatible_baselines_leave_152_fresh_trials(self):
        from workbench.judgements import load_tests
        tests = load_tests(Path(__file__).resolve().parents[1] / 'test_specs')
        original = provider.plan(tests, self.app.settings, self.target, self.app.store, self.selection)
        policy = copy.deepcopy(original['provider'])
        policy.update(policy=provider.LEGACY_POLICY, adapter_hash=provider.LEGACY_ADAPTER_HASH)
        preserved = {}
        for group in original['groups']:
            if group['repetition'] != 0:
                continue
            cid = digest({'provider': policy, 'effective': group['effective']})
            record = {'status': 'completed', 'model_id': provider.MODEL_ID, 'case_id': cid,
                      'repetition': 0, 'capability_policy': policy,
                      'test_definition': group['test'], 'variant_definition': group['variant'],
                      'effective_definition': group['effective'], 'score': {'exact_match': False}}
            path = self.app.store.save(record)
            preserved[path] = path.read_bytes()
        self.assertEqual(len(preserved), 160)
        revised = provider.plan(tests, self.app.settings, self.target, self.app.store, self.selection)
        self.assertEqual((revised['complete'], revised['pending']), (160, 152))
        self.assertTrue(all(g['repetition'] > 0 for g in revised['groups'] if not g['done']))
        self.assertTrue(all(path.read_bytes() == raw for path, raw in preserved.items()))

    def test_conditions_assignments_and_bounded_loops_keep_required_calls(self):
        variant=self.test['variants'][0]
        variant['steps'][0]['assign']='ready'
        variant['steps'].extend([
            {'id':'skip','type':'generate','prompt':'Must be skipped','when':{'step':'ready','equals':'WRONG'}},
            {'id':'repeat','type':'loop','max_iterations':2,'until':{'step':'later','equals':'STOP'},
             'steps':[{'id':'later','type':'generate','prompt':'Use previous output','uses':['ready'],'output':{'type':'text'}}]}])
        pending=self.make_plan();provider.run(self.app,{},pending,FakeBackend)
        record=self.app.store.all()[0]
        self.assertEqual(len(record['calls']),3)
        self.assertEqual(record['outputs']['ready'],'READY')
        self.assertEqual(record['step_events'][-1],{'step':'repeat','status':'loop_finished','iterations':2})
        self.assertTrue(any(e['step']=='skip' and e['status']=='skipped' for e in record['step_events']))

    def test_stop_after_model_finishes_single_provider_and_report_counts_aliases(self):
        other=copy.deepcopy(self.test);other['id']='second'
        other['variants'][0]['steps'][0]['prompt']='A genuinely different prompt'
        self.app.stop_after_model=True
        provider.run(self.app, {}, self.make_plan([self.test,other]), FakeBackend)
        self.assertEqual(len(self.app.store.all()),6)
        from reporting.report import build_report
        counts=build_report(self.app.store.all(),[self.test,other])['remote_statistics']
        self.assertEqual(counts['independent_observations'],6)
        self.assertEqual(counts['mapped_requested_cases'],6)
        self.assertEqual(counts['collapsed_cases'],0)
