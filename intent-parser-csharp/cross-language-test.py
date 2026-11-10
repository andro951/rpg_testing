#!/usr/bin/env python3
"""Offline C#/Python wire conformance. No expected answers enter normalization."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PYTHON_REFERENCE = Path(os.environ.get('PYTHON_REFERENCE', ROOT.parent / 'rpg_testing'))
sys.path.insert(0, str(PYTHON_REFERENCE))
import intent_parser as py

cases = []
for filename in ['fixtures/parity-fixtures.json', 'fixtures/optional-parity-fixtures.json', 'fixtures/shared-fixtures.json', 'fixtures/current-revision-fixtures.json', 'fixtures/current-contract-regressions.json', 'robustness-parity-fixtures.json']:
    for record in json.loads((ROOT / filename).read_text()):
        options = dict(record.get('options', {}))
        for action in ['parse', 'normalize']:
            cases.append({'action': action, 'text': record.get('text', record.get('output')), 'input': record['input'], 'options': options})
        cases.append({'action': 'normalize', 'text': record.get('text', record.get('output')), 'input': record['input'], 'options': {**options, 'json_patch': True}})
        if filename.endswith('current-revision-fixtures.json'):
            cases.append({'action': 'diagnostics', 'text': record['text'], 'input': record['input'], 'options': options})
            cases.append({'action': 'replay', 'records': [record], 'options': {'json_patch': True}})

for path in ['', '/items/1/v', '/items/"1"/v', '/items/true/v', '/items/null/v', '/items/"a/b"/v', '/a~1b/~0', '/items/1e-7/v', '/items/0.000001/v', '/items/-0/v', '/items/"\\ud83d\\ude00"/v', '/items/"x"suffix/v', '/items/"unfinished/v', '/items/1e-400/v', '/items/~2/v']:
    cases.append({'action':'parse', 'text':'update path:'+json.dumps(path)+' value:2', 'options':{'pathSyntax':'value_patch'}})
for text in ['remove path:a'+('\n,\n'*2000)+'remove path:b', '\n'*20000+'remove path:a', 'remove path:a'+('\n'*20000), 'op:update path:a value:-0', 'op:update path:a value:1e-7', 'op:update path:a value:0.000001', 'op:update path:a value:"\\ud800"', 'op:update path:a value:"\\ud83d\\ude00"']:
    cases.append({'action':'normalize','text':text,'input':{'a':0,'b':1}})
for document in [{'2':'two','1':'one','0':-0.0,'a':'😀'}, {'n':1e-7,'m':0.000001,'unicode':'箱\u2028é','v':-0.0}, {'id':True,'q':'"quoted"','control':'x\ny'}]:
    cases.append({'action':'prompt','input':document,'request':'Update safely.','options':{'idKey':'key'}})

input_text=''.join(json.dumps(c,ensure_ascii=True,separators=(',',':'))+'\n' for c in cases)
dotnet=os.environ.get('DOTNET','dotnet')
process=subprocess.run([dotnet,str(ROOT/'bin/Debug/net8.0/IntentParser.dll'),'--json-lines'],input=input_text,text=True,capture_output=True,check=True)
actual=[json.loads(line) for line in process.stdout.splitlines()]

def compare(a,b):
    if type(a) is dict and type(b) is dict:
        return set(a)==set(b) and all(compare(a[k],b[k]) for k in a)
    if type(a) is list and type(b) is list:
        return len(a)==len(b) and all(compare(x,y) for x,y in zip(a,b))
    if type(a) in (int,float) and type(b) in (int,float):
        return a==b
    return type(a) is type(b) and a==b

def invoke(c):
    opt=c.get('options',{}); action=c['action']
    if action=='parse': return py.parse_intent(c['text'],opt)
    if action=='diagnostics': return py.parse_intent_with_diagnostics(c['text'],opt)
    if action=='normalize': return py.normalize_intent(c['text'],c['input'],opt)
    if action=='prompt': return py.build_prompt({'request':c['request'],'document':c['input'],'idKey':opt.get('idKey','id')})
    if action=='replay': return py.replay_prepared(c['records'],opt)
    raise ValueError(action)

def scrub_errors(result):
    if type(result) is dict:
        return {k:scrub_errors(v) for k,v in result.items() if k!='error'}
    if type(result) is list:return [scrub_errors(v) for v in result]
    return result

failures=[]
for i,(case,received) in enumerate(zip(cases,actual)):
    try: expected={'ok':True,'result':invoke(copy.deepcopy(case))}
    except Exception as error: expected={'ok':False,'error':str(error)}
    if not compare(scrub_errors(expected),scrub_errors(received)):
        failures.append({'index':i,'case':case,'python':expected,'csharp':received})
report={'mode':'offline-native-cross-language-conformance','total':len(cases),'received':len(actual),'failed':len(failures),'failures':failures}
(ROOT/'cross-language-results.json').write_text(json.dumps(report,indent=2,ensure_ascii=True)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='failures'}))
if failures:
    print(json.dumps(failures[:5],indent=2,ensure_ascii=True))
    raise SystemExit(1)
