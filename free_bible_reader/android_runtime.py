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
import time
import re
from .android_voice_policy import candidates, SpeechError
import uuid
import wave

_server = None
_thread = None
_speech_lock = threading.Lock()
_narration_paused = threading.Event()
_speech_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='fbr-native-speech')

def _invoke(operation, payload=None):
    from java import jclass
    raw = jclass('com.freebiblereader.android.PlatformAdapter').invoke(operation, json.dumps(payload or {}, ensure_ascii=False, allow_nan=False))
    result = json.loads(str(raw))
    if result.get('status') == 'ERROR' or isinstance(result.get('error'), dict):
        detail=result.get('error')
        code=result.get('code') or (detail.get('code') if isinstance(detail,dict) else None)
        message=result.get('message') or (detail.get('message') if isinstance(detail,dict) else detail) or 'NATIVE_OPERATION_FAILED'
        if not code and re.fullmatch(r'[A-Z][A-Z0-9_]{2,80}',str(message)):code=str(message)
        raise SpeechError(code or 'NATIVE_OPERATION_FAILED', str(message))
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

def _wave_info(target):
    if not target.is_file() or not 44 < target.stat().st_size < 30_000_000:
        raise SpeechError('INVALID_NATIVE_AUDIO_OUTPUT')
    nonzero=False
    try:
        with wave.open(str(target),'rb') as audio:
            rate,frames=audio.getframerate(),audio.getnframes()
            channels,width=audio.getnchannels(),audio.getsampwidth()
            if rate<=0 or frames<=0 or channels not in {1,2} or width!=2:
                raise SpeechError('UNSUPPORTED_NATIVE_PCM_FORMAT')
            while chunk:=audio.readframes(8192):
                if any(chunk):nonzero=True
    except (wave.Error,EOFError) as error:
        raise SpeechError('INVALID_NATIVE_AUDIO_OUTPUT',str(error)) from error
    if not nonzero:raise SpeechError('SILENT_NATIVE_AUDIO_OUTPUT')
    return {'bytes':target.stat().st_size,'duration_seconds':round(frames/rate,4),'sample_rate':rate,'channels':channels,'sample_width':width,'nonzero_audio_samples':True,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}

def _native_play(target,volume,cancellation,progress,voice,info):
    # Generation and playback have distinct success conditions. This job returns
    # narration_completed only after the Android MediaPlayer completes this ID.
    while _narration_paused.is_set():
        if cancellation.wait(.15):raise SpeechError('SPEECH_CANCELLED')
        progress(phase='paused',provider=voice['provider'],voice_name=voice.get('name'))
    value=_invoke('playback.start',{'source':str(target),'volume':volume})
    ident=value.get('playback_id')
    if not ident:raise SpeechError('PLAYBACK_NOT_STARTED')
    deadline=time.monotonic()+min(1800,max(60,info['duration_seconds']*2+30));last=time.monotonic()
    try:
        while True:
            if cancellation.is_set():raise SpeechError('SPEECH_CANCELLED')
            value=_invoke('playback.status')
            if value.get('playback_id')!=ident:raise SpeechError('PLAYBACK_REPLACED')
            now=time.monotonic()
            if _narration_paused.is_set():
                deadline+=now-last
                if value.get('state') not in {'paused','completed','error'}:_invoke('playback.pause')
            last=now
            state=value.get('state')
            progress(phase='paused' if _narration_paused.is_set() else state,provider=voice['provider'],voice_name=voice.get('name'),playback_id=ident,position_ms=value.get('position_ms',0),duration_ms=value.get('duration_ms',0))
            if state=='error':raise SpeechError('AUDIO_PLAYBACK_FAILED',str(value.get('error') or 'Android media playback failed'))
            if value.get('completed') is True:
                return {'playback_id':ident,'narration_completed':True,'playback':value,'human_listening_verified':False}
            if state=='stopped':raise SpeechError('SPEECH_CANCELLED')
            if now>deadline:raise SpeechError('AUDIO_PLAYBACK_TIMEOUT')
            cancellation.wait(.2)
    except Exception:
        try:_invoke('playback.stop')
        except Exception:pass
        raise

