[CmdletBinding()]
param([string]$Output)
$ErrorActionPreference='Stop'
$ProductRoot=Split-Path $PSScriptRoot -Parent
$Source=Join-Path $ProductRoot 'tools\verify_installer.ps1'
$Tokens=$null;$Errors=$null
$Ast=[Management.Automation.Language.Parser]::ParseFile($Source,[ref]$Tokens,[ref]$Errors)
if($Errors.Count){throw ($Errors.Message -join '; ')}
$Function=$Ast.Find({param($Node)$Node -is [Management.Automation.Language.FunctionDefinitionAst] -and $Node.Name -eq 'Assert-ReceiptOwner'},$true)
if(!$Function){throw 'Expected pure owner-receipt guard function'}
# Only this pure function is evaluated. No verifier phase or installer is invoked.
Invoke-Expression $Function.Extent.Text
$OwnerDirectory='C:\FBR-guard-fixture\Free Bible Reader'
$ProductionAppId='{86957E89-5028-4A68-ACDA-98ECD7AD2D6F}'
$Sha='a'*64
function Fixture {
    $Registration=[ordered]@{exists=$true;DisplayName='FREE BIBLE READER';DisplayVersion='0.1.1';InstallLocation=$OwnerDirectory+'\';UninstallString='"'+$OwnerDirectory+'\unins000.exe"'}
    $Owner=[ordered]@{directory=$OwnerDirectory;files=@([ordered]@{relative_path='FreeBibleReader.exe';exists=$true;sha256=$Sha});uninstall_registration=$Registration}
    $Prior=[ordered]@{status='PASS';phase='UpdateOwner';owner_upgrade_performed=$true;version='0.1.1';owner_directory=$OwnerDirectory;owner_after=$Owner;bundle_checks=@([ordered]@{relative_path='FreeBibleReader.exe';matches_build=$true;sha256=$Sha});installer_manifest=[ordered]@{kind='production';app_id=$ProductionAppId;version='0.1.1';app_executable_sha256=$Sha}}
    [pscustomobject]@{prior=($Prior|ConvertTo-Json -Depth 12|ConvertFrom-Json);before=($Owner|ConvertTo-Json -Depth 12|ConvertFrom-Json);expected=$Sha}
}
$Checks=[Collections.Generic.List[object]]::new()
function Check([string]$Name,[scriptblock]$Change,[bool]$ShouldPass=$false){
    $State=Fixture
    if($Change){& $Change $State}
    $Accepted=$false;$Message=$null
    try{$Proof=Assert-ReceiptOwner $State.prior $State.before $State.expected;$Accepted=$true}catch{$Message=$_.Exception.Message}
    $Checks.Add([ordered]@{name=$Name;passed=($Accepted -eq $ShouldPass);accepted=$Accepted;expected_acceptance=$ShouldPass;rejection=$Message})
}
Check 'Path, production identity, receipt and current hash agree' {} $true
Check 'Unquoted exact registered uninstaller is accepted' {param($S)$S.before.uninstall_registration.UninstallString=$OwnerDirectory+'\unins000.exe'} $true
Check 'Absent prior receipt is rejected' {param($S)$S.prior=$null}
Check 'Failed prior update is rejected' {param($S)$S.prior.status='FAIL'}
Check 'A test installation receipt is rejected' {param($S)$S.prior.phase='InstallTest'}
Check 'An unperformed owner update is rejected' {param($S)$S.prior.owner_upgrade_performed=$false}
Check 'Different prior version is rejected by this explicit path' {param($S)$S.prior.version='0.1.0'}
Check 'Different receipt owner directory is rejected' {param($S)$S.prior.owner_directory='C:\Unrelated'}
Check 'Different prior owner snapshot directory is rejected' {param($S)$S.prior.owner_after.directory='C:\Unrelated'}
Check 'Test setup identity is rejected' {param($S)$S.prior.installer_manifest.kind='test'}
Check 'Wrong production AppId is rejected' {param($S)$S.prior.installer_manifest.app_id='{WRONG}'}
Check 'Installer version disagreement is rejected' {param($S)$S.prior.installer_manifest.version='0.1.0'}
Check 'Missing or malformed explicitly expected hash is rejected' {param($S)$S.expected='current'}
Check 'Installer EXE hash disagreement is rejected' {param($S)$S.prior.installer_manifest.app_executable_sha256='b'*64}
Check 'Prior owner EXE hash disagreement is rejected' {param($S)$S.prior.owner_after.files[0].sha256='b'*64}
Check 'Prior bundle did not match is rejected' {param($S)$S.prior.bundle_checks[0].matches_build=$false}
Check 'Duplicate prior bundle EXE entries are rejected' {param($S)$S.prior.bundle_checks=@($S.prior.bundle_checks[0],$S.prior.bundle_checks[0])}
Check 'Current EXE hash disagreement is rejected' {param($S)$S.before.files[0].sha256='b'*64}
Check 'Current missing EXE is rejected' {param($S)$S.before.files[0].exists=$false}
Check 'Current registration is absent' {param($S)$S.before.uninstall_registration.exists=$false}
Check 'Current registration version disagreement is rejected' {param($S)$S.before.uninstall_registration.DisplayVersion='0.1.0'}
Check 'Prior registration version disagreement is rejected' {param($S)$S.prior.owner_after.uninstall_registration.DisplayVersion='0.1.0'}
Check 'Current registered install location escaped owner is rejected' {param($S)$S.before.uninstall_registration.InstallLocation='C:\Unrelated'}
Check 'Current registered uninstall command escaped owner is rejected' {param($S)$S.before.uninstall_registration.UninstallString='C:\Unrelated\unins000.exe'}
Check 'Registered uninstall command with extra switches is rejected' {param($S)$S.before.uninstall_registration.UninstallString+=' /SILENT'}
$Result=[ordered]@{status=if(@($Checks|Where-Object passed -eq $false).Count){'FAIL'}else{'PASS'};checked_utc=[DateTime]::UtcNow.ToString('o');scope='Pure AST-extracted guard fixtures only; no installer, registry or application phase executed';source_sha256=(Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash.ToLowerInvariant();passed=@($Checks|Where-Object passed -eq $true).Count;failed=@($Checks|Where-Object passed -eq $false).Count;checks=@($Checks)}
if($Output){if(Test-Path -LiteralPath $Output){throw 'Guard result output is create-only'};$Result|ConvertTo-Json -Depth 10|Set-Content -LiteralPath $Output -Encoding utf8}
$Result|ConvertTo-Json -Depth 10
if($Result.status -ne 'PASS'){exit 1}
