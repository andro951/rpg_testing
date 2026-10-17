"""dot_patch_v1: plain collection identities; strict slash value_patch is unchanged.

Only path/from fields are normalized. IDs and operation values are never rewritten.
"""
from __future__ import annotations
import copy
import json
import re
from urllib.parse import unquote_to_bytes
from . import value_paths

VERSION = 'dot_patch_v1'
_SAFE = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_')


def scalar_text(value):
    if isinstance(value, str):
        return value
    return value_paths.selector(value)


def encode_part(text):
    if not isinstance(text, str):
        raise ValueError('Dot path components must be text')
    if not text:
        return '%_'
    return ''.join(chr(b) if chr(b) in _SAFE else '%%%02X' % b for b in text.encode('utf-8'))


def decode_part(text):
    if text == '%_':
        return ''
    if not text or re.search(r'%(?![0-9A-Fa-f]{2})', text):
        raise ValueError('Invalid dot path component escape; use %HH UTF-8 escapes')
    if any(c not in _SAFE and c != '%' for c in re.sub(r'%[0-9A-Fa-f]{2}', '', text)):
        raise ValueError('Reserved characters in a dot path component must use %HH escapes')
    try:
        return unquote_to_bytes(text).decode('utf-8', errors='strict')
    except UnicodeError as exc:
        raise ValueError('Dot path component escapes must encode valid UTF-8') from exc


def tokens(path):
    """Accept plain components and a JSON-quoted component compatibility spelling."""
    if not isinstance(path, str):
        raise ValueError('A dot path must be a string')
    if not path:
        return []
    result, offset = [], 0
    while True:
        if path[offset:offset+1] == '"':
            try:
                part, end = json.JSONDecoder().raw_decode(path, offset)
            except ValueError as exc:
                raise ValueError('Invalid quoted dot path component') from exc
            if not isinstance(part, str) or (end < len(path) and path[end] != '.'):
                raise ValueError('A quoted component must end before a dot or the end')
        else:
            end = path.find('.', offset)
            if end == -1:
                end = len(path)
            part = decode_part(path[offset:end])
        result.append(part)
        if end == len(path):
            return result
        offset = end + 1
        if offset == len(path):
            raise ValueError('Empty dot path components must be written %_')


def normalize_path(path):
    return '.'.join(encode_part(part) for part in tokens(path))


def normalize_operation(operation):
    """Normalize paths only; deep-copy all values including quotes in data."""
    if not isinstance(operation, dict):
        raise ValueError('Operation must be an object')
    result = copy.deepcopy(operation)
    fields = ('path', 'from') if result.get('op') in ('move', 'copy') else ('path',)
    for field in fields:
        if field in result:
            result[field] = normalize_path(result[field])
    return result


def resolve(state, schema, path):
    concrete = []
    for part in tokens(path):
        if isinstance(state, dict):
            if part not in state or part not in schema.get('properties', {}):
                raise ValueError('Missing or undefined property: ' + part)
            state, schema = state[part], schema['properties'][part]
            concrete.append(part)
        elif isinstance(state, list):
            matches = [i for i, element in enumerate(state)
                       if scalar_text(value_paths.identity(element, schema)) == part]
            if len(matches) != 1:
                label = 'Ambiguous plain selector' if len(matches) > 1 else 'Plain selector'
                raise ValueError(f'{label} {part!r} must match exactly one element; found {len(matches)}')
            concrete.append(str(matches[0]))
            state, schema = state[matches[0]], schema['items']
        else:
            raise ValueError('Dot path continues through a scalar')
    return state, schema, concrete


def validate(state, schema):
    value_paths.validate(state, schema)
    def walk(value, node):
        if isinstance(value, dict):
            for field, child in value.items():
                walk(child, node['properties'][field])
        elif isinstance(value, list):
            keys = [scalar_text(value_paths.identity(element, node)) for element in value]
            if len(set(keys)) != len(keys):
                raise ValueError('Ambiguous plain selectors: different typed identities have the same text')
            for element in value:
                walk(element, node['items'])
    walk(state, schema)


def lower_operation(state, operation, schema):
    normalized = normalize_operation(operation)
    # Resolve by actual schema/collection, then reuse the unchanged operation roles.
    fields = ('path', 'from') if normalized.get('op') in ('move', 'copy') else ('path',)
    for field in fields:
        if field in normalized:
            _, _, concrete = resolve(state, schema, normalized[field])
            normalized[field] = value_paths.from_pointer(state, schema, value_paths.pointer(concrete))
    return value_paths.lower_operation(state, normalized, schema)


def apply(initial, patch, schema):
    from .scoring import apply as standard_apply
    if not isinstance(patch, list):
        raise ValueError('Expected an array of operations')
    doc = copy.deepcopy(initial)
    validate(doc, schema)
    for operation in patch:
        doc = standard_apply(doc, [lower_operation(doc, operation, schema)], 'json_patch')
        validate(doc, schema)
    return doc


def from_pointer(state, schema, path):
    from .scoring import pointer, idx
    parts = []
    for part in pointer(path):
        if isinstance(state, list):
            element = state[idx(part, len(state))]
            parts.append(encode_part(scalar_text(value_paths.identity(element, schema))))
            state, schema = element, schema['items']
        elif isinstance(state, dict):
            parts.append(encode_part(part))
            state, schema = state[part], schema['properties'][part]
        else:
            raise ValueError('Reference path continues through a scalar')
    return '.'.join(parts)


def full_paths(value, schema, path=''):
    lines = []
    if isinstance(value, list) and value:
        children = [(encode_part(scalar_text(value_paths.identity(e, schema))), e, schema['items']) for e in value]
    elif isinstance(value, dict) and value:
        children = [(encode_part(k), v, schema['properties'][k]) for k, v in value.items()]
    else:
        return [path + ':' + json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))]
    for part, child, node in children:
        lines.extend(full_paths(child, node, path + '.' + part if path else part))
    return lines
