"""All saved outcomes and expected suite rows; never rescore or clone alias trials."""
from __future__ import annotations
import json
import re
from workbench.domain import digest, experiment_spec


def outcome(record):
    if record.get('status') != 'completed':
        return record.get('status', 'unscored')
    if record.get('measurement_valid') is False:
        return 'invalid'
    if record.get('timed_out'):
        return 'timeout'
    exact = record.get('score', {}).get('exact_match')
    return 'pass' if exact is True else 'fail' if exact is False else 'unscored'


def totals(cells, records):
    ids = {cid for cell in cells for cid in cell['primary_ids']}
    result = {key: 0 for key in ('pass', 'fail', 'timeout', 'error', 'aborted', 'skipped', 'invalid', 'unscored')}
    for cid in ids:
        state = records[cid]['outcome']
        result[state if state in result else 'unscored'] += 1
    result.update(observations=len(ids), references=sum(len(c['reference_ids']) for c in cells),
                  not_run=sum(not c['ids'] for c in cells))
    return result


def model_nickname(label):
    if 'perchance' in label.lower():
        return 'Perchance'
    match = re.search(r'qwen([0-9.]+)(-vl)?[-_](\d+(?:\.\d+)?b)', label, re.IGNORECASE)
    if match:
        return f"Q{match[1]}{'-VL' if match[2] else ''} {match[3].upper()}"
    name = re.sub(r'\.gguf$', '', label, flags=re.IGNORECASE)
    return name if len(name) <= 18 else name[:17] + '…'


def has_objective_oracle(test, variant):
    if str(test.get('id', '')).startswith('dialogue_test_'):
        return False
    representation = variant.get('result', {}).get('representation', 'answers')
    if representation == 'answers':
        return bool(variant.get('expected_answers'))
    return 'expected_state' in test


