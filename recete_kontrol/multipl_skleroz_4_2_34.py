# -*- coding: utf-8 -*-
"""SUT 4.2.34 — Multipl Skleroz hastalığında ilaç kullanım ilkeleri.

Resmî SUT lafzı: ``docs/sut/SUT_tam_metin.txt:8080-8165`` (mevzuat.gov.tr,
MevzuatNo=17229). 9 etken madde / 7 ilaç-yolağı. Protokol:
``docs/SUT_MANTIK_SEMA_PROTOKOLU.md`` + CLAUDE.md ``ATOMİK DEVRE ŞEMASI
PRENSİPLERİ``.

═══════════════════════════════════════════════════════════════════════════
ETKEN MADDE → YOLAK DİSPATCHER
═══════════════════════════════════════════════════════════════════════════

  BIRINCI     → 4.2.34(1): beta interferon, glatiramer asetat, teriflunomid,
                dimetil fumarat (birinci basamak DMT'ler).
  FINGOLIMOD  → 4.2.34(4): (a) yüksek aktivite yolu  VEYA (b) EDSS≤5,5 RRMS.
  NATALIZUMAB → 4.2.34(5): (a) yüksek aktivite yolu  VEYA (b) EDSS≤5,5 RRMS.
  OKRELIZUMAB → 4.2.34(6): (a) yüksek aktivite  VEYA (b) EDSS≤7 RRMS
                VEYA (c) EDSS≤7 primer progresif MS.
  KLADRIBIN   → 4.2.34(7): (a) EDSS≤5,5 RRMS +≥2 kriter  VEYA
                (b) EDSS≤7 RRMS + önceki DMT yetersiz +≥2 kriter;  (c) ortak
                3.basamak/nöro/1yıl;  (f) vücut ağırlığı (bilgi).
  ALEMTUZUMAB → 4.2.34(8): (a) önceki 2.basamak DMT yetersiz +≥2 kriter
                VEYA (b) EDSS≤7 RRMS.
  FAMPIRIDIN  → 4.2.34(9): güncel MS + EDSS≥4 (≥7 sonlandırılır); 3.basamak
                nöro rapor + reçete nöro. (madde-3 kombinasyon yasağından HARİÇ.)

═══════════════════════════════════════════════════════════════════════════
ORTAK ŞARTLAR (her yolakta)
═══════════════════════════════════════════════════════════════════════════
  • Üçüncü basamak sağlık hizmeti sunucusu (rapor düzenlenen) ......... A3
  • Nöroloji uzman hekiminin düzenlediği rapor ....................... A4
  • Rapor en fazla 1 yıl süreli ..................................... A5
  • Reçeteyi nöroloji uzman hekimi düzenlemiş ....................... A6
  • (madde 2)  Klinik İzole Sendrom (KİS) DEĞİL  [NEGATİF] .......... G2
  • (madde 3)  Başka MS DMT ile kombine kullanım YOK [NEGATİF] ...... G3
                (fampiridin hariç — fampiridin G3'e tabi değil)

EDSS politikası (kullanıcı kararı: "basit eşik"):
  esik altı → VAR ; (esik, sonlandır] → KE+şartlı (devam tedavisi olabilir) ;
  sonlandır üstü → YOK ; rapor sessiz → KE (ŞÜPHELİ).
A3 (3.basamak) ve A5 (1 yıl) (kullanıcı kararı: "hesaba tam kat"): parse
edilemezse `sartli_atom=False` → ŞÜPHELİ (örtük kabul YASAK).

═══════════════════════════════════════════════════════════════════════════
ÜST-VEYA (alternatif yollar)
═══════════════════════════════════════════════════════════════════════════
Grup adındaki ``‖Pn‖`` etiketi aynı alternatif yolu işaretler. Aynı etiketli
gruplar AND, farklı etiketler arası ÜST-VEYA (≥1 yol VAR → o blok VAR).
Etiketsiz gruplar ortak (AND) şartlardır.

Ana entrypoint: ``multipl_skleroz_kontrol_4_2_34(ilac_sonuc)`` → ``KontrolRaporu``.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İLAÇ SINIFI listeleri (etken + ticari ad). ATC sınıflaması zaman içinde
# değiştiği için (L04AA → L04AE/AG geçişleri) etken/ad metni esastır.
# ═══════════════════════════════════════════════════════════════════════

DRUG_DEFS: Dict[str, Tuple[Set[str], Set[str]]] = {
    'BIRINCI_BETA_IFN': (
        {'INTERFERON BETA', 'INTERFERON BETA-1A', 'INTERFERON BETA-1B',
         'INTERFERON BETA 1A', 'INTERFERON BETA 1B', 'PEGINTERFERON BETA',
         'PEGINTERFERON BETA-1A', 'BETA INTERFERON', 'BETA-1A', 'BETA-1B'},
        {'AVONEX', 'REBIF', 'BETAFERON', 'BETASERON', 'EXTAVIA', 'PLEGRIDY'},
    ),
    'BIRINCI_GLATIRAMER': (
        {'GLATIRAMER', 'GLATIRAMER ASETAT', 'GLATIRAMER ACETATE'},
        {'COPAXONE', 'GLATIRA', 'REMUREL', 'GLATILEX'},
    ),
    'BIRINCI_TERIFLUNOMID': (
        {'TERIFLUNOMID', 'TERIFLUNOMIDE'},
        {'AUBAGIO', 'TERIFLEX'},
    ),
    'BIRINCI_DIMETIL': (
        {'DIMETIL FUMARAT', 'DIMETILFUMARAT', 'DIMETHYL FUMARATE',
         'DIMETIL FUMARATE'},
        {'TECFIDERA', 'DIMESERA', 'SKILARENCE'},
    ),
    'FINGOLIMOD': (
        {'FINGOLIMOD'},
        {'GILENYA', 'FINGOMEL', 'FINGOTACT'},
    ),
    'NATALIZUMAB': (
        {'NATALIZUMAB'},
        {'TYSABRI'},
    ),
    'OKRELIZUMAB': (
        {'OKRELIZUMAB', 'OCRELIZUMAB'},
        {'OCREVUS'},
    ),
    'KLADRIBIN': (
        {'KLADRIBIN', 'CLADRIBINE', 'CLADRIBIN'},
        {'MAVENCLAD'},
    ),
    'ALEMTUZUMAB': (
        {'ALEMTUZUMAB'},
        {'LEMTRADA'},
    ),
    'FAMPIRIDIN': (
        {'FAMPIRIDIN', 'FAMPRIDIN', 'FAMPRIDINE', 'DALFAMPRIDINE',
         '4-AMINOPIRIDIN'},
        {'FAMPYRA'},
    ),
}

# Dispatcher anahtarı → yolak kimliği (birinci-basamak 4 etken aynı yolak)
DRUG_KEY_TO_YOLAK = {
    'BIRINCI_BETA_IFN': 'BIRINCI',
    'BIRINCI_GLATIRAMER': 'BIRINCI',
    'BIRINCI_TERIFLUNOMID': 'BIRINCI',
    'BIRINCI_DIMETIL': 'BIRINCI',
    'FINGOLIMOD': 'FINGOLIMOD',
    'NATALIZUMAB': 'NATALIZUMAB',
    'OKRELIZUMAB': 'OKRELIZUMAB',
    'KLADRIBIN': 'KLADRIBIN',
    'ALEMTUZUMAB': 'ALEMTUZUMAB',
    'FAMPIRIDIN': 'FAMPIRIDIN',
}

# Birinci-basamak DMT adları (rapor metninde "önceki tedavi" taraması için)
FIRST_LINE_KEYWORDS = (
    'interferon', 'glatiramer', 'teriflunomid', 'dimetil fumarat',
    'dimetilfumarat', 'avonex', 'rebif', 'betaferon', 'extavia', 'plegridy',
    'copaxone', 'aubagio', 'tecfidera',
)
# İkinci-basamak (alemtuzumab 8a önceki tedavi: fingolimod/natalizumab/
# kladribin/okrelizumab)
SECOND_LINE_KEYWORDS = (
    'fingolimod', 'gilenya', 'natalizumab', 'tysabri', 'kladribin',
    'mavenclad', 'okrelizumab', 'ocrelizumab', 'ocrevus',
)

# madde-3 kombinasyon yasağı kapsamındaki tüm DMT'ler (fampiridin HARİÇ)
COMBINE_DMT_KEYS = [k for k in DRUG_DEFS if k != 'FAMPIRIDIN']

# Branş anahtarları (norm_tr_lower alt-string)
NOROLOJI = ('noroloji', 'norolog', 'sinir hastalik')


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
    """Rapor + reçete açıklama/teşhis metinlerinin norm_tr_lower birleşimi."""
    parcalar: List[str] = []
    for anahtar in ('rapor_metni', 'tum_metin', 'rapor_kodu_aciklama',
                    'rap_ack', 'rec_ack', 'rap_tesh', 'rec_tesh'):
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


def _heyet_brans_listesi(ilac_sonuc: Dict) -> List[str]:
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not isinstance(heyet, (list, tuple)):
        return []
    return [h.get('brans') or '' for h in heyet if (h.get('ad') or h.get('brans'))]


def _rapor_var(ilac_sonuc: Dict) -> bool:
    return bool((ilac_sonuc.get('rapor_kodu') or ilac_sonuc.get('rap_kod') or '').strip()
                or (ilac_sonuc.get('rapor_takip_no') or ilac_sonuc.get('rap_tak_no') or '').strip())


def _rapor_brans_adaylar(ilac_sonuc: Dict) -> List[str]:
    rb = ilac_sonuc.get('rapor_doktor_brans') or ilac_sonuc.get('rapor_dr_brans') or ''
    return [rb] + _heyet_brans_listesi(ilac_sonuc)


_EDSS_RE = re.compile(r'edss[^\d]{0,20}(\d+(?:[.,]\d+)?)')


def _edss_deger(ilac_sonuc: Dict) -> Optional[float]:
    metin = _rapor_metni(ilac_sonuc)
    m = _EDSS_RE.search(metin)
    if not m:
        return None
    try:
        return float(m.group(1).replace(',', '.'))
    except ValueError:
        return None


def _ms_tani(ilac_sonuc: Dict) -> bool:
    icd = _teshis_birlesik(ilac_sonuc)
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'\bG35', icd):
        return True
    return ('multipl skleroz' in metin or 'multiple sclerosis' in metin
            or 'multipl sikleroz' in metin)


def _diger_ilac_metni(ilac_sonuc: Dict) -> Tuple[Optional[str], bool]:
    """Reçetedeki diğer ilaç adlarının norm_tr_upper birleşimi + alan var mı?

    (metin, alan_mevcut). Alan tamamen yoksa (None, False) → KE; varsa ama
    boşsa ('', True) → kombinasyon yok kabul edilir.
    """
    adlar: List[str] = []
    alan_var = False
    for anahtar in ('recete_ilaclari', 'diger_ilac_adlari', 'diger_ilaclar'):
        v = ilac_sonuc.get(anahtar)
        if v is None:
            continue
        alan_var = True
        if isinstance(v, (list, tuple)):
            for x in v:
                if isinstance(x, dict):
                    adlar.append(str(x.get('ad') or x.get('ilac') or ''))
                elif x:
                    adlar.append(str(x))
        elif v:
            adlar.append(str(v))
    if not alan_var:
        return None, False
    return norm_tr_upper(' '.join(a for a in adlar if a)), True


def _tarih_parse(deger) -> Optional[datetime]:
    if not deger:
        return None
    s = str(deger).strip()[:10]
    for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%Y.%m.%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ═══════════════════════════════════════════════════════════════════════
# DİSPATCHER
# ═══════════════════════════════════════════════════════════════════════

def _drug_key_belirle(ilac_sonuc: Dict) -> Optional[str]:
    m = _arama_metni(ilac_sonuc)
    for key, (etken, ticari) in DRUG_DEFS.items():
        if _iceriyor(m, etken) or _iceriyor(m, ticari):
            return key
    return None


def ms_yolak_belirle(ilac_sonuc: Dict) -> Optional[str]:
    """Kapsam içi mi + hangi yolak? → yolak kimliği | None (ATLANDI)."""
    key = _drug_key_belirle(ilac_sonuc)
    if key is None:
        return None
    return DRUG_KEY_TO_YOLAK[key]


# ═══════════════════════════════════════════════════════════════════════
# ATOMLAR
# ═══════════════════════════════════════════════════════════════════════

def atom_edss_max(ilac_sonuc: Dict, esik: float, grup: str,
                  sartli_band: Optional[float] = None) -> SartSonuc:
    """EDSS ≤ esik → VAR; (esik, sartli_band] → KE+şartlı (devam tedavisi);
    sartli_band üstü (ya da sartli_band yoksa esik üstü) → YOK; sessiz → KE."""
    val = _edss_deger(ilac_sonuc)
    ad = f'EDSS ≤ {esik:g}'.replace('.', ',')
    if val is None:
        return SartSonuc(ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='EDSS değeri raporda okunamadı — manuel',
                         kaynak='rapor_metni', grup=grup)
    val_s = f'{val:g}'.replace('.', ',')
    if val <= esik:
        return SartSonuc(ad=f'EDSS {val_s} (≤ {esik:g})'.replace('.', ','),
                         durum=SartDurumu.VAR,
                         neden=f'EDSS {val_s} başlama eşiği ({esik:g}) altında'.replace('.', ','),
                         kaynak='rapor_metni', grup=grup)
    if sartli_band is not None and val <= sartli_band:
        return SartSonuc(ad=f'EDSS {val_s}', durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden=(f'EDSS {val_s} başlama eşiği {esik:g} üstü ama '
                                f'≤ {sartli_band:g} — devam tedavisi olabilir, '
                                f'manuel').replace('.', ','),
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    ust = sartli_band if sartli_band is not None else esik
    return SartSonuc(ad=f'EDSS {val_s}', durum=SartDurumu.YOK,
                     neden=f'EDSS {val_s} > {ust:g} — tedavi sonlandırılmalı/uygun değil'.replace('.', ','),
                     kaynak='rapor_metni', grup=grup)


def atom_edss_fampiridin(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Fampiridin: EDSS ≥4 VAR; <4 → YOK; ≥7 → YOK (sonlandır); sessiz → KE."""
    val = _edss_deger(ilac_sonuc)
    if val is None:
        return SartSonuc(ad='EDSS ≥ 4 (≥7 sonlandırılır)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='EDSS değeri raporda okunamadı — manuel',
                         kaynak='rapor_metni', grup=grup)
    val_s = f'{val:g}'.replace('.', ',')
    if val >= 7:
        return SartSonuc(ad=f'EDSS {val_s}', durum=SartDurumu.YOK,
                         neden=f'EDSS {val_s} ≥ 7 — fampiridin tedavisi sonlandırılır',
                         kaynak='rapor_metni', grup=grup)
    if val >= 4:
        return SartSonuc(ad=f'EDSS {val_s} (≥ 4)', durum=SartDurumu.VAR,
                         neden=f'EDSS {val_s} ≥ 4 — fampiridin endikasyonu',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad=f'EDSS {val_s}', durum=SartDurumu.YOK,
                     neden=f'EDSS {val_s} < 4 — fampiridin endikasyonu yok',
                     kaynak='rapor_metni', grup=grup)


