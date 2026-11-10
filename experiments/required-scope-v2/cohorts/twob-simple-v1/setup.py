import sys
from pathlib import Path
b=Path(__file__).resolve().parent;stage=sys.argv[1];assert stage in ('development','verification');d=b/stage;src=b.parent/'nineb-copy-confirm-v1';expected=4 if stage=='development' else 8
s=(src/'prepare-desktop.py').read_text(encoding='utf8').replace("hold=base/'nineb-copy-confirm-v1'",f"hold=base/'twob-simple-v1/{stage}'");(d/'prepare-desktop.py').write_text(s,encoding='utf8')
s=(src/'preflight-local.py').read_text(encoding='utf8').replace("base=Path(r'C:\\Users\\Isaac\\Documents\\Codex\\2026-11-02\\task\\nineb-copy-confirm-v1')",f"base=Path(r'C:\\Users\\Isaac\\Documents\\Codex\\2026-11-02\\task\\twob-simple-v1\\{stage}')")
s=s.replace("model=sys.argv[1];assert model in ('local-81e2a88130ccfa4e','local-8c5e666555c53096')", "model='local-2542aed68e6bb077'");(d/'preflight-local.py').write_text(s,encoding='utf8')
s=(src/'run-local.py').read_text(encoding='utf8').replace("base=Path(r'C:\\Users\\Isaac\\Documents\\Codex\\2026-11-02\\task\\nineb-copy-confirm-v1')",f"base=Path(r'C:\\Users\\Isaac\\Documents\\Codex\\2026-11-02\\task\\twob-simple-v1\\{stage}')")
s=s.replace("model=sys.argv[1];assert model in ('local-81e2a88130ccfa4e','local-8c5e666555c53096')", "model='local-2542aed68e6bb077'").replace("validation['requests']==24",f"validation['requests']=={expected}").replace("pre['groups'][0]['jobs']==72",f"pre['groups'][0]['jobs']=={expected}")
s=s.replace("datetime.datetime(2026,11,4,21,45", "datetime.datetime(2026,11,4,21,35").replace("'2026-11-04T21:45:00Z'", "'2026-11-04T21:35:00Z'").replace("'fixtures':4,'methods':2,'presentations_per_method':12,'repetitions':3",f"'fixtures':2,'methods':{1 if stage=='development' else 2},'presentations_per_method':4,'repetitions':1")
(d/'run-local.py').write_text(s,encoding='utf8')
print('Prepared setup scripts for',stage)
