# -*- coding: utf-8 -*-
"""SUT 4.2.13 — Hepatit atomik kontrol modülü.

Pilot uygulama: YOAK 4.2.15.D ile şekillenen "atomik devre şeması" prensibinin
Hepatit ilaç grubuna uygulanması (CLAUDE.md §1-11, docs/SUT_MANTIK_SEMA_PROTOKOLU.md).

12 ayrı yolak (endikasyon × hasta tipi × ilaç türü):
    1. KRONIK-B-ERISKIN          4.2.13.1   (≥18 yaş kronik HBV)
    2. KRONIK-B-COCUK            4.2.13.1   (2-18 yaş kronik HBV)
    3. B-SIROZ                   4.2.13.1.1 (HBV + karaciğer sirozu)
    4. B-IMMUNOSUP               4.2.13.1.2 (immünsupresif/kemo/monoklonal altında HBV)
    5. B-TRANSPLANT              4.2.13.1.3 (karaciğer transplant + HBV)
    6. AKUT-B                    4.2.13(3)  (akut hepatit B + ciddi klinik)
    7. KRONIK-D                  4.2.13.2   (Delta hepatit, anti-HDV+)
    8. AKUT-C                    4.2.13.3.1 (akut hepatit C)
    9. KRONIK-C-ERISKIN-NAIVE    4.2.13.3.2.A.1 (erişkin C, naive)
    10. KRONIK-C-ERISKIN-EXP     4.2.13.3.2.A.2 (erişkin C, deneyimli)
    11. KRONIK-C-COCUK-NAIVE     4.2.13.3.2.B   (çocuk C, naive)
    12. KRONIK-C-COCUK-EXP       4.2.13.3.2.B.1 (çocuk C, deneyimli)

Üst formül:
    HEPATIT_UYGUN ⇔ DISPATCHER(reçete_ilaç, ICD, yaş, rapor_metni, geçmiş)
                  ∧ YOLAK_<karar>_UYGUN

Sayısal şartlar (HBV DNA, HCV RNA, HAI, fibrozis, FIB-4, APRI, Child-Pugh, INR,
PT, trombosit, ALT, genotip, HBeAg) için her biri ayrı regex parser. Parse
edilemeyenler `KONTROL_EDILEMEDI + sartli_atom=True` ile işaretlenir → eczacı
manuel doğrulayınca kesin UYGUN olur (SARTLI_UYGUN sonucu).

Hasta geçmişi (HCV DAA önceki tedavi sorgu):
- Önce aktif rapor metni: "daha önce hepatit C tedavisi almış", "NS5A inhibitörü",
  "proteaz inhibitörü", "interferon almış" ibareleri.
- Sonra `diger_raporlar_icd_tum_zamanlar` ve eski rapor metinleri.
- Yerel DB'de (oturum_raporlari.db) önceki reçetelerde HCV DAA varsa "var (kendi
  eczanemiz)" denir; yoksa "başka eczaneden alınmış olabilir — KE".
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc
)

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════
# 1. SUT METNİ KAYNAĞI + İLAÇ GRUPLARI (etken madde + ticari)
# ═════════════════════════════════════════════════════════════════════════

SUT_KURALI_HEPATIT = (
    'SUT 4.2.13 — Hepatit tedavisi (atomik 12 yolak, B/D/C, akut/kronik, '
    'erişkin/çocuk, naive/deneyimli)'
)

# HBV oral antiviraller (4.2.13.1 madde 3,4,5)
HBV_ORAL_ETKEN = (
    'LAMIVUDIN', 'LAMIVUDINE',
    'TELBIVUDIN', 'TELBIVUDINE',
    'ENTEKAVIR', 'ENTECAVIR',
    'TENOFOVIR',                # TDF + TAF ortak prefix
    'TENOFOVIR DISOPROKSIL', 'TENOFOVIR DISOPROXIL',
    'TENOFOVIR ALAFENAMID', 'TENOFOVIR ALAFENAMIDE',
    'ADEFOVIR',
)
HBV_ORAL_TICARI = (
    'BARACLUDE', 'VIREAD', 'VEMLIDY', 'ZEFFIX', 'SEBIVO', 'TYZEKA',
    'HEPSERA', 'TENOF', 'EPIVIR HBV',
)

# HBV oral antiviral ETKEN-SPESİFİK keyword listeleri (2026-05-29 Yalçın
# Durdağı VEMLIDY bug fix). Kullanıcı kararı: "Sadece aynı etken" —
# VEMLIDY için sadece TAF aranır, BARACLUDE/VIREAD dahil edilmez.
# DİKKAT: "TENOFOVIR" tek başına ambiguous (TDF + TAF ortak); bu nedenle
# alt-tip key'lerinde "TENOFOVIR" yalın YOK — sadece "TENOFOVIR DISOPROKSIL"
# (TDF) veya "TENOFOVIR ALAFENAMID" (TAF).
HBV_ALT_TIP_KW = {
    'TAF': ('TENOFOVIR ALAFENAMID', 'TENOFOVIR ALAFENAMIDE', 'VEMLIDY'),
    'TDF': ('TENOFOVIR DISOPROKSIL', 'TENOFOVIR DISOPROXIL',
            'VIREAD', 'TENOFAR', 'HIVERAC', 'TENOF'),
    'ETV': ('ENTECAVIR', 'ENTEKAVIR', 'BARACLUDE'),
    'LAM': ('LAMIVUDIN', 'LAMIVUDINE', 'ZEFFIX', 'EPIVIR HBV'),
    'TLB': ('TELBIVUDIN', 'TELBIVUDINE', 'SEBIVO', 'TYZEKA'),
    'ADV': ('ADEFOVIR', 'HEPSERA'),
}


def _hbv_oral_etken_alt_tip(ilac_adi: str, etkin_madde: str) -> str:
    """HBV oral antiviral aktif ilacın alt-tipini döndür.

    Returns: 'TAF' | 'TDF' | 'ETV' | 'LAM' | 'TLB' | 'ADV' | ''
    """
    ilac = (ilac_adi or '').upper()
    etkin = (etkin_madde or '').upper()
    if 'VEMLIDY' in ilac or 'ALAFENAMID' in etkin:
        return 'TAF'
    if ('VIREAD' in ilac or 'TENOFAR' in ilac or 'HIVERAC' in ilac
            or 'DISOPROKSIL' in etkin or 'DISOPROXIL' in etkin):
        return 'TDF'
    if 'BARACLUDE' in ilac or 'ENTECAVIR' in etkin or 'ENTEKAVIR' in etkin:
        return 'ETV'
    if ('ZEFFIX' in ilac or 'EPIVIR' in ilac
            or 'LAMIVUDIN' in etkin or 'LAMIVUDINE' in etkin):
        return 'LAM'
    if ('SEBIVO' in ilac or 'TYZEKA' in ilac
            or 'TELBIVUDIN' in etkin or 'TELBIVUDINE' in etkin):
        return 'TLB'
    if 'HEPSERA' in ilac or 'ADEFOVIR' in etkin:
        return 'ADV'
    return ''


# HCV DAA ilaçları (4.2.13.3.2)
HCV_DAA_ETKEN = (
    'SOFOSBUVIR', 'LEDIPASVIR', 'VELPATASVIR', 'VOXILAPREVIR',
    'GLEKAPREVIR', 'GLECAPREVIR', 'PIBRENTASVIR',
    'OMBITASVIR', 'PARITAPREVIR', 'DASABUVIR',
    'DAKLATASVIR', 'ELBASVIR', 'GRAZOPREVIR',
)
HCV_DAA_TICARI = (
    'SOVALDI', 'HARVONI', 'EPCLUSA', 'VOSEVI',
    'MAVYRET', 'MAVIRET', 'VIEKIRAX', 'EXVIERA',
    'DAKLINZA', 'ZEPATIER',
)

# Pegile interferon (4.2.13.1.2, 4.2.13.2, 4.2.13.3.1, 4.2.13.3.2.B)
PEG_IFN_ETKEN = (
    'PEGINTERFERON', 'PEGINTERFERON ALFA',
    'PEGINTERFERON ALFA-2A', 'PEGINTERFERON ALFA-2B',
)
PEG_IFN_TICARI = ('PEGASYS', 'PEGINTRON', 'VIRAFERONPEG')

# Standart interferon (çocuk Kronik C için)
INTERFERON_ETKEN = ('INTERFERON ALFA', 'INTERFERON ALFA-2A', 'INTERFERON ALFA-2B')

# Ribavirin (akut C'de YASAK, kronik C-çocuk'ta gerekli)
RIBAVIRIN_ETKEN = ('RIBAVIRIN',)
RIBAVIRIN_TICARI = ('COPEGUS', 'REBETOL', 'VIRAZOLE')

# NS5A inhibitörleri (4.2.13.3.2 (6) önceki tedavi geçmişi için)
NS5A_INHIB = ('LEDIPASVIR', 'VELPATASVIR', 'PIBRENTASVIR', 'OMBITASVIR',
              'ELBASVIR', 'DAKLATASVIR')
# Proteaz inhibitörleri (HCV)
PROTEAZ_INHIB = ('VOXILAPREVIR', 'GLEKAPREVIR', 'GLECAPREVIR',
                 'PARITAPREVIR', 'GRAZOPREVIR')

# Hepatit ICD-10 kodları
ICD_AKUT_B = ('B16',)
ICD_AKUT_D = ('B17.0',)
ICD_AKUT_C = ('B17.1',)
ICD_KRONIK_B = ('B18.0', 'B18.1')
ICD_KRONIK_C = ('B18.2',)
ICD_HEPATIT_GENEL = ('B16', 'B17', 'B18', 'B19', 'Z22.5')

# Reçete eden hekim yetkili branşları (4.2.13 madde 1)
RECETE_YETKILI_BRANSLAR = ('GASTROENTEROLOJI', 'GASTRO',
                            'ENFEKSIYON HASTALIKLARI', 'ENFEKSIYON',
                            'ENFEKTI', 'HEPATOLOJI',
                            'IC HASTALIKLARI', 'İC HASTALIKLARI',
                            'DAHILIYE', 'DAHİLİYE',
                            'COCUK SAGLIGI', 'COCUK', 'PEDIATRI',
                            'COCUK HASTALIKLARI')

# Rapor düzenleyen yetkili branşlar (gastro/enf zorunlu)
RAPOR_YETKILI_BRANSLAR = ('GASTROENTEROLOJI', 'GASTRO',
                           'ENFEKSIYON HASTALIKLARI', 'ENFEKSIYON',
                           'HEPATOLOJI')


def _tr_lower(s: Optional[str]) -> str:
    """Parser-uyumlu Türkçe lowercase.

    ÖNEMLİ: İngilizce lab kısaltmaları (FIB, ALT, INR, HBV, HCV, HAI) ASCII I
    içerir; Türkçe `I→ı` dönüşümü yapılırsa regex'ler eşleşmez. Bu yüzden
    sadece *dotted* İ → i (ASCII) çevirisi yapılır, plain ASCII I değişmez
    (Python .lower() → i). "BİLGİ" → "bilgi" ✓, "FIB-4" → "fib-4" ✓.
    """
    if not s:
        return ''
    return str(s).replace('İ', 'i').lower()


def _tr_upper(s: Optional[str]) -> str:
    if not s:
        return ''
    return (str(s).replace('ı', 'I').replace('i', 'İ').upper())


# ═════════════════════════════════════════════════════════════════════════
# 2. SAYISAL PARSER'LAR (her biri ayrı regex; KE→manuel)
# ═════════════════════════════════════════════════════════════════════════

def _hep_sayi_oku(s: str) -> Optional[float]:
    """'10.000', '10,000', '1.5e6', '2.000 IU' gibi sayıyı float'a çevir."""
    if not s:
        return None
    s = s.strip().replace(' ', '')
    # Bilimsel: 1.5x10^6, 1.5e6, 1,5e6
    m = re.match(r'^([0-9]+[\.,]?[0-9]*)\s*[xX*]\s*10\s*[\^]?\s*([0-9]+)$', s)
    if m:
        try:
            base = float(m.group(1).replace(',', '.'))
            exp = int(m.group(2))
            return base * (10 ** exp)
        except (ValueError, OverflowError):
            return None
    m = re.match(r'^([0-9]+[\.,]?[0-9]*)e([0-9]+)$', s, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(',', '.')) * (10 ** int(m.group(2)))
        except (ValueError, OverflowError):
            return None
    # Türkçe binlik nokta + ondalık virgül: "20.000", "1,45"
    if re.match(r'^\d{1,3}(\.\d{3})+(,\d+)?$', s):
        s2 = s.replace('.', '').replace(',', '.')
        try:
            return float(s2)
        except ValueError:
            return None
    # Yabancı: "20,000.5" / "20000.5"
    if ',' in s and '.' in s:
        s2 = s.replace(',', '')
        try:
            return float(s2)
        except ValueError:
            return None
    s2 = s.replace(',', '.')
    try:
        return float(s2)
    except ValueError:
        return None


def hep_parse_hbv_dna(metin: str) -> Tuple[Optional[float], str]:
    """HBV DNA değerini IU/ml olarak parse et.

    Returns: (deger, birim) — deger None ise parse edilemedi.
    'kopya/ml' → IU/ml dönüşümü: 1 IU/ml ≈ 5 kopya/ml (5'e bölünür).
    """
    if not metin:
        return (None, '')
    m_lower = _tr_lower(metin)
    # Pattern: "HBV DNA: 1.5x10^6 IU/ml" / "HBV-DNA 20.000 kopya/ml" / "hbv dna 2000 iu/ml"
    pattern = (
        r'hbv[\s\-]*dna[\s:=\-]*'
        r'(?:[<>≤≥]\s*)?'
        r'([\d\.,]+(?:[xX*]\s*10\s*[\^]?\s*\d+|e\d+)?)'
        r'\s*(iu\s*/?\s*ml|kopya\s*/?\s*ml|copies/?ml)?'
    )
    m = re.search(pattern, m_lower)
    if not m:
        # Yalnız "HBV DNA pozitif/negatif" kalitatif
        if re.search(r'hbv[\s\-]*dna[\s:=\-]*(\(\+\)|poz|pozitif|positive)', m_lower):
            return (-1.0, 'pozitif')  # -1 sentinel: pozitif ama sayı yok
        if re.search(r'hbv[\s\-]*dna[\s:=\-]*(\(\-\)|neg|negatif|negative)', m_lower):
            return (0.0, 'negatif')
        return (None, '')
    deger = _hep_sayi_oku(m.group(1))
    birim = (m.group(2) or '').strip()
    if deger is None:
        return (None, '')
    # kopya/ml → IU/ml dönüşümü
    if 'kopya' in birim or 'copies' in birim:
        return (deger / 5.0, 'iu/ml (dönüştürüldü)')
    return (deger, birim or 'iu/ml')


def hep_parse_hcv_rna(metin: str) -> Tuple[Optional[float], str]:
    """HCV RNA değeri (IU/ml) ya da kalitatif (+/-).
    Returns: (deger, durum). deger=-1 → pozitif (sayı yok), 0 → negatif.
    """
    if not metin:
        return (None, '')
    m_lower = _tr_lower(metin)
    pattern = (
        r'hcv[\s\-]*rna[\s:=\-]*'
        r'(?:[<>≤≥]\s*)?'
        r'([\d\.,]+(?:[xX*]\s*10\s*[\^]?\s*\d+|e\d+)?)'
        r'\s*(iu\s*/?\s*ml|copies/?ml)?'
    )
    m = re.search(pattern, m_lower)
    if m:
        deger = _hep_sayi_oku(m.group(1))
        return (deger, m.group(2) or 'iu/ml') if deger is not None else (None, '')
    if re.search(r'hcv[\s\-]*rna[\s:=\-]*(\(\+\)|poz|pozitif|positive|tespit)', m_lower):
        return (-1.0, 'pozitif')
    if re.search(r'hcv[\s\-]*rna[\s:=\-]*(\(\-\)|neg|negatif|negative|tespit\s*edilm)', m_lower):
        return (0.0, 'negatif')
    return (None, '')


def hep_parse_hai(metin: str) -> Optional[int]:
    """Karaciğer biyopsisi HAI (Histolojik Aktivite İndeksi) — Ishak skoru 0-18."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    m = re.search(r'(?:histolojik\s*aktivite\s*indeksi|hai|ishak)[\s:=\-]*'
                  r'(?:[<>≤≥]\s*)?(\d{1,2})', m_lower)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def hep_parse_fibrozis(metin: str) -> Optional[int]:
    """Karaciğer biyopsisi fibrozis evresi (Ishak: 0-6, METAVIR: F0-F4)."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    m = re.search(r'fibroz[ıi]s[\s:=\-]*(?:evre[\s:=\-]*)?'
                  r'(?:[<>≤≥]\s*)?(\d)', m_lower)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    # METAVIR F0-F4
    m = re.search(r'metav[ıi]r[\s:=\-]*f?(\d)', m_lower)
    if m:
        return int(m.group(1))
    m = re.search(r'\bf([0-4])\b(?!\w)', m_lower)
    if m:
        return int(m.group(1))
    return None


def hep_parse_fib4(metin: str) -> Optional[float]:
    """FIB-4 skoru (4.2.13.1 (1)(a)(2))."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    m = re.search(r'fib[\s\-]*4[\s:=\-]*(?:skor[u]?[\s:=\-]*)?'
                  r'(?:[<>≤≥]\s*)?([\d\.,]+)', m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    return None


def hep_parse_apri(metin: str) -> Optional[float]:
    """APRI skoru (4.2.13.1 (1)(a)(2))."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    m = re.search(r'apr[ıi][\s:=\-]*(?:skor[u]?[\s:=\-]*)?'
                  r'(?:[<>≤≥]\s*)?([\d\.,]+)', m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    return None


