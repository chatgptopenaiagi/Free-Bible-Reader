param()
$ErrorActionPreference = 'Stop'
$Project = Split-Path -Parent $PSScriptRoot
$Docker = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
$Receipt = Join-Path $Project 'reports\MISSION-FBR-004\evidence\python'
$Wheel = Join-Path $Project 'dist\free_bible_reader-0.3.0-py3-none-any.whl'
if (-not (Test-Path -LiteralPath $Wheel -PathType Leaf)) { throw 'Build the public wheel first.' }
$Container = 'fbr004-python-' + [guid]::NewGuid().ToString('N').Substring(0,12)
$Created = $false
try {
    $ContainerId = & $Docker create --name $Container --cpus 2 --memory 3g --mount "type=bind,source=$PSScriptRoot,target=/verification,readonly" --mount "type=bind,source=$Receipt,target=/evidence" python:3.14-slim python /verification/verify_python_linux.py
    if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated Linux verification container.' }
    $Created = $true
    & $Docker cp $Wheel "${Container}:/tmp/free_bible_reader-0.3.0-py3-none-any.whl"
    if ($LASTEXITCODE -ne 0) { throw 'Could not copy public wheel into the container.' }
    & $Docker start -a $Container
    if ($LASTEXITCODE -ne 0) { throw 'Linux acceptance failed; retain its evidence log.' }
    $State = & $Docker inspect $Container --format '{{json .State}}' | ConvertFrom-Json
    if ($State.ExitCode -ne 0) { throw "Linux acceptance exited with $($State.ExitCode)." }
    & $Docker image inspect python:3.14-slim --format '{{.Id}}' | Set-Content -LiteralPath (Join-Path $Receipt 'linux-container-image.txt')
} finally {
    if ($Created) { & $Docker rm $Container | Out-Null }
}
