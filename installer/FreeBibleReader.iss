#define MyAppVersion "0.1.0"
[Setup]
AppId={{86957E89-5028-4A68-ACDA-98ECD7AD2D6F}
AppName=FREE BIBLE READER
AppVersion={#MyAppVersion}
AppPublisher=FREE BIBLE READER contributors
AppPublisherURL=https://github.com/chatgptopenaiagi/Free-Bible-Reader
AppSupportURL=https://github.com/chatgptopenaiagi/Free-Bible-Reader/issues
AppUpdatesURL=https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases
DefaultDirName={localappdata}\Programs\Free Bible Reader
DefaultGroupName=FREE BIBLE READER
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir=..\dist
OutputBaseFilename=Free-Bible-Reader-{#MyAppVersion}-windows-x64-setup
SetupIconFile=..\assets\brand.ico
UninstallDisplayIcon={app}\FreeBibleReader.exe
UninstallDisplayName=FREE BIBLE READER
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
CloseApplications=yes
CloseApplicationsFilter=FreeBibleReader.exe
RestartApplications=no
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\FreeBibleReader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\FREE BIBLE READER"; Filename: "{app}\FreeBibleReader.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\FREE BIBLE READER"; Filename: "{app}\FreeBibleReader.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\FreeBibleReader.exe"; Description: "{cm:LaunchProgram,FREE BIBLE READER}"; Flags: nowait postinstall skipifsilent
