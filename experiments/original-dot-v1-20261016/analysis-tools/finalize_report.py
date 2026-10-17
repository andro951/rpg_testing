"""Finalize read-only analysis of the completed authorized experiment."""
from pathlib import Path
import collections,hashlib,json,sys
W=Path(__file__).resolve().parent;OUT=W.parent/'dot-path-v1-run';REPO=OUT/'desktop/repo'
sys.path.insert(0,str(REPO))
from workbench.domain import ResultStore
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
comparison=read(OUT/'comparison-summary.json');assert comparison['status']=='terminal_audit'and comparison['audited_complete_cohorts']==10
assert read(OUT/'native-retry/result.json')['status']=='finished'
assert read(OUT/'recovery/state.json')['stage']=='completed'
analysis=read(OUT/'failure-analysis.json');assert analysis['complete_cohorts_analyzed']==10
labels={'local-2542aed68e6bb077':'Qwen3.5-2B Q8_0','local-28df315996a77e69':'Qwen3.5-4B Q8_0','local-81e2a88130ccfa4e':'Qwen3.5-9B Q4_K_M','local-8c5e666555c53096':'Qwen3.5-9B Q4_K_S','local-cb6dd200423a32cc':'Qwen3-VL-8B-Instruct Q4_K_M','perchance-text-generator':'Perchance Text Generator (remote model unknown)','qwen35-9b-q4_k_m':'Qwen3.5-9B Q4_K_M','qwen35-9b-q8_0':'Qwen3.5-9B Q8_0','qwen35-27b-ud-iq2_xxs':'Qwen3.5-27B UD-IQ2_XXS','qwen35-27b-iq2_m-bartowski':'Qwen3.5-27B IQ2_M (Bartowski)'}
rows=[];total_calls=0;artifact_pairs=0;all_ids=set();store=ResultStore(REPO/'results')
for compact in comparison['cohorts']:
 mid=compact['model_id'];worker=compact['worker'];a=read(OUT/'audits'/worker/(mid+'.json'));assert not a['warnings']and a['records']==186
 for row in a['rows']:
  assert row['score_comparison']=='agrees'
  r=store.read(Path(row['raw_file']));assert r['simulated']is False and len(r['calls'])==1
  assert r['status']=='completed'and not r.get('timed_out',False)
  unique=(worker,mid,r['case_id']);assert unique not in all_ids;all_ids.add(unique);total_calls+=len(r['calls'])
  if'original930'in row:assert r['artifact_identity']==row['original930']['artifact_identity'];artifact_pairs+=1
 old=a['original930_non_noop_transitions'];noop=a['corrected_noop_transitions_separate'];opt=a['optimized_control_transitions_separate']
 pair=lambda x:{'old_pass':x.get('preserved_pass',0)+x.get('regression',0),'new_pass':x.get('preserved_pass',0)+x.get('corrected_failure',0),'corrected_failures':x.get('corrected_failure',0),'regressions':x.get('regression',0),'remaining_failures':x.get('remaining_failure',0)}
 f=next(s for s in analysis['summaries']if s['worker']==worker and s['model_id']==mid)
 rows.append({'worker':worker,'model_id':mid,'model':labels[mid],'observations':186,'strict_pass':a['outcomes'].get('PASS',0),'strict_fail':a['outcomes'].get('FAIL',0),'original930_unchanged_177':dict(observations=177,**pair(old))if old else None,'corrected_noop_separate_9':dict(observations=9,**pair(noop))if noop else None,'optimized_control_pass_186':opt.get('preserved_pass',0)+opt.get('regression',0),'optimized_transitions_secondary':opt,'failure_categories':f['categories']})
assert len(rows)==10 and len(all_ids)==total_calls==1860 and artifact_pairs==930
u=[r for r in analysis['records']if r['worker']=='unity'];assert len(u)==246
flags=collections.Counter(tuple(r['overlapping_path_and_wrapper_flags'].items())for r in u)
archives=[]
for p in sorted((OUT/'desktop/completed-cohorts').glob('*.tar.gz')):
 receipt=read(p.with_name(p.name.removesuffix('.tar.gz')+'.receipt.json'));assert hashlib.sha256(p.read_bytes()).hexdigest()==receipt['sha256'];archives.append({'worker':'desktop',**receipt})
assert len(archives)==6
for p in sorted((OUT/'unity').glob('*/collection-receipt.json')):archives.append({'worker':'unity','receipt_file':str(p),**read(p)})
assert len(archives)==10
v={'status':'complete','independent_utc_completion_check':sys.argv[1],'scope_digest':comparison['scope_digest'],'original930_baseline':{'finished':'2026-10-15 15:34:03 EDT','observations':930,'evidence_hash_manifest_sha256':'9c17ff3243415ce6fc427b40871d4672e321b7ff357f517b0aef2bf07d584a95'},'observations':1860,'scored_benchmark_calls':total_calls,'unique_cases':len(all_ids),'strict_pass':sum(r['strict_pass']for r in rows),'strict_fail':sum(r['strict_fail']for r in rows),'timeouts':0,'infrastructure_errors_in_scored_observations':0,'all_raw_checksums_actual_prompts_and_62_by_3_matrices_verified':True,'exact_recorded_artifact_identity_equal_in_all_930_original_pairs':True,'all_detailed_and_stored_grades_agree':True,'rows':rows,'unity_failed_cases_reviewed':246,'unity_failure_primary_categories':dict(collections.Counter(r['category']for r in u)),'unity_overlapping_failure_flags':[{'flags':dict(k),'observations':n}for k,n in flags.items()],'unity_fence_content_diagnostics':{'fences':36,'content_reaches_exact_expected_state':sum(r.get('fence_content_diagnostic',{}).get('exact_expected_state_match')is True for r in u),'also_missing_collection_prefix':3,'strict_scores_unchanged':True},'interpretation_limits':['Corrected unrelated-information NOOP task is excluded from notation-only original930 attribution.','No original930 baseline exists for desktop Q4_K_S or any Unity model/worker cohort.','Optimized controls use different instruction wording and are a secondary comparison, not a clean notation-only baseline.','Independent repetitions remain separate; Perchance seed effect, remote model and provider defaults remain unverified.','Only output method/path notation changed; all three input representations retain original display forms.','Historical disk Event 7 diagnostics and interrupted original native load are preserved separately. No new storage error was observed during the authorized continuation; hardware health is not established.','Windows raw timestamps run approximately twelve minutes ahead of independent UTC and Unity; all raw timestamps are retained.'],'no_prompts_grading_or_results_modified_by_analysis':True,'no_additional_inference_or_reruns_by_analysis':True,'evidence_archives':archives,'supporting_artifacts':{'comparison':str(OUT/'comparison-summary.json'),'all_failure_prompts_outputs_expected_states_and_errors':str(OUT/'failure-analysis.json'),'perchance_independent_trial_verification':str(OUT/'provider-only/completion-verification.json'),'native_continuation_result':str(OUT/'native-retry/result.json'),'full_code_tests':str(W/'full-tests-summary.json')}}
p=OUT/'final-report.json';assert not p.exists(),'Preserve existing final report';p.write_text(json.dumps(v,indent=2),encoding='utf8')
manifest={str(x.relative_to(OUT)):{'sha256':hashlib.sha256(x.read_bytes()).hexdigest(),'bytes':x.stat().st_size}for x in [p,OUT/'comparison-summary.json',OUT/'failure-analysis.json',OUT/'provider-only/completion-verification.json',OUT/'native-retry/result.json']}
(OUT/'final-report-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in v.items()if k not in('evidence_archives','supporting_artifacts')},indent=2))
