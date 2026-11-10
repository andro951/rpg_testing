"""Deterministic output readers for schema-free builds; no prompt/oracle input.

Each reader returns operation intent with lexical path provenance. Readers never
repair data values using expected answers. The generic intent grammar is used
only for JSON/intent arms; the independent text protocols retain their syntax.
"""
from __future__ import annotations
import re

from intent_parser.parse import parse_intent_with_diagnostics, path_tokens, unwrap_fence, WS
from intent_parser.patch import IntentError
from workbench.scoring import parse
from workbench.dot_paths import decode_part
from .live_intent import _decode_path


def _dot(path):
    return {'kind': 'dot', 'text': path}


def _slash_decoder(nodes, options):
    # Use the existing typed slash lexer (including embedded quoted slashes),
    # without interpreting an array selector as an RFC positional index.
    plain = {key: value for key, value in options.items() if key != '_host_path_decoder'}
    return {'kind': 'typed_components', 'parts': path_tokens(nodes, plain)}


def _intent(raw, slash=False):
    result = parse_intent_with_diagnostics(raw, {
        'pathSyntax': 'value_patch', '_host_path_decoder': _slash_decoder if slash else _decode_path,
        '_host_value_decoder': parse})
    if not result['operations']:
        unwrapped, _ = unwrap_fence(raw)
        if re.fullmatch('[' + WS + ']*\\[[' + WS + ']*\\][' + WS + ']*', unwrapped) is None:
            raise IntentError('No change requires an explicit empty array')
    return result


def _escape_text(text, marker):
    escapes = {'\\': '\\', 'n': '\n', 'r': '\r', 't': '\t'}
    if not marker:
        escapes.update({'s': ' ', '"': '"'})
    value, index = [], 0
    while index < len(text):
        if text[index] == '\\':
            index += 1
            if index == len(text) or text[index] not in escapes:
                raise IntentError('Unsupported text escape')
            value.append(escapes[text[index]])
        else:
            value.append(text[index])
        index += 1
    return ''.join(value)


def _line_records(raw, mode):
    if raw.strip() == 'none':
        return []
    records = []
    for line in re.split(r'\r?\n', raw):
        if not line.strip():
            continue
        if mode == 'path_list':
            match = re.fullmatch(r'(set|append|remove) \[([^\]]*)\](?:: (.*))?', line)
            if not match:
                raise IntentError('Expected one path-list operation per line')
            kind, path, content = match.groups()
            parts = [decode_part(part.strip()) for part in path.split(',')] if path else []
            reference = {'kind': 'components', 'parts': parts}
            value = parse(content) if content is not None else None
        else:
            match = re.fullmatch(r'(set|append) ([^:]+): (text|json):(.*)', line)
            if not match:
                removal = re.fullmatch(r'remove ([^:]+)', line)
                if not removal:
                    raise IntentError('Expected one literal-text operation per line')
                kind, reference, content, value = 'remove', _dot(removal[1]), None, None
            else:
                kind, path, label, content = match.groups()
                reference = _dot(path)
                if label == 'text':
                    if mode == 'end_marked_line':
                        if not content.endswith('|'):
                            raise IntentError('String values require a final pipe end marker')
                        content = content[:-1]
                    value = _escape_text(content, mode == 'end_marked_line')
                else:
                    value = parse(content)
                    if isinstance(value, str):
                        raise IntentError('json: is only for non-string values; use text: for strings')
        if kind == 'remove' and content is not None:
            raise IntentError('Remove has no value')
        if kind != 'remove' and content is None:
            raise IntentError('Set and append require a value')
        operation = {'op': {'set': 'update', 'append': 'append', 'remove': 'remove'}[kind], 'path': reference}
        if kind != 'remove':
            operation['value'] = value
        records.append(operation)
    if not records:
        raise IntentError('Return none for no change')
    return records


def _typed(raw, initial, identity_context=None):
    if identity_context is not None:
        from .typed_lines import decode as decode_typed
        return decode_typed(raw, initial, identity_context)
    from workbench.ember_text import parse as parse_typed
    from .schema_free_intent import _operation, _reference
    # Preserve the original typed-line subset and grouping/application order.
    records, operations, state = parse_typed(raw), [], initial
    for kind in ('s', 'd', 'a', 'r'):
        for record in records.get(kind, []):
            path = {'kind': 'object_components', 'parts': record['path']}
            old, _ = _reference(state, path)
            value = None if kind == 'd' else record['value']
            if kind == 'a':
                if isinstance(value, (dict, list)):
                    raise IntentError('Typed lines support primitive-value append only')
            else:
                if isinstance(old, (dict, list)) or isinstance(value, (dict, list)):
                    raise IntentError('Typed lines support scalar-field updates only')
                if kind == 'r':
                    if type(old) not in (int, float):
                        raise IntentError('Numeric change requires an existing number')
                    value = old + value
            operation = {'op': 'append' if kind == 'a' else 'update', 'path': path, 'value': value}
            _, state = _operation(state, operation)
            operations.append(operation)
    return operations


def decode(raw, output_format, initial_state, *, identity_context=None):
    if output_format in ('json_dot', 'json_slash'):
        return _intent(raw, slash=output_format == 'json_slash')
    if output_format == 'free_format':
        if raw.strip() == 'none':
            return {'operations': [], 'diagnostics': {'reader': 'explicit_none', 'semantic_inference': False}}
        # Free format prescribes no syntax. Recognized intent is executable;
        # prose outside the grammar is unassessed, not an invented patch.
        try:
            result = _intent(raw)
        except ValueError as exc:
            from .schema_free_intent import ParserGap
            raise ParserGap('Free-format response could not be normalized; prose semantic correctness is unknown: ' + str(exc)) from exc
        return result
    if output_format == 'typed_lines':
        operations = _typed(raw, initial_state, identity_context)
    elif output_format == 'two_line_text':
        from workbench.field_values import decode as decode_fields
        operations = [{**operation, 'op': {'replace': 'update', 'add': 'append', 'remove': 'remove'}[operation['op']],
                       'path': _dot(operation['path'])} for operation in decode_fields(raw)]
    else:
        operations = _line_records(raw, output_format)
    return {'operations': operations, 'diagnostics': {'reader': output_format, 'semantic_inference': False}}
