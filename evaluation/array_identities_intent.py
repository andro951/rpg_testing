"""Validator-only collection identity metadata; no types, values or prompt input.

Paths use exact property strings and None for an array-element template.
A null id_field selects primitive elements by their own values.
The v1 inference evaluator remains separate for historical test definitions.
"""
from __future__ import annotations

import copy
import hashlib
import platform
from pathlib import Path

from intent_parser.patch import IntentError, assert_json
from workbench import dot_paths, value_paths
from workbench.domain import canonical, digest
from workbench.scoring import apply as apply_rfc, at, changes, equal, parse
from .dot_separators_v2 import _resolution_parts

from .schema_free_intent import ParserGap


VERSION = 'array-identities-intent-v2'
OUTPUT_FORMATS = ('json_dot', 'json_slash', 'path_list', 'literal_line',
                  'end_marked_line', 'two_line_text', 'typed_lines', 'free_format')
SOURCES = ('evaluation/array_identities_intent.py', 'evaluation/array_identity_map.py', 'evaluation/typed_lines.py', 'evaluation/schema_free_intent.py', 'evaluation/output_formats.py',
           'evaluation/hosts.py', 'evaluation/live_intent.py', 'evaluation/dot_separators_v2.py',
           'intent_parser/parse.py', 'intent_parser/patch.py', 'intent_parser/json_contract.py',
           'intent_parser/grammar-spec.json', 'workbench/domain.py', 'workbench/workflows.py',
           'workbench/scoring.py', 'workbench/dot_paths.py', 'workbench/value_paths.py',
           'workbench/field_values.py', 'workbench/ember_text.py')
encode_part = dot_paths.encode_part
scalar_text = dot_paths.scalar_text


