"""Faithful Ember record grammar on explicitly supported unchanged study tasks."""
import copy
import hashlib
import json
from .builder import ROOT
from .original_prompt import baseline
from .presentation import id_keyed_arrays
from workbench.domain import digest,validate_test
from workbench.ember_text import METHOD,apply,full_paths,typed
from workbench.presentation import render_source_text

def database_rules():
    return baseline()['database_rules'].replace(
        'Adding or removing an element of a collection is allowed.',
        'You may append a primitive value to an existing collection.')

def support_reason(fixture):
    task=fixture['task'];p=fixture['parameters']
    if task=='no_change':return None
    if task not in ('update_field','append_value'):
        if task.startswith('update_'):return 'Source protocol has no ID-based array-element selection; positional edits are outside this suite.'
        if task=='append_record':return 'A complete object append needs compound/positional construction, not one primitive typed value.'
        if task.startswith('remove_'):return 'Source remove nullifies a field; it does not delete a collection element.'
        if task.startswith(('move_','copy_')):return 'Source protocol has no Move or Copy operation; tasks are not replaced with other operations.'
        return 'Task is unsupported by the exact source protocol.'
    value=p['new_value'];path=p['property_path']if task=='update_field'else p['array_path']
    from .builder import at
    node=fixture['state']
    from workbench.scoring import pointer
    for part in pointer(path):
        if not isinstance(node,dict):return 'The source grammar does not provide the required ID-based collection selection.'
        if part in ('__proto__','prototype','constructor')or not part:return 'The source protocol rejects this object field path.'
        node=node[part]
    try:typed(value)
    except ValueError as exc:return str(exc)
    if task=='update_field'and isinstance(node,(dict,list)):return 'Compound field construction is outside this unchanged scalar-update adapter.'
    return None

def require_supported(fixture):
    reason=support_reason(fixture)
    if reason:raise ValueError('Unsupported Ember fixture '+fixture['id']+': '+reason)

def provenance():
    return json.loads((ROOT/'reference/ember_ai_response_text_v1.provenance.json').read_text(encoding='utf8'))

def reference(fixture):
    from .builder import oracle,equal
    require_supported(fixture)
    if fixture['task']=='no_change':raw='none'
    else:
        p=fixture['parameters'];path=p['property_path']if fixture['task']=='update_field'else p['array_path']
        raw=('set'if fixture['task']=='update_field'else'append')+': '+path+'\n'+typed(p['new_value'])
    expected=oracle(fixture)[1]
    if not equal(apply(fixture['state'],raw,fixture['schema']),expected):raise ValueError('Ember reference differs from unchanged semantic oracle')
    return raw,expected

def parts(fixture,presentation,templates=None):
    from . import builder
    require_supported(fixture);builder.oracle(fixture)
    if presentation not in builder.presentations(fixture):raise ValueError('Inapplicable presentation')
    if presentation=='full_paths':
        state='\n'.join(full_paths(fixture['state']))
        note='Each line shows an actual object-field path immediately followed by a colon and its JSON value. Collections remain complete JSON values. Empty arrays and objects remain visible.'
    elif presentation=='id_keyed_arrays':
        state=json.dumps(id_keyed_arrays(fixture['state'],fixture['schema']),ensure_ascii=False,indent=2,allow_nan=False)
        note=baseline()['presentation_notes'][presentation].replace('Select their elements using the path rules above.','Paths target the underlying object fields and collections.')
    else:state=render_source_text(fixture['state'],'raw_json');note=''
    guidance=('Database rules:\n'+database_rules()+'\n\n'+
              (ROOT/'methods/ember_text_v1.txt').read_text(encoding='utf8').strip()+
              '\n\nDatabase structure:\n'+builder.structure_text(fixture['schema']))
    return {'task_requirements':guidance,'presentation_notes':note,'current_state':state,
            'new_information':builder.task_text(fixture,ROOT/'templates',METHOD)}

def render(bindings):
    from .original_prompt import render as original_render
    return original_render(bindings)

def compile_test(fixture,reviews=None):
    from . import builder
    from .response_contract import value_patch_schema
    require_supported(fixture);builder.validate_fixture(fixture)
    bindings={mode:parts(fixture,mode)for mode in builder.presentations(fixture)}
    requests={mode:render(value)for mode,value in bindings.items()};proof=digest(requests)
    test_id=fixture['id']+'__'+METHOD;review=(reviews or{}).get(test_id,{})
    approved=all(review.get(role,{}).get('status')=='accepted'and review.get(role,{}).get('prompt_digest')==proof for role in ('assistant','isaac'))
    operation=builder.TASKS[fixture['task']][0];required={'update':['replace'],'append':['add'],'no_change':[]}[operation]
    source=provenance()
    test={'schema_version':2,'id':test_id,'name':fixture['name'],'description':'Exact Ember typed-line grammar with explicitly supported unchanged study tasks.',
          'workflow':'steps','enabled':approved,'instructions':baseline()['system'],'repetitions':fixture.get('repetitions',3),'timeout_seconds':120,
          'source':{'initial_state':copy.deepcopy(fixture['state'])},'state_schema':copy.deepcopy(fixture['schema']),
          'expected_state':builder.oracle(fixture)[1],
          'prompt_builder':{'version':'database-v3','task':fixture['task'],'operation':operation,'method':METHOD,'fixture':fixture['id'],
                            'prompt_digest':proof,'review_status':'accepted'if approved else'needs_review','source_contract':source,
                            'study_adapter':'object-field paths and primitive append only; no source grammar extensions',
                            'template_sha256':digest({'method':(ROOT/'methods/ember_text_v1.txt').read_text(encoding='utf8'),'source':source,'baseline_rules':database_rules()})},'variants':[]}
    for mode,request in requests.items():
        test['variants'].append({'id':mode,'prompt_style':'direct_text_v1','prompt_bindings':copy.deepcopy(bindings[mode]),
          'state_presentation':'raw_json','cache':'default','steps':[{'id':'patch','type':'generate','prompt':request[-1]['content'],
          'output':{'type':'text'},'sampling':{'temperature':0,'top_p':1,'seed':42}}],
          'result':{'step':'patch','representation':METHOD,'required_ops':required,
                    'response_schema':value_patch_schema(fixture['state'],fixture['schema'])}})
    validate_test(test);return test
