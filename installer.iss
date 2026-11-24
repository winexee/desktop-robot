; Masaüstü Robot Süpürge - Inno Setup Kurulum Betiği
[Setup]
AppName=Masaüstü Robot Süpürge
AppVersion=1.0.0
AppPublisher=winexee
AppPublisherURL=https://github.com/winexee/desktop-robot
DefaultDirName={autopf}\MasaustuRobotSupurge
DefaultGroupName=Masaüstü Robot Süpürge
OutputDir=Output
OutputBaseFilename=MasaustuRobotSupurge_Setup
SetupIconFile=assets\robot_supurge.ico
UninstallDisplayIcon={app}\MasaustuRobotSupurge.exe
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=lowest
CloseApplications=yes

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek görevler:"; Flags: checkedonce
Name: "startmenuicon"; Description: "Başlat Menüsü klasörü oluştur"; GroupDescription: "Ek görevler:"; Flags: checkedonce

[Files]
Source: "dist\MasaustuRobotSupurge\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Masaüstü Robot Süpürge"; Filename: "{app}\MasaustuRobotSupurge.exe"; Tasks: startmenuicon
Name: "{group}\Kaldır"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{autodesktop}\Masaüstü Robot Süpürge"; Filename: "{app}\MasaustuRobotSupurge.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MasaustuRobotSupurge.exe"; Description: "Masaüstü Robot Süpürge'yi çalıştır"; Flags: nowait postinstall skipifsilent
