"""Local studio routes. Filesystem capabilities originate in native picks/uploads."""
from __future__ import annotations
import dataclasses
import hashlib
import pathlib
import re
import threading
import time
import uuid
from . import jobs, native
from .paths import data_root

@dataclasses.dataclass
class FileResult:
    path: pathlib.Path
    mime: str
    filename: str
    attachment: bool = True

_sources = {}
_source_lock = threading.RLock()

def register_source(path):
    path = pathlib.Path(path).resolve()
    if not path.is_file() or path.suffix.lower() not in {'.sqlite','.sqlite3','.db','.db3','.sql','.zip','.csv','.json','.jsonl','.ndjson'}:
        raise ValueError('UNSUPPORTED_SOURCE_FILE')
    ident = uuid.uuid4().hex
    with _source_lock:
        if len(_sources) >= 100:
            _sources.pop(next(iter(_sources)))
        _sources[ident] = path
    native.protect(path)
    return {'source_handle':ident, 'filename':path.name, 'bytes':path.stat().st_size}

def upload(stream, length, filename):
    if not 0 < length <= 256*1024*1024:
        raise ValueError('UPLOAD_LIMIT_256_MIB_USE_NATIVE_PICKER_FOR_LARGER_DATABASES')
    suffix = pathlib.PurePath(filename).suffix.lower()
    if suffix not in {'.sqlite','.sqlite3','.db','.db3','.sql','.zip','.csv','.json','.jsonl','.ndjson'}:
        raise ValueError('UNSUPPORTED_SOURCE_FILE')
    folder = data_root()/'staging'
    folder.mkdir(exist_ok=True)
    target = folder/(uuid.uuid4().hex+suffix)
    digest = hashlib.sha256()
    try:
        with target.open('xb') as output:
            remaining = length
            while remaining:
                chunk = stream.read(min(65536, remaining))
                if not chunk:
                    raise ValueError('INCOMPLETE_UPLOAD')
                output.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
        return dict(register_source(target), sha256=digest.hexdigest())
    except Exception:
        target.unlink(missing_ok=True)
        raise

def _source(handle):
    with _source_lock:
        value = _sources.get(handle)
    if value is None:
        raise ValueError('SOURCE_HANDLE_EXPIRED_CHOOSE_FILE_AGAIN')
    return value

def _audio_result(result):
    return dict(result, download_url='/api/studio/audio/file?id='+result['artifact_id'])

def get(path, q):
    one = lambda key, default=None:q.get(key,[default])[0]
    if path == '/api/studio/capabilities':
        return {'native_dialogs':native.available(), 'personal_data_separate':True, 'upload_limit_bytes':256*1024*1024, 'version':'0.2.0'}
    if path == '/api/studio/voices':
        from . import audio
        return audio.voice_catalog(refresh=one('refresh') == 'true')
    if path == '/api/studio/audio/file':
        from . import audio
        value=audio.artifact_path(one('id'))
        return FileResult(value,'audio/wav',value.name,False)
    if path == '/api/studio/job':
        return jobs.snapshot(one('id'))
    if path == '/api/studio/library':
        from . import library
        return {'editions':library.list_editions(include_importing=True),'jobs':library.jobs()}
    if path == '/api/studio/library/editions':
        from . import library
        return library.list_source_editions(one('inspection_id'), query=one('query',''), limit=int(one('limit','50')),offset=int(one('offset','0')),source_edition_id=one('source_edition_id'))
    if path == '/api/studio/library/job':
        from . import library
        return library.import_status(one('id'))
    if path == '/api/studio/library/stats':
        from . import library
        return library.edition_stats(one('edition'))
    if path == '/api/studio/library/export/file':
        from . import library
        value=library.export_info(one('id'))
        return FileResult(library.export_path(one('id')),value['mime'],value['filename'])
    if path == '/api/studio/workspace':
        from . import workspace
        return workspace.list_items(one('type'),one('query'),limit=int(one('limit','100')),offset=int(one('offset','0')),**{key:one(key) for key in ('edition_id','book','chapter') if one(key) is not None})
    if path == '/api/studio/item':
        from . import workspace
        return workspace.get_item(one('id'))
    if path == '/api/studio/documents':
        from . import documents
        return documents.list_artifacts()
    document_match=re.fullmatch(r'/api/studio/documents/([a-fA-F0-9-]{36})/download',path)
    if path == '/api/studio/document/file' or document_match:
        from . import documents
        ident=document_match[1] if document_match else one('id')
        meta=documents.get_artifact(ident)
        return FileResult(documents.artifact_file(ident),meta['mime'],meta['filename'])
    return None