def build_matrix(records, specs, fingerprint):
    definitions = {(t['id'], v['id']): experiment_spec(t, v) for t in specs for v in t.get('variants', [])}
    names = {(t['id'], v['id']): (t.get('name') or t['id'], v.get('name') or v['id']) for t in specs for v in t.get('variants', [])}
    active_specs = list(specs)
    active_definitions = {}
    definition_names = {}
    for test in active_specs:
        for variant in test.get('variants', []):
            definition = experiment_spec(test, variant)
            active_definitions.setdefault((test['id'], variant['id']), []).append(definition)
            definition_names[digest(definition)] = (test.get('name') or test['id'], variant.get('name') or variant['id'])
    rows, models, summaries = {}, {}, {}

    def row_for(definition, workflow, repetition, test_id, variant_id):
        current = workflow == fingerprint and definition in active_definitions.get((test_id, variant_id), [])
        key = digest({'definition': definition, 'workflow': workflow, 'repetition': repetition,
                      'test_id': test_id, 'variant_id': variant_id})
        test = definition.get('test', {}); variant = definition.get('variant', {})
        labels = definition_names.get(digest(definition), names.get((test_id, variant_id), (test_id, variant_id)))
        row = rows.setdefault(key, {'id': key, 'test_id': test_id, 'variant_id': variant_id,
            'name': labels[0], 'comparison_id': digest(test),
            'variant_name': labels[1],
            'repetition': repetition, 'current': current, 'revision': digest([definition, workflow])[:8], 'cells': {}})
        return row

    # Infer unrecorded cells from the active suite, not only from observed cases.
    for test in active_specs:
        if not test.get('enabled', True):
            continue
        for variant in test.get('variants', []):
            if variant.get('enabled', True) and has_objective_oracle(test, variant):
                definition = experiment_spec(test, variant)
                for rep in range(test.get('repetitions', 1)):
                    row_for(definition, fingerprint, rep, test['id'], variant['id'])

    excluded = 0
    for record in records:
        test_id = record.get('test_id', 'unknown'); variant_id = record.get('variant_id', 'unknown')
        test = record.get('test_definition', {}); variant = record.get('variant_definition', {})
        definition = experiment_spec(test, variant)
        if not test and not variant:
            known = definitions.get((test_id, variant_id))
            objective = has_objective_oracle(known['test'], known['variant']) if known else type(record.get('score', {}).get('exact_match')) is bool
        else:
            objective = has_objective_oracle(test, variant)
        if test_id.startswith('dialogue_test_') or not objective:
            excluded += 1
            continue
        cid = record['case_id']
        artifact = record.get('artifact_identity') or record.get('artifact_hashes', {})
        execution = record.get('execution_class', 'legacy_unverified')
        simulated = bool(record.get('simulated'))
        model = record['model_id'] + ':' + digest([artifact, execution, simulated])[:12]
        files = artifact.get('files', []) if isinstance(artifact, dict) else []
        label = ', '.join(f['name'] for f in files if 'name' in f) or record.get('model_name') or record['model_id']
        models[model] = {'id': model, 'model_id': record['model_id'], 'label': label,
                         'execution_class': execution, 'simulated': simulated}
        definition = experiment_spec(record.get('test_definition', {}), record.get('variant_definition', {}))
        workflow = record.get('provenance', {}).get('workflow_code')
        test_id = record.get('test_id', 'unknown'); variant_id = record.get('variant_id', 'unknown')
        row = row_for(definition, workflow, record.get('repetition', 0), test_id, variant_id)
        summaries[cid] = {'case_id': cid, 'model': model, 'outcome': outcome(record), 'current': row['current'],
            'metadata': {key: record[key] for key in ('model_id', 'test_id', 'variant_id', 'repetition', 'status',
                'score', 'timed_out', 'timeout_seconds', 'watchdog_seconds', 'measurement_valid', 'error', 'reason', 'pipeline_seconds', 'execution_class',
                'target', 'provenance', 'capability_policy', 'feature_applicability') if key in record},
            'output_preview': json.dumps(record.get('outputs', {}), ensure_ascii=False)[:4000],
            'oracle_preview': json.dumps({k: record.get('variant_definition', {}).get(k) for k in
                ('expected_answers', 'result')}, ensure_ascii=False)[:4000]}

        def add_cell(destination, reference):
            cell = destination['cells'].setdefault(model, {'ids': [], 'primary_ids': [], 'reference_ids': []})
            if cid not in cell['ids']:
                cell['ids'].append(cid)
            key = 'reference_ids' if reference else 'primary_ids'
            if cid not in cell[key]:
                cell[key].append(cid)
            if not reference and cid in cell['reference_ids']:
                cell['reference_ids'].remove(cid)

        add_cell(row, False)
        for alias in record.get('aliases', []):
            requested = alias.get('requested_definition')
            if not isinstance(requested, dict) or not has_objective_oracle(requested.get('test', {}), requested.get('variant', {})):
                continue
            alias_row = row_for(requested, workflow, alias['repetition'], alias['test_id'], alias['variant_id'])
            if alias_row['id'] != row['id']:
                add_cell(alias_row, True)

    ordered_models = sorted(models.values(), key=lambda m: (m['label'], m['id']))
    nicknames = {}
    for model in ordered_models:
        nickname = model_nickname(model['label'])
        nicknames.setdefault(nickname, []).append(model)
    for nickname, group in nicknames.items():
        for index, model in enumerate(group):
            model['nickname'] = nickname + (f' #{index + 1}' if len(group) > 1 else '')
    ordered_rows = sorted(rows.values(), key=lambda r: (not r['current'], r['test_id'], r['comparison_id'], r['variant_id'], r['revision'], r['repetition']))
    empty = {'ids': [], 'primary_ids': [], 'reference_ids': []}
    model_totals = {m['id']: totals([r['cells'].get(m['id'], empty) for r in ordered_rows], summaries) for m in ordered_models}
    return {'models': ordered_models, 'rows': ordered_rows, 'records': summaries, 'totals': model_totals, 'excluded_records': excluded,
            'note': 'Only tests with a fixed answer or final-state oracle appear here. Timeout is a run limit, not part of test identity or row grouping. Actual deadlines remain in saved run evidence. Dialogue and other open-ended generation are reserved for a separate view; their saved evidence is preserved. Totals count unique saved observations. Reference cells do not add trials. All-results totals are descriptive across saved configurations; use Current definitions to exclude historical experiments. Colors use original exact-match scores. Not-recorded cells are not failures or necessarily pending work. Skipped, invalid and infrastructure failures remain separate from semantic failures.'}