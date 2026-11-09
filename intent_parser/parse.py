"""Native port of parse.cjs and both GrammarForge grammars.

Token priority, ordered grammar alternatives, greedy repetition, component ranges,
IR construction and unique newline partitioning follow the reference in that order.
"""
from __future__ import annotations

import json
from decimal import Decimal
import re
from dataclasses import dataclass, field
from .patch import IntentError, assert_json
from .json_contract import stringify

OPERATIONS = dict(add='append', append='append', insert='append', update='update',
                  remove='remove', delete='remove', copy='copy', move='move')
LABELS = dict(op='op', operation='op', type='op', path='path', **{'from': 'from'},
              source='from', to='to', destination='to', value='value')
OPENS = {'(': ')', '[': ']', '{': '}'}
# ECMAScript whitespace, rather than Python's larger Unicode whitespace class.
WS = r'\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'
STRING = r'"(?:[^"\\\r\n]|\\.)*"'
NUMBER = r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?'
WORD = r'(?:(?!->)[^' + WS + r'"(){}\[\],;:=/\.>])+'


@dataclass
class Node:
    type: str = ''
    text: str = ''
    open: str = ''
    children: list = field(default_factory=list)

    @property
    def group(self):
        return bool(self.open)


def _compile_rules(operation=False, value_patch=False):
    rules = []
    if operation:
        for name, words in [('OP_LABEL', 'op|operation|type'),
                            ('PATH_LABEL', 'path|from|source|to|destination'), ('VALUE_LABEL', 'value')]:
            rules.append((name, r'(?:"(?:' + words + r')"|(?:' + words + r')\b)(?=[' + WS + r']*(?::|=|->))', re.I | re.A))
        aliases = 'add|append|insert|update|remove|delete|copy|move'
        if value_patch:
            aliases += '|replace'
        rules.append(('OPERATION', r'(?:' + aliases + r')\b', re.I | re.A))
    rules += [('STRING', STRING, 0), ('NUMBER', NUMBER, 0)]
    if operation:
        rules += [('BOOLEAN', r'(?:true|false)\b', re.A), ('NULL', r'null\b', re.A),
                  ('DELIMITER', r'=>|->|=', 0), ('COLON', ':', 0), ('SLASH', '/', 0), ('PATH_SEPARATOR', r'\.', 0), ('WORD', WORD, 0)]
    else:
        rules += [('DELIMITER', r'=>|->|:|=', 0), ('WORD', WORD, 0), ('PATH_SEPARATOR', r'\.|/', 0)]
    rules += [(name, re.escape(char), 0) for name, char in [
        ('LPAREN', '('), ('RPAREN', ')'), ('LBRACE', '{'), ('RBRACE', '}'),
        ('LBRACKET', '['), ('RBRACKET', ']'), ('SEP_COMMA', ',')]]
    if not operation:
        rules += [('SEMICOLON', ';', 0), ('IGNORE', '[' + WS.replace(r'\n', '').replace(r'\r', '').replace(r'\u2028', '').replace(r'\u2029', '') + ']+', 0),
                  ('NEWLINE', r'\r\n|[\r\n\u2028\u2029]', 0)]
    rules.append(('IGNORE', '[' + WS + ']+', 0))
    return [(name, re.compile(pattern, flags)) for name, pattern, flags in rules]


STRUCTURAL_RULES, OPERATION_RULES = _compile_rules(), _compile_rules(True)
VALUE_PATCH_OPERATION_RULES = _compile_rules(True, value_patch=True)


def _operations(options=None):
    # The approved CSC592 value-patch dialect names Update "replace". This is
    # scoped to that current host, not an alias in the generic intent language.
    return {**OPERATIONS, 'replace': 'update'} if (options or {}).get('pathSyntax') == 'value_patch' else OPERATIONS


