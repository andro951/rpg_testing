"""Audit immutable dot evidence and compare saved outcomes; never infer or rerun."""
from pathlib import Path
import collections,hashlib,json,os,sqlite3,sys,time,traceback,zlib
W=Path(__file__).resolve().parent;TASK=W.parent;OUT=TASK/'dot-path-v1-run';REPO=OUT/'desktop/repo'
sys.path[:0]=[str(REPO),str(TASK/'provider-runtime-deps'),str(TASK/'perchance-dependency-cache')]
from workbench.domain import ResultStore,digest
from evaluation.core import assess_record
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.pending');t.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8');os.replace(t,p)
def now():
 from datetime import datetime,timezone
 return datetime.now(timezone.utc).isoformat()
def key(r):return (r['model_id'],r['test_id'].split('__')[0],r['variant_id'],r['repetition'])
def controls():
 db=sqlite3.connect(TASK/'retrospective-work/evidence.sqlite');hashes=set(read(TASK/'selector-quote-revision/original-evidence-hashes.json').values())
 original={uid for uid,h in db.execute('select uid,raw_hash from refs')if h in hashes}
 optimized={uid for uid,src,jp in db.execute('select uid,source,json_pointer from refs')if not jp and src.startswith('E:\\Source\\Repos\\rpg_testing\\results\\')}
 old={};opt={}
 for uid,session,outcome,blob in db.execute('select uid,session,outcome,record from observations'):
  if uid not in original and uid not in optimized and session!='569edb88b72842c09ca78a3026deb28a':continue
  r=json.loads(zlib.decompress(blob));v={'uid':uid,'case_id':r['case_id'],'outcome':outcome,'raw_sha256':r.get('sha256'),'session':session,'artifact_identity':r.get('artifact_identity')}
  if uid in original:assert key(r)not in old;old[key(r)]=v
  if uid in optimized or session=='569edb88b72842c09ca78a3026deb28a':
   assert key(r)not in opt,(key(r),opt.get(key(r)),v);opt[key(r)]=v
 assert len(old)==930,len(old)
 assert len(opt)==1860,len(opt)
 return old,opt
OLD,OPT=controls();MAN=read(OUT/'prompt-manifest.json');WANTED={(r['test_id'],r['variant_id']):r['message_digest']for r in MAN['requests']}
CACHE={}
def transition(a,b):
 if a not in ('PASS','FAIL')or b not in ('PASS','FAIL'):return a+' -> '+b
 return {('PASS','PASS'):'preserved_pass',('FAIL','PASS'):'corrected_failure',('PASS','FAIL'):'regression',('FAIL','FAIL'):'remaining_failure'}[(a,b)]
