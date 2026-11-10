"""Opt-in, schema-free patch host. The normalizer sees only text and initial data.

Object-array identity is the one shared scalar ``id`` or ``*_id`` field with
unique values. Multiple candidates are rejected, never ranked or guessed from
arbitrary unique data. Empty arrays have no inferred type until an addition.
Arrays are unordered for final-state comparison, not for sequential execution.
Frozen schema-based evaluators and their historical definitions are unchanged.
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

class ParserGap(IntentError):
    """Unprescribed prose has no deterministic interpretation; not a model failure."""


VERSION = 'schema-free-intent-v1'
OUTPUT_FORMATS = ('json_dot', 'json_slash', 'path_list', 'literal_line',
                  'end_marked_line', 'two_line_text', 'typed_lines', 'free_format')
SOURCES = ('evaluation/schema_free_intent.py', 'evaluation/output_formats.py',
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


def id_field(array):
    """Return a provable ID-named field, or None for primitive/empty arrays."""
    if not isinstance(array, list):
        raise IntentError('Identity requires an array')
    if not array:
        return None
    if all(not isinstance(element, (dict, list)) for element in array):
        return None
    if not all(isinstance(element, dict) for element in array):
        raise IntentError('Arrays must contain only objects or only primitive IDs, not mixed containers')
    common = set.intersection(*(set(element) for element in array))
    candidates = [key for key in sorted(common) if (key == 'id' or key.endswith('_id'))
                  and all(not isinstance(element[key], (dict, list)) for element in array)]
    candidates = [key for key in candidates if not any(
        equal(a[key], b[key]) for i, a in enumerate(array) for b in array[i + 1:])]
    if len(candidates) != 1:
        raise IntentError('Object array requires exactly one shared unique scalar id or *_id field; '
                          + ('ambiguous candidates: ' + ', '.join(candidates) if candidates else 'none found'))
    return candidates[0]


def identity(element, array):
    key = id_field(array)
    return element[key] if key is not None else element


def validate_data(state):
    """Validate only the general collection contract, never a per-case shape."""
    assert_json(state)
    def walk(value):
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            key = id_field(value)
            ids = [element[key] if key is not None else element for element in value]
            if any(equal(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]):
                raise IntentError('Duplicate collection identifiers')
            if len({scalar_text(item) for item in ids}) != len(ids):
                raise IntentError('Ambiguous plain selectors: different typed identities have the same text')
            for child in value:
                walk(child)
    walk(state)


def _components(state, parts, *, typed=False, slash=False):
    concrete = []
    for part in parts:
        if isinstance(state, dict):
            key = value_paths.property_name(part) if slash else scalar_text(part)
            if key not in state:
                raise IntentError('Missing existing field: ' + key)
        elif isinstance(state, list):
            wanted = parse(part) if slash else part
            key_field = id_field(state)
            matches = [index for index, element in enumerate(state)
                       if (equal(element[key_field] if key_field else element, wanted) if typed or slash else
                           scalar_text(element[key_field] if key_field else element) == scalar_text(wanted))]
            if len(matches) != 1:
                raise IntentError('Array ID must match exactly one element; no positional selectors')
            key = matches[0]
        else:
            raise IntentError('Path continues through a scalar')
        concrete.append(str(key))
        state = state[key]
    return state, concrete


def resolve(state, path):
    """Resolve dot separators only if there is exactly one state interpretation."""
    parts = _resolution_parts(path)
    found = {}
    def walk(value, offset, concrete):
        if offset == len(parts):
            found[tuple(concrete)] = (value, concrete)
            return
        if isinstance(value, dict):
            choices = [(key, key, child) for key, child in value.items()]
        elif isinstance(value, list):
            field = id_field(value)
            choices = [(scalar_text(child[field] if field else child), str(i), child)
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
                        walk(child, end + 1, concrete + [key])
                    if len(found) > 1:
                        return
            if explicit:
                break
    walk(state, 0, [])
    if len(found) > 1:
        raise IntentError('Ambiguous dot path; use percent escapes or explicit components')
    if not found:
        raise IntentError('Path must resolve to an existing field or unique ID; no positional selectors')
    return next(iter(found.values()))


def from_pointer(state, parts):
    """Encode concrete parts (internal only) as canonical ID-based dot paths."""
    if isinstance(parts, str):
        from workbench.scoring import pointer
        parts = pointer(parts)
    encoded = []
    for part in parts:
        if isinstance(state, list):
            element = state[int(part)]
            encoded.append(encode_part(scalar_text(identity(element, state))))
            state = element
        else:
            encoded.append(encode_part(part))
            state = state[part]
    return '.'.join(encoded)


def _reference(state, reference):
    kind = reference.get('kind') if isinstance(reference, dict) else None
    if kind == 'dot':
        return resolve(state, reference['text'])
    if kind == 'components':
        return _components(state, reference['parts'])
    if kind == 'typed_components':
        return _components(state, reference['parts'], typed=True)
    if kind == 'slash':
        return _components(state, value_paths.tokens(reference['text']), slash=True)
    if kind == 'object_components':
        value = state
        for part in reference['parts']:
            if not isinstance(value, dict) or part not in value:
                raise IntentError('Typed lines support existing object-field paths only, not array-element selection')
            value = value[part]
        return value, reference['parts']
    raise IntentError('Missing lexical path provenance')


def _operation(state, raw):
    op = raw.get('op')
    if op not in ('update', 'append', 'remove'):
        raise IntentError('Only Update, Add and Remove are supported')
    fields = {'op', 'path'} if op == 'remove' else {'op', 'path', 'value'}
    if set(raw) != fields:
        raise IntentError('Missing or extra operation fields')
    target, parts = _reference(state, raw['path'])
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
                  'path': from_pointer(state, parts)}
    if op != 'remove':
        normalized['value'] = copy.deepcopy(raw['value'])
    concrete = {**normalized, 'path': pointer}
    after = apply_rfc(state, [concrete], 'json_patch')
    validate_data(after)
    return normalized, after


def _choose(state, raw):
    if 'unlabeledPathValue' not in raw:
        return _operation(state, raw)
    candidates = []
    for candidate in raw['unlabeledPathValue']:
        try:
            result = _operation(state, {'op': raw['op'], **candidate})
            if not any(equal(result[0], prior[0]) for prior in candidates):
                candidates.append(result)
        except (ValueError, KeyError, TypeError):
            continue
    if len(candidates) != 1:
        raise IntentError('Unlabeled path/value requires exactly one current-data interpretation')
    return candidates[0]


def apply_patch(initial_state, patch):
    """Apply canonical dot operations, e.g. a separately stored reference patch."""
    if not isinstance(patch, list):
        raise IntentError('Expected an array of operations')
    state = copy.deepcopy(initial_state)
    validate_data(state)
    normalized = []
    for operation in patch:
        if not isinstance(operation, dict):
            raise IntentError('Operation must be an object')
        op = {'replace': 'update', 'add': 'append', 'remove': 'remove'}.get(operation.get('op'))
        if op is None:
            raise IntentError('Unsupported reference operation')
        current, state = _operation(state, {**operation, 'op': op,
                                           'path': {'kind': 'dot', 'text': operation.get('path')}})
        normalized.append(current)
    return {'normalized_patch': normalized, 'final_state': state}


def normalize_response(raw, initial_state, output_format='json_dot'):
    """Leakage boundary: no schema, expected state, reference patch or task text."""
    if type(raw) is not str or not raw.strip():
        raise IntentError('A nonempty original textual response is required')
    if output_format not in OUTPUT_FORMATS:
        raise IntentError('Unknown output format: ' + str(output_format))
    state = copy.deepcopy(initial_state)
    validate_data(state)
    from .output_formats import decode
    parsed = decode(raw, output_format, state)
    normalized = []
    for operation in parsed['operations']:
        current, state = _choose(state, operation)
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
    before, expected, got = map(unordered, (test['source']['initial_state'], test['expected_state'], actual))
    validate_data(test['expected_state'])
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
        expected = apply_patch(test['source']['initial_state'], variant['expected_patch'])
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
        raise ValueError('schema-free-intent-v1 requires canonical dot_patch_v1 results')
    if result.get('output_format', 'json_dot') not in OUTPUT_FORMATS:
        raise ValueError('Unsupported schema-free output_format')
    if 'expected_state' not in test:
        raise ValueError('Schema-free scoring requires a final-state oracle')
    validate_data(test['source']['initial_state'])
    validate_data(test['expected_state'])
    def walk(steps):
        for step in steps:
            yield step
            yield from walk(step.get('steps', []))
    final = next((step for step in walk(variant.get('steps', [])) if step['id'] == result.get('step')), None)
    if final is None or final.get('type') != 'generate' or final.get('output', {}).get('type', 'text') != 'text':
        raise ValueError('Schema-free evaluation requires a text final generation step')
