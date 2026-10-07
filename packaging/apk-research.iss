#define MyAppName "apk-research"
#ifndef MyAppVersion
#define MyAppVersion "0.2.0-dev0"
#endif
#define MyAppPublisher "apk-research"
#define MyAppExeName "apk-research.exe"

[Setup]
AppId={{5C5EE2B7-78FB-47E1-95C7-85AA2540195A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\apk-research
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\installer
OutputBaseFilename=apk-research-setup_v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\build\app-icon\apk-research.ico
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousTasks=yes
CloseApplications=yes
RestartApplications=no
DisableDirPage=auto

[Files]
Source: "..\dist\apk-research\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent; Check: not IsUpdateMode
Filename: "{app}\{#MyAppExeName}"; Flags: nowait skipifdoesntexist; Check: ShouldRelaunchAfterUpdate

[Code]
function IsUpdateMode: Boolean;
begin
  Result := CompareText(ExpandConstant('{param:UPDATE|0}'), '1') = 0;
end;

function ShouldRelaunchAfterUpdate: Boolean;
begin
  Result := IsUpdateMode and
    (CompareText(ExpandConstant('{param:NORELAUNCH|0}'), '1') <> 0);
end;

procedure InitializeWizard;
begin
  if IsUpdateMode then
    WizardForm.Caption := 'Обновление apk-research';
end;
