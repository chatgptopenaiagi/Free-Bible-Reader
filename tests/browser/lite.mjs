import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require('C:/xampp/BIBLIA-XREF-MULTIENGINE-LAB/repositories/trekhleb-bible-cross-references/node_modules/playwright-core');
const root=process.cwd(), evidence=path.join(root,'reports/MISSION-FBR-004/evidence/browser');
const runtime=JSON.parse(fs.readFileSync(path.join(evidence,'server.json'),'utf8').replace(/^\uFEFF/,''));
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const errors=[],checks=[];
const page=await browser.newPage({viewport:{width:390,height:844}});
page.on('pageerror',error=>errors.push(error.message));
async function check(name,run){await run();checks.push({name,status:'PASS'});}
try{
 await page.goto(runtime.url+'lite/');
 await page.locator('#verses p').first().waitFor();
 await check('John 1 complete',async()=>{assert.equal(await page.locator('#verses p').count(),51);assert.match(await page.locator('#verses').innerText(),/In the beginning/);});
 await page.locator('#chapter').selectOption('3');
 await page.locator('#title').filter({hasText:/John 3/}).waitFor();
 await check('John 3 complete',async()=>assert.equal(await page.locator('#verses p').count(),36));
 await page.locator('#edition').selectOption('ronbl');
 await page.waitForFunction(()=>document.querySelector('#source').textContent.includes('Liber'));
 await check('Romanian exact chapter and limitation',async()=>{assert.equal(await page.locator('#verses p').count(),36);assert.match(await page.locator('#verse-16').innerText(),/Dumnezeu/);assert.match(await page.locator('#edition-note').innerText(),/27 books/);assert.equal(await page.locator('#book option').count(),27);});
 await page.locator('#next').click();await page.waitForFunction(()=>document.querySelector('#title').textContent.endsWith(' 4'));
 await page.locator('#previous').click();await page.waitForFunction(()=>document.querySelector('#title').textContent.endsWith(' 3'));
 checks.push({name:'Previous/next edition-specific chapters',status:'PASS'});
 await page.locator('#verse-16').click();await page.locator('#bookmark').click();
 await page.locator('#settings').click();
 await check('Bookmark captures edition/reference',async()=>{assert.match(await page.locator('#bookmarks').innerText(),/RONBL.*John 3:16/);});
 await page.locator('#theme').selectOption('dark');await page.locator('#language').selectOption('ro');
 await check('Romanian interface and dark theme',async()=>{assert.equal(await page.locator('html').getAttribute('lang'),'ro');assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');assert.equal(await page.locator('#edition').inputValue(),'ronbl');});
 await page.getByRole('button',{name:'Închide',exact:true}).first().click();
 await page.reload();await page.locator('#verses p').first().waitFor();
 await check('Reading/presentation persisted',async()=>{assert.equal(await page.locator('#edition').inputValue(),'ronbl');assert.equal(await page.locator('#chapter').inputValue(),'3');assert.equal(await page.locator('html').getAttribute('lang'),'ro');assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');});
 await page.locator('#search-open').click();await page.locator('#query').fill('dragoste');await page.locator('#search-form button').last().click();
 await page.locator('#result-list button').first().waitFor();
 await check('Romanian search and passage navigation',async()=>{assert.ok(await page.locator('#result-list button').count()>0);await page.locator('#result-list button').first().click();await page.waitForFunction(()=>document.querySelector('#results').hidden);assert.equal(await page.locator('#edition').inputValue(),'ronbl');});
 await page.locator('#settings').click();await page.locator('#language').selectOption('de');await page.locator('#font-size').fill('32');await page.locator('#font-size').dispatchEvent('input');await page.getByRole('button',{name:'Schließen',exact:true}).first().click();
 for(const [width,height] of [[320,568],[390,844],[768,1024],[1024,768],[1440,900],[1920,1080],[2560,1440],[3840,2160]]){
  await page.setViewportSize({width,height});
  await check(`Reflow ${width}x${height}`,async()=>{assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));for(const id of ['previous','next','play','search-open','settings'])assert.ok(await page.locator('#'+id).isVisible());});
 }
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(evidence,'lite-german-dark-phone.png'),fullPage:false});
 await page.locator('#settings').click();await page.locator('#theme').selectOption('light');await page.locator('#language').selectOption('en');await page.getByRole('button',{name:'Close',exact:true}).first().click();
 await page.screenshot({path:path.join(evidence,'lite-english-light-phone.png'),fullPage:false});
 await check('No unhandled browser errors',async()=>assert.deepEqual(errors,[]));
}catch(error){checks.push({name:'Failure',status:'FAIL',error:error.stack});await page.screenshot({path:path.join(evidence,'lite-failure.png')});process.exitCode=1;}
finally{fs.writeFileSync(path.join(evidence,'lite-results.json'),JSON.stringify({browser:'Installed Edge',platform:'Windows responsive browser, not physical Android',checks,errors},null,2));await browser.close();}
console.log(JSON.stringify({passed:checks.filter(x=>x.status==='PASS').length,failed:checks.filter(x=>x.status==='FAIL').length,errors}));
