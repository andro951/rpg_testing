"""Create an isolated marker-v1 runtime; leave all prior runtimes untouched."""
import shutil
from pathlib import Path
b=Path(__file__).resolve().parent;src=b.parent/'literal-text-branch-v2'/'runtime';dst=b/'runtime'
assert not dst.exists()
shutil.copytree(src,dst,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for rel in ('workbench/domain.py','workbench/scoring.py','workbench/workflows.py','evaluation/core.py'):
 p=dst/rel;text=p.read_text(encoding='utf8');assert 'literal_line_v2' in text;text=text.replace('literal_line_v2','literal_line_marker_v1');p.write_text(text,encoding='utf8')
shutil.copy2(b/'marker.py',dst/'workbench'/'literal_line.py')
print('Prepared isolated marker runtime; no inference started.')
