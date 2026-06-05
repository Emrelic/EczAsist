# -*- coding: utf-8 -*-
"""SUT 4.2.14.C-(çç) — Ruksolitinib (JAKAVI).

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:6165-6197`` (mevzuat.gov.tr,
MevzuatNo=17229; Ek:RG-18/6/2016, Değişik:RG-19/10/2023-32344).
Protokol metodolojisi: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md
``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

İlaç: ruksolitinib = JAKAVI (oral, ATC L01EJ01 / eski L01XE18). Topikal
ruksolitinib (OPZELURA, D11AH09 — vitiligo/dermatit) bu madde kapsamı DIŞI.

═══════════════════════════════════════════════════════════════════════════
ÜÇ ENDİKASYON YOLAKLI DİSPATCHER
═══════════════════════════════════════════════════════════════════════════

  Y_MF   → Miyelofibrozis (Madde 1 başlangıç + Madde 2 devam)
           primer MF ∨ post-polisitemik MF ∨ ET sonrası ikincil MF
  Y_GVHD → Graft versus Host (Madde 3)
           aGvHD derece 2-4 ∨ orta-ağır kGvHD, ≥12 yaş
  Y_PV   → Polisitemi Vera (Madde 4 başlangıç + Madde 5 devam)
           JAK2 (V617F/Exon 12) mutasyonu + HÜ yanıtsızlık durumu

  Dispatcher sinyali (öncelik): GvHD ibaresi > miyelofibroz ibaresi >
  polisitemi vera/JAK2 ibaresi. Hiçbiri net değilse → Y_MF varsayılır
  (kullanıcı kararı 2026-06-05) + ``dispatcher_belirsiz`` notu.

  Başla/Devam ayrımı (kullanıcı kararı 2026-06-05): EOS RaporAna
  ordinalitesi (``recete_tipi_eos_bazli``). İlk rapor → BAŞLANGIÇ; 2.+ →
  DEVAM. DEVAM modunda ilgili yanıt-değerlendirme (Madde 2/5 ya da
  14g/6ay) bir (bilgi) atomu olarak eklenir; başlangıç şartları yine
  görünür kalır (örtük kabul yasak).

═══════════════════════════════════════════════════════════════════════════
ORTAK KAPI — Madde 6 (tüm yolaklara uygulanır)
═══════════════════════════════════════════════════════════════════════════
  R1 SK raporu VAR ∧ R2 heyette ≥1 hematoloji uzmanı ∧ R4 reçete eden
  hematoloji uzman hekimi   [R3 3.basamak (bilgi) · R5 3 ay rapor (bilgi)]

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════
  GATE        ⇔ R1 ∧ R2 ∧ R4                [R3, R5 = bilgi → KE kalırsa ŞARTLI]
  Y_MF_UYGUN  ⇔ (M_T1∨M_T2∨M_T3) ∧ M_a ∧ M_b ∧ M_c
                ∧ (M_ç1∧M_ç2∧M_ç3∧M_ç4) ∧ M_d ∧ GATE
  Y_GVHD_UYGUN⇔ GV_endikasyon ∧ GV_yetersiz ∧ GV_yas ∧ GATE
  Y_PV_UYGUN  ⇔ PV_tani ∧ PV_jak2 ∧ (PV_1∨PV_2∨PV_3) ∧ GATE

Klinik/lab atomların çoğu rapor metninden parse edilemez → KE → ŞARTLI
UYGUN (eczacı manuel doğrular). Sessizlik örtük kabul edilmez (CLAUDE.md §2.5).

Ana entrypoint: ``ruksolitinib_kontrol_4_2_14_cc(ilac_sonuc)`` → KontrolRaporu.
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
RUKSOLITINIB_ETKEN: Set[str] = {'RUKSOLITINIB', 'RUXOLITINIB', 'RUKSOLITINIP'}
RUKSOLITINIB_TICARI: Set[str] = {'JAKAVI'}
ATC_RUKSOLITINIB = 'L01EJ01'        # güncel
ATC_RUKSOLITINIB_ESKI = 'L01XE18'   # eski kodlama
ATC_TOPIKAL = 'D11AH09'             # OPZELURA — kapsam DIŞI

# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower alt-string)
# ═══════════════════════════════════════════════════════════════════════
HEMATOLOJI = ['hematoloji']  # pediatrik hematoloji de 'hematoloji' içerir


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
    """Rapor + reçete açıklama birleşik metni (norm_tr_lower — regex için)."""
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


def _recete_aciklama_metni(ilac_sonuc: Dict) -> str:
    parcalar: List[str] = []
    for anahtar in ('recete_aciklamalari', 'rapor_aciklamalari'):
        v = ilac_sonuc.get(anahtar)
        if isinstance(v, (list, tuple)):
            parcalar.extend(str(x) for x in v if x)
        elif v:
            parcalar.append(str(v))
    for anahtar in ('mesaj_metni', 'rec_ack'):
        v = ilac_sonuc.get(anahtar)
        if v:
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


def _brans_listede(brans: Optional[str], anahtarlar: List[str]) -> bool:
    bl = _brans_l(brans)
    return bool(bl) and any(a in bl for a in anahtarlar)


def _heyet_brans_listesi(ilac_sonuc: Dict) -> List[str]:
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not isinstance(heyet, (list, tuple)):
        return []
    return [h.get('brans') or '' for h in heyet if (h.get('ad') or h.get('brans'))]


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


# SUT-anlatı (eşik/mevzuat) işaretleri — yakındaki sayı hastanın ölçümü
# değil mevzuat eşiğidir → atla (eritropoietin _lab_deger ile aynı disiplin).
_NARRATIVE = ("hedef", "altind", "ustun", "uzerin", "ulasi", "asinc", "asan",
              "arasi", "gelinc", "gecinc", "kesil", "baslan", "tutab", "saglan",
              "'in", "'nin", "'nın", "'yi", "'ye", "'ya", "'a ", "olmasi",
              "referans")


def _lab_deger(metin: str, anahtarlar: List[str]) -> Optional[float]:
    """Rapor metninde anahtar yakınındaki ilk ölçüm değeri. SUT-anlatı atlanır."""
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


def ruksolitinib_kapsami_mi(ilac_sonuc: Dict) -> bool:
    """JAKAVI / ruksolitinib (oral, L01EJ01/L01XE18) mı? Topikal hariç."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_TOPIKAL):
        return False  # OPZELURA topikal — kapsam dışı
    if atc.startswith(ATC_RUKSOLITINIB) or atc.startswith(ATC_RUKSOLITINIB_ESKI):
        return True
    m = _arama_metni(ilac_sonuc)
    return _iceriyor(m, RUKSOLITINIB_ETKEN) or _iceriyor(m, RUKSOLITINIB_TICARI)


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER — endikasyon yolağı
# ═══════════════════════════════════════════════════════════════════════

