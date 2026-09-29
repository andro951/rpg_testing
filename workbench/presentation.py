"""Deterministic model-facing views of authoritative JSON state."""
from __future__ import annotations
import json

MODES=('raw_json','indexed_arrays','full_paths')


def presentation_mode(test: dict, variant: dict | None = None) -> str:
    variant=variant or {}
    mode=variant.get('state_presentation',test.get('state_presentation','indexed_arrays'))
    if mode not in MODES:raise ValueError('Unknown state presentation: '+str(mode))
    return mode


def indexed_arrays(value):
    """Render every JSON array as an insertion-ordered object keyed by its real zero-based index."""
    if isinstance(value,list):
        return {str(i):indexed_arrays(item) for i,item in enumerate(value)}
    if isinstance(value,dict):
        return {key:indexed_arrays(item) for key,item in value.items()}
    return value


def _path_segment(value) -> str:
    return str(value).replace('\\','\\\\').replace('.','\\.').replace('\n','\\n').replace('\r','\\r')


def _path_value(value) -> str:
    if isinstance(value,str):
        return value.replace('\\','\\\\').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')
    if value is True:return 'true'
    if value is False:return 'false'
    if value is None:return 'null'
    return json.dumps(value,ensure_ascii=False,allow_nan=False)


def _full_path_rows(value,path=()):
    if isinstance(value,dict):
        if not value:
            yield path,'{}'
            return
        for key,item in value.items():
            yield from _full_path_rows(item,path+(_path_segment(key),))
        return
    if isinstance(value,list):
        if not value:
            yield path,'[]'
            return
        for index,item in enumerate(value):
            yield from _full_path_rows(item,path+(str(index),))
        return
    yield path,_path_value(value)


def full_paths_text(value) -> str:
    """Flatten arbitrary JSON into dot paths while preserving empty containers."""
    rows=list(_full_path_rows(value))
    if not rows:return '{}'
    out=[];previous_group=None
    for path,value_text in rows:
        parent=path[:-1]
        # Top-level scalar/empty siblings each get their own block. Nested scalar
        # siblings stay together, while neighboring object/array records separate.
        group=path if not parent else parent
        if out and group!=previous_group:out.append('')
        rendered='.'.join(path)
        out.append((rendered+': ' if rendered else '')+value_text)
        previous_group=group
    return '\n'.join(out)


def render_source(source: dict, mode: str):
    if mode=='raw_json':return source
    if mode=='indexed_arrays':return indexed_arrays(source)
    if mode=='full_paths':return full_paths_text(source)
    raise ValueError('Unknown state presentation: '+str(mode))


def render_source_text(source: dict, mode: str) -> str:
    if mode=='full_paths':return full_paths_text(source)
    # Keep insertion order so indexed-array keys stay 0,1,2,...,10,... and make
    # the model-facing state as readable as JSON a person would normally paste.
    return json.dumps(render_source(source,mode),ensure_ascii=False,indent=2,allow_nan=False)


def presentation_instruction(mode: str) -> str:
    # Modern comparison variants intentionally differ only in the rendered state.
    # Do not add representation-specific coaching here.
    if mode in MODES:return ''
    raise ValueError('Unknown state presentation: '+str(mode))
