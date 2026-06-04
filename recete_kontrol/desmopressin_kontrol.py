# -*- coding: utf-8 -*-
"""SUT — Desmopressin kullanım ilkesi (a şıkkı).

Resmî lafız (kullanıcı verdi 2026-06-04; ana SUT tebliğ metni
`SUT_tam_metin.txt`'te bulunmuyor — EK/ek ibare, kullanıcı onayıyla işlendi.
Kullanıcı: madde SADECE (a) şıkkından ibaret):
    "Desmopressin yalnızca;
     a) Primer enurezis nokturna tedavisinde ve santral diabetes insipidus
        tedavisinde uzman hekimlerce raporsuz reçete edilmesi halinde,
     ...bedelleri Kurumca karşılanır."

Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ATOMİK DEVRE
ŞEMASI PRENSİPLERİ. Tek yolak, RAPORSUZ (rapor atomu yok).

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ ( A1: primer enürezis nokturna  ∨  A2: santral diabetes insipidus )
          ∧ B1( reçete eden uzman hekim )

  "ve" lafzı iki ENDİKASYON listeler; her biri tek başına yeterli → VEYA grubu.
  "raporsuz" → rapor şartı YOK. "uzman hekimlerce" → reçete eden uzman olmalı
  (pratisyen/aile hekimi → YOK, kullanıcı kararı 2026-06-04). Branş bilinmezse KE.

Ana entrypoint: ``desmopressin_kontrol(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC H01BA02 desmopressin + etken + ticari
# ═══════════════════════════════════════════════════════════════════════
ATC_DESMOPRESSIN = 'H01BA02'
DESMOPRESSIN_ETKEN: Set[str] = {'DESMOPRESSIN', 'DESMOPRESIN', 'DESMOPRESSIN ASETAT'}
DESMOPRESSIN_TICARI: Set[str] = {
    'MINIRIN', 'MINIRINMELT', 'MINIMELT', 'NOCDURNA', 'NOQDIRNA',
    'OCTOSTIM', 'DESMOSPRAY', 'PRESSIN', 'DESMOMELT',
}

# Endikasyon ICD + metin
ENUREZIS_ICD = ('F98.0', 'F980', 'N39.4', 'N394', 'R32')
ENUREZIS_METIN = ('enurezis', 'enürezis', 'enurez', 'gece isemes', 'gece işemes',
                  'nokturnal enurez', 'yatak islatma', 'yatak ıslatma',
                  'alti islatma')
DI_ICD = ('E23.2', 'E232')
DI_METIN = ('diabetes insipidus', 'diabetes insipitus', 'diabetes insibitus',
            'santral di', 'diabetinsipid', 'di tani', 'sıvı kaybı', 'poliuri')

# Reçete edemeyen (uzman olmayan) branş anahtarları
NON_UZMAN_KW = ('pratisyen', 'aile hek', 'genel pratisyen', 'pratisyen tabip',
                'pratisyen hekim')


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


def _rapor_recete_metni(ilac_sonuc: Dict) -> str:
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


def _brans_l(brans: Optional[str]) -> str:
    return norm_tr_lower(brans or '')


def desmopressin_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """Desmopressin (H01BA02) mı?"""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_DESMOPRESSIN):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, DESMOPRESSIN_ETKEN) or _iceriyor(m, DESMOPRESSIN_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_ENDIKASYON = '(a) Endikasyon — enürezis nokturna VEYA santral DI'
GRUP_RECETE = '(a) Reçete eden uzman hekim (raporsuz)'


def atom_endik_enurezis(ilac_sonuc: Dict) -> SartSonuc:
    """A1: primer enürezis nokturna (ICD F98.0 / metin)."""
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_recete_metni(ilac_sonuc)
    icd_var = any(k in icd for k in ENUREZIS_ICD)
    metin_var = any(k in metin for k in ENUREZIS_METIN)
    if icd_var or metin_var:
        return SartSonuc(ad='Primer enürezis nokturna', durum=SartDurumu.VAR,
                         neden=('ICD ' + next(k for k in ENUREZIS_ICD if k in icd))
                               if icd_var else 'reçete/rapor: enürezis',
                         kaynak='ICD+metin', grup=GRUP_ENDIKASYON, veya_grubu=True)
    return SartSonuc(ad='Primer enürezis nokturna', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Enürezis (ICD F98.0 / metin) saptanmadı',
                     kaynak='ICD+metin', grup=GRUP_ENDIKASYON, veya_grubu=True,
                     sartli_atom=True)


def atom_endik_santral_di(ilac_sonuc: Dict) -> SartSonuc:
    """A2: santral diabetes insipidus (ICD E23.2 / metin)."""
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_recete_metni(ilac_sonuc)
    icd_var = any(k in icd for k in DI_ICD)
    metin_var = any(k in metin for k in DI_METIN)
    if icd_var or metin_var:
        return SartSonuc(ad='Santral diabetes insipidus', durum=SartDurumu.VAR,
                         neden=('ICD E23.2' if icd_var else 'reçete/rapor: diabetes insipidus'),
                         kaynak='ICD+metin', grup=GRUP_ENDIKASYON, veya_grubu=True)
    return SartSonuc(ad='Santral diabetes insipidus', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Diabetes insipidus (ICD E23.2 / metin) saptanmadı',
                     kaynak='ICD+metin', grup=GRUP_ENDIKASYON, veya_grubu=True,
                     sartli_atom=True)


def atom_recete_uzman(ilac_sonuc: Dict) -> SartSonuc:
    """B1: reçeteyi yazan uzman hekim (pratisyen/aile hekimi → YOK)."""
    brans = (ilac_sonuc.get('recete_hekim_uzmanligi')
             or ilac_sonuc.get('doktor_uzmanligi')
             or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden uzman hekim', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_RECETE, sartli_atom=True)
    if any(k in bl for k in NON_UZMAN_KW):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                         neden='Pratisyen/aile hekimi — yalnız uzman hekim reçete edebilir',
                         kaynak='hekim_brans', grup=GRUP_RECETE)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                     neden='Uzman hekim — yetkili (raporsuz)',
                     kaynak='hekim_brans', grup=GRUP_RECETE)


def _desmopressin_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_endik_enurezis(ilac_sonuc),
        atom_endik_santral_di(ilac_sonuc),
        atom_recete_uzman(ilac_sonuc),
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (ortak grup-bazlı kalıp)
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
    parcalar = ['SUT Desmopressin (a)']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — endikasyon + uzman hekim (raporsuz)')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — {len(ke)} şart manuel doğrulama gerektiriyor')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — ' + '; '.join(s.ad for s in yok[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def desmopressin_kontrol(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT — Desmopressin (a) enürezis nokturna / santral DI kontrolü."""
    if not desmopressin_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Kapsam dışı — desmopressin (H01BA02) değil',
            sut_kurali='SUT — Desmopressin')

    sartlar = _desmopressin_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'DESMOPRESSIN',
        'sut_maddesi': 'Desmopressin (a)',
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
        sut_kurali='SUT — Desmopressin (a) enürezis nokturna / santral DI (raporsuz)',
        aranan_ibare='enürezis nokturna VEYA santral DI + reçete eden uzman hekim',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("UYGUN (enürezis ICD + üroloji uzmanı)", {
            'etkin_madde': 'DESMOPRESSIN', 'atc_kodu': 'H01BA02',
            'recete_teshisleri': ['F98.0'], 'doktor_uzmanligi': 'Üroloji',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (santral DI ICD + endokrin uzmanı)", {
            'etkin_madde': 'DESMOPRESSIN', 'atc_kodu': 'H01BA02',
            'recete_teshisleri': ['E23.2'], 'doktor_uzmanligi': 'Endokrinoloji',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (enürezis metin + çocuk sağlığı uzmanı)", {
            'etkin_madde': 'MINIRIN', 'atc_kodu': 'H01BA02',
            'recete_aciklamalari': ['gece işemesi enürezis nokturna'],
            'doktor_uzmanligi': 'Çocuk Sağlığı ve Hastalıkları',
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (pratisyen hekim)", {
            'etkin_madde': 'DESMOPRESSIN', 'atc_kodu': 'H01BA02',
            'recete_teshisleri': ['F98.0'], 'doktor_uzmanligi': 'Pratisyen Tabip',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (aile hekimi)", {
            'etkin_madde': 'MINIRIN', 'atc_kodu': 'H01BA02',
            'recete_teshisleri': ['E23.2'], 'doktor_uzmanligi': 'Aile Hekimliği',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ŞARTLI (endikasyon yok, uzman var)", {
            'etkin_madde': 'DESMOPRESSIN', 'atc_kodu': 'H01BA02',
            'recete_teshisleri': ['Z00.0'], 'doktor_uzmanligi': 'Üroloji',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("ŞARTLI (endikasyon var, branş bilinmiyor)", {
            'etkin_madde': 'DESMOPRESSIN', 'atc_kodu': 'H01BA02',
            'recete_teshisleri': ['F98.0'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("UYGUN (ticari NOCDURNA + nöroloji)", {
            'ilac_adi': 'NOCDURNA 25 MCG', 'etkin_madde': 'DESMOPRESSIN',
            'recete_teshisleri': ['E23.2'], 'doktor_uzmanligi': 'Nöroloji',
        }, KontrolSonucu.UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT Desmopressin (a) — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = desmopressin_kontrol(ilac_sonuc)
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
