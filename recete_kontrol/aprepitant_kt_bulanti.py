# -*- coding: utf-8 -*-
"""SUT EK-4 — Aprepitant (EMEND, oral) kemoterapi ilişkili bulantı/kusma.

Resmî lafız (EK-4 ek listesi):
    "Yetişkin hastalarda yüksek ve orta derecede emetojenik kanser
     kemoterapisi alan ile ilişkili bulantı ve kusmanın önlenmesinde,
     kemoterapi rejimleri ile gelişen ya da kök hücre destekli yüksek doz
     kemoterapi uygulamaları sonrası gelişen emezisin önlenmesinde veya
     antrasiklin (doksorubisin veya epirubisin) ve siklofosfamid kombinasyon
     kemoterapisinin başlangıç ve tekrar kürleri ile ilişkili bulantı veya
     kusmanın önlenmesinde, bu durumların belirtildiği sağlık kurulu raporuna
     dayanılarak ödenir. Bir kür süresince en fazla 1 kutu reçete edilebilir.
     Fosaprepitant dimeglumin ile birlikte kullanılmaz."

Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ATOMİK DEVRE
ŞEMASI PRENSİPLERİ. Tek yolak; ilk/devam dispatcher yok; branş şartı yok
(sadece SK raporu); tek NOT atomu (fosaprepitant kombi yasağı — DeMorgan
gerekmez).

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ A1(yetişkin≥18)
          ∧ (E1 ∨ E2 ∨ E3)         ← endikasyon VEYA grubu (≥1)
          ∧ C1(sağlık kurulu raporu)
          ∧ F1(kür başına ≤1 kutu)
          ∧ G1(¬fosaprepitant kombi)

  E1 = yüksek/orta emetojenik KT ile ilişkili bulantı-kusma
       (kanser ICD C/D varsa VAR say — kullanıcı kararı 2026-06-04)
  E2 = KT rejimi / kök hücre destekli yüksek doz KT sonrası emezis
  E3 = antrasiklin(doks∨epi) ∧ siklofosfamid kombi KT başlangıç/tekrar kürü

Kullanıcı kararları (2026-06-04):
  - Kutu/kür: ≤1 → VAR; >1 → KE (manuel, çünkü kaç kür belirsiz)
  - SK raporu: ÇEŞİTLİ akışında rapor_turu+heyet zenginleştirilir; yoksa KE+şartlı
  - Endikasyon: kanser ICD (C/D) varsa endikasyon VAR

Ana entrypoint: ``aprepitant_kontrol_kt_bulanti(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — etken + ticari + ATC
# ═══════════════════════════════════════════════════════════════════════
# Aprepitant (oral, EMEND) ATC = A04AD12. Fosaprepitant (IV, IVEMEND) AYNI
# ATC'yi paylaşır → ATC tek başına ayıramaz; ad bazlı ayrım zorunlu.
# 'FOSAPREPITANT' içinde 'APREPITANT' substring var → guard şart.
APREPITANT_TICARI: Set[str] = {'EMEND'}  # oral; IVEMEND (fosaprepitant) hariç
ATC_APREPITANT = 'A04AD12'

# Fosaprepitant (kombi yasağı atomunda aranır)
FOSAPREPITANT_KW: Set[str] = {'FOSAPREPITANT', 'IVEMEND'}

# Kanser ICD önekleri (C00-D48 onkoloji). Basit prefix kontrolü.
KANSER_ICD_PREFIX = ('C', 'D0', 'D1', 'D2', 'D3', 'D4')  # C*, D00-D48 yaklaşık

# Endikasyon metin sinyalleri
EMETOJENIK_KW = ('emetojenik', 'emetojen', 'emezis', 'bulant', 'kusma')
KEMOTERAPI_KW = ('kemoterapi', 'kemoterapotik', 'sitotoksik', 'ktx', 'kt rejim')
KOK_HUCRE_KW = ('kok hucre', 'kemik iligi nakli', 'kit ', 'otolog', 'allojenik',
                'yuksek doz kemoterapi')
ANTRASIKLIN_KW = ('antrasiklin', 'doksorubisin', 'doxorubisin', 'epirubisin',
                  'adriamisin')
SIKLOFOSFAMID_KW = ('siklofosfamid', 'cyclophosphamid', 'endoksan')


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


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


def _kanser_icd_var(ilac_sonuc: Dict) -> Optional[str]:
    """Teşhislerde onkoloji ICD (C* / D00-D48) var mı? → eşleşen kod / None."""
    icd = _teshis_birlesik(ilac_sonuc)
    # Kod tokenlerini ayıkla (C50.9, D46 gibi)
    for tok in re.findall(r'\b([CD]\d{2}(?:\.\d+)?)\b', icd):
        ust = tok.upper()
        if ust.startswith('C'):
            return ust
        # D00-D48 (in situ / belirsiz davranışlı neoplazm) — D49 üstü hariç tut
        m = re.match(r'D(\d{2})', ust)
        if m and int(m.group(1)) <= 48:
            return ust
    return None


def _yas_oku(ilac_sonuc: Dict) -> Optional[int]:
    for anahtar in ('hasta_yasi', 'yas', 'hasta_yas'):
        v = ilac_sonuc.get(anahtar)
        if v in (None, ''):
            continue
        try:
            return int(float(str(v).strip()))
        except (TypeError, ValueError):
            continue
    return None


def _adet_oku(ilac_sonuc: Dict) -> Optional[float]:
    for anahtar in ('adet', 'kutu_sayisi', 'kutu', 'miktar'):
        v = ilac_sonuc.get(anahtar)
        if v in (None, ''):
            continue
        try:
            return float(str(v).replace(',', '.').strip())
        except (TypeError, ValueError):
            continue
    return None


def _diger_ilac_metni(ilac_sonuc: Dict) -> str:
    parcalar: List[str] = []
    for anahtar in ('diger_etken_maddeler', 'diger_ilac_adlari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
    return norm_tr_upper(' '.join(parcalar))


def aprepitant_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """Aprepitant (oral, EMEND) mı? Fosaprepitant (IVEMEND) HARİÇ."""
    m = _arama_metni(ilac_sonuc)
    if 'FOSAPREPITANT' in m or 'IVEMEND' in m:
        return False  # bu, kombi-yasağı ilacı — aprepitant kontrolü değil
    if 'APREPITANT' in m:
        return True
    if any(norm_tr_upper(t) in m for t in APREPITANT_TICARI):
        return True
    # ATC tek başına fosaprepitant ile ortak → ad doğrulaması olmadan kabul etme
    return False


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_HASTA = '(1) Yetişkin hasta'
GRUP_ENDIKASYON = '(2) KT ilişkili bulantı/kusma endikasyonu (≥1)'
GRUP_RAPOR = '(3) Sağlık kurulu raporu'
GRUP_DOZ = '(4) Kür başına ≤1 kutu'
GRUP_KOMBI = '(5) Fosaprepitant kombi yasağı'


def atom_yetiskin(ilac_sonuc: Dict) -> SartSonuc:
    yas = _yas_oku(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad='Yetişkin (≥18 yaş)', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı DB\'de yok — manuel doğrula',
                         kaynak='hasta_yas', grup=GRUP_HASTA, sartli_atom=True)
    if yas >= 18:
        return SartSonuc(ad=f'Yetişkin ({yas} yaş)', durum=SartDurumu.VAR,
                         neden='18 yaş ve üzeri', kaynak='hasta_yas', grup=GRUP_HASTA)
    return SartSonuc(ad=f'Yetişkin ({yas} yaş)', durum=SartDurumu.YOK,
                     neden='18 yaş altı — yetişkin değil', kaynak='hasta_yas', grup=GRUP_HASTA)


def atom_endik_emetojenik(ilac_sonuc: Dict) -> SartSonuc:
    """E1: yüksek/orta emetojenik KT ile ilişkili bulantı-kusma.

    Kullanıcı kararı 2026-06-04: kanser ICD (C/D) varsa endikasyon VAR.
    Bu atom endikasyon VEYA grubunun umbrella'sıdır.
    """
    metin = _rapor_metni(ilac_sonuc)
    kanser = _kanser_icd_var(ilac_sonuc)
    kt = any(k in metin for k in KEMOTERAPI_KW)
    emet = any(k in metin for k in EMETOJENIK_KW)
    if kanser:
        return SartSonuc(ad='Emetojenik KT ilişkili bulantı/kusma', durum=SartDurumu.VAR,
                         neden=f'Kanser ICD {kanser} — KT ilişkili endikasyon kabul',
                         kaynak='ICD', grup=GRUP_ENDIKASYON, veya_grubu=True)
    if kt and emet:
        return SartSonuc(ad='Emetojenik KT ilişkili bulantı/kusma', durum=SartDurumu.VAR,
                         neden='Rapor: kemoterapi + bulantı/kusma/emezis',
                         kaynak='rapor', grup=GRUP_ENDIKASYON, veya_grubu=True)
    return SartSonuc(ad='Emetojenik KT ilişkili bulantı/kusma',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Kanser ICD ve KT/bulantı ibaresi okunamadı — manuel',
                     kaynak='ICD+rapor', grup=GRUP_ENDIKASYON, veya_grubu=True,
                     sartli_atom=True)


def atom_endik_kok_hucre(ilac_sonuc: Dict) -> SartSonuc:
    """E2: KT rejimi / kök hücre destekli yüksek doz KT sonrası emezis."""
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in KOK_HUCRE_KW):
        return SartSonuc(ad='Kök hücre destekli / yüksek doz KT sonrası emezis',
                         durum=SartDurumu.VAR,
                         neden='Rapor: kök hücre / yüksek doz kemoterapi',
                         kaynak='rapor', grup=GRUP_ENDIKASYON, veya_grubu=True)
    return SartSonuc(ad='Kök hücre destekli / yüksek doz KT sonrası emezis',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Kök hücre/yüksek doz KT ibaresi raporda okunamadı — manuel',
                     kaynak='rapor', grup=GRUP_ENDIKASYON, veya_grubu=True,
                     sartli_atom=True)


def atom_endik_ac_kombi(ilac_sonuc: Dict) -> SartSonuc:
    """E3: antrasiklin (doks∨epi) ∧ siklofosfamid kombi KT başlangıç/tekrar kürü."""
    metin = _rapor_metni(ilac_sonuc)
    antra = any(k in metin for k in ANTRASIKLIN_KW)
    siklo = any(k in metin for k in SIKLOFOSFAMID_KW)
    if antra and siklo:
        return SartSonuc(ad='Antrasiklin + siklofosfamid kombi KT',
                         durum=SartDurumu.VAR,
                         neden='Rapor: antrasiklin (doks/epi) + siklofosfamid',
                         kaynak='rapor', grup=GRUP_ENDIKASYON, veya_grubu=True)
    return SartSonuc(ad='Antrasiklin + siklofosfamid kombi KT',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Antrasiklin+siklofosfamid kombinasyonu raporda okunamadı — manuel',
                     kaynak='rapor', grup=GRUP_ENDIKASYON, veya_grubu=True,
                     sartli_atom=True)


def atom_saglik_kurulu(ilac_sonuc: Dict) -> SartSonuc:
    """C1: sağlık kurulu raporu (RaporTuruAdi + heyet — kanser_gcsf kalıbı)."""
    rapor_turu = norm_tr_lower(ilac_sonuc.get('rapor_turu') or '')
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    heyet_n = len([h for h in heyet if (isinstance(h, dict) and (h.get('ad') or h.get('brans')))]) \
        if isinstance(heyet, (list, tuple)) else 0
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()

    kurul_isaret = ('kurul' in rapor_turu) or (heyet_n >= 2)
    uzman_tek = ('uzman hekim' in rapor_turu) and 'kurul' not in rapor_turu
    rapor_var = bool(rapor_kodu or rapor_takip or rapor_turu or heyet_n)

    if kurul_isaret:
        neden = f"Sağlık kurulu raporu ({rapor_turu or 'heyet ' + str(heyet_n) + ' uzman'})"
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
                         neden=neden, kaynak='rapor_turu+heyet', grup=GRUP_RAPOR)
    if uzman_tek and heyet_n <= 1:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Rapor türü "uzman hekim" — SUT sağlık kurulu raporu ister',
                         kaynak='rapor_turu+heyet', grup=GRUP_RAPOR)
    if not rapor_var:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor bulunamadı',
                         kaynak='rapor', grup=GRUP_RAPOR)
    return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama türü/heyeti sağlık kurulu olarak '
                           'doğrulanamadı — manuel', kaynak='rapor_turu+heyet',
                     grup=GRUP_RAPOR, sartli_atom=True)


def atom_kutu_kur(ilac_sonuc: Dict) -> SartSonuc:
    """F1: bir kür süresince en fazla 1 kutu (kullanıcı: >1 → KE manuel)."""
    adet = _adet_oku(ilac_sonuc)
    if adet is None:
        return SartSonuc(ad='Kür başına ≤1 kutu', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete kutu adedi okunamadı — manuel doğrula',
                         kaynak='doz', grup=GRUP_DOZ, sartli_atom=True)
    if adet <= 1:
        return SartSonuc(ad='Kür başına ≤1 kutu', durum=SartDurumu.VAR,
                         neden=f'Kutu adedi {adet:g} — bir kür için ≤1',
                         kaynak='doz', grup=GRUP_DOZ)
    return SartSonuc(ad='Kür başına ≤1 kutu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Kutu adedi {adet:g} — birden fazla kür olabilir, '
                           f'kür başına ≤1 manuel doğrula',
                     kaynak='doz', grup=GRUP_DOZ, sartli_atom=True)


def atom_fosaprepitant_kombi(ilac_sonuc: Dict) -> SartSonuc:
    """G1 (NOT): fosaprepitant dimeglumin ile birlikte kullanılmaz."""
    diger = _diger_ilac_metni(ilac_sonuc)
    if any(norm_tr_upper(k) in diger for k in FOSAPREPITANT_KW):
        return SartSonuc(ad='Fosaprepitant ile birlikte değil', durum=SartDurumu.YOK,
                         neden='Aynı reçetede fosaprepitant (IVEMEND) var — birlikte ödenmez',
                         kaynak='recete_kalemleri', grup=GRUP_KOMBI)
    return SartSonuc(ad='Fosaprepitant ile birlikte değil', durum=SartDurumu.VAR,
                     neden='Reçetede fosaprepitant yok', kaynak='recete_kalemleri',
                     grup=GRUP_KOMBI)


def _aprepitant_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_yetiskin(ilac_sonuc),
        atom_endik_emetojenik(ilac_sonuc),
        atom_endik_kok_hucre(ilac_sonuc),
        atom_endik_ac_kombi(ilac_sonuc),
        atom_saglik_kurulu(ilac_sonuc),
        atom_kutu_kur(ilac_sonuc),
        atom_fosaprepitant_kombi(ilac_sonuc),
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (eritropoietin/alprostadil kalıbı — grup bazlı)
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


def _mesaj_uret(sonuc: KontrolSonucu, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    parcalar = ['EK-4 Aprepitant (KT ilişkili bulantı/kusma)']
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

def aprepitant_kontrol_kt_bulanti(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4 — Aprepitant (oral) KT ilişkili bulantı/kusma kontrolü."""
    if not aprepitant_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Kapsam dışı — aprepitant (oral) değil',
            sut_kurali='SUT EK-4 — Aprepitant')

    sartlar = _aprepitant_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'APREPITANT',
        'sut_maddesi': 'EK-4 Aprepitant',
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
        sut_kurali='SUT EK-4 — Aprepitant (KT ilişkili bulantı/kusma)',
        aranan_ibare='yetişkin + emetojenik KT/kök hücre/AC kombi + SK raporu + '
                     '≤1 kutu/kür + fosaprepitant yasağı',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (≥10 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    SK = [{'brans': 'Tıbbi Onkoloji'}, {'brans': 'İç Hastalıkları'}]
    return [
        ("Tam UYGUN (kanser ICD + SK + 1 kutu)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 55, 'recete_teshisleri': ['C50.9'],
            'rapor_turu': 'Sağlık Kurulu Raporu', 'heyet_doktorlari': SK,
            'rapor_kodu': '1', 'kutu_sayisi': '1',
            'rapor_metni': 'meme kanseri kemoterapi bulantı kusma önlenmesi',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (AC kombi metin + SK + 1 kutu, ICD yok)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 60, 'recete_teshisleri': [],
            'rapor_turu': 'Sağlık Kurulu Raporu', 'heyet_doktorlari': SK,
            'rapor_kodu': '1', 'kutu_sayisi': '1',
            'rapor_metni': 'doksorubisin ve siklofosfamid kombinasyon kemoterapisi '
                           'başlangıç kürü bulantı',
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (18 yaş altı)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 15, 'recete_teshisleri': ['C91.0'],
            'rapor_turu': 'Sağlık Kurulu Raporu', 'heyet_doktorlari': SK,
            'rapor_kodu': '1', 'kutu_sayisi': '1',
            'rapor_metni': 'lösemi kemoterapi bulantı',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (fosaprepitant kombi)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 50, 'recete_teshisleri': ['C50.9'],
            'rapor_turu': 'Sağlık Kurulu Raporu', 'heyet_doktorlari': SK,
            'rapor_kodu': '1', 'kutu_sayisi': '1',
            'diger_etken_maddeler': ['FOSAPREPITANT DIMEGLUMIN'],
            'rapor_metni': 'meme kanseri kemoterapi bulantı',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (SK değil — uzman hekim raporu)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 50, 'recete_teshisleri': ['C50.9'],
            'rapor_turu': 'Uzman Hekim Raporu', 'heyet_doktorlari': [],
            'rapor_kodu': '1', 'kutu_sayisi': '1',
            'rapor_metni': 'meme kanseri kemoterapi bulantı',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ŞARTLI (kutu 2 → KE manuel)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 50, 'recete_teshisleri': ['C50.9'],
            'rapor_turu': 'Sağlık Kurulu Raporu', 'heyet_doktorlari': SK,
            'rapor_kodu': '1', 'kutu_sayisi': '2',
            'rapor_metni': 'meme kanseri kemoterapi bulantı',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("ŞARTLI (endikasyon okunamadı — kanser ICD yok, metin boş)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 50, 'recete_teshisleri': ['R11'],
            'rapor_turu': 'Sağlık Kurulu Raporu', 'heyet_doktorlari': SK,
            'rapor_kodu': '1', 'kutu_sayisi': '1',
            'rapor_metni': 'bulantı şikayeti',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("ŞARTLI (SK doğrulanamadı — rapor var türü yok)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 50, 'recete_teshisleri': ['C50.9'],
            'rapor_turu': '', 'heyet_doktorlari': [],
            'rapor_kodu': '1234', 'kutu_sayisi': '1',
            'rapor_metni': 'meme kanseri kemoterapi bulantı',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN DEĞİL (rapor hiç yok)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 50, 'recete_teshisleri': ['C50.9'],
            'rapor_turu': '', 'heyet_doktorlari': [],
            'rapor_kodu': '', 'kutu_sayisi': '1',
            'rapor_metni': 'meme kanseri kemoterapi bulantı',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN (kök hücre destekli yüksek doz KT)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 40, 'recete_teshisleri': [],
            'rapor_turu': 'Sağlık Kurulu Raporu', 'heyet_doktorlari': SK,
            'rapor_kodu': '1', 'kutu_sayisi': '1',
            'rapor_metni': 'kök hücre destekli yüksek doz kemoterapi sonrası emezis',
        }, KontrolSonucu.UYGUN),
        ("Fosaprepitant'ın kendisi → ATLANDI", {
            'etkin_madde': 'FOSAPREPITANT DIMEGLUMIN', 'atc_kodu': 'A04AD12',
            'hasta_yasi': 50, 'recete_teshisleri': ['C50.9'],
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("UYGUN (ticari EMEND + ICD)", {
            'ilac_adi': 'EMEND 125 MG/80 MG KAPSUL', 'etkin_madde': 'APREPITANT',
            'hasta_yasi': 62, 'recete_teshisleri': ['C34.9'],
            'rapor_turu': 'Sağlık Kurulu Raporu', 'heyet_doktorlari': SK,
            'rapor_kodu': '5', 'kutu_sayisi': '1',
            'rapor_metni': 'akciğer kanseri kemoterapi emetojenik bulantı kusma',
        }, KontrolSonucu.UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT EK-4 Aprepitant — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = aprepitant_kontrol_kt_bulanti(ilac_sonuc)
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
