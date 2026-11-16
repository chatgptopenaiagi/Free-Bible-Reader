/** Small, independently versioned navigation state. Never contains Scripture text. */
export const READER_STATE_KEY='free-bible-reader.position.v1';
export const validNativeLabel=value=>Number.isInteger(value)?value>=0&&value<=10000:typeof value==='string'&&value.length>0&&value.length<=80&&!/[\x00-\x1f\x7f]/.test(value);
export const nativeChapters=book=>book?.chapter_labels||book?.chapters?.map((_,i)=>i+1)||[];
export function validatePosition(value){
  if(!value||typeof value!=='object'||Array.isArray(value)||value.version!==1)return null;
  if(typeof value.edition!=='string'||!/^[A-Za-z0-9:_-]{1,80}$/.test(value.edition))return null;
  if(typeof value.book!=='string'||value.book.length<1||value.book.length>120||/[\x00-\x1f\x7f/\\]/.test(value.book))return null;
  if(!validNativeLabel(value.chapter))return null;
  for(const key of ['verse','selectedVerse'])if(value[key]!=null&&!validNativeLabel(value[key]))return null;
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
  const labels=nativeChapters(book),requested=position?.chapter??labels[0]??1;
  const exact=labels.find(label=>String(label)===String(requested));
  const chapter=wanted&&exact!==undefined?exact:labels[0]??1;
  return {edition:catalog.selected_edition||position?.edition||catalog.default_edition,book:book.id,chapter,verse:position?.verse??null,selectedVerse:position?.selectedVerse??null,adjusted:!wanted||String(chapter)!==String(requested)};
}
export function createRequestEpoch(){let current=0;return{next:()=>++current,isCurrent:token=>token===current,get current(){return current;}};}
