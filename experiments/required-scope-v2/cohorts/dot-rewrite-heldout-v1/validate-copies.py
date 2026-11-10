import json,sys
from pathlib import Path
b=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task\dot-rewrite-heldout-v1');root=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task\required-scope-v2\path-list-unity-run\common-repo');sys.path.insert(0,str(root));from workbench.domain import digest,validate_test;from workbench.workflows import messages,evaluate;from evaluation.core import assess
man=json.loads((b/'manifest.json').read_text());refs=json.loads((b/'references.json').read_text());tests={p.stem:json.loads(p.read_text(encoding='utf8'))for p in (b/'test_specs').glob('*.json')};assert len(tests)==12 and len(man['requests'])==36
for ident,t in tests.items():
 validate_test(t)
 if ident.endswith('__promptcopy_v2'):
  orig=tests[ident.removesuffix('__promptcopy_v2')]
  for k in ('source','state_schema','expected_state'):assert t[k]==orig[k]
  for v in t['variants']:
   q=next(w for w in orig['variants']if w['id']==v['id']);assert v['result']==q['result'] and v['steps'][0]['sampling']==q['steps'][0]['sampling'];assert v['prompt_bindings']['current_state']==q['prompt_bindings']['current_state'] and v['prompt_bindings']['new_information']==q['prompt_bindings']['new_information']
 for v in t['variants']:
  ref=next(r for r in refs if r['test_id']==ident and r['variant']==v['id']);assert evaluate(t,v,{'patch':ref['answer']})['exact_match'] and assess(t,v,{'patch':ref['answer']})['objective_outcome']=='PASS';assert digest(messages(t,v['steps'][0],{},v))==next(x['message_digest']for x in man['requests']if x['test_id']==ident and x['variant_id']==v['id'])
out={'fixture_count':6,'arms':2,'requests':36,'observations_per_model':108,'original_copy_same_state_schema_expected_task_result_sampling':True,'restructured_instruction_only':True,'reference_both_evaluators':'pass','heldout_unrun':True,'coverage':['nested identity targeting','multiple updates','object addition/removal','escaped values and IDs','unrelated state preservation'],'context_tokens':32768};(b/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