def audit(root,worker):
 store=ResultStore(root);groups=collections.defaultdict(list)
 for path in root.glob('*/*.json'):groups[path.parent.name].append(path)
 results=[]
 for mid,paths in groups.items():
  if len(paths)!=186:continue
  signature=tuple(sorted((p.name,p.stat().st_size,p.stat().st_mtime_ns)for p in paths));cache_key=(worker,mid)
  if cache_key in CACHE and CACHE[cache_key][0]==signature:results.append(CACHE[cache_key][1]);continue
  pairs=[(p,store.read(p))for p in paths]
  ids=set();rows=[];counts=collections.Counter();changes=collections.Counter();optchanges=collections.Counter();noop=collections.Counter();warnings=[]
  for path,r in pairs:
   k=key(r);assert k not in ids,k;ids.add(k);assert r.get('simulated')is False
   if mid=='perchance-text-generator':
    # Existing adapter deliberately records provider/workflow provenance rather than app.run_provenance.
    # Bind this batch using the unchanged raw definition and actual sent-message hash below.
    assert r['variant_definition']['result']['representation']=='dot_patch_v1'
   else:assert r['provenance']['scope_digest']==MAN['scope_digest']
   assert not r['provenance'].get('optimized_guidance',False)
   expected=WANTED[(r['test_id'],r['variant_id'])]
   calls=r.get('calls',[]);assert len(calls)<=1,(mid,r['case_id'],'unexpected_extra_calls')
   if calls:
    call=calls[0];actual=call.get('request_messages')or call.get('messages');assert digest(actual)==expected,(mid,r['case_id'],'prompt_mismatch')
   else:warnings.append({'case_id':r['case_id'],'issue':'technical_outcome_without_sent_request_evidence','status':r['status']})
   assessment=assess_record(r);outcome=assessment['objective_outcome'];counts[outcome]+=1
   detail={'case_id':r['case_id'],'test_id':r['test_id'],'format':r['variant_id'],'repetition':r['repetition'],'outcome':outcome,'raw_sha256':r['sha256'],'raw_file':str(path),'prompt_sha256':expected,'status':r['status'],'timed_out':bool(r.get('timed_out')),'score_comparison':assessment.get('score_comparison'),'primary_reason':assessment.get('primary_reason'),'failures':[c for c in assessment.get('checks',[])if c.get('status')in('failed','FAIL')]}
   if assessment.get('score_comparison')=='disagreement':warnings.append({'case_id':r['case_id'],'issue':'new_record_summary_and_detailed_evaluator_disagree'})
   if k in OLD:
    detail['original930']=OLD[k];delta=transition(OLD[k]['outcome'],outcome)
    if k[1]=='db_v3_no_change':noop[delta]+=1
    else:changes[delta]+=1
   if k in OPT:detail['optimized_control']=OPT[k];optchanges[transition(OPT[k]['outcome'],outcome)]+=1
   rows.append(detail)
  assert len(ids)==186
  assert ids=={(mid,r['test_id'].split('__')[0],r['variant_id'],rep)for r in MAN['requests']for rep in range(r['repetitions'])},'Configured repetition matrix differs'
  result={'worker':worker,'model_id':mid,'records':186,'outcomes':dict(counts),'original930_matched_non_noop':sum(changes.values()),'original930_non_noop_transitions':dict(changes),'corrected_noop_transitions_separate':dict(noop),'optimized_control_transitions_separate':dict(optchanges),'original930_baseline_missing':not bool(changes),'warnings':warnings,'all_raw_checksums_and_unique_repetition_keys_verified':True,'actual_sent_requests_match_scope_where_present':True,'rows':rows,'at':now()}
  save(OUT/'audits'/worker/(mid+'.json'),result);compact={k:v for k,v in result.items()if k!='rows'};CACHE[cache_key]=(signature,compact);results.append(compact)
 return results
def once():
 rows=audit(REPO/'results','desktop')
 for folder in(OUT/'unity').iterdir():
  root=folder/'evidence/repo/results'
  if root.exists():rows.extend(audit(root,'unity'))
 recovery=read(OUT/'recovery/state.json')if(OUT/'recovery/state.json').exists()else None
 terminal=(recovery.get('stage')in('completed','blocked_storage_after_retry','native_retry_blocked','native_retry_error','provider_blocked'))if recovery else((OUT/'desktop/result.json').exists()or(OUT/'desktop/driver-error.json').exists())
 uc=read(OUT/'unity/collector-status.json')if(OUT/'unity/collector-status.json').exists()else{}
 complete=terminal and uc.get('phase')=='finished'
 counts={p.name:len(list(p.glob('*.json')))for p in(REPO/'results').iterdir()if p.is_dir()}
 report={'status':'terminal_audit'if complete else'ongoing','at':now(),'scope_digest':MAN['scope_digest'],'expected_cohorts':10,'audited_complete_cohorts':len(rows),'cohorts':rows,'desktop_terminal':terminal,'recovery_state':recovery,'saved_desktop_records_by_model':counts,'unity_collector':uc,'original930_noop_excluded_from_notation_only_attribution':True,'missing_original930_baselines':['desktop Qwen3.5-9B Q4_K_S','all Unity model/worker cohorts'],'all_old_scores_used_as_saved_not_regraded':True,'no_inference_or_reruns_by_auditor':True}
 save(OUT/'comparison-summary.json',report);return complete
try:
 while True:
  if once()or'--watch'not in sys.argv:break
  time.sleep(30)
except BaseException as exc:save(OUT/'audit-error.json',{'error':str(exc),'at':now(),'traceback':traceback.format_exc()});raise
