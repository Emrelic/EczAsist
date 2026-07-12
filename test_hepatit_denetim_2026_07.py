# -*- coding: utf-8 -*-
"""SUT 4.2.13 Hepatit — 2026-07 denetim düzeltmeleri regresyon testleri.

Bu testler denetimde bulunan YANLIŞ-ONAY (false-positive) senaryolarının
artık doğru sonuç verdiğini kanıtlar. Her senaryo düzeltmeden ÖNCE hatalı
UYGUN üretiyordu.

  R1  Y6 Akut B — INR var ama sarılık yok → artık UYGUN değil (sarılık zorunlu)
  R2  Y6 Akut B — sarılık ≤4 hafta açık → UYGUN DEĞİL
  R3  Y9 HCV — dekompanse hasta + SVV rejimi → UYGUN DEĞİL (endikasyon kilidi)
  R4  Y1 Kronik B — tek başına ALT (düşük fibrozis/skor) → UYGUN DEĞİL
  R5  Y2 Çocuk B — 10 yaşına Entekavir (yalnız 16-18) → UYGUN DEĞİL
  R6  Y2 Çocuk B — 10 yaşına Lamivudin (2-18) → yaş-doz engellemez
  R7  Y10 HCV — "deneyimli" ama tür belirsiz → NS5A-naive dalı otomatik geçmez
  R8  K3  Y11/Y12 çocuk C — 2./3. basamak atomu mevcut
  R9  Y9 HCV — nonsirotik + SVV (meşru) → UYGUN/ŞARTLI (regresyon koruması)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recete_kontrol.base_kontrol import KontrolSonucu
from recete_kontrol.hepatit_kontrol import kontrol_hepatit_atomik


def _calistir(ilac_sonuc: dict):
    rapor = kontrol_hepatit_atomik(ilac_sonuc)
    yolak = rapor.detaylar.get('yolak', '?') if rapor.detaylar else '?'
    return rapor, yolak


def test_r1_y6_sarilik_yok_uygun_degil():
    """Y6: ciddi lab (INR 1.6) var ama sarılık raporda yok → UYGUN olmamalı."""
    r, yolak = _calistir({
        'ilac_adi': 'VIREAD 245 MG',
        'etkin_madde': 'TENOFOVIR DISOPROKSIL FUMARAT',
        'rapor_kodu': '06.01',
        'hasta_yasi': 40,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Akut Hepatit B. INR 1.6. Gastroenteroloji uzman raporu. '
            'Tedaviye tenofovir ile başlanması uygundur.'],
        'recete_teshisleri': ['B16 Akut viral hepatit B'],
    })
    print(f"\n[R1] Y6 sarılık yok: {r.sonuc.value} | yolak={yolak}")
    assert yolak == 'YOLAK6', f"Beklenen YOLAK6, alınan {yolak}"
    assert r.sonuc != KontrolSonucu.UYGUN, \
        'Sarılık>4hafta zorunlu iken salt INR ile UYGUN verilmemeli'


def test_r2_y6_sarilik_kisa_uygun_degil():
    """Y6: INR 1.6 + sarılık açıkça 2 hafta (≤4) → UYGUN DEĞİL."""
    r, yolak = _calistir({
        'ilac_adi': 'VIREAD 245 MG',
        'etkin_madde': 'TENOFOVIR DISOPROKSIL FUMARAT',
        'rapor_kodu': '06.01',
        'hasta_yasi': 40,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Akut Hepatit B. INR 1.6. Sarılık süresi 2 hafta. '
            'Gastroenteroloji uzman raporu.'],
        'recete_teshisleri': ['B16'],
    })
    print(f"[R2] Y6 sarılık 2 hafta: {r.sonuc.value} | yolak={yolak}")
    assert yolak == 'YOLAK6'
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL, \
        'Sarılık 2 hafta (≤4) → sarılık şartı YOK → UYGUN DEĞİL olmalı'


def test_r3_y9_dekompanse_svv_uygun_degil():
    """Y9: dekompanse Child-B hasta + SVV rejimi → endikasyon kilidi UYGUN DEĞİL.
    (K1: eskiden rejim OR'u nonsirotik grubunu geçiriyordu.)"""
    r, yolak = _calistir({
        'ilac_adi': 'VOSEVI',
        'etkin_madde': 'SOFOSBUVIR VELPATASVIR VOKSILAPREVIR',
        'rapor_kodu': '06.01',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit C. Dekompanse Child-Pugh B karaciğer sirozu. '
            'Asit mevcut. HCV RNA pozitif. Daha önce tedavi almamış. '
            'Üniversite hastanesi gastroenteroloji uzman raporu.'],
        'recete_teshisleri': ['B18.2 Kronik viral hepatit C'],
    })
    print(f"[R3] Y9 dekompanse+SVV: {r.sonuc.value} | yolak={yolak}")
    assert yolak == 'YOLAK9'
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL, \
        'Dekompanse hastada SVV (SL+RBV değil) → tüm dallar YOK → UYGUN DEĞİL'


