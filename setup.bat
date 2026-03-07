@echo off
chcp 65001 >/dev/null 2>&1
title BotanikTakip Kurulum

echo ============================================
echo   BotanikTakip - Kurulum Baslatiliyor
echo ============================================
echo.

:: Python kontrolu
python --version >/dev/null 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python bulunamadi!
    echo Python 3.8 veya ustu kurulu olmali.
    echo https://www.python.org/downloads/ adresinden indirin.
    echo Kurulum sirasinda "Add Python to PATH" secenegini isaretleyin.
    echo.
    pause
    exit /b 1
)

echo [OK] Python bulundu:
python --version
echo.

:: pip kontrolu
python -m pip --version >/dev/null 2>&1
if %errorlevel% neq 0 (
    echo [HATA] pip bulunamadi! Python kurulumunu kontrol edin.
    pause
    exit /b 1
)

echo [OK] pip bulundu
echo.

:: Kurulum sihirbazi
echo Kurulum sihirbazi baslatiliyor...
echo.
python "%~dp0kurulum_wizard.py"

if %errorlevel% neq 0 (
    echo.
    echo [HATA] Kurulum sihirbazi hata ile sonlandi.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Kurulum tamamlandi!
echo   Programi baslatmak icin: python main.py
echo ============================================
echo.
pause
