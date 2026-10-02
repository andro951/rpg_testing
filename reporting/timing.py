"""Descriptive timing badges; never change execution identity or saved scoring."""
import json
import math
from pathlib import Path
from statistics import median


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def expectations():
    return json.loads(Path(__file__).with_name('timing_expectations.json').read_text(encoding='utf-8'))


def annotate(matrix, specs, catalog=None):
    catalog = expectations() if catalog is None else catalog
    deadlines = {test['id']: test.get('timeout_seconds', 120) for test in specs}
    groups = {}
    for record in matrix['records'].values():
        metadata = record['metadata']
        timed_out = bool(metadata.get('timed_out')) or record['outcome'] == 'timeout'
        elapsed = metadata.get('pipeline_seconds')
        elapsed = elapsed if type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0 else None
        entry = catalog.get(metadata.get('test_id'), {}).get(metadata.get('variant_id'), {})
        expected = entry.get('seconds') if entry.get('definition_id') == record.get('definition_id') else None
        if expected is not None and not positive(expected):
            raise ValueError('Expected completion time must be positive and finite')
        timeout = 300 if record.get('execution_class') == 'remote_service' else deadlines.get(metadata.get('test_id'))
        record['timing'] = {'elapsed_seconds': elapsed, 'expected_seconds': expected,
                            'expectation_reason': entry.get('reason') if expected is not None else None,
                            'current_timeout_seconds': timeout if positive(timeout) else None,
                            'saved_timeout_seconds': metadata.get('watchdog_seconds', metadata.get('timeout_seconds')),
                            'timed_out': timed_out, 'peer_median_seconds': None, 'peer_models': 0,
                            'relative_threshold_seconds': None}
        if (not timed_out and record['outcome'] in ('pass', 'fail') and elapsed is not None and elapsed > 0
                and record.get('timing_group')):
            model_times = groups.setdefault(record['timing_group'], {})
            model_times.setdefault(record['model'], []).append(elapsed)
    for record in matrix['records'].values():
        peers = groups.get(record.get('timing_group'), {})
        timing = record['timing']
        timing['peer_models'] = len(peers)
        if len(peers) >= 3:
            baseline = median(median(times) for times in peers.values())
            timing['peer_median_seconds'] = baseline
            timing['relative_threshold_seconds'] = 2 * baseline
    return matrix