def test_r4_y1_alt_tek_basina_uygun_degil():
    """Y1: HBV DNA≥2000 + ALT yüksek ama HAI/fibrozis düşük + FIB-4/APRI düşük
    → yol-a YOK, yol-b YOK → UYGUN DEĞİL. (Bulgu 1: eski düz-OR ALT'ı tek başına
    geçiriyordu.)"""
    r, yolak = _calistir({
        'ilac_adi': 'BARACLUDE 0.5 MG',
        'etkin_madde': 'ENTEKAVIR',
        'rapor_kodu': '06.01.01',
        'hasta_yasi': 30,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B. HBV DNA: 5.000 IU/ml. '
            'ALT normalin üst sınırının 1,5 katı, 3 ay arayla tekrarlandı. '
            'Karaciğer biyopsisi HAI 3 ve fibrozis 1 olarak raporlandı. '
            'FIB-4 skoru 1,0 olup APRI skoru 0,3 bulunmuştur. '
            'Gastroenteroloji uzman raporu. Tedaviye başlanması.'],
        'recete_teshisleri': ['B18.1'],
    })
    print(f"[R4] Y1 ALT tek başına: {r.sonuc.value} | yolak={yolak}")
    assert yolak == 'YOLAK1'
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL, \
        'ALT yüksek ama fibrozis/skor düşük → yol-a YOK, yol-b YOK → UYGUN DEĞİL'


def test_r5_y2_cocuk_etv_yas_disi_uygun_degil():
    """Y2: 10 yaşındaki çocuğa Entekavir (yalnız 16-18) → UYGUN DEĞİL."""
    r, yolak = _calistir({
        'ilac_adi': 'BARACLUDE 0.5 MG',
        'etkin_madde': 'ENTEKAVIR',
        'rapor_kodu': '06.01.01',
        'hasta_yasi': 10,
        'doktor_uzmanligi': 'COCUK SAGLIGI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B. HBV DNA: 50.000 IU/ml. Fibrozis 2. '
            'Çocuk sağlığı ve hastalıkları uzman raporu.'],
        'recete_teshisleri': ['B18.1'],
    })
    print(f"[R5] Y2 çocuk 10y + ETV: {r.sonuc.value} | yolak={yolak}")
    assert yolak == 'YOLAK2'
    assert r.sonuc == KontrolSonucu.UYGUN_DEGIL, \
        'ETV 16-18 yaş içindir; 10 yaşta ilaç-yaş şartı YOK → UYGUN DEĞİL'


def test_r6_y2_cocuk_lam_yas_ici_engellemez():
    """Y2: 10 yaşına Lamivudin (2-18) → ilaç-yaş engellemez (UYGUN DEĞİL değil)."""
    r, yolak = _calistir({
        'ilac_adi': 'ZEFFIX 100 MG',
        'etkin_madde': 'LAMIVUDIN',
        'rapor_kodu': '06.01.01',
        'hasta_yasi': 10,
        'doktor_uzmanligi': 'COCUK SAGLIGI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B. HBV DNA: 50.000 IU/ml. Fibrozis 2. '
            'Çocuk sağlığı ve hastalıkları uzman raporu.'],
        'recete_teshisleri': ['B18.1'],
    })
    print(f"[R6] Y2 çocuk 10y + LAM: {r.sonuc.value} | yolak={yolak}")
    assert yolak == 'YOLAK2'
    assert r.sonuc != KontrolSonucu.UYGUN_DEGIL, \
        'LAM 2-18 yaş için uygun; 10 yaşta ilaç-yaş şartı engellememeli'


