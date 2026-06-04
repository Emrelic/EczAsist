# -*- coding: utf-8 -*-
"""SUT EK-4/F — Meklozin (PRİZİN) endikasyon kısıtı.

Resmî lafız (kullanıcı verdi 2026-06-04; ana SUT tebliğ `SUT_tam_metin.txt`'te
bulunmuyor — ek liste). PRİZİN = meklozin (meklozin HCl), metoklopramid DEĞİL:
    "Yalnızca; gebelikte, operasyonlardan sonra, röntgen çekilmesinin ardından
     mide bulantısı ve kusmanın giderilmesinde kullanılması halinde bedelleri
     Kurumca karşılanır."

Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI PRENSİPLERİ. Saf endikasyon kısıtı —
branş / rapor / doz şartı yok.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ B1( gebelik ∨ ameliyat-sonrası ∨ röntgen-sonrası mide bulantısı/kusma )

Kullanıcı kararı (2026-06-04, KATI): bu üç endikasyondan biri saptanmazsa →
UYGUN DEĞİL (silence → YOK). Meklozinin diğer kullanımları (vertigo, taşıt
tutması vb.) bu SUT kapsamında DEĞİL.

Ana entrypoint: ``meklozin_kontrol(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC R06AE05 meklozin + etken + ticari
# ═══════════════════════════════════════════════════════════════════════
ATC_MEKLOZIN = ('R06AE05', 'R06AE55')  # meklozin (tek + kombinasyon)
MEKLOZIN_ETKEN: Set[str] = {'MEKLOZIN', 'MEKLOZ', 'MECLOZINE', 'MECLIZINE',
                            'MEKLOZIN HIDROKLORUR'}
MEKLOZIN_TICARI: Set[str] = {'PRIZIN', 'PRİZİN'}

# Endikasyon sinyalleri
GEBELIK_ICD = ('O21', 'Z33', 'Z34', 'O26')   # hiperemezis gravidarum / gebelik
GEBELIK_METIN = ('gebe', 'hamile', 'gebelik', 'hiperemezis', 'hyperemesis',
                 'gravidarum', 'bulantili gebe')
AMELIYAT_METIN = ('ameliyat sonras', 'operasyon sonras', 'postoperatif',
                  'post operatif', 'post-op', 'cerrahi sonras', 'ameliyattan sonra',
                  'operasyondan sonra')
RONTGEN_METIN = ('rontgen', 'röntgen', 'radyoloji', 'radyografi', 'baryum',
                 'kontrast madde', 'radyolojik tetkik', 'rontgen sonras',
                 'rontgen cekil', 'goruntuleme sonras')


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


def meklozin_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if any(atc.startswith(p) for p in ATC_MEKLOZIN):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, MEKLOZIN_ETKEN) or _iceriyor(m, MEKLOZIN_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# ATOM — tek endikasyon kapısı (3 alt-bağlam OR)
# ═══════════════════════════════════════════════════════════════════════

GRUP_ENDIKASYON = ('(1) Endikasyon — gebelik / ameliyat sonrası / röntgen '
                   'sonrası bulantı-kusma')


def atom_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_recete_metni(ilac_sonuc)
    gebelik = any(k in icd for k in GEBELIK_ICD) or any(k in metin for k in GEBELIK_METIN)
    ameliyat = any(k in metin for k in AMELIYAT_METIN)
    rontgen = any(k in metin for k in RONTGEN_METIN)
    alt = [('Gebelik', 'var' if gebelik else 'yok'),
           ('Ameliyat sonrası', 'var' if ameliyat else 'yok'),
           ('Röntgen sonrası', 'var' if rontgen else 'yok')]
    if gebelik or ameliyat or rontgen:
        neden = ('gebelik' if gebelik else 'ameliyat sonrası' if ameliyat
                 else 'röntgen sonrası')
        return SartSonuc(ad='Endikasyon (gebelik/ameliyat/röntgen sonrası bulantı)',
                         durum=SartDurumu.VAR, neden=f'{neden} bulantı/kusma endikasyonu',
                         kaynak='ICD+metin', grup=GRUP_ENDIKASYON, alt_liste=alt)
    # KATI (kullanıcı kararı 2026-06-04): bu 3 endikasyon yoksa UYGUN DEĞİL
    return SartSonuc(ad='Endikasyon (gebelik/ameliyat/röntgen sonrası bulantı)',
                     durum=SartDurumu.YOK,
                     neden='Gebelik/ameliyat sonrası/röntgen sonrası bulantı endikasyonu '
                           'saptanmadı — meklozin yalnız bu 3 durumda karşılanır',
                     kaynak='ICD+metin', grup=GRUP_ENDIKASYON, alt_liste=alt)


def _meklozin_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [atom_endikasyon(ilac_sonuc)]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (tek grup)
# ═══════════════════════════════════════════════════════════════════════

def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    durumlar = [s.durum for s in sartlar if '(bilgi)' not in (s.grup or '')]
    if any(d == SartDurumu.YOK for d in durumlar):
        return KontrolSonucu.UYGUN_DEGIL
    if all(d == SartDurumu.VAR for d in durumlar) and durumlar:
        return KontrolSonucu.UYGUN
    return KontrolSonucu.KONTROL_EDILEMEDI


def _mesaj_uret(sonuc: KontrolSonucu, sartlar: List[SartSonuc]) -> str:
    parcalar = ['SUT Meklozin (PRİZİN)']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — gebelik/ameliyat/röntgen sonrası bulantı endikasyonu')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — kapsam içi endikasyon (gebelik/ameliyat/'
                        'röntgen sonrası) saptanmadı')
    else:
        parcalar.append('ŞÜPHELİ — endikasyon kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def meklozin_kontrol(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4/F — Meklozin (PRİZİN) endikasyon kısıtı kontrolü."""
    if not meklozin_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Kapsam dışı — meklozin (PRİZİN) değil',
            sut_kurali='SUT — Meklozin')

    sartlar = _meklozin_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'MEKLOZIN',
        'sut_maddesi': 'EK-4/F Meklozin',
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
        sut_kurali='SUT EK-4/F — Meklozin (PRİZİN) gebelik/ameliyat/röntgen sonrası bulantı',
        aranan_ibare='gebelik VEYA ameliyat sonrası VEYA röntgen sonrası bulantı-kusma',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("UYGUN (gebelik ICD O21)", {
            'etkin_madde': 'MEKLOZIN', 'atc_kodu': 'R06AE05',
            'recete_teshisleri': ['O21.0'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN (gebelik metin)", {
            'ilac_adi': 'PRIZIN', 'etkin_madde': 'MEKLOZIN',
            'rapor_aciklamalari': ['gebelikte bulantı kusma'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN (ameliyat sonrası)", {
            'etkin_madde': 'MEKLOZIN', 'atc_kodu': 'R06AE05',
            'recete_aciklamalari': ['operasyon sonrası bulantı'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN (röntgen sonrası)", {
            'etkin_madde': 'MECLIZINE', 'atc_kodu': 'R06AE05',
            'rapor_aciklamalari': ['röntgen çekilmesi ardından bulantı kusma'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (vertigo — kapsam dışı endikasyon)", {
            'etkin_madde': 'MEKLOZIN', 'atc_kodu': 'R06AE05',
            'recete_teshisleri': ['H81.1'], 'rapor_aciklamalari': ['vertigo baş dönmesi'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (taşıt tutması)", {
            'ilac_adi': 'PRIZIN', 'etkin_madde': 'MEKLOZIN',
            'rapor_aciklamalari': ['taşıt tutması bulantı'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (endikasyon boş)", {
            'etkin_madde': 'MEKLOZIN', 'atc_kodu': 'R06AE05',
            'recete_teshisleri': ['Z00.0'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Kapsam dışı (metoklopramid — meklozin değil)", {
            'etkin_madde': 'METOKLOPRAMID', 'atc_kodu': 'A03FA01',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("UYGUN (ticari PRİZİN + gebe)", {
            'ilac_adi': 'PRİZİN 25 MG', 'etkin_madde': 'MEKLOZIN HIDROKLORUR',
            'rapor_aciklamalari': ['hamile hasta bulantı kusma'],
        }, KontrolSonucu.UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT Meklozin (PRİZİN) — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = meklozin_kontrol(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} :: {s.neden}")
    print("=" * 60)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
