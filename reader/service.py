"""Portable read-only Bible reading/search API. No research engine dependency."""
from __future__ import annotations
import contextlib,json,pathlib,re,sqlite3
DATABASE=pathlib.Path(__file__).resolve().parents[1]/'data/reader.sqlite'
def connect():
    db=sqlite3.connect(DATABASE.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');return db
def catalog(edition='web'):
    with contextlib.closing(connect()) as db:
        es=[dict(r) for r in db.execute('SELECT id,name,language,source,license,metadata_json FROM Edition ORDER BY CASE id WHEN \'web\' THEN 0 ELSE 1 END,id')]
        if edition not in {e['id'] for e in es}:raise ValueError('UNSUPPORTED_EDITION')
        for e in es:e['metadata']=json.loads(e.pop('metadata_json'))
        books=[dict(r) for r in db.execute('SELECT id,name,chapters_json FROM Book WHERE edition=? ORDER BY sort_order',(edition,))]
        for b in books:b['chapters']=json.loads(b.pop('chapters_json'))
        return {'editions':es,'books':books,'default_edition':'web','selected_edition':edition}
def chapter(edition='web',book='John',chapter=1):
    if isinstance(chapter,bool):raise ValueError('INVALID_CHAPTER')
    chapter=int(chapter);c=catalog(edition);b=next((b for b in c['books'] if b['id']==book),None)
    if not b or not 1<=chapter<=len(b['chapters']):raise ValueError('REFERENCE_NOT_FOUND')
    index=c['books'].index(b)
    previous={'book':book,'chapter':chapter-1} if chapter>1 else ({'book':c['books'][index-1]['id'],'chapter':len(c['books'][index-1]['chapters'])} if index else None)
    next_={'book':book,'chapter':chapter+1} if chapter<len(b['chapters']) else ({'book':c['books'][index+1]['id'],'chapter':1} if index+1<len(c['books']) else None)
    with contextlib.closing(connect()) as db:verses=[{'number':r['verse'],'reference':f"{book}.{chapter}.{r['verse']}",'text':r['text'],'text_sha256':r['text_sha256']} for r in db.execute('SELECT verse,text,text_sha256 FROM Verse WHERE edition=? AND book=? AND chapter=? ORDER BY verse',(edition,book,chapter))]
    return {'status':'VALID_RESULT','edition':next(e for e in c['editions'] if e['id']==edition),'book':b,'chapter':chapter,'verses':verses,'previous':previous,'next':next_}
def search(query,edition='web',book=None,limit=25,offset=0):
    if not isinstance(query,str) or not 1<=len(query.strip())<=200:raise ValueError('INVALID_SEARCH')
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=100 or isinstance(offset,bool) or not isinstance(offset,int) or not 0<=offset<=100000:raise ValueError('INVALID_PAGINATION')
    c=catalog(edition)
    if book and book not in {b['id'] for b in c['books']}:raise ValueError('REFERENCE_NOT_FOUND')
    terms=[a or b for a,b in re.findall(r'"([^\"]+)"|(\S+)',query)];expression=' AND '.join('"'+x.replace('"','""')+'"' for x in terms)
    if not terms:raise ValueError('INVALID_SEARCH')
    where='v.edition=?'+(' AND v.book=?' if book else '');params=[expression,edition]+([book] if book else [])
    with contextlib.closing(connect()) as db:
        total=db.execute('SELECT COUNT(*) FROM VerseSearch f JOIN Verse v ON v.rowid=f.rowid WHERE VerseSearch MATCH ? AND '+where,params).fetchone()[0]
        rows=db.execute('SELECT v.book,v.chapter,v.verse,v.text FROM VerseSearch f JOIN Verse v ON v.rowid=f.rowid JOIN Book b ON b.edition=v.edition AND b.id=v.book WHERE VerseSearch MATCH ? AND '+where+' ORDER BY bm25(VerseSearch),b.sort_order,v.chapter,v.verse LIMIT ? OFFSET ?',params+[limit,offset]).fetchall()
    return {'status':'VALID_RESULT' if rows else 'NO_MATCH','edition':edition,'query':query,'total':total,'limit':limit,'offset':offset,'results':[dict(r,reference=f"{r['book']}.{r['chapter']}.{r['verse']}") for r in rows]}
