"""Portable read-only independent research engines and native-source text hub."""
from __future__ import annotations
import importlib,time
from . import reference as parser
from . import corpus_adapter as corpus
ENGINE_PATHS={'A':'visual','B':'aggregate','C':'phrase'}
def load_engine(engine):
    if engine not in ENGINE_PATHS:raise ValueError('UNKNOWN_ENGINE')
    return importlib.import_module('engines.'+ENGINE_PATHS[engine]+'.engine')
def editions(include_unavailable=False):return corpus.get_editions(include_unavailable)
def query(request,engine_loader=load_engine):
    started=time.perf_counter()
    if not isinstance(request,dict):return{'status':'QUERY_ERROR','error':'Request must be an object','engines':{}}
    user_reference=request.get('reference','');edition=request.get('edition_id','eng-kjv');choice=request.get('engine','all')
    response={'contract_version':'1.0','reference_input':user_reference,'requested_edition_id':edition,'engines':{},'source_semantics':'Source-curated cross-reference assertions; native edition texts are labeled separately; no theological or master-edition equivalence inferred.'}
    if not isinstance(user_reference,str)or not user_reference.strip()or len(user_reference)>1000:return dict(response,status='QUERY_ERROR',error='Reference must be a nonempty string of at most1000characters')
    limit,offset,direction=request.get('limit',25),request.get('offset',0),request.get('direction','both')
    if not isinstance(choice,str)or choice not in(*ENGINE_PATHS,'all')or isinstance(limit,bool)or not isinstance(limit,int)or not 1<=limit<=100 or isinstance(offset,bool)or not isinstance(offset,int)or not 0<=offset<=400 or offset+limit>500 or direction not in('incoming','outgoing','both'):
        return dict(response,status='QUERY_ERROR',error='Invalid engine/direction or bounded pagination')
    code=corpus.edition_code(edition)
    if not code:return dict(response,status='UNSUPPORTED_EDITION',error='Only native KJV,BSB,AOV source editions are included')
    native_edition='crossreferences:'+code
    response['edition_id']=native_edition;response['edition_alias_applied']=edition=='eng-kjv'
    try:parsed=parser.parse_reference(user_reference,request.get('language','en'))
    except Exception as error:return dict(response,status='QUERY_ERROR',error='Reference parser unavailable: '+type(error).__name__)
    response['parser']=parsed
    if parsed.get('status')!='VALID':return dict(response,status='REFERENCE_'+str(parsed.get('status','ERROR')))
    if len(parsed.get('normalized',[]))!=1:return dict(response,status='REFERENCE_AMBIGUOUS',error='Choose one contiguous reference or range')
    normalized=parsed['normalized'][0];response['reference']=normalized
    annotations={value for entry in parsed.get('indices',[])for value in entry.get('translations',[])if value}
    if annotations and not annotations.issubset({code}):return dict(response,status='EDITION_CONFLICT',error='Reference translation annotation conflicts with selected native edition',translation_annotations=sorted(annotations))
    mappings={}
    def resolve(ref):
        if ref not in mappings:
            try:mappings[ref]=corpus.resolve_reference(ref,native_edition)
            except Exception as error:mappings[ref]={'mapping_status':'UNMAPPED','reference':ref,'edition_id':native_edition,'units':[],'reason':'Native text unavailable: '+type(error).__name__}
        return mappings[ref]
    source=resolve(normalized);response['source_mapping']=source
    selected=list(ENGINE_PATHS)if choice=='all'else[choice]
    for engine_id in selected:
        try:
            if engine_id in('A','B')and code!='KJV':
                answer={'engine_id':engine_id,'status':'UNSUPPORTED_EDITION','reference':normalized,'edition_id':native_edition,'results':[],'reason':'This graph has only a KJV66coordinate profile; no BSB/AOV alignment is invented'}
            else:
                options={key:request[key]for key in('source','book','chapter','min_votes')if key in request and request[key]is not None}
                cap=100 if engine_id=='A' else 500
                selector='eng-kjv'if engine_id in('A','B')else native_edition
                answer=engine_loader(engine_id).query(normalized,selector,direction,min(cap,offset+limit+1),**options)
                complete=answer.get('results',[]);answer['results']=complete[offset:offset+limit]
                answer['pagination']={'offset':offset,'limit':limit,'more_in_bounded_query':offset+limit<cap and(len(complete)>offset+limit or bool(answer.get('truncated'))),'query_cap':cap,'cap_reached':offset+limit>=cap}
                answer['edition_id']=native_edition
                if engine_id in('A','B'):
                    answer['mapping']={'status':'SOURCE_COORDINATE_PROFILE_ONLY','coordinate_system':'KJV66','text_source':native_edition,'text_alignment_status':'NOT_ASSERTED_BETWEEN_INDEPENDENT_SOURCES','no_master_corpus':True}
                if engine_id=='A':
                    lines={row['dataset_source']['source_record']['line_number']for row in answer['results']}
                    answer['edges']=[edge for edge in answer.get('edges',[])if edge['source_line_number']in lines]
                    ids={edge[key]for edge in answer['edges']for key in('source_node','target_start_node','target_end_node')}
                    answer['nodes']=[node for node in answer.get('nodes',[])if node['id']in ids or node.get('is_focus')]
            for row in answer.get('results',[]):
                peer=row['source_reference']if row.get('direction')=='incoming'else row['target_reference']
                row.update(peer_reference=peer,source_edition=native_edition,reference_system='Source-specific coordinate profile; native text is labeled, not a certified cross-edition mapping',mapping=resolve(peer),validation_status='SOURCE_ASSERTION_PRESERVED')
            answer['source_mapping_status']=source['mapping_status'];response['engines'][engine_id]=answer
        except Exception as error:response['engines'][engine_id]={'engine_id':engine_id,'status':'QUERY_ERROR','reference':normalized,'edition_id':native_edition,'results':[],'error':'Engine failed independently: '+type(error).__name__}
    response['status']='VALID_RESULT'if any(engine['status']=='VALID_RESULT'for engine in response['engines'].values())else'NO_VALID_ENGINE_RESULT'
    peers={key:{row['peer_reference']for row in engine.get('results',[])}for key,engine in response['engines'].items()}
    response['comparison']={'scope':'Bounded returned assertions only; source grain and provenance remain distinct','returned_counts':{key:len(engine.get('results',[]))for key,engine in response['engines'].items()},'unique_peer_counts':{key:len(values)for key,values in peers.items()},'shared_peer_references':sorted(set.intersection(*peers.values()))if peers and all(peers.values())else[],'peer_union_count':len(set.union(*peers.values()))if peers else 0}
    response['elapsed_ms']=(time.perf_counter()-started)*1000
    return response
