"""Browser launcher / restart supervisor. Windows users double-click Start Workbench.vbs."""
from __future__ import annotations
import argparse
import json
import os
import signal
import subprocess
import sys
import traceback
import webbrowser
from pathlib import Path


def child(root,args):
    from workbench.locking import HostLock, WorkerBusy
    data=root/'.local'/('demo' if args.demo else 'workbench')
    try:
        with HostLock(data/'host.lock'):
            if args.batch:
                if not args.demo and not os.environ.get('SLURM_JOB_ID'):
                    raise RuntimeError('Unity batch runs must start inside a Slurm allocation.')
                from workbench.controller import Controller
                app=Controller(root,args.demo)
                def stop(*unused):app.control('stop')
                signal.signal(signal.SIGTERM,stop)
                if hasattr(signal,'SIGUSR1'):signal.signal(signal.SIGUSR1,stop)
                try:
                    app.run()
                    if app.restart_required:return 75
                    return 0 if app.report and app.report['ready'] and not app.session_errors else 2
                except Exception as exc:
                    app.log('batch_error',exc)
                    if app.restart_required:return 75
                    return 2
                finally:app.flush_logs()
            from workbench.server import serve
            return serve(root,demo=args.demo,port=8766 if args.demo else 8765,open_browser=not args.no_browser)
    except WorkerBusy:
        keyfile=data/'control.key'
        if not args.batch and keyfile.exists():
            from workbench.backends import Transport
            token=keyfile.read_text().strip();port=8766 if args.demo else 8765
            Transport(f'http://127.0.0.1:{port}',token,timeout=5).request('/api/state')
            if not args.no_browser:webbrowser.open(f'http://127.0.0.1:{port}/#key={token}')
            return 0
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--demo',action='store_true');p.add_argument('--batch',action='store_true')
    p.add_argument('--child',action='store_true');p.add_argument('--no-browser',action='store_true')
    args=p.parse_args(argv);root=Path(__file__).resolve().parent
    if sys.version_info<(3,10):raise RuntimeError('Python 3.10 or newer is required.')
    if args.child:return child(root,args)
    command=[sys.executable,str(Path(__file__).resolve()),'--child']
    if args.demo:command.append('--demo')
    if args.batch:command.append('--batch')
    if args.no_browser:command.append('--no-browser')
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    while True:
        code=subprocess.call(command,cwd=root,**flags)
        if code!=75:return code
        if not args.batch and '--no-browser' not in command:command.append('--no-browser')


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:
        root=Path(__file__).resolve().parent;log=root/'.local/launcher-error.log';log.parent.mkdir(exist_ok=True)
        log.write_text(traceback.format_exc(),encoding='utf-8')
        if '--batch' not in sys.argv:
            try:
                import tkinter as tk
                from tkinter import messagebox
                w=tk.Tk();w.withdraw();messagebox.showerror('RPG Testing',f'Workbench could not start. Details: {log}');w.destroy()
            except Exception:pass
        raise SystemExit(2)
