"""Engine B: provenance-preserving raw directed cross-reference graph.

No scripture text, cross-app database, implicit inverse edge or range expansion.
The reference syntax here is an internal dataset-coordinate parser. The shared
laboratory parser remains the authority for human input and edition mapping.
"""
from __future__ import annotations
import argparse
import collections
import contextlib
import json
import pathlib
import re
import sqlite3
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATABASE = ROOT / 'data/xref_aggregate.sqlite'
REPOSITORY = 'https://github.com/neuu-org/bible-crossrefs-dataset'
COMMIT = '8aa012820f5881a787e87d71005a22f52844c4fb'
BOOKS = 'Gen Exod Lev Num Deut Josh Judg Ruth 1Sam 2Sam 1Kgs 2Kgs 1Chr 2Chr Ezra Neh Esth Job Ps Prov Eccl Song Isa Jer Lam Ezek Dan Hos Joel Amos Obad Jonah Mic Nah Hab Zeph Hag Zech Mal Matt Mark Luke John Acts Rom 1Cor 2Cor Gal Eph Phil Col 1Thess 2Thess 1Tim 2Tim Titus Phlm Heb Jas 1Pet 2Pet 1John 2John 3John Jude Rev'.split()
RAW_CODES = 'GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZE DAN HOS JOE AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV'.split()
ALIASES = {name.upper(): name for name in BOOKS}
ALIASES.update(zip(RAW_CODES, BOOKS))
ALIASES.update({'JOH':'John','MAR':'Mark','JAM':'Jas','NAH':'Nah','SOS':'Song',
                '1JO':'1John','2JO':'2John','3JO':'3John','JDE':'Jude'})
ORDER = {book: index for index, book in enumerate(BOOKS, 1)}


def canonical_book(value):
    key = str(value).strip().upper()
    if key not in ALIASES:
        raise ValueError('Unmapped dataset book code: ' + str(value))
    return ALIASES[key]


def parse_endpoint(value):
    """Preserve an endpoint range as one node; no verse enumeration/inversion."""
    if not isinstance(value, str) or len(value) > 160:
        raise ValueError('Reference must be a bounded OSIS-like string')
    points = value.strip().split('-')
    if len(points) not in (1, 2):
        raise ValueError('Expected one reference or one explicit endpoint range')
    parsed = []
    for point in points:
        match = re.fullmatch(r'([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)', point)
        if not match:
            raise ValueError('Expected normalized Book.chapter.verse coordinates')
        book = canonical_book(match[1])
        chapter, verse = int(match[2]), int(match[3])
        # Coordinate syntax bounds, not a claim about a particular canon.
        if not (0 <= chapter < 10000 and 0 <= verse < 1000000):
            raise ValueError('Dataset coordinate exceeds numeric guard')
        order = ORDER[book]*10**12 + chapter*10**6 + verse
        parsed.append((book, chapter, verse, order))
    start, end = parsed[0], parsed[-1]
    if start[3] > end[3]:
        raise ValueError('Reversed endpoint range')
    first = f'{start[0]}.{start[1]}.{start[2]}'
    last = f'{end[0]}.{end[1]}.{end[2]}'
    reference = first if len(points) == 1 else first+'-'+last
    return {'reference':reference,'start_book':start[0],'start_chapter':start[1],
            'start_verse':start[2],'end_book':end[0],'end_chapter':end[1],
            'end_verse':end[2],'start_order':start[3],'end_order':end[3],
            'is_range':int(len(points)==2)}


def open_readonly(path=DATABASE):
    path = pathlib.Path(path).resolve()
    connection = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    expected = connection.execute("SELECT COUNT(*) FROM GraphDataset WHERE repository=? AND commit_id=?",(REPOSITORY,COMMIT)).fetchone()[0]
    if expected != 2:
        connection.close()
        raise ValueError('Engine B dataset identity guard failed')
    return connection


def _reply(reference, edition_id, status='NO_MATCH', **statistics):
    return {'engine_id':'B','status':status,'reference':reference,'edition_id':edition_id,
            'results':[],'statistics':statistics}


