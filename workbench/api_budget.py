"""Durable, fail-closed API spending reservations. No network calls.

Callers must reserve an independently justified upper bound before each request.
An interrupted or unmetered request keeps its full reservation indefinitely.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import tempfile
import time


class BudgetError(RuntimeError):
    pass


class BudgetExceeded(BudgetError):
    pass


def _money(value):
    if isinstance(value, (float, bool)):
        raise ValueError('Use an exact decimal string, integer, or Decimal')
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError('Invalid monetary amount') from exc
    if not number.is_finite() or number < 0:
        raise ValueError('Amounts must be finite and nonnegative')
    return number


def _tokens(value):
    if type(value) is not int or value < 0:
        raise ValueError('Token counts must be nonnegative integers')
    return value


@dataclass(frozen=True)
class Prices:
    input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal

    def __post_init__(self):
        for key in self.__dataclass_fields__:
            object.__setattr__(self, key, _money(getattr(self, key)))

    def as_dict(self):
        return {key: str(getattr(self, key)) for key in self.__dataclass_fields__}

    def cost(self, input_tokens, output_tokens, cached_input_tokens=0, write_30m_tokens=0, write_12h_tokens=0):
        inputs, outputs, cached = map(_tokens, (input_tokens, output_tokens, cached_input_tokens))
        writes30, writes12 = map(_tokens, (write_30m_tokens, write_12h_tokens))
        if cached+writes30+writes12 > inputs:
            raise ValueError('Cached reads and writes cannot exceed total input tokens')
        return ((inputs-cached-writes30-writes12)*self.input_per_million
                + cached*self.cached_input_per_million
                + writes30*self.input_per_million*Decimal('1.25')
                + writes12*self.input_per_million*Decimal('2.5')
                + outputs*self.output_per_million) / Decimal(1000000)


@contextmanager
def _locked(path, timeout):
    # Never unlink this file: all processes must continue locking the same inode.
    with open(path, 'a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b'0'); handle.flush()
            def lock():
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            def unlock():
                handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            def lock():
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            def unlock():
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        started = time.monotonic()
        while True:
            try:
                lock(); break
            except (BlockingIOError, OSError) as exc:
                if time.monotonic()-started >= timeout:
                    raise BudgetError('Budget ledger lock unavailable') from exc
                time.sleep(.02)
        try:
            yield
        finally:
            unlock()


class BudgetLedger:
    """One explicit currency-USD cap, exact price schedule, and durable journal.

    Neither cap nor default prices can silently change when reopening a ledger. Create
    distinct ledgers only for independently approved budgets, not to evade a cap.
    """
    def __init__(self, path, cap_usd, prices: Prices | None = None, lock_timeout=10):
        self.path = Path(path)
        self.cap = _money(cap_usd)
        if self.cap <= 0 or (prices is not None and not isinstance(prices, Prices)):
            raise ValueError('An explicit positive cap and explicit Prices are required')
        self.prices = prices
        if not isinstance(lock_timeout, (int, float)) or lock_timeout <= 0:
            raise ValueError('Positive lock timeout required')
        self.timeout = lock_timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_name(self.path.name+'.lock')
        with _locked(self.lock_path, self.timeout):
            if self.path.exists():
                self._read()
            else:
                self._write({'version': 1, 'currency': 'USD', 'cap_usd': str(self.cap),
                             'prices': prices.as_dict() if prices is not None else None, 'calls': {}})

    def _read(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if (data['version'] != 1 or data['currency'] != 'USD'
                    or _money(data['cap_usd']) != self.cap
                    or data['prices'] != (self.prices.as_dict() if self.prices is not None else None)
                    or not isinstance(data['calls'], dict)):
                raise ValueError('Ledger identity mismatch')
            for call_id, row in data['calls'].items():
                if not isinstance(call_id, str) or not call_id or row['status'] not in ('reserved', 'uncertain', 'settled'):
                    raise ValueError('Invalid call record')
                _money(row['reserved_usd'])
                if row['status'] == 'settled':
                    _money(row['actual_usd'])
            return data
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise BudgetError('Unreadable, corrupt, or incompatible budget ledger; refusing requests') from exc

    def _write(self, data):
        fd, name = tempfile.mkstemp(prefix=self.path.name+'.', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(data, handle, sort_keys=True, indent=2)
                handle.flush(); os.fsync(handle.fileno())
            os.replace(name, self.path)
            if os.name != 'nt':
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def _committed(data):
        return sum((_money(row['actual_usd'] if row['status']=='settled' else row['reserved_usd'])
                    for row in data['calls'].values()), Decimal(0))

    def reserve(self, call_id, max_input_tokens, max_output_tokens, prices=None, max_cost_usd=None):
        if not isinstance(call_id, str) or not call_id.strip():
            raise ValueError('Nonempty unique call ID required')
        _tokens(max_input_tokens); _tokens(max_output_tokens)
        prices = prices or self.prices
        if not isinstance(prices, Prices):
            raise ValueError('Explicit per-call prices are required')
        # Use the more expensive input class even for unusual price schedules.
        input_rate = max(prices.input_per_million, prices.cached_input_per_million)
        amount = (max_input_tokens*input_rate + max_output_tokens*prices.output_per_million)/Decimal(1000000)
        if max_cost_usd is not None:
            upper = _money(max_cost_usd)
            if upper < amount:
                raise ValueError('Explicit upper bound cannot be below token/rate bound')
            amount = upper
        with _locked(self.lock_path, self.timeout):
            data = self._read()
            if data.get('halt_reason'):
                raise BudgetExceeded('Ledger halted after a violated spending bound; review required')
            if any(row['status']=='uncertain' for row in data['calls'].values()):
                raise BudgetError('Uncertain previous charges require reconciliation before new requests')
            if call_id in data['calls']:
                raise BudgetError('Call ID already reserved or settled; never resend automatically')
            if self._committed(data)+amount > self.cap:
                raise BudgetExceeded('Insufficient budget for worst-case request reservation')
            row = {'status': 'reserved', 'reserved_usd': str(amount),
                   'max_input_tokens': max_input_tokens, 'max_output_tokens': max_output_tokens,
                   'prices': prices.as_dict()}
            data['calls'][call_id] = row
            self._write(data)
            return dict(row)

    def mark_unknown(self, call_id, reason='Request outcome or usage unknown'):
        with _locked(self.lock_path, self.timeout):
            data = self._read()
            row = data['calls'].get(call_id)
            if row is None or row['status'] == 'settled':
                raise BudgetError('Unknown or settled call cannot become uncertain')
            row.update(status='uncertain', uncertainty_reason=str(reason))
            self._write(data)

    def settle(self, call_id, usage, prices=None):
        """Record provider totals; output total already includes reasoning tokens.

        Missing/invalid usage keeps the reservation and blocks future calls. A
        later complete usage record may reconcile an uncertain call. Per-call
        price override supports documented long-context rates, not tier guessing.
        """
        with _locked(self.lock_path, self.timeout):
            data = self._read()
            row = data['calls'].get(call_id)
            if row is None or row['status'] not in ('reserved', 'uncertain'):
                raise BudgetError('Unknown or already settled call')
            try:
                actual_prices = prices or Prices(**row['prices'])
                if not isinstance(actual_prices, Prices) or not isinstance(usage, dict):
                    raise ValueError('Usage and explicit prices required')
                if 'input_tokens' in usage:
                    inputs, outputs = usage['input_tokens'], usage['output_tokens']
                    details = usage.get('input_tokens_details') or {}
                else:
                    inputs, outputs = usage['prompt_tokens'], usage['completion_tokens']
                    details = usage.get('prompt_tokens_details') or {}
                cached = details.get('cached_tokens', 0)
                writes = _tokens(details.get('cache_write_tokens', 0))
                split = details.get('cache_write_tokens_details') or {}
                if writes and not all(key in split for key in ('ttl_30m_tokens', 'ttl_12h_tokens')):
                    raise ValueError('Cache write tokens require complete observed TTL allocation')
                writes30 = _tokens(split.get('ttl_30m_tokens', 0))
                writes12 = _tokens(split.get('ttl_12h_tokens', 0))
                if writes30+writes12 != writes:
                    raise ValueError('Cache write TTL allocation does not match total writes')
                actual = actual_prices.cost(inputs, outputs, cached, writes30, writes12)
                # Ensure usage can be durably recorded before mutating the row.
                json.dumps(usage, allow_nan=False)
            except (KeyError, ValueError, TypeError, AttributeError) as exc:
                row.update(status='uncertain', uncertainty_reason='Incomplete or invalid provider usage')
                self._write(data)
                raise BudgetError('Incomplete/invalid usage; reservation retained and future requests blocked') from exc
            exceeded = actual > _money(row['reserved_usd'])
            row.update(status='settled', actual_usd=str(actual), usage=usage,
                       actual_prices=actual_prices.as_dict())
            row.pop('uncertainty_reason', None)
            if exceeded:
                data['halt_reason'] = 'Actual request cost exceeded reserved upper bound'
            self._write(data)
            if exceeded or self._committed(data) > self.cap:
                raise BudgetExceeded('Actual cost exceeded reservation; charges recorded, stop execution')
            return actual

    def snapshot(self):
        with _locked(self.lock_path, self.timeout):
            data = self._read()
            committed = self._committed(data)
            return {**data, 'committed_usd': str(committed), 'available_usd': str(self.cap-committed)}
