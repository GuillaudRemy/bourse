; Installateur Windows de Bourse (Inno Setup 6), construit par .github/workflows/publier.yml.
;
; Installation par utilisateur, sans droits administrateur, dans
; %LOCALAPPDATA%\Programs\Bourse. Les donnees vivent a part (%LOCALAPPDATA%\Bourse) :
; reinstaller, mettre a jour ou desinstaller ne les touche jamais.
;
; La mise a jour automatique relance ce meme installateur en /SILENT : l'entree
; [Run] sans « skipifsilent » relance alors l'application une fois les fichiers en place.

#define Version GetEnv("BOURSE_VERSION")
#if Version == ""
  #define Version "0.0.0"
#endif

[Setup]
AppId={{09CB41F6-88C0-4FE0-94B3-8A7003576DB1}
AppName=Bourse
AppVersion={#Version}
AppVerName=Bourse {#Version}
AppPublisher=Bourse
DefaultDirName={localappdata}\Programs\Bourse
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=..\sortie
OutputBaseFilename=Bourse-Setup
SetupIconFile=bourse.ico
UninstallDisplayIcon={app}\bourse.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[InstallDelete]
; Le code de la version precedente part entierement : pas de fichier fantome.
Type: filesandordirs; Name: "{app}\backend"
Type: filesandordirs; Name: "{app}\frontend"

[Files]
Source: "..\paquet\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "bourse.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\Bourse"; Filename: "{app}\python\python.exe"; Parameters: "-m backend.lanceur"; WorkingDir: "{app}"; IconFilename: "{app}\bourse.ico"; Comment: "Analyse des cours et des fondamentaux"
Name: "{autoprograms}\Bourse"; Filename: "{app}\python\python.exe"; Parameters: "-m backend.lanceur"; WorkingDir: "{app}"; IconFilename: "{app}\bourse.ico"

[Run]
Filename: "{app}\python\python.exe"; Parameters: "-m backend.lanceur"; WorkingDir: "{app}"; Description: "Lancer Bourse"; Flags: postinstall nowait; Check: LancerApres

[Code]
// /NOLAUNCH : installation sans lancement (tests automatiques).
function LancerApres(): Boolean;
begin
  Result := Pos('/NOLAUNCH', UpperCase(GetCmdTail)) = 0;
end;
