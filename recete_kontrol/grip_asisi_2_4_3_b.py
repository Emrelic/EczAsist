# -*- coding: utf-8 -*-
"""SUT 2.4.3-B — Grip (influenza) aşısı bedelinin karşılanması.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:1313-1319`` (mevzuat.gov.tr,
MevzuatNo=17229; Değişik:RG-26/11/2016-29900). Protokol:
``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ``ATOMİK DEVRE ŞEMASI
PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
SUT LAFZI (özet)
═══════════════════════════════════════════════════════════════════════════
Grip aşısı bedeli;
  • 65 yaş ve üzerindeki kişiler ile yaşlı bakımevi ve huzurevinde kalan
    kişilerin bu durumlarını belgelendirmeleri halinde SAĞLIK RAPORU
    ARANMAKSIZIN;
  • gebeliğin 2. veya 3. trimesterinde olan gebeler, astım dâhil kronik
    pulmoner ve kardiyovasküler sistem hastalığı olanlar, diyabet dâhil
    herhangi bir kronik metabolik hastalığı, kronik renal disfonksiyonu,
    hemoglobinopatisi veya immün yetmezliği olan veya immünsupresif tedavi
    alanlar ile 6 ay - 18 yaş arasında olan ve uzun süreli asetil salisilik
    asit tedavisi alan çocuk ve adolesanların hastalıklarını/gebelik durumunu
    belirten SAĞLIK RAPORUNA DAYANILARAK;
tüm hekimlerce her Eylül ilâ Mart dönemleri içerisinde reçete edildiğinde
BİR DEFAYA MAHSUS olmak üzere karşılanır.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (üst-VEYA: ‖A‖ raporsuz yol / ‖B‖ raporlu yol)
═══════════════════════════════════════════════════════════════════════════

  KARŞILANIR ⇔ (YOL_A ∨ YOL_B) ∧ DÖNEM(Eylül–Mart)
               ∧ BİR_DEFA(sezon)[bilgi] ∧ TÜM_HEKİM[bilgi]

  YOL_A (rapor ARANMAZ) ⇔ A1(yaş ≥ 65) ∨ A2(huzurevi/bakımevi belgesi)

  YOL_B (rapora DAYALI) ⇔ RİSK_GRUBU(≥1) ∧ B_RAPOR(sağlık raporu VAR)
     RİSK_GRUBU ⇔ R1(gebe 2./3. trim) ∨ R2(astım dâhil kr.pulmoner/KV)
                ∨ R3(DM dâhil kr.metabolik) ∨ R4(kr.renal disfonksiyon)
                ∨ R5(hemoglobinopati) ∨ R6(immün yetmezlik ∨ immünsupresif)
                ∨ R7(6ay–18 yaş ∧ uzun süreli ASA tedavisi)

Sessizlik = KONTROL_EDİLEMEDİ (örtük kabul YASAK). Risk atomları ve A2
huzurevi belgesi `sartli_atom` ile işaretlenir → ŞARTLI UYGUN. DÖNEM (Eylül-
Mart) reçete tarihinden otomatik; dönem dışı → UYGUN DEĞİL. "Bir defaya
mahsus" sezon takibi yapılamadığından KE/bilgi (manuel doğrulama).

Ana entrypoint: ``grip_asisi_kontrol_2_4_3_b(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# KAPSAM — grip (influenza) aşısı tespiti
# ═══════════════════════════════════════════════════════════════════════
# ATC J07BB* influenza aşıları (J07BB01 whole-virus, J07BB02 split/surface,
# J07BB03 canlı atenüe). Amantadin influenza profilaksisi N04BB01'dir →
# çakışmaz; pnömokok J07AL / hepatit A J07BC ile de çakışmaz.
_ATC_RE = re.compile(r'J07BB')

GRIP_TICARI = {
    'INFLUVAC', 'VAXIGRIP', 'FLUARIX', 'FLUAD', 'INFLEXAL', 'EFLUELDA',
    'FLUCELVAX', 'INFLUVAC TETRA', 'VAXIGRIP TETRA', 'FLUARIX TETRA',
}


def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def grip_asisi_kapsamda_mi(ilac_sonuc: Dict) -> bool:
    """ATC J07BB* veya bilinen grip aşısı ticari adı / etken lafzı."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if _ATC_RE.search(atc):
        return True
    m = _arama_metni(ilac_sonuc)
    if any(norm_tr_upper(t) in m for t in GRIP_TICARI):
        return True
    # Etken/ad lafzı: "INFLUENZA/GRIP" + "ASI/VAKSIN"
    influenza = ('INFLUENZA' in m) or ('GRIP' in m)
    asi = ('ASI' in m) or ('VAKSIN' in m) or ('VACCINE' in m)
    return influenza and asi


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

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


