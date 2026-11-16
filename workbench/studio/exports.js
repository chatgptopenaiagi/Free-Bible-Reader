import {nativeChapters} from '/reader-state.js';
import {selectedOrCurrent,verseBlock} from './selection.js';
import {selectionBlocks,collectionSelection} from './workspace.js';

export async function createExporter(common,{reader,getSelection=()=>null,getSearchSelection=()=>null,getCollectionSelection=()=>null}={}){
  await common.namespace('export');
  const {node,text,button,field,options,dialog,request,t}=common;
  const modal=dialog('export.title',{id:'studio-export',wide:true});
  const scopes=['selection','currentverse','currentchapter','multichapter','searchresults','comparison','collection','notes'];
  let snapshot=null,current=null,catalog=null,selectedVerse=null,searchSnapshot=null,sequence=0,controller=null,capabilities={},lastArtifact=null;
  const scope=field('export.scope','select'),format=field('export.format','select'),title=field('export.name'),font=field('export.font','select'),size=field('export.fontSize','number',12),paper=field('export.paper','select'),alignment=field('export.alignment','select');
  const start=field('export.start','select'),end=field('export.end','select'),collection=field('export.collection','select');
  const header=field('export.header'),footer=field('export.footer'),note=field('export.extraNote','textarea');
  const margins=Object.fromEntries(['top','right','bottom','left'].map(key=>[key,field('export.margin'+key[0].toUpperCase()+key.slice(1),'number',20)]));
  const pages=field('export.pageNumbers','checkbox'),notes=field('export.includeNotes','checkbox'),refs=field('export.includeReferences','checkbox'),sources=field('export.includeSources','checkbox');
  for(const value of [pages,notes,refs,sources])value.input.checked=true;
  const fields={scope,format,title,font,size,paper,alignment,start,end,collection,header,footer,note,pages,notes,refs,sources};
  for(const[key,value]of Object.entries(fields))value.input.id='export-'+key;
  size.input.min=8;size.input.max=24;size.input.step=1;note.input.rows=3;
  for(const[key,value]of Object.entries(margins)){value.input.id='export-margin-'+key;value.input.min=10;value.input.max=50;}
  const grid=node('div',null,'studio-form-grid');grid.append(scope.label,format.label,title.label,font.label,size.label,paper.label,alignment.label,start.label,end.label,collection.label,...Object.values(margins).map(x=>x.label),header.label,footer.label,pages.label,notes.label,refs.label,sources.label,note.label);
  const preview=node('div',null,'studio-export-preview');preview.id='export-preview';
  const status=node('p',null,'meta');status.id='export-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const result=node('div',null,'studio-actions');result.id='export-result';
  const history=node('div',null,'studio-list');history.id='export-history';
  modal.body.append(text('p','export.sourceNotice','notice'),grid,text('p','export.fontNotice','meta'),status,preview,result,text('h3','export.history'),history);
  const create=button('export.create',generate);create.id='export-create';
  const cancel=button('common.cancel',()=>{controller?.abort();modal.close();});modal.footer.append(create,cancel);
  function controls(){
    options(scope.input,scopes.map(key=>[key,t('export.'+key)]),scope.input.value||'selection');
    options(format.input,[['pdf','PDF'],['docx','DOCX']],format.input.value||'pdf');
    options(font.input,[['serif',t('export.serif')],['sans',t('export.sans')],['mono',t('export.mono')]],font.input.value||'serif');
    options(paper.input,[['A4','A4'],['Letter','Letter']],paper.input.value||'A4');
    options(alignment.input,['left','center','right','justify'].map(key=>[key,t('export.'+key)]),alignment.input.value||'left');
  }
  function fail(error){console.error('[Export]',error);common.notify(t(error?.code==='DOCUMENT_TOO_LARGE'?'export.tooLarge':error?.name==='AbortError'?'common.cancelled':'export.failed'),true);}
  function availableChapters(){const book=catalog?.books?.find(value=>value.id===current?.book);return book?nativeChapters(book):[current?.chapter].filter(value=>value!=null);}
  async function gather(){
    const selected=scope.input.value;let blocks=[],attached=[];
    if(selected==='selection'){blocks=(snapshot?.blocks?.some(x=>x.kind==='correction')?structuredClone(snapshot.blocks):selectionBlocks(snapshot));attached=snapshot?.notes||[];}
    else if(selected==='currentverse'){blocks=selectionBlocks(selectedOrCurrent({getCurrent:()=>current,getSelection:()=>selectedVerse}));}
    else if(selected==='currentchapter'){blocks=current?.verses?.map(value=>verseBlock(current,value))||[];}
    else if(selected==='multichapter'){
      const chapters=availableChapters(),first=chapters.findIndex(value=>String(value)===start.input.value),last=chapters.findIndex(value=>String(value)===end.input.value);
      if(first<0||last<first||last-first>=20)throw Error(t('export.chapterLimit'));
      for(const chapter of chapters.slice(first,last+1)){const value=String(chapter)===String(current.chapter)?current:await request('/api/reader/chapter?edition='+encodeURIComponent(current.edition.id)+'&book='+encodeURIComponent(current.book)+'&chapter='+encodeURIComponent(chapter));blocks.push(...value.verses.map(verse=>verseBlock({...value,book:typeof value.book==='object'?value.book.id:value.book},verse)));if(blocks.length>1000)throw Error(t('export.tooLarge'));}
    }else if(selected==='searchresults'){
      const found=searchSnapshot;blocks=selectionBlocks(found?.results||found);if(!blocks.length)throw Error(t('export.noSearch'));
    }else if(selected==='comparison'){
      const chosen=selectedVerse||current?.verses?.[0];if(!chosen)throw Error(t('export.noSelection'));
      for(const edition of [...new Set([current.edition.id,'web','kjv','bsb'])]){
        try{const chapter=edition===current.edition.id?current:await request('/api/reader/chapter?edition='+encodeURIComponent(edition)+'&book='+encodeURIComponent(current.book)+'&chapter='+encodeURIComponent(current.chapter));const verse=chapter.verses.find(value=>String(value.number)===String(chosen.number));
          if(verse)blocks.push(verseBlock({...chapter,book:typeof chapter.book==='object'?chapter.book.id:chapter.book},verse));
          else blocks.push({text:t('export.missingNative',{edition,reference:chosen.reference}),kind:'note',label:edition});
        }catch{blocks.push({text:t('export.missingNative',{edition,reference:chosen.reference}),kind:'note',label:edition});}
      }
      blocks.push({text:t('export.comparisonNotice'),kind:'note',label:t('export.comparison')});
    }else if(selected==='collection'){
      let value=collection.input.value?collectionSelection(await request('item?id='+encodeURIComponent(collection.input.value))):await getCollectionSelection?.();
      if(!value&&snapshot?.shape==='collection')value=snapshot;
      if(!value)throw Error(t('export.noCollection'));blocks=value.blocks||[];attached=value.notes||[];
    }else if(selected==='notes'){
      if(snapshot?.notes?.length)attached=snapshot.notes;
      else{const value=await request('workspace?type=notes&limit=200');if(value.total>200)throw Error(t('export.notesLimit'));attached=value.items.map(item=>({text:item.body,reference:item.source?.reference||item.title||'',label:item.source?.edition_name||'',source:item.source||null}));}
      if(!attached.length)throw Error(t('export.noNotes'));
    }
    if(note.input.value)attached=[...attached,{text:note.input.value}];
    if(!blocks.length&&!attached.length)throw Error(t('export.noSelection'));
    return{blocks,notes:attached};
  }
  function toggle(){const multi=scope.input.value==='multichapter';start.label.hidden=end.label.hidden=!multi;collection.label.hidden=scope.input.value!=='collection';}
  async function showPreview(){const token=++sequence;toggle();try{const value=await gather();if(token!==sequence)return;preview.replaceChildren();status.textContent=t('export.previewCount',{count:value.blocks.length,notes:value.notes.length});for(const block of value.blocks.slice(0,5)){const part=node('section',null,'studio-source');part.append(node('strong',[block.edition_name||block.edition_id||block.label,block.reference].filter(Boolean).join(' · ')),node('p',block.selected_text??block.text));preview.append(part);}if(value.blocks.length>5)preview.append(text('p','export.previewLimited','meta'));}catch(error){if(token===sequence){preview.replaceChildren();status.textContent=error.message;}}}
  function settings(){return{font:font.input.value,font_size:Number(size.input.value),paper:paper.input.value,alignment:alignment.input.value,margins_mm:Object.fromEntries(Object.entries(margins).map(([key,value])=>[key,Number(value.input.value)])),header:header.input.value,footer:footer.input.value,page_numbers:pages.input.checked,include_notes:notes.input.checked,include_references:refs.input.checked,include_source_labels:sources.input.checked};}
  async function showArtifact(artifact){
    lastArtifact=artifact;result.replaceChildren();result.append(node('strong',artifact.filename),node('span',t('export.ready',{bytes:artifact.bytes}),'meta'));
    const nativeSave=button('export.saveAs',async()=>{nativeSave.disabled=true;try{const saved=await request('export/save',{id:artifact.artifact_id,language:common.language()});common.notify(t(saved.cancelled?'export.saveCancelled':'export.saved'));}catch(error){fail(error);}finally{nativeSave.disabled=false;}});nativeSave.id='export-native-save';
    nativeSave.disabled=capabilities.native_dialogs!==true;
    const download=node('a',t('export.download'),'button');download.id='export-download';download.href='/api/studio/document/file?id='+encodeURIComponent(artifact.artifact_id);download.download=artifact.filename;
    result.append(nativeSave,download);if(!capabilities.native_dialogs)result.append(text('p','export.nativeUnavailable','notice'));
  }
  async function loadHistory(){
    const value=await request('documents'),items=value.items||value.artifacts?.items||value.artifacts||[];history.replaceChildren();
    if(!items.length){history.append(text('p','export.noHistory','meta'));return;}
    for(const artifact of items){const card=node('article',null,'studio-card');card.append(node('strong',artifact.title||artifact.filename),node('small',artifact.created_at,'meta'),button('export.openGenerated',()=>showArtifact(artifact)));history.append(card);}
  }
  async function generate(){
    create.disabled=true;controller=new AbortController();result.replaceChildren();lastArtifact=null;status.textContent=t('export.generating');
    try{const value=await gather(),shape={currentverse:'verses',currentchapter:'chapter',searchresults:'searchcomparison',comparison:'searchcomparison'}[scope.input.value]||scope.input.value;
      const job=await request('export',{format:format.input.value,title:title.input.value||t('export.defaultTitle',{reference:current?.book||''}),shape,blocks:value.blocks,notes:value.notes,settings:settings()});
      const artifact=await common.waitJob(job,{signal:controller.signal,onProgress:()=>status.textContent=t('export.generating')});await showArtifact(artifact);status.textContent=t('export.complete');await loadHistory();
    }catch(error){fail(error);status.textContent=t('export.failed');}finally{create.disabled=false;controller=null;}
  }
  for(const value of [scope,start,end,collection])value.input.addEventListener('change',showPreview);
  async function open(selection=null,outputFormat=null){
    snapshot=structuredClone(selection||getSelection?.()||selectedOrCurrent(reader));current=reader.getCurrent();const anchor=snapshot?.blocks?.[0];
    selectedVerse=current?.verses?.find(value=>value.reference===anchor?.reference)||reader.getSelection();searchSnapshot=structuredClone(await getSearchSelection?.()||null);catalog=reader.getCatalog?.();controls();
    scope.input.value=snapshot?.shape==='collection'?'collection':snapshot?.shape==='notes'?'notes':snapshot?.blocks?.length||snapshot?.text?'selection':'currentverse';if(outputFormat)format.input.value=outputFormat;
    title.input.value=snapshot?.title||t('export.defaultTitle',{reference:snapshot?.reference||current?.book||''});
    const chapters=availableChapters();options(start.input,chapters.map(value=>[value,String(value)]),current?.chapter);options(end.input,chapters.map(value=>[value,String(value)]),current?.chapter);
    capabilities=await request('capabilities').catch(()=>({native_dialogs:false}));
    const collections=await request('workspace?type=collections&limit=200').catch(()=>({items:[]}));options(collection.input,collections.items.map(item=>[item.id,item.title||item.id]),snapshot?.collection_id||collections.items[0]?.id);
    result.replaceChildren();status.textContent='';modal.open();await showPreview();await loadHistory();
  }
  common.subscribe(()=>{controls();toggle();});controls();toggle();
  return{open,getLastArtifact:()=>lastArtifact};
}
