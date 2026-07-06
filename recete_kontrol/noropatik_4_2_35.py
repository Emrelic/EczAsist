# -*- coding: utf-8 -*-
"""SUT 4.2.35 — Nöropatik ağrı (A) ve kronik kas iskelet ağrısı/fibromiyalji (B).

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:8166-8202`` (mevzuat.gov.tr,
MevzuatNo=17229). Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md
``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
YOLAKLAR (dispatcher: etken madde → ilaç sınıfı; endikasyon → alt-paragraf)
═══════════════════════════════════════════════════════════════════════════

  G    → 4.2.35.A(1)  Gabapentin — nöropatik ağrı (yalnız)
  P_A2 → 4.2.35.A(2)  Pregabalin — nöropatik ağrı
  P_B2 → 4.2.35.B(2)  Pregabalin — fibromiyalji / kronik kas iskelet ağrısı
  D_A3 → 4.2.35.A(3)  Duloksetin — diyabetik periferal nöropatik ağrı
  D_B1 → 4.2.35.B(1)  Duloksetin — fibromiyalji (prospektüs endikasyonu)
  AL_a → 4.2.35.A(4)a Alfa lipoik (komb. dahil) — diyabetik nöropati/polinöropati
  AL_b → 4.2.35.A(4)b Alfa lipoik (komb. dahil) — nöropatik ağrı
  K    → 4.2.35.A(5)  Kapsaisin mono krem — postherpetik nevralji / ağrılı
                       diyabetik periferik polinöropati

  Delege (ATLANDI): Gabapentin/Pregabalin + yalnız epilepsi/YAB → SUT 4.2.25.
  Delege (doğrudan): Duloksetin nöropati/FM kanıtı yoksa (depresyon/sessiz
                     dahil) → SUT 4.2.2(1) SNRI atomik kontrolü çağrılır ve
                     sonucu döndürülür (snri_4_2_2.py, 2026-07-06).

═══════════════════════════════════════════════════════════════════════════
SK-RAPORU GEREKTİREN YOLAKLAR (G, P) vs UZMAN-HEKİM-RAPORU YOLAKLARI (D, AL, K)
═══════════════════════════════════════════════════════════════════════════

  G / P : "...en az birinin yer aldığı 2./3. basamak SHS'de düzenlenen 6 ay
           süreli SAĞLIK KURULU raporuna istinaden BU HEKİMLERCE reçete."
           ⇒ SK raporu (heyette ≥1 uygun branş) ∧ reçeteci uygun branş ∧
             2./3. basamak ∧ ≤6 ay ∧ ¬(pregabalin+gabapentin kombi)
  D     : endokrin (her basamak) ∨ (nöroloji ∧ 3. basamak); veya bu uzmanların
           UZMAN HEKİM RAPORU'na dayanarak tüm hekimlerce.
  AL/K  : uzman hekim ∨ uzman hekim raporu → tüm hekimlerce.

Sessizlik = KONTROL_EDİLEMEDİ (örtük kabul YASAK). SK/basamak/süre metinden
doğrulanamazsa `sartli_atom` (KE) → diğer şartlar VAR ise ŞARTLI UYGUN.

Ana entrypoint: ``noropatik_kontrol_4_2_35(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İLAÇ SINIFI listeleri (etken + ticari ad)
# ═══════════════════════════════════════════════════════════════════════

GABAPENTIN_ETKEN = {'GABAPENTIN', 'GABAPENTINE'}
GABAPENTIN_TICARI = {'NEURONTIN', 'NERUDA', 'GABATEVA', 'GABALEPT',
                     'GABANTIN', 'GABAGAMMA', 'EPLERONT', 'GABAX'}

PREGABALIN_ETKEN = {'PREGABALIN', 'PREGABALINE'}
PREGABALIN_TICARI = {'LYRICA', 'GABRICA', 'PREGALIN', 'PREGABEX',
                     'PREJUNTIN', 'PREGABA', 'PREGANANT', 'NETGABA'}

DULOKSETIN_ETKEN = {'DULOKSETIN', 'DULOXETINE', 'DULOXETIN'}
DULOKSETIN_TICARI = {'CYMBALTA', 'DUXET', 'DULOXIN', 'DULOX', 'DULESS',
                     'DULNEX', 'DULJADE'}

ALFA_LIPOIK_ETKEN = {'TIOKTIK', 'TİOKTİK', 'TIYOKTIK', 'TİYOKTİK',
                     'ALFA LIPOIK', 'ALFA LİPOİK', 'ALFA-LIPOIK',
                     'ALPHA LIPOIC', 'TIOCTIC', 'LIPOIK ASIT', 'LİPOİK ASİT'}
ALFA_LIPOIK_TICARI = {'THIOCTACID', 'TIOCTACID', 'NOREXIA', 'TIOXIDAL',
                      'BENEDAY', 'INSULIPON', 'LIPONAT', 'NEUROLIP',
                      'TIOLIP', 'LIPOIK'}

KAPSAISIN_ETKEN = {'KAPSAISIN', 'KAPSAİSİN', 'CAPSAICIN', 'KAPSAYSIN'}
KAPSAISIN_TICARI = {'CAPSIN', 'ZOSTRIX', 'QUTENZA'}


# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower alt-string)
# ═══════════════════════════════════════════════════════════════════════
NOROLOJI = ['noroloji', 'norolog']
BEYIN_CER = ['beyin cerrah', 'norosirurji', 'sinir cerrah']
FTR = ['fiziksel tip', 'fizik tedav', 'fiziksel tedav', 'ftr',
       'rehabilitasyon', 'fizyoterapi', 'fizik ted']
ALGOLOJI = ['algoloji', 'algolog']
DERMATOLOJI = ['deri', 'dermatoloj', 'cilt', 'zuhrevi']
ROMATOLOJI = ['romatoloj']
ORTOPEDI = ['ortopedi', 'travmatoloji']
GERIATRI = ['geriatri']
ENDOKRIN = ['endokrin']
NEFROLOJI = ['nefroloji', 'nefrolog']
ANESTEZI = ['anestezi', 'reanimasyon']
IMMUNOLOJI = ['immunoloj', 'alerji']
IC_HAST = ['ic hastalik', 'dahiliye']
PRATISYEN = ['aile hek', 'pratisyen', 'genel pratisyen']

# Yolak başına kabul edilen branş listeleri (SUT lafzına birebir)
A1_BRANS = (NOROLOJI + BEYIN_CER + FTR + ALGOLOJI + DERMATOLOJI
            + ROMATOLOJI + ORTOPEDI + GERIATRI + ENDOKRIN)
A2_BRANS = (ROMATOLOJI + ALGOLOJI + DERMATOLOJI + ENDOKRIN + NOROLOJI
            + FTR + NEFROLOJI + ORTOPEDI + GERIATRI + BEYIN_CER)
B2_BRANS = ROMATOLOJI + ORTOPEDI + FTR + NOROLOJI + ALGOLOJI
B1_BRANS = ROMATOLOJI + ORTOPEDI + FTR + ALGOLOJI
ALA_BRANS = (NOROLOJI + BEYIN_CER + FTR + ANESTEZI + IMMUNOLOJI
             + ROMATOLOJI + IC_HAST + ENDOKRIN)
ALB_BRANS = (NOROLOJI + BEYIN_CER + FTR + ANESTEZI + IMMUNOLOJI
             + DERMATOLOJI + ROMATOLOJI + ORTOPEDI + ENDOKRIN)
K_BRANS = (NOROLOJI + BEYIN_CER + FTR + ANESTEZI + IMMUNOLOJI + DERMATOLOJI
           + ROMATOLOJI + ORTOPEDI + GERIATRI + IC_HAST + ENDOKRIN)


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _iceriyor(metin_upper: str, kume) -> bool:
    return any(norm_tr_upper(k) in metin_upper for k in kume)


def _rapor_metni(ilac_sonuc: Dict) -> str:
    parcalar: List[str] = []
    for anahtar in ('rapor_metni', 'tum_metin', 'rapor_kodu_aciklama', 'rap_ack'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
    for anahtar in ('rapor_aciklamalari', 'recete_aciklamalari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
    return norm_tr_lower(' '.join(parcalar))


def _teshis_upper(ilac_sonuc: Dict) -> str:
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


def _brans_listede(brans: Optional[str], anahtarlar: List[str]) -> bool:
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


def _3basamak(ilac_sonuc: Dict) -> Optional[bool]:
    """Rapor/tesis 2. veya 3. basamak mı? True/None(belirsiz).

    SUT 4.2.35.A/B: 'ikinci veya üçüncü basamak SHS'de düzenlenen' → 2. basamak
    (devlet hastanesi) da yeterli. Bu nedenle hem 2. hem 3. basamak ibareleri taranır.
    """
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in ('ucuncu basamak', '3. basamak', '3.basamak',
                                'ikinci basamak', '2. basamak', '2.basamak',
                                'egitim arastirma', 'universite hastane',
                                'sehir hastane', 'tip fakultesi', 'devlet hastane')):
        return True
    return None  # parse edilemedi


# ═══════════════════════════════════════════════════════════════════════
# ENDİKASYON tespiti
# ═══════════════════════════════════════════════════════════════════════

def _endikasyonlar(ilac_sonuc: Dict) -> Dict[str, bool]:
    metin = _rapor_metni(ilac_sonuc) + ' ' + norm_tr_lower(_teshis_upper(ilac_sonuc))
    icd = _teshis_upper(ilac_sonuc)
    d: Dict[str, bool] = {}
    d['diyabetik_noro'] = (
        any(k in metin for k in ('diyabetik noropati', 'diabetik noropati',
                                 'diyabetik polinoropati', 'periferal diabetik',
                                 'periferik polinoropati', 'polinoropati',
                                 'diyabetik periferik'))
        or bool(re.search(r'E1[0-4]\.?4', icd))
        or bool(re.search(r'\bG6(0|2)|\bG63\.?2', icd)))
    d['phn'] = (
        any(k in metin for k in ('postherpetik', 'post-herpetik', 'post herpetik',
                                 'zona sonrasi', 'herpes zoster nevralji'))
        or bool(re.search(r'\bB02\.?2|\bG53\.?0', icd)))
    d['noropatik'] = (
        any(k in metin for k in ('noropatik', 'noropati', 'nevralji', 'nevralgia'))
        or bool(re.search(r'\bG5[0-9]|\bG6[0-4]|\bM79\.?2', icd))
        or d['diyabetik_noro'] or d['phn'])
    d['fibromiyalji'] = (
        any(k in metin for k in ('fibromiyalji', 'fibromyalji'))
        or bool(re.search(r'\bM79\.?7', icd)))
    d['kronik_kas_iskelet'] = any(
        k in metin for k in ('kronik kas iskelet', 'kas iskelet agri',
                             'kas-iskelet agri', 'kronik kas-iskelet'))
    d['depresyon'] = (
        any(k in metin for k in ('depresyon', 'depresif', 'major depres'))
        or bool(re.search(r'\bF3[23]', icd)))
    d['epilepsi'] = (
        any(k in metin for k in ('epilepsi', 'konvulsiy', 'nobet'))
        or bool(re.search(r'\bG40', icd)))
    d['yab'] = (
        any(k in metin for k in ('yaygin anksiyete', 'generalize anksiyete'))
        or bool(re.search(r'\bF41', icd)))
    d['artrit'] = (
        any(k in metin for k in ('osteoartrit', 'artrit', 'gonartroz', 'koksartroz',
                                 'eklem agri', 'kas ve eklem'))
        or bool(re.search(r'\bM1[5-9]', icd)))
    return d


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════

def noropatik_yolak_belirle(ilac_sonuc: Dict) -> Dict[str, Optional[str]]:
    """{'durum': 'yolak'|'atlandi'|'disi', 'yolak': str|None, 'mesaj': str}."""
    m = _arama_metni(ilac_sonuc)
    e = _endikasyonlar(ilac_sonuc)
    noropatik_aile = e['noropatik'] or e['phn'] or e['diyabetik_noro']

    # ── Gabapentin → A(1) ──
    if _iceriyor(m, GABAPENTIN_ETKEN) or _iceriyor(m, GABAPENTIN_TICARI):
        if (e['epilepsi'] or e['yab']) and not (noropatik_aile or e['fibromiyalji']):
            return {'durum': 'atlandi', 'yolak': None,
                    'mesaj': 'Gabapentin epilepsi/YAB endikasyonunda — SUT 4.2.25 '
                             '(antiepileptik) butonunda kontrol edilir'}
        return {'durum': 'yolak', 'yolak': 'G', 'mesaj': ''}

    # ── Pregabalin → A(2) / B(2) ──
    if _iceriyor(m, PREGABALIN_ETKEN) or _iceriyor(m, PREGABALIN_TICARI):
        if (e['epilepsi'] or e['yab']) and not (
                noropatik_aile or e['fibromiyalji'] or e['kronik_kas_iskelet']):
            return {'durum': 'atlandi', 'yolak': None,
                    'mesaj': 'Pregabalin epilepsi/YAB endikasyonunda — SUT 4.2.25 '
                             '(antiepileptik) butonunda kontrol edilir'}
        if (e['fibromiyalji'] or e['kronik_kas_iskelet']) and not noropatik_aile:
            return {'durum': 'yolak', 'yolak': 'P_B2', 'mesaj': ''}
        return {'durum': 'yolak', 'yolak': 'P_A2', 'mesaj': ''}

    # ── Duloksetin → A(3) / B(1) / delege 4.2.2 (SNRI) ──
    # 2026-07-06: nöropati/fibromiyalji KANITI yoksa D_A3'e zorlamak yerine
    # SUT 4.2.2(1) SNRI atomik kontrolüne delege edilir (depresyon/anksiyete
    # ve SESSİZ endikasyon dahil — duloksetinin varsayılan maddesi 4.2.2).
    if _iceriyor(m, DULOKSETIN_ETKEN) or _iceriyor(m, DULOKSETIN_TICARI):
        if (e['fibromiyalji'] or e['kronik_kas_iskelet']) and not e['diyabetik_noro']:
            return {'durum': 'yolak', 'yolak': 'D_B1', 'mesaj': ''}
        if e['diyabetik_noro'] or noropatik_aile:
            return {'durum': 'yolak', 'yolak': 'D_A3', 'mesaj': ''}
        return {'durum': 'delege_422', 'yolak': None,
                'mesaj': 'Duloksetin: nöropati/fibromiyalji kanıtı yok — '
                         'SUT 4.2.2(1) SNRI kontrolüne delege'}

    # ── Alfa lipoik → A(4)a / A(4)b ──
    if _iceriyor(m, ALFA_LIPOIK_ETKEN) or _iceriyor(m, ALFA_LIPOIK_TICARI):
        if e['diyabetik_noro']:
            return {'durum': 'yolak', 'yolak': 'AL_a', 'mesaj': ''}
        return {'durum': 'yolak', 'yolak': 'AL_b', 'mesaj': ''}

    # ── Kapsaisin → A(5) ──
    if _iceriyor(m, KAPSAISIN_ETKEN) or _iceriyor(m, KAPSAISIN_TICARI):
        return {'durum': 'yolak', 'yolak': 'K', 'mesaj': ''}

    return {'durum': 'disi', 'yolak': None,
            'mesaj': 'SUT 4.2.35 (nöropatik/fibromiyalji) kapsamında değil'}


# ═══════════════════════════════════════════════════════════════════════
# ORTAK ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

def atom_sk_raporu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Sağlık kurulu raporu var mı? (G/P yolakları için zorunlu)."""
    metin = _rapor_metni(ilac_sonuc)
    heyet = [b for b in _heyet_brans_listesi(ilac_sonuc) if b]
    if 'saglik kurulu' in metin or 'heyet' in metin or len(heyet) >= 1:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
                         neden='Sağlık kurulu / heyet raporu tespit edildi',
                         kaynak='rapor', grup=grup)
    if _rapor_var(ilac_sonuc):
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor var ama sağlık kurulu (heyet) olduğu doğrulanamadı — manuel',
                         kaynak='rapor', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                     neden='Reçeteye bağlı rapor yok — SK raporu zorunlu',
                     kaynak='rapor', grup=grup)


