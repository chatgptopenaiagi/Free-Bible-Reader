import {clone,DEFAULT_PREFERENCES,STORAGE_KEY,decodePreferences,encodePreferences,validatePreferences} from './schema.js';
export function createPreferences(options={}) {
  const win=options.window??globalThis.window;
  const storageKey=options.storageKey??STORAGE_KEY;
  let storage=null,state=clone(DEFAULT_PREFERENCES),diagnostics=[],storageStatus='memory-only';
  const subscribers=new Set();
  try{storage=Object.hasOwn(options,'storage')?options.storage:win?.localStorage??null;if(storage)storageStatus='available';}
  catch{diagnostics.push({field:'storage',code:'STORAGE_UNAVAILABLE'});}
  function persist(){if(!storage)return;try{storage.setItem(storageKey,encodePreferences(state));storageStatus='available';}catch{storageStatus='memory-only';diagnostics.push({field:'storage',code:'STORAGE_WRITE_FAILED'});}}
  function publish(next,issues=[],save=true){
    const keys=Object.keys(DEFAULT_PREFERENCES).filter(key=>JSON.stringify(next[key])!==JSON.stringify(state[key]));
    diagnostics=issues.slice();state=next;if(save)persist();
    if(keys.length)for(const subscriber of [...subscribers])try{subscriber(clone(state),keys.slice());}catch{diagnostics.push({field:'subscriber',code:'SUBSCRIBER_ERROR'});}
    return clone(state);
  }
  if(storage)try {
    let text=storage.getItem(storageKey),oldKey=null;
    if(text===null)for(const key of ['biblia.ui.preferences.v1','biblia.ui.preferences','biblia-ui-preferences']){text=storage.getItem(key);if(text!==null){oldKey=key;break;}}
    if(text!==null){const decoded=decodePreferences(text);state=decoded.state;diagnostics=decoded.diagnostics;if(decoded.migrated||oldKey)persist();}
  }catch(error){const known=['UNSUPPORTED_VERSION','INVALID_JSON','INVALID_TYPE'].includes(error.message);if(!known)storageStatus='memory-only';diagnostics.push({field:'storage',code:known?error.message:'STORAGE_UNAVAILABLE'});}
  const onStorage=event=>{if(event.key!==storageKey)return;try{if(event.newValue===null)publish(clone(DEFAULT_PREFERENCES),[],false);else{const value=decodePreferences(event.newValue);publish(value.state,value.diagnostics,false);}}catch{diagnostics.push({field:'storage',code:'INVALID_JSON'});}};
  win?.addEventListener?.('storage',onStorage);
  return Object.freeze({
    get:()=>clone(state),
    set:patch=>{const value=validatePreferences(patch,state);return publish(value.state,value.diagnostics);},
    subscribe(fn){if(typeof fn!=='function')throw new TypeError('Subscriber must be a function');subscribers.add(fn);return()=>subscribers.delete(fn);},
    reset:()=>publish(clone(DEFAULT_PREFERENCES)),
    exportJSON:()=>encodePreferences(state),
    importJSON(text){const value=decodePreferences(text);return publish(value.state,value.diagnostics);},
    getDiagnostics:()=>clone(diagnostics),
    get storageStatus(){return storageStatus;},
    get storageKey(){return storageKey;},
    destroy(){win?.removeEventListener?.('storage',onStorage);subscribers.clear();},
  });
}
