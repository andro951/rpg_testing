"""LPIL syntax and one-level transformations, independent of tasks and scores.

External data must be inserted as opaque text, not reparsed as LPIL. Delimiter
collisions inside arbitrary data remain a documented language limitation.
"""
import re
import copy
from dataclasses import dataclass, field


class SyntaxError(ValueError):
    pass


@dataclass
class Node:
    kind: str
    level: int = 0
    children: list = field(default_factory=list)
    name: str = ''
    newline: str = ''
    handwritten: bool = False


@dataclass
class Opaque:
    text: str


def parse(text, types=()):
    if not isinstance(text, str):
        raise TypeError('LPIL must be text.')
    allowed = set(types) | {'TITLE'}
    blocks = []

    def read(position, ending=None):
        result, ordinary = [], []

        def flush():
            if ordinary:
                result.append(''.join(ordinary))
                ordinary.clear()

        while position < len(text):
            if ending and text.startswith(ending, position):
                flush()
                return result, position + len(ending)
            if position == 0 or text[position - 1] == '\n':
                line = re.match(r'([^\r\n]*)(\r?\n|$)', text[position:])
                body, newline = line.groups()
                title = re.fullmatch(r'--- (.+) ---', body)
                deferred_title = re.fullmatch(r'\((\d+):TITLE:(.*):\)', body)
                block = re.fullmatch(r'<\((/?[A-Za-z_][A-Za-z_0-9]*)\)>', body)
                deferred_block = re.fullmatch(r'\((\d+)\((/?[A-Za-z_][A-Za-z_0-9]*)\)\)', body)
                if title or deferred_title:
                    flush()
                    level = int(deferred_title[1]) if deferred_title else 0
                    if deferred_title and level < 1:
                        raise SyntaxError('Deferred levels must be positive.')
                    result.append(Node('title', level, [deferred_title[2] if deferred_title else title[1]], newline=newline))
                    position += len(line[0])
                    continue
                if block or deferred_block:
                    flush()
                    level = int(deferred_block[1]) if deferred_block else 0
                    name = deferred_block[2] if deferred_block else block[1]
                    if deferred_block and level < 1:
                        raise SyntaxError('Deferred levels must be positive.')
                    if name.startswith('/'):
                        if not blocks or blocks.pop() != (level, name[1:]):
                            raise SyntaxError('Named block closing marker does not match: ' + name)
                    else:
                        blocks.append((level, name))
                    result.append(Node('block', level, name=name, newline=newline))
                    position += len(line[0])
                    continue
            if ending not in ('`', '|>', '|)') and (
                    text.startswith('<(', position) or re.match(r'\((-?\d+)\(/?[A-Za-z_]', text[position:])):
                raise SyntaxError('Named block markers must be complete lines with positive deferred levels.')
            opening = None
            if text.startswith('<|', position):
                opening = ('literal', 0, '<|', '|>', '', False)
            elif text.startswith('<{', position):
                opening = ('replacement', 0, '<{', '}>', '', False)
            elif text.startswith('<:', position):
                match = re.match(r'<:([A-Za-z_][A-Za-z_0-9]*):', text[position:])
                if not match:
                    raise SyntaxError('Invalid inline type at character ' + str(position))
                opening = ('generic', 0, match[0], ':>', match[1], False)
            elif text[position] == '`':
                opening = ('literal', 0, '`', '`', '', True)
            else:
                match = re.match(r'\((-?\d+)([|{:])', text[position:])
                if match:
                    level, symbol = int(match[1]), match[2]
                    if level < 1:
                        raise SyntaxError('Deferred levels must be positive.')
                    kind = {'|': 'literal', '{': 'replacement', ':': 'generic'}[symbol]
                    name, prefix = '', match[0]
                    if kind == 'generic':
                        generic = re.match(r'\((-?\d+):([A-Za-z_][A-Za-z_0-9]*):', text[position:])
                        if not generic:
                            raise SyntaxError('Invalid deferred inline type.')
                        name, prefix = generic[2], generic[0]
                    opening = (kind, level, prefix, {'|': '|)', '{': '})', ':': ':)'}[symbol], name, False)
            if opening:
                flush()
                kind, level, prefix, suffix, name, handwritten = opening
                if kind == 'generic' and name not in allowed:
                    raise SyntaxError('Define inline type before using it: ' + name)
                children, position = read(position + len(prefix), suffix)
                result.append(Node(kind, level, children, name, handwritten=handwritten))
            else:
                ordinary.append(text[position])
                position += 1
        if ending:
            raise SyntaxError('Missing closing marker: ' + ending)
        flush()
        return result, position

    nodes, _ = read(0)
    if blocks:
        raise SyntaxError('Unclosed named block: ' + blocks[-1][1])
    return nodes


