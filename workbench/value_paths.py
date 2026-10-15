"""Value-selected paths for fixed-schema databases; distinct from RFC JSON Pointer."""
from __future__ import annotations
import copy
import json
import re


def escape(name):
    return name.replace('~', '~0').replace('/', '~1')


def selector(value):
    if isinstance(value, (dict, list)):
        raise ValueError('Collection identities must be JSON scalar values')
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def tokens(path):
    """Respect JSON string boundaries: slashes inside quoted values are literal."""
    if not isinstance(path, str) or (path and not path.startswith('/')):
        raise ValueError('A value path must be empty or start with /')
    if not path:
        return []
    parts, offset = [], 1
    while True:
        start = offset
        if offset < len(path) and path[offset] == '"':
            try:
                _, offset = json.JSONDecoder().raw_decode(path, offset)
            except ValueError as exc:
                raise ValueError('Invalid JSON string in value path') from exc
            if offset < len(path) and path[offset] != '/':
                raise ValueError('A quoted path part must be followed by / or the end')
        else:
            offset = path.find('/', offset)
            if offset == -1:
                offset = len(path)
        parts.append(path[start:offset])
        if offset == len(path):
            return parts
        offset += 1


def property_name(part):
    if part.startswith('"'):
        return json.loads(part)
    if re.search(r'~(?![01])', part):
        raise ValueError('Invalid property escape; use ~0 for ~ and ~1 for /')
    return part.replace('~1', '/').replace('~0', '~')


def identity(item, schema):
    if isinstance(item, dict):
        field = schema.get('x-id-field')
        if not isinstance(field, str) or field not in item:
            raise ValueError('Object collection requires its declared ID field')
        value = item[field]
    else:
        value = item
    selector(value)
    return value


def resolve(state, schema, path):
    """Return the selected value, its schema and its concrete RFC pointer parts."""
    from .scoring import equal, parse
    concrete = []
    for part in tokens(path):
        if isinstance(state, dict):
            key = property_name(part)
            if key not in state or key not in schema.get('properties', {}):
                raise ValueError('Missing or undefined property: ' + key)
            state, schema = state[key], schema['properties'][key]
            concrete.append(key)
        elif isinstance(state, list):
            try:
                wanted = parse(part)
                selector(wanted)
            except (ValueError, TypeError) as exc:
                raise ValueError('An array path part must be a JSON scalar value, not an index or unquoted string') from exc
            matches = [n for n, item in enumerate(state) if equal(identity(item, schema), wanted)]
            if len(matches) != 1:
                raise ValueError(f'Collection selector {part} must match exactly one element; found {len(matches)}')
            concrete.append(str(matches[0]))
            state, schema = state[matches[0]], schema['items']
        else:
            raise ValueError('Value path continues through a scalar')
    return state, schema, concrete


def pointer(parts):
    return ''.join('/' + escape(part) for part in parts)


def validate(state, schema):
    from jsonschema import Draft202012Validator
    from .domain import local_schema
    from .scoring import equal
    if not isinstance(schema, dict):
        raise ValueError('Value paths require a predefined database schema')
    local_schema(schema)
    Draft202012Validator(schema).validate(state)
    def walk(value, node):
        if isinstance(value, dict):
            if node.get('additionalProperties') is not False or set(node.get('required', [])) != set(node.get('properties', {})):
                raise ValueError('Database objects must have fixed predefined fields')
            for key, item in value.items():
                walk(item, node['properties'][key])
        elif isinstance(value, list):
            ids = [identity(item, node) for item in value]
            if any(equal(a, b) for n, a in enumerate(ids) for b in ids[n+1:]):
                raise ValueError('Duplicate collection identifiers')
            if node['items'].get('type') == 'object' and node.get('x-id-field') not in node['items'].get('properties', {}):
                raise ValueError('Object collection requires its declared ID field, even when empty')
            for item in value:
                walk(item, node['items'])
    walk(state, schema)


def lower_operation(state, item, schema):
    """Resolve ONE operation against the current state, never all paths up front."""
    from .scoring import apply as standard_apply, at
    if not isinstance(item, dict) or item.get('op') not in ('replace', 'add', 'remove', 'move'):
        raise ValueError('Allowed operations are replace, add, remove and move')
    op = item['op']
    if not isinstance(item.get('path'), str) or (op in ('replace', 'add') and 'value' not in item):
        raise ValueError('Operation requires a string path and its value/from fields')
    context = state
    out = {'op': op}
    if op == 'move':
        if not isinstance(item.get('from'), str):
            raise ValueError('Move requires a string from path')
        _, _, source = resolve(state, schema, item['from'])
        if not source or not isinstance(at(state, source[:-1]), list):
            raise ValueError('Move source must select a collection element')
        # Resolve before removal as well to reject descendants and the same collection.
        _, _, target = resolve(state, schema, item['path'])
        if target == source[:-1] or target[:len(source)] == source:
            raise ValueError('Move requires a different collection outside its source element')
        out['from'] = pointer(source)
        context = standard_apply(state, [{'op':'remove', 'path':out['from']}], 'json_patch')
    value, _, parts = resolve(context, schema, item['path'])
    if op in ('add', 'move'):
        if not isinstance(value, list):
            raise ValueError('Append/Move path must select the destination collection itself')
        out['path'] = pointer(parts) + '/-'
    elif op == 'remove':
        if not parts or not isinstance(at(context, parts[:-1]), list):
            raise ValueError('Remove path must select a collection element')
        out['path'] = pointer(parts)
    else:
        if not parts or not isinstance(at(context, parts[:-1]), dict) or isinstance(value, list):
            raise ValueError('Update path must select an existing object field, not a collection or whole record')
        out['path'] = pointer(parts)
    if op in ('replace', 'add'):
        out['value'] = copy.deepcopy(item['value'])
    return out


def apply(initial, patch, schema):
    from .scoring import apply as standard_apply
    if not isinstance(patch, list):
        raise ValueError('Expected an array of operations')
    doc = copy.deepcopy(initial)
    validate(doc, schema)
    for item in patch:
        doc = standard_apply(doc, [lower_operation(doc, item, schema)], 'json_patch')
        validate(doc, schema)
    return doc


def from_pointer(state, schema, path):
    """Encode an internal/reference RFC pointer using current collection identities."""
    from .scoring import pointer as parts, idx
    out = ''
    for part in parts(path):
        if isinstance(state, list):
            item = state[idx(part, len(state))]
            out += '/' + selector(identity(item, schema))
            state, schema = item, schema['items']
        elif isinstance(state, dict):
            # Quoting is needed only for a property beginning with a quotation mark.
            out += '/' + (selector(part) if part.startswith('"') else escape(part))
            state, schema = state[part], schema['properties'][part]
        else:
            raise ValueError('Reference path continues through a scalar')
    return out
