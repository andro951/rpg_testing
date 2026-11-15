"""Fixed context overruns are terminal case outcomes, not retries or model failures.

All generation in this module is simulated; no model/network requests occur.
"""
import copy
import unittest
from unittest.mock import patch

from tests import test_workbench_unattended as unattended
from workbench.execution_policy import ContextCapacity
from workbench.scheduler import Session, ContextCleanupFailure
from workbench.planning import pending_plan
from workbench.workflows import Cancelled


class FixedContextCapacityTests(unittest.TestCase):
    factory = unattended.UnattendedTests.factory
    run_session = unattended.UnattendedTests.run_session

    def setUp(self):
        unattended.UnattendedTests.setUp(self)
        for group in self.plan['groups']:
            group['context']['capacity_policy'] = 'fixed-case-local-v1'

    def add_second_case(self):
        group = self.plan['groups'][0]
        job = copy.deepcopy(group['jobs'][0])
        job['case_id'] = 'b' * 64
        job['variant']['id'] = 'second'
        group['jobs'].append(job)
        self.plan['pending'] += 1
        return job

    def backend_with_one_overrun(self, *, partial=True):
        backend = self.factory(lambda *a: None)
        original = backend.generate
        calls = {}
        def generate(model, *args, **kwargs):
            calls[model.mid] = calls.get(model.mid, 0) + 1
            if model.mid == 'large' and calls[model.mid] == 1:
                exc = ContextCapacity('Fixed context exhausted', 17000,
                                      {'input_tokens_verified': 16000})
                if partial:
                    exc.partial_response = {'text': 'unfinished answer',
                                            'reasoning_text': 'retained reasoning',
                                            'finish_reason': 'length',
                                            'raw_chunks': [{'text': 'unfinished answer'}],
                                            'request_seconds': .125}
                raise exc
            return original(model, *args, **kwargs)
        return backend, generate, calls

    def test_overrun_preserves_evidence_and_continues_without_reload(self):
        self.add_second_case()
        backend, generate, calls = self.backend_with_one_overrun()
        with patch.object(backend, 'generate', generate), patch.object(backend, 'clear_cache', autospec=True) as clear:
            session = Session(self.app, self.report, self.plan, backend)
            session.run()
        record = next(r for r in self.app.store.all() if r.get('reason') == 'context_capacity')
        self.assertEqual(record['status'], 'completed')
        self.assertFalse(record['measurement_valid'])
        self.assertFalse(record['valid_for_full_gpu_comparison'])
        self.assertFalse(record['score']['valid'])
        self.assertIsNone(record['score']['exact_match'])
        self.assertEqual(record['calls'][0]['text'], 'unfinished answer')
        self.assertEqual(record['calls'][0]['reasoning_text'], 'retained reasoning')
        self.assertEqual(record['calls'], record['partial']['calls'])
        self.assertEqual(record['outputs'], record['partial']['outputs'])
        self.assertEqual(record['step_events'], record['partial']['step_events'])
        self.assertEqual(record['context_capacity']['allocated_tokens'], 16384)
        self.assertEqual(record['context_capacity']['required_tokens'], 17000)
        self.assertEqual(record['context_capacity']['evidence']['input_tokens_verified'], 16000)
        self.assertEqual(record['context_cleanup']['status'], 'cleared')
        self.assertEqual(clear.call_count, 1)
        self.assertEqual(calls['large'], 2)
        self.assertEqual(len([e for e in self.events if e[0] == 'load' and e[1] == 'large']), 1)
        self.assertTrue(all(n == 0 for n in session.expansions.values()))
        self.assertFalse(any(r['status'] == 'skipped' for r in self.app.store.all()))
        self.assertEqual(pending_plan(self.models, [self.test], self.target, self.app.store)['pending'], 0)
        saved = self.app.store.path(record['model_id'], record['case_id']).read_bytes()
        with patch.object(backend, 'generate', side_effect=AssertionError('Terminal case reran')):
            Session(self.app, self.report, self.plan, backend).run()
        self.assertEqual(self.app.store.path(record['model_id'], record['case_id']).read_bytes(), saved)

    def test_input_overrun_without_response_does_not_invent_output(self):
        backend, generate, calls = self.backend_with_one_overrun(partial=False)
        with patch.object(backend, 'generate', generate), patch.object(backend, 'clear_cache'):
            Session(self.app, self.report, self.plan, backend).run()
        record = next(r for r in self.app.store.all() if r.get('reason') == 'context_capacity')
        self.assertEqual(record['calls'], [])
        self.assertEqual(record['outputs'], {})
        self.assertIsNone(record['score']['exact_match'])
        self.assertNotIn('format_compliance', record['score'])
        self.assertEqual(calls, {'large': 1, 'good': 1, 'small': 1})

    def test_review_overrun_preserves_initial_answer_and_partial_review(self):
        self.add_second_case()
        group = self.plan['groups'][0]
        group['jobs'][0]['variant']['retry_enabled'] = True
        backend = self.factory(lambda *a: None)
        original = backend.generate
        counts = {}
        def generate(model, *args, **kwargs):
            counts[model.mid] = counts.get(model.mid, 0) + 1
            if model.mid == 'large' and counts[model.mid] == 2:
                exc = ContextCapacity('Review history reached fixed capacity', 17000)
                exc.partial_response = {'text': 'unfinished review', 'finish_reason': 'length'}
                raise exc
            return original(model, *args, **kwargs)
        with patch.object(backend, 'generate', generate), patch.object(backend, 'clear_cache'):
            Session(self.app, self.report, self.plan, backend).run()
        record = next(r for r in self.app.store.all() if r.get('reason') == 'context_capacity')
        self.assertEqual(len(record['calls']), 2)
        self.assertEqual(record['calls'][0]['call_kind'], 'initial_answer')
        self.assertEqual(record['calls'][1]['call_kind'], 'self_review')
        self.assertEqual(record['calls'][1]['text'], 'unfinished review')
        self.assertTrue(record['calls'][1]['incomplete'])
        self.assertEqual(record['calls'][1]['messages'][-2]['content'], record['calls'][0]['text'])
        self.assertEqual(counts['large'], 3)
        self.assertIsNone(record['score']['exact_match'])

    def test_cleanup_failure_halts_without_skipping_or_reloading_remaining_cases(self):
        self.add_second_case()
        backend, generate, calls = self.backend_with_one_overrun()
        with patch.object(backend, 'generate', generate), patch.object(backend, 'clear_cache', side_effect=RuntimeError('cache unavailable')):
            with self.assertRaisesRegex(ContextCleanupFailure, 'later cases remain pending'):
                Session(self.app, self.report, self.plan, backend).run()
        records = self.app.store.all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['status'], 'completed')
        self.assertEqual(records[0]['context_cleanup'], {'status': 'failed', 'error': 'cache unavailable'})
        self.assertEqual(calls, {'large': 1})
        self.assertIsNone(self.app.backend)
        self.assertEqual(pending_plan(self.models, [self.test], self.target, self.app.store)['pending'], 2)

    def test_cancel_during_cleanup_keeps_terminal_evidence_and_stops(self):
        backend, generate, calls = self.backend_with_one_overrun()
        with patch.object(backend, 'generate', generate), patch.object(backend, 'clear_cache', side_effect=Cancelled('Stopped')):
            with self.assertRaises(Cancelled):
                Session(self.app, self.report, self.plan, backend).run()
        record = self.app.store.all()[0]
        self.assertEqual(record['status'], 'completed')
        self.assertEqual(record['context_cleanup']['status'], 'cancelled')
        self.assertEqual(calls, {'large': 1})
        self.assertIsNone(self.app.backend)

    def test_bulk_skip_stops_before_first_read_or_write(self):
        session = Session(self.app, self.report, self.plan, self.factory(lambda *a: None))
        group = self.plan['groups'][0]
        self.app.cancel_event.set()
        with patch.object(session, 'terminal') as terminal, patch.object(session, 'save') as save:
            with self.assertRaises(Cancelled):
                session.skip(group, group['jobs'], ContextCapacity('capacity'))
        terminal.assert_not_called()
        save.assert_not_called()
        self.assertEqual(self.app.store.all(), [])

    def test_bulk_skip_cancel_after_one_write_preserves_only_that_result(self):
        self.add_second_case()
        session = Session(self.app, self.report, self.plan, self.factory(lambda *a: None))
        group = self.plan['groups'][0]
        save = session.save
        def save_then_stop(record, *args):
            save(record, *args)
            self.app.cancel_event.set()
        with patch.object(session, 'save', side_effect=save_then_stop):
            with self.assertRaises(Cancelled):
                session.skip(group, group['jobs'], ContextCapacity('capacity'))
        records = self.app.store.all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['case_id'], group['jobs'][0]['case_id'])
        self.assertEqual(records[0]['status'], 'skipped')

    def test_bulk_skip_stop_checked_even_when_first_result_already_terminal(self):
        self.add_second_case()
        session = Session(self.app, self.report, self.plan, self.factory(lambda *a: None))
        group = self.plan['groups'][0]
        def terminal_then_stop(*args):
            self.app.cancel_event.set()
            return True
        with patch.object(session, 'terminal', side_effect=terminal_then_stop) as terminal:
            with self.assertRaises(Cancelled):
                session.skip(group, group['jobs'], ContextCapacity('capacity'))
        self.assertEqual(terminal.call_count, 1)
        self.assertEqual(self.app.store.all(), [])


if __name__ == '__main__':
    unittest.main()
