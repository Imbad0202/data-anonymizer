; Inno Setup script for Data Anonymizer
; Wraps PyInstaller --onedir output into a Windows installer

#define MyAppName "Data Anonymizer"
#define MyAppNameLite "Data Anonymizer Lite"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Imbad0202"
#define MyAppURL "https://github.com/Imbad0202/data-anonymizer"
#define MyAppExeName "DataAnonymizer.exe"
#define MyAppExeNameLite "DataAnonymizerLite.exe"

; --- Full Build ---

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\DataAnonymizer
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=DataAnonymizer-{#MyAppVersion}-Setup
OutputDir=dist\installer
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=assets\icon.ico

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; PyInstaller --onedir output
Source: "dist\DataAnonymizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
