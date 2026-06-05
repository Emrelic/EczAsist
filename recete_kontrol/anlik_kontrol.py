# -*- coding: utf-8 -*-
"""Anlık Reçete Kontrolü — birleşik tekil kontrol dispatcher'ı.

Botanik EOS'a yeni reçete kaydedildiğinde (periyodik SELECT-polling ile tespit)
her ilaç kalemini DOĞRU SUT kontrolüne yönlendirip tek bir KontrolRaporu üretir.

Yönlendirme önceliği:
  1) 4.2.9.A ESA (eritropoietin/darbepo/Mircera/roksadustat) — özel modül
  2) 4.2.14.B kanser/hormon + G-CSF — özel modül
  3) 4.2.1.C-1 Anti-TNF + 4.2.12.B spesifik olmayan immünglobulin — özel modül
  4) Genel master dispatcher (sut_kontrolleri.sut_kontrol_yap) — kategori tespit
     + KATEGORI_KONTROL_FONKSIYONU haritası (diyabet/statin/hepatit/klop/...)

⚠️ Botanik EOS kırmızı çizgisi: bu modül DB'ye yazmaz; yalnızca verilen
ilac_sonuc dict'i üzerinde saf hesaplama yapar.
"""

from __future__ import annotations

import importlib
from typing import Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import KontrolRaporu, KontrolSonucu

# Uyarı çıkaran sonuçlar (kullanıcı kuralı 2026-06-04: UYGUN DEĞİL + TIBBEN +
# ŞÜPHELİ + ŞARTLI). UYGUN / DİĞER RAPOR UYGUN / ATLANDI sessiz geçer.
UYARI_SONUCLARI = {
    KontrolSonucu.UYGUN_DEGIL,
    KontrolSonucu.TIBBEN_UYGUN_DEGIL,
    KontrolSonucu.KONTROL_EDILEMEDI,   # ŞÜPHELİ
    KontrolSonucu.SARTLI_UYGUN,        # ŞARTLI UYGUN
    KontrolSonucu.MANUEL_KONTROL,
}

# Bilgi/raporsuz kategoriler — gerçek SUT kapısı yok; ŞÜPHELİ dönse bile
# anlık uyarı çıkarmaz (aksi halde parol/vitamin/suni gözyaşı gürültü yapar).
BILGI_KATEGORILER = {
    'RAPORSUZ_BILGILENDIRME', 'MEDULA_OTOMATIK', 'BENZODIAZEPIN',
    'GOZ_LUBRIKAN',
}


