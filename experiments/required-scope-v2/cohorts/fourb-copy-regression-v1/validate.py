import json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;workspace=b.parent;root=workspace/'dot-rewrite-heldout-v1'/'desktop';sys.path.insert(0,str(root))
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from evaluation.core import assess
from workbench.dot_paths import resolve
from jsonschema import Draft202012Validator
man=json.loads((b/'manifest.json').read_text(encoding='utf8'));refs=json.loads((b/'references.json').read_text(encoding='utf8'));head=json.loads((workspace/'dot-rewrite-heldout-v1'/'lineage.json').read_text(encoding='utf8'))['candidate_head'];tests={p.stem:json.loads(p.read_text(encoding='utf8')) for p in (b/'test_specs').glob('*.json')};assert len(tests)==18 and len(man['requests'])==54
old_audits={}
for name in man['source_cohorts']:
 p=Path(r'E:\Source\Repos\rpg_testing\experiments\required-scope-v2\runs')/name/'desktop'/'local-28df315996a77e69'/'audit.json';old_audits[name]=json.loads(p.read_text(encoding='utf8'))
seen=set()
for req in man['requests']:
 t=tests[req['test_id']];v=next(x for x in t['variants'] if x['id']==req['variant_id']);old=json.loads((workspace/req['source_cohort']/'test_specs'/(req['baseline_test_id']+'.json')).read_text(encoding='utf8'));q=next(x for x in old['variants'] if x['id']==v['id']);validate_test(t)
 for k in ('source','state_schema','expected_state'):assert t[k]==old[k]
 for k in ('current_state','new_information','presentation_notes'):assert v['prompt_bindings'][k]==q['prompt_bindings'][k]
 assert v['result']==q['result'] and v['steps'][0]['sampling']==q['steps'][0]['sampling'];assert v['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0]==head
 ref=next(x for x in refs if x['test_id']==t['id'] and x['variant']==v['id']);assert evaluate(t,v,{'patch':ref['answer']})['exact_match'] and assess(t,v,{'patch':ref['answer']})['objective_outcome']=='PASS';assert digest(messages(t,v['steps'][0],{},v))==req['message_digest']
 evidence=[x for x in old_audits[req['source_cohort']]['evidence'] if x['test_id']==old['id'] and x['variant_id']==v['id']];assert len(evidence)==3;seen.update((req['source_cohort'],x['case_id']) for x in evidence)
 if v['id']=='full_paths':
  for line in v['prompt_bindings']['current_state'].splitlines():
   p,x=line.split(':',1);actual,_,_=resolve(t['source']['initial_state'],t['state_schema'],p);assert actual==json.loads(x)
assert len(seen)==162
out={'fixture_count':18,'requests':54,'planned_new_observations':162,'reused_baseline_observations':162,'unchanged_candidate_head':'pass','same_task_state_schema_result_sampling':'pass','both_reference_evaluators':'pass','all_full_paths_resolve':'pass','context_tokens':32768,'retrospective':True,'heldout':False};(b/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
