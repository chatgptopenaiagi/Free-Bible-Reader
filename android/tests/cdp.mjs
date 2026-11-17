import {execFileSync} from 'node:child_process';
import fs from 'node:fs/promises';
export const adb='C:\\Users\\LOVE\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe';
export const serial=process.env.FBR_ANDROID_SERIAL||'emulator-5580';
export function shell(command){return execFileSync(adb,['-s',serial,'shell',command],{encoding:'utf8',timeout:30000});}
export async function attach(packageId,port=9223){
 const pid=shell(`pidof ${packageId}`).trim().split(/\s+/)[0];
 execFileSync(adb,['-s',serial,'forward',`tcp:${port}`,`localabstract:webview_devtools_remote_${pid}`],{timeout:10000});
 let list;for(let i=0;i<40;i++){try{list=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();if(list.length)break;}catch{}await new Promise(r=>setTimeout(r,250));}
 if(!list?.length)throw Error('No installed WebView target');
 const ws=new WebSocket(list[0].webSocketDebuggerUrl);await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
 let counter=0;const pending=new Map(),events=[];
 ws.addEventListener('message',event=>{const value=JSON.parse(event.data);if(value.id){const p=pending.get(value.id);if(p){pending.delete(value.id);clearTimeout(p.timer);value.error?p.reject(Error(JSON.stringify(value.error))):p.resolve(value.result);}}else events.push(value);});
 async function send(method,params={}){const id=++counter;return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout: '+method));},30000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});}
 async function evaluate(expression){const result=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(result.exceptionDetails.text+': '+JSON.stringify(result.exceptionDetails.exception));return result.result?.value;}
 await send('Runtime.enable');await send('Page.enable');
 return {pid,url:list[0].url,send,evaluate,events,close:()=>ws.close()};
}
export async function wait(client,predicate,label='condition',timeout=20000){const start=Date.now();let last;while(Date.now()-start<timeout){try{if(await client.evaluate(predicate))return;}catch(error){last=error;}await new Promise(r=>setTimeout(r,200));}throw Error('Timed out: '+label+(last?' ('+last.message+')':''));}
export async function screenshot(path){const data=execFileSync(adb,['-s',serial,'exec-out','screencap','-p'],{timeout:15000,maxBuffer:30_000_000});await fs.writeFile(path,data);}
