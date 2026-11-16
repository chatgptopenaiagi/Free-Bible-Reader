"""Reproduce Android speech build inputs without changing pristine upstream checkouts.

Run with the existing build Python. Models are public, pinned separately by the
application's studio/voice_manifest.json. No installed user-data directory is read.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

WORKSPACE = Path(__file__).resolve().parents[2]
SUPPORT = WORKSPACE / 'build-support/android-speech'
UPSTREAM = SUPPORT / 'piper-kotlin'
REVISION = '287b89079336d0d02f02d2bc96e93b7ca1e72bc5'
ORT_VERSION = '1.22.0'
ORT_SOURCE_COMMIT = 'f217402897f40ebba457e2421bc0a4702771968e'
# Matches the official Maven Central SHA-256 sidecar. ORT1.31's ARM64
# initializer failed under the tested emulator native bridge; 1.22 passed.
ORT_SHA256 = '04a4617a9c797cf49225595e45b5546081cb34c86ac817581141577d3b7dbfe2'
EXPECTED_GITLINKS = {
    'espeak-ng': '699e79690f23e2558d990a3a78b0050745b96932',
    'piper1-gpl': '74ac24e7e8e2e57a5e1fada5505c74e3d9c1843a',
    'sonic': 'b93885dcb70aae50c6f76b0fe4e0868f029a077e',
}

def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def run(*args):
    return subprocess.check_output(args, text=True).strip()

def main():
    SUPPORT.mkdir(parents=True, exist_ok=True)
    git = shutil.which('git') or r'C:\Program Files\Git\cmd\git.exe'
    if not UPSTREAM.exists():
        subprocess.run([git, 'clone', '--no-checkout', 'https://github.com/piper-tts-apps/piper-kotlin.git', str(UPSTREAM)], check=True)
        subprocess.run([git, '-C', str(UPSTREAM), 'checkout', REVISION], check=True)
        subprocess.run([git, '-C', str(UPSTREAM), 'submodule', 'update', '--init', '--recursive'], check=True)
    if run(git, '-C', str(UPSTREAM), 'rev-parse', 'HEAD') != REVISION:
        raise RuntimeError('The upstream speech checkout has a different revision')
    if run(git, '-C', str(UPSTREAM), 'status', '--porcelain'):
        raise RuntimeError('Pristine upstream checkout is modified')
    for name, expected in EXPECTED_GITLINKS.items():
        if run(git, '-C', str(UPSTREAM / 'third-party' / name), 'rev-parse', 'HEAD') != expected:
            raise RuntimeError(f'Unexpected {name} revision')
    adapted = SUPPORT / 'piper-adapted'
    if not adapted.exists():
        shutil.copytree(UPSTREAM / 'third-party/piper1-gpl', adapted, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    # The upstream CMake applies its two declared patches to this dedicated copy.
    aar = SUPPORT / f'onnxruntime-android-{ORT_VERSION}.aar'
    url = f'https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/{ORT_VERSION}/{aar.name}'
    if not aar.exists():
        temporary = aar.with_suffix('.part')
        urllib.request.urlretrieve(url, temporary)
        temporary.replace(aar)
    actual = digest(aar)
    if actual != ORT_SHA256:
        raise RuntimeError('ONNX Runtime pinned SHA-256 mismatch')
    ort = SUPPORT / f'onnxruntime-{ORT_VERSION}'
    with zipfile.ZipFile(aar) as package:
        for name in package.namelist():
            destination = None
            if name.startswith('headers/') and name.endswith('.h'):
                destination = ort / 'include' / Path(name).name
            for abi in ('arm64-v8a', 'x86_64'):
                if name == f'jni/{abi}/libonnxruntime.so':
                    destination = ort / 'lib' / abi / 'libonnxruntime.so'
            if destination:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with package.open(name) as source, destination.open('wb') as target:
                    shutil.copyfileobj(source, target)
    for abi in ('arm64-v8a', 'x86_64'):
        if not (ort / 'lib' / abi / 'libonnxruntime.so').is_file():
            raise RuntimeError('Missing ONNX Runtime ABI ' + abi)
    receipt = {'piper_kotlin': {'repository': 'https://github.com/piper-tts-apps/piper-kotlin', 'revision': REVISION},
               'submodules': EXPECTED_GITLINKS, 'onnxruntime': {'version': ORT_VERSION, 'url': url, 'sha256': actual, 'bytes': aar.stat().st_size, 'source': f'https://github.com/microsoft/onnxruntime/tree/{ORT_SOURCE_COMMIT}', 'source_commit': ORT_SOURCE_COMMIT},
               'patches': [{'path': str(p.relative_to(UPSTREAM)).replace('\\', '/'), 'sha256': digest(p)} for p in sorted((UPSTREAM / 'piper-engine/src/main/cpp/patches/piper1-gpl').glob('*.patch'))],
               'abis': ['arm64-v8a', 'x86_64'], 'pristine_upstream_preserved': True}
    (SUPPORT / 'source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
