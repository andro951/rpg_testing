"""State-aware intent conversion. Mirrors patch.cjs; no model calls or schema guesses."""
from __future__ import annotations

import json
from .json_contract import stringify
import math


class IntentError(ValueError):
    """The text, operation or current state does not have one safe interpretation."""


def assert_json(value, seen=None):
    if type(value) is str:
        index = 0
        while index < len(value):
            code = ord(value[index])
            if 0xD800 <= code <= 0xDBFF:
                if index + 1 == len(value) or not 0xDC00 <= ord(value[index + 1]) <= 0xDFFF:
                    raise IntentError('Unpaired Unicode surrogate')
                index += 1
            elif 0xDC00 <= code <= 0xDFFF:
                raise IntentError('Unpaired Unicode surrogate')
            index += 1
        return
    if value is None or type(value) is bool:
        return
    if type(value) in (int, float):
        if (type(value) is int and abs(value) > 9007199254740991) or (type(value) is float and (not math.isfinite(value) or (value.is_integer() and abs(value) > 9007199254740991))):
            raise IntentError('Nonfinite or unsafe JSON number')
        return
    if type(value) not in (dict, list):
        raise IntentError('Non-JSON value')
    seen = set() if seen is None else seen
    if id(value) in seen:
        raise IntentError('Cyclic JSON value')
    if type(value) is dict:
        for key in value:
            if type(key) is not str:
                raise IntentError('JSON object keys must be strings')
            assert_json(key)
    seen.add(id(value))
    for child in value.values() if type(value) is dict else value:
        assert_json(child, seen)
    seen.remove(id(value))


def clone(value):
    assert_json(value)
    return json.loads(stringify(value))


def equal(a, b):
    """JSON equality with distinct boolean, number and string identities."""
    if type(a) in (int, float) and type(b) in (int, float):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
    return a == b


def _property_key(value):
    if isinstance(value, str):
        return value
    if value is None:
        return 'null'
    if type(value) is bool:
        return 'true' if value else 'false'
    if type(value) in (int, float):
        if value == math.trunc(value):
            return str(int(value))
        text = str(value)
        if 'e' in text:
            coefficient, exponent = text.split('e')
            exp = int(exponent)
            if exp >= -6:
                from decimal import Decimal
                return format(Decimal(text), 'f')
            return coefficient + 'e' + ('+' if exp >= 0 else '-') + str(abs(exp))
        return text
    raise IntentError('Path must contain scalar JSON tokens')


def resolve(root, path, options=None):
    id_key = (options or {}).get('idKey', 'id')
    node, parent, key, pointer = root, None, None, []
    for segment in path:
        parent = node
        if type(node) is list:
            matches = [i for i, value in enumerate(node)
                       if (type(value) is dict and id_key in value and equal(value[id_key], segment))
                       or (type(value) not in (list, dict) and equal(value, segment))]
            if len(matches) != 1:
                raise IntentError('Array ID must resolve exactly once: ' + _property_key(segment))
            key = matches[0]
        elif type(node) is dict and _property_key(segment) in node:
            key = _property_key(segment)
        else:
            raise IntentError('Missing path segment: ' + _property_key(segment))
        pointer.append(str(key))
        node = node[key]
    return {'node': node, 'parent': parent, 'key': key, 'pointer': pointer}


def _ptr(parts):
    return '/' + '/'.join(s.replace('~', '~0').replace('/', '~1') for s in parts) if parts else ''


def _delete(resolved):
    if resolved['parent'] is None:
        raise IntentError('Root removal unsupported')
    del resolved['parent'][resolved['key']]


_NO_IDENTITY = object()


def _identity(value, id_key):
    if type(value) is dict:
        return value.get(id_key, _NO_IDENTITY)
    if type(value) is list:
        return _NO_IDENTITY
    return value


def _check_append(array, value, id_key, exclude=None):
    identity = _identity(value, id_key)
    if type(value) is dict and id_key in value and type(identity) in (dict, list):
        raise IntentError('Object identities must be scalar JSON values')
    if identity is not _NO_IDENTITY and any(
            i != exclude and _identity(v, id_key) is not _NO_IDENTITY
            and equal(_identity(v, id_key), identity) for i, v in enumerate(array)):
        raise IntentError('Operation would create ambiguous duplicate identity')


def _concrete(operation, state, options):
    operation = clone(operation)
    if 'unlabeledPathValue' in operation:
        valid = []
        for candidate in operation['unlabeledPathValue']:
            trial = {'op': operation['op'], **candidate}
            try:
                _execute(clone(state), trial, options)
                valid.append(trial)
            except (IntentError, KeyError, TypeError):
                pass
        if len(valid) != 1:
            raise IntentError('Unlabeled path/value must resolve uniquely')
        return valid[0]
    if 'unlabeledPaths' in operation:
        paths = operation['unlabeledPaths']
        a, b = resolve(state, paths[0], options), resolve(state, paths[1], options)
        if isinstance(a['node'], list) == isinstance(b['node'], list):
            raise IntentError('Unlabeled source/destination ambiguous')
        operation['from'], operation['to'] = reversed(paths) if isinstance(a['node'], list) else paths
        del operation['unlabeledPaths']
    return operation