def test_r7_y10_tur_belirsiz_naive_dali_gecmez():
    """Y10: "tedavi deneyimli" ama NS5A/proteaz türü belirsiz → NS5A-naive
    (EX1) dalı otomatik VAR olmamalı (K4 örtük kabul yasağı)."""
    r, yolak = _calistir({
        'ilac_adi': 'VOSEVI',
        'etkin_madde': 'SOFOSBUVIR VELPATASVIR VOKSILAPREVIR',
        'rapor_kodu': '06.01',
        'hasta_yasi': 50,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit C. Nonsirotik. HCV RNA pozitif. '
            'Hasta tedavi deneyimli (önceki tedavi türü belirtilmemiş). '
            'Üniversite hastanesi gastroenteroloji uzman raporu.'],
        'recete_teshisleri': ['B18.2'],
    })
    print(f"[R7] Y10 tür belirsiz: {r.sonuc.value} | yolak={yolak}")
    assert yolak == 'YOLAK10'
    assert r.sonuc != KontrolSonucu.UYGUN, \
        'NS5A durumu belirsizken izinli dal otomatik UYGUN vermemeli (KE→şüpheli)'


def test_r8_cocuk_c_2_3_basamak_atomu_var():
    """K3: Y11 (çocuk C naive) sartlar listesinde 2./3. basamak atomu olmalı."""
    r, yolak = _calistir({
        'ilac_adi': 'MAVIRET',
        'etkin_madde': 'GLEKAPREVIR PIBRENTASVIR',
        'rapor_kodu': '06.01',
        'hasta_yasi': 14,
        'doktor_uzmanligi': 'COCUK SAGLIGI',
        'rapor_aciklamalari': [
            'Kronik Hepatit C. HCV RNA pozitif. Genotip 1. Nonsirotik. '
            'Çocuk sağlığı uzman raporu.'],
        'recete_teshisleri': ['B18.2'],
    })
    print(f"[R8] Y11 basamak atomu: {r.sonuc.value} | yolak={yolak}")
    assert yolak == 'YOLAK11'
    basamak_var = any('basamak' in (s.ad + ' ' + (s.grup or '')).lower()
                      for s in (r.sartlar or []))
    assert basamak_var, '2./3. basamak sağlık kurumu atomu Y11 sartlar\'ında yok'


def test_r9_y9_nonsirotik_svv_mesru():
    """Y9: nonsirotik + SVV (meşru senaryo) → UYGUN/ŞARTLI (düzeltme meşru
    reçeteyi bloklamamalı)."""
    r, yolak = _calistir({
        'ilac_adi': 'VOSEVI',
        'etkin_madde': 'SOFOSBUVIR VELPATASVIR VOKSILAPREVIR',
        'rapor_kodu': '06.01',
        'hasta_yasi': 45,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit C. Nonsirotik. HCV RNA pozitif. '
            'Daha önce tedavi almamış (naive). '
            'İkinci basamak gastroenteroloji uzman raporu.'],
        'recete_teshisleri': ['B18.2'],
    })
    print(f"[R9] Y9 nonsirotik+SVV: {r.sonuc.value} | yolak={yolak}")
    assert yolak == 'YOLAK9'
    assert r.sonuc != KontrolSonucu.UYGUN_DEGIL, \
        'Nonsirotik + SVV meşru → UYGUN DEĞİL verilmemeli'


if __name__ == '__main__':
    print('═' * 70)
    print('SUT 4.2.13 HEPATİT — 2026-07 DENETİM DÜZELTMELERİ REGRESYON TESTİ')
    print('═' * 70)
    testler = [
        test_r1_y6_sarilik_yok_uygun_degil,
        test_r2_y6_sarilik_kisa_uygun_degil,
        test_r3_y9_dekompanse_svv_uygun_degil,
        test_r4_y1_alt_tek_basina_uygun_degil,
        test_r5_y2_cocuk_etv_yas_disi_uygun_degil,
        test_r6_y2_cocuk_lam_yas_ici_engellemez,
        test_r7_y10_tur_belirsiz_naive_dali_gecmez,
        test_r8_cocuk_c_2_3_basamak_atomu_var,
        test_r9_y9_nonsirotik_svv_mesru,
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
    print(f'SONUÇ: {basarili}/{len(testler)} senaryo başarılı')
    print('═' * 70)
    sys.exit(0 if basarili == len(testler) else 1)
