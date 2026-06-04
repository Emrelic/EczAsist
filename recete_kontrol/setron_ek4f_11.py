# -*- coding: utf-8 -*-
"""SUT EK-4/F m.11 — 5-HT3 antiemetikleri (setronlar) doz limiti.

Resmî lafız (kullanıcı verdi 2026-06-04; ana SUT tebliğ `SUT_tam_metin.txt`'te
bulunmuyor — ek liste m.11):
    "Palonosetron HCl (her bir kemoterapi uygulamasında 7 gün için 1 flakon),
     Granisetron, Ondansetron, Tropisetron (21 günlük kür tedavisinde maksimum
     10 günlük dozda ödenir.)"

Saf doz/miktar limiti kuralı — branş/rapor şartı belirtilmemiştir.
Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI PRENSİPLERİ.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (dispatcher: etken)
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ DOZ_LIMIT
    Palonosetron  → F1(her KT uygulamasında 7 gün için ≤1 flakon)
    Granisetron / Ondansetron / Tropisetron
                  → F2(21 günlük kürde maksimum 10 günlük doz)

Kullanıcı kararı (aprepitant ile tutarlı, 2026-06-04): limit içinde → VAR;
aşımda → KONTROL_EDILEMEDI (manuel — reçetedeki kür/uygulama sayısı belirsiz).
Adet okunamazsa → KE+şartlı.

Ana entrypoint: ``setron_kontrol_ek4f_11(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC A04AA* (5-HT3 antagonistleri)
# ═══════════════════════════════════════════════════════════════════════
ATC_PALONOSETRON = 'A04AA05'
ATC_DIGER_SETRON = ('A04AA01', 'A04AA02', 'A04AA03')  # ondansetron/granisetron/tropisetron

PALONOSETRON_ETKEN: Set[str] = {'PALONOSETRON'}
PALONOSETRON_TICARI: Set[str] = {'ALOXI', 'PALONO', 'PALOXI'}

DIGER_SETRON_ETKEN: Set[str] = {
    'GRANISETRON', 'ONDANSETRON', 'TROPISETRON',
}
DIGER_SETRON_TICARI: Set[str] = {
    'KYTRIL', 'SETRON', 'GRANIKS', 'GRANEX',                 # granisetron
    'ZOFER', 'ZOFRAN', 'ONDAVELL', 'EMESET', 'ONDARAN', 'ONSETRON', 'ZONDAN',  # ondansetron
    'NAVOBAN',                                                # tropisetron
}


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


def setron_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """'PALO' | 'DIGER' | None."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    m = _arama_metni(ilac_sonuc)
    if atc.startswith(ATC_PALONOSETRON) or _iceriyor(m, PALONOSETRON_ETKEN) \
            or _iceriyor(m, PALONOSETRON_TICARI):
        return 'PALO'
    if any(atc.startswith(p) for p in ATC_DIGER_SETRON) \
            or _iceriyor(m, DIGER_SETRON_ETKEN) or _iceriyor(m, DIGER_SETRON_TICARI):
        return 'DIGER'
    return None


def setron_kapsami_mi(ilac_sonuc: Dict) -> bool:
    return setron_yolak_belirle(ilac_sonuc) is not None


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_PALO = '(PALO) Her KT uygulamasında 7 gün için ≤1 flakon'
GRUP_DIGER = '(DİĞER) 21 günlük kürde maksimum 10 günlük doz'


def atom_palonosetron_doz(ilac_sonuc: Dict) -> SartSonuc:
    adet = _adet_oku(ilac_sonuc)
    if adet is None:
        return SartSonuc(ad='Palonosetron ≤1 flakon (7 gün/KT uygulaması)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete flakon adedi okunamadı — manuel doğrula',
                         kaynak='doz', grup=GRUP_PALO, sartli_atom=True)
    if adet <= 1:
        return SartSonuc(ad='Palonosetron ≤1 flakon (7 gün/KT uygulaması)',
                         durum=SartDurumu.VAR,
                         neden=f'Flakon adedi {adet:g} — bir KT uygulaması için ≤1',
                         kaynak='doz', grup=GRUP_PALO)
    return SartSonuc(ad='Palonosetron ≤1 flakon (7 gün/KT uygulaması)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Flakon adedi {adet:g} — birden fazla KT uygulaması olabilir, '
                           f'her uygulamada ≤1 flakon manuel doğrula',
                     kaynak='doz', grup=GRUP_PALO, sartli_atom=True)


