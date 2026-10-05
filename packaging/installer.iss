; Inno Setup script for NeuraNova PA. Built by .github/workflows/windows.yml:
;   iscc /DAppVersion=1.0.0 packaging\installer.iss
; Installs for the current user only (no admin needed). Data lives in %LOCALAPPDATA%\NeuraNova PA and is kept
; on uninstall, so reinstalling or upgrading never loses tasks, settings or connected accounts.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6E1B8C2F-3A55-4F0B-9C1E-7A2D4E9B5F10}
AppName=NeuraNova PA
AppVersion={#AppVersion}
AppPublisher=NeuraNova
AppPublisherURL=https://www.neuranova.in
DefaultDirName={localappdata}\Programs\NeuraNova PA
DefaultGroupName=NeuraNova PA
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=NeuraNova-PA-Setup-{#AppVersion}
SetupIconFile=neuranova.ico
UninstallDisplayIcon={app}\NeuraNova PA.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "startup"; Description: "Start NeuraNova PA automatically when I sign in to Windows (recommended: reminders and checks keep running)"; GroupDescription: "Background:"

[Files]
Source: "..\dist\NeuraNova PA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README-WINDOWS.txt"; DestDir: "{app}"; Flags: isreadme

[Icons]
Name: "{group}\NeuraNova PA"; Filename: "{app}\NeuraNova PA.exe"
Name: "{group}\NeuraNova PA (sample data demo)"; Filename: "{app}\NeuraNova PA.exe"; Parameters: "--demo --port 8090"
Name: "{group}\Open NeuraNova PA data folder"; Filename: "{localappdata}\NeuraNova PA"
Name: "{group}\Uninstall NeuraNova PA"; Filename: "{uninstallexe}"
Name: "{autodesktop}\NeuraNova PA"; Filename: "{app}\NeuraNova PA.exe"; Tasks: desktopicon
Name: "{userstartup}\NeuraNova PA"; Filename: "{app}\NeuraNova PA.exe"; Parameters: "--no-browser"; WindowStartup: minimized; Tasks: startup

[Run]
Filename: "{app}\NeuraNova PA.exe"; Description: "Start NeuraNova PA now"; Flags: nowait postinstall skipifsilent
