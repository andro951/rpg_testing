"""Deterministic simulated inference only; no model or network requests."""
import copy
import tempfile
import subprocess
import types
import json
import shutil
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from workbench import domain, perchance
from workbench.workflows import execute, Cancelled, messages
from workbench.self_review import decision, REVIEW_QUESTION, REPLACEMENT_REQUEST
from workbench.planning import pending_plan

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_CODE = '29672ea8a2058fbd0e80a560233816c6f552861a12985d4e6a5a02208be19080'
PREVIOUS_ADAPTER = 'f2b784b8d2686d7a47c737bb384138d1d26972c6a52a01f7c71dee9082008055'


def fixture(enabled=True):
    return {'schema_version': 2, 'id': 'retry_fixture', 'workflow': 'steps', 'timeout_seconds': 120,
            'source': {'initial_state': {}, 'new_information': 'Return READY.'},
            'instructions': 'Follow the user request.', 'expected_state': {'secret_oracle': True},
            'variants': [{'id': 'answer', 'prompt_style': 'direct_text_v1', 'retry_enabled': enabled,
                          'steps': [{'id': 'answer', 'type': 'generate', 'prompt': 'Return READY.'}],
                          'result': {'step': 'answer', 'representation': 'answers'},
                          'expected_answers': {'answer': 'READY'}}]}


class Scripted:
    supports_cache = supports_schema = True
    def __init__(self, script, remote=False, after=None):
        self.script = iter(script); self.remote = remote; self.requests = []; self.after = after
    def generate(self, prompt, settings, schema, *args):
        self.requests.append(copy.deepcopy((prompt, settings, schema)))
        value = next(self.script)
        if isinstance(value, Exception):
            raise value
        if self.after:
            self.after(len(self.requests))
        return {'text': value, 'finish_reason': 'provider_completed' if self.remote else 'stop',
                'request_seconds': .125, 'usage': {'completion_tokens': len(value)},
                'raw_chunks': [{'text': value}], 'cached_tokens': 0}


