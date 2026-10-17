"""Native-interface test double; never evidence of model quality or GPU speed.

Only this simulated adapter learns the new static full-path fixtures. The real
inference backend, prompt interpreter, scoring, and case fingerprint stay intact.
"""
import contextlib
import copy
import json
import re
from .backends import DemoBackend
from .workflows import Cancelled

_LINE = re.compile(r'^([A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_0-9]+)*): ?(.*)$')


def _leaf(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        # This parser is deliberately limited to the synthetic demo fixtures.
        return re.sub(r'\\([nrt\\])', lambda m: {'n':'\n','r':'\r','t':'\t','\\':'\\'}[m[1]], text)


def _read_prefix(text):
    text = text.lstrip()
    if text.startswith(('{', '[')):
        value, end = json.JSONDecoder().raw_decode(text)
        return value, text[end:], False
    value = {}
    lines = text.splitlines(keepends=True)
    consumed = 0
    matched = False
    for line in lines:
        if not line.strip():
            consumed += len(line)
            continue
        match = _LINE.fullmatch(line.rstrip('\r\n'))
        if not match:
            break
        matched = True
        parts = match[1].split('.')
        parent = value
        for part in parts[:-1]:
            parent = parent.setdefault(part, {})
            if not isinstance(parent, dict):
                raise ValueError('Conflicting path in synthetic demo fixture')
        parent[parts[-1]] = _leaf(match[2])
        consumed += len(line)
    if not matched:
        raise ValueError('No synthetic state prefix')
    return value, text[consumed:], True


def _state_and_task(content):
    if '\nSOURCE\n' in content:
        source, task, flat = _read_prefix(content.split('\nSOURCE\n', 1)[1])
        return source, task, flat
    if 'Current State:\n' in content:
        state, tail, flat = _read_prefix(content.rsplit('Current State:\n', 1)[1])
    else:
        state, tail, flat = _read_prefix(content)
    event = ''
    task = tail.strip()
    if task.startswith('New Information:\n'):
        event_and_task = task[len('New Information:\n'):]
        event, separator, task = event_and_task.partition('\n\n')
        if not separator:
            task = ''
    return {'initial_state': state, 'new_information': event}, task, flat


def _ticket_index(state, ticket_id):
    tickets = state.get('tickets', {})
    entries = enumerate(tickets) if isinstance(tickets, list) else tickets.items()
    for index, item in entries:
        if isinstance(item, dict) and item.get('ticket_id') == ticket_id:
            return str(index)
    raise ValueError('Ticket not found in synthetic demo fixture: ' + ticket_id)


class DemoNative(DemoBackend):
    def __init__(self, settings=None, gpu=None, log=lambda *a: None):
        super().__init__(log)

    def load(self, model, context, cancel=None, layers='all', execution_class='full_gpu'):
        super().load(model, context, cancel)
        self.load_metadata.update(
            placement={'status': execution_class, 'gpu_layers': 33 if layers == 'all' else layers,
                       'total_layers': 33, 'cpu_layers': 0 if layers == 'all' else 33-layers},
            execution_class=execution_class)
        return self.load_metadata

    def generate(self, messages, settings, schema, cache='default', cancel=None):
        if cancel and cancel.is_set():
            raise Cancelled('Cancelled')
        users = [m['content'] for m in messages if m.get('role') == 'user']
        if not users:
            return super().generate(messages, settings, schema, cache, cancel)
        try:
            source, task, flat = _state_and_task(users[-1])
        except (ValueError, TypeError, KeyError):
            return super().generate(messages, settings, schema, cache, cancel)
        state = source.get('initial_state', {})
        is_lookup = ('ticket' in task.lower() and 'index' in task.lower()
                     and 'json patch' not in task.lower() and 'json pointer' not in task.lower())
        if is_lookup and isinstance(state, dict) and 'tickets' in state:
            event = source.get('new_information', '')
            ids = re.findall(r'SR-\d+', event + '\n' + task)
            ids = list(dict.fromkeys(ids))
            if 'insertion index' in task.lower() and 'new ticket' in task.lower() and len(ids) > 1:
                ids = ids[-1:]
            text = ', '.join(_ticket_index(state, ticket_id) for ticket_id in ids)
            if not text:
                raise ValueError('No target ticket in synthetic lookup question')
            self.counter += 1
            return {'text': text, 'finish_reason': 'stop', 'request_seconds': .02,
                    'first_token_seconds': .01, 'usage': {}, 'timings': {},
                    'cached_tokens': 1024 if cache == 'on' and self.counter > 1 else 0,
                    'simulated': True, 'raw_chunks': []}
        if not flat:
            return super().generate(messages, settings, schema, cache, cancel)
        # Translate only inside the test double. The real model still receives the
        # exact full-path prompt saved in the test definition.
        normalized = [copy.deepcopy(m) for m in messages if m.get('role') == 'system']
        normalized.append({'role': 'user', 'content': '\nSOURCE\n' + json.dumps(source, ensure_ascii=False)})
        normalized.extend(copy.deepcopy(m) for m in messages if m.get('role') == 'assistant')
        normalized.append({'role': 'user', 'content': task})
        return super().generate(normalized, settings, schema, cache, cancel)

    @contextlib.contextmanager
    def budget(self, seconds, terminate_process=True):
        yield
