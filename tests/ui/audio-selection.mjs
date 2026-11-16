import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {canonicalSpeechLanguage,chooseDefaultVoice} from '../../workbench/studio/audio.js';
const voices=[
 {provider:'espeak-ng',id:'en-029',name:'English Caribbean',language:'en-029',installed:true},
 {provider:'espeak-ng',id:'en-us',name:'English US',language:'en-us',installed:true},
 {provider:'espeak-ng',id:'ro',name:'Romanian',language:'ro',installed:true},
 {provider:'espeak-ng',id:'de',name:'German',language:'de',installed:true},
 {provider:'windows-sapi',id:'desktop-david',name:'Microsoft David Desktop',language:'en-US',installed:true},
 {provider:'windows-media',id:'david',name:'Microsoft David',language:'en-US',installed:true},
 {provider:'piper',id:'mihai',name:'Mihai',language:'ro-RO',installed:true},
 {provider:'piper',id:'joe',name:'Joe',language:'en-US',installed:false},
];
test('Explicit stored and installed voice is retained',()=>assert.equal(chooseDefaultVoice(voices,'eng',{provider:'espeak-ng',voice:'ro'}).id,'ro'));
test('Fresh English uses verified SAPI David before Media or arbitrary eSpeak dialect',()=>assert.equal(chooseDefaultVoice(voices,'eng').id,'desktop-david'));
test('Unavailable stored voice falls back to actual available SAPI David',()=>assert.equal(chooseDefaultVoice(voices,'en',{provider:'piper',voice:'joe'}).id,'desktop-david'));
test('Installed Romanian Piper is preferred for source ron',()=>assert.equal(chooseDefaultVoice(voices,'ron').id,'mihai'));
test('Romanian fallback is eSpeak ro without inventing a Windows Romanian voice',()=>assert.equal(chooseDefaultVoice(voices.filter(v=>v.provider!=='piper'),'rum').id,'ro'));
test('English eSpeak fallback uses en-us rather than first Caribbean dialect',()=>assert.equal(chooseDefaultVoice(voices.filter(v=>v.provider==='espeak-ng'),'en').id,'en-us'));
test('Unavailable runtime and uninstalled models cannot become defaults',()=>assert.equal(chooseDefaultVoice([{provider:'piper',id:'x',installed:true,runtime_available:false},{provider:'piper',id:'y',installed:false}],'ro'),null));
test('German and Romanian ISO aliases normalize without changing text',()=>{assert.equal(canonicalSpeechLanguage('deu'),'de');assert.equal(canonicalSpeechLanguage('Ron'),'ro');assert.equal(canonicalSpeechLanguage('ro_RO'),'ro');assert.equal(chooseDefaultVoice(voices,'ger').id,'de');});
test('Audio EN RO DE catalogs have equal keys and placeholders',async()=>{const catalogs=await Promise.all(['en','ro','de'].map(async code=>JSON.parse(await fs.readFile(new URL('../../workbench/studio/i18n/audio.'+code+'.json',import.meta.url),'utf8'))));const keys=Object.keys(catalogs[0]).sort();assert.equal(keys.length,89);for(const catalog of catalogs){assert.deepEqual(Object.keys(catalog).sort(),keys);for(const key of keys){assert.equal(typeof catalog[key],'string');assert.ok(catalog[key].length);const params=value=>[...value.matchAll(/\{([^}]+)\}/g)].map(m=>m[1]).sort();assert.deepEqual(params(catalog[key]),params(catalogs[0][key]));}}});

test('Android chooses a discovered offline device voice ahead of compact fallback',()=>{
 const device={provider:'android-native',id:'ro-local',name:'Romanian device voice',language:'ro-RO',installed:true,runtime_available:true,network_required:false};
 assert.equal(chooseDefaultVoice([...voices.filter(v=>v.provider!=='piper'),device],'ro').id,'ro-local');
});
test('Android network voice is not preferred over a working offline fallback',()=>{
 const network={provider:'android-native',id:'ro-network',name:'Romanian network voice',language:'ro-RO',installed:true,runtime_available:true,network_required:true};
 assert.equal(chooseDefaultVoice([network,...voices.filter(v=>v.provider==='espeak-ng')],'ro').id,'ro');
});
test('An explicitly selected available Android voice survives a provider refresh',()=>{
 const device={provider:'android-native',id:'ro-local',name:'Romanian device voice',language:'ro-RO',installed:true,runtime_available:true,network_required:false};
 assert.equal(chooseDefaultVoice([...voices,device],'ro',{provider:'android-native',voice:'ro-local'}).id,'ro-local');
});
