"""Unattended primary-GPU and smallest-first recovery passes; all evidence is file-based."""
from __future__ import annotations
import copy
import platform
import time
import uuid
from datetime import datetime, timezone
from .execution_policy import (RunFailure, DoesNotFit, ContextCapacity, RuntimeStall, POLICY_VERSION,
    PRIMARY_CASE_SECONDS, RECOVERY_CASE_SECONDS, MAX_CONTEXT_EXPANSIONS, fallback_id, next_context, recovery_layers)
from .telemetry import GpuMonitor, monitored_execute
from .workflows import Cancelled


def now(): return datetime.now(timezone.utc).isoformat()


class Session:
    def __init__(self, app, report, plan, backend_factory, monitor_factory=GpuMonitor):
        self.app,self.report,self.plan=app,report,plan
        self.backend_factory,self.monitor_factory=backend_factory,monitor_factory
        self.session_id=uuid.uuid4().hex
        self.deferred=[];self.contexts={};self.expansions={};self.loads=[]
        self.monitor=None

    def ensure_running(self):
        if self.app.cancel_event.is_set():raise Cancelled('Stopped')

    def record(self,group,job,execution_class='full_gpu'):
        model=group['model']
        return {'status':'error','case_id':fallback_id(job['case_id']) if execution_class=='cpu_offloaded' else job['case_id'],
            'primary_case_id':job['case_id'],'model_id':model['id'],'test_id':job['test']['id'],
            'variant_id':job['variant']['id'],'repetition':job['repetition'],'target':self.plan['target'],
            'test_definition':job['test'],'variant_definition':job['variant'],'model_definition':model,
            'artifact_hashes':model.get('sha256',{}),'session_id':self.session_id,'started_at':now(),
            'simulated':self.app.demo,'execution_class':execution_class,
            'valid_for_full_gpu_comparison':execution_class=='full_gpu',
            'policy':POLICY_VERSION,'gpu':self.report['gpu'],
            'provenance':{'backend_version':self.app.backend_version(),'python':platform.python_version(),
                          'source_commit':self.app.source_commit(),'workflow_code':self.app.workflow_code()}}

    def save(self,record,processed=True):
        record['finished_at']=now()
        self.app.store.save(record)
        if processed:self.app.run_processed+=1
        self.app.log('case',record['case_id']+' '+record['status']+' '+record['execution_class'])
        self.app.flush_logs();self.app.publish()

    def mark(self,group,jobs,exc,execution_class='full_gpu',recovery_eligible=False):
        for job in jobs:
            record=self.record(group,job,execution_class)
            path=self.app.store.path(record['model_id'],record['case_id'])
            if path.exists() and self.app.store.read(path)['status']=='completed':continue
            record.update(status='skipped',reason=getattr(exc,'reason','runtime_error'),error=str(exc),
                evidence=getattr(exc,'evidence',{}),recovery_eligible=recovery_eligible,
                measurement_valid=False,valid_for_full_gpu_comparison=False,
                score={'valid':False,'exact_match':None,'note':'Execution qualification failed, not a semantic answer score'})
            self.save(record)

    def close_model(self):
        backend=self.app.backend
        try:
            if backend:backend.unload()
        finally:
            self.app.backend=None
            if self.monitor:
                self.app.last_telemetry=self.monitor.snapshot();self.monitor.close();self.monitor=None
            self.app.monitor=None;self.app.flush_logs()

    def load(self,group,execution_class='full_gpu',layers='all',phase='primary'):
        self.ensure_running();self.close_model()
        model=group['installed'];mid=model['id'];context=self.contexts[mid]
        self.app.current={'model':mid,'stage':'loading','pass':phase,'execution_class':execution_class}
        self.app.message=f'{phase.title()}: loading {mid}'
        backend=self.backend_factory(self.app.settings,self.report['gpu'],self.app.log)
        self.app.backend=backend
        self.monitor=self.monitor_factory(self.report['gpu'].get('uuid'),simulated=self.app.demo)
        self.monitor.start();self.app.monitor=self.monitor
        start=time.perf_counter()
        try:
            result=backend.load(model,context,self.app.cancel_event,layers=layers,execution_class=execution_class)
            self.loads.append({'model_id':mid,'pass':phase,'status':'loaded','execution_class':execution_class,
                              'layers_requested':layers,'context':context,'seconds':time.perf_counter()-start,'load':copy.deepcopy(result)})
            self.app.current['placement']=result.get('placement')
            self.app.log('load',self.loads[-1]);self.app.flush_logs()
            return result
        except Exception as exc:
            self.loads.append({'model_id':mid,'pass':phase,'status':'failed','execution_class':execution_class,
                'layers_requested':layers,'context':context,'seconds':time.perf_counter()-start,
                'reason':getattr(exc,'reason','runtime_error'),'error':str(exc),'evidence':getattr(exc,'evidence',{})})
            self.app.log('load_failure',self.loads[-1]);self.close_model();raise

    def cases(self,group,jobs,execution_class='full_gpu',layers='all',phase='primary'):
        """Return unprocessed cases after memory failure, not after wrong model answers."""
        for index,job in enumerate(jobs):
            self.ensure_running()
            record=self.record(group,job,execution_class)
            path=self.app.store.path(record['model_id'],record['case_id'])
            if path.exists() and self.app.store.read(path)['status']=='completed':continue
            while True:
                self.ensure_running()
                self.app.current={'model':group['model']['id'],'test':job['test']['id'],'variant':job['variant']['id'],
                    'stage':'starting','pass':phase,'execution_class':execution_class,
                    'placement':self.app.backend.load_metadata.get('placement')}
                record=self.record(group,job,execution_class)
                record['load']=copy.deepcopy(self.app.backend.load_metadata)
                seconds=PRIMARY_CASE_SECONDS if execution_class=='full_gpu' else RECOVERY_CASE_SECONDS
                record['watchdog_seconds']=seconds
                try:
                    with self.app.backend.budget(seconds):
                        outcome=monitored_execute(job['test'],job['variant'],self.app.backend,self.app.cancel_event,
                            lambda value:self.app.current.update(stage=value),self.monitor)
                    record.update(status='completed',**outcome);self.app.completed_now+=1
                    self.save(record);break
                except Cancelled as exc:
                    record.update(status='aborted',error='Stopped by user',partial=getattr(exc,'partial',{}))
                    self.save(record);raise
                except ContextCapacity as exc:
                    mid=group['model']['id'];new=next_context(self.contexts[mid],exc.required_tokens)
                    record.update(status='error',reason=exc.reason,error=str(exc),partial=getattr(exc,'partial',{}),measurement_valid=False)
                    self.save(record,processed=False)
                    if not new or self.expansions[mid]>=MAX_CONTEXT_EXPANSIONS:
                        self.mark(group,jobs[index:],exc,execution_class);return []
                    self.contexts[mid]=new;self.expansions[mid]+=1
                    try:self.load(group,execution_class,layers,phase)
                    except DoesNotFit as load_error:
                        self.mark(group,jobs[index:],load_error,execution_class,recovery_eligible=execution_class=='full_gpu')
                        return jobs[index:] if execution_class=='full_gpu' else []
                except DoesNotFit as exc:
                    record.update(status='error',reason=exc.reason,error=str(exc),partial=getattr(exc,'partial',{}),measurement_valid=False)
                    self.save(record,processed=False)
                    self.mark(group,jobs[index:],exc,execution_class,recovery_eligible=execution_class=='full_gpu')
                    return jobs[index:] if execution_class=='full_gpu' else []
                except Exception as exc:
                    record.update(status='error',reason=getattr(exc,'reason','runtime_error'),error=str(exc),
                                  partial=getattr(exc,'partial',{}),measurement_valid=False)
                    self.save(record);self.app.session_errors+=1
                    self.mark(group,jobs[index+1:],exc,execution_class)
                    return []
            if self.app.pause_requested:
                self.app.state='paused';self.app.message='Paused after case by your request.'
                while self.app.pause_requested and not self.app.cancel_event.is_set():self.app.resume_event.wait(.2)
                self.ensure_running();self.app.state='running'
        return []

    def run(self):
        app=self.app
        app.run_total=self.plan['pending'];app.run_processed=0;app.skipped_models=[]
        try:
            for group in self.plan['groups']:
                if not group['jobs']:continue
                self.ensure_running();mid=group['model']['id']
                self.contexts[mid]=copy.deepcopy(group['context']);self.expansions[mid]=0
                primary=[j for j in group['jobs'] if not j.get('recovery_only')]
                pending_recovery=[j for j in group['jobs'] if j.get('recovery_only')]
                if pending_recovery:self.deferred.append((group,pending_recovery))
                if not primary:continue
                try:
                    self.load(group)
                    remaining=self.cases(group,primary)
                    if remaining:self.deferred.append((group,remaining))
                except Cancelled:raise
                except Exception as exc:
                    retry=isinstance(exc,DoesNotFit)
                    self.mark(group,primary,exc,recovery_eligible=retry)
                    app.skipped_models.append({'model_id':mid,'reason':getattr(exc,'reason','runtime_error'),'recovery_eligible':retry})
                    if retry:self.deferred.append((group,primary))
                    else:app.session_errors+=1
                finally:self.close_model()
                if app.stop_after_model:return
            self.deferred.sort(key=lambda x:x[0]['installed']['size_bytes'])
            for group,jobs in self.deferred:
                self.ensure_running()
                if app.stop_after_model:return
                app.run_total+=len([j for j in jobs if not j.get('recovery_only')])
                try:
                    try:
                        self.load(group,phase='recovery-full-gpu')
                        remaining=self.cases(group,jobs,phase='recovery-full-gpu')
                        if not remaining:continue
                        jobs=remaining
                    except DoesNotFit:pass
                    total=next((int(v)+1 for k,v in group['installed']['metadata'].items() if k.endswith('.block_count')),None)
                    trials=recovery_layers(total)
                    loaded=False;last=DoesNotFit('No feasible GPU+CPU placement found')
                    for layers in trials:
                        self.ensure_running()
                        try:
                            self.load(group,'cpu_offloaded',layers,'recovery-offloaded');loaded=True;break
                        except DoesNotFit as exc:last=exc
                    if loaded:self.cases(group,jobs,'cpu_offloaded',layers,'recovery-offloaded')
                    else:self.mark(group,jobs,last,'cpu_offloaded')
                except Cancelled:raise
                except Exception as exc:
                    self.mark(group,jobs,exc,'cpu_offloaded');app.session_errors+=1
                finally:self.close_model()
        finally:
            app.current=None;app.load_attempts=self.loads
            app.log('session_load_attempts',self.loads)
            self.close_model();app.publish(force=True)
