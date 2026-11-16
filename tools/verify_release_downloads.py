"""Independently download the explicit public release assets without credentials."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--tag',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    manifest=json.loads(Path(args.manifest).read_text('utf-8-sig'))
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=False)
    base='https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/download/'+urllib.parse.quote(args.tag,safe='')+'/'
    def download(asset):
        name=asset['file']
        if Path(name).name!=name:raise ValueError('Release asset must be a basename')
        target=output/name;partial=output/(name+'.part');url=base+urllib.parse.quote(name,safe='')
        for attempt in range(1,4):
            started=time.monotonic()
            try:
                sha=hashlib.sha256();size=0
                request=urllib.request.Request(url,headers={'User-Agent':'Free-Bible-Reader-public-download-verification/0.3.0','Accept':'application/octet-stream'})
                with urllib.request.urlopen(request,timeout=120) as response,partial.open('xb') as destination:
                    for block in iter(lambda:response.read(1024*1024),b''):
                        destination.write(block);sha.update(block);size+=len(block)
                value=sha.hexdigest()
                if size!=asset['bytes'] or value!=asset['sha256']:raise ValueError('Published download does not match verified local bytes')
                partial.rename(target)
                result={'file':name,'bytes':size,'sha256':value,'url':url,'status':'PASS','attempt':attempt,'elapsed_seconds':round(time.monotonic()-started,2),'anonymous':True}
                print(json.dumps(result),flush=True);return result
            except Exception as error:
                partial.unlink(missing_ok=True)
                if attempt==3:return {'file':name,'url':url,'status':'FAIL','error':str(error),'attempt':attempt,'anonymous':True}
                time.sleep(attempt*2)
    results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for future in as_completed([pool.submit(download,asset) for asset in manifest['assets']]):results.append(future.result())
    receipt={'tag':args.tag,'anonymous_downloads':True,'passed':sum(r['status']=='PASS' for r in results),'failed':sum(r['status']!='PASS' for r in results),'assets':sorted(results,key=lambda x:x['file'])}
    (output/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':receipt['passed'],'failed':receipt['failed']}),flush=True)
    if receipt['failed']:raise SystemExit(1)

if __name__=='__main__':main()
