/* Real source/installed startup fault tests; no app launch or audio operations. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {DEFAULT_PREFERENCES} from '../../ui-core/preferences/schema.js';

const root=process.cwd(),target=new URL(process.env.READER_URL||'http://127.0.0.1:57400/');
if(!['127.0.0.1','localhost'].includes(target.hostname))throw Error('Loopback runtime required');
const namespaces=['core','audio','library','search','workspace','export'];
const uid=crypto.randomUUID().slice(0,8),stamp=new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d+Z$/,'Z');
const evidence=path.resolve(process.env.FBR_STUDIO_INIT_EVIDENCE_DIR||path.join(root,'reports/MISSION-FBR-003/evidence',`studio-init-${stamp}-${uid}`));
await fs.mkdir(evidence,{recursive:true});
const modulePath=process.env.PLAYWRIGHT_MODULE;
const {chromium}=await import(modulePath?(modulePath.startsWith('file:')?modulePath:pathToFileURL(path.resolve(modulePath)).href):'playwright-core');
const executable='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const browser=await chromium.launch({headless:true,executablePath:executable});
const checks=[],external=[];
const savedPosition={version:1,edition:'kjv',book:'John',chapter:3,verse:16,selectedVerse:16};
const health=await fetch(new URL('/api/health',target)).then(r=>r.json());
assert.equal(health.product,'FREE BIBLE READER');assert.equal(health.version,process.env.EXPECTED_READER_VERSION||'0.2.0');
let runtimeEvidence=null;
if(process.env.READER_RUNTIME_STATE){const state=JSON.parse(await fs.readFile(process.env.READER_RUNTIME_STATE,'utf8'));assert.equal(state.pid,health.pid);assert.equal(new URL(state.url).origin,target.origin);runtimeEvidence={pid:state.pid,executable:state.executable,sha256:crypto.createHash('sha256').update(await fs.readFile(state.executable)).digest('hex'),pid_matches_health:true};if(process.env.READER_EXPECTED_EXECUTABLE_SHA256)assert.equal(runtimeEvidence.sha256,process.env.READER_EXPECTED_EXECUTABLE_SHA256.toLowerCase());}
else assert.notEqual(process.env.READER_RUNTIME_KIND,'installed','Installed classification requires actual runtime state proof');
const baseline=await fetch(new URL('/api/reader/chapter?edition=kjv&book=John&chapter=3',target)).then(r=>r.json());
const expectedText=baseline.verses.find(v=>v.reference==='John.3.16').text;
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');

async function setup(language='en'){
  const context=await browser.newContext({viewport:{width:1280,height:800}}),page=await context.newPage();page.setDefaultTimeout(15000);
  const audit={page_errors:[],console_errors:[],request_failures:[],namespace_requests:{},document_requests:0};
  page.on('pageerror',error=>audit.page_errors.push(error.message));
  page.on('console',message=>{if(message.type()==='error')audit.console_errors.push(message.text());});
  page.on('requestfailed',r=>audit.request_failures.push({path:new URL(r.url()).pathname,error:r.failure()?.errorText}));
  page.on('request',r=>{if(r.resourceType()==='document')audit.document_requests++;const p=new URL(r.url()).pathname;if(/^\/studio-ui\/i18n\/[^/]+\.(en|ro|de)\.json$/.test(p))audit.namespace_requests[p]=(audit.namespace_requests[p]||0)+1;});
  await context.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin===target.origin||['data:','blob:','about:'].includes(u.protocol))return route.continue();external.push(u.origin);return route.abort('blockedbyclient');});
  await context.addInitScript(({position,prefs})=>{if(!sessionStorage.getItem('studio-init-seeded')){localStorage.setItem('free-bible-reader.position.v1',JSON.stringify(position));localStorage.setItem('biblia.ui.preferences.v2',JSON.stringify(prefs));sessionStorage.setItem('studio-init-seeded','1');}},{position:savedPosition,prefs:{format:'biblia-ui-preferences',version:2,preferences:{...DEFAULT_PREFERENCES,themeMode:'sepia',interfaceLanguage:language}}});
  return{context,page,audit};
}
async function reading(page){
  await page.waitForFunction(()=>document.querySelector('#reader-content .scripture-verse.selected')?.dataset.reference==='John.3.16'&&document.querySelector('#reader-edition')?.value==='kjv');
  assert.equal(await page.locator('#reader-content .scripture-verse.selected [data-source-data]').textContent(),expectedText);
  const state=await page.evaluate(()=>({position:JSON.parse(localStorage.getItem('free-bible-reader.position.v1')),prefs:JSON.parse(localStorage.getItem('biblia.ui.preferences.v2')).preferences,language:document.documentElement.lang}));
  assert.equal(state.position.edition,'kjv');assert.equal(state.position.book,'John');assert.equal(String(state.position.chapter),'3');assert.equal(String(state.position.selectedVerse),'16');assert.equal(state.prefs.themeMode,'sepia');
  return state;
}
async function ready(page){await page.locator('#studio-menubar').waitFor({state:'visible'});await page.locator('#studio-player').waitFor({state:'visible'});assert.equal(await page.locator('#studio-menubar').count(),1);assert.equal(await page.locator('#studio-player').count(),1);assert.equal(await page.locator('#studio-notifications').count(),1);assert.equal(await page.locator('.studio-init-notice').count(),0);return reading(page);}
async function capture(page,name){const bytes=await page.screenshot({fullPage:false});await fs.writeFile(path.join(evidence,name+'.png'),bytes,{flag:'wx'});return{file:name+'.png',sha256:hash(bytes),bytes:bytes.length};}
async function record(name,fn){const start=performance.now();let result;try{result={name,passed:true,detail:await fn()};}catch(error){result={name,passed:false,error:String(error.stack||error)};}result.elapsed_ms=Math.round(performance.now()-start);checks.push(result);await fs.appendFile(path.join(evidence,'progress.ndjson'),JSON.stringify(result)+'\n');console.log((result.passed?'PASS ':'FAIL ')+name);return result;}

async function transient(namespace,{status503=false}={}){
  const {context,page,audit}=await setup();const blocked='/studio-ui/i18n/'+namespace+'.en.json';let injected=0;
  const matcher=u=>new URL(u).pathname===blocked;
  const handler=async route=>{injected++;if(injected===1){if(status503)return route.fulfill({status:503,contentType:'application/json',body:'{"synthetic":"temporarily unavailable"}'});return route.abort('connectionrefused');}return route.continue();};
  try{
    await page.route(matcher,handler);await page.goto(target.href,{waitUntil:'domcontentloaded'});await ready(page);
    // Force both lazy namespaces through genuine user controls after the preload.
    await page.locator('#studio-menubar [data-menu=library] summary').click();await page.locator('#studio-menubar [data-menu=library] [data-studio-key="action.import"]').click();await page.locator('#studio-import-dialog').waitFor({state:'visible'});await page.locator('#studio-import-dialog>header button').click();
    await page.locator('#studio-menubar [data-menu=search] summary').click();await page.locator('#studio-menubar [data-menu=search] [data-studio-key="action.advancedSearch"]').click();await page.locator('#studio-search-dialog').waitFor({state:'visible'});await page.locator('#studio-search-dialog>header button').click();
    assert.equal(injected,2,'Transient GET did not recover with exactly one retry');assert.equal(audit.document_requests,1,'Transient fetch caused a page reload');
    assert.equal(Object.keys(audit.namespace_requests).length,18);
    for(const [p,n]of Object.entries(audit.namespace_requests))assert.equal(n,p===blocked?2:1,'Namespace refetched or duplicated: '+p);
    assert.deepEqual(audit.page_errors,[]);return{blocked_path:blocked,failure_kind:status503?'503':'connectionrefused',injections:1,requests:injected,no_duplicate_controls:true,reading_reset:false,namespace_promises_reused:true,audit};
  }finally{await context.close();}
}
async function persistent(language,{missingKey=false}={}){
  const {context,page,audit}=await setup(language);const blocked=missingKey?'/studio-ui/i18n/library.de.json':'/studio-ui/i18n/library.en.json';let injected=0;
  const matcher=u=>new URL(u).pathname===blocked;
  const handler=async route=>{injected++;if(!missingKey)return route.abort('connectionrefused');const response=await route.fetch();const values=await response.json();assert.ok(Object.hasOwn(values,'library.importTitle'));delete values['library.importTitle'];return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(values)});};
  try{
    await page.route(matcher,handler);await page.goto(target.href,{waitUntil:'domcontentloaded'});const notice=page.locator('.studio-init-notice');await notice.waitFor({state:'visible'});await reading(page);
    assert.equal(await notice.getAttribute('role'),'alert');assert.equal(await page.locator('#studio-menubar').count(),0,'An incomplete studio was exposed as complete');
    assert.equal(injected,missingKey?1:3,'Unexpected retry policy for schema/network failure');assert.equal(audit.document_requests,1);
    const labels={en:'Retry studio',ro:'Reîncearcă',de:'Erneut versuchen'};assert.equal(await notice.locator('button').textContent(),labels[language]);
    const failure_image=await capture(page,(missingKey?'missing-key':'persistent')+'-'+language+'-error');
    await page.unroute(matcher,handler);const reload=page.waitForEvent('domcontentloaded');await notice.locator('button').click();await reload;const state=await ready(page);
    assert.equal(audit.document_requests,2,'Recovery must be one explicit user reload');assert.equal(state.prefs.interfaceLanguage,language);assert.equal(state.language,language);assert.deepEqual(audit.page_errors,[]);
    return{language,blocked_path:blocked,semantic_missing_key:missingKey,failed_requests_before_retry:injected,user_retry_recovered:true,automatic_reload_count:0,no_duplicate_controls:true,reading_and_preferences_retained:true,failure_image,recovery_image:await capture(page,(missingKey?'missing-key':'persistent')+'-'+language+'-recovered'),audit};
  }finally{await context.close();}
}

try{
  for(const name of namespaces)await record('A first namespace network failure recovers without duplicate controls: '+name,()=>transient(name));
  await record('A transient namespace HTTP503 recovers through a bounded GET retry',()=>transient('core',{status503:true}));
  for(const language of ['en','ro','de'])await record('Persistent namespace failure remains readable and explicit Retry restores studio: '+language,()=>persistent(language));
  await record('A syntactically valid catalog missing a required key is rejected, then Retry recovers',()=>persistent('en',{missingKey:true}));
  await record('All six served namespace catalogs have matching keys and placeholders in three languages',async()=>{
    const context=await browser.newContext(),names=[];try{for(const namespace of namespaces){const values={};for(const language of ['en','ro','de']){const response=await context.request.get(new URL(`/studio-ui/i18n/${namespace}.${language}.json`,target).href);assert.equal(response.status(),200);const bytes=await response.body();values[language]=JSON.parse(bytes);names.push({namespace,language,keys:Object.keys(values[language]).length,sha256:hash(bytes)});assert.ok(Object.values(values[language]).every(v=>typeof v==='string'));}
      const keys=Object.keys(values.en).sort();for(const lang of ['ro','de'])assert.deepEqual(Object.keys(values[lang]).sort(),keys,'Key mismatch '+namespace+'/'+lang);
      const placeholders=value=>[...new Set([...value.matchAll(/\{([A-Za-z_][\w]*)\}/g)].map(m=>m[1]))].sort();for(const key of keys)for(const lang of ['ro','de'])assert.deepEqual(placeholders(values[lang][key]),placeholders(values.en[key]),'Placeholder mismatch '+namespace+'/'+lang+'/'+key);
    }return{namespaces:6,languages:3,catalogs:names,key_and_placeholder_parity:true};}finally{await context.close();}
  });
  await record('An explicit write POST is not retried after503 and no saved search is created',async()=>{
    const {context,page,audit}=await setup();let calls=0;const query='studio-init-post-no-retry-'+uid;const matcher=u=>new URL(u).pathname==='/api/studio/workspace/create';
    try{await page.goto(target.href,{waitUntil:'domcontentloaded'});await ready(page);await page.locator('#studio-menubar [data-menu=search] summary').click();await page.locator('#studio-menubar [data-menu=search] [data-studio-key="action.advancedSearch"]').click();await page.locator('#studio-search-dialog').waitFor({state:'visible'});await page.locator('#studio-search-dialog [data-studio-key="search.query"]').locator('xpath=..').locator('input').fill(query);
      await page.route(matcher,route=>{assert.equal(route.request().method(),'POST');const body=route.request().postDataJSON();if(body.type!=='savedsearch'||body.title!==query)return route.continue();calls++;return route.fulfill({status:503,contentType:'application/json',body:'{"error":"SYNTHETIC_POST_FAILURE_NOT_WRITTEN"}'});});await page.locator('#studio-search-dialog button[data-studio-key="search.saveSearch"]').click();await page.waitForFunction(()=>document.querySelector('#studio-notifications')?.textContent.includes('SYNTHETIC_POST_FAILURE_NOT_WRITTEN'));await page.waitForTimeout(800);assert.equal(calls,1,'Write POST was retried');const response=await context.request.get(new URL('/api/studio/workspace?'+new URLSearchParams({type:'savedsearch',query,limit:10}),target).href);assert.equal(response.status(),200);const data=await response.json();assert.equal(data.items.length,0);assert.deepEqual(audit.page_errors,[]);return{post_requests:calls,server_side_write:false,unrelated_reading_history_not_intercepted:true,audit};
    }finally{await context.close();}
  });
}finally{
  await browser.close();const passed=checks.filter(c=>c.passed).length;const report={mission:'MISSION-FBR-003',checked_utc:new Date().toISOString(),status:checks.length===13&&passed===13&&!external.length?'PASS':'FAIL',runtime_kind:process.env.READER_RUNTIME_KIND||'source',runtime_evidence:runtimeEvidence,health,url:target.href,node_executable:process.execPath,node_version:process.version,browser_executable:executable,passed,failed:checks.length-passed,checks,external_requests:external,scope:'Thirteen actual browser/HTTP criteria. Fresh owned contexts; saved position seeded once per session, not reseeded on recovery reload. Network/HTTP/schema faults are synthetic and never modify source files. No application/server launch, model download, synthesis or shared browser profile mutation. Physical devices and other engines not tested.'};await fs.writeFile(path.join(evidence,'verification.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify({status:report.status,passed,failed:report.failed,evidence,failures:checks.filter(c=>!c.passed)},null,2));if(report.status!=='PASS')process.exitCode=1;
}
