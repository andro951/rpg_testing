"""Rebuild definitions and exact request previews; never execute benchmarks."""
import hashlib
import json
import os
import tempfile
from pathlib import Path

from workbench.domain import digest, experiment_spec, read_json
from workbench.judgements import review_lock
from workbench.workflows import messages
from .builder import ROOT, LABELS, TASKS, compile_test, oracle

REPO = ROOT.parent
ARCHIVE = 'archives/test-suite-2026-10-14'


def write_json(path, value):
    """Atomic LF output agrees with Git attributes on Windows and Linux."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build(root=REPO):
    fixtures = read_json(ROOT / 'fixtures.json')['fixtures']
    reviews = read_json(ROOT / 'reviews.json') if (ROOT / 'reviews.json').exists() else {}
    definitions = [compile_test(fixture, reviews) for fixture in fixtures]
    if len({test['id'] for test in definitions}) != len(definitions):
        raise ValueError('Duplicate fixture identity')
    expected_files = {test['id'] + '.json' for test in definitions}
    unexpected = {p.name for p in (root/'test_specs').glob('*.json')} - expected_files
    if unexpected:
        raise ValueError('Unmanaged active definitions; archive them before rebuilding: ' + ', '.join(sorted(unexpected)))
    evaluation = read_json(root / ARCHIVE / 'evaluation/catalog.json')
    samples = read_json(root / ARCHIVE / 'evaluation/fixtures.json')
    for entry in evaluation['definitions']:
        entry['path'] = ARCHIVE + '/' + entry['path']
        entry['scope'] = 'archived'
    for entry in samples['fixtures']:
        entry['source_path'] = ARCHIVE + '/' + entry['source_path']
    groups = read_json(root / ARCHIVE / 'reporting/grouping_metadata.json')
    timing = read_json(root / 'reporting/timing_expectations.json')
    manifest = {'status': 'pending_joint_prompt_review', 'model_runs_started_by_builder': 0, 'prompts': []}
    with review_lock(root):
        for fixture, test in zip(fixtures, definitions):
            path = root / 'test_specs' / (test['id'] + '.json')
            write_json(path, test)
            evaluation['definitions'].append({'id': test['id'], 'path': path.relative_to(root).as_posix(),
                'scope': 'active' if test['enabled'] else 'pending_review',
                'family': 'index' if TASKS[fixture['task']][0] == 'index' else 'array',
                'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'specific_requirements': fixture['name'] + '; preserve unrelated state and enforce the requested output contract.',
                'variants': [v['id'] for v in test['variants']]})
            answer = oracle(fixture)
            groups[test['id']] = {}
            timing[test['id']] = {}
            for variant in test['variants']:
                step = variant['steps'][0]
                preview = root / 'prompts/patch-suite' / test['id'] / (variant['id'] + '.txt')
                preview.parent.mkdir(parents=True, exist_ok=True)
                preview.write_text(step['prompt'] + '\n', encoding='utf-8', newline='\n')
                write_json(preview.with_suffix('.messages.json'), messages(test, step, {}, variant))
                manifest['prompts'].append({'test_id': test['id'], 'task': fixture['task'], 'presentation': variant['id'],
                    'file': preview.relative_to(root).as_posix(), 'prompt_sha256': hashlib.sha256(step['prompt'].encode()).hexdigest(),
                    'enabled': test['enabled'], 'prompt_digest': test['prompt_builder']['prompt_digest']})
                identity = digest(experiment_spec(test, variant))
                groups[test['id']][variant['id']] = {
                    'ability_category': 'Array index calculations' if TASKS[fixture['task']][0] == 'index' else 'JSON Patch operations',
                    'task_type': fixture['task'].replace('_', ' ').capitalize(),
                    'prompt_comparison_set': fixture['name'], 'test_version': '1',
                    'input_presentation': LABELS[variant['id']], 'reviewed_definition': identity}
                timing[test['id']][variant['id']] = {'definition_id': identity, 'seconds': fixture['expected_seconds'],
                    'reason': 'Initial expectation for a short index answer.' if TASKS[fixture['task']][0] == 'index' else 'Initial expectation for one patch operation over a small synthetic state.'}
                samples['fixtures'].append({'test_id': test['id'], 'variant_id': variant['id'],
                    'source_path': path.relative_to(root).as_posix(), 'label': 'synthetic known pass, not model inference',
                    'outputs': {'index': answer} if TASKS[fixture['task']][0] == 'index' else {'patch': json.dumps(answer[0])},
                    'expected_outcome': 'PASS'})
        write_json(root / 'evaluation/catalog.json', evaluation)
        write_json(root / 'evaluation/fixtures.json', samples)
        write_json(root / 'reporting/grouping_metadata.json', groups)
        write_json(root / 'reporting/timing_expectations.json', timing)
        write_json(root / 'prompts/patch-suite/manifest.json', manifest)
        lines = ['PATCH SUITE — PROMPT REVIEW INDEX', '',
                 f"{len(definitions)} data cases, {len({f['task'] for f in fixtures})} templates, {len(manifest['prompts'])} prompts. This build does not run benchmark inference.",
                 'A case is enabled only after Isaac and the assistant accept its exact prompts.',
                 'Each .txt file contains the complete user message. The adjacent .messages.json records the exact role fields.',
                 'The system message is empty. All task instructions are in the user message.', '',
                 'Paths below are relative to the repository root.', '']
        for number, test in enumerate(definitions, 1):
            lines.append(str(number) + '. ' + test['name'])
            lines.extend('   ' + entry['file'] for entry in manifest['prompts'] if entry['test_id'] == test['id'])
            lines.append('')
        (root/'prompts/patch-suite/INDEX.txt').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
        from tools.build_prompt_sharing import build as sharing
        write_json(root / 'optimization/sharing.json', sharing(root))
    return {'definitions': len(definitions), 'templates': len({f['task'] for f in fixtures}),
            'prompts': len(manifest['prompts']), 'enabled': sum(t['enabled'] for t in definitions)}


if __name__ == '__main__':
    print(build())
