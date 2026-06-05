# -*- coding: utf-8 -*-
"""SUT 4.2.1.C-2 … C-14 — Biyolojik ajanlar / küçük moleküller (anti-TNF dışı).

Kapsam (C-1 anti-TNF L04AB* AYRI modüldedir: ``anti_tnf_4_2_1_c1.py``):

  C-2  Rituksimab            L01FA01   MABTHERA / TRUXIMA / RIXATHON
  C-3  Abatasept             L04AA24   ORENCIA
  C-4  Ustekinumab           L04AC05   STELARA
  C-5  Tosilizumab           L04AC07   ACTEMRA
  C-6  Tofa/Upa/Bari/Abro    L04AF*    XELJANZ / RINVOQ / OLUMIANT / CIBINQO
  C-7  Kanakinumab, Anakinra L04AC08/03 ILARIS / KINERET
  C-8  Vedolizumab           L04AA33   ENTYVIO
  C-9  Sekukinumab           L04AC10   COSENTYX
  C-10 İksekizumab           L04AC13   TALTZ
  C-11 Guselkumab            L04AC16   TREMFYA
  C-12 Risankizumab          L04AC18   SKYRIZI
  C-13 Apremilast            L04AA32   OTEZLA
  C-14 Bimekizumab           L04AC21   BIMZELX

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:4214-4710`` (+ genel ilkeler
4065-4082). mevzuat.gov.tr MevzuatNo=17229. Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md``
+ CLAUDE.md ``ATOMİK DEVRE ŞEMASI``.

═══════════════════════════════════════════════════════════════════════════
ARKETİP TASARIMI (arketip arketip implementasyon — kullanıcı onayı 2026-06-05)
TÜMÜ TAMAM (A–H), 34/34 akıl testi geçiyor.
═══════════════════════════════════════════════════════════════════════════
  A  Plak Psöriazis / PASI 75 / Dermatoloji  → C-4(1) C-9(2) C-10(1) C-11
     C-12 C-13(2) C-14(1)
  B  RA / DAS28 / Romatoloji                  → C-2(1) C-3(1) C-5(1) C-6(1,2)
  C  PsA / PSARC                              → C-4(2) C-6(3) C-9(3) C-10(2) C-13(1)
  D  AS / BASDAİ                              → C-6(4,5) C-9(1)
  E  Crohn / Ülseratif kolit / CDAI          → C-4(3,4) C-6(6,7,9) C-8
  F  Juvenil / pediatrik / ACR pediatrik     → C-3(2) C-5(2,3) C-6(10) C-7(1)
  G  Otoinflamatuar (FMF/CAPS/TRAPS/Still/DHA)→ C-7(2-5) C-5(4) C-6(11)
  H  Özel (GPA/MPA, pemfigus, atopik derm.,  → C-2(2,3) C-6(8) C-9(4)
     hidradenit)

C-1 KARAR politikası burada da geçerli: yapısal atomlar (endikasyon/yaş/branş/
SK raporu/heyet) net YOK → UYGUN DEĞİL. Klinik şartlar (önceki tedavi/skor) →
parse-dene, sessiz → KE+şartlı (örtük kabul YASAK, CLAUDE.md §2.5). Süre/doz/
hafta gibi parse edilemeyen şartlar → (bilgi) grubu → matematiği bozmaz.

ARKETİP A KARARLARI (kullanıcı onayı 2026-06-05):
  1. PASI değeri raporda YOKSA → UYGUN DEĞİL (yapısal atom, sessiz=YOK).
  2. Heyette dermatoloji uzmanı → SK raporu atomundan AYRI atom.
  3. Reçete eden dermatoloji dışı branş → UYGUN DEĞİL (katı).

Ana entrypoint: ``biyolojik_kontrol_4_2_1_c(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower
# C-1 modülünden ortak yardımcı + atomları yeniden kullan (tek kaynak)
from recete_kontrol.anti_tnf_4_2_1_c1 import (
    _arama_metni, _iceriyor, _rapor_metni, _teshis_birlesik, _icd_var,
    _yas_oku, _lab_deger, _skor_atom, _akut_faz_veya_atom,
    atom_saglik_kurulu_raporu, atom_yas_op, atom_recete_brans,
    atom_heyet_brans, atom_ucuncu_basamak, _onceki_tedavi_atom, _genel_sonuc,
    DERMATOLOJI, ROMATOLOJI, KLINIK_IMMUN, FTR, IC_HAST, COCUK_HAST,
    GASTRO, GENEL_CERRAHI,
)

# C-1'de olmayan ek branş kümeleri (Arketip F/G/H)
NEFROLOJI = ['nefroloji']
COCUK_ROMATOLOJI = ['cocuk romatoloji', 'çocuk romatoloji', 'pediatrik romatoloji']
IMMUN_ALERJI = ['immunoloji', 'immünoloji', 'immunoloj', 'alerji', 'alerjik']

# Not: NEFROLOJI / çocuk romatoloji gibi ek branş kümeleri arketip F/G/H
# turunda yerel olarak tanımlanacak.

# ═══════════════════════════════════════════════════════════════════════
# ETKEN / TİCARİ İLAÇ KÜMELERİ (norm_tr_upper) + ATC
# ═══════════════════════════════════════════════════════════════════════
RITUKSIMAB: Set[str] = {'RITUKSIMAB', 'RITUXIMAB', 'MABTHERA', 'TRUXIMA',
                        'RIXATHON', 'RITEMVIA', 'BLITZIMA', 'RIABNI'}
ABATASEPT: Set[str] = {'ABATASEPT', 'ORENCIA'}
USTEKINUMAB: Set[str] = {'USTEKINUMAB', 'STELARA', 'WEZLANA', 'USTEKIMAB'}
TOSILIZUMAB: Set[str] = {'TOSILIZUMAB', 'TOCILIZUMAB', 'ACTEMRA', 'TOFIDENCE'}
TOFASITINIB: Set[str] = {'TOFASITINIB', 'TOFACITINIB', 'XELJANZ'}
UPADASITINIB: Set[str] = {'UPADASITINIB', 'UPADACITINIB', 'RINVOQ'}
BARISITINIB: Set[str] = {'BARISITINIB', 'BARICITINIB', 'OLUMIANT'}
ABROSITINIB: Set[str] = {'ABROSITINIB', 'ABROCITINIB', 'CIBINQO'}
KANAKINUMAB: Set[str] = {'KANAKINUMAB', 'ILARIS'}
ANAKINRA: Set[str] = {'ANAKINRA', 'KINERET'}
VEDOLIZUMAB: Set[str] = {'VEDOLIZUMAB', 'ENTYVIO'}
SEKUKINUMAB: Set[str] = {'SEKUKINUMAB', 'SECUKINUMAB', 'COSENTYX'}
IKSEKIZUMAB: Set[str] = {'IKSEKIZUMAB', 'IXEKIZUMAB', 'TALTZ'}
GUSELKUMAB: Set[str] = {'GUSELKUMAB', 'TREMFYA'}
RISANKIZUMAB: Set[str] = {'RISANKIZUMAB', 'RISANKIZUMAB', 'SKYRIZI'}
APREMILAST: Set[str] = {'APREMILAST', 'OTEZLA'}
BIMEKIZUMAB: Set[str] = {'BIMEKIZUMAB', 'BIMZELX'}

# Madde kodu → etken kümesi (üst dispatcher)
MADDE_ETKEN: List[Tuple[str, Set[str]]] = [
    ('C2', RITUKSIMAB), ('C3', ABATASEPT), ('C4', USTEKINUMAB),
    ('C5', TOSILIZUMAB),
    ('C6', TOFASITINIB | UPADASITINIB | BARISITINIB | ABROSITINIB),
    ('C7', KANAKINUMAB | ANAKINRA), ('C8', VEDOLIZUMAB),
    ('C9', SEKUKINUMAB), ('C10', IKSEKIZUMAB), ('C11', GUSELKUMAB),
    ('C12', RISANKIZUMAB), ('C13', APREMILAST), ('C14', BIMEKIZUMAB),
]

# Madde kodu → ATC (kesin eşleşme yedeği)
MADDE_ATC: Dict[str, Tuple[str, ...]] = {
    'C2': ('L01FA01',), 'C3': ('L04AA24',), 'C4': ('L04AC05',),
    'C5': ('L04AC07',), 'C6': ('L04AF01', 'L04AF02', 'L04AF03', 'L04AF08',
                               'L04AA29', 'L04AA37'),
    'C7': ('L04AC08', 'L04AC03'), 'C8': ('L04AA33',), 'C9': ('L04AC10',),
    'C10': ('L04AC13',), 'C11': ('L04AC16',), 'C12': ('L04AC18',),
    'C13': ('L04AA32',), 'C14': ('L04AC21',),
}

HEPSI: Set[str] = set().union(*[e for _, e in MADDE_ETKEN])

# ─── AKTİF kapsam (tüm maddeler — Arketip A–H) ──────────────────────────
AKTIF_MADDELER: Set[str] = {'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8',
                            'C9', 'C10', 'C11', 'C12', 'C13', 'C14'}

# Madde → kullanıcıya gösterilecek ad (GUI özet / mesaj)
MADDE_ADLARI: Dict[str, str] = {
    'C2': 'Rituksimab', 'C3': 'Abatasept', 'C4': 'Ustekinumab',
    'C5': 'Tosilizumab', 'C6': 'Tofa/Upa/Bari/Abrositinib',
    'C7': 'Kanakinumab/Anakinra', 'C8': 'Vedolizumab', 'C9': 'Sekukinumab',
    'C10': 'İksekizumab', 'C11': 'Guselkumab', 'C12': 'Risankizumab',
    'C13': 'Apremilast', 'C14': 'Bimekizumab',
}

# Endikasyon ICD setleri
ICD_PSO = ('L40',)
ICD_PSA = ('L40.5', 'M07')   # psöriyatik artrit — Arketip C (psöriazisten ayır)
ICD_RA = ('M05', 'M06')      # romatoid artrit (erişkin)
ICD_AS = ('M45', 'M46')      # ankilozan spondilit / aksiyel spondiloartrit
ICD_CROHN = ('K50',)
ICD_UK = ('K51',)
ICD_JIA = ('M08',)           # juvenil idiyopatik artrit
ICD_ATOPIK = ('L20',)        # atopik dermatit
ICD_GPA = ('M31.3', 'M31.7')  # granülomatöz polianjit / mikroskopik polianjit
ICD_PEMFIGUS = ('L10',)
ICD_HS = ('L73.2', 'L73')
ICD_FMF = ('E85.0', 'E85', 'M04.1')
ICD_DHA = ('M31.5', 'M31.6')  # dev hücreli arterit
ICD_STILL = ('M06.1',)


# ═══════════════════════════════════════════════════════════════════════
# Madde + endikasyon meta (psöriazis arketipi)
# ═══════════════════════════════════════════════════════════════════════
PSO_META: Dict[str, Dict] = {
    'C4':  {'ad': 'Ustekinumab',  'sut': '4.2.1.C-4 (1)',
            'rapor': '1 yıl', 'pasi_hf': '28. hafta',
            'tolere_kontr': True},
    'C9':  {'ad': 'Sekukinumab',  'sut': '4.2.1.C-9 (2)',
            'rapor': "6'şar ay", 'pasi_hf': '16 hafta',
            'tolere_kontr': True},
    'C10': {'ad': 'İksekizumab',  'sut': '4.2.1.C-10 (1)',
            'rapor': "başlangıç 4 ay → 6'şar ay", 'pasi_hf': '16 hafta',
            'tolere_kontr': True},
    'C11': {'ad': 'Guselkumab',   'sut': '4.2.1.C-11 (1)',
            'rapor': "başlangıç 4 ay → 6'şar ay", 'pasi_hf': '16 hafta',
            'tolere_kontr': True},
    'C12': {'ad': 'Risankizumab', 'sut': '4.2.1.C-12 (1)',
            'rapor': "başlangıç 4 ay → 6'şar ay", 'pasi_hf': '16 hafta',
            'tolere_kontr': True},
    'C13': {'ad': 'Apremilast',   'sut': '4.2.1.C-13 (2)',
            'rapor': '6 ay (günlük doz + süre belirtili)', 'pasi_hf': '—',
            'tolere_kontr': False},   # yalnız "yanıt vermeyen"
    'C14': {'ad': 'Bimekizumab',  'sut': '4.2.1.C-14 (1)',
            'rapor': "başlangıç 4 ay → 6'şar ay", 'pasi_hf': '16 hafta',
            'tolere_kontr': True},
}

# Arketip B (RA / DAS28 / Romatoloji)
RA_META: Dict[str, Dict] = {
    'C2': {'ad': 'Rituksimab',  'sut': '4.2.1.C-2 (1)', 'rapor': '6 ay',
           'mtx': True,  'ic_hast': False},
    'C3': {'ad': 'Abatasept',   'sut': '4.2.1.C-3 (1)', 'rapor': '3 ay',
           'mtx': True,  'ic_hast': False},
    'C5': {'ad': 'Tosilizumab', 'sut': '4.2.1.C-5 (1)', 'rapor': '3 ay',
           'mtx': True,  'ic_hast': False},
    'C6': {'ad': 'Tofa/Upa/Barisitinib', 'sut': '4.2.1.C-6 (1)(2)',
           'rapor': '3 ay → 6 ay', 'mtx': False, 'ic_hast': True},
}

# Arketip C (PsA / PSARC) — branş listeleri SUT lafzına göre madde-bazlı
RA_FTR = ROMATOLOJI + FTR
PSA_META: Dict[str, Dict] = {
    'C4':  {'ad': 'Ustekinumab', 'sut': '4.2.1.C-4 (2)', 'anti_tnf': True,
            'heyet': RA_FTR, 'recete': RA_FTR, 'recete_ad': 'romatoloji/FTR'},
    'C6':  {'ad': 'Tofa/Upadasitinib', 'sut': '4.2.1.C-6 (3)', 'anti_tnf': True,
            'heyet': ROMATOLOJI, 'recete': ROMATOLOJI, 'recete_ad': 'romatoloji'},
    'C9':  {'ad': 'Sekukinumab', 'sut': '4.2.1.C-9 (3)', 'anti_tnf': True,
            'heyet': RA_FTR, 'recete': RA_FTR, 'recete_ad': 'romatoloji/FTR'},
    'C10': {'ad': 'İksekizumab', 'sut': '4.2.1.C-10 (2)', 'anti_tnf': True,
            'heyet': RA_FTR, 'recete': RA_FTR, 'recete_ad': 'romatoloji/FTR'},
    'C13': {'ad': 'Apremilast', 'sut': '4.2.1.C-13 (1)', 'anti_tnf': False,
            'heyet': ROMATOLOJI + KLINIK_IMMUN + FTR,
            'recete': ROMATOLOJI + KLINIK_IMMUN + FTR + IC_HAST,
            'recete_ad': 'romatoloji/klinik immün/FTR/iç hast.'},
}

PSO_MADDELER: Set[str] = set(PSO_META)   # C4,C9,C10,C11,C12,C13,C14
RA_MADDELER: Set[str] = set(RA_META)     # C2,C3,C5,C6
PSA_MADDELER: Set[str] = set(PSA_META)   # C4,C6,C9,C10,C13

# Romatolojik ortak branş kümeleri
ROM_KI_FTR = ROMATOLOJI + KLINIK_IMMUN + FTR
GASTRO_CER = GASTRO + GENEL_CERRAHI

# Arketip D–H: ENDIK_META[endik][madde] = parametreler
ENDIK_META: Dict[str, Dict[str, Dict]] = {
    # ── Arketip D: AS / BASDAİ ──
    'AS': {
        'C6': {'ad': 'Tofa/Upadasitinib', 'sut': '4.2.1.C-6 (4)(5)',
               'basamak': 'anti_tnf', 'basdai': False, 'akut': False,
               'heyet': ROM_KI_FTR, 'recete': ROM_KI_FTR + IC_HAST,
               'recete_ad': 'romatoloji/klinik immün/FTR/iç hast.'},
        'C9': {'ad': 'Sekukinumab', 'sut': '4.2.1.C-9 (1)',
               'basamak': 'nsai', 'basdai': True, 'akut': True,
               'heyet': ROM_KI_FTR, 'recete': ROM_KI_FTR + IC_HAST,
               'recete_ad': 'romatoloji/klinik immün/FTR/iç hast.'},
    },
    # ── Arketip E: Crohn ──
    'CROHN': {
        'C4': {'ad': 'Ustekinumab', 'sut': '4.2.1.C-4 (3)'},
        'C6': {'ad': 'Upadasitinib', 'sut': '4.2.1.C-6 (6)'},
        'C8': {'ad': 'Vedolizumab', 'sut': '4.2.1.C-8 (1)'},
    },
    # ── Arketip E: Ülseratif kolit ──
    'UK': {
        'C4': {'ad': 'Ustekinumab', 'sut': '4.2.1.C-4 (4)'},
        'C6': {'ad': 'Tofa/Upadasitinib', 'sut': '4.2.1.C-6 (7)(9)'},
        'C8': {'ad': 'Vedolizumab', 'sut': '4.2.1.C-8 (2)'},
    },
    # ── Arketip F: Juvenil / pediatrik (ACR pediatrik) ──
    'JIA': {
        'C3': {'ad': 'Abatasept', 'sut': '4.2.1.C-3 (2)',
               'recete': COCUK_ROMATOLOJI + COCUK_HAST,
               'recete_ad': 'çocuk romatoloji/çocuk hast.'},
        'C5': {'ad': 'Tosilizumab', 'sut': '4.2.1.C-5 (2)(3)',
               'recete': COCUK_ROMATOLOJI + COCUK_HAST,
               'recete_ad': 'çocuk romatoloji/çocuk hast.'},
        'C6': {'ad': 'Tofacitinib', 'sut': '4.2.1.C-6 (10)',
               'recete': COCUK_ROMATOLOJI, 'recete_ad': 'çocuk romatoloji'},
        'C7': {'ad': 'Kanakinumab/Anakinra', 'sut': '4.2.1.C-7 (1)',
               'recete': COCUK_ROMATOLOJI, 'recete_ad': 'çocuk romatoloji'},
    },
    # ── Arketip G: Otoinflamatuar (FMF/CAPS/TRAPS/Still/DHA) — klinik=KE ──
    'OTOINF': {
        'C5': {'ad': 'Tosilizumab (DHA)', 'sut': '4.2.1.C-5 (4)',
               'heyet': ROMATOLOJI + KLINIK_IMMUN,
               'recete': ROMATOLOJI + KLINIK_IMMUN,
               'recete_ad': 'romatoloji/immünoloji'},
        'C6': {'ad': 'Upadasitinib (DHA)', 'sut': '4.2.1.C-6 (11)',
               'heyet': ROMATOLOJI + KLINIK_IMMUN,
               'recete': ROMATOLOJI + KLINIK_IMMUN,
               'recete_ad': 'romatoloji/immünoloji'},
        'C7': {'ad': 'Kanakinumab/Anakinra (FMF/CAPS/TRAPS/Still)',
               'sut': '4.2.1.C-7 (2)(3)(4)(5)',
               'heyet': ROMATOLOJI + NEFROLOJI,
               'recete': ROMATOLOJI + NEFROLOJI,
               'recete_ad': 'romatoloji (FMF amiloidoz: +nefroloji)'},
    },
    # ── Arketip H: Özel ──
    'GPA': {
        'C2': {'ad': 'Rituksimab (GPA/MPA)', 'sut': '4.2.1.C-2 (2)',
               'heyet': ROMATOLOJI + KLINIK_IMMUN + NEFROLOJI,
               'recete': ROMATOLOJI + KLINIK_IMMUN + NEFROLOJI,
               'recete_ad': 'romatoloji/klinik immün/nefroloji'},
    },
    'PEMFIGUS': {
        'C2': {'ad': 'Rituksimab (pemfigus vulgaris)', 'sut': '4.2.1.C-2 (3)',
               'heyet': DERMATOLOJI, 'recete': DERMATOLOJI,
               'recete_ad': 'dermatoloji'},
    },
    'ATOPIK': {
        'C6': {'ad': 'Upa/Bari/Abrositinib (atopik dermatit)',
               'sut': '4.2.1.C-6 (8)',
               'heyet': DERMATOLOJI + IMMUN_ALERJI,
               'recete': DERMATOLOJI + IMMUN_ALERJI,
               'recete_ad': 'dermatoloji/immünoloji/immünoloji-alerji'},
    },
    'HS': {
        'C9': {'ad': 'Sekukinumab (hidradenitis süpürativa)',
               'sut': '4.2.1.C-9 (4)', 'heyet': DERMATOLOJI,
               'recete': DERMATOLOJI, 'recete_ad': 'dermatoloji'},
    },
}

# Madde → desteklenen endikasyonlar (öncelik sırası; spesifik ICD önce)
MADDE_ENDIK_SIRA: Dict[str, List[str]] = {
    'C2': ['RA', 'GPA', 'PEMFIGUS'],
    'C3': ['RA', 'JIA'],
    'C4': ['PSA', 'PSO', 'CROHN', 'UK'],
    'C5': ['RA', 'JIA', 'OTOINF'],
    'C6': ['PSA', 'RA', 'AS', 'CROHN', 'UK', 'ATOPIK', 'JIA', 'OTOINF'],
    'C7': ['JIA', 'OTOINF'],
    'C8': ['CROHN', 'UK'],
    'C9': ['PSA', 'AS', 'HS', 'PSO'],
    'C10': ['PSA', 'PSO'],
    'C11': ['PSO'],
    'C12': ['PSO'],
    'C13': ['PSA', 'PSO'],
    'C14': ['PSO'],
}


def _madde_meta(madde: str) -> Dict:
    return PSO_META.get(madde) or RA_META.get(madde) or PSA_META.get(madde) or {}


def _endik_meta(madde: str, endik: str) -> Dict:
    if endik == 'PSO':
        return PSO_META.get(madde, {})
    if endik == 'RA':
        return RA_META.get(madde, {})
    if endik == 'PSA':
        return PSA_META.get(madde, {})
    return ENDIK_META.get(endik, {}).get(madde, {})


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════
def biyolojik_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """C-2…C-14 (anti-TNF dışı) biyolojik kapsamı mı? (yalnız AKTİF maddeler)."""
    return biyolojik_madde_belirle(ilac_sonuc) is not None


def biyolojik_madde_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """Etken/ATC → madde kodu ('C4'…). Yalnız AKTİF maddeler döner."""
    m = _arama_metni(ilac_sonuc)
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    for kod, etkenler in MADDE_ETKEN:
        if kod not in AKTIF_MADDELER:
            continue
        if _iceriyor(m, etkenler):
            return kod
        if atc and any(atc.startswith(a) for a in MADDE_ATC.get(kod, ())):
            return kod
    return None


def _endik_eslesir(ilac_sonuc: Dict, endik: str, madde: str) -> bool:
    """Reçete/rapor verisi verilen endikasyona (ICD ∨ metin) uyuyor mu?"""
    teshis = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if endik == 'PSA':
        return (_icd_var(teshis, ICD_PSA) or 'psoriyatik artrit' in metin
                or 'psoriatik artrit' in metin)
    if endik == 'PSO':
        if madde in {'C11', 'C12', 'C14'}:   # yalnız-psöriazis ilaçları
            return True
        return (_icd_var(teshis, ICD_PSO) or 'plak psoriazis' in metin
                or 'plak tip psoriazis' in metin or 'psoriazis vulgaris' in metin
                or 'psoriasis' in metin or 'sedef' in metin or 'psoriazis' in metin)
    if endik == 'RA':
        return _icd_var(teshis, ICD_RA) or 'romatoid artrit' in metin
    if endik == 'AS':
        return (_icd_var(teshis, ICD_AS) or 'ankilozan spondilit' in metin
                or 'spondiloartrit' in metin or 'spondilartrit' in metin)
    if endik == 'CROHN':
        return _icd_var(teshis, ICD_CROHN) or 'crohn' in metin
    if endik == 'UK':
        return (_icd_var(teshis, ICD_UK) or 'ulseratif kolit' in metin
                or 'ülseratif kolit' in metin)
    if endik == 'JIA':
        return (_icd_var(teshis, ICD_JIA) or 'juvenil' in metin
                or 'juvenil' in metin or 'juvenil idiyopatik' in metin)
    if endik == 'ATOPIK':
        return _icd_var(teshis, ICD_ATOPIK) or 'atopik dermatit' in metin
    if endik == 'GPA':
        return (_icd_var(teshis, ICD_GPA) or 'granulomatoz' in metin
                or 'granülomatöz' in metin or 'wegener' in metin
                or 'polianjit' in metin or 'polianjiitis' in metin)
    if endik == 'PEMFIGUS':
        return _icd_var(teshis, ICD_PEMFIGUS) or 'pemfigus' in metin
    if endik == 'HS':
        return (_icd_var(teshis, ICD_HS) or 'hidradenit' in metin
                or 'akne inversa' in metin)
    if endik == 'OTOINF':
        return (_icd_var(teshis, ICD_FMF + ICD_DHA + ICD_STILL)
                or 'ailevi akdeniz' in metin or 'fmf' in metin
                or 'kriyopirin' in metin or 'caps' in metin or 'traps' in metin
                or 'hids' in metin or 'mevalonat' in metin
                or 'dev hucreli arterit' in metin or 'dev hücreli arterit' in metin
                or 'still' in metin or 'periyodik ates' in metin)
    return False


def biyolojik_endikasyon_belirle(ilac_sonuc: Dict, madde: str) -> str:
    """Madde içi endikasyon yolağını belirle (öncelik sırasıyla); yoksa DIGER."""
    for endik in MADDE_ENDIK_SIRA.get(madde, []):
        if _endik_eslesir(ilac_sonuc, endik, madde):
            return endik
    return 'DIGER'


# ═══════════════════════════════════════════════════════════════════════
# ARKETİP A ATOMLARI (Psöriazis / PASI 75 / Dermatoloji)
# ═══════════════════════════════════════════════════════════════════════
def _atom_plak_psoriazis(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Orta/şiddetli plak psöriazis endikasyonu (L40 ∨ metin). Yapısal."""
    teshis = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if (_icd_var(teshis, ICD_PSO) or 'plak psoriazis' in metin
            or 'plak tip psoriazis' in metin or 'psoriazis vulgaris' in metin
            or 'psoriasis' in metin or 'sedef' in metin or 'psoriazis' in metin):
        return SartSonuc(ad='Orta/şiddetli plak psöriazis', durum=SartDurumu.VAR,
                         neden='Plak psöriazis endikasyonu (ICD L40 / rapor metni)',
                         kaynak='teshis+rapor', grup=grup)
    return SartSonuc(ad='Orta/şiddetli plak psöriazis', durum=SartDurumu.YOK,
                     neden='Plak psöriazis endikasyonu (L40 / metin) bulunamadı',
                     kaynak='teshis+rapor', grup=grup)


