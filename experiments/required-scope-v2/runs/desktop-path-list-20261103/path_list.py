"""One complete line per update; unquoted path steps, typed JSON values."""
import json,re
from workbench import dot_paths
from workbench.scoring import parse as parse_json

LINE=re.compile(r'^(set|append|remove) \[([^\]\r\n]*)\](?:: (.*))?$')
def decode(raw, initial=None, schema=None):
    if not isinstance(raw,str):raise ValueError('Expected text')
    text=raw.strip()
    if text=='none':return []
    if not text:raise ValueError('Return none or one update per line')
    result=[]
    for number,line in enumerate(text.splitlines(),1):
        if not line.strip():continue
        match=LINE.fullmatch(line)
        if not match:raise ValueError(f'Line {number}: invalid record')
        kind,body,value=match.groups()
        if not body.strip():raise ValueError('A path must have at least one step')
        encoded=[part.strip() for part in body.split(',')]
        if any(not x for x in encoded):raise ValueError('Empty steps must be encoded as %_')
        parts=[dot_paths.decode_part(x) for x in encoded]
        op={'op':{'set':'replace','append':'add','remove':'remove'}[kind], 'path':'.'.join(dot_paths.encode_part(x) for x in parts)}
        if kind=='remove':
            if value is not None:raise ValueError('Remove has no value')
        else:
            if value is None or value=='':raise ValueError('Set and append require a JSON value')
            op['value']=parse_json(value)
        result.append(op)
    if not result:raise ValueError('Return none or one update per line')
    return result

def apply(initial,raw,schema):return dot_paths.apply(initial,decode(raw),schema)
def encode(operations):
    if not operations:return 'none'
    out=[]
    for op in operations:
        name={'replace':'set','add':'append','remove':'remove'}[op['op']]
        parts=dot_paths.tokens(op['path']);path=', '.join(dot_paths.encode_part(part) for part in parts)
        line=f'{name} [{path}]'
        if name!='remove':line+=': '+json.dumps(op['value'],ensure_ascii=True,allow_nan=False,separators=(',',':'))
        out.append(line)
    return '\n'.join(out)
