"""Durable success -> normal promotion -> full configured-worker coverage.

Saved observations remain authoritative; orchestration status never invents results.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import uuid
from workbench.domain import digest, read_json, write_json, ResultStore, experiment_spec, code_fingerprint
from workbench.judgements import load_tests, review_lock
from workbench.locking import HostLock
from workbench.workflows import messages, Cancelled
from .storage import Store

APPROVAL = 'Standing user authorization: successful built-in OPRO promotes reviewed guidance and runs full coverage on every configured model, including Perchance and one Unity job per model.'


def scope(root):
    tests = load_tests(root / 'test_specs')
    return {'workflow': code_fingerprint(), 'definitions': [
        {'test_id': t['id'], 'variant_id': v['id'], 'definition': digest(experiment_spec(t, v)),
         'messages': digest(messages(t, v['steps'][0], {}, v)), 'repetitions': t.get('repetitions', 1)}
        for t in tests for v in t['variants'] if v.get('enabled', True)]}


def directory(root, key):
    from workbench.domain import safe_id
    return Path(root) / 'coverage_results' / safe_id(key)


def read_state(root, key):
    state=Store(root).read(directory(root, key) / 'state.json')
    stale=False
    for worker in state.get('workers',[]):
        for row in worker.get('rows',[]):
            for evidence in row.get('evidence',[]):
                path=Path(evidence['path'])
                if not path.exists() or path.stat().st_size!=evidence['bytes'] or path.stat().st_mtime_ns!=evidence['mtime_ns']:
                    row.update(status='stale',reason='Saved raw evidence is missing or changed; resume to audit it.')
                    worker['status']='partial';stale=True;break
    if stale:state.update(status='partial',message='Saved raw evidence is missing or changed; full coverage needs an audit.')
    return state


def save(root, state):
    Store(root).write(directory(root, state['id']) / 'state.json', state)


def configured(app):
    models = [m['id'] for m in app.catalog() if m.get('enabled', True)]
    workers = [{'id': 'desktop', 'kind': 'local', 'models': models + ([] if app.demo else ['perchance-text-generator'])}]
    path = app.data / 'coverage-workers.json'
    config = read_json(path) if path.exists() else {'unity': []}
    seen = set()
    for worker in config['unity']:
        worker = copy.deepcopy(worker)
        if not worker.get('model_id') or worker['model_id'] in seen:
            raise ValueError('Configure each Unity model exactly once')
        seen.add(worker['model_id'])
        worker.update(id='unity-' + worker['model_id'], kind='unity', models=[worker['model_id']])
        workers.append(worker)
    return workers


def promote(app, session_id):
    """Acceptance requires a completed perfect candidate and a structural review.

    Persist the entire transaction before replacing definitions; replay is idempotent.
    """
    from .engine import top_three
    from .promotion import apply
    session = Store(app.root).load(session_id)
    if session.get('status') != 'perfect':
        return None
    ranked = top_three(session, session['cohort']['models'], Store(app.root).observations(session))
    if not ranked or ranked[0]['percentage'] != 100 or not ranked[0]['complete']:
        return None
    winner = ranked[0]
    attempt = next(a for a in session['attempts'] if a['number'] == winner['attempt'])
    if attempt.get('status') != 'complete' or attempt.get('review_status', 'accepted') != 'accepted':
        return None
    key = digest({'session': session_id, 'candidate': winner['candidate']})
    target = directory(app.root, key)
    with HostLock(app.data / 'coverage.lock'), review_lock(app.root):
        if (target / 'state.json').exists():
            state = read_state(app.root, key)
            finish_promotion(app.root, state)
            return key
        cases = session['scope']['cases']
        bases = {c['test']['id']: c['test'] for c in cases.values()}
        updates = {}; recipes = {}
        for test_id, base in bases.items():
            current = read_json(app.root / 'test_specs' / (test_id + '.json'))
            if current != base:
                raise ValueError('OPRO base definition changed; promotion blocked')
            enabled = {v['id'] for v in base['variants'] if v.get('enabled', True)}
            covered = {c['variant']['id'] for c in cases.values() if c['test']['id'] == test_id}
            if not enabled <= covered or any('prompt_bindings' not in v for v in base['variants']):
                raise ValueError('Automatic promotion requires complete database presentation coverage')
            recipe = {'session_id': session_id, 'candidate': winner['candidate'], 'candidate_digest': digest(winner['candidate']),
                      'review_status': 'accepted', 'validation': {k: winner[k] for k in ('complete', 'required', 'recorded', 'passes')},
                      'approval_basis': APPROVAL, 'base_test': base,
                      'base_definition_digest': digest(base),
                      'template_definition_digest': base.get('prompt_builder', {}).get('automatic_promotion', {}).get('template_definition_digest', digest(base))}
            promoted = apply(base, recipe)
            for c in cases.values():
                if c['test']['id'] == test_id:
                    v = next(v for v in promoted['variants'] if v['id'] == c['variant']['id'])
                    from .templates import render, bindings
                    if messages(promoted, v['steps'][0], {}, v) != render(winner['candidate'], bindings(c)):
                        raise ValueError('Saved-definition renderer differs from the validated candidate')
            updates[test_id] = promoted
            recipes[test_id] = recipe
        state = {'id': key, 'session_id': session_id, 'candidate_digest': digest(winner['candidate']),
                 'status': 'promoting', 'promotion': {'before': bases, 'after': updates, 'recipes': recipes},
                 'workers': configured(app), 'approval_basis': APPROVAL}
        attempt.update(review_status='accepted',review={'candidate_digest':state['candidate_digest'],
            'validation':{k:winner[k] for k in ('complete','required','recorded','passes')},
            'findings':['Exact validated messages, complete presentations, unchanged fixtures/oracles/controls, no fixture IDs or expected states in the template.'],
            'approval_basis':APPROVAL})
        Store(app.root).save(session)
        save(app.root, state)
        finish_promotion(app.root, state)
        return key


def finish_promotion(root, state):
    if state['status'] != 'promoting':
        return
    for tid, after in state['promotion']['after'].items():
        p = root / 'test_specs' / (tid + '.json')
        if read_json(p) not in (state['promotion']['before'][tid], after):
            raise ValueError('Conflicting definition during promotion recovery')
    path = root / 'optimization/active_promotions.json'
    registry = read_json(path) if path.exists() else {'version': 1, 'recipes': {}}
    registry['recipes'].update(state['promotion']['recipes'])
    write_json(path, registry)
    from .promotion import rebuild
    rebuild(root)
    state['scope'] = scope(root); state['suite_digest'] = digest(state['scope'])
    state.update(status='pending', message='Promoted from the saved base definitions. Full configured-model coverage pending.')
    save(root, state)


def summarize(app, models):
    """Use the actual planner's exact compatibility checks, never totals alone."""
    report, plan = app.build_preflight(track_progress=False)
    native = {g['model']['id']: g for g in plan['groups']}
    rows = []
    for mid in models:
        if mid == 'perchance-text-generator':
            from workbench import perchance
            remote = plan.get('perchance_plan')
            if not remote:
                rows.append({'model_id': mid, 'status': 'blocked', 'reason': 'Perchance requires an eligible actual 8 GB worker', 'complete': 0})
                continue
            groups = remote['groups']; total = len(groups); complete = sum(g['done'] for g in groups)
            evidence=[]
            for group in groups:
                if group['done']:
                    path=app.store.path(mid,group['case_id']);evidence.append(evidence_file(path))
        else:
            group = native.get(mid)
            if group is None:
                rows.append({'model_id': mid, 'status': 'blocked', 'reason': 'Configured model unavailable or excluded', 'complete': 0})
                continue
            from workbench.planning import _compatible_completed_result
            from workbench.domain import case_id
            records = []
            for path in app.store.root.glob(mid+'/*.json'):
                try: records.append(app.store.read(path))
                except (OSError,ValueError): pass
            complete=0;total=0;evidence=[]
            for test in load_tests(app.root/'test_specs'):
                for variant in test['variants']:
                    if not variant.get('enabled',True):continue
                    for repetition in range(test.get('repetitions',1)):
                        total+=1
                        prior=_compatible_completed_result(records,group['model'],test,variant,repetition,plan['target'],code_fingerprint())
                        if prior and prior['record']['status']=='completed':
                            complete+=1;evidence.append(evidence_file(app.store.path(mid,prior['record']['case_id'])))
        rows.append({'model_id': mid, 'status': 'completed' if total and complete == total else 'partial',
                     'complete': complete, 'required': total,'evidence':evidence})
    return rows, report, plan


