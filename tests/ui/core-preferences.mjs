import test from 'node:test';
import assert from 'node:assert/strict';
import {createUICore,DEFAULT_PREFERENCES,PREFERENCES_VERSION,STORAGE_KEY}from '../../ui-core/index.js';

function memoryStorage(initial={}){const values=new Map(Object.entries(initial));return{values,getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,String(value))};}

test('stable defaults and defensive whole-state copies',()=>{
  const core=createUICore({storage:null});assert.deepEqual(core.preferences.get(),DEFAULT_PREFERENCES);
  const copy=core.preferences.get();copy.panelSizes.reader=1000;copy.themeMode='dark';
  assert.equal(core.preferences.get().themeMode,'light');assert.equal(core.preferences.get().panelSizes.reader,55);core.destroy();
});
test('validated patch subscription reports changed keys and unsubscribes',()=>{
  const core=createUICore({storage:null});const calls=[];
  const off=core.preferences.subscribe((state,keys)=>calls.push({state,keys}));
  core.preferences.set({themeMode:'dark',paragraphSpacing:1.5,panelSizes:{reader:65}});
  assert.deepEqual(calls[0].keys,['themeMode','paragraphSpacing','panelSizes']);
  assert.equal(calls[0].state.panelSizes.research,30);off();core.preferences.set({themeMode:'sepia'});assert.equal(calls.length,1);core.destroy();
});
test('refresh restores all versioned validated preferences',()=>{
  const storage=memoryStorage(),first=createUICore({storage});
  first.preferences.set({interfaceLanguage:'ro',scriptureFont:'palatino',lineHeight:1.9,panelCollapsed:{inspector:true},panelVisibility:{sidebar:false}});
  const expected=first.preferences.get();first.destroy();
  const second=createUICore({storage});assert.deepEqual(second.preferences.get(),expected);
  assert.equal(JSON.parse(storage.getItem(STORAGE_KEY)).version,PREFERENCES_VERSION);second.destroy();
});
test('unknown keys, CSS payloads, invalid enum and nonfinite numbers are rejected',()=>{
  const core=createUICore({storage:null});
  core.preferences.set({unknown:true,themeMode:'url(evil)',interfaceFont:'evil; color:red',lineHeight:Infinity,paragraphSpacing:NaN,customColors:{text:'red; background:url(evil)',foreign:'#ffffff'},panelSizes:{reader:-1,constructor:4}});
  assert.deepEqual(core.preferences.get(),DEFAULT_PREFERENCES);
  const codes=core.preferences.getDiagnostics().map(issue=>issue.code);assert.ok(codes.includes('INVALID_COLOR'));assert.ok(codes.includes('UNKNOWN_KEY'));core.destroy();
});
test('prototype-bearing JSON cannot pollute any object',()=>{
  const core=createUICore({storage:null});core.preferences.importJSON('{"__proto__":{"polluted":true},"panelSizes":{"__proto__":7,"constructor":8}}');
  assert.equal({}.polluted,undefined);assert.equal(Object.hasOwn(core.preferences.get().panelSizes,'__proto__'),false);core.destroy();
});
test('blocked storage getter degrades to working in-memory preferences',()=>{
  const win={get localStorage(){throw new Error('blocked');}};
  const core=createUICore({window:win});core.preferences.set({themeMode:'dark'});
  assert.equal(core.preferences.get().themeMode,'dark');assert.equal(core.capabilities.storageAvailable,false);core.destroy();
});
test('quota failure does not lose state or crash updates',()=>{
  const core=createUICore({storage:{getItem:()=>null,setItem(){throw new Error('quota');}}});
  core.preferences.set({scriptureFontScale:1.7});assert.equal(core.preferences.get().scriptureFontScale,1.7);
  assert.equal(core.capabilities.storageStatus,'memory-only');assert.ok(core.preferences.getDiagnostics().some(issue=>issue.code==='STORAGE_WRITE_FAILED'));core.destroy();
});
test('v1 migration is explicit and preserves original legacy key',()=>{
  const old=JSON.stringify({version:1,prefs:{theme:'dark',language:'de',font:'georgia',fontSize:20,panelVisibility:{reader:true}}});
  const storage=memoryStorage({'biblia.ui.preferences.v1':old});const core=createUICore({storage});
  assert.equal(core.preferences.get().themeMode,'dark');assert.equal(core.preferences.get().interfaceLanguage,'de');assert.equal(core.preferences.get().interfaceFontScale,1.25);
  assert.equal(storage.getItem('biblia.ui.preferences.v1'),old);assert.equal(JSON.parse(storage.getItem(STORAGE_KEY)).version,2);core.destroy();
});
test('future version and malformed import do not replace state',()=>{
  const core=createUICore({storage:null});core.preferences.set({themeMode:'dark'});const before=core.preferences.get();
  assert.throws(()=>core.preferences.importJSON('{'),/INVALID_JSON/);assert.throws(()=>core.preferences.importJSON('{"version":99,"preferences":{}}'),/UNSUPPORTED_VERSION/);
  assert.deepEqual(core.preferences.get(),before);core.destroy();
});
test('export/import round trip and scoped reset',()=>{
  const storage=memoryStorage({'unrelated-project':'preserve'}),core=createUICore({storage});
  core.preferences.set({colorPalette:'userCustom',customColors:{text:'#123',background:'#ffffff'},panelSizes:{reader:72},panelCollapsed:{research:true}});
  const exported=core.preferences.exportJSON(),expected=core.preferences.get();core.preferences.reset();core.preferences.importJSON(exported);
  assert.deepEqual(core.preferences.get(),expected);assert.equal(storage.getItem('unrelated-project'),'preserve');assert.equal(expected.customColors.text,'#112233');core.destroy();
});
test('partial imported panel maps retain mandatory defaults; empty custom map clears overrides',()=>{
  const core=createUICore({storage:null});core.preferences.importJSON('{"panelVisibility":{"reader":false}}');
  assert.equal(core.preferences.get().panelVisibility.reader,false);assert.equal(core.preferences.get().panelVisibility.inspector,true);
  core.preferences.set({customColors:{text:'#222222'}});core.preferences.set({customColors:{}});assert.deepEqual(core.preferences.get().customColors,{});core.destroy();
});
test('panel maps are bounded and only accept safe IDs and finite values',()=>{
  const core=createUICore({storage:null});const sizes=Object.fromEntries(Array.from({length:70},(_,index)=>['panel'+index,20]));
  core.preferences.set({panelSizes:sizes});assert.equal(Object.keys(core.preferences.get().panelSizes).length,32);
  assert.ok(core.preferences.getDiagnostics().length>0);core.destroy();
});
test('cross-tab storage event applies state without a write loop',()=>{
  const listeners=new Map(),storage=memoryStorage();let writes=0;const original=storage.setItem;storage.setItem=(...args)=>{writes++;return original(...args);};
  const win={localStorage:storage,addEventListener:(key,fn)=>listeners.set(key,fn),removeEventListener:key=>listeners.delete(key)};
  const core=createUICore({window:win});const payload=JSON.stringify({version:2,preferences:{...DEFAULT_PREFERENCES,themeMode:'dark'}});
  listeners.get('storage')({key:STORAGE_KEY,newValue:payload});assert.equal(core.preferences.get().themeMode,'dark');assert.equal(writes,0);core.destroy();assert.equal(listeners.size,0);
});
