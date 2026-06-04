# -*- coding: utf-8 -*-
"""SUT 4.2.33 — Göz hastalıklarında anti-VEGF / ilgili ilaç kullanım ilkeleri.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:7918-8079`` (mevzuat.gov.tr,
MevzuatNo=17229; Değişik:RG-4/9/2019-30878 + sonraki RG değişiklikleri).
Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ``ATOMİK DEVRE
ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
KAPSAM (eczane teslimi — "ayakta tedaviler kapsamında aylık temin")
═══════════════════════════════════════════════════════════════════════════

  Kapsam içi (3. basamak, sağlık kurulu raporu):
    - Ranibizumab  (LUCENTIS, RANIVISIO ...)        S01LA04
    - Aflibersept  (EYLEA ...)                      S01LA05
    - Deksametazon intravitreal implant (OZURDEX)   S01BA01 (implant formu)
    - Verteporfin  (VISUDYNE)                        S01LA01

  Kapsam dışı:
    - Bevacizumab (ALTUZAN/AVASTIN ...) → GÜNÜBİRLİK; hastanede uygulanır,
      eczane teslimi değil → ATLANDI + bilgi notu.

═══════════════════════════════════════════════════════════════════════════
ENDİKASYON DISPATCHER (ICD + teşhis lafzı)
═══════════════════════════════════════════════════════════════════════════

  AMD     (4.2.33.A) → H35.3 / "yaş tip", "neovasküler", "yaşa bağlı makula"
  RVO     (4.2.33.B) → H34.8 / "retina ven tıkanıklığı", "santral retinal ven"
  PM-KNV  (4.2.33.C) → H44.2 / "patolojik miyopi", "koroidal neovaskül"
  DMÖ     (4.2.33.Ç) → H36.0 / E1x.3 / "diyabetik maküler ödem"
  belirsiz          → endikasyon atomu KE (ortak şartlar yine değerlendirilir)

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ G1(göz hast. uzman hekimi reçete)
          ∧ G2(sağlık kurulu raporu + heyette ≥3 göz uzmanı)
          ∧ G3(endikasyon — AMD/RVO/PM/DMÖ)
          [∧ B1..B6 bilgi/şartlı — matematik dışı, manuel doğrulama]

  Gating atom YOK → UYGUN_DEĞİL. Gating KE (yalnız şartlı) → SARTLI_UYGUN;
  aksi → ŞÜPHELİ. Hepsi VAR → UYGUN. Sessizlik = örtük kabul YASAK
  (CLAUDE.md §2.5): rapor hiç yoksa G2 = YOK; tespit edilemiyorsa KE.

Ana entrypoint: ``goz_antivegf_kontrol_4_2_33(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç sınıfı listeleri (etken madde + ticari ad — norm_tr_upper / ASCII)
# ═══════════════════════════════════════════════════════════════════════

RANIBIZUMAB: Set[str] = {
    'RANIBIZUMAB', 'RANIBIZUMABE', 'LUCENTIS', 'RANIVISIO', 'BYOOVIZ',
    'XIMLUCI', 'RANIEYE',
}
AFLIBERSEPT: Set[str] = {
    'AFLIBERSEPT', 'AFLIBERCEPT', 'EYLEA', 'AFLIVEX', 'AFLIBETA',
}
VERTEPORFIN: Set[str] = {
    'VERTEPORFIN', 'VERTEPORFINE', 'VISUDYNE',
}
# Deksametazon intravitreal implant — yalnız implant formu (Ozurdex). Düz
# deksametazon göz damlası / sistemik deksametazon KAPSAM DIŞIDIR; bu yüzden
# marka (OZURDEX) ya da etken + "implant/intravitreal" birlikte aranır.
DEKSAMETAZON_IMPLANT_MARKA: Set[str] = {'OZURDEX'}
DEKSAMETAZON_ETKEN: Set[str] = {'DEKSAMETAZON', 'DEXAMETHASONE', 'DEKSAMETAZONE'}
IMPLANT_ISARET: Set[str] = {'IMPLANT', 'INTRAVITREAL', 'INTRAOKULER'}

# Kapsam dışı — günübirlik (hastane uygular)
BEVACIZUMAB: Set[str] = {
    'BEVACIZUMAB', 'BEVASIZUMAB', 'BEVACIZUMABE', 'ALTUZAN', 'AVASTIN',
    'ZIRABEV', 'MVASI', 'AYBINTIO', 'ABEVMY', 'ONBEVZI', 'OYAVAS', 'VEGZELMA',
}

# Reçetede görülebilecek tüm madde anti-VEGF/ilgili (B5 kombine yasağı için)
TUM_GOZ_ANTIVEGF: Set[str] = (
    RANIBIZUMAB | AFLIBERSEPT | VERTEPORFIN | BEVACIZUMAB
    | DEKSAMETAZON_IMPLANT_MARKA | {'BROLUCIZUMAB', 'BEOVU', 'FARICIMAB', 'VABYSMO'}
)

# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower ile alt-string eşleşmesi)
# ═══════════════════════════════════════════════════════════════════════
GOZ_BRANSLAR: List[str] = ['goz hastalik', 'goz hast', 'oftalmol']

# ═══════════════════════════════════════════════════════════════════════
# Endikasyon ICD / teşhis lafzı sinyalleri
# ═══════════════════════════════════════════════════════════════════════
ENDIKASYON_TANIM: Dict[str, Dict[str, object]] = {
    'AMD': {
        'ad': 'Yaş tip yaşa bağlı makula dejenerasyonu (4.2.33.A)',
        'icd_prefix': ['H35.3'],
        'lafiz': ['yas tip', 'neovaskuler amd', 'yasa bagli makula',
                  'yasa bagli makuler', 'islak tip', 'eksudatif amd',
                  'koroid neovask'],  # AMD-KNV
    },
    'RVO': {
        'ad': 'Retina ven tıkanıklığı / santral retinal ven tıkanıklığı (4.2.33.B)',
        'icd_prefix': ['H34.8', 'H34.1'],
        'lafiz': ['ven tikanik', 'retinal ven', 'santral retinal ven',
                  'dal ven tikanik', 'rvo', 'crvo', 'brvo'],
    },
    'PM': {
        'ad': 'Patolojik miyopiye bağlı koroidal neovaskülarizasyon (4.2.33.C)',
        'icd_prefix': ['H44.2'],
        'lafiz': ['patolojik miyop', 'dejeneratif miyop', 'miyopiye bagli',
                  'pm knv', 'miyopik koroidal'],
    },
    'DMO': {
        'ad': 'Diyabetik maküler ödem (4.2.33.Ç)',
        'icd_prefix': ['H36.0'],
        'lafiz': ['diyabetik makuler odem', 'diyabetik makula odem',
                  'diyabetik makuler', 'dmo', 'diyabetik makulopati'],
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    """İlaç adı + etken madde birleşik (dispatcher eşleşmesi için, ASCII-upper)."""
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _iceriyor(metin_upper: str, kume: Set[str]) -> bool:
    """metin_upper (zaten norm_tr_upper edilmiş) içinde kümeden biri geçiyor mu?"""
    return any(norm_tr_upper(k) in metin_upper for k in kume)


def _rapor_metni(ilac_sonuc: Dict) -> str:
    """Rapor + reçete açıklama birleşik metni (norm_tr_lower — regex için)."""
    parcalar: List[str] = []
    for anahtar in ('rapor_metni', 'tum_metin', 'rapor_kodu_aciklama',
                    'rap_ack', 'rap_tesh', 'rec_tesh'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
    for anahtar in ('rapor_aciklamalari', 'recete_aciklamalari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
    return norm_tr_lower(' '.join(parcalar))


def _teshis_metinleri(ilac_sonuc: Dict) -> Tuple[str, str]:
    """(ICD/teşhis birleşik ASCII-upper, teşhis lafzı ASCII-lower)."""
    parcalar: List[str] = []
    for anahtar in ('rec_tesh', 'rap_tesh'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
    for anahtar in ('recete_teshisleri', 'rapor_teshisleri'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
            parcalar.append(str(v))
    birlesik = ' '.join(parcalar)
    return norm_tr_upper(birlesik), norm_tr_lower(birlesik)


def _brans_l(brans: Optional[str]) -> str:
    return norm_tr_lower(brans or '')


def _brans_listede(brans: Optional[str], anahtarlar: List[str]) -> bool:
    bl = _brans_l(brans)
    if not bl:
        return False
    return any(a in bl for a in anahtarlar)


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER — ilaç sınıfı
# ═══════════════════════════════════════════════════════════════════════

def _ilac_sinifi(ilac_sonuc: Dict) -> Optional[str]:
    """Reçete kalemi anti-VEGF/ilgili hangi sınıfa düşer?

    Returns: 'RANIBIZUMAB' | 'AFLIBERSEPT' | 'DEKSAMETAZON_IMPLANT' |
             'VERTEPORFIN' | 'BEVACIZUMAB' (kapsam dışı/günübirlik) | None.
    """
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    m = _arama_metni(ilac_sonuc)

    # Bevacizumab — günübirlik (kapsam dışı işaretle)
    if atc.startswith('L01XC07') or atc.startswith('L01FG01') \
            or _iceriyor(m, BEVACIZUMAB):
        return 'BEVACIZUMAB'
    if atc.startswith('S01LA04') or _iceriyor(m, RANIBIZUMAB):
        return 'RANIBIZUMAB'
    if atc.startswith('S01LA05') or _iceriyor(m, AFLIBERSEPT):
        return 'AFLIBERSEPT'
    if atc.startswith('S01LA01') or _iceriyor(m, VERTEPORFIN):
        return 'VERTEPORFIN'
    # Deksametazon — yalnız intravitreal implant (Ozurdex). Damla/sistemik hariç.
    if _iceriyor(m, DEKSAMETAZON_IMPLANT_MARKA):
        return 'DEKSAMETAZON_IMPLANT'
    if _iceriyor(m, DEKSAMETAZON_ETKEN) and _iceriyor(m, IMPLANT_ISARET):
        return 'DEKSAMETAZON_IMPLANT'
    return None


def goz_antivegf_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """GUI kategori eşlemesi için: kapsanan bir göz ilacı mı?

    Returns sınıf adı (kapsam içi + 'BEVACIZUMAB') veya None.
    """
    return _ilac_sinifi(ilac_sonuc)


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER — endikasyon
# ═══════════════════════════════════════════════════════════════════════

def _endikasyon_belirle(ilac_sonuc: Dict) -> Tuple[Optional[str], str]:
    """ICD + teşhis lafzından endikasyon yolağı belirle.

    Returns: ('AMD'|'RVO'|'PM'|'DMO'|None, neden_str).
    """
    icd_upper, lafiz_lower = _teshis_metinleri(ilac_sonuc)

    for kod, tanim in ENDIKASYON_TANIM.items():
        # ICD önek eşleşmesi (kelime sınırında, nokta toleranslı)
        for pref in tanim['icd_prefix']:  # type: ignore[index]
            pref_u = pref.upper()
            # H35.3 → "H35.3" veya "H35.31"/"H35.32" alt kodları
            patt = r'\b' + re.escape(pref_u).replace(r'\.', r'\.') + r'(\d|\b)'
            if re.search(patt, icd_upper):
                return kod, f"ICD {pref} eşleşti ({tanim['ad']})"
    # Lafız eşleşmesi (ICD bulunamazsa)
    for kod, tanim in ENDIKASYON_TANIM.items():
        for kelime in tanim['lafiz']:  # type: ignore[index]
            if kelime in lafiz_lower:
                return kod, f"Teşhis lafzı '{kelime}' ({tanim['ad']})"
    return None, "Endikasyon ICD/teşhisi okunamadı (AMD/RVO/PM/DMÖ)"


# ═══════════════════════════════════════════════════════════════════════
# GATING ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

def atom_goz_uzmani_recete(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """G1: reçeteyi düzenleyen GÖZ HASTALIKLARI uzman hekimi mi?"""
    brans = (ilac_sonuc.get('doktor_uzmanligi') or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden göz hastalıkları uzmanı',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel doğrulama',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, GOZ_BRANSLAR):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Göz hastalıkları uzman hekimi',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='4.2.33: anti-VEGF yalnız göz hastalıkları uzman '
                           'hekimlerince reçete edilebilir',
                     kaynak='hekim_brans', grup=grup)


def atom_sk_3goz_uzmani(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """G2: Sağlık kurulu raporu + heyette ≥3 göz hastalıkları uzmanı (katı).

    Sessizlik = örtük kabul YASAK:
      - rapor hiç yok → YOK (rapor zorunlu)
      - heyet bilgisi yok → KE (SK doğrulanamadı, manuel)
      - heyette ≥3 göz uzmanı → VAR
      - heyet tam (branşlar dolu) ama göz uzmanı <3 → YOK
      - heyet kısmen eksik branşlı → KE (manuel)
      - rapor "uzman hekim raporu" + heyet ≤1 → YOK (SK değil)
    """
    rapor_turu = norm_tr_lower(ilac_sonuc.get('rapor_turu') or
                               ilac_sonuc.get('rapor_turu_adi') or '')
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not isinstance(heyet, (list, tuple)):
        heyet = []
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or
                   ilac_sonuc.get('rap_tak_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rapor_turu or heyet)

    if not rapor_var:
        return SartSonuc(ad='Sağlık kurulu raporu (≥3 göz uzmanı)',
                         durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor bulunamadı — 4.2.33 sağlık '
                               'kurulu raporu zorunlu',
                         kaynak='rapor', grup=grup)

    uzman_tek = ('uzman' in rapor_turu) and ('kurul' not in rapor_turu)
    if uzman_tek and len(heyet) <= 1:
        return SartSonuc(ad='Sağlık kurulu raporu (≥3 göz uzmanı)',
                         durum=SartDurumu.YOK,
                         neden='Rapor "uzman hekim raporu" — 4.2.33 diğer etkin '
                               'maddeler için 3 göz uzmanlı SK raporu ister',
                         kaynak='rapor_turu+heyet', grup=grup)

    if not heyet:
        return SartSonuc(ad='Sağlık kurulu raporu (≥3 göz uzmanı)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor heyeti bilgisi yok — SK + 3 göz uzmanı '
                               'manuel doğrulanmalı',
                         kaynak='heyet', grup=grup, sartli_atom=True)

    goz_uzmanlari = [h.get('brans') for h in heyet
                     if _brans_listede(h.get('brans'), GOZ_BRANSLAR)]
    goz_n = len(goz_uzmanlari)
    bransli_n = len([h for h in heyet if (h.get('brans') or '').strip()])
    heyet_tam = bransli_n == len(heyet)  # tüm üyelerin branşı dolu

    if goz_n >= 3:
        return SartSonuc(ad='Sağlık kurulu raporu (≥3 göz uzmanı)',
                         durum=SartDurumu.VAR,
                         neden=f'Heyette {goz_n} göz hastalıkları uzmanı (SK raporu)',
                         kaynak='heyet', grup=grup)
    if heyet_tam:
        return SartSonuc(ad='Sağlık kurulu raporu (≥3 göz uzmanı)',
                         durum=SartDurumu.YOK,
                         neden=f'Heyette yalnız {goz_n} göz uzmanı — 4.2.33 en az '
                               f'3 göz hastalıkları uzmanı ister (heyet {len(heyet)} kişi)',
                         kaynak='heyet', grup=grup)
    return SartSonuc(ad='Sağlık kurulu raporu (≥3 göz uzmanı)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Heyette {goz_n} göz uzmanı tespit edildi ama bazı '
                           f'üyelerin branşı eksik — manuel doğrula',
                     kaynak='heyet', grup=grup, sartli_atom=True)


def atom_endikasyon(endikasyon: Optional[str], neden: str, grup: str) -> SartSonuc:
    """G3: endikasyon AMD/RVO/PM/DMÖ tespit edildi mi?"""
    if endikasyon:
        return SartSonuc(ad=f'Endikasyon: {endikasyon}', durum=SartDurumu.VAR,
                         neden=neden, kaynak='ICD/teşhis', grup=grup)
    return SartSonuc(ad='Endikasyon (AMD/RVO/PM/DMÖ)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=neden + ' — manuel doğrulanmalı',
                     kaynak='ICD/teşhis', grup=grup, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# BİLGİ / ŞARTLI ATOMLAR (matematiği bozmaz — '(bilgi)' suffix)
# ═══════════════════════════════════════════════════════════════════════

def atom_ucuncu_basamak(grup: str) -> SartSonuc:
    """B1 (bilgi): 3. basamak SHS şartı. Tesis basamağı güvenilir
    belirlenemediğinden manuel doğrulama notu."""
    return SartSonuc(ad='3. basamak sağlık hizmeti sunucusu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Ranibizumab/aflibersept/deksametazon implant/verteporfin '
                           '3. basamakta uygulanır/reçetelenir — tesis basamağı '
                           'manuel doğrulanmalı',
                     kaynak='tesis', grup=grup, sartli_atom=True)


def atom_yukleme_dozu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """B2 (bilgi): yükleme dozu tamamlanması / kaçıncı doz raporda belirtilmeli."""
    metin = _rapor_metni(ilac_sonuc)
    isaret = ('yukleme' in metin or 'yukleme dozu' in metin or
              re.search(r'\b[1-9]\s*\.?\s*doz\b', metin) or 'idame' in metin or
              'baslangic' in metin)
    if isaret:
        return SartSonuc(ad='Yükleme dozu / kaçıncı doz (rapor)',
                         durum=SartDurumu.VAR,
                         neden='Raporda yükleme/doz/başlangıç-idame ibaresi bulundu '
                               '— kaçıncı doz manuel teyit',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Yükleme dozu / kaçıncı doz (rapor)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='İlk tedavide yükleme dozları tamamlanmalı; reçete/raporda '
                           'kaçıncı doz belirtilmeli — manuel doğrulama',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_baslama_esasi(sinif: str, endikasyon: Optional[str], grup: str) -> SartSonuc:
    """B3 (bilgi): tedaviye bevacizumab ile başlanır esası (A/B/C/Ç)."""
    yol = {'AMD': '4.2.33.A', 'RVO': '4.2.33.B', 'PM': '4.2.33.C',
           'DMO': '4.2.33.Ç'}.get(endikasyon or '', '4.2.33')
    return SartSonuc(ad='Bevacizumab ile başlama esası',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'{yol}: tedaviye bevacizumab ile başlanır; ranibizumab/'
                           f'aflibersept cevapsızlık/yetersiz cevap (OKT dokümante) '
                           f'sonrası geçilir — ilaç geçmişi manuel doğrulanmalı',
                     kaynak='ilac_gecmisi', grup=grup, sartli_atom=True)


def atom_yanit_degerlendirme(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """B4 (bilgi): tedaviye yanıt (OKT fovea ≤250µm / görme keskinliği)."""
    metin = _rapor_metni(ilac_sonuc)
    isaret = ('okt' in metin or 'fovea' in metin or 'gorme keskinlig' in metin or
              'mikron' in metin or 'foveal' in metin)
    if isaret:
        return SartSonuc(ad='Tedaviye yanıt değerlendirmesi (OKT/görme)',
                         durum=SartDurumu.VAR,
                         neden='Raporda OKT/fovea/görme keskinliği ibaresi var — '
                               'yanıt kriterleri manuel teyit',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Tedaviye yanıt değerlendirmesi (OKT/görme)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='İdame/yükleme: görme keskinliği + OKT fovea kalınlığı '
                           'değerlendirmesi her raporda belirtilmeli — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_kombine_ayni_goz(ilac_sonuc: Dict, grup: str) -> Optional[SartSonuc]:
    """B5 (bilgi, koşullu): aynı reçetede başka bir anti-VEGF varsa aynı gözde
    kombine kullanım yasağı manuel doğrulanmalı (farklı göz serbest)."""
    diger = ilac_sonuc.get('recete_ilaclari') or []
    adlar: List[str] = []
    for d in diger:
        if isinstance(d, dict):
            ad = d.get('ad') or ''
        else:
            ad = str(d)
        if ad:
            adlar.append(norm_tr_upper(ad))
    baska = [a for a in adlar if any(norm_tr_upper(k) in a for k in TUM_GOZ_ANTIVEGF)]
    if not baska:
        return None
    return SartSonuc(ad='Aynı göz kombine kullanım yasağı',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Aynı reçetede başka anti-VEGF var — aynı gözde kombine '
                           'kullanılırsa karşılanmaz (farklı göz serbest), manuel doğrula',
                     kaynak='recete_kalemleri', grup=grup, sartli_atom=True)


def atom_deksametazon_limit(grup: str) -> SartSonuc:
    """B6 (bilgi): deksametazon implant yılda max 4 / arada ≥3 ay."""
    return SartSonuc(ad='Deksametazon implant: yılda max 4 / arada ≥3 ay',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Deksametazon implant anti-VEGF sonrası en erken 1 ay, '
                           'yılda en fazla 4 kez, aynı göze ardışık uygulamalar arası '
                           '≥3 ay — uygulama tarihçesi manuel doğrulanmalı',
                     kaynak='ilac_gecmisi', grup=grup, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# KONTROL — gating + bilgi atomlarını topla
# ═══════════════════════════════════════════════════════════════════════

def _kontrol_sartlari(ilac_sonuc: Dict, sinif: str,
                      endikasyon: Optional[str], end_neden: str) -> List[SartSonuc]:
    sartlar: List[SartSonuc] = []
    # Gating (AND)
    sartlar.append(atom_goz_uzmani_recete(
        ilac_sonuc, grup='(1) Reçete eden göz uzmanı'))
    sartlar.append(atom_sk_3goz_uzmani(
        ilac_sonuc, grup='(a) Sağlık kurulu raporu (3 göz uzmanı)'))
    sartlar.append(atom_endikasyon(
        endikasyon, end_neden, grup='Endikasyon (AMD/RVO/PM/DMÖ)'))
    # Bilgi / şartlı
    sartlar.append(atom_ucuncu_basamak(grup='3. basamak (bilgi)'))
    sartlar.append(atom_yukleme_dozu(ilac_sonuc, grup='Yükleme dozu (bilgi)'))
    sartlar.append(atom_baslama_esasi(sinif, endikasyon, grup='Başlama esası (bilgi)'))
    sartlar.append(atom_yanit_degerlendirme(ilac_sonuc, grup='Yanıt değerlendirme (bilgi)'))
    b5 = atom_kombine_ayni_goz(ilac_sonuc, grup='Kombine yasağı (bilgi)')
    if b5:
        sartlar.append(b5)
    if sinif == 'DEKSAMETAZON_IMPLANT':
        sartlar.append(atom_deksametazon_limit(grup='Deksametazon limiti (bilgi)'))
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (grup + veya_grubu + şartlı atom mantığı)
# ═══════════════════════════════════════════════════════════════════════

def _grup_degerlendir(gs: List[SartSonuc]) -> Tuple[str, bool]:
    """Bir grubu değerlendir → ('var'|'yok'|'ke', sadece_sartli_ke)."""
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
    # AND
    if any(d == SartDurumu.YOK for d in durumlar):
        return ('yok', False)
    if all(d == SartDurumu.VAR for d in durumlar):
        return ('var', False)
    return ('ke', ke_sartli)


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    """SartSonuc listesinden genel sonuç (CLAUDE.md disiplini).

    '(bilgi)' grupları matematik dışı. Bir grup YOK → UYGUN_DEGIL.
    KE varsa: hepsi şartlı atom KE ise SARTLI_UYGUN, değilse ŞÜPHELİ.
    """
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


def _mesaj_uret(sonuc: KontrolSonucu, sinif: str, endikasyon: Optional[str],
                sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI
          and '(bilgi)' not in (s.grup or '')]
    sinif_ad = SINIF_AD.get(sinif, sinif)
    end_ad = endikasyon or 'endikasyon belirsiz'
    parcalar = [f"SUT 4.2.33 / {sinif_ad} / {end_ad}"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — göz uzmanı reçete + 3 göz uzmanlı SK raporu + endikasyon")
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f"ŞARTLI UYGUN — hesaplanabilir şartlar VAR; "
                        f"{len(ke)} şart manuel doğrulama gerektiriyor")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append("UYGUN DEĞİL — " + '; '.join(s.ad for s in yok[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f"ŞÜPHELİ — {len(ke)} şart kontrol edilemedi")
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

SINIF_AD: Dict[str, str] = {
    'RANIBIZUMAB': 'Ranibizumab',
    'AFLIBERSEPT': 'Aflibersept',
    'DEKSAMETAZON_IMPLANT': 'Deksametazon intravitreal implant',
    'VERTEPORFIN': 'Verteporfin',
    'BEVACIZUMAB': 'Bevacizumab (günübirlik)',
}

KAPSAM_ICI = {'RANIBIZUMAB', 'AFLIBERSEPT', 'DEKSAMETAZON_IMPLANT', 'VERTEPORFIN'}


def goz_antivegf_kontrol_4_2_33(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.33 anti-VEGF ana kontrol fonksiyonu.

    Akış:
      1. İlaç sınıfı (dispatcher) — kapsam dışı/bevacizumab → ATLANDI
      2. Endikasyon dispatcher (ICD/teşhis) — AMD/RVO/PM/DMÖ
      3. Gating + bilgi atomları → genel sonuç
    """
    sinif = _ilac_sinifi(ilac_sonuc)
    if sinif is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.33 kapsamı dışı — anti-VEGF/ilgili göz ilacı '
                  'tespit edilemedi',
            sut_kurali='SUT 4.2.33')
    if sinif == 'BEVACIZUMAB':
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Bevacizumab GÜNÜBİRLİK tedavi kapsamında — hastanede uygulanır, '
                  'eczane teslimi değildir (4.2.33 ayakta temin kapsamı dışı)',
            sut_kurali='SUT 4.2.33',
            detaylar={'sinif': 'BEVACIZUMAB', 'gunubirlik': True})

    endikasyon, end_neden = _endikasyon_belirle(ilac_sonuc)
    sartlar = _kontrol_sartlari(ilac_sonuc, sinif, endikasyon, end_neden)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sinif, endikasyon, sartlar)
    alt_madde = {'AMD': '4.2.33.A', 'RVO': '4.2.33.B', 'PM': '4.2.33.C',
                 'DMO': '4.2.33.Ç'}.get(endikasyon or '', '4.2.33')
    return KontrolRaporu(
        sonuc=sonuc,
        mesaj=mesaj,
        sut_kurali=f"SUT {alt_madde} / {SINIF_AD[sinif]}",
        sartlar=sartlar,
        detaylar={'sinif': sinif, 'sinif_ad': SINIF_AD[sinif],
                  'endikasyon': endikasyon})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (CLAUDE.md §7.7 — ≥10 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _heyet(*branslar: str) -> List[Dict]:
    return [{'ad': f'Dr {i}', 'brans': b, 'tckn': ''} for i, b in enumerate(branslar)]


def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        # 1) Ranibizumab AMD tam UYGUN: göz uzmanı + 3 göz uzmanlı SK + H35.3
        ("Ranibizumab/AMD tam UYGUN", {
            'ilac_adi': 'LUCENTIS', 'etkin_madde': 'RANIBIZUMAB', 'atc': 'S01LA04',
            'doktor_uzmanligi': 'Göz Hastalıkları', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'rapor_kodu': '33.01', 'rec_tesh': 'H35.3 Maküla dejenerasyonu',
            'heyet_doktorlari': _heyet('Göz Hastalıkları', 'Göz Hastalıkları',
                                        'Göz Hastalıkları'),
        }, KontrolSonucu.UYGUN),
        # 2) Aflibersept DMÖ UYGUN: lafız ile endikasyon
        ("Aflibersept/DMÖ UYGUN (lafız)", {
            'ilac_adi': 'EYLEA', 'etkin_madde': 'AFLIBERSEPT', 'atc': 'S01LA05',
            'doktor_uzmanligi': 'Oftalmoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'rap_tesh': 'Diyabetik maküler ödem',
            'heyet_doktorlari': _heyet('Göz Hastalıkları', 'Göz Hastalıkları',
                                        'Göz Hastalıkları', 'İç Hastalıkları'),
        }, KontrolSonucu.UYGUN),
        # 3) UYGUN DEĞİL: reçete eden göz uzmanı değil
        ("UYGUN DEĞİL (reçete eden dahiliye)", {
            'ilac_adi': 'EYLEA', 'etkin_madde': 'AFLIBERSEPT', 'atc': 'S01LA05',
            'doktor_uzmanligi': 'İç Hastalıkları', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'rec_tesh': 'H35.3',
            'heyet_doktorlari': _heyet('Göz Hastalıkları', 'Göz Hastalıkları',
                                        'Göz Hastalıkları'),
        }, KontrolSonucu.UYGUN_DEGIL),
        # 4) UYGUN DEĞİL: heyette <3 göz uzmanı (tam heyet)
        ("UYGUN DEĞİL (heyet 2 göz uzmanı)", {
            'ilac_adi': 'LUCENTIS', 'etkin_madde': 'RANIBIZUMAB', 'atc': 'S01LA04',
            'doktor_uzmanligi': 'Göz Hastalıkları', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'rec_tesh': 'H34.8',
            'heyet_doktorlari': _heyet('Göz Hastalıkları', 'Göz Hastalıkları',
                                        'Dahiliye'),
        }, KontrolSonucu.UYGUN_DEGIL),
        # 5) UYGUN DEĞİL: rapor "uzman hekim raporu" (SK değil)
        ("UYGUN DEĞİL (uzman hekim raporu)", {
            'ilac_adi': 'EYLEA', 'etkin_madde': 'AFLIBERSEPT', 'atc': 'S01LA05',
            'doktor_uzmanligi': 'Göz Hastalıkları', 'rapor_turu': 'Uzman Hekim Raporu',
            'rec_tesh': 'H35.3', 'heyet_doktorlari': _heyet('Göz Hastalıkları'),
        }, KontrolSonucu.UYGUN_DEGIL),
        # 6) UYGUN DEĞİL: rapor hiç yok
        ("UYGUN DEĞİL (rapor yok)", {
            'ilac_adi': 'LUCENTIS', 'etkin_madde': 'RANIBIZUMAB', 'atc': 'S01LA04',
            'doktor_uzmanligi': 'Göz Hastalıkları', 'rec_tesh': 'H35.3',
        }, KontrolSonucu.UYGUN_DEGIL),
        # 7) ŞARTLI UYGUN: heyet bilgisi yok (SK doğrulanamadı) + endikasyon var
        ("ŞARTLI (heyet bilgisi yok)", {
            'ilac_adi': 'LUCENTIS', 'etkin_madde': 'RANIBIZUMAB', 'atc': 'S01LA04',
            'doktor_uzmanligi': 'Göz Hastalıkları', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'rapor_kodu': '33.01', 'rec_tesh': 'H35.3',
        }, KontrolSonucu.SARTLI_UYGUN),
        # 8) ŞARTLI UYGUN: endikasyon belirsiz ama gating VAR
        ("ŞARTLI (endikasyon belirsiz)", {
            'ilac_adi': 'EYLEA', 'etkin_madde': 'AFLIBERSEPT', 'atc': 'S01LA05',
            'doktor_uzmanligi': 'Göz Hastalıkları', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'rec_tesh': 'Z00.0',
            'heyet_doktorlari': _heyet('Göz Hastalıkları', 'Göz Hastalıkları',
                                        'Göz Hastalıkları'),
        }, KontrolSonucu.SARTLI_UYGUN),
        # 9) ŞÜPHELİ: branş bilinmiyor (KE şartlı) + heyet yok (KE şartlı) →
        #    aslında hepsi şartlı KE → SARTLI. Branşı tamamen boş + rapor kodu yok
        #    senaryosunu ŞÜPHELİ yapmak için rapor da yok → G2 YOK olur. Bunun
        #    yerine: branş boş, SK+heyet VAR, endikasyon VAR → yalnız G1 KE(şartlı)
        ("ŞARTLI (branş bilinmiyor)", {
            'ilac_adi': 'LUCENTIS', 'etkin_madde': 'RANIBIZUMAB', 'atc': 'S01LA04',
            'doktor_uzmanligi': '', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'rec_tesh': 'H35.3',
            'heyet_doktorlari': _heyet('Göz Hastalıkları', 'Göz Hastalıkları',
                                        'Göz Hastalıkları'),
        }, KontrolSonucu.SARTLI_UYGUN),
        # 10) Deksametazon implant (Ozurdex) RVO UYGUN
        ("Deksametazon implant/RVO UYGUN", {
            'ilac_adi': 'OZURDEX', 'etkin_madde': 'DEKSAMETAZON', 'atc': 'S01BA01',
            'doktor_uzmanligi': 'Göz Hastalıkları', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'rap_tesh': 'H34.8 retina ven tıkanıklığı',
            'heyet_doktorlari': _heyet('Göz Hastalıkları', 'Göz Hastalıkları',
                                        'Göz Hastalıkları'),
        }, KontrolSonucu.UYGUN),
        # 11) Bevacizumab → ATLANDI (günübirlik)
        ("Bevacizumab ATLANDI (günübirlik)", {
            'ilac_adi': 'ALTUZAN', 'etkin_madde': 'BEVACIZUMAB', 'atc': 'L01XC07',
            'doktor_uzmanligi': 'Göz Hastalıkları', 'rec_tesh': 'H35.3',
        }, KontrolSonucu.ATLANDI),
        # 12) Düz deksametazon göz damlası → kapsam dışı (implant değil) ATLANDI
        ("Deksametazon damla → kapsam dışı", {
            'ilac_adi': 'DEXASINE', 'etkin_madde': 'DEKSAMETAZON', 'atc': 'S01BA01',
            'doktor_uzmanligi': 'Göz Hastalıkları', 'rec_tesh': 'H10.9',
        }, KontrolSonucu.ATLANDI),
        # 13) Kapsam dışı (parasetamol)
        ("Kapsam dışı (parasetamol)", {
            'ilac_adi': 'PAROL', 'etkin_madde': 'PARASETAMOL', 'atc': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        # 14) Verteporfin PM-KNV UYGUN
        ("Verteporfin/PM UYGUN", {
            'ilac_adi': 'VISUDYNE', 'etkin_madde': 'VERTEPORFIN', 'atc': 'S01LA01',
            'doktor_uzmanligi': 'Göz Hastalıkları', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'rap_tesh': 'H44.2 patolojik miyopi koroidal neovaskülarizasyon',
            'heyet_doktorlari': _heyet('Göz Hastalıkları', 'Göz Hastalıkları',
                                        'Göz Hastalıkları'),
        }, KontrolSonucu.UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.33 anti-VEGF — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = goz_antivegf_kontrol_4_2_33(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        isaret = "✓" if ok else "✗"
        print(f"{isaret} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 60)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
