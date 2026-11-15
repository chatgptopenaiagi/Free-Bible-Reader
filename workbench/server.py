"""Local-only engineering workbench. No production application or permanent service."""
from __future__ import annotations
import argparse,contextlib,json,os,pathlib,sys,threading,time,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge import hub,reference,corpus_adapter
from reader import service as reader
STATIC={'/':('workbench/index.html','text/html; charset=utf-8'),'/favicon.ico':('workbench/favicon.svg','image/svg+xml'),'/app.js':('workbench/app.js','text/javascript; charset=utf-8'),'/style.css':('workbench/style.css','text/css; charset=utf-8'),'/visual.js':('engines/visual/component.js','text/javascript; charset=utf-8'),'/visual.css':('engines/visual/component.css','text/css; charset=utf-8')}
def unique_object(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ValueError('Duplicate JSON key: '+key)
        value[key]=item
    return value
def invalid_constant(value):raise ValueError('Non-finite JSON constant: '+value)
class Handler(BaseHTTPRequestHandler):
    server_version='BIBLIA-Xref-Lab/1.0'
    def log_message(self,*args):pass
    def send(self,status,data,kind='application/json; charset=utf-8'):
        raw=json.dumps(data,ensure_ascii=False,allow_nan=False).encode('utf-8') if isinstance(data,(dict,list)) else data
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'");self.end_headers();self.wfile.write(raw)
    def host_ok(self):return self.headers.get('Host','') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
    def do_GET(self):
        if not self.host_ok():return self.send(400,{'error':'Local host header required'})
        path=urllib.parse.urlsplit(self.path).path
        if path in STATIC:
            file,kind=STATIC[path];return self.send(200,(ROOT/file).read_bytes(),kind)
        asset=None
        if path.startswith('/ui-core/'):
            candidate=(ROOT/path.lstrip('/')).resolve()
            if candidate.is_relative_to((ROOT/'ui-core').resolve()) and candidate.suffix in ('.js','.css','.json','.svg'):asset=candidate
        elif path.count('/')==1 and pathlib.Path(path).suffix in ('.js','.css','.svg'):
            candidate=(ROOT/'workbench'/path.lstrip('/')).resolve()
            if candidate.is_relative_to((ROOT/'workbench').resolve()):asset=candidate
        if asset and asset.is_file():
            kind={'.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml'}[asset.suffix]
            return self.send(200,asset.read_bytes(),kind)
        if path.startswith('/api/reader/'):
            try:
                options=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query);edition=options.get('edition',['web'])[0]
                if path=='/api/reader/catalog':return self.send(200,reader.catalog(edition))
                if path=='/api/reader/chapter':return self.send(200,reader.chapter(edition,options.get('book',['John'])[0],options.get('chapter',['1'])[0]))
            except (ValueError,TypeError) as error:return self.send(400,{'status':'QUERY_ERROR','error':str(error)})
            except (OSError,Exception) as error:return self.send(500,{'status':'QUERY_ERROR','error':'READER_UNAVAILABLE'})
        if path=='/api/health':return self.send(200,{'status':'OK','scope':'FREE BIBLE READER desktop application','product':'FREE BIBLE READER','version':'0.1.0','lab_engines_available':True,'reader_available':reader.DATABASE.exists(),'allowed_engine':self.server.allowed_engine,'pid':os.getpid(),'bind':'127.0.0.1','contract_version':'1.0'})
        if path=='/api/editions':return self.send(200,{'editions':hub.editions(urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('all',['false'])[0]=='true')})
        if path=='/api/books':
            with contextlib.closing(reference.connect_registry()) as db:rows=db.execute('SELECT osis,chapters_json FROM BookRegistry WHERE native_source_code IS NOT NULL ORDER BY book_order').fetchall()
            return self.send(200,{'books':[{'osis':r[0],'chapters':json.loads(r[1])} for r in rows],'reference_system':'openbibleinfo-kjv66','warning':'Navigation coordinates are not a universal edition canon.'})
        return self.send(404,{'error':'Unknown route'})
    def do_POST(self):
        if not self.host_ok():return self.send(400,{'error':'Local host header required'})
        origin=self.headers.get('Origin');expected=f'http://127.0.0.1:{self.server.server_port}'
        if origin and origin!=expected:return self.send(403,{'error':'Same-origin local requests only'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=16384:return self.send(413,{'error':'JSON body required, maximum16384bytes'})
            payload=json.loads(self.rfile.read(size),object_pairs_hook=unique_object,parse_constant=invalid_constant);path=urllib.parse.urlsplit(self.path).path
            if not isinstance(payload,dict):return self.send(400,{'error':'JSON object required'})
            if path=='/api/reader/search':return self.send(200,reader.search(payload.get('query',''),payload.get('edition','web'),payload.get('book'),payload.get('limit',25),payload.get('offset',0)))
            if path=='/api/parse':return self.send(200,reference.parse_reference(payload.get('reference',''),payload.get('language','en')))
            if path=='/api/resolve':return self.send(200,corpus_adapter.resolve_reference(payload.get('reference',''),payload.get('edition_id','eng-kjv')))
            if path in ('/api/query','/api/compare'):
                if path=='/api/compare':payload['engine']='all'
                allowed=self.server.allowed_engine
                if allowed!='all' and payload.get('engine',allowed)!=allowed:return self.send(400,{'error':'This independent server exposes engine '+allowed})
                payload.setdefault('engine',allowed);return self.send(200,hub.query(payload))
            return self.send(404,{'error':'Unknown route'})
        except (ValueError,TypeError,json.JSONDecodeError) as error:return self.send(400,{'error':str(error)})
        except Exception as error:return self.send(500,{'status':'QUERY_ERROR','error':type(error).__name__+': '+str(error)})
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=0);ap.add_argument('--engine',choices=['all','A','B','C'],default='all');ap.add_argument('--state-file',default=str(ROOT/'evidence/integration/workbench-runtime.json'));a=ap.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);server.allowed_engine=a.engine
    state={'pid':os.getpid(),'port':server.server_port,'url':f'http://127.0.0.1:{server.server_port}/','engine':a.engine,'script':str(pathlib.Path(__file__).resolve()),'python':sys.executable,'started_utc':reference.utc(),'bind':'127.0.0.1'}
    pathlib.Path(a.state_file).write_text(json.dumps(state,indent=2),encoding='utf-8');print(json.dumps(state),flush=True)
    try:server.serve_forever(poll_interval=.3)
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()

