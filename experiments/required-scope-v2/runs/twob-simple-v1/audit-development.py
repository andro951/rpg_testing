import collections,hashlib,json,sys
from pathlib import Path
b=Path(__file__).resolve().parent;d=b/'development';root=d/'desktop';sys.path.insert(0,str(root))
from workbench.domain import ResultStore,digest
from workbench.workflows import messages
from evaluation.core import assess_record
m='local-2542aed68e6bb077';man=json.loads((d/'manifest.json').read_text(encoding='utf8'));want={(x['test_id'],x['variant_id']):x for x in man['requests']};tests={p.stem:json.loads(p.read_text(encoding='utf8')) for p in (d/'test_specs').glob('*.json')};store=ResultStore(root/'results');paths=sorted((store.root/m).glob('*.json'));assert len(paths)==4
old=Path(r'E:\Source\Repos\rpg_testing\experiments\required-scope-v2\runs\reserved-id-v1\desktop\local-2542aed68e6bb077');audit=json.loads((old/'audit.json').read_text(encoding='utf8'));pairs=[];evidence=[];seen=set()
for p in paths:
 r=store.read(p);t=tests[r['test_id']];v=next(x for x in t['variants'] if x['id']==r['variant_id']);q=want[(t['id'],v['id'])];assert r['repetition']==0;key=(q['baseline_test_id'],v['id'],0);assert key not in seen;seen.add(key);matches=[x for x in audit['evidence'] if (x['test_id'],x['variant_id'],x['repetition'])==key];assert len(matches)==1;e=matches[0];op=old/e['path'];prior=json.loads(op.read_text(encoding='utf8'));checksum=prior.pop('sha256');assert digest(prior)==checksum and hashlib.sha256(op.read_bytes()).hexdigest()==e['sha256'];assert prior['artifact_identity']==r['artifact_identity'] and prior['target']==r['target'];assert prior['load']['context']['allocated_tokens']==r['load']['context']['allocated_tokens']==32768
 for field in ('source','state_schema','expected_state'):assert prior['test_definition'][field]==r['test_definition'][field]
 req=messages(t,v['steps'][0],{},v);assert digest(req)==q['message_digest'];calls=r.get('calls',[]);assert (calls and calls[0]['messages']==req) or (not calls and (r.get('timed_out') or r.get('status') in ('error','aborted')))
 if prior.get('calls') and calls:assert prior['calls'][0]['sampling']==calls[0]['sampling']
 out=assess_record(r)['objective_outcome'];pairs.append({'baseline_test_id':key[0],'variant':key[1],'repetition':0,'original':e['outcome'],'candidate':out});evidence.append({'case_id':r['case_id'],'test_id':r['test_id'],'variant_id':v['id'],'outcome':out,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'path':str(p),'baseline_path':str(op)})
assert len(seen)==4
trans=collections.Counter(x['original']+' -> '+x['candidate'] for x in pairs);g=trans['FAIL -> PASS'];loss=trans['PASS -> FAIL'];verdicts=sum(x['candidate'] in ('PASS','FAIL') for x in pairs);advance=g>=1 and loss==0 and verdicts>=3
out={'stage':'development','model':m,'observations':4,'matched_pairs':4,'transitions':dict(trans),'candidate_outcomes':dict(collections.Counter(x['candidate'] for x in pairs)),'advance_to_verification':advance,'screen':'at least one gain, no passing baseline regressions, at least three semantic verdicts','pairs':pairs,'evidence':evidence};(d/'audit.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='evidence'},indent=2))
