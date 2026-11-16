"""Bounded cancellable work. Job snapshots never expose filesystem paths."""
from __future__ import annotations
import concurrent.futures
import copy
import threading
import time
import uuid

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix='fbr-studio')
_lock = threading.RLock()
_jobs = {}

def public(value):
    if isinstance(value, dict):
        private = {'path', 'source_path', 'local_path', 'model_path', 'password',
                   'token', 'authorization', 'connection_string', 'auth', 'secret'}
        return {key: public(item) for key, item in value.items()
                if str(key).casefold() not in private}
    if isinstance(value, (list, tuple)):
        return [public(item) for item in value]
    return value

def submit(kind, operation):
    with _lock:
        active = sum(item['state'] in {'QUEUED','RUNNING'} for item in _jobs.values())
        if active >= 6:
            raise ValueError('TOO_MANY_ACTIVE_JOBS')
        ident = uuid.uuid4().hex
        event = threading.Event()
        job = {'id':ident, 'kind':kind, 'state':'QUEUED', 'created_at':time.time(), 'progress':{}, 'event':event}
        _jobs[ident] = job
        # Retain a bounded recent history, not source text or a permanent daemon.
        old = sorted((v for v in _jobs.values() if v['state'] not in {'QUEUED','RUNNING'}), key=lambda v:v['created_at'])
        for entry in old[:-100]:
            _jobs.pop(entry['id'], None)
    def progress(**changes):
        with _lock:
            job['progress'].update(public(changes))
    def run():
        with _lock:
            job['state'] = 'CANCELLED' if event.is_set() else 'RUNNING'
        if event.is_set():
            return
        try:
            result = operation(event, progress)
            with _lock:
                job['result'] = public(result)
                job['state'] = 'CANCELLED' if event.is_set() else 'COMPLETE'
        except Exception as error:
            with _lock:
                job['state'] = 'CANCELLED' if event.is_set() else 'FAILED'
                job['error'] = {'code':getattr(error,'code',type(error).__name__), 'message':str(error)[:1000]}
        finally:
            with _lock:
                job['finished_at'] = time.time()
    _executor.submit(run)
    return snapshot(ident)

def snapshot(ident):
    with _lock:
        job = _jobs.get(ident)
        if job is None:
            raise ValueError('JOB_NOT_FOUND')
        return copy.deepcopy({key:value for key,value in job.items() if key != 'event'})

def cancel(ident):
    with _lock:
        job = _jobs.get(ident)
        if job is None:
            raise ValueError('JOB_NOT_FOUND')
        job['event'].set()
    return snapshot(ident)
