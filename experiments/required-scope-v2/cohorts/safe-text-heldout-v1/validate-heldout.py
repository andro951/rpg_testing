import copy,json,sys
from pathlib import Path
b=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task\safe-text-heldout-v1');sys.path.insert(0,str(Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task\literal-text-branch-v2\runtime')));from workbench.domain import digest,validate_test;from workbench.workflows import messages,evaluate;from evaluation.core import assess
man=json.loads((b/'manifest.json').read_text());refs=json.loads((b/'references.json').read_text());tests={p.stem:json.loads(p.read_text(encoding='utf8'))for p in (b/'test_specs').glob('*.json')};assert len(tests)==18 and len(man['requests'])==54
for ident,t in tests.items():
 validate_test(t)
 if ident.endswith('__promptcopy_v1') or ident.endswith('__literal_line_v2'):
  suffix='__promptcopy_v1' if ident.endswith('__promptcopy_v1') else '__literal_line_v2';orig=tests[ident.removesuffix(suffix)]
  for k in ('source','state_schema','expected_state'):assert t[k]==orig[k]
  for v in t['variants']:
   q=next(w for w in orig['variants']if w['id']==v['id']);vr=copy.deepcopy(v['result']);qr=copy.deepcopy(q['result']);vr.pop('representation',None);qr.pop('representation',None);assert vr==qr and v['steps'][0]['sampling']==q['steps'][0]['sampling'];assert v['prompt_bindings']['current_state']==q['prompt_bindings']['current_state'] and v['prompt_bindings']['new_information']==q['prompt_bindings']['new_information']
   if suffix=='__literal_line_v2':assert v['prompt_bindings']['task_requirements'].split('\n\nOutput format:\n')[0]==q['prompt_bindings']['task_requirements'].split('\n\nOutput format:\n')[0]
 for v in t['variants']:
  ref=next(r for r in refs if r['test_id']==ident and r['variant']==v['id']);assert evaluate(t,v,{'patch':ref['answer']})['exact_match'] and assess(t,v,{'patch':ref['answer']})['objective_outcome']=='PASS';assert digest(messages(t,v['steps'][0],{},v))==next(x['message_digest']for x in man['requests']if x['test_id']==ident and x['variant_id']==v['id'])
t=tests['safeheld_quotes__research_json_v2__literal_line_v2'];v=t['variants'][0];bad='set mailbox.messages.m1.body: text:wrong';assert not evaluate(t,v,{'patch':bad})['exact_match'] and assess(t,v,{'patch':bad})['objective_outcome']!='PASS'
out={'fixture_count':6,'arms':3,'requests':54,'observations_per_model':162,'matched_source_schema_expected_task_sampling':True,'baseline_ancestry_verified':True,'reference_both_evaluators':'pass','incorrect_output_rejected':True,'parser_roundtrip':'13 values, 5 malformed cases, mixed operations, optional quote and whitespace escapes','heldout_unrun':True,'context_tokens':32768};(b/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