def atom_rrms(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Relaps-remisyonla seyreden (RRMS) güncel MS tanısı."""
    metin = _rapor_metni(ilac_sonuc)
    poz = ('rrms' in metin
           or ('relaps' in metin and 'remisyon' in metin)
           or 'relapsing remitting' in metin
           or 'relapsing-remitting' in metin
           or 'ataklarla seyreden' in metin
           or 'yineleyici-duzelen' in metin)
    if poz:
        return SartSonuc(ad='Relaps-remisyonla seyreden MS (RRMS)',
                         durum=SartDurumu.VAR,
                         neden='Raporda RRMS / relaps-remisyon ibaresi',
                         kaynak='rapor_metni', grup=grup)
    if ('primer progresif' in metin or 'primary progressive' in metin
            or 'sekonder progresif' in metin or 'secondary progressive' in metin):
        return SartSonuc(ad='Relaps-remisyonla seyreden MS (RRMS)',
                         durum=SartDurumu.YOK,
                         neden='Rapor progresif MS belirtiyor — RRMS değil',
                         kaynak='rapor_metni', grup=grup)
    if _ms_tani(ilac_sonuc):
        return SartSonuc(ad='Relaps-remisyonla seyreden MS (RRMS)',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='MS tanısı var ama RRMS tipi metinde netleşmedi — manuel',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Relaps-remisyonla seyreden MS (RRMS)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='RRMS güncel MS tanısı raporda okunamadı — manuel',
                     kaynak='rapor_metni', grup=grup)


def atom_primer_progresif(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Primer progresif MS (okrelizumab 6-c)."""
    metin = _rapor_metni(ilac_sonuc)
    if ('primer progresif' in metin or 'primary progressive' in metin
            or 'ppms' in metin):
        return SartSonuc(ad='Primer progresif MS', durum=SartDurumu.VAR,
                         neden='Raporda primer progresif MS ibaresi',
                         kaynak='rapor_metni', grup=grup)
    if _ms_tani(ilac_sonuc):
        return SartSonuc(ad='Primer progresif MS',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='MS tanısı var ama primer progresif tipi netleşmedi — manuel',
                         kaynak='rapor_metni', grup=grup, sartli_atom=True)
    return SartSonuc(ad='Primer progresif MS', durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Primer progresif MS tanısı raporda okunamadı — manuel',
                     kaynak='rapor_metni', grup=grup)


def atom_ms_tani_zorunlu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    if _ms_tani(ilac_sonuc):
        return SartSonuc(ad='Güncel MS tanı kriterleri', durum=SartDurumu.VAR,
                         neden='MS tanısı (G35 / multipl skleroz) tespit edildi',
                         kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad='Güncel MS tanı kriterleri',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Güncel MS tanısı raporda/ICD\'de doğrulanamadı — manuel',
                     kaynak='ICD+rapor', grup=grup)


def atom_3basamak(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Üçüncü basamak sağlık hizmeti sunucusu (kullanıcı: tam kat → sessiz=ŞÜPHELİ)."""
    metin = _rapor_metni(ilac_sonuc)
    if any(k in metin for k in ('ucuncu basamak', '3. basamak', '3.basamak',
                                'egitim arastirma', 'egitim ve arastirma',
                                'universite', 'sehir hastane', 'tip fakultesi')):
        return SartSonuc(ad='Üçüncü basamak sağlık hizmeti sunucusu',
                         durum=SartDurumu.VAR,
                         neden='Raporda 3. basamak SHS ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Üçüncü basamak sağlık hizmeti sunucusu',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor düzenleyen tesisin 3. basamak olduğu doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup)


def atom_rapor_noroloji(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Nöroloji uzman hekiminin düzenlediği rapor."""
    rapor_var = _rapor_var(ilac_sonuc)
    adaylar = _rapor_brans_adaylar(ilac_sonuc)
    if any(_brans_listede(a, NOROLOJI) for a in adaylar):
        return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.VAR,
                         neden='Rapor nöroloji uzman hekimi tarafından düzenlenmiş',
                         kaynak='rapor_brans', grup=grup)
    if rapor_var and not any(_brans_l(a) for a in adaylar):
        return SartSonuc(ad='Nöroloji uzman hekim raporu',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Rapor var ama düzenleyen/heyet branşı okunamadı — manuel',
                         kaynak='rapor_brans', grup=grup, sartli_atom=True)
    if rapor_var:
        return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.YOK,
                         neden='Rapor düzenleyen nöroloji uzman hekimi değil',
                         kaynak='rapor_brans', grup=grup)
    return SartSonuc(ad='Nöroloji uzman hekim raporu', durum=SartDurumu.YOK,
                     neden='Reçeteye bağlı nöroloji uzman hekim raporu yok',
                     kaynak='rapor_brans', grup=grup)


