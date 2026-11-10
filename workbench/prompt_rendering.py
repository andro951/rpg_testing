"""Formatting helpers for frozen research definitions and historical scripts.

New prompts are assembled by prompt_builder. The schema-based view helpers here
only reproduce archived input presentations; they do not generate test oracles.
"""
import json
from workbench.value_paths import escape, identity, selector


def render(parts, system=''):
    """Reproduce the original direct-message wrapper without loading a builder."""
    text = parts['task_requirements']
    if parts['presentation_notes']:
        text += '\n\nInput presentation:\n' + parts['presentation_notes']
    text += '\n\nCurrent data:\n' + parts['current_state'] + '\n\nTask:\n' + parts['new_information']
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': text}]


def preview(request):
    return '\n\n'.join(message['role'].upper() + ' MESSAGE\n\n' + message['content'] for message in request)


def id_keyed_arrays(value, schema):
    """Keep string IDs as keys and use JSON spelling for other scalar IDs."""
    if isinstance(value, list):
        result = {}
        for element in value:
            identifier = identity(element, schema)
            key = identifier if isinstance(identifier, str) else selector(identifier)
            if key in result:
                # A JSON object cannot distinguish numeric 42 from string "42" as keys.
                raise ValueError('Collection IDs collide as dictionary keys: ' + key)
            result[key] = id_keyed_arrays(element, schema['items'])
        return result
    if isinstance(value, dict):
        return {key: id_keyed_arrays(element, schema['properties'][key]) for key, element in value.items()}
    return value


def full_paths(value, schema, path=''):
    """Display the actual value path, then a colon and its JSON value."""
    lines = []
    if isinstance(value, list) and value:
        for element in value:
            part = selector(identity(element, schema))
            lines.extend(full_paths(element, schema['items'], path + '/' + part))
    elif isinstance(value, dict) and value:
        for key, element in value.items():
            part = selector(key) if key.startswith('"') else escape(key)
            lines.extend(full_paths(element, schema['properties'][key], path + '/' + part))
    else:
        lines.append(path + ':' + json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')))
    return lines


def structure_text(schema):
    lines = []
    def walk(node, label, depth):
        prefix, kind = '  ' * depth, node['type']
        if kind == 'object':
            lines.append(prefix + label + ': an object with exactly these fields:')
            for name, child in node['properties'].items():
                walk(child, json.dumps(name, ensure_ascii=False), depth + 1)
        elif kind == 'array':
            if node['items']['type'] == 'object':
                lines.append(prefix + label + ': a collection of objects. Each element has a unique ' + json.dumps(node['x-id-field'], ensure_ascii=False) + ' value within this collection.')
                walk(node['items'], 'Each element', depth + 1)
            else:
                lines.append(prefix + label + ': a collection of unique ' + node['items']['type'] + ' values.')
        else:
            lines.append(prefix + label + ': ' + kind + '.')
    walk(schema, 'Database', 0)
    return '\n'.join(lines)
