"""Deterministic simulation of GPU qualification, recovery, interruption and resume."""
import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from workbench.controller import Controller
from workbench.backends import DemoBackend
from workbench.execution_policy import CPUOffload, DoesNotFit, ContextCapacity, RunFailure, fallback_id
from workbench.domain import read_json
from workbench.scheduler import Session
from workbench import preflight

ROOT=Path(__file__).resolve().parents[1]

class TwoPassTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);shutil.copytree(ROOT/'test_specs',self.root/'test_specs')
        self.app=Controller(self.root,True);self.app.selftest=lambda:None
        definitions=[read_json(p) for p in (self.root/'test_specs').glob('*.json')]
        self.case_count=sum(t.get('repetitions',1)*sum(v.get('enabled',True) for v in t['variants']) for t in definitions if t.get('enabled',True))
        self.catalog=[];self.installed=[]
        for mid,size in [('large',6),('good',4),('small',3)]:
            m={'id':mid,'files':[mid+'.gguf'],'base_model':'SIMULATED','required_vram_gb':8,'sha256':{mid+'.gguf':'a'*64}}
            self.catalog.append(m)
            self.installed.append({'id':mid,'name':mid,'files':m['files'],'paths':[], 'size_bytes':size*2**30,
                'required_vram_gb':8,'recommended_vram_gb':8,'complete':True,'errors':[],'missing_shards':[],
                'catalogued':True,'metadata':{'demo.context_length':65536,'demo.block_count':32},'catalog':m})
        self.app.catalog=lambda:copy.deepcopy(self.catalog);self.app.demo_models=lambda:copy.deepcopy(self.installed)
        self.app.fingerprint=lambda m:{m['files'][0]:'a'*64}
        self.events=[];self.failures={};self.instances=[]
    def factory(self,settings,gpu,log):
        outer=self
        class Backend(DemoBackend):
            def load(self,m,c,cancel=None,layers='all',execution_class='full_gpu'):
                self.mid=m['id'];outer.events.append(('load',self.mid,execution_class,layers,c['allocated_tokens']))
                failure=outer.failures.get((self.mid,execution_class))
                if failure:
                    if isinstance(failure,list):
                        item=failure.pop(0) if failure else None
                        if item:raise item
                    elif callable(failure):failure()
                    else:raise failure
                result=super().load(m,c,cancel,layers,execution_class)
                if execution_class=='cpu_offloaded':result['placement']={'status':'cpu_offloaded','gpu_layers':layers,'total_layers':33,'cpu_layers':33-layers}
                return result
            def unload(self):outer.events.append(('unload',getattr(self,'mid',None)))
            def generate(self,*args,**kwargs):
                outer.events.append(('generate',getattr(self,'mid',None)))
                return super().generate(*args,**kwargs)
        b=Backend(log);self.instances.append(b);return b
    def run_session(self):
        report=self.app.check()
        self.assertTrue(report['ready'],report)
        s=Session(self.app,report,self.app.plan,self.factory);s.run();return s
    def test_primary_all_before_smallest_first_recovery(self):
        for mid in ('large','small'):self.failures[mid,'full_gpu']=CPUOffload('3 CPU layers',{'gpu_layers':30,'total_layers':33})
        self.run_session()
        loads=[e for e in self.events if e[0]=='load']
        self.assertEqual([e[1] for e in loads[:3]],['large','good','small'])
        self.assertEqual([(e[1],e[2]) for e in loads[3:]],[('small','full_gpu'),('small','cpu_offloaded'),('large','full_gpu'),('large','cpu_offloaded')])
        rows=self.app.store.all()
        self.assertEqual(sum(r['status']=='skipped' and r['execution_class']=='full_gpu' for r in rows),2*self.case_count)
        self.assertEqual(sum(r['status']=='completed' and r['execution_class']=='cpu_offloaded' for r in rows),2*self.case_count)
        self.assertEqual(sum(r['status']=='completed' and r['execution_class']=='full_gpu' for r in rows),self.case_count)
        self.assertFalse(any(r['valid_for_full_gpu_comparison'] for r in rows if r['execution_class']=='cpu_offloaded'))
        self.assertEqual(self.app.check()['plan']['pending'],0)
    def test_secondary_never_satisfies_primary_success(self):
        self.failures['small','full_gpu']=DoesNotFit('OOM');self.run_session()
        rows=[r for r in self.app.store.all() if r['model_id']=='small']
        self.assertEqual(len(rows),2*self.case_count)
        self.assertTrue(all(r['status']=='skipped' for r in rows if r['execution_class']=='full_gpu'))
    def test_recovery_full_success_stays_primary(self):
        self.failures['small','full_gpu']=[DoesNotFit('busy display memory')]
        self.run_session();rows=[r for r in self.app.store.all() if r['model_id']=='small']
        self.assertEqual(len(rows),self.case_count);self.assertTrue(all(r['status']=='completed' for r in rows))
        self.assertTrue(all(r['execution_class']=='full_gpu' and r['attempts'][0]['status']=='skipped' for r in rows))
    def test_recovery_failures_are_bounded_and_resume_is_empty(self):
        self.failures['small','full_gpu']=DoesNotFit('OOM');self.failures['small','cpu_offloaded']=DoesNotFit('OOM')
        self.run_session();loads=[e for e in self.events if e[0]=='load' and e[1]=='small']
        self.assertEqual(len(loads),6);self.assertEqual([e[3] for e in loads[2:]],[24,16,8,3])
        self.assertEqual(self.app.check()['plan']['pending'],0)
    def test_bad_binary_not_retried_as_offload(self):
        self.failures['large','full_gpu']=RunFailure('unsupported architecture')
        self.run_session();self.assertEqual(len([e for e in self.events if e[0]=='load' and e[1]=='large']),1)
    def test_stop_after_model_does_not_enter_recovery(self):
        self.app.stop_after_model=True;self.failures['large','full_gpu']=DoesNotFit('OOM')
        self.run_session();self.assertEqual(len([e for e in self.events if e[0]=='load']),1)
        self.assertTrue(all(r['execution_class']=='full_gpu' for r in self.app.store.all()))
    def test_deleting_offloaded_result_schedules_recovery_only(self):
        self.failures['small','full_gpu']=DoesNotFit('OOM');self.run_session()
        r=next(r for r in self.app.store.all() if r['execution_class']=='cpu_offloaded')
        self.app.store.path(r['model_id'],r['case_id']).unlink()
        report=self.app.check();jobs=[j for g in self.app.plan['groups'] for j in g['jobs']]
        self.assertEqual(len(jobs),1);self.assertTrue(jobs[0]['recovery_only'])
        self.events.clear();self.run_session();self.assertEqual(len([e for e in self.events if e[0]=='load']),2)
    def test_cancel_unloads_and_preserves_aborted_evidence(self):
        original=self.factory
        def factory(*args):
            b=original(*args);generate=b.generate
            def stop(*a,**kw):self.app.cancel_event.set();return generate(*a,**kw)
            b.generate=stop;return b
        self.factory=factory
        from workbench.workflows import Cancelled
        with self.assertRaises(Cancelled):self.run_session()
        self.assertIsNone(self.app.backend);self.assertTrue(any(e[0]=='unload' for e in self.events))
        self.assertTrue(any(r['status']=='aborted' for r in self.app.store.all()))
    def test_context_expansion_retains_attempt_and_restarts_source(self):
        original=self.factory;once=[True]
        def factory(*args):
            b=original(*args);gen=b.generate
            def generate(*a,**kw):
                if once[0]:once[0]=False;raise ContextCapacity('Need more room',20000)
                return gen(*a,**kw)
            b.generate=generate;return b
        self.factory=factory;self.run_session()
        expanded=[e for e in self.events if e[0]=='load' and e[1]=='large']
        self.assertEqual(len(expanded),2);self.assertGreater(expanded[1][4],expanded[0][4])
        self.assertTrue(any(r.get('attempts') for r in self.app.store.all()))
        self.assertEqual(sum(r['status']=='completed' for r in self.app.store.all()),3*self.case_count)

if __name__=='__main__':unittest.main()
