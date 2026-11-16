"""Offline speech providers, verified managed voices and private WAV artifacts.

No application/server imports, global installation or import-time process launch.
Root's job manager supplies cancellation Events and wraps these synchronous APIs.
"""
from __future__ import annotations
import array
import contextlib
import datetime as dt
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import pathlib
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
import wave
from .paths import data_root, public_root

MAX_TEXT = 25000
MAX_WAV_BYTES = 180 * 1024 * 1024
MAX_CACHE_BYTES = 256 * 1024 * 1024
MAX_CACHE_FILES = 100  # WAV plus sidecar count: at most 50 completed pairs.
_work_lock = threading.Lock()
_process_lock = threading.Lock()
_native_cache = None
_native_cache_time = 0.0
_espeak_cache = None

class AudioError(ValueError):
    def __init__(self, code, message=None):
        self.code = code
        super().__init__(message or code)

def _utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def _sha(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def _cancelled(cancellation):
    return cancellation is not None and cancellation.is_set()

def _check_cancel(cancellation):
    if _cancelled(cancellation):
        raise AudioError('CANCELLED')

def _emit(progress, **values):
    if progress:
        progress(values)

def _folder(name):
    root = data_root().resolve()
    target = root / name
    if target.exists() and (target.is_symlink() or getattr(target,'is_junction',lambda:False)()):
        raise AudioError('UNSAFE_STUDIO_PATH')
    target.mkdir(exist_ok=True)
    if not target.resolve().is_relative_to(root):
        raise AudioError('UNSAFE_STUDIO_PATH')
    return target

def _manifest():
    value = json.loads((public_root() / 'studio/voice_manifest.json').read_text(encoding='utf-8'))
    if value.get('schema_version') != 1 or value.get('provider') != 'piper':
        raise AudioError('INVALID_VOICE_MANIFEST')
    return value

def _voice(voice_id):
    if not isinstance(voice_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', voice_id):
        raise AudioError('UNKNOWN_MANAGED_VOICE')
    found = next((v for v in _manifest()['voices'] if v['id'] == voice_id), None)
    if found is None:
        raise AudioError('UNKNOWN_MANAGED_VOICE')
    return found

def _voice_path(voice_id):
    target = _folder('voices') / voice_id
    if target.is_symlink() or getattr(target,'is_junction',lambda:False)() or not target.resolve().is_relative_to(_folder('voices').resolve()):
        raise AudioError('UNSAFE_VOICE_PATH')
    return target

def _verify_voice(voice, full_hash=False):
    folder = _voice_path(voice['id'])
    if not folder.is_dir() or not (folder / 'installation.json').is_file():
        return False
    try:
        receipt = json.loads((folder / 'installation.json').read_text(encoding='utf-8'))
        if receipt.get('voice_id') != voice['id'] or receipt.get('commit') != voice['commit']:
            return False
        for item in voice['files']:
            path = folder / item['name']
            if path.is_symlink() or not path.is_file() or path.stat().st_size != item['bytes']:
                return False
            if full_hash and _sha(path) != item['sha256']:
                return False
        return True
    except (OSError, ValueError, TypeError):
        return False

def _run_owned(command, cancellation=None, timeout=300, environment=None, expect_json=True):
    """At most one provider subprocess. Kill only the child we created."""
    _check_cancel(cancellation)
    if not _process_lock.acquire(blocking=False):
        raise AudioError('PROVIDER_BUSY')
    process = None
    try:
        child_env = os.environ.copy()
        child_env.update({'PYTHONPATH':'','PYTHONHOME':'','NODE_PATH':''})
        child_env.update(environment or {})
        process = subprocess.Popen(command, cwd=public_root(), env=child_env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        started = time.monotonic()
        while True:
            if _cancelled(cancellation) or time.monotonic() - started > timeout:
                process.kill()
                process.communicate(timeout=10)
                raise AudioError('CANCELLED' if _cancelled(cancellation) else 'SYNTHESIS_TIMEOUT')
            try:
                stdout, stderr = process.communicate(timeout=.1)
                break
            except subprocess.TimeoutExpired:
                continue
        if len(stdout) > 1024 * 1024 or len(stderr) > 1024 * 1024:
            raise AudioError('PROVIDER_OUTPUT_LIMIT')
        if process.returncode != 0:
            raise AudioError('PROVIDER_FAILED', 'The selected speech provider could not generate audio.')
        if not expect_json:
            return stdout.decode('utf-8',errors='replace')
        try:
            return json.loads(stdout.decode('utf-8-sig').strip())
        except (ValueError, UnicodeError):
            raise AudioError('INVALID_PROVIDER_RESPONSE') from None
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
        _process_lock.release()

def _native_command(action):
    if sys.platform != 'win32':
        raise AudioError('WINDOWS_SPEECH_UNAVAILABLE')
    executable = pathlib.Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    if not executable.is_file():
        raise AudioError('WINDOWS_SPEECH_UNAVAILABLE')
    # The static command contains no interpolated voice, text or request pathname.
    # Existing Restricted -File policy is respected; no policy/bypass switch is used.
    code = '& {' + (public_root() / 'studio/windows_speech.ps1').read_text(encoding='utf-8') + '} -Action $env:FBR_SPEECH_ACTION -RequestPath $env:FBR_SPEECH_REQUEST'
    return [str(executable), '-NoProfile', '-NonInteractive', '-Command', code]

def _native_catalog(refresh=False):
    global _native_cache, _native_cache_time
    if sys.platform != 'win32':
        return {'voices':[],'errors':[{'provider':'windows-native','error':'WINDOWS_SPEECH_UNAVAILABLE'}]}
    if _native_cache is not None and (not refresh or _process_lock.locked()) and time.monotonic() - _native_cache_time < 300:
        return _native_cache
    try:
        value = _run_owned(_native_command('catalog'), timeout=25,
            environment={'FBR_SPEECH_ACTION':'catalog','FBR_SPEECH_REQUEST':''})
        _native_cache = value
        _native_cache_time = time.monotonic()
        return value
    except (OSError, AudioError) as error:
        return {'voices':[],'errors':[{'provider':'windows-native','error':getattr(error,'code','WINDOWS_SPEECH_UNAVAILABLE')}]}

def _espeak_runtime():
    # This preserved bundled runtime is specifically the Windows build. Other
    # platforms supply a native adapter; they must not try to execute its EXE.
    if sys.platform != 'win32':
        raise AudioError('ESPEAK_RUNTIME_UNAVAILABLE')
    folder = public_root()/'runtime/espeak-ng'
    metadata_path = public_root()/'runtime/espeak-ng-runtime.json'
    if not metadata_path.is_file():
        raise AudioError('ESPEAK_RUNTIME_UNAVAILABLE')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    executable = folder/'espeak-ng.exe'
    expected = next((f for f in metadata['files'] if f['path']=='espeak-ng.exe'),None)
    if expected is None or not executable.is_file() or _sha(executable)!=expected['sha256']:
        raise AudioError('ESPEAK_RUNTIME_INTEGRITY_FAILED')
    return folder, executable, metadata

def _espeak_catalog(refresh=False):
    global _espeak_cache
    if _espeak_cache is not None and (not refresh or _process_lock.locked()):
        return _espeak_cache
    try:
        folder, executable, metadata = _espeak_runtime()
        text = _run_owned([str(executable),'--path='+str(folder),'--voices'],timeout=20,expect_json=False)
        voices = []
        for line in text.splitlines()[1:]:
            fields = line.split()
            if len(fields)<5 or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',fields[1]) or fields[4].startswith('mb'):
                continue
            voices.append({'provider':'espeak-ng','id':fields[1],'language':fields[1],
                'name':fields[3].replace('_',' '),'gender':fields[2],'managed':False,
                'installed':True,'removable':False,'installation_kind':'BUNDLED_RUNTIME'})
        _espeak_cache = {'voices':voices,'available':bool(voices),'version':metadata['runtime_version'],'errors':[]}
        return _espeak_cache
    except (AudioError,OSError,ValueError,KeyError) as error:
        return {'voices':[],'available':False,'errors':[{'provider':'espeak-ng','error':getattr(error,'code','ESPEAK_RUNTIME_UNAVAILABLE')}]}

def voice_catalog(refresh=False):
    native = _native_catalog(refresh)
    espeak = _espeak_catalog(refresh)
    voices = list(native.get('voices', []))+list(espeak['voices'])
    piper_available = importlib.util.find_spec('piper') is not None
    try:
        version = importlib.metadata.version('piper-tts')
    except importlib.metadata.PackageNotFoundError:
        version = None
    for item in _manifest()['voices']:
        installed = _verify_voice(item)
        voices.append({key:item[key] for key in ('id','provider','name','language','quality','license','license_url','sample_rate')} | {
            'managed':True,'installed':installed,'removable':_voice_path(item['id']).exists(),
            'download_bytes':sum(f['bytes'] for f in item['files']),
            'integrity_basis':'INSTALL_RECEIPT_AND_SIZES' if installed else 'NOT_VERIFIED',
            'runtime_available':piper_available,'repository':item['repository'],'commit':item['commit']})
    providers = [
        {'id':name,'available':any(v['provider']==name for v in voices),'managed':False}
        for name in ('windows-sapi','windows-media')]
    providers.append({'id':'piper','available':piper_available,'version':version,'managed':True,'device':'CPU'})
    providers.append({'id':'espeak-ng','available':espeak['available'],'managed':False,'version':espeak.get('version'),'installation_kind':'BUNDLED_RUNTIME'})
    return {'status':'OK','providers':providers,'voices':voices,'errors':native.get('errors',[])+espeak.get('errors',[]),
        'default':{'provider':'piper','voice':'ro_RO-mihai-medium'},
        'limits':{'max_text_characters':MAX_TEXT,'speed_min':.5,'speed_max':2,'provider_processes':1},
        'windows_voice_management':'WINDOWS_SETTINGS_ONLY','audible_listening_verified':False}

def install_voice(voice_id, progress=None, cancellation=None):
    voice = _voice(voice_id)
    if not _work_lock.acquire(blocking=False):
        raise AudioError('AUDIO_BUSY')
    stage = None
    try:
        _check_cancel(cancellation)
        target = _voice_path(voice_id)
        if target.exists():
            if _verify_voice(voice, full_hash=True):
                return {'status':'ALREADY_INSTALLED','voice_id':voice_id,'verified':True}
            raise AudioError('VOICE_PRESENT_BUT_INVALID', 'Remove the managed voice before reinstalling it.')
        stage = _folder('voices') / ('.install-' + uuid.uuid4().hex)
        stage.mkdir()
        total = sum(item['bytes'] for item in voice['files'])
        completed = 0
        for item in voice['files']:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', item['name']) or not re.fullmatch(r'[a-f0-9]{64}', item['sha256']):
                raise AudioError('INVALID_VOICE_MANIFEST')
            url = urllib.parse.urlsplit(item['url'])
            if url.scheme != 'https' or url.hostname != 'huggingface.co' or url.query or voice['commit'] not in url.path:
                raise AudioError('INVALID_VOICE_SOURCE')
            _check_cancel(cancellation)
            destination = stage / item['name']
            digest = hashlib.sha256()
            received = 0
            with urllib.request.urlopen(urllib.request.Request(item['url'], headers={'User-Agent':'Free-Bible-Reader-Voice-Manager/0.2.0'}), timeout=30) as response, destination.open('xb') as output:
                if response.status != 200 or (response.headers.get('Content-Length') is not None and int(response.headers['Content-Length']) != item['bytes']):
                    raise AudioError('VOICE_DOWNLOAD_SIZE_MISMATCH')
                while block := response.read(256 * 1024):
                    _check_cancel(cancellation)
                    received += len(block)
                    if received > item['bytes']:
                        raise AudioError('VOICE_DOWNLOAD_SIZE_MISMATCH')
                    output.write(block)
                    digest.update(block)
                    _emit(progress, phase='download',voice_id=voice_id,downloaded_bytes=completed+received,total_bytes=total)
            if received != item['bytes'] or digest.hexdigest() != item['sha256']:
                raise AudioError('VOICE_DOWNLOAD_INTEGRITY_FAILED')
            completed += received
        config = json.loads((stage / (voice_id+'.onnx.json')).read_text(encoding='utf-8'))
        if config.get('audio',{}).get('sample_rate') != voice['sample_rate']:
            raise AudioError('VOICE_CONFIG_MISMATCH')
        receipt = {'voice_id':voice_id,'provider':'piper','commit':voice['commit'],'installed_utc':_utc(),
            'files':voice['files'],'license':voice['license'],'license_url':voice['license_url'],'all_sha256_verified':True}
        (stage / 'installation.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        _check_cancel(cancellation)
        stage.rename(target)
        stage = None
        _emit(progress,phase='complete',voice_id=voice_id,downloaded_bytes=total,total_bytes=total)
        return {'status':'INSTALLED_AND_VERIFIED','voice_id':voice_id,'verified':True,'bytes':total,'commit':voice['commit']}
    finally:
        try:
            if stage is not None and stage.is_dir():
                # Delete only files in our fresh, randomly named staging directory.
                for path in stage.iterdir():
                    if path.is_file() and not path.is_symlink():
                        path.unlink()
                stage.rmdir()
        finally:
            _work_lock.release()

def remove_voice(voice_id):
    voice = _voice(voice_id)
    if not _work_lock.acquire(blocking=False):
        raise AudioError('AUDIO_BUSY')
    try:
        target = _voice_path(voice_id)
        if not target.exists():
            return {'status':'NOT_INSTALLED','voice_id':voice_id}
        permitted = {item['name'] for item in voice['files']} | {'installation.json'}
        children = list(target.iterdir())
        if any(path.name not in permitted or not path.is_file() or path.is_symlink() for path in children):
            raise AudioError('UNEXPECTED_VOICE_FILES', 'The voice directory contains unrelated files; they were preserved.')
        for path in children:
            path.unlink()
        target.rmdir()
        return {'status':'REMOVED','voice_id':voice_id,'managed_files_only':True}
    finally:
        _work_lock.release()

def artifact_path(artifact_id):
    if not isinstance(artifact_id,str) or not re.fullmatch(r'[a-f0-9]{32}',artifact_id):
        raise AudioError('INVALID_ARTIFACT_ID')
    path = _folder('audio') / (artifact_id+'.wav')
    if path.is_symlink() or not path.resolve().is_relative_to(_folder('audio').resolve()) or not path.is_file():
        raise AudioError('ARTIFACT_NOT_FOUND')
    return path

def _prune_completed_cache(protect_ids=(), reserve_bytes=0, reserve_files=0):
    """Only completed artifacts carrying our marker are eligible for eviction."""
    folder = _folder('audio')
    entries = []
    for sidecar in folder.glob('*.json'):
        if not re.fullmatch(r'[a-f0-9]{32}',sidecar.stem) or sidecar.is_symlink() or sidecar.stat().st_size>65536:
            continue
        wav = folder/(sidecar.stem+'.wav')
        try:
            metadata = json.loads(sidecar.read_text(encoding='utf-8'))
            if metadata.get('managed_by')!='free-bible-reader-audio' or metadata.get('status')!='READY' or metadata.get('artifact_id')!=sidecar.stem or not wav.is_file() or wav.is_symlink():
                continue
            entries.append({'id':sidecar.stem,'wav':wav,'sidecar':sidecar,'bytes':wav.stat().st_size+sidecar.stat().st_size,'modified':wav.stat().st_mtime_ns})
        except (OSError,ValueError):
            continue
    entries.sort(key=lambda item:item['modified'])
    protected = set(protect_ids)
    if entries:
        protected.add(entries[-1]['id'])
    total = sum(item['bytes'] for item in entries)+reserve_bytes
    count = len(entries)*2+reserve_files
    removed, locked = [], []
    for item in entries:
        if total<=MAX_CACHE_BYTES and count<=MAX_CACHE_FILES:
            break
        if item['id'] in protected:
            continue
        try:
            item['wav'].unlink()
            item['sidecar'].unlink()
        except OSError:
            locked.append(item['id'])
            continue
        total-=item['bytes'];count-=2;removed.append(item['id'])
    return {'budget_met':total<=MAX_CACHE_BYTES and count<=MAX_CACHE_FILES,'managed_bytes_including_reservation':total,
        'managed_files_including_reservation':count,'max_bytes':MAX_CACHE_BYTES,'max_files':MAX_CACHE_FILES,
        'removed_artifact_ids':removed,'locked_or_unavailable_artifact_ids':locked,'protected_latest':True}

def prune_audio_cache(protect_ids=()):
    if not _work_lock.acquire(blocking=False):
        return {'status':'DEFERRED','reason':'AUDIO_BUSY'}
    try:
        return {'status':'OK',**_prune_completed_cache(protect_ids)}
    finally:
        _work_lock.release()

def _wav_info(path):
    size = path.stat().st_size
    if not 44 < size <= MAX_WAV_BYTES:
        raise AudioError('INVALID_AUDIO_OUTPUT')
    try:
        with wave.open(str(path),'rb') as wav:
            frames,rate,channels,width = wav.getnframes(),wav.getframerate(),wav.getnchannels(),wav.getsampwidth()
            if frames <= 0 or not 8000 <= rate <= 192000 or channels not in (1,2) or width not in (1,2,3,4):
                raise AudioError('INVALID_AUDIO_OUTPUT')
            sample = wav.readframes(min(frames,rate*5))
            if not sample or not any(sample):
                raise AudioError('SILENT_AUDIO_OUTPUT')
        return {'bytes':size,'sample_rate':rate,'channels':channels,'sample_width':width,'frames':frames,'duration_seconds':round(frames/rate,4),'sha256':_sha(path),'nonzero_audio_samples':True}
    except (wave.Error,EOFError):
        raise AudioError('INVALID_AUDIO_OUTPUT') from None

def synthesize(request, cancellation=None, progress=None):
    if not isinstance(request,dict):
        raise AudioError('INVALID_SYNTHESIS_REQUEST')
    text = request.get('text')
    if not isinstance(text,str) or not text.strip() or len(text) > MAX_TEXT or '\0' in text:
        raise AudioError('INVALID_TEXT')
    speed = request.get('speed',1.0)
    if isinstance(speed,bool) or not isinstance(speed,(int,float)) or not math.isfinite(speed) or not .5 <= speed <= 2:
        raise AudioError('INVALID_SPEED')
    provider = request.get('provider','piper')
    voice_id = request.get('voice','ro_RO-mihai-medium')
    if provider not in ('piper','windows-sapi','windows-media','espeak-ng') or not isinstance(voice_id,str) or len(voice_id)>2048:
        raise AudioError('UNSUPPORTED_PROVIDER_OR_VOICE')
    if not _work_lock.acquire(blocking=False):
        raise AudioError('AUDIO_BUSY')
    output = None
    job = None
    try:
        _check_cancel(cancellation)
        artifact_id = uuid.uuid4().hex
        output = _folder('audio') / (artifact_id+'.wav')
        job = _folder('audio-jobs') / (uuid.uuid4().hex+'.json')
        payload = {'provider':provider,'voice':voice_id,'text':text,'speed':float(speed),'output_path':str(output)}
        if provider == 'piper':
            voice = _voice(voice_id)
            if not _verify_voice(voice,full_hash=True):
                raise AudioError('VOICE_NOT_INSTALLED_OR_CORRUPT')
            folder = _voice_path(voice_id)
            payload.update(model_path=str(folder/(voice_id+'.onnx')),config_path=str(folder/(voice_id+'.onnx.json')))
            if getattr(sys,'frozen',False):
                command = [sys.executable,'--tts-worker',str(job)]
            else:
                command = [sys.executable,'-m','studio.piper_worker',str(job)]
            environment = {}
        elif provider == 'espeak-ng':
            voice = next((item for item in _espeak_catalog()['voices'] if item['id']==voice_id),None)
            if voice is None:
                raise AudioError('VOICE_NOT_AVAILABLE')
            folder, executable, metadata = _espeak_runtime()
            command = [str(executable),'--path='+str(folder),'-b','1','-v',voice_id,'-s',str(round(175*speed)),'-w',str(output),'-f',str(job)]
            environment = {}
        else:
            voice = next((item for item in _native_catalog()['voices'] if item['provider']==provider and item['id']==voice_id),None)
            if voice is None:
                raise AudioError('VOICE_NOT_AVAILABLE')
            command = _native_command('synthesize')
            environment = {'FBR_SPEECH_ACTION':'synthesize','FBR_SPEECH_REQUEST':str(job)}
        with job.open('x',encoding='utf-8') as stream:
            if provider == 'espeak-ng':
                stream.write(text)
            else:
                json.dump(payload,stream,ensure_ascii=False)
        _emit(progress,phase='synthesis',provider=provider,voice_id=voice_id)
        _run_owned(command,cancellation=cancellation,timeout=300,environment=environment,expect_json=(provider!='espeak-ng'))
        _check_cancel(cancellation)
        info = _wav_info(output)
        result = {'status':'READY','id':artifact_id,'artifact_id':artifact_id,'path':str(output),'file_name':output.name,
            'managed_by':'free-bible-reader-audio','schema_version':1,
            'mime_type':'audio/wav','provider':provider,'voice':voice_id,'voice_name':voice['name'],
            'requested_speed':speed,'text_characters':len(text),'text_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'generated_utc':_utc(),'audible_listening_verified':False,**info}
        # Reserve space before publishing this artifact as completed. If protected
        # or locked old files prevent a bounded cache, reject this unfinished WAV.
        result['cache'] = _prune_completed_cache(reserve_bytes=info['bytes']+65536,reserve_files=2)
        if not result['cache']['budget_met']:
            raise AudioError('AUDIO_CACHE_BUDGET_BLOCKED','The audio cache is busy or locked; no additional audio was retained.')
        metadata = json.dumps(result,ensure_ascii=False,indent=2)
        if len(metadata.encode('utf-8'))>65536:
            raise AudioError('ARTIFACT_METADATA_LIMIT')
        with output.with_suffix('.json').open('x',encoding='utf-8') as stream:
            stream.write(metadata)
        _emit(progress,phase='complete',artifact_id=artifact_id)
        return result
    except Exception:
        if output is not None and output.is_file() and not output.is_symlink():
            output.unlink()
        if output is not None and output.with_suffix('.json').is_file() and not output.with_suffix('.json').is_symlink():
            output.with_suffix('.json').unlink()
        raise
    finally:
        try:
            if job is not None and job.is_file() and not job.is_symlink():
                job.unlink()
        finally:
            _work_lock.release()
