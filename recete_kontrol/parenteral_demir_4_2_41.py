# -*- coding: utf-8 -*-
"""SUT 4.2.41 — Parenteral demir preparatları kullanım ilkeleri.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:8306-8324`` (mevzuat.gov.tr,
MevzuatNo=17229; Ek ibare:RG-2/11/2024-32710 + Değişik/Ek ibare:RG-9/5/2024 ve
RG-25/3/2025-32852 → branş listesine "anestezi ve reanimasyon" eklendi).
Protokol: ``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md
``ATOMİK DEVRE ŞEMASI PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
TEK YOLAK (dispatcher yok) — 13 endikasyon VEYA grubu + branş şartları
═══════════════════════════════════════════════════════════════════════════

  Kapsam ilacı: parenteral (IV/IM) demir preparatları.
    ATC öneki  : B03AC  (oral demir B03AA/AB/AD/AE → KAPSAM DIŞI)
    Etken      : demir sukroz, (ferrik/demir) karboksimaltoz, demir
                 izomaltozid / ferrik derizomaltoz, demir dekstran, ferrik
                 glukonat
    Ticari     : VENOFER, FERINJECT/INFERJECT, MONOFER, COSMOFER, FERMED, DIAFER

  SUT lafzı (md.1): Parenteral demir, aşağıdaki (a–k) durumlarında görülen
  DEMİR EKSİKLİĞİ tedavisinde; bu durumların belirtildiği 6 ay süreli
  KARDİYOLOJİ / KADIN HASTALIKLARI VE DOĞUM / GENEL CERRAHİ / İÇ HASTALIKLARI /
  ÇOCUK SAĞLIĞI VE HASTALIKLARI / ANESTEZİ VE REANİMASYON uzmanlarınca
  düzenlenen rapora istinaden BU HEKİMLER tarafından reçete edilir.

  Endikasyonlar (a–k) — VEYA (≥1 yeterli):
    a) İntestinal malabsorbsiyon sendromları
    b) Kronik inflamatuvar bağırsak hastalıkları (Crohn / ÜK; ICD K50/K51)
    c) Aktif GİS kanaması (ICD K92.x)
    ç) Hemodiyaliz hastaları
    d) Total / subtotal gastrektomi
    e) Atrofik gastrit (ICD K29.4)
    f) Oral demir alımını tolere edemeyen hamileler (gebelik + oral intolerans)
    g) Demir eksikliği anemisi + (saturasyon <%20 ve/veya ferritin <100 mcg/l)
       + evre III/IV/V kronik böbrek hastası   ← BİLEŞİK atom (AND)
    ğ) Periton diyaliz hastalarının anemisi
    h) Postpartum anemi
    ı) Cerrahi öncesi / sonrası anemi
    i) Kansere bağlı anemi (ICD C00-C97)
    j) KKY (konjestif kalp yetmezliği) anemisi (ICD I50)
    k) Prediyaliz [evre V KBY] anemisi

═══════════════════════════════════════════════════════════════════════════
BOOLEAN FORMÜL
═══════════════════════════════════════════════════════════════════════════

  UYGUN ⇔ (E_a ∨ E_b ∨ … ∨ E_k)    [Endikasyon, OR ≥1]
          ∧ R1 (rapor branşı ∈ 6 uzman)
          ∧ P1 (reçete branşı ∈ 6 uzman)
          [bilgi: R2 6 ay rapor süresi — matematiği bozmaz]

  • Lab eşiği (TSAT<%20 / ferritin<100) YALNIZ (g) şıkkını kapısı; diğer
    endikasyonlarda SUT lab şartı koymamıştır (örtük kabul / eşik yayma yasak).
  • Endikasyon metinde HİÇ tespit edilemezse → grup YOK → UYGUN DEĞİL
    (pozitif zorunlu şartın yokluğu; kullanıcı kararı 2026-06-04). (g)'de
    klinik var ama lab okunamazsa → atom KE → grup ŞARTLI.

Ana entrypoint: ``parenteral_demir_kontrol_4_2_41(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç sınıfı tespiti (yalnız PARENTERAL demir — oral hariç)
# ═══════════════════════════════════════════════════════════════════════

# ATC öneki: B03AC = "Iron, parenteral preparations" (B03AC01 dekstran,
# B03AC02 sakkarat demir oksit, B03AC06 sukroz, B03AC07 sodyum ferrik glukonat…)
ATC_PARENTERAL = 'B03AC'

# Etken metni — parenteral'e özgü ibareler (oral "demir III hidroksit
# polimaltoz" / "demir sülfat" / "demir glisin sülfat" KATILMAZ).
ETKEN_PARENTERAL: Set[str] = {
    'DEMIR SUKROZ', 'DEMIR HIDROKSIT SUKROZ', 'SUKROZ DEMIR',
    'DEMIR KARBOKSIMALTOZ', 'FERRIK KARBOKSIMALTOZ', 'KARBOKSIMALTOZ',
    'DEMIR IZOMALTOZID', 'DEMIR IZOMALTOZIT', 'IZOMALTOZID',
    'FERRIK DERIZOMALTOZ', 'DERIZOMALTOZ',
    'DEMIR DEKSTRAN', 'FERRIK GLUKONAT', 'DEMIR GLUKONAT', 'SODYUM FERRIK GLUKONAT',
}

# Ticari adlar (hepsi parenteral)
TICARI_PARENTERAL: Set[str] = {
    'VENOFER', 'FERINJECT', 'INFERJECT', 'MONOFER', 'COSMOFER',
    'FERMED', 'DIAFER', 'FERINVOL',
}


# ═══════════════════════════════════════════════════════════════════════
# Branş kümeleri (norm_tr_lower alt-string) — SUT'taki 6 uzman
# ═══════════════════════════════════════════════════════════════════════
UZMAN_BRANSLAR: List[str] = [
    'kardiyolog', 'kardiyoloji',                      # kardiyoloji
    'kadin hast', 'kadin dogum', 'jinekolog', 'dogum',  # kadın hast. ve doğum
    'genel cerrah',                                   # genel cerrahi
    'ic hastalik', 'dahiliye',                        # iç hastalıkları
    'cocuk sagligi', 'cocuk hast', 'pediatri', 'cocuk',  # çocuk sağlığı ve hast.
    'anestezi', 'reanimasyon',                        # anestezi ve reanimasyon
]

GRUP_ENDIKASYON = '(1) Endikasyon (a–k)'
GRUP_RAPOR = '(1) Uzman hekim raporu (6 branş)'
GRUP_RECETE = '(1) Reçete eden branş (6 uzman)'
GRUP_SURE = '(1) Rapor süresi 6 ay (bilgi)'


# ═══════════════════════════════════════════════════════════════════════
# Yardımcılar (eritropoietin_4_2_9_a kalıbı)
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


# SUT-anlatı (threshold/narrative) işaretleri — yakınındaki sayı hastanın
# ölçümü DEĞİL, mevzuat eşiğidir → atla. (eritropoietin ile aynı.)
_NARRATIVE = ("hedef", "altind", "ustun", "uzerin", "ulasi", "asinc", "asan",
              "arasi", "gelinc", "gecinc", "kesil", "baslan", "tutab",
              "'in", "'nin", "'nın", "'yi", "'ye", "'ya", "'a ")


def _lab_deger(metin: str, anahtarlar: List[str]) -> Optional[float]:
    """Rapor metninde anahtar yakınındaki ilk ölçüm değeri (SUT-anlatı atlanır)."""
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


def _ilac_sinifi(ilac_sonuc: Dict) -> Optional[str]:
    """Parenteral demir mi? → 'DEMIR_PARENTERAL' | None.

    ATC önekiyle (B03AC) ayırt edilir; oral demir (B03AA/AB/AD/AE) None döner.
    ATC yoksa etken/ticari ada düşer.
    """
    atc = norm_tr_upper(ilac_sonuc.get('atc_kodu') or ilac_sonuc.get('atc') or '')
    if atc.startswith(ATC_PARENTERAL):
        return 'DEMIR_PARENTERAL'
    if atc and atc.startswith('B03A') and not atc.startswith(ATC_PARENTERAL):
        # Oral demir (B03AA/AB/AD/AE) — açıkça kapsam dışı
        return None
    m = _arama_metni(ilac_sonuc)
    if _iceriyor(m, TICARI_PARENTERAL) or _iceriyor(m, ETKEN_PARENTERAL):
        return 'DEMIR_PARENTERAL'
    return None


# ═══════════════════════════════════════════════════════════════════════
# ENDİKASYON ATOMLARI (a–k) — hepsi VEYA grubu
# ═══════════════════════════════════════════════════════════════════════

def _endik_var(metin: str, icd: str, keywords: List[str],
               icd_patterns: List[str]) -> Tuple[bool, str]:
    """Basit pozitif endikasyon: keyword (metin) ∨ ICD öneki bulundu mu?"""
    for kw in keywords:
        if kw in metin:
            return True, f"rapor: '{kw}'"
    for pat in icd_patterns:
        if re.search(pat, icd):
            return True, f"ICD: {pat.replace(chr(92)+'b', '').strip()}"
    return False, ''


# (label, keywords[norm_tr_lower], icd_patterns[norm_tr_upper regex])
_BASIT_ENDIKASYONLAR: List[Tuple[str, str, List[str], List[str]]] = [
    ('a', 'İntestinal malabsorbsiyon sendromu',
     ['intestinal malabsorbsiyon', 'malabsorbsiyon', 'malabsorpsiyon',
      'emilim bozuklugu'], []),
    ('b', 'Kronik inflamatuar bağırsak hastalığı',
     ['kronik inflamatuar bagirsak', 'inflamatuar bagirsak', 'inflamatuar barsak',
      'crohn', 'ulseratif kolit'], [r'\bK50', r'\bK51']),
    ('c', 'Aktif GİS kanaması',
     ['aktif gis kanama', 'gastrointestinal kanama', 'gis kanama',
      'sindirim sistemi kanama', 'mide kanama'], [r'\bK92']),
    ('ç', 'Hemodiyaliz hastası',
     ['hemodiyaliz'], [r'\bZ99\.?2']),
    ('d', 'Total / subtotal gastrektomi',
     ['gastrektomi', 'mide rezeksiyon'], [r'\bZ90\.?3']),
    ('e', 'Atrofik gastrit',
     ['atrofik gastrit'], [r'\bK29\.?4']),
    ('ğ', 'Periton diyaliz anemisi',
     ['periton diyaliz', 'sapd', 'capd'], []),
    ('h', 'Postpartum anemi',
     ['postpartum', 'dogum sonrasi anemi', 'lohusa anemi'], []),
    ('ı', 'Cerrahi öncesi / sonrası anemi',
     ['cerrahi oncesi', 'cerrahi sonrasi', 'ameliyat oncesi', 'ameliyat sonrasi',
      'preoperatif', 'postoperatif', 'perioperatif'], []),
    ('i', 'Kansere bağlı anemi',
     ['kansere bagli anemi', 'maligniteye bagli anemi', 'kanser anemi',
      'kemoterapiye bagli anemi'], [r'\bC[0-9]{2}', r'\bD46']),
    ('j', 'KKY (konjestif kalp yetmezliği) anemisi',
     ['konjestif kalp yetmezligi', 'kalp yetmezligi', 'kky'], [r'\bI50']),
    ('k', 'Prediyaliz (evre V KBY) anemisi',
     ['prediyaliz', 'pre diyaliz', 'pre-diyaliz', 'son donem bobrek',
      'evre v kby', 'evre 5 kby'], []),
]


def _atom_basit_endikasyon(ilac_sonuc: Dict, sif: str, label: str,
                           keywords: List[str], icd_patterns: List[str]) -> SartSonuc:
    metin = _rapor_metni(ilac_sonuc)
    icd = _teshis_birlesik(ilac_sonuc)
    var, neden = _endik_var(metin, icd, keywords, icd_patterns)
    durum = SartDurumu.VAR if var else SartDurumu.YOK
    return SartSonuc(
        ad=f'({sif}) {label}', durum=durum,
        neden=neden if var else 'rapor/teşhiste bu endikasyon ibaresi bulunamadı',
        kaynak='rapor+ICD', grup=GRUP_ENDIKASYON, veya_grubu=True)


def _atom_f_hamile_oral_intolerans(ilac_sonuc: Dict) -> SartSonuc:
    """(f) Oral demir alımını tolere edemeyen hamile (gebelik + oral intolerans)."""
    metin = _rapor_metni(ilac_sonuc)
    icd = _teshis_birlesik(ilac_sonuc)
    gebe = any(k in metin for k in ('gebe', 'hamile', 'gebelik')) \
        or re.search(r'\bO[0-9]{2}', icd) is not None or 'z34' in metin
    oral_intol = any(k in metin for k in (
        'oral demir', 'oral tedavi', 'tolere edem', 'intolerans',
        'oral demiri tolere', 'oral demir alimi'))
    if gebe and oral_intol:
        return SartSonuc(ad='(f) Oral demir tolere edemeyen hamile',
                         durum=SartDurumu.VAR,
                         neden='rapor: gebelik + oral demir intoleransı',
                         kaynak='rapor', grup=GRUP_ENDIKASYON, veya_grubu=True)
    if gebe and not oral_intol:
        return SartSonuc(ad='(f) Oral demir tolere edemeyen hamile',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='gebelik var ama oral demir intoleransı ibaresi '
                               'bulunamadı — manuel doğrula',
                         kaynak='rapor', grup=GRUP_ENDIKASYON, veya_grubu=True,
                         sartli_atom=True)
    return SartSonuc(ad='(f) Oral demir tolere edemeyen hamile',
                     durum=SartDurumu.YOK,
                     neden='gebelik + oral intolerans ibaresi bulunamadı',
                     kaynak='rapor', grup=GRUP_ENDIKASYON, veya_grubu=True)


def _atom_g_kby_demir_eksikligi(ilac_sonuc: Dict) -> SartSonuc:
    """(g) IDA ∧ evre III/IV/V KBH ∧ (TSAT<%20 ∨ ferritin<100) — bileşik."""
    metin = _rapor_metni(ilac_sonuc)
    icd = _teshis_birlesik(ilac_sonuc)
    ida = any(k in metin for k in ('demir eksikligi anemisi', 'demir eksikligi',
                                   'ida', 'demir eksigi'))
    # Evre III/IV/V KBH — ICD N18.3/4/5 veya metinde evre 3/4/5 + böbrek
    n18_evre = re.search(r'\bN18\.?[345]', icd) is not None
    metin_evre = (('kronik bobrek' in metin or 'kbh' in metin or 'kby' in metin)
                  and re.search(r'evre\s*(iii|iv|v|3|4|5)', metin) is not None)
    ckd35 = n18_evre or metin_evre
    if not (ida and ckd35):
        return SartSonuc(ad='(g) IDA + evre III-V KBH + demir parametreleri',
                         durum=SartDurumu.YOK,
                         neden='demir eksikliği anemisi + evre III/IV/V KBH '
                               'ibaresi birlikte bulunamadı',
                         kaynak='rapor+ICD', grup=GRUP_ENDIKASYON, veya_grubu=True)
    tsat = _lab_deger(metin, ['tsat', 'transferrin satur', 'satürasyon', 'saturasyon'])
    ferritin = _lab_deger(metin, ['ferritin'])
    if tsat is None and ferritin is None:
        return SartSonuc(ad='(g) IDA + evre III-V KBH + (TSAT<%20 / ferritin<100)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='IDA + evre III-V KBH var; TSAT/ferritin rapor '
                               'metninden okunamadı — manuel doğrula',
                         kaynak='rapor+lab', grup=GRUP_ENDIKASYON, veya_grubu=True,
                         sartli_atom=True)
    uygun = (tsat is not None and tsat < 20) or (ferritin is not None and ferritin < 100)
    if uygun:
        return SartSonuc(ad='(g) IDA + evre III-V KBH + (TSAT<%20 / ferritin<100)',
                         durum=SartDurumu.VAR,
                         neden=f"TSAT={tsat if tsat is not None else '?'} "
                               f"ferritin={ferritin if ferritin is not None else '?'} "
                               f"— demir eksikliği kriteri sağlandı",
                         kaynak='rapor+lab', grup=GRUP_ENDIKASYON, veya_grubu=True)
    return SartSonuc(ad='(g) IDA + evre III-V KBH + (TSAT<%20 / ferritin<100)',
                     durum=SartDurumu.YOK,
                     neden=f"TSAT={tsat if tsat is not None else '?'} "
                           f"ferritin={ferritin if ferritin is not None else '?'} "
                           f"— TSAT<%20 / ferritin<100 kriteri sağlanmadı",
                     kaynak='rapor+lab', grup=GRUP_ENDIKASYON, veya_grubu=True)


def _endikasyon_atomlari(ilac_sonuc: Dict) -> List[SartSonuc]:
    s: List[SartSonuc] = []
    for sif, label, kws, icds in _BASIT_ENDIKASYONLAR:
        s.append(_atom_basit_endikasyon(ilac_sonuc, sif, label, kws, icds))
    s.append(_atom_f_hamile_oral_intolerans(ilac_sonuc))
    s.append(_atom_g_kby_demir_eksikligi(ilac_sonuc))
    return s


# ═══════════════════════════════════════════════════════════════════════
# BRANŞ / RAPOR ATOMLARI (R1, P1, R2)
# ═══════════════════════════════════════════════════════════════════════

def _atom_rapor_brans(ilac_sonuc: Dict) -> SartSonuc:
    """R1: rapor düzenleyen 6 uzmandan biri mi?"""
    rb = (ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans')
          or '').strip()
    heyet = _heyet_brans_listesi(ilac_sonuc)
    adaylar = [rb] + heyet
    rapor_kodu = (ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
    rapor_takip = (ilac_sonuc.get('rapor_takip_no') or ilac_sonuc.get('rap_tak_no')
                   or '').strip()
    rapor_var = bool(rapor_kodu or rapor_takip or any(adaylar))
    if any(_brans_listede(b, UZMAN_BRANSLAR) for b in adaylar):
        return SartSonuc(ad='Uzman hekim raporu (6 branştan biri)',
                         durum=SartDurumu.VAR,
                         neden=f'Rapor yetkili uzman branşında ({rb or "heyet"})',
                         kaynak='rapor_brans', grup=GRUP_RAPOR)
    if rb:  # branş biliniyor ama 6 uzmandan değil
        return SartSonuc(ad='Uzman hekim raporu (6 branştan biri)',
                         durum=SartDurumu.YOK,
                         neden=f'Rapor branşı yetkili 6 uzmandan değil: {rb}',
                         kaynak='rapor_brans', grup=GRUP_RAPOR)
    if not rapor_var:
        return SartSonuc(ad='Uzman hekim raporu (6 branştan biri)',
                         durum=SartDurumu.YOK,
                         neden='Reçeteye bağlı uzman hekim raporu bulunamadı',
                         kaynak='rapor', grup=GRUP_RAPOR)
    return SartSonuc(ad='Uzman hekim raporu (6 branştan biri)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor mevcut ama düzenleyen branş okunamadı — manuel',
                     kaynak='rapor_brans', grup=GRUP_RAPOR, sartli_atom=True)


def _atom_recete_brans(ilac_sonuc: Dict) -> SartSonuc:
    """P1: reçete eden 6 uzmandan biri mi?"""
    brans = (ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or '').strip()
    if not brans:
        return SartSonuc(ad='Reçete eden branş (6 uzmandan biri)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=GRUP_RECETE, sartli_atom=True)
    if _brans_listede(brans, UZMAN_BRANSLAR):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Kardiyoloji/kadın doğum/genel cerrahi/iç hast./'
                               'çocuk/anestezi — yetkili',
                         kaynak='hekim_brans', grup=GRUP_RECETE)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Yalnız kardiyoloji, kadın hast.&doğum, genel cerrahi, '
                           'iç hast., çocuk veya anestezi-reanimasyon reçete edebilir',
                     kaynak='hekim_brans', grup=GRUP_RECETE)


def _atom_rapor_suresi(ilac_sonuc: Dict) -> SartSonuc:
    """R2 (bilgi): 6 ay süreli rapor — parse edilemez, manuel."""
    return SartSonuc(ad='Rapor süresi 6 ay', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor süresi (6 ay) reçete verisinden okunamıyor — manuel',
                     kaynak='rapor', grup=GRUP_SURE, sartli_atom=True)


def _tum_atomlar(ilac_sonuc: Dict) -> List[SartSonuc]:
    s = _endikasyon_atomlari(ilac_sonuc)
    s.append(_atom_rapor_brans(ilac_sonuc))
    s.append(_atom_recete_brans(ilac_sonuc))
    s.append(_atom_rapor_suresi(ilac_sonuc))
    return s


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ (eritropoietin kalıbı)
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
    parcalar = ["SUT 4.2.41 / Parenteral demir"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — endikasyon + rapor branşı + reçete branşı sağlandı")
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append(f"ŞARTLI UYGUN — hesaplanabilir şartlar VAR; "
                        f"{len(ke)} şart manuel doğrulama gerektiriyor")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        # Endikasyon grubu YOK ise özel mesaj
        endik_yok = any(s.grup == GRUP_ENDIKASYON and s.durum != SartDurumu.VAR
                        for s in sartlar) and not any(
            s.grup == GRUP_ENDIKASYON and s.durum == SartDurumu.VAR for s in sartlar)
        nedenler = []
        if endik_yok:
            nedenler.append("(a–k) endikasyonlarından hiçbiri tespit edilemedi")
        nedenler.extend(s.ad for s in yok if s.grup != GRUP_ENDIKASYON)
        parcalar.append("UYGUN DEĞİL — " + '; '.join(nedenler[:3]))
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f"ŞÜPHELİ — {len(ke)} şart kontrol edilemedi")
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

def parenteral_demir_kontrol_4_2_41(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.41 ana kontrol fonksiyonu (parenteral demir preparatları)."""
    sinif = _ilac_sinifi(ilac_sonuc)
    if sinif is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.41 kapsamı dışı — parenteral demir (B03AC) değil',
            sut_kurali='SUT 4.2.41')

    sartlar = _tum_atomlar(ilac_sonuc)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj, sut_kurali='SUT 4.2.41',
        sartlar=sartlar,
        detaylar={'ilac_sinifi': sinif})


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ (≥10 senaryo)
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    return [
        ("Hemodiyaliz + nefro? hayır — iç hast. rapor+reçete (ç) UYGUN", {
            'etkin_madde': 'DEMIR SUKROZ', 'atc_kodu': 'B03AC',
            'brans': 'İç Hastalıkları', 'rapor_doktor_brans': 'İç Hastalıkları',
            'rapor_kodu': '1234',
            'rapor_metni': 'hemodiyaliz hastası demir eksikliği tedavisi',
        }, KontrolSonucu.UYGUN),
        ("Kansere bağlı anemi + kadın doğum (Ferinject) UYGUN", {
            'ilac_adi': 'FERINJECT', 'atc_kodu': 'B03AC',
            'brans': 'Kadın Hastalıkları ve Doğum',
            'rapor_doktor_brans': 'Kadın Hastalıkları ve Doğum', 'rapor_kodu': '55',
            'recete_teshisleri': ['C50.9'],
            'rapor_metni': 'meme kanseri kemoterapiye bağlı anemi',
        }, KontrolSonucu.UYGUN),
        ("Postpartum anemi + genel cerrahi reçete UYGUN", {
            'etkin_madde': 'FERRIK KARBOKSIMALTOZ', 'atc_kodu': 'B03AC07',
            'brans': 'Genel Cerrahi', 'rapor_doktor_brans': 'Genel Cerrahi',
            'rapor_kodu': '7',
            'rapor_metni': 'postpartum dönemde gözlenen anemi',
        }, KontrolSonucu.UYGUN),
        ("(g) tam: IDA+evre IV KBH+ferritin80 + nefro? hayır iç hast UYGUN", {
            'etkin_madde': 'DEMIR KARBOKSIMALTOZ', 'atc_kodu': 'B03AC',
            'brans': 'İç Hastalıkları', 'rapor_doktor_brans': 'İç Hastalıkları',
            'rapor_kodu': '9', 'recete_teshisleri': ['N18.4'],
            'rapor_metni': 'demir eksikliği anemisi evre 4 kronik böbrek '
                           'hastalığı ferritin 80 tsat %25',
        }, KontrolSonucu.UYGUN),
        ("(g) klinik var ama lab yok → ŞARTLI", {
            'etkin_madde': 'DEMIR SUKROZ', 'atc_kodu': 'B03AC',
            'brans': 'İç Hastalıkları', 'rapor_doktor_brans': 'İç Hastalıkları',
            'rapor_kodu': '9', 'recete_teshisleri': ['N18.5'],
            'rapor_metni': 'demir eksikliği anemisi evre 5 kronik böbrek hastalığı',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("(g) lab eşik üstü (ferritin150,tsat30) + başka endikasyon yok → UYGUN DEĞİL", {
            'etkin_madde': 'DEMIR SUKROZ', 'atc_kodu': 'B03AC',
            'brans': 'İç Hastalıkları', 'rapor_doktor_brans': 'İç Hastalıkları',
            'rapor_kodu': '9', 'recete_teshisleri': ['N18.3'],
            'rapor_metni': 'demir eksikligi anemisi evre 3 kronik bobrek hastaligi '
                           'ferritin 150 tsat %30',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Endikasyon hiç yok → UYGUN DEĞİL", {
            'etkin_madde': 'DEMIR SUKROZ', 'atc_kodu': 'B03AC',
            'brans': 'İç Hastalıkları', 'rapor_doktor_brans': 'İç Hastalıkları',
            'rapor_kodu': '9', 'rapor_metni': 'demir tedavisi başlandı',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Endikasyon var ama reçete branşı yetkisiz (nöroloji) → UYGUN DEĞİL", {
            'etkin_madde': 'DEMIR SUKROZ', 'atc_kodu': 'B03AC',
            'brans': 'Nöroloji', 'rapor_doktor_brans': 'İç Hastalıkları',
            'rapor_kodu': '9', 'rapor_metni': 'hemodiyaliz hastası',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Endikasyon var ama rapor branşı yetkisiz → UYGUN DEĞİL", {
            'etkin_madde': 'DEMIR SUKROZ', 'atc_kodu': 'B03AC',
            'brans': 'İç Hastalıkları', 'rapor_doktor_brans': 'Nöroloji',
            'rapor_kodu': '9', 'rapor_metni': 'hemodiyaliz hastası',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Endikasyon var, rapor yok → UYGUN DEĞİL", {
            'etkin_madde': 'DEMIR SUKROZ', 'atc_kodu': 'B03AC',
            'brans': 'İç Hastalıkları', 'rapor_metni': 'hemodiyaliz hastası',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("Crohn (IBD) + çocuk uzmanı UYGUN (b, ICD K50)", {
            'etkin_madde': 'DEMIR IZOMALTOZID', 'atc_kodu': 'B03AC',
            'brans': 'Çocuk Sağlığı ve Hastalıkları',
            'rapor_doktor_brans': 'Çocuk Sağlığı ve Hastalıkları', 'rapor_kodu': '3',
            'recete_teshisleri': ['K50.0'], 'rapor_metni': 'crohn hastalığı anemi',
        }, KontrolSonucu.UYGUN),
        ("Anestezi-reanimasyon + cerrahi öncesi anemi (2025 ek branş) UYGUN", {
            'ilac_adi': 'MONOFER', 'atc_kodu': 'B03AC',
            'brans': 'Anestezi ve Reanimasyon',
            'rapor_doktor_brans': 'Anestezi ve Reanimasyon', 'rapor_kodu': '12',
            'rapor_metni': 'cerrahi öncesi gözlenen anemi',
        }, KontrolSonucu.UYGUN),
        ("(f) gebe + oral demir intoleransı + kadın doğum UYGUN", {
            'etkin_madde': 'DEMIR SUKROZ', 'atc_kodu': 'B03AC',
            'brans': 'Kadın Hastalıkları ve Doğum',
            'rapor_doktor_brans': 'Kadın Hastalıkları ve Doğum', 'rapor_kodu': '4',
            'rapor_metni': 'gebe hasta oral demir tedavisini tolere edemiyor intolerans',
        }, KontrolSonucu.UYGUN),
        ("Oral demir (B03AB) → ATLANDI", {
            'etkin_madde': 'DEMIR III HIDROKSIT POLIMALTOZ', 'atc_kodu': 'B03AB05',
            'ilac_adi': 'MALTOFER', 'brans': 'İç Hastalıkları',
            'rapor_metni': 'hemodiyaliz',
        }, KontrolSonucu.ATLANDI),
        ("Kapsam dışı (parasetamol) → ATLANDI", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.41 — Parenteral Demir Akıl Testi\n" + "=" * 60)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = parenteral_demir_kontrol_4_2_41(ilac_sonuc)
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
