"""Versioned one-line literal text updates. Original parsers remain unchanged."""
import json,re
from workbench import dot_paths
from workbench.scoring import parse as parse_json

LINE=re.compile(r'^(set|append) ([^\s:]+): (text|json):(.*)$')
REMOVE=re.compile(r'^remove ([^\s:]+)$')

def _text_decode(value):
    out=[];i=0
    while i<len(value):
        c=value[i]
        if c!='\\':out.append(c);i+=1;continue
        if i+1>=len(value):raise ValueError('Trailing backslash in text')
        k=value[i+1];table={'\\':'\\','n':'\n','r':'\r'}
        if k not in table:raise ValueError('Invalid text escape: use \\\\, \\n or \\r')
        out.append(table[k]);i+=2
    return ''.join(out)

def _text_encode(value):return value.replace('\\','\\\\').replace('\n','\\n').replace('\r','\\r')

def decode(raw,initial=None,schema=None):
    if not isinstance(raw,str):raise ValueError('Expected text')
    if raw=='none' or raw=='none\n':return []
    if not raw:raise ValueError('Return none or one update per line')
    lines=raw.split('\n')
    if lines[-1]=='':lines.pop()
    if not lines or any(not line or '\r' in line for line in lines):raise ValueError('Empty records and raw CR are invalid')
    result=[]
    for number,line in enumerate(lines,1):
        remove=REMOVE.fullmatch(line)
        if remove:
            path=remove.group(1);dot_paths.tokens(path);result.append({'op':'remove','path':path});continue
        match=LINE.fullmatch(line)
        if not match:raise ValueError(f'Line {number}: invalid record')
        kind,path,typ,value=match.groups();dot_paths.tokens(path)
        if typ=='text':value=_text_decode(value)
        else:
            if not value:raise ValueError('JSON value is required')
            value=parse_json(value)
            if isinstance(value,str):raise ValueError('Use text: for a string value')
        result.append({'op':{'set':'replace','append':'add'}[kind],'path':path,'value':value})
    return result

def apply(initial,raw,schema):return dot_paths.apply(initial,decode(raw),schema)
def encode(operations):
    if not operations:return 'none'
    out=[]
    for op in operations:
        kind={'replace':'set','add':'append','remove':'remove'}[op['op']];path=op['path'];dot_paths.tokens(path)
        if kind=='remove':out.append('remove '+path);continue
        value=op['value'];literal='text:'+_text_encode(value) if isinstance(value,str) else 'json:'+json.dumps(value,ensure_ascii=True,allow_nan=False,separators=(',',':'))
        out.append(kind+' '+path+': '+literal)
    return '\n'.join(out)