def atom_heyet_brans(ilac_sonuc: Dict, brans_list: List[str], grup: str) -> SartSonuc:
    """Heyette ≥1 uygun branş uzmanı (SUT: 'en az birinin yer aldığı')."""
    heyet = [b for b in _heyet_brans_listesi(ilac_sonuc) if b]
    if any(_brans_listede(b, brans_list) for b in heyet):
        return SartSonuc(ad='Heyette uygun uzman (≥1)', durum=SartDurumu.VAR,
                         neden='Sağlık kurulunda SUT branşlarından en az biri var',
                         kaynak='rapor_heyet', grup=grup)
    if not heyet:
        return SartSonuc(ad='Heyette uygun uzman (≥1)', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Heyet branş bilgisi okunamadı — manuel',
                         kaynak='rapor_heyet', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Heyette uygun uzman (≥1)', durum=SartDurumu.YOK,
                     neden='Sağlık kurulunda SUT\'ta sayılan branşlardan uzman yok',
                     kaynak='rapor_heyet', grup=grup)


def atom_receteci_brans(ilac_sonuc: Dict, brans_list: List[str], grup: str,
                        zorunlu: bool = True) -> SartSonuc:
    """Reçete eden hekim SUT branş listesinde mi? (G/P: 'bu hekimlerce')."""
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    if not _brans_l(brans):
        return SartSonuc(ad='Reçete eden uygun branş', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, brans_list):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='SUT\'ta sayılan uzman branşı reçete edebilir',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='SUT\'ta sayılan uzman branşı değil — bu ilacı bu endikasyonda '
                           'yazamaz',
                     kaynak='hekim_brans', grup=grup)


