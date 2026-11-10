import json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;root=b.parent/'dot-rewrite-heldout-v1'/'desktop';sys.path.insert(0,str(root))
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from workbench.dot_paths import resolve
from evaluation.core import assess
from jsonschema import Draft202012Validator
man=json.loads((b/'manifest.json').read_text(encoding='utf8'));refs=json.loads((b/'references.json').read_text(encoding='utf8'));tests={p.stem:json.loads(p.read_text(encoding='utf8')) for p in (b/'test_specs').glob('*.json')};old=json.loads(next((b.parent/'dot-escape-heldout-v1'/'test_specs').glob('*__research_json_v2.json')).read_text(encoding='utf8'));head=old['variants'][0]['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0];assert len(tests)==3 and len(man['requests'])==6
for t in tests.values():
 validate_test(t);assert t['repetitions']==1 and {v['id'] for v in t['variants']}=={'normal_json','full_paths'};Draft202012Validator(t['state_schema']).validate(t['source']['initial_state']);Draft202012Validator(t['state_schema']).validate(t['expected_state']);v0,v1=t['variants'];assert v0['result']==v1['result'] and v0['steps'][0]['sampling']==v1['steps'][0]['sampling'] and v0['prompt_bindings']['new_information']==v1['prompt_bindings']['new_information']
 for v in t['variants']:
  assert v['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0]==head
  r=next(x for x in refs if x['test_id']==t['id'] and x['variant']==v['id']);assert evaluate(t,v,{'patch':r['answer']})['exact_match'] and assess(t,v,{'patch':r['answer']})['objective_outcome']=='PASS';assert digest(messages(t,v['steps'][0],{},v))==next(x['message_digest'] for x in man['requests'] if x['test_id']==t['id'] and x['variant_id']==v['id'])
  if v['id']=='full_paths':
   for line in v['prompt_bindings']['current_state'].splitlines():
    p,x=line.split(':',1);actual,_,_=resolve(t['source']['initial_state'],t['state_schema'],p);assert actual==json.loads(x)
out={'fixtures':3,'requests':6,'observations':6,'repetitions':1,'reference_evaluators':'pass','full_paths':'pass','unchanged_original_head':'pass','paired_task_schema_state_sampling':'pass','prompt_digests':'pass','context_tokens':32768};(b/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
