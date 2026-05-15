# -*- coding: utf-8 -*-
"""SUT Motor Pilot — Fibrat 4.2.28.B karşılaştırmalı test.

Aynı senaryoyu HEM mevcut `recete_kontrol.sut_kontrolleri.kontrol_fibrat()`
HEM `recete_kontrol.sut_motor.degerlendir(fibrat.json, ...)` çalıştırır,
sonuçları (KontrolSonucu) karşılaştırır.

Hedef: motor verdict'i mevcut kontrolün verdict'ine **bire bir** eşit olsun.
SartSonuc detayları farklılaşabilir (motor henüz "(bilgi)" paralel grupları
üretmiyor) — verdict eşitliği yeterli.
"""
import os
import sys

# UTF-8 çıktı (Windows konsol için)
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recete_kontrol import sut_kontrolleri as sk
from recete_kontrol.sut_motor import degerlendir, kural_yukle

# Mevcut Fibrat akıl testindeki senaryoları yeniden kullan
from test_sut_4_2_28_B_fibrat import SENARYOLAR


KURAL_YOLU = os.path.join(os.path.dirname(__file__),
                           'sut_kurallari', 'fibrat_4_2_28_b.json')


def _kisalt(s: str, n: int = 100) -> str:
    return s[:n] + ('...' if len(s) > n else '')


def _calistir():
    kural = kural_yukle(KURAL_YOLU)
    print(f"=== SUT Motor Pilot — Fibrat 4.2.28.B ===")
    print(f"Kural: {kural['adi']} ({kural['sut_kodu']})")
    print(f"Senaryo sayısı: {len(SENARYOLAR)}\n")

    es = 0  # eşit
    fr = 0  # farklı (motor ≠ mevcut)
    bk = 0  # mevcut beklenenden farklı (mevcut başarısız)
    mk = 0  # motor beklenenden farklı (motor başarısız)

    for s in SENARYOLAR:
        try:
            mevcut = sk.kontrol_fibrat(s['ilac']).sonuc.value
            motor = degerlendir(kural, s['ilac']).sonuc.value
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"✗ HATA [{s['ad']}]: {e}\n")
            fr += 1
            continue

        beklenen = s['beklenen']
        es_mu = (mevcut == motor)
        if es_mu:
            es += 1
        else:
            fr += 1

        durum = "✓" if es_mu else "✗"
        print(f"{durum} [{s['ad']}]")
        print(f"   beklenen={beklenen}  mevcut={mevcut}  motor={motor}")

        if mevcut != beklenen:
            bk += 1
            print(f"   ⚠ MEVCUT beklenenden farklı")
        if motor != beklenen:
            mk += 1
            print(f"   ⚠ MOTOR beklenenden farklı")
        print()

    n = len(SENARYOLAR)
    print("=" * 60)
    print(f"SONUÇ:")
    print(f"  Motor ↔ Mevcut eşitliği:  {es}/{n}  (fark: {fr})")
    print(f"  Mevcut ↔ Beklenen:         {n - bk}/{n}")
    print(f"  Motor  ↔ Beklenen:         {n - mk}/{n}")
    print("=" * 60)
    return fr == 0 and mk == 0


if __name__ == '__main__':
    sys.exit(0 if _calistir() else 1)