def _rapor_var(ilac_sonuc: Dict) -> bool:
    return bool((ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
                or (ilac_sonuc.get('rapor_takip_no') or ilac_sonuc.get('rap_tak_no') or '').strip())


def _yas_int(ilac_sonuc: Dict) -> Optional[int]:
    """hasta_yasi / yas alanından ilk tam sayı (yıl)."""
    for anahtar in ('hasta_yasi', 'yas'):
        v = ilac_sonuc.get(anahtar)
        if v is None or v == '':
            continue
        m = re.search(r'\d+', str(v))
        if m:
            try:
                return int(m.group())
            except ValueError:
                continue
    return None


def _recete_ay(ilac_sonuc: Dict) -> Optional[int]:
    """Reçete tarihinin ay'ı (1-12). rec_tar 'dd.mm.yyyy' / donem 'YYYY-MM'."""
    rt = (ilac_sonuc.get('rec_tar') or ilac_sonuc.get('recete_tarihi')
          or ilac_sonuc.get('tarih') or '').strip()
    m = re.match(r'\d{1,2}\.(\d{1,2})\.\d{4}', rt)
    if m:
        try:
            ay = int(m.group(1))
            if 1 <= ay <= 12:
                return ay
        except ValueError:
            pass
    donem = (ilac_sonuc.get('donem') or '').strip()  # 'YYYY-MM'
    m = re.match(r'\d{4}-(\d{1,2})', donem)
    if m:
        try:
            ay = int(m.group(1))
            if 1 <= ay <= 12:
                return ay
        except ValueError:
            pass
    return None


# ═══════════════════════════════════════════════════════════════════════
# YOL_A atomları (rapor aranmaz) ‖A‖
# ═══════════════════════════════════════════════════════════════════════

def atom_a1_yas65(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    yas = _yas_int(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad='65 yaş ve üzeri', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı bilinmiyor — manuel', kaynak='DB_yas',
                         grup=grup, veya_grubu=True, sartli_atom=True)
    if yas >= 65:
        return SartSonuc(ad=f'65 yaş ve üzeri (yaş {yas})', durum=SartDurumu.VAR,
                         neden='65 yaş ve üzeri — rapor aranmaksızın karşılanır',
                         kaynak='DB_yas', grup=grup, veya_grubu=True)
    return SartSonuc(ad=f'65 yaş ve üzeri (yaş {yas})', durum=SartDurumu.YOK,
                     neden='65 yaş altı — bu yol için yaş kriteri sağlanmıyor',
                     kaynak='DB_yas', grup=grup, veya_grubu=True)


def atom_a2_huzurevi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in ('huzurevi', 'bakimevi', 'yasli bakim',
                                'yasli bakimevi')):
        return SartSonuc(ad='Yaşlı bakımevi / huzurevinde kalıyor (belge)',
                         durum=SartDurumu.VAR,
                         neden='Huzurevi/bakımevi ibaresi — belgelendirilirse rapor aranmaz',
                         kaynak='rapor_metni', grup=grup, veya_grubu=True)
    return SartSonuc(ad='Yaşlı bakımevi / huzurevinde kalıyor (belge)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Huzurevi/bakımevi durum belgesi sistemde yok — manuel',
                     kaynak='rapor_metni', grup=grup, veya_grubu=True, sartli_atom=True)


def yol_a_atomlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    grup = '(2.4.3-B/a) 65 yaş ∨ huzurevi — rapor aranmaz (≥1) ‖A‖'
    return [atom_a1_yas65(ilac_sonuc, grup),
            atom_a2_huzurevi(ilac_sonuc, grup)]


# ═══════════════════════════════════════════════════════════════════════
# YOL_B risk grubu atomları (rapora dayalı) ‖B‖ — OR grubu
# ═══════════════════════════════════════════════════════════════════════

def _risk_atom(varsa: bool, ad: str, neden_var: str, grup: str,
               yok: bool = False, neden_yok: str = '') -> SartSonuc:
    if varsa:
        return SartSonuc(ad=ad, durum=SartDurumu.VAR, neden=neden_var,
                         kaynak='ICD+rapor', grup=grup, veya_grubu=True)
    if yok:
        return SartSonuc(ad=ad, durum=SartDurumu.YOK, neden=neden_yok,
                         kaynak='ICD+rapor', grup=grup, veya_grubu=True)
    return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='ICD/rapor metninde tespit edilemedi — manuel',
                     kaynak='ICD+rapor', grup=grup, veya_grubu=True, sartli_atom=True)


