# -*- coding: utf-8 -*-
"""SUT — Finasterid / Dutasterid (5-alfa redüktaz inhibitörü, BPH).

Resmî lafız (kullanıcı verdi 2026-06-04; ana SUT tebliğ `SUT_tam_metin.txt`'te
bulunmuyor — EK/ek liste):
    "Üroloji uzman hekimince veya bu uzman hekimin düzenlediği 6 ay süreli
     uzman hekim raporuna dayanılarak tüm hekimlerce reçete edilebilir.
     Finasterid, dutasterid (tamsulosin kombinasyonları dahil) etken maddeli
     ilaçların kombine kullanılması halinde Kurumca bedelleri karşılanmaz."

Glokom/demans (2-paralel-yetki) kalıbı + KOMBİNE KULLANIM YASAĞI (tek NOT
atomu). Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI PRENSİPLERİ.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ ( A: reçete eden üroloji uzmanı
            ∨ B: üroloji uzmanınca düzenlenmiş 6 ay süreli uzman hekim raporu )
          ∧ G1( finasterid/dutasterid kombine kullanım YOK )
          [bilgi: rapor 6 ay süreli]

  A/B → tek VEYA grubu (≥1 yeterli). G1 → tek NOT atomu (aynı reçetede 2.
  finasterid/dutasterid içeren ürün varsa kombine → YOK → UYGUN DEĞİL).
  "tamsulosin kombinasyonları dahil" → DUODART (dutasterid+tamsulosin) de 5-ARI sayılır.

Ana entrypoint: ``finasterid_dutasterid_kontrol(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti
# ═══════════════════════════════════════════════════════════════════════
# G04CB01 finasterid, G04CB02 dutasterid; G04CA52 dutasterid+tamsulosin (DUODART)
ATC_5ARI_PREFIX = ('G04CB',)
ATC_5ARI_KOMBO = ('G04CA52',)  # dutasterid + tamsulosin
ARI5_ETKEN: Set[str] = {'FINASTERID', 'FINASTERIDE', 'DUTASTERID', 'DUTASTERIDE'}
ARI5_TICARI: Set[str] = {
    'PROSCAR', 'PROPECIA', 'FINPROS', 'FINASTER', 'PROSTACOM', 'FINARID',
    'AVODART', 'DUTAS', 'DUODART', 'COMBODART', 'DUOPROST', 'DUTPROST',
}

# Üroloji branş anahtarı
UROLOJI = ('uroloji',)


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


def _uroloji_mi(brans: Optional[str]) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in UROLOJI)


def _metin_5ari_mi(ad: str, etken: str, atc: str = '') -> bool:
    """Verilen ad/etken/ATC bir finasterid/dutasterid (tamsulosin kombo dahil) mi?"""
    a = norm_tr_upper(atc or '')
    if any(a.startswith(p) for p in ATC_5ARI_PREFIX) or any(
            a.startswith(p) for p in ATC_5ARI_KOMBO):
        return True
    m = norm_tr_upper((ad or '') + ' ' + (etken or ''))
    return _iceriyor(m, ARI5_ETKEN) or _iceriyor(m, ARI5_TICARI)


def finasterid_dutasterid_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """Finasterid/dutasterid (tamsulosin kombo dahil) ürünü mü?"""
    return _metin_5ari_mi(
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
        ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_YETKI = '(1) Yetki — üroloji reçete VEYA üroloji uzmanı raporu'
GRUP_SURE = '(1) Rapor 6 ay süreli (bilgi)'
GRUP_KOMBI = '(2) Kombine kullanım yasağı (finasterid/dutasterid)'


def atom_recete_uroloji(ilac_sonuc: Dict) -> SartSonuc:
    """A: reçeteyi yazan hekim üroloji uzmanı mı?"""
    brans = (ilac_sonuc.get('recete_hekim_uzmanligi')
             or ilac_sonuc.get('doktor_uzmanligi')
             or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden üroloji uzmanı', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_YETKI, veya_grubu=True,
                         sartli_atom=True)
    if _uroloji_mi(brans):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Üroloji uzmanı — raporsuz reçete edebilir',
                         kaynak='hekim_brans', grup=GRUP_YETKI, veya_grubu=True)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Üroloji uzmanı değil — üroloji uzmanı raporu gerekir',
                     kaynak='hekim_brans', grup=GRUP_YETKI, veya_grubu=True)


def atom_rapor_uroloji(ilac_sonuc: Dict) -> SartSonuc:
    """B: üroloji uzmanınca düzenlenmiş uzman hekim raporu VAR mı?"""
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    if _uroloji_mi(rb):
        return SartSonuc(ad='Üroloji uzmanı raporu (6 ay süreli)', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb} — tüm hekimler reçete edebilir',
                         kaynak='rapor_brans', grup=GRUP_YETKI, veya_grubu=True)
    if not rapor_var:
        return SartSonuc(ad='Üroloji uzmanı raporu (6 ay süreli)', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı üroloji uzmanı raporu yok',
                         kaynak='rapor', grup=GRUP_YETKI, veya_grubu=True)
    if rb:
        return SartSonuc(ad='Üroloji uzmanı raporu (6 ay süreli)', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — üroloji değil',
                         kaynak='rapor_brans', grup=GRUP_YETKI, veya_grubu=True)
    return SartSonuc(ad='Üroloji uzmanı raporu (6 ay süreli)', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş üroloji olarak '
                           'doğrulanamadı — manuel', kaynak='rapor_brans',
                     grup=GRUP_YETKI, veya_grubu=True, sartli_atom=True)


def atom_rapor_6ay(ilac_sonuc: Dict) -> SartSonuc:
    """(bilgi) Rapor 6 ay süreli (path B için). Tarih parse zayıf → KE bilgi."""
    from datetime import date, datetime
    bas = ilac_sonuc.get('rapor_baslangic_tarihi') or ilac_sonuc.get('rapor_bas_tarihi')
    bit = ilac_sonuc.get('rapor_bitis_tarihi') or ilac_sonuc.get('rapor_son_tarihi')

    def _parse(d):
        if isinstance(d, date):
            return d
        if not d:
            return None
        s = str(d).strip()
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y',
                    '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
            try:
                return datetime.strptime(s[:len(fmt) + 4], fmt).date()
            except ValueError:
                continue
        return None

    d_bas, d_bit = _parse(bas), _parse(bit)
    if d_bas and d_bit:
        gun = (d_bit - d_bas).days
        if gun <= 190:
            return SartSonuc(ad='Rapor süresi 6 ay', durum=SartDurumu.VAR,
                             neden=f'Rapor süresi {gun} gün — 6 ay sınırında',
                             kaynak='rapor_tarihleri', grup=GRUP_SURE)
        return SartSonuc(ad='Rapor süresi 6 ay', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=f'Rapor süresi {gun} gün — 6 ayı aşıyor olabilir, manuel',
                         kaynak='rapor_tarihleri', grup=GRUP_SURE, sartli_atom=True)
    return SartSonuc(ad='Rapor süresi 6 ay', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor başlangıç/bitiş tarihi yok — manuel doğrula',
                     kaynak='rapor_tarihleri', grup=GRUP_SURE, sartli_atom=True)


def atom_kombi_yasagi(ilac_sonuc: Dict) -> SartSonuc:
    """G1 (NOT): aynı reçetede 2. finasterid/dutasterid (tamsulosin kombo dahil) yok."""
    diger_etken = ilac_sonuc.get('diger_etken_maddeler') or []
    diger_ilac = ilac_sonuc.get('diger_ilac_adlari') or []
    eslesen: List[str] = []
    n = max(len(diger_etken) if isinstance(diger_etken, (list, tuple)) else 0,
            len(diger_ilac) if isinstance(diger_ilac, (list, tuple)) else 0)
    de = list(diger_etken) if isinstance(diger_etken, (list, tuple)) else []
    di = list(diger_ilac) if isinstance(diger_ilac, (list, tuple)) else []
    for i in range(n):
        et = de[i] if i < len(de) else ''
        ad = di[i] if i < len(di) else ''
        if _metin_5ari_mi(ad, et):
            eslesen.append((ad or et or '?'))
    if eslesen:
        return SartSonuc(ad='Kombine kullanım yok', durum=SartDurumu.YOK,
                         neden='Aynı reçetede başka finasterid/dutasterid ürünü var '
                               f'({", ".join(eslesen[:3])}) — kombine kullanım ödenmez',
                         kaynak='recete_kalemleri', grup=GRUP_KOMBI)
    return SartSonuc(ad='Kombine kullanım yok', durum=SartDurumu.VAR,
                     neden='Reçetede başka finasterid/dutasterid ürünü yok',
                     kaynak='recete_kalemleri', grup=GRUP_KOMBI)


def _finasterid_dutasterid_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_recete_uroloji(ilac_sonuc),
        atom_rapor_uroloji(ilac_sonuc),
        atom_kombi_yasagi(ilac_sonuc),
        atom_rapor_6ay(ilac_sonuc),  # bilgi
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
    parcalar = ['SUT Finasterid/Dutasterid (BPH 5-ARI)']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — üroloji yetkisi var ve kombine kullanım yok')
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

def finasterid_dutasterid_kontrol(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT — Finasterid/Dutasterid (BPH 5-ARI) kontrolü."""
    if not finasterid_dutasterid_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Kapsam dışı — finasterid/dutasterid ürünü değil',
            sut_kurali='SUT — Finasterid/Dutasterid')

    sartlar = _finasterid_dutasterid_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'FINDUT',
        'sut_maddesi': 'Finasterid/Dutasterid (BPH 5-ARI)',
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
        sut_kurali='SUT — Finasterid/Dutasterid (BPH 5-ARI) üroloji + kombi yasağı',
        aranan_ibare='reçete/rapor üroloji uzmanı + finasterid/dutasterid kombine değil',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("UYGUN (finasterid + üroloji reçete)", {
            'etkin_madde': 'FINASTERID', 'atc_kodu': 'G04CB01',
            'doktor_uzmanligi': 'Üroloji',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (dutasterid + dahiliye reçete + üroloji raporu)", {
            'etkin_madde': 'DUTASTERID', 'atc_kodu': 'G04CB02',
            'doktor_uzmanligi': 'İç Hastalıkları',
            'rapor_doktor_brans': 'Üroloji', 'rapor_kodu': '123',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (DUODART kombo + üroloji reçete)", {
            'ilac_adi': 'DUODART', 'etkin_madde': 'DUTASTERID/TAMSULOSIN',
            'atc_kodu': 'G04CA52', 'doktor_uzmanligi': 'Üroloji',
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (dahiliye + rapor yok)", {
            'etkin_madde': 'FINASTERID', 'atc_kodu': 'G04CB01',
            'doktor_uzmanligi': 'İç Hastalıkları',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (kombine: finasterid + dutasterid)", {
            'etkin_madde': 'FINASTERID', 'atc_kodu': 'G04CB01',
            'doktor_uzmanligi': 'Üroloji',
            'diger_etken_maddeler': ['DUTASTERID'], 'diger_ilac_adlari': ['AVODART'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (kombine: finasterid + DUODART)", {
            'etkin_madde': 'FINASTERID', 'atc_kodu': 'G04CB01',
            'doktor_uzmanligi': 'Üroloji',
            'diger_etken_maddeler': ['DUTASTERID/TAMSULOSIN'],
            'diger_ilac_adlari': ['DUODART'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN (finasterid + tamsulosin MONO başka — kombi değil)", {
            'etkin_madde': 'FINASTERID', 'atc_kodu': 'G04CB01',
            'doktor_uzmanligi': 'Üroloji',
            'diger_etken_maddeler': ['TAMSULOSIN'], 'diger_ilac_adlari': ['FLOMAX'],
        }, KontrolSonucu.UYGUN),
        ("ŞARTLI (branş bilinmiyor + rapor yok)", {
            'etkin_madde': 'DUTASTERID', 'atc_kodu': 'G04CB02',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN (ticari AVODART, üroloji reçete)", {
            'ilac_adi': 'AVODART 0.5 MG', 'etkin_madde': 'DUTASTERID',
            'doktor_uzmanligi': 'Üroloji',
        }, KontrolSonucu.UYGUN),
        ("Kapsam dışı (saf tamsulosin)", {
            'etkin_madde': 'TAMSULOSIN', 'atc_kodu': 'G04CA02',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT Finasterid/Dutasterid (BPH 5-ARI) — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = finasterid_dutasterid_kontrol(ilac_sonuc)
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
