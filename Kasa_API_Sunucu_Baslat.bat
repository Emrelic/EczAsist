@echo off
title Botanik Kasa API Sunucusu
cd /d "%~dp0"

echo ============================================
echo   BOTANIK KASA API SUNUCUSU
echo   IP: 192.168.0.10  Port: 5000
echo ============================================
echo.

REM Flask kurulu mu kontrol et
python -c "import flask" 2>nul
if errorlevel 1 (
    echo Flask kurulu degil. Kuruluyor...
    pip install flask flask-cors
    echo.
)

echo API Sunucusu baslatiliyor...
echo Kapatmak icin bu pencereyi kapatin.
echo.
python kasa_api_server.py --host 0.0.0.0 --port 5000

pause
