"""GPU-local runner. Invoke run_worker.py for pre-run Git sync and source pinning."""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .backends import BackendError, ManagedBackend, MockBackend, artifact_info, detect_gpu
from .core import PIPELINES, ResultStore, atomic_write, canonical, digest, pipeline_messages, read_json, score, validate_inputs


def code_digest(root: Path) -> str:
    files=sorted((root/'rpgbench').glob('*.py'))+[root/'run_worker.py',root/'requirements.txt']
    return digest({str(p.relative_to(root)):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in files if p.exists()})


def environment(worker: dict, gpu: dict) -> dict:
    cpu=platform.processor()
    if not cpu and Path('/proc/cpuinfo').exists():
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                cpu=line.split(':',1)[1].strip();break
    return {'gpu_name':gpu['name'],'gpu_total_gib':gpu['total_gib'],'driver':gpu['driver'],
            'cpu':cpu or 'unknown','logical_cpus':os.cpu_count(),'os':platform.platform(),
            'python':platform.python_version(),'jsonschema':importlib.metadata.version('jsonschema'),
            'backend':worker['backend'],'backend_version':worker['backend_version'],
            'gpu_offload':worker.get('gpu_offload','max'),'extra_body':worker.get('extra_body',{}),
            'measurement_mode':'simulated' if worker['backend']=='mock' else 'local_http'}


def make_case_id(model: dict, artifacts: dict, fixture: dict, pipeline: str, exp: dict,
                 seed: int, repetition: int, env: dict, code_hash: str) -> str:
    return digest({'model':{'id':model['id'],'base_model':model['base_model'],'quantization':model['quantization']},
                   'artifacts':artifacts,'fixture':fixture,'pipeline':pipeline,
                   'experiment':{k:v for k,v in exp.items() if k not in {'pipelines','seeds','repetitions','max_attempts'}},
                   'seed':seed,'repetition':repetition,'environment':env,'code_digest':code_hash})


class PipelineError(BackendError):
    def __init__(self, message, calls, elapsed):
        super().__init__(message)
        self.partial_calls = calls
        self.elapsed = elapsed


def execute_case(backend, fixture: dict, pipeline: str, exp: dict, seed: int) -> dict:
    start=time.perf_counter();calls=[]
    staged,representation=PIPELINES[pipeline]
    analysis=None
    for stage in (['analysis','patch'] if staged else ['patch']):
        messages=pipeline_messages(fixture,pipeline,analysis)
        try:
            result=backend.generate(messages,exp,seed)
        except BackendError as exc:
            raise PipelineError(str(exc),calls,time.perf_counter()-start) from exc
        calls.append({'stage':stage,'messages':messages,**result})
        if result['finish_reason']!='stop':
            return {'calls':calls,'pipeline_seconds':time.perf_counter()-start,
                    'score':{'valid':False,'exact_match':False,'error':'Incomplete/non-stop generation: '+str(result['finish_reason'])}}
        if stage=='analysis':analysis=result['text']
    elapsed=time.perf_counter()-start
    scoring_start=time.perf_counter()
    scored=score(fixture,calls[-1]['text'],representation)
    return {'calls':calls,'pipeline_seconds':elapsed,'scoring_seconds':time.perf_counter()-scoring_start,'score':scored}


