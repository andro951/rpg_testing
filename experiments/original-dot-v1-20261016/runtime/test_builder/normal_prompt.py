"""Reviewed normal templates, optionally selected by operation, using shared LPIL rules."""
from collections import Counter
from .builder import ROOT
from workbench.domain import read_json

OPERATIONS = {'update', 'append', 'remove', 'move', 'copy', 'no_change'}


def _validate_candidate(candidate):
    from optimization import lpil
    from optimization.templates import LABELS
    if not isinstance(candidate, dict) or candidate.get('template_format') != 'lpil':
        raise ValueError('Normal prompt requires a reviewed LPIL system/user template')
    if not all(isinstance(candidate.get(role), str) and candidate[role].strip() for role in ('system', 'user')):
        raise ValueError('Normal prompt needs nonempty system and user messages')
    if Counter(lpil.replacements(candidate['system'] + '\n' + candidate['user'])) != Counter(LABELS):
        raise ValueError('Normal template must bind each supported label exactly once')


def configuration():
    config = read_json(ROOT / 'normal_prompt.json')
    if config.get('schema_version') != 1:
        raise ValueError('Unknown normal prompt configuration version')
    _validate_candidate(config['candidate'])
    overrides = config.get('operation_templates', {})
    if not isinstance(overrides, dict) or set(overrides) - OPERATIONS:
        raise ValueError('Unknown normal prompt operation')
    for override in overrides.values():
        if not isinstance(override, dict) or set(override) != {'candidate', 'provenance'} or not isinstance(override['provenance'], dict):
            raise ValueError('Operation template needs its candidate and provenance')
        _validate_candidate(override['candidate'])
    return config


def selected(config, operation=None):
    if operation is not None and operation not in OPERATIONS:
        raise ValueError('Unknown normal prompt operation')
    override = config.get('operation_templates', {}).get(operation)
    if override is not None:
        return override['candidate'], override['provenance']
    return config['candidate'], config['provenance']


def render(parts, operation=None):
    from optimization.templates import render as render_candidate
    candidate, _ = selected(configuration(), operation)
    values = {**parts, 'prior_outputs': '{}'}
    return render_candidate(candidate, values)


def preview(request):
    return '\n\n'.join(message['role'].upper() + ' MESSAGE\n\n' + message['content'] for message in request)
