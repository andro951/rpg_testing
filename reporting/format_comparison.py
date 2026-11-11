"""Read-only format comparison metadata and explicitly imported result summaries."""
import csv
import hashlib
from pathlib import Path


def format_pair(test, variant):
    builder = test.get('prompt_builder', {})
    output = builder.get('method') or variant.get('result', {}).get('representation')
    presentation = variant.get('state_presentation', test.get('state_presentation'))
    input_format = variant.get('id') if builder else presentation
    if not input_format or not output:
        return None
    return {'input': input_format, 'output': output}


def load_comparison(path):
    """Keep imported grading separate from the original immutable saved scores."""
    path = Path(path)
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'model', 'model_id', 'case', 'input_format', 'output_format', 'outcome', 'repetition'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Format comparison CSV is missing required columns')
        rows = list(reader)
    seen, models, observations = set(), {}, []
    for row in rows:
        key = tuple(row[k] for k in ('model_id', 'case', 'input_format', 'output_format', 'repetition'))
        if key in seen:
            raise ValueError('Duplicate format comparison condition: ' + repr(key))
        seen.add(key)
        if any(not row[k] for k in ('model', 'model_id', 'case', 'input_format', 'output_format')):
            raise ValueError('Empty format comparison identity')
        state = row['outcome'].lower()
        if state not in ('pass', 'fail', 'timeout', 'error', 'aborted', 'skipped', 'invalid', 'unscored', 'parser_gap'):
            raise ValueError('Unknown format comparison outcome: ' + state)
        if row['model_id'] in models and models[row['model_id']]['label'] != row['model']:
            raise ValueError('Conflicting model labels in format comparison')
        models[row['model_id']] = {'id': row['model_id'], 'label': row['model']}
        observations.append({'id': '|'.join(key), 'model': row['model_id'], 'input': row['input_format'],
                             'output': row['output_format'], 'outcome': state, 'case': row['case'],
                             'source_run': row.get('source_run'), 'evidence_kind': row.get('evidence_kind'),
                             'result_sha256': row.get('result_sha256')})
    return {'label': 'Current-series comparison', 'models': sorted(models.values(), key=lambda m: m['label']),
            'observations': observations, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'note': 'Latest-available current-series composite, not one globally identical prompt run. '
                    'Imported final-state pass/fail uses the unified current intent parser. '
                    'Original saved scores remain unchanged in the Results tab. '
                    'Each condition is counted once; Perchance is a remote service with capability-limited sampling.'}
