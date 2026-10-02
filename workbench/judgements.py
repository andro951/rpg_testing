"""Manual test review, independent of execution identity and immutable results."""
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import wraps
import copy
import os
from pathlib import Path
import threading
from .domain import digest, experiment_spec, load_tests as raw_load_tests, read_json, write_json

STATUSES = ('rejected', 'needs_review', 'accepted')
_active = threading.local()


def definition_id(test, variant):
    return digest(experiment_spec(test, variant))


@contextmanager
def review_lock(root):
    """Prevent judgement changes during a run; OS locks are released on process exit."""
    root = Path(root).resolve()
    held = getattr(_active, 'roots', set())
    if root in held:
        yield
        return
    path = root / '.local' / 'test-review.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError('A benchmark run or judgement update is active. Finish it before changing judgements or starting another run.') from exc
        _active.roots = held | {root}
        try:
            yield
        finally:
            _active.roots = held
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def guarded_run(function):
    @wraps(function)
    def guarded(app, *args, **kwargs):
        with review_lock(app.root):
            return function(app, *args, **kwargs)
    return guarded


class JudgementStore:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / 'test_judgements.json'

    def read(self):
        if not self.path.exists():
            return {'version': 1, 'entries': {}}
        data = read_json(self.path)
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('entries'), dict):
            raise ValueError('Invalid test judgement catalog; runs are blocked until it is repaired.')
        for key, entry in data['entries'].items():
            if (len(key) != 64 or any(c not in '0123456789abcdef' for c in key) or
                    not isinstance(entry, dict) or entry.get('status') not in STATUSES or
                    type(entry.get('blocked')) is not bool or not isinstance(entry.get('history', []), list)):
                raise ValueError('Invalid test judgement entry')
            if entry['blocked'] != (entry['status'] == 'rejected'):
                raise ValueError('A rejected definition cannot be reinstated')
        return data

    def update(self, ids, status, reason, reviewer, note=''):
        if status not in STATUSES or not isinstance(ids, list) or not ids or len(ids) > 1000:
            raise ValueError('Select test definitions and a valid judgement')
        if not all(isinstance(key, str) and len(key) == 64 and all(c in '0123456789abcdef' for c in key) for key in ids):
            raise ValueError('Invalid definition ID')
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 200:
            raise ValueError('A judgement reason is required')
        if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 80 or not isinstance(note, str) or len(note) > 4000:
            raise ValueError('Enter a reviewer and a note of at most 4,000 characters')
        with review_lock(self.root):
            data = self.read()
            if any(data['entries'].get(key, {}).get('blocked') and status != 'rejected' for key in ids):
                raise ValueError('Rejected definitions are permanently blocked. Create an edited version, which starts in Needs review.')
            event = {'status': status, 'reason': reason.strip(), 'reviewer': reviewer.strip(), 'note': note,
                     'at': datetime.now(timezone.utc).isoformat()}
            for key in set(ids):
                previous = data['entries'].get(key, {})
                data['entries'][key] = {**event, 'blocked': status == 'rejected',
                                       'history': previous.get('history', []) + [event]}
            write_json(self.path, data)
            return data


def load_tests(folder):
    tests = copy.deepcopy(raw_load_tests(folder))
    entries = JudgementStore(Path(folder).parent).read()['entries']
    for test in tests:
        for variant in test['variants']:
            if entries.get(definition_id(test, variant), {}).get('blocked'):
                variant['enabled'] = False
    return [test for test in tests if any(variant.get('enabled', True) for variant in test['variants'])]


def annotate(matrix, data):
    for row in matrix['rows']:
        entry = data['entries'].get(row['definition_id'], {})
        row['judgement'] = copy.deepcopy(entry) if entry else {'status': 'needs_review', 'blocked': False}
    return matrix
