#define AppName "DK Music Player v1.0"
#define AppVersion "1.0.0"
#define AppPublisher "Dinh Kim Thach (dinhkimthach.name.vn)"
#define AppExeName "DKMusicPlayer.exe"

#define PackageId "dk-music-player"
#define Arch "amd64"
#ifndef BuildVersion
  #define BuildVersion "1.0.0"
#endif

[Setup]
AppId={{DKMusicPlayer_SingleInstance_AppID}}
AppName={#AppName}
AppVersion={#BuildVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\DKMusicPlayer
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=installer\windows
OutputBaseFilename={#PackageId}_{#BuildVersion}_{#Arch}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

SetupIconFile=assets\icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create Desktop Shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent