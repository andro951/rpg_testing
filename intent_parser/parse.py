"""Native interpreter of the generated GrammarForge grammar specification.

Token priority, ordered grammar alternatives, greedy repetition, component ranges,
IR construction and unique newline partitioning follow the reference in that order.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from functools import lru_cache
import re
from dataclasses import dataclass, field
from .patch import IntentError, assert_json
from .json_contract import stringify

OPERATIONS = dict(add='append', append='append', insert='append', update='update', set='update', change='update',
                  remove='remove', delete='remove', copy='copy', move='move')
LABELS = dict(op='op', operation='op', type='op', path='path', **{'from': 'from'},
              source='from', to='to', destination='to', value='value')
OPENS = {'(': ')', '[': ']', '{': '}'}
# ECMAScript whitespace, rather than Python's larger Unicode whitespace class.
WS = r'\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'
NUMBER = r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?'


@dataclass
class Node:
    type: str = ''
    text: str = ''
    open: str = ''
    children: list = field(default_factory=list)
    start: int = 0
    end: int = 0

    @property
    def group(self):
        return bool(self.open)


# This generated artifact is exported from GrammarForge, not a second grammar.
SPEC = json.loads(Path(__file__).with_name('grammar-spec.json').read_text())['grammars']


def _js_whitespace(source):
    result, in_class, index = [], False, 0
    while index < len(source):
        char = source[index]
        if char == '\\' and index + 1 < len(source):
            escape = source[index + 1]
            result.append((WS if in_class else '[' + WS + ']') if escape == 's' else source[index:index + 2])
            index += 2
            continue
        if char == '[':
            in_class = True
        elif char == ']':
            in_class = False
        result.append(char)
        index += 1
    return ''.join(result)


@lru_cache(maxsize=None)
def _compile_rules(grammar, value_patch=False):
    rules = []
    for token in SPEC[grammar]['tokens']:
        source = token['source']
        if value_patch and token['type'] in ('UPDATE', 'Q_UPDATE'):
            source = source.replace('update', '(?:update|replace)')
        # Preserve ECMAScript whitespace and ASCII word boundaries in Python.
        source = source.replace(r'[^\S\r\n\u2028\u2029]', '[' + WS.replace(r'\n', '').replace(r'\r', '').replace(r'\u2028', '').replace(r'\u2029', '') + ']')
        source = _js_whitespace(source)
        source = source.replace(r'\\.', r'\\[^\r\n\u2028\u2029]')
        flags = re.A | (re.I if 'i' in token.get('flags', '') else 0)
        rules.append((token['type'], re.compile(source, flags), token.get('tag') == 'IGNORE'))
    return rules


@dataclass
class GrammarNode:
    type: str
    start: int
    end: int
    children: list


def _grammar_parse(text, grammar, options=None):
    tokens = _tokenize(text, grammar=grammar, options=options)
    rules = SPEC[grammar]['rules']
    def parse(expression, index):
        if isinstance(expression, str):
            if expression in rules:
                found = yield rules[expression], index
                if found is None:
                    return None
                end, children = found
                return end, [GrammarNode(expression, index, end, children)]
            if index < len(tokens) and tokens[index].type == expression:
                return index + 1, []
            return None
        kind, inner = expression
        if kind == '|':
            for alternative in inner:
                result = yield alternative, index
                if result is not None:
                    return result
            return None
        children = []
        if kind == ',':
            for part in inner:
                found = yield part, index
                if found is None:
                    return None
                index, child = found
                children.extend(child)
            return index, children
        start = index
        while True:
            found = yield inner, index
            if found is None or found[0] == index:
                break
            index, child = found
            children.extend(child)
            if kind == '?':
                break
        return None if kind == '+' and start == index else (index, children)
    # Explicit interpreter stack avoids Python's recursion limit for long
    # statement lists without changing process-global recursion settings.
    stack = [parse(SPEC[grammar]['start'], 0)]
    result = None
    while stack:
        try:
            expression, index = stack[-1].send(result)
            stack.append(parse(expression, index))
            result = None
        except StopIteration as completed:
            stack.pop()
            result = completed.value
    if result is None or result[0] != len(tokens):
        raise IntentError('No complete operation sequence')
    return tokens, result[1][0]


def _operations(options=None):
    # The approved CSC592 value-patch dialect names Update "replace". This is
    # scoped to that current host, not an alias in the generic intent language.
    return {**OPERATIONS, 'replace': 'update'} if (options or {}).get('pathSyntax') == 'value_patch' else OPERATIONS


def _tokenize(text, operation=False, options=None, grammar=None):
    result, index = [], 0
    rules = _compile_rules(grammar or ('operation' if operation else 'tokens'), (options or {}).get('pathSyntax') == 'value_patch')
    while index < len(text):
        for kind, pattern, ignore in rules:
            match = pattern.match(text, index)
            if match and match.end() > index:
                if not ignore:
                    result.append(Node(kind, match[0], start=index, end=match.end()))
                index = match.end()
                break
        else:
            raise IntentError('Unexpected character at index ' + str(index))
    return result


def lex_parse(text):
    tokens, ast = _grammar_parse(text, 'tokens')
    def convert(node):
        if node.type == 'group':
            return [Node(open=tokens[node.start].text, children=[item for child in node.children for item in convert(child)])]
        if node.type == 'atom':
            token = tokens[node.start]
            if token.type in ('NUMBER', 'STRING'):
                _json(token.text)
            return [token]
        return [item for child in node.children for item in convert(child)]
    return convert(ast)


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
    # Private host hook preserves lexical boundaries without changing the generic
    # language or the shared JS/C# contract. Never sourced from model output.
    decoder = (options or {}).get('_host_path_decoder')
    if decoder is not None:
        return decoder(nodes, options)
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


def _value_of(nodes, options=None):
    if not nodes:
        raise IntentError('Missing value')
    raw = ' '.join(map(_render, nodes))
    value = _json(raw)  # Retain shared finite/safe/duplicate/Unicode validation.
    decoder = (options or {}).get('_host_value_decoder')
    return decoder(raw) if decoder is not None else value


def _components(nodes, options=None):
    tokens, ast = _grammar_parse(' '.join(map(_render, nodes)), 'operation', options)
    return _ast_components(tokens, ast)


def _ast_components(tokens, ast):
    result = []
    def visit(node):
        if node.type.endswith('_component'):
            result.append([item for item in lex_parse(' '.join(token.text for token in tokens[node.start:node.end])) if not _sep(item)])
        else:
            for child in node.children:
                visit(child)
    visit(ast)
    return result


def parse_record(nodes, options=None):
    text = ' '.join(_render(node) for node in nodes if not _sep(node))
    tokens, ast = _grammar_parse(text, 'operation', options)
    return _convert_operation(text, tokens, ast, options)


def _descendants(root):
    pending = [root]
    while pending:
        node = pending.pop()
        yield node
        pending.extend(reversed(node.children))


def _raw(text, tokens, node):
    return text[tokens[node.start].start:tokens[node.end - 1].end] if node.end > node.start else ''


def _typed_value(text, tokens, root, options):
    typed = next((node for node in _descendants(root) if node.type.startswith('typed_')), None)
    if typed is None:
        value_node = next(node for node in _descendants(root) if node.type == 'json_value')
        raw = _raw(text, tokens, value_node)
    elif typed.type == 'typed_text':
        start = tokens[typed.start + 1].end
        end = start
        while end < len(text) and text[end] not in '\r\n\u2028\u2029':
            end += 1
        value = text[start:end]
        mode = options.get('output_format', options.get('outputFormat'))
        if mode == 'typed_lines' and value.startswith(' '):
            value = value[1:]
        if mode in ('literal_line', 'end_marked_line'):
            if mode == 'end_marked_line':
                if not value.endswith('|'):
                    raise IntentError('Text value needs a final end marker')
                value = value[:-1]
            escapes = {'\\': '\\', 'n': '\n', 'r': '\r', 't': '\t'}
            if mode == 'literal_line':
                escapes.update({'s': ' ', '"': '"'})
            decoded, offset = [], 0
            while offset < len(value):
                char = value[offset]
                if char == '\\':
                    offset += 1
                    if offset == len(value) or value[offset] not in escapes:
                        raise IntentError('Unsupported text escape')
                    char = escapes[value[offset]]
                decoded.append(char)
                offset += 1
            value = ''.join(decoded)
        assert_json(value)
        return value
    else:
        raw = _raw(text, tokens, typed).split(':', 1)[1].strip()
        if typed.type == 'typed_null':
            return None
        if typed.type in ('typed_object', 'typed_list') and not raw:
            return {} if typed.type == 'typed_object' else []
        if typed.type == 'typed_number':
            if not re.fullmatch(r'[+-]?' + NUMBER[2:], raw):
                raise IntentError('Typed number must be one complete JSON number')
            raw = raw.removeprefix('+')
    value = _json(raw)
    if typed is not None and typed.type == 'typed_json' and isinstance(value, str):
        raise IntentError('json: does not accept a string value')
    decoder = options.get('_host_value_decoder')
    return decoder(raw) if decoder is not None else value


def _convert_operation(text, tokens, root, options=None):
    options = options or {}
    line = next((node for node in _descendants(root) if node.type in ('line_write', 'line_remove', 'line_transfer')), None)
    if line is None:
        result = _convert_components(_ast_components(tokens, root), options)
    else:
        nodes = list(_descendants(line))
        word = tokens[line.start].text.lower()
        op = _operations(options).get(word)
        if op is None:
            raise IntentError('Unsupported line operation')
        def path(role):
            node = next(n for n in nodes if n.type == role)
            slash = next((n for n in _descendants(node) if n.type == 'line_slash_path'), None)
            if slash is not None:
                raw = _raw(text, tokens, slash)
                if line.type == 'line_remove' or any(n.type in ('header_write', 'header_transfer') for n in nodes):
                    end = tokens[slash.end - 1].end
                    while end < len(text) and text[end] not in '\r\n\u2028\u2029' and re.fullmatch('[' + WS + ']', text[end]):
                        end += 1
                    raw = text[tokens[slash.start].start:end]
                decoder = options.get('_host_path_decoder')
                return decoder([Node('RAW_PATH', raw)], options) if decoder is not None else _value_path_tokens(raw)
            return path_tokens(lex_parse(_raw(text, tokens, node)), options)
        result = {'op': op}
        if line.type == 'line_transfer':
            result.update({'from': path('line_source'), 'to': path('line_destination')})
        else:
            result['path'] = path('line_target')
            if line.type == 'line_write':
                value_node = next(node for node in nodes if node.type == 'line_value')
                result['value'] = _typed_value(text, tokens, value_node, options)
        if word == 'add':
            result['semantic'] = 'literal_add'
        if word == 'change':
            if not any(node.type == 'typed_number' for node in nodes):
                raise IntentError('change requires number:')
            result['semantic'] = 'numeric_delta'
    if result['op'] == 'remove' and options.get('output_format', options.get('outputFormat')) == 'typed_lines':
        result['semantic'] = 'typed_remove'
    return result



def _convert_components(components, options=None):
    operations = _operations(options)
    fields, unlabeled = {}, []
    for items in components:
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
        word = str(_token_value(fields['op'][0])).lower()
        op = operations.get(word)
    else:
        positions = [i for i, x in enumerate(unlabeled) if x.type == 'WORD' and x.text.lower() in operations]
        if not positions:
            positions = [i for i, x in enumerate(unlabeled) if x.type == 'STRING' and str(_token_value(x)).lower() in operations]
        if len(positions) != 1:
            raise IntentError('Exactly one unambiguous operation type required')
        word = str(_token_value(unlabeled.pop(positions[0]))).lower()
        op = operations.get(word)
    if not op:
        raise IntentError('Unsupported or ambiguous operation alias')
    ir = {'op': op}
    if word == 'add':
        ir['semantic'] = 'literal_add'
    for key in ('path', 'from', 'to'):
        if key in fields:
            ir[key] = path_tokens(fields[key], options)
    if 'value' in fields:
        ir['value'] = _value_of(fields['value'], options)
    if op in ('append', 'update') and unlabeled:
        if 'path' in ir and 'value' not in ir:
            ir['value'] = _value_of(unlabeled, options)
            unlabeled.clear()
        elif 'path' not in ir and 'value' not in ir:
            candidates = {}
            for split in range(1, len(unlabeled)):
                for path, value in [(unlabeled[:split], unlabeled[split:]), (unlabeled[split:], unlabeled[:split])]:
                    try:
                        candidate = {'path': path_tokens(path, options), 'value': _value_of(value, options)}
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
    assert_json(text)
    if len(text.encode('utf-16-le', errors='surrogatepass')) // 2 > options.get('maxChars', 65536):
        raise IntentError('Intent text size limit exceeded')
    text, diagnostics = unwrap_fence(text)
    # Recognize text bodies before checking grouping: literal quotes/brackets
    # inside grammar-declared text are data, not program delimiters.
    repaired, repair = text, None
    try:
        tokens, ast = _grammar_parse(text, 'intent', options)
    except IntentError:
        repaired, repair = _repair_outer_wrapper(text, options)
        tokens, ast = _grammar_parse(repaired, 'intent', options)
    if repair:
        diagnostics.append({'code': 'OUTER_GROUP_RECOVERED', 'detail': repair})
    masked = list(repaired)
    for node in _descendants(ast):
        if node.type == 'typed_text':
            start = tokens[node.start + 1].end
            end = start
            while end < len(repaired) and repaired[end] not in '\r\n\u2028\u2029':
                masked[end] = ' '
                end += 1
    _repair_outer_wrapper(''.join(masked), options)
    def operations(node):
        records, pending = [], [node]
        while pending:
            current = pending.pop()
            if current.type == 'operation':
                records.append(_convert_operation(repaired, tokens, current, options))
                if len(records) > options.get('maxOperations', 256):
                    raise IntentError('Operation count limit exceeded')
            else:
                pending.extend(reversed(current.children))
        return records
    result = operations(ast)
    # The grammar owns structure. The bounded partition search is only a proof
    # that its ordered choice has not hidden another newline interpretation.
    pending = [ast]
    while pending:
        node = pending.pop()
        if node.type == 'op_list':
            explicit = ('line_write', 'line_remove', 'line_transfer')
            checks = []
            if not any(n.type in explicit for n in _descendants(node)):
                checks.append((' '.join(token.text for token in tokens[node.start:node.end]), operations(node)))
            else:
                # Explicit line signatures delimit old optional-field runs.
                # Retain ambiguity proofs inside mixed programs without ever
                # feeding literal text back through the old token projection.
                events, walk = [], list(reversed(node.children))
                while walk:
                    current = walk.pop()
                    if current.type in ('operation', 'op_group'):
                        events.append(current)
                    else:
                        walk.extend(reversed(current.children))
                run = []
                def flush():
                    if run:
                        start = tokens[run[0].start].start
                        end = tokens[run[-1].end - 1].end
                        checks.append((repaired[start:end], [operation for n in run for operation in operations(n)]))
                        run.clear()
                for event in events:
                    if event.type == 'op_group' or any(n.type in explicit for n in _descendants(event)):
                        flush()
                    else:
                        run.append(event)
                flush()
            for source, expected in checks:
                nodes = lex_parse(source)
                try:
                    alternate = parse_sequence(nodes, options)
                    if _key(alternate) != _key(expected):
                        raise IntentError('Ambiguous complete operation interpretations')
                except IntentError as error:
                    if 'limit exceeded' in str(error) or 'Ambiguous' in str(error):
                        raise
        pending.extend(reversed(node.children))
    return {'operations': result, 'diagnostics': diagnostics}


def parse_intent(text, options=None):
    return parse_intent_with_diagnostics(text, options)['operations']
