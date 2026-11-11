"""Strict requested-format compliance, independent of intent and final-state scoring.

These format-specific validators restore the documented syntax checks, not the
retired decoders' recovery or state-dependent behavior. They never parse with
the intent grammar, execute operations, inspect data/oracles, or repair text.
"""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote_to_bytes

VERSION = 'strict-format-compliance-v1'
FORMATS = ('json_dot', 'json_slash', 'path_list', 'literal_line',
           'end_marked_line', 'typed_lines')
_COMPONENT = re.compile(r'(?:[A-Za-z0-9_-]|%[0-9A-Fa-f]{2})+')
_DECIMAL = re.compile(r'[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?')


def identity():
    source = Path(__file__).read_bytes().replace(b'\r\n', b'\n')
    return {'version': VERSION, 'fingerprint': hashlib.sha256(source).hexdigest(),
            'scope': 'format_only', 'affects_intent_verdict': False}


def _reject(message):
    raise ValueError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _reject('Duplicate JSON object field: ' + key)
        result[key] = value
    return result


def _json(text):
    # Decimal checks JSON syntax without imposing binary-float numeric limits.
    return json.loads(text, object_pairs_hook=_pairs, parse_float=Decimal, parse_int=Decimal,
                      parse_constant=lambda value: _reject('Non-JSON value: ' + value))


def _component(text):
    if text == '%_':
        return
    if not _COMPONENT.fullmatch(text):
        _reject('Path components require unquoted letters, digits, hyphens, underscores or %HH escapes')
    try:
        unquote_to_bytes(text).decode('utf-8', errors='strict')
    except UnicodeError:
        _reject('Path escapes must encode valid UTF-8')


def _dot(path):
    if not isinstance(path, str):
        _reject('A path must be a string')
    # The empty root path is not an empty component. Empty fields use %_.
    if path:
        for part in path.split('.'):
            _component(part)


def _list_path(path):
    if path:
        for part in path.split(','):
            _component(part.strip(' '))


def _slash(path, *, typed=False):
    if not isinstance(path, str):
        _reject('A path must be a string')
    if not path:
        if typed:
            _reject('Typed-line paths start with / and contain a nonempty part')
        return
    if not path.startswith('/') or (typed and any(c in path for c in '\r\n\u2028\u2029')):
        _reject('Expected an exact slash path')
    offset = 1
    decoder = json.JSONDecoder()
    while True:
        quoted = path[offset:offset + 1] == '"'
        if quoted:
            try:
                part, end = decoder.raw_decode(path, offset)
            except ValueError:
                _reject('Invalid quoted JSON path part')
            if not isinstance(part, str) or (end < len(path) and path[end] != '/'):
                _reject('A quoted path part must end before / or the end of the path')
        else:
            end = path.find('/', offset)
            if end < 0:
                end = len(path)
            part = path[offset:end]
            if re.search(r'~(?![01])', part):
                _reject('Unquoted slash parts require valid ~0/~1 escapes')
        if typed and not quoted and part.replace('~1', '/').replace('~0', '~') in ('__proto__', 'prototype', 'constructor'):
            _reject('Unsafe typed-line field name')
        if typed and not quoted and not part:
            _reject('Typed-line paths cannot contain empty parts')
        if end == len(path):
            return
        offset = end + 1


def _json_operations(raw, form):
    operations = _json(raw)
    if not isinstance(operations, list):
        _reject('Return one JSON array of operations')
    path_check = _dot if form == 'json_dot' else _slash
    for operation in operations:
        if not isinstance(operation, dict):
            _reject('Each operation must be a JSON object')
        verb = operation.get('op')
        if verb in ('replace', 'add'):
            fields = {'op', 'path', 'value'}
        elif verb == 'remove':
            fields = {'op', 'path'}
        elif verb in ('move', 'copy'):
            fields = {'op', 'from', 'path'}
        else:
            _reject('JSON op must be exactly replace, add, remove, move or copy')
        if set(operation) != fields:
            _reject('Missing or extra JSON operation fields')
        path_check(operation['path'])
        if 'from' in operation:
            path_check(operation['from'])
    return len(operations)


def _lines(raw, *, blank_records=False):
    if '\r' in raw.replace('\r\n', '') or '\u2028' in raw or '\u2029' in raw:
        _reject('Use LF or CRLF physical line endings')
    lines = raw.replace('\r\n', '\n').split('\n')
    if lines[-1] == '':
        lines.pop()  # A final line ending terminates a record, not a repair.
    if not blank_records and any(line == '' for line in lines):
        _reject('Each physical line must contain a complete operation')
    return lines


