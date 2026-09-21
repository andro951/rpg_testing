"""Strict JSON/patch scoring. Model output is never evaluated as executable code."""
from __future__ import annotations
import copy
import json
import re
from .domain import canonical


def parse(text):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('Duplicate JSON key: '+k)
            out[k]=v
        return out
    out=json.loads(text,object_pairs_hook=pairs)
    canonical(out)
    return out


def equal(a,b):
    if isinstance(a,bool) or isinstance(b,bool):return type(a) is type(b) and a==b
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):return a==b
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b


def pointer(path):
    if not isinstance(path,str) or (path and not path.startswith('/')):raise ValueError('Invalid JSON Pointer')
    if not path:return []
    if re.search(r'~(?![01])',path):raise ValueError('Invalid pointer escape')
    return [x.replace('~1','/').replace('~0','~') for x in path[1:].split('/')]


def idx(key,length,append=False):
    if key=='-' and append:return length
    if not re.fullmatch(r'0|[1-9][0-9]*',key):raise ValueError('Invalid array index')
    n=int(key)
    if n>=length+int(append):raise ValueError('Array index out of bounds')
    return n


def at(doc,parts):
    for p in parts:doc=doc[idx(p,len(doc))] if isinstance(doc,list) else doc[p]
    return doc


def change(doc,parts,op,value=None):
    if not parts:return None if op=='remove' else copy.deepcopy(value)
    parent,key=at(doc,parts[:-1]),parts[-1]
    if isinstance(parent,list):
        n=idx(key,len(parent),op=='add')
        if op=='add':parent.insert(n,copy.deepcopy(value))
        elif op=='remove':parent.pop(n)
        else:parent[n]=copy.deepcopy(value)
    elif isinstance(parent,dict):
        if op!='add' and key not in parent:raise ValueError('Target field does not exist')
        if op=='remove':del parent[key]
        else:parent[key]=copy.deepcopy(value)
    else:raise ValueError('Target parent is not a container')
    return doc


def apply(initial,patch,representation):
    if not isinstance(patch,list):raise ValueError('Expected an array of patch operations')
    doc=copy.deepcopy(initial)
    for item in patch:
        if not isinstance(item,dict):raise ValueError('Operation must be an object')
        op=item['op'];parts=pointer(item['path'])
        if representation=='semantic':
            if set(item)!={'op','path','value'}:raise ValueError('Semantic operation requires op, path, value')
            old=at(doc,parts)
            if op=='set':doc=change(doc,parts,'replace',item['value'])
            elif op in ('list_add','list_remove') and isinstance(old,list):
                if op=='list_add':old.append(copy.deepcopy(item['value']))
                else:
                    matches=[i for i,x in enumerate(old) if equal(x,item['value'])]
                    if len(matches)!=1:raise ValueError('Removal requires one unique match')
                    old.pop(matches[0])
            else:raise ValueError('Unknown semantic operation or non-array target')
        elif representation=='json_patch':
            if op in ('add','replace'):doc=change(doc,parts,op,item['value'])
            elif op=='remove':doc=change(doc,parts,op)
            elif op=='test':
                if not equal(at(doc,parts),item['value']):raise ValueError('JSON Patch test failed')
            elif op in ('copy','move'):
                src=pointer(item['from']);value=copy.deepcopy(at(doc,src))
                if op=='move':
                    if len(parts)>len(src) and parts[:len(src)]==src:raise ValueError('Cannot move into a descendant')
                    doc=change(doc,src,'remove')
                doc=change(doc,parts,'add',value)
            else:raise ValueError('Unknown JSON Patch operation')
        else:raise ValueError('Unknown representation')
    return doc


def changes(a,b,path=''):
    if equal(a,b):return {}
    if isinstance(a,dict) and isinstance(b,dict):
        out={}
        for key in a.keys()|b.keys():
            p=path+'/'+key.replace('~','~0').replace('/','~1')
            if key not in b:out[p]={'deleted':True}
            elif key not in a:out[p]={'value':b[key]}
            else:out.update(changes(a[key],b[key],p))
        return out
    return {path:{'value':b}}


def score_state(test,value,representation):
    from jsonschema import Draft202012Validator
    before=test['source']['initial_state'];expected=test['expected_state'];required=changes(before,expected)
    try:
        if isinstance(value,str):value=parse(value)
        actual=value if representation=='state' else apply(before,value,representation)
        if test.get('state_schema'):Draft202012Validator(test['state_schema']).validate(actual)
        predicted=changes(before,actual);shared=required.keys() & predicted.keys()
        correct=sum(equal(required[k],predicted[k]) for k in shared)
        return {'valid':True,'exact_match':equal(expected,actual),'actual_state':actual,
                'required_changes':len(required),'correct_changes':correct,
                'missed_changes':len(required.keys()-predicted.keys()),'wrong_values':len(shared)-correct,
                'unsupported_changes':len(predicted.keys()-required.keys()),
                'precision':correct/len(predicted) if predicted else None,
                'recall':correct/len(required) if required else None}
    except Exception as exc:
        return {'valid':False,'exact_match':False,'error':str(exc),'required_changes':len(required)}
