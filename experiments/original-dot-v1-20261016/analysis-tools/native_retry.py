"""One user-authorized continuation after Perchance; never repeats terminal cases."""
from pathlib import Path
import copy,hashlib,json,os,platform,subprocess,sys,threading,time,traceback
W=Path(__file__).resolve().parent;TASK=W.parent;ROOT=TASK/'dot-path-v1-run';REPO=ROOT/'desktop/repo';OUT=ROOT/'native-retry';OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(REPO),str(TASK/'provider-runtime-deps'),str(TASK/'perchance-dependency-cache')];sys.stdout.reconfigure(encoding='utf8');sys.stderr.reconfigure(encoding='utf8');os.chdir(REPO)
from workbench.controller import Controller
from workbench.domain import read_json,implementation_fingerprint
from workbench.judgements import review_lock
from workbench.scheduler import Session
from workbench.native import NativeBackend
from workbench.workflows import Cancelled
app=None;ended=threading.Event();fault=None;baseline=0
def now():
 from datetime import datetime,timezone
 return datetime.now(timezone.utc).isoformat()
def save(name,v):
 p=OUT/name;t=p.with_suffix(p.suffix+'.pending');t.write_text(json.dumps(v,indent=2),encoding='utf8');os.replace(t,p)
def storage_events():
 import xml.etree.ElementTree as ET
 query="*[System[Provider[@Name='disk'] and (EventID=7)]]"
 r=subprocess.run([r'C:\Windows\System32\wevtutil.exe','qe','System','/q:'+query,'/f:xml','/rd:true','/c:20'],capture_output=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW);assert r.returncode==0,r.stderr.decode(errors='replace')
 text=r.stdout.decode('utf-16'if r.stdout.startswith((b'\xff\xfe',b'\xfe\xff'))else'utf-8-sig');ns={'e':'http://schemas.microsoft.com/win/2004/08/events/event'};events=[]
 for event in ET.fromstring('<Events>'+text+'</Events>'):
  devices=[x.text for x in event.findall('e:EventData/e:Data',ns)if x.text and'Harddisk1\\DR1'in x.text]
  if devices:events.append({'RecordId':int(event.find('e:System/e:EventRecordID',ns).text),'TimeCreated':event.find('e:System/e:TimeCreated',ns).attrib['SystemTime'],'Id':7,'Message':'Disk Event 7 for '+devices[0],'event_xml':ET.tostring(event,encoding='unicode')})
 return events
class Fixed(Session):
 def load(self,g,*args,**kwargs):
  global fault
  assert self.contexts[g['model']['id']]['allocated_tokens']==32768
  try:
   for path,pin in zip(g['installed']['paths'],g['model']['artifact_identity']['files']):
    stat=Path(path).stat();assert stat.st_size==pin['size_bytes']and stat.st_mtime_ns==pin['mtime_ns'],'Artifact pin changed'
   return super().load(g,*args,**kwargs)
  except Cancelled:raise
  except Exception as exc:
   fault=fault or{'reason':'runtime_load_qualification_failure_on_authorized_retry','error':str(exc),'type':type(exc).__name__,'model_id':g['model']['id'],'at':now()};save('load-blocker.json',fault);app.cancel_event.set();raise Cancelled('Single authorized retry could not qualify loading; unrun observations remain pending')from exc
def watch():
 global fault
 last=0
 while not ended.wait(2):
  if(OUT/'stop.request').exists():app.control('stop')
  if time.monotonic()-last>=15:
   last=time.monotonic()
   try:
    new=[e for e in storage_events()if int(e['RecordId'])>baseline]
    if new:
     fault={'reason':'renewed_disk_event_7_after_authorized_retry','events':new,'file_causality_not_established':True,'at':now()};save('storage-blocker.json',fault);app.control('stop')
   except Exception as exc:save('storage-monitor-error.json',{'error':str(exc),'at':now()})
  save('run-status.json',{'pid':os.getpid(),'at':now(),'state':app.state,'processed':app.run_processed,'total':app.run_total,'current':app.current,'progress':app.progress,'errors':app.session_errors,'storage_failure':fault,'automatic_activity_pause':False})
def main():
 global app,baseline
 provider=read_json(ROOT/'provider-only/result.json');assert provider['observations']==186 and provider['status']in('finished','finished_with_errors')
 assert not(OUT/'launch-receipt.json').exists(),'Do not loop authorized native retry'
 old=read_json(ROOT/'desktop/launch-preflight.json')
 while not(OUT/'frozen-native-plan.json').exists():
  if(OUT/'plan-preparation-error.json').exists():raise RuntimeError(read_json(OUT/'plan-preparation-error.json')['error'])
  time.sleep(2)
 plan=read_json(OUT/'frozen-native-plan.json');app=Controller(REPO);app.settings.update(sync_source=False,publish_results=False)
 for g in plan['groups']:g['jobs']=[j for j in g['jobs']if not app.store.done(g['model']['id'],j['case_id'])]
 groups=[g for g in plan['groups']if g['jobs']];assert len(groups)==4 and sum(len(g['jobs'])for g in groups)==744
 plan['pending']=744;plan['perchance_plan']=None;app.report=old;app.plan=plan
 events=storage_events();baseline=max((int(e['RecordId'])for e in events),default=0);save('storage-baseline.json',{'maximum_event_record_id':baseline,'events':events,'at':now()})
 with review_lock(REPO):
  app.state='running';app.started=now();app.run_provenance={'backend_version':old['target']['backend_version']if'target'in old else plan['target']['backend_version'],'python':platform.python_version(),'source_commit':None,'workflow_code':app.workflow_code(),'raw_implementation':implementation_fingerprint(),'selection':None,'experiment':'original930-plus-dot_patch_v1','scope_digest':read_json(ROOT/'prompt-manifest.json')['scope_digest'],'original_wording':True,'optimized_guidance':False,'continuation_of':'953abdbffbe0473ebeb21a67fc4029fe','native_retry_authorized_after_perchance':True,'automatic_activity_pause':False}
  session=Fixed(app,old,plan,NativeBackend);save('launch-receipt.json',{'pid':os.getpid(),'session_id':session.id,'at':now(),'pending':744,'completed_VL_and_Perchance_not_rerun':True,'source_scope':app.run_provenance['scope_digest'],'retry_ordinal':1})
  watcher=threading.Thread(target=watch,daemon=True);watcher.start()
  try:session.run()
  except Cancelled:
   if not fault:raise
  finally:ended.set();watcher.join(12);app.flush_logs()
  save('result.json',{'status':('blocked_storage'if fault['reason']=='renewed_disk_event_7_after_authorized_retry'else'blocked_load_failure')if fault else'finished_with_errors'if app.session_errors else'finished','at':now(),'session_id':session.id,'processed':app.run_processed,'storage_failure':fault,'errors':app.session_errors,'unrun_cases_remain_pending':True,'no_further_automatic_heavy_read_retry':True})
try:main()
except BaseException as exc:save('driver-error.json',{'error':str(exc),'type':type(exc).__name__,'at':now(),'traceback':traceback.format_exc(),'no_automatic_retry':True});raise
