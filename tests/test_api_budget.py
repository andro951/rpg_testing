import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest
from decimal import Decimal
from workbench.api_budget import BudgetLedger, BudgetError, BudgetExceeded, Prices, _locked


def contender(path, queue, ident):
    ledger = BudgetLedger(path, '1', Prices('1', '.1', '1'))
    try:
        ledger.reserve(ident, 600000, 0)
        queue.put(True)
    except BudgetExceeded:
        queue.put(False)


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'budget.json'
        self.prices = Prices('2', '.1', '10')
        self.ledger = BudgetLedger(self.path, '1', self.prices)

    def test_exact_reservation_and_settlement(self):
        self.ledger.reserve('one', 10000, 10000)
        self.assertEqual(self.ledger.snapshot()['committed_usd'], '0.12')
        actual = self.ledger.settle('one', {'input_tokens': 1000, 'output_tokens': 200,
            'input_tokens_details': {'cached_tokens': 500},
            'output_tokens_details': {'reasoning_tokens': 100}})
        self.assertEqual(actual, Decimal('.00305'))
        self.assertEqual(self.ledger.snapshot()['committed_usd'], '0.00305')

    def test_chat_usage(self):
        self.ledger.reserve('one', 1000, 1000)
        self.assertEqual(self.ledger.settle('one', {'prompt_tokens': 100, 'completion_tokens': 10}), Decimal('.0003'))

    def test_cap_reopen_and_duplicates(self):
        self.ledger.reserve('one', 0, 90000)
        with self.assertRaises(BudgetExceeded): self.ledger.reserve('two', 0, 20000)
        reopened = BudgetLedger(self.path, '1', self.prices)
        with self.assertRaises(BudgetError): reopened.reserve('one', 0, 1)
        with self.assertRaises(BudgetError): BudgetLedger(self.path, '2', self.prices)
        with self.assertRaises(BudgetError): BudgetLedger(self.path, '1', Prices('3', '.1', '10'))

    def test_missing_usage_keeps_reservation(self):
        self.ledger.reserve('one', 100, 100)
        before = self.ledger.snapshot()['committed_usd']
        for usage in (None, {}, {'input_tokens': 1}, {'input_tokens': True, 'output_tokens': 1},
                      {'input_tokens': 2, 'output_tokens': 1, 'input_tokens_details': {'cached_tokens': 3}}):
            with self.assertRaises(BudgetError): self.ledger.settle('one', usage)
            self.assertEqual(self.ledger.snapshot()['committed_usd'], before)
            with self.assertRaises(BudgetError): self.ledger.reserve('blocked', 1, 1)

    def test_no_double_settle(self):
        self.ledger.reserve('one', 100, 100)
        self.ledger.settle('one', {'input_tokens': 1, 'output_tokens': 1})
        with self.assertRaises(BudgetError): self.ledger.settle('one', {'input_tokens': 1, 'output_tokens': 1})
        with self.assertRaises(BudgetError): self.ledger.settle('missing', {'input_tokens': 1, 'output_tokens': 1})

    def test_actual_overrun_recorded(self):
        self.ledger.reserve('one', 1, 1)
        with self.assertRaises(BudgetExceeded): self.ledger.settle('one', {'input_tokens': 0, 'output_tokens': 200000})
        self.assertEqual(Decimal(self.ledger.snapshot()['committed_usd']), Decimal('2'))
        with self.assertRaises(BudgetExceeded): self.ledger.reserve('two', 1, 1)

    def test_invalid_configuration_and_tokens(self):
        for cap in ('0', '-1', 'NaN', 'Infinity', 1.1, True):
            with self.assertRaises(ValueError): BudgetLedger(self.path, cap, self.prices)
        with self.assertRaises(ValueError): Prices('1', None, '1')
        for count in (-1, True, 1.5):
            with self.assertRaises(ValueError): self.ledger.reserve('invalid', count, 0)
        with self.assertRaises(ValueError): self.ledger.reserve('', 1, 1)

    def test_corruption_fails_closed(self):
        self.path.write_text('{bad')
        with self.assertRaises(BudgetError): self.ledger.reserve('one', 1, 1)

    def test_mixed_prices_and_explicit_upper_bound(self):
        path = Path(self.temp.name)/'mixed.json'
        ledger = BudgetLedger(path, '1')
        with self.assertRaises(ValueError): ledger.reserve('missing', 1, 1)
        ledger.reserve('sol', 1000, 1000, prices=self.prices, max_cost_usd='.1')
        ledger.reserve('luna', 1000, 1000, prices=Prices('.1', '.01', '.5'))
        self.assertEqual(Decimal(ledger.snapshot()['committed_usd']), Decimal('.1006'))
        self.assertEqual(ledger.settle('sol', {'input_tokens': 100, 'output_tokens': 10},
            prices=Prices('4', '.2', '15')), Decimal('.00055'))
        with self.assertRaises(ValueError): ledger.reserve('under', 1000, 1000, prices=self.prices, max_cost_usd='.001')

    def test_uncertain_call_blocks_until_metered(self):
        self.ledger.reserve('one', 100, 100)
        self.ledger.mark_unknown('one')
        with self.assertRaises(BudgetError): self.ledger.reserve('two', 1, 1)
        self.ledger.settle('one', {'input_tokens': 1, 'output_tokens': 1})
        self.ledger.reserve('two', 1, 1)

    def test_bound_violation_halts_even_with_remaining_budget(self):
        self.ledger.reserve('one', 1, 1)
        with self.assertRaises(BudgetExceeded):
            self.ledger.settle('one', {'input_tokens': 10, 'output_tokens': 10})
        with self.assertRaises(BudgetExceeded): self.ledger.reserve('two', 1, 1)

    @unittest.skipIf(__import__('os').name == 'nt', 'Windows same-process lock semantics differ')
    def test_lock_timeout_fails_closed(self):
        self.ledger.timeout = .03
        with _locked(self.ledger.lock_path, 1):
            with self.assertRaises(BudgetError): self.ledger.reserve('blocked', 1, 1)

    def test_cache_writes_replace_ordinary_input_cost(self):
        self.ledger.reserve('cache', 1000, 100, max_cost_usd='.01')
        usage = {'input_tokens': 1000, 'output_tokens': 100,
                 'input_tokens_details': {'cached_tokens': 100, 'cache_write_tokens': 500,
                    'cache_write_tokens_details': {'ttl_30m_tokens': 200, 'ttl_12h_tokens': 300}}}
        # ordinary400*.000002 + reads100*.0000001 + write30m200*.0000025
        # + write12h300*.000005 + output100*.00001 = .00381
        self.assertEqual(self.ledger.settle('cache', usage), Decimal('.00381'))

    def test_invalid_cache_write_evidence_blocks(self):
        self.ledger.reserve('cache', 1000, 100, max_cost_usd='.01')
        invalid = [
            {'cache_write_tokens': 20},
            {'cache_write_tokens': 20, 'cache_write_tokens_details': {'ttl_30m_tokens': 20}},
            {'cache_write_tokens': 20, 'cache_write_tokens_details': {'ttl_30m_tokens': 10, 'ttl_12h_tokens': 5}},
            {'cache_write_tokens': 0, 'cache_write_tokens_details': {'ttl_30m_tokens': 1, 'ttl_12h_tokens': 0}},
            {'cached_tokens': 990, 'cache_write_tokens': 20,
             'cache_write_tokens_details': {'ttl_30m_tokens': 20, 'ttl_12h_tokens': 0}},
            {'cache_write_tokens': -1},
        ]
        for details in invalid:
            with self.subTest(details=details):
                with self.assertRaises(BudgetError): self.ledger.settle('cache',
                    {'input_tokens': 1000, 'output_tokens': 1, 'input_tokens_details': details})
                with self.assertRaises(BudgetError): self.ledger.reserve('blocked', 1, 1)
        self.assertEqual(self.ledger.snapshot()['calls']['cache']['status'], 'uncertain')

    def test_concurrent_processes_cannot_overspend(self):
        path = str(Path(self.temp.name)/'parallel.json')
        ctx = multiprocessing.get_context('spawn')
        queue = ctx.Queue()
        children = [ctx.Process(target=contender, args=(path, queue, str(n))) for n in range(4)]
        for child in children: child.start()
        for child in children:
            child.join(20)
            self.assertEqual(child.exitcode, 0)
        self.assertEqual(sum(queue.get(timeout=2) for _ in children), 1)
        self.assertEqual(BudgetLedger(path, '1', Prices('1', '.1', '1')).snapshot()['committed_usd'], '0.6')


if __name__ == '__main__': unittest.main()