def _render(nodes, shift=0, normalize=False, literal_depth=0, metadata=True, replacements=None):
    output = []
    for node in nodes:
        if isinstance(node, Opaque):
            output.append(node.text)
            continue
        if isinstance(node, str):
            output.append(node)
            continue
        level = max(0, node.level + shift)
        inside = literal_depth + (node.kind == 'literal')
        body = _render(node.children, shift, normalize, inside, metadata, replacements)
        if node.kind in ('title', 'block'):
            if not metadata and node.level == 0 and literal_depth == 0:
                continue
            if node.kind == 'title':
                value = '--- ' + body + ' ---' if level == 0 else f'({level}:TITLE:{body}:)'
            else:
                value = '<(' + node.name + ')>' if level == 0 else f'({level}({node.name}))'
            output.append(value + node.newline)
        elif node.kind == 'replacement':
            # Replacement data is returned verbatim and is never reparsed.
            if replacements is not None and node.level == 0 and literal_depth == 0:
                if body not in replacements:
                    raise ValueError('No replacement provided for: ' + body)
                output.append(replacements[body])
            else:
                output.append('<{' + body + '}>' if level == 0 else f'({level}{{{body}}})')
        elif node.kind == 'literal':
            backtick = level == 0 and ((node.handwritten and shift <= 0) or (normalize and literal_depth == 0))
            output.append('`' + body + '`' if backtick else ('<|' + body + '|>' if level == 0 else f'({level}|{body}|)'))
        elif node.kind == 'generic':
            if node.name == 'TITLE' and level == 0:
                output.append('--- ' + body + ' ---')
            else:
                output.append('<:' + node.name + ':' + body + ':>' if level == 0 else f'({level}:{node.name}:{body}:)')
    return ''.join(output)


def raise_level(text, types=()):
    return _render(parse(text, types), shift=1)


def lower_level(text, types=()):
    return _render(parse(text, types), shift=-1)


def normalize(text, types=()):
    return _render(parse(text, types), normalize=True)


def content(text, types=()):
    """Remove title and named-marker lines when reproducing their content."""
    return _render(parse(text, types), metadata=False)


def substitute(text, values, types=()):
    return _render(parse(text, types), replacements=values)


def replacements(text, types=()):
    found = []

    def walk(nodes, literal=False):
        for node in nodes:
            if isinstance(node, str):
                continue
            if node.kind == 'replacement' and node.level == 0 and not literal:
                found.append(_render(node.children))
            else:
                walk(node.children, literal or node.kind == 'literal')
    walk(parse(text, types))
    return found


def named_blocks(text, name, types=()):
    return [n for n in parse(text, types) if isinstance(n, Node) and n.kind == 'block' and n.level == 0 and n.name == name]


def shift_nodes(nodes, change):
    result = copy.deepcopy(nodes)
    for node in result:
        if isinstance(node, Node):
            handwritten = node.handwritten and node.level == 0 and change <= 0
            node.level = max(0, node.level + change)
            node.handwritten = handwritten
            node.children = shift_nodes(node.children, change)
    return result


def fill_nodes(nodes, values):
    """Insert parsed fragments or opaque data without rescanning inserted text."""
    result = []
    for node in nodes:
        if isinstance(node, Node) and node.kind == 'replacement' and node.level == 0:
            key = _render(node.children)
            if key not in values:
                raise ValueError('No outer-builder value for: ' + key)
            result.extend(copy.deepcopy(values[key]))
        else:
            result.append(copy.deepcopy(node))
    return result


def assemble(outer, fragments):
    """Outer slots are filled at their own level, then lowered exactly once.

Fragments are parsed LPIL node lists. Their external data is represented with
Opaque nodes, so marker-shaped data and handwritten text are never reparsed.
"""
    raised = {key: shift_nodes(value, 1) for key, value in fragments.items()}
    return _render(shift_nodes(fill_nodes(parse(outer), raised), -1), normalize=True)
