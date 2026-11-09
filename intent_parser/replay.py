"""Deterministic prepared-output replay, never live inference or claimed accuracy."""
import hashlib
from .parse import parse_intent
from .patch import IntentError, apply_patch, convert_intent, equal


def replay_prepared(records, options=None):
    if type(records) is not list:
        raise IntentError('Prepared records must be an array')
    options, results = options or {}, []
    for index, record in enumerate(records):
        raw = record.get('output') if record.get('output') is not None else record.get('text')
        if type(raw) is not str:
            raise IntentError(f'Record {index} lacks textual output')
        result = {'index': index, 'name': record.get('name'), 'rawOutput': raw,
                  'rawSha256': hashlib.sha256(raw.encode('utf-16-le', errors='surrogatepass').decode('utf-16-le', errors='replace').encode('utf-8')).hexdigest()}
        try:
            ir = parse_intent(raw, options)
            selected = convert_intent(ir, record['input'], options)
            custom = convert_intent(ir, record['input'], {**options, 'json_patch': False}) if options.get('json_patch') else selected
            final = apply_patch(record['input'], custom, options)
            result.update(accepted=True, patch=selected, finalState=final)
            if 'expected' in record:
                result['expectedStateMatches'] = equal(final, record['expected'])
            if 'reject' in record:
                result['expectedRejectionMatches'] = record['reject'] is False
        except (IntentError, TypeError, KeyError, RecursionError) as exc:
            result.update(accepted=False, error=str(exc))
            if 'expected' in record:
                result['expectedStateMatches'] = False
            if 'reject' in record:
                result['expectedRejectionMatches'] = record['reject'] is True
        results.append(result)
    accepted = sum(r['accepted'] for r in results)
    return {'mode': 'offline-prepared-output-replay', 'liveInference': False,
            'format': 'rfc6902' if options.get('json_patch') else 'custom',
            'total': len(results), 'accepted': accepted, 'rejected': len(results)-accepted, 'results': results}
