"""Codex transport, durable writer configuration and OPRO integration (synthetic inference)."""
import copy
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from optimization import codex
from optimization.engine import Engine, create
from optimization.storage import Store
from tests import test_prompt_optimization as fixtures
from workbench.workflows import Cancelled

OPTIONS = {'models': [{'id': 'fake-gpt-a', 'name': 'Synthetic GPT', 'efforts': ['low', 'high'],
                       'default_effort': 'low', 'is_default': True}], 'default_model': 'fake-gpt-a'}
WRITER = {'provider': 'codex', 'model': 'fake-gpt-a', 'effort': 'high'}
PEER = Path(__file__).parent / 'fixtures/codex_app_server.py'


class CodexTransportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = SimpleNamespace(root=Path(temporary.name), cancel_event=threading.Event(), set_progress=lambda *args: None)
        self.session = {'id': 'synthetic-session', 'prompt_writer': dict(WRITER)}
        self.saved = []

    def client(self, mode='normal', **kwargs):
        return codex.Client([sys.executable, str(PEER), mode], **kwargs)

    def generator(self, mode='normal'):
        generator = codex.Generator(self.app, self.session, lambda: self.saved.append(copy.deepcopy(self.session)),
                                    client_factory=lambda **kwargs: self.client(mode, **kwargs))
        self.addCleanup(generator.close)
        return generator

    def test_real_stdio_catalog_pagination_and_signed_out(self):
        for mode in ('normal', 'signed-out', 'malformed'):
            with self.subTest(mode=mode):
                client = self.client(mode)
                try:
                    if mode == 'malformed':
                        with self.assertRaisesRegex(RuntimeError, 'malformed'):
                            client.initialize()
                    else:
                        client.initialize()
                        if mode == 'signed-out':
                            with self.assertRaisesRegex(ValueError, 'Sign in'):
                                client.models()
                        else:
                            self.assertEqual([m['id'] for m in client.models()], ['fake-gpt-a', 'fake-gpt-b'])
                finally:
                    client.close()

    def test_thread_saved_before_turn_and_reused_after_reconnection(self):
        generator = self.generator()
        self.assertEqual(self.saved[0]['codex_thread']['id'], 'synthetic-thread')
        response = generator.propose([{'role': 'user', 'content': 'Synthetic request'}], {}, None, self.app.cancel_event)
        self.assertEqual(response['text'], 'Synthetic proposal')
        self.assertNotIn('Thinking', response['text'])
        self.assertEqual(response['finish_reason'], 'stop')
        self.assertEqual(response['rpc_request']['effort'], 'high')
        self.assertNotIn('temperature', response['rpc_request'])
        self.assertNotIn('outputSchema', response['rpc_request'])
        self.assertTrue(any(e['method'] == 'thread/tokenUsage/updated' for e in response['raw_events']))
        generator.close()
        previous_saves = len(self.saved)
        resumed = self.generator()
        self.assertEqual(resumed.thread_id, 'synthetic-thread')
        self.assertEqual(len(self.saved), previous_saves)
        self.assertEqual(resumed.propose([{'role': 'user', 'content': 'Next'}], {}, None, self.app.cancel_event)['thread_id'], response['thread_id'])

    def test_failed_resume_never_creates_a_replacement_thread(self):
        self.session['codex_thread'] = {'id': 'saved-thread', 'host_identity': codex.host_identity()}
        with self.assertRaisesRegex(RuntimeError, 'thread missing'):
            self.generator('resume-fail')
        self.assertEqual(self.session['codex_thread']['id'], 'saved-thread')
        self.assertEqual(self.saved, [])

    def test_invalid_effort_missing_install_and_foreign_host(self):
        with self.assertRaisesRegex(ValueError, 'supported effort'):
            codex.validate({**WRITER, 'effort': 'unsupported'}, OPTIONS)
        with patch('optimization.codex.shutil.which', return_value=None), patch('optimization.codex.Path.glob', return_value=[]):
            with self.assertRaisesRegex(ValueError, 'not installed'):
                codex.command()
        self.session['codex_thread'] = {'id': 'other', 'host_identity': 'foreign'}
        with self.assertRaisesRegex(ValueError, 'another worker'):
            self.generator()

    def test_failure_disconnection_and_interactive_request_saved_without_retry(self):
        for mode, text in (('failed', 'Synthetic generation failure'), ('rpc-error', 'Synthetic turn rejected'),
                           ('disconnect', 'disconnected'), ('interactive', 'interactive')):
            with self.subTest(mode=mode):
                generator = self.generator(mode)
                with self.assertRaisesRegex(RuntimeError, text) as raised:
                    generator.propose([{'role': 'user', 'content': 'Synthetic request'}], {}, None, self.app.cancel_event)
                self.assertEqual(raised.exception.partial_response['thread_id'], 'synthetic-thread')
                if mode == 'failed':
                    self.assertEqual(raised.exception.partial_response['text'], 'Synthetic proposal')
                generator.close()

    def test_cancel_sends_interrupt_and_preserves_partial_without_deadline(self):
        generator = self.generator()
        self.app.set_progress = lambda *args: self.app.cancel_event.set()
        with patch.object(generator.client, 'send', wraps=generator.client.send) as sent:
            with self.assertRaises(Cancelled) as raised:
                generator.propose([{'role': 'user', 'content': 'Synthetic request'}], {}, None, self.app.cancel_event)
        self.assertEqual(raised.exception.partial_response['text'], 'Synthetic proposal')
        self.assertTrue(any(call.args[0] == 'turn/interrupt' for call in sent.call_args_list))
        self.assertEqual(raised.exception.partial_response['finish_reason'], 'interrupted')


