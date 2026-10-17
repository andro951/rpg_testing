"""Current reviewed starting cases and exact saved-result handoffs."""
from pathlib import Path
from urllib.parse import urlencode
from workbench.domain import ResultStore, code_fingerprint, digest, experiment_spec, read_json, safe_id
from workbench.judgements import JudgementStore
from . import templates
from .catalog import registration


def targets(root):
    root=Path(root)
    data=templates.catalog()
    rejected=JudgementStore(root).read()['entries']
    result=[]
    for path in sorted((root/'test_specs').glob('*.json')):
        test=read_json(path)
        if not test.get('enabled',True):continue
        for variant in test['variants']:
            if not variant.get('enabled',True) or variant.get('result',{}).get('representation') not in ('json_patch','value_patch'):continue
            key=test['id']+'/'+variant['id']
            entry=data['variants'].get(key)
            if not entry or not entry['objective_optimization_eligible']:continue
            try:registration(test,variant,data)
            except ValueError:continue
            proof=digest(experiment_spec(test,variant))
            if rejected.get(proof,{}).get('blocked'):continue
            result.append({'test_id':test['id'],'variant_id':variant['id'],'definition_id':proof,
                'name':test.get('name',test['id']),'presentation':entry['existing_groups']['input_presentation'],
                'task_type':entry['task_family'],'repetitions':test.get('repetitions',1)})
    return result


def validate_target(root, target):
    if not isinstance(target,dict) or set(target)-{'test_id','variant_id','definition_id'} or not {'test_id','variant_id'}<=set(target):
        raise ValueError('Choose a starting test and presentation.')
    if any(not isinstance(value,str) or not value for value in target.values()):
        raise ValueError('Invalid starting test selection.')
    found=next((item for item in targets(root) if item['test_id']==target['test_id'] and item['variant_id']==target['variant_id']),None)
    if found is None:raise ValueError('The starting test is unavailable, disabled, rejected or no longer reviewed.')
    if target.get('definition_id') and target['definition_id']!=found['definition_id']:
        raise ValueError('This result uses an older test definition. Select the current test explicitly to start a new experiment.')
    return found


def from_result(root, model_id, case_id):
    root=Path(root)
    record=ResultStore(root/'results').read(ResultStore(root/'results').path(safe_id(model_id),safe_id(case_id)))
    if record.get('model_id')!=model_id or record.get('case_id')!=case_id:
        raise ValueError('Saved result identity does not match the requested result.')
    if not record.get('test_definition') or not record.get('variant_definition'):
        raise ValueError('The saved result does not contain its exact test definition.')
    if record.get('provenance',{}).get('workflow_code')!=code_fingerprint():
        raise ValueError('This result uses an older benchmark workflow. Select a current test explicitly in Prompt Optimization.')
    target=validate_target(root,{'test_id':record['test_id'],'variant_id':record['variant_id'],
        'definition_id':digest(experiment_spec(record['test_definition'],record['variant_definition']))})
    return {'target':target,'origin_model_id':model_id,'source_result':{'model_id':model_id,'case_id':case_id}},record


def fragment(selection):
    target=selection['target']
    return urlencode({'page':'optimization',**{key:target[key] for key in ('test_id','variant_id','definition_id')},
        'origin_model_id':selection['origin_model_id'],'source_result_id':selection['source_result']['case_id']})
