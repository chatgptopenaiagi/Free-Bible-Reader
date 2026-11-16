export function captureSelection(reader){
  const current=reader.getCurrent();if(!current)return null;const selection=window.getSelection(),article=document.getElementById('reader-content');
  if(!selection?.rangeCount||selection.isCollapsed)return null;const range=selection.getRangeAt(0);
  if(!article.contains(range.startContainer)||!article.contains(range.endContainer))return null;
  const blocks=[];
  for(const paragraph of article.querySelectorAll('.scripture-verse')){
    const span=paragraph.querySelector('[data-source-data]');if(!span||!range.intersectsNode(span))continue;
    const part=document.createRange();part.selectNodeContents(span);
    if(span.contains(range.startContainer))part.setStart(range.startContainer,range.startOffset);
    if(span.contains(range.endContainer))part.setEnd(range.endContainer,range.endOffset);
    const chosen=part.toString();if(!chosen)continue;
    const prefix=document.createRange();prefix.selectNodeContents(span);prefix.setEnd(part.startContainer,part.startOffset);
    const start=prefix.toString().length;const verse=current.verses.find(v=>v.reference===paragraph.dataset.reference);
    if(!verse)continue;
    blocks.push({text:chosen,selected_text:chosen,original_text:verse.text,edition_id:current.edition.id,edition_name:current.edition.name,language:current.edition.language,book:current.book,chapter:current.chapter,verse_start:verse.nativeVerseStart??verse.number,verse_end:verse.nativeVerseEnd??verse.number,label:verse.label??String(verse.number),reference:verse.reference,sourceTextSha256:verse.text_sha256,start_utf16:start,end_utf16:start+chosen.length});
  }
  return blocks.length?{blocks,text:blocks.map(v=>v.text).join('\n'),edition_id:current.edition.id,book:current.book,chapter:current.chapter,reference:blocks[0].reference}:null;
}
export function verseBlock(current,verse){return{text:verse.text,selected_text:verse.text,edition_id:current.edition.id,edition_name:current.edition.name,language:current.edition.language,book:current.book,chapter:current.chapter,verse_start:verse.nativeVerseStart??verse.number,verse_end:verse.nativeVerseEnd??verse.number,label:verse.label??String(verse.number),reference:verse.reference,sourceTextSha256:verse.text_sha256,start_utf16:0,end_utf16:verse.text.length};}
export function selectedOrCurrent(reader){const current=reader.getCurrent();if(!current)return null;const selected=reader.getSelection()||current.verses[0];return selected?{blocks:[verseBlock(current,selected)],text:selected.text,edition_id:current.edition.id,book:current.book,chapter:current.chapter,reference:selected.reference}:null;}
