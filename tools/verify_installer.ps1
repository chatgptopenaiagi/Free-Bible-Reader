[CmdletBinding()]
param([string]$Installer,[switch]$UpdateOwnedInstall)
$ErrorActionPreference='Stop'
$ProductRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
if(!$Installer){$Installer=Join-Path $ProductRoot 'dist\Free-Bible-Reader-0.1.0-windows-x64-setup.exe'}
$Evidence=Join-Path $ProductRoot 'evidence'
$TestDirectory=[IO.Path]::GetFullPath((Join-Path $ProductRoot ('.install-test-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmss'))))
if(!$TestDirectory.StartsWith($ProductRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Test install path escaped the product workspace'}
if(Test-Path -LiteralPath $TestDirectory){throw 'Create-only installer test refuses an existing destination'}
$Log=Join-Path $Evidence 'installer-test-install.log'
$InstallProcess=Start-Process -FilePath $Installer -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/DIR="'+$TestDirectory+'"'),('/LOG="'+$Log+'"') -WindowStyle Hidden -Wait -PassThru
if($InstallProcess.ExitCode -ne 0){throw "Installer failed: $($InstallProcess.ExitCode)"}
$Exe=Join-Path $TestDirectory 'FreeBibleReader.exe'
$ResultPath=Join-Path $Evidence 'isolated-installed-self-test.json'
$TestProcess=Start-Process -FilePath $Exe -ArgumentList '--self-test','--self-test-output',('"'+$ResultPath+'"') -WindowStyle Hidden -Wait -PassThru
$Checks=Get-Content -LiteralPath $ResultPath -Raw | ConvertFrom-Json
if($TestProcess.ExitCode -ne 0 -or $Checks.status -ne 'PASS'){throw 'Installed reading/engine self-test failed'}
$RelativeFiles=@('FreeBibleReader.exe','_internal\data\reader.sqlite','_internal\data\xref_visual.sqlite','_internal\data\xref_aggregate.sqlite','_internal\data\xref_phrase.sqlite','_internal\data\xref_reference.sqlite','_internal\runtime\node.exe','_internal\ui-core\i18n\en.json','_internal\ui-core\i18n\ro.json','_internal\ui-core\i18n\de.json')
$Files=@(foreach($Relative in $RelativeFiles){$Installed=Join-Path $TestDirectory $Relative;$Built=Join-Path $ProductRoot ('dist\FreeBibleReader\'+$Relative);$Observed=(Get-FileHash -LiteralPath $Installed).Hash;$Expected=(Get-FileHash -LiteralPath $Built).Hash;[pscustomobject]@{relative_path=$Relative;bytes=(Get-Item -LiteralPath $Installed).Length;sha256=$Observed;matches_build=($Observed -eq $Expected)}})
if(@($Files | Where-Object matches_build -ne $true).Count){throw 'Installed files differ from tested build'}
$Uninstaller=Join-Path $TestDirectory 'unins000.exe'
# The target was created by this test, and its resolved absolute path was checked above.
$UninstallProcess=Start-Process -FilePath $Uninstaller -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="'+(Join-Path $Evidence 'installer-test-uninstall.log')+'"') -WindowStyle Hidden -Wait -PassThru
if($UninstallProcess.ExitCode -ne 0 -or (Test-Path -LiteralPath $Exe)){throw 'Scoped uninstall verification failed'}
$OwnerDirectory=Join-Path $env:LOCALAPPDATA 'Programs\Free Bible Reader'
if(Test-Path -LiteralPath $OwnerDirectory){
    $PriorReceipt=Join-Path $Evidence 'installer-verification.initial-packaging.json'
    if(!$UpdateOwnedInstall -or !(Test-Path -LiteralPath $PriorReceipt)){throw 'Owner install destination already exists; inspect it before replacement'}
    $Prior=Get-Content -LiteralPath $PriorReceipt -Raw | ConvertFrom-Json
    $OwnerExe=Join-Path $OwnerDirectory 'FreeBibleReader.exe'
    if($Prior.owner_directory -ne $OwnerDirectory -or $Prior.owner_install_exit -ne 0 -or !(Test-Path -LiteralPath $OwnerExe)){throw 'Existing installation is not the recorded release test installation'}
    $ExpectedExe=($Prior.installed_file_checks | Where-Object relative_path -eq 'FreeBibleReader.exe').sha256
    if((Get-FileHash -LiteralPath $OwnerExe).Hash -ne $ExpectedExe){throw 'Existing installation differs from the recorded test; preserve it for inspection'}
}
$OwnerInstall=Start-Process -FilePath $Installer -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG="'+(Join-Path $Evidence 'owner-install.log')+'"') -WindowStyle Hidden -Wait -PassThru
if($OwnerInstall.ExitCode -ne 0){throw 'Owner installation failed'}
[pscustomobject]@{status='PASS';installer_sha256=(Get-FileHash -LiteralPath $Installer).Hash;installer_bytes=(Get-Item -LiteralPath $Installer).Length;isolated_directory=$TestDirectory;isolated_install_exit=$InstallProcess.ExitCode;installed_self_test=$Checks;installed_file_checks=$Files;uninstall_exit=$UninstallProcess.ExitCode;test_executable_removed=!(Test-Path -LiteralPath $Exe);owner_install_exit=$OwnerInstall.ExitCode;owner_directory=$OwnerDirectory;restart_required=$false} | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $Evidence 'installer-verification.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $Evidence 'installer-verification.json') -Raw
