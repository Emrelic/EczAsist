# -*- coding: utf-8 -*-
"""SUT 4.2.9.B — Sevelamer, lantanyum karbonat ve alüminyum klorür hidroksit
(fosfor bağlayıcılar) kullanım ilkeleri.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:5065-5082`` (mevzuat.gov.tr,
MevzuatNo=17229, Değişik başlık:RG-7/10/2016-29850). Protokol:
``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ``ATOMİK DEVRE ŞEMASI
PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
KAPSAM (dispatcher: ilaç sınıfı)
═══════════════════════════════════════════════════════════════════════════

  Kapsam ilaçları (fosfor bağlayıcılar — bu maddenin denetlediği ilaçlar):
    SEVELAMER  → RENAGEL / RENVELA — ATC V03AE02
    LANTANYUM  → FOSRENOL (lantanyum karbonat) — ATC V03AE03
    ALUMINYUM  → alüminyum klorür hidroksit

  Kapsam DIŞI: kalsiyum asetat / kalsiyum karbonat gibi "diğer fosfor
  düşürücü ilaçlar" — bunlar madde (1)'deki BAŞLANGIÇ ÖN-KOŞUL ilaçlarıdır
  (≥3 ay kullanılmış olmalı), denetim nesnesi değildir → ATLANDI.

═══════════════════════════════════════════════════════════════════════════
ATOMİK ŞARTLAR (CLAUDE.md disiplini — her ibare = bir ampul)
═══════════════════════════════════════════════════════════════════════════

  G1 — Başlangıç ön-koşulu (md.1):
    S1  diğer fosfor düşürücü ilaç ≥3 ay + raporda belirtilmiş   [AND]

  G2 — Başlangıç lab kriteri (md.1, a∨b∨c∨ç ≥1):                [VEYA]
    S2a Kalsiyum × Fosfor çarpımı ≥ 72
    S2b PTH < 100 pg/ml  ∧  adinamik kemik hastalığı
    S2c Kt/V > 1,4  ∧  düzeltilmiş Ca×P > 55
    S2ç Kt/V > 1,4  ∧  PTH ≥ 300 pg/ml

  G3 — Yetki (md.2):                                            [AND]
    S3  hemodiyaliz ∨ periton diyaliz hastası
    S4  rapor: nefroloji / iç hastalıkları / çocuk uzman hekim
    S5  reçete: bu branşlar ∨ diyaliz sertifikalı tüm hekimler

  G4 — Doz / Fosfor (md.3):                                     [AND]
    S6  fosfor düzeyi ≥ 3,5 mg/dl (< 3,5 → tedavi kesilir = kontrendikasyon)
    S7  en fazla bir aylık doz
    S8  son 1 ay fosfor tetkik tarih+sonuç   [(bilgi)]

  G5 — Kombinasyon yasağı (md.5):                               [AND]
    S9  sevelamer + lantanyum karbonat AYNI reçetede → YASAK

  Madde (4) (P>4 → ilk başlama kriterleri ile yeniden başlanır) bilgilendirme
  niteliğindedir, ayrı bir kapı değildir.

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔  G1(S1)
         ∧ G2(S2a ∨ S2b ∨ S2c ∨ S2ç)
         ∧ G3(S3 ∧ S4 ∧ S5)
         ∧ G4(S6 ∧ S7)            (S8 bilgi)
         ∧ ¬S9

Başlangıç kriterleri (G1/G2): kullanıcı kararı 2026-06-05 —
"DAHA ÖNCE BAŞLANGIÇ RAPORU VAR MI DİYE BAK; BULUNAMADI İSE KE+ŞARTLI UYGUN".
Hastanın bu etken için EOS başlangıç raporu (``baslangic_raporu_bul`` /
``recete_tipi_eos_bazli``) aranır; bulunursa o raporun metni başlangıç
kriterlerine kaynak olur, bulunamazsa atomlar KE+şartlı → ŞARTLI UYGUN.
Sessizlik = örtük kabul YASAK.

Ana entrypoint: ``sevelamer_fosfor_kontrol_4_2_9_b(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç sınıfı listeleri (etken + ticari ad + ATC)
# ═══════════════════════════════════════════════════════════════════════

SEVELAMER = {
    'SEVELAMER', 'SEVELAMER KARBONAT', 'SEVELAMER HIDROKLORUR',
    'SEVELAMER HIDROKLORID', 'RENAGEL', 'RENVELA', 'SEVELACARE', 'SEVKAR',
}
LANTANYUM = {
    'LANTANYUM', 'LANTANYUM KARBONAT', 'LANTHANUM', 'LANTHANUM CARBONATE',
    'FOSRENOL',
}
ALUMINYUM = {
    'ALUMINYUM KLORUR HIDROKSIT', 'ALUMINYUM KLORUR HIDROKSID',
    'ALUMINYUM KLORUR', 'ALUMINUM CHLORIDE HYDROXIDE',
}

# ATC önekleri (güçlü sinyal)
ATC_FOSFOR = {
    'V03AE02': 'SEVELAMER',
    'V03AE03': 'LANTANYUM',
}

# EOS başlangıç araması için keyword havuzu
FOSFOR_EOS_KEYWORDS: Tuple[str, ...] = tuple(sorted(
    SEVELAMER | LANTANYUM | ALUMINYUM))

# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower alt-string)
# ═══════════════════════════════════════════════════════════════════════
NEFROLOJI = ['nefroloji']
IC_HAST = ['ic hastalik', 'dahiliye']
COCUK = ['cocuk', 'pediatri']
# md.2 yetkili branşlar (reçete/rapor)
YETKILI_BRANS = NEFROLOJI + IC_HAST + COCUK


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


def _rapor_metni(ilac_sonuc: Dict) -> str:
    """Aktif rapor + reçete metinleri (norm_tr_lower)."""
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


def _diger_ilac_metni(ilac_sonuc: Dict) -> str:
    """Aynı reçetedeki diğer ilaç adları (norm_tr_upper)."""
    parcalar: List[str] = []
    v = ilac_sonuc.get('diger_ilac_adlari')
    if isinstance(v, (list, tuple)):
        parcalar.extend(str(x) for x in v if x)
    elif v:
        parcalar.append(str(v))
    for it in (ilac_sonuc.get('recete_ilaclari') or []):
        if isinstance(it, dict):
            ad = it.get('ad') or it.get('ilac') or ''
            if ad:
                parcalar.append(str(ad))
        elif it:
            parcalar.append(str(it))
    return norm_tr_upper(' '.join(parcalar))


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
              "arasi", "gelinc", "gecinc", "kesil", "baslan", "tutab", "ve uzeri",
              "'in", "'nin", "'nın", "'yi", "'ye", "'ya", "'a ", "'un", "'nun")


def _lab_deger(metin: str, anahtarlar: List[str]) -> Optional[float]:
    """Rapor metninde anahtar yakınındaki ilk ölçüm değerini döndür.

    metin: norm_tr_lower edilmiş. SUT-anlatı sayıları (_NARRATIVE) atlanır.
    """
    for a in anahtarlar:
        for m in re.finditer(re.escape(a) + r'[^\d\n]{0,12}?(\d+(?:[.,]\d+)?)', metin):
            before = metin[max(0, m.start() - 18):m.start()]
            after = metin[m.end():m.end() + 18]
            ctx = before + ' ' + after
            if any(tok in ctx for tok in _NARRATIVE):
                continue
            try:
                return float(m.group(1).replace(',', '.'))
            except ValueError:
                continue
    return None


# ═══════════════════════════════════════════════════════════════════════
# İLAÇ SINIFI (DİSPATCHER)
# ═══════════════════════════════════════════════════════════════════════

def _ilac_sinifi(ilac_sonuc: Dict) -> Optional[str]:
    """Fosfor bağlayıcı sınıfı → 'SEVELAMER'|'LANTANYUM'|'ALUMINYUM'|None."""
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    for prefix, sinif in ATC_FOSFOR.items():
        if atc.startswith(prefix):
            return sinif
    m = _arama_metni(ilac_sonuc)
    if _iceriyor(m, SEVELAMER):
        return 'SEVELAMER'
    if _iceriyor(m, LANTANYUM):
        return 'LANTANYUM'
    if _iceriyor(m, ALUMINYUM):
        return 'ALUMINYUM'
    return None


def sevelamer_fosfor_kapsami_mi(ilac_sonuc: Dict) -> bool:
    return _ilac_sinifi(ilac_sonuc) is not None


# ═══════════════════════════════════════════════════════════════════════
# BAŞLANGIÇ RAPORU BAĞLAMI (G1/G2 kaynağı)
# ═══════════════════════════════════════════════════════════════════════

def _baslangic_corpus(ilac_sonuc: Dict) -> Tuple[str, bool, str]:
    """Başlangıç kriterleri (G1/G2) için kaynak metin + 'başlangıç var mı'.

    Sıra:
      1. ilac_sonuc['baslangic_rapor_metni'] (GUI/test pre-enrichment) →
         başlangıç bulundu, corpus = başlangıç + aktif metin.
      2. ilac_sonuc['baslangic_durum'] == 'BASLANGIC'/'AKTIF_ZATEN_BASLANGIC'
         (EOS ordinalitesi) → aktif reçete = başlangıç → corpus = aktif metin.
      3. hasta_tc varsa baslangic_raporu_bul() (EOS) dene.
      4. Aksi halde başlangıç bulunamadı → (corpus, False).

    Returns:
        (corpus_lower, baslangic_var, kaynak_aciklama)
    """
    aktif = _rapor_metni(ilac_sonuc)

    bm = ilac_sonuc.get('baslangic_rapor_metni')
    if bm:
        return (norm_tr_lower(str(bm) + ' ' + aktif), True,
                'başlangıç rapor metni (önceden bulundu)')

    durum = (ilac_sonuc.get('baslangic_durum') or '').strip().upper()
    if durum in ('BASLANGIC', 'AKTIF_ZATEN_BASLANGIC'):
        return (aktif, True, 'aktif reçete başlangıç (EOS ordinalitesi)')
    if durum in ('BASKA_ECZANE_RISKI', 'YOK_EOS', 'DEVAM'):
        return (aktif, False, f'başlangıç raporu bulunamadı ({durum})')

    # EOS canlı sorgu (DB yoksa sessizce geç — test ortamı)
    hasta_tc = (ilac_sonuc.get('hasta_tc') or '').strip()
    if hasta_tc:
        try:  # pragma: no cover - DB'ye bağlı
            from recete_kontrol.baslangic_rapor_bulucu import baslangic_raporu_bul
            aktif_takip = (ilac_sonuc.get('rapor_takip_no')
                           or ilac_sonuc.get('rap_tak_no') or '')
            sonuc = baslangic_raporu_bul(
                hasta_tc, FOSFOR_EOS_KEYWORDS,
                aktif_rapor_takip_no=aktif_takip or None,
                aktif_rapor_metni=aktif)
            if sonuc:
                d = (sonuc.get('durum') or '').upper()
                metin = (sonuc.get('rapor_metni') or '').strip()
                if d in ('BULUNDU', 'BULUNDU_LAFIZ', 'BULUNDU_TABLO',
                         'AKTIF_ZATEN_BASLANGIC'):
                    corpus = norm_tr_lower((metin + ' ' + aktif) if metin else aktif)
                    return (corpus, True, f'EOS başlangıç ({d})')
        except Exception:  # pragma: no cover
            pass

    # Başlangıç tespit edilemedi
    return (aktif, False, 'başlangıç raporu bulunamadı — manuel')


def _cap_carpim(metin: str) -> Optional[float]:
    """Kalsiyum × Fosfor çarpımı — önce lafzen 'çarpım', sonra Ca·P hesabı."""
    carpim = _lab_deger(metin, ['kalsiyum fosfor carpim', 'ca x p', 'ca*p',
                                'caxp', 'kalsiyum x fosfor', 'cap carpim',
                                'fosfor carpim', 'carpim'])
    if carpim is not None:
        return carpim
    ca = _lab_deger(metin, ['duzeltilmis kalsiyum', 'kalsiyum', 'serum kalsiyum',
                            'ca '])
    p = _lab_deger(metin, ['fosfor', 'fosfat', 'serum fosfor'])
    if ca is not None and p is not None:
        return round(ca * p, 1)
    return None


# ═══════════════════════════════════════════════════════════════════════
# G1 — BAŞLANGIÇ ÖN-KOŞULU (md.1)
# ═══════════════════════════════════════════════════════════════════════

GRUP_ONKOSUL = '(1) Başlangıç ön-koşulu: ≥3 ay diğer fosfor düşürücü'


def atom_s1_onkosul(corpus: str, baslangic_var: bool, kaynak: str) -> SartSonuc:
    """S1: diğer fosfor düşürücü ilaç ≥3 ay kullanılmış + raporda belirtilmiş."""
    if not baslangic_var:
        return SartSonuc(
            ad='≥3 ay diğer fosfor düşürücü ilaç (başlangıç ön-koşulu)',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden=f'Başlangıç raporu bulunamadı — ön-koşul doğrulanamadı '
                  f'({kaynak})', kaynak='baslangic', grup=GRUP_ONKOSUL,
            sartli_atom=True)
    # Başlangıç metninde "diğer fosfor düşürücü / kalsiyum asetat-karbonat" +
    # süre ibaresi ara
    fosfor_ilac = any(k in corpus for k in (
        'diger fosfor dusurucu', 'fosfor dusurucu', 'kalsiyum asetat',
        'kalsiyum karbonat', 'fosfor baglayici'))
    sure = bool(re.search(r'\b3\s*ay', corpus)) or 'uc ay' in corpus \
        or bool(re.search(r'\b(en az|asgari)\b[^.]{0,20}ay', corpus))
    if fosfor_ilac and sure:
        return SartSonuc(
            ad='≥3 ay diğer fosfor düşürücü ilaç', durum=SartDurumu.VAR,
            neden='Başlangıç raporunda önceki fosfor düşürücü + ≥3 ay ibaresi',
            kaynak='baslangic', grup=GRUP_ONKOSUL)
    return SartSonuc(
        ad='≥3 ay diğer fosfor düşürücü ilaç', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Başlangıç raporu var ama ≥3 ay önceki fosfor düşürücü ibaresi '
              'metinden net okunamadı — manuel', kaynak='baslangic',
        grup=GRUP_ONKOSUL, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# G2 — BAŞLANGIÇ LAB KRİTERİ (md.1, a∨b∨c∨ç)
# ═══════════════════════════════════════════════════════════════════════

GRUP_LAB = '(1) Başlangıç lab kriteri (a/b/c/ç ≥1)'


def _ke_lab(ad: str) -> SartSonuc:
    return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Başlangıç raporu lab değerleri metinden okunamadı — '
                           'manuel doğrula', kaynak='baslangic_lab',
                     grup=GRUP_LAB, veya_grubu=True, sartli_atom=True)


def atom_s2a(corpus: str, baslangic_var: bool) -> SartSonuc:
    """a) Ca × P çarpımı ≥ 72."""
    if not baslangic_var:
        return _ke_lab('a) Ca×P ≥ 72')
    cap = _cap_carpim(corpus)
    if cap is None:
        return _ke_lab('a) Ca×P ≥ 72')
    if cap >= 72:
        return SartSonuc(ad=f'a) Ca×P {cap:g} ≥ 72', durum=SartDurumu.VAR,
                         neden=f'Kalsiyum×fosfor çarpımı {cap:g}',
                         kaynak='baslangic_lab', grup=GRUP_LAB, veya_grubu=True)
    return SartSonuc(ad=f'a) Ca×P {cap:g} < 72', durum=SartDurumu.YOK,
                     neden=f'Çarpım {cap:g} — 72 eşiğinin altında',
                     kaynak='baslangic_lab', grup=GRUP_LAB, veya_grubu=True)


def atom_s2b(corpus: str, baslangic_var: bool) -> SartSonuc:
    """b) PTH < 100 ∧ adinamik kemik hastalığı."""
    if not baslangic_var:
        return _ke_lab('b) PTH < 100 ∧ adinamik kemik hastalığı')
    pth = _lab_deger(corpus, ['parathormon', 'parat hormon', 'pth'])
    adinamik = 'adinamik' in corpus or 'adynamik' in corpus
    if pth is None or not adinamik:
        return _ke_lab('b) PTH < 100 ∧ adinamik kemik hastalığı')
    if pth < 100 and adinamik:
        return SartSonuc(ad=f'b) PTH {pth:g} < 100 ∧ adinamik', durum=SartDurumu.VAR,
                         neden=f'PTH {pth:g} pg/ml + adinamik kemik hastalığı',
                         kaynak='baslangic_lab', grup=GRUP_LAB, veya_grubu=True)
    return SartSonuc(ad=f'b) PTH {pth:g} / adinamik', durum=SartDurumu.YOK,
                     neden=f'PTH {pth:g} (<100 değil) veya adinamik yok',
                     kaynak='baslangic_lab', grup=GRUP_LAB, veya_grubu=True)


def atom_s2c(corpus: str, baslangic_var: bool) -> SartSonuc:
    """c) Kt/V > 1,4 ∧ düzeltilmiş Ca×P > 55."""
    if not baslangic_var:
        return _ke_lab('c) Kt/V > 1,4 ∧ Ca×P > 55')
    ktv = _lab_deger(corpus, ['kt/v', 'ktv', 'kt v'])
    cap = _cap_carpim(corpus)
    if ktv is None or cap is None:
        return _ke_lab('c) Kt/V > 1,4 ∧ Ca×P > 55')
    if ktv > 1.4 and cap > 55:
        return SartSonuc(ad=f'c) Kt/V {ktv:g}>1,4 ∧ Ca×P {cap:g}>55',
                         durum=SartDurumu.VAR,
                         neden=f'Kt/V {ktv:g} + çarpım {cap:g}',
                         kaynak='baslangic_lab', grup=GRUP_LAB, veya_grubu=True)
    return SartSonuc(ad=f'c) Kt/V {ktv:g} / Ca×P {cap:g}', durum=SartDurumu.YOK,
                     neden=f'Kt/V {ktv:g} (>1,4 değil) veya çarpım {cap:g} (>55 değil)',
                     kaynak='baslangic_lab', grup=GRUP_LAB, veya_grubu=True)


def atom_s2c_cedilla(corpus: str, baslangic_var: bool) -> SartSonuc:
    """ç) Kt/V > 1,4 ∧ PTH ≥ 300."""
    if not baslangic_var:
        return _ke_lab('ç) Kt/V > 1,4 ∧ PTH ≥ 300')
    ktv = _lab_deger(corpus, ['kt/v', 'ktv', 'kt v'])
    pth = _lab_deger(corpus, ['parathormon', 'parat hormon', 'pth'])
    if ktv is None or pth is None:
        return _ke_lab('ç) Kt/V > 1,4 ∧ PTH ≥ 300')
    if ktv > 1.4 and pth >= 300:
        return SartSonuc(ad=f'ç) Kt/V {ktv:g}>1,4 ∧ PTH {pth:g}≥300',
                         durum=SartDurumu.VAR,
                         neden=f'Kt/V {ktv:g} + PTH {pth:g} pg/ml',
                         kaynak='baslangic_lab', grup=GRUP_LAB, veya_grubu=True)
    return SartSonuc(ad=f'ç) Kt/V {ktv:g} / PTH {pth:g}', durum=SartDurumu.YOK,
                     neden=f'Kt/V {ktv:g} (>1,4 değil) veya PTH {pth:g} (≥300 değil)',
                     kaynak='baslangic_lab', grup=GRUP_LAB, veya_grubu=True)


# ═══════════════════════════════════════════════════════════════════════
# G3 — YETKİ (md.2)
# ═══════════════════════════════════════════════════════════════════════

GRUP_DIYALIZ = '(2) Diyaliz tedavisi (HD ∨ periton)'
GRUP_RAPOR = '(2) Rapor: nefroloji/iç hast./çocuk uzmanı'
GRUP_RECETE = '(2) Reçete: yetkili branş ∨ diyaliz sertifikalı'


def atom_s3_diyaliz(ilac_sonuc: Dict) -> SartSonuc:
    """S3: hemodiyaliz ∨ periton diyaliz hastası."""
    metin = _rapor_metni(ilac_sonuc)
    hd = 'hemodiyaliz' in metin or re.search(r'\bhd\b', metin) is not None
    pd = 'periton' in metin or re.search(r'\b(capd|sapd)\b', metin) is not None
    if hd or pd:
        tip = 'hemodiyaliz' if hd else 'periton diyaliz'
        return SartSonuc(ad='Diyaliz tedavisi altında', durum=SartDurumu.VAR,
                         neden=f'Rapor: {tip}', kaynak='rapor', grup=GRUP_DIYALIZ)
    return SartSonuc(ad='Diyaliz tedavisi (HD/periton)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor metninde diyaliz tedavisi (HD/periton) ibaresi '
                           'bulunamadı — manuel doğrula', kaynak='rapor',
                     grup=GRUP_DIYALIZ, sartli_atom=True)


def atom_s4_rapor_brans(ilac_sonuc: Dict) -> SartSonuc:
    """S4: rapor nefroloji / iç hastalıkları / çocuk uzmanı tarafından."""
    rb = ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or ''
    heyet = _heyet_brans_listesi(ilac_sonuc)
    adaylar = [rb] + heyet
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or ilac_sonuc.get('rap_tak_no') or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or any(adaylar))
    if any(_brans_listede(b, YETKILI_BRANS) for b in adaylar):
        return SartSonuc(ad='Uzman hekim raporu (nefro/iç/çocuk)', durum=SartDurumu.VAR,
                         neden='Rapor yetkili uzman branşında', kaynak='rapor_brans',
                         grup=GRUP_RAPOR)
    if not rapor_var:
        return SartSonuc(ad='Uzman hekim raporu (nefro/iç/çocuk)', durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı uzman hekim raporu bulunamadı',
                         kaynak='rapor', grup=GRUP_RAPOR)
    return SartSonuc(ad='Uzman hekim raporu (nefro/iç/çocuk)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş nefro/iç/çocuk olarak '
                           'doğrulanamadı — manuel', kaynak='rapor_brans',
                     grup=GRUP_RAPOR, sartli_atom=True)


def atom_s5_recete_brans(ilac_sonuc: Dict) -> SartSonuc:
    """S5: reçete nefro/iç/çocuk uzmanı ∨ diyaliz sertifikalı tüm hekim.

    Diyaliz sertifikası DB'de yok → yetkili branş dışı hekim KE+şartlı.
    """
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    bl = _brans_l(brans)
    if not bl:
        return SartSonuc(ad='Reçete eden branş', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_RECETE, sartli_atom=True)
    if _brans_listede(brans, YETKILI_BRANS):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Nefroloji/iç hast./çocuk — yetkili',
                         kaynak='hekim_brans', grup=GRUP_RECETE)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Yetkili uzman branşı değil — diyaliz sertifikalı hekim '
                           'olabilir, manuel doğrula', kaynak='hekim_brans',
                     grup=GRUP_RECETE, sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# G4 — DOZ / FOSFOR (md.3)
# ═══════════════════════════════════════════════════════════════════════

GRUP_FOSFOR = '(3) Fosfor düzeyi ≥ 3,5 mg/dl'
GRUP_DOZ = '(3) En fazla 1 aylık doz'
GRUP_BELGE = '(3) Fosfor tetkik belgesi (bilgi)'


def atom_s6_fosfor(ilac_sonuc: Dict) -> SartSonuc:
    """S6: fosfor düzeyi < 3,5 mg/dl → tedavi kesilir (kontrendikasyon)."""
    metin = _rapor_metni(ilac_sonuc)
    p = _lab_deger(metin, ['fosfor', 'fosfat', 'serum fosfor', 'p:'])
    if p is None:
        return SartSonuc(ad='Fosfor düzeyi (≥ 3,5 mg/dl)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Fosfor düzeyi reçete/rapor metninden okunamadı — '
                               'manuel (her reçetede son 1 ay fosfor şart)',
                         kaynak='rapor_lab', grup=GRUP_FOSFOR, sartli_atom=True)
    if p < 3.5:
        return SartSonuc(ad=f'Fosfor {p:g} < 3,5 mg/dl', durum=SartDurumu.YOK,
                         neden=f'Fosfor {p:g} mg/dl — 3,5 altında, tedavi kesilmeli',
                         kaynak='rapor_lab', grup=GRUP_FOSFOR)
    return SartSonuc(ad=f'Fosfor {p:g} ≥ 3,5 mg/dl', durum=SartDurumu.VAR,
                     neden=f'Fosfor {p:g} mg/dl — tedavi sürdürülebilir',
                     kaynak='rapor_lab', grup=GRUP_FOSFOR)


def atom_s7_doz(ilac_sonuc: Dict) -> SartSonuc:
    """S7 (şartlı): bir defada en fazla 1 aylık doz. Kutu adediyle kaba hesap."""
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
                         grup=GRUP_DOZ, sartli_atom=True)
    if kutu <= 6:
        return SartSonuc(ad='En fazla 1 aylık doz', durum=SartDurumu.VAR,
                         neden=f'Kutu adedi {kutu:g} — 1 aylık için makul',
                         kaynak='doz', grup=GRUP_DOZ)
    return SartSonuc(ad='En fazla 1 aylık doz', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=f'Kutu adedi {kutu:g} — 1 aylık dozu aşıyor olabilir, manuel',
                     kaynak='doz', grup=GRUP_DOZ, sartli_atom=True)


def atom_s8_belge(ilac_sonuc: Dict) -> SartSonuc:
    """S8 (bilgi): son 1 ay fosfor tetkik tarih+sonuç reçete/raporda."""
    metin = _rapor_metni(ilac_sonuc)
    tarih_var = bool(re.search(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', metin))
    if tarih_var:
        return SartSonuc(ad='Fosfor tetkik tarih+sonuç', durum=SartDurumu.VAR,
                         neden='Tetkik tarihi reçete/rapor metninde bulundu',
                         kaynak='rapor_metni', grup=GRUP_BELGE)
    return SartSonuc(ad='Fosfor tetkik tarih+sonuç', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Son 1 ay fosfor tetkik tarih/sonucu metinden okunamadı — '
                           'manuel', kaynak='rapor_metni', grup=GRUP_BELGE,
                     sartli_atom=True)


# ═══════════════════════════════════════════════════════════════════════
# G5 — KOMBİNASYON YASAĞI (md.5)
# ═══════════════════════════════════════════════════════════════════════

GRUP_KOMBI = '(5) Sevelamer + lantanyum kombinasyon yasağı'


def atom_s9_kombinasyon(ilac_sonuc: Dict, sinif: str) -> SartSonuc:
    """S9: sevelamer + lantanyum karbonat aynı reçetede → YASAK (md.5)."""
    diger = _diger_ilac_metni(ilac_sonuc)
    diger_sev = _iceriyor(diger, SEVELAMER)
    diger_lan = _iceriyor(diger, LANTANYUM)
    catisma = (sinif == 'SEVELAMER' and diger_lan) or \
              (sinif == 'LANTANYUM' and diger_sev)
    if catisma:
        return SartSonuc(ad='Sevelamer + lantanyum kombinasyonu', durum=SartDurumu.YOK,
                         neden='Aynı reçetede sevelamer ve lantanyum karbonat birlikte '
                               '— SUT md.5 kombine kullanım yasağı', kaynak='diger_ilac',
                         grup=GRUP_KOMBI)
    return SartSonuc(ad='Kombinasyon yasağı (sevelamer+lantanyum)', durum=SartDurumu.VAR,
                     neden='Yasaklı kombinasyon (sevelamer+lantanyum) saptanmadı',
                     kaynak='diger_ilac', grup=GRUP_KOMBI)


# ═══════════════════════════════════════════════════════════════════════
# ŞART ÜRETİMİ
# ═══════════════════════════════════════════════════════════════════════

def _sartlar_uret(ilac_sonuc: Dict, sinif: str) -> List[SartSonuc]:
    corpus, baslangic_var, kaynak = _baslangic_corpus(ilac_sonuc)
    s: List[SartSonuc] = []
    # G1 — başlangıç ön-koşulu
    s.append(atom_s1_onkosul(corpus, baslangic_var, kaynak))
    # G2 — başlangıç lab (a/b/c/ç VEYA)
    s.append(atom_s2a(corpus, baslangic_var))
    s.append(atom_s2b(corpus, baslangic_var))
    s.append(atom_s2c(corpus, baslangic_var))
    s.append(atom_s2c_cedilla(corpus, baslangic_var))
    # G3 — yetki
    s.append(atom_s3_diyaliz(ilac_sonuc))
    s.append(atom_s4_rapor_brans(ilac_sonuc))
    s.append(atom_s5_recete_brans(ilac_sonuc))
    # G4 — doz/fosfor
    s.append(atom_s6_fosfor(ilac_sonuc))
    s.append(atom_s7_doz(ilac_sonuc))
    s.append(atom_s8_belge(ilac_sonuc))
    # G5 — kombinasyon
    s.append(atom_s9_kombinasyon(ilac_sonuc, sinif))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (eritropoietin 4.2.9.A kalıbı)
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


def _mesaj_uret(sonuc: KontrolSonucu, sinif: str, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    parcalar = [f"SUT 4.2.9.B / {sinif.title()}"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — tüm şartlar sağlandı")
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f"ŞARTLI UYGUN — hesaplanabilir şartlar VAR; "
                        f"{len(ke)} şart manuel doğrulama gerektiriyor "
                        f"(başlangıç raporu kriterleri)")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        parcalar.append("UYGUN DEĞİL — " + '; '.join(s.ad for s in yok[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f"ŞÜPHELİ — {len(ke)} şart kontrol edilemedi")
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def sevelamer_fosfor_kontrol_4_2_9_b(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.9.B ana kontrol fonksiyonu (sevelamer/lantanyum/alüminyum klorür
    hidroksit fosfor bağlayıcılar)."""
    sinif = _ilac_sinifi(ilac_sonuc)
    if sinif is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.9.B kapsamı dışı — fosfor bağlayıcı (sevelamer/'
                  'lantanyum/alüminyum klorür hidroksit) değil',
            sut_kurali='SUT 4.2.9.B')

    sartlar = _sartlar_uret(ilac_sonuc, sinif)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sinif, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj, sut_kurali='SUT 4.2.9.B',
        sartlar=sartlar,
        detaylar={'ilac_sinifi': sinif})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (≥10 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("Tam UYGUN (başlangıç metni + Ca×P 80 + nefro + HD + fosfor 5.2)", {
            'etkin_madde': 'SEVELAMER', 'atc_kodu': 'V03AE02',
            'brans': 'Nefroloji', 'rapor_doktor_brans': 'Nefroloji',
            'rapor_kodu': '1234', 'kutu': '1',
            'rapor_metni': 'hemodiyaliz hastası fosfor 5.2 mg/dl tetkik 10.05.2026',
            'baslangic_rapor_metni': 'diğer fosfor düşürücü kalsiyum asetat 3 ay '
                                     'kullanıldı kalsiyum 10 fosfor 8 çarpım 80',
        }, KontrolSonucu.UYGUN),
        ("ŞARTLI (başlangıç bulunamadı, devam reçetesi, fosfor 5)", {
            'etkin_madde': 'SEVELAMER', 'atc_kodu': 'V03AE02',
            'brans': 'Nefroloji', 'rapor_doktor_brans': 'Nefroloji',
            'rapor_kodu': '1234', 'kutu': '1',
            'rapor_metni': 'hemodiyaliz hastası fosfor 5 mg/dl tetkik 10.05.2026',
            'baslangic_durum': 'BASKA_ECZANE_RISKI',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN DEĞİL (fosfor 3.0 < 3.5 → kes)", {
            'etkin_madde': 'SEVELAMER', 'atc_kodu': 'V03AE02',
            'brans': 'Nefroloji', 'rapor_doktor_brans': 'Nefroloji',
            'rapor_kodu': '1234',
            'rapor_metni': 'hemodiyaliz fosfor 3.0 mg/dl',
            'baslangic_durum': 'BASLANGIC',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN DEĞİL (sevelamer + lantanyum kombine — md.5)", {
            'etkin_madde': 'SEVELAMER', 'atc_kodu': 'V03AE02',
            'brans': 'Nefroloji', 'rapor_doktor_brans': 'Nefroloji',
            'rapor_kodu': '1234',
            'rapor_metni': 'hemodiyaliz fosfor 5 mg/dl',
            'diger_ilac_adlari': ['FOSRENOL 500 MG'],
            'baslangic_durum': 'BASLANGIC',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("UYGUN (lantanyum, FOSRENOL, periton, çocuk, ç) Kt/V+PTH)", {
            'etkin_madde': 'LANTANYUM KARBONAT', 'atc_kodu': 'V03AE03',
            'ilac_adi': 'FOSRENOL 750 MG', 'brans': 'Çocuk Sağlığı ve Hastalıkları',
            'rapor_doktor_brans': 'Çocuk Nefroloji', 'rapor_kodu': '99', 'kutu': '1',
            'rapor_metni': 'periton diyaliz fosfor 6 mg/dl tetkik 01.06.2026',
            'baslangic_rapor_metni': 'diğer fosfor düşürücü 3 ay kullanıldı '
                                     'kt/v 1.6 parathormon 320 pg/ml',
        }, KontrolSonucu.UYGUN),
        ("ŞARTLI (başlangıç var ama lab okunamadı, iç hast.)", {
            'etkin_madde': 'SEVELAMER', 'atc_kodu': 'V03AE02',
            'brans': 'İç Hastalıkları', 'rapor_doktor_brans': 'İç Hastalıkları',
            'rapor_kodu': '5', 'kutu': '1',
            'rapor_metni': 'hemodiyaliz fosfor 5.5 mg/dl tetkik 02.06.2026',
            'baslangic_rapor_metni': 'kronik böbrek yetmezliği takip',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN DEĞİL (rapor branş yok — rapor bulunamadı)", {
            'etkin_madde': 'SEVELAMER', 'atc_kodu': 'V03AE02',
            'brans': 'Nefroloji',
            'rapor_metni': 'hemodiyaliz fosfor 5 mg/dl',
            'baslangic_durum': 'BASLANGIC',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("ŞARTLI (reçete kardiyoloji → diyaliz sert.? + başlangıç yok)", {
            'etkin_madde': 'SEVELAMER', 'atc_kodu': 'V03AE02',
            'brans': 'Kardiyoloji', 'rapor_doktor_brans': 'Nefroloji',
            'rapor_kodu': '7', 'kutu': '1',
            'rapor_metni': 'hemodiyaliz fosfor 5 mg/dl tetkik 03.06.2026',
            'baslangic_durum': 'BASKA_ECZANE_RISKI',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("UYGUN (a yolu Ca×P hesap: Ca 11 × P 7 = 77)", {
            'etkin_madde': 'SEVELAMER KARBONAT', 'atc_kodu': 'V03AE02',
            'brans': 'Nefroloji', 'rapor_doktor_brans': 'Nefroloji',
            'rapor_kodu': '8', 'kutu': '1',
            'rapor_metni': 'hemodiyaliz fosfor 7 mg/dl tetkik 04.06.2026',
            'baslangic_rapor_metni': 'diğer fosfor düşürücü ilaç 3 ay '
                                     'kalsiyum 11 fosfor 7',
        }, KontrolSonucu.UYGUN),
        ("ŞARTLI (başlangıç a/b/c/ç hepsi okunamadı ama bulundu)", {
            'etkin_madde': 'SEVELAMER', 'atc_kodu': 'V03AE02',
            'brans': 'Nefroloji', 'rapor_doktor_brans': 'Nefroloji',
            'rapor_kodu': '9', 'kutu': '1',
            'rapor_metni': 'hemodiyaliz fosfor 5 mg/dl tetkik 05.06.2026',
            'baslangic_rapor_metni': 'fosfor düşürücü 3 ay kullanıldı kontrolsüz '
                                     'hiperfosfatemi',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("ŞARTLI (rapor var/branş belirsiz + başlangıç yok + her şey KE)", {
            'etkin_madde': 'SEVELAMER', 'atc_kodu': 'V03AE02',
            'rapor_kodu': '11', 'rapor_doktor_brans': 'Genel Cerrahi',
            'rapor_metni': 'kronik böbrek hastası fosfor 4.8 mg/dl',
            'baslangic_durum': 'BASKA_ECZANE_RISKI',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("Kapsam dışı (kalsiyum asetat — ön-koşul ilacı)", {
            'etkin_madde': 'KALSIYUM ASETAT', 'atc_kodu': 'V03AE07',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.9.B — Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = sevelamer_fosfor_kontrol_4_2_9_b(ilac_sonuc)
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
