@echo off
REM ===================================================================
REM SARTLI UYGUN etiketi + statin tamamlamalari
REM ===================================================================

cd /d "%~dp0"
chcp 65001 >nul

echo.
echo === Git Durumu ===
git status --short
echo.

echo === Tum degisiklikler stage'leniyor ===
git add -A
echo.

echo === Commit olusturuluyor ===
git commit -m "SARTLI UYGUN verdict etiketi + statin sema iyilestirmeleri" -m "Yeni KontrolSonucu.SARTLI_UYGUN enum + SartSonuc.sartli_atom bayragi." -m "" -m "Mantik: tum YOK gruplar bossa ve KE gruplar TAMAMEN sartli atomdan" -m "olusuyorsa SARTLI_UYGUN dondurur (aksi halde KONTROL_EDILEMEDI)." -m "" -m "Statin sartli atomlar:" -m "- X1 (Tedaviye 6+ ay ara) - pipeline'da son alim tarihi yoksa" -m "- CU2 (Cocuk rapor 6 ay suresi) - metinde 'X ay sure' yoksa" -m "" -m "GUI tarafi:" -m "- 19 yerde VERDICT_ETIKET'e SARTLI UYGUN eklendi" -m "- JSON serialization'a sartli_atom field eklendi" -m "- _SEMA_SONUC_RENK + verdict_renk + rozet_renk: zeytin yesili" -m "- verdict_kisa normalize 'SARTLI' / 'SARTLI' tespiti" -m "" -m "test_statin_sema_smoke.py: 2 yeni senaryo (YET X1 KE, COC CU2 KE)." -m "" -m "Sema renderer ek iyilestirmeleri (onceki commit sonrasi):" -m "- RAY_OFFSET (18px): dikey raylar kutu kenariyla ortusmesin" -m "- PARALEL_GAP_Y (yol-ici OR) vs YOLAK_GAP_Y (yol-arasi) ayrildi" -m "- BOX_PIN (5px): kablolar kutu kenarindan geri" -m "- Tam ekran toggle butonu + Sigdir/1:1/+/- zoom kontrolleri" -m "- alt_liste JSON serialization bug fix"
echo.

echo === Uzak depoya push ediliyor ===
git push
echo.

echo === Bitti ===
pause
