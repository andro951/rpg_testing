"""Unattended, GPU-first execution and smallest-first hybrid recovery.

Completed and skipped case files are authoritative. Retry evidence is retained;
semantic mistakes are never retried. No function here prompts the user.
"""
from __future__ import annotations
import copy
import contextlib
import platform
import uuid
from datetime import datetime, timezone
from .execution_policy import (RunFailure, DoesNotFit, ContextCapacity, RuntimeStall, POLICY_VERSION,
    MAX_CONTEXT_EXPANSIONS, fallback_id, next_context, recovery_layers)
from .telemetry import GpuMonitor, monitored_execute
from .workflows import Cancelled


def now():return datetime.now(timezone.utc).isoformat()


class Session:
    def __init__(self, app, report, plan, backend_factory, monitor_factory=GpuMonitor):
        self.app,self.report,self.plan=app,report,plan
        self.backend_factory,self.monitor_factory=backend_factory,monitor_factory
        self.id=uuid.uuid4().hex;self.contexts={};self.expansions={};self.loads=[];self.monitor=None
        self.deferred=[];self.counted=set();self.seed_checks={}

    def check_stop(self):
        if self.app.cancel_event.is_set():raise Cancelled('Stopped by user or scheduler')

    def base_record(self,group,job,mode):
        return {'status':'error','case_id':fallback_id(job['case_id']) if mode=='cpu_offloaded' else job['case_id'],
            'primary_case_id':job['case_id'],'model_id':group['model']['id'],'test_id':job['test']['id'],
            'variant_id':job['variant']['id'],'repetition':job['repetition'],'target':self.plan['target'],
            'test_definition':job['test'],'variant_definition':job['variant'],
            'artifact_identity':copy.deepcopy(group['model'].get('artifact_identity',{})),
            'artifact_hashes':copy.deepcopy(group['model'].get('sha256',{})),'session_id':self.id,
            'simulated':self.app.demo,'execution_class':mode,'started_at':now(),
            'valid_for_full_gpu_comparison':mode=='full_gpu','policy':POLICY_VERSION,
            'gpu':self.report['gpu'],'provenance':self.app.run_provenance,
            'load':copy.deepcopy(getattr(self.app.backend,'load_metadata',{}))}

    def terminal(self,group,job,mode):
        cid=fallback_id(job['case_id']) if mode=='cpu_offloaded' else job['case_id']
        p=self.app.store.path(group['model']['id'],cid)
        if not p.exists():return False
        r=self.app.store.read(p)
        return r['status']=='completed' or mode=='cpu_offloaded' and r['status']=='skipped'

    def save(self,record,count=True):
        record['finished_at']=now();self.app.store.save(record)
        if count and record['case_id'] not in self.counted:
            self.counted.add(record['case_id']);self.app.run_processed+=1
        self.app.log('case',record['case_id']+' '+record['status']+' '+record['execution_class'])
        self.app.set_progress('run','Saving benchmark result',100,self.app.run_overall_percent(),
                              record.get('test_id','')+' / '+record.get('variant_id',''))
        self.app.flush_logs();self.app.publish()

    def skip(self,group,jobs,exc,mode='full_gpu',recoverable=False):
        for job in jobs:
            if self.terminal(group,job,mode):continue
            r=self.base_record(group,job,mode)
            r.update(status='skipped',reason=getattr(exc,'reason','runtime_error'),error=str(exc),
                evidence=getattr(exc,'evidence',{}),recovery_eligible=recoverable,
                measurement_valid=False,valid_for_full_gpu_comparison=False,
                score={'valid':False,'exact_match':None,'note':'Execution qualification failed, not a semantic answer'})
            self.save(r)

    def close_model(self):
        backend=self.app.backend
        try:
            if backend:backend.unload()
        finally:
            self.app.backend=None
            if self.monitor:
                self.app.last_telemetry=self.monitor.snapshot();self.monitor.close();self.monitor=None
            self.app.monitor=None;self.app.flush_logs()

    def load(self,group,mode='full_gpu',layers='all',phase='primary'):
        self.check_stop();self.close_model()
        model=group['installed'];mid=model['id'];context=self.contexts[mid]
        self.app.current={'model':mid,'stage':'loading','pass':phase,'execution_class':mode}
        self.app.message=f'{phase}: loading {mid}'
        self.app.backend=self.backend_factory(self.app.settings,self.report['gpu'],self.app.log)
        self.app.backend.progress=lambda task,pct,detail='':self.app.set_progress(
            'run',task,pct,self.app.run_overall_percent(),f'{mid} · {detail}')
        self.monitor=self.monitor_factory(self.report['gpu'].get('uuid'),simulated=self.app.demo)
        self.monitor.start();self.app.monitor=self.monitor
        try:
            self.app.set_progress('run','Loading model',0,self.app.run_overall_percent(),f'{mid} · {phase}')
            data=self.app.backend.load(model,context,self.app.cancel_event,layers=layers,execution_class=mode)
            seed_key=(mid,mode,str(layers),context.get('allocated_tokens'))
            if seed_key not in self.seed_checks:
                self.app.current['stage']='seed_reproducibility_check'
                try:seed_check=self.app.backend.seed_reproducibility_check(self.app.cancel_event)
                except Cancelled:raise
                except Exception as exc:
                    seed_check={'policy':'seed-reproducibility-v1','status':'error','seed_behavior_verified':False,
                                'same_seed_exact_match':None,'different_seed_changes_output':None,'error':str(exc)}
                self.seed_checks[seed_key]=copy.deepcopy(seed_check)
                self.app.log('seed_check',{'model_id':mid,'mode':mode,'context_tokens':context.get('allocated_tokens'),**seed_check})
            else:seed_check=copy.deepcopy(self.seed_checks[seed_key])
            data['seed_reproducibility']=copy.deepcopy(seed_check)
            self.app.backend.load_metadata['seed_reproducibility']=copy.deepcopy(seed_check)
            entry={'model_id':mid,'pass':phase,'status':'loaded','mode':mode,'requested_layers':layers,'load':copy.deepcopy(data)}
            self.app.current['placement']=data.get('placement');self.loads.append(entry)
            self.app.log('load',entry);self.app.flush_logs()
        except Exception as exc:
            self.loads.append({'model_id':mid,'pass':phase,'status':'failed','mode':mode,'requested_layers':layers,
                'context':context,'reason':getattr(exc,'reason','runtime_error'),'error':str(exc),
                'evidence':getattr(exc,'evidence',{}),'load':copy.deepcopy(getattr(self.app.backend,'load_metadata',{}))})
            self.app.log('load_failed',self.loads[-1]);self.close_model();raise

    def run_cases(self,group,jobs,mode='full_gpu',layers='all',phase='primary'):
        """Return remaining jobs only for a full-GPU memory failure."""
        for index,job in enumerate(jobs):
            if self.terminal(group,job,mode):continue
            while True:
                self.check_stop()
                if self.app.pause_requested:
                    self.app.state='paused';self.app.message='Paused between cases by your request.'
                    while self.app.pause_requested and not self.app.cancel_event.is_set():self.app.resume_event.wait(.2)
                    self.check_stop();self.app.state='running'
                self.app.current={'model':group['model']['id'],'test':job['test']['id'],'variant':job['variant']['id'],
                    'stage':'starting','pass':phase,'execution_class':mode,
                    'placement':self.app.backend.load_metadata.get('placement')}
                record=self.base_record(group,job,mode)
                seconds=job['test']['timeout_seconds']
                record['timeout_seconds']=seconds;record['watchdog_seconds']=seconds
                try:
                    # One timer includes ALL calls, branches and review passes in this workflow.
                    self.app.timing_active=True
                    case_label=f"{job['test']['id']} / {job['variant']['id']} / repetition {job['repetition']+1}"
                    self.app.set_progress('run','Running benchmark case',0,self.app.run_overall_percent(),case_label)
                    def case_progress(info):
                        self.app.current.update(stage=info['step'])
                        self.app.set_progress('run','Running benchmark case',info['percent'],self.app.run_overall_percent(),
                                              case_label+' · '+str(info['step']))
                    with self.app.backend.budget(seconds,terminate_process=False):
                        result=monitored_execute(job['test'],job['variant'],self.app.backend,
                            self.app.cancel_event,lambda step:self.app.current.update(stage=step),self.monitor,job['repetition'],case_progress)
                    record.update(status='completed',**result);self.app.completed_now+=1
                except Cancelled as exc:
                    record.update(status='aborted',error='Stopped',partial=getattr(exc,'partial',{}))
                    self.app.timing_active=False;self.save(record);raise
                except RuntimeStall as exc:
                    self.app.timing_active=False
                    partial=copy.deepcopy(getattr(exc,'partial',{}) or {})
                    record.update(status='completed',reason='case_timeout',error=str(exc),timed_out=True,
                                  partial=partial,calls=copy.deepcopy(partial.get('calls',[])),
                                  outputs=copy.deepcopy(partial.get('outputs',{})),
                                  step_events=copy.deepcopy(partial.get('step_events',[])),
                                  pipeline_seconds=partial.get('pipeline_seconds',seconds),
                                  measurement_valid=True,
                                  score={'valid':False,'exact_match':False,
                                         'error':f'Timed out after {seconds} seconds',
                                         'note':'Generation was cut off at the test time limit; partial output is preserved.'})
                    self.app.completed_now+=1;self.save(record)
                    try:self.app.backend.clear_cache()
                    except Cancelled:raise
                    except Exception:
                        try:self.load(group,mode,layers,phase)
                        except DoesNotFit as failed:
                            remaining=jobs[index+1:]
                            self.skip(group,remaining,failed,mode,recoverable=mode=='full_gpu')
                            return remaining if mode=='full_gpu' else []
                        except Cancelled:raise
                        except Exception as failed:
                            self.skip(group,jobs[index+1:],failed,mode);return []
                    break
                except ContextCapacity as exc:
                    self.app.timing_active=False
                    record.update(status='error',reason=exc.reason,error=str(exc),partial=getattr(exc,'partial',{}),measurement_valid=False)
                    self.save(record,False)
                    mid=group['model']['id'];larger=next_context(self.contexts[mid],exc.required_tokens)
                    if not larger or self.expansions[mid]>=MAX_CONTEXT_EXPANSIONS:
                        self.skip(group,jobs[index:],exc,mode);return []
                    self.contexts[mid]=larger;self.expansions[mid]+=1
                    try:self.load(group,mode,layers,phase)
                    except DoesNotFit as failed:
                        self.skip(group,jobs[index:],failed,mode,recoverable=mode=='full_gpu')
                        return jobs[index:] if mode=='full_gpu' else []
                    except Cancelled:raise
                    except Exception as failed:self.skip(group,jobs[index:],failed,mode);return []
                    continue
                except DoesNotFit as exc:
                    self.app.timing_active=False
                    record.update(status='error',reason=exc.reason,error=str(exc),partial=getattr(exc,'partial',{}),measurement_valid=False)
                    self.save(record,False);self.skip(group,jobs[index:],exc,mode,recoverable=mode=='full_gpu')
                    return jobs[index:] if mode=='full_gpu' else []
                except Exception as exc:
                    self.app.timing_active=False
                    record.update(status='error',reason=getattr(exc,'reason','runtime_error'),error=str(exc),
                                  partial=getattr(exc,'partial',{}),measurement_valid=False)
                    self.save(record,False);self.app.session_errors+=1
                    self.skip(group,jobs[index:],exc,mode);return []
                finally:self.app.timing_active=False
                self.save(record);break
        return []

    def run(self):
        a=self.app;a.run_total=self.plan['pending'];a.run_processed=0;a.skipped_models=[]
        try:
            for group in self.plan['groups']:
                if not group['jobs']:continue
                self.check_stop();mid=group['model']['id'];self.contexts[mid]=copy.deepcopy(group['context']);self.expansions[mid]=0
                primary=[j for j in group['jobs'] if not j.get('recovery_only')]
                recovery=[j for j in group['jobs'] if j.get('recovery_only')]
                if recovery:self.deferred.append((group,recovery))
                if not primary:continue
                try:
                    self.load(group)
                    remaining=self.run_cases(group,primary)
                    if remaining:self.deferred.append((group,remaining))
                except Cancelled:raise
                except Exception as exc:
                    retry=isinstance(exc,DoesNotFit)
                    self.skip(group,primary,exc,recoverable=retry)
                    a.skipped_models.append({'model_id':mid,'reason':getattr(exc,'reason','runtime_error'),'recovery_eligible':retry})
                    if retry:self.deferred.append((group,primary))
                    else:a.session_errors+=1
                finally:self.close_model()
                if a.stop_after_model:return
            # Only memory/placement failures get a second pass, never unrelated invalid models.
            combined={}
            for group,jobs in self.deferred:
                entry=combined.setdefault(group['model']['id'],(group,{}))
                entry[1].update({j['case_id']:j for j in jobs})
            self.deferred=[(g,list(jobs.values())) for g,jobs in combined.values()]
            self.deferred.sort(key=lambda g:g[0]['installed']['size_bytes'])
            for group,jobs in self.deferred:
                self.check_stop()
                if a.stop_after_model:return
                try:
                    try:
                        self.load(group,phase='recovery-full-gpu')
                        remaining=self.run_cases(group,jobs,phase='recovery-full-gpu')
                        if not remaining:continue
                        jobs=remaining
                    except DoesNotFit:pass
                    metadata=group['installed']['metadata']
                    arch=metadata.get('general.architecture')
                    total=metadata.get(str(arch)+'.block_count')
                    if total is None:total=next((v for k,v in metadata.items() if k.endswith('.block_count')),None)
                    total=int(total)+1 if total is not None else None
                    last=DoesNotFit('No feasible GPU+CPU placement found');loaded=False
                    for layers in recovery_layers(total):
                        try:self.load(group,'cpu_offloaded',layers,'recovery-offloaded');loaded=True;break
                        except DoesNotFit as exc:last=exc
                    if loaded:
                        a.run_total+=len([j for j in jobs if not self.terminal(group,j,'cpu_offloaded')])
                        self.run_cases(group,jobs,'cpu_offloaded',layers,'recovery-offloaded')
                    else:self.skip(group,jobs,last,'cpu_offloaded')
                except Cancelled:raise
                except Exception as exc:self.skip(group,jobs,exc,'cpu_offloaded');a.session_errors+=1
                finally:self.close_model()
        finally:
            a.timing_active=False;a.current=None;a.load_attempts=self.loads
            a.log('session_load_attempts',self.loads);self.close_model();a.publish(force=True)
