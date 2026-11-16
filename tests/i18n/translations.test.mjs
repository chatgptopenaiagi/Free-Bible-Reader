import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {createTranslator} from '../../ui-core/i18n/translator.js';
import {LANGUAGES, resolveLanguage} from '../../ui-core/i18n/registry.js';
import {validateCatalog, validateCatalogs, extractPlaceholders} from '../../ui-core/i18n/validation.js';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const dictionaries=Object.fromEntries(await Promise.all(['en','ro','de'].map(async code=>[code,JSON.parse(await fs.readFile(path.join(root,'ui-core/i18n',code+'.json'),'utf8'))])));
const required=JSON.parse(await fs.readFile(path.join(root,'ui-core/layout/frontend-keys.json'),'utf8')).keys;
const results=[];
const test=async(name,fn)=>{try{await fn();results.push({name,status:'PASS'});}catch(error){results.push({name,status:'FAIL',error:String(error.stack??error)});}};
const make=(code='en',options={})=>createTranslator(code,{loader:async language=>dictionaries[language],logger:null,...options});

await test('Exact key and placeholder parity, frontend manifest and plain text',()=>{
 const report=validateCatalogs(dictionaries,{requiredKeys:required});assert.equal(report.valid,true,JSON.stringify(report.errors));
 assert.equal(report.keyCount,521);for(const d of Object.values(dictionaries))assert.equal(Object.keys(d).filter(k=>k.startsWith('books.')).length,66);
});
await test('Regional selection and only three enabled UI languages',()=>{
 assert.deepEqual(LANGUAGES.map(x=>x.id),['en','ro','de']);assert.equal(resolveLanguage(' RO_ro ').language,'ro');
 assert.equal(resolveLanguage('de-DE').language,'de');assert.equal(resolveLanguage('ar').supported,false);
 assert.ok(LANGUAGES.every(x=>x.direction==='ltr'));
});
await test('All enum display labels are covered in each catalog',()=>{
 const groups={themes:['light','dark','system','sepia','contrast','custom'],palettes:['classicBible','modernBlue','forestGreen','royalPurple','warmParchment','monochrome','userCustom'],fonts:['system','segoeUI','arial','calibri','verdana','tahoma','georgia','timesNewRoman','palatino','notoSans','notoSerif'],colors:['primary','secondary','accent','background','surface','text','muted','border','selected','control','link','highlight','graphSelection','crossReference'],layout:['single','dual','triple','research','reading']};
 for(const [prefix,ids] of Object.entries(groups))for(const id of ids)for(const d of Object.values(dictionaries))assert.equal(typeof d[`${prefix}.${id}`],'string');
});
await test('Live language changes and unsubscribe',async()=>{
 const t=await make();const changes=[];const unsubscribe=t.subscribe(x=>changes.push(x));assert.equal(t.language,'en');
 await t.setLanguage('ro');assert.equal(t.t('reader.book'),'Carte');await t.setLanguage('de');assert.equal(t.t('reader.book'),'Buch');
 assert.equal(changes.length,2);unsubscribe();await t.setLanguage('en');assert.equal(changes.length,2);
});
await test('Number formatting follows the UI locale',async()=>{
 const t=await make('de');assert.equal(t.formatNumber(1234.5),new Intl.NumberFormat('de').format(1234.5));
 await t.setLanguage('ro');assert.equal(t.formatNumber(1234.5),new Intl.NumberFormat('ro').format(1234.5));assert.equal(t.formatNumber(NaN),'—');
});
await test('Missing locale key falls back to English with a deduplicated explicit warning',async()=>{
 const ro={...dictionaries.ro};delete ro['reader.book'];const t=await make('ro',{loader:async c=>c==='ro'?ro:dictionaries[c]});
 assert.equal(t.t('reader.book'),'Book');assert.equal(t.t('reader.book'),'Book');assert.equal(t.getWarnings().filter(x=>x.code==='I18N_MISSING_KEY').length,1);
});
await test('Unknown keys stay visible and have explicit diagnostics',async()=>{
 const t=await make();assert.equal(t.has('reader.book'),true);assert.equal(t.has('absent.key'),false);assert.equal(t.t('absent.key'),'⟦absent.key⟧');
 assert.ok(t.getWarnings().some(x=>x.code==='I18N_UNKNOWN_KEY'));assert.equal(t.t(null),'⟦invalid-key⟧');
});
await test('Parameters are plain text; missing parameters are visible without leaking values',async()=>{
 const t=await make('ro');const attack='<img src=x onerror=alert(1)>';assert.equal(t.t('reader.chapterHeading',{book:attack,chapter:1}),attack+' 1');
 assert.equal(t.t('reader.chapterHeading',{book:'John'}),'John {chapter}');const warning=t.getWarnings().find(x=>x.code==='I18N_MISSING_PARAM');
 assert.equal(warning.parameter,'chapter');assert.equal(JSON.stringify(warning).includes('John'),false);
});
await test('Unsupported language and failed catalog requests recover to English',async()=>{
 const t=await make('ar');assert.equal(t.language,'en');assert.ok(t.getWarnings().some(x=>x.code==='I18N_UNSUPPORTED_LANGUAGE'));
 const broken=await make('de',{loader:async c=>{if(c==='de')throw Error('offline');return dictionaries[c];}});
 assert.equal(broken.language,'en');assert.ok(broken.getWarnings().some(x=>x.code==='I18N_LOAD_FAILED'));
});
await test('The last selected language wins a slow-load race',async()=>{
 let release;const gate=new Promise(resolve=>release=resolve);const t=await make('en',{loader:async c=>{if(c==='ro')await gate;return dictionaries[c];}});
 const slow=t.setLanguage('ro');await t.setLanguage('de');release();await slow;assert.equal(t.language,'de');
});
await test('A failing subscriber cannot prevent language change',async()=>{
 const t=await make();t.subscribe(()=>{throw Error('fixture');});await t.setLanguage('de');assert.equal(t.language,'de');assert.ok(t.getWarnings().some(x=>x.code==='I18N_SUBSCRIBER_ERROR'));
});
await test('Catalog validator rejects structural, HTML, key and placeholder errors',()=>{
 assert.equal(validateCatalog(null).valid,false);assert.equal(validateCatalog([]).valid,false);
 assert.equal(validateCatalog({'bad key':'x'}).valid,false);assert.equal(validateCatalog({a:'<b>Hi</b>'}).valid,false);
 assert.equal(validateCatalog({a:' '}).valid,false);assert.equal(validateCatalog({a:'{x}'},{baseCatalog:{a:'{y}'}}).valid,false);
 assert.equal(validateCatalogs({ro:{a:'x'}}).valid,false);assert.deepEqual(extractPlaceholders('{b} {a} {b}'),['a','b']);
});
await test('DOM localization writes text and safe attributes while protecting source data',async()=>{
 const t=await make('de');class Element{constructor(attrs,ignored=false){this.attrs={...attrs};this.textContent='original';this.ignored=ignored;}getAttribute(k){return this.attrs[k]??null;}setAttribute(k,v){this.attrs[k]=v;}closest(){return this.ignored?{}:null;}}
 const label=new Element({'data-i18n':'reader.book'});const input=new Element({'data-i18n-attr':'placeholder:reader.searchPlaceholder;onclick:reader.book'});
 const source=new Element({'data-i18n':'reader.book'},true);const rootElement=new Element({});const fakeDocument={nodeType:9,documentElement:rootElement,querySelectorAll:()=>[label,input,source]};
 const result=t.localize(fakeDocument);assert.equal(label.textContent,'Buch');assert.equal(input.attrs.placeholder,dictionaries.de['reader.searchPlaceholder']);
 assert.equal(input.attrs.onclick,undefined);assert.equal(source.textContent,'original');assert.equal(result.skipped,1);assert.equal(rootElement.attrs.lang,'de');assert.equal(rootElement.attrs.dir,'ltr');
 assert.ok(t.getWarnings().some(x=>x.code==='I18N_UNSAFE_ATTRIBUTE'));
});
await test('Language changes do not mutate scripture, parser state or source catalogs',async()=>{
 const source={edition_id:'eng-kjv',parser_locale:'en',OriginalText:'Ἐν ἀρχῇ — בראשית — في البدء'};const before=JSON.stringify(source);const catalogBefore=JSON.stringify(dictionaries);
 const t=await make();await t.setLanguage('ro');await t.setLanguage('de');assert.equal(JSON.stringify(source),before);assert.equal(JSON.stringify(dictionaries),catalogBefore);
});
await test('Every catalog placeholder has the exact same names as English',()=>{
 for(const [key,value] of Object.entries(dictionaries.en))for(const code of ['ro','de'])assert.deepEqual(extractPlaceholders(dictionaries[code][key]),extractPlaceholders(value),`${code}:${key}`);
 assert.deepEqual(extractPlaceholders(dictionaries.en['research.openReference']),[]);
});

