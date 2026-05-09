# -*- coding: utf-8 -*-
"""SUT 4.2.15.D YOAK akıl testi.

D-1 (AF) ve D-2 (DVT/PE) tüm dallarını + kombi yasağı + kontrendikasyonları
+ istisna gruplarını + sağlık kurulu raporu kontrolünü senaryo bazlı sınar.
"""
import sys
sys.path.insert(0, '.')
from recete_kontrol import sut_kontrolleri as sk
from recete_kontrol.base_kontrol import KontrolSonucu, SartDurumu

basarisiz = []


def test(ad, beklenen, rapor):
    """beklenen = 'uygun' / 'uygun_degil' / 'kontrol_edilemedi'."""
    gercek = rapor.sonuc.value
    durum = "✓" if gercek == beklenen else "✗"
    print(f"{durum} {ad}: beklenen={beklenen}, gerçek={gercek}")
    if gercek != beklenen:
        print(f"   mesaj: {rapor.mesaj}")
        if rapor.sartlar:
            print("   şartlar:")
            for s in rapor.sartlar:
                print(f"     - [{s.durum.value}] {s.ad}: {s.neden}")
    return gercek == beklenen


def yap(ilac_adi='XARELTO 20 MG', etkin='RIVAROKSABAN', rapor_kodu='04.03',
        rapor_aciklamasi='', recete_teshisleri=None, hasta_yasi=None,
        recete_ilaclari=None, diger_ilac_adlari=None,
        diger_etken_maddeler=None):
    return {
        'ilac_adi': ilac_adi,
        'etkin_madde': etkin,
        'rapor_kodu': rapor_kodu,
        'rapor_aciklamalari': [rapor_aciklamasi] if rapor_aciklamasi else [],
        'recete_teshisleri': recete_teshisleri or [],
        'hasta_yasi': hasta_yasi,
        'recete_ilaclari': [{'ad': x} for x in (recete_ilaclari or [])],
        'diger_ilac_adlari': diger_ilac_adlari or [],
        'diger_etken_maddeler': diger_etken_maddeler or [],
        'doktor_uzmanligi': 'AİLE HEKİMLİĞİ',
    }


# ══════════════════════════════════════════════════════════════
# BOŞ METİN / RAPORSUZ SENARYOLARI
# ══════════════════════════════════════════════════════════════

# S01: Boş metin + raporsuz → UYGUN_DEGIL
r = sk.kontrol_yoak(yap(rapor_kodu=''))
if not test('S01: Boş metin + raporsuz', 'uygun_degil', r):
    basarisiz.append('S01')

# S02: Boş metin + rapor kodu var → KONTROL_EDILEMEDI
r = sk.kontrol_yoak(yap(rapor_kodu='04.03'))
if not test('S02: Boş metin + rapor kodu var', 'kontrol_edilemedi', r):
    basarisiz.append('S02')


# ══════════════════════════════════════════════════════════════
# KOMBİ YASAĞI (D-1(4))
# ══════════════════════════════════════════════════════════════

# S03: Aynı reçetede iki YOAK (XARELTO + ELIQUIS) → UYGUN_DEGIL
r = sk.kontrol_yoak(yap(
    ilac_adi='XARELTO 20 MG', etkin='RIVAROKSABAN',
    rapor_kodu='04.03',
    rapor_aciklamasi='Sağlık kurulu raporu — Atriyal fibrilasyon, 78 yaşında, '
                     'kardiyoloji + iç hastalıkları + nöroloji uzman onayı, '
                     'varfarin altında inme geçirdi.',
    diger_ilac_adlari=['ELIQUIS 5 MG']))
if not test('S03: Kombi YOAK yasağı (XARELTO+ELIQUIS)', 'uygun_degil', r):
    basarisiz.append('S03')

# S04: Aynı reçetede aynı YOAK farklı doz (kombi DEĞİL) → UYGUN
r = sk.kontrol_yoak(yap(
    ilac_adi='XARELTO 20 MG', etkin='RIVAROKSABAN',
    rapor_aciklamasi='Atriyal fibrilasyon, 78 yaşında, sağlık kurulu raporu '
                     '(kardiyoloji, iç hastalıkları, nöroloji uzmanları) — '
                     'varfarin altındayken inme geçirdi.',
    diger_ilac_adlari=['XARELTO 15 MG']))
if not test('S04: Aynı YOAK farklı doz — kombi DEĞİL', 'uygun', r):
    basarisiz.append('S04')


