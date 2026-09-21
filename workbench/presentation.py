"""Deterministic model-facing views of authoritative JSON state."""
from __future__ import annotations
import json

MODES=('raw_json','indexed_arrays')


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


def render_source(source: dict, mode: str):
    if mode=='raw_json':return source
    if mode=='indexed_arrays':return indexed_arrays(source)
    raise ValueError('Unknown state presentation: '+str(mode))


def render_source_text(source: dict, mode: str) -> str:
    # Do not sort keys: indexed-array keys must stay in numeric insertion order (0,1,2,...,10,...).
    return json.dumps(render_source(source,mode),ensure_ascii=False,separators=(',',':'),allow_nan=False)


def presentation_instruction(mode: str) -> str:
    if mode=='raw_json':
        return 'SOURCE is ordinary JSON. Arrays are shown with normal square-bracket JSON syntax.'
    if mode=='indexed_arrays':
        return ('SOURCE is an indexed view of ordinary JSON. Every original JSON array is displayed as a JSON object '
                'whose string keys are the real zero-based array indexes. Use those visible numeric keys directly as '
                'the corresponding RFC 6902 array indexes in JSON Pointer paths. The authoritative state still contains '
                'real arrays, so add, remove, move and copy use normal RFC 6902 array semantics.')
    raise ValueError('Unknown state presentation: '+str(mode))