def ruksolitinib_yolak_belirle(ilac_sonuc: Dict) -> Optional[Tuple[str, bool]]:
    """Kapsam içi mi + hangi yolak? → ('Y_MF'|'Y_GVHD'|'Y_PV', belirsiz) | None.

    belirsiz=True → hiçbir net sinyal yok, Y_MF varsayıldı (kullanıcı kararı).
    """
    if not ruksolitinib_kapsami_mi(ilac_sonuc):
        return None
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)

    # GvHD sinyalleri (en spesifik — önce)
    gvhd = (bool(re.search(r'\bD89\.?81', icd) or re.search(r'\bT86\.?0', icd))
            or any(k in metin for k in (
                'graft versus host', 'graft-versus-host', 'greft versus',
                'gvhd', 'agvhd', 'kgvhd', 'akut graft', 'kronik graft')))
    if gvhd:
        return ('Y_GVHD', False)

    # Miyelofibrozis (post-PV/post-ET MF de buraya — "miyelofibroz" anahtar)
    mf = (bool(re.search(r'\bD47\.?[134]', icd) or re.search(r'\bD75\.?81', icd))
          or any(k in metin for k in (
              'miyelofibroz', 'myelofibroz', 'miyelofibrozis', 'osteomyelofibroz',
              'primer miyelofibroz', 'post polisitemik', 'post-polisitemik',
              'esansiyel trombositemi sonrasi', 'idyopatik miyelofibroz')))
    if mf:
        return ('Y_MF', False)

    # Polisitemi Vera
    pv = (bool(re.search(r'\bD45\b', icd))
          or any(k in metin for k in (
              'polisitemi vera', 'polistemi vera', 'polisitemia vera',
              'jak2', 'jak 2', 'v617f', 'exon 12', 'exon12')))
    if pv:
        return ('Y_PV', False)

    # Hiçbir net sinyal yok → Y_MF varsayımı (kullanıcı kararı 2026-06-05)
    return ('Y_MF', True)


# ═══════════════════════════════════════════════════════════════════════
# BAŞLANGIÇ / DEVAM dispatcher (EOS ordinalitesi)
# ═══════════════════════════════════════════════════════════════════════

def _ruksolitinib_eos_keywords() -> Tuple[str, ...]:
    return tuple(sorted(RUKSOLITINIB_ETKEN | RUKSOLITINIB_TICARI))


def ruksolitinib_recete_tipi(ilac_sonuc: Dict) -> Tuple[str, str]:
    """BAŞLANGIÇ mi DEVAM mı? → ('BASLANGIC'|'DEVAM', gerekçe).

    Sinyal: 1) EOS RaporAna ordinalitesi (recete_tipi_eos_bazli) —
    ilk rapor BAŞLANGIÇ, 2.+ DEVAM. 2) açıklamada "devam/idame". 3) belirsiz
    → BAŞLANGIÇ (tüm başlangıç şartları görünür kalsın).
    """
    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    aktif_takip = (ilac_sonuc.get('rapor_takip_no')
                   or ilac_sonuc.get('rap_tak_no') or '').strip()
    if hasta_tc:
        try:
            from recete_kontrol.baslangic_rapor_bulucu import recete_tipi_eos_bazli
            tip, gerekce, _detay = recete_tipi_eos_bazli(
                hasta_tc, _ruksolitinib_eos_keywords(),
                aktif_rapor_takip_no=aktif_takip or None)
            if tip == 'BASLANGIC':
                return ('BASLANGIC', f'EOS: {gerekce}')
            if tip == 'DEVAM':
                return ('DEVAM', f'EOS: {gerekce}')
        except Exception:  # pragma: no cover - EOS yoksa
            pass
    ack = _recete_aciklama_metni(ilac_sonuc)
    if re.search(r'\bdevam\b', ack) or 'idame' in ack:
        return ('DEVAM', 'Reçete/rapor açıklamasında "devam/idame" ibaresi')
    return ('BASLANGIC', 'EOS\'ta geçmiş rapor yok ve "devam" ibaresi yok — '
                         'başlangıç varsayıldı (manuel doğrula)')


# ═══════════════════════════════════════════════════════════════════════
# ORTAK KAPI ATOMLARI (Madde 6)
# ═══════════════════════════════════════════════════════════════════════

GRUP_SK = '(6) Sağlık kurulu raporu'
GRUP_HEYET = '(6) Heyette hematoloji uzmanı'
GRUP_RECETE = '(6) Reçete eden hematoloji uzmanı'
GRUP_BASAMAK = '(6) 3. basamak sağlık hizmeti (bilgi)'
GRUP_SURE = '(6) Rapor süresi 3 ay (bilgi)'


def atom_sk_raporu(ilac_sonuc: Dict) -> SartSonuc:
    """R1: rapor bir SAĞLIK KURULU raporu olmalı (kanser_gcsf disiplini)."""
    rapor_turu = norm_tr_lower(ilac_sonuc.get('rapor_turu') or
                               ilac_sonuc.get('rapor_turu_adi') or '')
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    heyet_n = len([h for h in heyet if (h.get('ad') or h.get('brans'))]) \
        if isinstance(heyet, (list, tuple)) else 0
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or
                   ilac_sonuc.get('rap_tak_no') or '').strip()
    kurul_isaret = ('kurul' in rapor_turu) or (heyet_n >= 2)
    uzman_tek = ('uzman' in rapor_turu) and ('kurul' not in rapor_turu)
    rapor_var = bool(rapor_kodu or rapor_takip or rapor_turu or heyet_n)
    if kurul_isaret:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
                         neden=f"Sağlık kurulu raporu "
                               f"({rapor_turu or 'heyet ' + str(heyet_n) + ' uzman'})",
                         kaynak='rapor_turu+heyet', grup=GRUP_SK)
    if uzman_tek and heyet_n <= 1:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Rapor "uzman hekim raporu" — Madde 6 sağlık kurulu '
                               'raporu ister (heyet ≤1)',
                         kaynak='rapor_turu+heyet', grup=GRUP_SK)
    if not rapor_var:
        return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı rapor yok — Madde 6 SK raporu zorunlu',
                         kaynak='rapor', grup=GRUP_SK)
    return SartSonuc(ad='Sağlık kurulu raporu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama türü/heyeti sağlık kurulu olarak '
                           'doğrulanamadı — manuel kontrol',
                     kaynak='rapor_turu+heyet', grup=GRUP_SK, sartli_atom=True)


