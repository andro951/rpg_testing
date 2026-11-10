"""One isolated Slurm job per configured model; ambiguous submission never retries."""
import hashlib
import io
import json
import os
import shlex
import subprocess
import tarfile
from pathlib import Path, PurePosixPath
from workbench.domain import digest, read_json, write_json, safe_id, ResultStore


def evidence_root(path):
    """Use the Windows extended path namespace without changing storage location."""
    path=path.resolve()
    value=str(path)
    prefix='\\\\?\\'
    if os.name=='nt' and not value.startswith(prefix):
        return Path(prefix+'UNC\\'+value[2:] if value.startswith('\\\\') else prefix+value)
    return path


def ssh(worker, code, payload=None, binary=False):
    argv = worker['ssh']
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) for a in argv):
        raise ValueError('Unity ssh must be an explicit argument array')
    result = subprocess.run(argv + ['python3 -c ' + shlex.quote(code)],
        input=payload, capture_output=True, timeout=60,
        **({'creationflags': subprocess.CREATE_NO_WINDOW} if __import__('os').name == 'nt' else {}))
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-4000:])
    return result.stdout if binary else json.loads(result.stdout)


SUBMIT = r'''
import json,sys,subprocess,os,tarfile,io
from datetime import datetime
from pathlib import Path
packet=json.load(sys.stdin);root=Path(packet['root']);root.mkdir(parents=True,exist_ok=True)
manifest=root/'coverage-manifest.json'
if manifest.exists():
 if json.loads(manifest.read_text())!=packet['manifest']:raise RuntimeError('Frozen manifest conflict')
else:
 import base64
 with tarfile.open(fileobj=io.BytesIO(base64.b64decode(packet['archive'])),mode='r:gz') as tar:
  for m in tar.getmembers():
   p=Path(m.name)
   if p.is_absolute() or '..' in p.parts or m.issym() or m.islnk():raise RuntimeError('Unsafe source archive')
  tar.extractall(root/'repo')
 manifest.write_text(json.dumps(packet['manifest']))
receipt=root/'job.json';intent=root/'submission-intent.json'
if receipt.exists():print(receipt.read_text());sys.exit()
if intent.exists():
 # A lost sbatch acknowledgement is ambiguous. Reconcile by exact Slurm comment.
 found=[]
 for command in (['squeue','-h','-u',os.environ['USER'],'-o','%i|%k'],['sacct','-X','-n','-P','--starttime',datetime.fromtimestamp(intent.stat().st_mtime).strftime('%Y-%m-%dT%H:%M:%S'),'--format=JobIDRaw,Comment']):
  r=subprocess.run(command,capture_output=True,text=True)
  found.extend(line.split('|')[0].strip() for line in r.stdout.splitlines() if line.strip().endswith('|'+packet['token']))
 found=sorted(set(found))
 if len(found)!=1:raise RuntimeError('Submission acknowledgement missing; reconcile exact job ID before resume. No resubmission.')
 job=found[0]
else:
 with intent.open('x') as f:f.write(json.dumps({'token':packet['token']}));f.flush();os.fsync(f.fileno())
 r=subprocess.run(['sbatch','--parsable','--comment='+packet['token'],'--chdir='+str(root/'repo'),str(root/'repo/coverage.sbatch')],capture_output=True,text=True)
 if r.returncode:raise RuntimeError('sbatch failed; submission intent retained: '+r.stderr)
 job=r.stdout.strip().split(';')[0]
 if not job.isdigit():raise RuntimeError('Unrecognized Slurm acknowledgement; intent retained')
value={'job_id':job,'token':packet['token'],'root':str(root),'suite_digest':packet['manifest']['suite_digest'],'model_id':packet['manifest']['model_id'],'source_digest':packet['manifest'].get('source_digest')}
with receipt.open('x') as f:f.write(json.dumps(value));f.flush();os.fsync(f.fileno())
print(json.dumps(value))
'''

SNAPSHOT = r'''
import json,sys,subprocess
from pathlib import Path
p=json.load(sys.stdin);root=Path(p['root']);out={}
for name in ('job.json','repo/coverage-worker-status.json'):
 f=root/name
 if f.exists():out[name]=json.loads(f.read_text())
job=out.get('job.json',{}).get('job_id')
if job:
 out['queue']=subprocess.run(['squeue','-h','-j',job,'-o','%T'],capture_output=True,text=True).stdout.strip()
 out['accounting']=subprocess.run(['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ExitCode'],capture_output=True,text=True).stdout.strip()
print(json.dumps(out))
'''


