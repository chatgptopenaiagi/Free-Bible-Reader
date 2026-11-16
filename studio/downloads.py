"""Explicit HTTPS acquisition to private staging; no automatic import or URL credentials.

DNS is checked on every hop and the verified public IP is pinned for the actual TLS
connection while the original hostname remains the SNI/certificate/Host identity.
"""
from __future__ import annotations
import base64,hashlib,http.client,ipaddress,json,pathlib,socket,ssl,urllib.parse,uuid
from . import library

MAX_BYTES=256*1024*1024

def public_target(url,resolver=socket.getaddrinfo):
    if not isinstance(url,str) or len(url)>4096:raise ValueError('INVALID_DOWNLOAD_URL')
    u=urllib.parse.urlsplit(url)
    if u.scheme.lower()!='https' or not u.hostname or u.username or u.password or u.fragment:raise ValueError('PUBLIC_HTTPS_URL_REQUIRED')
    try:port=u.port
    except ValueError:raise ValueError('INVALID_DOWNLOAD_PORT') from None
    if port not in (None,443):raise ValueError('HTTPS_PORT_443_REQUIRED')
    host=u.hostname.encode('idna').decode('ascii').lower()
    if host in ('localhost','localhost.localdomain') or host.endswith(('.localhost','.local','.internal')):raise ValueError('PRIVATE_DOWNLOAD_TARGET_REJECTED')
    addresses=[]
    try:
        for r in resolver(host,443,type=socket.SOCK_STREAM):
            ip=ipaddress.ip_address(r[4][0])
            if not ip.is_global or ip.is_multicast:raise ValueError('PRIVATE_DOWNLOAD_TARGET_REJECTED')
            if str(ip) not in addresses:addresses.append(str(ip))
    except socket.gaierror:raise ValueError('DOWNLOAD_DNS_FAILED') from None
    if not addresses:raise ValueError('DOWNLOAD_DNS_FAILED')
    return u,host,addresses

class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,ip):super().__init__(host,443,timeout=20,context=ssl.create_default_context());self.pinned_ip=ip
    def connect(self):
        sock=socket.create_connection((self.pinned_ip,443),self.timeout)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except Exception:sock.close();raise

def stage_download(url,progress=None,cancel_event=None,max_bytes=MAX_BYTES,expected_sha256=None,auth=None):
    if not isinstance(max_bytes,int) or not 1<=max_bytes<=MAX_BYTES:raise ValueError('INVALID_DOWNLOAD_LIMIT')
    if expected_sha256 is not None and (not isinstance(expected_sha256,str) or len(expected_sha256)!=64 or any(c not in '0123456789abcdefABCDEF' for c in expected_sha256)):raise ValueError('INVALID_EXPECTED_HASH')
    authorization=None
    if auth is not None:
        if not isinstance(auth,dict):raise ValueError('INVALID_DOWNLOAD_AUTH')
        kind=auth.get('type')
        if kind=='bearer':
            token=auth.get('token')
            if not isinstance(token,str) or not 1<=len(token)<=8192 or any(ord(c)<33 or ord(c)>126 for c in token):raise ValueError('INVALID_DOWNLOAD_AUTH')
            authorization='Bearer '+token
        elif kind=='basic':
            user=auth.get('username');password=auth.get('password')
            if not isinstance(user,str) or not isinstance(password,str) or ':' in user or len(user)+len(password)>8192 or any(c in user+password for c in '\r\n\x00'):raise ValueError('INVALID_DOWNLOAD_AUTH')
            authorization='Basic '+base64.b64encode((user+':'+password).encode('utf-8')).decode('ascii')
        else:raise ValueError('INVALID_DOWNLOAD_AUTH')
    original=url;out=None;conn=None;auth_host=None
    try:
        for hop in range(4):
            u,host,addresses=public_target(url);conn=_PinnedHTTPS(host,addresses[0])
            target=urllib.parse.urlunsplit(('', '',u.path or '/',u.query,''))
            if auth_host is None:auth_host=host
            headers={'Host':host,'User-Agent':'Free-Bible-Reader/0.2.0','Accept':'application/octet-stream,*/*;q=0.5','Connection':'close'}
            # Never forward a user credential across redirect origins.
            if authorization and host==auth_host:headers['Authorization']=authorization
            conn.request('GET',target,headers=headers)
            response=conn.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location');conn.close();conn=None
                if not location or hop==3:raise ValueError('DOWNLOAD_REDIRECT_LIMIT')
                url=urllib.parse.urljoin(url,location);continue
            if response.status!=200:raise ValueError('DOWNLOAD_HTTP_'+str(response.status))
            length=response.getheader('Content-Length');length=int(length) if length is not None else None
            if length is not None and not 0<=length<=max_bytes:raise ValueError('DOWNLOAD_SIZE_LIMIT')
            ext=pathlib.PurePosixPath(u.path).suffix.lower()
            if ext not in ('.zip','.sqlite','.sqlite3','.db','.csv','.json','.jsonl','.ndjson','.sql'):ext='.download'
            id=str(uuid.uuid4());out=library.data_root()/'downloads'/(id+ext);out.parent.mkdir(parents=True,exist_ok=True)
            count=0;digest=hashlib.sha256();safe_url=urllib.parse.urlunsplit(('https',host,u.path,'',''))
            with out.open('xb') as f:
                while True:
                    if cancel_event is not None and cancel_event.is_set():raise ValueError('DOWNLOAD_CANCELLED')
                    chunk=response.read(65536)
                    if not chunk:break
                    count+=len(chunk)
                    if count>max_bytes:raise ValueError('DOWNLOAD_SIZE_LIMIT')
                    f.write(chunk);digest.update(chunk)
                    if progress:progress({'status':'DOWNLOADING','bytes':count,'expected_bytes':length,'url':safe_url})
            if length is not None and count!=length:raise ValueError('DOWNLOAD_INCOMPLETE')
            if expected_sha256 and digest.hexdigest()!=expected_sha256.lower():raise ValueError('DOWNLOAD_HASH_MISMATCH')
            receipt={'download_id':id,'status':'DOWNLOADED_ONLY','path':str(out),'source_url':safe_url,'bytes':count,'sha256':digest.hexdigest(),'expected_sha256_matched':bool(expected_sha256),'requires_inspection_and_confirmation':True,'authentication_used':auth is not None,'credentials_persisted':False}
            out.with_suffix(out.suffix+'.receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
            if progress:progress(receipt)
            return receipt
        raise ValueError('DOWNLOAD_REDIRECT_LIMIT')
    except Exception:
        if out and out.exists():out.unlink() # only the UUID-owned partial download
        raise
    finally:
        if conn:conn.close()
