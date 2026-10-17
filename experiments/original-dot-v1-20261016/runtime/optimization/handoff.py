"""Open the local Workbench from its explicitly clicked results-viewer action."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from .selection import fragment


def open_local(root, selection, port=8765):
    root=Path(root).resolve()
    base=f'http://127.0.0.1:{port}/'
    def ready():
        try:
            with urlopen(base+'api/optimization/identity',timeout=2) as response:identity=json.load(response)
        except HTTPError as exc:
            raise ValueError('Restart Workbench to load the new prompt-selection feature, then try again.') from exc
        except (URLError,TimeoutError,OSError):return False
        if identity.get('application')!='rpg-workbench' or Path(identity.get('root','')).resolve()!=root:
            raise ValueError('The Workbench port belongs to another project. Open the matching Workbench and use its Results table.')
        return True
    if not ready():
        flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
        process=subprocess.Popen([sys.executable,str(root/'launch_workbench.py'),'--no-browser'],cwd=root,**flags)
        deadline=time.monotonic()+20
        while not ready():
            if process.poll() is not None or time.monotonic()>=deadline:
                raise ValueError('Workbench could not open. Start Workbench, then try Optimize this prompt again.')
            time.sleep(.15)
    return base+'#'+fragment(selection)
