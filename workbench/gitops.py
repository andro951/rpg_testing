"""Conservative Git transport. Never reset, stash, force-push, or stage arbitrary files."""
from __future__ import annotations
import os
import shutil
import subprocess
from pathlib import Path
from .domain import safe_id


def git(root, *args):
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    result=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,
        encoding='utf-8',errors='replace',timeout=120,env=dict(os.environ,GIT_TERMINAL_PROMPT='0'),**flags)
    if result.returncode:raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def inspect(root):
    git(root,'rev-parse','--show-toplevel')
    dirty=git(root,'status','--porcelain')
    return {'dirty':dirty,'commit':git(root,'rev-parse','HEAD'),'origin':git(root,'remote','get-url','origin')}


def pull(root):
    # A dirty worktree is not inherently unsafe: Git can fast-forward while
    # preserving local edits when incoming changes do not overlap them. If an
    # incoming change would overwrite a local edit (or the branch cannot
    # fast-forward), git pull --ff-only aborts before discarding local work and
    # git() surfaces that error to the Workbench.
    before=git(root,'rev-parse','HEAD')
    git(root,'pull','--ff-only')
    return git(root,'rev-parse','HEAD')!=before


def save_configuration(root):
    staged=git(root,'diff','--cached','--name-only').splitlines()
    allowed=lambda p:p.startswith('test_specs/') and p.endswith('.json') and len(Path(p).parts)==2
    if any(not allowed(p) for p in staged):raise RuntimeError('Unrelated files are staged; refusing to commit them.')
    files=git(root,'ls-files','--modified','--others','--exclude-standard').splitlines()
    files=[p for p in files if allowed(p)]
    if not files:return
    git(root,'add','--',*files)
    git(root,'-c','user.name=RPG Workbench','-c','user.email=workbench@localhost','commit','-m','config: save test definitions')


class Publisher:
    def __init__(self,root,data,worker):
        self.root,self.data=Path(root),Path(data);self.worker=safe_id(worker)
        self.checkout=self.data/'publish';self.branch='results/'+self.worker
    def prepare(self):
        if (self.checkout/'.git').exists():return
        git(self.root,'fetch','origin')
        remotes=git(self.root,'branch','-r','--list','origin/'+self.branch)
        locals=git(self.root,'branch','--list',self.branch)
        if locals:git(self.root,'worktree','add',str(self.checkout),self.branch)
        elif remotes:git(self.root,'worktree','add','-b',self.branch,str(self.checkout),'origin/'+self.branch)
        else:git(self.root,'worktree','add','-b',self.branch,str(self.checkout),'HEAD')
    def flush(self):
        self.prepare()
        destination=self.checkout/'workbench_results'/self.worker
        for folder in ('results','logs'):
            source=self.data/folder;target=destination/folder
            target.mkdir(parents=True,exist_ok=True)
            keep=set()
            for file in source.rglob('*'):
                if not file.is_file() or file.is_symlink() or file.name.startswith('.'):continue
                relative=file.relative_to(source);keep.add(relative)
                output=target/relative;output.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(file,output)
            for old in target.rglob('*'):
                if old.is_file() and old.relative_to(target) not in keep:old.unlink()
        staged=git(self.checkout,'diff','--cached','--name-only').splitlines()
        scope='workbench_results/'+self.worker+'/'
        if any(not p.startswith(scope) for p in staged):raise RuntimeError('Unrelated staged files in result worktree')
        git(self.checkout,'add','-A','--',scope)
        if git(self.checkout,'diff','--cached','--name-only'):
            git(self.checkout,'-c','user.name=RPG Workbench','-c','user.email=workbench@localhost','commit','-m','results: checkpoint '+self.worker)
        git(self.checkout,'push','origin','HEAD:refs/heads/'+self.branch)
