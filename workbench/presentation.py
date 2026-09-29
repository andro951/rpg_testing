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
    # Keep insertion order so indexed-array keys stay 0,1,2,...,10,... and make
    # the model-facing state as readable as JSON a person would normally paste.
    return json.dumps(render_source(source,mode),ensure_ascii=False,indent=2,allow_nan=False)


def presentation_instruction(mode: str) -> str:
    if mode=='raw_json':
        return ''
    if mode=='indexed_arrays':
        return ("For this version, arrays in Current State are shown as objects with their zero-based indexes as keys. "
                "They're still arrays in the actual state, so use those numbers as array indexes in JSON Patch paths.")
    raise ValueError('Unknown state presentation: '+str(mode))
