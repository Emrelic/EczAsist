# -*- coding: utf-8 -*-
"""SUT 4.2.13.1 — Hepatit B Y1 yolağı başlangıç ↔ devam ayrımı akıl testi.

2026-05-21'de eklenen başlangıç/devam dallanmasının doğru çalıştığını
doğrular. Tespit (_hep_recete_tipi_tespit) + atomlar (_hep_atom_*) +
Y1 entegrasyonu uçtan uca test edilir.

Senaryolar:
  1. Metin "başlanması" → BAŞLANGIÇ tespiti
  2. Metin "tedavinin devamı" → DEVAM tespiti
  3. Sessiz metin + boş DB → BELİRSİZ
  4. Metin çelişkisi (ilk tedavi + devam) → DEVAM güvenli
  5. /3 doğru doz (Entekavir 0.5 mg) → VAR
  6. /3 yanlış doz (Entekavir 1 mg) → KE (eczacı doğrulamalı)
  7. Devam reçetesi → /6.a HBsAg raporda VAR
  8. Devam reçetesi + /6.b HBsAg-/AntiHBs+ → sonlandırma bilgi atomu
  9. BELİRSİZ → atomlar (bilgi)'ye düşer, verdict çekirdek atomlardan
"""
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recete_kontrol.base_kontrol import KontrolSonucu, SartDurumu
from recete_kontrol.hepatit_kontrol import (
    kontrol_hepatit_atomik,
    _hep_recete_tipi_tespit, _tr_lower, _tr_upper,
    _hep_atom_eriskin_baslangic_dozu,
    _hep_atom_hbsag_antihbs_raporda,
    _hep_atom_sonlandirma_12ay,
    _hep_atom_hbsag_pozitif_devam,
    _hep_etken_degisim_atomlari,
    _BASLANGIC_IBARELERI, _DEVAM_IBARELERI,
)


# ─────────────────────────────────────────────────────────────────────────
# TESPİT (_hep_recete_tipi_tespit) — UNIT TESTLER
# ─────────────────────────────────────────────────────────────────────────

def test_tespit_baslangic_metin():
    metin = _tr_lower(
        'Kronik hepatit B. HBV DNA: 50.000 IU/ml. Tedaviye entekavir ile '
        'başlanması uygundur.')
    tip, gerekce, extra = _hep_recete_tipi_tespit({}, 'HEPATIT_B', metin)
    print(f"[T1] Tespit (başlangıç metin): tip={tip}")
    assert tip == 'BASLANGIC', f"Beklenen BASLANGIC, alınan {tip}: {gerekce}"
    assert extra['metin_baslangic'] is True


def test_tespit_devam_metin():
    metin = _tr_lower('Tedavinin devamı için yeni rapor düzenlenmiştir.')
    tip, gerekce, extra = _hep_recete_tipi_tespit({}, 'HEPATIT_B', metin)
    print(f"[T2] Tespit (devam metin): tip={tip}")
    assert tip == 'DEVAM', f"Beklenen DEVAM, alınan {tip}: {gerekce}"
    assert extra['metin_devam'] is True


def test_tespit_sessiz_metin_belirsiz():
    metin = _tr_lower('Hasta hepatit B, HBV DNA pozitif.')
    tip, gerekce, extra = _hep_recete_tipi_tespit({}, 'HEPATIT_B', metin)
    print(f"[T3] Tespit (sessiz metin + DB boş): tip={tip}")
    assert tip == 'BELIRSIZ', f"Beklenen BELIRSIZ, alınan {tip}: {gerekce}"


def test_tespit_celiski_devam_kazanir():
    """DB devam diyor ama metin "ilk tedavi" diyorsa → DEVAM güvenli karar."""
    # NOT: hasta_tc verilmediği için DB sorgusu yapılamayacak.
    # Bu senaryoda sadece metin çelişkisini test ediyoruz: ikisi de metin sinyali.
    metin = _tr_lower('İlk tedavi, ancak tedavinin devamı için yenileme raporu.')
    tip, gerekce, extra = _hep_recete_tipi_tespit({}, 'HEPATIT_B', metin)
    print(f"[T4] Tespit (çelişki — metin hem ilk hem devam): tip={tip}")
    # Hem başlangıç hem devam ibaresi → DEVAM kazanır (güvenli)
    assert tip == 'DEVAM', f"Çelişkide DEVAM güvenli, alınan {tip}"


