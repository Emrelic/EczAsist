# -*- coding: utf-8 -*-
"""SUT EK-4/F m.55 — Ginkgo biloba glikozidleri (demans).

Resmî lafız (kullanıcı verdi 2026-06-04; ana SUT tebliğ `SUT_tam_metin.txt`'te
bulunmuyor — ek liste m.55):
    "Gingko glikozidleri (65 yaş ve üzeri hastalarda yalnızca alzheimer tipi
     demans, vasküler demans ve miks formlarındaki demans sendromları
     endikasyonlarında, nöroloji veya geriatri uzman hekimlerince düzenlenen
     bir yıl süreli uzman hekim raporuna dayanılarak tüm uzman hekimlerce)"

Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI PRENSİPLERİ. Tek yolak; rapor ZORUNLU
(raporsuz yol yok); yaş ≥65 + demans endikasyonu şart.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ A1(yaş ≥ 65)
          ∧ B1(endikasyon: alzheimer tipi ∨ vasküler ∨ miks demans)
          ∧ C1(nöroloji VEYA geriatri uzmanınca düzenlenmiş uzman hekim raporu)
          ∧ D1(reçete eden uzman hekim — tüm uzmanlar; pratisyen/aile değil)
          [bilgi: rapor 1 yıl süreli]

Ana entrypoint: ``ginkgo_kontrol_ek4f_55(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC N06DX02 ginkgo biloba
# ═══════════════════════════════════════════════════════════════════════
ATC_GINKGO = 'N06DX02'
GINKGO_ETKEN: Set[str] = {'GINKGO', 'GINGKO', 'GINKGO BILOBA', 'GINKO BILOBA',
                          'EGB 761', 'GINKGO GLIKOZID'}
GINKGO_TICARI: Set[str] = {
    'TEBOKAN', 'TANAKAN', 'BILOBIL', 'GINGIUM', 'GINKOR', 'MEMOPLANT',
    'GINKGOBA', 'GINKOCER', 'BILOBA', 'GINKOSAN',
}

# Yetkili rapor branşları
RAPOR_BRANS = ('noroloji', 'geriatri')
# Reçete edemeyen (uzman olmayan) branşlar
NON_UZMAN_KW = ('pratisyen', 'aile hek', 'genel pratisyen', 'pratisyen tabip',
                'pratisyen hekim')

# Demans endikasyon ICD + metin
DEMANS_ICD = ('F00', 'F01', 'F02', 'F03', 'G30')
ALZHEIMER_METIN = ('alzheimer', 'alzhaymer')
VASKULER_METIN = ('vaskuler demans', 'vasküler demans')
MIKS_METIN = ('miks demans', 'mikst demans', 'miks form', 'mikst form',
              'karma demans')
DEMANS_METIN = ('demans', 'dementia', 'bunama')


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


def ginkgo_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_GINKGO):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, GINKGO_ETKEN) or _iceriyor(m, GINKGO_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

GRUP_YAS = '(1) Yaş ≥65'
GRUP_ENDIK = '(1) Demans endikasyonu (alzheimer/vasküler/miks)'
GRUP_RAPOR = '(2) Nöroloji/geriatri uzmanı raporu'
GRUP_SURE = '(2) Rapor 1 yıl süreli (bilgi)'
GRUP_RECETE = '(3) Reçete eden uzman hekim'


def atom_yas_65(ilac_sonuc: Dict) -> SartSonuc:
    yas = _yas_oku(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad='Yaş ≥65', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı DB\'de yok — manuel doğrula',
                         kaynak='hasta_yas', grup=GRUP_YAS, sartli_atom=True)
    if yas >= 65:
        return SartSonuc(ad=f'Yaş {yas} (≥65)', durum=SartDurumu.VAR,
                         neden='65 yaş ve üzeri', kaynak='hasta_yas', grup=GRUP_YAS)
    return SartSonuc(ad=f'Yaş {yas} (≥65)', durum=SartDurumu.YOK,
                     neden=f'{yas} yaş — 65 altı, kapsam dışı',
                     kaynak='hasta_yas', grup=GRUP_YAS)


def atom_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    alz = any(k in metin for k in ALZHEIMER_METIN) or 'G30' in icd or 'F00' in icd
    vask = any(k in metin for k in VASKULER_METIN) or 'F01' in icd
    miks = any(k in metin for k in MIKS_METIN)
    demans_genel = any(k in metin for k in DEMANS_METIN) or any(
        k in icd for k in DEMANS_ICD)
    alt = [('Alzheimer tipi demans', 'var' if alz else 'kontrol_edilemedi'),
           ('Vasküler demans', 'var' if vask else 'kontrol_edilemedi'),
           ('Miks form demans', 'var' if miks else 'kontrol_edilemedi')]
    if alz or vask or miks:
        return SartSonuc(ad='Demans endikasyonu (alzheimer/vasküler/miks)',
                         durum=SartDurumu.VAR,
                         neden=('alzheimer' if alz else 'vasküler demans' if vask
                                else 'miks demans'),
                         kaynak='ICD+rapor', grup=GRUP_ENDIK, alt_liste=alt)
    if demans_genel:
        return SartSonuc(ad='Demans endikasyonu (alzheimer/vasküler/miks)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Demans var ama tipi (alzheimer/vasküler/miks) '
                               'belirtilmemiş — manuel doğrula',
                         kaynak='ICD+rapor', grup=GRUP_ENDIK, alt_liste=alt,
                         sartli_atom=True)
    return SartSonuc(ad='Demans endikasyonu (alzheimer/vasküler/miks)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Demans endikasyonu (ICD F00-F03/G30 veya metin) okunamadı — manuel',
                     kaynak='ICD+rapor', grup=GRUP_ENDIK, alt_liste=alt, sartli_atom=True)


def atom_rapor_brans(ilac_sonuc: Dict) -> SartSonuc:
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or '')
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or rb)
    if _brans_listede(rb, RAPOR_BRANS):
        return SartSonuc(ad='Nöroloji/geriatri uzmanı raporu', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb}', kaynak='rapor_brans', grup=GRUP_RAPOR)
    if not rapor_var:
        return SartSonuc(ad='Nöroloji/geriatri uzmanı raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor yok (rapor zorunlu)',
                         kaynak='rapor', grup=GRUP_RAPOR)
    if rb:
        return SartSonuc(ad='Nöroloji/geriatri uzmanı raporu', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — nöroloji/geriatri değil',
                         kaynak='rapor_brans', grup=GRUP_RAPOR)
    return SartSonuc(ad='Nöroloji/geriatri uzmanı raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama branş nöroloji/geriatri olarak '
                           'doğrulanamadı — manuel', kaynak='rapor_brans',
                     grup=GRUP_RAPOR, sartli_atom=True)


def atom_rapor_1yil(ilac_sonuc: Dict) -> SartSonuc:
    """(bilgi) Rapor 1 yıl süreli. Tarih parse zayıf → KE bilgi."""
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
        if 330 <= gun <= 400:
            return SartSonuc(ad='Rapor süresi 1 yıl', durum=SartDurumu.VAR,
                             neden=f'Rapor süresi {gun} gün — ~1 yıl',
                             kaynak='rapor_tarihleri', grup=GRUP_SURE)
        return SartSonuc(ad='Rapor süresi 1 yıl', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=f'Rapor süresi {gun} gün — 1 yıl değil, manuel doğrula',
                         kaynak='rapor_tarihleri', grup=GRUP_SURE, sartli_atom=True)
    return SartSonuc(ad='Rapor süresi 1 yıl', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor başlangıç/bitiş tarihi yok — manuel doğrula',
                     kaynak='rapor_tarihleri', grup=GRUP_SURE, sartli_atom=True)


def atom_recete_uzman(ilac_sonuc: Dict) -> SartSonuc:
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
                     neden='Uzman hekim — yetkili (rapora dayanılarak tüm uzman hekimler)',
                     kaynak='hekim_brans', grup=GRUP_RECETE)


def _ginkgo_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_yas_65(ilac_sonuc),
        atom_endikasyon(ilac_sonuc),
        atom_rapor_brans(ilac_sonuc),
        atom_recete_uzman(ilac_sonuc),
        atom_rapor_1yil(ilac_sonuc),  # bilgi
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
    parcalar = ['SUT EK-4/F m.55 Ginkgo glikozidleri (demans)']
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append('UYGUN — tüm şartlar sağlandı')
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

def ginkgo_kontrol_ek4f_55(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4/F m.55 — Ginkgo glikozidleri (demans) kontrolü."""
    if not ginkgo_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='EK-4/F m.55 kapsamı dışı — ginkgo biloba değil',
            sut_kurali='SUT EK-4/F m.55')

    sartlar = _ginkgo_sartlari(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'GINKGO',
        'sut_maddesi': 'EK-4/F m.55',
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
        sut_kurali='SUT EK-4/F m.55 — Ginkgo glikozidleri (demans)',
        aranan_ibare='yaş≥65 + alzheimer/vasküler/miks demans + nöro/geriatri raporu + '
                     'reçete uzman hekim',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("UYGUN (70 yaş, alzheimer, nöro rapor, dahiliye reçete)", {
            'etkin_madde': 'GINKGO BILOBA', 'atc_kodu': 'N06DX02',
            'hasta_yasi': 70, 'recete_teshisleri': ['G30.0'],
            'rapor_doktor_brans': 'Nöroloji', 'doktor_uzmanligi': 'İç Hastalıkları',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['alzheimer tipi demans'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN (68 yaş, vasküler demans, geriatri rapor+reçete)", {
            'etkin_madde': 'GINKGO', 'atc_kodu': 'N06DX02',
            'hasta_yasi': 68, 'recete_teshisleri': ['F01.9'],
            'rapor_doktor_brans': 'Geriatri', 'doktor_uzmanligi': 'Geriatri',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['vasküler demans'],
        }, KontrolSonucu.UYGUN),
        ("UYGUN DEĞİL (60 yaş — 65 altı)", {
            'etkin_madde': 'GINKGO BILOBA', 'atc_kodu': 'N06DX02',
            'hasta_yasi': 60, 'recete_teshisleri': ['G30.0'],
            'rapor_doktor_brans': 'Nöroloji', 'doktor_uzmanligi': 'Nöroloji',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['alzheimer'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (rapor branş kardiyoloji)", {
            'etkin_madde': 'GINKGO', 'atc_kodu': 'N06DX02',
            'hasta_yasi': 72, 'recete_teshisleri': ['G30.0'],
            'rapor_doktor_brans': 'Kardiyoloji', 'doktor_uzmanligi': 'Nöroloji',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['alzheimer'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (rapor yok)", {
            'etkin_madde': 'GINKGO', 'atc_kodu': 'N06DX02',
            'hasta_yasi': 75, 'recete_teshisleri': ['G30.0'],
            'doktor_uzmanligi': 'Nöroloji', 'rapor_aciklamalari': ['alzheimer'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (reçete eden aile hekimi)", {
            'etkin_madde': 'GINKGO', 'atc_kodu': 'N06DX02',
            'hasta_yasi': 75, 'recete_teshisleri': ['G30.0'],
            'rapor_doktor_brans': 'Nöroloji', 'doktor_uzmanligi': 'Aile Hekimliği',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['alzheimer'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ŞARTLI (yaş yok, diğer her şey VAR)", {
            'etkin_madde': 'GINKGO', 'atc_kodu': 'N06DX02',
            'recete_teshisleri': ['G30.0'], 'rapor_doktor_brans': 'Nöroloji',
            'doktor_uzmanligi': 'Nöroloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['alzheimer'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("ŞARTLI (demans var ama tip belirsiz)", {
            'etkin_madde': 'GINKGO', 'atc_kodu': 'N06DX02',
            'hasta_yasi': 70, 'recete_teshisleri': ['F03'],
            'rapor_doktor_brans': 'Geriatri', 'doktor_uzmanligi': 'Geriatri',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['demans sendromu'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN (ticari TEBOKAN, miks demans)", {
            'ilac_adi': 'TEBOKAN 80 MG', 'etkin_madde': 'GINKGO BILOBA',
            'hasta_yasi': 78, 'recete_teshisleri': [],
            'rapor_doktor_brans': 'Nöroloji', 'doktor_uzmanligi': 'Psikiyatri',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['miks demans formu'],
        }, KontrolSonucu.UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT EK-4/F m.55 Ginkgo glikozidleri — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = ginkgo_kontrol_ek4f_55(ilac_sonuc)
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
