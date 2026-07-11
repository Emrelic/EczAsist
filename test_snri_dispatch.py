# -*- coding: utf-8 -*-
"""SNRI 4.2.2(1) dispatch entegrasyon testi (2026-07-06).

Kapsam:
  1. snri_4_2_2 modül akıl testi (13 senaryo)
  2. kontrol_psikiyatri → SNRI delege (eksik dal fix)
  3. kontrol_cesitli_madde_45_uriner → duloksetin SUI-suz delege
     (önceki davranış: sabit ŞÜPHELİ — kullanıcı şikayeti 2026-07-06,
      10 duloksetin reçetesinin tümü ÜROLOJİ butonunda ŞÜPHELİ)
  4. noropatik_4_2_35 → duloksetin sessiz delege
  5. Regresyon: SSRI / üriner SUI'li duloksetin davranışı değişmedi

Çalıştır: python test_snri_dispatch.py
"""
import sys

from recete_kontrol.base_kontrol import KontrolSonucu
from recete_kontrol.snri_4_2_2 import akil_testi_calistir, snri_kontrol_4_2_2
from recete_kontrol.sut_kontrolleri import (
    kontrol_psikiyatri, kontrol_cesitli_madde_45_uriner)
from recete_kontrol.noropatik_4_2_35 import noropatik_kontrol_4_2_35

SONUCLAR = []


def kontrol(ad, rapor, beklenen):
    ok = rapor.sonuc == beklenen
    SONUCLAR.append(ok)
    print(f"{'✓' if ok else '✗'} {ad}")
    if not ok:
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        print(f"    MESAJ: {rapor.mesaj}")