def identity_info():
    root = Path(__file__).resolve().parents[1]
    data = {'version': VERSION,
            'source_hashes': {name: hashlib.sha256((root / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                              for name in SOURCES}}
    # Runtime version is saved provenance, not a cross-host source-compatibility gate.
    return {**data, 'python_version': platform.python_version(), 'fingerprint': digest(data)}


def configuration():
    info = identity_info()
    return {'version': VERSION, 'fingerprint': info['fingerprint']}


from .array_identity_map import IdentityMap


def _context(array_identities):
    return array_identities if isinstance(array_identities, IdentityMap) else IdentityMap(array_identities)


def id_field(array, array_identities, path=()):
    return _context(array_identities).field(array, tuple(path))


def identity(element, array, array_identities, path=()):
    key = id_field(array, array_identities, path)
    return element[key] if key is not None else element


def validate_data(state, array_identities):
    _context(array_identities).validate(state)


def _components(state, parts, array_identities, *, typed=False, slash=False):
    concrete = []
    template = ()
    for part in parts:
        if isinstance(state, dict):
            key = value_paths.property_name(part) if slash else scalar_text(part)
            if key not in state:
                raise IntentError('Missing existing field: ' + key)
        elif isinstance(state, list):
            wanted = parse(part) if slash else part
            key_field = id_field(state, array_identities, template)
            matches = [index for index, element in enumerate(state)
                       if (equal(element[key_field] if key_field is not None else element, wanted) if typed or slash else
                           scalar_text(element[key_field] if key_field is not None else element) == scalar_text(wanted))]
            if len(matches) != 1:
                raise IntentError('Array ID must match exactly one element; no positional selectors')
            key = matches[0]
        else:
            raise IntentError('Path continues through a scalar')
        template += (None if isinstance(state, list) else key,)
        concrete.append(str(key))
        state = state[key]
    return state, concrete


def resolve(state, path, array_identities):
    """Resolve dot separators only if there is exactly one state interpretation."""
    array_identities = _context(array_identities)
    parts = _resolution_parts(path)
    found = {}
    def walk(value, offset, concrete, template):
        if offset == len(parts):
            found[tuple(concrete)] = (value, concrete)
            return
        if isinstance(value, dict):
            choices = [(key, key, child) for key, child in value.items()]
        elif isinstance(value, list):
            field = id_field(value, array_identities, template)
            choices = [(scalar_text(child[field] if field is not None else child), str(i), child)
                       for i, child in enumerate(value)]
        else:
            return
        text = ''
        longest = max((len(key) for key, _, _ in choices), default=0)
        for end in range(offset, len(parts)):
            part, explicit = parts[end]
            if end > offset and explicit:
                break
            text = part if end == offset else text + '.' + part
            if len(text) > longest:
                break
            if text or end > offset or explicit:
                for name, key, child in choices:
                    if name == text:
                        walk(child, end + 1, concrete + [key], template + (None if isinstance(value, list) else key,))
                    if len(found) > 1:
                        return
            if explicit:
                break
    walk(state, 0, [], ())
    if len(found) > 1:
        raise IntentError('Ambiguous dot path; use percent escapes or explicit components')
    if not found:
        raise IntentError('Path must resolve to an existing field or unique ID; no positional selectors')
    return next(iter(found.values()))


def from_pointer(state, parts, array_identities):
    """Encode concrete parts (internal only) as canonical ID-based dot paths."""
    if isinstance(parts, str):
        from workbench.scoring import pointer
        parts = pointer(parts)
    encoded = []
    template = ()
    for part in parts:
        if isinstance(state, list):
            element = state[int(part)]
            encoded.append(encode_part(scalar_text(identity(element, state, array_identities, template))))
            template += (None,)
            state = element
        else:
            encoded.append(encode_part(part))
            template += (part,)
            state = state[part]
    return '.'.join(encoded)


def _reference(state, reference, array_identities):
    kind = reference.get('kind') if isinstance(reference, dict) else None
    if kind == 'dot':
        return resolve(state, reference['text'], array_identities)
    if kind == 'components':
        return _components(state, reference['parts'], array_identities)
    if kind == 'typed_components':
        return _components(state, reference['parts'], array_identities, typed=True)
    if kind == 'slash':
        return _components(state, value_paths.tokens(reference['text']), array_identities, slash=True)
    if kind == 'object_components':
        value = state
        for part in reference['parts']:
            if not isinstance(value, dict) or part not in value:
                raise IntentError('Typed lines support existing object-field paths only, not array-element selection')
            value = value[part]
        return value, reference['parts']
    raise IntentError('Missing lexical path provenance')


def _operation(state, raw, array_identities):
    op = raw.get('op')
    if op in ('move', 'copy'):
        if set(raw) != {'op', 'from', 'to'}:
            raise IntentError('Move and Copy require only source and destination paths')
        source, source_parts = _reference(state, raw['from'], array_identities)
        destination, destination_parts = _reference(state, raw['to'], array_identities)
        parent = at(state, source_parts[:-1]) if source_parts else None
        if not isinstance(parent, list):
            raise IntentError('Move and Copy select one existing source array element')
        if not isinstance(destination, list):
            raise IntentError('Move and Copy destination selects an existing array itself')
        if parent is destination:
            raise IntentError('Same-collection transfer unsupported')
        if destination_parts[:len(source_parts)] == source_parts:
            raise IntentError('Transfer into source or descendant unsupported')
        normalized = {'op': op, 'from': from_pointer(state, source_parts, array_identities),
                      'path': from_pointer(state, destination_parts, array_identities)}
        # These are custom collection transfers, not RFC move/copy. Append the
        # complete independent value first, so removal cannot shift a nested
        # destination's concrete index before it has been used.
        concrete = [{'op': 'add', 'path': value_paths.pointer(destination_parts) + '/-',
                     'value': copy.deepcopy(source)}]
        if op == 'move':
            concrete.append({'op': 'remove', 'path': value_paths.pointer(source_parts)})
        after = apply_rfc(state, concrete, 'json_patch')
        _context(array_identities).validate(after, check_paths=False)
        return normalized, after
    if op not in ('update', 'append', 'remove'):
        raise IntentError('Only Update, Add, Remove, Move and Copy are supported')
    fields = {'op', 'path'} if op == 'remove' else {'op', 'path', 'value'}
    if set(raw) != fields:
        raise IntentError('Missing or extra operation fields')
    target, parts = _reference(state, raw['path'], array_identities)
    parent = at(state, parts[:-1]) if parts else None
    if op == 'append':
        if not isinstance(target, list):
            raise IntentError('Add selects an existing array itself')
        pointer = value_paths.pointer(parts) + '/-'
    elif op == 'remove':
        if not isinstance(parent, list):
            raise IntentError('Remove selects one existing array element')
        pointer = value_paths.pointer(parts)
    else:
        if not isinstance(parent, dict) or isinstance(target, list):
            raise IntentError('Update selects an existing object field, not a collection or whole array element')
        pointer = value_paths.pointer(parts)
    normalized = {'op': {'update': 'replace', 'append': 'add', 'remove': 'remove'}[op],
                  'path': from_pointer(state, parts, array_identities)}
    if op != 'remove':
        normalized['value'] = copy.deepcopy(raw['value'])
    concrete = {**normalized, 'path': pointer}
    after = apply_rfc(state, [concrete], 'json_patch')
    _context(array_identities).validate(after, check_paths=False)
    return normalized, after


def _choose(state, raw, array_identities):
    if 'unlabeledPaths' in raw:
        if set(raw) != {'op', 'unlabeledPaths'} or raw.get('op') not in ('move', 'copy'):
            raise IntentError('Unlabeled source/destination requires Move or Copy')
        paths = raw['unlabeledPaths']
        if not isinstance(paths, list) or len(paths) != 2:
            raise IntentError('Two unlabeled paths required')
        candidates = []
        for source, destination in (paths, paths[::-1]):
            try:
                candidates.append(_operation(state, {'op': raw['op'], 'from': source,
                                                      'to': destination}, array_identities))
            except (ValueError, KeyError, TypeError):
                continue
        if len(candidates) != 1:
            raise IntentError('Unlabeled source/destination requires exactly one current-data interpretation')
        return candidates[0]
    if 'unlabeledPathValue' not in raw:
        return _operation(state, raw, array_identities)
    candidates = []
    for candidate in raw['unlabeledPathValue']:
        try:
            result = _operation(state, {'op': raw['op'], **candidate}, array_identities)
            if not any(equal(result[0], prior[0]) for prior in candidates):
                candidates.append(result)
        except (ValueError, KeyError, TypeError):
            continue
    if len(candidates) != 1:
        raise IntentError('Unlabeled path/value requires exactly one current-data interpretation')
    return candidates[0]


def apply_patch(initial_state, patch, array_identities):
    """Apply canonical dot operations, e.g. a separately stored reference patch."""
    if not isinstance(patch, list):
        raise IntentError('Expected an array of operations')
    array_identities = _context(array_identities)
    state = copy.deepcopy(initial_state)
    validate_data(state, array_identities)
    normalized = []
    for operation in patch:
        if not isinstance(operation, dict):
            raise IntentError('Operation must be an object')
        op = {'replace': 'update', 'add': 'append', 'remove': 'remove',
              'move': 'move', 'copy': 'copy'}.get(operation.get('op'))
        if op is None:
            raise IntentError('Unsupported reference operation')
        if op in ('move', 'copy'):
            if set(operation) != {'op', 'from', 'path'}:
                raise IntentError('Reference Move and Copy require only op, from and path')
            raw = {'op': op, 'from': {'kind': 'dot', 'text': operation['from']},
                   'to': {'kind': 'dot', 'text': operation['path']}}
        else:
            raw = {**operation, 'op': op, 'path': {'kind': 'dot', 'text': operation.get('path')}}
        current, state = _operation(state, raw, array_identities)
        normalized.append(current)
    return {'normalized_patch': normalized, 'final_state': state}


def normalize_response(raw, initial_state, output_format='json_dot', array_identities=None):
    """Only text, initial data and explicit collection identity metadata enter."""
    if type(raw) is not str or not raw.strip():
        raise IntentError('A nonempty original textual response is required')
    if output_format not in OUTPUT_FORMATS:
        raise IntentError('Unknown output format: ' + str(output_format))
    array_identities = _context(array_identities)
    state = copy.deepcopy(initial_state)
    validate_data(state, array_identities)
    from .output_formats import decode
    parsed = decode(raw, output_format, state, identity_context=array_identities)
    normalized = []
    for operation in parsed['operations']:
        current, state = _choose(state, operation, array_identities)
        normalized.append(current)
    return {'normalized_patch': normalized, 'final_state': state,
            'diagnostics': parsed['diagnostics'],
            'runtime': {'python_version': platform.python_version()},
            'raw_sha256': hashlib.sha256(raw.encode('utf-8', errors='surrogatepass')).hexdigest()}


def unordered(value):
    """Canonical comparison view; execution and saved actual data keep their order."""
    if isinstance(value, dict):
        return {key: unordered(child) for key, child in value.items()}
    if isinstance(value, list):
        children = [unordered(child) for child in value]
        return sorted(children, key=canonical)
    if type(value) is float and value.is_integer():
        return int(value)
    return value


def score_final(test, actual):
    _context(test['source'].get('array_identities')).validate(actual, check_paths=False)
    before, expected, got = map(unordered, (test['source']['initial_state'], test['expected_state'], actual))
    _context(test['source'].get('array_identities')).validate(test['expected_state'], check_paths=False)
    required, predicted = changes(before, expected), changes(before, got)
    shared = required.keys() & predicted.keys()
    correct = sum(equal(required[key], predicted[key]) for key in shared)
    return {'valid': True, 'exact_match': equal(expected, got), 'actual_state': copy.deepcopy(actual),
            'state_exact_match': equal(expected, got), 'array_order': 'irrelevant',
            'required_changes': len(required), 'correct_changes': correct,
            'missed_changes': len(required.keys() - predicted.keys()), 'wrong_values': len(shared) - correct,
            'unsupported_changes': len(predicted.keys() - required.keys()),
            'precision': correct / len(predicted) if predicted else None,
            'recall': correct / len(required) if required else None}


def expected_patch_diagnostic(test, variant, normalized):
    """Diagnostic only. Even a broken reference must never change pass/fail."""
    if 'expected_patch' not in variant:
        return {'expected_patch_match': None, 'expected_patch_mismatch': None,
                'expected_patch_diagnostic': 'No reference patch was supplied.'}
    try:
        expected = apply_patch(test['source']['initial_state'], variant['expected_patch'], test['source'].get('array_identities'))
        if not equal(unordered(expected['final_state']), unordered(test['expected_state'])):
            raise IntentError('Reference patch does not produce the expected final state')
        matches = equal(normalized, expected['normalized_patch'])
        return {'expected_patch_match': matches, 'expected_patch_mismatch': not matches,
                'expected_normalized_patch': expected['normalized_patch'],
                'expected_patch_diagnostic': 'Normalized patch matches the reference.' if matches else
                    'Normalized patch differs from the reference; final-state correctness alone determines pass/fail.'}
    except (ValueError, KeyError, TypeError) as exc:
        return {'expected_patch_match': None, 'expected_patch_mismatch': None,
                'expected_patch_diagnostic': 'Reference patch unavailable: ' + str(exc)}


def validate_selection(test, variant):
    result = variant.get('result', {})
    selected = result.get('evaluator')
    if selected != configuration():
        raise ValueError('Unknown or stale schema-free evaluator; explicitly compile a new evaluator configuration')
    if result.get('representation') != 'dot_patch_v1':
        raise ValueError(VERSION + ' requires canonical dot_patch_v1 results')
    if result.get('output_format', 'json_dot') not in OUTPUT_FORMATS:
        raise ValueError('Unsupported schema-free output_format')
    if 'expected_state' not in test:
        raise ValueError('Schema-free scoring requires a final-state oracle')
    validate_data(test['source']['initial_state'], test['source'].get('array_identities'))
    _context(test['source'].get('array_identities')).validate(test['expected_state'], check_paths=False)
    def walk(steps):
        for step in steps:
            yield step
            yield from walk(step.get('steps', []))
    final = next((step for step in walk(variant.get('steps', [])) if step['id'] == result.get('step')), None)
    if final is None or final.get('type') != 'generate' or final.get('output', {}).get('type', 'text') != 'text':
        raise ValueError('Schema-free evaluation requires a text final generation step')
