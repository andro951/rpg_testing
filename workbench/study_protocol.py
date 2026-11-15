"""Optional, frozen study-wide native context; never selects a policy implicitly.

Only an explicitly supplied study_protocol.json activates this mode. This module
never writes that file, chooses a limit, loads a model, or edits model metadata.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import re

from .domain import digest, safe_id

FILENAME = 'study_protocol.json'
VERSION = 'common-native-context-v1'
CAPACITY_POLICY = 'fixed-case-local-v1'


def validate(value):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'study_id', 'context', 'qualification_evidence'}:
        raise ValueError('Study protocol requires schema_version, study_id, context and qualification_evidence')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Unsupported study protocol schema version')
    safe_id(value['study_id'])
    context = value['context']
    if not isinstance(context, dict) or set(context) != {'policy', 'tokens', 'capacity_policy'}:
        raise ValueError('Study context requires policy, tokens and capacity_policy')
    if context['policy'] != VERSION or context['capacity_policy'] != CAPACITY_POLICY:
        raise ValueError('Unsupported study context policy')
    if type(context['tokens']) is not int or not 512 <= context['tokens'] <= 2**31-1:
        raise ValueError('Common context tokens must be an integer from 512 through 2147483647')
    evidence = value['qualification_evidence']
    if not isinstance(evidence, list) or not evidence:
        raise ValueError('Common context requires qualification evidence references')
    seen = set()
    for row in evidence:
        if not isinstance(row, dict) or set(row) != {'reference', 'sha256'}:
            raise ValueError('Qualification evidence requires reference and sha256')
        reference = row['reference']
        if not isinstance(reference, str) or not reference.strip() or len(reference) > 2048 or any(ord(c) < 32 for c in reference):
            raise ValueError('Invalid qualification evidence reference')
        if reference in seen:
            raise ValueError('Duplicate qualification evidence reference')
        seen.add(reference)
        if not isinstance(row['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
            raise ValueError('Invalid qualification evidence SHA-256')
    return copy.deepcopy(value)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate study protocol JSON field: ' + key)
        result[key] = value
    return result


def load(root):
    root = Path(root).resolve()
    path = root / FILENAME
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise ValueError('Study protocol must be a regular file at the repository root')
    return validate(json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object))


def snapshot(protocol):
    if protocol is None:
        return None
    value = validate(protocol)
    return {'digest': digest(value), 'protocol': value,
            'evidence_verification': 'references-only-unverified'}


def context_plan(tests, metadata, protocol=None):
    # Import lazily to keep the default estimator independently usable by OPRO.
    from .inventory import automatic_context
    if protocol is None:
        return automatic_context(tests, metadata)
    value = validate(protocol)
    estimated = automatic_context(tests, metadata)
    tokens = value['context']['tokens']
    if tokens > estimated['native_tokens']:
        raise ValueError('Common study context exceeds this model\'s true native maximum; never clamp it per model')
    return {**estimated, 'allocated_tokens': tokens,
            'capacity_policy': CAPACITY_POLICY,
            'study_protocol': snapshot(value),
            'input_may_exceed_allocated_context': estimated['input_estimate_bytes'] >= tokens,
            'method': 'explicit frozen common native context; byte estimates are diagnostic only; exact runtime tokenizer guard',
            'output_cap': None}


def remote_context(protocol):
    """Requested provenance only; never an applied Perchance control or CID."""
    if protocol is None:
        return None
    value = validate(protocol)
    return {'study_protocol': snapshot(value), 'requested_tokens': value['context']['tokens'],
            'applied_tokens': None, 'control_status': 'unsupported',
            'provider_context_limit': None, 'verification_status': 'unknown',
            'reason': 'The remote provider exposes no verifiable context-allocation control.'}


def verify_native_context(context, actual):
    """An explicit common allocation needs positive runtime evidence, not argv."""
    if context.get('study_protocol') is not None:
        frozen = context['study_protocol']
        if (not isinstance(frozen, dict) or set(frozen) != {'digest', 'protocol', 'evidence_verification'}
                or snapshot(frozen['protocol']) != frozen
                or context['allocated_tokens'] != frozen['protocol']['context']['tokens']):
            raise ValueError('Requested allocation differs from its frozen study protocol')
        if type(actual) is not int or actual <= 0 or actual != context['allocated_tokens']:
            raise ValueError('Runtime did not verify the exact common study context allocation')
    elif actual and actual != context['allocated_tokens']:
        raise ValueError('Runtime changed the context allocation')
