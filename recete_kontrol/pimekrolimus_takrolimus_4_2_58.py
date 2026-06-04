# -*- coding: utf-8 -*-
"""SUT 4.2.58 — Pimekrolimus ve takrolimus (topikal formları).

Resmî SUT lafzı (docs/sut/SUT_tam_metin.txt:8689-8692, Ek:RG-4/9/2019-30878):
    (1) Ayakta tedavilerde aynı reçetede 2 kutuya kadar tüm hekimlerce, 2 kutu
        üzeri kullanım gereken hallerde dermatoloji uzman hekimlerince reçete
        edilmesi halinde bedelleri Kurumca karşılanır. Dermatoloji uzman
        hekimlerince düzenlenen 1 yıl süreli rapora istinaden aynı reçetede 10
        kutuya kadar tüm hekimlerce, 10 kutu üzeri kullanım gereken hallerde
        dermatoloji uzman hekimlerince reçete edilmesi halinde bedelleri
        Kurumca karşılanır.

Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI. Kutu adedi + dermatoloji raporu +
reçete branşı kademeli kuralı. Yalnız TOPİKAL form (sistemik takrolimus
PROGRAF/L04AD02 — transplant — HARİÇ).

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  limit = 10  (dermatoloji uzmanınca düzenlenmiş 1 yıl rapor varsa)
        =  2  (rapor yok / dermatoloji dışı rapor)

  UYGUN ⇔ (kutu ≤ limit)                                  ← tüm hekimler
          ∨ (kutu > limit ∧ reçete eden dermatoloji uzmanı)

Kutu okunamaz / reçete branşı belirsiz (kutu>limit iken) → KE+şartlı.

Ana entrypoint: ``pimtak_kontrol_4_2_58(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC D11AH01 (takrolimus topikal) / D11AH02 (pimekrolimus)
# ═══════════════════════════════════════════════════════════════════════
ATC_TOPIKAL = ('D11AH01', 'D11AH02')  # takrolimus topikal / pimekrolimus
PIMEKROLIMUS_KW: Set[str] = {'PIMEKROLIMUS', 'PIMECROLIMUS', 'ELIDEL'}
TAKROLIMUS_TOPIKAL_TICARI: Set[str] = {'PROTOPIC', 'TAKROL', 'TACNI TOPIK'}
TOPIKAL_FORM = ('topik', 'merhem', 'pomad', 'krem', 'cilt', 'deri')

DERMATOLOJI = ('dermatoloji', 'cildiye', 'deri hastalik')


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _iceriyor(metin_upper: str, kume) -> bool:
    return any(norm_tr_upper(k) in metin_upper for k in kume)


def _brans_l(brans: Optional[str]) -> str:
    return norm_tr_lower(brans or '')


def _dermatoloji_mi(brans: Optional[str]) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in DERMATOLOJI)


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


def pimtak_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """Topikal pimekrolimus/takrolimus mu? Sistemik takrolimus (L04AD02) HARİÇ."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if any(atc.startswith(p) for p in ATC_TOPIKAL):
        return True
    if atc.startswith('L04AD'):  # sistemik takrolimus — kapsam dışı
        return False
    m = _arama_metni(ilac_sonuc)
    if _iceriyor(m, PIMEKROLIMUS_KW):
        return True
    if _iceriyor(m, TAKROLIMUS_TOPIKAL_TICARI):
        return True
    # Etken takrolimus + topikal form ibaresi (sistemikten ayır)
    if 'TAKROLIMUS' in m or 'TACROLIMUS' in m:
        if any(norm_tr_upper(f) in m for f in TOPIKAL_FORM):
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════
# RAPOR DURUMU + LİMİT
# ═══════════════════════════════════════════════════════════════════════

def _dermatoloji_raporu_var(ilac_sonuc: Dict) -> bool:
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    return _dermatoloji_mi(rb) and bool(rapor_kodu or rapor_takip or rb)


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_KUTU = '(1) Kutu adedi / yetki kuralı'
GRUP_RAPOR_BILGI = '(1) Dermatoloji 1 yıl raporu (bilgi)'


