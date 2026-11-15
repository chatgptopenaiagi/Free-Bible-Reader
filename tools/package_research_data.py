"""Build a separate release asset from the four public, derived research models."""
import hashlib,json,pathlib,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
NAMES=['xref_visual.sqlite','xref_aggregate.sqlite','xref_phrase.sqlite','xref_reference.sqlite']
def sha(path):
    with path.open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()
def main():
    target=ROOT/'dist/Free-Bible-Reader-0.1.0-research-data.zip'
    if target.exists():raise RuntimeError('Create-only release archive already exists')
    assets=[{'name':name,'bytes':(ROOT/'data'/name).stat().st_size,'sha256':sha(ROOT/'data'/name)} for name in NAMES]
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name in NAMES:archive.write(ROOT/'data'/name,arcname=name)
        archive.write(ROOT/'THIRD-PARTY-NOTICES.md',arcname='THIRD-PARTY-NOTICES.md')
        for notice in sorted((ROOT/'licenses').glob('research-*')):
            archive.write(notice,arcname='licenses/'+notice.name)
    result={'version':'0.1.0','url':'https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases/download/v0.1.0/'+target.name,'archive':target.name,'bytes':target.stat().st_size,'sha256':sha(target),'assets':assets,'scope':'Public derived research models only; no original corpus, SQL Server data, user caches or S21 content. Data retains its attributed third-party licenses.'}
    (ROOT/'data/research-release.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    installer=ROOT/'dist/Free-Bible-Reader-0.1.0-windows-x64-setup.exe'
    (ROOT/'dist/SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n' for p in [installer,target]),encoding='ascii')
    print(json.dumps({'archive_bytes':result['bytes'],'archive_sha256':result['sha256'],'uncompressed_bytes':sum(a['bytes'] for a in assets)},indent=2))
if __name__=='__main__':main()
