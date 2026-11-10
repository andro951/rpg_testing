import collections,hashlib,json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;root=b/'desktop';sys.path.insert(0,str(root))
from workbench.domain import ResultStore,digest
from workbench.workflows import messages
from evaluation.core import assess_record
m='local-2542aed68e6bb077';man=json.loads((b/'manifest.json').read_text(encoding='utf8'));want={(x['test_id'],x['variant_id']):x for x in man['requests']};tests={p.stem:json.loads(p.read_text(encoding='utf8')) for p in (b/'test_specs').glob('*.json')};store=ResultStore(root/'results');paths=sorted((store.root/m).glob('*.json'));assert len(paths)==6
cells={};evidence=[]
for p in paths:
 r=store.read(p);t=tests[r['test_id']];v=next(x for x in t['variants'] if x['id']==r['variant_id']);q=want[(t['id'],v['id'])];assert r['repetition']==0;req=messages(t,v['steps'][0],{},v);assert digest(req)==q['message_digest'];calls=r.get('calls',[]);assert (calls and calls[0]['messages']==req) or (not calls and (r.get('timed_out') or r.get('status') in ('error','aborted')));key=q['fixture'];assert v['id'] not in cells.setdefault(key,{});out=assess_record(r)['objective_outcome'];cells[key][v['id']]=(r,out);evidence.append({'case_id':r['case_id'],'fixture':key,'variant_id':v['id'],'outcome':out,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'path':str(p)})
assert len(cells)==3 and all(set(x)=={'normal_json','full_paths'} for x in cells.values());pairs=[]
for fixture,v in sorted(cells.items()):
 a,c=v['normal_json'][0],v['full_paths'][0];assert a['artifact_identity']==c['artifact_identity'] and a['target']==c['target'];assert all(r['load']['context']['allocated_tokens']==32768 for r in (a,c))
 if a.get('calls') and c.get('calls'):assert a['calls'][0]['sampling']==c['calls'][0]['sampling']
 for f in ('source','state_schema','expected_state'):assert a['test_definition'][f]==c['test_definition'][f]
 pairs.append({'fixture':fixture,'normal_json':v['normal_json'][1],'full_paths':v['full_paths'][1]})
out={'cohort':'twob-presentation-confirm-v1','model':m,'observations':6,'matched_pairs':3,'outcomes':{arm:dict(collections.Counter(x[arm] for x in pairs)) for arm in ('normal_json','full_paths')},'transitions':dict(collections.Counter(x['normal_json']+' -> '+x['full_paths'] for x in pairs)),'pairs':pairs,'evidence':evidence};(b/'audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='evidence'},indent=2))
