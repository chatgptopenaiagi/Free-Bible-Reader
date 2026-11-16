/** Offline narration: one cancellable synthesis job, one source unit at a time. */
export function canonicalSpeechLanguage(value){const code=String(value||'').replaceAll('_','-').toLowerCase().split('-')[0];return ['ron','rum','ro'].includes(code)?'ro':['deu','ger','de'].includes(code)?'de':['eng','en'].includes(code)?'en':code;}
export function chooseDefaultVoice(voices,sourceLanguage,stored=null){
  const actual=voices.filter(v=>v.installed&&v.runtime_available!==false);
  const saved=actual.find(v=>v.provider===stored?.provider&&v.id===stored?.voice);if(saved)return saved;
  const lang=canonicalSpeechLanguage(sourceLanguage),matching=actual.filter(v=>canonicalSpeechLanguage(v.language)===lang);
  const david=(items,provider)=>items.find(v=>v.provider===provider&&v.name.toLowerCase().includes('david'));
  return matching.find(v=>v.provider==='piper')||matching.find(v=>v.provider==='android-native'&&v.network_required===false)||david(matching,'windows-sapi')||david(matching,'windows-media')||matching.find(v=>v.provider==='windows-sapi')||matching.find(v=>v.provider==='windows-media')||matching.find(v=>v.provider==='espeak-ng'&&v.id===(lang==='en'?'en-us':lang))||matching.find(v=>v.provider==='espeak-ng'&&v.id===lang)||matching[0]||david(actual,'windows-sapi')||david(actual,'windows-media')||actual[0]||null;
}
export async function createAudioStudio(common,{reader,getSelection}){
  await common.namespace('audio');
  const {t,node,text,button,field,options,dialog,request,waitJob,notify}=common;
  const STORAGE='free-bible-reader.audio.v1';
  let catalog={voices:[],providers:[]},settings={provider:null,voice:null,speed:1,volume:1,scope:'selection'};
  try{const saved=JSON.parse(localStorage.getItem(STORAGE)||'null');if(saved?.version===1){for(const k of ['provider','voice','scope'])if(typeof saved[k]==='string')settings[k]=saved[k];if(Number.isFinite(saved.speed)&&saved.speed>=.5&&saved.speed<=2)settings.speed=saved.speed;if(Number.isFinite(saved.volume)&&saved.volume>=0&&saved.volume<=1)settings.volume=saved.volume;}}catch{}
  let plan=null,epoch=0,clipEpoch=0,activeJob=null,serial=Promise.resolve(),paused=false,preparing=false,generating=false,finished=false,currentItem=null,managerJob=null,managerAbort=null,managerBusy=false,refreshingVoices=false,refreshPromise=null,selectionSnapshot=null,state='idle';
  const media=node('audio');media.id='studio-audio-source';media.hidden=true;media.preload='auto';media.volume=settings.volume;
  const player=node('section',null,'studio-player');player.id='studio-player';player.setAttribute('aria-label',t('audio.player'));
  const controls=node('div',null,'studio-player-controls');
  function iconButton(key,icon,handler,id){const b=button(key,handler,'studio-player-button');b.removeAttribute('data-studio-key');b.textContent=icon;b.dataset.audioLabel=key;b.id=id;b.title=t(key);b.setAttribute('aria-label',t(key));return b;}
  const previous=iconButton('audio.previous','◀',()=>move(-1),'studio-audio-previous');
  const playing=iconButton('audio.play','▶',()=>play(),'studio-audio-play');
  const pausing=iconButton('audio.pause','Ⅱ',()=>pause(),'studio-audio-pause');
  const stopping=iconButton('audio.stop','■',()=>stop(),'studio-audio-stop');
  const next=iconButton('audio.next','▶|',()=>move(1),'studio-audio-next');
  const config=iconButton('audio.playback','⚙',()=>openPlayback(),'studio-audio-settings');
  controls.append(previous,playing,pausing,stopping,next,config);
  const selectors=node('div',null,'studio-player-selectors'),providerField=field('audio.provider','select'),voiceField=field('audio.voice','select');
  const provider=providerField.input,voice=voiceField.input;provider.id='studio-audio-provider';providerField.label.htmlFor=provider.id;voice.id='studio-audio-voice';voiceField.label.htmlFor=voice.id;selectors.append(providerField.label,voiceField.label);
  const status=node('p',null,'studio-player-status');status.id='studio-audio-status';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  player.append(controls,selectors,status,media);document.body.append(player);
  const voicesDialog=dialog('audio.voices',{id:'studio-voices-dialog',wide:true});
  const voiceFilter=field('audio.filter','search'),previewField=field('audio.previewText','textarea',t('audio.sampleRo'));
  voiceFilter.input.id='studio-voice-filter';voiceFilter.label.htmlFor=voiceFilter.input.id;previewField.input.id='studio-voice-preview-text';previewField.label.htmlFor=previewField.input.id;previewField.input.maxLength=2000;
  const voiceList=node('div',null,'studio-voice-list');voiceList.id='studio-voice-list';
  const managerStatus=node('p');managerStatus.id='studio-voice-status';managerStatus.setAttribute('role','status');
  const managerProgress=node('progress');managerProgress.id='studio-voice-progress';managerProgress.hidden=true;managerProgress.setAttribute('aria-label',t('audio.downloadProgress'));
  const managerCancel=button('common.cancel',()=>{managerAbort?.abort();if(managerJob)request('job/cancel',{id:managerJob}).catch(()=>{});});managerCancel.id='studio-voice-job-cancel';managerCancel.hidden=true;
  const isAndroid=()=>catalog.platform==='android'||catalog.providers.some(p=>p.id==='android-native');
  const windows=button('audio.windowsSettings',()=>request(isAndroid()?'android-voices':'windows-voices').then(()=>notify(t(isAndroid()?'audio.androidOpened':'audio.windowsOpened'))));windows.id='studio-windows-voices';
  const voicesHelp=text('p','audio.voicesHelp','notice');
  voicesDialog.body.append(voicesHelp,voiceFilter.label,previewField.label,managerStatus,managerProgress,managerCancel,voiceList);
  const previewStop=button('audio.stop',()=>stop());previewStop.id='studio-voice-preview-stop';
  voicesDialog.footer.append(previewStop,button('audio.refresh',()=>refreshVoices(true)),windows,text('small','audio.closeCancels'));
  voicesDialog.onClose(()=>managerAbort?.abort());
  const playback=dialog('audio.playback',{id:'studio-playback-dialog'}),scopeField=field('audio.scope','select'),speedField=field('audio.speed','range',settings.speed),volumeField=field('audio.volume','range',settings.volume),verseStart=field('audio.verseFrom','select'),verseEnd=field('audio.verseTo','select'),chapterStart=field('audio.chapterFrom','select'),chapterEnd=field('audio.chapterTo','select');
  scopeField.input.id='studio-playback-scope';speedField.input.id='studio-playback-speed';volumeField.input.id='studio-playback-volume';verseStart.input.id='studio-playback-verse-start';verseEnd.input.id='studio-playback-verse-end';chapterStart.input.id='studio-playback-chapter-start';chapterEnd.input.id='studio-playback-chapter-end';
  for(const f of [scopeField,speedField,volumeField,verseStart,verseEnd,chapterStart,chapterEnd])f.label.htmlFor=f.input.id;
  Object.assign(speedField.input,{min:'.5',max:'2',step:'.05'});Object.assign(volumeField.input,{min:'0',max:'1',step:'.05'});
  const speedValue=node('output'),volumeValue=node('output');speedField.label.append(speedValue);volumeField.label.append(volumeValue);
  const begin=button('audio.begin',()=>beginScope());begin.id='studio-playback-begin';
  playback.body.append(text('p','audio.scopeHelp','notice'),scopeField.label,verseStart.label,verseEnd.label,chapterStart.label,chapterEnd.label,speedField.label,volumeField.label);
  playback.footer.append(begin,button('audio.voices',()=>openVoices()));

  function save(){try{localStorage.setItem(STORAGE,JSON.stringify({version:1,...settings}));}catch{}}
  const language=canonicalSpeechLanguage;
  function providerName(id){const key='audio.provider.'+id;return t(key)===key?id:t(key);}
  function explain(error){if(error?.name==='AbortError'||error?.code==='CANCELLED')return t('common.cancelled');const key='audio.error.'+error?.code;return t(key)===key?t('audio.failed'):t(key);}
  function issue(error){state='error';renderStatus();notify(explain(error),true);}
  function describe(item){return item?.reference||t('audio.preview');}
  function clearHighlight(){document.querySelectorAll('.scripture-verse.narrating').forEach(el=>el.classList.remove('narrating'));}
  function highlight(item){clearHighlight();if(item?.edition_id!=null&&editionId(reader.getCurrent())!==item.edition_id)return;if(item?.reference)for(const el of document.querySelectorAll('.scripture-verse'))if(el.dataset.reference===item.reference)el.classList.add('narrating');}
  function renderStatus(){status.textContent=t('audio.state.'+state,{reference:describe(currentItem)});previous.disabled=!plan||preparing;next.disabled=!plan||preparing;pausing.disabled=!plan;stopping.disabled=!plan&&!activeJob;playing.setAttribute('aria-pressed',String(!!plan&&!paused&&!finished));}
  function selectedVoice(){return catalog.voices.find(v=>v.provider===settings.provider&&v.id===settings.voice);}
  function renderPlatform(){const key=isAndroid()?'audio.androidSettings':'audio.windowsSettings';windows.dataset.studioKey=key;windows.textContent=t(key);voicesHelp.dataset.studioKey=isAndroid()?'audio.androidVoicesHelp':'audio.voicesHelp';voicesHelp.textContent=t(voicesHelp.dataset.studioKey);player.setAttribute('aria-label',t(isAndroid()?'audio.androidPlayer':'audio.player'));}
  function renderSelectors(){
    renderPlatform();
    options(provider,catalog.providers.filter(p=>p.available).map(p=>[p.id,providerName(p.id)]),settings.provider);
    const candidates=catalog.voices.filter(v=>v.provider===settings.provider&&v.installed&&v.runtime_available!==false);
    options(voice,candidates.map(v=>[v.id,`${v.name} · ${v.language}${isAndroid()?' · '+t(v.network_required===true?'audio.networkVoice':v.network_required===false?'audio.offlineVoice':'audio.voiceAvailabilityUnknown'):''}`]),settings.voice);
    if(settings.voice&&!candidates.some(v=>v.id===settings.voice)){const missing=node('option',t('audio.voiceMissing'));missing.value=settings.voice;missing.disabled=true;voice.append(missing);voice.value=settings.voice;}
    provider.disabled=!catalog.providers.some(p=>p.available);voice.disabled=!candidates.length;
  }
  async function refreshVoices(refresh=false){
    if(refreshPromise)return refreshPromise;
    refreshingVoices=true;renderVoices();
    const pending=(async()=>{catalog=await request('voices'+(refresh?'?refresh=true':''));
    if(!catalog.voices.some(v=>v.provider===settings.provider&&v.id===settings.voice&&v.installed&&v.runtime_available!==false)){
      const wasSelected=!!settings.provider&&!!settings.voice;
      const chosen=chooseDefaultVoice(catalog.voices,reader.getCurrent()?.edition?.language||common.language());
      if(chosen){settings.provider=chosen.provider;settings.voice=chosen.id;save();}
      if(wasSelected&&chosen)notify(t('audio.savedVoiceUnavailable'));
    }
    renderSelectors();return catalog;})();
    refreshPromise=pending;
    try{return await pending;}finally{if(refreshPromise===pending)refreshPromise=null;refreshingVoices=false;renderVoices();}
  }
  function cancelJob(){if(activeJob)request('job/cancel',{id:activeJob}).catch(()=>{});}
  function clearClip(){media.pause();media.removeAttribute('src');media.load();clearHighlight();}
  function stop(){epoch++;cancelJob();plan=null;paused=false;finished=false;preparing=false;generating=false;currentItem=null;clearClip();state='idle';renderStatus();}
  function pause(){paused=true;media.pause();state=generating?'pausedPending':'paused';renderStatus();}
  async function resume(){paused=false;if(generating||preparing){state='generating';renderStatus();return;}if(media.getAttribute('src')&&!media.ended){try{await media.play();state='playing';highlight(currentItem);}catch{paused=true;state='ready';}renderStatus();}}
  function editionId(current){return current?.edition?.id??current?.edition_id??null;}
  function labels(book){return Array.isArray(book?.chapter_labels)?book.chapter_labels.slice():Array.isArray(book?.chapters)?book.chapters.map((_,index)=>index+1):[];}
  function unitFromVerse(current,v){return{text:v.text,reference:v.reference,edition_id:editionId(current),book:typeof current.book==='object'?current.book.id:current.book,chapter:current.chapter,verse:v.nativeVerseStart??v.number};}
  function selectionUnits(selection){
    if(!selection||!Array.isArray(selection.blocks)||!selection.blocks.length)throw Error(t('audio.noSelection'));
    return selection.blocks.map(block=>({text:block.text??block.selected_text,reference:block.reference??selection.reference,edition_id:block.edition_id??selection.edition_id,book:block.book??selection.book,chapter:block.chapter??selection.chapter,verse:block.verse_start??null}));
  }
  async function ensureUnits(token){
    if(plan.units)return;
    const thisPlan=plan,chapter=thisPlan.chapters[thisPlan.chapterIndex],current=reader.getCurrent();preparing=true;state='generating';renderStatus();
    let data;
    if(editionId(current)===thisPlan.edition&&String(current.book)===String(thisPlan.book)&&String(current.chapter)===String(chapter))data=current;
    else if(thisPlan.followReader)data=await reader.open({edition:thisPlan.edition,book:thisPlan.book,chapter,verse:null,selectedVerse:null});
    else data=await request(`/api/reader/chapter?edition=${encodeURIComponent(thisPlan.edition)}&book=${encodeURIComponent(thisPlan.book)}&chapter=${encodeURIComponent(chapter)}`);
    if(token!==epoch||thisPlan!==plan)return;
    if(!data?.verses?.length)throw Error(t('audio.noText'));
    const context={...data,book:typeof data.book==='object'?data.book.id:data.book};thisPlan.units=data.verses.map(v=>unitFromVerse(context,v));
    if(thisPlan.unitIndex===-1)thisPlan.unitIndex=thisPlan.units.length-1;preparing=false;renderStatus();
  }
  function schedule(){
    const token=++epoch;cancelJob();clearClip();generating=true;state=paused?'pausedPending':'generating';renderStatus();
    serial=serial.catch(()=>{}).then(async()=>{
      if(token!==epoch||!plan)return;
      let jobId=null;
      try{
        if(refreshPromise)await refreshPromise;
        if(token!==epoch||!plan)return;
        await ensureUnits(token);if(token!==epoch||!plan)return;
        const item=plan.units[plan.unitIndex];if(typeof item?.text!=='string'||!item.text.trim())throw Error(t('audio.noText'));if(item.text.length>25000)throw Error(t('audio.textTooLong'));
        currentItem=item;const selected=selectedVoice();if(!selected?.installed||selected.runtime_available===false)throw Object.assign(Error(),{code:'VOICE_NOT_INSTALLED_OR_CORRUPT'});
        const initial=await request('audio/synthesize',{provider:settings.provider,voice:settings.voice,text:item.text,speed:settings.speed});jobId=initial.id;
        if(token!==epoch){await request('job/cancel',{id:jobId}).catch(()=>{});await waitJob(initial).catch(()=>{});return;}
        activeJob=jobId;state=paused?'pausedPending':'generating';renderStatus();
        const result=await waitJob(initial);
        if(token!==epoch||!plan)return;
        const url=result.download_url||('/api/studio/audio/file?id='+encodeURIComponent(result.artifact_id));if(!url.startsWith('/api/studio/audio/file?id='))throw Error(t('audio.failed'));
        media.src=url;media.volume=settings.volume;clipEpoch=token;generating=false;preparing=false;highlight(item);
        if(paused){state='paused';renderStatus();return;}
        try{await media.play();if(token===epoch)state='playing';}catch{if(token===epoch){paused=true;state='ready';}}
        renderStatus();
      }catch(error){if(token===epoch){generating=false;preparing=false;paused=true;clearHighlight();issue(error);}}
      finally{if(activeJob===jobId)activeJob=null;if(token===epoch){generating=false;preparing=false;renderStatus();}}
    });
    return serial;
  }
  async function startPlan(value){stop();plan=value;paused=false;finished=false;await schedule();}
  async function play(selection=null){
    if(selection==null&&plan&&!finished){await resume();return;}
    if(selection==null&&plan&&finished){plan.unitIndex=0;plan.chapterIndex=0;if(plan.chapters.length>1)plan.units=null;paused=false;finished=false;await schedule();return;}
    const chosen=selection||getSelection();const units=selectionUnits(chosen);await startPlan({units,unitIndex:0,chapters:[],chapterIndex:0,followReader:false});
  }
  async function move(direction){
    if(!plan||preparing)return;const index=plan.unitIndex+direction;
    if(plan.units&&index>=0&&index<plan.units.length)plan.unitIndex=index;
    else if(plan.chapters.length&&plan.chapterIndex+direction>=0&&plan.chapterIndex+direction<plan.chapters.length){plan.chapterIndex+=direction;plan.units=null;plan.unitIndex=direction<0?-1:0;}
    else{if(direction>0){epoch++;cancelJob();media.pause();finished=true;generating=false;paused=false;state='finished';clearHighlight();renderStatus();}return;}
    finished=false;await schedule();
  }
  media.addEventListener('ended',()=>{if(plan&&clipEpoch===epoch&&!paused)move(1).catch(issue);});
  media.addEventListener('error',()=>{if(plan&&media.getAttribute('src')){paused=true;state='error';clearHighlight();renderStatus();}});
  provider.addEventListener('change',()=>{stop();settings.provider=provider.value;settings.voice=catalog.voices.find(v=>v.provider===provider.value&&v.installed&&v.runtime_available!==false)?.id||null;save();renderSelectors();});
  voice.addEventListener('change',()=>{stop();settings.voice=voice.value;save();});

  function renderScopes(){options(scopeField.input,['selection','verse','range','chapter','chapterrange','book'].map(v=>[v,t('audio.scope.'+v)]),settings.scope);}
  function showScope(){const value=scopeField.input.value;verseStart.label.hidden=value!=='range';verseEnd.label.hidden=value!=='range';chapterStart.label.hidden=value!=='chapterrange';chapterEnd.label.hidden=value!=='chapterrange';}
  function fillPlayback(){
    const current=reader.getCurrent();if(!current)return;
    renderScopes();const verses=current.verses||[],selected=reader.getSelection(),index=verses.findIndex(v=>v.reference===selected?.reference),start=Math.max(0,index);
    options(verseStart.input,verses.map((v,i)=>[i,v.reference||String(v.label??v.number)]),start);options(verseEnd.input,verses.map((v,i)=>[i,v.reference||String(v.label??v.number)]),start);
    const book=(reader.getCatalog()?.books||[]).find(b=>b.id===current.book),chapters=labels(book);options(chapterStart.input,chapters.map((v,i)=>[i,String(v)]),Math.max(0,chapters.findIndex(v=>String(v)===String(current.chapter))));options(chapterEnd.input,chapters.map((v,i)=>[i,String(v)]),chapters.length-1);
    speedField.input.value=settings.speed;volumeField.input.value=settings.volume;speedValue.textContent=settings.speed.toFixed(2)+'×';volumeValue.textContent=Math.round(settings.volume*100)+'%';showScope();
  }
  async function openPlayback(){selectionSnapshot=getSelection();fillPlayback();playback.open();}
  async function beginScope(){
    const current=reader.getCurrent();if(!current)throw Error(t('audio.noText'));const scope=scopeField.input.value;settings.scope=scope;save();let value;
    if(scope==='selection')value={units:selectionUnits(selectionSnapshot||getSelection()),unitIndex:0,chapters:[],chapterIndex:0,followReader:false};
    else if(scope==='verse'){const v=reader.getSelection()||current.verses[0];value={units:[unitFromVerse(current,v)],unitIndex:0,chapters:[],chapterIndex:0,followReader:false};}
    else if(scope==='range'){const from=Number(verseStart.input.value),to=Number(verseEnd.input.value);if(to<from)throw Error(t('audio.invalidRange'));value={units:current.verses.slice(from,to+1).map(v=>unitFromVerse(current,v)),unitIndex:0,chapters:[],chapterIndex:0,followReader:false};}
    else if(scope==='chapter')value={units:current.verses.map(v=>unitFromVerse(current,v)),unitIndex:0,chapters:[],chapterIndex:0,followReader:false};
    else{const book=(reader.getCatalog()?.books||[]).find(b=>b.id===current.book),all=labels(book);const from=scope==='book'?0:Number(chapterStart.input.value),to=scope==='book'?all.length-1:Number(chapterEnd.input.value);if(!all.length||to<from)throw Error(t('audio.invalidRange'));value={edition:editionId(current),book:current.book,chapters:all.slice(from,to+1),chapterIndex:0,unitIndex:0,units:null,followReader:true};}
    playback.close();await startPlan(value);
  }
  scopeField.input.addEventListener('change',showScope);
  speedField.input.addEventListener('input',()=>{settings.speed=Number(speedField.input.value);speedValue.textContent=settings.speed.toFixed(2)+'×';save();});
  speedField.input.addEventListener('change',()=>{if(plan)schedule();});
  volumeField.input.addEventListener('input',()=>{settings.volume=Number(volumeField.input.value);media.volume=settings.volume;volumeValue.textContent=Math.round(settings.volume*100)+'%';save();});

  async function settlePlayback(){stop();await serial.catch(()=>{});}
  async function manageInstall(voiceId){
    if(managerBusy)return;managerBusy=true;renderVoices();await settlePlayback();managerAbort=new AbortController();managerProgress.hidden=false;managerCancel.hidden=false;
    try{const initial=await request('voice/install',{voice:voiceId});managerJob=initial.id;await waitJob(initial,{signal:managerAbort.signal,onProgress:p=>{managerStatus.textContent=t('audio.downloading',{percent:p.total_bytes?Math.round(100*(p.downloaded_bytes||0)/p.total_bytes):0});if(p.total_bytes){managerProgress.max=p.total_bytes;managerProgress.value=p.downloaded_bytes||0;}}});managerStatus.textContent=t('audio.installed');await refreshVoices(true);}
    catch(error){managerStatus.textContent=explain(error);if(error.name!=='AbortError')notify(explain(error),true);}
    finally{managerJob=null;managerAbort=null;managerBusy=false;managerProgress.hidden=true;managerCancel.hidden=true;renderVoices();}
  }
  async function manageRemove(item){
    if(managerBusy)return;
    if(!window.confirm(t('audio.confirmRemove',{voice:item.name})))return;
    managerBusy=true;renderVoices();try{await settlePlayback();await request('voice/remove',{voice:item.id,confirmed:true});managerStatus.textContent=t('audio.removed');await refreshVoices(true);}finally{managerBusy=false;renderVoices();}
  }
  async function preview(item){
    if(managerBusy)return;
    if(refreshPromise)await refreshPromise;
    await settlePlayback();settings.provider=item.provider;settings.voice=item.id;save();renderSelectors();const code=language(item.language);if(!previewField.input.dataset.edited)previewField.input.value=t('audio.sample'+(code==='ro'?'Ro':code==='de'?'De':'En'));
    await play({blocks:[{text:previewField.input.value,reference:t('audio.preview')}],text:previewField.input.value});
  }
  previewField.input.addEventListener('input',()=>previewField.input.dataset.edited='true');
  function renderVoices(){
    const filter=voiceFilter.input.value.trim().toLocaleLowerCase(common.language());voiceList.replaceChildren();
    const list=catalog.voices.filter(v=>!filter||`${v.name} ${v.language} ${providerName(v.provider)}`.toLocaleLowerCase(common.language()).includes(filter));
    for(const item of list){const card=node('article',null,'studio-voice-card');card.dataset.provider=item.provider;card.dataset.voice=item.id;card.append(node('h3',item.name),node('p',`${providerName(item.provider)} · ${item.language}`),text('p',item.installed?'audio.available':'audio.notInstalled','meta'));const actions=node('div',null,'studio-actions');
      if(item.managed&&!item.installed){const install=button('audio.install',()=>manageInstall(item.id));install.dataset.voiceInstall=item.id;actions.append(install);}
      if(item.managed&&item.removable){const remove=button('audio.remove',()=>manageRemove(item));remove.dataset.voiceRemove=item.id;actions.append(remove);}
      if(item.installed&&item.runtime_available!==false){const previewButton=button('audio.preview',()=>preview(item));previewButton.dataset.voicePreview=item.id;actions.append(previewButton);}
      for(const control of actions.querySelectorAll('button'))control.disabled=managerBusy||refreshingVoices;
      if(isAndroid())card.append(text('p',item.network_required===true?'audio.networkVoice':item.bundled?'audio.bundledVoice':item.network_required===false?'audio.offlineVoice':'audio.voiceAvailabilityUnknown','meta'));
      if(item.license)card.append(node('p',item.license,'meta'));card.append(actions);voiceList.append(card);
    }
    if(!list.length)voiceList.append(text('p','audio.noVoices'));
  }
  voiceFilter.input.addEventListener('input',renderVoices);
  async function openVoices(){voicesDialog.open();managerStatus.textContent=t('common.loading');try{await refreshVoices(true);managerStatus.textContent='';}catch(error){managerStatus.textContent=explain(error);}}
  common.subscribe(()=>{for(const element of player.querySelectorAll('[data-audio-label]')){element.title=t(element.dataset.audioLabel);element.setAttribute('aria-label',t(element.dataset.audioLabel));}player.setAttribute('aria-label',t('audio.player'));managerProgress.setAttribute('aria-label',t('audio.downloadProgress'));renderSelectors();renderVoices();renderStatus();const old=scopeField.input.value;renderScopes();scopeField.input.value=old;});
  window.addEventListener('pagehide',stop);
  renderScopes();renderStatus();await refreshVoices();
  return{openVoices,openPlayback,play,pause,stop,refreshVoices,next:()=>move(1),previous:()=>move(-1),getState:()=>({state,provider:settings.provider,voice:settings.voice,speed:settings.speed,volume:settings.volume,paused,generating,activeJob,reference:currentItem?.reference||null,scope:settings.scope}),destroy(){stop();player.remove();voicesDialog.element.remove();playback.element.remove();}};
}
export default createAudioStudio;
