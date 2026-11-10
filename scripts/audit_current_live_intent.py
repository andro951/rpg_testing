#!/usr/bin/env python3
"""Frozen current-suite audit. No inference; no import of overnight.py.

Both phases include reserved final inputs and require an explicit freeze ID.
References use synthetic answers only. Replay reads saved answers only after
the caller supplies the freeze authorization. Outputs are exclusively created.
"""
from __future__ import annotations
import argparse
import collections
import copy
import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
STRICT_WORKFLOW = '56502881bc3c89f6b58c8f5e755b32f58cbd675274ed5363293b598aaddf9787'


def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def source_hashes():
    # Include implementation and tests/scripts, excluding data, archives and caches.
    excluded = {'.git', '.local', '__pycache__', 'archives', 'results', '.venv', 'venv', 'node_modules'}
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(ROOT.rglob('*.py'))
            if not excluded.intersection(p.relative_to(ROOT).parts)}


class MockBackend:
    """Only backend this audit can instantiate. Returned timings are unavailable."""
    supports_cache = True
    supports_schema = True

    def __init__(self, raw):
        self.raw = raw

    def generate(self, messages, settings, schema, cache, cancel):
        return {'text': self.raw, 'finish_reason': 'stop', 'cached_tokens': None,
                'request_seconds': None, 'first_token_seconds': None,
                'usage': {}, 'timings': {}, 'raw_chunks': []}


def inventory(night, read_json, digest, experiment_spec):
    expected = {}
    protected = {}
    rounds = []
    for rd in sorted(night.glob('round-*')):
        if not rd.is_dir() or not (rd / 'manifest.json').exists():
            continue
        mp = rd / 'manifest.json'
        m = read_json(mp)
        check(digest(m['requests']) == m['scope_digest'], f'Scope digest mismatch: {mp}')
        protected[str(mp)] = sha(mp)
        for rel, wanted in m['files'].items():
            p = (rd / rel.replace('\\', '/')).resolve()
            check(rd.resolve() in p.parents, 'Manifest path escapes round directory')
            check(sha(p) == wanted, f'Manifest file hash mismatch: {p}')
            protected[str(p)] = wanted
        refs = read_json(rd / 'references.json')
        reference = {}
        for ref in refs:
            check(ref['test_id'] not in reference, 'Duplicate synthetic reference')
            check(ref.get('synthetic_reference_not_model_input') is True, 'Unlabelled reference')
            reference[ref['test_id']] = ref['operations']
        tests = {}
        for q in m['requests']:
            tid = q['test_id']
            if tid not in tests:
                tests[tid] = read_json(rd / 'desktop' / 'test_specs' / (tid + '.json'))
            t = tests[tid]
            variants = [v for v in t['variants'] if v['id'] == q['variant']]
            check(len(variants) == 1 and tid in reference, 'Missing variant/reference')
            v = variants[0]
            check(t.get('enabled', True) and v.get('enabled', True), 'Disabled manifest variant')
            check(v['result']['representation'] == 'dot_patch_v1', 'Wrong current representation')
            check('evaluator' not in v['result'], 'Frozen source is not the original strict contract')
            key = (m['round'], q['model'], tid, q['variant'])
            check(key not in expected, 'Duplicate manifest request identity')
            expected[key] = (q, t, v, reference[tid], digest(experiment_spec(t, v)))
        check(set(reference) == set(tests), 'Reference/manifest test coverage mismatch')
        rounds.append({'round': m['round'], 'scope_digest': m['scope_digest'],
                       'definitions': len(tests), 'variants': len(m['requests']),
                       'observations': sum(q['repetitions'] for q in m['requests'])})
    check(bool(rounds), 'No round manifests found')
    return expected, protected, rounds


