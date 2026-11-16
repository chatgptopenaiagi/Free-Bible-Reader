"""Explicit phrase/word/prefix/Boolean search over installed reading editions.

Original text is never normalized in storage. NFC/casefold and optional accent
folding are query-time comparison policies, not linguistic/morphology claims.
"""
from __future__ import annotations
import contextlib,re,time,unicodedata
from . import library

def fold(text,diacritics='exact'):
    s=unicodedata.normalize('NFC',text).casefold()
    if diacritics=='folded':s=''.join(c for c in unicodedata.normalize('NFD',s) if unicodedata.category(c)!='Mn')
    return s

def _word_pattern(term,prefix=False):
    return re.compile(r'(?<!\w)'+re.escape(term)+(r'\w*' if prefix else '')+r'(?!\w)',re.UNICODE)

def _boolean(query,diacritics):
    tokens=re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|\bAND\b|\bOR\b|\bNOT\b|[^\s()]+',query)
    if not tokens or len(tokens)>64:raise ValueError('INVALID_BOOLEAN_QUERY')
    pos=0;depth=0;terms=0
    def atom():
        nonlocal pos,depth,terms
        if pos>=len(tokens):raise ValueError('INVALID_BOOLEAN_QUERY')
        t=tokens[pos];pos+=1
        if t=='NOT':return ('not',atom())
        if t=='(':
            depth+=1
            if depth>8:raise ValueError('BOOLEAN_NESTING_LIMIT')
            node=or_()
            if pos>=len(tokens) or tokens[pos]!=')':raise ValueError('INVALID_BOOLEAN_QUERY')
            pos+=1;depth-=1;return node
        if t in ('AND','OR',')'):raise ValueError('INVALID_BOOLEAN_QUERY')
        terms+=1
        if terms>32:raise ValueError('SEARCH_TERM_LIMIT')
        if t.startswith('"'):
            if not t.endswith('"'):raise ValueError('INVALID_BOOLEAN_QUERY')
            return ('phrase',fold(t[1:-1],diacritics))
        prefix=t.endswith('*');term=t[:-1] if prefix else t
        if not term or '*' in term or '"' in term:raise ValueError('INVALID_BOOLEAN_QUERY')
        return ('term',_word_pattern(fold(term,diacritics),prefix))
    def and_():
        nonlocal pos
        node=atom()
        while pos<len(tokens) and tokens[pos] not in (')','OR'):
            if tokens[pos]=='AND':pos+=1
            node=('and',node,atom())
        return node
    def or_():
        nonlocal pos
        node=and_()
        while pos<len(tokens) and tokens[pos]=='OR':pos+=1;node=('or',node,and_())
        return node
    tree=or_()
    if pos!=len(tokens):raise ValueError('INVALID_BOOLEAN_QUERY')
    def evaluate(node,s):
        tag=node[0]
        if tag=='term':return bool(node[1].search(s))
        if tag=='phrase':return node[1] in s
        if tag=='not':return not evaluate(node[1],s)
        if tag=='and':return evaluate(node[1],s) and evaluate(node[2],s)
        return evaluate(node[1],s) or evaluate(node[2],s)
    return lambda s:evaluate(tree,s)

def matcher(query,mode='words',diacritics='exact'):
    if mode not in ('phrase','words','prefix','boolean'):raise ValueError('INVALID_SEARCH_MODE')
    if diacritics not in ('exact','folded'):raise ValueError('INVALID_DIACRITICS_POLICY')
    if not isinstance(query,str) or not 1<=len(query.strip())<=200:raise ValueError('INVALID_SEARCH')
    query=query.strip()
    if mode=='boolean':return _boolean(query,diacritics)
    if mode=='phrase':
        phrase=fold(query.strip('"'),diacritics)
        if not phrase:raise ValueError('INVALID_SEARCH')
        return lambda s:phrase in s
    terms=re.findall(r'\w+',fold(query,diacritics),re.UNICODE)
    if not terms or len(terms)>32:raise ValueError('INVALID_SEARCH')
    patterns=[_word_pattern(t,mode=='prefix') for t in terms]
    return lambda s:all(p.search(s) for p in patterns)

