# -*- coding: utf-8 -*-
"""SUT 4.2.25 — Antiepileptik ilaçların kullanım ilkeleri (atomik motor).

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:7530-7554`` (mevzuat.gov.tr,
MevzuatNo=17229). Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md
``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``. Kalıp: ``noropatik_4_2_35.py``.

═══════════════════════════════════════════════════════════════════════════
YOLAKLAR (dispatcher: etken madde → ilaç sınıfı)
═══════════════════════════════════════════════════════════════════════════

  YN  → 4.2.25(1)  Yeni nesil (lamotrigin, topiramat, vigabatrin,
                    levetirasetam) — nöroloji/beyin cerrahisi uzmanı VEYA raporu
  ZON → 4.2.25(2)  Zonisamit — nöroloji uzmanı VEYA nöroloji raporu (1 yıl)
  PRE → 4.2.25(3)  Pregabalin (epilepsi) — 2./3. bas. + heyette ≥1 nöroloji +
                    1 yıl SK raporu + reçeteci nöroloji + ¬YAB + ¬gabapentin kombi
  LAK → 4.2.25(4)  Lakozamid — 16 yaş+ ∧ parsiyel epilepsi ∧ ≥2 AEP 6 ay
                    yanıtsız ∧ ek tedavi/monoterapi ∧ nöroloji raporu ∧ reçeteci uzman
  GAB → 4.2.25(5)  Gabapentin (Neurontin) — 2./3. bas. + heyette ≥1 nöroloji +
                    1 yıl SK raporu + reçeteci nöroloji + ¬pregabalin kombi

  Delege (ATLANDI): gabapentin/pregabalin + yalnız NÖROPATİK ağrı (epilepsi/YAB
                    YOK) → SUT 4.2.35 (noropatik_4_2_35.py). Bipolar (lamotrijin)
                    → SUT 4.2.2 (psikiyatri).

  Delege (doğrudan): sodyum valproat — SUT 4.2.25 resmî listesinde YOK
               (epilepside kısıt taşımaz); tek kısıt bipolar endikasyonu →
               valproat_4_2_2_7.py atomik kontrolü çağrılır (2026-07-06).

═══════════════════════════════════════════════════════════════════════════
ATOM TİPLERİ
═══════════════════════════════════════════════════════════════════════════

  uzman_yetki (VEYA)  : (reçeteci ∈ set) ∨ (uzman hekim raporu düzenleyen ∈ set)
                        — YN, ZON yolakları ("uzman VEYA raporu → tüm hekimlerce")
  SK-AND zinciri      : SK raporu ∧ heyet≥1 nöroloji ∧ 2./3.bas ∧ reçeteci nöroloji
                        — PRE, GAB ("SK raporuna istinaden nöroloji uzman hekimlerince")
  parse-zor şartlar   : 2./3. basamak, rapor süresi → KONTROL_EDİLEMEDİ + sartli_atom
                        (örtük kabul YASAK, CLAUDE.md §2.5). Süre → (bilgi) grubu.

Ana entrypoint: ``antiepileptik_kontrol_4_2_25(ilac_sonuc)`` → ``KontrolRaporu``.
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

# 4.2.25(1) yeni nesil
LAMOTRIJIN_ETKEN = {'LAMOTRIJIN', 'LAMOTRIGIN', 'LAMOTRIGINE'}
LAMOTRIJIN_TICARI = {'LAMICTAL', 'LAMOTRIX', 'LAMODEX', 'LAMOXEL', 'LAMICTAN'}
TOPIRAMAT_ETKEN = {'TOPIRAMAT', 'TOPIRAMATE'}
TOPIRAMAT_TICARI = {'TOPAMAX', 'TOPAMAC', 'EXOTRA', 'TOPIROL', 'TOPISEC'}
VIGABATRIN_ETKEN = {'VIGABATRIN', 'VIGABATRINE'}
VIGABATRIN_TICARI = {'SABRIL'}
LEVETIRASETAM_ETKEN = {'LEVETIRASETAM', 'LEVATIRASETAM', 'LEVETIRACETAM'}
LEVETIRASETAM_TICARI = {'KEPPRA', 'LEVEBON', 'EPITERRA', 'LEVADRA', 'LEVROUS',
                        'TIRASETAM', 'EPILEV'}

# 4.2.25(2) zonisamit
ZONISAMIT_ETKEN = {'ZONISAMID', 'ZONISAMIT', 'ZONISAMIDE'}
ZONISAMIT_TICARI = {'ZONEGRAN'}

# 4.2.25(3) pregabalin / 4.2.25(5) gabapentin
PREGABALIN_ETKEN = {'PREGABALIN', 'PREGABALINE'}
PREGABALIN_TICARI = {'LYRICA', 'GABRICA', 'PREGALIN', 'PREGABEX',
                     'PREJUNTIN', 'PREGABA', 'PREGANANT', 'NETGABA'}
GABAPENTIN_ETKEN = {'GABAPENTIN', 'GABAPENTINE'}
GABAPENTIN_TICARI = {'NEURONTIN', 'NERUDA', 'GABATEVA', 'GABALEPT',
                     'GABANTIN', 'GABAGAMMA', 'EPLERONT', 'GABAX'}

# 4.2.25(4) lakozamid
LAKOZAMID_ETKEN = {'LAKOSAMID', 'LAKOZAMID', 'LACOSAMID', 'LACOSAMIDE'}
LAKOZAMID_TICARI = {'VIMPAT', 'LAKOZ'}


# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower alt-string)
# ═══════════════════════════════════════════════════════════════════════
NOROLOJI = ['noroloji', 'norolog']
BEYIN_CER = ['beyin cerrah', 'norosirurji', 'sinir cerrah']
PRATISYEN = ['aile hek', 'pratisyen', 'genel pratisyen']

NOR_BC = NOROLOJI + BEYIN_CER


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar (noropatik_4_2_35.py ile aynı sözleşme)
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


def _receteci_brans(ilac_sonuc: Dict) -> str:
    return (ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or '')


def _yas(ilac_sonuc: Dict) -> Optional[int]:
    """Yaş YALNIZ DB'den okunur (rapor metninden okuma YASAK — CLAUDE.md feedback)."""
    for anahtar in ('yas', 'hasta_yasi', 'hasta_yas'):
        v = ilac_sonuc.get(anahtar)
        if v is None or str(v).strip() == '':
            continue
        try:
            return int(str(v).strip())
        except (ValueError, TypeError):
            continue
    return None


