import {FONT_OPTIONS}from './fonts.js';
import {applyTokens}from '../tokens/index.js';
import {watchMedia,mediaMatches}from '../platform/capabilities.js';
export function createTypography({preferences,root,window:win}) {
  let systemReduced=mediaMatches(win,'(prefers-reduced-motion: reduce)'),resolved;
  function apply(){
    const state=preferences.get(),interfaceFont=FONT_OPTIONS.find(font=>font.id===state.interfaceFont),scriptureFont=FONT_OPTIONS.find(font=>font.id===state.scriptureFont);
    const density={compact:0.8,comfortable:1,spacious:1.2}[state.displayDensity];
    const reduced=state.reducedMotion||systemReduced;
    const tokens={'--ui-interface-font':interfaceFont.family,'--ui-scripture-font':scriptureFont.family,'--ui-interface-font-size':`${16*state.interfaceFontScale}px`,'--ui-scripture-font-size':`${16*state.scriptureFontScale}px`,'--ui-interface-font-scale':state.interfaceFontScale,'--ui-scripture-font-scale':state.scriptureFontScale,'--ui-line-height':state.lineHeight,'--ui-paragraph-spacing':`${state.paragraphSpacing}em`,'--ui-reading-width':{narrow:'58ch',comfortable:'72ch',wide:'92ch'}[state.readingWidth],'--ui-density':density,'--ui-control-height':`${Math.round(44*density)}px`,'--ui-motion-duration':reduced?'0ms':'140ms'};
    for(const [index,size]of [0.25,0.5,0.75,1].entries())tokens[`--ui-space-${index+1}`]=`${size*density}rem`;
    applyTokens(root,tokens);if(root?.dataset){root.dataset.uiDensity=state.displayDensity;root.dataset.uiReducedMotion=String(reduced);}
    resolved={interfaceFont:state.interfaceFont,scriptureFont:state.scriptureFont,density:state.displayDensity,reducedMotion:reduced,systemReducedMotion:systemReduced,tokens};
    return JSON.parse(JSON.stringify(resolved));
  }
  const stopMedia=watchMedia(win,'(prefers-reduced-motion: reduce)',matches=>{systemReduced=matches;apply();});
  const unsubscribe=preferences.subscribe(apply);apply();
  return Object.freeze({get:()=>JSON.parse(JSON.stringify(resolved)),apply,destroy(){unsubscribe();stopMedia();}});
}
