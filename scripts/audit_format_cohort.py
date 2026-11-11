"""Replay exactly 2,232 manifest-selected saved responses through syntax checks.

No inference, semantic rescoring, response repair, or original-evidence writes.
Usage: python scripts/audit_format_cohort.py --package RESULTS.zip --output NEW_DIR
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from evaluation.format_compliance import FORMATS, identity, validate


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check_cohort(rows):
    if len(rows) != 2232:
        raise ValueError('The exact 2232-row cohort is required')
    keys = {(r['model_id'], r['case'], r['input_format'], r['output_format']) for r in rows}
    if len(keys) != 2232:
        raise ValueError('Duplicate cohort condition')
    models = collections.Counter(r['model_id'] for r in rows)
    if len(models) != 6 or set(models.values()) != {372}:
        raise ValueError('Require six models with 372 observations each')
    forms = collections.Counter((r['model_id'], r['output_format']) for r in rows)
    if set(f for _, f in forms) != set(FORMATS) or len(forms) != 36 or set(forms.values()) != {62}:
        raise ValueError('Require six active formats with 62 observations per model')
    if len({r['case'] for r in rows}) != 21:
        raise ValueError('Require all 21 cases')
    if any(r['passed'] not in ('True', 'False') for r in rows):
        raise ValueError('Missing package semantic verdict')


def read_original(row):
    path = Path(row['result_file'])
    data = path.read_bytes()
    if sha256(data) != row['result_sha256']:
        raise ValueError('Source checksum mismatch: ' + str(path))
    result = json.loads(data)
    texts = [c.get('text') for c in result.get('calls', []) if c.get('step') == 'patch']
    if 'patch' in result.get('outputs', {}):
        raw, raw_source = result['outputs']['patch'], 'outputs.patch'
    elif texts:
        raw, raw_source = texts[-1], 'calls:last_patch.text'
    else:
        raise ValueError('Missing original patch output and call text: ' + str(path))
    if not isinstance(raw, str):
        raise ValueError('Original patch response must be text: ' + str(path))
    if texts and texts[-1] != raw:
        raise ValueError('Original output/call text mismatch: ' + str(path))
    # Saved call text is original evidence when the pipeline did not save outputs.
    # An explicitly saved empty response is evidence, not a fabricated empty value.
    return raw, result.get('score'), raw_source


def verify_unchanged(sources):
    for path, digest in sources.items():
        if sha256(Path(path).read_bytes()) != digest:
            raise ValueError('Source changed during audit: ' + str(path))


def ensure_output_location(output, package, rows):
    output = Path(output).resolve()
    protected = {Path(package).resolve().parent}
    for row in rows:
        path = Path(row['result_file']).resolve()
        run = next((parent for parent in path.parents if parent.name == row['source_run']), path.parent)
        protected.add(run)
    if any(output == directory or directory in output.parents for directory in protected):
        raise ValueError('Output directory is inside original evidence: ' + str(output))
    return output


def write_immutable(output, artifacts):
    """Preflight every conflict, then exclusively create new files; never replace."""
    output = Path(output)
    encoded = {name: text.encode('utf8') for name, text in artifacts.items()}
    for name, data in encoded.items():
        target = output / name
        if target.exists() and target.read_bytes() != data:
            raise FileExistsError('Conflicting audit artifact: ' + str(target))
    output.mkdir(parents=True, exist_ok=True)
    for name, data in encoded.items():
        target = output / name
        try:
            with target.open('xb') as handle:
                handle.write(data)
        except FileExistsError:
            if target.read_bytes() != data:
                raise FileExistsError('Conflicting audit artifact: ' + str(target))


def json_lines(rows):
    return ''.join(json.dumps(row, ensure_ascii=True) + '\n' for row in rows)


def audit(package, output):
    package = Path(package).resolve()
    package_bytes = package.read_bytes()
    package_digest = sha256(package_bytes)
    with zipfile.ZipFile(io.BytesIO(package_bytes)) as archive:
        rows = list(csv.DictReader(io.StringIO(archive.read('full_372_per_model.csv').decode())))
    check_cohort(rows)
    output = ensure_output_location(output, package, rows)
    validator_identity = identity()
    sources = {package: package_digest}
    records, portable, unique = [], [], {}
    counts, errors = collections.Counter(), collections.Counter()
    for index, row in enumerate(rows, 1):
        raw, score, raw_source = read_original(row)
        source = Path(row['result_file']).resolve()
        if source in sources and sources[source] != row['result_sha256']:
            raise ValueError('Conflicting source hashes')
        sources[source] = row['result_sha256']
        verdict = validate(raw, row['output_format'])
        if verdict['fingerprint'] != validator_identity['fingerprint']:
            raise ValueError('Validator changed during audit')
        digest = sha256(raw.encode('utf8'))
        group_id = row['output_format'] + ':' + digest
        record = dict(row, row=index, raw=raw, raw_sha256=digest, group_id=group_id,
                      compliance=verdict, original_score=score, raw_source=raw_source)
        records.append(record)
        safe = {k: record[k] for k in ('row', 'model', 'model_id', 'case', 'input_format',
                'output_format', 'outcome', 'passed', 'source_run', 'evidence_kind',
                'repetition', 'status', 'result_sha256', 'raw_sha256', 'group_id')}
        safe.update(result_reference=row['source_run'] + '/frozen/results/' + row['model_id']
                    + '/' + source.name, compliance=verdict)
        portable.append(safe)
        group = unique.setdefault(group_id, dict(group_id=group_id, rows=[],
                output_format=row['output_format'], raw_sha256=digest, raw=raw,
                compliant=verdict['compliant'], errors=verdict['errors']))
        if group['raw'] != raw or group['compliant'] != verdict['compliant']:
            raise ValueError('Response grouping collision or inconsistent verdict')
        group['rows'].append(index)
        counts[(row['model'], row['output_format'], row['passed'] == 'True', verdict['compliant'])] += 1
        for error in verdict['errors']:
            errors[(row['model'], row['output_format'], error)] += 1
    verify_unchanged(sources)
    if identity() != validator_identity:
        raise ValueError('Validator changed during audit')
    summary = dict(package=package.name, package_sha256=package_digest,
                   validator=validator_identity, count=len(rows), all_source_hashes_verified=True,
                   source_hashes_reverified_after_read=True,
                   source_runs=dict(collections.Counter(r['source_run'] for r in rows)),
                   counts=[dict(model=k[0], output_format=k[1], semantic_pass=k[2], strict_pass=k[3], count=n)
                           for k, n in sorted(counts.items())],
                   errors=[dict(model=k[0], output_format=k[1], error=k[2], count=n)
                           for k, n in sorted(errors.items())])
    groups = list(unique.values())
    inspection = [dict(rows=g['rows'], format=g['output_format'], strict_pass=g['compliant'],
                       errors=g['errors'], raw=g['raw'], group_id=g['group_id'])
                  for g in sorted(groups, key=lambda g:(g['compliant'],g['output_format'],g['rows'][0]))]
    write_immutable(output, {'audit.json': json.dumps(summary, indent=2) + '\n',
                            'rows.jsonl': json_lines(records),
                            'unique-responses.txt': json_lines(inspection),
                            'cohort-rows.jsonl': json_lines(portable),
                            'cohort-response-groups.jsonl': json_lines(groups)})
    # Check again after writing supplementary reports; originals are never written.
    verify_unchanged(sources)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    summary = audit(args.package, args.output)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
