import copy,json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;root=b.parent/'literal-text-branch-v2'/'desktop';sys.path.insert(0,str(root))
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from workbench.dot_paths import resolve
from evaluation.core import assess
from jsonschema import Draft202012Validator
man=json.loads((b/'manifest.json').read_text(encoding='utf8'));refs=json.loads((b/'references.json').read_text(encoding='utf8'));tests={p.stem:json.loads(p.read_text(encoding='utf8')) for p in (b/'test_specs').glob('*.json')};old=list((b.parent/'safe-text-heldout-v1'/'test_specs').glob('*.json'));heads={}
for p in old:
 t=json.loads(p.read_text(encoding='utf8'));arm='literal_line_v2' if t['id'].endswith('__literal_line_v2') else 'original' if t['id'].endswith('__research_json_v2') else None
 if arm:
  for v in t['variants']:
   h=v['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0];heads.setdefault(arm,h);assert heads[arm]==h
assert len(tests)==12 and len(man['requests'])==36 and set(heads)=={'original','literal_line_v2'}
for ident,t in tests.items():
 validate_test(t);Draft202012Validator(t['state_schema']).validate(t['source']['initial_state']);Draft202012Validator(t['state_schema']).validate(t['expected_state']);arm='literal_line_v2' if ident.endswith('__literal_line_v2') else 'original'
 if arm=='literal_line_v2':
  orig=tests[ident.removesuffix('__literal_line_v2')]
  for k in ('source','state_schema','expected_state'):assert t[k]==orig[k]
 for v in t['variants']:
  assert v['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0]==heads[arm]
  if arm=='literal_line_v2':
   q=next(w for w in orig['variants'] if w['id']==v['id']);a=copy.deepcopy(v['result']);z=copy.deepcopy(q['result']);assert a.pop('representation')=='literal_line_v2' and z.pop('representation')=='dot_patch_v1' and a==z;assert v['steps'][0]['sampling']==q['steps'][0]['sampling']
   for field in ('current_state','new_information','presentation_notes'):assert v['prompt_bindings'][field]==q['prompt_bindings'][field]
  ref=next(r for r in refs if r['test_id']==ident and r['variant']==v['id']);assert evaluate(t,v,{'patch':ref['answer']})['exact_match'] and assess(t,v,{'patch':ref['answer']})['objective_outcome']=='PASS';assert digest(messages(t,v['steps'][0],{},v))==next(x['message_digest'] for x in man['requests'] if x['test_id']==ident and x['variant_id']==v['id'])
  if v['id']=='full_paths':
   for line in v['prompt_bindings']['current_state'].splitlines():
    p,x=line.split(':',1);actual,_,_=resolve(t['source']['initial_state'],t['state_schema'],p);assert actual==json.loads(x)
out={'fixture_count':6,'schemas':6,'arms':2,'requests':36,'observations_per_model':108,'original_copy_same_state_schema_expected_task_result_sampling':True,'both_instruction_heads_match_prior_frozen_recipes':True,'reference_both_evaluators':'pass','all_full_paths_resolve':'pass','heldout_unrun':True,'model':man['model'],'context_tokens':32768}
(b/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
