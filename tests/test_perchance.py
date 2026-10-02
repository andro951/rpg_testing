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
from workbench.domain import ResultStore, code_fingerprint, read_json, write_json
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

    def test_collapse_cache_sampling_and_repetitions_and_subset_identity(self):
        alternate = copy.deepcopy(self.test['variants'][0])
        alternate.update(id='b', cache='off')
        alternate['steps'][0]['sampling'].update(temperature=1, top_p=.5, seed=100)
        self.test['variants'].append(alternate)
        full = self.make_plan()
        self.assertEqual((full['requested_cases'], full['independent_observations'], full['collapsed_cases']), (6, 1, 5))
        subset = self.make_plan(selection={**self.selection, 'test_id': self.test['id'], 'variant_id': 'b'})
        self.assertEqual(subset['groups'][0]['case_id'], full['groups'][0]['case_id'])
        self.assertEqual(subset['groups'][0]['variant']['id'], 'a')
        self.assertEqual(len(full['groups'][0]['aliases']), 6)

    def test_distinct_prompts_states_outputs_oracles_timeouts_and_workflows(self):
        for field in ('prompt', 'state', 'schema', 'oracle', 'timeout', 'workflow', 'representation'):
            other = copy.deepcopy(self.test); other['id'] = 'other'
            if field == 'prompt':other['variants'][0]['steps'][0]['prompt'] += ' Different.'
            elif field == 'state':other['source']['initial_state'] = {'n': 1}
            elif field == 'schema':other['variants'][0]['steps'][0]['output'] = {'type': 'boolean'}
            elif field == 'oracle':other['variants'][0]['expected_answers']['answer'] = 'OTHER'
            elif field == 'timeout':other['timeout_seconds'] = 20
            elif field == 'representation':other['variants'][0]['state_presentation'] = 'raw_json'
            else:
                other['variants'][0]['steps'].append({'id':'second','type':'generate','prompt':'Another step','output':{'type':'text'},'uses':['answer']})
            with self.subTest(field=field):self.assertEqual(self.make_plan([self.test, other])['independent_observations'], 2)

    def test_remote_preflight_bypasses_native_and_larger_tiers(self):
        for tier in (8, 11, 12, 16):
            with patch('workbench.inventory.detect_gpus', return_value=[{'name':'GPU','total_gib':tier}]), patch.object(provider.BrowserBackend, 'open') as opened:
                report, plan = self.app.build_preflight(selection=self.selection)
            self.assertEqual(report['ready'], tier == 8)
            self.assertEqual(plan['pending'], 1)
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

    def test_run_once_resume_mapping_export_and_no_original_changes(self):
        pending = self.make_plan()
        before = (self.root/'test_specs/fixture.json').read_bytes()
        provider.run(self.app, {'gpu':{}}, pending, FakeBackend)
        self.assertEqual(len(FakeBackend.created[0].calls), 1)
        self.assertTrue(FakeBackend.created[0].closed)
        self.assertEqual(len(self.app.store.all()), 1)
        record = self.app.store.all()[0]
        self.assertEqual(len(record['aliases']), 3)
        self.assertIsNone(record['calls'][0]['applied_sampling'])
        self.assertEqual(record['execution_class'], 'remote_service')
        self.assertFalse(record['feature_applicability']['cache_control'])
        provider.run(self.app, {}, self.make_plan(), FakeBackend)
        self.assertEqual(len(FakeBackend.created), 1)
        self.assertEqual(before, (self.root/'test_specs/fixture.json').read_bytes())
        archive = zipfile.ZipFile(io.BytesIO(self.app.export()))
        self.assertTrue(any(n.startswith('perchance-plans/') for n in archive.namelist()))
        summary = json.loads(archive.read('summary.json'))
        self.assertEqual(summary['perchance']['independent_observations'], 1)
        self.assertEqual(summary['perchance']['mapped_requested_cases'], 3)

    def test_wrong_answers_and_timeouts_are_terminal_and_partials_preserved(self):
        for failure in (None, provider.PerchanceTimeout):
            other = copy.deepcopy(self.test); other['timeout_seconds'] += int(failure is not None)
            FakeBackend.response = 'WRONG'; FakeBackend.failure = failure
            pending = self.make_plan([other]); provider.run(self.app, {}, pending, FakeBackend)
            record = self.app.store.read(self.app.store.path(provider.MODEL_ID, pending['groups'][0]['case_id']))
            self.assertFalse(record['score']['exact_match'])
            self.assertEqual(self.make_plan([other])['pending'], 0)
            if failure:self.assertEqual(record['calls'][0]['text'], 'PARTIAL')

    def test_cancellation_and_infrastructure_attempts(self):
        FakeBackend.failure = provider.Cancelled
        with self.assertRaises(provider.Cancelled):provider.run(self.app, {}, self.make_plan(), FakeBackend)
        self.assertEqual(self.app.store.all()[0]['status'], 'aborted')
        self.assertTrue(FakeBackend.created[0].closed)
        FakeBackend.failure = RuntimeError
        provider.run(self.app, {}, self.make_plan(), FakeBackend)
        self.assertEqual(len(self.app.store.all()[0]['attempts']), 1)
        FakeBackend.failure = None
        provider.run(self.app, {}, self.make_plan(), FakeBackend)
        self.assertEqual(len(self.app.store.all()[0]['attempts']), 2)

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
        self.assertEqual(len(FakeBackend.created[-1].calls), 2)
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
        self.assertEqual(self.make_plan([self.test,other])['independent_observations'],1)

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

    def test_native_inference_fingerprint_unchanged(self):
        self.assertEqual(code_fingerprint(), 'de9b98611a020972925a3a7f1a1cbb962e39bffbcaceb78d229610d4a2436d6d')

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
        self.assertEqual(len(self.app.store.all()),2)
        from reporting.report import build_report
        counts=build_report(self.app.store.all(),[self.test,other])['remote_statistics']
        self.assertEqual(counts['independent_observations'],2)
        self.assertEqual(counts['mapped_requested_cases'],6)
        self.assertEqual(counts['collapsed_cases'],4)