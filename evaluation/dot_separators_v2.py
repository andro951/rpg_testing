"""Versioned offline dot separator validator; generation parsing is unchanged.

Only path/from fields are normalized. IDs and operation values are never rewritten.
"""
from __future__ import annotations
import copy
import json
import re
from urllib.parse import unquote_to_bytes
from workbench import value_paths

VERSION = 'dot-separators-v2'
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


def _resolve_strict(state, schema, path):
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


def _resolution_parts(path):
    """Keep explicit quoted/encoded component boundaries; allow literal text.

    Dots in unquoted, unencoded text can be structural or part of an identity.
    Percent escapes and JSON-quoted components retain their existing meaning.
    Empty raw pieces can participate in a literal dotted identity, but cannot
    select an empty identity by themselves (%_ or "" is still required).
    """
    if not isinstance(path, str):
        raise ValueError('A dot path must be a string')
    if not path:
        return []
    parts, offset = [], 0
    while True:
        explicit = False
        if path[offset:offset + 1] == '"':
            try:
                text, end = json.JSONDecoder().raw_decode(path, offset)
            except ValueError:
                pass  # It may be literal identity text, not quoted syntax.
            else:
                explicit = isinstance(text, str) and (end == len(path) or path[end] == '.')
        if not explicit:
            end = path.find('.', offset)
            if end == -1:
                end = len(path)
            raw = path[offset:end]
            explicit = '%' in raw
            if raw == '%_':
                text = ''
            else:
                if re.search(r'%(?![0-9A-Fa-f]{2})', raw):
                    raise ValueError('Invalid dot path component escape; use %HH UTF-8 escapes')
                try:
                    text = unquote_to_bytes(raw).decode('utf-8', errors='strict')
                except UnicodeError as exc:
                    raise ValueError('Dot path component escapes must encode valid UTF-8') from exc
        parts.append((text, explicit))
        if end == len(path):
            return parts
        offset = end + 1


def syntax_tokens(path):
    """Lexical validation for diagnostics; resolve() checks unique meaning."""
    return [text for text, _ in _resolution_parts(path)]


def resolve(state, schema, path):
    """Resolve literal separators only when exactly one state location matches.

    Never reinterpret a percent-decoded dot or a quoted component as structure.
    Never prefer a structural interpretation over a literal identity (or vice
    versa). Operation-role and schema validation still run after resolution.
    """
    parts = _resolution_parts(path)
    found = {}

    def walk(value, node, offset, concrete):
        if offset == len(parts):
            found[tuple(concrete)] = (value, node, concrete)
            return
        if not isinstance(value, (dict, list)):
            return
        identities = ([(scalar_text(value_paths.identity(element, node)), index, element)
                       for index, element in enumerate(value)] if isinstance(value, list) else [])
        longest = max((len(key) for key in value if key in node.get('properties', {})), default=0) if isinstance(value, dict) else max((len(key) for key, _, _ in identities), default=0)
        text = ''
        for end in range(offset, len(parts)):
            part, explicit = parts[end]
            if end > offset and explicit:
                break
            text = part if end == offset else text + '.' + part
            if len(text) > longest:
                break
            # A missing raw component is not an empty identity spelling.
            if text or end > offset or explicit:
                if isinstance(value, dict):
                    if text in value and text in node.get('properties', {}):
                        walk(value[text], node['properties'][text], end + 1, concrete + [text])
                else:
                    for identity, index, element in identities:
                        if identity == text:
                            walk(element, node['items'], end + 1, concrete + [str(index)])
                        if len(found) > 1:
                            return
            if len(found) > 1 or explicit:
                return

    walk(state, schema, 0, [])
    if len(found) > 1:
        raise ValueError('Ambiguous dot path: literal components and separators match multiple state locations; use %HH escapes or JSON-quoted components')
    if found:
        return next(iter(found.values()))
    # Preserve the established diagnostic for paths that still cannot resolve.
    return _resolve_strict(state, schema, path)


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
    if not isinstance(operation, dict):
        raise ValueError('Operation must be an object')
    normalized = copy.deepcopy(operation)
    # Resolve by actual schema/collection, then reuse the unchanged operation roles.
    fields = ('path', 'from') if normalized.get('op') in ('move', 'copy') else ('path',)
    for field in fields:
        if field in normalized:
            _, _, concrete = resolve(state, schema, normalized[field])
            normalized[field] = value_paths.from_pointer(state, schema, value_paths.pointer(concrete))
    return value_paths.lower_operation(state, normalized, schema)


def apply(initial, patch, schema):
    from workbench.scoring import apply as standard_apply
    if not isinstance(patch, list):
        raise ValueError('Expected an array of operations')
    doc = copy.deepcopy(initial)
    validate(doc, schema)
    for operation in patch:
        doc = standard_apply(doc, [lower_operation(doc, operation, schema)], 'json_patch')
        validate(doc, schema)
    return doc


def from_pointer(state, schema, path):
    from workbench.scoring import pointer, idx
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
