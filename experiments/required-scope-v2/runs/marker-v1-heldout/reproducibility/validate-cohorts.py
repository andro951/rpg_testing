import copy,json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;sys.path.insert(0,str(b/'runtime'))
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from workbench.dot_paths import resolve
from workbench.literal_line import decode
from evaluation.core import assess
from jsonschema import Draft202012Validator

for raw,expected in [('set sample.note: text:  spaces  |','  spaces  '),('set sample.note: text:ends in pipe||','ends in pipe|'),('set sample.note: text:first\\nsecond|','first\nsecond'),('set sample.note: text:literal \\\\n|',r'literal \n'),('set sample.note: text:He said "hello": yes|','He said "hello": yes')]:
 assert decode(raw)[0]['value']==expected,(repr(raw),repr(decode(raw)[0]['value']),repr(expected))
head_seen=None
for name in ('marker-v1-development','marker-v1-heldout'):
 d=b.parent/name;man=json.loads((d/'manifest.json').read_text(encoding='utf8'));refs=json.loads((d/'references.json').read_text(encoding='utf8'));tests={p.stem:json.loads(p.read_text(encoding='utf8')) for p in (d/'test_specs').glob('*.json')};assert len(tests)==12 and len(man['requests'])==36
 for ident,t in tests.items():
  validate_test(t);Draft202012Validator(t['state_schema']).validate(t['source']['initial_state']);Draft202012Validator(t['state_schema']).validate(t['expected_state']);arm='literal_line_marker_v1' if ident.endswith('__literal_line_marker_v1') else 'original'
  if arm!='original':
   orig=tests[ident.removesuffix('__literal_line_marker_v1')]
   for k in ('source','state_schema','expected_state'):assert t[k]==orig[k]
  for v in t['variants']:
   if arm!='original':
    h=v['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0]
    if head_seen is None:head_seen=h
    assert h==head_seen
    q=next(w for w in orig['variants'] if w['id']==v['id']);a=copy.deepcopy(v['result']);z=copy.deepcopy(q['result']);assert a.pop('representation')=='literal_line_marker_v1' and z.pop('representation')=='dot_patch_v1' and a==z;assert v['steps'][0]['sampling']==q['steps'][0]['sampling']
    for k in ('current_state','new_information','presentation_notes'):assert v['prompt_bindings'][k]==q['prompt_bindings'][k]
   ref=next(r for r in refs if r['test_id']==ident and r['variant']==v['id']);assert evaluate(t,v,{'patch':ref['answer']})['exact_match'] and assess(t,v,{'patch':ref['answer']})['objective_outcome']=='PASS';assert digest(messages(t,v['steps'][0],{},v))==next(x['message_digest'] for x in man['requests'] if x['test_id']==ident and x['variant_id']==v['id'])
   if v['id']=='full_paths':
    for line in v['prompt_bindings']['current_state'].splitlines():
     p,x=line.split(':',1);actual,_,_=resolve(t['source']['initial_state'],t['state_schema'],p);assert actual==json.loads(x)
 out={'fixture_count':6,'arms':2,'requests':36,'observations_per_model':108,'same_state_schema_expected_task_sampling':True,'reference_both_evaluators':'pass','all_full_paths_resolve':'pass','marker_examples':'pass','heldout_unrun':True,'model':man['model'],'context_tokens':32768};(d/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(name,json.dumps(out))
