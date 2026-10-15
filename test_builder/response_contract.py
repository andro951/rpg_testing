"""Post-response method checks derived only from input, never sent as decoding constraints."""
from .builder import escape


def value_patch_schema(state, schema):
    # Paths are resolved against live state, not enumerated from the initial state.
    # This also accepts quoted property names and equivalent JSON number spellings.
    def operation(name, extra=None):
        properties={'op':{'const':name},'path':{'type':'string'}}
        properties.update(extra or {})
        return {'type':'object','required':list(properties),'properties':properties}
    return {'type':'array','items':{'oneOf':[
        operation('replace',{'value':{}}),operation('add',{'value':{}}),
        operation('remove'),operation('move',{'from':{'type':'string'}})]}}


def json_patch_schema(state):
    collections, fields = {}, []
    def walk(value, path=''):
        if isinstance(value, list):
            collections[path] = len(value)
            for index, item in enumerate(value):
                walk(item, path+'/'+str(index))
        elif isinstance(value, dict):
            for key, item in value.items():
                child = path+'/'+escape(key)
                if not isinstance(item,list):
                    fields.append(child)
                walk(item,child)
    walk(state)
    def enum(values):
        return {'enum':values} if values else {'not':{}}
    def operation(name, paths, extra=None):
        properties = {'op':{'const':name},'path':enum(paths)}
        properties.update(extra or {})
        return {'type':'object','required':list(properties),'properties':properties}
    appends = [target for path,n in collections.items() for target in (path+'/-',path+'/'+str(n))]
    elements = [path+'/'+str(i) for path,n in collections.items() for i in range(n)]
    choices = [operation('replace',fields,{'value':{}}),operation('add',appends,{'value':{}}),operation('remove',elements)]
    for source,n in collections.items():
        targets = [target for path,size in collections.items() if path!=source for target in (path+'/-',path+'/'+str(size))]
        choices.append(operation('move',targets,{'from':enum([source+'/'+str(i) for i in range(n)])}))
    return {'type':'array','items':{'oneOf':choices}}
