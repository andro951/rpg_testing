"""One-time graphical dependency setup. Never installs into system Python."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox

ROOT=Path(__file__).resolve().parent


def main():
    window=tk.Tk();window.withdraw()
    if sys.version_info<(3,10):
        messagebox.showerror('RPG Testing','Install Python 3.10 or newer first.');return
    env=ROOT/'.venv-workbench';python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    def ready(exe):
        try:return subprocess.run([str(exe),'-c','import jsonschema'],capture_output=True,timeout=15,**flags).returncode==0
        except (OSError,subprocess.SubprocessError):return False
    chosen=python if python.is_file() and ready(python) else Path(sys.executable)
    if not ready(chosen):
        if not messagebox.askyesno('RPG Testing — setup','Create a private Python environment in this project and install its requirements? This uses the Internet. No drivers or system packages will be changed.'):return
        window.deiconify();window.title('RPG Testing — preparing');window.geometry('500x120')
        label=tk.Label(window,text='Preparing isolated runtime…',wraplength=450,padx=20,pady=20);label.pack()
        done=threading.Event();outcome=[]
        def install():
            try:
                log=ROOT/'.local/setup.log';log.parent.mkdir(exist_ok=True)
                with log.open('w',encoding='utf-8') as f:
                    subprocess.run([sys.executable,'-m','venv',str(env)],stdout=f,stderr=subprocess.STDOUT,check=True,**flags)
                    subprocess.run([str(python),'-m','pip','install','--no-cache-dir','-r',str(ROOT/'requirements.txt')],stdout=f,stderr=subprocess.STDOUT,check=True,**flags)
                outcome.append(None)
            except Exception as exc:outcome.append(str(exc))
            finally:done.set()
        window.protocol('WM_DELETE_WINDOW',lambda:messagebox.showinfo('Setup','Setup is still running. Its progress is saved in .local/setup.log.'))
        threading.Thread(target=install,daemon=True).start()
        def poll():
            if done.is_set():window.quit()
            else:window.after(200,poll)
        poll();window.mainloop();window.withdraw()
        if outcome[0]:messagebox.showerror('Setup failed',outcome[0]+'\nSee .local/setup.log.');return
        chosen=python
    args=[str(chosen),str(ROOT/'launch_workbench.py')]
    if '--demo' in sys.argv:args.append('--demo')
    subprocess.Popen(args,cwd=ROOT,**flags)
    window.destroy()


if __name__=='__main__':main()