const hashes=Object.fromEntries(await Promise.all(['en','ro','de'].map(async code=>[code,crypto.createHash('sha256').update(await fs.readFile(path.join(root,'ui-core/i18n',code+'.json'))).digest('hex')])));
// Keep historical receipts immutable. Callers may select a fresh output directory;
// otherwise every invocation gets its own dated evidence directory.
const requestedEvidenceDirectory=process.env.FBR_TEST_EVIDENCE_DIR?.trim();
const evidenceDirectory=requestedEvidenceDirectory?path.resolve(root,requestedEvidenceDirectory):path.join(root,'reports','MISSION-FBR-002','evidence',`i18n-${new Date().toISOString().replace(/[-:.]/g,'')}-${crypto.randomUUID().slice(0,8)}`);
const evidenceFile=path.join(evidenceDirectory,'i18n-tests.json');
const receipt={mission:'MISSION-FBR-002',checked_utc:new Date().toISOString(),runtime:process.version,scope:'Catalog validation and dependency-free translator functional tests; browser behavior is tested separately.',status:results.every(x=>x.status==='PASS')?'PASS':'FAIL',passed:results.filter(x=>x.status==='PASS').length,failed:results.filter(x=>x.status==='FAIL').length,languages:['en','ro','de'],keys_each:Object.fromEntries(Object.entries(dictionaries).map(([c,d])=>[c,Object.keys(d).length])),frontend_literal_keys:required.length,catalog_sha256:hashes,evidence_file:path.relative(root,evidenceFile).split(path.sep).join('/'),tests:results};
await fs.mkdir(evidenceDirectory,{recursive:true});await fs.writeFile(evidenceFile,JSON.stringify(receipt,null,2)+'\n',{encoding:'utf8',flag:'wx'});
console.log(JSON.stringify(receipt,null,2));if(receipt.failed)process.exitCode=1;