# ══════════════════════════════════════════════════════════════
# D-1 (AF) DALI
# ══════════════════════════════════════════════════════════════

# S05: AF + 78 yaş + SK raporu (kard/iç hast/nöroloji) +
#      varfarin altı SVO → UYGUN
r = sk.kontrol_yoak(yap(
    rapor_aciklamasi='Atriyal fibrilasyon tanısı, 78 yaşındadır, '
                     'sağlık kurulu raporu — kardiyoloji + iç hastalıkları '
                     '+ nöroloji uzmanları onaylamıştır. Varfarin tedavisi '
                     'altında iken serebrovasküler olay geçirmiştir.',
    recete_teshisleri=['I48 ATRIYAL FIBRILASYON']))
if not test('S05: AF + risk + SK + varfarin altı SVO', 'uygun', r):
    basarisiz.append('S05')

# S06: AF + 80 yaş + SK + 2 ay varfarin + INR son 5/3 → UYGUN
r = sk.kontrol_yoak(yap(
    hasta_yasi=80,
    rapor_aciklamasi='Non-valvüler atriyal fibrilasyon. Hasta 80 yaşındadır. '
                     'Sağlık kurulu raporu — kardiyoloji + iç hastalıkları '
                     '+ göğüs hastalıkları uzmanları. En az 2 ay süre ile '
                     'varfarin kullanılmış, son 5 INR ölçümünün 4\'ünde 2-3 '
                     'arasında tutulamadı.'))
if not test('S06: AF + ≥75 yaş + SK + 2ay varfarin + INR 5/3', 'uygun', r):
    basarisiz.append('S06')

# S07: AF + DM/HT + SK + varfarin tutulamadı → UYGUN
r = sk.kontrol_yoak(yap(
    hasta_yasi=62,
    rapor_aciklamasi='Atriyal fibrilasyon, diabetes mellitus, hipertansiyon. '
                     'Sağlık kurulu raporu kardiyoloji ve iç hastalıkları ve '
                     'nöroloji uzmanlarınca onaylanmıştır. 2 ay süre ile '
                     'varfarin kullanıldı; INR hedef aralıkta tutulamadı.',
    recete_teshisleri=['I48', 'E11', 'I10']))
if not test('S07: AF + DM+HT + SK + varfarin tutulamadı', 'uygun', r):
    basarisiz.append('S07')

# S08: AF + risk faktörü + SK var ama varfarin/INR/SVO hiç yok → UYGUN_DEGIL
# (Atomik mantık: hiçbir ibare yoksa şart YOK; eski kod KE derdi)
r = sk.kontrol_yoak(yap(
    hasta_yasi=78,
    rapor_aciklamasi='Atriyal fibrilasyon, 78 yaşında. Sağlık kurulu raporu '
                     'kardiyoloji, iç hastalıkları, nöroloji uzmanlarınca.',
    recete_teshisleri=['I48']))
if not test('S08: AF + risk + SK ama varfarin/INR/SVO hiç yok',
            'uygun_degil', r):
    basarisiz.append('S08')

# S09: AF + mekanik kapak (kontrendikasyon) → UYGUN_DEGIL
r = sk.kontrol_yoak(yap(
    hasta_yasi=70,
    rapor_aciklamasi='Atriyal fibrilasyon. Mekanik mitral kapak protezi var. '
                     'Sağlık kurulu raporu — kardiyoloji, iç hastalıkları, '
                     'nöroloji.',
    recete_teshisleri=['I48']))
if not test('S09: AF + mekanik kapak (kontrendikasyon)', 'uygun_degil', r):
    basarisiz.append('S09')

# S10: AF + orta-ciddi mitral darlık → UYGUN_DEGIL
r = sk.kontrol_yoak(yap(
    hasta_yasi=70,
    rapor_aciklamasi='Atriyal fibrilasyon. Romatizmal mitral darlık (ciddi). '
                     'Sağlık kurulu raporu — kardiyoloji, iç hastalıkları, '
                     'nöroloji uzmanları.',
    recete_teshisleri=['I48']))
if not test('S10: AF + ciddi mitral darlık', 'uygun_degil', r):
    basarisiz.append('S10')

# S11: AF + biyoprotez kapak (kontrendikasyon DEĞİL) → UYGUN
r = sk.kontrol_yoak(yap(
    hasta_yasi=78,
    rapor_aciklamasi='Atriyal fibrilasyon, 78 yaşında. Biyoprotez aort kapak '
                     'replasmanı sonrası. Sağlık kurulu raporu — kardiyoloji, '
                     'iç hastalıkları, nöroloji uzmanları. Varfarin altında '
                     'iken iskemik inme geçirmiştir.',
    recete_teshisleri=['I48']))
