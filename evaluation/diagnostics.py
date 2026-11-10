"""Advisory explanations only; never repair or apply a submitted operation."""
import json
from workbench.scoring import equal, parse
from workbench.value_paths import identity, property_name, resolve, tokens


def value_path_hint(doc, schema, operation):
    for field in ('from', 'path') if operation['op'] in ('move', 'copy') else ('path',):
        path = operation[field]
        parts = tokens(path)
        node, definition = doc, schema
        for number, part in enumerate(parts):
            if isinstance(node, dict):
                key = property_name(part)
                node, definition = node[key], definition['properties'][key]
            elif isinstance(node, list):
                try:
                    wanted = parse(part)
                except (ValueError, TypeError):
                    matches = [x for x in node if isinstance(identity(x, definition), str)
                               and identity(x, definition) == part]
                    if len(matches) != 1:
                        return ''
                    corrected = parts[:number] + [json.dumps(part, ensure_ascii=False)] + parts[number + 1:]
                    candidate = ''.join('/' + token for token in corrected)
                    resolve(doc, schema, candidate)
                    collection = ''.join('/' + token for token in parts[:number]) or '(root collection)'
                    encoded = json.dumps({field: candidate}, ensure_ascii=False)
                    return (f' {field}: string selector {part!r} in {collection} is missing its JSON double quotes. '
                            f'Encode this field as {encoded}. Formatting suggestion only; '
                            'the submitted operation was not repaired or applied.')
                matches = [x for x in node if equal(identity(x, definition), wanted)]
                if len(matches) != 1:
                    return ''
                node, definition = matches[0], definition['items']
            else:
                return ''
        if operation['op'] == 'remove' and field == 'path' and isinstance(node, list):
            return (' Remove path selects the collection itself; it must select one element by its value or ID. '
                    + ('The from field does not select an element for Remove; it is used by Move and Copy. '
                       if 'from' in operation else '')
                    + 'No operation was repaired or applied.')
    return ''
