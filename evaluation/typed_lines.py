"""Ordered typed-line extension for the current array-identities evaluator.

The published Ember reader and legacy schema-free host retain their contract.
"""
import math
import re

from intent_parser.patch import IntentError
from workbench.ember_text import DECIMAL, TYPED, typed as legacy_typed
from workbench.scoring import parse as parse_json
from workbench.value_paths import tokens

HEADER = re.compile(r'(set|append|change|remove|move|copy): (/[^\r\n\u2028\u2029]*)\Z')
DESTINATION = re.compile(r'to: (/[^\r\n\u2028\u2029]*)\Z')


def _path(path):
    parts = tokens(path)
    if not parts or any(not part for part in parts):
        raise IntentError('Invalid or unsafe typed-line path')
    return {'kind': 'slash', 'text': path}


def typed(value):
    """Reference encoder for the extended protocol, not prompt construction."""
    if isinstance(value, (dict, list)):
        import json
        return ('object: ' if isinstance(value, dict) else 'list: ') + json.dumps(value, ensure_ascii=False, allow_nan=False)
    return legacy_typed(value)


def records(raw):
    if not isinstance(raw, str):
        raise IntentError('Typed lines require plain text')
    if raw.strip() == 'none':
        return []
    lines = re.split(r'\r?\n', raw)
    result, index = [], 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        match = HEADER.fullmatch(lines[index])
        if not match:
            raise IntentError('Expected set, append, change, remove, move or copy and an exact /path')
        verb, path = match.groups()
        record = {'verb': verb, 'path': _path(path)}
        index += 1
        if verb in ('move', 'copy'):
            match = DESTINATION.fullmatch(lines[index]) if index < len(lines) else None
            if not match:
                raise IntentError('Move and Copy require one immediately following to: /destination line')
            record['from'] = record.pop('path')
            record['to'] = _path(match[1])
            result.append(record)
            index += 1
            continue
        if verb != 'remove':
            match = TYPED.fullmatch(lines[index]) if index < len(lines) else None
            if not match:
                raise IntentError('Expected exactly one typed value after ' + verb)
            kind, content = match.groups()
            if kind == 'text':
                value = content if content is not None else ''
            elif kind == 'number':
                if not content or not DECIMAL.fullmatch(content):
                    raise IntentError('Number must be a finite decimal without exponent notation')
                value = parse_json(content.lstrip('+'))
                if not math.isfinite(value):
                    raise IntentError('Number must be finite')
            elif kind == 'boolean':
                if content not in ('true', 'false'):
                    raise IntentError('Boolean must be true or false')
                value = content == 'true'
            elif kind == 'null':
                if content is not None and content.strip():
                    raise IntentError('null: takes no value')
                value = None
            else:
                expected = dict if kind == 'object' else list
                value = expected() if content is None or not content.strip() else parse_json(content)
                if type(value) is not expected:
                    raise IntentError(kind + ': requires a JSON ' + kind)
            if verb == 'change' and kind != 'number':
                raise IntentError('change requires number:')
            record['value'] = value
            index += 1
        result.append(record)
    if not result:
        raise IntentError('Return none for no change')
    return result


def _safe_reference(state, path, identity_context):
    from .array_identities_intent import _reference
    old, concrete = _reference(state, path, identity_context)
    node, parent = state, None
    for part in concrete:
        parent = node
        if isinstance(node, dict):
            if part in ('__proto__', 'prototype', 'constructor'):
                raise IntentError('Unsafe typed-line object field')
            node = node[part]
        else:
            node = node[int(part)]
    return old, parent


def decode(raw, initial, identity_context):
    from .array_identities_intent import _operation
    state, operations = initial, []
    for record in records(raw):
        verb = record['verb']
        if verb in ('move', 'copy'):
            for path in (record['from'], record['to']):
                _safe_reference(state, path, identity_context)
            op = {'op': verb, 'from': record['from'], 'to': record['to']}
            _, state = _operation(state, op, identity_context)
            operations.append(op)
            continue
        path = record['path']
        old, parent = _safe_reference(state, path, identity_context)
        op = {'op': 'append' if verb == 'append' else 'update', 'path': path}
        if verb == 'remove' and isinstance(parent, list):
            op['op'] = 'remove'
        else:
            value = None if verb == 'remove' else record['value']
            if verb in ('change', 'remove'):
                if not isinstance(parent, dict) or isinstance(old, (dict, list)) or isinstance(value, (dict, list)):
                    raise IntentError('Typed-line updates select existing scalar object fields')
            if verb == 'change':
                if type(old) not in (int, float) or not math.isfinite(old):
                    raise IntentError('Numeric change requires an existing finite number')
                value = old + value
                if not math.isfinite(value):
                    raise IntentError('Numeric change result must be finite')
            op['value'] = value
        _, state = _operation(state, op, identity_context)
        operations.append(op)
    return operations
