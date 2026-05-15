@echo off
REM ===================================================================
REM Statin SUT 4.2.28.A — Syntax + Smoke Test
REM Calistir: cift tikla. Cikti pencereyi acik tutar.
REM ===================================================================
cd /d "%~dp0"
chcp 65001 >nul

echo.
echo === 1. py_compile (syntax check) ===
python -m py_compile recete_kontrol\sut_kontrolleri.py
if errorlevel 1 (
    echo HATA: syntax bozuk!
    pause
    exit /b 1
)
echo OK: sut_kontrolleri.py syntax temiz
echo.

echo === 2. test_statin_sema_smoke.py (semaarender + UYGUN/UYGUN_DEGIL/SUPHELI) ===
python test_statin_sema_smoke.py
set TESTRC=%errorlevel%
echo.

if %TESTRC% equ 0 (
    echo === BASARILI: tum senaryolar gecti ===
) else (
    echo === BAZI SENARYOLAR BASARISIZ — yukaridaki ciktiya bak ===
)
echo.
pause
exit /b %TESTRC%
