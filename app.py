"""FREE BIBLE READER: local-only desktop launcher and portable HTTP application."""
from __future__ import annotations
import argparse,contextlib,json,os,pathlib,socket,sys,threading,time,urllib.parse,urllib.request,webbrowser
VERSION='0.1.0'
ROOT=pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parent))
sys.path.insert(0,str(ROOT))
def user_directory():return pathlib.Path(os.environ.get('LOCALAPPDATA',pathlib.Path.home()/'.local/share'))/'FreeBibleReader'
def existing_instance(state_path):
    try:
        state=json.loads(state_path.read_text(encoding='utf-8'));url=urllib.parse.urlsplit(state['url'])
        if url.scheme!='http' or url.hostname!='127.0.0.1' or not url.port or url.username or url.password or url.path not in ('','/'):return None
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{url.port}/api/health',timeout=1) as response:health=json.load(response)
        if health.get('product')=='FREE BIBLE READER' and health.get('pid')==state.get('pid'):return state
    except (OSError,ValueError,KeyError):pass
    return None
def self_test():
    from reader.service import catalog,chapter,search
    checks={'three_editions':len(catalog()['editions'])==3,'books66':len(catalog()['books'])==66,'john3_36verses':len(chapter('web','John',3)['verses'])==36,'real_john3_16':'God so loved' in chapter('web','John',3)['verses'][15]['text'],'search':any(x['reference']=='John.3.16' for x in search('"God so loved"')['results']),'last_book':chapter('web','Rev',22)['next'] is None,'static_frontend':(ROOT/'workbench/index.html').is_file(),'ui_core':(ROOT/'ui-core/index.js').is_file()}
    try:
        from bridge import hub
        answer=hub.query({'reference':'John 1:1','engine':'all','edition_id':'crossreferences:KJV','limit':1})
        checks['three_research_engines']=all(answer['engines'][e]['status']=='VALID_RESULT' for e in ('A','B','C'))
    except Exception:checks['three_research_engines']=False
    result={'product':'FREE BIBLE READER','version':VERSION,'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks}
    return result
def native_window(server,open_reader):
    import tkinter as tk
    from tkinter import ttk
    window=tk.Tk();window.title('FREE BIBLE READER');window.geometry('460x265');window.minsize(400,245);window.configure(bg='#f4f1e8')
    languages={'en':{'ready':'Your offline Bible reader is ready.','open':'Open reader','quit':'Close application','note':'Keep this window open while reading.','language':'Language'},'ro':{'ready':'Cititorul biblic offline este pregătit.','open':'Deschide cititorul','quit':'Închide aplicația','note':'Păstrați această fereastră deschisă în timpul lecturii.','language':'Limbă'},'de':{'ready':'Ihr Offline-Bibelleser ist bereit.','open':'Bibelleser öffnen','quit':'Anwendung schließen','note':'Dieses Fenster beim Lesen geöffnet lassen.','language':'Sprache'}}
    locale_path=user_directory()/'launcher-language.json'
    try:initial=json.loads(locale_path.read_text()).get('language','en')
    except (OSError,ValueError):initial='en'
    language=tk.StringVar(value=initial if initial in languages else 'en')
    tk.Label(window,text='FREE BIBLE READER',font=('Segoe UI',21,'bold'),bg='#f4f1e8',fg='#184e56').pack(pady=(24,8))
    ready=tk.Label(window,font=('Segoe UI',11),bg='#f4f1e8',fg='#243237');ready.pack(pady=5)
    row=ttk.Frame(window);row.pack(pady=7);label=ttk.Label(row);label.pack(side='left',padx=5)
    choice=ttk.Combobox(row,textvariable=language,values=['en','ro','de'],state='readonly',width=6);choice.pack(side='left')
    buttons=ttk.Frame(window);buttons.pack(pady=12)
    opening=ttk.Button(buttons,command=lambda:open_reader());opening.pack(side='left',padx=6)
    def stop():window.destroy()
    closing=ttk.Button(buttons,command=stop);closing.pack(side='left',padx=6)
    note=tk.Label(window,font=('Segoe UI',9),bg='#f4f1e8',fg='#56686c');note.pack()
    def translate(*args):
        text=languages[language.get()];ready.configure(text=text['ready']);opening.configure(text=text['open']);closing.configure(text=text['quit']);note.configure(text=text['note']);label.configure(text=text['language'])
        try:locale_path.parent.mkdir(parents=True,exist_ok=True);locale_path.write_text(json.dumps({'language':language.get()}),encoding='utf-8')
        except OSError:pass
    language.trace_add('write',translate);translate();window.protocol('WM_DELETE_WINDOW',stop);window.after(500,open_reader);window.mainloop()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--headless',action='store_true');parser.add_argument('--no-browser',action='store_true');parser.add_argument('--port',type=int,default=0);parser.add_argument('--state-file');parser.add_argument('--self-test',action='store_true');parser.add_argument('--self-test-output');args=parser.parse_args()
    if args.self_test:
        result=self_test()
        if args.self_test_output:pathlib.Path(args.self_test_output).write_text(json.dumps(result,indent=2),encoding='utf-8')
        elif sys.stdout:print(json.dumps(result,indent=2))
        return 0 if result['status']=='PASS' else 1
    from workbench import server as module
    module.ROOT=ROOT
    config=user_directory();config.mkdir(parents=True,exist_ok=True);state_file=pathlib.Path(args.state_file) if args.state_file else config/'runtime.json';state_file.parent.mkdir(parents=True,exist_ok=True)
    prior=existing_instance(state_file)
    if prior:
        if not args.no_browser:webbrowser.open(prior['url'])
        if sys.stdout:print(json.dumps(dict(prior,reused=True)),flush=True)
        return 0
    origin_path=state_file.with_name('origin.json')
    try:port=json.loads(origin_path.read_text()).get('port',48179)
    except (OSError,ValueError):port=48179
    if not isinstance(port,int) or not 1024<=port<=65535:port=48179
    if args.port:port=args.port
    try:server=module.ThreadingHTTPServer(('127.0.0.1',port),module.Handler)
    except OSError:
        if args.port:raise
        server=module.ThreadingHTTPServer(('127.0.0.1',0),module.Handler)
    server.allowed_engine='all';url=f'http://127.0.0.1:{server.server_port}/';origin_path.write_text(json.dumps({'port':server.server_port}),encoding='utf-8')
    state={'product':'FREE BIBLE READER','version':VERSION,'pid':os.getpid(),'url':url,'port':server.server_port,'bind':'127.0.0.1','started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'executable':sys.executable};state_file.write_text(json.dumps(state,indent=2),encoding='utf-8')
    if sys.stdout:print(json.dumps(state),flush=True)
    def open_reader(language=None):
        # The native launcher must not override the browser's persisted UI language.
        if not args.no_browser:webbrowser.open(url+('?lang='+language if language in ('en','ro','de') else ''))
    try:
        if args.headless:
            if not args.no_browser:open_reader()
            server.serve_forever(poll_interval=.3)
        else:
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            try:native_window(server,open_reader)
            finally:server.shutdown();worker.join(timeout=5)
    except KeyboardInterrupt:pass
    finally:
        server.server_close()
        # Keep the observed origin for stable local preferences; no user notes/settings are removed.
        try:
            if json.loads(state_file.read_text()).get('pid')==os.getpid():state_file.write_text(json.dumps(dict(state,stopped=True)),encoding='utf-8')
        except (OSError,ValueError):pass
    return 0
if __name__=='__main__':raise SystemExit(main())
