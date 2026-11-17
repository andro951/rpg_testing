"""Isolated paid-API study controller. No CLI/autostart or desktop registration.

Use only after account, budget and experimental controls are approved. Existing
native controller, runtime and evidence remain unchanged. Uses the same scorer,
ResultStore and exact-path result-sync machinery, with separate provider identity.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import threading
import uuid
from .domain import ResultStore, digest, write_json, read_json, validate_test, experiment_spec, code_fingerprint
from .openai_api import PreparedOpenAIClient, prepare_scope, validate_scope, MODELS
from .result_sync import ResultSync, sync_run, git
from .workflows import execute, Cancelled
from .api_budget import _locked


def api_fingerprint():
    root=Path(__file__).parent
    return digest({name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                   for name in ('openai_api.py','openai_study.py','api_budget.py','openai_study_run.py')})


def _validate_checkout(root):
    if root!=Path(__file__).resolve().parent.parent:
        raise ValueError('API controller must run in its own isolated source checkout')
    if git(root,'status','--porcelain','--untracked-files=no'):
        raise ValueError('Commit tracked source changes before paid execution')


class StudyBackend:
    supports_cache=False
    supports_schema=False
    def __init__(self,client,journal):self.client,self.journal=client,Path(journal)
    def generate(self,messages,settings,schema,cache='default',cancel=None):
        if cache!='default' or schema is not None:
            raise ValueError('Unvalidated API cache/schema control')
        if cancel and cancel.is_set():raise Cancelled('Stopped before API call')
        data=read_json(self.journal)
        entry={'messages':copy.deepcopy(messages),'requested_sampling':copy.deepcopy(settings),'status':'in_flight'}
        data['calls'].append(entry);write_json(self.journal,data)
        try:
            result=self.client.generate(messages)
            data=read_json(self.journal);entry=data['calls'][-1]
            result['requested_sampling']=copy.deepcopy(settings)
            result['applied_sampling']={'reasoning_effort':self.client.effort}
            result['unsupported_controls']=sorted(set(result.get('unsupported_controls',[]))|set(settings))
            entry.update(status='complete',response=copy.deepcopy(result))
            write_json(self.journal,data)
            return result
        except Exception as exc:
            data=read_json(self.journal);entry=data['calls'][-1]
            entry.update(status='interrupted',error_type=type(exc).__name__,
                         partial_response=copy.deepcopy(getattr(exc,'partial_response',None)))
            write_json(self.journal,data)
            raise


class OpenAIStudyController:
    def __init__(self,root,tests,models,effort,ledger,transport,*,coverage_id,
                 approved_controls=False,simulated=False,sync=None):
        self.root=Path(root).resolve()
        if not approved_controls:
            raise ValueError('Explicit API control-difference approval required')
        if not models or len(set(models))!=len(models) or any(m not in MODELS for m in models):
            raise ValueError('Exact requested model list required')
        self.tests=prepare_scope(tests)
        validate_scope(self.tests)
        for test in self.tests:
            validate_test(test)
            for variant in test['variants']:
                if variant.get('cache','default')!='default':
                    raise ValueError('Controlled cache not supported by API study')
                def validate_steps(steps):
                    for step in steps:
                        if step.get('output',{}).get('type','text')!='text':
                            raise ValueError('Schema-constrained API study not validated')
                        if 'steps' in step:validate_steps(step['steps'])
                validate_steps(variant['steps'])
        self.models,self.effort,self.ledger,self.transport=models,effort,ledger,transport
        self.coverage_id=coverage_id
        if not isinstance(coverage_id,str) or not coverage_id.strip():raise ValueError('Coverage identity required')
        self.demo=simulated
        if simulated and getattr(transport,'simulated',False) is not True:
            raise ValueError('Simulated study requires an explicitly simulated transport')
        if not simulated:_validate_checkout(self.root)
        self.store=ResultStore(self.root/('results-demo' if simulated else 'results'))
        self.local=self.root/'.local'/'openai-study'/digest(coverage_id)
        self.local.mkdir(parents=True,exist_ok=True)
        self.cancel_event=threading.Event()
        self.result_sync=sync or ResultSync(self.root, (getattr(transport,'_key',''),))
        self.result_sync_active=False;self.result_sync_status={}
        self.source_commit=git(self.root,'rev-parse','HEAD')
        source_tree=digest([line for line in git(self.root,'ls-tree','HEAD').splitlines()
                            if line.split('\t')[-1] not in ('results','results-demo')])
        self.identity={'source_tree':source_tree,'provider':'openai-responses','api_code':api_fingerprint(),
                       'workflow_code':code_fingerprint(),'effort':effort,'coverage_id':coverage_id,
                       'context':'provider_native','output_limit':'provider_native',
                       'sampling':'provider_defaults','service_tier':'default','store':False,
                       'cache':{'mode':'implicit','ttl':'30m'}}
        self.manifest={'identity':self.identity,'models':models,'tests_sha256':digest(self.tests),
                       'source_commit':self.source_commit,'budget_path_sha256':digest(str(ledger.path.resolve()))}
        manifest_path=self.local/'manifest.json'
        if manifest_path.exists():
            previous=read_json(manifest_path)
            # Result-only sync commits change HEAD, not the source tree. Retain
            # the original source pin and completed-case identities on resume.
            comparable=lambda m:{k:v for k,v in m.items() if k!='source_commit'}
            if comparable(previous)!=comparable(self.manifest):
                raise ValueError('Coverage source/controls changed; separate study required')
            self.manifest=previous
        else:write_json(manifest_path,self.manifest)

    def log(self,*args):pass
    def retry_result_sync(self):
        if not self.demo:self.result_sync_status=self.result_sync.retry()
        return self.result_sync_status

    def jobs(self):
        for model in self.models:
            for test in self.tests:
                if not test.get('enabled',True):continue
                for variant in test['variants']:
                    if not variant.get('enabled',True):continue
                    for repetition in range(test.get('repetitions',1)):
                        cid=digest({'identity':self.identity,'model':model,'experiment':experiment_spec(test,variant),
                                    'repetition':repetition})
                        yield model,test,variant,repetition,cid

    @sync_run
    def run(self):
        # Single coverage owner, while the shared ledger independently protects
        # all models/processes using the combined approved dollar cap.
        with _locked(self.local/'run.lock',.1):
            return self._run_locked()

    def _run_locked(self):
        if not self.demo:_validate_checkout(self.root)
        if api_fingerprint()!=self.identity['api_code'] or code_fingerprint()!=self.identity['workflow_code']:
            raise ValueError('Source changed after study construction; refusing API dispatch')
        current_tree=digest([line for line in git(self.root,'ls-tree','HEAD').splitlines()
                             if line.split('\t')[-1] not in ('results','results-demo')])
        if current_tree!=self.identity['source_tree']:
            raise ValueError('Committed source changed after study construction')
        available=set(self.transport.available_models())
        if not set(self.models)<=available:raise ValueError('Requested models unavailable to this API account')
        completed=skipped=0
        for model,test,variant,repetition,cid in self.jobs():
            if self.store.done(model,cid):skipped+=1;continue
            if self.cancel_event.is_set():return {'status':'stopped','completed':completed,'reused':skipped}
            journal=self.local/(cid+'.json')
            if journal.exists():
                raise RuntimeError('Unfinished paid case requires reconciliation; automatic replay forbidden: '+cid)
            record={'model_id':model,'case_id':cid,'test_id':test['id'],'variant_id':variant['id'],
                    'repetition':repetition,'test_definition':test,'variant_definition':variant,
                    'provenance':copy.deepcopy(self.manifest),'simulated':self.demo,
                    'execution_class':'remote_api','valid_for_full_gpu_comparison':False,
                    'session_id':uuid.uuid4().hex,'target':copy.deepcopy(self.identity)}
            write_json(journal,{'case_id':cid,'calls':[],'status':'started','provenance':self.manifest})
            def persist_received(envelope):
                data=read_json(journal)
                data['calls'][-1]['received_before_settlement']=envelope
                write_json(journal,data)
            client=PreparedOpenAIClient(model,self.effort,self.ledger,self.transport,scope=self.tests,
                                       response_sink=persist_received)
            backend=StudyBackend(client,journal)
            try:
                outcome=execute(test,variant,backend,self.cancel_event,repetition=repetition)
                record.update(outcome,status='completed',sampling_seed_policy='requested_only_not_verified_by_provider')
                self.store.save(record)
                data=read_json(journal);data['status']='completed';write_json(journal,data)
                completed+=1
            except Exception as exc:
                record.update(getattr(exc,'partial',{}),status='aborted' if isinstance(exc,Cancelled) else 'error',
                              error_type=type(exc).__name__,measurement_valid=False,
                              raw_call_journal=read_json(journal),score={'valid':False,'exact_match':None})
                self.store.save(record)
                raise
        return {'status':'completed','completed':completed,'reused':skipped}
