# -*- coding: utf-8 -*-
"""Klopidogrel / Prasugrel / Tikagrelor atomik SUT kontrol akıl testleri.

SUT 4.2.15.A / Ç / E mevzuatına göre 4 yolak (Y1: stent / Y2: AKS /
Y3: kronik / Y4: girişimsel) + Prasugrel/Tikagrelor ek şartları.

Test senaryoları her yolak için: UYGUN / UYGUN_DEGIL / SUPHELI + edge case.
"""
import sys
from recete_kontrol.sut_kontrolleri import kontrol_klopidogrel
from recete_kontrol.base_kontrol import KontrolSonucu, SartDurumu


def _ozet(rapor):
    yolak = rapor.detaylar.get('yolak_durumlari', {})
    return (f'sonuç={rapor.sonuc.value} | yolaklar={yolak} | '
            f'şart={len(rapor.sartlar)}')


def _grup_durumlari(rapor):
    return rapor.detaylar.get('grup_durumlari', {})


def _rec(rapor_metin, **kwargs):
    """Test fixture helper. mesaj_metni alanı ana metin kaynagi."""
    base = {
        'ilac_adi': 'PLAVIX',
        'etkin_madde': 'KLOPIDOGREL',
        'rapor_kodu': '',
        'recete_teshisleri': [],
        'mesaj_metni': rapor_metin,
        'doktor_uzmanligi': '',
    }
    base.update(kwargs)
    return base


