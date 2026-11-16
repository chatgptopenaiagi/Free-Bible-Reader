"""Bounded, read-only source inspection and explicit user-mapped import rows.

SQL dumps are parsed as data. They are NEVER executed by SQLite or SQL Server.
No source connection is writable; library.py owns the separate destination.
"""
from __future__ import annotations
import base64,contextlib,csv,hashlib,io,itertools,json,pathlib,re,shutil,sqlite3,uuid,zipfile
from . import library

MAX_FILE=512*1024*1024
MAX_SQLITE_FILE=16*1024*1024*1024
MAX_ZIP_BYTES=256*1024*1024
MAX_CELL=1_000_000
ALLOWED={'.sqlite':'sqlite','.sqlite3':'sqlite','.db':'sqlite','.db3':'sqlite','.csv':'csv','.json':'json','.jsonl':'jsonl','.ndjson':'jsonl','.sql':'sql','.zip':'zip'}
_IDENT=re.compile(r'^[^\x00-\x1f]{1,128}$')

def quote_identifier(name):
    if not isinstance(name,str) or not _IDENT.fullmatch(name):raise ValueError('INVALID_IDENTIFIER')
    return '"'+name.replace('"','""')+'"'

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def json_safe(value):
    if isinstance(value,(bytes,bytearray)):
        if len(value)>MAX_CELL:raise ValueError('BINARY_CELL_TOO_LARGE')
        return {'__fbr_binary_base64__':base64.b64encode(value).decode('ascii'),'byte_length':len(value),'sha256':hashlib.sha256(value).hexdigest()}
    if isinstance(value,dict):return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value,list):return [json_safe(v) for v in value]
    return value

def _inspection_path(id):
    try:uuid.UUID(str(id))
    except ValueError:raise ValueError('INVALID_INSPECTION_ID') from None
    return library.data_root()/'inspections'/(str(id)+'.json')

def load_inspection(id):
    p=_inspection_path(id)
    if not p.is_file():raise ValueError('INSPECTION_NOT_FOUND')
    return json.loads(p.read_text(encoding='utf-8'))

def verify_staged(info,full=False):
    p=pathlib.Path(info['path'])
    st=p.stat()
    if st.st_size!=info['size'] or st.st_mtime_ns!=info['mtime_ns']:raise ValueError('SOURCE_CHANGED_REINSPECT_REQUIRED')
    if full and sha256(p)!=info['sha256']:raise ValueError('SOURCE_CHANGED_REINSPECT_REQUIRED')

def _json_array_rows(stream):
    """Incremental top-level array of objects; JSONL uses its own line iterator."""
    dec=json.JSONDecoder();buf='';pos=0;started=False;finished=False;expect_value=True;had_value=False;after_comma=False
    while True:
        chunk=stream.read(65536)
        if chunk:buf=buf[pos:]+chunk;pos=0
        elif not buf[pos:].strip():break
        while True:
            while pos<len(buf) and buf[pos].isspace():pos+=1
            if not started:
                if pos>=len(buf):break
                if buf[pos]!='[':raise ValueError('JSON_TOP_LEVEL_ARRAY_REQUIRED_USE_JSONL')
                pos+=1;started=True;continue
            if not expect_value:
                if pos>=len(buf):break
                if buf[pos]==',':pos+=1;expect_value=True;after_comma=True;continue
                if buf[pos]!=']':raise ValueError('JSON_ARRAY_SEPARATOR_REQUIRED')
            if pos<len(buf) and buf[pos]==']':
                if after_comma:raise ValueError('JSON_TRAILING_COMMA_REJECTED')
                pos+=1;finished=True
                if buf[pos:].strip() or stream.read(1).strip():raise ValueError('JSON_TRAILING_DATA')
                return
            try:row,end=dec.raw_decode(buf,pos)
            except json.JSONDecodeError:
                if not chunk:raise ValueError('INVALID_JSON') from None
                if len(buf)-pos>MAX_CELL*8:raise ValueError('JSON_RECORD_TOO_LARGE')
                break
            if not isinstance(row,dict):raise ValueError('JSON_OBJECT_ROWS_REQUIRED')
            yield row;pos=end;expect_value=False;had_value=True;after_comma=False
        if not chunk:break
    if not finished:raise ValueError('INCOMPLETE_JSON_ARRAY')

