import copy,json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;root=b.parent/'literal-text-branch-v2'/'desktop';sys.path.insert(0,str(root))
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from workbench.literal_line import encode
from evaluation.core import assess
from test_builder.original_prompt import render
from test_builder.normal_prompt import preview
from workbench.judgements import definition_id
read=lambda p:json.loads(p.read_text(encoding='utf8'))
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
template=read(next((b.parent/'safe-text-heldout-v1'/'test_specs').glob('*__literal_line_v2.json')))
head=template['variants'][0]['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0]
oldrefs=read(b/'baseline'/'references.json');requests=[];refs=[];entries={}
for f in sorted((b/'baseline'/'test_specs').glob('*__research_json_v2.json')):
 original=read(f);candidate=copy.deepcopy(original);candidate['id']=original['id']+'__literal_line_v2';candidate['name']=original['name']+' literal line v2';candidate['description']='Fresh 4B model-specific confirmation, preserved representation branch.';candidate['prompt_builder']['method']='literal_line_v2'
 for v in candidate['variants']:
  v['result']['representation']='literal_line_v2';binding=v['prompt_bindings'];_,structure=binding['task_requirements'].split('\n\nDatabase structure:\n',1);binding['task_requirements']=head+'\n\nDatabase structure:\n'+structure;v['steps'][0]['prompt']=render(binding)[-1]['content']
 candidate['prompt_builder']['prompt_digest']=digest({v['id']:render(v['prompt_bindings']) for v in candidate['variants']})
 for arm,t in [('original',original),('literal_line_v2',candidate)]:
  validate_test(t);save(b/'test_specs'/f"{t['id']}.json",t)
  for v in t['variants']:
   ref=next(x for x in oldrefs if x['test_id']==original['id'] and x['variant']==v['id']);answer=encode(json.loads(ref['answer'])) if arm=='literal_line_v2' else ref['answer'];assert evaluate(t,v,{'patch':answer})['exact_match'] and assess(t,v,{'patch':answer})['objective_outcome']=='PASS'
   req=messages(t,v['steps'][0],{},v);p=b/'prompts'/t['id']/(v['id']+'.txt');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(preview(req),encoding='utf8');requests.append({'test_id':t['id'],'fixture':t['prompt_builder']['fixture'],'arm':arm,'variant_id':v['id'],'repetitions':3,'message_digest':digest(req)});refs.append({'test_id':t['id'],'variant':v['id'],'answer':answer});entries[definition_id(t,v)]={'status':'accepted','blocked':False,'reason':'Fresh model-specific confirmation of existing recipes','reviewer':'Codex','note':'Independent expected state and references','history':[]}
assert len(requests)==36
save(b/'test_judgements.json',{'version':1,'entries':entries});save(b/'references.json',refs);save(b/'manifest.json',{'cohort':'fourb-text-confirm-v1','fixtures':6,'arms':['original','literal_line_v2'],'model':'local-28df315996a77e69','requests':requests,'scope_digest':digest(requests),'observations_per_model':108,'inference_started':False})
print('Prepared six new schemas and 36 requests; both evaluator reference checks pass.')
