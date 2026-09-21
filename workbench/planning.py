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


def pending_plan(models, tests, target, store):
    """No model discovery here: completed work must not require installed weights."""
    validate_catalog(models)
    groups=[];complete=0;excluded=[];unassigned=[]
    for model in models:
        if model.get('enabled', True) is False:
            continue
        if model.get('required_vram_gb') is None:
            unassigned.append(model['id']);continue
        reason=eligibility(model['required_vram_gb'], target['vram_gb'])
        if reason is None:
            excluded.append(model['id']);continue
        jobs=[];done=0
        for test in tests:
            for variant in test['variants']:
                if not variant.get('enabled',True):continue
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
            'target':copy.deepcopy(target)}


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
