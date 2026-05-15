@echo off
REM ===================================================================
REM Cowork Oncesi Commit + Push
REM Bu dosyayi cift tikla, mevcut tum degisiklikleri commit'le ve push'la.
REM ===================================================================

cd /d "%~dp0"
chcp 65001 >nul

echo.
echo === Git Durumu ===
git status
echo.

echo === Tum degisiklikler stage'leniyor ===
git add -A
echo.

echo === Commit olusturuluyor: "Cowork oncesi commit" ===
git commit -m "Cowork oncesi commit"
echo.

echo === Uzak depoya push ediliyor ===
git push
echo.

echo === Bitti ===
pause
