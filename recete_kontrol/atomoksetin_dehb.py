# -*- coding: utf-8 -*-
"""SUT — Atomoksetin (DEHB) kullanım ilkesi.

Resmî lafız (kullanıcı verdi 2026-06-04; ana SUT tebliğ metninde bulunmuyor
— EK/ek ibare olabilir, kullanıcı onayıyla işlendi):
    "6-25 yaş hastalarda psikiyatri uzman hekiminin yer aldığı sağlık kurulu
     raporuna dayanılarak psikiyatri uzman hekimi veya çocuk sağlığı ve
     hastalıkları uzman hekimlerince reçete edilir. 16-18 ergen yaş grubunda
     ayrıca erişkin psikiyatri uzmanlarınca da aynı koşullarda rapor ve reçete
     düzenlenebilir."

Kapsam (kullanıcı kararı 2026-06-04): SADECE atomoksetin (N06BA09; Strattera).
Metilfenidat dahil DEĞİL.

Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ATOMİK DEVRE
ŞEMASI PRENSİPLERİ.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ A1(6 ≤ yaş ≤ 25)
          ∧ C1(sağlık kurulu raporu)
          ∧ C2(SK heyetinde psikiyatri uzmanı yer alıyor)
          ∧ D1(reçete eden: psikiyatri ∨ çocuk sağlığı ve hastalıkları uzmanı)

16-18 ergen yaş grubu: erişkin psikiyatri uzmanı da kabul (psikiyatri/ruh
sağlığı keyword'ü hem çocuk psikiyatrisini hem erişkin psikiyatriyi kapsar).

SK raporu + heyet ÇEŞİTLİ akışında rapor_turu+heyet zenginleştirmesiyle
doğrulanır (aprepitant kalıbı). Doğrulanamazsa KE+şartlı → ŞARTLI UYGUN.

Ana entrypoint: ``atomoksetin_kontrol_dehb(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — N06BA09 atomoksetin (yalnız)
# ═══════════════════════════════════════════════════════════════════════
ATC_ATOMOKSETIN = 'N06BA09'
ATOMOKSETIN_ETKEN: Set[str] = {'ATOMOKSETIN', 'ATOMOXETINE', 'ATOMOKSETIN HIDROKLORUR'}
ATOMOKSETIN_TICARI: Set[str] = {
    'STRATTERA', 'ATOMINEX', 'ATTENTROL', 'ATOMERA', 'ATOMOX', 'TOMOXETIN',
}

# Branş anahtarları (norm_tr_lower substring)
PSIKIYATRI_KW = ('psikiyatri', 'ruh sagligi')  # erişkin + çocuk-ergen ruh sağlığı
COCUK_KW = ('cocuk sagligi', 'pediatri', 'cocuk hastalik')  # çocuk sağlığı ve hast.


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


def _brans_listede(brans: Optional[str], anahtarlar) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in anahtarlar)


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


def _heyet_branslari(ilac_sonuc: Dict) -> List[str]:
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not isinstance(heyet, (list, tuple)):
        return []
    return [str(h.get('brans') or '') for h in heyet
            if isinstance(h, dict) and (h.get('ad') or h.get('brans'))]


def atomoksetin_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """Atomoksetin (N06BA09) mı?"""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_ATOMOKSETIN):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, ATOMOKSETIN_ETKEN) or _iceriyor(m, ATOMOKSETIN_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_YAS = '(1) Yaş 6-25'
GRUP_RAPOR = '(2) Psikiyatri uzmanlı sağlık kurulu raporu'
GRUP_RECETE = '(3) Reçete: psikiyatri veya çocuk sağlığı uzmanı'


def atom_yas_araligi(ilac_sonuc: Dict) -> SartSonuc:
    """A1: 6 ≤ yaş ≤ 25."""
    yas = _yas_oku(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad='Yaş 6-25', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı DB\'de yok — manuel doğrula',
                         kaynak='hasta_yas', grup=GRUP_YAS, sartli_atom=True)
    if 6 <= yas <= 25:
        return SartSonuc(ad=f'Yaş {yas} (6-25)', durum=SartDurumu.VAR,
                         neden='6-25 yaş aralığında', kaynak='hasta_yas', grup=GRUP_YAS)
    return SartSonuc(ad=f'Yaş {yas} (6-25)', durum=SartDurumu.YOK,
                     neden=f'{yas} yaş — 6-25 aralığı dışında',
                     kaynak='hasta_yas', grup=GRUP_YAS)


def atom_saglik_kurulu(ilac_sonuc: Dict) -> SartSonuc:
    """C1: sağlık kurulu raporu (RaporTuruAdi + heyet — kanser_gcsf kalıbı)."""
    rapor_turu = norm_tr_lower(ilac_sonuc.get('rapor_turu') or '')
    heyet_n = len(_heyet_branslari(ilac_sonuc))
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()

    kurul_isaret = ('kurul' in rapor_turu) or (heyet_n >= 2)
    uzman_tek = ('uzman hekim' in rapor_turu) and 'kurul' not in rapor_turu
    rapor_var = bool(rapor_kodu or rapor_takip or rapor_turu or heyet_n)

    if kurul_isaret:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
                         neden=f"Sağlık kurulu raporu ({rapor_turu or 'heyet '+str(heyet_n)+' uzman'})",
                         kaynak='rapor_turu+heyet', grup=GRUP_RAPOR)
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


def atom_heyet_psikiyatri(ilac_sonuc: Dict) -> SartSonuc:
    """C2: SK heyetinde psikiyatri uzmanı (çocuk-ergen veya erişkin ruh sağlığı)."""
    branslar = _heyet_branslari(ilac_sonuc)
    if not branslar:
        return SartSonuc(ad='Heyette psikiyatri uzmanı', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor heyeti bilgisi yok — manuel doğrula',
                         kaynak='heyet', grup=GRUP_RAPOR, sartli_atom=True)
    psik = [b for b in branslar if _brans_listede(b, PSIKIYATRI_KW)]
    if psik:
        return SartSonuc(ad='Heyette psikiyatri uzmanı', durum=SartDurumu.VAR,
                         neden=f'Heyette psikiyatri/ruh sağlığı: {", ".join(psik)}',
                         kaynak='heyet', grup=GRUP_RAPOR)
    return SartSonuc(ad='Heyette psikiyatri uzmanı', durum=SartDurumu.YOK,
                     neden=f'Heyette psikiyatri uzmanı yok (heyet: {", ".join(branslar)})',
                     kaynak='heyet', grup=GRUP_RAPOR)


def atom_recete_brans(ilac_sonuc: Dict) -> SartSonuc:
    """D1: reçete eden psikiyatri (16-18'de erişkin dahil) veya çocuk sağlığı uzmanı."""
    brans = (ilac_sonuc.get('recete_hekim_uzmanligi')
             or ilac_sonuc.get('doktor_uzmanligi')
             or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden hekim branşı', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_RECETE, sartli_atom=True)
    if _brans_listede(brans, PSIKIYATRI_KW) or _brans_listede(brans, COCUK_KW):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Psikiyatri/ruh sağlığı veya çocuk sağlığı uzmanı — yetkili',
                         kaynak='hekim_brans', grup=GRUP_RECETE)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Yalnız psikiyatri veya çocuk sağlığı ve hastalıkları uzmanı '
                           'reçete edebilir', kaynak='hekim_brans', grup=GRUP_RECETE)