def advance_once(app, key):
    with HostLock(app.data / 'coverage.lock'):
        state = read_state(app.root, key)
        with review_lock(app.root):
            finish_promotion(app.root, state)
            if digest(scope(Path(state.get('suite_root',app.root)))) != state['suite_digest']:
                state.update(status='blocked', message='Current suite changed; frozen coverage preserved.')
                save(app.root, state); return state
        for worker in state['workers']:
            if app.cancel_event.is_set():
                state.update(status='stopped', message='Stopped; terminal evidence preserved.'); save(app.root, state); return state
            if worker.get('status')=='blocked':continue
            if worker['kind']!='local' and worker.get('status')=='completed':continue
            try:
                worker['status']='checking';save(app.root,state)
                if worker['kind'] == 'adopted':
                    from .coverage_adoption import advance
                    advance(app,state,worker)
                elif worker['kind'] == 'local':
                    # Disable source sync/publish only for this authorized frozen operation.
                    previous = dict(app.settings)
                    try:
                        app.settings.update(sync_source=False, publish_results=False)
                        prior_rows, _, _ = summarize(app, worker['models'])
                        if not all(r['status']=='completed' for r in prior_rows):app.run()
                        rows, report, plan = summarize(app, worker['models'])
                        worker.update(rows=rows, status='completed' if all(r['status']=='completed' for r in rows) else 'blocked',
                                      issues=report.get('issues', []))
                        if worker['status']=='blocked':worker['error']='Local coverage is unfinished or blocked; explicit Resume is required. No automatic retry.'
                    finally: app.settings = previous
                else:
                    from .coverage_unity import advance
                    advance(app, state, worker)
            except Cancelled:
                state.update(status='stopped', message='Stopped; terminal evidence preserved.');save(app.root,state);raise
            except Exception as exc:
                worker.update(status='blocked', error=str(exc))
            save(app.root, state)
        statuses = [w.get('status', 'pending') for w in state['workers']]
        state['status'] = 'completed' if statuses and all(s == 'completed' for s in statuses) else 'partial' if any(s in ('completed','running','queued','partial') for s in statuses) else 'blocked'
        state['message'] = 'Full configured-model coverage complete.' if state['status'] == 'completed' else 'Coverage remains pending, partial or blocked; inspect each worker.'
        save(app.root, state)
        return state


