"""Engine A query contract over real pinned visual cross-reference assertions.

No corpus mutation, translation equivalence, invented edges or hidden database build.
CLI: python engines/visual/engine.py John.1.1 --direction both --limit 25
"""
from pathlib import Path
import argparse,json,sqlite3,hashlib,re,time
try:from .layout import compute_layout,point,arc_geometry
except ImportError:from layout import compute_layout,point,arc_geometry

LAB=Path(__file__).resolve().parents[2]
DATABASE=LAB/'data'/'xref_visual.sqlite'
NORMALIZED=re.compile(r'^[1-3]?[A-Za-z]+\.\d+\.\d+(?:-[1-3]?[A-Za-z]+\.\d+\.\d+)?$')
MAX_LINKS=100

def query(reference:str,edition_id='eng-kjv',direction='both',limit=25,**options):
    started=time.perf_counter()
    output={'engine_id':'A','status':'QUERY_ERROR','reference':reference,'edition_id':edition_id,'direction':direction,'results':[],
      'nodes':[],'edges':[],'genres':[],'layout':None,'assertion_scope':'SOURCE_GRAPH_ASSERTIONS_NOT_VERSE_OR_THEOLOGICAL_EQUIVALENCE'}
    connection=None
    try:
        if not isinstance(reference,str)or not isinstance(edition_id,str):raise ValueError('reference and edition_id must be strings')
        if direction not in ('incoming','outgoing','both'):raise ValueError('direction must be incoming, outgoing or both')
        if isinstance(limit,bool)or not isinstance(limit,int)or limit<1:raise ValueError('limit must be a positive integer')
        effective_limit=min(limit,MAX_LINKS);output.update({'requested_limit':limit,'limit':effective_limit,'node_bound':3*effective_limit+2})
        if not DATABASE.is_file():
            output.update(status='NO_SOURCE_DATA',message='The visual source database has not been built.');return output
        connection=sqlite3.connect(DATABASE.as_uri()+'?mode=ro',uri=True,timeout=3)
        connection.row_factory=sqlite3.Row;connection.execute('PRAGMA query_only=ON')
        mapping=connection.execute('SELECT * FROM VisualEditionMapping WHERE corpus_edition_id=?',(edition_id,)).fetchone()
        if mapping is None:
            output.update(status='UNSUPPORTED_EDITION',message='No visual coordinate mapping is registered for this corpus edition.');return output
        output['mapping']={'status':mapping['mapping_status'],'coverage':mapping['coverage'],'visual_edition_id':mapping['visual_edition_id'],
          'text_alignment_status':'UNMAPPED_REFERENCE','evidence':json.loads(mapping['evidence_json']),
          'bridge_requirement':'Independent source-unit/text correspondence proof is required; graph coordinates alone do not establish verse equivalence.'}
        if not NORMALIZED.fullmatch(reference):
            output.update(status='UNMAPPED_REFERENCE',message='A normalized OSIS verse or fully qualified OSIS range is required.');return output
        endpoints=reference.split('-');start_ref=endpoints[0];end_ref=endpoints[-1]
        start=connection.execute('SELECT * FROM VisualReference WHERE reference=?',(start_ref,)).fetchone()
        end=connection.execute('SELECT * FROM VisualReference WHERE reference=?',(end_ref,)).fetchone()
        if start is None or end is None:
            output.update(status='UNMAPPED_REFERENCE',message='The reference is outside this upstream 66-book KJV coordinate universe. Apocrypha and other versifications are not inferred.');return output
        lo,hi=start['global_index'],end['global_index']
        if lo>hi:
            output.update(status='UNMAPPED_REFERENCE',message='The normalized reference range is reversed.');return output
        source=connection.execute('SELECT * FROM VisualDatasetSource LIMIT 1').fetchone()
        if source is None:
            output.update(status='NO_SOURCE_DATA',message='No visual source dataset is available.');return output
        provenance={'repository':source['repository'],'commit':source['source_commit'],'path':source['source_path'],
          'archive_sha256':source['archive_sha256'],'member_sha256':source['member_sha256'],'snapshot_date':source['snapshot_date'],
          'license':source['license'],'attribution':source['attribution']}
        output['dataset_source']=provenance
        outgoing='(source_index BETWEEN ? AND ?)';incoming='(target_start_index<=? AND target_end_index>=?)'
        if direction=='outgoing':where=outgoing;params=[lo,hi]
        elif direction=='incoming':where=incoming;params=[hi,lo]
        else:where='('+outgoing+' OR '+incoming+')';params=[lo,hi,hi,lo]
        minimum=options.get('min_votes')
        if minimum is not None:
            if isinstance(minimum,bool)or not isinstance(minimum,int):raise ValueError('min_votes must be an integer when supplied')
            where+=' AND votes>=?';params.append(minimum)
        output['filters']={'min_votes':minimum,'default_vote_policy':'All signed source votes; the original UI defaults to 4, but this API does not silently hide records.'}
        count=connection.execute('SELECT COUNT(*) FROM VisualEdge WHERE accepted=1 AND '+where,params).fetchone()[0]
        rows=connection.execute('SELECT * FROM VisualEdge WHERE accepted=1 AND '+where+' ORDER BY votes DESC,source_index,target_start_index,target_end_index,source_line_number LIMIT ?',params+[effective_limit]).fetchall()
        output.update(total_matching_links=count,truncated=count>len(rows))
        layout=compute_layout(options.get('width',1000),options.get('height',420),31102);output['layout']=layout
        genres=[dict(r)for r in connection.execute('SELECT g.*,MIN(b.first_index) AS first_index,MAX(b.last_index) AS last_index FROM VisualGenre g JOIN VisualBook b ON b.genre_id=g.genre_id GROUP BY g.genre_id ORDER BY g.ordinal')]
        output['genres']=genres
        indices={lo,hi}
        for row in rows:indices.update((row['source_index'],row['target_start_index'],row['target_end_index']))
        marks=','.join('?'for _ in indices)
        node_rows=connection.execute('SELECT r.*,b.genre_id,g.color,g.name AS genre_name FROM VisualReference r JOIN VisualBook b ON b.book_id=r.book_id JOIN VisualGenre g ON g.genre_id=b.genre_id WHERE r.global_index IN ('+marks+') ORDER BY r.global_index',list(indices)).fetchall()
        node_map={}
        for r in node_rows:
            x,y=point(layout,r['global_index']+.5)
            node={'id':r['global_index'],'reference':r['reference'],'book_id':r['book_id'],'chapter':r['chapter'],'verse':r['verse'],
              'global_index':r['global_index'],'genre_id':r['genre_id'],'genre_name':r['genre_name'],'color':r['color'],'x':x,'y':y,'is_focus':lo<=r['global_index']<=hi}
            node_map[r['global_index']]=node;output['nodes'].append(node)
        for r in rows:
            a=r['source_index'];b=r['target_start_index'];c=r['target_end_index']
            is_out=lo<=a<=hi;is_in=b<=hi and c>=lo
            actual_direction=direction if direction!='both'else('both'if is_out and is_in else'outgoing'if is_out else'incoming')
            target=r['target_start_reference']if b==c else r['target_start_reference']+'-'+r['target_end_reference']
            raw=bytes(r['raw_record'])
            record={'line_number':r['source_line_number'],'upstream_link_id':r['upstream_link_id'],'raw_source_reference':r['raw_source_reference'],'raw_target_reference':r['raw_target_reference'],
              'raw_record_utf8':raw.decode('utf-8'),'raw_record_sha256':r['raw_record_sha256'],'votes':r['votes']}
            proof={**provenance,'source_record':record}
            result={'source_reference':r['source_reference'],'target_reference':target,'direction':actual_direction,'relationship_type':'editorial_cross_reference',
              'dataset_source':proof,'weight':r['weight'],'votes':r['votes'],
              'evidence':{'kind':'pinned_upstream_tsv_record','normalizations':json.loads(r['remaps_json']),
                'source_assertion':'Editorial cross-reference ranked by community helpfulness votes; not proof of doctrine, textual equivalence or historical causation.',
                'raw_record_hash_verified':hashlib.sha256(raw).hexdigest()==r['raw_record_sha256']}}
            output['results'].append(result)
            output['edges'].append({'id':r['edge_id'],'source_node':a,'target_start_node':b,'target_end_node':c,'source_reference':r['source_reference'],'target_reference':target,
              'direction':actual_direction,'votes':r['votes'],'weight':r['weight'],'source_line_number':r['source_line_number'],
              'source_color':node_map[a]['color'],'target_color':node_map[b]['color'],
              'geometry':arc_geometry(layout,a,b,c),'dataset_source':proof})
        output['status']='VALID_RESULT'if rows else'NO_MATCH'
        output['message']='Source graph results; corpus text alignment remains separately verified.'if rows else'No source cross-reference matched these coordinate/direction/vote filters.'
        output['counts']={'returned_links':len(rows),'returned_nodes':len(output['nodes']),'matching_links':count,'source_graph_books':66,'source_graph_verses':31102}
        return output
    except Exception as exc:
        output.update(status='QUERY_ERROR',message=f'{type(exc).__name__}: {exc}',results=[],nodes=[],edges=[]);return output
    finally:
        if connection is not None:connection.close()
        output['elapsed_ms']=round((time.perf_counter()-started)*1000,3)

def main():
    parser=argparse.ArgumentParser(description='Engine A: normalized OSIS visual source-graph query')
    parser.add_argument('reference');parser.add_argument('--edition-id',default='eng-kjv');parser.add_argument('--direction',choices=['incoming','outgoing','both'],default='both');parser.add_argument('--limit',type=int,default=25);parser.add_argument('--min-votes',type=int)
    args=parser.parse_args();print(json.dumps(query(args.reference,args.edition_id,args.direction,args.limit,min_votes=args.min_votes),ensure_ascii=False,indent=2,allow_nan=False))

if __name__=='__main__':main()
