# -*- coding: utf-8 -*-
"""SUT 4.2.13 Hepatit atomik kontrol — akıl testi (10 senaryo).

12 yolağı kapsayan ana senaryoları doğrular:
    1. Yolak 1: Kronik B Erişkin UYGUN — HBV DNA + HAI yolu
    2. Yolak 1: Kronik B Erişkin UYGUN — Yol-b (>40 yaş + HBV DNA ≥20.000)
    3. Yolak 1: UYGUN DEĞİL — raporsuz
    4. Yolak 2: Çocuk B UYGUN — fibrozis ≥2 yolu
    5. Yolak 6: Akut B UYGUN — INR ≥1.5
    6. Yolak 8: Akut C UYGUN_DEĞİL — Ribavirin yasağı ihlali
    7. Yolak 9: Kronik C Erişkin Naive UYGUN — Nonsirotik + SVV
    8. Yolak 10: Kronik C Erişkin Exp UYGUN — NS5A almış + SVV
    9. Yolak 4: B + İmmünsüpresif UYGUN — HBsAg(+)
    10. Yolak 9: Kronik C Naive ŞÜPHELİ — siroz durumu sessiz (KE)
    + Parser unit testleri (HBV DNA, HCV RNA, Child-Pugh, genotip, FIB-4)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from recete_kontrol.base_kontrol import KontrolSonucu, SartDurumu
from recete_kontrol.hepatit_kontrol import (
    kontrol_hepatit_atomik,
    hep_parse_hbv_dna, hep_parse_hcv_rna, hep_parse_child_pugh,
    hep_parse_genotip, hep_parse_fib4, hep_parse_apri,
    hep_parse_alt_ust_sinir_orani, hep_parse_kompanse_dekompanse,
    hep_parse_hbeag, hep_parse_anti_hdv, hep_parse_inr, hep_parse_sarilik_sure,
)


# ─────────────────────────────────────────────────────────────────────────
# PARSER UNIT TESTLERİ
# ─────────────────────────────────────────────────────────────────────────

def test_parserlar():
    print("\n=== PARSER TESTLERİ ===")
    # HBV DNA
    v, _ = hep_parse_hbv_dna("HBV DNA: 50.000 IU/ml")
    assert v == 50000.0, f"Beklenen 50000, alınan {v}"
    print(f"  ✓ HBV DNA 50.000 IU/ml → {v}")
    v, b = hep_parse_hbv_dna("HBV DNA 1.5e6 IU/ml")
    assert v == 1500000.0, f"Beklenen 1.5e6, alınan {v}"
    print(f"  ✓ HBV DNA 1.5e6 IU/ml → {v}")
    v, b = hep_parse_hbv_dna("HBV-DNA 10000 kopya/ml")
    # 10000 kopya/ml ÷ 5 = 2000 IU/ml
    assert v == 2000.0, f"Beklenen 2000 (dönüştürülmüş), alınan {v}"
    print(f"  ✓ HBV DNA 10000 kopya/ml → {v} IU/ml (kopya→IU)")
    v, b = hep_parse_hbv_dna("HBV DNA pozitif")
    assert v == -1.0, f"Beklenen -1 (pozitif sentinel), alınan {v}"
    print(f"  ✓ HBV DNA pozitif (kalitatif) → sentinel {v}")

    # HCV RNA
    v, _ = hep_parse_hcv_rna("HCV RNA: 2500000 IU/ml")
    assert v == 2500000.0
    print(f"  ✓ HCV RNA 2.5M IU/ml → {v}")
    v, _ = hep_parse_hcv_rna("HCV RNA negatif")
    assert v == 0.0
    print(f"  ✓ HCV RNA negatif → {v}")

    # Child-Pugh
    assert hep_parse_child_pugh("Child-Pugh A") == 'A'
    assert hep_parse_child_pugh("child pugh B") == 'B'
    assert hep_parse_child_pugh("Child-Pugh skoru 10") == 'C'
    assert hep_parse_child_pugh("Child-Pugh skoru 5") == 'A'
    print("  ✓ Child-Pugh A/B/C skor→sınıf dönüşümü")

    # Genotip
    assert hep_parse_genotip("Genotip 1a") == '1a'
    assert hep_parse_genotip("genotip 3") == '3'
    print("  ✓ Genotip 1a / 3")

    # FIB-4 / APRI
    assert hep_parse_fib4("FIB-4: 2.3") == 2.3
    assert hep_parse_apri("APRI 0.8") == 0.8
    print("  ✓ FIB-4 = 2.3, APRI = 0.8")

    # ALT/üst sınır oranı
    r = hep_parse_alt_ust_sinir_orani("ALT normalin 2.5 katı")
    assert r == 2.5, f"Beklenen 2.5, alınan {r}"
    r = hep_parse_alt_ust_sinir_orani("ALT > 2x üst sınır")
    assert r == 2.0
    print(f"  ✓ ALT oranı: 2.5x ve 2x")

    # Siroz durum
    assert hep_parse_kompanse_dekompanse("dekompanse siroz, Child-Pugh B") == 'dekompanse'
    assert hep_parse_kompanse_dekompanse("nonsirotik hasta") == 'nonsirotik'
    assert hep_parse_kompanse_dekompanse("kompanse sirotik") == 'kompanse'
    print("  ✓ Siroz durum: nonsirotik / kompanse / dekompanse")

    # HBeAg
    assert hep_parse_hbeag("HBeAg pozitif") == 'POZ'
    assert hep_parse_hbeag("HBeAg(-)") == 'NEG'
    print("  ✓ HBeAg POZ / NEG")

    # Anti-HDV
    assert hep_parse_anti_hdv("Anti-HDV pozitif") == 'POZ'
    print("  ✓ Anti-HDV POZ")

    # INR + sarılık süre
    assert hep_parse_inr("INR 1.8") == 1.8
    assert hep_parse_sarilik_sure("sarılık süresi 5 hafta") == 5.0
    print("  ✓ INR=1.8, sarılık=5 hafta")

    # Cümle-sonu noktası (greedy [\d.,]+ tuzağı) — sondaki ayırıcı kırpılır
    assert hep_parse_fib4("Değerlendirmede FIB-4: 1.0.") == 1.0
    assert hep_parse_apri("APRI skoru 0,3.") == 0.3
    assert hep_parse_fib4("FIB-4 2,1, ileri fibrozis.") == 2.1
    v, _ = hep_parse_hbv_dna("HBV DNA: 50.000 IU/ml.")
    assert v == 50000.0, f"Beklenen 50000, alınan {v}"
    # Baştaki ayırıcı bozulmamalı: ".5" → 0.5
    assert hep_parse_apri("APRI .5") == 0.5
    print("  ✓ Cümle-sonu noktası: '1.0.'→1.0, '0,3.'→0.3, '50.000.'→50000, "
          "'.5'→0.5")


# ─────────────────────────────────────────────────────────────────────────
# YOLAK SENARYOLARI
# ─────────────────────────────────────────────────────────────────────────

def _calistir_ozet(senaryo_adi: str, ilac_sonuc: dict) -> tuple:
    """Test koşusu — kısa özet döndür."""
    rapor = kontrol_hepatit_atomik(ilac_sonuc)
    yolak = rapor.detaylar.get('yolak', '?') if rapor.detaylar else '?'
    return (rapor.sonuc, rapor.mesaj[:120], yolak,
            len(rapor.sartlar) if rapor.sartlar else 0)


def test_1_kronik_b_eriskin_uygun_HAI_yolu():
    """SENARYO 1 — Yolak 1: Kronik B Erişkin UYGUN (HAI ≥6 yolu)."""
    ilac_sonuc = {
        'ilac_adi': 'BARACLUDE 0.5 MG',
        'etkin_madde': 'ENTEKAVIR',
        'rapor_kodu': '06.01.01',
        'hasta_yasi': 45,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B tanısı. HBV DNA: 1.500.000 IU/ml. '
            'Karaciğer biyopsisi: HAI 8, fibrozis 3. Gastroenteroloji '
            'uzmanı tarafından raporlanmıştır. Tedaviye entekavir ile '
            'başlanması uygundur.'],
        'recete_teshisleri': ['B18.1 Diğer kronik viral hepatit'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 1", ilac_sonuc)
    print(f"\n[1] Kronik B Erişkin UYGUN (HAI): {sonuc.value} | yolak={yolak} | "
          f"{sn} şart")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK1', f"Yolak beklenen YOLAK1, alınan {yolak}"
    assert sonuc in (KontrolSonucu.UYGUN, KontrolSonucu.SARTLI_UYGUN), \
        f"Beklenen UYGUN/ŞARTLI_UYGUN, alınan {sonuc.value}"


def test_2_kronik_b_yolb_yas40_HBVDNA_20000():
    """SENARYO 2 — Yolak 1: Yol-b (>40 yaş + HBV DNA ≥ 20.000)."""
    ilac_sonuc = {
        'ilac_adi': 'VIREAD 245 MG',
        'etkin_madde': 'TENOFOVIR DISOPROKSIL FUMARAT',
        'rapor_kodu': '06.01',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'ENFEKSIYON HASTALIKLARI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B. Hasta 55 yaşında. HBV DNA: 1.000.000 IU/ml. '
            'Biyopsi yapılmadan tedaviye başlanması uygundur (4.2.13.1(1)(b)). '
            'Enfeksiyon Hastalıkları uzmanı raporu.'],
        'recete_teshisleri': ['B18.1'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 2", ilac_sonuc)
    print(f"\n[2] Kronik B Yol-b (>40 yaş): {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK1'


def test_3_raporsuz():
    """SENARYO 3 — Raporsuz reçete → UYGUN_DEGIL."""
    ilac_sonuc = {
        'ilac_adi': 'BARACLUDE 0.5 MG',
        'etkin_madde': 'ENTEKAVIR',
        'rapor_kodu': '',
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 3", ilac_sonuc)
    print(f"\n[3] Raporsuz: {sonuc.value} | {mesaj}")
    assert sonuc == KontrolSonucu.UYGUN_DEGIL


def test_4_cocuk_b_fibrozis_yolu():
    """SENARYO 4 — Yolak 2: Çocuk B, fibrozis ≥2 (ALT'siz)."""
    ilac_sonuc = {
        'ilac_adi': 'VIREAD 245 MG',
        'etkin_madde': 'TENOFOVIR DISOPROKSIL',
        'rapor_kodu': '06.01',
        'hasta_yasi': 14,
        'doktor_uzmanligi': 'COCUK HASTALIKLARI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B (14 yaş). HBV DNA: 100.000 IU/ml. '
            'Karaciğer biyopsisi: fibrozis 3. Gastroenteroloji uzman raporu. '
            'Tedaviye TDF ile başlanması uygundur.'],
        'recete_teshisleri': ['B18.1'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 4", ilac_sonuc)
    print(f"\n[4] Çocuk B (fibrozis): {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK2'


def test_5_akut_b_INR_yuksek():
    """SENARYO 5 — Yolak 6: Akut B + ciddi klinik (INR ≥1.5)."""
    ilac_sonuc = {
        'ilac_adi': 'VIREAD 245 MG',
        'etkin_madde': 'TENOFOVIR',
        'rapor_kodu': '06.01',
        'hasta_yasi': 35,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Akut Hepatit B tanısı. Ciddi akut klinik: INR 1.8, '
            'sarılık süresi 5 hafta. Gastroenteroloji uzmanı raporu. '
            'Antiviral tedavi başlanması uygundur.'],
        'recete_teshisleri': ['B16.9 Akut Hepatit B'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 5", ilac_sonuc)
    print(f"\n[5] Akut B (INR yüksek): {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK6'


def test_6_akut_c_ribavirin_yasak():
    """SENARYO 6 — Yolak 8: Akut C, Ribavirin YASAK ihlali → UYGUN_DEGIL."""
    ilac_sonuc = {
        'ilac_adi': 'PEGASYS 180 MCG',
        'etkin_madde': 'PEGINTERFERON ALFA-2A',
        'rapor_kodu': '06.01',
        'hasta_yasi': 40,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Akut Hepatit C tanısı. HCV RNA pozitif. Pegile interferon alfa '
            'monoterapi tedavisi başlanmıştır. Gastroenteroloji uzmanı raporu.'],
        'recete_teshisleri': ['B17.1'],
        # Ribavirin reçetede → YASAK
        'recete_ilaclari': [
            {'ad': 'PEGASYS 180 MCG'},
            {'ad': 'COPEGUS 200 MG'},  # Ribavirin — YASAK
        ],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 6", ilac_sonuc)
    print(f"\n[6] Akut C + Ribavirin (YASAK ihlali): {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK8'
    # Ribavirin yasağı YOK olduğu için UYGUN_DEGIL bekleniyor
    assert sonuc == KontrolSonucu.UYGUN_DEGIL, \
        f"Ribavirin yasağı tetiklenmeli; alınan: {sonuc.value}"


def test_7_kronik_c_eriskin_naive_SVV():
    """SENARYO 7 — Yolak 9: Erişkin C Naive, Nonsirotik + SVV."""
    ilac_sonuc = {
        'ilac_adi': 'VOSEVI 400/100/100 MG',
        'etkin_madde': 'SOFOSBUVIR+VELPATASVIR+VOXILAPREVIR',
        'rapor_kodu': '06.01',
        'hasta_yasi': 50,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit C tanısı (3. basamak üniversite hastanesi). '
            'HCV RNA pozitif: 1.500.000 IU/ml. Nonsirotik hasta. '
            'Hasta daha önce hepatit C tedavisi almamıştır (naive). '
            'Gastroenteroloji uzmanı raporu. Planlanan tedavi: '
            'Sofosbuvir+Velpatasvir+Voxilaprevir 8 hafta.'],
        'recete_teshisleri': ['B18.2 Kronik viral hepatit C'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 7", ilac_sonuc)
    print(f"\n[7] Kronik C Erişkin Naive (SVV nonsirot): {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK9'


def test_8_kronik_c_eriskin_exp_NS5A_almis():
    """SENARYO 8 — Yolak 10: Erişkin C Deneyimli, NS5A almış + SVV."""
    ilac_sonuc = {
        'ilac_adi': 'VOSEVI',
        'etkin_madde': 'SOFOSBUVIR+VELPATASVIR+VOXILAPREVIR',
        'rapor_kodu': '06.01',
        'hasta_yasi': 55,
        'doktor_uzmanligi': 'ENFEKSIYON',
        'rapor_aciklamalari': [
            'Kronik Hepatit C, 3. basamak hastane. HCV RNA pozitif. '
            'Kompanse Child-Pugh A. Genotip 1b. Hasta daha önce ledipasvir '
            '(NS5A inhibitörü) tedavisi almış; nüks olmuştur. '
            'Gastroenteroloji uzman raporu. Planlanan tedavi: '
            'Sofosbuvir+Velpatasvir+Voxilaprevir 12 hafta.'],
        'recete_teshisleri': ['B18.2'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 8", ilac_sonuc)
    print(f"\n[8] Kronik C Erişkin Deneyimli (NS5A almış+SVV): "
          f"{sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK10'


def test_9_b_immunsupresif_HBsAg_pozitif():
    """SENARYO 9 — Yolak 4: HBsAg(+) + immünsupresif (örnek: rituximab)."""
    ilac_sonuc = {
        'ilac_adi': 'VIREAD',
        'etkin_madde': 'TENOFOVIR DISOPROKSIL',
        'rapor_kodu': '06.01',
        'hasta_yasi': 50,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Hasta lenfoma nedeniyle rituximab + kemoterapi alıyor. '
            'HBsAg pozitif. Profilaktik antiviral tedavi başlanması '
            'uygundur (4.2.13.1.2). Tedavi süresince + sonraki 12 ay TDF.'],
        'recete_teshisleri': [],
        'recete_ilaclari': [
            {'ad': 'VIREAD 245 MG'},
            {'ad': 'RITUXIMAB 100 MG'},
        ],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 9", ilac_sonuc)
    print(f"\n[9] B+İmmünsüpresif (HBsAg+ + rituximab): "
          f"{sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK4'


def test_10_kronik_c_sessiz_siroz_KE():
    """SENARYO 10 — Yolak 9: Siroz durumu sessiz (KE) → ŞÜPHELİ."""
    ilac_sonuc = {
        'ilac_adi': 'EPCLUSA',
        'etkin_madde': 'SOFOSBUVIR+VELPATASVIR',
        'rapor_kodu': '06.01',
        'hasta_yasi': 50,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit C. HCV RNA pozitif. Naive. Sofosbuvir+Velpatasvir.'
            # Siroz durumu BELİRTİLMEMİŞ → sessizlik → KE (örtük kabul yasak)
        ],
        'recete_teshisleri': ['B18.2'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 10", ilac_sonuc)
    print(f"\n[10] Kronik C sessiz siroz: {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK9'
    # Sessizlik → ŞÜPHELİ/SARTLI_UYGUN bekleniyor (UYGUN olmamalı)
    assert sonuc in (KontrolSonucu.KONTROL_EDILEMEDI,
                     KontrolSonucu.SARTLI_UYGUN,
                     KontrolSonucu.UYGUN_DEGIL), \
        f"Sessiz siroz → KE bekleniyor; alınan: {sonuc.value}"


# ─────────────────────────────────────────────────────────────────────────
# DİSPATCHER / KAPSAM TESTLERİ
# ─────────────────────────────────────────────────────────────────────────

def test_11_hiv_ilaci_atlanir():
    """HIV ilacı (dolutegravir) → ATLANDI (Hepatit kapsamı dışı)."""
    from recete_kontrol.hepatit_kontrol import _hep_etken_tip
    tip = _hep_etken_tip('TIVICAY', 'DOLUTEGRAVIR')
    print(f"\n[11] HIV ilacı tip tespiti: {tip}")
    assert tip == 'NONE', f"HIV → NONE, alınan: {tip}"


def test_12_delta_hepatit():
    """SENARYO 12 — Yolak 7: Delta hepatit (Anti-HDV+)."""
    ilac_sonuc = {
        'ilac_adi': 'PEGASYS 180 MCG',
        'etkin_madde': 'PEGINTERFERON ALFA-2A',
        'rapor_kodu': '06.01',
        'hasta_yasi': 40,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Delta ajanlı Kronik Hepatit B. Anti-HDV pozitif. HBV DNA: 5000 IU/ml. '
            'Pegile interferon tedavisi planlanmıştır. Gastroenteroloji uzmanı raporu.'],
        'recete_teshisleri': ['B17.0 Akut delta hepatit'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 12", ilac_sonuc)
    print(f"\n[12] Kronik Delta: {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK7'


def test_13_aile_hekimi_y1_raporlu():
    """SUT 4.1.1/8: Aile hekimi raporlu reçetede 4.2.13.1 yazabilir.
    Kronik B + HBV oral + aile hekimi → reçete yetkisi VAR."""
    ilac_sonuc = {
        'ilac_adi': 'VIREAD 245 MG',
        'etkin_madde': 'TENOFOVIR DISOPROKSIL',
        'rapor_kodu': '14.1',
        'doktor_uzmanligi': 'AILE HEKIMI',
        'hasta_dogum_tarihi': '1970-01-01',
        'rapor_aciklamalari': [
            'Kronik Hepatit B. HBV DNA 50000 IU/ml. HAI: 7. Fibrozis: 3. '
            'Gastroenteroloji uzmanı raporu.'],
        'recete_teshisleri': ['B18.1 Kronik Hepatit B'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 13", ilac_sonuc)
    print(f"\n[13] Aile hekimi Y1 raporlu: {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK1'
    # Aile hekimi yetkili olmalı (SUT 4.1.1/8) — UYGUN_DEGIL DEĞİL
    assert sonuc.value != 'uygun_degil', \
        f"Aile hekimi raporlu Y1'de UYGUN_DEGIL beklenmiyor: {mesaj}"


def test_14_aile_hekimi_hcv_yetkisiz():
    """SUT 4.1.1/8: Aile hekimi HCV (4.2.13.3) yazamaz — sadece 4.2.13.1/4.2.13.2.
    Aile hekimi + HCV DAA → reçete yetkisi YOK."""
    ilac_sonuc = {
        'ilac_adi': 'EPCLUSA 400/100 MG',
        'etkin_madde': 'SOFOSBUVIR+VELPATASVIR',
        'rapor_kodu': '14.2',
        'doktor_uzmanligi': 'AILE HEKIMI',
        'hasta_dogum_tarihi': '1970-01-01',
        'rapor_aciklamalari': [
            'Kronik Hepatit C nonsirotik. HCV RNA pozitif. Genotip 1a. '
            'Gastroenteroloji uzmanı raporu.'],
        'recete_teshisleri': ['B18.2 Kronik Hepatit C'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 14", ilac_sonuc)
    print(f"\n[14] Aile hekimi HCV yetkisiz: {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK9'
    # HCV için aile hekimi yetkisiz olmalı
    assert sonuc.value == 'uygun_degil', \
        f"HCV'de aile hekimi UYGUN_DEGIL bekleniyor: {mesaj}"


def test_16_y1_pegile_ifn_ust_or_kolu():
    """SUT 4.2.13.1(2)(a) — PIF kolu üst-VEYA çiftinin alternatifi olarak
    çalışmalı: yol-a/yol-b atomları YOK olsa bile PIF kolu (ALT>2×ÜS +
    HBeAg+DNA eşik) tam ise UYGUN/SARTLI_UYGUN. Bug fix doğrulama testi."""
    ilac_sonuc = {
        'ilac_adi': 'PEGASYS 180 MCG',
        'etkin_madde': 'PEGINTERFERON ALFA-2A',
        'rapor_kodu': '06.01',
        'hasta_yasi': 35,
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'rapor_aciklamalari': [
            'Kronik Hepatit B. ALT 220 U/L (normalin üst sınırı 40 U/L, '
            'oranı 5.5×). HBeAg negatif. HBV DNA: 1.500.000 IU/ml '
            '(7.5×10⁶ kopya/ml — 10⁷ eşik altı). Pegile interferon '
            'tedavisi başlanması uygundur. Gastroenteroloji uzmanı raporu.'],
        'recete_teshisleri': ['B18.1 Diğer kronik viral hepatit'],
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 16", ilac_sonuc)
    print(f"\n[16] Y1 Pegile IFN PIF kolu: {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK1', f"Y1 bekleniyor, geldi: {yolak}"
    # PIF kolu üst-VEYA içinde olduğu için yol-a/yol-b YOK olsa bile UYGUN
    # ya da SARTLI_UYGUN çıkmalı (UYGUN_DEGIL OLMAMALI)
    assert sonuc != KontrolSonucu.UYGUN_DEGIL, \
        f"PIF kolu yol-a/yol-b alternatifi — UYGUN_DEGIL olmamalı: {mesaj}"


def test_15_y11_tek_basina_ribavirin_yasak():
    """SUT 4.2.13.3.2.B(2): Tek başına Ribavirin endikasyonu YOKTUR.
    Çocuk + sadece Ribavirin (IFN/PegIFN/DAA yok) → UYGUN_DEGIL."""
    ilac_sonuc = {
        'ilac_adi': 'COPEGUS 200 MG',
        'etkin_madde': 'RIBAVIRIN',
        'rapor_kodu': '14.3',
        'doktor_uzmanligi': 'GASTROENTEROLOJI',
        'hasta_yasi': 14,  # çocuk
        'rapor_aciklamalari': [
            'Kronik Hepatit C çocuk hasta. HCV RNA pozitif. Genotip 3. '
            '2. basamak gastroenteroloji raporu.'],
        'recete_teshisleri': ['B18.2 Kronik Hepatit C'],
        'recete_ilaclari': [{'ad': 'COPEGUS 200 MG'}],  # SADECE Ribavirin
    }
    sonuc, mesaj, yolak, sn = _calistir_ozet("Senaryo 15", ilac_sonuc)
    print(f"\n[15] Y11 tek başına Rib yasağı: {sonuc.value} | yolak={yolak}")
    print(f"    Mesaj: {mesaj}")
    assert yolak == 'YOLAK11', f"Y11 bekleniyor, geldi: {yolak}"
    assert sonuc.value == 'uygun_degil', \
        f"Tek başına Rib UYGUN_DEGIL bekleniyor: {mesaj}"


# ─────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('═' * 70)
    print('SUT 4.2.13 HEPATİT — ATOMİK 12 YOLAK AKIL TESTİ')
    print('═' * 70)

    # Parser testleri
    test_parserlar()

    # Senaryo testleri
    senaryolar = [
        test_1_kronik_b_eriskin_uygun_HAI_yolu,
        test_2_kronik_b_yolb_yas40_HBVDNA_20000,
        test_3_raporsuz,
        test_4_cocuk_b_fibrozis_yolu,
        test_5_akut_b_INR_yuksek,
        test_6_akut_c_ribavirin_yasak,
        test_7_kronik_c_eriskin_naive_SVV,
        test_8_kronik_c_eriskin_exp_NS5A_almis,
        test_9_b_immunsupresif_HBsAg_pozitif,
        test_10_kronik_c_sessiz_siroz_KE,
        test_11_hiv_ilaci_atlanir,
        test_12_delta_hepatit,
        test_13_aile_hekimi_y1_raporlu,
        test_14_aile_hekimi_hcv_yetkisiz,
        test_15_y11_tek_basina_ribavirin_yasak,
        test_16_y1_pegile_ifn_ust_or_kolu,
    ]
    basarili = 0
    basarisiz = []
    for f in senaryolar:
        try:
            f()
            basarili += 1
        except AssertionError as exc:
            basarisiz.append((f.__name__, str(exc)))
            print(f"  ✗ {f.__name__}: {exc}")
        except Exception as exc:
            basarisiz.append((f.__name__, f'EXCEPTION: {exc}'))
            print(f"  ✗ {f.__name__}: EXCEPTION {exc}")
            import traceback
            traceback.print_exc()
    print()
    print('═' * 70)
    print(f'SONUÇ: {basarili}/{len(senaryolar)} senaryo başarılı')
    if basarisiz:
        print(f'BAŞARISIZ ({len(basarisiz)}):')
        for ad, neden in basarisiz:
            print(f'  - {ad}: {neden}')
    print('═' * 70)
    sys.exit(0 if not basarisiz else 1)
