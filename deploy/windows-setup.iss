#ifndef PublishDir
  #error PublishDir is required
#endif
#ifndef ReleaseVersion
  #define ReleaseVersion "1.0.0"
#endif
[Setup]
AppId={{9B3F13AF-8D45-4C51-B2AF-A86D283F4811}
AppName=PetriTrace
AppVersion={#ReleaseVersion}
DefaultDirName={localappdata}\Programs\PetriTrace
DefaultGroupName=PetriTrace
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\artifacts\setup
OutputBaseFilename=PetriTrace-{#ReleaseVersion}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\PetriTrace.exe
CloseApplications=yes
RestartApplications=no
SetupIconFile=..\static\brand\windows-icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Files]
Source: "{#PublishDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PetriTrace"; Filename: "{app}\PetriTrace.exe"; WorkingDir: "{app}"

[Registry]
Root: HKCU; Subkey: "Software\Classes\picameracontrol"; ValueType: string; ValueData: "URL:PetriTrace Manager"
Root: HKCU; Subkey: "Software\Classes\picameracontrol"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\picameracontrol\shell\open\command"; ValueType: string; ValueData: """{app}\PetriTrace.exe"" ""%1"""

; User configuration stays in the existing LocalAppData directory.
; Do not remove device configuration, keys, or Raspberry Pi data on uninstall.

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var Command: String;
begin
  if CurUninstallStep = usUninstall then
    if RegQueryStringValue(HKCU, 'Software\Classes\picameracontrol\shell\open\command', '', Command) then
      if CompareText(Command, '"' + ExpandConstant('{app}\PetriTrace.exe') + '" "%1"') = 0 then
        RegDeleteKeyIncludingSubkeys(HKCU, 'Software\Classes\picameracontrol');
end;
