"""Bootstrap: pull BEFORE importing the runner; then run tests and pinned worker code."""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--no-sync',action='store_true')
    p.add_argument('--skip-self-tests',action='store_true')
    args,rest=p.parse_known_args()
    root=Path(__file__).resolve().parent
    local=root/'.local';local.mkdir(exist_ok=True)
    lock=local/'worker.lock'
    try:
        fd=os.open(lock,os.O_WRONLY|os.O_CREAT|os.O_EXCL)
    except FileExistsError:
        p.error('Worker lock exists. Verify no runner is alive before manually removing .local/worker.lock')
    try:
        with os.fdopen(fd,'w') as f:json.dump({'pid':os.getpid()},f)
        if not args.no_sync:
            env=dict(os.environ,GIT_TERMINAL_PROMPT='0')
            status=subprocess.run(['git','status','--porcelain'],cwd=root,env=env,capture_output=True,text=True,check=True).stdout.strip()
            if status:raise RuntimeError('Dirty source checkout. Commit changes before auto-pull; nothing was reset.')
            subprocess.run(['git','pull','--ff-only'],cwd=root,env=env,check=True)
        if not args.skip_self_tests:
            subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root,check=True)
        # New interpreter imports the freshly pulled code. No hot-reload mid experiment.
        return subprocess.call([sys.executable,'-m','rpgbench.runner',*rest],cwd=root)
    finally:
        lock.unlink(missing_ok=True)

if __name__=='__main__':raise SystemExit(main())
