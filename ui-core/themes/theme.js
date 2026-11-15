import {PALETTES}from './palettes.js';
import {contrastReport,contrastingText,suggestColor}from './contrast.js';
import {applyTokens,colorTokenName,SAFETY_TOKENS}from '../tokens/index.js';
import {watchMedia,mediaMatches}from '../platform/capabilities.js';
const contrastColors={primary:'#ffff00',secondary:'#00ffff',accent:'#ffee00',background:'#000000',surface:'#000000',text:'#ffffff',muted:'#eeeeee',border:'#ffffff',selected:'#333333',control:'#111111',link:'#80dfff',highlight:'#ffee00',graphSelection:'#ffff00',crossReference:'#c5b5ff'};
const mix=(color,amount)=>'#'+[1,3,5].map(index=>Math.round(parseInt(color.slice(index,index+2),16)*(1-amount)+255*amount).toString(16).padStart(2,'0')).join('');
export function createTheme({preferences,root,window:win}) {
  let resolved=null,systemDark=mediaMatches(win,'(prefers-color-scheme: dark)');
  function apply() {
    const state=preferences.get();let mode=state.themeMode==='system'?(systemDark?'dark':'light'):state.themeMode;
    const palette=PALETTES.find(item=>item.id===state.colorPalette)??PALETTES[0];let colors={...palette.colors};
    if(mode==='dark') {
      for(const key of ['primary','secondary','accent','graphSelection','crossReference'])colors[key]=mix(colors[key],0.65);
      Object.assign(colors,{background:'#111820',surface:'#1b2530',text:'#f1f4f8',muted:'#bdc8d1',border:'#657584',selected:'#254760',control:'#293847',link:'#96ccff',highlight:'#5a480c'});
    }else if(mode==='sepia')Object.assign(colors,{background:'#f4ead7',surface:'#fff8e9',text:'#392e21',muted:'#62523b',border:'#b5a486',selected:'#e3d3b2',control:'#eadcc1',link:'#62421d',highlight:'#f3d88c'});
    else if(mode==='contrast')colors={...contrastColors};
    const customActive=mode!=='contrast'&&(mode==='custom'||state.colorPalette==='userCustom');
    if(customActive)Object.assign(colors,state.customColors);
    const tokens=Object.fromEntries(Object.entries(colors).map(([key,value])=>[colorTokenName(key),value]));
    Object.assign(tokens,{'--ui-on-primary':contrastingText(colors.primary),'--ui-control-text':contrastingText(colors.control),'--ui-highlight-text':contrastingText(colors.highlight),'--ui-focus':colors.link,'--ui-border-width':state.contrastPreference==='more'?'2px':'1px'});
    Object.assign(tokens,SAFETY_TOKENS);
    applyTokens(root,tokens);if(root?.dataset){root.dataset.uiTheme=mode;root.dataset.uiContrast=state.contrastPreference;root.dataset.uiPalette=state.colorPalette;}
    if(root?.style)root.style.colorScheme=mode==='dark'||mode==='contrast'?'dark':'light';
    resolved={requestedMode:state.themeMode,mode,palette:palette.id,colors,customActive,customSavedButNotApplied:mode==='contrast'&&Object.keys(state.customColors).length>0,contrast:contrastReport(colors,state.contrastPreference==='more'?7:4.5)};
    return JSON.parse(JSON.stringify(resolved));
  }
  const stopMedia=watchMedia(win,'(prefers-color-scheme: dark)',matches=>{systemDark=matches;apply();});
  const unsubscribe=preferences.subscribe(apply);apply();
  return Object.freeze({get:()=>JSON.parse(JSON.stringify(resolved)),apply,getContrastReport:()=>JSON.parse(JSON.stringify(resolved.contrast)),suggestContrast:(foreground,background,target=4.5)=>suggestColor(resolved.colors,foreground,background,target),destroy(){unsubscribe();stopMedia();}});
}
