"""Stage only pinned eSpeak Romanian/bootstrap data, never models or Bible files."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'build-support/android-speech/piper-kotlin/third-party/espeak-ng'
REVISION='699e79690f23e2558d990a3a78b0050745b96932'
DATA=ROOT/'build-support/android-assets/speech/fbr-speech/espeak-ng-data'
DEST=ROOT/'build-support/android-assets/voice-addon/espeak-ro'
SELECTION=('phondata','phonindex','phontab','intonations','ro_dict','en_dict','lang/roa/ro','lang/gmw/en')

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    git=shutil.which('git') or r'C:\Program Files\Git\cmd\git.exe'
    revision=subprocess.check_output([git,'-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()
    if revision!=REVISION:raise RuntimeError('Unexpected eSpeak source revision')
    if subprocess.check_output([git,'-C',str(SOURCE),'status','--porcelain'],text=True).strip():raise RuntimeError('Pristine eSpeak source was modified')
    full=json.loads((DATA.parent/'asset-manifest.json').read_text(encoding='utf-8'))
    pins={v['path']:v for v in full['files']}
    files=[]
    for relative in SELECTION:
        source=DATA/relative;pin=pins.get('espeak-ng-data/'+relative)
        if not pin or not source.is_file() or source.stat().st_size!=pin['bytes'] or sha(source)!=pin['sha256']:raise RuntimeError('Prepared eSpeak data differs from its verified manifest: '+relative)
        target=DEST/'espeak-ng-data'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        files.append({'path':target.relative_to(DEST).as_posix(),'bytes':target.stat().st_size,'sha256':sha(target)})
    for source in sorted(SOURCE.glob('COPYING*')):
        if not source.is_file():continue
        target=DEST/'licenses'/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        files.append({'path':target.relative_to(DEST).as_posix(),'bytes':target.stat().st_size,'sha256':sha(target)})
    allowed={v['path'] for v in files}|{'manifest.json'}
    extra=[str(v.relative_to(DEST)) for v in DEST.rglob('*') if v.is_file() and v.relative_to(DEST).as_posix() not in allowed]
    if extra:raise RuntimeError('Unexpected staged files; preserved for inspection: '+repr(extra))
    manifest={'schema_version':1,'engine':'eSpeak NG','source_repository':'https://github.com/espeak-ng/espeak-ng','source_revision':REVISION,'advertised_locales':['ro-RO'],'voice_name':'com.freebiblereader.voice.ro.ro-RO.espeak','quality':'basic formant; not a neural model','english_bootstrap_only':True,'files':files}
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(files),'bytes':sum(v['bytes'] for v in files),'manifest_sha256':sha(DEST/'manifest.json'),'private_or_biblical_data':False,'voice_models':0},indent=2))

if __name__=='__main__':main()
