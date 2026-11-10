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
out=base/'array-boundaries-v1';repo=Path(r'E:\Source\Repos\rpg_testing\experiments\required-scope-v2\runs'); dot=repo/'unity-work-20261103';pl=repo/'unity-path-list-20261103';slash=repo/'unity-slash-id-20261103'
S={'type':'string'};I={'type':'integer'};B={'type':'boolean'}
def obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
def arr(item,idfield=None):
 x={'type':'array','items':item}
 if idfield:x['x-id-field']=idfield
 return x
def path(*p):return '.'.join(encode_part(x) for x in p)
def op(kind,parts,val=None):
 x={'op':kind,'path':path(*parts)}
 if kind!='remove':x['value']=val
 return x
items=[]
def add(key,schema,state,task,ops,expected):items.append({'key':'arrays_'+key,'schema':schema,'state':state,'task':task,'ops':ops,'expected':expected})
# Recipes: distinct primitive arrays plus nested records.
s1=obj({'cookbook':obj({'recipes':arr(obj({'recipe_id':S,'ingredients':arr(S),'notes':S}),'recipe_id'),'title':S})})
x1={'cookbook':{'recipes':[{'recipe_id':'soup','ingredients':['onion','pepper','salt','herbs','beans','water'],'notes':'warm'},{'recipe_id':'bread','ingredients':['flour','water'],'notes':'baked'}],'title':'Kitchen'}}
y=copy.deepcopy(x1);y['cookbook']['recipes'][0]['ingredients'].remove('salt')
add('remove_ingredient',s1,x1,'Remove salt from the ingredients of recipe soup; keep everything else unchanged.',[op('remove',('cookbook','recipes','soup','ingredients','salt'))],y)
y=copy.deepcopy(x1);y['cookbook']['recipes'][1]['ingredients'].append('yeast')
add('append_ingredient',s1,x1,'Append yeast to the ingredients of recipe bread; keep everything else unchanged.',[op('add',('cookbook','recipes','bread','ingredients'),'yeast')],y)
# Transit: primitive arrays are empty or populated; object update spans branches.
s2=obj({'transit':obj({'routes':arr(obj({'route_id':S,'stops':arr(S),'enabled':B}),'route_id'),'depot':S})})
x2={'transit':{'routes':[{'route_id':'north','stops':[],'enabled':False},{'route_id':'south','stops':['Hill','Park','Pier','Market'],'enabled':True}],'depot':'East'}}
y=copy.deepcopy(x2);y['transit']['routes'][0]['stops'].append('Museum')
add('append_empty',s2,x2,'Append Museum to the stops of route north; keep everything else unchanged.',[op('add',('transit','routes','north','stops'),'Museum')],y)
y=copy.deepcopy(x2);y['transit']['routes'][1]['stops'].remove('Park');y['transit']['routes'][0]['enabled']=True
add('cross_branch',s2,x2,'In order, remove Park from route south stops, then set route north enabled to true. Keep everything else unchanged.',[op('remove',('transit','routes','south','stops','Park')),op('replace',('transit','routes','north','enabled'),True)],y)
# Lending: object append and deletion among unique IDs in a different schema.
s3=obj({'library':obj({'shelves':arr(obj({'shelf_id':S,'books':arr(obj({'isbn':S,'name':S,'year':I}),'isbn')}),'shelf_id'),'open':B})})
x3={'library':{'shelves':[{'shelf_id':'history','books':[{'isbn':'h1','name':'Past','year':2001},{'isbn':'h2','name':'Maps','year':2010}]},{'shelf_id':'science','books':[]}],'open':True}}
book={'isbn':'s1','name':'Stars','year':2020};y=copy.deepcopy(x3);y['library']['shelves'][1]['books'].append(copy.deepcopy(book))
add('append_object_empty',s3,x3,'Append this book to the science shelf: '+json.dumps(book)+'. Keep everything else unchanged.',[op('add',('library','shelves','science','books'),book)],y)
y=copy.deepcopy(x3);y['library']['shelves'][0]['books'].pop(1)
add('remove_object_nested',s3,x3,'Remove book h2 from the history shelf; keep everything else unchanged.',[op('remove',('library','shelves','history','books','h2'))],y)
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
  t=copy.deepcopy(source);t['id']=case['key']+'__'+method;t['name']=case['key'];t['description']='Separately identified generalization cohort.';t['source']={'initial_state':copy.deepcopy(state)};t['state_schema']=copy.deepcopy(schema);t['expected_state']=copy.deepcopy(case['expected']);t['prompt_builder'].update(fixture=case['key'],task=case['key'],operation=('mixed' if len(case['ops'])>1 else {'replace':'update','add':'append','remove':'remove'}[case['ops'][0]['op']]),method=method,version='array-boundaries-v1',review_status='accepted');t['enabled']=True
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
save(out/'test_judgements.json',{'version':1,'entries':entries});save(out/'references.json',references);save(out/'manifest.json',{'cohort':'array-boundaries-v1','fixtures':len(items),'presentations_per_method':18,'repetitions':3,'observations_per_method_per_model':54,'methods':['research_json_v2','path_list_v1','research_slash_json_v1'],'requests':requests,'scope_digest':digest(requests),'prior_results_unchanged':True,'inference_started':False})
print('Six new fixtures across three schemas, 54 rendered requests, 54 observations per method/configuration; original prompt instructions unchanged; independent expected states and both evaluators pass.')