# ═══════════════════════════════════════════════════════════════════════
# STANDALONE ATOMİK MODÜL DİSPATCH KAYIT DEFTERİ
# ═══════════════════════════════════════════════════════════════════════
# Kendi GUI butonu + kapsam tespitçisi olan atomik motorlar. kontrol_et_tekil
# 7 açık modülden sonra, genel master dispatcher'dan ÖNCE bu listeyi gezer:
# her modülün tespitçisi (kapsami_mi / yolak_belirle / _ilac_sinifi) kapsam
# içiyse atomik motoru çağrılır. Atomik motor eski-stil genel kategori
# kontrolüne tercih edilir.
#
# NOT: antiepileptik (4.2.25) / nöropatik (4.2.35) / hepatit (4.2.13) /
# psikiyatri (4.2.2) / solunum zaten genel dispatcher kategorilerine bağlı
# ve gabapentin/pregabalin gibi endikasyona-duyarlı ayrımları orada çözülüyor
# — burada TEKRAR eklenmez (çakışma riskini önlemek için).
#
# Format: (kategori, modül_yolu, tespit_fonksiyonu, kontrol_fonksiyonu)
_EK_MODUL_DISPATCH: List[Tuple[str, str, str, str]] = [
    # ── Nöroloji ──
    ('PARKINSON', 'recete_kontrol.parkinson_4_2_36',
     'parkinson_yolak_belirle', 'parkinson_kontrol_4_2_36'),
    ('MULTIPL_SKLEROZ', 'recete_kontrol.multipl_skleroz_4_2_34',
     'ms_yolak_belirle', 'multipl_skleroz_kontrol_4_2_34'),
    ('MIGREN', 'recete_kontrol.migren_4_2_19',
     'migren_kapsami_mi', 'migren_kontrol_4_2_19'),
    ('DEMANS_ALS', 'recete_kontrol.demans_als_ek4f_7',
     'demans_als_kapsami_mi', 'demans_als_kontrol_ek4f_7'),
    ('GINKGO', 'recete_kontrol.ginkgo_ek4f_55',
     'ginkgo_kapsami_mi', 'ginkgo_kontrol_ek4f_55'),
    ('ATOMOKSETIN', 'recete_kontrol.atomoksetin_dehb',
     'atomoksetin_kapsami_mi', 'atomoksetin_kontrol_dehb'),
    # ── Kardiyoloji / Pulmoner ──
    ('PULMONER_HT', 'recete_kontrol.pulmoner_ht_4_2_30_a',
     'pulmoner_ht_yolak_belirle', 'pulmoner_ht_kontrol_4_2_30_a'),
    # ── Onkoloji ──
    ('MELANOM', 'recete_kontrol.melanom_braf_mek_4_2_14_c_z',
     'melanom_yolak_belirle', 'melanom_kontrol_4_2_14_c_z'),
    ('LEFLUNOMID', 'recete_kontrol.leflunomid_4_2_1_a',
     'leflunomid_kapsami_mi', 'leflunomid_kontrol_4_2_1_a'),
    # ── Biyolojik ajanlar (anti-TNF dışı) SUT 4.2.1.C-2…C-14 ──
    # anti-TNF (L04AB*) C-1 genel dispatcher'da; bu kayıt L04AC/L04AF/L01FA/
    # L04AA biyolojiklerini kapsar (çakışma yok). Kapsam dışı → ATLANDI → fall-through.
    ('BIYOLOJIK_C', 'recete_kontrol.biyolojik_4_2_1_c',
     'biyolojik_kapsami_mi', 'biyolojik_kontrol_4_2_1_c'),
    # ── Hematoloji / Nefroloji ──
    ('PARENTERAL_DEMIR', 'recete_kontrol.parenteral_demir_4_2_41',
     '_ilac_sinifi', 'parenteral_demir_kontrol_4_2_41'),
    # ── Pediatri / Enfeksiyon / Aşı ──
    ('PALIVIZUMAB', 'recete_kontrol.palivizumab_4_2_20',
     'palivizumab_kapsamda_mi', 'palivizumab_kontrol_4_2_20'),
    ('GRIP_ASISI', 'recete_kontrol.grip_asisi_2_4_3_b',
     'grip_asisi_kapsamda_mi', 'grip_asisi_kontrol_2_4_3_b'),
    ('ALERJI_ASISI', 'recete_kontrol.alerji_asisi_4_2_3',
     'alerji_asisi_kapsami_mi', 'alerji_asisi_kontrol_4_2_3'),
    ('ANTIFUNGAL', 'recete_kontrol.antifungal_4_2_23',
     'antifungal_kapsami_mi', 'antifungal_kontrol_4_2_23'),
    ('IVERMEKTIN', 'recete_kontrol.ivermektin_ek4f',
     'ivermektin_kapsami_mi', 'ivermektin_kontrol_ek4f'),
    ('RIFAKSIMIN', 'recete_kontrol.rifaksimin_ek4f',
     'rifaksimin_kapsami_mi', 'rifaksimin_kontrol'),
    # ── Üroloji ──
    ('PENTOSAN', 'recete_kontrol.pentosan_ek4f_69',
     'pentosan_kapsami_mi', 'pentosan_kontrol_ek4f_69'),
    ('ALPROSTADIL', 'recete_kontrol.alprostadil_ek4f_37_1',
     'alprostadil_kapsami_mi', 'alprostadil_kontrol_ek4f_37_1'),
    ('FINASTERID_DUTASTERID', 'recete_kontrol.finasterid_dutasterid_bph',
     'finasterid_dutasterid_kapsami_mi', 'finasterid_dutasterid_kontrol'),
    ('DESMOPRESSIN', 'recete_kontrol.desmopressin_kontrol',
     'desmopressin_kapsami_mi', 'desmopressin_kontrol'),
    # ── Göz ──
    ('GLOKOM', 'recete_kontrol.glokom_4_2_11',
     'glokom_kapsami_mi', 'glokom_kontrol_4_2_11'),
    # ── Dermatoloji ──
    ('PIMEKROLIMUS_TAKROLIMUS', 'recete_kontrol.pimekrolimus_takrolimus_4_2_58',
     'pimtak_kapsami_mi', 'pimtak_kontrol_4_2_58'),
    # ── Endokrin / Kadın hastalıkları ──
    ('ORLISTAT', 'recete_kontrol.orlistat_4_2_18',
     'orlistat_kapsami_mi', 'orlistat_kontrol_4_2_18'),
    ('FLUDROKORTIZON', 'recete_kontrol.fludrokortizon_ek4f_77',
     'fludrokortizon_kapsami_mi', 'fludrokortizon_kontrol_ek4f_77'),
    ('KADIN_HORMON', 'recete_kontrol.kadin_hormonlari_4_2_29',
     'kadin_hormonlari_kapsami_mi', 'kadin_hormonlari_kontrol_4_2_29'),
    # ── KT antiemetik / Antiemetik ──
    ('SETRON', 'recete_kontrol.setron_ek4f_11',
     'setron_kapsami_mi', 'setron_kontrol_ek4f_11'),
    ('APREPITANT', 'recete_kontrol.aprepitant_kt_bulanti',
     'aprepitant_kapsami_mi', 'aprepitant_kontrol_kt_bulanti'),
    ('MEKLOZIN', 'recete_kontrol.meklozin_antiemetik',
     'meklozin_kapsami_mi', 'meklozin_kontrol'),
]