def post(path, p):
    if path == '/api/studio/job/cancel':
        return jobs.cancel(p['id'])
    if path == '/api/studio/source/choose':
        result=native.request('open',language=p.get('language','en'))
        return result if result.get('cancelled') else register_source(result['path'])
    if path == '/api/studio/quit':
        return native.request('quit')
    if path == '/api/studio/windows-voices':
        import os
        if os.name != 'nt':
            raise ValueError('WINDOWS_SETTINGS_UNAVAILABLE')
        os.startfile('ms-settings:speech')
        return {'opened':'Windows Speech settings','voice_installation_not_asserted':True}
    if path == '/api/studio/voice/install':
        from . import audio
        return jobs.submit('voice-install',lambda event,progress:audio.install_voice(p['voice'],cancellation=event,progress=lambda info:progress(**info)))
    if path == '/api/studio/voice/remove':
        from . import audio
        if p.get('confirmed') is not True:raise ValueError('CONFIRMATION_REQUIRED')
        return audio.remove_voice(p['voice'])
    if path == '/api/studio/audio/synthesize':
        from . import audio
        return jobs.submit('speech',lambda event,progress:_audio_result(audio.synthesize(p,cancellation=event,progress=lambda info:progress(**info))))
    if path == '/api/studio/search':
        from . import search
        options={key:p[key] for key in ('query','edition','books','testament','mode','diacritics','limit','offset') if key in p}
        return jobs.submit('search',lambda event,progress:search.search(**options,cancel_event=event))
    if path == '/api/studio/library/inspect':
        from . import library
        source=_source(p['source_handle'])
        return jobs.submit('inspect',lambda event,progress:library.inspect_source(source,format=p.get('format'),member=p.get('member'),copy=False))
    if path == '/api/studio/library/preview':
        from . import library
        return library.preview_import(p['inspection_id'],p['mapping'],p.get('metadata'))
    if path == '/api/studio/library/import':
        from . import library
        created=library.create_import(p['inspection_id'],p['mapping'],p['metadata'],confirmed=p.get('confirmed',False))
        return start_import(created['id'])
    if path == '/api/studio/library/resume':
        from . import library
        library.resume_import(p['id'])
        return start_import(p['id'])
    if path == '/api/studio/library/cancel':
        from . import library
        return library.cancel_import(p['id'])
    if path == '/api/studio/library/remove':
        from . import library
        return library.remove_edition(p['edition'],confirmed=p.get('confirmed',False))
    if path == '/api/studio/library/reindex':
        from . import library
        return library.rebuild_search_index() if hasattr(library,'rebuild_search_index') else _reindex_personal()
    if path == '/api/studio/library/export':
        from . import library
        def export(event,progress):
            value=library.export_edition(p['edition'],confirmed=p.get('confirmed',False))
            return dict(value,download_url='/api/studio/library/export/file?id='+value['id'])
        return jobs.submit('library-export',export)
    if path == '/api/studio/library/export/save':
        from . import library
        value=library.export_info(p['id'])
        return native.request('save',source=str(library.export_path(p['id'])),filename=value['filename'],language=p.get('language','en'))
    if path == '/api/studio/library/download':
        from . import downloads
        def download(event, progress):
            result=downloads.stage_download(p['url'],expected_sha256=p.get('sha256') or None,auth=p.get('auth'),cancel_event=event,progress=lambda info:progress(**info))
            return dict(result,**register_source(result['path']))
        return jobs.submit('download',download)
    if path == '/api/studio/sqlserver/inspect':
        from . import sqlserver
        return jobs.submit('sqlserver-inspect',lambda event,progress:sqlserver.inspect_sqlserver(p['server'],p['database'],encrypt=p.get('encrypt',True),trust_server_certificate=p.get('trust_server_certificate',False)))
    if path == '/api/studio/sqlserver/editions':
        from . import sqlserver
        return jobs.submit('sqlserver-editions',lambda event,progress:sqlserver.list_sqlserver_editions(p['server'],p['database'],encrypt=p.get('encrypt',True),trust_server_certificate=p.get('trust_server_certificate',False)))
    if path == '/api/studio/sqlserver/stage':
        from . import sqlserver
        def stage(event,progress):
            options={key:p[key] for key in ('server','database','schema','table','order_column','edition_column','edition_value','encrypt','trust_server_certificate','maximum','profile') if key in p}
            result=sqlserver.stage_sqlserver(**options,cancel_event=event,progress=lambda info:progress(**info))
            return dict(result,**register_source(result['path']))
        return jobs.submit('sqlserver-stage',stage)
    if path == '/api/studio/workspace/create':
        from . import workspace
        return workspace.create_item(p)
    if path == '/api/studio/workspace/update':
        from . import workspace
        return workspace.update_item(p['id'],p['patch'],p.get('revision'))
    if path == '/api/studio/workspace/delete':
        from . import workspace
        return workspace.delete_item(p['id'],p.get('revision'))
    if path == '/api/studio/collection/add':
        from . import workspace
        return workspace.add_collection_item(p['id'],p['item'])
    if path == '/api/studio/collection/remove':
        from . import workspace
        return workspace.remove_collection_item(p['id'],p['member_id'])
    if path == '/api/studio/export':
        from . import documents
        return jobs.submit('export',lambda event,progress:documents.create_export(p))
    if path == '/api/studio/export/save':
        from . import documents
        meta=documents.get_artifact(p['id'])
        return native.request('save',source=str(documents.artifact_file(p['id'])),filename=meta['filename'],language=p.get('language','en'))
    return None

def start_import(ident):
    from . import library
    def run(event,progress):
        started=time.monotonic();initial=library.import_status(ident)['inserted']
        while True:
            state=library.run_import(ident,batch_size=500,cancel_event=event)
            progress(import_id=ident,rows=state['inserted'],elapsed_seconds=round(time.monotonic()-started,2),rows_per_second=round((state['inserted']-initial)/max(time.monotonic()-started,.001),1))
            if state['status'] in {'COMPLETE','CANCELLED','FAILED'}:return state
    return dict(jobs.submit('import',run),import_id=ident)

def _reindex_personal():
    from . import library
    import contextlib
    with library._WRITE_LOCK, contextlib.closing(library.connect(True)) as db, db:
        db.execute("INSERT INTO PersonalSearch(PersonalSearch) VALUES('rebuild')")
    return {'status':'COMPLETE','scope':'Personal library only; bundled indexes unchanged'}
