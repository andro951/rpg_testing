"""Synthetic workflow tests: no network, model, or benchmark observations."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from prompt_builder.builder import compile_test, load_case, build, validate_artifacts
from prompt_builder.coverage import validate_manifest
from workbench.domain import experiment_spec, validate_test
from workbench.workflows import execute, Cancelled
from tests.helpers.template_responses import encode_response

ROOT = Path(__file__).resolve().parents[1] / 'archives/suite-before-240-2026-11-15/prompt_builder/templates'

class Backend:
    supports_schema = False
    supports_cache = False
    def __init__(self, answers): self.answers = iter(answers); self.requests = []
    def generate(self, messages, settings, schema, cache, cancel):
        self.requests.append(copy.deepcopy(messages))
        return {'text':next(self.answers), 'finish_reason':'stop'}

class SelfCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'templates'
        shutil.copytree(ROOT, self.root)
        for name in ('selection', 'coverage'):
            path = self.root / 'common' / (name+'.json')
            data = json.loads(path.read_text()); data['self_check_modes'] = ['off','on']
            path.write_text(json.dumps(data))
        self.case = load_case('update_record_field', self.root)
        self.test = compile_test(self.case, 'json_dot', root=self.root)
        self.off, self.on = self.test['variants'][:2]
        self.correct = encode_response(self.case, 'json_dot')
    def run_answers(self, answers, on=True):
        backend = Backend(answers)
        result = execute(self.test, self.on if on else self.off, backend)
        return result, backend
    def test_identity_and_baseline(self):
        self.assertNotEqual(experiment_spec(self.test,self.off), experiment_spec(self.test,self.on))
        self.assertEqual(self.on['id'], self.off['id']+'__self_check')
        self.assertEqual(self.off['steps'],self.on['steps'])
        result, backend = self.run_answers([self.correct], on=False)
        self.assertEqual(len(backend.requests),1)
        self.assertTrue(result['score']['exact_match'])
    def test_yes_does_not_use_oracle_to_retry_wrong_answer(self):
        result, backend = self.run_answers(['[]','yes'])
        self.assertEqual(len(backend.requests),2)
        self.assertFalse(result['score']['exact_match'])
        self.assertEqual(result['outputs']['patch'],'[]')
    def test_no_revises_correct_answer_even_if_oracle_would_pass(self):
        result, backend = self.run_answers([self.correct,'no','[]','yes'])
        self.assertEqual(len(backend.requests),4)
        self.assertFalse(result['score']['exact_match'])
        self.assertEqual(result['outputs']['self_check_initial_answer'],self.correct)
    def test_correction_uses_original_and_latest_raw_answer(self):
        result, backend = self.run_answers(['[]','no',self.correct,'yes'])
        self.assertTrue(result['score']['exact_match'])
        self.assertEqual(len(result['calls']),4)
        original = backend.requests[0]
        for request in backend.requests[1:]: self.assertEqual(request[:-2],original)
        self.assertEqual(backend.requests[-1][-2]['content'],self.correct)
        self.assertEqual(backend.requests[2][-2]['content'],'[]')
    def test_three_revisions_eight_calls_maximum(self):
        result, backend = self.run_answers(['[]','no','[]','no','[]','no',self.correct,'no'])
        self.assertEqual(len(backend.requests),8)
        self.assertTrue(result['score']['exact_match'])
        self.assertEqual(result['step_events'][-1]['status'],'revision_limit_reached')
    def test_invalid_check_preserved_and_fails_closed(self):
        result, backend = self.run_answers([self.correct,'Probably yes'])
        self.assertFalse(result['score']['valid'])
        self.assertIn('Invalid self-check',result['score']['error'])
        self.assertEqual(result['outputs']['self_check_decision_1'],'Probably yes')
        self.assertEqual(len(result['calls']),2)
    def test_protocol_validation(self):
        bad = copy.deepcopy(self.test)
        bad['variants'][1]['self_check']['max_revisions'] = 4
        with self.assertRaisesRegex(ValueError,'Unsupported self-check'): validate_test(bad)
    def test_perchance_uses_same_protocol_without_faking_finish_reason(self):
        import threading
        from workbench.perchance import execute_job, effective
        class Provider:
            def __init__(self): self.answers = iter(['[]','no',self_correct,'yes'])
            def generate(self, messages, settings, schema, cancel):
                return {'text':next(self.answers),'finish_reason':'provider_completed',
                        'requested_sampling':dict(settings),'applied_sampling':None}
        self_correct = self.correct
        result = execute_job({'test':self.test,'variant':self.on,'repetition':0},Provider(),threading.Event())
        self.assertTrue(result['score']['exact_match'])
        self.assertEqual(len(result['calls']),4)
        self.assertTrue(all(c['finish_reason']=='provider_completed' for c in result['calls']))
        self.assertNotEqual(effective(self.test,self.off),effective(self.test,self.on))
    def test_cancel_preserves_initial_answer(self):
        import threading
        event = threading.Event()
        class CancellingBackend(Backend):
            def generate(inner,*args):
                result = super(CancellingBackend,inner).generate(*args)
                event.set()
                return result
        with self.assertRaises(Cancelled) as caught:
            execute(self.test,self.on,CancellingBackend([self.correct]),cancel=event)
        self.assertEqual(caught.exception.partial['outputs']['patch'],self.correct)
        self.assertEqual(len(caught.exception.partial['calls']),1)
    def test_final_answer_retains_independent_format_metric(self):
        result, _ = self.run_answers([self.correct,'yes'])
        self.assertIn('format_compliance',result['score'])
        self.assertTrue(result['score']['exact_match'])
    def test_complete_manifest_carries_both_conditions(self):
        dest = Path(self.temp.name)/'build'
        manifest = build(dest, root=self.root)
        self.assertEqual(manifest['observations_per_model'],744)
        self.assertEqual({r['self_check'] for r in manifest['prompts']},{'off','on'})
        validate_manifest(manifest,self.root)
        validate_artifacts(dest,manifest)
        manifest['prompts'][1]['self_check']='off'
        with self.assertRaises(ValueError): validate_manifest(manifest,self.root)

if __name__ == '__main__': unittest.main()