def _sql_statements(stream):
    # Statement boundaries respect SQL quoted literals/identifiers. Comments are
    # recognized outside quotes; CREATE/INSERT validators still reject code.
    buf=[];quote=None;line_comment=False;block_comment=False;previous=''
    for line in stream:
        i=0
        while i<len(line):
            ch=line[i];nxt=line[i+1:i+2]
            if line_comment:
                if ch=='\n':line_comment=False;buf.append(' ')
                i+=1;continue
            if block_comment:
                if ch=='*' and nxt=='/':block_comment=False;i+=2
                else:i+=1
                continue
            if quote:
                buf.append(ch)
                if ch==quote:
                    if nxt==quote:buf.append(nxt);i+=2;continue
                    quote=None
                i+=1;continue
            if ch=='-' and nxt=='-':line_comment=True;i+=2;continue
            if ch=='/' and nxt=='*':block_comment=True;i+=2;continue
            if ch in "'\"`":quote=ch;buf.append(ch)
            elif ch==';':
                if ''.join(buf).strip():yield ''.join(buf).strip()
                buf=[]
            else:buf.append(ch)
            if len(buf)>MAX_CELL*8:raise ValueError('SQL_STATEMENT_TOO_LARGE')
            i+=1
    if quote or block_comment:raise ValueError('INCOMPLETE_SQL_DUMP')
    if ''.join(buf).strip():yield ''.join(buf).strip()

SQL_IDENT=r'(?:"(?:[^"]|"")+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_]*)'
def _unquote(s):return s.strip().strip('"`[]').replace('""','"')

def _split_values(s):
    # Literal-only grammar: NULL, signed decimal, SQL string and hex blob.
    i=0;values=[]
    while i<len(s):
        while i<len(s) and s[i].isspace():i+=1
        if i>=len(s):break
        if s[i:i+1]=="'":
            i+=1;v=[]
            while i<len(s):
                if s[i]=="'":
                    if s[i+1:i+2]=="'":v.append("'");i+=2;continue
                    i+=1;break
                v.append(s[i]);i+=1
            else:raise ValueError('INVALID_SQL_LITERAL')
            val=''.join(v)
        else:
            m=re.match(r'(NULL|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)(?=\s*(?:,|$))',s[i:],re.I)
            if not m:raise ValueError('SQL_NON_LITERAL_VALUE_REJECTED')
            val=None if m[1].upper()=='NULL' else m[1];i+=len(m[0])
        values.append(val)
        while i<len(s) and s[i].isspace():i+=1
        if i<len(s):
            if s[i]!=',':raise ValueError('SQL_NON_LITERAL_VALUE_REJECTED')
            i+=1
    return values

