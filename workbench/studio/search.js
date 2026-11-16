/* Advanced search UI. Original source text only; highlights are safe DOM nodes. */
export function createAdvancedSearch(c,{reader,onSave,onExport,onCompare}={}){
  const {node,text,button,field,dialog,request,waitJob}=c;let ready,dlg,controller=null,snapshot=null,result=null;const selectedRows=new Map();
  const key=s=>'search.'+s;
  const load=()=>ready??=c.namespace('search');
  const choices=(input,entries,selected)=>{input.replaceChildren(...entries.map(([value,label,raw=false])=>{const o=raw?node('option',label):text('option',key(label));o.value=String(value);return o;}));if(selected!=null)input.value=String(selected);};
  const select=(name,entries,selected)=>{const f=field(key(name),'select');choices(f.input,entries,selected);return f;};
  function block(r){return{edition_id:r.edition,edition_name:r.edition_name||r.edition,language:r.language||'und',book:r.book,chapter:r.chapter,verse_start:r.nativeVerseStart??r.verse,verse_end:r.nativeVerseEnd??r.verse,label:r.label??String(r.verse),reference:r.reference,text:r.text,selected_text:r.text,source_text:r.text,sourceTextSha256:r.text_sha256,start_utf16:0,end_utf16:r.text.length,license:r.license,source:r.source,source_record_id:r.source_record_id};}
  function selection(r){return{edition:r.edition,edition_id:r.edition,book:r.book,chapter:r.chapter,verse:r.verse,number:r.verse,label:r.label??String(r.verse),reference:r.reference,text:r.text,start:0,end:r.text.length,start_utf16:0,end_utf16:r.text.length,source_kind:'verse',source_id:r.reference,blocks:[block(r)]};}
  function combined(rows){return{blocks:rows.map(block),text:rows.map(r=>r.text).join('\n\n'),selection_kind:'whole-search-results',search_snapshot:snapshot?structuredClone(snapshot):null};}
  function highlight(source,query,mode,diacritics){
    const output=node('p',null,'scripture studio-search-text');let folded='',map=[];
    const fold=s=>{let out=s.normalize('NFC').toLocaleLowerCase();if(diacritics==='folded')out=out.normalize('NFD').replace(/\p{M}/gu,'');return out;};
    for(const match of source.matchAll(/\P{M}\p{M}*|\p{M}+/gu)){const f=fold(match[0]);for(let i=0;i<f.length;i++)map.push([match.index,match.index+match[0].length]);folded+=f;}
    const terms=mode==='phrase'?[query.replace(/^"|"$/g,'')]:[...query.matchAll(/"([^"]+)"|([\p{L}\p{N}_]+)/gu)].map(m=>m[1]||m[2]).filter(s=>!['AND','OR','NOT'].includes(s));let ranges=[];
    for(const term of terms){const needle=fold(term);if(!needle)continue;let at=0;while((at=folded.indexOf(needle,at))!==-1){if(map[at]&&map[at+needle.length-1])ranges.push([map[at][0],map[at+needle.length-1][1]]);at+=Math.max(needle.length,1);if(ranges.length>=500)break;}}
    ranges.sort((a,b)=>a[0]-b[0]);const merged=[];for(const r of ranges){const last=merged.at(-1);if(last&&r[0]<=last[1])last[1]=Math.max(last[1],r[1]);else merged.push([...r]);}
    let pos=0;for(const [start,end]of merged){output.append(document.createTextNode(source.slice(pos,start)),node('mark',source.slice(start,end)));pos=end;}output.append(document.createTextNode(source.slice(pos)));return output;
  }
  async function open(selected=null,{edition='current',mode:initialMode='words'}={}){
    if(controller){controller.abort();controller=null;}
    await load();dlg??=dialog(key('title'),{id:'studio-search-dialog',wide:true});dlg.body.replaceChildren();
    const saved=selected?.savedSearch||selected?.dataSnapshot||(selected?.type==='savedsearch'?selected.data:null)||{};
    const current=reader?.getPosition?.()||{};const catalog=await request('/api/reader/catalog?edition='+encodeURIComponent(current.edition||'web'));
    const requestedEdition=saved.edition||(edition==='current'?(current.edition||catalog.selected_edition):edition);
    const initialText=String(saved.query||selected?.text||'');
    const query=field(key('query'),'search',initialText.slice(0,200)),mode=select('mode',[['words','words'],['phrase','phrase'],['prefix','prefix'],['boolean','boolean']],saved.mode||initialMode),scope=select('scope',[['all','allTestaments'],['OT','oldTestament'],['NT','newTestament']],saved.testament||'all'),editions=select('edition',[['all','allEditions'],...catalog.editions.map(e=>[e.id,e.name,true])],requestedEdition),marks=select('diacritics',[['exact','exact'],['folded','folded']],saved.diacritics||'exact'),books=field(key('books'),'select');books.input.multiple=true;books.input.size=5;choices(books.input,catalog.books.map(b=>[b.id,b.name,true]));query.input.maxLength=200;
    if(![...editions.input.options].some(o=>o.value===requestedEdition)){const o=node('option',requestedEdition+' · '+c.t(key('unavailableEdition')));o.value=requestedEdition;editions.input.append(o);editions.input.value=requestedEdition;}
    const grid=node('div',null,'studio-grid');for(const f of [query,mode,scope,editions,marks,books])grid.append(f.label);
    const summary=text('p',key('help')),status=node('p'),results=node('div'),actions=node('div',null,'studio-actions');status.setAttribute('role','status');let offset=0;
    async function bookChoices(){const ed=editions.input.value==='all'?(current.edition||'web'):editions.input.value;const cat=await request('/api/reader/catalog?edition='+encodeURIComponent(ed));choices(books.input,cat.books.map(b=>[b.id,b.name,true]));}
    editions.input.addEventListener('change',()=>bookChoices().catch(c.notifyError));
    function render(value){result=value;results.replaceChildren();const submitted=snapshot;status.textContent=c.t(key(value.total_exact?'count':'partialCount'),{total:value.total,query:submitted.query});
      if(value.status==='CANCELLED'){status.textContent=c.t(key('cancelled'));return;}
      if(!value.results.length)results.append(text('p',key('noResults')));
      for(const r of value.results){const card=node('article',null,'studio-card'),title=node('h3',`${r.reference} · ${catalog.editions.find(e=>e.id===r.edition)?.name||r.edition}`),buttons=node('div',null,'studio-actions'),check=field(key('selectResult'),'checkbox'),id=r.edition+'#'+r.local_row_id;check.input.checked=selectedRows.has(id);check.input.addEventListener('change',()=>{if(check.input.checked)selectedRows.set(id,r);else selectedRows.delete(id);updateSelection();});card.append(check.label,title,highlight(r.text,submitted.query,submitted.mode,submitted.diacritics));
        buttons.append(button(key('read'),async()=>{await reader?.open?.({edition:r.edition,book:r.book,chapter:r.chapter,verse:r.verse,selectedVerse:r.verse});dlg.close();}));
        if(onSave)buttons.append(button(key('save'),()=>onSave(selection(r))));if(onExport)buttons.append(button(key('export'),()=>onExport(selection(r))));if(onCompare)buttons.append(button(key('compare'),()=>onCompare(selection(r))));card.append(buttons);results.append(card);}
      previous.disabled=offset===0;next.disabled=!value.total_exact||offset+value.limit>=value.total;updateSelection();
    }
    async function run(newQuery){if(controller)controller.abort();controller=new AbortController();const own=controller;searchButton.disabled=true;cancelButton.disabled=false;status.textContent=c.t(key('searching'));
      if(newQuery){offset=0;selectedRows.clear();result=null;results.replaceChildren();previous.disabled=next.disabled=true;updateSelection();snapshot={query:query.input.value.trim(),mode:mode.input.value,edition:editions.input.value,diacritics:marks.input.value,testament:scope.input.value,books:[...books.input.selectedOptions].map(o=>o.value)};if(!snapshot.books.length)delete snapshot.books;if(snapshot.query)request('workspace/create',{type:'history',title:snapshot.query,data:{kind:'search',...snapshot}}).catch(()=>c.notify(c.t(key('historyFailed')),true));}
      try{const initial=await request('search',{...snapshot,limit:25,offset},own.signal);const value=await waitJob(initial,{signal:own.signal,onProgress:()=>{}});if(controller!==own)return;render(value);}catch(error){if(controller===own){if(error.name==='AbortError')status.textContent=c.t(key('cancelled'));else c.notifyError(error);}}finally{if(controller===own){controller=null;searchButton.disabled=false;cancelButton.disabled=true;}}
    }
    const searchButton=button(key('search'),()=>run(true)),cancelButton=button(key('cancel'),()=>controller?.abort()),previous=button(key('previous'),()=>{offset=Math.max(0,offset-25);return run(false);}),next=button(key('next'),()=>{offset+=25;return run(false);}),saveSearch=button(key('saveSearch'),async()=>{const data={query:query.input.value.trim(),mode:mode.input.value,edition:editions.input.value,diacritics:marks.input.value,testament:scope.input.value,books:[...books.input.selectedOptions].map(o=>o.value)};if(!data.query)throw Error(c.t(key('queryRequired')));await request('workspace/create',{type:'savedsearch',title:data.query,data});c.notify(c.t(key('searchSaved')));}),saveSelected=button(key('saveSelected'),()=>onSave?.(combined([...selectedRows.values()]))),exportSelected=button(key('exportSelected'),()=>onExport?.(combined([...selectedRows.values()])));
    function updateSelection(){saveSelected.disabled=!onSave||selectedRows.size===0;exportSelected.disabled=!onExport||selectedRows.size===0;}
    cancelButton.disabled=true;previous.disabled=next.disabled=true;updateSelection();actions.append(searchButton,cancelButton,previous,next,saveSearch,saveSelected,exportSelected);if(initialText.length>200)dlg.body.append(text('p',key('selectionShortened'),'studio-warning'));dlg.body.append(grid,summary,actions,status,results);dlg.open();query.input.focus();query.input.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();run(true);}});
    if(saved.books?.length){await bookChoices();for(const o of books.input.options)o.selected=saved.books.includes(o.value);}
  }
  document.addEventListener('studio-open-saved-search',event=>open({savedSearch:event.detail}).catch(c.notifyError));
  return{open,cancel(){controller?.abort();},getLastResult:()=>result,getSelection:()=>combined(selectedRows.size?[...selectedRows.values()]:(result?.results||[]))};
}
