"""Create 0.1.1 release metadata while reusing the immutable published data asset.

This utility never rebuilds databases, changes data/research-release.json, or
repackages the existing ~200 MB research ZIP. New outputs are create-only.
"""
import argparse,datetime,hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def sha(path):
    with path.open('rb') as source:return hashlib.file_digest(source,'sha256').hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--installer',type=pathlib.Path);parser.add_argument('--output-directory',type=pathlib.Path);args=parser.parse_args()
    version=json.loads((ROOT/'package.json').read_text(encoding='utf-8-sig'))['version']
    folder=(args.output_directory or ROOT/'dist'/version).resolve();installer=(args.installer or folder/f'Free-Bible-Reader-{version}-windows-x64-setup.exe').resolve()
    if not folder.is_relative_to((ROOT/'dist').resolve()):raise ValueError('Release outputs must remain in this project dist directory')
    if not installer.is_file():raise FileNotFoundError('Build and verify the new installer before preparing release metadata')
    manifest_path=folder/f'release-manifest-{version}.json';checksums=folder/f'SHA256SUMS-{version}.txt'
    if manifest_path.exists() or checksums.exists():raise FileExistsError('Create-only release metadata already exists')
    data=json.loads((ROOT/'data/research-release.json').read_text(encoding='utf-8-sig'))
    observed=[dict(item,observed_sha256=sha(ROOT/'data'/item['name'])) for item in data['assets']]
    if any(item['observed_sha256'].lower()!=item['sha256'].lower() for item in observed):raise ValueError('Public research data changed; reuse of the published asset is not justified')
    old_archive=ROOT/'dist'/data['archive']
    if old_archive.exists() and sha(old_archive).lower()!=data['sha256'].lower():raise ValueError('Existing published data archive hash mismatch')
    installer_hash=sha(installer)
    result={'application_version':version,'created_utc':datetime.datetime.now(datetime.UTC).isoformat(),'installer':{'name':installer.name,'bytes':installer.stat().st_size,'sha256':installer_hash},'research_data':data,'research_asset_reused':True,'new_research_archive_created':False,'verified_local_research_files':observed,'data_manifest_modified':False,'publication_performed':False}
    folder.mkdir(parents=True,exist_ok=True)
    with manifest_path.open('x',encoding='utf-8') as target:json.dump(result,target,indent=2)
    with checksums.open('x',encoding='ascii') as target:target.write(f'{installer_hash}  {installer.name}\n')
    print(json.dumps({'status':'PASS','manifest':str(manifest_path),'checksums':str(checksums),'research_asset_reused':data['url'],'research_sha256':data['sha256']},indent=2))
if __name__=='__main__':main()
