#define MyAppName "Aes Studio"
#define MyAppVersion "2.1.0"
#define MyAppExeName "AesStudio.exe"
[Setup]
AppId={{A5168A77-49BB-4CC8-9D78-AE5200000002}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Aes Studio
DefaultGroupName=Aes Studio
OutputBaseFilename=AesStudio-2.1-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
[Files]
Source: "..\dist\AesStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{autoprograms}\Aes Studio"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Aes Studio"; Filename: "{app}\{#MyAppExeName}"
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Aes Studio"; Flags: nowait postinstall skipifsilent
