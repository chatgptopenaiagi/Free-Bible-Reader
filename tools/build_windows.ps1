[CmdletBinding()]
param([string]$BuildPython,[string]$InnoCompiler)
$ErrorActionPreference='Stop'
$ProductRoot=Split-Path $PSScriptRoot -Parent
if(!$BuildPython){$BuildPython=Join-Path $ProductRoot '.build-venv\Scripts\python.exe'}
if(!$InnoCompiler){$InnoCompiler=Join-Path $ProductRoot '.build-tools\InnoSetup\ISCC.exe'}
if(!(Test-Path -LiteralPath $BuildPython)){throw 'Create an isolated Python build environment and install requirements-build.txt; pass -BuildPython.'}
if(!(Test-Path -LiteralPath $InnoCompiler)){throw 'Install signed official Inno Setup, then pass -InnoCompiler.'}
Push-Location $ProductRoot
try{
    foreach($Needed in @('runtime\node.exe','data\reader.sqlite','data\xref_visual.sqlite','data\xref_aggregate.sqlite','data\xref_phrase.sqlite','data\xref_reference.sqlite','workbench\index.html','ui-core\index.js')){if(!(Test-Path -LiteralPath $Needed)){throw "Missing build input: $Needed"}}
    & $BuildPython -m PyInstaller --noconfirm --noupx --windowed --onedir --name FreeBibleReader --icon assets/brand.ico --distpath dist --workpath build --specpath . --add-data 'workbench;workbench' --add-data 'ui-core;ui-core' --add-data 'data;data' --add-data 'parser;parser' --add-data 'runtime;runtime' --add-data 'licenses;licenses' --add-data 'engines/visual/component.js;engines/visual' --add-data 'engines/visual/component.css;engines/visual' --hidden-import engines.visual.engine --hidden-import engines.visual.layout --hidden-import engines.aggregate.engine --hidden-import engines.phrase.engine app.py
    if($LASTEXITCODE -ne 0){throw 'Executable build failed'}
    & $InnoCompiler 'installer\FreeBibleReader.iss'
    if($LASTEXITCODE -ne 0){throw 'Installer build failed'}
    Get-FileHash -LiteralPath 'dist\Free-Bible-Reader-0.1.0-windows-x64-setup.exe' -Algorithm SHA256
}finally{Pop-Location}
