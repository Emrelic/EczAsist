# -*- coding: utf-8 -*-
"""SUT 4.2.9.A — Eritropoietin, darbepoetin ve roksadustat kullanım ilkeleri.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:5030-5064`` (mevzuat.gov.tr,
MevzuatNo=17229, Değişik:RG-19/10/2023). Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md``
+ CLAUDE.md ``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
İKİ ENDİKASYON YOLAĞI (dispatcher: endikasyon + ilaç)
═══════════════════════════════════════════════════════════════════════════

  Kapsam ilaçları: eritropoietin (alfa/beta/zeta), metoksipolietilen glikol
  epoetin beta (Mircera), darbepoetin (Aranesp), roksadustat (Evrenzo).
  ATC: B03XA01/02/03/05.

  YOLAK A-1 → Kronik böbrek yetmezliği ile ilişkili anemi (4.2.9.A-1)
  YOLAK A-2 → Myelodisplastik sendrom (4.2.9.A-2)

  Dispatcher genel kuralı (4.2.9.A md.1):
    - Roksadustat YALNIZ KBY anemisinde (MDS / diğer endikasyon → UYGUN_DEĞİL)
    - EPO/darbepo YALNIZ KBY anemi VEYA MDS (diğer endikasyon → UYGUN_DEĞİL)
    - Endikasyon (ICD/metin) tespit edilemiyor → ŞÜPHELİ

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  YOLAK A-1:  A1_UYGUN ⇔ A1(KBY) ∧ A2(demir: TSAT≥20 ∨ ferritin≥100)
                         ∧ A3(Hb ≤ 12) ∧ A4(reçete branş) ∧ A5(rapor branş)
                         [∧ A8(≤1 ay doz)]   ;  Hb>12 ⇒ UYGUN_DEĞİL
              [bilgi: A6 tetkik belge tarih/sonuç · A7 doz/süre]

  YOLAK A-2:  A2_UYGUN ⇔ B1(MDS) ∧ B2(Hb<11) ∧ B3(blast<%5)
                         ∧ B4(serum EPO<500) ∧ B6(hematoloji rapor)
                         ∧ B7(reçete hematoloji/iç hast.)
                         ;  Hb>12 ⇒ UYGUN_DEĞİL
              [bilgi: B8 hemogram belge tarih/sonuç]

Lab değerleri rapor metninden parse edilir (kullanıcı kuralı 2026-06-03
"hesaplamayı dene"); SUT-anlatı sayıları (hedef/altında/aşınca/'in) ayıklanır;
değer yoksa KE+şartlı → SARTLI_UYGUN. Sessizlik = örtük kabul YASAK.

Ana entrypoint: ``eritropoietin_kontrol_4_2_9_a(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç sınıfı listeleri (etken + ticari ad + ATC)
# ═══════════════════════════════════════════════════════════════════════

EPOETIN: Set[str] = {
    'EPOETIN', 'ERITROPOIETIN', 'ERYTHROPOIETIN',
    'EPOETIN ALFA', 'EPOETIN BETA', 'EPOETIN ZETA',
    'EPREX', 'NEORECORMON', 'RETACRIT', 'BINOCRIT', 'EPOSINO',
    'EPOTIN', 'EPORON', 'EPOJECT', 'EPOBORON', 'ESPOGEN', 'EPODER',
}
MIRCERA: Set[str] = {
    'METOKSIPOLIETILEN', 'METHOXY POLYETHYLENE', 'METOKSI POLIETILEN',
    'EPOETIN BETA METOKSI', 'MIRCERA', 'C.E.R.A',
}
DARBEPOETIN: Set[str] = {
    'DARBEPOETIN', 'DARBEPOETIN ALFA', 'ARANESP',
}
ROKSADUSTAT: Set[str] = {
    'ROKSADUSTAT', 'ROXADUSTAT', 'EVRENZO',
}

# ATC önekleri (güçlü sinyal)
ATC_ESA = {
    'B03XA01': 'EPOETIN',
    'B03XA02': 'DARBEPOETIN',
    'B03XA03': 'MIRCERA',
    'B03XA05': 'ROKSADUSTAT',
}

# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower alt-string)
# ═══════════════════════════════════════════════════════════════════════
NEFROLOJI = ['nefroloji']
IC_HAST = ['ic hastalik', 'dahiliye']
COCUK = ['cocuk', 'pediatri']
HEMATOLOJI = ['hematoloji']
# A-1 reçete/rapor için geniş izinli liste (diyaliz sertifikalı hariç DB'de yok)
A1_GENIS = NEFROLOJI + IC_HAST + COCUK


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


def _brans_listede(brans: Optional[str], anahtarlar: List[str]) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in anahtarlar)


def _heyet_brans_listesi(ilac_sonuc: Dict) -> List[str]:
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not isinstance(heyet, (list, tuple)):
        return []
    return [h.get('brans') or '' for h in heyet if (h.get('ad') or h.get('brans'))]


# SUT-anlatı (threshold/narrative) işaretleri — bunların yakınındaki sayı
# hastanın ölçüm değeri DEĞİL, mevzuat eşik sayısıdır → atla.
_NARRATIVE = ("hedef", "altind", "ustun", "uzerin", "ulasi", "asinc", "asan",
              "arasi", "gelinc", "gecinc", "kesil", "baslan", "tutab",
              "'in", "'nin", "'nın", "'yi", "'ye", "'ya", "'a ")


def _lab_deger(metin: str, anahtarlar: List[str]) -> Optional[float]:
    """Rapor metninde anahtar yakınındaki ilk ölçüm değerini döndür.

    metin: norm_tr_lower edilmiş. SUT-anlatı sayıları (_NARRATIVE) atlanır.
    """
    for a in anahtarlar:
        for m in re.finditer(re.escape(a) + r'[^\d\n]{0,12}?(\d+(?:[.,]\d+)?)', metin):
            before = metin[max(0, m.start() - 15):m.start()]
            after = metin[m.end():m.end() + 15]
            ctx = before + ' ' + after
            if any(tok in ctx for tok in _NARRATIVE):
                continue
            try:
                return float(m.group(1).replace(',', '.'))
            except ValueError:
                continue
    return None


# ═══════════════════════════════════════════════════════════════════════
# İLAÇ SINIFI + ENDİKASYON + DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════

def _ilac_sinifi(ilac_sonuc: Dict) -> Optional[str]:
    """ESA ilaç sınıfı → 'EPOETIN'|'MIRCERA'|'DARBEPOETIN'|'ROKSADUSTAT'|None."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    for prefix, sinif in ATC_ESA.items():
        if atc.startswith(prefix):
            return sinif
    m = _arama_metni(ilac_sonuc)
    if _iceriyor(m, ROKSADUSTAT):
        return 'ROKSADUSTAT'
    if _iceriyor(m, DARBEPOETIN):
        return 'DARBEPOETIN'
    if _iceriyor(m, MIRCERA):
        return 'MIRCERA'
    if _iceriyor(m, EPOETIN):
        return 'EPOETIN'
    return None


