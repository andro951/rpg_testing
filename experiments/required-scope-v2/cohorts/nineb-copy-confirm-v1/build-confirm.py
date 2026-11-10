"""Freeze both existing prompt arms on the new VL8 confirmation cases."""
import copy, hashlib, json, sys
from pathlib import Path

b = Path(__file__).resolve().parent
root = b.parent / 'dot-rewrite-heldout-v1' / 'desktop'
sys.path.insert(0, str(root))
from workbench.domain import digest, validate_test
from workbench.workflows import messages, evaluate
from evaluation.core import assess
from workbench.prompt_rendering import render
from workbench.prompt_rendering import preview
from workbench.judgements import definition_id

read = lambda p: json.loads(p.read_text(encoding='utf8'))
def save(p,x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

prior=read(next((b.parent/'dot-escape-heldout-v1'/'test_specs').glob('*__promptcopy_v1.json')));candidate=prior['variants'][0]['prompt_bindings']['task_requirements'].split('\n\nDatabase structure:\n',1)[0]
oldrefs = read(b/'baseline'/'references.json')
requests, refs, entries = [], [], {}
for f in sorted((b/'baseline'/'test_specs').glob('*__research_json_v2.json')):
    original = read(f)
    proposed = copy.deepcopy(original)
    proposed['id'] = original['id'] + '__promptcopy_v1'
    proposed['name'] = original['name'] + ' instruction copy v1'
    proposed['description'] = 'Model-specific confirmation, unchanged previously tested prompt copy.'
    proposed['prompt_builder']['method'] = 'promptcopy_v1'
    for v in proposed['variants']:
        binding = v['prompt_bindings']
        _, structure = binding['task_requirements'].split('\n\nDatabase structure:\n',1)
        binding['task_requirements'] = candidate + '\n\nDatabase structure:\n' + structure
        v['steps'][0]['prompt'] = render(binding)[-1]['content']
    proposed['prompt_builder']['prompt_digest'] = digest({v['id']:render(v['prompt_bindings']) for v in proposed['variants']})
    for arm,t in [('original',original),('promptcopy_v1',proposed)]:
        validate_test(t)
        save(b/'test_specs'/f"{t['id']}.json",t)
        for v in t['variants']:
            ref = next(x for x in oldrefs if x['test_id']==original['id'] and x['variant']==v['id'])
            answer = ref['answer']
            assert evaluate(t,v,{'patch':answer})['exact_match']
            assert assess(t,v,{'patch':answer})['objective_outcome']=='PASS'
            req = messages(t,v['steps'][0],{},v)
            p=b/'prompts'/t['id']/(v['id']+'.txt');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(preview(req),encoding='utf8')
            requests.append({'test_id':t['id'],'fixture':t['prompt_builder']['fixture'],'arm':arm,'variant_id':v['id'],'repetitions':3,'message_digest':digest(req)})
            refs.append({'test_id':t['id'],'variant':v['id'],'answer':answer})
            entries[definition_id(t,v)]={'status':'accepted','blocked':False,'reason':'Model-specific confirmation of existing recipes','reviewer':'Codex','note':'Fresh schemas, independently constructed expected states and reference checks','history':[]}
assert len(requests)==24
save(b/'test_judgements.json',{'version':1,'entries':entries})
save(b/'references.json',refs)
save(b/'manifest.json',{'cohort':'nineb-copy-confirm-v1','fixtures':4,'arms':['original','promptcopy_v1'],'models':['local-81e2a88130ccfa4e','local-8c5e666555c53096'],'requests':requests,'scope_digest':digest(requests),'observations_per_model':72,'inference_started':False})
print('Prepared four distinct-schema cases, 24 requests, 72 planned observations per model; both evaluator reference checks passed.')
