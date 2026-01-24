@echo off
chcp 65001 >nul 2>&1
title Botanik Kasa Modulu - Kurulum Sihirbazi
color 0A

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║          BOTANIK KASA MODULU - KURULUM SIHIRBAZI            ║
echo ║                                                              ║
echo ║     Kasa Kapatma ve Ekstre Kontrol Modulleri Kurulumu       ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo.

REM ===== ADIM 1: Python Kontrolu =====
echo [ADIM 1/5] Python kontrolu yapiliyor...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [HATA] Python bulunamadi!
    echo.
    echo Python kurulu degil veya PATH'e eklenmemis.
    echo Lutfen https://www.python.org adresinden Python indirip kurun.
    echo Kurulum sirasinda "Add Python to PATH" secenegini isaretleyin.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
echo [OK] Python %PYTHON_VER% bulundu.
echo.

REM ===== ADIM 2: Gerekli Paketlerin Kurulumu =====
echo [ADIM 2/5] Gerekli Python paketleri kuruluyor...
echo Bu islem birkaç dakika surebilir, lutfen bekleyin...
echo.

pip install -r "%~dp0requirements.txt" --quiet
if errorlevel 1 (
    echo [UYARI] Bazi paketler kurulamadi, manuel kontrol gerekebilir.
) else (
    echo [OK] Tum paketler basariyla kuruldu.
)
echo.

REM ===== ADIM 3: Makine Tipi Secimi =====
:MAKINE_SEC
echo [ADIM 3/5] Makine tipi secimi
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║  Bu bilgisayar nasil kullanilacak?                          ║
echo ║                                                              ║
echo ║  [1] ANA MAKINE (Server)                                    ║
echo ║      - Veritabani bu bilgisayarda tutulur                   ║
echo ║      - Diger terminaller buraya baglanir                    ║
echo ║      - API Server calistirir                                ║
echo ║                                                              ║
echo ║  [2] TERMINAL (Client)                                      ║
echo ║      - Ana makineye baglanir                                ║
echo ║      - Veriler ana makinede saklanir                        ║
echo ║      - Ag uzerinden calisir                                 ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
set /p MAKINE_TIPI="Seciminiz (1 veya 2): "

if "%MAKINE_TIPI%"=="1" goto ANA_MAKINE_AYAR
if "%MAKINE_TIPI%"=="2" goto TERMINAL_AYAR
echo [HATA] Gecersiz secim! Lutfen 1 veya 2 girin.
goto MAKINE_SEC

REM ===== ANA MAKINE AYARLARI =====
:ANA_MAKINE_AYAR
echo.
echo [ADIM 4/5] Ana Makine ayarlari yapiliyor...
echo.

REM IP adresini bul
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    for /f "tokens=1" %%b in ("%%a") do set LOCAL_IP=%%b
)

echo Bu bilgisayarin IP adresi: %LOCAL_IP%
echo.

REM Konfigurasyon dosyasi olustur
echo {"makine_tipi": "ana_makine", "api_host": "0.0.0.0", "api_port": 5000, "local_ip": "%LOCAL_IP%"} > "%~dp0kasa_config.json"
echo [OK] Konfigurasyon kaydedildi: kasa_config.json
echo.

REM Baslat scripti olustur
echo @echo off > "%~dp0KASA_BASLAT.bat"
echo title Botanik Kasa - Ana Makine >> "%~dp0KASA_BASLAT.bat"
echo echo. >> "%~dp0KASA_BASLAT.bat"
echo echo ══════════════════════════════════════════════════════════ >> "%~dp0KASA_BASLAT.bat"
echo echo   BOTANIK KASA - ANA MAKINE >> "%~dp0KASA_BASLAT.bat"
echo echo   API Server baslatiliyor... >> "%~dp0KASA_BASLAT.bat"
echo echo   Diger terminaller bu makineye baglanabilir. >> "%~dp0KASA_BASLAT.bat"
echo echo   Kapatmak icin bu pencereyi kapatin. >> "%~dp0KASA_BASLAT.bat"
echo echo ══════════════════════════════════════════════════════════ >> "%~dp0KASA_BASLAT.bat"
echo echo. >> "%~dp0KASA_BASLAT.bat"
echo cd /d "%%~dp0" >> "%~dp0KASA_BASLAT.bat"
echo start "" python kasa_api_server.py --host 0.0.0.0 --port 5000 >> "%~dp0KASA_BASLAT.bat"
echo timeout /t 3 /nobreak ^>nul >> "%~dp0KASA_BASLAT.bat"
echo python kasa_takip_modul.py >> "%~dp0KASA_BASLAT.bat"

