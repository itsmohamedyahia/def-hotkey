; Inno Setup script for def Dictionary App

[Setup]
AppId={{82D1E4BA-A2F5-4081-9DFD-9EA63B5D3452}}
AppName=def
AppVersion=2.0.0
AppPublisher=itsmohamedyahia
DefaultDirName={localappdata}\Programs\def
DefaultGroupName=def
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\def.exe
Compression=lzma2
SolidCompression=yes
OutputDir=dist
OutputBaseFilename=def-installer
SetupIconFile=app.ico
; Mutex to prevent installation while the app is running
AppMutex=def_dictionary_mutex
CloseApplications=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Desktop shortcut, checked by default
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\def.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\def"; Filename: "{app}\def.exe"
Name: "{userdesktop}\def"; Filename: "{app}\def.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\def.exe"; Description: "{cm:LaunchProgram,def}"; Flags: nowait postinstall skipifsilent
