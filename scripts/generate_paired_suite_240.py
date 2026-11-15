"""Reproduce the approved 40-state/six-action suite. Never runs inference.
State recipes are synthetic research data; expectations never enter prompts.
"""
from pathlib import Path
import copy,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evaluation.array_identities_intent import resolve,scalar_text,encode_part,validate_data,apply_patch
ACTIONS=('update','append','remove','move','copy','no_op')
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def describe(state,path,identities):
 """Describe selectors in ordinary prose rather than supply an output path."""
 _,parts=resolve(state,path,identities); node=state; components=[];template=[]
 from evaluation.array_identities_intent import identity
 for part in parts:
  if isinstance(node,list):
   child=node[int(part)]; selector=identity(child,node,identities,template)
   components.append('the element with '+('ID ' if isinstance(child,dict) else 'value ')+json.dumps(selector,ensure_ascii=False));template.append(None)
  else:
   child=node[part];components.append(('the collection ' if isinstance(child,list) else 'the field ')+json.dumps(part,ensure_ascii=False));template.append(part)
  node=child
 return ' within '.join(reversed(components))
def cases():
 for index,s in enumerate(json.loads((ROOT/'scripts/paired_suite_240_states.json').read_text(encoding='utf-8')),1):
  state=s['state']; identities=s['array_identities']; source=s['source']+'.'+encode_part(scalar_text(s['selected']))
  for action in ACTIONS:
   patch={'update':[{'op':'replace','path':s['update_path'],'value':s['update_value']}],
    'append':[{'op':'add','path':s['append_path'],'value':s['new_element']}],
    'remove':[{'op':'remove','path':s['remove_path'] if action=='remove' and s['remove_path']!=s['source']+'.'+str(s['selected']) else source}],
    'move':[{'op':'move','from':source,'path':s['destination']}],
    'copy':[{'op':'copy','from':source,'path':s['destination']}],'no_op':[]}[action]
   src_desc=describe(state,s['source'],identities);dst_desc=describe(state,s['destination'],identities)
   texts={'update':f"Set {describe(state,s['update_path'],identities)} to {json.dumps(s['update_value'],ensure_ascii=False)}.",
    'append':f"Append this complete element to {describe(state,s['append_path'],identities)}: {json.dumps(s['new_element'],ensure_ascii=False)}.",
    'remove':f"Remove {describe(state,patch[0]['path'] if action=='remove' else source,identities)}.",
    'move':f"Move the complete element with {'value' if not isinstance(resolve(state,s['source'],identities)[0][0],dict) else 'ID'} {json.dumps(s['selected'],ensure_ascii=False)} from {src_desc} to {dst_desc}. Remove it from the source and preserve every field/value in the destination.",
    'copy':f"Copy the complete element with {'value' if not isinstance(resolve(state,s['source'],identities)[0][0],dict) else 'ID'} {json.dumps(s['selected'],ensure_ascii=False)} from {src_desc} to {dst_desc}. Leave the source unchanged and preserve every field/value in the destination.",
    'no_op':'The documentation uses blue headings and a serif font.'}
   archive=ROOT/'archives/suite-before-240-2026-11-15/prompt_builder/templates/test_cases'
   for original in s['originals']:
    original_action='no_op' if original=='no_change' else original.split('_')[0]
    if original_action==action:
     texts[action]=(archive/original/'requested_change.txt').read_text(encoding='utf-8').strip()
   # Independent expected-state mutation uses resolved concrete locations, not evaluator operations.
   expected=copy.deepcopy(state)
   def at(parts):
    x=expected
    for part in parts:x=x[int(part)] if isinstance(x,list) else x[part]
    return x
   if patch:
    op=patch[0];_,parts=resolve(state,op['path'],identities)
    if action=='update':
     parent=at(parts[:-1]);parent[int(parts[-1]) if isinstance(parent,list) else parts[-1]]=copy.deepcopy(op['value'])
    elif action=='append':at(parts).append(copy.deepcopy(op['value']))
    elif action=='remove':del at(parts[:-1])[int(parts[-1])]
    else:
     element,sp=resolve(state,op['from'],identities);at(parts).append(copy.deepcopy(element))
     if action=='move':del at(sp[:-1])[int(sp[-1])]
   validate_data(state,identities);validate_data(expected,identities)
   assert apply_patch(state,patch,identities)['final_state']==expected
   yield f's{index:02d}_{s["name"]}__{action}',s,action,patch,expected,texts[action]
def main():
 target=ROOT/'prompt_builder/templates/test_cases'
 manifest=[]
 for name,s,action,patch,expected,text in cases():
  p=target/name;p.mkdir(parents=True,exist_ok=True)
  for filename,data in [('starting_data.json',s['state']),('expected_result.json',expected),('expected_patch.json',patch),('array_identities.json',s['array_identities'])]:write(p/filename,data)
  (p/'requested_change.txt').write_text(text+'\n',encoding='utf-8')
  manifest.append({'case':name,'state':name.split('__')[0],'action':action,'retained_originals':s['originals'],'diversity':s['diversity']})
 write(ROOT/'scripts/paired_suite_240_manifest.json',manifest)
 print(f'Generated {len(manifest)} cases from 40 states; no inference performed.')
if __name__=='__main__':main()
