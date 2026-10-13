#ifndef PayloadDir
  #error PayloadDir must be supplied by build.ps1
#endif
#ifndef OutputDir
  #error OutputDir must be supplied by build.ps1
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{BA1247EF-B51A-4BF3-B736-D8BEC8F01D82}
AppName=Docling Stage-2B Offline
AppVersion={#AppVersion}
AppPublisher=Docling Stage-2B Windows Community Project
DefaultDirName={localappdata}\Programs\Docling Stage-2B
DefaultGroupName=Docling Stage-2B
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=Docling-Stage2B-Offline-Setup
Compression=lzma2/fast
SolidCompression=yes
; Large native ML runtimes and model packs cannot fit into a single Windows EXE.
; Produce a small Setup.exe plus all local BIN slices. All files together form
; a self-contained offline installer; the destination PC never downloads data.
DiskSpanning=yes
DiskSliceSize=1900000000
SlicesPerDisk=1
WizardStyle=modern
ArchitecturesAllowed=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\DoclingStage2B.exe
CloseApplications=force
RestartApplications=no

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Icons]
Name: "{autoprograms}\Docling Stage-2B"; Filename: "{app}\DoclingStage2B.exe"
Name: "{autodesktop}\Docling Stage-2B"; Filename: "{app}\DoclingStage2B.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\support\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; Parameters: "/silent /install"; Flags: waituntilterminated; StatusMsg: "Installing the bundled offline WebView2 runtime..."; Check: not WebView2Present
Filename: "{app}\DoclingStage2B.exe"; Description: "Launch Docling Stage-2B"; Flags: nowait postinstall skipifsilent

[Code]
function WebView2Present: Boolean;
var
  Version: String;
begin
  Result :=
    (RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-18A5-4189-BE3D-3936461E5D85}', 'pv', Version) and (Version <> '')) or
    (RegQueryStringValue(HKLM, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-18A5-4189-BE3D-3936461E5D85}', 'pv', Version) and (Version <> ''));
end;