def atom_heyet_hematoloji(ilac_sonuc: Dict) -> SartSonuc:
    """R2: heyette ≥1 hematoloji uzmanı."""
    heyet = _heyet_brans_listesi(ilac_sonuc)
    if not heyet:
        return SartSonuc(ad='Heyette hematoloji uzmanı', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor heyeti bilgisi yok — manuel doğrula',
                         kaynak='heyet', grup=GRUP_HEYET, sartli_atom=True)
    if any(_brans_listede(b, HEMATOLOJI) for b in heyet):
        return SartSonuc(ad='Heyette hematoloji uzmanı', durum=SartDurumu.VAR,
                         neden='Heyette hematoloji uzmanı bulundu',
                         kaynak='heyet', grup=GRUP_HEYET)
    return SartSonuc(ad='Heyette hematoloji uzmanı', durum=SartDurumu.YOK,
                     neden=f"Heyette hematoloji uzmanı yok (heyet: {', '.join(heyet)})",
                     kaynak='heyet', grup=GRUP_HEYET)


def atom_recete_hematoloji(ilac_sonuc: Dict) -> SartSonuc:
    """R4: reçete eden hematoloji uzman hekimi."""
    brans = (ilac_sonuc.get('doktor_uzmanligi') or ilac_sonuc.get('brans') or '')
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden hematoloji uzmanı', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_RECETE, sartli_atom=True)
    if _brans_listede(brans, HEMATOLOJI):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Hematoloji uzmanı — yetkili',
                         kaynak='hekim_brans', grup=GRUP_RECETE)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Madde 6: yalnız hematoloji uzman hekimi reçete edebilir',
                     kaynak='hekim_brans', grup=GRUP_RECETE)


def atom_ucuncu_basamak(ilac_sonuc: Dict) -> SartSonuc:
    """R3 (bilgi): 3. basamak resmi sağlık hizmeti sunucusu."""
    metin = _rapor_metni(ilac_sonuc)
    tesis = norm_tr_lower(ilac_sonuc.get('tesis_adi') or ilac_sonuc.get('hastane') or '')
    isaret = ('3. basamak' in metin or '3.basamak' in metin or
              'ucuncu basamak' in metin or 'uciuncu basamak' in metin or
              'egitim ve arastirma' in tesis or 'universite' in tesis or
              'sehir hastane' in tesis)
    if isaret:
        return SartSonuc(ad='3. basamak sağlık hizmeti sunucusu', durum=SartDurumu.VAR,
                         neden='3. basamak ibaresi/tesis bulundu',
                         kaynak='rapor+tesis', grup=GRUP_BASAMAK)
    return SartSonuc(ad='3. basamak sağlık hizmeti sunucusu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='3. basamak (üniversite/eğitim-araştırma/şehir hast.) '
                           'doğrulanamadı — manuel', kaynak='rapor+tesis',
                     grup=GRUP_BASAMAK, sartli_atom=True)


def atom_rapor_suresi_3ay(ilac_sonuc: Dict) -> SartSonuc:
    """R5 (bilgi): 3 ay süreli rapor."""
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'3\s*ay|90\s*g[üu]n|u[cç]\s*ay', metin):
        return SartSonuc(ad='Rapor süresi 3 ay', durum=SartDurumu.VAR,
                         neden='Rapor metninde "3 ay" ibaresi',
                         kaynak='rapor_metni', grup=GRUP_SURE)
    return SartSonuc(ad='Rapor süresi 3 ay', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor süresi ibaresi okunamadı — manuel',
                     kaynak='rapor_metni', grup=GRUP_SURE, sartli_atom=True)


def _gate_atomlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    return [
        atom_sk_raporu(ilac_sonuc),
        atom_heyet_hematoloji(ilac_sonuc),
        atom_recete_hematoloji(ilac_sonuc),
        atom_ucuncu_basamak(ilac_sonuc),   # bilgi
        atom_rapor_suresi_3ay(ilac_sonuc),  # bilgi
    ]


# ═══════════════════════════════════════════════════════════════════════
# Y_MF atomları — Miyelofibrozis (Madde 1 + 2)
# ═══════════════════════════════════════════════════════════════════════

MF_TANI = '(1) Miyelofibrozis tanısı (≥1)'
MF_SPLENO = '(1a) Semptomatik masif splenomegali'
MF_DIPSS = '(1b) DIPSS-plus orta/yüksek risk'
MF_YANIT = '(1c) Önceki tedavi + yetersiz/kaybolmuş yanıt'
MF_KAN = '(1ç) Kan değerleri (trom≥100k/Hb≥8/nöt≥1000/blast<%10)'
MF_KIT = '(1d) Kemik iliği nakline uygun değil'
MF_DEVAM = '(2) 6. ay yanıt değerlendirme (bilgi)'


