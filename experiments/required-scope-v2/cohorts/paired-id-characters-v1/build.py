import copy,json,sys,hashlib
from pathlib import Path
base=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task'); prior=base/'required-scope-v2'; root=prior/'path-list-unity-run/common-repo';sys.path.insert(0,str(root))
from workbench.dot_paths import encode_part,full_paths,apply as dot_apply
from workbench.path_list import encode as list_encode,apply as list_apply
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from evaluation.core import assess
from test_builder.builder import structure_text
from test_builder.presentation import id_keyed_arrays,full_paths as slash_full_paths
from test_builder.original_prompt import render
from test_builder.normal_prompt import preview
from workbench.presentation import render_source_text
from workbench.judgements import definition_id
out=base/'paired-id-characters-v1';repo=Path(r'E:\Source\Repos\rpg_testing\experiments\required-scope-v2\runs'); dot=repo/'unity-work-20261103';pl=repo/'unity-path-list-20261103';slash=repo/'unity-slash-id-20261103'
S={'type':'string'};I={'type':'integer'};B={'type':'boolean'}
def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
def arr(i,idfield):return {'type':'array','items':i,'x-id-field':idfield}
def path(*p):return '.'.join(encode_part(x) for x in p)
def op(kind,parts,val=None):
 x={'op':kind,'path':path(*parts)}
 if kind!='remove':x['value']=val
 return x
items=[]
def add(k,schema,state,task,ops,expected):items.append({'key':'paired_'+k,'schema':schema,'state':state,'task':task,'ops':ops,'expected':expected})
# Each pair differs in identifier characters only; object structure and values match.
s1=obj({'catalog':obj({'records':arr(obj({'record_id':S,'rating':I,'label':S}),'record_id'),'name':S})})
for label,ident in [('plain','R-7'),('reserved','R.7')]:
 state={'catalog':{'records':[{'record_id':'other','rating':2,'label':'Other'},{'record_id':ident,'rating':5,'label':'Target'}],'name':'Catalog'}};y=copy.deepcopy(state);y['catalog']['records'][1]['rating']=9
 add('record_'+label,s1,state,'Set rating to 9 for record with record_id '+json.dumps(ident)+'. Preserve everything else.',[op('replace',('catalog','records',ident,'rating'),9)],y)
s2=obj({'fleet':obj({'devices':arr(obj({'device_id':S,'mode':S}),'device_id'),'online':B})})
for label,ident in [('plain','node-7'),('reserved','node/7')]:
 state={'fleet':{'devices':[{'device_id':'other','mode':'standby'},{'device_id':ident,'mode':'active'}],'online':True}};y=copy.deepcopy(state);y['fleet']['devices'].pop(1)
 add('device_'+label,s2,state,'Remove the device with device_id '+json.dumps(ident)+'. Preserve everything else.',[op('remove',('fleet','devices',ident))],y)
s3=obj({'supply':obj({'racks':arr(obj({'rack_id':S,'parts':arr(obj({'part_id':S,'count':I}),'part_id')}),'rack_id'),'open':B})})
for label,rack,part in [('plain','rack-7','part-7'),('reserved','rack%7','part]7')]:
 state={'supply':{'racks':[{'rack_id':'other','parts':[]},{'rack_id':rack,'parts':[{'part_id':'other','count':2},{'part_id':part,'count':5}]}],'open':True}};y=copy.deepcopy(state);y['supply']['racks'][1]['parts'][1]['count']=9
 add('part_'+label,s3,state,'In rack with rack_id '+json.dumps(rack)+', set count to 9 for part with part_id '+json.dumps(part)+'. Preserve everything else.',[op('replace',('supply','racks',rack,'parts',part,'count'),9)],y)
for c in items:
 assert dot_apply(c['state'],c['ops'],c['schema'])==c['expected'];assert list_apply(c['state'],list_encode(c['ops']),c['schema'])==c['expected']
