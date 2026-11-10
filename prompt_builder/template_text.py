"""File-owned prompt text, with strict placeholder expansion and no code literals."""
from pathlib import Path
from string import Template
import re

COMMENT = re.compile(r'\{#.*?#\}(?:\r?\n)?', re.S)

def read_text(path):
    # Keep every meaningful byte, including trailing task/value whitespace.
    return Path(path).read_text(encoding='utf-8')

def fill(path, values):
    try:
        return Template(COMMENT.sub('',read_text(path))).substitute(values)
    except (KeyError, ValueError) as exc:
        raise ValueError(f'Invalid placeholder in {path}: {exc}') from exc

def assemble(root, *, input_format, output_format, current_data, task, schema_description=None, with_parts=False):
    root = Path(root)
    common = root/'common'
    output = root/'output_format'/output_format
    note = read_text(root/'input_format'/input_format/'notes.txt')
    values = {'current_data':current_data, 'task':task, 'input_notes':note,
              'input_note_block':fill(common/'layout/input-note.txt', {'input_notes':note}) if note else ''}
    # Optional placeholders are sourced only from explicit files. Unknown placeholders fail.
    for key, path in {'database_rules':common/'database_rules.txt',
                      'allowed_changes':common/'allowed_changes.txt',
                      'path_rules':output/'path_rules.txt',
                      'output_format':output/'format.txt',
                      'shared_rules':output/'shared_rules.txt',
                      'instructions':output/'instructions.txt',
                      'format_database_rules':output/'database_rules.txt'}.items():
        if path.is_file(): values[key] = read_text(path)
    if schema_description is not None:values['schema_description']=schema_description
    layout = output/'user.txt'
    if not layout.exists():layout=common/'layout/user.txt'
    messages = [{'role':'system','content':fill(common/'layout/system.txt',values)},
                {'role':'user','content':fill(layout,values)}]
    if not with_parts:return messages
    names = [m.group('named') or m.group('braced') for m in Template.pattern.finditer(COMMENT.sub('',read_text(layout)))]
    guidance_keys = {'database_rules','allowed_changes','path_rules','output_format','shared_rules','instructions','format_database_rules'}
    guidance = '\n\n'.join([messages[0]['content'],*(values[name] for name in names if name in guidance_keys)]) if messages[0]['content'] else '\n\n'.join(values[name] for name in names if name in guidance_keys)
    bindings = {'task_requirements':guidance,'presentation_notes':note,'current_state':current_data,'new_information':task}
    return messages, bindings
