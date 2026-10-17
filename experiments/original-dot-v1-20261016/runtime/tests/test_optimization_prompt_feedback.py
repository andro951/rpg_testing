from unittest.mock import patch
from tests.suite_fixtures import LEGACY_ROOT, fixture_path, legacy_sharing
import copy
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from optimization import engine, prompt_builder
from optimization.engine import create, Engine
from optimization.storage import Store
from optimization.feedback import diagnostic
from optimization.export_prompt import export
from tests.test_prompt_optimization import ROOT, native, MockRuntime, TokenRuntime
from workbench.controller import Controller
from workbench.domain import digest


class PromptFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ('test_specs', 'docs/prompt-optimization', 'optimization/definitions'):
            shutil.copytree(fixture_path(folder), self.root / folder)
        catalog_patch = patch('optimization.templates.catalog', side_effect=legacy_sharing)
        catalog_patch.start()
        self.addCleanup(catalog_patch.stop)
        self.app = Controller(self.root, demo=True)
        self.cohort = {'models': [native()], 'gpu': {'name': 'Mock GPU', 'total_gib': 8}, 'simulated': True}
        self.session = create(self.app, {'generator_id': 'local-a'}, self.cohort)
        self.store = Store(self.root)

    def packet(self, records):
        return engine.generation_packet(self.session, self.cohort['models'], records, self.store)

    def trial(self, index=0):
        message = {'role': 'user', 'content': 'Exact state ' + 'x' * 10000}
        check = {'code': 'pointer.syntax', 'status': 'failed', 'explanation': 'path: Invalid JSON Pointer',
                 'expected': 'ORACLE_STATE_MUST_NOT_BE_IN_PROMPT', 'actual': 'x' * 100000}
        return {'candidate': None, 'model_id': 'local-a', 'model_identity': native()['identity'],
                'case_id': next(iter(self.session['scope']['cases'])), 'repetition': index,
                'trial_key': 'trial-' + str(index), 'status': 'completed', 'pass': False,
                'outputs': {'patch': '[{"op":"move","path":"tickets/7","from":"tickets/91"}]'},
                'score': {'exact_match': False, 'actual_state': 'x' * 100000},
                'evaluation': {'objective_outcome': 'FAIL', 'primary_reason': 'path: Invalid JSON Pointer',
                    'original_score': {'actual_state': 'x' * 100000}, 'checks': [check], 'steps': [{'checks': [check]}]},
                'calls': [{'step': 'patch', 'request_messages': [message],
                    'text': '[{"op":"move","path":"tickets/7","from":"tickets/91"}]', 'finish_reason': 'stop',
                    'raw_chunks': ['stream chunk'] * 10000}]}

    def test_exact_prompts_once_all_trial_outputs_and_no_oracle_or_duplicate_states(self):
        records = [self.trial(i) for i in range(5)]
        original = copy.deepcopy(records)
        packet = self.packet(records)
        self.assertEqual(records, original)
        self.assertEqual(len(packet['prompts']), 1)
        self.assertEqual(len(packet['reference_evidence']), 5)
        for item in packet['reference_evidence']:
            self.assertEqual(item['calls'][0]['text'], records[0]['calls'][0]['text'])
            self.assertEqual(len(item['evaluation']['other_checks']), 1)
            self.assertEqual(item['evaluation']['primary_reason'], 'path: Invalid JSON Pointer')
        message = engine.packet_messages(self.session, packet)[0]['content']
        self.assertEqual(message.count(records[0]['calls'][0]['request_messages'][0]['content']), 1)
        self.assertNotIn('ORACLE_STATE_MUST_NOT_BE_IN_PROMPT', message)
        self.assertNotIn('raw_chunks', message)
        self.assertNotIn('original_score', message)
        self.assertNotIn('actual_state', message)
        self.assertLess(len(message), len(json.dumps(original)) // 10)

    def test_timeout_retains_full_partial_output_and_fallback_captured_messages(self):
        record = self.trial()
        record.update(status='timeout', error='Operational watchdog expired')
        call = record['calls'][0]
        call['messages'] = call.pop('request_messages')
        call['text'] = 'PARTIAL_BEGIN\n' + 'unclosed ` <{x}> (2{x}) ' * 1000 + '\nPARTIAL_END'
        call['incomplete'] = True
        call['finish_reason'] = None
        packet = self.packet([record])
        self.assertEqual(len(packet['prompts']), 1)
        captured = packet['reference_evidence'][0]['calls'][0]
        self.assertEqual(captured['request_capture'], 'captured_workflow_messages')
        self.assertTrue(captured['incomplete'])
        self.assertIn(call['text'], engine.packet_messages(self.session, packet)[0]['content'])

    def test_builder_is_user_only_preserves_language_examples_and_fills_slots(self):
        messages = engine.packet_messages(self.session, self.packet([]))
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['role'], 'user')
        text = messages[0]['content']
        self.assertIn(self.session['prompt_builder']['description'], text)
        self.assertIn('This is the 1st run. You have created 0 new prompts so far.', text)
        for name in ('LPIL_DESCRIPTION', 'EVALUATION_HISTORY', 'TASK_DEFINITION', 'OPTIMIZER_OUTPUT_RULES'):
            self.assertNotIn('<{' + name + '}>', text)
        self.assertIn('Write `(1{current_state})` exactly 1 time.', text)
        self.assertIn('SYSTEM_MESSAGE:', text)

    def test_reviewed_prompt_explains_scoring_scope_controls_and_empty_system(self):
        record = self.trial()
        record.update(status='timeout', timeout_seconds=120, benchmark_reasoning=None)
        text = engine.packet_messages(self.session, self.packet([record]))[0]['content']
        self.assertIn('a timeout is unsuccessful', text)
        self.assertIn('does not turn a timeout into a pass or a proven semantic failure', text)
        self.assertIn('Checks marked not_evaluated were not checked', text)
        self.assertIn('Perchance\'s reasoning setting is unverified', text)
        self.assertIn('Requested sampling controls are not confirmed applied controls', text)
        self.assertIn('"timeout_seconds": 120', text)
        self.assertIn('"benchmark_reasoning": null', text)
        self.assertIn('"origin_model_id": "local-a"', text)
        self.assertIn('every configured repetition', text)
        self.assertIn('There are no fully tested generated candidates', text)
        self.assertIn('You may leave SYSTEM_MESSAGE empty', text)
        self.assertIn('do not copy those backticks around the markers', text)

    def test_foreign_host_evidence_does_not_influence_feedback(self):
        local, foreign, replaced = self.trial(), self.trial(1), self.trial(2)
        foreign['model_id'] = 'foreign-model'
        replaced['model_identity'] = 'different-model-with-same-id'
        self.assertEqual(len(self.packet([local, foreign, replaced])['reference_evidence']), 1)

    def test_generation_raw_chunks_reasoning_not_duplicated_into_history(self):
        key = self.store.evidence(self.session['id'], {'kind': 'generation_response', 'text': 'invalid candidate',
            'reasoning_text': 'hidden reasoning' * 10000, 'raw_chunks': ['chunk'] * 10000})
        self.session['attempts'] = [{'number': 1, 'status': 'invalid', 'response_evidence': key}]
        packet = self.packet([])
        self.assertEqual(packet['history'][0]['generation']['text'], 'invalid candidate')
        text = engine.packet_messages(self.session, packet)[0]['content']
        self.assertIn('invalid candidate', text)
        self.assertNotIn('hidden reasoning', text)
        self.assertNotIn('raw_chunks', text)
        self.assertEqual(self.store.get_evidence(self.session['id'], key)['reasoning_text'], 'hidden reasoning' * 10000)

    def test_pruning_removes_only_unreferenced_history_prompts(self):
        packet = {'history': [{'number': 1, 'candidate': None, 'trials': [{'calls': [{'prompt_id': 'unused'}]}]}],
                  'prompts': {'unused': [{'role': 'user', 'content': 'huge unused prompt'}],
                              'shared': [{'role': 'user', 'content': 'keep baseline'}]},
                  'reference_evidence': [{'calls': [{'prompt_id': 'shared'}]}], 'pruned_attempts': []}
        original = copy.deepcopy(packet)
        counter = lambda messages: 99999 if 'huge unused prompt' in messages[0]['content'] else 1000
        messages, result = engine.fit_packet(self.session, packet, counter, {'context_tokens': 8192, 'output_reserve': 4096})
        self.assertEqual(result['pruned_attempts'], [1])
        self.assertNotIn('huge unused prompt', messages[0]['content'])
        self.assertIn('keep baseline', messages[0]['content'])
        self.assertEqual(packet, original)

    def test_context_error_saves_measured_counts_not_just_estimated_bytes(self):
        runtime = TokenRuntime(lambda messages: 70000)
        with self.assertRaises(ValueError) as raised:
            engine.prepare_generation(self.session, self.packet([]), native(), engine.settings({}), runtime)
        self.assertEqual(raised.exception.evidence['input_tokens'], 70000)
        self.assertEqual(raised.exception.evidence['context_tokens'], 65536)
        self.assertIn('70000', str(raised.exception))

    def test_resume_old_zero_attempt_session_adopts_writer_without_rerunning_baseline(self):
        session = self.store.load(self.session['id'])
        session.pop('prompt_builder')
        old_system, old_user = session['optimizer_system'], session['optimizer_user']
        self.store.save(session)
        holder = []
        def factory(app, cohort):
            runtime = MockRuntime(app, cohort)
            holder.append(runtime)
            return runtime
        runner = Engine(self.app, session['id'], factory)
        runner.runtime = MockRuntime(self.app, self.cohort)
        runner.evaluate(None, self.cohort['models'], session['scope']['layers'][-1]['members'])
        before = self.store.load(session['id'])['observations'][:]
        Engine(self.app, session['id'], factory).run(cohort=self.cohort)
        updated = self.store.load(session['id'])
        self.assertEqual(len(holder[0].trials), 3)  # Candidate only, no baseline reruns.
        self.assertEqual(updated['observations'][:len(before)], before)
        self.assertEqual((updated['optimizer_system'], updated['optimizer_user']), (old_system, old_user))
        self.assertEqual(updated['prompt_builder']['version'], 'lpil-opro-v1')
        self.assertEqual(updated['status'], 'perfect')
        adopted = self.store.get_evidence(session['id'], updated['configuration_history'][0])
        self.assertEqual(adopted['kind'], 'prompt_builder_adopted')
        self.assertEqual(len(holder[0].requests[0]['messages']), 1)

    def test_export_matches_next_request_without_mutating_session_or_evidence(self):
        def contents(data):
            # ZIP creation timestamps can differ even when saved evidence is unchanged.
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                return {name: archive.read(name) for name in archive.namelist()}
        before = contents(self.store.export(self.session['id']))
        destination = self.root / 'export/first.txt'
        metadata = export(self.root, self.session['id'], destination)
        expected = engine.packet_messages(self.session, self.packet([]))
        self.assertEqual(destination.read_bytes(), expected[0]['content'].encode('utf-8'))
        self.assertEqual(json.loads(destination.with_suffix('.messages.json').read_text()), expected)
        self.assertEqual(metadata['message_digest'], digest(expected))
        self.assertEqual(contents(self.store.export(self.session['id'])), before)
        self.assertFalse(metadata['inference_started'])

    def test_existing_source_counts_and_custom_output_builder(self):
        config = self.session['prompt_builder']
        config['source_candidate'] = '<{source}>'
        config['existing_replacements'] = [{'name': 'source', 'count': 2}]
        with self.assertRaisesRegex(ValueError, 'counts'):
            engine.packet_messages(self.session, self.packet([]))
        config['existing_replacements'][0]['count'] = 1
        config['use_standard_opro_output'] = False
        config['output_rules'] = 'Return one complete customer-message classifier.'
        text = engine.packet_messages(self.session, self.packet([]))[0]['content']
        self.assertIn(config['output_rules'], text)
        self.assertNotIn('SYSTEM_MESSAGE:', text)


if __name__ == '__main__':
    unittest.main()