if not test('S11: AF + biyoprotez kapak (kontrendike DEĞİL)', 'uygun', r):
    basarisiz.append('S11')

# S12: AF + risk + SK YOK (sadece kardiyolog) → UYGUN_DEGIL
r = sk.kontrol_yoak(yap(
    hasta_yasi=80,
    rapor_aciklamasi='Atriyal fibrilasyon, 80 yaşında. Kardiyoloji uzmanı '
                     'tarafından düzenlenmiş uzman hekim raporu. 2 ay '
                     'varfarin sonrası INR tutulamadı.',
    recete_teshisleri=['I48']))
if not test('S12: AF + risk + SK YOK (sadece 1 uzman)', 'uygun_degil', r):
    basarisiz.append('S12')

# S13: AF + SK var ama nöroloji/kardiyoloji yok (3 uzman: iç hast/göğüs/KVC)
#      → UYGUN_DEGIL (zorunlu branş eksik)
r = sk.kontrol_yoak(yap(
    hasta_yasi=80,
    rapor_aciklamasi='Atriyal fibrilasyon, 80 yaşında. Sağlık kurulu raporu '
                     '— iç hastalıkları, göğüs hastalıkları, kalp damar '
                     'cerrahisi uzmanları. 2 ay varfarin sonrası INR '
                     'tutulamadı.',
    recete_teshisleri=['I48']))
if not test('S13: AF + SK ama kard/nöroloji YOK', 'uygun_degil', r):
    basarisiz.append('S13')


# ══════════════════════════════════════════════════════════════
# D-2 (DVT/PE) DALI
# ══════════════════════════════════════════════════════════════

# S14: DVT + 50 yaş + SK + 2 ay varfarin + INR 5/3 → UYGUN
r = sk.kontrol_yoak(yap(
    hasta_yasi=50,
    rapor_aciklamasi='Sol bacak derin ven trombozu. Hasta 50 yaşında. '
                     'Sağlık kurulu raporu — kardiyoloji, iç hastalıkları, '
                     'göğüs hastalıkları uzmanları. En az 2 ay süre ile '
                     'varfarin kullanılmış, son 5 INR ölçümünün 3\'ünde 2-3 '
                     'arası tutulamadı.',
    recete_teshisleri=['I80']))
if not test('S14: DVT + yetişkin + SK + varfarin/INR', 'uygun', r):
    basarisiz.append('S14')

# S15: DVT + yetişkin + SK ama varfarin/istisna hiç yok → UYGUN_DEGIL
# (Atomik mantık: hiçbir ibare yoksa şart YOK)
r = sk.kontrol_yoak(yap(
    hasta_yasi=50,
    rapor_aciklamasi='Akut DVT. 50 yaşında. Sağlık kurulu raporu — '
                     'kardiyoloji, iç hastalıkları, göğüs hastalıkları '
                     'uzmanları.',
    recete_teshisleri=['I80']))
if not test('S15: DVT + SK ama varfarin/istisna YOK', 'uygun_degil', r):
    basarisiz.append('S15')

# S16: PE + tekrarlayan idiopatik (istisna) + SK → UYGUN
r = sk.kontrol_yoak(yap(
    hasta_yasi=55,
    rapor_aciklamasi='Tekrarlayan idiopatik pulmoner emboli. 55 yaşında. '
                     'Sağlık kurulu raporu — kardiyoloji, iç hastalıkları, '
                     'göğüs hastalıkları uzmanları.',
    recete_teshisleri=['I26']))
if not test('S16: PE + idiopatik istisna', 'uygun', r):
    basarisiz.append('S16')

# S17: DVT + homozigot trombofili (istisna) → UYGUN
r = sk.kontrol_yoak(yap(
    hasta_yasi=40,
    rapor_aciklamasi='Derin ven trombozu, homozigot trombofili. 40 yaşında. '
                     'Sağlık kurulu raporu — kardiyoloji, iç hastalıkları, '
                     'göğüs hastalıkları uzmanları.',
    recete_teshisleri=['I80']))
if not test('S17: DVT + homozigot trombofili', 'uygun', r):
    basarisiz.append('S17')

