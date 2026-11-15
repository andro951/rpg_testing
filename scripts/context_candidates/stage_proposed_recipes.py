"""Proposed only: render paired-generator prose without changing active suite."""
import sys,json,copy,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
if not (ROOT/'prompt_builder').is_dir():
 raise RuntimeError('Place this renderer under repository scripts/context_candidates.')
sys.path.insert(0,str(ROOT))
import generate_candidates as diagnostics
from scripts.generate_paired_suite_240 import cases
from prompt_builder.builder import prompt,applicable,validate_presentation_identity
from prompt_builder.reference_output import encode
from workbench.self_review import REVIEW_QUESTION,REPLACEMENT_REQUEST

def write(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

proposed=json.loads((OUT/'proposed-recipes.json').read_text(encoding='utf-8'))
assert {r['intended_state_index'] for r in proposed}=={26,32,37}
summaries=[]
for entry in proposed:
 index=entry['intended_state_index'];recipe=entry['recipe']
 if recipe['name']=='authentic_bramble_new_game':
  raw=(OUT/'fixtures/The-Last-Light-at-Bramble-Bridge-new-game.json').read_bytes()
  assert hashlib.sha256(raw).hexdigest()=='ecec972f7a180a4f69bcb639b3ff11ba8a36ae5c6d7bb30f2e386e6aeb684543'
  assert recipe['state']==json.loads(raw)
 original=copy.deepcopy(recipe);rows=[]
 for generated_name,s,action,patch,expected,text in cases([recipe]):
  name=f's{index:02d}_{recipe["name"]}__{action}'
  # cases() independently mutates expected state, then cross-checks evaluator application.
  assert (expected==s['state']) == (action=='no_op'),name
  assert s['state']==original['state']
  case={'id':name,'starting_data':s['state'],'array_identities':s['array_identities'],'expected_patch':patch,'expected_result':expected,'requested_change':text}
  write(OUT/'paired-prose-rendered'/recipe['name']/'cases'/f'{action}.json',case)
  validate_presentation_identity(case,diagnostics.VIEWS)
  for fmt in diagnostics.FORMATS:
   assert applicable(case,fmt) is None
   reference=encode(s['state'],patch,fmt,s['array_identities'])
   for view in diagnostics.VIEWS:
    messages=prompt(case,view,fmt);content=''.join(m['content'] for m in messages)
    write(OUT/'paired-prose-rendered'/recipe['name']/'rendered_prompts'/f'{action}__{view}__{fmt}.json',messages)
    history=copy.deepcopy(messages)
    for attempt in range(4):
     history.extend([{'role':'assistant','content':reference},{'role':'user','content':REVIEW_QUESTION}])
     if attempt<3:history.extend([{'role':'assistant','content':'no'},{'role':'user','content':REPLACEMENT_REQUEST}])
    rows.append({'action':action,'view':view,'format':fmt,'initial_content_chars':len(content),'initial_content_utf8_bytes':len(content.encode()),'messages_json_utf8_bytes':len(json.dumps(messages,ensure_ascii=False).encode()),'reference_answer_chars':len(reference),'four_answer_review_content_chars':sum(len(m['content']) for m in history),'token_count':None})
 assert recipe==original
 write(OUT/'paired-prose-rendered'/recipe['name']/'measurements.json',rows)
 summaries.append({'name':recipe['name'],'intended_state_index':index,'rendered_prompts':len(rows),'max_initial_chars':max(r['initial_content_chars'] for r in rows),'max_cumulative_reference_chars':max(r['four_answer_review_content_chars'] for r in rows),'token_count':None})
write(OUT/'paired-prose-rendered/summary.json',summaries)
print(json.dumps(summaries,indent=2))
