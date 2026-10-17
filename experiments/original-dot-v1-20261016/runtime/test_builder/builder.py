"""Database tasks/data are independent of the selected operation method."""
from __future__ import annotations
import copy
import json
import re
from pathlib import Path
from string import Template
from jsonschema import Draft202012Validator
from workbench.domain import digest, local_schema, validate_test
from workbench.presentation import render_source_text
from workbench.scoring import apply, equal, pointer
from .presentation import full_paths, id_keyed_arrays

ROOT = Path(__file__).resolve().parent
PRESENTATIONS = ('normal_json', 'id_keyed_arrays', 'full_paths')
LABELS = {'normal_json': 'Normal JSON', 'id_keyed_arrays': 'ID-keyed arrays', 'full_paths': 'Full paths'}
METHODS = {'value_patch': {'name': 'Value-based patch', 'file': 'methods/value_patch.txt', 'representation': 'value_patch',
    'operations': {'update': 'replace', 'append': 'add', 'remove': 'remove', 'move': 'move', 'copy': 'copy', 'no_change': None}}}
METHODS['original_value_patch_v1'] = {**METHODS['value_patch'], 'name':'Original pre-optimization value patch', 'file':'methods/original_value_patch_v1.txt'}
METHODS['dot_patch_v1'] = {**METHODS['value_patch'], 'name':'Original pre-optimization dot paths v1', 'file':'methods/dot_patch_v1.txt', 'representation':'dot_patch_v1'}
DEFAULT_METHOD = 'value_patch'
TASKS = {
    'update_field': ('update', ('property_path', 'new_value')),
    'update_record': ('update', ('array_path', 'id_field', 'id_value', 'property_path', 'new_value')),
    'update_record_nested': ('update', ('array_path', 'id_field', 'id_value', 'property_path', 'new_value')),
    'append_value': ('append', ('array_path', 'new_value')),
    'append_record': ('append', ('array_path', 'new_record')),
    'remove_value': ('remove', ('array_path', 'value')),
    'remove_record': ('remove', ('array_path', 'id_field', 'id_value')),
    'move_value': ('move', ('array_path', 'value', 'destination_array')),
    'move_record': ('move', ('array_path', 'id_field', 'id_value', 'destination_array')),
    'copy_value': ('copy', ('array_path', 'value', 'destination_array')),
    'copy_record': ('copy', ('array_path', 'id_field', 'id_value', 'destination_array')),
    'no_change': ('no_change', ()),
}
TASK_TEMPLATES = {task: 'update_record' if task == 'update_record_nested' else task for task in TASKS}


