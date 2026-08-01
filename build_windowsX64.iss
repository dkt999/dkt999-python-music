#define AppName "DK Music Player"
#define AppVersion "1.0.0"
#define AppPublisher "Dinh Kim Thach (dinhkimthach.name.vn)"
#define AppExeName "DKMusicPlayer.exe"

#define PackageId "dk-music-player"
#define Arch "amd64"
#ifndef BuildVersion
  #define BuildVersion "1.0.0"
#endif

#define AppProgID "DKMusicPlayer.AssocFile"

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
Name: "associate_audio"; Description: "Thêm {#AppName} vào danh sách Open With cho các file âm thanh (.mp3, .wav, .flac, .m4a, ...)"; GroupDescription: "File associations:"

[Files]
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; 1. Định nghĩa ProgID dùng chung cho tất cả các loại file Audio
Root: HKCU; Subkey: "Software\Classes\{#AppProgID}"; ValueType: string; ValueName: ""; ValueData: "Audio File ({#AppName})"; Flags: uninsdeletekey; Tasks: associate_audio
Root: HKCU; Subkey: "Software\Classes\{#AppProgID}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Tasks: associate_audio
Root: HKCU; Subkey: "Software\Classes\{#AppProgID}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: associate_audio

; 2. Đăng ký Open With cho từng định dạng audio cụ thể
Root: HKCU; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: string; ValueName: "{#AppProgID}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate_audio
Root: HKCU; Subkey: "Software\Classes\.wav\OpenWithProgids"; ValueType: string; ValueName: "{#AppProgID}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate_audio
Root: HKCU; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: string; ValueName: "{#AppProgID}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate_audio
Root: HKCU; Subkey: "Software\Classes\.aac\OpenWithProgids"; ValueType: string; ValueName: "{#AppProgID}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate_audio
Root: HKCU; Subkey: "Software\Classes\.m4a\OpenWithProgids"; ValueType: string; ValueName: "{#AppProgID}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate_audio
Root: HKCU; Subkey: "Software\Classes\.ogg\OpenWithProgids"; ValueType: string; ValueName: "{#AppProgID}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate_audio
Root: HKCU; Subkey: "Software\Classes\.wma\OpenWithProgids"; ValueType: string; ValueName: "{#AppProgID}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate_audio
Root: HKCU; Subkey: "Software\Classes\.opus\OpenWithProgids"; ValueType: string; ValueName: "{#AppProgID}"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associate_audio

; 3. Đăng ký Windows Capabilities (để xuất hiện trong Default Apps trên Windows 10/11)
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "DKMusicPlayer"; ValueData: "Software\DKMusicPlayer\Capabilities"; Flags: uninsdeletevalue; Tasks: associate_audio
Root: HKCU; Subkey: "Software\DKMusicPlayer\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#AppName}"; Tasks: associate_audio
Root: HKCU; Subkey: "Software\DKMusicPlayer\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Trình phát nhạc và định dạng âm thanh audio"; Tasks: associate_audio

; Danh sách file hỗ trợ trong Windows Settings
Root: HKCU; Subkey: "Software\DKMusicPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp3"; ValueData: "{#AppProgID}"; Tasks: associate_audio
Root: HKCU; Subkey: "Software\DKMusicPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wav"; ValueData: "{#AppProgID}"; Tasks: associate_audio
Root: HKCU; Subkey: "Software\DKMusicPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".flac"; ValueData: "{#AppProgID}"; Tasks: associate_audio
Root: HKCU; Subkey: "Software\DKMusicPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".aac"; ValueData: "{#AppProgID}"; Tasks: associate_audio
Root: HKCU; Subkey: "Software\DKMusicPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m4a"; ValueData: "{#AppProgID}"; Tasks: associate_audio
Root: HKCU; Subkey: "Software\DKMusicPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ogg"; ValueData: "{#AppProgID}"; Tasks: associate_audio
Root: HKCU; Subkey: "Software\DKMusicPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wma"; ValueData: "{#AppProgID}"; Tasks: associate_audio
Root: HKCU; Subkey: "Software\DKMusicPlayer\Capabilities\FileAssociations"; ValueType: string; ValueName: ".opus"; ValueData: "{#AppProgID}"; Tasks: associate_audio

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
// Khai báo API Windows Shell để refresh hệ thống
procedure SHChangeNotify(wEventId: LongInt; uFlags: UINT; dwItem1: LongInt; dwItem2: LongInt);
external 'SHChangeNotify@shell32.dll stdcall';

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Gọi SHCNE_ASSOCCHANGED ($08000000) để Windows cập nhật icon/Open With ngay
    SHChangeNotify($08000000, $0000, 0, 0);
  end;
end;