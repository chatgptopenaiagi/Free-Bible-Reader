[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$BaseArtifactDirectory,
    [Parameter(Mandatory)][string]$DestinationArtifactDirectory,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedBaseManifestSha256,
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedExecutableSha256,
    [string]$RunId
)
$ErrorActionPreference='Stop'
$ProductRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$Version=(Get-Content -LiteralPath (Join-Path $ProductRoot 'package.json') -Raw|ConvertFrom-Json).version
$BaseArtifactDirectory=[IO.Path]::GetFullPath($BaseArtifactDirectory)
$DestinationArtifactDirectory=[IO.Path]::GetFullPath($DestinationArtifactDirectory)
$DistPrefix=[IO.Path]::GetFullPath((Join-Path $ProductRoot 'dist'))+[IO.Path]::DirectorySeparatorChar
foreach($Path in @($BaseArtifactDirectory,$DestinationArtifactDirectory)){if(!$Path.StartsWith($DistPrefix,[StringComparison]::OrdinalIgnoreCase)){throw 'Promotion paths must remain under this project dist directory'}}
if($BaseArtifactDirectory -eq $DestinationArtifactDirectory -or $DestinationArtifactDirectory.StartsWith($BaseArtifactDirectory+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Promotion destination must be separate from the verified base artifact'}
if(Test-Path -LiteralPath $DestinationArtifactDirectory){throw 'Promotion destination is create-only and must not already exist'}
if(!$RunId){$RunId='promote-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)}
if($RunId -notmatch '^[a-zA-Z0-9_-]{1,100}$'){throw 'Invalid promotion run ID'}
$Evidence=Join-Path $ProductRoot ('reports\MISSION-FBR-003\evidence\'+$RunId)
if(Test-Path -LiteralPath $Evidence){throw 'Promotion evidence is create-only'}
New-Item -ItemType Directory -Path $Evidence|Out-Null
function Hash([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Write-NewJson([string]$Path,$Value){if(Test-Path -LiteralPath $Path){throw 'Create-only JSON output already exists'};$Value|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $Path -Encoding utf8}
function Safe-BundlePath([string]$Root,[string]$Relative){
    if(!$Relative -or [IO.Path]::IsPathRooted($Relative) -or $Relative.Contains(':') -or @($Relative.Replace('\','/').Split('/')|Where-Object {$_ -in @('','.','..')}).Count){throw 'Unsafe bundle manifest path'}
    $Path=[IO.Path]::GetFullPath((Join-Path $Root $Relative))
    if(!$Path.StartsWith($Root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Bundle path escaped root'}
    return $Path
}
$BaseManifestPath=Join-Path $BaseArtifactDirectory 'app-build-manifest.json'
$BaseBundle=Join-Path $BaseArtifactDirectory 'FreeBibleReader'
$DestinationBundle=Join-Path $DestinationArtifactDirectory 'FreeBibleReader'
$Result=[ordered]@{status='RUNNING';version=$Version;run_id=$RunId;started_utc=[DateTime]::UtcNow.ToString('o');base_artifact_directory=$BaseArtifactDirectory;destination_artifact_directory=$DestinationArtifactDirectory;build_executed=$false;installer_compiled=$false;installation_executed=$false;runtime_source_modified=$false}
try{
    $BaseManifestSha=Hash $BaseManifestPath
    if($BaseManifestSha -ne $ExpectedBaseManifestSha256){throw 'Base build manifest differs from the explicitly verified hash'}
    $Base=Get-Content -LiteralPath $BaseManifestPath -Raw|ConvertFrom-Json
    if($Base.version -ne $Version -or $Base.executable_sha256 -ne $ExpectedExecutableSha256){throw 'Base version or executable identity differs from verified inputs'}
    $Tree=@(Get-ChildItem -LiteralPath $BaseBundle -Recurse -Force)
    if((Get-Item -LiteralPath $BaseBundle).Attributes -band [IO.FileAttributes]::ReparsePoint -or @($Tree|Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count){throw 'Base bundle contains filesystem links'}
    $BaseFiles=@($Tree|Where-Object {!$_.PSIsContainer})
    if($BaseFiles.Count -ne @($Base.files).Count -or @($Base.files.relative_path|ForEach-Object {$_.ToLowerInvariant()}|Sort-Object -Unique).Count -ne @($Base.files).Count){throw 'Base bundle tree differs from its exact manifest'}
    foreach($File in $Base.files){$Path=Safe-BundlePath $BaseBundle $File.relative_path;if(!(Test-Path -LiteralPath $Path -PathType Leaf) -or (Get-Item -LiteralPath $Path).Length -ne $File.bytes -or (Hash $Path) -ne $File.sha256){throw "Verified base bundle changed: $($File.relative_path)"}}
    if((Hash (Join-Path $BaseBundle 'FreeBibleReader.exe')) -ne $ExpectedExecutableSha256){throw 'Verified base executable changed'}
    $Additions=@(foreach($Name in @('TTS-SOURCES.md','TTS-SOURCES.json')){
        $Source=Join-Path $ProductRoot ('licenses\'+$Name);$Relative='_internal\licenses\'+$Name
        if(Test-Path -LiteralPath (Safe-BundlePath $BaseBundle $Relative)){throw 'Base already contains a promotion note; refusing a different promotion scope'}
        [ordered]@{relative_path=$Relative;source_relative_path=('licenses/'+$Name);bytes=(Get-Item -LiteralPath $Source).Length;sha256=Hash $Source}
    })
    $RequiredBytes=($BaseFiles|Measure-Object -Property Length -Sum).Sum+($Additions|Measure-Object -Property bytes -Sum).Sum+100MB
    $Free=([IO.DriveInfo]::new([IO.Path]::GetPathRoot($DestinationArtifactDirectory))).AvailableFreeSpace
    if($Free -lt $RequiredBytes){throw 'Insufficient free storage for a separate preserved promotion bundle'}
    # Both fully resolved recursive copy paths were checked against this project's dist boundary above.
    New-Item -ItemType Directory -Path $DestinationArtifactDirectory|Out-Null
    Copy-Item -LiteralPath $BaseBundle -Destination $DestinationArtifactDirectory -Recurse
    foreach($Addition in $Additions){$Target=Safe-BundlePath $DestinationBundle $Addition.relative_path;if(Test-Path -LiteralPath $Target){throw 'Promotion refuses to overwrite an existing file'};Copy-Item -LiteralPath (Join-Path $ProductRoot $Addition.source_relative_path) -Destination $Target}
    $Files=@(Get-ChildItem -LiteralPath $DestinationBundle -Recurse -File|Sort-Object FullName|ForEach-Object {[ordered]@{relative_path=[IO.Path]::GetRelativePath($DestinationBundle,$_.FullName);bytes=$_.Length;sha256=Hash $_.FullName}})
    if($Files.Count -ne @($Base.files).Count+2){throw 'Promoted bundle must contain exactly the verified base plus two notes'}
    $Index=@{};foreach($File in $Files){$Index[$File.relative_path.Replace('\','/')]= $File}
    foreach($File in @($Base.files)+$Additions){$Observed=$Index[$File.relative_path.Replace('\','/')];if(!$Observed -or $Observed.bytes -ne $File.bytes -or $Observed.sha256 -ne $File.sha256){throw "Promoted file differs from its exact expected input: $($File.relative_path)"}}
    $Pins=Get-Content -LiteralPath (Join-Path $ProductRoot 'data\build-inputs.json') -Raw|ConvertFrom-Json
    if($Pins.application_version -ne $Version -or @($Pins.inputs).Count -ne 7){throw 'Unexpected portable input version/count'}
    $PinnedChecks=@(foreach($Pin in $Pins.inputs){$Observed=$Index['_internal/'+$Pin.path];if(!$Observed -or $Observed.bytes -ne $Pin.bytes -or $Observed.sha256 -ne $Pin.sha256){throw "Promoted pinned input mismatch: $($Pin.path)"};[ordered]@{path=$Pin.path;sha256=$Observed.sha256;matches=$true}})
    $Speech=Get-Content -LiteralPath (Join-Path $ProductRoot 'runtime\espeak-ng-runtime.json') -Raw|ConvertFrom-Json
    if(@($Speech.files).Count -ne 444){throw 'Unexpected eSpeak manifest count'}
    foreach($File in $Speech.files){$Observed=$Index['_internal/runtime/espeak-ng/'+$File.path];if(!$Observed -or $Observed.bytes -ne $File.bytes -or $Observed.sha256 -ne $File.sha256){throw "Promoted eSpeak mismatch: $($File.path)"}}
    $NewManifest=Join-Path $DestinationArtifactDirectory 'app-build-manifest.json'
    $Promotion=[ordered]@{kind='verified-bundle-plus-two-source-notes';base_manifest_sha256=$BaseManifestSha;base_manifest_path=$BaseManifestPath;base_executable_sha256=$ExpectedExecutableSha256;base_files_verified=@($Base.files).Count;additions=$Additions;no_runtime_file_changes=$true;promotion_script_sha256=Hash $PSCommandPath}
    Write-NewJson $NewManifest ([ordered]@{version=$Version;created_utc=[DateTime]::UtcNow.ToString('o');build_root=$DestinationBundle;executable_sha256=Hash (Join-Path $DestinationBundle 'FreeBibleReader.exe');files=$Files;source_workspace=$ProductRoot;promotion=$Promotion})
    $Result.status='PASS';$Result.base_manifest_sha256=$BaseManifestSha;$Result.manifest=$NewManifest;$Result.manifest_sha256=Hash $NewManifest;$Result.base_files_verified=@($Base.files).Count;$Result.promoted_file_count=$Files.Count;$Result.additions=$Additions;$Result.executable_sha256=Hash (Join-Path $DestinationBundle 'FreeBibleReader.exe');$Result.pinned_inputs=$PinnedChecks;$Result.espeak_files_verified=444;$Result.free_bytes_before=$Free;$Result.required_bytes=$RequiredBytes
}catch{$Result.status='FAIL';$Result.error=$_.Exception.Message;throw}
finally{$Result.completed_utc=[DateTime]::UtcNow.ToString('o');Write-NewJson (Join-Path $Evidence 'promotion-result.json') $Result;$Result|ConvertTo-Json -Depth 12}
