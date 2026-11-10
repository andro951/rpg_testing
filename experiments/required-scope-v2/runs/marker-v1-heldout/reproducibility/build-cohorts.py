"""Create separate development and predeclared heldout cohorts for marker-v1."""
import copy,json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;root=b/'runtime';sys.path.insert(0,str(root))
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from workbench.literal_line import encode
from evaluation.core import assess
from workbench.prompt_rendering import render
from workbench.prompt_rendering import preview
from workbench.judgements import definition_id
read=lambda p:json.loads(p.read_text(encoding='utf8'))
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
output=r'''Output format:
Return only update lines, without explanation or Markdown. Return exactly none if no change is needed. Each complete update occupies one physical line.
For an existing string field: set dot.path: text:literal text|
For an existing non-string field: set dot.path: json:JSON_value
To append: append dot.path: text:literal text| OR append dot.path: json:JSON_value
To remove: remove dot.path
Use text: only for strings. The final | is the required end marker and is not part of the value. All characters between text: and that final | are the value, including leading/trailing spaces, quotes, colons and other | characters. Do not put outer quotes around text. Empty text is text:|. Decode requested input text before writing it.
In text, write \\ for one backslash, \n for a newline, \r for a carriage return and \t for a tab. These are the only backslash escapes; quotes and | need no escape. To represent a literal backslash followed by n, write \\n, not \n.
Use json: for complete non-string JSON values; objects and arrays use normal JSON syntax. Do not use json: for a string. Paths follow the dot-path rules above. Apply operations in order.
Examples, unrelated to the task:
set sample.note: text:He said "hello": yes|
set sample.note: text:first\nsecond|
set sample.note: text:literal \\n|
set sample.note: text:  spaces  |
set sample.note: text:ends in pipe||
set sample.count: json:4
append sample.items: json:{"item_id":"new","value":1}
remove sample.items.old
Return only the required changes.'''
for name,srcname in [('marker-v1-development','literal-text-dev-baseline-v1'),('marker-v1-heldout','marker-v1-heldout-baseline')]:
 dest=b.parent/name;assert not (dest/'manifest.json').exists();src=b.parent/srcname;oldrefs=read(src/'references.json');requests=[];refs=[];entries={}
 for f in sorted((src/'test_specs').glob('*__research_json_v2.json')):
  original=read(f);candidate=copy.deepcopy(original);candidate['id']=original['id']+'__literal_line_marker_v1';candidate['name']=original['name']+' end-marked literal text';candidate['description']='Separate marker representation from pre-optimization dot baseline.';candidate['prompt_builder']['method']='literal_line_marker_v1'
  for v in candidate['variants']:
   v['result']['representation']='literal_line_marker_v1';binding=v['prompt_bindings'];head,structure=binding['task_requirements'].split('\n\nDatabase structure:\n',1);prefix=head.split('\n\nOutput format:\n',1)[0];binding['task_requirements']=prefix+'\n\n'+output+'\n\nDatabase structure:\n'+structure;v['steps'][0]['prompt']=render(binding)[-1]['content']
  candidate['prompt_builder']['prompt_digest']=digest({v['id']:render(v['prompt_bindings']) for v in candidate['variants']})
  for arm,t in [('original',original),('literal_line_marker_v1',candidate)]:
   validate_test(t);save(dest/'test_specs'/f"{t['id']}.json",t)
   for v in t['variants']:
    ref=next(x for x in oldrefs if x['test_id']==original['id'] and x['variant']==v['id']);answer=encode(json.loads(ref['answer'])) if arm=='literal_line_marker_v1' else ref['answer'];assert evaluate(t,v,{'patch':answer})['exact_match'] and assess(t,v,{'patch':answer})['objective_outcome']=='PASS'
    req=messages(t,v['steps'][0],{},v);p=dest/'prompts'/t['id']/(v['id']+'.txt');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(preview(req),encoding='utf8');requests.append({'test_id':t['id'],'fixture':t['prompt_builder']['fixture'],'arm':arm,'variant_id':v['id'],'repetitions':3,'message_digest':digest(req)});refs.append({'test_id':t['id'],'variant':v['id'],'answer':answer});entries[definition_id(t,v)]={'status':'accepted','blocked':False,'reason':'User authorized versioned representation evaluation','reviewer':'Codex','note':'Independent references checked','history':[]}
 assert len(requests)==36
 save(dest/'test_judgements.json',{'version':1,'entries':entries});save(dest/'references.json',refs);save(dest/'manifest.json',{'cohort':name,'fixtures':6,'arms':['original','literal_line_marker_v1'],'model':'local-28df315996a77e69','requests':requests,'scope_digest':digest(requests),'observations_per_model':108,'inference_started':False,'lineage':'pre-optimization original dot JSON; distinct output representation and isolated parser'})
 print(name,'36 requests validated; no inference started.')