def sql_rows(stream,table=None,schema_only=False):
    schemas={}
    for statement in _sql_statements(stream):
        if re.fullmatch(r'(?:BEGIN(?: TRANSACTION)?|COMMIT|END TRANSACTION)',statement,re.I):continue
        m=re.fullmatch(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?('+SQL_IDENT+r')\s*\((.*)\)',statement,re.I|re.S)
        if m:
            name=_unquote(m[1]);cols=[]
            # Split commas only outside nested type/constraint parentheses.
            parts=re.split(r',(?=(?:[^()]|\([^()]*\))*$)',m[2])
            for part in parts:
                part=part.strip()
                if re.match(r'^(?:PRIMARY|FOREIGN|UNIQUE|CHECK|CONSTRAINT)\b',part,re.I):continue
                cm=re.match('('+SQL_IDENT+r')\s+(?:[A-Za-z][A-Za-z0-9_]*(?:\s*\([^)]*\))?)',part)
                if not cm:raise ValueError('UNSUPPORTED_SQL_COLUMN_DECLARATION')
                cols.append(_unquote(cm[1]))
            schemas[name]=cols
            if schema_only:yield {'table':name,'columns':cols}
            continue
        m=re.fullmatch(r'INSERT\s+INTO\s+('+SQL_IDENT+r')\s*(?:\((.*?)\))?\s+VALUES\s*\((.*)\)',statement,re.I|re.S)
        if not m:raise ValueError('SQL_STATEMENT_NOT_ALLOWLISTED')
        name=_unquote(m[1]);cols=[_unquote(s) for s in m[2].split(',')] if m[2] else schemas.get(name)
        if not cols:raise ValueError('SQL_INSERT_COLUMNS_REQUIRED')
        values=_split_values(m[3])
        if len(values)!=len(cols):raise ValueError('SQL_COLUMN_VALUE_MISMATCH')
        if not schema_only and (table is None or table==name):yield dict(zip(cols,values))

def _rows(info,table=None,selection=None):
    p=pathlib.Path(info['path']);fmt=info['format']
    if fmt=='sqlite':
        with contextlib.closing(library.open_readonly(p)) as c:
            names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if table not in names:raise ValueError('SOURCE_TABLE_NOT_FOUND')
            # SQLite data files are never asked to execute stored views/triggers.
            where='';params=[]
            if selection and selection.get('edition_column'):
                where=' WHERE '+quote_identifier(selection['edition_column'])+'=?';params=[selection['edition_value']]
            # Rowid gives a stable snapshot order. WITHOUT ROWID tables use their
            # declared primary-key columns, otherwise inspection rejects them.
            try:cursor=c.execute('SELECT * FROM '+quote_identifier(table)+where+' ORDER BY rowid',params)
            except sqlite3.OperationalError:
                pk=[r['name'] for r in c.execute('PRAGMA table_info('+quote_identifier(table)+')') if r['pk']]
                if not pk:raise ValueError('STABLE_SOURCE_ORDER_REQUIRED') from None
                cursor=c.execute('SELECT * FROM '+quote_identifier(table)+where+' ORDER BY '+','.join(map(quote_identifier,pk)),params)
            for row in cursor:yield dict(row)
    elif fmt=='csv':
        with p.open(encoding='utf-8-sig',newline='') as f:
            csv.field_size_limit(MAX_CELL)
            reader=csv.DictReader(f);headers=reader.fieldnames or []
            if not headers or len(headers)>200 or len(set(headers))!=len(headers) or any(not h or len(h)>128 for h in headers):raise ValueError('CSV_UNIQUE_HEADER_REQUIRED')
            for row in reader:
                if None in row or any(v is None for v in row.values()):raise ValueError('CSV_COLUMN_COUNT_MISMATCH')
                yield row
    elif fmt=='jsonl':
        with p.open(encoding='utf-8-sig') as f:
            for line in f:
                if len(line)>MAX_CELL*8:raise ValueError('JSON_RECORD_TOO_LARGE')
                if line.strip():
                    v=json.loads(line)
                    if not isinstance(v,dict):raise ValueError('JSON_OBJECT_ROWS_REQUIRED')
                    yield v
    elif fmt=='json':
        with p.open(encoding='utf-8-sig') as f:yield from _json_array_rows(f)
    elif fmt=='sql':
        with p.open(encoding='utf-8-sig') as f:yield from sql_rows(f,table)
    else:raise ValueError('UNSUPPORTED_FORMAT')

def inspect_source(path,format=None,member=None,copy=True):
    p=pathlib.Path(path).expanduser().resolve()
    if not p.is_file():raise ValueError('SOURCE_FILE_NOT_FOUND')
    fmt=format or ALLOWED.get(p.suffix.lower())
    if fmt not in set(ALLOWED.values()):raise ValueError('UNSUPPORTED_FORMAT')
    size=p.stat().st_size
    if fmt=='sqlite' and size>MAX_SQLITE_FILE:raise ValueError('LOCAL_SQLITE_SIZE_LIMIT_16GIB')
    if fmt!='sqlite' and size>MAX_FILE:raise ValueError('SOURCE_TOO_LARGE')
    if fmt=='sqlite' and pathlib.Path(str(p)+'-wal').exists() and pathlib.Path(str(p)+'-wal').stat().st_size:
        raise ValueError('SQLITE_ACTIVE_WAL_EXPORT_A_CLOSED_SNAPSHOT_FIRST')
    if fmt=='zip':
        with zipfile.ZipFile(p) as z:
            entries=z.infolist()
            if len(entries)>128 or sum(i.file_size for i in entries)>MAX_ZIP_BYTES:raise ValueError('ZIP_LIMIT_EXCEEDED')
            options=[]
            for e in entries:
                n=e.filename.replace('\\','/');parts=pathlib.PurePosixPath(n)
                if n.startswith('/') or '..' in parts.parts or ':' in n or (e.external_attr>>16)&0o170000==0o120000:raise ValueError('UNSAFE_ZIP_PATH')
                if e.file_size>MAX_FILE or e.file_size>max(e.compress_size,1)*1000:raise ValueError('ZIP_EXPANSION_LIMIT')
                if not e.is_dir() and ALLOWED.get(parts.suffix.lower()) not in (None,'zip'):options.append(e.filename)
            if member is None:return {'format':'zip','members':options,'requires_member_selection':True,'size':size,'sha256':sha256(p)}
            if member not in options:raise ValueError('ZIP_MEMBER_NOT_ALLOWED')
            target=library.data_root()/'staging'/(str(uuid.uuid4())+pathlib.PurePosixPath(member).suffix)
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(member) as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,65536)
            out=inspect_source(target,copy=False);out['archive_sha256']=sha256(p);out['archive_member']=member
            _inspection_path(out['inspection_id']).write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8');return out
    id=str(uuid.uuid4());warnings=[]
    # Large external SQLite remains read-only, avoiding a second 3GB master copy.
    staged=copy and (fmt!='sqlite' or size<=128*1024*1024)
    if staged:
        target=library.data_root()/'staging'/(id+p.suffix.lower());target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target);p=target
    elif fmt=='sqlite':warnings.append('Large/external SQLite is read directly in read-only mode; source stat is checked for every batch and full SHA again before completion.')
    st=p.stat();out={'inspection_id':id,'format':fmt,'path':str(p),'staged_copy':staged,'size':st.st_size,'mtime_ns':st.st_mtime_ns,'sha256':sha256(p),'tables':[],'warnings':warnings}
    if fmt=='sqlite':
        with contextlib.closing(library.open_readonly(p)) as c:
            plain={r['name'] for r in c.execute('PRAGMA table_list') if r['type']=='table'}
            for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' LIMIT 80"):
                name=r[0];cols=[dict(x) for x in c.execute('PRAGMA table_info('+quote_identifier(name)+')')]
                if name not in plain:continue # internal FTS shadow/virtual tables are not source data tables
                out['tables'].append({'name':name,'columns':[x['name'] for x in cols],'column_types':{x['name']:x['type'] for x in cols}})
    elif fmt=='sql':
        with p.open(encoding='utf-8-sig') as f:
            tables={}
            # Parse the WHOLE bounded dump before confirmation, rejecting trailing code.
            for entry in sql_rows(f,schema_only=True):tables[entry['table']]=entry['columns']
            out['tables']=[{'name':k,'columns':v} for k,v in tables.items()]
    else:
        sample=list(itertools.islice(_rows(out),5));cols=list(dict.fromkeys(k for r in sample for k in r))
        out['tables']=[{'name':'rows','columns':cols,'preview':sample}]
    # Preview is a bounded read; source record counts are not invented here.
    for table in out['tables']:
        if 'preview' not in table:table['preview']=json_safe(list(itertools.islice(_rows(out,table['name']),5)))
    folder=_inspection_path(id).parent;folder.mkdir(parents=True,exist_ok=True)
    known={t['name']:set(t['columns']) for t in out['tables']}
    if fmt=='sqlite' and {'id','language','language_english','vernacular_title','english_title'}<=known.get('version',set()) and {'version_id','book','chapter','start_verse','end_verse','text'}<=known.get('verse',set()):
        out['source_edition_selector']={'available':True,'kind':'version-table','api':'list_source_editions','mapping_template':{'table':'verse','book':'book','chapter':'chapter','verse':'start_verse','end_verse':'end_verse','text':'text','source_record_id':'id','edition_column':'version_id'}}
    elif fmt=='sqlite' and {'id','name','language','metadata_json'}<=known.get('Edition',set()) and {'edition','book','chapter','verse','text'}<=known.get('Verse',set()):
        template={'table':'Verse','book':'book','chapter':'chapter','verse':'verse','text':'text','edition_column':'edition'}
        if 'source_record_id' in known['Verse']:template['source_record_id']='source_record_id'
        out['source_edition_selector']={'available':True,'kind':'reader-package','api':'list_source_editions','mapping_template':template}
    _inspection_path(id).write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8')
    return out

