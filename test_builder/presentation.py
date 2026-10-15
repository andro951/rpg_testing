"""ID-based database views; array positions are never exposed to the model."""
import json
from workbench.value_paths import escape, identity, selector


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
