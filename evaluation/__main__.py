"""Offline saved-evidence replay: python -m evaluation --source results."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from reporting.report import load_evidence
from workbench.domain import ResultStore, write_json, digest
from .catalog import registration
from .core import VERSION, assess_record


def readable(assessment):
    lines = [f"{assessment['test_id']} / {assessment['variant_id']}",
             f"Result: {assessment['objective_outcome']} | Execution: {assessment['execution_outcome']}",
             f"Original score comparison: {assessment['score_comparison']}", '']
    for check in assessment['checks']:
        context = f" operation {check['operation']}" if 'operation' in check else ''
        lines.append(f"{check['status'].upper()} {check['code']}{context}: {check['explanation']}")
        for key in ('expected', 'actual'):
            if key in check:
                from json import dumps
                value = check[key]
                formatted = value if isinstance(value, str) and '\n' in value else dumps(value, ensure_ascii=False, indent=2)
                lines.append(f"  {key}:")
                lines.extend('    ' + line for line in formatted.splitlines())
    if assessment['steps']:
        lines.extend(['', 'Step diagnostics:'])
        for step in assessment['steps']:
            lines.append(f"  {step['step']} iteration {step['iteration']}: complete={step['complete']}; semantic={step['semantic_outcome']}")
            for check in step['checks']:
                lines.append(f"    {check['status'].upper()} {check['code']}: {check['explanation']}")
    return '\n'.join(lines) + '\n'


def evidence_records(source, problems):
    """Directory replay keeps only one raw observation in memory at a time."""
    if source.is_dir():
        store = ResultStore(source)
        for path in sorted(source.glob('*/*.json')):
            try:
                yield store.read(path)
            except (ValueError, OSError, TypeError) as exc:
                problems.append({'file': str(path), 'error': str(exc)})
    else:
        records, errors = load_evidence(source)
        problems.extend(errors)
        yield from records


def replay(source, output, test_id=None, *, validator=None):
    if validator is not None:
        return revalidate(source, output, test_id, validator)
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError('Assessment output must be outside the saved evidence directory.')
    if not source.exists():
        raise ValueError('Evidence source does not exist: ' + str(source))
    problems = []
    output.mkdir(parents=True, exist_ok=True)
    counts, definitions, comparisons = Counter(), {}, Counter()
    for record in evidence_records(source, problems):
        if test_id and record.get('test_id') != test_id:
            continue
        try:
            entry = registration(record['test_id'], record['variant_id'])
            assessment = assess_record(record)
            assessment['registration_family'] = entry['family']
            assessment['registration_requirements'] = entry['specific_requirements']
            # Captured definitions always win; a source edit is a separately visible fact.
            assessment['current_source_hash'] = entry['source_sha256']
            assessment['evidence_source'] = str(source)
            name = record['case_id']
            write_json(output/'assessments'/f'{name}.json', assessment)
            text_path = output/'assessments'/f'{name}.txt'
            text_path.write_text(readable(assessment), encoding='utf-8')
            counts[assessment['objective_outcome']] += 1
            comparisons[assessment['score_comparison']] += 1
            group = definitions.setdefault(record['test_id'], {'variants': {}, 'outcomes': Counter()})
            group['outcomes'][assessment['objective_outcome']] += 1
            variant = group['variants'].setdefault(record['variant_id'], {'records': 0, 'models': set(), 'examples': {}})
            variant['records'] += 1
            variant['models'].add(record['model_id'])
            variant['examples'].setdefault(assessment['objective_outcome'], name)
        except (ValueError, TypeError, KeyError) as exc:
            problems.append({'case_id': record.get('case_id'), 'error': str(exc)})
    for group in definitions.values():
        for variant in group['variants'].values():
            variant['models'] = sorted(variant['models'])
    summary = {'evaluator_version': VERSION, 'source': str(source), 'output': str(output),
               'outcomes': dict(counts), 'score_comparisons': dict(comparisons),
               'definitions': definitions, 'problems': problems}
    write_json(output/'summary.json', summary)
    lines = ['# Detailed evaluation replay', '', f'Version: {VERSION}', '',
             'Read-only assessments of captured definitions; original results and scores are preserved.', '',
             '| Test | Variants | PASS | FAIL | INCONCLUSIVE | UNSCORED |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for identifier, group in sorted(definitions.items()):
        c = group['outcomes']
        lines.append(f"| {identifier} | {len(group['variants'])} | {c['PASS']} | {c['FAIL']} | {c['INCONCLUSIVE']} | {c['UNSCORED']} |")
    lines.extend(['', f'Original score comparisons: {dict(comparisons)}', f'Evidence/assessment problems: {len(problems)}', '',
                  'Individual readable .txt and structured .json reports are in `assessments/`; summary.json indexes examples per variant/outcome.'])
    (output/'README.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return summary


def immutable_json(path, value):
    """Never replace a different assessment or receipt at an existing identity."""
    import json
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != value:
            raise ValueError('Conflicting existing validation artifact: ' + str(path))
    else:
        write_json(path, value)


def revalidate(source, output, test_id, validator):
    from .validation import get_validator
    selected = get_validator(validator)
    source, output = Path(source).resolve(), Path(output).resolve()
    if output == source or source in output.parents:
        raise ValueError('Assessment output must be outside the saved evidence directory.')
    if not source.exists():
        raise ValueError('Evidence source does not exist: ' + str(source))
    output = output / (selected.version + '-' + selected.fingerprint[:16])
    immutable_json(output/'validator.json', selected.identity())
    problems, assessed, skipped = [], [], []
    counts, comparisons = Counter(), Counter()
    for record in evidence_records(source, problems):
        if test_id and record.get('test_id') != test_id:
            continue
        try:
            variant = record.get('variant_definition')
            if variant is None:
                variants = [v for v in record['test_definition'].get('variants', [])
                            if v['id'] == record.get('variant_id')]
                if len(variants) != 1:
                    raise ValueError('Captured definition must contain exactly one matching variant')
                variant = variants[0]
            if not selected.applicable(variant.get('result', {}).get('representation')):
                skipped.append({'case_id': record.get('case_id'), 'source_record_checksum': record.get('sha256'),
                                'reason': 'not_applicable'})
                continue
            assessment = assess_record(record, validator=validator)
            try:
                entry = registration(record['test_id'], record['variant_id'])
            except ValueError:
                entry = None
            assessment['registration_status'] = 'registered' if entry else 'captured_contract_only'
            if entry:
                assessment['current_source_hash'] = entry['source_sha256']
            # All semantic inputs come from the captured record, never the current catalog.
            name = assessment['validation_id']
            immutable_json(output/'assessments'/f'{name}.json', assessment)
            assessed.append({'validation_id': name, 'case_id': record.get('case_id'),
                             'source_record_checksum': record.get('sha256')})
            counts[assessment['objective_outcome']] += 1
            comparisons[assessment['score_comparison']] += 1
        except (ValueError, TypeError, KeyError) as exc:
            problems.append({'case_id': record.get('case_id'), 'error': str(exc)})
    dataset = {'source': str(source), 'test_filter': test_id, 'assessments': assessed,
               'not_applicable': skipped, 'problems': problems}
    dataset_id = digest(dataset)
    summary = {'evaluator_version': VERSION, 'validator': selected.identity(),
               'dataset_id': dataset_id, 'source': str(source), 'output': str(output),
               'outcomes': dict(counts), 'score_comparisons': dict(comparisons),
               'assessed_records': len(assessed), 'unique_validations': len({a['validation_id'] for a in assessed}),
               **dataset}
    immutable_json(output/f'summary-{dataset_id}.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='results')
    parser.add_argument('--output', default='.local/evaluation')
    parser.add_argument('--test', help='Replay only this test definition.')
    from .validation import VALIDATORS
    parser.add_argument('--validator', choices=VALIDATORS, help='Versioned offline reinterpretation; preserves generation lineage and original scores.')
    args = parser.parse_args()
    summary = replay(args.source, args.output, args.test, validator=args.validator)
    print(f"{sum(summary['outcomes'].values())} assessments: {summary['outcomes']}; score comparison: {summary['score_comparisons']}")
    print(f"Reports: {Path(args.output).resolve()}")
    if summary['problems']:
        print(f"{len(summary['problems'])} evidence/assessment problems; see summary.json")
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
