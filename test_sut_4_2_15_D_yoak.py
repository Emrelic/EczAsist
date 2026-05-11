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
    rapor_aciklamasi='Non-valvüler atriyal fibrilasyon, 78 yaşında, sağlık '
                     'kurulu raporu (kardiyoloji, iç hastalıkları, nöroloji '
                     'uzmanları) — varfarin altındayken inme geçirdi.',
    diger_ilac_adlari=['XARELTO 15 MG']))
if not test('S04: Aynı YOAK farklı doz — kombi DEĞİL', 'uygun', r):
    basarisiz.append('S04')


# ══════════════════════════════════════════════════════════════
# D-1 (AF) DALI
# ══════════════════════════════════════════════════════════════

# S05: AF + 78 yaş + SK raporu (kard/iç hast/nöroloji) +
#      varfarin altı SVO → UYGUN
r = sk.kontrol_yoak(yap(
    rapor_aciklamasi='Non-valvüler atriyal fibrilasyon tanısı, 78 yaşındadır, '
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
                     'varfarin kullanılmış; birer hafta arayla yapılan son 5 '
                     'INR ölçümünün 4\'ünde INR 2-3 arasında tutulamadı, '
                     'varfarin kesilerek YOAK tedavisine geçildi.'))
if not test('S06: AF + ≥75 yaş + SK + 2ay varfarin + INR 5/3', 'uygun', r):
    basarisiz.append('S06')

# S07: AF + DM/HT + SK + varfarin tutulamadı → UYGUN
r = sk.kontrol_yoak(yap(
    hasta_yasi=62,
    rapor_aciklamasi='Non-valvüler atriyal fibrilasyon, diabetes mellitus, '
                     'hipertansiyon. Sağlık kurulu raporu kardiyoloji ve '
                     'iç hastalıkları ve nöroloji uzmanlarınca onaylanmıştır. '
                     '2 ay süre ile varfarin kullanıldı, birer hafta arayla '
                     'son 5 INR ölçümünün 3\'ünde INR 2-3 hedef aralıkta '
                     'tutulamadı; varfarin kesilerek YOAK tedavisine geçildi.',
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
    rapor_aciklamasi='Non-valvüler atriyal fibrilasyon, 78 yaşında. '
                     'Biyoprotez aort kapak replasmanı sonrası. Sağlık kurulu '
                     'raporu — kardiyoloji, iç hastalıkları, nöroloji '
                     'uzmanları. Varfarin altında iken iskemik inme '
                     'geçirmiştir.',
    recete_teshisleri=['I48']))
if not test('S11: AF + biyoprotez kapak (kontrendike DEĞİL)', 'uygun', r):
    basarisiz.append('S11')

# S12: AF + SK metni yetersiz + varfarin chain eksik → KONTROL_EDILEMEDI
# Not: rapor_kodu='' Medula otoritesi devre dışı. SK lafzen yok (uzman hekim
# raporu), 24 ay sonrası F yolu açık (aile hekimi) ama varfarin chain (Da2/Da6
# parser-zayıf) eksik → varfarin yolu KE → genel ŞÜPHELİ (manuel doğrulama).
r = sk.kontrol_yoak(yap(
    rapor_kodu='',
    hasta_yasi=80,
    rapor_aciklamasi='Non-valvüler atriyal fibrilasyon, 80 yaşında. '
                     'Kardiyoloji uzmanı tarafından düzenlenmiş uzman hekim '
                     'raporu. 2 ay varfarin sonrası INR tutulamadı.',
    recete_teshisleri=['I48']))
if not test('S12: AF + SK metni yetersiz + varfarin chain eksik',
            'kontrol_edilemedi', r):
    basarisiz.append('S12')

# S13: AF + SK var ama kard/nöro YOK + varfarin chain eksik → KONTROL_EDILEMEDI
# Not: D-1(2) ilk 24 ay kard/nöro zorunlu yok. F yolu (24 ay sonrası) açık
# ama varfarin chain (Da2/Da6) lafzen eksik → varfarin yolu KE.
r = sk.kontrol_yoak(yap(
    rapor_kodu='',
    hasta_yasi=80,
    rapor_aciklamasi='Non-valvüler atriyal fibrilasyon, 80 yaşında. Sağlık '
                     'kurulu raporu — iç hastalıkları, göğüs hastalıkları, '
                     'kalp damar cerrahisi uzmanları. 2 ay varfarin sonrası '
                     'INR tutulamadı.',
    recete_teshisleri=['I48']))
