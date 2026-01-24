@echo off
chcp 65001 >nul 2>&1
title Kurulum Paketi Olusturucu
color 0B

echo.
echo ══════════════════════════════════════════════════════════════
echo   BOTANIK KASA - KURULUM PAKETI OLUSTURUCU
echo ══════════════════════════════════════════════════════════════
echo.

set "KAYNAK=%~dp0"
set "HEDEF=%USERPROFILE%\Desktop\BotanikKasa_Kurulum"

echo Kurulum paketi olusturuluyor...
echo Hedef: %HEDEF%
echo.

REM Hedef klasoru olustur
if exist "%HEDEF%" rmdir /s /q "%HEDEF%"
mkdir "%HEDEF%"

echo [1/8] Kurulum dosyalari kopyalaniyor...
copy "%KAYNAK%KURULUM.bat" "%HEDEF%\" >nul
copy "%KAYNAK%requirements.txt" "%HEDEF%\" >nul

echo [2/8] Konfigurasyon modulu kopyalaniyor...
copy "%KAYNAK%kasa_config.py" "%HEDEF%\" >nul

echo [3/8] API modulleri kopyalaniyor...
copy "%KAYNAK%kasa_api_server.py" "%HEDEF%\" >nul
copy "%KAYNAK%kasa_api_client.py" "%HEDEF%\" >nul

echo [4/8] Kasa modulu kopyalaniyor...
copy "%KAYNAK%kasa_takip_modul.py" "%HEDEF%\" >nul

echo [5/8] Ekstre modulu kopyalaniyor...
copy "%KAYNAK%depo_ekstre_modul.py" "%HEDEF%\" >nul 2>nul

echo [6/8] Yardimci moduller kopyalaniyor...
copy "%KAYNAK%botanik_veri_cek.py" "%HEDEF%\" >nul 2>nul
copy "%KAYNAK%kasa_raporlama.py" "%HEDEF%\" >nul 2>nul
copy "%KAYNAK%kasa_yazici.py" "%HEDEF%\" >nul 2>nul
copy "%KAYNAK%kasa_whatsapp.py" "%HEDEF%\" >nul 2>nul
copy "%KAYNAK%kasa_gecmis.py" "%HEDEF%\" >nul 2>nul
copy "%KAYNAK%kasa_email.py" "%HEDEF%\" >nul 2>nul
copy "%KAYNAK%kasa_yardim.py" "%HEDEF%\" >nul 2>nul
copy "%KAYNAK%kasa_kontrol_listesi.py" "%HEDEF%\" >nul 2>nul
copy "%KAYNAK%rapor_ayarlari.py" "%HEDEF%\" >nul 2>nul

echo [7/8] Test dosyalari kopyalaniyor...
copy "%KAYNAK%test_ag_baglanti.py" "%HEDEF%\" >nul 2>nul

echo [8/8] README olusturuluyor...
(
echo ══════════════════════════════════════════════════════════════
echo   BOTANIK KASA MODULU - KURULUM KILAVUZU
echo ══════════════════════════════════════════════════════════════
echo.
echo KURULUM ADIMLARI:
echo.
echo 1. Bu klasoru hedef bilgisayara kopyalayin
echo    ^(USB, ag paylasimi veya OneDrive ile^)
echo.
echo 2. KURULUM.bat dosyasini cift tiklayarak calistirin
echo.
echo 3. Kurulum sihirbazini takip edin:
echo    - Python kontrol edilecek
echo    - Gerekli paketler kurulacak
echo    - Ana Makine / Terminal secimi yapilacak
echo.
echo 4. Kurulum tamamlaninca "KASA_BASLAT.bat" olusacak
echo.
echo ══════════════════════════════════════════════════════════════
echo.
echo GEREKSINIMLER:
echo   - Windows 10/11
echo   - Python 3.8 veya uzeri
echo   - Internet baglantisi ^(ilk kurulum icin^)
echo.
echo ══════════════════════════════════════════════════════════════
echo.
echo MAKINE TIPLERI:
echo.
echo [ANA MAKINE]
echo   - Veritabani bu bilgisayarda tutulur
echo   - API Server calistirir
echo   - Diger terminaller buraya baglanir
echo.
echo [TERMINAL]
echo   - Ana makineye baglanir
echo   - Veriler ana makinede saklanir
echo   - Ana makine IP adresi gerekir
echo.
echo ══════════════════════════════════════════════════════════════
) > "%HEDEF%\BENIOKU.txt"

echo.
echo ══════════════════════════════════════════════════════════════
echo   KURULUM PAKETI OLUSTURULDU!
echo ══════════════════════════════════════════════════════════════
echo.
echo   Konum: %HEDEF%
echo.
echo   Icerik:
dir /b "%HEDEF%"
echo.
echo ══════════════════════════════════════════════════════════════
echo.
echo   Bu klasoru baska bilgisayara kopyalayin ve
echo   KURULUM.bat dosyasini calistirin.
echo.
echo ══════════════════════════════════════════════════════════════
echo.

REM Klasoru ac
explorer "%HEDEF%"

pause
