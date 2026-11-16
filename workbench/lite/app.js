/** Lite is a reading product, not a hidden desktop studio. The same services
 * supply unchanged, edition-specific Scripture to both Android products. */
const $=id=>document.getElementById(id);
const translations={
 en:{tagline:'A quiet place to read.',edition:'Bible translation',book:'Book',chapter:'Chapter',save:'Bookmark',previous:'‹ Previous',next:'Next ›',listen:'▶ Listen',stop:'■ Stop',search:'Search',results:'Search results',more:'More results',settings:'Reading settings',close:'Close',language:'Interface language',theme:'Appearance',light:'Light',dark:'Dark',system:'System',size:'Scripture text size',voice:'Voice',speed:'Playback speed',voices:'Device voice settings',saved:'Bookmarks',query:'Words or phrase',loading:'Opening Scripture…',error:'This action could not be completed. Please try again.',noResults:'No matching passages.',savedDone:'Bookmark saved.',voiceMissing:'No installed voice matches this Bible. Open device voice settings to install a voice.',voiceOffline:'Offline device voice',voiceNetwork:'This device voice may need a network connection.',noVoice:'No device voice available',partial:'Romanian draft New Testament · 27 books. Old Testament books are not included.',offline:'Bundled text • available offline',reading:'Reading',matches:'matches',stopped:'Narration stopped.'},
 ro:{tagline:'Un loc liniștit pentru lectură.',edition:'Traducerea Bibliei',book:'Cartea',chapter:'Capitolul',save:'Semn de carte',previous:'‹ Înapoi',next:'Înainte ›',listen:'▶ Ascultă',stop:'■ Oprește',search:'Caută',results:'Rezultatele căutării',more:'Mai multe rezultate',settings:'Setări de lectură',close:'Închide',language:'Limba interfeței',theme:'Aspect',light:'Luminos',dark:'Întunecat',system:'Sistem',size:'Mărimea textului biblic',voice:'Vocea',speed:'Viteza lecturii',voices:'Vocile dispozitivului',saved:'Semne de carte',query:'Cuvinte sau expresie',loading:'Se deschide Scriptura…',error:'Acțiunea nu a putut fi finalizată. Încearcă din nou.',noResults:'Nu au fost găsite pasaje.',savedDone:'Semn de carte salvat.',voiceMissing:'Nu există o voce instalată pentru această Biblie. Instalează o voce din setările dispozitivului.',voiceOffline:'Voce locală, fără internet',voiceNetwork:'Această voce poate necesita o conexiune la internet.',noVoice:'Nicio voce disponibilă',partial:'Noul Testament românesc, ediție în lucru · 27 de cărți. Vechiul Testament nu este inclus.',offline:'Text inclus • disponibil fără internet',reading:'Lectură',matches:'rezultate',stopped:'Lectura audio a fost oprită.'},
 de:{tagline:'Ein ruhiger Ort zum Lesen.',edition:'Bibelübersetzung',book:'Buch',chapter:'Kapitel',save:'Lesezeichen',previous:'‹ Zurück',next:'Weiter ›',listen:'▶ Vorlesen',stop:'■ Stopp',search:'Suchen',results:'Suchergebnisse',more:'Weitere Ergebnisse',settings:'Leseeinstellungen',close:'Schließen',language:'Sprache der Oberfläche',theme:'Darstellung',light:'Hell',dark:'Dunkel',system:'System',size:'Schriftgröße des Bibeltextes',voice:'Stimme',speed:'Lesegeschwindigkeit',voices:'Stimmen des Geräts',saved:'Lesezeichen',query:'Wörter oder Ausdruck',loading:'Bibeltext wird geöffnet…',error:'Die Aktion konnte nicht abgeschlossen werden. Bitte erneut versuchen.',noResults:'Keine passenden Bibelstellen.',savedDone:'Lesezeichen gespeichert.',voiceMissing:'Keine installierte Stimme passt zu dieser Bibel. Installieren Sie eine Stimme in den Geräteeinstellungen.',voiceOffline:'Offline-Stimme des Geräts',voiceNetwork:'Diese Stimme benötigt möglicherweise eine Internetverbindung.',noVoice:'Keine Stimme verfügbar',partial:'Rumänischer Entwurf des Neuen Testaments · 27 Bücher. Das Alte Testament ist nicht enthalten.',offline:'Enthaltener Text • offline verfügbar',reading:'Lesen',matches:'Treffer',stopped:'Vorlesen beendet.'}
};
const KEY='free-bible-reader.lite.v1';
const defaults={edition:'web',book:'John',chapter:1,verse:1,scrollVerse:1,language:'en',theme:'system',fontSize:20,speed:1,voice:null,bookmarks:[]};
let state={...defaults};
try{const raw=JSON.parse(localStorage.getItem(KEY)||'{}');for(const key of Object.keys(defaults))if(Object.hasOwn(raw,key))state[key]=raw[key];}catch{}
if(!Object.hasOwn(translations,state.language))state.language='en';
if(!['light','dark','system'].includes(state.theme))state.theme='system';
state.fontSize=Math.min(32,Math.max(16,Number(state.fontSize)||20));state.speed=Math.min(2,Math.max(.5,Number(state.speed)||1));
state.bookmarks=Array.isArray(state.bookmarks)?state.bookmarks.filter(x=>x&&typeof x.book==='string'&&typeof x.edition==='string'&&Number.isInteger(x.chapter)).slice(0,200):[];
let catalog=null,current=null,sequence=0,voices=[],speechEpoch=0,activeJob=null,searchOffset=0,searchQuery='';
const t=key=>translations[state.language][key]||translations.en[key]||key;
const message=(key,extra='')=>{$('status').textContent=t(key)+(extra?' '+extra:'');};
function persist(){try{localStorage.setItem(KEY,JSON.stringify(state));}catch{}}
function localize(){document.documentElement.lang=state.language;for(const node of document.querySelectorAll('[data-t]'))node.textContent=t(node.dataset.t);$('tagline').textContent=t('tagline');$('settings').ariaLabel=t('settings');$('language').value=state.language;renderNote();renderBookmarks();renderVoice();}
function theme(){document.documentElement.dataset.theme=state.theme==='system'?(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'):state.theme;document.documentElement.style.setProperty('--font',`${state.fontSize}px`);$('theme').value=state.theme;$('font-size').value=state.fontSize;$('speed').value=state.speed;}
function element(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}
function options(select,items,value){select.replaceChildren(...items.map(([id,label])=>{const option=element('option',label);option.value=id;return option;}));if(value!==undefined)select.value=String(value);}
async function api(path,body){const result=await fetch(path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const value=await result.json();if(!result.ok)throw new Error(value.error||value.code||'REQUEST_FAILED');return value;}
async function job(path,body){let value=await api(path,body);activeJob=value.id;while(['QUEUED','RUNNING'].includes(value.state)){await new Promise(resolve=>setTimeout(resolve,140));value=await api('/api/studio/job?id='+value.id);}activeJob=null;if(value.state!=='COMPLETE')throw new Error(value.error?.message||value.state);return value.result;}
function renderNote(){$('edition-note').textContent=current?.edition?.id==='ronbl'?t('partial'):t('offline');}
function selectVerse(number,scroll=false){state.verse=number;for(const node of $('verses').children)node.dataset.selected=String(node.dataset.verse===String(number));persist();if(scroll)document.getElementById('verse-'+number)?.scrollIntoView({block:'center'});}
function render(){
 $('title').textContent=`${current.book.name} ${current.chapter}`;$('source').textContent=current.edition.name;
 $('verses').replaceChildren(...current.verses.map(verse=>{const p=element('p');p.id='verse-'+verse.number;p.dataset.verse=verse.number;p.tabIndex=0;const n=element('span',String(verse.number));n.className='verse-number';p.append(n,document.createTextNode(verse.text));p.addEventListener('click',()=>selectVerse(verse.number));p.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectVerse(verse.number);}});return p;}));
 $('previous').disabled=!current.previous;$('next').disabled=!current.next;renderNote();selectVerse(state.verse||current.verses[0]?.number||1);$('status').textContent='';
}
async function open(edition=state.edition,book=state.book,chapter=state.chapter,{verse=1,restore=false,position=verse}={}){
 const request=++sequence;stop(false);message('loading');
 try{
  const data=await api('/api/reader/catalog?edition='+encodeURIComponent(edition));if(request!==sequence)return;
  const chosen=data.books.find(b=>b.id===book)||data.books[0];if(!chosen)throw new Error('NO_BOOKS');
  const chapters=chosen.chapter_labels||chosen.chapters.map((_,i)=>i+1);chapter=chapters.some(c=>String(c)===String(chapter))?chapter:chapters[0];
  const passage=await api('/api/reader/chapter?'+new URLSearchParams({edition,book:chosen.id,chapter}));if(request!==sequence)return;
  catalog=data;current=passage;state={...state,edition,book:chosen.id,chapter,verse,scrollVerse:position};
  options($('edition'),data.editions.map(e=>[e.id,e.name]),edition);options($('book'),data.books.map(b=>[b.id,b.name]),chosen.id);options($('chapter'),chapters.map(c=>[c,String(c)]),chapter);
  render();persist();if(restore&&String(position)!=='1')requestAnimationFrame(()=>document.getElementById('verse-'+position)?.scrollIntoView({block:'start'}));else window.scrollTo(0,0);renderVoice();
 }catch(error){if(request===sequence)message('error');console.error('Reading action failed',error.message);}
}
$('navigation').addEventListener('submit',event=>event.preventDefault());
$('edition').addEventListener('change',()=>open($('edition').value,state.book,state.chapter,{verse:state.verse,restore:true}));
$('book').addEventListener('change',()=>open(state.edition,$('book').value,1));$('chapter').addEventListener('change',()=>open(state.edition,state.book,Number($('chapter').value)));
for(const direction of ['previous','next'])$(direction).addEventListener('click',()=>{if(current?.[direction])open(state.edition,current[direction].book,current[direction].chapter);});
function renderBookmarks(){const list=$('bookmarks');list.replaceChildren(...state.bookmarks.map(item=>{const button=element('button',`${item.edition.toUpperCase()} · ${item.book} ${item.chapter}:${item.verse||1}`);button.type='button';button.addEventListener('click',()=>{$('settings-dialog').close();open(item.edition,item.book,item.chapter,{verse:item.verse,restore:true});});return button;}));}
$('bookmark').addEventListener('click',()=>{if(!current)return;const {edition,book,chapter,verse}=state;state.bookmarks=state.bookmarks.filter(x=>!(x.edition===edition&&x.book===book&&x.chapter===chapter&&x.verse===verse));state.bookmarks.unshift({edition,book,chapter,verse});state.bookmarks=state.bookmarks.slice(0,200);persist();renderBookmarks();message('savedDone');});
$('settings').addEventListener('click',async()=>{$('settings-dialog').showModal();try{const response=await api('/api/studio/voices');voices=(response.voices||[]).filter(v=>v.installed&&v.runtime_available!==false);renderVoice();}catch{voices=[];renderVoice();}});
for(const key of ['language','theme','font-size','speed'])$(key).addEventListener('input',()=>{const name=key==='font-size'?'fontSize':key;state[name]=['font-size','speed'].includes(key)?Number($(key).value):$(key).value;persist();theme();localize();});
matchMedia('(prefers-color-scheme:dark)').addEventListener?.('change',theme);
function speechLanguage(value){const lang=String(value||'').split(/[-_]/)[0];return ['ron','rum'].includes(lang)?'ro':lang==='eng'?'en':lang==='deu'?'de':lang;}
function chosenVoice(){const wanted=speechLanguage(current?.edition?.language);return voices.find(v=>v.id===state.voice)||voices.find(v=>speechLanguage(v.language)===wanted&&!v.network_required)||voices.find(v=>speechLanguage(v.language)===wanted);}
function renderVoice(){const selected=chosenVoice();options($('voice'),voices.length?voices.map(v=>[v.id,`${v.language} · ${v.name}`]):[['',t('noVoice')]],selected?.id);$('voice-info').textContent=selected?t(selected.network_required?'voiceNetwork':'voiceOffline'):t('voiceMissing');}
$('voice').addEventListener('change',()=>{state.voice=$('voice').value;persist();renderVoice();});
$('voice-settings').addEventListener('click',()=>api('/api/studio/android-voices',{}).catch(()=>message('error')));
function stop(announce=true){speechEpoch++;$('audio').pause();$('audio').removeAttribute('src');$('audio').load();if(activeJob)api('/api/studio/job/cancel',{id:activeJob}).catch(()=>{});for(const p of $('verses').children)p.removeAttribute('data-speaking');$('stop').hidden=true;$('play').hidden=false;if(announce)message('stopped');}
$('stop').addEventListener('click',()=>stop());
$('play').addEventListener('click',async()=>{
 stop(false);const epoch=speechEpoch;if(!current)return;
 try{if(!voices.length)voices=(await api('/api/studio/voices')).voices.filter(v=>v.installed&&v.runtime_available!==false);const voice=chosenVoice();if(!voice){message('voiceMissing');return;}
 $('play').hidden=true;$('stop').hidden=false;
 const begin=Math.max(0,current.verses.findIndex(v=>String(v.number)===String(state.verse)));
 for(const verse of current.verses.slice(begin)){
  if(epoch!==speechEpoch)return;selectVerse(verse.number,true);const p=document.getElementById('verse-'+verse.number);p.dataset.speaking='true';
  const result=await job('/api/studio/audio/synthesize',{provider:voice.provider,voice:voice.id,text:verse.text,speed:state.speed});if(epoch!==speechEpoch)return;
  const audio=$('audio');audio.src=result.download_url;await audio.play();await new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=()=>reject(new Error('PLAYBACK_FAILED'));const timer=setInterval(()=>{if(epoch!==speechEpoch){clearInterval(timer);resolve();}},150);audio.addEventListener('ended',()=>clearInterval(timer),{once:true});});p.removeAttribute('data-speaking');
 }
 if(epoch===speechEpoch)stop(false);
 }catch(error){if(epoch===speechEpoch){stop(false);message('error');}console.error('Narration unavailable',error.message);}
});
$('search-open').addEventListener('click',()=>{$('search-dialog').showModal();$('query').focus();});$('search-close').addEventListener('click',()=>$('search-dialog').close());
async function search(append=false){
 if(!append){searchOffset=0;searchQuery=$('query').value.trim();$('result-list').replaceChildren();}if(!searchQuery)return;
 $('more').disabled=true;message('loading');
 try{const response=await api('/api/reader/search',{query:searchQuery,edition:state.edition,limit:25,offset:searchOffset});
 $('search-dialog').close();$('results').hidden=false;for(const result of response.results||[]){const card=element('div');const button=element('button',`${result.book} ${result.chapter}:${result.verse}`);button.type='button';button.addEventListener('click',()=>{open(result.edition||state.edition,result.book,Number(result.chapter),{verse:result.verse,restore:true});$('results').hidden=true;});card.append(button,element('p',result.text));$('result-list').append(card);}searchOffset+=(response.results||[]).length;$('more').hidden=searchOffset>=response.total;message(response.total?'matches':'noResults',response.total?String(response.total):'');if(!append)$('results').scrollIntoView({block:'start'});
 }catch{message('error');}finally{$('more').disabled=false;}
}
$('search-form').addEventListener('submit',event=>{event.preventDefault();search();});$('more').addEventListener('click',()=>search(true));
addEventListener('pagehide',()=>{stop(false);persist();});
document.addEventListener('scroll',()=>{if(!current)return;const first=[...$('verses').children].find(p=>p.getBoundingClientRect().bottom>40);if(first){state.scrollVerse=Number(first.dataset.verse)||first.dataset.verse;persist();}},{passive:true});
theme();localize();await open(state.edition,state.book,state.chapter,{verse:state.verse,position:state.scrollVerse||state.verse,restore:true});