def test_y1_stent_uygun():
    """Y-1 UYGUN: koroner stent + kardiyolog -> raporsuz akis."""
    r = kontrol_klopidogrel(_rec(
        'Koroner artere stent uygulanan hasta. PKG yapildi.',
        recete_teshisleri=['I25.1'],
        doktor_uzmanligi='Kardiyoloji',
    ))
    print(f'[T1 Y1-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, f'beklenti UYGUN, gercek {r.sonuc}'


def test_y1_stent_yanlis_brans():
    """Y-1 raporsuz akista yanlis brans -> uygun degil."""
    r = kontrol_klopidogrel(_rec(
        'Koroner stent takildi.',
        recete_teshisleri=['I25.1'],
        doktor_uzmanligi='Aile Hekimligi',
    ))
    print(f'[T2 Y1-WRONG-BRANS] {_ozet(r)}')
    assert r.sonuc != KontrolSonucu.UYGUN, f'aile hekimi raporsuz olmaz'


def test_y2_aks_stemi_uygun():
    """Y-2 UYGUN: STEMI + acil tip, raporsuz."""
    r = kontrol_klopidogrel(_rec(
        'STEMI tanisi, hastaneye yatis. EKG ST yukselmesi, troponin pozitif.',
        recete_teshisleri=['I21.0'],
        doktor_uzmanligi='Acil Tip',
    ))
    print(f'[T3 Y2-STEMI-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, f'STEMI + acil tip UYGUN olmali'


def test_y2_nstemi_troponin_yok():
    """Y-2: NSTEMI ama EKG/troponin lafzi yok -> SUPHELI veya UYGUN."""
    r = kontrol_klopidogrel(_rec(
        'NSTEMI tanisi.',
        recete_teshisleri=['I21.4'],
        doktor_uzmanligi='Kardiyoloji',
    ))
    print(f'[T4 Y2-NSTEMI-KE] {_ozet(r)}')
    assert r.sonuc in (KontrolSonucu.KONTROL_EDILEMEDI, KontrolSonucu.UYGUN), \
        f'NSTEMI sessiz troponin -> KE veya UYGUN'


def test_y3_kronik_anjio_kah():
    """Y-3 UYGUN: rapor kodu 04.02.1 + anjio + KAH + kardiyolog rapor."""
    r = kontrol_klopidogrel(_rec(
        'Koroner anjiografi yapildi. Koroner arter hastaligi tespit.',
        rapor_kodu='04.02.1',
        recete_teshisleri=['I25.1'],
        rapor_dr_brans='Kardiyoloji',
        doktor_uzmanligi='Aile Hekimligi',
    ))
    print(f'[T5 Y3-KAH-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, f'anjio+KAH+rapor UYGUN olmali'


def test_y3_iskemik_inme_uygun():
    """Y-3 UYGUN: iskemik inme + rapor + noroloji."""
    r = kontrol_klopidogrel(_rec(
        'Iskemik inme oykusu. Serebral iskemi.',
        rapor_kodu='04.04',
        recete_teshisleri=['I63.5'],
        rapor_dr_brans='Noroloji',
        doktor_uzmanligi='Aile Hekimligi',
    ))
    print(f'[T6 Y3-INME-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, f'iskemik inme+rapor UYGUN'


def test_y3_pah_uygun():
    """Y-3 UYGUN: tikayici periferik arter + rapor + ic hastaliklari."""
    r = kontrol_klopidogrel(_rec(
        'Tikayici periferik arter hastaligi, klaudikasyo.',
        rapor_kodu='04.02.1',
        recete_teshisleri=['I70.2'],
        rapor_dr_brans='Ic Hastaliklari',
        doktor_uzmanligi='Aile Hekimligi',
    ))
    print(f'[T7 Y3-PAH-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, f'PAH+rapor UYGUN'


def test_y4_girisimsel_uygun():
    """Y-4 UYGUN: serebral koil + beyin cerrahisi -> raporsuz."""
    r = kontrol_klopidogrel(_rec(
        'Serebral girisim sonrasi koil yerlestirildi.',
        ilac_adi='KARUM',
        doktor_uzmanligi='Beyin Cerrahisi',
    ))
    print(f'[T8 Y4-KOIL-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, f'serebral koil + B.Cer UYGUN'


def test_y4_radyolog_stentgraft():
    """Y-4 UYGUN: girisimsel radyolog + stentgraft."""
    r = kontrol_klopidogrel(_rec(
        'Endovaskuler islem, periferik stentgraft yerlestirildi.',
        ilac_adi='PLAGREL',
        doktor_uzmanligi='Radyoloji',
    ))
    print(f'[T9 Y4-RADYO-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, f'radyolog + stentgraft UYGUN'


def test_hicbir_endikasyon_yok():
    """Hicbir yolak tetiklenmez -> UYGUN_DEGIL."""
    r = kontrol_klopidogrel(_rec(
        'Diyabet kontrolu icin',
        recete_teshisleri=['E11.9'],
        doktor_uzmanligi='Aile Hekimligi',
    ))
    print(f'[T10 HICBIR] {_ozet(r)}')
    assert r.sonuc != KontrolSonucu.UYGUN, \
        f'diyabet icin klopidogrel uygun olmaz'


def test_bos_metin():
    """Tam bos recete -> UYGUN_DEGIL."""
    r = kontrol_klopidogrel(_rec(''))
    print(f'[T11 BOS] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL, \
        f'bos metin UYGUN_DEGIL olmali'


def test_prasugrel_yasli():
    """Prasugrel + yas 80 -> kontrendike (UYGUN_DEGIL)."""
    r = kontrol_klopidogrel(_rec(
        'STEMI, PKG karari, hastaneye yatis.',
        ilac_adi='EFFIENT',
        etkin_madde='PRASUGREL',
        recete_teshisleri=['I21.0'],
        doktor_uzmanligi='Kardiyoloji',
        hasta_yasi=80,
        hasta_kilosu=75,
    ))
    print(f'[T12 PRASU-YASLI] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL, \
        f'Prasugrel >=75 yasta kontrendike'


def test_prasugrel_uygun():
    """Prasugrel + yas 60, kilo 80, SVO yok, STEMI + PKG -> UYGUN."""
    r = kontrol_klopidogrel(_rec(
        'STEMI tanisi, PKG karari alindi. Hastaneye yatis. '
        'EKG ST yukselmesi, troponin pozitif. SVO oykusu yok.',
        ilac_adi='EFFIENT',
        etkin_madde='PRASUGREL',
        recete_teshisleri=['I21.0'],
        doktor_uzmanligi='Kardiyoloji',
        hasta_yasi=60,
        hasta_kilosu=80,
    ))
    print(f'[T13 PRASU-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, \
        f'Prasugrel <75 + >60kg + STEMI + PKG UYGUN'


def test_tikagrelor_uygun():
    """Tikagrelor + STEMI + EKG/troponin + fibrinolitik yok + varfarin yok."""
    r = kontrol_klopidogrel(_rec(
        'STEMI tanisi. EKG\'de persistan ST yukselmesi 2 ardisik '
        'derivasyon. Troponin pozitif, CK-MB pozitif. '
        'Fibrinolitik tedavi uygulanmamistir. '
        'Varfarin kullanmiyor.',
        ilac_adi='BRILINTA',
        etkin_madde='TIKAGRELOR',
        recete_teshisleri=['I21.0'],
        doktor_uzmanligi='Kardiyoloji',
        diger_ilac_adlari=[],
    ))
    print(f'[T14 TIKAG-UYGUN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, \
        f'Tikagrelor tum sartlar tamam UYGUN'


def test_tikagrelor_varfarin_var():
    """Tikagrelor + varfarin diger recetede -> kontrendike."""
    r = kontrol_klopidogrel(_rec(
        'STEMI tanisi. EKG ST yukselmesi, troponin pozitif. '
        'Fibrinolitik uygulanmamistir.',
        ilac_adi='BRILINTA',
        etkin_madde='TIKAGRELOR',
        recete_teshisleri=['I21.0'],
        doktor_uzmanligi='Kardiyoloji',
        diger_ilac_adlari=['COUMADIN 5MG TB'],
    ))
    print(f'[T15 TIKAG-VARFARIN] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL, \
        f'Tikagrelor + varfarin kontrendike'


def test_mehmet_senel_nstemi_tikagrelor():
    """Gercek uretim senaryosu (1WFII9U, 04.07.2023):
    NSTEMI hastasi + Tikagrelor + tum SUT sartlari lafzen rapor metninde.

    Bug fix: 'stemi' substring eski liste, 'nstemi' icinde de geciyordu —
    STEMI atomu yanlislikla VAR sayiyordu. Word-boundary regex ile fix.
    NSTEMI: VAR, STEMI: YOK olmali (klinik dogru).
    """
    r = kontrol_klopidogrel(_rec(
        '02.07.2023 TARIHINDE ACIL SERVISE MURACAT ETMIS, AKUT KORONER '
        'SENDROMLU HASTA (NSTEMI) TIKAGRELOR BASLAMADAN ONCEKI 72 SAAT '
        'ICINDE HASTANEYE YATIRILMIS OLUP ACIL TEDAVIDE FIBRINOLITIK TEDAVI '
        'UYGULANMAMIS HASTA, VARFARIN TEDAVISI ALTINDA OLMAYAN, HASTANIN '
        'TROPONIN DEGERI VE CK-MB DEGERI POZITIF OLAN, PERSISTAN GOGUS '
        'AGRISI BULUNAN VE EKG\'DE EN AZ 2 (IKI) ARDISIK DERIVASYONDA '
        '1 MM\'DEN DERIN ST DEPRESYONU BULUNAN, ST YUKSELMESIZ MIYOKARD '
        'ENFARKTUSLU (NSTEMI) TESHISLI HASTA',
        ilac_adi='BRILINTA 90MG 56 FILM TABLET',
        etkin_madde='TIKAGRELOR',
        recete_teshisleri=['E78.4', 'I10', 'I25.1', 'K29.6'],
        doktor_uzmanligi='Kardiyoloji',
        rapor_dr_brans='Kardiyoloji',
    ))
    print(f'[T21 MEHMET-NSTEMI] {_ozet(r)}')
    # NSTEMI + tum sartlar → UYGUN
    assert r.sonuc == KontrolSonucu.UYGUN, \
        f'NSTEMI + tum SUT sartlari lafzen UYGUN olmali'
    # STEMI atomu YOK olmali (false-positive bug fix dogrulamasi)
    stemi_atom = next((s for s in r.sartlar
                        if s.ad == 'STEMI (ST yükselmeli MI)'), None)
    nstemi_atom = next((s for s in r.sartlar
                         if s.ad == 'NSTEMI (ST yükselmesiz MI)'), None)
    assert stemi_atom and stemi_atom.durum.value == 'yok', \
        f'NSTEMI rapora STEMI atomu YOK olmali, oldu: {stemi_atom.durum.value}'
    assert nstemi_atom and nstemi_atom.durum.value == 'var', \
        f'NSTEMI lafzi tespit edilmeli'


def test_ayse_ulas_tikagrelor_gercek_rapor():
    """Gercek uretim senaryosu (3HCB4FX, 26.09.2025):
    Tikagrelor reçetesinde tum SUT sartlari lafzen rapor metninde geciyor:
    STEMI + 72sa fibrinolitik YOK + varfarin altinda OLMAYAN + troponin/CK-MB
    pozitif + EKG ST yukselmesi.

    Eski bug 1: 'varfarin altinda olmayan' lafzi tanimliyordu (sadece 'degil').
    Eski bug 2: 'troponin pozitif' siki substring, 'troponin degeri pozitif'
                formuyla eslesemiyor; gevsek ±80 char anchor yakinlik eklendi.
    """
    r = kontrol_klopidogrel(_rec(
        'AKUT KORONER SENDROMLU HASTA (STEMI) TIKAGRELOR BASLAMADAN ONCEKI '
        '72 SAAT ICINDE ACIL SERVISIMIZE YATIRILMIS OLUP, ACIL TEDAVIDE '
        'FIBRINOLITIK TEDAVI UYGULANMAMIS HASTA, VARFARIN TEDAVISI ALTINDA '
        'OLMAYAN, HASTANIN TROPONIN DEGERI VE CK-MB DEGERI POZITIF OLAN VE '
        'EKG\'DE EN AZ 2 (IKI) ARDISIK DERIVASYONDA 1 MM VE UZERI PERSISTAN '
        'ST SEGMENT YUKSELME GOSTERMIS OLUP ST YUKSELMELI MIYOKARD ENFARKTUSU '
        'TESHISLI HASTANIN TIKAGRELOR (BRILINTA) 90 MG 2X1 KULLANMASI UYGUNDUR.',
        ilac_adi='BRILINTA 90MG 56 FILM TABLET',
        etkin_madde='TIKAGRELOR',
        recete_teshisleri=['I10', 'I20.9', 'I25.0', 'I21.0'],
        doktor_uzmanligi='Pratisyen Hekim',
        rapor_dr_brans='Kardiyoloji',
    ))
    print(f'[T20 AYSE-TIKAGRELOR] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, \
        f'STEMI + 4 SUT sarti lafzen tam — UYGUN olmali, oldu: {r.sonuc}'


def test_anjio_varyantlari():
    """Anjio/angio/anjiyo/angiografi varyantlari kabul edilmeli."""
    for varyant in ['anjio', 'angio', 'anjiyo', 'angiografi', 'angiografik',
                     'kor.anjio', 'kag']:
        r = kontrol_klopidogrel(_rec(
            f'{varyant} yapildi, koroner arter hastaligi.',
            rapor_kodu='04.02.1',
            recete_teshisleri=['I25.1'],
            rapor_dr_brans='Kardiyoloji',
            doktor_uzmanligi='Aile Hekimligi',
        ))
        gd = _grup_durumlari(r)
        # Y-3 endikasyon grubu adini bul
        ad = next((k for k in gd if k.startswith('Y-3: Kronik endikasyon')), None)
        assert ad is not None, f'Y-3 endikasyon grubu bulunamadi'
        assert gd[ad] == 'var', \
            f'anjio varyanti "{varyant}" Y-3 endikasyon VAR olmali, oldu: {gd[ad]}'
    print(f'[T16 ANJIO-VARYANTLARI] hepsi VAR (anjio/angio/anjiyo/...)')


def test_hayri_musaoglu_anjigrafik_yazim():
    """Gercek uretim senaryosu (3KFA8US, 2026-01-22):
    'KRONER ARTER HASTALIGI ANJIGRAFIK OLARAK BELGELENMISTIR' lafzi
    Turkce yaygin yazim hatasi (anjigrafik = anjiografik, 'o' eksik).
    Eski bug: bu varyant tanınmiyordu, Y-3 endikasyon YOK → UYGUN_DEGIL.
    Duzeltme: anjigraf substring listede; bu recete UYGUN olmali.
    """
    r = kontrol_klopidogrel(_rec(
        'KRONER ARTER HASTALIGI ANJIGRAFIK OLARAK BELGELENMISTIR '
        '(Ekleme=17/10/2025 15:46)',
        ilac_adi='KARUM 75MG 28 FILM TABLET',
        etkin_madde='KLOPIDOGREL',
        rapor_kodu='04.02.1',
        recete_teshisleri=['I25.1'],
        rapor_dr_brans='Kardiyoloji',
        doktor_uzmanligi='Pratisyen Hekim',
    ))
    print(f'[T18 HAYRI-ANJIGRAFIK] {_ozet(r)}')
    # Y-3 anjio+KAH lafzen tespit → endikasyon grubu VAR → genel UYGUN
    assert r.sonuc == KontrolSonucu.UYGUN, \
        f'anjigrafik (eksik o) yazim hatasi yakalanmali → UYGUN'


def test_anjio_tarihi_atomu_sema():
    """Anjio tarihi atomu Y-3 endikasyon grubunda OR atomu olarak gorunmeli.
    Mantik formulu: (biyo VEYA anjio+KAH VEYA anjio_tarihi VEYA PAH VEYA inme).
    """
    r = kontrol_klopidogrel(_rec(
        'Koroner anjiografi tarihi: 15.06.2025 tespit edildi, KAH belgelenmis',
        rapor_kodu='04.02.1',
        recete_teshisleri=['I25.1'],
        rapor_dr_brans='Kardiyoloji',
    ))
    # Anjio tarihi atomu sartlar listesinde var mı kontrol et
    anjio_tarih_atom = next(
        (s for s in r.sartlar if 'Anjiografi tarihi raporda' in s.ad), None)
    assert anjio_tarih_atom is not None, 'Anjio tarihi atomu eksik'
    # Tarih yakalanmis olmali (15.06.2025 anchor uzakliginda)
    print(f'[T19 ANJIO-TARIH-ATOMU] anjio tarihi atom durumu='
          f'{anjio_tarih_atom.durum.value} | neden={anjio_tarih_atom.neden[:60]}')
    assert anjio_tarih_atom.grup == 'Y-3: Kronik endikasyon [(3)] — ≥1', \
        f'Anjio tarihi atomu Y-3 endikasyon grubunda olmali'
    assert anjio_tarih_atom.veya_grubu is True, \
        f'Anjio tarihi atomu OR grup uyesi olmali'


def test_aile_hekimi_ilk_24_ay():
    """Aile hekimi rapor yazan + Y-3: ilk 24 ay uygun degil."""
    r = kontrol_klopidogrel(_rec(
        'Koroner anjiografi, KAH.',
        rapor_kodu='04.02.1',
        recete_teshisleri=['I25.1'],
        rapor_dr_brans='Aile Hekimligi',
        doktor_uzmanligi='Aile Hekimligi',
    ))
    print(f'[T17 AILE-ILK-24AY] {_ozet(r)}')
    assert r.sonuc != KontrolSonucu.UYGUN, \
        f'aile hekimi rapor + Y-3 ilk 24 ay -> uygun degil'


if __name__ == '__main__':
    testler = [
        test_y1_stent_uygun,
        test_y1_stent_yanlis_brans,
        test_y2_aks_stemi_uygun,
        test_y2_nstemi_troponin_yok,
        test_y3_kronik_anjio_kah,
        test_y3_iskemik_inme_uygun,
        test_y3_pah_uygun,
        test_y4_girisimsel_uygun,
        test_y4_radyolog_stentgraft,
        test_hicbir_endikasyon_yok,
        test_bos_metin,
        test_prasugrel_yasli,
        test_prasugrel_uygun,
        test_tikagrelor_uygun,
        test_tikagrelor_varfarin_var,
        test_ayse_ulas_tikagrelor_gercek_rapor,
        test_mehmet_senel_nstemi_tikagrelor,
        test_anjio_varyantlari,
        test_hayri_musaoglu_anjigrafik_yazim,
        test_anjio_tarihi_atomu_sema,
        test_aile_hekimi_ilk_24_ay,
    ]
    basari = 0
    hata = 0
    for t in testler:
        try:
            t()
            basari += 1
        except AssertionError as e:
            print(f'  [FAIL] {t.__name__}: {e}')
            hata += 1
        except Exception as e:
            print(f'  [ERR ] {t.__name__}: {type(e).__name__}: {e}')
            hata += 1
    print()
    print(f'=== OZET: {basari}/{len(testler)} BASARILI, {hata} HATA ===')
    sys.exit(0 if hata == 0 else 1)
