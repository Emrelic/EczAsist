# -*- coding: utf-8 -*-
"""SUT 4.2.15.E — Tikagrelor bağımsız tek-yolak AND-zincir test akıl testleri.

Boolean formül:
  Tikag_UYGUN ⇔ T-1 ∧ T-2 ∧ T-3 ∧ T-4 ∧ (Yol-A ∨ Yol-B)

T-1: NSTEMI ∨ STEMI
T-2: Son 72sa fibrinolitik YOK
T-3: Varfarin tedavisi altında DEĞİL
T-4: EKG_a (STEMI varyantı) ∨ EKG_b (NSTEMI varyantı)
Yol-A: reçete yazan Kard/KDC (raporsuz)
Yol-B: rapor + ≥1 Kard/KDC + reçete Kard/KDC/İç (raporlu 1yıl)
"""
from recete_kontrol.sut_kontrolleri import kontrol_tikagrelor
from recete_kontrol.base_kontrol import KontrolSonucu


def _ozet(rapor):
    return (f'sonuc={rapor.sonuc.value} | '
            f'akis={rapor.detaylar.get("akis_durumu", {})}')


def _rec(rapor_metin, **kwargs):
    base = {
        'ilac_adi': 'BRILINTA 90MG 56 FILM TABLET',
        'etkin_madde': 'TIKAGRELOR',
        'rapor_kodu': '',
        'recete_teshisleri': [],
        'mesaj_metni': rapor_metin,
        'doktor_uzmanligi': 'Kardiyoloji',
        'diger_ilac_adlari': [],
    }
    base.update(kwargs)
    return base


