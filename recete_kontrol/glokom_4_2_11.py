# -*- coding: utf-8 -*-
"""SUT 4.2.11 — Glokom ilaçları.

Resmî SUT lafzı (docs/sut/SUT_tam_metin.txt:5360-5362, mevzuat.gov.tr
MevzuatNo=17229):
    "(1) Glokom ilaçları ile tedaviye göz sağlığı ve hastalıkları uzman
     hekimi tarafından başlanacaktır. Göz sağlığı ve hastalıkları uzman
     hekimi tarafından düzenlenen uzman hekim raporuna dayanılarak diğer
     hekimlerce de reçete edilebilir."

Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ATOMİK DEVRE
ŞEMASI PRENSİPLERİ. Tek madde, iki paralel yetki yolu (üst-VEYA). Yaş /
sağlık kurulu / endikasyon / doz şartı YOK.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  GLOKOM_UYGUN ⇔ ( A: reçete eden göz uzmanı )
                 ∨ ( B: göz uzmanınca düzenlenmiş uzman hekim raporu VAR )

  A → tedaviye göz uzmanı başlar / sürdürür (her durumda yeterli)
  B → göz uzmanı raporu varsa diğer hekimler de reçete edebilir

İki atom tek VEYA grubunda (≥1 yeterli). Her ikisi de YOK → UYGUN DEĞİL
(göz uzmanı değil + göz uzmanı raporu yok). Branş okunamazsa KE+şartlı.

Ana entrypoint: ``glokom_kontrol_4_2_11(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC S01E* (antiglokom) + etken
# ═══════════════════════════════════════════════════════════════════════
ATC_GLOKOM_PREFIX = 'S01E'  # S01EA/EB/EC/ED/EE/EX — antiglokom preparatları
GLOKOM_ETKEN: Set[str] = {
    'TIMOLOL', 'TIMOLOL', 'BETAKSOLOL', 'BETAXOLOL', 'KARTEOLOL', 'CARTEOLOL',
    'LATANOPROST', 'TRAVOPROST', 'BIMATOPROST', 'TAFLUPROST', 'LATANOPROSTEN',
    'DORZOLAMID', 'DORZOLAMIDE', 'BRINZOLAMID', 'BRINZOLAMIDE',
    'BRIMONIDIN', 'BRIMONIDINE', 'APRAKLONIDIN', 'APRACLONIDINE',
    'PILOKARPIN', 'PILOCARPINE', 'NETARSUDIL',
}
GLOKOM_TICARI: Set[str] = {
    'XALATAN', 'TRAVATAN', 'LUMIGAN', 'TAPTIQOM', 'SAFLUTAN', 'GANFORT',
    'COSOPT', 'AZARGA', 'AZOPT', 'TRUSOPT', 'ALPHAGAN', 'COMBIGAN',
    'DUOTRAV', 'GLAUCOTENS', 'TIMOSAN', 'XALACOM', 'SIMBRINZA', 'IZBA',
}

# Göz sağlığı ve hastalıkları branş anahtarları (norm_tr_lower substring)
GOZ_BRANS = ('goz', 'oftalmoloji')  # 'göz' → norm_tr_lower → 'goz'


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


def _goz_uzmani_mi(brans: Optional[str]) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in GOZ_BRANS)


def glokom_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """SUT 4.2.11 glokom ilacı mı? ATC S01E* veya etken/ticari."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_GLOKOM_PREFIX):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, GLOKOM_ETKEN) or _iceriyor(m, GLOKOM_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR — tek VEYA grubu (yetki)
# ═══════════════════════════════════════════════════════════════════════

GRUP_YETKI = '(1) Yetki — göz uzmanı reçete VEYA göz uzmanı raporu'


def atom_recete_goz_uzmani(ilac_sonuc: Dict) -> SartSonuc:
    """A: reçeteyi yazan hekim göz sağlığı ve hastalıkları uzmanı mı?"""
    brans = (ilac_sonuc.get('recete_hekim_uzmanligi')
             or ilac_sonuc.get('doktor_uzmanligi')
             or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden göz uzmanı', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_YETKI, veya_grubu=True,
                         sartli_atom=True)
    if _goz_uzmani_mi(brans):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Göz sağlığı ve hastalıkları uzmanı — tedaviyi başlatabilir',
                         kaynak='hekim_brans', grup=GRUP_YETKI, veya_grubu=True)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Göz uzmanı değil — göz uzmanı raporu gerekir',
                     kaynak='hekim_brans', grup=GRUP_YETKI, veya_grubu=True)


