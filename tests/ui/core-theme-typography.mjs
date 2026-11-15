import test from 'node:test';
import assert from 'node:assert/strict';
import {createUICore,THEME_MODES,PALETTES,COLOR_FIELDS,FONT_OPTIONS,contrastRatio,SAFETY_TOKENS}from '../../ui-core/index.js';

function platform(){
  const tokens=new Map(),queries=new Map();
  const root={dataset:{},style:{setProperty:(key,value)=>tokens.set(key,value)}};
  const win={document:{documentElement:root},matchMedia(query){if(!queries.has(query)){const callbacks=new Set();queries.set(query,{matches:false,addEventListener:(_,fn)=>callbacks.add(fn),removeEventListener:(_,fn)=>callbacks.delete(fn),change(value){this.matches=value;for(const fn of callbacks)fn({matches:value});},callbacks});}return queries.get(query);}};
  return{tokens,queries,root,win};
}
test('all six themes, seven palettes and fourteen strict categories are present',()=>{
  assert.equal(THEME_MODES.length,6);assert.equal(PALETTES.length,7);assert.equal(COLOR_FIELDS.length,14);
  for(const palette of PALETTES)assert.deepEqual(Object.keys(palette.colors).sort(),[...COLOR_FIELDS].sort());
});
test('theme changes apply real token values without reload',()=>{
  const env=platform(),core=createUICore({window:env.win,storage:null});const light=env.tokens.get('--ui-background');
  core.preferences.set({themeMode:'dark'});assert.notEqual(env.tokens.get('--ui-background'),light);assert.equal(env.root.dataset.uiTheme,'dark');assert.equal(env.root.style.colorScheme,'dark');
  core.preferences.set({themeMode:'sepia'});assert.equal(env.tokens.get('--ui-background'),'#f4ead7');core.destroy();
});
test('all palettes change the source token set immediately',()=>{
  const env=platform(),core=createUICore({window:env.win,storage:null});
  for(const palette of PALETTES){core.preferences.set({colorPalette:palette.id});assert.equal(env.tokens.get('--ui-primary'),palette.colors.primary);}
  core.destroy();
});
test('system scheme responds to matchMedia and cleans up listeners',()=>{
  const env=platform(),core=createUICore({window:env.win,storage:null});core.preferences.set({themeMode:'system'});
  const scheme=env.queries.get('(prefers-color-scheme: dark)');scheme.change(true);assert.equal(core.theme.get().mode,'dark');assert.equal(core.preferences.get().themeMode,'system');
  scheme.change(false);assert.equal(core.theme.get().mode,'light');core.destroy();assert.equal(scheme.callbacks.size,0);
});
test('custom low contrast warns and suggestions preserve original user colors',()=>{
  const env=platform(),core=createUICore({window:env.win,storage:null});
  core.preferences.set({themeMode:'custom',customColors:{text:'#eeeeee',background:'#ffffff',surface:'#ffffff'}});
  assert.ok(core.theme.getContrastReport().warnings.some(w=>w.foreground==='text'));
  const suggestion=core.theme.suggestContrast('text','background');assert.equal(suggestion.suggested,'#000000');assert.equal(suggestion.passes,true);
  assert.equal(core.preferences.get().customColors.text,'#eeeeee');assert.equal(env.tokens.get('--ui-text'),'#eeeeee');core.destroy();
  for(const[key,value]of Object.entries(SAFETY_TOKENS))assert.equal(env.tokens.get(key),value);
  assert.ok(contrastRatio(SAFETY_TOKENS['--ui-safety-text'],SAFETY_TOKENS['--ui-safety-background'])>=4.5);
});
test('dedicated contrast mode meets AA across all checked text pairs and preserves saved custom values',()=>{
  const env=platform(),core=createUICore({window:env.win,storage:null});
  core.preferences.set({themeMode:'contrast',colorPalette:'userCustom',customColors:{text:'#111111',background:'#111111'},contrastPreference:'more'});
  const report=core.theme.getContrastReport();assert.equal(report.passes,true);assert.ok(report.pairs.every(pair=>pair.ratio>=7));
  assert.equal(core.preferences.get().customColors.text,'#111111');assert.equal(core.theme.get().customSavedButNotApplied,true);assert.equal(env.tokens.get('--ui-border-width'),'2px');core.destroy();
});
test('WCAG ratio endpoints and no false suggestion guarantee',()=>{
  assert.equal(contrastRatio('#000000','#ffffff'),21);assert.equal(contrastRatio('#222222','#222222'),1);
  const core=createUICore({storage:null});assert.throws(()=>core.theme.suggestContrast('unknown','background'),/UNKNOWN_COLOR_FIELD/);core.destroy();
});
test('typography scales, line height, paragraphs and measure autoapply',()=>{
  const env=platform(),core=createUICore({window:env.win,storage:null});
  core.preferences.set({interfaceFont:'system',scriptureFont:'palatino',interfaceFontScale:1.25,scriptureFontScale:1.5,lineHeight:2,paragraphSpacing:1.75,readingWidth:'wide'});
  assert.equal(env.tokens.get('--ui-interface-font-size'),'20px');assert.equal(env.tokens.get('--ui-scripture-font-size'),'24px');
  assert.equal(env.tokens.get('--ui-line-height'),'2');assert.equal(env.tokens.get('--ui-paragraph-spacing'),'1.75em');assert.equal(env.tokens.get('--ui-reading-width'),'92ch');
  assert.ok(env.tokens.get('--ui-scripture-font').includes('Palatino'));core.destroy();
});
test('all font options are allowlisted CSS fallback stacks',()=>{
  const env=platform(),core=createUICore({window:env.win,storage:null});
  for(const font of FONT_OPTIONS){core.preferences.set({interfaceFont:font.id,scriptureFont:font.id});assert.equal(env.tokens.get('--ui-interface-font'),font.family);assert.equal(env.tokens.get('--ui-scripture-font'),font.family);}
  assert.ok(FONT_OPTIONS.some(font=>font.id==='consolas'&&font.family.includes('ui-monospace')));
  assert.ok(FONT_OPTIONS.every(font=>font.family.includes('Nirmala UI')&&font.family.includes('Segoe UI Historic')));
  core.destroy();
});
test('density and reduced motion respect user and OS preferences',()=>{
  const env=platform(),core=createUICore({window:env.win,storage:null});core.preferences.set({displayDensity:'compact',reducedMotion:true});
  assert.equal(env.tokens.get('--ui-density'),'0.8');assert.equal(env.tokens.get('--ui-motion-duration'),'0ms');
  core.preferences.set({reducedMotion:false});assert.equal(env.tokens.get('--ui-motion-duration'),'140ms');
  env.queries.get('(prefers-reduced-motion: reduce)').change(true);assert.equal(env.tokens.get('--ui-motion-duration'),'0ms');assert.equal(core.capabilities.systemReducedMotion,true);core.destroy();
});
test('missing or blocked DOM/media APIs remain functional',()=>{
  const core=createUICore({window:{matchMedia(){throw new Error('blocked');}},storage:null});
  core.preferences.set({themeMode:'system',scriptureFontScale:1.4});assert.equal(core.theme.get().mode,'light');assert.equal(core.capabilities.hasDOM,false);core.destroy();
});