def test_stemi_tam_uygun():
    """STEMI + EKG/troponin + fibrinolitik YOK + varfarin YOK → UYGUN."""
    r = kontrol_tikagrelor(_rec(
        'STEMI tanisi. EKG en az iki ardisik derivasyonda ST yukselmesi. '
        'Troponin pozitif, CK-MB pozitif. Fibrinolitik tedavi uygulanmamistir. '
        'Varfarin tedavisi altinda olmayan hasta.',
        recete_teshisleri=['I21.0'],
    ))
    print(f'[T-STEMI-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN


def test_nstemi_tam_uygun():
    """NSTEMI + persistan göğüs ağrısı + EKG ST depresyonu + troponin poz."""
    r = kontrol_tikagrelor(_rec(
        'AKUT KORONER SENDROMLU HASTA NSTEMI. PERSISTAN GOGUS AGRISI. EKG en '
        'az 2 ardisik derivasyonda 1 mm den derin ST DEPRESYONU. Troponin '
        'pozitif. Fibrinolitik tedavi uygulanmamistir. Varfarin tedavisi '
        'altinda olmayan.',
        recete_teshisleri=['I21.4'],
    ))
    print(f'[T-NSTEMI-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN


def test_varfarin_diger_recete_kontrendike():
    """Diğer reçetede Coumadin → varfarin altında, Tikagrelor kontrendike."""
    r = kontrol_tikagrelor(_rec(
        'STEMI. EKG ST yukselmesi, troponin pozitif. Fibrinolitik uygulanmamistir.',
        recete_teshisleri=['I21.0'],
        diger_ilac_adlari=['COUMADIN 5MG TB'],
    ))
    print(f'[T-VARF-DIGER] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_fibrinolitik_pozitif_kontrendike():
    """72 saat fibrinolitik tedavi var → kontrendike."""
    r = kontrol_tikagrelor(_rec(
        'STEMI. EKG ST yukselmesi, troponin pozitif. Hasta acil serviste '
        'tenekteplaz tedavisi aldi. Varfarin tedavisi altinda olmayan.',
        recete_teshisleri=['I21.0'],
    ))
    print(f'[T-FIBR-VAR] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_aks_yok_kontrendike():
    """NSTEMI/STEMI lafzı yok → T-1 YOK → UYGUN_DEGIL."""
    r = kontrol_tikagrelor(_rec(
        'Anstabil angina hastasi. EKG normal, troponin negatif.',
        recete_teshisleri=['I20.0'],
    ))
    print(f'[T-AKS-YOK] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_ekg_kanit_eksik_supheli():
    """STEMI tanısı var ama EKG/troponin parse zayıf → ŞÜPHELİ veya UYGUN."""
    r = kontrol_tikagrelor(_rec(
        'STEMI tanisi. Hastaneye yatirildi. Fibrinolitik tedavi uygulanmamistir. '
        'Varfarin yok.',
        recete_teshisleri=['I21.0'],
    ))
    print(f'[T-EKG-ZAYIF] {_ozet(r)}')
    # STEMI tanısı + EKG kanıt zayıfsa T-4a STEMI varyantı VAR sayılır
    # (kullanıcı kuralı: STEMI lafzen ST yükselmesi içerir)
    # ama T-4b NSTEMI varyantı için EKG değişiklik gerekiyor → KE
    # alt-OR ≥1 yeterli → T-4 VAR olabilir. Test bekleyişi gevşek.
    assert r.sonuc in (KontrolSonucu.UYGUN, KontrolSonucu.KONTROL_EDILEMEDI)


def test_yol_a_yanlis_brans():
    """Aile hekimi reçetesi raporsuz akış uygun değil → UYGUN_DEGIL veya KE."""
    r = kontrol_tikagrelor(_rec(
        'STEMI. EKG ST yukselmesi, troponin pozitif. Fibrinolitik uygulanmamistir. '
        'Varfarin yok.',
        recete_teshisleri=['I21.0'],
        doktor_uzmanligi='Aile Hekimligi',
    ))
    print(f'[T-YOL-A-WRONG] {_ozet(r)}')
    assert r.sonuc != KontrolSonucu.UYGUN


def test_yol_b_raporlu_uygun():
    """Raporlu akış: rapor + Kard rapor üyesi + İç hast reçete → UYGUN."""
    r = kontrol_tikagrelor(_rec(
        'STEMI. EKG ST yukselmesi, troponin pozitif. Fibrinolitik uygulanmamistir. '
        'Varfarin yok.',
        recete_teshisleri=['I21.0'],
        doktor_uzmanligi='Ic Hastaliklari',
        rapor_kodu='04.04',
        rapor_dr_brans='Kardiyoloji',
    ))
    print(f'[T-YOL-B-RAPORLU] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN


def test_fibrinolitik_typo_fibrinonolitik():
    """Doktor typo'su 'fibrinonolitik' (fazladan 'no') — 360JSQ1 MAHMUT UZUN
    örneği 2026-05-17. Mevcut atom anchor + yakınlık ile typo'yu yakalamalı."""
    r = kontrol_tikagrelor(_rec(
        'Akut koroner sendromlu hastalarda st yukselmesiz miyokard '
        'enfarktusu (NSTEMI) ile acil servise muracaat etmistir. '
        'Tikagrelor baslamadan onceki 72 saat icinde hastaneye yatirilmis '
        've acil tedavide fibrinonolitik tedavi uygulanmamistir. '
        'Hasta varfarin tedavisi altinda degildir. Persistan gogus agrisi '
        'bulunmaktadir ve EKGde en az iki ardisik derivasyonda 1 mmden '
        'derin ST depresyonu mevcuttur. Troponin pozitiftir.',
        recete_teshisleri=['I21.4'],
        doktor_uzmanligi='Kardiyoloji',
    ))
    print(f'[T-FIB-TYPO] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, \
        f'Typo fibrinonolitik UYGUN olmali, oldu: {r.sonuc}'
    fib_atom = next((s for s in r.sartlar
                      if 'fibrinolitik' in s.ad.lower() or
                         '72 saat' in s.ad.lower()), None)
    assert fib_atom and fib_atom.durum.value == 'var', \
        f'Fibrinolitik atomu VAR olmali (typo tolere edilmeli)'


def test_stemi_raporunda_nstemi_yok():
    """STEMI raporunda NSTEMI atomu yanlışlıkla VAR sayılmamalı (mutually exclusive).

    Bug fix (3LXWQW0 SEYIT AHMET GURBUZSAL 2026-05-17): rapor metninde
    'AKUT KORONER SENDROMLU ... STEMI' lafzı geçince NSTEMI atomu da VAR
    sayılıyordu — çünkü atom 'akut koroner sendrom' / 'miyokard enfarkt'
    ibarelerini de NSTEMI varsayıyordu. STEMI ile NSTEMI mutually exclusive
    olmalı.
    """
    r = kontrol_tikagrelor(_rec(
        '24.08.2025 TARIHINDE HASTA ACIL SERVISE BASVURMUS, AKUT KORONER '
        'SENDROMLU HASTA ST YUKSELMELI MIYOKARD ENFARKTUSU (STEMI) OLAN HASTA. '
        'EKG DE EN AZ IKI ARDISIK DERIVASYONDA 1 MM VE UZERI PERSISTAN ST '
        'SEGMENT YUKSELME GOSTERMIS VE TROPONIN / CK-MB POZITIFTIR. (STEMI) '
        'TIKAGRELOR BASLANMADAN ONCEKI 72 SAAT ICINDE HASTANEYE YATIRLMIS, '
        'ACIL TEDAVIDE FIBRINOLITIK TEDAVI UYGULANMAMISTIR. HASTA VARFARIN '
        'TEDAVISI ALTINDA DEGILDIR.',
        recete_teshisleri=['I21.9', 'I10', 'E78.4'],
        doktor_uzmanligi='Kardiyoloji',
    ))
    print(f'[T-STEMI-NSTEMI-EXC] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN
    # NSTEMI atomu YOK olmalı (STEMI varken)
    nstemi_atom = next((s for s in r.sartlar
                         if s.ad == 'NSTEMI (ST yükselmesiz MI)'), None)
    stemi_atom = next((s for s in r.sartlar
                        if s.ad == 'STEMI (ST yükselmeli MI)'), None)
    assert nstemi_atom and nstemi_atom.durum.value == 'yok', \
        f'STEMI varken NSTEMI YOK olmalı, oldu: {nstemi_atom.durum.value if nstemi_atom else "None"}'
    assert stemi_atom and stemi_atom.durum.value == 'var', \
        f'STEMI atomu VAR olmalı'


def test_mehmet_senel_nstemi_gercek():
    """Gerçek üretim senaryosu (NSTEMI + tam SUT lafzı)."""
    r = kontrol_tikagrelor(_rec(
        '02.07.2023 TARIHINDE ACIL SERVISE MURACAT ETMIS, AKUT KORONER '
        'SENDROMLU HASTA (NSTEMI) TIKAGRELOR BASLAMADAN ONCEKI 72 SAAT '
        'ICINDE HASTANEYE YATIRILMIS OLUP ACIL TEDAVIDE FIBRINOLITIK TEDAVI '
        'UYGULANMAMIS HASTA, VARFARIN TEDAVISI ALTINDA OLMAYAN, HASTANIN '
        'TROPONIN DEGERI VE CK-MB DEGERI POZITIF OLAN, PERSISTAN GOGUS '
        'AGRISI BULUNAN VE EKG\'DE EN AZ 2 (IKI) ARDISIK DERIVASYONDA '
        '1 MM\'DEN DERIN ST DEPRESYONU BULUNAN, ST YUKSELMESIZ MIYOKARD '
        'ENFARKTUSLU (NSTEMI) TESHISLI HASTA',
        recete_teshisleri=['I21.4'],
        rapor_dr_brans='Kardiyoloji',
    ))
    print(f'[T-MEHMET-NSTEMI] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN


if __name__ == '__main__':
    testler = [
        test_stemi_tam_uygun,
        test_nstemi_tam_uygun,
        test_varfarin_diger_recete_kontrendike,
        test_fibrinolitik_pozitif_kontrendike,
        test_aks_yok_kontrendike,
        test_ekg_kanit_eksik_supheli,
        test_yol_a_yanlis_brans,
        test_yol_b_raporlu_uygun,
        test_fibrinolitik_typo_fibrinonolitik,
        test_stemi_raporunda_nstemi_yok,
        test_mehmet_senel_nstemi_gercek,
    ]
    basarisiz = []
    for t in testler:
        try:
            t()
        except AssertionError as e:
            basarisiz.append((t.__name__, str(e)))
            print(f'  XX {t.__name__}: {e}')
    if basarisiz:
        print(f'\n{len(basarisiz)}/{len(testler)} BASARISIZ:')
        for ad, hata in basarisiz:
            print(f'  - {ad}: {hata}')
        import sys
        sys.exit(1)
    print(f'\nTumu ({len(testler)}) BASARILI [OK]')
