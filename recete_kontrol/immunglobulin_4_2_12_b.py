# -*- coding: utf-8 -*-
"""SUT 4.2.12.B — Spesifik olmayan/gamma/polivalan immünglobulinler.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:5406-5450`` (mevzuat.gov.tr,
MevzuatNo=17229; Başlığı ile Birlikte Değişik:RG-2/11/2024-32710). Protokol:
``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + ``docs/SUT_AI_PROTOKOL_v1.md`` +
CLAUDE.md ``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
KAPSAM & DİSPATCH
═══════════════════════════════════════════════════════════════════════════
Kapsam: spesifik OLMAYAN normal human immünglobulin (ATC J06BA*; IVIG/SCIG).
Kapsam DIŞI: spesifik/hiperimmün Ig'ler (Hepatit B/HBIG, tetanoz, anti-D/Rho,
CMV, kuduz, suçiçeği — J06BB*; bunlar 4.2.12.A) → ATLANDI.

Tek motor + yumuşak route dispatch (kullanıcı kararı 2026-06-04):
  • IGM  → Pentaglobin (IgM-zenginleştirilmiş)  → B-1(2) septik şok yolağı
  • SC   → yalnız subkutan ürünler (Hizentra/Cuvitru/Cutaquig/HyQvia/...)
           veya ATC J06BA01 → B-2 (a/b/c)
  • IV   → diğer tüm spesifik olmayan Ig (B-1, a–g)
  • BELİRSİZ → endikasyon hangi route'ta geçerliyse o; branş listesi birleşim.

Asıl dispatcher ENDİKASYON'dur (ICD + rapor/teşhis metni). Endikasyon bent'i
hem heyette aranan uzmanı hem reçete eden uzmanı belirler.

═══════════════════════════════════════════════════════════════════════════
ENDİKASYON YOLAKLARI (B-1: a–g + madde 2;  B-2: a–c)
═══════════════════════════════════════════════════════════════════════════
  PRIMER_IY   (a) Primer/konjenital immün yetmezlik
                  IV: hemat, tıbbi onk, enf+klin.mikr, göğüs, romatoloji,
                      nefroloji, immünoloji/alerji
                  SC: hemat, göğüs, immünoloji/alerji
  KLL_MM_HKHT (b) (prof. antibiyotik başarısız∨kontrendike) ∧
                  [KLL hipogama+rekürren enf ∨ MM hipogama+rekürren enf ∨
                   allojenik HKHT öncesi/sonrası hipogama]
                  → hematoloji ∨ çocuk hem-onk   (IV+SC)
  ITP         (c) İTP ∧ (kanama riski yüksek ∨ cerrahi öncesi trombosit)
                  → hematoloji   (IV)
  GBS         (ç) Guillain-Barré  → nöroloji  (IV, ACİL: uzman hekim raporu yeter)
  KAWASAKI    (d) Kawasaki → romatoloji, immünoloji/alerji, kardiyoloji,
                  enf+klin.mikr, çocuk enfeksiyon   (IV)
  MMN         (e) Multifokal motor nöropati → nöroloji  (IV)
  CIDP        (f) KİDP ∧ [steroid(puls+idame≥6ay) yetersiz ∨ steroid
                  komplikasyon/kontrendikasyon] → nöroloji  (IV)
              (c-SC) KİDP'de IVIG stabilizasyon sonrası SC devam ∧ YALNIZ
                  ERİŞKİN → nöroloji   (B-2)
  MG_BULBER   (g) Bulber tutulumlu Myastenia Gravis → nöroloji
                  (IV, ACİL: uzman hekim raporu yeter)
  SEPTIK_SOK  (2) IgM ile zenginleştirilmiş Ig; 3.basamak YBÜ ∧ ciddi
                  bakteriyel enf. septik şok ∧ (OAB≤65mmHg ∧ laktat≥2) ∧
                  antibiyotik/sıvı/vazopressör'e dirençli → UZMAN HEKİM
                  (SK GEREKMEZ).

═══════════════════════════════════════════════════════════════════════════
ORTAK ŞARTLAR (madde-2/IgM hariç)
═══════════════════════════════════════════════════════════════════════════
  R1  Sağlık kurulu raporu VAR        (ACİL endikasyonda: SK ∨ uzman raporu)
  R2  Heyette ilgili bent uzmanı VAR  (≥1)
  R3  Reçeteyi ilgili bent uzmanı düzenlemiş
  R4  Rapor süresi (1 yıl; ç,g: 1 ay)  → (bilgi)
  X1  Birdshot retinokoroidopati YOK   → ÖN-KONTROL (varsa ödenmez = UYGUN DEĞİL)

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (genel kalıp)
═══════════════════════════════════════════════════════════════════════════
  YOLAK_UYGUN ⇔ ENDİKASYON ∧ R1 ∧ R2 ∧ R3 ∧ R4(bilgi)   (¬X1 ön-kontrol)
                [∧ endikasyona-özel klinik şartlar (şartlı/KE)]
  SEPTIK_UYGUN ⇔ IgM ∧ septik_şok(şartlı) ∧ (OAB∧laktat şartlı) ∧
                 tedaviye_dirençli(şartlı) ∧ 3.basamak_YBÜ(şartlı) ∧
                 reçete_uzman_hekim

Sessizlik = KONTROL_EDILEMEDI (örtük kabul YASAK, CLAUDE.md §2.5). Klinik
alt-şartlar parse edilemezse KE+şartlı → SARTLI_UYGUN (eczacı doğrular).
Rapor hiç yoksa R1=YOK → UYGUN_DEĞİL. Endikasyon hiç tespit edilemezse →
ŞÜPHELİ (hangi bent olduğu manuel belirlenmeli).

Ana entrypoint: ``immunglobulin_kontrol_4_2_12_b(ilac_sonuc)`` → ``KontrolRaporu``.
Kapsam/route : ``immunglobulin_kapsami_mi`` / ``ig_route_belirle``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İLAÇ TESPİTİ — spesifik OLMAYAN immünglobulin (J06BA*)
# ═══════════════════════════════════════════════════════════════════════
ATC_NONSPESIFIK_PREFIX = 'J06BA'   # J06BA01 (SC/ekstravasküler), J06BA02 (IV)
ATC_SPESIFIK_PREFIX = 'J06BB'      # spesifik/hiperimmün (Hep B, tetanoz, anti-D…)

# Spesifik olmayan Ig'in jenerik etken/ad işaretleri.
NONSPESIFIK_ANAHTAR: Set[str] = {
    'IMMUNGLOBULIN', 'IMMUNOGLOBULIN', 'IMMUN GLOBULIN', 'IMMUNO GLOBULIN',
    'IVIG', 'SCIG', 'NORMAL IMMUNGLOBULIN', 'INSAN NORMAL IMMUNGLOBULIN',
    'GAMMA GLOBULIN', 'GAMAGLOBULIN', 'POLIVALAN',
}

# Spesifik/hiperimmün dışlama işaretleri (bunlar 4.2.12.A — kapsam dışı).
SPESIFIK_DISLAMA: Set[str] = {
    'HEPATIT', 'HBIG', 'TETANOZ', 'TETANUS', 'ANTI-D', 'ANTI D', 'ANTID',
    'RHO', 'RHESUS', 'KUDUZ', 'RABIES', 'VARICELLA', 'VARISELLA', 'SUCICEGI',
    'ZOSTER', 'CMV', 'SITOMEGALO', 'PALIVIZUMAB',  # palivizumab=spesifik mAb
}

# IgM-zenginleştirilmiş ürün (Pentaglobin) → madde-2 septik şok yolağı.
IGM_URUNLER: Set[str] = {'PENTAGLOBIN', 'IGM', 'IG M ZENGINLESTIRILMIS',
                         'IGM ZENGINLESTIRILMIS'}

# Yalnız subkutan ürünler → B-2.
SC_URUNLER: Set[str] = {
    'HIZENTRA', 'CUVITRU', 'CUTAQUIG', 'HYQVIA', 'GAMMANORM', 'XEMBIFY',
    'GAMUNEX SC',
}

# IV (veya IV/SC) spesifik olmayan Ig ürünleri → B-1 (bilgi/destek).
IV_URUNLER: Set[str] = {
    'KIOVIG', 'PRIVIGEN', 'OCTAGAM', 'FLEBOGAMMA', 'INTRATECT', 'IQYMUNE',
    'NANOGAM', 'GAMUNEX', 'IG VENA', 'IGVENA', 'INTRAGLOBIN', 'ENDOBULIN',
    'GAMMAGARD', 'PANZYGA', 'IMUNOGLOBIN', 'VENISIVE', 'GAMTAS',
}


# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower alt-string)
# ═══════════════════════════════════════════════════════════════════════
B_HEMATOLOJI = ['hematoloji']
B_COCUK_HEM_ONK = ['cocuk hematoloji', 'cocuk hematolojisi',
                   'pediatrik hematoloji', 'cocuk onkoloji',
                   'cocuk hematolojisi ve onkoloji']
B_TIBBI_ONK = ['tibbi onkoloji', 'medikal onkoloji', 'onkoloji']
B_ENFEKSIYON = ['enfeksiyon', 'klinik mikrobiyoloji']
B_COCUK_ENF = ['cocuk enfeksiyon', 'pediatrik enfeksiyon']
B_GOGUS = ['gogus hastalik', 'gogus hast', 'gogus']
B_ROMATOLOJI = ['romatoloji']
B_NEFROLOJI = ['nefroloji']
B_IMMUNOLOJI = ['immunoloji', 'alerji', 'allerji', 'klinik immunoloji']
B_NOROLOJI = ['noroloji', 'sinir hastaliklari']
B_KARDIYOLOJI = ['kardiyoloji']

# Pratisyen/aile hekimi (uzman hekim sayılmaz).
PRATISYEN_BRANSLAR = ['pratisyen', 'aile hek', 'genel pratisyen']


# ═══════════════════════════════════════════════════════════════════════
# ENDİKASYON KAYDI (registry)
# ═══════════════════════════════════════════════════════════════════════
# Her endikasyon: ad, hangi bent(ler), ICD prefiksleri, metin anahtarları,
# IV/SC branş listeleri, acil mı (uzman raporu yeterli), geçerli route'lar.

class Endikasyon:
    __slots__ = ('key', 'ad', 'madde', 'icd', 'anahtar', 'brans_iv',
                 'brans_sc', 'acil', 'routes')

    def __init__(self, key, ad, madde, icd, anahtar, brans_iv,
                 brans_sc=None, acil=False, routes=('IV',)):
        self.key = key
        self.ad = ad
        self.madde = madde
        self.icd: Tuple[str, ...] = icd
        self.anahtar: Tuple[str, ...] = anahtar
        self.brans_iv: List[str] = brans_iv
        self.brans_sc: Optional[List[str]] = brans_sc
        self.acil = acil
        self.routes: Tuple[str, ...] = routes


PRIMER_IY = Endikasyon(
    'PRIMER_IY', 'Primer (konjenital) immün yetmezlik', 'B-1(a)/B-2(a)',
    icd=('D80', 'D81', 'D82', 'D83', 'D84'),
    anahtar=('PRIMER IMMUN YETMEZLIK', 'KONJENITAL IMMUN', 'AGAMAGLOBULINEMI',
             'AGAMMAGLOBULINEMI', 'PRIMER IMMUN YETERSIZLIK',
             'ANTIKOR URETIMININ BOZUL', 'COMMON VARIABLE', 'CVID'),
    brans_iv=(B_HEMATOLOJI + B_TIBBI_ONK + B_ENFEKSIYON + B_GOGUS
              + B_ROMATOLOJI + B_NEFROLOJI + B_IMMUNOLOJI),
    brans_sc=(B_HEMATOLOJI + B_GOGUS + B_IMMUNOLOJI),
    routes=('IV', 'SC'))

KLL_MM_HKHT = Endikasyon(
    'KLL_MM_HKHT', 'KLL/MM/HKHT hipogamaglobulinemi', 'B-1(b)/B-2(b)',
    icd=('C91.1', 'C90.0', 'C90.2'),
    anahtar=('KRONIK LENFOSITIK LOSEMI', 'KLL', 'MULTIPL MIYELOM',
             'MULTIPLE MYELOMA', 'MULTIPL MYELOM', 'ALLOJENIK',
             'HEMATOPOIETIK KOK HUCRE', 'KOK HUCRE NAKLI',
             'KEMIK ILIGI NAKLI', 'HKHT'),
    brans_iv=(B_HEMATOLOJI + B_COCUK_HEM_ONK),
    brans_sc=(B_HEMATOLOJI + B_COCUK_HEM_ONK),
    routes=('IV', 'SC'))

ITP = Endikasyon(
    'ITP', 'İmmün Trombositopeni (İTP)', 'B-1(c)',
    icd=('D69.3',),
    anahtar=('IMMUN TROMBOSITOPENI', 'IMMUN TROMBOSITOPENIK',
             'IDIYOPATIK TROMBOSITOPENI', 'ITP'),
    brans_iv=B_HEMATOLOJI, routes=('IV',))

GBS = Endikasyon(
    'GBS', 'Guillain-Barré sendromu', 'B-1(ç)',
    icd=('G61.0',),
    anahtar=('GUILLAIN', 'GUILLAN', 'GUILLAIN BARRE', 'GBS',
             'AKUT INFLAMATUAR DEMIYELINIZAN POLIRADIKULON'),
    brans_iv=B_NOROLOJI, acil=True, routes=('IV',))

KAWASAKI = Endikasyon(
    'KAWASAKI', 'Kawasaki hastalığı', 'B-1(d)',
    icd=('M30.3',),
    anahtar=('KAWASAKI',),
    brans_iv=(B_ROMATOLOJI + B_IMMUNOLOJI + B_KARDIYOLOJI + B_ENFEKSIYON
              + B_COCUK_ENF),
    routes=('IV',))

MMN = Endikasyon(
    'MMN', 'Multifokal motor nöropati', 'B-1(e)',
    icd=('G61.8',),
    anahtar=('MULTIFOKAL MOTOR NOROPATI', 'MULTIFOKAL MOTOR NEUROPATI', 'MMN'),
    brans_iv=B_NOROLOJI, routes=('IV',))

CIDP = Endikasyon(
    'CIDP', 'Kronik inflamatuvar demiyelinizan polinöropati (KİDP)',
    'B-1(f)/B-2(c)',
    icd=('G61.81', 'G61.8'),
    anahtar=('KRONIK INFLAMATUAR DEMIYELINIZAN', 'KRONIK INFLAMATUVAR DEMIYELINIZAN',
             'KIDP', 'CIDP', 'DEMIYELINIZAN POLINOROPATI',
             'DEMIYELINIZAN POLINEUROPATI'),
    brans_iv=B_NOROLOJI, brans_sc=B_NOROLOJI, routes=('IV', 'SC'))

MG_BULBER = Endikasyon(
    'MG_BULBER', 'Bulber tutulumlu Myastenia Gravis', 'B-1(g)',
    icd=('G70.0',),
    anahtar=('MYASTENIA GRAVIS', 'MIYASTENIA GRAVIS', 'MYASTHENIA',
             'BULBER MYASTENI', 'BULBER TUTULUM'),
    brans_iv=B_NOROLOJI, acil=True, routes=('IV',))

SEPTIK_SOK = Endikasyon(
    'SEPTIK_SOK', 'IgM-Ig: septik şok (3.basamak YBÜ)', 'B-1(2)',
    icd=('R57.2', 'A41'),
    anahtar=('SEPTIK SOK', 'SEPSIS', 'SEPTIK SOKTA'),
    brans_iv=[], acil=False, routes=('IGM',))

# Tespit önceliği: spesifik → genel (hipogama hem PRIMER hem b'de geçer; b
# daha spesifik bağlam ister → b önce). MG/CIDP/MMN nöro-spesifik önce.
ENDIKASYON_SIRA: List[Endikasyon] = [
    MG_BULBER, CIDP, MMN, KAWASAKI, GBS, ITP, KLL_MM_HKHT, PRIMER_IY,
]


# ═══════════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _atc(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')


def _iceriyor(metin_upper: str, kume) -> bool:
    return any(norm_tr_upper(k) in metin_upper for k in kume)


def _brans_l(brans: Optional[str]) -> str:
    return norm_tr_lower(brans or '')


def _brans_listede(brans: Optional[str], anahtarlar: List[str]) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in anahtarlar)


def _endikasyon_metni(ilac_sonuc: Dict) -> str:
    """Reçete + rapor teşhis/açıklama birleşik (ASCII-upper, endikasyon araması)."""
    parcalar: List[str] = []
    for k in ('rec_tesh', 'rap_tesh', 'rap_ack', 'rapor_metni', 'tum_metin',
              'teshis_tum', 'recete_teshisleri', 'rapor_aciklamalari',
              'recete_aciklamalari', 'teshis_kodu_listesi'):
        v = ilac_sonuc.get(k)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
            parcalar.append(str(v))
    return norm_tr_upper(' '.join(parcalar))


def _icd_var(metin_upper: str, prefiksler: Tuple[str, ...]) -> bool:
    """ICD prefiksi (nokta dahil) metinde token olarak var mı?"""
    for p in prefiksler:
        pu = norm_tr_upper(p)
        # 'C91.1' → 'C91\.1', tam/alt kod: C91.1 veya C91.10
        pat = re.escape(pu).replace(r'\.', r'\.')
        if re.search(r'\b' + pat + r'(\b|\d)', metin_upper):
            return True
    return False


def _yas(ilac_sonuc: Dict) -> Optional[int]:
    for k in ('hasta_yasi', 'yas', 'hasta_yas'):
        v = ilac_sonuc.get(k)
        if v in (None, ''):
            continue
        try:
            return int(float(str(v).replace(',', '.')))
        except (ValueError, TypeError):
            continue
    return None


# ═══════════════════════════════════════════════════════════════════════
# KAPSAM / ROUTE / ENDİKASYON DİSPATCH
# ═══════════════════════════════════════════════════════════════════════

def immunglobulin_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """Reçete kalemi spesifik OLMAYAN immünglobulin mi (J06BA*)?"""
    atc = _atc(ilac_sonuc)
    metin = _arama_metni(ilac_sonuc)
    # Spesifik (J06BB / hiperimmün ad) → kapsam dışı
    if atc.startswith(ATC_SPESIFIK_PREFIX):
        return False
    if atc.startswith(ATC_NONSPESIFIK_PREFIX):
        # Pentaglobin J06BA02 de buraya düşer (IgM) — kapsamda.
        return True
    # ATC yoksa ad üzerinden: Ig anahtarı VAR ∧ spesifik dışlama YOK
    if _iceriyor(metin, NONSPESIFIK_ANAHTAR) and not _iceriyor(metin, SPESIFIK_DISLAMA):
        return True
    return False


def ig_route_belirle(ilac_sonuc: Dict) -> str:
    """Route ipucu → 'IGM' | 'SC' | 'IV' | 'BELIRSIZ'."""
    atc = _atc(ilac_sonuc)
    metin = _arama_metni(ilac_sonuc)
    if _iceriyor(metin, IGM_URUNLER):
        return 'IGM'
    if _iceriyor(metin, SC_URUNLER) or atc.startswith('J06BA01'):
        return 'SC'
    if _iceriyor(metin, IV_URUNLER) or atc.startswith('J06BA02'):
        return 'IV'
    return 'BELIRSIZ'


def _endikasyon_belirle(ilac_sonuc: Dict, route: str) -> Optional[Endikasyon]:
    """Endikasyon tespit (ICD + metin anahtarı), route geçerliliğiyle.

    IGM route → yalnız SEPTIK_SOK. Diğer route'larda öncelik sırasına göre
    ilk eşleşen (route uyumlu) endikasyon döner.
    """
    if route == 'IGM':
        return SEPTIK_SOK
    metin = _endikasyon_metni(ilac_sonuc)
    aday: Optional[Endikasyon] = None
    for end in ENDIKASYON_SIRA:
        # route uyumu: BELIRSIZ → hepsi; aksi halde end.routes içinde olmalı
        if route != 'BELIRSIZ' and route not in end.routes:
            continue
        if _icd_var(metin, end.icd) or _iceriyor(metin, end.anahtar):
            aday = end
            break
    return aday


# ═══════════════════════════════════════════════════════════════════════
# ORTAK ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

def _rapor_sinyali_var(ilac_sonuc: Dict) -> bool:
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no')
                   or ilac_sonuc.get('rap_tak_no') or '').strip()
    rapor_turu = (ilac_sonuc.get('rapor_turu') or ilac_sonuc.get('rapor_turu_adi') or '').strip()
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or '').strip()
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    heyet_n = len(heyet) if isinstance(heyet, (list, tuple)) else 0
    return bool(rapor_kodu or rapor_takip or rapor_turu or rb or heyet_n)


def atom_r1_rapor(ilac_sonuc: Dict, grup: str, acil: bool) -> SartSonuc:
    """R1: Sağlık kurulu raporu VAR.

    ACİL endikasyon (GBS/MG): SK ∨ uzman hekim raporu yeterli → herhangi rapor
    VAR sayılır. Diğerlerinde SK raporu şart (kanser_gcsf SK mantığı).
    """
    rapor_turu = norm_tr_lower(ilac_sonuc.get('rapor_turu') or
                               ilac_sonuc.get('rapor_turu_adi') or '')
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    heyet_n = len([h for h in heyet if (isinstance(h, dict) and (h.get('ad') or h.get('brans')))]) \
        if isinstance(heyet, (list, tuple)) else 0
    rapor_var = _rapor_sinyali_var(ilac_sonuc)

    if acil:
        if rapor_var:
            return SartSonuc(ad='Rapor (SK veya uzman hekim — acil)',
                             durum=SartDurumu.VAR,
                             neden='Acil endikasyon: uzman hekim raporu da yeterli',
                             kaynak='rapor', grup=grup)
        return SartSonuc(ad='Rapor (SK veya uzman hekim — acil)',
                         durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor bulunamadı',
                         kaynak='rapor', grup=grup)

    kurul_isaret = ('kurul' in rapor_turu) or (heyet_n >= 2)
    uzman_tek = ('uzman' in rapor_turu) and ('kurul' not in rapor_turu)
    if kurul_isaret:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
                         neden=f"Sağlık kurulu raporu "
                               f"({rapor_turu or 'heyet ' + str(heyet_n) + ' uzman'})",
                         kaynak='rapor_turu+heyet', grup=grup)
    if uzman_tek and heyet_n <= 1:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Rapor "uzman hekim raporu" — 4.2.12.B sağlık kurulu '
                               'raporu ister (heyet ≤1)',
                         kaynak='rapor_turu+heyet', grup=grup)
    if not rapor_var:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor yok — SK raporu zorunlu',
                         kaynak='rapor', grup=grup)
    return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama türü/heyeti sağlık kurulu olarak '
                           'doğrulanamadı — manuel kontrol',
                     kaynak='rapor_turu+heyet', grup=grup, sartli_atom=True)


def atom_r2_heyet(ilac_sonuc: Dict, branslar: List[str], grup: str,
                  acil: bool) -> SartSonuc:
    """R2: heyette ilgili bent uzmanı (≥1) var mı?"""
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not isinstance(heyet, (list, tuple)) or not heyet:
        if acil:
            # Acil GBS/MG: uzman hekim raporu yeterli → heyet ARANMAZ (bilgi dışı,
            # matematiği bozmaz). Heyet VARSA aşağıda normal denetlenir.
            return SartSonuc(
                ad='Heyet (acil — uzman raporu yeterli)',
                durum=SartDurumu.KONTROL_EDILEMEDI,
                neden='Acil endikasyon: ilgili uzman hekim raporu yeterli, '
                      'sağlık kurulu/heyet aranmaz',
                kaynak='heyet', grup='(bilgi) ' + grup, sartli_atom=True)
        return SartSonuc(ad='Heyette ilgili uzman (≥1)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor heyeti bilgisi yok — manuel doğrulama',
                         kaynak='heyet', grup=grup, sartli_atom=True)
    bulunan = [h.get('brans') for h in heyet
               if isinstance(h, dict) and _brans_listede(h.get('brans'), branslar)]
    if bulunan:
        return SartSonuc(ad='Heyette ilgili uzman (≥1)', durum=SartDurumu.VAR,
                         neden='Heyette uygun branş: '
                               + ', '.join(b for b in bulunan if b),
                         kaynak='heyet', grup=grup)
    branslar_str = ', '.join((h.get('brans') if isinstance(h, dict) else str(h)) or '?'
                             for h in heyet)
    return SartSonuc(ad='Heyette ilgili uzman (≥1)', durum=SartDurumu.YOK,
                     neden=f'Heyette ilgili bent uzmanı yok (heyet: {branslar_str})',
                     kaynak='heyet', grup=grup)


def atom_r3_recete_brans(ilac_sonuc: Dict, branslar: List[str],
                         grup: str) -> SartSonuc:
    """R3: reçeteyi düzenleyen hekim ilgili bent uzmanı mı?"""
    brans = (ilac_sonuc.get('doktor_uzmanligi') or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden ilgili uzman',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, branslar):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='İlgili bent uzmanı', kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Reçeteyi ilgili bent uzmanı düzenlemeli',
                     kaynak='hekim_brans', grup=grup)


def atom_r4_sure_bilgi(grup: str, sure_lafzi: str) -> SartSonuc:
    """R4 (bilgi): rapor süresi (1 yıl / 1 ay) — parse edilemez, manuel."""
    return SartSonuc(ad=f'Rapor süresi {sure_lafzi}', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Rapor geçerlilik süresi ({sure_lafzi}) — manuel kontrol',
                     kaynak='rapor', grup=grup, sartli_atom=True)


def atom_endikasyon(ilac_sonuc: Dict, end: Endikasyon, grup: str) -> SartSonuc:
    """Endikasyon teşhisi (ICD/metin) — dispatch zaten eşleşti, kanıtı raporla."""
    metin = _endikasyon_metni(ilac_sonuc)
    icd = _icd_var(metin, end.icd)
    anah = _iceriyor(metin, end.anahtar)
    if icd or anah:
        kaynak = 'ICD' if icd else 'teshis_metni'
        return SartSonuc(ad=f'Endikasyon: {end.ad}', durum=SartDurumu.VAR,
                         neden=f'{end.ad} teşhisi bulundu ({kaynak})',
                         kaynak=kaynak, grup=grup)
    return SartSonuc(ad=f'Endikasyon: {end.ad}',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'{end.ad} teşhisi metinde net doğrulanamadı — manuel',
                     kaynak='teshis', grup=grup, sartli_atom=True)


# ── Endikasyona-özel klinik şart atomları (şartlı/KE) ──

_RE_PROF_ANTIBIYOTIK = re.compile(
    r'PROFILAKTIK\s+ANTIBIYOTIK.{0,40}(BASARISIZ|YETERSIZ|KONTRENDIKE|YANIT\s*ALINAMA)'
    r'|ANTIBIYOTIK\s+PROFILAKSI.{0,40}(BASARISIZ|YETERSIZ|KONTRENDIKE)')
_RE_HIPOGAMA = re.compile(r'HIPOGAMAGLOBULINEMI|HIPOGAMMAGLOBULINEMI|HIPOGAMA')
_RE_REKUREN = re.compile(r'REKURREN\s+(BAKTERIYEL\s+)?ENF|TEKRARLAYAN\s+ENF|REKUREN\s+ENF')
_RE_KANAMA = re.compile(r'KANAMA\s+RISKI\s+YUKSEK|CIDDI\s+KANAMA|AKTIF\s+KANAMA')
_RE_CERRAHI_TROMBO = re.compile(
    r'CERRAHI.{0,30}TROMBOSIT|TROMBOSIT.{0,30}(YUKSEL|HIZL)|AMELIYAT\s+ONCESI\s+TROMBOSIT')
_RE_STEROID_YETERSIZ = re.compile(
    r'STEROID.{0,40}(YETERSIZ|YANIT\s*ALINAMA|YETERSIZ\s*CEVAP|CEVAP\s*ALINAMA)')
_RE_STEROID_KONTR = re.compile(
    r'STEROID.{0,40}(KOMPLIKASYON|KONTRENDIKE|KONTRENDIKASYON|YAN\s*ETKI)')
_RE_SEPTIK = re.compile(r'SEPTIK\s+SOK|SEPSIS|SEPTIK\s+SOKTA')
_RE_YBU = re.compile(r'YOGUN\s*BAKIM|3\.?\s*BASAMAK|UCUNCU\s+BASAMAK|YBU')
_RE_DIRENCLI = re.compile(
    r'(ANTIBIYOTIK|SIVI|VAZOPRESSOR|VAZOPRESOR).{0,40}(RAGMEN|DIRENCLI|YANIT\s*ALINAMA)'
    r'|DIRENCLI\s+HIPOTANSIYON|REFRAKTER')


def atom_sartli_regex(ilac_sonuc: Dict, regex, ad: str, grup: str,
                      veya_grubu: bool = False, neden_var: str = '',
                      neden_yok: str = '') -> SartSonuc:
    """Klinik ibareyi parse-dene; bulunamazsa KE+şartlı (örtük kabul yasak)."""
    metin = _endikasyon_metni(ilac_sonuc)
    if regex.search(metin):
        return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                         neden=neden_var or f'Raporda "{ad}" ibaresi bulundu',
                         kaynak='rapor_metni', grup=grup, veya_grubu=veya_grubu)
    return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=neden_yok or f'"{ad}" ibaresi metinde tespit edilemedi — manuel',
                     kaynak='rapor_metni', grup=grup, veya_grubu=veya_grubu,
                     sartli_atom=True)


def atom_yalniz_eriskin(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """B-2(c) CIDP SC: yalnız erişkin (yaş ≥ 18)."""
    yas = _yas(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad='Yalnız erişkin (≥18 yaş)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı bilinmiyor — manuel doğrulama',
                         kaynak='hasta_yasi', grup=grup, sartli_atom=True)
    if yas >= 18:
        return SartSonuc(ad=f'Yalnız erişkin (yaş {yas})', durum=SartDurumu.VAR,
                         neden='Erişkin — SC KİDP yalnız erişkinde',
                         kaynak='hasta_yasi', grup=grup)
    return SartSonuc(ad=f'Yalnız erişkin (yaş {yas})', durum=SartDurumu.YOK,
                     neden='SC KİDP yalnız erişkinde geçerli (yaş <18)',
                     kaynak='hasta_yasi', grup=grup)


def atom_recete_uzman_hekim(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Madde-2: reçeteyi UZMAN hekim düzenlemiş mi (pratisyen/aile değil)?"""
    brans = (ilac_sonuc.get('doktor_uzmanligi') or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden uzman hekim',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, PRATISYEN_BRANSLAR):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                         neden='Pratisyen/aile hekimi — uzman hekim ister',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden uzman hekim: {brans}', durum=SartDurumu.VAR,
                     neden='Uzman hekim', kaynak='hekim_brans', grup=grup)


