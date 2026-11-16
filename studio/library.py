"""User-owned Bible editions. Bundled databases and import sources are read-only.

This module deliberately does not import reader.service (the reader wraps it).
Import policy lives in studio.importers; creating a job is an explicit confirmation.
"""
from __future__ import annotations
import contextlib, hashlib, json, os, pathlib, re, sqlite3, threading, time, uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
_WRITE_LOCK = threading.RLock()

def data_root():
    try:
        from .paths import data_root as path_root
        return pathlib.Path(path_root())
    except ImportError:
        p = pathlib.Path(os.environ.get('FBR_STUDIO_DIR') or pathlib.Path(os.environ.get('LOCALAPPDATA', pathlib.Path.home()))/'FreeBibleReader'/'studio')
        p.mkdir(parents=True, exist_ok=True)
        return p

def library_path(): return data_root()/'library.sqlite'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS Edition(id TEXT PRIMARY KEY,name TEXT NOT NULL,language TEXT NOT NULL,source TEXT NOT NULL,license TEXT NOT NULL,metadata_json TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ready');
CREATE TABLE IF NOT EXISTS Book(edition TEXT NOT NULL,id TEXT NOT NULL,name TEXT NOT NULL,sort_order INTEGER NOT NULL,chapters_json TEXT NOT NULL,PRIMARY KEY(edition,id),FOREIGN KEY(edition) REFERENCES Edition(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS Verse(id INTEGER PRIMARY KEY,edition TEXT NOT NULL,book TEXT NOT NULL,chapter TEXT NOT NULL,verse TEXT NOT NULL,text TEXT NOT NULL,text_sha256 TEXT NOT NULL,source_record_id TEXT,sort_order INTEGER NOT NULL,raw_json TEXT NOT NULL,FOREIGN KEY(edition) REFERENCES Edition(id) ON DELETE CASCADE,UNIQUE(edition,sort_order));
CREATE INDEX IF NOT EXISTS VerseReference ON Verse(edition,book,chapter,sort_order);
CREATE TABLE IF NOT EXISTS ImportJob(id TEXT PRIMARY KEY,inspection_id TEXT NOT NULL,edition_id TEXT NOT NULL,mapping_json TEXT NOT NULL,metadata_json TEXT NOT NULL,status TEXT NOT NULL,cursor INTEGER NOT NULL DEFAULT 0,inserted INTEGER NOT NULL DEFAULT 0,error TEXT,created_utc TEXT NOT NULL,updated_utc TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS PersonalSearch USING fts5(text,content='Verse',content_rowid='id',tokenize='unicode61 remove_diacritics 0');
CREATE TRIGGER IF NOT EXISTS VerseInsert AFTER INSERT ON Verse BEGIN INSERT INTO PersonalSearch(rowid,text) VALUES(new.id,new.text); END;
CREATE TRIGGER IF NOT EXISTS VerseDelete AFTER DELETE ON Verse BEGIN INSERT INTO PersonalSearch(PersonalSearch,rowid,text) VALUES('delete',old.id,old.text); END;
'''

def connect(write=False):
    p=library_path()
    if write:
        p.parent.mkdir(parents=True,exist_ok=True)
        c=sqlite3.connect(p,timeout=30); c.execute('PRAGMA foreign_keys=ON');c.executescript(SCHEMA)
    else:
        if not p.exists(): return None
        c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=5);c.execute('PRAGMA query_only=ON')
    c.row_factory=sqlite3.Row
    return c

def sources(include_private=True):
    out=[]
    for p in (ROOT/'data/reader.sqlite',ROOT/'data/romanian.sqlite'):
        if p.exists():out.append((p,'bundled'))
    p=library_path()
    if include_private and p.exists():out.append((p,'personal'))
    return out

def open_readonly(path):
    c=sqlite3.connect(pathlib.Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=5);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');return c

def list_editions(include_importing=False):
    out=[]
    for p,origin in sources():
        with contextlib.closing(open_readonly(p)) as c:
            cols={r['name'] for r in c.execute('PRAGMA table_info(Edition)')}
            where=" WHERE status='ready'" if 'status' in cols and not include_importing else ''
            for row in c.execute('SELECT * FROM Edition'+where):
                e=dict(row);e['metadata']=json.loads(e.pop('metadata_json','{}'));e['origin']=origin;out.append(e)
    # Never allow a private edition to impersonate a bundled edition.
    seen=set();result=[]
    for e in out:
        if e['id'] not in seen:seen.add(e['id']);result.append(e)
    return result

def locate(edition):
    if not isinstance(edition,str) or not edition:raise ValueError('UNSUPPORTED_EDITION')
    for p,origin in sources():
        with contextlib.closing(open_readonly(p)) as c:
            cols={r['name'] for r in c.execute('PRAGMA table_info(Edition)')}
            row=c.execute('SELECT * FROM Edition WHERE id=?'+(" AND status='ready'" if 'status' in cols else ''),(edition,)).fetchone()
            if row:return p,origin
    raise ValueError('UNSUPPORTED_EDITION')

def catalog(edition=None):
    editions=list_editions();edition=edition or ('web' if any(e['id']=='web' for e in editions) else editions[0]['id'] if editions else None)
    if edition is None:return {'editions':[],'books':[],'default_edition':None,'selected_edition':None}
    p,_=locate(edition)
    with contextlib.closing(open_readonly(p)) as c:
        books=[]
        has_order=any(r['name']=='sort_order' for r in c.execute('PRAGMA table_info(Verse)'))
        for r in c.execute('SELECT id,name,chapters_json FROM Book WHERE edition=? ORDER BY sort_order',(edition,)):
            b=dict(r);b['chapters']=json.loads(b.pop('chapters_json'))
            order='MIN(sort_order)' if has_order else 'chapter'
            # The original reader's chapters_json contains verse COUNTS, not
            # chapter labels. Discover labels independently from actual rows.
            labels=[str(x[0]) for x in c.execute('SELECT chapter FROM Verse WHERE edition=? AND book=? GROUP BY chapter ORDER BY '+order,(edition,b['id']))]
            b['chapter_labels']=[int(x) if x.isdigit() else x for x in labels]
            books.append(b)
    return {'editions':editions,'books':books,'default_edition':'web' if any(e['id']=='web' for e in editions) else edition,'selected_edition':edition}

def chapter(edition='web',book='John',chapter=1):
    if isinstance(chapter,bool):raise ValueError('INVALID_CHAPTER')
    cata=catalog(edition);b=next((b for b in cata['books'] if b['id']==str(book)),None)
    labels=[str(n) for n in b['chapter_labels']] if b else []
    label=str(chapter)
    if not b or label not in labels:raise ValueError('REFERENCE_NOT_FOUND')
    bi=cata['books'].index(b);ci=labels.index(label)
    def pos(bb,cc):return {'book':bb['id'],'chapter':cc}
    previous=pos(b,b['chapter_labels'][ci-1]) if ci else pos(cata['books'][bi-1],cata['books'][bi-1]['chapter_labels'][-1]) if bi else None
    next_=pos(b,b['chapter_labels'][ci+1]) if ci+1<len(labels) else pos(cata['books'][bi+1],cata['books'][bi+1]['chapter_labels'][0]) if bi+1<len(cata['books']) else None
    p,origin=locate(edition)
    with contextlib.closing(open_readonly(p)) as c:
        order='sort_order' if any(r['name']=='sort_order' for r in c.execute('PRAGMA table_info(Verse)')) else 'verse'
        rows=c.execute(f'SELECT verse,text,text_sha256 FROM Verse WHERE edition=? AND book=? AND chapter=? ORDER BY {order}',(edition,str(book),chapter)).fetchall()
    verses=[]
    for r in rows:
        native=str(r['verse']);parts=re.fullmatch(r'(\d+)(?:-(\d+))?',native)
        verses.append({'number':int(native) if native.isdigit() else native,'label':native,'nativeVerseStart':int(parts[1]) if parts else None,'nativeVerseEnd':int(parts[2] or parts[1]) if parts else None,'reference':f'{book}.{label}.{native}','text':r['text'],'text_sha256':r['text_sha256']})
    return {'status':'VALID_RESULT','edition':next(e for e in cata['editions'] if e['id']==edition),'book':b,'chapter':int(label) if label.isdigit() else label,'verses':verses,'previous':previous,'next':next_,'native_labels_preserved':True}

def _now():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())

def create_import(inspection_id,mapping,metadata,confirmed=False):
    if confirmed is not True:raise ValueError('IMPORT_CONFIRMATION_REQUIRED')
    from . import importers
    info=importers.load_inspection(inspection_id); importers.validate_mapping(info,mapping)
    if not isinstance(metadata,dict) or not isinstance(metadata.get('name'),str) or not metadata['name'].strip():raise ValueError('EDITION_NAME_REQUIRED')
    for key,maximum in (('name',300),('language',64),('source',2000),('license',2000),('source_edition_id',256)):
        value=metadata.get(key)
        if value is not None and (not isinstance(value,str) or len(value)>maximum or '\x00' in value):raise ValueError('INVALID_EDITION_METADATA_'+key.upper())
    preview=importers.preview_import(inspection_id,mapping,metadata)
    if not preview['valid']:raise ValueError('INVALID_IMPORT_PREVIEW')
    jobid=str(uuid.uuid4());edition='personal:'+str(uuid.uuid4());now=_now()
    # A generated local ID is disclosed as local identity, never a fabricated publisher ID.
    meta=dict(metadata);meta.update({'local_edition_id':edition,'source_edition_id':metadata.get('source_edition_id'), 'source_sha256':info['sha256'],'identity_policy':'local UUID; publisher/source identifier retained separately when supplied','source_record_id_policy':'Original selected source column (including null) retained' if mapping.get('source_record_id') else 'Zero-based selected source row ordinal; not a publisher identifier','private':True,'import_format':info['format']})
    with _WRITE_LOCK,contextlib.closing(connect(True)) as c,c:
        c.execute('INSERT INTO Edition VALUES(?,?,?,?,?,?,?)',(edition,str(meta['name'])[:300],str(meta.get('language','und'))[:64],str(meta.get('source','User-selected local source'))[:2000],str(meta.get('license','Private import; redistribution rights not established'))[:2000],json.dumps(meta,ensure_ascii=False),'importing'))
        c.execute('INSERT INTO ImportJob(id,inspection_id,edition_id,mapping_json,metadata_json,status,created_utc,updated_utc) VALUES(?,?,?,?,?,?,?,?)',(jobid,inspection_id,edition,json.dumps(mapping),json.dumps(meta,ensure_ascii=False),'PENDING',now,now))
    return import_status(jobid)

def import_status(job_id):
    c=connect()
    if c is None:raise ValueError('JOB_NOT_FOUND')
    with contextlib.closing(c):r=c.execute('SELECT * FROM ImportJob WHERE id=?',(job_id,)).fetchone()
    if not r:raise ValueError('JOB_NOT_FOUND')
    d=dict(r);d['mapping']=json.loads(d.pop('mapping_json'));d['metadata']=json.loads(d.pop('metadata_json'));return d

def cancel_import(job_id):
    with _WRITE_LOCK,contextlib.closing(connect(True)) as c,c:
        if not c.execute("UPDATE ImportJob SET status='CANCELLED',updated_utc=? WHERE id=? AND status NOT IN ('COMPLETE','FAILED')",(_now(),job_id)).rowcount:raise ValueError('JOB_NOT_CANCELLABLE')
    return import_status(job_id)

def resume_import(job_id):
    with _WRITE_LOCK,contextlib.closing(connect(True)) as c,c:
        if not c.execute("UPDATE ImportJob SET status='PENDING',error=NULL,updated_utc=? WHERE id=? AND status IN ('CANCELLED','FAILED')",(_now(),job_id)).rowcount:raise ValueError('JOB_NOT_RESUMABLE')
    return import_status(job_id)

def run_import(job_id,batch_size=500,cancel_event=None):
    """Commit one bounded batch plus its cursor atomically; caller repeats until COMPLETE.

    Cancellation leaves the non-public importing edition intact for explicit resume.
    No incomplete edition enters catalog/search. A process crash releases SQLite's lock.
    """
    from . import importers
    if isinstance(batch_size,bool) or not isinstance(batch_size,int) or not 1<=batch_size<=2000:raise ValueError('INVALID_BATCH_SIZE')
    with _WRITE_LOCK:
        job=import_status(job_id)
        if job['status'] in ('COMPLETE','CANCELLED'):return job
        info=importers.load_inspection(job['inspection_id']);importers.verify_staged(info)
        if cancel_event is not None and cancel_event.is_set():return cancel_import(job_id)
        try:
            iterator=importers.mapped_rows(info,job['mapping'],start=job['cursor'])
            batch=[]
            for i,r in enumerate(iterator):
                batch.append(r)
                if len(batch)>=batch_size:break
            # EOF is detected on the following bounded call when length equals batch_size.
            done=len(batch)<batch_size
            if done:importers.verify_staged(info,full=True)
            with contextlib.closing(connect(True)) as c,c:
                c.execute('BEGIN IMMEDIATE')
                live=c.execute('SELECT status,cursor FROM ImportJob WHERE id=?',(job_id,)).fetchone()
                if live['status']=='CANCELLED':return import_status(job_id)
                if live['cursor']!=job['cursor']:return import_status(job_id)
                for n,r in enumerate(batch,job['cursor']):
                    c.execute('INSERT INTO Verse(edition,book,chapter,verse,text,text_sha256,source_record_id,sort_order,raw_json) VALUES(?,?,?,?,?,?,?,?,?)',(job['edition_id'],r['book'],r['chapter'],r['verse'],r['text'],hashlib.sha256(r['text'].encode('utf-8')).hexdigest(),r['source_record_id'],n,json.dumps(r['raw'],ensure_ascii=False)))
                c.execute('UPDATE ImportJob SET cursor=?,inserted=inserted+?,status=?,updated_utc=?,error=NULL WHERE id=?',(job['cursor']+len(batch),len(batch),'COMPLETE' if done else 'RUNNING',_now(),job_id))
                if done:
                    books=c.execute('SELECT book,MIN(sort_order) AS ord FROM Verse WHERE edition=? GROUP BY book ORDER BY ord',(job['edition_id'],)).fetchall()
                    for n,b in enumerate(books):
                        ch=[r[0] for r in c.execute('SELECT chapter FROM Verse WHERE edition=? AND book=? GROUP BY chapter ORDER BY MIN(sort_order)',(job['edition_id'],b['book']))]
                        ch=[int(x) if x.isdigit() else x for x in ch]
                        c.execute('INSERT INTO Book VALUES(?,?,?,?,?)',(job['edition_id'],b['book'],job['mapping'].get('book_names',{}).get(b['book'],b['book']),n,json.dumps(ch)))
                    c.execute("UPDATE Edition SET status='ready' WHERE id=?",(job['edition_id'],))
        except Exception as exc:
            with contextlib.closing(connect(True)) as c,c:c.execute("UPDATE ImportJob SET status='FAILED',error=?,updated_utc=? WHERE id=? AND cursor=? AND status NOT IN ('COMPLETE','CANCELLED')",(str(exc)[:1000],_now(),job_id,job['cursor']))
            raise
    return import_status(job_id)

def jobs():
    c=connect()
    if c is None:return []
    with contextlib.closing(c):return [dict(r) for r in c.execute('SELECT id,edition_id,status,cursor,inserted,error,created_utc,updated_utc FROM ImportJob ORDER BY created_utc DESC LIMIT 100')]

def rebuild_search_index():
    with _WRITE_LOCK,contextlib.closing(connect(True)) as c,c:
        c.execute("INSERT INTO PersonalSearch(PersonalSearch) VALUES('rebuild')")
        c.execute("INSERT INTO PersonalSearch(PersonalSearch) VALUES('integrity-check')")
        count=c.execute('SELECT COUNT(*) FROM Verse').fetchone()[0]
    return {'status':'COMPLETE','indexed_rows':count,'scope':'personal library only; bundled databases unchanged'}

def edition_stats(edition):
    p,origin=locate(edition)
    with contextlib.closing(open_readonly(p)) as c:
        books=c.execute('SELECT COUNT(*) FROM Book WHERE edition=?',(edition,)).fetchone()[0]
        chapters=c.execute('SELECT COUNT(*) FROM (SELECT book,chapter FROM Verse WHERE edition=? GROUP BY book,chapter)',(edition,)).fetchone()[0]
        verses,payload=c.execute('SELECT COUNT(*),COALESCE(SUM(LENGTH(CAST(text AS BLOB))),0) FROM Verse WHERE edition=?',(edition,)).fetchone()
    return {'edition':edition,'origin':origin,'books':books,'chapters':chapters,'verses':verses,'text_utf8_bytes':payload,'source_database_read_only':True,'size_policy':'Text payload bytes, not the physical share of a multi-edition database'}

def _export_id(id):
    try:return str(uuid.UUID(str(id)))
    except (ValueError,TypeError,AttributeError):raise ValueError('INVALID_EXPORT_ID') from None

def export_info(id):
    id=_export_id(id);p=data_root()/'packages'/(id+'.json')
    if not p.is_file():raise ValueError('EXPORT_NOT_FOUND')
    value=json.loads(p.read_text(encoding='utf-8'));value['path']=str(data_root()/'packages'/(id+'.sqlite'));return value

def export_path(id):
    p=pathlib.Path(export_info(id)['path'])
    if not p.is_file():raise ValueError('EXPORT_FILE_MISSING')
    return p

def export_edition(edition,confirmed=False):
    """Create one explicit selected-edition package, never a whole private corpus copy."""
    if confirmed is not True:raise ValueError('EXPORT_CONFIRMATION_REQUIRED')
    source,origin=locate(edition);ident=str(uuid.uuid4());folder=data_root()/'packages';folder.mkdir(parents=True,exist_ok=True);dest=folder/(ident+'.sqlite')
    try:
        with contextlib.closing(open_readonly(source)) as src,contextlib.closing(sqlite3.connect(dest)) as dst,dst:
            src.execute('BEGIN')
            e=dict(src.execute('SELECT * FROM Edition WHERE id=?',(edition,)).fetchone());meta=json.loads(e['metadata_json']);meta['export']={'selected_edition_only':True,'source_origin':origin,'created_utc':_now(),'text_policy':'Original Unicode and source-record/native labels preserved; no redistribution permission inferred'}
            dst.executescript(SCHEMA)
            dst.execute('INSERT INTO Edition VALUES(?,?,?,?,?,?,?)',(e['id'],e['name'],e['language'],e['source'],e['license'],json.dumps(meta,ensure_ascii=False),'ready'))
            for b in src.execute('SELECT * FROM Book WHERE edition=? ORDER BY sort_order',(edition,)):dst.execute('INSERT INTO Book VALUES(?,?,?,?,?)',tuple(b[k] for k in ('edition','id','name','sort_order','chapters_json')))
            columns={r['name'] for r in src.execute('PRAGMA table_info(Verse)')};order='sort_order' if 'sort_order' in columns else 'rowid';count=0
            for n,r in enumerate(src.execute('SELECT rowid AS _rowid_,* FROM Verse WHERE edition=? ORDER BY '+order,(edition,))):
                r=dict(r);record_id=r.get('source_record_id',str(r['_rowid_']));raw=r.get('raw_json') or json.dumps({k:v for k,v in r.items() if k!='_rowid_'},ensure_ascii=False)
                dst.execute('INSERT INTO Verse(edition,book,chapter,verse,text,text_sha256,source_record_id,sort_order,raw_json) VALUES(?,?,?,?,?,?,?,?,?)',(edition,str(r['book']),str(r['chapter']),str(r['verse']),r['text'],r['text_sha256'],record_id,n,raw));count+=1
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('EXPORT_INTEGRITY_FAILED')
        digest=hashlib.sha256()
        with dest.open('rb') as f:
            for b in iter(lambda:f.read(1024*1024),b''):digest.update(b)
        out={'id':ident,'filename':'Free-Bible-Reader-selected-edition-'+ident[:8]+'.sqlite','mime':'application/vnd.sqlite3','sha256':digest.hexdigest(),'bytes':dest.stat().st_size,'edition':edition,'records':count,'selected_edition_only':True,'source_mutated':False,'created_utc':_now()}
        (folder/(ident+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');return {**out,'path':str(dest)}
    except Exception:
        if dest.exists():dest.unlink()
        raise

def remove_edition(edition,confirmed=False):
    if confirmed is not True or not str(edition).startswith('personal:'):raise ValueError('PERSONAL_EDITION_CONFIRMATION_REQUIRED')
    with _WRITE_LOCK,contextlib.closing(connect(True)) as c,c:
        c.execute('DELETE FROM ImportJob WHERE edition_id=?',(edition,));n=c.execute('DELETE FROM Edition WHERE id=?',(edition,)).rowcount
    return {'removed':bool(n),'edition':edition}

# Public workflow convenience entry points, kept out of reader.service's import graph.
def inspect_source(*args,**kwargs):
    from .importers import inspect_source as f
    return f(*args,**kwargs)
def preview_import(*args,**kwargs):
    from .importers import preview_import as f
    return f(*args,**kwargs)
def list_source_editions(*args,**kwargs):
    from .importers import list_source_editions as f
    return f(*args,**kwargs)
