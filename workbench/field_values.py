"""Research field/value records with schema-aware IDs and actual array deletion.

This is an independent research protocol, not the source application's parser.
Values are complete JSON literals, preserving types and arbitrary nested values.
"""
import re
from .scoring import parse as parse_json

METHOD='field_value_v2'

def decode(raw,initial=None,schema=None):
    if not isinstance(raw,str):raise ValueError('Expected plain-text field/value records')
    text=raw.strip()
    if text=='none':return []
    if not text:raise ValueError('Return none or field/value records; an empty response is invalid')
    lines=re.split(r'\r?\n',text);result=[];index=0
    while index<len(lines):
        if not lines[index].strip():index+=1;continue
        match=re.fullmatch(r'(set|append|remove): (.*)',lines[index])
        if not match:raise ValueError(f'Line {index+1}: expected set, append or remove followed by its path')
        kind,path=match.groups()
        operation={'op':{'set':'replace','append':'add','remove':'remove'}[kind],'path':path}
        index+=1
        if kind!='remove':
            if index>=len(lines)or not lines[index].startswith('value: '):
                raise ValueError(f'Line {index+1}: set/append requires one immediately following value: JSON literal line')
            operation['value']=parse_json(lines[index][len('value: '):]);index+=1
        result.append(operation)
    return result

def apply(initial,raw,schema):
    from .dot_paths import apply as apply_values
    return apply_values(initial,decode(raw),schema)

def encode(operations):
    import json
    if not operations:return 'none'
    records=[]
    for operation in operations:
        kind={'replace':'set','add':'append','remove':'remove'}.get(operation.get('op'))
        if not kind:raise ValueError('This study requires only Update, array Add and array Remove')
        text=kind+': '+operation['path']
        if kind!='remove':text+='\nvalue: '+json.dumps(operation['value'],ensure_ascii=True,allow_nan=False,separators=(',',':'))
        records.append(text)
    return '\n\n'.join(records)