def _ek_modul_dispatch(ilac_sonuc: Dict) -> Tuple[Optional[str], Optional[KontrolRaporu]]:
    """Standalone atomik modülleri (kayıt defteri) sırayla dene.

    İlk kapsam-içi modülün sonucunu döndür. Hiçbiri kapsam içinde değilse
    (None, None). Her modül kendi try/except'i ile izole — biri patlarsa
    diğerleri denenir.

    ÖNEMLİ: Bir modülün tespitçisi (kapsami_mi) geniş davranıp kapsam=True
    derken kontrol fonksiyonu ATLANDI dönebilir (örn. topiramat epilepsi
    bağlamında → migren modülü ATLANDI). Bu durumda kısa-devre YAPMA;
    sonraki modüllere ve genel dispatcher'a düşmesine izin ver (topiramat
    epilepsi → ANTIEPILEPTIK). ATLANDI = "benim kuralım değil, aramaya devam".
    """
    for kategori, modul_yolu, tespit_adi, giris_adi in _EK_MODUL_DISPATCH:
        try:
            modul = importlib.import_module(modul_yolu)
            tespit = getattr(modul, tespit_adi)
            if tespit(ilac_sonuc):
                giris = getattr(modul, giris_adi)
                rapor = giris(ilac_sonuc)
                if rapor is not None and rapor.sonuc == KontrolSonucu.ATLANDI:
                    continue  # bu kural uygulanmadı — aramaya devam
                return kategori, rapor
        except Exception:
            continue
    return None, None


def uyari_gerekir_mi(sonuc: Optional[KontrolSonucu],
                      kategori: Optional[str] = None) -> bool:
    """Bu kontrol sonucu anlık uyarı penceresi gerektirir mi?

    Bilgi kategorileri (raporsuz/medula otomatik) uyarı çıkarmaz.
    """
    if kategori in BILGI_KATEGORILER:
        return False
    return sonuc in UYARI_SONUCLARI


