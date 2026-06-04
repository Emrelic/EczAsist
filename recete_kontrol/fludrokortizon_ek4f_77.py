# -*- coding: utf-8 -*-
"""SUT EK-4/F m.77 — Fludrokortizon (2 endikasyon yolağı).

Resmî lafız (kullanıcı verdi 2026-06-04; ana SUT tebliğ `SUT_tam_metin.txt`'te
bulunmuyor — ek liste):
    "Fludrokortizon; primer adrenokortikal yetmezlikte (Addison hastalığı)
     veya tuz kaybettiren adrenogenital sendromda glukokortikoid ile kombine
     olarak kullanılması halinde endokrinoloji ve metabolizma hastalıkları
     uzman hekimleri tarafından düzenlenen uzman hekim raporuna istinaden
     endokrinoloji ve metabolizma hastalıkları, iç hastalıkları veya çocuk
     sağlığı ve hastalıkları uzman hekimlerince reçete edilmesi halinde ...
     Primer (çoklu sistem dejenerasyonu, parkinson hastalığı vb.) veya sekonder
     (diyabetik nefropati, amiloidoz, alkol kötüye kullanımı vb.) otonom
     nöropatide ortostatik hipotansiyonun kısa dönemli tedavisinde kardiyoloji
     veya nöroloji uzman hekimlerince düzenlenen en fazla 2 ay süreli uzman
     hekim raporuna istinaden kardiyoloji veya nöroloji uzman hekimlerince
     reçete edilmesi halinde bedelleri Kurumca karşılanır."

Protokol: CLAUDE.md ATOMİK DEVRE ŞEMASI PRENSİPLERİ.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL (dispatcher: endikasyon)
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ Y1 ∨ Y2

  Y1 (adrenal):  A1(Addison ∨ tuz kaybettiren adrenogenital sendrom)
               ∧ A2(glukokortikoid ile kombine)
               ∧ C1(endokrinoloji uzmanı raporu)
               ∧ D1(reçete: endokrinoloji ∨ iç hast. ∨ çocuk sağlığı)

  Y2 (otonom nöropati / ortostatik hipotansiyon):
                 B1(primer[parkinson/çoklu sistem dej.] ∨ sekonder[diyabetik
                    nefropati/amiloidoz/alkol] otonom nöropatide ortostatik hipotansiyon)
               ∧ C2(kardiyoloji ∨ nöroloji uzmanı raporu)
               ∧ D2(reçete: kardiyoloji ∨ nöroloji)
               [bilgi: rapor ≤2 ay süreli]

Dispatcher: endikasyon sinyallerine göre yolak seçilir; ikisi de varsa reçete
branşı ile tiebreak; hiçbiri yoksa → KONTROL_EDILEMEDI (ŞÜPHELİ).

Glukokortikoid kombine (Y1 A2): zorunlu kombinasyon — aynı reçetede
glukokortikoid varsa VAR; yoksa KE+şartlı (eş zamanlı/başka reçetede olabilir,
örtük YOK sayılmaz).

Ana entrypoint: ``fludrokortizon_kontrol_ek4f_77(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç tespiti — ATC H02AA02 fludrokortizon
# ═══════════════════════════════════════════════════════════════════════
ATC_FLUDRO = 'H02AA02'
FLUDRO_ETKEN: Set[str] = {'FLUDROKORTIZON', 'FLUDROCORTISONE', 'FLUDROKORTIZON ASETAT'}
FLUDRO_TICARI: Set[str] = {'ASTONIN', 'FLORINEF'}

# Glukokortikoid markerları (Y1 kombine şartı — diğer reçete kalemleri)
GLUKOKORTIKOID_KW: Set[str] = {
    'HIDROKORTIZON', 'HYDROCORTISONE', 'PREDNIZOLON', 'PREDNISOLONE',
    'PREDNIZON', 'PREDNISONE', 'METILPREDNIZOLON', 'METHYLPREDNISOLONE',
    'DEKSAMETAZON', 'DEXAMETHASONE', 'BETAMETAZON', 'BETAMETHASONE',
    'KORTIZON', 'CORTISONE', 'DEFLAZAKORT', 'DEFLAZACORT', 'TRIAMSINOLON',
}

# Branş anahtarları (norm_tr_lower substring)
Y1_RECETE_BRANS = ('endokrin', 'ic hastalik', 'dahiliye', 'cocuk sagligi', 'pediatri')
Y1_RAPOR_BRANS = ('endokrin',)
Y2_BRANS = ('kardiyoloji', 'noroloji')

# Endikasyon sinyalleri
ADRENAL_ICD = ('E27.1', 'E271', 'E27.2', 'E272', 'E25', 'E27.4', 'E274')
ADRENAL_METIN = ('addison', 'adrenokortikal yetmez', 'primer adrenal yetmez',
                 'adrenogenital', 'tuz kaybettiren', 'konjenital adrenal hiperplazi',
                 'kah ', 'adrenal yetmezlik')
OTONOM_ICD = ('I95.1', 'I951', 'G90', 'G20', 'G23.1', 'E11.4', 'E10.4', 'G90.3')
OTONOM_METIN = ('ortostatik hipotansiyon', 'otonom noropati', 'otonomik noropati',
                'parkinson', 'coklu sistem', 'multipl sistem atrofi', 'msa',
                'diyabetik nefropati', 'diyabetik noropati', 'amiloidoz',
                'alkol kotuye', 'postural hipotansiyon')


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


def _glukokortikoid_var(ilac_sonuc: Dict) -> Optional[str]:
    parcalar: List[str] = []
    for anahtar in ('diger_etken_maddeler', 'diger_ilac_adlari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
    metin = norm_tr_upper(' '.join(parcalar))
    for k in GLUKOKORTIKOID_KW:
        if norm_tr_upper(k) in metin:
            return k
    return None


def fludrokortizon_kapsami_mi(ilac_sonuc: Dict) -> bool:
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_FLUDRO):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, FLUDRO_ETKEN) or _iceriyor(m, FLUDRO_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER — endikasyon yolağı
# ═══════════════════════════════════════════════════════════════════════

def _adrenal_sinyal(ilac_sonuc: Dict) -> bool:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    return any(k in icd for k in ADRENAL_ICD) or any(k in metin for k in ADRENAL_METIN)


def _otonom_sinyal(ilac_sonuc: Dict) -> bool:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    return any(k in icd for k in OTONOM_ICD) or any(k in metin for k in OTONOM_METIN)


def fludrokortizon_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """'Y1' (adrenal) | 'Y2' (otonom nöropati) | None (belirsiz)."""
    y1 = _adrenal_sinyal(ilac_sonuc)
    y2 = _otonom_sinyal(ilac_sonuc)
    if y1 and not y2:
        return 'Y1'
    if y2 and not y1:
        return 'Y2'
    if y1 and y2:
        # tiebreak: reçete branşı
        rb = _recete_brans(ilac_sonuc)
        if _brans_listede(rb, Y2_BRANS):
            return 'Y2'
        if _brans_listede(rb, Y1_RECETE_BRANS):
            return 'Y1'
        return 'Y1'  # her ikisi de — adrenal öncelik (daha yaygın)
    return None


# ═══════════════════════════════════════════════════════════════════════
# YOLAK 1 atomları (adrenal)
# ═══════════════════════════════════════════════════════════════════════

GRUP_Y1_ENDIK = '(Y1) Endikasyon — Addison VEYA tuz kaybettiren adrenogenital sendrom'
GRUP_Y1_KOMBI = '(Y1) Glukokortikoid ile kombine'
GRUP_Y1_RAPOR = '(Y1) Endokrinoloji uzmanı raporu'
GRUP_Y1_RECETE = '(Y1) Reçete: endokrinoloji / iç hast. / çocuk sağlığı'


def atom_y1_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    addison = ('addison' in metin or 'adrenokortikal yetmez' in metin
               or 'E27.1' in icd or 'E271' in icd or 'E27.2' in icd or 'E272' in icd
               or 'adrenal yetmezlik' in metin)
    ags = ('adrenogenital' in metin or 'tuz kaybettiren' in metin
           or 'konjenital adrenal hiperplazi' in metin
           or 'E25' in icd)
    alt = [('Addison / primer adrenokortikal yetmezlik', 'var' if addison else 'kontrol_edilemedi'),
           ('Tuz kaybettiren adrenogenital sendrom', 'var' if ags else 'kontrol_edilemedi')]
    if addison or ags:
        return SartSonuc(ad='Adrenal endikasyon (Addison / adrenogenital sendrom)',
                         durum=SartDurumu.VAR,
                         neden='Addison/adrenal yetmezlik' if addison else 'adrenogenital sendrom',
                         kaynak='ICD+rapor', grup=GRUP_Y1_ENDIK, alt_liste=alt)
    return SartSonuc(ad='Adrenal endikasyon (Addison / adrenogenital sendrom)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Addison/adrenogenital endikasyonu okunamadı — manuel',
                     kaynak='ICD+rapor', grup=GRUP_Y1_ENDIK, alt_liste=alt, sartli_atom=True)


def atom_y1_glukokortikoid(ilac_sonuc: Dict) -> SartSonuc:
    gk = _glukokortikoid_var(ilac_sonuc)
    if gk:
        return SartSonuc(ad='Glukokortikoid ile kombine', durum=SartDurumu.VAR,
                         neden=f'Reçetede glukokortikoid: {gk}',
                         kaynak='recete_kalemleri', grup=GRUP_Y1_KOMBI)
    return SartSonuc(ad='Glukokortikoid ile kombine', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Aynı reçetede glukokortikoid yok — eş zamanlı/başka reçetede '
                           'olabilir, manuel doğrula', kaynak='recete_kalemleri',
                     grup=GRUP_Y1_KOMBI, sartli_atom=True)


def atom_y1_rapor(ilac_sonuc: Dict) -> SartSonuc:
    rb = _rapor_brans(ilac_sonuc)
    if _brans_listede(rb, Y1_RAPOR_BRANS):
        return SartSonuc(ad='Endokrinoloji uzmanı raporu', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb}', kaynak='rapor_brans', grup=GRUP_Y1_RAPOR)
    if not _rapor_var_mi(ilac_sonuc):
        return SartSonuc(ad='Endokrinoloji uzmanı raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı uzman hekim raporu yok',
                         kaynak='rapor', grup=GRUP_Y1_RAPOR)
    if rb:
        return SartSonuc(ad='Endokrinoloji uzmanı raporu', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — endokrinoloji değil',
                         kaynak='rapor_brans', grup=GRUP_Y1_RAPOR)
    return SartSonuc(ad='Endokrinoloji uzmanı raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama branş endokrinoloji olarak doğrulanamadı — manuel',
                     kaynak='rapor_brans', grup=GRUP_Y1_RAPOR, sartli_atom=True)


def atom_y1_recete(ilac_sonuc: Dict) -> SartSonuc:
    rb = _recete_brans(ilac_sonuc)
    if not _brans_l(rb):
        return SartSonuc(ad='Reçete eden branş', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_Y1_RECETE, sartli_atom=True)
    if _brans_listede(rb, Y1_RECETE_BRANS):
        return SartSonuc(ad=f'Reçete eden: {rb}', durum=SartDurumu.VAR,
                         neden='Endokrinoloji / iç hast. / çocuk sağlığı — yetkili',
                         kaynak='hekim_brans', grup=GRUP_Y1_RECETE)
    return SartSonuc(ad=f'Reçete eden: {rb}', durum=SartDurumu.YOK,
                     neden='Yalnız endokrinoloji / iç hast. / çocuk sağlığı reçete edebilir',
                     kaynak='hekim_brans', grup=GRUP_Y1_RECETE)


def _y1_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_y1_endikasyon(ilac_sonuc),
        atom_y1_glukokortikoid(ilac_sonuc),
        atom_y1_rapor(ilac_sonuc),
        atom_y1_recete(ilac_sonuc),
    ]


# ═══════════════════════════════════════════════════════════════════════
# YOLAK 2 atomları (otonom nöropati / ortostatik hipotansiyon)
# ═══════════════════════════════════════════════════════════════════════

GRUP_Y2_ENDIK = '(Y2) Otonom nöropatide ortostatik hipotansiyon'
GRUP_Y2_RAPOR = '(Y2) Kardiyoloji / nöroloji uzmanı raporu'
GRUP_Y2_RECETE = '(Y2) Reçete: kardiyoloji / nöroloji'
GRUP_Y2_SURE = '(Y2) Rapor ≤2 ay süreli (bilgi)'


def atom_y2_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    orto = ('ortostatik hipotansiyon' in metin or 'postural hipotansiyon' in metin
            or 'I95.1' in icd or 'I951' in icd)
    otonom = any(k in metin for k in ('otonom noropati', 'otonomik noropati',
                                      'parkinson', 'coklu sistem', 'multipl sistem atrofi',
                                      'diyabetik nefropati', 'diyabetik noropati',
                                      'amiloidoz', 'alkol kotuye')) \
        or any(k in icd for k in ('G90', 'G20', 'G23.1'))
    if orto or otonom:
        return SartSonuc(ad='Otonom nöropatide ortostatik hipotansiyon',
                         durum=SartDurumu.VAR,
                         neden=('ortostatik hipotansiyon' if orto else
                                'otonom nöropati (primer/sekonder)'),
                         kaynak='ICD+rapor', grup=GRUP_Y2_ENDIK)
    return SartSonuc(ad='Otonom nöropatide ortostatik hipotansiyon',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Ortostatik hipotansiyon / otonom nöropati endikasyonu '
                           'okunamadı — manuel', kaynak='ICD+rapor',
                     grup=GRUP_Y2_ENDIK, sartli_atom=True)


def atom_y2_rapor(ilac_sonuc: Dict) -> SartSonuc:
    rb = _rapor_brans(ilac_sonuc)
    if _brans_listede(rb, Y2_BRANS):
        return SartSonuc(ad='Kardiyoloji / nöroloji uzmanı raporu', durum=SartDurumu.VAR,
                         neden=f'Rapor düzenleyen: {rb}', kaynak='rapor_brans', grup=GRUP_Y2_RAPOR)
    if not _rapor_var_mi(ilac_sonuc):
        return SartSonuc(ad='Kardiyoloji / nöroloji uzmanı raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı uzman hekim raporu yok',
                         kaynak='rapor', grup=GRUP_Y2_RAPOR)
    if rb:
        return SartSonuc(ad='Kardiyoloji / nöroloji uzmanı raporu', durum=SartDurumu.YOK,
                         neden=f'Rapor branşı "{rb}" — kardiyoloji/nöroloji değil',
                         kaynak='rapor_brans', grup=GRUP_Y2_RAPOR)
    return SartSonuc(ad='Kardiyoloji / nöroloji uzmanı raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama branş kardiyoloji/nöroloji olarak '
                           'doğrulanamadı — manuel', kaynak='rapor_brans',
                     grup=GRUP_Y2_RAPOR, sartli_atom=True)


def atom_y2_recete(ilac_sonuc: Dict) -> SartSonuc:
    rb = _recete_brans(ilac_sonuc)
    if not _brans_l(rb):
        return SartSonuc(ad='Reçete eden branş', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_Y2_RECETE, sartli_atom=True)
    if _brans_listede(rb, Y2_BRANS):
        return SartSonuc(ad=f'Reçete eden: {rb}', durum=SartDurumu.VAR,
                         neden='Kardiyoloji / nöroloji — yetkili',
                         kaynak='hekim_brans', grup=GRUP_Y2_RECETE)
    return SartSonuc(ad=f'Reçete eden: {rb}', durum=SartDurumu.YOK,
                     neden='Yalnız kardiyoloji / nöroloji reçete edebilir',
                     kaynak='hekim_brans', grup=GRUP_Y2_RECETE)


def atom_y2_sure(ilac_sonuc: Dict) -> SartSonuc:
    """(bilgi) Rapor en fazla 2 ay süreli. Tarih parse zayıf → KE bilgi."""
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
        if gun <= 65:
            return SartSonuc(ad='Rapor süresi ≤2 ay', durum=SartDurumu.VAR,
                             neden=f'Rapor süresi {gun} gün — 2 ay sınırında',
                             kaynak='rapor_tarihleri', grup=GRUP_Y2_SURE)
        return SartSonuc(ad='Rapor süresi ≤2 ay', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=f'Rapor süresi {gun} gün — 2 ayı aşıyor olabilir, manuel',
                         kaynak='rapor_tarihleri', grup=GRUP_Y2_SURE, sartli_atom=True)
    return SartSonuc(ad='Rapor süresi ≤2 ay', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor başlangıç/bitiş tarihi yok — manuel doğrula',
                     kaynak='rapor_tarihleri', grup=GRUP_Y2_SURE, sartli_atom=True)


def _y2_sartlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_y2_endikasyon(ilac_sonuc),
        atom_y2_rapor(ilac_sonuc),
        atom_y2_recete(ilac_sonuc),
        atom_y2_sure(ilac_sonuc),  # bilgi
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


def _mesaj_uret(sonuc: KontrolSonucu, yolak: str, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    yolak_ad = {'Y1': 'adrenal (Addison/adrenogenital)',
                'Y2': 'otonom nöropati/ortostatik hipotansiyon'}.get(yolak, yolak)
    parcalar = [f'EK-4/F m.77 Fludrokortizon / {yolak_ad}']
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

YOLAK_FN = {'Y1': _y1_sartlari, 'Y2': _y2_sartlari}


def fludrokortizon_kontrol_ek4f_77(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT EK-4/F m.77 — Fludrokortizon (adrenal / otonom nöropati)."""
    if not fludrokortizon_kapsami_mi(ilac_sonuc):
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='EK-4/F m.77 kapsamı dışı — fludrokortizon değil',
            sut_kurali='SUT EK-4/F m.77')

    yolak = fludrokortizon_yolak_belirle(ilac_sonuc)
    if not yolak:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='EK-4/F m.77 Fludrokortizon — endikasyon (adrenal / otonom '
                  'nöropati) tespit edilemedi — manuel doğrulama',
            sut_kurali='SUT EK-4/F m.77',
            sartlar=[SartSonuc(ad='Endikasyon (adrenal / otonom nöropati)',
                               durum=SartDurumu.KONTROL_EDILEMEDI,
                               neden='ICD/rapor metninde endikasyon okunamadı',
                               kaynak='ICD+rapor', grup='Endikasyon dispatcher',
                               sartli_atom=True)])

    sartlar = YOLAK_FN[yolak](ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)

    detaylar = {
        'alt_grup': 'FLUDROKORTIZON',
        'sut_maddesi': 'EK-4/F m.77',
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
        sut_kurali='SUT EK-4/F m.77 — Fludrokortizon (adrenal / otonom nöropati)',
        aranan_ibare='endikasyon + uzman raporu + reçete branşı (yolağa göre)',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("Y1 UYGUN (Addison + GK kombine + endo rapor + endo reçete)", {
            'etkin_madde': 'FLUDROKORTIZON', 'atc_kodu': 'H02AA02',
            'recete_teshisleri': ['E27.1'], 'rapor_doktor_brans': 'Endokrinoloji',
            'doktor_uzmanligi': 'Endokrinoloji ve Metabolizma Hastalıkları',
            'rapor_kodu': '1', 'diger_etken_maddeler': ['HIDROKORTIZON'],
            'rapor_aciklamalari': ['addison hastalığı'],
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN (adrenogenital + GK + iç hast. reçete + endo rapor)", {
            'etkin_madde': 'FLUDROKORTIZON', 'atc_kodu': 'H02AA02',
            'recete_teshisleri': ['E25.0'], 'rapor_doktor_brans': 'Endokrinoloji',
            'doktor_uzmanligi': 'İç Hastalıkları', 'rapor_kodu': '1',
            'diger_ilac_adlari': ['PREDNOL'], 'diger_etken_maddeler': ['METILPREDNIZOLON'],
            'rapor_aciklamalari': ['tuz kaybettiren adrenogenital sendrom'],
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN DEĞİL (rapor branş kardiyoloji)", {
            'etkin_madde': 'FLUDROKORTIZON', 'atc_kodu': 'H02AA02',
            'recete_teshisleri': ['E27.1'], 'rapor_doktor_brans': 'Kardiyoloji',
            'doktor_uzmanligi': 'İç Hastalıkları', 'rapor_kodu': '1',
            'diger_etken_maddeler': ['HIDROKORTIZON'],
            'rapor_aciklamalari': ['addison'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 UYGUN DEĞİL (reçete eden kardiyoloji)", {
            'etkin_madde': 'FLUDROKORTIZON', 'atc_kodu': 'H02AA02',
            'recete_teshisleri': ['E27.1'], 'rapor_doktor_brans': 'Endokrinoloji',
            'doktor_uzmanligi': 'Kardiyoloji', 'rapor_kodu': '1',
            'diger_etken_maddeler': ['HIDROKORTIZON'],
            'rapor_aciklamalari': ['addison'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 ŞARTLI (GK yok — manuel)", {
            'etkin_madde': 'FLUDROKORTIZON', 'atc_kodu': 'H02AA02',
            'recete_teshisleri': ['E27.1'], 'rapor_doktor_brans': 'Endokrinoloji',
            'doktor_uzmanligi': 'Endokrinoloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['addison'],
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Y2 UYGUN (ortostatik hipotansiyon + nöro rapor + nöro reçete)", {
            'etkin_madde': 'FLUDROKORTIZON', 'atc_kodu': 'H02AA02',
            'recete_teshisleri': ['I95.1'], 'rapor_doktor_brans': 'Nöroloji',
            'doktor_uzmanligi': 'Nöroloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['parkinson otonom nöropati ortostatik hipotansiyon'],
        }, KontrolSonucu.UYGUN),
        ("Y2 UYGUN (kardiyoloji rapor + kardiyoloji reçete)", {
            'etkin_madde': 'FLUDROKORTIZON', 'atc_kodu': 'H02AA02',
            'recete_teshisleri': ['I95.1'], 'rapor_doktor_brans': 'Kardiyoloji',
            'doktor_uzmanligi': 'Kardiyoloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['ortostatik hipotansiyon'],
        }, KontrolSonucu.UYGUN),
        ("Y2 UYGUN DEĞİL (reçete eden endokrinoloji — Y2'de yetkisiz)", {
            'etkin_madde': 'FLUDROKORTIZON', 'atc_kodu': 'H02AA02',
            'recete_teshisleri': ['I95.1'], 'rapor_doktor_brans': 'Nöroloji',
            'doktor_uzmanligi': 'Endokrinoloji', 'rapor_kodu': '1',
            'rapor_aciklamalari': ['ortostatik hipotansiyon otonom nöropati'],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Endikasyon belirsiz → ŞÜPHELİ", {
            'etkin_madde': 'FLUDROKORTIZON', 'atc_kodu': 'H02AA02',
            'recete_teshisleri': ['Z00.0'], 'doktor_uzmanligi': 'Üroloji',
            'rapor_aciklamalari': ['kontrol'],
        }, KontrolSonucu.KONTROL_EDILEMEDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("Y1 UYGUN (ticari ASTONIN)", {
            'ilac_adi': 'ASTONIN-H 0.1 MG', 'etkin_madde': 'FLUDROKORTIZON',
            'recete_teshisleri': ['E27.1'], 'rapor_doktor_brans': 'Endokrinoloji',
            'doktor_uzmanligi': 'Çocuk Sağlığı ve Hastalıkları', 'rapor_kodu': '1',
            'diger_etken_maddeler': ['HIDROKORTIZON'],
            'rapor_aciklamalari': ['addison hastalığı'],
        }, KontrolSonucu.UYGUN),
    ]


def _akil_testi() -> None:
    print("SUT EK-4/F m.77 Fludrokortizon — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = fludrokortizon_kontrol_ek4f_77(ilac_sonuc)
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