def _mf_tani_atomlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    tanilar = [
        ('Primer miyelofibrozis', bool(re.search(r'\bD47\.?4', icd))
         or 'primer miyelofibroz' in metin or 'primer myelofibroz' in metin
         or 'idyopatik miyelofibroz' in metin),
        ('Post-polisitemik miyelofibrozis', 'post polisitemik' in metin
         or 'post-polisitemik' in metin or 'polisitemi sonrasi' in metin),
        ('ET sonrası ikincil miyelofibrozis', 'esansiyel trombositemi sonrasi' in metin
         or 'et sonrasi' in metin or 'trombositemi sonrasi miyelofibroz' in metin),
    ]
    sonuc: List[SartSonuc] = []
    herhangi = any(v for _, v in tanilar)
    # Genel "miyelofibroz" ibaresi var ama alt-tip net değilse → ilk atomu KE-VAR
    genel_mf = bool(re.search(r'\bD47\.?[14]', icd)) or 'miyelofibroz' in metin \
        or 'myelofibroz' in metin
    for ad, var in tanilar:
        if var:
            sonuc.append(SartSonuc(ad=ad, durum=SartDurumu.VAR, neden='Tanı bulundu',
                                   kaynak='ICD+rapor', grup=MF_TANI, veya_grubu=True))
        else:
            sonuc.append(SartSonuc(ad=ad, durum=SartDurumu.YOK, neden='Tanı ibaresi yok',
                                   kaynak='ICD+rapor', grup=MF_TANI, veya_grubu=True))
    if not herhangi and genel_mf:
        # Alt-tip ayrışmadı ama MF var — grubu KE-şartlıya çek (örtük kabul yok)
        sonuc.append(SartSonuc(
            ad='Miyelofibrozis (alt-tip ayrışmadı)', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Miyelofibroz ibaresi var ama primer/post-PV/post-ET ayrımı '
                  'metinden okunamadı — manuel', kaynak='ICD+rapor',
            grup=MF_TANI, veya_grubu=True, sartli_atom=True))
    elif not herhangi:
        sonuc.append(SartSonuc(
            ad='Miyelofibrozis tanısı', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Miyelofibroz tanısı net okunamadı — manuel',
            kaynak='ICD+rapor', grup=MF_TANI, veya_grubu=True, sartli_atom=True))
    return sonuc


def atom_mf_splenomegali(ilac_sonuc: Dict) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if 'masif splenomegali' in metin or 'masif dalak' in metin or \
            ('semptomatik' in metin and 'splenomegali' in metin):
        return SartSonuc(ad='Semptomatik masif splenomegali', durum=SartDurumu.VAR,
                         neden='Rapor: semptomatik/masif splenomegali',
                         kaynak='rapor_metni', grup=MF_SPLENO)
    return SartSonuc(ad='Semptomatik masif splenomegali',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Semptomatik masif splenomegali ibaresi okunamadı — manuel',
                     kaynak='rapor_metni', grup=MF_SPLENO, sartli_atom=True)


def atom_mf_dipss(ilac_sonuc: Dict) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    has_dipss = 'dipss' in metin or 'dipps' in metin
    orta_yuksek = any(k in metin for k in (
        'orta risk', 'yuksek risk', 'intermediate', 'high risk', 'orta-yuksek',
        'orta veya yuksek', 'int-2', 'int 2', 'intermediate-2'))
    dusuk = ('dusuk risk' in metin or 'low risk' in metin) and not orta_yuksek
    if has_dipss and orta_yuksek:
        return SartSonuc(ad='DIPSS-plus orta/yüksek risk', durum=SartDurumu.VAR,
                         neden='Rapor: DIPSS-plus orta/yüksek risk',
                         kaynak='rapor_metni', grup=MF_DIPSS)
    if orta_yuksek:
        return SartSonuc(ad='DIPSS-plus orta/yüksek risk', durum=SartDurumu.VAR,
                         neden='Rapor: orta/yüksek risk ibaresi (DIPSS açıkça yazılmamış)',
                         kaynak='rapor_metni', grup=MF_DIPSS)
    if dusuk:
        return SartSonuc(ad='DIPSS-plus orta/yüksek risk', durum=SartDurumu.YOK,
                         neden='Rapor: düşük risk — orta/yüksek değil',
                         kaynak='rapor_metni', grup=MF_DIPSS)
    return SartSonuc(ad='DIPSS-plus orta/yüksek risk',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='DIPSS-plus risk grubu okunamadı — manuel',
                     kaynak='rapor_metni', grup=MF_DIPSS, sartli_atom=True)


def atom_mf_yanit(ilac_sonuc: Dict) -> SartSonuc:
    """M_c: ≥1 seri tedavi almış ∧ dalakta ≥%50 azalma elde edilemeyen ∨ yanıt kaybolan."""
    metin = _rapor_metni(ilac_sonuc)
    seri = ('seri tedavi' in metin or 'sira tedavi' in metin or
            'onceki tedavi' in metin or 'ruksolitinib' in metin or
            'birinci basamak' in metin)
    yetersiz = ('yanit elde edilemed' in metin or 'azalma elde edilemed' in metin or
                'yanit kayb' in metin or 'yaniti kayb' in metin or
                'yetersiz yanit' in metin or 'dirençli' in metin or 'direncli' in metin)
    if seri and yetersiz:
        return SartSonuc(ad='Önceki tedavi + yetersiz/kaybolmuş yanıt', durum=SartDurumu.VAR,
                         neden='Rapor: en az 1 seri tedavi + dalak yanıtı yetersiz/kaybolmuş',
                         kaynak='rapor_metni', grup=MF_YANIT)
    return SartSonuc(ad='Önceki tedavi + yetersiz/kaybolmuş yanıt',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='≥1 seri tedavi ve dalakta ≥%50 azalma sağlanamaması/yanıt '
                           'kaybı ibaresi net okunamadı — manuel',
                     kaynak='rapor_metni', grup=MF_YANIT, sartli_atom=True)


def _kan_atom(ad: str, deger: Optional[float], esik: float, yon: str,
              birim: str, grup: str) -> SartSonuc:
    """Tek kan-değeri atomu. yon='ge' (≥ esik VAR) | 'lt' (< esik VAR)."""
    if deger is None:
        return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=f'{ad} rapor metninden okunamadı — manuel',
                         kaynak='rapor_lab', grup=grup, sartli_atom=True)
    uygun = (deger >= esik) if yon == 'ge' else (deger < esik)
    isaret = '≥' if yon == 'ge' else '<'
    if uygun:
        return SartSonuc(ad=f'{ad} ({deger:g})', durum=SartDurumu.VAR,
                         neden=f'{deger:g} {birim} {isaret} {esik:g} — uygun',
                         kaynak='rapor_lab', grup=grup)
    return SartSonuc(ad=f'{ad} ({deger:g})', durum=SartDurumu.YOK,
                     neden=f'{deger:g} {birim} — {isaret}{esik:g} şartını sağlamıyor',
                     kaynak='rapor_lab', grup=grup)


