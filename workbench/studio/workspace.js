import {selectedOrCurrent} from './selection.js';
import {contrastRatio} from '/ui-core/themes/contrast.js';

/** Normalize captured text or a whole search-result verse without changing text. */
export function selectionBlocks(selection){
  if(!selection)return[];
  const values=Array.isArray(selection)?selection:Array.isArray(selection.blocks)?selection.blocks:[selection];
  return values.map(value=>{
    const text=String(value.selected_text??value.text??'');
    const block={text,selected_text:text,edition_id:value.edition_id??value.edition,
      edition_name:value.edition_name,language:value.language,book:value.book,
      chapter:value.chapter,verse_start:value.verse_start??value.verse??value.number,
      verse_end:value.verse_end??value.verse??value.number,label:value.label??String(value.verse??value.number??''),
      reference:value.reference,sourceTextSha256:value.sourceTextSha256,
      origin:value.origin??value.source,license:value.license,source_record_id:value.source_record_id,
      original_text:value.original_text??value.source_text,
      start_utf16:value.start_utf16??value.start,end_utf16:value.end_utf16??value.end};
    if(block.start_utf16==null&&block.original_text===text){block.start_utf16=0;block.end_utf16=text.length;}
    return Object.fromEntries(Object.entries(block).filter(([,value])=>value!==undefined));
  }).filter(block=>block.text.length);
}

export function collectionSelection(item){
  const blocks=[],notes=[];
  for(const member of item.members||[]){const value=member.snapshot,sources=value.blocks?.length?value.blocks:[value.source].filter(Boolean);
    if(value.type==='source_blocks')blocks.push(...value.blocks);
    else if(value.type==='corrections')blocks.push({text:value.corrected_text||value.body||'',kind:'correction',reference:sources[0]?.reference||'',label:sources[0]?.edition_name||'',source:sources[0]||null});
    else{blocks.push(...sources);if(value.body)notes.push({text:value.body,reference:sources[0]?.reference||value.title||''});}
  }
  return{shape:'collection',collection_id:item.id,title:item.title,blocks,notes,text:blocks.map(x=>x.selected_text??x.text??'').join('\n')};
}