def hep_parse_alt_ust_sinir_orani(metin: str) -> Optional[float]:
    """ALT değeri / normalin üst sınırı oranı.

    Rapor lafzında çeşitli formlar:
      "ALT 88 (ÜS 40)" → 2.2
      "ALT normalin 2 katı" → 2.0
      "ALT > 2x üst sınır" → 2.0+
      "ALT yüksek" → KE
      "ALT: 120 U/L" + "üst sınır 40" → 3.0
    """
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    # "ALT normalin X katı/üzeri"
    m = re.search(r'alt[\s\w]*?normalin?\s*(?:üst\s*sınırının?\s*)?'
                  r'([\d\.,]+)\s*kat', m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    # "ALT X katı"
    m = re.search(r'alt[\s:=\-]*([\d\.,]+)\s*x\s*(?:üs|ust|üst|normal)', m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    # "ALT > 2x üst" / "ALT > 2 x ÜS"
    m = re.search(r'alt[\s\w]*?>\s*([\d\.,]+)\s*x\s*(?:üs|ust|üst|normal)', m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    # Sayısal değer + üst sınır birlikte
    m_alt = re.search(r'alt[\s:=\-]*([\d\.,]+)\s*(?:u/?l|iu/?l)?', m_lower)
    m_us = re.search(r'(?:üst\s*sınır|us\s*[:=])\s*([\d\.,]+)', m_lower)
    if m_alt and m_us:
        v = _hep_sayi_oku(m_alt.group(1))
        u = _hep_sayi_oku(m_us.group(1))
        if v and u and u > 0:
            return v / u
    return None


def hep_parse_alt_yuksek(metin: str) -> Optional[bool]:
    """ALT yüksek mi (kalitatif): "yüksek", "normalin üzerinde"."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    if re.search(r'alt[\s\w]{0,30}?(yüksek|yuksek|normalin\s*üzerinde|'
                 r'normalin\s*üstünde|elev[ae]ted)', m_lower):
        return True
    return None


def hep_parse_child_pugh(metin: str) -> Optional[str]:
    """Child-Pugh skoru sınıfı: 'A' / 'B' / 'C' / None."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    # "Child-Pugh A/B/C" / "Child A" / "Child-Turcotte B"
    m = re.search(r'child[\s\-]*(?:pugh|turcotte)?[\s\-]*([abc])\b', m_lower)
    if m:
        return m.group(1).upper()
    # "Child-Pugh skoru 8" → B (7-9), "skoru 12" → C
    m = re.search(r'child[\s\-]*pugh[\s\w]*?skor[u]?[\s:=\-]*([\d]+)', m_lower)
    if m:
        try:
            s = int(m.group(1))
            if s <= 6:
                return 'A'
            if s <= 9:
                return 'B'
            return 'C'
        except ValueError:
            return None
    return None


def hep_parse_kompanse_dekompanse(metin: str) -> Optional[str]:
    """Rapor: 'nonsirotik' / 'kompanse' (Child-Pugh A) / 'dekompanse' (B/C)."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    if re.search(r'dekompanse|dekompansat|child[\s\-]*(b|c)', m_lower):
        return 'dekompanse'
    if re.search(r'kompanse|child[\s\-]*a', m_lower):
        return 'kompanse'
    if re.search(r'nonsiroti?k|non\-?siroti?k|sirotik\s*değil|sirotik\s*degil',
                 m_lower):
        return 'nonsirotik'
    return None


def hep_parse_genotip(metin: str) -> Optional[str]:
    """HCV genotipi: '1', '1a', '1b', '2', '3', '4', '5', '6'."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    m = re.search(r'genot[iı]p[\s:=\-]*'
                  r'([1-6])([ab])?', m_lower)
    if m:
        g = m.group(1)
        alt = m.group(2) or ''
        return g + alt
    return None


def hep_parse_hbeag(metin: str) -> Optional[str]:
    """HBeAg durumu: 'POZ' / 'NEG' / None."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    if re.search(r'hbeag[\s:=\-]*(\(\+\)|poz|pozitif|positive|reactive|reaktif)',
                 m_lower):
        return 'POZ'
    if re.search(r'hbeag[\s:=\-]*(\(\-\)|neg|negatif|negative)', m_lower):
        return 'NEG'
    return None


def hep_parse_hbsag(metin: str) -> Optional[str]:
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    # "hbsag" / "hbs ag" / "hbs-ag" / "HBs Ag" tüm varyantlar — anti_hbs ile tutarlı
    if re.search(r'hbs[\s\-]?ag[\s:=\-]*(\(\+\)|poz|pozitif|positive|reactive)',
                 m_lower):
        return 'POZ'
    if re.search(r'hbs[\s\-]?ag[\s:=\-]*(\(\-\)|neg|negatif|negative)', m_lower):
        return 'NEG'
    return None


def hep_parse_anti_hdv(metin: str) -> Optional[str]:
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    if re.search(r'anti[\s\-]?hdv[\s:=\-]*(\(\+\)|poz|pozitif|positive)', m_lower):
        return 'POZ'
    if re.search(r'anti[\s\-]?hdv[\s:=\-]*(\(\-\)|neg|negatif|negative)', m_lower):
        return 'NEG'
    return None


def hep_parse_anti_hbc(metin: str) -> Optional[str]:
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    if re.search(r'anti[\s\-]?hbc[\s:=\-]*(\(\+\)|poz|pozitif|positive|reactive)',
                 m_lower):
        return 'POZ'
    if re.search(r'anti[\s\-]?hbc[\s:=\-]*(\(\-\)|neg|negatif|negative)', m_lower):
        return 'NEG'
    return None


def hep_parse_anti_hbs(metin: str) -> Optional[str]:
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    if re.search(r'anti[\s\-]?hbs[\s:=\-]*(\(\+\)|poz|pozitif|positive|reactive)',
                 m_lower):
        return 'POZ'
    if re.search(r'anti[\s\-]?hbs[\s:=\-]*(\(\-\)|neg|negatif|negative)', m_lower):
        return 'NEG'
    return None


def hep_parse_inr(metin: str) -> Optional[float]:
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    m = re.search(r'\binr[\s:=\-]*(?:[<>≤≥]\s*)?([\d\.,]+)', m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    return None


def hep_parse_pt_uzun(metin: str) -> Optional[float]:
    """PT uzaması: 'PT 4 sn uzun', 'PT normalden 5 sn uzun' → saniye."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    m = re.search(r'pt[\s\w]{0,30}?(?:normal\w*\s*)?(?:üst\s*sınır\w*\s*)?'
                  r'([\d\.,]+)\s*(?:sn|saniye)\s*(?:uzun|fazla|üzeri)',
                  m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    return None


def hep_parse_trombosit(metin: str) -> Optional[float]:
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    m = re.search(r'trombosit[\s:=\-]*(?:[<>≤≥]\s*)?'
                  r'([\d\.,]+)\s*(?:/?\s*mm3|/?\s*µl|/?\s*ul|x10|bin)?',
                  m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    m = re.search(r'plt[\s:=\-]*([\d\.,]+)', m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    return None


def hep_parse_sarilik_sure(metin: str) -> Optional[float]:
    """Sarılık süresi (hafta) — akut B'de kriter."""
    if not metin:
        return None
    m_lower = _tr_lower(metin)
    m = re.search(r'sar[ıi]l[ıi]k[\s\w]{0,40}?'
                  r'(?:süre|süresi|>|den\s*uzun|den\s*fazla|fazla|uzun)\s*'
                  r'([\d\.,]+)\s*hafta', m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    m = re.search(r'sar[ıi]l[ıi]k[\s\w]{0,30}?([\d\.,]+)\s*hafta', m_lower)
    if m:
        return _hep_sayi_oku(m.group(1))
    return None


def hep_parse_yas(ilac_sonuc: Dict, metin: str = '') -> Optional[int]:
    """Hasta yaşı: ilac_sonuc → metin regex → None."""
    for key in ('hasta_yasi', 'yas', 'patient_age'):
        v = ilac_sonuc.get(key)
        if v is None:
            continue
        try:
            n = int(re.sub(r'[^0-9]', '', str(v)) or 0)
            if 0 < n < 130:
                return n
        except (ValueError, TypeError):
            pass
    if metin:
        m_lower = _tr_lower(metin)
        m = re.search(r'(?:hasta|yaş|yasi|age)[\s:=]*'
                      r'(\d{1,3})\s*(?:yaş|yıl|y)?', m_lower)
        if m:
            try:
                n = int(m.group(1))
                if 0 < n < 130:
                    return n
            except ValueError:
                pass
    return None


# ═════════════════════════════════════════════════════════════════════════
# 3. İLAÇ TÜRÜ TESPİTİ (dispatcher sinyali)
# ═════════════════════════════════════════════════════════════════════════

def _hep_recetede_ilac_var(diger_ilac_adlari_upper: str,
                            anahtarlar: Tuple[str, ...]) -> bool:
    """Reçete kalemlerinden birinde verilen etken/ticari adlardan biri var mı?"""
    return any(k in diger_ilac_adlari_upper for k in anahtarlar)


def _hep_etken_tip(ilac_adi: str, etkin: str) -> str:
    """Tek ilaç için tip: 'HBV_ORAL' | 'HCV_DAA' | 'PEG_IFN' | 'IFN' |
    'RIBAVIRIN' | 'NONE'."""
    arama = (ilac_adi or '').upper() + ' ' + (etkin or '').upper()
    if any(e in arama for e in HCV_DAA_ETKEN) or \
       any(t in arama for t in HCV_DAA_TICARI):
        return 'HCV_DAA'
    if any(e in arama for e in HBV_ORAL_ETKEN) or \
       any(t in arama for t in HBV_ORAL_TICARI):
        return 'HBV_ORAL'
    if any(e in arama for e in PEG_IFN_ETKEN) or \
       any(t in arama for t in PEG_IFN_TICARI):
        return 'PEG_IFN'
    if any(e in arama for e in INTERFERON_ETKEN):
        return 'IFN'
    if any(e in arama for e in RIBAVIRIN_ETKEN) or \
       any(t in arama for t in RIBAVIRIN_TICARI):
        return 'RIBAVIRIN'
    return 'NONE'


def _hep_hepatit_ilaci_mi(ilac_adi: str, etkin: str) -> bool:
    return _hep_etken_tip(ilac_adi, etkin) != 'NONE'


# ═════════════════════════════════════════════════════════════════════════
# 4. HASTA GEÇMİŞİ (NS5A/proteaz inhibitör önceki tedavi)
# ═════════════════════════════════════════════════════════════════════════

def _hep_gecmis_db_sorgu(hasta_tc: Optional[str],
                          etken_keywords: Tuple[str, ...]
                          ) -> Tuple[Optional[bool], str]:
    """Yerel oturum_raporlari.db'de hastanın önceki reçetelerinde verilen
    etken maddelerin satılıp satılmadığını sorgula.

    Returns:
        (True, 'kendi_eczane:<tarih> <ilaç>') — yerel DB'de bulundu
        (False, '')                            — yerel DB'de bulunamadı
        (None, 'db_erisilemedi')               — DB sorgulanamadı (TC yok / hata)

    KULLANICI KURALI (\\*sss yanıtı):
    "Hasta geçmişine bak. Bulamazsan başka eczaneden alınmış olabilir.
     Bulursan 'buldum', bulamazsan 'kontrol edilemedi'."
    """
    if not hasta_tc:
        return (None, 'TC yok — DB sorgulanamadı')
    try:
        import sqlite3
        import os
        from pathlib import Path
        # APPDATA / BotanikKasa / oturum_raporlari.db (kasa_takip_modul.py kalıbı)
        appdata = os.environ.get('APPDATA')
        if not appdata:
            return (None, 'APPDATA bulunamadı')
        db_yolu = Path(appdata) / 'BotanikKasa' / 'oturum_raporlari.db'
        if not db_yolu.exists():
            # Alternatif: proje kök dizini
            from pathlib import Path as _P
            alt = _P(__file__).resolve().parent.parent / 'oturum_raporlari.db'
            if alt.exists():
                db_yolu = alt
            else:
                return (None, 'oturum_raporlari.db bulunamadı')
        # SADECE SELECT — Botanik EOS değil, yerel SQLite (CLAUDE.md serbest)
        conn = sqlite3.connect(str(db_yolu))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Tablo şeması belirsiz — yaygın isimleri dene
        for table, cols in (
            ('recete_kalemleri', ('ilac_adi', 'etkin_madde')),
            ('satilan_ilaclar', ('ilac_adi', 'etkin_madde')),
            ('recete', ('ilac_adi',)),
        ):
            try:
                # Tablonun varlığını kontrol
                cur.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name=?", (table,))
                if not cur.fetchone():
                    continue
                # Hasta TC alanı için yaygın adlar
                for tc_col in ('hasta_tc', 'tc_no', 'hasta_tckn', 'tckn'):
                    try:
                        like_clauses = ' OR '.join(
                            [f"UPPER({c}) LIKE ?" for c in cols])
                        params = ([hasta_tc] +
                                  [f'%{k}%' for k in etken_keywords
                                   for _ in cols])
                        # Düzelt: her column için tüm keyword'ler, OR ile
                        sub = ' OR '.join([f"UPPER({c}) LIKE ?" for c in cols
                                            for _ in etken_keywords])
                        params = [hasta_tc] + [f'%{k}%' for c in cols
                                                for k in etken_keywords]
                        sql = (f"SELECT * FROM {table} WHERE {tc_col} = ? "
                               f"AND ({sub}) LIMIT 1")
                        cur.execute(sql, params)
                        row = cur.fetchone()
                        if row:
                            conn.close()
                            keys = row.keys()
                            ad = None
                            for c in cols:
                                if c in keys and row[c]:
                                    ad = row[c]; break
                            return (True, f'kendi_eczane:{ad or "ilaç"}')
                    except sqlite3.Error:
                        continue
            except sqlite3.Error:
                continue
        conn.close()
        # ──────────────────────────────────────────────────────────────────
        # 2026-05-29: Yerel oturum_raporlari.db boş → Botanik EOS fallback.
        # Yalçın Durdağı bug: 2019-2023 BARACLUDE reçeteleri yerel DB'de
        # YOK (EczAsist 2024 öncesi yoktu) ama EOS'ta 13 reçete var → /4
        # etken değişim atomları "drug history sorgulanamadı" yerine
        # gerçek geçmişi görmeli.
        eos_sonuc = _hep_eos_gecmis_sorgu(hasta_tc, etken_keywords)
        if eos_sonuc[0] is True:
            return eos_sonuc
        return (False, 'yerel DB + EOS tarandı — bulunamadı (başka eczane riski)')
    except Exception as e:
        logger.debug('Hepatit DB sorgu hatası: %s', e)
        return (None, f'DB sorgu hatası: {e}')


# ATC kodu → etken adı ve alt-tip eşlemesi (HBV oral antiviraller).
# Bu eşleme `_hep_eos_gecmis_sorgu` sonucunda etken keyword'ünü ürün adına
# eklemek için kullanılır — `_hep_etken_degisim_atomlari` substring
# eşleşmesi için etken keyword'üne (örn. ENTECAVIR) ihtiyaç duyar.
_ATC_HBV_ORAL_ETKEN = {
    'J05AF05': 'LAMIVUDIN',
    'J05AF06': 'ENTECAVIR',
    'J05AF07': 'TENOFOVIR DISOPROKSIL',
    'J05AF08': 'ADEFOVIR',
    'J05AF10': 'ENTECAVIR',  # BARACLUDE
    'J05AF11': 'TELBIVUDIN',
    'J05AF13': 'TENOFOVIR ALAFENAMID',
}


def _eos_urun_etken_cikar(urun_adi: str, atc_kodu: str) -> str:
    """Ürün adı + ATC kodundan HBV oral etken keyword'ünü çıkar.

    Önce ATC eşleme, sonra ürün adı substring (HBV_ALT_TIP_KW kullanır).
    Returns: 'ENTECAVIR', 'TENOFOVIR ALAFENAMID', ... veya boş.
    """
    if atc_kodu:
        kod_temiz = atc_kodu.strip().upper()
        if kod_temiz in _ATC_HBV_ORAL_ETKEN:
            return _ATC_HBV_ORAL_ETKEN[kod_temiz]
    alt_tip = _hbv_oral_etken_alt_tip(urun_adi or '', '')
    alt_tip_etken = {
        'TAF': 'TENOFOVIR ALAFENAMID',
        'TDF': 'TENOFOVIR DISOPROKSIL',
        'ETV': 'ENTECAVIR',
        'LAM': 'LAMIVUDIN',
        'TLB': 'TELBIVUDIN',
        'ADV': 'ADEFOVIR',
    }
    return alt_tip_etken.get(alt_tip, '')


def _hep_eos_gecmis_sorgu(hasta_tc: str,
                            etken_keywords: Tuple[str, ...]
                            ) -> Tuple[Optional[bool], str]:
    """Botanik EOS'ta hastanın etken-eş keyword'lerle önceki reçetelerini
    tara. En eski reçeteyi döndür — substring eşleşmesi için etken
    keyword'ü ürün adına eklenir.

    CLAUDE.md §2: SADECE SELECT (BotanikDB guard).

    Returns:
        (True, 'eos:YYYY-MM-DD URUN (ETKEN)') — en eski reçete bulundu
        (False, '...')                          — EOS'ta da bulunamadı
        (None, '...')                           — EOS hatası
    """
    if not hasta_tc or not etken_keywords:
        return (False, '')
    try:
        from botanik_db import get_botanik_db
        db = get_botanik_db()
        if not db.baglan():
            return (None, 'EOS bağlanamadı')
        recs = db.hasta_ilk_recete_etken_bazli(
            hasta_tc, etken_keywords, limit=30)
        if not recs:
            return (False, 'EOS\'ta bu etken için reçete yok')
        # En eski (liste tarih artan sıralı)
        ilk = recs[0]
        tarih_raw = ilk.get('RxIslemTarihi') or ilk.get('RxReceteTarihi')
        tarih_str = ''
        if tarih_raw:
            try:
                tarih_str = tarih_raw.strftime('%Y-%m-%d')
            except AttributeError:
                tarih_str = str(tarih_raw)[:10]
        urun = (ilk.get('UrunAdi') or '').strip()
        atc = (ilk.get('ATCKodu') or '').strip()
        etken_keyword = _eos_urun_etken_cikar(urun, atc)
        gerekce = f'eos:{tarih_str} {urun}'
        if etken_keyword:
            gerekce += f' ({etken_keyword})'
        return (True, gerekce)
    except Exception as e:
        logger.debug('EOS geçmiş sorgu hatası: %s', e)
        return (None, f'EOS sorgu hatası: {e}')


def hep_onceki_hcv_tedavi_var_mi(metin_lower: str,
                                  ilac_sonuc: Dict
                                  ) -> Tuple[SartDurumu, str, Dict]:
    """SUT 4.2.13.3.2 (6) gereği rapor metninde önceki HCV tedavi geçmişi.

    Returns: (durum, neden, detay)
        VAR — rapor ya da yerel DB'de önceki HCV tedavi bulundu
        YOK — rapor "tedavi almamış" diyor ya da hiç ibare yok ama DB'de de yok
        KONTROL_EDILEMEDI — rapor sessiz + DB sorgulanamadı/bulamadı (başka
                            eczane olabilir)
    """
    detay = {'kaynak': '', 'ns5a': False, 'proteaz': False, 'ifn': False,
             'sof': False, 'naive_lafzen': False, 'yerel_db_bulundu': None}

    # 1. Rapor lafzen "naive / ilk tedavi / daha önce almamış"
    if re.search(r'(?:daha\s+önce\s+(?:tedavi\s+)?almam|naive|tedavi\s+almamış|'
                 r'ilk\s+(?:kez|defa)\s+tedavi)', metin_lower):
        detay['naive_lafzen'] = True
        return (SartDurumu.YOK, 'Rapor lafzen: daha önce HCV tedavisi almamış (naive)',
                detay)

    # 2. NS5A inhibitörü ibaresi (en kritik dispatcher sinyali)
    if re.search(r'ns\s*5\s*a\s*(?:inhibit|inh)', metin_lower):
        detay['ns5a'] = True
    if re.search(r'(?:ledipasvir|velpatasvir|pibrentasvir|ombitasvir|elbasvir|'
                 r'daklatasvir)\s*(?:tedavi|alm|kull)', metin_lower):
        detay['ns5a'] = True

    # 3. Proteaz inhibitörü
    if re.search(r'proteaz\s*(?:inhibit|inh)', metin_lower):
        detay['proteaz'] = True
    if re.search(r'(?:voxilaprevir|glekaprevir|glecaprevir|paritaprevir|'
                 r'grazoprevir)\s*(?:tedavi|alm|kull)', metin_lower):
        detay['proteaz'] = True

    # 4. İnterferon / Sofosbuvir geçmişi
    if re.search(r'(?:peg)?interferon\s*(?:tedavi|alm|kull|geçmiş)', metin_lower):
        detay['ifn'] = True
    if re.search(r'sofosbuvir\s*(?:tedavi|alm|kull)', metin_lower):
        detay['sof'] = True

    if detay['ns5a'] or detay['proteaz'] or detay['ifn'] or detay['sof']:
        detay['kaynak'] = 'rapor_metni'
        return (SartDurumu.VAR,
                f"Rapor metninde önceki HCV tedavi ibaresi: "
                f"NS5A={detay['ns5a']}, Proteaz={detay['proteaz']}, "
                f"IFN={detay['ifn']}, SOF={detay['sof']}", detay)

    # 5. Lafzen "tedavi deneyimli / tedavi sonrası nüks"
    if re.search(r'(?:tedavi\s*deneyimli|tedavi\s*sonrası\s*nüks|'
                 r'önceki\s*tedavi|relapse)', metin_lower):
        detay['kaynak'] = 'rapor_metni'
        return (SartDurumu.VAR,
                'Rapor: "tedavi deneyimli/nüks" ibaresi (önceki tedavi türü '
                'belirsiz — manuel doğrulanmalı)', detay)

    # 6. Rapor sessiz → yerel DB sorgu (kendi eczane)
    hasta_tc = (ilac_sonuc.get('hasta_tc')
                or ilac_sonuc.get('tc_no')
                or ilac_sonuc.get('tckn'))
    db_var, db_neden = _hep_gecmis_db_sorgu(
        str(hasta_tc) if hasta_tc else None,
        HCV_DAA_ETKEN + HCV_DAA_TICARI + PEG_IFN_ETKEN + RIBAVIRIN_ETKEN)
    detay['yerel_db_bulundu'] = db_var
    if db_var is True:
        detay['kaynak'] = 'kendi_eczane_db'
        return (SartDurumu.VAR, f'Yerel eczane DB: {db_neden}', detay)
    if db_var is False:
        # Yerel DB'de yok ama başka eczaneden alınmış olabilir → KE
        return (SartDurumu.KONTROL_EDILEMEDI,
                f'Rapor sessiz; yerel eczane DB taranıp HCV tedavi bulunamadı '
                f'— başka eczaneden alınmış olabilir, manuel doğrulanmalı',
                detay)
    # DB sorgulanamadı
    return (SartDurumu.KONTROL_EDILEMEDI,
            f'Rapor "daha önce tedavi" belirtmemiş + {db_neden} → manuel '
            f'doğrulanmalı (başka eczaneden alınmış olabilir)', detay)


# ═════════════════════════════════════════════════════════════════════════
# 5. ORTAK ATOMLAR (R1, D1, ICD eşleme)
# ═════════════════════════════════════════════════════════════════════════

def _hep_brans_yetkili(metin_lower: str,
                        anahtarlar: Tuple[str, ...]) -> bool:
    """Reçete metninde / doktor branşında verilen branşlardan biri geçiyor mu."""
    if not metin_lower:
        return False
    for k in anahtarlar:
        kl = _tr_lower(k)
        if kl in metin_lower:
            return True
    return False


def hep_atom_uzman_rapor(metin_lower: str, rapor_kodu: str,
                          ilac_sonuc: Dict) -> SartSonuc:
    """R1: Gastroenteroloji veya enfeksiyon hastalıkları uzman raporu.

    SUT 4.2.13 madde 1: "gastroenteroloji veya enfeksiyon hastalıkları uzman
    hekimlerinden biri tarafından düzenlenen sağlık raporuna dayanılarak..."
    """
    if not (metin_lower or rapor_kodu):
        return SartSonuc(
            'Uzman raporu (gastroenteroloji/enfeksiyon)',
            SartDurumu.YOK,
            'Rapor metni boş ve rapor kodu yok — uzman raporu yok',
            'rapor_kodu/rapor_metni', grup='(R) Uzman raporu')
    if not rapor_kodu:
        # Rapor kodu yok ama metin var → muhtemelen mesaj/açıklama
        return SartSonuc(
            'Uzman raporu (gastroenteroloji/enfeksiyon)',
            SartDurumu.YOK,
            'Rapor kodu yok (raporsuz reçete) — SUT 4.2.13 madde 1 uzman raporu zorunlu',
            'rapor_kodu', grup='(R) Uzman raporu')
    # Branş tespiti: önce reçete metninde, sonra doktor uzmanlığında
    bulundu = _hep_brans_yetkili(metin_lower, RAPOR_YETKILI_BRANSLAR)
    if bulundu:
        return SartSonuc(
            'Uzman raporu (gastroenteroloji/enfeksiyon)',
            SartDurumu.VAR,
            f'Rapor kodu {rapor_kodu} + metinde uzman branşı tespit edildi',
            'rapor_kodu/rapor_metni', grup='(R) Uzman raporu')
    # Rapor pragmatik kabul (Medula 06.01 / 14.x / B kodları)
    # 2026-05-29: Eskiden KE+sartli idi, kullanıcı geri bildirimi ile VAR
    # yapıldı. Mantık: Medula 06.01 kodunu vermeden önce uzman branş
    # onayını yapar — RaporAna tablosunda doktor branş alanı yok ama
    # Medula rapor kodu vermek için uzman branş onayını zaten zorunlu
    # tutar. Yani 06.01/14.x/B kodları SUT 4.2.13(1) "gastroenteroloji
    # veya enfeksiyon uzman hekimi tarafından düzenlenen rapor" şartını
    # Medula garantisi ile karşılar.
    rapor_pragmatik = (rapor_kodu.startswith('06.01')
                       or rapor_kodu.startswith('14.')
                       or rapor_kodu.startswith('B'))
    if rapor_pragmatik:
        return SartSonuc(
            'Uzman raporu (gastroenteroloji/enfeksiyon)',
            SartDurumu.VAR,
            f'Rapor kodu {rapor_kodu} — Medula uzman branş kontrolünü '
            f'rapor verme aşamasında yapar (SUT 4.2.13(1) garantisi)',
            'rapor_kodu', grup='(R) Uzman raporu')
    return SartSonuc(
        'Uzman raporu (gastroenteroloji/enfeksiyon)',
        SartDurumu.KONTROL_EDILEMEDI,
        f'Rapor kodu {rapor_kodu} mevcut ama yetkili branş ibaresi tespit '
        f'edilemedi — manuel doğrulanmalı',
        'rapor_kodu/rapor_metni', grup='(R) Uzman raporu', sartli_atom=True)


AILE_HEKIMI_ANAHTARLAR = ('AILE HEKIMI', 'AILE HEKIMLIGI', 'AILE HEK',
                           'AİLE HEKİMİ', 'AİLE HEKİMLİĞİ', 'FAMILY')


def hep_atom_recete_yetkisi(ilac_sonuc: Dict, metin_lower: str,
                             aile_hekimi_yetkili: bool = False,
                             rapor_kodu: str = '') -> SartSonuc:
    """D1: Reçete eden hekim gastro/enf/iç hast./çocuk sağlığı.

    SUT 4.2.13 madde 1: "...bu uzman hekimler ile çocuk sağlığı ve hastalıkları
    veya iç hastalıkları uzman hekimleri tarafından reçete edilir."

    aile_hekimi_yetkili=True (4.2.13.1 ve 4.2.13.2 yolakları için, SUT 4.1.1/8):
        Aile hekimi sözleşmesi yapılan/yetkilendirilen hekim, raporlu reçetede
        4.2.13.1 ve 4.2.13.2 maddelerini yazabilir. Rapor şartı: rapor_kodu var
        olmalı.
    """
    brans = _tr_lower(ilac_sonuc.get('doktor_uzmanligi') or '')
    if not brans:
        return SartSonuc(
            'Reçete eden hekim yetkili branş',
            SartDurumu.KONTROL_EDILEMEDI,
            'Doktor branşı bilgisi yok — manuel doğrulanmalı',
            'doktor_uzmanligi', grup='(R) Uzman raporu', sartli_atom=True)
    yetkili = _hep_brans_yetkili(brans, RECETE_YETKILI_BRANSLAR)
    if yetkili:
        return SartSonuc(
            'Reçete eden hekim yetkili branş',
            SartDurumu.VAR,
            f'Doktor branşı: {brans} (yetkili: gastro/enf/iç hast./çocuk)',
            'doktor_uzmanligi', grup='(R) Uzman raporu')
    # SUT 4.1.1/8 — Aile hekimi, raporlu reçetede 4.2.13.1 ve 4.2.13.2 yazabilir
    aile_hek = _hep_brans_yetkili(brans, AILE_HEKIMI_ANAHTARLAR)
    if aile_hek and aile_hekimi_yetkili and rapor_kodu:
        return SartSonuc(
            'Reçete eden hekim yetkili branş',
            SartDurumu.VAR,
            f'Aile hekimi (rapor varsa SUT 4.1.1/8 ile 4.2.13.1/4.2.13.2 yetkili)',
            'doktor_uzmanligi', grup='(R) Uzman raporu')
    if aile_hek and aile_hekimi_yetkili and not rapor_kodu:
        return SartSonuc(
            'Reçete eden hekim yetkili branş',
            SartDurumu.YOK,
            f'Aile hekimi reçetesi — rapor şartı sağlanamadı (SUT 4.1.1/8)',
            'doktor_uzmanligi', grup='(R) Uzman raporu')
    # Aile hekimi ya da diğer → yetkisiz
    return SartSonuc(
        'Reçete eden hekim yetkili branş',
        SartDurumu.YOK,
        f'Doktor branşı: {brans} — gastro/enf/iç hast./çocuk dışı (yetkisiz)',
        'doktor_uzmanligi', grup='(R) Uzman raporu')


def hep_atom_recete_yetkisi_hcv(ilac_sonuc: Dict, metin_lower: str) -> SartSonuc:
    """HCV kronik (4.2.13.3.2(5)): gastro/enf uzman raporu + bu uzmanlar ile
    çocuk sağlığı VEYA iç hastalıkları reçete edebilir. Aile hekimi kapsam dışı.
    """
    brans = _tr_lower(ilac_sonuc.get('doktor_uzmanligi') or '')
    if not brans:
        return SartSonuc(
            'Reçete eden hekim yetkili branş (HCV)',
            SartDurumu.KONTROL_EDILEMEDI,
            'Doktor branşı bilgisi yok — manuel doğrulanmalı',
            'doktor_uzmanligi', grup='(R) Uzman raporu', sartli_atom=True)
    # HCV kronik için 4 yetkili: gastro / enf / iç hast / çocuk hast
    hcv_yetki = ('GASTRO', 'ENFEKSI', 'HEPATOLOJI', 'IC HASTALIK',
                 'İC HASTALIK', 'DAHILIYE', 'COCUK SAGLIGI',
                 'COCUK HASTALIK', 'PEDIATRI')
    yetkili = _hep_brans_yetkili(brans, hcv_yetki)
    if yetkili:
        return SartSonuc(
            'Reçete eden hekim yetkili branş (HCV)',
            SartDurumu.VAR,
            f'Doktor branşı: {brans} (HCV yetkili)',
            'doktor_uzmanligi', grup='(R) Uzman raporu')
    return SartSonuc(
        'Reçete eden hekim yetkili branş (HCV)',
        SartDurumu.YOK,
        f'Doktor branşı: {brans} — gastro/enf/iç hast./çocuk dışı',
        'doktor_uzmanligi', grup='(R) Uzman raporu')


def hep_atom_rapor_2_3_basamak(metin_lower: str, rapor_kodu: str) -> SartSonuc:
    """Kronik C: 2./3. basamak sağlık kurumu raporu zorunlu (4.2.13.3.2(5))."""
    if re.search(r'(?:2[\.\s]*basamak|ikinci\s*basamak|3[\.\s]*basamak|'
                 r'üçüncü\s*basamak|eğitim\s*araştırma|üniversite|devlet\s*hastane)',
                 metin_lower):
        return SartSonuc(
            '2./3. basamak sağlık kurumu raporu',
            SartDurumu.VAR,
            'Rapor metninde 2./3. basamak ibaresi tespit edildi',
            'rapor_metni', grup='(R) Uzman raporu')
    if rapor_kodu:
        # Rapor kodu var ama metinde basamak ibaresi yok — Medula varsayar
        return SartSonuc(
            '2./3. basamak sağlık kurumu raporu',
            SartDurumu.KONTROL_EDILEMEDI,
            f'Rapor kodu {rapor_kodu} var; basamak ibaresi metinden okunamadı '
            f'— Medula filtrelemiş olabilir, manuel doğrulanmalı',
            'rapor_kodu', grup='(R) Uzman raporu', sartli_atom=True)
    return SartSonuc(
        '2./3. basamak sağlık kurumu raporu',
        SartDurumu.YOK,
        'Rapor kodu yok ve metinde basamak ibaresi yok',
        'rapor_metni', grup='(R) Uzman raporu')


def _hep_bilgi_atom(ad: str, neden: str, grup_baslik: str,
                     kaynak: str = 'rapor_metni') -> SartSonuc:
    """KE+(bilgi) atom oluşturucu (verdict matematiğini bozmaz).

    `(bilgi)` suffix'i `_hep_genel_sonuc` aggregator'ında atomu hesaplamadan
    geçirir (line ~1003); sadece şemada/raporda görsel bilgi olarak görünür.
    """
    return SartSonuc(
        ad, SartDurumu.KONTROL_EDILEMEDI, neden, kaynak,
        grup=f'{grup_baslik} (bilgi)', sartli_atom=True)


def _hep_baslangic_rapor_db_atom(ilac_sonuc: Dict,
                                    kategori: str) -> SartSonuc:
    """Hastanın MEDULA'dan taranmış geçmiş raporlarında, ilgili kategoride
    (HEPATIT_B / HEPATIT_C / HEPATIT_D) **başlangıç raporu** var mı?

    - Yerel DB'de en eski rapor bulunduysa → VAR (bilgi: tarih + rapor kodu).
    - DB tamamen boşsa → KE + (bilgi) "Geçmiş Rapor Tara butonuyla tarayın".
    - DB'de kayıt var ama bu kategoride yoksa → KE + (bilgi) "başka eczane
      olabilir, manuel doğrulayın" ([[feedback-baska-eczane-ke]]).
    """
    g = '(G) Hastanın başlangıç raporu (geçmiş tarama, SUT 4.2.13.1/6-7)'
    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    if not hasta_tc:
        return _hep_bilgi_atom(
            'Hastanın başlangıç raporu (geçmiş)',
            'Hasta TC bilinmiyor — geçmiş raporlar sorgulanamadı',
            grup_baslik=g, kaynak='hasta_tc')
    try:
        from recete_kontrol.hasta_rapor_gecmisi_db import (
            en_eski_baslangic_raporu, hasta_raporlarini_oku, sema_olustur)
        sema_olustur()
        eski = en_eski_baslangic_raporu(hasta_tc, kategori=kategori)
        if eski:
            return SartSonuc(
                f'Başlangıç raporu DB\'de VAR ({kategori})',
                SartDurumu.VAR,
                f'En eski rapor: {eski.rapor_kodu} - {eski.tani} '
                f'(başl: {eski.baslangic_tarihi}, takip: {eski.rapor_takip_no})',
                'hasta_rapor_gecmisi_db', grup=f'{g} (bilgi)',
                sartli_atom=True)
        # DB'de kayıt var ama bu kategoride yoksa
        hep_kayit = hasta_raporlarini_oku(hasta_tc)
        if hep_kayit:
            return _hep_bilgi_atom(
                f'Başlangıç raporu DB\'de YOK ({kategori})',
                f'Hasta DB\'sinde {len(hep_kayit)} rapor var ama '
                f'{kategori} kategorisinde yok — başka eczane olabilir, '
                f'manuel doğrulayın',
                grup_baslik=g, kaynak='hasta_rapor_gecmisi_db')
        # Hiç tarama yapılmamış
        return _hep_bilgi_atom(
            'Hastanın geçmiş raporları DB\'de yok',
            '🩺 GEÇMİŞ RAPOR TARA butonu ile MEDULA\'dan tarama yapın',
            grup_baslik=g, kaynak='hasta_rapor_gecmisi_db')
    except Exception as e:
        return _hep_bilgi_atom(
            'Başlangıç raporu sorgu hatası',
            f'DB sorgusu başarısız: {e}',
            grup_baslik=g, kaynak='hasta_rapor_gecmisi_db')


# ═════════════════════════════════════════════════════════════════════════
# 6b. BAŞLANGIÇ ↔ DEVAM REÇETE TİPİ TESPİTİ (SUT 4.2.13.1 dallanması)
# ═════════════════════════════════════════════════════════════════════════
#
# SUT 4.2.13.1 başlangıç/devam ayrımı:
#   • /1 (HBV DNA + HAI/fibrozis), /1.b (40+ + DNA≥20k), /3 (erişkin doz)
#     → SADECE BAŞLANGIÇ şartları
#   • /4 (tedavi değişim), /6 (sonlandırma), /7 (HBsAg+ devam)
#     → SADECE DEVAM şartları
#   • /8 rapor süresi → ikisinde de farklı (≤6 ay başlangıç, ≤1 yıl devam)
#
# Tespit sinyalleri (öncelik sırası):
#   1. hasta_rapor_gecmisi DB (MEDULA tarama) — aynı kategoride önceki rapor
#   2. Hasta drug history (yerel oturum_raporlari.db) — aynı kategori HBV oral
#   3. Rapor metni ibareleri ("ilk tedavi/yeni tanı" vs "devam/yenileme/idame")

# "İlk tedavi/yeni başlangıç" işaret ibareleri (rapor metni)
# Kelime sınırı + Türkçe karakter (ş/s) varyantları
_BASLANGIC_IBARELERI = (
    r'ilk\s+tedavi', r'yeni\s+tan[ıi]', r'ilk\s+rapor',
    r'\bba[şs]lan(?:ı?l|m|ır)',          # başlanması, başlanılması, başlanır
    r'\bba[şs]lat(?:ıl|ı|m)',            # başlatılmıştır, başlatıldı, başlatılma
    r'ba[şs]lang[ıi][cç]\s+raporu',
    r'\bnaive\b', r'tedavi\s*ba[şs]l',  # "tedavi başla..." (her formda)
    r'yeni\s+ba[şs]l',                  # "yeni başlanan"
)
# "Devam/yenileme/idame" işaret ibareleri
_DEVAM_IBARELERI = (
    r'\bdevam\s+ediyor', r'\bdevam\s+etmekte', r'tedavinin\s+devam',
    r'\byenileme\b', r'\byenilen(?:miş|en|di)\b',
    r'\bidame\b', r'tedavisi\s+sürmekte',
    r'\baydır\s+kullan', r'\baydır\s+tedavi',
    r'\byıl(?:dır)?\s+tedavi', r'mevcut\s+tedavi',
    r'kontrol\s+raporu', r'devam\s+raporu',
)


def _hep_recete_tipi_tespit(ilac_sonuc: Dict, kategori: str,
                              metin_lower: str,
                              ) -> Tuple[str, str, Dict]:
    """SUT 4.2.13 — Reçete BAŞLANGIÇ tedavisi mi, DEVAM (yenileme) tedavisi mi?

    Args:
        ilac_sonuc: aktif reçete dict (hasta_tc, rapor_kodu, mesaj_metni, ...)
        kategori: 'HEPATIT_B' | 'HEPATIT_C' | 'HEPATIT_D'
        metin_lower: birleşik rapor+reçete+teşhis metni (lower)

    Returns:
        (tip, gerekce, extra)
            tip: 'BASLANGIC' | 'DEVAM' | 'BELIRSIZ'
            gerekce: insan-okur açıklama
            extra: {'db_kayit': N, 'db_kategori_var': bool, 'metin_baslangic': bool,
                    'metin_devam': bool, 'onceki_etken': str, 'detay_listesi': [...]}
    """
    extra: Dict = {
        'db_kayit_sayisi': 0,
        'db_kategori_var': False,
        'db_en_eski_tarih': '',
        'db_en_eski_takip': '',
        'metin_baslangic': False,
        'metin_devam': False,
        'gecmis_etken': '',
        'sinyaller': [],
        # Sinyal 4 — EOS bazlı (en güvenilir, ETAP 1)
        'eos_karar': '',  # 'BASLANGIC' | 'DEVAM' | 'BELIRSIZ_EOS' | 'YOK_EOS' | ''
        'eos_gerekce': '',
        'eos_rapor_sayisi': 0,
        'eos_aktif_sira': 0,
        'force_override': '',
    }

    # ════════════════════════════════════════════════════════════════════
    # Manuel override — başlangıç sekmesi gibi özel akışlar için
    # ════════════════════════════════════════════════════════════════════
    # _baslangic_rapor_doldur (📜 sekmesi) eski rapor metnini koyup yeniden
    # kontrol çalıştırır; bu durumda otomatik tip tespiti hala DEVAM döner
    # (EOS sıra >1 değişmez). Override ile başlangıç şartlarının çalışması
    # garanti edilir.
    forced = (ilac_sonuc.get('_force_recete_tipi') or '').upper().strip()
    if forced in ('BASLANGIC', 'DEVAM', 'BELIRSIZ'):
        extra['force_override'] = forced
        extra['sinyaller'].insert(
            0, f'Manuel override: {forced} (başlangıç sekmesi çağrısı)')
        return (forced,
                f'Manuel override: {forced} '
                '(otomatik tip tespiti atlandı — başlangıç rapor kontrolü)',
                extra)

    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()

    # ════════════════════════════════════════════════════════════════════
    # Sinyal 4 — Botanik EOS RaporAna karşılaştırması (EN ÖNCELİKLİ)
    # ════════════════════════════════════════════════════════════════════
    # Hastanın bu etken için EOS'taki tüm DISTINCT raporlarını çek; aktif
    # rapor takip no en eski ise BAŞLANGIÇ, değilse DEVAM. EOS kesin cevap
    # verirse mevcut 3 sinyali bypass et (en güvenilir kaynak).
    aktif_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    try:
        from recete_kontrol.baslangic_rapor_bulucu import (
            recete_tipi_eos_bazli, hepatit_keyword_listesi)
        # Etken tipini ilaç adı/etken'den tahmin et
        ilac_adi_up = (ilac_sonuc.get('ilac_adi') or '').upper()
        etkin_up = (ilac_sonuc.get('etkin_madde') or '').upper()
        etkin_tip_eos = _hep_etken_tip(ilac_adi_up, etkin_up)
        eos_keywords = hepatit_keyword_listesi(etkin_tip_eos)
        if hasta_tc and eos_keywords:
            eos_tip, eos_ger, eos_det = recete_tipi_eos_bazli(
                hasta_tc, eos_keywords,
                aktif_rapor_takip_no=aktif_takip,
                aktif_rapor_id=ilac_sonuc.get('rapor_ana_id'))
            extra['eos_karar'] = eos_tip
            extra['eos_gerekce'] = eos_ger
            extra['eos_rapor_sayisi'] = eos_det.get('eos_rapor_sayisi', 0)
            extra['eos_aktif_sira'] = eos_det.get('aktif_rapor_sira', 0)
            extra['sinyaller'].insert(
                0, f'EOS [Sinyal 4]: {eos_tip} — {eos_ger}')
            if eos_tip == 'BASLANGIC':
                return ('BASLANGIC', f'EOS: {eos_ger}', extra)
            if eos_tip == 'DEVAM':
                return ('DEVAM', f'EOS: {eos_ger}', extra)
            # YOK_EOS veya BELIRSIZ_EOS → diğer sinyallere düş
    except Exception as e:
        logger.debug('EOS Sinyal 4 hatası: %s', e)
        extra['sinyaller'].append(f'EOS Sinyal 4 hatası: {e}')

    # Sinyal 1: hasta_rapor_gecmisi DB (Medula taraması cache'i)
    if hasta_tc:
        try:
            from recete_kontrol.hasta_rapor_gecmisi_db import (
                en_eski_baslangic_raporu, hasta_raporlarini_oku, sema_olustur)
            sema_olustur()
            tum_kayitlar = hasta_raporlarini_oku(hasta_tc)
            extra['db_kayit_sayisi'] = len(tum_kayitlar)
            eski = en_eski_baslangic_raporu(hasta_tc, kategori=kategori)
            if eski:
                extra['db_kategori_var'] = True
                extra['db_en_eski_tarih'] = eski.baslangic_tarihi or ''
                extra['db_en_eski_takip'] = eski.rapor_takip_no or ''
                extra['sinyaller'].append(
                    f'DB: önceki {kategori} raporu VAR '
                    f'({eski.rapor_kodu} - {eski.baslangic_tarihi})')
        except Exception as e:
            logger.debug('Hepatit DB sorgu hatası: %s', e)
            extra['sinyaller'].append(f'DB sorgu hatası: {e}')

    # Sinyal 2: rapor metni ibareleri
    for pat in _BASLANGIC_IBARELERI:
        if re.search(pat, metin_lower):
            extra['metin_baslangic'] = True
            extra['sinyaller'].append(f'Metin: "{pat}" ibaresi (başlangıç)')
            break
    for pat in _DEVAM_IBARELERI:
        if re.search(pat, metin_lower):
            extra['metin_devam'] = True
            extra['sinyaller'].append(f'Metin: "{pat}" ibaresi (devam)')
            break

    # Sinyal 3: hasta drug history (sadece HBV/HCV için anlamlı)
    # Mevcut _hep_gecmis_db_sorgu fonksiyonunu kullan.
    # 2026-05-29: Etken adı + MARKA adı birlikte aranır — EOS UrunAdi
    # field'ı marka adını içerir (örn. BARACLUDE, VEMLIDY). Sadece etken
    # adı ile sorgu BARACLUDE'u bulamazdı (Yalçın Durdağı bug).
    etken_anahtarlari: Tuple[str, ...] = ()
    if kategori == 'HEPATIT_B':
        etken_anahtarlari = HBV_ORAL_ETKEN + HBV_ORAL_TICARI
    elif kategori == 'HEPATIT_C':
        etken_anahtarlari = (HCV_DAA_ETKEN + HCV_DAA_TICARI
                              + PEG_IFN_ETKEN + PEG_IFN_TICARI)
    elif kategori == 'HEPATIT_D':
        etken_anahtarlari = (HBV_ORAL_ETKEN + HBV_ORAL_TICARI
                              + PEG_IFN_ETKEN + PEG_IFN_TICARI)
    if etken_anahtarlari:
        bulundu, gerekce = _hep_gecmis_db_sorgu(hasta_tc, etken_anahtarlari)
        if bulundu is True:
            extra['gecmis_etken'] = gerekce
            extra['sinyaller'].append(f'Drug history: önceki {kategori} reçetesi VAR — {gerekce}')

    # Karar
    devam_sinyali = (extra['db_kategori_var']
                     or extra['metin_devam']
                     or bool(extra['gecmis_etken']))
    baslangic_sinyali = extra['metin_baslangic']

    if devam_sinyali and not baslangic_sinyali:
        return ('DEVAM',
                ' + '.join(extra['sinyaller']) or 'Devam sinyali',
                extra)
    if devam_sinyali and baslangic_sinyali:
        # Çelişki: hem DB'de önceki rapor var hem metin "yeni tanı" diyor
        # Pratik: DEVAM güvenli (önceki rapor varsa yenileme/devam ihtimali yüksek)
        return ('DEVAM',
                'Çelişki: DB devam diyor ama metin "ilk tedavi" diyor — DEVAM seçildi '
                '(' + ' / '.join(extra['sinyaller']) + ')',
                extra)
    if baslangic_sinyali and not devam_sinyali:
        # Metin sinyali güçlü (klinik dil): "tedaviye başlanması/ilk tedavi/
        # yeni tanı" gibi açık ibareler. DB doğrulaması bonus, kararı bağlamaz.
        return ('BASLANGIC',
                ' + '.join(extra['sinyaller']) or 'Başlangıç sinyali (metin)',
                extra)
    # Hiçbir sinyal yok
    if extra['db_kayit_sayisi'] == 0:
        return ('BELIRSIZ',
                'Hasta DB tamamen boş + metinde başlangıç/devam ibaresi yok — '
                '🩺 GEÇMİŞ RAPOR TARA gerekli',
                extra)
    # DB dolu ama bu kategoride yok + metin sessiz
    return ('BELIRSIZ',
            f'DB\'de {extra["db_kayit_sayisi"]} rapor var ama {kategori} '
            f'kategorisinde yok + metin sessiz — başka eczane olabilir, '
            f'manuel doğrulayın ([[feedback-baska-eczane-ke]])',
            extra)


def _hep_atom_recete_tipi(tip: str, gerekce: str, kategori: str) -> SartSonuc:
    """Reçete tipi (BAŞLANGIÇ/DEVAM/BELIRSIZ) tespit atomu — bilgi grubu.

    Verdict matematiğine girmez ((bilgi) suffix); şemada görünür.
    """
    g = f'(T) Reçete tipi tespiti ({kategori})'
    if tip == 'BASLANGIC':
        return SartSonuc(
            f'Reçete tipi: BAŞLANGIÇ tedavi ({kategori})',
            SartDurumu.VAR, gerekce, 'hasta_db/rapor_metni',
            grup=f'{g} (bilgi)', sartli_atom=True)
    if tip == 'DEVAM':
        return SartSonuc(
            f'Reçete tipi: DEVAM/yenileme tedavi ({kategori})',
            SartDurumu.VAR, gerekce, 'hasta_db/rapor_metni',
            grup=f'{g} (bilgi)', sartli_atom=True)
    return SartSonuc(
        f'Reçete tipi: BELİRSİZ ({kategori})',
        SartDurumu.KONTROL_EDILEMEDI, gerekce, 'hasta_db/rapor_metni',
        grup=f'{g} (bilgi)', sartli_atom=True)


# ═════════════════════════════════════════════════════════════════════════
# 6c. BAŞLANGIÇ-SPESİFİK ATOMLAR (SUT 4.2.13.1/3 erişkin doz)
# ═════════════════════════════════════════════════════════════════════════

# (etken_keyword, beklenen_mg, mg_regex) — SUT 4.2.13.1/3 erişkin başlangıç dozları
_ERISKIN_BASLANGIC_DOZ_TABLOSU: Tuple[Tuple[str, str, str], ...] = (
    ('LAMIVUDIN',           '100 mg',  r'\b100\s*mg\b'),
    ('LAMIVUDINE',          '100 mg',  r'\b100\s*mg\b'),
    ('TELBIVUDIN',          '600 mg',  r'\b600\s*mg\b'),
    ('TELBIVUDINE',         '600 mg',  r'\b600\s*mg\b'),
    ('TENOFOVIR DISOPROKSIL', '245 mg', r'\b245\s*mg\b'),
    ('TENOFOVIR DISOPROXIL',  '245 mg', r'\b245\s*mg\b'),
    ('TENOFOVIR ALAFENAMID',  '25 mg',  r'\b25\s*mg\b'),
    ('TENOFOVIR ALAFENAMIDE', '25 mg',  r'\b25\s*mg\b'),
    ('ENTEKAVIR',           '0.5 mg',  r'\b0[\.,]?\s*5\s*mg\b'),
    ('ENTECAVIR',           '0.5 mg',  r'\b0[\.,]?\s*5\s*mg\b'),
)


def _hep_atom_eriskin_baslangic_dozu(ilac_adi_upper: str,
                                       etkin_upper: str) -> SartSonuc:
    """SUT 4.2.13.1/3 — Erişkin oral antiviral başlangıç dozu gerçek kontrolü.

    Etken adı + ilaç adındaki mg ibaresi → beklenen başlangıç dozuyla uyumlu mu?
    """
    g = '(3) Erişkin başlangıç dozu (SUT 4.2.13.1/3)'
    arama = ilac_adi_upper + ' ' + etkin_upper
    # Tenofovir disoproksil ve alafenamid ortak prefix var; uzun olan önce
    for et_kw, doz_label, mg_pattern in _ERISKIN_BASLANGIC_DOZ_TABLOSU:
        if et_kw in arama:
            if re.search(mg_pattern, arama, re.IGNORECASE):
                return SartSonuc(
                    f'Başlangıç dozu: {et_kw} {doz_label}',
                    SartDurumu.VAR,
                    f'Reçete dozu SUT 4.2.13.1/3 ile uyumlu ({doz_label})',
                    'recete', grup=g)
            # Etken eşleşti ama mg ibaresi yok → şüpheli
            return SartSonuc(
                f'Başlangıç dozu: {et_kw} {doz_label}',
                SartDurumu.KONTROL_EDILEMEDI,
                f'Etken {et_kw}, beklenen {doz_label} ama ilaç adında bu mg '
                f'ibaresi bulunamadı: "{ilac_adi_upper}" — eczacı doğrulamalı',
                'recete', grup=g, sartli_atom=True)
    # Etken SUT listesinden değil (adefovir vb.)
    return SartSonuc(
        'Erişkin başlangıç dozu (LAM/TBV/TDF/TAF/ETV)',
        SartDurumu.KONTROL_EDILEMEDI,
        f'Etken SUT 4.2.13.1/3 listesinden değil: "{etkin_upper}" — '
        f'manuel doğrulama gerekli',
        'recete', grup=g, sartli_atom=True)


# ═════════════════════════════════════════════════════════════════════════
# 6d. DEVAM-SPESİFİK ATOMLAR (SUT 4.2.13.1/4, /6, /7)
# ═════════════════════════════════════════════════════════════════════════

# SUT 4.2.13.1(4) alt-madde ibareleri — etken değişim/ekleme gerekçeleri
# Her alt-madde ayrı pattern listesi; helper içinde re.search ile tarandı.

# (4)(a) — LAM/TBV iken 24. hafta DNA ≥50 IU/ml lafzı
_4A_24HF_DNA_PATTERNS = (
    r'24\s*\.?\s*\s*hafta',
    r'24\s*\.\s*hf\b',
    r'24\s*hf\b',
)
# (4)(b) — DNA pozitifleşme VEYA 10 kat yükselme
_4B_POZITIFLESME_PATTERNS = (
    r'pozitifle[şs]me',
    r'dna\s+(?:pozitifle[şs]|pozitife\s+d[oö]n)',
    r'(?:neg|negatif)\w*\s+(?:hbv\s+)?dna\w*\s+pozitif',
)
_4B_10KAT_PATTERNS = (
    r'10\s*kat\s*(?:y[üu]ksel|art|ço[ğg]al)',
    r'(?:viral\s+y[üu]k\s+)?10\s*kat\s*art',
)
# (4)(c) — TDF/TAF/ETV alırken 1. yıl sonu DNA(+) durumu
_4C_1YIL_PATTERNS = (
    r'1\s*\.?\s*y[ıi]l[ıi]?n?\s*sonu',
    r'birinci\s*y[ıi]l[ıi]?n?\s*sonu',
    r'12\s*\.?\s*ay\s*sonu',
    r'12\s*ay\s*sonunda',
)
# (4)(ç) — gebelik (koşulsuz)
_4CC_GEBELIK_PATTERNS = (
    r'\bgebe(?:lik)?\b',
    r'\bhamile(?:lik)?\b',
)
# (4)(d) — yan etki (koşulsuz)
_4D_YAN_ETKI_PATTERNS = (
    r'yan\s*etki',
    r'advers',
    r'tolere\s*ed[ie](?:lemed|med)',
    r'intolerans',
)
# (4)(e) — değişim gerekçesi raporda yazılı (zorunlu AND)
_4E_GEREKCE_PATTERNS = (
    r'tedavi\s*de[ğg]i[şs](?:imi|tirme|ikli[ğg]i)',
    r'yeni\s*oral\s*antiviral\s*eklen',
    r'antiviral\s*eklen',
    r'antiviral\s*de[ğg]i[şs]',
    r'oral\s*antiviral.{0,15}(?:de[ğg]i[şs]|eklen)',
)
# (4)(f) — adefovir → TDF/TAF/ETV (koşulsuz)
_4F_ADEFOVIR_PATTERNS = (
    r'\badefovir\b',
)


def _hep_etken_degisim_atomlari(ilac_adi_upper: str, etkin_upper: str,
                                  gecmis_etken_gerekce: str,
                                  metin_lower: str) -> List[SartSonuc]:
    """SUT 4.2.13.1(4) — Etken değişim/ekleme alt-maddeler atomik tablosu.

    Aktif etken önceki tedaviyle aynıysa → tek (4) atomu VAR, /4 uygulanmaz.
    Farklıysa 6 alternatif yol (a/b/c/ç/d/f) VEYA grubunda + (e) gerekçe AND.

    Returns: SartSonuc listesi (1 atom aynı durumunda, 7 atom değişim durumunda).
    """
    if not gecmis_etken_gerekce:
        return [SartSonuc(
            'Aktif etken — önceki tedaviyle aynı mı?',
            SartDurumu.KONTROL_EDILEMEDI,
            'Hasta drug history sorgulanamadı — önceki HBV oral etkeni '
            'bilinmiyor; etken aynıysa /4 değişim kuralları aranmaz',
            'hasta_gecmisi',
            grup='(4) Tedavi devamı/değişim (SUT 4.2.13.1/4)',
            sartli_atom=True)]

    gecmis_upper = gecmis_etken_gerekce.upper()
    aktif_arama = ilac_adi_upper + ' ' + etkin_upper
    ayni_etken = False
    aktif_etken_kelime = ''
    for et_kw, _doz, _mg in _ERISKIN_BASLANGIC_DOZ_TABLOSU:
        if et_kw in aktif_arama:
            aktif_etken_kelime = et_kw
            if et_kw in gecmis_upper:
                ayni_etken = True
            break

    if ayni_etken:
        return [SartSonuc(
            f'Aktif etken önceki tedaviyle aynı ({aktif_etken_kelime})',
            SartDurumu.VAR,
            f'Önceki: {gecmis_etken_gerekce} — etken değişikliği yok, /4 '
            f'değişim alt-maddeleri uygulanmaz',
            'recete+hasta_gecmisi',
            grup='(4) Tedavi devamı/değişim (SUT 4.2.13.1/4)')]

    # ════════════════════════════════════════════════════════════════════
    # Etken farklı → 6 alternatif yol VEYA grubunda + (e) gerekçe AND
    # ════════════════════════════════════════════════════════════════════
    atomlar: List[SartSonuc] = []
    g_alt = '(4-alt) Etken değişim alt-yolu (SUT 4.2.13.1/4) [VEYA]'
    onceki_lam_tbv = ('LAMIVUDIN' in gecmis_upper
                       or 'LAMIVUDINE' in gecmis_upper
                       or 'TELBIVUDIN' in gecmis_upper
                       or 'TELBIVUDINE' in gecmis_upper)
    onceki_tdf_taf_etv = ('TENOFOVIR' in gecmis_upper
                           or 'ENTEKAVIR' in gecmis_upper
                           or 'ENTECAVIR' in gecmis_upper)
    onceki_adefovir = 'ADEFOVIR' in gecmis_upper

    # (4)(a) — LAM/TBV iken 24. hafta DNA ≥50 IU/ml
    if onceki_lam_tbv:
        if any(re.search(p, metin_lower) for p in _4A_24HF_DNA_PATTERNS):
            atomlar.append(SartSonuc(
                '(4)(a) LAM/TBV → 24. hafta DNA ≥50 IU/ml',
                SartDurumu.VAR,
                'Önceki etken LAM/TBV + raporda "24. hafta" lafzı — '
                '/4(a) lafzı sağlandı (DNA değeri eczacı doğrulamalı)',
                'rapor_metni', grup=g_alt, veya_grubu=True))
        else:
            atomlar.append(SartSonuc(
                '(4)(a) LAM/TBV → 24. hafta DNA ≥50 IU/ml',
                SartDurumu.YOK,
                'Önceki LAM/TBV ama "24. hafta" lafzı raporda yok',
                'rapor_metni', grup=g_alt, veya_grubu=True))
    else:
        atomlar.append(SartSonuc(
            '(4)(a) LAM/TBV → 24. hafta DNA ≥50 IU/ml',
            SartDurumu.NA,
            f'Ön-koşul yok: önceki etken LAM/TBV değil ({gecmis_etken_gerekce})',
            'hasta_gecmisi', grup=g_alt, veya_grubu=True))

    # (4)(b) — DNA(-) pozitifleşme VEYA 10 kat yükselme
    poz = any(re.search(p, metin_lower) for p in _4B_POZITIFLESME_PATTERNS)
    onkat = any(re.search(p, metin_lower) for p in _4B_10KAT_PATTERNS)
    if poz or onkat:
        atomlar.append(SartSonuc(
            '(4)(b) DNA pozitifleşme ∨ 10 kat yükselme',
            SartDurumu.VAR,
            f'Raporda: pozitifleşme={poz}, 10 kat={onkat}',
            'rapor_metni', grup=g_alt, veya_grubu=True))
    else:
        atomlar.append(SartSonuc(
            '(4)(b) DNA pozitifleşme ∨ 10 kat yükselme',
            SartDurumu.YOK,
            '"pozitifleşme" veya "10 kat" lafzı raporda yok',
            'rapor_metni', grup=g_alt, veya_grubu=True))

    # (4)(c) — TDF/TAF/ETV alırken 1. yıl sonu DNA(+)
    if onceki_tdf_taf_etv:
        if any(re.search(p, metin_lower) for p in _4C_1YIL_PATTERNS):
            atomlar.append(SartSonuc(
                '(4)(c) TDF/TAF/ETV → 1. yıl sonu DNA(+)',
                SartDurumu.VAR,
                'Önceki TDF/TAF/ETV + raporda "1. yıl sonu" lafzı — '
                'DNA(+) durumu eczacı doğrulamalı',
                'rapor_metni', grup=g_alt, veya_grubu=True))
        else:
            atomlar.append(SartSonuc(
                '(4)(c) TDF/TAF/ETV → 1. yıl sonu DNA(+)',
                SartDurumu.YOK,
                'Önceki TDF/TAF/ETV ama "1. yıl sonu" lafzı raporda yok',
                'rapor_metni', grup=g_alt, veya_grubu=True))
    else:
        atomlar.append(SartSonuc(
            '(4)(c) TDF/TAF/ETV → 1. yıl sonu DNA(+)',
            SartDurumu.NA,
            f'Ön-koşul yok: önceki etken TDF/TAF/ETV değil',
            'hasta_gecmisi', grup=g_alt, veya_grubu=True))

    # (4)(ç) — gebelik (koşulsuz)
    if any(re.search(p, metin_lower) for p in _4CC_GEBELIK_PATTERNS):
        atomlar.append(SartSonuc(
            '(4)(ç) Gebelik — koşulsuz değişim',
            SartDurumu.VAR,
            'Raporda "gebelik/hamilelik" lafzı tespit edildi',
            'rapor_metni', grup=g_alt, veya_grubu=True))
    else:
        atomlar.append(SartSonuc(
            '(4)(ç) Gebelik — koşulsuz değişim',
            SartDurumu.YOK,
            '"gebelik/hamilelik" lafzı raporda yok',
            'rapor_metni', grup=g_alt, veya_grubu=True))

    # (4)(d) — yan etki (koşulsuz)
    if any(re.search(p, metin_lower) for p in _4D_YAN_ETKI_PATTERNS):
        atomlar.append(SartSonuc(
            '(4)(d) Yan etki/advers — koşulsuz değişim',
            SartDurumu.VAR,
            'Raporda "yan etki/advers/tolere edilemiyor" lafzı tespit edildi',
            'rapor_metni', grup=g_alt, veya_grubu=True))
    else:
        atomlar.append(SartSonuc(
            '(4)(d) Yan etki/advers — koşulsuz değişim',
            SartDurumu.YOK,
            '"yan etki/advers/tolere edilemiyor" lafzı raporda yok',
            'rapor_metni', grup=g_alt, veya_grubu=True))

    # (4)(f) — adefovir önceki etken (koşulsuz)
    if onceki_adefovir:
        atomlar.append(SartSonuc(
            '(4)(f) Adefovir → TDF/TAF/ETV koşulsuz',
            SartDurumu.VAR,
            f'Önceki etken adefovir, koşulsuz TDF/TAF/ETV geçişi meşru',
            'hasta_gecmisi', grup=g_alt, veya_grubu=True))
    else:
        atomlar.append(SartSonuc(
            '(4)(f) Adefovir → TDF/TAF/ETV koşulsuz',
            SartDurumu.NA,
            'Ön-koşul yok: önceki etken adefovir değil',
            'hasta_gecmisi', grup=g_alt, veya_grubu=True))

    # (4)(e) — değişim gerekçesi raporda yazılı (zorunlu AND)
    g_e = '(4-e) Değişim gerekçesi raporda yazılı (SUT 4.2.13.1/4(e))'
    bulunan_e = [p for p in _4E_GEREKCE_PATTERNS if re.search(p, metin_lower)]
    if bulunan_e:
        atomlar.append(SartSonuc(
            'Değişim gerekçesi raporda yazılı',
            SartDurumu.VAR,
            f'Gerekçe ibareleri: {", ".join(bulunan_e[:3])}',
            'rapor_metni', grup=g_e))
    else:
        atomlar.append(SartSonuc(
            'Değişim gerekçesi raporda yazılı',
            SartDurumu.KONTROL_EDILEMEDI,
            f'Aktif etken ({aktif_etken_kelime or "?"}) önceki tedaviden '
            f'({gecmis_etken_gerekce}) farklı ama raporda "değişim gerekçesi" '
            f'lafzı tespit edilemedi — eczacı doğrulamalı',
            'rapor_metni', grup=g_e, sartli_atom=True))

    return atomlar


def _hep_atom_hbsag_antihbs_raporda(metin_lower: str) -> SartSonuc:
    """SUT 4.2.13.1/6.a — Yenilenen raporda serolojik durum lafzen yazılı mı?

    SUT lafzı: "tek başına HBsAg pozitifliği VEYA HBsAg negatifliği ile birlikte
    Anti-HBs negatifliği raporda belirtilmelidir."

    Atom mantığı (DeMorgan ile çözüldü):
      • HBsAg(+) lafzı raporda VAR              → VAR (tek başına yeterli)
      • HBsAg(-) ∧ AntiHBs durumu lafzen VAR     → VAR (SUT'un "ile birlikte"
            şartı sağlanmış; AntiHBs(+) ise /6.b ayrıca devreye girer)
      • HBsAg(-) ∧ AntiHBs sessiz                → KE (SUT lafzı uyarınca
            AntiHBs de raporda belirtilmeli)
      • HBsAg sessiz                             → KE (rapor lafzen yetersiz)
    """
    g = '(6.a) HBsAg/Anti-HBs raporda (SUT 4.2.13.1/6.a)'
    hbsag = hep_parse_hbsag(metin_lower)
    anti_hbs = hep_parse_anti_hbs(metin_lower)
    if hbsag == 'POZ':
        return SartSonuc(
            'HBsAg(+) raporda belirtilmiş (tek başına yeterli)',
            SartDurumu.VAR,
            f'HBsAg=POZ — SUT 4.2.13.1/6.a "tek başına HBsAg pozitifliği" '
            f'şartı sağlandı (Anti-HBs={anti_hbs or "yok"})',
            'rapor_metni', grup=g)
    if hbsag == 'NEG':
        if anti_hbs in ('POZ', 'NEG'):
            return SartSonuc(
                f'HBsAg(-) + Anti-HBs({anti_hbs}) raporda belirtilmiş',
                SartDurumu.VAR,
                f'HBsAg=NEG ∧ Anti-HBs={anti_hbs} — SUT 4.2.13.1/6.a '
                f'"HBsAg negatifliği ile birlikte Anti-HBs" şartı sağlandı',
                'rapor_metni', grup=g)
        return SartSonuc(
            'HBsAg/Anti-HBs durumu raporda belirtilmiş',
            SartDurumu.KONTROL_EDILEMEDI,
            'HBsAg(-) lafzı var ama Anti-HBs durumu raporda sessiz — '
            'SUT 4.2.13.1/6.a "HBsAg negatifliği ile birlikte Anti-HBs '
            'negatifliği" şartı için Anti-HBs lafzı da yazılmalı',
            'rapor_metni', grup=g, sartli_atom=True)
    return SartSonuc(
        'HBsAg/Anti-HBs durumu raporda belirtilmiş',
        SartDurumu.KONTROL_EDILEMEDI,
        'Yenilenen raporda HBsAg pozitifliği veya negatifliği ibaresi yok — '
        'eczacı doğrulamalı (SUT 4.2.13.1/6.a)',
        'rapor_metni', grup=g, sartli_atom=True)


def _hep_atom_sonlandirma_12ay(metin_lower: str) -> SartSonuc:
    """SUT 4.2.13.1/6.b — HBsAg(-) + Anti-HBs(+) ise ≤12 ay daha devam.

    Bu atomun verdict'i:
    - HBsAg(-) + Anti-HBs(+) durumu yoksa → NA (atom gizlenir / VAR sayılır)
    - Durum varsa → 12 ay süresi parse edilemediği için KE+(bilgi)
    """
    g = '(6.b) Sonlandırma: HBsAg- + AntiHBs+ → ≤12 ay (SUT 4.2.13.1/6.b)'
    hbsag = hep_parse_hbsag(metin_lower)
    anti_hbs = hep_parse_anti_hbs(metin_lower)
    if hbsag == 'NEG' and anti_hbs == 'POZ':
        return SartSonuc(
            'Sonlandırma süresi ≤12 ay (HBsAg-/Anti-HBs+ sonrası)',
            SartDurumu.KONTROL_EDILEMEDI,
            'HBsAg(-) + Anti-HBs(+) durumu tespit edildi — tedavi en fazla '
            '12 ay daha devam edebilir; süre eczacı tarafından doğrulanmalı',
            'rapor_metni', grup=f'{g} (bilgi)', sartli_atom=True)
    # Durum yoksa atom gizli (NA)
    return SartSonuc(
        'Sonlandırma kriterleri (SUT 4.2.13.1/6.b)',
        SartDurumu.NA,
        f'HBsAg={hbsag or "yok"}, Anti-HBs={anti_hbs or "yok"} — sonlandırma '
        f'koşulu (HBsAg-/AntiHBs+) yok, /6.b uygulanmaz',
        'rapor_metni', grup=f'{g} (bilgi)')


def _hep_atom_hbsag_pozitif_devam(metin_lower: str) -> SartSonuc:
    """SUT 4.2.13.1/7 — HBsAg(+) devam eden hastalarda klinik/lab/görüntüleme
    ile tedaviye devam kararı.

    HBsAg(+) ise: devam meşru (VAR), karar gerekçesi raporda bekleniyor (bilgi).
    HBsAg(-)/yok ise: atom NA (uygulanmaz).
    """
    g = '(7) HBsAg+ devam (SUT 4.2.13.1/7)'
    hbsag = hep_parse_hbsag(metin_lower)
    if hbsag == 'POZ':
        return SartSonuc(
            'HBsAg(+) → tedaviye devam meşru',
            SartDurumu.VAR,
            'HBsAg pozitif — klinik/lab/görüntüleme/biyopsi kararıyla devam '
            'edilebilir; karar gerekçesi raporda eczacı doğrulamalı',
            'rapor_metni', grup=g)
    return SartSonuc(
        'HBsAg+ devam koşulu (SUT 4.2.13.1/7)',
        SartDurumu.NA,
        f'HBsAg={hbsag or "yok"} — /7 maddesi (HBsAg+ devam) uygulanmaz',
        'rapor_metni', grup=f'{g} (bilgi)')


def _hep_atom_rapor_suresi(ilac_sonuc: Dict, metin_lower: str,
                             is_baslangic: bool, is_devam: bool,
                             label: str) -> SartSonuc:
    """SUT 4.2.13.1/8 — Rapor süresi tarih bazlı kontrolü.

    SUT lafzı: "Oral antiviral tedavilerde ilk rapor süresi en fazla 6 ay,
    sonraki rapor süreleri bir yılı geçemez."

    Atom mantığı:
      • is_baslangic → ≤ 186 gün (6 ay + tolerans)
      • is_devam     → ≤ 372 gün (1 yıl + tolerans)
      • is_belirsiz  → ≤ 372 gün (güvenli taraf — en geniş limit)

    Tarihler `rapor_baslangic_tarihi` / `rapor_bitis_tarihi` field'larından
    çekilir (Hemanjiyom 4.2.62 kalıbı). Yoksa metinden "X ay" / "X gün"
    ibaresi denenir. Hiçbirisi yoksa KE+(bilgi).
    """
    from datetime import date, datetime
    grup = '(8) Rapor süresi (SUT 4.2.13.1/8)'
    limit_gun = 186 if is_baslangic else 372

    bas = (ilac_sonuc.get('rapor_baslangic_tarihi') or
           ilac_sonuc.get('rapor_bas_tarihi'))
    bit = (ilac_sonuc.get('rapor_bitis_tarihi') or
           ilac_sonuc.get('rapor_son_tarihi'))

    def _parse(d):
        if isinstance(d, date):
            return d
        if not d:
            return None
        s = str(d).strip()
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y',
                    '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(s[:len(fmt) + 4], fmt).date()
            except ValueError:
                continue
        return None

    d_bas, d_bit = _parse(bas), _parse(bit)
    if d_bas and d_bit:
        gun = (d_bit - d_bas).days
        if gun <= limit_gun:
            return SartSonuc(
                label, SartDurumu.VAR,
                f'Rapor süresi {gun} gün — limit {limit_gun} gün altında',
                kaynak='rapor_tarihleri', grup=grup)
        return SartSonuc(
            label, SartDurumu.YOK,
            f'Rapor süresi {gun} gün — limit {limit_gun} gün üzerinde',
            kaynak='rapor_tarihleri', grup=grup)

    # Metinden ipucu — "X ay" / "X yıl" (word boundary ile sayı tam yakalama)
    m_ay = re.search(r'\b(\d{1,2})\s*ay\b', metin_lower)
    m_yil = re.search(r'\b(\d{1,2})\s*y[ıi]l\b', metin_lower)
    if m_ay or m_yil:
        try:
            if m_yil:
                gun = int(m_yil.group(1)) * 365
                ibaresi = f'{m_yil.group(1)} yıl'
            else:
                gun = int(m_ay.group(1)) * 30
                ibaresi = f'{m_ay.group(1)} ay'
            if gun <= limit_gun:
                return SartSonuc(
                    label, SartDurumu.VAR,
                    f'Rapor metni: "{ibaresi}" ≈ {gun} gün — limit altında',
                    kaynak='rapor_metni', grup=grup)
            return SartSonuc(
                label, SartDurumu.YOK,
                f'Rapor metni: "{ibaresi}" ≈ {gun} gün — limit {limit_gun} '
                f'gün üzerinde',
                kaynak='rapor_metni', grup=grup)
        except ValueError:
            pass

    return SartSonuc(
        label, SartDurumu.KONTROL_EDILEMEDI,
        'Rapor başlangıç/bitiş tarihleri pipeline\'a gelmiyor ve metinde '
        'süre ibaresi yok — eczacı doğrulamalı (SUT 4.2.13.1/8)',
        kaynak='rapor_tarihleri', grup=f'{grup} (bilgi)', sartli_atom=True)


# ═════════════════════════════════════════════════════════════════════════
# 6e. PAYLAŞILIR HELPER — başlangıç/devam atomlarını yolaklara ekle
# ═════════════════════════════════════════════════════════════════════════

def _hep_y_baslangic_devam_uygula(
        ilac_sonuc: Dict, metin_lower: str,
        kategori: str, etkin_tip: str,
        sartlar: List[SartSonuc], detaylar: Dict,
        ekle_eriskin_doz: bool = True,
        ekle_devam_atomlari: bool = True,
        rapor_sure_label_ilk: str = 'İlk rapor süresi ≤ 6 ay',
        rapor_sure_label_devam: str = 'Sonraki rapor süresi ≤ 1 yıl',
        rapor_sure_label_belirsiz: str = (
            'Rapor süresi: ilk rapor ≤6 ay, sonraki ≤1 yıl'),
        ) -> Tuple[str, str, Dict]:
    """B/D yolaklarında (Y1,Y2,Y3,Y4,Y5,Y7) başlangıç/devam dallanmasını uygular.

    - Reçete tipini tespit eder
    - Tip atomunu ekler
    - DB başlangıç raporu atomunu ekler
    - /3 erişkin başlangıç dozu (sadece HBV_ORAL + erişkin yolakları için)
    - /4, /6.a, /6.b, /7 devam atomları (sadece HBV_ORAL için)
    - /8 rapor süresi bilgi atomu

    Returns: (tip, gerekce, extra) — yolak fonksiyonu kararını verebilsin
    """
    tip, gerekce, extra = _hep_recete_tipi_tespit(
        ilac_sonuc, kategori, metin_lower)
    detaylar['recete_tipi'] = tip
    detaylar['recete_tipi_gerekce'] = gerekce
    detaylar['recete_tipi_extra'] = extra
    sartlar.append(_hep_atom_recete_tipi(tip, gerekce, kategori))

    is_baslangic = (tip == 'BASLANGIC')
    is_devam = (tip == 'DEVAM')
    is_belirsiz = (tip == 'BELIRSIZ')

    # DB sorgu atomu (geçmiş tarama)
    sartlar.append(_hep_baslangic_rapor_db_atom(ilac_sonuc, kategori))

    ilac_adi_upper = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_upper = (ilac_sonuc.get('etkin_madde') or '').upper()

    # /3 erişkin başlangıç dozu (BAŞLANGIÇ veya BELIRSIZ + HBV_ORAL)
    if ekle_eriskin_doz and etkin_tip == 'HBV_ORAL' and (
            is_baslangic or is_belirsiz):
        doz_atom = _hep_atom_eriskin_baslangic_dozu(ilac_adi_upper, etkin_upper)
        if is_belirsiz and '(bilgi)' not in doz_atom.grup:
            doz_atom.grup = doz_atom.grup + ' (bilgi)'
            doz_atom.sartli_atom = True
        sartlar.append(doz_atom)

    # Devam atomları (DEVAM veya BELIRSIZ + HBV_ORAL)
    if ekle_devam_atomlari and etkin_tip == 'HBV_ORAL' and (
            is_devam or is_belirsiz):
        gecmis_etken_gerekce = extra.get('gecmis_etken', '') if extra else ''
        # /4 alt-maddeler (1 atom aynı durumunda, 7 atom değişim durumunda)
        atomlar_devam: List[SartSonuc] = list(_hep_etken_degisim_atomlari(
            ilac_adi_upper, etkin_upper, gecmis_etken_gerekce, metin_lower))
        atomlar_devam.extend([
            _hep_atom_hbsag_antihbs_raporda(metin_lower),
            _hep_atom_sonlandirma_12ay(metin_lower),
            _hep_atom_hbsag_pozitif_devam(metin_lower),
        ])
        for a in atomlar_devam:
            if is_belirsiz and '(bilgi)' not in (a.grup or ''):
                a.grup = (a.grup or '') + ' (bilgi)'
                a.sartli_atom = True
        sartlar.extend(atomlar_devam)

    # /8 rapor süresi — tip'e göre etiket + tarih bazlı parse
    if is_baslangic:
        sart_label_8 = rapor_sure_label_ilk
    elif is_devam:
        sart_label_8 = rapor_sure_label_devam
    else:
        sart_label_8 = rapor_sure_label_belirsiz
    sure_atom = _hep_atom_rapor_suresi(
        ilac_sonuc, metin_lower, is_baslangic, is_devam, sart_label_8)
    if is_belirsiz and '(bilgi)' not in (sure_atom.grup or ''):
        sure_atom.grup = (sure_atom.grup or '') + ' (bilgi)'
        sure_atom.sartli_atom = True
    sartlar.append(sure_atom)

    return (tip, gerekce, extra)


def hep_icd_var(teshis_metin_upper: str, gecmis_icd: List[str],
                prefixleri: Tuple[str, ...]) -> Tuple[bool, str]:
    """ICD prefix'lerinden biri aktif teşhis veya geçmiş raporlarda var mı."""
    for pre in prefixleri:
        if pre in teshis_metin_upper:
            return (True, f'aktif_teshis:{pre}')
    for satir in (gecmis_icd or []):
        if not satir:
            continue
        upper = satir.upper()
        for pre in prefixleri:
            if upper.startswith(pre) or f' {pre}' in upper:
                return (True, f'gecmis_icd:{satir}')
    return (False, '')


# ═════════════════════════════════════════════════════════════════════════
# 6. ATOMIK ŞART HELPER — sayısal değer için 3-yönlü atom (VAR/YOK/KE)
# ═════════════════════════════════════════════════════════════════════════

def _hep_atom_sayisal_esik(deger: Optional[float],
                            esik: float,
                            op: str,
                            ad: str,
                            grup: str,
                            veya_grubu: bool = False,
                            kaynak: str = 'rapor_metni',
                            birim: str = '') -> SartSonuc:
    """Sayısal şart için 3-yönlü değerlendirme.

    op: '>=', '>', '<=', '<', '==', '!='
    deger None → KE (parser zayıf — manuel doğrulanmalı)
    """
    if deger is None:
        return SartSonuc(
            ad, SartDurumu.KONTROL_EDILEMEDI,
            'Değer rapordan parse edilemedi — manuel doğrulanmalı',
            kaynak, grup=grup, veya_grubu=veya_grubu, sartli_atom=True)
    sonuc = False
    if op == '>=':
        sonuc = deger >= esik
    elif op == '>':
        sonuc = deger > esik
    elif op == '<=':
        sonuc = deger <= esik
    elif op == '<':
        sonuc = deger < esik
    elif op == '==':
        sonuc = deger == esik
    elif op == '!=':
        sonuc = deger != esik
    durum = SartDurumu.VAR if sonuc else SartDurumu.YOK
    return SartSonuc(
        ad, durum,
        f'Değer: {deger:g}{birim} (eşik {op} {esik:g}) → '
        f'{"sağlanıyor" if sonuc else "sağlanmıyor"}',
        kaynak, grup=grup, veya_grubu=veya_grubu)


# ═════════════════════════════════════════════════════════════════════════
# 7. ÜST-VEYA AGGREGATOR (genel sonuç motoru, YOAK/Fibrat kalıbı)
# ═════════════════════════════════════════════════════════════════════════

def _hep_grup_durumu(grup_sartlar: List[SartSonuc],
                      veya: bool = False) -> SartDurumu:
    """Bir grup şartı toplu durumuna çevir (AND varsayılan).

    NA atomları (uygulanamaz şart, örn. başlangıç dalında devam atomu) sayılmaz.
    Tüm atomlar NA ise grup NA döner.
    """
    if not grup_sartlar:
        return SartDurumu.NA
    var = sum(1 for s in grup_sartlar if s.durum == SartDurumu.VAR)
    yok = sum(1 for s in grup_sartlar if s.durum == SartDurumu.YOK)
    ke = sum(1 for s in grup_sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI)
    if var == 0 and yok == 0 and ke == 0:
        return SartDurumu.NA
    if veya:
        if var > 0:
            return SartDurumu.VAR
        if ke > 0:
            return SartDurumu.KONTROL_EDILEMEDI
        return SartDurumu.YOK
    if yok > 0:
        return SartDurumu.YOK
    if ke > 0:
        return SartDurumu.KONTROL_EDILEMEDI
    return SartDurumu.VAR


def _hep_genel_sonuc(sartlar: List[SartSonuc], detaylar: Dict,
                      sut_kurali: str,
                      ust_or_ciftleri: Optional[List[Tuple[str, ...]]] = None,
                      yolak_etiketi: str = '') -> KontrolRaporu:
    """Atomik şart listesini KontrolRaporu'na çevir (YOAK kalıbı).

    ust_or_ciftleri: [(prefix1, prefix2, ...), ...]
        Aynı seviyede VEYA bağlı grup ad-prefix'leri. Birinin VAR olması yeterli.
    """
    gruplar: Dict[str, List[SartSonuc]] = {}
    for s in sartlar:
        gruplar.setdefault(s.grup, []).append(s)

    grup_durumlari: Dict[str, SartDurumu] = {}
    for ad, gs in gruplar.items():
        if not ad or '(bilgi)' in ad or '[paralel]' in ad:
            continue
        if gs and all(s.sartli_atom for s in gs):
            continue
        veya_flag = any(s.veya_grubu for s in gs)
        durum = _hep_grup_durumu(gs, veya=veya_flag)
        # NA gruplar verdict matematiğine girmez (uygulanamaz şart, örn.
        # başlangıç dalında devam atomları)
        if durum == SartDurumu.NA:
            continue
        grup_durumlari[ad] = durum

    # Üst-VEYA çiftleri
    for prefixler in (ust_or_ciftleri or []):
        keys = [next((k for k in grup_durumlari if k.startswith(p)), None)
                for p in prefixler]
        keys = [k for k in keys if k]
        if not keys:
            continue
        durumlar = [grup_durumlari[k] for k in keys]
        if any(d == SartDurumu.VAR for d in durumlar):
            sonuc = SartDurumu.VAR
        elif any(d == SartDurumu.KONTROL_EDILEMEDI for d in durumlar):
            sonuc = SartDurumu.KONTROL_EDILEMEDI
        else:
            sonuc = SartDurumu.YOK
        birlesik_ad = ' ∨ '.join(prefixler)
        grup_durumlari[f'Üst-VEYA: {birlesik_ad}'] = sonuc
        for k in keys:
            grup_durumlari.pop(k, None)

    yok_gruplar = [g for g, d in grup_durumlari.items()
                   if d == SartDurumu.YOK]
    ke_gruplar = [g for g, d in grup_durumlari.items()
                  if d == SartDurumu.KONTROL_EDILEMEDI]
    # (bilgi) atomlar verdict matematiğini bozmaz — şartlı atom listesinden de
    # filtrele (CLAUDE.md §6: parse edilemeyen şartlar bilgi grubunda tutulur)
    sartli_atomlar = [s for s in sartlar
                      if s.sartli_atom
                      and s.durum == SartDurumu.KONTROL_EDILEMEDI
                      and '(bilgi)' not in (s.grup or '')]

    detaylar['grup_durumlari'] = {g: d.value for g, d in grup_durumlari.items()}
    detaylar['yolak_etiketi'] = yolak_etiketi
    # `detaylar['yolak']` (kod: YOLAK1..YOLAK12) dispatch sırasında konuldu;
    # üzerine yazma — sadece insan-okur etiketi 'yolak_etiketi' anahtarına yaz.

    aranan = 'Hepatit endikasyonu + uzman raporu + viral yük / lab değerleri'
    if yok_gruplar:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj=f'{yolak_etiketi} UYGUN DEĞİL — sağlanmayan: '
                  f'{", ".join(yok_gruplar)}',
            sut_kurali=sut_kurali, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare=aranan,
            uyari='Eksik şart(lar) için reçete reddedilmeli ya da rapor düzeltilmeli')
    if ke_gruplar:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'{yolak_etiketi} ŞÜPHELİ — manuel doğrulanmalı: '
                  f'{", ".join(ke_gruplar)}',
            sut_kurali=sut_kurali, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare=aranan,
            uyari='Bazı şartlar metinden tespit edilemedi — eczacı doğrulamalı')
    if sartli_atomlar:
        adlar = [s.ad for s in sartli_atomlar]
        return KontrolRaporu(
            sonuc=KontrolSonucu.SARTLI_UYGUN,
            mesaj=f'{yolak_etiketi} ŞARTLI UYGUN — sistem sorgulayamıyor: '
                  f'{", ".join(adlar)} (eczacı doğrulamalı)',
            sut_kurali=sut_kurali, detaylar=detaylar, sartlar=sartlar,
            aranan_ibare=aranan,
            uyari='Şartlı atom(lar) eczacı tarafından doğrulanmalı')
    return KontrolRaporu(
        sonuc=KontrolSonucu.UYGUN,
        mesaj=f'{yolak_etiketi} UYGUN — tüm zorunlu şartlar sağlanıyor '
              f'({len(grup_durumlari)} grup VAR)',
        sut_kurali=sut_kurali, detaylar=detaylar, sartlar=sartlar,
        aranan_ibare=aranan)


# ═════════════════════════════════════════════════════════════════════════
# 8. YOLAK 1 — KRONIK HEPATIT B ERİŞKİN (4.2.13.1)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak1_eriskin_b(metin_lower: str, teshis_metin: str,
                            gecmis_icd: List[str], rapor_kodu: str,
                            yas: Optional[int], etkin_tip: str,
                            ilac_sonuc: Dict, sartlar: List[SartSonuc],
                            detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.1 — Kronik Hepatit B erişkin (≥18 yaş).

    Başlangıç-devam ayrımı (2026-05-21):
      • BAŞLANGIÇ: /1 HBV DNA + (HAI/fibrozis ∨ ALT/FIB-4/APRI) ∨ /1.b 40+ DNA≥20k,
        /3 erişkin doz (LAM 100/TBV 600/TDF 245/TAF 25/ETV 0.5)
      • DEVAM: /4 tedavi değişim gerekçesi, /6.a HBsAg/AntiHBs raporda,
        /6.b HBsAg-/AntiHBs+ → ≤12 ay sonlandırma, /7 HBsAg+ devam meşru
      • Tip BELİRSİZ ise her iki atom seti (bilgi) olarak — verdict matematiği
        sadece ortak atomlar (endikasyon, uzman rapor, /8 rapor süresi) üzerinden

    Yol-a: HBV DNA ≥ 10.000 kopya/ml + (HAI≥6 ∨ fibrozis≥2) ∨ (ALT yüksek
           3 ay arayla + (FIB-4>1.45 ∨ APRI>0.5))
    Yol-b: ≥40 yaş ∧ HBV DNA ≥ 20.000 IU/ml ∧ oral antiviral
    """
    detaylar['sut_maddesi'] = '4.2.13.1'

    # Reçete tipi tespit (BAŞLANGIÇ/DEVAM/BELIRSIZ) — atomları sartlar'a ekler
    # NOT: helper /3 erişkin doz + devam atomları + /8 rapor süresi + DB sorgu
    # atomlarını burada ekler; bizim aşağıda yapacağımız iş başlangıç-spesifik
    # yol-a / yol-b / pegile IFN şartlarını ekleyip etiketlemek.
    recete_tipi, tip_gerekce, tip_extra = _hep_y_baslangic_devam_uygula(
        ilac_sonuc, metin_lower, 'HEPATIT_B', etkin_tip, sartlar, detaylar)

    is_baslangic = (recete_tipi == 'BASLANGIC')
    is_devam = (recete_tipi == 'DEVAM')
    is_belirsiz = (recete_tipi == 'BELIRSIZ')
    # BELIRSIZ → başlangıç şartları (bilgi) olarak çalışsın; devam şartları da
    # (bilgi) olarak ekle. Burada sadece atom seçimini bayrakla yönlendiriyoruz.
    show_baslangic_atomlari = is_baslangic or is_belirsiz
    show_devam_atomlari = is_devam or is_belirsiz
    # BELIRSIZ ise atomları (bilgi) suffix'li gruplara yaz (verdict'i etkilemez)
    bilgi_suffix = ' (bilgi)' if is_belirsiz else ''

    # Endikasyon: HBV ICD veya rapor metni
    hbv_icd, _ = hep_icd_var(teshis_metin, gecmis_icd, ICD_KRONIK_B)
    hbv_metin = bool(re.search(r'(?:kronik\s*hepatit\s*b|hbv|hepatit\s*b\s*'
                                r'(?:enfeksiyon|tanı|virüs|virusu))',
                                metin_lower))
    if hbv_icd or hbv_metin:
        sartlar.append(SartSonuc(
            'Kronik Hepatit B tanısı',
            SartDurumu.VAR,
            f'ICD: {hbv_icd}, metin: {hbv_metin}',
            'teshis/rapor_metni', grup='(E) Endikasyon'))
    else:
        sartlar.append(SartSonuc(
            'Kronik Hepatit B tanısı',
            SartDurumu.KONTROL_EDILEMEDI,
            'ICD B18.0/B18.1 yok ve metinde "kronik hepatit B" ibaresi yok',
            'teshis/rapor_metni', grup='(E) Endikasyon', sartli_atom=True))

    ilac_adi_upper = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_upper = (ilac_sonuc.get('etkin_madde') or '').upper()

    # Sayısal parser'lar — başlangıç ve devam dallarında ortak kullanılabilir
    hbv_dna, _dna_birim = hep_parse_hbv_dna(metin_lower)

    # ════════════════════════════════════════════════════════════════════
    # BAŞLANGIÇ atomları — SUT 4.2.13.1/1, /1.b, /3, /2 (pegile IFN eşik)
    # ════════════════════════════════════════════════════════════════════
    if show_baslangic_atomlari:
        # YOL-a — HBV DNA + (histoloji ∨ ALT yol)
        g_a = f'(1)(a) HBV DNA + histoloji/ALT [yol-a]{bilgi_suffix}'
        # HBV DNA ≥ 10.000 kopya/ml ≈ 2.000 IU/ml
        if hbv_dna is None:
            sartlar.append(SartSonuc(
                'HBV DNA ≥ 2.000 IU/ml (10.000 kopya/ml)',
                SartDurumu.KONTROL_EDILEMEDI,
                'HBV DNA değeri rapordan parse edilemedi',
                'rapor_metni', grup=g_a, sartli_atom=True))
        elif hbv_dna < 0:
            sartlar.append(SartSonuc(
                'HBV DNA ≥ 2.000 IU/ml (10.000 kopya/ml)',
                SartDurumu.KONTROL_EDILEMEDI,
                'HBV DNA pozitif belirtilmiş ama sayısal değer yok — eşik '
                'aşımı manuel doğrulanmalı',
                'rapor_metni', grup=g_a, sartli_atom=True))
        else:
            sartlar.append(_hep_atom_sayisal_esik(
                hbv_dna, 2000.0, '>=',
                'HBV DNA ≥ 2.000 IU/ml (10.000 kopya/ml)',
                grup=g_a, birim=' IU/ml'))

        # Histoloji yolu: HAI ≥ 6 VEYA fibrozis ≥ 2
        hai = hep_parse_hai(metin_lower)
        fibroz = hep_parse_fibrozis(metin_lower)
        g_a_hist = f'(1)(a)(1) Histoloji (HAI≥6 ∨ fibrozis≥2) [yol-a-hist]{bilgi_suffix}'
        sartlar.append(_hep_atom_sayisal_esik(
            hai, 6.0, '>=', 'HAI ≥ 6 (Histolojik Aktivite İndeksi)',
            grup=g_a_hist, veya_grubu=True))
        sartlar.append(_hep_atom_sayisal_esik(
            fibroz, 2.0, '>=', 'Fibrozis ≥ 2',
            grup=g_a_hist, veya_grubu=True))

        # ALT yolu: 3 ay arayla ALT yüksek + (FIB-4 > 1.45 VEYA APRI > 0.5)
        alt_yuksek = hep_parse_alt_yuksek(metin_lower)
        alt_orani = hep_parse_alt_ust_sinir_orani(metin_lower)
        fib4 = hep_parse_fib4(metin_lower)
        apri = hep_parse_apri(metin_lower)

        uc_ay = bool(re.search(
            r'3\s*ay\s*ara|üç\s*ay\s*ara|3\s*ay\s*sonra\s*tekrar',
            metin_lower))

        g_a_alt = (f'(1)(a)(2) ALT yüksek + (FIB-4>1.45 ∨ APRI>0.5) '
                   f'[yol-a-alt]{bilgi_suffix}')
        if alt_yuksek is True or (alt_orani is not None and alt_orani > 1.0):
            sartlar.append(SartSonuc(
                'ALT normalin üzerinde (3 ay arayla 2 kez)',
                SartDurumu.VAR if uc_ay else SartDurumu.KONTROL_EDILEMEDI,
                f'ALT yüksek tespit edildi; 3 ay ara ibaresi: '
                f'{"VAR" if uc_ay else "yok"}',
                'rapor_metni', grup=g_a_alt, sartli_atom=not uc_ay))
        else:
            sartlar.append(SartSonuc(
                'ALT normalin üzerinde (3 ay arayla 2 kez)',
                SartDurumu.KONTROL_EDILEMEDI,
                'ALT yüksekliği ya da 3 ay ara ibaresi tespit edilemedi',
                'rapor_metni', grup=g_a_alt, sartli_atom=True))
        g_a_alt_iç = f'(1)(a)(2) FIB-4 ∨ APRI [yol-a-alt-iç]{bilgi_suffix}'
        sartlar.append(_hep_atom_sayisal_esik(
            fib4, 1.45, '>', 'FIB-4 > 1.45',
            grup=g_a_alt_iç, veya_grubu=True))
        sartlar.append(_hep_atom_sayisal_esik(
            apri, 0.5, '>', 'APRI > 0.5',
            grup=g_a_alt_iç, veya_grubu=True))

        # YOL-b — ≥40 yaş + HBV DNA ≥ 20.000 IU/ml + oral antiviral
        g_b = (f'(1)(b) ≥40 yaş + HBV DNA ≥ 20.000 IU/ml + oral antiviral '
               f'[yol-b]{bilgi_suffix}')
        if yas is None:
            sartlar.append(SartSonuc(
                'Hasta yaşı > 40',
                SartDurumu.KONTROL_EDILEMEDI,
                'Hasta yaşı bilinmiyor (TC yok)',
                'hasta_yasi', grup=g_b, sartli_atom=True))
        else:
            sartlar.append(SartSonuc(
                'Hasta yaşı > 40',
                SartDurumu.VAR if yas > 40 else SartDurumu.YOK,
                f'Hasta yaşı: {yas}',
                'hasta_yasi', grup=g_b))
        sartlar.append(_hep_atom_sayisal_esik(
            hbv_dna if (hbv_dna and hbv_dna > 0) else None,
            20000.0, '>=', 'HBV DNA ≥ 20.000 IU/ml (yol-b eşik)',
            grup=g_b, birim=' IU/ml'))
        sartlar.append(SartSonuc(
            'Reçete: oral antiviral (interferon değil)',
            SartDurumu.VAR if etkin_tip == 'HBV_ORAL' else SartDurumu.YOK,
            f'Reçete ilaç tipi: {etkin_tip}',
            'recete', grup=g_b))

        # Pegile IFN eligibilité (4.2.13.1/2.a) — TÜM PIF şartları aynı grup
        # adı altında AND ile birleşir; üst-VEYA çiftine tek prefix ile katılır.
        # SUT lafzı: "ALT > 2×ÜS VE [(HBeAg(-)∧DNA≤10⁷) VEYA (HBeAg(+)∧DNA≤10⁹)]"
        # Bu nedenle HBeAg+DNA koşulu TEK birleşik atom olarak üretilir
        # (içinde POZ/NEG OR mantığı atomun durumunda çözülür) — böylece grup
        # AND-OR karışımı olmadan saf AND olur ve _hep_grup_durumu doğru çalışır.
        if etkin_tip == 'PEG_IFN':
            g_pi = f'(2)(a) Pegile interferon — erişkin ek şartlar{bilgi_suffix}'
            if alt_orani is not None:
                sartlar.append(SartSonuc(
                    'ALT > 2× normalin üst sınırı (pegile IFN için)',
                    SartDurumu.VAR if alt_orani > 2.0 else SartDurumu.YOK,
                    f'ALT oranı: {alt_orani:g}× ÜS',
                    'rapor_metni', grup=g_pi))
            else:
                sartlar.append(SartSonuc(
                    'ALT > 2× normalin üst sınırı (pegile IFN için)',
                    SartDurumu.KONTROL_EDILEMEDI,
                    'ALT/ÜS oranı parse edilemedi',
                    'rapor_metni', grup=g_pi, sartli_atom=True))
            hbeag = hep_parse_hbeag(metin_lower)
            # HBeAg(±) + DNA eşik — POZ/NEG mantığı atom içinde çözülür
            if hbeag == 'NEG' and hbv_dna and hbv_dna > 0:
                eag_durum = (SartDurumu.VAR if hbv_dna * 5 <= 1e7
                              else SartDurumu.YOK)
                eag_neden = f'HBeAg=NEG, HBV DNA={hbv_dna} IU/ml (eşik 10⁷ kopya/ml)'
            elif hbeag == 'POZ' and hbv_dna and hbv_dna > 0:
                eag_durum = (SartDurumu.VAR if hbv_dna * 5 <= 1e9
                              else SartDurumu.YOK)
                eag_neden = f'HBeAg=POZ, HBV DNA={hbv_dna} IU/ml (eşik 10⁹ kopya/ml)'
            else:
                eag_durum = SartDurumu.KONTROL_EDILEMEDI
                eag_neden = (f'HBeAg={hbeag}, HBV DNA={hbv_dna} '
                             '— eşik karşılaştırması yapılamadı')
            sartlar.append(SartSonuc(
                '(HBeAg(-)∧DNA≤10⁷) ∨ (HBeAg(+)∧DNA≤10⁹) (pegile IFN)',
                eag_durum, eag_neden, 'rapor_metni', grup=g_pi,
                sartli_atom=(eag_durum == SartDurumu.KONTROL_EDILEMEDI)))
            sartlar.append(SartSonuc(
                'Tedavi süresi ≤ 48 hafta',
                SartDurumu.KONTROL_EDILEMEDI,
                'Süre rapora göre eczacı tarafından doğrulanmalı',
                'rapor_metni', grup=f'{g_pi} (bilgi)', sartli_atom=True))

        # NOT: /3 erişkin başlangıç dozu helper'da eklendi (yukarıda)

    # NOT: DEVAM atomları (/4, /6.a, /6.b, /7) + /8 rapor süresi +
    # _hep_baslangic_rapor_db_atom helper'da eklendi.

    # /1.4 Biyopsi kontrendikasyon — başlangıç dalı için bilgi (yol-a alternatif)
    if show_baslangic_atomlari:
        sartlar.append(_hep_bilgi_atom(
            'Biyopsi kontrendikasyon: PT>3sn ∨ trombosit<80k ∨ kanama ∨ '
            'KBY/nakil ∨ lezyon ∨ siroz ∨ karaciğer nakli ∨ gebelik ∨ '
            'psikiyatri uyumsuz',
            'Biyopsi koşulu aranmayan durumlar raporda açıkça belirtilmiş mi',
            grup_baslik='(1.4) Biyopsi kontrendikasyon (SUT 4.2.13.1.4)'))

    # Üst-VEYA çiftleri — sadece BAŞLANGIÇ atomları gerçekten verdict'e
    # girdiğinde anlamlı. DEVAM yalnız modunda yol-a/yol-b yok, çift listesi boş.
    # BELIRSIZ modunda atomlar (bilgi) suffix'li → aggregator zaten skip eder.
    # SUT 4.2.13.1: tedaviye "pegile interferonlar VEYA oral antiviraller" ile
    # başlanabilir → PIF kolu (4.2.13.1/2.a) yol-a/yol-b'nin alternatifidir.
    # Etken=PEG_IFN ise PIF kolu ust-VEYA çiftine dahil edilir.
    ust_or = []
    if is_baslangic:
        ana_yol = ['(1)(a) HBV DNA', '(1)(b) ≥40 yaş']
        if etkin_tip == 'PEG_IFN':
            ana_yol.append('(2)(a) Pegile interferon')
        ust_or = [
            tuple(ana_yol),
            ('(1)(a)(1) Histoloji',
             '(1)(a)(2) ALT yüksek',
             '(1)(a)(2) FIB-4'),
        ]

    yolak_etiket_suffix = ''
    if is_baslangic:
        yolak_etiket_suffix = ' — BAŞLANGIÇ'
    elif is_devam:
        yolak_etiket_suffix = ' — DEVAM'
    elif is_belirsiz:
        yolak_etiket_suffix = ' — BELİRSİZ (manuel doğrulama)'

    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        ust_or_ciftleri=ust_or,
        yolak_etiketi=f'[Yolak 1] Kronik Hepatit B Erişkin (4.2.13.1)'
                      f'{yolak_etiket_suffix}')


# ═════════════════════════════════════════════════════════════════════════
# 9. YOLAK 2 — KRONIK HEPATIT B ÇOCUK (4.2.13.1, 2-18 yaş)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak2_cocuk_b(metin_lower: str, teshis_metin: str,
                          gecmis_icd: List[str], rapor_kodu: str,
                          yas: Optional[int], etkin_tip: str,
                          ilac_sonuc: Dict, sartlar: List[SartSonuc],
                          detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.1 (1)(a)(1) — 2-18 yaş: ALT>2×ÜS + HAI≥4 VEYA fibrozis≥2."""
    detaylar['sut_maddesi'] = '4.2.13.1 (2-18 yaş)'

    # Yaş 2-18 atomu
    g_yas = '(0) Yaş 2-18'
    if yas is None:
        sartlar.append(SartSonuc(
            'Yaş 2-18 (çocuk)', SartDurumu.KONTROL_EDILEMEDI,
            'Hasta yaşı bilinmiyor', 'hasta_yasi',
            grup=g_yas, sartli_atom=True))
    elif 2 <= yas <= 18:
        sartlar.append(SartSonuc(
            'Yaş 2-18 (çocuk)', SartDurumu.VAR,
            f'Hasta yaşı: {yas}', 'hasta_yasi', grup=g_yas))
    else:
        sartlar.append(SartSonuc(
            'Yaş 2-18 (çocuk)', SartDurumu.YOK,
            f'Hasta yaşı: {yas} — çocuk yolağı değil',
            'hasta_yasi', grup=g_yas))

    # HBV tanı + HBV DNA ≥ 10.000 kopya/ml (2.000 IU/ml)
    hbv_dna, _ = hep_parse_hbv_dna(metin_lower)
    g_e = '(E) Endikasyon — HBV + HBV DNA'
    hbv_icd, _ = hep_icd_var(teshis_metin, gecmis_icd, ICD_KRONIK_B)
    sartlar.append(SartSonuc(
        'Kronik Hepatit B tanısı',
        SartDurumu.VAR if hbv_icd or 'hepatit b' in metin_lower
        else SartDurumu.KONTROL_EDILEMEDI,
        f'ICD: {hbv_icd}', 'teshis/rapor_metni', grup=g_e,
        sartli_atom=not hbv_icd))
    sartlar.append(_hep_atom_sayisal_esik(
        hbv_dna if (hbv_dna and hbv_dna > 0) else None,
        2000.0, '>=', 'HBV DNA ≥ 2.000 IU/ml',
        grup=g_e, birim=' IU/ml'))

    # ALT > 2× ÜS + HAI ≥ 4 VEYA fibrozis ≥ 2
    alt_orani = hep_parse_alt_ust_sinir_orani(metin_lower)
    hai = hep_parse_hai(metin_lower)
    fibroz = hep_parse_fibrozis(metin_lower)

    g_alt = '(1)(a)(1) ALT>2×ÜS ∧ HAI≥4 [çocuk-yol1]'
    sartlar.append(_hep_atom_sayisal_esik(
        alt_orani, 2.0, '>', 'ALT > 2× normalin üst sınırı',
        grup=g_alt))
    sartlar.append(_hep_atom_sayisal_esik(
        hai, 4.0, '>=', 'HAI ≥ 4',
        grup=g_alt))

    g_fibroz = '(1)(a)(1) Fibrozis ≥ 2 (ALT şartsız) [çocuk-yol2]'
    sartlar.append(_hep_atom_sayisal_esik(
        fibroz, 2.0, '>=', 'Fibrozis ≥ 2',
        grup=g_fibroz))

    # Başlangıç/devam dallanması (DB sorgu + /4-/6/7 + /8 helper'da)
    # NOT: Çocuk için /3 erişkin başlangıç dozu uygulanmaz (çocuk yaş-doz çocuk
    # tablosunda). Devam atomları (/4 değişim, /6 son /7 HBsAg+) çocuk için de
    # geçerli (SUT 4.2.13.1/5(b)1-6 → 4.2.13.1/4'e paralel).
    recete_tipi, tip_gerekce, tip_extra = _hep_y_baslangic_devam_uygula(
        ilac_sonuc, metin_lower, 'HEPATIT_B', etkin_tip, sartlar, detaylar,
        ekle_eriskin_doz=False)

    # Çocuk yaş-doz (bilgi)
    sartlar.append(_hep_bilgi_atom(
        'Yaş-doz uyumu: LAM 3mg/kg/gün (2-18) ∨ TDF 245mg/gün (12-18) ∨ '
        'TAF 25mg/gün (12-18) ∨ ETV 0.5mg/gün (16-18)',
        'Reçete dozu çocuk yaş aralığına uygun mu — eczacı doğrulamalı',
        grup_baslik='(5) Çocuk yaş-doz (SUT 4.2.13.1/5)',
        kaynak='recete/hasta_yasi'))
    # 4.2.13.1.4 — Biyopsi kontrendikasyon (çocuk Knodell skor)
    sartlar.append(_hep_bilgi_atom(
        'Biyopsi kontrendikasyon (Knodell skor): PT>3sn ∨ trombosit<80k ∨ '
        'kanama ∨ KBY ∨ lezyon ∨ siroz/nakil ∨ gebelik ∨ psikiyatri uyumsuz',
        'Biyopsi koşulu aranmayan durumlar raporda açıkça belirtilmiş mi',
        grup_baslik='(1.4) Biyopsi kontrendikasyon (SUT 4.2.13.1.4)'))

    etiket_suffix = (
        ' — BAŞLANGIÇ' if recete_tipi == 'BASLANGIC' else
        ' — DEVAM' if recete_tipi == 'DEVAM' else
        ' — BELİRSİZ (manuel doğrulama)')
    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        ust_or_ciftleri=[
            ('(1)(a)(1) ALT>2×ÜS', '(1)(a)(1) Fibrozis ≥ 2')],
        yolak_etiketi=f'[Yolak 2] Kronik Hepatit B Çocuk 2-18 (4.2.13.1)'
                      f'{etiket_suffix}')


# ═════════════════════════════════════════════════════════════════════════
# 10. YOLAK 3 — B SİROZ (4.2.13.1.1)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak3_b_siroz(metin_lower: str, teshis_metin: str,
                          gecmis_icd: List[str], rapor_kodu: str,
                          ilac_sonuc: Dict, sartlar: List[SartSonuc],
                          detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.1.1 — Karaciğer sirozunda HBV DNA(+) ile tedavi."""
    detaylar['sut_maddesi'] = '4.2.13.1.1'

    g_e = '(E) Endikasyon — siroz + HBV DNA(+)'
    siroz = bool(re.search(r'(?:karaciğer\s*siroz|siroz\b|hepatik\s*siroz|'
                            r'siroza\s*bağlı)', metin_lower))
    siroz_icd, _ = hep_icd_var(teshis_metin, gecmis_icd, ('K74', 'K70.3'))
    sartlar.append(SartSonuc(
        'Karaciğer sirozu',
        SartDurumu.VAR if (siroz or siroz_icd) else SartDurumu.KONTROL_EDILEMEDI,
        f'Metin lafzı={siroz}, ICD={siroz_icd}',
        'teshis/rapor_metni', grup=g_e, sartli_atom=not (siroz or siroz_icd)))

    hbv_dna, _ = hep_parse_hbv_dna(metin_lower)
    if hbv_dna is None:
        sartlar.append(SartSonuc(
            'HBV DNA pozitif',
            SartDurumu.KONTROL_EDILEMEDI,
            'HBV DNA durumu raporda yok',
            'rapor_metni', grup=g_e, sartli_atom=True))
    elif hbv_dna < 0 or hbv_dna > 0:
        sartlar.append(SartSonuc(
            'HBV DNA pozitif',
            SartDurumu.VAR,
            f'HBV DNA: {hbv_dna} (pozitif)',
            'rapor_metni', grup=g_e))
    else:
        sartlar.append(SartSonuc(
            'HBV DNA pozitif',
            SartDurumu.YOK,
            'HBV DNA negatif/0 — siroz tedavi koşulu yok',
            'rapor_metni', grup=g_e))

    # Biyopsi VAR/YOK üst-VEYA — SUT 4.2.13.1.1:
    # "biyopsi kanıtı olmayan hastalarda trombosit<150.000 ∨ PT≥3sn"
    # Yol-A: Biyopsi VAR (HAI/fibrozis raporlanmış)
    # Yol-B: Biyopsi YOK + (trombosit<150k ∨ PT≥3sn)
    hai = hep_parse_hai(metin_lower)
    fibroz = hep_parse_fibrozis(metin_lower)
    trombo = hep_parse_trombosit(metin_lower)
    pt_uz = hep_parse_pt_uzun(metin_lower)
    biyopsi_var_metin = bool(re.search(r'(?:biyopsi\s*yapıld|biyopsi\s*kanıt|'
                                         r'biyopsi\s*sonuc|hai\s*[:=]|'
                                         r'fibrozis\s*[:=]|metavir|ishak\s*skor)',
                                         metin_lower))

    g_yol_a = '(1)(A) Biyopsi VAR (HAI/fibrozis raporlanmış)'
    sartlar.append(SartSonuc(
        'Biyopsi kanıtı VAR (HAI/fibrozis raporlanmış)',
        SartDurumu.VAR if (hai is not None or fibroz is not None
                             or biyopsi_var_metin)
        else SartDurumu.KONTROL_EDILEMEDI,
        f'HAI={hai}, fibrozis={fibroz}, metin ibaresi={biyopsi_var_metin}',
        'rapor_metni', grup=g_yol_a, sartli_atom=(
            hai is None and fibroz is None and not biyopsi_var_metin)))

    g_yol_b = '(1)(B) Biyopsi YOK → trombosit<150.000 ∨ PT≥3sn'
    sartlar.append(_hep_atom_sayisal_esik(
        trombo, 150000.0, '<', 'Trombosit < 150.000/mm³',
        grup=g_yol_b, veya_grubu=True, birim='/mm³'))
    sartlar.append(_hep_atom_sayisal_esik(
        pt_uz, 3.0, '>=', 'PT uzaması ≥ 3 sn',
        grup=g_yol_b, veya_grubu=True, birim=' sn'))

    # Başlangıç/devam dallanması — SUT 4.2.13.1 genel ilkeleri (siroz altında).
    # Siroz hastasında oral antiviral kullanılır → /3 erişkin doz + /4/6/7 geçer.
    # etkin_tip Y3'e parametre olarak gelmiyor; ilac_sonuc'tan tespit edilir.
    _et_y3 = _hep_etken_tip(
        (ilac_sonuc.get('ilac_adi') or ''),
        (ilac_sonuc.get('etkin_madde') or ''))
    recete_tipi, _, _ = _hep_y_baslangic_devam_uygula(
        ilac_sonuc, metin_lower, 'HEPATIT_B', _et_y3, sartlar, detaylar)

    etiket_suffix = (
        ' — BAŞLANGIÇ' if recete_tipi == 'BASLANGIC' else
        ' — DEVAM' if recete_tipi == 'DEVAM' else
        ' — BELİRSİZ (manuel doğrulama)')
    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        ust_or_ciftleri=[
            ('(1)(A) Biyopsi VAR', '(1)(B) Biyopsi YOK')],
        yolak_etiketi=f'[Yolak 3] Hepatit B Siroz (4.2.13.1.1){etiket_suffix}')


# ═════════════════════════════════════════════════════════════════════════
# 11. YOLAK 4 — B + İMMÜNSÜPRESİF (4.2.13.1.2)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak4_b_immunsup(metin_lower: str, teshis_metin: str,
                             gecmis_icd: List[str], rapor_kodu: str,
                             ilac_sonuc: Dict, sartlar: List[SartSonuc],
                             detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.1.2 — İmmünsupresif/kemoterapi/monoklonal alan HBV tedavisi.

    3 alt-yolak:
        (1) HBsAg(+) → ALT/HBV DNA/biyopsi şartsız
        (2) Kronik B + immünsupresif → normal Kronik B kuralları (= Yolak 1)
        (3) HBsAg(-) ∧ (HBV DNA(+) ∨ Anti-HBc(+)) → şartsız
    """
    detaylar['sut_maddesi'] = '4.2.13.1.2'

    # Ortak: İmmünsupresif/kemo/monoklonal tedavi alıyor mu?
    g_im = '(E) İmmünsupresif/kemo/monoklonal tedavisi alıyor'
    imsup = bool(re.search(r'(?:immünsupresif|immunsupresif|immunosup|'
                            r'kemoterapi|sitotoks|monoklonal\s*antikor|'
                            r'rituximab|tnf\s*inhibit|biyolojik\s*ajan|'
                            r'metilprednizolon\s*yüksek|prednizolon\s*yüksek)',
                            metin_lower))
    # Diğer reçete ilaçlarında / geçmiş raporlarda da bak
    diger_ilaclar = ilac_sonuc.get('recete_ilaclari') or []
    diger_ad = ' '.join([(str(i.get('ad', '')) if isinstance(i, dict) else str(i))
                          for i in diger_ilaclar]).upper()
    imsup_ilac = bool(re.search(
        r'(?:RITUXIMAB|INFLIXIMAB|ADALIMUMAB|ETANERCEPT|GOLIMUMAB|TOCILIZUMAB|'
        r'METHOTREXATE|AZATIYOPRIN|MYCOPHENOLATE|SIKLOSPORIN|TAKROLIMUS|'
        r'CYCLOPHOSPHAMIDE|VINCRISTINE)', diger_ad))
    if imsup or imsup_ilac:
        sartlar.append(SartSonuc(
            'İmmünsupresif/kemo/monoklonal tedavi',
            SartDurumu.VAR,
            f'Metin: {imsup}, Reçete kalemleri: {imsup_ilac}',
            'rapor_metni/recete', grup=g_im))
    else:
        sartlar.append(SartSonuc(
            'İmmünsupresif/kemo/monoklonal tedavi',
            SartDurumu.KONTROL_EDILEMEDI,
            'Rapor / reçete / geçmiş kalemlerde immünsupresif tedavi tespit '
            'edilemedi — başka eczanede olabilir, manuel doğrulanmalı',
            'rapor_metni', grup=g_im, sartli_atom=True))

    # 3 alt-yolak (üst-VEYA)
    hbsag = hep_parse_hbsag(metin_lower)
    hbv_dna, _ = hep_parse_hbv_dna(metin_lower)
    anti_hbc = hep_parse_anti_hbc(metin_lower)

    g_y1 = '(1) HBsAg(+) yolu'
    sartlar.append(SartSonuc(
        'HBsAg pozitif',
        SartDurumu.VAR if hbsag == 'POZ' else (
            SartDurumu.YOK if hbsag == 'NEG' else SartDurumu.KONTROL_EDILEMEDI),
        f'HBsAg: {hbsag}',
        'rapor_metni', grup=g_y1, sartli_atom=hbsag is None))

    g_y3 = '(3) HBsAg(-) ∧ (HBV DNA(+) ∨ Anti-HBc(+)) yolu'
    sartlar.append(SartSonuc(
        'HBsAg(-) ∧ (HBV DNA(+) ∨ Anti-HBc(+))',
        SartDurumu.VAR if (hbsag == 'NEG' and (
            (hbv_dna and hbv_dna != 0) or anti_hbc == 'POZ'))
        else (SartDurumu.YOK if hbsag == 'POZ'
              else SartDurumu.KONTROL_EDILEMEDI),
        f'HBsAg={hbsag}, HBV DNA={hbv_dna}, Anti-HBc={anti_hbc}',
        'rapor_metni', grup=g_y3,
        sartli_atom=(hbsag is None or
                     (hbsag == 'NEG' and hbv_dna is None and anti_hbc is None))))

    # Tedavi sonrası 12 ay devamı (bilgi)
    g_devam = '(1)(3) Tedavi bitimi sonrası ≤12 ay devam (bilgi)'
    sartlar.append(SartSonuc(
        'Antiviral tedavi süresi: immünsup tedavi + sonrası ≤ 12 ay',
        SartDurumu.KONTROL_EDILEMEDI,
        'Tedavi başlangıç/bitiş tarihleri rapora göre eczacı doğrulamalı',
        'rapor_metni', grup=f'{g_devam} (bilgi)', sartli_atom=True))

    # 4.2.13.1/8 — Rapor süresi
    sartlar.append(_hep_bilgi_atom(
        'Rapor süresi: ilk rapor ≤6 ay, sonraki ≤1 yıl',
        'Rapor başlangıç/bitiş tarihleri eczacı tarafından doğrulanmalı',
        grup_baslik='(8) Rapor süresi (SUT 4.2.13.1/8)',
        kaynak='rapor_tarihi'))

    # Başlangıç/idame raporu DB sorgu (MEDULA geçmiş tarama)
    sartlar.append(_hep_baslangic_rapor_db_atom(ilac_sonuc, 'HEPATIT_B'))

    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        ust_or_ciftleri=[('(1) HBsAg(+) yolu',
                          '(3) HBsAg(-) ∧ (HBV DNA(+)')],
        yolak_etiketi='[Yolak 4] Hepatit B + İmmünsüpresif (4.2.13.1.2)')


# ═════════════════════════════════════════════════════════════════════════
# 12. YOLAK 5 — B TRANSPLANT (4.2.13.1.3)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak5_b_transplant(metin_lower: str, teshis_metin: str,
                                gecmis_icd: List[str], rapor_kodu: str,
                                ilac_sonuc: Dict, sartlar: List[SartSonuc],
                                detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.1.3 — Karaciğer transplant (HBV) + Anti-HBc(+) donör.
    Biyopsi/seroloji/ALT/HBV DNA ŞARTSIZ.
    """
    detaylar['sut_maddesi'] = '4.2.13.1.3'

    g = '(E) Karaciğer transplant (HBV) ∨ Anti-HBc(+) donör'
    tx = bool(re.search(r'(?:karaciğer\s*nakl|karaciğer\s*transplant|'
                         r'liver\s*transplant|transplantasyon)', metin_lower))
    anti_hbc_donor = bool(re.search(r'anti[\s\-]?hbc.{0,30}donör|donörden.{0,30}anti'
                                     r'[\s\-]?hbc', metin_lower))
    tx_icd, _ = hep_icd_var(teshis_metin, gecmis_icd, ('Z94.4', 'T86.4'))

    if tx or anti_hbc_donor or tx_icd:
        sartlar.append(SartSonuc(
            'Karaciğer transplant (HBV) ∨ Anti-HBc(+) donör',
            SartDurumu.VAR,
            f'Metin transplant={tx}, Anti-HBc donör={anti_hbc_donor}, ICD={tx_icd}',
            'teshis/rapor_metni', grup=g))
    else:
        sartlar.append(SartSonuc(
            'Karaciğer transplant (HBV) ∨ Anti-HBc(+) donör',
            SartDurumu.KONTROL_EDILEMEDI,
            'Transplant ya da Anti-HBc(+) donör ibaresi tespit edilemedi',
            'teshis/rapor_metni', grup=g, sartli_atom=True))

    # 4.2.13.1/8 — Rapor süresi
    sartlar.append(_hep_bilgi_atom(
        'Rapor süresi: ilk rapor ≤6 ay, sonraki ≤1 yıl',
        'Rapor başlangıç/bitiş tarihleri eczacı tarafından doğrulanmalı',
        grup_baslik='(8) Rapor süresi (SUT 4.2.13.1/8)',
        kaynak='rapor_tarihi'))

    # Başlangıç/idame raporu DB sorgu (MEDULA geçmiş tarama)
    sartlar.append(_hep_baslangic_rapor_db_atom(ilac_sonuc, 'HEPATIT_B'))

    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        yolak_etiketi='[Yolak 5] Hepatit B Transplant (4.2.13.1.3)')


# ═════════════════════════════════════════════════════════════════════════
# 13. YOLAK 6 — AKUT HEPATIT B (4.2.13(3))
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak6_akut_b(metin_lower: str, teshis_metin: str,
                         gecmis_icd: List[str], rapor_kodu: str,
                         etkin_tip: str,
                         ilac_sonuc: Dict, sartlar: List[SartSonuc],
                         detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13(3) — Akut Hepatit B + ciddi klinik."""
    detaylar['sut_maddesi'] = '4.2.13(3)'

    g_e = '(E) Akut Hepatit B tanısı'
    akut = bool(re.search(r'akut\s*hepatit\s*b', metin_lower))
    akut_icd, _ = hep_icd_var(teshis_metin, gecmis_icd, ICD_AKUT_B)
    sartlar.append(SartSonuc(
        'Akut Hepatit B tanısı',
        SartDurumu.VAR if (akut or akut_icd) else SartDurumu.KONTROL_EDILEMEDI,
        f'Metin={akut}, ICD={akut_icd}',
        'teshis/rapor_metni', grup=g_e, sartli_atom=not (akut or akut_icd)))

    # Ciddi klinik (OR ≥1)
    g_kl = '(3)(a) Ciddi akut klinik (INR≥1.5 ∨ PT>4sn üzeri ∨ sarılık>4 hafta) [klinik]'
    inr = hep_parse_inr(metin_lower)
    pt_uz = hep_parse_pt_uzun(metin_lower)
    sar_hafta = hep_parse_sarilik_sure(metin_lower)
    sartlar.append(_hep_atom_sayisal_esik(
        inr, 1.5, '>=', 'INR ≥ 1.5',
        grup=g_kl, veya_grubu=True))
    sartlar.append(_hep_atom_sayisal_esik(
        pt_uz, 4.0, '>', 'PT > normalin üst sınırı + 4 sn',
        grup=g_kl, veya_grubu=True))
    sartlar.append(_hep_atom_sayisal_esik(
        sar_hafta, 4.0, '>', 'Sarılık > 4 hafta',
        grup=g_kl, veya_grubu=True))

    # İlaç: SB onaylı antiviral
    g_ilac = '(3) İlaç: SB onaylı antiviral'
    sartlar.append(SartSonuc(
        'Reçete: SB onaylı antiviral',
        SartDurumu.VAR if etkin_tip == 'HBV_ORAL' else SartDurumu.YOK,
        f'İlaç tipi: {etkin_tip}',
        'recete', grup=g_ilac))

    # Bitiş: 4 hafta arayla 2 kez HBsAg(-) (bilgi)
    g_bilgi = '(3) Tedavi limiti: 4hf arayla 2× HBsAg(-) (bilgi)'
    sartlar.append(SartSonuc(
        'Tedavi limiti: 4 hafta arayla 2× HBsAg negatifliği',
        SartDurumu.KONTROL_EDILEMEDI,
        'Tedavi sonu kriteri eczacı tarafından izlenmeli',
        'rapor_metni', grup=f'{g_bilgi} (bilgi)', sartli_atom=True))

    # Başlangıç/idame raporu DB sorgu (MEDULA geçmiş tarama)
    sartlar.append(_hep_baslangic_rapor_db_atom(ilac_sonuc, 'HEPATIT_B'))

    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        yolak_etiketi='[Yolak 6] Akut Hepatit B (4.2.13(3))')


