"""Read-only recovery audit. No inference, result edits, fetch, or publishing.

The baseline Git object must already be available locally. CI fetches that pinned
object before this script runs. Incorrect completed answers must also stay done.
"""
from __future__ import annotations
import argparse
import copy
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BASELINE = '78c6b154c8668fca7db128923d2d7893342baf8e'
FINGERPRINT_FILES = (
    'domain.py', 'workflows.py', 'scoring.py', 'backends.py', 'inventory.py',
    'presentation.py', 'seedcheck.py', 'native.py', 'scheduler.py',
    'execution_policy.py', 'telemetry.py',
)


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace').strip())
    return result.stdout


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def audit(root: Path, baseline: str) -> dict:
    require(bool(re.fullmatch(r'[0-9a-f]{40}', baseline)), 'Baseline must be a complete commit SHA.')
    sys.path.insert(0, str(root))
    from workbench.domain import (ResultStore, case_id, code_fingerprint, experiment_spec,
                                  load_tests, validate_test)
    from workbench.inventory import automatic_context
    from workbench.planning import pending_plan
    from workbench.preflight import _context_planning_tests
    from workbench.workflows import messages

    code_checks = {}
    for name in FINGERPRINT_FILES:
        old = git(root, 'show', baseline + ':workbench/' + name).replace(b'\r\n', b'\n')
        now = (root / 'workbench' / name).read_bytes().replace(b'\r\n', b'\n')
        code_checks[name] = old == now
        require(old == now, 'Fingerprint-bearing file changed: ' + name)

    names = git(root, 'ls-tree', '-r', '--name-only', baseline, '--', 'test_specs/').decode().splitlines()
    before = []
    for name in names:
        if not name.endswith('.json') or len(Path(name).parts) != 2:
            continue
        definition = json.loads(git(root, 'show', baseline + ':' + name))
        validate_test(definition)
        if definition.get('enabled', True):
            before.append(definition)
    after = load_tests(root / 'test_specs')
    by_id = {t['id']: t for t in after}
    context_old = automatic_context(before, {'planning.context_length': 2**63 - 1})['allocated_tokens']
    context_new = automatic_context(_context_planning_tests(after),
                                    {'planning.context_length': 2**63 - 1})['allocated_tokens']
    require(context_old == context_new, f'Context recipe changed: {context_old} -> {context_new}')

    model = {'id': 'identity-audit-fixture', 'required_vram_gb': 8,
             'files': ['audit.gguf'], 'sha256': {'audit.gguf': 'a' * 64}}
    target = {'vram_gb': 8, 'context_recipe': context_old, 'backend': 'identity-audit-only'}
    checked = 0
    prompt_checks = 0
    with tempfile.TemporaryDirectory(prefix='rpg-identity-audit-') as temp:
        store = ResultStore(Path(temp))
        for old_test in before:
            require(old_test['id'] in by_id, 'Existing test removed: ' + old_test['id'])
            new_test = by_id[old_test['id']]
            new_variants = {v['id']: v for v in new_test['variants']}
            for old_variant in old_test['variants']:
                if not old_variant.get('enabled', True):
                    continue
                label = old_test['id'] + '/' + old_variant['id']
                require(old_variant['id'] in new_variants, 'Existing variant removed: ' + label)
                new_variant = new_variants[old_variant['id']]
                require(new_variant.get('enabled', True), 'Existing variant disabled: ' + label)
                require(experiment_spec(old_test, old_variant) == experiment_spec(new_test, new_variant),
                        'Existing experiment definition changed: ' + label)
                require(new_test.get('repetitions', 1) >= old_test.get('repetitions', 1),
                        'Existing repetitions removed: ' + label)
                # Compare every old generated request with deterministic previous outputs.
                def check_steps(old_steps, new_steps):
                    nonlocal prompt_checks
                    for old_step, new_step in zip(old_steps, new_steps):
                        if old_step['type'] == 'loop':
                            check_steps(old_step['steps'], new_step['steps'])
                        else:
                            values = {key: 'identity-audit previous output' for key in old_step.get('uses', [])}
                            require(messages(old_test, old_step, values, old_variant) ==
                                    messages(new_test, new_step, values, new_variant),
                                    'Existing model-facing request changed: ' + label + '/' + old_step['id'])
                            prompt_checks += 1
                check_steps(old_variant['steps'], new_variant['steps'])
                for rep in range(old_test.get('repetitions', 1)):
                    old_id = case_id(model, old_test, old_variant, rep, target)
                    new_id = case_id(model, new_test, new_variant, rep, target)
                    require(old_id == new_id, 'Existing case ID changed: ' + label)
                    store.save({'status': 'completed', 'model_id': model['id'], 'case_id': old_id,
                                'test_id': old_test['id'], 'variant_id': old_variant['id'],
                                'repetition': rep, 'score': {'valid': True, 'exact_match': False}})
                    checked += 1
        original_plan = pending_plan([model], before, target, store)
        recovered_plan = pending_plan([model], after, target, store)
        require(original_plan['pending'] == 0, 'Baseline synthetic completion check failed.')
        require(recovered_plan['complete'] == checked, 'Old completed cases did not all remain complete.')
        old_keys = {(t['id'], v['id'], rep) for t in before for v in t['variants']
                    if v.get('enabled', True) for rep in range(t.get('repetitions', 1))}
        pending_keys = {(j['test']['id'], j['variant']['id'], j['repetition'])
                        for g in recovered_plan['groups'] for j in g['jobs']}
        require(not old_keys & pending_keys, 'An old completed case became pending.')

    real_results = []
    result_root = root / 'results'
    if result_root.is_dir():
        real_store = ResultStore(result_root)
        rows = [r for r in real_store.all() if not r.get('simulated')
                and r.get('execution_class', 'full_gpu') == 'full_gpu'
                and r.get('target') and r.get('provenance', {}).get('workflow_code') == code_fingerprint()]
        latest = {}
        for record in rows:
            mid = record['model_id']
            key = record.get('finished_at', record.get('started_at', ''))
            if mid not in latest or key > latest[mid][0]:
                latest[mid] = (key, record)
        for mid, (_, record) in sorted(latest.items()):
            real_target = copy.deepcopy(record['target'])
            real_target['context_recipe'] = context_new
            real_model = {'id': mid, 'required_vram_gb': 8,
                          'artifact_identity': record.get('artifact_identity'),
                          'sha256': record.get('artifact_hashes', {}),
                          'files': list(record.get('artifact_hashes', {})) or ['metadata-only.gguf']}
            a = pending_plan([real_model], before, real_target, real_store)
            b = pending_plan([real_model], after, real_target, real_store)
            old_pending = {j['case_id'] for g in a['groups'] for j in g['jobs']}
            new_old_pending = {j['case_id'] for g in b['groups'] for j in g['jobs']
                               if (j['test']['id'], j['variant']['id'], j['repetition']) in old_keys}
            require(new_old_pending == old_pending, 'Stored old completion was invalidated for ' + mid)
            real_results.append({'model_id': mid, 'before_complete': a['complete'],
                                 'before_pending': a['pending'], 'after_complete': b['complete'],
                                 'after_pending': b['pending'], 'newly_invalidated_old_cases': 0})
    return {'baseline_commit': baseline,
            'current_commit': git(root, 'rev-parse', 'HEAD').decode().strip(),
            'fingerprint_files_unchanged': code_checks, 'workflow_code': code_fingerprint(),
            'context_recipe_before': context_old, 'context_recipe_after': context_new,
            'existing_model_requests_checked': prompt_checks,
            'existing_cases_checked_per_model': checked,
            'new_cases_per_model': recovered_plan['pending'],
            'total_cases_per_model': checked + recovered_plan['pending'],
            'newly_invalidated_old_cases': 0, 'stored_result_plans': real_results,
            'inference_performed': False, 'results_modified': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--baseline', default=BASELINE)
    args = parser.parse_args()
    try:
        report = audit(args.root.resolve(), args.baseline)
    except Exception as exc:
        print(f'AUDIT FAILED: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
