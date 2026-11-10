"""Frozen single-model Slurm coverage entry point; no generation of OPRO prompts."""
from pathlib import Path
import json
import os
import shutil
import signal
import traceback
import hashlib
from .domain import read_json, write_json, digest, ResultStore
from .locking import HostLock
from .controller import Controller
from optimization.coverage import scope, summarize


def run(root):
    if not os.environ.get('SLURM_JOB_ID'):
        raise RuntimeError('Coverage inference requires an allocated Slurm job')
    manifest=read_json(root/'coverage-manifest.json')
    with HostLock(root/'.local/workbench/host.lock'):
        for name,expected in manifest['source_files'].items():
            p=(root/name).resolve()
            if not p.is_relative_to(root.resolve()) or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
                raise ValueError('Frozen worker source changed: '+name)
        if digest(read_json(root/'.local/workbench/settings.json'))!=manifest['settings_digest'] or digest(read_json(root/'models.json'))!=manifest['model_digest']:
            raise ValueError('Frozen worker model/settings configuration changed')
        if digest(scope(root))!=manifest['suite_digest']:
            raise ValueError('Frozen worker suite differs from requested coverage')
        app=Controller(root)
        for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *args:app.control('stop'))
        for old_root in manifest.get('seed_results_roots',[]):
            store=ResultStore(Path(old_root))
            for p in store.root.glob(manifest['model_id']+'/*.json'):
                record=store.read(p);dest=app.store.path(record['model_id'],record['case_id'])
                if dest.exists():
                    if dest.read_bytes()!=p.read_bytes():raise ValueError('Conflicting retained result')
                else:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        app.run(selection={'model_id':manifest['model_id']})
        rows,report,plan=summarize(app,[manifest['model_id']])
        completed=rows and all(r['status']=='completed' for r in rows) and not app.session_errors
        result={'status':'completed' if completed else 'partial','model_id':manifest['model_id'],
                'suite_digest':manifest['suite_digest'],'job_id':os.environ['SLURM_JOB_ID'],
                'source_digest':manifest['source_digest'],
                'rows':rows,'issues':report.get('issues',[]),'errors':app.session_errors}
        write_json(root/'coverage-worker-status.json',result)
        return 0 if completed else 2


if __name__=='__main__':
    root=Path.cwd()
    try:raise SystemExit(run(root))
    except Exception as exc:
        write_json(root/'coverage-worker-status.json',{'status':'blocked','error':str(exc),'traceback':traceback.format_exc()})
        raise
