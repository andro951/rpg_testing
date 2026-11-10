import copy, json, sys
from pathlib import Path

b = Path(__file__).resolve().parent
sys.path.insert(0, str(b.parent / 'literal-text-branch-v2' / 'desktop'))
from workbench.dot_paths import apply
from marker import encode, decode

fixture = json.loads((b.parent / 'safe-text-heldout-v1' / 'test_specs' / 'safeheld_boundary_spaces__research_json_v2__literal_line_v2.json').read_text(encoding='utf8'))
initial = fixture['source']['initial_state']
schema = fixture['state_schema']
values = ['', '  leading', 'trailing  ', '  both  ', '|', 'ending|', 'in|side', r'\n', '\n', r'\"', '"', 'value: text: |', '\t']
count = 0
for value in values:
    for pos in range(3):
        ops = [{'op':'replace','path':'archive.docs.d1.text','value':'one'}, {'op':'replace','path':'archive.docs.d1.text','value':'two'}, {'op':'replace','path':'archive.docs.d1.text','value':'three'}]
        ops[pos]['value'] = value
        for final in ('', '\n'):
            wire = encode(ops) + final
            assert decode(wire) == ops, (repr(value), repr(wire))
            actual = apply(initial, decode(wire), schema)
            expected = copy.deepcopy(initial); expected['archive']['docs'][0]['text'] = ops[-1]['value']
            assert actual == expected
            count += 1
for raw in ('set archive.owner: text:no terminator', 'set archive.owner: text:bad\\q|', 'set archive.owner: text:bad\\s|'):
    try: decode(raw)
    except ValueError: pass
    else: raise AssertionError('Malformed record accepted: '+repr(raw))
ops = [{'op':'add','path':'archive.docs','value':{'doc_id':'d3','text':' | '}}, {'op':'remove','path':'archive.docs.d1'}, {'op':'replace','path':'archive.owner','value':' end |'}]
assert decode(encode(ops)) == ops
actual = apply(initial, decode(encode(ops)), schema)
assert actual['archive']['docs'] == [initial['archive']['docs'][1], {'doc_id':'d3','text':' | '}]
assert actual['archive']['owner'] == ' end |'
assert decode('none') == [] and decode('none\n') == []
print(f'PASS {count} round trips and state applications, plus object add/remove, no-op and malformed-output checks.')
print('Ending a raw string value with | is unambiguous: the final | is the terminator; any preceding | is data.')
