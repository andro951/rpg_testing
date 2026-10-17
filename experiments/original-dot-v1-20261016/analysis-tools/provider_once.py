"""Durable at-most-once transport claims; does not change provider requests."""
from pathlib import Path
import json,os
class AttemptLedger:
 def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
 def claimed(self,cid):return(self.root/(cid+'.started.json')).exists()
 def write_once(self,path,value):
  with path.open('x',encoding='utf8')as f:json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
 def begin(self,cid,value):self.write_once(self.root/(cid+'.started.json'),value)
 def finish(self,cid,value):self.write_once(self.root/(cid+'.returned.json'),value)
def unattempted(groups,store,model_id,ledger):
 return[g for g in groups if not store.path(model_id,g['case_id']).exists()and not ledger.claimed(g['case_id'])]