def list_source_editions(inspection_id,query='',limit=50,offset=0,source_edition_id=None):
    info=load_inspection(inspection_id);verify_staged(info)
    if info['format']!='sqlite' or not info.get('source_edition_selector',{}).get('available'):raise ValueError('SOURCE_EDITION_SELECTOR_UNAVAILABLE')
    if not isinstance(query,str) or len(query)>200 or not isinstance(limit,int) or isinstance(limit,bool) or not 1<=limit<=100 or not isinstance(offset,int) or isinstance(offset,bool) or not 0<=offset<=100000:raise ValueError('INVALID_EDITION_PAGINATION')
    if info['source_edition_selector'].get('kind')=='reader-package':
        with contextlib.closing(library.open_readonly(info['path'])) as db:
            matches=[]
            for row in db.execute('SELECT * FROM Edition ORDER BY id'):
                e=dict(row)
                if source_edition_id is not None and e['id']!=str(source_edition_id):continue
                if query and query.casefold() not in ' '.join(str(e.get(k,'')) for k in ('id','name','language')).casefold():continue
                e['source_edition_id']=e.pop('id');e['coverage']='Package metadata; native original labels retained';e['row_count']=None;e['metadata']=json.loads(e.pop('metadata_json'))
                if source_edition_id is not None:e['row_count']=db.execute('SELECT COUNT(*) FROM Verse WHERE edition=?',(e['source_edition_id'],)).fetchone()[0]
                matches.append(e)
        return {'inspection_id':inspection_id,'editions':matches[offset:offset+limit],'total':len(matches),'limit':limit,'offset':offset,'mapping_template':info['source_edition_selector']['mapping_template'],'source_identifiers_are_actual':True}
    where='';params=[]
    if source_edition_id is not None:where=' WHERE id=?';params=[str(source_edition_id)]
    elif query:
        term='%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        where=" WHERE id LIKE ? ESCAPE '\\' OR language LIKE ? ESCAPE '\\' OR language_english LIKE ? ESCAPE '\\' OR vernacular_title LIKE ? ESCAPE '\\' OR english_title LIKE ? ESCAPE '\\'";params=[term]*5
    with contextlib.closing(library.open_readonly(info['path'])) as db:
        total=db.execute('SELECT COUNT(*) FROM version'+where,params).fetchone()[0]
        rows=[]
        for r in db.execute('SELECT * FROM version'+where+' ORDER BY id LIMIT ? OFFSET ?',params+[limit,offset]):
            e=dict(r);e['source_edition_id']=e.pop('id');e['name']=e.get('vernacular_title') or e.get('english_title') or e['source_edition_id'];e['coverage']='Not measured from metadata alone';e['row_count']=None
            if source_edition_id is not None:e['row_count']=db.execute('SELECT COUNT(*) FROM verse WHERE version_id=?',(e['source_edition_id'],)).fetchone()[0]
            rows.append(e)
    return {'inspection_id':inspection_id,'editions':rows,'total':total,'limit':limit,'offset':offset,'mapping_template':info['source_edition_selector']['mapping_template'],'source_identifiers_are_actual':True}