def atom_rapor_bilgi(ilac_sonuc: Dict, derma_rapor: bool, limit: int) -> SartSonuc:
    """(bilgi) Dermatoloji 1 yıl raporu var mı → limit 10/2."""
    if derma_rapor:
        return SartSonuc(ad='Dermatoloji 1 yıl raporu', durum=SartDurumu.VAR,
                         neden=f'Dermatoloji raporu var → reçete limiti {limit} kutu '
                               f'(1 yıl süre tarih alanından manuel doğrula)',
                         kaynak='rapor_brans', grup=GRUP_RAPOR_BILGI)
    return SartSonuc(ad='Dermatoloji 1 yıl raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Dermatoloji raporu yok/doğrulanamadı → reçete limiti {limit} kutu',
                     kaynak='rapor_brans', grup=GRUP_RAPOR_BILGI, sartli_atom=True)


def atom_kutu_yetki(ilac_sonuc: Dict, derma_rapor: bool, limit: int) -> SartSonuc:
    """Ana gate: kutu ≤ limit → tüm hekimler; kutu > limit → dermatoloji reçete."""
    adet = _adet_oku(ilac_sonuc)
    brans = (ilac_sonuc.get('recete_hekim_uzmanligi')
             or ilac_sonuc.get('doktor_uzmanligi')
             or ilac_sonuc.get('brans') or '')
    rapor_etiket = 'raporlu (≤10)' if derma_rapor else 'raporsuz (≤2)'
    if adet is None:
        return SartSonuc(ad=f'Kutu adedi / yetki ({rapor_etiket})',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete kutu adedi okunamadı — manuel doğrula',
                         kaynak='doz', grup=GRUP_KUTU, sartli_atom=True)
    if adet <= limit:
        return SartSonuc(ad=f'Kutu {adet:g} ≤ {limit} ({rapor_etiket})',
                         durum=SartDurumu.VAR,
                         neden=f'Kutu adedi {adet:g} ≤ {limit} — tüm hekimler reçete edebilir',
                         kaynak='doz', grup=GRUP_KUTU)
    # kutu > limit → reçete eden dermatoloji olmalı
    if _dermatoloji_mi(brans):
        return SartSonuc(ad=f'Kutu {adet:g} > {limit} + dermatoloji reçete',
                         durum=SartDurumu.VAR,
                         neden=f'Kutu adedi {adet:g} > {limit} ama reçete eden dermatoloji '
                               f'uzmanı — uygun', kaynak='doz+hekim_brans', grup=GRUP_KUTU)
    if not _brans_l(brans):
        return SartSonuc(ad=f'Kutu {adet:g} > {limit} — reçete branşı?',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=f'Kutu {adet:g} > {limit}; {limit} üzeri için dermatoloji '
                               f'reçetesi gerekir ama reçete branşı bilinmiyor — manuel',
                         kaynak='doz+hekim_brans', grup=GRUP_KUTU, sartli_atom=True)
    return SartSonuc(ad=f'Kutu {adet:g} > {limit} — reçete dermatoloji değil',
                     durum=SartDurumu.YOK,
                     neden=f'Kutu adedi {adet:g} > {limit}; {limit} üzeri yalnız dermatoloji '
                           f'uzmanınca reçete edilebilir (reçete: {brans})',
                     kaynak='doz+hekim_brans', grup=GRUP_KUTU)


def _pimtak_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    derma_rapor = _dermatoloji_raporu_var(ilac_sonuc)
    limit = 10 if derma_rapor else 2
    return [
        atom_kutu_yetki(ilac_sonuc, derma_rapor, limit),
        atom_rapor_bilgi(ilac_sonuc, derma_rapor, limit),  # bilgi
    ]


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


