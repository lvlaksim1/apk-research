#ifndef MyAppVersion
#define MyAppVersion "0.0.0-dev"
#endif

#define MyAppName "apk-research"
#define MyAppExeName "apk-research.exe"
#define MyAppId "{{5C5EE2B7-78FB-47E1-95C7-85AA2540195A}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=lvlaksim1
AppPublisherURL=https://github.com/lvlaksim1/apk-research
AppSupportURL=https://github.com/lvlaksim1/apk-research/issues
DefaultDirName={localappdata}\Programs\apk-research
DefaultGroupName=apk-research
DisableDirPage=yes
DisableProgramGroupPage=yes
DirExistsWarning=no
UsePreviousAppDir=yes
UsePreviousGroup=yes
UsePreviousTasks=yes
OutputDir=..\installer
OutputBaseFilename=apk-research-update_v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\build\app-icon\apk-research.ico
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}
VersionInfoDescription=apk-research update installer

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: unchecked

[Files]
Source: "..\dist\apk-research\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Recreate shortcuts on every update so icon/metadata changes are refreshed.
[Icons]
Name: "{autoprograms}\apk-research"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{userdesktop}\apk-research"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить apk-research"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  InstalledExe: String;
begin
  InstalledExe := ExpandConstant('{app}\{#MyAppExeName}');
  if not FileExists(InstalledExe) then
  begin
    MsgBox('apk-research не найден.' + #13#10 +
      'Для первой установки используйте полный установщик apk-research-setup.',
      mbError, MB_OK);
    Result := False;
    exit;
  end;
  Result := True;
end;