def _synthesize(payload,cancellation,progress,narration=False):
    from studio.paths import data_root
    if not isinstance(payload.get('text'),str) or not 0<len(payload['text'].strip())<=6000 or '\0' in payload['text']:
        raise SpeechError('INVALID_TEXT')
    speed=payload.get('speed',1);volume=payload.get('volume',1)
    if isinstance(speed,bool) or not isinstance(speed,(int,float)) or not .5<=speed<=2:raise SpeechError('INVALID_SPEED')
    if isinstance(volume,bool) or not isinstance(volume,(int,float)) or not 0<=volume<=1:raise SpeechError('INVALID_VOLUME')
    if not _speech_lock.acquire(blocking=False):raise SpeechError('AUDIO_BUSY')
    folder=data_root()/'audio';folder.mkdir(exist_ok=True);ident=uuid.uuid4().hex
    future=None;temporary=None;target=folder/(ident+'.wav');attempts=[]
    generation_deadline=time.monotonic()+180
    try:
        progress(phase='discovering-voices')
        options,expected=candidates(payload,_invoke('speech.catalog'))
        retained=0
        for index,file in enumerate(sorted(folder.glob('*.wav'),key=lambda p:p.stat().st_mtime,reverse=True)):
            retained+=file.stat().st_size
            if index>=100 or retained>64*1024*1024:
                try:file.unlink()
                except OSError:pass
        for number,voice in enumerate(options,1):
            if cancellation.is_set():raise SpeechError('SPEECH_CANCELLED')
            temporary=folder/(ident+'-'+str(number)+'.wav')
            request_id=ident+'-'+str(number)
            request={**payload,'provider':voice['provider'],'voice':voice['id'],'voice_name':voice.get('voice_name',voice.get('name')),'engine_package':voice.get('engine_package'),'expected_language':expected,'output_path':str(temporary),'request_id':request_id}
            progress(phase='synthesizing' if number==1 else 'recovering',attempt=number,max_attempts=len(options),provider=voice['provider'],voice_name=voice.get('name'))
            try:
                future=_speech_pool.submit(_invoke,'speech.synthesize',request)
                deadline=min(generation_deadline,time.monotonic()+90)
                while True:
                    try:
                        native=future.result(timeout=.15);break
                    except concurrent.futures.TimeoutError:
                        if cancellation.is_set() or time.monotonic()>deadline:
                            try:_invoke('speech.cancel',{'request_id':request_id})
                            except Exception:pass
                            try:future.result(timeout=10)
                            except Exception:pass
                            if not future.done():raise SpeechError('SPEECH_WORKER_STILL_STOPPING')
                            raise SpeechError('SPEECH_CANCELLED' if cancellation.is_set() else 'SYNTHESIS_TIMEOUT')
                if cancellation.is_set():raise SpeechError('SPEECH_CANCELLED')
                info=_wave_info(temporary);temporary.replace(target);temporary=None
                playback=_native_play(target,volume,cancellation,progress,voice,info) if narration else {'narration_completed':False}
                attempts.append({'provider':voice['provider'],'voice':voice['id'],'status':'COMPLETE'})
                return {'status':'COMPLETE' if narration else 'READY','id':ident,'artifact_id':ident,'provider':voice['provider'],'voice':voice['id'],'voice_name':voice.get('name'),'engine_package':voice.get('engine_package'),'expected_language':expected,'speech_mode':payload.get('speech_mode','selected'),'fallback_used':number>1,'attempts':attempts,'text_sha256':hashlib.sha256(payload['text'].encode()).hexdigest(),'download_url':'/api/studio/audio/file?id='+ident,'native':native,**info,**playback}
            except Exception as error:
                code=getattr(error,'code','NATIVE_OPERATION_FAILED')
                attempts.append({'provider':voice['provider'],'voice':voice['id'],'status':'FAILED','code':code,'message':str(error)[:250]})
                if temporary is not None and (future is None or future.done()):temporary.unlink(missing_ok=True)
                target.unlink(missing_ok=True)
                if cancellation.is_set() or code in {'CANCELLED','SPEECH_CANCELLED','SYNTHESIS_CANCELLED','SPEECH_WORKER_STILL_STOPPING'}:raise
                if number==len(options):
                    raise SpeechError('SPEECH_RECOVERY_FAILED' if len(options)>1 else code,'; '.join(a['provider']+': '+a.get('code','COMPLETE') for a in attempts)) from error
                if future is not None and not future.done():raise SpeechError('SPEECH_WORKER_STILL_STOPPING')
        raise SpeechError('NO_COMPATIBLE_VOICE')
    finally:
        if future is not None and not future.done():
            unfinished=temporary
            def settled(_):
                if unfinished is not None:unfinished.unlink(missing_ok=True)
                _speech_lock.release()
            future.add_done_callback(settled)
        else:
            if temporary is not None:temporary.unlink(missing_ok=True)
            _speech_lock.release()

def _platform(method, path, payload):
    from studio import api, jobs
    from studio.paths import data_root
    if method == 'GET' and path == '/api/studio/capabilities':
        return {'native_dialogs':True,'native_share':True,'platform':'android','variant':_server.product_variant,
                'sql_server':False,'personal_data_separate':True,'version':getattr(_server,'product_version','0.3.1-beta.1'),'upload_limit_bytes':256*1024*1024}
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
    if method == 'POST' and path == '/api/studio/speech/engine':
        return _invoke('speech.engine.select',payload)
    if method == 'POST' and path in {'/api/studio/audio/synthesize','/api/studio/audio/narrate'}:
        narration=path.endswith('/narrate')
        if narration:_narration_paused.clear()
        return jobs.submit('narration' if narration else 'speech',lambda event,progress:_synthesize(payload,event,progress,narration=narration))
    if path.startswith('/api/studio/playback/'):
        operation=path.rsplit('/',1)[-1]
        if operation not in {'status','pause','resume','stop','volume'}:raise SpeechError('UNKNOWN_PLAYBACK_ACTION')
        if method=='POST':
            if operation=='pause':_narration_paused.set()
            elif operation in {'resume','stop'}:_narration_paused.clear()
            if operation=='resume':
                state=_invoke('playback.status')
                if state.get('state') in {'idle','stopped','completed'}:return state
        return _invoke('playback.'+operation,payload if method=='POST' else {})
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
    server.product_version = _invoke('app.info').get('version','0.3.1-beta.1')
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