def atom_diger_setron_doz(ilac_sonuc: Dict) -> SartSonuc:
    adet = _adet_oku(ilac_sonuc)
    if adet is None:
        return SartSonuc(ad='≤10 günlük doz (21 günlük kür)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete kutu/doz adedi okunamadı — manuel doğrula',
                         kaynak='doz', grup=GRUP_DIGER, sartli_atom=True)
    if adet <= 1:
        return SartSonuc(ad='≤10 günlük doz (21 günlük kür)', durum=SartDurumu.VAR,
                         neden=f'Kutu adedi {adet:g} — 10 günlük doz için makul (~1 kutu)',
                         kaynak='doz', grup=GRUP_DIGER)
    return SartSonuc(ad='≤10 günlük doz (21 günlük kür)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Kutu adedi {adet:g} — 10 günlük dozu aşıyor olabilir, '
                           f'21 günlük kürde maks 10 gün manuel doğrula',
                     kaynak='doz', grup=GRUP_DIGER, sartli_atom=True)


def _setron_sartlari(ilac_sonuc: Dict, yolak: str) -> List[SartSonuc]:
    if yolak == 'PALO':
        return [atom_palonosetron_doz(ilac_sonuc)]
    return [atom_diger_setron_doz(ilac_sonuc)]


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


def _mesaj_uret(sonuc: KontrolSonucu, yolak: str, sartlar: List[SartSonuc]) -> str:
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    yolak_ad = {'PALO': 'Palonosetron (≤1 flakon/KT uygulaması)',
                'DIGER': 'Granisetron/Ondansetron/Tropisetron (≤10 gün/21 günlük kür)'}.get(
        yolak, yolak)
    parcalar = [f'EK-4/F m.11 Setron / {yolak_ad}']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — doz limiti içinde')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — doz limiti manuel doğrulama gerektiriyor '
                        f'({len(ke)} şart)')
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def setron_kontrol_ek4f_11(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4/F m.11 — 5-HT3 antiemetik (setron) doz limiti kontrolü."""
    yolak = setron_yolak_belirle(ilac_sonuc)
    if not yolak:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='EK-4/F m.11 kapsamı dışı — setron (5-HT3 antiemetik) değil',
            sut_kurali='SUT EK-4/F m.11')

    sartlar = _setron_sartlari(ilac_sonuc, yolak)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)

    detaylar = {
        'alt_grup': 'SETRON',
        'sut_maddesi': 'EK-4/F m.11',
        'yolak': yolak,
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
        sut_kurali='SUT EK-4/F m.11 — Setron (5-HT3 antiemetik) doz limiti',
        aranan_ibare='palonosetron ≤1 flakon / diğer setron ≤10 günlük doz (21 günlük kür)',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("Palonosetron UYGUN (1 flakon)", {
            'etkin_madde': 'PALONOSETRON', 'atc_kodu': 'A04AA05', 'kutu_sayisi': '1',
        }, KontrolSonucu.UYGUN),
        ("Palonosetron ŞARTLI (3 flakon — manuel)", {
            'etkin_madde': 'PALONOSETRON', 'atc_kodu': 'A04AA05', 'kutu_sayisi': '3',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Palonosetron ŞARTLI (adet okunamadı)", {
            'etkin_madde': 'PALONOSETRON', 'atc_kodu': 'A04AA05',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Ondansetron UYGUN (1 kutu)", {
            'etkin_madde': 'ONDANSETRON', 'atc_kodu': 'A04AA01', 'kutu_sayisi': '1',
        }, KontrolSonucu.UYGUN),
        ("Granisetron ŞARTLI (3 kutu — manuel)", {
            'etkin_madde': 'GRANISETRON', 'atc_kodu': 'A04AA02', 'kutu_sayisi': '3',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Tropisetron UYGUN (ticari NAVOBAN, 1 kutu)", {
            'ilac_adi': 'NAVOBAN 5 MG', 'etkin_madde': 'TROPISETRON', 'kutu_sayisi': '1',
        }, KontrolSonucu.UYGUN),
        ("Ondansetron UYGUN (ticari ZOFER, 1 kutu)", {
            'ilac_adi': 'ZOFER 8 MG', 'etkin_madde': 'ONDANSETRON',
            'atc_kodu': 'A04AA01', 'kutu_sayisi': '1',
        }, KontrolSonucu.UYGUN),
        ("Palonosetron UYGUN (ticari ALOXI, 1 flakon)", {
            'ilac_adi': 'ALOXI 250 MCG', 'etkin_madde': 'PALONOSETRON', 'kutu_sayisi': '1',
        }, KontrolSonucu.UYGUN),
        ("Kapsam dışı (aprepitant — NK1, setron değil)", {
            'etkin_madde': 'APREPITANT', 'atc_kodu': 'A04AD12',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT EK-4/F m.11 Setron — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = setron_kontrol_ek4f_11(ilac_sonuc)
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