def kontrol_et_tekil(ilac_sonuc: Dict) -> Tuple[Optional[str], Optional[KontrolRaporu]]:
    """Tek bir reçete kalemini uygun SUT kontrolüne yönlendir.

    Returns: (kategori, KontrolRaporu) — kontrol uygulanmadıysa (None, None).
    """
    # 1) 4.2.9.A — ESA (eritropoietin/darbepo/Mircera/roksadustat)
    try:
        from recete_kontrol.eritropoietin_4_2_9_a import (
            _ilac_sinifi as _esa_sinifi, eritropoietin_kontrol_4_2_9_a)
        if _esa_sinifi(ilac_sonuc):
            return 'ERITROPOIETIN', eritropoietin_kontrol_4_2_9_a(ilac_sonuc)
    except Exception:
        pass

    # 2) 4.2.14.B — kanser/hormon + G-CSF
    try:
        from recete_kontrol.kanser_gcsf_4_2_14_b import (
            kanser_gcsf_yolak_belirle, kanser_gcsf_kontrol_4_2_14_b)
        if kanser_gcsf_yolak_belirle(ilac_sonuc):
            return 'KANSER_GCSF', kanser_gcsf_kontrol_4_2_14_b(ilac_sonuc)
    except Exception:
        pass

    # 3) 4.2.1.C-1 — Anti-TNF biyolojik ajanlar (adalimumab/etanersept/
    #    infliksimab/sertolizumab/golimumab — ATC L04AB*)
    try:
        from recete_kontrol.anti_tnf_4_2_1_c1 import (
            anti_tnf_kapsami_mi, anti_tnf_kontrol_4_2_1_c1)
        if anti_tnf_kapsami_mi(ilac_sonuc):
            return 'ANTI_TNF', anti_tnf_kontrol_4_2_1_c1(ilac_sonuc)
    except Exception:
        pass

    # 4) 4.2.12.B — Spesifik olmayan immünglobulin (IVIG/SCIG — ATC J06BA*)
    try:
        from recete_kontrol.immunglobulin_4_2_12_b import (
            immunglobulin_kapsami_mi, immunglobulin_kontrol_4_2_12_b)
        if immunglobulin_kapsami_mi(ilac_sonuc):
            return 'IMMUNGLOBULIN', immunglobulin_kontrol_4_2_12_b(ilac_sonuc)
    except Exception:
        pass

    # 5) 4.2.33 — Göz anti-VEGF (ranibizumab/aflibersept/deksametazon implant/
    #    verteporfin; bevacizumab → ATLANDI/günübirlik, sessiz geçer)
    try:
        from recete_kontrol.goz_antivegf_4_2_33 import (
            goz_antivegf_yolak_belirle, goz_antivegf_kontrol_4_2_33)
        if goz_antivegf_yolak_belirle(ilac_sonuc):
            return 'GOZ_ANTIVEGF', goz_antivegf_kontrol_4_2_33(ilac_sonuc)
    except Exception:
        pass

    # 6) 4.2.14.C-(çç) — Ruksolitinib (JAKAVI; miyelofibrozis/GvHD/polisitemi vera)
    try:
        from recete_kontrol.ruksolitinib_4_2_14_c_cc import (
            ruksolitinib_kapsami_mi, ruksolitinib_kontrol_4_2_14_cc)
        if ruksolitinib_kapsami_mi(ilac_sonuc):
            return 'RUKSOLITINIB', ruksolitinib_kontrol_4_2_14_cc(ilac_sonuc)
    except Exception:
        pass

    # 7) 4.2.9.B — Fosfor bağlayıcı (sevelamer/lantanyum karbonat/alüminyum
    #    klorür hidroksit — ATC V03AE02/03)
    try:
        from recete_kontrol.sevelamer_fosfor_4_2_9_b import (
            sevelamer_fosfor_kapsami_mi, sevelamer_fosfor_kontrol_4_2_9_b)
        if sevelamer_fosfor_kapsami_mi(ilac_sonuc):
            return 'FOSFOR_BAGLAYICI', sevelamer_fosfor_kontrol_4_2_9_b(ilac_sonuc)
    except Exception:
        pass

    # 8) Standalone atomik modüller (kayıt defteri — Parkinson/MS/Migren/
    #    Pulmoner HT/Melanom/Parenteral Demir/Palivizumab/Grip/EK-4F'ler vb.)
    kat, rap = _ek_modul_dispatch(ilac_sonuc)
    if kat is not None and rap is not None:
        return kat, rap

    # 9) Genel master dispatcher (kategori tespit + kontrol)
    try:
        from recete_kontrol.sut_kontrolleri import sut_kontrol_yap
        res = sut_kontrol_yap(ilac_sonuc)
        if res and res.get('kontrol_raporu') is not None:
            return res.get('kategori'), res['kontrol_raporu']
    except Exception:
        pass

    return None, None


