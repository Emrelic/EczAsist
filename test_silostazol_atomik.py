# -*- coding: utf-8 -*-
"""Silostazol atomik SUT kontrol akıl testleri.

SUT 4.2.15.B mevzuatına göre tek yolak + (a)/(b) alt-yolu.
  Üst kısım: F1 SK rapor + (F2a heyet KDC ∨ F2b heyet Kard+GC) + G1 reçete eden
  (a) yolu : PAH + klas 3/4 + op yapılamayan
  (b) yolu : PAH + komorbidite + op yüksek riskli
"""
import sys
from recete_kontrol.sut_kontrolleri import (kontrol_silostazol,
                                             sut_kategorisi_tespit_et)
from recete_kontrol.base_kontrol import KontrolSonucu


def _ozet(r):
    d = r.detaylar
    s = (f'sonuc={r.sonuc.value} | '
         f'F1={d.get("F1 SK rapor")} F2={d.get("F2 heyet")} '
         f'G1={d.get("G1 reçete eden")} '
         f'(a)={d.get("(a) yolu")} (b)={d.get("(b) yolu")} '
         f'avb={d.get("(a∨b) endikasyon")}')
    return s.encode('ascii', 'replace').decode('ascii')


def _rec(metin='', **kwargs):
    base = {
        'ilac_adi': 'PLETAL',
        'etkin_madde': 'SILOSTAZOL',
        'rapor_kodu': '',
        'recete_teshisleri': [],
        'mesaj_metni': metin,
        'doktor_uzmanligi': '',
        'rapor_doktor_brans': '',
    }
    base.update(kwargs)
    return base


