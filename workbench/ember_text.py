"""Ember's exact typed-line grammar, with an explicit database-study adapter.

The source parser is vendored under tests/fixtures/ember_source. No JSON repair,
array indexes, invented move/copy operations, or game-specific coercions apply.
"""
import copy
import math
import re

METHOD='ember_text_v1'
JS_SPACE='\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680'+''.join(chr(n)for n in range(0x2000,0x200b))+'\u2028\u2029\u202f\u205f\u3000\ufeff'
DECIMAL=re.compile(r'[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z')
HEADER=re.compile(r'(set|append|change|remove): (/[^\r\n\u2028\u2029]*)\Z')
TYPED=re.compile(r'(text|number|boolean|null|list|object):(?: ([^\r\n\u2028\u2029]*))?\Z')

def parse(raw):
    """Port of EmberAiResponseText.operations, including grouping and whitespace."""
    if not isinstance(raw,str):raise ValueError('Ember text output must be plain text')
    text=raw.strip(JS_SPACE)
    if text=='none':return {}
    if not text:raise ValueError('State response is empty; return none or update records.')
    lines=re.split(r'\r?\n',text);operations={};written=set();index=0
    while index<len(lines):
        if not lines[index].strip(JS_SPACE):index+=1;continue
        header=HEADER.fullmatch(lines[index])
        if not header:raise ValueError(f'State line {index+1}: expected set, append, change, or remove with an exact /path.')
        operation,pointer=header.groups();parts=pointer[1:].split('/')
        if any(not part or re.search(r'~(?![01])',part)for part in parts):
            raise ValueError(f'State line {index+1}: invalid path {pointer}.')
        path=[part.replace('~1','/').replace('~0','~')for part in parts]
        if any(part in ('__proto__','prototype','constructor')for part in path):
            raise ValueError(f'State line {index+1}: unsafe path {pointer}.')
        key=operation+':'+pointer
        if operation!='append'and key in written:raise ValueError('State response repeats '+key+'.')
        written.add(key)
        if operation=='remove':
            operations.setdefault('d',[]).append({'path':path});index+=1;continue
        index+=1;line=lines[index]if index<len(lines)else''
        if re.fullmatch(r'(null|list|object):[ \t]*',line):line=line.rstrip(JS_SPACE)
        typed=TYPED.fullmatch(line)
        if not typed:raise ValueError(f'State line {index+1}: expected one typed value after {operation}.')
        kind,content=typed.groups()
        if kind=='text':value=content if content is not None else''
        elif kind=='number':
            if not content or not DECIMAL.fullmatch(content):raise ValueError(f'State line {index+1}: number must be a finite decimal.')
            value=float(content)
            if not math.isfinite(value):raise ValueError(f'State line {index+1}: number must be a finite decimal.')
        elif kind=='boolean':
            if content not in ('true','false'):raise ValueError(f'State line {index+1}: boolean must be true or false.')
            value=content=='true'
        else:
            if content is not None:raise ValueError(f'State line {index+1}: {kind}: takes no value.')
            value=None if kind=='null'else[]if kind=='list'else{}
        if operation=='change'and kind!='number':raise ValueError(f'State line {index+1}: change requires number:.')
        operations.setdefault({'set':'s','append':'a','change':'r'}[operation],[]).append({'path':path,'value':value})
        index+=1
    return operations

def _object_path(doc,parts):
    value=doc
    for part in parts:
        if not isinstance(value,dict):
            raise ValueError('Ember study adapter does not select array elements or traverse scalars; positional/ID selectors are not invented.')
        if part not in value:raise ValueError('Missing existing object field: '+part)
        value=value[part]
    return value

def decode(raw,initial,schema):
    """Lower actual source operations to existing strict study operations.

    Ember applies sets, null/removes, appends, then numeric changes, regardless
    of record order. Its remove nullifies a field; it does not remove an array
    element. Compound construction and positional array editing are excluded.
    """
    from .value_paths import apply as apply_values,from_pointer,validate
    records=parse(raw);doc=copy.deepcopy(initial);validate(doc,schema);patch=[]
    for kind in ('s','d','a','r'):
        for record in records.get(kind,[]):
            parts=record['path'];old=_object_path(doc,parts)
            pointer='/'+ '/'.join(part.replace('~','~0').replace('/','~1')for part in parts)
            path=from_pointer(doc,schema,pointer)
            if kind=='a':
                if not isinstance(old,list):raise ValueError('Append target must be an existing collection')
                value=record['value']
                if isinstance(value,(dict,list)):raise ValueError('Compound append construction is unsupported by the unchanged study task contract')
                operation={'op':'add','path':path,'value':value}
            else:
                if isinstance(old,(dict,list)):raise ValueError('Study Update must select an existing scalar object field')
                value=None if kind=='d'else record['value']
                if isinstance(value,(dict,list)):raise ValueError('Compound set construction is unsupported by the unchanged study task contract')
                if kind=='r':
                    if type(old)not in (int,float)or not math.isfinite(old):raise ValueError('Numeric change needs an existing finite numeric field')
                    value=old+value
                    if not math.isfinite(value):raise ValueError('Numeric change result must be finite')
                operation={'op':'replace','path':path,'value':value}
            doc=apply_values(doc,[operation],schema);patch.append(operation)
    return patch

def apply(initial,raw,schema):
    from .value_paths import apply as apply_values
    return apply_values(initial,decode(raw,initial,schema),schema)

def full_paths(value,path=''):
    """Native object paths only: a collection remains a complete JSON value."""
    import json
    if isinstance(value,dict)and value:
        return [line for key,child in value.items()for line in full_paths(child,path+'/'+key.replace('~','~0').replace('/','~1'))]
    return [path+':'+json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))]

def typed(value):
    """Synthetic reference emitter, never an expected answer in a model prompt."""
    if isinstance(value,str):
        if any(c in value for c in '\r\n\u2028\u2029'):raise ValueError('Source protocol cannot encode multiline text values')
        if value!=value.rstrip(JS_SPACE):raise ValueError('Final-record trailing whitespace cannot round-trip through the source parser')
        return 'text:'+(' '+value if value else'')
    if value is None:return 'null:'
    if type(value)is bool:return 'boolean: '+str(value).lower()
    if type(value)in(int,float)and math.isfinite(value):
        # The source grammar accepts finite decimals, not exponent notation.
        from decimal import Decimal
        spelling=format(Decimal(str(value)),'f')
        return 'number: '+spelling
    raise ValueError('This study adapter emits primitive typed values only')
