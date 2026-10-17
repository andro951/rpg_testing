"""Analyze saved failures only. Never changes scores, prompts, raw files or runs."""
from pathlib import Path
import collections,json,re,sys
W=Path(__file__).resolve().parent;OUT=W.parent/'dot-path-v1-run';REPO=OUT/'desktop/repo'
sys.path[:0]=[str(REPO),str(W.parent/'provider-runtime-deps')]
from workbench import dot_paths
from workbench.domain import ResultStore
store=ResultStore(REPO/'results')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def category(text,row,r):
 try:patch=json.loads(text)
 except (ValueError,TypeError):
  return ('outer_json_markdown_fence'if text.strip().startswith('```')else'outer_json_missing_operation_braces'if re.match(r'\[\s*"op"\s*:',text.strip())else'outer_json_other'),None
 if not isinstance(patch,list):return 'operation_array_or_object_structure',patch
 errors=[]
 for op in patch:
  if not isinstance(op,dict):return 'operation_array_or_object_structure',patch
  for field in (('path','from')if op.get('op')in('move','copy')else('path',)):
   value=op.get(field)
   if isinstance(value,str)and('/'in value):errors.append('path_retains_slash_notation')
   elif isinstance(value,str)and(value.startswith('@')or'.@'in value):errors.append('path_uses_at_marker')
   else:
    try:dot_paths.tokens(value)
    except (ValueError,TypeError):errors.append('other_dot_path_syntax')
 if errors:return sorted(set(errors))[0],patch
 reason=row.get('primary_reason')or''
 if reason.startswith('Missing or undefined property: '):
  absent=reason.split(': ',1)[1];initial=r['test_definition']['source']['initial_state'];schema=r['test_definition']['state_schema']
  for field,collection in initial.items():
   node=schema['properties'][field]
   if isinstance(collection,list):
    if any(dot_paths.scalar_text(dot_paths.value_paths.identity(e,node))==absent for e in collection):return 'missing_source_collection_prefix',patch
  return 'wrong_field_or_selector',patch
 if reason.startswith('Plain selector ')or reason.startswith('Ambiguous plain selector'):return 'wrong_identity_or_positional_selector',patch
 if reason.startswith('This contract requires these operation names'):return 'wrong_operation_name',patch
 if reason.startswith('The current data already equals the expected state'):return 'noop_unnecessary_change',patch
 if reason.startswith('Remove path must select a collection element'):return 'wrong_operation_path_role',patch
 if "is not of type 'string'"in reason:return 'wrong_element_value_type',patch
 if any(f.get('code')=='patch.final_state'for f in row.get('failures',[])):return 'semantic_final_state',patch
 return 'operation_role_value_schema_or_other_semantic',patch
allrows=[];summaries=[]
for audit_path in sorted((OUT/'audits').glob('*/*.json')):
 audit=read(audit_path)
 if audit_path.name!=audit['model_id']+'.json':continue
 counts=collections.Counter();bytest=collections.Counter();groups={};failures=[]
 for row in audit['rows']:
  if row['outcome']=='PASS':continue
  raw=Path(row['raw_file']);r=store.read(raw);calls=r.get('calls',[]);text=calls[0].get('text','')if calls else''
  cat,patch=category(text,row,r);counts[cat]+=1;bytest[(cat,row['test_id'],row['format'])]+=1
  record={'worker':audit['worker'],'model_id':audit['model_id'],'case_id':row['case_id'],'test_id':row['test_id'],'format':row['format'],'repetition':row['repetition'],'category':cat,'strict_outcome_unchanged':row['outcome'],'score_comparison':row.get('score_comparison'),'primary_reason':row.get('primary_reason'),'validation_failures':row['failures'],'model_output':text,'actual_messages':calls[0].get('request_messages')or calls[0].get('messages')if calls else None,'initial_state':r['test_definition']['source']['initial_state'],'state_schema':r['test_definition']['state_schema'],'expected_state':r['test_definition'].get('expected_state'),'raw_file':str(raw),'raw_sha256':r['sha256'],'noop_excluded_from_original_notation_attribution':row['test_id'].startswith('db_v3_no_change__')}
  if cat=='outer_json_markdown_fence':
   # Analytical counterfactual only: never alters a raw response or a strict grade.
   match=re.fullmatch(r'```(?:json)?\s*\n?(.*?)\n?```',text.strip(),re.S)
   diagnostic={'strict_outcome_remains_failed':True,'purpose':'Determine whether a fence also hides a path/application error; not a benchmark score'}
   try:
    assert match,'Fence not recognized';inner=json.loads(match.group(1));state=dot_paths.apply(record['initial_state'],inner,record['state_schema'])
    diagnostic.update(inner_json_valid=True,application_succeeded=True,exact_expected_state_match=state==record['expected_state'])
   except Exception as exc:diagnostic.update(application_succeeded=False,error=str(exc))
   record['fence_content_diagnostic']=diagnostic
  if audit['worker']=='unity':
   content=patch
   if cat=='outer_json_markdown_fence':
    try:content=json.loads(match.group(1))
    except Exception:content=None
   flags={'markdown_fence':cat=='outer_json_markdown_fence','slash_path':False,'missing_collection_prefix':False}
   if isinstance(content,list):
    for operation in content:
     if not isinstance(operation,dict):continue
     for field in (('path','from')if operation.get('op')in('move','copy')else('path',)):
      path=operation.get(field)
      if not isinstance(path,str):continue
      flags['slash_path']|='/'in path
      for collection_name,collection in record['initial_state'].items():
       node=record['state_schema']['properties'][collection_name]
       if isinstance(collection,list)and any(dot_paths.scalar_text(dot_paths.value_paths.identity(e,node))==path for e in collection):flags['missing_collection_prefix']=True
   record['overlapping_path_and_wrapper_flags']=flags
  failures.append(record)
  key=(cat,row['test_id'],row['format'],text)
  if key not in groups:groups[key]={'category':cat,'test_id':row['test_id'],'format':row['format'],'output':text,'primary_reason':row.get('primary_reason'),'count':0,'case_ids':[]}
  groups[key]['count']+=1;groups[key]['case_ids'].append(row['case_id'])
 allrows.extend(failures)
 summaries.append({'worker':audit['worker'],'model_id':audit['model_id'],'observations':audit['records'],'outcomes':audit['outcomes'],'failed_records_inspected':len(failures),'categories':dict(counts),'all_failures_outer_json_valid':not any(c.startswith('outer_json')for c in counts),'unique_examples':list(groups.values()),'no_benchmark_recovery_or_score_changes':True})
v={'scope_digest':read(OUT/'prompt-manifest.json')['scope_digest'],'complete_cohorts_analyzed':len(summaries),'strict_scores_unchanged':True,'no_inference_reruns_prompt_or_parser_changes':True,'records':allrows,'summaries':summaries}
p=OUT/'failure-analysis.json';p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps([{k:v for k,v in s.items()if k!='unique_examples'}for s in summaries],indent=2))