def _atomoksetin_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_yas_araligi(ilac_sonuc),
        atom_saglik_kurulu(ilac_sonuc),
        atom_heyet_psikiyatri(ilac_sonuc),
        atom_recete_brans(ilac_sonuc),
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (grup bazlı — ortak kalıp)
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
    parcalar = ['SUT Atomoksetin (DEHB)']
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

def atomoksetin_kontrol_dehb(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT — Atomoksetin (DEHB) kontrolü."""
    if not atomoksetin_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='Kapsam dışı — atomoksetin (N06BA09) değil',
            sut_kurali='SUT — Atomoksetin (DEHB)')

    sartlar = _atomoksetin_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'ATOMOKSETIN',
        'sut_maddesi': 'Atomoksetin (DEHB)',
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
        sut_kurali='SUT — Atomoksetin (DEHB) 6-25 yaş psikiyatri SK raporu',
        aranan_ibare='6-25 yaş + psikiyatri uzmanlı SK raporu + psikiyatri/çocuk reçete',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    SK_PSIK = [{'brans': 'Çocuk ve Ergen Ruh Sağlığı ve Hastalıkları'},
               {'brans': 'Çocuk Sağlığı ve Hastalıkları'}]
    SK_ERISKIN = [{'brans': 'Ruh Sağlığı ve Hastalıkları'},
                  {'brans': 'Nöroloji'}]
    SK_NO_PSIK = [{'brans': 'Çocuk Sağlığı ve Hastalıkları'},
                  {'brans': 'Nöroloji'}]
    return [
        ("UYGUN (10 yaş, çocuk psik heyet, çocuk psik reçete)", {
            'etkin_madde': 'ATOMOKSETIN', 'atc_kodu': 'N06BA09',
            'hasta_yasi': 10, 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_PSIK, 'rapor_kodu': '1',
            'doktor_uzmanligi': 'Çocuk ve Ergen Ruh Sağlığı ve Hastalıkları',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (17 yaş ergen, erişkin psik heyet+reçete)", {
            'etkin_madde': 'ATOMOKSETIN', 'atc_kodu': 'N06BA09',
            'hasta_yasi': 17, 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ERISKIN, 'rapor_kodu': '1',
            'doktor_uzmanligi': 'Ruh Sağlığı ve Hastalıkları',
        }, KontrolSonucu.UYGUN),
        ("UYGUN (8 yaş, çocuk sağlığı uzmanı reçete)", {
            'etkin_madde': 'ATOMOKSETIN', 'atc_kodu': 'N06BA09',
            'hasta_yasi': 8, 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_PSIK, 'rapor_kodu': '1',
            'doktor_uzmanligi': 'Çocuk Sağlığı ve Hastalıkları',
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (28 yaş — aralık dışı)", {
            'etkin_madde': 'ATOMOKSETIN', 'atc_kodu': 'N06BA09',
            'hasta_yasi': 28, 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ERISKIN, 'rapor_kodu': '1',
            'doktor_uzmanligi': 'Ruh Sağlığı ve Hastalıkları',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (5 yaş — aralık altı)", {
            'etkin_madde': 'STRATTERA', 'atc_kodu': 'N06BA09',
            'hasta_yasi': 5, 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_PSIK, 'rapor_kodu': '1',
            'doktor_uzmanligi': 'Çocuk Sağlığı ve Hastalıkları',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (heyette psikiyatri yok)", {
            'etkin_madde': 'ATOMOKSETIN', 'atc_kodu': 'N06BA09',
            'hasta_yasi': 12, 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_NO_PSIK, 'rapor_kodu': '1',
            'doktor_uzmanligi': 'Çocuk Sağlığı ve Hastalıkları',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (reçete eden kardiyoloji)", {
            'etkin_madde': 'ATOMOKSETIN', 'atc_kodu': 'N06BA09',
            'hasta_yasi': 14, 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_PSIK, 'rapor_kodu': '1',
            'doktor_uzmanligi': 'Kardiyoloji',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (uzman hekim raporu — SK değil)", {
            'etkin_madde': 'ATOMOKSETIN', 'atc_kodu': 'N06BA09',
            'hasta_yasi': 14, 'rapor_turu': 'Uzman Hekim Raporu',
            'heyet_doktorlari': [], 'rapor_kodu': '1',
            'doktor_uzmanligi': 'Ruh Sağlığı ve Hastalıkları',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ŞARTLI (yaş yok, diğer her şey VAR)", {
            'etkin_madde': 'ATOMOKSETIN', 'atc_kodu': 'N06BA09',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'heyet_doktorlari': SK_PSIK,
            'rapor_kodu': '1', 'doktor_uzmanligi': 'Ruh Sağlığı ve Hastalıkları',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("ŞARTLI (heyet bilgisi yok ama SK türü var)", {
            'etkin_madde': 'ATOMOKSETIN', 'atc_kodu': 'N06BA09',
            'hasta_yasi': 12, 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': [], 'rapor_kodu': '1',
            'doktor_uzmanligi': 'Ruh Sağlığı ve Hastalıkları',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Kapsam dışı (metilfenidat — atomoksetin değil)", {
            'etkin_madde': 'METILFENIDAT', 'atc_kodu': 'N06BA04',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT Atomoksetin (DEHB) — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = atomoksetin_kontrol_dehb(ilac_sonuc)
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