def _tokenize(text, operation=False, options=None):
    result, index = [], 0
    rules = (VALUE_PATCH_OPERATION_RULES if (options or {}).get('pathSyntax') == 'value_patch' else OPERATION_RULES) if operation else STRUCTURAL_RULES
    while index < len(text):
        for kind, pattern in rules:
            match = pattern.match(text, index)
            if match:
                if kind != 'IGNORE':
                    result.append(Node(kind, match[0]))
                index = match.end()
                break
        else:
            raise IntentError('Unexpected character at index ' + str(index))
    return result


def lex_parse(text):
    tokens, index = _tokenize(text), 0
    def sequence(closer=None):
        nonlocal index
        result = []
        while index < len(tokens):
            token = tokens[index]
            index += 1
            if token.text in OPENS and token.type != 'STRING':
                result.append(Node(open=token.text, children=sequence(OPENS[token.text])))
            elif token.type in ('RPAREN', 'RBRACE', 'RBRACKET'):
                if token.text != closer:
                    raise IntentError('Mismatched grouping')
                return result
            else:
                result.append(token)
        if closer:
            raise IntentError('Unbalanced grouping')
        return result
    result = sequence()
    def check(nodes):
        for node in nodes:
            if node.group:
                check(node.children)
            elif node.type in ('NUMBER', 'STRING'):
                _json(node.text)
    check(result)
    return result


def _sep(node):
    return node.type in ('SEP_COMMA', 'NEWLINE')


def _no_duplicates(pairs):
    value = {}
    for key, child in pairs:
        if key in value:
            raise IntentError('Duplicate JSON value key')
        value[key] = child
    return value


def _parse_number(text):
    value = float(text)
    if value == 0 and Decimal(text) != 0:
        raise IntentError('Nonzero JSON number underflow')
    return value


def _json(text):
    try:
        # JSON.parse uses binary64 for every number; enforce the same safe domain.
        value = json.loads(text, parse_int=_parse_number, parse_float=_parse_number, object_pairs_hook=_no_duplicates,
                           parse_constant=lambda _: (_ for _ in ()).throw(IntentError('Nonfinite or unsafe JSON number')))
        assert_json(value)
        return value
    except (ValueError, OverflowError) as exc:
        if isinstance(exc, IntentError):
            raise
        raise IntentError('Value must be intact JSON; cannot guess or repair its contents') from exc


def _token_value(node):
    return _json(node.text) if node.type == 'STRING' else node.text


def _render(node):
    return node.open + ' '.join(map(_render, node.children)) + OPENS[node.open] if node.group else node.text


def _key(value):
    return stringify(value)


def _value_path_tokens(path):
    """CSC592 host syntax: slash boundaries outside quoted JSON string segments."""
    if path == '':
        return []
    if not path.startswith('/'):
        return [path]
    result, offset = [], 1
    while True:
        if offset < len(path) and path[offset] == '"':
            try:
                _, end = json.JSONDecoder().raw_decode(path, offset)
            except ValueError as exc:
                raise IntentError('Invalid JSON string in value path') from exc
            if end < len(path) and path[end] != '/':
                raise IntentError('A quoted path part must be followed by / or the end')
            result.append(_json(path[offset:end]))
        else:
            end = path.find('/', offset)
            if end < 0:
                end = len(path)
            part = path[offset:end]
            if part in ('true', 'false', 'null') or re.fullmatch(NUMBER, part):
                result.append(_json(part))
            else:
                if re.search(r'~(?:[^01]|$)', part):
                    raise IntentError('Invalid value path escape')
                result.append(part.replace('~1', '/').replace('~0', '~'))
        if end == len(path):
            return result
        offset = end + 1


