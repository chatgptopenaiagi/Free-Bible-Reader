"""Compile matching eSpeak runtime data and stage the three pinned public voices.

This uses an isolated host-source copy, never changes the pristine upstream source,
and never reads a user's installed voice or personal-library directories.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
SUPPORT=ROOT/'build-support/android-speech'

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cmake',default=shutil.which('cmake'))
    parser.add_argument('--generator',default=None)
    parser.add_argument('--skip-host-build',action='store_true')
    args=parser.parse_args()
    if not args.cmake:raise RuntimeError('Select the existing verified host CMake executable')
    source=SUPPORT/'espeak-host-source';build=SUPPORT/'espeak-host-generated'
    if not source.exists():shutil.copytree(SUPPORT/'piper-kotlin/third-party/espeak-ng',source,ignore=shutil.ignore_patterns('.git'))
    if not args.skip_host_build:
        configure=[args.cmake,'-S',str(source),'-B',str(build),'-DBUILD_SHARED_LIBS=OFF','-DENABLE_TESTS=OFF','-DUSE_ASYNC=OFF','-DUSE_LIBPCAUDIO=OFF','-DUSE_MBROLA=OFF','-DUSE_LIBSONIC=OFF','-DCMAKE_POLICY_VERSION_MINIMUM=3.10']
        if args.generator:configure+=['-G',args.generator]
        if args.generator and args.generator.startswith('Visual Studio'):configure+=['-A','x64']
        subprocess.run(configure,check=True)
        subprocess.run([args.cmake,'--build',str(build),'--config','Release','--parallel','4'],check=True)
    data=build/'espeak-ng-data'
    for name in ('phondata','phonindex','phontab','intonations','ro_dict','en_dict','de_dict'):
        if not (data/name).is_file():raise RuntimeError('Missing compiled eSpeak data: '+name)
    target=ROOT/'build-support/android-assets/speech/fbr-speech';target.mkdir(parents=True,exist_ok=True)
    shutil.copytree(data,target/'espeak-ng-data',dirs_exist_ok=True)
    license_dir=target/'licenses';license_dir.mkdir(exist_ok=True)
    upstream=SUPPORT/'piper-kotlin'
    for source_path, name in ((upstream/'LICENSE','piper-kotlin.LICENSE'),
                              (upstream/'third-party/piper1-gpl/COPYING','piper.COPYING'),
                              (upstream/'third-party/sonic/LICENSE','sonic.LICENSE')):
        shutil.copy2(source_path,license_dir/name)
    for source_path in (upstream/'third-party/espeak-ng').glob('COPYING*'):
        shutil.copy2(source_path,license_dir/('espeak-ng.'+source_path.name))
    native=json.loads((SUPPORT/'source-receipt.json').read_text(encoding='utf-8'))
    ort_version=native['onnxruntime']['version']
    notice_cache=SUPPORT/f'onnxruntime-{ort_version}-notices';notice_cache.mkdir(exist_ok=True)
    for name in ('LICENSE','ThirdPartyNotices.txt'):
        source=notice_cache/name
        if not source.exists():urllib.request.urlretrieve(f'https://raw.githubusercontent.com/microsoft/onnxruntime/v{ort_version}/{name}',source)
        shutil.copy2(source,license_dir/('onnxruntime.'+name))
    voices=json.loads((ROOT/'studio/voice_manifest.json').read_text(encoding='utf-8'))
    records=[]
    for voice in voices['voices']:
        for item in voice['files']:
            cached=ROOT/'build-support/android-assets/voices'/voice['id']/item['name'];cached.parent.mkdir(parents=True,exist_ok=True)
            if not cached.is_file() or sha(cached)!=item['sha256']:
                pending=cached.with_suffix(cached.suffix+'.part')
                urllib.request.urlretrieve(item['url'],pending)
                if pending.stat().st_size!=item['bytes'] or sha(pending)!=item['sha256']:raise RuntimeError('Voice integrity failed: '+item['name'])
                pending.replace(cached)
            destination=target/'voices'/voice['id']/item['name'];destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(cached,destination)
        records.append({key:voice[key] for key in ('id','name','language','quality','license','license_url','repository','commit','sample_rate')})
    files=[]
    for path in sorted(target.rglob('*')):
        if path.is_file() and path.name!='asset-manifest.json':files.append({'path':path.relative_to(target).as_posix(),'bytes':path.stat().st_size,'sha256':sha(path)})
    manifest={'schema_version':1,'voices':records,'files':files,'espeak_revision':'699e79690f23e2558d990a3a78b0050745b96932','onnxruntime_version':ort_version,'bundled_languages':['ro-RO','en-US','de-DE']}
    (target/'asset-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(files),'bytes':sum(x['bytes'] for x in files),'voices':len(records),'manifest_sha256':sha(target/'asset-manifest.json')},indent=2))

if __name__=='__main__':main()
