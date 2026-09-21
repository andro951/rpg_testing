"""Explicit installation of official llama.cpp release archives under the repository."""
from __future__ import annotations
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import tarfile
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from urllib.request import Request, build_opener
from .hub import SecureRedirect
from .domain import write_json, digest
from .workflows import Cancelled

BASE='https://api.github.com/repos/ggml-org/llama.cpp/releases'
MAX_ARCHIVE=2*1024**3
MAX_EXTRACTED=6*1024**3

class RuntimeClient:
    def __init__(self,opener=None):self.opener=opener or build_opener(SecureRedirect()).open
    def releases(self):
        req=Request(BASE+'?per_page=15',headers={'User-Agent':'RPG-Testing-Workbench','Accept':'application/vnd.github+json'})
        with self.opener(req,timeout=30) as r:
            raw=r.read(16*1024**2+1)
            if len(raw)>16*1024**2:raise ValueError('Oversized release metadata')
            releases=json.loads(raw)
        return bundles(releases)


def bundles(releases,system=None,machine=None):
    system=system or platform.system();machine=(machine or platform.machine()).lower()
    arch='arm64' if machine in ('aarch64','arm64') else 'x64'
    result=[]
    for release in releases:
        tag=release.get('tag_name','')
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+',tag):continue
        assets=release.get('assets',[])
        for asset in assets:
            name=asset.get('name','').lower()
            host=('win' in name and 'darwin' not in name) if system=='Windows' else ('ubuntu' in name or 'linux' in name)
            if not host or arch not in name or not name.endswith(('.zip','.tar.gz')):continue
            if 'cudart' in name or not ('cuda' in name or 'vulkan' in name):continue
            selected=[asset]
            family=re.search(r'cuda[-_]?(?:cu)?(\d+)',name)
            if family:
                version=family[1]
                deps=[a for a in assets if 'cudart' in a.get('name','').lower() and
                    re.search(r'(?:cu|cuda[-_]?|cudart[-_])'+version+r'(?:[.\-_]|$)',a['name'].lower()) and
                    (arch in a['name'].lower() or 'x64' not in a['name'].lower() and 'arm64' not in a['name'].lower()) and
                    a['name'].lower().endswith('.zip' if system=='Windows' else '.tar.gz')]
                if len(deps)==1:selected+=deps
            records=[]
            for a in selected:
                url=a.get('browser_download_url','')
                if not url.startswith('https://github.com/ggml-org/llama.cpp/releases/download/'+tag+'/'):break
                if '/' in a['name'] or '\\' in a['name']:break
                records.append({k:a.get(k) for k in ('id','name','size','digest','browser_download_url')})
            if len(records)!=len(selected):continue
            key=digest({'tag':tag,'asset_ids':[a['id'] for a in records]})[:20]
            result.append({'id':key,'tag':tag,'name':asset['name'],'assets':records,
                'size_bytes':sum(a.get('size') or 0 for a in records),'prerelease':release.get('prerelease',False),
                'note':('CUDA 12 candidate for older NVIDIA hardware; runtime/device compatibility is still checked.' if family and family[1]=='12' else
                         'CUDA 13 generally requires newer NVIDIA hardware; not the GTX 1080 choice.' if family and family[1]=='13' else
                         'Vulkan GPU build; driver support and all-layer placement must pass runtime checks.')})
    return result


def member_path(root,name):
    if '\x00' in name or '\\' in name or ':' in name or name.startswith('/') or '..' in PurePosixPath(name).parts:
        raise ValueError('Unsafe runtime archive path')
    path=root.joinpath(*PurePosixPath(name).parts)
    if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Archive path escapes destination')
    return path