def search(query,edition='web',books=None,testament='all',mode='words',diacritics='exact',limit=25,offset=0,cancel_event=None,timeout=10,max_scan_rows=500000,book=None):
    if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=100 or isinstance(offset,bool) or not isinstance(offset,int) or not 0<=offset<=100000:raise ValueError('INVALID_PAGINATION')
    if testament not in ('all','OT','NT','ot','nt'):raise ValueError('INVALID_TESTAMENT')
    if not isinstance(timeout,(int,float)) or isinstance(timeout,bool) or not 0<timeout<=30:raise ValueError('INVALID_SEARCH_TIMEOUT')
    if not isinstance(max_scan_rows,int) or isinstance(max_scan_rows,bool) or not 1<=max_scan_rows<=1000000:raise ValueError('INVALID_SCAN_LIMIT')
    matches=matcher(query,mode,diacritics);editions=library.list_editions()
    wanted=[e['id'] for e in editions] if edition in ('all','*') else edition if isinstance(edition,list) else [edition]
    if not wanted or len(wanted)>100 or any(not isinstance(e,str) or e not in {e['id'] for e in editions} for e in wanted):raise ValueError('UNSUPPORTED_EDITION')
    if book and books is None:books=[book]
    if isinstance(books,str):books=[books]
    if books is not None and (not isinstance(books,list) or len(books)>200 or any(not isinstance(b,str) or len(b)>120 for b in books)):raise ValueError('INVALID_BOOK_SCOPE')
    start=time.monotonic();rows=[];total=0;scanned=0;cancelled=False;truncated=False
    # Native order is stable across pages; scores are not falsely compared across
    # different tokenizers, editions or scripts.
    for ed in wanted:
        cat=library.catalog(ed);book_order={b['id']:i for i,b in enumerate(cat['books'])}
        selected=set(book_order) if books is None else set(books)&set(book_order)
        # Canon labels come from the existing pinned standard book registry. For
        # nonstandard private books testament is unknown, never guessed by index.
        nt={'Matt','Mark','Luke','John','Acts','Rom','1Cor','2Cor','Gal','Eph','Phil','Col','1Thess','2Thess','1Tim','2Tim','Titus','Phlm','Heb','Jas','1Pet','2Pet','1John','2John','3John','Jude','Rev'}
        ot={'Gen','Exod','Lev','Num','Deut','Josh','Judg','Ruth','1Sam','2Sam','1Kgs','2Kgs','1Chr','2Chr','Ezra','Neh','Esth','Job','Ps','Prov','Eccl','Song','Isa','Jer','Lam','Ezek','Dan','Hos','Joel','Amos','Obad','Jonah','Mic','Nah','Hab','Zeph','Hag','Zech','Mal'}
        if testament.upper()=='NT':selected&=nt
        elif testament.upper()=='OT':selected&=ot
        if not selected:continue
        p,origin=library.locate(ed)
        with contextlib.closing(library.open_readonly(p)) as db:
            placeholders=','.join('?' for _ in selected)
            order='v.sort_order' if origin=='personal' else 'b.sort_order,v.chapter,v.verse'
            source_id='v.source_record_id' if origin=='personal' else 'v.rowid'
            cursor=db.execute(f'SELECT v.book,v.chapter,v.verse,v.text,v.text_sha256,v.rowid AS local_row_id,{source_id} AS source_record_id FROM Verse v JOIN Book b ON b.edition=v.edition AND b.id=v.book WHERE v.edition=? AND v.book IN ({placeholders}) ORDER BY {order}',[ed,*selected])
            while True:
                chunk=cursor.fetchmany(256)
                if not chunk:break
                if (cancel_event is not None and cancel_event.is_set()):cancelled=True;break
                if time.monotonic()-start>timeout or scanned>=max_scan_rows:truncated=True;break
                for r in chunk:
                    if scanned>=max_scan_rows:truncated=True;break
                    scanned+=1
                    if matches(fold(r['text'],diacritics)):
                        if total>=offset and len(rows)<limit:
                            meta=next(e for e in editions if e['id']==ed)
                            native=str(r['verse']);native_range=re.fullmatch(r'(\d+)(?:-(\d+))?',native)
                            item=dict(r);item.update({'edition':ed,'edition_name':meta['name'],'language':meta['language'],'license':meta['license'],'source':meta['source'],'reference':f'{r["book"]}.{r["chapter"]}.{r["verse"]}','label':native,'nativeVerseStart':int(native_range[1]) if native_range else None,'nativeVerseEnd':int(native_range[2] or native_range[1]) if native_range else None});rows.append(item)
                        total+=1
                if truncated:break
            if cancelled or truncated:break
    return {'status':'CANCELLED' if cancelled else 'PARTIAL' if truncated else 'VALID_RESULT' if rows else 'NO_MATCH','edition':edition,'query':query,'mode':mode,'diacritics':diacritics,'testament':testament,'books':books,'total':total,'total_exact':not(cancelled or truncated),'limit':limit,'offset':offset,'results':rows,'scanned_rows':scanned,'elapsed_ms':round((time.monotonic()-start)*1000,2),'comparison_policy':'NFC plus Unicode casefold; optional combining-mark removal; original text retained; native stable order; not morphology or translation equivalence'}