def atom_uzman_yetki(ilac_sonuc: Dict, brans_list: List[str], grup: str) -> List[SartSonuc]:
    """(reçeteci ∈ list) ∨ (uzman hekim raporu düzenleyen ∈ list) → veya_grubu.

    D/AL/K yolakları: 'uzman hekim tarafından VEYA bu uzmanların raporuna
    dayanılarak tüm hekimlerce'.
    """
    s: List[SartSonuc] = []
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    bl = _brans_l(brans)

    if not bl:
        s.append(SartSonuc(ad='Reçete eden uzman branşı', durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='Reçete eden hekim branşı bilinmiyor — manuel',
                           kaynak='hekim_brans', grup=grup, veya_grubu=True, sartli_atom=True))
    elif _brans_listede(brans, brans_list):
        s.append(SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                           neden='SUT uzman branşı doğrudan reçete edebilir',
                           kaynak='hekim_brans', grup=grup, veya_grubu=True))
    else:
        s.append(SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                           neden='SUT uzman branşı değil — uzman hekim raporu gerekli',
                           kaynak='hekim_brans', grup=grup, veya_grubu=True))

    rapor_var = _rapor_var(ilac_sonuc)
    adaylar = _rapor_brans_adaylar(ilac_sonuc)
    if any(_brans_listede(a, brans_list) for a in adaylar):
        s.append(SartSonuc(ad='Uzman hekim raporu (SUT branşı düzenlemiş)',
                           durum=SartDurumu.VAR,
                           neden='SUT uzman branşının düzenlediği rapora dayanılarak '
                                 'tüm hekimlerce reçete edilebilir',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True))
    elif rapor_var and not any(_brans_l(a) for a in adaylar):
        s.append(SartSonuc(ad='Uzman hekim raporu (düzenleyen branş bilinmiyor)',
                           durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='Rapor var ama düzenleyen/heyet branşı okunamadı — manuel',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True, sartli_atom=True))
    elif rapor_var:
        s.append(SartSonuc(ad='Uzman hekim raporu (SUT branşı değil)',
                           durum=SartDurumu.YOK,
                           neden='Rapor düzenleyen SUT uzman branşı değil',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True))
    else:
        s.append(SartSonuc(ad='Uzman hekim raporu', durum=SartDurumu.YOK,
                           neden='Reçeteye bağlı uzman hekim raporu yok',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True))
    return s