# ═════════════════════════════════════════════════════════════════════════
# 14. YOLAK 7 — KRONIK HEPATIT D (Delta) — (4.2.13.2)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak7_kronik_d(metin_lower: str, teshis_metin: str,
                           gecmis_icd: List[str], rapor_kodu: str,
                           etkin_tip: str,
                           ilac_sonuc: Dict, sartlar: List[SartSonuc],
                           detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.2 — Delta ajanlı Kronik Hepatit B (Anti-HDV+)."""
    detaylar['sut_maddesi'] = '4.2.13.2'

    g_e = '(E) Endikasyon — Anti-HDV(+) + HBV DNA raporda'
    anti_hdv = hep_parse_anti_hdv(metin_lower)
    sartlar.append(SartSonuc(
        'Anti-HDV pozitif',
        SartDurumu.VAR if anti_hdv == 'POZ' else (
            SartDurumu.YOK if anti_hdv == 'NEG' else SartDurumu.KONTROL_EDILEMEDI),
        f'Anti-HDV: {anti_hdv}', 'rapor_metni',
        grup=g_e, sartli_atom=anti_hdv is None))

    hbv_dna, _ = hep_parse_hbv_dna(metin_lower)
    sartlar.append(SartSonuc(
        'HBV DNA sonucu raporda belirtilmiş',
        SartDurumu.VAR if hbv_dna is not None else SartDurumu.YOK,
        f'HBV DNA: {hbv_dna}', 'rapor_metni',
        grup=g_e))

    # Reçete: pegile IFN ve/veya oral antiviral
    g_ilac = '(1) İlaç — pegile IFN ± oral antiviral'
    sartlar.append(SartSonuc(
        'Reçete: pegile interferon (Delta yolu)',
        SartDurumu.VAR if etkin_tip == 'PEG_IFN' else (
            SartDurumu.VAR if etkin_tip == 'HBV_ORAL'
            else SartDurumu.KONTROL_EDILEMEDI),
        f'İlaç tipi: {etkin_tip}',
        'recete', grup=g_ilac, sartli_atom=False))

    # SUT 4.2.13.2: "Kronik Hepatit B tedavi koşullarını taşıyanlarda tedaviye
    # oral antiviral ilaçlardan biri eklenebilir." → Oral antiviral eklenmişse
    # Y1 (Kronik B Erişkin) atomlarını inline kontrol et.
    ust_or_y7: List[Tuple[str, ...]] = []
    if etkin_tip == 'HBV_ORAL':
        hai = hep_parse_hai(metin_lower)
        fibroz = hep_parse_fibrozis(metin_lower)
        alt_yuksek = hep_parse_alt_yuksek(metin_lower)
        alt_orani = hep_parse_alt_ust_sinir_orani(metin_lower)
        fib4 = hep_parse_fib4(metin_lower)
        apri = hep_parse_apri(metin_lower)

        # Yol-a-hist: HAI ≥ 6 ∨ fibrozis ≥ 2 (Kronik B Yol-a histoloji)
        g_kb_hist = '(KB-A-hist) Kronik B yol-a histoloji: HAI≥6 ∨ fibrozis≥2'
        sartlar.append(_hep_atom_sayisal_esik(
            hai, 6.0, '>=', 'HAI ≥ 6 (Histolojik Aktivite İndeksi)',
            grup=g_kb_hist, veya_grubu=True))
        sartlar.append(_hep_atom_sayisal_esik(
            fibroz, 2.0, '>=', 'Fibrozis ≥ 2',
            grup=g_kb_hist, veya_grubu=True))

        # Yol-a-alt: ALT > ÜS (3 ay arayla) + (FIB-4 > 1.45 ∨ APRI > 0.5)
        g_kb_alt = '(KB-A-alt) Kronik B yol-a ALT: ALT yüksek ∧ (FIB-4>1.45 ∨ APRI>0.5)'
        if alt_yuksek is True or (alt_orani is not None and alt_orani > 1.0):
            sartlar.append(SartSonuc(
                'ALT normalin üzerinde (3 ay arayla 2 kez)',
                SartDurumu.KONTROL_EDILEMEDI,
                f'ALT yüksek tespit edildi; 3 ay arası ibaresi manuel doğr.',
                'rapor_metni', grup=g_kb_alt, sartli_atom=True))
        else:
            sartlar.append(SartSonuc(
                'ALT normalin üzerinde (3 ay arayla 2 kez)',
                SartDurumu.KONTROL_EDILEMEDI,
                'ALT yüksekliği tespit edilemedi',
                'rapor_metni', grup=g_kb_alt, sartli_atom=True))
        g_kb_alt_ic = '(KB-A-alt-iç) Kronik B yol-a iç: FIB-4>1.45 ∨ APRI>0.5'
        sartlar.append(_hep_atom_sayisal_esik(
            fib4, 1.45, '>', 'FIB-4 > 1.45',
            grup=g_kb_alt_ic, veya_grubu=True))
        sartlar.append(_hep_atom_sayisal_esik(
            apri, 0.5, '>', 'APRI > 0.5',
            grup=g_kb_alt_ic, veya_grubu=True))

        # Yan-şart için üst-VEYA: histoloji ∨ ALT yolu (Kronik B kriterleri)
        ust_or_y7.append(('(KB-A-hist)', '(KB-A-alt-iç)'))

    # Başlangıç/devam dallanması — Delta (HEPATIT_D kategorisi). HBV oral için
    # B'nin başlangıç dozu (/3) + devam (/4/6/7) atomları geçerli (SUT 4.2.13.2
    # → "Kronik Hepatit B tedavi koşullarını taşıyanlarda oral antiviral
    # eklenebilir"). PEG_IFN ise erişkin doz tablosuna girmediği için
    # ekle_eriskin_doz=False otomatik (helper içinde etkin_tip kontrolü var).
    recete_tipi, _, _ = _hep_y_baslangic_devam_uygula(
        ilac_sonuc, metin_lower, 'HEPATIT_D', etkin_tip, sartlar, detaylar)
    # HBV oral varsa ayrıca HEPATIT_B kategorisinden de başlangıç raporu sorgu
    if etkin_tip == 'HBV_ORAL':
        sartlar.append(_hep_baslangic_rapor_db_atom(ilac_sonuc, 'HEPATIT_B'))

    # EK-4E Madde 11/A/10 — Enf Uzm raporu, bulunmadığı yerlerde reçete açıklama
    # bölümünde belirtilmesi koşuluyla iç hastalıkları/çocuk hast uzm reçete eder
    rec_aciklama = ' '.join([str(x) for x in
                               (ilac_sonuc.get('recete_aciklamalari') or [])])
    ek4e_belirtilmis = bool(re.search(
        r'(?:enfeksiyon\s*(?:uzm|hek|hast)\s*(?:yok|bulunma|olmadığı)|'
        r'enf\s*uzm.{0,20}yok|enfeksiyon.{0,20}bulunma)',
        _tr_lower(rec_aciklama)))
    sartlar.append(_hep_bilgi_atom(
        'EK-4E 11/A/10: Enf Uzm yoksa İç Hast/Çocuk SH yazabilir (reçete '
        'açıklamasında belirtilmek koşuluyla)',
        f'Reçete açıklaması Enf Uzm yokluğunu belirtmiş={ek4e_belirtilmis} '
        f'— eczacı doğrulamalı',
        grup_baslik='(EK-4E) Enf Uzm yokluğunda yetki devri'))

    etiket_suffix = (
        ' — BAŞLANGIÇ' if recete_tipi == 'BASLANGIC' else
        ' — DEVAM' if recete_tipi == 'DEVAM' else
        ' — BELİRSİZ (manuel doğrulama)')
    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        ust_or_ciftleri=ust_or_y7 or None,
        yolak_etiketi=f'[Yolak 7] Kronik Hepatit D / Delta (4.2.13.2)'
                      f'{etiket_suffix}')


# ═════════════════════════════════════════════════════════════════════════
# 15. YOLAK 8 — AKUT HEPATIT C (4.2.13.3.1)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak8_akut_c(metin_lower: str, teshis_metin: str,
                         gecmis_icd: List[str], rapor_kodu: str,
                         etkin_tip: str,
                         ilac_sonuc: Dict, sartlar: List[SartSonuc],
                         detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.3.1 — Akut Hepatit C. 24 hafta pegile IFN MONOTERAPI.
    Ribavirin EKLENEMEZ.
    """
    detaylar['sut_maddesi'] = '4.2.13.3.1'

    g_e = '(E) Akut Hepatit C + HCV RNA(+)'
    akut_c = bool(re.search(r'akut\s*hepatit\s*c', metin_lower))
    akut_c_icd, _ = hep_icd_var(teshis_metin, gecmis_icd, ICD_AKUT_C)
    sartlar.append(SartSonuc(
        'Akut Hepatit C tanısı',
        SartDurumu.VAR if (akut_c or akut_c_icd) else SartDurumu.KONTROL_EDILEMEDI,
        f'Metin={akut_c}, ICD={akut_c_icd}',
        'teshis/rapor_metni', grup=g_e, sartli_atom=not (akut_c or akut_c_icd)))

    hcv_rna, hcv_rna_dur = hep_parse_hcv_rna(metin_lower)
    if hcv_rna is None:
        sartlar.append(SartSonuc(
            'HCV RNA pozitif (raporda)',
            SartDurumu.KONTROL_EDILEMEDI,
            'HCV RNA değeri/durumu raporda yok',
            'rapor_metni', grup=g_e, sartli_atom=True))
    elif hcv_rna == 0:
        sartlar.append(SartSonuc(
            'HCV RNA pozitif (raporda)',
            SartDurumu.YOK,
            'HCV RNA negatif — akut C tedavi koşulu yok',
            'rapor_metni', grup=g_e))
    else:
        sartlar.append(SartSonuc(
            'HCV RNA pozitif (raporda)',
            SartDurumu.VAR,
            f'HCV RNA: {hcv_rna} ({hcv_rna_dur})',
            'rapor_metni', grup=g_e))

    # İlaç: pegile IFN alfa monoterapi
    g_ilac = '(2) Reçete: pegile IFN alfa monoterapi'
    sartlar.append(SartSonuc(
        'Reçete: pegile interferon alfa',
        SartDurumu.VAR if etkin_tip == 'PEG_IFN' else SartDurumu.YOK,
        f'İlaç tipi: {etkin_tip}',
        'recete', grup=g_ilac))

    # KRITIK: Ribavirin EKLENEMEZ (negatif şart)
    g_yasak = '(2) Ribavirin yasağı — reçetede olmamalı'
    diger_ilaclar = ilac_sonuc.get('recete_ilaclari') or []
    diger_ad = ' '.join([(str(i.get('ad', '')) if isinstance(i, dict) else str(i))
                          for i in diger_ilaclar]).upper()
    rbv_var = (any(k in diger_ad for k in RIBAVIRIN_ETKEN)
               or any(k in diger_ad for k in RIBAVIRIN_TICARI))
    if rbv_var:
        sartlar.append(SartSonuc(
            'Ribavirin reçetede YOK (akut C için yasak)',
            SartDurumu.YOK,
            f'Reçete kalemlerinde ribavirin tespit edildi — akut C\'de YASAK',
            'recete', grup=g_yasak))
    else:
        sartlar.append(SartSonuc(
            'Ribavirin reçetede YOK (akut C için yasak)',
            SartDurumu.VAR,
            'Reçete kalemlerinde ribavirin yok (uygun)',
            'recete', grup=g_yasak))

    # Süre 24 hafta (bilgi)
    g_bilgi = '(2) Süre 24 hafta (bilgi)'
    sartlar.append(SartSonuc(
        'Tedavi süresi 24 hafta',
        SartDurumu.KONTROL_EDILEMEDI,
        'Süre rapor/eczacı doğrulaması ile takip edilmeli',
        'rapor_metni', grup=f'{g_bilgi} (bilgi)', sartli_atom=True))

    # Başlangıç/idame raporu DB sorgu (MEDULA geçmiş tarama)
    sartlar.append(_hep_baslangic_rapor_db_atom(ilac_sonuc, 'HEPATIT_C'))

    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        yolak_etiketi='[Yolak 8] Akut Hepatit C (4.2.13.3.1)')


