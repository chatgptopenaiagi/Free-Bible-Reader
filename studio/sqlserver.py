"""Optional Windows SQL Server read-only acquisition using the existing OS client.

System.Data.SqlClient runs in Windows PowerShell; no Python wheel/runtime or SQL
Server service/configuration changes are required. Integrated authentication only.
The selected database/table is explicit; no database creation or admin probing.
"""
from __future__ import annotations
import json,os,pathlib,queue,subprocess,threading,time,uuid
from . import library,importers

def _request(server,database,**kwargs):
    if not isinstance(server,str) or not 1<=len(server)<=256 or any(c in server for c in '\r\n\x00;'):raise ValueError('INVALID_SQLSERVER_HOST')
    if not isinstance(database,str) or not 1<=len(database)<=128 or any(c in database for c in '\r\n\x00'):raise ValueError('EXPLICIT_DATABASE_REQUIRED')
    return {'server':server,'database':database,'encrypt':True,'trust_server_certificate':False,**kwargs}

def _process(request):
    if os.name!='nt':raise ValueError('SQLSERVER_WINDOWS_ADAPTER_UNAVAILABLE')
    exe=pathlib.Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    if not exe.exists():raise ValueError('SQLSERVER_WINDOWS_CLIENT_UNAVAILABLE')
    # Hidden owned helper; stdin contains ephemeral selected connection fields.
    # This is trusted, static application command text. User connection fields
    # arrive only as stdin JSON and are never interpolated into that command.
    # Normal -Command execution does not alter/bypass machine execution policy.
    command=pathlib.Path(__file__).with_suffix('.ps1').read_text(encoding='utf-8')
    p=subprocess.Popen([str(exe),'-NoProfile','-NonInteractive','-Command',command],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return p

def inspect_sqlserver(server,database,encrypt=True,trust_server_certificate=False):
    req=_request(server,database,action='inspect',encrypt=bool(encrypt),trust_server_certificate=bool(trust_server_certificate));p=_process(req)
    try:out,err=p.communicate(json.dumps(req),timeout=45)
    except subprocess.TimeoutExpired:p.kill();p.communicate();raise ValueError('SQLSERVER_TIMEOUT') from None
    if p.returncode:raise ValueError('SQLSERVER_READ_ONLY_CONNECTION_FAILED')
    result=json.loads(out.lstrip('\ufeff'));result['connection']={'server':server,'database':database,'authentication':'Windows integrated','encrypt':bool(encrypt),'trust_server_certificate':bool(trust_server_certificate)}
    return result

def list_sqlserver_editions(server,database,encrypt=True,trust_server_certificate=False):
    req=_request(server,database,action='corpus-editions',encrypt=bool(encrypt),trust_server_certificate=bool(trust_server_certificate));p=_process(req)
    try:out,err=p.communicate(json.dumps(req),timeout=45)
    except subprocess.TimeoutExpired:p.kill();p.communicate();raise ValueError('SQLSERVER_TIMEOUT') from None
    if p.returncode:raise ValueError('SQLSERVER_KNOWN_CORPUS_PROFILE_UNAVAILABLE')
    return json.loads(out.lstrip('\ufeff'))

def stage_sqlserver(server,database,schema,table,order_column,edition_column=None,edition_value=None,encrypt=True,trust_server_certificate=False,maximum=100000,cancel_event=None,progress=None,profile='generic'):
    for x in (schema,table,order_column):importers.quote_identifier(x)
    if edition_column:importers.quote_identifier(edition_column)
    if not isinstance(maximum,int) or isinstance(maximum,bool) or not 1<=maximum<=500000:raise ValueError('SQLSERVER_ROW_LIMIT')
    if profile not in ('generic','biblia-corpus-lab'):raise ValueError('INVALID_SQLSERVER_PROFILE')
    if profile=='biblia-corpus-lab':
        try:uuid.UUID(str(edition_value))
        except ValueError:raise ValueError('EXPLICIT_CORPUS_REVISION_UUID_REQUIRED') from None
    req=_request(server,database,action='rows',schema=schema,table=table,order_column=order_column,edition_column=edition_column,edition_value=edition_value,encrypt=bool(encrypt),trust_server_certificate=bool(trust_server_certificate),maximum=maximum+1,profile=profile)
    out=library.data_root()/'staging'/(str(uuid.uuid4())+'.jsonl');out.parent.mkdir(parents=True,exist_ok=True);p=_process(req);count=0;size=0;stop=threading.Event();lines=queue.Queue(maxsize=64);pump=None
    try:
        p.stdin.write(json.dumps(req));p.stdin.close()
        def read_lines():
            try:
                for line in p.stdout:
                    while not stop.is_set():
                        try:lines.put(line,timeout=.1);break
                        except queue.Full:pass
                    if stop.is_set():return
            finally:
                while not stop.is_set():
                    try:lines.put(None,timeout=.1);break
                    except queue.Full:pass
        pump=threading.Thread(target=read_lines,daemon=True);pump.start();deadline=time.monotonic()+180
        with out.open('x',encoding='utf-8',newline='\n') as f:
            while True:
                if cancel_event is not None and cancel_event.is_set():raise ValueError('SQLSERVER_CANCELLED')
                if time.monotonic()>deadline:raise ValueError('SQLSERVER_EXPORT_TIMEOUT')
                try:line=lines.get(timeout=.1)
                except queue.Empty:continue
                if line is None:break
                row=json.loads(line.lstrip('\ufeff'));count+=1;size+=len(line.encode('utf-8'))
                if count>maximum or size>importers.MAX_FILE:raise ValueError('SQLSERVER_EXPORT_LIMIT_USE_EDITION_FILTER')
                f.write(json.dumps(row,ensure_ascii=False)+'\n')
                if progress and count%500==0:progress({'status':'READING_SQLSERVER','rows':count,'bytes':size})
        if p.wait(timeout=15):raise ValueError('SQLSERVER_READ_ONLY_EXPORT_FAILED')
        info=importers.inspect_source(out,copy=False)
        info.update({'sqlserver_source':{'server':server,'database':database,'schema':schema,'table':table,'authentication':'Windows integrated','selected_edition_value':edition_value,'profile':profile},'source_row_count':count,'source_query_policy':'SELECT only; user-selected database/table/unique order key; parameterized edition filter; private staged snapshot'})
        importers._inspection_path(info['inspection_id']).write_text(json.dumps(info,ensure_ascii=False),encoding='utf-8')
        return info
    except Exception:
        if p.poll() is None:p.kill()
        p.wait(timeout=10)
        if out.exists():out.unlink()
        raise
    finally:
        stop.set()
        if pump:pump.join(timeout=1)
        if p.stdout:p.stdout.close()
        if p.stderr:p.stderr.close()
