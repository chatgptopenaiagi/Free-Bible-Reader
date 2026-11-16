[CmdletBinding()]
param(
    [ValidateSet('Check','Restore')][string]$Mode='Check',
    [string]$Python,
    [string]$ResearchArchive
)
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$false
$ProductRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
if(!$Python){$Python=Join-Path $ProductRoot '.build-venv\Scripts\python.exe'}
$Version=(Get-Content -LiteralPath (Join-Path $ProductRoot 'package.json') -Raw|ConvertFrom-Json).version
$Pins=Get-Content -LiteralPath (Join-Path $ProductRoot 'data\build-inputs.json') -Raw|ConvertFrom-Json
if($Pins.kind -ne 'free-bible-reader-build-inputs' -or $Pins.schema_version -ne 1 -or $Pins.application_version -ne $Version){throw 'Unsupported build-input manifest'}
$Allowed=@('data/reader.sqlite','data/xref_visual.sqlite','data/xref_aggregate.sqlite','data/xref_phrase.sqlite','data/xref_reference.sqlite','runtime/node.exe','data/romanian.sqlite')
if(@($Pins.inputs).Count -ne 7 -or @($Pins.inputs.path|Sort-Object -Unique).Count -ne 7){throw 'Expected seven unique pinned build inputs'}
function Hash([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Check-Inputs {
    @(foreach($Pin in $Pins.inputs){
        if($Pin.path -cnotin $Allowed -or $Pin.sha256 -notmatch '^[0-9a-f]{64}$' -or $Pin.bytes -le 0){throw 'Invalid pinned build input'}
        $Path=Join-Path $ProductRoot $Pin.path
        $Exists=Test-Path -LiteralPath $Path -PathType Leaf
        $Actual=if($Exists){Hash $Path}else{$null}
        $Bytes=if($Exists){(Get-Item -LiteralPath $Path).Length}else{0}
        [pscustomobject]@{path=$Pin.path;exists=$Exists;matches=($Exists -and $Bytes -eq $Pin.bytes -and $Actual -eq $Pin.sha256);bytes=$Bytes;sha256=$Actual}
    })
}
function Download-Pinned([string]$Url,[string]$Target,[long]$Bytes,[string]$ExpectedSha){
    $Uri=[Uri]$Url
    if($Uri.Scheme -ne 'https' -or $Uri.UserInfo){throw 'A canonical HTTPS download without credentials is required'}
    if(Test-Path -LiteralPath $Target){throw 'Download target is create-only'}
    $Handler=[Net.Http.HttpClientHandler]::new();$Handler.UseCookies=$false;$Handler.UseDefaultCredentials=$false
    $Client=[Net.Http.HttpClient]::new($Handler);$Client.Timeout=[TimeSpan]::FromMinutes(15)
    $Response=$null;$InputStream=$null;$OutputStream=$null
    try{
        $Response=$Client.GetAsync($Uri,[Net.Http.HttpCompletionOption]::ResponseHeadersRead).GetAwaiter().GetResult()
        $Response.EnsureSuccessStatusCode()|Out-Null
        if($null -ne $Response.Content.Headers.ContentLength -and $Response.Content.Headers.ContentLength -ne $Bytes){throw 'Publisher content length differs from pinned bytes'}
        $InputStream=$Response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
        $OutputStream=[IO.File]::Open($Target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        $Buffer=[byte[]]::new(1024*1024);$Total=0L
        while(($Read=$InputStream.Read($Buffer,0,$Buffer.Length)) -gt 0){$Total+=$Read;if($Total -gt $Bytes){throw 'Download exceeded pinned byte count'};$OutputStream.Write($Buffer,0,$Read)}
        $OutputStream.Dispose();$OutputStream=$null
        if($Total -ne $Bytes -or (Hash $Target) -ne $ExpectedSha){throw 'Downloaded bytes or SHA-256 differ from pinned input'}
        return [ordered]@{url=$Url;bytes=$Total;sha256=$ExpectedSha;status='VERIFIED'}
    }finally{if($OutputStream){$OutputStream.Dispose()};if($InputStream){$InputStream.Dispose()};if($Response){$Response.Dispose()};$Client.Dispose();$Handler.Dispose()}
}
$Before=Check-Inputs
if(@($Before|Where-Object {$_.exists -and !$_.matches}).Count){throw 'An existing input differs from its pin; preserve it and investigate rather than overwriting it'}
$Restored=[Collections.Generic.List[object]]::new()
if($Mode -eq 'Restore'){
    # Downloads remain project-local. The helper never installs or executes Node.
    $Missing=@($Before|Where-Object {!$_.exists})
    if($Missing.Count){
        $DownloadRoot=Join-Path $ProductRoot ('build-support\input-restoration-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8))
        New-Item -ItemType Directory -Path $DownloadRoot|Out-Null
        if('runtime/node.exe' -in $Missing.path){
            $Pin=@($Pins.inputs|Where-Object path -eq 'runtime/node.exe')[0]
            if($Pin.version -notmatch '^\d+\.\d+\.\d+$'){throw 'Invalid pinned Node version'}
            $Url='https://nodejs.org/dist/v'+$Pin.version+'/win-x64/node.exe'
            $Downloaded=Join-Path $DownloadRoot 'node.exe'
            $Proof=Download-Pinned $Url $Downloaded $Pin.bytes $Pin.sha256
            $Target=Join-Path $ProductRoot 'runtime\node.exe'
            if(Test-Path -LiteralPath $Target){throw 'Node appeared during restoration; refusing to overwrite it'}
            Move-Item -LiteralPath $Downloaded -Destination $Target
            $Restored.Add([ordered]@{path='runtime/node.exe';download=$Proof;execution_performed=$false})
        }
        if(@($Missing|Where-Object path -Like 'data/xref_*.sqlite').Count){
            if(!(Test-Path -LiteralPath $Python -PathType Leaf)){throw 'Create an isolated Python environment first, or pass -Python with a verified interpreter'}
            $Research=Get-Content -LiteralPath (Join-Path $ProductRoot 'data\research-release.json') -Raw|ConvertFrom-Json
            if($Research.version -ne $Pins.research_data_version -or $Research.sha256 -notmatch '^[0-9a-f]{64}$' -or $Research.bytes -le 0){throw 'Invalid pinned research release'}
            if($ResearchArchive){$Archive=[IO.Path]::GetFullPath($ResearchArchive);if((Get-Item -LiteralPath $Archive).Length -ne $Research.bytes -or (Hash $Archive) -ne $Research.sha256){throw 'Selected research archive does not match the committed pin'}}
            else{$Archive=Join-Path $DownloadRoot $Research.archive;$Proof=Download-Pinned $Research.url $Archive $Research.bytes $Research.sha256}
            & $Python (Join-Path $ProductRoot 'engines\fetch_research_assets.py') --release-zip $Archive --sha256 $Research.sha256
            if($LASTEXITCODE -ne 0){throw 'Research restoration failed; existing data was preserved'}
            $Restored.Add([ordered]@{path='data/xref_*.sqlite';archive_sha256=$Research.sha256;existing_identical_files_reused=$true})
        }
    }
}
$After=Check-Inputs
$SpeechManifest=Get-Content -LiteralPath (Join-Path $ProductRoot 'runtime\espeak-ng-runtime.json') -Raw|ConvertFrom-Json
$SpeechRoot=Join-Path $ProductRoot 'runtime\espeak-ng'
$SpeechMetadataGood=$SpeechManifest.component -eq 'eSpeak NG' -and $SpeechManifest.runtime_version -eq '1.52.0' -and $SpeechManifest.source_msi_sha256 -eq '7f673c709ea5dd579d3b5ebb98688cc575328a6ab7438d2bc405b88cedaeafb9'
$SpeechTree=if(Test-Path -LiteralPath $SpeechRoot -PathType Container){@(Get-ChildItem -LiteralPath $SpeechRoot -Recurse -Force)}else{@()}
$SpeechTreeGood=@($SpeechTree|Where-Object {!$_.PSIsContainer}).Count -eq 444 -and @($SpeechTree|Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count -eq 0
$SpeechChecks=@(foreach($File in $SpeechManifest.files){
    $Relative=[string]$File.path
    if(!$Relative -or $Relative.Contains('\') -or $Relative.Contains(':') -or $Relative.StartsWith('/') -or @($Relative.Split('/')|Where-Object {$_ -in @('','.','..')}).Count){throw 'Unsafe committed eSpeak path'}
    $Path=Join-Path $SpeechRoot $Relative;$Exists=Test-Path -LiteralPath $Path -PathType Leaf
    [ordered]@{path=$Relative;matches=($Exists -and (Get-Item -LiteralPath $Path).Length -eq $File.bytes -and (Hash $Path) -eq $File.sha256)}
})
$AllMatch=(@($After|Where-Object {!$_.matches}).Count -eq 0) -and $SpeechMetadataGood -and $SpeechTreeGood -and $SpeechChecks.Count -eq 444 -and @($SpeechChecks|Where-Object {!$_.matches}).Count -eq 0
[ordered]@{status=if($AllMatch){'PASS'}else{'MISSING_INPUTS'};mode=$Mode;application_version=$Version;inputs=$After;restored=@($Restored);espeak_files_checked=$SpeechChecks.Count;espeak_tree_exact=$SpeechTreeGood;espeak_all_match=($SpeechMetadataGood -and @($SpeechChecks|Where-Object {!$_.matches}).Count -eq 0);note='Reader/Romanian data and eSpeak runtime are committed source files. Restore them through the source checkout if absent; only ignored Node/research inputs are downloaded.'}|ConvertTo-Json -Depth 10
if(!$AllMatch){exit 1}
