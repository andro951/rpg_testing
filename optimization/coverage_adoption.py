"""Adopt a frozen desktop/Unity batch without launching or resubmitting anything."""
import hashlib
import time
from pathlib import Path
from workbench.domain import read_json, digest, ResultStore, experiment_spec
from workbench.judgements import load_tests
from workbench.workflows import messages
from .coverage import scope, directory, save, read_state, evidence_file


def adopt(app, batch_root):
    root=Path(batch_root).resolve();plan=read_json(root/'batch-plan.json');manifest=read_json(root/'prompt-manifest.json')
    if plan['scope_digest']!=manifest['scope_digest'] or plan['candidate_sha256']!=manifest['candidate_sha256']:
        raise ValueError('Batch candidate/suite receipts conflict')
    suite_root=root/'common-repo'
    if hashlib.sha256((root/'source.tar.gz').read_bytes()).hexdigest()!=plan['source_archive_sha256']:
        raise ValueError('Frozen source archive checksum mismatch')
    # Frozen external batches may still carry the original data layout.
    promotion_file=suite_root/'archives/prompt-builder-inputs/promotions'/(manifest['promotion_id']+'.json')
    if not promotion_file.exists():
        promotion_file=suite_root/'test_builder/promotions'/(manifest['promotion_id']+'.json')
    promotion=read_json(promotion_file)
    if digest(promotion['candidate'])!=manifest['candidate_sha256'] or promotion['provenance']['review_status']!='accepted':
        raise ValueError('Batch candidate differs from the accepted normal promotion')
    actual={(t['id'],v['id'],digest(messages(t,v['steps'][0],{},v)),t.get('repetitions',1))
            for t in load_tests(suite_root/'test_specs') for v in t['variants'] if v.get('enabled',True)}
    expected={(r['test_id'],r['variant_id'],r['message_digest'],r['repetitions']) for r in manifest['requests']}
    if actual!=expected:raise ValueError('Batch frozen prompts differ from its saved suite')
    receipt=read_json(root/'unity/submission-receipt.json')
    if receipt['scope_digest']!=manifest['scope_digest'] or receipt['source_archive_sha256']!=plan['source_archive_sha256']:
        raise ValueError('Unity source/suite receipt differs from the frozen batch')
    jobs={j['model_id']:j for j in receipt['jobs']}
    if len(jobs)!=len(receipt['jobs']) or len({j['job_id'] for j in jobs.values()})!=len(jobs):
        raise ValueError('Duplicate Unity model/job identity')
    key='adopt-'+digest({'batch':str(root),'suite':manifest['scope_digest'],'candidate':manifest['candidate_sha256']})
    if (directory(app.root,key)/'state.json').exists():return key
    workers=[]
    for cohort in plan['cohorts']:
        mid=cohort['model_id'];worker={'id':cohort['worker']+'-'+cohort['slug'],'kind':'adopted','models':[mid],
                'model_id':mid,'batch_root':str(root),'cohort':cohort,'status':'pending'}
        if cohort['worker']=='unity':
            job=jobs.get(mid)
            if not job or job['remote_root']!=cohort['remote_root'] or not job['one_model'] or not job['one_gpu']:
                raise ValueError('Unity job does not match the frozen one-model cohort')
            worker['receipt']=job
        workers.append(worker)
    if sum(r[3] for r in actual)*len(workers)!=plan['required_current_observations']:
        raise ValueError('Batch coverage denominator differs from the frozen scope')
    state={'id':key,'status':'pending','session_id':promotion['provenance']['session_id'],
        'suite_digest':digest(scope(suite_root)),'scope':scope(suite_root),'suite_root':str(suite_root),
        'active_suite_matches':scope(app.root)==scope(suite_root),'candidate_digest':manifest['candidate_sha256'],
        'original_suite_digest':manifest['scope_digest'],'adopted_batch':str(root),'workers':workers,
        'message':'Existing accepted promotion and submitted jobs adopted; no submission or rerun.'}
    save(app.root,state);return key


def advance(app,state,worker):
    cohort=worker['cohort'];batch=Path(worker['batch_root']);mid=worker['model_id']
    if cohort['worker']=='unity':
        folder=batch/'unity'/cohort['slug'];results=folder/'evidence/repo/results'
    elif cohort.get('already_current_complete'):
        results=Path(cohort['current_results_root']);folder=results.parent.parent
    else:folder=Path(cohort['root']);results=folder/'repo/results'
    tests={t['id']:t for t in load_tests(Path(state.get('suite_root',app.root))/'test_specs')}
    wanted={(t['id'],v['id'],rep) for t in tests.values() for v in t['variants'] if v.get('enabled',True) for rep in range(t.get('repetitions',1))}
    found={};evidence=[];store=ResultStore(results)
    for path in (results/mid).glob('*.json'):
        record=store.read(path);tid=record['test_id'];vid=record['variant_id'];ident=(tid,vid,record['repetition'])
        if ident not in wanted:continue
        test=tests[tid];variant=next(v for v in test['variants'] if v['id']==vid)
        if experiment_spec(test,variant)!=experiment_spec(record['test_definition'],record['variant_definition']):continue
        if record['status']!='completed' or record.get('simulated') is not False:continue
        if record['provenance']['workflow_code']!=state['scope']['workflow']:raise ValueError('Unreviewed workflow identity')
        if not record['calls'] or record['calls'][0]['messages']!=messages(test,variant['steps'][0],{},variant):
            raise ValueError('Raw request differs from frozen prompt')
        if cohort['provider']=='native':
            if record['execution_class']!='full_gpu' or record['load']['context']['allocated_tokens']!=32768:
                raise ValueError('Native placement/context differs from frozen batch')
            if cohort.get('artifact_identity') and record['artifact_identity']!=cohort['artifact_identity']:
                raise ValueError('Native artifact identity differs from frozen batch')
        if ident in found:raise ValueError('Duplicate observation for the frozen condition/repetition')
        found[ident]=record;evidence.append(evidence_file(path))
    if set(found)==wanted:
        reuse=folder/'reuse-manifest.json'
        if reuse.exists():
            for entry in read_json(reuse)['entries']:
                if hashlib.sha256(store.path(mid,entry['case_id']).read_bytes()).hexdigest()!=entry['bytes_sha256']:
                    raise ValueError('Retained raw result changed')
        from evaluation.core import assess_record
        from collections import Counter
        worker.update(status='completed',rows=[{'model_id':mid,'status':'completed','complete':len(found),
            'required':len(wanted),'evidence':evidence,'outcomes':dict(Counter(assess_record(r)['objective_outcome'] for r in found.values()))}])
    elif cohort['worker']=='unity':
        status_path=folder/'job-status.json'
        snapshot=read_json(status_path) if status_path.exists() else {}
        if snapshot.get('job_id')!=worker['receipt']['job_id'] or snapshot.get('remote_root')!=worker['receipt']['remote_root']:
            raise ValueError('Collector receipt conflicts with adopted job')
        queue=snapshot.get('queue','')
        if time.time()-status_path.stat().st_mtime>180:
            worker.update(status='blocked',error='Collector status is stale; verify the existing job. No resubmission.')
        elif queue:
            worker.update(status='running' if '|RUNNING|' in queue else 'queued',snapshot={k:v for k,v in snapshot.items() if k!='fit.json'})
        else:worker.update(status='blocked',error='Existing job terminal without complete collected evidence; inspect its retained logs.')
    else:worker.update(status='partial',error='Adopted desktop evidence incomplete; explicit guarded recovery required.')