def atom_kombi_yasak(ilac_sonuc: Dict, bu_pregabalin: bool, grup: str) -> SartSonuc:
    """Pregabalin + gabapentin AYNI REÇETEDE kombine kullanılamaz (NEGATİF)."""
    diger = norm_tr_upper(' '.join(
        [str(x) for x in (ilac_sonuc.get('diger_etken_maddeler') or [])]
        + [str(x) for x in (ilac_sonuc.get('diger_ilac_adlari') or [])]))
    if bu_pregabalin:
        karsi = _iceriyor(diger, GABAPENTIN_ETKEN) or _iceriyor(diger, GABAPENTIN_TICARI)
        karsi_ad = 'gabapentin'
    else:
        karsi = _iceriyor(diger, PREGABALIN_ETKEN) or _iceriyor(diger, PREGABALIN_TICARI)
        karsi_ad = 'pregabalin'
    if karsi:
        return SartSonuc(ad='Pregabalin + gabapentin kombi yasağı', durum=SartDurumu.YOK,
                         neden=f'Aynı reçetede {karsi_ad} de var — kombine kullanılamaz',
                         kaynak='recete_kalemleri', grup=grup)
    return SartSonuc(ad='Pregabalin + gabapentin kombi yasağı', durum=SartDurumu.VAR,
                     neden='Aynı reçetede karşıt etken yok',
                     kaynak='recete_kalemleri', grup=grup)