def _3basamak(ilac_sonuc: Dict) -> Optional[bool]:
    """Rapor/tesis 2./3. basamak mı? True / None(belirsiz)."""
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
    d['epilepsi'] = (
        any(k in metin for k in ('epilepsi', 'epilept', 'konvulsiy', 'nobet',
                                 'parsiyel', 'fokal', 'jeneralize', 'absans'))
        or bool(re.search(r'\bG40', icd)))
    d['parsiyel'] = (
        any(k in metin for k in ('parsiyel', 'fokal', 'parsiyel baslangic'))
        or bool(re.search(r'\bG40\.?[012]', icd)))
    d['yab'] = (
        any(k in metin for k in ('yaygin anksiyete', 'generalize anksiyete'))
        or bool(re.search(r'\bF41', icd)))
    d['bipolar'] = (
        any(k in metin for k in ('bipolar', 'manik', 'mani '))
        or bool(re.search(r'\bF3[01]', icd)))
    d['noropatik'] = (
        any(k in metin for k in ('noropatik', 'noropati', 'nevralji', 'nevralgia',
                                 'postherpetik', 'diyabetik noropati', 'polinoropati'))
        or bool(re.search(r'\bG5[0-9]|\bG6[0-4]|\bM79\.?2|\bB02\.?2', icd)))
    return d


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════

