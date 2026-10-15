"""Rebuild reviewed database definitions and exact prompt-only exports; no inference."""
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from workbench.domain import digest, experiment_spec, read_json
from workbench.judgements import review_lock
from workbench.workflows import messages
from .builder import ROOT, LABELS, METHODS, TASKS, TASK_TEMPLATES, compile_test, oracle

REPO = ROOT.parent
ARCHIVE = 'archives/test-suite-2026-10-14'


def write_json(path, value):
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


def remove_managed(root, relative):
    path = (root / relative).resolve()
    allowed = ((root/'test_specs').resolve(), (root/'prompts/patch-suite').resolve(), (root/'prompt-review').resolve())
    if not any(path.is_relative_to(folder) for folder in allowed) or path.suffix not in ('.txt', '.json'):
        raise ValueError('Refusing to remove an unmanaged generated path')
    path.unlink(missing_ok=True)
    # Remove only empty generated directories, never recurse into unrelated content.
    if path.parent != (root/'test_specs').resolve() and path.parent not in allowed:
        try:
            path.parent.rmdir()
        except OSError:
            pass


def build(root=REPO):
    data = read_json(ROOT/'fixtures.json')
    fixtures, methods = data['fixtures'], data['methods']
    reviews = read_json(ROOT/'reviews.json') if (ROOT/'reviews.json').exists() else {}
    pairs = [(fixture, method, compile_test(fixture, reviews, method)) for fixture in fixtures for method in methods]
    definitions = [test for _, _, test in pairs]
    if len({test['id'] for test in definitions}) != len(definitions):
        raise ValueError('Duplicate fixture/method identity')
    old_path = root/'prompts/patch-suite/manifest.json'
    old = read_json(old_path) if old_path.exists() else {'prompts': []}
    old_ids = {p['test_id'] for p in old['prompts']}
    current_ids = {t['id'] for t in definitions}
    unexpected = {p.stem for p in (root/'test_specs').glob('*.json')} - current_ids - old_ids
    if unexpected:
        raise ValueError('Unmanaged active definitions: ' + ', '.join(sorted(unexpected)))
    evaluation = read_json(root/ARCHIVE/'evaluation/catalog.json')
    samples = read_json(root/ARCHIVE/'evaluation/fixtures.json')
    for entry in evaluation['definitions']:
        entry['path'] = ARCHIVE + '/' + entry['path']
        entry['scope'] = 'archived'
    for entry in samples['fixtures']:
        entry['source_path'] = ARCHIVE + '/' + entry['source_path']
    groups = read_json(root/ARCHIVE/'reporting/grouping_metadata.json')
    timing = read_json(root/'reporting/timing_expectations.json')
    for test_id in old_ids:
        timing.pop(test_id, None)
    ready = bool(definitions) and all(test['enabled'] for test in definitions)
    manifest = {'version':'database-v3', 'status':'ready' if ready else 'pending_joint_prompt_review', 'model_runs_started_by_builder':0, 'prompts':[]}
    with review_lock(root):
        for number, (fixture, method, test) in enumerate(pairs, 1):
            path = root/'test_specs'/(test['id']+'.json')
            write_json(path, test)
            evaluation['definitions'].append({'id':test['id'], 'path':path.relative_to(root).as_posix(),
                'scope':'active' if test['enabled'] else 'pending_review', 'family':'database',
                'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'specific_requirements':fixture['name']+'; enforce the declared schema, unique identities and requested operations.',
                'variants':[v['id'] for v in test['variants']]})
            answer = oracle(fixture,method)
            groups[test['id']], timing[test['id']] = {}, {}
            slug = re.sub(r'[^a-z0-9]+', '-', fixture['name'].lower()).strip('-')
            for variant in test['variants']:
                prompt = variant['steps'][0]['prompt']
                preview = root/'prompts/patch-suite'/test['id']/(variant['id']+'.txt')
                review = root/'prompt-review'/f"{number:02d}-{slug}-{method.replace('_','-')}-{variant['id'].replace('_','-')}.txt"
                preview.parent.mkdir(parents=True, exist_ok=True)
                review.parent.mkdir(parents=True, exist_ok=True)
                preview.write_bytes(prompt.encode('utf-8'))
                review.write_bytes(prompt.encode('utf-8'))
                write_json(preview.with_suffix('.messages.json'), messages(test,variant['steps'][0],{},variant))
                manifest['prompts'].append({'test_id':test['id'], 'task':fixture['task'], 'method':method,
                    'presentation':variant['id'], 'file':preview.relative_to(root).as_posix(), 'review_file':review.relative_to(root).as_posix(),
                    'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(), 'enabled':test['enabled'],
                    'prompt_digest':test['prompt_builder']['prompt_digest']})
                identity = digest(experiment_spec(test,variant))
                groups[test['id']][variant['id']] = {'ability_category':'Database operations',
                    'task_type':'Database '+TASKS[fixture['task']][0].replace('_',' ').capitalize(),
                    'prompt_comparison_set':fixture['name'], 'test_version':'1', 'operation_method':METHODS[method]['name'],
                    'input_presentation':LABELS[variant['id']], 'reviewed_definition':identity}
                timing[test['id']][variant['id']] = {'definition_id':identity,'seconds':fixture['expected_seconds'],
                    'reason':'Initial expectation for a short database operation list over a small synthetic state.'}
                samples['fixtures'].append({'test_id':test['id'], 'variant_id':variant['id'], 'source_path':path.relative_to(root).as_posix(),
                    'label':'synthetic known pass, not model inference', 'outputs':{'patch':json.dumps(answer[0])}, 'expected_outcome':'PASS'})
        keep = {p['file'] for p in manifest['prompts']} | {p['review_file'] for p in manifest['prompts']}
        for entry in old['prompts']:
            for key in ('file','review_file'):
                name = entry.get(key)
                if name and name not in keep:
                    remove_managed(root,name)
                    if key == 'file':
                        remove_managed(root,str(Path(name).with_suffix('.messages.json')))
        for test_id in old_ids - current_ids:
            remove_managed(root,'test_specs/'+test_id+'.json')
        write_json(root/'evaluation/catalog.json',evaluation)
        write_json(root/'evaluation/fixtures.json',samples)
        write_json(root/'reporting/grouping_metadata.json',groups)
        write_json(root/'reporting/timing_expectations.json',timing)
        write_json(root/'prompts/patch-suite/manifest.json',manifest)
        lines = ['DATABASE SUITE — PROMPT REVIEW INDEX', '',
            f"{len(fixtures)} data cases, {len(set(TASK_TEMPLATES.values()))} task templates, {len(manifest['prompts'])} prompts.",
            'Ready for benchmark runs: all exact prompts approved.' if ready else 'Pending exact-prompt approval; unapproved cases remain disabled.',
            'No model inference is run by this builder. Both people must approve the exact prompts before running tests.',
            'prompt-review contains only complete prompts, one text file per prompt. The system message is empty.', '']
        lines.extend(p['review_file'] for p in manifest['prompts'])
        (root/'prompts/patch-suite/INDEX.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
        from tools.build_prompt_sharing import build as sharing
        write_json(root/'optimization/sharing.json',sharing(root))
    return {'definitions':len(definitions),'task_templates':len(set(TASK_TEMPLATES.values())), 'prompts':len(manifest['prompts']),
            'enabled':sum(t['enabled'] for t in definitions)}


if __name__ == '__main__':
    print(build())