def statistics(database=DATABASE):
    """Actual current table counts; called explicitly, not for every query."""
    with contextlib.closing(open_readonly(database)) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Graph%' ORDER BY name")]
        counts = {name:db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in tables}
        sources = [dict(r) for r in db.execute('SELECT d.dataset_id,COUNT(s.edge_source_id) AS assertions,COUNT(DISTINCT s.edge_id) AS unique_directed_edges FROM GraphDataset d LEFT JOIN GraphEdgeSource s ON s.dataset_id=d.dataset_id GROUP BY d.dataset_id')]
        return {'engine_id':'B','counts':counts,'source_specific':sources,
                'duplicate_assertions':counts['GraphEdgeSource']-counts['GraphEdge'],
                'direction_policy':'Raw directed assertions; incoming lookup does not create reverse edges',
                'range_policy':'Original range remains one endpoint; overlap matching is marked, not expansion'}


def _sources(value):
    if value is None:
        return ['openbible','souliberty']
    values = [value] if isinstance(value, str) else list(value)
    values = ['souliberty' if v == 'tsk' else v for v in values]
    if not values or any(v not in ('openbible','souliberty') for v in values):
        raise ValueError('Source filter must select openbible or souliberty/tsk')
    return sorted(set(values))


def query(reference: str, edition_id='eng-kjv', direction='both', limit=25, **options) -> dict:
    """Indexed adjacency lookup, preserving asserted orientation/provenance.

    Optional filters: source/sources, book/books, chapter, min_votes, min_weight.
    Edition mapping outside eng-kjv must be explicitly verified by the bridge via
    coordinate_mapping_verified=True; that flag is an assertion by its caller.
    database is an internal test/deployment path, never a user HTTP file input.
    """
    started = time.perf_counter()
    result = _reply(reference,edition_id)
    try:
        if direction not in ('outgoing','incoming','both'):
            raise ValueError('direction must be outgoing, incoming or both')
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=500:
            raise ValueError('limit must be an integer between1 and500')
        try:
            endpoint = parse_endpoint(reference)
        except ValueError as error:
            result.update(status='UNMAPPED_REFERENCE',error=str(error))
            return result
        result['reference'] = endpoint['reference']
        if edition_id != 'eng-kjv' and options.get('coordinate_mapping_verified') is not True:
            result.update(status='UNSUPPORTED_EDITION',error='KJV-based dataset coordinates require an explicit verified corpus/edition mapping')
            return result
        path = pathlib.Path(options.get('database',DATABASE))
        if not path.is_file():
            result.update(status='NO_SOURCE_DATA',error='Engine B graph has not been imported')
            return result
        sources = _sources(options.get('sources',options.get('source')))
        raw_books = options.get('books',options.get('book'))
        books = [] if raw_books is None else [canonical_book(b) for b in ([raw_books] if isinstance(raw_books,str) else raw_books)]
        chapter = options.get('chapter')
        if chapter is not None and (isinstance(chapter,bool) or not isinstance(chapter,int) or not 0<=chapter<10000):
            raise ValueError('chapter filter must be a bounded integer')
        minimum_votes,minimum_weight = options.get('min_votes'),options.get('min_weight')
        for value in (minimum_votes,minimum_weight):
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float))):
                raise ValueError('Numeric ranking threshold required')
        with contextlib.closing(open_readonly(path)) as db:
            nodes = list(db.execute('SELECT node_id,reference FROM GraphNode WHERE start_order<=? AND end_order>=?',(endpoint['end_order'],endpoint['start_order'])))
            if not nodes:
                result['statistics'].update(reason='No dataset endpoint overlaps the requested coordinates')
                return result
            node_ids = [r['node_id'] for r in nodes]
            marks = ','.join('?' for _ in node_ids)
            clauses,params,candidate_parts,candidate_params = [],[],[],[]
            for side in ('outgoing','incoming'):
                if direction not in (side,'both'):
                    continue
                field = 'e.source_node_id' if side=='outgoing' else 'e.target_node_id'
                other = 't' if side=='outgoing' else 's'
                candidate_parts.append('SELECT edge_id FROM GraphEdge WHERE '+field[2:]+' IN ('+marks+')')
                candidate_params.extend(node_ids)
                clause = field+' IN ('+marks+')'
                side_params = list(node_ids)
                if books:
                    clause += ' AND '+other+'.start_book IN ('+','.join('?' for _ in books)+')'
                    side_params.extend(books)
                if chapter is not None:
                    clause += ' AND '+other+'.start_chapter=?'
                    side_params.append(chapter)
                clauses.append('('+clause+')');params.extend(side_params)
            selected_sources = ','.join('?' for _ in sources)
            # UNION builds the bounded indexed adjacency first. CROSS JOIN keeps
            # source/vote aggregation after that small candidate set rather than
            # scanning all730k provenance assertions for every verse lookup.
            base = ' FROM ('+' UNION '.join(candidate_parts)+''') candidate
              CROSS JOIN GraphEdge e ON e.edge_id=candidate.edge_id
              CROSS JOIN GraphNode s ON s.node_id=e.source_node_id
              CROSS JOIN GraphNode t ON t.node_id=e.target_node_id
              CROSS JOIN GraphEdgeSource es ON es.edge_id=e.edge_id
              LEFT JOIN GraphVote v ON v.edge_source_id=es.edge_source_id
              WHERE ('''+ ' OR '.join(clauses)+') AND es.dataset_id IN ('+selected_sources+')'
            params = candidate_params+params+sources
            having,having_params = [],[]
            if minimum_votes is not None:
                having.append('MAX(v.votes)>=?');having_params.append(minimum_votes)
            if minimum_weight is not None:
                having.append('COALESCE(MAX(v.votes),0)+COUNT(DISTINCT es.dataset_id)>=?');having_params.append(minimum_weight)
            grouped = base+' GROUP BY e.edge_id'+(' HAVING '+' AND '.join(having) if having else '')
            available = db.execute('SELECT COUNT(*) FROM (SELECT e.edge_id'+grouped+')',params+having_params).fetchone()[0]
            sql = '''SELECT e.edge_id,e.source_node_id,e.target_node_id,s.reference AS source_reference,
              t.reference AS target_reference,MAX(v.votes) AS votes,
              COUNT(DISTINCT es.dataset_id) AS source_count,
              COALESCE(MAX(v.votes),0)+COUNT(DISTINCT es.dataset_id) AS rank_score'''+grouped+' ORDER BY rank_score DESC,s.reference,t.reference LIMIT ?'
            rows = db.execute(sql,params+having_params+[limit]).fetchall()
            for row in rows:
                outgoing = row['source_node_id'] in node_ids
                incoming = row['target_node_id'] in node_ids
                orientation = 'both' if outgoing and incoming else ('outgoing' if outgoing else 'incoming')
                evidence_rows = db.execute('''SELECT es.dataset_id,es.source_path,es.source_record,
                  es.raw_record_json,es.source_file_sha256,v.votes,
                  sr.raw_reference AS raw_source_reference,tr.raw_reference AS raw_target_reference
                  FROM GraphEdgeSource es LEFT JOIN GraphVote v ON v.edge_source_id=es.edge_source_id
                  JOIN GraphReference sr ON sr.reference_id=es.source_reference_id
                  JOIN GraphReference tr ON tr.reference_id=es.target_reference_id
                  WHERE es.edge_id=? AND es.dataset_id IN ('''+selected_sources+') ORDER BY es.dataset_id,es.edge_source_id',[row['edge_id']]+sources).fetchall()
                evidence = [{'dataset':v['dataset_id'],'repository':REPOSITORY,'commit':COMMIT,
                    'path':v['source_path'],'source_record':v['source_record'],
                    'source_file_sha256':v['source_file_sha256'],
                    'raw_source_reference':v['raw_source_reference'],'raw_target_reference':v['raw_target_reference'],
                    'votes':v['votes'],'generated_reverse':False,
                    'interpretation':'Dataset cross-reference assertion; no more specific theological type supplied'} for v in evidence_rows]
                primary = evidence[0]
                result['results'].append({'source_reference':row['source_reference'],
                    'target_reference':row['target_reference'],'direction':orientation,
                    'relationship_type':'dataset_cross_reference',
                    'dataset_source':{k:primary[k] for k in ('repository','commit','path','source_record')},
                    'votes':row['votes'],'weight':row['rank_score'],
                    'source_agreement_count':row['source_count'],'evidence':evidence,
                    'range_match':any(n['reference']!=endpoint['reference'] for n in nodes if n['node_id'] in (row['source_node_id'],row['target_node_id']))})
            result['status'] = 'VALID_RESULT' if rows else 'NO_MATCH'
            result['statistics'].update({'available_edges':available,'returned_edges':len(rows),
                'truncated':available>limit,'matched_endpoint_nodes':len(nodes),
                'sources_filter':sources,'neighbor_book_filter':books,'neighbor_chapter_filter':chapter,
                'coordinate_basis':'KJV-based source reference system; no universal versification assertion',
                'edition_mapping':'source_native_kjv' if edition_id=='eng-kjv' else 'caller_asserted_verified_mapping',
                'ranking':'MAX actual OpenBible votes per directed edge + distinct selected source count; TSK missing votes stay null',
                'direction_policy':'Original source/target retained; incoming is lookup orientation, never an inferred inverse',
                'range_policy':'Stored whole range; endpoint overlap is explicitly range_match, not expanded verse assertions'})
    except (ValueError,TypeError,sqlite3.Error,OSError) as error:
        result.update(status='QUERY_ERROR',error=str(error))
    finally:
        result['statistics']['elapsed_ms']=(time.perf_counter()-started)*1000
    return result


