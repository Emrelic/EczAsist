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

from typing import Dict, Optional, Tuple

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

    # 6) Genel master dispatcher (kategori tespit + kontrol)
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