# ─────────────────────────────────────────────────────────────────────────
# /3 ERİŞKİN BAŞLANGIÇ DOZU — ATOM TESTLERİ
# ─────────────────────────────────────────────────────────────────────────

def test_doz_eriskin_dogru_entekavir():
    """SUT 4.2.13.1/3 — Entekavir 0.5 mg → VAR."""
    atom = _hep_atom_eriskin_baslangic_dozu('BARACLUDE 0.5 MG 30 TABLET',
                                              'ENTEKAVIR')
    print(f"[T5] /3 Entekavir 0.5 mg: durum={atom.durum.value}, "
          f"neden={atom.neden[:80]}")
    assert atom.durum == SartDurumu.VAR


def test_doz_eriskin_yanlis_entekavir():
    """SUT 4.2.13.1/3 — Entekavir 1 mg (yanlış) → KE."""
    atom = _hep_atom_eriskin_baslangic_dozu('FAKE 1 MG TABLET', 'ENTEKAVIR')
    print(f"[T6] /3 Entekavir 1 mg (yanlış): durum={atom.durum.value}, "
          f"sartli={atom.sartli_atom}")
    assert atom.durum == SartDurumu.KONTROL_EDILEMEDI
    assert atom.sartli_atom is True


def test_doz_eriskin_tdf_dogru():
    atom = _hep_atom_eriskin_baslangic_dozu('VIREAD 245 MG 30 TABLET',
                                              'TENOFOVIR DISOPROKSIL FUMARAT')
    print(f"[T6b] /3 TDF 245 mg: durum={atom.durum.value}")
    assert atom.durum == SartDurumu.VAR


def test_doz_eriskin_taf_dogru():
    atom = _hep_atom_eriskin_baslangic_dozu('VEMLIDY 25 MG 30 TABLET',
                                              'TENOFOVIR ALAFENAMID FUMARAT')
    print(f"[T6c] /3 TAF 25 mg: durum={atom.durum.value}")
    assert atom.durum == SartDurumu.VAR


def test_doz_eriskin_listede_olmayan_etken():
    """Adefovir gibi /3 listesinden olmayan etken → KE."""
    atom = _hep_atom_eriskin_baslangic_dozu('HEPSERA 10 MG', 'ADEFOVIR')
    print(f"[T6d] /3 Adefovir (listede yok): durum={atom.durum.value}")
    assert atom.durum == SartDurumu.KONTROL_EDILEMEDI


# ─────────────────────────────────────────────────────────────────────────
# DEVAM ATOMLARI — /6.a, /6.b, /7 ATOM TESTLERİ
# ─────────────────────────────────────────────────────────────────────────

def test_hbsag_raporda_var():
    metin = _tr_lower('HBsAg pozitif, Anti-HBs negatif.')
    atom = _hep_atom_hbsag_antihbs_raporda(metin)
    print(f"[T7] /6.a HBsAg+ raporda: durum={atom.durum.value}")
    assert atom.durum == SartDurumu.VAR


def test_hbsag_raporda_sessiz_ke():
    metin = _tr_lower('Hastanın tedavisi devam etmektedir.')
    atom = _hep_atom_hbsag_antihbs_raporda(metin)
    print(f"[T7b] /6.a HBsAg sessiz: durum={atom.durum.value}, "
          f"sartli={atom.sartli_atom}")
    assert atom.durum == SartDurumu.KONTROL_EDILEMEDI


