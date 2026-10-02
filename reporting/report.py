"""Versioned long-array analysis and a self-contained, offline HTML export."""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import zipfile
from pathlib import Path, PurePosixPath

from workbench.analysis import summarize
from workbench.domain import ResultStore, canonical, code_fingerprint, digest, experiment_spec, read_json
from .matrix import build_matrix

VERSION = 'all-results-report-v2'
OPERATIONS = ('replace', 'remove', 'add', 'move', 'copy', 'test')
REPRESENTATIONS = ('raw', 'indexed', 'full_paths')
MAPPING = {}
for offset, operation in enumerate(OPERATIONS):
    patch = f'array_patch_{operation}_{offset + 4:03}'
    locate = f'array_index_{operation}_{offset + 10:03}'
    for variant, representation in [('raw_array_json_patch', 'raw'), ('indexed_object_json_patch', 'indexed')]:
        MAPPING[patch, variant] = ('patch', operation, representation)
    MAPPING[patch + '_full_paths', 'full_paths_json_patch'] = ('patch', operation, 'full_paths')
    for variant, representation in [('raw_array_index', 'raw'), ('indexed_object_index', 'indexed'), ('full_paths_index', 'full_paths')]:
        MAPPING[locate, variant] = ('locate', operation, representation)


def unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def load_evidence(source):
    """Validate checksums/identities without extracting archives or changing evidence."""
    source = Path(source)
    records, problems = [], []
    store = ResultStore(source)
    if source.is_dir():
        for path in sorted(source.glob('*/*.json')):
            try:
                records.append(store.read(path))
            except (ValueError, OSError, TypeError) as exc:
                problems.append({'file': str(path), 'error': str(exc)})
    else:
        with zipfile.ZipFile(source) as archive:
            total = 0
            for info in archive.infolist():
                name = PurePosixPath(info.filename)
                if name.is_absolute() or '..' in name.parts or '\\' in info.filename:
                    raise ValueError('Unsafe archive member')
                if info.is_dir() or name.suffix != '.json' or len(name.parts) < 2:
                    continue
                # Evidence bundles may also contain specs and metadata.
                if not re.fullmatch(r'[0-9a-f]{64}', name.stem):
                    continue
                total += info.file_size
                if info.file_size > 128 * 1024**2 or total > 1024**3:
                    raise ValueError('Evidence archive exceeds the 1 GiB expanded limit')
                try:
                    record = json.loads(archive.read(info).decode('utf-8-sig'), object_pairs_hook=unique_pairs)
                    checksum = record.pop('sha256', None)
                    if checksum != digest(record):
                        raise ValueError('Checksum mismatch')
                    if record.get('case_id') != name.stem or record.get('model_id') != name.parent.name:
                        raise ValueError('Result identity does not match its filename')
                    if record.get('status') not in ('completed', 'skipped', 'error', 'aborted'):
                        raise ValueError('Unknown result status')
                    record['sha256'] = checksum
                    records.append(record)
                except (ValueError, TypeError, AttributeError) as exc:
                    problems.append({'file': info.filename, 'error': str(exc)})
    return records, problems


def stable_version(value):
    lines = str(value or '').splitlines()
    stable = [line.strip() for line in lines if line.strip().startswith(('version:', 'built with'))]
    return '\n'.join(stable) if stable else str(value or '')


def protocol(record):
    target = copy.deepcopy(record.get('target', {}))
    if 'backend_version' in target:
        target['backend_version'] = stable_version(target['backend_version'])
    return {'target': target, 'workflow': record.get('provenance', {}).get('workflow_code'),
            'policy': record.get('policy', record.get('measurement_policy')),
            'execution_class': record.get('execution_class', 'legacy_unverified'),
            'allocated_context': (record.get('load', {}).get('context') or {}).get('allocated'),
            'simulated': bool(record.get('simulated'))}


