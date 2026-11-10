"""Explicit, versioned live host for the frozen dot-path research contract.

No expected values, prompts or scores enter normalize_response. The shared
intent parser remains generic; only this host interprets its path tokens as the
captured dot dialect and limits operations to existing-field update/add/remove.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import platform
from importlib import metadata
from jsonschema.exceptions import ValidationError, SchemaError
from pathlib import Path

from intent_parser.parse import parse_intent_with_diagnostics, path_tokens, _token_value, unwrap_fence, WS
from intent_parser.patch import IntentError, assert_json
from workbench import dot_paths
from workbench.domain import digest, local_schema
from workbench.scoring import apply as apply_rfc
from . import dot_separators_v2

VERSION = 'dot-intent-v1'
STRICT = 'strict-json-v1'
SOURCES = (
    'evaluation/live_intent.py', 'evaluation/dot_separators_v2.py',
    'intent_parser/__init__.py', 'intent_parser/parse.py',
    'intent_parser/patch.py', 'intent_parser/json_contract.py',
    'workbench/domain.py', 'workbench/workflows.py', 'workbench/scoring.py', 'workbench/live.py',
    'workbench/dot_paths.py', 'workbench/value_paths.py',
)


def identity():
    root = Path(__file__).resolve().parents[1]
    hashes = {name: hashlib.sha256((root/name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
              for name in SOURCES}
    version = metadata.version('jsonschema')
    data = {'version': VERSION, 'source_hashes': hashes,
            'python_version': platform.python_version(), 'jsonschema_version': version}
    return {**data, 'fingerprint': digest(data)}


def configuration():
    info = identity()
    return {'version': VERSION, 'fingerprint': info['fingerprint']}


def validate_selection(test, variant):
    if 'evaluator' not in variant.get('result', {}):
        return
    selected = variant['result']['evaluator']
    if not isinstance(selected, dict) or set(selected) != {'version', 'fingerprint'}:
        raise ValueError('result.evaluator requires exact version and fingerprint')
    if selected != configuration():
        raise ValueError('Unknown or stale live evaluator; explicitly prepare a new evaluator configuration')
    if variant['result'].get('representation') != 'dot_patch_v1':
        raise ValueError('dot-intent-v1 applies only to dot_patch_v1; other contracts are unchanged')
    if not test.get('state_schema') or 'expected_state' not in test:
        raise ValueError('Live intent evaluation requires the captured state schema and state oracle')
    def walk(steps):
        for step in steps:
            yield step
            yield from walk(step.get('steps', []))
    final = next((step for step in walk(variant['steps'])
                  if step['id'] == variant['result'].get('step')), None)
    if final is None or final.get('type') != 'generate' or final.get('output', {}).get('type', 'text') != 'text':
        raise ValueError('dot-intent-v1 requires a text final generation step; constrained outputs remain strict')


def select(test, version=VERSION):
    """Make a new experimental definition, never edit approved source prompts."""
    if version not in (VERSION, STRICT):
        raise ValueError('Unknown evaluator: ' + str(version))
    result = copy.deepcopy(test)
    pin = configuration() if version == VERSION else None
    for variant in result['variants']:
        if version == STRICT:
            variant.get('result', {}).pop('evaluator', None)
        elif variant.get('enabled', True):
            variant.setdefault('result', {})['evaluator'] = copy.deepcopy(pin)
            validate_selection(result, variant)
    return result


def _decode_path(nodes, options):
    """Retain lexical boundaries before any schema/state resolution.

    A JSON string is the whole dot path. A grouped path explicitly lists literal
    components. An unquoted dotted spelling retains quoted/percent boundaries,
    rather than blindly joining already-decoded segments.
    """
    if len(nodes) == 1 and nodes[0].group:
        # Use original numeric lexemes here: the generic cross-language IR uses
        # binary64, whereas the frozen dot dialect distinguishes JSON spellings
        # 1 and 1.0 when constructing an identity's plain-text selector.
        parts=[]
        for node in nodes[0].children:
            if node.type in ('SEP_COMMA', 'NEWLINE', 'PATH_SEPARATOR'):
                if node.text == '/':raise IntentError('Grouped dot paths do not use slash separators')
                continue
            if node.group or node.type not in ('STRING', 'NUMBER', 'WORD'):
                raise IntentError('Grouped paths require scalar components')
            parts.append(json.loads(node.text) if node.type in ('STRING', 'NUMBER') or node.text in ('true','false','null') else node.text)
        assert_json(parts)
        return {'kind': 'components', 'parts': parts}
    if len(nodes) == 1 and nodes[0].type == 'STRING':
        return {'kind': 'dot', 'text': _token_value(nodes[0])}
    if not nodes:
        raise IntentError('Missing dot path')
    expect_part = True
    for node in nodes:
        if node.group:
            raise IntentError('Nested dot path grouping is unsupported')
        if expect_part:
            if node.type not in ('WORD', 'STRING', 'NUMBER'):
                raise IntentError('Expected a dot path component')
        elif node.type != 'PATH_SEPARATOR' or node.text != '.':
            raise IntentError('Dot path components require dot separators')
        expect_part = not expect_part
    if expect_part:
        raise IntentError('Incomplete dot path')
    return {'kind': 'dot', 'text': ''.join(node.text for node in nodes)}


def _path(state, schema, reference):
    if not isinstance(reference, dict):
        raise IntentError('Missing lexical path provenance')
    if reference.get('kind') == 'components':
        raw = '.'.join(dot_paths.encode_part(dot_paths.scalar_text(p)) for p in reference['parts'])
        _, _, concrete = dot_paths.resolve(state, schema, raw)
    elif reference.get('kind') == 'dot':
        _, _, concrete = dot_separators_v2.resolve(state, schema, reference['text'])
    else:
        raise IntentError('Unsupported path provenance')
    from workbench.value_paths import pointer
    return dot_paths.from_pointer(state, schema, pointer(concrete))


def _operation(state, schema, raw):
    op = raw.get('op')
    if op not in ('update', 'append', 'remove'):
        raise IntentError('This research host permits only Update, Add and Remove; no Move/Copy')
    fields = {'op', 'path'} if op == 'remove' else {'op', 'path', 'value'}
    if set(raw) != fields:
        raise IntentError('Missing or extra operation fields')
    normalized = {'op': {'update': 'replace', 'append': 'add', 'remove': 'remove'}[op],
                  'path': _path(state, schema, raw['path'])}
    if op != 'remove':
        normalized['value'] = copy.deepcopy(raw['value'])
    concrete = dot_paths.lower_operation(state, normalized, schema)
    after = apply_rfc(state, [concrete], 'json_patch')
    assert_json(after)
    dot_paths.validate(after, schema)
    return normalized, after


def _choose(state, schema, raw):
    if 'unlabeledPathValue' not in raw:
        return _operation(state, schema, raw)
    candidates = []
    for candidate in raw['unlabeledPathValue']:
        try:
            result = _operation(state, schema, {'op': raw['op'], **candidate})
            if all(digest(result[0]) != digest(prior[0]) for prior in candidates):
                candidates.append(result)
        except (ValueError, KeyError, TypeError, ValidationError, SchemaError):
            continue
    if len(candidates) != 1:
        raise IntentError('Unlabeled path/value requires exactly one schema/state interpretation')
    return candidates[0]


def normalize_response(raw, initial_state, schema):
    """Only raw text, initial state and schema cross this leakage boundary."""
    if type(raw) is not str:
        raise IntentError('Live intent evaluation requires original textual output')
    if not raw.strip():
        raise IntentError('Empty output is not an explicit no-change response')
    local_schema(schema)
    state, schema = copy.deepcopy(initial_state), copy.deepcopy(schema)
    assert_json(state)
    dot_paths.validate(state, schema)
    # replace is enabled solely for this host's established JSON operation name.
    # No generic set/replace alias or RFC input bridge is introduced.
    parsed = parse_intent_with_diagnostics(raw, {
        'pathSyntax': 'value_patch', '_host_path_decoder': _decode_path,
        '_host_value_decoder': json.loads})
    assert_json(parsed)
    if not parsed['operations']:
        unwrapped, _ = unwrap_fence(raw)
        if re.fullmatch('[' + WS + ']*\\[[' + WS + ']*\\][' + WS + ']*', unwrapped) is None:
            raise IntentError('No change requires an explicit empty array, optionally fenced')
    operations = []
    for operation in parsed['operations']:
        normalized, state = _choose(state, schema, operation)
        operations.append(normalized)
    return {'normalized_patch': operations, 'final_state': state,
            'diagnostics': parsed['diagnostics'],
            'raw_sha256': hashlib.sha256(raw.encode('utf-8', errors='surrogatepass')).hexdigest()}
