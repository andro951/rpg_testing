"""Synthetic response examples for tests, never used to construct model prompts."""
import json
from evaluation.schema_free_intent import resolve, identity, apply_patch
from workbench.ember_text import typed


def slash_path(state,path):
    _,parts=resolve(state,path);out=[]
    for part in parts:
        if isinstance(state,list):
            element=state[int(part)]
            out.append(json.dumps(identity(element,state),ensure_ascii=False));state=element
        else:
            out.append(part.replace('~','~0').replace('/','~1'));state=state[part]
    return '/'+('/'.join(out)) if parts else ''


def encode(initial,patch,output_format):
    """Encode a known reference in its actual reader's syntax, preserving values."""
    if output_format in ('json_dot','free_format'):return json.dumps(patch,ensure_ascii=False)
    if not patch:return '[]'if output_format=='json_slash'else'none'
    lines=[];operations=[];state=initial
    for op in patch:
        verb={'replace':'set','add':'append','remove':'remove'}[op['op']]
        path=op['path'];value=op.get('value');raw=json.dumps(value,ensure_ascii=False)
        if output_format=='json_slash':operations.append({**op,'path':slash_path(state,path)})
        elif output_format=='path_list':lines.append(verb+' ['+', '.join(path.split('.'))+']'+(': '+raw if verb!='remove'else''))
        elif output_format=='two_line_text':
            lines.append(verb+': '+path)
            if verb!='remove':lines.append('value: '+raw)
        elif output_format=='typed_lines':lines.extend([verb+': '+slash_path(state,path),typed(value)])
        elif output_format in ('literal_line','end_marked_line'):
            if verb=='remove':lines.append(verb+' '+path)
            else:
                if isinstance(value,str):
                    text=value.replace('\\','\\\\').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')
                    if output_format=='end_marked_line':text+='|'
                    else:
                        trailing=len(text)-len(text.rstrip(' '))
                        if trailing:text=text[:-trailing]+'\\s'*trailing
                    payload='text:'+text
                else:payload='json:'+raw
                lines.append(verb+' '+path+': '+payload)
        else:raise ValueError('Unknown reference output format: '+output_format)
        state=apply_patch(state,[op])['final_state']
    return json.dumps(operations,ensure_ascii=False)if output_format=='json_slash'else'\n'.join(lines)
