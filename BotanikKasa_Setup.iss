; Botanik Kasa Modulu - Inno Setup Script
; Bu dosyayi Inno Setup ile derleyerek Setup.exe olusturabilirsiniz

#define MyAppName "Botanik Kasa Modulu"
#define MyAppVersion "3.5"
#define MyAppPublisher "Botanik Eczane"
#define MyAppExeName "KASA_BASLAT.bat"

[Setup]
AppId={{B0TAN1K-KASA-M0DUL-2024-SETUP}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\BotanikKasa
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=C:\Users\ana\OneDrive\Desktop
OutputBaseFilename=BotanikKasa_Setup
SetupIconFile=kasa_icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Components]
Name: "main"; Description: "Program Dosyalari"; Flags: fixed

[Files]
; Ana program dosyalari
Source: "kasa_takip_modul.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "kasa_config.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "kasa_api_server.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "kasa_api_client.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

; Yardimci moduller
Source: "depo_ekstre_modul.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "botanik_veri_cek.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "kasa_raporlama.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "kasa_yazici.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "kasa_whatsapp.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "kasa_gecmis.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "kasa_email.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "kasa_yardim.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "kasa_kontrol_listesi.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "rapor_ayarlari.py"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; Ikon dosyasi
Source: "kasa_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Botanik Kasa"; Filename: "{app}\KASA_BASLAT.bat"; WorkingDir: "{app}"; IconFilename: "{app}\kasa_icon.ico"
Name: "{group}\Kaldir"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Botanik Kasa"; Filename: "{app}\KASA_BASLAT.bat"; WorkingDir: "{app}"; IconFilename: "{app}\kasa_icon.ico"

[Run]
; Python paketlerini kur (python -m pip kullan)
Filename: "cmd.exe"; Parameters: "/c python -m pip install flask flask-cors requests comtypes pywin32 Pillow --quiet"; StatusMsg: "Python paketleri kuruluyor (bu birkaç dakika surebilir)..."; Flags: runhidden waituntilterminated
; Ana makine icin Windows Firewall kurali ekle (5000 portu)
Filename: "netsh"; Parameters: "advfirewall firewall add rule name=""BotanikKasa API"" dir=in action=allow protocol=tcp localport=5000"; StatusMsg: "Firewall kurali ekleniyor..."; Flags: runhidden waituntilterminated

[Code]
var
  MakineTipiPage: TInputOptionWizardPage;
  IPAdresPage: TInputQueryWizardPage;
  MakineTipi: Integer;
  AnaMakineIP: String;

procedure InitializeWizard;
begin
  // Makine Tipi Secim Sayfasi
  MakineTipiPage := CreateInputOptionPage(wpSelectDir,
    'Makine Tipi Secimi',
    'Bu bilgisayar nasil kullanilacak?',
    'Lutfen bu bilgisayarin rolunu secin:',
    True, False);
  MakineTipiPage.Add('ANA MAKINE (Server) - Veritabani bu bilgisayarda tutulur, diger terminaller buraya baglanir');
  MakineTipiPage.Add('TERMINAL (Client) - Ana makineye baglanir, veriler ana makinede saklanir');
  MakineTipiPage.Values[0] := True;

  // IP Adresi Girisi Sayfasi (Terminal icin)
  IPAdresPage := CreateInputQueryPage(MakineTipiPage.ID,
    'Ana Makine IP Adresi',
    'Terminal modu icin ana makinenin IP adresini girin',
    'Ana makinenin IP adresi (ornek: 192.168.1.120):');
  IPAdresPage.Add('IP Adresi:', False);
  IPAdresPage.Values[0] := '192.168.1.120';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  // Component secim sayfasini atla (tek secim var)
  if PageID = wpSelectComponents then
    Result := True;
  // Terminal secilmediyse IP sayfasini atla
  if PageID = IPAdresPage.ID then
    Result := MakineTipiPage.Values[0]; // Ana Makine secildiyse atla
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ConfigFile: String;
  ConfigContent: String;
