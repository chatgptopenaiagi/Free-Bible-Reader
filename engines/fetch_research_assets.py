"""Restore optional research assets from a checksum-verified release ZIP.

Source checkouts can omit the three large engine databases. This explicit CLI
accepts an owner-selected release archive (or HTTPS URL) and its independently
provided SHA256. It never downloads automatically during a reader request,
executes downloaded code, replaces existing data, or touches reader.sqlite.
"""
from __future__ import annotations
import argparse,contextlib,hashlib,json,pathlib,shutil,sqlite3,tempfile,urllib.parse,urllib.request,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
ASSETS=('xref_visual.sqlite','xref_aggregate.sqlite','xref_phrase.sqlite','xref_reference.sqlite')


def archive_plan(archive):
    plan={}
    for entry in archive.infolist():
        if entry.is_dir():continue
        name=entry.filename.replace('\\','/')
        if name.startswith('/')or any(part in('..','')for part in name.split('/')):raise ValueError('Unsafe archive path')
        if name in ASSETS:base=name
        elif name in tuple('data/'+value for value in ASSETS):base=name.split('/')[-1]
        else:continue
        if base in plan or not 0<entry.file_size<=2*1024**3:raise ValueError('Duplicate or oversized research asset')
        plan[base]=entry
    if set(plan)!=set(ASSETS):raise ValueError('Archive must supply all four named research databases')
    return plan


def install(archive_path,expected_sha256):
    if len(expected_sha256)!=64 or any(char not in'0123456789abcdefABCDEF'for char in expected_sha256):raise ValueError('SHA256 must contain64hex digits')
    with pathlib.Path(archive_path).open('rb')as source:observed=hashlib.file_digest(source,'sha256').hexdigest()
    if observed.lower()!=expected_sha256.lower():raise ValueError('Release archive SHA256 mismatch')
    destination=ROOT/'data';destination.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive_path)as archive:
        plan=archive_plan(archive)
        if shutil.disk_usage(destination).free<sum(entry.file_size for entry in plan.values())+100*1024**2:raise OSError('Insufficient free storage for research assets')
        with tempfile.TemporaryDirectory(prefix='research-assets-',dir=destination)as temporary:
            temporary=pathlib.Path(temporary)
            for name,entry in plan.items():
                output=temporary/name
                with archive.open(entry)as source,output.open('xb')as target:shutil.copyfileobj(source,target,1024*1024)
                with contextlib.closing(sqlite3.connect(output.as_uri()+'?mode=ro&immutable=1',uri=True))as db:
                    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Invalid research SQLite asset')
            reused=[];installed=[]
            # A source checkout may already contain the small reference seed.
            # Reuse an identical asset; preserve any existing different bytes.
            for name in ASSETS:
                current=destination/name
                if not current.exists():continue
                with current.open('rb')as stream:current_hash=hashlib.file_digest(stream,'sha256').hexdigest()
                with(temporary/name).open('rb')as stream:incoming_hash=hashlib.file_digest(stream,'sha256').hexdigest()
                if current_hash!=incoming_hash:raise FileExistsError('Existing research asset differs; preserve it before deliberate replacement')
                reused.append('data/'+name)
            for name in ASSETS:
                if not(destination/name).exists():
                    (temporary/name).rename(destination/name);installed.append('data/'+name)
    return{'status':'INSTALLED'if installed else'ALREADY_AVAILABLE','archive_sha256':observed,'assets':installed,'reused_identical_assets':reused,'reader_database_modified':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--release-zip',type=pathlib.Path);source.add_argument('--url');parser.add_argument('--sha256',required=True);args=parser.parse_args()
    if args.release_zip:result=install(args.release_zip,args.sha256)
    else:
        parsed=urllib.parse.urlsplit(args.url)
        if parsed.scheme!='https'or parsed.username or parsed.password:raise ValueError('Use an explicit HTTPS release URL without credentials')
        with tempfile.TemporaryDirectory(prefix='research-download-',dir=ROOT)as temporary:
            path=pathlib.Path(temporary)/'research.zip'
            with urllib.request.urlopen(args.url,timeout=60)as response,path.open('xb')as output:
                length=0
                while chunk:=response.read(1024*1024):
                    length+=len(chunk)
                    if length>2*1024**3:raise ValueError('Release ZIP exceeds download bound')
                    output.write(chunk)
            result=install(path,args.sha256)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
