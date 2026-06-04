# -*- coding: utf-8 -*-
"""SUT EK-4/F m.7 — Donepezil / Galantamin / Memantin / Rivastigmin / Riluzol.

Resmî lafız (EK-4/F ek listesi m.7; kullanıcı verdi 2026-06-04, ana SUT
tebliğ metni `SUT_tam_metin.txt`'te bulunmuyor — ek liste):
    "Donepezil HCl, Galantamin, Memantin, Rivastigmin, Riluzol (Nöroloji,
     geriatri, psikiyatri uzman hekimlerince raporsuz, bu hekimlerce
     düzenlenecek uzman hekim raporuna dayanılarak tüm hekimlerce ...)"

Alzheimer/demans (donepezil/galantamin/memantin/rivastigmin) + ALS (riluzol).
Glokom (4.2.11) ile aynı 2-paralel-yetki kalıbı; branş = nöroloji/geriatri/
psikiyatri. Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI PRENSİPLERİ.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ ( A: reçete eden nöroloji ∨ geriatri ∨ psikiyatri uzmanı )
          ∨ ( B: bu uzmanlarca düzenlenmiş uzman hekim raporu VAR )

  A → bu 3 uzman raporsuz reçete edebilir
  B → bu 3 uzmanca düzenlenmiş uzman hekim raporu varsa TÜM hekimler reçete eder

İki atom tek VEYA grubunda (≥1 yeterli). İkisi de YOK → UYGUN DEĞİL.
Branş okunamazsa KE+şartlı.

Ana entrypoint: ``demans_als_kontrol_ek4f_7(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC + etken + ticari
# ═══════════════════════════════════════════════════════════════════════
# N06DA* : antikolinesterazlar (donepezil/rivastigmin/galantamin)
# N06DX01: memantin ;  N07XX02: riluzol (ALS)
ATC_PREFIXLER = ('N06DA', 'N06DX01', 'N07XX02')
DEMANS_ALS_ETKEN: Set[str] = {
    'DONEPEZIL', 'GALANTAMIN', 'GALANTAMINE', 'MEMANTIN', 'MEMANTINE',
    'RIVASTIGMIN', 'RIVASTIGMINE', 'RILUZOL', 'RILUZOLE',
}
DEMANS_ALS_TICARI: Set[str] = {
    'ARICEPT', 'ARDEPIL', 'DONOPED', 'NORACEPT',      # donepezil
    'REMINYL',                                          # galantamin
    'EBIXA', 'AXURA', 'MEMANTIN', 'ABIXA',              # memantin
    'EXELON', 'RIVELON', 'RIVOR',                       # rivastigmin
    'RILUTEK', 'RILUZOL', 'TERAUD',                     # riluzol
}

# Yetkili branşlar (norm_tr_lower substring)
YETKILI_BRANS = ('noroloji', 'geriatri', 'psikiyatri', 'ruh sagligi')


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


def _brans_l(brans: Optional[str]) -> str:
    return norm_tr_lower(brans or '')


def _yetkili_brans_mi(brans: Optional[str]) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in YETKILI_BRANS)


def demans_als_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """EK-4/F m.7 ilacı mı? ATC N06DA*/N06DX01/N07XX02 veya etken/ticari."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if any(atc.startswith(p) for p in ATC_PREFIXLER):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, DEMANS_ALS_ETKEN) or _iceriyor(m, DEMANS_ALS_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR — tek VEYA grubu (yetki)
# ═══════════════════════════════════════════════════════════════════════

GRUP_YETKI = ('(7) Yetki — nöro/geriatri/psikiyatri reçete VEYA '
              'bu uzmanlarca rapor')


def atom_recete_yetkili(ilac_sonuc: Dict) -> SartSonuc:
    """A: reçeteyi yazan hekim nöroloji/geriatri/psikiyatri uzmanı mı?"""
    brans = (ilac_sonuc.get('recete_hekim_uzmanligi')
             or ilac_sonuc.get('doktor_uzmanligi')
             or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden nöro/geriatri/psikiyatri uzmanı',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_YETKI, veya_grubu=True,
                         sartli_atom=True)
    if _yetkili_brans_mi(brans):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Nöroloji/geriatri/psikiyatri uzmanı — raporsuz reçete edebilir',
                         kaynak='hekim_brans', grup=GRUP_YETKI, veya_grubu=True)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Yetkili uzman değil — bu uzmanlarca düzenlenmiş rapor gerekir',
                     kaynak='hekim_brans', grup=GRUP_YETKI, veya_grubu=True)