def extract_archive(archive,root,budget=MAX_EXTRACTED):
    root.mkdir(parents=True,exist_ok=True);written=0;links=[]
    def copy_file(name,stream,size,mode=0o644):
        nonlocal written
        path=member_path(root,name);written+=size
        if written>budget:raise ValueError('Runtime archive exceeds extraction budget')
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.is_symlink():raise ValueError('Archive tries to overwrite a symlink')
        data=stream.read(size+1)
        if len(data)!=size:raise ValueError('Invalid runtime archive member size')
        if path.exists() and path.read_bytes()!=data:raise ValueError('Conflicting files in runtime bundle')
        path.write_bytes(data)
        if os.name!='nt':path.chmod(0o755 if mode&0o111 else 0o644)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                # Validate original spelling before ZipInfo's OS-specific normalization.
                member_path(root,info.orig_filename)
                path=member_path(root,info.filename)
                if stat.S_ISLNK(info.external_attr>>16):raise ValueError('ZIP symlinks are not supported')
                if info.is_dir():path.mkdir(parents=True,exist_ok=True)
                else:
                    with z.open(info) as f:copy_file(info.filename,f,info.file_size,info.external_attr>>16)
    else:
        with tarfile.open(archive,'r:gz') as t:
            for info in t:
                path=member_path(root,info.name)
                if info.isdir():path.mkdir(parents=True,exist_ok=True)
                elif info.isfile():
                    with t.extractfile(info) as f:copy_file(info.name,f,info.size,info.mode)
                elif info.issym():links.append((path,info.linkname))
                else:raise ValueError('Unsupported special runtime archive member')
        for path,target in links:
            if os.name=='nt':raise ValueError('Install a Windows ZIP, not Unix symlink binaries')
            if target.startswith('/') or ':' in target or '\\' in target:raise ValueError('Unsafe runtime link')
            resolved=(path.parent/target).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():raise ValueError('Runtime symlink escapes or has missing target')
            if path.exists() or path.is_symlink():raise ValueError('Runtime link overwrites a file')
            path.symlink_to(target)
    return written


def install(bundle,root,cancel,log,opener=None):
    """Called only for a server-issued, user-selected bundle. Never installs drivers."""
    opener=opener or build_opener(SecureRedirect()).open
    parent=root/'.local'/'runtime';parent.mkdir(parents=True,exist_ok=True)
    dest=parent/(bundle['tag']+'-'+bundle['id'])
    if dest.exists():
        manifest=json.loads((dest/'installation.json').read_text())
        for name,h in manifest['files'].items():
            if hashlib.sha256((dest/name).read_bytes()).hexdigest()!=h:raise ValueError('Installed runtime changed; select/reinstall a clean build')
        return str(dest/manifest['executable'])
    stage=parent/('.install-'+uuid.uuid4().hex);stage.mkdir()
    extracted=stage/'files';archives=stage/'archives';archives.mkdir()
    provenance=[];remaining=MAX_EXTRACTED
    try:
        for asset in bundle['assets']:
            if cancel.is_set():raise Cancelled('Runtime installation cancelled')
            url=asset['browser_download_url']
            if not url.startswith('https://github.com/ggml-org/llama.cpp/releases/download/'+bundle['tag']+'/'):raise ValueError('Only official release assets may be installed')
            size=asset.get('size')
            if type(size)is not int or not 0<size<=MAX_ARCHIVE:raise ValueError('Invalid runtime archive size')
            if shutil.disk_usage(parent).free<size*3+128*1024**2:raise ValueError('Insufficient repository disk space for runtime archive and extraction')
            path=archives/asset['name'];hasher=hashlib.sha256();count=0
            with opener(Request(url,headers={'User-Agent':'RPG-Testing-Workbench'}),timeout=60) as response,path.open('wb') as f:
                while chunk:=response.read(1024**2):
                    if cancel.is_set():raise Cancelled('Runtime installation cancelled')
                    count+=len(chunk)
                    if count>size:raise ValueError('Runtime archive exceeds declared size')
                    hasher.update(chunk);f.write(chunk)
            h=hasher.hexdigest();expected=asset.get('digest')
            if count!=size:raise ValueError('Incomplete runtime download')
            if expected and expected!='sha256:'+h:raise ValueError('Runtime checksum mismatch')
            log('runtime','Downloaded '+asset['name']);remaining-=extract_archive(path,extracted,remaining)
            provenance.append({'name':asset['name'],'sha256':h,'publisher_digest_verified':bool(expected)})
        executables=[p for p in extracted.rglob('*') if p.is_file() and p.name in ('llama-server','llama-server.exe')]
        if len(executables)!=1:raise ValueError('Expected exactly one llama-server executable in release')
        exe=executables[0];files={p.relative_to(extracted).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in extracted.rglob('*') if p.is_file()}
        write_json(extracted/'installation.json',{'tag':bundle['tag'],'assets':provenance,'executable':exe.relative_to(extracted).as_posix(),'files':files})
        os.replace(extracted,dest)
        return str(dest/exe.relative_to(extracted))
    finally:shutil.rmtree(stage,ignore_errors=True)
