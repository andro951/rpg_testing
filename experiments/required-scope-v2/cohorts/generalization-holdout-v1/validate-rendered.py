import json,sys
from pathlib import Path
base=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task\holdout-v1');snapshot=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task\required-scope-v2\path-list-unity-run\common-repo');sys.path.insert(0,str(snapshot))
from workbench.dot_paths import resolve
from workbench.value_paths import resolve as slash_resolve
from workbench.path_list import decode
from jsonschema import Draft202012Validator
for f in sorted((base/'test_specs').glob('*.json')):
 t=json.loads(f.read_text(encoding='utf8'));Draft202012Validator(t['state_schema']).validate(t['source']['initial_state']);Draft202012Validator(t['state_schema']).validate(t['expected_state']);v=next(v for v in t['variants'] if v['id']=='full_paths');lines=v['prompt_bindings']['current_state'].splitlines()
 for line in lines:
  p,x=line.split(':',1);value=json.loads(x)
  if v['result']['representation']=='path_list_v1':p=decode('set '+p+': null')[0]['path']
  resolver=slash_resolve if v['result']['representation']=='value_patch' else resolve;actual,_,_=resolver(t['source']['initial_state'],t['state_schema'],p);assert actual==value,(f.name,p,actual,value)
 print(t['id'],'leaf_paths',len(lines),'task:',v['prompt_bindings']['new_information'])
print('All full-path views resolved to their true values; schemas validate; no extra model runs.')