def test_a_uygun_kdc_pah_klas_op_yok():
    """(a) yolu UYGUN: KDC heyet + PAH+doppler + klas 3 + op yapılamayan."""
    r = kontrol_silostazol(_rec(
        ('Periferik arter hastalığı doppler ile tespit edilmiştir. '
         'Klas 3 semptomları mevcut. Operasyon yapılamayan hasta.'),
        rapor_kodu='04.04',
        rapor_doktor_brans='Kalp Damar Cerrahisi',
        doktor_uzmanligi='Kalp Damar Cerrahisi',
    ))
    print(f'[T1 a-UYGUN-KDC] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, f'beklenti UYGUN, gerçek {r.sonuc}'


def test_b_uygun_kard_gc_pah_komorbid_riskli():
    """(b) yolu UYGUN: Kard+GC heyet + PAH+anjio + komorbid ICD + op yüksek riskli."""
    r = kontrol_silostazol(_rec(
        ('Periferik arter hastalığı anjiyografi ile tespit. '
         'Operasyonu yüksek riskli hasta.'),
        rapor_kodu='04.04',
        rapor_doktor_brans='Kardiyoloji, Genel Cerrahi',
        doktor_uzmanligi='İç Hastalıkları',
        rap_tesh='I70.2 I10 I50.0',  # PAH + HT + KKY (komorbidite)
    ))
    print(f'[T2 b-UYGUN-Kard+GC] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN, f'beklenti UYGUN, gerçek {r.sonuc}'


def test_rapor_yok():
    """rapor_kodu boş → F1 YOK → UYGUN_DEGIL."""
    r = kontrol_silostazol(_rec(
        'Periferik arter hastalığı doppler. Klas 3. Operasyon yapılamayan.',
        rapor_kodu='',
        doktor_uzmanligi='KDC',
    ))
    print(f'[T3 rapor-YOK] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_heyet_yok_rapor_brans_bos():
    """Rapor var ama rapor_doktor_brans boş (heyet DB'de yok) → F2 YOK → UYGUN_DEGIL."""
    r = kontrol_silostazol(_rec(
        'PAH doppler tespit, klas 4 dinlenme ağrısı, operasyon yapılamayan.',
        rapor_kodu='04.04',
        rapor_doktor_brans='',  # heyet kaydı yok
        doktor_uzmanligi='Aile Hekimliği',
    ))
    print(f'[T4 heyet-YOK] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_klas_yok():
    """(a) yolunda klas 3-4 ibaresi yok ve (b) komorbidite yok → a,b YOK → UYGUN_DEGIL."""
    r = kontrol_silostazol(_rec(
        'Periferik arter hastalığı doppler. Operasyon yapılamayan.',  # klas yok
        rapor_kodu='04.04',
        rapor_doktor_brans='KDC',
        doktor_uzmanligi='KDC',
    ))
    print(f'[T5 klas-YOK] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_recete_yazan_yetkisiz():
    """Reçete yazan branş yetkili değil (örn. ortopedi) → G1 YOK → UYGUN_DEGIL."""
    r = kontrol_silostazol(_rec(
        'PAH doppler tespit, klas 3, operasyon yapılamayan.',
        rapor_kodu='04.04',
        rapor_doktor_brans='KDC',
        doktor_uzmanligi='Ortopedi ve Travmatoloji',
    ))
    print(f'[T6 recete-yetkisiz] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_b_komorbid_gecmis_icd():
    """(b) komorbidite sadece hastanın geçmiş raporlarındaki ICD'den gelir."""
    r = kontrol_silostazol(_rec(
        ('Periferik arter hastalığı anjiyografi tespit. '
         'Operasyonu yüksek riskli.'),
        rapor_kodu='04.04',
        rapor_doktor_brans='Kalp Damar Cerrahisi',
        doktor_uzmanligi='İç Hastalıkları',
        diger_raporlar_icd=['E11.9', 'I50.0', 'N18.3'],  # DM + KKY + KBY
    ))
    print(f'[T7 b-komorbid-gecmis-ICD] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN


def test_bos_metin_rapor_yok():
    """Hiç bilgi yok → UYGUN_DEGIL."""
    r = kontrol_silostazol(_rec(''))
    print(f'[T8 bos-her-sey] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_suheli_recete_brans_bos():
    """rec_brans boş → G1 KE; diğerleri VAR → genel KE → ŞÜPHELİ."""
    r = kontrol_silostazol(_rec(
        'PAH doppler tespit, klas 3, operasyon yapılamayan.',
        rapor_kodu='04.04',
        rapor_doktor_brans='KDC',
        doktor_uzmanligi='',  # boş — KE
    ))
    print(f'[T9 supheli-recete-brans-bos] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.KONTROL_EDILEMEDI


def test_kard_tek_basina_yetmez():
    """Heyette sadece Kard, GC yok → F2a YOK, F2b YOK → F2 YOK → UYGUN_DEGIL."""
    r = kontrol_silostazol(_rec(
        'PAH doppler tespit, klas 4, operasyon yapılamayan.',
        rapor_kodu='04.04',
        rapor_doktor_brans='Kardiyoloji',  # tek başına yetmez (KDC değil, GC yok)
        doktor_uzmanligi='İç Hastalıkları',
    ))
    print(f'[T10 kard-tek] {_ozet(r)}')
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL


def test_gercek_vaka_dopplar_klass_typo():
    """Gerçek saha vakası (AHMET ATEŞ 3OHVLSK, 2026-07-03): rapor lafzında
    "DOPPLAR" (doppler) ve "KLASS 3" (klas 3) yazım hataları — parser typo
    toleransı ile (a) yolu VAR olmalı."""
    r = kontrol_silostazol(_rec(
        ('HASTA İLERİ EVRE PERİFERİK ARTER HASTALIĞI DOPPLAR İLE '
         'DESTEKLENMİŞ OLUP KLASS 3 SEMPTOMLERİ BULUNAN HASTANIN 1 YIL '
         'BOYUNCA SİLOSTAZOL 2X1 KULLANMASI UYGUNDUR.OPERASYON YAPILAMAYAN '
         'HASTA. LDL:110 23.03.2026 TIKAYICI PERİFER ARTER HASTALIĞI '
         'HASTAYA 02/02/2022 TARİHİNDE ANJİO-STENT UYGULANMIŞTIR. '
         'KORONER ARTER HASTALIĞI MEVCUTTUR.'),
        rapor_kodu='04.04',
        rapor_doktor_brans='Kalp ve Damar Cerrahisi',
        doktor_uzmanligi='Kalp ve Damar Cerrahisi',
    ))
    print(f'[T11 gercek-vaka-typo] {_ozet(r)}')
    assert r.detaylar.get('(a) yolu') == 'var', \
        f"(a) yolu var beklendi, gerçek {r.detaylar.get('(a) yolu')}"
    assert r.sonuc == KontrolSonucu.UYGUN, f'beklenti UYGUN, gerçek {r.sonuc}'


def test_kategori_silastazol_varyant():
    """Etken "SİLASTAZOL" (a'lı Medula yazımı) → kategori SILOSTAZOL
    (anlık kontrol genel dispatcher'ı bu haritadan yakalar)."""
    for etken in ('SİLASTAZOL', 'SILASTAZOL', 'SILOSTAZOL', 'CILOSTAZOL'):
        kat = sut_kategorisi_tespit_et({
            'ilac_adi': 'PLETAL 100MG 60 TABLET', 'etkin_madde': etken})
        assert kat == 'SILOSTAZOL', f'{etken} -> {kat} (SILOSTAZOL beklendi)'
    kat = sut_kategorisi_tespit_et({'ilac_adi': 'PLETAL 100MG 60 TABLET',
                                     'etkin_madde': ''})
    assert kat == 'SILOSTAZOL', f'PLETAL ad fallback -> {kat}'
    print('[T12 kategori-varyant] SILASTAZOL/PLETAL -> SILOSTAZOL OK')


if __name__ == '__main__':
    testler = [
        test_a_uygun_kdc_pah_klas_op_yok,
        test_b_uygun_kard_gc_pah_komorbid_riskli,
        test_rapor_yok,
        test_heyet_yok_rapor_brans_bos,
        test_klas_yok,
        test_recete_yazan_yetkisiz,
        test_b_komorbid_gecmis_icd,
        test_bos_metin_rapor_yok,
        test_suheli_recete_brans_bos,
        test_kard_tek_basina_yetmez,
        test_gercek_vaka_dopplar_klass_typo,
        test_kategori_silastazol_varyant,
    ]
    basari = 0
    hata = 0
    for t in testler:
        try:
            t()
            basari += 1
        except AssertionError as e:
            print(f'  HATA: {t.__name__} | {e}')
            hata += 1
    print(f'\n=== OZET: {basari}/{len(testler)} BASARILI, {hata} HATA ===')
    sys.exit(0 if hata == 0 else 1)