if not test('S13: AF + SK kard/nöro eksik + varfarin chain eksik',
            'kontrol_edilemedi', r):
    basarisiz.append('S13')


# ══════════════════════════════════════════════════════════════
# D-2 (DVT/PE) DALI
# ══════════════════════════════════════════════════════════════

# S14: DVT + 50 yaş + SK + 2 ay varfarin + INR 5/3 → UYGUN
# Not: 6 atom AND zinciri (mevzuat tam) — haftalık ölçüm + varfarin kesildi
# ibareleri de gerekli, yoksa ŞÜPHELİ olur.
r = sk.kontrol_yoak(yap(
    hasta_yasi=50,
    rapor_aciklamasi='Sol bacak derin ven trombozu. Hasta 50 yaşında. '
                     'Sağlık kurulu raporu — kardiyoloji, iç hastalıkları, '
                     'göğüs hastalıkları uzmanları. En az 2 ay süre ile '
                     'varfarin kullanılmış, birer hafta arayla ölçümler '
                     'yapılmış, son 5 INR ölçümünün 3\'ünde 2-3 arası '
                     'tutulamadı, varfarin kesilerek yeni tedaviye geçildi.',
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
# EK-4/F MADDE 53–54: ORTOPEDİ PROFİLAKSİ YOLU (yeni 2026-05-11)
# ══════════════════════════════════════════════════════════════
# Dispatcher: etken madde = rivaroksaban/dabigatran + doktor branşı
#             ortopedi → _yoak_ek4f_kontrol yoluna düşer.

def yap_ek4f(ilac_adi='XARELTO 10 MG', etkin='RIVAROKSABAN',
             rapor_kodu='04.04',
             rapor_aciklamasi='', doktor='ORTOPEDİ VE TRAVMATOLOJİ',
             kutu_sayisi=1):
    return {
        'ilac_adi': ilac_adi,
        'etkin_madde': etkin,
        'rapor_kodu': rapor_kodu,
        'rapor_aciklamalari': [rapor_aciklamasi] if rapor_aciklamasi else [],
        'recete_teshisleri': [],
        'hasta_yasi': 65,
        'recete_ilaclari': [],
        'diger_ilac_adlari': [],
        'diger_etken_maddeler': [],
        'doktor_uzmanligi': doktor,
        'kutu_sayisi': kutu_sayisi,
    }


# S24: Rivaroksaban + diz total eklem replasmanı + 1 kutu + ortopedi → UYGUN
r = sk.kontrol_yoak(yap_ek4f(
    rapor_aciklamasi='Elektif total diz replasmanı sonrası DVT profilaksisi. '
                     'Hasta 65 yaşında, ortopedi sağlık kurulu raporu.',
    kutu_sayisi=1))
if not test('S24: EK-4/F Riva + diz + 1 kutu + ortopedi', 'uygun', r):
    basarisiz.append('S24')

# S25: Rivaroksaban + kalça + 3 kutu + ortopedi → UYGUN
r = sk.kontrol_yoak(yap_ek4f(
    rapor_aciklamasi='Elektif total kalça replasmanı sonrası DVT profilaksisi. '
                     'Hasta 72 yaşında. Ortopedi uzmanı raporu.',
    kutu_sayisi=3))
if not test('S25: EK-4/F Riva + kalça + 3 kutu + ortopedi', 'uygun', r):
    basarisiz.append('S25')

# S26: Rivaroksaban + diz + 5 kutu (limit aşımı, max 1) → UYGUN_DEGIL
r = sk.kontrol_yoak(yap_ek4f(
    rapor_aciklamasi='Elektif total diz replasmanı sonrası DVT profilaksisi. '
                     'Ortopedi raporu.',
    kutu_sayisi=5))
if not test('S26: EK-4/F Riva + diz + 5 kutu (limit aşımı)',
            'uygun_degil', r):
    basarisiz.append('S26')

# S27: Rivaroksaban + kalça + 4 kutu (limit aşımı, max 3) → UYGUN_DEGIL
r = sk.kontrol_yoak(yap_ek4f(
    rapor_aciklamasi='Elektif total kalça replasmanı sonrası DVT profilaksisi. '
                     'Ortopedi uzman raporu.',
    kutu_sayisi=4))
if not test('S27: EK-4/F Riva + kalça + 4 kutu (limit aşımı)',
            'uygun_degil', r):
    basarisiz.append('S27')

# S28: Dabigatran + kalça + 2 kutu @ DDD (2 cap/gün) = 60 gün → UYGUN_DEGIL
# SUT EK-4/F M.53: kalça için en fazla 35 gün. 2 kutu × 60 cap / 2 = 60 gün > 35
r = sk.kontrol_yoak(yap_ek4f(
    ilac_adi='PRADAXA 110 MG', etkin='DABIGATRAN ETEKSILAT',
    rapor_aciklamasi='Elektif total kalça replasmanı (THA) sonrası 35 günlük '
                     'DVT profilaksisi. Ortopedi sağlık kurulu raporu.',
    kutu_sayisi=2))
if not test('S28: EK-4/F Dab + kalça + 2 kutu (60 gün > 35 SUT limiti)',
            'uygun_degil', r):
    basarisiz.append('S28')

# S28b: Dabigatran + kalça + 1 kutu @ DDD = 30 gün → UYGUN (≤35)
r = sk.kontrol_yoak(yap_ek4f(
    ilac_adi='PRADAXA 110 MG', etkin='DABIGATRAN ETEKSILAT',
    rapor_aciklamasi='Elektif total kalça replasmanı (THA) sonrası 30 günlük '
                     'DVT profilaksisi. Ortopedi sağlık kurulu raporu.',
    kutu_sayisi=1))
if not test('S28b: EK-4/F Dab + kalça + 1 kutu (30 gün ≤35 SUT OK)',
            'uygun', r):
    basarisiz.append('S28b')

# S29: Apiksaban + ortopedi → D-2 fallback (kapsam dışı, rapor metni
#      D-2 için yetersiz) → KE veya UYGUN_DEGIL (UYGUN olmamalı)
r = sk.kontrol_yoak(yap_ek4f(
    ilac_adi='ELIQUIS 5 MG', etkin='APIKSABAN',
    rapor_aciklamasi='Elektif total diz replasmanı sonrası DVT profilaksisi. '
                     'Ortopedi raporu.',
    kutu_sayisi=1))
print(f"S29: Apiksaban + ortopedi (D-2 fallback) — sonuç: {r.sonuc.value}")
if r.sonuc == KontrolSonucu.UYGUN:
    print("✗ S29 BAŞARISIZ — apiksaban EK-4/F kapsamı dışı, UYGUN olmamalı!")
    basarisiz.append('S29')
else:
    print('✓ S29: Apiksaban EK-4/F kapsamı dışı, D-2 fallback')

# S30: Rivaroksaban + ortopedi + diz/kalça sessiz → ŞÜPHELİ
r = sk.kontrol_yoak(yap_ek4f(
    rapor_aciklamasi='Ortopedik cerrahi sonrası tromboprofilaksi gerekiyor. '
                     'Ortopedi raporu.',
    kutu_sayisi=1))
if not test('S30: EK-4/F Riva + lokalizasyon sessiz (ŞÜPHELİ)',
            'kontrol_edilemedi', r):
    basarisiz.append('S30')


# ══════════════════════════════════════════════════════════════
# SONUÇ
# ══════════════════════════════════════════════════════════════

print('\n' + '=' * 60)
toplam = 30
basarili = toplam - len(basarisiz)
print(f'SONUÇ: {basarili}/{toplam} senaryo başarılı')
if basarisiz:
    print(f'BAŞARISIZ: {", ".join(basarisiz)}')
    sys.exit(1)
print('Tüm akıl testleri OK ✓')
