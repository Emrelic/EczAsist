# -*- coding: utf-8 -*-
"""Hepatit — "İlaç Geçmişini Raporlardan Tara" özelliği testleri.

hepatit_onceki_etken_raporlardan(): hastanın raporlarından önceki HBV oral
etkenini tespit + aktifle karşılaştırma. hasta_etken_tablo mock'lanır.
Ayrıca _gecmis_etken_override enjeksiyonunun /4 belirsizliğini gidermesi.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import recete_kontrol.rapor_etken_madde_tablosu as ret
from recete_kontrol.rapor_etken_madde_tablosu import EtkenTabloSatiri
from recete_kontrol.hepatit_kontrol import (
    hepatit_onceki_etken_raporlardan, _hep_recete_tipi_tespit, _tr_lower,
)


def _mock_tablo(satirlar):
    """hasta_etken_tablo'yu verilen satırlarla değiştir (restore et)."""
    orig = ret.hasta_etken_tablo

    def restore():
        ret.hasta_etken_tablo = orig
    ret.hasta_etken_tablo = lambda tc: satirlar
    return restore


def test_ayni_etken_tespit():
    """Önceki TENOFOVIR + aktif TENOFOVIR (NEFOVIR) → ayni_mi True."""
    restore = _mock_tablo([
        EtkenTabloSatiri(etken_madde='TENOFOVIR DISOPROKSIL FUMARAT',
                         tarih='13/06/2025', rapor_kodu='14.01'),
    ])
    try:
        r = hepatit_onceki_etken_raporlardan(
            '45301997604', 'NEFOVIR 245MG', 'TENOFOVIR DISOPROKSIL',
            aktif_rapor_tarih='15/06/2026')
    finally:
        restore()
    print(f"[1] ayni: rapor_var={r['rapor_var']}, ayni_mi={r['ayni_mi']}, "
          f"gerekce={r['gecmis_etken_gerekce']}")
    assert r['rapor_var'] is True
    assert r['aktif_alt_tip'] == 'TDF'
    assert r['onceki_alt_tip'] == 'TDF'
    assert r['ayni_mi'] is True
    assert 'TENOFOVIR' in r['gecmis_etken_gerekce'].upper()


def test_degisim_tespit():
    """Önceki ENTEKAVIR (BARACLUDE) + aktif TENOFOVIR → ayni_mi False."""
    restore = _mock_tablo([
        EtkenTabloSatiri(etken_madde='ENTEKAVIR', tarih='01/02/2023',
                         rapor_kodu='14.01'),
    ])
    try:
        r = hepatit_onceki_etken_raporlardan(
            '45301997604', 'NEFOVIR 245MG', 'TENOFOVIR DISOPROKSIL',
            aktif_rapor_tarih='15/06/2026')
    finally:
        restore()
    print(f"[2] değişim: onceki_alt={r['onceki_alt_tip']}, ayni_mi={r['ayni_mi']}")
    assert r['onceki_alt_tip'] == 'ETV'
    assert r['ayni_mi'] is False
    assert 'DEĞİŞMİŞ' in r['mesaj']


def test_en_son_onceki_secilir():
    """Birden çok önceki etken varsa EN SON tarihli seçilir."""
    restore = _mock_tablo([
        EtkenTabloSatiri(etken_madde='LAMIVUDIN', tarih='01/01/2020'),
        EtkenTabloSatiri(etken_madde='ENTEKAVIR', tarih='10/03/2024'),
        EtkenTabloSatiri(etken_madde='TENOFOVIR ALAFENAMID', tarih='05/05/2022'),
    ])
    try:
        r = hepatit_onceki_etken_raporlardan(
            '11111111111', 'VEMLIDY', 'TENOFOVIR ALAFENAMID',
            aktif_rapor_tarih='01/01/2026')
    finally:
        restore()
    print(f"[3] en son önceki: {r['onceki_alt_tip']} ({len(r['onceki_etkenler'])} kayıt)")
    # En son önceki = ENTEKAVIR (10/03/2024) → aktif TAF ile farklı
    assert r['onceki_alt_tip'] == 'ETV'
    assert r['ayni_mi'] is False
    assert len(r['onceki_etkenler']) == 3


def test_rapor_yok():
    """Yerel rapor kaydı boş → rapor_var False, Medula tara uyarısı."""
    restore = _mock_tablo([])
    try:
        r = hepatit_onceki_etken_raporlardan('22222222222', 'NEFOVIR',
                                             'TENOFOVIR DISOPROKSIL')
    finally:
        restore()
    print(f"[4] rapor yok: basarili={r['basarili']}, rapor_var={r['rapor_var']}")
    assert r['basarili'] is True
    assert r['rapor_var'] is False
    assert 'MEDULA' in r['mesaj'].upper()


def test_hbv_oral_disi_elenir():
    """Raporda yalnız HCV/başka etken varsa önceki HBV oral bulunmaz."""
    restore = _mock_tablo([
        EtkenTabloSatiri(etken_madde='SOFOSBUVIR', tarih='01/01/2023'),
        EtkenTabloSatiri(etken_madde='PARASETAMOL', tarih='01/01/2024'),
    ])
    try:
        r = hepatit_onceki_etken_raporlardan('33333333333', 'NEFOVIR',
                                             'TENOFOVIR DISOPROKSIL',
                                             aktif_rapor_tarih='01/01/2026')
    finally:
        restore()
    print(f"[5] HBV oral dışı elenir: onceki={len(r['onceki_etkenler'])}")
    assert r['rapor_var'] is True
    assert r['onceki_etkenler'] == []
    assert r['ayni_mi'] is None


