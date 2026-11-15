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
        self.assertEqual(result['calls'][0]['text'],self.correct)
        self.assertEqual(result['calls'][0]['call_kind'],'initial_answer')
    def test_correction_uses_original_and_latest_raw_answer(self):
        result, backend = self.run_answers(['[]','no',self.correct,'yes'])
        self.assertTrue(result['score']['exact_match'])
        self.assertEqual(len(result['calls']),4)
        original = backend.requests[0]
        for request in backend.requests[1:]: self.assertEqual(request[:len(original)],original)
        self.assertEqual(backend.requests[-1][-2]['content'],self.correct)
        self.assertEqual(backend.requests[2][-2]['content'],'no')
        self.assertEqual(backend.requests[2][len(original)]['content'],'[]')
        self.assertEqual(backend.requests[-1][-3]['content'],
                         'You judged your previous answer wrong. Provide a new answer to the original request, following its requested output format.')
    def test_three_revisions_eight_calls_maximum(self):
        result, backend = self.run_answers(['[]','no','[]','no','[]','no',self.correct,'no'])
        self.assertEqual(len(backend.requests),8)
        self.assertTrue(result['score']['exact_match'])
        reviews=[e for e in result['step_events'] if e['status']=='self_review']
        self.assertEqual(reviews[-1]['outcome'],'retry_budget_exhausted')
        self.assertEqual(reviews[-1]['retries_used'],3)
    def test_ambiguous_check_preserved_and_stops_unendorsed(self):
        result, backend = self.run_answers([self.correct,'Probably yes'])
        self.assertTrue(result['score']['exact_match'])
        self.assertEqual(result['calls'][-1]['review_decision'],'ambiguous')
        self.assertEqual(result['calls'][-1]['text'],'Probably yes')
        reviews=[e for e in result['step_events'] if e['status']=='self_review']
        self.assertEqual(reviews[-1]['outcome'],'ambiguous_review')
        self.assertEqual(len(result['calls']),2)
    def test_existing_retry_protocol_is_only_runtime_switch(self):
        self.assertEqual(len(self.test['variants']),6)
        self.assertEqual(sum(v.get('retry_enabled',False) for v in self.test['variants']),3)
        self.assertFalse(any('self_check' in v for v in self.test['variants']))
        bad = copy.deepcopy(self.test)
        bad['variants'][1]['retry_enabled'] = 'on'
        with self.assertRaisesRegex(ValueError,'retry_enabled must be boolean'): validate_test(bad)
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
        self.assertEqual(caught.exception.partial['calls'][0]['text'],self.correct)
        self.assertEqual(caught.exception.partial['calls'][0]['call_kind'],'initial_answer')
        self.assertEqual(len(caught.exception.partial['calls']),1)
    def test_final_answer_retains_independent_format_metric(self):
        result, _ = self.run_answers([self.correct,'yes'])
        self.assertIn('format_compliance',result['score'])
        self.assertTrue(result['score']['exact_match'])
    @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
    def test_ui_does_not_duplicate_explicit_six_variant_matrix(self):
        import subprocess
        source = Path(__file__).resolve().parents[1]/'workbench/web/app.js'
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8');
const snippet=source.slice(source.indexOf("on('add-retry-pairs',"),source.indexOf("on('save-test',"));
let callback;const input={value:process.argv[2]};
vm.runInNewContext(snippet,{on:(id,fn)=>callback=fn,$:id=>input,structuredClone,toast:()=>{}});
callback();callback();const result=JSON.parse(input.value);
assert.equal(result.variants.length,6);
assert.equal(result.variants.filter(v=>v.retry_enabled).length,3);
"""
        subprocess.run(['node','-e',script,str(source),json.dumps(self.test)],check=True,capture_output=True,text=True)
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