def maintained_baseline(root):
    """Load only pure domain/scoring/workflow modules, never a runtime/backend."""
    root = root.resolve()
    protected = {}
    for name in ('dot_paths.py', 'value_paths.py', 'presentation.py'):
        original = root / 'workbench' / name
        current = ROOT / 'workbench' / name
        check(original.read_bytes().replace(b'\r\n', b'\n') == current.read_bytes().replace(b'\r\n', b'\n'),
              'Pure baseline dependency differs: ' + name)
        protected[str(original)] = sha(original)
    modules = {}
    for name in ('domain', 'scoring', 'workflows'):
        path = root / 'workbench' / (name + '.py')
        protected[str(path)] = sha(path)
        spec = importlib.util.spec_from_file_location('workbench._audit_baseline_' + name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module
    domain, scoring, workflows = (modules[n] for n in ('domain', 'scoring', 'workflows'))
    scoring.canonical = domain.canonical
    workflows.canonical = domain.canonical
    workflows.score_state = scoring.score_state
    workflows.parse = scoring.parse
    workflows.equal = scoring.equal
    check(domain.code_fingerprint() == STRICT_WORKFLOW, 'Maintained baseline workflow fingerprint differs')
    return modules, protected


def strict_case_identity(baseline, t, v, selected, sv):
    from workbench.domain import case_id
    model = {'id': 'audit-synthetic', 'files': ['audit.gguf'], 'required_vram_gb': 8}
    target = {'vram_gb': 8, 'gpu_name': 'synthetic-no-inference'}
    old = baseline['domain'].case_id(model, t, v, 0, target)
    check(case_id(model, t, v, 0, target) == old, 'Strict case ID differs from maintained baseline')
    check(case_id(model, selected, sv, 0, target) != old, 'Selected case ID equals strict baseline')
    return old


def identity_check(t, v, selected, sv, output):
    from workbench.domain import (ENGINE_VERSION, digest, experiment_spec, case_id,
                                  code_fingerprint, ResultStore)
    from workbench.planning import pending_plan
    check(code_fingerprint() == STRICT_WORKFLOW, 'Strict workflow fingerprint changed')
    model = {'id': 'audit-synthetic', 'files': ['audit.gguf'], 'required_vram_gb': 8}
    target = {'vram_gb': 8, 'gpu_name': 'synthetic-no-inference'}
    old = case_id(model, t, v, 0, target)
    calculated = digest({'engine': ENGINE_VERSION, 'workflow_code': STRICT_WORKFLOW,
                         'model': model['id'], 'artifact_pin': {},
                         'experiment': experiment_spec(t, v), 'repetition': 0,
                         'target': target})
    check(old == calculated, 'Strict case ID changed')
    new = case_id(model, selected, sv, 0, target)
    check(new != old, 'Selected evaluator did not change case ID')
    # Isolated synthetic store, never a real result folder; wrong answers stay terminal.
    with tempfile.TemporaryDirectory(prefix='synthetic-resume-', dir=output) as tmp:
        store = ResultStore(pathlib.Path(tmp))
        store.save({'case_id': old, 'model_id': model['id'], 'test_id': t['id'],
                    'variant_id': v['id'], 'repetition': 0, 'status': 'completed',
                    'score': {'valid': True, 'exact_match': False},
                    'test_definition': t, 'variant_definition': v, 'target': target,
                    'provenance': {'workflow_code': STRICT_WORKFLOW}})
        one = copy.deepcopy(t)
        one['variants'] = [copy.deepcopy(v)]
        one['repetitions'] = 1
        plan = pending_plan([model], [one], target, store)
        check(plan['pending'] == 0 and plan['complete'] == 1,
              'Completed wrong strict result was incorrectly reopened')
    return {'strict_case_id': old, 'selected_case_id': new,
            'strict_workflow_fingerprint': STRICT_WORKFLOW,
            'completed_wrong_strict_result_remains_terminal': True}


def aggregate(rows):
    counts = collections.Counter()
    latest = max((r['round'] for r in rows), default=None)
    for r in rows:
        key = (r['round'], r['role'], r['arm'], r['model'])
        counts[key + ('records',)] += 1
        if r.get('incomplete'):
            counts[key + ('incomplete',)] += 1
        for field in ('saved_strict_score', 'current_strict_score', 'selected_score'):
            score = r.get(field)
            if score is not None:
                counts[key + (field + '_exact',)] += int(score.get('exact_match') is True)
    groups = {}
    for key, value in sorted(counts.items()):
        group = groups.setdefault(key[:4], {'round': key[0], 'role': key[1],
                                 'arm': key[2], 'model': key[3]})
        group[key[4]] = value
    return {'groups': list(groups.values()), 'latest_round': latest,
            'latest_round_groups': [g for g in groups.values() if g['round'] == latest]}


def run(args):
    from workbench.domain import read_json, digest, experiment_spec, ResultStore
    from workbench.workflows import execute, evaluate
    from evaluation.live_intent import select, identity
    night = args.night_root.resolve()
    output = args.output.resolve()
    check(output != night and night not in output.parents, 'Output must be outside originals')
    check(not output.exists(), 'Output directory already exists; use a new exclusive directory')
    check(bool(args.freeze_id.strip()), 'Explicit freeze ID required for reserved final coverage')
    before = source_hashes()
    frozen = identity()
    if args.expected_fingerprint:
        check(frozen['fingerprint'] == args.expected_fingerprint, 'Evaluator freeze fingerprint mismatch')
    output.mkdir(parents=True, exist_ok=False)
    save(output / 'freeze.json', {'freeze_id': args.freeze_id, 'evaluator': frozen,
                                 'source_hashes': before, 'phase': args.phase,
                                 'live_inference': False})
    expected, protected, rounds = inventory(night, read_json, digest, experiment_spec)
    baseline, baseline_hashes = maintained_baseline(args.baseline_root)
    protected.update(baseline_hashes)
    rows = []
    identity_result = None
    selected_cache = {}
    def selected_definition(t, variant_id):
        key = digest(t)
        if key not in selected_cache:
            selected_cache[key] = select(t)
        st = selected_cache[key]
        return st, next(x for x in st['variants'] if x['id'] == variant_id)
    if args.phase == 'references':
        for key, (q, t, v, ops, spec_digest) in expected.items():
            st, sv = selected_definition(t, v['id'])
            if identity_result is None:
                identity_result = identity_check(t, v, st, sv, output)
            before_test = digest(t)
            raw = json.dumps(ops, ensure_ascii=False)
            strict_case_identity(baseline, t, v, st, sv)
            original_strict = baseline['workflows'].execute(t, v, MockBackend(raw))
            strict = execute(t, v, MockBackend(raw))
            check(strict['score'] == original_strict['score'], 'Strict reference score differs from maintained baseline')
            check(strict['outputs'] == original_strict['outputs'], 'Strict output retention differs from baseline')
            selected = execute(st, sv, MockBackend(raw))
            check(strict['score'].get('exact_match') is True, 'Strict synthetic reference failed: ' + str(key))
            check(selected['score'].get('exact_match') is True, 'Selected synthetic reference failed: ' + str(key))
            check(digest(strict['calls'][0]['messages']) == q['message_digest'], 'Strict messages changed')
            check(digest(selected['calls'][0]['messages']) == q['message_digest'], 'Selected messages changed')
            for result in (strict, selected):
                check(result['outputs'][v['result']['step']] == raw, 'Original synthetic output was changed')
                check(result['calls'][0]['text'] == raw, 'Original synthetic call was changed')
            # Never derive negatives from saved answers, or provide expected values to the parser.
            missing = '__audit_missing_scope__'
            state = t['source']['initial_state']
            while isinstance(state, dict) and missing in state:
                missing += '_'
            negatives = ['[', json.dumps([{'op': 'remove', 'path': missing}])]
            negative_results = []
            for negative in negatives:
                scored = execute(st, sv, MockBackend(negative))['score']
                check(scored.get('exact_match') is not True, 'Negative fixture falsely passed')
                negative_results.append(scored)
            check(digest(t) == before_test, 'Source definition mutated')
            row = {'round': key[0], 'model': q['model'], 'test_id': q['test_id'],
                   'variant_id': q['variant'], 'role': q['role'], 'arm': q['arm'],
                   'experiment_spec_digest': spec_digest,
                   'maintained_strict_score': original_strict['score'],
                   'current_strict_score': strict['score'], 'selected_score': selected['score'],
                   'synthetic_only': True, 'negative_scores': negative_results,
                   'messages_unchanged': True, 'original_output_retained': True}
            save(output / 'cases' / (digest(key) + '.json'), row)
            rows.append(row)
    else:
        index_path = (args.input_index or night.parent / 'csc592-outer-arrays-v1' / 'replay-inputs.json').resolve()
        check(output != index_path and index_path not in output.parents, 'Output overlaps input index')
        index = read_json(index_path)
        protected[str(index_path)] = sha(index_path)
        records = [i for i in index['inputs'] if i.get('cohort') == 'overnight']
        wanted = {(*key, rep) for key, (q, *_) in expected.items() for rep in range(q['repetitions'])}
        seen = set()
        for item in records:
            path = pathlib.Path(item['path']).resolve()
            check(night in path.parents, 'Indexed evidence lies outside selected night root')
            check(sha(path) == item['sha256'], 'Indexed evidence SHA256 mismatch')
            protected[str(path)] = item['sha256']
            record = ResultStore(path.parents[1]).read(path)
            key = (item['round'], record['model_id'], record['test_id'], record['variant_id'])
            check(key in expected, 'Saved result absent from manifest')
            q, t, v, _, spec_digest = expected[key]
            observation = (*key, record['repetition'])
            check(observation in wanted and observation not in seen, 'Duplicate/out-of-scope observation')
            seen.add(observation)
            check(item['role'] == q['role'] and item['arm'] == q['arm'], 'Role/arm mismatch')
            captured_t, captured_v = record['test_definition'], record['variant_definition']
            check(digest(experiment_spec(captured_t, captured_v)) == spec_digest, 'Captured definition mismatch')
            calls = record.get('calls', [])
            check(bool(calls) and digest(calls[0]['messages']) == q['message_digest'], 'Captured request mismatch')
            st = select(captured_t)
            sv = next(x for x in st['variants'] if x['id'] == captured_v['id'])
            if identity_result is None:
                identity_result = identity_check(captured_t, captured_v, st, sv, output)
            strict_case_identity(baseline, captured_t, captured_v, st, sv)
            incomplete = (record.get('status') != 'completed' or record.get('timed_out')
                          or any(c.get('finish_reason') not in ('stop', 'provider_completed')
                                 or c.get('incomplete') or c.get('timed_out') for c in calls))
            row = {'case_id': record['case_id'], 'round': key[0], 'model': q['model'],
                   'test_id': q['test_id'], 'variant_id': q['variant'],
                   'repetition': record['repetition'], 'role': q['role'], 'arm': q['arm'],
                   'source_path': str(path), 'source_sha256': item['sha256'],
                   'source_record_checksum': record['sha256'], 'experiment_spec_digest': spec_digest,
                   'saved_strict_score': copy.deepcopy(record.get('score')),
                   'incomplete': bool(incomplete), 'retried': False,
                   'selected_evaluator': sv['result']['evaluator']}
            if not incomplete:
                values = copy.deepcopy(record['outputs'])
                values_before = digest(values)
                check(isinstance(values.get(captured_v['result']['step']), str), 'Final raw output is not text')
                row['maintained_strict_score'] = baseline['workflows'].evaluate(captured_t, captured_v, values)
                row['current_strict_score'] = evaluate(captured_t, captured_v, values)
                check(row['maintained_strict_score'] == row['current_strict_score'],
                      'Strict replay score differs from maintained baseline')
                row['selected_score'] = evaluate(st, sv, values)
                check(digest(values) == values_before, 'Evaluation mutated saved output values')
                row['original_output_digest'] = values_before
            save(output / 'cases' / (record['case_id'] + '.json'), row)
            rows.append(row)
        check(seen == wanted, 'Missing expected observations')
    after = source_hashes()
    check(before == after and identity() == frozen, 'Implementation changed during audit')
    changed = [p for p, h in protected.items() if sha(pathlib.Path(p)) != h]
    check(not changed, 'Frozen source/evidence files changed during audit: ' + repr(changed))
    summary = {'phase': args.phase, 'freeze_id': args.freeze_id, 'evaluator': frozen,
               'rounds': rounds, 'records': len(rows), 'live_inference': False,
               'identity_checks': identity_result, 'source_hashes_before': before,
               'source_hashes_after': after, 'protected_file_hashes_before': protected,
               'protected_file_hashes_after': dict(protected),
               'all_source_and_evidence_unchanged': True, **aggregate(rows)}
    save(output / 'summary.json', summary)
    print(json.dumps({'output': str(output), 'phase': args.phase, 'records': len(rows),
                      'evaluator_fingerprint': frozen['fingerprint'],
                      'source_and_evidence_unchanged': True}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-root', type=pathlib.Path, required=True,
                        help='Original maintained checkout for exact pure strict-path comparisons')
    parser.add_argument('--night-root', type=pathlib.Path, required=True)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    parser.add_argument('--phase', choices=('references', 'replay'), required=True)
    parser.add_argument('--freeze-id', required=True,
                        help='Explicitly authorized code freeze ID; never invent one for held-out runs')
    parser.add_argument('--expected-fingerprint', help='Require this exact evaluator fingerprint')
    parser.add_argument('--input-index', type=pathlib.Path)
    args = parser.parse_args()
    run(args)


if __name__ == '__main__':
    main()