def test_aktif_rapor_kendisi_haric():
    """Aktif rapor tarihindeki/sonraki satırlar önceki sayılmaz."""
    restore = _mock_tablo([
        EtkenTabloSatiri(etken_madde='TENOFOVIR DISOPROKSIL FUMARAT',
                         tarih='15/06/2026'),  # aktif raporun kendisi
    ])
    try:
        r = hepatit_onceki_etken_raporlardan(
            '44444444444', 'NEFOVIR', 'TENOFOVIR DISOPROKSIL',
            aktif_rapor_tarih='15/06/2026')
    finally:
        restore()
    print(f"[6] aktif hariç: onceki={len(r['onceki_etkenler'])}")
    assert r['onceki_etkenler'] == []


def test_override_recete_tipi_tespit():
    """_gecmis_etken_override → _hep_recete_tipi_tespit extra['gecmis_etken']
    doldurur ve DEVAM sinyali üretir."""
    ilac_sonuc = {
        'hasta_tc': '',  # DB/EOS sorgusu yapılmasın
        'ilac_adi': 'NEFOVIR 245MG',
        'etkin_madde': 'TENOFOVIR DISOPROKSIL',
        '_gecmis_etken_override': 'raporlar:13/06/2025 TENOFOVIR DISOPROKSIL FUMARAT',
    }
    metin = _tr_lower('kronik hepatit b. tedavinin devamıdır.')
    tip, gerekce, extra = _hep_recete_tipi_tespit(
        ilac_sonuc, 'HEPATIT_B', metin)
    print(f"[7] override: tip={tip}, gecmis_etken={extra['gecmis_etken'][:40]}")
    assert extra['gecmis_etken'] == ilac_sonuc['_gecmis_etken_override']
    assert tip == 'DEVAM'


def test_override_uctan_uca_ayni_etken():
    """Override ile kontrol_hepatit_atomik: /4 atomu artık 'sorgulanamadı' KE
    değil — aktif TENOFOVIR önceki TENOFOVIR ile aynı → değişim aranmaz."""
    from recete_kontrol.hepatit_kontrol import kontrol_hepatit_atomik
    from recete_kontrol.base_kontrol import SartDurumu
    ilac_sonuc = {
        'ilac_adi': 'NEFOVIR 245MG',
        'etkin_madde': 'TENOFOVIR DISOPROKSIL',
        'rapor_kodu': '06.01',
        'hasta_yasi': 46,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B. HBsAg pozitif. 13.06.2025 tarihli raporun '
            'devamıdır. Gastroenteroloji uzman raporu.'],
        'recete_teshisleri': ['B18.1'],
        '_gecmis_etken_override': 'raporlar:13/06/2025 TENOFOVIR DISOPROKSIL FUMARAT',
    }
    rapor = kontrol_hepatit_atomik(ilac_sonuc)
    # /4 grubunda "sorgulanamadı" KE atomu OLMAMALI; "aynı" VAR atomu olmalı
    dort_atomlar = [s for s in (rapor.sartlar or [])
                    if '4.2.13.1/4' in (s.grup or '')]
    ayni_var = any('aynı' in s.ad.lower() and s.durum == SartDurumu.VAR
                   for s in dort_atomlar)
    sorgulanamadi = any('önceki tedaviyle aynı mı' in s.ad.lower()
                        and s.durum == SartDurumu.KONTROL_EDILEMEDI
                        for s in dort_atomlar)
    print(f"[8] uçtan uca: tip={rapor.detaylar.get('recete_tipi')}, "
          f"ayni_VAR={ayni_var}, sorgulanamadi_KE={sorgulanamadi}")
    assert ayni_var, 'Override sonrası /4 "aynı etken" VAR atomu bekleniyor'
    assert not sorgulanamadi, '/4 "sorgulanamadı" KE atomu kalmamalı'


if __name__ == '__main__':
    print('═' * 70)
    print('HEPATİT — İLAÇ GEÇMİŞİNİ RAPORLARDAN TARA TESTLERİ')
    print('═' * 70)
    testler = [
        test_ayni_etken_tespit,
        test_degisim_tespit,
        test_en_son_onceki_secilir,
        test_rapor_yok,
        test_hbv_oral_disi_elenir,
        test_aktif_rapor_kendisi_haric,
        test_override_recete_tipi_tespit,
        test_override_uctan_uca_ayni_etken,
    ]
    basarili = 0
    for t in testler:
        try:
            t()
            basarili += 1
        except AssertionError as e:
            print(f'  ✗ {t.__name__}: {e}')
        except Exception as e:
            print(f'  ✗ {t.__name__} HATA: {type(e).__name__}: {e}')
    print()
    print('═' * 70)
    print(f'SONUÇ: {basarili}/{len(testler)} test başarılı')
    print('═' * 70)
    sys.exit(0 if basarili == len(testler) else 1)