def _mf_kan_atomlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    metin = _rapor_metni(ilac_sonuc)
    trom = _lab_deger(metin, ['trombosit', 'platelet', 'plt'])
    hb = _lab_deger(metin, ['hemoglobin', 'hgb', 'hb'])
    notr = _lab_deger(metin, ['notrofil', 'nötrofil', 'anc', 'mutlak notrofil'])
    blast = _lab_deger(metin, ['blast', 'cevresel kan blast', 'periferik blast'])
    # Trombosit ≥100.000 — metinde "100000" veya "100 bin" ya da "100" (bin/mm3)
    # küçük yazımlar olabilir; ölçek normalize: <1000 ise "bin" cinsindendir.
    def _olcek(v: Optional[float], bin_esik: float) -> Optional[float]:
        if v is None:
            return None
        return v * 1000 if v < bin_esik else v
    return [
        _kan_atom('Trombosit ≥100.000/mm³', _olcek(trom, 1000), 100000, 'ge', '/mm³', MF_KAN),
        _kan_atom('Hemoglobin ≥8 g/dl', hb, 8, 'ge', 'g/dl', MF_KAN),
        _kan_atom('Nötrofil ≥1000/mm³', _olcek(notr, 100), 1000, 'ge', '/mm³', MF_KAN),
        _kan_atom('Çevresel kan blast <%10', blast, 10, 'lt', '%', MF_KAN),
    ]


def atom_mf_kit_nakil(ilac_sonuc: Dict) -> SartSonuc:
    """M_d: kemik iliği nakline UYGUN OLMAYAN (negatif ibare — örtük kabul yok)."""
    metin = _rapor_metni(ilac_sonuc)
    uygun_degil = any(k in metin for k in (
        'nakline uygun olmayan', 'nakline uygun degil', 'nakil aday degil',
        'nakle uygun degil', 'transplantasyona uygun olmayan',
        'transplant aday degil', 'kit aday degil', 'nakil yapilamayan'))
    uygun = ('nakline uygun' in metin or 'nakil aday' in metin or
             'transplantasyona uygun' in metin) and not uygun_degil
    if uygun_degil:
        return SartSonuc(ad='Kemik iliği nakline uygun değil', durum=SartDurumu.VAR,
                         neden='Rapor: kemik iliği nakline uygun olmayan',
                         kaynak='rapor_metni', grup=MF_KIT)
    if uygun:
        return SartSonuc(ad='Kemik iliği nakline uygun değil', durum=SartDurumu.YOK,
                         neden='Rapor: nakil adayı/uygun — SUT nakil uygun OLMAYAN ister',
                         kaynak='rapor_metni', grup=MF_KIT)
    return SartSonuc(ad='Kemik iliği nakline uygun değil',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Kemik iliği nakli uygunluğu raporda belirtilmemiş — '
                           'manuel doğrula (örtük kabul yapılmaz)',
                     kaynak='rapor_metni', grup=MF_KIT, sartli_atom=True)


def atom_mf_devam(ilac_sonuc: Dict) -> SartSonuc:
    """Madde 2 (bilgi): 6. ay yanıt değerlendirme — dalak azalma/semptom iyileşme."""
    return SartSonuc(
        ad='6. ay yanıt değerlendirmesi (dalak azalma / konstitüsyonel semptom)',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Madde 2: tedavi başlangıcından 6 ay sonra dalakta azalma yoksa veya '
              'konstitüsyonel semptomda iyileşme yoksa tedavi kesilir — her 3 aylık '
              'raporda belirtilmeli; manuel doğrula',
        kaynak='rapor_metni', grup=MF_DEVAM, sartli_atom=True)


def y_mf_kontrol(ilac_sonuc: Dict, recete_tipi: str) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.extend(_mf_tani_atomlari(ilac_sonuc))
    s.append(atom_mf_splenomegali(ilac_sonuc))
    s.append(atom_mf_dipss(ilac_sonuc))
    s.append(atom_mf_yanit(ilac_sonuc))
    s.extend(_mf_kan_atomlari(ilac_sonuc))
    s.append(atom_mf_kit_nakil(ilac_sonuc))
    if recete_tipi == 'DEVAM':
        s.append(atom_mf_devam(ilac_sonuc))  # bilgi
    s.extend(_gate_atomlari(ilac_sonuc))
    return s


# ═══════════════════════════════════════════════════════════════════════
# Y_GVHD atomları — Graft versus Host (Madde 3)
# ═══════════════════════════════════════════════════════════════════════

GVHD_ENDIKASYON = '(3) GvHD endikasyonu (aGvHD 2-4 / orta-ağır kGvHD)'
GVHD_YETERSIZ = '(3) Kortikosteroid/sistemik tedaviye yetersiz yanıt'
GVHD_YAS = '(3) Yaş ≥12'
GVHD_DEVAM = '(3) Yanıt değerlendirme 14g/6ay (bilgi)'


def atom_gvhd_endikasyon(ilac_sonuc: Dict) -> SartSonuc:
    """GV_2: derece 2-4 aGvHD ∨ orta-ağır kGvHD."""
    metin = _rapor_metni(ilac_sonuc)
    agvhd = ('agvhd' in metin or 'akut graft' in metin or
             ('akut' in metin and 'graft' in metin))
    derece24 = bool(re.search(r'derece\s*[2-4]', metin) or
                    re.search(r'grade\s*(ii|iii|iv|[2-4])', metin) or
                    'evre 2' in metin or 'evre 3' in metin or 'evre 4' in metin)
    kgvhd = ('kgvhd' in metin or 'kronik graft' in metin or
             ('kronik' in metin and 'graft' in metin))
    orta_agir = ('orta' in metin or 'agir' in metin or 'ciddi' in metin or
                 'moderate' in metin or 'severe' in metin)
    a_ok = agvhd and derece24
    k_ok = kgvhd and orta_agir
    if a_ok or k_ok:
        ned = []
        if a_ok:
            ned.append('aGvHD derece 2-4')
        if k_ok:
            ned.append('orta-ağır kGvHD')
        return SartSonuc(ad='GvHD endikasyonu', durum=SartDurumu.VAR,
                         neden='Rapor: ' + ' / '.join(ned),
                         kaynak='rapor_metni', grup=GVHD_ENDIKASYON)
    if (agvhd and bool(re.search(r'derece\s*1', metin))) or \
       (kgvhd and 'hafif' in metin and not orta_agir):
        return SartSonuc(ad='GvHD endikasyonu', durum=SartDurumu.YOK,
                         neden='Rapor: derece 1 aGvHD / hafif kGvHD — kapsam dışı',
                         kaynak='rapor_metni', grup=GVHD_ENDIKASYON)
    if agvhd or kgvhd:
        return SartSonuc(ad='GvHD endikasyonu', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='GvHD var ama derece (aGvHD 2-4) / şiddet (orta-ağır '
                               'kGvHD) okunamadı — manuel',
                         kaynak='rapor_metni', grup=GVHD_ENDIKASYON, sartli_atom=True)
    return SartSonuc(ad='GvHD endikasyonu', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='aGvHD/kGvHD endikasyonu net okunamadı — manuel',
                     kaynak='rapor_metni', grup=GVHD_ENDIKASYON, sartli_atom=True)


