[CmdletBinding()]
param([string]$Output)
$ErrorActionPreference='Stop'
$ProductRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$Source=Join-Path $ProductRoot 'tools\build_windows.ps1'
$Tokens=$null;$Errors=$null
$Ast=[Management.Automation.Language.Parser]::ParseFile($Source,[ref]$Tokens,[ref]$Errors)
if($Errors.Count){throw ($Errors.Message -join '; ')}
foreach($Name in @('Hash','Get-VerifiedEspeakRuntime')){
    $Function=$Ast.Find({param($Node)$Node -is [Management.Automation.Language.FunctionDefinitionAst] -and $Node.Name -eq $Name},$true)
    if(!$Function){throw "Missing pure build guard: $Name"}
    # Only these function definitions run; no app build, installer or download.
    Invoke-Expression $Function.Extent.Text
}
$EvidenceRoot=Join-Path $ProductRoot 'reports\MISSION-FBR-003\evidence'
$Fixture=Join-Path $EvidenceRoot ('build-guard-fixture-'+[Guid]::NewGuid().ToString('N'))
$Runtime=Join-Path $Fixture 'runtime\espeak-ng'
New-Item -ItemType Directory -Path $Runtime|Out-Null
$Payload=[byte[]](65,66,67)
$Names=@('espeak-ng.exe','libespeak-ng.dll','COPYING')+@(0..440|ForEach-Object {'fixture-'+$_+'.bin'})
$Files=@(foreach($Name in $Names){$Path=Join-Path $Runtime $Name;[IO.File]::WriteAllBytes($Path,$Payload);[ordered]@{path=$Name;bytes=3;sha256=Hash $Path}})
$Original=[ordered]@{component='eSpeak NG';runtime_version='1.52.0';source_msi_sha256='7f673c709ea5dd579d3b5ebb98688cc575328a6ab7438d2bc405b88cedaeafb9';files=$Files}|ConvertTo-Json -Depth 8
$Manifest=Join-Path $Fixture 'runtime\espeak-ng-runtime.json'
function Reset-Manifest {$Original|Set-Content -LiteralPath $Manifest -Encoding utf8}
Reset-Manifest
$Checks=[Collections.Generic.List[object]]::new()
function Check([string]$Name,[scriptblock]$Run,[bool]$Expected){
    $Accepted=$false;$Message=$null
    try{& $Run|Out-Null;$Accepted=$true}catch{$Message=$_.Exception.Message}
    $Checks.Add([ordered]@{name=$Name;passed=($Accepted -eq $Expected);accepted=$Accepted;expected_acceptance=$Expected;message=$Message})
}
try{
    Check 'Actual committed runtime: all444 file sizes and hashes match' {Get-VerifiedEspeakRuntime $ProductRoot} $true
    Check 'Valid isolated444-file fixture is accepted' {Get-VerifiedEspeakRuntime $Fixture} $true
    $One=Join-Path $Runtime 'fixture-440.bin'
    Remove-Item -LiteralPath $One
    Check 'Missing payload file is rejected' {Get-VerifiedEspeakRuntime $Fixture} $false
    [IO.File]::WriteAllBytes($One,$Payload)
    [IO.File]::WriteAllBytes($One,[byte[]](68,69,70))
    Check 'Same-size changed bytes are rejected by SHA' {Get-VerifiedEspeakRuntime $Fixture} $false
    [IO.File]::WriteAllBytes($One,$Payload)
    $Extra=Join-Path $Runtime 'unexpected-private-file.txt';[IO.File]::WriteAllBytes($Extra,$Payload)
    Check 'Unexpected extra file is rejected before bundling' {Get-VerifiedEspeakRuntime $Fixture} $false
    Remove-Item -LiteralPath $Extra
    $Changed=$Original|ConvertFrom-Json;$Changed.files[443].path='../escape.bin';$Changed|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $Manifest -Encoding utf8
    Check 'Parent traversal in manifest is rejected' {Get-VerifiedEspeakRuntime $Fixture} $false
    Reset-Manifest
    $Changed=$Original|ConvertFrom-Json;$Changed.files[443].path='COPYING';$Changed|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $Manifest -Encoding utf8
    Check 'Duplicate payload manifest path is rejected' {Get-VerifiedEspeakRuntime $Fixture} $false
    Reset-Manifest
    $Changed=$Original|ConvertFrom-Json;$Changed.runtime_version='0.0.0';$Changed|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $Manifest -Encoding utf8
    Check 'Unexpected source runtime version is rejected' {Get-VerifiedEspeakRuntime $Fixture} $false
    $Result=[ordered]@{status=if(@($Checks|Where-Object passed -eq $false).Count){'FAIL'}else{'PASS'};checked_utc=[DateTime]::UtcNow.ToString('o');source_sha256=Hash $Source;scope='Read-only actual444-file runtime verification and private tiny444-file guard fixtures only; no build, installer, network or provider execution';passed=@($Checks|Where-Object passed -eq $true).Count;failed=@($Checks|Where-Object passed -eq $false).Count;checks=@($Checks)}
    if($Output){if(Test-Path -LiteralPath $Output){throw 'Output is create-only'};$Result|ConvertTo-Json -Depth 10|Set-Content -LiteralPath $Output -Encoding utf8}
    $Result|ConvertTo-Json -Depth 10
    if($Result.status -ne 'PASS'){exit 1}
}finally{
    $Resolved=[IO.Path]::GetFullPath($Fixture)
    $Prefix=[IO.Path]::GetFullPath($EvidenceRoot)+[IO.Path]::DirectorySeparatorChar
    if(!$Resolved.StartsWith($Prefix,[StringComparison]::OrdinalIgnoreCase) -or (Split-Path $Resolved -Leaf) -notlike 'build-guard-fixture-*'){throw 'Fixture cleanup target failed its project evidence boundary'}
    Remove-Item -LiteralPath $Resolved -Recurse
}
