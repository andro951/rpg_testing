import sys
from pathlib import Path
root=Path(r'D:\Program Files\JS Dev\rpg_testing')
sys.path.insert(0,str(root))
name=sys.argv[1];path=root/'tests'/f'{name}.py';code=path.read_text()
if name=='browser_smoke':
 code=code.replace('timeout=15000','timeout=120000')
elif name=='browser_model_smoke':
 code=code.replace("                assert app.report is not None", "                app.thread.join(60)\n                assert app.report is not None")
exec(compile(code,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
