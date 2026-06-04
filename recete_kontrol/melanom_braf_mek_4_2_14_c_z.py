# -*- coding: utf-8 -*-
"""SUT 4.2.14.C-(z) — Dabrafenib / Trametinib / Vemurafenib / Kobimetinib.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:6093-6125`` (mevzuat.gov.tr,
MevzuatNo=17229; 4.2.14.C "Özel düzenleme yapılan ilaçlar" altında (z)
bendi). Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md
``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
DÖRT YOLAK (dispatcher: etken/ATC → yolak)
═══════════════════════════════════════════════════════════════════════════

  Y1 → Dabrafenib   (TAFINLAR, L01EC02) — a: metastatik/relaps · b: adjuvan
  Y2 → Trametinib   (MEKINIST, L01EE01) — a: metastatik/relaps · b: adjuvan
  Y3 → Kobimetinib  (COTELLIC, L01EE02) — yalnız metastatik/relaps
  Y4 → Vemurafenib  (ZELBORAF, L01EC01) — yalnız metastatik/relaps

  Endikasyon alt-dispatch (Y1/Y2): rapor lafzında "adjuvan" + "evre III" +
  "tam rezeksiyon" sinyali → b yolu (12 ay), aksi → a yolu (metastatik/relaps).

═══════════════════════════════════════════════════════════════════════════
İZİNLİ REJİMLER (madde-5 kombinasyon kuralı)
═══════════════════════════════════════════════════════════════════════════

  Dabrafenib tek · Dabrafenib+Trametinib · Vemurafenib tek · Vemurafenib+Kobimetinib

  - Trametinib ve Kobimetinib KOMBİNE ZORUNLUDUR (tek ajan ödenmez).
  - Çapraz kombinasyon (dab+vemu, trame+kobi, üçlü, vb.) ödenmez.
  - Ardışık kullanım ödenmez (geçmiş bazlı — parse edilemez → bilgi/KE).

  Kullanıcı kararı (2026-06-04): zorunlu-kombine ilaç (Y2/Y3) reçetede tek
  başına ve partneri görünmüyorsa → kombinasyon atomu YOK (UYGUN DEĞİL).

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  a) UYGUN ⇔ A1(RAF naif) ∧ A2(ECOG 0/1) ∧ A3(BRAF V600+) ∧ A4(progresyon)
            ∧ A6(relaps/metastatik melanom) ∧ R1(SK + tıbbi onkoloji heyet)
            ∧ R2(reçete tıbbi onkoloji) ∧ K(kombinasyon kuralı)
            [∧ A5 lokal tedavi · S1 süre · ardışık — bilgi, matematik dışı]

  b) UYGUN ⇔ A1(RAF naif) ∧ bA3(BRAF V600E+) ∧ bA6(Evre III melanom)
            ∧ bREZ(tam rezeksiyon takiben adjuvan) ∧ R1 ∧ R2 ∧ K
            [∧ S1 12 ay · ardışık — bilgi]

Gating atom YOK → UYGUN_DEĞİL. Yalnız KE-şartlı atom kalırsa → ŞARTLI UYGUN;
aksi (gating KE) → ŞÜPHELİ. Hepsi VAR → UYGUN. Sessizlik = örtük kabul YASAK
(CLAUDE.md §2.5).

Ana entrypoint: ``melanom_kontrol_4_2_14_c_z(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İLAÇ SINIFI listeleri (etken + ticari ad — norm_tr_upper / ASCII)
# ═══════════════════════════════════════════════════════════════════════
DABRAFENIB: set = {'DABRAFENIB', 'DABRAFENIBE', 'DABRAFENIB MESILAT', 'TAFINLAR'}
TRAMETINIB: set = {'TRAMETINIB', 'TRAMETINIBE', 'MEKINIST'}
VEMURAFENIB: set = {'VEMURAFENIB', 'VEMURAFENIBE', 'ZELBORAF'}
KOBIMETINIB: set = {'KOBIMETINIB', 'COBIMETINIB', 'KOBIMETINIB FUMARAT',
                    'COBIMETINIB FUMARAT', 'COTELLIC'}

# ATC eşlemesi (etken/ad bulunamazsa yedek)
_ATC_YOLAK = {'L01EC02': 'Y1', 'L01EE01': 'Y2', 'L01EE02': 'Y3', 'L01EC01': 'Y4'}

YOLAK_ETKEN = {'Y1': DABRAFENIB, 'Y2': TRAMETINIB,
               'Y3': KOBIMETINIB, 'Y4': VEMURAFENIB}

# ═══════════════════════════════════════════════════════════════════════
# Branş anahtarları (norm_tr_lower alt-string). SUT: "tıbbi onkoloji".
# ═══════════════════════════════════════════════════════════════════════
ONKOLOJI = ['tibbi onkoloji', 'onkoloji', 'onkolog']
PRATISYEN = ['aile hek', 'pratisyen', 'genel pratisyen']

# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar
# ═══════════════════════════════════════════════════════════════════════

def _arama_metni(ilac_sonuc: Dict) -> str:
    parcalar = [
        ilac_sonuc.get('ilac_adi') or ilac_sonuc.get('ilac') or '',
        ilac_sonuc.get('etkin_madde') or ilac_sonuc.get('etkin') or '',
    ]
    return norm_tr_upper(' '.join(p for p in parcalar if p))


def _iceriyor(metin_upper: str, kume: set) -> bool:
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
    return [h.get('brans') or '' for h in heyet
            if isinstance(h, dict) and (h.get('ad') or h.get('brans'))]


def _rapor_var(ilac_sonuc: Dict) -> bool:
    return bool((ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
                or (ilac_sonuc.get('rapor_takip_no') or '').strip()
                or (ilac_sonuc.get('rapor_turu') or '').strip()
                or _heyet_brans_listesi(ilac_sonuc))


def _diger_ilac_metni(ilac_sonuc: Dict) -> str:
    """Aynı reçetedeki diğer kalemler + eş-zamanlı yazılmış ilaç adları."""
    parcalar: List[str] = []
    ri = ilac_sonuc.get('recete_ilaclari') or ilac_sonuc.get('recete_kalemleri')
    if isinstance(ri, (list, tuple)):
        for x in ri:
            if isinstance(x, dict):
                parcalar.append(str(x.get('ad') or x.get('ilac') or ''))
            elif x:
                parcalar.append(str(x))
    for anahtar in ('diger_ilac_adlari', 'diger_ilaclar'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
            parcalar.append(str(v))
    return norm_tr_upper(' '.join(p for p in parcalar if p))


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════

def melanom_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """Kapsam içi mi + hangi yolak? → 'Y1'|'Y2'|'Y3'|'Y4'|None (ATLANDI)."""
    m = _arama_metni(ilac_sonuc)
    # ATC daha spesifik (kobimetinib/trametinib etken adı kısmen örtüşebilir
    # ama burada ad kümeleri ayrık; yine de ATC önce denenir).
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    for kod, yolak in _ATC_YOLAK.items():
        if kod in atc:
            return yolak
    for yolak, kume in YOLAK_ETKEN.items():
        if _iceriyor(m, kume):
            return yolak
    return None


def _melanom_endikasyon(ilac_sonuc: Dict) -> bool:
    """Malign melanom var mı? ICD C43* veya lafız 'malign melanom'/'melanom'."""
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'\bC43', icd):
        return True
    return 'melanom' in metin


def _adjuvan_sinyali(ilac_sonuc: Dict) -> bool:
    """b yolu (Evre III adjuvan) sinyalleri: adjuvan + evre III + rezeksiyon."""
    metin = _rapor_metni(ilac_sonuc)
    adjuvan = 'adjuvan' in metin
    evre3 = bool(re.search(r'evre\s*(iii|3)\b', metin))
    rezeksiyon = 'rezeksiyon' in metin
    return adjuvan and (evre3 or rezeksiyon)


def melanom_endikasyon_yolu(ilac_sonuc: Dict, yolak: str) -> str:
    """Y1/Y2 için 'a' (metastatik/relaps) | 'b' (adjuvan). Y3/Y4 daima 'a'."""
    if yolak in ('Y1', 'Y2') and _adjuvan_sinyali(ilac_sonuc):
        return 'b'
    return 'a'


# ═══════════════════════════════════════════════════════════════════════
# ORTAK ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

def atom_raf_naif(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A1 (NEGATİF): daha önce herhangi bir RAF yolağı inhibitörü kullanmamış."""
    metin = _rapor_metni(ilac_sonuc)
    pat_naif = re.search(r'raf[^.]{0,40}(kullanmam|kullanilmam|naif|kullanmad)', metin)
    pat_kullanildi = re.search(
        r'raf[^.]{0,40}(kullanildi|kullanmis|alt[iı]nda progres|tedavisi sonras)',
        metin)
    if pat_naif:
        return SartSonuc(ad='RAF yolağı inhibitörü kullanmamış', durum=SartDurumu.VAR,
                         neden='Raporda "RAF inhibitörü kullanmamış/naif" ibaresi',
                         kaynak='rapor_metni', grup=grup)
    if pat_kullanildi:
        return SartSonuc(ad='RAF yolağı inhibitörü kullanmamış', durum=SartDurumu.YOK,
                         neden='Raporda daha önce RAF inhibitörü kullanıldığı ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='RAF yolağı inhibitörü kullanmamış',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Daha önce RAF inhibitörü kullanımı metinden netleşmedi — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_ecog(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A2: ECOG performans skoru 0 veya 1."""
    metin = _rapor_metni(ilac_sonuc)
    if 'ecog' not in metin:
        return SartSonuc(ad='ECOG performans skoru 0-1', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Raporda ECOG skoru belirtilmemiş — manuel doğrula',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    # ECOG ... <skor>
    m = re.search(r'ecog[^0-9]{0,25}([0-4])(?:\s*[-–/veya ]{1,5}([0-4]))?', metin)
    if m:
        skorlar = [int(g) for g in m.groups() if g is not None]
        if skorlar and all(x in (0, 1) for x in skorlar):
            return SartSonuc(ad='ECOG performans skoru 0-1', durum=SartDurumu.VAR,
                             neden=f'ECOG {"-".join(str(x) for x in skorlar)}',
                             kaynak='rapor_metni', grup=grup)
        return SartSonuc(ad='ECOG performans skoru 0-1', durum=SartDurumu.YOK,
                         neden=f'ECOG {"-".join(str(x) for x in skorlar)} — 0/1 dışında',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='ECOG performans skoru 0-1', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='ECOG geçiyor ama skor değeri okunamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_braf_v600(ilac_sonuc: Dict, grup: str, e_zorunlu: bool = False) -> SartSonuc:
    """A3: BRAF V600 mutasyonu pozitif. e_zorunlu=True ise V600E (b yolu)."""
    metin = _rapor_metni(ilac_sonuc)
    var_v600 = bool(re.search(r'braf[^.]{0,15}v\s*600', metin)) or 'v600' in metin
    var_v600e = bool(re.search(r'v\s*600\s*e', metin))
    neg = bool(re.search(r'braf[^.]{0,25}(negatif|saptanmad|wild|yaban)', metin))
    ad = 'BRAF V600E mutasyonu pozitif' if e_zorunlu else 'BRAF V600 mutasyonu pozitif'
    if neg:
        return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                         neden='Raporda BRAF mutasyonu negatif/wild-tip ibaresi',
                         kaynak='rapor_metni', grup=grup)
    if e_zorunlu:
        if var_v600e:
            return SartSonuc(ad=ad, durum=SartDurumu.VAR, neden='Raporda BRAF V600E pozitif',
                             kaynak='rapor_metni', grup=grup)
        if var_v600:
            return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                             neden='BRAF V600 var ama spesifik "E" alt-tipi netleşmedi — manuel',
                             kaynak='rapor_metni', grup=grup, sartli_atom=True)
    elif var_v600:
        return SartSonuc(ad=ad, durum=SartDurumu.VAR, neden='Raporda BRAF V600 pozitif',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Raporda BRAF V600 mutasyon durumu belirtilmemiş — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_progresyon(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A4: lokal tedaviler sonrası progresyon göstermiş."""
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'progres', metin):
        return SartSonuc(ad='Lokal tedavi sonrası progresyon', durum=SartDurumu.VAR,
                         neden='Raporda progresyon ibaresi', kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Lokal tedavi sonrası progresyon',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Raporda progresyon ibaresi bulunamadı — manuel doğrula',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_lokal_tedavi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A5 (bilgi): lokal tedavilerin tekrar kullanılamadığı."""
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'lokal tedav[^.]{0,40}(tekrar|uygulanam|kullanilam)', metin):
        return SartSonuc(ad='Lokal tedavi tekrar kullanılamıyor', durum=SartDurumu.VAR,
                         neden='Raporda lokal tedavi tekrarlanamadığı ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Lokal tedavi tekrar kullanılamıyor',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Lokal tedavi tekrar kullanılamadığı metinden netleşmedi — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_endikasyon_a(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """A6 (a yolu): relaps / metastatik malign melanom."""
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    melanom = _melanom_endikasyon(ilac_sonuc)
    metastatik = bool(re.search(r'metastat|relaps|evre\s*(iv|4)\b|nuks', metin))
    if not melanom:
        return SartSonuc(ad='Relaps/metastatik malign melanom', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Teşhis/raporda malign melanom (C43) bulunamadı — manuel',
                         kaynak='ICD+rapor', grup=grup, sartli_atom=True)
    if metastatik:
        return SartSonuc(ad='Relaps/metastatik malign melanom', durum=SartDurumu.VAR,
                         neden='Malign melanom + metastatik/relaps ibaresi',
                         kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad='Relaps/metastatik malign melanom', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Malign melanom var ama relaps/metastatik evre netleşmedi — manuel',
                     kaynak='ICD+rapor', grup=grup, sartli_atom=True)


def atom_endikasyon_b_evre3(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """bA6 (b yolu): Evre III malign melanom."""
    metin = _rapor_metni(ilac_sonuc)
    melanom = _melanom_endikasyon(ilac_sonuc)
    evre3 = bool(re.search(r'evre\s*(iii|3)\b', metin))
    if not melanom:
        return SartSonuc(ad='Evre III malign melanom', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Teşhis/raporda malign melanom bulunamadı — manuel',
                         kaynak='ICD+rapor', grup=grup, sartli_atom=True)
    if evre3:
        return SartSonuc(ad='Evre III malign melanom', durum=SartDurumu.VAR,
                         neden='Malign melanom + Evre III ibaresi',
                         kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad='Evre III malign melanom', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Malign melanom var ama Evre III netleşmedi — manuel',
                     kaynak='ICD+rapor', grup=grup, sartli_atom=True)


def atom_rezeksiyon_adjuvan(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """bREZ (b yolu): tam rezeksiyon takiben adjuvan tedavi."""
    metin = _rapor_metni(ilac_sonuc)
    rezeksiyon = 'rezeksiyon' in metin
    adjuvan = 'adjuvan' in metin
    if rezeksiyon and adjuvan:
        return SartSonuc(ad='Tam rezeksiyon takiben adjuvan tedavi', durum=SartDurumu.VAR,
                         neden='Raporda tam rezeksiyon + adjuvan ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Tam rezeksiyon takiben adjuvan tedavi',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Tam rezeksiyon/adjuvan tedavi metinden tam doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_sk_onkoloji(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """R1: tıbbi onkoloji uzmanının yer aldığı sağlık kurulu raporu."""
    rapor_turu = norm_tr_lower(ilac_sonuc.get('rapor_turu') or '')
    heyet_branslar = _heyet_brans_listesi(ilac_sonuc)
    heyet_n = len(heyet_branslar)
    onkoloji_heyette = any(_brans_listede(b, ONKOLOJI) for b in heyet_branslar)
    kurul_isaret = ('kurul' in rapor_turu) or (heyet_n >= 2)
    uzman_tek = ('uzman hekim' in rapor_turu) and 'kurul' not in rapor_turu
    rapor_var = _rapor_var(ilac_sonuc)

    if kurul_isaret and onkoloji_heyette:
        return SartSonuc(ad='SK raporu + tıbbi onkoloji uzmanı', durum=SartDurumu.VAR,
                         neden=f'Sağlık kurulu raporu, heyette tıbbi onkoloji (heyet {heyet_n})',
                         kaynak='rapor_turu+heyet', grup=grup)
    if uzman_tek:
        return SartSonuc(ad='SK raporu + tıbbi onkoloji uzmanı', durum=SartDurumu.YOK,
                         neden='Rapor türü "uzman hekim" — SUT sağlık kurulu raporu ister',
                         kaynak='rapor_turu+heyet', grup=grup)
    if not rapor_var:
        return SartSonuc(ad='SK raporu + tıbbi onkoloji uzmanı', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor bulunamadı',
                         kaynak='rapor', grup=grup)
    if kurul_isaret and not heyet_branslar:
        return SartSonuc(ad='SK raporu + tıbbi onkoloji uzmanı',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Sağlık kurulu raporu var ama heyet branşları okunamadı — '
                               'tıbbi onkoloji üyesi manuel doğrula',
                         kaynak='rapor_turu+heyet', grup=grup, sartli_atom=True)
    if kurul_isaret and heyet_branslar and not onkoloji_heyette:
        return SartSonuc(ad='SK raporu + tıbbi onkoloji uzmanı', durum=SartDurumu.YOK,
                         neden='Sağlık kurulu heyetinde tıbbi onkoloji uzmanı yok',
                         kaynak='rapor_turu+heyet', grup=grup)
    return SartSonuc(ad='SK raporu + tıbbi onkoloji uzmanı',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama sağlık kurulu / tıbbi onkoloji heyeti '
                           'doğrulanamadı — manuel', kaynak='rapor_turu+heyet',
                     grup=grup, sartli_atom=True)


def atom_recete_onkoloji(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """R2: tıbbi onkoloji uzman hekimince reçete edilmesi."""
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden tıbbi onkoloji uzmanı',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, ONKOLOJI):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Tıbbi onkoloji uzmanı reçete edebilir',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Tıbbi onkoloji uzmanı değil — SUT yalnız tıbbi onkoloji ister',
                     kaynak='hekim_brans', grup=grup)


def atom_kombinasyon(ilac_sonuc: Dict, yolak: str, grup: str) -> SartSonuc:
    """K (madde 5): ilaca özgü izinli kombinasyon kuralı.

    İzinli: dabrafenib tek/+trametinib · vemurafenib tek/+kobimetinib ·
    trametinib YALNIZ +dabrafenib · kobimetinib YALNIZ +vemurafenib.
    """
    diger = _diger_ilac_metni(ilac_sonuc)
    has_dab = _iceriyor(diger, DABRAFENIB)
    has_trame = _iceriyor(diger, TRAMETINIB)
    has_vemu = _iceriyor(diger, VEMURAFENIB)
    has_kobi = _iceriyor(diger, KOBIMETINIB)
    ad = 'Kombinasyon kuralı'

    if yolak == 'Y1':  # Dabrafenib: tek ajan veya +trametinib
        if has_vemu or has_kobi:
            return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                             neden='Dabrafenib + vemurafenib/kobimetinib — tanımlı dışı kombinasyon (ödenmez)',
                             kaynak='recete_kalemleri', grup=grup)
        neden = ('Dabrafenib + trametinib (izinli kombinasyon)' if has_trame
                 else 'Dabrafenib tek ajan (izinli)')
        return SartSonuc(ad=ad, durum=SartDurumu.VAR, neden=neden,
                         kaynak='recete_kalemleri', grup=grup)

    if yolak == 'Y4':  # Vemurafenib: tek ajan veya +kobimetinib
        if has_dab or has_trame:
            return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                             neden='Vemurafenib + dabrafenib/trametinib — tanımlı dışı kombinasyon (ödenmez)',
                             kaynak='recete_kalemleri', grup=grup)
        neden = ('Vemurafenib + kobimetinib (izinli kombinasyon)' if has_kobi
                 else 'Vemurafenib tek ajan (izinli)')
        return SartSonuc(ad=ad, durum=SartDurumu.VAR, neden=neden,
                         kaynak='recete_kalemleri', grup=grup)

    if yolak == 'Y2':  # Trametinib: YALNIZ +dabrafenib (kombine zorunlu)
        if has_vemu or has_kobi:
            return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                             neden='Trametinib + vemurafenib/kobimetinib — tanımlı dışı kombinasyon (ödenmez)',
                             kaynak='recete_kalemleri', grup=grup)
        if has_dab:
            return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                             neden='Trametinib + dabrafenib (izinli kombinasyon)',
                             kaynak='recete_kalemleri', grup=grup)
        return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                         neden='Trametinib dabrafenib ile kombine zorunlu — reçetede dabrafenib yok',
                         kaynak='recete_kalemleri', grup=grup)

    # yolak == 'Y3' Kobimetinib: YALNIZ +vemurafenib (kombine zorunlu)
    if has_dab or has_trame:
        return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                         neden='Kobimetinib + dabrafenib/trametinib — tanımlı dışı kombinasyon (ödenmez)',
                         kaynak='recete_kalemleri', grup=grup)
    if has_vemu:
        return SartSonuc(ad=ad, durum=SartDurumu.VAR,
                         neden='Kobimetinib + vemurafenib (izinli kombinasyon)',
                         kaynak='recete_kalemleri', grup=grup)
    return SartSonuc(ad=ad, durum=SartDurumu.YOK,
                     neden='Kobimetinib vemurafenib ile kombine zorunlu — reçetede vemurafenib yok',
                     kaynak='recete_kalemleri', grup=grup)


def atom_sure_bilgi(ilac_sonuc: Dict, yolak: str, yol: str) -> SartSonuc:
    """S1 (bilgi): SK ≤6 ay; a→progresyona kadar, b→en fazla 12 ay."""
    sure = 'en fazla 12 ay (adjuvan)' if yol == 'b' else 'progresyona kadar'
    return SartSonuc(ad=f'Tedavi süresi ({sure}) + SK ≤6 ay',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='SK raporu ≤6 ay ve tedavi süresi metinden doğrulanamadı — manuel',
                     kaynak='rapor', grup='(z) Süre (bilgi)', sartli_atom=True)


def atom_ardisik_bilgi(ilac_sonuc: Dict) -> SartSonuc:
    """Madde-5 (bilgi): ardışık kullanım ödenmez (geçmiş bazlı — parse edilemez)."""
    return SartSonuc(ad='Ardışık kullanım yapılmamış',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Bu grup ilaçların ardışık kullanımı ödenmez — hasta geçmişi '
                           'manuel doğrulanmalı',
                     kaynak='hasta_gecmisi', grup='(z) Ardışık kullanım (bilgi)',
                     sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# YOLAK BAZLI ŞART ÜRETİMİ
# ═══════════════════════════════════════════════════════════════════════

def _yolak_a_sartlari(ilac_sonuc: Dict, yolak: str) -> List[SartSonuc]:
    """a yolu — metastatik/relaps malign melanom (tüm 4 ilaç)."""
    return [
        atom_raf_naif(ilac_sonuc, '(z) RAF inhibitörü kullanmamış'),
        atom_ecog(ilac_sonuc, '(z) ECOG 0-1'),
        atom_braf_v600(ilac_sonuc, '(z) BRAF V600 pozitif'),
        atom_progresyon(ilac_sonuc, '(z) Progresyon'),
        atom_lokal_tedavi(ilac_sonuc, '(z) Lokal tedavi (bilgi)'),
        atom_endikasyon_a(ilac_sonuc, '(z) Endikasyon (relaps/metastatik melanom)'),
        atom_sk_onkoloji(ilac_sonuc, '(z) SK raporu + tıbbi onkoloji heyet'),
        atom_recete_onkoloji(ilac_sonuc, '(z) Reçete: tıbbi onkoloji'),
        atom_kombinasyon(ilac_sonuc, yolak, '(z) Kombinasyon kuralı'),
        atom_sure_bilgi(ilac_sonuc, yolak, 'a'),
        atom_ardisik_bilgi(ilac_sonuc),
    ]


def _yolak_b_sartlari(ilac_sonuc: Dict, yolak: str) -> List[SartSonuc]:
    """b yolu — Evre III adjuvan (yalnız Y1/Y2)."""
    return [
        atom_raf_naif(ilac_sonuc, '(z) RAF inhibitörü kullanmamış'),
        atom_braf_v600(ilac_sonuc, '(z) BRAF V600E pozitif', e_zorunlu=True),
        atom_endikasyon_b_evre3(ilac_sonuc, '(z) Endikasyon (Evre III melanom)'),
        atom_rezeksiyon_adjuvan(ilac_sonuc, '(z) Tam rezeksiyon + adjuvan'),
        atom_sk_onkoloji(ilac_sonuc, '(z) SK raporu + tıbbi onkoloji heyet'),
        atom_recete_onkoloji(ilac_sonuc, '(z) Reçete: tıbbi onkoloji'),
        atom_kombinasyon(ilac_sonuc, yolak, '(z) Kombinasyon kuralı'),
        atom_sure_bilgi(ilac_sonuc, yolak, 'b'),
        atom_ardisik_bilgi(ilac_sonuc),
    ]


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (parkinson/aprepitant kalıbı — grup bazlı)
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


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

YOLAK_METADATA = {
    'Y1': {'ad': 'Dabrafenib', 'etken': 'dabrafenib'},
    'Y2': {'ad': 'Trametinib', 'etken': 'trametinib'},
    'Y3': {'ad': 'Kobimetinib', 'etken': 'kobimetinib'},
    'Y4': {'ad': 'Vemurafenib', 'etken': 'vemurafenib'},
}


def _mesaj_uret(sonuc: KontrolSonucu, yolak: str, yol: str,
                sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    ad = YOLAK_METADATA.get(yolak, {}).get('ad', yolak)
    yol_ad = 'Evre III adjuvan' if yol == 'b' else 'metastatik/relaps'
    parcalar = [f"SUT 4.2.14.C-(z) / {ad} ({yol_ad})"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — tüm şartlar sağlandı")
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f"ŞARTLI UYGUN — hesaplanabilir şartlar VAR; "
                        f"{len(ke)} şart manuel doğrulama gerektiriyor")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append("UYGUN DEĞİL — " + '; '.join(s.ad + ': ' + s.neden
                                                     for s in yok[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f"ŞÜPHELİ — {len(ke)} şart kontrol edilemedi")
    return ' | '.join(parcalar)


def melanom_kontrol_4_2_14_c_z(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.14.C-(z) ana kontrol fonksiyonu (BRAF/MEK inhibitörleri)."""
    yolak = melanom_yolak_belirle(ilac_sonuc)
    if yolak is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.14.C-(z) kapsamı dışı — dabrafenib/trametinib/'
                  'vemurafenib/kobimetinib değil',
            sut_kurali='SUT 4.2.14.C-(z)')

    yol = melanom_endikasyon_yolu(ilac_sonuc, yolak)
    sartlar = (_yolak_b_sartlari(ilac_sonuc, yolak) if yol == 'b'
               else _yolak_a_sartlari(ilac_sonuc, yolak))
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, yol, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali='SUT 4.2.14.C-(z)',
        sartlar=sartlar,
        detaylar={'yolak': yolak, 'yolak_ad': YOLAK_METADATA[yolak]['ad'],
                  'endikasyon_yolu': yol})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    SK_ONK = [{'ad': 'Dr. A', 'brans': 'Tıbbi Onkoloji'},
              {'ad': 'Dr. B', 'brans': 'Genel Cerrahi'},
              {'ad': 'Dr. C', 'brans': 'Patoloji'}]
    SK_NO_ONK = [{'ad': 'Dr. A', 'brans': 'Dermatoloji'},
                 {'ad': 'Dr. B', 'brans': 'Genel Cerrahi'}]
    rapor_a_tam = ('braf v600 pozitif ecog 0 lokal tedaviler sonrasi progresyon '
                   'gosterilmis lokal tedaviler tekrar kullanilamadi raf inhibitoru '
                   'kullanmamis metastatik malign melanom')
    return [
        # ── Y1 Dabrafenib a yolu ──
        ("Y1 UYGUN (dabrafenib tek, tam rapor, SK onkoloji, onkoloji reçete)", {
            'etkin_madde': 'DABRAFENIB', 'atc_kodu': 'L01EC02',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN (dabrafenib + trametinib kombi)", {
            'etkin_madde': 'DABRAFENIB', 'atc_kodu': 'L01EC02',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
            'recete_ilaclari': [{'ad': 'MEKINIST 2 MG'}],
        }, KontrolSonucu.UYGUN),
        ("Y1 UYGUN DEĞİL (dabrafenib + vemurafenib — çapraz kombi)", {
            'etkin_madde': 'DABRAFENIB', 'atc_kodu': 'L01EC02',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
            'recete_ilaclari': [{'ad': 'ZELBORAF 240 MG'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 UYGUN DEĞİL (reçete eden dermatoloji)", {
            'etkin_madde': 'DABRAFENIB', 'atc_kodu': 'L01EC02',
            'brans': 'Dermatoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 UYGUN DEĞİL (heyette onkoloji yok)", {
            'etkin_madde': 'DABRAFENIB', 'atc_kodu': 'L01EC02',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_NO_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 ŞARTLI (rapor metni eksik — KE şartlı, gating VAR)", {
            'etkin_madde': 'DABRAFENIB', 'atc_kodu': 'L01EC02',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': 'malign melanom',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Y1 UYGUN DEĞİL (ECOG 3)", {
            'etkin_madde': 'DABRAFENIB', 'atc_kodu': 'L01EC02',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam.replace('ecog 0', 'ecog 3'),
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y1 UYGUN DEĞİL (rapor yok)", {
            'etkin_madde': 'DABRAFENIB', 'atc_kodu': 'L01EC02',
            'brans': 'Tıbbi Onkoloji', 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Y2 Trametinib (kombine zorunlu) ──
        ("Y2 UYGUN DEĞİL (trametinib tek başına — kombi zorunlu)", {
            'etkin_madde': 'TRAMETINIB', 'atc_kodu': 'L01EE01',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y2 UYGUN (trametinib + dabrafenib)", {
            'etkin_madde': 'TRAMETINIB', 'atc_kodu': 'L01EE01',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
            'recete_ilaclari': [{'ad': 'TAFINLAR 75 MG'}],
        }, KontrolSonucu.UYGUN),
        # ── Y3 Kobimetinib (kombine zorunlu) ──
        ("Y3 UYGUN (kobimetinib + vemurafenib)", {
            'etkin_madde': 'KOBIMETINIB', 'atc_kodu': 'L01EE02',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
            'recete_ilaclari': [{'ad': 'ZELBORAF 240 MG'}],
        }, KontrolSonucu.UYGUN),
        ("Y3 UYGUN DEĞİL (kobimetinib tek başına)", {
            'etkin_madde': 'KOBIMETINIB', 'atc_kodu': 'L01EE02',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Y4 Vemurafenib ──
        ("Y4 UYGUN (vemurafenib tek)", {
            'etkin_madde': 'VEMURAFENIB', 'atc_kodu': 'L01EC01',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam,
        }, KontrolSonucu.UYGUN),
        # ── Y1 b yolu (adjuvan) ──
        ("Y1-b UYGUN (adjuvan evre III + dabrafenib/trametinib)", {
            'etkin_madde': 'DABRAFENIB', 'atc_kodu': 'L01EC02',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': ('braf v600e pozitif evre iii malign melanom tam rezeksiyon '
                            'takiben adjuvan tedavi raf inhibitoru kullanmamis'),
            'recete_ilaclari': [{'ad': 'MEKINIST 2 MG'}],
        }, KontrolSonucu.UYGUN),
        ("Y4-b yok (vemurafenib adjuvan sinyali olsa da a yolu kalır, tek ajan UYGUN)", {
            'etkin_madde': 'VEMURAFENIB', 'atc_kodu': 'L01EC01',
            'brans': 'Tıbbi Onkoloji', 'rapor_turu': 'Sağlık Kurulu Raporu',
            'heyet_doktorlari': SK_ONK, 'recete_teshisleri': ['C43.9'],
            'rapor_metni': rapor_a_tam + ' adjuvan evre iii',
        }, KontrolSonucu.UYGUN),
        # ── Kapsam dışı ──
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.14.C-(z) — Melanom BRAF/MEK — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = melanom_kontrol_4_2_14_c_z(ilac_sonuc)
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