begin
  if CurStep = ssPostInstall then
  begin
    // Konfigurasyon dosyasi olustur
    ConfigFile := ExpandConstant('{app}\kasa_config.json');

    if MakineTipiPage.Values[0] then
    begin
      // Ana Makine
      ConfigContent := '{"makine_tipi": "ana_makine", "api_host": "0.0.0.0", "api_port": 5000}';

      // Baslat scripti (Ana Makine) - Konsol olmadan
      SaveStringToFile(ExpandConstant('{app}\KASA_BASLAT.bat'),
        '@echo off' + #13#10 +
        'cd /d "%~dp0"' + #13#10 +
        'start "" pythonw kasa_api_server.py --host 0.0.0.0 --port 5000' + #13#10 +
        'timeout /t 2 /nobreak >nul' + #13#10 +
        'start "" pythonw kasa_takip_modul.py' + #13#10,
        False);
    end
    else
    begin
      // Terminal
      AnaMakineIP := IPAdresPage.Values[0];
      ConfigContent := '{"makine_tipi": "terminal", "ana_makine_ip": "' + AnaMakineIP + '", "api_port": 5000}';

      // Baslat scripti (Terminal) - Konsol olmadan
      SaveStringToFile(ExpandConstant('{app}\KASA_BASLAT.bat'),
        '@echo off' + #13#10 +
        'cd /d "%~dp0"' + #13#10 +
        'start "" pythonw kasa_takip_modul.py --server ' + AnaMakineIP + ':5000' + #13#10,
        False);
    end;

    SaveStringToFile(ConfigFile, ConfigContent, False);
  end;
end;

function PythonKuruluMu(): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec('cmd.exe', '/c python --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0);
end;

function InitializeSetup(): Boolean;
var
  UninstallString: String;
  UninstallPath: String;
  ResultCode: Integer;
  ProgramKurulu: Boolean;
begin
  Result := True;
  ProgramKurulu := False;
  UninstallString := '';

  // Yontem 1: Kurulum dizininde unins000.exe var mi kontrol et (en guvenilir)
  UninstallPath := ExpandConstant('{autopf}\BotanikKasa\unins000.exe');
  if FileExists(UninstallPath) then
  begin
    ProgramKurulu := True;
    UninstallString := '"' + UninstallPath + '"';
  end;

  // Yontem 2: Registry'den kontrol (HKLM 64-bit)
  if not ProgramKurulu then
    if RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{B0TAN1K-KASA-M0DUL-2024-SETUP}_is1', 'UninstallString', UninstallString) then
      ProgramKurulu := True;

  // Yontem 3: Registry'den kontrol (HKLM 32-bit)
  if not ProgramKurulu then
    if RegQueryStringValue(HKLM32, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{B0TAN1K-KASA-M0DUL-2024-SETUP}_is1', 'UninstallString', UninstallString) then
      ProgramKurulu := True;

  // Yontem 4: Registry'den kontrol (HKCU)
  if not ProgramKurulu then
    if RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{B0TAN1K-KASA-M0DUL-2024-SETUP}_is1', 'UninstallString', UninstallString) then
      ProgramKurulu := True;

  if ProgramKurulu then
  begin
    // Program kurulu - sadece kaldir, yeniden kurma
    if MsgBox('Botanik Kasa Modulu zaten kurulu!' + #13#10 + #13#10 +
              'Programi kaldirmak istiyor musunuz?' + #13#10 + #13#10 +
              '(Yeniden kurmak icin Setup''i tekrar calistirin)',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      // Programi kaldir
      if UninstallString <> '' then
        Exec('cmd.exe', '/c ' + UninstallString + ' /SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);

      MsgBox('Program basariyla kaldirildi!' + #13#10 + #13#10 +
             'Yeniden kurmak icin Setup dosyasini tekrar calistirin.',
             mbInformation, MB_OK);
    end;
    // Her iki durumda da kurulumu durdur
    Result := False;
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
var
  ResultCode: Integer;
  PythonURL: String;
begin
  // Kurulum dizini secildikten sonra Python kontrol et
  if CurPageID = wpReady then
  begin
    if not PythonKuruluMu() then
    begin
      if MsgBox('Python bulunamadi!' + #13#10 + #13#10 +
                'Bu program icin Python 3.10+ gereklidir.' + #13#10 +
                'Python simdi otomatik olarak indirilip kurulsun mu?' + #13#10 + #13#10 +
                '(Kurulum sirasinda "Add Python to PATH" secenegini ISARETLEYIN!)',
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        // Python indirme sayfasini ac
        PythonURL := 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe';
        ShellExec('open', PythonURL, '', '', SW_SHOW, ewNoWait, ResultCode);

        MsgBox('Python indirme basladi.' + #13#10 + #13#10 +
               'ONEMLI: Kurulum sirasinda asagidaki secenegi ISARETLEYIN:' + #13#10 +
               '[X] Add Python to PATH' + #13#10 + #13#10 +
               'Python kurulumu tamamlandiktan sonra bu kuruluma devam edin.',
               mbInformation, MB_OK);
      end
      else
      begin
        MsgBox('Python olmadan kurulum yapilamaz.' + #13#10 +
               'Lutfen once Python kurun ve tekrar deneyin.',
               mbError, MB_OK);
        WizardForm.Close;
      end;
    end;
  end;
end;
