"""Android lifecycle and native adapters for the unchanged portable services.

Imported by Chaquopy only. Desktop and wheel imports never require Java.
Every HTTP request requires an app-private, ephemeral session cookie.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import threading
import uuid
import wave

_server = None
_thread = None
_speech_lock = threading.Lock()
_speech_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='fbr-native-speech')

def _invoke(operation, payload=None):
    from java import jclass
    raw = jclass('com.freebiblereader.android.PlatformAdapter').invoke(operation, json.dumps(payload or {}, ensure_ascii=False, allow_nan=False))
    result = json.loads(str(raw))
    if result.get('status') == 'ERROR':
        raise ValueError(result.get('message') or result.get('error') or 'NATIVE_OPERATION_FAILED')
    return result

def _dialog(action, values):
    operation = {'open':'picker.open', 'save':'picker.save', 'quit':'app.quit'}.get(action)
    if operation is None:
        raise ValueError('UNKNOWN_NATIVE_ACTION')
    return _invoke(operation, values)

def _document(request):
    from studio.paths import data_root
    folder = data_root() / 'document-staging'
    folder.mkdir(exist_ok=True)
    target = folder / (uuid.uuid4().hex + '.' + request['format'])
    try:
        result = _invoke('document.generate', {'format':request['format'], 'request':request, 'output_path':str(target)})
        if not target.is_file() or not 0 < target.stat().st_size <= 30_000_000:
            raise ValueError('INVALID_NATIVE_DOCUMENT_OUTPUT')
        return target.read_bytes(), {'provider':'android-native', **result}
    finally:
        target.unlink(missing_ok=True)

def _synthesize(payload, cancellation, progress):
    from studio.paths import data_root
    if not isinstance(payload.get('text'), str) or not 0 < len(payload['text'].strip()) <= 6000 or '\0' in payload['text']:
        raise ValueError('INVALID_SPEECH_TEXT')
    speed = payload.get('speed', 1)
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not .5 <= speed <= 2:
        raise ValueError('INVALID_SPEECH_SPEED')
    if payload.get('provider') not in {'android-native','piper','espeak-ng'}:
        raise ValueError('UNSUPPORTED_ANDROID_SPEECH_PROVIDER')
    if not _speech_lock.acquire(blocking=False):
        raise ValueError('AUDIO_BUSY')
    folder = data_root() / 'audio'
    folder.mkdir(exist_ok=True)
    ident = uuid.uuid4().hex
    target = folder / (ident + '.wav')
    future = None
    try:
        # Prune completed cache only; leave at most 64 MiB / 100 recent WAVs.
        files = sorted(folder.glob('*.wav'), key=lambda p:p.stat().st_mtime, reverse=True)
        retained = 0
        for index, file in enumerate(files):
            retained += file.stat().st_size
            if index >= 100 or retained > 64 * 1024 * 1024:
                try:file.unlink()
                except OSError:pass
        request = {**payload, 'output_path':str(target), 'request_id':ident}
        progress(phase='synthesizing', provider=payload['provider'])
        future = _speech_pool.submit(_invoke, 'speech.synthesize', request)
        while True:
            try:
                value = future.result(timeout=.15)
                break
            except concurrent.futures.TimeoutError:
                if cancellation.is_set():
                    _invoke('speech.cancel', {'request_id':ident})
                    # Do not admit another job until the native worker has stopped.
                    try:future.result(timeout=15)
                    except Exception:pass
                    raise ValueError('SPEECH_CANCELLED')
        if cancellation.is_set():
            raise ValueError('SPEECH_CANCELLED')
        if not target.is_file() or not 44 < target.stat().st_size < 30_000_000:
            raise ValueError('INVALID_NATIVE_AUDIO_OUTPUT')
        nonzero = False
        with wave.open(str(target), 'rb') as audio:
            rate, frames = audio.getframerate(), audio.getnframes()
            channels, width = audio.getnchannels(), audio.getsampwidth()
            if rate <= 0 or frames <= 0 or channels != 1 or width != 2:
                raise ValueError('UNSUPPORTED_NATIVE_PCM_FORMAT')
            while chunk := audio.readframes(8192):
                if any(chunk):nonzero = True
        if not nonzero:
            raise ValueError('SILENT_NATIVE_AUDIO_OUTPUT')
        return {'status':'READY','id':ident,'artifact_id':ident,'provider':payload['provider'],'voice':payload.get('voice'),
                'bytes':target.stat().st_size,'duration_seconds':round(frames/rate,4),'sample_rate':rate,
                'channels':channels,'sample_width':width,'nonzero_audio_samples':True,
                'text_sha256':hashlib.sha256(payload['text'].encode()).hexdigest(),
                'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                'download_url':'/api/studio/audio/file?id='+ident,'native':value}
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        # A cancellation which cannot stop a provider must keep the busy guard until
        # its single worker really exits; never overlap process-global speech state.
        if future is not None and not future.done():
            future.add_done_callback(lambda _: _speech_lock.release())
        else:
            _speech_lock.release()

def _platform(method, path, payload):
    from studio import api, jobs
    from studio.paths import data_root
    if method == 'GET' and path == '/api/studio/capabilities':
        return {'native_dialogs':True,'native_share':True,'platform':'android','variant':_server.product_variant,
                'sql_server':False,'personal_data_separate':True,'version':'0.3.0','upload_limit_bytes':256*1024*1024}
    if method == 'GET' and path == '/api/studio/voices':
        return _invoke('speech.catalog')
    if method == 'GET' and path == '/api/studio/audio/file':
        ident = payload.get('id', [''])[0]
        if len(ident) != 32 or any(char not in '0123456789abcdef' for char in ident):
            raise ValueError('INVALID_ARTIFACT_ID')
        target = data_root() / 'audio' / (ident + '.wav')
        if not target.is_file():raise ValueError('ARTIFACT_NOT_FOUND')
        return api.FileResult(target, 'audio/wav', target.name, False)
    if method == 'POST' and path in {'/api/studio/windows-voices','/api/studio/android-voices'}:
        return _invoke('settings.voices')
    if method == 'POST' and path == '/api/studio/audio/synthesize':
        return jobs.submit('speech',lambda event,progress:_synthesize(payload,event,progress))
    if method == 'POST' and path in {'/api/studio/voice/install','/api/studio/voice/remove'}:
        raise ValueError('BUNDLED_ANDROID_VOICES_ARE_MANAGED_BY_THE_APP_PACKAGE')
    if path.startswith('/api/studio/sqlserver/'):
        raise ValueError('WINDOWS_SQL_SERVER_ADAPTER_UNAVAILABLE_ON_ANDROID_IMPORT_SQLITE_INSTEAD')
    if method == 'POST' and path == '/api/studio/export/share':
        from studio import documents
        meta = documents.get_artifact(payload['id'])
        return _invoke('share',{'source':str(documents.artifact_file(payload['id'])),'filename':meta['filename'],'mime':meta['mime']})
    return api.NOT_HANDLED

def start(asset_root, private_root, variant, session_token):
    """Start one in-process loopback service, returning its assigned port."""
    global _server, _thread
    if _server is not None:
        return _server.server_port
    if variant not in {'lite','ultimate'} or len(session_token) < 32:
        raise ValueError('INVALID_ANDROID_RUNTIME_CONFIGURATION')
    os.environ['FBR_ASSET_ROOT'] = str(Path(asset_root).resolve())
    os.environ['FBR_PARSER'] = 'portable'
    from studio import paths, native, documents, api
    paths.configure_root(Path(private_root))
    native.configure_adapter(_dialog)
    documents.configure_renderer(_document)
    api.configure_platform(_platform)
    from workbench.server import ThreadingHTTPServer, Handler
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.allowed_engine = 'all'
    server.session_token = session_token
    server.product_variant = variant
    _server = server
    _thread = threading.Thread(target=server.serve_forever, name='fbr-loopback', daemon=True)
    _thread.start()
    return server.server_port

def stop():
    """Activity lifecycle hook; safe when called from a Java worker thread."""
    global _server, _thread
    server, _server = _server, None
    if server is not None:
        try:_invoke('speech.cancel')
        except Exception:pass
        server.shutdown()
        server.server_close()
    if _thread is not None:
        _thread.join(timeout=3)
    _thread = None
