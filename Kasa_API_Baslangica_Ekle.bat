@echo off
echo ============================================
echo   API SUNUCUSUNU WINDOWS BASLANGICINA EKLEME
echo ============================================
echo.

set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SCRIPT_PATH=%~dp0Kasa_API_Sunucu_Arka_Plan.vbs

echo Kisayol olusturuluyor...

REM VBS ile kisayol olustur
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\CreateShortcut.vbs"
echo sLinkFile = "%STARTUP_FOLDER%\Kasa API Sunucu.lnk" >> "%TEMP%\CreateShortcut.vbs"
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> "%TEMP%\CreateShortcut.vbs"
echo oLink.TargetPath = "%SCRIPT_PATH%" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.WorkingDirectory = "%~dp0" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Description = "Botanik Kasa API Sunucusu" >> "%TEMP%\CreateShortcut.vbs"
echo oLink.Save >> "%TEMP%\CreateShortcut.vbs"

cscript //nologo "%TEMP%\CreateShortcut.vbs"
del "%TEMP%\CreateShortcut.vbs"

echo.
echo Basarili! API sunucusu Windows baslangicina eklendi.
echo Bilgisayar her acildiginda otomatik calisacak.
echo.
echo Startup klasoru: %STARTUP_FOLDER%
echo.
pause