def _text(content, *, marked):
    if marked:
        if not content.endswith('|'):
            _reject('text: requires a final | end marker')
        content = content[:-1]
    elif content.endswith(' '):
        _reject('Literal-line trailing spaces must be written as \\s')
    allowed = {'\\', 'n', 'r', 't'} | (set() if marked else {'s', '"'})
    index = 0
    while index < len(content):
        if content[index] == '\\':
            index += 1
            if index == len(content) or content[index] not in allowed:
                _reject('Unsupported text escape')
        elif content[index] == '\t':
            _reject('Write tabs using \\t')
        index += 1


def _line_operations(raw, form):
    count = 0
    for line in _lines(raw):
        if form == 'path_list':
            transfer = re.fullmatch(r'(move|copy) \[([^\]]*)\] -> \[([^\]]*)\]', line)
            if transfer:
                _list_path(transfer[2]); _list_path(transfer[3])
            else:
                match = re.fullmatch(r'(set|append|remove) \[([^\]]*)\](?:: (.*))?', line)
                if not match:
                    _reject('Expected one exact path-list operation per line')
                _list_path(match[2])
                if match[1] == 'remove':
                    if match[3] is not None:
                        _reject('Remove has no value')
                elif match[3] is None:
                    _reject('Set and append require a JSON value')
                else:
                    _json(match[3])
        else:
            transfer = re.fullmatch(r'(move|copy) (\S+) -> (\S+)', line)
            removal = re.fullmatch(r'remove (\S+)', line)
            if transfer:
                _dot(transfer[2]); _dot(transfer[3])
            elif removal:
                _dot(removal[1])
            else:
                match = re.fullmatch(r'(set|append) (\S+): (text|json):(.*)', line)
                if not match:
                    _reject('Expected one exact literal-text operation per line')
                _dot(match[2])
                if match[3] == 'text':
                    _text(match[4], marked=form == 'end_marked_line')
                elif isinstance(_json(match[4]), str):
                    _reject('json: is only for non-string values; use text:')
        count += 1
    return count


def _typed_value(line, verb):
    match = re.fullmatch(r'(text|number|boolean|null|list|object):(?: (.*))?', line)
    if not match:
        _reject('Expected exactly one typed value line')
    kind, content = match.groups()
    if verb == 'change' and kind != 'number':
        _reject('change requires number:')
    if kind == 'number':
        if content is None or not _DECIMAL.fullmatch(content):
            _reject('number: requires a finite decimal without exponent notation')
    elif kind == 'boolean':
        if content not in ('true', 'false'):
            _reject('boolean: requires exactly true or false')
    elif kind == 'null':
        if content is not None:
            _reject('null: takes no following content')
    elif kind in ('list', 'object') and content is not None:
        expected = list if kind == 'list' else dict
        if type(_json(content)) is not expected:
            _reject(kind + ': requires a JSON ' + kind)
    # text is literal data, including quotes, backslashes and operation words.


def _typed_operations(raw):
    lines = _lines(raw, blank_records=True)
    index = count = 0
    while index < len(lines):
        if lines[index] == '':
            index += 1
            continue
        match = re.fullmatch(r'(set|append|remove|move|copy|change): (.*)', lines[index])
        if not match:
            _reject('Expected an exact typed-line operation header')
        verb, path = match.groups()
        _slash(path, typed=True)
        index += 1
        if verb in ('move', 'copy'):
            if index >= len(lines) or not lines[index].startswith('to: '):
                _reject('Transfer requires an immediately following to: path')
            _slash(lines[index][4:], typed=True)
            index += 1
        elif verb != 'remove':
            if index >= len(lines):
                _reject('Missing value line')
            _typed_value(lines[index], verb)
            index += 1
        count += 1
    return count


def validate(raw, output_format):
    """Return syntax compliance only. No initial state or expected answer accepted.

    Slash selector/property roles require state and are not guessed here. Missing
    fields, identity resolution, operation targets and final values are separate
    intent checks. No operation list or corrected response is returned.
    """
    result = {**identity(), 'output_format': output_format, 'compliant': None,
              'status': 'not_applicable', 'errors': []}
    if output_format == 'free_format':
        return {**result, 'reason': 'Free format prescribes no output syntax.'}
    if output_format not in FORMATS:
        return {**result, 'status': 'not_evaluated', 'errors': ['Unknown output format']}
    try:
        if not isinstance(raw, str) or not raw:
            _reject('A nonempty original textual response is required')
        if output_format in ('json_dot', 'json_slash'):
            count = _json_operations(raw, output_format)
        elif raw in ('none', 'none\n', 'none\r\n'):
            count = 0
        elif output_format == 'typed_lines':
            count = _typed_operations(raw)
        else:
            count = _line_operations(raw, output_format)
        if count == 0 and output_format not in ('json_dot', 'json_slash') and not raw.startswith('none'):
            _reject('Return exactly none for no change')
    except (ValueError, TypeError, RecursionError) as exc:
        return {**result, 'status': 'failed', 'compliant': False, 'errors': [str(exc)]}
    return {**result, 'status': 'passed', 'compliant': True, 'operation_count': count}
