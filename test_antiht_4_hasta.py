# -*- coding: utf-8 -*-
"""4 hastanın antihipertansif kontrol doğrulaması (2026-05-23).

Test edilen vakalar:
  1. TEVRAT MORKOÇ — KAPRIL + AYRA PLUS aynı reçetede → TIBBEN_UYGUN_DEGIL
  2. HÜSEYİN ZİREK — COVERAM tek başına → UYGUN (Türkçe karakter bug fix)
  3. DURSUN ESA — COVERAM tek başına → UYGUN (aynı bug fix)
  4. UFUK TAPAN — ENAPRIL tek başına → UYGUN (diger_etken_maddeler boş; Bug B)

Çalıştır: python test_antiht_4_hasta.py
"""
import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recete_kontrol.base_kontrol import KontrolSonucu
from recete_kontrol.sut_motor.uyumluluk import (
    kontrol_mono_antihipertansif_motor,
    kontrol_kombi_antiht_arbdis_motor,
)


def vaka(ad, ilac_sonuc, fn, beklenen):
    rapor = fn(ilac_sonuc)
    sonuc = rapor.sonuc
    ok = sonuc == beklenen
    isaret = "✓" if ok else "✗"
    print(f"{isaret} {ad}")
    print(f"   Beklenen: {beklenen.name}")
    print(f"   Gerçek  : {sonuc.name}")
    print(f"   Mesaj   : {rapor.mesaj}")
    if not ok:
        print(f"   ŞARTLAR :")
        for s in rapor.sartlar or []:
            print(f"     - [{s.durum.name:18}] {s.ad}: {s.neden}")
    return ok


print("=" * 70)
print("ANTİHT 4 HASTA DOĞRULAMA — Bug A (TR karakter) + Bug B (rec_no) +")
print("                          TIBBEN UYGUN DEĞİL etiketi")
print("=" * 70)

sonuclar = []

# 1. TEVRAT MORKOÇ — KAPRIL + AYRA PLUS aynı reçetede → TIBBEN_UYGUN_DEGIL
sonuclar.append(vaka(
    "1. TEVRAT MORKOÇ — KAPRIL + AYRA PLUS aynı reçetede (ACE+ARB klinik kontrendikasyon)",
    {
        'ilac_adi': 'KAPRIL 25MG 48 TABLET',
        'etkin_madde': 'KAPTOPRİL',
        'atc_kodu': 'C09AA01',
        'rapor_kodu': '',
        'doktor_uzmanligi': 'Kardiyoloji',
        'diger_etken_maddeler': ['KANDESARTAN VE DİÜRETİKLER'],
        'diger_ilac_adlari': ['AYRA PLUS 16MG/12.5MG 28 TABLET'],
        'recete_teshisleri': ['I10 ESANSIYEL (PRIMER) HIPERTANSIYON'],
    },
    kontrol_mono_antihipertansif_motor,
    KontrolSonucu.TIBBEN_UYGUN_DEGIL,
))

# 2. HÜSEYİN ZİREK — COVERAM tek başına → UYGUN
sonuclar.append(vaka(
    "2. HÜSEYİN ZİREK — COVERAM tek başına (PERİNDOPRİL+AMLODİPİN Türkçe karakter)",
    {
        'ilac_adi': 'COVERAM 10MG+5MG 30 FİLM TABLET',
        'etkin_madde': 'PERİNDOPRİL VE AMLODİPİN',
        'atc_kodu': 'C09BB04',
        'rapor_kodu': '',
        'doktor_uzmanligi': 'İç Hastalıkları (Ana Branş), Aile Hekimliği Uzmanı',
        'diger_etken_maddeler': [],
        'diger_ilac_adlari': [],
        'recete_teshisleri': ['I10 ESANSIYEL (PRIMER) HIPERTANSIYON'],
    },
    kontrol_kombi_antiht_arbdis_motor,
    KontrolSonucu.UYGUN,
))

# 3. DURSUN ESA — COVERAM tek başına → UYGUN
sonuclar.append(vaka(
    "3. DURSUN ESA — COVERAM 10/10MG tek başına",
    {
        'ilac_adi': 'COVERAM 10MG+10MG 30 FİLM TABLET',
        'etkin_madde': 'PERİNDOPRİL VE AMLODİPİN',
        'atc_kodu': 'C09BB04',
        'rapor_kodu': '04.02',
        'doktor_uzmanligi': 'Aile Hekimliği Uzmanı',
        'diger_etken_maddeler': [],
        'diger_ilac_adlari': [],
        'recete_teshisleri': ['I10 ESANSIYEL (PRIMER) HIPERTANSIYON'],
    },
    kontrol_kombi_antiht_arbdis_motor,
    KontrolSonucu.UYGUN,
))

# 4. UFUK TAPAN — ENAPRIL tek başına → UYGUN
sonuclar.append(vaka(
    "4. UFUK TAPAN — ENAPRIL tek başına (Bug B: rec_no=None gruplama düzeltildi)",
    {
        'ilac_adi': 'ENAPRIL 5MG 20 TABLET',
        'etkin_madde': 'ENALAPRİL',
        'atc_kodu': 'C09AA02',
        'rapor_kodu': '04.05',
        'doktor_uzmanligi': 'Aile Hekimliği Uzmanı',
        'diger_etken_maddeler': [],
        'diger_ilac_adlari': [],
        'recete_teshisleri': ['I10 ESANSIYEL (PRIMER) HIPERTANSIYON'],
    },
    kontrol_mono_antihipertansif_motor,
    KontrolSonucu.UYGUN,
))

# Regresyon: ACE+ARB DOĞRU tetiklenmeye devam etmeli (Bug A normalize'dan sonra
# Türkçe karakter de eşleşsin diye)
sonuclar.append(vaka(
    "REGRESYON: ENALAPRİL (Türkçe İ) + LOSARTAN aynı reçetede → TIBBEN_UYGUN_DEGIL",
    {
        'ilac_adi': 'RENİTEC 20MG 28 TABLET',
        'etkin_madde': 'ENALAPRİL',  # Türkçe İ
        'atc_kodu': 'C09AA02',
        'rapor_kodu': '',
        'doktor_uzmanligi': 'Aile Hekimliği Uzmanı',
        'diger_etken_maddeler': ['LOSARTAN POTASYUM'],
        'diger_ilac_adlari': ['COSAAR 50MG 28 TABLET'],
        'recete_teshisleri': ['I10'],
    },
    kontrol_mono_antihipertansif_motor,
    KontrolSonucu.TIBBEN_UYGUN_DEGIL,
))

print()
print("=" * 70)
basari = sum(sonuclar)
toplam = len(sonuclar)
print(f"SONUÇ: {basari}/{toplam} test başarılı")
print("=" * 70)
sys.exit(0 if basari == toplam else 1)
