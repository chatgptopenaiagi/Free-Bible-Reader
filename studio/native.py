"""Native dialogs are executed only by the launcher's Tk main thread."""
from __future__ import annotations
import pathlib
import queue
import shutil
import threading
import json
from .paths import data_root, public_root

_requests = queue.Queue(maxsize=8)
_active = False
_protected_paths = set()

def protect(path):
    _protected_paths.add(pathlib.Path(path).resolve())

def available():
    return _active

def install(window):
    global _active
    _active = True
    folder=data_root()/'inspections'
    if folder.is_dir():
        for file in list(folder.glob('*.json'))[:1000]:
            try:
                info=json.loads(file.read_text(encoding='utf-8'))
                if info.get('path'):protect(info['path'])
            except (OSError,ValueError,TypeError):pass
    def poll():
        try:
            task = _requests.get_nowait()
        except queue.Empty:
            task = None
        if task is not None:
            try:
                from tkinter import filedialog
                locale=task.get('language','en')
                titles={'en':('Open Bible database','Save document'),'ro':('Deschide o bază biblică','Salvează documentul'),'de':('Bibeldatenbank öffnen','Dokument speichern')}.get(locale,('Open Bible database','Save document'))
                documents=pathlib.Path.home()/'Documents'
                initial=documents if documents.is_dir() else pathlib.Path.home()
                if task['action'] == 'open':
                    name = filedialog.askopenfilename(parent=window, title=titles[0],initialdir=str(initial), filetypes=[('Bible databases and exports','*.sqlite *.sqlite3 *.db *.db3 *.sql *.zip *.csv *.json *.jsonl'),('All files','*.*')])
                    task['result'] = {'cancelled':not bool(name), 'path':name or None}
                elif task['action'] == 'save':
                    source = pathlib.Path(task['source'])
                    suffix = source.suffix.lower()
                    name = filedialog.asksaveasfilename(parent=window, title=titles[1],initialdir=str(initial), initialfile=task['filename'], defaultextension=suffix, filetypes=[(suffix.upper().lstrip('.')+' document','*'+suffix)])
                    if name:
                        target = pathlib.Path(name).expanduser().resolve()
                        if target == source.resolve() or target in _protected_paths or target.is_relative_to(public_root().resolve()) or target.suffix.lower()!=suffix:
                            raise ValueError('Choose a different destination with the document extension; source files and application files cannot be overwritten')
                        shutil.copyfile(source, target)
                    task['result'] = {'cancelled':not bool(name), 'filename':pathlib.Path(name).name if name else None}
                elif task['action'] == 'quit':
                    task['result'] = {'closing':True}
                    window.after(200, window.destroy)
                else:
                    raise ValueError('Unknown native action')
            except Exception as error:
                task['error'] = str(error)
            finally:
                task['done'].set()
        if _active:
            window.after(60, poll)
    window.after(60, poll)

def uninstall():
    global _active
    _active = False
    while True:
        try:
            task = _requests.get_nowait()
        except queue.Empty:
            break
        task['error'] = 'Application closed'
        task['done'].set()

def request(action, **values):
    if not _active:
        raise ValueError('NATIVE_DIALOG_UNAVAILABLE')
    task = {'action':action, 'done':threading.Event(), **values}
    _requests.put_nowait(task)
    if not task['done'].wait(300):
        raise TimeoutError('Native dialog did not complete')
    if 'error' in task:
        raise ValueError(task['error'])
    return task.get('result', {})
