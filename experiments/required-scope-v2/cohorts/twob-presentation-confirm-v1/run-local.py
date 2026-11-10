import datetime,hashlib,json,os,sys,time,traceback
from pathlib import Path
base=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task\twob-presentation-confirm-v1');root=base/'desktop';sys.path.insert(0,str(root));from workbench.controller import Controller
model='local-2542aed68e6bb077';manifest=json.loads((base/'manifest.json').read_text(encoding='utf8'));validation=json.loads((base/'validation.json').read_text(encoding='utf8'));pre=json.loads((root/'preflight-receipt.json').read_text(encoding='utf8'));assert validation['requests']==6 and pre['ready'] and len(pre['groups'])==1 and pre['groups'][0]['model']==model and pre['groups'][0]['jobs']==6 and pre['groups'][0]['context']['allocated_tokens']==32768
assert not list((root/'results'/model).glob('*.json'))
deadline=datetime.datetime(2026,11,4,21,40,tzinfo=datetime.timezone.utc).timestamp();assert time.time()<deadline
receipt=root/('launch-receipt-'+model+'.json')
with receipt.open('x',encoding='utf8') as f:json.dump({'pid':os.getpid(),'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cohort':manifest['cohort'],'scope_digest':manifest['scope_digest'],'fixtures':3,'methods':1,'presentations_per_method':6,'repetitions':1,'local_models':1,'provider':'deferred; previous CDP failure' ,'deadline_utc':'2026-11-04T21:40:00Z','prior_results_reused':0},f,indent=2)
def save(s):
 print(json.dumps(s,default=str),flush=True)
try:
 from workbench import perchance_setup
 def defer_blocked_provider(app,preparation=None,selection=None,reuse=False,force_pending=False):
  app.perchance_setup_decision={'id':'deferred-after-cdp-error','context':{'selection':selection,'preparation':preparation},'consumed':reuse,'status':'declined','reason':'Perchance deferred after CDP timeout and denied process inspection; continuing authorized local work.','time':time.time()}
 perchance_setup.prepare=defer_blocked_provider
 app=Controller(root);app.start('run', {'selection': {'model_id':model}});stop=False
 while app.thread.is_alive():
  s=app.snapshot();save({'pid':os.getpid(),'state':s['state'],'message':s['message'],'current':s.get('current'),'progress':s.get('progress'),'failure':s.get('failure'),'completed_now':s.get('completed_now'),'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
  if not stop and time.time()>=deadline:app.control('stop');stop=True
  time.sleep(5)
 app.thread.join();s=app.snapshot();save({'pid':os.getpid(),'state':s['state'],'message':s['message'],'failure':s.get('failure'),'completed_now':s.get('completed_now'),'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
except BaseException as e:save({'pid':os.getpid(),'state':'wrapper_error','error':str(e),'traceback':traceback.format_exc()});raise
