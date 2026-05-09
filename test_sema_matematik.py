# -*- coding: utf-8 -*-
"""Şema matematiği headless test — VEYA grupları doğru sayıyor mu."""
import sys
import json
sys.path.insert(0, '.')

from recete_kontrol import sut_kontrolleri as sk
from aylik_recete_sorgu_gui import AylikReceteSorguGUI as G


def sartlar_dict(rapor):
    return [{'ad': p.ad, 'durum': p.durum.value, 'neden': p.neden,
             'kaynak': p.kaynak, 'grup': p.grup,
             'veya_grubu': p.veya_grubu} for p in rapor.sartlar]


def test_senaryo(ad, ilac_sonuc, beklenen_gerekli=None,
                  beklenen_saglanan=None):
    rapor = sk.kontrol_yoak(ilac_sonuc)
    sartlar = sartlar_dict(rapor)
    gmat = G._sema_grup_matematigi(sartlar)
    print(f"\n── {ad} ──")
    print(f"   Sonuç: {rapor.sonuc.value}")
    print(f"   Toplam: {gmat['saglanan_toplam']} / {gmat['gerekli_toplam']} "
          f"(şart sağlanıyor / gerekli)")
    for g in gmat['gruplar']:
        veya = ' [VEYA]' if g['veya'] else ''
        print(f"     • {g['grup'][:55]:<55} → {g['saglanan']}/{g['gerekli']}"
              f"{veya}")
    if beklenen_gerekli is not None:
        ok = (gmat['gerekli_toplam'] == beklenen_gerekli)
        print(f"   beklenen gerekli={beklenen_gerekli} → "
              f"{'✓' if ok else '✗'}")
    if beklenen_saglanan is not None:
        ok = (gmat['saglanan_toplam'] == beklenen_saglanan)
        print(f"   beklenen saglanan={beklenen_saglanan} → "
              f"{'✓' if ok else '✗'}")
    return gmat


# 1. UYGUN — AF + 78 yaş + SK + varfarin altı SVO
test_senaryo('S1: AF + ≥75 + SK + SVO altı (UYGUN beklenir)', {
    'ilac_adi': 'XARELTO 20 MG',
    'etkin_madde': 'RIVAROKSABAN',
    'rapor_kodu': '04.03',
    'rapor_aciklamalari': [
        'Atriyal fibrilasyon, 78 yaşında. Sağlık kurulu raporu — '
        'kardiyoloji, iç hastalıkları, nöroloji uzmanları onayı. '
        'Varfarin altında iken iskemik inme geçirmiştir.'],
    'recete_teshisleri': ['I48'],
    'hasta_yasi': 78,
    'doktor_uzmanligi': 'KARDİYOLOJİ',
})

# 2. UYGUN_DEGIL — AF + mekanik kapak (kontrendikasyon)
test_senaryo('S2: AF + mekanik kapak (UYGUN_DEGIL beklenir)', {
    'ilac_adi': 'XARELTO 20 MG', 'etkin_madde': 'RIVAROKSABAN',
    'rapor_kodu': '04.03',
    'rapor_aciklamalari': ['Atriyal fibrilasyon. Mekanik mitral kapak. '
                            'Sağlık kurulu raporu kardiyoloji nöroloji '
                            'iç hastalıkları.'],
    'recete_teshisleri': ['I48'],
    'hasta_yasi': 70,
    'doktor_uzmanligi': 'KARDİYOLOJİ',
})

# 3. DVT + tüm şartlar
test_senaryo('S3: DVT + yetişkin + SK + 2ay varfarin + INR 5/3 (UYGUN)', {
    'ilac_adi': 'XARELTO 20 MG', 'etkin_madde': 'RIVAROKSABAN',
    'rapor_kodu': '04.03',
    'rapor_aciklamalari': [
        'Sol bacak DVT. 50 yaşında. Sağlık kurulu raporu — kardiyoloji, '
        'iç hastalıkları, göğüs hastalıkları uzmanları. En az 2 ay '
        'varfarin sonrası INR son 5 ölçümün 3\'ünde 2-3 tutulamadı.'],
    'recete_teshisleri': ['I80'],
    'hasta_yasi': 50,
    'doktor_uzmanligi': 'KARDİYOLOJİ',
})

# 4. Eksik — sadece AF, hiçbir risk faktörü ya da varfarin yok
test_senaryo('S4: AF + risk yok + varfarin yok (kısmen sağlanan)', {
    'ilac_adi': 'XARELTO 20 MG', 'etkin_madde': 'RIVAROKSABAN',
    'rapor_kodu': '04.03',
    'rapor_aciklamalari': ['Atriyal fibrilasyon.'],
    'recete_teshisleri': ['I48'],
    'hasta_yasi': 50,
    'doktor_uzmanligi': 'KARDİYOLOJİ',
})

print('\n✓ Matematik testi tamam')