def path_tokens(nodes, options=None):
    explicit = len(nodes) == 1 and nodes[0].group
    if explicit:
        nodes = nodes[0].children
        if not nodes:
            return []
    if len(nodes) == 1 and nodes[0].type == 'STRING':
        value = _token_value(nodes[0])
        if not explicit and (options or {}).get('pathSyntax') == 'value_patch':
            return _value_path_tokens(value)
        if not explicit and value.startswith('/'):
            if re.search(r'~(?:[^01]|$)', value):
                raise IntentError('Invalid JSON Pointer escape')
            return [part.replace('~1', '/').replace('~0', '~') for part in value[1:].split('/')]
        return [value]
    result = []
    for node in nodes:
        if node.group:
            raise IntentError('Nested path grouping is ambiguous')
        if node.type in ('PATH_SEPARATOR', 'SEP_COMMA', 'NEWLINE'):
            continue
        if node.type not in ('STRING', 'WORD', 'NUMBER'):
            raise IntentError('Invalid path token')
        result.append(_json(node.text) if node.type == 'NUMBER' or (node.type == 'WORD' and node.text in ('true', 'false', 'null')) else _token_value(node))
    if not result:
        raise IntentError('Empty path requires explicit root representation')
    return result


def _value_of(nodes):
    if not nodes:
        raise IntentError('Missing value')
    return _json(' '.join(map(_render, nodes)))


# Declarative counterpart of operation.grammar. An expression is either a token,
# ordered alternative ('|'), sequence (','), or greedy repetition ('*', '+', '?').
def _seq(*parts):
    return (',', parts)
def _alt(*parts):
    return ('|', parts)
def _repeat(part, quantifier='*'):
    return (quantifier, part)

RULES = {
    'component': _alt('operation_field', 'path_field', 'value_field', 'operation_type', 'json_value', 'path'),
    'operation_field': _seq('OP_LABEL', 'delimiter', 'operation_type'),
    'path_field': _seq('PATH_LABEL', 'delimiter', 'path'),
    'value_field': _seq('VALUE_LABEL', 'delimiter', 'json_value'),
    'delimiter': _alt('COLON', 'DELIMITER'),
    'separator': _alt('SLASH', 'PATH_SEPARATOR'),
    'path_delimiter': _alt('SLASH', 'PATH_SEPARATOR', 'SEP_COMMA'),
    'operation_type': _alt('OPERATION', 'STRING'),
    'path': _alt('grouped_path', 'scalar_path'),
    'scalar_path': _seq(_repeat('SLASH', '?'), 'path_part', _repeat(_seq('separator', 'path_part'))),
    'grouped_path': _alt(_seq('LPAREN', 'path_parts', 'RPAREN'), _seq('LBRACKET', 'path_parts', 'RBRACKET'), _seq('LBRACE', 'path_parts', 'RBRACE')),
    'path_parts': _repeat(_seq('path_part', _repeat('path_delimiter', '?'))),
    'path_part': _alt('STRING', 'NUMBER', 'WORD', 'OPERATION', 'BOOLEAN', 'NULL'),
    'json_value': _alt('json_object', 'json_array', 'STRING', 'NUMBER', 'BOOLEAN', 'NULL'),
    'json_object': _seq('LBRACE', _repeat('members', '?'), 'RBRACE'),
    'members': _seq('member', _repeat(_seq('SEP_COMMA', 'member'))),
    'member': _seq('json_key', 'COLON', 'json_value'),
    'json_key': _alt('STRING', 'OP_LABEL', 'PATH_LABEL', 'VALUE_LABEL'),
    'json_array': _seq('LBRACKET', _repeat('elements', '?'), 'RBRACKET'),
    'elements': _seq('json_value', _repeat(_seq('SEP_COMMA', 'json_value'))),
}


def _components(nodes, options=None):
    tokens = _tokenize(' '.join(map(_render, nodes)), operation=True, options=options)
    def parse(expression, index):
        if isinstance(expression, str):
            if expression in RULES:
                return parse(RULES[expression], index)
            return index + 1 if index < len(tokens) and tokens[index].type == expression else None
        kind, inner = expression
        if kind == '|':
            for alternative in inner:
                end = parse(alternative, index)
                if end is not None:
                    return end
            return None
        if kind == ',':
            for part in inner:
                index = parse(part, index)
                if index is None:
                    return None
            return index
        start = index
        while True:
            end = parse(inner, index)
            if end is None or end == index:
                break
            index = end
            if kind == '?':
                break
        return None if kind == '+' and index == start else index
    result, start = [], 0
    while start < len(tokens):
        end = parse('component', start)
        if end is None or end == start:
            raise IntentError('Invalid operation component')
        result.append(lex_parse(' '.join(token.text for token in tokens[start:end])))
        start = end
    if not result:
        raise IntentError('Missing operation')
    return result


