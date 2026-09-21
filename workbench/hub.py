"""Metadata-only Hugging Face browser. No SDK model cache and no implicit downloads."""
from __future__ import annotations
import json
import re
import urllib.request
from pathlib import PurePosixPath
from urllib.parse import quote, urlencode, urlsplit
from .domain import digest


class SecureRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlsplit(newurl).scheme!='https':raise ValueError('Refusing a non-HTTPS redirect')
        redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
        if redirected and urlsplit(newurl).netloc!=urlsplit(req.full_url).netloc:
            redirected.remove_header('Authorization')
        return redirected


def safe_repo(repo):
    if not isinstance(repo,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*',repo):
        raise ValueError('Use a publisher/repository model ID')
    if any(p in ('.','..') for p in repo.split('/')):raise ValueError('Unsafe repository ID')
    return repo


def safe_remote_file(name):
    if not isinstance(name,str) or '\\' in name or ':' in name or name.startswith('/') or any(p in ('','..','.') for p in name.split('/')):
        raise ValueError('Unsafe repository filename')
    return name


class HubClient:
    def __init__(self,token='',opener=None):
        self.token=token;self.opener=opener or urllib.request.build_opener(SecureRedirect()).open
    def json(self,url):
        if urlsplit(url).netloc!='huggingface.co' or urlsplit(url).scheme!='https':raise ValueError('Not a Hugging Face metadata URL')
        headers={'User-Agent':'RPG-Testing-Workbench','Accept':'application/json'}
        if self.token:headers['Authorization']='Bearer '+self.token
        with self.opener(urllib.request.Request(url,headers=headers),timeout=30) as response:
            raw=response.read(16*1024**2+1)
            if len(raw)>16*1024**2:raise ValueError('Repository metadata exceeds the supported size')
            return json.loads(raw)
    def search(self,query):
        if not isinstance(query,str) or not 1<=len(query.strip())<=200:raise ValueError('Enter a model name or repository')
        params=urlencode({'search':query.strip(),'filter':'gguf','sort':'downloads','direction':-1,'limit':30,'full':'true'})
        data=self.json('https://huggingface.co/api/models?'+params)
        return [{'id':m['id'],'downloads':m.get('downloads'),'likes':m.get('likes'),'updated':m.get('lastModified'),
                 'gated':m.get('gated',False),'license':m.get('cardData',{}).get('license')} for m in data]
    def variants(self,repo,target_gb=8):
        safe_repo(repo)
        info=self.json('https://huggingface.co/api/models/'+repo+'?blobs=true')
        return group_variants(info,target_gb)


def group_variants(info,target_gb):
    repo=safe_repo(info['id']);revision=info.get('sha','')
    if not re.fullmatch(r'[0-9a-f]{40,64}',revision):raise ValueError('Hub did not supply an immutable repository revision')
    groups={}
    for entry in info.get('siblings',[]):
        name=entry.get('rfilename','')
        if not name.lower().endswith('.gguf') or 'mmproj' in name.lower():continue
        safe_remote_file(name)
        split=re.fullmatch(r'(.+)-(\d{5})-of-(\d{5})\.gguf',name,re.I)
        key=split[1] if split else name[:-5]
        groups.setdefault(key,[]).append(entry)
    out=[]
    for name,files in groups.items():
        files=sorted(files,key=lambda f:f['rfilename'])
        split=re.fullmatch(r'(.+)-(\d{5})-of-(\d{5})\.gguf',files[0]['rfilename'],re.I)
        complete=not split or [f['rfilename'] for f in files]==[f'{split[1]}-{i:05}-of-{int(split[3]):05}.gguf' for i in range(1,int(split[3])+1)]
        match=re.search(r'(IQ[1-8]_[A-Z0-9_]+|Q[2-8]_[A-Z0-9_]+|BF16|F16|F32)(?=$|[^A-Z0-9_])',name.upper())
        quant=match[1] if match else 'UNKNOWN'
        sizes=[f.get('size',f.get('lfs',{}).get('size')) for f in files]
        size=sum(sizes) if all(type(n)is int and n>0 for n in sizes) else None
        paths=[f['rfilename'] for f in files];basenames=[PurePosixPath(p).name for p in paths]
        if len(set(basenames))!=len(basenames):continue
        hashes={PurePosixPath(f['rfilename']).name:f.get('lfs',{}).get('sha256') for f in files}
        hashes=hashes if all(isinstance(h,str) and re.fullmatch(r'[0-9a-f]{64}',h) for h in hashes.values()) else {}
        item={'id':'hf-'+digest({'repo':repo,'revision':revision,'files':paths})[:20],
              'repo_id':repo,'revision':revision,'base_model':info.get('cardData',{}).get('base_model') or repo,
              'files':basenames,'remote_files':dict(zip(basenames,paths)),'quantization':quant,'size_bytes':size,
              'file_sizes':dict(zip(basenames,sizes)),'sha256':hashes,'complete':complete,'shards':len(files),
              'license':info.get('cardData',{}).get('license'),'gated':info.get('gated',False),
              'required_vram_gb':None,'vram_status':'unassigned'}
        out.append(item)
    recommend(out,target_gb)
    return {'repo_id':repo,'revision':revision,'variants':out,'license':info.get('cardData',{}).get('license'),
            'note':'Sizes are download sizes, not runtime VRAM. Recommendations are heuristics, never quality or fit measurements.'}


def recommend(items,target):
    if type(target)is not int or target not in (8,11,12,16,24,32,40,48,80):raise ValueError('Choose a supported target GPU size')
    for item in items:
        q=item['quantization'];size=item['size_bytes']
        item['recommended']=False
        if not size or not item['complete']:
            item['fit_note']='Incomplete shards or unknown size';item['_rank']=-100;continue
        gib=size/2**30;room=target-gib
        item['fit_note']='Likely too tight' if room<1.25 else 'Candidate with estimated headroom'
        bits=16 if q in ('BF16','F16') else 32 if q=='F32' else int(re.search(r'[1-8]',q)[0]) if re.search(r'[1-8]',q) else 0
        score=bits+(0.3 if '_K_M' in q else 0)-(0.2 if '_K_S' in q else 0)
        item['_rank']=score if room>=1.25 else -10+score/100
    ordered=sorted(items,key=lambda x:(x['_rank'],x['size_bytes'] or 0),reverse=True)
    picked=[]
    for item in ordered:
        if item['_rank']<0:continue
        size=item['size_bytes']/2**30
        if all(abs(size-v) >= max(.4,target*.05) for v in picked):
            item['recommended']=True;picked.append(size)
        if len(picked)==3:break
    items.sort(key=lambda x:x['size_bytes'] or 0,reverse=True)
    for item in items:item.pop('_rank',None)
