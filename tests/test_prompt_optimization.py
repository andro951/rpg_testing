import copy
import io
import json
import shutil
import tempfile
import threading
import unittest
import zipfile
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from optimization import engine
from optimization.engine import Engine, create, score, top_three, fit_packet, settings
from optimization.runtime import CandidateBackend, GeneratorBackend, discover
from optimization.storage import Store
from optimization.templates import LABELS, bindings, freeze, parse_candidate, projection, render
from workbench.controller import Controller
from workbench.domain import digest
from workbench.workflows import Cancelled, evaluate
from workbench.execution_policy import DoesNotFit, RuntimeStall
from optimization.token_budget import plan as token_plan

ROOT = Path(__file__).resolve().parents[1]


def proposal(name='good'):
    return 'SYSTEM_MESSAGE:\n' + name + '\n${task_requirements}\n${presentation_notes}\nUSER_MESSAGE:\nCurrent State:\n${current_state}\nNew Information:\n${new_information}\nPrior:\n${prior_outputs}'


def native(name='local-a'):
    return {'id': name, 'identity': digest(name), 'provider': 'native', 'name': name,
            'metadata': {'mock.context_length': 65536}}


def valid_move(case):
    before = case['test']['source']['initial_state']['tickets']
    after = case['test']['expected_state']['tickets']
    changed = [i for i in range(len(before)) if before[i] != after[i]]
    for source, target in ((changed[0], changed[-1]), (changed[-1], changed[0])):
        moved = before[:]
        moved.insert(target, moved.pop(source))
        if moved == after:
            return [{'op': 'move', 'from': '/tickets/' + str(source), 'path': '/tickets/' + str(target)}]
    raise AssertionError('Fixture no longer describes a single array move')


class MockGenerator:
    def __init__(self, runtime):
        self.runtime = runtime

    def token_count(self, messages):
        return 1000

    def budget(self, seconds):
        return nullcontext()

    def propose(self, messages, sampling, reserve, cancel):
        self.runtime.requests.append({'messages': messages, 'sampling': sampling, 'reserve': reserve})
        if self.runtime.proposal_error:
            raise self.runtime.proposal_error
        return {'text': self.runtime.proposals.pop(0), 'finish_reason': 'stop', 'raw_chunks': [], 'reasoning_text': ''}


class MockRuntime:
    def __init__(self, app, cohort):
        self.app, self.cohort = app, cohort
        self.backend = SimpleNamespace(timed_out=False)
        self.proposals = [proposal()]
        self.requests = []
        self.trials = []
        self.fail_case = None
        self.proposal_error = None
        self.error = None
        self.after_trial = None
        self.closed = False

    def generator(self, model, config):
        return MockGenerator(self)

    def evaluate(self, model, case, candidate, repetition):
        self.trials.append((model['id'], case['id'], candidate, repetition))
        if self.error:
            raise self.error
        patch_value = valid_move(case)
        if candidate and ('bad' in candidate['system'] or case['id'] == self.fail_case):
            patch_value = []
        outputs = {case['variant']['result']['step']: json.dumps(patch_value)}
        request = render(candidate, bindings(case)) if candidate else [{'role': 'user', 'content': 'Mock original request'}]
        result = {'outputs': outputs, 'calls': [{'step': case['variant']['result']['step'], 'text': outputs[case['variant']['result']['step']],
                                               'finish_reason': 'stop', 'request_messages': request, 'messages': request}],
                  'score': evaluate(case['test'], case['variant'], outputs), 'measurement_valid': True, 'simulated': True}
        if self.after_trial:
            self.after_trial()
        return result

    def close(self):
        self.closed = True


class TokenRuntime:
    def __init__(self, counter, capacity=None, failure=None):
        self.counter, self.capacity, self.failure = counter, capacity, failure
        self.loads = []
        self.backend = None

    def generator(self, model, config):
        context = config['context_tokens']
        self.loads.append(context)
        if self.failure:
            raise self.failure
        if self.capacity and context > self.capacity:
            raise DoesNotFit('Fixture KV allocation does not fit', {'fixture': True})
        self.backend = SimpleNamespace(token_count=self.counter, context=context)
        return self.backend


class OptimizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'test_specs', self.root / 'test_specs')
        shutil.copytree(ROOT / 'docs/prompt-optimization', self.root / 'docs/prompt-optimization')
        shutil.copytree(ROOT / 'optimization/definitions', self.root / 'optimization/definitions')
        self.app = Controller(self.root, demo=True)
        self.cohort = {'models': [native()], 'gpu': {'name': 'Mock GPU', 'total_gib': 8}, 'simulated': True}
        self.session = create(self.app, {'generator_id': 'local-a', 'settings': {'max_attempts': 2}}, self.cohort)
        self.store = Store(self.root)

    def runner(self):
        holder = []
        def factory(app, cohort):
            runtime = MockRuntime(app, cohort)
            holder.append(runtime)
            return runtime
        runner = Engine(self.app, self.session['id'], factory)
        return runner, holder

    def record(self, candidate, model, member, repetition=0, passed=True):
        case = self.session['scope']['cases'][member]
        return {'trial_key': engine.trial_key(self.session, candidate, model, case, repetition), 'candidate': candidate,
                'model_id': model['id'], 'case_id': member, 'status': 'completed', 'pass': passed}

    def test_plain_sections_preserve_text_and_crlf(self):
        parsed = parse_candidate(proposal().replace('\n', '\r\n'))
        self.assertTrue(parsed['user'].startswith('Current State:'))
        self.assertEqual(parse_candidate(proposal())['system'], 'good\n${task_requirements}\n${presentation_notes}')

    def test_labels_are_per_experiment_not_a_global_whitelist(self):
        self.assertEqual(parse_candidate('SYSTEM_MESSAGE:\n\nUSER_MESSAGE:\n${other}', ['other']), {'system': '', 'user': '${other}'})

    def test_unknown_missing_expression_and_repeated_headings_rejected(self):
        for text in (proposal().replace('${prior_outputs}', ''), proposal() + '${unknown}', proposal() + '${a.b}',
                     proposal() + '\nUSER_MESSAGE:\nextra', '```\n' + proposal(), proposal().replace('USER_MESSAGE:', 'User_message:')):
            with self.subTest(text=text[-45:]), self.assertRaises(ValueError):
                parse_candidate(text)

    def test_literal_one_pass_and_repeated_labels_in_either_role(self):
        candidate = parse_candidate(proposal() + '\n${current_state}')
        values = {key: '${new_information}' if key == 'current_state' else key for key in LABELS}
        result = render(candidate, values)
        self.assertEqual(result[1]['content'].count('${new_information}'), 2)

    def test_scope_is_origin_then_entire_task_type(self):
        self.assertEqual([len(layer['members']) for layer in self.session['scope']['layers']], [1, 3])
        for case in self.session['scope']['cases'].values():
            before = copy.deepcopy(case)
            value = bindings(case)
            self.assertEqual(case, before)
            self.assertIn('["move"]', value['task_requirements'])
            self.assertNotIn('expected_state', json.dumps(value))
        paths = next(case for case in self.session['scope']['cases'].values() if case['presentation'] == 'Full paths')
        self.assertIn('$.tickets[0].ticket_id', bindings(paths)['current_state'])

    def test_rejected_origin_blocks_creation(self):
        from workbench.judgements import JudgementStore
        member = self.session['scope']['layers'][0]['members'][0]
        key = self.session['scope']['cases'][member]['definition_id']
        JudgementStore(self.root).update([key], 'rejected', 'bad test', 'unit test')
        with self.assertRaisesRegex(ValueError, 'origin'):
            freeze(self.root)

    def test_aliases_ignore_overridden_prompt_version_but_not_repetition(self):
        case = next(iter(self.session['scope']['cases'].values()))
        clone = copy.deepcopy(case)
        clone['variant']['steps'][-1]['prompt'] = 'Different original wording'
        candidate = parse_candidate(proposal())
        self.assertEqual(projection(case, candidate), projection(clone, candidate))
        self.assertNotEqual(projection(case, None), projection(clone, None))
        model = self.cohort['models'][0]
        self.assertNotEqual(engine.trial_key(self.session, candidate, model, case, 0), engine.trial_key(self.session, candidate, model, case, 1))

    def test_remote_controls_collapse_but_native_controls_are_distinct(self):
        case = next(iter(self.session['scope']['cases'].values()))
        changed = copy.deepcopy(case)
        changed['variant']['sampling'] = {'temperature': 1}
        candidate = parse_candidate(proposal())
        self.assertEqual(projection(case, candidate, True), projection(changed, candidate, True))
        self.assertNotEqual(projection(case, candidate), projection(changed, candidate))
        changed = copy.deepcopy(case)
        changed['variant']['steps'][-1]['sampling'] = {'temperature': 1, 'seed': 999}
        self.assertEqual(projection(case, candidate, True), projection(changed, candidate, True))
        self.assertNotEqual(projection(case, candidate), projection(changed, candidate))

    def test_incomplete_candidates_never_enter_top_three(self):
        candidate = parse_candidate(proposal())
        self.session['attempts'] = [{'number': 1, 'candidate': candidate}]
        member = self.session['scope']['layers'][0]['members'][0]
        record = self.record(candidate, self.cohort['models'][0], member)
        self.assertEqual(top_three(self.session, self.cohort['models'], [record]), [])
        self.assertFalse(score(self.session, candidate, [], [])['complete'])

    def test_ranking_uses_only_current_machine_and_all_repetitions(self):
        candidate = parse_candidate(proposal())
        self.session['attempts'] = [{'number': 1, 'candidate': candidate}]
        local, foreign = native(), native('foreign')
        records = [self.record(candidate, local, member) for member in self.session['scope']['cases']]
        records += [self.record(candidate, foreign, member, passed=False) for member in self.session['scope']['cases']]
        self.assertEqual(top_three(self.session, [local], records)[0]['percentage'], 100)
        self.assertEqual(top_three(self.session, [foreign], records)[0]['percentage'], 0)
        case = next(iter(self.session['scope']['cases'].values()))
        case['test']['repetitions'] = 2
        self.assertFalse(score(self.session, candidate, [local], records)['complete'])

    def test_top_three_unique_with_deterministic_ties_and_pooled_score(self):
        members = list(self.session['scope']['cases'])
        local = native()
        first, second = parse_candidate(proposal('first')), parse_candidate(proposal('second'))
        self.session['attempts'] = [{'number': 1, 'candidate': first}, {'number': 2, 'candidate': first}, {'number': 3, 'candidate': second}]
        records = [self.record(candidate, local, member) for candidate in (first, second) for member in members]
        ranked = top_three(self.session, [local], records)
        self.assertEqual([item['attempt'] for item in ranked], [1, 3])

    def test_storage_checksum_and_archive_roundtrip(self):
        key = self.store.evidence(self.session['id'], {'text': 'literal ${data}', 'kind': 'response'})
        imported = Store(self.root / 'other_machine')
        self.assertEqual(imported.import_archive(self.store.export(self.session['id'])), self.session['id'])
        self.assertEqual(imported.get_evidence(self.session['id'], key)['text'], 'literal ${data}')
        path = self.store.directory(self.session['id']) / 'evidence' / (key + '.json')
        path.write_text('{}')
        with self.assertRaises(ValueError):
            self.store.get_evidence(self.session['id'], key)

    def test_archive_traversal_rejected_without_writes(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            archive.writestr('../escape.json', '{}')
        target = Store(self.root / 'other')
        with self.assertRaises(ValueError):
            target.import_archive(output.getvalue())
        self.assertFalse(target.root.exists())

    def test_context_prunes_input_only_and_protects_top_three(self):
        packet = {'history': [{'number': 1, 'candidate': None}, {'number': 2, 'candidate': {'system': 'a'}, 'layer': 0,
                               'score': {'percentage': 5}}], 'top_three': [{'candidate': {'system': 'winner'}, 'summary': []}], 'pruned_attempts': []}
        original = copy.deepcopy(packet)
        def counter(messages):
            return 30000 if '"number": 1' in messages[1]['content'] else 1000
        limits = {'context_tokens': 32768, 'output_reserve': 4096}
        messages, result = fit_packet(self.session, packet, counter, limits)
        self.assertEqual(result['pruned_attempts'], [1])
        self.assertIn('winner', messages[1]['content'])
        self.assertEqual(packet, original)
        with self.assertRaisesRegex(ValueError, 'Protected'):
            fit_packet(self.session, packet, lambda _: 999999, limits)

    def test_config_validates_finite_ranges_and_generator_reasoning_only(self):
        for config in ({'max_attempts': True}, {'temperature_min': float('nan')}, {'temperature_min': 1, 'temperature_max': .5},
                       {'reasoning': 'yes'}, {'output_reserve': 32768}, {'test_reasoning': True}):
            with self.assertRaises(ValueError):
                settings(config)
        self.assertFalse(settings({})['reasoning'])
        self.assertEqual((settings({})['temperature_min'] + settings({})['temperature_max']) / 2, .7)

    def test_mock_smoke_pass_full_scope_perfect_then_resume_no_reruns(self):
        runner, holder = self.runner()
        runner.run(cohort=self.cohort)
        saved = self.store.load(self.session['id'])
        self.assertEqual(saved['status'], 'perfect')
        self.assertEqual(len(saved['attempts']), 1)
        self.assertEqual(len(holder[0].trials), 6)
        self.assertTrue(holder[0].closed)
        self.assertEqual(top_three(saved, self.cohort['models'], self.store.observations(saved))[0]['percentage'], 100)
        rerun, next_holder = self.runner()
        rerun.run(cohort=self.cohort)
        self.assertEqual(next_holder[0].trials, [])
        self.assertEqual(next_holder[0].requests, [])
        self.assertEqual(self.app.store.all(), [])

    def test_invalid_duplicate_and_failed_proposals_consume_attempts(self):
        def factory(app, cohort):
            runtime = MockRuntime(app, cohort)
            runtime.proposals = ['bad response', proposal('bad')]
            return runtime
        Engine(self.app, self.session['id'], factory).run(cohort=self.cohort)
        saved = self.store.load(self.session['id'])
        self.assertEqual(saved['status'], 'attempt_limit')
        self.assertEqual([a['status'] for a in saved['attempts']], ['invalid', 'origin_failed'])
        first = saved['attempts'][0]
        self.assertIn('bad response', self.store.get_evidence(saved['id'], first['response_evidence'])['text'])
        request = self.store.get_evidence(saved['id'], saved['attempts'][1]['request_evidence'])
        self.assertIn('bad response', request['messages'][1]['content'])
        self.assertTrue(.5 <= request['sampling']['temperature'] <= .9)
        self.assertTrue(0 <= request['sampling']['seed'] < 2**32)

    def test_nonperfect_best_does_not_stop_before_attempt_limit(self):
        def factory(app, cohort):
            runtime = MockRuntime(app, cohort)
            runtime.fail_case = self.session['scope']['layers'][-1]['members'][0]
            runtime.proposals = [proposal(), proposal()]
            return runtime
        Engine(self.app, self.session['id'], factory).run(cohort=self.cohort)
        saved = self.store.load(self.session['id'])
        self.assertEqual(saved['status'], 'attempt_limit')
        self.assertEqual([a['status'] for a in saved['attempts']], ['complete', 'duplicate'])
        self.assertEqual(len(top_three(saved, self.cohort['models'], self.store.observations(saved))), 1)

    def test_infrastructure_error_preserved_and_resume_only_missing(self):
        runner, holder = self.runner()
        def factory(app, cohort):
            runtime = MockRuntime(app, cohort)
            runtime.error = RuntimeError('connection failed')
            return runtime
        with self.assertRaisesRegex(RuntimeError, 'connection failed'):
            Engine(self.app, self.session['id'], factory).run(cohort=self.cohort)
        saved = self.store.load(self.session['id'])
        self.assertEqual(saved['status'], 'blocked')
        self.assertEqual(self.store.observations(saved)[0]['status'], 'error')
        runner = Engine(self.app, self.session['id'], lambda app, cohort: MockRuntime(app, cohort))
        runner.run(cohort=self.cohort)
        self.assertEqual(self.store.load(saved['id'])['status'], 'perfect')

    def test_interrupted_generation_consumes_attempt_and_preserves_partial(self):
        def factory(app, cohort):
            runtime = MockRuntime(app, cohort)
            exc = Cancelled('stopped generating')
            exc.partial_response = {'text': 'SYSTEM_MESSAGE:\npartial'}
            runtime.proposal_error = exc
            return runtime
        with self.assertRaises(Cancelled):
            Engine(self.app, self.session['id'], factory).run(cohort=self.cohort)
        saved = self.store.load(self.session['id'])
        self.assertEqual(saved['status'], 'stopped')
        self.assertEqual(saved['attempts'][0]['status'], 'interrupted')
        error = self.store.get_evidence(saved['id'], saved['attempts'][0]['error_evidence'])
        self.assertIn('partial', error['partial_response']['text'])

    def test_cross_machine_remaining_does_not_generate_and_ranks_new_cohort_only(self):
        runner, holder = self.runner()
        runner.run(cohort=self.cohort)
        other = {'models': [native('local-b')], 'gpu': self.cohort['gpu']}
        rerun, more = self.runner()
        rerun.run('evaluate_remaining', other)
        self.assertEqual(more[0].requests, [])
        self.assertEqual(len(more[0].trials), 6)
        saved = self.store.load(self.session['id'])
        self.assertEqual(len(saved['attempts']), 1)
        self.assertEqual(saved['cohort']['models'][0]['id'], 'local-b')
        self.assertEqual(top_three(saved, other['models'], self.store.observations(saved))[0]['percentage'], 100)

    def test_lost_frozen_model_does_not_silently_qualify(self):
        runner, _ = self.runner()
        with self.assertRaisesRegex(ValueError, 'frozen host model'):
            runner.run(cohort={'models': [native('different')], 'gpu': self.cohort['gpu']})

    def test_candidate_wrapper_replaces_actual_messages_and_keeps_prior_outputs(self):
        case = next(iter(self.session['scope']['cases'].values()))
        seen = []
        class Backend:
            def generate(self, messages, settings, schema, cache, cancel):
                seen.append(messages)
                return {'text': 'answer', 'finish_reason': 'stop'}
        wrapper = CandidateBackend(Backend(), case, parse_candidate(proposal()))
        wrapper.stage = 'analysis'
        wrapper.generate([{'role': 'user', 'content': 'Original analysis'}], {}, None)
        wrapper.stage = case['variant']['result']['step']
        call = wrapper.generate([{'role': 'user', 'content': 'Original final'}], {}, None)
        self.assertEqual(seen[0][0]['content'], 'Original analysis')
        self.assertIn('answer', seen[1][1]['content'])
        self.assertEqual(call['request_messages'], seen[1])
        self.assertEqual(call['benchmark_reasoning'], 'off')

    def test_generator_reasoning_does_not_change_native_benchmark_launch(self):
        model = {'paths': ['fake.gguf']}
        generator = GeneratorBackend({'backend': 'llamacpp'}, {}, lambda *a: None, True)
        generator.owned_id = 'test'
        args = generator.launch_arguments('server', model, {'allocated_tokens': 32768}, '')
        self.assertEqual(args[args.index('--reasoning') + 1], 'on')
        from workbench.native import NativeBackend
        benchmark = NativeBackend({'backend': 'llamacpp'}, {})
        benchmark.owned_id = 'test'
        args = benchmark.launch_arguments('server', model, {'allocated_tokens': 32768}, '')
        self.assertEqual(args[args.index('--reasoning') + 1], 'off')

    def test_origin_gate_uses_selected_model_then_widens_to_all_models(self):
        second = native('local-b')
        cohort = {**self.cohort, 'models': [native(), second]}
        saved = self.store.load(self.session['id'])
        saved['cohort'] = cohort
        self.store.save(saved)
        class MixedRuntime(MockRuntime):
            def evaluate(self, model, case, candidate, repetition):
                outcome = super().evaluate(model, case, candidate, repetition)
                if candidate and model['id'] == 'local-b':
                    outcome['outputs'] = {case['variant']['result']['step']: '[]'}
                    outcome['score'] = evaluate(case['test'], case['variant'], outcome['outputs'])
                return outcome
        def factory(app, cohort):
            runtime = MixedRuntime(app, cohort)
            runtime.proposals = [proposal(), proposal()]
            return runtime
        Engine(self.app, saved['id'], factory).run(cohort=cohort)
        result = self.store.load(saved['id'])
        self.assertEqual(result['attempts'][0]['status'], 'complete')
        ranked = top_three(result, cohort['models'], self.store.observations(result))
        self.assertEqual(ranked[0]['percentage'], 50)
        self.assertEqual(result['status'], 'attempt_limit')

    def test_timeouts_are_terminal_and_resume_never_rerolls_them(self):
        runner, _ = self.runner()
        case = next(iter(self.session['scope']['cases'].values()))
        model = self.cohort['models'][0]
        timeout = self.record(None, model, case['id'], passed=False)
        timeout.update(status='timeout', timed_out=True, timeout_seconds=120)
        key = self.store.evidence(self.session['id'], timeout)
        saved = self.store.load(self.session['id'])
        saved['observations'] = [key]
        self.store.save(saved)
        runner, holder = self.runner()
        runner.run(cohort=self.cohort)
        self.assertEqual(len(holder[0].trials), 5)
        self.assertFalse(any(t[1] == case['id'] and t[2] is None for t in holder[0].trials))
        record = self.store.get_evidence(self.session['id'], key)
        self.assertEqual(record['timeout_seconds'], 120)

    def test_pause_resume_waits_at_trial_boundary(self):
        runner, _ = self.runner()
        self.app.pause_requested = True
        self.app.resume_event.clear()
        worker = threading.Thread(target=runner.boundary)
        worker.start()
        for unused in range(100):
            if self.store.load(self.session['id'])['status'] == 'paused':
                break
            threading.Event().wait(.01)
        self.assertTrue(worker.is_alive())
        self.app.control('resume')
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.store.load(self.session['id'])['status'], 'running')

    def test_timeout_diagnostics_saved_and_native_runtime_recovers_without_retry(self):
        class TimedRuntime(MockRuntime):
            def evaluate(self, model, case, candidate, repetition):
                if not self.trials:
                    self.trials.append((model['id'], case['id'], candidate, repetition))
                    self.backend.timed_out = True
                    exc = RuntimeError('watchdog')
                    exc.partial = {'calls': [], 'outputs': {}}
                    raise exc
                self.backend.timed_out = False
                return super().evaluate(model, case, candidate, repetition)
        holder = []
        def factory(app, cohort):
            runtime = TimedRuntime(app, cohort)
            holder.append(runtime)
            return runtime
        Engine(self.app, self.session['id'], factory).run(cohort=self.cohort)
        saved = self.store.load(self.session['id'])
        self.assertEqual(self.store.observations(saved)[0]['status'], 'timeout')
        self.assertEqual(len(holder[0].trials), 6)
        self.assertEqual(saved['status'], 'perfect')

    def test_host_discovery_filters_unassigned_disabled_and_large_models(self):
        app = self.app
        app.demo = False
        app.settings['model_root'] = str(self.root)
        items = []
        for name, budget, enabled in [('qwen3.5-9B', 8, True), ('qwen3.5-27B', 16, True),
                                      ('qwen3.5-35B', 16, False), ('unassigned', None, True), ('too-large', 48, True)]:
            items.append({'id': name, 'name': name, 'required_vram_gb': budget, 'complete': True,
                          'paths': [], 'errors': [], 'metadata': {}, 'catalog': {'enabled': enabled}})
        with patch('workbench.inventory.detect_gpus', return_value=[{'name': 'Mock GPU', 'total_gib': 16}]), \
             patch('workbench.inventory.scan_models', return_value=items), patch('workbench.inventory.executable', return_value='runtime'), \
             patch.object(app, 'catalog', return_value=[]), patch.object(app, 'identify_artifact', return_value={}), \
             patch.object(app, 'backend_version', return_value='version'):
            options = discover(app)
        self.assertEqual([m['id'] for m in options['models']], ['qwen3.5-9B', 'qwen3.5-27B'])
        self.assertEqual(options['default_generator'], 'qwen3.5-27B')
        self.assertEqual(len(options['excluded']), 3)

    def test_remote_wrapper_records_unverified_controls_and_actual_completion(self):
        case = next(iter(self.session['scope']['cases'].values()))
        class Remote:
            def generate(self, messages, settings, schema, cancel):
                return {'text': '[]', 'finish_reason': 'provider_completed', 'applied_sampling': None,
                        'requested_sampling': settings, 'seed_reproducibility': 'unverified'}
        wrapper = CandidateBackend(Remote(), case, parse_candidate(proposal()), True)
        wrapper.stage = case['variant']['result']['step']
        call = wrapper.generate([], {'seed': 25}, None)
        self.assertEqual(call['provider_finish_reason'], 'provider_completed')
        self.assertEqual(call['finish_reason'], 'stop')
        self.assertIsNone(call['applied_sampling'])
        self.assertEqual(call['requested_sampling']['seed'], 25)
        self.assertEqual(call['benchmark_reasoning'], 'unverified')

    def test_crashed_generation_request_remains_consumed_on_resume(self):
        saved = self.store.load(self.session['id'])
        request = self.store.evidence(saved['id'], {'kind': 'generation_request', 'messages': []})
        saved['attempts'].append({'number': 1, 'status': 'generating', 'request_evidence': request, 'layer': -1})
        self.store.save(saved)
        runner, holder = self.runner()
        runner.run(cohort=self.cohort)
        saved = self.store.load(saved['id'])
        self.assertEqual(saved['attempts'][0]['status'], 'interrupted')
        self.assertEqual(saved['attempts'][1]['number'], 2)
        self.assertEqual(len(holder[0].requests), 1)
        self.assertEqual(saved['status'], 'perfect')

    def test_explicit_generator_settings_change_preserves_coverage_and_attempts(self):
        runner, holder = self.runner()
        runner.run(cohort=self.cohort)
        before = self.store.load(self.session['id'])
        changed = engine.update_settings(self.app, before['id'], {'max_attempts': 30})
        self.assertEqual(changed['observations'], before['observations'])
        self.assertEqual(changed['attempts'], before['attempts'])
        self.assertNotIn('context_tokens', changed['settings'])
        self.assertNotIn('output_reserve', changed['settings'])
        evidence = self.store.get_evidence(changed['id'], changed['configuration_history'][0])
        self.assertEqual(evidence['previous'], before['settings'])
        self.assertEqual(evidence['settings']['max_attempts'], 30)

    def test_declined_perchance_setup_keeps_coverage_pending_then_resume_completes(self):
        remote = {'id': 'perchance-text-generator', 'identity': digest('mock-remote'), 'provider': 'perchance'}
        cohort = {**self.cohort, 'models': [native(), remote]}
        session = create(self.app, {'generator_id': 'local-a', 'settings': {'max_attempts': 2}}, cohort)
        holder = []
        def factory(app, options):
            runtime = MockRuntime(app, options)
            holder.append(runtime)
            return runtime
        def decline(app, **kwargs):
            app.perchance_setup_decision = {'status': 'declined', 'id': 'mock-no'}
        with patch('workbench.perchance_setup.prepare', side_effect=decline) as prepare:
            Engine(self.app, session['id'], factory).run(cohort=cohort)
        prepare.assert_called_once_with(self.app, selection={'model_id': remote['id']}, force_pending=True)
        saved = self.store.load(session['id'])
        self.assertEqual(saved['status'], 'pending')
        self.assertEqual(top_three(saved, cohort['models'], self.store.observations(saved)), [])
        self.assertTrue(all(trial[0] != remote['id'] for trial in holder[0].trials))
        def ready(app, **kwargs):
            app.perchance_setup_decision = {'status': 'ready', 'id': 'mock-ready'}
        with patch('workbench.perchance_setup.prepare', side_effect=ready) as prepare:
            Engine(self.app, session['id'], factory).run(cohort=cohort)
        self.assertEqual(len(holder[1].requests), 0)
        self.assertTrue(all(trial[0] == remote['id'] for trial in holder[1].trials))
        self.assertEqual(self.store.load(session['id'])['status'], 'perfect')
        with patch('workbench.perchance_setup.prepare') as prepare:
            Engine(self.app, session['id'], factory).run(cohort=cohort)
        prepare.assert_not_called()

    def test_perchance_setup_pending_override_applies_outside_regular_benchmark_store(self):
        from workbench import perchance_setup
        self.app.demo = False
        with patch('workbench.inventory.detect_gpus', return_value=[{'name': 'Mock GPU', 'total_gib': 8}]), \
             patch('workbench.perchance_setup.perchance.plan', return_value={'pending': []}), \
             patch('workbench.perchance_setup.health', return_value={'ready': True, 'reason': ''}) as health:
            perchance_setup.prepare(self.app, selection={'model_id': 'perchance-text-generator'}, force_pending=True)
        health.assert_called_once()
        self.assertEqual(self.app.perchance_setup_decision['status'], 'ready')

    def test_model_load_timeout_is_infrastructure_not_a_terminal_test_timeout(self):
        class LoadTimeoutRuntime(MockRuntime):
            def evaluate(self, model, case, candidate, repetition):
                self.trial_started = False
                self.backend.timed_out = True
                raise RuntimeError('model load watchdog')
        with self.assertRaisesRegex(RuntimeError, 'model load watchdog'):
            Engine(self.app, self.session['id'], LoadTimeoutRuntime).run(cohort=self.cohort)
        saved = self.store.load(self.session['id'])
        record = self.store.observations(saved)[0]
        self.assertEqual(record['status'], 'error')
        self.assertFalse(record['timed_out'])
        self.assertFalse(score(saved, None, self.cohort['models'], [record])['complete'])

    def test_automatic_tokens_are_not_user_settings_and_old_controls_are_ignored(self):
        self.assertNotIn('context_tokens', settings({}))
        self.assertNotIn('output_reserve', settings({}))
        for key in ('context_tokens', 'output_reserve'):
            with self.assertRaises(ValueError):
                settings({key: 8192})
        old = {'max_attempts': 20, 'context_tokens': 1024, 'output_reserve': 256}
        normalized = settings(old, allow_legacy=True)
        self.assertEqual(normalized, settings({'max_attempts': 20}))
        self.assertEqual(old['context_tokens'], 1024)

    def test_token_plan_uses_native_limit_reasoning_and_prior_output(self):
        messages = [{'role': 'user', 'content': 'hello'}]
        basic = token_plan(native(), messages)
        reasoning = token_plan(native(), messages, True)
        observed = token_plan(native(), messages, False, [{'text': 'x' * 24000}])
        self.assertGreater(reasoning['desired_output_reserve'], basic['desired_output_reserve'])
        self.assertGreater(observed['desired_output_reserve'], basic['desired_output_reserve'])
        tiny = {**native(), 'metadata': {'mock.context_length': 2048}}
        limited = token_plan(tiny, [{'role': 'user', 'content': 'x' * 100000}], True)
        self.assertEqual(limited['context_tokens'], 2048)
        self.assertEqual(limited['output_reserve'], 512)
        with self.assertRaisesRegex(ValueError, 'metadata'):
            token_plan({**native(), 'metadata': {}}, messages)

    def test_exact_tokenizer_grows_context_before_pruning_and_uses_remaining_output(self):
        packet = {'history': [], 'pruned_attempts': [], 'protected': 'keep'}
        runtime = TokenRuntime(lambda _: 20000)
        backend, messages, budget = engine.prepare_generation(self.session, packet, native(), settings({}), runtime)
        self.assertGreater(len(runtime.loads), 1)
        self.assertGreater(runtime.loads[-1], runtime.loads[0])
        self.assertEqual(budget['pruned_attempts'], [])
        self.assertEqual(budget['input_tokens'], 20000)
        self.assertEqual(budget['output_tokens_available'], backend.context - 20000 - 32)
        self.assertGreater(budget['output_tokens_available'], budget['output_reserve'])

    def test_gpu_memory_backoff_prunes_only_history_and_records_every_load(self):
        packet = {'history': [{'number': 1, 'candidate': None, 'text': 'x' * 40000}],
                  'pruned_attempts': [], 'top_three': [{'candidate': 'winner'}]}
        original = copy.deepcopy(packet)
        runtime = TokenRuntime(lambda messages: 9000 if '"number": 1' in messages[1]['content'] else 1000, capacity=8192)
        backend, messages, budget = engine.prepare_generation(self.session, packet, native(), settings({}), runtime)
        self.assertEqual(backend.context, 8192)
        self.assertEqual(budget['memory_context_ceiling'], 8192)
        self.assertEqual(budget['pruned_attempts'], [1])
        self.assertIn('winner', messages[1]['content'])
        self.assertTrue(any(item['status'] == 'gpu_memory_error' for item in budget['load_attempts']))
        self.assertEqual(packet, original)

    def test_automatic_preparation_does_not_retry_other_runtime_errors(self):
        packet = {'history': [], 'pruned_attempts': []}
        runtime = TokenRuntime(lambda _: 1000, failure=RuntimeStall('Fixture loading timed out'))
        with self.assertRaises(RuntimeStall):
            engine.prepare_generation(self.session, packet, native(), settings({}), runtime)
        self.assertEqual(len(runtime.loads), 1)

    def test_automatic_budget_refuses_to_truncate_protected_content(self):
        packet = {'history': [], 'pruned_attempts': [], 'top_three': ['protected winner']}
        original = copy.deepcopy(packet)
        runtime = TokenRuntime(lambda _: 70000)
        with self.assertRaisesRegex(ValueError, 'Protected'):
            engine.prepare_generation(self.session, packet, native(), settings({}), runtime)
        self.assertEqual(runtime.loads[-1], 65536)
        self.assertEqual(packet, original)

    def test_old_session_uses_automatic_budget_without_erasing_old_settings(self):
        old = self.store.load(self.session['id'])
        old['settings'].update(context_tokens=1024, output_reserve=256)
        self.store.save(old)
        runner, holder = self.runner()
        runner.run(cohort=self.cohort)
        saved = self.store.load(old['id'])
        self.assertEqual(saved['settings']['context_tokens'], 1024)
        request = self.store.get_evidence(saved['id'], saved['attempts'][0]['request_evidence'])
        self.assertEqual(request['context']['policy'], 'automatic-generator-tokens-v1')
        self.assertGreater(request['context']['context_tokens'], 1024)
        self.assertEqual(holder[0].requests[0]['reserve'], request['context']['output_tokens_available'])
        self.assertGreater(holder[0].requests[0]['reserve'], request['context']['output_reserve'])

    def test_preparation_error_saved_without_consuming_attempt_and_resume_reuses_baseline(self):
        missing = self.store.load(self.session['id'])
        missing['cohort']['models'][0]['metadata'] = {}
        self.store.save(missing)
        with self.assertRaisesRegex(ValueError, 'metadata'):
            Engine(self.app, missing['id'], MockRuntime).run(cohort=missing['cohort'])
        failed = self.store.load(missing['id'])
        self.assertEqual(failed['attempts'], [])
        error = self.store.get_evidence(failed['id'], failed['preparation_errors'][0])
        self.assertEqual(error['kind'], 'generation_preparation_error')
        runner, holder = self.runner()
        runner.run(cohort=self.cohort)
        self.assertEqual(len(holder[0].trials), 3)
        self.assertEqual(self.store.load(missing['id'])['status'], 'perfect')

    def test_generator_output_limit_is_the_automatically_available_context(self):
        backend = GeneratorBackend({'backend': 'llamacpp'}, {}, lambda *args: None)
        backend.owned_id = 'test'
        backend.load_metadata = {}
        backend.transport = SimpleNamespace(request=lambda endpoint, body, **kwargs: body)
        result = backend.propose([{'role': 'user', 'content': 'prompt'}], {'temperature': .7}, 12256, threading.Event())
        self.assertEqual(result['max_tokens'], 12256)
        self.assertEqual(result['request_messages'][0]['content'], 'prompt')

    def test_automatic_memory_backoff_is_bounded_and_preserves_diagnostics(self):
        runtime = TokenRuntime(lambda _: 1000, capacity=512)
        with self.assertRaises(DoesNotFit) as failure:
            engine.prepare_generation(self.session, {'history': [], 'pruned_attempts': []}, native(), settings({}), runtime)
        self.assertEqual(runtime.loads[-1], 1024)
        self.assertEqual(len(runtime.loads), len(set(runtime.loads)))
        self.assertEqual(len(failure.exception.evidence['automatic_token_planning']), len(runtime.loads))

    def test_archive_preserves_and_requires_preparation_error_evidence(self):
        saved = self.store.load(self.session['id'])
        key = self.store.evidence(saved['id'], {'kind': 'generation_preparation_error', 'error': 'capacity'})
        saved['preparation_errors'] = [key]
        self.store.save(saved)
        archive = self.store.export(saved['id'])
        target = Store(self.root / 'other')
        target.import_archive(archive)
        self.assertEqual(target.load(saved['id'])['preparation_errors'], [key])
        self.assertEqual(target.get_evidence(saved['id'], key)['error'], 'capacity')
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(archive)) as original, zipfile.ZipFile(output, 'w') as altered:
            for name in original.namelist():
                if name != 'evidence/' + key + '.json':
                    altered.writestr(name, original.read(name))
        with self.assertRaisesRegex(ValueError, 'missing referenced evidence'):
            Store(self.root / 'broken').import_archive(output.getvalue())


if __name__ == '__main__':
    unittest.main()