def atom_rapor_goz_uzmani(ilac_sonuc: Dict) -> SartSonuc:
    """B: göz uzmanınca düzenlenmiş uzman hekim raporu VAR mı?"""
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    if _goz_uzmani_mi(rb):
        return SartSonuc(ad='Göz uzmanı uzman hekim raporu', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb} — diğer hekimler reçete edebilir',
                         kaynak='rapor_brans', grup=GRUP_YETKI, veya_grubu=True)
    if not rapor_var:
        return SartSonuc(ad='Göz uzmanı uzman hekim raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı göz uzmanı raporu yok',
                         kaynak='rapor', grup=GRUP_YETKI, veya_grubu=True)
    if rb:
        return SartSonuc(ad='Göz uzmanı uzman hekim raporu', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — göz uzmanı değil',
                         kaynak='rapor_brans', grup=GRUP_YETKI, veya_grubu=True)
    return SartSonuc(ad='Göz uzmanı uzman hekim raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş göz uzmanı olarak '
                           'doğrulanamadı — manuel', kaynak='rapor_brans',
                     grup=GRUP_YETKI, veya_grubu=True, sartli_atom=True)


def _glokom_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_recete_goz_uzmani(ilac_sonuc),
        atom_rapor_goz_uzmani(ilac_sonuc),
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (grup bazlı — eritropoietin/alprostadil kalıbı)
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
    parcalar = ['SUT 4.2.11 Glokom ilaçları']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — göz uzmanı reçetesi veya göz uzmanı raporu var')
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f'ŞARTLI UYGUN — yetki branşı doğrulanamadı '
                        f'({len(ke)} şart manuel)')
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append('UYGUN DEĞİL — reçete eden göz uzmanı değil ve '
                        'göz uzmanı raporu yok')
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f'ŞÜPHELİ — {len(ke)} şart kontrol edilemedi')
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def glokom_kontrol_4_2_11(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.11 — Glokom ilaçları kontrolü."""
    if not glokom_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.11 kapsamı dışı — glokom ilacı (S01E*) değil',
            sut_kurali='SUT 4.2.11')

    sartlar = _glokom_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'GLOKOM',
        'sut_maddesi': '4.2.11',
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
        sut_kurali='SUT 4.2.11 — Glokom ilaçları',
        aranan_ibare='reçete göz uzmanı VEYA göz uzmanınca düzenlenmiş uzman hekim raporu',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("UYGUN (reçete göz uzmanı)", {
            'etkin_madde': 'LATANOPROST', 'atc_kodu': 'S01EE01',
            'doktor_uzmanligi': 'Göz Sağlığı ve Hastalıkları',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (reçete dahiliye + rapor göz uzmanı)", {
            'etkin_madde': 'TIMOLOL', 'atc_kodu': 'S01ED01',
            'doktor_uzmanligi': 'İç Hastalıkları',
            'rapor_doktor_brans': 'Göz Hastalıkları', 'rapor_kodu': '123',
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (dahiliye + rapor yok)", {
            'etkin_madde': 'DORZOLAMID', 'atc_kodu': 'S01EC03',
            'doktor_uzmanligi': 'İç Hastalıkları',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (aile hekimi + kardiyoloji raporu)", {
            'etkin_madde': 'BRIMONIDIN', 'atc_kodu': 'S01EA05',
            'doktor_uzmanligi': 'Aile Hekimliği',
            'rapor_doktor_brans': 'Kardiyoloji', 'rapor_kodu': '5',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ŞARTLI (reçete branş bilinmiyor + rapor yok)", {
            'etkin_madde': 'TRAVOPROST', 'atc_kodu': 'S01EE04',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN (oftalmoloji branş etiketi)", {
            'etkin_madde': 'BIMATOPROST', 'atc_kodu': 'S01EE03',
            'doktor_uzmanligi': 'Oftalmoloji',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (ticari COSOPT, göz uzmanı raporu)", {
            'ilac_adi': 'COSOPT GÖZ DAMLASI', 'etkin_madde': 'DORZOLAMID/TIMOLOL',
            'atc_kodu': 'S01ED51', 'doktor_uzmanligi': 'Aile Hekimliği',
            'rapor_doktor_brans': 'Göz Sağlığı ve Hastalıkları', 'rapor_takip_no': '999',
        }, KontrolSonucu.UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (suni gözyaşı S01XA)", {
            'etkin_madde': 'HIPROMELLOZ', 'atc_kodu': 'S01XA20',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.11 Glokom — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = glokom_kontrol_4_2_11(ilac_sonuc)
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
