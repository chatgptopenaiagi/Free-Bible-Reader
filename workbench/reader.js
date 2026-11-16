import {$,element as el,options,api} from '/ui-core/components/dom.js';
import {createReaderState,resolveCatalogPosition,createRequestEpoch,nativeChapters} from './reader-state.js';
import {createReaderSearch} from './reader-search.js';
import {createReaderComparison} from './reader-comparison.js';

export function createReader({translator:t,preferences=null,onSelect=()=>{},onExplore=()=>{},onCatalog=()=>{}}){
  const state=createReaderState(),navigation=createRequestEpoch(),catalogs=new Map();
  let catalog=null,current=null,selection=null,visibleVerse=null,lastViewport=null,notice=null,navigating=false,scrollTimer=null;
  const labelBook=book=>t.has(`books.${book.id}`)?t.t(`books.${book.id}`):book.name;
  const currentEdition=()=>current?.edition||catalog?.editions.find(e=>e.id===$('reader-edition').value);
  const clone=value=>value?JSON.parse(JSON.stringify(value)):null;
  const labelValue=value=>typeof value==='number'?t.formatNumber(value):String(value);
  const reference=(book,chapter,verse)=>`${book}.${chapter}${verse!=null?'.'+verse:''}`;
  const readerVisible=()=>!$('panel-reader').hidden&&!$('panel-reader').classList.contains('collapsed');
  const headerOffset=()=>document.querySelector('.app-header')?.getBoundingClientRect().bottom||0;
  const frame=callback=>(globalThis.requestAnimationFrame||((fn)=>setTimeout(fn,0)))(callback);
  function position(){return current?{edition:current.edition.id,book:current.book,chapter:current.chapter,verse:visibleVerse??selection?.number??current.verses[0]?.number??null,selectedVerse:selection?.number??null}:null;}
  function persist(){const value=position();if(value)state.save(value);}
  function captureViewport(){
    if(!current||navigating||!readerVisible())return lastViewport;
    const top=headerOffset()+8,verses=[...$('reader-content').querySelectorAll('.scripture-verse')];
    const target=verses.find(node=>{const rect=node.getBoundingClientRect();return rect.bottom>top&&rect.top<innerHeight;});
    if(target){const number=current.verses.find(v=>String(v.number)===target.dataset.verse)?.number;visibleVerse=number;lastViewport={verse:number,offset:target.getBoundingClientRect().top};persist();}
    return lastViewport;
  }
  function restoreViewport(anchor=lastViewport){
    if(!readerVisible()||!current)return;
    const number=anchor?.verse??visibleVerse??selection?.number;
    const node=[...$('reader-content').querySelectorAll('.scripture-verse')].find(n=>String(n.dataset.verse)===String(number));
    if(!node)return;
    if(anchor&&Number.isFinite(anchor.offset))window.scrollBy(0,node.getBoundingClientRect().top-anchor.offset);
    else {node.scrollIntoView({block:'start',behavior:'instant'});window.scrollBy(0,-headerOffset()-12);}
  }
  function reveal(){frame(()=>restoreViewport());}
  function showChapterStart(){frame(()=>{if(!readerVisible())return;$('reader-heading').scrollIntoView({block:'start',behavior:'instant'});window.scrollBy(0,-headerOffset()-12);captureViewport();});}
  async function getCatalog(edition){if(!catalogs.has(edition))catalogs.set(edition,api(`/api/reader/catalog?edition=${encodeURIComponent(edition)}`).catch(error=>{catalogs.delete(edition);throw error;}));return catalogs.get(edition);}
  function renderNotice(){if(!navigating)$('reader-status').textContent=notice?t.t(notice.key,notice.params):'';}
  function renderChapters(chapter=$('reader-chapter').value||1){
    const book=catalog?.books.find(b=>b.id===$('reader-book').value);if(!book)return;
    const labels=nativeChapters(book);options($('reader-chapter'),labels.map(value=>[value,labelValue(value)]),labels.find(value=>String(value)===String(chapter))??labels[0]);
    const grid=$('reader-chapters-grid');if(!grid)return;grid.replaceChildren();
    labels.forEach(value=>{const button=el('button',labelValue(value));button.type='button';button.setAttribute('aria-current',String(value)===String($('reader-chapter').value)?'page':'false');button.addEventListener('click',async()=>{grid.hidden=true;$('reader-chapters-toggle')?.setAttribute('aria-expanded','false');const loaded=await load(book.id,value);if(loaded)$('reader-heading').focus({preventScroll:true});});grid.append(button);});
  }
  function renderLibrary(){
    if(!catalog)return;const filter=$('library-filter').value.toLocaleLowerCase(t.language),container=$('library-books');container.replaceChildren();
    catalog.books.forEach((book,index)=>{if(filter&&!`${labelBook(book)} ${book.name} ${book.id}`.toLocaleLowerCase(t.language).includes(filter))return;
      if(!filter&&(index===0||book.id==='Matt'))container.append(el('h3',t.t(book.id==='Matt'?'reader.newTestament':catalog.books.length===66?'reader.oldTestament':'reader.libraryHeading'),'library-group'));
      const button=el('button',labelBook(book),'library-book');button.type='button';button.dataset.book=book.id;button.setAttribute('aria-current',String(book.id===$('reader-book').value));
      button.addEventListener('click',()=>{chooseBook(book.id);document.dispatchEvent(new CustomEvent('reader-library-select'));});container.append(button);
    });
  }
  function renderCatalog(edition=current?.edition.id||$('reader-edition').value||'web',book=current?.book||$('reader-book').value||'John',chapter=current?.chapter||$('reader-chapter').value||1){
    if(!catalog)return;options($('reader-edition'),catalog.editions.map(e=>[e.id,e.name]),edition);options($('reader-book'),catalog.books.map(b=>[b.id,labelBook(b)]),book);renderChapters(chapter);renderLibrary();
    const source=currentEdition();$('sidebar-edition').textContent=source?.name||'';$('sidebar-license').textContent=typeof source?.license==='object'?JSON.stringify(source.license):source?.license||'';$('reader-edition-label').textContent=source?.name||'';
  }
  function renderSelection(){
    $('reader-content').querySelectorAll('.scripture-verse').forEach(p=>p.classList.toggle('selected',p.dataset.reference===selection?.reference));
    $('selected-verse').textContent=selection?t.t('reader.verseSelected',{reference:selection.reference}):t.t('reader.verseHint');
    $('selected-verse').closest('.reader-context')?.classList.toggle('has-selection',!!selection);
    for(const id of ['explore-verse','compare-verse'])if($(id)){$(id).hidden=!selection;$(id).disabled=navigating||!selection;}
  }
  function selectVerse(ref){selection=current?.verses.find(v=>v.reference===ref)||null;if(selection){visibleVerse=selection.number;lastViewport={verse:visibleVerse,offset:[...$('reader-content').querySelectorAll('[data-verse]')].find(n=>n.dataset.verse===String(visibleVerse))?.getBoundingClientRect().top};}renderSelection();persist();document.dispatchEvent(new CustomEvent('reader:selection',{detail:clone(selection)}));if(selection)onSelect({kind:'reader',edition:current.edition,book:current.book,chapter:current.chapter,verse:selection});}
  function renderChapter(){
    if(!current)return;const book=catalog.books.find(b=>b.id===current.book),name=book?labelBook(book):current.book;
    $('reader-heading').textContent=t.t('reader.chapterHeading',{book:name,chapter:labelValue(current.chapter)});$('reader-breadcrumb').textContent=`${t.t('nav.library')} / ${name} / ${labelValue(current.chapter)}`;
    $('reader-content').replaceChildren();for(const verse of current.verses){const p=el('p',undefined,'scripture-verse');p.dataset.reference=verse.reference;p.dataset.verse=verse.number;
      const number=el('button',labelValue(verse.label??verse.number),'verse-number');number.type='button';number.disabled=navigating;number.setAttribute('aria-label',`${t.t('reader.selectVerse')} ${verse.reference}`);number.addEventListener('click',()=>selectVerse(verse.reference));
      const text=el('span',verse.text);text.dir='auto';p.dir='auto';text.dataset.sourceData='';p.append(number,text);$('reader-content').append(p);
    }
    for(const suffix of ['', '-bottom']){if($('reader-previous'+suffix))$('reader-previous'+suffix).disabled=navigating||!current.previous;if($('reader-next'+suffix))$('reader-next'+suffix).disabled=navigating||!current.next;}
    renderSelection();document.dispatchEvent(new CustomEvent('reader:chapter',{detail:clone(current)}));
  }
  function busy(value){navigating=value;$('reader-progress').hidden=!value;$('reader-content').toggleAttribute('aria-busy',value);for(const node of $('reader-content').querySelectorAll('button'))node.disabled=value;for(const suffix of ['', '-bottom']){if($('reader-previous'+suffix))$('reader-previous'+suffix).disabled=value||!current?.previous;if($('reader-next'+suffix))$('reader-next'+suffix).disabled=value||!current?.next;}renderSelection();}
  async function navigate(target,{restoring=false,fresh=false}={}){
    const token=navigation.next(),requested={...target};busy(true);notice=null;$('reader-status').textContent=t.t('reader.loading');
    try{
      const nextCatalog=await getCatalog(requested.edition);if(!navigation.isCurrent(token))return null;
      const native=resolveCatalogPosition(requested,nextCatalog);
      const data=await api(`/api/reader/chapter?edition=${encodeURIComponent(requested.edition)}&book=${encodeURIComponent(native.book)}&chapter=${encodeURIComponent(native.chapter)}`);if(!navigation.isCurrent(token))return null;
      catalog=nextCatalog;current={...data,book:typeof data.book==='object'?data.book.id:data.book};selection=current.verses.find(v=>requested.selectedVerse!=null&&String(v.number)===String(requested.selectedVerse))||null;
      const anchor=current.verses.find(v=>requested.verse!=null&&String(v.number)===String(requested.verse));visibleVerse=anchor?.number??current.verses[0]?.number??null;lastViewport=null;
      if(native.adjusted||(requested.verse&&!anchor)||(requested.selectedVerse&&!selection))notice={key:'reader.positionUnavailable',params:{reference:reference(requested.book,requested.chapter,requested.selectedVerse||requested.verse)}};
      else if(restoring)notice={key:'reader.resumed',params:{reference:reference(current.book,current.chapter,visibleVerse)}};
      busy(false);renderCatalog();renderChapter();renderNotice();persist();onCatalog(catalog);onSelect({kind:'reader',edition:current.edition,book:current.book,chapter:current.chapter,verseCount:current.verses.length});
      if(anchor){lastViewport={verse:anchor.number,offset:headerOffset()+12};frame(()=>restoreViewport());}else if(!fresh)showChapterStart();
      return clone(current);
    }catch(error){if(navigation.isCurrent(token)){busy(false);if(current)renderCatalog();notice=null;$('reader-status').textContent=t.t('reader.loadError');onSelect({kind:'reader-error',error:error.message,details:error.data});}return null;}
    finally{if(navigation.isCurrent(token))busy(false);}
  }
  function load(book=$('reader-book').value,chapter=$('reader-chapter').value||1,verse=null){return navigate({edition:$('reader-edition').value||current?.edition.id||'web',book,chapter,verse,selectedVerse:verse});}
  async function chooseBook(book){
    const chosen=catalog?.books.find(b=>b.id===book),pending=load(book,nativeChapters(chosen)[0]??1),token=navigation.current,loaded=await pending;
    if(!loaded)return null;
    frame(()=>{if(!navigation.isCurrent(token)||!readerVisible())return;$('reader-navigation').scrollIntoView({block:'start',behavior:'instant'});window.scrollBy(0,-headerOffset()-12);captureViewport();});
    return loaded;
  }
  function clearSearch(){search.invalidate();$('reader-search-results').replaceChildren();$('reader-search-paging').replaceChildren();$('reader-search-status').textContent=t.t('reader.searchHint');}
  function renderSearch(){
    const snapshot=search.getSnapshot();if(!snapshot)return;const{data,context}=snapshot,status=$('reader-search-status');status.removeAttribute('data-i18n');
    const sourceEdition=catalog.editions.find(e=>e.id===context.edition)?.name||context.edition,scopedBook=catalog.books.find(book=>book.id===context.book),edition=context.book?`${sourceEdition} · ${scopedBook?labelBook(scopedBook):context.book}`:sourceEdition;
    status.textContent=(data.total?t.t('reader.searchPage',{start:t.formatNumber(data.offset+1),end:t.formatNumber(data.offset+data.results.length),total:t.formatNumber(data.total)}):t.t('reader.noResults'))+' · '+t.t('reader.searchContext',{query:context.query,edition});
    const list=$('reader-search-results');list.replaceChildren();for(const record of data.results){const item=el('li'),button=el('button',record.reference,'ref-link');button.type='button';button.addEventListener('click',async()=>{if($('reader-search-drawer'))$('reader-search-drawer').open=false;$('reader-search-toggle')?.setAttribute('aria-expanded','false');await navigate({edition:context.edition,book:record.book,chapter:record.chapter,verse:record.verse,selectedVerse:record.verse});$('reader-content').focus({preventScroll:true});});const text=el('p',record.text,'search-scripture');text.dataset.sourceData='';item.append(button,text);list.append(item);}
    const pager=$('reader-search-paging');pager.replaceChildren();for(const[key,offset,show]of[['common.previous',Math.max(0,data.offset-data.limit),data.offset>0],['common.next',data.offset+data.limit,data.offset+data.results.length<data.total]])if(show){const button=el('button',t.t(key));button.type='button';button.addEventListener('click',()=>search.page(offset));pager.append(button);}
  }
  const search=createReaderSearch({fetchPage:context=>api('/api/reader/search',{query:context.query,edition:context.edition,...(context.book?{book:context.book}:{}),limit:context.limit,offset:context.offset}),onResult:renderSearch,onError:error=>{search.invalidate();$('reader-search-results').replaceChildren();$('reader-search-paging').replaceChildren();const key=error.validation==='TOO_LONG'?'reader.searchTooLong':error.validation==='TOO_SHORT'?'reader.searchMinimum':'reader.searchError';$('reader-search-status').removeAttribute('data-i18n');$('reader-search-status').textContent=t.t(key);if(!error.validation)onSelect({kind:'search-error',error:error.message,details:error.data});},onBusy:value=>{$('reader-search-button').disabled=value;for(const button of $('reader-search-paging').querySelectorAll('button'))button.disabled=value;if(value){$('reader-search-status').removeAttribute('data-i18n');$('reader-search-status').textContent=t.t('reader.searching');}}});
  function openSearch(force){const drawer=$('reader-search-drawer')||document.querySelector('.reader-search');if(drawer){drawer.open=force===true?true:!drawer.open;$('reader-search-toggle')?.setAttribute('aria-expanded',String(drawer.open));if(drawer.open)$('reader-search-input').focus();}}
  function setFocus(active){captureViewport();document.body.dataset.readingFocus=String(active);const button=$('reader-focus-toggle');if(button){button.dataset.i18n=active?'reader.exitFocus':'reader.focus';button.textContent=t.t(button.dataset.i18n);button.setAttribute('aria-pressed',String(active));}document.dispatchEvent(new CustomEvent('reader-focus-change',{detail:active}));reveal();}
  $('reader-navigation').addEventListener('submit',event=>event.preventDefault());
  $('reader-edition').addEventListener('change',()=>{captureViewport();const old=position(),edition=$('reader-edition').value;clearSearch();navigate({...old,edition,book:old?.book||'John',chapter:old?.chapter||1,verse:old?.verse??null,selectedVerse:old?.selectedVerse??null});});
  $('reader-book').addEventListener('change',()=>{renderChapters(1);chooseBook($('reader-book').value);});$('reader-chapter').addEventListener('change',()=>load());$('library-filter').addEventListener('input',renderLibrary);
  for(const suffix of ['', '-bottom']){$('reader-previous'+suffix)?.addEventListener('click',()=>current?.previous&&load(current.previous.book,current.previous.chapter));$('reader-next'+suffix)?.addEventListener('click',()=>current?.next&&load(current.next.book,current.next.chapter));}
  $('reader-search-input').maxLength=200;$('reader-search-form').addEventListener('submit',event=>{event.preventDefault();search.start({query:$('reader-search-input').value,edition:$('reader-edition').value,book:$('reader-search-book').checked?$('reader-book').value:null});});
  $('reader-search-toggle')?.addEventListener('click',()=>openSearch());$('reader-search-drawer')?.addEventListener('toggle',()=>$('reader-search-toggle')?.setAttribute('aria-expanded',String($('reader-search-drawer').open)));
  $('reader-chapters-toggle')?.addEventListener('click',()=>{const grid=$('reader-chapters-grid');if(grid){grid.hidden=!grid.hidden;$('reader-chapters-toggle').setAttribute('aria-expanded',String(!grid.hidden));}});
  $('reader-focus-toggle')?.addEventListener('click',()=>setFocus(document.body.dataset.readingFocus!=='true'));
  $('workspace-layout').addEventListener('change',captureViewport);
  $('explore-verse').addEventListener('click',()=>{captureViewport();if(selection)onExplore({reference:selection.reference,edition:current.edition.id});});
  createReaderComparison({translator:t,api,getSelection:()=>selection,getEditions:()=>catalog?.editions||[],getCurrent:()=>current});
  document.addEventListener('keydown',event=>{if(event.defaultPrevented||event.altKey||event.ctrlKey||event.metaKey||event.shiftKey||event.target.closest?.('form,input,textarea,select,[contenteditable]')||document.querySelector('dialog[open]')||!readerVisible())return;if(event.key==='/'){event.preventDefault();openSearch(true);}else if(event.key==='['&&current?.previous){event.preventDefault();load(current.previous.book,current.previous.chapter);}else if(event.key===']'&&current?.next){event.preventDefault();load(current.next.book,current.next.chapter);}});
  window.addEventListener('scroll',()=>{clearTimeout(scrollTimer);scrollTimer=setTimeout(captureViewport,120);},{passive:true});window.addEventListener('pagehide',()=>{captureViewport();persist();});
  preferences?.subscribe((state,keys)=>{if(keys.includes('workspaceLayout')){if(state.workspaceLayout!=='reading'&&document.body.dataset.readingFocus==='true')setFocus(false);if(state.workspaceLayout==='reading')reveal();}if(keys.some(k=>['interfaceFont','scriptureFont','interfaceFontScale','scriptureFontScale','lineHeight','paragraphSpacing','readingWidth','displayDensity'].includes(k)))reveal();});
  t.subscribe(()=>{const anchor=captureViewport();renderCatalog();renderChapter();renderSearch();renderNotice();if($('reader-focus-toggle'))$('reader-focus-toggle').textContent=t.t(document.body.dataset.readingFocus==='true'?'reader.exitFocus':'reader.focus');frame(()=>restoreViewport(anchor));});
  return{async init(){try{const initial=await getCatalog('web'),saved=state.get();catalog=initial;let valid=saved&&initial.editions.some(e=>e.id===saved.edition);if(valid){const source=await getCatalog(saved.edition),book=source.books.find(book=>book.id===saved.book);valid=!!book&&nativeChapters(book).some(value=>String(value)===String(saved.chapter));}await navigate(valid?saved:{edition:'web',book:'John',chapter:1,verse:null,selectedVerse:null},{restoring:!!valid,fresh:!valid});}catch(error){$('reader-status').textContent=t.t('reader.loadError');onSelect({kind:'reader-error',error:error.message});}},load,getSelection:()=>clone(selection),getCurrent:()=>clone(current),getPosition:()=>{captureViewport();return position();},reveal,open:navigate,selectVerse,getCatalog:()=>clone(catalog),async refresh(edition=null){catalogs.clear();return navigate({...position(),...(edition?{edition,book:'John',chapter:1,verse:null,selectedVerse:null}:{})});}};
}
