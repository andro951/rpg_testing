"""Export a separate disabled original+dot experiment; never edit active controls."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
from .builder import ROOT, compile_test, oracle
from .normal_prompt import preview
from .original_prompt import baseline
from workbench.domain import digest, read_json
from workbench.workflows import messages


def build(root):
    root=Path(root)
    fixtures=read_json(ROOT/'fixtures.json')['fixtures']
    manifest={'schema_version':1,'method':'dot_patch_v1','status':'pending_joint_prompt_review',
              'model_runs_started_by_builder':0,'original_manifest_sha256':baseline()['original_manifest_sha256'],
              'baseline_origin':'Original930 actual messages, before manual quote clarification and OPRO',
              'noop_distinction':'Current unrelated-information task retained. Three NOOP prompt versions are not notation-only matches to original930.',
              'normalization_scope':'Only path/from strings, after strict outer JSON parsing; data values and original raw responses are preserved.',
              'missing_original930_model_baselines':['desktop Qwen3.5-9B Q4_K_S','all four Unity model/worker cohorts'],
              'prompts':[]}
    diffs=[];matched=0
    def write(relative,value):
        p=root/relative;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    for fixture in fixtures:
        control=compile_test(fixture,method='original_value_patch_v1')
        dot=compile_test(fixture,method='dot_patch_v1')
        write('test_specs/'+dot['id']+'.json',dot)
        answer,state=oracle(fixture,'dot_patch_v1')
        write('references/'+dot['id']+'.json',{'label':'synthetic reference, not model inference','patch':answer,'expected_state':state})
        for variant in dot['variants']:
            mode=variant['id'];request=messages(dot,variant['steps'][0],{},variant)
            original=baseline()['messages'][fixture['id']+'__value_patch'][mode]
            cv=next(v for v in control['variants']if v['id']==mode)
            reconstructed=messages(control,cv['steps'][0],{},cv)
            unchanged=fixture['task']!='no_change'
            if unchanged:
                if reconstructed!=original:raise ValueError('Original prompt reconstruction differs: '+fixture['id']+'/'+mode)
                matched+=1
            relative='prompts/'+dot['id']+'/'+mode
            write(relative+'.messages.json',request)
            p=root/(relative+'.txt');p.write_text(preview(request),encoding='utf-8',newline='\n')
            write('controls/'+fixture['id']+'/'+mode+'.original930.messages.json',original)
            write('controls/'+fixture['id']+'/'+mode+'.current-noop-original-renderer.messages.json',reconstructed)
            diffs.extend(difflib.unified_diff(original[-1]['content'].splitlines(keepends=True),request[-1]['content'].splitlines(keepends=True),fromfile=fixture['id']+'/'+mode+'/original930',tofile=fixture['id']+'/'+mode+'/original-dot-v1'))
            manifest['prompts'].append({'test_id':dot['id'],'fixture':fixture['id'],'format':mode,'method':'dot_patch_v1',
               'file':relative+'.txt','messages_file':relative+'.messages.json','message_digest':digest(request),
               'prompt_digest':dot['prompt_builder']['prompt_digest'],'original_message_digest':digest(original),
               'original_reconstruction_matches':reconstructed==original,'notation_only_comparison_eligible':unchanged,'enabled':False})
    manifest['original_prompts_reconstructed_exactly']=matched
    manifest['original_noop_versions_replaced']=3
    manifest['prompt_scope_digest']=digest([{k:p[k]for k in('test_id','format','message_digest')}for p in manifest['prompts']])
    manifest['method_text_sha256']=hashlib.sha256((ROOT/'methods/dot_patch_v1.txt').read_bytes()).hexdigest()
    write('manifest.json',manifest)
    (root/'original930-to-dot.diff').write_text(''.join(diffs),encoding='utf-8',newline='\n')
    return {'definitions':len(fixtures),'prompts':len(manifest['prompts']),'enabled':0,'scope_digest':manifest['prompt_scope_digest'],
            'original_exact_reconstructions':matched,'noop_changed_prompts':3}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(build(parser.parse_args().output),indent=2))
