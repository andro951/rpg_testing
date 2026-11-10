"""Synthetic response examples for tests, never used to construct model prompts."""
import json
from evaluation.array_identities_intent import resolve, identity, apply_patch
from evaluation.typed_lines import typed


def slash_path(state,path,array_identities):
    _,parts=resolve(state,path,array_identities);out=[];template=[]
    for part in parts:
        if isinstance(state,list):
            element=state[int(part)]
            out.append(json.dumps(identity(element,state,array_identities,template),ensure_ascii=False));state=element;template.append(None)
        else:
            out.append(part.replace('~','~0').replace('/','~1'));state=state[part];template.append(part)
    return '/'+('/'.join(out)) if parts else ''


def encode(initial,patch,output_format,array_identities):
    """Encode a known reference in its actual reader's syntax, preserving values."""
    if output_format in ('json_dot','free_format'):return json.dumps(patch,ensure_ascii=False)
    if not patch:return '[]'if output_format=='json_slash'else'none'
    lines=[];operations=[];state=initial
    for op in patch:
        verb={'replace':'set','add':'append','remove':'remove'}[op['op']]
        path=op['path'];value=op.get('value');raw=json.dumps(value,ensure_ascii=False)
        if output_format=='json_slash':operations.append({**op,'path':slash_path(state,path,array_identities)})
        elif output_format=='path_list':lines.append(verb+' ['+', '.join(path.split('.'))+']'+(': '+raw if verb!='remove'else''))
        elif output_format=='two_line_text':
            lines.append(verb+': '+path)
            if verb!='remove':lines.append('value: '+raw)
        elif output_format=='typed_lines':
            lines.append(verb+': '+slash_path(state,path,array_identities))
            if verb!='remove':lines.append(typed(value))
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
        state=apply_patch(state,[op],array_identities)['final_state']
    return json.dumps(operations,ensure_ascii=False)if output_format=='json_slash'else'\n'.join(lines)
