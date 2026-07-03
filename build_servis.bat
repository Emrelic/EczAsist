@echo off
REM ============================================================
REM  Yabanci Uyruklu Hasta Uyari Servisi - EXE derleme scripti
REM  Tek tik: gereksinimleri kurar + onefile/noconsole exe uretir.
REM  Cikti: dist\YabanciHastaUyari.exe
REM ============================================================
setlocal
cd /d "%~dp0"

echo [1/3] Gereksinimler kuruluyor (pyinstaller, pystray, pillow, pyodbc)...
python -m pip install --upgrade pip
python -m pip install pyinstaller pystray pillow pyodbc
if errorlevel 1 (
    echo HATA: pip kurulumu basarisiz.
    pause
    exit /b 1
)

echo [2/3] EXE derleniyor...
python -m PyInstaller --noconfirm --onefile --noconsole ^
    --name YabanciHastaUyari ^
    --hidden-import pyodbc ^
    --collect-all pystray ^
    --collect-all PIL ^
    yabanci_hasta_servis.py
if errorlevel 1 (
    echo HATA: PyInstaller derleme basarisiz.
    pause
    exit /b 1
)

echo [3/3] Tamamlandi.
echo Cikti: %~dp0dist\YabanciHastaUyari.exe
echo.
echo Dagitim icin bu exe'yi merkez klasore kopyalayin:
echo   \\192.168.1.169\merkez klasor\
echo Diger bilgisayarlarda exe'yi calistirin; "Kurulsun mu?" deyince Evet'e
echo basin - kendini C:\BotanikTakip'e kopyalayip Windows acilisina ekler.
echo.
pause
