"""Export disabled Ember-method prompts and an explicit unsupported-fixture ledger."""
import argparse
import json
from pathlib import Path
from .builder import ROOT
from .ember_prompt import compile_test,reference,support_reason,provenance
from .normal_prompt import preview
from workbench.domain import digest,read_json
from workbench.workflows import messages

def build(output,reviews=None):
    root=Path(output);manifest={'method':'ember_text_v1','status':'pending_exact_prompt_review','source_contract':provenance(),
        'inference_started':False,'unsupported':[],'prompts':[],'comparison_note':'Compare only the same supported fixtures; do not compare this narrowed denominator against a full-suite percentage. Full paths display uses native object paths with complete collection values.'}
    def write(path,value):
        p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    definitions=0
    for fixture in read_json(ROOT/'fixtures.json')['fixtures']:
        reason=support_reason(fixture)
        if reason:manifest['unsupported'].append({'fixture':fixture['id'],'task':fixture['task'],'reason':reason});continue
        t=compile_test(fixture,reviews);definitions+=1;write('test_specs/'+t['id']+'.json',t)
        answer,expected=reference(fixture);write('references/'+t['id']+'.json',{'synthetic_reference_only':True,'response':answer,'expected_state':expected})
        for v in t['variants']:
            request=messages(t,v['steps'][0],{},v);name='prompts/'+t['id']+'/'+v['id']
            write(name+'.messages.json',request);(root/(name+'.txt')).write_text(preview(request),encoding='utf8')
            manifest['prompts'].append({'test_id':t['id'],'fixture':fixture['id'],'format':v['id'],'message_digest':digest(request),
                                       'repetitions':t['repetitions'],'enabled':t['enabled'],'messages_file':name+'.messages.json'})
    manifest.update(definitions=definitions,prompt_presentations=len(manifest['prompts']),observations_per_model=sum(p['repetitions']for p in manifest['prompts']))
    manifest['scope_digest']=digest(manifest['prompts']);write('manifest.json',manifest)
    return {k:manifest[k]for k in ('definitions','prompt_presentations','observations_per_model','scope_digest','unsupported')}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    print(json.dumps(build(args.output),indent=2))
