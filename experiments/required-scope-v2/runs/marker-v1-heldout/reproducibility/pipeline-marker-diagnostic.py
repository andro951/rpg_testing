"""Synthetic SSE -> NativeBackend -> workflow -> ResultStore -> evaluators; no inference."""
import copy, io, json, sys, tempfile
from pathlib import Path
from unittest.mock import patch

base = Path(__file__).resolve().parent
v1 = True
root = base / 'runtime'
sys.path.insert(0, str(root))
from workbench.backends import Transport
from workbench.native import NativeBackend
from workbench.workflows import execute
from workbench.domain import ResultStore
from workbench.literal_line import encode, decode
from evaluation.core import assess_record

fixture_path = base.parent / 'marker-v1-development' / 'test_specs' / 'literaldev_whitespace__research_json_v2__literal_line_marker_v1.json'
fixture = json.loads(fixture_path.read_text(encoding='utf8'))
variant = copy.deepcopy(fixture['variants'][0])
variant['result']['required_ops'] = ['replace'] * 3
values = ['  lead', 'tail  ', '  both  ', '', r'backslash-n: \n', 'actual\nnewline', r'backslash-quote: \"', 'quote: "']
values[5] = 'actual\nnewline'.replace('\\n', '\n')

class Response:
    status = 200
    def __init__(self, path, wire):
        if path == '/apply-template': self.payload = json.dumps({'prompt':'synthetic'}).encode(); return
        if path == '/tokenize': self.payload = json.dumps({'tokens':[1, 2]}).encode(); return
        assert path == '/v1/chat/completions'
        # Split inside prefixes, escapes and trailing spaces; JSON encoding handles all data bytes.
        pieces = [wire[i:i+3] for i in range(0, len(wire), 3)]
        events = [{'choices':[{'delta':{'content':p},'finish_reason':None}]} for p in pieces]
        events.append({'choices':[{'delta':{},'finish_reason':'stop'}]})
        self.stream = io.BytesIO(b''.join(b'data: '+json.dumps(e, ensure_ascii=False).encode('utf8')+b'\n\n' for e in events)+b'data: [DONE]\n\n')
    def read(self, *args): return self.payload
    def readline(self): return self.stream.readline()

def raw_value(v):
    return v.replace('\\','\\\\').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')

count = 0
with tempfile.TemporaryDirectory(prefix='literal-pipeline-') as tmp:
    store = ResultStore(Path(tmp))
    for pos in range(3):
        for value in values:
            for canonical in (True, False):
                for final_newline in (False, True):
                    test = copy.deepcopy(fixture)
                    docs = test['source']['initial_state']['service']['tickets'] if v1 else test['source']['initial_state']['archive']['docs']
                    docs.append({'ticket_id':'t3','message':'old3','priority':3} if v1 else {'doc_id':'d3','text':'old3'})
                    target_values = ['one', 'two', 'three']
                    target_values[pos] = value
                    expected = copy.deepcopy(test['source']['initial_state'])
                    ops = []
                    for i, target in enumerate(target_values):
                        if v1:
                            expected['service']['tickets'][i]['message'] = target
                            path = f'service.tickets.t{i+1}.message'
                        else:
                            expected['archive']['docs'][i]['text'] = target
                            path = f'archive.docs.d{i+1}.text'
                        ops.append({'op':'replace','path':path,'value':target})
                    test['expected_state'] = expected
                    wire = encode(ops) if canonical else '\n'.join('set '+o['path']+': text:'+raw_value(o['value'])+'|' for o in ops)
                    if final_newline: wire += '\n'
                    assert decode(wire) == ops, (pos, repr(value), repr(wire))
                    class Connection:
                        sock = None
                        def __init__(self,*a,**k): pass
                        def request(self, method, path, body=None, headers=None): self.path = path
                        def getresponse(self): return Response(self.path, wire)
                        def close(self): pass
                    native = NativeBackend.__new__(NativeBackend)
                    native.transport = Transport('http://127.0.0.1:12345')
                    native.load_metadata = {}; native.context = 32768; native.owned_id = 'synthetic'
                    with patch('http.client.HTTPConnection', Connection):
                        result = execute(test, variant, native)
                    assert result['outputs']['patch'] == wire, ('transport/workflow changed bytes', repr(wire), repr(result['outputs'].get('patch')))
                    assert result['calls'][0]['text'] == wire
                    assert result['score']['exact_match'], (repr(value), result['score'])
                    cid = f'{count:064x}'
                    record = {'status':'completed','case_id':cid,'model_id':'synthetic','test_definition':test,'variant_definition':variant,**result}
                    path = store.save(record)
                    readback = store.read(path)
                    assert readback['outputs']['patch'] == wire and readback['calls'][0]['text'] == wire
                    verdict = assess_record(readback)
                    assert verdict['objective_outcome'] == 'PASS', verdict
                    count += 1
print(f'PASS {count} full-path cases on marker-v1: real SSE transport, native response extraction, workflow, persistent JSON, parser, state scorer and independent evaluator.')
print('Covers first/middle/last update; raw and encoded spaces; final newline present/absent; empty; literal backslash+n versus actual newline; literal backslash+quote.')