echo [OK] Baslat scripti olusturuldu: KASA_BASLAT.bat
goto KURULUM_TAMAMLA

REM ===== TERMINAL AYARLARI =====
:TERMINAL_AYAR
echo.
echo [ADIM 4/5] Terminal ayarlari yapiliyor...
echo.
echo Ana makinenin IP adresini girin.
echo (Ornek: 192.168.1.120)
echo.
set /p ANA_MAKINE_IP="Ana Makine IP: "

if "%ANA_MAKINE_IP%"=="" (
    echo [HATA] IP adresi bos olamaz!
    goto TERMINAL_AYAR
)

echo.
echo Ana makineye baglanti test ediliyor...
python -c "import requests; r=requests.get('http://%ANA_MAKINE_IP%:5000/api/health', timeout=5); print('[OK] Baglanti basarili!' if r.status_code==200 else '[HATA] Baglanti basarisiz')" 2>nul
if errorlevel 1 (
    echo [UYARI] Ana makineye baglanilamadi.
    echo         Ana makinede API Server calistigrindan emin olun.
    echo         Kuruluma devam ediliyor...
)
echo.

REM Konfigurasyon dosyasi olustur
echo {"makine_tipi": "terminal", "ana_makine_ip": "%ANA_MAKINE_IP%", "api_port": 5000} > "%~dp0kasa_config.json"
echo [OK] Konfigurasyon kaydedildi: kasa_config.json
echo.

REM Baslat scripti olustur
echo @echo off > "%~dp0KASA_BASLAT.bat"
echo title Botanik Kasa - Terminal >> "%~dp0KASA_BASLAT.bat"
echo echo. >> "%~dp0KASA_BASLAT.bat"
echo echo ══════════════════════════════════════════════════════════ >> "%~dp0KASA_BASLAT.bat"
echo echo   BOTANIK KASA - TERMINAL >> "%~dp0KASA_BASLAT.bat"
echo echo   Ana Makine: %ANA_MAKINE_IP%:5000 >> "%~dp0KASA_BASLAT.bat"
echo echo ══════════════════════════════════════════════════════════ >> "%~dp0KASA_BASLAT.bat"
echo echo. >> "%~dp0KASA_BASLAT.bat"
echo cd /d "%%~dp0" >> "%~dp0KASA_BASLAT.bat"
echo python kasa_takip_modul.py --server %ANA_MAKINE_IP%:5000 >> "%~dp0KASA_BASLAT.bat"

echo [OK] Baslat scripti olusturuldu: KASA_BASLAT.bat
goto KURULUM_TAMAMLA

REM ===== KURULUM TAMAMLANDI =====
:KURULUM_TAMAMLA
echo.
echo [ADIM 5/5] Kurulum tamamlaniyor...
echo.

REM Masaustune kisayol olustur
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%temp%\kisayol.vbs"
echo sLinkFile = oWS.SpecialFolders("Desktop") ^& "\Botanik Kasa.lnk" >> "%temp%\kisayol.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%temp%\kisayol.vbs"
echo oLink.TargetPath = "%~dp0KASA_BASLAT.bat" >> "%temp%\kisayol.vbs"
echo oLink.WorkingDirectory = "%~dp0" >> "%temp%\kisayol.vbs"
echo oLink.Description = "Botanik Kasa Modulu" >> "%temp%\kisayol.vbs"
echo oLink.Save >> "%temp%\kisayol.vbs"
cscript //nologo "%temp%\kisayol.vbs"
del "%temp%\kisayol.vbs"
echo [OK] Masaustune kisayol olusturuldu: "Botanik Kasa"
echo.

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                                                              ║
echo ║              KURULUM BASARIYLA TAMAMLANDI!                  ║
echo ║                                                              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
if "%MAKINE_TIPI%"=="1" (
    echo   Makine Tipi: ANA MAKINE
    echo   IP Adresi: %LOCAL_IP%
    echo.
    echo   Diger terminaller bu IP'yi kullanarak baglanabilir.
) else (
    echo   Makine Tipi: TERMINAL
    echo   Ana Makine: %ANA_MAKINE_IP%
)
echo.
echo   Programi baslatmak icin:
echo   - Masaustundeki "Botanik Kasa" kisayolunu kullanin
echo   - veya KASA_BASLAT.bat dosyasini calistirin
echo.
echo ══════════════════════════════════════════════════════════════
echo.
pause