def atom_gvhd_yetersiz_yanit(ilac_sonuc: Dict) -> SartSonuc:
    """GV_1: kortikosteroid ∨ diğer sistemik tedaviye yetersiz yanıt."""
    metin = _rapor_metni(ilac_sonuc)
    if (('kortikosteroid' in metin or 'steroid' in metin or 'sistemik tedavi' in metin)
            and ('yetersiz yanit' in metin or 'yanitsiz' in metin or 'refrakter' in metin
                 or 'dirençli' in metin or 'direncli' in metin)):
        return SartSonuc(ad='Kortikosteroid/sistemik tedaviye yetersiz yanıt',
                         durum=SartDurumu.VAR,
                         neden='Rapor: kortikosteroid/sistemik tedaviye yetersiz yanıt',
                         kaynak='rapor_metni', grup=GVHD_YETERSIZ)
    return SartSonuc(ad='Kortikosteroid/sistemik tedaviye yetersiz yanıt',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Kortikosteroid/sistemik tedaviye yetersiz yanıt ibaresi '
                           'okunamadı — manuel', kaynak='rapor_metni',
                     grup=GVHD_YETERSIZ, sartli_atom=True)


def atom_gvhd_yas(ilac_sonuc: Dict) -> SartSonuc:
    yas = _yas_oku(ilac_sonuc)
    if yas is None:
        return SartSonuc(ad='Yaş ≥12', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Hasta yaşı DB\'de yok — manuel',
                         kaynak='hasta_yas', grup=GVHD_YAS, sartli_atom=True)
    if yas >= 12:
        return SartSonuc(ad=f'Yaş {yas} (≥12)', durum=SartDurumu.VAR,
                         neden='12 yaş ve üzeri', kaynak='hasta_yas', grup=GVHD_YAS)
    return SartSonuc(ad=f'Yaş {yas} (<12)', durum=SartDurumu.YOK,
                     neden='GvHD endikasyonu 12 yaş ve üzeri için',
                     kaynak='hasta_yas', grup=GVHD_YAS)


def atom_gvhd_devam(ilac_sonuc: Dict) -> SartSonuc:
    return SartSonuc(
        ad='Yanıt değerlendirme (aGvHD 14. gün / kGvHD 6. ay tam-kısmi yanıt)',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Madde 3: aGvHD 14. günde, kGvHD 6. ayda tam/kısmi yanıt alınan '
              'hastalarda devam edilir — manuel doğrula',
        kaynak='rapor_metni', grup=GVHD_DEVAM, sartli_atom=True)


def y_gvhd_kontrol(ilac_sonuc: Dict, recete_tipi: str) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_gvhd_endikasyon(ilac_sonuc))
    s.append(atom_gvhd_yetersiz_yanit(ilac_sonuc))
    s.append(atom_gvhd_yas(ilac_sonuc))
    if recete_tipi == 'DEVAM':
        s.append(atom_gvhd_devam(ilac_sonuc))  # bilgi
    s.extend(_gate_atomlari(ilac_sonuc))
    return s


# ═══════════════════════════════════════════════════════════════════════
# Y_PV atomları — Polisitemi Vera (Madde 4 + 5)
# ═══════════════════════════════════════════════════════════════════════

PV_TANI = '(4) Polisitemi Vera tanısı'
PV_JAK2 = '(4) JAK2 (V617F/Exon 12) mutasyonu'
PV_DURUM = '(4) HÜ yanıtsızlık durumu (≥1)'
PV_DEVAM = '(5) 32 hafta yanıt değerlendirme (bilgi)'


def atom_pv_tani(ilac_sonuc: Dict) -> SartSonuc:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'\bD45\b', icd) or 'polisitemi vera' in metin or \
            'polistemi vera' in metin or 'polisitemia vera' in metin:
        return SartSonuc(ad='Polisitemi Vera tanısı', durum=SartDurumu.VAR,
                         neden=('ICD D45' if re.search(r'\bD45\b', icd)
                                else 'rapor: polisitemi vera'),
                         kaynak='ICD+rapor', grup=PV_TANI)
    return SartSonuc(ad='Polisitemi Vera tanısı', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Polisitemi vera tanısı (ICD D45 / metin) okunamadı — manuel',
                     kaynak='ICD+rapor', grup=PV_TANI, sartli_atom=True)


def atom_pv_jak2(ilac_sonuc: Dict) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    if 'jak2' in metin or 'jak 2' in metin or 'v617f' in metin or \
            'exon 12' in metin or 'exon12' in metin:
        return SartSonuc(ad='JAK2 (V617F/Exon 12) mutasyonu', durum=SartDurumu.VAR,
                         neden='Rapor: JAK2 mutasyonu belirtilmiş',
                         kaynak='rapor_metni', grup=PV_JAK2)
    return SartSonuc(ad='JAK2 (V617F/Exon 12) mutasyonu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='JAK2 (V617F/Exon 12) mutasyon ibaresi okunamadı — manuel',
                     kaynak='rapor_metni', grup=PV_JAK2, sartli_atom=True)