# S18: DVT + aktif kanser + VTE öyküsü (istisna) → UYGUN
r = sk.kontrol_yoak(yap(
    hasta_yasi=65,
    rapor_aciklamasi='Akciğer adenokarsinomu (aktif), metastatik hastalık. '
                     'Daha önce derin ven trombozu öyküsü (geçirilmiş VTE). '
                     'Sağlık kurulu raporu — kardiyoloji, iç hastalıkları, '
                     'göğüs hastalıkları uzmanları.',
    recete_teshisleri=['C34', 'I80']))
if not test('S18: DVT + aktif kanser + VTE', 'uygun', r):
    basarisiz.append('S18')

# S19: DVT + kanser var ama VTE öyküsü YOK → KONTROL_EDILEMEDI
# (sadece "kanser" yetmez, hem VTE hem aktif kanser gerekir)
r = sk.kontrol_yoak(yap(
    hasta_yasi=60,
    rapor_aciklamasi='Akciğer kanseri, metastatik. 60 yaşında. Sağlık kurulu '
                     'raporu — kardiyoloji, iç hastalıkları, göğüs '
                     'hastalıkları.',
    recete_teshisleri=['C34']))
if not test('S19: PE/DVT + kanser ama VTE öyküsü YOK',
            'kontrol_edilemedi', r):
    basarisiz.append('S19')

# S20: DVT + immobil hasta (istisna) → UYGUN
r = sk.kontrol_yoak(yap(
    hasta_yasi=72,
    rapor_aciklamasi='Akut DVT. Hasta sağ hemiplejik ve yatağa bağımlıdır '
                     '(immobil — serebrovasküler olay sekeli). 72 yaşında. '
                     'Sağlık kurulu raporu — kardiyoloji, iç hastalıkları, '
                     'göğüs hastalıkları uzmanları.',
    recete_teshisleri=['I80']))
if not test('S20: DVT + immobil istisna', 'uygun', r):
    basarisiz.append('S20')

# S21: DVT + 12 yaş (pediatrik, yetişkin değil) → UYGUN_DEGIL
r = sk.kontrol_yoak(yap(
    hasta_yasi=12,
    rapor_aciklamasi='Derin ven trombozu. Pediatrik hasta. Sağlık kurulu '
                     'raporu — kardiyoloji, iç hastalıkları, göğüs '
                     'hastalıkları uzmanları. 2 ay varfarin sonrası INR '
                     'tutulamadı.',
    recete_teshisleri=['I80']))
if not test('S21: DVT + pediatrik hasta', 'uygun_degil', r):
    basarisiz.append('S21')


# ══════════════════════════════════════════════════════════════
# ENDİKASYON YOK / KAPSAM DIŞI SENARYOLARI
# ══════════════════════════════════════════════════════════════

# S22: Endikasyon hiç tespit edilemedi → KONTROL_EDILEMEDI
r = sk.kontrol_yoak(yap(
    rapor_aciklamasi='Hasta antikoagülan tedavi gereksinimi nedeniyle '
                     'takipte. Genel sağlık durumu stabil.'))
if not test('S22: Endikasyon yok', 'kontrol_edilemedi', r):
    basarisiz.append('S22')

# S23: Sadece ortopedik profilaksi (D kapsamında DEĞİL) → KE veya UYGUN_DEGIL
# (ortopedik profilaksi 4.2.15.D'de tanımlı değildir, eski algoritma yanlış
#  UYGUN diyordu)
r = sk.kontrol_yoak(yap(
    rapor_aciklamasi='Total kalça artroplastisi sonrası tromboprofilaksi. '
                     'Yeni protez yerleştirildi.'))
# Kabul kriteri: UYGUN olmamalı (kapsam dışı)
print(f"S23: Ortopedik (D kapsamı dışı) — sonuç: {r.sonuc.value} "
      f"({r.mesaj[:80]})")
if r.sonuc == KontrolSonucu.UYGUN:
    print("✗ S23 BAŞARISIZ — ortopedik profilaksi 4.2.15.D'de yok!")
    basarisiz.append('S23')
else:
    print('✓ S23: Ortopedik artık UYGUN denmiyor')


# ══════════════════════════════════════════════════════════════
# SONUÇ
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
toplam = 23
basarili = toplam - len(basarisiz)
print(f'SONUÇ: {basarili}/{toplam} senaryo başarılı')
if basarisiz:
    print(f'BAŞARISIZ: {", ".join(basarisiz)}')
    sys.exit(1)
print('Tüm akıl testleri OK ✓')
