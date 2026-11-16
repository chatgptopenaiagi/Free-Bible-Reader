/** Query context belongs to the displayed result set, not subsequently edited controls. */
export function searchContext(input){
  const query=String(input.query??'').trim();
  if(query.length<2)return{error:'TOO_SHORT'};
  if(query.length>200)return{error:'TOO_LONG'};
  return {context:Object.freeze({query,edition:String(input.edition),book:input.book?String(input.book):null,limit:25})};
}
export function createReaderSearch({fetchPage,onResult=()=>{},onError=()=>{},onBusy=()=>{}}){
  let epoch=0,last=null;
  async function request(context,offset){
    const token=++epoch;onBusy(true,context);
    try{const data=await fetchPage({...context,offset});if(token!==epoch)return null;last={context,data};onResult(last);return last;}
    catch(error){if(token===epoch)onError(error,context);return null;}
    finally{if(token===epoch)onBusy(false,context);}
  }
  return{start(input){const parsed=searchContext(input);if(parsed.error){onError({validation:parsed.error});return Promise.resolve(null);}return request(parsed.context,0);},page(offset){if(!last||!Number.isInteger(offset)||offset<0)return Promise.resolve(null);return request(last.context,offset);},invalidate(){epoch++;last=null;onBusy(false);},getSnapshot(){return last?{context:{...last.context},data:last.data}:null;}};
}
