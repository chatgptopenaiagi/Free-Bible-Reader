/** Native dialogs remain preferred; the fallback needs no polyfill or remote dependency. */
export function createDialogController(dialog){
  let fallback=false,backdrop=null,previous=[],savedRole=null,savedModal=null;
  const doc=dialog.ownerDocument;
  const isOpen=()=>dialog.hasAttribute('open');
  const focusable=()=>[...dialog.querySelectorAll('button,input,select,textarea,a[href],[tabindex]')].filter(node=>!node.disabled&&!node.hidden&&node.tabIndex>=0&&!node.closest('[inert]')&&node.getClientRects().length);
  function keydown(event){if(!fallback)return;if(event.key==='Escape'){event.preventDefault();event.stopPropagation();close();return;}if(event.key!=='Tab')return;const nodes=focusable(),first=nodes[0],last=nodes.at(-1);if(!first){event.preventDefault();dialog.focus();return;}if(!dialog.contains(doc.activeElement)){event.preventDefault();(event.shiftKey?last:first).focus();}else if(event.shiftKey&&doc.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&doc.activeElement===last){event.preventDefault();first.focus();}}
  function focusin(event){if(fallback&&!dialog.contains(event.target))(focusable()[0]||dialog).focus();}
  function open(){if(isOpen())return;if(typeof dialog.showModal==='function'&&typeof dialog.close==='function'){try{dialog.showModal();return;}catch{/* Fall back to an ordinary accessible fixed dialog. */}}
    fallback=true;savedRole=dialog.getAttribute('role');savedModal=dialog.getAttribute('aria-modal');dialog.setAttribute('open','');dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');dialog.classList.add('dialog-fallback');dialog.tabIndex=-1;
    backdrop=doc.createElement('div');backdrop.className='dialog-fallback-backdrop';backdrop.setAttribute('aria-hidden','true');dialog.before(backdrop);backdrop.addEventListener('click',close);
    previous=[...doc.body.children].filter(node=>node!==dialog&&node!==backdrop).map(node=>({node,inert:node.inert}));for(const {node}of previous)node.inert=true;
    doc.addEventListener('keydown',keydown,true);doc.addEventListener('focusin',focusin,true);(focusable()[0]||dialog).focus();
  }
  function close(){if(!isOpen())return;if(!fallback&&typeof dialog.close==='function'){dialog.close();return;}fallback=false;doc.removeEventListener('keydown',keydown,true);doc.removeEventListener('focusin',focusin,true);dialog.removeAttribute('open');dialog.classList.remove('dialog-fallback');if(savedRole===null)dialog.removeAttribute('role');else dialog.setAttribute('role',savedRole);if(savedModal===null)dialog.removeAttribute('aria-modal');else dialog.setAttribute('aria-modal',savedModal);for(const {node,inert}of previous)node.inert=inert;previous=[];backdrop?.remove();backdrop=null;dialog.dispatchEvent(new Event('close'));}
  return Object.freeze({open,close,isOpen,get usingFallback(){return fallback;}});
}