def atom_basamak(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """2./3. basamak SHS şartı (parse zor → KE + şartlı)."""
    if _3basamak(ilac_sonuc) is True:
        return SartSonuc(ad='2./3. basamak sağlık hizmeti sunucusu', durum=SartDurumu.VAR,
                         neden='Raporda 3. basamak/üniversite/EAH ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='2./3. basamak sağlık hizmeti sunucusu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Raporun düzenlendiği basamak metinden doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_sure_6ay(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """6 ay süreli SK raporu (parse zor → KE + şartlı)."""
    metin = _rapor_metni(ilac_sonuc)
    m = re.search(r'(\d{1,2})\s*ay\s*sur', metin)
    if m:
        try:
            ay = int(m.group(1))
            if ay <= 6:
                return SartSonuc(ad=f'Rapor süresi {ay} ay (≤6)', durum=SartDurumu.VAR,
                                 neden='6 ay süre şartı sağlanıyor',
                                 kaynak='rapor_metni', grup=grup)
            return SartSonuc(ad=f'Rapor süresi {ay} ay (>6)', durum=SartDurumu.YOK,
                             neden='SUT 4.2.35: en fazla 6 ay süreli SK raporu',
                             kaynak='rapor_metni', grup=grup)
        except ValueError:
            pass
    # Parse edilemedi → CLAUDE.md §6: rapor süresi gibi okunamayan yapısal şart
    # (bilgi) grubuna alınır; matematiği bozmaz, görsel olarak görünür.
    # (antiepileptik_4_2_25 süre atomu ile hizalı). Parse EDİLEN >6 ay ihlali
    # ise yukarıda düz grupta YOK döner → UYGUN DEĞİL korunur.
    return SartSonuc(ad='Rapor süresi ≤ 6 ay', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor süresi metinden okunamadı — manuel (bilgi)',
                     kaynak='rapor_metni', grup=f'{grup} (bilgi)', sartli_atom=True)


# ── Endikasyon atomları ──

def _atom_endik(durum_var: bool, durum_yok: bool, ad: str, grup: str,
                neden_var: str, neden_yok: str) -> SartSonuc:
    if durum_var:
        return SartSonuc(ad=ad, durum=SartDurumu.VAR, neden=neden_var,
                         kaynak='ICD+rapor', grup=grup)
    if durum_yok:
        return SartSonuc(ad=ad, durum=SartDurumu.YOK, neden=neden_yok,
                         kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Endikasyon reçete/raporda net okunamadı — manuel',
                     kaynak='ICD+rapor', grup=grup, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# YOLAK FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════════

def g_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    e = _endikasyonlar(ilac_sonuc)
    noro = e['noropatik'] or e['phn'] or e['diyabetik_noro']
    s: List[SartSonuc] = []
    s.append(_atom_endik(
        noro, (e['fibromiyalji'] or e['kronik_kas_iskelet']) and not noro,
        'Endikasyon: nöropatik ağrı', '(A1) Endikasyon (nöropatik ağrı)',
        'Nöropatik ağrı / diyabetik nöropati / PHN endikasyonu',
        'Gabapentin yalnız nöropatik ağrıda (A1); fibromiyalji kapsam dışı'))
    s.append(atom_sk_raporu(ilac_sonuc, grup='(A1) Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, A1_BRANS, grup='(A1) Heyette uygun uzman'))
    s.append(atom_receteci_brans(ilac_sonuc, A1_BRANS, grup='(A1) Reçete eden uzman'))
    s.append(atom_basamak(ilac_sonuc, grup='(A1) 2./3. basamak SHS'))
    s.append(atom_sure_6ay(ilac_sonuc, grup='(A1) Rapor süresi ≤6 ay'))
    s.append(atom_kombi_yasak(ilac_sonuc, bu_pregabalin=False,
                              grup='(A1) Pregabalin+gabapentin kombi yasağı'))
    return s


def p_a2_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    e = _endikasyonlar(ilac_sonuc)
    noro = e['noropatik'] or e['phn'] or e['diyabetik_noro']
    s: List[SartSonuc] = []
    s.append(_atom_endik(
        noro, False, 'Endikasyon: nöropatik ağrı',
        '(A2) Endikasyon (nöropatik ağrı)',
        'Nöropatik ağrı endikasyonu', ''))
    s.append(atom_sk_raporu(ilac_sonuc, grup='(A2) Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, A2_BRANS, grup='(A2) Heyette uygun uzman'))
    s.append(atom_receteci_brans(ilac_sonuc, A2_BRANS, grup='(A2) Reçete eden uzman'))
    s.append(atom_basamak(ilac_sonuc, grup='(A2) 2./3. basamak SHS'))
    s.append(atom_sure_6ay(ilac_sonuc, grup='(A2) Rapor süresi ≤6 ay'))
    s.append(atom_kombi_yasak(ilac_sonuc, bu_pregabalin=True,
                              grup='(A2) Pregabalin+gabapentin kombi yasağı'))
    return s


def p_b2_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    e = _endikasyonlar(ilac_sonuc)
    fm = e['fibromiyalji'] or e['kronik_kas_iskelet']
    s: List[SartSonuc] = []
    s.append(_atom_endik(
        fm, False, 'Endikasyon: fibromiyalji / kronik kas iskelet ağrısı',
        '(B2) Endikasyon (fibromiyalji/kronik kas-iskelet)',
        'Fibromiyalji / kronik kas iskelet ağrısı endikasyonu', ''))
    s.append(atom_sk_raporu(ilac_sonuc, grup='(B2) Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, B2_BRANS, grup='(B2) Heyette uygun uzman'))
    s.append(atom_receteci_brans(ilac_sonuc, B2_BRANS, grup='(B2) Reçete eden uzman'))
    s.append(atom_basamak(ilac_sonuc, grup='(B2) 2./3. basamak SHS'))
    s.append(atom_sure_6ay(ilac_sonuc, grup='(B2) Rapor süresi ≤6 ay'))
    s.append(atom_kombi_yasak(ilac_sonuc, bu_pregabalin=True,
                              grup='(B2) Pregabalin+gabapentin kombi yasağı'))
    return s


def d_a3_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Duloksetin A(3): diyabetik periferal nöropatik ağrı + (endokrin ∨
    nöroloji-3.basamak) reçeteci/raporu."""
    e = _endikasyonlar(ilac_sonuc)
    s: List[SartSonuc] = []
    s.append(_atom_endik(
        e['diyabetik_noro'], False,
        'Endikasyon: diyabetik periferal nöropatik ağrı',
        '(A3) Endikasyon (diyabetik periferal nöropatik ağrı)',
        'Diyabetik periferal nöropatik ağrı endikasyonu', ''))

    # Yetki: reçeteci endokrin (her basamak) ∨ (nöroloji ∧ 3.basamak)
    #        ∨ uzman hekim raporu (endokrin ∨ nöroloji-3.basamak düzenlemiş)
    grup = '(A3) Endokrin veya 3.basamak nöroloji uzmanı/raporu (≥1)'
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    bl = _brans_l(brans)
    bas3 = _3basamak(ilac_sonuc)

    # Atom 1 — reçeteci endokrin
    if not bl:
        s.append(SartSonuc(ad='Reçete eden endokrinoloji uzmanı',
                           durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='Reçete eden hekim branşı bilinmiyor — manuel',
                           kaynak='hekim_brans', grup=grup, veya_grubu=True, sartli_atom=True))
    elif _brans_listede(brans, ENDOKRIN):
        s.append(SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                           neden='Endokrinoloji uzmanı her basamakta reçete edebilir',
                           kaynak='hekim_brans', grup=grup, veya_grubu=True))
    else:
        s.append(SartSonuc(ad=f'Reçete eden: {brans} (endokrin değil)',
                           durum=SartDurumu.YOK,
                           neden='Endokrinoloji uzmanı değil',
                           kaynak='hekim_brans', grup=grup, veya_grubu=True))

    # Atom 2 — reçeteci nöroloji ∧ 3. basamak
    if bl and _brans_listede(brans, NOROLOJI):
        if bas3 is True:
            s.append(SartSonuc(ad=f'Reçete eden: {brans} + 3. basamak', durum=SartDurumu.VAR,
                               neden='3. basamakta nöroloji uzmanı reçete edebilir',
                               kaynak='hekim_brans', grup=grup, veya_grubu=True))
        else:
            s.append(SartSonuc(ad='Nöroloji uzmanı + 3. basamak',
                               durum=SartDurumu.KONTROL_EDILEMEDI,
                               neden='Nöroloji uzmanı; 3. basamak olduğu doğrulanamadı — manuel',
                               kaynak='hekim_brans', grup=grup, veya_grubu=True, sartli_atom=True))
    else:
        s.append(SartSonuc(ad='Nöroloji uzmanı + 3. basamak', durum=SartDurumu.YOK,
                           neden='Reçeteci 3. basamak nöroloji uzmanı değil',
                           kaynak='hekim_brans', grup=grup, veya_grubu=True))

    # Atom 3 — uzman hekim raporu (endokrin ∨ nöroloji düzenlemiş)
    rapor_var = _rapor_var(ilac_sonuc)
    adaylar = _rapor_brans_adaylar(ilac_sonuc)
    if any(_brans_listede(a, ENDOKRIN + NOROLOJI) for a in adaylar):
        s.append(SartSonuc(ad='Uzman hekim raporu (endokrin/nöroloji düzenlemiş)',
                           durum=SartDurumu.VAR,
                           neden='Endokrin/nöroloji uzman raporuna dayanılarak tüm hekimlerce',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True))
    elif rapor_var and not any(_brans_l(a) for a in adaylar):
        s.append(SartSonuc(ad='Uzman hekim raporu (düzenleyen branş bilinmiyor)',
                           durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='Rapor var ama düzenleyen branşı okunamadı — manuel',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True, sartli_atom=True))
    else:
        s.append(SartSonuc(ad='Uzman hekim raporu (endokrin/nöroloji)',
                           durum=SartDurumu.YOK,
                           neden='Endokrin/nöroloji uzman hekim raporu yok',
                           kaynak='rapor_brans', grup=grup, veya_grubu=True))
    return s


def d_b1_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Duloksetin fibromiyalji → B(1) jenerik: romatoloji/ortopedi/FTR/algoloji
    uzmanı veya raporu."""
    e = _endikasyonlar(ilac_sonuc)
    fm = e['fibromiyalji'] or e['kronik_kas_iskelet']
    s: List[SartSonuc] = []
    s.append(_atom_endik(
        fm, False, 'Endikasyon: fibromiyalji / kronik kas iskelet ağrısı',
        '(B1) Endikasyon (fibromiyalji/kronik kas-iskelet)',
        'Fibromiyalji / kronik kas iskelet ağrısı endikasyonu', ''))
    s.extend(atom_uzman_yetki(ilac_sonuc, B1_BRANS,
                              grup='(B1) Romatoloji/ortopedi/FTR/algoloji uzmanı veya raporu (≥1)'))
    return s


def al_a_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    e = _endikasyonlar(ilac_sonuc)
    s: List[SartSonuc] = []
    s.append(_atom_endik(
        e['diyabetik_noro'], False,
        'Endikasyon: diyabetik nöropati / periferal diabetik polinöropati',
        '(A4a) Endikasyon (diyabetik nöropati/polinöropati)',
        'Diyabetik nöropatik ağrı / periferal diabetik polinöropati', ''))
    s.extend(atom_uzman_yetki(ilac_sonuc, ALA_BRANS,
                              grup='(A4a) SUT uzman branşı veya raporu (≥1)'))
    return s


def al_b_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    e = _endikasyonlar(ilac_sonuc)
    noro = e['noropatik'] or e['phn'] or e['diyabetik_noro']
    s: List[SartSonuc] = []
    s.append(_atom_endik(
        noro, False, 'Endikasyon: nöropatik ağrı',
        '(A4b) Endikasyon (nöropatik ağrı)', 'Nöropatik ağrı endikasyonu', ''))
    s.extend(atom_uzman_yetki(ilac_sonuc, ALB_BRANS,
                              grup='(A4b) SUT uzman branşı veya raporu (≥1)'))
    return s


def k_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    e = _endikasyonlar(ilac_sonuc)
    m = _arama_metni(ilac_sonuc)
    s: List[SartSonuc] = []

    # Form: mono krem
    if 'KREM' in m or 'CREAM' in m:
        s.append(SartSonuc(ad='Form: mono krem', durum=SartDurumu.VAR,
                           neden='Krem formu', kaynak='ilac_adi', grup='(A5) Mono krem formu'))
    else:
        s.append(SartSonuc(ad='Form: mono krem', durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='Krem formu metinden doğrulanamadı — manuel',
                           kaynak='ilac_adi', grup='(A5) Mono krem formu', sartli_atom=True))

    # Endikasyon: PHN ∨ ağrılı diyabetik periferik polinöropati; artrit/OA → YOK
    if e['phn'] or e['diyabetik_noro']:
        s.append(SartSonuc(ad='Endikasyon: postherpetik nevralji / ağrılı diyabetik '
                              'periferik polinöropati', durum=SartDurumu.VAR,
                           neden='Postherpetik nevralji veya ağrılı diyabetik polinöropati',
                           kaynak='ICD+rapor', grup='(A5) Endikasyon (PHN/diyabetik polinöropati)'))
    elif e['artrit']:
        s.append(SartSonuc(ad='Endikasyon (artrit/osteoartrit/kas-eklem ağrısı)',
                           durum=SartDurumu.YOK,
                           neden='Artrit/osteoartrit/kas-eklem ağrısında bedeli karşılanmaz',
                           kaynak='ICD+rapor', grup='(A5) Endikasyon (PHN/diyabetik polinöropati)'))
    else:
        s.append(SartSonuc(ad='Endikasyon: postherpetik nevralji / ağrılı diyabetik '
                              'periferik polinöropati', durum=SartDurumu.KONTROL_EDILEMEDI,
                           neden='PHN / ağrılı diyabetik polinöropati endikasyonu net okunamadı — manuel',
                           kaynak='ICD+rapor', grup='(A5) Endikasyon (PHN/diyabetik polinöropati)',
                           sartli_atom=True))

    s.extend(atom_uzman_yetki(ilac_sonuc, K_BRANS,
                              grup='(A5) SUT uzman branşı veya raporu (≥1)'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (parkinson_4_2_36 ile aynı motor)
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


def _mesaj_uret(sonuc: KontrolSonucu, yolak: str, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    meta = YOLAK_METADATA.get(yolak, {})
    parcalar = [f"SUT {meta.get('sut', '4.2.35')} / {meta.get('ad', yolak)}"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — tüm şartlar sağlandı")
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

YOLAK_FN_MAP = {
    'G': g_kontrol, 'P_A2': p_a2_kontrol, 'P_B2': p_b2_kontrol,
    'D_A3': d_a3_kontrol, 'D_B1': d_b1_kontrol,
    'AL_a': al_a_kontrol, 'AL_b': al_b_kontrol, 'K': k_kontrol,
}
YOLAK_METADATA = {
    'G':    {'ad': 'Gabapentin (nöropatik ağrı)', 'sut': '4.2.35.A(1)'},
    'P_A2': {'ad': 'Pregabalin (nöropatik ağrı)', 'sut': '4.2.35.A(2)'},
    'P_B2': {'ad': 'Pregabalin (fibromiyalji/kronik kas-iskelet)', 'sut': '4.2.35.B(2)'},
    'D_A3': {'ad': 'Duloksetin (diyabetik periferal nöropatik ağrı)', 'sut': '4.2.35.A(3)'},
    'D_B1': {'ad': 'Duloksetin (fibromiyalji)', 'sut': '4.2.35.B(1)'},
    'AL_a': {'ad': 'Alfa lipoik (diyabetik nöropati/polinöropati)', 'sut': '4.2.35.A(4)a'},
    'AL_b': {'ad': 'Alfa lipoik (nöropatik ağrı)', 'sut': '4.2.35.A(4)b'},
    'K':    {'ad': 'Kapsaisin mono krem', 'sut': '4.2.35.A(5)'},
}


def noropatik_kontrol_4_2_35(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.35 (nöropatik ağrı / fibromiyalji) ana kontrol fonksiyonu."""
    karar = noropatik_yolak_belirle(ilac_sonuc)
    if karar['durum'] == 'disi':
        return KontrolRaporu(sonuc=KontrolSonucu.ATLANDI, mesaj=karar['mesaj'],
                             sut_kurali='SUT 4.2.35')
    if karar['durum'] == 'atlandi':
        return KontrolRaporu(sonuc=KontrolSonucu.ATLANDI, mesaj=karar['mesaj'],
                             sut_kurali='SUT 4.2.35 (başka maddeye delege)')
    if karar['durum'] == 'delege_422':
        # Duloksetin nöropati/FM kanıtı yok → SUT 4.2.2(1) SNRI atomik kontrol
        from recete_kontrol.snri_4_2_2 import snri_kontrol_4_2_2
        return snri_kontrol_4_2_2(ilac_sonuc, _delege_kaynak='noropatik')

    yolak = karar['yolak']
    sartlar = YOLAK_FN_MAP[yolak](ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali=f"SUT {YOLAK_METADATA[yolak]['sut']}",
        sartlar=sartlar,
        detaylar={'yolak': yolak, 'yolak_ad': YOLAK_METADATA[yolak]['ad']})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        # ── G — Gabapentin A(1) ──
        ("G UYGUN (gabapentin, nöropatik, SK heyet nöroloji, reçeteci nöroloji, 3.bas, 6 ay)", {
            'etkin_madde': 'GABAPENTIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G62.9 POLINOROPATI'],
            'heyet_doktorlari': [{'ad': 'Dr A', 'brans': 'Nöroloji'},
                                 {'ad': 'Dr B', 'brans': 'Algoloji'}],
            'rapor_kodu': '1', 'rapor_metni': 'ucuncu basamak 6 ay sureli saglik kurulu',
        }, KontrolSonucu.UYGUN),
        ("G ŞARTLI (gabapentin, nöropatik, reçeteci nöroloji, SK/basamak/süre belirsiz)", {
            'etkin_madde': 'GABAPENTIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['nöropatik ağrı'], 'rapor_kodu': '99',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("G UYGUN DEĞİL (gabapentin, reçeteci aile hekimi)", {
            'etkin_madde': 'GABAPENTIN', 'brans': 'Aile Hekimliği',
            'recete_teshisleri': ['nöropatik ağrı'], 'rapor_kodu': '5',
            'heyet_doktorlari': [{'ad': 'X', 'brans': 'Nöroloji'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("G UYGUN DEĞİL (gabapentin + pregabalin aynı reçete kombi)", {
            'etkin_madde': 'GABAPENTIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['nöropatik ağrı'], 'rapor_kodu': '5',
            'heyet_doktorlari': [{'ad': 'X', 'brans': 'Nöroloji'}],
            'diger_etken_maddeler': ['PREGABALIN'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("G ATLANDI (gabapentin epilepsi → 4.2.25)", {
            'etkin_madde': 'GABAPENTIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
        }, KontrolSonucu.ATLANDI),
        # ── P — Pregabalin ──
        ("P_A2 ŞARTLI (pregabalin, nöropatik, reçeteci romatoloji)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Romatoloji',
            'recete_teshisleri': ['nöropatik ağrı'], 'rapor_kodu': '3',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("P_B2 UYGUN (pregabalin fibromiyalji, SK heyet FTR, reçeteci FTR, 3.bas, 6 ay)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Fiziksel Tıp ve Rehabilitasyon',
            'recete_teshisleri': ['M79.7 FIBROMIYALJI'],
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'FTR'}, {'ad': 'B', 'brans': 'Romatoloji'}],
            'rapor_kodu': '7', 'rapor_metni': 'universite hastanesi 6 ay sureli saglik kurulu raporu',
        }, KontrolSonucu.UYGUN),
        ("P_B2 UYGUN DEĞİL (pregabalin fibromiyalji, reçeteci endokrin — B2 listesinde yok)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Endokrinoloji',
            'recete_teshisleri': ['M79.7 FIBROMIYALJI'], 'rapor_kodu': '7',
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'FTR'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        # 2. basamak (devlet hastanesi) algılanmalı + süre okunamasa da (bilgi) → UYGUN
        ("P_A2 UYGUN (pregabalin nöropatik, 2.basamak devlet hast., süre yok→bilgi)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G62.9 NÖROPATİK AĞRI'], 'rapor_kodu': '8',
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
            'rapor_metni': 'ikinci basamak devlet hastanesi saglik kurulu raporu',
        }, KontrolSonucu.UYGUN),
        # >6 ay süre parse EDİLEN ihlal → (bilgi) değil, düz grupta YOK → UYGUN DEĞİL
        ("P_A2 UYGUN DEĞİL (pregabalin nöropatik, rapor 12 ay >6)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G62.9 NÖROPATİK AĞRI'], 'rapor_kodu': '8',
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
            'rapor_metni': 'ucuncu basamak 12 ay sureli saglik kurulu raporu',
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── D — Duloksetin ──
        ("D_A3 UYGUN (duloksetin diyabetik nöropati, reçeteci endokrin)", {
            'etkin_madde': 'DULOKSETIN', 'brans': 'Endokrinoloji ve Metabolizma',
            'recete_teshisleri': ['E11.4 DIYABETIK NOROPATI'],
        }, KontrolSonucu.UYGUN),
        ("D_A3 UYGUN (duloksetin, aile hek + nöroloji uzman raporu)", {
            'etkin_madde': 'DULOKSETIN', 'brans': 'Aile Hekimliği',
            'recete_teshisleri': ['diyabetik polinöropati'],
            'rapor_kodu': '4', 'rapor_doktor_brans': 'Nöroloji',
        }, KontrolSonucu.UYGUN),
        ("D_A3 UYGUN DEĞİL (duloksetin, reçeteci nöroloji ama 3.basamak değil, rapor yok)", {
            'etkin_madde': 'DULOKSETIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['diyabetik nöropati'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("D_B1 UYGUN (duloksetin fibromiyalji, reçeteci romatoloji)", {
            'etkin_madde': 'DULOKSETIN', 'brans': 'Romatoloji',
            'recete_teshisleri': ['M79.7 FIBROMIYALJI'],
        }, KontrolSonucu.UYGUN),
        ("D delege 4.2.2 (duloksetin depresyon, reçeteci psikiyatri → SNRI UYGUN)", {
            'etkin_madde': 'DULOKSETIN', 'brans': 'Psikiyatri',
            'recete_teshisleri': ['F32.9 DEPRESYON'],
        }, KontrolSonucu.UYGUN),
        ("D delege 4.2.2 (duloksetin SESSİZ, aile hekimi raporsuz → SNRI UYGUN DEĞİL)", {
            'etkin_madde': 'DULOKSETIN', 'ilac_adi': 'DUXET 30MG',
            'brans': 'Aile Hekimliği',
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── AL — Alfa lipoik (Beneday) ──
        ("AL_a UYGUN (BENEDAY diyabetik nöropati, reçeteci endokrin)", {
            'ilac_adi': 'BENEDAY ENTERIK KAPLI TABLET', 'etkin_madde': 'B1+B6+B12',
            'brans': 'Endokrinoloji', 'recete_teshisleri': ['E11.4 DIYABETIK POLINOROPATI'],
        }, KontrolSonucu.UYGUN),
        ("AL_b UYGUN (THIOCTACID nöropatik, aile hek + nöroloji raporu)", {
            'ilac_adi': 'THIOCTACID 600 MG', 'etkin_madde': 'TIOKTIK ASIT',
            'brans': 'Aile Hekimliği', 'recete_teshisleri': ['nöropatik ağrı'],
            'rapor_kodu': '8', 'rapor_doktor_brans': 'Nöroloji',
        }, KontrolSonucu.UYGUN),
        ("AL_a ŞARTLI (BENEDAY, endikasyon var, reçeteci/rapor branşı belirsiz)", {
            'ilac_adi': 'BENEDAY', 'etkin_madde': 'ALFA LİPOİK ASİT',
            'recete_teshisleri': ['diyabetik nöropati'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("AL_b UYGUN DEĞİL (alfa lipoik, reçeteci kardiyoloji, rapor yok)", {
            'ilac_adi': 'INSULIPON', 'etkin_madde': 'ALFA LIPOIK ASIT',
            'brans': 'Kardiyoloji', 'recete_teshisleri': ['nöropatik ağrı'],
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── K — Kapsaisin ──
        ("K UYGUN (kapsaisin krem PHN, reçeteci dermatoloji)", {
            'ilac_adi': 'ZOSTRIX KREM', 'etkin_madde': 'KAPSAISIN',
            'brans': 'Deri ve Zührevi Hastalıkları',
            'recete_teshisleri': ['B02.2 POSTHERPETIK NEVRALJI'],
        }, KontrolSonucu.UYGUN),
        ("K UYGUN DEĞİL (kapsaisin krem osteoartrit endikasyon)", {
            'ilac_adi': 'CAPSIN KREM', 'etkin_madde': 'KAPSAISIN', 'brans': 'Ortopedi',
            'recete_teshisleri': ['M17.9 GONARTROZ OSTEOARTRIT'],
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Kapsam dışı ──
        ("Kapsam dışı (parasetamol)", {'etkin_madde': 'PARASETAMOL'}, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.35 — Nöropatik ağrı / Fibromiyalji — Akıl Testi\n" + "=" * 64)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = noropatik_kontrol_4_2_35(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        if not ok:
            print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 64)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