def classify(record, kind):
    if record.get('status') != 'completed':
        return record.get('status', 'unknown')
    if record.get('timed_out'):
        return 'timeout'
    if not record.get('measurement_valid', True):
        return 'invalid_measurement'
    score = record.get('score', {})
    if type(score.get('exact_match')) is not bool:
        return 'unscored'
    if score.get('exact_match') is True:
        return 'correct'
    if kind == 'locate':
        expected = record.get('variant_definition', {}).get('expected_answers', {}).get('index')
        actual = record.get('outputs', {}).get('index')
        if isinstance(actual, str) and isinstance(expected, str):
            # Conservative diagnostic only: ordered integer tokens, no negatives/decimals.
            if not re.search(r'[-+]\d|\d\.\d', actual):
                numbers = re.findall(r'\b\d+\b', actual)
                if numbers and numbers == re.findall(r'\b\d+\b', expected):
                    return 'correct_index_wrong_format'
        return 'wrong_or_ambiguous_index'
    return 'invalid_output' if score.get('valid') is False else 'incorrect_update'


def build_report(records, specs, fingerprint=None, problems=None, comparison_specs=()):
    fingerprint = fingerprint or code_fingerprint()
    definitions = {(test['id'], variant['id']): experiment_spec(test, variant)
                   for test in specs for variant in test.get('variants', [])}
    seen, evidence, cohorts, history, models = {}, {}, {}, [], {}
    for record in records:
        cid = record['case_id']
        if cid in seen:
            if canonical(seen[cid]) != canonical(record):
                raise ValueError('Conflicting results share a case ID')
            continue
        seen[cid] = record
        mapping = MAPPING.get((record.get('test_id'), record.get('variant_id')))
        if not mapping:
            continue
        kind, operation, representation = mapping
        artifact = record.get('artifact_identity') or record.get('artifact_hashes', {})
        load = record.get('load', {})
        configuration = {'artifact': artifact,
                         'native_context': (load.get('context') or {}).get('native'),
                         'placement': {key: (load.get('placement') or {}).get(key) for key in ('gpu_layers', 'cpu_layers', 'total_layers')}}
        model = record['model_id'] + ':' + digest(configuration)[:12]
        files = artifact.get('files', []) if isinstance(artifact, dict) else []
        label = ', '.join(item['name'] for item in files if 'name' in item) or record.get('model_name') or record['model_id']
        models[model] = {'label': label, 'id': record['model_id'], 'artifact': artifact, 'configuration': configuration}
        evidence[cid] = record
        row = {'id': cid, 'model': model, 'kind': kind, 'operation': operation,
               'representation': representation, 'repetition': record.get('repetition', 0),
               'outcome': classify(record, kind), 'seconds': None}
        seconds = record.get('pipeline_seconds')
        if row['outcome'] not in ('timeout', 'invalid_measurement') and record['status'] == 'completed' and type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0:
            row['seconds'] = seconds
        definition = experiment_spec(record.get('test_definition', {}), record.get('variant_definition', {}))
        current = definition == definitions.get((record.get('test_id'), record.get('variant_id'))) and record.get('provenance', {}).get('workflow_code') == fingerprint
        if not current:
            row['reason'] = 'Historical definition or workflow fingerprint; excluded from current comparisons'
            history.append(row)
            continue
        conditions = protocol(record)
        key = digest(conditions)
        cohort = cohorts.setdefault(key, {'id': key, 'conditions': conditions, 'rows': [], 'cells': [], 'matched': {}})
        cohort['rows'].append(row)
    for cohort in cohorts.values():
        present_models = sorted({row['model'] for row in cohort['rows']})
        for kind in ('locate', 'patch'):
            slots = {}
            for row in cohort['rows']:
                if row['kind'] == kind:
                    slots.setdefault((row['model'], row['operation'], row['repetition'], row['representation']), []).append(row)
            repetitions = sorted({row['repetition'] for row in cohort['rows'] if row['kind'] == kind})
            matched = []
            for operation in OPERATIONS:
                for repetition in repetitions:
                    if all(len(slots.get((model, operation, repetition, representation), [])) == 1 and
                           slots[model, operation, repetition, representation][0]['outcome'] in ('correct', 'timeout', 'correct_index_wrong_format', 'wrong_or_ambiguous_index', 'invalid_output', 'incorrect_update')
                           for model in present_models for representation in REPRESENTATIONS):
                        matched.append([operation, repetition])
                    for model in present_models:
                        for representation in REPRESENTATIONS:
                            rows = slots.get((model, operation, repetition, representation), [])
                            cohort['cells'].append({'kind': kind, 'model': model, 'operation': operation,
                                'repetition': repetition, 'representation': representation,
                                'outcome': rows[0]['outcome'] if len(rows) == 1 else 'ambiguous' if rows else 'missing',
                                'ids': [row['id'] for row in rows]})
            cohort['matched'][kind] = matched
    remote = [r for r in seen.values() if r.get('execution_class') == 'remote_service']
    requested = len({a['requested_id'] for r in remote for a in r.get('aliases', [])})
    remote_statistics = {'independent_observations': sum(bool(r.get('calls')) for r in remote),
                         'observation_records':len(remote), 'mapped_requested_cases': requested,
                         'collapsed_cases': max(0, requested-len(remote)),
                         'statuses': {s: sum(r.get('status') == s for r in remote) for s in ('completed','error','aborted')},
                         'timeouts': sum(bool(r.get('timed_out')) for r in remote)}
    return {'version': VERSION, 'fingerprint': fingerprint, 'models': models,
            'matrix': build_matrix(list(seen.values()), specs, fingerprint, comparison_specs),
            'remote_statistics': remote_statistics,
            'cohorts': sorted(cohorts.values(), key=lambda item: (-len(item['rows']), item['id'])),
            'historical': history, 'evidence': evidence, 'problems': problems or [],
            'original_summary': summarize(list(seen.values())),
            'notes': ['Rates use only operations/repetitions observed once in all three representations and all models in the selected cohort. Timeouts count as unsuccessful; infrastructure and invalid measurements appear in coverage.',
                      'Patch full-path companions use direct_text_v1; raw/indexed use conversational_v2. This is a comparison of recorded configurations, not an isolated causal representation effect.',
                      'Completed-response latency excludes timeouts, which are displayed separately. Missing metrics are unavailable, never zero.',
                      'Index diagnostic v1 compares ordered integer tokens conservatively; it is not a replacement for original exact-match scoring. Sentences may identify the correct index but fail format. Ambiguous answers remain separate.',
                      'Historical records remain inspectable and retain original per-protocol summaries. Artifact identities may contain size/mtime rather than cryptographic hashes.',
                      'Remote service cohorts are separate from local GPU cohorts. Perchance aliases reference one observation; requested sampling is not applied sampling. Inspect capability_policy and aliases. Service latency includes browser/network/remote work.']}