# ═══════════════════════════════════════════════════════════════════════
# Basit self-test (DB gerektirmeyen yönlendirme + uyarı eşiği)
# ═══════════════════════════════════════════════════════════════════════

def _selftest() -> None:
    print("Anlık Kontrol dispatcher — self-test")
    print("=" * 50)

    # uyari_gerekir_mi
    assert uyari_gerekir_mi(KontrolSonucu.UYGUN_DEGIL)
    assert uyari_gerekir_mi(KontrolSonucu.KONTROL_EDILEMEDI)
    assert uyari_gerekir_mi(KontrolSonucu.SARTLI_UYGUN)
    assert uyari_gerekir_mi(KontrolSonucu.TIBBEN_UYGUN_DEGIL)
    assert not uyari_gerekir_mi(KontrolSonucu.UYGUN)
    assert not uyari_gerekir_mi(KontrolSonucu.ATLANDI)
    assert not uyari_gerekir_mi(KontrolSonucu.DIGER_RAPOR_UYGUN)
    assert not uyari_gerekir_mi(None)
    print("✓ uyari_gerekir_mi eşiği doğru")

    # Yönlendirme: ESA
    kat, rap = kontrol_et_tekil({
        'ilac_adi': 'ARANESP', 'etkin_madde': 'DARBEPOETIN', 'atc_kodu': 'B03XA02',
        'recete_teshisleri': ['N18.5'], 'brans': 'Nefroloji',
        'rapor_doktor_brans': 'Nefroloji',
        'rapor_metni': 'hemodiyaliz hemoglobin 9 ferritin 150 tsat %25',
    })
    print(f"  ESA → kategori={kat}, sonuc={rap.sonuc.value if rap else None}")
    assert kat == 'ERITROPOIETIN' and rap is not None

    # Yönlendirme: kanser/G-CSF
    kat, rap = kontrol_et_tekil({
        'ilac_adi': 'NEULASTA', 'etkin_madde': 'PEGFILGRASTIM',
        'rapor_turu': 'Sağlık Kurulu Raporu', 'brans': 'Hematoloji',
    })
    print(f"  G-CSF → kategori={kat}, sonuc={rap.sonuc.value if rap else None}")
    assert kat == 'KANSER_GCSF' and rap is not None

    # Yönlendirme: 4.2.33 göz anti-VEGF
    kat, rap = kontrol_et_tekil({
        'ilac_adi': 'LUCENTIS', 'etkin_madde': 'RANIBIZUMAB', 'atc_kodu': 'S01LA04',
        'brans': 'Göz Hastalıkları', 'rapor_turu': 'Sağlık Kurulu Raporu',
        'rec_tesh': 'H35.3',
        'heyet_doktorlari': [{'brans': 'Göz Hastalıkları'},
                              {'brans': 'Göz Hastalıkları'},
                              {'brans': 'Göz Hastalıkları'}],
    })
    print(f"  Göz anti-VEGF → kategori={kat}, "
          f"sonuc={rap.sonuc.value if rap else None}")
    assert kat == 'GOZ_ANTIVEGF' and rap is not None

    # Bevacizumab → ATLANDI (günübirlik) — uyarı çıkmaz
    kat, rap = kontrol_et_tekil({
        'ilac_adi': 'ALTUZAN', 'etkin_madde': 'BEVACIZUMAB', 'atc_kodu': 'L01XC07',
        'brans': 'Göz Hastalıkları', 'rec_tesh': 'H35.3',
    })
    print(f"  Bevacizumab → kategori={kat}, "
          f"sonuc={rap.sonuc.value if rap else None}")
    assert kat == 'GOZ_ANTIVEGF' and rap is not None
    assert not uyari_gerekir_mi(rap.sonuc, kat)

    # Yönlendirme: 4.2.9.B fosfor bağlayıcı
    kat, rap = kontrol_et_tekil({
        'ilac_adi': 'RENVELA', 'etkin_madde': 'SEVELAMER KARBONAT',
        'atc_kodu': 'V03AE02', 'brans': 'Nefroloji',
        'rapor_doktor_brans': 'Nefroloji', 'rapor_kodu': '1',
        'rapor_metni': 'hemodiyaliz hastası fosfor 5.5 mg/dl',
        'baslangic_durum': 'BASKA_ECZANE_RISKI',
    })
    print(f"  Fosfor bağlayıcı → kategori={kat}, "
          f"sonuc={rap.sonuc.value if rap else None}")
    assert kat == 'FOSFOR_BAGLAYICI' and rap is not None

    # Yönlendirme: standalone atomik modüller (kayıt defteri)
    _ek_testler = [
        ('PARKINSON', {'ilac_adi': 'PEXOLA', 'etkin_madde': 'PRAMIPEKSOL',
                       'atc_kodu': 'N04BC05', 'rec_tesh': 'G20'}),
        ('MULTIPL_SKLEROZ', {'ilac_adi': 'GILENYA', 'etkin_madde': 'FINGOLIMOD',
                             'atc_kodu': 'L04AA27', 'rec_tesh': 'G35'}),
        ('MIGREN', {'ilac_adi': 'IMIGRAN', 'etkin_madde': 'SUMATRIPTAN',
                    'atc_kodu': 'N02CC01', 'rec_tesh': 'G43.9'}),
        ('PULMONER_HT', {'ilac_adi': 'TRACLEER', 'etkin_madde': 'BOSENTAN',
                         'atc_kodu': 'C02KX01', 'rec_tesh': 'I27.0'}),
        ('PARENTERAL_DEMIR', {'ilac_adi': 'FERINJECT', 'etkin_madde': 'DEMIR KARBOKSIMALTOZ',
                              'atc_kodu': 'B03AC01'}),
        ('PALIVIZUMAB', {'ilac_adi': 'SYNAGIS', 'etkin_madde': 'PALIVIZUMAB',
                         'atc_kodu': 'J06BD01'}),
        ('GRIP_ASISI', {'ilac_adi': 'VAXIGRIP TETRA', 'etkin_madde': 'INFLUENZA ASISI',
                        'atc_kodu': 'J07BB02'}),
        ('GLOKOM', {'ilac_adi': 'XALATAN', 'etkin_madde': 'LATANOPROST',
                    'atc_kodu': 'S01EE01'}),
    ]
    for beklenen_kat, s_test in _ek_testler:
        kat, rap = kontrol_et_tekil(s_test)
        print(f"  {beklenen_kat} → kategori={kat}, "
              f"sonuc={rap.sonuc.value if rap else None}")
        assert kat == beklenen_kat, f"{beklenen_kat} yönlendirmesi başarısız: {kat}"
        assert rap is not None

    # Yönlendirme: genel (statin örn.) — kategori tespitine bağlı
    kat, rap = kontrol_et_tekil({
        'ilac_adi': 'ATOR 20', 'etkin_madde': 'ATORVASTATIN',
        'sut_maddesi': '4.2.28.A', 'rapor_kodu': '04.08',
        'recete_teshisleri': ['E78.0'],
    })
    print(f"  Genel(statin?) → kategori={kat}, "
          f"sonuc={rap.sonuc.value if rap else None}")

    # Yönlendirme: kapsam dışı
    kat, rap = kontrol_et_tekil({
        'ilac_adi': 'PAROL', 'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
    })
    print(f"  Kapsam dışı → kategori={kat}")

    print("=" * 50)
    print("✓ Tüm yönlendirme testleri geçti")


if __name__ == '__main__':
    _selftest()
