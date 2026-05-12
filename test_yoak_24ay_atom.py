"""SUT 4.2.15.D-1(2) son cumle - 24 ay tamamlanmis atomu testi.

_yoak_atom_f1_24ay_doldu fonksiyonunun davranisi:
- hasta_yoak_ilk_recete_tarihi + 24 takvim ayi <= recete_tarihi -> VAR
- < 24 ay -> YOK
- alan eksik / parse fail -> KONTROL_EDILEMEDI

Cikti ASCII (Windows cp1254 uyumlu).
"""
import sys
import os
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from recete_kontrol.sut_kontrolleri import (
    _yoak_atom_f1_24ay_doldu, SartDurumu)
from datetime import datetime

basari = 0
toplam = 0

def kontrol(ad, beklenen, ilac_sonuc):
    global basari, toplam
    toplam += 1
    durum, neden = _yoak_atom_f1_24ay_doldu(ilac_sonuc)
    if durum == beklenen:
        basari += 1
        print(f"[OK] {ad}: durum={durum.name}")
        print(f"     neden: {neden}")
    else:
        print(f"[FAIL] {ad}: beklenen={beklenen.name}, gercek={durum.name}")
        print(f"       neden: {neden}")

print("=" * 60)
print("F1 atomu (24 ay tamamlanmis) testleri")
print("=" * 60)

# T1: 37 ay gecmis -> VAR
kontrol(
    "T1 ilk=2023-04-01, recete=2026-05-05 -> 37 ay VAR",
    SartDurumu.VAR,
    {"hasta_yoak_ilk_recete_tarihi": "2023-04-01",
     "recete_tarihi": "05.05.2026"})

# T2: 9 ay -> YOK
kontrol(
    "T2 ilk=2025-08-01, recete=2026-05-05 -> 9 ay YOK",
    SartDurumu.YOK,
    {"hasta_yoak_ilk_recete_tarihi": "2025-08-01",
     "recete_tarihi": "05.05.2026"})

# T3: ilk tarih yok -> KE
kontrol(
    "T3 ilk=None -> KE",
    SartDurumu.KONTROL_EDILEMEDI,
    {"hasta_yoak_ilk_recete_tarihi": None,
     "recete_tarihi": "05.05.2026"})

# T4: recete tarihi yok -> KE
kontrol(
    "T4 recete=None -> KE",
    SartDurumu.KONTROL_EDILEMEDI,
    {"hasta_yoak_ilk_recete_tarihi": "2023-04-01",
     "recete_tarihi": None})

# T5: parse fail -> KE
kontrol(
    "T5 garbage tarih -> KE",
    SartDurumu.KONTROL_EDILEMEDI,
    {"hasta_yoak_ilk_recete_tarihi": "garbage-tarih",
     "recete_tarihi": "05.05.2026"})

# T6: tam 24 ay -> VAR
kontrol(
    "T6 ilk=2024-05-05, recete=2026-05-05 -> tam 24 ay VAR",
    SartDurumu.VAR,
    {"hasta_yoak_ilk_recete_tarihi": "2024-05-05",
     "recete_tarihi": "05.05.2026"})

# T7: 24 ay - 1 gun -> YOK (sinir altı)
kontrol(
    "T7 ilk=2024-05-06, recete=2026-05-05 -> 23 ay 29 gun YOK",
    SartDurumu.YOK,
    {"hasta_yoak_ilk_recete_tarihi": "2024-05-06",
     "recete_tarihi": "05.05.2026"})

# T8: datetime objesi -> VAR
kontrol(
    "T8 datetime obj ilk=2023-01-01, recete=2026-05-05 -> 40 ay VAR",
    SartDurumu.VAR,
    {"hasta_yoak_ilk_recete_tarihi": datetime(2023, 1, 1),
     "recete_tarihi": datetime(2026, 5, 5)})

# T9: 24 ay sonrasi ama ayni ay, gun sonrasi -> VAR
kontrol(
    "T9 ilk=2024-05-05, recete=2026-05-10 -> 24 ay 5 gun VAR",
    SartDurumu.VAR,
    {"hasta_yoak_ilk_recete_tarihi": "2024-05-05",
     "recete_tarihi": "10.05.2026"})

# T10: SAYIME HERGUL pilot (rapor ekleme=02/01/2026)
# Diyelim ki en eski reçetesi 2024-Subat ya da daha onceden:
kontrol(
    "T10 SAYIME-pilot ilk=2023-06-15, recete=05.05.2026 -> 34 ay VAR",
    SartDurumu.VAR,
    {"hasta_yoak_ilk_recete_tarihi": "2023-06-15",
     "recete_tarihi": "05.05.2026"})

# T11: SAYIME-yeni hasta varsayim (ilk=2026-Subat) -> YOK
kontrol(
    "T11 yeni hasta ilk=2026-02-01, recete=05.05.2026 -> 3 ay YOK",
    SartDurumu.YOK,
    {"hasta_yoak_ilk_recete_tarihi": "2026-02-01",
     "recete_tarihi": "05.05.2026"})

print()
print("=" * 60)
print(f"Sonuc: {basari}/{toplam} test gecti")
print("=" * 60)
sys.exit(0 if basari == toplam else 1)
