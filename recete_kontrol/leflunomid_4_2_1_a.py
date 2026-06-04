# -*- coding: utf-8 -*-
"""SUT 4.2.1.A — Leflunomid (romatoid artrit / psoriatik artrit).

Resmî lafız (docs/sut/SUT_tam_metin.txt:4056, MevzuatNo=17229):

    4.2.1.A - Leflunomid
    (1) Romatoid artritli veya psoriatik artritli (bu endikasyonda sadece
        leflunomid 20-100 mg) hastaların tedavisinde; (Mülga ibare) bu durumun
        belirtildiği iç hastalıkları, romatoloji, çocuk sağlığı ve hastalıkları,
        fiziksel tıp ve rehabilitasyon uzman hekimlerinden biri tarafından
        düzenlenen bir yıl süreli uzman hekim raporuna dayanılarak bu uzman
        hekimlerce reçete edilir.

Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI PRENSİPLERİ.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (tek yolak — RA ∨ PsA endikasyonu)
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ A1 ∧ A2 ∧ B1 ∧ D1   ( B2 = bilgi )

  A1 (endikasyon, raporda belirtilmiş):
        romatoid artrit (M05/M06) ∨ psoriatik artrit (L40.5/M07.x)   [VEYA grubu]
  A2 (PsA doz kısıtı):
        PsA endikasyonunda SADECE leflunomid 20 mg / 100 mg kapsanır
        (10 mg PsA'da kapsam dışı). RA endikasyonu tüm güçleri kapsar.
  B1 (rapor): iç hastalıkları ∨ romatoloji ∨ çocuk sağlığı ∨ fiziksel tıp ve
        rehabilitasyon uzman hekimi tarafından düzenlenen uzman hekim raporu
  B2 (bilgi): rapor bir yıl süreli
  D1 (reçete): aynı uzman hekimlerden biri (dahiliye/romatoloji/çocuk/FTR) reçete eder

A2 detay (PsA "20-100 mg" yorumu): "bu endikasyonda sadece leflunomid 20-100 mg"
ibaresi PsA için yalnız 20 mg ve 100 mg güçlerinin kapsandığı şeklinde yorumlandı
(10 mg PsA'da kapsam dışı). RA varsa kapsam tam → doz kısıtı uygulanmaz.

Ana entrypoint: ``leflunomid_kontrol_4_2_1_a(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC L04AA13 leflunomid (konvansiyonel sentetik DMARD)
# ═══════════════════════════════════════════════════════════════════════
ATC_LEFLUNOMID = 'L04AA13'
LEFLUNOMID_ETKEN: Set[str] = {'LEFLUNOMID', 'LEFLUNOMIDE', 'LEFLUNOMIT'}
LEFLUNOMID_TICARI: Set[str] = {
    'ARAVA', 'LEFNO', 'IMMULEF', 'REPSO', 'ARABLOCK', 'LEFLAR',
    'LUNAVA', 'ZALEF', 'ROFLON', 'LEFLODENK',
}

# Yetkili branşlar (norm_tr_lower substring) — hem rapor hem reçete için aynı
YETKILI_BRANS = ('ic hastalik', 'dahiliye', 'romatoloji', 'cocuk sagligi',
                 'pediatri', 'fiziksel tip', 'fizik tedavi', 'rehabilitasyon',
                 'ftr')

# Endikasyon sinyalleri
RA_ICD = ('M05', 'M06')
RA_METIN = ('romatoid artrit', 'romatoit artrit', 'rheumatoid', 'ra tani',
            'romatoid artirit')
PSA_ICD = ('L40.5', 'L405', 'M07.0', 'M070', 'M07.1', 'M071', 'M07.2', 'M072',
           'M07.3', 'M073', 'M09.0', 'M090', 'M07')
PSA_METIN = ('psoriatik artrit', 'psöriatik artrit', 'psoriazik artrit',
             'psoriyatik artrit', 'artropatik psoriasis', 'artropatik psöriasis',
             'psoriatik artropati', 'psoriasis artropatika')


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


def _serbest_metin(ilac_sonuc: Dict) -> str:
    """Rapor + reçete açıklama metinleri tek normalize string."""
    parcalar: List[str] = []
    for anahtar in ('rapor_metni', 'tum_metin', 'rapor_kodu_aciklama', 'rap_ack',
                    'mesaj_metni'):
        v = ilac_sonuc.get(anahtar)
        if v:
            parcalar.append(str(v))
    for anahtar in ('rapor_aciklamalari', 'recete_aciklamalari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
            parcalar.append(str(v))
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


def _brans_listede(brans: Optional[str], anahtarlar=YETKILI_BRANS) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in anahtarlar)


def _recete_brans(ilac_sonuc: Dict) -> str:
    return (ilac_sonuc.get('recete_hekim_uzmanligi')
            or ilac_sonuc.get('doktor_uzmanligi')
            or ilac_sonuc.get('brans') or '')


def _rapor_brans(ilac_sonuc: Dict) -> str:
    return (ilac_sonuc.get('rapor_doktor_brans')
            or ilac_sonuc.get('rapor_dr_brans') or '')


def _rapor_var_mi(ilac_sonuc: Dict) -> bool:
    return bool((ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
                or (ilac_sonuc.get('rapor_takip_no') or '').strip()
                or _rapor_brans(ilac_sonuc))


def _doz_mg(ilac_sonuc: Dict) -> Optional[int]:
    """İlaç adından güç (mg) ayıkla — leflunomid 10/20/100 mg."""
    ad = norm_tr_upper(ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '')
    m = re.search(r'(\d+)\s*MG', ad)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def leflunomid_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_LEFLUNOMID):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, LEFLUNOMID_ETKEN) or _iceriyor(m, LEFLUNOMID_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# Endikasyon flagleri
# ═══════════════════════════════════════════════════════════════════════

def _ra_var(ilac_sonuc: Dict) -> bool:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _serbest_metin(ilac_sonuc)
    return any(c in icd for c in RA_ICD) or any(k in metin for k in RA_METIN)


def _psa_var(ilac_sonuc: Dict) -> bool:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _serbest_metin(ilac_sonuc)
    return any(c in icd for c in PSA_ICD) or any(k in metin for k in PSA_METIN)


# ═══════════════════════════════════════════════════════════════════════
# Atomlar
# ═══════════════════════════════════════════════════════════════════════

GRUP_ENDIK = '(1) Endikasyon — romatoid artrit VEYA psoriatik artrit'
GRUP_DOZ = '(1) PsA doz kısıtı — yalnız 20/100 mg (10 mg PsA kapsam dışı)'
GRUP_RAPOR = '(1) Uzman hekim raporu — dahiliye/romatoloji/çocuk/FTR'
GRUP_RECETE = '(1) Reçete eden — dahiliye/romatoloji/çocuk/FTR'
GRUP_SURE = '(1) Rapor bir yıl süreli (bilgi)'


def atom_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    ra = _ra_var(ilac_sonuc)
    psa = _psa_var(ilac_sonuc)
    alt = [('Romatoid artrit (M05/M06)', 'var' if ra else 'kontrol_edilemedi'),
           ('Psoriatik artrit (L40.5/M07.x)', 'var' if psa else 'kontrol_edilemedi')]
    if ra or psa:
        return SartSonuc(ad='Endikasyon (RA / psoriatik artrit)',
                         durum=SartDurumu.VAR, veya_grubu=True,
                         neden=('romatoid artrit' if ra else 'psoriatik artrit'),
                         kaynak='ICD+rapor', grup=GRUP_ENDIK, alt_liste=alt)
    return SartSonuc(ad='Endikasyon (RA / psoriatik artrit)',
                     durum=SartDurumu.KONTROL_EDILEMEDI, veya_grubu=True,
                     neden='Romatoid/psoriatik artrit endikasyonu raporda okunamadı — manuel',
                     kaynak='ICD+rapor', grup=GRUP_ENDIK, alt_liste=alt, sartli_atom=True)


def atom_psa_doz(ilac_sonuc: Dict) -> SartSonuc:
    """PsA endikasyonunda yalnız 20/100 mg kapsanır. RA varsa kapsam tam."""
    ra = _ra_var(ilac_sonuc)
    psa = _psa_var(ilac_sonuc)
    mg = _doz_mg(ilac_sonuc)
    # RA endikasyonu varsa tüm güçler kapsanır (PsA olsa da) → kısıt uygulanmaz.
    if ra or not psa:
        return SartSonuc(ad='Doz kapsamı (RA tüm güçler)', durum=SartDurumu.VAR,
                         neden='RA endikasyonu/kapsam — güç kısıtı yok',
                         kaynak='ilac_adi+endikasyon', grup=GRUP_DOZ)
    # Yalnız PsA:
    if mg is None:
        return SartSonuc(ad='PsA doz kapsamı (20/100 mg)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='İlaç adından güç (mg) okunamadı — PsA için yalnız '
                               '20/100 mg kapsanır, manuel doğrula',
                         kaynak='ilac_adi', grup=GRUP_DOZ, sartli_atom=True)
    if mg in (20, 100):
        return SartSonuc(ad=f'PsA doz kapsamı ({mg} mg)', durum=SartDurumu.VAR,
                         neden=f'{mg} mg — PsA için kapsanan güç',
                         kaynak='ilac_adi', grup=GRUP_DOZ)
    return SartSonuc(ad=f'PsA doz kapsamı ({mg} mg)', durum=SartDurumu.YOK,
                     neden=f'{mg} mg — PsA endikasyonunda yalnız 20/100 mg kapsanır',
                     kaynak='ilac_adi', grup=GRUP_DOZ)


def atom_rapor(ilac_sonuc: Dict) -> SartSonuc:
    rb = _rapor_brans(ilac_sonuc)
    if _brans_listede(rb):
        return SartSonuc(ad='Uzman hekim raporu (yetkili branş)', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb}', kaynak='rapor_brans',
                         grup=GRUP_RAPOR)
    if not _rapor_var_mi(ilac_sonuc):
        return SartSonuc(ad='Uzman hekim raporu (yetkili branş)', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı bir yıl süreli uzman hekim raporu yok',
                         kaynak='rapor', grup=GRUP_RAPOR)
    if rb:
        return SartSonuc(ad='Uzman hekim raporu (yetkili branş)', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — dahiliye/romatoloji/çocuk/FTR değil',
                         kaynak='rapor_brans', grup=GRUP_RAPOR)
    return SartSonuc(ad='Uzman hekim raporu (yetkili branş)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş doğrulanamadı — manuel',
                     kaynak='rapor_brans', grup=GRUP_RAPOR, sartli_atom=True)


def atom_recete(ilac_sonuc: Dict) -> SartSonuc:
    rb = _recete_brans(ilac_sonuc)
    if not _brans_l(rb):
        return SartSonuc(ad='Reçete eden branş', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_RECETE, sartli_atom=True)
    if _brans_listede(rb):
        return SartSonuc(ad=f'Reçete eden: {rb}', durum=SartDurumu.VAR,
                         neden='Dahiliye/romatoloji/çocuk/FTR — yetkili',
                         kaynak='hekim_brans', grup=GRUP_RECETE)
    return SartSonuc(ad=f'Reçete eden: {rb}', durum=SartDurumu.YOK,
                     neden='Yalnız iç hastalıkları/romatoloji/çocuk sağlığı/fiziksel '
                           'tıp ve rehabilitasyon uzmanı reçete edebilir',
                     kaynak='hekim_brans', grup=GRUP_RECETE)


def atom_rapor_sure(ilac_sonuc: Dict) -> SartSonuc:
    """(bilgi) Rapor bir yıl süreli. Tarih parse zayıf → KE bilgi."""
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
        if 350 <= gun <= 400:
            return SartSonuc(ad='Rapor bir yıl süreli', durum=SartDurumu.VAR,
                             neden=f'Rapor süresi {gun} gün — bir yıl sınırında',
                             kaynak='rapor_tarihleri', grup=GRUP_SURE)
        return SartSonuc(ad='Rapor bir yıl süreli', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=f'Rapor süresi {gun} gün — bir yıldan farklı olabilir, manuel',
                         kaynak='rapor_tarihleri', grup=GRUP_SURE, sartli_atom=True)
    return SartSonuc(ad='Rapor bir yıl süreli', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor başlangıç/bitiş tarihi yok — manuel doğrula',
                     kaynak='rapor_tarihleri', grup=GRUP_SURE, sartli_atom=True)


def _sartlar_uret(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_endikasyon(ilac_sonuc),
        atom_psa_doz(ilac_sonuc),
        atom_rapor(ilac_sonuc),
        atom_recete(ilac_sonuc),
        atom_rapor_sure(ilac_sonuc),  # bilgi
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
    parcalar = ['SUT 4.2.1.A Leflunomid']
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

def leflunomid_kontrol_4_2_1_a(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.1.A — Leflunomid (RA / psoriatik artrit)."""
    if not leflunomid_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='4.2.1.A kapsamı dışı — leflunomid değil',
            sut_kurali='SUT 4.2.1.A')

    sartlar = _sartlar_uret(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)

    detaylar = {
        'alt_grup': 'LEFLUNOMID',
        'sut_maddesi': '4.2.1.A',
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
        sut_kurali='SUT 4.2.1.A — Leflunomid (romatoid artrit / psoriatik artrit)',
        aranan_ibare='RA/PsA endikasyonu + uzman hekim raporu (dahiliye/romatoloji/'
                     'çocuk/FTR) + reçete branşı + PsA doz kısıtı (20/100 mg)',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("RA UYGUN (romatoloji rapor + romatoloji reçete)", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'ARAVA 20 MG FILM TABLET',
            'recete_teshisleri': ['M05.9'], 'rapor_doktor_brans': 'Romatoloji',
            'doktor_uzmanligi': 'Romatoloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['romatoid artrit'],
        }, KontrolSonucu.UYGUN),
        ("RA UYGUN (dahiliye rapor + FTR reçete + 10 mg — RA'da kapsam tam)", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'LEFLUNOMID 10 MG TABLET',
            'recete_teshisleri': ['M06.0'], 'rapor_doktor_brans': 'İç Hastalıkları',
            'doktor_uzmanligi': 'Fiziksel Tıp ve Rehabilitasyon', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['romatoid artrit'],
        }, KontrolSonucu.UYGUN),
        ("PsA UYGUN (20 mg + romatoloji rapor + romatoloji reçete)", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'ARAVA 20 MG', 'recete_teshisleri': ['L40.5'],
            'rapor_doktor_brans': 'Romatoloji', 'doktor_uzmanligi': 'Romatoloji',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['psoriatik artrit'],
        }, KontrolSonucu.UYGUN),
        ("PsA UYGUN DEĞİL (10 mg — PsA'da yalnız 20/100 mg)", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'LEFLUNOMID 10 MG', 'recete_teshisleri': ['M07.3'],
            'rapor_doktor_brans': 'Romatoloji', 'doktor_uzmanligi': 'Romatoloji',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['psoriatik artrit'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (rapor branşı kardiyoloji)", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'ARAVA 20 MG', 'recete_teshisleri': ['M05.9'],
            'rapor_doktor_brans': 'Kardiyoloji', 'doktor_uzmanligi': 'Romatoloji',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['romatoid artrit'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (reçete eden kardiyoloji)", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'ARAVA 20 MG', 'recete_teshisleri': ['M05.9'],
            'rapor_doktor_brans': 'Romatoloji', 'doktor_uzmanligi': 'Kardiyoloji',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['romatoid artrit'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (rapor yok)", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'ARAVA 20 MG', 'recete_teshisleri': ['M05.9'],
            'doktor_uzmanligi': 'Romatoloji',
            'rapor_aciklamalari': ['romatoid artrit'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ŞÜPHELİ (endikasyon yok, branşlar uygun)", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'ARAVA 20 MG', 'recete_teshisleri': ['Z00.0'],
            'rapor_doktor_brans': 'Romatoloji', 'doktor_uzmanligi': 'Romatoloji',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['kontrol'],
        }, KontrolSonucu.SARTLI_UYGUN),  # endikasyon KE-şartlı
        ("PsA ŞARTLI (güç okunamadı)", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'LEFLUNOMID FILM TABLET', 'recete_teshisleri': ['L40.5'],
            'rapor_doktor_brans': 'Romatoloji', 'doktor_uzmanligi': 'Romatoloji',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['psoriatik artrit'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("PsA UYGUN (100 mg yükleme + çocuk sağlığı)", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'ARAVA 100 MG', 'recete_teshisleri': ['L40.5'],
            'rapor_doktor_brans': 'Çocuk Sağlığı ve Hastalıkları',
            'doktor_uzmanligi': 'Çocuk Sağlığı ve Hastalıkları', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['psoriatik artrit'],
        }, KontrolSonucu.UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("RA+PsA birlikte + 10 mg → RA kapsamı UYGUN", {
            'etkin_madde': 'LEFLUNOMID', 'atc_kodu': 'L04AA13',
            'ilac_adi': 'LEFLUNOMID 10 MG', 'recete_teshisleri': ['M05.9', 'L40.5'],
            'rapor_doktor_brans': 'Romatoloji', 'doktor_uzmanligi': 'Romatoloji',
            'rapor_kodu': '1', 'rapor_aciklamalari': ['romatoid artrit psoriatik artrit'],
        }, KontrolSonucu.UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.1.A Leflunomid — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = leflunomid_kontrol_4_2_1_a(ilac_sonuc)
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