def _mesaj_uret(sonuc: KontrolSonucu, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    parcalar = ['SUT 4.2.58 Pimekrolimus/Takrolimus (topikal)']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — kutu adedi/yetki kuralı sağlandı')
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

def pimtak_kontrol_4_2_58(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.58 — Pimekrolimus/takrolimus (topikal) kontrolü."""
    if not pimtak_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.58 kapsamı dışı — topikal pimekrolimus/takrolimus değil',
            sut_kurali='SUT 4.2.58')

    sartlar = _pimtak_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'PIMTAK',
        'sut_maddesi': '4.2.58',
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
        sut_kurali='SUT 4.2.58 — Pimekrolimus/takrolimus topikal (kutu/yetki)',
        aranan_ibare='kutu ≤2 (raporsuz) / ≤10 (dermatoloji raporu) tüm hekim; üzeri dermatoloji',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("UYGUN (raporsuz, 2 kutu, aile hekimi)", {
            'etkin_madde': 'PIMEKROLIMUS', 'atc_kodu': 'D11AH02',
            'doktor_uzmanligi': 'Aile Hekimliği', 'kutu_sayisi': '2',
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (raporsuz, 3 kutu, aile hekimi)", {
            'etkin_madde': 'PIMEKROLIMUS', 'atc_kodu': 'D11AH02',
            'doktor_uzmanligi': 'Aile Hekimliği', 'kutu_sayisi': '3',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN (raporsuz, 3 kutu, dermatoloji)", {
            'etkin_madde': 'PIMEKROLIMUS', 'atc_kodu': 'D11AH02',
            'doktor_uzmanligi': 'Dermatoloji', 'kutu_sayisi': '3',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (dermatoloji raporu, 10 kutu, aile hekimi)", {
            'ilac_adi': 'PROTOPIC MERHEM', 'etkin_madde': 'TAKROLIMUS',
            'doktor_uzmanligi': 'Aile Hekimliği', 'kutu_sayisi': '10',
            'rapor_doktor_brans': 'Dermatoloji', 'rapor_kodu': '1',
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (dermatoloji raporu, 12 kutu, aile hekimi)", {
            'ilac_adi': 'PROTOPIC', 'etkin_madde': 'TAKROLIMUS',
            'doktor_uzmanligi': 'Aile Hekimliği', 'kutu_sayisi': '12',
            'rapor_doktor_brans': 'Dermatoloji', 'rapor_kodu': '1',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN (dermatoloji raporu, 12 kutu, dermatoloji reçete)", {
            'ilac_adi': 'PROTOPIC', 'etkin_madde': 'TAKROLIMUS',
            'doktor_uzmanligi': 'Dermatoloji', 'kutu_sayisi': '12',
            'rapor_doktor_brans': 'Dermatoloji', 'rapor_kodu': '1',
        }, KontrolSonucu.UYGUN),
        ("ŞARTLI (raporsuz, 5 kutu, branş bilinmiyor)", {
            'etkin_madde': 'PIMEKROLIMUS', 'atc_kodu': 'D11AH02', 'kutu_sayisi': '5',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("ŞARTLI (kutu okunamadı)", {
            'etkin_madde': 'PIMEKROLIMUS', 'atc_kodu': 'D11AH02',
            'doktor_uzmanligi': 'Aile Hekimliği',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN (dermatoloji-dışı rapor → limit 2, 2 kutu)", {
            'etkin_madde': 'PIMEKROLIMUS', 'atc_kodu': 'D11AH02',
            'doktor_uzmanligi': 'Aile Hekimliği', 'kutu_sayisi': '2',
            'rapor_doktor_brans': 'İç Hastalıkları', 'rapor_kodu': '1',
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (dermatoloji-dışı rapor → limit 2, 5 kutu, aile hekimi)", {
            'etkin_madde': 'PIMEKROLIMUS', 'atc_kodu': 'D11AH02',
            'doktor_uzmanligi': 'Aile Hekimliği', 'kutu_sayisi': '5',
            'rapor_doktor_brans': 'İç Hastalıkları', 'rapor_kodu': '1',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Kapsam dışı (sistemik takrolimus PROGRAF)", {
            'ilac_adi': 'PROGRAF 1 MG KAPSUL', 'etkin_madde': 'TAKROLIMUS',
            'atc_kodu': 'L04AD02', 'kutu_sayisi': '1',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.58 Pimekrolimus/Takrolimus topikal — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = pimtak_kontrol_4_2_58(ilac_sonuc)
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
