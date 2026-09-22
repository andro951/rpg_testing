import contextlib,copy,json,shutil,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from workbench.controller import Controller
from workbench.scheduler import Session
from workbench.demo_native import DemoNative
from workbench.domain import read_json,case_id
from workbench.execution_policy import CPUOffload,DoesNotFit,UnverifiedPlacement,ContextCapacity,RuntimeStall,fallback_id
from workbench.planning import pending_plan
from workbench.workflows import Cancelled

ROOT=Path(__file__).resolve().parents[1]

class UnattendedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        shutil.copytree(ROOT/'test_specs',self.root/'test_specs')
        self.app=Controller(self.root,True);self.app.selftest=lambda:None
        self.test=read_json(self.root/'test_specs/time_only.json');self.test['variants']=self.test['variants'][:1]
        self.target={'gpu_name':'SIMULATED','vram_gb':8,'backend':'demo'}
        self.models=[{'id':mid,'files':[mid+'.gguf'],'required_vram_gb':8,'sha256':{mid+'.gguf':'a'*64}}
                     for mid in ['large','good','small']]
        self.plan=pending_plan(self.models,[self.test],self.target,self.app.store)
        sizes={'large':6,'small':3,'good':4}
        for group in self.plan['groups']:
            mid=group['model']['id'];group['installed']={'id':mid,'paths':[],'size_bytes':sizes[mid]*2**30,
                'metadata':{'general.architecture':'demo','demo.block_count':32}}
            group['context']={'allocated_tokens':16384,'native_tokens':65536}
        self.report={'gpu':{'uuid':'demo','name':'SIMULATED','total_gib':8}}
        self.events=[]
    def factory(self,behavior):
        events=self.events
        class Fake(DemoNative):
            def load(b,model,context,cancel=None,layers='all',execution_class='full_gpu'):
                b.mid=model['id'];events.append(('load',b.mid,execution_class,layers,context['allocated_tokens']))
                behavior(b,model,context,execution_class)
                return super().load(model,context,cancel,layers,execution_class)
            def unload(b):events.append(('unload',getattr(b,'mid',None)))
            def generate(b,*args,**kwargs):
                events.append(('case',b.mid));return super().generate(*args,**kwargs)
        return Fake
    def run_session(self,behavior):
        session=Session(self.app,self.report,self.plan,self.factory(behavior));session.run();return session
    def test_all_primary_models_before_smallest_first_recovery(self):
        def behavior(b,m,c,mode):
            if m['id']!='good' and mode=='full_gpu':raise CPUOffload('partial',{'gpu_layers':30,'cpu_layers':3})
        self.run_session(behavior)
        loaded=[e for e in self.events if e[0]=='load']
        self.assertEqual([e[1] for e in loaded[:3]],['large','good','small'])
        self.assertEqual([e[1] for e in loaded[3:]],['small','small','large','large'])
        records=self.app.store.all();hybrid=[r for r in records if r.get('execution_class')=='cpu_offloaded']
        self.assertEqual(len(hybrid),2);self.assertTrue(all(not r['valid_for_full_gpu_comparison'] for r in hybrid))
        self.assertEqual(len([e for e in self.events if e[0]=='case']),3)
        self.assertEqual(pending_plan(self.models,[self.test],self.target,self.app.store)['pending'],0)
    def test_recovery_that_fits_stays_full_gpu(self):
        counts={}
        def behavior(b,m,c,mode):
            counts[m['id']]=counts.get(m['id'],0)+1
            if m['id']=='large' and counts[m['id']]==1:raise DoesNotFit('oom')
        self.run_session(behavior)
        r=next(r for r in self.app.store.all() if r['model_id']=='large')
        self.assertEqual(r['status'],'completed');self.assertEqual(r['execution_class'],'full_gpu')
        self.assertEqual(r['attempts'][0]['status'],'skipped')
    def test_unknown_placement_never_treated_as_hybrid(self):
        def behavior(b,m,c,mode):
            if m['id']=='large':raise UnverifiedPlacement('No report')
        self.run_session(behavior)
        self.assertEqual(len([e for e in self.events if e[0]=='load' and e[1]=='large']),1)
    def test_all_recovery_attempts_bounded_and_terminal(self):
        def behavior(b,m,c,mode):
            if m['id']!='good':raise DoesNotFit('oom')
        self.run_session(behavior)
        self.assertEqual(len([e for e in self.events if e[0]=='load' and e[1]=='large']),6)
        self.assertEqual(pending_plan(self.models,[self.test],self.target,self.app.store)['pending'],0)
    def test_stop_after_current_model_no_recovery(self):
        def behavior(b,m,c,mode):self.app.stop_after_model=True;raise DoesNotFit('oom')
        self.run_session(behavior)
        self.assertEqual(len([e for e in self.events if e[0]=='load']),1)
        p=pending_plan(self.models,[self.test],self.target,self.app.store)
        self.assertTrue(p['groups'][0]['jobs'][0]['recovery_only'])
    def test_deleting_hybrid_result_resumes_recovery_only(self):
        self.test_all_primary_models_before_smallest_first_recovery()
        r=next(r for r in self.app.store.all() if r['execution_class']=='cpu_offloaded')
        self.app.delete_result(r['model_id'],r['case_id'])
        p=pending_plan(self.models,[self.test],self.target,self.app.store)
        jobs=[j for g in p['groups'] for j in g['jobs']]
        self.assertEqual(len(jobs),1);self.assertTrue(jobs[0]['recovery_only'])
    def test_wrong_answers_not_retried(self):
        Fake=self.factory(lambda *a:None)
        def wrong(b,*a,**k):return {'text':'not-json','finish_reason':'stop','cached_tokens':0}
        with patch.object(Fake,'generate',wrong):Session(self.app,self.report,self.plan,Fake).run()
        records=self.app.store.all();self.assertEqual(len(records),3)
        self.assertTrue(all(r['status']=='completed' and not r['score']['valid'] for r in records))
        self.assertEqual(len([e for e in self.events if e[0]=='load']),3)
    def test_case_timeout_preserves_partial_is_terminal_and_continues(self):
        group=self.plan['groups'][0];second=copy.deepcopy(group['jobs'][0])
        second['case_id']='b'*64;second['variant']=copy.deepcopy(second['variant']);second['variant']['id']='second'
        group['jobs'].append(second);self.plan['pending']+=1
        Fake=self.factory(lambda *a:None);original=Fake.generate;calls={}
        def timeout_once(b,*a,**k):
            calls[b.mid]=calls.get(b.mid,0)+1
            if b.mid=='large' and calls[b.mid]==1:
                exc=RuntimeStall('Operational watchdog expired',{'timeout_seconds':60})
                exc.partial_response={'text':'partial answer','reasoning_text':'','finish_reason':None,
                                      'usage':{},'timings':{},'raw_chunks':[],'incomplete':True,'request_seconds':60}
                raise exc
            return original(b,*a,**k)
        with patch.object(Fake,'generate',timeout_once):Session(self.app,self.report,self.plan,Fake).run()
        large=[r for r in self.app.store.all() if r['model_id']=='large']
        self.assertEqual(len(large),2);timed=next(r for r in large if r.get('timed_out'))
        self.assertEqual(timed['status'],'completed');self.assertFalse(timed['score']['exact_match'])
        self.assertEqual(timed['calls'][0]['text'],'partial answer');self.assertEqual(timed['timeout_seconds'],60)
        self.assertEqual(calls['large'],2)
        self.assertEqual(pending_plan(self.models,[self.test],self.target,self.app.store)['pending'],0)
    def test_context_expands_once_and_preserves_attempt(self):
        Fake=self.factory(lambda *a:None);original=Fake.generate;called=set()
        def grow(b,*a,**k):
            if b.mid=='large' and b.mid not in called:
                called.add(b.mid);raise ContextCapacity('needs more',17000)
            return original(b,*a,**k)
        with patch.object(Fake,'generate',grow):Session(self.app,self.report,self.plan,Fake).run()
        large=[e for e in self.events if e[0]=='load' and e[1]=='large']
        self.assertEqual([e[-1] for e in large],[16384,32768])
        r=next(r for r in self.app.store.all() if r['model_id']=='large')
        self.assertEqual(r['attempts'][0]['reason'],'context_capacity')
    def test_cancel_does_not_enter_recovery(self):
        def behavior(b,m,c,mode):self.app.cancel_event.set();raise Cancelled('User stop')
        with self.assertRaises(Cancelled):self.run_session(behavior)
        self.assertEqual(len([e for e in self.events if e[0]=='load']),1)
        self.assertIsNone(self.app.backend)
    def test_cpu_usage_alone_is_not_a_skip_reason(self):
        self.run_session(lambda *a:None)
        self.assertTrue(all(r['status']=='completed' for r in self.app.store.all()))
    def test_logging_blocked_during_measured_work(self):
        Fake=self.factory(lambda *a:None);orig=Fake.generate
        def verify(b,*a,**k):
            with self.assertRaises(RuntimeError):self.app.flush_logs()
            return orig(b,*a,**k)
        with patch.object(Fake,'generate',verify):Session(self.app,self.report,self.plan,Fake).run()
        self.assertTrue(all(r['status']=='completed' for r in self.app.store.all()))

if __name__=='__main__':unittest.main()
