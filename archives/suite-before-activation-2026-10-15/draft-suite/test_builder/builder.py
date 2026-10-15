"""Patch-only suite authoring. No model calls, filesystem writes, or oracle insertion."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from string import Template

from workbench.domain import digest, validate_test
from workbench.presentation import render_source_text

ROOT = Path(__file__).resolve().parent
PRESENTATIONS = ('normal_json', 'indexed_arrays', 'full_paths')
LABELS = {'normal_json': 'Normal JSON', 'indexed_arrays': 'Indexed arrays', 'full_paths': 'Full paths'}
TASKS = {
    'find_one_index': ('index', None, ('array_path', 'id_field', 'id_value')),
    'find_two_indexes': ('index', None, ('array_path', 'id_field', 'id_values')),
    'index_after': ('index', None, ('array_path', 'id_field', 'id_value')),
    'append_index': ('index', None, ('array_path',)),
    'move_destination': ('index', None, ('array_path', 'id_field', 'source_id', 'target_id', 'position')),
    'add_before': ('patch', 'add', ('array_path', 'id_field', 'target_id', 'new_object')),
    'add_after': ('patch', 'add', ('array_path', 'id_field', 'target_id', 'new_object')),
    'append': ('patch', 'add', ('array_path', 'new_object')),
    'remove': ('patch', 'remove', ('array_path', 'id_field', 'id_value')),
    'replace_property': ('patch', 'replace', ('array_path', 'id_field', 'id_value', 'property', 'new_value')),
    'replace_nested': ('patch', 'replace', ('property_path', 'new_value')),
    'copy_before': ('patch', 'copy', ('array_path', 'id_field', 'source_id', 'target_id')),
    'copy_after': ('patch', 'copy', ('array_path', 'id_field', 'source_id', 'target_id')),
    'copy_append': ('patch', 'copy', ('array_path', 'id_field', 'source_id', 'destination_array')),
    'move_before': ('patch', 'move', ('array_path', 'id_field', 'source_id', 'target_id')),
    'move_after': ('patch', 'move', ('array_path', 'id_field', 'source_id', 'target_id')),
    'move_append': ('patch', 'move', ('array_path', 'id_field', 'source_id', 'destination_array')),
}


def literal(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def escape(key):
    return key.replace('~', '~0').replace('/', '~1')


def at(state, path):
    if not isinstance(path, str) or not path.startswith('/'):
        raise ValueError('Fixture paths must be non-root JSON Pointers')
    value = state
    for part in path[1:].split('/'):
        # Reject malformed escapes rather than silently matching a different key.
        if re.search(r'~(?![01])', part):
            raise ValueError('Invalid JSON Pointer escape')
        part = part.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if not re.fullmatch(r'0|[1-9][0-9]*', part) or int(part) >= len(value):
                raise ValueError('Invalid or out-of-bounds array index in fixture path')
            value = value[int(part)]
        else:
            value = value[part]
    return value


def locate(array, field, wanted):
    if not isinstance(array, list) or not isinstance(field, str) or not field:
        raise ValueError('An object array and nonempty identifier field are required')
    matches = [i for i, item in enumerate(array) if isinstance(item, dict)
               and field in item and type(item[field]) is type(wanted) and item[field] == wanted]
    if len(matches) != 1:
        raise ValueError('Each requested identifier must match exactly one object')
    return matches[0]


def validate_fixture(fixture):
    allowed = {'id', 'name', 'task', 'state', 'parameters', 'repetitions', 'expected_seconds'}
    if set(fixture) - allowed:
        raise ValueError('Unknown fixture field; oracles and prose instructions do not belong in fixture inputs')
    task = fixture['task']
    if task not in TASKS:
        raise ValueError('Unknown patch-suite task: ' + str(task))
    params = fixture['parameters']
    if set(params) != set(TASKS[task][2]):
        raise ValueError('Missing or unknown task parameters: ' + task)
    if not isinstance(fixture['state'], dict):
        raise ValueError('Initial state must be an object')
    array = at(fixture['state'], params['array_path']) if 'array_path' in params else None
    if array is not None and not isinstance(array, list):
        raise ValueError('array_path must identify an array')
    if 'id_field' in params:
        ids = params.get('id_values', [params[k] for k in ('id_value', 'source_id', 'target_id') if k in params])
        if not isinstance(ids, list) or not ids:
            raise ValueError('Identifiers must be a nonempty list')
        for value in ids:
            locate(array, params['id_field'], value)
        if task == 'find_two_indexes' and (len(ids) != 2 or ids[0] == ids[1]):
            raise ValueError('Two-index lookup requires two distinct identifiers')
        if 'source_id' in params and 'target_id' in params and params['source_id'] == params['target_id']:
            raise ValueError('Source and target must be distinct')
    if 'position' in params and params['position'] not in ('before', 'after'):
        raise ValueError('Position must be before or after')
    if 'new_object' in params and not isinstance(params['new_object'], dict):
        raise ValueError('new_object must be an object')
    if 'destination_array' in params:
        if not isinstance(at(fixture['state'], params['destination_array']), list):
            raise ValueError('Destination must be an array')
        if params['destination_array'] == params['array_path']:
            raise ValueError('Use before/after templates for same-array placement')
    if 'property_path' in params:
        at(fixture['state'], params['property_path'])
    if 'property' in params:
        item = array[locate(array, params['id_field'], params['id_value'])]
        if params['property'] not in item:
            raise ValueError('Replacement property must exist')


def full_paths(value, path=''):
    lines = []
    if isinstance(value, list):
        lines.append((path or '/') + ' (array)')
        for index, item in enumerate(value):
            lines.extend(full_paths(item, path + '/' + str(index)))
    elif isinstance(value, dict) and value:
        for key, item in value.items():
            lines.extend(full_paths(item, path + '/' + escape(key)))
    else:
        lines.append((path or '/') + ' = ' + literal(value))
    return lines


def contains_array(value):
    return isinstance(value, list) or (isinstance(value, dict) and any(contains_array(v) for v in value.values()))


def presentations(fixture):
    return PRESENTATIONS if contains_array(fixture['state']) else ('normal_json', 'full_paths')


def build_prompt(fixture, presentation, templates=ROOT / 'templates'):
    validate_fixture(fixture)
    if presentation not in presentations(fixture):
        raise ValueError('Unknown or inapplicable presentation')
    kind, operation, _ = TASKS[fixture['task']]
    if presentation == 'full_paths':
        state = '\n'.join(full_paths(fixture['state']))
        note = 'State is shown as JSON Pointer paths.'
        if contains_array(fixture['state']):
            note += ' Entries marked (array) are arrays.'
    else:
        state = render_source_text(fixture['state'], 'raw_json' if presentation == 'normal_json' else 'indexed_arrays')
        note = ('Arrays are displayed as objects whose keys are their zero-based indexes. Treat them as arrays.'
                if presentation == 'indexed_arrays' else '')
    template = Template((templates / (fixture['task'] + '.txt')).read_text(encoding='utf-8').strip())
    slots = set()
    for match in Template.pattern.finditer(template.template):
        if match.group('invalid') is not None:
            raise ValueError('Malformed template placeholder')
        name = match.group('named') or match.group('braced')
        if name:
            slots.add(name)
    if slots != set(fixture['parameters']):
        raise ValueError('Template must use exactly its task parameters')
    # Substitute once. Dollar signs, braces and marker-like text inside data stay literal.
    values = {key: literal(value) for key, value in fixture['parameters'].items()}
    if 'position' in values:
        values['position'] = fixture['parameters']['position']
    task = template.substitute(values)
    if kind == 'patch':
        task += ('\nReturn only a JSON Patch array containing exactly one ' + operation +
                 ' operation. Use JSON Pointer paths. Do not include markdown or an explanation.')
    parts = [note, 'State:\n' + state, 'Task:\n' + task]
    return '\n\n'.join(p for p in parts if p)


def oracle(fixture):
    """Generate separate grading data. This output is never passed to build_prompt."""
    validate_fixture(fixture)
    task, p = fixture['task'], fixture['parameters']
    state = copy.deepcopy(fixture['state'])
    array = at(state, p['array_path']) if 'array_path' in p else None
    def index(key):
        return locate(array, p['id_field'], p[key])
    if task == 'find_one_index':
        return str(index('id_value'))
    if task == 'find_two_indexes':
        return ', '.join(str(locate(array, p['id_field'], value)) for value in p['id_values'])
    if task == 'index_after':
        return str(index('id_value') + 1)
    if task == 'append_index':
        return str(len(array))
    if task == 'move_destination':
        source, target = index('source_id'), index('target_id')
        return str(target + (p['position'] == 'after') - (source < target))
    base = p.get('array_path')
    if task in ('add_before', 'add_after'):
        patch = {'op': 'add', 'path': base + '/' + str(index('target_id') + (task == 'add_after')), 'value': p['new_object']}
    elif task == 'append':
        patch = {'op': 'add', 'path': base + '/-', 'value': p['new_object']}
    elif task == 'remove':
        patch = {'op': 'remove', 'path': base + '/' + str(index('id_value'))}
    elif task == 'replace_property':
        patch = {'op': 'replace', 'path': base + '/' + str(index('id_value')) + '/' + escape(p['property']), 'value': p['new_value']}
    elif task == 'replace_nested':
        patch = {'op': 'replace', 'path': p['property_path'], 'value': p['new_value']}
    elif task in ('copy_before', 'copy_after', 'move_before', 'move_after'):
        source, target = index('source_id'), index('target_id')
        moving = task.startswith('move')
        destination = target + task.endswith('after') - (moving and source < target)
        patch = {'op': 'move' if moving else 'copy', 'from': base + '/' + str(source), 'path': base + '/' + str(destination)}
    elif task in ('copy_append', 'move_append'):
        patch = {'op': 'copy' if task == 'copy_append' else 'move', 'from': base + '/' + str(index('source_id')), 'path': p['destination_array'] + '/-'}
    else:
        raise ValueError('No oracle for task')
    # Use the existing independent patch executor for the saved final-state oracle.
    from workbench.scoring import apply
    return [patch], apply(state, [patch], 'json_patch')


def compile_test(fixture, reviews=None):
    validate_fixture(fixture)
    kind, operation, _ = TASKS[fixture['task']]
    prompts = {mode: build_prompt(fixture, mode) for mode in presentations(fixture)}
    proof = digest(prompts)
    review = (reviews or {}).get(fixture['id'], {})
    approved = all(review.get(role, {}).get('prompt_digest') == proof and
                   review.get(role, {}).get('status') == 'accepted' for role in ('assistant', 'isaac'))
    test = {'schema_version': 2, 'id': fixture['id'], 'name': fixture['name'],
            'description': 'Template-built ' + fixture['task'].replace('_', ' ') + '.',
            'workflow': 'steps', 'enabled': approved, 'instructions': '',
            'repetitions': fixture.get('repetitions', 3), 'timeout_seconds': 120,
            'source': {'initial_state': copy.deepcopy(fixture['state'])},
            'prompt_builder': {'task': fixture['task'], 'fixture': fixture['id'], 'prompt_digest': proof,
                               'review_status': 'accepted' if approved else 'needs_review',
                               'template_sha256': hashlib.sha256((ROOT/'templates'/(fixture['task']+'.txt')).read_text(encoding='utf-8').encode('utf-8')).hexdigest()},
            'variants': []}
    answer = oracle(fixture)
    if kind == 'patch':
        test['expected_state'] = answer[1]
    for mode, prompt in prompts.items():
        step_id = 'index' if kind == 'index' else 'patch'
        variant = {'id': mode, 'prompt_style': 'direct_text_v1',
                   'state_presentation': 'indexed_arrays' if mode == 'indexed_arrays' else 'raw_json',
                   'cache': 'default', 'steps': [{'id': step_id, 'type': 'generate', 'prompt': prompt,
                   'output': {'type': 'text'}, 'sampling': {'temperature': 0, 'top_p': 1, 'seed': 42}}],
                   'result': {'step': step_id, 'representation': 'answers' if kind == 'index' else 'json_patch'}}
        if kind == 'index':
            variant['expected_answers'] = {'index': answer}
        else:
            variant['result']['required_ops'] = [operation]
        test['variants'].append(variant)
    validate_test(test)
    return test
