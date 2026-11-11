"""Schema-aware host for intent parsing of the approved value-patch dialect.

Only raw text, initial state and its declared schema enter this adapter. Oracles,
benchmark scores and prompt generation are intentionally absent.
"""
from __future__ import annotations

import hashlib

from jsonschema.exceptions import ValidationError, SchemaError
from intent_parser import parse_intent
from intent_parser.json_contract import stringify
from intent_parser.patch import IntentError, assert_json, clone, equal
from workbench import value_paths
from workbench.scoring import apply as standard_apply


def encode_path(parts):
    if type(parts) is not list:
        raise IntentError('A parsed path must be a list of typed scalar parts')
    if any(type(part) in (dict, list) for part in parts):
        raise IntentError('Path selectors must be scalar')
    assert_json(parts)
    # Quote ALL string parts: object properties and array IDs share an unambiguous
    # encoding while preserving slashes, empty strings and scalar JSON types.
    return ''.join('/' + stringify(part) for part in parts)


def _contextual_operation(state, schema, operation):
    if 'semantic' not in operation:
        return operation
    if (operation.get('semantic') != 'literal_add' or operation.get('op') != 'append'
            or set(operation) != {'op', 'path', 'value', 'semantic'}):
        raise IntentError('Invalid literal add operation fields')
    target, _, _ = value_paths.resolve(state, schema, encode_path(operation['path']))
    # This selects intent only. The unchanged schema-aware lowerer enforces
    # existing-field/collection roles and rejects root or whole-element updates.
    return {'op': 'append' if isinstance(target, list) else 'update',
            'path': operation['path'], 'value': operation['value']}


def lower(state, schema, operation):
    operation = _contextual_operation(state, schema, operation)
    op = operation['op']
    if op not in ('update', 'append', 'remove', 'move', 'copy'):
        raise IntentError('Unsupported operation')
    allowed = {'op', 'from', 'to'} if op in ('move', 'copy') else (
        {'op', 'path'} if op == 'remove' else {'op', 'path', 'value'})
    if set(operation) != allowed:
        raise IntentError('Missing or unexpected operation fields')
    patch = {'op': {'update': 'replace', 'append': 'add'}.get(op, op)}
    if op in ('move', 'copy'):
        patch.update({'from': encode_path(operation['from']), 'path': encode_path(operation['to'])})
    else:
        patch['path'] = encode_path(operation['path'])
        if op != 'remove':
            patch['value'] = clone(operation['value'])
    concrete = value_paths.lower_operation(state, patch, schema)
    after = standard_apply(state, [concrete], 'json_patch')
    assert_json(after)
    value_paths.validate(after, schema)
    return concrete, after


def select_operation(state, schema, raw):
    """Use state/schema alone to choose exactly one valid interpretation."""
    if 'unlabeledPathValue' in raw:
        candidates = [{'op': raw['op'], **candidate,
                       **({'semantic': raw['semantic']} if 'semantic' in raw else {})}
                      for candidate in raw['unlabeledPathValue']]
    elif 'unlabeledPaths' in raw:
        first, second = raw['unlabeledPaths']
        candidates = [{'op': raw['op'], 'from': first, 'to': second},
                      {'op': raw['op'], 'from': second, 'to': first}]
    else:
        operation = _contextual_operation(state, schema, raw)
        concrete, after = lower(state, schema, operation)
        return operation, concrete, after
    valid = []
    for candidate in candidates:
        try:
            candidate = _contextual_operation(state, schema, candidate)
            concrete, after = lower(state, schema, candidate)
            if not any(equal(candidate, item[0]) for item in valid):
                valid.append((candidate, concrete, after))
        except (ValueError, KeyError, TypeError, ValidationError, SchemaError):
            pass
    if len(valid) != 1:
        raise IntentError('Unlabeled operation must have exactly one valid schema/state interpretation')
    return valid[0]


def replay_value_intent(text, initial_state, schema, options=None):
    """Return diagnostics, never a benchmark correctness score or partial mutation."""
    if type(text) is not str:
        raise IntentError('Expected textual output')
    result = {'rawOutput': text, 'rawSha256': hashlib.sha256(text.encode('utf-16-le', errors='surrogatepass').decode('utf-16-le', errors='replace').encode('utf-8')).hexdigest()}
    try:
        options = dict(options or {})
        options['pathSyntax'] = 'value_patch'
        state, schema = clone(initial_state), clone(schema)
        value_paths.validate(state, schema)
        parsed = parse_intent(text, options)
        assert_json(parsed)
        custom, standard = [], []
        for raw in parsed:
            operation, concrete, state = select_operation(state, schema, raw)
            custom.append(clone(operation))
            standard.append(concrete)
        # Output format is exclusive; finalState is diagnostic, not an oracle.
        result.update(accepted=True, patch=standard if options.get('json_patch') else custom,
                      finalState=state)
    except (ValueError, KeyError, TypeError, RecursionError, ValidationError, SchemaError) as exc:
        result.update(accepted=False, error=str(exc))
    return result