def literal(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def escape(key):
    return key.replace('~', '~0').replace('/', '~1')


def at(state, path):
    value = state
    for part in pointer(path):
        if isinstance(value, list):
            if not re.fullmatch(r'0|[1-9][0-9]*', part) or int(part) >= len(value):
                raise ValueError('Invalid or out-of-bounds array index in fixture path')
            value = value[int(part)]
        elif isinstance(value, dict):
            if part not in value:
                raise ValueError('Missing fixture property: ' + part)
            value = value[part]
        else:
            raise ValueError('Fixture path continues through a scalar')
    return value


def locate(array, field, wanted):
    if not isinstance(array, list):
        raise ValueError('A collection must be an array')
    matches = [i for i, item in enumerate(array) if equal(item, wanted)] if field is None else [
        i for i, item in enumerate(array) if isinstance(item, dict) and field in item and equal(item[field], wanted)]
    if len(matches) != 1:
        raise ValueError('The requested identifier must match exactly one collection element')
    return matches[0]


def schema_at(schema, state, path):
    for part in pointer(path):
        if isinstance(state, list):
            schema, state = schema['items'], at(state, '/' + part)
        else:
            schema, state = schema['properties'][part], state[part]
    return schema


def validate_database(value, schema):
    """Check fixed fields/types and unique identities, including empty collection schemas."""
    local_schema(schema)
    Draft202012Validator.check_schema(schema)
    errors = sorted(e.message for e in Draft202012Validator(schema).iter_errors(value))
    if errors:
        raise ValueError('Database schema: ' + '; '.join(errors))
    def structure(node):
        if node['type'] == 'object':
            if node.get('additionalProperties') is not False or set(node.get('required', [])) != set(node['properties']):
                raise ValueError('Every record must define all fields and forbid extra fields')
            for child in node['properties'].values():
                structure(child)
        elif node['type'] == 'array':
            if node['items']['type'] == 'object' and node.get('x-id-field') not in node['items']['properties']:
                raise ValueError('Record collections require a predefined unique ID field')
            if node['items']['type'] != 'object' and not node.get('uniqueItems'):
                raise ValueError('Value collections must require unique elements')
            structure(node['items'])
    def walk(item, node):
        if node['type'] == 'object':
            for key, child in node['properties'].items():
                walk(item[key], child)
        elif node['type'] == 'array':
            field = node.get('x-id-field')
            ids = [element[field] for element in item] if field is not None else item
            if any(equal(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]):
                raise ValueError('Duplicate collection identifiers')
            for element in item:
                walk(element, node['items'])
    structure(schema)
    walk(value, schema)


def validate_fixture(fixture):
    allowed = {'id', 'name', 'task', 'state', 'schema', 'parameters', 'repetitions', 'expected_seconds'}
    if set(fixture) - allowed or fixture['task'] not in TASKS:
        raise ValueError('Unknown database task or fixture field')
    p, state = fixture['parameters'], fixture['state']
    if set(p) != set(TASKS[fixture['task']][1]):
        raise ValueError('Missing or unknown task parameters')
    validate_database(state, fixture['schema'])
    if 'array_path' in p:
        array = at(state, p['array_path'])
        node = schema_at(fixture['schema'], state, p['array_path'])
        if not isinstance(array, list):
            raise ValueError('array_path must identify a collection')
        if 'id_field' in p and p['id_field'] != node.get('x-id-field'):
            raise ValueError('Task identifier field must match the predefined collection ID field')
        if 'id_value' in p:
            index = locate(array, p['id_field'], p['id_value'])
            if 'property_path' in p:
                at(array[index], p['property_path'])
        if 'value' in p:
            locate(array, None, p['value'])
    elif 'property_path' in p:
        at(state, p['property_path'])
    if 'destination_array' in p:
        if p['destination_array'] == p['array_path'] or not isinstance(at(state, p['destination_array']), list):
            raise ValueError('Transfer requires a different destination collection')
        if pointer(p['destination_array'])[:len(pointer(p['array_path']))] == pointer(p['array_path']):
            raise ValueError('Transfer destinations must be independent collections')


def structure_text(schema):
    lines = []
    def walk(node, label, depth):
        prefix, kind = '  ' * depth, node['type']
        if kind == 'object':
            lines.append(prefix + label + ': an object with exactly these fields:')
            for name, child in node['properties'].items():
                walk(child, literal(name), depth + 1)
        elif kind == 'array':
            if node['items']['type'] == 'object':
                lines.append(prefix + label + ': a collection of objects. Each element has a unique ' + literal(node['x-id-field']) + ' value within this collection.')
                walk(node['items'], 'Each element', depth + 1)
            else:
                lines.append(prefix + label + ': a collection of unique ' + node['items']['type'] + ' values.')
        else:
            lines.append(prefix + label + ': ' + kind + '.')
    walk(schema, 'Database', 0)
    return '\n'.join(lines)


def contains_array(value):
    return isinstance(value, list) or (isinstance(value, dict) and any(contains_array(v) for v in value.values()))


def presentations(fixture):
    return PRESENTATIONS if contains_array(fixture['state']) else ('normal_json', 'full_paths')


def task_text(fixture, templates=ROOT / 'templates', method=DEFAULT_METHOD):
    template = Template((templates / (TASK_TEMPLATES[fixture['task']] + '.txt')).read_text(encoding='utf-8').strip())
    slots = set()
    for match in Template.pattern.finditer(template.template):
        if match.group('invalid') is not None:
            raise ValueError('Malformed template placeholder')
        name = match.group('named') or match.group('braced')
        if name:
            slots.add(name)
    if slots != set(fixture['parameters']):
        raise ValueError('Template must use exactly its task parameters')
    parameters = copy.deepcopy(fixture['parameters'])
    if METHODS[method]['representation'] in ('value_patch','dot_patch_v1'):
        if method == 'dot_patch_v1':
            from workbench.dot_paths import from_pointer
        else:
            from workbench.value_paths import from_pointer
        state, schema = fixture['state'], fixture['schema']
        for key in ('array_path','destination_array'):
            if key in parameters:
                parameters[key] = from_pointer(state,schema,parameters[key])
        if 'property_path' in parameters:
            if 'array_path' in fixture['parameters']:
                p = fixture['parameters']
                array = at(state,p['array_path'])
                record = array[locate(array,p['id_field'],p['id_value'])]
                record_schema = schema_at(schema,state,p['array_path'])['items']
                parameters['property_path'] = from_pointer(record,record_schema,p['property_path'])
            else:
                parameters['property_path'] = from_pointer(state,schema,parameters['property_path'])
    return template.substitute({key: literal(value) for key, value in parameters.items()})


def prompt_parts(fixture, presentation, method=DEFAULT_METHOD, templates=ROOT / 'templates'):
    if method in ('original_value_patch_v1','dot_patch_v1'):
        from .original_prompt import parts
        return parts(fixture, presentation, method, templates)
    oracle(fixture)  # Reject malformed or impossible task data before exporting any prompt.
    if method not in METHODS or presentation not in presentations(fixture):
        raise ValueError('Unknown operation method or inapplicable presentation')
    if presentation == 'full_paths':
        state = '\n'.join(full_paths(fixture['state'], fixture['schema']))
        note = ('Each line shows a path followed immediately by a colon and its JSON value. '
                'The path is written exactly as it selects that value, using the rules above. '
                'Empty collections are shown as [] and empty objects as {}. '
                'When putting a path into an operation, encode it as a JSON string.')
    else:
        state = (json.dumps(id_keyed_arrays(fixture['state'], fixture['schema']), ensure_ascii=False, indent=2, allow_nan=False)
                 if presentation == 'id_keyed_arrays' else render_source_text(fixture['state'], 'raw_json'))
        note = ('Collections are displayed as objects keyed by each element\'s unique ID. '
                'For an object element, the key is its designated ID field\'s value; the ID field is also kept inside the element. '
                'For a primitive element, the key is the element\'s own value. '
                'JSON object keys are strings, so non-string IDs use their JSON spelling as keys; their values keep their original JSON types. '
                'An empty collection is shown as {}. Use the database structure to distinguish collections from ordinary objects. '
                'The underlying collections remain arrays. Select their elements using the path rules above.'
                if presentation == 'id_keyed_arrays' else '')
    guidance = ('Database rules:\n' + (ROOT/'database-rules.txt').read_text(encoding='utf-8').strip() +
        '\n\n' + (ROOT/METHODS[method]['file']).read_text(encoding='utf-8').strip() +
        '\n\nDatabase structure:\n' + structure_text(fixture['schema']))
    if TASKS[fixture['task']][0] == 'update' and 'array_path' in fixture['parameters']:
        from .normal_prompt import configuration
        guidance += '\n\nTask-specific path construction:\n' + configuration()['collection_update_guidance']
    if TASKS[fixture['task']][0] in ('remove', 'move', 'copy'):
        from .normal_prompt import configuration
        key = 'collection_remove_guidance' if TASKS[fixture['task']][0] == 'remove' else 'collection_transfer_guidance'
        guidance += '\n\nTask-specific element path construction:\n' + configuration()[key]
    return {'task_requirements': guidance, 'presentation_notes': note, 'current_state': state,
            'new_information': task_text(fixture, templates, method)}


def build_messages(fixture, presentation, templates=ROOT / 'templates', method=DEFAULT_METHOD):
    if method in ('original_value_patch_v1','dot_patch_v1'):
        from .original_prompt import render
        return render(prompt_parts(fixture, presentation, method, templates))
    from .normal_prompt import render
    return render(prompt_parts(fixture, presentation, method, templates), operation=TASKS[fixture['task']][0])


def build_prompt(fixture, presentation, templates=ROOT / 'templates', method=DEFAULT_METHOD):
    return build_messages(fixture, presentation, templates, method)[-1]['content']


def oracle(fixture, method=DEFAULT_METHOD):
    """Reference patch/final state, never inserted into a model prompt."""
    validate_fixture(fixture)
    task, p, original = fixture['task'], fixture['parameters'], fixture['state']
    kind = TASKS[task][0]
    if task == 'update_field':
        patch = [{'op': 'replace', 'path': p['property_path'], 'value': p['new_value']}]
    elif kind == 'no_change':
        patch = []
    elif kind == 'update':
        index = locate(at(original, p['array_path']), p['id_field'], p['id_value'])
        path = p['array_path'] + '/' + str(index) + p['property_path']
        patch = [] if equal(at(original, path), p['new_value']) else [{'op': 'replace', 'path': path, 'value': p['new_value']}]
        if (kind == 'no_change') != (not patch):
            raise ValueError('No-change fixtures must already satisfy the request; updates must change a value')
    elif kind == 'append':
        patch = [{'op': 'add', 'path': p['array_path'] + '/-', 'value': p.get('new_record', p.get('new_value'))}]
    else:
        index = locate(at(original, p['array_path']), p.get('id_field'), p.get('id_value', p.get('value')))
        path = p['array_path'] + '/' + str(index)
        patch = [{'op': 'remove', 'path': path}] if kind == 'remove' else [{'op': kind, 'from': path, 'path': p['destination_array'] + '/-'}]
    final = apply(original, patch, 'json_patch')
    if kind == 'update' and equal(original, final):
        raise ValueError('Update fixtures must change a value; use the no-change task for an already satisfied request')
    validate_database(final, fixture['schema'])
    if METHODS[method]['representation'] in ('value_patch','dot_patch_v1'):
        if method == 'dot_patch_v1':
            from workbench.dot_paths import from_pointer
        else:
            from workbench.value_paths import from_pointer
        result = []
        context = copy.deepcopy(original)
        for item in patch:
            out = copy.deepcopy(item)
            if 'from' in item:
                out['from'] = from_pointer(context, fixture['schema'], item['from'])
            target = item['path'][:-2] if item['op'] in ('add','move','copy') else item['path']
            out['path'] = from_pointer(context, fixture['schema'], target)
            result.append(out)
            context = apply(context, [item], 'json_patch')
        patch = result
    return patch, final


def compile_test(fixture, reviews=None, method=DEFAULT_METHOD):
    if method in ('original_value_patch_v1','dot_patch_v1'):
        from .original_prompt import compile_test as compile_original
        return compile_original(fixture, reviews, method)
    if method not in METHODS:
        raise ValueError('Unknown operation method')
    validate_fixture(fixture)
    operation = METHODS[method]['operations'][TASKS[fixture['task']][0]]
    from .normal_prompt import configuration, render, selected
    config = configuration()
    effective_candidate, effective_provenance = selected(config, TASKS[fixture['task']][0])
    parts = {mode: prompt_parts(fixture, mode, method) for mode in presentations(fixture)}
    requests = {mode: render(value, operation=TASKS[fixture['task']][0]) for mode, value in parts.items()}
    systems = {request[0]['content'] for request in requests.values()}
    if len(systems) != 1:
        raise ValueError('Normal system instructions must not vary with the input presentation')
    prompts = {mode: request[-1]['content'] for mode, request in requests.items()}
    proof, test_id = digest(requests), fixture['id'] + '__' + method
    review = (reviews or {}).get(test_id, {})
    approved = all(review.get(role, {}).get('prompt_digest') == proof and review.get(role, {}).get('status') == 'accepted' for role in ('assistant', 'isaac'))
    test = {'schema_version': 2, 'id': test_id, 'name': fixture['name'], 'description': 'Database ' + TASKS[fixture['task']][0] + ' using ' + METHODS[method]['name'] + '.',
        'workflow': 'steps', 'enabled': approved, 'instructions': next(iter(systems)), 'repetitions': fixture.get('repetitions', 3), 'timeout_seconds': 120,
        'source': {'initial_state': copy.deepcopy(fixture['state'])}, 'state_schema': copy.deepcopy(fixture['schema']),
        'expected_state': oracle(fixture)[1], 'prompt_builder': {'version': 'database-v3', 'task': fixture['task'],
            'operation': TASKS[fixture['task']][0], 'method': method, 'fixture': fixture['id'], 'prompt_digest': proof,
            'review_status': 'accepted' if approved else 'needs_review', 'normal_template': copy.deepcopy(effective_provenance),
            'template_sha256': digest({'task': (ROOT/'templates'/(TASK_TEMPLATES[fixture['task']]+'.txt')).read_text(encoding='utf-8'),
                'database_rules': (ROOT/'database-rules.txt').read_text(encoding='utf-8'), 'method': (ROOT/METHODS[method]['file']).read_text(encoding='utf-8'), 'normal_template': effective_candidate, 'collection_update_guidance': config['collection_update_guidance'], 'collection_transfer_guidance': config['collection_transfer_guidance'], 'collection_remove_guidance': config['collection_remove_guidance']})}, 'variants': []}
    for mode, prompt in prompts.items():
        from .response_contract import json_patch_schema, value_patch_schema
        test['variants'].append({'id': mode, 'prompt_style': 'direct_text_v1', 'prompt_bindings': copy.deepcopy(parts[mode]),
            # direct_text_v1 sends the already-rendered prompt unchanged; the variant ID records its view.
            'state_presentation': 'raw_json', 'cache': 'default',
            'steps': [{'id': 'patch', 'type': 'generate', 'prompt': prompt, 'output': {'type': 'text'}, 'sampling': {'temperature': 0, 'top_p': 1, 'seed': 42}}],
            'result': {'step': 'patch', 'representation': METHODS[method]['representation'], 'required_ops': [operation] if operation else [],
                       'response_schema': value_patch_schema(fixture['state'],fixture['schema']) if METHODS[method]['representation']=='value_patch' else json_patch_schema(fixture['state'])}})
    validate_test(test)
    return test
