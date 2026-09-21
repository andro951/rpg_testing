"""Same pending-first planner for manual preparation and unattended native execution."""
from __future__ import annotations
import os
import platform
import shutil
import socket
import tempfile
from pathlib import Path
from .domain import load_tests, device_tier
from .inventory import automatic_context, detect_gpus, executable, scan_models
from .planning import pending_plan, public_plan
from .execution_policy import POLICY_VERSION


def issue(code,message,label=None,action=None,level='blocked'):
    return {'id':code,'message':message,'level':'fixable' if action else level,'label':label,'action':action}


def build(app,preparation=None):
    problems=[];warnings=[];settings=app.settings
    models=app.catalog();tests=load_tests(app.root/'test_specs')
    if not tests:problems.append(issue('tests','No enabled test files. Enable one in Test definitions.'))
    if app.demo:gpu={'name':'SIMULATED GTX 1080','uuid':'demo','total_gib':8,'free_gib':8,'driver':'simulated'}
    elif preparation:gpu={'name':preparation['gpu_name'],'total_gib':preparation['vram_gb'],'uuid':None,'driver':None}
    else:
        try:
            gpus=detect_gpus()
            if len(gpus)!=1:raise ValueError('Exactly one visible NVIDIA GPU is required')
            gpu=gpus[0]
        except Exception as exc:
            problems.append(issue('gpu','GPU detection failed: '+str(exc)))
            gpu={'name':'Unavailable','total_gib':0,'uuid':None,'driver':None}
    target={'gpu_name':gpu['name'],'vram_gb':device_tier(gpu['total_gib']) or gpu['total_gib'],
            'backend':'demo' if app.demo else 'llamacpp','backend_version':app.backend_version(),
            'os':platform.platform(),'python':platform.python_version(),'cpu':platform.processor() or platform.machine(),
            'driver':gpu.get('driver'),'context_recipe':automatic_context(tests,{'planning.context_length':2**40})['allocated_tokens'],
            'execution_policy':POLICY_VERSION}
    for file in app.store.root.glob('*/*.json'):
        try:app.store.read(file)
        except (ValueError,KeyError,TypeError) as exc:
            try:app.store.path(file.parent.name,file.stem)
            except ValueError:
                problems.append(issue('corrupt_filename','Invalid result filename: '+str(file)));continue
            problems.append(issue('corrupt_'+file.stem,'Corrupt result: '+str(exc),'Delete corrupted result',
                                  {'type':'delete_corrupt','model_id':file.parent.name,'case_id':file.stem}))
    if any(i['id'].startswith('corrupt_') for i in problems):
        return {'ready':False,'prepared':False,'issues':problems,'gpu':gpu,'plan':{'pending':0,'groups':[]}},None
    models=app.with_known_pins(models)
    plan=pending_plan(models,tests,target,app.store)
    folder_info=app.folder_info();path=folder_info.get('path')
    found=app.demo_models() if app.demo else scan_models(Path(path),models) if path else []
    app.last_models=found
    changed=False
    for item in found:
        if item['catalogued'] and item['complete'] and not item['errors']:
            pinned=app.fingerprint(item)
            for model in models:
                if model['id']==item['id'] and model.get('sha256')!=pinned:model['sha256']=pinned;changed=True
    if changed:plan=pending_plan(models,tests,target,app.store)
    grouped={}
    for item in found:grouped.setdefault(item['id'],[]).append(item)
    if plan['pending']:
        if not app.demo:
            if not path or not Path(path).is_dir():
                problems.append(issue('folder','Choose an existing models folder. None is assumed.','Choose model folder',{'type':'choose_folder'}))
            elif not found and settings.get('confirmed_empty_folder')!=path:
                problems.append(issue('empty_folder','No models found. Was this the intended empty folder?','Confirm empty folder',{'type':'confirm_folder'}))
            exe=executable('llama-server',settings.get('llama_path',''))
            if not exe:
                problems.append(issue('backend','A compatible native llama.cpp runtime is required.','Find runtime releases',{'type':'runtime_browser'}))
            else:
                try:
                    from .native import capabilities
                    capabilities(exe,preparation=bool(preparation))
                except Exception as exc:problems.append(issue('backend_capabilities',str(exc),'Find runtime releases',{'type':'runtime_browser'}))
            if not preparation:
                with socket.socket() as sock:
                    sock.settimeout(.25)
                    if sock.connect_ex(('127.0.0.1',1235))==0:problems.append(issue('port','Native server port 1235 is used by an unrelated process. Stop it before running.'))
        for name in ('results','logs'):
            directory=app.data/name
            if not directory.is_dir():problems.append(issue('folder_'+name,'Missing '+name+' folder','Create '+name+' folder',{'type':'create_folder','name':name}))
            else:
                try:
                    with tempfile.TemporaryFile(dir=directory):pass
                except OSError as exc:problems.append(issue('write_'+name,str(exc)))
        if shutil.disk_usage(app.data).free<128*1024**2:problems.append(issue('disk','Free at least 128 MiB for result/log files.'))
        for group in plan['groups']:
            if not group['jobs']:continue
            mid=group['model']['id'];items=grouped.get(mid,[])
            if len(items)>1:
                problems.append(issue('duplicate_'+mid,'Multiple installations match '+mid+'. Keep one copy in the selected folder.'));continue
            item=items[0] if items else None
            if not item or not item['complete']:
                action={'type':'download_model','model_id':mid} if group['model'].get('repo_id') and path else None
                problems.append(issue('missing_'+mid,'Pending cases require missing model/shards: '+mid,'Download missing '+mid if action else None,action));continue
            group['installed']=item
            if item['errors']:problems.append(issue('invalid_'+mid,'Invalid GGUF: '+str(item['errors'])));continue
            try:group['context']=automatic_context(tests,item['metadata'])
            except ValueError as exc:problems.append(issue('context_'+mid,str(exc)));continue
            if not preparation and not app.demo and item['size_bytes']/2**30>=gpu.get('free_gib',0):
                warnings.append(mid+': weights exceed currently free GPU memory; full-GPU load will be attempted and its failure recorded. Recovery runs only after the primary pass.')
    for item in found:
        if item['required_vram_gb'] is None:
            problems.append(issue('unassigned_'+item['id'],'Assign a VRAM tier to '+item['name'],'Assign VRAM',{'type':'models'}))
    problems.extend(app.git_issues())
    report={'ready':not problems and not preparation,'prepared':not problems and bool(preparation),
            'preparation_only':bool(preparation),'issues':problems,'warnings':warnings,'plan':public_plan(plan),'gpu':gpu,
            'folder':folder_info,'inventory_warning':None,
            'note':'Preparation checks files on this host, not a future Unity allocation.' if preparation else
                   'No user prompts during execution. Model placement is checked at load; failed full-GPU cases precede separate recovery comparisons.'}
    return report,plan
