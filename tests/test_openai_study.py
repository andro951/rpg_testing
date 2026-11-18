"""Isolated controller tests: scripted API only, no network, Git or paid calls."""
import copy
from decimal import Decimal
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from tests.test_self_review import fixture
from workbench.api_budget import BudgetLedger, BudgetExceeded
from workbench.domain import read_json, write_json
from workbench.openai_study import OpenAIStudyController

MODELS = ['gpt-6.1-sol', 'gpt-6-luna']


def response(text):
    return {'status': 'completed', 'id': 'scripted-response',
            'usage': {'input_tokens': 100, 'output_tokens': 10},
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}


class Transport:
    simulated=True
    def __init__(self, script=()):
        self.script = iter(script)
        self.requests = []
        self.before_request = None

    def available_models(self): return MODELS

    def request(self, method, path, body):
        self.requests.append(copy.deepcopy((method, path, body)))
        if self.before_request: self.before_request(len(self.requests))
        item = next(self.script)
        if isinstance(item, Exception): raise item
        return response(item)


class Sync:
    def __init__(self, root):
        self.root = root
        self.events = []
        self.batches = []

    def retry(self):
        self.events.append('retry')
        return {'status': 'complete'}

    def begin(self):
        batch = {'files': {}, 'status': 'recording'}
        self.batches.append(batch)
        self.events.append('begin')
        return batch

    def relative_result_path(self, path): return path.relative_to(self.root).as_posix()

    def before_save(self, batch, path):
        self.events.append('before')
        batch['files'][self.relative_result_path(path)] = None

    def after_save(self, batch, name):
        self.events.append('after')
        self.assert_saved = (self.root/name).is_file()
        batch['files'][name] = 'recorded'

    def save_receipt(self, batch): self.events.append('receipt')


class OpenAIStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = BudgetLedger(self.root/'budget.json', '100')
        self.git = patch('workbench.openai_study.git', return_value='source-commit-one')
        self.git.start(); self.addCleanup(self.git.stop)

    def controller(self, transport, tests=None, models=None, coverage='coverage', **kwargs):
        return OpenAIStudyController(self.root, tests or [fixture(False)], models or MODELS[:1],
            'medium', kwargs.pop('ledger', self.ledger), transport,
            coverage_id=coverage, approved_controls=True, simulated=kwargs.pop('simulated', True), **kwargs)

    def test_production_rejects_foreign_checkout(self):
        from workbench.openai_study import _validate_checkout
        with self.assertRaises(ValueError):_validate_checkout(self.root)

    def test_full_scope_copied_with_off_and_justified_on(self):
        original = fixture(False)
        on = copy.deepcopy(original['variants'][0]); on.update(id='on', retry_enabled=True)
        original['variants'].append(on)
        before = copy.deepcopy(original)
        transport = Transport(['READY', 'READY', 'Yes\nThe requested READY answer is correct.'])
        controller = self.controller(transport, [original])
        self.assertEqual(original, before)
        variants = controller.tests[0]['variants']
        self.assertFalse(variants[0]['retry_enabled'])
        self.assertEqual(variants[1]['retry_protocol'], 'justified-v2')
        summary = controller.run()
        self.assertEqual(summary['completed'], 2)
        self.assertEqual(len(transport.requests), 3)
        self.assertEqual(len(controller.store.all()), 2)
        self.assertTrue(all(record['score']['exact_match'] for record in controller.store.all()))
        self.assertNotIn('secret_oracle', str(transport.requests))

    def test_journal_durable_before_next_call_and_contains_raw(self):
        transport = Transport(['READY', 'Yes\nCorrect answer.'])
        controller = self.controller(transport, [fixture(True)])
        cid = next(controller.jobs())[-1]
        def observe(number):
            journal = read_json(controller.local/(cid+'.json'))
            self.assertEqual(journal['calls'][-1]['status'], 'in_flight')
            if number == 2:
                self.assertEqual(journal['calls'][0]['status'], 'complete')
                self.assertEqual(journal['calls'][0]['response']['raw_response']['id'], 'scripted-response')
        transport.before_request = observe
        controller.run()
        journal = read_json(controller.local/(cid+'.json'))
        self.assertEqual(journal['status'], 'completed')
        self.assertEqual(len(journal['calls']), 2)
        self.assertTrue(all(row['status']=='complete' for row in journal['calls']))

    def test_completed_results_resume_without_inference(self):
        first = self.controller(Transport(['READY']))
        first.run()
        second_transport = Transport([])
        second = self.controller(second_transport)
        self.assertEqual(second.run(), {'status': 'completed', 'completed': 0, 'reused': 1})
        self.assertFalse(second_transport.requests)
        self.assertEqual(len(second.store.all()), 1)

    def test_unknown_transport_case_blocks_automatic_replay(self):
        first_transport = Transport([TimeoutError('scripted')])
        first = self.controller(first_transport)
        with self.assertRaises(TimeoutError): first.run()
        self.assertEqual(len(first_transport.requests), 1)
        result = first.store.all()[0]
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['raw_call_journal']['calls'][0]['status'], 'interrupted')
        self.assertEqual(next(iter(self.ledger.snapshot()['calls'].values()))['status'], 'uncertain')
        second_transport = Transport([])
        with self.assertRaisesRegex(RuntimeError, 'reconciliation'):
            self.controller(second_transport).run()
        self.assertFalse(second_transport.requests)

    def test_abandoned_started_journal_blocks_replay(self):
        transport = Transport([])
        controller = self.controller(transport)
        cid = next(controller.jobs())[-1]
        write_json(controller.local/(cid+'.json'), {'status': 'started', 'calls': []})
        with self.assertRaisesRegex(RuntimeError, 'reconciliation'): controller.run()
        self.assertFalse(transport.requests)

    def test_budget_denial_before_transport_has_no_paid_retry(self):
        ledger = BudgetLedger(self.root/'small.json', '.001')
        transport = Transport([])
        controller = self.controller(transport, ledger=ledger)
        with self.assertRaises(BudgetExceeded): controller.run()
        self.assertFalse(transport.requests)
        self.assertFalse(ledger.snapshot()['calls'])
        with self.assertRaisesRegex(RuntimeError, 'reconciliation'):
            self.controller(Transport([]), ledger=ledger).run()
        self.assertEqual(len(controller.store.all()), 1)

    def test_case_identity_changes_with_provenance_controls(self):
        original = self.controller(Transport([]))
        original_id = next(original.jobs())[-1]
        other = self.controller(Transport([]), coverage='other')
        self.assertNotEqual(original_id, next(other.jobs())[-1])
        with patch('workbench.openai_study.api_fingerprint', return_value='different-source'):
            with self.assertRaisesRegex(ValueError, 'source/controls changed'):
                self.controller(Transport([]))
            revised = self.controller(Transport([]), coverage='revised-source')
            self.assertNotEqual(original_id, next(revised.jobs())[-1])
        changed = fixture(False)
        changed['variants'][0]['steps'][0]['prompt'] = 'Return OTHER.'
        with self.assertRaisesRegex(ValueError, 'source/controls changed'):
            self.controller(Transport([]), [changed])

    def test_models_use_single_combined_ledger(self):
        transport = Transport(['READY', 'READY'])
        controller = self.controller(transport, models=MODELS)
        self.assertEqual(controller.run()['completed'], 2)
        entries = list(self.ledger.snapshot()['calls'].values())
        self.assertEqual(len(entries), 2)
        self.assertTrue(all(row['status']=='settled' for row in entries))
        self.assertEqual(Decimal(self.ledger.snapshot()['committed_usd']), Decimal('.000315'))
        self.assertEqual({request[2]['model'] for request in transport.requests}, set(MODELS))

    def test_exact_result_sync_enrollment_without_git_network(self):
        sync = Sync(self.root)
        with patch('workbench.openai_study._validate_checkout'):
            controller = self.controller(Transport(['READY']), simulated=False, sync=sync)
        with patch('workbench.openai_study._validate_checkout'):
            controller.run()
        self.assertTrue(sync.assert_saved)
        self.assertEqual(sync.events, ['retry', 'begin', 'before', 'after', 'receipt', 'retry'])
        paths = list(sync.batches[0]['files'])
        self.assertEqual(len(paths), 1)
        self.assertTrue(paths[0].startswith('results/gpt-6.1-sol/'))
        self.assertNotIn('budget', paths[0])
        self.assertFalse(controller.result_sync_active)

    def test_result_only_commit_resume_preserves_source_pin_and_case_id(self):
        state = {'head': 'source-commit', 'results': 'old-results-tree'}
        def fake_git(root, *args):
            if args == ('rev-parse', 'HEAD'): return state['head']
            if args == ('ls-tree', 'HEAD'):
                return ('040000 tree same-source-tree\tworkbench\n'
                        '100644 blob same-readme\tREADME.md\n'
                        '040000 tree '+state['results']+'\tresults\n')
            raise AssertionError(args)
        with patch('workbench.openai_study.git', side_effect=fake_git):
            first = self.controller(Transport(['READY']))
            original_id = next(first.jobs())[-1]
            first.run()
            state.update(head='result-sync-commit', results='new-results-tree')
            transport = Transport([])
            resumed = self.controller(transport)
            self.assertEqual(next(resumed.jobs())[-1], original_id)
            self.assertEqual(resumed.manifest['source_commit'], 'source-commit')
            self.assertEqual(resumed.run()['reused'], 1)
            self.assertFalse(transport.requests)

    def test_simulated_rejects_real_and_unmarked_transports(self):
        from workbench.openai_api import OpenAITransport
        for transport in (OpenAITransport('fake-key-never-used'), object()):
            with self.subTest(transport=type(transport).__name__):
                with self.assertRaisesRegex(ValueError, 'explicitly simulated transport'):
                    self.controller(transport)
        transport = Transport([]); transport.simulated = 1
        with self.assertRaisesRegex(ValueError, 'explicitly simulated transport'):
            self.controller(transport)

    def test_code_changed_between_construction_and_run_never_dispatches(self):
        transport = Transport([])
        controller = self.controller(transport)
        with patch('workbench.openai_study.api_fingerprint', return_value='changed-api'):
            with self.assertRaisesRegex(ValueError, 'Source changed'):
                controller.run()
        with patch('workbench.openai_study.code_fingerprint', return_value='changed-workflow'):
            with self.assertRaisesRegex(ValueError, 'Source changed'):
                controller.run()
        with patch('workbench.openai_study.git', return_value='different-tree'):
            with self.assertRaisesRegex(ValueError, 'Committed source changed'):
                controller.run()
        self.assertFalse(transport.requests)
        self.assertFalse(self.ledger.snapshot()['calls'])

    def test_billing_failure_journal_keeps_raw_request_and_call_id(self):
        class InvalidUsage(Transport):
            def request(self, method, path, body):
                self.requests.append(copy.deepcopy((method, path, body)))
                raw = response('READY')
                raw['usage'] = {'input_tokens': 100, 'output_tokens': 10,
                                'input_tokens_details': {'cache_write_tokens': 20}}
                return raw
        transport = InvalidUsage()
        controller = self.controller(transport)
        with self.assertRaises(RuntimeError): controller.run()
        result = controller.store.all()[0]
        evidence = result['raw_call_journal']['calls'][0]['partial_response']
        self.assertEqual(evidence['raw_response']['output'][0]['content'][0]['text'], 'READY')
        self.assertEqual(evidence['request'], transport.requests[0][2])
        call_id = evidence['budget_call_id']
        self.assertEqual(self.ledger.snapshot()['calls'][call_id]['status'], 'uncertain')
        envelope = result['raw_call_journal']['calls'][0]['received_before_settlement']
        self.assertEqual(envelope['raw_response'], evidence['raw_response'])
        self.assertEqual(envelope['budget_call_id'], call_id)
        self.assertEqual(envelope['request'], transport.requests[0][2])

    def test_received_envelope_is_durable_before_ledger_settlement(self):
        transport = Transport(['READY'])
        controller = self.controller(transport)
        cid = next(controller.jobs())[-1]
        settle = self.ledger.settle
        checked = []
        def inspect(call_id, usage, **kwargs):
            journal = read_json(controller.local/(cid+'.json'))
            envelope = journal['calls'][-1]['received_before_settlement']
            self.assertEqual(envelope['budget_call_id'], call_id)
            self.assertEqual(envelope['raw_response']['usage'], usage)
            self.assertEqual(envelope['request'], transport.requests[-1][2])
            self.assertEqual(self.ledger.snapshot()['calls'][call_id]['status'], 'reserved')
            checked.append(True)
            return settle(call_id, usage, **kwargs)
        with patch.object(self.ledger, 'settle', side_effect=inspect): controller.run()
        self.assertEqual(checked, [True])
        final = read_json(controller.local/(cid+'.json'))
        self.assertIn('received_before_settlement', final['calls'][0])

    def test_requires_control_approval_and_account_models(self):
        with self.assertRaisesRegex(ValueError, 'approval'):
            OpenAIStudyController(self.root, [fixture(False)], MODELS, 'medium', self.ledger,
                                  Transport([]), coverage_id='unapproved')
        transport = Transport([])
        transport.available_models = lambda: ['gpt-6-luna']
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            self.controller(transport).run()
        self.assertFalse(transport.requests)


if __name__ == '__main__': unittest.main()
