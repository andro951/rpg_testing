"""Export immutable case records without conflating retries or simulated runs."""
from __future__ import annotations
import argparse
import csv
import io
import statistics
from pathlib import Path
from .core import atomic_write, digest, read_json


def collect(roots: list[Path], include_simulated: bool = False) -> list[dict]:
    records = {}
    for root in roots:
        for path in sorted(root.rglob('attempt-*.json')):
            envelope = read_json(path)
            record = envelope['record']
            if envelope.get('sha256') != digest(record):
                raise ValueError(f'Corrupt result: {path}')
            if record.get('status') not in {'completed', 'error'}:
                raise ValueError(f'Invalid status: {path}')
            if record.get('simulated', False) and not include_simulated:
                continue
            # The same copied result is not a new measurement.
            records.setdefault(digest(record), record)
    return list(records.values())


def summarize(records: list[dict]) -> dict:
    groups = {}
    for record in records:
        key = record['case_id']
        groups.setdefault(key, []).append(record)
    completed = []
    errors = 0
    for case_id, attempts in groups.items():
        results = [r for r in attempts if r['status'] == 'completed']
        errors += sum(r['status'] == 'error' for r in attempts)
        if len(results) > 1:
            raise ValueError(f'Multiple distinct completions for {case_id}; assign a new repetition instead of silently averaging duplicates')
        completed.extend(results)
    rows = []
    for r in completed:
        s = r['score']
        rows.append({'case_id': r['case_id'], 'model_id': r['model_id'], 'pipeline': r['pipeline'],
                     'fixture_id': r['fixture_id'], 'seed': r['seed'], 'repetition': r['repetition'],
                     'simulated': r.get('simulated', False), 'environment_id': digest(r['environment']),
                     'gpu_name': r['environment']['gpu_name'], 'backend': r['environment']['backend'],
                     'valid': s['valid'], 'exact_match': s['exact_match'],
                     'correct_changes': s.get('correct_changes'), 'required_changes': s.get('required_changes'),
                     'missed_changes': s.get('missed_changes'), 'wrong_values': s.get('wrong_values'),
                     'unsupported_changes': s.get('unsupported_changes'),
                     'pipeline_seconds': r['pipeline_seconds'], 'call_count': len(r['calls'])})
    grouped = {}
    for row in rows:
        key = (row['model_id'], row['pipeline'], row['environment_id'], row['simulated'])
        grouped.setdefault(key, []).append(row)
    aggregates = []
    for key, cases in sorted(grouped.items()):
        model, pipeline, env, simulated = key
        aggregates.append({'model_id': model, 'pipeline': pipeline, 'environment_id': env, 'simulated': simulated,
                           'completed_cases': len(cases),
                           'exact_match_rate': sum(r['exact_match'] for r in cases)/len(cases),
                           'valid_output_rate': sum(r['valid'] for r in cases)/len(cases),
                           'median_pipeline_seconds': statistics.median(r['pipeline_seconds'] for r in cases)})
    return {'completed_cases': len(rows), 'infrastructure_error_attempts': errors,
            'unresolved_cases': sum(not any(r['status'] == 'completed' for r in a) for a in groups.values()),
            'groups': aggregates, 'cases': rows}


def write_exports(report: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    atomic_write(output/'summary.json', report)
    if report['cases']:
        text = io.StringIO(newline='')
        writer = csv.DictWriter(text, fieldnames=list(report['cases'][0]))
        writer.writeheader(); writer.writerows(report['cases'])
        (output/'cases.csv').write_text(text.getvalue(), encoding='utf-8')
    else:
        (output/'cases.csv').write_text('case_id\n', encoding='utf-8')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots',nargs='+',type=Path)
    parser.add_argument('--include-simulated',action='store_true')
    parser.add_argument('--output',type=Path,default=Path('.local/analysis'))
    args=parser.parse_args(argv)
    for root in args.roots:
        if not root.is_dir():parser.error(f'Result directory does not exist: {root}')
    report=summarize(collect(args.roots,args.include_simulated))
    write_exports(report,args.output)
    print(f"Exported {report['completed_cases']} completed cases; {report['infrastructure_error_attempts']} infrastructure-error attempts; {report['unresolved_cases']} unresolved cases.")
    return 0

if __name__=='__main__':raise SystemExit(main())
