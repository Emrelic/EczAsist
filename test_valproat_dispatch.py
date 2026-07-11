# -*- coding: utf-8 -*-
"""Valproat SUT 4.2.2(7) dispatch entegrasyon testi (2026-07-06).

Kapsam:
  1. valproat_4_2_2_7 modül akıl testi (12 senaryo — 7 gerçek vaka tipi dahil)
  2. antiepileptik_kontrol_4_2_25 → valproat delege (önce: 'kapsam dışı' ATLANDI)
  3. kontrol_psikiyatri → valproat delege (önce: rapor kodu varsa körlemesine UYGUN)
  4. Regresyon: lamotrijin bipolar ATLANDI + gabapentin nöropatik ATLANDI korunur

Çalıştır: python test_valproat_dispatch.py
"""
import sys

from recete_kontrol.base_kontrol import KontrolSonucu
from recete_kontrol.valproat_4_2_2_7 import akil_testi_calistir
from recete_kontrol.antiepileptik_4_2_25 import antiepileptik_kontrol_4_2_25
from recete_kontrol.sut_kontrolleri import kontrol_psikiyatri

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
    print("1) valproat_4_2_2_7 modül akıl testi")
    print("=" * 70)
    SONUCLAR.append(akil_testi_calistir())

    print()
    print("=" * 70)
    print("2) antiepileptik_kontrol_4_2_25 → valproat delege")
    print("=" * 70)
    kontrol("DEPAKIN CHRONO + topiramat idame raporu → UYGUN (epilepsi)",
            antiepileptik_kontrol_4_2_25({
                'ilac_adi': 'CONVULEX 50MG/ML 100ML PEDIATRIK ŞURUP',
                'etkin_madde': 'VALPROİK ASİT', 'atc_kodu': 'N03AG01',
                'rapor_kodu': '6',
                'rapor_aciklamalari': ['idame tedavi TOPIRAMAT Ağızdan katı '
                                       '1 Gün 1 400 Miligram']}),
            KontrolSonucu.UYGUN)
    kontrol("DEPALEX XR + yaş/kilo raporu, endikasyon sessiz → ŞARTLI UYGUN",
            antiepileptik_kontrol_4_2_25({
                'ilac_adi': 'DEPALEX XR 500MG UZUN ETKILI 30 FİLM TABLET',
                'etkin_madde': 'VALPROİK ASİT', 'atc_kodu': 'N03AG01',
                'rapor_kodu': '9', 'yas': '51',
                'rapor_aciklamalari': ['HASTA 12 YAŞINDAN BÜYÜK (51 YAŞINDA) '
                                       'VE 50 KİLODAN FAZLADIR (85 KG)']}),
            KontrolSonucu.SARTLI_UYGUN)
    kontrol("DEPAKIN raporsuz sessiz şurup → ŞARTLI UYGUN",
            antiepileptik_kontrol_4_2_25({
                'ilac_adi': 'DEPAKIN 57.64MG/ML 150ML ŞURUP',
                'etkin_madde': 'VALPROİK ASİT', 'atc_kodu': 'N03AG01'}),
            KontrolSonucu.SARTLI_UYGUN)
    kontrol("Valproat bipolar + aile hekimi raporsuz → UYGUN DEĞİL",
            antiepileptik_kontrol_4_2_25({
                'ilac_adi': 'DEPAKIN CHRONO BT 500MG', 'yas': '30',
                'etkin_madde': 'VALPROIK ASIT', 'brans': 'Aile Hekimliği',
                'recete_teshisleri': ['F31 BIPOLAR BOZUKLUK']}),
            KontrolSonucu.UYGUN_DEGIL)
    # Regresyon — mevcut delege davranışları bozulmamalı
    kontrol("Lamotrijin bipolar → ATLANDI (4.2.2 psikiyatri, regresyon)",
            antiepileptik_kontrol_4_2_25({
                'etkin_madde': 'LAMOTRIJIN',
                'recete_teshisleri': ['F31 BIPOLAR']}),
            KontrolSonucu.ATLANDI),
    kontrol("Parasetamol → ATLANDI (kapsam dışı, regresyon)",
            antiepileptik_kontrol_4_2_25({'etkin_madde': 'PARASETAMOL'}),
            KontrolSonucu.ATLANDI)

    print()
    print("=" * 70)
    print("3) kontrol_psikiyatri → valproat delege")
    print("=" * 70)
    kontrol("ELİF İREM tipi: DEPAKIN CHRONO + antipsikotik kokteyl raporu → "
            "ŞARTLI UYGUN (eski dal körlemesine UYGUN derdi)",
            kontrol_psikiyatri({
                'ilac_adi': 'DEPAKIN CHRONO BT 500MG 30 TABLET',
                'etkin_madde': 'VALPROİK ASİT', 'rapor_kodu': '11',
                'yas': '30',
                'rapor_aciklamalari': [
                    'VALPROIK ASIT+SODYUM VALPROAT 1500 Miligram KETIAPIN '
                    'FUMARAT 1200 Miligram HALOPERIDOL 15 Miligram '
                    'RISPERIDON 6 Miligram']}),
            KontrolSonucu.SARTLI_UYGUN)
    kontrol("EBRU DOĞAN tipi: '1 yıl geçerlidir' raporu → ŞARTLI UYGUN",
            kontrol_psikiyatri({
                'ilac_adi': 'DEPAKIN CHRONO BT 500MG 30 TABLET',
                'etkin_madde': 'VALPROİK ASİT', 'rapor_kodu': '5',
                'yas': '45',
                'rapor_aciklamalari': ['1 yıl süre ile geçerlidir.']}),
            KontrolSonucu.SARTLI_UYGUN)
    kontrol("Bipolar F31 + reçeteci psikiyatri raporsuz → UYGUN",
            kontrol_psikiyatri({
                'ilac_adi': 'DEPAKIN 500MG', 'etkin_madde': 'VALPROIK ASIT',
                'doktor_uzmanligi': 'Psikiyatri',
                'recete_teshisleri': ['F31.1 BIPOLAR BOZUKLUK']}),
            KontrolSonucu.UYGUN)
    kontrol("DEPALEX ticari fallback (etken boş) → valproat modülü yakalar",
            kontrol_psikiyatri({
                'ilac_adi': 'DEPALEX XR 500MG UZUN ETKILI', 'yas': '51',
                'etkin_madde': '',
                'recete_teshisleri': ['G40.9 EPILEPSI']}),
            KontrolSonucu.UYGUN)

    print()
    print("=" * 70)
    toplam = len(SONUCLAR)
    gecen = sum(1 for x in SONUCLAR if x)
    print(f"GENEL SONUÇ: {gecen}/{toplam} kontrol geçti")
    return gecen == toplam


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
