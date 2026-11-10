"""Reuse the frozen copy definitions on the same retrospective tasks for 4B."""
import json,shutil
from pathlib import Path
b=Path(__file__).resolve().parent;src=b.parent/'vl8-copy-regression-v1'
for name in ('test_specs','prompts'):
 dest=b/name;assert not dest.exists();shutil.copytree(src/name,dest)
for name in ('references.json','test_judgements.json'):
 shutil.copy2(src/name,b/name)
m=json.loads((src/'manifest.json').read_text(encoding='utf8'));m['cohort']='fourb-copy-regression-v1';m['model']='local-28df315996a77e69';m['inference_started']=False;(b/'manifest.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf8')
for name in ('validate.py','prepare-desktop.py','preflight-local.py','run-local.py','audit.py','save-audit.py'):
 text=(src/name).read_text(encoding='utf8').replace('vl8-copy-regression-v1','fourb-copy-regression-v1').replace('local-cb6dd200423a32cc','local-28df315996a77e69')
 (b/name).write_text(text,encoding='utf8')
print('Prepared the unchanged prompt copy on previously examined tasks for 4B; no inference started.')
