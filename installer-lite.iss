; Inno Setup script for Data Anonymizer Lite (no NER)
; Smaller binary without PyTorch/ckip-transformers

#define MyAppName "Data Anonymizer Lite"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Imbad0202"
#define MyAppURL "https://github.com/Imbad0202/data-anonymizer"
#define MyAppExeName "DataAnonymizerLite.exe"

[Setup]
AppId={{B2C3D4E5-F6A7-8901-BCDE-F12345678901}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\DataAnonymizerLite
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=DataAnonymizerLite-{#MyAppVersion}-Setup
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
Source: "dist\DataAnonymizerLite\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
