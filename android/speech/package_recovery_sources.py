"""Create a scoped source supplement, NOT a self-contained native source bundle.

Run only after the tested application source is frozen. No model weights,
databases, local properties, evidence, user settings or compiled output are read.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[2]
BASE={
    'name':'Free-Bible-Reader-0.3.0-Android-Speech-Sources.zip',
    'url':'https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/download/v0.3.0-beta.1/Free-Bible-Reader-0.3.0-Android-Speech-Sources.zip',
    'bytes':302100990,
    'sha256':'e60d87e2400fc58a7c9bdcc76ee4b5ec950235b6cea450323266e29c16c35cff',
    'role':'Required unchanged upstream native source companion: Piper Kotlin, OHF Piper, eSpeak NG, Sonic and complete ONNX Runtime 1.22.0 source.',
}
EXCLUDE_PARTS={'.git','.gradle','.cxx','build','evidence','node_modules','__pycache__'}
EXCLUDE_NAMES={'local.properties','CHECKPOINT.md','VERIFICATION.md'}
EXCLUDE_SUFFIXES={'.pyc','.so','.dll','.exe','.apk','.aab','.whl','.onnx','.sqlite','.db','.wav','.mp3','.zip','.log','.key','.pem'}
FILES=(
    'LICENSE','THIRD-PARTY-NOTICES.md','licenses/TTS-SOURCES.md',
    'studio/voice_manifest.json',
    'android/app/src/main/java/com/freebiblereader/android/MainActivity.java',
    'android/app/src/main/java/com/freebiblereader/android/PlatformAdapter.java',
    'android/app/src/main/java/com/freebiblereader/android/AndroidSpeechEngines.java',
    'android/app/src/main/java/com/freebiblereader/android/NativeAudioPlayer.java',
    'free_bible_reader/android_runtime.py','free_bible_reader/android_voice_policy.py',
    'workbench/studio/audio.js',
    'workbench/studio/i18n/audio.en.json','workbench/studio/i18n/audio.ro.json','workbench/studio/i18n/audio.de.json',
    'tests/test_android_speech_recovery.py','tests/test_android_adapters.py',
)
DIRECTORIES=('android/speech','android/voice-addon','workbench/lite')

def allowed(path):
    relative=path.relative_to(ROOT)
    return path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT.resolve()) and not any(part in EXCLUDE_PARTS for part in relative.parts) and path.name not in EXCLUDE_NAMES and path.suffix.lower() not in EXCLUDE_SUFFIXES

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def rebuild_text(version,source_ref):
    return f'''# Romanian voice recovery source supplement {version}

This ZIP is a **source supplement**, not a self-contained full native source
archive. It contains the current reader speech adapters, policy/runtime/UI,
tests, local Piper patch and complete first-party Romanian voice-companion
module. It contains no private libraries, notes, model weights or recordings.

Use it together with the full application source from the same release's Git
tag ({source_ref or 'the exact source tag/commit identified in the release notes'})
and this required unchanged native source companion:

{BASE['url']}

Exact companion size: {BASE['bytes']} bytes.
SHA-256: `{BASE['sha256']}`.
Verify the checksum before using its sources. BASE-SOURCES.json records the same
dependency in machine-readable form. The companion contains pristine pinned
Piper Kotlin/Piper/eSpeak/Sonic sources and the full ONNX Runtime 1.22.0 source
ZIP. Its SOURCE-MANIFEST.json gives per-file hashes.

## Rebuild sequence

1. Obtain the complete application source from the matching Git tag. Work in a
   fresh developer checkout, separate from installed personal data. Overlay this
   supplement's `source/` files at the application root. Do not overwrite the new
   application sources with the old companion's first-party adapter copies.
2. Retain the companion's `upstream/piper-kotlin/` and nested ONNX Runtime source
   ZIP for the exact native sources. The current `android/speech/source-origins.json`
   identifies unchanged upstream revisions and the new declared local patch.
3. For the normal verified preparation path run `python android/speech/prepare_native.py`.
   It obtains/verifies Git revisions and the pinned official ORT Android AAR.
   Source archives omit Git metadata; the preparer's routine Git revision checks
   use fresh pinned checkouts. The full source companion independently supplies
   the corresponding source files, including the full ORT source if rebuilding
   that dependency rather than using its official AAR.
4. Compile matching eSpeak data with
   `python android/speech/prepare_assets.py --cmake <host-cmake> --generator <host-generator>`.
   Use the generator suitable for the developer's toolchain. This stages matching
   data and the three hash-pinned public Piper models. Model metadata/source URLs
   are in studio/voice_manifest.json; private voice caches are never input.
5. Run `python android/voice-addon/prepare_assets.py`. It stages only the verified
   Romanian/bootstrap eSpeak data and notices for the independent companion.
6. Using the repository's Android build configuration and the documented existing
   toolchain, build the desired app targets, for example
   `gradle -p android :app:assembleLiteRelease :app:assembleUltimateRelease :voice-addon:assembleRelease -PtargetAbi=arm64-v8a`.
   Configure SDK, JDK and build-Python locations for the developer's computer.
   The tested toolchain is SDK36, NDK28.2.13676358, CMake3.22.1, JDK21,
   Gradle9.3.1 and Chaquopy17.2/Python3.14. This packager installs nothing.
7. Run the isolated policy/adapter tests and real Android acceptance tests before
   distributing a rebuilt package. Package compilation alone does not establish
   narration, speaker output or physical Vivo compatibility.

The new local patch changes eSpeak initialization to return errors rather than
exit the reader process. It is applied only to the dedicated adapted Piper copy;
pristine sources remain unchanged. Current APKs use the stated development
signing configuration, not invented production signing credentials.

First-party source retains its stated license. GPL-covered native components
retain their GPL terms and notices; the companion and this supplement must remain
clearly linked from the binary release. The new Romanian companion is a real
independent Android TextToSpeechService using basic eSpeak formant synthesis.
It does not contain Piper, ONNX, neural models or biblical/private databases.
'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',required=True)
    parser.add_argument('--source-ref',default='')
    parser.add_argument('--list',action='store_true',help='Inspect source scope without creating an archive')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{1,60}',args.version):raise ValueError('Invalid version')
    if args.source_ref and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,100}',args.source_ref):raise ValueError('Invalid source ref')
    selected={ROOT/name for name in FILES}
    for name in DIRECTORIES:selected.update(path for path in (ROOT/name).rglob('*') if allowed(path))
    for path in selected:
        if not allowed(path):raise ValueError('Missing or disallowed source: '+path.relative_to(ROOT).as_posix())
    paths=sorted(selected)
    if args.list:
        print(json.dumps({'supplement_not_self_contained':True,'files':[path.relative_to(ROOT).as_posix() for path in paths],'required_base':BASE},indent=2));return
    folder=ROOT/'build-support/android-speech';folder.mkdir(parents=True,exist_ok=True)
    output=folder/f'Free-Bible-Reader-{args.version}-Speech-Changes-and-Romanian-Voice-Sources.zip'
    records=[]
    base_manifest={'schema_version':1,'supplement_not_self_contained':True,'required_base_archive':BASE,'application_repository':'https://github.com/chatgptopenaiagi/Free-Bible-Reader','application_source_ref':args.source_ref or None,'source_ref_verified_by_packager':False}
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for path in paths:
            name='source/'+path.relative_to(ROOT).as_posix();archive.write(path,name);records.append({'path':name,'bytes':path.stat().st_size,'sha256':sha(path)})
        archive.writestr('BASE-SOURCES.json',json.dumps(base_manifest,indent=2)+'\n')
        archive.writestr('REBUILD.md',rebuild_text(args.version,args.source_ref))
        archive.writestr('SUPPLEMENT-MANIFEST.json',json.dumps({'schema_version':1,'version':args.version,'supplement_not_self_contained':True,'files':records,'required_base':BASE},indent=2)+'\n')
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():raise ValueError('ZIP CRC failure')
        for row in records:
            with archive.open(row['path']) as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=row['sha256'] or archive.getinfo(row['path']).file_size!=row['bytes']:raise ValueError('Source hash mismatch')
    print(json.dumps({'file':output.name,'bytes':output.stat().st_size,'sha256':sha(output),'source_files':len(records),'all_source_hashes_verified':True,'supplement_not_self_contained':True,'required_base_sha256':BASE['sha256']},indent=2))

if __name__=='__main__':main()