def parse_record(nodes, options=None):
    operations = _operations(options)
    fields, unlabeled = {}, []
    for items in _components([node for node in nodes if not _sep(node)], options):
        key = LABELS.get(str(_token_value(items[0])).lower()) if not items[0].group else None
        if key and len(items) > 1 and items[1].type == 'DELIMITER':
            if key in fields:
                raise IntentError('Duplicate ' + key + ' label')
            fields[key] = items[2:]
        else:
            unlabeled.extend(items)
    if 'op' not in fields and not any(x.type == 'WORD' and x.text.lower() in operations for x in unlabeled):
        candidates = [(key, i, node) for key in ('path', 'from', 'to') for i, node in enumerate(fields.get(key, []))
                      if node.type == 'WORD' and node.text.lower() in operations
                      and (i == 0 or fields[key][i-1].type != 'PATH_SEPARATOR')
                      and (i+1 == len(fields[key]) or fields[key][i+1].type != 'PATH_SEPARATOR')]
        if len(candidates) == 1:
            key, i, node = candidates[0]
            fields[key].pop(i)
            unlabeled.append(node)
    if 'op' in fields:
        if len(fields['op']) != 1:
            raise IntentError('Exactly one operation type required')
        op = operations.get(str(_token_value(fields['op'][0])).lower())
    else:
        positions = [i for i, x in enumerate(unlabeled) if x.type == 'WORD' and x.text.lower() in operations]
        if not positions:
            positions = [i for i, x in enumerate(unlabeled) if x.type == 'STRING' and str(_token_value(x)).lower() in operations]
        if len(positions) != 1:
            raise IntentError('Exactly one unambiguous operation type required')
        op = operations.get(str(_token_value(unlabeled.pop(positions[0]))).lower())
    if not op:
        raise IntentError('Unsupported or ambiguous operation alias')
    ir = {'op': op}
    for key in ('path', 'from', 'to'):
        if key in fields:
            ir[key] = path_tokens(fields[key], options)
    if 'value' in fields:
        ir['value'] = _value_of(fields['value'])
    if op in ('append', 'update') and unlabeled:
        if 'path' in ir and 'value' not in ir:
            ir['value'] = _value_of(unlabeled)
            unlabeled.clear()
        elif 'path' not in ir and 'value' not in ir:
            candidates = {}
            for split in range(1, len(unlabeled)):
                for path, value in [(unlabeled[:split], unlabeled[split:]), (unlabeled[split:], unlabeled[:split])]:
                    try:
                        candidate = {'path': path_tokens(path, options), 'value': _value_of(value)}
                        candidates[_key(candidate)] = candidate
                    except IntentError:
                        pass
            if not candidates:
                raise IntentError('Cannot distinguish unlabeled path and JSON value')
            ir['unlabeledPathValue'] = list(candidates.values())
            unlabeled.clear()
    if unlabeled:
        if op in ('copy', 'move') and 'path' not in ir and (('from' in ir) != ('to' in ir)) and len(unlabeled) == 1 and (unlabeled[0].group or unlabeled[0].type == 'STRING'):
            ir['to' if 'from' in ir else 'from'] = path_tokens(unlabeled, options)
            unlabeled.clear()
        if unlabeled and any(key in ir for key in ('path', 'from', 'to')):
            raise IntentError('Unlabeled component conflicts with labeled paths')
        if unlabeled and op in ('copy', 'move'):
            if len(unlabeled) != 2 or not all(x.group or x.type == 'STRING' for x in unlabeled):
                raise IntentError('Two unlabeled paths require explicit grouping or quoted strings')
            ir['unlabeledPaths'] = [path_tokens([x], options) for x in unlabeled]
        elif unlabeled:
            ir['path'] = path_tokens(unlabeled, options)
    if op in ('copy', 'move'):
        if 'value' in ir:
            raise IntentError('Copy/move use source path, not value')
        if 'path' in ir:
            if 'from' in ir and 'to' not in ir:
                ir['to'] = ir.pop('path')
            elif 'to' in ir and 'from' not in ir:
                ir['from'] = ir.pop('path')
            else:
                raise IntentError('Copy/move path role ambiguous')
        if 'unlabeledPaths' not in ir and ('from' not in ir or 'to' not in ir):
            raise IntentError('Copy/move needs source and destination')
    else:
        if 'from' in ir or 'to' in ir:
            raise IntentError('Directional paths not valid for this operation')
        if 'path' not in ir and 'unlabeledPathValue' not in ir:
            raise IntentError('Missing path')
        if op == 'remove' and 'value' in ir:
            raise IntentError('Remove cannot carry a value')
        if op != 'remove' and 'value' not in ir and 'unlabeledPathValue' not in ir:
            raise IntentError('Missing value')
    return ir