# ═════════════════════════════════════════════════════════════════════════
# 16. HCV REJİM TESPİT YARDIMCISI (Yolak 9–12 ortak)
# ═════════════════════════════════════════════════════════════════════════

def _hep_hcv_rejim_tespit(ilac_adi_upper: str, etkin_upper: str,
                            diger_ilac_adlari_upper: str) -> str:
    """Reçetedeki HCV rejimini tespit et.

    Returns:
        'SVV'    — Sofosbuvir+Velpatasvir+Voxilaprevir (VOSEVI)
        'SV'     — Sofosbuvir+Velpatasvir (EPCLUSA)
        'SL'     — Sofosbuvir+Ledipasvir (HARVONI)
        'SOF'    — Sofosbuvir tek (SOVALDI)
        'GP'     — Glekaprevir+Pibrentasvir (MAVIRET/MAVYRET)
        'GP_RBV' — G+P + Ribavirin
        'SL_RBV' — Sofosbuvir+Ledipasvir + Ribavirin
        'IFN_RBV'/'PEG_RBV' — klasik kombinasyon (çocuk)
        'OTHER'  — başka
    """
    arama = ilac_adi_upper + ' ' + etkin_upper + ' ' + diger_ilac_adlari_upper
    has_sof = 'SOFOSBUVIR' in arama or 'SOVALDI' in arama
    has_vel = 'VELPATASVIR' in arama or 'EPCLUSA' in arama or 'VOSEVI' in arama
    has_vox = 'VOXILAPREVIR' in arama or 'VOSEVI' in arama
    has_led = 'LEDIPASVIR' in arama or 'HARVONI' in arama
    has_gle = ('GLEKAPREVIR' in arama or 'GLECAPREVIR' in arama
               or 'MAVIRET' in arama or 'MAVYRET' in arama)
    has_pib = 'PIBRENTASVIR' in arama or 'MAVIRET' in arama or 'MAVYRET' in arama
    has_rbv = any(k in arama for k in RIBAVIRIN_ETKEN + RIBAVIRIN_TICARI)
    has_ifn = any(k in arama for k in INTERFERON_ETKEN)
    has_peg = any(k in arama for k in PEG_IFN_ETKEN + PEG_IFN_TICARI)

    if has_sof and has_vel and has_vox:
        return 'SVV'
    if has_sof and has_vel:
        return 'SV'
    if has_sof and has_led and has_rbv:
        return 'SL_RBV'
    if has_sof and has_led:
        return 'SL'
    if has_gle and has_pib and has_rbv:
        return 'GP_RBV'
    if has_gle and has_pib:
        return 'GP'
    if has_peg and has_rbv:
        return 'PEG_RBV'
    if has_ifn and has_rbv:
        return 'IFN_RBV'
    if has_sof:
        return 'SOF'
    return 'OTHER'