class CodexEngineTests(unittest.TestCase):
    def setUp(self):
        fixtures.OptimizationTests.setUp(self)
        with patch('optimization.codex.discover', return_value=OPTIONS):
            self.session = create(self.app, {'prompt_writer': WRITER, 'settings': {'max_attempts': 2}}, self.cohort)
        self.runner = Engine(self.app, self.session['id'], fixtures.MockRuntime)
        self.generator_instances = []

    def fake_generator(self, app, session, save):
        session.setdefault('codex_thread', {'id': 'synthetic-thread', 'host_identity': codex.host_identity()})
        save()
        def propose_one(messages, sampling, limit, cancel):
            import re
            self.assertEqual(sampling, {})
            self.assertIsNone(limit)
            text = fixtures.proposal('bad' if not self.generator_instances else 'good')
            text = re.sub(r'\$\{([A-Za-z_][A-Za-z_0-9]*)\}', r'(1{\1})', text)
            self.generator_instances.append(session['codex_thread']['id'])
            return {'text': text, 'finish_reason': 'stop', 'thread_id': session['codex_thread']['id']}
        return SimpleNamespace(propose=propose_one, close=lambda: None, load_metadata={})

    def test_codex_candidates_use_existing_evaluation_and_resume_same_thread(self):
        with patch('optimization.codex.Generator', side_effect=self.fake_generator):
            self.runner.run(cohort=self.cohort)
        saved = self.store.load(self.session['id'])
        self.assertEqual([a['status'] for a in saved['attempts']], ['origin_failed', 'complete'])
        self.assertEqual(self.generator_instances, ['synthetic-thread', 'synthetic-thread'])
        self.assertEqual(saved['status'], 'perfect')
        request = self.store.get_evidence(saved['id'], saved['attempts'][0]['request_evidence'])
        self.assertEqual(request['applied_controls'], {'model': 'fake-gpt-a', 'effort': 'high'})
        self.assertEqual(request['unsupported_controls'], ['temperature', 'seed', 'local_reasoning_toggle'])
        self.assertIsNone(request['timeout_seconds'])
        self.assertEqual(request['sampling'], {})
        before = len(self.store.observations(saved))
        with patch('optimization.codex.Generator', side_effect=AssertionError('No duplicate generation')):
            Engine(self.app, saved['id'], fixtures.MockRuntime).run(cohort=self.cohort)
        self.assertEqual(len(self.store.observations(self.store.load(saved['id']))), before)
        self.assertEqual(self.store.load(saved['id'])['prompt_writer'], WRITER)

    def test_invalid_writer_rejected_and_legacy_defaults_local(self):
        for writer in ({'provider': 'other'}, {'provider': 'local', 'effort': 'high'}, {**WRITER, 'effort': 'unsupported'}):
            with patch('optimization.codex.discover', return_value=OPTIONS), self.assertRaises(ValueError):
                create(self.app, {'prompt_writer': writer}, self.cohort)
        local = create(self.app, {'generator_id': 'local-a'}, self.cohort)
        self.assertEqual(local['prompt_writer'], {'provider': 'local'})

    def test_stopped_codex_proposal_saves_partial_and_consumes_attempt(self):
        def interrupted(app, session, save):
            backend = self.fake_generator(app, session, save)
            def stop(*args):
                error = Cancelled('Synthetic manual stop')
                error.partial_response = {'text': 'Unfinished proposal', 'thread_id': 'synthetic-thread',
                                          'raw_events': [{'method': 'item/reasoning/summaryTextDelta', 'params': {'delta': 'partial reasoning'}}]}
                raise error
            backend.propose = stop
            return backend
        with patch('optimization.codex.Generator', side_effect=interrupted), self.assertRaises(Cancelled):
            self.runner.run(cohort=self.cohort)
        session = self.store.load(self.session['id'])
        self.assertEqual(session['status'], 'stopped')
        self.assertEqual(session['attempts'][0]['status'], 'interrupted')
        evidence = self.store.get_evidence(session['id'], session['attempts'][0]['error_evidence'])
        self.assertEqual(evidence['partial_response']['text'], 'Unfinished proposal')
        self.assertEqual(evidence['partial_response']['raw_events'][0]['params']['delta'], 'partial reasoning')
        self.assertEqual(session['codex_thread']['id'], 'synthetic-thread')

    def test_import_preserves_thread_and_rejects_conflicting_writer(self):
        self.session['codex_thread'] = {'id': 'synthetic-thread', 'host_identity': codex.host_identity()}
        self.store.save(self.session)
        archive = self.store.export(self.session['id'])
        self.assertEqual(self.store.import_archive(archive), self.session['id'])
        changed = self.store.load(self.session['id'])
        changed['prompt_writer']['effort'] = 'low'
        self.store.save(changed)
        with self.assertRaisesRegex(ValueError, 'prompt-writer contracts'):
            self.store.import_archive(archive)
