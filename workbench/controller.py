"""Controller state, explicit actions and GPU-local execution. Browser-neutral."""
from __future__ import annotations
import copy
import hashlib
import functools
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from datetime import datetime,timezone
from pathlib import Path
from .domain import ResultStore, TIERS, canonical, digest, read_json, safe_id, write_json, validate_test
from .inventory import command, executable, file_hashes, scan_models
from .planning import validate_catalog
from . import preflight
from .workflows import execute, Cancelled
from .backends import DemoBackend
from .native import NativeBackend
from .model_manager import ModelManager


def now():return datetime.now(timezone.utc).isoformat()


def exclusive_edit(method):
    @functools.wraps(method)
    def wrapped(self,*args,**kwargs):
        if not self.operation.acquire(blocking=False):raise RuntimeError('An operation is active. Wait or stop it first.')
        try:return method(self,*args,**kwargs)
        finally:self.operation.release()
    return wrapped


class Controller(ModelManager):
    def __init__(self,root:Path,demo=False):
        self.root=Path(root).resolve();self.demo=demo
        self.data=self.root/'.local'/('demo' if demo else 'workbench');self.data.mkdir(parents=True,exist_ok=True)
        self.settings_path=self.data/'settings.json'
        defaults={'backend':'llamacpp','model_root':'','confirmed_empty_folder':'','llama_path':'',
                  'hf_token':'','sync_source':not demo,'publish_results':False,'remote_enabled':False,'models_folder_version':1}
        saved=read_json(self.settings_path) if self.settings_path.exists() else {}
        # Explicit consent for the new folder policy: no migration from LM Studio or guessed defaults.
        if saved.get('models_folder_version')!=1:saved.pop('model_root',None);saved.pop('confirmed_empty_folder',None)
        self.settings={**defaults,**{k:v for k,v in saved.items() if k in defaults}}
        self.settings['backend']='llamacpp'
        self.settings['runtime_cache']=str(self.root/'.local/runtime-cache')
        self.hub_results=[];self.hub_detail=None;self.runtime_options=[];self.folder_scanned=False
        self.run_total=0;self.run_processed=0;self.skipped_models=[];self.load_attempts=[]
        self.monitor=None;self.last_telemetry=None;self.timing_active=False;self.run_provenance={}
        self.store=ResultStore(self.data/'results');self.registry_path=self.data/'artifacts.json'
        self.registry=read_json(self.registry_path) if self.registry_path.exists() else {}
        self.last_models=[];self.report=None;self.plan=None;self.state='idle';self.message='Run preflight to inspect pending work.'
        self.lock=threading.RLock();self.operation=threading.Lock();self.thread=None
        self.cancel_event=threading.Event();self.resume_event=threading.Event();self.resume_event.set()
        self.pause_requested=False;self.stop_after_model=False;self.backend=None
        self.logs=[];self.pending_logs=[];self.completed_now=0;self.session_errors=0;self.current=None;self.restart_required=False
        self.started=None;self.finished=None;self.publisher=None;self.last_publish=0;self.version_cache=None
        self.selftest_digest=None;self.verified_fingerprints={};self.on_shutdown=None;self.remote_info=None
        for name in ('results','logs'):(self.data/name).mkdir(exist_ok=True)
        self.log('startup','Workbench started'+(' in SIMULATED DEMO mode' if demo else ''))
    def log(self,category,message):
        text=str(message)
        for secret in (self.settings.get('hf_token'),self.settings.get('model_api_token')):
            if secret:text=text.replace(secret,'[REDACTED]')
        entry={'time':now(),'category':category,'message':text}
        with self.lock:
            self.logs.append(entry);self.pending_logs.append(entry)
            if len(self.logs)>2000:self.logs=self.logs[-2000:]
    def flush_logs(self):
        if self.timing_active:raise RuntimeError('Logs are buffered until the timed workflow finishes')
        with self.lock:items=list(self.pending_logs)
        if items:
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
            write_json(self.data/'logs'/(stamp+'.json'),items)
            with self.lock:del self.pending_logs[:len(items)]
    def catalog(self):
        if self.demo:return [{'id':'demo-2b','base_model':'SIMULATED','files':['demo.gguf'],'quantization':'SIMULATED','required_vram_gb':8,'sha256':{'demo.gguf':'a'*64}}]
        models=read_json(self.root/'models.json');validate_catalog(models);return models
    def demo_models(self):
        return [{'id':'demo-2b','name':'Simulated 2B fixture model','files':['demo.gguf'],'paths':[],
                 'size_bytes':2*1024**3,'quantization':'SIMULATED','required_vram_gb':8,'recommended_vram_gb':8,
                 'catalogued':True,'complete':True,'missing_shards':[],'errors':[],
                 'metadata':{'general.name':'SIMULATED','demo.context_length':65536},'catalog':self.catalog()[0]}]
    def folder_info(self):
        if self.demo:return {'path':'SIMULATED: no weights used','source':'demo','issue':None}
        path=self.settings.get('model_root','')
        return {'path':path or None,'source':'Explicitly chosen models folder' if path else None,
                'issue':None if path else 'Choose a models folder. There is no automatic default.'}
    def backend_version(self):
        if self.demo:return 'demo-native-v3'
        if self.version_cache:return self.version_cache
        from .native import diagnostic_command
        exe=executable('llama-server',self.settings.get('llama_path',''))
        try:version=diagnostic_command([exe,'--version']) if exe else 'unavailable'
        except Exception as exc:version='unavailable: '+str(exc)
        if not version.startswith('unavailable'):self.version_cache=version
        return version
    def fingerprint(self,item):
        if self.demo:return {'demo.gguf':'a'*64}
        signature=[(str(Path(p).resolve()),Path(p).stat().st_size,Path(p).stat().st_mtime_ns) for p in item['paths']]
        key=digest(signature)
        if key in self.verified_fingerprints:return self.verified_fingerprints[key]
        hashes=file_hashes(item['paths']);self.verified_fingerprints[key]=hashes
        self.registry[item['id']]={'sha256':hashes,'signature':signature,'verified_at':now()}
        write_json(self.registry_path,self.registry)
        return hashes
    def with_known_pins(self,models):
        effective=copy.deepcopy(models)
        for m in effective:
            if m['id'] in self.registry:m['sha256']=self.registry[m['id']]['sha256']
            elif not m.get('sha256'):
                records=[r for r in self.store.all() if r.get('model_id')==m['id'] and r.get('artifact_hashes')]
                pins={canonical(r['artifact_hashes']) for r in records}
                if len(pins)==1:m['sha256']=json.loads(next(iter(pins)))
        return effective
    def git_issues(self):
        if self.demo or not self.settings['sync_source']:return []
        from .gitops import inspect
        try:
            info=inspect(self.root)
            if info['dirty']:return [preflight.issue('git_dirty','The source checkout has changes. Save catalog/test edits or resolve unrelated edits first.','Save and push catalog and test edits',{'type':'save_configuration'})]
        except Exception as exc:return [preflight.issue('git',str(exc)+' Use a Git clone for automatic sync, or disable Git in Worker setup.','Open Worker setup',{'type':'setup'})]
        return []
    def selftest(self):
        paths=sorted((self.root/'workbench').glob('*.py'))+sorted((self.root/'tests').glob('test*.py'))
        signature=digest({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
        if signature==self.selftest_digest:return
        self.log('preflight','Running harness unit/smoke tests (no real GPU inference).')
        flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
        result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests'],cwd=self.root,capture_output=True,text=True,timeout=180,**flags)
        self.log('selftest',result.stdout+result.stderr)
        if result.returncode:raise RuntimeError('Harness self-tests failed; inspect Logs. No benchmark was run.')
        self.selftest_digest=signature
    def check(self,preparation=None):
        self.message='Checking files, pending work, and backend readiness.'
        self.selftest()
        report,plan=preflight.build(self,preparation)
        self.report,self.plan=report,plan
        self.message='Preparation checks passed; actual GPU checks remain.' if report['prepared'] else 'Ready.' if report['ready'] else 'Preflight found issues. Use the individual action buttons.'
        self.log('preflight',self.message)
        self.flush_logs();return report
    def start(self,kind='preflight',payload=None):
        if not self.operation.acquire(blocking=False):raise RuntimeError('Another operation is active.')
        if self.restart_required:self.operation.release();raise RuntimeError('Source changed. Restart the workbench before continuing.')
        self.state='checking' if kind=='preflight' else 'fixing' if kind=='fix' else 'running'
        self.cancel_event.clear()
        def work():
            try:
                if kind=='preflight':self.check((payload or {}).get('preparation'))
                elif kind=='fix':self.fix(payload);self.check()
                elif kind=='run':self.run()
                elif kind=='hub_search':self.search_hub(payload)
                elif kind=='hub_inspect':self.inspect_hub(payload)
                elif kind=='hub_download':self.download_selected(payload)
                elif kind=='runtime_list':self.list_runtimes()
                elif kind=='runtime_install':self.install_runtime(payload)
                elif kind=='scan':self.scan_folder()
                else:raise ValueError('Unknown operation')
            except Cancelled:self.state='stopped';self.message='Stopped. Unfinished cases remain pending.'
            except Exception as exc:self.state='error';self.message=str(exc);self.log('error',exc)
            finally:
                if kind!='run' and self.state not in ('error','stopped'):self.state='idle'
                try:self.flush_logs()
                finally:self.operation.release()
        self.thread=threading.Thread(target=work,daemon=True);self.thread.start()
    def fix(self,action):
        if not self.report:raise ValueError('Run preflight first.')
        found=next((i for i in self.report['issues'] if i['id']==action.get('issue_id')),None)
        if not found or not found.get('action'):raise ValueError('No current repair action for this issue.')
        a=found['action'];kind=a['type'];self.log('action','User approved: '+found['label'])
        if kind=='create_folder':(self.data/a['name']).mkdir(parents=True,exist_ok=True)
        elif kind=='confirm_folder':self.settings['confirmed_empty_folder']=self.folder_info()['path'];self.save_settings()
        elif kind=='download_model':
            from .downloads import download_model
            model=next(m for m in self.catalog() if m['id']==a['model_id'])
            download_model(model,Path(self.folder_info()['path']),self.cancel_event,self.log,token=self.settings.get('hf_token',''))
        elif kind=='delete_corrupt':
            path=self.store.path(a['model_id'],a['case_id'])
            if path.exists():path.unlink()
            self.log('result_delete','User removed corrupt result '+a['case_id'])
        elif kind=='save_configuration':
            from .gitops import save_configuration,git
            save_configuration(self.root)
            git(self.root,'push','origin','HEAD')
        else:raise ValueError('This issue needs input in Models or Worker setup.')
    def save_settings(self):
        write_json(self.settings_path,self.settings)
        try:os.chmod(self.settings_path,0o600)
        except OSError:pass
    def scan_folder(self):
        if self.demo:self.last_models=self.demo_models();return
        path=self.settings.get('model_root','')
        if not path:raise ValueError('Choose your models folder first')
        self.last_models=scan_models(Path(path),self.catalog());self.folder_scanned=True
        self.message=f'Found {len(self.last_models)} model variants.'
    @exclusive_edit
    def configure(self,values):
        values=dict(values)
        allowed={'model_root','confirmed_empty_folder','llama_path','hf_token','sync_source','publish_results'}
        if set(values)-allowed:raise ValueError('Unknown setting; native llama.cpp is the only backend and test settings belong in tests')
        for key,val in values.items():
            if key in ('sync_source','publish_results'):
                if type(val)is not bool:raise ValueError('Expected boolean')
            elif not isinstance(val,str):raise ValueError('Expected text')
        if 'model_root' in values and values['model_root']:
            folder=Path(values['model_root']).expanduser()
            if not folder.is_absolute() or not folder.is_dir():raise ValueError('Choose an existing absolute models folder')
            values={**values,'model_root':str(folder.resolve())}
            if values['model_root']!=self.settings['model_root']:
                self.settings['confirmed_empty_folder']=''
        if values.get('confirmed_empty_folder'):
            confirmation=Path(values['confirmed_empty_folder']).expanduser().resolve()
            selected=values.get('model_root',self.settings['model_root'])
            if not selected or confirmation!=Path(selected).resolve():
                raise ValueError('Confirm the currently selected models folder, not a different path')
            values['confirmed_empty_folder']=str(confirmation)
        self.settings.update(values);self.save_settings();self.version_cache=None;self.report=None
        if 'model_root' in values and values['model_root']:self.scan_folder()
    @exclusive_edit
    def assign_model(self,mid,tier):
        if self.demo:raise ValueError('Demo model assignments are simulated and read-only.')
        if type(tier)is not int or tier not in TIERS:raise ValueError('Choose a supported VRAM tier.')
        item=next((m for m in self.last_models if m['id']==mid),None)
        if not item or not item['complete'] or item['errors']:raise ValueError('Rescan to find a complete, valid GGUF first.')
        models=self.catalog();existing=next((m for m in models if m['id']==mid),None)
        if existing is None:
            existing={'id':safe_id(mid),'base_model':item['name'],'files':item['files'],'quantization':item['quantization']};models.append(existing)
        existing.update(required_vram_gb=tier,vram_status='user_assigned_unverified',sha256=self.fingerprint(item))
        validate_catalog(models);write_json(self.root/'models.json',models);self.report=None
        self.log('catalog','Assigned '+mid+' to '+str(tier)+' GB; estimate is not measured VRAM.')
    def control(self,action):
        if action=='pause':self.resume_event.clear();self.pause_requested=True
        elif action=='resume':self.pause_requested=False;self.resume_event.set()
        elif action=='stop_after_model':self.stop_after_model=True;self.pause_requested=False;self.resume_event.set()
        elif action=='stop':
            self.cancel_event.set();self.resume_event.set()
            if self.backend:self.backend.cancel()
        else:raise ValueError('Unknown control')
    def run(self):
        if not self.demo and self.settings['sync_source']:
            from .gitops import pull
            if pull(self.root):
                self.restart_required=True;raise RuntimeError('Source changed before the run. Restart with the new version before starting tests.')
        report=self.check()
        if not report['ready']:self.state='idle';return
        self.state='running';self.completed_now=0;self.session_errors=0;self.started=now();self.finished=None
        self.pause_requested=False;self.stop_after_model=False;self.resume_event.set()
        from .scheduler import Session
        from .demo_native import DemoNative
        self.run_provenance={'backend_version':self.backend_version(),'python':platform.python_version(),
                             'source_commit':self.source_commit(),'workflow_code':self.workflow_code()}
        try:Session(self,report,self.plan,DemoNative if self.demo else NativeBackend).run()
        finally:self.finished=now();self.current=None
        self.state='finished' if not self.session_errors else 'finished_with_errors'
        self.message='Run finished. Full-GPU, skipped, and hybrid results are recorded separately.'
        self.report,self.plan=preflight.build(self)
    def source_commit(self):
        try:
            from .gitops import git
            return git(self.root,'rev-parse','HEAD')
        except Exception:return None
    def workflow_code(self):
        from .domain import code_fingerprint
        return code_fingerprint()
    def publish(self,force=False):
        if self.demo or not self.settings['publish_results'] or (not force and time.monotonic()-self.last_publish<180):return
        from .gitops import Publisher
        try:
            if not self.publisher:self.publisher=Publisher(self.root,self.data,'worker-'+digest(platform.node())[:10])
            self.publisher.flush();self.log('git','Pushed results checkpoint.')
        except Exception as exc:self.log('publish_error',str(exc)+' Results remain saved locally.')
        self.last_publish=time.monotonic()
    def snapshot(self):
        with self.lock:
            return {'state':self.state,'busy':self.operation.locked(),'message':self.message,'report':copy.deepcopy(self.report),
                    'models':copy.deepcopy(self.last_models),'current':copy.deepcopy(self.current),'completed_now':self.completed_now,
                    'session_errors':self.session_errors,'demo':self.demo,'run_total':self.run_total,'run_processed':self.run_processed,
                    'telemetry':self.monitor.snapshot() if self.monitor else self.last_telemetry,
                    'skipped_models':copy.deepcopy(self.skipped_models),'load_attempts':copy.deepcopy(self.load_attempts),
                    'hub_results':copy.deepcopy(self.hub_results),'hub_detail':copy.deepcopy(self.hub_detail),'runtime_options':copy.deepcopy(self.runtime_options),
                    'folder_scanned':self.folder_scanned,'restart_required':self.restart_required,
                    'settings':{k:v for k,v in self.settings.items() if not k.endswith(('token','secret'))},
                    'has_hf_token':bool(self.settings.get('hf_token')),'logs':copy.deepcopy(self.logs[-300:]),
                    'remote':self.remote_info,'started_at':self.started,'finished_at':self.finished}
    @exclusive_edit
    def result_records(self):
        records=[]
        for path in sorted(self.store.root.glob('*/*.json')):
            try:records.append(self.store.read(path))
            except (ValueError,KeyError,TypeError) as exc:
                records.append({'status':'corrupt','case_id':path.stem,'model_id':path.parent.name,'test_id':'Unknown','variant_id':'Unknown','error':str(exc)})
        return records
    @exclusive_edit
    def delete_result(self,mid,cid):
        path=self.store.path(mid,cid)
        if not path.exists():raise ValueError('Result not found')
        path.unlink();self.log('delete','User deleted '+mid+'/'+cid+'; this case is pending again.');self.report=None;self.flush_logs()
    @exclusive_edit
    def export(self):
        self.flush_logs();out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
            for folder in ('results','logs'):
                for p in sorted((self.data/folder).rglob('*')):
                    if p.is_file() and not p.is_symlink() and not p.name.startswith('.'):
                        z.write(p,p.relative_to(self.data).as_posix())
            from .analysis import summarize, csv_export
            valid=[];corrupt=[]
            for path in sorted(self.store.root.glob('*/*.json')):
                try:valid.append(self.store.read(path))
                except (ValueError,KeyError,TypeError) as exc:
                    corrupt.append({'file':path.relative_to(self.data).as_posix(),'error':str(exc)})
            summary=summarize(valid)
            summary['corrupt_files']=corrupt
            z.writestr('summary.json',json.dumps(summary,indent=2))
            z.writestr('summary.csv',csv_export(summary))
            z.writestr('ABOUT.txt','SIMULATED DEMO\n' if self.demo else 'GPU-local benchmark evidence. See each result for provenance and unavailable metrics.\n')
        return out.getvalue()