def antiepileptik_yolak_belirle(ilac_sonuc: Dict) -> Dict[str, Optional[str]]:
    """{'durum': 'yolak'|'atlandi'|'disi', 'yolak': str|None, 'mesaj': str}."""
    m = _arama_metni(ilac_sonuc)
    e = _endikasyonlar(ilac_sonuc)

    # ── Yeni nesil → (1) ──
    if (_iceriyor(m, LAMOTRIJIN_ETKEN) or _iceriyor(m, LAMOTRIJIN_TICARI)):
        if e['bipolar'] and not e['epilepsi']:
            return {'durum': 'atlandi', 'yolak': None,
                    'mesaj': 'Lamotrijin bipolar endikasyonunda — SUT 4.2.2 '
                             '(psikiyatri) butonunda kontrol edilir'}
        return {'durum': 'yolak', 'yolak': 'YN', 'mesaj': ''}
    if (_iceriyor(m, TOPIRAMAT_ETKEN) or _iceriyor(m, TOPIRAMAT_TICARI)
            or _iceriyor(m, VIGABATRIN_ETKEN) or _iceriyor(m, VIGABATRIN_TICARI)
            or _iceriyor(m, LEVETIRASETAM_ETKEN) or _iceriyor(m, LEVETIRASETAM_TICARI)):
        return {'durum': 'yolak', 'yolak': 'YN', 'mesaj': ''}

    # ── Zonisamit → (2) ──
    if _iceriyor(m, ZONISAMIT_ETKEN) or _iceriyor(m, ZONISAMIT_TICARI):
        return {'durum': 'yolak', 'yolak': 'ZON', 'mesaj': ''}

    # ── Lakozamid → (4) ──
    if _iceriyor(m, LAKOZAMID_ETKEN) or _iceriyor(m, LAKOZAMID_TICARI):
        return {'durum': 'yolak', 'yolak': 'LAK', 'mesaj': ''}

    # ── Pregabalin → (3) / nöropatik ise 4.2.35'e delege ──
    if _iceriyor(m, PREGABALIN_ETKEN) or _iceriyor(m, PREGABALIN_TICARI):
        if e['noropatik'] and not (e['epilepsi'] or e['yab']):
            return {'durum': 'atlandi', 'yolak': None,
                    'mesaj': 'Pregabalin nöropatik ağrı endikasyonunda — SUT 4.2.35 '
                             '(nöropatik) butonunda kontrol edilir'}
        return {'durum': 'yolak', 'yolak': 'PRE', 'mesaj': ''}

    # ── Gabapentin → (5) / nöropatik ise 4.2.35'e delege ──
    if _iceriyor(m, GABAPENTIN_ETKEN) or _iceriyor(m, GABAPENTIN_TICARI):
        if e['noropatik'] and not (e['epilepsi'] or e['yab']):
            return {'durum': 'atlandi', 'yolak': None,
                    'mesaj': 'Gabapentin nöropatik ağrı endikasyonunda — SUT 4.2.35 '
                             '(nöropatik) butonunda kontrol edilir'}
        return {'durum': 'yolak', 'yolak': 'GAB', 'mesaj': ''}

    # ── Valproat → SUT 4.2.2(7) delege (2026-07-06) ──
    # 4.2.25 resmî listesinde YOK; tek kısıt bipolar endikasyonu (4.2.2(7)).
    # Önceki davranış: 'disi' → runner kontrol_psikiyatri'nin yüzeysel
    # valproat dalına düşürüyordu; artık atomik motor sonucu döner.
    from recete_kontrol.valproat_4_2_2_7 import valproat_kapsami_mi
    if valproat_kapsami_mi(ilac_sonuc):
        return {'durum': 'delege_valproat', 'yolak': None,
                'mesaj': 'Valproat — SUT 4.2.2(7) atomik kontrolüne delege'}

    return {'durum': 'disi', 'yolak': None,
            'mesaj': 'SUT 4.2.25 (antiepileptik) kapsamında değil'}


# ═══════════════════════════════════════════════════════════════════════
# ORTAK ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

def atom_uzman_yetki(ilac_sonuc: Dict, brans_list: List[str], grup: str) -> List[SartSonuc]:
    """(reçeteci ∈ list) ∨ (uzman hekim raporu düzenleyen ∈ list) → veya_grubu.

    YN/ZON: 'uzman hekimleri tarafından VEYA bu uzmanların raporuna dayanılarak
    tüm hekimlerce'.
    """
    s: List[SartSonuc] = []
    brans = _receteci_brans(ilac_sonuc)
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


