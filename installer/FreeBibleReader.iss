#define MyAppVersion "0.2.0"
#ifndef FBR_BUILD_ROOT
  #define FBR_BUILD_ROOT "..\dist\0.2.0\FreeBibleReader"
#endif
#ifndef FBR_OUTPUT_DIR
  #define FBR_OUTPUT_DIR "..\dist\0.2.0"
#endif
[Setup]
#ifdef FBR_TEST_INSTALL
AppId={{8D2365AC-9142-4BA8-A6A3-C0B07D2689E4}
AppName=FREE BIBLE READER verification
DefaultDirName={localappdata}\FBRVerification\FreeBibleReader-{#MyAppVersion}
CreateUninstallRegKey=no
UsePreviousAppDir=no
UsePreviousGroup=no
UsePreviousTasks=no
UpdateUninstallLogAppName=no
CloseApplications=no
OutputBaseFilename=Free-Bible-Reader-{#MyAppVersion}-windows-x64-verification-setup
#else
AppId={{86957E89-5028-4A68-ACDA-98ECD7AD2D6F}
AppName=FREE BIBLE READER
DefaultDirName={localappdata}\Programs\Free Bible Reader
DefaultGroupName=FREE BIBLE READER
CloseApplications=yes
CloseApplicationsFilter=FreeBibleReader.exe
OutputBaseFilename=Free-Bible-Reader-{#MyAppVersion}-windows-x64-setup
#endif
AppVersion={#MyAppVersion}
AppPublisher=FREE BIBLE READER contributors
AppPublisherURL=https://github.com/chatgptopenaiagi/Free-Bible-Reader
AppSupportURL=https://github.com/chatgptopenaiagi/Free-Bible-Reader/issues
AppUpdatesURL=https://github.com/chatgptopenaiagi/Free-Bible-Reader/releases
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#FBR_OUTPUT_DIR}
SetupIconFile=..\assets\brand.ico
UninstallDisplayIcon={app}\FreeBibleReader.exe
UninstallDisplayName=FREE BIBLE READER
Uninstallable=yes
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
RestartApplications=no
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

#ifndef FBR_TEST_INSTALL
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
#endif

[Files]
Source: "{#FBR_BUILD_ROOT}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

#ifndef FBR_TEST_INSTALL
[Icons]
Name: "{autoprograms}\FREE BIBLE READER"; Filename: "{app}\FreeBibleReader.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\FREE BIBLE READER"; Filename: "{app}\FreeBibleReader.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\FreeBibleReader.exe"; Description: "{cm:LaunchProgram,FREE BIBLE READER}"; Flags: nowait postinstall skipifsilent
#endif
