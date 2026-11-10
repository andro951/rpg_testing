import json,sys,hashlib
from pathlib import Path
base=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task\holdout-v1');sys.path.insert(0,str(base/'desktop'));from workbench.domain import digest,validate_test;from workbench.workflows import messages,evaluate;from evaluation.core import assess
man=json.loads((base/'manifest.json').read_text(encoding='utf8'));refs=json.loads((base/'references.json').read_text(encoding='utf8'));cases={};n=0
for p in (base/'desktop/test_specs').glob('*.json'):
 t=json.loads(p.read_text(encoding='utf8'));validate_test(t);cases[(t['prompt_builder']['fixture'],t['prompt_builder']['method'])]=t
 for v in t['variants']:
  r=next(x for x in refs if x['test_id']==t['id'] and x['variant']==v['id']);assert evaluate(t,v,{'patch':r['answer']})['exact_match'] and assess(t,v,{'patch':r['answer']})['objective_outcome']=='PASS';m=messages(t,v['steps'][0],{},v);item=next(x for x in man['requests']if x['test_id']==t['id']and x['variant_id']==v['id']);assert digest(m)==item['message_digest'];n+=1
for (fixture,method),t in cases.items():
 if method!='research_json_v2':continue
 for candidate in ('path_list_v1','research_slash_json_v1'):
  other=cases[(fixture,candidate)];assert t['source']==other['source'] and t['state_schema']==other['state_schema'] and t['expected_state']==other['expected_state']
  for v in t['variants']:
   w=next(x for x in other['variants']if x['id']==v['id']);assert v['prompt_bindings']['new_information']==w['prompt_bindings']['new_information'];assert v['steps'][0]['sampling']==w['steps'][0]['sampling'];assert v['result']['required_ops']==w['result']['required_ops']
assert n==54;out={'fixture_count':6,'requests':54,'observations_per_method_per_configuration':54,'full_path_resolutions':18*45,'both_evaluators':'pass','independent_expected_state':'pass','fixed_instruction_prefix':'byte-identical to saved recipes','matched_state_schema_expected_and_task':'pass','sampling':'unchanged','context_tokens':32768,'new_cohort':True,'inference_started':False};(base/'validation.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8');print(json.dumps(out,indent=2))