def _endikasyon_belirle(ilac_sonuc: Dict) -> Tuple[bool, bool]:
    """(mds, kby) — ICD + rapor metni sinyalleri."""
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    mds = bool(re.search(r'\bD46', icd)) or 'myelodisplastik' in metin \
        or re.search(r'\bmds\b', metin) is not None
    kby = bool(re.search(r'\bN18', icd)) or any(
        k in metin for k in ('kronik bobrek', 'kronik renal', 'son donem bobrek',
                              'sdby', 'kby', 'diyaliz', 'hemodiyaliz', 'periton',
                              'prediyaliz', 'kronik bobrek yetmezlik'))
    return mds, kby


def eritropoietin_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """Kapsam içi mi + hangi yolak? → 'A1'|'A2'|None.

    None = ESA ilacı değil (ATLANDI). Endikasyon gating dispatcher'da değil,
    ana entrypoint'te (ön-kontrol) yapılır.
    """
    if _ilac_sinifi(ilac_sonuc) is None:
        return None
    mds, kby = _endikasyon_belirle(ilac_sonuc)
    if mds and not kby:
        return 'A2'
    if kby and not mds:
        return 'A1'
    if mds and kby:
        # Her ikisi — ICD önceliği; ikisi de ICD ise KBY (daha yaygın) + belirsiz
        icd = _teshis_birlesik(ilac_sonuc)
        if re.search(r'\bD46', icd) and not re.search(r'\bN18', icd):
            return 'A2'
        return 'A1'
    return None  # endikasyon belirsiz