def risk_grubu_atomlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    grup = '(2.4.3-B/b) Risk grubu — sağlık raporuna dayalı (≥1) ‖B‖'
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    yas = _yas_int(ilac_sonuc)
    s: List[SartSonuc] = []

    # R1 — gebeliğin 2. veya 3. trimesteri
    trimester = any(k in metin for k in ('2. trimester', '3. trimester',
                                         'ikinci trimester', 'ucuncu trimester',
                                         '2.trimester', '3.trimester'))
    s.append(_risk_atom(trimester, 'Gebeliğin 2./3. trimesteri',
                        'Raporda 2./3. trimester gebelik ibaresi', grup))

    # R2 — astım dâhil kronik pulmoner ve kardiyovasküler sistem hastalığı
    r2_icd = bool(re.search(r'\bJ4[0-7]|\bI\d\d|\bE84', icd))  # KOAH/astım/KV/kistik fibroz
    r2_kw = ('astim', 'koah', 'kronik pulmoner', 'kronik bronsit', 'amfizem',
             'kistik fibroz', 'kardiyovaskuler', 'kalp yetmezlik', 'koroner',
             'iskemik kalp', 'kalp hastalig')
    s.append(_risk_atom(r2_icd or any(k in metin for k in r2_kw),
                        'Astım dâhil kronik pulmoner / kardiyovasküler hastalık',
                        'Kronik pulmoner veya kardiyovasküler hastalık tespit edildi', grup))

    # R3 — diyabet dâhil herhangi bir kronik metabolik hastalık
    r3_icd = bool(re.search(r'\bE1[0-4]|\bE7[0-9]|\bE88', icd))
    r3_kw = ('diyabet', 'diabet', 'seker hastalig', 'metabolik')
    s.append(_risk_atom(r3_icd or any(k in metin for k in r3_kw),
                        'Diyabet dâhil kronik metabolik hastalık',
                        'Kronik metabolik hastalık (DM dâhil) tespit edildi', grup))

    # R4 — kronik renal disfonksiyon
    r4_icd = bool(re.search(r'\bN1[89]', icd))
    r4_kw = ('kronik renal', 'kronik bobrek', 'bobrek yetmezlik', 'kbh',
             'diyaliz', 'renal disfonksiyon')
    s.append(_risk_atom(r4_icd or any(k in metin for k in r4_kw),
                        'Kronik renal disfonksiyon',
                        'Kronik böbrek hastalığı / renal disfonksiyon tespit edildi', grup))

    # R5 — hemoglobinopati
    r5_icd = bool(re.search(r'\bD5[678]', icd))
    r5_kw = ('hemoglobinopati', 'talasemi', 'orak hucre', 'akdeniz anemisi')
    s.append(_risk_atom(r5_icd or any(k in metin for k in r5_kw),
                        'Hemoglobinopati',
                        'Hemoglobinopati (talasemi / orak hücre) tespit edildi', grup))

    # R6 — immün yetmezliği olan veya immünsupresif tedavi alan
    r6_icd = bool(re.search(r'\bD8[0-9]|\bB2[0-4]', icd))
    r6_kw = ('immun yetmezlik', 'immun supres', 'immunsupres', 'bagisiklik yetmezlik',
             'hiv', 'immunsupresif', 'immun supresif')
    s.append(_risk_atom(r6_icd or any(k in metin for k in r6_kw),
                        'İmmün yetmezlik / immünsupresif tedavi',
                        'İmmün yetmezlik veya immünsupresif tedavi tespit edildi', grup))

    # R7 — 6 ay - 18 yaş arası + uzun süreli asetil salisilik asit tedavisi
    asa = any(k in metin for k in ('asetilsalisilik', 'asetil salisilik',
                                   'aspirin', 'asa tedavi', 'uzun sureli asa'))
    if yas is not None and yas > 18:
        s.append(_risk_atom(False, '6ay-18 yaş + uzun süreli ASA tedavisi', '', grup,
                            yok=True, neden_yok='18 yaş üstü — bu alt-kriter dışı'))
    elif yas is not None and asa:
        s.append(_risk_atom(True, f'6ay-18 yaş + uzun süreli ASA tedavisi (yaş {yas})',
                            'ASA tedavisi alan çocuk/adölesan', grup))
    else:
        s.append(_risk_atom(False, '6ay-18 yaş + uzun süreli ASA tedavisi', '', grup))
    return s