export async function createWorkspaceStudio(common,{reader,getSelection=()=>null,onExport=()=>{}}={}){
  await common.namespace('workspace');
  const {node,text,button,field,options,dialog,request,t}=common;
  const types=['notes','highlights','bookmarks','collections','corrections','savedsearch','history'];
  const main=dialog('workspace.title',{id:'studio-workspace',wide:true});
  const editor=dialog('workspace.editor',{id:'studio-item-editor',wide:true});
  const picker=dialog('workspace.collectionPick',{id:'studio-collection-picker'});
  const toolbar=node('div',null,'studio-actions'),filter=field('workspace.type','select'),query=field('workspace.search');
  filter.input.id='workspace-type';query.input.id='workspace-query';
  const list=node('div',null,'studio-list');list.id='workspace-items';
  const count=node('p',null,'meta');count.id='workspace-count';
  let activeType='notes',offset=0,total=0,activeItem=null,rows=[],sequence=0,searchTimer;
  toolbar.append(filter.label,query.label,button('workspace.new',()=>edit(null)),button('workspace.refresh',()=>reload()));
  main.body.append(text('p','workspace.private','meta'),toolbar,count,list);
  const more=button('workspace.more',()=>reload(true));more.id='workspace-more';main.footer.append(more);
  function fail(error){console.error('[Workspace]',error);common.notify(t(error.code==='IMMUTABLE_SOURCE'?'workspace.immutable':'workspace.failed'),true);}
  function snapshot(){return structuredClone(getSelection?.()||selectedOrCurrent(reader));}
  function sourceText(item){return(item.blocks?.length?item.blocks:[item.source].filter(Boolean)).map(block=>block.selected_text??block.text??'').join('\n');}
  function renderTypes(){options(filter.input,types.map(value=>[value,t('workspace.'+value)]),activeType);}
  function showSource(container,blocks){
    container.replaceChildren();if(!blocks.length){container.append(text('p','workspace.noSource','meta'));return;}
    for(const block of blocks){const section=node('section',null,'studio-source');section.append(node('strong',[block.edition_name||block.edition_id,block.reference||block.label].filter(Boolean).join(' · ')),node('p',block.selected_text??block.text??''));container.append(section);}
  }
  function renderRows(){
    list.replaceChildren();count.textContent=t('workspace.count',{count:total});more.hidden=rows.length>=total;
    if(!rows.length){list.append(text('p','workspace.empty'));return;}
    for(const item of rows){const card=node('article',null,'studio-card');card.dataset.itemId=item.id;
      card.append(node('h3',item.title||item.source?.reference||t('workspace.untitled')),node('p',item.body||item.corrected_text||sourceText(item),'studio-excerpt'),node('small',item.updated_at,'meta'));
      const actions=node('div',null,'studio-actions');actions.append(button('workspace.edit',()=>edit(item)),button('workspace.export',()=>emitExport(item)),button('workspace.delete',async()=>{await request('workspace/delete',{id:item.id,revision:item.revision});common.notify(t('workspace.deleted'));await reload();await refreshAnnotations();}));
      if(item.type==='savedsearch'||item.type==='history'&&item.data?.query)actions.prepend(button('workspace.openSearch',()=>{main.close();document.dispatchEvent(new CustomEvent('studio-open-saved-search',{detail:structuredClone(item.data)}));}));
      if(item.source?.edition_id&&item.source.book&&item.source.chapter!=null)actions.prepend(button('workspace.openPassage',async()=>{main.close();const verse=item.source.verse_start??item.source.verse??null;await reader.open({edition:item.source.edition_id,book:item.source.book,chapter:item.source.chapter,verse,selectedVerse:verse});}));
      if(item.type==='collections')actions.prepend(button('workspace.members',()=>edit(item)));
      card.append(actions);list.append(card);
    }
  }
  async function reload(append=false){
    const token=++sequence;if(!append){offset=0;rows=[];}else offset=rows.length;
    try{const value=await request('workspace?type='+encodeURIComponent(activeType)+'&query='+encodeURIComponent(query.input.value)+'&limit=50&offset='+offset);if(token!==sequence)return;rows.push(...value.items);total=value.total;renderRows();}catch(error){fail(error);}
  }
  async function open(type='notes'){activeType=types.includes(type)?type:'notes';renderTypes();main.open();await reload();}
  filter.input.addEventListener('change',()=>{activeType=filter.input.value;reload();});
  query.input.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>reload(),180);});

  async function emitExport(item){
    const full=item.type==='collections'?await request('item?id='+encodeURIComponent(item.id)):item;
    const selection=full.type==='collections'?collectionSelection(full):{shape:full.type==='notes'?'notes':'selection',title:full.title,blocks:full.type==='corrections'?[{text:full.corrected_text,kind:'correction',reference:full.source?.reference||'',source:full.source}]:full.blocks?.length?full.blocks:[full.source].filter(Boolean),notes:full.body?[{text:full.body,reference:full.source?.reference||full.title||'',label:full.source?.edition_name||full.source?.edition_id||'',source:full.source||null}]:[]};
    main.close();editor.close();onExport(selection);
  }
  async function edit(item,selected=null,type=activeType){
    type=item?.type||type;
    if(!item&&!selected&&['highlights','bookmarks','corrections'].includes(type))selected=snapshot();
    activeItem=item?await request('item?id='+encodeURIComponent(item.id)):null;
    const blocks=activeItem?.blocks?.length?activeItem.blocks:activeItem?.source?[activeItem.source]:selectionBlocks(selected);
    editor.body.replaceChildren();editor.footer.replaceChildren();
    const heading=field('workspace.name','text',activeItem?.title||''),body=field('workspace.body','textarea',activeItem?.body||''),tags=field('workspace.tags','text',(activeItem?.tags||[]).join(', '));
    heading.input.id='workspace-item-title';body.input.id='workspace-item-body';body.input.rows=5;tags.input.id='workspace-item-tags';
    const color=field('workspace.color','color',/^#[0-9a-f]{6}$/i.test(activeItem?.color||'')?activeItem.color:'#fff0a6');color.input.id='workspace-item-color';
    const corrected=field('workspace.corrected','textarea',activeItem?.corrected_text??blocks.map(x=>x.selected_text??x.text??'').join('\n'));corrected.input.id='workspace-item-correction';corrected.input.rows=6;
    const source=node('div');showSource(source,blocks);
    editor.body.append(heading.label,body.label,tags.label);
    const savedQuery=field('workspace.savedQuery','text',activeItem?.data?.query||''),savedEdition=field('workspace.savedEdition','text',activeItem?.data?.edition||reader?.getCurrent()?.edition.id||'web');
    savedQuery.input.id='workspace-saved-query';savedEdition.input.id='workspace-saved-edition';
    if(type==='savedsearch')editor.body.append(savedQuery.label,savedEdition.label);
    if(type==='highlights')editor.body.append(color.label);
    if(type==='corrections')editor.body.append(text('p','workspace.correctionNotice','notice'),corrected.label);
    editor.body.append(text('h3','workspace.original'),source);
    if(type==='collections'&&activeItem){
      const members=node('div',null,'studio-list');members.id='workspace-collection-members';
      for(const member of activeItem.members||[]){const card=node('article',null,'studio-card');card.append(node('p',member.snapshot.title||member.snapshot.body||member.snapshot.blocks?.map(x=>x.reference).join(', ')||member.snapshot.source?.reference||t('workspace.untitled')),button('workspace.remove',async()=>{await request('collection/remove',{id:activeItem.id,member_id:member.id});await edit(activeItem,null,'collections');await reload();}));members.append(card);}
      editor.body.append(text('h3','workspace.members'),members,button('workspace.addCurrent',()=>saveCollection(snapshot(),activeItem.id)));
      editor.footer.append(button('workspace.export',()=>emitExport(activeItem)));
    }
    const save=button('workspace.save',async()=>{
      save.disabled=true;
      try{
        const patch={title:heading.input.value,body:body.input.value,tags:tags.input.value.split(',').map(x=>x.trim()).filter(Boolean)};
        if(type==='highlights')patch.color=color.input.value;
        if(type==='corrections')patch.corrected_text=corrected.input.value;
        if(type==='savedsearch'){
          if(!savedQuery.input.value.trim()){common.notify(t('workspace.queryRequired'),true);return;}
          patch.data={...(activeItem?.data||{}),query:savedQuery.input.value,edition:savedEdition.input.value};
        }
        const result=activeItem?await request('workspace/update',{id:activeItem.id,patch,revision:activeItem.revision}):await request('workspace/create',{type,...patch,source:blocks[0]||null,blocks});
        common.notify(t('workspace.saved'));editor.close();await reload();await refreshAnnotations();return result;
      }catch(error){fail(error);}finally{save.disabled=false;}
    });save.id='workspace-item-save';editor.footer.append(save,button('common.cancel',()=>editor.close()));editor.open();heading.input.focus();
  }
  async function saveSelection(selection,type='notes'){
    const chosen=selection||snapshot(),blocks=selectionBlocks(chosen);
    if(!blocks.length){common.notify(t('workspace.noSelection'),true);return;}
    if(type==='bookmarks'){
      try{const item=await request('workspace/create',{type,title:blocks[0].reference||'',body:'',source:blocks[0],blocks});common.notify(t('workspace.saved'));await refreshAnnotations();return item;}catch(error){fail(error);}
    }else await edit(null,{blocks},types.includes(type)?type:'notes');
  }
  async function saveCollection(selection,id=null){
    const chosen=selection||snapshot(),blocks=selectionBlocks(chosen);
    if(!blocks.length){common.notify(t('workspace.noSelection'),true);return;}
    const collections=await request('workspace?type=collections&limit=200');picker.body.replaceChildren();picker.footer.replaceChildren();
    const choice=field('workspace.collection','select'),name=field('workspace.collectionName');choice.input.id='workspace-collection-choice';name.input.id='workspace-collection-name';
    options(choice.input,[['new',t('workspace.newCollection')],...collections.items.map(x=>[x.id,x.title||t('workspace.untitled')])],id||collections.items[0]?.id||'new');
    const toggle=()=>name.label.hidden=choice.input.value!=='new';choice.input.addEventListener('change',toggle);toggle();
    const preview=node('div');showSource(preview,blocks);picker.body.append(choice.label,name.label,preview);
    const add=button('workspace.add',async()=>{add.disabled=true;try{let target=choice.input.value;if(target==='new')target=(await request('workspace/create',{type:'collections',title:name.input.value||t('workspace.newCollection')})).id;await request('collection/add',{id:target,item:{blocks}});common.notify(t('workspace.saved'));picker.close();if(activeItem?.id===target)await edit(activeItem,null,'collections');await reload();}catch(error){fail(error);}finally{add.disabled=false;}});add.id='workspace-collection-add';picker.footer.append(add,button('common.cancel',()=>picker.close()));picker.open();
  }

  let annotationTimer,annotationSequence=0,annotationKey='',cachedAnnotations=[],lastHistoryKey='';
  const highlightNames=new Set();
  async function refreshAnnotations(force=true){
    const current=reader?.getCurrent();if(!current)return;
    const key=JSON.stringify([current.edition.id,current.book,current.chapter]),token=++annotationSequence;
    if(force||key!==annotationKey){
      const found=[];
      for(const type of ['notes','highlights','bookmarks']){
        let offset=0;
        do{const result=await request('workspace?type='+type+'&limit=200&offset='+offset+'&edition_id='+encodeURIComponent(current.edition.id)+'&book='+encodeURIComponent(current.book)+'&chapter='+encodeURIComponent(current.chapter)).catch(()=>null);if(!result||token!==annotationSequence)return;found.push(...result.items);offset+=result.items.length;if(!result.items.length||offset>=result.total)break;}while(true);
      }
      annotationKey=key;cachedAnnotations=found;
    }
    const now=reader.getCurrent();if(!now||JSON.stringify([now.edition.id,now.book,now.chapter])!==key||token!==annotationSequence)return;
    document.querySelectorAll('.studio-annotation-badge').forEach(value=>value.remove());
    if(globalThis.CSS?.highlights)for(const key of highlightNames)CSS.highlights.delete(key);highlightNames.clear();
    const ranges=new Map(),colors={yellow:'#fff0a6',green:'#c9efcf',blue:'#cfe6ff',pink:'#f9d1e5',purple:'#e4d5ff',orange:'#ffdfb5'};
    for(const item of cachedAnnotations){if(!['notes','highlights','bookmarks'].includes(item.type))continue;
      for(const block of item.blocks?.length?item.blocks:[item.source].filter(Boolean)){
        if(block.edition_id!==current.edition.id)continue;
        const paragraph=[...document.querySelectorAll('#reader-content .scripture-verse')].find(value=>value.dataset.reference===block.reference);const span=paragraph?.querySelector('[data-source-data]');if(!span)continue;
        if(block.original_text&&span.textContent!==block.original_text)continue;
        const badge=button('workspace.annotation',()=>edit(item), 'studio-annotation-badge');badge.textContent=item.type==='bookmarks'?'★':item.type==='highlights'?'●':'✎';badge.removeAttribute('data-studio-key');badge.setAttribute('aria-label',t('workspace.annotation'));paragraph.append(badge);
        if(item.type==='highlights'&&globalThis.CSS?.highlights&&globalThis.Highlight&&span.firstChild?.nodeType===Node.TEXT_NODE){
          const start=block.start_utf16??0,end=block.end_utf16??span.textContent.length;if(start<0||end<start||end>span.textContent.length)continue;
          if(span.textContent.slice(start,end)!==(block.selected_text??block.text))continue;
          const color=/^#[0-9a-f]{6}$/i.test(item.color||'')?item.color:colors[item.color]||colors.yellow,name='fbr-personal-'+color.slice(1);
          const range=document.createRange();range.setStart(span.firstChild,start);range.setEnd(span.firstChild,end);if(!ranges.has(name))ranges.set(name,{color,ranges:[]});ranges.get(name).ranges.push(range);
        }
      }
    }
    let style=document.getElementById('studio-annotation-style');if(!style){style=node('style');style.id='studio-annotation-style';document.head.append(style);}style.textContent=[...ranges].map(([name,value])=>`::highlight(${name}){background:${value.color};color:${contrastRatio(value.color,'#000000')>=contrastRatio(value.color,'#ffffff')?'#000000':'#ffffff'}}`).join('\n');
    for(const[name,value]of ranges){CSS.highlights.set(name,new Highlight(...value.ranges));highlightNames.add(name);}
    if(key!==lastHistoryKey){lastHistoryKey=key;const verse=current.verses?.[0];if(verse){const source={edition_id:current.edition.id,edition_name:current.edition.name,book:current.book,chapter:current.chapter,verse_start:verse.nativeVerseStart??verse.number,verse_end:verse.nativeVerseEnd??verse.number,reference:verse.reference,label:String(verse.label??verse.number),selected_text:verse.text};request('workspace/create',{type:'history',title:current.book+' '+current.chapter,source,data:{action:'opened_chapter',verse_count:current.verses.length}}).catch(()=>{});}}
  }
  const article=document.getElementById('reader-content');if(article)new MutationObserver(()=>{clearTimeout(annotationTimer);annotationTimer=setTimeout(()=>refreshAnnotations(false),150);}).observe(article,{childList:true});
  common.subscribe(()=>{renderTypes();renderRows();});renderTypes();refreshAnnotations();
  return{open,saveSelection,saveCollection,refresh:reload,refreshAnnotations,async getCollectionSelection(){if(activeItem?.type!=='collections')return null;return collectionSelection(await request('item?id='+encodeURIComponent(activeItem.id)));}};
}