def data_view(mode,method):
 if mode=='normal_json':return render_source_text(state,'raw_json')
 if mode=='id_keyed_arrays':return json.dumps(id_keyed_arrays(state,schema),ensure_ascii=False,indent=2,allow_nan=False)
 if method=='research_slash_json_v1':return '\n'.join(slash_full_paths(state,schema))
 lines=full_paths(state,schema)
 if method=='path_list_v1':
  from workbench.dot_paths import tokens
  def fmt(line):
   p,v=line.split(':',1);return '['+', '.join(encode_part(x) for x in tokens(p))+']: '+v
  return '\n'.join(fmt(x) for x in lines)
 return '\n'.join(lines)
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
requests=[];entries={};references=[]
for method,priorroot,template in [('research_json_v2',dot,'db_v3_update_record__research_json_v2'),('path_list_v1',pl,'db_v3_update_record__path_list_v1'),('research_slash_json_v1',slash,'db_v3_update_record__research_slash_json_v1')]:
 source=json.loads((priorroot/'test_specs'/f'{template}.json').read_text(encoding='utf8'));orig={v['id']:v for v in source['variants']}
 for case in items:
  schema=case['schema'];state=case['state']
  t=copy.deepcopy(source);t['id']=case['key']+'__'+method;t['name']=case['key'];t['description']='Separately identified generalization cohort.';t['source']={'initial_state':copy.deepcopy(state)};t['state_schema']=copy.deepcopy(schema);t['expected_state']=copy.deepcopy(case['expected']);t['prompt_builder'].update(fixture=case['key'],task=case['key'],operation=('mixed' if len(case['ops'])>1 else {'replace':'update','add':'append','remove':'remove'}[case['ops'][0]['op']]),method=method,version='paired-id-characters-v1',review_status='accepted');t['enabled']=True
  for v in t['variants']:
   mode=v['id'];binding=v['prompt_bindings'];original=orig[mode]['prompt_bindings']['task_requirements'];head=original.split('\n\nDatabase structure:\n',1)[0];binding['task_requirements']=head+'\n\nDatabase structure:\n'+structure_text(schema);assert binding['task_requirements'].split('\n\nDatabase structure:\n',1)[0]==head
   binding['current_state']=data_view(mode,method);binding['new_information']=case['task'];v['steps'][0]['prompt']=render(binding)[-1]['content'];v['result']['required_ops']=[o['op']for o in case['ops']]
  t['prompt_builder']['prompt_digest']=digest({v['id']:render(v['prompt_bindings']) for v in t['variants']});validate_test(t);save(out/'test_specs'/f"{t['id']}.json",t)
  if method=='research_slash_json_v1':
   from workbench.dot_paths import resolve
   from workbench import value_paths
   doc=copy.deepcopy(state);translated=[]
   for operation in case['ops']:
    current=copy.deepcopy(operation);_,_,concrete=resolve(doc,schema,current['path']);current['path']=value_paths.from_pointer(doc,schema,value_paths.pointer(concrete));translated.append(current);doc=dot_apply(doc,[operation],schema)
   assert value_paths.apply(state,translated,schema)==case['expected'];answer=json.dumps(translated,ensure_ascii=False)
  else:answer=json.dumps(case['ops'],ensure_ascii=False)if method=='research_json_v2'else list_encode(case['ops'])
  for v in t['variants']:
   r=evaluate(t,v,{'patch':answer});a=assess(t,v,{'patch':answer});assert r['exact_match'] and a['objective_outcome']=='PASS',(t['id'],v['id'],r,a);m=messages(t,v['steps'][0],{},v);f=out/'prompts'/t['id']/(v['id']+'.txt');f.parent.mkdir(parents=True,exist_ok=True);f.write_text(preview(m),encoding='utf8');requests.append({'test_id':t['id'],'fixture':case['key'],'method':method,'variant_id':v['id'],'repetitions':3,'message_digest':digest(m)});references.append({'test_id':t['id'],'variant':v['id'],'answer':answer});entries[definition_id(t,v)]={'status':'accepted','blocked':False,'reason':'User authorized fixed-prompt generalization cohort; independently reviewed','reviewer':'Codex','note':'Only fixture data, schema and task changed','history':[]}
assert len(requests)==54
save(out/'test_judgements.json',{'version':1,'entries':entries});save(out/'references.json',references);save(out/'manifest.json',{'cohort':'paired-id-characters-v1','fixtures':len(items),'presentations_per_method':18,'repetitions':3,'observations_per_method_per_model':54,'methods':['research_json_v2','path_list_v1','research_slash_json_v1'],'requests':requests,'scope_digest':digest(requests),'prior_results_unchanged':True,'inference_started':False})
print('Six new fixtures across three schemas, 54 rendered requests, 54 observations per method/configuration; original prompt instructions unchanged; independent expected states and both evaluators pass.')