def _pv_durum_atomlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Madde 4 alt-durumları (1-/2-/3-) — ≥1 yeterli (veya_grubu)."""
    metin = _rapor_metni(ilac_sonuc)
    hu = ('hidroksiure' in metin or 'hydrea' in metin or 'hidroksiurea' in metin)
    # 1- : HÜ ≥2g/gün/maks + ≥3 ay + (flebotomi ∨ trombosit/wbc ∨ dalak ∨ tromboz)
    pv1 = hu and any(k in metin for k in (
        'flebotomi', 'tromboz', 'trombosit', 'beyaz kure', 'lökosit', 'lokosit',
        'dalak', 'splenomegali', 'kucuilme saptanma', 'kucilme saptanma'))
    # 2- : min HÜ dozunda sitopeni (nötrofil/trombosit/Hb düşük)
    pv2 = hu and any(k in metin for k in (
        'notrofil', 'nötrofil', 'sitopeni', 'pansitopeni')) and \
        any(k in metin for k in ('en dusuk', 'minimum doz', 'en az doz', '<1000',
                                 '<100000', 'düsuk'))
    # 3- : HÜ ilişkili bacak ülseri ∨ mukokutanöz belirti
    pv3 = ('bacak ulser' in metin or 'mukokutanoz' in metin or
           'mukokutanöz' in metin or 'cilt ulser' in metin)
    durumlar = [
        ('Hidroksiüreye rağmen yetersiz yanıt (flebotomi/sitoz/dalak/tromboz)', pv1),
        ('En düşük HÜ dozunda sitopeni (nötrofil<1000/trombosit<100k/Hb<10)', pv2),
        ('HÜ ilişkili bacak ülseri / kontrolsüz mukokutanöz belirti', pv3),
    ]
    sonuc: List[SartSonuc] = []
    if any(v for _, v in durumlar):
        for ad, v in durumlar:
            sonuc.append(SartSonuc(
                ad=ad, durum=(SartDurumu.VAR if v else SartDurumu.YOK),
                neden=('Rapor ibaresi bulundu' if v else 'İbare yok'),
                kaynak='rapor_metni', grup=PV_DURUM, veya_grubu=True))
    else:
        for ad, _ in durumlar:
            sonuc.append(SartSonuc(
                ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                neden='HÜ yanıtsızlık durumu ibaresi okunamadı — manuel',
                kaynak='rapor_metni', grup=PV_DURUM, veya_grubu=True, sartli_atom=True))
    return sonuc


def atom_pv_devam(ilac_sonuc: Dict) -> SartSonuc:
    return SartSonuc(
        ad='32 hafta sonunda yanıt (dalak ≥%35 küçülme + tam kan normalizasyonu)',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Madde 5: 32 haftalık tedavi sonunda dalakta ≥%35 küçülme ve tam kan '
              'sayımı normalize ise devam edilir — manuel doğrula',
        kaynak='rapor_metni', grup=PV_DEVAM, sartli_atom=True)


def y_pv_kontrol(ilac_sonuc: Dict, recete_tipi: str) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    s.append(atom_pv_tani(ilac_sonuc))
    s.append(atom_pv_jak2(ilac_sonuc))
    s.extend(_pv_durum_atomlari(ilac_sonuc))
    if recete_tipi == 'DEVAM':
        s.append(atom_pv_devam(ilac_sonuc))  # bilgi
    s.extend(_gate_atomlari(ilac_sonuc))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (grup + veya_grubu + şartlı atom — kanser_gcsf kalıbı)
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


YOLAK_AD = {
    'Y_MF': 'Miyelofibrozis (Madde 1/2)',
    'Y_GVHD': 'Graft versus Host (Madde 3)',
    'Y_PV': 'Polisitemi Vera (Madde 4/5)',
}


def _mesaj_uret(sonuc: KontrolSonucu, yolak: str, recete_tipi: str,
                belirsiz: bool, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    tip_ad = {'BASLANGIC': 'başlangıç', 'DEVAM': 'devam'}.get(recete_tipi, recete_tipi)
    parcalar = [f"Ruksolitinib (çç) / {YOLAK_AD.get(yolak, yolak)} / {tip_ad}"]
    if belirsiz:
        parcalar.append('⚠ endikasyon yolağı belirsiz — Y_MF varsayıldı')
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

YOLAK_FN_MAP = {'Y_MF': y_mf_kontrol, 'Y_GVHD': y_gvhd_kontrol, 'Y_PV': y_pv_kontrol}


def ruksolitinib_kontrol_4_2_14_cc(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.14.C-(çç) Ruksolitinib ana kontrol fonksiyonu."""
    sonuc_yolak = ruksolitinib_yolak_belirle(ilac_sonuc)
    if sonuc_yolak is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.14.C-(çç) kapsamı dışı — ruksolitinib (JAKAVI) değil',
            sut_kurali='SUT 4.2.14.C-(çç)')

    yolak, belirsiz = sonuc_yolak
    recete_tipi, tip_gerekce = ruksolitinib_recete_tipi(ilac_sonuc)
    sartlar = YOLAK_FN_MAP[yolak](ilac_sonuc, recete_tipi)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, recete_tipi, belirsiz, sartlar)

    detaylar = {
        'alt_grup': 'RUKSOLITINIB',
        'sut_maddesi': '4.2.14.C-(çç)',
        'yolak': yolak,
        'yolak_ad': YOLAK_AD.get(yolak, yolak),
        'dispatcher_belirsiz': belirsiz,
        'recete_tipi': recete_tipi,
        'recete_tipi_gerekce': tip_gerekce,
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
        sut_kurali=f"SUT 4.2.14.C-(çç) Ruksolitinib / {YOLAK_AD.get(yolak, yolak)}",
        aranan_ibare='endikasyon (MF/GvHD/PV) + başlangıç kriterleri + SK raporu '
                     '(heyette hematoloji) + hematoloji reçete',
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (≥14 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    # Ortak tam-uygun gate (SK kurul + heyette hematoloji + hematoloji reçete)
    GATE_OK = {
        'rapor_turu': 'Sağlık Kurulu Raporu', 'doktor_uzmanligi': 'Hematoloji',
        'rapor_kodu': '02.01',
        'heyet_doktorlari': [{'brans': 'Hematoloji'}, {'brans': 'İç Hastalıkları'}],
    }
    return [
        ("Y_MF tam UYGUN (tüm klinik + lab + gate)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 65, 'recete_teshisleri': ['D47.4'],
            'rapor_metni': 'primer miyelofibrozis. semptomatik masif splenomegali. '
                           'dipss-plus yuksek risk. en az bir seri tedavi sonrasi dalakta '
                           'yanit elde edilemedi. trombosit 150000 hemoglobin 10 notrofil '
                           '2000 cevresel kan blast 3. kemik iligi nakline uygun olmayan hasta.',
            **GATE_OK,
        }, KontrolSonucu.UYGUN),
        ("Y_MF UYGUN DEĞİL (düşük risk DIPSS)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 60, 'recete_teshisleri': ['D47.4'],
            'rapor_metni': 'primer miyelofibrozis. masif splenomegali. dipss-plus dusuk risk. '
                           'seri tedavi sonrasi yanit kayboldu. trombosit 150000 hemoglobin 10 '
                           'notrofil 2000 blast 2. kemik iligi nakline uygun olmayan.',
            **GATE_OK,
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y_MF UYGUN DEĞİL (trombosit <100k)", {
            'etkin_madde': 'JAKAVI', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 70, 'recete_teshisleri': ['D47.4'],
            'rapor_metni': 'primer miyelofibrozis. masif splenomegali. dipss yuksek risk. '
                           'seri tedavi yanit elde edilemedi. trombosit 80000 hemoglobin 9 '
                           'notrofil 1500 blast 4. nakline uygun degil.',
            **GATE_OK,
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y_MF ŞARTLI (klinik ibareler eksik, gate tam)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 66, 'recete_teshisleri': ['D47.4'],
            'rapor_metni': 'primer miyelofibrozis tanisi',
            **GATE_OK,
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Y_MF UYGUN DEĞİL (reçete eden hematoloji değil)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 66, 'recete_teshisleri': ['D47.4'],
            'rapor_metni': 'primer miyelofibrozis. masif splenomegali. dipss yuksek risk. '
                           'seri tedavi yanit elde edilemedi. trombosit 150000 hemoglobin 10 '
                           'notrofil 2000 blast 3. nakline uygun degil.',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'doktor_uzmanligi': 'Dahiliye',
            'rapor_kodu': '02.01',
            'heyet_doktorlari': [{'brans': 'Hematoloji'}, {'brans': 'İç Hastalıkları'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y_MF UYGUN DEĞİL (heyette hematoloji yok)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 66, 'recete_teshisleri': ['D47.4'],
            'rapor_metni': 'primer miyelofibrozis. masif splenomegali. dipss yuksek risk. '
                           'seri tedavi yanit elde edilemedi. trombosit 150000 hemoglobin 10 '
                           'notrofil 2000 blast 3. nakline uygun degil.',
            'rapor_turu': 'Sağlık Kurulu Raporu', 'doktor_uzmanligi': 'Hematoloji',
            'rapor_kodu': '02.01',
            'heyet_doktorlari': [{'brans': 'İç Hastalıkları'}, {'brans': 'Genel Cerrahi'}],
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y_MF UYGUN DEĞİL (nakil adayı — kontrendikasyon)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 50, 'recete_teshisleri': ['D47.4'],
            'rapor_metni': 'primer miyelofibrozis. masif splenomegali. dipss yuksek risk. '
                           'seri tedavi yanit elde edilemedi. trombosit 150000 hemoglobin 10 '
                           'notrofil 2000 blast 3. hasta kemik iligi nakline uygun, nakil adayi.',
            **GATE_OK,
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y_GVHD tam UYGUN (aGvHD derece 3, 30 yaş)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 30, 'recete_teshisleri': ['D89.81'],
            'rapor_metni': 'akut graft versus host hastaligi agvhd derece 3. kortikosteroid '
                           'tedavisine yetersiz yanit.',
            **GATE_OK,
        }, KontrolSonucu.UYGUN),
        ("Y_GVHD UYGUN DEĞİL (yaş <12)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 9, 'recete_teshisleri': ['D89.81'],
            'rapor_metni': 'akut graft versus host agvhd derece 3. kortikosteroide '
                           'yetersiz yanit.',
            **GATE_OK,
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Y_GVHD ŞARTLI (GvHD var derece okunamadı)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 40, 'recete_teshisleri': ['D89.81'],
            'rapor_metni': 'graft versus host hastaligi mevcut',
            **GATE_OK,
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Y_PV tam UYGUN (JAK2 + flebotomi)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 58, 'recete_teshisleri': ['D45'],
            'rapor_metni': 'polisitemi vera. jak2 v617f mutasyonu pozitif. hidroksiure 2 g/gun '
                           'tedaviye ragmen aylik flebotomi ihtiyaci devam ediyor.',
            **GATE_OK,
        }, KontrolSonucu.UYGUN),
        ("Y_PV ŞARTLI (JAK2 + durum okunamadı)", {
            'etkin_madde': 'JAKAVI', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 55, 'recete_teshisleri': ['D45'],
            'rapor_metni': 'polisitemi vera tanisi. jak2 mutasyonu pozitif.',
            **GATE_OK,
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Belirsiz endikasyon → Y_MF varsayım, ŞARTLI", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 60, 'recete_teshisleri': ['R69'],
            'rapor_metni': 'hematolojik hastalik takibi',
            **GATE_OK,
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (topikal OPZELURA)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'D11AH09',
            'rapor_metni': 'vitiligo',
        }, KontrolSonucu.ATLANDI),
        ("Y_MF UYGUN DEĞİL (rapor yok)", {
            'etkin_madde': 'RUKSOLITINIB', 'atc_kodu': 'L01EJ01',
            'hasta_yasi': 60, 'recete_teshisleri': ['D47.4'],
            'rapor_metni': 'primer miyelofibrozis. masif splenomegali. dipss yuksek risk. '
                           'seri tedavi yanit elde edilemedi. trombosit 150000 hemoglobin 10 '
                           'notrofil 2000 blast 3. nakline uygun degil.',
            'doktor_uzmanligi': 'Hematoloji',
        }, KontrolSonucu.UYGUN_DEGIL),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.14.C-(çç) Ruksolitinib — Akıl Testi\n" + "=" * 64)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = ruksolitinib_kontrol_4_2_14_cc(ilac_sonuc)
        ok = rapor.sonuc == beklenen
        gecti += ok
        print(f"{'✓' if ok else '✗'} {ad}")
        print(f"    beklenen={beklenen.value}  gerçek={rapor.sonuc.value}")
        if not ok:
            print(f"    MESAJ: {rapor.mesaj}")
            for s in rapor.sartlar:
                print(f"      - [{s.durum.value}] {s.ad} ({s.grup}) :: {s.neden}")
    print("=" * 64)
    print(f"SONUÇ: {gecti}/{len(senaryolar)} senaryo geçti")


if __name__ == '__main__':
    _akil_testi()
