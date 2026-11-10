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
out=base/'holdout-v1';repo=Path(r'E:\Source\Repos\rpg_testing\experiments\required-scope-v2\runs'); dot=repo/'unity-work-20261103';pl=repo/'unity-path-list-20261103';slash=repo/'unity-slash-id-20261103'
S={'type':'string'};I={'type':'integer'}
card={'type':'object','properties':{'card_id':S,'note':S,'count':I,'tags':{'type':'array','items':S}},'required':['card_id','note','count','tags'],'additionalProperties':False}
group={'type':'object','properties':{'group_id':S,'cards':{'type':'array','x-id-field':'card_id','items':card}},'required':['group_id','cards'],'additionalProperties':False}
project={'type':'object','properties':{'project_id':S,'title':S,'groups':{'type':'array','x-id-field':'group_id','items':group}},'required':['project_id','title','groups'],'additionalProperties':False}
schema={'type':'object','properties':{'workspace':{'type':'object','properties':{'projects':{'type':'array','x-id-field':'project_id','items':project},'summary':S},'required':['projects','summary'],'additionalProperties':False}},'required':['workspace'],'additionalProperties':False}
cards=[{'card_id':f'card-{i:02d}','note':f'Note {i:02d}','count':i,'tags':['common']}for i in range(8)]
cards[7]={'card_id':'id./,]"% snow 雪','note':'First line\nSecond: "quoted" \\ path','count':7,'tags':['common','rare/slash]x']}
state={'workspace':{'projects':[{'project_id':'project-alpha','title':'Archive','groups':[{'group_id':'group-main','cards':cards},{'group_id':'group-other','cards':[{'card_id':'other-1','note':'Keep me','count':1,'tags':['ready']}]}]},{'project_id':'project-beta','title':'Keep unchanged','groups':[]}],'summary':'Preserve this workspace'}}
def path(*p):return '.'.join(encode_part(x) for x in p)
prefix=('workspace','projects','project-alpha','groups','group-main','cards')
def op(kind,parts,val=None):
 d={'op':kind,'path':path(*parts)}
 if kind!='remove':d['value']=val
 return d
newcard={'card_id':'card-new','note':'New card','count':17,'tags':['new','ready']}
newnote='Line one\nHe said "hello" \\ goodbye 雪'
items=[]
def add(key,task,ops,update):
 expected=copy.deepcopy(state);update(expected);items.append({'key':'holdout_'+key,'task':task,'ops':ops,'expected':expected})
def main(e):return e['workspace']['projects'][0]['groups'][0]['cards']
add('deep_update','In project "project-alpha", group "group-main", find card "card-06". Set its count to 90; preserve all other data.',[op('replace',(*prefix,'card-06','count'),90)],lambda e:main(e)[6].__setitem__('count',90))
add('long_remove','In project "project-alpha", group "group-main", remove the card whose card_id is "card-05"; preserve all other data.',[op('remove',(*prefix,'card-05'))],lambda e:main(e).pop(5))
weird=cards[7]['card_id'];add('escaped_update','In project "project-alpha", group "group-main", find the card whose card_id is '+json.dumps(weird,ensure_ascii=False)+'. Set its note to this exact JSON string: '+json.dumps(newnote,ensure_ascii=False)+'. Preserve all other data.',[op('replace',(*prefix,weird,'note'),newnote)],lambda e:main(e)[7].__setitem__('note',newnote))
add('nested_append','Append this complete element to the cards array in project "project-alpha", group "group-main": '+json.dumps(newcard,ensure_ascii=False)+'. Preserve all other data.',[op('add',prefix,newcard)],lambda e:main(e).append(copy.deepcopy(newcard)))
def multi(e):
 a=main(e);a[3]['note']='Revised';a.pop(5);a.append(copy.deepcopy(newcard))
add('multiple_changes','In project "project-alpha", group "group-main", perform these changes in order: set card "card-03" note to "Revised"; remove card "card-05"; then append this complete card: '+json.dumps(newcard,ensure_ascii=False)+'. Preserve all other data.',[op('replace',(*prefix,'card-03','note'),'Revised'),op('remove',(*prefix,'card-05')),op('add',prefix,newcard)],multi)
add('nested_primitive_remove','In project "project-alpha", group "group-main", find the card whose card_id is '+json.dumps(weird,ensure_ascii=False)+'. Remove the tag "rare/slash]x" from that card. Preserve all other data.',[op('remove',(*prefix,weird,'tags','rare/slash]x'))],lambda e:main(e)[7]['tags'].remove('rare/slash]x'))
assert len(items)==6
for i in items:
 assert dot_apply(state,i['ops'],schema)==i['expected'],i['key'];assert list_apply(state,list_encode(i['ops']),schema)==i['expected'],i['key']
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
  t=copy.deepcopy(source);t['id']=case['key']+'__'+method;t['name']=case['key'];t['description']='Separately identified generalization cohort.';t['source']={'initial_state':copy.deepcopy(state)};t['state_schema']=copy.deepcopy(schema);t['expected_state']=copy.deepcopy(case['expected']);t['prompt_builder'].update(fixture=case['key'],task=case['key'],operation=('mixed' if len(case['ops'])>1 else {'replace':'update','add':'append','remove':'remove'}[case['ops'][0]['op']]),method=method,version='generalization-holdout-v1',review_status='accepted');t['enabled']=True
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
save(out/'test_judgements.json',{'version':1,'entries':entries});save(out/'references.json',references);save(out/'manifest.json',{'cohort':'generalization-holdout-v1','fixtures':len(items),'presentations_per_method':18,'repetitions':3,'observations_per_method_per_model':54,'methods':['research_json_v2','path_list_v1','research_slash_json_v1'],'requests':requests,'scope_digest':digest(requests),'prior_results_unchanged':True,'inference_started':False})
print('Six new fixtures, 54 rendered requests, 54 observations per method/configuration; original prompt instructions unchanged; independent expected states and both evaluators pass.')