def run_suite(root: Path, models: list, exp: dict, fixtures: list, worker: dict, output: Path,
              gpu: dict, backend, publisher=None) -> dict:
    validate_inputs(models,exp,fixtures)
    if worker['backend']!='mock' and ('REPLACE' in worker.get('backend_version','') or not worker.get('backend_version')):
        raise ValueError('Record the installed backend AND engine runtime build in backend_version first')
    env=environment(worker,gpu);hash_code=code_digest(root)
    store=ResultStore(output/'cases')
    session_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
    try:
        commit=subprocess.run(['git','-C',str(root),'rev-parse','HEAD'],capture_output=True,text=True,timeout=10).stdout.strip() or None
    except (OSError,subprocess.SubprocessError):commit=None
    summary={'session_id':session_id,'simulated':worker['backend']=='mock','completed_now':0,'already_complete':0,
             'errors':0,'exhausted':0,'models_loaded':0,'skipped_models':[], 'environment':env,
             'source_commit':commit,'code_digest':hash_code,'gpu_provenance':gpu,
             'peak_gpu_memory_gib':None,'peak_gpu_memory_note':'Not sampled in v0.1; not zero',
             'full_gpu_residency_verified':False}
    for model in models:
        # A nominal 80 GiB device may report slightly less usable capacity with ECC/reservations.
        if gpu['total_gib'] < model['required_vram_gb']*0.98:
            summary['skipped_models'].append({'model':model['id'],'reason':'below configured required_vram_gb budget'})
            continue
        try:
            if worker['backend']=='mock':
                artifacts,binding={'simulated':True},{}
            else:
                artifacts,binding=artifact_info(model,worker)
        except BackendError as exc:
            summary['skipped_models'].append({'model':model['id'],'reason':str(exc)})
            continue
        jobs=[]
        for pipeline in exp['pipelines']:
            for fixture in fixtures:
                for seed in exp['seeds']:
                    for repetition in range(exp['repetitions']):
                        cid=make_case_id(model,artifacts,fixture,pipeline,exp,seed,repetition,env,hash_code)
                        if store.done(cid):summary['already_complete']+=1
                        elif len(store.records(cid))>=exp['max_attempts']:summary['exhausted']+=1
                        else:jobs.append((cid,fixture,pipeline,seed,repetition))
        if not jobs:continue
        print(f"Loading {model['id']}: {len(jobs)} pending cases",flush=True)
        try:
            backend.load(model,binding,exp);summary['models_loaded']+=1
            if exp.get('warmup',True):
                warm=dict(exp,max_output_tokens=4)
                backend.generate([{'role':'user','content':'Reply OK.'}],warm,0)
        except Exception as exc:
            try:backend.unload()
            except Exception:pass
            summary['skipped_models'].append({'model':model['id'],'reason':'load/warm-up failed: '+str(exc)})
            summary['errors']+=1
            continue
        try:
            for cid,fixture,pipeline,seed,repetition in jobs:
                metadata={'case_id':cid,'session_id':session_id,'fixture_id':fixture['id'],'fixture_digest':digest(fixture),
                          'model_id':model['id'],'pipeline':pipeline,'seed':seed,'repetition':repetition,
                          'experiment':exp,'artifacts':artifacts,'environment':env,'source_commit':commit,
                          'code_digest':hash_code,'load':backend.load_metadata,'simulated':summary['simulated']}
                while len(store.records(cid))<exp['max_attempts'] and not store.done(cid):
                    try:
                        outcome=execute_case(backend,fixture,pipeline,exp,seed)
                        store.save(dict(metadata,status='completed',**outcome))
                        summary['completed_now']+=1
                    except BackendError as exc:
                        store.save(dict(metadata,status='error',error=str(exc),
                                        calls=getattr(exc,'partial_calls',[]),
                                        pipeline_seconds=getattr(exc,'elapsed',None)))
                        summary['errors']+=1
                    print(f"  {fixture['id']} / {pipeline}: {'recorded' if store.done(cid) else 'infrastructure error'}",flush=True)
                    if publisher:publisher.flush()
        finally:
            backend.unload()
        atomic_write(output/'sessions'/(session_id+'.json'),summary)
        if publisher:publisher.flush()
    atomic_write(output/'sessions'/(session_id+'.json'),summary)
    if publisher:
        publisher.flush(force=True)
        if publisher.errors:summary['publication_warnings']=publisher.errors
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--worker',type=Path,default=Path('worker.local.json'))
    parser.add_argument('--models',type=Path,help='Local model catalog JSON (default: <root>/models.json)')
    parser.add_argument('--worker-id',default='desktop')
    parser.add_argument('--output',type=Path,default=Path('.local/results'))
    parser.add_argument('--mock',action='store_true')
    parser.add_argument('--publish',action='store_true')
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--vram-gb',type=float,default=8,help='Planning/mock only; never overrides real detection')
    parser.add_argument('--model',action='append')
    args=parser.parse_args(argv)
    root=args.root.resolve()
    models_path=args.models or root/'models.json'
    if not models_path.is_absolute():models_path=(root/models_path).resolve()
    if not models_path.is_file():parser.error('Local model catalog not found: '+str(models_path)+'. Configure models in Workbench or pass --models.')
    models=read_json(models_path);exp=read_json(root/'experiment.json')
    fixtures=[read_json(p) for p in sorted((root/'fixtures').glob('*.json'))]
    validate_inputs(models,exp,fixtures)
    if args.model:
        unknown=set(args.model)-{m['id'] for m in models}
        if unknown:parser.error('Unknown models: '+','.join(sorted(unknown)))
        models=[m for m in models if m['id'] in args.model]
    if args.plan:
        print(json.dumps([{'model':m['id'],'required_vram_gb':m['required_vram_gb'],
            'eligible_budget':args.vram_gb>=m['required_vram_gb']*0.98,'vram_status':m['vram_status']} for m in models],indent=2));return 0
    publisher=None
    if args.mock:
        if args.publish:parser.error('Do not publish simulated smoke results as experiment results')
        worker={'backend':'mock','backend_version':'mock-v1'}
        gpu={'name':'SIMULATED GPU','total_gib':args.vram_gb,'driver':'none','uuid':'mock'}
        backend=MockBackend()
    else:
        worker=read_json(args.worker);gpu=detect_gpu(worker)
        backend=ManagedBackend(worker,root/'.local/load_logs',gpu)
        if args.publish:
            from .git_sync import ResultPublisher
            publisher=ResultPublisher(root,args.worker_id,worker.get('publication_interval_seconds',180))
    output=publisher.output if publisher else args.output.resolve()
    summary=run_suite(root,models,exp,fixtures,worker,output,gpu,backend,publisher)
    print(json.dumps(summary,indent=2))
    if summary['errors'] or summary['exhausted'] or summary.get('publication_warnings'):return 2
    if not(summary['completed_now'] or summary['already_complete']):return 2
    return 0

if __name__=='__main__':
    raise SystemExit(main())
