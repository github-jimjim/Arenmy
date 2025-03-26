[Setup]
AppName=Jomfish
AppVersion=10.0
WizardStyle=modern
DefaultDirName={userappdata}\Jomfish  
DefaultGroupName=Jomfish
UninstallDisplayIcon={app}\jomfish.exe
Compression=lzma2
SolidCompression=yes
OutputDir=userdocs:Inno Setup Output
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
PrivilegesRequired=none

[Files]
Source: "jomfish.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "arena\dist\arena.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "jomfish_none.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "Readme.txt"; DestDir: "{app}"; Flags: isreadme

[Icons]
Name: "{group}\Jomfish"; Filename: "{app}\jomfish.exe"
Name: "{group}\Arena"; Filename: "{app}\arena.exe"

[Run]
Filename: "{cmd}"; Parameters: "/C reg add ""HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment"" /v PATH /t REG_EXPAND_SZ /d ""%PATH%;{app}"" /f"; Flags: runhidden runascurrentuser