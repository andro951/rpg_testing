"""Prototype only: end-marked, one-line string updates; no production parser changed."""
import json, re
from workbench import dot_paths
from workbench.scoring import parse as parse_json

LINE = re.compile(r'^(set|append) ([^\s:]+): (text|json):(.*)$')
REMOVE = re.compile(r'^remove ([^\s:]+)$')

def _decode_text(value):
    out, i = [], 0
    table = {'\\':'\\', 'n':'\n', 'r':'\r', 't':'\t'}
    while i < len(value):
        if value[i] != '\\':
            out.append(value[i]); i += 1; continue
        if i + 1 >= len(value) or value[i+1] not in table:
            raise ValueError('Invalid text escape')
        out.append(table[value[i+1]]); i += 2
    return ''.join(out)

def decode(raw, initial=None, schema=None):
    if not isinstance(raw, str): raise ValueError('Expected text')
    if raw in ('none', 'none\n'): return []
    if not raw: raise ValueError('Expected update lines')
    lines = raw.split('\n')
    if lines[-1] == '': lines.pop()
    if not lines or any(not line or '\r' in line for line in lines): raise ValueError('Invalid empty line or raw CR')
    result = []
    for line in lines:
        match = REMOVE.fullmatch(line)
        if match:
            path = match.group(1); dot_paths.tokens(path); result.append({'op':'remove', 'path':path}); continue
        match = LINE.fullmatch(line)
        if not match: raise ValueError('Invalid update line')
        kind, path, typ, value = match.groups(); dot_paths.tokens(path)
        if typ == 'text':
            if not value.endswith('|'): raise ValueError('Text terminator required')
            value = _decode_text(value[:-1])
        else:
            value = parse_json(value)
            if isinstance(value, str): raise ValueError('Use text for strings')
        result.append({'op':{'set':'replace', 'append':'add'}[kind], 'path':path, 'value':value})
    return result

def apply(initial, raw, schema):
    return dot_paths.apply(initial, decode(raw), schema)

def encode(ops):
    if not ops: return 'none'
    result = []
    for op in ops:
        kind = {'replace':'set', 'add':'append', 'remove':'remove'}[op['op']]
        path = op['path']; dot_paths.tokens(path)
        if kind == 'remove': result.append('remove '+path); continue
        value = op['value']
        if isinstance(value, str):
            value = value.replace('\\','\\\\').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')
            payload = 'text:' + value + '|'
        else: payload = 'json:' + json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(',',':'))
        result.append(kind+' '+path+': '+payload)
    return '\n'.join(result)