def atom_rapor_yetkili(ilac_sonuc: Dict) -> SartSonuc:
    """B: nöro/geriatri/psikiyatri uzmanınca düzenlenmiş uzman hekim raporu VAR mı?"""
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    if _yetkili_brans_mi(rb):
        return SartSonuc(ad='Nöro/geriatri/psikiyatri uzman hekim raporu',
                         durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb} — tüm hekimler reçete edebilir',
                         kaynak='rapor_brans', grup=GRUP_YETKI, veya_grubu=True)
    if not rapor_var:
        return SartSonuc(ad='Nöro/geriatri/psikiyatri uzman hekim raporu',
                         durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı yetkili uzman raporu yok',
                         kaynak='rapor', grup=GRUP_YETKI, veya_grubu=True)
    if rb:
        return SartSonuc(ad='Nöro/geriatri/psikiyatri uzman hekim raporu',
                         durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — nöro/geriatri/psikiyatri değil',
                         kaynak='rapor_brans', grup=GRUP_YETKI, veya_grubu=True)
    return SartSonuc(ad='Nöro/geriatri/psikiyatri uzman hekim raporu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş doğrulanamadı — manuel',
                     kaynak='rapor_brans', grup=GRUP_YETKI, veya_grubu=True,
                     sartli_atom=True)


def _demans_als_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_recete_yetkili(ilac_sonuc),
        atom_rapor_yetkili(ilac_sonuc),
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
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    parcalar = ['SUT EK-4/F m.7 Donepezil/Galantamin/Memantin/Rivastigmin/Riluzol']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — yetkili uzman reçetesi veya yetkili uzman raporu var')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — yetki branşı doğrulanamadı '
                        f'({len(ke)} şart manuel)')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — reçete eden yetkili uzman değil ve '
                        'nöro/geriatri/psikiyatri raporu yok')
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def demans_als_kontrol_ek4f_7(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4/F m.7 — Donepezil/Galantamin/Memantin/Rivastigmin/Riluzol."""
    if not demans_als_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='EK-4/F m.7 kapsamı dışı — demans/ALS ilacı değil',
            sut_kurali='SUT EK-4/F m.7')

    sartlar = _demans_als_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'DEMANS_ALS',
        'sut_maddesi': 'EK-4/F m.7',
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
        sut_kurali='SUT EK-4/F m.7 — Donepezil/Galantamin/Memantin/Rivastigmin/Riluzol',
        aranan_ibare='reçete nöro/geriatri/psikiyatri uzmanı VEYA bu uzmanlarca rapor',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("UYGUN (donepezil + nöroloji reçete)", {
            'etkin_madde': 'DONEPEZIL', 'atc_kodu': 'N06DA02',
            'doktor_uzmanligi': 'Nöroloji',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (memantin + geriatri reçete)", {
            'etkin_madde': 'MEMANTIN', 'atc_kodu': 'N06DX01',
            'doktor_uzmanligi': 'Geriatri',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (riluzol + psikiyatri reçete)", {
            'etkin_madde': 'RILUZOL', 'atc_kodu': 'N07XX02',
            'doktor_uzmanligi': 'Ruh Sağlığı ve Hastalıkları',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (rivastigmin + dahiliye reçete + nöroloji raporu)", {
            'etkin_madde': 'RIVASTIGMIN', 'atc_kodu': 'N06DA03',
            'doktor_uzmanligi': 'İç Hastalıkları',
            'rapor_doktor_brans': 'Nöroloji', 'rapor_kodu': '123',
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (dahiliye + rapor yok)", {
            'etkin_madde': 'GALANTAMIN', 'atc_kodu': 'N06DA04',
            'doktor_uzmanligi': 'İç Hastalıkları',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (aile hekimi + kardiyoloji raporu)", {
            'etkin_madde': 'DONEPEZIL', 'atc_kodu': 'N06DA02',
            'doktor_uzmanligi': 'Aile Hekimliği',
            'rapor_doktor_brans': 'Kardiyoloji', 'rapor_kodu': '5',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ŞARTLI (reçete branş bilinmiyor + rapor yok)", {
            'etkin_madde': 'MEMANTIN', 'atc_kodu': 'N06DX01',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN (ticari ARICEPT, dahiliye + geriatri raporu)", {
            'ilac_adi': 'ARICEPT 10 MG', 'etkin_madde': 'DONEPEZIL',
            'atc_kodu': 'N06DA02', 'doktor_uzmanligi': 'Aile Hekimliği',
            'rapor_doktor_brans': 'Geriatri', 'rapor_takip_no': '999',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (ticari EXELON ATC yok, psikiyatri reçete)", {
            'ilac_adi': 'EXELON 9.5 MG/24 SAAT', 'etkin_madde': 'RIVASTIGMIN',
            'doktor_uzmanligi': 'Psikiyatri',
        }, KontrolSonucu.UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT EK-4/F m.7 Demans/ALS — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = demans_als_kontrol_ek4f_7(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} :: {s.neden}")
    print("=" * 60)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