def test_sonlandirma_hbsag_neg_antihbs_pos():
    """SUT 4.2.13.1/6.b — HBsAg(-) + Anti-HBs(+) → sonlandırma kuralları."""
    metin = _tr_lower('HBsAg negatif, Anti-HBs pozitif.')
    atom = _hep_atom_sonlandirma_12ay(metin)
    print(f"[T8] /6.b Sonlandırma HBsAg-/AntiHBs+: durum={atom.durum.value}, "
          f"grup='{atom.grup}'")
    # Durum KE çünkü 12 ay süresi parse edilemiyor
    assert atom.durum == SartDurumu.KONTROL_EDILEMEDI
    assert '(bilgi)' in atom.grup  # verdict matematiğine girmesin


def test_sonlandirma_durum_yok_NA():
    """HBsAg(-)+AntiHBs(+) durumu yoksa /6.b atomu NA (gizlenir)."""
    metin = _tr_lower('HBsAg pozitif.')
    atom = _hep_atom_sonlandirma_12ay(metin)
    print(f"[T8b] /6.b Sonlandırma durumu yok: durum={atom.durum.value}")
    assert atom.durum == SartDurumu.NA


def test_hbsag_pozitif_devam_meşru():
    """SUT 4.2.13.1/7 — HBsAg+ → tedaviye devam meşru."""
    metin = _tr_lower('HBsAg pozitif, klinik ve laboratuvar takibi sürdürülüyor.')
    atom = _hep_atom_hbsag_pozitif_devam(metin)
    print(f"[T9] /7 HBsAg+ devam: durum={atom.durum.value}")
    assert atom.durum == SartDurumu.VAR


# ─────────────────────────────────────────────────────────────────────────
# /4 ETKEN DEĞİŞİM ATOMU
# ─────────────────────────────────────────────────────────────────────────

def _degisim_atomlari(ilac, etkin, gecmis, metin):
    """API sarmalayıcı: _hep_etken_degisim_atomlari liste döndürür (2026-05
    refactor'ında tek-atom _hep_atom_etken_devam'ın yerini aldı)."""
    return _hep_etken_degisim_atomlari(
        _tr_upper(ilac), _tr_upper(etkin), gecmis, _tr_lower(metin))


def _gerekce_atomu(atomlar):
    """(4-e) değişim gerekçesi AND atomunu bul."""
    return next(a for a in atomlar if a.grup.startswith('(4-e)'))


def test_degisim_etken_ayni_devam_var():
    """Önceki etken VAR ve aktif etkenle aynı → değişim yok, tek VAR atomu."""
    atomlar = _degisim_atomlari(
        'BARACLUDE 0.5 MG', 'ENTEKAVIR',
        'kendi_eczane:BARACLUDE 0.5 MG ENTEKAVIR',
        'hbsag pozitif, tedavi devam ediyor.')
    print(f"[T10] /4 Etken aynı (devam): {len(atomlar)} atom, "
          f"durum={atomlar[0].durum.value}")
    assert len(atomlar) == 1
    assert atomlar[0].durum == SartDurumu.VAR


def test_degisim_farkli_etken_gerekce_var():
    """Etken farklı ama "24. hafta" + değişim gerekçesi metinde →
    VEYA grubunda VAR alt-yol + (4-e) gerekçe VAR."""
    atomlar = _degisim_atomlari(
        'VIREAD 245 MG', 'TENOFOVIR DISOPROKSIL',
        'kendi_eczane:ZEFFIX 100 MG LAMIVUDIN',
        '24. haftada HBV DNA ≥ 50 IU/ml — tedavi değişimi yapıldı.')
    veya_var = any(a.durum == SartDurumu.VAR for a in atomlar if a.veya_grubu)
    gerekce = _gerekce_atomu(atomlar)
    print(f"[T11] /4 Etken değişim + gerekçe: veya_grubu_var={veya_var}, "
          f"gerekçe={gerekce.durum.value}")
    assert veya_var
    assert gerekce.durum == SartDurumu.VAR