def validate_mapping(info,mapping):
    if not isinstance(mapping,dict):raise ValueError('COLUMN_MAPPING_REQUIRED')
    table=mapping.get('table','rows');t=next((t for t in info['tables'] if t['name']==table),None)
    if not t:raise ValueError('SOURCE_TABLE_NOT_FOUND')
    for key in ('book','chapter','verse','text'):
        if mapping.get(key) not in t['columns']:raise ValueError('MISSING_MAPPED_COLUMN_'+key.upper())
    for key in ('end_verse','source_record_id','edition_column','order_column'):
        if mapping.get(key) is not None and mapping[key] not in t['columns']:raise ValueError('INVALID_MAPPED_COLUMN')
    if mapping.get('edition_column') and mapping.get('edition_value') is None:raise ValueError('SOURCE_EDITION_SELECTION_REQUIRED')
    if 'book_map' in mapping and (not isinstance(mapping['book_map'],dict) or len(mapping['book_map'])>200):raise ValueError('INVALID_BOOK_MAP')
    for field in ('book_map','book_names'):
        if field in mapping and (not isinstance(mapping[field],dict) or len(mapping[field])>200 or any(not isinstance(k,str) or not isinstance(v,str) or not k or not v or len(k)>120 or len(v)>120 or '\x00' in k+v for k,v in mapping[field].items())):raise ValueError('INVALID_BOOK_MAP')
    return True

