"""Freeze existing 4B literal-v2 recipe on previously examined required-scope tasks."""
import copy,json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;workspace=b.parent;root=workspace/'literal-text-branch-v2'/'desktop';sys.path.insert(0,str(root))
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from workbench.literal_line import encode
from evaluation.core import assess
from workbench.prompt_rendering import render
from workbench.prompt_rendering import preview
from workbench.judgements import definition_id
read=lambda p:json.loads(p.read_text(encoding='utf8'))
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
template=read(next((workspace/'safe-text-heldout-v1'/'test_specs').glob('*__literal_line_v2.json')));head=template['variants'][0]['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0];requests=[];refs=[];entries={};seen=set()
for cohort in ('id-routing-v1','array-boundaries-v1','multi-change-v1'):
 source=workspace/cohort;oldrefs=read(source/'references.json')
 for p in sorted((source/'test_specs').glob('*__research_json_v2.json')):
  original=read(p);t=copy.deepcopy(original);assert original['id'] not in seen;seen.add(original['id']);t['id']=original['id']+'__literal_line_v2';t['name']=original['name']+' 4B literal regression';t['description']='Retrospective regression check of unchanged model-specific representation.';t['prompt_builder']['method']='literal_line_v2'
  for v in t['variants']:
   v['result']['representation']='literal_line_v2';binding=v['prompt_bindings'];_,structure=binding['task_requirements'].split('\n\nDatabase structure:\n',1);binding['task_requirements']=head+'\n\nDatabase structure:\n'+structure;v['steps'][0]['prompt']=render(binding)[-1]['content']
  t['prompt_builder']['prompt_digest']=digest({v['id']:render(v['prompt_bindings']) for v in t['variants']});validate_test(t);save(b/'test_specs'/f"{t['id']}.json",t)
  for v in t['variants']:
   ref=next(x for x in oldrefs if x['test_id']==original['id'] and x['variant']==v['id']);answer=encode(json.loads(ref['answer']));assert evaluate(t,v,{'patch':answer})['exact_match'] and assess(t,v,{'patch':answer})['objective_outcome']=='PASS';req=messages(t,v['steps'][0],{},v);q=b/'prompts'/t['id']/(v['id']+'.txt');q.parent.mkdir(parents=True,exist_ok=True);q.write_text(preview(req),encoding='utf8');requests.append({'test_id':t['id'],'baseline_test_id':original['id'],'source_cohort':cohort,'fixture':t['prompt_builder']['fixture'],'arm':'literal_line_v2','variant_id':v['id'],'repetitions':3,'message_digest':digest(req)});refs.append({'test_id':t['id'],'variant':v['id'],'answer':answer});entries[definition_id(t,v)]={'status':'accepted','blocked':False,'reason':'Model-specific retrospective representation check','reviewer':'Codex','note':'Original expected state and operations preserved','history':[]}
assert len(seen)==18 and len(requests)==54
save(b/'test_judgements.json',{'version':1,'entries':entries});save(b/'references.json',refs);save(b/'manifest.json',{'cohort':'fourb-literal-regression-v1','source_cohorts':['id-routing-v1','array-boundaries-v1','multi-change-v1'],'fixtures':18,'arms':['literal_line_v2'],'baseline':'reused original dot results from source cohorts','model':'local-28df315996a77e69','requests':requests,'scope_digest':digest(requests),'planned_new_observations':162,'inference_started':False})
print('Prepared 18 prior tasks, 54 rendered literal-v2 requests, 162 observations; references pass both evaluators.')
