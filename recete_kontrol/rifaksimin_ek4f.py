# -*- coding: utf-8 -*-
"""SUT EK-4 — Rifaksimin (form-bazlı endikasyon kısıtı).

Resmî lafız (kullanıcı verdi 2026-06-04; ana SUT tebliğ `SUT_tam_metin.txt`'te
bulunmuyor — ek liste / EK-4/E reçeteleme kuralı):
    Rifaksimin yalnızca;
    200 mg tablet için; akut gastrointestinal enfeksiyon, hiperamonemi
        tedavisinde ko-adjuvant olarak, diyare baskın irritabl bağırsak
        sendromu tedavisinde, (UH-P)
    550 mg tablet için; 18 yaş ve üzerindeki hastalarda aşikar (overt) hepatik
        ensefalopati epizodlarının tekrarının azaltılmasında. (UH-P)

Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI. FORM (200/550 mg) → endikasyon dispatcher.
(UH-P) reçeteleme kuralı → branş gate uygulanmadı (bilgi).

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (dispatcher: form/güç)
═══════════════════════════════════════════════════════════════════════════

  200 mg ⇔ E1(akut GİS enfeksiyonu) ∨ E2(hiperamonemi ko-adjuvant)
           ∨ E3(diyare baskın irritabl bağırsak sendromu)

  550 mg ⇔ A1(yaş ≥ 18) ∧ E4(aşikar/overt hepatik ensefalopati epizod tekrarı)

Endikasyon kaynaklarda bulunamazsa → KE+şartlı (örtük kabul yasağı). 550 mg'da
yaş<18 → YOK → UYGUN DEĞİL. Form okunamazsa 200 mg endikasyonları değerlendirilir
(daha geniş; not düşülür).

Ana entrypoint: ``rifaksimin_kontrol(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC A07AA11 rifaksimin
# ═══════════════════════════════════════════════════════════════════════
ATC_RIFAKSIMIN = 'A07AA11'
RIFAKSIMIN_ETKEN: Set[str] = {'RIFAKSIMIN', 'RIFAXIMIN', 'RIFAKSIMINE'}
RIFAKSIMIN_TICARI: Set[str] = {'NORMIX', 'TARGAXAN', 'XIFAXAN', 'RIFACOL',
                               'COLIDUR', 'RIVAXAL', 'RIFAXIM'}

# Endikasyon (200 mg) sinyalleri
GIS_ENF_ICD = ('A09', 'A04', 'A08')
GIS_ENF_METIN = ('gastrointestinal enfeksiyon', 'akut diyare', 'gastroenterit',
                 'enfeksiyoz diyare', 'enfeksiyöz diyare', 'barsak enfeksiyon',
                 'bagirsak enfeksiyon', 'ishal')
HIPERAMONEMI_METIN = ('hiperamonemi', 'hiperamonyemi', 'amonyak yuksek',
                      'amonemi', 'kan amonyak')
IBS_ICD = ('K58',)
IBS_METIN = ('irritabl barsak', 'irritabl bagirsak', 'irritabl bağırsak',
             'ibs', 'diyare baskin', 'diyare baskın', 'huzursuz barsak')
# Endikasyon (550 mg)
HE_ICD = ('K72', 'K70', 'K74', 'K76')
HE_METIN = ('hepatik ensefalopati', 'ensefalopati', 'karaciger ensefalopati',
            'overt', 'asikar')


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _ad(ilac_sonuc: Dict) -> str:
    return norm_tr_upper(ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '')


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


def rifaksimin_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_RIFAKSIMIN):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, RIFAKSIMIN_ETKEN) or _iceriyor(m, RIFAKSIMIN_TICARI)


def _form_guc(ilac_sonuc: Dict) -> str:
    """'550' | '200' | 'BELIRSIZ' (ilaç adındaki güçten)."""
    ad = _ad(ilac_sonuc)
    if re.search(r'\b550\b', ad) or '550 MG' in ad or 'TARGAXAN' in ad \
            or 'XIFAXAN' in ad:
        return '550'
    if re.search(r'\b200\b', ad) or '200 MG' in ad or 'NORMIX' in ad:
        return '200'
    return 'BELIRSIZ'


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_200 = '(200 mg) Endikasyon — GİS enf / hiperamonemi / diyare-baskın IBS'
GRUP_550_YAS = '(550 mg) Yaş ≥18'
GRUP_550_HE = '(550 mg) Aşikar hepatik ensefalopati (epizod tekrarı azaltma)'


def atom_200_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    gis = any(k in icd for k in GIS_ENF_ICD) or any(k in metin for k in GIS_ENF_METIN)
    hiper = any(k in metin for k in HIPERAMONEMI_METIN)
    ibs = any(k in icd for k in IBS_ICD) or any(k in metin for k in IBS_METIN)
    alt = [('Akut GİS enfeksiyonu', 'var' if gis else 'kontrol_edilemedi'),
           ('Hiperamonemi (ko-adjuvant)', 'var' if hiper else 'kontrol_edilemedi'),
           ('Diyare baskın IBS', 'var' if ibs else 'kontrol_edilemedi')]
    if gis or hiper or ibs:
        neden = ('akut GİS enfeksiyonu' if gis else 'hiperamonemi' if hiper
                 else 'diyare baskın IBS')
        return SartSonuc(ad='200 mg endikasyonu', durum=SartDurumu.VAR,
                         neden=neden, kaynak='ICD+rapor', grup=GRUP_200, alt_liste=alt)
    return SartSonuc(ad='200 mg endikasyonu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Akut GİS enf / hiperamonemi / diyare-baskın IBS endikasyonu '
                           'okunamadı — manuel (rifaksimin yalnız bu endikasyonlarda)',
                     kaynak='ICD+rapor', grup=GRUP_200, alt_liste=alt, sartli_atom=True)


def atom_550_yas(ilac_sonuc: Dict) -> SartSonuc:
    yas = _yas_oku(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad='Yaş ≥18', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı DB\'de yok — manuel', kaynak='hasta_yas',
                         grup=GRUP_550_YAS, sartli_atom=True)
    if yas >= 18:
        return SartSonuc(ad=f'Yaş {yas} (≥18)', durum=SartDurumu.VAR,
                         neden='18 yaş ve üzeri', kaynak='hasta_yas', grup=GRUP_550_YAS)
    return SartSonuc(ad=f'Yaş {yas} (≥18)', durum=SartDurumu.YOK,
                     neden=f'{yas} yaş — 550 mg yalnız 18 yaş ve üzeri',
                     kaynak='hasta_yas', grup=GRUP_550_YAS)


def atom_550_he(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    he = 'hepatik ensefalopati' in metin or 'karaciger ensefalopati' in metin \
        or any(k in icd for k in HE_ICD) and 'ensefalopati' in metin
    # ICD K72 tek başına da kabul (hepatik yetmezlik/ensefalopati)
    if not he and any(k in icd for k in ('K72',)):
        he = True
    if he:
        return SartSonuc(ad='Aşikar hepatik ensefalopati', durum=SartDurumu.VAR,
                         neden='hepatik ensefalopati endikasyonu', kaynak='ICD+rapor',
                         grup=GRUP_550_HE)
    return SartSonuc(ad='Aşikar hepatik ensefalopati', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Aşikar (overt) hepatik ensefalopati endikasyonu okunamadı — manuel',
                     kaynak='ICD+rapor', grup=GRUP_550_HE, sartli_atom=True)


def _rifaksimin_sartlari(ilac_sonuc: Dict, form: str) -> List[SartSonuc]:
    if form == '550':
        return [atom_550_yas(ilac_sonuc), atom_550_he(ilac_sonuc)]
    # 200 veya BELIRSIZ (geniş endikasyon → 200 yolu)
    return [atom_200_endikasyon(ilac_sonuc)]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (ortak grup-bazlı kalıp)
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


def _mesaj_uret(sonuc: KontrolSonucu, form: str, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    form_ad = {'550': '550 mg (hepatik ensefalopati)',
               '200': '200 mg (GİS/hiperamonemi/IBS)',
               'BELIRSIZ': '200 mg varsayım'}.get(form, form)
    parcalar = [f'SUT Rifaksimin / {form_ad}']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — endikasyon sağlandı')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — {len(ke)} şart manuel doğrulama gerektiriyor')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — ' + '; '.join(s.ad for s in yok[:2]))
    else:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def rifaksimin_kontrol(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT — Rifaksimin (200/550 mg form-bazlı endikasyon) kontrolü."""
    if not rifaksimin_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Kapsam dışı — rifaksimin değil',
            sut_kurali='SUT — Rifaksimin')

    form = _form_guc(ilac_sonuc)
    sartlar = _rifaksimin_sartlari(ilac_sonuc, form)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, form, sartlar)

    detaylar = {
        'alt_grup': 'RIFAKSIMIN',
        'sut_maddesi': 'Rifaksimin (EK-4)',
        'form_guc': form,
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
        sut_kurali='SUT — Rifaksimin (200/550 mg endikasyon kısıtı)',
        aranan_ibare='200mg: GİS enf/hiperamonemi/diyare-IBS · 550mg: ≥18 yaş + hepatik ensefalopati',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("200mg UYGUN (akut GİS enf ICD A09)", {
            'ilac_adi': 'NORMIX 200 MG', 'etkin_madde': 'RIFAKSIMIN', 'atc_kodu': 'A07AA11',
            'recete_teshisleri': ['A09'],
        }, KontrolSonucu.UYGUN),
        ("200mg UYGUN (diyare baskın IBS metin)", {
            'ilac_adi': 'NORMIX 200 MG', 'etkin_madde': 'RIFAKSIMIN',
            'rapor_aciklamalari': ['diyare baskın irritabl bağırsak sendromu'],
        }, KontrolSonucu.UYGUN),
        ("200mg UYGUN (hiperamonemi)", {
            'ilac_adi': 'RIFACOL 200 MG', 'etkin_madde': 'RIFAKSIMIN', 'atc_kodu': 'A07AA11',
            'rapor_aciklamalari': ['hiperamonemi tedavisi ko-adjuvant'],
        }, KontrolSonucu.UYGUN),
        ("200mg ŞARTLI (endikasyon okunamadı)", {
            'ilac_adi': 'NORMIX 200 MG', 'etkin_madde': 'RIFAKSIMIN', 'atc_kodu': 'A07AA11',
            'recete_teshisleri': ['Z00.0'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("550mg UYGUN (45 yaş + hepatik ensefalopati)", {
            'ilac_adi': 'TARGAXAN 550 MG', 'etkin_madde': 'RIFAKSIMIN', 'atc_kodu': 'A07AA11',
            'hasta_yasi': 45, 'recete_teshisleri': ['K72.9'],
            'rapor_aciklamalari': ['aşikar hepatik ensefalopati epizod tekrarı'],
        }, KontrolSonucu.UYGUN),
        ("550mg UYGUN DEĞİL (16 yaş)", {
            'ilac_adi': 'XIFAXAN 550 MG', 'etkin_madde': 'RIFAKSIMIN', 'atc_kodu': 'A07AA11',
            'hasta_yasi': 16, 'recete_teshisleri': ['K72.9'],
            'rapor_aciklamalari': ['hepatik ensefalopati'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("550mg ŞARTLI (yetişkin, HE okunamadı)", {
            'ilac_adi': 'TARGAXAN 550 MG', 'etkin_madde': 'RIFAKSIMIN', 'atc_kodu': 'A07AA11',
            'hasta_yasi': 50, 'recete_teshisleri': ['Z00.0'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("550mg ŞARTLI (yaş yok, HE var)", {
            'ilac_adi': 'TARGAXAN 550 MG', 'etkin_madde': 'RIFAKSIMIN', 'atc_kodu': 'A07AA11',
            'recete_teshisleri': ['K72.9'],
            'rapor_aciklamalari': ['hepatik ensefalopati'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT Rifaksimin — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = rifaksimin_kontrol(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 60)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
