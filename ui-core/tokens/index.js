export const colorTokenName=key=>'--ui-'+key.replace(/[A-Z]/g,char=>'-'+char.toLowerCase());
export const SAFETY_TOKENS=Object.freeze({'--ui-safety-background':'#fff4d2','--ui-safety-text':'#332500','--ui-safety-border':'#7d6120','--ui-safety-control':'#ffffff','--ui-safety-focus':'#172f47'});
export function applyTokens(root,tokens) {
  if(!root?.style?.setProperty)return;
  for(const [name,value]of Object.entries(tokens))if(/^--ui-[a-z0-9-]+$/.test(name))root.style.setProperty(name,String(value));
}
