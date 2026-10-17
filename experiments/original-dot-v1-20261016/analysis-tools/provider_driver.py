"""Provider-only continuation of the sealed experiment; frozen adapter unchanged."""
from pathlib import Path
import collections,copy,hashlib,json,os,sys,threading,traceback,uuid
W=Path(__file__).resolve().parent;TASK=W.parent;ROOT=TASK/'dot-path-v1-run';REPO=ROOT/'desktop/repo';OUT=ROOT/'provider-only';DEPS=TASK/'provider-runtime-deps';PW=TASK/'perchance-dependency-cache'
sys.path[:0]=[str(W),str(REPO),str(DEPS),str(PW)];os.environ['PYTHONPATH']=os.pathsep.join([str(REPO),str(DEPS),str(PW)]);os.environ['PYTHONNOUSERSITE']='1';sys.stdout.reconfigure(encoding='utf8');sys.stderr.reconfigure(encoding='utf8');os.chdir(REPO)
from provider_once import AttemptLedger,unattempted
from windows_process import is_running
from workbench.controller import Controller
from workbench.domain import read_json,digest
from workbench.judgements import review_lock,load_tests
from workbench.workflows import messages,repetition_seed,Cancelled
from workbench import perchance
from workbench.perchance_connection import ControlledBrowserBackend
from evaluation.core import assess_record
OUT.mkdir(exist_ok=True);ledger=AttemptLedger(OUT/'claims');ended=threading.Event();app=None;mapping={};execution=uuid.uuid4().hex
def now():
 from datetime import datetime,timezone
 return datetime.now(timezone.utc).isoformat()
def save(name,v):
 p=OUT/name;t=p.with_suffix(p.suffix+'.pending');t.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8');os.replace(t,p)
def alive(pid):
 return is_running(pid)
class OnceBackend(ControlledBrowserBackend):
 def open(self):
  super().open();save('launch-receipt.json',{'execution_id':execution,'pid':os.getpid(),'scope_digest':read_json(ROOT/'prompt-manifest.json')['scope_digest'],'provider_browser_and_plugin_ready':True,'at':now(),'requested_observations':186,'continuation_of_native_session':'953abdbffbe0473ebeb21a67fc4029fe','old_native_driver_terminated':True,'native_models_not_loaded':True,'deadline_seconds':300})
 def generate(self,prompt,requested,schema,cancel):
  key=(digest(prompt),requested['seed']);assert key in mapping,'Request is outside sealed scope';job=mapping[key];cid=job['case_id'];assert schema is None and requested['temperature']==0 and requested['top_p']==1
  ledger.begin(cid,{'execution_id':execution,'at':now(),'prompt_digest':key[0],'requested_sampling':requested,'repetition':job['repetition'],'independent_service_trial':True,'seed_effect_unverified':True})
  try:
   response=super().generate(prompt,requested,schema,cancel);ledger.finish(cid,{'at':now(),'response':response});return response
  except BaseException as exc:
   ledger.finish(cid,{'at':now(),'error':str(exc),'type':type(exc).__name__,'partial_response':getattr(exc,'partial_response',{})});raise
def watch():
 while not ended.wait(2):
  if(OUT/'stop.request').exists():app.control('stop')
  if(OUT/'pause.request').exists()and not app.pause_requested:app.control('pause')
  save('run-status.json',{'execution_id':execution,'pid':os.getpid(),'at':now(),'state':app.state,'processed':app.run_processed,'total':app.run_total,'current':app.current,'progress':app.progress,'errors':app.session_errors,'automatic_activity_pause':False})
