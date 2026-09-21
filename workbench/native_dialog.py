"""Host-native file/folder chooser helpers. They never choose or create a path automatically."""
from __future__ import annotations
from pathlib import Path

def _initial(value: str) -> str | None:
    if not value:return None
    path=Path(value).expanduser()
    if path.is_file():path=path.parent
    return str(path) if path.is_dir() else None

def select_directory(initial: str = "") -> str | None:
    import tkinter as tk
    from tkinter import filedialog
    root=tk.Tk();root.withdraw()
    try:
        root.attributes('-topmost',True);root.update_idletasks()
        value=filedialog.askdirectory(parent=root,initialdir=_initial(initial),mustexist=True,
            title='Choose the folder that contains (or will contain) your GGUF models')
        return str(Path(value).resolve()) if value else None
    finally:root.destroy()

def select_llama_server(initial: str = "") -> str | None:
    import os,tkinter as tk
    from tkinter import filedialog
    root=tk.Tk();root.withdraw()
    try:
        root.attributes('-topmost',True);root.update_idletasks()
        types=[('llama-server','llama-server.exe')] if os.name=='nt' else [('llama-server','llama-server'),('All files','*')]
        value=filedialog.askopenfilename(parent=root,initialdir=_initial(initial),title='Choose llama-server',filetypes=types)
        return str(Path(value).resolve()) if value else None
    finally:root.destroy()
