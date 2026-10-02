import sys, json, copy, tempfile, collections, subprocess, hashlib
from pathlib import Path
ROOT=Path(r'D:\Program Files\JS Dev\rpg_testing')
sys.path.insert(0,str(ROOT))
from workbench.domain import read_json, load_tests, ResultStore, case_id, code_fingerprint
from workbench.planning import pending_plan
from workbench.native import _template_compatible_messages
from workbench.inventory import automatic_context
from workbench.preflight import _context_planning_tests
tests=load_tests(ROOT/'test_specs')
files=subprocess.check_output(['git','-C',str(ROOT),'ls-files'],text=True).splitlines()
inventory=[]
for name in files:
 p=ROOT/name;b=p.read_bytes()
 inventory.append({'file':name,'bytes':len(b),'lines':b.count(b'\n'),'sha256':hashlib.sha256(b).hexdigest()})
store=ResultStore(ROOT/'results');records=store.all()
report={'tracked_files':len(files),'extensions':dict(collections.Counter(Path(n).suffix for n in files)),
 'enabled_tests':len(tests),'enabled_cases_per_model':sum(t.get('repetitions',1)*sum(v.get('enabled',True) for v in t['variants']) for t in tests),
 'result_records':len(records),'result_statuses':dict(collections.Counter(r['status'] for r in records)),
 'result_models':dict(collections.Counter(r['model_id'] for r in records)),
 'result_classes':dict(collections.Counter(r.get('execution_class','legacy') for r in records)),
 'result_simulated':sum(bool(r.get('simulated')) for r in records),
 'context_recipe':automatic_context(_context_planning_tests(tests),{'planning.context_length':2**63-1}),
 'workflow_code':code_fingerprint()}
msgs=[{'role':'system','content':'Rules'},{'role':'user','content':'State'},{'role':'user','content':'Patch'}]
adapted,meta=_template_compatible_messages(msgs,{'chat_template_caps':{'supports_system_role':True},'chat_template':'Conversation roles must alternate user/assistant/user/assistant/...'})
report['strict_template_probe']={'messages_unchanged':adapted==msgs,'adaptation':meta}
adapted,meta=_template_compatible_messages(msgs,{'chat_template_caps':{'supports_system_role':False}})
report['newline_probe']={'content_repr':repr(adapted[0]['content']),'contains_literal_slash_n':r'\n' in adapted[0]['content'],'contains_actual_newline':'\n' in adapted[0]['content']}
t=copy.deepcopy(next(t for t in tests if t['id']=='time_only'));t['variants']=t['variants'][:1];t['repetitions']=1
m={'id':'probe','files':['probe.gguf'],'required_vram_gb':8,'sha256':{'probe.gguf':'a'*64}};target={'vram_gb':8}
with tempfile.TemporaryDirectory() as tmp:
 s=ResultStore(Path(tmp));cid=case_id(m,t,t['variants'][0],0,target)
 s.save({'status':'skipped','model_id':m['id'],'case_id':cid,'test_id':t['id'],'variant_id':t['variants'][0]['id'],'repetition':0,'target':target,'execution_class':'full_gpu','recovery_eligible':True,'reason':'gpu_memory','artifact_hashes':m['sha256'],'provenance':{'workflow_code':code_fingerprint()},'test_definition':t,'variant_definition':t['variants'][0]})
 before=pending_plan([m],[t],target,s)
 t2=copy.deepcopy(t);t2['timeout_seconds']+=1
 after=pending_plan([m],[t2],target,s)
 report['timeout_recovery_probe']={'before_pending':before['pending'],'before_recovery_only':before['groups'][0]['jobs'][0]['recovery_only'],'after_pending':after['pending'],'after_complete':after['complete']}
report['specs']=[{'id':t['id'],'cases':t.get('repetitions',1)*sum(v.get('enabled',True) for v in t['variants']),'variants':[v['id'] for v in t['variants']]} for t in tests]
out=ROOT/'.local/audit-probes.json';out.write_text(json.dumps(report,indent=2),encoding='utf-8')
(ROOT/'.local/audit-inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='specs'},indent=2))
