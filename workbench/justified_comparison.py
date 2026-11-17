"""Prepare a separate affected-only comparison. Never runs or installs a suite."""
from __future__ import annotations
import copy
from .domain import digest
from .self_review import LEGACY_PROTOCOL, JUSTIFIED_PROTOCOL, enabled, protocol


def prepare(tests):
    """Return copied retry-enabled definitions and exact old/new pairing manifest.

    Model, sampling, seed/repetition, inputs and output format are unchanged. The
    caller must keep original source/results and select this separate suite only.
    Completion of all desktop models and Perchance must be verified externally.
    """
    selected, pairs = [], []
    seen = set()
    for test in tests:
        variants = []
        if test.get('enabled', True) is False:
            continue
        for variant in test['variants']:
            if variant.get('enabled', True) is False or not enabled(variant):
                continue
            if protocol(variant) != LEGACY_PROTOCOL:
                raise ValueError('Comparison source must be the original yes/no protocol')
            key = (test['id'], variant['id'])
            if key in seen:
                raise ValueError('Duplicate comparison pair')
            seen.add(key)
            revised = copy.deepcopy(variant)
            revised['retry_protocol'] = JUSTIFIED_PROTOCOL
            variants.append(revised)
            source_test = {k: copy.deepcopy(v) for k,v in test.items() if k != 'variants'}
            pairs.append({'test_id': test['id'], 'variant_id': variant['id'],
                          'source_test_sha256': digest(source_test),
                          'source_variant_sha256': digest(variant),
                          'revised_variant_sha256': digest(revised),
                          'old_protocol': LEGACY_PROTOCOL, 'new_protocol': JUSTIFIED_PROTOCOL})
        if variants:
            revised_test = copy.deepcopy(test)
            revised_test['variants'] = variants
            selected.append(revised_test)
    if not pairs:
        raise ValueError('No affected retry-enabled conditions selected')
    return selected, {'schema_version': 1, 'condition': JUSTIFIED_PROTOCOL,
                      'affected_variants': len(pairs), 'pairs': pairs}