def atom_b_rapor(ilac_sonuc: Dict) -> SartSonuc:
    grup = '(2.4.3-B/b) Sağlık raporuna dayalı ‖B‖'
    if _rapor_var(ilac_sonuc):
        return SartSonuc(ad='Sağlık raporu (hastalık/gebelik durumunu belirten)',
                         durum=SartDurumu.VAR,
                         neden='Reçeteye bağlı sağlık raporu var',
                         kaynak='rapor', grup=grup)
    return SartSonuc(ad='Sağlık raporu (hastalık/gebelik durumunu belirten)',
                     durum=SartDurumu.YOK,
                     neden='Risk grubu yolunda sağlık raporu zorunlu — rapor yok',
                     kaynak='rapor', grup=grup)


# ═══════════════════════════════════════════════════════════════════════
# ORTAK atomlar (her iki yol için) + bilgi atomları
# ═══════════════════════════════════════════════════════════════════════

_DONEM_AYLAR = {9, 10, 11, 12, 1, 2, 3}  # Eylül-Mart
_AY_AD = {1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
          7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'}


def atom_donem(ilac_sonuc: Dict) -> SartSonuc:
    grup = '(2.4.3-B) Eylül–Mart dönemi'
    ay = _recete_ay(ilac_sonuc)
    if ay is None:
        return SartSonuc(ad='Eylül–Mart döneminde reçete', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete tarihi okunamadı — manuel', kaynak='rec_tar', grup=grup)
    if ay in _DONEM_AYLAR:
        return SartSonuc(ad=f'Eylül–Mart döneminde reçete ({_AY_AD[ay]})',
                         durum=SartDurumu.VAR,
                         neden='Reçete Eylül-Mart grip aşısı döneminde', kaynak='rec_tar', grup=grup)
    return SartSonuc(ad=f'Eylül–Mart döneminde reçete ({_AY_AD[ay]})',
                     durum=SartDurumu.YOK,
                     neden='Reçete dönem dışında (Nisan-Ağustos) — grip aşısı karşılanmaz',
                     kaynak='rec_tar', grup=grup)


def bilgi_atomlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        SartSonuc(ad='Bir defaya mahsus (sezonda tek aşı)',
                  durum=SartDurumu.KONTROL_EDILEMEDI,
                  neden='Sezon (Eylül-Mart) mükerrer aşı takibi yapılamadı — manuel',
                  kaynak='-', grup='(bilgi) Bir defaya mahsus', sartli_atom=True),
        SartSonuc(ad='Tüm hekimlerce reçete edilebilir',
                  durum=SartDurumu.VAR,
                  neden='Branş/uzman kısıtı yok — tüm hekimler reçete edebilir',
                  kaynak='-', grup='(bilgi) Tüm hekimlerce'),
    ]


def grip_asisi_sartlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.extend(yol_a_atomlar(ilac_sonuc))
    s.extend(risk_grubu_atomlar(ilac_sonuc))
    s.append(atom_b_rapor(ilac_sonuc))
    s.append(atom_donem(ilac_sonuc))
    s.extend(bilgi_atomlar(ilac_sonuc))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (üst-VEYA ‖A‖/‖B‖ destekli — MS 4.2.34 kalıbı)
# ═══════════════════════════════════════════════════════════════════════

_PATH_TAG_RE = re.compile(r'‖([^‖]+)‖')


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


def _or_birlestir(sonuclar: List[Tuple[str, bool]]) -> Tuple[str, bool]:
    if any(d == 'var' for d, _ in sonuclar):
        return ('var', False)
    ke = [(d, s) for d, s in sonuclar if d == 'ke']
    if ke:
        return ('ke', all(s for _, s in ke))
    return ('yok', False)


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    gruplar: Dict[str, List[SartSonuc]] = {}
    for s in sartlar:
        if '(bilgi)' in (s.grup or ''):
            continue
        gruplar.setdefault(s.grup, []).append(s)
    if not gruplar:
        return KontrolSonucu.KONTROL_EDILEMEDI

    ortak: List[Tuple[str, bool]] = []
    yollar: Dict[str, List[Tuple[str, bool]]] = {}
    for grup, gs in gruplar.items():
        durum = _grup_durum(gs)
        m = _PATH_TAG_RE.search(grup)
        if m:
            yollar.setdefault(m.group(1), []).append(durum)
        else:
            ortak.append(durum)

    sonuc_listesi: List[Tuple[str, bool]] = list(ortak)
    if yollar:
        yol_sonuclari = [_and_birlestir(v) for v in yollar.values()]
        sonuc_listesi.append(_or_birlestir(yol_sonuclari))

    durum, sartli = _and_birlestir(sonuc_listesi)
    if durum == 'yok':
        return KontrolSonucu.UYGUN_DEGIL
    if durum == 'ke':
        return (KontrolSonucu.SARTLI_UYGUN if sartli
                else KontrolSonucu.KONTROL_EDILEMEDI)
    return KontrolSonucu.UYGUN


def _mesaj_uret(sonuc: KontrolSonucu, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    parcalar = ['SUT 2.4.3-B / Grip aşısı']
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

def grip_asisi_kontrol_2_4_3_b(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 2.4.3-B — Grip (influenza) aşısı ana kontrol fonksiyonu."""
    if not grip_asisi_kapsamda_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 2.4.3-B kapsamı dışı — grip (influenza) aşısı değil',
            sut_kurali='SUT 2.4.3-B')

    sartlar = grip_asisi_sartlar(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj, sut_kurali='SUT 2.4.3-B',
        sartlar=sartlar, detaylar={'kontrol': 'grip_asisi_2_4_3_b'})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        # ── Kapsam ──
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01'}, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (pnömokok aşısı J07AL)", {
            'ilac_adi': 'PREVENAR 13', 'atc_kodu': 'J07AL02'}, KontrolSonucu.ATLANDI),
        # ── YOL_A: 65 yaş ──
        ("YOL_A UYGUN (70 yaş, Ekim, raporsuz)", {
            'ilac_adi': 'INFLUVAC', 'atc_kodu': 'J07BB02', 'hasta_yasi': '70',
            'rec_tar': '15.10.2025'}, KontrolSonucu.UYGUN),
        ("YOL_A UYGUN (65 yaş tam sınır, Aralık)", {
            'atc_kodu': 'J07BB02', 'hasta_yasi': '65', 'rec_tar': '01.12.2025'},
         KontrolSonucu.UYGUN),
        ("YOL_A huzurevi (50 yaş ama huzurevi ibaresi, Kasım, raporsuz)", {
            'atc_kodu': 'J07BB02', 'hasta_yasi': '50', 'rec_tar': '10.11.2025',
            'rapor_metni': 'huzurevi sakini'}, KontrolSonucu.UYGUN),
        # ── DÖNEM ──
        ("Dönem dışı UYGUN DEĞİL (70 yaş ama Haziran)", {
            'atc_kodu': 'J07BB02', 'hasta_yasi': '70', 'rec_tar': '15.06.2025'},
         KontrolSonucu.UYGUN_DEGIL),
        ("Dönem dışı UYGUN DEĞİL (risk+rapor ama Mayıs)", {
            'atc_kodu': 'J07BB02', 'hasta_yasi': '40', 'rec_tar': '20.05.2025',
            'rapor_kodu': '111', 'recete_teshisleri': ['J45']}, KontrolSonucu.UYGUN_DEGIL),
        # ── YOL_B: risk + rapor ──
        ("YOL_B UYGUN (40 yaş astım J45 + rapor, Ocak)", {
            'atc_kodu': 'J07BB02', 'hasta_yasi': '40', 'rec_tar': '05.01.2026',
            'rapor_kodu': '222', 'recete_teshisleri': ['J45']}, KontrolSonucu.UYGUN),
        ("YOL_B UYGUN (35 yaş DM E11 + rapor, Şubat)", {
            'atc_kodu': 'J07BB02', 'hasta_yasi': '35', 'rec_tar': '10.02.2026',
            'rapor_kodu': '333', 'recete_teshisleri': ['E11']}, KontrolSonucu.UYGUN),
        ("YOL_B UYGUN (28 yaş immün D84 + rapor, Mart)", {
            'atc_kodu': 'J07BB02', 'hasta_yasi': '28', 'rec_tar': '20.03.2026',
            'rapor_kodu': '444', 'recete_teshisleri': ['D84']}, KontrolSonucu.UYGUN),
        # ── YOL_B: risk var ama rapor YOK → ŞARTLI (huzurevi KE açık) ──
        ("Risk var rapor YOK (40 yaş astım, Ekim, raporsuz) → ŞARTLI", {
            'atc_kodu': 'J07BB02', 'hasta_yasi': '40', 'rec_tar': '15.10.2025',
            'recete_teshisleri': ['J45']}, KontrolSonucu.SARTLI_UYGUN),
        # ── Belirsiz: genç, risk sessiz, raporsuz → ŞARTLI (huzurevi+risk KE) ──
        ("Belirsiz (45 yaş, ICD yok, raporsuz, Kasım) → ŞARTLI", {
            'atc_kodu': 'J07BB02', 'hasta_yasi': '45', 'rec_tar': '12.11.2025'},
         KontrolSonucu.SARTLI_UYGUN),
        # ── R7 ASA çocuk ──
        ("YOL_B UYGUN (12 yaş + ASA tedavisi + rapor, Aralık)", {
            'atc_kodu': 'J07BB02', 'hasta_yasi': '12', 'rec_tar': '01.12.2025',
            'rapor_kodu': '555', 'rapor_metni': 'uzun sureli asetilsalisilik asit tedavisi'},
         KontrolSonucu.UYGUN),
        # ── Ticari ad ile tespit ──
        ("Ticari ad tespiti (VAXIGRIP TETRA, 68 yaş, Eylül)", {
            'ilac_adi': 'VAXIGRIP TETRA', 'hasta_yasi': '68', 'rec_tar': '25.09.2025'},
         KontrolSonucu.UYGUN),
        # ── Yaş yok → KE/şartlı ──
        ("Yaş bilinmiyor, raporsuz, Ekim → ŞARTLI", {
            'atc_kodu': 'J07BB02', 'rec_tar': '10.10.2025'}, KontrolSonucu.SARTLI_UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT 2.4.3-B — Grip Aşısı — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = grip_asisi_kontrol_2_4_3_b(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 60)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
