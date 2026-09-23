"""Readiness report. Checking never downloads, installs, unloads or changes settings."""
from __future__ import annotations
import importlib.util
import os
import platform
import shutil
import socket
import tempfile
from pathlib import Path
from .domain import ResultStore, load_tests, read_json, device_tier
from .inventory import automatic_context, command, detect_gpus, executable, scan_models
from .planning import pending_plan, public_plan, requirements, validate_selection


def issue(code, message, label=None, action=None, level='blocked'):
    return {'id':code,'message':message,'level':'fixable' if action else level,'label':label,'action':action}


def build(app, preparation=None, track_progress=True, selection=None):
    def update(task,task_percent,overall_percent,detail=''):
        if track_progress:app.set_progress('preflight',task,task_percent,overall_percent,detail)
    problems=[];settings=app.settings;kind=settings['backend']
    update('Loading benchmark definitions',0,10,'Reading models and enabled test files.')
    all_models=app.catalog();tests=load_tests(app.root/'test_specs')
    selection=validate_selection(selection,all_models,tests)
    models=[m for m in all_models if not selection or 'model_id' not in selection or m['id']==selection['model_id']]
    update('Loading benchmark definitions',100,15,f'{len(tests)} enabled tests loaded.')
    if not tests:problems.append(issue('tests','No enabled test files. Add or enable a test in Test definitions.'))
    update('Detecting GPU and runtime',10,16,'Inspecting the execution environment.')
    if app.demo:
        gpu={'name':'SIMULATED GTX 1080','uuid':'demo','total_gib':8,'free_gib':8,'driver':'simulated'}
    elif preparation:
        gpu={'name':preparation['gpu_name'],'total_gib':preparation['vram_gb'],'uuid':None,'driver':None}
    else:
        try:
            gpus=detect_gpus()
            if len(gpus)!=1:raise ValueError('Exactly one visible NVIDIA GPU is required; use a single-GPU allocation.')
            gpu=gpus[0]
        except Exception as exc:
            problems.append(issue('gpu','GPU detection failed: '+str(exc)))
            gpu={'name':'Unavailable','total_gib':0,'driver':None,'uuid':None}
    backend_version=app.backend_version()
    update('Detecting GPU and runtime',100,20,'Hardware and backend identity collected.')
    target={'gpu_name':gpu['name'],'vram_gb':device_tier(gpu['total_gib'],gpu['name']) or gpu['total_gib'],
            'backend':'demo' if app.demo else kind,'backend_version':backend_version,
            'os':platform.platform(),'python':platform.python_version(),'cpu':platform.processor() or platform.machine(),'driver':gpu.get('driver'),
            # Context allocation uses the whole enabled suite, never just what remains.
            # The recipe is computable without model files so completed models remain optional.
            'context_recipe':automatic_context(tests, {'planning.context_length':2**63-1})['allocated_tokens'],
            'execution_policy':'native-two-pass-v2'}
    update('Checking existing results',0,20,'Validating saved completion evidence.')
    # Pins are metadata, NOT completion tracking. Recover from checksummed results if needed.
    for file in app.store.root.glob('*/*.json'):
        if selection and 'model_id' in selection and file.parent.name!=selection['model_id']:continue
        try:app.store.read(file)
        except (ValueError,KeyError,TypeError) as exc:
            try:app.store.path(file.parent.name,file.stem)
            except ValueError:
                problems.append(issue('corrupt_filename','Invalid result filename: '+str(file)));continue
            problems.append(issue('corrupt_'+file.stem,'Corrupt result: '+str(exc),'Delete corrupted result',
                                  {'type':'delete_corrupt','model_id':file.parent.name,'case_id':file.stem}))
    if any(i['id'].startswith('corrupt_') for i in problems):
        return {'ready':False,'prepared':False,'preparation_only':bool(preparation),'issues':problems,'selection':selection,
                'gpu':gpu,'plan':{'pending':0,'complete':0,'model_loads':0,'groups':[]},
                'note':'Completion cannot be trusted until corrupt result files are resolved.'},None
    update('Checking existing results',100,25,'Saved result files checked.')
    models=app.with_known_artifacts(models)
    store=app.store
    plan=pending_plan(models,tests,target,store,selection)
    folder_info=app.folder_info()
    path=folder_info.get('path')
    inventory=[];inventory_error=None
    update('Scanning model files',0,25,'Finding GGUF files and reading lightweight metadata.')
    def scan_progress(done,total,name):
        update('Scanning model files',100*done/max(1,total),25+10*done/max(1,total),name)
    found=app.demo_models() if app.demo else scan_models(Path(path),all_models,scan_progress) if path else []
    update('Scanning model files',100,35,f'{len(found)} model variants discovered.')
    app.last_models=found;app.folder_scanned=bool(path)
    # Cheap metadata identity prevents ordinary file replacements from reusing older completion evidence.
    # Full-file SHA-256 is deliberately not computed here; trusted source hashes are retained when already known.
    changed=False
    identity_items=[item for item in found if item['catalogued'] and item['complete'] and not item['errors']
                    and (not selection or 'model_id' not in selection or item['id']==selection['model_id'])]
    update('Identifying model files',100 if not identity_items else 0,35,
           'No eligible model files need identification.' if not identity_items else f'0 / {len(identity_items)} models')
    for item_index,item in enumerate(identity_items,1):
        identity=app.identify_artifact(item)
        for m in models:
            if m['id']==item['id'] and m.get('artifact_identity')!=identity:
                m['artifact_identity']=identity;changed=True
        update('Identifying model files',100*item_index/max(1,len(identity_items)),
               35+55*item_index/max(1,len(identity_items)),
               f'Model {item_index}/{len(identity_items)} · {item["name"]}')
    update('Identifying model files',100,90,
           f'{len(identity_items)} model identities checked from filename, size, modification time and known source metadata.')
    if changed:plan=pending_plan(models,tests,target,store,selection)
    grouped={}
    for item in found:grouped.setdefault(item['id'],[]).append(item)
    update('Checking execution readiness',0,90,'Checking storage, runtime controls, contexts, and pending models.')
    # A missing folder or backend is irrelevant when no pending model needs it.
    if plan['pending']:
        if not path and not app.demo:
            problems.append(issue('folder',folder_info.get('issue') or 'Choose the active model folder.','Choose model folder',{'type':'choose_folder'},'needs_input'))
        elif path and not Path(path).is_dir() and not app.demo:
            problems.append(issue('folder','The chosen models folder is unavailable.','Choose model folder',{'type':'choose_folder'}))
        elif not found and not app.demo and settings.get('confirmed_empty_folder')!=path:
            problems.append(issue('empty_folder','The current configured model folder is empty: '+str(path),'Confirm this folder',{'type':'confirm_folder'}))
        for name in ('results','logs'):
            directory=app.data/name
            if not directory.is_dir():
                problems.append(issue('folder_'+name,'Missing '+name+' folder.','Create '+name+' folder',{'type':'create_folder','name':name}))
            else:
                try:
                    with tempfile.TemporaryFile(dir=directory):pass
                except OSError as exc:problems.append(issue('write_'+name,'Cannot write '+name+': '+str(exc)))
        try:
            if shutil.disk_usage(app.data).free<128*1024**2:problems.append(issue('disk','Less than 128 MiB free for logs and results. Free space before running.'))
        except OSError as exc:problems.append(issue('disk',str(exc)))
        if not app.demo:
            exe=executable('llama-server',settings.get('llama_path',''))
            if not exe:
                problems.append(issue('backend','Native llama.cpp is missing.','Install llama.cpp',{'type':'runtime_install'}))
            else:
                try:
                    from .native import capabilities
                    capabilities(exe,preparation=bool(preparation))
                except Exception as exc:problems.append(issue('backend_capability',str(exc),'Install / select runtime',{'type':'runtime'}))
            if not preparation:
                try:
                    with socket.socket() as sock:sock.bind(('127.0.0.1',1235))
                except OSError:problems.append(issue('port','Port 1235 is owned by another process. It was not stopped.'))
        for group in plan['groups']:
            if not group['jobs']:continue
            mid=group['model']['id'];items=grouped.get(mid,[])
            if not items:
                action={'type':'download_model','model_id':mid} if group['model'].get('repo_id') and path else None
                problems.append(issue('missing_'+mid,'Pending tests require '+mid+'. Model files are missing.', 'Download '+mid if action else None,action))
                continue
            if len(items)!=1:
                problems.append(issue('duplicate_'+mid,'Multiple installed copies match '+mid+'. Remove the duplicate from the configured model folder.'));continue
            model=items[0];group['installed']=model
            if not model['complete'] or model['errors']:
                action={'type':'download_model','model_id':mid} if not model['errors'] and group['model'].get('repo_id') else None
                problems.append(issue('invalid_'+mid,'Incomplete/invalid model '+mid+': '+str(model['missing_shards']+model['errors']), 'Download missing shards' if action else None,action));continue
            try:
                group['context']=automatic_context(tests,model['metadata'])
            except ValueError as exc:problems.append(issue('context_'+mid,str(exc)));continue
    if selection and 'model_id' in selection and selection['model_id'] in plan['excluded']:
        problems.append(issue('selected_model_tier','The selected model is not eligible for this GPU tier. Check its assignment in Installed models.','Review VRAM assignment',{'type':'models'}))
    if selection and 'model_id' in selection and selection['model_id'] in plan['unassigned']:
        problems.append(issue('selected_model_unassigned','Assign a VRAM tier to the selected model first.','Assign VRAM',{'type':'models'}))
    for item in found:
        if selection and 'model_id' in selection and item['id']!=selection['model_id']:continue
        if item['required_vram_gb'] is None:
            problems.append(issue('unassigned_'+item['id'],'Assign a VRAM tier to '+item['name']+' in Models.','Assign VRAM',{'type':'models'},'needs_input'))
    update('Checking execution readiness',85,98,'Checking Git/source state and final readiness.')
    problems.extend(app.git_issues())
    update('Finalizing preflight',100,100,'Preflight report assembled.')
    report={'ready':not problems and not preparation,'prepared':not problems and bool(preparation),
            'preparation_only':bool(preparation),'selection':selection,'issues':problems,'plan':public_plan(plan),'gpu':gpu,
            'folder':folder_info,'inventory_warning':inventory_error,
            'note':'Preparation checks cannot certify a future allocation, driver, or remote installation.' if preparation else ('Live preflight blocked; resolve the listed issues.' if problems else 'Live preflight passed; model readiness is checked after each load.')}
    return report,plan