def atom_sk_raporu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Sağlık kurulu raporu var mı? (PRE/GAB zorunlu)."""
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


def atom_heyet_brans(ilac_sonuc: Dict, brans_list: List[str], grup: str,
                     etiket: str = 'Heyette uygun uzman (≥1)') -> SartSonuc:
    """Heyette ≥1 uygun branş uzmanı (SUT: 'en az birinin yer aldığı')."""
    heyet = [b for b in _heyet_brans_listesi(ilac_sonuc) if b]
    if any(_brans_listede(b, brans_list) for b in heyet):
        return SartSonuc(ad=etiket, durum=SartDurumu.VAR,
                         neden='Sağlık kurulunda SUT branşı (nöroloji) var',
                         kaynak='rapor_heyet', grup=grup)
    if not heyet:
        return SartSonuc(ad=etiket, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Heyet branş bilgisi okunamadı — manuel',
                         kaynak='rapor_heyet', grup=grup, sartli_atom=True)
    return SartSonuc(ad=etiket, durum=SartDurumu.YOK,
                     neden='Sağlık kurulunda SUT\'ta sayılan branş (nöroloji) yok',
                     kaynak='rapor_heyet', grup=grup)


def atom_receteci_brans(ilac_sonuc: Dict, brans_list: List[str], grup: str,
                        etiket_yok: str = 'SUT\'ta sayılan uzman branşı değil') -> SartSonuc:
    """Reçete eden hekim SUT branş listesinde mi? (PRE/GAB: 'nöroloji uzman hekimlerince')."""
    brans = _receteci_brans(ilac_sonuc)
    if not _brans_l(brans):
        return SartSonuc(ad='Reçete eden uygun branş', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, brans_list):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='SUT\'ta sayılan uzman branşı reçete edebilir',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden=etiket_yok, kaynak='hekim_brans', grup=grup)


def atom_receteci_uzman(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Reçete eden 'uzman hekim' mi? (LAK: 'tüm uzman hekimlerce'). Pratisyen → YOK."""
    brans = _receteci_brans(ilac_sonuc)
    if not _brans_l(brans):
        return SartSonuc(ad='Reçete eden uzman hekim', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, PRATISYEN):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                         neden='Pratisyen/aile hekimi — lakozamid yalnız uzman hekimlerce',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans} (uzman)', durum=SartDurumu.VAR,
                     neden='Uzman hekim reçete edebilir',
                     kaynak='hekim_brans', grup=grup)


