"""Direct, resumable GGUF downloads into an explicitly selected model directory."""
from __future__ import annotations
import hashlib
import os
import re
import shutil
import urllib.request
from pathlib import Path
from urllib.parse import quote
from .hub import SecureRedirect, safe_repo, safe_remote_file
from .inventory import gguf_metadata
from .workflows import Cancelled

HTTPSOnly=SecureRedirect


def contained_destination(root,repo,revision):
    root=Path(root).expanduser()
    if not root.is_absolute() or not root.is_dir():raise ValueError('Select an existing absolute models folder first')
    folder=root/safe_repo(repo)/(revision[:12] if re.fullmatch(r'[0-9a-f]{40,64}',revision) else 'main')
    if not folder.resolve().is_relative_to(root.resolve()):raise ValueError('Model destination escapes the selected folder')
    return folder


def download_model(model,root,cancel,log=lambda *a:None,opener=None,token=''):
    repo=safe_repo(model.get('repo_id',''));revision=model.get('revision','main')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',revision):raise ValueError('Unsafe revision')
    opener=opener or urllib.request.build_opener(SecureRedirect()).open
    dest=contained_destination(root,repo,revision);dest.mkdir(parents=True,exist_ok=True)
    paths=[]
    for name in model['files']:
        if Path(name).name!=name or '/' in name or '\\' in name or ':' in name or not name.endswith('.gguf'):raise ValueError('Unsafe model filename')
        if cancel.is_set():raise Cancelled('Download cancelled')
        remote=safe_remote_file(model.get('remote_files',{}).get(name,name))
        final=dest/name;temporary=dest/(name+'.partial')
        if final.is_symlink() or temporary.is_symlink():raise ValueError('Refusing a symlink download target')
        expected=model.get('sha256',{}).get(name)
        if final.exists():
            gguf_metadata(final)
            if expected and hash_file(final)!=expected:raise ValueError('Existing GGUF hash differs; it was not overwritten')
            paths.append(str(final));log('download','Already installed: '+name);continue
        offset=temporary.stat().st_size if temporary.exists() else 0
        known_size=model.get('file_sizes',{}).get(name)
        if offset and known_size==offset:
            gguf_metadata(temporary)
            if not expected or hash_file(temporary)==expected:
                os.replace(temporary,final);paths.append(str(final));continue
            raise ValueError('The complete partial file has the wrong hash; remove it before retrying')
        headers={'User-Agent':'RPG-Testing-Workbench'}
        if token:headers['Authorization']='Bearer '+token
        if offset:headers['Range']='bytes='+str(offset)+'-'
        url='https://huggingface.co/'+repo+'/resolve/'+quote(revision,safe='')+'/'+quote(remote,safe='/')
        with opener(urllib.request.Request(url,headers=headers),timeout=60) as response:
            status=getattr(response,'status',200)
            mode='wb';total=int(response.headers.get('Content-Length') or 0)
            if status==206:
                match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                if not match or int(match[1])!=offset or int(match[2])+1!=int(match[3]):raise ValueError('Invalid resume response')
                total=int(match[3]);mode='ab'
            elif status==200:offset=0
            else:raise ValueError('Unexpected download status')
            if total and shutil.disk_usage(dest).free<total-offset+64*1024**2:raise ValueError('Insufficient free space in selected model folder')
            count=offset;last=count
            with temporary.open(mode) as f:
                while True:
                    if cancel.is_set():raise Cancelled('Download paused; partial bytes stay in the selected model folder')
                    block=response.read(1024**2)
                    if not block:break
                    f.write(block);count+=len(block)
                    if count-last>=64*1024**2:log('download',f'{name}: {count/2**30:.2f} / {total/2**30:.2f} GiB');last=count
                f.flush();os.fsync(f.fileno())
        if total and count!=total:raise ValueError('Incomplete download; resume with the same selection')
        actual=hash_file(temporary)
        if expected and actual!=expected:
            invalid=temporary.with_suffix('.failed-'+actual[:8]);os.replace(temporary,invalid)
            raise ValueError('SHA-256 verification failed; invalid bytes quarantined beside the model, not installed')
        gguf_metadata(temporary)
        if final.exists():raise ValueError('Destination appeared during download; it was not overwritten')
        os.replace(temporary,final);paths.append(str(final));log('download','Installed '+name+' SHA-256 '+actual)
    return paths


def hash_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
    return h.hexdigest()
