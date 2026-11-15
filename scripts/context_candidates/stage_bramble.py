"""Stage authentic game state unchanged; never edit active tests or infer."""
from generate_candidates import *
import hashlib,shutil
from evaluation.array_identities_intent import encode_part
SOURCE=OUT/'fixtures/The-Last-Light-at-Bramble-Bridge-new-game.json'
EXPECTED_SHA='ecec972f7a180a4f69bcb639b3ff11ba8a36ae5c6d7bb30f2e386e6aeb684543'
raw=SOURCE.read_bytes();assert hashlib.sha256(raw).hexdigest()==EXPECTED_SHA
state=json.loads(raw);d=OUT/'bramble-authentic';d.mkdir(exist_ok=True)
shutil.copyfile(SOURCE,d/'starting_data.json')
for provenance in ['PROVENANCE.txt','The-Last-Light-at-Bramble-Bridge-materialization.json','bramble-array-audit.json']:
 shutil.copyfile(SOURCE.parent/provenance,d/provenance)
assert (d/'starting_data.json').read_bytes()==raw
found={};occurrences=[]
def walk(x,path=()):
 if isinstance(x,list):
  field='id' if any(isinstance(v,dict) for v in x) else None
  if field:assert all(isinstance(v,dict) and 'id' in v for v in x)
  if path not in found or field:found[path]=field
  occurrences.append({'path':list(path),'length':len(x),'id_field':field})
  for v in x:walk(v,path+(None,))
 elif isinstance(x,dict):
  for k,v in x.items():walk(v,path+(k,))
walk(state)
ids=[{'path':list(p),'id_field':f} for p,f in found.items()];validate_data(state,ids);write(d/'array_identities.json',ids)
twine='A length of spare twine';fact=state['player']['known_facts'][0]
src='player.inventory.'+encode_part(twine);dst='npc_directory.locations.bramble-bridge.characters.'+encode_part('Mira Bellweather')+'.full_character.inventory'
patches={'update':[{'op':'replace','path':'player.state_of_mind','value':'Reassured by Mira’s practical plan and eager to investigate the riverbank.'}], 'append':[{'op':'add','path':'player.inventory','value':'A clean linen wrapping cloth'}], 'remove':[{'op':'remove','path':src}], 'move':[{'op':'move','from':src,'path':dst}], 'copy':[{'op':'copy','from':'player.known_facts.'+encode_part(fact),'path':'story_memory.world_notes'}], 'no_op':[]}
requests={'update':'Set the player’s state_of_mind to "Reassured by Mira’s practical plan and eager to investigate the riverbank."','append':'Append "A clean linen wrapping cloth" to the player’s inventory.','remove':'Remove "A length of spare twine" from the player’s inventory.','move':'Move "A length of spare twine" from the player’s inventory to Mira Bellweather’s full-character inventory in the Bramble Bridge location. Leave every other field unchanged.','copy':'Copy the player’s known fact "'+fact+'" into the world_notes collection in story_memory. Keep the original known fact.','no_op':'The game’s external help page should use blue headings and a serif font.'}
rows=[]
for action,patch in patches.items():
 expected=apply_patch(state,patch,ids)['final_state'];validate_data(expected,ids)
 case={'id':'bramble_authentic__'+action,'starting_data':state,'array_identities':ids,'expected_patch':patch,'expected_result':expected,'requested_change':requests[action]};write(d/(action+'.json'),case);assert json.loads((d/(action+'.json')).read_text(encoding='utf-8'))['starting_data']==state
 validate_presentation_identity(case,VIEWS)
 for fmt in FORMATS:
  assert applicable(case,fmt) is None,(action,fmt,applicable(case,fmt))
  reference=encode(state,patch,fmt,ids)
  for view in VIEWS:
   msgs=prompt(case,view,fmt);pd=d/'rendered_prompts';pd.mkdir(exist_ok=True);write(pd/f'{action}__{view}__{fmt}.json',msgs);content=''.join(m['content'] for m in msgs);cumulative=copy.deepcopy(msgs)
   for attempt in range(4):
    cumulative.extend([{'role':'assistant','content':reference},{'role':'user','content':REVIEW_QUESTION}])
    if attempt<3:cumulative.extend([{'role':'assistant','content':'no'},{'role':'user','content':REPLACEMENT_REQUEST}])
   rows.append({'action':action,'view':view,'format':fmt,'initial_content_chars':len(content),'initial_content_utf8_bytes':len(content.encode()),'messages_json_utf8_bytes':len(json.dumps(msgs,ensure_ascii=False).encode()),'reference_answer_chars':len(reference),'four_answer_review_content_chars':sum(len(m['content']) for m in cumulative),'token_count':None})
write(d/'measurements.json',rows);write(d/'array_audit.json',occurrences)
summary={'source_sha256':EXPECTED_SHA,'preserved_source_bytes':len(raw),'compact_json_bytes':len(json.dumps(state,ensure_ascii=False,separators=(',',':')).encode()),'array_occurrences':len(occurrences),'array_declarations':len(ids),'max_initial_chars':max(r['initial_content_chars'] for r in rows),'max_reference_cumulative_chars':max(r['four_answer_review_content_chars'] for r in rows),'verified_cases':6,'verified_format_applicability':36,'rendered_prompts':108,'tokens':None}
write(d/'summary.json',summary);print(json.dumps(summary,indent=2))
