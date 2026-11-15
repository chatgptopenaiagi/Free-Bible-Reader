"""Public native-source reader; no private master corpus, SQL or UUID mapping."""
from __future__ import annotations
import contextlib,hashlib,importlib,json,re
from . import reference
SUPPORTED={'KJV':('King James Version','English'),'BSB':('Berean Standard Bible','English'),'AOV':('Afrikaanse Ou Vertaling','Afrikaans')}
def edition_code(value):
    if value=='eng-kjv':return'KJV'
    if not isinstance(value,str):return None
    code=value.removeprefix('crossreferences:').upper()
    return code if code in SUPPORTED else None
def get_editions(include_unavailable=False):
    return[{'edition_id':'crossreferences:'+code,'source_version_key':'crossreferences:'+code,'name':label,'local_package_available':True,'language_source_label':language,'mapping_policy':'NATIVE_SOURCE_NOT_MASTER_EDITION_EQUIVALENCE'}for code,(label,language)in SUPPORTED.items()]
def native_engine():return importlib.import_module('engines.phrase.engine')
def _unit(reference_value,code,native):
    ids=native['source'].get('source_fragment_ids',[]);book,chapter,verse=reference.split_reference(reference_value)[0]
    return{'text':native['text'],'source_record_id':ids[0]if len(ids)==1 else None,'source_fragment_ids':ids,'ref':None,
        'native_locator':{'reference':reference_value,'edition':'crossreferences:'+code,'book':book,'chapter':chapter,'verse':verse,'source_fragment_ids':ids},
        'raw_utf8_sha256':hashlib.sha256(native['text'].encode('utf-8')).hexdigest(),'hash_scope':'reconstructed_native_source_text','source':native['source'],'is_whole_original_unit':True,'offset_space':'native_source_edition'}
def resolve_reference(reference_value,edition_id='eng-kjv',**options):
    code=edition_code(edition_id)
    answer={'reference':reference_value,'requested_edition_id':edition_id,'edition_id':'crossreferences:'+code if code else None,'source_version_key':'crossreferences:'+code if code else None,'mapping_status':'UNSUPPORTED','units':[],'evidence':[],'engine_compatible':False,'reason':'Unsupported public native source edition'}
    if not code:return answer
    engine=native_engine();points=[reference_value]
    if '-'in reference_value:
        try:
            start,end=reference.split_reference(reference_value)
            if start[0]!=end[0]:raise ValueError('Cross-book native ranges are retained without inferred intervening canon')
            with contextlib.closing(engine.connect())as db:
                lower=start[1]*1000000+start[2];upper=end[1]*1000000+end[2]
                points=[row[0]for row in db.execute('SELECT reference FROM PhraseVerse WHERE edition_code=? AND book_id=? AND chapter*1000000+verse BETWEEN ? AND ? ORDER BY chapter,verse LIMIT 501',(code,engine.BOOK_INDEX.get(start[0],-1),lower,upper))]
            if len(points)>500:raise ValueError('Native range exceeds500units')
        except Exception:
            answer.update(mapping_status='UNMAPPED',reason='Native range cannot be resolved within its bounded source coordinates');return answer
    missing=[]
    for point in points:
        native=engine.get_native_verse(point,code)
        if native.get('status')!='VALID_RESULT'or native.get('text')is None:missing.append({'reference':point,'status':native.get('status'),'reason':native.get('reason')});continue
        answer['units'].append(_unit(point,code,native));answer['evidence'].append({'reference':point,'type':'native_source_edition','source':native['source'],'no_master_mapping':True})
    if answer['units']:
        answer.update(mapping_status='NATIVE_SOURCE',reason='Text belongs to this explicitly labeled source edition; graph-coordinate compatibility is separately qualified, never a master-corpus EXACT claim',native_source_available=True)
    else:answer.update(mapping_status='UNMAPPED',reason='No unambiguous native source text for the requested reference')
    answer['missing_native_members']=missing
    answer['coverage']={'returned_whole_native_units':len(answer['units']),'fragmentation_applied':False,'requested_range':'-'in reference_value}
    return answer
