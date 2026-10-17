"""Definition-bound instruction locations and explicit prompt expansion scopes."""
from pathlib import Path
from workbench.domain import code_fingerprint, digest, experiment_spec, read_json
from workbench.workflows import messages

ROOT = Path(__file__).resolve().parents[1]


def catalog():
    return read_json(Path(__file__).with_name('sharing.json'))


def steps(items):
    for step in items:
        if step['type'] == 'loop':
            yield from steps(step['steps'])
        else:
            yield step


def rendered(test, variant, step):
    # Only history messages use these placeholders; editable system/final-user
    # messages contain the original fixed input and instruction text.
    values = {key: '<prior-output>' for key in step.get('uses', [])}
    return messages(test, step, values, variant)


def registration(test, variant, data=None):
    data = data or catalog()
    key = test['id'] + '/' + variant['id']
    entry = data['variants'].get(key)
    if not entry:
        raise ValueError('Unregistered prompt sharing definition: ' + key)
    if (entry['reviewed_definition'] != digest(experiment_spec(test, variant))
            or data['workflow_fingerprint'] != code_fingerprint()):
        raise ValueError('Prompt sharing review is stale: ' + key)
    return entry


def expansion(test, variant, component, data=None):
    """Read declared layers, never infer sharing from a display category."""
    data = data or catalog()
    entry = registration(test, variant, data)
    if not entry['objective_optimization_eligible']:
        raise ValueError('Test is outside active objective optimization')
    if component not in entry['components']:
        raise ValueError('Incompatible prompt component: ' + component)
    return [data['scopes'][key] for key in entry['components'][component]['expansion_scopes']]


def locate(test, variant, slot, data=None):
    """Resolve an exact reviewed span, refusing changed instructions/input."""
    entry = registration(test, variant, data)
    if not any(slot == reviewed for binding in entry['components'].values() for reviewed in binding['slots']):
        raise ValueError('Editable prompt span is stale or unregistered')
    step = next(s for s in steps(variant['steps']) if s['id'] == slot['step_id'])
    msgs = rendered(test, variant, step)
    index = 0 if slot['message'] == 'system' else len(msgs) - 1
    text = msgs[index]['content']
    start, end = slot['start'], slot['end']
    if (not 0 <= start <= end <= len(text) or text[start:end] != slot['original_text']
            or digest(text) != slot['message_digest']):
        raise ValueError('Editable prompt span is stale')
    return {'message_index': index, 'start': start, 'end': end, 'text': text}


def validate(root=ROOT, data=None):
    """Validate all definitions, spans and nested, compatible scope memberships."""
    data = data or catalog()
    found = set()
    for folder in ('test_specs', 'examples/test_specs'):
        for path in sorted((root / folder).glob('*.json')):
            test = read_json(path)
            for variant in test['variants']:
                key = test['id'] + '/' + variant['id']
                if key in found:
                    raise ValueError('Duplicate prompt-sharing identity: ' + key)
                found.add(key)
                entry = registration(test, variant, data)
                if entry['source_file'] != path.relative_to(root).as_posix():
                    raise ValueError('Wrong definition source: ' + key)
                for component, binding in entry['components'].items():
                    for slot in binding['slots']:
                        locate(test, variant, slot, data)
                    previous = set()
                    for scope_id in binding['expansion_scopes']:
                        scope = data['scopes'][scope_id]
                        members = set(scope['members'])
                        if (len(members) != len(scope['members']) or key not in members
                                or not previous <= members):
                            raise ValueError('Invalid expansion nesting: ' + scope_id)
                        for member in members:
                            target = data['variants'][member]
                            if not target['objective_optimization_eligible'] or component not in target['components']:
                                raise ValueError('Incompatible expansion member: ' + member)
                            if component == 'task_instructions' and (target['task_family'] != entry['task_family']
                                    or target['output_contract'] != entry['output_contract']):
                                raise ValueError('Incompatible task instruction contract: ' + member)
                        previous = members
    if found != set(data['variants']):
        raise ValueError('Prompt-sharing coverage does not match source catalog')
    return {'definitions': len({e['source_file'] for e in data['variants'].values()}),
            'variants': len(found), 'scopes': len(data['scopes'])}
