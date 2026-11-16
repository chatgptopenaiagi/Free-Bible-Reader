[CmdletBinding()]
param(
    [ValidateSet('App','ProductionInstaller','TestInstaller','All')][string]$Phase='App',
    [string]$BuildPython,
    [string]$InnoCompiler,
    [string]$ArtifactDirectory,
    [string]$RunId
)
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$false
$ProductRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$Version=(Get-Content -LiteralPath (Join-Path $ProductRoot 'package.json') -Raw | ConvertFrom-Json).version
if($Version -notmatch '^\d+\.\d+\.\d+$'){throw 'A stable application version is required'}
if(!$BuildPython){$BuildPython=Join-Path $ProductRoot '.build-venv\Scripts\python.exe'}
if(!$InnoCompiler){$InnoCompiler=Join-Path $ProductRoot '.build-tools\InnoSetup\ISCC.exe'}
if(!$ArtifactDirectory){$ArtifactDirectory=Join-Path $ProductRoot ('dist\'+$Version)}
$ArtifactDirectory=[IO.Path]::GetFullPath($ArtifactDirectory)
$DistPrefix=[IO.Path]::GetFullPath((Join-Path $ProductRoot 'dist'))+[IO.Path]::DirectorySeparatorChar
if(!$ArtifactDirectory.StartsWith($DistPrefix,[StringComparison]::OrdinalIgnoreCase)){throw 'Versioned artifact directory must remain under this project dist directory'}
if(!$RunId){$RunId='build-'+$Version.Replace('.','-')+'-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,6)}
if($RunId -notmatch '^[a-zA-Z0-9_-]{1,100}$'){throw 'Invalid run ID'}
$Evidence=Join-Path $ProductRoot ('reports\MISSION-FBR-004\evidence\'+$RunId)
if(Test-Path -LiteralPath $Evidence){throw 'Create-only build run already exists; choose another RunId'}
New-Item -ItemType Directory -Path $Evidence | Out-Null
function Write-NewJson([string]$Path,$Value){if(Test-Path -LiteralPath $Path){throw "Evidence already exists: $Path"};$Value | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $Path -Encoding utf8}
function Hash([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Get-PyInstallerArguments([string]$ProjectRoot,[string]$OutputPath,[string]$WorkPath){
    # PyInstaller resolves data sources against the generated spec location, not cwd.
    $ArgsList=@('-m','PyInstaller','--noupx','--windowed','--onedir','--name','FreeBibleReader','--icon',(Join-Path $ProjectRoot 'assets\brand.ico'),'--distpath',$OutputPath,'--workpath',$WorkPath,'--specpath',$WorkPath)
    $Mappings=[ordered]@{'workbench'='workbench';'ui-core'='ui-core';'studio'='studio';'data'='data';'parser'='parser';'runtime'='runtime';'licenses'='licenses';'engines\visual\component.js'='engines/visual';'engines\visual\component.css'='engines/visual'}
    foreach($Mapping in $Mappings.GetEnumerator()){$Source=[IO.Path]::GetFullPath((Join-Path $ProjectRoot $Mapping.Key));$ArgsList+='--add-data';$ArgsList+=($Source+';'+$Mapping.Value)}
    $ArgsList+=@('--hidden-import','engines.visual.engine','--hidden-import','engines.visual.layout','--hidden-import','engines.aggregate.engine','--hidden-import','engines.phrase.engine','--hidden-import','studio.piper_worker','--collect-all','piper','--collect-all','onnxruntime','--collect-all','numpy','--collect-all','docx','--collect-all','reportlab',(Join-Path $ProjectRoot 'app.py'))
    return $ArgsList
}


function Get-PinnedBuildInputs([string]$ProjectRoot,[string]$ApplicationVersion){
    $InputManifest=Join-Path $ProjectRoot 'data\build-inputs.json'
    $Config=Get-Content -LiteralPath $InputManifest -Raw | ConvertFrom-Json
    if($Config.kind -ne 'free-bible-reader-build-inputs' -or $Config.schema_version -ne 1 -or $Config.application_version -ne $ApplicationVersion){throw 'Unsupported portable build-input manifest kind/schema/application version'}
    $Allowed=@('data/reader.sqlite','data/xref_visual.sqlite','data/xref_aggregate.sqlite','data/xref_phrase.sqlite','data/xref_reference.sqlite','runtime/node.exe','data/romanian.sqlite')
    if(@($Config.inputs).Count -ne 7 -or @($Config.inputs.path | Sort-Object -Unique).Count -ne 7){throw 'Portable build-input manifest must contain exactly seven unique inputs'}
    $Research=Get-Content -LiteralPath (Join-Path $ProjectRoot 'data\research-release.json') -Raw | ConvertFrom-Json
    if($Config.research_data_version -ne $Research.version){throw 'Research data release version differs from pinned build inputs'}
    $Checks=@(foreach($InputFile in $Config.inputs){
        if($InputFile.path -cnotin $Allowed -or $InputFile.sha256 -notmatch '^[0-9a-fA-F]{64}$' -or !$InputFile.version){throw 'Invalid pinned relative input path/hash/version'}
        if($InputFile.role -eq 'public-research-snapshot'){$Asset=@($Research.assets | Where-Object {('data/'+$_.name) -eq $InputFile.path});if($Asset.Count -ne 1 -or $Asset[0].sha256 -ne $InputFile.sha256 -or $InputFile.version -ne $Research.version){throw 'Pinned research input differs from public release metadata'}}
        $Path=[IO.Path]::GetFullPath((Join-Path $ProjectRoot $InputFile.path))
        if(!$Path.StartsWith($ProjectRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Pinned input escaped the project root'}
        $Actual=Hash $Path;$Bytes=(Get-Item -LiteralPath $Path).Length
        [ordered]@{relative_path=$InputFile.path;version=$InputFile.version;sha256=$Actual;expected_sha256=$InputFile.sha256.ToLowerInvariant();bytes=$Bytes;matches_preserved_input=($Actual -eq $InputFile.sha256 -and $Bytes -eq $InputFile.bytes)}
    })
    if(@($Checks | Where-Object matches_preserved_input -ne $true).Count){throw 'Bundled Node or public database snapshots changed from portable pinned inputs'}
    return $Checks
}

function Get-VerifiedEspeakRuntime([string]$ProjectRoot){
    $RuntimeRoot=[IO.Path]::GetFullPath((Join-Path $ProjectRoot 'runtime\espeak-ng'))
    $RuntimeManifest=Join-Path $ProjectRoot 'runtime\espeak-ng-runtime.json'
    $Config=Get-Content -LiteralPath $RuntimeManifest -Raw | ConvertFrom-Json
    if($Config.component -ne 'eSpeak NG' -or $Config.runtime_version -ne '1.52.0' -or $Config.source_msi_sha256 -ne '7f673c709ea5dd579d3b5ebb98688cc575328a6ab7438d2bc405b88cedaeafb9'){throw 'Unsupported pinned eSpeak runtime provenance'}
    if(!(Test-Path -LiteralPath $RuntimeRoot -PathType Container)){throw 'Missing bundled eSpeak runtime; restore the committed runtime/espeak-ng tree'}
    if((Get-Item -LiteralPath $RuntimeRoot).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Bundled eSpeak runtime must not be a filesystem link'}
    $Entries=@($Config.files)
    if($Entries.Count -ne 444 -or @($Entries.path | ForEach-Object {$_.ToLowerInvariant()} | Sort-Object -Unique).Count -ne 444){throw 'eSpeak manifest must contain exactly 444 unique payload files'}
    $Tree=@(Get-ChildItem -LiteralPath $RuntimeRoot -Recurse -Force)
    if(@($Tree | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }).Count){throw 'Bundled eSpeak runtime contains a filesystem link'}
    $ActualFiles=@($Tree | Where-Object { !$_.PSIsContainer })
    if($ActualFiles.Count -ne 444){throw 'Bundled eSpeak runtime has missing or additional files'}
    $Checks=@(foreach($Entry in $Entries){
        $Relative=[string]$Entry.path
        if(!$Relative -or $Relative.Contains('\') -or $Relative.Contains(':') -or $Relative.StartsWith('/') -or @($Relative.Split('/') | Where-Object {$_ -in @('','.','..')}).Count -or $Entry.sha256 -notmatch '^[0-9a-fA-F]{64}$' -or $Entry.bytes -lt 0){throw 'Unsafe or invalid eSpeak payload entry'}
        $Path=[IO.Path]::GetFullPath((Join-Path $RuntimeRoot $Relative))
        if(!$Path.StartsWith($RuntimeRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or !(Test-Path -LiteralPath $Path -PathType Leaf)){throw "Missing or unsafe eSpeak payload: $Relative"}
        $Bytes=(Get-Item -LiteralPath $Path).Length
        $Actual=Hash $Path
        if($Bytes -ne $Entry.bytes -or $Actual -ne $Entry.sha256){throw "Bundled eSpeak payload changed: $Relative"}
        [ordered]@{relative_path=('runtime/espeak-ng/'+$Relative);bytes=$Bytes;sha256=$Actual;matches_manifest=$true}
    })
    foreach($Required in @('espeak-ng.exe','libespeak-ng.dll','COPYING')){if($Required -cnotin @($Entries.path)){throw "Missing required eSpeak payload entry: $Required"}}
    return [ordered]@{component='eSpeak NG';version='1.52.0';manifest_sha256=Hash $RuntimeManifest;files_checked=$Checks.Count;bytes=($ActualFiles | Measure-Object -Property Length -Sum).Sum;all_files_match=$true;files=$Checks}
}

$BuildRoot=Join-Path $ArtifactDirectory 'FreeBibleReader'
$BuildManifest=Join-Path $ArtifactDirectory 'app-build-manifest.json'
$Result=[ordered]@{phase=$Phase;version=$Version;run_id=$RunId;evidence_directory=$Evidence;artifact_directory=$ArtifactDirectory;started_utc=[DateTime]::UtcNow.ToString('o');status='RUNNING';build_executed=$false;install_executed=$false}
try{
    foreach($Needed in @('runtime\node.exe','data\reader.sqlite','data\xref_visual.sqlite','data\xref_aggregate.sqlite','data\xref_phrase.sqlite','data\xref_reference.sqlite','workbench\index.html','ui-core\index.js')){if(!(Test-Path -LiteralPath (Join-Path $ProductRoot $Needed))){throw "Missing build input: $Needed"}}
    $AppVersion=[regex]::Match((Get-Content -LiteralPath (Join-Path $ProductRoot 'app.py') -Raw),"(?m)^VERSION='([^']+)'").Groups[1].Value
    $HealthVersion=[regex]::Match((Get-Content -LiteralPath (Join-Path $ProductRoot 'workbench\server.py') -Raw),"'version':'([^']+)'").Groups[1].Value
    $InstallerVersion=[regex]::Match((Get-Content -LiteralPath (Join-Path $ProductRoot 'installer\FreeBibleReader.iss') -Raw),'#define MyAppVersion "([^"]+)"').Groups[1].Value
    if($AppVersion -ne $Version -or $HealthVersion -ne $Version -or $InstallerVersion -ne $Version){throw 'Application/package/health/installer versions differ'}
    $Result.preserved_input_checks=@(Get-PinnedBuildInputs $ProductRoot $Version)
    $Result.speech_runtime_checks=Get-VerifiedEspeakRuntime $ProductRoot
    $Result.portable_input_manifest_sha256=Hash (Join-Path $ProductRoot 'data\build-inputs.json')
    New-Item -ItemType Directory -Path $ArtifactDirectory -Force | Out-Null
    Push-Location $ProductRoot
    try{
        if($Phase -in @('App','All')){
            if(!(Test-Path -LiteralPath $BuildPython)){throw 'Use the existing isolated build Python or pass -BuildPython'}
            if((Test-Path -LiteralPath $BuildRoot) -or (Test-Path -LiteralPath $BuildManifest)){throw 'Create-only app build refuses an existing versioned bundle; choose a fresh ArtifactDirectory'}
            $Work=Join-Path $ProductRoot ('build\'+$Version+'\'+$RunId)
            New-Item -ItemType Directory -Path $Work -Force | Out-Null
            $Arguments=@(Get-PyInstallerArguments $ProductRoot $ArtifactDirectory $Work)
            & $BuildPython @Arguments 2>&1 | Tee-Object -FilePath (Join-Path $Evidence 'pyinstaller.log')
            if($LASTEXITCODE -ne 0){throw 'Executable build failed'}
            $Files=@(Get-ChildItem -LiteralPath $BuildRoot -Recurse -File | Sort-Object FullName | ForEach-Object {[ordered]@{relative_path=[IO.Path]::GetRelativePath($BuildRoot,$_.FullName);bytes=$_.Length;sha256=Hash $_.FullName}})
            Write-NewJson $BuildManifest ([ordered]@{version=$Version;created_utc=[DateTime]::UtcNow.ToString('o');build_root=$BuildRoot;executable_sha256=Hash (Join-Path $BuildRoot 'FreeBibleReader.exe');files=$Files;source_workspace=$ProductRoot})
            $Result.build_executed=$true
        }
        if($Phase -in @('ProductionInstaller','TestInstaller','All')){
            if(!(Test-Path -LiteralPath $InnoCompiler)){throw 'Use the recorded official project-scoped Inno compiler or pass -InnoCompiler'}
            if(!(Test-Path -LiteralPath $BuildManifest)){throw 'A versioned app build manifest is required before compiling installers'}
            $Manifest=Get-Content -LiteralPath $BuildManifest -Raw | ConvertFrom-Json
            if($Manifest.version -ne $Version -or $Manifest.executable_sha256 -ne (Hash (Join-Path $BuildRoot 'FreeBibleReader.exe'))){throw 'App build manifest/version mismatch'}
            foreach($File in $Manifest.files){$Path=[IO.Path]::GetFullPath((Join-Path $BuildRoot $File.relative_path));if(!$Path.StartsWith($BuildRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or (Hash $Path) -ne $File.sha256){throw 'App bundle changed after its build manifest was recorded'}}
            foreach($Kind in @('production','test')){
                if($Phase -eq 'ProductionInstaller' -and $Kind -ne 'production'){continue}
                if($Phase -eq 'TestInstaller' -and $Kind -ne 'test'){continue}
                $Suffix=if($Kind -eq 'test'){'windows-x64-verification-setup.exe'}else{'windows-x64-setup.exe'}
                $Target=Join-Path $ArtifactDirectory ('Free-Bible-Reader-'+$Version+'-'+$Suffix)
                if((Test-Path -LiteralPath $Target) -or (Test-Path -LiteralPath ($Target+'.manifest.json'))){throw "Create-only installer refuses existing artifact: $Target"}
                $Arguments=@("/DFBR_BUILD_ROOT=$BuildRoot","/DFBR_OUTPUT_DIR=$ArtifactDirectory")
                if($Kind -eq 'test'){$Arguments+='/DFBR_TEST_INSTALL=1'}
                $Arguments+='installer\FreeBibleReader.iss'
                & $InnoCompiler @Arguments 2>&1 | Tee-Object -FilePath (Join-Path $Evidence ('inno-'+$Kind+'.log'))
                if($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $Target)){throw "$Kind installer compile failed"}
                Write-NewJson ($Target+'.manifest.json') ([ordered]@{version=$Version;kind=$Kind;created_utc=[DateTime]::UtcNow.ToString('o');installer=$Target;bytes=(Get-Item -LiteralPath $Target).Length;sha256=Hash $Target;app_build_manifest=$BuildManifest;app_build_manifest_sha256=Hash $BuildManifest;app_executable_sha256=$Manifest.executable_sha256;app_id=if($Kind -eq 'test'){'{8D2365AC-9142-4BA8-A6A3-C0B07D2689E4}'}else{'{86957E89-5028-4A68-ACDA-98ECD7AD2D6F}'};test_variant_is_production_installer=($Kind -ne 'test');test_variant_scope=if($Kind -eq 'test'){'Different AppId; no uninstall registration, shortcuts, automatic app closing or Run entry. Same app bundle as production.'}else{'Normal production identity preserved.'}})
            }
        }
    }finally{Pop-Location}
    $Result.status='PASS'
}catch{$Result.status='FAIL';$Result.error=$_.Exception.Message;throw}
finally{$Result.completed_utc=[DateTime]::UtcNow.ToString('o');Write-NewJson (Join-Path $Evidence 'build-result.json') $Result;$Result | ConvertTo-Json -Depth 8}
