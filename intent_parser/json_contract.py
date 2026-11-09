"""Portable JSON formatting matching JSON.stringify within the safe number domain."""
import json
from decimal import Decimal


def stringify(value):
    if value is None:
        return 'null'
    if type(value) is bool:
        return 'true' if value else 'false'
    if type(value) is str:
        # Combine a valid explicit UTF-16 pair if supplied by a native caller.
        value = value.encode('utf-16-le', 'surrogatepass').decode('utf-16-le')
        return json.dumps(value, ensure_ascii=False)
    if type(value) in (int, float):
        if value == int(value):
            return str(int(value))
        text = repr(value)
        if 'e' not in text:
            return text
        coefficient, exponent = text.split('e')
        exp = int(exponent)
        if exp >= -6:
            return format(Decimal(text), 'f')
        return coefficient + 'e' + ('+' if exp >= 0 else '-') + str(abs(exp))
    if type(value) is list:
        return '[' + ','.join(stringify(v) for v in value) + ']'
    keys = list(value)
    numeric = [key for key in keys if key.isascii() and key.isdigit() and str(int(key)) == key and int(key) < 4294967295]
    keys = sorted(numeric, key=int) + [key for key in keys if key not in numeric]
    return '{' + ','.join(stringify(key) + ':' + stringify(value[key]) for key in keys) + '}'
