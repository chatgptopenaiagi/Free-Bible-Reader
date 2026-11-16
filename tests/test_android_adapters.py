"""Portable security/adapter contracts; Android execution has separate evidence."""
import json
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from pathlib import Path
from studio import api, native, documents, paths
from workbench.server import ThreadingHTTPServer, Handler

class AndroidContractTests(unittest.TestCase):
    def test_loopback_session_is_required_for_static_and_api(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.allowed_engine='all';server.product_variant='lite';server.session_token='a'*64
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            for path in ('/lite/','/api/health','/api/reader/catalog'):
                with self.assertRaises(HTTPError) as caught:urlopen(base+path)
                self.assertEqual(caught.exception.code,403)
            with self.assertRaises(HTTPError):urlopen(Request(base+'/api/health',headers={'Cookie':'fbr_session=wrong'}))
            with urlopen(Request(base+'/api/health',headers={'Cookie':'fbr_session='+'a'*64})) as response:
                value=json.load(response)
                self.assertEqual(value['variant'],'lite');self.assertFalse(value['lab_engines_available'])
            request=Request(base+'/api/query',data=b'{"reference":"John 1:1"}',headers={'Cookie':'fbr_session='+'a'*64,'Content-Type':'application/json'})
            with self.assertRaises(HTTPError) as caught:urlopen(request)
            self.assertEqual(caught.exception.code,501)
        finally:server.shutdown();server.server_close();thread.join()

    def test_native_adapter_has_no_desktop_dependency(self):
        calls=[]
        try:
            native.configure_adapter(lambda action,values:(calls.append((action,values)) or {'cancelled':True}))
            self.assertTrue(native.available());self.assertTrue(native.request('open')['cancelled'])
            self.assertEqual(calls,[('open',{})])
        finally:native.configure_adapter()

    def test_native_renderer_runs_only_after_document_validation(self):
        calls=[]
        try:
            documents.configure_renderer(lambda request:(calls.append(request) or (b'%PDF-1.4\n',{'provider':'test-only'})))
            with self.assertRaises(documents.DocumentError):documents.create_export({'format':'pdf','blocks':[]})
            self.assertEqual(calls,[])
            with tempfile.TemporaryDirectory() as temporary:
                old=paths._configured_root;paths.configure_root(temporary)
                try:
                    result=documents.create_export({'format':'pdf','title':'Română','blocks':[{'text':'ă â î ș ț Ă Â Î Ș Ț','reference':'John.3.16','label':'Test fixture'}]})
                    self.assertEqual(result['rendering']['provider'],'test-only')
                    self.assertEqual(calls[0]['blocks'][0]['text'],'ă â î ș ț Ă Â Î Ș Ț')
                    self.assertEqual(documents.read_artifact(result['artifact_id'])[0],b'%PDF-1.4\n')
                finally:paths._configured_root=old
        finally:documents.configure_renderer()

    def test_platform_delegation_retains_portable_routes(self):
        try:
            api.configure_platform(lambda method,path,payload: {'platform':'test-only'} if path=='/api/studio/capabilities' else api.NOT_HANDLED)
            self.assertEqual(api.get('/api/studio/capabilities',{}),{'platform':'test-only'})
            self.assertIsNone(api.get('/api/studio/no-such-route',{}))
        finally:api.configure_platform()

if __name__=='__main__':unittest.main()