def main():
 global app,mapping
 assert not alive(1292)and not alive(46324),'Original driver/model owner must end before handoff'
 assert read_json(ROOT/'desktop/driver-error.json')['type']=='Cancelled'
 dep=read_json(DEPS/'manifest.json');assert dep['status']=='complete'
 for rel,h in dep['files'].items():assert hashlib.sha256((DEPS/rel).read_bytes()).hexdigest()==h,rel
 source=read_json(REPO/'source-manifest.json')
 for rel,h in source['files'].items():assert hashlib.sha256((REPO/rel).read_bytes()).hexdigest()==h,rel
 app=Controller(REPO);app.settings.update(sync_source=False,publish_results=False);app.state='preparing_provider'
 watcher=threading.Thread(target=watch,daemon=True);watcher.start()
 try:
  with review_lock(REPO):
   cached=read_json(ROOT/'desktop/launch-preflight.json');assert 7.5<=cached['gpu']['total_gib']<=8.25
   target={'backend':'perchance','vram_gb':8,'gpu_name':cached['gpu']['name'],'os':cached['plan']['target']['os'],'execution_class':'remote_service','execution_policy':perchance.VERSION}
   tests=[read_json(REPO/name)for name in sorted(source['files'])if name.startswith('test_specs/')and name.endswith('.json')];assert len(tests)==21;pending=perchance.plan(tests,app.settings,target,app.store,{'model_id':perchance.MODEL_ID})
   assert len(pending['groups'])==186 and pending['collapsed_cases']==0
   if(OUT/'plan.json').exists():assert{g['case_id']for g in pending['groups']}=={g['case_id']for g in read_json(OUT/'plan.json')['groups']},'Frozen continuation identity changed'
   wanted={(p['test_id'],p['variant_id']):p['message_digest']for p in read_json(ROOT/'prompt-manifest.json')['requests']}
   for g in pending['groups']:
    v=g['variant'];msg=messages(g['test'],v['steps'][0],{},v);md=digest(msg);assert md==wanted[(g['test']['id'],v['id'])];assert len(v['steps'])==1 and g['test']['timeout_seconds']==300
    key=(md,repetition_seed(v['steps'][0]['sampling']['seed'],g['repetition']));assert key not in mapping;mapping[key]=g
   remaining=unattempted(pending['groups'],app.store,perchance.MODEL_ID,ledger);remaining_ids={g['case_id']for g in remaining}
   for g in pending['groups']:g['done']=g['case_id']not in remaining_ids
   pending['pending']=len(remaining);pending['complete']=186-len(remaining);save('plan.json',pending)
   if '--validate-plan-only'in sys.argv:
    save('plan-validation.json',{'status':'passed','configured_observations':186,'pending':len(remaining),'distinct_prompt_seed_pairs':len(mapping),'scope_digest':read_json(ROOT/'prompt-manifest.json')['scope_digest'],'source_files_byte_verified':len(source['files']),'real_inference':False});print('Frozen provider plan validated: 186 independent cases, no generation.',flush=True);return
   from workbench.perchance_setup import health
   setup=health(app);save('setup-health.json',setup);assert setup['ready'],setup['reason']
   app.report={'ready':True,'remote_provider':True,'selection':pending['selection'],'issues':[],'plan':{k:v for k,v in pending.items()if k!='groups'},'gpu':cached['gpu'],'folder':{'path':None,'source':'Remote service: no GGUFs'}};app.plan=pending;app.state='running';app.started=now()
   perchance.run(app,app.report,pending,backend_factory=OnceBackend)
   rows=[app.store.read(p)for p in(app.store.root/perchance.MODEL_ID).glob('*.json')];expected={g['case_id']for g in pending['groups']}
   assert{r['case_id']for r in rows}==expected,'Missing/uncertain trials stay pending; never reroll claims automatically'
   status='cancelled'if app.cancel_event.is_set()else'finished_with_errors'if app.session_errors else'finished'
   save('result.json',{'status':status,'execution_id':execution,'observations':len(rows),'outcomes':dict(collections.Counter(assess_record(r)['objective_outcome']for r in rows)),'statuses':dict(collections.Counter(r['status']for r in rows)),'timeouts':sum(bool(r.get('timed_out'))for r in rows),'claims':len(list(ledger.root.glob('*.started.json'))),'scope_digest':read_json(ROOT/'prompt-manifest.json')['scope_digest'],'finished':now(),'native_pending':744,'no_completed_native_or_provider_cases_rerun':True});app.state=status
 finally:ended.set();watcher.join(5);app.flush_logs()
try:main()
except BaseException as exc:save('driver-error.json',{'error':str(exc),'type':type(exc).__name__,'at':now(),'traceback':traceback.format_exc(),'no_automatic_retry':True});raise