# ═══════════════════════════════════════════════════════════════════════
# YOLAK ŞART ÜRETİMİ
# ═══════════════════════════════════════════════════════════════════════

def _endikasyon_branslari(end: Endikasyon, route: str) -> List[str]:
    if route == 'SC' and end.brans_sc is not None:
        return end.brans_sc
    if route == 'BELIRSIZ' and end.brans_sc is not None:
        # Birleşim (iki route'ta da geçerli endikasyon)
        return list(dict.fromkeys(end.brans_iv + end.brans_sc))
    return end.brans_iv


def _yolak_sartlari(ilac_sonuc: Dict, end: Endikasyon, route: str) -> List[SartSonuc]:
    """Endikasyona göre SartSonuc listesi (ortak + endikasyon-özel)."""
    # ── Madde-2 IgM septik şok (SK gerekmez) ──
    if end.key == 'SEPTIK_SOK':
        g = '(2) IgM septik şok'
        return [
            atom_sartli_regex(ilac_sonuc, _RE_SEPTIK, 'Septik şok endikasyonu',
                              g + ' — septik şok',
                              neden_var='Raporda septik şok/sepsis ibaresi'),
            atom_sartli_regex(ilac_sonuc, _RE_YBU, '3. basamak yoğun bakım',
                              g + ' — 3.basamak YBÜ'),
            atom_sartli_regex(ilac_sonuc, _RE_DIRENCLI,
                              'Antibiyotik/sıvı/vazopressör dirençli hipotansiyon',
                              g + ' — tedaviye dirençli'),
            atom_recete_uzman_hekim(ilac_sonuc, g + ' — reçete uzman hekim'),
            # OAB≤65 / laktat≥2 — sayısal, parse zor → bilgi
            SartSonuc(ad='OAB ≤65 mmHg ∧ laktat ≥2 mmol/L',
                      durum=SartDurumu.KONTROL_EDILEMEDI,
                      neden='Ortalama arter basıncı / laktat değeri — manuel doğrulama',
                      kaynak='rapor_metni', grup='(bilgi) OAB/laktat', sartli_atom=True),
        ]

    branslar = _endikasyon_branslari(end, route)
    bent = end.madde
    sartlar: List[SartSonuc] = [
        atom_endikasyon(ilac_sonuc, end, grup=f'{bent} Endikasyon'),
        atom_r1_rapor(ilac_sonuc, grup=f'{bent} Sağlık kurulu raporu', acil=end.acil),
        atom_r2_heyet(ilac_sonuc, branslar, grup=f'{bent} Heyette ilgili uzman',
                      acil=end.acil),
        atom_r3_recete_brans(ilac_sonuc, branslar, grup=f'{bent} Reçete eden uzman'),
    ]

    # ── Endikasyon-özel klinik şartlar ──
    if end.key == 'KLL_MM_HKHT':
        sartlar.append(atom_sartli_regex(
            ilac_sonuc, _RE_PROF_ANTIBIYOTIK,
            'Profilaktik antibiyotik başarısız/kontrendike',
            f'{bent} Prof. antibiyotik şartı'))
        sartlar.append(atom_sartli_regex(
            ilac_sonuc, _RE_HIPOGAMA, 'Hipogamaglobulinemi',
            f'{bent} Hipogamaglobulinemi'))
        # rekürren enf yalnız KLL/MM yolunda (HKHT'de aranmaz) — şartlı bilgi
        sartlar.append(atom_sartli_regex(
            ilac_sonuc, _RE_REKUREN, 'Rekürren bakteriyel enfeksiyon (KLL/MM)',
            '(bilgi) Rekürren enfeksiyon'))
    elif end.key == 'ITP':
        sartlar.append(atom_sartli_regex(
            ilac_sonuc, _RE_KANAMA, 'Kanama riski yüksek',
            f'{bent} İTP klinik şartı (≥1)', veya_grubu=True))
        sartlar.append(atom_sartli_regex(
            ilac_sonuc, _RE_CERRAHI_TROMBO,
            'Cerrahi öncesi trombosit hızla yükseltilmeli',
            f'{bent} İTP klinik şartı (≥1)', veya_grubu=True))
    elif end.key == 'CIDP':
        if route == 'SC':
            sartlar.append(atom_yalniz_eriskin(
                ilac_sonuc, grup=f'{bent} Yalnız erişkin'))
            sartlar.append(SartSonuc(
                ad='IVIG stabilizasyon sonrası SC devam',
                durum=SartDurumu.KONTROL_EDILEMEDI,
                neden='IVIG ile stabilizasyon sonrası SC geçiş — manuel doğrulama',
                kaynak='rapor_metni', grup='(bilgi) SC geçiş', sartli_atom=True))
        else:
            sartlar.append(atom_sartli_regex(
                ilac_sonuc, _RE_STEROID_YETERSIZ,
                'Steroide yetersiz cevap (puls+idame ≥6 ay)',
                f'{bent} Steroid şartı (≥1)', veya_grubu=True))
            sartlar.append(atom_sartli_regex(
                ilac_sonuc, _RE_STEROID_KONTR,
                'Steroid komplikasyon/kontrendikasyon',
                f'{bent} Steroid şartı (≥1)', veya_grubu=True))

    # ── Süre (bilgi) ──
    sure = '1 ay' if end.acil or end.key == 'GBS' else '1 yıl'
    sartlar.append(atom_r4_sure_bilgi(grup=f'(bilgi) Rapor süresi', sure_lafzi=sure))
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# ÖN-KONTROL: Birdshot retinokoroidopati (ödenmez)
# ═══════════════════════════════════════════════════════════════════════
_RE_BIRDSHOT = re.compile(r'BIRDSHOT|RETINOKOROIDOPATI|RETINOKOROIDIT')