def atom_basamak(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """2./3. basamak SHS şartı (parse zor → KE + şartlı)."""
    if _3basamak(ilac_sonuc) is True:
        return SartSonuc(ad='2./3. basamak sağlık hizmeti sunucusu', durum=SartDurumu.VAR,
                         neden='Raporda 2./3. basamak/üniversite/EAH ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='2./3. basamak sağlık hizmeti sunucusu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Raporun düzenlendiği basamak metinden doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_sure_1yil_bilgi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """1 yıl süreli rapor (parse zor → KE; (bilgi) grubunda matematiği bozmaz)."""
    metin = _rapor_metni(ilac_sonuc)
    m = re.search(r'(\d{1,2})\s*(ay|yil)\s*sur', metin)
    if m:
        birim = m.group(2)
        try:
            deger = int(m.group(1))
            if (birim == 'yil' and deger >= 1) or (birim == 'ay' and deger >= 12):
                return SartSonuc(ad='Rapor süresi 1 yıl', durum=SartDurumu.VAR,
                                 neden='1 yıl süreli rapor ibaresi',
                                 kaynak='rapor_metni', grup=grup)
        except ValueError:
            pass
    return SartSonuc(ad='Rapor süresi 1 yıl', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor süresi (1 yıl) metinden okunamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


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


def atom_yab_yasak(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Pregabalin YAB endikasyonunda ödenmez (NEGATİF: YAB varsa YOK)."""
    e = _endikasyonlar(ilac_sonuc)
    if e['yab']:
        return SartSonuc(ad='Endikasyon yaygın anksiyete bozukluğu (YAB) değil',
                         durum=SartDurumu.YOK,
                         neden='Yaygın anksiyete bozukluğu endikasyonunda bedeli karşılanmaz',
                         kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad='Endikasyon yaygın anksiyete bozukluğu (YAB) değil',
                     durum=SartDurumu.VAR,
                     neden='YAB endikasyonu tespit edilmedi',
                     kaynak='ICD+rapor', grup=grup)


# ── LAK'a özel klinik atomlar ──

def atom_yas_16(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    yas = _yas(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad='Yaş ≥ 16', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı bilinmiyor — manuel',
                         kaynak='hasta_yas', grup=grup, sartli_atom=True)
    if yas >= 16:
        return SartSonuc(ad=f'Yaş {yas} (≥16)', durum=SartDurumu.VAR,
                         neden='16 yaş ve üzeri', kaynak='hasta_yas', grup=grup)
    return SartSonuc(ad=f'Yaş {yas} (<16)', durum=SartDurumu.YOK,
                     neden='Lakozamid 16 yaş altı endikasyon dışı',
                     kaynak='hasta_yas', grup=grup)


def atom_parsiyel_epilepsi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    e = _endikasyonlar(ilac_sonuc)
    if e['parsiyel']:
        return SartSonuc(ad='Parsiyel başlangıçlı epilepsi', durum=SartDurumu.VAR,
                         neden='Parsiyel/fokal başlangıçlı epilepsi (ICD/metin)',
                         kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad='Parsiyel başlangıçlı epilepsi', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Parsiyel başlangıçlı epilepsi endikasyonu net okunamadı — manuel',
                     kaynak='ICD+rapor', grup=grup, sartli_atom=True)


def atom_2aep_6ay_yanitsiz(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    iki_aep = any(k in metin for k in ('iki antiepileptik', '2 antiepileptik',
                                       'iki antiepileptik ilac', 'iki aei', '2 aei',
                                       'iki ilac', 'en az iki'))
    yanitsiz = any(k in metin for k in ('yanit alinamayan', 'yanit alinamadi',
                                        'tedaviye yanitsiz', 'direncli', 'dirençli',
                                        'cevap alinamayan'))
    if iki_aep and (yanitsiz or '6 ay' in metin or 'alti ay' in metin):
        return SartSonuc(ad='≥2 antiepileptik 6 ay yanıtsız', durum=SartDurumu.VAR,
                         neden='En az iki antiepileptik 6 ay süre tedaviye yanıtsızlık ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='≥2 antiepileptik 6 ay yanıtsız', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='≥2 AEP 6 ay yanıtsızlık ibaresi raporda doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_lak_noroloji_raporu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """LAK: nöroloji uzman hekim raporuna dayanılarak (rapor düzenleyen nöroloji)."""
    adaylar = _rapor_brans_adaylar(ilac_sonuc)
    if any(_brans_listede(a, NOROLOJI) for a in adaylar):
        return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.VAR,
                         neden='Nöroloji uzman hekiminin düzenlediği rapor',
                         kaynak='rapor_brans', grup=grup)
    if _rapor_var(ilac_sonuc) and not any(_brans_l(a) for a in adaylar):
        return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor var ama düzenleyen branşı okunamadı — manuel',
                         kaynak='rapor_brans', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.YOK,
                     neden='Nöroloji uzman hekim raporu yok',
                     kaynak='rapor_brans', grup=grup)


# ═══════════════════════════════════════════════════════════════════════
# YOLAK FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════════

def yn_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """4.2.25(1) Yeni nesil: nöroloji/beyin cerrahisi uzmanı VEYA raporu."""
    return atom_uzman_yetki(
        ilac_sonuc, NOR_BC,
        grup='(1) Nöroloji/beyin cerrahisi uzmanı veya raporu (≥1)')


def zon_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """4.2.25(2) Zonisamit: nöroloji uzmanı VEYA nöroloji raporu (1 yıl)."""
    s: List[SartSonuc] = []
    s.extend(atom_uzman_yetki(
        ilac_sonuc, NOROLOJI,
        grup='(2) Nöroloji uzmanı veya nöroloji raporu (≥1)'))
    # 1 yıl süre — yalnız rapor yolunda geçerli → (bilgi) grubu, matematiği bozmaz
    s.append(atom_sure_1yil_bilgi(
        ilac_sonuc, grup='(2) Rapor süresi 1 yıl (bilgi)'))
    return s


def pre_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """4.2.25(3) Pregabalin (epilepsi)."""
    s: List[SartSonuc] = []
    s.append(atom_sk_raporu(ilac_sonuc, grup='(3) Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, NOROLOJI, grup='(3) Heyette nöroloji uzmanı (≥1)'))
    s.append(atom_basamak(ilac_sonuc, grup='(3) 2./3. basamak SHS'))
    s.append(atom_sure_1yil_bilgi(ilac_sonuc, grup='(3) Rapor süresi 1 yıl (bilgi)'))
    s.append(atom_receteci_brans(ilac_sonuc, NOROLOJI, grup='(3) Reçete eden nöroloji uzmanı',
                                 etiket_yok='Nöroloji uzmanı değil — pregabalin\'i yazamaz'))
    s.append(atom_yab_yasak(ilac_sonuc, grup='(3) YAB endikasyonu yasağı'))
    s.append(atom_kombi_yasak(ilac_sonuc, bu_pregabalin=True,
                              grup='(3) Pregabalin+gabapentin kombi yasağı'))
    return s


def lak_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """4.2.25(4) Lakozamid."""
    s: List[SartSonuc] = []
    s.append(atom_yas_16(ilac_sonuc, grup='(4) Yaş ≥16'))
    s.append(atom_parsiyel_epilepsi(ilac_sonuc, grup='(4) Parsiyel başlangıçlı epilepsi'))
    s.append(atom_2aep_6ay_yanitsiz(ilac_sonuc, grup='(4) ≥2 AEP 6 ay yanıtsız'))
    s.append(atom_lak_noroloji_raporu(ilac_sonuc, grup='(4) Nöroloji uzman hekim raporu'))
    s.append(atom_receteci_uzman(ilac_sonuc, grup='(4) Reçete eden uzman hekim'))
    return s


def gab_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """4.2.25(5) Gabapentin (Neurontin)."""
    s: List[SartSonuc] = []
    s.append(atom_sk_raporu(ilac_sonuc, grup='(5) Sağlık kurulu raporu'))
    s.append(atom_heyet_brans(ilac_sonuc, NOROLOJI, grup='(5) Heyette nöroloji uzmanı (≥1)'))
    s.append(atom_basamak(ilac_sonuc, grup='(5) 2./3. basamak SHS'))
    s.append(atom_sure_1yil_bilgi(ilac_sonuc, grup='(5) Rapor süresi 1 yıl (bilgi)'))
    s.append(atom_receteci_brans(ilac_sonuc, NOROLOJI, grup='(5) Reçete eden nöroloji uzmanı',
                                 etiket_yok='Nöroloji uzmanı değil — gabapentin\'i yazamaz'))
    s.append(atom_kombi_yasak(ilac_sonuc, bu_pregabalin=False,
                              grup='(5) Pregabalin+gabapentin kombi yasağı'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (noropatik_4_2_35 / parkinson_4_2_36 ile aynı motor)
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
    parcalar = [f"SUT {meta.get('sut', '4.2.25')} / {meta.get('ad', yolak)}"]
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
    'YN': yn_kontrol, 'ZON': zon_kontrol, 'PRE': pre_kontrol,
    'LAK': lak_kontrol, 'GAB': gab_kontrol,
}
YOLAK_METADATA = {
    'YN':  {'ad': 'Yeni nesil (lamotrigin/topiramat/vigabatrin/levetirasetam)',
            'sut': '4.2.25(1)'},
    'ZON': {'ad': 'Zonisamit', 'sut': '4.2.25(2)'},
    'PRE': {'ad': 'Pregabalin (epilepsi)', 'sut': '4.2.25(3)'},
    'LAK': {'ad': 'Lakozamid', 'sut': '4.2.25(4)'},
    'GAB': {'ad': 'Gabapentin', 'sut': '4.2.25(5)'},
}


def antiepileptik_kontrol_4_2_25(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.25 (antiepileptik ilaçlar) ana kontrol fonksiyonu."""
    karar = antiepileptik_yolak_belirle(ilac_sonuc)
    if karar['durum'] == 'disi':
        return KontrolRaporu(sonuc=KontrolSonucu.ATLANDI, mesaj=karar['mesaj'],
                             sut_kurali='SUT 4.2.25')
    if karar['durum'] == 'atlandi':
        return KontrolRaporu(sonuc=KontrolSonucu.ATLANDI, mesaj=karar['mesaj'],
                             sut_kurali='SUT 4.2.25 (başka maddeye delege)')
    if karar['durum'] == 'delege_valproat':
        # Valproat 4.2.25 listesinde yok → SUT 4.2.2(7) atomik kontrolü
        from recete_kontrol.valproat_4_2_2_7 import valproat_kontrol_4_2_2_7
        return valproat_kontrol_4_2_2_7(ilac_sonuc)

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
        # ── YN — Yeni nesil (1) ──
        ("YN UYGUN (levetirasetam, reçeteci nöroloji)", {
            'etkin_madde': 'LEVETIRASETAM', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
        }, KontrolSonucu.UYGUN),
        ("YN UYGUN (topiramat, aile hek + beyin cerrahisi raporu)", {
            'etkin_madde': 'TOPIRAMAT', 'brans': 'Aile Hekimliği',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
            'rapor_kodu': '5', 'rapor_doktor_brans': 'Beyin Cerrahisi',
        }, KontrolSonucu.UYGUN),
        ("YN UYGUN DEĞİL (vigabatrin, aile hek, rapor yok)", {
            'etkin_madde': 'VIGABATRIN', 'brans': 'Aile Hekimliği',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("YN ŞARTLI (lamotrijin epilepsi, aile hek + rapor branşı bilinmiyor)", {
            'etkin_madde': 'LAMOTRIJIN', 'brans': 'Aile Hekimliği',
            'recete_teshisleri': ['G40.9 EPILEPSI'], 'rapor_kodu': '7',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("YN ATLANDI (lamotrijin bipolar → 4.2.2)", {
            'etkin_madde': 'LAMOTRIJIN', 'brans': 'Psikiyatri',
            'recete_teshisleri': ['F31.9 BIPOLAR'],
        }, KontrolSonucu.ATLANDI),
        # ── ZON — Zonisamit (2) ──
        ("ZON UYGUN (zonisamit, reçeteci nöroloji)", {
            'etkin_madde': 'ZONISAMIT', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G40.2 PARSIYEL EPILEPSI'],
        }, KontrolSonucu.UYGUN),
        ("ZON UYGUN DEĞİL (zonisamit, reçeteci dahiliye, rapor yok)", {
            'etkin_madde': 'ZONISAMID', 'brans': 'İç Hastalıkları',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── PRE — Pregabalin (3) ──
        ("PRE UYGUN (pregabalin epilepsi, SK heyet nöroloji, reçeteci nöroloji, 3.bas, 1yıl)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
            'rapor_kodu': '3', 'rapor_metni': 'ucuncu basamak 1 yil sureli saglik kurulu',
        }, KontrolSonucu.UYGUN),
        ("PRE ŞARTLI (pregabalin epilepsi, reçeteci nöroloji, basamak/süre belirsiz)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G40.9 EPILEPSI'], 'rapor_kodu': '3',
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("PRE UYGUN DEĞİL (pregabalin YAB endikasyonu)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['F41.1 YAYGIN ANKSIYETE'],
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
            'rapor_kodu': '3', 'rapor_metni': '3. basamak 1 yil saglik kurulu',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("PRE UYGUN DEĞİL (pregabalin + gabapentin kombi)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
            'rapor_kodu': '3', 'rapor_metni': '3. basamak 1 yil saglik kurulu',
            'diger_etken_maddeler': ['GABAPENTIN'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("PRE UYGUN DEĞİL (pregabalin epilepsi, reçeteci romatoloji)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Romatoloji',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
            'rapor_kodu': '3', 'rapor_metni': '3. basamak 1 yil saglik kurulu',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("PRE ATLANDI (pregabalin nöropatik → 4.2.35)", {
            'etkin_madde': 'PREGABALIN', 'brans': 'Romatoloji',
            'recete_teshisleri': ['nöropatik ağrı'],
        }, KontrolSonucu.ATLANDI),
        # ── LAK — Lakozamid (4) ──
        ("LAK UYGUN (lakozamid, 30 yaş, parsiyel, 2 AEP 6 ay yanıtsız, nöroloji raporu, uzman reçete)", {
            'etkin_madde': 'LAKOSAMID', 'brans': 'Nöroloji', 'yas': 30,
            'recete_teshisleri': ['G40.1 PARSIYEL EPILEPSI'],
            'rapor_kodu': '9', 'rapor_doktor_brans': 'Nöroloji',
            'rapor_metni': 'iki antiepileptik ilac 6 ay tedaviye yanit alinamayan parsiyel',
        }, KontrolSonucu.UYGUN),
        ("LAK UYGUN DEĞİL (lakozamid 12 yaş)", {
            'etkin_madde': 'LAKOSAMID', 'brans': 'Nöroloji', 'yas': 12,
            'recete_teshisleri': ['G40.1 PARSIYEL EPILEPSI'],
            'rapor_kodu': '9', 'rapor_doktor_brans': 'Nöroloji',
            'rapor_metni': 'iki antiepileptik 6 ay yanit alinamayan',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("LAK UYGUN DEĞİL (lakozamid, reçeteci aile hekimi)", {
            'etkin_madde': 'LAKOSAMID', 'brans': 'Aile Hekimliği', 'yas': 40,
            'recete_teshisleri': ['G40.1 PARSIYEL EPILEPSI'],
            'rapor_kodu': '9', 'rapor_doktor_brans': 'Nöroloji',
            'rapor_metni': 'iki antiepileptik 6 ay yanit alinamayan',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("LAK ŞARTLI (lakozamid, yaş bilinmiyor, klinik ibareler belirsiz)", {
            'etkin_madde': 'LAKOSAMID', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
            'rapor_kodu': '9', 'rapor_doktor_brans': 'Nöroloji',
        }, KontrolSonucu.SARTLI_UYGUN),
        # ── GAB — Gabapentin / Neurontin (5) ──
        ("GAB UYGUN (NEURONTIN epilepsi, SK heyet nöroloji, reçeteci nöroloji, 3.bas, 1yıl)", {
            'ilac_adi': 'NEURONTIN 600 MG', 'etkin_madde': 'GABAPENTIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
            'rapor_kodu': '5', 'rapor_metni': 'ucuncu basamak 1 yil sureli saglik kurulu raporu',
        }, KontrolSonucu.UYGUN),
        ("GAB ŞARTLI (NEURONTIN epilepsi, reçeteci nöroloji, basamak/süre belirsiz)", {
            'ilac_adi': 'NEURONTIN', 'etkin_madde': 'GABAPENTIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G40.9 EPILEPSI'], 'rapor_kodu': '5',
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("GAB UYGUN DEĞİL (gabapentin + pregabalin kombi)", {
            'etkin_madde': 'GABAPENTIN', 'brans': 'Nöroloji',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
            'rapor_kodu': '5', 'rapor_metni': '3. basamak 1 yil saglik kurulu',
            'diger_etken_maddeler': ['PREGABALIN'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("GAB UYGUN DEĞİL (gabapentin epilepsi, reçeteci aile hekimi)", {
            'etkin_madde': 'GABAPENTIN', 'brans': 'Aile Hekimliği',
            'recete_teshisleri': ['G40.9 EPILEPSI'],
            'heyet_doktorlari': [{'ad': 'A', 'brans': 'Nöroloji'}],
            'rapor_kodu': '5', 'rapor_metni': '3. basamak 1 yil saglik kurulu',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("GAB ATLANDI (NEURONTIN nöropatik → 4.2.35)", {
            'ilac_adi': 'NEURONTIN', 'etkin_madde': 'GABAPENTIN', 'brans': 'Algoloji',
            'recete_teshisleri': ['nöropatik ağrı'],
        }, KontrolSonucu.ATLANDI),
        # ── Valproat → 4.2.2(7) delege (2026-07-06) ──
        ("Valproat delege (epilepsi → 4.2.2(7) kısıtsız UYGUN)", {
            'etkin_madde': 'VALPROAT', 'recete_teshisleri': ['G40.9 EPILEPSI'],
        }, KontrolSonucu.UYGUN),
        ("Valproat delege (bipolar + aile hekimi raporsuz → UYGUN DEĞİL)", {
            'etkin_madde': 'VALPROIK ASIT', 'brans': 'Aile Hekimliği',
            'recete_teshisleri': ['F31 BIPOLAR BOZUKLUK'],
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Kapsam dışı ──
        ("Kapsam dışı (parasetamol)", {'etkin_madde': 'PARASETAMOL'}, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.25 — Antiepileptik ilaçlar — Akıl Testi\n" + "=" * 64)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = antiepileptik_kontrol_4_2_25(ilac_sonuc)
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