# ═══════════════════════════════════════════════════════════════════════
# YOLAK A-1 atomları (KBY anemi)
# ═══════════════════════════════════════════════════════════════════════

def _diyaliz_tipi(ilac_sonuc: Dict) -> Optional[str]:
    """Rapor metninden diyaliz tipi → 'HD'|'PD'|'PRE'|None."""
    metin = _rapor_metni(ilac_sonuc)
    if 'hemodiyaliz' in metin or re.search(r'\bhd\b', metin):
        return 'HD'
    if 'periton' in metin or re.search(r'\b(capd|sapd)\b', metin):
        return 'PD'
    if 'prediyaliz' in metin or 'pre diyaliz' in metin or 'pre-diyaliz' in metin:
        return 'PRE'
    return None


def atom_a1_endikasyon(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    n18 = bool(re.search(r'\bN18', icd))
    metin_kby = any(k in metin for k in ('kronik bobrek', 'diyaliz', 'hemodiyaliz',
                                         'periton', 'son donem bobrek', 'kby'))
    if n18 or metin_kby:
        return SartSonuc(ad='KBY anemi endikasyonu', durum=SartDurumu.VAR,
                         neden=('ICD N18' if n18 else 'rapor: kronik böbrek/diyaliz'),
                         kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad='KBY anemi endikasyonu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='KBY/diyaliz endikasyonu net okunamadı — manuel',
                     kaynak='ICD+rapor', grup=grup, sartli_atom=True)


def atom_demir_yeterli(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A2: TSAT ≥ %20 ve/veya ferritin ≥ 100 µg/L (≥1 yeterli)."""
    metin = _rapor_metni(ilac_sonuc)
    tsat = _lab_deger(metin, ['tsat', 'transferrin satur', 'satürasyon', 'saturasyon'])
    ferritin = _lab_deger(metin, ['ferritin'])
    if tsat is None and ferritin is None:
        return SartSonuc(ad='Demir parametreleri (TSAT≥%20 / ferritin≥100)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='TSAT/ferritin rapor metninden okunamadı — manuel',
                         kaynak='rapor_lab', grup=grup, sartli_atom=True)
    yeterli = (tsat is not None and tsat >= 20) or (ferritin is not None and ferritin >= 100)
    if yeterli:
        return SartSonuc(ad='Demir yeterli (TSAT≥%20 / ferritin≥100)',
                         durum=SartDurumu.VAR,
                         neden=f"TSAT={tsat if tsat is not None else '?'} "
                               f"ferritin={ferritin if ferritin is not None else '?'}",
                         kaynak='rapor_lab', grup=grup)
    # En az biri ölçülmüş ama yeterli değil — diğeri de ölçülmüşse YOK; değilse KE
    if tsat is not None and ferritin is not None:
        return SartSonuc(ad='Demir yetersiz (TSAT<%20 ve ferritin<100)',
                         durum=SartDurumu.YOK,
                         neden=f'TSAT={tsat} ferritin={ferritin} — önce demir tedavisi gerekli',
                         kaynak='rapor_lab', grup=grup)
    return SartSonuc(ad='Demir parametreleri', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f"TSAT={tsat if tsat is not None else '?'} "
                           f"ferritin={ferritin if ferritin is not None else '?'} — "
                           f"diğer değer yok, manuel doğrula",
                     kaynak='rapor_lab', grup=grup, sartli_atom=True)


def atom_hb_araligi(ilac_sonuc: Dict, grup: str, ust_sinir: float = 12.0,
                     baslangic_alt: Optional[float] = None) -> SartSonuc:
    """A3/B2: Hb tedavi aralığında mı? Hb > ust_sinir → kontrendikasyon (kes).

    baslangic_alt verilirse (MDS=11) ve Hb o değerin altındaysa açıkça başlangıç-VAR.
    """
    metin = _rapor_metni(ilac_sonuc)
    hb = _lab_deger(metin, ['hemoglobin', 'hgb', 'hb'])
    if hb is None:
        return SartSonuc(ad=f'Hemoglobin (≤{ust_sinir:g})', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hb değeri rapor metninden okunamadı — manuel',
                         kaynak='rapor_lab', grup=grup, sartli_atom=True)
    if hb > ust_sinir:
        return SartSonuc(ad=f'Hemoglobin {hb:g} > {ust_sinir:g}', durum=SartDurumu.YOK,
                         neden=f'Hb {hb:g} gr/dl — {ust_sinir:g} aşıldı, tedavi kesilmeli',
                         kaynak='rapor_lab', grup=grup)
    return SartSonuc(ad=f'Hemoglobin {hb:g} (≤{ust_sinir:g})', durum=SartDurumu.VAR,
                     neden=f'Hb {hb:g} gr/dl — tedavi aralığında', kaynak='rapor_lab', grup=grup)


def atom_a1_recete_brans(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A4: reçete eden branş — diyaliz tipine göre.

    PRE/PD → nefroloji zorunlu. HD → nefro/iç/çocuk/diyaliz sertifikalı.
    Tip belirsiz → geniş liste + KE notu. Diyaliz sertifikalı DB'de yok →
    geniş liste dışıysa KE+şartlı (kullanıcı kuralı 2026-06-03).
    """
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    bl = _brans_l(brans)
    tip = _diyaliz_tipi(ilac_sonuc)
    if not bl:
        return SartSonuc(ad='Reçete eden branş', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if tip in ('PRE', 'PD'):
        if _brans_listede(brans, NEFROLOJI):
            return SartSonuc(ad=f'Reçete eden: {brans} ({tip})', durum=SartDurumu.VAR,
                             neden=f'{tip} hastasında nefroloji reçete edebilir',
                             kaynak='hekim_brans', grup=grup)
        return SartSonuc(ad=f'Reçete eden: {brans} ({tip})', durum=SartDurumu.YOK,
                         neden=f'{tip} (prediyaliz/periton) hastasında yalnız nefroloji '
                               f'reçete edebilir', kaynak='hekim_brans', grup=grup)
    # HD veya tip belirsiz → geniş liste
    if _brans_listede(brans, A1_GENIS):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Nefroloji/iç hast./çocuk — yetkili'
                               + ('' if tip else ' (diyaliz tipi belirsiz)'),
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Nefro/iç/çocuk değil — diyaliz sertifikalı hekim olabilir, '
                           'manuel doğrula', kaynak='hekim_brans', grup=grup, sartli_atom=True)


def atom_a1_rapor_brans(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A5: rapor düzenleyen nefro/iç/çocuk/diyaliz sertifikalı uzman mı?"""
    rb = ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or ''
    heyet = _heyet_brans_listesi(ilac_sonuc)
    adaylar = [rb] + heyet
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or ilac_sonuc.get('rap_tak_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or any(adaylar))
    if any(_brans_listede(b, A1_GENIS) for b in adaylar):
        return SartSonuc(ad='Uzman hekim raporu (nefro/iç/çocuk)', durum=SartDurumu.VAR,
                         neden='Rapor yetkili uzman branşında', kaynak='rapor_brans', grup=grup)
    if not rapor_var:
        return SartSonuc(ad='Uzman hekim raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı uzman hekim raporu bulunamadı',
                         kaynak='rapor', grup=grup)
    return SartSonuc(ad='Uzman hekim raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş nefro/iç/çocuk olarak '
                           'doğrulanamadı (diyaliz sertifikalı olabilir) — manuel',
                     kaynak='rapor_brans', grup=grup, sartli_atom=True)


def atom_tetkik_belge(ilac_sonuc: Dict, grup: str, ibare: str) -> SartSonuc:
    """A6/B8 (bilgi): tetkik/hemogram sonuç belgesi tarih+sonuç reçete/raporda."""
    metin = _rapor_metni(ilac_sonuc)
    tarih_var = bool(re.search(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', metin))
    if tarih_var:
        return SartSonuc(ad=ibare, durum=SartDurumu.VAR,
                         neden='Tetkik tarihi rapor/reçete metninde bulundu',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad=ibare, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Tetkik sonuç belgesi tarih/sonucu metinden okunamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_bir_aylik_doz(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A8 (şartlı): bir defada en fazla 1 aylık ilaç. Kutu adediyle kaba hesap."""
    kutu = ilac_sonuc.get('kutu_sayisi')
    try:
        kutu = float(kutu) if kutu not in (None, '') else None
    except (TypeError, ValueError):
        kutu = None
    if kutu is None:
        ks = (ilac_sonuc.get('kutu') or '').strip()
        try:
            kutu = float(ks) if ks else None
        except ValueError:
            kutu = None
    if kutu is None:
        return SartSonuc(ad='En fazla 1 aylık doz', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Kutu/doz okunamadı — manuel', kaynak='doz',
                         grup=grup, sartli_atom=True)
    if kutu <= 12:
        return SartSonuc(ad='En fazla 1 aylık doz', durum=SartDurumu.VAR,
                         neden=f'Kutu adedi {kutu:g} — 1 aylık için makul',
                         kaynak='doz', grup=grup)
    return SartSonuc(ad='En fazla 1 aylık doz', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Kutu adedi {kutu:g} — 1 aylık dozu aşıyor olabilir, manuel',
                     kaynak='doz', grup=grup, sartli_atom=True)


def y_a1_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """YOLAK A-1: KBY anemi."""
    s: List[SartSonuc] = []
    s.append(atom_a1_endikasyon(ilac_sonuc, grup='(A-1) KBY anemi endikasyonu'))
    s.append(atom_demir_yeterli(ilac_sonuc, grup='(A-1) Demir parametreleri'))
    s.append(atom_hb_araligi(ilac_sonuc, grup='(A-1) Hemoglobin ≤12', ust_sinir=12.0))
    s.append(atom_a1_recete_brans(ilac_sonuc, grup='(A-1) Reçete eden branş'))
    s.append(atom_a1_rapor_brans(ilac_sonuc, grup='(A-1) Uzman hekim raporu'))
    s.append(atom_bir_aylik_doz(ilac_sonuc, grup='(A-1) En fazla 1 aylık doz'))
    s.append(atom_tetkik_belge(ilac_sonuc, grup='(A-1) Tetkik belgesi (bilgi)',
                               ibare='Tetkik sonuç belgesi tarih+sonuç'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# YOLAK A-2 atomları (MDS)
# ═══════════════════════════════════════════════════════════════════════

def atom_b1_endikasyon(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    d46 = bool(re.search(r'\bD46', icd))
    if d46 or 'myelodisplastik' in metin or re.search(r'\bmds\b', metin):
        return SartSonuc(ad='MDS endikasyonu', durum=SartDurumu.VAR,
                         neden=('ICD D46' if d46 else 'rapor: myelodisplastik sendrom'),
                         kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad='MDS endikasyonu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='MDS endikasyonu net okunamadı — manuel',
                     kaynak='ICD+rapor', grup=grup, sartli_atom=True)


def atom_b_blast(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    blast = _lab_deger(metin, ['blast'])
    if blast is None:
        return SartSonuc(ad='Blast oranı < %5', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Blast oranı rapor metninden okunamadı — manuel',
                         kaynak='rapor_lab', grup=grup, sartli_atom=True)
    if blast < 5:
        return SartSonuc(ad=f'Blast %{blast:g} < %5', durum=SartDurumu.VAR,
                         neden=f'Blast oranı %{blast:g}', kaynak='rapor_lab', grup=grup)
    return SartSonuc(ad=f'Blast %{blast:g} ≥ %5', durum=SartDurumu.YOK,
                     neden=f'Blast oranı %{blast:g} — %5 ve üzeri', kaynak='rapor_lab', grup=grup)


def atom_b_serum_epo(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    epo = _lab_deger(metin, ['serum eritropoietin', 'eritropoietin duzey',
                             'eritropoetin duzey', 'epo duzey', 'serum epo'])
    if epo is None:
        return SartSonuc(ad='Serum EPO < 500 mu/ml', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Serum eritropoietin düzeyi okunamadı — manuel',
                         kaynak='rapor_lab', grup=grup, sartli_atom=True)
    if epo < 500:
        return SartSonuc(ad=f'Serum EPO {epo:g} < 500', durum=SartDurumu.VAR,
                         neden=f'Serum eritropoietin {epo:g} mu/ml', kaynak='rapor_lab', grup=grup)
    return SartSonuc(ad=f'Serum EPO {epo:g} ≥ 500', durum=SartDurumu.YOK,
                     neden=f'Serum eritropoietin {epo:g} mu/ml — 500 ve üzeri',
                     kaynak='rapor_lab', grup=grup)


def atom_b_rapor_hematoloji(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    rb = ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or ''
    heyet = _heyet_brans_listesi(ilac_sonuc)
    adaylar = [rb] + heyet
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_var = bool(rapor_kodu or any(adaylar))
    if any(_brans_listede(b, HEMATOLOJI) for b in adaylar):
        return SartSonuc(ad='Hematoloji uzman hekim raporu', durum=SartDurumu.VAR,
                         neden='Rapor hematoloji uzmanınca', kaynak='rapor_brans', grup=grup)
    if not rapor_var:
        return SartSonuc(ad='Hematoloji uzman hekim raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor bulunamadı', kaynak='rapor', grup=grup)
    return SartSonuc(ad='Hematoloji uzman hekim raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama hematoloji uzmanı olduğu doğrulanamadı — manuel',
                     kaynak='rapor_brans', grup=grup, sartli_atom=True)


def atom_b_recete_brans(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden branş (hematoloji/iç hast.)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, HEMATOLOJI + IC_HAST):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Hematoloji / iç hastalıkları — yetkili',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Yalnız hematoloji veya iç hastalıkları reçete edebilir',
                     kaynak='hekim_brans', grup=grup)


def y_a2_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """YOLAK A-2: MDS."""
    s: List[SartSonuc] = []
    s.append(atom_b1_endikasyon(ilac_sonuc, grup='(A-2) MDS endikasyonu'))
    s.append(atom_hb_araligi(ilac_sonuc, grup='(A-2) Hemoglobin', ust_sinir=12.0))
    s.append(atom_b_blast(ilac_sonuc, grup='(A-2) Blast oranı < %5'))
    s.append(atom_b_serum_epo(ilac_sonuc, grup='(A-2) Serum EPO < 500'))
    s.append(atom_b_rapor_hematoloji(ilac_sonuc, grup='(A-2) Hematoloji uzman raporu'))
    s.append(atom_b_recete_brans(ilac_sonuc, grup='(A-2) Reçete eden branş'))
    s.append(atom_tetkik_belge(ilac_sonuc, grup='(A-2) Hemogram belgesi (bilgi)',
                               ibare='Hemogram sonuç belgesi tarih+sonuç'))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA
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
    yolak_ad = {'A1': 'KBY anemi (4.2.9.A-1)', 'A2': 'MDS (4.2.9.A-2)'}.get(yolak, yolak)
    parcalar = [f"SUT 4.2.9.A / {yolak_ad}"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — tüm şartlar sağlandı")
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f"ŞARTLI UYGUN — hesaplanabilir şartlar VAR; "
                        f"{len(ke)} şart manuel doğrulama gerektiriyor")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append("UYGUN DEĞİL — " + '; '.join(s.ad for s in yok[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f"ŞÜPHELİ — {len(ke)} şart kontrol edilemedi")
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

YOLAK_FN_MAP = {'A1': y_a1_kontrol, 'A2': y_a2_kontrol}
YOLAK_METADATA = {
    'A1': {'ad': 'KBY ile ilişkili anemi', 'sut': '4.2.9.A-1'},
    'A2': {'ad': 'Myelodisplastik sendrom', 'sut': '4.2.9.A-2'},
}


def eritropoietin_kontrol_4_2_9_a(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.9.A ana kontrol fonksiyonu (ESA: EPO/darbepo/Mircera/roksadustat)."""
    sinif = _ilac_sinifi(ilac_sonuc)
    if sinif is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.9.A kapsamı dışı — ESA (EPO/darbepo/roksadustat) değil',
            sut_kurali='SUT 4.2.9.A')

    mds, kby = _endikasyon_belirle(ilac_sonuc)

    # ── Ön-kontrol: ilaç-endikasyon uyumu (md.1) ──
    if sinif == 'ROKSADUSTAT' and mds and not kby:
        return KontrolRaporu(
            sonuc=KontrolSonucu.UYGUN_DEGIL,
            mesaj='SUT 4.2.9.A — Roksadustat yalnız KBY anemisinde karşılanır '
                  '(MDS endikasyonu kapsam dışı, md.1)',
            sut_kurali='SUT 4.2.9.A (1)',
            sartlar=[SartSonuc(ad='Roksadustat endikasyon', durum=SartDurumu.YOK,
                               neden='Roksadustat MDS\'de Kurumca karşılanmaz',
                               kaynak='dispatcher', grup='(1) İlaç-endikasyon uyumu')])

    if not mds and not kby:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='SUT 4.2.9.A — Endikasyon (KBY anemi / MDS) tespit edilemedi; '
                  'EPO/darbepo/roksadustat yalnız bu endikasyonlarda karşılanır (md.1) '
                  '— manuel doğrulama',
            sut_kurali='SUT 4.2.9.A (1)',
            sartlar=[SartSonuc(ad='Endikasyon (KBY anemi / MDS)',
                               durum=SartDurumu.KONTROL_EDILEMEDI,
                               neden='ICD/rapor metninde KBY veya MDS okunamadı',
                               kaynak='ICD+rapor', grup='(1) Endikasyon',
                               sartli_atom=True)])

    yolak = eritropoietin_yolak_belirle(ilac_sonuc)
    if not yolak:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj='SUT 4.2.9.A — Endikasyon belirsiz, yolak seçilemedi — manuel',
            sut_kurali='SUT 4.2.9.A')

    sartlar = YOLAK_FN_MAP[yolak](ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali=f"SUT 4.2.9.A / {YOLAK_METADATA[yolak]['sut']}",
        sartlar=sartlar,
        detaylar={'yolak': yolak, 'ilac_sinifi': sinif,
                  'yolak_ad': YOLAK_METADATA[yolak]['ad']})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (≥10 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("A-1 tam UYGUN (HD, nefro, Hb9.5, ferritin120)", {
            'etkin_madde': 'DARBEPOETIN', 'atc_kodu': 'B03XA02',
            'brans': 'Nefroloji', 'rapor_doktor_brans': 'Nefroloji',
            'recete_teshisleri': ['N18.5'], 'kutu': '1',
            'rapor_metni': 'hemodiyaliz hastası hemoglobin 9.5 gr/dl ferritin 120 '
                           'tsat %25 tetkik 12.05.2026',
        }, KontrolSonucu.UYGUN),
        ("A-1 UYGUN DEĞİL (Hb 13 > 12)", {
            'etkin_madde': 'EPOETIN ALFA', 'atc_kodu': 'B03XA01',
            'brans': 'Nefroloji', 'rapor_doktor_brans': 'Nefroloji',
            'recete_teshisleri': ['N18.5'],
            'rapor_metni': 'hemodiyaliz hemoglobin 13 gr/dl ferritin 200 tsat %30',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("A-1 UYGUN DEĞİL (demir yetersiz)", {
            'etkin_madde': 'EPOETIN', 'atc_kodu': 'B03XA01',
            'brans': 'Nefroloji', 'rapor_doktor_brans': 'Nefroloji',
            'recete_teshisleri': ['N18.5'],
            'rapor_metni': 'hemodiyaliz hemoglobin 9 ferritin 50 tsat %12',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("A-1 ŞARTLI (lab yok, nefro)", {
            'etkin_madde': 'DARBEPOETIN', 'atc_kodu': 'B03XA02',
            'brans': 'Nefroloji', 'rapor_doktor_brans': 'Nefroloji',
            'recete_teshisleri': ['N18.5'], 'kutu': '1',
            'rapor_metni': 'kronik böbrek yetmezliği hemodiyaliz',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("A-1 UYGUN DEĞİL (periton + iç hast.)", {
            'etkin_madde': 'EPOETIN', 'atc_kodu': 'B03XA01',
            'brans': 'İç Hastalıkları', 'rapor_doktor_brans': 'Nefroloji',
            'recete_teshisleri': ['N18.4'],
            'rapor_metni': 'periton diyaliz hemoglobin 9 ferritin 150 tsat %25',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("A-1 ŞARTLI (HD + kardiyo reçete → diyaliz sert.?)", {
            'etkin_madde': 'EPOETIN', 'atc_kodu': 'B03XA01',
            'brans': 'Kardiyoloji', 'rapor_doktor_brans': 'Nefroloji',
            'recete_teshisleri': ['N18.5'], 'kutu': '1',
            'rapor_metni': 'hemodiyaliz hemoglobin 9.5 ferritin 150 tsat %25',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("A-2 tam UYGUN (MDS, hematoloji, Hb9 blast3 epo300)", {
            'etkin_madde': 'EPOETIN ALFA', 'atc_kodu': 'B03XA01',
            'brans': 'Hematoloji', 'rapor_doktor_brans': 'Hematoloji',
            'recete_teshisleri': ['D46.9'], 'kutu': '2',
            'rapor_metni': 'myelodisplastik sendrom hemoglobin 9 blast %3 serum '
                           'eritropoietin düzeyi 300 mu/ml hemogram 10.05.2026',
        }, KontrolSonucu.UYGUN),
        ("A-2 UYGUN DEĞİL (blast %8)", {
            'etkin_madde': 'EPOETIN', 'atc_kodu': 'B03XA01',
            'brans': 'Hematoloji', 'rapor_doktor_brans': 'Hematoloji',
            'recete_teshisleri': ['D46.9'],
            'rapor_metni': 'mds hemoglobin 9 blast %8 serum eritropoietin düzeyi 300',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("A-2 UYGUN DEĞİL (serum EPO 600)", {
            'etkin_madde': 'EPOETIN', 'atc_kodu': 'B03XA01',
            'brans': 'Hematoloji', 'rapor_doktor_brans': 'Hematoloji',
            'recete_teshisleri': ['D46.9'],
            'rapor_metni': 'mds hemoglobin 9 blast %3 serum eritropoietin düzeyi 600',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("A-2 UYGUN DEĞİL (reçete kardiyoloji)", {
            'etkin_madde': 'EPOETIN', 'atc_kodu': 'B03XA01',
            'brans': 'Kardiyoloji', 'rapor_doktor_brans': 'Hematoloji',
            'recete_teshisleri': ['D46.9'],
            'rapor_metni': 'mds hemoglobin 9 blast %3 serum eritropoietin düzeyi 300',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Roksadustat + MDS → UYGUN DEĞİL", {
            'etkin_madde': 'ROKSADUSTAT', 'atc_kodu': 'B03XA05',
            'brans': 'Hematoloji', 'recete_teshisleri': ['D46.9'],
            'rapor_metni': 'myelodisplastik sendrom',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Endikasyon belirsiz → ŞÜPHELİ", {
            'etkin_madde': 'EPOETIN', 'atc_kodu': 'B03XA01',
            'brans': 'Nefroloji', 'rapor_metni': 'anemi tedavisi',
        }, KontrolSonucu.KONTROL_EDILEMEDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.9.A — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = eritropoietin_kontrol_4_2_9_a(ilac_sonuc)
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
