# -*- coding: utf-8 -*-
"""KLOGEL-A (klopidogrel+ASA kombinasyonu) dispatch regresyon testi.

SUT 4.2.15.A başlığı "Klopidogrel (kombinasyonları dahil)" — kombinasyon
ürünleri (etken "KOMBİNASYONLAR", ATC B01AC30) mevcut klopidogrel atomik
motoruna yönlenmelidir. Vaka: AVNİ DİLLİ 3OC7VPJ, KLOGEL-A 75/100, 2026-07-05.

İki yüzey test edilir:
  1) Aylık buton kapsamı: AylikReceteSorguGUI._klopidogrel_kategori/_alt_sinif
  2) Anlık kontrol kapsamı: sut_kontrolleri.sut_kategorisi_tespit_et

Çalıştırma: python test_klogel_dispatch.py
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASARILI = 0
BASARISIZ = 0


def kontrol(ad, gercek, beklenen):
    global BASARILI, BASARISIZ
    if gercek == beklenen:
        BASARILI += 1
        print(f"  PASS  {ad}: {gercek!r}")
    else:
        BASARISIZ += 1
        print(f"  FAIL  {ad}: beklenen {beklenen!r}, gelen {gercek!r}")


print("── 1) Aylık buton yüzeyi: _klopidogrel_kategori ──")
from aylik_recete_sorgu_gui import AylikReceteSorguGUI

kat = AylikReceteSorguGUI._klopidogrel_kategori
alt = AylikReceteSorguGUI._klopidogrel_alt_sinif

# KLOGEL-A: etken KOMBİNASYONLAR + ATC B01AC30 → ad kapısından yakalanmalı
kontrol("KLOGEL-A / KOMBİNASYONLAR / B01AC30",
        kat("KLOGEL-A 75/100MG 30 KAPSUL", "KOMBİNASYONLAR", "B01AC30"),
        "KLOPIDOGREL")
# Botanik'te hatalı C10 ATC girilmiş olsa bile ad kapısı yakalamalı
kontrol("KLOGEL-A / hatalı ATC C10",
        kat("KLOGEL-A 75/75MG 30 KAPSUL", "KOMBİNASYONLAR", "C10BX"),
        "KLOPIDOGREL")
# Diğer kombo markalar
kontrol("DUOPLAVIN", kat("DUOPLAVIN 75/100MG", "", "B01AC30"), "KLOPIDOGREL")
kontrol("COPLAVIX", kat("COPLAVIX 75/100MG", "", ""), "KLOPIDOGREL")
kontrol("DUOCOVER", kat("DUOCOVER 75/75MG", "", ""), "KLOPIDOGREL")
kontrol("DUOFLAGREL", kat("DUOFLAGREL 75/150MG", "", ""), "KLOPIDOGREL")
# B01AC30 ama klopidogrel İÇERMEYEN kombinasyon → kapsam DIŞI kalmalı
kontrol("ASASANTIN (ASA+dipiridamol, B01AC30)",
        kat("ASASANTIN RETARD 50 KAPSUL", "ASA + DIPIRIDAMOL", "B01AC30"),
        "NONE")
# Türkçe İ tuzağı: etken "KLOPİDOGREL" (dotted İ) yakalanmalı
kontrol("Türkçe İ etken (KLOPİDOGREL)",
        kat("GENERIK ILAC 75MG", "KLOPİDOGREL HİDROJEN SÜLFAT", ""),
        "KLOPIDOGREL")
# Fallback'e yeni eklenen mono jenerikler
kontrol("PINGEL (ATC boş)", kat("PINGEL 75MG", "", ""), "KLOPIDOGREL")
kontrol("PLAGREL (ATC boş)", kat("PLAGREL 75MG", "", ""), "KLOPIDOGREL")
kontrol("DILOXOL", kat("DILOXOL 75 MG 28 TB", "", ""), "KLOPIDOGREL")
kontrol("OPIREL", kat("OPIREL 75 MG", "", ""), "KLOPIDOGREL")
# Regresyon: mevcut davranış bozulmadı
kontrol("PLAVIX regresyon", kat("PLAVIX 75MG", "KLOPIDOGREL", "B01AC04"),
        "KLOPIDOGREL")
kontrol("BRILINTA regresyon", kat("BRILINTA 90MG", "TIKAGRELOR", "B01AC24"),
        "KLOPIDOGREL")  # kapsam etiketi tek: KLOPIDOGREL (P2Y12 grubu)
kontrol("Kapsam dışı ilaç", kat("PAROL 500MG", "PARASETAMOL", "N02BE01"),
        "NONE")

print("── 2) Alt sınıf: _klopidogrel_alt_sinif ──")
kontrol("KLOGEL-A alt sınıf",
        alt("KLOGEL-A 75/100MG 30 KAPSUL", "KOMBİNASYONLAR", "B01AC30"),
        "KLOPIDOGREL")
kontrol("BRILINTA alt sınıf", alt("BRILINTA 90MG", "", ""), "TIKAGRELOR")
kontrol("BRİLİNTA (Türkçe İ) alt sınıf", alt("BRİLİNTA 90MG", "", ""),
        "TIKAGRELOR")
kontrol("PRASIBLOCK alt sınıf", alt("PRASIBLOCK 10MG", "", ""), "PRASUGREL")

print("── 3) Anlık yüzey: sut_kategorisi_tespit_et ──")
from recete_kontrol.sut_kontrolleri import sut_kategorisi_tespit_et

kontrol("KLOGEL-A anlık kategori",
        sut_kategorisi_tespit_et({
            "ilac_adi": "KLOGEL-A 75/100MG 30 KAPSÜL",
            "etkin_madde": "KOMBİNASYONLAR",
        }),
        "KLOPIDOGREL")
kontrol("DUOPLAVIN anlık kategori",
        sut_kategorisi_tespit_et({
            "ilac_adi": "DUOPLAVIN 75/100MG 30 FTB",
            "etkin_madde": "KOMBİNASYONLAR",
        }),
        "KLOPIDOGREL")
kontrol("PLANOR anlık kategori",
        sut_kategorisi_tespit_et({
            "ilac_adi": "PLANOR 75 MG 28 FTB",
            "etkin_madde": "",
        }),
        "KLOPIDOGREL")
asasantin_kat = sut_kategorisi_tespit_et({
    "ilac_adi": "ASASANTIN RETARD 50 KAPSUL",
    "etkin_madde": "ASA + DIPIRIDAMOL",
})
kontrol("ASASANTIN anlık ≠ KLOPIDOGREL",
        asasantin_kat != "KLOPIDOGREL", True)
kontrol("PLAVIX anlık regresyon",
        sut_kategorisi_tespit_et({
            "ilac_adi": "PLAVIX 75MG 28 FTB",
            "etkin_madde": "KLOPIDOGREL",
        }),
        "KLOPIDOGREL")

print("── 4) Branş eşleştirici Türkçe İ fix: _klop_doktor_brans_in ──")
from recete_kontrol.sut_kontrolleri import (
    _klop_doktor_brans_in, _KLOP_BRANS_KRONIK_RAPOR)

kontrol("KARDİYOLOJİ (Türkçe İ)",
        _klop_doktor_brans_in("KARDİYOLOJİ", _KLOP_BRANS_KRONIK_RAPOR)[0],
        True)
kontrol("İÇ HASTALIKLARI (Türkçe İ)",
        _klop_doktor_brans_in("İÇ HASTALIKLARI", _KLOP_BRANS_KRONIK_RAPOR)[0],
        True)
kontrol("NÖROLOJİ",
        _klop_doktor_brans_in("NÖROLOJİ", _KLOP_BRANS_KRONIK_RAPOR)[0],
        True)
kontrol("KALP VE DAMAR CERRAHİSİ (ANA BRANŞ) regresyon",
        _klop_doktor_brans_in("KALP VE DAMAR CERRAHİSİ (ANA BRANŞ)",
                              _KLOP_BRANS_KRONIK_RAPOR)[0],
        True)
kontrol("Yetkisiz branş (ORTOPEDİ)",
        _klop_doktor_brans_in("ORTOPEDİ VE TRAVMATOLOJİ",
                              _KLOP_BRANS_KRONIK_RAPOR)[0],
        False)

print("── 5) Uçtan uca: AVNİ DİLLİ 3OC7VPJ senaryosu (Y-3) ──")
from recete_kontrol.sut_kontrolleri import kontrol_klopidogrel
from recete_kontrol.base_kontrol import KontrolSonucu

avni = {
    "ilac_adi": "KLOGEL-A 75/100MG 30 KAPSÜL",
    "etkin_madde": "KOMBİNASYONLAR",
    "atc_kodu": "B01AC30",
    "rapor_kodu": "04.02.1",
    "recete_teshisleri": [],
    "rapor_aciklamalari": [
        "01.09.2025(LDL)180 HASTAYA 01.09.2025 TARİHİNDE ANJİO-STENT "
        "UYGULANMIŞTIR. KORONER ARTER HASTALIĞI MEVCUTTUR. ANJİOTENSİN "
        "RESEPTÖR BLOKERLERİNİN DİĞER ANTİHİPERTANSİPLER İLE "
        "KOMBİNASYONLARININ KULLANIMINDA, HASTANIN MENOTERAPİ İLE KAN "
        "BASINCINI YETERLİ ORANDA KONTROL ALTINA ALINAMAMIŞTIR. "
        "(Ekleme=02/09/2025 16:47)",
    ],
    "recete_aciklamalari": ["Diğer - ."],
    "recete_tarihi": "27.06.2026",
    "doktor_uzmanligi": "",
    "rapor_doktor_brans": "KARDİYOLOJİ",
    "rapor_dr_brans": "KARDİYOLOJİ",
    "recete_ilaclari": [],
    "hasta_tc": "39478351628",
}
rap = kontrol_klopidogrel(avni)
kontrol("AVNİ DİLLİ genel sonuç", rap.sonuc, KontrolSonucu.UYGUN)
y3_durumlar = {s.ad: s.durum.value for s in rap.sartlar
               if s.grup.startswith("Y-3")}
kontrol("Y-3 anjiografik KAH atomu",
        y3_durumlar.get("Anjiografik koroner arter hastalığı"), "var")
kontrol("Y-3 anjio tarihi atomu",
        y3_durumlar.get("Anjiografi tarihi raporda"), "var")
kontrol("Y-3 uzman rapor atomu",
        y3_durumlar.get("Uzman hekim raporu VAR (≤12 ay)"), "var")
kontrol("Y-3 rapor doktor branşı atomu (KARDİYOLOJİ)",
        y3_durumlar.get("Rapor yazan doktor: Kard/İç/Nör/KDC/Acil"), "var")

print()
print(f"TOPLAM: {BASARILI} PASS / {BASARISIZ} FAIL")
sys.exit(1 if BASARISIZ else 0)
