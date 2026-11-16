"""Package exact native speech source inputs, local adapter, patches and notices.

The application repository provides the remaining first-party application source.
This archive excludes models, personal data, Git object databases and built output.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[2]
SUPPORT=ROOT/'build-support/android-speech'
EXCLUDE={'.git','build','.gradle','.cxx','__pycache__','node_modules'}

def eligible(path,base):
    relative=path.relative_to(base)
    return path.is_file() and not any(part in EXCLUDE for part in relative.parts) and path.name not in {'.git','CHECKPOINT.md'} and path.suffix not in {'.pyc','.so','.dll','.exe','.onnx'}

def main():
    output=SUPPORT/'Free-Bible-Reader-0.3.0-Android-Speech-Sources.zip'
    ort=SUPPORT/'onnxruntime-v1.22.0-source.zip'
    if not ort.is_file():raise RuntimeError('The complete pinned ONNX Runtime source archive is required')
    with zipfile.ZipFile(ort) as native_source:
        if native_source.testzip():raise RuntimeError('ONNX Runtime source archive CRC failure')
    records=[]
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        first_party_license=ROOT/'LICENSE'
        archive.write(first_party_license,'free-bible-reader/LICENSE')
        with first_party_license.open('rb') as stream:license_sha=hashlib.file_digest(stream,'sha256').hexdigest()
        records.append({'path':'free-bible-reader/LICENSE','bytes':first_party_license.stat().st_size,'sha256':license_sha})
        for base,prefix in [(SUPPORT/'piper-kotlin','upstream/piper-kotlin'),(ROOT/'android/speech','free-bible-reader/android/speech')]:
            for path in sorted(base.rglob('*')):
                if not eligible(path,base):continue
                name=prefix+'/'+path.relative_to(base).as_posix();archive.write(path,name)
                with path.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
                records.append({'path':name,'bytes':path.stat().st_size,'sha256':sha})
        archive.write(ort,'upstream/onnxruntime-v1.22.0-source.zip',compress_type=zipfile.ZIP_STORED)
        with ort.open('rb') as stream:ort_sha=hashlib.file_digest(stream,'sha256').hexdigest()
        records.append({'path':'upstream/onnxruntime-v1.22.0-source.zip','bytes':ort.stat().st_size,'sha256':ort_sha})
        manifest={'schema_version':1,'files':records,'source_origins':json.loads((ROOT/'android/speech/source-origins.json').read_text()),'excluded':'voice weights, personal databases, user settings, Git metadata and compiled binaries'}
        archive.writestr('SOURCE-MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    with output.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise RuntimeError('Corresponding-source ZIP CRC failure')
    print(json.dumps({'file':output.name,'files':len(records),'bytes':output.stat().st_size,'sha256':digest},indent=2))

if __name__=='__main__':main()