def _birdshot_mu(ilac_sonuc: Dict) -> bool:
    return bool(_RE_BIRDSHOT.search(_endikasyon_metni(ilac_sonuc)))


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (kanser_gcsf motoru — grup + veya + şartlı; (bilgi) skip)
# ═══════════════════════════════════════════════════════════════════════

def _grup_degerlendir(gs: List[SartSonuc]) -> Tuple[str, bool]:
    veya = any(s.veya_grubu for s in gs)
    durumlar = [s.durum for s in gs]
    ke_atomlar = [s for s in gs if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    ke_sartli = bool(ke_atomlar) and all(s.sartli_atom for s in ke_atomlar)
    if veya:
        if any(d == SartDurumu.VAR for d in durumlar):
            return ('var', False)
        if all(d == SartDurumu.YOK for d in durumlar):
            return ('yok', False)
        return ('ke', ke_sartli)
    if any(d == SartDurumu.YOK for d in durumlar):
        return ('yok', False)
    if all(d == SartDurumu.VAR for d in durumlar):
        return ('var', False)
    return ('ke', ke_sartli)


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    gruplar: Dict[str, List[SartSonuc]] = {}
    for s in sartlar:
        if '(bilgi)' in (s.grup or ''):
            continue
        gruplar.setdefault(s.grup, []).append(s)
    if not gruplar:
        return KontrolSonucu.KONTROL_EDILEMEDI
    grup_sonuclari: List[str] = []
    sadece_sartli_ke = True
    for gs in gruplar.values():
        durum, sartli = _grup_degerlendir(gs)
        grup_sonuclari.append(durum)
        if durum == 'yok':
            sadece_sartli_ke = False
        elif durum == 'ke' and not sartli:
            sadece_sartli_ke = False
    if 'yok' in grup_sonuclari:
        return KontrolSonucu.UYGUN_DEGIL
    if 'ke' in grup_sonuclari:
        return (KontrolSonucu.SARTLI_UYGUN if sadece_sartli_ke
                else KontrolSonucu.KONTROL_EDILEMEDI)
    return KontrolSonucu.UYGUN


def _mesaj_uret(sonuc: KontrolSonucu, end: Optional[Endikasyon],
                route: str, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    ad = end.ad if end else 'belirsiz endikasyon'
    parcalar = [f'SUT 4.2.12.B ({route}) / {ad}']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — tüm zorunlu şartlar sağlandı')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — hesaplanabilir şartlar VAR; '
                        f'{len(ke)} şart manuel doğrulama gerektiriyor')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — ' + '; '.join(s.ad for s in yok[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def immunglobulin_kontrol_4_2_12_b(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.12.B — Spesifik olmayan immünglobulin kontrolü."""
    if not immunglobulin_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.12.B kapsamı dışı — spesifik olmayan immünglobulin '
                  '(J06BA*) değil',
            sut_kurali='SUT 4.2.12.B')

    # Ön-kontrol: Birdshot retinokoroidopati → ödenmez
    if _birdshot_mu(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj='SUT 4.2.12.B — Birdshot retinokoroidopati endikasyonu ödenmez',
            sut_kurali='SUT 4.2.12.B (Birdshot retinokoroidopati hariç)',
            aranan_ibare='birdshot retinokoroidopati (dışlama)')

    route = ig_route_belirle(ilac_sonuc)
    end = _endikasyon_belirle(ilac_sonuc, route)

    if end is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='SUT 4.2.12.B — endikasyon (a–g/2) tespit edilemedi; hangi bent '
                  'olduğu manuel belirlenmeli',
            sut_kurali='SUT 4.2.12.B',
            aranan_ibare='primer IY / KLL-MM-HKHT / İTP / GBS / Kawasaki / MMN / '
                         'KİDP / bulber MG / septik şok',
            sartlar=[SartSonuc(
                ad='Endikasyon tespiti', durum=SartDurumu.KONTROL_EDILEMEDI,
                neden='Reçete/rapor teşhisinden 4.2.12.B endikasyonu okunamadı',
                kaynak='teshis', grup='Endikasyon', sartli_atom=True)])

    sartlar = _yolak_sartlari(ilac_sonuc, end, route)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, end, route, sartlar)

    detaylar = {
        'route': route,
        'endikasyon': end.key,
        'endikasyon_ad': end.ad,
        'madde': end.madde,
        'sut_maddesi': '4.2.12.B',
        'ilac_adi': (ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '').upper(),
        'etkin_madde': (ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '').upper(),
        'sart_sayisi': len(sartlar),
        'verdict_sartlar': [
            {'ad': s.ad, 'durum': s.durum.value, 'neden': s.neden,
             'kaynak': s.kaynak, 'grup': s.grup, 'veya_grubu': s.veya_grubu,
             'sartli_atom': s.sartli_atom, 'alt_liste': s.alt_liste}
            for s in sartlar
        ],
    }
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali=f'SUT 4.2.12.B / {end.madde} — {end.ad}',
        aranan_ibare=f'{end.ad}: endikasyon ∧ SK raporu ∧ heyet uzmanı ∧ '
                     f'reçete uzmanı',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (CLAUDE.md §7.7 — ≥10 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        # 1) Primer IY IV tam UYGUN (kurul + immünoloji heyet + immünoloji reçete)
        ("Primer IY IV UYGUN", {
            'ilac_adi': 'PRIVIGEN', 'etkin_madde': 'INSAN NORMAL IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'İmmünoloji ve Alerji Hastalıkları',
            'rapor_kodu': '12.01', 'recete_teshisleri': ['D80.0'],
            'heyet_doktorlari': [{'brans': 'İmmünoloji ve Alerji'},
                                 {'brans': 'Enfeksiyon Hastalıkları'}],
        }, KontrolSonucu.UYGUN),
        # 2) Primer IY SC UYGUN (Hizentra, göğüs heyet + göğüs reçete)
        ("Primer IY SC UYGUN (Hizentra)", {
            'ilac_adi': 'HIZENTRA', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA01', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'Göğüs Hastalıkları', 'rapor_kodu': '12.02',
            'recete_teshisleri': ['D83.9'],
            'heyet_doktorlari': [{'brans': 'Göğüs Hastalıkları'},
                                 {'brans': 'İmmünoloji'}],
        }, KontrolSonucu.UYGUN),
        # 3) Primer IY SC UYGUN DEĞİL: nefroloji SC'de geçerli değil (reçete branşı)
        ("Primer IY SC UYGUN DEĞİL (nefroloji SC-dışı)", {
            'ilac_adi': 'CUVITRU', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA01', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'Nefroloji', 'rapor_kodu': '12.02',
            'recete_teshisleri': ['D80.1'],
            'heyet_doktorlari': [{'brans': 'Nefroloji'}, {'brans': 'Hematoloji'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 4) KLL/MM/HKHT UYGUN (kurul + hematoloji), klinik şartlar şartlı → SARTLI
        ("KLL hipogama ŞARTLI (klinik ibare yok)", {
            'ilac_adi': 'KIOVIG', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'Hematoloji', 'rapor_kodu': '12.03',
            'recete_teshisleri': ['C91.1'],
            'heyet_doktorlari': [{'brans': 'Hematoloji'}, {'brans': 'İç Hastalıkları'}],
        }, KontrolSonucu.SARTLI_UYGUN),
        # 5) KLL tam UYGUN: klinik ibareler raporda var
        ("KLL hipogama UYGUN (tüm ibareler)", {
            'ilac_adi': 'OCTAGAM', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'Hematoloji', 'rapor_kodu': '12.03',
            'recete_teshisleri': ['C91.1'],
            'rap_ack': 'Kronik lenfositik lösemi, hipogamaglobulinemi ve rekürren '
                       'bakteriyel enfeksiyon. Profilaktik antibiyotik başarısız.',
            'heyet_doktorlari': [{'brans': 'Hematoloji'}, {'brans': 'İç Hastalıkları'}],
        }, KontrolSonucu.UYGUN),
        # 6) İTP UYGUN (kanama riski + hematoloji)
        ("İTP UYGUN (kanama riski)", {
            'ilac_adi': 'FLEBOGAMMA', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'Hematoloji', 'rapor_kodu': '12.04',
            'recete_teshisleri': ['D69.3'],
            'rap_ack': 'İmmün trombositopeni, kanama riski yüksek.',
            'heyet_doktorlari': [{'brans': 'Hematoloji'}, {'brans': 'İç Hastalıkları'}],
        }, KontrolSonucu.UYGUN),
        # 7) GBS acil UYGUN: uzman hekim raporu (heyet yok) + nöroloji
        ("GBS acil UYGUN (uzman raporu)", {
            'ilac_adi': 'IG VENA', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'rapor_turu': 'Uzman Hekim Raporu',
            'doktor_uzmanligi': 'Nöroloji', 'rapor_kodu': '12.05',
            'recete_teshisleri': ['G61.0'],
        }, KontrolSonucu.UYGUN),
        # 8) Kawasaki UYGUN DEĞİL: reçete nöroloji (Kawasaki branşı değil)
        ("Kawasaki UYGUN DEĞİL (nöroloji reçete)", {
            'ilac_adi': 'KIOVIG', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'Nöroloji', 'rapor_kodu': '12.06',
            'recete_teshisleri': ['M30.3'],
            'heyet_doktorlari': [{'brans': 'Kardiyoloji'}, {'brans': 'Romatoloji'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 9) CIDP IV UYGUN (steroid yetersiz + nöroloji)
        ("CIDP IV UYGUN (steroid yetersiz)", {
            'ilac_adi': 'PANZYGA', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'Nöroloji', 'rapor_kodu': '12.07',
            'recete_teshisleri': ['G61.81'],
            'rap_ack': 'Kronik inflamatuvar demiyelinizan polinöropati. Steroid '
                       'tedavisine yetersiz cevap alındı.',
            'heyet_doktorlari': [{'brans': 'Nöroloji'}, {'brans': 'İç Hastalıkları'}],
        }, KontrolSonucu.UYGUN),
        # 10) CIDP SC çocuk → UYGUN DEĞİL (yalnız erişkin)
        ("CIDP SC çocuk UYGUN DEĞİL", {
            'ilac_adi': 'HIZENTRA', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA01', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'Nöroloji', 'rapor_kodu': '12.08',
            'recete_teshisleri': ['G61.81'], 'hasta_yasi': 10,
            'rap_ack': 'KİDP IVIG stabilizasyon sonrası SC devam.',
            'heyet_doktorlari': [{'brans': 'Nöroloji'}, {'brans': 'İç Hastalıkları'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 11) Bulber MG acil UYGUN
        ("Bulber MG acil UYGUN", {
            'ilac_adi': 'PRIVIGEN', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'rapor_turu': 'Uzman Hekim Raporu',
            'doktor_uzmanligi': 'Nöroloji', 'rapor_kodu': '12.09',
            'recete_teshisleri': ['G70.0'],
            'rap_ack': 'Bulber tutulumlu myastenia gravis.',
        }, KontrolSonucu.UYGUN),
        # 12) Septik şok IgM (Pentaglobin) ŞARTLI (klinik ibareler eksik)
        ("Septik şok IgM ŞARTLI", {
            'ilac_adi': 'PENTAGLOBIN', 'etkin_madde': 'IGM IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'doktor_uzmanligi': 'Anesteziyoloji ve Reanimasyon',
            'recete_teshisleri': ['R57.2'],
        }, KontrolSonucu.SARTLI_UYGUN),
        # 13) Septik şok IgM tam UYGUN (tüm klinik ibareler + uzman)
        ("Septik şok IgM UYGUN", {
            'ilac_adi': 'PENTAGLOBIN', 'etkin_madde': 'IGM IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'doktor_uzmanligi': 'Yoğun Bakım',
            'recete_teshisleri': ['R57.2'],
            'rap_ack': 'Üçüncü basamak yoğun bakımda septik şok; uygun antibiyotik, '
                       'sıvı, vazopressör tedavisine rağmen dirençli hipotansiyon.',
        }, KontrolSonucu.UYGUN),
        # 14) Rapor yok → UYGUN DEĞİL (R1 YOK)
        ("Primer IY rapor yok UYGUN DEĞİL", {
            'ilac_adi': 'KIOVIG', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'doktor_uzmanligi': 'İmmünoloji',
            'recete_teshisleri': ['D80.0'],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 15) Endikasyon tespit edilemedi → ŞÜPHELİ
        ("Endikasyon belirsiz ŞÜPHELİ", {
            'ilac_adi': 'KIOVIG', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'İç Hastalıkları', 'rapor_kodu': '99',
            'recete_teshisleri': ['Z00.0'],
            'heyet_doktorlari': [{'brans': 'İç Hastalıkları'}],
        }, KontrolSonucu.KONTROL_EDILEMEDI),
        # 16) Birdshot → UYGUN DEĞİL (ödenmez)
        ("Birdshot UYGUN DEĞİL (ödenmez)", {
            'ilac_adi': 'KIOVIG', 'etkin_madde': 'IMMUNGLOBULIN',
            'atc_kodu': 'J06BA02', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'doktor_uzmanligi': 'Göz Hastalıkları',
            'rap_ack': 'Birdshot retinokoroidopati.',
        }, KontrolSonucu.UYGUN_DEGIL),
        # 17) Spesifik Ig (Hepatit B) → ATLANDI
        ("Hepatit B Ig ATLANDI (spesifik)", {
            'ilac_adi': 'HEPATECT', 'etkin_madde': 'HEPATIT B IMMUNGLOBULIN',
            'atc_kodu': 'J06BB04', 'recete_teshisleri': ['B16.9'],
        }, KontrolSonucu.ATLANDI),
        # 18) Kapsam dışı (parasetamol) → ATLANDI
        ("Kapsam dışı (parasetamol) ATLANDI", {
            'ilac_adi': 'PAROL', 'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.12.B İmmünglobulin — Akıl Testi\n" + "=" * 66)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = immunglobulin_kontrol_4_2_12_b(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 66)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
