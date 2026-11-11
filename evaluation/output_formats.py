"""One grammar entry point for every current model-response presentation.

Output format selects literal TEXT encoding only. Operation recognition and
recursive structure always belong to the shared intent grammar, never an
independent per-format reader. This module preserves lexical path information
for state-aware resolution without reading prompts or expected answers.
"""
from __future__ import annotations

import re

from intent_parser.parse import parse_intent_with_diagnostics, _token_value, _json, unwrap_fence, WS
from intent_parser.patch import IntentError
from workbench.dot_paths import decode_part
from workbench.scoring import parse
from .live_intent import _decode_path


def _path(nodes, options):
    """Preserve explicit types, slash spelling, and dot/group boundaries."""
    if len(nodes) == 1 and nodes[0].type == 'RAW_PATH':
        reference = {'kind': 'slash', 'text': nodes[0].text}
    elif len(nodes) == 1 and nodes[0].type == 'STRING' and _token_value(nodes[0]).startswith('/'):
        reference = {'kind': 'slash', 'text': _token_value(nodes[0])}
    elif nodes and not nodes[0].group and nodes[0].text == '/':
        reference = {'kind': 'slash', 'text': ''.join(node.text for node in nodes)}
    elif len(nodes) == 1 and nodes[0].group:
        parts, typed_parts = [], []
        atoms = [node for node in nodes[0].children if node.type not in ('SEP_COMMA', 'NEWLINE', 'PATH_SEPARATOR')]
        # A quoted component identifies explicit typed components. Entirely
        # unquoted lists are the documented textual path-list presentation.
        json_components = any(node.type == 'STRING' for node in atoms)
        for node in nodes[0].children:
            if node.type in ('SEP_COMMA', 'NEWLINE', 'PATH_SEPARATOR'):
                continue
            if node.group or node.type not in ('STRING', 'WORD', 'NUMBER'):
                raise IntentError('Grouped paths require scalar components')
            typed_parts.append(json_components or node.type == 'STRING')
            if node.type == 'STRING':
                parts.append(_token_value(node))
            elif node.type == 'NUMBER' or node.text in ('true', 'false', 'null'):
                value = _json(node.text)  # Validate even when retaining textual identity.
                parts.append(value if json_components else node.text)
            else:
                parts.append(decode_part(node.text))
        reference = {'kind': 'components', 'parts': parts, 'typed_parts': typed_parts}
    else:
        reference = _decode_path(nodes, options)
    if options.get('output_format') == 'typed_lines':
        reference = {**reference, 'reject_unsafe_fields': True}
    return reference


def decode(raw, output_format, initial_state, *, identity_context=None):
    """Normalize structure with the same parser regardless of requested syntax.

    ``initial_state`` and ``identity_context`` are intentionally not consulted
    here: semantic path selection happens only in the host, after parsing.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise IntentError('A nonempty textual response is required')
    try:
        result = parse_intent_with_diagnostics(raw, {
            'pathSyntax': 'value_patch', 'output_format': output_format,
            '_host_path_decoder': _path, '_host_value_decoder': parse})
    except ValueError as exc:
        if output_format == 'free_format':
            from .schema_free_intent import ParserGap
            raise ParserGap('Free-format response could not be normalized; prose semantic correctness is unknown: ' + str(exc)) from exc
        raise
    if not result['operations']:
        unwrapped, _ = unwrap_fence(raw)
        if re.fullmatch('[' + WS + ']*(?:none|\\[[' + WS + ']*\\])[' + WS + ']*', unwrapped, re.I) is None:
            raise IntentError('No change requires explicit none or an empty array')
    result['diagnostics'] = {'reader': 'shared_intent_grammar',
                             'requested_output_format': output_format,
                             'semantic_inference': False,
                             'parser': result['diagnostics']}
    return result
