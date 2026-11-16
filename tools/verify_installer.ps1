[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('InstallTest','VerifyTest','UninstallTest','UpdateOwner')][string]$Phase,
    [string]$Installer,
    [string]$RunId,
    [switch]$ConfirmGuiFinished,
    [switch]$UpdateOwnedInstall,
    [string]$ExpectedOwnerExeSha256,
    [string]$ExpectedOwnerReceipt,
    [string]$ApprovedTestReceipt,
    [ValidateRange(30,1800)][int]$TimeoutSeconds=300
)
$ErrorActionPreference='Stop'
if($ExpectedOwnerReceipt -and $Phase -ne 'UpdateOwner'){throw '-ExpectedOwnerReceipt is valid only for the explicit UpdateOwner phase'}
$ProductRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$Version=(Get-Content -LiteralPath (Join-Path $ProductRoot 'package.json') -Raw | ConvertFrom-Json).version
$ProductionAppId='{86957E89-5028-4A68-ACDA-98ECD7AD2D6F}'
$TestAppId='{8D2365AC-9142-4BA8-A6A3-C0B07D2689E4}'
$OwnerDirectory=[IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs\Free Bible Reader'))
$VerificationRoot=[IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'FBRVerification'))
if(!$RunId){if($Phase -notin @('InstallTest','UpdateOwner')){throw 'Use the RunId returned by InstallTest'};$RunId='verify-'+$Version.Replace('.','-')+'-'+[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,6)}
if($RunId -notmatch '^[a-zA-Z0-9_-]{1,100}$'){throw 'Invalid run ID'}
$Evidence=Join-Path $ProductRoot ('reports\MISSION-FBR-003\evidence\'+$RunId)
New-Item -ItemType Directory -Path $Evidence -Force | Out-Null
$TestDirectory=[IO.Path]::GetFullPath((Join-Path $VerificationRoot $RunId))
if(!$TestDirectory.StartsWith($VerificationRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or $TestDirectory -eq $OwnerDirectory){throw 'Test destination escaped the dedicated verification directory'}
$PhaseNumber=@{InstallTest='01';VerifyTest='02';UninstallTest='03';UpdateOwner='04'}[$Phase]
$SuccessPath=Join-Path $Evidence ($PhaseNumber+'-'+$Phase+'.json')
if(Test-Path -LiteralPath $SuccessPath){throw 'This phase already completed successfully; historical receipt is create-only'}
$Attempt=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,6)
function Hash([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Write-NewJson([string]$Path,$Value){if(Test-Path -LiteralPath $Path){throw "Evidence already exists: $Path"};$Value | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $Path -Encoding utf8}
function Read-Json([string]$Path){Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json}
function Owner-Snapshot {
    $Files=@(foreach($Relative in @('FreeBibleReader.exe','_internal\data\reader.sqlite','_internal\data\xref_visual.sqlite','_internal\data\xref_aggregate.sqlite','_internal\data\xref_phrase.sqlite','_internal\data\xref_reference.sqlite')){$Path=Join-Path $OwnerDirectory $Relative;[ordered]@{relative_path=$Relative;exists=(Test-Path -LiteralPath $Path);sha256=if(Test-Path -LiteralPath $Path){Hash $Path}else{$null}}})
    $Key='HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\'+$ProductionAppId+'_is1'
    $Values=Get-ItemProperty -LiteralPath $Key -ErrorAction SilentlyContinue
    $Registration=[ordered]@{exists=($null -ne $Values);DisplayName=$Values.DisplayName;DisplayVersion=$Values.DisplayVersion;InstallLocation=$Values.InstallLocation;UninstallString=$Values.UninstallString}
    $Links=@(foreach($Path in @((Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\FREE BIBLE READER.lnk'),(Join-Path ([Environment]::GetFolderPath('Desktop')) 'FREE BIBLE READER.lnk'))){[ordered]@{path=$Path;exists=(Test-Path -LiteralPath $Path);sha256=if(Test-Path -LiteralPath $Path){Hash $Path}else{$null}}})
    [ordered]@{directory=$OwnerDirectory;files=$Files;uninstall_registration=$Registration;shortcuts=$Links}
}
function Assert-OwnerSame($Before,$After){if(($Before | ConvertTo-Json -Depth 15 -Compress) -ne ($After | ConvertTo-Json -Depth 15 -Compress)){throw 'Existing owner application, uninstall identity or shortcut snapshot changed during test phase'}}
function Assert-ReceiptOwner($Prior,$Before,[string]$ExpectedSha){
    # A current EXE alone is not evidence for a previously verified installation.
    if($ExpectedSha -notmatch '^[a-fA-F0-9]{64}$' -or $Prior.status -ne 'PASS' -or $Prior.phase -ne 'UpdateOwner' -or !$Prior.owner_upgrade_performed -or $Prior.version -notin @('0.1.1','0.2.0') -or $Prior.owner_directory -ne $OwnerDirectory -or $Prior.owner_after.directory -ne $OwnerDirectory){throw 'Expected owner receipt is not a successful, path-bound prior supported production upgrade'}
    $Metadata=$Prior.installer_manifest
    if($Metadata.kind -ne 'production' -or $Metadata.app_id -ne $ProductionAppId -or $Metadata.version -ne $Prior.version -or $Metadata.app_executable_sha256 -ne $ExpectedSha){throw 'Prior owner installer identity/version/executable hash mismatch'}
    $PriorFiles=@($Prior.owner_after.files | Where-Object relative_path -eq 'FreeBibleReader.exe');$ProvenFiles=@($Prior.bundle_checks | Where-Object relative_path -eq 'FreeBibleReader.exe');$CurrentFiles=@($Before.files | Where-Object relative_path -eq 'FreeBibleReader.exe')
    if($PriorFiles.Count -ne 1 -or !$PriorFiles[0].exists -or $PriorFiles[0].sha256 -ne $ExpectedSha -or $ProvenFiles.Count -ne 1 -or !$ProvenFiles[0].matches_build -or $ProvenFiles[0].sha256 -ne $ExpectedSha -or $CurrentFiles.Count -ne 1 -or !$CurrentFiles[0].exists -or $CurrentFiles[0].sha256 -ne $ExpectedSha){throw 'Prior receipt and current owner executable do not match the explicitly expected hash'}
    $ExpectedUninstaller=Join-Path $OwnerDirectory 'unins000.exe'
    foreach($Registration in @($Prior.owner_after.uninstall_registration,$Before.uninstall_registration)){
        if(!$Registration.exists -or $Registration.DisplayName -ne 'FREE BIBLE READER' -or $Registration.DisplayVersion -ne $Prior.version -or !$Registration.InstallLocation -or [IO.Path]::GetFullPath($Registration.InstallLocation).TrimEnd('\','/') -ne $OwnerDirectory.TrimEnd('\','/') -or $Registration.UninstallString -notin @($ExpectedUninstaller,('"'+$ExpectedUninstaller+'"'))){throw 'Prior or current production uninstall registration/version/path mismatch'}
    }
    [ordered]@{mode='SUCCESSFUL_PRIOR_UPDATE_RECEIPT';previous_version=$Prior.version;expected_executable_sha256=$ExpectedSha.ToLowerInvariant();owner_directory=$OwnerDirectory;production_app_id=$ProductionAppId}
}
function Assert-NoRunningApp([string]$Directory){$Prefix=$Directory+[IO.Path]::DirectorySeparatorChar;$Running=@(Get-CimInstance Win32_Process -Filter "Name='FreeBibleReader.exe'" | Where-Object {$_.ExecutablePath -and $_.ExecutablePath.StartsWith($Prefix,[StringComparison]::OrdinalIgnoreCase)});if($Running.Count){throw 'Close the specific application through its normal GUI before this explicit uninstall/update phase'}}
function Run-Child([string]$File,[string[]]$Arguments,[string]$WorkingDirectory,[switch]$CleanEnvironment){
    $Info=[Diagnostics.ProcessStartInfo]::new();$Info.FileName=$File;$Info.WorkingDirectory=$WorkingDirectory;$Info.UseShellExecute=$false;$Info.CreateNoWindow=$true;$Info.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
    foreach($Argument in $Arguments){$Info.ArgumentList.Add($Argument)}
    if($CleanEnvironment){$Profile=Join-Path $TestDirectory 'verification-profile';New-Item -ItemType Directory -Path $Profile -Force | Out-Null;$Info.Environment['LOCALAPPDATA']=$Profile;$Info.Environment['APPDATA']=(Join-Path $Profile 'Roaming');$Info.Environment['PATH']=(Join-Path $env:SystemRoot 'System32')+';'+$env:SystemRoot;$Info.Environment['PYTHONPATH']='';$Info.Environment['PYTHONHOME']='';$Info.Environment['NODE_PATH']='';$Info.Environment['TEMP']=$Profile;$Info.Environment['TMP']=$Profile}
    $Process=[Diagnostics.Process]::Start($Info)
    if(!$Process.WaitForExit($TimeoutSeconds*1000)){throw "Owned child PID $($Process.Id) exceeded timeout; no retry or automatic unrelated process termination was performed"}
    [ordered]@{pid=$Process.Id;exit_code=$Process.ExitCode;restart_required=($Process.ExitCode -eq 3010)}
}
function Read-Installer([string]$Path,[string]$Kind){
    $Metadata=Read-Json ($Path+'.manifest.json');$ExpectedId=if($Kind -eq 'test'){$TestAppId}else{$ProductionAppId}
    if($Metadata.kind -ne $Kind -or $Metadata.version -ne $Version -or $Metadata.app_id -ne $ExpectedId -or $Metadata.sha256 -ne (Hash $Path)){throw 'Installer identity/version/hash manifest mismatch'}
    if((Hash $Metadata.app_build_manifest) -ne $Metadata.app_build_manifest_sha256){throw 'App build manifest changed after installer creation'}
    return $Metadata
}
function Compare-Bundle([string]$Directory,$Manifest){
    $Checks=@(foreach($File in $Manifest.files){$Path=[IO.Path]::GetFullPath((Join-Path $Directory $File.relative_path));if(!$Path.StartsWith($Directory+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Build manifest path escaped installed directory'};$Actual=Hash $Path;[ordered]@{relative_path=$File.relative_path;bytes=(Get-Item -LiteralPath $Path).Length;sha256=$Actual;matches_build=($Actual -eq $File.sha256)}})
    if(@($Checks | Where-Object matches_build -ne $true).Count){throw 'Installed bundle differs from its immutable build manifest'}
    return $Checks
}
$Result=[ordered]@{phase=$Phase;version=$Version;run_id=$RunId;evidence_directory=$Evidence;test_directory=$TestDirectory;owner_directory=$OwnerDirectory;started_utc=[DateTime]::UtcNow.ToString('o');status='RUNNING';owner_upgrade_performed=$false;owner_uninstall_performed=$false;restart_required=$false;test_installer_is_production_installer=$false}
try{
    if($Phase -eq 'InstallTest'){
        if(!$Installer){$Installer=Join-Path $ProductRoot ('dist\'+$Version+'\Free-Bible-Reader-'+$Version+'-windows-x64-verification-setup.exe')}
        $Metadata=Read-Installer $Installer 'test'
        if(Test-Path -LiteralPath $TestDirectory){throw 'Create-only test refuses an existing destination'}
        $Before=Owner-Snapshot;$Log=Join-Path $Evidence ('install-'+$Attempt+'.log')
        $Process=Run-Child $Installer @('/SP-','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/RESTARTEXITCODE=3010','/NOCLOSEAPPLICATIONS','/NORESTARTAPPLICATIONS',('/DIR='+$TestDirectory),('/LOG='+$Log)) $ProductRoot
        $Result.restart_required=$Process.restart_required;if($Process.exit_code -ne 0){throw "Test installation exit code $($Process.exit_code)"}
        $After=Owner-Snapshot;Assert-OwnerSame $Before $After
        $Marker=[ordered]@{run_id=$RunId;version=$Version;app_id=$TestAppId;installer_sha256=$Metadata.sha256;app_build_manifest=$Metadata.app_build_manifest;created_utc=[DateTime]::UtcNow.ToString('o')}
        Write-NewJson (Join-Path $TestDirectory '.fbr-verification-marker.json') $Marker
        $Result.installer=$Installer;$Result.installer_manifest=$Metadata;$Result.install_process=$Process;$Result.owner_before=$Before;$Result.owner_after=$After;$Result.owner_preserved=$true;$Result.executable=(Join-Path $TestDirectory 'FreeBibleReader.exe');$Result.gui_profile=(Join-Path $TestDirectory 'verification-profile');$Result.next_phase='VerifyTest; launch actual GUI separately, then UninstallTest -ConfirmGuiFinished only after GUI verification is complete.'
    }elseif($Phase -in @('VerifyTest','UninstallTest')){
        $InstallState=Read-Json (Join-Path $Evidence '01-InstallTest.json');$Marker=Read-Json (Join-Path $TestDirectory '.fbr-verification-marker.json')
        if($InstallState.status -ne 'PASS' -or $InstallState.test_directory -ne $TestDirectory -or $Marker.run_id -ne $RunId -or $Marker.app_id -ne $TestAppId){throw 'Dedicated test installation identity does not match its successful receipt/marker'}
        $Before=Owner-Snapshot;Assert-OwnerSame $InstallState.owner_before $Before
        if($Phase -eq 'VerifyTest'){
            if((Hash $Marker.app_build_manifest) -ne $InstallState.installer_manifest.app_build_manifest_sha256){throw 'Build manifest changed since test installation'}
            $Manifest=Read-Json $Marker.app_build_manifest;$Result.app_build_manifest=$Marker.app_build_manifest;$Result.app_build_manifest_sha256=Hash $Marker.app_build_manifest;$SelfOutput=Join-Path $TestDirectory ('self-test-'+$Attempt+'.json')
            $Process=Run-Child (Join-Path $TestDirectory 'FreeBibleReader.exe') @('--self-test','--self-test-output',$SelfOutput) $TestDirectory -CleanEnvironment
            $Self=Read-Json $SelfOutput
            if($Process.exit_code -ne 0 -or $Self.status -ne 'PASS' -or $Self.version -ne $Version){throw 'Installed standalone self-test failed or reports the wrong version'}
            $Result.self_test=$Self;$Result.self_test_process=$Process;$Result.bundle_checks=@(Compare-Bundle $TestDirectory $Manifest);$Result.executable=(Join-Path $TestDirectory 'FreeBibleReader.exe');$Result.gui_profile=(Join-Path $TestDirectory 'verification-profile');$Result.clean_child_PATH=((Join-Path $env:SystemRoot 'System32')+';'+$env:SystemRoot);$Result.self_test_working_directory_outside_source=$true;$Result.source_workspace_absent_from_child_PATH=$true
        }else{
            if(!$ConfirmGuiFinished){throw 'UninstallTest requires explicit -ConfirmGuiFinished; GUI ownership remains with the caller'}
            $Verified=Read-Json (Join-Path $Evidence '02-VerifyTest.json');if($Verified.status -ne 'PASS'){throw 'Successful VerifyTest receipt required'}
            Assert-NoRunningApp $TestDirectory
            $Process=Run-Child (Join-Path $TestDirectory 'unins000.exe') @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',('/LOG='+(Join-Path $Evidence ('uninstall-'+$Attempt+'.log')))) $TestDirectory
            if($Process.exit_code -ne 0 -or (Test-Path -LiteralPath (Join-Path $TestDirectory 'FreeBibleReader.exe'))){throw 'Scoped test uninstall failed'}
            $Result.uninstall_process=$Process;$Result.test_executable_removed=$true;$Result.caller_confirmed_gui_finished=$true;$Result.remaining_directory=(Test-Path -LiteralPath $TestDirectory)
        }
        $After=Owner-Snapshot;Assert-OwnerSame $Before $After;$Result.owner_before=$Before;$Result.owner_after=$After;$Result.owner_preserved=$true
    }else{
        if(!$UpdateOwnedInstall -or !$ExpectedOwnerExeSha256 -or !$ApprovedTestReceipt){throw 'UpdateOwner requires explicit -UpdateOwnedInstall, -ExpectedOwnerExeSha256 and successful -ApprovedTestReceipt'}
        $Approved=Read-Json $ApprovedTestReceipt;if($Approved.status -ne 'PASS' -or $Approved.phase -ne 'VerifyTest' -or $Approved.version -ne $Version){throw 'Approved test verification does not match this release'}
        if(!$Installer){$Installer=Join-Path $ProductRoot ('dist\'+$Version+'\Free-Bible-Reader-'+$Version+'-windows-x64-setup.exe')}
        $Metadata=Read-Installer $Installer 'production';$Manifest=Read-Json $Metadata.app_build_manifest
        $Before=Owner-Snapshot
        if($ExpectedOwnerReceipt){
            $Prior=Read-Json $ExpectedOwnerReceipt;$Proof=Assert-ReceiptOwner $Prior $Before $ExpectedOwnerExeSha256
            $Proof.receipt=[IO.Path]::GetFullPath($ExpectedOwnerReceipt);$Proof.receipt_sha256=Hash $ExpectedOwnerReceipt;$Result.previous_owner_proof=$Proof
        }else{
            $Prior=Read-Json (Join-Path $ProductRoot 'evidence\installer-verification.json');$HistoricalExe=($Prior.installed_file_checks | Where-Object relative_path -eq 'FreeBibleReader.exe').sha256
            if($Prior.owner_directory -ne $OwnerDirectory -or $Prior.installed_self_test.version -ne '0.1.0' -or $ExpectedOwnerExeSha256 -ne $HistoricalExe -or (Hash (Join-Path $OwnerDirectory 'FreeBibleReader.exe')) -ne $ExpectedOwnerExeSha256){throw 'Owner destination is not the explicitly expected preserved 0.1.0 installation'}
            $Result.previous_owner_proof=[ordered]@{mode='HISTORICAL_0.1.0_RECEIPT';previous_version='0.1.0';expected_executable_sha256=$ExpectedOwnerExeSha256;receipt=(Join-Path $ProductRoot 'evidence\installer-verification.json')}
        }
        if($Approved.app_build_manifest_sha256 -ne $Metadata.app_build_manifest_sha256 -or ($Approved.bundle_checks | Where-Object relative_path -eq 'FreeBibleReader.exe').sha256 -ne $Manifest.executable_sha256){throw 'Approved test executable differs from production bundle'}
        Assert-NoRunningApp $OwnerDirectory
        $Process=Run-Child $Installer @('/SP-','/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/RESTARTEXITCODE=3010','/NOCLOSEAPPLICATIONS','/NORESTARTAPPLICATIONS',('/LOG='+(Join-Path $Evidence ('owner-update-'+$Attempt+'.log')))) $ProductRoot
        $Result.restart_required=$Process.restart_required;if($Process.exit_code -ne 0){throw "Owner update exit code $($Process.exit_code)"}
        $Result.bundle_checks=@(Compare-Bundle $OwnerDirectory $Manifest);$Result.owner_before=$Before;$Result.owner_after=Owner-Snapshot;$Result.owner_upgrade_performed=$true;$Result.owner_update_process=$Process;$Result.installer_manifest=$Metadata
    }
    $Result.status='PASS';$Result.completed_utc=[DateTime]::UtcNow.ToString('o');Write-NewJson $SuccessPath $Result
}catch{$Result.status='FAIL';$Result.error=$_.Exception.Message;throw}
finally{$Result.completed_utc=[DateTime]::UtcNow.ToString('o');Write-NewJson (Join-Path $Evidence ($Phase+'-attempt-'+$Attempt+'.json')) $Result;$Result | ConvertTo-Json -Depth 6}
