"""Stage only public, allowlisted offline resources for distinct Android products.

No personal profile, original corpus, Windows executable or loose downloaded model
is discovered recursively. Speech's independently hashed assets belong to its
Ultimate-only Gradle module and are deliberately not duplicated here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
DBS=('reader.sqlite','romanian.sqlite','xref_visual.sqlite','xref_aggregate.sqlite','xref_phrase.sqlite','xref_reference.sqlite')
ALLOWED={'.js','.mjs','.css','.html','.json','.svg','.ttf','.txt','.md','.xml'}

def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        while part:=source.read(1024*1024):value.update(part)
    return value.hexdigest()

def stage(variant):
    if variant not in ('lite','ultimate'):raise ValueError('Unknown Android product')
    target=ROOT/'android/app/src'/variant/'assets/fbr'
    target.mkdir(parents=True,exist_ok=True)
    files={}
    def add(path,relative=None):
        path=Path(path)
        if not path.is_file() or path.is_symlink():raise ValueError('Missing or unsafe public resource: '+str(path))
        key=str(relative or path.relative_to(ROOT)).replace('\\','/')
        if key in files:raise ValueError('Duplicate Android resource: '+key)
        files[key]=path
    for name in DBS if variant=='ultimate' else DBS[:2]:add(ROOT/'data'/name)
    # Chaquopy extracts this curated pure-Python core beside data/. No host
    # interpreter, venv, compiled Windows wheel or generated wheel-assets tree.
    for package in ('free_bible_reader','reader','studio','workbench','bridge','engines'):
        for file in (ROOT/package).rglob('*.py'):
            if 'assets' not in file.relative_to(ROOT/package).parts and '__pycache__' not in file.parts:
                add(file)
    folders=['workbench','ui-core','parser'] if variant=='ultimate' else ['workbench/lite']
    for folder in folders:
        for file in (ROOT/folder).rglob('*'):
            if file.is_file() and file.suffix.lower() in ALLOWED and '__pycache__' not in file.parts:
                add(file)
    if variant=='lite':
        add(ROOT/'workbench/platform-bootstrap.js')
        add(ROOT/'workbench/favicon.svg')
    if variant=='ultimate':
        for file in (ROOT/'studio/fonts').glob('*.ttf'):add(file)
        for name in ('component.js','component.css'):add(ROOT/'engines/visual'/name)
    for name in ('LICENSE','NOTICE.md'):
        if (ROOT/name).is_file():add(ROOT/name)
    for file in (ROOT/'licenses').rglob('*'):
        if file.is_file() and file.suffix.lower() in {'.txt','.md','.json'}:add(file)
    manifest=[]
    for key,source in sorted(files.items()):
        output=target/key;output.parent.mkdir(parents=True,exist_ok=True)
        digest=sha(source)
        if not output.is_file() or output.stat().st_size!=source.stat().st_size or sha(output)!=digest:
            shutil.copyfile(source,output)
        manifest.append({'path':key,'size':source.stat().st_size,'sha256':digest})
    # Fail rather than quietly packaging a stale or private leftover file.
    unexpected=[str(p.relative_to(target)) for p in target.rglob('*') if p.is_file() and str(p.relative_to(target)).replace('\\','/') not in files and p.name!='resource-manifest.json']
    if unexpected:raise ValueError('Unexpected staged assets; inspect without deleting evidence: '+repr(unexpected[:10]))
    receipt={'schema_version':1,'product':variant,'version':'0.3.1-beta.1' if variant=='ultimate' else '0.3.0','private_corpus_included':False,'files':manifest,'total_bytes':sum(f['size'] for f in manifest),'speech_assets':'Ultimate-only :speech module; independently hashed' if variant=='ultimate' else 'Android device voices only','reading_editions':['web','kjv','bsb','ronbl'],'romanian_coverage':'Draft Latin-script New Testament only; 27 books'}
    (target/'resource-manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'variant':variant,'files':len(manifest),'bytes':receipt['total_bytes'],'path':str(target)},ensure_ascii=False))
    return receipt

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('variant',choices=['lite','ultimate','all'],default='all',nargs='?');args=parser.parse_args()
    for variant in ('lite','ultimate') if args.variant=='all' else (args.variant,):stage(variant)