def _repair_outer_wrapper(text, options):
    stack, unmatched, quoted, escaped = [], [], False, False
    for i, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char in OPENS:
            stack.append((char, i))
            if len(stack) > options.get('maxDepth', 64):
                raise IntentError('Grouping depth limit exceeded')
        elif char in OPENS.values():
            if stack:
                if OPENS[stack[-1][0]] != char:
                    raise IntentError('Mismatched grouping')
                stack.pop()
            else:
                unmatched.append((char, i))
    if quoted:
        raise IntentError('Unterminated quoted value')
    first = re.search('[^' + WS + ']', text)
    if len(stack) == 1 and not unmatched and first and stack[0][1] == first.start():
        return text + OPENS[stack[0][0]], 'missing outer closer'
    end = re.sub('[' + WS + ']+$', '', text)
    if not stack and len(unmatched) == 1 and unmatched[0][1] == len(end) - 1:
        opener = next(key for key, value in OPENS.items() if value == unmatched[0][0])
        return opener + text, 'missing outer opener'
    if stack or unmatched:
        raise IntentError('Unbalanced inner grouping cannot be safely recovered')
    return text, None


def _has_operation(node, options=None):
    operations = _operations(options)
    for i, child in enumerate(node.children):
        if child.group:
            if _has_operation(child, options):
                return True
        elif ((child.type in ('WORD', 'STRING') and str(_token_value(child)).lower() in operations) or
              (LABELS.get(str(_token_value(child)).lower()) == 'op' and i+1 < len(node.children) and node.children[i+1].type == 'DELIMITER')):
            return True
    return False