def mapped_rows(info,mapping,start=0):
    validate_mapping(info,mapping);accepted=0
    for index,row in enumerate(_rows(info,mapping.get('table','rows'),mapping)):
        if mapping.get('edition_column') and str(row.get(mapping['edition_column']))!=str(mapping['edition_value']):continue
        if accepted<start:accepted+=1;continue
        accepted+=1
        rawtext=row.get(mapping['text'])
        if not isinstance(rawtext,str) or len(rawtext)>MAX_CELL:raise ValueError('INVALID_TEXT_CELL')
        if any(row.get(mapping[k]) is None or isinstance(row.get(mapping[k]),bool) for k in ('book','chapter','verse')):raise ValueError('INVALID_NATIVE_LOCATOR')
        labels={k:str(row.get(mapping[k],'')) for k in ('book','chapter','verse')}
        if any(not v or len(v)>120 or '\x00' in v for v in labels.values()):raise ValueError('INVALID_NATIVE_LOCATOR')
        labels['book']=str(mapping.get('book_map',{}).get(labels['book'],labels['book']))
        if mapping.get('end_verse'):
            end_value=row.get(mapping['end_verse'])
            if isinstance(end_value,bool):raise ValueError('INVALID_NATIVE_LOCATOR')
            end='' if end_value is None else str(end_value)
            if len(end)>120 or '\x00' in end:raise ValueError('INVALID_NATIVE_LOCATOR')
            if end and end!=labels['verse']:labels['verse']+='-'+end
        record_id=row.get(mapping['source_record_id']) if mapping.get('source_record_id') else index
        yield {**labels,'text':rawtext,'source_record_id':str(record_id) if record_id is not None else None,'raw':json_safe(row)}

def preview_import(inspection_id,mapping,metadata=None,limit=8):
    info=load_inspection(inspection_id);verify_staged(info);validate_mapping(info,mapping)
    rows=list(itertools.islice(mapped_rows(info,mapping),min(max(int(limit),1),25)))
    return {'valid':bool(rows),'inspection_id':inspection_id,'sample':rows,'mapping':mapping,'metadata':metadata or {},'warnings':info['warnings']+['Source labels/ranges retained; no automatic versification or translation equivalence asserted.'],'requires_explicit_confirmation':True}
