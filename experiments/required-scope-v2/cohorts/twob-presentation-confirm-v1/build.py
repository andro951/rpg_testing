import copy,json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;root=b.parent/'dot-rewrite-heldout-v1'/'desktop';sys.path.insert(0,str(root))
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from evaluation.core import assess
from workbench.prompt_rendering import preview
from workbench.judgements import definition_id
read=lambda p:json.loads(p.read_text(encoding='utf8'))
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
oldrefs=read(b/'baseline'/'references.json');reqs=[];refs=[];entries={}
for p in sorted((b/'baseline'/'test_specs').glob('*__research_json_v2.json')):
 if 'present_literal__' in p.name:continue
 t=read(p);t['repetitions']=1;t['variants']=[v for v in t['variants'] if v['id'] in ('normal_json','full_paths')];assert len(t['variants'])==2;validate_test(t);save(b/'test_specs'/f"{t['id']}.json",t)
 for v in t['variants']:
  ref=next(x for x in oldrefs if x['test_id']==t['id'] and x['variant']==v['id']);answer=ref['answer'];assert evaluate(t,v,{'patch':answer})['exact_match'] and assess(t,v,{'patch':answer})['objective_outcome']=='PASS';req=messages(t,v['steps'][0],{},v);q=b/'prompts'/t['id']/(v['id']+'.txt');q.parent.mkdir(parents=True,exist_ok=True);q.write_text(preview(req),encoding='utf8');reqs.append({'test_id':t['id'],'fixture':t['prompt_builder']['fixture'],'arm':'original','variant_id':v['id'],'repetitions':1,'message_digest':digest(req)});refs.append({'test_id':t['id'],'variant':v['id'],'answer':answer});entries[definition_id(t,v)]={'status':'accepted','blocked':False,'reason':'User authorized model-specific presentation confirmation','reviewer':'Codex','note':'Independent expected-state and reference checks','history':[]}
assert len(reqs)==6
save(b/'test_judgements.json',{'version':1,'entries':entries});save(b/'references.json',refs);save(b/'manifest.json',{'cohort':'twob-presentation-confirm-v1','model':'local-2542aed68e6bb077','fixtures':3,'presentations':['normal_json','full_paths'],'repetitions':1,'requests':reqs,'scope_digest':digest(reqs),'planned_observations':6,'inference_started':False})
print('Prepared three fresh tasks, two unchanged presentations, one repetition: six observations.')
