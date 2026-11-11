#!/usr/bin/env python3
"""Compare new format IR in the actual GrammarForge, native Python and C# ports.

Build C# first. Override DOTNET when its SDK is not on PATH. No results/history
files are rewritten, and no models or expected-state evaluator are involved.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from intent_parser import parse_intent
from intent_parser.patch import equal

fixture = ROOT / 'intent-parser-js/unified-format-fixtures.json'
cases = json.loads(fixture.read_text())
js = r"""
const fs=require('node:fs'),api=require('./intent-parser-js');
const cases=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
console.log(JSON.stringify(cases.map(c=>{try{return {ok:true,result:api.parseIntent(c.text,c.options)}}catch{return {ok:false}}})));
"""
# Require the explicit CommonJS entry because this directory has no index.js.
js = js.replace("require('./intent-parser-js')", "require('./intent-parser-js/index.cjs')")
javascript = json.loads(subprocess.run(['node', '-e', js, str(fixture)], cwd=ROOT, capture_output=True, text=True, check=True).stdout)
wire = ''.join(json.dumps({'action': 'parse', 'text': c['text'], 'options': c.get('options', {})}) + '\n' for c in cases)
response = subprocess.run([os.environ.get('DOTNET', 'dotnet'), str(ROOT / 'intent-parser-csharp/bin/Debug/net8.0/IntentParser.dll'), '--json-lines'],
                          input=wire, capture_output=True, text=True, check=True)
csharp = [json.loads(line) for line in response.stdout.splitlines()]
if len(csharp) != len(cases):
    raise SystemExit('C# response count mismatch')
failures = []
for case, js_result, cs_result in zip(cases, javascript, csharp):
    try:
        python = {'ok': True, 'result': parse_intent(case['text'], case.get('options'))}
    except ValueError:
        python = {'ok': False}
    expected = {'ok': False} if case.get('reject') else {'ok': True, 'result': case['expected']}
    for language, result in [('javascript', js_result), ('python', python), ('csharp', cs_result)]:
        clean = {key: value for key, value in result.items() if key != 'error'}
        if not equal(clean, expected):
            failures.append({'case': case['name'], 'language': language, 'expected': expected, 'actual': clean})
print(json.dumps({'cases': len(cases), 'languages': 3, 'checks': len(cases) * 3, 'failed': len(failures)}))
if failures:
    print(json.dumps(failures, indent=2))
    raise SystemExit(1)
