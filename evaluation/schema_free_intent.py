"""Retired schema-free-intent-v1 contract metadata, with no response decoder.

Saved historical scores and raw evidence are viewed directly. New definitions
must select the current array-identities evaluator and explicit identity map.
"""
from intent_parser.patch import IntentError
from .retired_contracts import require_supported

VERSION = 'schema-free-intent-v1'
OUTPUT_FORMATS = ('json_dot', 'json_slash', 'path_list', 'literal_line',
                  'end_marked_line', 'two_line_text', 'typed_lines', 'free_format')


class ParserGap(IntentError):
    """Unprescribed prose has no deterministic interpretation; not a model failure."""


def _retired():
    require_supported({'evaluator': {'version': VERSION}})


def configuration():
    _retired()


def identity_info():
    _retired()


def normalize_response(raw, initial_state, output_format='json_dot'):
    _retired()


def validate_selection(test, variant):
    _retired()