def _atom_pasi_deger(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """PASI değeri raporda belirtilmiş mi? (KARAR-1: yoksa YOK → UYGUN DEĞİL)."""
    metin = _rapor_metni(ilac_sonuc)
    val, _ = _lab_deger(metin, ['pasi'])
    if val is not None:
        return SartSonuc(ad=f'PASI değeri raporda (PASI {val:g})',
                         durum=SartDurumu.VAR,
                         neden='Rapor metninde PASI değeri bulundu',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='PASI değeri raporda', durum=SartDurumu.YOK,
                     neden='Raporda PASI değeri bulunamadı — SUT: raporda '
                           'belirtilmesi zorunlu (değer yoksa UYGUN DEĞİL)',
                     kaynak='rapor_metni', grup=grup)


def _atom_geleneksel_tedavi(ilac_sonuc: Dict, grup: str,
                            tolere_kontr: bool) -> SartSonuc:
    """Geleneksel sistemik tedavi (siklosporin∨MTX∨fototerapi/PUVA) yanıtsızlık
    VEYA (tolere_kontr ise) tolere edememe VEYA kontrendike. parse-dene → KE+şartlı."""
    ibareler = ['siklosporin', 'metotreksat', 'methotrexat', 'fototerapi',
                'puva', 'fotokemoterapi', 'geleneksel sistemik', 'sistemik tedavi',
                'yanit vermeyen', 'yanitsiz', 'cevapsiz']
    if tolere_kontr:
        ibareler += ['tolere edemeyen', 'tolere edememe', 'kontrendike',
                     'kontraendike']
    etiket = ('Geleneksel sistemik tedaviye yanıtsızlık'
              + (' ∨ tolere edememe ∨ kontrendike' if tolere_kontr else ''))
    return _onceki_tedavi_atom(ilac_sonuc, grup, etiket, ibareler)


def _atom_pasi75_bilgi(ilac_sonuc: Dict, grup: str, hafta: str) -> SartSonuc:
    """16/28 hafta sonunda PASI ≥%75 (devam şartı). BİLGİ — başlangıç/devam
    ayrımı tek reçeteden yapılamaz, matematiği bozmaz."""
    return SartSonuc(
        ad=f'{hafta} sonunda PASI ≥%75 iyileşme (devam şartı)',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Başlangıç/devam ayrımı + PASI75 yanıtı tek reçeteden '
              'doğrulanamaz — yeni raporda belirtilmeli (manuel)',
        kaynak='rapor_metni', grup=grup, sartli_atom=True)


def _biyolojik_genel_bilgi_atomlari(ilac_sonuc: Dict, rituksimab: bool = False
                                    ) -> List[SartSonuc]:
    """Genel ilkeler (1)/(3) → BİLGİ atomları (matematiği bozmaz)."""
    ara = '12 ay' if rituksimab else '6 ay'
    return [
        SartSonuc(ad=f'(1) Tedaviye ara → yeniden başlangıç ({ara})',
                  durum=SartDurumu.KONTROL_EDILEMEDI,
                  neden=f'{ara}+ ara verildiyse başlangıç kriterleri aranır — '
                        'ilaç geçmişi (EOS) manuel',
                  kaynak='ilac_gecmisi',
                  grup='(Genel) Tedaviye ara (bilgi)', sartli_atom=True),
        SartSonuc(ad='(3) İki tanı + iki farklı biyolojik birlikteliği',
                  durum=SartDurumu.KONTROL_EDILEMEDI,
                  neden='İki farklı tanı ile iki farklı biyolojik birlikte '
                        'kullanımı karşılanmaz — çapraz reçete/rapor manuel',
                  kaynak='diger_ilac',
                  grup='(Genel) İki biyolojik (bilgi)', sartli_atom=True),
    ]


# ═══════════════════════════════════════════════════════════════════════
# ARKETİP A YOLAK KONTROLÜ
# ═══════════════════════════════════════════════════════════════════════
def pso_kontrol(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    """Plak psöriazis / PASI 75 / dermatoloji ortak yolağı (C-4/9/10/11/12/13/14)."""
    meta = PSO_META[madde]
    p = meta['sut']
    s: List[SartSonuc] = []
    # A1 erişkin
    s.append(atom_yas_op(ilac_sonuc, f'{p} Erişkin (yaş ≥18)', '>=', 18,
                         'Erişkin (yaş ≥18)'))
    # A2 plak psöriazis endikasyonu
    s.append(_atom_plak_psoriazis(ilac_sonuc, f'{p} Plak psöriazis endikasyonu'))
    # B1 geleneksel sistemik tedavi yanıtsızlık (∨ tolere ∨ kontrendike)
    s.append(_atom_geleneksel_tedavi(
        ilac_sonuc, f'{p} Geleneksel sistemik tedavi yanıtsızlığı',
        meta['tolere_kontr']))
    # B2 PASI değeri raporda (KARAR-1: yoksa UYGUN DEĞİL)
    s.append(_atom_pasi_deger(ilac_sonuc, f'{p} PASI değeri raporda'))
    # C1 SK raporu
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu'))
    # C2 heyette dermatoloji (KARAR-2: ayrı atom)
    s.append(atom_heyet_brans(ilac_sonuc, f'{p} Heyette dermatoloji uzmanı',
                              DERMATOLOJI, 'Heyette dermatoloji uzmanı'))
    # D1 reçete eden dermatoloji (KARAR-3: katı)
    s.append(atom_recete_brans(ilac_sonuc, f'{p} Reçete eden dermatoloji uzmanı',
                               DERMATOLOJI, 'Dermatoloji uzmanı'))
    # C3 3. basamak — bilgi (parse zayıf)
    c3 = atom_ucuncu_basamak(ilac_sonuc, f'{p} 3. basamak resmi kurum (bilgi)')
    s.append(c3)
    # E1 PASI75 devam — bilgi
    if meta['pasi_hf'] != '—':
        s.append(_atom_pasi75_bilgi(ilac_sonuc, f'{p} PASI75 devam (bilgi)',
                                    meta['pasi_hf']))
    return s


# ═══════════════════════════════════════════════════════════════════════
# ARKETİP B ATOMLARI (RA / DAS28 / Romatoloji)
# ═══════════════════════════════════════════════════════════════════════
MTX_IBARELER = ['metotreksat', 'methotrexat', 'methotreksat', ' mtx',
                'emthexate', 'zexate', 'trixilem', 'methotrexate']


def _atom_ra_endikasyon(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Erişkin romatoid artrit endikasyonu (M05/M06 ∨ metin). Yapısal."""
    teshis = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if _icd_var(teshis, ICD_RA) or 'romatoid artrit' in metin:
        return SartSonuc(ad='Romatoid artrit endikasyonu', durum=SartDurumu.VAR,
                         neden='RA endikasyonu (ICD M05/M06 / rapor metni)',
                         kaynak='teshis+rapor', grup=grup)
    return SartSonuc(ad='Romatoid artrit endikasyonu', durum=SartDurumu.YOK,
                     neden='RA endikasyonu (M05/M06 / metin) bulunamadı',
                     kaynak='teshis+rapor', grup=grup)


def _atom_mtx_kombinasyon(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Methotrexat ile kombinasyon (reçete kalemi ∨ rapor). Sessiz → KE+şartlı
    (MTX ayrı reçetede olabilir — KARAR onayı 2026-06-05)."""
    metin = _rapor_metni(ilac_sonuc)   # diger_ilac_adlari da dahil
    if any(ib in metin for ib in MTX_IBARELER):
        return SartSonuc(ad='Methotrexat ile kombinasyon', durum=SartDurumu.VAR,
                         neden='Methotrexat reçete/rapor metninde bulundu',
                         kaynak='rapor+diger_ilac', grup=grup)
    return SartSonuc(ad='Methotrexat ile kombinasyon',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Methotrexat eş-zamanlı kullanımı doğrulanamadı '
                           '(ayrı reçetede olabilir) — manuel',
                     kaynak='rapor+diger_ilac', grup=grup, sartli_atom=True)


def _atom_basamak_ra(ilac_sonuc: Dict, grup: str, madde: str) -> SartSonuc:
    """Basamak tedavi: ≥3 DMARD (3'er ay) ∨ ≥1 anti-TNF yetersiz/intolerans.
    Rituksimab (C-2): + TNF başlanması uygun değil. parse-dene → KE+şartlı."""
    ibareler = ['dmard', 'hastalik modifiye', 'methotrexat', 'metotreksat',
                'leflunomid', 'sulfasalazin', 'anti-tnf', 'anti tnf',
                'tnf inhibit', 'tnf', 'intoleran']
    etiket = "≥3 DMARD (3'er ay) ∨ ≥1 anti-TNF yetersiz/intolerans"
    if madde == 'C2':
        ibareler += ['uygun olmayan', 'uygun gorulmeyen', 'uygun degil']
        etiket = ("≥1 anti-TNF'e rağmen DAS28>5,1 ∨ TNF uygun değil "
                  "∨ TNF intolerans")
    return _onceki_tedavi_atom(ilac_sonuc, grup, etiket, ibareler)


def ra_kontrol(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    """RA / DAS28 / romatoloji ortak yolağı (C-2/C-3/C-5/C-6)."""
    meta = RA_META[madde]
    p = meta['sut']
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, f'{p} Erişkin (yaş ≥18)', '>=', 18,
                         'Erişkin (yaş ≥18)'))
    s.append(_atom_ra_endikasyon(ilac_sonuc, f'{p} Romatoid artrit endikasyonu'))
    if meta['mtx']:
        s.append(_atom_mtx_kombinasyon(ilac_sonuc,
                                       f'{p} Methotrexat ile kombinasyon'))
    s.append(_atom_basamak_ra(ilac_sonuc, f'{p} Basamak tedavi', madde))
    s.append(_skor_atom(ilac_sonuc, f'{p} DAS28 > 5,1', 'DAS28',
                        ['das 28', 'das28', 'das-28'], '>', 5.1,
                        ['idame', 'devam', 'dusme', 'puan', 'yanit']))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(
        ilac_sonuc, f'{p} Heyette romatoloji/klinik immün/FTR',
        ROMATOLOJI + KLINIK_IMMUN + FTR,
        'Heyette romatoloji ∨ klinik immün ∨ FTR'))
    izinli = ROMATOLOJI + KLINIK_IMMUN + FTR + (IC_HAST if meta['ic_hast'] else [])
    s.append(atom_recete_brans(
        ilac_sonuc, f'{p} Reçete eden yetkili branş', izinli,
        'Romatoloji/klinik immün/FTR' + ('/iç hast.' if meta['ic_hast'] else '')))
    # bilgi: 3. basamak
    s.append(atom_ucuncu_basamak(ilac_sonuc, f'{p} 3. basamak resmi kurum (bilgi)'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# ARKETİP C ATOMLARI (PsA / PSARC)
# ═══════════════════════════════════════════════════════════════════════
def _atom_psa_endikasyon(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Aktif psöriyatik artrit endikasyonu (L40.5 / M07 ∨ metin). Yapısal."""
    teshis = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if (_icd_var(teshis, ICD_PSA) or 'psoriyatik artrit' in metin
            or 'psoriatik artrit' in metin):
        return SartSonuc(ad='Psöriyatik artrit endikasyonu', durum=SartDurumu.VAR,
                         neden='PsA endikasyonu (ICD L40.5/M07 / rapor metni)',
                         kaynak='teshis+rapor', grup=grup)
    return SartSonuc(ad='Psöriyatik artrit endikasyonu', durum=SartDurumu.YOK,
                     neden='PsA endikasyonu (L40.5/M07 / metin) bulunamadı',
                     kaynak='teshis+rapor', grup=grup)


def psa_kontrol(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    """PsA / PSARC ortak yolağı (C-4(2)/C-6(3)/C-9(3)/C-10(2)/C-13(1))."""
    meta = PSA_META[madde]
    p = meta['sut']
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, f'{p} Erişkin (yaş ≥18)', '>=', 18,
                         'Erişkin (yaş ≥18)'))
    s.append(_atom_psa_endikasyon(ilac_sonuc, f'{p} Psöriyatik artrit endikasyonu'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, f'{p} ≥3 DMARD (3\'er ay) uygun doz',
        "≥3 DMARD uygun dozunda en az 3'er ay",
        ['dmard', 'hastalik modifiye', 'methotrexat', 'metotreksat',
         'leflunomid', 'sulfasalazin']))
    if meta['anti_tnf']:
        s.append(_onceki_tedavi_atom(
            ilac_sonuc, f'{p} ≥1 anti-TNF 3 ay yetersiz',
            '≥1 anti-TNF ajanı 3 ay kullanıp yetersiz/intolerans',
            ['anti-tnf', 'anti tnf', 'tnf inhibit', 'tnf', 'intoleran']))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, f'{p} Aktif hastalık (≥3 hassas + ≥3 şiş eklem)',
        'Aktif (≥3 hassas + ≥3 şiş eklem, 1 ay arayla 2 muayene)',
        ['hassas eklem', 'sis eklem', 'şiş eklem', 'psarc', 'aktif psoriyatik',
         'aktif psoriatik']))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, f'{p} Heyette {meta["recete_ad"]}',
                              meta['heyet'], f'Heyette {meta["recete_ad"]}'))
    s.append(atom_recete_brans(ilac_sonuc, f'{p} Reçete eden {meta["recete_ad"]}',
                               meta['recete'], meta['recete_ad']))
    s.append(atom_ucuncu_basamak(ilac_sonuc, f'{p} 3. basamak resmi kurum (bilgi)'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# ORTAK YARDIMCI ATOMLAR (Arketip D–H)
# ═══════════════════════════════════════════════════════════════════════
def _atom_endik(ilac_sonuc: Dict, grup: str, endik: str, madde: str,
                etiket: str) -> SartSonuc:
    """Yapısal endikasyon atomu (ICD ∨ metin eşleşmesi)."""
    if _endik_eslesir(ilac_sonuc, endik, madde):
        return SartSonuc(ad=etiket, durum=SartDurumu.VAR,
                         neden='Endikasyon (ICD / rapor metni) doğrulandı',
                         kaynak='teshis+rapor', grup=grup)
    return SartSonuc(ad=etiket, durum=SartDurumu.YOK,
                     neden='Endikasyon (ICD / metin) bulunamadı',
                     kaynak='teshis+rapor', grup=grup)


def _ke_bilgi_atom(grup: str, etiket: str, neden: str) -> SartSonuc:
    """Parse edilemeyen klinik/süre şartı → KE + (bilgi) grubu."""
    return SartSonuc(ad=etiket, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=neden, kaynak='rapor_metni', grup=grup,
                     sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# ARKETİP D — AS / BASDAİ
# ═══════════════════════════════════════════════════════════════════════
def as_kontrol(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    meta = ENDIK_META['AS'][madde]
    p = meta['sut']
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, f'{p} Erişkin (yaş ≥18)', '>=', 18,
                         'Erişkin (yaş ≥18)'))
    s.append(_atom_endik(ilac_sonuc, f'{p} (Aksiyel) AS / spondiloartrit endikasyonu',
                         'AS', madde, '(Aksiyel) AS / spondiloartrit endikasyonu'))
    if meta['basamak'] == 'anti_tnf':
        s.append(_onceki_tedavi_atom(
            ilac_sonuc, f'{p} ≥1 anti-TNF yetersiz/intolerans',
            '≥1 anti-TNF ajanına yetersiz cevap ∨ intolerans',
            ['anti-tnf', 'anti tnf', 'tnf inhibit', 'tnf', 'intoleran',
             'yetersiz cevap']))
    else:  # nsai (C-9/1)
        s.append(_onceki_tedavi_atom(
            ilac_sonuc, f'{p} ≥3 NSAİİ (biri maks. indometazin) maks. doz',
            '≥3 NSAİİ (biri maks. indometazin) maks. dozda yetersiz',
            ['indometazin', 'nsai', 'nonsteroid', 'antiinflamatuar']))
    if meta['basdai']:
        s.append(_skor_atom(ilac_sonuc, f'{p} BASDAİ > 5', 'BASDAİ',
                            ['basdai', 'basda'], '>', 5,
                            ['idame', 'devam', 'birim', 'duzelme', 'yanit']))
    if meta['akut']:
        s.append(_akut_faz_veya_atom(
            ilac_sonuc, f'{p} ESH>28 ∨ CRP>ÜSN ∨ MR/sintigrafi (≥1)'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, f'{p} Heyette {meta["recete_ad"]}',
                              meta['heyet'], f'Heyette romatoloji/klinik immün/FTR'))
    s.append(atom_recete_brans(ilac_sonuc, f'{p} Reçete eden {meta["recete_ad"]}',
                               meta['recete'], meta['recete_ad']))
    s.append(atom_ucuncu_basamak(ilac_sonuc, f'{p} 3. basamak resmi kurum (bilgi)'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# ARKETİP E — Crohn / Ülseratif kolit (CDAI)
# ═══════════════════════════════════════════════════════════════════════
def ibd_kontrol(ilac_sonuc: Dict, madde: str, endik: str) -> List[SartSonuc]:
    meta = ENDIK_META[endik][madde]
    p = meta['sut']
    crohn = endik == 'CROHN'
    ad_endik = ('Fistülize/şiddetli/aktif luminal Crohn' if crohn
                else 'Şiddetli aktif ülseratif kolit')
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, f'{p} Yetişkin (yaş ≥18)', '>=', 18,
                         'Yetişkin (yaş ≥18)'))
    s.append(_atom_endik(ilac_sonuc, f'{p} {ad_endik} endikasyonu', endik, madde,
                         f'{ad_endik} endikasyonu'))
    if crohn:
        s.append(_onceki_tedavi_atom(
            ilac_sonuc, f'{p} ≥1 anti-TNF 3 ay yetersiz',
            '≥1 anti-TNF tedavisine rağmen hastalık kontrol edilemiyor',
            ['anti-tnf', 'anti tnf', 'tnf', 'kontrol edileme', 'yetersiz']))
    else:
        s.append(_onceki_tedavi_atom(
            ilac_sonuc, f'{p} ≥1 biyolojik/anti-TNF (∨ konvansiyonel) yetersiz',
            '≥1 biyolojik ajan/anti-TNF (∨ kortikosteroid+6MP/AZA) yetersiz',
            ['biyolojik', 'anti-tnf', 'anti tnf', 'tnf', 'kortikosteroid',
             '6-mp', 'azatiyopurin', 'kontrol edileme', 'yetersiz']))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(
        ilac_sonuc, f'{p} Heyette gastroenteroloji ∨ genel cerrahi',
        GASTRO_CER, 'Heyette gastroenteroloji ∨ genel cerrahi'))
    s.append(atom_recete_brans(
        ilac_sonuc, f'{p} Reçete eden gastro/genel cerrahi/iç hast.',
        GASTRO + GENEL_CERRAHI + IC_HAST, 'Gastro / genel cerrahi / iç hastalıkları'))
    s.append(atom_ucuncu_basamak(ilac_sonuc, f'{p} 3. basamak resmi kurum (bilgi)'))
    s.append(_ke_bilgi_atom(
        f'{p} CDAI yanıt takibi (bilgi)',
        'CDAI ≥70 puan düşüş (devam şartı)',
        'Crohn Hastalık Aktivite İndeksi başlangıç/devam yanıtı tek reçeteden '
        'doğrulanamaz — manuel'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# ARKETİP F — Juvenil / pediatrik (ACR pediatrik) — yapısal kapı + klinik KE
# ═══════════════════════════════════════════════════════════════════════
def jia_kontrol(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    meta = ENDIK_META['JIA'][madde]
    p = meta['sut']
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, f'{p} Çocuk (yaş <18)', '<', 18,
                         'Çocuk (yaş <18)'))
    s.append(_atom_endik(ilac_sonuc, f'{p} Juvenil idiyopatik artrit endikasyonu',
                         'JIA', madde, 'Juvenil idiyopatik artrit endikasyonu'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, f'{p} Önceki tedavi (NSAİİ/MTX/anti-TNF/tosilizumab) yetersiz',
        'Önceki basamak tedavisi yetersiz (madde lafzına göre)',
        ['nsai', 'nonsteroid', 'methotrexat', 'metotreksat', 'anti-tnf',
         'anti tnf', 'tnf', 'tosilizumab', 'tocilizumab', 'anakinra',
         'kortikosteroid']))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, f'{p} Heyette çocuk romatoloji uzmanı',
                              COCUK_ROMATOLOJI, 'Heyette çocuk romatoloji uzmanı'))
    s.append(atom_recete_brans(ilac_sonuc, f'{p} Reçete eden {meta["recete_ad"]}',
                               meta['recete'], meta['recete_ad']))
    s.append(atom_ucuncu_basamak(ilac_sonuc, f'{p} 3. basamak resmi kurum (bilgi)'))
    s.append(_ke_bilgi_atom(
        f'{p} ACR pediatrik yanıt (bilgi)',
        'ACR pediatrik 30/50/70 yanıt kriteri (başlangıç/devam)',
        'ACR pediatrik cevap kriteri + ağırlık (40/10 kg) tek reçeteden '
        'doğrulanamaz — manuel'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# ARKETİP G — Otoinflamatuar (FMF/CAPS/TRAPS/Still/DHA) — yapısal + klinik KE
# ═══════════════════════════════════════════════════════════════════════
def otoinf_kontrol(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    meta = ENDIK_META['OTOINF'][madde]
    p = meta['sut']
    s: List[SartSonuc] = []
    s.append(_atom_endik(
        ilac_sonuc, f'{p} Otoinflamatuar tanı (FMF/CAPS/TRAPS/Still/DHA)',
        'OTOINF', madde, 'Otoinflamatuar tanı (FMF/CAPS/TRAPS/Still/DHA)'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, f'{p} Heyette {meta["recete_ad"]}',
                              meta['heyet'], f'Heyette {meta["recete_ad"]}'))
    s.append(atom_recete_brans(ilac_sonuc, f'{p} Reçete eden {meta["recete_ad"]}',
                               meta['recete'], meta['recete_ad']))
    # Çekirdek klinik şart KE+şartlı (matematiğe dahil → yapısal tamsa ŞARTLI)
    s.append(_ke_bilgi_atom(
        f'{p} Klinik şartlar (manuel doğrulama)',
        'Atak sıklığı / CRP / kolşisin yanıtı / doz / yaş-ağırlık / önceki tedavi',
        'Otoinflamatuar klinik şartlar (atak/CRP/kolşisin/doz/ağırlık) metin '
        'parse ile doğrulanamaz — manuel'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# ARKETİP H — Özel (GPA/MPA, pemfigus, atopik dermatit, hidradenit)
# ═══════════════════════════════════════════════════════════════════════
def gpa_kontrol(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    meta = ENDIK_META['GPA'][madde]
    p = meta['sut']
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, f'{p} Erişkin (yaş ≥18)', '>=', 18,
                         'Erişkin (yaş ≥18)'))
    s.append(_atom_endik(ilac_sonuc, f'{p} GPA (Wegener) / MPA endikasyonu',
                         'GPA', madde, 'GPA (Wegener) / MPA endikasyonu'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, f'{p} Siklofosfamide dirençli ∨ verilemeyen',
        'Siklofosfamide dirençli ∨ siklofosfamid tedavisi verilemeyen',
        ['siklofosfamid', 'direncli', 'dirençli', 'verilemeyen']))
    s.append(_ke_bilgi_atom(
        f'{p} Glukokortikoid kombinasyonu',
        'Glukokortikoidlerle kombine kullanım',
        'GK kombinasyonu + 1 ay rapor süresi metin parse ile doğrulanamaz — manuel'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, f'{p} Heyette {meta["recete_ad"]}',
                              meta['heyet'], f'Heyette {meta["recete_ad"]}'))
    s.append(atom_recete_brans(ilac_sonuc, f'{p} Reçete eden {meta["recete_ad"]}',
                               meta['recete'], meta['recete_ad']))
    return s


def pemfigus_kontrol(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    meta = ENDIK_META['PEMFIGUS'][madde]
    p = meta['sut']
    s: List[SartSonuc] = []
    s.append(_atom_endik(ilac_sonuc, f'{p} Orta-şiddetli pemfigus vulgaris endikasyonu',
                         'PEMFIGUS', madde, 'Orta-şiddetli pemfigus vulgaris endikasyonu'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, f'{p} Sistemik steroid/immünsupresan ≥1 ay yetersiz',
        'Sistemik steroid &/veya immünsupresan ≥1 ay sonrası yetersiz/yeni lezyon',
        ['steroid', 'immunsupres', 'immünsupres', 'yeni lezyon', 'iyilesme']))
    s.append(_ke_bilgi_atom(
        f'{p} PDAİ skoru', 'PDAİ > 15',
        'Pemfigus Hastalığı Alan İndeksi (PDAİ) değeri metin parse ile '
        'doğrulanamadı — manuel'))
    s.append(atom_ucuncu_basamak(ilac_sonuc, f'{p} 3. basamak resmi kurum (bilgi)'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu (6 ay)'))
    s.append(atom_heyet_brans(ilac_sonuc, f'{p} Heyette dermatoloji uzmanı',
                              meta['heyet'], 'Heyette dermatoloji uzmanı'))
    s.append(atom_recete_brans(ilac_sonuc, f'{p} Reçete eden dermatoloji uzmanı',
                               meta['recete'], 'Dermatoloji uzmanı'))
    return s


def atopik_kontrol(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    meta = ENDIK_META['ATOPIK'][madde]
    p = meta['sut']
    # Barisitinib → ≥18; upadasitinib/abrositinib → ≥12
    barisitinib = _iceriyor(_arama_metni(ilac_sonuc), BARISITINIB)
    yas_esik = 18 if barisitinib else 12
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, f'{p} Yaş ≥{yas_esik}', '>=', yas_esik,
                         f'Yaş ≥{yas_esik} ({"barisitinib" if barisitinib else "upa/abrositinib"})'))
    s.append(_atom_endik(ilac_sonuc, f'{p} Orta/şiddetli atopik dermatit endikasyonu',
                         'ATOPIK', madde, 'Orta/şiddetli atopik dermatit endikasyonu'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, f'{p} Sistemik kortikosteroid+siklosporin (2 ay) yetersiz/tolere/kontrendike',
        '≥2 ay sistemik kortikosteroid + siklosporin yarar görmeyen ∨ tolere '
        'edemeyen ∨ kontrendike',
        ['kortikosteroid', 'siklosporin', 'yarar gormeyen', 'tolere',
         'kontrendike']))
    s.append(_atom_dupilumab_kombi(ilac_sonuc, f'{p} Dupilumab+JAK kombi yasağı'))
    s.append(atom_ucuncu_basamak(ilac_sonuc, f'{p} 3. basamak resmi kurum (bilgi)'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, f'{p} Heyette {meta["recete_ad"]} (3 uzman)',
                              meta['heyet'], f'Heyette dermatoloji/immünoloji'))
    s.append(atom_recete_brans(ilac_sonuc, f'{p} Reçete eden {meta["recete_ad"]}',
                               meta['recete'], meta['recete_ad']))
    s.append(_ke_bilgi_atom(
        f'{p} EASI/DLQI/Pruritus yanıtı (bilgi)',
        '12 hf: EASI ≥%50 ∨ DLQI ≥4 ∨ Pruritus NRS ≥3 (devam şartı)',
        'Atopik dermatit yanıt kriterleri tek reçeteden doğrulanamaz — manuel'))
    return s


def _atom_dupilumab_kombi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Upa/abro/bari + dupilumab birlikte kullanılamaz (C-6/8)."""
    metin = _rapor_metni(ilac_sonuc)   # diger_ilac_adlari dahil
    if 'dupilumab' in metin or 'dupixent' in metin:
        return SartSonuc(ad='Dupilumab ile kombinasyon', durum=SartDurumu.YOK,
                         neden='Upa/abro/bari + dupilumab birlikte kullanılamaz',
                         kaynak='diger_ilac', grup=grup)
    return SartSonuc(ad='Dupilumab kombinasyonu yok', durum=SartDurumu.VAR,
                     neden='Reçetede dupilumab işareti yok',
                     kaynak='diger_ilac', grup=grup, sartli_atom=True)


def hs_kontrol(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    meta = ENDIK_META['HS'][madde]
    p = meta['sut']
    s: List[SartSonuc] = []
    s.append(atom_yas_op(ilac_sonuc, f'{p} Erişkin (yaş ≥18)', '>=', 18,
                         'Erişkin (yaş ≥18)'))
    s.append(_atom_endik(ilac_sonuc, f'{p} Orta-şiddetli hidradenitis süpürativa endikasyonu',
                         'HS', madde, 'Orta-şiddetli hidradenitis süpürativa endikasyonu'))
    s.append(_onceki_tedavi_atom(
        ilac_sonuc, f'{p} 6 hf antibiyotik + ≥3 ay adalimumab yetersiz',
        '6 hafta sistemik antibiyotik + ≥3 ay adalimumab kullanıp yetersiz',
        ['antibiyotik', 'adalimumab', 'yetersiz']))
    s.append(atom_ucuncu_basamak(ilac_sonuc, f'{p} 3. basamak resmi kurum (bilgi)'))
    s.append(atom_saglik_kurulu_raporu(ilac_sonuc, f'{p} Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, f'{p} Heyette 3 dermatoloji uzmanı',
                              meta['heyet'], 'Heyette dermatoloji uzmanı'))
    s.append(atom_recete_brans(ilac_sonuc, f'{p} Reçete eden dermatoloji uzmanı',
                               meta['recete'], 'Dermatoloji uzmanı'))
    return s


def _diger_endikasyon_stub(ilac_sonuc: Dict, madde: str) -> List[SartSonuc]:
    """Bu madde/endikasyon henüz (sonraki arketip turunda) eklenecek."""
    ad = MADDE_ADLARI.get(madde, madde)
    return [SartSonuc(
        ad=f'{ad}: psöriazis dışı endikasyon',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Bu ilacın psöriazis dışı endikasyonu (RA/PsA/AS/Crohn/ÜK vb.) '
              'sonraki arketip turunda eklenecek — şimdilik manuel kontrol',
        kaynak='endikasyon', grup='Endikasyon (sonraki tur) (bilgi)',
        sartli_atom=True)]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ + MESAJ
# ═══════════════════════════════════════════════════════════════════════
def _mesaj_uret(sonuc: KontrolSonucu, madde: str, endik: str,
                sartlar: List[SartSonuc]) -> str:
    meta = _endik_meta(madde, endik) or _madde_meta(madde)
    baslik = (f"SUT {meta.get('sut', '4.2.1.' + madde)} "
              f"{meta.get('ad', MADDE_ADLARI.get(madde, madde))}")
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    if sonuc == KontrolSonucu.UYGUN:
        son = "UYGUN — tüm zorunlu şartlar sağlandı"
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        son = (f"ŞARTLI UYGUN — yapısal şartlar VAR; {len(ke)} klinik şart "
               f"manuel doğrulama gerektiriyor")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        son = "UYGUN DEĞİL — " + '; '.join(s.ad for s in yok[:3])
    else:
        son = f"ŞÜPHELİ — {len(ke)} şart kontrol edilemedi"
    return f"{baslik} | {son}"


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════
def biyolojik_kontrol_4_2_1_c(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.1.C-2…C-14 (anti-TNF dışı biyolojik) ana kontrol fonksiyonu."""
    madde = biyolojik_madde_belirle(ilac_sonuc)
    if madde is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.1.C-2…C-14 kapsamı dışı — biyolojik ajan tespit edilemedi',
            sut_kurali='SUT 4.2.1.C')
    endik = biyolojik_endikasyon_belirle(ilac_sonuc, madde)
    if endik == 'PSO':
        sartlar = pso_kontrol(ilac_sonuc, madde)
    elif endik == 'RA':
        sartlar = ra_kontrol(ilac_sonuc, madde)
    elif endik == 'PSA':
        sartlar = psa_kontrol(ilac_sonuc, madde)
    elif endik == 'AS':
        sartlar = as_kontrol(ilac_sonuc, madde)
    elif endik in ('CROHN', 'UK'):
        sartlar = ibd_kontrol(ilac_sonuc, madde, endik)
    elif endik == 'JIA':
        sartlar = jia_kontrol(ilac_sonuc, madde)
    elif endik == 'OTOINF':
        sartlar = otoinf_kontrol(ilac_sonuc, madde)
    elif endik == 'GPA':
        sartlar = gpa_kontrol(ilac_sonuc, madde)
    elif endik == 'PEMFIGUS':
        sartlar = pemfigus_kontrol(ilac_sonuc, madde)
    elif endik == 'ATOPIK':
        sartlar = atopik_kontrol(ilac_sonuc, madde)
    elif endik == 'HS':
        sartlar = hs_kontrol(ilac_sonuc, madde)
    else:
        sartlar = _diger_endikasyon_stub(ilac_sonuc, madde)
    sartlar.extend(_biyolojik_genel_bilgi_atomlari(
        ilac_sonuc, rituksimab=(madde == 'C2')))
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, madde, endik, sartlar)
    meta = _endik_meta(madde, endik) or _madde_meta(madde)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali=f"SUT {meta.get('sut', '4.2.1.' + madde)}",
        sartlar=sartlar,
        detaylar={'madde': madde, 'endikasyon': endik,
                  'ilac': meta.get('ad', MADDE_ADLARI.get(madde, madde))})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (CLAUDE.md §7.7)
# ═══════════════════════════════════════════════════════════════════════
def _rapor(heyet_brans: Optional[List[str]] = None, **ek) -> Dict:
    d = {'rapor_turu': 'Sağlık Kurulu Raporu'}
    if heyet_brans is not None:
        d['heyet_doktorlari'] = [{'brans': b} for b in heyet_brans]
    d.update(ek)
    return d


def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        # 1) Risankizumab PSO tam UYGUN
        ('Risankizumab PSO UYGUN', _rapor(
            ['Dermatoloji'], ilac_adi='SKYRIZI', etkin_madde='RISANKIZUMAB',
            atc_kodu='L04AC18', hasta_yasi=40,
            recete_teshisleri=['L40 Psoriazis'],
            rapor_metni='Plak psöriazis. Siklosporin ve metotreksat tedavisine '
                        'yanıt vermeyen hasta. PASI 18 olarak ölçüldü.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN),
        # 2) Risankizumab PASI değeri YOK → UYGUN DEĞİL (KARAR-1)
        ('Risankizumab PASI yok → UYGUN DEĞİL', _rapor(
            ['Dermatoloji'], ilac_adi='SKYRIZI', etkin_madde='RISANKIZUMAB',
            hasta_yasi=40, recete_teshisleri=['L40'],
            rapor_metni='Plak psöriazis. Metotreksata yanıtsız.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN_DEGIL),
        # 3) Guselkumab reçete eden iç hastalıkları → UYGUN DEĞİL (KARAR-3)
        ('Guselkumab reçete iç hast. → UYGUN DEĞİL', _rapor(
            ['Dermatoloji'], ilac_adi='TREMFYA', etkin_madde='GUSELKUMAB',
            hasta_yasi=50, recete_teshisleri=['L40'],
            rapor_metni='Plak psöriazis, PASI 22, fototerapiye yanıtsız.',
            doktor_uzmanligi='İç Hastalıkları'),
         KontrolSonucu.UYGUN_DEGIL),
        # 4) İksekizumab heyette dermatoloji yok → UYGUN DEĞİL (KARAR-2)
        ('İksekizumab heyet dermatoloji yok → UYGUN DEĞİL', _rapor(
            ['İç Hastalıkları'], ilac_adi='TALTZ', etkin_madde='IKSEKIZUMAB',
            hasta_yasi=45, recete_teshisleri=['L40'],
            rapor_metni='Plak psöriazis, PASI 20, siklosporine yanıtsız.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN_DEGIL),
        # 5) Bimekizumab raporsuz → UYGUN DEĞİL
        ('Bimekizumab raporsuz → UYGUN DEĞİL', {
            'ilac_adi': 'BIMZELX', 'etkin_madde': 'BIMEKIZUMAB',
            'hasta_yasi': 40, 'recete_teshisleri': ['L40'],
            'rapor_metni': 'PASI 18', 'doktor_uzmanligi': 'Dermatoloji'},
         KontrolSonucu.UYGUN_DEGIL),
        # 6) Ustekinumab klinik sessiz (geleneksel tedavi ibaresi yok) → ŞARTLI
        ('Ustekinumab geleneksel tedavi sessiz → ŞARTLI', _rapor(
            ['Dermatoloji'], ilac_adi='STELARA', etkin_madde='USTEKINUMAB',
            hasta_yasi=55, recete_teshisleri=['L40'],
            rapor_metni='Plak psöriazis. PASI 25.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.SARTLI_UYGUN),
        # 7) Risankizumab çocuk (yaş <18) → UYGUN DEĞİL
        ('Risankizumab çocuk → UYGUN DEĞİL', _rapor(
            ['Dermatoloji'], ilac_adi='SKYRIZI', etkin_madde='RISANKIZUMAB',
            hasta_yasi=12, recete_teshisleri=['L40'],
            rapor_metni='Plak psöriazis, PASI 16, MTX yanıtsız.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN_DEGIL),
        # 8) Apremilast PSO UYGUN (yalnız yanıt vermeyen)
        ('Apremilast PSO UYGUN', _rapor(
            ['Dermatoloji'], ilac_adi='OTEZLA', etkin_madde='APREMILAST',
            hasta_yasi=48, recete_teshisleri=['L40'],
            rapor_metni='Kronik plak psöriazis. Siklosporin, metotreksat ve '
                        'PUVA dahil sistemik tedavilere yanıt vermeyen. PASI 19. '
                        'Günlük doz ve süre belirtildi.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN),
        # 9) Sekukinumab AS — klinik kısmen sessiz (NSAİİ/akut faz KE) → ŞARTLI
        ('Sekukinumab AS klinik kısmi → ŞARTLI', _rapor(
            ['Romatoloji'], ilac_adi='COSENTYX', etkin_madde='SEKUKINUMAB',
            hasta_yasi=40, recete_teshisleri=['M45 Ankilozan spondilit'],
            rapor_metni='Ankilozan spondilit, BASDAİ 6.',
            doktor_uzmanligi='Romatoloji'),
         KontrolSonucu.SARTLI_UYGUN),
        # 10) Kapsam dışı (parasetamol)
        ('Kapsam dışı parasetamol', {
            'ilac_adi': 'PAROL', 'etkin_madde': 'PARASETAMOL',
            'atc_kodu': 'N02BE01'},
         KontrolSonucu.ATLANDI),
        # 11) Risankizumab endikasyon yok (plak psöriazis ICD/metin yok) → UYGUN DEĞİL
        ('Risankizumab endikasyon yok → UYGUN DEĞİL', _rapor(
            ['Dermatoloji'], ilac_adi='SKYRIZI', etkin_madde='RISANKIZUMAB',
            hasta_yasi=40, recete_teshisleri=['M06'],
            rapor_metni='Romatoid artrit. PASI 18.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN_DEGIL),
        # 12) Bimekizumab tam UYGUN
        ('Bimekizumab PSO UYGUN', _rapor(
            ['Dermatoloji'], ilac_adi='BIMZELX', etkin_madde='BIMEKIZUMAB',
            hasta_yasi=35, recete_teshisleri=['L40'],
            rapor_metni='Plak psöriazis, fototerapiyi tolere edemeyen, PASI 21.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN),

        # ── Arketip B (RA / DAS28) ──
        # 13) Abatasept RA tam UYGUN (MTX + DMARD + DAS28>5.1 + romatoloji)
        ('Abatasept RA UYGUN', _rapor(
            ['Romatoloji'], ilac_adi='ORENCIA', etkin_madde='ABATASEPT',
            atc_kodu='L04AA24', hasta_yasi=55,
            recete_teshisleri=['M06 Romatoid artrit'],
            rapor_metni='Romatoid artrit. Methotrexat ile birlikte. En az 3 '
                        'DMARD kullanmış. DAS28 5,8 ölçüldü.',
            doktor_uzmanligi='Romatoloji'),
         KontrolSonucu.UYGUN),
        # 14) Tosilizumab RA — MTX sessiz → ŞARTLI
        ('Tosilizumab RA MTX sessiz → ŞARTLI', _rapor(
            ['Romatoloji'], ilac_adi='ACTEMRA', etkin_madde='TOSILIZUMAB',
            hasta_yasi=60, recete_teshisleri=['M06'],
            rapor_metni='Romatoid artrit. Anti-TNF tedaviye rağmen DAS28 6,1.',
            doktor_uzmanligi='Romatoloji'),
         KontrolSonucu.SARTLI_UYGUN),
        # 15) Rituksimab RA reçete dermatoloji → UYGUN DEĞİL (branş)
        ('Rituksimab RA reçete dermatoloji → UYGUN DEĞİL', _rapor(
            ['Romatoloji'], ilac_adi='MABTHERA', etkin_madde='RITUKSIMAB',
            atc_kodu='L01FA01', hasta_yasi=50, recete_teshisleri=['M05'],
            rapor_metni='Romatoid artrit. Methotrexat ile kombinasyon. Anti-TNF '
                        'intoleransı. DAS28 5,4.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN_DEGIL),
        # 16) Tofacitinib RA UYGUN (C-6, MTX şartı yok, iç hast. reçete izinli)
        ('Tofacitinib RA UYGUN (iç hast.)', _rapor(
            ['Romatoloji'], ilac_adi='XELJANZ', etkin_madde='TOFASITINIB',
            atc_kodu='L04AF01', hasta_yasi=48, recete_teshisleri=['M06'],
            rapor_metni='Romatoid artrit. En az bir anti-TNF ajanına rağmen '
                        'DAS28 5,5.',
            doktor_uzmanligi='İç Hastalıkları'),
         KontrolSonucu.UYGUN),
        # 17) Abatasept RA heyette romatoloji yok → UYGUN DEĞİL
        ('Abatasept RA heyet yok → UYGUN DEĞİL', _rapor(
            ['Kardiyoloji'], ilac_adi='ORENCIA', etkin_madde='ABATASEPT',
            hasta_yasi=55, recete_teshisleri=['M06'],
            rapor_metni='Romatoid artrit, methotrexat, DMARD, DAS28 5,9.',
            doktor_uzmanligi='Romatoloji'),
         KontrolSonucu.UYGUN_DEGIL),
        # 18) Tosilizumab juvenil JIA — önceki tedavi sessiz → ŞARTLI
        ('Tosilizumab juvenil JIA → ŞARTLI', _rapor(
            ['Çocuk Romatoloji'], ilac_adi='ACTEMRA', etkin_madde='TOSILIZUMAB',
            hasta_yasi=10, recete_teshisleri=['M08 Juvenil artrit'],
            rapor_metni='Juvenil idiyopatik artrit.',
            doktor_uzmanligi='Çocuk Sağlığı ve Hastalıkları'),
         KontrolSonucu.SARTLI_UYGUN),

        # ── Arketip C (PsA / PSARC) ──
        # 19) İksekizumab PsA tam UYGUN (DMARD + anti-TNF + aktif eklem + romatoloji)
        ('İksekizumab PsA UYGUN', _rapor(
            ['Romatoloji'], ilac_adi='TALTZ', etkin_madde='IKSEKIZUMAB',
            hasta_yasi=45, recete_teshisleri=['L40.5 Psöriyatik artrit'],
            rapor_metni='Aktif psöriyatik artrit. 3 DMARD ve anti-TNF ajanı '
                        'kullanmış. 4 hassas eklem, 4 şiş eklem.',
            doktor_uzmanligi='Romatoloji'),
         KontrolSonucu.UYGUN),
        # 20) Apremilast PsA UYGUN (anti-TNF basamağı YOK — sadece DMARD+eklem)
        ('Apremilast PsA UYGUN (anti-TNF şartı yok)', _rapor(
            ['Romatoloji'], ilac_adi='OTEZLA', etkin_madde='APREMILAST',
            hasta_yasi=50, recete_teshisleri=['M07'],
            rapor_metni='Psöriyatik artrit. En az 3 DMARD uygun dozda kullanmış. '
                        '3 hassas eklem, 3 şiş eklem.',
            doktor_uzmanligi='İç Hastalıkları'),   # C-13 reçete iç hast. izinli
         KontrolSonucu.UYGUN),
        # 21) C-6(3) Tofa PsA reçete iç hast. → UYGUN DEĞİL (yalnız romatoloji)
        ('Tofacitinib PsA iç hast. → UYGUN DEĞİL (yalnız romatoloji)', _rapor(
            ['Romatoloji'], ilac_adi='XELJANZ', etkin_madde='TOFASITINIB',
            hasta_yasi=48, recete_teshisleri=['L40.5'],
            rapor_metni='Aktif psöriyatik artrit, 3 DMARD, anti-TNF yetersiz, '
                        '3 hassas 3 şiş eklem.',
            doktor_uzmanligi='İç Hastalıkları'),
         KontrolSonucu.UYGUN_DEGIL),
        # 22) Sekukinumab PsA klinik sessiz → ŞARTLI
        ('Sekukinumab PsA klinik sessiz → ŞARTLI', _rapor(
            ['Fizik Tedavi ve Rehabilitasyon'], ilac_adi='COSENTYX',
            etkin_madde='SEKUKINUMAB', hasta_yasi=40,
            recete_teshisleri=['M07'], rapor_metni='Psöriyatik artrit.',
            doktor_uzmanligi='Fizik Tedavi ve Rehabilitasyon'),
         KontrolSonucu.SARTLI_UYGUN),

        # ── Arketip D (AS / BASDAİ) ──
        # 23) Sekukinumab AS tam UYGUN
        ('Sekukinumab AS UYGUN', _rapor(
            ['Romatoloji'], ilac_adi='COSENTYX', etkin_madde='SEKUKINUMAB',
            hasta_yasi=42, recete_teshisleri=['M45 Ankilozan spondilit'],
            rapor_metni='Ankilozan spondilit. 3 NSAİİ indometazin maks dozda '
                        'yetersiz. BASDAİ 6. ESH 35. CRP yüksek.',
            doktor_uzmanligi='Romatoloji'),
         KontrolSonucu.UYGUN),
        # 24) Upadasitinib AS reçete dermatoloji → UYGUN DEĞİL
        ('Upadasitinib AS reçete dermatoloji → UYGUN DEĞİL', _rapor(
            ['Romatoloji'], ilac_adi='RINVOQ', etkin_madde='UPADASITINIB',
            atc_kodu='L04AF03', hasta_yasi=40, recete_teshisleri=['M45'],
            rapor_metni='Aksiyel ankilozan spondilit. Anti-TNF intoleransı.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN_DEGIL),

        # ── Arketip E (Crohn / ÜK) ──
        # 25) Vedolizumab Crohn UYGUN
        ('Vedolizumab Crohn UYGUN', _rapor(
            ['Gastroenteroloji'], ilac_adi='ENTYVIO', etkin_madde='VEDOLIZUMAB',
            atc_kodu='L04AA33', hasta_yasi=35, recete_teshisleri=['K50 Crohn'],
            rapor_metni='Aktif luminal Crohn. Anti-TNF tedavisine rağmen kontrol '
                        'edilemiyor.',
            doktor_uzmanligi='Gastroenteroloji'),
         KontrolSonucu.UYGUN),
        # 26) Vedolizumab ÜK heyet yok → UYGUN DEĞİL
        ('Vedolizumab ÜK heyet yok → UYGUN DEĞİL', _rapor(
            ['Kardiyoloji'], ilac_adi='ENTYVIO', etkin_madde='VEDOLIZUMAB',
            hasta_yasi=40, recete_teshisleri=['K51 Ülseratif kolit'],
            rapor_metni='Şiddetli aktif ülseratif kolit, anti-TNF yetersiz.',
            doktor_uzmanligi='Gastroenteroloji'),
         KontrolSonucu.UYGUN_DEGIL),

        # ── Arketip F (Juvenil) ──
        # 27) Abatasept JIA — önceki tedavi ibaresi var, ACR=bilgi → UYGUN
        ('Abatasept JIA → UYGUN (önceki tedavi ibaresi)', _rapor(
            ['Çocuk Romatoloji'], ilac_adi='ORENCIA', etkin_madde='ABATASEPT',
            hasta_yasi=12, recete_teshisleri=['M08 Juvenil idiyopatik artrit'],
            rapor_metni='Juvenil idiyopatik artrit. Anti-TNF tedaviye rağmen '
                        'yanıtsız.',
            doktor_uzmanligi='Çocuk Romatoloji'),
         KontrolSonucu.UYGUN),
        # 28) Tofacitinib JIA erişkin yaş (≥18) → UYGUN DEĞİL (çocuk şartı)
        ('Tofacitinib JIA yaş ≥18 → UYGUN DEĞİL', _rapor(
            ['Çocuk Romatoloji'], ilac_adi='XELJANZ', etkin_madde='TOFASITINIB',
            hasta_yasi=25, recete_teshisleri=['M08'],
            rapor_metni='Juvenil idiyopatik artrit.',
            doktor_uzmanligi='Çocuk Romatoloji'),
         KontrolSonucu.UYGUN_DEGIL),

        # ── Arketip G (Otoinflamatuar) ──
        # 29) Kanakinumab FMF → klinik KE → ŞARTLI
        ('Kanakinumab FMF → ŞARTLI', _rapor(
            ['Romatoloji'], ilac_adi='ILARIS', etkin_madde='KANAKINUMAB',
            atc_kodu='L04AC08', hasta_yasi=30,
            recete_teshisleri=['E85.0 Ailevi Akdeniz Ateşi'],
            rapor_metni='Ailevi Akdeniz Ateşi (FMF). Kolşisin yetersiz.',
            doktor_uzmanligi='Romatoloji'),
         KontrolSonucu.SARTLI_UYGUN),
        # 30) Anakinra FMF reçete dermatoloji → UYGUN DEĞİL
        ('Anakinra FMF reçete dermatoloji → UYGUN DEĞİL', _rapor(
            ['Romatoloji'], ilac_adi='KINERET', etkin_madde='ANAKINRA',
            hasta_yasi=28, recete_teshisleri=['E85.0'],
            rapor_metni='FMF amiloidoz.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN_DEGIL),

        # ── Arketip H (Özel) ──
        # 31) Rituksimab GPA → klinik KE → ŞARTLI
        ('Rituksimab GPA → ŞARTLI', _rapor(
            ['Romatoloji'], ilac_adi='MABTHERA', etkin_madde='RITUKSIMAB',
            atc_kodu='L01FA01', hasta_yasi=50,
            recete_teshisleri=['M31.3 Wegener granülomatozu'],
            rapor_metni='Granülomatöz polianjit (Wegener). Siklofosfamide '
                        'dirençli. Glukokortikoid ile kombine.',
            doktor_uzmanligi='Romatoloji'),
         KontrolSonucu.SARTLI_UYGUN),
        # 32) Sekukinumab hidradenitis UYGUN-zemin (klinik KE) → ŞARTLI
        ('Sekukinumab hidradenitis → ŞARTLI', _rapor(
            ['Dermatoloji'], ilac_adi='COSENTYX', etkin_madde='SEKUKINUMAB',
            hasta_yasi=33, recete_teshisleri=['L73.2 Hidradenitis süpürativa'],
            rapor_metni='Orta-şiddetli hidradenitis süpürativa. 6 hafta '
                        'antibiyotik ve adalimumab yetersiz.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN),
        # 33) Upadasitinib atopik dermatit + dupilumab kombi → UYGUN DEĞİL
        ('Upadasitinib atopik + dupilumab → UYGUN DEĞİL', _rapor(
            ['Dermatoloji'], ilac_adi='RINVOQ', etkin_madde='UPADASITINIB',
            hasta_yasi=20, recete_teshisleri=['L20 Atopik dermatit'],
            rapor_metni='Orta-şiddetli atopik dermatit. Kortikosteroid ve '
                        'siklosporin tolere edemeyen. Dupilumab ile birlikte.',
            doktor_uzmanligi='Dermatoloji',
            diger_ilac_adlari=['DUPIXENT']),
         KontrolSonucu.UYGUN_DEGIL),
        # 34) Barisitinib atopik dermatit yaş 15 (<18) → UYGUN DEĞİL
        ('Barisitinib atopik yaş 15 → UYGUN DEĞİL', _rapor(
            ['Dermatoloji'], ilac_adi='OLUMIANT', etkin_madde='BARISITINIB',
            hasta_yasi=15, recete_teshisleri=['L20'],
            rapor_metni='Atopik dermatit. Kortikosteroid+siklosporin yetersiz.',
            doktor_uzmanligi='Dermatoloji'),
         KontrolSonucu.UYGUN_DEGIL),
    ]


def _akil_testi() -> None:
    senaryolar = _senaryolar()
    gecen = 0
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = biyolojik_kontrol_4_2_1_c(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecen += ok
        isaret = 'OK ' if ok else 'XX '
        print(f"{isaret}{ad}")
        if not ok:
            print(f"    beklenen={beklenen.value}  bulunan={rapor.sonuc.value}")
            print(f"    mesaj: {rapor.mesaj}")
    print(f"\n{gecen}/{len(senaryolar)} test geçti")


if __name__ == '__main__':
    _akil_testi()
