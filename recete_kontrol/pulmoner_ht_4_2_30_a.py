# -*- coding: utf-8 -*-
"""SUT 4.2.30.A — Pulmoner arteriyel hipertansiyonda (DSÖ Grup I PAH) ilaç
kullanım ilkeleri.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:7847-7880`` (mevzuat.gov.tr,
MevzuatNo=17229). Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md
``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
ETKEN MADDE → İLAÇ SINIFI (dispatcher)
═══════════════════════════════════════════════════════════════════════════
  ERA         → bosentan, masitentan, ambrisentan  (madde 6: ikisi birlikte YASAK)
  PDE5        → sildenafil, tadalafil  (madde 7; ED kullanımıyla ATC çakışır →
                yalnız PAH bağlamı varsa kontrol edilir, yoksa ATLANDI)
  SGC         → riociguat  (madde 7)
  PROSTANOID  → iloprost (inhaler), epoprostenol, treprostinil  (madde 8)
  IP          → seleksipag  (madde 5: yalnız kombinasyonda; madde 8)

═══════════════════════════════════════════════════════════════════════════
ORTAK ŞARTLAR (her sınıfta — AND)
═══════════════════════════════════════════════════════════════════════════
  • E1  DSÖ Grup I PAH tanısı (ICD I27.0 / "pulmoner arteriyel hipertansiyon")
  • E2  Sağ kalp kateterizasyonu ile doğrulanmış      (başlangıç — sessiz→KE+şartlı)
  • E3  Vazoreaktivite testi negatif                  (başlangıç — sessiz→KE+şartlı)
  • E4  Pulmoner arter kama basıncı (PCWP) < 15 mmHg  (başlangıç — sessiz→KE+şartlı)
  • NYHA fonksiyonel sınıfı (II/III/IV)               (sessiz→KE+şartlı; I→YOK)
  • F1  SK raporu VAR
  • F2  Üçüncü basamak sağlık tesisi                  (tam-kat → sessiz→KE+şartlı)
  • F3  Heyette ≥1: kardiyoloji ∨ KDC ∨ göğüs hast. ∨ çocuk kardiyolojisi
  • F4  Reçeteyi bu branşlardan biri düzenlemiş
  • F5  Rapor 3 ay süreli  (bilgi — hesaba katılmaz)

Kullanıcı kararı (2026-06-04): başlangıç tanı kriterleri (E2/E3/E4/NYHA) raporda
bulunamazsa madde-2 devam raporu olabileceğinden ``KONTROL_EDILEMEDI +
sartli_atom`` → genel sonuç ŞÜPHELİ/ŞARTLI (hard-fail etmez, örtük kabul de yok).

═══════════════════════════════════════════════════════════════════════════
İLAÇ-SINIFI ÖZEL ŞARTLAR
═══════════════════════════════════════════════════════════════════════════
  • (1-c) Epoprostenol  → yalnız NYHA III∨IV;  (9) böbrek diyalizi endikasyonu YOK
  • (1-ç) Treprostinil  → yalnız NYHA III ∧ (idiyopatik∨kalıtsal)
  • (5)   Seleksipag    → ERA ve/veya PDE5i ile kombine ∧ "yetersiz yanıt" ibaresi
  • (10)  Bosentan 32mg → <30 kg pediatrik ∨ yutma güçlüğü  (bilgi/KE — 32mg ise)

═══════════════════════════════════════════════════════════════════════════
KOMBİNASYON YASAKLARI (reçetedeki diğer PAH ilaçlarından hesaplanır)
═══════════════════════════════════════════════════════════════════════════
  • (6) C6  ≥2 ERA birlikte → YOK                 (ERA ilaçlarına eklenir)
  • (7) C7  {sildenafil,riociguat,tadalafil}'tan ≥2 → YOK  (PDE5/SGC'ye eklenir)
  • (8) C8  {iloprost-inh,epoprostenol,treprostinil,seleksipag}'tan ≥2 → YOK
            (PROSTANOID/IP ilaçlarına eklenir)
  • (1-a) İKİLİ KOMBİNASYON KISITI (tüm sınıflara eklenir):
        mono → her NYHA serbest; NYHA IV → ikili/üçlü serbest;
        NYHA II/III ikili → yetişkin: yalnız (ambrisentan∨masitentan)+
        (tadalafil∨sildenafil); 1-17 yaş: yalnız bosentan+sildenafil;
        NYHA II/III üçlü → YOK. NYHA/yaş bilinmiyorsa KE+şartlı.

Ana entrypoint: ``pulmoner_ht_kontrol_4_2_30_a(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İLAÇ TANIMLARI (etken + ticari ad). ATC zaman içinde değişebildiğinden
# etken/ad metni esastır.
# ═══════════════════════════════════════════════════════════════════════

DRUG_DEFS: Dict[str, Tuple[Set[str], Set[str]]] = {
    'BOSENTAN': (
        {'BOSENTAN'},
        {'TRACLEER', 'STAYVEER', 'BOSENAS', 'BOSWELL', 'BOSENTANAS'},
    ),
    'MASITENTAN': (
        {'MASITENTAN', 'MACITENTAN'},
        {'OPSUMIT'},
    ),
    'AMBRISENTAN': (
        {'AMBRISENTAN'},
        {'VOLIBRIS'},
    ),
    'SILDENAFIL': (
        {'SILDENAFIL'},
        {'REVATIO'},  # PAH markası; ED markaları (Viagra/Degra) bağlam ile elenir
    ),
    'TADALAFIL': (
        {'TADALAFIL'},
        {'ADCIRCA'},  # PAH markası; ED markası (Cialis) bağlam ile elenir
    ),
    'RIOCIGUAT': (
        {'RIOCIGUAT', 'RIOSIGUAT'},
        {'ADEMPAS'},
    ),
    'ILOPROST': (
        {'ILOPROST'},
        {'VENTAVIS'},  # inhaler formu
    ),
    'EPOPROSTENOL': (
        {'EPOPROSTENOL'},
        {'FLOLAN', 'VELETRI'},
    ),
    'TREPROSTINIL': (
        {'TREPROSTINIL'},
        {'REMODULIN', 'TYVASO'},
    ),
    'SELEKSIPAG': (
        {'SELEKSIPAG', 'SELEXIPAG'},
        {'UPTRAVI'},
    ),
}

# İlaç anahtarı → SUT ilaç sınıfı (yolak)
DRUG_KEY_TO_SINIF = {
    'BOSENTAN': 'ERA', 'MASITENTAN': 'ERA', 'AMBRISENTAN': 'ERA',
    'SILDENAFIL': 'PDE5', 'TADALAFIL': 'PDE5',
    'RIOCIGUAT': 'SGC',
    'ILOPROST': 'PROSTANOID', 'EPOPROSTENOL': 'PROSTANOID',
    'TREPROSTINIL': 'PROSTANOID',
    'SELEKSIPAG': 'IP',
}

# ATC önekleri (PAH-spesifik). ED ile çakışan G04BE03/08 dispatch'te
# kullanılmaz — sildenafil/tadalafil yalnız etken/ad + PAH bağlamı ile girer.
PAH_ATC_PREFIX = (
    'C02KX01',  # bosentan
    'C02KX02',  # ambrisentan
    'C02KX04',  # masitentan
    'C02KX05',  # riociguat
    'B01AC09',  # epoprostenol
    'B01AC11',  # iloprost
    'B01AC21',  # treprostinil
    'B01AC27',  # selexipag
)

# ED ile çakışan ATC ile gelen ilaçlar için PAH bağlamı gerektir
PDE5_KEYS = {'SILDENAFIL', 'TADALAFIL'}
ERA_KEYS = {'BOSENTAN', 'MASITENTAN', 'AMBRISENTAN'}
SGC_KEYS = {'RIOCIGUAT'}
PROSTANOID_KEYS = {'ILOPROST', 'EPOPROSTENOL', 'TREPROSTINIL'}

# Kesin-PAH (ED ile çakışmayan) ilaç anahtarları → bağlam tespitinde kullanılır
DEFINITE_PAH_KEYS = ERA_KEYS | SGC_KEYS | PROSTANOID_KEYS | {'SELEKSIPAG'}

SINIF_AD = {
    'ERA': 'Endotelin reseptör antagonisti (bosentan/masitentan/ambrisentan)',
    'PDE5': 'PDE-5 inhibitörü (sildenafil/tadalafil)',
    'SGC': 'sGC stimülatörü (riociguat)',
    'PROSTANOID': 'Prostanoid (iloprost inh./epoprostenol/treprostinil)',
    'IP': 'IP reseptör agonisti (seleksipag)',
}

# Yetkili branşlar (norm_tr_lower alt-string)
KARDIYOLOJI = ('kardiyol',)
KDC = ('kalp damar cerrah', 'kalp ve damar cerrah', 'kalp-damar cerrah')
GOGUS_HAST = ('gogus hastalik', 'gogus hst')
COCUK_KARDIYO = ('cocuk kardiyol', 'pediatrik kardiyol')
YETKILI_BRANSLAR = KARDIYOLOJI + KDC + GOGUS_HAST + COCUK_KARDIYO


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _iceriyor(metin_upper: str, kume: Set[str]) -> bool:
    return any(norm_tr_upper(k) in metin_upper for k in kume)


def _rapor_metni(ilac_sonuc: Dict) -> str:
    parcalar: List[str] = []
    for anahtar in ('rapor_metni', 'tum_metin', 'rapor_kodu_aciklama',
                    'rap_ack', 'rec_ack', 'rap_tesh', 'rec_tesh'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
    for anahtar in ('rapor_aciklamalari', 'recete_aciklamalari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
    return norm_tr_lower(' '.join(parcalar))


def _teshis_birlesik(ilac_sonuc: Dict) -> str:
    teshisler: List[str] = []
    for anahtar in ('recete_teshisleri', 'rec_tesh', 'rap_tesh',
                    'teshis_kodu_listesi', 'diger_raporlar_icd'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            teshisler.extend(str(x) for x in v if x)
        elif v:
            teshisler.append(str(v))
    return norm_tr_upper(' '.join(teshisler))


def _brans_l(brans: Optional[str]) -> str:
    return norm_tr_lower(brans or '')


def _brans_listede(brans: Optional[str], anahtarlar) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in anahtarlar)


def _heyet_brans_listesi(ilac_sonuc: Dict) -> List[str]:
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not isinstance(heyet, (list, tuple)):
        return []
    return [h.get('brans') or '' for h in heyet
            if isinstance(h, dict) and (h.get('ad') or h.get('brans'))]


def _rapor_var(ilac_sonuc: Dict) -> bool:
    return bool((ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
                or (ilac_sonuc.get('rapor_takip_no') or ilac_sonuc.get('rap_tak_no') or '').strip())


def _rapor_brans_adaylar(ilac_sonuc: Dict) -> List[str]:
    rb = ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or ''
    return [rb] + _heyet_brans_listesi(ilac_sonuc)


def _yas_int(ilac_sonuc: Dict) -> Optional[int]:
    for anahtar in ('hasta_yasi', 'yas'):
        v = ilac_sonuc.get(anahtar)
        if v is None or v == '':
            continue
        m = re.search(r'\d+', str(v))
        if m:
            try:
                return int(m.group(0))
            except ValueError:
                continue
    return None


# NYHA / fonksiyonel sınıf parse — roman (I-IV) ya da arabic (1-4)
# Anahtar (nyha / fonksiyonel / who / fc / fk) ile sayı arasında "sınıf",
# "kapasite", "class" gibi kelimeler ya da iki nokta/tire olabilir.
_ROMAN = {'IV': 4, 'III': 3, 'II': 2, 'I': 1}
_NYHA_RE = re.compile(
    r'(?:nyha|fonksiyonel|fonk\.?|who|\bfc\b|\bfk\b)'
    r'(?:[\s:.\-]*(?:sinif\w*|kapasit\w*|class|fc|fk))*'
    r'[\s:.\-]*(iv|iii|ii|i|[1-4])\b', re.IGNORECASE)


def _nyha_sinifi(ilac_sonuc: Dict) -> Optional[int]:
    metin = _rapor_metni(ilac_sonuc)
    en_yuksek: Optional[int] = None
    for m in _NYHA_RE.finditer(metin):
        token = m.group(1).strip().lower()
        if token in ('1', '2', '3', '4'):
            val = int(token)
        else:
            val = _ROMAN.get(token.upper())
        if val is None:
            continue
        # Aynı raporda birden çok sınıf geçebilir (örn. "II veya III") →
        # en yüksek (en ilerlemiş) sınıfı esas al; kapsam değerlendirmesi
        # buna göre yapılır.
        if en_yuksek is None or val > en_yuksek:
            en_yuksek = val
    return en_yuksek


def _pah_baglami_var(ilac_sonuc: Dict, pah_set: Set[str]) -> bool:
    """sildenafil/tadalafil için PAH bağlamı: ICD I27 / metin PAH ibaresi /
    eş-zamanlı kesin-PAH ilacı."""
    icd = _teshis_birlesik(ilac_sonuc)
    if re.search(r'\bI27', icd):
        return True
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in ('pulmoner arteriyel hipertansiyon',
                                'pulmoner hipertansiyon',
                                'pulmoner arteryel hipertansiyon')):
        return True
    if re.search(r'\bpah\b', metin):
        return True
    # eş-zamanlı kesin-PAH ilacı (ya da PAH-spesifik PDE5 markası)
    if pah_set & DEFINITE_PAH_KEYS:
        return True
    m = _arama_metni(ilac_sonuc)
    if _iceriyor(m, {'REVATIO', 'ADCIRCA'}):
        return True
    return False


def _diger_ad_listesi(ilac_sonuc: Dict) -> Tuple[List[str], bool]:
    """Reçetedeki diğer ilaç adları + alan mevcut mu."""
    adlar: List[str] = []
    alan_var = False
    for anahtar in ('recete_ilaclari', 'diger_ilac_adlari', 'diger_ilaclar'):
        v = ilac_sonuc.get(anahtar)
        if v is None:
            continue
        alan_var = True
        if isinstance(v, (list, tuple)):
            for x in v:
                if isinstance(x, dict):
                    adlar.append(str(x.get('ad') or x.get('ilac') or ''))
                elif x:
                    adlar.append(str(x))
        elif v:
            adlar.append(str(v))
    return [a for a in adlar if a], alan_var


def _ad_to_key(ad: str) -> Optional[str]:
    au = norm_tr_upper(ad)
    for key, (etken, ticari) in DRUG_DEFS.items():
        if _iceriyor(au, etken) or _iceriyor(au, ticari):
            return key
    return None


def _recete_pah_seti(ilac_sonuc: Dict, bu_key: Optional[str]) -> Tuple[Set[str], bool]:
    """Reçetedeki tüm PAH ilaç anahtarları (bu ilaç dahil) + diğer-ilaç alanı var mı."""
    pah: Set[str] = set()
    if bu_key:
        pah.add(bu_key)
    adlar, alan_var = _diger_ad_listesi(ilac_sonuc)
    for ad in adlar:
        k = _ad_to_key(ad)
        if k:
            pah.add(k)
    return pah, alan_var


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════

def _drug_key_belirle(ilac_sonuc: Dict) -> Optional[str]:
    m = _arama_metni(ilac_sonuc)
    for key, (etken, ticari) in DRUG_DEFS.items():
        if _iceriyor(m, etken) or _iceriyor(m, ticari):
            return key
    # ATC öneki (PAH-spesifik) ile fallback
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    for pref in PAH_ATC_PREFIX:
        if atc.startswith(pref):
            # ATC → key eşleme
            atc_map = {
                'C02KX01': 'BOSENTAN', 'C02KX02': 'AMBRISENTAN',
                'C02KX04': 'MASITENTAN', 'C02KX05': 'RIOCIGUAT',
                'B01AC09': 'EPOPROSTENOL', 'B01AC11': 'ILOPROST',
                'B01AC21': 'TREPROSTINIL', 'B01AC27': 'SELEKSIPAG',
            }
            return atc_map.get(pref)
    return None


def pulmoner_ht_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """Kapsam içi mi + hangi sınıf? → sınıf kimliği | None (ATLANDI).

    sildenafil/tadalafil yalnız PAH bağlamı varsa kapsama girer.
    """
    key = _drug_key_belirle(ilac_sonuc)
    if key is None:
        return None
    if key in PDE5_KEYS:
        pah_set, _ = _recete_pah_seti(ilac_sonuc, key)
        if not _pah_baglami_var(ilac_sonuc, pah_set):
            return None  # ED kullanımı varsayılır → ATLANDI
    return DRUG_KEY_TO_SINIF[key]


# ═══════════════════════════════════════════════════════════════════════
# ORTAK ATOMLAR (madde 1 tanı kriterleri + madde 4 yetki)
# ═══════════════════════════════════════════════════════════════════════

def atom_pah_tanisi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """E1: DSÖ Grup I PAH tanısı."""
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'\bI27\.?0', icd) or 'pulmoner arteriyel hipertansiyon' in metin \
            or 'pulmoner arteryel hipertansiyon' in metin:
        return SartSonuc(ad='DSÖ Grup I PAH tanısı', durum=SartDurumu.VAR,
                         neden='ICD I27.0 / pulmoner arteriyel hipertansiyon ibaresi',
                         kaynak='ICD+rapor', grup=grup)
    if re.search(r'\bI27', icd) or 'pulmoner hipertansiyon' in metin \
            or re.search(r'\bpah\b', metin):
        return SartSonuc(ad='DSÖ Grup I PAH tanısı',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Pulmoner hipertansiyon var ama DSÖ Grup I (PAH) tipi netleşmedi — manuel',
                         kaynak='ICD+rapor', grup=grup, sartli_atom=True)
    return SartSonuc(ad='DSÖ Grup I PAH tanısı',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='DSÖ Grup I PAH tanısı raporda/ICD\'de doğrulanamadı — manuel',
                     kaynak='ICD+rapor', grup=grup, sartli_atom=True)


def _atom_baslangic_metin(ilac_sonuc: Dict, ad: str, grup: str,
                          poz_kaliplar: Tuple[str, ...]) -> SartSonuc:
    """Başlangıç tanı kriteri ortak parser (sessiz → KE+şartlı; madde 2 devam)."""
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in poz_kaliplar):
        return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                         neden=f'Raporda "{ad}" ibaresi bulundu',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=(f'{ad} raporda bulunamadı — başlangıç kriteri; '
                            'madde-2 devam raporunda aranmaz — manuel'),
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_sag_kalp_kateter(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """E2: Sağ kalp kateterizasyonu ile doğrulanmış."""
    return _atom_baslangic_metin(
        ilac_sonuc, 'Sağ kalp kateterizasyonu ile doğrulanmış', grup,
        ('sag kalp kateter', 'sag kalp kataterizasyon', 'right heart cath',
         'rhc'))


def atom_vazoreaktivite_negatif(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """E3: Vazoreaktivite testi negatif."""
    metin = _rapor_metni(ilac_sonuc)
    if 'vazoreaktivite' in metin or 'vazoreaktif' in metin or 'vasoreactiv' in metin:
        # negatiflik teyidi
        if re.search(r'vazoreakti\w*[^.]{0,40}negatif', metin) \
                or re.search(r'negatif[^.]{0,40}vazoreakti', metin):
            return SartSonuc(ad='Vazoreaktivite testi negatif', durum=SartDurumu.VAR,
                             neden='Raporda vazoreaktivite testi negatif ibaresi',
                             kaynak='rapor_metni', grup=grup)
        if re.search(r'vazoreakti\w*[^.]{0,40}pozitif', metin):
            return SartSonuc(ad='Vazoreaktivite testi negatif', durum=SartDurumu.YOK,
                             neden='Rapor vazoreaktivite testi POZİTİF — kalsiyum kanal blokeri endikasyonu',
                             kaynak='rapor_metni', grup=grup)
        return SartSonuc(ad='Vazoreaktivite testi negatif',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Vazoreaktivite testi geçiyor ama negatif/pozitif netleşmedi — manuel',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Vazoreaktivite testi negatif',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=('Vazoreaktivite testi raporda bulunamadı — başlangıç kriteri; '
                            'madde-2 devam raporunda aranmaz — manuel'),
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


_PCWP_RE = re.compile(
    r'(?:kama\s*basinc\w*|pcwp|pawp|wedge)[^0-9<]{0,20}(<\s*)?(\d{1,2})')


def atom_kama_basinci(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """E4: Pulmoner arter kama basıncı < 15 mmHg."""
    metin = _rapor_metni(ilac_sonuc)
    m = _PCWP_RE.search(metin)
    if m:
        kucuktur = bool(m.group(1))
        try:
            val = int(m.group(2))
        except ValueError:
            val = None
        if val is not None:
            if val < 15 or (kucuktur and val <= 15):
                return SartSonuc(ad='Kama basıncı < 15 mmHg', durum=SartDurumu.VAR,
                                 neden=f'Raporda kama basıncı {"<" if kucuktur else ""}{val} mmHg',
                                 kaynak='rapor_metni', grup=grup)
            return SartSonuc(ad='Kama basıncı < 15 mmHg', durum=SartDurumu.YOK,
                             neden=f'Raporda kama basıncı {val} mmHg ≥ 15 — DSÖ Grup I PAH kriteri sağlanmıyor',
                             kaynak='rapor_metni', grup=grup)
    if 'kama basinc' in metin or 'wedge' in metin or 'pcwp' in metin:
        return SartSonuc(ad='Kama basıncı < 15 mmHg',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Kama basıncı geçiyor ama sayısal değer okunamadı — manuel',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Kama basıncı < 15 mmHg',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=('Kama basıncı raporda bulunamadı — başlangıç kriteri; '
                            'madde-2 devam raporunda aranmaz — manuel'),
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_nyha_genel(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """NYHA II/III/IV → VAR; I → YOK; sessiz → KE+şartlı."""
    nyha = _nyha_sinifi(ilac_sonuc)
    if nyha is None:
        return SartSonuc(ad='NYHA fonksiyonel sınıf II–IV',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='NYHA fonksiyonel sınıfı raporda okunamadı — manuel',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    if nyha >= 2:
        return SartSonuc(ad=f'NYHA sınıf {"I" * nyha if nyha < 4 else "IV"}',
                         durum=SartDurumu.VAR,
                         neden=f'NYHA sınıf {nyha} — endikasyon kapsamında (II–IV)',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='NYHA sınıf I', durum=SartDurumu.YOK,
                     neden='NYHA sınıf I — PAH ilaç endikasyonu kapsamı dışında (II–IV gerekir)',
                     kaynak='rapor_metni', grup=grup)


def atom_sk_raporu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """F1: SK raporu mevcut."""
    if _rapor_var(ilac_sonuc):
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
                         neden='Reçeteye bağlı rapor mevcut',
                         kaynak='rapor', grup=grup)
    return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                     neden='Reçeteye bağlı sağlık kurulu raporu yok',
                     kaynak='rapor', grup=grup)


def atom_3basamak(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """F2: Üçüncü basamak sağlık hizmeti sunucusu (tam-kat → sessiz=şartlı)."""
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in ('ucuncu basamak', '3. basamak', '3.basamak',
                                'egitim arastirma', 'egitim ve arastirma',
                                'universite', 'sehir hastane', 'tip fakultesi')):
        return SartSonuc(ad='Üçüncü basamak sağlık tesisi', durum=SartDurumu.VAR,
                         neden='Raporda 3. basamak SHS ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Üçüncü basamak sağlık tesisi',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor düzenleyen tesisin 3. basamak olduğu doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_heyet_brans(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """F3: Heyette ≥1 kardiyoloji/KDC/göğüs hast./çocuk kardiyolojisi uzmanı."""
    adaylar = _rapor_brans_adaylar(ilac_sonuc)
    if any(_brans_listede(a, YETKILI_BRANSLAR) for a in adaylar):
        return SartSonuc(ad='Heyette yetkili uzman (kardiyo/KDC/göğüs/çocuk kard.)',
                         durum=SartDurumu.VAR,
                         neden='Rapor/heyet branşı yetkili uzman içeriyor',
                         kaynak='rapor_brans', grup=grup)
    if _rapor_var(ilac_sonuc) and not any(_brans_l(a) for a in adaylar):
        return SartSonuc(ad='Heyette yetkili uzman (kardiyo/KDC/göğüs/çocuk kard.)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor var ama düzenleyen/heyet branşı okunamadı — manuel',
                         kaynak='rapor_brans', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Heyette yetkili uzman (kardiyo/KDC/göğüs/çocuk kard.)',
                     durum=SartDurumu.YOK,
                     neden='Rapor heyetinde kardiyoloji/KDC/göğüs hast./çocuk kardiyolojisi uzmanı yok',
                     kaynak='rapor_brans', grup=grup)


def atom_recete_brans(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """F4: Reçeteyi yetkili branş hekimi düzenlemiş."""
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    if not _brans_l(brans):
        return SartSonuc(ad='Reçete eden yetkili uzman',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, YETKILI_BRANSLAR):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Yetkili uzman (kardiyo/KDC/göğüs/çocuk kard.) reçete edebilir',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Reçeteyi yalnız kardiyoloji/KDC/göğüs hast./çocuk kardiyolojisi uzmanı düzenleyebilir',
                     kaynak='hekim_brans', grup=grup)


def atom_rapor_3ay_bilgi(grup: str) -> SartSonuc:
    """F5: Rapor 3 ay süreli (bilgi — hesaba katılmaz)."""
    return SartSonuc(ad='Rapor 3 ay süreli', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor 3 ay süreli olmalı (madde 4) — manuel doğrulanmalı',
                     kaynak='rapor_tarih', grup=grup, sartli_atom=True)


def _ortak_sartlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_pah_tanisi(ilac_sonuc, grup='(4.2.30.A/1) DSÖ Grup I PAH tanısı'),
        atom_sag_kalp_kateter(ilac_sonuc, grup='(4.2.30.A/1) Sağ kalp kateter doğrulaması'),
        atom_vazoreaktivite_negatif(ilac_sonuc, grup='(4.2.30.A/1) Vazoreaktivite negatif'),
        atom_kama_basinci(ilac_sonuc, grup='(4.2.30.A/1) Kama basıncı < 15 mmHg'),
        atom_nyha_genel(ilac_sonuc, grup='(4.2.30.A/1) NYHA fonksiyonel sınıf'),
        atom_sk_raporu(ilac_sonuc, grup='(4.2.30.A/4) Sağlık kurulu raporu'),
        atom_3basamak(ilac_sonuc, grup='(4.2.30.A/4) Üçüncü basamak tesis'),
        atom_heyet_brans(ilac_sonuc, grup='(4.2.30.A/4) Heyette yetkili uzman'),
        atom_recete_brans(ilac_sonuc, grup='(4.2.30.A/4) Reçete eden yetkili uzman'),
        atom_rapor_3ay_bilgi(grup='(4.2.30.A/4) Rapor 3 ay süreli (bilgi)'),
    ]


# ═══════════════════════════════════════════════════════════════════════
# KOMBİNASYON ATOMLARI (madde 5–8 + 1-a)
# ═══════════════════════════════════════════════════════════════════════

def _key_ad(key: str) -> str:
    return key.title()


def atom_iki_era_yok(pah_set: Set[str], alan_var: bool, grup: str) -> SartSonuc:
    """C6 (madde 6): bosentan/masitentan/ambrisentan ikisi birlikte YASAK."""
    eralar = sorted(pah_set & ERA_KEYS)
    if len(eralar) >= 2:
        return SartSonuc(ad='İki ERA birlikte değil', durum=SartDurumu.YOK,
                         neden='Eş-zamanlı ERA: ' + ', '.join(_key_ad(k) for k in eralar)
                               + ' — madde 6: bosentan/masitentan/ambrisentan kombine kullanılamaz',
                         kaynak='recete_ilaclari', grup=grup)
    if not alan_var:
        return SartSonuc(ad='İki ERA birlikte değil',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçetedeki diğer ilaçlar bilinmiyor — manuel',
                         kaynak='recete_ilaclari', grup=grup, sartli_atom=True)
    return SartSonuc(ad='İki ERA birlikte değil', durum=SartDurumu.VAR,
                     neden='Reçetede ikinci bir ERA yok',
                     kaynak='recete_ilaclari', grup=grup)


def atom_pde5_sgc_yok(pah_set: Set[str], alan_var: bool, grup: str) -> SartSonuc:
    """C7 (madde 7): sildenafil/riociguat/tadalafil ikisi birlikte YASAK."""
    grup_ilac = sorted(pah_set & ({'SILDENAFIL', 'TADALAFIL'} | SGC_KEYS))
    if len(grup_ilac) >= 2:
        return SartSonuc(ad='Sildenafil/riociguat/tadalafil birlikte değil',
                         durum=SartDurumu.YOK,
                         neden='Eş-zamanlı: ' + ', '.join(_key_ad(k) for k in grup_ilac)
                               + ' — madde 7: sildenafil/riociguat/tadalafil kombine kullanılamaz',
                         kaynak='recete_ilaclari', grup=grup)
    if not alan_var:
        return SartSonuc(ad='Sildenafil/riociguat/tadalafil birlikte değil',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçetedeki diğer ilaçlar bilinmiyor — manuel',
                         kaynak='recete_ilaclari', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Sildenafil/riociguat/tadalafil birlikte değil',
                     durum=SartDurumu.VAR,
                     neden='Reçetede bu gruptan ikinci bir ilaç yok',
                     kaynak='recete_ilaclari', grup=grup)


def atom_prostanoid_yok(pah_set: Set[str], alan_var: bool, grup: str) -> SartSonuc:
    """C8 (madde 8): iloprost-inh/epoprostenol/treprostinil/seleksipag ikisi
    birlikte YASAK."""
    g = sorted(pah_set & (PROSTANOID_KEYS | {'SELEKSIPAG'}))
    if len(g) >= 2:
        return SartSonuc(ad='İloprost/epoprostenol/treprostinil/seleksipag birlikte değil',
                         durum=SartDurumu.YOK,
                         neden='Eş-zamanlı: ' + ', '.join(_key_ad(k) for k in g)
                               + ' — madde 8: kombine kullanılamaz',
                         kaynak='recete_ilaclari', grup=grup)
    if not alan_var:
        return SartSonuc(ad='İloprost/epoprostenol/treprostinil/seleksipag birlikte değil',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçetedeki diğer ilaçlar bilinmiyor — manuel',
                         kaynak='recete_ilaclari', grup=grup, sartli_atom=True)
    return SartSonuc(ad='İloprost/epoprostenol/treprostinil/seleksipag birlikte değil',
                     durum=SartDurumu.VAR,
                     neden='Reçetede bu gruptan ikinci bir ilaç yok',
                     kaynak='recete_ilaclari', grup=grup)


def atom_kombi_matris(ilac_sonuc: Dict, pah_set: Set[str], alan_var: bool,
                      grup: str) -> SartSonuc:
    """1-a/1-b ikili/üçlü kombinasyon izin matrisi.

    mono → her NYHA serbest; NYHA IV → ikili/üçlü serbest;
    NYHA II/III ikili → yetişkin: (ambrisentan∨masitentan)+(tadalafil∨sildenafil),
    1-17 yaş: bosentan+sildenafil; NYHA II/III üçlü → YOK.
    """
    ad = 'Kombinasyon izni (madde 1-a/1-b)'
    n = len(pah_set)
    if not alan_var and n <= 1:
        # diğer ilaç alanı yok ama tek ilaç biliniyor → mono kabul
        n = 1
    if n <= 1:
        return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                         neden='Monoterapi — her NYHA sınıfında izinli',
                         kaynak='recete_ilaclari', grup=grup)
    if not alan_var:
        return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçetedeki diğer ilaçlar bilinmiyor — kombinasyon değerlendirilemedi — manuel',
                         kaynak='recete_ilaclari', grup=grup, sartli_atom=True)
    nyha = _nyha_sinifi(ilac_sonuc)
    if nyha is None:
        return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=f'{n} ilaçlı kombinasyon; NYHA sınıfı okunamadığından izin değerlendirilemedi — manuel',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    if nyha >= 4:
        return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                         neden=f'NYHA IV — {n} ilaçlı kombinasyon (ikili/üçlü) izinli',
                         kaynak='rapor_metni', grup=grup)
    # NYHA II/III. madde 1-a yalnız ERA+PDE5 (ambri/masi/bosentan +
    # tada/sil) oral ikililerini kısıtlar. Kombinasyonda 1-a'da adı geçmeyen
    # bir ilaç (riociguat/prostanoid/seleksipag) varsa bu, madde-2 eskalasyon
    # veya madde-5 (seleksipag) yoludur → 1-a pairing uygulanmaz; ilgili özel
    # atomlar (madde 5/6/7/8) zaten yasakları yakalar.
    bir_a_ilaclari = ERA_KEYS | {'SILDENAFIL', 'TADALAFIL'}
    if pah_set - bir_a_ilaclari:
        return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                         neden=(f'NYHA {nyha}: kombinasyonda 1-a dışı ilaç '
                                '(riociguat/prostanoid/seleksipag) — madde 2 eskalasyon / '
                                'madde 5 yolu; özel atomlarla değerlendirildi'),
                         kaynak='recete_ilaclari', grup=grup)
    # NYHA II/III, tümü ERA/PDE5
    if n >= 3:
        return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                         neden=f'NYHA {nyha}: üçlü kombinasyon yalnız NYHA IV\'te izinli (madde 1-a)',
                         kaynak='rapor_metni', grup=grup)
    # n == 2 ikili
    yas = _yas_int(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='İkili kombinasyon; hasta yaşı bilinmiyor — izinli çift değerlendirilemedi — manuel',
                         kaynak='hasta', grup=grup, sartli_atom=True)
    era = pah_set & {'AMBRISENTAN', 'MASITENTAN'}
    pde5 = pah_set & {'TADALAFIL', 'SILDENAFIL'}
    if yas >= 18:
        if len(era) == 1 and len(pde5) == 1 and n == 2:
            return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                             neden=(f'NYHA {nyha} yetişkin ikili: '
                                    f'{_key_ad(next(iter(era)))}+{_key_ad(next(iter(pde5)))}'
                                    ' — izinli (ambrisentan/masitentan + tadalafil/sildenafil)'),
                             kaynak='recete_ilaclari', grup=grup)
        return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                         neden=(f'NYHA {nyha} yetişkin ikili: yalnız (ambrisentan∨masitentan)+'
                                f'(tadalafil∨sildenafil) izinli; mevcut çift: '
                                + ', '.join(_key_ad(k) for k in sorted(pah_set))),
                         kaynak='recete_ilaclari', grup=grup)
    # 1-17 yaş
    if 1 <= yas <= 17:
        if pah_set == {'BOSENTAN', 'SILDENAFIL'}:
            return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                             neden=f'NYHA {nyha} (1-17 yaş) ikili: bosentan+sildenafil — izinli',
                             kaynak='recete_ilaclari', grup=grup)
        return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                         neden=(f'NYHA {nyha} (1-17 yaş) ikili: yalnız bosentan+sildenafil izinli; '
                                'mevcut çift: ' + ', '.join(_key_ad(k) for k in sorted(pah_set))),
                         kaynak='recete_ilaclari', grup=grup)
    # yas < 1
    return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Hasta yaşı {yas} — kombinasyon izin matrisi tanımsız — manuel',
                     kaynak='hasta', grup=grup, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# İLAÇ-SINIFI ÖZEL ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

def atom_nyha_3_4(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Epoprostenol (1-c): yalnız NYHA III∨IV."""
    nyha = _nyha_sinifi(ilac_sonuc)
    if nyha is None:
        return SartSonuc(ad='Epoprostenol: NYHA III veya IV',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='NYHA sınıfı okunamadı — manuel',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    if nyha in (3, 4):
        return SartSonuc(ad=f'Epoprostenol: NYHA {nyha} (III/IV)', durum=SartDurumu.VAR,
                         neden=f'NYHA {nyha} — epoprostenol endikasyonu (1-c)',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad=f'Epoprostenol: NYHA {nyha}', durum=SartDurumu.YOK,
                     neden=f'NYHA {nyha} — epoprostenol yalnız NYHA III/IV\'te (madde 1-c)',
                     kaynak='rapor_metni', grup=grup)


def atom_epoprostenol_diyaliz_yok(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """C9 (madde 9): epoprostenol böbrek diyalizi endikasyonunda ödenmez."""
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in ('bobrek diyaliz', 'hemodiyaliz', 'periton diyaliz',
                                'diyaliz')):
        return SartSonuc(ad='Böbrek diyalizi endikasyonu değil', durum=SartDurumu.YOK,
                         neden='Raporda diyaliz ibaresi — epoprostenol diyaliz endikasyonunda ödenmez (madde 9)',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Böbrek diyalizi endikasyonu değil', durum=SartDurumu.VAR,
                     neden='Diyaliz endikasyonu ibaresi yok',
                     kaynak='rapor_metni', grup=grup)


def atom_nyha_3(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Treprostinil (1-ç): yalnız NYHA III."""
    nyha = _nyha_sinifi(ilac_sonuc)
    if nyha is None:
        return SartSonuc(ad='Treprostinil: NYHA III',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='NYHA sınıfı okunamadı — manuel',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    if nyha == 3:
        return SartSonuc(ad='Treprostinil: NYHA III', durum=SartDurumu.VAR,
                         neden='NYHA III — treprostinil endikasyonu (1-ç)',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad=f'Treprostinil: NYHA {nyha}', durum=SartDurumu.YOK,
                     neden=f'NYHA {nyha} — treprostinil yalnız NYHA III\'te (madde 1-ç)',
                     kaynak='rapor_metni', grup=grup)


def atom_idiyopatik_kalitsal(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Treprostinil (1-ç): idiyopatik ∨ kalıtsal PAH."""
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in ('idiyopatik', 'idiopatik', 'kalitsal',
                                'herediter', 'heredite')):
        return SartSonuc(ad='İdiyopatik veya kalıtsal PAH', durum=SartDurumu.VAR,
                         neden='Raporda idiyopatik/kalıtsal PAH ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='İdiyopatik veya kalıtsal PAH',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='İdiyopatik/kalıtsal PAH ibaresi raporda bulunamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_seleksipag_kombi(ilac_sonuc: Dict, pah_set: Set[str], alan_var: bool,
                          grup: str) -> SartSonuc:
    """C5 (madde 5): seleksipag yalnız ERA ve/veya PDE5i ile kombine + yetersiz
    yanıt; iloprost-inh ile birlikte YASAK (madde 8 atomu ayrıca karşılar)."""
    if 'ILOPROST' in pah_set:
        return SartSonuc(ad='Seleksipag kombinasyon koşulu', durum=SartDurumu.YOK,
                         neden='Seleksipag iloprost trometamol (inhaler) ile birlikte kullanılamaz (madde 5)',
                         kaynak='recete_ilaclari', grup=grup)
    partner = pah_set & (ERA_KEYS | {'SILDENAFIL', 'TADALAFIL'})
    metin = _rapor_metni(ilac_sonuc)
    yetersiz = any(k in metin for k in ('yetersiz', 'yeterli yanit vermey',
                                        'yanit alinamad', 'yetmedi', 'etkisiz',
                                        'kontrol altina alinamad'))
    if partner and yetersiz:
        return SartSonuc(ad='Seleksipag kombinasyon koşulu', durum=SartDurumu.VAR,
                         neden='ERA/PDE5i ile kombine + yetersiz yanıt ibaresi (madde 5)',
                         kaynak='recete_ilaclari', grup=grup)
    if partner and not yetersiz:
        return SartSonuc(ad='Seleksipag kombinasyon koşulu',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='ERA/PDE5i kombinasyonu var ama "yetersiz yanıt" ibaresi bulunamadı — manuel',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    if not alan_var:
        return SartSonuc(ad='Seleksipag kombinasyon koşulu',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçetedeki diğer ilaçlar bilinmiyor — ERA/PDE5i kombinasyonu (ayrı reçete olabilir) doğrulanamadı — manuel',
                         kaynak='recete_ilaclari', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Seleksipag kombinasyon koşulu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Seleksipag yalnız ERA/PDE5i kombinasyonunda ödenir; bu reçetede partner yok (kronik kombinasyon ayrı reçetede olabilir) — manuel',
                     kaynak='recete_ilaclari', grup=grup, sartli_atom=True)


def atom_bosentan_32mg(ilac_sonuc: Dict, grup: str) -> Optional[SartSonuc]:
    """C10 (madde 10): bosentan 32mg → <30 kg pediatrik ∨ yutma güçlüğü.
    Yalnız 32mg tespit edilirse eklenir; aksi halde None (NA)."""
    ad_metni = _arama_metni(ilac_sonuc)
    if '32 MG' not in ad_metni and '32MG' not in ad_metni:
        return None
    metin = _rapor_metni(ilac_sonuc)
    yas = _yas_int(ilac_sonuc)
    yutma = any(k in metin for k in ('yutma gucluk', 'yutamayan', 'entube',
                                     'nazogastrik', 'agizdan beslen', 'yogun bakim'))
    pediatrik = (yas is not None and yas < 18)
    if yutma or pediatrik:
        return SartSonuc(ad='Bosentan 32mg: <30 kg pediatrik veya yutma güçlüğü',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=('32mg form; <30 kg pediatrik/yutma güçlüğü kuvvetle muhtemel '
                                'ama kilo/durum manuel doğrulanmalı (madde 10)'),
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Bosentan 32mg: <30 kg pediatrik veya yutma güçlüğü',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='32mg form yalnız <30 kg pediatrik veya yutma güçlüğünde ödenir — manuel doğrulanmalı (madde 10)',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# SINIF KONTROL FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════════

def _sinif_sartlari(ilac_sonuc: Dict, drug_key: str, sinif: str) -> List[SartSonuc]:
    pah_set, alan_var = _recete_pah_seti(ilac_sonuc, drug_key)
    s = _ortak_sartlar(ilac_sonuc)
    # Kombinasyon izin matrisi (1-a/1-b) — tüm sınıflarda
    s.append(atom_kombi_matris(ilac_sonuc, pah_set, alan_var,
                               grup='(4.2.30.A/1-a) Kombinasyon izni'))
    if sinif == 'ERA':
        s.append(atom_iki_era_yok(pah_set, alan_var, grup='(4.2.30.A/6) İki ERA yok'))
        if drug_key == 'BOSENTAN':
            b32 = atom_bosentan_32mg(ilac_sonuc, grup='(4.2.30.A/10) Bosentan 32mg (bilgi)')
            if b32 is not None:
                s.append(b32)
    elif sinif in ('PDE5', 'SGC'):
        s.append(atom_pde5_sgc_yok(pah_set, alan_var,
                                   grup='(4.2.30.A/7) Sildenafil/riociguat/tadalafil yok'))
    elif sinif == 'PROSTANOID':
        s.append(atom_prostanoid_yok(pah_set, alan_var,
                                     grup='(4.2.30.A/8) Prostanoid/seleksipag yok'))
        if drug_key == 'EPOPROSTENOL':
            s.append(atom_nyha_3_4(ilac_sonuc, grup='(4.2.30.A/1-c) Epoprostenol NYHA III/IV'))
            s.append(atom_epoprostenol_diyaliz_yok(
                ilac_sonuc, grup='(4.2.30.A/9) Diyaliz endikasyonu değil'))
        elif drug_key == 'TREPROSTINIL':
            s.append(atom_nyha_3(ilac_sonuc, grup='(4.2.30.A/1-ç) Treprostinil NYHA III'))
            s.append(atom_idiyopatik_kalitsal(
                ilac_sonuc, grup='(4.2.30.A/1-ç) İdiyopatik/kalıtsal PAH'))
    elif sinif == 'IP':  # seleksipag
        s.append(atom_prostanoid_yok(pah_set, alan_var,
                                     grup='(4.2.30.A/8) Prostanoid/seleksipag yok'))
        s.append(atom_seleksipag_kombi(ilac_sonuc, pah_set, alan_var,
                                       grup='(4.2.30.A/5) Seleksipag kombinasyon'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA
# ═══════════════════════════════════════════════════════════════════════

def _grup_durum(gs: List[SartSonuc]) -> Tuple[str, bool]:
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


def _and_birlestir(sonuclar: List[Tuple[str, bool]]) -> Tuple[str, bool]:
    if any(d == 'yok' for d, _ in sonuclar):
        return ('yok', False)
    ke = [(d, s) for d, s in sonuclar if d == 'ke']
    if ke:
        return ('ke', all(s for _, s in ke))
    return ('var', False)


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    gruplar: Dict[str, List[SartSonuc]] = {}
    for s in sartlar:
        if '(bilgi)' in (s.grup or ''):
            continue
        gruplar.setdefault(s.grup, []).append(s)
    if not gruplar:
        return KontrolSonucu.KONTROL_EDILEMEDI
    durumlar = [_grup_durum(gs) for gs in gruplar.values()]
    durum, sartli = _and_birlestir(durumlar)
    if durum == 'yok':
        return KontrolSonucu.UYGUN_DEGIL
    if durum == 'ke':
        return (KontrolSonucu.SARTLI_UYGUN if sartli
                else KontrolSonucu.KONTROL_EDILEMEDI)
    return KontrolSonucu.UYGUN


def _mesaj_uret(sonuc: KontrolSonucu, sinif: str, drug_key: str,
                sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    parcalar = [f'SUT 4.2.30.A / {_key_ad(drug_key)} ({SINIF_AD.get(sinif, sinif)})']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — tüm şartlar sağlandı')
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

def pulmoner_ht_kontrol_4_2_30_a(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.30.A — Pulmoner arteriyel hipertansiyon ilaçları ana kontrol."""
    drug_key = _drug_key_belirle(ilac_sonuc)
    sinif = pulmoner_ht_yolak_belirle(ilac_sonuc)
    if drug_key is None or sinif is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.30.A kapsamı dışı — PAH ilacı değil (veya PDE5i ED bağlamı)',
            sut_kurali='SUT 4.2.30.A')

    sartlar = _sinif_sartlari(ilac_sonuc, drug_key, sinif)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sinif, drug_key, sartlar)

    detaylar = {
        'sinif': sinif,
        'drug_key': drug_key,
        'sinif_ad': SINIF_AD.get(sinif, sinif),
        'sut_maddesi': '4.2.30.A',
        'ilac_adi': (ilac_sonuc.get('ilac_adi') or '').upper(),
        'etkin_madde': (ilac_sonuc.get('etkin_madde') or '').upper(),
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
        sut_kurali=f'SUT 4.2.30.A — {_key_ad(drug_key)} ({SINIF_AD.get(sinif, sinif)})',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    # Tam UYGUN ortak: başlangıç kriterleri + NYHA + yetki + tek ilaç (mono)
    tam = {
        'brans': 'Kardiyoloji', 'rapor_doktor_brans': 'Kardiyoloji',
        'rapor_kodu': '500', 'recete_teshisleri': ['I27.0'],
        'recete_ilaclari': [], 'hasta_yasi': '45',
        'rapor_metni': ('pulmoner arteriyel hipertansiyon sag kalp kateterizasyonu ile '
                        'dogrulanmis vazoreaktivite testi negatif kama basinci < 12 mmHg '
                        'nyha sinif III ucuncu basamak universite hastanesi'),
    }
    return [
        # ── ERA mono UYGUN ──
        ("ERA mono UYGUN (bosentan, tüm kriter)", {
            **tam, 'etkin_madde': 'BOSENTAN', 'ilac_adi': 'TRACLEER 125 MG',
        }, KontrolSonucu.UYGUN),
        # ── Tanı kriteri eksik → ŞARTLI ──
        ("ERA ŞARTLI (kateter/vazoreaktivite ibaresi yok = devam raporu)", {
            **tam, 'etkin_madde': 'AMBRISENTAN', 'ilac_adi': 'VOLIBRIS',
            'rapor_metni': 'pulmoner arteriyel hipertansiyon nyha sinif III ucuncu basamak universite',
        }, KontrolSonucu.SARTLI_UYGUN),
        # ── NYHA I → UYGUN DEĞİL ──
        ("ERA UYGUN DEĞİL (NYHA I kapsam dışı)", {
            **tam, 'etkin_madde': 'MASITENTAN', 'ilac_adi': 'OPSUMIT',
            'rapor_metni': ('pulmoner arteriyel hipertansiyon sag kalp kateterizasyonu '
                            'dogrulanmis vazoreaktivite negatif kama basinci < 10 mmHg '
                            'nyha sinif I ucuncu basamak universite'),
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── reçete branşı yetkisiz → UYGUN DEĞİL ──
        ("ERA UYGUN DEĞİL (reçete dahiliye)", {
            **tam, 'brans': 'İç Hastalıkları', 'etkin_madde': 'BOSENTAN',
            'ilac_adi': 'TRACLEER',
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── İki ERA kombinasyonu → UYGUN DEĞİL (madde 6) ──
        ("ERA UYGUN DEĞİL (bosentan+ambrisentan madde 6)", {
            **tam, 'etkin_madde': 'BOSENTAN', 'ilac_adi': 'TRACLEER',
            'recete_ilaclari': [{'ad': 'VOLIBRIS 10 MG'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── PDE5 ED bağlamı yok → ATLANDI ──
        ("PDE5 ATLANDI (sildenafil ED, PAH bağlamı yok)", {
            'etkin_madde': 'SILDENAFIL', 'ilac_adi': 'VIAGRA 100 MG',
            'brans': 'Üroloji', 'rapor_metni': 'erektil disfonksiyon',
            'recete_teshisleri': ['N48.4'], 'recete_ilaclari': [],
        }, KontrolSonucu.ATLANDI),
        # ── PDE5 PAH bağlamı (Revatio) UYGUN ──
        ("PDE5 UYGUN (revatio PAH bağlamı, mono)", {
            **tam, 'etkin_madde': 'SILDENAFIL', 'ilac_adi': 'REVATIO 20 MG',
        }, KontrolSonucu.UYGUN),
        # ── madde 7: sildenafil + riociguat → UYGUN DEĞİL ──
        ("PDE5 UYGUN DEĞİL (sildenafil+riociguat madde 7)", {
            **tam, 'etkin_madde': 'SILDENAFIL', 'ilac_adi': 'REVATIO',
            'recete_ilaclari': [{'ad': 'ADEMPAS 2.5 MG'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── ikili kombi yetişkin izinli (ambrisentan+tadalafil, NYHA III) ──
        ("ERA UYGUN (yetişkin ikili ambrisentan+tadalafil NYHA III)", {
            **tam, 'etkin_madde': 'AMBRISENTAN', 'ilac_adi': 'VOLIBRIS',
            'recete_ilaclari': [{'ad': 'ADCIRCA 20 MG'}],
        }, KontrolSonucu.UYGUN),
        # ── ikili kombi yetişkin izinsiz (bosentan+tadalafil NYHA III) ──
        ("ERA UYGUN DEĞİL (yetişkin ikili bosentan+tadalafil madde 1-a)", {
            **tam, 'etkin_madde': 'BOSENTAN', 'ilac_adi': 'TRACLEER',
            'recete_ilaclari': [{'ad': 'ADCIRCA 20 MG'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── NYHA IV ikili serbest (bosentan+tadalafil NYHA IV) ──
        ("ERA UYGUN (NYHA IV ikili serbest bosentan+tadalafil)", {
            **tam, 'etkin_madde': 'BOSENTAN', 'ilac_adi': 'TRACLEER',
            'recete_ilaclari': [{'ad': 'ADCIRCA 20 MG'}],
            'rapor_metni': ('pulmoner arteriyel hipertansiyon sag kalp kateterizasyonu '
                            'dogrulanmis vazoreaktivite testi negatif kama basinci < 12 mmHg '
                            'nyha sinif IV ucuncu basamak universite'),
        }, KontrolSonucu.UYGUN),
        # ── pediatrik ikili izinli (bosentan+sildenafil, 10 yaş, NYHA III) ──
        ("ERA UYGUN (pediatrik bosentan+sildenafil NYHA III)", {
            **tam, 'etkin_madde': 'BOSENTAN', 'ilac_adi': 'TRACLEER 32 MG',
            'recete_ilaclari': [{'ad': 'REVATIO 20 MG'}], 'hasta_yasi': '10',
        }, KontrolSonucu.UYGUN),  # 32mg = (bilgi) atom → hesaba katılmaz
        # ── Epoprostenol NYHA II → UYGUN DEĞİL (1-c) ──
        ("PROSTANOID UYGUN DEĞİL (epoprostenol NYHA II)", {
            **tam, 'etkin_madde': 'EPOPROSTENOL', 'ilac_adi': 'FLOLAN',
            'rapor_metni': ('pulmoner arteriyel hipertansiyon sag kalp kateterizasyonu '
                            'dogrulanmis vazoreaktivite negatif kama basinci < 12 mmHg '
                            'nyha sinif II ucuncu basamak universite'),
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Epoprostenol NYHA IV UYGUN ──
        ("PROSTANOID UYGUN (epoprostenol NYHA IV)", {
            **tam, 'etkin_madde': 'EPOPROSTENOL', 'ilac_adi': 'FLOLAN',
            'rapor_metni': ('pulmoner arteriyel hipertansiyon sag kalp kateterizasyonu '
                            'dogrulanmis vazoreaktivite negatif kama basinci < 12 mmHg '
                            'nyha sinif IV ucuncu basamak universite'),
        }, KontrolSonucu.UYGUN),
        # ── Treprostinil NYHA III + idiyopatik UYGUN ──
        ("PROSTANOID UYGUN (treprostinil NYHA III idiyopatik)", {
            **tam, 'etkin_madde': 'TREPROSTINIL', 'ilac_adi': 'REMODULIN',
            'rapor_metni': ('idiyopatik pulmoner arteriyel hipertansiyon sag kalp '
                            'kateterizasyonu dogrulanmis vazoreaktivite negatif '
                            'kama basinci < 12 mmHg nyha sinif III ucuncu basamak universite'),
        }, KontrolSonucu.UYGUN),
        # ── Treprostinil NYHA III ama idiyopatik/kalıtsal değil → ŞARTLI ──
        ("PROSTANOID ŞARTLI (treprostinil NYHA III, idiyopatik ibaresi yok)", {
            **tam, 'etkin_madde': 'TREPROSTINIL', 'ilac_adi': 'REMODULIN',
        }, KontrolSonucu.SARTLI_UYGUN),
        # ── Seleksipag iloprost ile → UYGUN DEĞİL (madde 5) ──
        ("IP UYGUN DEĞİL (seleksipag + iloprost madde 5)", {
            **tam, 'etkin_madde': 'SELEKSIPAG', 'ilac_adi': 'UPTRAVI',
            'recete_ilaclari': [{'ad': 'VENTAVIS'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Seleksipag partner + yetersiz → UYGUN ──
        ("IP UYGUN (seleksipag + ambrisentan, yetersiz yanıt)", {
            **tam, 'etkin_madde': 'SELEKSIPAG', 'ilac_adi': 'UPTRAVI',
            'recete_ilaclari': [{'ad': 'VOLIBRIS 10 MG'}],
            'rapor_metni': ('pulmoner arteriyel hipertansiyon sag kalp kateterizasyonu '
                            'dogrulanmis vazoreaktivite negatif kama basinci < 12 mmHg '
                            'nyha sinif III ucuncu basamak universite era tedavisi yetersiz yanit'),
        }, KontrolSonucu.UYGUN),
        # ── Seleksipag tek başına → ŞARTLI (partner ayrı reçetede olabilir) ──
        ("IP ŞARTLI (seleksipag mono, partner yok)", {
            **tam, 'etkin_madde': 'SELEKSIPAG', 'ilac_adi': 'UPTRAVI',
        }, KontrolSonucu.SARTLI_UYGUN),
        # ── Kapsam dışı ──
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.30.A — Pulmoner Arteriyel Hipertansiyon — Akıl Testi\n" + "=" * 70)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = pulmoner_ht_kontrol_4_2_30_a(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 70)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
