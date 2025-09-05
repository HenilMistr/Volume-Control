;--------------------------------
; Inno Setup Script for Volume Controller
;--------------------------------

[Setup]
AppName=Volume Controller
AppVersion=1.0
AppPublisher=Your Name
DefaultDirName={autopf}\Volume Controller
DefaultGroupName=Volume Controller
UninstallDisplayIcon={app}\volume_controller.exe
OutputDir=dist_installer
OutputBaseFilename=VolumeControllerSetup
Compression=lzma
SolidCompression=yes
LicenseFile=LICENSE.txt  ; <-- Put your license text here

[Files]
Source: "dist\volume_controller.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: dontcopy

[Icons]
Name: "{group}\Volume Controller"; Filename: "{app}\volume_controller.exe"; Tasks: startmenu
Name: "{commondesktop}\Volume Controller"; Filename: "{app}\volume_controller.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"
Name: "startmenu"; Description: "Create a Start Menu shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "startup"; Description: "Start Volume Controller with Windows"; GroupDescription: "Startup options:"; Flags: unchecked

[Run]
Filename: "{app}\volume_controller.exe"; Description: "Launch Volume Controller"; Flags: nowait postinstall skipifsilent

[Registry]
; Add auto-start only if "startup" task is selected
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "VolumeController"; \
    ValueData: """{app}\volume_controller.exe"""; \
    Flags: uninsdeletevalue; Tasks: startup

;--------------------------------
; Custom Silent Install Options
;--------------------------------
[Code]
function CmdLineParamExists(const Value: string): Boolean;
var
  i: Integer;
begin
  Result := False;
  for i := 1 to ParamCount do
  begin
    if CompareText(ParamStr(i), Value) = 0 then
    begin
      Result := True;
      Break;
    end;
  end;
end;

procedure InitializeWizard;
begin
  { If running silently with /STARTUP, force startup task checked }
  if IsSilent and CmdLineParamExists('/STARTUP') then
    WizardSelectTasks('startup');

  { If running silently with /NOICONS, disable desktop + start menu icons }
  if IsSilent and CmdLineParamExists('/NOICONS') then
    WizardSelectTasks('');

  { Handle /DIR= for custom install path (Inno already supports /DIR= natively) }
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    if MsgBox('Do you want to also remove saved settings (hotkeys.json)?', mbConfirmation, MB_YESNO) = IDYES then
    begin
      DeleteFile(ExpandConstant('{localappdata}\VolumeController\hotkeys.json'));
    end;
  end;
end;
