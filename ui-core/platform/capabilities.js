export function mediaMatches(win,query) {try{return Boolean(win?.matchMedia?.(query)?.matches);}catch{return false;}}
export function watchMedia(win,query,callback) {
  let media;try{media=win?.matchMedia?.(query);}catch{return()=>{};}
  if(!media)return()=>{};
  const handler=event=>callback(Boolean(event.matches));
  if(media.addEventListener){media.addEventListener('change',handler);return()=>media.removeEventListener('change',handler);}
  if(media.addListener){media.addListener(handler);return()=>media.removeListener(handler);}
  return()=>{};
}
export function createCapabilities({window:win,root,preferences}) {
  const matches=query=>mediaMatches(win,query);
  return Object.freeze({hasDOM:Boolean(root?.style?.setProperty),hasMatchMedia:typeof win?.matchMedia==='function',
    get storageAvailable(){return preferences.storageStatus==='available';},get storageStatus(){return preferences.storageStatus;},
    get systemDark(){return matches('(prefers-color-scheme: dark)');},get systemReducedMotion(){return matches('(prefers-reduced-motion: reduce)');},
    get forcedColors(){return matches('(forced-colors: active)');}});
}
