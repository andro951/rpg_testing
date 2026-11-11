"""Lossless input views. ID declarations select conversion keys, not schema text."""
import json
from evaluation.array_identity_map import IdentityMap
from intent_parser.patch import IntentError, assert_json
from workbench.dot_paths import scalar_text, encode_part
from workbench.scoring import equal


def id_field(array):
    """Data-only named-table convention, never identity metadata or a schema."""
    if not array or all(not isinstance(v, (dict, list)) for v in array):
        return None
    if not all(isinstance(v, dict) for v in array):
        raise IntentError('ID-dependent presentation requires homogeneous arrays')
    common = set.intersection(*(set(v) for v in array))
    candidates = [k for k in sorted(common) if (k == 'id' or k.endswith('_id'))
                  and all(not isinstance(v[k], (dict, list)) for v in array)
                  and not any(equal(a[k], b[k]) for i, a in enumerate(array) for b in array[i + 1:])]
    if len(candidates) != 1:
        raise IntentError('ID-dependent presentation requires one unambiguous unique id or *_id field in starting data; use normal_json')
    return candidates[0]


def identity(element, array):
    field = id_field(array)
    return element[field] if field is not None else element


def validate_display(value):
    """Check named-table display requirements without identity metadata."""
    if isinstance(value, dict):
        for child in value.values():validate_display(child)
    elif isinstance(value, list):
        ids = [identity(child, value) for child in value]
        if len({scalar_text(item) for item in ids}) != len(ids):
            raise IntentError('Array IDs collide in the presentation')
        for child in value:validate_display(child)

SERIALIZERS = ('normal_json','id_keyed_arrays','full_paths','named_tables')

def has_array(value):
    return isinstance(value,list) or isinstance(value,dict) and any(has_array(v) for v in value.values())

def keyed(value,array_identities=None):
    """Use only declared array identities; retain all fields and container types."""
    declarations=IdentityMap(array_identities)
    declarations.validate(value)
    def walk(node,path):
        # Tag BOTH container kinds: user data can contain any field, even "$array".
        if isinstance(node,list):
            field=declarations.field(node,path)
            return {'$array':{scalar_text(v[field] if field is not None else v):walk(v,path+(None,)) for v in node}}
        if isinstance(node,dict):return {'$object':{k:walk(v,path+(k,)) for k,v in node.items()}}
        return node
    return walk(value,())

def full_paths(value,array_identities=None,path=''):
    """Use declared identities for array path parts, never positional indices."""
    declarations=IdentityMap(array_identities)
    declarations.validate(value)
    def walk(node,data_path,display_path):
        display=display_path or '<root>'
        if isinstance(node,dict) and node:
            lines=[display+': <object>']
            for k,v in node.items():
                part=encode_part(k)
                lines.extend(walk(v,data_path+(k,),display_path+'.'+part if display_path else part))
            return lines
        if isinstance(node,list) and node:
            lines=[display+': <array>']
            field=declarations.field(node,data_path)
            for v in node:
                part=encode_part(scalar_text(v[field] if field is not None else v))
                lines.extend(walk(v,data_path+(None,),display_path+'.'+part if display_path else part))
            return lines
        return [display+': '+json.dumps(node,ensure_ascii=False,allow_nan=False,separators=(',',':'))]
    return walk(value,(),path)

def named_tables(value):
    """Python literal cells preserve types, nested structures and whitespace."""
    lines=[]
    def cell(v):return repr(v).replace('|','\\x7c')
    def walk(node,path):
        title=' / '.join(repr(p)for p in path)or'<root>'
        if isinstance(node,dict):
            lines.extend(['Object '+title+' (single object, not an array)','field | value'])
            for k,v in node.items():
                if isinstance(v,(dict,list)):lines.append(cell(k)+' | see '+('table'if isinstance(v,list)else'object')+' below')
                else:lines.append(cell(k)+' | '+cell(v))
            if not node:lines.append('(empty object)')
            lines.append('')
            for k,v in node.items():
                if isinstance(v,(dict,list)):walk(v,path+[k])
        elif isinstance(node,list):
            lines.append('Table '+title+' (array)')
            if not node:lines.append('(empty array)')
            elif isinstance(node[0],dict):
                label=id_field(node)
                columns=list(dict.fromkeys(k for row in node for k in row))
                lines.append('ID field: '+repr(label))
                lines.append(' | '.join(cell(k)for k in columns))
                for row in node:lines.append(' | '.join(cell(row[k])if k in row else '<absent>'for k in columns))
            else:
                lines.append('unique value / ID')
                lines.extend(cell(x)for x in node)
            lines.append('')
        else:lines.append('Value '+title+': '+cell(node))
    walk(value,[])
    return '\n'.join(lines).rstrip('\n')

def render(value,serializer,array_identities=None):
    assert_json(value)
    if serializer=='normal_json':return json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)
    if serializer=='id_keyed_arrays':return json.dumps(keyed(value,array_identities),ensure_ascii=False,indent=2,allow_nan=False)
    if serializer=='full_paths':return '\n'.join(full_paths(value,array_identities))
    if serializer=='named_tables':
        validate_display(value)
        return named_tables(value)
    raise ValueError('Unknown input serializer: '+str(serializer))
