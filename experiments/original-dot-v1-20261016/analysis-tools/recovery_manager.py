from pathlib import Path
import json,os,subprocess,sys,time,traceback
W=Path(__file__).resolve().parent;ROOT=W.parent/'dot-path-v1-run';OUT=ROOT/'recovery';OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(v):
 p=OUT/'state.json';t=p.with_suffix('.pending');t.write_text(json.dumps(v,indent=2),encoding='utf8');os.replace(t,p)
def start(script,folder):
 folder.mkdir(exist_ok=True)
 return subprocess.Popen([sys.executable,'-I','-S','-B','-u',str(W/script)],cwd=W,stdout=(folder/'stdout.log').open('ab'),stderr=(folder/'stderr.log').open('ab'),creationflags=subprocess.CREATE_NO_WINDOW)
try:
 save({'stage':'waiting_for_recovery_validation','pid':os.getpid(),'native_pending':744,'provider_requested':186})
 while not(ROOT/'handoff/recovery-validation.json').exists():time.sleep(3)
 assert read(ROOT/'handoff/recovery-validation.json')['status']=='passed'
 assert not(ROOT/'provider-only/launch-receipt.json').exists(),'Inspect existing continuation; never duplicate'
 save({'stage':'starting_provider','pid':os.getpid(),'native_completed':186,'native_pending':744,'provider_requested':186,'native_retry_after_provider_authorized':True})
 provider=start('provider_driver.py',ROOT/'provider-only');save({'stage':'provider_running','pid':os.getpid(),'provider_pid':provider.pid,'native_completed':186,'native_pending':744})
 while provider.poll()is None:time.sleep(3)
 p=ROOT/'provider-only/result.json'
 if provider.returncode or not p.exists()or read(p)['status']not in('finished','finished_with_errors'):
  save({'stage':'provider_blocked','provider_exit_code':provider.returncode,'native_pending':744,'no_native_retry_before_provider_complete':True});raise SystemExit(1)
 save({'stage':'starting_authorized_native_retry','provider_observations':read(p)['observations'],'native_pending':744})
 native=start('native_retry.py',ROOT/'native-retry');save({'stage':'native_retry_running','native_pid':native.pid,'provider_observations':186,'native_pending':744})
 while native.poll()is None:time.sleep(3)
 p=ROOT/'native-retry/result.json';status=read(p)['status']if p.exists()else'native_retry_error'
 save({'stage':'blocked_storage_after_retry'if status=='blocked_storage'else'native_retry_blocked'if status=='blocked_load_failure'else'completed'if native.returncode==0 and status in('finished','finished_with_errors')else'native_retry_error','native_exit_code':native.returncode,'native_result_status':status,'provider_observations':186,'no_further_automatic_retry':True})
except BaseException as exc:
 if not isinstance(exc,SystemExit):(OUT/'manager-error.json').write_text(json.dumps({'error':str(exc),'traceback':traceback.format_exc()},indent=2),encoding='utf8')
 raise
