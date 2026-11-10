import collections,hashlib,json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;root=b/'desktop';sys.path.insert(0,str(root))
from workbench.domain import ResultStore,digest
from workbench.workflows import messages
from evaluation.core import assess_record
model='local-28df315996a77e69';man=json.loads((b/'manifest.json').read_text(encoding='utf8'));want={(x['test_id'],x['variant_id']):x for x in man['requests']};tests={p.stem:json.loads(p.read_text(encoding='utf8')) for p in (b/'test_specs').glob('*.json')};store=ResultStore(root/'results');paths=sorted((store.root/model).glob('*.json'));assert len(paths)==162
repo=Path(r'E:\Source\Repos\rpg_testing\experiments\required-scope-v2\runs');old={}
for cohort in man['source_cohorts']:
 d=repo/cohort/'desktop'/model;a=json.loads((d/'audit.json').read_text(encoding='utf8'));old[cohort]=(d,{(x['test_id'],x['variant_id'],x['repetition']):x for x in a['evidence']})
seen=set();pairs=[];evidence=[]
for p in paths:
 r=store.read(p);t=tests[r['test_id']];v=next(x for x in t['variants'] if x['id']==r['variant_id']);spec=want[(t['id'],v['id'])];req=messages(t,v['steps'][0],{},v);assert digest(req)==spec['message_digest'];calls=r.get('calls',[]);assert (calls and calls[0]['messages']==req) or (not calls and (r.get('timed_out') or r.get('status') in ('error','aborted')))
 k=(spec['source_cohort'],spec['baseline_test_id'],v['id'],r['repetition']);assert k not in seen;seen.add(k);d,items=old[k[0]];e=items[(k[1],k[2],k[3])];oldpath=d/e['path'];oldrecord=json.loads(oldpath.read_text(encoding='utf8'));checksum=oldrecord.pop('sha256');assert digest(oldrecord)==checksum and hashlib.sha256(oldpath.read_bytes()).hexdigest()==e['sha256'];assert oldrecord['artifact_identity']==r['artifact_identity'] and oldrecord['target']==r['target'];assert oldrecord['load']['context']['allocated_tokens']==r['load']['context']['allocated_tokens']==32768
 if oldrecord.get('calls') and calls:assert oldrecord['calls'][0]['sampling']==calls[0]['sampling']
 for field in ('source','state_schema','expected_state'):assert oldrecord['test_definition'][field]==r['test_definition'][field]
 out=assess_record(r)['objective_outcome'];pairs.append({'source_cohort':k[0],'fixture':spec['fixture'],'variant':v['id'],'repetition':r['repetition'],'original':e['outcome'],'literal_line_v2':out});evidence.append({'case_id':r['case_id'],'test_id':r['test_id'],'variant_id':v['id'],'repetition':r['repetition'],'source_cohort':k[0],'outcome':out,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'path':str(p),'baseline_path':str(d/e['path'])})
assert len(seen)==162
summary={'cohort':'fourb-literal-regression-v1','model':model,'retrospective':True,'observations':162,'matched_pairs':162,'outcomes':{arm:dict(collections.Counter(x[arm] for x in pairs)) for arm in ('original','literal_line_v2')},'transitions':dict(collections.Counter(x['original']+' -> '+x['literal_line_v2'] for x in pairs)),'by_source':{},'pairs':pairs,'evidence':evidence}
for name in man['source_cohorts']:
 subset=[x for x in pairs if x['source_cohort']==name];assert len(subset)==54;summary['by_source'][name]={'outcomes':{arm:dict(collections.Counter(x[arm] for x in subset)) for arm in ('original','literal_line_v2')},'transitions':dict(collections.Counter(x['original']+' -> '+x['literal_line_v2'] for x in subset))}
(b/'audit.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8');print(json.dumps({k:v for k,v in summary.items() if k not in ('pairs','evidence')},indent=2))
