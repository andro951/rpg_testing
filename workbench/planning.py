"""One pending-work planner, shared by preparation, live preflight and execution."""
from __future__ import annotations
import copy
from .domain import case_id, eligibility, safe_id, TIERS
from .execution_policy import fallback_id


def validate_catalog(models):
    if not isinstance(models, list):
        raise ValueError('models.json must contain only a JSON array of model variants')
    seen = set()
    for model in models:
        mid = safe_id(model['id'])
        if mid in seen:
            raise ValueError('Duplicate model ID: ' + mid)
        seen.add(mid)
        if 'min_vram_gb' in model:
            raise ValueError('Use required_vram_gb')
        if model.get('required_vram_gb') is not None and (type(model['required_vram_gb']) is not int or model['required_vram_gb'] not in TIERS):
            raise ValueError('Invalid assigned VRAM tier: ' + mid)
        files = model.get('files', [])
        if not files or len(files) != len(set(files)):
            raise ValueError('Model needs unique GGUF filenames: ' + mid)
        for f in files:
            if not isinstance(f, str) or not f.endswith('.gguf') or '/' in f or '\\' in f or f in ('.','..'):
                raise ValueError('Unsafe model filename')
        hashes = model.get('sha256', {})
        if hashes and set(hashes) != set(files):
            raise ValueError('Artifact fingerprints must cover every model shard')
        if any(not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h) for h in hashes.values()):
            raise ValueError('Invalid SHA-256 fingerprint')


def normalize_selection(selection):
    """A run filter, never an experimental setting or an implicit request for all models."""
    if selection is None:
        return None
    allowed={'model_id','all_models','test_id','test_ids','variant_id'}
    if not isinstance(selection,dict) or not selection or set(selection)-allowed:
        raise ValueError('Selection needs an explicit model scope and optional test / variant scope')
    has_model='model_id' in selection
    has_all='all_models' in selection
    if has_model==has_all:
        raise ValueError('Choose exactly one model scope: model_id or all_models')
    if has_all and selection['all_models'] is not True:
        raise ValueError('all_models must be true when selected')
    if 'test_id' in selection and 'test_ids' in selection:
        raise ValueError('Choose either one test_id or a test_ids subset, not both')
    if 'variant_id' in selection and 'test_id' not in selection:
        raise ValueError('Choose one test before choosing a variant')
    if has_all and 'test_id' not in selection:
        raise ValueError('All-model targeted runs require one explicit test_id')
    normalized={'model_id':safe_id(selection['model_id'])} if has_model else {'all_models':True}
    if 'test_id' in selection:normalized['test_id']=safe_id(selection['test_id'])
    if 'variant_id' in selection:normalized['variant_id']=safe_id(selection['variant_id'])
    if 'test_ids' in selection:
        values=selection['test_ids']
        if not isinstance(values,list) or not values:
            raise ValueError('Choose at least one test')
        ids=[safe_id(value) for value in values]
        if len(ids)!=len(set(ids)):
            raise ValueError('Selected tests must be unique')
        normalized['test_ids']=sorted(ids)
    return normalized


def validate_selection(selection, models, tests):
    selection = normalize_selection(selection)
    if selection is None:
        return None
    if 'model_id' in selection:
        if not any(m['id']==selection['model_id'] and m.get('enabled',True) for m in models):
            raise ValueError('Selected model is unavailable or disabled. Rescan and assign it in Installed models.')
    elif not any(m.get('enabled',True) for m in models):
        raise ValueError('No enabled models are available. Rescan and assign models in Installed models.')
    selected_ids=[selection['test_id']] if 'test_id' in selection else selection.get('test_ids',[])
    for test_id in selected_ids:
        test=next((t for t in tests if t['id']==test_id and t.get('enabled',True)),None)
        if test is None:
            raise ValueError('Selected test is unavailable or disabled. Refresh the test choices.')
        variants=[v for v in test['variants'] if v.get('enabled',True)]
        if not variants or ('variant_id' in selection and not any(v['id']==selection['variant_id'] for v in variants)):
            raise ValueError('Selected test has no matching enabled variant. Refresh the test choices.')
    return selection


def pending_plan(models, tests, target, store, selection=None):
    """No model discovery here: completed work must not require installed weights."""
    validate_catalog(models)
    selection=validate_selection(selection,models,tests)
    groups=[];complete=0;excluded=[];unassigned=[]
    for model in models:
        if selection and 'model_id' in selection and model['id']!=selection['model_id']:continue
        if model.get('enabled', True) is False:
            continue
        if model.get('required_vram_gb') is None:
            unassigned.append(model['id']);continue
        reason=eligibility(model['required_vram_gb'], target['vram_gb'])
        if reason is None:
            excluded.append(model['id']);continue
        jobs=[];done=0
        for test in tests:
            if selection and 'test_id' in selection and selection['test_id']!=test['id']:continue
            if selection and 'test_ids' in selection and test['id'] not in selection['test_ids']:continue
            for variant in test['variants']:
                if not variant.get('enabled',True):continue
                if selection and selection.get('variant_id',variant['id'])!=variant['id']:continue
                for repetition in range(test.get('repetitions',1)):
                    cid=case_id(model,test,variant,repetition,target)
                    if store.done(model['id'],cid):
                        existing=store.read(store.path(model['id'],cid))
                        if existing['status']=='skipped' and existing.get('recovery_eligible') and not store.done(model['id'],fallback_id(cid)):
                            jobs.append({'case_id':cid,'model_id':model['id'],'test':test,'variant':variant,'repetition':repetition,'recovery_only':True})
                        else:done+=1;complete+=1
                    else:
                        jobs.append({'case_id':cid,'model_id':model['id'],'test':test,'variant':variant,'repetition':repetition})
        groups.append({'model':copy.deepcopy(model),'reason':reason,'jobs':jobs,'complete':done})
    return {'groups':groups,'pending':sum(len(g['jobs']) for g in groups),'complete':complete,
            'model_loads':sum(bool(g['jobs']) for g in groups),'excluded':excluded,'unassigned':unassigned,
            'target':copy.deepcopy(target),'selection':copy.deepcopy(selection)}


def public_plan(plan):
    return {**{k:v for k,v in plan.items() if k!='groups'},'groups':[
        {'model_id':g['model']['id'],'reason':g['reason'],'pending':len(g['jobs']),
         'complete':g['complete'],'context':g.get('context')} for g in plan['groups']]}


def requirements(group):
    cache=False;schema=False
    def walk(steps):
        nonlocal schema
        for step in steps:
            if step['type']=='loop':walk(step['steps'])
            elif step.get('output',{}).get('type','text')!='text':schema=True
    for job in group['jobs']:
        cache|=job['variant'].get('cache','default')!='default'
        walk(job['variant']['steps'])
    return {'cache':cache,'schema':schema}
