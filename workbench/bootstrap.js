/** Dependency-free startup feedback. Recovery is an explicit full-page reload. */
(async()=>{
  const surface=document.getElementById('startup-status');
  const message=document.getElementById('startup-message');
  const retry=document.getElementById('startup-retry');
  const title=document.getElementById('startup-title');
  if(!surface||!message||!retry||!title)return;
  const supported=new Set(['en','ro','de']);
  const messages={
    en:{title:'Starting FREE BIBLE READER',starting:'Loading the offline reader…',slow:'The reader is taking longer to start. Keep the companion window open. You can retry if this message remains.',error:'The reader could not start because a local application file could not be loaded. Keep the companion window open and choose Retry.',retry:'Retry startup',help:'Retry reloads this page without clearing saved settings or reading position.'},
    ro:{title:'Pornire FREE BIBLE READER',starting:'Se încarcă cititorul offline…',slow:'Pornirea cititorului durează mai mult. Păstrați fereastra aplicației deschisă. Puteți reîncerca dacă acest mesaj persistă.',error:'Cititorul nu a putut porni deoarece un fișier local al aplicației nu a putut fi încărcat. Păstrați fereastra aplicației deschisă și reîncercați.',retry:'Reîncearcă pornirea',help:'Reîncercarea reîncarcă pagina fără a șterge setările sau poziția de lectură salvate.'},
    de:{title:'FREE BIBLE READER wird gestartet',starting:'Der Offline-Bibelleser wird geladen…',slow:'Der Start dauert länger. Lassen Sie das Begleitfenster geöffnet. Wenn diese Meldung bleibt, können Sie es erneut versuchen.',error:'Der Bibelleser konnte nicht starten, weil eine lokale Anwendungsdatei nicht geladen werden konnte. Lassen Sie das Begleitfenster geöffnet und versuchen Sie es erneut.',retry:'Start erneut versuchen',help:'Ein erneuter Versuch lädt diese Seite neu, ohne gespeicherte Einstellungen oder die Leseposition zu löschen.'},
  };
  function language(){
    const requested=new URL(location.href).searchParams.get('lang');
    if(supported.has(requested))return requested;
    try{
      const raw=localStorage.getItem('biblia.ui.preferences.v2');
      if(typeof raw==='string'&&raw.length<=65536){
        const saved=JSON.parse(raw);
        if(saved&&typeof saved==='object'&&!Array.isArray(saved)&&saved.version===2&&saved.format==='biblia-ui-preferences'&&saved.preferences&&typeof saved.preferences==='object'&&!Array.isArray(saved.preferences)&&supported.has(saved.preferences.interfaceLanguage))return saved.preferences.interfaceLanguage;
      }
    }catch{/* Startup feedback must work when browser storage is unavailable. */}
    return supported.has(document.documentElement.lang)?document.documentElement.lang:'en';
  }
  const locale=language(),text=messages[locale];
  surface.lang=locale;
  title.textContent=text.title;
  retry.textContent=text.retry;
  retry.title=text.help;
  retry.href=location.href;
  retry.addEventListener('click',event=>{event.preventDefault();location.reload();});
  message.textContent=text.starting;
  surface.dataset.state='loading';
  surface.setAttribute('aria-busy','true');
  const slow=setTimeout(()=>{message.textContent=text.slow;surface.dataset.state='slow';},12000);
  try{
    await import('/app.js');
    clearTimeout(slow);
    surface.setAttribute('aria-busy','false');
    surface.dataset.state='ready';
    surface.hidden=true;
  }catch(error){
    clearTimeout(slow);
    surface.setAttribute('aria-busy','false');
    surface.setAttribute('role','alert');
    surface.dataset.state='error';
    message.textContent=text.error;
    try{surface.focus();}catch{/* The visible reload link remains usable. */}
    console.error('[FREE BIBLE READER startup]',error);
  }
})();
