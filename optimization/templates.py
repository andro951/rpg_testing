"""Full-message contracts, literal bindings, and immutable trial projections."""
import copy
import json
import re
from .catalog import catalog, expansion, registration, steps
from workbench.domain import digest, read_json
from workbench.presentation import render_source_text
from workbench.workflows import messages
from workbench.judgements import JudgementStore, definition_id

LABELS = ('current_state', 'new_information', 'task_requirements', 'presentation_notes', 'prior_outputs')
MARKER = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}')


def parse_candidate(text, labels=LABELS):
    if not isinstance(text, str):
        raise ValueError('Candidate response must be text.')
    text = text.replace('\r\n', '\n')
    if not text.startswith('SYSTEM_MESSAGE:\n'):
        raise ValueError('Start with the exact standalone SYSTEM_MESSAGE: heading; no preamble or fences.')
    headings = re.findall(r'^(SYSTEM_MESSAGE:|USER_MESSAGE:)$', text, re.M)
    if headings != ['SYSTEM_MESSAGE:', 'USER_MESSAGE:']:
        raise ValueError('Use each standalone heading exactly once, SYSTEM_MESSAGE: before USER_MESSAGE:.')
    system, user = text[len('SYSTEM_MESSAGE:\n'):].split('\nUSER_MESSAGE:\n', 1)
    if not user.strip():
        raise ValueError('USER_MESSAGE must not be empty.')
    combined = system + '\n' + user
    found = set(MARKER.findall(combined))
    if '${' in MARKER.sub('', combined):
        raise ValueError('Malformed placeholder; only literal ${label} is supported.')
    if found != set(labels):
        raise ValueError('Missing labels: ' + ', '.join(sorted(set(labels) - found)) +
                         '; unknown labels: ' + ', '.join(sorted(found - set(labels))))
    return {'system': system, 'user': user}


def substitute(template, values):
    return MARKER.sub(lambda match: values[match[1]], template)


def render(candidate, values):
    return [{'role': role, 'content': substitute(candidate[role], values)} for role in ('system', 'user')]


def full_paths(value, path='$'):
    if isinstance(value, dict) and value:
        return '\n'.join(full_paths(item, path + '.' + key) for key, item in value.items())
    if isinstance(value, list) and value:
        return '\n'.join(full_paths(item, path + '[' + str(index) + ']') for index, item in enumerate(value))
    return path + ' = ' + json.dumps(value, ensure_ascii=False)


def bindings(case, prior=None):
    test, variant = case['test'], case['variant']
    state = test['source']['initial_state']
    presentation = case['presentation']
    if presentation == 'Full paths':
        state_text = full_paths(state)
        note = 'Paths show original state locations; arrays remain arrays. Output paths must be RFC 6901 JSON Pointers, not dotted input paths.'
    else:
        indexed = presentation == 'Indexed arrays'
        state_text = render_source_text(state, 'indexed_arrays' if indexed else 'raw_json')
        note = ('Numeric object keys display the real zero-based indexes of original arrays. The authoritative state still contains arrays; use RFC 6902 array semantics.'
                if indexed else 'The state is ordinary JSON; arrays retain their real zero-based positions.')
    event = variant.get('new_information_override', test['source'].get('new_information', ''))
    required = variant.get('result', {}).get('required_ops')
    requirement = 'Return only an RFC 6902 JSON Patch array, with RFC 6901 JSON Pointer paths. Apply only established events, preserve unrelated values, and do not add explanations.'
    if required is not None:
        requirement += ' The operation list must contain exactly these operation types in this order: ' + json.dumps(required) + '.'
    return {'current_state': state_text, 'new_information': event if isinstance(event, str) else json.dumps(event, ensure_ascii=False),
            'task_requirements': requirement, 'presentation_notes': note,
            'prior_outputs': json.dumps(prior or {}, ensure_ascii=False)}


def freeze(root):
    """Freeze only reviewed, active, non-rejected members; no solution in bindings."""
    data = catalog()
    anchor = data['variants']['array_patch_move_007/indexed_object_json_patch']
    test = read_json(root / anchor['source_file'])
    variant = next(v for v in test['variants'] if v['id'] == 'indexed_object_json_patch')
    registration(test, variant, data)
    # October 8 revision: one origin gate, then the complete matching task type.
    scopes = [{'id': 'task_type', 'members': [key for key, entry in data['variants'].items()
               if entry['objective_optimization_eligible'] and entry['task_family'] == anchor['task_family']
               and entry['output_contract'] == anchor['output_contract']]}]
    rejected = JudgementStore(root).read()['entries']
    cases = {}
    layers = []
    for scope in scopes:
        members = []
        for key in scope['members']:
            entry = data['variants'][key]
            t = read_json(root / entry['source_file'])
            v = next(v for v in t['variants'] if t['id'] + '/' + v['id'] == key)
            registration(t, v, data)
            if not t.get('enabled', True) or not v.get('enabled', True) or rejected.get(definition_id(t, v), {}).get('blocked'):
                continue
            if v['result']['representation'] != 'json_patch':
                raise ValueError('Full-message binding requires a JSON Patch contract: ' + key)
            # Final-call replacement is supported; earlier calls are preserved.
            cases[key] = {'id': key, 'test': copy.deepcopy(t), 'variant': copy.deepcopy(v),
                          'presentation': entry['existing_groups']['input_presentation'],
                          'definition_id': definition_id(t, v)}
            members.append(key)
        layers.append({'id': scope['id'] if 'id' in scope else digest(scope), 'members': members})
    origin = 'array_patch_move_007/indexed_object_json_patch'
    if origin not in cases:
        raise ValueError('The origin test is disabled or rejected.')
    layers.insert(0, {'id': 'origin', 'members': [origin]})
    # The component's first scope is already origin; omit identical layers.
    unique = []
    for layer in layers:
        if not unique or set(layer['members']) != set(unique[-1]['members']):
            unique.append(layer)
    return {'cases': cases, 'layers': unique, 'workflow_fingerprint': data['workflow_fingerprint']}


def projection(case, candidate, remote=False):
    """Prompt versions overridden by a candidate become aliases, never repeats."""
    test, variant = case['test'], case['variant']
    final = variant['result']['step']
    earlier = [s for s in steps(variant['steps']) if s['id'] != final]
    controls = {} if remote else {'sampling': variant.get('sampling', {}), 'cache': variant.get('cache', 'default')}
    workflow = [{k: v for k, v in s.items() if k != 'prompt' and not (remote and k == 'sampling')}
                for s in steps(variant['steps'])]
    return digest({'bindings': bindings(case), 'earlier': [messages(test, s, {k: '<actual prior output>' for k in s.get('uses', [])}, variant) for s in earlier],
                   'workflow': workflow,
                   'controls': controls, 'contract': variant['result'], 'oracle': test.get('expected_state'),
                   'candidate': candidate,
                   'original_final_messages': messages(test, next(s for s in steps(variant['steps']) if s['id'] == final),
                                                       {k: '<actual prior output>' for s in steps(variant['steps']) for k in s.get('uses', [])}, variant) if candidate is None else None})