def parse_sequence(nodes, options=None):
    options = options or {}
    max_attempts, max_operations = options.get('maxBoundaryAttempts', 4096), options.get('maxOperations', 256)
    first = next((i for i, node in enumerate(nodes) if not _sep(node)), None)
    if first is None:
        return []
    last = len(nodes)
    while last > first and _sep(nodes[last-1]):
        last -= 1
    compact, separators = [], []
    def flush_separators():
        if separators:
            compact.append(next((n for n in separators if n.type == 'NEWLINE'), separators[0]))
        separators.clear()
    for node in nodes[first:last]:
        if _sep(node):
            separators.append(node)
        else:
            flush_separators()
            compact.append(node)
    flush_separators()
    nodes = compact
    if any(node.type == 'SEMICOLON' for node in nodes):
        result, segment = [], []
        for node in nodes + [Node('SEMICOLON')]:
            if node.type == 'SEMICOLON':
                if any(not _sep(n) for n in segment):
                    result.extend(parse_sequence(segment, options))
                segment = []
            else:
                segment.append(node)
        if len(result) > max_operations:
            raise IntentError('Operation count limit exceeded')
        return result
    boundaries = [0] + [i+1 for i, node in enumerate(nodes) if node.type == 'NEWLINE']
    if boundaries[-1] != len(nodes):
        boundaries.append(len(nodes))
    attempts, memo = 0, {}
    def solve(start):
        nonlocal attempts
        if start == len(nodes):
            return [[]]
        if start in memo:
            return memo[start]
        results = {}
        for end in boundaries:
            if end <= start:
                continue
            part = nodes[start:end]
            if not any(not _sep(n) for n in part):
                for tail in solve(end):
                    results[_key(tail)] = tail
                continue
            attempts += 1
            if attempts > max_attempts:
                raise IntentError('Operation boundary complexity limit exceeded; use explicit groups or semicolons')
            try:
                operation = parse_record(part, options)
            except IntentError:
                continue
            for tail in solve(end):
                if len(tail) >= max_operations:
                    raise IntentError('Operation count limit exceeded')
                candidate = [operation] + tail
                results[_key(candidate)] = candidate
                if len(results) > 1:
                    break
            if len(results) > 1:
                break
        memo[start] = list(results.values())
        return memo[start]
    candidates = solve(0)
    if len(candidates) != 1:
        raise IntentError('Ambiguous newline operation boundaries' if candidates else 'No complete operation sequence')
    return candidates[0]


def unwrap_fence(text):
    match = re.fullmatch('[' + WS + r']*```(?:json)?[ \t]*\r?\n([\s\S]*?)\r?\n```[ \t]*[' + WS + ']*', text, re.I)
    return (match[1], [{'code': 'MARKDOWN_FENCE_REMOVED', 'detail': 'single enclosing JSON code fence'}]) if match else (text, [])


def parse_intent_with_diagnostics(text, options=None):
    options = options or {}
    if type(text) is not str:
        raise IntentError('Intent text must be a string')
    if len(text.encode('utf-16-le', errors='surrogatepass')) // 2 > options.get('maxChars', 65536):
        raise IntentError('Intent text size limit exceeded')
    text, diagnostics = unwrap_fence(text)
    repaired, repair = _repair_outer_wrapper(text, options)
    tree = lex_parse(repaired)
    if repair:
        diagnostics.append({'code': 'OUTER_GROUP_RECOVERED', 'detail': repair})
    meaningful = [node for node in tree if not _sep(node)]
    if len(meaningful) == 1 and meaningful[0].group and all(_sep(n) for n in meaningful[0].children):
        return {'operations': [], 'diagnostics': diagnostics}
    candidates = {}
    def accept(records):
        if len(records) > options.get('maxOperations', 256):
            raise IntentError('Operation count limit exceeded')
        candidates[_key(records)] = records
    def retain_error(error):
        if 'limit exceeded' in str(error) or 'Ambiguous' in str(error):
            raise error
    try:
        accept(parse_sequence(tree, options))
    except IntentError as error:
        retain_error(error)
    try:
        records, current = [], []
        def flush():
            if any(not _sep(node) for node in current):
                records.extend(parse_sequence(current, options))
            current.clear()
        for node in tree:
            if node.type == 'SEMICOLON':
                flush()
            elif node.group and all(_sep(x) for x in current) and _has_operation(node, options):
                flush()
                inner = [n for n in node.children if not _sep(n)]
                if inner and all(n.group for n in inner):
                    records.extend(parse_record(child.children, options) for child in inner)
                else:
                    records.extend(parse_sequence(node.children, options))
            else:
                current.append(node)
        flush()
        accept(records)
    except IntentError as error:
        retain_error(error)
    if len(candidates) != 1:
        raise IntentError('Ambiguous complete operation interpretations' if candidates else 'No complete operation sequence')
    return {'operations': next(iter(candidates.values())), 'diagnostics': diagnostics}


def parse_intent(text, options=None):
    return parse_intent_with_diagnostics(text, options)['operations']
