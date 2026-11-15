const MOBILE_QUERY='(max-width: 760px)';
export function isMobileViewport(win=globalThis.window){
  try{if(typeof win?.matchMedia==='function')return Boolean(win.matchMedia(MOBILE_QUERY).matches);}catch{/* Continue with measured width. */}
  return Number.isFinite(win?.innerWidth)&&win.innerWidth<=760;
}
export function watchViewport(callback,win=globalThis.window){
  let media;try{if(typeof win?.matchMedia==='function')media=win.matchMedia(MOBILE_QUERY);}catch{/* A resize listener is sufficient. */}
  if(typeof media?.addEventListener==='function'){media.addEventListener('change',callback);return()=>media.removeEventListener?.('change',callback);}
  if(typeof media?.addListener==='function'){media.addListener(callback);return()=>media.removeListener?.(callback);}
  win?.addEventListener?.('resize',callback);return()=>win?.removeEventListener?.('resize',callback);
}
