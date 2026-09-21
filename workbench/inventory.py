"""Discover the configured LM Studio directory, GGUF artifacts and hardware."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
from pathlib import Path
from .domain import read_json, recommend_vram, digest


def command(args: list[str], timeout: float = 20) -> str:
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    run = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace',
                         timeout=timeout, **options)
    if run.returncode:
        raise RuntimeError((run.stderr or run.stdout or f'{args[0]} failed').strip())
    return run.stdout.strip()


def executable(name: str, override: str = '') -> str | None:
    if override:
        p = Path(override).expanduser()
        return str(p.resolve()) if p.is_file() else shutil.which(override)
    found = shutil.which(name)
    if found:
        return found
    suffix = '.exe' if os.name == 'nt' else ''
    candidates = []
    if name == 'lms':
        candidates = [Path.home()/'.lmstudio/bin'/('lms'+suffix)]
    elif os.name == 'nt' and name in ('tailscale','nvidia-smi'):
        base = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))
        candidates = [base/'Tailscale/tailscale.exe'] if name == 'tailscale' else [base/'NVIDIA Corporation/NVSMI/nvidia-smi.exe',Path('C:/Windows/System32/nvidia-smi.exe')]
    return next((str(p) for p in candidates if p.is_file()), None)


def lmstudio_folder(home: Path | None = None) -> dict:
    """Read settings, never substitute a guessed default models directory."""
    home = home or Path.home()
    lmhome = Path(os.environ.get('LMSTUDIO_HOME', str(home/'.lmstudio')))
    candidates = [lmhome/'settings.json', lmhome/'.internal/settings.json',
                  lmhome/'.internal/settings-v2.json', home/'.cache/lm-studio/settings.json']
    keys = ('modelsDirectory','modelsFolder','modelDirectory','modelsPath','modelStoragePath')
    for p in candidates:
        if not p.is_file():
            continue
        try:
            settings = read_json(p)
            containers = [settings] + [settings.get(k,{}) for k in ('userPreferences','paths','settings')]
            for container in containers:
                for key in keys:
                    value = container.get(key) if isinstance(container,dict) else None
                    if isinstance(value,str) and value.strip():
                        folder = Path(os.path.expandvars(value)).expanduser()
                        if not folder.is_absolute():
                            return {'path':None,'source':str(p),'issue':'Configured model directory is not absolute'}
                        return {'path':str(folder),'source':str(p),'issue':None}
        except (ValueError,OSError,TypeError):
            continue
    return {'path':None,'source':None,'issue':'Cannot read LM Studio’s active model folder. Select its current folder once.'}


def gguf_metadata(path: Path) -> dict:
    """Read GGUF metadata only. Skip tokenizer arrays rather than loading weights."""
    scalar = {0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
    size = path.stat().st_size
    with path.open('rb') as f:
        def read(n):
            b=f.read(n)
            if len(b)!=n:raise ValueError('Truncated GGUF header')
            return b
        def number(fmt):return struct.unpack('<'+fmt,read(struct.calcsize('<'+fmt)))[0]
        def string(keep=True):
            length=number('Q')
            if length>size-f.tell():raise ValueError('Invalid GGUF string length')
            if keep:
                if length>4_000_000:raise ValueError('Oversized GGUF metadata string')
                return read(length).decode('utf-8')
            f.seek(length,1)
        def value(kind,keep=True,depth=0):
            if depth>4:raise ValueError('Nested GGUF metadata is too deep')
            if kind in scalar:return number(scalar[kind])
            if kind==8:return string(keep)
            if kind==9:
                subtype,count=number('I'),number('Q')
                if count>100_000_000:raise ValueError('Invalid GGUF array count')
                if subtype in scalar:
                    length=count*struct.calcsize('<'+scalar[subtype])
                    if length>size-f.tell():raise ValueError('Truncated GGUF array')
                    f.seek(length,1)
                else:
                    for _ in range(count):value(subtype,False,depth+1)
                return None
            raise ValueError(f'Unsupported GGUF metadata type {kind}')
        if read(4)!=b'GGUF':raise ValueError('Not a GGUF file')
        version=number('I')
        if version not in (2,3):raise ValueError(f'Unsupported GGUF version {version}')
        tensors,count=number('Q'),number('Q')
        if count>100_000:raise ValueError('Invalid GGUF metadata count')
        metadata={}
        for _ in range(count):
            key=string()
            keep=key.startswith('general.') or key.endswith(('.context_length','.block_count','.embedding_length','.attention.head_count','.attention.head_count_kv','.attention.key_length','.attention.value_length'))
            result=value(number('I'),keep)
            if keep and result is not None:metadata[key]=result
        return metadata


def scan_models(root: Path, catalog: list[dict], inventory: list[dict] | None = None) -> list[dict]:
    if not root.is_dir():return []
    groups={}
    for path in sorted(root.rglob('*.gguf')):
        if path.is_symlink() or 'mmproj' in path.name.lower():continue
        match=re.fullmatch(r'(.+)-(\d{5})-of-(\d{5})\.gguf',path.name)
        group=str(path.parent/(match[1]+'.gguf')) if match else str(path)
        groups.setdefault(group,[]).append(path)
    out=[]
    for key,paths in groups.items():
        paths=sorted(paths)
        names=[p.name for p in paths]
        shard=re.fullmatch(r'(.+)-(\d{5})-of-(\d{5})\.gguf',paths[0].name)
        expected=[f'{shard[1]}-{n:05}-of-{int(shard[3]):05}.gguf' for n in range(1,int(shard[3])+1)] if shard else names
        matches=[m for m in catalog if sorted(m['files'])==sorted(expected)]
        entry=matches[0] if len(matches)==1 else {}
        errors=[]
        try:meta=gguf_metadata(paths[0])
        except (ValueError,OSError,UnicodeError) as e:meta={};errors.append(str(e))
        quant=re.search(r'(IQ\d[^.]*|Q\d[^.]*|BF16|F16|F32)(?:-|\.)',paths[0].name,re.I)
        quant_name=entry.get('quantization') or (quant[1].split('-')[0] if quant else 'unknown')
        relative=paths[0].relative_to(root).as_posix()
        inv_matches=[]
        for item in inventory or []:
            invkey=item.get('key') or item.get('modelKey') or item.get('path','')
            invpath=item.get('path','')
            iq=item.get('quantization',{})
            iq=iq.get('name','') if isinstance(iq,dict) else iq
            if invkey==relative or invpath==relative or invpath==str(paths[0]) or paths[0].name in str(invkey):
                inv_matches.append(invkey)
            elif '/'.join(relative.split('/')[:2]).lower() in str(invkey).lower() and str(iq).upper()==quant_name.upper():
                inv_matches.append(item.get('selected_variant') or invkey)
        inv_matches=list(dict.fromkeys(inv_matches))
        if len(inv_matches)>1:errors.append('LM Studio inventory has ambiguous model keys')
        size_bytes=sum(p.stat().st_size for p in paths)
        out.append({'id':entry.get('id') or ('local-'+digest(expected)[:16]),'name':meta.get('general.name',Path(key).stem),
                    'paths':[str(p) for p in paths],'files':expected,'size_bytes':size_bytes,
                    'quantization':quant_name,'required_vram_gb':entry.get('required_vram_gb'),
                    'recommended_vram_gb':recommend_vram(size_bytes),'catalogued':bool(entry),
                    'complete':names==expected,'missing_shards':sorted(set(expected)-set(names)),
                    'model_key':inv_matches[0] if len(inv_matches)==1 else relative,
                    'key_source':'LM Studio inventory' if len(inv_matches)==1 else 'configured-root relative artifact path',
                    'metadata':meta,'errors':errors,'catalog':entry})
    return out


def file_hashes(paths: list[str]) -> dict:
    out={}
    for filename in paths:
        h=hashlib.sha256()
        with open(filename,'rb') as f:
            for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
        out[Path(filename).name]=h.hexdigest()
    return out


def detect_gpus(run=command) -> list[dict]:
    exe=executable('nvidia-smi') or 'nvidia-smi'
    raw=run([exe,'--query-gpu=index,uuid,name,memory.total,memory.free,driver_version','--format=csv,noheader,nounits'])
    gpus=[]
    visible=os.environ.get('CUDA_VISIBLE_DEVICES')
    for row in csv.reader(io.StringIO(raw)):
        if len(row)!=6:raise ValueError('Unexpected nvidia-smi output')
        idx,uid,name,total,free,driver=[x.strip() for x in row]
        if visible is not None and idx not in visible.split(',') and uid not in visible.split(','):continue
        gpus.append({'index':idx,'uuid':uid,'name':name,'total_gib':float(total)/1024,'free_gib':float(free)/1024,'driver':driver})
    return gpus


def automatic_context(tests: list[dict], metadata: dict) -> dict:
    """Automatic finite allocation, including the explicitly shared cached prefix."""
    maximum=next((int(v) for k,v in metadata.items() if k.endswith('.context_length')),None)
    if not maximum or maximum<512:raise ValueError('Model context metadata is unavailable')
    def prompt_bytes(steps):
        total=0
        for step in steps:
            if step.get('type')=='loop':total+=step['max_iterations']*prompt_bytes(step['steps'])
            else:total+=len(step.get('prompt','').encode('utf-8'))+128
        return total
    longest=0
    for test in tests:
        fixed=len(json.dumps(test['source'],ensure_ascii=False).encode('utf-8'))
        fixed+=len(test.get('shared_prefix','').encode('utf-8'))+len(test.get('instructions','').encode('utf-8'))+256
        branch=max((prompt_bytes(v['steps']) for v in test['variants'] if v.get('enabled',True)),default=0)
        longest=max(longest,fixed+branch)
    desired=max(4096,2**math_ceil_log2(max(1,longest*2+2048)))
    # Bytes are only a planning estimate, not tokenizer output. A conservative estimate
    # exceeding native context must not falsely prove that the actual tokens cannot fit.
    context=min(desired,maximum)
    return {'allocated_tokens':context,'native_tokens':maximum,'input_estimate_bytes':longest,
            'method':'conservative byte estimate including shared prefix plus headroom; exact native runtime guard',
            'input_may_exceed_native_context':longest>=maximum,'output_cap':None}


def math_ceil_log2(n: int) -> int:return (n-1).bit_length()
