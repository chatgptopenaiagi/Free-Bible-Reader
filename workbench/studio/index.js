import {createCommon,node} from './common.js';
import {captureSelection,selectedOrCurrent,verseBlock} from './selection.js';
import {createLibrary} from './library.js';
import {createAdvancedSearch} from './search.js';
import {createWorkspaceStudio} from './workspace.js';
import {createExporter} from './exports.js';
import {createAudioStudio} from './audio.js';

export async function createStudio({reader,core,translator,layout,research}){
  const common=createCommon({preferences:core.preferences});await Promise.all(['core','audio','library','search','workspace','export'].map(name=>common.namespace(name)));
  let held=null,currentKey='',exporter,personal,search,audio;
  const currentSelection=()=>captureSelection(reader)||held||selectedOrCurrent(reader);
  function normalized(value){if(value?.blocks)return value;const current=reader.getCurrent();if(!value)return currentSelection();return{blocks:[{text:value.text,selected_text:value.text,edition_id:value.edition_id||value.edition||current?.edition.id,edition_name:value.edition_name||(current?.edition.id===(value.edition_id||value.edition)?current.edition.name:undefined),language:value.language,origin:value.origin,license:value.license,source_record_id:value.source_record_id,book:value.book,chapter:value.chapter,verse_start:value.verse??value.number,verse_end:value.verse??value.number,reference:value.reference,label:value.label??String(value.verse??value.number),start_utf16:0,end_utf16:value.text.length}],text:value.text,reference:value.reference,edition_id:value.edition_id||value.edition};}
  function requireSelection(){const value=currentSelection();if(!value?.blocks?.length)throw Error(common.t('core.chooseText'));return value;}
  const tools={
    async compare(value=currentSelection()){
      value=normalized(value);const first=value?.blocks?.[0];if(!first)throw Error(common.t('core.chooseText'));
      await reader.open({edition:first.edition_id,book:first.book,chapter:first.chapter,verse:first.verse_start,selectedVerse:first.verse_start});
      document.getElementById('compare-verse').click();
    },
    async crossrefs(value=currentSelection(),engine='all'){
      const first=normalized(value)?.blocks?.[0];if(!first)throw Error(common.t('core.chooseText'));
      const native={'kjv':'crossreferences:KJV','bsb':'crossreferences:BSB'}[first.edition_id];
      if(!native){common.notify(common.t('core.mapping'),true);layout.setMode('research');return;}
      const select=document.getElementById('edition');if([...select.options].some(o=>o.value===native))select.value=native;
      document.getElementById('engine').value=engine;layout.setMode('research');await research.open(first.reference);
    }
  };
  exporter=await createExporter(common,{reader,getSelection:currentSelection,getSearchSelection:()=>{if(search?.getSelection)return search.getSelection();const rows=search?.getLastResult()?.results||[];return{blocks:rows.map(row=>normalized(row).blocks[0]),text:rows.map(row=>row.text).join('\n'),shape:'searchcomparison'};},getCollectionSelection:()=>personal?.getCollectionSelection?.()});
  personal=await createWorkspaceStudio(common,{reader,getSelection:currentSelection,onExport:value=>exporter.open(normalized(value))});
  search=createAdvancedSearch(common,{reader,onSave:value=>personal.saveCollection(normalized(value)),onExport:value=>exporter.open(normalized(value)),onCompare:tools.compare});
  const library=createLibrary(common,{reader,onImport:async()=>{held=null;await reader.refresh();renderLanguage();}});
  audio=await createAudioStudio(common,{reader,getSelection:currentSelection});
  const settings=()=>document.getElementById('settings-open').click();
  const guide=common.dialog('action.guide',{id:'studio-guide-dialog'});
  function showGuide(kind='guide'){guide.body.replaceChildren(common.text('p','core.'+kind),common.text('p','core.privacy'),common.text('p','core.roCoverage'));guide.open();}
  const nav=node('nav',null,'studio-menubar');nav.id='studio-menubar';nav.setAttribute('aria-label','Reading studio');
  const menus=[
    ['file',[['open',()=>library.openImport()],['pdf',()=>exporter.open(currentSelection(),'pdf')],['docx',()=>exporter.open(currentSelection(),'docx')],['print',()=>{document.body.classList.add('studio-print');window.print();setTimeout(()=>document.body.classList.remove('studio-print'),1000);}],['exit',()=>common.request('quit',{})]]],
    ['bible',[['translation',()=>focus('reader-edition')],['language',()=>focus('studio-bible-language')],['book',()=>focus('reader-book')],['chapter',()=>document.getElementById('reader-chapters-toggle').click()],['compare',()=>tools.compare()],['reading',()=>{layout.setMode('reading');reader.reveal();}]]],
    ['audio',[['read',()=>audio.play(currentSelection())],['voices',()=>audio.openVoices()],['downloadVoices',()=>audio.openVoices()],['windowsVoices',()=>audio.openVoices()],['playback',()=>audio.openPlayback()]]],
    ['search',[['quickSearch',()=>document.getElementById('reader-search-toggle').click()],['advancedSearch',()=>search.open(currentSelection())],['searchAll',()=>search.open(currentSelection(),{edition:'all'})],['savedSearches',()=>personal.open('savedsearch')],['searchHistory',()=>personal.open('history')]]],
    ['research',[['engineA',()=>tools.crossrefs(currentSelection(),'A')],['engineB',()=>tools.crossrefs(currentSelection(),'B')],['engineC',()=>tools.crossrefs(currentSelection(),'C')],['selectedResearch',()=>search.open(requireSelection())],['compare',()=>tools.compare()],['collections',()=>personal.open('collections')]]],
    ['library',[['myLibraries',()=>library.open()],['import',()=>library.openImport()],['importCorpus',()=>library.openImport({biblia:true})],['download',()=>library.openDownload()],['sqlServer',()=>library.openSQLServer()],['databaseInfo',()=>library.open()]]],
    ['documents',[['notes',()=>personal.open('notes')],['highlights',()=>personal.open('highlights')],['bookmarks',()=>personal.open('bookmarks')],['corrections',()=>personal.open('corrections')],['collections',()=>personal.open('collections')],['exportManager',()=>exporter.open()]]],
    ['settings',[['appearance',settings],['interfaceLanguage',settings],['playback',()=>audio.openPlayback()],['storage',()=>library.open()]]],
    ['help',[['guide',()=>showGuide()],['shortcuts',()=>showGuide('shortcuts')],['about',()=>showGuide('about')]]]
  ];
  for(const [name,actions]of menus){const menu=node('details',null,'studio-menu'),summary=common.text('summary','menu.'+name),list=node('div',null,'studio-menu-items');menu.dataset.menu=name;summary.id='studio-menu-'+name;for(const[key,run]of actions)list.append(common.button('action.'+key,()=>{menu.open=false;return run();}));menu.append(summary,list);menu.addEventListener('toggle',()=>{if(menu.open)for(const other of nav.querySelectorAll('details'))if(other!==menu)other.open=false;});nav.append(menu);}
  const more=node('details',null,'studio-menu studio-tools');more.append(common.text('summary','core.more'));const moreList=node('div',null,'studio-menu-items');for(const[name,actions]of menus){moreList.append(common.text('h3','menu.'+name));for(const[key,run]of actions)moreList.append(common.button('action.'+key,()=>{more.open=false;return run();}));}more.append(moreList);nav.append(more);
  document.querySelector('.app-header').append(nav);
  document.addEventListener('pointerdown',event=>{if(!nav.contains(event.target))for(const menu of nav.querySelectorAll('details'))menu.open=false;});
  function focus(id){layout.setMode('reading');const control=document.getElementById(id);control?.scrollIntoView({block:'center'});control?.focus();}
  const languageField=common.field('core.language','select');languageField.input.id='studio-bible-language';languageField.label.htmlFor=languageField.input.id;document.getElementById('reader-navigation').prepend(languageField.label);
  const editionNote=common.text('p','core.roCoverage','notice studio-edition-note');editionNote.id='studio-edition-note';editionNote.hidden=true;document.getElementById('reader-navigation').after(editionNote);
  const canonicalLanguage=value=>({eng:'en',ron:'ro',rum:'ro',deu:'de',ger:'de'}[value]||value||'und');
  function renderLanguage(){const cat=reader.getCatalog();if(!cat)return;const previous=languageField.input.value;const names={en:'English',ro:'Română',de:'Deutsch'};const values=[...new Set(cat.editions.map(e=>canonicalLanguage(e.language)))];common.options(languageField.input,[['all',common.t('core.allLanguages')],...values.map(v=>[v,names[v]||v])],values.includes(previous)?previous:'all');filterTranslation();}
  function filterTranslation(){const cat=reader.getCatalog();if(!cat)return;for(const option of document.getElementById('reader-edition').options){const edition=cat.editions.find(e=>e.id===option.value);option.hidden=languageField.input.value!=='all'&&canonicalLanguage(edition?.language)!==languageField.input.value;}editionNote.hidden=reader.getCurrent()?.edition.id!=='ronbl';}
  languageField.input.addEventListener('change',async()=>{filterTranslation();const cat=reader.getCatalog(),selected=reader.getCurrent();if(languageField.input.value!=='all'&&canonicalLanguage(selected?.edition.language)!==languageField.input.value){const ed=cat.editions.find(e=>canonicalLanguage(e.language)===languageField.input.value);if(ed)await reader.open({...reader.getPosition(),edition:ed.id});}filterTranslation();});
  document.addEventListener('reader:chapter',()=>{const current=reader.getCurrent(),key=current?.edition.id+'|'+current?.book+'|'+current?.chapter;if(key!==currentKey){held=null;currentKey=key;}filterTranslation();personal.refreshAnnotations?.();});
  document.addEventListener('reader:selection',()=>{held=selectedOrCurrent(reader);});
  document.addEventListener('selectionchange',()=>{const selected=captureSelection(reader);if(selected)held=selected;});
  const menu=node('div',null,'studio-context-menu');menu.id='studio-context-menu';menu.setAttribute('role','menu');menu.hidden=true;document.body.append(menu);let contextSelection,contextOpener;
  async function copy(withReference){const value=contextSelection;const ref=withReference?'\n— '+value.blocks.map(v=>v.reference).join('; ')+' ('+(value.blocks[0].edition_name||value.edition_id)+')':'';const text=value.text+ref;try{await navigator.clipboard.writeText(text);}catch{const temp=node('textarea',text);temp.style.position='fixed';temp.style.opacity='0';document.body.append(temp);temp.select();if(!document.execCommand('copy')){temp.remove();throw Error(common.t('common.failed'));}temp.remove();}common.notify(common.t('core.copied'));}
  const contextActions=[['read',()=>audio.play(contextSelection)],['search',()=>search.open(contextSelection)],['all',()=>search.open(contextSelection,{edition:'all'})],['similar',()=>search.open(contextSelection,{edition:'all',mode:'words'})],['compare',()=>tools.compare(contextSelection)],['crossrefs',()=>tools.crossrefs(contextSelection)],['copy',()=>copy(false)],['copyReference',()=>copy(true)],['highlight',()=>personal.saveSelection(contextSelection,'highlights')],['note',()=>personal.saveSelection(contextSelection,'notes')],['collection',()=>personal.saveCollection(contextSelection)],['bookmark',()=>personal.saveSelection(contextSelection,'bookmarks')],['pdf',()=>exporter.open(contextSelection,'pdf')],['docx',()=>exporter.open(contextSelection,'docx')],['export',()=>exporter.open(contextSelection)]];
  for(const[key,run]of contextActions){const button=common.button('context.'+key,()=>{menu.hidden=true;return run();});button.setAttribute('role','menuitem');button.dataset.contextAction=key;menu.append(button);}
  function openContext(x,y){contextSelection=currentSelection();if(!contextSelection)return;held=contextSelection;contextOpener=document.activeElement;menu.hidden=false;menu.style.left=Math.max(4,Math.min(x,innerWidth-menu.offsetWidth-4))+'px';menu.style.top=Math.max(4,Math.min(y,innerHeight-Math.min(menu.scrollHeight,innerHeight-16)-8))+'px';menu.querySelector('button').focus({preventScroll:true});}
  document.getElementById('reader-content').addEventListener('contextmenu',event=>{if(currentSelection()){event.preventDefault();openContext(event.clientX,event.clientY);}});
  document.addEventListener('pointerdown',event=>{if(!menu.contains(event.target))menu.hidden=true;});
  menu.addEventListener('keydown',event=>{const buttons=[...menu.querySelectorAll('button')],index=buttons.indexOf(document.activeElement);if(event.key==='Escape'){event.preventDefault();menu.hidden=true;(contextOpener?.focus?contextOpener:document.getElementById('reader-content')).focus({preventScroll:true});}else if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();buttons[event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length].focus();}else if(event.key==='Tab')menu.hidden=true;});
  document.addEventListener('keydown',event=>{if(event.shiftKey&&event.key==='F10'&&!document.querySelector('dialog[open]')){event.preventDefault();const rect=document.getElementById('reader-heading').getBoundingClientRect();openContext(Math.max(8,rect.left),Math.max(8,rect.bottom));}else if(event.ctrlKey&&event.shiftKey&&event.code==='KeyF'){event.preventDefault();search.open(currentSelection());}});
  common.subscribe(()=>renderLanguage());common.localize();renderLanguage();document.body.dataset.studioReady='true';
  return{common,library,search,personal,exporter,audio,getSelection:currentSelection};
}
