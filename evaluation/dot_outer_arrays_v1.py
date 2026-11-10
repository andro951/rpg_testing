"""Offline outer-array tolerance composed with approved separator resolution."""
from normalization.outer_arrays import normalize_outer_array
from .dot_separators_v2 import apply, lower_operation, syntax_tokens
VERSION = 'dot-outer-arrays-v1'


def parse_response(text):
    normalized = normalize_outer_array(text)
    changes = normalized.metadata()
    return normalized.operations, changes if any(changes.values()) else None
