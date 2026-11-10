import collections, hashlib, json, sys
from pathlib import Path

b = Path(__file__).resolve().parent / 'verification'
root = b / 'desktop'
sys.path.insert(0, str(root))
from workbench.domain import ResultStore, digest
from workbench.workflows import messages
from evaluation.core import assess_record

model = sys.argv[1]
man = json.loads((b / 'manifest.json').read_text())
want = {(x['test_id'], x['variant_id']): x for x in man['requests']}
tests = {p.stem: json.loads(p.read_text(encoding='utf8')) for p in (b / 'test_specs').glob('*.json')}
store = ResultStore(root / 'results')
paths = sorted((store.root / model).glob('*.json'))
expected_count = 8
assert len(paths) == expected_count, (model, len(paths))
cells, evidence = {}, []
for p in paths:
    r = store.read(p)
    t = tests[r['test_id']]
    v = next(x for x in t['variants'] if x['id'] == r['variant_id'])
    spec = want[(t['id'], v['id'])]
    req = messages(t, v['steps'][0], {}, v)
    assert digest(req) == spec['message_digest']
    calls = r.get('calls', [])
    assert (calls and calls[0]['messages'] == req) or (not calls and (r.get('timed_out') or r.get('status') in ('error', 'aborted')))
    arm = spec['arm']
    key = (spec['fixture'], v['id'], r['repetition'])
    assert arm not in cells.setdefault(key, {})
    outcome = assess_record(r)['objective_outcome']
    cells[key][arm] = (r, outcome)
    evidence.append({'case_id': r['case_id'], 'test_id': r['test_id'], 'variant_id': v['id'], 'repetition': r['repetition'], 'arm': arm, 'outcome': outcome, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'path': str(p), 'request_captured': bool(calls)})
assert len(cells) == 4
pairs, unmatched = [], []
for key, v in sorted(cells.items()):
    if set(v) != {'original', 'twob_short_v1'}:
        assert expected_count in (13, 107) and len(v) == 1
        unmatched.append({'fixture': key[0], 'variant': key[1], 'repetition': key[2], 'present': list(v), 'reason': 'The matching observation has not been recorded; an interrupted request may have an uncertain outcome.'})
        continue
    a, c = v['original'][0], v['twob_short_v1'][0]
    assert a['artifact_identity'] == c['artifact_identity'] and a['target'] == c['target']
    assert all(r['load']['context']['allocated_tokens'] == 32768 for r in (a, c))
    if a.get('calls') and c.get('calls'):
        assert a['calls'][0]['sampling'] == c['calls'][0]['sampling']
    for field in ('source', 'state_schema', 'expected_state'):
        assert a['test_definition'][field] == c['test_definition'][field]
    pairs.append({'fixture': key[0], 'variant': key[1], 'repetition': key[2], 'original': v['original'][1], 'twob_short_v1': v['twob_short_v1'][1]})
assert len(unmatched) == (1 if expected_count == 107 else len(unmatched) if expected_count == 13 else 0)
assert len(pairs) + len(unmatched) == len(cells)
result = {'cohort': 'twob-short-verification-v1', 'model': model, 'observations': len(paths), 'matched_pairs': len(pairs), 'missing_pairs': 4 - len(cells), 'unmatched': unmatched, 'outcomes': {arm: dict(collections.Counter(p[arm] for p in pairs)) for arm in ('original', 'twob_short_v1')}, 'transitions': dict(collections.Counter(p['original'] + ' -> ' + p['twob_short_v1'] for p in pairs)), 'pairs': pairs, 'evidence': evidence}
d = b / 'audits'
d.mkdir(exist_ok=True)
(b / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('pairs', 'evidence')}, indent=2))