def resume(app, key, retry_blocked=False):
    """Monitor submitted jobs through terminal status; OS-held locks prevent overlap.

    Explicit Stop exits polling and leaves every submitted job intact.
    """
    if retry_blocked:
        with HostLock(app.data/'coverage.lock'):
            state=read_state(app.root,key)
            for worker in state['workers']:
                if worker.get('status')=='blocked':worker['status']='pending'
            save(app.root,state)
    while True:
        state=advance_once(app,key)
        if not any(w.get('status') in ('queued','running') for w in state['workers']):return state
        app.message=state['message']
        app.state='running'
        app.set_progress('coverage','Waiting for submitted model coverage',detail='; '.join(w['id']+': '+w.get('status','pending') for w in state['workers']))
        if app.cancel_event.wait(30):
            state.update(status='stopped',message='Monitoring stopped; existing Unity jobs remain submitted.')
            save(app.root,state);return state


def after_success(app, session_id):
    try:key = promote(app, session_id)
    except Exception as exc:
        from .engine import top_three
        session=Store(app.root).load(session_id)
        ranked=top_three(session,session['cohort']['models'],Store(app.root).observations(session))
        if not ranked:raise
        key=digest({'session':session_id,'candidate':ranked[0]['candidate']})
        if (directory(app.root,key)/'state.json').exists():
            state=read_state(app.root,key)
            state['message']='Promotion interrupted: '+str(exc)+'. Saved transaction requires resume.'
        else:
            state={'id':key,'session_id':session_id,'candidate_digest':digest(ranked[0]['candidate']),
                'status':'blocked','scope':scope(app.root),'suite_digest':digest(scope(app.root)),
                'workers':[],'message':'Promotion blocked: '+str(exc)}
        save(app.root,state);app.coverage_id=key;app.message=state['message'];return state
    if key:
        app.coverage_id = key
        return resume(app, key)


def evidence_file(path):
    stat=path.stat()
    return {'path':str(path),'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns,
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def restore_pending(app):
    """Reconnect monitoring on normal app restart; explicit stopped work stays stopped."""
    for path in sorted((app.root/'coverage_results').glob('*/state.json')):
        state=read_state(app.root,path.parent.name)
        if state['status'] in ('pending','promoting') or (state['status']!='stopped' and any(w.get('status') in ('queued','running','checking') for w in state['workers'])):
            app.start('coverage',{'id':state['id']});return state['id']
