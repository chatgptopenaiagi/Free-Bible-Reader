"""Reproduce the separately bundled public-domain Romanian NT draft from eBible VPL XML.

No SQL from the archive is executed. Existing database artifacts are not overwritten.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,pathlib,sqlite3,xml.etree.ElementTree as ET,zipfile,datetime

BOOKS=[('MAT','Matt','Matei'),('MRK','Mark','Marcu'),('LUK','Luke','Luca'),('JHN','John','Ioan'),('ACT','Acts','Faptele Apostolilor'),('ROM','Rom','Romani'),('1CO','1Cor','1 Corinteni'),('2CO','2Cor','2 Corinteni'),('GAL','Gal','Galateni'),('EPH','Eph','Efeseni'),('PHP','Phil','Filipeni'),('COL','Col','Coloseni'),('1TH','1Thess','1 Tesaloniceni'),('2TH','2Thess','2 Tesaloniceni'),('1TI','1Tim','1 Timotei'),('2TI','2Tim','2 Timotei'),('TIT','Titus','Tit'),('PHM','Phlm','Filimon'),('HEB','Heb','Evrei'),('JAS','Jas','Iacov'),('1PE','1Pet','1 Petru'),('2PE','2Pet','2 Petru'),('1JN','1John','1 Ioan'),('2JN','2John','2 Ioan'),('3JN','3John','3 Ioan'),('JUD','Jude','Iuda'),('REV','Rev','Apocalipsa')]

def build(archive,outdir):
    archive=pathlib.Path(archive);outdir=pathlib.Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    dest=outdir/'romanian.sqlite';manifest=outdir/'romanian-manifest.json';source=outdir/'romanian-source.jsonl.gz'
    if any(p.exists() for p in (dest,manifest,source)):raise ValueError('ROMANIAN_OUTPUT_ALREADY_EXISTS')
    with zipfile.ZipFile(archive) as z:
        payload=z.read('ronbl_vpl.xml');about=z.read('ronbl_about.htm').decode('utf-8-sig')
    if 'Public Domain' not in about or 'schiță de traducere' not in about:raise ValueError('SOURCE_RIGHTS_OR_DRAFT_METADATA_CHANGED')
    parsed=ET.fromstring(payload)
    bmap={a:(b,n) for a,b,n in BOOKS};rows=[];chaptersets={};seen=set()
    for ordinal,node in enumerate(parsed.findall('v')):
        original=node.attrib;native=original['b'];book,_=bmap[native];chapter=original['c'];verse=original['v'];text=node.text or ''
        key=(book,chapter,verse)
        if key in seen:raise ValueError('DUPLICATE_NATIVE_REFERENCE')
        seen.add(key);chaptersets.setdefault(book,[])
        if chapter not in chaptersets[book]:chaptersets[book].append(chapter)
        rows.append({'edition':'ronbl','book':book,'chapter':int(chapter) if chapter.isdigit() else chapter,'verse':verse,'text':text,'text_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),'sort_order':ordinal,'native_locator':original})
    meta={'source_id':'ronbl','source_url':'https://ebible.org/details.php?id=ronbl','download_url':'https://ebible.org/Scriptures/ronbl_vpl.zip','source_date':'2026-10-28','script':'Latn','coverage':'New Testament only','draft':True,'license':'Public Domain (eBible current edition and archive declaration)','format':'VPL XML: text-only; notes/paragraph formatting absent','text_policy':'Exact XML text nodes preserved, including trailing spaces; canonical book IDs mapped from source SIL/UBS codes; native labels retained','book_name_policy':'Romanian interface display labels, not a translation of source text','source_archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'source_xml_sha256':hashlib.sha256(payload).hexdigest(),'verse_count':len(rows),'book_count':len(chaptersets),'chapter_count':sum(map(len,chaptersets.values()))}
    with sqlite3.connect(dest) as c:
        c.executescript("CREATE TABLE Edition(id TEXT PRIMARY KEY,name TEXT,language TEXT,source TEXT,license TEXT,metadata_json TEXT);CREATE TABLE Book(edition TEXT,id TEXT,name TEXT,sort_order INTEGER,chapters_json TEXT,PRIMARY KEY(edition,id));CREATE TABLE Verse(edition TEXT,book TEXT,chapter INTEGER,verse TEXT,text TEXT,text_sha256 TEXT,sort_order INTEGER,native_locator_json TEXT);CREATE INDEX VerseReference ON Verse(edition,book,chapter,sort_order);CREATE VIRTUAL TABLE VerseSearch USING fts5(text,content='Verse',content_rowid='rowid',tokenize='unicode61 remove_diacritics 0');")
        c.execute('INSERT INTO Edition VALUES(?,?,?,?,?,?)',('ronbl','Biblia Liberă — Noul Testament (schiță)','ro','https://ebible.org/details.php?id=ronbl','Public Domain',json.dumps(meta,ensure_ascii=False)))
        for order,(_,book,name) in enumerate(BOOKS):
            if book in chaptersets:c.execute('INSERT INTO Book VALUES(?,?,?,?,?)',('ronbl',book,name,order,json.dumps([int(x) if x.isdigit() else x for x in chaptersets[book]])))
        c.executemany('INSERT INTO Verse VALUES(?,?,?,?,?,?,?,?)',[(r['edition'],r['book'],r['chapter'],r['verse'],r['text'],r['text_sha256'],r['sort_order'],json.dumps(r['native_locator'])) for r in rows]);c.execute("INSERT INTO VerseSearch(VerseSearch) VALUES('rebuild')")
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('ROMANIAN_DATABASE_INTEGRITY_FAILED')
        assert c.execute('SELECT COUNT(*) FROM Verse').fetchone()[0]==len(rows)
        for r,actual in zip(rows,c.execute('SELECT text FROM Verse ORDER BY sort_order')):assert r['text']==actual[0]
    with source.open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as f:
            for r in rows:f.write((json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8'))
    meta.update({'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'database_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'database_bytes':dest.stat().st_size,'source_jsonl_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'all_text_nodes_exact_roundtrip':True})
    manifest.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    return meta

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('--outdir',default=str(pathlib.Path(__file__).resolve().parents[1]/'data'));a=p.parse_args();print(json.dumps(build(a.archive,a.outdir),ensure_ascii=False,indent=2))