def test_degisim_farkli_etken_gerekce_yok_KE():
    """Etken farklı ve gerekçe yok → (4-e) gerekçe atomu KE + şartlı."""
    atomlar = _degisim_atomlari(
        'VIREAD 245 MG', 'TENOFOVIR DISOPROKSIL',
        'kendi_eczane:ZEFFIX 100 MG LAMIVUDIN',
        'Hasta tedaviye devam ediyor.')
    gerekce = _gerekce_atomu(atomlar)
    print(f"[T12] /4 Etken değişim + gerekçesiz: durum={gerekce.durum.value}, "
          f"sartli={gerekce.sartli_atom}")
    assert gerekce.durum == SartDurumu.KONTROL_EDILEMEDI
    assert gerekce.sartli_atom is True


# ─────────────────────────────────────────────────────────────────────────
# UÇ-UCA: Y1 BAŞLANGIÇ VS DEVAM SENARYOLARI
# ─────────────────────────────────────────────────────────────────────────

def _calistir(senaryo: str, ilac_sonuc: dict):
    rapor = kontrol_hepatit_atomik(ilac_sonuc)
    yolak = rapor.detaylar.get('yolak', '?') if rapor.detaylar else '?'
    tip = rapor.detaylar.get('recete_tipi', '?') if rapor.detaylar else '?'
    return rapor, yolak, tip


def test_y1_baslangic_dogru_doz_uygun():
    """Y1 BAŞLANGIÇ — Entekavir 0.5 mg doğru doz + HBV DNA + HAI 8 → UYGUN/SARTLI."""
    ilac_sonuc = {
        'ilac_adi': 'BARACLUDE 0.5 MG',
        'etkin_madde': 'ENTEKAVIR',
        'rapor_kodu': '06.01.01',
        'hasta_yasi': 45,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B yeni tanı. HBV DNA: 1.500.000 IU/ml. '
            'Karaciğer biyopsisi: HAI 8, fibrozis 3. ALT 3 ay arayla yüksek. '
            'FIB-4: 2.0. Gastroenteroloji uzmanı raporu. '
            'Tedaviye entekavir ile başlanması uygundur.'],
        'recete_teshisleri': ['B18.1 Diğer kronik viral hepatit'],
    }
    rapor, yolak, tip = _calistir('Y1 BAŞLANGIÇ', ilac_sonuc)
    print(f"\n[Y1-B] Başlangıç doğru doz: {rapor.sonuc.value} | "
          f"yolak={yolak} | tip={tip}")
    assert yolak == 'YOLAK1'
    assert tip == 'BASLANGIC'
    # Verdict UYGUN ya da SARTLI_UYGUN (KE'lik atomlar olabilir)
    assert rapor.sonuc != KontrolSonucu.UYGUN_DEGIL


def test_y1_devam_uygun():
    """Y1 DEVAM — devam metni + HBsAg+ rapor → UYGUN/SARTLI."""
    ilac_sonuc = {
        'ilac_adi': 'BARACLUDE 0.5 MG',
        'etkin_madde': 'ENTEKAVIR',
        'rapor_kodu': '06.01.01',
        'hasta_yasi': 50,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B, tedavinin devamı için yenileme raporu. '
            'HBsAg pozitif, Anti-HBs negatif. Klinik ve laboratuvar takibi '
            'sürdürülüyor. Gastroenteroloji uzman raporu.'],
        'recete_teshisleri': ['B18.1'],
    }
    rapor, yolak, tip = _calistir('Y1 DEVAM', ilac_sonuc)
    print(f"\n[Y1-D] Devam uygun: {rapor.sonuc.value} | yolak={yolak} | tip={tip}")
    assert yolak == 'YOLAK1'
    assert tip == 'DEVAM'
    assert rapor.sonuc != KontrolSonucu.UYGUN_DEGIL