# ═════════════════════════════════════════════════════════════════════════
# 17. YOLAK 9 — KRONIK HEPATIT C ERİŞKİN NAIVE (4.2.13.3.2.A.1)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak9_kronik_c_eriskin_naive(metin_lower: str, teshis_metin: str,
                                          gecmis_icd: List[str], rapor_kodu: str,
                                          yas: Optional[int], rejim: str,
                                          ilac_sonuc: Dict,
                                          sartlar: List[SartSonuc],
                                          detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.3.2.A.1 — Erişkin Kronik C, daha önce tedavi almamış.

    Nonsirotik: SVV 8 hafta ∨ GP 8 hafta
    Kompanse (Child A): SVV 12 hafta ∨ GP 8 hafta
    Dekompanse (Child B/C) ∧ G1a/1b/4/5/6: SL+RBV 12 hafta
    """
    detaylar['sut_maddesi'] = '4.2.13.3.2.A.1'

    # Endikasyon
    g_e = '(E) Kronik Hepatit C + HCV RNA(+)'
    kronik_c = bool(re.search(r'kronik\s*hepatit\s*c', metin_lower))
    kronik_c_icd, _ = hep_icd_var(teshis_metin, gecmis_icd, ICD_KRONIK_C)
    sartlar.append(SartSonuc(
        'Kronik Hepatit C tanısı',
        SartDurumu.VAR if (kronik_c or kronik_c_icd)
        else SartDurumu.KONTROL_EDILEMEDI,
        f'Metin={kronik_c}, ICD={kronik_c_icd}',
        'teshis/rapor_metni', grup=g_e,
        sartli_atom=not (kronik_c or kronik_c_icd)))

    hcv_rna, _ = hep_parse_hcv_rna(metin_lower)
    if hcv_rna is None:
        sartlar.append(SartSonuc(
            'HCV RNA pozitif',
            SartDurumu.KONTROL_EDILEMEDI,
            'HCV RNA durumu raporda yok',
            'rapor_metni', grup=g_e, sartli_atom=True))
    elif hcv_rna == 0:
        sartlar.append(SartSonuc(
            'HCV RNA pozitif', SartDurumu.YOK,
            'HCV RNA negatif', 'rapor_metni', grup=g_e))
    else:
        sartlar.append(SartSonuc(
            'HCV RNA pozitif', SartDurumu.VAR,
            f'HCV RNA: {hcv_rna}', 'rapor_metni', grup=g_e))

    # Erişkin yaş atomu
    if yas is None:
        sartlar.append(SartSonuc(
            'Erişkin yaş (≥18)', SartDurumu.KONTROL_EDILEMEDI,
            'Hasta yaşı bilinmiyor', 'hasta_yasi',
            grup=g_e, sartli_atom=True))
    else:
        sartlar.append(SartSonuc(
            'Erişkin yaş (≥18)',
            SartDurumu.VAR if yas >= 18 else SartDurumu.YOK,
            f'Hasta yaşı: {yas}', 'hasta_yasi', grup=g_e))

    # Naive (tedavi almamış) - kullanıcı doğrulaması zorunlu
    durum, neden, naive_detay = hep_onceki_hcv_tedavi_var_mi(
        metin_lower, ilac_sonuc)
    detaylar['hcv_gecmis'] = naive_detay
    # Naive yolağı için: önceki tedavi YOK olmalı
    if durum == SartDurumu.VAR:
        sartlar.append(SartSonuc(
            'Daha önce HCV tedavisi almamış (naive)',
            SartDurumu.YOK,
            f'Önceki HCV tedavi tespit edildi — naive yolağı UYGUN değil '
            f'(Yolak 10 deneyimli yolağı kullanılmalı). {neden}',
            naive_detay.get('kaynak', ''),
            grup=g_e))
    elif durum == SartDurumu.YOK:
        sartlar.append(SartSonuc(
            'Daha önce HCV tedavisi almamış (naive)',
            SartDurumu.VAR,
            f'Naive doğrulandı: {neden}',
            naive_detay.get('kaynak', 'rapor_metni'), grup=g_e))
    else:
        sartlar.append(SartSonuc(
            'Daha önce HCV tedavisi almamış (naive)',
            SartDurumu.KONTROL_EDILEMEDI,
            neden, 'rapor_metni/yerel_db', grup=g_e, sartli_atom=True))

    # Rapor şartları: 2/3. basamak + gastro/enf + içerik (HCV RNA + siroz + Child + genotip)
    sartlar.append(hep_atom_rapor_2_3_basamak(metin_lower, rapor_kodu))

    # Endikasyon-rejim eşleşme (3 alt-yolak ÜST-VEYA)
    siroz_durum = hep_parse_kompanse_dekompanse(metin_lower)
    cp = hep_parse_child_pugh(metin_lower)
    genotip = hep_parse_genotip(metin_lower)
    detaylar.update({'siroz_durum': siroz_durum, 'child_pugh': cp,
                     'genotip': genotip, 'rejim': rejim})

    # Grup 1 — Nonsirotik (SVV 8 hf ∨ GP 8 hf)
    g_g1 = '(A.1.1) Nonsirotik — SVV 8hf ∨ GP 8hf [grup-nonsirot]'
    is_nonsirot = (siroz_durum == 'nonsirotik')
    sartlar.append(SartSonuc(
        'Nonsirotik hasta',
        SartDurumu.VAR if is_nonsirot else (
            SartDurumu.YOK if siroz_durum else SartDurumu.KONTROL_EDILEMEDI),
        f'Siroz durumu: {siroz_durum}',
        'rapor_metni', grup=g_g1, sartli_atom=siroz_durum is None))
    sartlar.append(SartSonuc(
        'Reçete: SVV (Sofosbuvir+Velpatasvir+Voxilaprevir) ∨ GP',
        SartDurumu.VAR if rejim in ('SVV', 'GP') else SartDurumu.YOK,
        f'Rejim: {rejim}',
        'recete', grup=g_g1, veya_grubu=True))

    # Grup 2 — Kompanse Child A (SVV 12hf ∨ GP 8hf)
    g_g2 = '(A.1.2) Kompanse Child-Pugh A — SVV 12hf ∨ GP 8hf [grup-kompans]'
    is_komp = (siroz_durum == 'kompanse' or cp == 'A')
    sartlar.append(SartSonuc(
        'Kompanse sirotik (Child-Pugh A)',
        SartDurumu.VAR if is_komp else (
            SartDurumu.YOK if siroz_durum else SartDurumu.KONTROL_EDILEMEDI),
        f'Siroz={siroz_durum}, Child={cp}',
        'rapor_metni', grup=g_g2, sartli_atom=siroz_durum is None and cp is None))
    sartlar.append(SartSonuc(
        'Reçete: SVV ∨ GP (Child-A için)',
        SartDurumu.VAR if rejim in ('SVV', 'GP') else SartDurumu.YOK,
        f'Rejim: {rejim}',
        'recete', grup=g_g2, veya_grubu=True))

    # Grup 3 — Dekompanse Child B/C + Genotip 1a/1b/4/5/6 (SL+RBV 12hf)
    g_g3 = '(A.1.3) Dekompanse Child B/C + G1a/1b/4/5/6 — SL+RBV 12hf [grup-dekomp]'
    is_dekomp = (siroz_durum == 'dekompanse' or cp in ('B', 'C'))
    uygun_genotip = genotip in ('1', '1a', '1b', '4', '5', '6')
    sartlar.append(SartSonuc(
        'Dekompanse sirotik (Child B/C)',
        SartDurumu.VAR if is_dekomp else SartDurumu.YOK,
        f'Siroz={siroz_durum}, Child={cp}',
        'rapor_metni', grup=g_g3))
    sartlar.append(SartSonuc(
        'Genotip 1a/1b/4/5/6 (dekompanse için onaylı)',
        SartDurumu.VAR if uygun_genotip else (
            SartDurumu.YOK if genotip else SartDurumu.KONTROL_EDILEMEDI),
        f'Genotip: {genotip}',
        'rapor_metni', grup=g_g3, sartli_atom=genotip is None))
    sartlar.append(SartSonuc(
        'Reçete: Sofosbuvir+Ledipasvir+Ribavirin',
        SartDurumu.VAR if rejim == 'SL_RBV' else SartDurumu.YOK,
        f'Rejim: {rejim}',
        'recete', grup=g_g3))

    # Başlangıç/idame raporu DB sorgu
    sartlar.append(_hep_baslangic_rapor_db_atom(ilac_sonuc, 'HEPATIT_C'))

    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        ust_or_ciftleri=[
            ('(A.1.1) Nonsirotik',
             '(A.1.2) Kompanse Child-Pugh A',
             '(A.1.3) Dekompanse Child B/C')],
        yolak_etiketi='[Yolak 9] Kronik Hepatit C Erişkin Naive '
                       '(4.2.13.3.2.A.1)')


# ═════════════════════════════════════════════════════════════════════════
# 18. YOLAK 10 — KRONIK HCV ERİŞKİN DENEYİMLİ (4.2.13.3.2.A.2)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak10_kronik_c_eriskin_exp(metin_lower: str, teshis_metin: str,
                                          gecmis_icd: List[str], rapor_kodu: str,
                                          yas: Optional[int], rejim: str,
                                          ilac_sonuc: Dict,
                                          sartlar: List[SartSonuc],
                                          detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.3.2.A.2 — Erişkin Kronik C, tedavi deneyimli.

    EX1 NS5A almamış nonsirotik: SVV 12hf ∨ GP 8hf
    EX2 NS5A almamış kompanse:   SVV 12hf ∨ GP 12hf
    EX3 NS5A/proteaz almış nonsirot/kompans: SVV 12hf ∨ GP±RBV 16hf (SB onayı)
    EX4 NS5A/proteaz almış dekompans G1a/1b/4/5/6: SL+RBV 24hf
    """
    detaylar['sut_maddesi'] = '4.2.13.3.2.A.2'

    # Endikasyon — Yolak 9 ile aynı endikasyon atomları (tekrar)
    g_e = '(E) Kronik Hepatit C + HCV RNA(+) + erişkin'
    kronik_c = bool(re.search(r'kronik\s*hepatit\s*c', metin_lower))
    kronik_c_icd, _ = hep_icd_var(teshis_metin, gecmis_icd, ICD_KRONIK_C)
    sartlar.append(SartSonuc(
        'Kronik Hepatit C tanısı',
        SartDurumu.VAR if (kronik_c or kronik_c_icd)
        else SartDurumu.KONTROL_EDILEMEDI,
        f'Metin={kronik_c}, ICD={kronik_c_icd}',
        'teshis/rapor_metni', grup=g_e,
        sartli_atom=not (kronik_c or kronik_c_icd)))
    hcv_rna, _ = hep_parse_hcv_rna(metin_lower)
    sartlar.append(SartSonuc(
        'HCV RNA pozitif',
        (SartDurumu.VAR if (hcv_rna is not None and hcv_rna != 0)
         else (SartDurumu.YOK if hcv_rna == 0 else SartDurumu.KONTROL_EDILEMEDI)),
        f'HCV RNA: {hcv_rna}', 'rapor_metni', grup=g_e,
        sartli_atom=hcv_rna is None))
    if yas is not None:
        sartlar.append(SartSonuc(
            'Erişkin yaş (≥18)',
            SartDurumu.VAR if yas >= 18 else SartDurumu.YOK,
            f'Hasta yaşı: {yas}', 'hasta_yasi', grup=g_e))

    # Önceki tedavi — VAR olmalı + NS5A/proteaz tespiti
    durum, neden, gecmis_detay = hep_onceki_hcv_tedavi_var_mi(
        metin_lower, ilac_sonuc)
    detaylar['hcv_gecmis'] = gecmis_detay
    if durum == SartDurumu.VAR:
        sartlar.append(SartSonuc(
            'Daha önce HCV tedavisi almış (deneyimli)',
            SartDurumu.VAR, neden,
            gecmis_detay.get('kaynak', ''), grup=g_e))
    elif durum == SartDurumu.YOK:
        sartlar.append(SartSonuc(
            'Daha önce HCV tedavisi almış (deneyimli)',
            SartDurumu.YOK,
            f'Rapor naive — Yolak 10 değil, Yolak 9 (naive) kullanılmalı',
            'rapor_metni', grup=g_e))
    else:
        sartlar.append(SartSonuc(
            'Daha önce HCV tedavisi almış (deneyimli)',
            SartDurumu.KONTROL_EDILEMEDI, neden,
            'rapor_metni/yerel_db', grup=g_e, sartli_atom=True))

    ns5a_almis = gecmis_detay.get('ns5a', False)
    proteaz_almis = gecmis_detay.get('proteaz', False)
    siroz_durum = hep_parse_kompanse_dekompanse(metin_lower)
    cp = hep_parse_child_pugh(metin_lower)
    genotip = hep_parse_genotip(metin_lower)
    is_nonsirot = (siroz_durum == 'nonsirotik')
    is_komp = (siroz_durum == 'kompanse' or cp == 'A')
    is_dekomp = (siroz_durum == 'dekompanse' or cp in ('B', 'C'))
    detaylar.update({'siroz_durum': siroz_durum, 'child_pugh': cp,
                     'genotip': genotip, 'rejim': rejim,
                     'ns5a_almis': ns5a_almis, 'proteaz_almis': proteaz_almis})

    # EX1 — NS5A almamış nonsirotik (SVV 12hf ∨ GP 8hf)
    g_x1 = '(A.2.1) NS5A almamış nonsirotik [exp-1]'
    sartlar.append(SartSonuc(
        'NS5A almamış + nonsirotik',
        SartDurumu.VAR if (not ns5a_almis and is_nonsirot)
        else SartDurumu.YOK,
        f'NS5A almış={ns5a_almis}, nonsirotik={is_nonsirot}',
        'rapor_metni', grup=g_x1))
    sartlar.append(SartSonuc(
        'Reçete: SVV ∨ GP',
        SartDurumu.VAR if rejim in ('SVV', 'GP') else SartDurumu.YOK,
        f'Rejim: {rejim}', 'recete', grup=g_x1, veya_grubu=True))

    # EX2 — NS5A almamış kompanse (SVV 12hf ∨ GP 12hf)
    g_x2 = '(A.2.2) NS5A almamış kompanse Child A [exp-2]'
    sartlar.append(SartSonuc(
        'NS5A almamış + kompanse',
        SartDurumu.VAR if (not ns5a_almis and is_komp)
        else SartDurumu.YOK,
        f'NS5A={ns5a_almis}, kompanse={is_komp}',
        'rapor_metni', grup=g_x2))
    sartlar.append(SartSonuc(
        'Reçete: SVV ∨ GP (Child A için)',
        SartDurumu.VAR if rejim in ('SVV', 'GP') else SartDurumu.YOK,
        f'Rejim: {rejim}', 'recete', grup=g_x2, veya_grubu=True))

    # EX3 — NS5A/proteaz almış nonsirot/kompans (SVV 12hf ∨ GP±RBV 16hf)
    g_x3 = '(A.2.3) NS5A∨proteaz almış nonsirot/kompans [exp-3]'
    sartlar.append(SartSonuc(
        '(NS5A ∨ proteaz inhibitör) almış + nonsirot/kompans',
        SartDurumu.VAR if ((ns5a_almis or proteaz_almis)
                            and (is_nonsirot or is_komp))
        else SartDurumu.YOK,
        f'NS5A/proteaz alındı={ns5a_almis or proteaz_almis}, '
        f'nonsirot/komp={is_nonsirot or is_komp}',
        'rapor_metni', grup=g_x3))
    sartlar.append(SartSonuc(
        'Reçete: SVV ∨ GP±RBV (16hf SB onayı ile)',
        SartDurumu.VAR if rejim in ('SVV', 'GP', 'GP_RBV')
        else SartDurumu.YOK,
        f'Rejim: {rejim}', 'recete', grup=g_x3, veya_grubu=True))
    if rejim == 'GP_RBV':
        sartlar.append(SartSonuc(
            'SB hasta bazında onay (GP+RBV için bilgi)',
            SartDurumu.KONTROL_EDILEMEDI,
            'SB onay belgesi eczacı tarafından kontrol edilmeli',
            'rapor_metni', grup=f'{g_x3} (bilgi)', sartli_atom=True))

    # EX4 — NS5A/proteaz almış dekompanse G1a/1b/4/5/6 (SL+RBV 24hf)
    g_x4 = '(A.2.4) NS5A∨proteaz almış dekompans G1a/1b/4/5/6 [exp-4]'
    uygun_genotip = genotip in ('1', '1a', '1b', '4', '5', '6')
    sartlar.append(SartSonuc(
        '(NS5A ∨ proteaz) almış + dekompanse + G1a/1b/4/5/6',
        SartDurumu.VAR if ((ns5a_almis or proteaz_almis)
                            and is_dekomp and uygun_genotip)
        else SartDurumu.YOK,
        f'NS5A/proteaz alındı={ns5a_almis or proteaz_almis}, '
        f'dekomp={is_dekomp}, genotip={genotip}',
        'rapor_metni', grup=g_x4))
    sartlar.append(SartSonuc(
        'Reçete: Sofosbuvir+Ledipasvir+Ribavirin (24 hafta)',
        SartDurumu.VAR if rejim == 'SL_RBV' else SartDurumu.YOK,
        f'Rejim: {rejim}', 'recete', grup=g_x4))

    # Başlangıç/idame raporu DB sorgu (deneyimli için kritik — önceki HCV
    # tedavisini DB'den kanıtlayabiliriz)
    sartlar.append(_hep_baslangic_rapor_db_atom(ilac_sonuc, 'HEPATIT_C'))

    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        ust_or_ciftleri=[
            ('(A.2.1) NS5A almamış nonsirotik',
             '(A.2.2) NS5A almamış kompanse',
             '(A.2.3) NS5A∨proteaz almış nonsirot',
             '(A.2.4) NS5A∨proteaz almış dekompans')],
        yolak_etiketi='[Yolak 10] Kronik HCV Erişkin Deneyimli '
                       '(4.2.13.3.2.A.2)')


