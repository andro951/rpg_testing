"""Compare saved development SSE content with calls and workflow values, without model calls."""
import collections, json, sys
from pathlib import Path

base = Path(__file__).resolve().parent
sys.path.insert(0, str(base / 'desktop'))
from workbench.domain import ResultStore
root = base.parent / 'literal-text-dev-v1' / 'desktop' / 'results'
store = ResultStore(root)
paths = sorted((root / 'local-81e2a88130ccfa4e').glob('*.json'))
assert len(paths) == 108
stats = collections.Counter()
examples = []
for path in paths:
    r = store.read(path)
    if r['variant_definition']['result']['representation'] != 'literal_line_v1':
        continue
    calls = r.get('calls', [])
    assert len(calls) == 1
    call = calls[0]
    chunks = call.get('raw_chunks', [])
    streamed = ''.join(choice.get('delta', {}).get('content') or '' for chunk in chunks for choice in chunk.get('choices', []))
    assert streamed == call['text'] == r['outputs']['patch'], path
    stats['verified'] += 1
    if streamed.endswith(' '): stats['literal_response_ends_space'] += 1
    if 'space' in r['test_id'].lower() or 'whitespace' in r['test_id'].lower():
        examples.append({'case':r['test_id'], 'variant':r['variant_id'], 'text':streamed, 'score':r.get('score')})
assert stats['verified'] == 54
print(json.dumps({'stats':dict(stats),'development_whitespace_examples':examples[:3]}, ensure_ascii=True, indent=2))