class SelfReviewTests(unittest.TestCase):
    def run_script(self, script, enabled=True, remote=False, cancel=None, after=None):
        test = fixture(enabled); variant = test['variants'][0]
        backend = Scripted(script, remote, after)
        if remote:
            result = perchance.execute_job({'test': test, 'variant': variant}, backend, cancel or threading.Event())
        else:
            result = execute(test, variant, backend, cancel)
        return result, backend

    def test_disabled_and_omitted_are_single_answer(self):
        result, backend = self.run_script(['READY'], False)
        self.assertEqual(len(backend.requests), 1)
        self.assertTrue(result['score']['exact_match'])
        self.assertNotIn('call_kind', result['calls'][0])
        test = fixture(); del test['variants'][0]['retry_enabled']
        self.assertEqual(len(execute(test, test['variants'][0], Scripted(['READY']))['calls']), 1)

    def test_immediate_yes_reviews_original_context_without_oracle(self):
        result, backend = self.run_script(['READY', 'Yes.'])
        self.assertEqual(len(result['calls']), 2)
        original = messages(fixture(), fixture()['variants'][0]['steps'][0], {}, fixture()['variants'][0])
        self.assertEqual(backend.requests[1][0], original + [
            {'role': 'assistant', 'content': 'READY'}, {'role': 'user', 'content': REVIEW_QUESTION}])
        self.assertNotIn('secret_oracle', str(backend.requests))
        self.assertTrue(result['score']['exact_match'])
        self.assertEqual(result['step_events'][0]['outcome'], 'accepted')

    def test_no_then_yes_preserves_all_requests_and_final_answer(self):
        result, backend = self.run_script(['WRONG', 'no', 'READY', 'yes'])
        self.assertEqual([c['text'] for c in result['calls']], ['WRONG', 'no', 'READY', 'yes'])
        self.assertEqual(result['outputs']['answer'], 'READY')
        self.assertTrue(result['score']['exact_match'])
        self.assertEqual([c['call_kind'] for c in result['calls']],
                         ['initial_answer', 'self_review', 'replacement_answer', 'self_review'])
        self.assertEqual(backend.requests[2][0][-1]['content'], REPLACEMENT_REQUEST)
        self.assertEqual(backend.requests[2][0][-2]['content'], 'no')
        self.assertEqual([c['answer_attempt'] for c in result['calls']], [0, 0, 1, 1])
        for call in result['calls']:
            self.assertEqual(call['request_seconds'], .125)
            self.assertIn('usage', call); self.assertIn('raw_chunks', call)
            self.assertGreaterEqual(call['workflow_request_seconds'], 0)

    def test_three_replacements_and_final_review_are_hard_bound(self):
        result, backend = self.run_script(['a', 'no', 'b', 'no', 'c', 'no', 'READY', 'no'])
        self.assertEqual(len(backend.requests), 8)
        event = result['step_events'][-2]
        self.assertEqual((event['outcome'], event['retries_used']), ('retry_budget_exhausted', 3))
        # Self-criticism is not an oracle verdict.
        self.assertTrue(result['score']['exact_match'])

    def test_third_replacement_can_be_accepted(self):
        result, _ = self.run_script(['a', 'no', 'b', 'no', 'c', 'no', 'READY', 'yes'])
        self.assertEqual(result['step_events'][-2]['outcome'], 'accepted')

    def test_ambiguous_stops_unendorsed_and_is_not_a_yes(self):
        for reply in ('maybe', '', 'yes, but no', 'Yes because it is correct', 'no yes', '```yes```'):
            with self.subTest(reply=reply):
                result, backend = self.run_script(['READY', reply])
                self.assertEqual(len(backend.requests), 2)
                self.assertEqual(result['calls'][-1]['review_decision'], 'ambiguous')
                self.assertEqual(result['step_events'][-2]['outcome'], 'ambiguous_review')
                self.assertTrue(result['score']['exact_match'])
        self.assertEqual(decision(' NO! \n'), 'no')

    def test_yes_does_not_turn_wrong_answer_into_pass(self):
        result, _ = self.run_script(['WRONG', 'yes'])
        self.assertFalse(result['score']['exact_match'])
        self.assertEqual(result['step_events'][-2]['outcome'], 'accepted')

    def test_stop_before_review_retains_original_answer(self):
        cancel = threading.Event()
        with self.assertRaises(Cancelled) as raised:
            self.run_script(['READY'], cancel=cancel, after=lambda n: cancel.set())
        self.assertEqual([c['text'] for c in raised.exception.partial['calls']], ['READY'])

    def test_review_error_and_partial_stream_are_preserved(self):
        for failure in (Cancelled('Stopped'), RuntimeError('transport failed')):
            failure.partial_response = {'text': 'par', 'raw_chunks': [{'text': 'par'}], 'usage': {}}
            with self.subTest(error=type(failure).__name__), self.assertRaises(type(failure)) as raised:
                self.run_script(['READY', failure])
            calls = raised.exception.partial['calls']
            self.assertEqual([c['text'] for c in calls], ['READY', 'par'])
            self.assertEqual(calls[-1]['call_kind'], 'self_review')
            self.assertTrue(calls[-1]['incomplete'])
            self.assertIn('request_error', calls[-1])

    def test_replacement_error_retains_no_and_failed_call(self):
        with self.assertRaises(RuntimeError) as raised:
            self.run_script(['WRONG', 'no', RuntimeError('failed')])
        calls = raised.exception.partial['calls']
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[1]['review_decision'], 'no')
        self.assertEqual(calls[2]['call_kind'], 'replacement_answer')

    def test_review_is_unconstrained_even_for_constrained_answers(self):
        test = fixture(); variant = test['variants'][0]
        variant['steps'][0]['output'] = {'type': 'string'}
        backend = Scripted(['"WRONG"', 'no', '"READY"', 'yes'])
        result = execute(test, variant, backend)
        self.assertEqual([r[2] for r in backend.requests], [{'type': 'string'}, None, {'type': 'string'}, None])
        self.assertEqual(result['outputs']['answer'], 'READY')

    def test_perchance_uses_same_bounded_workflow_and_unknown_controls(self):
        for script, count in ((['READY'], 1), (['READY','yes'], 2),
                              (['WRONG','no','READY','yes'], 4),
                              (['a','no','b','no','c','no','READY','no'], 8), (['READY','maybe'], 2)):
            with self.subTest(script=script):
                result, backend = self.run_script(script, enabled=count != 1, remote=True)
                self.assertEqual(len(backend.requests), count)
                self.assertTrue(result['score']['exact_match'])
                self.assertIsNone(result['cache_verified'])
                self.assertIsNone(result['gpu_memory'])
                self.assertFalse(result['feature_applicability']['seed_control'])

    def test_perchance_error_and_stop_keep_evidence(self):
        for failure in (Cancelled('stop'), perchance.PerchanceTimeout('deadline'), RuntimeError('failed')):
            failure.partial_response = {'text': 'partial'}
            with self.subTest(error=type(failure).__name__), self.assertRaises(type(failure)) as raised:
                self.run_script(['READY', failure], remote=True)
            self.assertEqual([c['text'] for c in raised.exception.partial['calls']], ['READY','partial'])

    def test_final_metrics_remain_independent(self):
        from tests.helpers.frozen_templates import compile_test
        from prompt_builder.reference_output import encode
        test = compile_test('no_change', 'json_slash', input_formats=['normal_json'])
        variant = test['variants'][0]; variant['retry_enabled'] = True
        good = encode(test['source']['initial_state'], variant['expected_patch'], 'json_slash', test['source']['array_identities'])
        result = execute(test, variant, Scripted(['WRONG', 'no', good, 'yes']))
        self.assertTrue(result['score']['exact_match'])
        self.assertTrue(result['score']['format_compliance']['compliant'])

    def test_setting_requires_actual_boolean(self):
        for value in (1, 0, 'true', None, {}):
            test = fixture(value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                domain.validate_test(test)

    def test_disabled_flag_is_identity_neutral_but_context_policy_is_new(self):
        test = fixture(False); variant = test['variants'][0]
        missing = copy.deepcopy(variant); del missing['retry_enabled']
        self.assertEqual(domain.experiment_spec(test, variant), domain.experiment_spec(test, missing))
        self.assertEqual(perchance.effective(test, variant), perchance.effective(test, missing))
        # Context allocation/overflow semantics changed intentionally; do not
        # whitelist the new implementation as the frozen old experiment.
        self.assertNotEqual(domain.code_fingerprint(), PREVIOUS_CODE)
        self.assertEqual(perchance.identity({})['adapter_hash'], PREVIOUS_ADAPTER)
        with patch.object(domain, 'implementation_fingerprint', return_value='f'*64):
            self.assertEqual(domain.code_fingerprint(), 'f'*64)

    def test_workflow_changes_case_identity_and_never_collapses_at_provider(self):
        test = fixture(False); variant = test['variants'][0]
        model = {'id': 'fake', 'files': ['fake.gguf'], 'required_vram_gb': 8}
        enabled = {**variant, 'retry_enabled': True}
        self.assertNotEqual(domain.case_id(model,test,variant,0,{'vram_gb':8}),
                            domain.case_id(model,test,enabled,0,{'vram_gb':8}))
        self.assertNotEqual(perchance.effective(test, variant), perchance.effective(test, enabled))

    def test_mock_save_and_resume_twice_preserves_raw_results(self):
        test = fixture(False); model = {'id':'fake', 'files':['fake.gguf'], 'required_vram_gb':8}; target={'vram_gb':8}
        # Same variant ID with changed workflow must not reuse historical completion.
        with tempfile.TemporaryDirectory() as folder:
            store = domain.ResultStore(Path(folder)); variant = test['variants'][0]
            cid = domain.case_id(model,test,variant,0,target)
            store.save({'status':'completed','case_id':cid,'model_id':model['id'],
                        'provenance':{'workflow_code':domain.code_fingerprint()},
                        **execute(test,variant,Scripted(['READY']))})
            original = store.path(model['id'],cid).read_bytes()
            self.assertEqual(pending_plan([model],[test],target,store)['pending'],0)
            variant['retry_enabled'] = True
            plan = pending_plan([model],[test],target,store)
            self.assertEqual(plan['pending'],1)
            cid2 = plan['groups'][0]['jobs'][0]['case_id']
            store.save({'status':'completed','case_id':cid2,'model_id':model['id'],
                        'provenance':{'workflow_code':domain.code_fingerprint()},
                        **execute(test,variant,Scripted(['WRONG','no','READY','yes']))})
            for _ in range(2):
                self.assertEqual(pending_plan([model],[test],target,store)['pending'],0)
            self.assertEqual(store.path(model['id'],cid).read_bytes(),original)
            self.assertEqual(len(store.all()),2)

    def test_disabled_matches_prechange_runner_for_all_372_current_prompts(self):
        from prompt_builder.reference_output import encode
        previous = types.ModuleType('workbench._pre_retry_workflows')
        previous.__package__ = 'workbench'
        source = (ROOT/'tests/fixtures/self_review_disabled_workflows.txt').read_text(encoding='utf-8')
        exec(compile(source, '<frozen pre-retry runner>', 'exec'), previous.__dict__)
        count = 0
        # Preserve the original 21-case/372-prompt regression population.
        # Compile frozen inputs under the current evaluator rather than regrade
        # archived evidence or silently expand this historical parity check.
        from tests.helpers.frozen_templates import build
        with tempfile.TemporaryDirectory() as temp:
            build(Path(temp))
            frozen_tests = domain.load_tests(Path(temp)/'test_specs')
        for test in frozen_tests:
            for variant in test['variants']:
                raw = encode(test['source']['initial_state'], variant['expected_patch'],
                             variant['result']['output_format'], test['source']['array_identities'])
                before = previous.execute(test,variant,Scripted([raw]))
                after = execute(test,variant,Scripted([raw]))
                for result in (before,after):
                    result.pop('pipeline_seconds'); result.pop('scoring_seconds')
                self.assertEqual(before, after, (test['id'], variant['id']))
                explicit = {**variant,'retry_enabled':False}
                self.assertEqual(domain.experiment_spec(test,variant),domain.experiment_spec(test,explicit))
                count += 1
        self.assertEqual(count,372)

    def test_v3_evaluator_pin_stays_exact_with_raw_sources_visible(self):
        from evaluation.array_identities_intent import configuration, identity_info
        self.assertEqual(configuration()['fingerprint'],
                         '7f8348680b973038b3d29323fbbca442d553138e11086c05b9f124cd9cfd573e')
        self.assertNotEqual(identity_info()['implementation_fingerprint'], configuration()['fingerprint'])
        self.assertIn('workbench/workflows.py', identity_info()['source_hashes'])

    def test_intent_pass_and_strict_format_failure_stay_independent_after_review(self):
        from tests.helpers.frozen_templates import compile_test
        test = compile_test('no_change','json_slash',input_formats=['normal_json'])
        variant = test['variants'][0]; variant['retry_enabled'] = True
        result = execute(test,variant,Scripted(['```json\n[]\n```','yes']))
        self.assertTrue(result['score']['exact_match'])
        self.assertFalse(result['score']['format_compliance']['compliant'])

    def test_retries_add_control_text_without_multiplying_context(self):
        from workbench.inventory import automatic_context
        test=fixture(False)
        disabled=automatic_context([test],{'model.context_length':262144})
        test['variants'][0]['retry_enabled']=True
        enabled=automatic_context([test],{'model.context_length':262144})
        self.assertEqual(enabled['allocated_tokens'],disabled['allocated_tokens'])
        self.assertGreater(enabled['review_control_estimate_bytes'],0)
        self.assertEqual(disabled['review_control_estimate_bytes'],0)
        self.assertEqual(enabled['input_estimate_bytes'],disabled['input_estimate_bytes'])
        self.assertLessEqual(enabled['allocated_tokens'],262144)
        self.assertIsNone(enabled['output_cap'])

    @unittest.skipUnless(shutil.which('node'), 'Node unavailable')
    def test_ui_prepares_idempotent_pairs_without_saving_or_mutating_original(self):
        script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(process.argv[1],'utf8');
const snippet=source.slice(source.indexOf("on('add-retry-pairs',"),source.indexOf("on('save-test',"));
let callback; const input={value:JSON.stringify({variants:[{id:'normal_json',steps:[{id:'patch'}],prompt_bindings:{a:1}}]})};
vm.runInNewContext(snippet,{on:(id,fn)=>callback=fn,$:id=>input,structuredClone,toast:()=>{}});
callback(); callback(); const result=JSON.parse(input.value);
assert.equal(result.variants.length,2); assert.equal(result.variants[0].retry_enabled,undefined);
assert.equal(result.variants[1].retry_enabled,true); assert.equal(result.variants[1].id,'normal_json__retry');
assert.deepEqual(result.variants[0].steps,result.variants[1].steps);
assert.deepEqual(result.variants[0].prompt_bindings,result.variants[1].prompt_bindings);
"""
        subprocess.run(['node','-e',script,str(ROOT/'workbench/web/app.js')],check=True,capture_output=True,text=True)


if __name__ == '__main__':
    unittest.main()
