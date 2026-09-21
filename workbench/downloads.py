"""Explicit, cancellable downloads of catalogued GGUFs. No arbitrary URL execution."""
from __future__ import annotations
import hashlib
import os
import re
import urllib.request
from pathlib import Path
from urllib.parse import quote,urlsplit
from .inventory import gguf_metadata
from .workflows import Cancelled

class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlsplit(newurl).scheme!='https':raise ValueError('Refusing an insecure download redirect')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def download_model(model,root,cancel,log=lambda *a:None,opener=None):
    repo=model.get('repo_id','')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('A valid publisher/model repository is required')
    for f in model['files']:
        if not f.endswith('.gguf') or '/' in f or '\\' in f:raise ValueError('Unsafe model filename')
    destination=Path(root)/repo;destination.mkdir(parents=True,exist_ok=True)
    opener=opener or urllib.request.build_opener(HTTPSOnly()).open
    for name in model['files']:
        if cancel.is_set():raise Cancelled('Download cancelled')
        final=destination/name;expected=model.get('sha256',{}).get(name)
        if final.exists():
            gguf_metadata(final)
            if expected:
                from .inventory import file_hashes
                if file_hashes([str(final)])[name]!=expected:raise ValueError('Existing file hash differs; inspect it before replacing: '+name)
            log('download','Already present: '+name);continue
        temporary=destination/(name+'.partial')
        url='https://huggingface.co/'+repo+'/resolve/'+quote(model.get('revision','main'),safe='')+'/'+quote(name,safe='')
        count=0;h=hashlib.sha256();last=0
        try:
            with opener(urllib.request.Request(url,headers={'User-Agent':'RPG-Testing-Workbench'}),timeout=60) as response, temporary.open('wb') as f:
                total=int(response.headers.get('Content-Length') or 0)
                while True:
                    if cancel.is_set():raise Cancelled('Download cancelled')
                    chunk=response.read(1024**2)
                    if not chunk:break
                    f.write(chunk);h.update(chunk);count+=len(chunk)
                    if count-last>=128*1024**2:log('download',name+': '+str(count//1024**2)+' MiB');last=count
                f.flush();os.fsync(f.fileno())
            if total and count!=total:raise ValueError('Download ended before the advertised size')
            if expected and h.hexdigest()!=expected:raise ValueError('Downloaded file failed its SHA-256 check')
            gguf_metadata(temporary)
            if final.exists():raise ValueError('A file appeared at the destination; refusing to overwrite it')
            os.replace(temporary,final);log('download','Finished '+name+' SHA-256 '+h.hexdigest())
        finally:
            if temporary.exists():temporary.unlink()
