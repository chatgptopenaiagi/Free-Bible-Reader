"""Create PRIVATE offline import packs; never part of release preparation.

Run --list first, then explicitly select actual source version IDs. Sources are
read-only. The resulting SQLite is inspected/imported through Ultimate's native
document picker. An optional complete-source ZIP is an offline transfer medium,
not a claim that every source module is a distinct published Bible edition.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        while part:=stream.read(1024*1024):result.update(part)
    return result.hexdigest()

def connect(source):
    connection=sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)
    connection.execute('PRAGMA query_only=ON');connection.row_factory=sqlite3.Row
    tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'version','verse'}<=tables:raise ValueError('This private helper supports the discovered BIBLIA version/verse schema only; use the guided importer for other schemas')
    return connection

def run(args):
    source=Path(args.source).resolve(strict=True)
    if not source.is_file():raise ValueError('Select the SQLite source file')
    with connect(source) as db:
        query='SELECT id,language,language_english,vernacular_title,english_title FROM version'
        params=[]
        if args.query:
            query+=' WHERE lower(language_english) LIKE ? OR lower(english_title) LIKE ? OR lower(vernacular_title) LIKE ? OR lower(id) LIKE ?'
            params=['%'+args.query.casefold()+'%']*4
        rows=[dict(r) for r in db.execute(query+' ORDER BY id',params)]
        if args.list:
            print(json.dumps({'version_records_matching':len(rows),'not_a_count_of_distinct_translations':True,'editions':rows},ensure_ascii=False,indent=2));return
        if not args.edition and not args.full_source_archive:raise ValueError('Select --edition ID (repeatable), or explicitly request --full-source-archive')
        output=Path(args.output or ROOT/'build-support/private-corpus'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())).resolve()
        # A private build must stay in the ignored build-support/private-corpus tree.
        allowed=(ROOT/'build-support/private-corpus').resolve()
        if not output.is_relative_to(allowed):raise ValueError('Private output must remain under ignored build-support/private-corpus')
        output.mkdir(parents=True,exist_ok=False)
        before={'bytes':source.stat().st_size,'mtime_ns':source.stat().st_mtime_ns,'sha256':digest(source)}
        manifest={'private':True,'publication_authorized':False,'source':str(source),'source_before':before,'source_version_records':db.execute('SELECT count(*) FROM version').fetchone()[0],'editions':[],'files':[]}
        if args.edition:
            target=output/'personal-selected-editions.sqlite'
            with sqlite3.connect(target) as dest:
                dest.executescript('CREATE TABLE Edition(id TEXT PRIMARY KEY,name TEXT,language TEXT,source TEXT,license TEXT,metadata_json TEXT);CREATE TABLE Book(edition TEXT,id TEXT,name TEXT,sort_order INTEGER,chapters_json TEXT,PRIMARY KEY(edition,id));CREATE TABLE Verse(edition TEXT,book TEXT,chapter TEXT,verse TEXT,text TEXT,text_sha256 TEXT,sort_order INTEGER,source_record_id TEXT);')
                for edition in dict.fromkeys(args.edition):
                    metadata=db.execute('SELECT * FROM version WHERE id=?',(edition,)).fetchone()
                    if metadata is None:raise ValueError('Unknown actual source edition ID: '+edition)
                    meta=dict(metadata);identity='source:'+str(meta['id'])
                    dest.execute('INSERT INTO Edition VALUES(?,?,?,?,?,?)',(identity,meta.get('vernacular_title') or meta.get('english_title') or str(meta['id']),meta.get('language') or 'und','Private source version '+str(meta['id']),'Personal import; redistribution status not asserted',json.dumps({'source_version':meta,'private':True,'canon':'Source book collection; completeness not inferred'},ensure_ascii=False)))
                    books={};total=0;logical=hashlib.sha256()
                    cursor=db.execute('SELECT id,book,chapter,start_verse,end_verse,text FROM verse WHERE version_id=? ORDER BY id',(edition,))
                    while batch:=cursor.fetchmany(1000):
                        values=[]
                        for row in batch:
                            book,chapter=str(row['book']),str(row['chapter']);start,end=str(row['start_verse']),str(row['end_verse']) if row['end_verse'] is not None else str(row['start_verse'])
                            verse=start if start==end else start+'-'+end
                            if not isinstance(row['text'],str):raise ValueError('Non-text source row '+str(row['id']))
                            total+=1;books.setdefault(book,{}).setdefault(chapter,0);books[book][chapter]+=1
                            values.append((identity,book,chapter,verse,row['text'],hashlib.sha256(row['text'].encode()).hexdigest(),total,str(row['id'])))
                            logical.update(json.dumps([str(row['id']),book,chapter,verse,row['text']],ensure_ascii=False,separators=(',',':')).encode())
                        dest.executemany('INSERT INTO Verse VALUES(?,?,?,?,?,?,?,?)',values);dest.commit()
                    for order,(book,chapters) in enumerate(books.items(),1):dest.execute('INSERT INTO Book VALUES(?,?,?,?,?)',(identity,book,book,order,json.dumps(list(chapters.values()))))
                    manifest['editions'].append({'source_version_id':edition,'package_edition_id':identity,'records':total,'books':len(books),'chapters':sum(len(c) for c in books.values()),'source_order_text_digest':logical.hexdigest(),'native_book_chapter_verse_labels_preserved':True,'published_edition_completeness':'Not inferred'})
                dest.executescript('CREATE INDEX VerseReference ON Verse(edition,book,chapter,sort_order);CREATE INDEX VerseSource ON Verse(edition,source_record_id);')
                if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Export integrity check failed')
            manifest['files'].append({'path':target.name,'bytes':target.stat().st_size,'sha256':digest(target)})
        if args.full_source_archive:
            target=output/'PRIVATE-complete-biblia-source.zip'
            started=time.monotonic()
            with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
                archive.write(source,'personal-corpus.sqlite')
            with zipfile.ZipFile(target) as archive:
                if archive.testzip() is not None:raise ValueError('Complete source archive CRC failed')
                stream_digest=hashlib.sha256()
                with archive.open('personal-corpus.sqlite') as stream:
                    while part:=stream.read(1024*1024):stream_digest.update(part)
            if stream_digest.hexdigest()!=before['sha256']:raise ValueError('Archived source round-trip mismatch')
            manifest['files'].append({'path':target.name,'bytes':target.stat().st_size,'sha256':digest(target),'uncompressed_bytes':source.stat().st_size,'exact_source_round_trip':True,'elapsed_seconds':round(time.monotonic()-started,2)})
        after={'bytes':source.stat().st_size,'mtime_ns':source.stat().st_mtime_ns,'sha256':digest(source)}
        manifest['source_after']=after;manifest['source_preserved']=before==after
        if before!=after:raise ValueError('Source changed during private packaging; discard this snapshot, not the source')
        (output/'PRIVATE-MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'private':True,'output':str(output),'source_preserved':True,'editions':manifest['editions'],'files':manifest['files']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--list',action='store_true');p.add_argument('--query');p.add_argument('--edition',action='append');p.add_argument('--full-source-archive',action='store_true');p.add_argument('--output');run(p.parse_args())
