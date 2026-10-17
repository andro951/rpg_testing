"""Original930 direct prompts, reconstructed from exact pre-revision messages.

No promoted normal_prompt configuration or OPRO guidance is consulted.
"""
import copy
import json
from functools import lru_cache
from .builder import ROOT
from workbench.domain import digest, read_json, validate_test

METHODS = ('original_value_patch_v1', 'dot_patch_v1')


@lru_cache(maxsize=1)
def baseline():
    return read_json(ROOT/'original_prompt_v1.json')


def parts(fixture, presentation, method, templates):
    from . import builder
    from .presentation import full_paths, id_keyed_arrays
    from workbench.presentation import render_source_text
    builder.oracle(fixture, method)
    if presentation not in builder.presentations(fixture):
        raise ValueError('Unknown operation method or inapplicable presentation')
    if method == 'dot_patch_v1':
        from workbench.dot_paths import validate
        validate(fixture['state'], fixture['schema'])
    data = baseline()
    state = ('\n'.join(full_paths(fixture['state'], fixture['schema'])) if presentation == 'full_paths' else
             json.dumps(id_keyed_arrays(fixture['state'], fixture['schema']), ensure_ascii=False, indent=2, allow_nan=False)
             if presentation == 'id_keyed_arrays' else render_source_text(fixture['state'], 'raw_json'))
    guidance = ('Database rules:\n' + data['database_rules'] + '\n\n' +
                (ROOT/builder.METHODS[method]['file']).read_text(encoding='utf-8').strip() +
                '\n\nDatabase structure:\n' + builder.structure_text(fixture['schema']))
    note = data['presentation_notes'][presentation]
    if method == 'dot_patch_v1' and presentation == 'full_paths':
        note = note.replace('The path is written exactly as it selects that value, using the rules above.',
                            'Displayed paths retain the original slash form. For output operations, use the dot-path rules above and the database structure to select the same field or element.')
    return {'task_requirements': guidance, 'presentation_notes': note,
            'current_state': state, 'new_information': builder.task_text(fixture, templates, method)}


def render(parts):
    text = parts['task_requirements']
    if parts['presentation_notes']:
        text += '\n\nInput presentation:\n' + parts['presentation_notes']
    text += '\n\nCurrent data:\n' + parts['current_state'] + '\n\nTask:\n' + parts['new_information']
    return [{'role':'system','content':baseline()['system']}, {'role':'user','content':text}]


def compile_test(fixture, reviews, method):
    from . import builder
    from .response_contract import value_patch_schema
    bindings = {mode:parts(fixture, mode, method, ROOT/'templates') for mode in builder.presentations(fixture)}
    requests = {mode:render(value) for mode,value in bindings.items()}
    proof, test_id = digest(requests), fixture['id'] + '__' + method
    review = (reviews or {}).get(test_id,{})
    approved = all(review.get(role,{}).get('prompt_digest') == proof and review.get(role,{}).get('status') == 'accepted'
                   for role in ('assistant','isaac'))
    operation = builder.TASKS[fixture['task']][0]
    token = builder.METHODS[method]['operations'][operation]
    contract = value_patch_schema(fixture['state'], fixture['schema'])
    if method == 'dot_patch_v1':
        contract = {**contract, 'x-path-format':'dot_patch_v1',
                    'description':'JSON operation objects; only path/from strings use dot_patch_v1 resolution and path-only quote normalization.'}
    provenance = {'source':'original930','original_manifest_sha256':baseline()['original_manifest_sha256'],
                  'definitions_file_sha256':baseline()['definitions_file_sha256'],
                  'original_system':'empty','opro_guidance':False,
                  'noop_fixture':'current unrelated-information task; not the original redundant assignment'}
    test = {'schema_version':2,'id':test_id,'name':fixture['name'],
            'description':'Original930 prompt baseline with '+builder.METHODS[method]['name']+'.',
            'workflow':'steps','enabled':approved,'instructions':baseline()['system'],
            'repetitions':fixture.get('repetitions',3),'timeout_seconds':120,
            'source':{'initial_state':copy.deepcopy(fixture['state'])},'state_schema':copy.deepcopy(fixture['schema']),
            'expected_state':builder.oracle(fixture,method)[1],
            'prompt_builder':{'version':'database-v3','task':fixture['task'],'operation':operation,'method':method,
                              'fixture':fixture['id'],'prompt_digest':proof,'review_status':'accepted'if approved else'needs_review',
                              'baseline_provenance':provenance,
                              'template_sha256':digest({'method':(ROOT/builder.METHODS[method]['file']).read_text(encoding='utf-8'),
                                                        'baseline':baseline(),'task':(ROOT/'templates'/(builder.TASK_TEMPLATES[fixture['task']]+'.txt')).read_text(encoding='utf-8')})},'variants':[]}
    for mode,request in requests.items():
        test['variants'].append({'id':mode,'prompt_style':'direct_text_v1','prompt_bindings':copy.deepcopy(bindings[mode]),
          'state_presentation':'raw_json','cache':'default',
          'steps':[{'id':'patch','type':'generate','prompt':request[-1]['content'],'output':{'type':'text'},
                    'sampling':{'temperature':0,'top_p':1,'seed':42}}],
          'result':{'step':'patch','representation':builder.METHODS[method]['representation'],
                    'required_ops':[token]if token else[],'response_schema':copy.deepcopy(contract)}})
    validate_test(test)
    return test
