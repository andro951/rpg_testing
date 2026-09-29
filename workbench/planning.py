"""One pending-work planner, shared by preparation, live preflight and execution."""
from __future__ import annotations
import copy
from .domain import case_id, code_fingerprint, eligibility, experiment_spec, safe_id, TIERS
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


def _timeout_neutral_spec(test, variant):
    """Experimental identity with only the watchdog duration removed."""
    spec=copy.deepcopy(experiment_spec(test,variant))
    spec['test'].pop('timeout_seconds',None)
    return spec


def stable_backend_version(value):
    """Strip volatile llama-server log timing while retaining build identity."""
    if not isinstance(value,str):
        return value
    lines=[line.strip() for line in value.splitlines() if line.strip()]
    stable=[line for line in lines if line.lower().startswith('version:') or line.lower().startswith('built with ')]
    return '\n'.join(stable) if stable else value.strip()


def _stable_target(target):
    if not isinstance(target,dict):
        return target
    normalized=copy.deepcopy(target)
    if 'backend_version' in normalized:
        normalized['backend_version']=stable_backend_version(normalized['backend_version'])
    return normalized


def _model_history(store, model_id):
    """Best-effort history for timeout compatibility; unrelated corrupt files stay isolated."""
    records=[]
    directory=store.root / model_id
    if not directory.exists():
        return records
    for path in sorted(directory.glob('*.json')):
        try:
            records.append(store.read(path))
        except (OSError,ValueError):
            continue
    return records


def _historical_timeout_result(records, model, test, variant, repetition, target, workflow_code):
    """Reuse old results only when the sole experiment change is timeout_seconds.

    Historical case IDs cannot be regenerated safely after timeout changes because
    the ID itself includes the timeout. Compare the persisted identity inputs
    directly instead: workflow fingerprint, model artifact, target, and the
    timeout-neutral test/variant definition.
    """
    wanted=_timeout_neutral_spec(test,variant)
    artifact_pin=model.get('artifact_identity') or model.get('sha256',{})
    matches=[]
    for record in records:
        if (record.get('model_id')!=model['id'] or record.get('test_id')!=test['id']
                or record.get('variant_id')!=variant['id'] or record.get('repetition')!=repetition
                or _stable_target(record.get('target'))!=_stable_target(target)
                or record.get('execution_class','full_gpu')!='full_gpu'):
            continue
        provenance=record.get('provenance')
        if not isinstance(provenance,dict) or provenance.get('workflow_code')!=workflow_code:
            continue
        record_artifact=record.get('artifact_identity') or record.get('artifact_hashes',{})
        if record_artifact!=artifact_pin:
            continue
        old_test=record.get('test_definition');old_variant=record.get('variant_definition')
        if not isinstance(old_test,dict) or not isinstance(old_variant,dict):
            continue
        try:
            if _timeout_neutral_spec(old_test,old_variant)!=wanted:
                continue
        except (KeyError,TypeError,ValueError):
            continue
        if record.get('status') in ('completed','skipped'):
            matches.append(record)
    if not matches:
        return None

    def timed_out(record):
        return bool(record.get('timed_out')) or record.get('reason')=='case_timeout'

    # Any successful/non-timeout completion remains complete after a timeout-only bump.
    non_timeout=[record for record in matches if not timed_out(record)]
    if non_timeout:
        return {'done':True,'record':max(non_timeout,key=lambda r:str(r.get('finished_at','')))}

    def timeout(record):
        value=record.get('timeout_seconds')
        if type(value) not in (int,float):
            value=record.get('test_definition',{}).get('timeout_seconds',0)
        return value if type(value) in (int,float) else 0

    latest=max(matches,key=lambda r:(timeout(r),str(r.get('finished_at',''))))
    # A timed-out case becomes pending only when it is being given a larger watchdog.
    return {'done':test['timeout_seconds']<=timeout(latest),'record':latest}


def pending_plan(models, tests, target, store, selection=None):
    """No model discovery here: completed work must not require installed weights."""
    validate_catalog(models)
    selection=validate_selection(selection,models,tests)
    groups=[];complete=0;excluded=[];unassigned=[];history={};workflow_code=code_fingerprint()
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
                        if model['id'] not in history:
                            history[model['id']]=_model_history(store,model['id'])
                        prior=_historical_timeout_result(history[model['id']],model,test,variant,repetition,target,workflow_code)
                        if prior and prior['done']:
                            done+=1;complete+=1
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
