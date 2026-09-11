#define MyAppName "GET-Passes"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "СПб ГУП «Горэлектротранс»"
#define MyAppURL "https://github.com/avers2604/gup"
#define MyAppExeName "GET-Passes.exe"

[Setup]
AppId={{4A9A0D65-914B-4B68-A35C-A6F5E6843CB7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\GET-Passes
DefaultGroupName=GET-Passes
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=GET-Passes-Setup
SetupIconFile=..\app_icon.ico
UninstallDisplayIcon={app}\GET-Passes.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoVersion=1.1.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Система выпуска пропусков
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
Source: "..\dist\GET-Passes.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\GET-Passes"; Filename: "{app}\GET-Passes.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\GET-Passes"; Filename: "{app}\GET-Passes.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\GET-Passes.exe"; Description: "Запустить GET-Passes"; Flags: nowait postinstall skipifsilent
