# -*- coding: utf-8 -*-
"""SUT 4.2.15.Ç — Prasugrel bağımsız 2-yolak kontrol akıl testleri.

Boolean formül:
  Prasu_UYGUN ⇔ (P-1 ∨ P-2) ∧ (Yol-A ∨ Yol-B)

P-1: yaş<75 ∧ kilo>60 ∧ SVO_yok ∧ PKG ∧ (NSTEMI ∨ STEMI)
P-2: Klopidogrel altında stent trombozu ∧ (NSTEMI ∨ STEMI)
Yol-A: reçete yazan Kard/KDC (raporsuz)
Yol-B: rapor + ≥1 Kard/KDC + reçete Kard/KDC/İç (raporlu 1yıl)
"""
from recete_kontrol.sut_kontrolleri import kontrol_prasugrel
from recete_kontrol.base_kontrol import KontrolSonucu


def _ozet(rapor):
    return (f'sonuç={rapor.sonuc.value} | '
            f'yolak={rapor.detaylar.get("yolak_durumlari", {})}')


def _rec(rapor_metin, **kwargs):
    base = {
        'ilac_adi': 'EFFIENT 10MG 28 FILM TABLET',
        'etkin_madde': 'PRASUGREL',
        'rapor_kodu': '',
        'recete_teshisleri': [],
        'mesaj_metni': rapor_metin,
        'doktor_uzmanligi': 'Kardiyoloji',
        'hasta_yasi': 60,
        'hasta_kilosu': 80,
    }
    base.update(kwargs)
    return base


