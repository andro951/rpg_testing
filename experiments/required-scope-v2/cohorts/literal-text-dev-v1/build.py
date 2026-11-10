import copy,json,sys
from pathlib import Path
base=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task');src=base/'literal-text-dev-baseline-v1';b=base/'literal-text-dev-v1';b.mkdir(exist_ok=True);root=base/'literal-text-branch-v1'/'runtime';sys.path.insert(0,str(root));from workbench.domain import digest,validate_test;from workbench.workflows import messages,evaluate;from workbench.literal_line import encode;from evaluation.core import assess;from test_builder.original_prompt import render;from test_builder.normal_prompt import preview;from workbench.judgements import definition_id
read=lambda p:json.loads(p.read_text(encoding='utf8'));save=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8');oldrefs=read(src/'references.json');entries={};reqs=[];refs=[];(b/'test_specs').mkdir(exist_ok=True)
output='''Output format:
Return only update lines, without explanation or Markdown. Return exactly none if no change is needed. Each complete update occupies one physical line.
For an existing field: set dot.path: text:literal text through end of line
For an existing non-string field: set dot.path: json:JSON_value
To append one element: append dot.path: text:literal text OR append dot.path: json:JSON_value
To remove an element: remove dot.path
Use text: only for strings. Text begins immediately after text: and every character through end of line is part of the value, including leading and trailing spaces and colons; there are no outer quotes. Encode a literal backslash as two backslashes, a newline as backslash+n, and a carriage return as backslash+r. No other backslash escapes are permitted. Empty text is written as text: with nothing after it. Use json: for a complete non-string JSON value; objects and arrays use normal JSON syntax. Do not use json: for a string. Paths follow the dot-path rules above. Apply operations in order.
Examples, unrelated to the task:
set sample.note: text:He said "hello": yes
set sample.count: json:4
append sample.items: json:{"item_id":"new","value":1}
remove sample.items.old
Return only the required changes.'''
for p in sorted((src/'test_specs').glob('*__research_json_v2.json')):
 t=read(p);arm='promptcopy_v1' if t['id'].endswith('__promptcopy_v1')else 'original';variants=[(arm,t)]
 if arm=='original':
  u=copy.deepcopy(t);u['id']=t['id']+'__literal_line_v1';u['name']=t['name']+' literal line v1';u['description']='Representation/parser branch from preserved original dot baseline.';u['prompt_builder']['method']='literal_line_v1'
  for v in u['variants']:
   v['result']['representation']='literal_line_v1';binding=v['prompt_bindings'];head,structure=binding['task_requirements'].split('\n\nDatabase structure:\n',1);assert '\n\nOutput format:\n'in head;prefix=head.split('\n\nOutput format:\n',1)[0];binding['task_requirements']=prefix+'\n\n'+output+'\n\nDatabase structure:\n'+structure;v['steps'][0]['prompt']=render(binding)[-1]['content']
  u['prompt_builder']['prompt_digest']=digest({v['id']:render(v['prompt_bindings']) for v in u['variants']});variants.append(('literal_line_v1',u))
 for arm,u in variants:
  validate_test(u);save(b/'test_specs'/f"{u['id']}.json",u)
  for v in u['variants']:
   ref=next(x for x in oldrefs if x['test_id']==t['id'] and x['variant']==v['id']);answer=encode(json.loads(ref['answer'])) if arm=='literal_line_v1' else ref['answer'];assert evaluate(u,v,{'patch':answer})['exact_match'] and assess(u,v,{'patch':answer})['objective_outcome']=='PASS';req=messages(u,v['steps'][0],{},v);f=b/'prompts'/u['id']/(v['id']+'.txt');f.parent.mkdir(parents=True,exist_ok=True);f.write_text(preview(req),encoding='utf8');reqs.append({'test_id':u['id'],'fixture':u['prompt_builder']['fixture'],'arm':arm,'variant_id':v['id'],'repetitions':3,'message_digest':digest(req)});refs.append({'test_id':u['id'],'variant':v['id'],'answer':answer});entries[definition_id(u,v)]={'status':'accepted','blocked':False,'reason':'User authorized representation branch; reference semantics preserved','reviewer':'Codex','note':'Fresh heldout, independently validated','history':[]}
assert len(reqs)==36;save(b/'test_judgements.json',{'version':1,'entries':entries});save(b/'references.json',refs);save(b/'manifest.json',{'cohort':'literal-text-dev-v1','fixtures':6,'arms':['original','literal_line_v1'],'requests':reqs,'scope_digest':digest(reqs),'inference_started':False,'observations_per_model':108});save(b/'lineage.json',{'literal_branch':'literal_line_v1','parent':'preserved original dot JSON, before prompt optimization','intervention':'representation and isolated parser','semantic_evaluator':'canonical dot-path final-state and required-op checks','text_contract':'unquoted to end of line; backslash escaped as double backslash; newline as backslash-n; carriage return as backslash-r; empty and whitespace preserved','nonstring':'json: complete JSON non-string','candidate_prompt_copy':'dot-json-instruction-copy-v1','heldout_unrun':True});print('36 requests, 108 observations/model; original/literal reference answers pass both evaluators.')
