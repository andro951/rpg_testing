import sys
from pathlib import Path
root=Path(r'C:\Users\Isaac\Documents\Codex\2026-11-02\task\literal-text-branch-v2\runtime');sys.path.insert(0,str(root));from workbench.literal_line import encode,decode
values=['backslash then quote: \\"','literal \\n','actual\nnewline','','  boundary  ','quote " literal','\\"','\\n']
for v in values:
 ops=[{'op':'replace','path':'example.note','value':v}];wire=encode(ops);assert decode(wire)==ops,(repr(v),repr(wire));print(repr(v),'->',repr(wire))
assert decode('set example.note: text:quote \\"ok\\"')[0]['value']=='quote "ok"'
print('PASS: literal backslash-plus-quote differs from optional quote escape; literal backslash-n differs from newline; empty and boundary whitespace round-trip.')
