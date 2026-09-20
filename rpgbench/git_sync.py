"""Conservative Git transport. No force pushes, resets, rebases or broad staging."""
from __future__ import annotations
import os
import re
import subprocess
import time
from pathlib import Path


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env=dict(os.environ,GIT_TERMINAL_PROMPT='0')
    p=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,env=env,timeout=120)
    if check and p.returncode:
        raise RuntimeError(f"Git {args[0]} failed: {p.stderr.strip()}")
    return p


def sync_source(root: Path) -> str:
    if git(root,'status','--porcelain').stdout.strip():
        raise RuntimeError('Source checkout is dirty. Commit your changes; no automatic stash/reset is performed.')
    git(root,'pull','--ff-only')
    return git(root,'rev-parse','HEAD').stdout.strip()


class ResultPublisher:
    def __init__(self, source: Path, worker_id: str, interval: float = 180):
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}',worker_id):
            raise ValueError('worker_id must be a short letters/digits/dashes identifier')
        self.source=source.resolve()
        self.branch='results/'+worker_id
        self.path=self.source/'.worker_results'/worker_id
        self.prefix='results/'+worker_id
        self.interval=interval
        self.last=0.0
        self.errors=[]
        git(self.source,'fetch','origin')
        if self.path.exists():
            if git(self.path,'branch','--show-current').stdout.strip()!=self.branch:
                raise RuntimeError('Existing results worktree has wrong branch')
        else:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            local=git(self.source,'show-ref','--verify','--quiet','refs/heads/'+self.branch,check=False).returncode==0
            remote=git(self.source,'show-ref','--verify','--quiet','refs/remotes/origin/'+self.branch,check=False).returncode==0
            if local:
                git(self.source,'worktree','add',str(self.path),self.branch)
            elif remote:
                git(self.source,'worktree','add','-b',self.branch,str(self.path),'origin/'+self.branch)
            else:
                git(self.source,'worktree','add','-b',self.branch,str(self.path),'HEAD')
        # Recover staged/unstaged local results before pulling; never discard them.
        self.flush(force=True)
        remote=git(self.source,'show-ref','--verify','--quiet','refs/remotes/origin/'+self.branch,check=False).returncode==0
        if remote:
            git(self.path,'pull','--ff-only','origin',self.branch)
        self.output=self.path/self.prefix
        self.output.mkdir(parents=True,exist_ok=True)

    def flush(self, force: bool = False) -> bool:
        if not force and time.monotonic()-self.last<self.interval:
            return True
        self.last=time.monotonic()
        try:
            staged=git(self.path,'diff','--cached','--name-only').stdout.splitlines()
            if any(not p.startswith(self.prefix+'/') for p in staged):
                raise RuntimeError('Unrelated staged files in results worktree; refusing to commit')
            directory=self.path/self.prefix
            if directory.exists():
                # This directory contains only harness-created synthetic JSON results.
                git(self.path,'add','-f','--',self.prefix)
            changed=git(self.path,'diff','--cached','--quiet',check=False).returncode
            if changed not in (0,1):
                raise RuntimeError('Cannot inspect Git index')
            if changed:
                git(self.path,'commit','-m','results: checkpoint '+self.branch)
            git(self.path,'push','-u','origin',self.branch)
            return True
        except (RuntimeError,OSError,subprocess.SubprocessError) as exc:
            self.errors.append(str(exc))
            print('RESULT PUBLISH WARNING:',exc,flush=True)
            return False
