"""Optional offline intent-parser diagnostics over saved Workbench evidence.

This is deliberately separate from the benchmark evaluator and runner. Captured
answers are not rewritten into the intent language, and acceptance is not a score.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from intent_parser import replay_prepared


def analyze_records(records, options=None):
    """Parse completed final outputs using only captured initial state and text.

    Expected states, example patches, prompts and historical scores never enter
    the parser. No current test definitions are loaded and no inference is run.
    """
    results = []
    for record in records:
        identity = {key: record.get(key) for key in ('case_id', 'test_id', 'variant_id')}
        result = {**identity, 'status': 'skipped'}
        try:
            if record.get('status') != 'completed' or record.get('timed_out'):
                raise ValueError('Saved execution is not completed.')
            if any(call.get('finish_reason') not in ('stop', 'provider_completed')
                   or call.get('incomplete') or call.get('timed_out') for call in record.get('calls', [])):
                raise ValueError('Saved call is incomplete.')
            definition = record['test_definition']
            contract = record['variant_definition']['result']
            dialect = contract.get('representation')
            result['source_dialect'] = dialect
            if dialect == 'answers':
                raise ValueError('Answer-only contracts have no state-operation output.')
            if dialect not in ('intent', 'value_patch'):
                raise ValueError(
                    f'Unsupported captured source dialect: {dialect!r}. '
                    'Only explicit intent and schema-backed value_patch are supported; '
                    'json_patch requires RFC 6902 semantics. '
                    'Use the unchanged benchmark evaluator for those dialects.')
            state = definition['source']['initial_state']
            raw = record['outputs'][contract['step']]
            if not isinstance(raw, str):
                raise ValueError('Final output is not text.')
            # Explicit allowlist is the leakage boundary. Never forward record,
            # definition or variant objects to the normalizer/replay function.
            prepared = {'input': copy.deepcopy(state), 'output': raw}
            if dialect == 'value_patch':
                from .value_intent import replay_value_intent
                diagnostic = replay_value_intent(raw, prepared['input'],
                    copy.deepcopy(definition['state_schema']), copy.deepcopy(options or {}))
            else:
                intent_options = copy.deepcopy(options or {})
                diagnostic = replay_prepared([prepared], intent_options)['results'][0]
            result.update(status='analyzed', diagnostic=diagnostic)
        except (KeyError, TypeError, ValueError) as exc:
            result['reason'] = str(exc)
        results.append(result)
    analyzed = [r for r in results if r['status'] == 'analyzed']
    return {'mode': 'offline-workbench-intent-diagnostics', 'liveInference': False,
            'benchmarkScoresChanged': False, 'total': len(results),
            'analyzed': len(analyzed), 'skipped': len(results) - len(analyzed),
            'accepted': sum(r['diagnostic']['accepted'] for r in analyzed),
            'results': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='results', help='Saved evidence directory or ZIP.')
    parser.add_argument('--output', help='New diagnostic JSON file; default: stdout. Never overwrites.')
    parser.add_argument('--test', help='Only inspect this captured test ID.')
    parser.add_argument('--id-key', default='id', help='Object collection ID field (default: id).')
    parser.add_argument('--json-patch', action='store_true', help='Emit RFC 6902 conversion diagnostics.')
    args = parser.parse_args(argv)
    source = Path(args.source).resolve()
    output = Path(args.output).resolve() if args.output else None
    if not source.exists():
        parser.error('Evidence source does not exist.')
    if output and (output == source or source in output.parents):
        parser.error('Diagnostic output must be outside the saved evidence source.')
    # Reuse checksum-verified evidence reading, never the scoring or runner path.
    from evaluation.__main__ import evidence_records
    problems = []
    records = (record for record in evidence_records(source, problems)
               if not args.test or record.get('test_id') == args.test)
    report = analyze_records(records, {'idKey': args.id_key, 'json_patch': args.json_patch})
    report['source'] = str(source)
    report['problems'] = problems
    payload = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if output:
        # Exclusive creation prevents overwriting saved evidence, reports or prompts.
        with output.open('x', encoding='utf-8') as handle:
            handle.write(payload)
    else:
        print(payload, end='')
    return 1 if problems else 0


if __name__ == '__main__':
    raise SystemExit(main())
