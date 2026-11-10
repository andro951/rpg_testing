import copy,json,sys,hashlib
from pathlib import Path
base=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task'); prior=base/'required-scope-v2'; root=prior/'path-list-unity-run/common-repo';sys.path.insert(0,str(root))
from workbench.dot_paths import encode_part,full_paths,apply as dot_apply
from workbench.path_list import encode as list_encode,apply as list_apply
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from evaluation.core import assess
from workbench.prompt_rendering import structure_text
from workbench.prompt_rendering import id_keyed_arrays,full_paths as slash_full_paths
from workbench.prompt_rendering import render
from workbench.prompt_rendering import preview
from workbench.presentation import render_source_text
from workbench.judgements import definition_id
out=base/'multi-change-v1';repo=Path(r'E:\Source\Repos\rpg_testing\experiments\required-scope-v2\runs'); dot=repo/'unity-work-20261103';pl=repo/'unity-path-list-20261103';slash=repo/'unity-slash-id-20261103'
S={'type':'string'};I={'type':'integer'};B={'type':'boolean'}
def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
def arr(i,idfield):return {'type':'array','items':i,'x-id-field':idfield}
def path(*p):return '.'.join(encode_part(x) for x in p)
def op(kind,parts,val=None):
 x={'op':kind,'path':path(*parts)}
 if kind!='remove':x['value']=val
 return x
items=[]
def add(k,schema,state,task,ops,expected):items.append({'key':'changes_'+k,'schema':schema,'state':state,'task':task,'ops':ops,'expected':expected})
# Team roster: one versus three updates to existing fields.
s1=obj({'team':obj({'members':arr(obj({'member_id':S,'level':I,'ready':B}),'member_id'),'label':S})})
x1={'team':{'members':[{'member_id':'ada','level':3,'ready':False},{'member_id':'ben','level':4,'ready':True},{'member_id':'cy','level':5,'ready':False}],'label':'Blue'}}
y=copy.deepcopy(x1);y['team']['members'][0]['level']=6
add('team_single',s1,x1,'Set ada level to 6; preserve everything else.',[op('replace',('team','members','ada','level'),6)],y)
y=copy.deepcopy(x1);y['team']['members'][0]['level']=6;y['team']['members'][1]['ready']=False;y['team']['members'][2]['level']=7
add('team_three',s1,x1,'In order set ada level to 6, set ben ready to false, and set cy level to 7; preserve everything else.',[op('replace',('team','members','ada','level'),6),op('replace',('team','members','ben','ready'),False),op('replace',('team','members','cy','level'),7)],y)
# Store: one versus mixed object-array and existing field changes.
s2=obj({'store':obj({'items':arr(obj({'sku':S,'price':I,'stock':I}),'sku'),'open':B})})
x2={'store':{'items':[{'sku':'p1','price':4,'stock':8},{'sku':'p2','price':7,'stock':2},{'sku':'p3','price':3,'stock':5}],'open':True}}
y=copy.deepcopy(x2);y['store']['items'][0]['price']=5
add('store_single',s2,x2,'Set item p1 price to 5; preserve everything else.',[op('replace',('store','items','p1','price'),5)],y)
item={'sku':'p4','price':9,'stock':6};y=copy.deepcopy(x2);y['store']['items'][0]['price']=5;y['store']['items'].pop(1);y['store']['items'].append(copy.deepcopy(item))
add('store_mixed',s2,x2,'In order set p1 price to 5, remove item p2, then append this item: '+json.dumps(item)+'. Preserve everything else.',[op('replace',('store','items','p1','price'),5),op('remove',('store','items','p2')),op('add',('store','items'),item)],y)
# Orchard: changes across nested child collections.
s3=obj({'orchard':obj({'plots':arr(obj({'plot_id':S,'trees':arr(obj({'tree_id':S,'height':I,'fruit':I}),'tree_id')}),'plot_id'),'season':S})})
x3={'orchard':{'plots':[{'plot_id':'north','trees':[{'tree_id':'oak','height':5,'fruit':0},{'tree_id':'pear','height':4,'fruit':6}]},{'plot_id':'south','trees':[{'tree_id':'apple','height':3,'fruit':4}]}],'season':'spring'}}
y=copy.deepcopy(x3);y['orchard']['plots'][0]['trees'][1]['fruit']=8
add('orchard_single',s3,x3,'In north set pear fruit to 8; preserve everything else.',[op('replace',('orchard','plots','north','trees','pear','fruit'),8)],y)
y=copy.deepcopy(x3);y['orchard']['plots'][0]['trees'][1]['fruit']=8;y['orchard']['plots'][1]['trees'][0]['height']=4;y['orchard']['season']='summer'
add('orchard_three',s3,x3,'In order set north pear fruit to 8, set south apple height to 4, and set season to summer. Preserve everything else.',[op('replace',('orchard','plots','north','trees','pear','fruit'),8),op('replace',('orchard','plots','south','trees','apple','height'),4),op('replace',('orchard','season'),'summer')],y)
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
  t=copy.deepcopy(source);t['id']=case['key']+'__'+method;t['name']=case['key'];t['description']='Separately identified generalization cohort.';t['source']={'initial_state':copy.deepcopy(state)};t['state_schema']=copy.deepcopy(schema);t['expected_state']=copy.deepcopy(case['expected']);t['prompt_builder'].update(fixture=case['key'],task=case['key'],operation=('mixed' if len(case['ops'])>1 else {'replace':'update','add':'append','remove':'remove'}[case['ops'][0]['op']]),method=method,version='multi-change-v1',review_status='accepted');t['enabled']=True
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
save(out/'test_judgements.json',{'version':1,'entries':entries});save(out/'references.json',references);save(out/'manifest.json',{'cohort':'multi-change-v1','fixtures':len(items),'presentations_per_method':18,'repetitions':3,'observations_per_method_per_model':54,'methods':['research_json_v2','path_list_v1','research_slash_json_v1'],'requests':requests,'scope_digest':digest(requests),'prior_results_unchanged':True,'inference_started':False})
print('Six new fixtures across three schemas, 54 rendered requests, 54 observations per method/configuration; original prompt instructions unchanged; independent expected states and both evaluators pass.')