def main():
    print("=" * 70)
    print("1) snri_4_2_2 modül akıl testi")
    print("=" * 70)
    modul_ok = akil_testi_calistir()
    SONUCLAR.append(modul_ok)

    print()
    print("=" * 70)
    print("2) kontrol_psikiyatri → SNRI delege")
    print("=" * 70)
    kontrol("Duloksetin raporsuz, reçeteci psikiyatri → UYGUN",
            kontrol_psikiyatri({
                'ilac_adi': 'DUXET 60MG 28 GASTRO-REZISTAN SERT KAPSÜL',
                'etkin_madde': 'DULOKSETİN', 'atc_kodu': 'N06AX21',
                'doktor_uzmanligi': 'Ruh Sağlığı ve Hastalıkları'}),
            KontrolSonucu.UYGUN)
    kontrol("Duloksetin raporsuz, aile hekimi → UYGUN DEĞİL",
            kontrol_psikiyatri({
                'ilac_adi': 'DULOXX 30MG 28 KAPSÜL (SNRI)',
                'etkin_madde': 'DULOKSETİN', 'atc_kodu': 'N06AX21',
                'doktor_uzmanligi': 'Aile Hekimliği'}),
            KontrolSonucu.UYGUN_DEGIL)
    kontrol("Duloksetin raporsuz, branş bilinmiyor → ŞARTLI UYGUN",
            kontrol_psikiyatri({
                'ilac_adi': 'DYLOXIA 30MG 28 KAPSÜL',
                'etkin_madde': 'DULOKSETİN', 'atc_kodu': 'N06AX21'}),
            KontrolSonucu.SARTLI_UYGUN)
    kontrol("Venlafaksin, nöroloji + geçmiş yok → ŞARTLI UYGUN (6 ay manuel)",
            kontrol_psikiyatri({
                'ilac_adi': 'EFEXOR XR', 'etkin_madde': 'VENLAFAKSIN',
                'atc_kodu': 'N06AX16', 'doktor_uzmanligi': 'Nöroloji'}),
            KontrolSonucu.SARTLI_UYGUN)
    kontrol("Mirtazapin, nöroloji, ilk reçete 10 ay önce → UYGUN DEĞİL",
            kontrol_psikiyatri({
                'ilac_adi': 'REMERON', 'etkin_madde': 'MIRTAZAPIN',
                'atc_kodu': 'N06AX11', 'doktor_uzmanligi': 'Nöroloji',
                'recete_tarihi': '2026-06-15',
                'hasta_snri_ilk_recete_tarihi': '2025-08-10'}),
            KontrolSonucu.UYGUN_DEGIL)
    # Regresyon — SSRI davranışı değişmemeli
    kontrol("SSRI (sertralin) raporsuz → UYGUN (regresyon)",
            kontrol_psikiyatri({
                'ilac_adi': 'LUSTRAL', 'etkin_madde': 'SERTRALIN',
                'atc_kodu': 'N06AB06', 'doktor_uzmanligi': 'Aile Hekimliği'}),
            KontrolSonucu.UYGUN)

    print()
    print("=" * 70)
    print("3) Üriner M.45 → duloksetin delege (ŞÜPHELİ yığılması fix)")
    print("=" * 70)
    # Kullanıcının gerçek vakaları (2026-07-06):
    kontrol("DUXET raporsuz (HATİCE DÖNMEZ tipi) → artık sabit ŞÜPHELİ değil "
            "(branş yok → ŞARTLI UYGUN)",
            kontrol_cesitli_madde_45_uriner({
                'ilac_adi': 'DUXET 60MG 28 GASTRO-REZISTAN SERT KAPSÜL',
                'etkin_madde': 'DULOKSETİN', 'atc_kodu': 'N06AX21',
                'cinsiyet': 'K'}),
            KontrolSonucu.SARTLI_UYGUN)
    kontrol("DULOXX + migren SGKEYR raporu, kadın, SUI yok (ESEDOVA tipi) → "
            "SNRI şartlarına delege (branş yok → ŞARTLI UYGUN)",
            kontrol_cesitli_madde_45_uriner({
                'ilac_adi': 'DULOXX 30MG 28 KAPSÜL (SNRI)',
                'etkin_madde': 'DULOKSETİN', 'atc_kodu': 'N06AX21',
                'cinsiyet': 'K', 'rapor_kodu': '20.00',
                'rapor_aciklamalari': [
                    'SGKEYR DULOKSETIN HCL (30 mg 1x1) G43.9-Migren, '
                    'G44.2-Gerilim baş ağrısı']}),
            KontrolSonucu.SARTLI_UYGUN)
    # Rapor yalnız "nöropatik ağrı" diyor ("diyabetik" ibaresi YOK) —
    # D_A3 yalnız diyabetik periferal nöropatik ağrıyı kapsar → endikasyon
    # atomu KE-şartlı, nöroloji raporu VAR → ŞARTLI UYGUN (manuel: diyabetik mi?)
    kontrol("DUXET + nöropatik ağrı raporu, erkek (ERHAN USLU tipi) → "
            "4.2.35 D_A3 zincir delege (ŞARTLI UYGUN)",
            kontrol_cesitli_madde_45_uriner({
                'ilac_adi': 'DUXET 30MG 28 GASTRO-REZISTAN SERT KAPSÜL',
                'etkin_madde': 'DULOKSETİN', 'atc_kodu': 'N06AX21',
                'cinsiyet': 'E', 'rapor_kodu': '68',
                'rapor_doktor_brans': 'Nöroloji',
                'rapor_aciklamalari': [
                    'nöropatik ağrı duloksetin 60 mg 1x1 pregabalin 150 mg 2x1']}),
            KontrolSonucu.SARTLI_UYGUN)
    kontrol("Duloksetin raporsuz, reçeteci psikiyatri → UYGUN (üriner girişten)",
            kontrol_cesitli_madde_45_uriner({
                'ilac_adi': 'CYMBALTA 30 MG', 'etkin_madde': 'DULOKSETIN',
                'atc_kodu': 'N06AX21', 'doktor_uzmanligi': 'Psikiyatri',
                'cinsiyet': 'K'}),
            KontrolSonucu.UYGUN)
    # Regresyon — SUI'li kadın raporlu duloksetin M.45'te kalmalı
    kontrol("Duloksetin + kadın + SUI raporu → M.45 UYGUN (regresyon)",
            kontrol_cesitli_madde_45_uriner({
                'ilac_adi': 'CYMBALTA 30 MG', 'etkin_madde': 'DULOKSETIN',
                'atc_kodu': 'N06AX21', 'cinsiyet': 'K', 'rapor_kodu': '20.01',
                'doktor_uzmanligi': 'Üroloji',
                'rapor_aciklamalari': ['stres üriner inkontinans mikst']}),
            KontrolSonucu.UYGUN)

    print()
    print("=" * 70)
    print("4) Nöropatik 4.2.35 → duloksetin sessiz delege")
    print("=" * 70)
    kontrol("Duloksetin sessiz + psikiyatri → SNRI UYGUN",
            noropatik_kontrol_4_2_35({
                'etkin_madde': 'DULOKSETIN', 'brans': 'Psikiyatri'}),
            KontrolSonucu.UYGUN)
    kontrol("Duloksetin diyabetik nöropati + endokrin → D_A3 UYGUN (regresyon)",
            noropatik_kontrol_4_2_35({
                'etkin_madde': 'DULOKSETIN',
                'brans': 'Endokrinoloji ve Metabolizma',
                'recete_teshisleri': ['E11.4 DIYABETIK NOROPATI']}),
            KontrolSonucu.UYGUN)

    print()
    print("=" * 70)
    toplam = len(SONUCLAR)
    gecen = sum(1 for x in SONUCLAR if x)
    print(f"GENEL SONUÇ: {gecen}/{toplam} kontrol geçti")
    return gecen == toplam


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
