"""Match the preserved 32K baseline in isolated stage runtimes; do not lower context."""
import sys
from pathlib import Path
b=Path(__file__).resolve().parent;stage=sys.argv[1];assert stage in ('development','verification')
p=b/stage/'desktop'/'workbench'/'inventory.py';s=p.read_text(encoding='utf8');old='desired=max(16384,2**math_ceil_log2(max(1,longest*2+8192)))';new='desired=max(32768,2**math_ceil_log2(max(1,longest*2+8192)))';assert s.count(old)==1;p.write_text(s.replace(old,new),encoding='utf8');print('Set isolated context floor to 32768 to match saved baseline; no model call.')
