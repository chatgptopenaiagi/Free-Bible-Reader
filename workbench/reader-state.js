/** Small, independently versioned navigation state. Never contains Scripture text. */
export const READER_STATE_KEY='free-bible-reader.position.v1';
export function validatePosition(value){
  if(!value||typeof value!=='object'||Array.isArray(value)||value.version!==1)return null;
  if(typeof value.edition!=='string'||!/^[A-Za-z0-9:_-]{1,80}$/.test(value.edition))return null;
  if(typeof value.book!=='string'||!/^[1-4]?[A-Za-z]{1,16}$/.test(value.book))return null;
  if(!Number.isInteger(value.chapter)||value.chapter<1||value.chapter>1000)return null;
  for(const key of ['verse','selectedVerse'])if(value[key]!=null&&(!Number.isInteger(value[key])||value[key]<1||value[key]>1000))return null;
  return {version:1,edition:value.edition,book:value.book,chapter:value.chapter,verse:value.verse??null,selectedVerse:value.selectedVerse??null};
}
export function createReaderState(options={}){
  let storage=null,value=null,status='memory-only';
  try{storage=Object.hasOwn(options,'storage')?options.storage:globalThis.window?.localStorage;if(storage){status='available';const raw=storage.getItem(READER_STATE_KEY);if(raw!==null)value=validatePosition(JSON.parse(raw));}}
  catch{status='memory-only';}
  return {get:()=>value?{...value}:null,save(position){const validated=validatePosition({version:1,...position});if(!validated)return false;value=validated;try{storage?.setItem(READER_STATE_KEY,JSON.stringify(value));}catch{status='memory-only';}return true;},get storageStatus(){return status;}};
}
/** Validates source-native book/chapter metadata without inventing verse equivalence. */
export function resolveCatalogPosition(position,catalog){
  const fallback=catalog.books.find(b=>b.id==='John')||catalog.books[0];
  const wanted=catalog.books.find(b=>b.id===position?.book),book=wanted||fallback;
  if(!book)throw new Error('Reader catalog contains no books');
  const requested=Number(position?.chapter)||1,chapter=wanted?Math.max(1,Math.min(requested,book.chapters.length)):1;
  return {edition:catalog.selected_edition||position?.edition||catalog.default_edition,book:book.id,chapter,verse:position?.verse??null,selectedVerse:position?.selectedVerse??null,adjusted:!wanted||chapter!==requested};
}
export function createRequestEpoch(){let current=0;return{next:()=>++current,isCurrent:token=>token===current,get current(){return current;}};}
