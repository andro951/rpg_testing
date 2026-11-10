"""Normalize only missing OUTER array delimiters; never infer operation contents.

The result is an operation array in the INPUT dialect. Dot paths remain custom
until resolved against state/schema and lowered to standard JSON Pointer paths.
"""
from dataclasses import dataclass
import json


def _strict(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def bad(value):
        raise ValueError('Invalid JSON number: ' + value)
    value = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    json.dumps(value, allow_nan=False)
    return value


@dataclass(frozen=True)
class ArrayNormalization:
    operations: list
    added_opening: bool = False
    added_closing: bool = False

    def to_json(self):
        """Valid JSON text, without claiming the input paths are RFC pointers."""
        return json.dumps(self.operations, ensure_ascii=True, allow_nan=False)

    def metadata(self):
        return {'added_opening': self.added_opening,
                'added_closing': self.added_closing}


def normalize_outer_array(text):
    """Return one uniquely parsed operation array or raise ValueError.

    Try only insertion of one outer '[' and/or ']'. Internal bytes, including
    string whitespace and escapes, are untouched. Empty repaired arrays are not
    inferred. Task completeness is deliberately left to semantic validation.
    """
    if not isinstance(text, str):
        raise ValueError('AI output must be text')
    candidates = []
    for opening, closing in ((False, False), (True, False), (False, True), (True, True)):
        candidate = ('[' if opening else '') + text + (']' if closing else '')
        try:
            value = _strict(candidate)
        except (ValueError, TypeError, RecursionError):
            continue
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            continue
        if not value and (opening or closing):
            continue
        candidates.append(ArrayNormalization(value, opening, closing))
    if not candidates:
        raise ValueError('Expected complete operation objects with only optional missing outer array brackets; internal JSON is not repaired')
    if len(candidates) != 1:
        raise ValueError('Ambiguous outer array normalization')
    return candidates[0]