def test_y1_belirsiz_bilgi_atomlar():
    """Y1 BELİRSİZ — sessiz metin + boş DB → atomlar (bilgi)'ye düşer,
    çekirdek atomlardan UYGUN."""
    ilac_sonuc = {
        'ilac_adi': 'BARACLUDE 0.5 MG',
        'etkin_madde': 'ENTEKAVIR',
        'rapor_kodu': '06.01.01',
        'hasta_yasi': 45,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik hepatit B. HBV DNA pozitif. Gastroenteroloji uzman raporu.'],
        'recete_teshisleri': ['B18.1'],
    }
    rapor, yolak, tip = _calistir('Y1 BELİRSİZ', ilac_sonuc)
    print(f"\n[Y1-X] Belirsiz: {rapor.sonuc.value} | yolak={yolak} | tip={tip}")
    assert yolak == 'YOLAK1'
    assert tip == 'BELIRSIZ'
    # BELIRSIZ'de başlangıç/devam atomları (bilgi) — verdict çekirdek
    # atomlardan (endikasyon, uzman rapor) belirlenmeli; UYGUN_DEGIL beklenmiyor
    assert rapor.sonuc != KontrolSonucu.UYGUN_DEGIL


def test_y1_devam_gerekçesiz_etken_degisimi_supheli():
    """Y1 DEVAM — etken farklı + gerekçesiz → ŞARTLI/ŞÜPHELİ."""
    # NOT: drug history sorgusu hasta_tc verilmediği için yapılamaz, bu yüzden
    # /4 atomu KE çıkar (gecmis_etken bilinmiyor). DEVAM tespiti metin
    # sinyaliyle yapılır.
    ilac_sonuc = {
        'ilac_adi': 'VIREAD 245 MG',
        'etkin_madde': 'TENOFOVIR DISOPROKSIL',
        'rapor_kodu': '06.01.01',
        'hasta_yasi': 50,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B, tedavi devam ediyor. HBsAg pozitif. '
            'Gastroenteroloji uzman raporu.'],
        'recete_teshisleri': ['B18.1'],
    }
    rapor, yolak, tip = _calistir('Y1 DEVAM gerekçesiz', ilac_sonuc)
    print(f"\n[Y1-D2] Devam gerekçesiz: {rapor.sonuc.value} | tip={tip}")
    assert tip == 'DEVAM'
    # /4 atomu KE → şartlı_uygun veya şüpheli; UYGUN_DEGIL bekleniyor değil
    assert rapor.sonuc != KontrolSonucu.UYGUN_DEGIL


# ─────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('═' * 70)
    print('SUT 4.2.13.1 — Y1 BAŞLANGIÇ ↔ DEVAM AYRIMI AKIL TESTİ')
    print('═' * 70)

    testler = [
        # Tespit unit testleri
        test_tespit_baslangic_metin,
        test_tespit_devam_metin,
        test_tespit_sessiz_metin_belirsiz,
        test_tespit_celiski_devam_kazanir,
        # /3 doz atomu
        test_doz_eriskin_dogru_entekavir,
        test_doz_eriskin_yanlis_entekavir,
        test_doz_eriskin_tdf_dogru,
        test_doz_eriskin_taf_dogru,
        test_doz_eriskin_listede_olmayan_etken,
        # Devam atomları
        test_hbsag_raporda_var,
        test_hbsag_raporda_sessiz_ke,
        test_sonlandirma_hbsag_neg_antihbs_pos,
        test_sonlandirma_durum_yok_NA,
        test_hbsag_pozitif_devam_meşru,
        # /4 etken değişim
        test_degisim_etken_ayni_devam_var,
        test_degisim_farkli_etken_gerekce_var,
        test_degisim_farkli_etken_gerekce_yok_KE,
        # Uç-uca Y1 entegrasyon
        test_y1_baslangic_dogru_doz_uygun,
        test_y1_devam_uygun,
        test_y1_belirsiz_bilgi_atomlar,
        test_y1_devam_gerekçesiz_etken_degisimi_supheli,
    ]
    print('\n=== TESPİT + ATOM + ENTEGRASYON TESTLERİ ===')
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
    print(f'SONUÇ: {basarili}/{len(testler)} senaryo başarılı')
    print('═' * 70)
    sys.exit(0 if basarili == len(testler) else 1)
