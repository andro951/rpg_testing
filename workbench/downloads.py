"""Direct, resumable GGUF downloads into the explicitly chosen model folder."""
from __future__ import annotations
import hashlib
import os
import re
import shutil
import urllib.request
from pathlib import Path
from urllib.parse import quote
from .hub import SecureRedirect,safe_repo,safe_remote_file
from .inventory import gguf_metadata
from .workflows import Cancelled

HTTPSOnly=SecureRedirect

def hash_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
    return h.hexdigest()

def download_model(model,root,cancel,log=lambda *a:None,opener=None,token=''):
    root=Path(root).expanduser()
    if not root.is_absolute() or not root.is_dir():raise ValueError('Choose an existing absolute models folder')
    repo=safe_repo(model.get('repo_id',''));revision=model.get('revision','main')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',revision):raise ValueError('Unsafe model revision')
    opener=opener or urllib.request.build_opener(SecureRedirect()).open
    dest=root/repo
    if revision!='main':dest=dest/(revision[:12] if re.fullmatch(r'[0-9a-f]{40,64}',revision) else revision)
    if not dest.resolve().is_relative_to(root.resolve()):raise ValueError('Destination escapes chosen folder')
    dest.mkdir(parents=True,exist_ok=True);paths=[]
    for name in model['files']:
        if Path(name).name!=name or any(c in name for c in ('/','\\',':')) or not name.endswith('.gguf'):
            raise ValueError('Unsafe model filename')
        if cancel.is_set():raise Cancelled('Download cancelled')
        remote=safe_remote_file(model.get('remote_files',{}).get(name,name))
        final=dest/name;partial=dest/(name+'.partial')
        if final.is_symlink() or partial.is_symlink():raise ValueError('Refusing a symlink destination')
        expected=model.get('sha256',{}).get(name)
        if final.exists():
            gguf_metadata(final)
            if expected and hash_file(final)!=expected:raise ValueError('Existing model checksum mismatch; not overwritten')
            paths.append(str(final));continue
        offset=partial.stat().st_size if partial.exists() else 0
        size=model.get('file_sizes',{}).get(name)
        if offset and size==offset:
            gguf_metadata(partial)
            if expected and hash_file(partial)!=expected:raise ValueError('Completed partial file checksum mismatch')
            os.replace(partial,final);paths.append(str(final));continue
        headers={'User-Agent':'RPG-Testing-Workbench'}
        if token:headers['Authorization']='Bearer '+token
        if offset:headers['Range']='bytes='+str(offset)+'-'
        url='https://huggingface.co/'+repo+'/resolve/'+quote(revision,safe='')+'/'+quote(remote,safe='/')
        with opener(urllib.request.Request(url,headers=headers),timeout=60) as response:
            status=getattr(response,'status',200);mode='wb';total=int(response.headers.get('Content-Length') or 0)
            if status==206:
                m=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('Content-Range',''))
                if not m or int(m[1])!=offset or int(m[2])+1!=int(m[3]):raise ValueError('Invalid download resume range')
                total=int(m[3]);mode='ab'
            elif status==200:offset=0
            else:raise ValueError('Unexpected download response')
            if total and shutil.disk_usage(dest).free<total-offset+64*1024**2:raise ValueError('Not enough free space in the chosen models folder')
            count=offset;last=count
            with partial.open(mode) as f:
                while True:
                    if cancel.is_set():raise Cancelled('Download cancelled; partial bytes retained in the chosen folder')
                    block=response.read(1024**2)
                    if not block:break
                    f.write(block);count+=len(block)
                    if count-last>=64*1024**2:
                        log('download',f'{name}: {count/2**30:.2f}/{total/2**30:.2f} GiB');last=count
                f.flush();os.fsync(f.fileno())
        if total and count!=total:raise ValueError('Incomplete download; select the same model to resume')
        actual=hash_file(partial)
        if expected and actual!=expected:
            os.replace(partial,partial.with_suffix('.failed-'+actual[:8]))
            raise ValueError('SHA-256 mismatch; rejected bytes were not installed')
        gguf_metadata(partial)
        if final.exists():raise ValueError('Destination appeared during download; refusing to overwrite it')
        os.replace(partial,final);paths.append(str(final));log('download','Installed '+name+' SHA-256 '+actual)
    return paths
