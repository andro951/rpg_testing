"""Minimal, explicit array identity declarations for validator use only."""
from intent_parser.patch import IntentError, assert_json
from workbench.dot_paths import scalar_text
from workbench.scoring import equal


class IdentityMap:
    def __init__(self, declarations):
        if not isinstance(declarations, list):
            raise IntentError('array_identities must be an explicit list (use [] when there are no arrays)')
        self.fields = {}
        for entry in declarations:
            if not isinstance(entry, dict) or set(entry) != {'path', 'id_field'}:
                raise IntentError('Each array identity requires only path and id_field')
            path, field = entry['path'], entry['id_field']
            if not isinstance(path, list) or any(part is not None and type(part) is not str for part in path):
                raise IntentError('Array identity path must be a list of exact property strings and null element steps')
            if field is not None and type(field) is not str:
                raise IntentError('id_field must be an exact property string or null for primitive identities')
            path = tuple(path)
            if path in self.fields:
                raise IntentError('Duplicate array identity path: ' + repr(path))
            self.fields[path] = field
        for path in self.fields:
            for index, part in enumerate(path):
                if part is None:
                    ancestor = path[:index]
                    if ancestor not in self.fields:
                        raise IntentError('Missing parent array identity: ' + repr(ancestor))
                    if self.fields[ancestor] is None:
                        raise IntentError('Primitive identity array cannot contain nested collections: ' + repr(ancestor))

    def field(self, array, path):
        if not isinstance(array, list):
            raise IntentError('Identity requires an array at ' + repr(path))
        if path not in self.fields:
            raise IntentError('Missing array identity mapping at ' + repr(path))
        field = self.fields[path]
        for element in array:
            if field is None:
                if isinstance(element, (dict, list)):
                    raise IntentError('Primitive identity mapping cannot select container elements at ' + repr(path))
            elif not isinstance(element, dict) or field not in element or isinstance(element[field], (dict, list)):
                raise IntentError('Object identity requires scalar field ' + repr(field) + ' on every element at ' + repr(path))
        return field

    def validate(self, state, *, check_paths=True):
        assert_json(state)
        def walk(value, path):
            if isinstance(value, dict):
                for name, child in value.items():
                    walk(child, path + (name,))
            elif isinstance(value, list):
                field = self.field(value, path)
                ids = [element[field] if field is not None else element for element in value]
                if any(equal(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]):
                    raise IntentError('Duplicate collection identifiers at ' + repr(path))
                if len({scalar_text(item) for item in ids}) != len(ids):
                    raise IntentError('Ambiguous plain selectors: different typed identities have the same text at ' + repr(path))
                for child in value:
                    walk(child, path + (None,))
        walk(state, ())
        if check_paths:
            for path in self.fields:
                self._check_path(state, path)

    def _check_path(self, state, path):
        def follow(value, remaining):
            if not remaining:
                if not isinstance(value, list):
                    raise IntentError('Array identity path targets a non-array: ' + repr(path))
                return True
            part, *tail = remaining
            if part is None:
                if not isinstance(value, list):
                    raise IntentError('Array element template step targets a non-array: ' + repr(path))
                # Descendant shape is unknowable behind an empty array. Keep its
                # declaration so future additions must obey it, never guess it.
                if not value:
                    return True
                return any_results([follow(child, tail) for child in value])
            if not isinstance(value, dict):
                raise IntentError('Property template step targets a non-object: ' + repr(path))
            if part not in value:
                return False
            return follow(value[part], tail)
        def any_results(values):
            return any(values)
        if not follow(state, path):
            raise IntentError('Array identity path has no matching collection: ' + repr(path))