def _execute(state, operation, options):
    id_key = options.get('idKey') or 'id'
    op = operation['op']
    if op in ('copy', 'move'):
        source, dest = resolve(state, operation['from'], options), resolve(state, operation['to'], options)
        if not isinstance(dest['node'], list):
            raise IntentError('Destination must be a collection')
        if source['parent'] is dest['node']:
            raise IntentError('Same-collection transfer unsupported')
        if len(operation['from']) <= len(operation['to']) and all(
                equal(a, b) for a, b in zip(operation['from'], operation['to'])):
            raise IntentError('Transfer into source or descendant unsupported')
        _check_append(dest['node'], source['node'], id_key)
        value = clone(source['node'])
        patch = [{'op': 'add', 'path': _ptr(dest['pointer']) + '/-', 'value': clone(value)}]
        dest['node'].append(value)
        if op == 'move':
            patch.append({'op': 'remove', 'path': _ptr(source['pointer'])})
            _delete(source)
        return patch
    resolved = resolve(state, operation['path'], options)
    if op == 'append':
        if not isinstance(resolved['node'], list):
            raise IntentError('Append target must be collection')
        _check_append(resolved['node'], operation['value'], id_key)
        resolved['node'].append(clone(operation['value']))
        return [{'op': 'add', 'path': _ptr(resolved['pointer']) + '/-', 'value': clone(operation['value'])}]
    if op == 'update':
        if resolved['parent'] is None:
            raise IntentError('Root replacement unsupported')
        value, parent, key = operation['value'], resolved['parent'], resolved['key']
        if key == id_key:
            owner = resolve(state, operation['path'][:-1], options)
            if isinstance(owner['parent'], list):
                if isinstance(value, (dict, list)):
                    raise IntentError('Object identities must be scalar JSON values')
                _check_append(owner['parent'], {id_key: value}, id_key, owner['key'])
        if isinstance(parent, list):
            _check_append(parent, value, id_key, key)
        parent[key] = clone(value)
        return [{'op': 'replace', 'path': _ptr(resolved['pointer']), 'value': clone(value)}]
    if op == 'remove':
        _delete(resolved)
        return [{'op': 'remove', 'path': _ptr(resolved['pointer'])}]
    raise IntentError('Unsupported operation')


def _validate_shape(operation):
    if type(operation) is not dict or operation.get('op') not in ('append', 'update', 'remove', 'copy', 'move'):
        raise IntentError('Invalid operation')
    two = operation['op'] in ('copy', 'move')
    allowed = ('op', 'from', 'to', 'unlabeledPaths') if two else (
        ('op', 'path') if operation['op'] == 'remove' else ('op', 'path', 'value', 'unlabeledPathValue'))
    if any(key not in allowed for key in operation):
        raise IntentError('Unexpected operation field')
    def is_path(value):
        return type(value) is list and all(x is None or type(x) in (str, int, float, bool) for x in value)
    for key in ('path', 'from', 'to'):
        if key in operation and not is_path(operation[key]):
            raise IntentError('Path must contain scalar JSON tokens')
    if two:
        if 'unlabeledPaths' in operation:
            paths = operation['unlabeledPaths']
            if type(paths) is not list or len(paths) != 2 or not all(is_path(p) for p in paths):
                raise IntentError('Invalid unlabeled paths')
        elif 'from' not in operation or 'to' not in operation:
            raise IntentError('Missing directional path')
    elif 'unlabeledPathValue' not in operation and (
            'path' not in operation or (operation['op'] != 'remove' and 'value' not in operation)):
        raise IntentError('Missing path/value')


def convert_intent(ir, document, options=None):
    options = options or {}
    if type(ir) is not list:
        raise IntentError('Operation list required')
    state, custom, standard = clone(document), [], []
    for raw in ir:
        _validate_shape(raw)
        operation = _concrete(raw, state, options)
        standard.extend(_execute(state, operation, options))
        custom.append(operation)
    return standard if options.get('json_patch', False) else custom


def apply_patch(document, patch, options=None):
    state, options = clone(document), options or {}
    for operation in patch:
        _validate_shape(operation)
        assert_json(operation)
        if 'unlabeledPaths' in operation or 'unlabeledPathValue' in operation:
            raise IntentError('Custom patch must have resolved roles')
        _execute(state, operation, options)
    return state
