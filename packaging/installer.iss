; Inno Setup script for Architectural Reverse Engineer (Windows)
;
; This creates a standard Windows installer (.exe) that:
;   - Installs the bundled application to Program Files
;   - Creates Start Menu and Desktop shortcuts
;   - Registers an uninstaller
;
; Prerequisites:
;   - Run build_windows.bat first to produce dist\ArchReverse\
;   - Inno Setup 6: https://jrsoftware.org/isdl.php

#define MyAppName "Architectural Reverse Engineer"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "ArchReverse"
#define MyAppURL "https://github.com/your-org/architectural-reverse-engineer"
#define MyAppExeName "ArchReverse.exe"

[Setup]
AppId={{B7A3E1F2-4D5C-6E7F-8A9B-0C1D2E3F4A5B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=ArchitecturalReverseEngineer-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Include the entire PyInstaller output directory
Source: "..\dist\ArchReverse\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
