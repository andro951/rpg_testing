import json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;root=b.parent/'dot-rewrite-heldout-v1'/'desktop';sys.path.insert(0,str(root))
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from workbench.dot_paths import resolve
from evaluation.core import assess
from jsonschema import Draft202012Validator
audit=json.loads((Path(r'E:\Source\Repos\rpg_testing\experiments\required-scope-v2\runs\reserved-id-v1\desktop\local-2542aed68e6bb077')/'audit.json').read_text(encoding='utf8'))
for name in ('development','verification'):
 d=b/name;man=json.loads((d/'manifest.json').read_text(encoding='utf8'));refs=json.loads((d/'references.json').read_text(encoding='utf8'));tests={p.stem:json.loads(p.read_text(encoding='utf8')) for p in (d/'test_specs').glob('*.json')};assert len(man['requests'])==(4 if name=='development' else 8)
 for req in man['requests']:
  t=tests[req['test_id']];v=next(x for x in t['variants'] if x['id']==req['variant_id']);validate_test(t);assert t['repetitions']==1 and len(t['variants'])==2
  Draft202012Validator(t['state_schema']).validate(t['source']['initial_state']);Draft202012Validator(t['state_schema']).validate(t['expected_state'])
  if req['arm']=='twob_short_v1':assert digest(v['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0])==man['candidate_head_digest']
  if name=='verification' and req['arm']=='twob_short_v1':
   orig=tests[req['baseline_test_id']];q=next(x for x in orig['variants'] if x['id']==v['id'])
   for k in ('source','state_schema','expected_state'):assert t[k]==orig[k]
   assert v['result']==q['result'] and v['steps'][0]['sampling']==q['steps'][0]['sampling']
   for k in ('current_state','new_information','presentation_notes'):assert v['prompt_bindings'][k]==q['prompt_bindings'][k]
  if name=='development':
   ev=[x for x in audit['evidence'] if x['test_id']==req['baseline_test_id'] and x['variant_id']==v['id'] and x['repetition']==0];assert len(ev)==1 and ev[0]['outcome']=='FAIL'
  ref=next(x for x in refs if x['test_id']==t['id'] and x['variant']==v['id']);assert evaluate(t,v,{'patch':ref['answer']})['exact_match'] and assess(t,v,{'patch':ref['answer']})['objective_outcome']=='PASS';assert digest(messages(t,v['steps'][0],{},v))==req['message_digest']
  if v['id']=='full_paths':
   for line in v['prompt_bindings']['current_state'].splitlines():
    p,x=line.split(':',1);actual,_,_=resolve(t['source']['initial_state'],t['state_schema'],p);assert actual==json.loads(x)
 out={'fixtures':2,'requests':len(man['requests']),'observations':len(man['requests']),'repetitions':1,'reference_evaluators':'pass','full_paths':'pass','prompt_digests':'pass','reused_baselines':'four failures, one per key' if name=='development' else None,'preflight_stage':name,'candidate_head_digest':man['candidate_head_digest']};(d/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(name,json.dumps(out))
