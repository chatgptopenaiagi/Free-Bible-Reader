"""Build the redistributable reader package; never opens the original corpus."""
import collections,contextlib,datetime,gzip,hashlib,json,pathlib,re,sqlite3,sys,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
NATIVE_DATABASE=ROOT/'data/xref_phrase.sqlite'
BOOKS='Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov Eccl Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal Matt Mark Luke John Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet 1John 2John 3John Jude Rev'.split()
NAMES='Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|1 Samuel|2 Samuel|1 Kings|2 Kings|1 Chronicles|2 Chronicles|Ezra|Nehemiah|Esther|Job|Psalms|Proverbs|Ecclesiastes|Song of Solomon|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|1 Corinthians|2 Corinthians|Galatians|Ephesians|Philippians|Colossians|1 Thessalonians|2 Thessalonians|1 Timothy|2 Timothy|Titus|Philemon|Hebrews|James|1 Peter|2 Peter|1 John|2 John|3 John|Jude|Revelation'.split('|')
CODES='GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV'.split();CODE_MAP=dict(zip(CODES,BOOKS))
EDITION_METADATA=[{'id':'web','name':'World English Bible (Protestant Edition)','language':'en','source':'https://ebible.org/Scriptures/engwebp_vpl.zip','license':'Public domain; World English Bible name is an eBible.org trademark','rights_url':'https://ebible.org/find/details.php?id=engwebp'}, {'id':'kjv','name':'King James Version — CrossReferences source edition','language':'en','source':'https://github.com/CrossReferences-org/bible-cross-references/tree/a80ab3d8bcc4ed53c86bae2e2a5ef183b9316653','license':'Public domain outside UK; see KJV territorial notice','rights_url':'https://ebible.org/Scriptures/details.php?id=eng-kjv2006'}, {'id':'bsb','name':'Berean Standard Bible — CrossReferences source edition','language':'en','source':'https://github.com/CrossReferences-org/bible-cross-references/tree/a80ab3d8bcc4ed53c86bae2e2a5ef183b9316653','license':'Public domain (CC0 dedication)','rights_url':'https://berean.bible/terms.htm'}]
CODE_MAP.update({'SOL':'Song','EZE':'Ezek','JOH':'John','MAR':'Mark','JAM':'Jas','PHI':'Phil','JOE':'Joel','NAH':'Nah','1JO':'1John','2JO':'2John','3JO':'3John'})
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def initial_source():
    archive=ROOT/'build-support/engwebp_vpl.zip'
    if not archive.exists():
        import urllib.request
        archive.parent.mkdir(parents=True,exist_ok=True)
        urllib.request.urlretrieve('https://ebible.org/Scriptures/engwebp_vpl.zip',archive)
    with zipfile.ZipFile(archive) as z:raw=z.read('engwebp_vpl.txt');about=z.read('engwebp_about.htm')
    rows=[]
    for index,line in enumerate(raw.decode('utf-8-sig').splitlines(),1):
        if not line:continue
        match=re.fullmatch(r'(\S+) (\d+):(\d+) (.*)',line)
        if not match or match[1] not in CODE_MAP:raise RuntimeError(f'Unsupported VPL line {index}: {line[:50]}')
        rows.append({'edition':'web','book':CODE_MAP[match[1]],'chapter':int(match[2]),'verse':int(match[3]),'text':match[4]})
    source=NATIVE_DATABASE;before=sha(source)
    with contextlib.closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as db:
        for code,ref,text in db.execute("SELECT edition_code,reference,native_text FROM PhraseVerse WHERE edition_code IN ('KJV','BSB') ORDER BY edition_code,book_id,chapter,verse"):
            if text is None:raise RuntimeError('Unresolved source text cannot enter public reader')
            book,ch,v=ref.split('.');rows.append({'edition':code.lower(),'book':book,'chapter':int(ch),'verse':int(v),'text':text})
    if sha(source)!=before:raise RuntimeError('Native source database changed')
    (ROOT/'data').mkdir(exist_ok=True)
    with gzip.GzipFile(filename='',mode='wb',fileobj=(ROOT/'data/reader-source.jsonl.gz').open('wb'),mtime=0) as compressed:
        for row in rows:compressed.write((json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8'))
    (ROOT/'evidence/reader-source-manifest.json').write_text(json.dumps({'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'web_archive_sha256':sha(archive),'web_vpl_member_sha256':hashlib.sha256(raw).hexdigest(),'web_about_sha256':hashlib.sha256(about).hexdigest(),'native_phrase_db_sha256':before,'native_source_commit':'a80ab3d8bcc4ed53c86bae2e2a5ef183b9316653','rows':len(rows),'edition_metadata':EDITION_METADATA,'source_policy':'eBible published VPL plain scripture text; KJV/BSB native strings reconstructed by documented source fragment order; no original Cggg corpus data accessed'},indent=2),encoding='utf-8')
def build():
    source=ROOT/'data/reader-source.jsonl.gz'
    if not source.exists():initial_source()
    target=ROOT/'data/reader.sqlite'
    if target.exists():raise RuntimeError('Reader database already exists; use an explicitly new output for rebuild')
    db=sqlite3.connect(target)
    db.executescript('''PRAGMA foreign_keys=ON;
    CREATE TABLE Edition(id TEXT PRIMARY KEY,name TEXT,language TEXT,source TEXT,license TEXT,metadata_json TEXT);
    CREATE TABLE Book(edition TEXT REFERENCES Edition(id),id TEXT,name TEXT,sort_order INTEGER,chapters_json TEXT,PRIMARY KEY(edition,id));
    CREATE TABLE Verse(edition TEXT,book TEXT,chapter INTEGER,verse INTEGER,text TEXT NOT NULL,text_sha256 TEXT NOT NULL,PRIMARY KEY(edition,book,chapter,verse),FOREIGN KEY(edition,book) REFERENCES Book(edition,id));
    CREATE INDEX verse_reference ON Verse(edition,book,chapter,verse);
    CREATE VIRTUAL TABLE VerseSearch USING fts5(text,content='Verse',content_rowid='rowid',tokenize='unicode61 remove_diacritics 0');''')
    with gzip.open(source,'rt',encoding='utf-8') as f:rows=[json.loads(line) for line in f]
    chapters=collections.defaultdict(lambda:collections.defaultdict(int))
    for row in rows:chapters[row['edition'],row['book']][row['chapter']]=max(chapters[row['edition'],row['book']][row['chapter']],row['verse'])
    for e in EDITION_METADATA:db.execute('INSERT INTO Edition VALUES(?,?,?,?,?,?)',(e['id'],e['name'],e['language'],e['source'],e['license'],json.dumps(e)))
    for (edition,book),chs in chapters.items():
        if set(chs)!=set(range(1,max(chs)+1)):raise RuntimeError('Missing source chapter: '+str((edition,book)))
        db.execute('INSERT INTO Book VALUES(?,?,?,?,?)',(edition,book,NAMES[BOOKS.index(book)],BOOKS.index(book)+1,json.dumps([chs[c] for c in range(1,max(chs)+1)])))
    db.executemany('INSERT INTO Verse VALUES(?,?,?,?,?,?)',[(r['edition'],r['book'],r['chapter'],r['verse'],r['text'],hashlib.sha256(r['text'].encode('utf-8')).hexdigest()) for r in rows]);db.execute("INSERT INTO VerseSearch(VerseSearch) VALUES('rebuild')");db.commit()
    errors=[]
    for row in rows:
        found=db.execute('SELECT text,text_sha256 FROM Verse WHERE edition=? AND book=? AND chapter=? AND verse=?',(row['edition'],row['book'],row['chapter'],row['verse'])).fetchone()
        if not found or found[0]!=row['text'] or found[1]!=hashlib.sha256(row['text'].encode('utf-8')).hexdigest():errors.append({k:row[k] for k in ('edition','book','chapter','verse')})
    counts={e['id']:dict(zip(('books','chapters','verses'),[db.execute('SELECT COUNT(*) FROM Book WHERE edition=?',(e['id'],)).fetchone()[0],db.execute('SELECT COUNT(*) FROM (SELECT book,chapter FROM Verse WHERE edition=? GROUP BY book,chapter)',(e['id'],)).fetchone()[0],db.execute('SELECT COUNT(*) FROM Verse WHERE edition=?',(e['id'],)).fetchone()[0]])) for e in EDITION_METADATA}
    integrity=db.execute('PRAGMA integrity_check').fetchone()[0];fk=list(db.execute('PRAGMA foreign_key_check'));db.close()
    receipt={'status':'PASS' if not errors and integrity=='ok' and not fk and all(x['books']==66 for x in counts.values()) else 'FAIL','compared_rows':len(rows),'mismatches':errors,'integrity':integrity,'foreign_key_errors':fk,'counts':counts,'database_bytes':target.stat().st_size,'database_sha256':sha(target),'source_jsonl_gzip_sha256':sha(source)}
    (ROOT/'evidence/reader-data-verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt,indent=2))
    if receipt['status']!='PASS':raise RuntimeError('Reader fidelity checks failed')
if __name__=='__main__':build()
