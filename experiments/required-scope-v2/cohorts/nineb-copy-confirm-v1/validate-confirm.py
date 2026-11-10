import json, sys
from pathlib import Path

b=Path(__file__).resolve().parent
root=b.parent/'dot-rewrite-heldout-v1'/'desktop'
sys.path.insert(0,str(root))
from workbench.domain import digest,validate_test
from workbench.workflows import messages,evaluate
from workbench.dot_paths import resolve
from evaluation.core import assess
from jsonschema import Draft202012Validator

man=json.loads((b/'manifest.json').read_text());refs=json.loads((b/'references.json').read_text())
tests={p.stem:json.loads(p.read_text(encoding='utf8')) for p in (b/'test_specs').glob('*.json')}
old=b.parent/'dot-escape-heldout-v1'/'test_specs'
oldtests=[json.loads(p.read_text(encoding='utf8')) for p in old.glob('*.json')]
oldheads={}
for t in oldtests:
    arm='promptcopy_v1' if t['id'].endswith('__promptcopy_v1') else 'original'
    for v in t['variants']:
        h=v['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0]
        oldheads.setdefault(arm,h);assert oldheads[arm]==h
assert len(tests)==8 and len(man['requests'])==24
for ident,t in tests.items():
    validate_test(t)
    Draft202012Validator(t['state_schema']).validate(t['source']['initial_state'])
    Draft202012Validator(t['state_schema']).validate(t['expected_state'])
    arm='promptcopy_v1' if ident.endswith('__promptcopy_v1') else 'original'
    if arm=='promptcopy_v1':
        orig=tests[ident.removesuffix('__promptcopy_v1')]
        for k in ('source','state_schema','expected_state'): assert t[k]==orig[k]
    for v in t['variants']:
        assert v['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0]==oldheads[arm]
        if arm=='promptcopy_v1':
            q=next(w for w in orig['variants'] if w['id']==v['id'])
            assert v['result']==q['result'] and v['steps'][0]['sampling']==q['steps'][0]['sampling']
            for field in ('current_state','new_information','presentation_notes'): assert v['prompt_bindings'][field]==q['prompt_bindings'][field]
        ref=next(r for r in refs if r['test_id']==ident and r['variant']==v['id'])
        assert evaluate(t,v,{'patch':ref['answer']})['exact_match']
        assert assess(t,v,{'patch':ref['answer']})['objective_outcome']=='PASS'
        assert digest(messages(t,v['steps'][0],{},v))==next(x['message_digest'] for x in man['requests'] if x['test_id']==ident and x['variant_id']==v['id'])
        if v['id']=='full_paths':
            for line in v['prompt_bindings']['current_state'].splitlines():
                p,x=line.split(':',1);actual,_,_=resolve(t['source']['initial_state'],t['state_schema'],p);assert actual==json.loads(x)
out={'fixture_count':4,'schemas':4,'arms':2,'requests':24,'observations_per_model':72,'original_copy_same_state_schema_expected_task_result_sampling':True,'both_instruction_heads_match_prior_frozen_recipes':True,'reference_both_evaluators':'pass','all_full_paths_resolve':'pass','heldout_unrun':True,'models':man['models'],'context_tokens':32768}
(b/'validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
