"""Portable pinned upstream reference parser; the shipped seed is read-only."""
from __future__ import annotations
import contextlib,datetime,json,pathlib,re,shutil,sqlite3,subprocess,sys
ROOT=pathlib.Path(getattr(sys,'_MEIPASS',pathlib.Path(__file__).resolve().parents[1]))
DB=ROOT/'data/xref_reference.sqlite'
BOOK_PAIRS='Gen:GEN Exod:EXO Lev:LEV Num:NUM Deut:DEU Josh:JOS Judg:JDG Ruth:RUT 1Sam:1SA 2Sam:2SA 1Kgs:1KI 2Kgs:2KI 1Chr:1CH 2Chr:2CH Ezra:EZR Neh:NEH Esth:EST Job:JOB Ps:PSA Prov:PRO Eccl:ECC Song:SNG Isa:ISA Jer:JER Lam:LAM Ezek:EZK Dan:DAN Hos:HOS Joel:JOL Amos:AMO Obad:OBA Jonah:JON Mic:MIC Nah:NAM Hab:HAB Zeph:ZEP Hag:HAG Zech:ZEC Mal:MAL Matt:MAT Mark:MRK Luke:LUK John:JHN Acts:ACT Rom:ROM 1Cor:1CO 2Cor:2CO Gal:GAL Eph:EPH Phil:PHP Col:COL 1Thess:1TH 2Thess:2TH 1Tim:1TI 2Tim:2TI Titus:TIT Phlm:PHM Heb:HEB Jas:JAS 1Pet:1PE 2Pet:2PE 1John:1JN 2John:2JN 3John:3JN Jude:JUD Rev:REV'
BOOK_TO_NATIVE=dict(part.split(':')for part in BOOK_PAIRS.split())
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def connect_registry():
    connection=sqlite3.connect(DB.resolve().as_uri()+'?mode=ro&immutable=1',uri=True,timeout=10)
    connection.row_factory=sqlite3.Row;connection.execute('PRAGMA query_only=ON');return connection
def node_executable():
    embedded=ROOT/'runtime/node.exe'
    if embedded.is_file():return str(embedded)
    found=shutil.which('node')
    if found:return found
    raise RuntimeError('REFERENCE_PARSER_RUNTIME_UNAVAILABLE')
def parse_many(requests):
    if not isinstance(requests,list)or len(requests)>100:raise ValueError('PARSER_REQUEST_BOUND')
    payload=''.join(json.dumps(value,ensure_ascii=False)+'\n'for value in requests)
    command=[node_executable(),str(ROOT/'parser/parse.mjs')]
    result=subprocess.run(command,input=payload,text=True,encoding='utf-8',capture_output=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('REFERENCE_PARSER_EXECUTION_FAILED')
    values=[json.loads(line)for line in result.stdout.splitlines()if line.strip()]
    if len(values)!=len(requests):raise RuntimeError('REFERENCE_PARSER_RESPONSE_COUNT')
    return values
def parse_reference(reference,language='en',record=False):
    # record is accepted for interface compatibility, never a seed database write.
    return parse_many([{'reference':reference,'language':language}])[0]
def split_reference(reference):
    if not isinstance(reference,str)or ','in reference:raise ValueError('One contiguous normalized reference required')
    points=reference.split('-')
    if len(points)>2:raise ValueError('One explicit range required')
    def point(value):
        match=re.fullmatch(r'([1-4]?[A-Za-z]+)\.(\d+)\.(\d+)',value)
        if not match:raise ValueError('Normalized OSIS point required')
        return(match[1],int(match[2]),int(match[3]))
    return point(points[0]),point(points[-1])
def expand_reference(reference,limit=500):
    start,end=split_reference(reference)
    if start[0]!=end[0]:raise ValueError('Cross-book range retained without expansion')
    with contextlib.closing(connect_registry())as connection:
        row=connection.execute('SELECT chapters_json FROM BookRegistry WHERE osis=?',(start[0],)).fetchone()
    if row is None:raise ValueError('Unregistered book')
    lengths=json.loads(row[0]);output=[]
    for chapter in range(start[1],end[1]+1):
        if not 1<=chapter<=len(lengths):raise ValueError('Chapter outside declared parser reference system')
        first=start[2] if chapter==start[1] else 1
        last=end[2] if chapter==end[1] else lengths[chapter-1]
        if not 1<=first<=last<=lengths[chapter-1]:raise ValueError('Verse outside declared parser reference system')
        output.extend(f'{start[0]}.{chapter}.{verse}'for verse in range(first,last+1))
        if len(output)>limit:raise ValueError('Bounded range exceeded')
    return output
