# -*- coding: utf-8 -*-
"""Pentoksifilin (TRENTAL, ATC C04AD03) — EK-4/D muafiyet kontrolü.

⚠️ Kapsam: YALNIZ PENTOKSİFİLİN. Kalsiyum dobesilat (C05BX01) AYRI modülde
(`dobesilat_genel_raporlu_4_1_4.py`, SUT 4.1.4 genel-raporlu çerçevesi) işlenir —
bu iki etken sık birlikte reçetelense de ayrı ele alınır.

Resmî mevzuat bulgusu (2026-07-05, primary source taraması):
    • Ana SUT tebliğ (`docs/sut/SUT_tam_metin.txt`) 4.2.x özel maddelerinde
      pentoksifilin YOK.
    • EK-4/F (Ayakta Tedavide Sağlık Raporu ile Verilebilecek İlaçlar) YOK
      → RAPOR ZORUNLU DEĞİL; raporsuz da ödenir (SUT 4.1.4/4.1.8, katılım paylı).
    • EK-4/D (Hasta Katılım Payından Muaf İlaçlar) VAR, iki başlık:
        - m.4.4 "Periferik ve serebral damar hastalıkları, venöz yetmezlikler"
          → 4.4.3 "Periferik ve serebral damar düzenleyiciler" (pentoksifilin =
          periferik vazodilatör, C04AD). ICD: G46, I63, I65-I70, I71.2/4/6/9,
          I72, I73.1, I73.8, I73.9, I74, I77, I79.0, I79.2, I82, I83.0, I83.2,
          I85.9, I87.
        - m.4.11 "Raynaud hastalığı (I73.0)" → 4.11.3 "Pentoksifilin"
          (pentoksifilin AÇIKÇA adıyla listeli).

Kaynak: SGK "Hasta Katılım Payından Muaf İlaçlar Listesi (EK-4/D)" resmî .doc.

═══════════════════════════════════════════════════════════════════════════
KARAR AKIŞI / MANTIK FORMÜLÜ
═══════════════════════════════════════════════════════════════════════════
Düşük-kısıtlı grup: EK-4/F kapısı olmadığından ödemeyi engelleyen sert bir SUT
şartı YOKTUR. Kontrol = KATILIM PAYI MUAFİYETİ doğrulaması (EK-4/D ICD eşleşmesi).

  Muafiyet ICD değerlendirmesi (rapor teşhisi):
     muaf_44   : ICD ∈ 4.4 damar/venöz listesi   → MUAF
     raynaud   : ICD = I73.0                       → MUAF (m.4.11.3)
     muaf_disi : ICD var ama 4.4/4.11 dışı         → ÖDENİR, muaf DEĞİL (paylı)
     okunamadi : rapor var, ICD boş/okunamadı      → ŞÜPHELİ (manuel — örtük kabul yasak)

  SONUÇ:
     rapor YOK                → UYGUN  (raporsuz ödenir, katılım paylı)
     muaf_44 ∨ raynaud        → UYGUN  (katılım payından muaf)
     muaf_disi                → UYGUN  (ödenir; muaf değil, paylı)
     okunamadi (rapor var)    → ŞÜPHELİ

Ana entrypoint: ``pentoksifilin_kontrol_ek4d(ilac_sonuc)`` → ``KontrolRaporu``.
Kapsam tespiti: ``pentoksifilin_kapsami_mi(ilac_sonuc)``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC C04AD03 pentoksifilin
# ═══════════════════════════════════════════════════════════════════════
ATC_PENTOKSIFILIN = 'C04AD03'
PENTOKS_ETKEN: Set[str] = {'PENTOKSIFILIN', 'PENTOKSIFILLIN', 'PENTOXIFYLLINE',
                           'PENTOXIFYLLIN', 'OKSPENTIFILIN', 'OXPENTIFYLLINE'}
PENTOKS_TICARI: Set[str] = {'TRENTAL', 'TRENTILIN', 'PENTOX'}


# ═══════════════════════════════════════════════════════════════════════
# EK-4/D Madde 4.4 — muafiyet ICD kümesi (periferik/serebral damar + venöz)
# ═══════════════════════════════════════════════════════════════════════
MUAF_44_PREFIX: Tuple[str, ...] = (
    'G46',                          # serebrovasküler sendromlar
    'I63', 'I65', 'I66', 'I67', 'I68', 'I69',  # I63 + I65-I69 (I65-I70 aralığı)
    'I70',                          # ateroskleroz
    'I71',                          # aort anevrizması (4.4: .2/.4/.6/.9 — pragmatik geniş)
    'I72',                          # diğer anevrizmalar
    'I74',                          # arteriyel embolizm/tromboz
    'I77',                          # arter/arteriyol diğer bozuklukları
    'I79',                          # damar bozuklukları BYS hastalıklarda (.0*/.2*)
    'I82',                          # venöz emboli/tromboz diğer
    'I83',                          # alt ekstremite varisi
    'I85',                          # özofagus varisi
    'I87',                          # venöz diğer bozukluklar (I87.2 kronik venöz yetm.)
)
# I73 özel: I73.0=Raynaud (4.11), I73.1/.8/.9=4.4. Bare 'I73' → periferik damar (4.4).


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


def _atc(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')


def pentoksifilin_kapsami_mi(ilac_sonuc: Dict) -> bool:
    if _atc(ilac_sonuc).startswith(ATC_PENTOKSIFILIN):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, PENTOKS_ETKEN) or _iceriyor(m, PENTOKS_TICARI)


def _teshis_tokenlari(ilac_sonuc: Dict) -> List[str]:
    """Rapor/reçete teşhis ICD kodlarını normalize edilmiş liste olarak topla."""
    ham: List[str] = []
    for anahtar in ('recete_teshisleri', 'rec_tesh', 'rap_tesh',
                    'teshis_kodu_listesi', 'teshis_kodu', 'teshis_tum',
                    'diger_raporlar_icd', 'rapor_teshisleri'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            ham.extend(str(x) for x in v if x)
        elif v:
            ham.append(str(v))
    tokenlar: List[str] = []
    for parca in ham:
        for tok in norm_tr_upper(parca).replace(';', ',').replace('|', ',').split(','):
            tok = tok.strip().replace(' ', '')
            if tok:
                tokenlar.append(tok)
    return tokenlar


def _rapor_var_mi(ilac_sonuc: Dict) -> bool:
    for anahtar in ('rapor_kodu', 'rap_kod', 'rapor_takip_no', 'rapor_turu',
                    'rapor_metni', 'tum_metin', 'rapor_doktor_brans',
                    'rapor_aciklamalari', 'rapor_kodu_aciklama'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            if any(x for x in v):
                return True
        elif v and str(v).strip():
            return True
    return False


def _is_raynaud(tok: str) -> bool:
    return tok.startswith('I73.0') or tok.startswith('I730')


def _is_muaf_44(tok: str) -> bool:
    if any(tok.startswith(p) for p in MUAF_44_PREFIX):
        return True
    # I73.1 / I73.8 / I73.9 ve bare I73 (periferik damar) → 4.4; I73.0 hariç
    if tok.startswith('I73') and not _is_raynaud(tok):
        return True
    return False


def _icd_muafiyet(tokenlar: List[str]) -> Tuple[str, Optional[str]]:
    """ICD kümesini EK-4/D muafiyeti açısından değerlendir.

    Dönüş: (durum, eslesen_kod)
      'muaf_44'   : 4.4 damar/venöz listesinde
      'raynaud'   : I73.0 (m.4.11.3 pentoksifilin)
      'muaf_disi' : ICD var ama 4.4/4.11 dışı
      'okunamadi' : hiç ICD tokenı yok
    """
    if not tokenlar:
        return ('okunamadi', None)
    raynaud_kod: Optional[str] = None
    diger_kod: Optional[str] = None
    for tok in tokenlar:
        if _is_muaf_44(tok):
            return ('muaf_44', tok)
        if _is_raynaud(tok):
            raynaud_kod = tok
        else:
            diger_kod = tok
    if raynaud_kod:
        return ('raynaud', raynaud_kod)
    if diger_kod:
        return ('muaf_disi', diger_kod)
    return ('okunamadi', None)


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_KAPSAM = 'Ödeme kapsamı (EK-4/F dışı — rapor zorunlu değil)'
GRUP_MUAF = 'Katılım payı muafiyeti (EK-4/D 4.4/4.11)'
GRUP_MIKTAR = 'Miktar/doz (bilgi)'
GRUP_ENDIK = 'Endikasyon (bilgi)'


def atom_odeme_kapsami(ilac_sonuc: Dict) -> SartSonuc:
    """İlaç ödeme kapsamında mı? EK-4/F dışı → rapor zorunlu değil, hep VAR."""
    return SartSonuc(
        ad='Ödeme kapsamı', durum=SartDurumu.VAR,
        neden='EK-4/F dışı — rapor zorunlu değil; raporsuz da ödenir (katılım paylı)',
        kaynak='EK-4/D/F', grup=GRUP_KAPSAM)


def atom_muafiyet(ilac_sonuc: Dict) -> SartSonuc:
    """EK-4/D katılım payı muafiyeti değerlendirmesi (ana atom)."""
    rapor_var = _rapor_var_mi(ilac_sonuc)
    tokenlar = _teshis_tokenlari(ilac_sonuc)
    durum, kod = _icd_muafiyet(tokenlar)

    if not rapor_var:
        return SartSonuc(
            ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
            neden='Rapor yok — raporsuz ödenir (katılım payı alınır); muafiyet '
                  'için rapor + uygun ICD (EK-4/D 4.4/4.11) gerekir',
            kaynak='rapor', grup=GRUP_MUAF)
    if durum == 'muaf_44':
        return SartSonuc(
            ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
            neden=f'Rapor ICD {kod} → EK-4/D m.4.4 (periferik/serebral damar, '
                  f'venöz yetmezlik) — katılım payından MUAF',
            kaynak='ICD', grup=GRUP_MUAF)
    if durum == 'raynaud':
        return SartSonuc(
            ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
            neden=f'Rapor ICD {kod} Raynaud → EK-4/D m.4.11.3 pentoksifilin — '
                  f'katılım payından MUAF',
            kaynak='ICD', grup=GRUP_MUAF)
    if durum == 'muaf_disi':
        return SartSonuc(
            ad='Katılım payı muafiyeti', durum=SartDurumu.VAR,
            neden=f'Rapor ICD {kod} EK-4/D m.4.4/4.11 dışı → ödenir ama katılım '
                  f'payından muaf DEĞİL (paylı)',
            kaynak='ICD', grup=GRUP_MUAF)
    # okunamadi
    return SartSonuc(
        ad='Katılım payı muafiyeti', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Rapor var ama teşhis ICD okunamadı — muafiyet (EK-4/D 4.4/4.11) '
              'manuel doğrulanmalı (örtük kabul yasağı)',
        kaynak='ICD', grup=GRUP_MUAF)


def atom_miktar_bilgi(ilac_sonuc: Dict) -> SartSonuc:
    """(bilgi) Miktar/doz — parse zayıf, matematiği bozmaz."""
    return SartSonuc(
        ad='Miktar/doz sınırı', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Raporlu: en fazla 3 aylık doz; raporsuz: kısa süreli (en küçük '
              'ambalaj) — miktar manuel kontrol edilir',
        kaynak='miktar', grup=GRUP_MIKTAR, sartli_atom=True)


def atom_endikasyon_bilgi(ilac_sonuc: Dict) -> SartSonuc:
    """(bilgi) Onaylı endikasyon / endikasyon-dışı farkındalık."""
    return SartSonuc(
        ad='Onaylı endikasyon', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Pentoksifilin onaylı endikasyonu periferik arter hastalığı; farklı '
              'endikasyonda Sağlık Bakanlığı endikasyon-dışı onayı gerekebilir '
              '(SUT uyarı 223) — manuel',
        kaynak='endikasyon', grup=GRUP_ENDIK, sartli_atom=True)


def _sartlari_uret(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_odeme_kapsami(ilac_sonuc),
        atom_muafiyet(ilac_sonuc),
        atom_miktar_bilgi(ilac_sonuc),        # bilgi
        atom_endikasyon_bilgi(ilac_sonuc),    # bilgi
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (grup-bazlı ortak kalıp — bilgi grupları hesaptan çıkar)
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
    muaf_atom = next((s for s in sartlar if s.grup == GRUP_MUAF), None)
    neden = (muaf_atom.neden if muaf_atom else '') or ''
    parcalar = ['Pentoksifilin (EK-4/D)']
    if sonuc == KontrolSonucu.UYGUN:
        if 'MUAF' in neden and 'muaf DEĞİL' not in neden:
            parcalar.append('UYGUN — katılım payından MUAF (EK-4/D)')
        else:
            parcalar.append('UYGUN — ödenir (katılım paylı; muafiyet yok/rapor yok)')
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append('ŞÜPHELİ — rapor var, ICD okunamadı; muafiyeti manuel doğrula')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append('ŞARTLI UYGUN — bilgi şartları manuel doğrula')
    else:
        parcalar.append(sonuc.value)
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def pentoksifilin_kontrol_ek4d(ilac_sonuc: Dict) -> KontrolRaporu:
    """Pentoksifilin (TRENTAL) — EK-4/D muafiyet kontrolü."""
    if not pentoksifilin_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Kapsam dışı — pentoksifilin değil',
            sut_kurali='EK-4/D m.4.4/4.11')

    sartlar = _sartlari_uret(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'PENTOKSIFILIN',
        'etken': 'PENTOKSIFILIN',
        'sut_maddesi': 'EK-4/D m.4.4 (+m.4.11.3 Raynaud)',
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
        sut_kurali='EK-4/D m.4.4 periferik/serebral damar + venöz yetmezlik '
                   '(pentoksifilin ayrıca m.4.11.3 Raynaud); EK-4/F dışı → '
                   'raporsuz ödenir',
        aranan_ibare='EK-4/F dışı (raporsuz ödenir) + EK-4/D muafiyet ICD',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("UYGUN muaf (TRENTAL + periferik damar I73.9)", {
            'ilac_adi': 'TRENTAL CR 600 MG', 'etkin_madde': 'PENTOKSIFILIN',
            'atc_kodu': 'C04AD03', 'rapor_kodu': '1',
            'recete_teshisleri': ['I73.9'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (venöz yetmezlik I87.2)", {
            'etkin_madde': 'PENTOKSIFILIN', 'atc_kodu': 'C04AD03',
            'rapor_kodu': '1', 'recete_teshisleri': ['I87.2'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (Raynaud I73.0 → m.4.11.3)", {
            'etkin_madde': 'PENTOKSIFILIN', 'atc_kodu': 'C04AD03',
            'rapor_kodu': '1', 'recete_teshisleri': ['I73.0'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (serebrovasküler I63.9)", {
            'etkin_madde': 'PENTOKSIFILIN', 'atc_kodu': 'C04AD03',
            'rapor_kodu': '1', 'recete_teshisleri': ['I63.9'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf (G46.0 + ticari ad, etken boş)", {
            'ilac_adi': 'TRENTILIN RETARD 600', 'etkin_madde': '',
            'rapor_kodu': '1', 'rec_tesh': 'G46.0',
        }, KontrolSonucu.UYGUN),
        ("UYGUN muaf-değil (alakasız ICD J06.9 → ödenir paylı)", {
            'etkin_madde': 'PENTOKSIFILIN', 'atc_kodu': 'C04AD03',
            'rapor_kodu': '1', 'recete_teshisleri': ['J06.9'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN raporsuz (TRENTAL, rapor yok → paylı ödenir)", {
            'ilac_adi': 'TRENTAL', 'etkin_madde': 'PENTOKSIFILIN',
            'atc_kodu': 'C04AD03',
        }, KontrolSonucu.UYGUN),
        ("ŞÜPHELİ (rapor var, ICD okunamadı)", {
            'etkin_madde': 'PENTOKSIFILIN', 'atc_kodu': 'C04AD03',
            'rapor_kodu': '1', 'rapor_doktor_brans': 'Kardiyoloji',
        }, KontrolSonucu.KONTROL_EDILEMEDI),
        ("Kapsam dışı (kalsiyum dobesilat — ayrı modül)", {
            'ilac_adi': 'DOXIUM 500', 'etkin_madde': 'KALSIYUM DOBESILAT',
            'atc_kodu': 'C05BX01',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("Pentoksifilin EK-4/D — Akıl Testi\n" + "=" * 58)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = pentoksifilin_kontrol_ek4d(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 58)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