def neighborhood(reference,edition_id='eng-kjv',direction='both',depth=1,max_nodes=60,max_edges=200,per_node_limit=25,**options):
    if not (isinstance(depth,int) and 1<=depth<=2 and isinstance(max_nodes,int) and 2<=max_nodes<=200 and isinstance(max_edges,int) and 1<=max_edges<=1000):
        return _reply(reference,edition_id,'QUERY_ERROR',error='Neighborhood bounds: depth1..2, nodes2..200, edges1..1000')
    initial = query(reference,edition_id,direction,per_node_limit,**options)
    if initial['status'] not in ('VALID_RESULT','NO_MATCH'):
        return initial
    root=initial['reference'];queue=collections.deque([(root,0)]);nodes={root};seen=set();edges={};truncated=False
    while queue and len(edges)<max_edges:
        current,level=queue.popleft()
        if current in seen or level>=depth:continue
        seen.add(current)
        answer=initial if current==root else query(current,edition_id,direction,per_node_limit,**options)
        truncated=truncated or answer['statistics'].get('truncated',False)
        for edge in answer['results']:
            new_nodes={edge['source_reference'],edge['target_reference']}-nodes
            if len(nodes)+len(new_nodes)>max_nodes or len(edges)>=max_edges:
                truncated=True;continue
            nodes.update(new_nodes)
            key=(edge['source_reference'],edge['target_reference'])
            if key not in edges:
                edge['traversal_depth']=level+1;edges[key]=edge
            for node in sorted(new_nodes):queue.append((node,level+1))
    if queue:truncated=True
    out=_reply(root,edition_id,'VALID_RESULT' if edges else 'NO_MATCH',depth=depth,
        max_nodes=max_nodes,max_edges=max_edges,returned_nodes=len(nodes),returned_edges=len(edges),
        truncated=truncated,range_policy='Whole-range nodes; no generated inverse edges',
        ranking_scope='Each bounded adjacency is ranked independently; not a global centrality score')
    out['results']=list(edges.values());out['nodes']=sorted(nodes)
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference',nargs='?',default='John.1.1')
    parser.add_argument('--edition-id',default='eng-kjv')
    parser.add_argument('--direction',choices=['outgoing','incoming','both'],default='both')
    parser.add_argument('--limit',type=int,default=25)
    parser.add_argument('--source',action='append')
    parser.add_argument('--book',action='append')
    parser.add_argument('--chapter',type=int)
    parser.add_argument('--neighborhood-depth',type=int)
    parser.add_argument('--stats',action='store_true')
    args=parser.parse_args()
    if args.stats:answer=statistics()
    else:
        options={'sources':args.source,'books':args.book,'chapter':args.chapter}
        if args.neighborhood_depth:answer=neighborhood(args.reference,args.edition_id,args.direction,args.neighborhood_depth,per_node_limit=args.limit,**options)
        else:answer=query(args.reference,args.edition_id,args.direction,args.limit,**options)
    print(json.dumps(answer,ensure_ascii=False,indent=2))
    return 1 if answer.get('status') in ('QUERY_ERROR','NO_SOURCE_DATA') else 0


if __name__=='__main__':raise SystemExit(main())