def atom_recete_noroloji(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Reçeteyi nöroloji uzman hekimi düzenlemiş."""
    brans = ilac_sonuc.get('brans') or ilac_sonuc.get('doktor_uzmanligi') or ''
    if not _brans_l(brans):
        return SartSonuc(ad='Reçete eden nöroloji uzmanı',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçete eden hekim branşı bilinmiyor — manuel',
                         kaynak='hekim_brans', grup=grup, sartli_atom=True)
    if _brans_listede(brans, NOROLOJI):
        return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.VAR,
                         neden='Nöroloji uzman hekimi reçete edebilir',
                         kaynak='hekim_brans', grup=grup)
    return SartSonuc(ad=f'Reçete eden: {brans}', durum=SartDurumu.YOK,
                     neden='Reçeteyi yalnız nöroloji uzman hekimi düzenleyebilir',
                     kaynak='hekim_brans', grup=grup)


def atom_rapor_1yil(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Rapor en fazla 1 yıl süreli (kullanıcı: tam kat → tarih yoksa ŞÜPHELİ)."""
    bas = _tarih_parse(ilac_sonuc.get('rapor_baslangic_tarihi')
                       or ilac_sonuc.get('rapor_tarihi')
                       or ilac_sonuc.get('rap_bas_tar'))
    bit = _tarih_parse(ilac_sonuc.get('rapor_bitis_tarihi')
                       or ilac_sonuc.get('rap_bit_tar'))
    if bas and bit:
        gun = (bit - bas).days
        if 0 <= gun <= 400:
            return SartSonuc(ad='Rapor ≤ 1 yıl süreli', durum=SartDurumu.VAR,
                             neden=f'Rapor süresi ~{gun} gün (≤ 1 yıl)',
                             kaynak='rapor_tarih', grup=grup)
        return SartSonuc(ad='Rapor ≤ 1 yıl süreli', durum=SartDurumu.YOK,
                         neden=f'Rapor süresi {gun} gün — 1 yılı aşıyor',
                         kaynak='rapor_tarih', grup=grup)
    return SartSonuc(ad='Rapor ≤ 1 yıl süreli',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Rapor başlangıç/bitiş tarihi yok — süre doğrulanamadı — manuel',
                     kaynak='rapor_tarih', grup=grup)


def atom_kis_yok(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """(madde 2) Klinik İzole Sendrom DEĞİL — KİS'te bedel karşılanmaz."""
    metin = _rapor_metni(ilac_sonuc)
    if ('klinik izole sendrom' in metin or 'clinically isolated' in metin
            or 'izole sendrom' in metin or re.search(r'\bkis\b', metin)
            or re.search(r'\bcis\b', metin)):
        return SartSonuc(ad='Klinik İzole Sendrom (KİS) değil',
                         durum=SartDurumu.YOK,
                         neden='Klinik İzole Sendrom tedavisi — 4.2.34(2): bedel karşılanmaz',
                         kaynak='rapor_metni', grup=grup)
    if _ms_tani(ilac_sonuc):
        return SartSonuc(ad='Klinik İzole Sendrom (KİS) değil',
                         durum=SartDurumu.VAR,
                         neden='Güncel MS tanısı var — KİS değil',
                         kaynak='ICD+rapor', grup=grup)
    return SartSonuc(ad='Klinik İzole Sendrom (KİS) değil',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='KİS dışlaması netleşmedi (MS tanısı da doğrulanamadı) — manuel',
                     kaynak='rapor_metni', grup=grup, sartli_atom=True)


def atom_kombinasyon_yok(ilac_sonuc: Dict, grup: str,
                         bu_drug_key: Optional[str]) -> SartSonuc:
    """(madde 3) Başka MS DMT ile kombine kullanım YOK (fampiridin hariç)."""
    metin, alan_var = _diger_ilac_metni(ilac_sonuc)
    if not alan_var:
        return SartSonuc(ad='Kombine MS DMT kullanımı yok',
                         durum=SartDurumu.KONTROL_EDILEMEDI,
                         neden='Reçetedeki diğer ilaçlar bilinmiyor — manuel',
                         kaynak='recete_ilaclari', grup=grup, sartli_atom=True)
    bulunan: List[str] = []
    for key in COMBINE_DMT_KEYS:
        if key == bu_drug_key:
            continue
        etken, ticari = DRUG_DEFS[key]
        if _iceriyor(metin or '', etken) or _iceriyor(metin or '', ticari):
            bulunan.append(key.replace('BIRINCI_', '').replace('_', ' ').title())
    if bulunan:
        return SartSonuc(ad='Kombine MS DMT kullanımı yok', durum=SartDurumu.YOK,
                         neden='Eş-zamanlı MS DMT: ' + ', '.join(bulunan)
                               + ' — 4.2.34(3): kombine kullanımda bedel karşılanmaz',
                         kaynak='recete_ilaclari', grup=grup)
    return SartSonuc(ad='Kombine MS DMT kullanımı yok', durum=SartDurumu.VAR,
                     neden='Reçetede başka MS DMT (kombinasyon) yok',
                     kaynak='recete_ilaclari', grup=grup)


def atom_yuksek_aktivite_2kriter(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Yüksek hastalık aktivitesi: {son 1 yıl ≥1 atak, MRG lezyon artışı,
    doğrulanmış EDSS ≥0,5 artış} kriterlerinden ≥2 (kullanıcı: tam kat)."""
    metin = _rapor_metni(ilac_sonuc)
    bulunan: List[str] = []
    if re.search(r'atak|relaps', metin):
        bulunan.append('son 1 yıl atak')
    if 'lezyon' in metin and any(k in metin for k in ('artis', 'yeni t2',
                                                      'aktif lezyon', 'buyume',
                                                      'buyume')):
        bulunan.append('MRG lezyon yükü artışı')
    if 'edss' in metin and any(k in metin for k in ('artis', '0,5 puan',
                                                    '0.5 puan', 'puan artis')):
        bulunan.append('EDSS ≥0,5 artış')
    if len(bulunan) >= 2:
        return SartSonuc(ad='Yüksek hastalık aktivitesi (≥2 kriter)',
                         durum=SartDurumu.VAR,
                         neden='Raporda ≥2 kriter: ' + ', '.join(bulunan),
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Yüksek hastalık aktivitesi (≥2 kriter)',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden=('Yüksek aktivite ≥2 kriter raporda doğrulanamadı'
                            + (f' (bulunan: {", ".join(bulunan)})' if bulunan else '')
                            + ' — manuel'),
                     kaynak='rapor_metni', grup=grup)


def atom_onceki_dmt_yetersiz(ilac_sonuc: Dict, grup: str,
                             onceki_keywords) -> SartSonuc:
    """Önceki DMT('ler) toplamda ≥1 yıl kullanılmış ve yetersiz yanıt
    (kullanıcı: tam kat → metinden doğrulanamazsa ŞÜPHELİ)."""
    metin = _rapor_metni(ilac_sonuc)
    yetersiz = any(k in metin for k in ('yeterli yanit vermey', 'yetersiz yanit',
                                        'yanit alinamad', 'yanit yok', 'etkisiz',
                                        'direncli', 'dirençli', 'yanitsiz',
                                        'progresyon', 'fayda gormedi',
                                        'fayda saglamadi'))
    onceki = any(k in metin for k in onceki_keywords)
    if yetersiz and onceki:
        return SartSonuc(ad='Önceki DMT ≥1 yıl + yetersiz yanıt',
                         durum=SartDurumu.VAR,
                         neden='Raporda önceki DMT kullanımı + yetersiz yanıt ibaresi',
                         kaynak='rapor_metni', grup=grup)
    return SartSonuc(ad='Önceki DMT ≥1 yıl + yetersiz yanıt',
                     durum=SartDurumu.KONTROL_EDILEMEDI,
                     neden='Önceki DMT ≥1 yıl kullanımı + yetersiz yanıt doğrulanamadı — manuel',
                     kaynak='rapor_metni', grup=grup)


# ═══════════════════════════════════════════════════════════════════════
# ORTAK ŞART BLOĞU
# ═══════════════════════════════════════════════════════════════════════

def _ortak_sartlar(ilac_sonuc: Dict, sut_pref: str, drug_key: Optional[str],
                   kombi: bool = True) -> List[SartSonuc]:
    s = [
        atom_3basamak(ilac_sonuc, grup=f'{sut_pref} Üçüncü basamak SHS'),
        atom_rapor_noroloji(ilac_sonuc, grup=f'{sut_pref} Nöroloji uzman hekim raporu'),
        atom_rapor_1yil(ilac_sonuc, grup=f'{sut_pref} Rapor ≤1 yıl süreli'),
        atom_recete_noroloji(ilac_sonuc, grup=f'{sut_pref} Reçete eden nöroloji uzmanı'),
        atom_kis_yok(ilac_sonuc, grup='(4.2.34/2) KİS değil'),
    ]
    if kombi:
        s.append(atom_kombinasyon_yok(
            ilac_sonuc, grup='(4.2.34/3) Kombine MS DMT yok', bu_drug_key=drug_key))
    return s


# ═══════════════════════════════════════════════════════════════════════
# YOLAKLAR
# ═══════════════════════════════════════════════════════════════════════

def birinci_kontrol(ilac_sonuc: Dict, drug_key: Optional[str]) -> List[SartSonuc]:
    s = [
        atom_edss_max(ilac_sonuc, esik=5.5, sartli_band=6.5,
                      grup='(4.2.34/1) EDSS ≤5,5 (devam ≤6,5)'),
        atom_rrms(ilac_sonuc, grup='(4.2.34/1) RRMS güncel MS tanısı'),
    ]
    s.extend(_ortak_sartlar(ilac_sonuc, '(4.2.34/1)', drug_key))
    return s


def _fingolimod_natalizumab_kontrol(ilac_sonuc: Dict, drug_key: Optional[str],
                                    fno: str) -> List[SartSonuc]:
    """4.2.34(4)/(5): (a) yüksek aktivite yolu VEYA (b) EDSS≤5,5 RRMS."""
    pa = f'‖{fno}a‖'
    pb = f'‖{fno}b‖'
    s = _ortak_sartlar(ilac_sonuc, f'(4.2.34/{fno})', drug_key)
    # Yol (a) — yüksek aktivite
    s.append(atom_onceki_dmt_yetersiz(
        ilac_sonuc, grup=f'(4.2.34/{fno}-a) Önceki birinci-basamak DMT yetersiz {pa}',
        onceki_keywords=FIRST_LINE_KEYWORDS))
    s.append(atom_rrms(ilac_sonuc, grup=f'(4.2.34/{fno}-a) Yüksek aktivite RRMS {pa}'))
    s.append(atom_yuksek_aktivite_2kriter(
        ilac_sonuc, grup=f'(4.2.34/{fno}-a) Yüksek hastalık aktivitesi ≥2 kriter {pa}'))
    # Yol (b) — EDSS≤5,5 standart
    s.append(atom_edss_max(ilac_sonuc, esik=5.5,
                           grup=f'(4.2.34/{fno}-b) EDSS ≤5,5 {pb}'))
    s.append(atom_rrms(ilac_sonuc, grup=f'(4.2.34/{fno}-b) RRMS güncel MS {pb}'))
    return s


def fingolimod_kontrol(ilac_sonuc: Dict, drug_key: Optional[str]) -> List[SartSonuc]:
    return _fingolimod_natalizumab_kontrol(ilac_sonuc, drug_key, '4')


def natalizumab_kontrol(ilac_sonuc: Dict, drug_key: Optional[str]) -> List[SartSonuc]:
    return _fingolimod_natalizumab_kontrol(ilac_sonuc, drug_key, '5')


def okrelizumab_kontrol(ilac_sonuc: Dict, drug_key: Optional[str]) -> List[SartSonuc]:
    """4.2.34(6): (a) yüksek aktivite VEYA (b) EDSS≤7 RRMS VEYA (c) EDSS≤7 PPMS."""
    s = _ortak_sartlar(ilac_sonuc, '(4.2.34/6)', drug_key)
    # (a)
    s.append(atom_onceki_dmt_yetersiz(
        ilac_sonuc, grup='(4.2.34/6-a) Önceki birinci-basamak DMT yetersiz ‖6a‖',
        onceki_keywords=FIRST_LINE_KEYWORDS))
    s.append(atom_rrms(ilac_sonuc, grup='(4.2.34/6-a) Yüksek aktivite RRMS ‖6a‖'))
    s.append(atom_yuksek_aktivite_2kriter(
        ilac_sonuc, grup='(4.2.34/6-a) Yüksek hastalık aktivitesi ≥2 kriter ‖6a‖'))
    # (b)
    s.append(atom_edss_max(ilac_sonuc, esik=7.0, grup='(4.2.34/6-b) EDSS ≤7 ‖6b‖'))
    s.append(atom_rrms(ilac_sonuc, grup='(4.2.34/6-b) RRMS güncel MS ‖6b‖'))
    # (c)
    s.append(atom_edss_max(ilac_sonuc, esik=7.0, grup='(4.2.34/6-c) EDSS ≤7 ‖6c‖'))
    s.append(atom_primer_progresif(ilac_sonuc, grup='(4.2.34/6-c) Primer progresif MS ‖6c‖'))
    return s


def kladribin_kontrol(ilac_sonuc: Dict, drug_key: Optional[str]) -> List[SartSonuc]:
    """4.2.34(7): (a) EDSS≤5,5 RRMS +≥2 kriter VEYA (b) EDSS≤7 RRMS + önceki
    DMT yetersiz +≥2 kriter; (c) ortak nöro/3.basamak/1yıl; (f) vücut ağırlığı."""
    s = _ortak_sartlar(ilac_sonuc, '(4.2.34/7-c)', drug_key)
    # (a)
    s.append(atom_edss_max(ilac_sonuc, esik=5.5, grup='(4.2.34/7-a) EDSS ≤5,5 ‖7a‖'))
    s.append(atom_rrms(ilac_sonuc, grup='(4.2.34/7-a) RRMS güncel MS ‖7a‖'))
    s.append(atom_yuksek_aktivite_2kriter(
        ilac_sonuc, grup='(4.2.34/7-a) Yüksek hastalık aktivitesi ≥2 kriter ‖7a‖'))
    # (b)
    s.append(atom_edss_max(ilac_sonuc, esik=7.0, grup='(4.2.34/7-b) EDSS ≤7 ‖7b‖'))
    s.append(atom_rrms(ilac_sonuc, grup='(4.2.34/7-b) RRMS güncel MS ‖7b‖'))
    s.append(atom_onceki_dmt_yetersiz(
        ilac_sonuc, grup='(4.2.34/7-b) Önceki birinci-basamak DMT yetersiz ‖7b‖',
        onceki_keywords=FIRST_LINE_KEYWORDS))
    s.append(atom_yuksek_aktivite_2kriter(
        ilac_sonuc, grup='(4.2.34/7-b) Yüksek hastalık aktivitesi ≥2 kriter ‖7b‖'))
    # (f) güncel vücut ağırlığı — bilgi (hesaplama dışı)
    s.append(SartSonuc(ad='Güncel vücut ağırlığı raporda', durum=SartDurumu.KONTROL_EDILEMEDI,
                       neden='Her raporda güncel vücut ağırlığı belirtilmeli (7-f) — manuel',
                       kaynak='rapor_metni', grup='(4.2.34/7-f) Güncel vücut ağırlığı (bilgi)',
                       sartli_atom=True))
    return s


def alemtuzumab_kontrol(ilac_sonuc: Dict, drug_key: Optional[str]) -> List[SartSonuc]:
    """4.2.34(8): (a) önceki ikinci-basamak DMT yetersiz +≥2 kriter VEYA
    (b) EDSS≤7 RRMS."""
    s = _ortak_sartlar(ilac_sonuc, '(4.2.34/8)', drug_key)
    # (a)
    s.append(atom_onceki_dmt_yetersiz(
        ilac_sonuc, grup='(4.2.34/8-a) Önceki ikinci-basamak DMT yetersiz ‖8a‖',
        onceki_keywords=SECOND_LINE_KEYWORDS))
    s.append(atom_rrms(ilac_sonuc, grup='(4.2.34/8-a) Yüksek aktivite RRMS ‖8a‖'))
    s.append(atom_yuksek_aktivite_2kriter(
        ilac_sonuc, grup='(4.2.34/8-a) Yüksek hastalık aktivitesi ≥2 kriter ‖8a‖'))
    # (b)
    s.append(atom_edss_max(ilac_sonuc, esik=7.0, grup='(4.2.34/8-b) EDSS ≤7 ‖8b‖'))
    s.append(atom_rrms(ilac_sonuc, grup='(4.2.34/8-b) RRMS güncel MS ‖8b‖'))
    return s


def fampiridin_kontrol(ilac_sonuc: Dict, drug_key: Optional[str]) -> List[SartSonuc]:
    """4.2.34(9): güncel MS + EDSS≥4 (≥7 sonlandırılır); 3.basamak nöro rapor
    + reçete nöro. Madde-3 kombinasyon yasağından HARİÇ."""
    s = [
        atom_ms_tani_zorunlu(ilac_sonuc, grup='(4.2.34/9) Güncel MS tanısı'),
        atom_edss_fampiridin(ilac_sonuc, grup='(4.2.34/9) EDSS ≥4 (≥7 sonlandırılır)'),
    ]
    # Ortak şartlar — kombinasyon HARİÇ (fampiridin madde-3 dışı)
    s.extend(_ortak_sartlar(ilac_sonuc, '(4.2.34/9)', drug_key, kombi=False))
    return s


YOLAK_FN_MAP = {
    'BIRINCI': birinci_kontrol,
    'FINGOLIMOD': fingolimod_kontrol,
    'NATALIZUMAB': natalizumab_kontrol,
    'OKRELIZUMAB': okrelizumab_kontrol,
    'KLADRIBIN': kladribin_kontrol,
    'ALEMTUZUMAB': alemtuzumab_kontrol,
    'FAMPIRIDIN': fampiridin_kontrol,
}
YOLAK_METADATA = {
    'BIRINCI': {'ad': 'Beta IFN / glatiramer / teriflunomid / dimetil fumarat',
                'sut': '4.2.34(1)'},
    'FINGOLIMOD': {'ad': 'Fingolimod', 'sut': '4.2.34(4)'},
    'NATALIZUMAB': {'ad': 'Natalizumab', 'sut': '4.2.34(5)'},
    'OKRELIZUMAB': {'ad': 'Okrelizumab', 'sut': '4.2.34(6)'},
    'KLADRIBIN': {'ad': 'Kladribin', 'sut': '4.2.34(7)'},
    'ALEMTUZUMAB': {'ad': 'Alemtuzumab', 'sut': '4.2.34(8)'},
    'FAMPIRIDIN': {'ad': 'Fampiridin', 'sut': '4.2.34(9)'},
}


# ═══════════════════════════════════════════════════════════════════════
# GENEL SONUÇ HESAPLAMA (üst-VEYA destekli)
# ═══════════════════════════════════════════════════════════════════════

_PATH_TAG_RE = re.compile(r'‖([^‖]+)‖')


def _grup_durum(gs: List[SartSonuc]) -> Tuple[str, bool]:
    """Tek grup → ('var'|'yok'|'ke', sadece_sartli_ke)."""
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


def _and_birlestir(sonuclar: List[Tuple[str, bool]]) -> Tuple[str, bool]:
    if any(d == 'yok' for d, _ in sonuclar):
        return ('yok', False)
    ke = [(d, s) for d, s in sonuclar if d == 'ke']
    if ke:
        return ('ke', all(s for _, s in ke))
    return ('var', False)


def _or_birlestir(sonuclar: List[Tuple[str, bool]]) -> Tuple[str, bool]:
    if any(d == 'var' for d, _ in sonuclar):
        return ('var', False)
    ke = [(d, s) for d, s in sonuclar if d == 'ke']
    if ke:
        return ('ke', all(s for _, s in ke))
    return ('yok', False)


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    gruplar: Dict[str, List[SartSonuc]] = {}
    for s in sartlar:
        if '(bilgi)' in (s.grup or ''):
            continue
        gruplar.setdefault(s.grup, []).append(s)
    if not gruplar:
        return KontrolSonucu.KONTROL_EDILEMEDI

    ortak: List[Tuple[str, bool]] = []
    yollar: Dict[str, List[Tuple[str, bool]]] = {}
    for grup, gs in gruplar.items():
        durum = _grup_durum(gs)
        m = _PATH_TAG_RE.search(grup)
        if m:
            yollar.setdefault(m.group(1), []).append(durum)
        else:
            ortak.append(durum)

    sonuc_listesi: List[Tuple[str, bool]] = list(ortak)
    if yollar:
        yol_sonuclari = [_and_birlestir(v) for v in yollar.values()]
        sonuc_listesi.append(_or_birlestir(yol_sonuclari))

    durum, sartli = _and_birlestir(sonuc_listesi)
    if durum == 'yok':
        return KontrolSonucu.UYGUN_DEGIL
    if durum == 'ke':
        return (KontrolSonucu.SARTLI_UYGUN if sartli
                else KontrolSonucu.KONTROL_EDILEMEDI)
    return KontrolSonucu.UYGUN


def _mesaj_uret(sonuc: KontrolSonucu, yolak: str, sartlar: List[SartSonuc]) -> str:
    yok = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]
    meta = YOLAK_METADATA.get(yolak, {})
    parcalar = [f"SUT {meta.get('sut', '4.2.34')} / {meta.get('ad', yolak)}"]
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

def multipl_skleroz_kontrol_4_2_34(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.34 — Multipl Skleroz ilaçları ana kontrol fonksiyonu."""
    drug_key = _drug_key_belirle(ilac_sonuc)
    yolak = DRUG_KEY_TO_YOLAK.get(drug_key) if drug_key else None
    if yolak is None:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.34 kapsamı dışı — MS hastalık modifiye edici ilaç değil',
            sut_kurali='SUT 4.2.34')

    sartlar = YOLAK_FN_MAP[yolak](ilac_sonuc, drug_key)
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)

    detaylar = {
        'yolak': yolak,
        'drug_key': drug_key,
        'yolak_ad': YOLAK_METADATA[yolak]['ad'],
        'sut_maddesi': YOLAK_METADATA[yolak]['sut'],
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
        sut_kurali=f"SUT {YOLAK_METADATA[yolak]['sut']} — {YOLAK_METADATA[yolak]['ad']}",
        sartlar=sartlar, detaylar=detaylar)


# ═══════════════════════════════════════════════════════════════════════
# AKIL TESTİ
# ═══════════════════════════════════════════════════════════════════════

def _senaryolar() -> List[Tuple[str, Dict, KontrolSonucu]]:
    # Tam UYGUN için: EDSS rapor metninde, RRMS, 3.basamak, rapor+reçete
    # nöroloji, rapor tarihleri (≤1yıl), MS tanısı (KİS değil), diğer ilaç boş.
    tam_ortak = {
        'brans': 'Nöroloji', 'rapor_doktor_brans': 'Nöroloji', 'rapor_kodu': '100',
        'rapor_baslangic_tarihi': '01.01.2026', 'rapor_bitis_tarihi': '01.01.2027',
        'recete_teshisleri': ['G35'], 'recete_ilaclari': [],
    }
    return [
        # ── BIRINCI ──
        ("BIRINCI UYGUN (interferon beta, EDSS 3, tüm şartlar)", {
            **tam_ortak, 'etkin_madde': 'INTERFERON BETA-1A', 'ilac_adi': 'REBIF',
            'rapor_metni': 'EDSS 3 relaps remisyon multipl skleroz ucuncu basamak universite',
        }, KontrolSonucu.UYGUN),
        ("BIRINCI UYGUN DEĞİL (EDSS 7 > 6,5 sonlandır)", {
            **tam_ortak, 'etkin_madde': 'GLATIRAMER ASETAT', 'ilac_adi': 'COPAXONE',
            'rapor_metni': 'EDSS 7 relaps remisyon multipl skleroz ucuncu basamak',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("BIRINCI UYGUN DEĞİL (reçete kardiyoloji)", {
            **tam_ortak, 'brans': 'Kardiyoloji', 'etkin_madde': 'TERIFLUNOMID',
            'rapor_metni': 'EDSS 2 relaps remisyon multipl skleroz universite',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("BIRINCI ŞARTLI (EDSS 6 başlama üstü, devam bandı)", {
            **tam_ortak, 'etkin_madde': 'DIMETIL FUMARAT', 'ilac_adi': 'TECFIDERA',
            'rapor_metni': 'EDSS 6 relaps remisyon multipl skleroz ucuncu basamak',
        }, KontrolSonucu.SARTLI_UYGUN),
        ("BIRINCI ŞÜPHELİ (EDSS yok, 3.basamak yok)", {
            **tam_ortak, 'etkin_madde': 'INTERFERON BETA-1B', 'ilac_adi': 'BETAFERON',
            'rapor_metni': 'relaps remisyon multipl skleroz',
        }, KontrolSonucu.KONTROL_EDILEMEDI),
        ("BIRINCI UYGUN DEĞİL (KİS - madde 2)", {
            **tam_ortak, 'etkin_madde': 'INTERFERON BETA', 'ilac_adi': 'AVONEX',
            'recete_teshisleri': [],
            'rapor_metni': 'EDSS 2 klinik izole sendrom ucuncu basamak universite relaps',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("BIRINCI UYGUN DEĞİL (kombinasyon - madde 3)", {
            **tam_ortak, 'etkin_madde': 'GLATIRAMER', 'ilac_adi': 'COPAXONE',
            'recete_ilaclari': [{'ad': 'GILENYA 0.5 MG'}],
            'rapor_metni': 'EDSS 2 relaps remisyon multipl skleroz universite',
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── FINGOLIMOD ──
        ("FINGOLIMOD UYGUN (yol-b EDSS 4, RRMS, şartlar)", {
            **tam_ortak, 'etkin_madde': 'FINGOLIMOD', 'ilac_adi': 'GILENYA',
            'rapor_metni': 'EDSS 4 relaps remisyon multipl skleroz ucuncu basamak universite',
        }, KontrolSonucu.UYGUN),
        ("FINGOLIMOD ŞARTLI (yol-a yüksek aktivite metinli, EDSS 6>5,5)", {
            **tam_ortak, 'etkin_madde': 'FINGOLIMOD', 'ilac_adi': 'GILENYA',
            'rapor_metni': ('EDSS 6 relaps remisyon multipl skleroz ucuncu basamak '
                            'universite interferon yetersiz yanit atak mrg lezyon artis '
                            'edss artis'),
        }, KontrolSonucu.UYGUN),
        # ── OKRELIZUMAB ──
        ("OKRELIZUMAB UYGUN (yol-c PPMS EDSS 6)", {
            **tam_ortak, 'etkin_madde': 'OKRELIZUMAB', 'ilac_adi': 'OCREVUS',
            'rapor_metni': 'EDSS 6 primer progresif multipl skleroz ucuncu basamak universite',
        }, KontrolSonucu.UYGUN),
        ("OKRELIZUMAB UYGUN (yol-b RRMS EDSS 6)", {
            **tam_ortak, 'etkin_madde': 'OKRELIZUMAB', 'ilac_adi': 'OCREVUS',
            'rapor_metni': 'EDSS 6 relaps remisyon multipl skleroz ucuncu basamak universite',
        }, KontrolSonucu.UYGUN),
        # ── KLADRIBIN ──
        ("KLADRIBIN ŞÜPHELİ (yol-a EDSS 4 RRMS, ≥2 kriter doğrulanamadı)", {
            **tam_ortak, 'etkin_madde': 'KLADRIBIN', 'ilac_adi': 'MAVENCLAD',
            'rapor_metni': 'EDSS 4 relaps remisyon multipl skleroz ucuncu basamak universite',
        }, KontrolSonucu.KONTROL_EDILEMEDI),
        ("KLADRIBIN UYGUN (yol-a EDSS 5 RRMS +2 kriter)", {
            **tam_ortak, 'etkin_madde': 'KLADRIBIN', 'ilac_adi': 'MAVENCLAD',
            'rapor_metni': ('EDSS 5 relaps remisyon multipl skleroz ucuncu basamak '
                            'universite atak mrg lezyon yeni t2 artis'),
        }, KontrolSonucu.UYGUN),
        # ── ALEMTUZUMAB ──
        ("ALEMTUZUMAB UYGUN (yol-b EDSS 6 RRMS)", {
            **tam_ortak, 'etkin_madde': 'ALEMTUZUMAB', 'ilac_adi': 'LEMTRADA',
            'rapor_metni': 'EDSS 6 relaps remisyon multipl skleroz ucuncu basamak universite',
        }, KontrolSonucu.UYGUN),
        # ── FAMPIRIDIN ──
        ("FAMPIRIDIN UYGUN (EDSS 5 ≥4, MS, şartlar, kombi muaf)", {
            **tam_ortak, 'etkin_madde': 'FAMPRIDIN', 'ilac_adi': 'FAMPYRA',
            'recete_ilaclari': [{'ad': 'GILENYA'}],  # fampiridin madde-3 hariç
            'rapor_metni': 'EDSS 5 multipl skleroz ucuncu basamak universite',
        }, KontrolSonucu.UYGUN),
        ("FAMPIRIDIN UYGUN DEĞİL (EDSS 3 < 4)", {
            **tam_ortak, 'etkin_madde': 'FAMPRIDIN', 'ilac_adi': 'FAMPYRA',
            'rapor_metni': 'EDSS 3 multipl skleroz ucuncu basamak universite',
        }, KontrolSonucu.UYGUN_DEGIL),
        ("FAMPIRIDIN UYGUN DEĞİL (EDSS 7 sonlandır)", {
            **tam_ortak, 'etkin_madde': 'FAMPRIDIN', 'ilac_adi': 'FAMPYRA',
            'rapor_metni': 'EDSS 7 multipl skleroz ucuncu basamak universite',
        }, KontrolSonucu.UYGUN_DEGIL),
        # ── Kapsam dışı ──
        ("Kapsam dışı (parasetamol)", {
            'etkin_madde': 'PARASETAMOL', 'atc_kodu': 'N02BE01',
        }, KontrolSonucu.ATLANDI),
    ]


def _akil_testi() -> None:
    print("SUT 4.2.34 — Multipl Skleroz — Akıl Testi\n" + "=" * 64)
    gecti = 0
    senaryolar = _senaryolar()
    for ad, ilac_sonuc, beklenen in senaryolar:
        rapor = multipl_skleroz_kontrol_4_2_34(ilac_sonuc)
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