def write_report(report, output, protected=()):
    output = Path(output).resolve()
    for root in protected:
        root = Path(root).resolve()
        if output == root or root in output.parents:
            raise ValueError('Report output must be outside evidence and test specs')
    script = Path(__file__).with_name('matrix.js').read_text(encoding='utf-8') + '\n' + Path(__file__).with_name('report.js').read_text(encoding='utf-8')
    data = canonical(report).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    html = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RPG testing statistics</title><body><script type="application/json" id="evidence-data">' + data + '</script><script>' + script + '</script></body></html>'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding='utf-8')
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('results'), help='results directory or evidence ZIP')
    parser.add_argument('--specs', type=Path, default=Path('test_specs'))
    parser.add_argument('--comparison-specs', type=Path, default=Path(__file__).with_name('comparison_specs'), help='named additional report comparisons; does not schedule inference')
    parser.add_argument('--output', type=Path, default=Path('.local/reports/statistics.html'))
    args = parser.parse_args(argv)
    records, problems = load_evidence(args.source)
    specs = [read_json(path) for path in sorted(args.specs.glob('*.json'))]
    comparison_specs = [read_json(path) for path in sorted(args.comparison_specs.glob('*.json'))]
    report = build_report(records, specs, problems=problems, comparison_specs=comparison_specs)
    if args.source.is_dir():
        for cid, summary in report['matrix']['records'].items():
            summary['source_uri'] = (args.source / summary['metadata']['model_id'] / (cid + '.json')).resolve().as_uri()
    else:
        for cid, summary in report['matrix']['records'].items():
            summary['source_archive'] = str(args.source.resolve()) + ' / ' + summary['metadata']['model_id'] + '/' + cid + '.json'
    path = write_report(report, args.output, (args.source, args.specs, args.comparison_specs))
    print(f'{path}: {len(report["matrix"]["records"])} total records, {len(report["evidence"])} long-array records, {len(report["cohorts"])} current cohorts, {len(problems)} unreadable files')
    return report


if __name__ == '__main__':
    main()