def test_p1_standart_uygun():
    """P-1 standart yol tam: 60 yaş, 80 kg, SVO yok, NSTEMI+PKG → UYGUN."""
    r = kontrol_prasugrel(_rec(
        'AKUT KORONER SENDROMLU HASTA. NSTEMI tanisi. PERKUTAN KORONER '
        'GIRISIM KARARI ALINDI. SEREBROVASKULER OLAY OYKUSU OLMAYAN HASTA.',
        recete_teshisleri=['I21.4'],
    ))
    print(f'[P1-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, \
        f'P-1 tam tam, beklenti UYGUN; gerçek={r.sonuc}'


def test_p1_yas_75_kontrendike():
    """Hasta yaş 75 (sınır): Prasugrel kontrendike → UYGUN_DEGIL."""
    r = kontrol_prasugrel(_rec(
        'NSTEMI tanisi. PKG karari. SVO oykusu olmayan hasta.',
        recete_teshisleri=['I21.4'],
        hasta_yasi=75,
    ))
    print(f'[P1-YAS75] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_p1_yas_db_yok_ke():
    """Hasta yaşı DB'de yok, dogum tarihi de yok → yaş atomu KE → ŞÜPHELİ.

    Kritik kural (2026-05-17): rapor lafzından yaş okuma YASAK; raporda
    '75 yaşın altında' lafzı olsa bile yaş = None kalmalı, DB'de yaş
    bulunamadıysa KE üretilmeli (eski tuzak — 75'i hasta yaşı sanma).
    """
    r = kontrol_prasugrel(_rec(
        '75 YASIN ALTINDA 60 KG IN USTUNDEKI SEREBROVASKULER OLAY OYKUSU '
        'OLMAYAN AKUT KORONER SENDROMLU OLUP NSTEMI HASTALARDA PKG KARARI '
        'ALINMIS.',
        recete_teshisleri=['I21.4'],
        hasta_yasi=None,
        hasta_kilosu=None,
        # dogum_tarihi YOK
    ))
    print(f'[P1-YAS-DB-YOK] {_ozet(r)}')
    # Yaş atomu KE düşürür → final ŞÜPHELİ
    assert r.sonuc == KontrolSonucu.KONTROL_EDILEMEDI, \
        f'DB\'de yaş yok ise rapor metni 75 yaş altı dese de KE olmalı'


def test_p1_dogum_tarihinden_yas_hesabi():
    """hasta_yasi YOK ama dogum_tarihi var → otomatik yaş hesabı."""
    from datetime import date
    bugun = date.today()
    dogum_yili = bugun.year - 50
    r = kontrol_prasugrel(_rec(
        'NSTEMI + PKG karari. SVO oykusu yok.',
        recete_teshisleri=['I21.4'],
        hasta_yasi=None,
        dogum_tarihi=f'{dogum_yili}-06-15',
        hasta_kilosu=80,
    ))
    print(f'[P1-DOGUM-TARIH] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, \
        'dogum_tarihi 50 yıl önce → yaş ~50 < 75, UYGUN olmalı'


def test_p1_svo_typo_serabrvaskuler():
    """SUT lafzı doktor typo'su 'SERABRVASKULER' (3C12MNU MEHMET GÜLER bug fix)."""
    r = kontrol_prasugrel(_rec(
        'AKUT KORONER SENDROMLU OLUP NSTEMI HASTASI. PERKUTAN KORONER '
        'GIRISIM KARARI ALINDI. 75 YASIN ALTINA 60 KG IN USTUNDEKI '
        'SERABRVASKULER OLAY OYKUSU OLMAYAN HASTA.',
        recete_teshisleri=['I21.4'],
        hasta_yasi=66,
        hasta_kilosu=82,
    ))
    print(f'[P1-SVO-TYPO] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, \
        'Doktor typo SERABRVASKULER regex ile yakalanmalı, UYGUN'


def test_p1_svo_typo_serbravaskuler():
    """SVO başka bir typo: 'SERBRAVASKULER' (harf yer değiştirmesi)."""
    r = kontrol_prasugrel(_rec(
        'NSTEMI tanisi. PKG karari. SERBRAVASKULER OLAY OYKUSU OLMAYAN HASTA.',
        recete_teshisleri=['I21.4'],
    ))
    print(f'[P1-SVO-SERBRA] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN


def test_p1_svo_pozitif_kontrendike():
    """SVO öyküsü VAR (geçirmiş) → kontrendike → UYGUN_DEGIL."""
    r = kontrol_prasugrel(_rec(
        'NSTEMI tanisi. PKG karari. SEREBROVASKULER OLAY GECIRMIS HASTA.',
        recete_teshisleri=['I21.4'],
    ))
    print(f'[P1-SVO-POZ] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_p1_pkg_eksik_yok():
    """NSTEMI var ama PKG kararı lafzı yok → P-1B-pkg YOK → ŞÜPHELİ/UYGUN_DEGIL."""
    r = kontrol_prasugrel(_rec(
        'AKUT KORONER SENDROMLU HASTA NSTEMI. SVO oykusu olmayan hasta.',
        recete_teshisleri=['I21.4'],
    ))
    print(f'[P1-PKG-YOK] {_ozet(r)}')
    assert r.sonuc != KontrolSonucu.UYGUN, \
        'PKG kararı atomu YOK → P-1 tamam değil'


def test_p2_klop_stent_trombozu_tam_lafiz():
    """P-2 tam lafız: 'klopidogrel altında stent trombozu' → P-2 VAR → UYGUN."""
    r = kontrol_prasugrel(_rec(
        'KLOPIDOGREL ALTINDA STENT TROMBOZU GELISEN AKUT KORONER SENDROMLU '
        'NSTEMI HASTASI.',
        recete_teshisleri=['I21.4'],
    ))
    print(f'[P2-TAM-LAFIZ] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN


def test_p2_stent_tromboz_lafiz_klop_gecmis_db():
    """P-2 kademe 2: 'stent trombozu' lafzı + hasta geçmiş ilaç listesi Plavix."""
    r = kontrol_prasugrel(_rec(
        'AKUT KORONER SENDROMLU NSTEMI. KORONER STENT TROMBOZU GELISTI.',
        recete_teshisleri=['I21.4'],
        recete_ilaclari=['PLAVIX 75MG TB'],
    ))
    print(f'[P2-DB-KLOP] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, \
        'Hasta geçmiş reçetede Plavix → P-2 VAR'


def test_p2_stent_tromboz_lafiz_klop_db_yok_ke():
    """P-2 kademe 3: 'stent trombozu' var ama Klop kullanım izi YOK → KE."""
    r = kontrol_prasugrel(_rec(
        'AKUT KORONER SENDROMLU NSTEMI. STENT TROMBOZU GELISTI.',
        recete_teshisleri=['I21.4'],
        recete_ilaclari=[],
    ))
    print(f'[P2-DB-KLOP-YOK] {_ozet(r)}')
    # P-1 tam (yaş/kilo defaults + NSTEMI + PKG yok). Burada P-2 KE düşer ama
    # P-1 PKG eksik olabilir; bu yüzden final ŞÜPHELİ veya UYGUN_DEGIL.
    assert r.sonuc != KontrolSonucu.UYGUN


def test_yol_a_yanlis_brans():
    """Yol-A aile hekimliği → raporsuz akış yok. Rapor da yok → ŞÜPHELİ/UYGUN_DEGIL."""
    r = kontrol_prasugrel(_rec(
        'NSTEMI tanisi. PKG karari. SVO oykusu yok.',
        recete_teshisleri=['I21.4'],
        doktor_uzmanligi='Aile Hekimligi',
        rapor_kodu='',
    ))
    print(f'[YOL-A-WRONG] {_ozet(r)}')
    assert r.sonuc != KontrolSonucu.UYGUN


def test_3c12mnu_mehmet_guler_gercek():
    """Gerçek üretim senaryosu (3C12MNU MEHMET GÜLER, 18.02.2025):
    Effient reçetesi, Pratisyen Hekim, Kardiyoloji raporu, NSTEMI+PKG+SVO yok.

    Eski sistem: ŞÜPHELİ (Klopidogrel 4-yolak şemasıyla yanlış kontrol +
    SVO atomu typo'ya takılıyor + yaş atomu rapor lafzından okuyor).
    Yeni sistem: UYGUN olmalı (P-1 tam + Yol-B raporlu akış).
    """
    r = kontrol_prasugrel(_rec(
        '75 YASIN ALTINA 60 KG IN USTUNDEKI SERABRVASKULER OLAY OYKUSU '
        'OLMAYAN AKUT KORONER SEMDROMLU OLUP HASTANEYE YATIRILAN VE '
        'ACILEN KORONER ANJIOGRAFISI YAPILIP PERKUTAN KORONER GIRISIM '
        'KARARI ALINAN ST YUKSELMESIZ MIYOKART ENFAKTUSU (NSTEMI) '
        'HASTALARDA PRASUGREL 1X1 TEDAVISINE GECILMISTIR.',
        recete_teshisleri=['E78.4', 'I10', 'I21.9', 'K21'],
        rapor_kodu='04.02',
        doktor_uzmanligi='Pratisyen Hekim',
        rapor_dr_brans='Kardiyoloji',
        hasta_yasi=66,    # DB'den (örnek)
        hasta_kilosu=85,  # DB'den (örnek)
    ))
    print(f'[3C12MNU-MEHMET] {_ozet(r)}')
    # Pratisyen Hekim Yol-A için uygun değil → Yol-B (raporlu) gerekli.
    # rapor_dr_brans=Kardiyoloji + reçete=Pratisyen → Yol-B reçete branşı YOK
    # → ŞÜPHELİ veya UYGUN_DEGIL. Buradaki amaç eski ŞÜPHELİ tuzağının
    # çözüldüğünü göstermek değil; SVO+yaş tuzağı düzeltildiğinden P-1
    # tanı/uygunluk tam, sadece reçete branşı yanlış. Bu doğru davranış.
    assert r.sonuc != KontrolSonucu.UYGUN, \
        f'Pratisyen Hekim reçete → akış yanlış, UYGUN olmamalı'
    # Ancak P-1 P-2 yolakları sağlanıyor olmalı (SVO+yaş tuzağı çözüldü)
    yolak = r.detaylar.get('yolak_durumlari', {})
    assert yolak.get('P-1 standart') == 'var', \
        f'P-1 standart yol VAR olmalı, oldu: {yolak}'


if __name__ == '__main__':
    testler = [
        test_p1_standart_uygun,
        test_p1_yas_75_kontrendike,
        test_p1_yas_db_yok_ke,
        test_p1_dogum_tarihinden_yas_hesabi,
        test_p1_svo_typo_serabrvaskuler,
        test_p1_svo_typo_serbravaskuler,
        test_p1_svo_pozitif_kontrendike,
        test_p1_pkg_eksik_yok,
        test_p2_klop_stent_trombozu_tam_lafiz,
        test_p2_stent_tromboz_lafiz_klop_gecmis_db,
        test_p2_stent_tromboz_lafiz_klop_db_yok_ke,
        test_yol_a_yanlis_brans,
        test_3c12mnu_mehmet_guler_gercek,
    ]
    basarisiz = []
    for t in testler:
        try:
            t()
        except AssertionError as e:
            basarisiz.append((t.__name__, str(e)))
            print(f'  ✗ {t.__name__}: {e}')
    if basarisiz:
        print(f'\n{len(basarisiz)}/{len(testler)} BASARISIZ:')
        for ad, hata in basarisiz:
            print(f'  - {ad}: {hata}')
        import sys
        sys.exit(1)
    print(f'\nTumu ({len(testler)}) BASARILI [OK]')