def bundle(app, state, worker):
    import base64
    root = app.root
    required = ('model', 'model_path', 'runtime_path', 'python', 'constraint', 'qos', 'remote_base', 'ssh', 'inference_port')
    if any(k not in worker for k in required):
        raise ValueError('Unity worker lacks pinned model/runtime/allocation configuration')
    safe_id(worker['model_id'])
    if worker['model']['id'] != worker['model_id']:
        raise ValueError('Unity model identity mismatch')
    port = worker['inference_port']
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Invalid per-model inference port')
    if len({w['inference_port'] for w in state['workers'] if w['kind']=='unity'}) != sum(w['kind']=='unity' for w in state['workers']):
        raise ValueError('Unity jobs need unique inference ports')
    settings = {k:v for k,v in app.settings.items() if k in ('perchance_epoch','backend')}
    settings.update(model_root=str(PurePosixPath(worker['model_path']).parent), models_folder_version=1,
                    llama_path=worker['runtime_path'], inference_port=port,
                    sync_source=False, publish_results=False, remote_enabled=False)
    manifest = {'id': state['id'], 'suite_digest': state['suite_digest'], 'scope': state['scope'],
                'model_id': worker['model_id'], 'seed_results_roots': worker.get('seed_results_roots', [])}
    manifest['source_files']={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ('workbench','optimization','test_builder') for p in (root/folder).rglob('*')
        if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts}
    manifest['source_digest']=digest(manifest['source_files'])
    manifest['settings_digest']=digest(settings)
    manifest['model_digest']=digest([worker['model']])
    for name in ('constraint','qos'):
        if not __import__('re').fullmatch(r'[A-Za-z0-9_&.-]+',worker[name]):
            raise ValueError('Invalid Slurm '+name)
    script = '\n'.join(['#!/bin/bash', '#SBATCH --job-name=rpg-coverage', '#SBATCH --partition=gpu',
        '#SBATCH --gpus=1', '#SBATCH --cpus-per-task=4', '#SBATCH --mem=32G', '#SBATCH --time=04:00:00',
        '#SBATCH --constraint='+worker['constraint'], '#SBATCH --qos='+worker['qos'],
        'set -euo pipefail', ': "${SLURM_JOB_ID:?Submit through Slurm}"',
        shlex.quote(worker['python'])+' -B -m workbench.coverage_worker', ''])
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w:gz') as tar:
        for folder in ('workbench','optimization','test_builder','test_specs','evaluation','reporting','fixtures','prompts','docs','tools'):
            for path in sorted((root/folder).rglob('*')):
                if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts:
                    tar.add(path,arcname=path.relative_to(root).as_posix())
        def add(name,value):
            raw=value.encode();info=tarfile.TarInfo(name);info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
        add('models.json',json.dumps([worker['model']]))
        add('.local/workbench/settings.json',json.dumps(settings))
        add('coverage-manifest.json',json.dumps(manifest))
        add('coverage.sbatch',script)
    remote=worker['remote_base'].rstrip('/')+'/'+state['id']+'/'+worker['model_id']
    if not remote.startswith('/') or '..' in PurePosixPath(remote).parts:
        raise ValueError('Invalid remote coverage root')
    return {'root':remote,'token':'rpg-'+digest({'coverage':state['id'],'model':worker['model_id']})[:32],
            'manifest':manifest,'archive':base64.b64encode(output.getvalue()).decode()}


def advance(app, state, worker):
    if not worker.get('receipt'):
        packet=bundle(app,state,worker)
        # The remote exclusive intent is authoritative across a lost local acknowledgement.
        worker['receipt']=ssh(worker,SUBMIT,json.dumps(packet).encode())
    receipt=worker['receipt']
    if receipt['suite_digest']!=state['suite_digest'] or receipt['model_id']!=worker['model_id']:
        raise ValueError('Unity receipt differs from frozen coverage')
    snapshot=ssh(worker,SNAPSHOT,json.dumps(receipt).encode());worker['snapshot']=snapshot
    result=snapshot.get('repo/coverage-worker-status.json',{})
    if result.get('status')=='completed':
        if result.get('suite_digest')!=state['suite_digest'] or result.get('model_id')!=worker['model_id'] or result.get('source_digest')!=receipt.get('source_digest'):
            raise ValueError('Unity result manifest mismatch')
        # Collect raw checksummed records before calling coverage complete.
        code="""import sys,json,tarfile,io;from pathlib import Path
p=json.load(sys.stdin);root=Path(p['root'])/'repo';out=io.BytesIO()
with tarfile.open(fileobj=out,mode='w:gz') as t:
 for f in sorted((root/'results').glob('*/*.json')):t.add(f,arcname=f.relative_to(root).as_posix())
sys.stdout.buffer.write(out.getvalue())"""
        raw=ssh(worker,code,json.dumps(receipt).encode(),binary=True)
        from .coverage import directory
        dest=evidence_root(directory(app.root,state['id'])/worker['id']);dest.mkdir(exist_ok=True)
        archive=dest/'evidence.tar.gz';archive.write_bytes(raw)
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:
            for member in tar.getmembers():
                p=Path(member.name)
                if p.is_absolute() or '..' in p.parts or member.issym() or member.islnk() or not (dest/p).resolve().is_relative_to(dest.resolve()):raise ValueError('Unsafe evidence archive')
            tar.extractall(dest)
        records=ResultStore(dest/'results').all()
        returned={r['case_id']:r for r in records}
        expected=result.get('rows',[])
        if len(expected)!=1 or expected[0]['model_id']!=worker['model_id'] or expected[0]['status']!='completed':
            raise ValueError('Unity returned incomplete model coverage')
        row=expected[0];evidence=row.get('evidence',[])
        if not evidence or len(evidence)!=row['required']:raise ValueError('Unity raw evidence manifest is incomplete')
        local_evidence=[]
        from .coverage import evidence_file
        for item in evidence:
            cid=PurePosixPath(item['path']).stem
            p=dest/'results'/worker['model_id']/(cid+'.json')
            if cid not in returned or returned[cid]['status']!='completed' or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:
                raise ValueError('Unity raw evidence differs from the completed manifest')
            local_evidence.append(evidence_file(p))
        worker.update(status='completed', rows=[{**row,'evidence':local_evidence}], result=result, archive_sha256=hashlib.sha256(raw).hexdigest())
    elif snapshot.get('queue'):
        worker['status']='running' if 'RUNNING' in snapshot['queue'] else 'queued'
    else:
        worker.update(status='blocked',error='Unity job terminal or missing; no automatic resubmission',result=result)