# ═════════════════════════════════════════════════════════════════════════
# 19. YOLAK 11 — KRONIK HCV ÇOCUK NAIVE (4.2.13.3.2.B)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak11_kronik_c_cocuk_naive(metin_lower: str, teshis_metin: str,
                                         gecmis_icd: List[str], rapor_kodu: str,
                                         yas: Optional[int], rejim: str,
                                         ilac_sonuc: Dict,
                                         sartlar: List[SartSonuc],
                                         detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.3.2.B — Çocuk Kronik C, naive."""
    detaylar['sut_maddesi'] = '4.2.13.3.2.B'

    g_e = '(E) Çocuk Kronik HCV + HCV RNA(+) + Genotip'
    sartlar.append(SartSonuc(
        'Kronik Hepatit C tanısı',
        SartDurumu.VAR if (re.search(r'kronik\s*hepatit\s*c', metin_lower)
                            or 'B18.2' in teshis_metin)
        else SartDurumu.KONTROL_EDILEMEDI,
        'Tanı: rapor metni / B18.2',
        'teshis/rapor_metni', grup=g_e, sartli_atom=True))
    hcv_rna, _ = hep_parse_hcv_rna(metin_lower)
    sartlar.append(SartSonuc(
        'HCV RNA pozitif',
        (SartDurumu.VAR if hcv_rna and hcv_rna != 0
         else (SartDurumu.YOK if hcv_rna == 0
               else SartDurumu.KONTROL_EDILEMEDI)),
        f'HCV RNA: {hcv_rna}', 'rapor_metni', grup=g_e,
        sartli_atom=hcv_rna is None))
    if yas is None:
        sartlar.append(SartSonuc(
            'Çocuk yaş (3-18)', SartDurumu.KONTROL_EDILEMEDI,
            'Hasta yaşı bilinmiyor', 'hasta_yasi', grup=g_e,
            sartli_atom=True))
    elif 3 <= yas <= 18:
        sartlar.append(SartSonuc(
            'Çocuk yaş (3-18)', SartDurumu.VAR,
            f'Hasta yaşı: {yas}', 'hasta_yasi', grup=g_e))
    else:
        sartlar.append(SartSonuc(
            'Çocuk yaş (3-18)', SartDurumu.YOK,
            f'Hasta yaşı: {yas} — çocuk yolağı dışı', 'hasta_yasi',
            grup=g_e))

    genotip = hep_parse_genotip(metin_lower)
    sartlar.append(SartSonuc(
        'Genotip tayini belirtilmiş',
        SartDurumu.VAR if genotip else SartDurumu.KONTROL_EDILEMEDI,
        f'Genotip: {genotip}', 'rapor_metni', grup=g_e,
        sartli_atom=genotip is None))

    # İlaç yolu A: IFN+RBV veya peg-IFN+RBV (RBV kontrendike ise tek)
    g_ilac_a = '(B.1) IFN+RBV ∨ peg-IFN+RBV ∨ tek (RBV kontrendike) [çocuk-rejim-1]'
    rbv_kontr = bool(re.search(r'(?:ribavirin\s*kontrendik|rbv\s*kontrendik|'
                                r'ribavirin\s*alerji|ribavirin\s*tolere\s*edemi)',
                                metin_lower))
    is_kombi = rejim in ('IFN_RBV', 'PEG_RBV')
    sartlar.append(SartSonuc(
        'Reçete: IFN+RBV ∨ peg-IFN+RBV (kombinasyon)',
        SartDurumu.VAR if is_kombi else (
            SartDurumu.VAR if rbv_kontr and rejim in ('IFN', 'PEG_IFN')
            else SartDurumu.YOK),
        f'Rejim: {rejim}, RBV kontrendike: {rbv_kontr}',
        'recete', grup=g_ilac_a, veya_grubu=True))

    # İlaç yolu B: 12-18 yaş naive → G+P 8 hafta (genotip serbest)
    g_ilac_b = '(B.5) 12-18 yaş naive: G+P 8 hafta [çocuk-rejim-2]'
    yas_uygun = yas is not None and 12 <= yas <= 18
    sartlar.append(SartSonuc(
        'Yaş 12-18 + Reçete: G+P 8 hafta',
        SartDurumu.VAR if (yas_uygun and rejim == 'GP') else SartDurumu.YOK,
        f'Yaş={yas}, Rejim={rejim}',
        'recete/hasta_yasi', grup=g_ilac_b, veya_grubu=True))

    # 3-18 yaş Ribavirin dozu (bilgi)
    g_doz = '(B.4) RBV dozu 15 mg/kg/gün, max 1200 mg (bilgi)'
    sartlar.append(SartSonuc(
        'Ribavirin dozu 15 mg/kg/gün (max 1200 mg)',
        SartDurumu.KONTROL_EDILEMEDI,
        'Doz hesabı eczacı tarafından doğrulanmalı (kilo gerekir)',
        'rapor_metni/recete', grup=f'{g_doz} (bilgi)', sartli_atom=True))

    # SUT 4.2.13.3.2.B (2) — Tek başına Ribavirin kullanım endikasyonu YOKTUR.
    # Reçetede Rib var ama IFN/PegIFN/HCV DAA yok ise UYGUN_DEĞİL.
    g_rib_yasak = '(B.2) Tek başına Ribavirin yasağı'
    diger_ilaclar = ilac_sonuc.get('recete_ilaclari') or []
    diger_ad_upper = ' '.join([
        (str(i.get('ad', '')) if isinstance(i, dict) else str(i)).upper()
        for i in diger_ilaclar])
    arama_all = (ilac_sonuc.get('ilac_adi') or '').upper() + ' ' + \
                (ilac_sonuc.get('etkin_madde') or '').upper() + ' ' + diger_ad_upper
    has_rib = (any(k in arama_all for k in RIBAVIRIN_ETKEN)
               or any(k in arama_all for k in RIBAVIRIN_TICARI))
    has_partner = (any(k in arama_all for k in INTERFERON_ETKEN)
                   or any(k in arama_all for k in PEG_IFN_ETKEN)
                   or any(k in arama_all for k in PEG_IFN_TICARI)
                   or any(k in arama_all for k in HCV_DAA_ETKEN)
                   or any(k in arama_all for k in HCV_DAA_TICARI))
    if has_rib and not has_partner:
        sartlar.append(SartSonuc(
            'Tek başına Ribavirin değil (IFN/PegIFN/DAA kombi olmalı)',
            SartDurumu.YOK,
            'Reçetede Ribavirin var ama IFN/PegIFN/HCV DAA yok — SUT 4.2.13.3.2.B(2) '
            'tek başına Ribavirin endikasyonu yoktur',
            'recete', grup=g_rib_yasak))
    elif has_rib and has_partner:
        sartlar.append(SartSonuc(
            'Tek başına Ribavirin değil (IFN/PegIFN/DAA kombi olmalı)',
            SartDurumu.VAR,
            'Ribavirin + kombinasyon ilacı reçetede mevcut (uygun)',
            'recete', grup=g_rib_yasak))
    else:
        # Rib yoksa atom uygulanmaz — bilgilendirme amaçlı VAR
        sartlar.append(SartSonuc(
            'Tek başına Ribavirin değil (IFN/PegIFN/DAA kombi olmalı)',
            SartDurumu.VAR,
            'Reçetede Ribavirin yok — yasak şartı uygulanmıyor',
            'recete', grup=g_rib_yasak))

    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        ust_or_ciftleri=[('(B.1) IFN+RBV', '(B.5) 12-18 yaş naive: G+P')],
        yolak_etiketi='[Yolak 11] Kronik HCV Çocuk Naive (4.2.13.3.2.B)')


# ═════════════════════════════════════════════════════════════════════════
# 20. YOLAK 12 — KRONIK HCV ÇOCUK DENEYİMLİ (4.2.13.3.2.B.1)
# ═════════════════════════════════════════════════════════════════════════

def _hep_yolak12_kronik_c_cocuk_exp(metin_lower: str, teshis_metin: str,
                                        gecmis_icd: List[str], rapor_kodu: str,
                                        yas: Optional[int], rejim: str,
                                        ilac_sonuc: Dict,
                                        sartlar: List[SartSonuc],
                                        detaylar: Dict) -> KontrolRaporu:
    """SUT 4.2.13.3.2.B.1 — Çocuk Kronik C, deneyimli.

    12-18 yaş için 6+ alt-kombinasyon (genotip × siroz × NS5A/proteaz geçmişi).
    """
    detaylar['sut_maddesi'] = '4.2.13.3.2.B.1'

    g_e = '(E) Çocuk 12-18 + Kronik C + deneyimli'
    if yas is None:
        sartlar.append(SartSonuc(
            'Yaş 12-18',
            SartDurumu.KONTROL_EDILEMEDI,
            'Hasta yaşı bilinmiyor', 'hasta_yasi',
            grup=g_e, sartli_atom=True))
    elif 12 <= yas <= 18:
        sartlar.append(SartSonuc(
            'Yaş 12-18', SartDurumu.VAR,
            f'Hasta yaşı: {yas}', 'hasta_yasi', grup=g_e))
    else:
        sartlar.append(SartSonuc(
            'Yaş 12-18', SartDurumu.YOK,
            f'Hasta yaşı: {yas} — bu yolak 12-18 yaş için',
            'hasta_yasi', grup=g_e))

    # Önceki tedavi durumu
    durum, neden, gecmis_detay = hep_onceki_hcv_tedavi_var_mi(
        metin_lower, ilac_sonuc)
    detaylar['hcv_gecmis'] = gecmis_detay
    sartlar.append(SartSonuc(
        'Daha önce HCV tedavisi almış (deneyimli)',
        durum if durum != SartDurumu.NA else SartDurumu.KONTROL_EDILEMEDI,
        neden, 'rapor_metni/yerel_db', grup=g_e,
        sartli_atom=durum == SartDurumu.KONTROL_EDILEMEDI))

    ns5a_almis = gecmis_detay.get('ns5a', False)
    proteaz_almis = gecmis_detay.get('proteaz', False)
    ifn_almis = gecmis_detay.get('ifn', False)
    sof_almis = gecmis_detay.get('sof', False)
    siroz_durum = hep_parse_kompanse_dekompanse(metin_lower)
    is_nonsirot = siroz_durum == 'nonsirotik'
    is_komp = siroz_durum == 'kompanse'
    genotip = hep_parse_genotip(metin_lower)

    # SL — Sofosbuvir+Ledipasvir
    g_sl_g1 = '(B.1.2a) SL: G1 nonsirot 12hf ∨ komp siroz 24hf [çocuk-exp-SL-G1]'
    g_sl_g456 = '(B.1.2a) SL: G4/5/6 nonsirot ∨ komp 12hf [çocuk-exp-SL-G456]'
    if rejim == 'SL':
        sartlar.append(SartSonuc(
            'Reçete: SL (Sofosbuvir+Ledipasvir)',
            SartDurumu.VAR, f'Rejim={rejim}', 'recete', grup=g_sl_g1))
        sartlar.append(SartSonuc(
            'Genotip 1 + (nonsirot 12hf ∨ kompanse siroz 24hf)',
            SartDurumu.VAR if (genotip in ('1', '1a', '1b')
                                and (is_nonsirot or is_komp))
            else SartDurumu.YOK,
            f'Genotip={genotip}, siroz={siroz_durum}',
            'rapor_metni', grup=g_sl_g1))
        sartlar.append(SartSonuc(
            'Genotip 4/5/6 + (nonsirot ∨ kompanse) 12hf',
            SartDurumu.VAR if (genotip in ('4', '5', '6')
                                and (is_nonsirot or is_komp))
            else SartDurumu.YOK,
            f'Genotip={genotip}, siroz={siroz_durum}',
            'rapor_metni', grup=g_sl_g456))

    # GP — Glekaprevir+Pibrentasvir (5 senaryo)
    g_gp_1 = '(B.1.2b) GP: G1,2,4,5,6 nonsirot + NS5A/proteaz almamış 8hf [exp-GP-1]'
    g_gp_2 = '(B.1.2b) GP: G1,2,4,5,6 kompanse + NS5A/proteaz almamış 12hf [exp-GP-2]'
    g_gp_3 = '(B.1.2b) GP: G3 + IFN/SOF almış, NS5A/proteaz almamış 16hf [exp-GP-3]'
    g_gp_4 = '(B.1.2b) GP: G1 + proteaz almış, NS5A almamış 12hf [exp-GP-4]'
    g_gp_5 = '(B.1.2b) GP: G1 + NS5A almış, proteaz almamış 16hf [exp-GP-5]'
    if rejim == 'GP':
        g12456 = genotip in ('1', '1a', '1b', '2', '4', '5', '6')
        g3 = genotip == '3'
        g1 = genotip in ('1', '1a', '1b')
        sartlar.append(SartSonuc(
            'G1,2,4,5,6 + nonsirot + NS5A/proteaz almamış',
            SartDurumu.VAR if (g12456 and is_nonsirot
                                and not ns5a_almis and not proteaz_almis)
            else SartDurumu.YOK,
            f'G={genotip}, nonsirot={is_nonsirot}, '
            f'NS5A={ns5a_almis}, proteaz={proteaz_almis}',
            'rapor_metni', grup=g_gp_1))
        sartlar.append(SartSonuc(
            'G1,2,4,5,6 + kompanse + NS5A/proteaz almamış',
            SartDurumu.VAR if (g12456 and is_komp
                                and not ns5a_almis and not proteaz_almis)
            else SartDurumu.YOK,
            f'G={genotip}, komp={is_komp}, '
            f'NS5A={ns5a_almis}, proteaz={proteaz_almis}',
            'rapor_metni', grup=g_gp_2))
        sartlar.append(SartSonuc(
            'G3 + IFN ∨ Sofosbuvir almış + NS5A/proteaz almamış',
            SartDurumu.VAR if (g3 and (ifn_almis or sof_almis)
                                and not ns5a_almis and not proteaz_almis)
            else SartDurumu.YOK,
            f'G={genotip}, IFN/SOF={ifn_almis or sof_almis}, '
            f'NS5A={ns5a_almis}, proteaz={proteaz_almis}',
            'rapor_metni', grup=g_gp_3))
        sartlar.append(SartSonuc(
            'G1 + proteaz almış + NS5A almamış',
            SartDurumu.VAR if (g1 and proteaz_almis and not ns5a_almis)
            else SartDurumu.YOK,
            f'G={genotip}, proteaz={proteaz_almis}, NS5A={ns5a_almis}',
            'rapor_metni', grup=g_gp_4))
        sartlar.append(SartSonuc(
            'G1 + NS5A almış + proteaz almamış',
            SartDurumu.VAR if (g1 and ns5a_almis and not proteaz_almis)
            else SartDurumu.YOK,
            f'G={genotip}, NS5A={ns5a_almis}, proteaz={proteaz_almis}',
            'rapor_metni', grup=g_gp_5))

    if rejim not in ('SL', 'GP'):
        # Bilinmeyen rejim — sadece bilgi
        sartlar.append(SartSonuc(
            'Reçete: SL ∨ GP (çocuk deneyimli için onaylı)',
            SartDurumu.YOK,
            f'Rejim {rejim} bu yolak için tanımlı değil',
            'recete', grup='(B.1) Onaylı rejim — SL ∨ GP'))

    return _hep_genel_sonuc(
        sartlar, detaylar, SUT_KURALI_HEPATIT,
        ust_or_ciftleri=[
            ('(B.1.2a) SL: G1 nonsirot',
             '(B.1.2a) SL: G4/5/6 nonsirot',
             '(B.1.2b) GP: G1,2,4,5,6 nonsirot',
             '(B.1.2b) GP: G1,2,4,5,6 kompanse',
             '(B.1.2b) GP: G3',
             '(B.1.2b) GP: G1 + proteaz almış',
             '(B.1.2b) GP: G1 + NS5A almış')],
        yolak_etiketi='[Yolak 12] Kronik HCV Çocuk Deneyimli '
                       '(4.2.13.3.2.B.1)')


# ═════════════════════════════════════════════════════════════════════════
# 21. ÜST-DÜZEY DISPATCHER
# ═════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════
# 20.5 YOLAK METADATA + DİĞER YOLAKLAR (accordion paneli için)
# ═════════════════════════════════════════════════════════════════════════

HEPATIT_YOLAK_METADATA: Dict[str, Dict[str, str]] = {
    'YOLAK1':  {'ad': 'Kronik Hepatit B Erişkin',          'sut': '4.2.13.1'},
    'YOLAK2':  {'ad': 'Kronik Hepatit B Çocuk (2-18)',     'sut': '4.2.13.1 (5)'},
    'YOLAK3':  {'ad': 'Hepatit B + Karaciğer Sirozu',       'sut': '4.2.13.1.1'},
    'YOLAK4':  {'ad': 'Hepatit B + İmmünsüpresif',          'sut': '4.2.13.1.2'},
    'YOLAK5':  {'ad': 'Hepatit B + Karaciğer Transplant',  'sut': '4.2.13.1.3'},
    'YOLAK6':  {'ad': 'Akut Hepatit B',                     'sut': '4.2.13 (3)'},
    'YOLAK7':  {'ad': 'Kronik Hepatit D (Delta)',          'sut': '4.2.13.2'},
    'YOLAK8':  {'ad': 'Akut Hepatit C',                     'sut': '4.2.13.3.1'},
    'YOLAK9':  {'ad': 'Kronik HCV Erişkin Naive',          'sut': '4.2.13.3.2.A.1'},
    'YOLAK10': {'ad': 'Kronik HCV Erişkin Deneyimli',      'sut': '4.2.13.3.2.A.2'},
    'YOLAK11': {'ad': 'Kronik HCV Çocuk Naive',            'sut': '4.2.13.3.2.B'},
    'YOLAK12': {'ad': 'Kronik HCV Çocuk Deneyimli',        'sut': '4.2.13.3.2.B.1'},
}


def _hep_dispatcher_sinyalleri(etkin_tip: str, metin_lower: str,
                                  teshis_metin: str, gecmis_icd: List[str],
                                  yas: Optional[int],
                                  ilac_sonuc: Dict) -> Dict:
    """Dispatcher kararını üreten tüm sinyalleri tek dict'te topla.

    Hem _hep_yolak_dispatch hem _hep_eleme_nedeni tarafından kullanılır
    (tek kaynak — kopyalama önlenir)."""
    teshis_upper = teshis_metin.upper() if teshis_metin else ''
    akut_b_icd, _ = hep_icd_var(teshis_upper, gecmis_icd, ICD_AKUT_B)
    akut_c_icd, _ = hep_icd_var(teshis_upper, gecmis_icd, ICD_AKUT_C)
    delta_icd, _ = hep_icd_var(teshis_upper, gecmis_icd, ('B17.0', 'B18.0'))
    onceki_hcv_durum, _, _ = hep_onceki_hcv_tedavi_var_mi(
        metin_lower, ilac_sonuc)
    return {
        'etkin_tip': etkin_tip,
        'is_hbv_oral': etkin_tip == 'HBV_ORAL',
        'is_hcv_daa': etkin_tip == 'HCV_DAA',
        'is_peg_ifn': etkin_tip == 'PEG_IFN',
        'is_ifn': etkin_tip == 'IFN',
        'is_rib': etkin_tip == 'RIBAVIRIN',
        'akut_b': bool(akut_b_icd) or bool(
            re.search(r'akut\s*hepatit\s*b', metin_lower)),
        'akut_c': bool(akut_c_icd) or bool(
            re.search(r'akut\s*hepatit\s*c', metin_lower)),
        'delta': bool(delta_icd) or (
            bool(re.search(
                r'(?:delta\s*(?:\+|pozitif|\(\+\))'
                r'|hdv\s*(?:\+|pozitif|\(\+\))'
                r'|anti[\s\-]?hdv\s*(?:\+|pozitif|\(\+\)))',
                metin_lower))
            or (bool(re.search(r'(?:delta|hdv|anti[\s\-]?hdv)', metin_lower))
                and not bool(re.search(
                    r'(?:delta\s*ajans[ıi]z|delta\s*yok|delta\s*negat'
                    r'|hdv\s*negat|hdv\s*\(-\)'
                    r'|anti[\s\-]?hdv\s*(?:negat|\(-\))'
                    r'|delta\s*\(-\))',
                    metin_lower)))),
        'transplant': bool(re.search(
            r'(?:karaciğer\s*nakl|transplant|liver\s*transplant)',
            metin_lower)),
        'imsup': bool(re.search(
            r'(?:immünsupresif|kemoterapi|sitotoks|monoklonal|'
            r'rituximab|tnf\s*inh|biyolojik\s*ajan)', metin_lower)),
        'siroz': bool(re.search(
            r'(?:karaciğer\s*siroz|\bsiroz\b)', metin_lower)),
        'is_cocuk': yas is not None and yas < 18,
        'is_eriskin': yas is not None and yas >= 18,
        'onceki_hcv_durum': onceki_hcv_durum,
    }


def _hep_eleme_nedeni(yolak_kod: str, sinyaller: Dict, aktif_kod: str) -> str:
    """Bir yolağın neden seçilmediğinin kısa kullanıcı dostu açıklaması."""
    s = sinyaller
    is_hbv = s['is_hbv_oral'] or s['is_peg_ifn']
    is_hcv = s['is_hcv_daa'] or (s['is_ifn'] and not s['akut_c']) or s['is_rib']

    # HBV grup yolakları (Y1-Y5, Y7) için ilaç şartı
    if yolak_kod in ('YOLAK1', 'YOLAK2', 'YOLAK3', 'YOLAK4', 'YOLAK5'):
        if not is_hbv:
            return f"Reçete HBV ilacı değil (etkin tip: {s['etkin_tip']})"
    if yolak_kod == 'YOLAK6':
        if not s['is_hbv_oral']:
            return f"Reçete HBV oral değil (etkin tip: {s['etkin_tip']})"
        if not s['akut_b']:
            return 'Raporda/teşhiste "akut hepatit B" ibaresi/ICD yok'
    if yolak_kod == 'YOLAK7':
        if not (s['is_peg_ifn'] or s['is_hbv_oral']):
            return f"Reçete PEG-IFN/HBV oral değil (etkin tip: {s['etkin_tip']})"
        if not s['delta']:
            return 'Raporda Delta/HDV/Anti-HDV ibaresi/ICD yok'
    if yolak_kod == 'YOLAK8':
        if not s['is_peg_ifn']:
            return f"Reçete PEG-IFN değil (etkin tip: {s['etkin_tip']})"
        if not s['akut_c']:
            return 'Raporda/teşhiste "akut hepatit C" ibaresi/ICD yok'

    # HCV grup yolakları
    if yolak_kod in ('YOLAK9', 'YOLAK10', 'YOLAK11', 'YOLAK12'):
        if not is_hcv:
            return f"Reçete HCV ilacı değil (etkin tip: {s['etkin_tip']})"
        if yolak_kod in ('YOLAK9', 'YOLAK10') and not s['is_eriskin']:
            return 'Hasta çocuk (yaş < 18) — erişkin HCV yolağı dışında'
        if yolak_kod in ('YOLAK11', 'YOLAK12') and not s['is_cocuk']:
            return 'Hasta erişkin — çocuk HCV yolağı dışında'
        if yolak_kod in ('YOLAK10', 'YOLAK12'):
            if s['onceki_hcv_durum'] != SartDurumu.VAR:
                return 'Önceki HCV tedavi kanıtı yok — naive yolağı geçerli'
        if yolak_kod in ('YOLAK9', 'YOLAK11'):
            if s['onceki_hcv_durum'] == SartDurumu.VAR:
                return 'Önceki HCV tedavi kanıtı var — deneyimli yolağı geçerli'

    # Yol-içi dispatcher sıra eleme (Y1 default — Y2-Y5 öncelik aldı?)
    if yolak_kod == 'YOLAK1' and is_hbv:
        if s['transplant']: return 'Y5 transplant öncelik aldı'
        if s['imsup']:      return 'Y4 immünsüpresif öncelik aldı'
        if s['siroz']:      return 'Y3 siroz öncelik aldı'
        if s['is_cocuk']:   return 'Y2 çocuk öncelik aldı'
    if yolak_kod == 'YOLAK2' and is_hbv:
        if not s['is_cocuk']:
            return 'Hasta çocuk değil (yaş ≥ 18 ∨ bilinmiyor)'
        if s['transplant']: return 'Y5 transplant öncelik aldı'
        if s['imsup']:      return 'Y4 immünsüpresif öncelik aldı'
        if s['siroz']:      return 'Y3 siroz öncelik aldı'
    if yolak_kod == 'YOLAK3' and is_hbv and not s['siroz']:
        return 'Raporda "siroz" ibaresi yok'
    if yolak_kod == 'YOLAK4' and is_hbv and not s['imsup']:
        return 'Raporda immünsüp/kemo/monoklonal/rituximab/biyolojik ibaresi yok'
    if yolak_kod == 'YOLAK5' and is_hbv and not s['transplant']:
        return 'Raporda "karaciğer nakli/transplant" ibaresi yok'

    return 'Bu yolak için endikasyon sinyali yok'


def _hep_diger_yolaklar(aktif_kod: str, sinyaller: Dict) -> List[Dict]:
    """Aktif olmayan 11 yolak için metadata listesi (GUI accordion için)."""
    if aktif_kod not in HEPATIT_YOLAK_METADATA:
        return []
    out = []
    for kod, meta in HEPATIT_YOLAK_METADATA.items():
        if kod == aktif_kod:
            continue
        out.append({
            'kod': kod,
            'ad': meta['ad'],
            'sut': meta['sut'],
            'eleme_nedeni': _hep_eleme_nedeni(kod, sinyaller, aktif_kod),
        })
    return out


def hepatit_yolak_hesapla(ilac_sonuc: Dict, yolak_kodu: str) -> KontrolRaporu:
    """Spesifik bir hepatit yolağını dispatcher bypass'le çalıştır (lazy).

    GUI accordion paneli pasif yolak başlığına tıklandığında çağırır:
    `_hep_yolak<N>_*` fonksiyonu manuel olarak çalıştırılır, ortak setup
    (metin birleşimi + ortak atomlar) aynı `kontrol_hepatit_atomik`'teki
    gibi yapılır.
    """
    if yolak_kodu not in HEPATIT_YOLAK_METADATA:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Bilinmeyen yolak: {yolak_kodu}',
            sut_kurali=SUT_KURALI_HEPATIT)

    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
    etkin_tip = _hep_etken_tip(ilac_adi, etkin)

    # Metin birleşimi (kontrol_hepatit_atomik ile aynı)
    parcalar: List[str] = []
    for k in ('mesaj_metni',):
        v = ilac_sonuc.get(k)
        if v:
            parcalar.append(str(v))
    for k in ('rapor_aciklamalari', 'recete_aciklamalari', '_recete_aciklamalari'):
        v = ilac_sonuc.get(k, [])
        if v:
            parcalar.extend([str(x) for x in v])
    tani_bilgileri = ilac_sonuc.get('rapor_tani_bilgileri', []) or []
    for tani in tani_bilgileri:
        if isinstance(tani, dict):
            kod = tani.get('sut_kodu', '')
            if kod:
                parcalar.append(kod)
            for icd in tani.get('icd_kodlari', []):
                ad = icd.get('adi', '') if isinstance(icd, dict) else ''
                if ad:
                    parcalar.append(ad)
    birlesik = ' '.join(parcalar)
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', []) or []
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''
    metin_lower = _tr_lower(birlesik + ' ' + teshis_metin)
    gecmis_icd = (ilac_sonuc.get('diger_raporlar_icd_tum_zamanlar')
                  or ilac_sonuc.get('diger_raporlar_icd') or [])
    yas = hep_parse_yas(ilac_sonuc, birlesik)

    sartlar: List[SartSonuc] = []
    detaylar: Dict = {
        'ilac_adi': ilac_adi, 'etkin_madde': etkin, 'rapor_kodu': rapor_kodu,
        'etkin_tip': etkin_tip, 'yolak': yolak_kodu,
        'dispatcher_gerekce': 'manuel yolak hesaplama (accordion lazy)',
        'hasta_yasi': yas, 'manuel_yolak': True,
    }

    # Ortak atomlar (aktif dispatcher mantığı ile aynı)
    sartlar.append(hep_atom_uzman_rapor(metin_lower, rapor_kodu, ilac_sonuc))
    if yolak_kodu in ('YOLAK8', 'YOLAK9', 'YOLAK10', 'YOLAK11', 'YOLAK12'):
        sartlar.append(hep_atom_recete_yetkisi_hcv(ilac_sonuc, metin_lower))
    else:
        aile_hek_ok = yolak_kodu in ('YOLAK1', 'YOLAK2', 'YOLAK3',
                                       'YOLAK4', 'YOLAK5', 'YOLAK7')
        sartlar.append(hep_atom_recete_yetkisi(
            ilac_sonuc, metin_lower,
            aile_hekimi_yetkili=aile_hek_ok,
            rapor_kodu=rapor_kodu))

    rejim = ''
    if yolak_kodu in ('YOLAK9', 'YOLAK10', 'YOLAK11', 'YOLAK12'):
        diger_ilaclar = ilac_sonuc.get('recete_ilaclari') or []
        diger_ad_upper = ' '.join([
            (str(i.get('ad', '')) if isinstance(i, dict) else str(i)).upper()
            for i in diger_ilaclar])
        rejim = _hep_hcv_rejim_tespit(ilac_adi, etkin, diger_ad_upper)
        detaylar['hcv_rejim'] = rejim

    # Yolak fonksiyonunu çağır (dispatcher bypass)
    yolak_fn_map = {
        'YOLAK1':  lambda: _hep_yolak1_eriskin_b(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas,
            etkin_tip, ilac_sonuc, sartlar, detaylar),
        'YOLAK2':  lambda: _hep_yolak2_cocuk_b(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas,
            etkin_tip, ilac_sonuc, sartlar, detaylar),
        'YOLAK3':  lambda: _hep_yolak3_b_siroz(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu,
            ilac_sonuc, sartlar, detaylar),
        'YOLAK4':  lambda: _hep_yolak4_b_immunsup(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu,
            ilac_sonuc, sartlar, detaylar),
        'YOLAK5':  lambda: _hep_yolak5_b_transplant(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu,
            ilac_sonuc, sartlar, detaylar),
        'YOLAK6':  lambda: _hep_yolak6_akut_b(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, etkin_tip,
            ilac_sonuc, sartlar, detaylar),
        'YOLAK7':  lambda: _hep_yolak7_kronik_d(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, etkin_tip,
            ilac_sonuc, sartlar, detaylar),
        'YOLAK8':  lambda: _hep_yolak8_akut_c(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, etkin_tip,
            ilac_sonuc, sartlar, detaylar),
        'YOLAK9':  lambda: _hep_yolak9_kronik_c_eriskin_naive(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas, rejim,
            ilac_sonuc, sartlar, detaylar),
        'YOLAK10': lambda: _hep_yolak10_kronik_c_eriskin_exp(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas, rejim,
            ilac_sonuc, sartlar, detaylar),
        'YOLAK11': lambda: _hep_yolak11_kronik_c_cocuk_naive(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas, rejim,
            ilac_sonuc, sartlar, detaylar),
        'YOLAK12': lambda: _hep_yolak12_kronik_c_cocuk_exp(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas, rejim,
            ilac_sonuc, sartlar, detaylar),
    }
    return yolak_fn_map[yolak_kodu]()


def _hep_yolak_dispatch(ilac_adi: str, etkin: str, etkin_tip: str,
                         metin_lower: str, teshis_metin: str,
                         gecmis_icd: List[str], rapor_kodu: str,
                         yas: Optional[int],
                         ilac_sonuc: Dict) -> Tuple[str, str]:
    """12 yolaktan birini seç.

    Returns: (yolak_kodu, gerekce)
        yolak_kodu: 'YOLAK1'..'YOLAK12' | 'BELIRSIZ'
    """
    teshis_upper = teshis_metin.upper() if teshis_metin else ''

    # 1. Sinyal — Reçete ilaç tipi
    is_hcv_daa = (etkin_tip == 'HCV_DAA')
    is_hbv_oral = (etkin_tip == 'HBV_ORAL')
    is_peg_ifn = (etkin_tip == 'PEG_IFN')
    is_ifn = (etkin_tip == 'IFN')

    # 2. Endikasyon sinyalleri
    akut_b_icd, _ = hep_icd_var(teshis_upper, gecmis_icd, ICD_AKUT_B)
    akut_b_metin = bool(re.search(r'akut\s*hepatit\s*b', metin_lower))
    akut_c_icd, _ = hep_icd_var(teshis_upper, gecmis_icd, ICD_AKUT_C)
    akut_c_metin = bool(re.search(r'akut\s*hepatit\s*c', metin_lower))
    delta_icd, _ = hep_icd_var(teshis_upper, gecmis_icd, ('B17.0', 'B18.0'))
    # Delta metin parser — sadece pozitif ibareler veya negatif olmayan
    # delta lafzı True döner. B18.1 ICD açıklaması "DELTA AJANSIZ" (delta
    # YOK) ile yanlış pozitifi önler (İSKAN ERDOĞMUŞ pilot bug 2026-05-25).
    _delta_negatif = bool(re.search(
        r'(?:delta\s*ajans[ıi]z|delta\s*yok|delta\s*negat'
        r'|hdv\s*negat|hdv\s*\(-\)'
        r'|anti[\s\-]?hdv\s*(?:negat|\(-\))'
        r'|delta\s*\(-\))',
        metin_lower))
    _delta_pozitif = bool(re.search(
        r'(?:delta\s*(?:\+|pozitif|\(\+\))'
        r'|hdv\s*(?:\+|pozitif|\(\+\))'
        r'|anti[\s\-]?hdv\s*(?:\+|pozitif|\(\+\)))',
        metin_lower))
    _delta_general = bool(re.search(
        r'(?:delta|hdv|anti[\s\-]?hdv)', metin_lower))
    delta_metin = _delta_pozitif or (_delta_general and not _delta_negatif)
    transplant = bool(re.search(r'(?:karaciğer\s*nakl|transplant|liver\s*transplant)',
                                 metin_lower))
    siroz = bool(re.search(r'(?:karaciğer\s*siroz|\bsiroz\b)', metin_lower))
    imsup = bool(re.search(r'(?:immünsupresif|kemoterapi|sitotoks|monoklonal|'
                            r'rituximab|tnf\s*inh|biyolojik\s*ajan)', metin_lower))

    is_cocuk = (yas is not None and yas < 18)

    # Karar mantığı (öncelik sırası):
    # - Akut B → Yolak 6 (akut B + HBV oral)
    if (akut_b_icd or akut_b_metin) and is_hbv_oral:
        return ('YOLAK6', 'Akut B ICD/metin + HBV oral antiviral')

    # - Akut C → Yolak 8 (akut C + peg-IFN)
    if (akut_c_icd or akut_c_metin) and is_peg_ifn:
        return ('YOLAK8', 'Akut C ICD/metin + pegile IFN')

    # - Delta (HDV) → Yolak 7
    if delta_icd or delta_metin:
        if is_peg_ifn or is_hbv_oral:
            return ('YOLAK7', 'Delta/HDV + (peg-IFN ∨ HBV oral)')

    # - HBV oral (kronik B varyantları)
    if is_hbv_oral or is_peg_ifn:
        if transplant:
            return ('YOLAK5', 'Transplant ibaresi + HBV ilacı')
        if imsup:
            return ('YOLAK4', 'İmmünsüpresif ibaresi + HBV ilacı')
        if siroz:
            return ('YOLAK3', 'Siroz ibaresi + HBV ilacı')
        if is_cocuk:
            return ('YOLAK2', 'Çocuk yaş + HBV ilacı')
        return ('YOLAK1', 'Erişkin + kronik HBV (varsayılan)')

    # - HCV DAA / IFN+RBV (kronik C) / Ribavirin (kombi şartı Y11/Y10'da)
    is_rib = (etkin_tip == 'RIBAVIRIN')
    if is_hcv_daa or (is_ifn and not akut_c_icd) or is_rib:
        # Önceki tedavi geçmişi: deneyimli mi naive mi?
        durum, _neden, _detay = hep_onceki_hcv_tedavi_var_mi(
            metin_lower, ilac_sonuc)
        if is_cocuk:
            if durum == SartDurumu.VAR:
                return ('YOLAK12', 'Çocuk + deneyimli HCV')
            return ('YOLAK11', 'Çocuk + naive HCV (varsayılan)')
        # Erişkin
        if durum == SartDurumu.VAR:
            return ('YOLAK10', 'Erişkin + deneyimli HCV')
        return ('YOLAK9', 'Erişkin + naive HCV (varsayılan)')

    return ('BELIRSIZ', f'İlaç tipi tanınmadı ({etkin_tip})')


# ═════════════════════════════════════════════════════════════════════════
# 22. TOP-LEVEL ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════

def kontrol_hepatit_atomik(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.13 Hepatit — 12 yolak atomik kontrol (üst dispatcher).

    Bu fonksiyon `sut_kontrolleri.kontrol_hepatit` placeholder'ının yerine
    geçer; atomik şema disiplini + SartSonuc gruplandırma + ÜST-VEYA
    aggregator + sayısal parser'lar + hasta geçmişi sorgusu içerir.
    """
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin = (ilac_sonuc.get('etkin_madde') or '').upper()
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()

    etkin_tip = _hep_etken_tip(ilac_adi, etkin)
    if etkin_tip == 'NONE':
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Hepatit (HBV/HCV/HDV) ilacı değil',
            sut_kurali=SUT_KURALI_HEPATIT)

    # Birleşik metin (mesaj + rapor açıklamaları + reçete açıklamaları + tanı)
    parcalar: List[str] = []
    for k in ('mesaj_metni',):
        v = ilac_sonuc.get(k)
        if v:
            parcalar.append(str(v))
    for k in ('rapor_aciklamalari', 'recete_aciklamalari', '_recete_aciklamalari'):
        v = ilac_sonuc.get(k, [])
        if v:
            parcalar.extend([str(x) for x in v])
    tani_bilgileri = ilac_sonuc.get('rapor_tani_bilgileri', []) or []
    for tani in tani_bilgileri:
        if isinstance(tani, dict):
            kod = tani.get('sut_kodu', '')
            if kod:
                parcalar.append(kod)
            for icd in tani.get('icd_kodlari', []):
                ad = icd.get('adi', '') if isinstance(icd, dict) else ''
                if ad:
                    parcalar.append(ad)
    birlesik = ' '.join(parcalar)
    recete_teshisleri = ilac_sonuc.get('recete_teshisleri', []) or []
    teshis_metin = ' '.join(recete_teshisleri).upper() if recete_teshisleri else ''
    metin_lower = _tr_lower(birlesik + ' ' + teshis_metin)

    # Geçmiş ICD'ler
    gecmis_icd = (ilac_sonuc.get('diger_raporlar_icd_tum_zamanlar')
                  or ilac_sonuc.get('diger_raporlar_icd') or [])
    yas = hep_parse_yas(ilac_sonuc, birlesik)

    # Boş veri kontrolü
    if not metin_lower.strip() and not rapor_kodu:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj='Hepatit ilacı RAPORSUZ — uzman raporu zorunlu (SUT 4.2.13)',
            sut_kurali=SUT_KURALI_HEPATIT,
            uyari='Gastroenteroloji/Enfeksiyon uzman raporu gerekli',
            aranan_ibare='Uzman raporu (zorunlu)',
            sartlar=[SartSonuc(
                'Rapor/mesaj metni + rapor kodu',
                SartDurumu.YOK,
                'Metin boş ve rapor kodu yok',
                'rapor_metni/rapor_kodu',
                grup='(R) Uzman raporu')])

    # Dispatcher: yolağı seç
    yolak_kodu, dispatcher_gerekce = _hep_yolak_dispatch(
        ilac_adi, etkin, etkin_tip, metin_lower, teshis_metin,
        gecmis_icd, rapor_kodu, yas, ilac_sonuc)

    sartlar: List[SartSonuc] = []
    detaylar: Dict = {
        'ilac_adi': ilac_adi, 'etkin_madde': etkin, 'rapor_kodu': rapor_kodu,
        'etkin_tip': etkin_tip, 'yolak': yolak_kodu,
        'dispatcher_gerekce': dispatcher_gerekce,
        'hasta_yasi': yas,
    }

    # ORTAK ATOMLAR (her yolakta)
    sartlar.append(hep_atom_uzman_rapor(metin_lower, rapor_kodu, ilac_sonuc))
    # HCV yolaklarında ek reçete yetkisi atomu
    if yolak_kodu in ('YOLAK8', 'YOLAK9', 'YOLAK10', 'YOLAK11', 'YOLAK12'):
        sartlar.append(hep_atom_recete_yetkisi_hcv(ilac_sonuc, metin_lower))
    else:
        # SUT 4.1.1/8: 4.2.13.1 (Y1/Y2/Y3/Y4/Y5) ve 4.2.13.2 (Y7) için aile
        # hekimi raporlu reçete yazabilir. Y6 (Akut B 4.2.13(3)) HARİÇ.
        aile_hek_ok = yolak_kodu in ('YOLAK1', 'YOLAK2', 'YOLAK3',
                                       'YOLAK4', 'YOLAK5', 'YOLAK7')
        sartlar.append(hep_atom_recete_yetkisi(
            ilac_sonuc, metin_lower,
            aile_hekimi_yetkili=aile_hek_ok,
            rapor_kodu=rapor_kodu))

    # Yolağa göre dispatcher
    if yolak_kodu == 'BELIRSIZ':
        sartlar.append(SartSonuc(
            'Dispatcher: yolak belirlenemedi',
            SartDurumu.KONTROL_EDILEMEDI,
            dispatcher_gerekce,
            'dispatcher', grup='(D) Dispatcher', sartli_atom=True))
        return _hep_genel_sonuc(
            sartlar, detaylar, SUT_KURALI_HEPATIT,
            yolak_etiketi='[Belirsiz Yolak]')

    # HCV yolakları için rejim tespit (Yolak 8 hariç, çünkü o sadece PEG_IFN)
    rejim = ''
    if yolak_kodu in ('YOLAK9', 'YOLAK10', 'YOLAK11', 'YOLAK12'):
        diger_ilaclar = ilac_sonuc.get('recete_ilaclari') or []
        diger_ad_upper = ' '.join([
            (str(i.get('ad', '')) if isinstance(i, dict) else str(i)).upper()
            for i in diger_ilaclar])
        rejim = _hep_hcv_rejim_tespit(ilac_adi, etkin, diger_ad_upper)
        detaylar['hcv_rejim'] = rejim

    # Yolak fonksiyonunu çağır
    rapor: Optional[KontrolRaporu] = None
    if yolak_kodu == 'YOLAK1':
        rapor = _hep_yolak1_eriskin_b(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas,
            etkin_tip, ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK2':
        rapor = _hep_yolak2_cocuk_b(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas,
            etkin_tip, ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK3':
        rapor = _hep_yolak3_b_siroz(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu,
            ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK4':
        rapor = _hep_yolak4_b_immunsup(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu,
            ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK5':
        rapor = _hep_yolak5_b_transplant(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu,
            ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK6':
        rapor = _hep_yolak6_akut_b(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, etkin_tip,
            ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK7':
        rapor = _hep_yolak7_kronik_d(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, etkin_tip,
            ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK8':
        rapor = _hep_yolak8_akut_c(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, etkin_tip,
            ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK9':
        rapor = _hep_yolak9_kronik_c_eriskin_naive(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas, rejim,
            ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK10':
        rapor = _hep_yolak10_kronik_c_eriskin_exp(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas, rejim,
            ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK11':
        rapor = _hep_yolak11_kronik_c_cocuk_naive(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas, rejim,
            ilac_sonuc, sartlar, detaylar)
    elif yolak_kodu == 'YOLAK12':
        rapor = _hep_yolak12_kronik_c_cocuk_exp(
            metin_lower, teshis_metin, gecmis_icd, rapor_kodu, yas, rejim,
            ilac_sonuc, sartlar, detaylar)
    else:
        # Buraya gelmemeli
        rapor = _hep_genel_sonuc(
            sartlar, detaylar, SUT_KURALI_HEPATIT,
            yolak_etiketi=f'[Tanımsız yolak: {yolak_kodu}]')

    # Diğer yolaklar metadata (GUI accordion paneli için)
    try:
        sinyaller = _hep_dispatcher_sinyalleri(
            etkin_tip, metin_lower, teshis_metin, gecmis_icd, yas, ilac_sonuc)
        if rapor.detaylar is None:
            rapor.detaylar = {}
        rapor.detaylar['diger_yolaklar'] = _hep_diger_yolaklar(
            yolak_kodu, sinyaller)
        rapor.detaylar['aktif_yolak_meta'] = HEPATIT_YOLAK_METADATA.get(
            yolak_kodu, {'ad': yolak_kodu, 'sut': '?'})
        rapor.detaylar['kontrol_modulu'] = 'hepatit'
    except Exception:
        pass
    return rapor


# Public API
__all__ = [
    'kontrol_hepatit_atomik',
    'hepatit_yolak_hesapla',
    'HEPATIT_YOLAK_METADATA',
    'SUT_KURALI_HEPATIT',
    'HBV_ORAL_ETKEN', 'HCV_DAA_ETKEN', 'PEG_IFN_ETKEN', 'RIBAVIRIN_ETKEN',
    # Parsers (test için)
    'hep_parse_hbv_dna', 'hep_parse_hcv_rna', 'hep_parse_hai',
    'hep_parse_fibrozis', 'hep_parse_fib4', 'hep_parse_apri',
    'hep_parse_alt_ust_sinir_orani', 'hep_parse_child_pugh',
    'hep_parse_kompanse_dekompanse', 'hep_parse_genotip',
    'hep_parse_hbeag', 'hep_parse_hbsag', 'hep_parse_anti_hdv',
    'hep_parse_anti_hbc', 'hep_parse_anti_hbs',
    'hep_parse_inr', 'hep_parse_pt_uzun', 'hep_parse_trombosit',
    'hep_parse_sarilik_sure', 'hep_parse_yas',
    # Atom + helper
    'hep_atom_uzman_rapor', 'hep_atom_recete_yetkisi',
    'hep_atom_recete_yetkisi_hcv', 'hep_atom_rapor_2_3_basamak',
    'hep_icd_var', 'hep_onceki_hcv_tedavi_var_mi',
]
