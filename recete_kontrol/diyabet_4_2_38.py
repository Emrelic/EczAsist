# -*- coding: utf-8 -*-
"""SUT 4.2.38 — Diyabet Tedavisinde İlaç Kullanım İlkeleri

9 yolaklı atomik kontrol motoru. Tasarım dokümanı:
`docs/sut/SUT_4_2_38_DIYABET_ANALIZ.md`. Protokol metodolojisi:
`docs/SUT_MANTIK_SEMA_PROTOKOLU.md` (CLAUDE.md §10–11).

Yolak haritası:
    Y1  → Met / Sulfo / Akarboz / İnsan insülin           (Fıkra 1, rapor şartı YOK)
    Y2  → Repaglinid / Nateglinid / OAD kombi             (Fıkra 2)
    Y3  → Analog insülin / Pioglitazon / Pio kombi        (Fıkra 3)
    Y3b → İnsülin Degludek+Aspart (Ryzodeg)               (Fıkra 3b)
    Y4  → DPP-4 antagonistleri + kombineleri              (Fıkra 4)
    Y5  → Eksenatid                                       (Fıkra 5)
    Y6  → SGLT-2 + kombineleri                            (Fıkra 6)
    Y7  → Glarjin+Liksisenatid (Soliqua)                  (Fıkra 7)
    Y8  → Empa+Lina kombi (Glyxambi)                      (Fıkra 8)
    Y9_KAPSAM_DISI → Diğer GLP-1 (lira/sema/dula/tirze)   (kapsam dışı)

Ana entrypoint: ``diyabet_kontrol_4_2_38(ilac_sonuc)`` → ``KontrolRaporu``.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple, Set
from recete_kontrol.base_kontrol import (
    KontrolRaporu, KontrolSonucu, SartDurumu, SartSonuc,
)
from recete_kontrol.tr_normalize import norm_tr_upper, norm_tr_lower

# ═══════════════════════════════════════════════════════════════════════
# İlaç sınıfı listeleri (etkin madde + ticari ad)
# ═══════════════════════════════════════════════════════════════════════

METFORMIN: Set[str] = {
    'METFORMIN', 'METFORMIN HCL',
    'GLUKOFEN', 'GLIFOR', 'GLUCOPHAGE', 'METFORM', 'MATOFIN',
    'DIAFORMIN',  # Met tek başına Diaformin var; met+glibenklamid kombi DAONIL
}

SULFONILURE: Set[str] = {
    'GLIKLAZID', 'GLICLAZID', 'DIAMICRON', 'BETANORM', 'DIAMERID',
    'GLIMEPIRID', 'AMARYL', 'GLIMAX', 'MERIDIA', 'GLIBEDAL',
    'GLIBENKLAMID', 'DAONIL', 'GLUKOMID',
    'GLIPIZID', 'MINIDIAB', 'GLUCOTROL',
}

GLINID: Set[str] = {
    # Repaglinid
    'REPAGLINID',
    'NOVONORM', 'DIAFREE', 'NOVADE', 'REPAFIX',
    'REPAMEF', 'REPELIT', 'REPLIC', 'PAREGLIN',
    # Nateglinid (TR ticari adlar — TEGLIX en yaygın)
    'NATEGLINID',
    'STARLIX', 'TEGLIX', 'DIALIX', 'INCURIA', 'INGLEX',
    'NAGLID', 'NATEFUL', 'NATMET', 'NATPLUS',  # NATMET/NATPLUS = +metformin kombi
}

TZD: Set[str] = {  # Pioglitazon (TR ticari adlar — DROPIA/GLIFIX en yaygın)
    'PIOGLITAZON', 'PIOGLITAZON HCL',
    'ACTOS', 'GLUSTIN', 'PIONORM',
    'DROPIA', 'GLIFIX', 'DIALIC', 'DYNDION',
    'PIOFORCE', 'PIOFOX', 'PIOGTAN', 'PIONDIA', 'PIXART',
}

AKARBOZ: Set[str] = {
    'AKARBOZ', 'ACARBOSE', 'GLUCOBAY',
}

DPP4: Set[str] = {
    'SITAGLIPTIN', 'SITAGLIPTIN FOSFAT',
    'VILDAGLIPTIN',
    'SAKSAGLIPTIN',
    'LINAGLIPTIN',
    'ALOGLIPTIN',
    'JANUVIA', 'GALVUS', 'ONGLYZA', 'TRAJENTA', 'NESINA',
    'JANUMET', 'GALVUSMET', 'KOMBOGLYZE', 'JENTADUETO', 'VIPDOMET',
}

SGLT2: Set[str] = {
    'DAPAGLIFLOZIN', 'DAPAGLIFLOZIN PROPANDIOL',
    'EMPAGLIFLOZIN',
    'KANAGLIFLOZIN', 'CANAGLIFLOZIN',
    'ERTUGLIFLOZIN',
    'JARDIANCE', 'FORZIGA', 'FORXIGA', 'INVOKANA', 'STEGLATRO',
    'SYNJARDY', 'XIGDUO', 'VOKANAMET', 'SEGLUROMET',  # SGLT-2 + Metformin kombi
}

# Eksenatid SUT 4.2.38(5)'in tek konusu — diğer GLP-1'ler kapsam DIŞI
GLP1_EKSENATID: Set[str] = {
    'EKSENATID', 'EXENATID', 'BYETTA', 'BYDUREON',
}

GLP1_DIGER: Set[str] = {
    'LIRAGLUTID', 'VICTOZA', 'SAXENDA',
    'SEMAGLUTID', 'OZEMPIC', 'RYBELSUS', 'WEGOVY',
    'DULAGLUTID', 'TRULICITY',
    'TIRZEPATID', 'MOUNJARO',
    'INSULIN DEGLUDEK/LIRAGLUTID', 'XULTOPHY',  # Degludek+Liraglutid (Xultophy)
}

# İnsülinler
INSAN_INSULIN: Set[str] = {
    'HUMULIN', 'ACTRAPID', 'INSULATARD', 'INSUMAN', 'MIXTARD',
    'INSULIN HUMAN', 'INSULIN NPH', 'INSULIN NPH(HUMAN)',
}

ANALOG_INSULIN: Set[str] = {
    'INSULIN GLARJIN', 'INSULIN GLARGIN', 'GLARJIN', 'GLARGIN',
    'INSULIN DETEMIR', 'DETEMIR', 'LEVEMIR',
    'INSULIN DEGLUDEC', 'DEGLUDEC', 'DEGLUDEK', 'TRESIBA',
    'LANTUS', 'TOUJEO', 'BASAGLAR', 'ABASAGLAR',
    'INSULIN ASPART', 'ASPART', 'NOVORAPID',
    'INSULIN LISPRO', 'LISPRO', 'HUMALOG',
    'INSULIN GLULIZIN', 'GLULIZIN', 'APIDRA',
    'NOVOMIX', 'HUMALOGMIX',
}

# Sabit kombi preparatlar (en spesifik — dispatcher önceliği)
KOMBI_DEGLUDEK_ASPART: Set[str] = {
    'INSULIN DEGLUDEK/ASPART', 'INSÜLIN DEGLUDEK/INSÜLIN ASPART',
    'RYZODEG',
}

KOMBI_GLARJIN_LIKSISENATID: Set[str] = {
    'INSÜLIN GLARJIN/LIKSISENATID', 'INSULIN GLARJIN/LIKSISENATID',
    'GLARJIN/LIKSISENATID', 'SOLIQUA', 'LIKSISENATID', 'LIXISENATID',
    'LYXUMIA',  # Liksisenatid tek başına da Y7 kapsamında (4.2.38'de sadece kombi var
                # ama liksisenatid tek başına Türkiye'de yok — yine de yakalansın)
}

KOMBI_EMPA_LINA: Set[str] = {
    'EMPAGLIFLOZIN/LINAGLIPTIN', 'LINAGLIPTIN/EMPAGLIFLOZIN',
    'GLYXAMBI',
}

KOMBI_DPP4_SGLT2_DIGER: Set[str] = {
    # Lina+Empa Y8'de; diğer DPP-4+SGLT-2 kombileri Y4'e düşer (DPP-4 öncelikli)
    'QTERN',         # Dapa+Saksa
    'STEGLUJAN',     # Ertu+Sita
    'DAPAGLIFLOZIN/SAKSAGLIPTIN', 'SAKSAGLIPTIN/DAPAGLIFLOZIN',
}

# ─── Y3b alt-kümeleri (analog karışım VEYA uzun etkili insülin önceden kullanım) ───
# SUT 4.2.38(3)(b) "analog karışım veya uzun etkili insülinler" — TR piyasası
ANALOG_KARISIM_INSULIN: Set[str] = {
    # Etken madde — slash'lı + slash'sız + biphasic varyantları
    'INSULIN ASPART/INSULIN ASPART PROTAMIN', 'INSULIN ASPART PROTAMIN',
    'ASPART PROTAMIN', 'BIPHASIC INSULIN ASPART',
    'INSULIN LISPRO/INSULIN LISPRO PROTAMIN', 'INSULIN LISPRO PROTAMIN',
    'LISPRO PROTAMIN', 'BIPHASIC INSULIN LISPRO',
    # Ticari ad (Türkiye)
    'NOVOMIX', 'NOVO MIX',
    'NOVOMIX 30', 'NOVOMIX 50', 'NOVOMIX 70',
    'HUMALOGMIX', 'HUMALOG MIX',
    'HUMALOG MIX 25', 'HUMALOG MIX 50',
}

ANALOG_UZUN_ETKILI_INSULIN: Set[str] = {
    # Etken madde
    'INSULIN GLARJIN', 'INSULIN GLARGIN', 'GLARJIN', 'GLARGIN', 'GLARGINE',
    'INSULIN DETEMIR', 'DETEMIR',
    'INSULIN DEGLUDEC', 'DEGLUDEC', 'DEGLUDEK',
    # Ticari ad (Türkiye — biyobenzerler dahil)
    'LANTUS', 'TOUJEO',           # Sanofi (glarjin U100 + U300)
    'BASAGLAR', 'ABASAGLAR',      # Lilly biyobenzer glarjin
    'GLARIN',                     # TR yerli biyobenzer glarjin
    'LEVEMIR',                    # NovoNordisk detemir
    'TRESIBA',                    # NovoNordisk degludek
}

# NPH/orta etkili insan bazal — kullanıcı kararı 2026-05-24: geniş yorum, VAR sayılır
# ADA/EASD sınıfında "intermediate-acting", ama klinik pratikte bazal kullanım
# yaygın olduğundan Y3b.1b'de VAR sayılır.
NPH_INSAN_BAZAL_INSULIN: Set[str] = {
    'HUMULIN N', 'HUMULIN-N',
    'INSULATARD',                 # NovoNordisk NPH (FlexPen/Penfill)
    'INSUMAN BASAL', 'INSUMAN-BASAL',
    'INSULIN NPH', 'NPH INSULIN',
    'ISOPHANE', 'IZOFAN', 'İZOFAN',
}

# ─── SUT 4.2.74 — Standart KY tedavisi 4'lüsü (Y_KY için) ───
ACE_INHIBITOR: Set[str] = {
    # Etken madde
    'PERINDOPRIL', 'RAMIPRIL', 'ENALAPRIL', 'LISINOPRIL', 'LİSİNOPRIL',
    'BENAZEPRIL', 'CILAZAPRIL', 'CİLAZAPRIL', 'FOSINOPRIL', 'FOSİNOPRİL',
    'QUINAPRIL', 'KUİNAPRİL', 'ZOFENOPRIL', 'ZOFENOPRİL',
    'TRANDOLAPRIL', 'CAPTOPRIL', 'KAPTOPRİL', 'MOEXIPRIL', 'IMIDAPRIL',
    # Ticari ad
    'COVERSYL', 'PREXANIL', 'BIPRETERAX', 'PRESTARIUM',
    'DELIX', 'RAMIXAR', 'TRITACE', 'CARDACE', 'VIVACE',
    'KONVERIL', 'ZESTRIL', 'ANGIOPRIL',
    'INHIBACE', 'CIBADREX',
    'MONOPRIL', 'STARIL',
    'ACCURETIC', 'ACUITEL',
    'ZOFENIL', 'BIFRIL',
    'GOPTEN', 'ODRIK',
    'KAPOTEN',
}

ARB_GRUBU: Set[str] = {
    # Etken madde
    'LOSARTAN', 'VALSARTAN', 'IRBESARTAN', 'İRBESARTAN',
    'KANDESARTAN', 'CANDESARTAN', 'TELMISARTAN', 'TELMİSARTAN',
    'OLMESARTAN', 'EPROSARTAN', 'AZILSARTAN', 'AZİLSARTAN',
    # Ticari ad
    'COZAAR', 'EKSEFOR', 'LARITON', 'LOSAR',
    'DIOVAN', 'VALEXA', 'VALSACOR', 'TARK', 'VALSARTIL',
    'APROVEL', 'KARVEA', 'IRBES', 'IRDA',
    'ATACAND', 'BLOPRESS', 'RATACAND',
    'MICARDIS', 'PRITOR', 'TELVAS', 'TEVELOX', 'TWENTACOR',
    'OLMETEC', 'BENICAR', 'VOTUM',
    'TEVETEN',
    'EDARBI',
    # Kombi (ARB içerikli)
    'EXFORGE', 'SEVIKAR', 'TWYNSTA', 'MICARDISPLUS', 'CO-DIOVAN', 'CODIOVAN',
    'CO-APROVEL', 'COAPROVEL', 'CO-OLMETEC', 'HYZAAR', 'KARVEZIDE',
    'FORZATEN', 'CO-IRDA', 'TRIVERAM', 'ATACAND PLUS',
}

BETA_BLOKOR: Set[str] = {
    # Etken madde — KY'de etkin sayılanlar: bisoprolol, carvedilol, nebivolol, metoprolol succinate
    'BISOPROLOL', 'BİSOPROLOL', 'CARVEDILOL', 'KARVEDİLOL', 'KARVEDILOL',
    'NEBIVOLOL', 'NEBİVOLOL', 'METOPROLOL', 'METROPROLOL',
    'PROPRANOLOL', 'ATENOLOL', 'ESMOLOL', 'CELIPROLOL',
    'ACEBUTOLOL', 'BETAKSOLOL', 'PINDOLOL', 'SOTALOL',
    # Ticari ad
    'CONCOR', 'BISOBETA', 'BISOPROL', 'ISOTEN',
    'DILATREND', 'COREG', 'CARVEDIPHARM',
    'NEBILET', 'NEVENA', 'NEBIVOL',
    'BELOC', 'BELOCZOK', 'METPRES', 'METOPROL',
    'DIDERAL', 'INDERAL', 'TENORMIN', 'TENOLOL',
    'BREVIBLOC', 'KERLONE',
}

MRA_ALDOSTERON_ANT: Set[str] = {
    'SPIRONOLAKTON', 'SPIRONOLACTONE', 'EPLERENON', 'EPLERENONE',
    'ALDACTONE', 'ALDACTAZIDE', 'INSPRA',
}

GLP1_TUMU: Set[str] = (GLP1_EKSENATID | GLP1_DIGER)  # SUT 4(ç)/5(ç) yasak için tek küme


def _arama_metni(ilac_sonuc: Dict) -> str:
    """İlaç adı + etkin madde birleşik TR→ASCII upper-case arama metni."""
    ilac_adi = ilac_sonuc.get('ilac_adi') or ''
    etkin_madde = ilac_sonuc.get('etkin_madde') or ''
    return norm_tr_upper(f"{ilac_adi} {etkin_madde}")


def _iceriyor(metin: str, kume: Set[str]) -> bool:
    """metin (upper) içinde küme elemanlarından herhangi biri geçiyor mu?"""
    return any(k in metin for k in kume)


# ═══════════════════════════════════════════════════════════════════════
# DISPATCHER — etken madde → yolak
# ═══════════════════════════════════════════════════════════════════════

def yolak_belirle(ilac_sonuc: Dict) -> str:
    """SUT 4.2.38 yolak kararı.

    Öncelik (en spesifik → en geniş):
      1. Sabit kombi preparatlar (Y8 / Y7 / Y3b)
      2. Eksenatid (Y5)
      3. Diğer GLP-1 (Y9_KAPSAM_DISI)
      4. DPP-4 + kombi (Y4)
      5. SGLT-2 + kombi (Y6)
      6. Analog insülin / Pioglitazon (Y3)
      7. Repaglinid / Nateglinid (Y2)
      8. Metformin / Sulfo / Akarboz / İnsan insülin (Y1)

    Diyabet kapsamı dışı ise '' döner.
    """
    m = _arama_metni(ilac_sonuc)

    # 1. Sabit kombi preparatlar — en spesifik tespit
    if _iceriyor(m, KOMBI_EMPA_LINA):
        return 'Y8'
    if _iceriyor(m, KOMBI_GLARJIN_LIKSISENATID):
        return 'Y7'
    if _iceriyor(m, KOMBI_DEGLUDEK_ASPART):
        return 'Y3b'

    # 2. Eksenatid
    if _iceriyor(m, GLP1_EKSENATID):
        return 'Y5'

    # 3. Diğer GLP-1 (lira/sema/dula/tirze) — kapsam dışı
    if _iceriyor(m, GLP1_DIGER):
        return 'Y9_KAPSAM_DISI'

    # 4. DPP-4 + kombi
    if _iceriyor(m, DPP4):
        return 'Y4'

    # 5. SGLT-2 + kombi (DPP-4 değilse) — alt-dispatcher (S5=A)
    if _iceriyor(m, SGLT2):
        return _sglt2_alt_dispatcher(ilac_sonuc)

    # 6. Analog insülin / Pioglitazon
    if _iceriyor(m, ANALOG_INSULIN) or _iceriyor(m, TZD):
        return 'Y3'

    # 7. Repaglinid / Nateglinid
    if _iceriyor(m, GLINID):
        return 'Y2'

    # 8. Met / Sulfo / Akarboz / İnsan insülin
    if (_iceriyor(m, METFORMIN) or _iceriyor(m, SULFONILURE)
            or _iceriyor(m, AKARBOZ) or _iceriyor(m, INSAN_INSULIN)):
        return 'Y1'

    return ''


def _sglt2_alt_dispatcher(ilac_sonuc: Dict) -> str:
    """SGLT-2 (dapa/empa) için alt-dispatcher: Y_KY ∨ Y_KBH ∨ Y6 (S5=A).

    Aktif rapor ibareleri:
      - KY: ICD I50.x VEYA "kalp yetersizliği/yetmezliği", "NYHA", "EF≤"
      - KBH: ICD N18.x VEYA "kronik böbrek", "ACR", "PCR", "proteinüri"
      - DM: ICD E10/E11 VEYA "diyabet/glisemik/HbA1c"

    Öncelik: KY > KBH > DM (en spesifik endikasyon). Hiçbiri yoksa Y6 default.

    Rapor bağlamı önceliği (2026-07-06): Reçete kalemi DM raporuna (07.02.x)
    bağlıysa, reçete ICD'sindeki I50/N18 kodları reçetedeki BAŞKA kalemlere
    ait olabilir — bu durumda 4.2.74'e yalnız RAPOR METNİ KY/KBH anlatıyorsa
    sapılır; rapor sessizse Y6 (DM). Pilot: ADEM ERASLAN 3O68UR0 (JARDIANCE,
    DM raporu 07.02.1 + reçetede N18 → yanlışlıkla Y_KBH'a gidiyordu).

    Kaleme bağlı rapor önceliği genişletmesi (2026-07-06, MUSTAFA TAŞKIN
    2O4QGJV — FORZIGA DM raporlu, reçetede SANELOC'un I50.9'u → yanlışlıkla
    Y_KY + "heyette kardiyolog yok" UYGUN DEĞİL üretiyordu):
      - Rapor kodu 04.01* (Kalp Yetmezliği) → metne bakmadan Y_KY.
      - Rapor kodu lookup'ı BOŞ gelebilir (RIRaporKodId yok) → rapor METNİ
        DM anlatıyorsa (rapor ICD satırı E10–E14 / "diyabet/diabetes/
        glisemik/HbA1c") bu da DM raporu sinyalidir; reçete ICD fallback'ine
        düşülmez. rapor_metni = rap_ack + ek bilgi + rapor ICD satırları
        olduğundan raporun kendi teşhisleri bu metinde aranabilir.
    """
    metin = norm_tr_lower(ilac_sonuc.get('rapor_metni') or '')
    teshisler = ilac_sonuc.get('recete_teshisleri') or []
    teshis_str = norm_tr_upper(' '.join(teshisler))

    ky_metin = bool(re.search(
        r'(kalp\s*yetersizli|kalp\s*yetmezli|nyha|ejeksiyon|\bef\s*[<≤])',
        metin))
    kbh_metin = bool(re.search(
        r'(kronik\s*b[oö]brek|\bkbh\b|\bkby\b|\bacr\b|\bpcr\b|proteinuri|persistan\s*protein)',
        metin))
    ky_icd = bool(re.search(r'\bI50(\.\d+)?\b', teshis_str))
    kbh_icd = bool(re.search(r'\bN18(\.\d+)?\b', teshis_str))

    rapor_kodu = str(ilac_sonuc.get('rapor_kodu') or '').strip()

    # Kaleme bağlı rapor KY raporuysa (04.01 Kalp Yetmezliği(I50)) raporun
    # kendisi endikasyonu söylüyor → metne bakmadan Y_KY.
    if rapor_kodu.startswith('04.01'):
        return 'Y_KY'

    # DM raporu sinyali: rapor kodu 07.02* VEYA rapor metni DM anlatıyor.
    # Kod lookup'ı boş gelebildiği için metin sinyali de kalem-rapor
    # önceliği sayılır (MUSTAFA TAŞKIN 2O4QGJV, 2026-07-06).
    dm_rapor = rapor_kodu.startswith('07.02') or bool(re.search(
        r'(\be1[0-4](\.\d+)?\b|diyabet|diabetes|glisemik|hba1c|'
        r'hemoglobin\s*a1c)', metin))
    if dm_rapor:
        # DM raporuna bağlı kalem: reçete ICD'si tek başına 4.2.74'e saptırmaz
        if ky_metin:
            return 'Y_KY'
        if kbh_metin:
            return 'Y_KBH'
        return 'Y6'

    if ky_metin or ky_icd:
        return 'Y_KY'
    if kbh_metin or kbh_icd:
        return 'Y_KBH'
    return 'Y6'


# ═══════════════════════════════════════════════════════════════════════
# Paylaşımlı atomik helper'lar
# ═══════════════════════════════════════════════════════════════════════

# Hekim branş eşleme — Medula'da gelen string'leri normalize eder
_BRANS_NORMALIZE = {
    'endokrinoloji': 'endokrin',
    'endokrinoloji ve metabolizma hastaliklari': 'endokrin',
    'endokrin': 'endokrin',
    'ic hastaliklari': 'ic',
    'iç hastaliklari': 'ic',
    'iç hastalıkları': 'ic',
    'dahiliye': 'ic',
    'cocuk sagligi ve hastaliklari': 'pediatri',
    'çocuk sağliği ve hastaliklari': 'pediatri',
    'çocuk sağlığı ve hastalıkları': 'pediatri',
    'cocuk': 'pediatri',
    'pediatri': 'pediatri',
    'kardiyoloji': 'kardiyo',
    'kardiyo': 'kardiyo',
    'aile hekimligi': 'aile_hek',
    'aile hekimliği': 'aile_hek',
    'aile hekimi': 'aile_hek',
}


_ASCII_TR_MAP = str.maketrans({
    'ı': 'i', 'î': 'i', 'ï': 'i',
    'ğ': 'g', 'ş': 's', 'ç': 'c', 'ö': 'o', 'ü': 'u',
})


def _ascii_normalize(s: str) -> str:
    """Türkçe karakterleri ASCII'ye düşür + combining markları sil.

    'İ'.lower() → 'i̇' (i + combining dot above); NFD ayrıştırır,
    sonra combining'ler silinir → 'i'. Ardından ı/ş/ç/ö/ü/ğ → i/s/c/o/u/g.
    """
    s = s.lower()
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.translate(_ASCII_TR_MAP)
    return s


def _brans_norm(brans: Optional[str]) -> str:
    """Branş string'ini normalize et."""
    if not brans:
        return ''
    s = _ascii_normalize(brans.strip())
    if s in _BRANS_NORMALIZE:
        return _BRANS_NORMALIZE[s]
    for anahtar, norm in _BRANS_NORMALIZE.items():
        anahtar_norm = _ascii_normalize(anahtar)
        if anahtar_norm in s:
            return norm
    return s


def atom_hekim_brans_uygun(
    ilac_sonuc: Dict,
    izinli: Set[str],
    grup: str = 'Reçete hekimi yetkisi',
) -> SartSonuc:
    """Reçete eden hekim branşı izinli kümeye dahil mi?

    izinli: ör. {'endokrin', 'ic', 'pediatri', 'kardiyo', 'aile_hek'}
    """
    brans = _brans_norm(ilac_sonuc.get('doktor_uzmanligi') or
                        ilac_sonuc.get('recete_hekim_uzmanligi'))
    if not brans:
        return SartSonuc(
            ad='Reçete eden hekim branşı',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Hekim branşı bilinmiyor — manuel doğrulama',
            kaynak='hekim_brans',
            grup=grup,
            veya_grubu=True,
            sartli_atom=True,
        )
    if brans in izinli:
        return SartSonuc(
            ad=f'Reçete hekimi: {brans}',
            durum=SartDurumu.VAR,
            neden=f'Yetkili branş ({brans})',
            kaynak='hekim_brans',
            grup=grup,
            veya_grubu=True,
        )
    return SartSonuc(
        ad=f'Reçete hekimi: {brans}',
        durum=SartDurumu.YOK,
        neden=f'Yetkili branşlardan biri olmalı: {", ".join(sorted(izinli))}',
        kaynak='hekim_brans',
        grup=grup,
        veya_grubu=True,
    )


def atom_uzman_raporu_brans(
    ilac_sonuc: Dict,
    izinli: Set[str],
    grup: str = 'Uzman hekim raporu',
) -> SartSonuc:
    """Reçeteye bağlı rapor, izinli bir branşın uzman hekim raporu mu?

    Rapor üzerindeki rapor doktoru branşı (varsa) izinli kümede ise VAR.
    """
    rapor_brans = _brans_norm(
        ilac_sonuc.get('rapor_doktor_brans')
        or ilac_sonuc.get('rapor_dr_brans')
        or ilac_sonuc.get('rapor_doktor_uzmanligi')
        or ilac_sonuc.get('rapor_uzmanlik')
    )
    if not rapor_brans:
        # Rapor doktoru branşı bilinmiyor — uzman raporu varlığını test edelim
        rapor_metin = norm_tr_lower(ilac_sonuc.get('rapor_metni') or '')
        rapor_kodu = (ilac_sonuc.get('rapor_kodu') or '').strip()
        rapor_takip = (ilac_sonuc.get('rapor_takip_no') or '').strip()
        # Rapor mevcudiyeti sinyali: kod veya takip no veya metin lafzı
        rapor_var = bool(rapor_kodu or rapor_takip or (
            rapor_metin and any(b in rapor_metin for b in
                                ['uzman hekim', 'uzman dr', 'uzm. dr',
                                 'uzm dr'])))
        if rapor_var:
            # Reçeteye bağlı rapor mevcut ama düzenleyen branş kaydı yok.
            # Production veride `rapor_doktor_uzmanligi` çoğu zaman boş gelir;
            # SUT 4.2.38 fıkraları reçete edilen ilacın türüne göre raporu
            # ilgili uzman branşına kısıtlar — bu nedenle KE+şartlı (manuel
            # doğrulama) en güvenli yorumdur. Yetki grubu (OR) tarafı reçete
            # hekimi VAR ise grup yine VAR olur; ikisi de KE/YOK olduğunda
            # ŞARTLI_UYGUN üretilir (kullanıcı kuralı 2026-05-24).
            return SartSonuc(
                ad='Uzman hekim raporu',
                durum=SartDurumu.KONTROL_EDILEMEDI,
                neden='Rapor mevcut ama düzenleyen hekim branşı sorgulanamıyor '
                      '— manuel doğrulanmalı',
                kaynak='rapor',
                grup=grup,
                veya_grubu=True,
                sartli_atom=True,
            )
        return SartSonuc(
            ad='Uzman hekim raporu',
            durum=SartDurumu.YOK,
            neden='Reçeteye bağlı uzman hekim raporu bulunamadı',
            kaynak='rapor',
            grup=grup,
            veya_grubu=True,
        )
    if rapor_brans in izinli:
        return SartSonuc(
            ad=f'Uzman hekim raporu: {rapor_brans}',
            durum=SartDurumu.VAR,
            neden=f'{rapor_brans} uzman hekim raporu',
            kaynak='rapor',
            grup=grup,
            veya_grubu=True,
        )
    return SartSonuc(
        ad=f'Uzman hekim raporu: {rapor_brans}',
        durum=SartDurumu.YOK,
        neden=f'Rapor düzenleyen branş yetkili değil ({rapor_brans})',
        kaynak='rapor',
        grup=grup,
        veya_grubu=True,
    )


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y1 — Tüm hekimler (Fıkra 1, rapor şartı YOK)
# ═══════════════════════════════════════════════════════════════════════

def y1_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y1: Met/Sulfo/Met+Sulfo/Akarboz/İnsan insülin → rapor şartı YOK.

    Tek atom: ilaç sınıfı doğrulaması (zaten dispatcher yaptı).
    """
    return [
        SartSonuc(
            ad='SUT 4.2.38(1) — Tüm hekimler reçete edebilir',
            durum=SartDurumu.VAR,
            neden='Metformin / sülfonilüre / akarboz / insan insülini — rapor şartı yok',
            kaynak='ilac_sinifi',
            grup='Fıkra (1) — temel OAD/insan insülin',
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y2 — Repaglinid / Nateglinid / OAD kombi (Fıkra 2)
# ═══════════════════════════════════════════════════════════════════════

Y2_IZINLI = {'endokrin', 'ic', 'pediatri', 'kardiyo', 'aile_hek'}


def y2_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y2: Repaglinid/Nateglinid/OAD kombi.

    PARALEL-YOL kalıbı (üst-VEYA çifti, klinik şart yok):
      Y2_UYGUN ⇔ [ Y2.1 ] ∨ [ Y2.2 ]
    """
    sartlar: List[SartSonuc] = []
    grup_raporsuz = '‖Y2‖ Raporsuz Yol — Hekim Endo/IH/Pediatri/Kardio/AileHek'
    grup_raporlu = '‖Y2‖ Raporlu Yol — Rapor Endo/IH/Pediatri/Kardio/AileHek'
    hekim_atomu = atom_hekim_brans_uygun(ilac_sonuc, Y2_IZINLI, grup=grup_raporsuz)
    hekim_atomu.veya_grubu = False
    sartlar.append(hekim_atomu)
    rapor_atomu = atom_uzman_raporu_brans(ilac_sonuc, Y2_IZINLI, grup=grup_raporlu)
    rapor_atomu.veya_grubu = False
    sartlar.append(rapor_atomu)
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y6 — SGLT-2 inhibitörleri (Fıkra 6)
# ═══════════════════════════════════════════════════════════════════════

Y6_IZINLI = {'endokrin', 'ic'}


def atom_metformin_sulfo_max_yetersiz(ilac_sonuc: Dict,
                                       grup: str = 'Klinik şart') -> SartSonuc:
    """Met VE/VEYA sülfonilüre max doz yetersiz glisemik kontrol?

    Rapor metninde ibareleri ara:
      - 'metformin' + 'max(simum) (tolere) doz' + 'yetersiz/sağlanama'
      - 'sülfonilüre' + benzer
    Halk yazımı varyantlarını tolere eder: max/maks/maximum/maxımum,
    tire-kırması ('sülfoni-lürelerin'), 'kontrolu/kontrolun' suffix,
    'max KULLANIM doz' gibi arada kelime, tıbben eşdeğer 'kan şekeri
    yeterince düşürülemedi' lafzı. Bulunmazsa KE.
    """
    # `_rapor_metni` helper rapor_metni VEYA rapor_aciklamalari fallback yapar
    # (eski wrapper/test'lerle uyumluluk için).
    metin_raw = ilac_sonuc.get('rapor_metni') or ''
    if not metin_raw:
        rap_acklari = ilac_sonuc.get('rapor_aciklamalari') or []
        if isinstance(rap_acklari, (list, tuple)):
            metin_raw = ' '.join(str(x) for x in rap_acklari if x)
        else:
            metin_raw = str(rap_acklari)
    if not metin_raw:
        return SartSonuc(
            ad='Metformin/sülfonilüre max doz yetersiz glisemik kontrol',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Rapor metni boş — klinik şart sorgulanamadı',
            kaynak='rapor_metni',
            grup=grup,
        )
    # Tire-kırması temizliği: Medula raporları bazen kelime ortasında tire
    # ekliyor ("sülfoni-lürelerin", "kont-rol", "doz-larda"). Pattern öncesi
    # tire ve takip eden boşluğu sil.
    metin = norm_tr_lower(re.sub(r'-\s*', '', metin_raw))

    # ─── METFORMİN — standart + typo varyantları ───────────────────────
    # Hedef yazımlar: metformin, metrformin (extra r), metfomrin / metfromin
    # (r ↔ m yer değiştirmesi — FATMA KAHRAMAN 2LONLCP, BAYRAM KARABAYIR
    # 2USHOJ3 raporları 2026-05-24).
    pat_met = re.compile(
        r'(?:metformin|metrformin|metfomrin|metfromin|metoformin)',
        re.IGNORECASE)

    # ─── SÜLFONİLÜRE — geniş varyant ──────────────────────────────────
    # Hedef: sülfonilüre, sülfanilüre, sülfanülüre, sülfanüre, sülfonure,
    # sulfoniure (i var l yok — SEVİM MERCAN 37PBI31), sülfanülüre
    # (ŞEVKET OKUMUŞ 3A83JP4), sülfanüre (PERİZADE AKGÜN 2P3ZIME,
    # NAHİDE ÇELİK 32JX9E8). [oa]=ön ünlü, [ıiuü]?l?=ara hece esnek.
    pat_sulfo = re.compile(
        r'(?:s[uü]lf[oa]n[ıiuü]?l?[uü]re'
        r'|gliklazid|glimepirid|glibenklamid|glipizid)',
        re.IGNORECASE)

    # ─── MAX DOZ — 4 ayrı pattern (OR ile birleşir) ───────────────────
    # (A) Standart: "maks/max/maksimum/maksimun + ... + (tolere ed*)? + doz"
    #     - "MAKSIMUN" typo: mu[mn] suffix (SEZAİ ÖZKAN 39LP3E1,
    #       AYŞEGÜL TELLİ 3GO3CGD)
    #     - "MAKSIMAL/MAXIMAL" (MEHMET ÇITAK 3A0MDCJ, FATMA KAHRAMAN
    #       2LONLCP, BAYRAM KARABAYIR 2USHOJ3)
    #     - "EDILEN" suffix (bil eksik — SİNAN DEMİRHAN 3HKETUW,
    #       HALİL ÇEVİK 3GTF6YY): ed\w* daha esnek
    #     - "KULLANIM DOZUNDA" (tolere ile doz arası kelime — AYŞEGÜL
    #       TELLİ 3GO3CGD): tolere sonrası 0-3 kelime
    pat_max_a = re.compile(
        r'(?:'
        r'(?:maks?|max|maxs?)\w{0,3}mu[mn]'   # maksimum/maximum/maksimun/maxsimum
        r'|\b(?:maks?|max)\b'                 # kısa form
        r'|\b(?:maks|max)imal\w*'             # maksimal/maximal
        r')'
        r'\.?\s*(?:\w+\s+){0,3}'              # max ile (tolere|doz) arası 0-3 sözcük
        r'(?:toler[ae]\s+ed\w*[\s\.,;:]*(?:\w+\s+){0,3})?'  # tolere ed* + 0-3 söz
        r'(?:doz|d[uü]zey)',
        re.IGNORECASE)
    # (B) Reverse order: "tolere ed* + ... + maks + ... + doz"
    #     - FADİM YÜKSEL 3NC6FI8, 2UGGHWN ("tolere edebilecek maksimum doz")
    #     - CENNET ÇAĞLAR 2R8LQZT ("tolere edilebilir maksimum doz")
    pat_max_b_reverse = re.compile(
        r'toler[ae]\s+ed\w*\s+(?:\w+\s+){0,3}'
        r'(?:(?:maks?|max|maxs?)\w{0,3}mu[mn]|\b(?:maks|max)imal\w*)'
        r'\.?\s*(?:\w+\s+){0,3}(?:doz|d[uü]zey)',
        re.IGNORECASE)
    # (C) Implicit max: "tolere ed* + doz" (max ibaresi yok ama klinik
    #     eşdeğer — hekim 'tolere edilebilir doz' yazdığında max'i ima eder)
    #     - AYŞE KÜÇÜK 3FCXSUL/3BSRW37 ("tolere edilebilir dozunda yetersiz")
    pat_max_c_implicit = re.compile(
        r'toler[ae]\s+ed\w*\s+(?:\w+\s+){0,2}(?:doz|d[uü]zey)',
        re.IGNORECASE)
    # (D) "tolere ed* + maks + (ilaç/kullanım)" — doz lafzı yok (ŞEVKET
    #     OKUMUŞ 3A83JP4: "tolera edebilecegi maksimum metformin ve
    #     sulfanulure kullanmis"). max+kullan/tedavi/uygula bağlamı.
    pat_max_d_no_doz = re.compile(
        r'(?:'
        r'toler[ae]\s+ed\w+\s+(?:\w+\s+){0,3}'
        r'(?:(?:maks?|max|maxs?)\w{0,3}mu[mn]|\b(?:maks|max)imal\w*)'
        r'|(?:(?:maks?|max|maxs?)\w{0,3}mu[mn]|\b(?:maks|max)imal\w*)'
        r'\s+(?:\w+\s+){0,5}(?:kullan|tedavi|uygula)'
        r')',
        re.IGNORECASE)

    # ─── YETERSİZ KONTROL — kapsamlı lafız listesi ────────────────────
    pat_yet = re.compile(
        r'(?:'
        # "yetersiz [glisemik] kontrol" — tek başına yeterli
        r'yetersiz\s*(?:glisemik\s*)?kontrol'
        # "yeterli + (0-2 söz) + kontrol(...) + (0-2 söz) + sağla(nam/nma/yam)"
        #  - "yeterli oranda glisemik kontrol saglanam" (MELİKE DAĞ 2TYB4GA,
        #    MEHMET KILIÇALP 30RRUTR, FATMA BEHREM 2YK7HF2)
        #  - "yeterli glisemik kontrol HASTADA saglanam" (SEZAİ ÖZKAN 39LP3E1)
        #  - "yeterli duzeyde kontrol saglanam" (EMİNE UZUN 3JVSGG2)
        #  - "yeterli glisemik kontrolu SAGLAYAMAMIS" (FADİM YÜKSEL —
        #    sağlay variant: yam)
        #  - typo toleransı: "yeterli glismeik/glismik kontrol" (FATMA
        #    KAHRAMAN, BAYRAM KARABAYIR — 0-2 ara sözcük yakalar)
        r'|yeterli\s*(?:\w+\s+){0,2}'
        r'kontrol(?:u|un|undan|larda|lerde|ler|leri)?\s*(?:\w+\s+){0,2}'
        r'sa[gğ]la(?:nam|nma|yam|yama)'
        # "kontrol(u/...)? sağlanama" — bare (yeterli prefix yok, ELIF gibi)
        r'|kontrol(?:u|un|undan|larda|lerde|ler|leri)?\s*sa[gğ]lanama'
        # "kontrol edilem(eyen/edi)" — HALİL ÇEVİK 3GTF6YY
        r'|kontrol(?:u|un|larda|lerde)?\s*edil(?:em|m)e'
        # "(glisemik|kan seker(i)?|glukoz|glikoz|ks) regülasyon(u) ...
        #  saglanam" — kelime arası 0-3 söz (EMİNE UZUN: regulasyonu
        #  YETERLİ DÜZEYDE saglanam)
        #  - HAMDULLAH AKSU 33CUC0E, HAVVA KARAARSLAN 2Q0279X: "kan seker
        #    regulasyonu" (i eksik)
        #  - PERİZADE AKGÜN 2P3ZIME: "glukoz regulasyon"
        #  - EMİN ERARSLAN 2SRQD0J: "kan sekeri regulasyonu"
        r'|(?:glisemik|kan\s*seker[ıi]?|glukoz|glikoz|\bks)\s*'
        r'reg[uü]lasyon(?:u|un|unu|undan)?'
        r'\s*(?:\w+\s+){0,3}sa[gğ]lanam'
        # "regule (olm/edil(em)/degil)" — tek başına yeterli
        #  - "regule olmayan/olmamis" (MEHMET ÇITAK 3A0MDCJ, FATMA YILMAZ
        #    3MTPNTP, MAKBULE TEKİN 2NPHE6Z, NAHİDE ÇELİK 32JX9E8)
        #  - "regule edilemedi/edilememis" (CENNET ÇAĞLAR 2R8LQZT,
        #    PERİZADE AKGÜN 2P3ZIME)
        #  - "regule degil" (SİNAN DEMİRHAN 3HKETUW)
        #  - Typo "reugle" (MAKBULE TEKİN 2NPHE6Z): re[uü]gle
        r'|re(?:g[uü]|[uü]g)le\s*(?:olm|edil(?:em|m)e|de[gğ]il)'
        # "normoglisemi saglanam" — SEVİM MERCAN 37PBI31
        r'|normoglisemi\s*sa[gğ]lanam'
        # "glisemik kontrol elde edilm" — KUDUSE GÜLER 2 varyantı
        r'|glisemik\s*kontrol(?:u)?\s*(?:elde\s*)?edil(?:em|m)'
        # "kan şekeri (yeterince) düşürülemedi" — MUZAFFER ŞAHİN
        r'|kan\s*sekeri\s*(?:yeterince\s*)?dusurul\w*'
        # "yeterli [glisemik] yanıt alınama" — SABRİYE ERBAŞ
        r'|yeterli\s*(?:glisemik\s*)?yan[ıi]t\s*al[ıi]nam'
        r')',
        re.IGNORECASE)

    var_met = bool(pat_met.search(metin))
    # EMİNE UZUN 3JVSGG2 özel: "METFORMİN VE SÜ İLE KŞ REGÜLASYONU..."
    # — "SÜ" kısaltma = sülfonilüre. Bağlama bağlı, sadece "metformin ve sü"
    # kombinasyonunda kabul et (yalnız 'su' kelimesi başka anlamda olabilir).
    var_sulfo = bool(pat_sulfo.search(metin)) or bool(re.search(
        r'metformin\s+ve\s+s[uü]\b\s*(?:ile|tedavi|grub|kombin)',
        metin, re.IGNORECASE))
    var_max = (bool(pat_max_a.search(metin))
               or bool(pat_max_b_reverse.search(metin))
               or bool(pat_max_c_implicit.search(metin))
               or bool(pat_max_d_no_doz.search(metin)))
    var_yet = bool(pat_yet.search(metin))

    # (1) Max ibaresi + yetersiz kontrol + en az bir ilaç → VAR (kesin SUT)
    if (var_met or var_sulfo) and var_max and var_yet:
        return SartSonuc(
            ad='Metformin/sülfonilüre max doz yetersiz glisemik kontrol',
            durum=SartDurumu.VAR,
            neden='Rapor lafzında "max doz" + "yetersiz kontrol" ibareleri bulundu',
            kaynak='rapor_metni',
            grup=grup,
        )
    # (2) Hem metformin hem sülfonilüre AÇIKÇA isimlendirilmiş + yetersiz
    # kontrol → VAR (max ibaresi olmasa bile). Klinik gerekçe: hekim her
    # iki ilacı da yazıp "kontrol saglanmadi" diyorsa SUT'un istediği
    # kombinasyon tedavisi yetersizliği lafzen ifade edilmiş demektir.
    #  - MELİKE DAĞ 2TYB4GA, MEHMET KILIÇALP 30RRUTR, FATMA BEHREM 2YK7HF2:
    #    "metformin ve sulfonilurelerin yeterli oranda kontrol saglanam"
    #  - EMİN ERARSLAN 2SRQD0J: "3 aydan fazla sulfonilurele ve metformin
    #    kullanimina ragmen kan sekeri regulasyonu saglanam"
    if var_met and var_sulfo and var_yet:
        return SartSonuc(
            ad='Metformin/sülfonilüre max doz yetersiz glisemik kontrol',
            durum=SartDurumu.VAR,
            neden='Hem metformin hem sülfonilüre + yetersiz kontrol — '
                  'kombi tedavi başarısızlığı lafzen ifade edilmiş',
            kaynak='rapor_metni',
            grup=grup,
        )
    if var_yet and (var_met or var_sulfo):
        # Max doz ibaresi yok, tek ilaç + yetersiz kontrol — şartlı (KE)
        return SartSonuc(
            ad='Metformin/sülfonilüre max doz yetersiz glisemik kontrol',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Yetersiz kontrol ibaresi var ama "maksimum tolere doz" net değil',
            kaynak='rapor_metni',
            grup=grup,
            sartli_atom=True,
        )
    return SartSonuc(
        ad='Metformin/sülfonilüre max doz yetersiz glisemik kontrol',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Rapor lafzında klinik şart ibaresi bulunamadı — manuel doğrulama',
        kaynak='rapor_metni',
        grup=grup,
        sartli_atom=True,
    )


def y6_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y6: SGLT-2 inhibitörleri (dapa/empa) + kombineleri.

    PARALEL-YOL kalıbı (2026-05-25, üst-VEYA çifti):
      Y6_UYGUN ⇔ [ Y6.2 ]               ; RAPORSUZ YOL
                 ∨
                 [ Y6.3 ∧ Y6.1 ]         ; RAPORLU YOL

      Y6.1 = Met VE/VEYA Sulfo max doz yetersiz glisemik kontrol
      Y6.2 = reçete hekimi ∈ {Endo, IH}
      Y6.3 = uzman raporu (Endo/IH)

    Klinik şart (Y6.1) RAPORSUZ yolda hekim sorumluluğunda kalır → bilgi
    atomu olarak görünür, matematiğe katmaz.
    """
    sartlar: List[SartSonuc] = []
    grup_raporsuz = '‖Y6‖ Raporsuz Yol — Hekim Endo/IH'
    grup_raporsuz_bilgi = '‖Y6‖ Raporsuz Yol — Klinik şart hekim sorumluluğu (bilgi)'
    grup_raporlu = '‖Y6‖ Raporlu Yol — Rapor Endo/IH + Klinik şart'

    # RAPORSUZ YOL: tek atom (hekim Endo/IH)
    hekim_atomu = atom_hekim_brans_uygun(
        ilac_sonuc, Y6_IZINLI, grup=grup_raporsuz)
    hekim_atomu.veya_grubu = False  # tek-atom AND
    sartlar.append(hekim_atomu)
    # Raporsuz yolda klinik şart bilgi olarak gösterilsin (matematiğe katmaz)
    sartlar.append(SartSonuc(
        ad='Klinik şart (Met/Sulfo max yetersiz) — raporsuz yolda hekim sorumluluğunda',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Endo/IH uzmanı raporsuz yazma yetkisine sahip; klinik şart '
              'hekim sorumluluğunda (eczacı/sistem doğrulayamaz)',
        kaynak='hekim_sorumluluk', grup=grup_raporsuz_bilgi,
        sartli_atom=True))

    # RAPORLU YOL: rapor branşı Endo/IH + klinik şart (AND, aynı grupta)
    rapor_atomu = atom_uzman_raporu_brans(
        ilac_sonuc, Y6_IZINLI, grup=grup_raporlu)
    rapor_atomu.veya_grubu = False  # raporlu yolda AND
    sartlar.append(rapor_atomu)
    klinik_atomu = atom_metformin_sulfo_max_yetersiz(
        ilac_sonuc, grup=grup_raporlu)
    klinik_atomu.veya_grubu = False
    sartlar.append(klinik_atomu)
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# PAYLAŞIMLI ATOMLAR — Y3b / Y5 / Y7 / Y8 / Y_KY / Y_KBH
# (Karar Defteri 2026-05-24: S1=A, S2=C, S3=A, S4=A)
# ═══════════════════════════════════════════════════════════════════════

def _rapor_metni(ilac_sonuc: Dict) -> str:
    """Rapor metni TR→ASCII lower-case (regex search için).

    Alan öncelikleri (GUI/wrapper farklılığı için tolerans):
      1. rapor_metni — yeni motor standart alanı
      2. rapor_aciklamalari (list) — eski wrapper ve bazı testlerin alanı,
         birleşik metin olarak okunur
    """
    raw = ilac_sonuc.get('rapor_metni') or ''
    if not raw:
        rap_acklari = ilac_sonuc.get('rapor_aciklamalari') or []
        if isinstance(rap_acklari, (list, tuple)):
            raw = ' '.join(str(x) for x in rap_acklari if x)
        else:
            raw = str(rap_acklari)
    return norm_tr_lower(raw)


def _diger_kalemler_iceriyor(ilac_sonuc: Dict, kume: Set[str]) -> bool:
    """Aynı reçetedeki DİĞER kalemler kümede mi? (TR→ASCII normalize)"""
    diger = ilac_sonuc.get('recete_ilaclari') or []
    parcalar: List[str] = []
    for kalem in diger:
        if isinstance(kalem, dict):
            parcalar.append(norm_tr_upper(str(kalem.get('ad') or '')))
            parcalar.append(norm_tr_upper(str(kalem.get('etkin_madde') or '')))
        else:
            parcalar.append(norm_tr_upper(str(kalem)))
    metin = ' '.join(parcalar)
    return any(k in metin for k in kume)


def _hasta_ilac_gecmisi_iceriyor(ilac_sonuc: Dict, kume: Set[str]) -> bool:
    """Hastanın daha önce kullandığı ilaçlar kümede mi? (TR→ASCII normalize)

    `hasta_ilac_gecmisi` alanı GUI tarafından doldurulmazsa False döner
    (S1/S4 kalıbı: yerel DB yoksa atom üst tarafta KE üretmeli).
    """
    gecmis = ilac_sonuc.get('hasta_ilac_gecmisi') or []
    if not gecmis:
        return False
    parcalar: List[str] = []
    for kalem in gecmis:
        if isinstance(kalem, dict):
            parcalar.append(norm_tr_upper(str(kalem.get('ad') or '')))
            parcalar.append(norm_tr_upper(str(kalem.get('etkin_madde') or '')))
        else:
            parcalar.append(norm_tr_upper(str(kalem)))
    metin = ' '.join(parcalar)
    return any(k in metin for k in kume)


def _hasta_ilac_gecmisi_var_mi(ilac_sonuc: Dict) -> bool:
    """Hastanın ilaç geçmişi verisi mevcut mu? (yok ise KE kararı için)"""
    return bool(ilac_sonuc.get('hasta_ilac_gecmisi'))


# ────────────────────────────────────────────────────────────────────────
# Tip 2 DM / Yetişkin
# ────────────────────────────────────────────────────────────────────────

def atom_tip2_dm_var(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Tip 2 DM teşhisi: ICD E11.x VEYA rapor metni."""
    teshisler = ilac_sonuc.get('recete_teshisleri') or []
    teshis_str = norm_tr_upper(' '.join(teshisler))
    if re.search(r'\bE11(\.\d+)?\b', teshis_str):
        return SartSonuc(
            ad='Tip 2 DM teşhisi', durum=SartDurumu.VAR,
            neden='ICD E11.x bulundu', kaynak='teshis', grup=grup)
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'(tip\s*2\s*diabet|tip\s*2\s*dm|tip\s*ii\s*diabet|t2dm)', metin):
        return SartSonuc(
            ad='Tip 2 DM teşhisi', durum=SartDurumu.VAR,
            neden='Rapor lafzında "Tip 2 DM" bulundu', kaynak='rapor', grup=grup)
    return SartSonuc(
        ad='Tip 2 DM teşhisi', durum=SartDurumu.YOK,
        neden='ICD E11.x ve rapor lafzı bulunamadı',
        kaynak='teshis+rapor', grup=grup)


def atom_yetiskin_18ust(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Hasta yaşı ≥18 mi? (Y7 için zorunlu)."""
    yas_raw = ilac_sonuc.get('hasta_yasi')
    try:
        yas = int(re.findall(r'\d+', str(yas_raw))[0]) if yas_raw else None
    except (ValueError, IndexError):
        yas = None
    if yas is None:
        return SartSonuc(
            ad='Yetişkin (≥18)', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Hasta yaşı bilinmiyor', kaynak='hasta', grup=grup,
            sartli_atom=True)
    if yas >= 18:
        return SartSonuc(
            ad=f'Yetişkin (yaş={yas})', durum=SartDurumu.VAR,
            neden=f'Yaş {yas} ≥18', kaynak='hasta', grup=grup)
    return SartSonuc(
        ad=f'Yetişkin (yaş={yas})', durum=SartDurumu.YOK,
        neden=f'Yaş {yas} <18 — Y7 yetişkin hasta şartı sağlanmıyor',
        kaynak='hasta', grup=grup)


# ────────────────────────────────────────────────────────────────────────
# BMI > 35 (S3=A: rapor lafzı öncelikli, yoksa şu anki BMI)
# ────────────────────────────────────────────────────────────────────────

def atom_bmi_35_ustu(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """BMI > 35 (tedavi başlangıcı).

    Karar S3=A: rapor metninde "tedavi başlangıcında BMI/VKİ X" lafzı varsa
    onu kullan; yoksa hasta kilo/boy → BMI hesapla.
    """
    metin = _rapor_metni(ilac_sonuc)
    # Rapor lafzı öncelikli — 3 varyant:
    # 1) "BMI/VKİ X" sayısal (kısa form)
    # 2) "VÜCUT KİTLE/KÜTLE İNDEKSİ X" sayısal (uzun form)
    # 3) "X KG/M² ÜZERİNDE OLAN" lafzı (SUT ibaresi alıntısı — AYNUR YILMAZ)
    m = re.search(
        r'(?:tedavi\s*ba[sş]lang[ıi]c[ıi]nda)?\s*'
        r'(?:bmi|vk[ıi]|v[uü]c[uü]t\s*k[ıi]t(?:le|tle)?\s*[ıi]ndeks[ıi])'
        r'\s*[:=]?\s*(\d+(?:[.,]\d+)?)',
        metin)
    if m:
        try:
            bmi_rapor = float(m.group(1).replace(',', '.'))
            if bmi_rapor > 35:
                return SartSonuc(
                    ad=f'BMI > 35 (rapor: {bmi_rapor:.1f})', durum=SartDurumu.VAR,
                    neden=f'Rapor lafzı BMI={bmi_rapor:.1f} > 35',
                    kaynak='rapor', grup=grup)
            return SartSonuc(
                ad=f'BMI > 35 (rapor: {bmi_rapor:.1f})', durum=SartDurumu.YOK,
                neden=f'Rapor lafzı BMI={bmi_rapor:.1f} ≤ 35',
                kaynak='rapor', grup=grup)
        except ValueError:
            pass

    # 2026-05-24: SUT lafzı alıntısı — "35 KG/M² ÜZERİNDE/ÜSTÜNDE OLAN"
    # AYNUR YILMAZ pilot: "...VÜCUT KİTLE İNDEKSİ TEDAVİ BAŞLANGICINDA
    # 35 KG/M2 NİN ÜZERİNDE OLAN VE... TİP 2 DİYABET HASTASI" — doktor
    # bu hastanın eşik üstü olduğunu beyan ediyor → VAR (≥35 ise).
    # 2026-05-24 ek: "35 KG/M'NİN ÜZERİNDE" varyantı — m ile NİN arasında
    # apostrof (' veya unicode ’/‘) bulunuyor; \w word char değil, possessive
    # eki yakalanmıyordu. AYNUR YILMAZ 3BYHF7H (15.02.2025) pilot.
    m_eshik = re.search(
        r'(\d+(?:[.,]\d+)?)\s*kg\s*/?\s*m\s*[²2\^]?\s*'
        r"['’‘]?\s*\w{0,5}\s*"
        r'(?:[uü]zerinde|[uü]st[uü]nde|[uü]zeri\b|[uü]st[uü]\b)',
        metin)
    if m_eshik:
        try:
            eshik = float(m_eshik.group(1).replace(',', '.'))
            if eshik >= 35:
                return SartSonuc(
                    ad=f'BMI > 35 (rapor lafzı: ≥{eshik:.0f} kg/m²)',
                    durum=SartDurumu.VAR,
                    neden=f'Rapor "{eshik:.0f} kg/m² üzerinde" beyan ediyor',
                    kaynak='rapor', grup=grup)
        except ValueError:
            pass

    # Fallback: şu anki kilo/boy
    kilo = ilac_sonuc.get('hasta_kilo')
    boy = ilac_sonuc.get('hasta_boy')
    try:
        kilo_f = float(kilo) if kilo else None
        boy_f = float(boy) if boy else None
    except (TypeError, ValueError):
        kilo_f = boy_f = None
    if kilo_f and boy_f and boy_f > 0:
        boy_m = boy_f / 100.0 if boy_f > 3 else boy_f  # cm → m
        bmi = kilo_f / (boy_m * boy_m)
        if bmi > 35:
            return SartSonuc(
                ad=f'BMI > 35 (mevcut: {bmi:.1f})', durum=SartDurumu.VAR,
                neden=f'Hasta kilo/boy ile BMI={bmi:.1f} > 35',
                kaynak='hasta', grup=grup)
        return SartSonuc(
            ad=f'BMI > 35 (mevcut: {bmi:.1f})', durum=SartDurumu.YOK,
            neden=(f'Hasta mevcut BMI={bmi:.1f} ≤ 35; '
                   'tedavi başlangıcında daha yüksek olabilir — manuel doğrula'),
            kaynak='hasta', grup=grup, sartli_atom=True)

    return SartSonuc(
        ad='BMI > 35 (tedavi başlangıcı)', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Rapor lafzı ve hasta kilo/boy verisi yok — manuel doğrula',
        kaynak='rapor+hasta', grup=grup, sartli_atom=True)


# ────────────────────────────────────────────────────────────────────────
# Akut pankreatit YOK (NEG — örtük kabul yasak, sessiz=KE)
# ────────────────────────────────────────────────────────────────────────

def atom_akut_pankreatit_yok_neg(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """NEG atom: pankreatit öyküsü YOK olmalı (sessiz=KE)."""
    teshisler = ilac_sonuc.get('recete_teshisleri') or []
    teshis_str = norm_tr_upper(' '.join(teshisler))
    if re.search(r'\bK85(\.\d+)?\b', teshis_str):
        return SartSonuc(
            ad='Akut pankreatit öyküsü YOK', durum=SartDurumu.YOK,
            neden='ICD K85.x (akut pankreatit) bulundu — kontrendikasyon',
            kaynak='teshis', grup=grup)
    metin = _rapor_metni(ilac_sonuc)
    pat_var = re.compile(
        r'(?:akut\s*pankreatit|pankreatit\s*[öo]yk[üu]s[üu]?|pankreatit\s*ge[çc]i)',
        re.IGNORECASE)
    # 2026-05-24: rapor lafzı varyantları — "geçirilme/geçirme" arada kelime,
    # "bulunmayan/bulunmamaktadır/olmayan" eki, "negatif/saptanmamış" eşdeğerleri.
    # Önceki pattern sadece "bulunmama/olmama" yakalıyordu — "bulunmayan"
    # substring değildi, yanlış pozitif VAR'a düşüyordu (AYNUR YILMAZ vakası).
    pat_yok = re.compile(
        r'(?:akut\s*pankreatit\s*(?:ge[çc]ir(?:il)?\w*\s*)?'
        r'(?:[öo]yk[üu]s[üu]?\s*)?'
        r'(?:yok(?:tur|sa|mus|m[ıi][şs])?|bulunma\w*|olmama\w*|olmayan\w*'
        r'|saptanma\w*|tespit\s*edilme\w*|g[öo]r[uü]lme\w*'
        r'|me?vcut\s*de[gğ]il|negatif)'
        r'|pankreatit\s*(?:ge[çc]ir(?:il)?\w*\s*)?'
        r'(?:[öo]yk[üu]s[üu]?\s*)?'
        r'(?:yok(?:tur|sa|mus|m[ıi][şs])?|bulunma\w*|olmama\w*|olmayan\w*'
        r'|saptanma\w*|tespit\s*edilme\w*|g[öo]r[uü]lme\w*'
        r'|me?vcut\s*de[gğ]il|negatif))',
        re.IGNORECASE)
    pos = bool(pat_var.search(metin))
    neg = bool(pat_yok.search(metin))
    if neg:
        return SartSonuc(
            ad='Akut pankreatit öyküsü YOK', durum=SartDurumu.VAR,
            neden='Rapor lafzı "pankreatit yok/bulunmamaktadır"',
            kaynak='rapor', grup=grup)
    if pos:
        return SartSonuc(
            ad='Akut pankreatit öyküsü YOK', durum=SartDurumu.YOK,
            neden='Rapor lafzı pankreatit öyküsü VAR — kontrendikasyon',
            kaynak='rapor', grup=grup)
    # Sessiz → KE (örtük kabul yasak)
    return SartSonuc(
        ad='Akut pankreatit öyküsü YOK', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Rapor sessiz — pankreatit öyküsü manuel doğrulanmalı (örtük kabul yasak)',
        kaynak='rapor+teshis', grup=grup, sartli_atom=True)


# ────────────────────────────────────────────────────────────────────────
# Y_KY: EF / NYHA / KY tedavi 4'lüsü / kullanılamama gerekçesi / kardiyolog
# ────────────────────────────────────────────────────────────────────────

def atom_ef_40_alti(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """EF ≤ %40 (sol ventrikül).

    Yakalanan formatlar:
      - "EF %35", "EF: 30%", "LVEF 25", "ejeksiyon fraksiyonu 35"
      - "EF<%40", "EF<40", "EF<=40", "EF>40" (operatörlü)

    Operatörlü değerlerde mantık:
      - "<val" → EF < val → val ≤ 41 ise EF ≤ 40 garanti → VAR
      - ">val" → EF > val → val ≥ 40 ise EF > 40 garanti → YOK
      - diğer → direkt karşılaştırma
    """
    metin = _rapor_metni(ilac_sonuc)
    # Operatör de yakalanır: <, >, =, : ya da yok
    pat = re.compile(
        r'(?:lvef|ef|ejeksiyon\s*fraksiyon[u]?)\s*([<>=:]?)\s*[%]?\s*(\d{1,3})\s*[%]?',
        re.IGNORECASE)
    m = pat.search(metin)
    if not m:
        return SartSonuc(
            ad='EF ≤ %40 (sol ventrikül)', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Rapor metninde EF değeri bulunamadı — manuel doğrula',
            kaynak='rapor', grup=grup, sartli_atom=True)
    op = m.group(1) or ''
    try:
        ef = int(m.group(2))
    except ValueError:
        return SartSonuc(
            ad='EF ≤ %40', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='EF değeri parse edilemedi', kaynak='rapor', grup=grup,
            sartli_atom=True)
    if op == '<':
        if ef <= 41:
            return SartSonuc(
                ad=f'EF ≤ %40 (rapor: <%{ef})', durum=SartDurumu.VAR,
                neden=f'Rapor: EF<%{ef} → EF ≤ %40 garanti',
                kaynak='rapor', grup=grup)
        return SartSonuc(
            ad=f'EF ≤ %40 (rapor: <%{ef})', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden=f'Rapor: EF<%{ef} — kesin değer bilinmiyor; manuel doğrula',
            kaynak='rapor', grup=grup, sartli_atom=True)
    if op == '>':
        if ef >= 40:
            return SartSonuc(
                ad=f'EF ≤ %40 (rapor: >%{ef})', durum=SartDurumu.YOK,
                neden=f'Rapor: EF>%{ef} → EF > %40 garanti',
                kaynak='rapor', grup=grup)
        return SartSonuc(
            ad=f'EF ≤ %40 (rapor: >%{ef})', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden=f'Rapor: EF>%{ef} — kesin değer bilinmiyor; manuel doğrula',
            kaynak='rapor', grup=grup, sartli_atom=True)
    if ef <= 40:
        return SartSonuc(
            ad=f'EF ≤ %40 (rapor: %{ef})', durum=SartDurumu.VAR,
            neden=f'EF=%{ef} ≤ %40', kaynak='rapor', grup=grup)
    return SartSonuc(
        ad=f'EF ≤ %40 (rapor: %{ef})', durum=SartDurumu.YOK,
        neden=f'EF=%{ef} > %40; KY ek endikasyonu (4.2.74-1) için uygun değil',
        kaynak='rapor', grup=grup)


def atom_nyha_2_4(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """NYHA sınıf II–IV (semptomatik KY).

    İki aşamalı tarama:
      1) Rapor (TR→ASCII lower) içinde "nyha" konumu bulunur.
      2) NYHA'dan sonraki 60 karakterlik pencerede sınıf belirteci aranır
         (i/ii/iii/iv VEYA 1-4). Pencere yaklaşımı, "(NYHA ) sınıf II-IV)"
         gibi araya fazladan parantez/boşluk giren bozuk yazımları da yakalar.
      3) Birden fazla sınıf bulunursa (örn "II-IV") en yüksek değer alınır.
    """
    metin = _rapor_metni(ilac_sonuc)  # TR→ASCII lower (roman'lar i/v olur)
    # "nyha" geçen tüm konumların sonuncusunu al — rapor genelde ilk geçişte sınıf yazar
    nyha_iters = list(re.finditer(r'nyha', metin))
    if not nyha_iters:
        return SartSonuc(
            ad='NYHA sınıf II–IV', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Rapor metninde NYHA sınıfı bulunamadı — manuel doğrula',
            kaynak='rapor', grup=grup, sartli_atom=True)
    # En yakın sınıfı bulmak için her NYHA'dan sonraki pencerede ara
    siniflar: List[int] = []
    raw_tokens: List[str] = []
    roma_arap = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4}
    for nm in nyha_iters:
        pencere = metin[nm.end(): nm.end() + 60]
        # Sınıf belirteçleri — kelime sınırı (lookahead/lookbehind ile harf bitişiği yasak)
        tokens = re.findall(
            r'(?<![a-z])(iv|iii|ii|i|[1-4])(?![a-z0-9])', pencere)
        for tok in tokens:
            if tok in roma_arap:
                siniflar.append(roma_arap[tok])
                raw_tokens.append(tok.upper())
            elif tok.isdigit():
                v = int(tok)
                if 1 <= v <= 4:
                    siniflar.append(v)
                    raw_tokens.append(tok)
        if siniflar:
            break  # ilk bulduğun NYHA'dan sonra dur
    if not siniflar:
        return SartSonuc(
            ad='NYHA sınıf II–IV', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='NYHA sonrası sınıf belirteci bulunamadı',
            kaynak='rapor', grup=grup, sartli_atom=True)
    en_yuksek = max(siniflar)
    en_dusuk = min(siniflar)
    ham = '-'.join(raw_tokens) if len(raw_tokens) > 1 else raw_tokens[0]
    if 2 <= en_yuksek <= 4:
        return SartSonuc(
            ad=f'NYHA sınıf II–IV (rapor: {ham})', durum=SartDurumu.VAR,
            neden=f'NYHA {ham} → semptomatik KY (II–IV)',
            kaynak='rapor', grup=grup)
    return SartSonuc(
        ad=f'NYHA sınıf II–IV (rapor: {ham})', durum=SartDurumu.YOK,
        neden=f'NYHA {ham} → semptomatik KY (II–IV) şartı sağlanmıyor',
        kaynak='rapor', grup=grup)


def _ilac_sinifi_sglt2(ilac_sonuc: Dict) -> str:
    """Reçetedeki SGLT-2 etken maddesi → 'dapa' / 'empa' / 'diger' / ''."""
    arama = _arama_metni(ilac_sonuc)
    if 'DAPAGLIFLOZIN' in arama or 'FORZIGA' in arama or 'FORXIGA' in arama:
        return 'dapa'
    if 'EMPAGLIFLOZIN' in arama or 'JARDIANCE' in arama or 'SYNJARDY' in arama:
        return 'empa'
    if _iceriyor(arama, SGLT2):
        return 'diger'
    return ''


def atom_egfr_uygun(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """eGFR ≥ X (dapa için 25, empa için 20).

    Yakalanan formatlar:
      - "eGFR 25", "eGFR:25", "eGFR ≥25", "eGFR >25"
      - "eGFR değeri >25" (araya giren kelime tolere edilir, lazy window)
      - "eGFR (>25 ml/dk)"

    Operatörlü mantık:
      - ">val" veya "≥val" → eGFR ≥ val → val ≥ esik ise VAR
      - "<val" veya "≤val" → eGFR ≤ val → val ≥ esik ise KE, val < esik ise YOK
    """
    sinif = _ilac_sinifi_sglt2(ilac_sonuc)
    esik = 25 if sinif == 'dapa' else 20 if sinif == 'empa' else 20
    metin = _rapor_metni(ilac_sonuc)
    # eGFR'den sonra 30 karakter içinde (operatör yok-da-olabilir) sayı yakala
    pat = re.compile(
        r'egfr\b[^\d<>≤≥=:]{0,30}?([<>≤≥=:]?)\s*(\d{1,3})\b',
        re.IGNORECASE)
    m = pat.search(metin)
    if not m:
        return SartSonuc(
            ad=f'eGFR ≥ {esik} (dapa≥25 / empa≥20)',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Rapor metninde eGFR değeri bulunamadı',
            kaynak='rapor', grup=grup, sartli_atom=True)
    op = m.group(1) or ''
    try:
        egfr = int(m.group(2))
    except ValueError:
        return SartSonuc(
            ad=f'eGFR ≥ {esik}', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='eGFR değeri parse edilemedi', kaynak='rapor', grup=grup,
            sartli_atom=True)
    if op in ('>', '≥'):
        if egfr >= esik:
            return SartSonuc(
                ad=f'eGFR ≥ {esik} (rapor: >{egfr})', durum=SartDurumu.VAR,
                neden=f'Rapor: eGFR>{egfr} ≥ {esik} ({sinif or "SGLT-2"} sınırı)',
                kaynak='rapor', grup=grup)
        return SartSonuc(
            ad=f'eGFR ≥ {esik} (rapor: >{egfr})', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden=f'Rapor: eGFR>{egfr} — kesin değer bilinmiyor; manuel doğrula',
            kaynak='rapor', grup=grup, sartli_atom=True)
    if op in ('<', '≤'):
        if egfr < esik:
            return SartSonuc(
                ad=f'eGFR ≥ {esik} (rapor: <{egfr})', durum=SartDurumu.YOK,
                neden=f'Rapor: eGFR<{egfr} < {esik} ({sinif or "SGLT-2"} sınırı)',
                kaynak='rapor', grup=grup)
        return SartSonuc(
            ad=f'eGFR ≥ {esik} (rapor: <{egfr})', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden=f'Rapor: eGFR<{egfr} — kesin değer bilinmiyor; manuel doğrula',
            kaynak='rapor', grup=grup, sartli_atom=True)
    if egfr >= esik:
        return SartSonuc(
            ad=f'eGFR ≥ {esik} (rapor: {egfr})', durum=SartDurumu.VAR,
            neden=f'eGFR={egfr} ≥ {esik} ({sinif or "SGLT-2"} sınırı)',
            kaynak='rapor', grup=grup)
    return SartSonuc(
        ad=f'eGFR ≥ {esik} (rapor: {egfr})', durum=SartDurumu.YOK,
        neden=f'eGFR={egfr} < {esik} ({sinif or "SGLT-2"} sınırı)',
        kaynak='rapor', grup=grup)


def atom_standart_ky_tedavi_kullaniyor(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Hasta standart KY tedavi 4'lüsünü kullanıyor mu?
       ((ACE-İ ∨ ARB) ∧ BB ∧ MRA)

    Karar S1=A: yerel ilaç DB'de bulamazsak KE (örtük kabul yasak).
    """
    if not _hasta_ilac_gecmisi_var_mi(ilac_sonuc):
        # Aktif reçetede yan kalemlerden bakalım
        ace_arb = (_diger_kalemler_iceriyor(ilac_sonuc, ACE_INHIBITOR)
                   or _diger_kalemler_iceriyor(ilac_sonuc, ARB_GRUBU))
        bb = _diger_kalemler_iceriyor(ilac_sonuc, BETA_BLOKOR)
        mra = _diger_kalemler_iceriyor(ilac_sonuc, MRA_ALDOSTERON_ANT)
        if ace_arb and bb and mra:
            return SartSonuc(
                ad='Standart KY tedavi (ACE/ARB+BB+MRA) — aktif reçete',
                durum=SartDurumu.VAR,
                neden='Aynı reçetede ACE/ARB + BB + MRA bulundu',
                kaynak='recete_ilaclari', grup=grup, veya_grubu=True)
        return SartSonuc(
            ad='Standart KY tedavi (ACE/ARB+BB+MRA)',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Hasta ilaç geçmişi verisi yok — başka eczane bilinmiyor (manuel doğrula)',
            kaynak='hasta_ilac_gecmisi', grup=grup, veya_grubu=True,
            sartli_atom=True)

    ace = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, ACE_INHIBITOR)
    arb = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, ARB_GRUBU)
    bb = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, BETA_BLOKOR)
    mra = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, MRA_ALDOSTERON_ANT)
    ace_arb = ace or arb
    if ace_arb and bb and mra:
        eksikler = []
        if not ace_arb:
            eksikler.append('ACE/ARB')
        if not bb:
            eksikler.append('BB')
        if not mra:
            eksikler.append('MRA')
        return SartSonuc(
            ad='Standart KY tedavi (ACE/ARB+BB+MRA)', durum=SartDurumu.VAR,
            neden='Hasta ilaç geçmişinde 3 sınıf da bulundu',
            kaynak='hasta_ilac_gecmisi', grup=grup, veya_grubu=True)
    eksikler = []
    if not ace_arb:
        eksikler.append('ACE/ARB')
    if not bb:
        eksikler.append('BB')
    if not mra:
        eksikler.append('MRA')
    return SartSonuc(
        ad='Standart KY tedavi (ACE/ARB+BB+MRA)',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden=f'Hasta ilaç geçmişinde eksik sınıf(lar): {", ".join(eksikler)} '
              '— başka eczanede kullanmış olabilir (manuel doğrula)',
        kaynak='hasta_ilac_gecmisi', grup=grup, veya_grubu=True,
        sartli_atom=True)


def atom_standart_ky_tedavi_rapor_lafzi(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Y_KY KY1c — Rapor lafzında "hasta ACE/ARB + BB + MRA tedavisi alıyor" var mı?

    Paralel-OR atomu (bkz. [[project-y3b-rapor-lafzi-paralel-atom]]):
      - DB tarafı (atom_standart_ky_tedavi_kullaniyor) eksik kalsa bile
        rapor doktoru lafzen "hasta ACE/ARB+BB+MRA tedavisi alıyor" demişse
        KY1 grubu VAR sayılır.
      - Kanıt akışı: rapor lafzı tek başına yeterli (S1=A geçici kabul).
      - Lafız geçmiyorsa KE (sessiz=KE, örtük kabul yasak).

    Yakalanan kalıplar:
      - "ace inhibitörü /arb +beta bloker +mra tedavisi almaktadır"
      - "standart tedavi ... ace/arb, beta blokör, mra"
    """
    metin = _rapor_metni(ilac_sonuc)
    ace_arb = bool(re.search(
        r'(ace\s*inh|anjiyot|anjiot|\barb\b|arb[/\s,+])', metin))
    bb = bool(re.search(r'(beta\s*blok|beta-?blok|\bbb\b)', metin))
    mra = bool(re.search(
        r'(\bmra\b|aldosteron|spironolakton|eplerenon)', metin))
    kullanim = bool(re.search(
        r'(almakta|aliyor|kullaniyor|kullanmakta|standart\s*tedavi|tedavisi)',
        metin))
    if ace_arb and bb and mra and kullanim:
        return SartSonuc(
            ad='Standart KY tedavi — rapor lafzı (ACE/ARB+BB+MRA)',
            durum=SartDurumu.VAR,
            neden='Rapor lafzı: "hasta ACE/ARB + BB + MRA tedavisi alıyor"',
            kaynak='rapor', grup=grup, veya_grubu=True)
    eksikler = []
    if not ace_arb:
        eksikler.append('ACE/ARB lafzı')
    if not bb:
        eksikler.append('BB lafzı')
    if not mra:
        eksikler.append('MRA lafzı')
    if not kullanim:
        eksikler.append('kullanım fiili')
    return SartSonuc(
        ad='Standart KY tedavi — rapor lafzı (ACE/ARB+BB+MRA)',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden=f'Rapor lafzında eksik ibareler: {", ".join(eksikler)}',
        kaynak='rapor', grup=grup, veya_grubu=True, sartli_atom=True)


def atom_ky_kullanilamama_gerekce(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """KY tedavi sınıflarından birinin/birkaçının kullanılamama gerekçesi raporda mı?

    Lafız örneği: "ACE inhibitörü öksürük nedeniyle kullanılamadı",
    "beta blokör astım nedeniyle kontrendike", vs.
    """
    metin = _rapor_metni(ilac_sonuc)
    pat = re.compile(
        r'(?:ace|arb|anjiyotensin|beta\s*blok|aldosteron|mra|spironolakton|eplerenon)'
        r'.{0,80}?(?:kullan[ıi]lam|kontrendike|intolerans|tolere\s*ed[ie]me|'
        r'yan\s*etki|alerji|geri\s*[çc]ekil)',
        re.IGNORECASE | re.DOTALL)
    if pat.search(metin):
        return SartSonuc(
            ad='Kullanılamama gerekçesi raporda', durum=SartDurumu.VAR,
            neden='Rapor lafzı: KY tedavi sınıfı için kullanılamama/kontrendikasyon gerekçesi',
            kaynak='rapor', grup=grup, veya_grubu=True)
    return SartSonuc(
        ad='Kullanılamama gerekçesi raporda',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Rapor metninde kullanılamama gerekçesi bulunamadı (alternatif)',
        kaynak='rapor', grup=grup, veya_grubu=True, sartli_atom=True)


def _brans_heyette(ilac_sonuc: Dict, hedef_brans: str) -> Optional[bool]:
    """Heyet doktorlarında belirli branştan uzman VAR mı?
       hedef_brans normalize edilmiş key (örn. 'kardiyo', 'nefroloji', 'endokrin').
       True = VAR, False = YOK, None = veri yok.
    """
    heyet = ilac_sonuc.get('heyet_doktorlari') or []
    if not heyet:
        return None
    for d in heyet:
        if isinstance(d, dict):
            brans = (d.get('brans') or d.get('uzmanlik')
                     or d.get('doktor_uzmanligi') or '')
        else:
            brans = str(d)
        brans_norm = _brans_norm(brans)
        # Ham stringde DE ara: "İç Hastalıkları -> Nefroloji" gibi ana dal +
        # yan dal birleşik yazımlarda _brans_norm 'ic'ye indirger ve yan dal
        # bilgisi kaybolur → nefrolog heyette olduğu halde YOK üretilirdi
        # (ADEM ERASLAN 3O68UR0 / JARDIANCE pilotu 2026-07-06).
        ham = _ascii_normalize(brans)
        if hedef_brans == 'kardiyo' and (brans_norm == 'kardiyo'
                                         or 'kardiyoloji' in ham):
            return True
        if hedef_brans == 'nefroloji' and ('nefro' in brans_norm
                                           or 'nefro' in ham):
            return True
        if hedef_brans == 'endokrin' and (brans_norm == 'endokrin'
                                          or 'endokrin' in ham):
            return True
        if hedef_brans == 'ic' and (brans_norm == 'ic'
                                    or 'ic hastalik' in ham
                                    or 'dahiliye' in ham):
            return True
    return False


def atom_heyet_kardiyolog(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Heyette en az 1 kardiyoloji uzmanı VAR mı?"""
    sonuc = _brans_heyette(ilac_sonuc, 'kardiyo')
    if sonuc is None:
        return SartSonuc(
            ad='Heyette ≥1 kardiyoloji uzmanı',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Heyet doktor listesi alınamadı', kaynak='rapor_heyet',
            grup=grup, sartli_atom=True)
    if sonuc:
        return SartSonuc(
            ad='Heyette ≥1 kardiyoloji uzmanı', durum=SartDurumu.VAR,
            neden='Heyette kardiyoloji uzmanı bulundu',
            kaynak='rapor_heyet', grup=grup)
    return SartSonuc(
        ad='Heyette ≥1 kardiyoloji uzmanı', durum=SartDurumu.YOK,
        neden='Heyette kardiyoloji uzmanı YOK — 4.2.74-1 zorunlu şart',
        kaynak='rapor_heyet', grup=grup)


def atom_heyet_nefrolog(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Heyette en az 1 nefroloji uzmanı VAR mı?"""
    sonuc = _brans_heyette(ilac_sonuc, 'nefroloji')
    if sonuc is None:
        return SartSonuc(
            ad='Heyette ≥1 nefroloji uzmanı',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Heyet doktor listesi alınamadı', kaynak='rapor_heyet',
            grup=grup, sartli_atom=True)
    if sonuc:
        return SartSonuc(
            ad='Heyette ≥1 nefroloji uzmanı', durum=SartDurumu.VAR,
            neden='Heyette nefroloji uzmanı bulundu',
            kaynak='rapor_heyet', grup=grup)
    return SartSonuc(
        ad='Heyette ≥1 nefroloji uzmanı', durum=SartDurumu.YOK,
        neden='Heyette nefroloji uzmanı YOK — 4.2.74-2 zorunlu şart',
        kaynak='rapor_heyet', grup=grup)


def atom_heyet_endokrinolog(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Heyette en az 1 endokrinoloji uzmanı VAR mı? (Y3b için)."""
    sonuc = _brans_heyette(ilac_sonuc, 'endokrin')
    if sonuc is None:
        return SartSonuc(
            ad='Heyette ≥1 endokrinoloji uzmanı',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Heyet doktor listesi alınamadı', kaynak='rapor_heyet',
            grup=grup, sartli_atom=True)
    if sonuc:
        return SartSonuc(
            ad='Heyette ≥1 endokrinoloji uzmanı', durum=SartDurumu.VAR,
            neden='Heyette endokrinoloji uzmanı bulundu',
            kaynak='rapor_heyet', grup=grup)
    return SartSonuc(
        ad='Heyette ≥1 endokrinoloji uzmanı', durum=SartDurumu.YOK,
        neden='Heyette endokrinoloji uzmanı YOK',
        kaynak='rapor_heyet', grup=grup)


def atom_heyet_ih(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Heyette en az 1 iç hastalıkları uzmanı VAR mı? (Y3b 24 ay sonrası için)."""
    sonuc = _brans_heyette(ilac_sonuc, 'ic')
    if sonuc is None:
        return SartSonuc(
            ad='Heyette ≥1 iç hastalıkları uzmanı',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Heyet doktor listesi alınamadı', kaynak='rapor_heyet',
            grup=grup, sartli_atom=True)
    if sonuc:
        return SartSonuc(
            ad='Heyette ≥1 iç hastalıkları uzmanı', durum=SartDurumu.VAR,
            neden='Heyette IH uzmanı bulundu',
            kaynak='rapor_heyet', grup=grup)
    return SartSonuc(
        ad='Heyette ≥1 iç hastalıkları uzmanı', durum=SartDurumu.YOK,
        neden='Heyette IH uzmanı YOK',
        kaynak='rapor_heyet', grup=grup)


# ────────────────────────────────────────────────────────────────────────
# Y_KBH: KBH var / RAAS-İ / persistan proteinüri / ACR-PCR
# ────────────────────────────────────────────────────────────────────────

def atom_kbh_var(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """KBH endikasyonu: ICD N18.x VEYA rapor metni."""
    teshisler = ilac_sonuc.get('recete_teshisleri') or []
    teshis_str = norm_tr_upper(' '.join(teshisler))
    if re.search(r'\bN18(\.\d+)?\b', teshis_str):
        return SartSonuc(
            ad='KBH endikasyonu', durum=SartDurumu.VAR,
            neden='ICD N18.x bulundu', kaynak='teshis', grup=grup)
    metin = _rapor_metni(ilac_sonuc)
    if re.search(
            r'(kronik\s*b[oö]brek\s*hastal[ıi]g|kby|kbh|chronic\s*kidney)',
            metin):
        return SartSonuc(
            ad='KBH endikasyonu', durum=SartDurumu.VAR,
            neden='Rapor lafzı: kronik böbrek hastalığı', kaynak='rapor',
            grup=grup)
    return SartSonuc(
        ad='KBH endikasyonu', durum=SartDurumu.YOK,
        neden='ICD N18.x ve rapor lafzı bulunamadı', kaynak='teshis+rapor',
        grup=grup)


def atom_raas_kullaniyor(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """RAAS-İ (ACE-İ veya ARB) kullanıyor mu?"""
    # Aktif reçete diğer kalemleri
    aktif = (_diger_kalemler_iceriyor(ilac_sonuc, ACE_INHIBITOR)
             or _diger_kalemler_iceriyor(ilac_sonuc, ARB_GRUBU))
    if aktif:
        return SartSonuc(
            ad='RAAS-İ kullanıyor (ACE-İ veya ARB)', durum=SartDurumu.VAR,
            neden='Aynı reçetede ACE-İ veya ARB bulundu',
            kaynak='recete_ilaclari', grup=grup)
    # Hasta ilaç geçmişi
    if _hasta_ilac_gecmisi_var_mi(ilac_sonuc):
        gecmis = (_hasta_ilac_gecmisi_iceriyor(ilac_sonuc, ACE_INHIBITOR)
                  or _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, ARB_GRUBU))
        if gecmis:
            return SartSonuc(
                ad='RAAS-İ kullanıyor (ACE-İ veya ARB)', durum=SartDurumu.VAR,
                neden='Hasta ilaç geçmişinde ACE-İ/ARB bulundu',
                kaynak='hasta_ilac_gecmisi', grup=grup)
    # Rapor metni
    metin = _rapor_metni(ilac_sonuc)
    if re.search(
            r'(raas|renin\s*anjiyotensin|ace\s*inhibit|arb|anjiyotensin\s*resept)',
            metin):
        return SartSonuc(
            ad='RAAS-İ kullanıyor', durum=SartDurumu.VAR,
            neden='Rapor lafzı: RAAS-İ / ACE / ARB ibaresi',
            kaynak='rapor', grup=grup)
    return SartSonuc(
        ad='RAAS-İ kullanıyor (ACE-İ veya ARB)',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Yerel DB ve rapor sessiz — başka eczane bilinmiyor (manuel doğrula)',
        kaynak='hasta_ilac+recete+rapor', grup=grup, sartli_atom=True)


def atom_proteinuri_persistan_3ay(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Persistan proteinüri ≥ 3 ay (rapor lafzı)."""
    metin = _rapor_metni(ilac_sonuc)
    pat = re.compile(
        r'(persistan\s*proteinuri|persistan.{0,20}proteinuri|'
        r'3\s*ay.{0,30}proteinuri|proteinuri.{0,30}3\s*ay)',
        re.IGNORECASE)
    if pat.search(metin):
        return SartSonuc(
            ad='Persistan proteinüri ≥ 3 ay', durum=SartDurumu.VAR,
            neden='Rapor lafzı: persistan proteinüri (≥3 ay)',
            kaynak='rapor', grup=grup)
    return SartSonuc(
        ad='Persistan proteinüri ≥ 3 ay',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Rapor metninde "persistan proteinüri ≥ 3 ay" lafzı bulunamadı',
        kaynak='rapor', grup=grup, sartli_atom=True)


def atom_acr_uygun(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """ACR (Albumin/Kreatinin) ≥ 200 mg/g."""
    metin = _rapor_metni(ilac_sonuc)
    pat = re.compile(r'acr\s*[:=≥>]?\s*(\d+(?:[.,]\d+)?)', re.IGNORECASE)
    m = pat.search(metin)
    if not m:
        return SartSonuc(
            ad='ACR ≥ 200 mg/g', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Rapor metninde ACR değeri bulunamadı',
            kaynak='rapor', grup=grup, veya_grubu=True, sartli_atom=True)
    try:
        acr = float(m.group(1).replace(',', '.'))
    except ValueError:
        return SartSonuc(
            ad='ACR ≥ 200 mg/g', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='ACR değeri parse edilemedi', kaynak='rapor', grup=grup,
            veya_grubu=True, sartli_atom=True)
    if acr >= 200:
        return SartSonuc(
            ad=f'ACR ≥ 200 mg/g (rapor: {acr:g})', durum=SartDurumu.VAR,
            neden=f'ACR={acr:g} ≥ 200 mg/g',
            kaynak='rapor', grup=grup, veya_grubu=True)
    return SartSonuc(
        ad=f'ACR ≥ 200 mg/g (rapor: {acr:g})', durum=SartDurumu.YOK,
        neden=f'ACR={acr:g} < 200 mg/g',
        kaynak='rapor', grup=grup, veya_grubu=True)


def atom_pcr_uygun(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """PCR (Protein/Kreatinin) > 300 mg/g."""
    metin = _rapor_metni(ilac_sonuc)
    pat = re.compile(r'pcr\s*[:=≥>]?\s*(\d+(?:[.,]\d+)?)', re.IGNORECASE)
    m = pat.search(metin)
    if not m:
        return SartSonuc(
            ad='PCR > 300 mg/g', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Rapor metninde PCR değeri bulunamadı',
            kaynak='rapor', grup=grup, veya_grubu=True, sartli_atom=True)
    try:
        pcr = float(m.group(1).replace(',', '.'))
    except ValueError:
        return SartSonuc(
            ad='PCR > 300 mg/g', durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='PCR değeri parse edilemedi', kaynak='rapor', grup=grup,
            veya_grubu=True, sartli_atom=True)
    if pcr > 300:
        return SartSonuc(
            ad=f'PCR > 300 mg/g (rapor: {pcr:g})', durum=SartDurumu.VAR,
            neden=f'PCR={pcr:g} > 300 mg/g',
            kaynak='rapor', grup=grup, veya_grubu=True)
    return SartSonuc(
        ad=f'PCR > 300 mg/g (rapor: {pcr:g})', durum=SartDurumu.YOK,
        neden=f'PCR={pcr:g} ≤ 300 mg/g',
        kaynak='rapor', grup=grup, veya_grubu=True)


# ────────────────────────────────────────────────────────────────────────
# Y3b: önceden insülin kullanım / labil-hipo-regülasyon / 24 ay dispatcher
# ────────────────────────────────────────────────────────────────────────

def atom_rapor_lafzi_onceden_insulin_y3b(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Y3b.1a — Rapor açıklamasında 'analog karışım / uzun etkili insülin /
    bazal insülin' kullanım ibaresi VAR mı?

    SUT 4.2.38(3)(b) atomu: "analog karışım veya uzun etkili insülinlerden
    birini kullanmış olmasına rağmen ..." şartının **rapor lafzı kanıtı**.
    `atom_onceden_kullanilmis_insulin_y3b` (hasta geçmişi kanıtı) ile VEYA-bağlı.
    """
    # _rapor_metni norm_tr_lower yapıyor — TR karakter ve combining-dot temizlendi
    metin = _rapor_metni(ilac_sonuc)
    patternler = [
        ('analog karışım',
         r'analog\s*kar[ıi][şs][ıi]m'),
        ('uzun etkili insülin',
         r'uzun\s*etkili\s*ins[üu]?l[üu]?in'),
        ('bazal insülin',
         r'ba[sz]al\s*ins[üu]?l[üu]?in'),
        ('analog uzun etkili',
         r'analog\s*uzun\s*etkili'),
    ]
    for ibare, pat in patternler:
        if re.search(pat, metin, re.IGNORECASE):
            return SartSonuc(
                ad='Rapor lafzında önceden insülin kullanım ibaresi',
                durum=SartDurumu.VAR,
                neden=f'Rapor açıklamasında "{ibare}" lafzı bulundu',
                kaynak='rapor', grup=grup, veya_grubu=True)
    return SartSonuc(
        ad='Rapor lafzında önceden insülin kullanım ibaresi',
        durum=SartDurumu.YOK,
        neden='Rapor lafzında analog karışım / uzun etkili / bazal insülin '
              'ibaresi bulunamadı',
        kaynak='rapor', grup=grup, veya_grubu=True)


def atom_onceden_kullanilmis_insulin_y3b(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Y3b.1b — Hasta ilaç geçmişinde analog karışım / uzun etkili / NPH bazal
    insülin VAR mı?

    `atom_rapor_lafzi_onceden_insulin_y3b` (rapor lafzı kanıtı) ile
    VEYA-bağlı (≥1 yeterli). NPH (insan orta etkili) kullanıcı kararı ile
    geniş yorumda dahil (2026-05-24)."""
    ad = 'Hasta geçmişinde analog karışım / uzun etkili / NPH insülin'
    if not _hasta_ilac_gecmisi_var_mi(ilac_sonuc):
        # Aktif reçetede diğer kalem var mı?
        aktif = (_diger_kalemler_iceriyor(ilac_sonuc, ANALOG_KARISIM_INSULIN)
                 or _diger_kalemler_iceriyor(ilac_sonuc, ANALOG_UZUN_ETKILI_INSULIN)
                 or _diger_kalemler_iceriyor(ilac_sonuc, NPH_INSAN_BAZAL_INSULIN))
        if aktif:
            return SartSonuc(
                ad=ad, durum=SartDurumu.VAR,
                neden='Aynı reçetede analog karışım/uzun etkili/NPH insülin bulundu',
                kaynak='recete_ilaclari', grup=grup, veya_grubu=True)
        return SartSonuc(
            ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Hasta ilaç geçmişi verisi yok — başka eczane bilinmiyor',
            kaynak='hasta_ilac_gecmisi', grup=grup,
            veya_grubu=True, sartli_atom=True)
    karisim = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, ANALOG_KARISIM_INSULIN)
    uzun = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, ANALOG_UZUN_ETKILI_INSULIN)
    nph = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, NPH_INSAN_BAZAL_INSULIN)
    if karisim or uzun or nph:
        if karisim:
            bulgu = 'analog karışım'
        elif uzun:
            bulgu = 'uzun etkili (analog bazal)'
        else:
            bulgu = 'NPH (insan bazal — geniş yorum)'
        return SartSonuc(
            ad=ad, durum=SartDurumu.VAR,
            neden=f'Hasta geçmişinde {bulgu} insülin bulundu',
            kaynak='hasta_ilac_gecmisi', grup=grup, veya_grubu=True)
    return SartSonuc(
        ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Hasta yerel ilaç geçmişinde insülin yok — başka eczane bilinmiyor',
        kaynak='hasta_ilac_gecmisi', grup=grup,
        veya_grubu=True, sartli_atom=True)


def atom_labil_hipo_regulasyon(ilac_sonuc: Dict, grup: str) -> List[SartSonuc]:
    """Y3b OR-grubu: labil ∨ sık hipo ∨ hipo riski ∨ regülasyon yok.

    4 alt atomu OR grubunda döndürür (≥1 yeterli).
    """
    metin = _rapor_metni(ilac_sonuc)
    secenekler = [
        ('Kan şekeri labil seyrediyor',
         r'(labil|de[ğg]i[şs]ken|stabil\s*degil|stabilite\s*yok)'),
        ('Sık hipoglisemik olay',
         r's[ıi]k.{0,15}hipogli?sem|hipogli?sem.{0,15}s[ıi]k'),
        ('Hipoglisemi riski yüksek',
         # "hipoglisemi riski yüksek/mevcut/var" + "yüksek hipoglisemi"
         # + "nokturnal hipoglisemi" (gece hipoglisemi → risk göstergesi)
         # + "gece hipoglisemi" (Türkçe karşılığı, kullanıcı onayı 2026-05-24
         #   MEHMET SAHİL ÖZDEMİR vakası — SUT'taki gece hipoglisemi geçirenler
         #   kuralı için medikal eşdeğer)
         r'hipogli?sem.{0,20}risk.{0,20}(?:y[uü]ks|mevcut|var\b)|'
         r'y[uü]ksek\s*hipogli?sem|'
         r'(?:nokt[uü]rnal|gece)\s*hipogli?sem|'
         r'hipogli?sem.{0,15}(?:nokt[uü]rnal|gece)'),
        ('Regülasyon sağlanamadı',
         r'reg[uü]lasyon.{0,15}(?:sa[gğ]lanam|yok|kayb)'),
    ]
    sartlar: List[SartSonuc] = []
    for ad, pat in secenekler:
        if re.search(pat, metin, re.IGNORECASE):
            sartlar.append(SartSonuc(
                ad=ad, durum=SartDurumu.VAR,
                neden='Rapor lafzında bulundu', kaynak='rapor', grup=grup,
                veya_grubu=True))
            continue
        # B1 özel: "stabil seyrediyor" SUT şartının ZIDDI — kırmızı bayrak
        if (ad == 'Kan şekeri labil seyrediyor'
                and re.search(r'(?:kan\s*[şs]ekeri\s*)?stabil\s*seyred',
                              metin, re.IGNORECASE)):
            sartlar.append(SartSonuc(
                ad=ad, durum=SartDurumu.YOK,
                neden='⚠ Rapor "stabil seyrediyor" diyor — SUT "labil" istiyor; '
                      'rapor lafzı şartın ZIDDI, manuel doğrula',
                kaynak='rapor', grup=grup,
                veya_grubu=True, sartli_atom=True))
            continue
        # B2 yumuşak yorum: "gece/nokturnal/tekrarlayan hipoglisemi olay"
        # — "sık" lafzı yok ama sıklığa atıf var → KE (manuel teyit)
        if (ad == 'Sık hipoglisemik olay'
                and re.search(
                    r'(?:gece|nokt[uü]rnal|tekrarlayan|ardarda)\s*hipogli?sem|'
                    r'hipogli?sem.{0,20}(?:gece|nokt[uü]rnal|tekrarlayan)',
                    metin, re.IGNORECASE)):
            sartlar.append(SartSonuc(
                ad=ad, durum=SartDurumu.KONTROL_EDILEMEDI,
                neden='Rapor "gece/nokturnal/tekrarlayan hipoglisemi" diyor — '
                      '"sık" lafzı yok ama sıklık sinyali var, manuel doğrula',
                kaynak='rapor', grup=grup,
                veya_grubu=True, sartli_atom=True))
            continue
        sartlar.append(SartSonuc(
            ad=ad, durum=SartDurumu.YOK,
            neden='Rapor lafzında bulunamadı', kaynak='rapor', grup=grup,
            veya_grubu=True))
    return sartlar


def _parse_tarih_str(s) -> Optional["date"]:  # type: ignore[name-defined]
    """'dd/mm/yyyy' / 'dd.mm.yyyy' / 'dd-mm-yyyy' string → date, hatada None."""
    if not s:
        return None
    from datetime import date
    m = re.match(r'(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})', str(s).strip())
    if not m:
        return None
    try:
        gun, ay, yil = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yil < 100:
            yil += 2000
        return date(yil, ay, gun)
    except (ValueError, OverflowError):
        return None


def atom_24_ay_sonra_mi_y3b(ilac_sonuc: Dict) -> Optional[bool]:
    """Y3b dispatcher: ilk rapordan 24 ay geçti mi?

    S2=C kararı: aktif rapor metninde "ilk rapor tarihi DD/MM/YYYY" lafzı varsa
    hesapla; yoksa None (→ atom seviyesinde KE).

    Referans tarih (kontrol anı):
      1. reçete tarihi — öncelikli (kontrol bu reçete için yapılıyor)
      2. rapor tarihi — fallback
      3. bugün — son çare (eski reçete kontrolünde zaman kayması riski)

    Dönüş: True (24+ ay geçti), False (henüz geçmedi), None (bilinmiyor).
    """
    metin = _rapor_metni(ilac_sonuc)
    # "ilk rapor tarihi 02.05.2023", "ilk rapor 5/4/2024"
    pat = re.compile(
        r'ilk\s*rapor.{0,30}?(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})',
        re.IGNORECASE)
    m = pat.search(metin)
    if not m:
        return None
    try:
        from datetime import date
        gun, ay, yil = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if yil < 100:
            yil += 2000
        ilk_rapor = date(yil, ay, gun)
        ref = (_parse_tarih_str(ilac_sonuc.get('recete_tarihi'))
               or _parse_tarih_str(ilac_sonuc.get('rapor_tarihi'))
               or date.today())
        ay_fark = (ref.year - ilk_rapor.year) * 12 + (ref.month - ilk_rapor.month)
        return ay_fark >= 24
    except (ValueError, ImportError):
        return None


# ────────────────────────────────────────────────────────────────────────
# Y8: önceden Met+Sulfo + Empa/Lina kullanım
# ────────────────────────────────────────────────────────────────────────

def atom_onceden_met_veya_sulfo_y8(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Hasta önceden Met VE/VEYA Sulfo kullanmış mı? (Y8.1)"""
    if not _hasta_ilac_gecmisi_var_mi(ilac_sonuc):
        return SartSonuc(
            ad='Önceden Metformin VE/VEYA Sülfonilüre kullanmış',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Hasta ilaç geçmişi verisi yok — başka eczane bilinmiyor',
            kaynak='hasta_ilac_gecmisi', grup=grup, sartli_atom=True)
    met = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, METFORMIN)
    sulfo = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, SULFONILURE)
    if met or sulfo:
        return SartSonuc(
            ad='Önceden Metformin VE/VEYA Sülfonilüre kullanmış',
            durum=SartDurumu.VAR,
            neden=f'Hasta geçmişinde {"metformin" if met else "sülfonilüre"} bulundu',
            kaynak='hasta_ilac_gecmisi', grup=grup)
    return SartSonuc(
        ad='Önceden Metformin VE/VEYA Sülfonilüre kullanmış',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Yerel ilaç geçmişinde Met/Sulfo yok — başka eczane bilinmiyor',
        kaynak='hasta_ilac_gecmisi', grup=grup, sartli_atom=True)


def atom_onceden_empa_veya_lina_y8(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Hasta önceden Empa VEYA Lina'dan birini kullanmış mı? (Y8.2)"""
    if not _hasta_ilac_gecmisi_var_mi(ilac_sonuc):
        return SartSonuc(
            ad='Önceden Empagliflozin VEYA Linagliptin kullanmış',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Hasta ilaç geçmişi verisi yok — başka eczane bilinmiyor',
            kaynak='hasta_ilac_gecmisi', grup=grup, sartli_atom=True)
    empa = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc,
                                         {'EMPAGLIFLOZIN', 'JARDIANCE', 'SYNJARDY'})
    lina = _hasta_ilac_gecmisi_iceriyor(ilac_sonuc,
                                         {'LINAGLIPTIN', 'TRAJENTA', 'JENTADUETO'})
    if empa or lina:
        return SartSonuc(
            ad='Önceden Empagliflozin VEYA Linagliptin kullanmış',
            durum=SartDurumu.VAR,
            neden=f'Hasta geçmişinde {"empa" if empa else "lina"} bulundu',
            kaynak='hasta_ilac_gecmisi', grup=grup)
    return SartSonuc(
        ad='Önceden Empagliflozin VEYA Linagliptin kullanmış',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Yerel ilaç geçmişinde empa/lina yok — başka eczane bilinmiyor',
        kaynak='hasta_ilac_gecmisi', grup=grup, sartli_atom=True)


# ────────────────────────────────────────────────────────────────────────
# Y5/Y7/Y8 paylaşımlı: yetersiz glisemik kontrol
# ────────────────────────────────────────────────────────────────────────

def atom_yetersiz_glisemik_kontrol(ilac_sonuc: Dict, grup: str) -> SartSonuc:
    """Yetersiz glisemik kontrol (Y7/Y8 için tek atom; Y5 için 4a/4b'nin alt
       atomu olarak da kullanılabilir).
    """
    metin = _rapor_metni(ilac_sonuc)
    pat = re.compile(
        r'(?:yeterli\s*(?:glisemik\s*)?kontrol\s*sa[gğ]lanam|'
        r'yetersiz\s*(?:glisemik\s*)?kontrol|'
        r'kontrol\s*sa[gğ]lanama|glisemik\s*regulasyon\s*sa[gğ]lanam)',
        re.IGNORECASE)
    if pat.search(metin):
        return SartSonuc(
            ad='Yetersiz glisemik kontrol', durum=SartDurumu.VAR,
            neden='Rapor lafzı: yetersiz/sağlanamayan kontrol',
            kaynak='rapor', grup=grup)
    return SartSonuc(
        ad='Yetersiz glisemik kontrol',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Rapor metninde yetersiz kontrol ibaresi bulunamadı',
        kaynak='rapor', grup=grup, sartli_atom=True)


# ════════════════════════════════════════════════════════════════════════
# YOLAK Y9 — Kapsam dışı GLP-1 (lira/sema/dula/tirze)
# ════════════════════════════════════════════════════════════════════════

def y9_kapsam_disi_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y9: SUT 4.2.38 kapsamı dışı GLP-1 analoğu.

    Liraglutid, semaglutid, dulaglutid, tirzepatid SUT 4.2.38'de düzenlenmemiş.
    SGK ödeme yapmaz → her zaman UYGUN_DEĞİL.
    """
    return [
        SartSonuc(
            ad='SUT 4.2.38 kapsamı',
            durum=SartDurumu.YOK,
            neden='Bu GLP-1 analoğu SUT 4.2.38 kapsamında değil — SGK ödeme yapmaz',
            kaynak='ilac_sinifi',
            grup='Kapsam',
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y3 — Analog insülin / Pioglitazon (Fıkra 3) — TODO
# ═══════════════════════════════════════════════════════════════════════

Y3_IZINLI = {'endokrin', 'ic', 'pediatri', 'kardiyo'}  # Aile hek YOK!


def y3_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y3: Analog insülin / Pioglitazon / Pio kombi.

    PARALEL-YOL kalıbı (üst-VEYA çifti, Y2'den tek farkı Aile hek yok).
    """
    sartlar: List[SartSonuc] = []
    grup_raporsuz = '‖Y3‖ Raporsuz Yol — Hekim Endo/IH/Pediatri/Kardio'
    grup_raporlu = '‖Y3‖ Raporlu Yol — Rapor Endo/IH/Pediatri/Kardio'
    hekim_atomu = atom_hekim_brans_uygun(ilac_sonuc, Y3_IZINLI, grup=grup_raporsuz)
    hekim_atomu.veya_grubu = False
    sartlar.append(hekim_atomu)
    rapor_atomu = atom_uzman_raporu_brans(ilac_sonuc, Y3_IZINLI, grup=grup_raporlu)
    rapor_atomu.veya_grubu = False
    sartlar.append(rapor_atomu)
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y4 — DPP-4 antagonistleri (Fıkra 4) — kısmî
# ═══════════════════════════════════════════════════════════════════════

Y4_IZINLI = {'endokrin', 'ic'}


def atom_dpp4_dusuk_doz_kby(ilac_sonuc: Dict,
                              grup: str = 'Fıkra (4) — düşük doz formu') -> Optional[SartSonuc]:
    """Saksagliptin 2.5mg / Alogliptin 12.5mg → sadece KBY hastalarda.

    Diğer formlar için NA (None) döner.
    """
    arama = _arama_metni(ilac_sonuc)
    pat_saksa = re.compile(r'(?:saksagliptin|onglyza)[^a-z0-9]{0,30}2[.,]5\s*mg',
                            re.IGNORECASE)
    pat_alo = re.compile(r'(?:alogliptin|nesina)[^a-z0-9]{0,30}12[.,]5\s*mg',
                          re.IGNORECASE)
    if not (pat_saksa.search(arama) or pat_alo.search(arama)):
        return None  # NA — bu form değil

    # KBY tespiti: ICD N18.x + rapor metni
    teshisler = ilac_sonuc.get('recete_teshisleri') or []
    teshis_str = norm_tr_upper(' '.join(teshisler)) if teshisler else ''
    icd_kby = bool(re.search(r'\bN18\.?\d?\b', teshis_str))
    metin = norm_tr_lower(ilac_sonuc.get('rapor_metni') or '')
    metin_kby = bool(re.search(
        r'(?:kby|kronik\s*b[oö]brek\s*yetmezli[gğ]i|diyaliz|hemodiyaliz)', metin))

    if icd_kby or metin_kby:
        return SartSonuc(
            ad='Düşük doz formu (saksa 2.5mg / alo 12.5mg) — KBY',
            durum=SartDurumu.VAR,
            neden='KBY teşhisi (ICD N18.x) veya rapor lafzı bulundu',
            kaynak='teshis+rapor',
            grup=grup,
        )
    return SartSonuc(
        ad='Düşük doz formu (saksa 2.5mg / alo 12.5mg) — KBY',
        durum=SartDurumu.YOK,
        neden='Bu doz formu sadece KBY hastalarında kullanılabilir; KBY teşhisi/lafzı yok',
        kaynak='teshis+rapor',
        grup=grup,
    )


def y4_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y4: DPP-4 antagonistleri + kombineleri.

    PARALEL-YOL kalıbı (2026-05-25, üst-VEYA çifti):
      Y4_UYGUN ⇔ [ Y4.2 ] ∨ [ Y4.3 ∧ Y4.1 ]
               ∧ (saksa2.5 → Y4.4) ∧ (alo12.5 → Y4.5) ∧ KY4.1
    """
    sartlar: List[SartSonuc] = []
    grup_raporsuz = '‖Y4‖ Raporsuz Yol — Hekim Endo/IH'
    grup_raporsuz_bilgi = '‖Y4‖ Raporsuz Yol — Klinik şart hekim sorumluluğu (bilgi)'
    grup_raporlu = '‖Y4‖ Raporlu Yol — Rapor Endo/IH + Klinik şart'

    # RAPORSUZ YOL
    hekim_atomu = atom_hekim_brans_uygun(
        ilac_sonuc, Y4_IZINLI, grup=grup_raporsuz)
    hekim_atomu.veya_grubu = False
    sartlar.append(hekim_atomu)
    sartlar.append(SartSonuc(
        ad='Klinik şart (Met/Sulfo max yetersiz) — raporsuz yolda hekim sorumluluğunda',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Endo/IH uzmanı raporsuz yazma yetkisine sahip; klinik şart '
              'hekim sorumluluğunda (eczacı/sistem doğrulayamaz)',
        kaynak='hekim_sorumluluk', grup=grup_raporsuz_bilgi,
        sartli_atom=True))

    # RAPORLU YOL
    rapor_atomu = atom_uzman_raporu_brans(
        ilac_sonuc, Y4_IZINLI, grup=grup_raporlu)
    rapor_atomu.veya_grubu = False
    sartlar.append(rapor_atomu)
    klinik_atomu = atom_metformin_sulfo_max_yetersiz(
        ilac_sonuc, grup=grup_raporlu)
    klinik_atomu.veya_grubu = False
    sartlar.append(klinik_atomu)

    # Saksa/Alo düşük doz şartı (paralel yol dışında, hep gerekli)
    dusuk_doz = atom_dpp4_dusuk_doz_kby(ilac_sonuc)
    if dusuk_doz is not None:
        sartlar.append(dusuk_doz)
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y3b — Degludek+Aspart / Ryzodeg (Fıkra 3-b)
# Formül: (Y3b.1a ∨ Y3b.1b) ∧ (Y3b.2a∨2b∨2c∨2d) ∧ Y3b.3 ∧ Y3b.6 ∧
#         ((¬Y3b.7 → Y3b.4) ∧ (Y3b.7 → (Y3b.4 ∨ Y3b.5)))
# Y3b.1a = rapor lafzı kanıtı, Y3b.1b = hasta geçmişi kanıtı (OR-bağlı)
# ═══════════════════════════════════════════════════════════════════════

Y3B_IZINLI = {'endokrin', 'ic'}


def y3b_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y3b: Degludek+Aspart kombi (Ryzodeg)."""
    sartlar: List[SartSonuc] = []
    grup_onceden = 'Fıkra (3b) — Önceden insülin kullanım (≥1)'
    grup_heyet = 'Fıkra (3b) — Heyet uzmanı'
    grup_yetki = 'Fıkra (3b) — Reçete hekimi yetkisi'

    # Y3b.1a + Y3b.1b — paralel OR atomları (rapor lafzı ∨ hasta geçmişi)
    sartlar.append(atom_rapor_lafzi_onceden_insulin_y3b(ilac_sonuc, grup_onceden))
    sartlar.append(atom_onceden_kullanilmis_insulin_y3b(ilac_sonuc, grup_onceden))
    # Y3b.2a-d klinik OR-grup
    sartlar.extend(atom_labil_hipo_regulasyon(
        ilac_sonuc, 'Fıkra (3b) — Klinik şart (≥1)'))
    # Y3b.3 SK raporu — heyet doktorlarının varlığı SK indikator
    if ilac_sonuc.get('heyet_doktorlari'):
        sartlar.append(SartSonuc(
            ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
            neden='Heyet doktorları listesi mevcut',
            kaynak='rapor_heyet', grup=grup_heyet))
    else:
        sartlar.append(SartSonuc(
            ad='Sağlık kurulu raporu',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Heyet listesi alınamadı — SK rapor varlığı doğrulanamadı',
            kaynak='rapor_heyet', grup=grup_heyet, sartli_atom=True))

    # Y3b.7 24 ay dispatcher (S2=C)
    sonra_mi = atom_24_ay_sonra_mi_y3b(ilac_sonuc)
    if sonra_mi is None:
        # KE — ilk varsay (en sıkı): endo zorunlu
        sartlar.append(SartSonuc(
            ad='İlk rapordan 24 ay geçti mi (dispatcher)',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='İlk rapor tarihi rapor metninde bulunamadı — manuel doğrula',
            kaynak='rapor', grup='Fıkra (3b) — Süre dispatcher (bilgi)',
            sartli_atom=True))
        # Endo zorunlu varsayımı (ilk rapor)
        sartlar.append(atom_heyet_endokrinolog(ilac_sonuc, grup_heyet))
    elif sonra_mi:
        # 24 ay sonrası: endo VEYA IH yeterli
        sartlar.append(SartSonuc(
            ad='İlk rapordan 24 ay geçti', durum=SartDurumu.VAR,
            neden='İlk rapor tarihi parse edildi (≥24 ay)',
            kaynak='rapor', grup='Fıkra (3b) — Süre dispatcher (bilgi)'))
        endo = atom_heyet_endokrinolog(ilac_sonuc, grup_heyet)
        ih = atom_heyet_ih(ilac_sonuc, grup_heyet)
        # OR grup için işaretle
        endo.veya_grubu = True
        ih.veya_grubu = True
        sartlar.append(endo)
        sartlar.append(ih)
    else:
        # İlk rapor: endo zorunlu
        sartlar.append(SartSonuc(
            ad='İlk rapor (24 aydan az)', durum=SartDurumu.VAR,
            neden='İlk rapordan henüz 24 ay geçmemiş',
            kaynak='rapor', grup='Fıkra (3b) — Süre dispatcher (bilgi)'))
        sartlar.append(atom_heyet_endokrinolog(ilac_sonuc, grup_heyet))

    # Y3b.6 reçete hekimi — SUT 4.2.38(3b) "sağlık kurulu raporuna dayanılarak
    # endokrinoloji veya iç hastalıkları uzman hekimlerince" diyor. SK raporu
    # zaten Y3b.3 + Y3b.4 (heyet endokrinolog) ile kontrol ediliyor. Ayrı bir
    # "uzman hekim raporu" şartı SUT lafzına aykırı — fazlalık. Yalnızca
    # reçeteyi yazan hekim branşı kontrol edilir.
    sartlar.append(atom_hekim_brans_uygun(ilac_sonuc, Y3B_IZINLI, grup=grup_yetki))

    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y5 — Eksenatid (Fıkra 5)
# Formül: Y5.1 ∧ Y5.2 ∧ Y5.3 ∧ (Y5.4a ∨ Y5.4b) ∧
#         ((Y5.5 → Y5.6) ∧ (¬Y5.5 → (Y5.7 ∧ Y5.8 ∧ Y5.9))) ∧ KY5.1 ∧ KY5.2
# (Y5.5/Y5.6/Y5.7/Y5.8 ilk-vs-devam dispatcher; ilk rapor varsa daha gevşek)
# ═══════════════════════════════════════════════════════════════════════

Y5_DEVAM_IZINLI = {'endokrin', 'ic'}
Y5_ILK_IZINLI = {'endokrin'}  # ilk reçete sadece endokrin uzmanı yazar (SUT 5/c)


def _y5_alt_dispatcher(ilac_sonuc: Dict) -> str:
    """Y5 alt-yolak: hasta_ilac_gecmisi'nde BYETTA/Eksenatid varsa devam, yoksa ilk reçete.

    Kullanıcı kuralı 2026-05-25: SUT 4.2.38(5)/c "başlangıç dozu rapor şartı
    aranmaksızın (2x5mcg) (1 kutu) olarak endokrinoloji uzman hekimlerince
    reçete edilir" — ilk reçete; "Tedaviye devam edilecekse... rapor..." — devam.
    """
    if _hasta_ilac_gecmisi_iceriyor(ilac_sonuc, GLP1_EKSENATID):
        return 'devam'
    return 'ilk'


def _y5_ortak_klinik_atomlari(ilac_sonuc: Dict,
                                 grup_klinik: str,
                                 grup_yolu: str) -> List[SartSonuc]:
    """Y5 ortak klinik şartlar — ilk ve devam yolu için aynı:
       Tip 2 DM + BMI>35 + Pankreatit yok + (Y5.4a ∨ Y5.4b)."""
    sartlar: List[SartSonuc] = []
    sartlar.append(atom_tip2_dm_var(ilac_sonuc, grup_klinik))
    sartlar.append(atom_bmi_35_ustu(ilac_sonuc, grup_klinik))
    sartlar.append(atom_akut_pankreatit_yok_neg(ilac_sonuc, grup_klinik))

    # Y5.4a/b — Met/Sulfo max yetersiz VEYA Met/Pio+bazal yetersiz
    sartlar.append(atom_metformin_sulfo_max_yetersiz(ilac_sonuc, grup=grup_yolu))
    metin = _rapor_metni(ilac_sonuc)
    if re.search(
            r'(?:pioglitazon|bazal\s*ins[uü]lin).{0,40}?(?:yetersiz|sa[gğ]lanam)',
            metin, re.IGNORECASE):
        sartlar.append(SartSonuc(
            ad='Met/Pio+bazal insülin yetersiz (b-yolu)',
            durum=SartDurumu.VAR,
            neden='Rapor lafzı: pio/bazal insülin yetersiz kontrol',
            kaynak='rapor', grup=grup_yolu, veya_grubu=True))
    else:
        sartlar.append(SartSonuc(
            ad='Met/Pio+bazal insülin yetersiz (b-yolu)',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Rapor metninde b-yolu klinik lafzı bulunamadı',
            kaynak='rapor', grup=grup_yolu, veya_grubu=True, sartli_atom=True))
    for s in sartlar:
        if s.grup == grup_yolu and 'Metformin/sülfonilüre max' in s.ad:
            s.veya_grubu = True
    return sartlar


def _y5_kombi_yasak_atomlari(ilac_sonuc: Dict,
                                grup_kombi: str) -> List[SartSonuc]:
    """KY5.1 DPP-4 yok + KY5.2 aktif tedavi sırasında pankreatit yok."""
    sartlar: List[SartSonuc] = []
    if _diger_kalemler_iceriyor(ilac_sonuc, DPP4):
        sartlar.append(SartSonuc(
            ad='Aynı reçetede DPP-4 YOK', durum=SartDurumu.YOK,
            neden='SUT 5(ç): Eksenatid + DPP-4 birlikte ödenmez',
            kaynak='recete_ilaclari', grup=grup_kombi))
    else:
        sartlar.append(SartSonuc(
            ad='Aynı reçetede DPP-4 YOK', durum=SartDurumu.VAR,
            neden='Reçete DPP-4 içermiyor',
            kaynak='recete_ilaclari', grup=grup_kombi))

    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'(?:tedavi.{0,15}pankreatit|pankreatit.{0,15}geli[şs])', metin):
        sartlar.append(SartSonuc(
            ad='Aktif tedavi sırasında pankreatit YOK', durum=SartDurumu.YOK,
            neden='Rapor: aktif tedavi sırasında pankreatit gelişimi',
            kaynak='rapor', grup=grup_kombi))
    else:
        sartlar.append(SartSonuc(
            ad='Aktif tedavi sırasında pankreatit YOK', durum=SartDurumu.VAR,
            neden='Rapor sessiz — pankreatit gelişim belirtilmemiş',
            kaynak='rapor', grup=grup_kombi))
    return sartlar


def _y5_ilk_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y5 İLK REÇETE — SUT 4.2.38(5)/c:
       "başlangıç dozu rapor şartı aranmaksızın (2x5mcg) (1 kutu) olarak
        endokrinoloji uzman hekimlerince reçete edilir."

    Yetki tek-atom: reçete hekimi endokrinoloji (iç hast DAHİL DEĞİL ilk reçetede).
    Rapor şartı YOK. 1 kutu sınırı kontrol edilemez (kutu sayısı motorda yok) →
    (bilgi) atomu olarak görünür, matematiğe katmaz.
    """
    sartlar: List[SartSonuc] = []
    grup_klinik = 'Fıkra (5/c) İlk Reçete —Klinik şart'
    grup_yolu = 'Fıkra (5/c) İlk Reçete —Tedavi yolu (a∨b)'
    grup_yetki = 'Fıkra (5/c) İlk Reçete —Hekim Endokrinoloji (rapor şartı yok)'
    grup_kutu_bilgi = 'Fıkra (5/c) İlk Reçete —1 kutu sınırı (bilgi)'
    grup_kombi = 'Fıkra (5)(ç) — Kombi yasağı'

    sartlar.extend(_y5_ortak_klinik_atomlari(ilac_sonuc, grup_klinik, grup_yolu))

    # Yetki: sadece endokrinoloji (iç hast değil)
    sartlar.append(atom_hekim_brans_uygun(
        ilac_sonuc, Y5_ILK_IZINLI, grup=grup_yetki))

    # 1 kutu sınırı — motor görünmüyor, bilgi atomu
    sartlar.append(SartSonuc(
        ad='İlk reçete: 1 kutu (2x5mcg) sınırı',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Kutu sayısı motora gelmiyor — manuel doğrulanmalı (bilgi)',
        kaynak='recete', grup=grup_kutu_bilgi, sartli_atom=True))

    sartlar.extend(_y5_kombi_yasak_atomlari(ilac_sonuc, grup_kombi))
    return sartlar


def _y5_devam_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y5 DEVAM REÇETE — 6 ay (ilk devam) veya 1 yıl (sonraki) endo
    uzman hekim raporuna dayanılarak endo/iç uzman hekimlerince yazılır."""
    sartlar: List[SartSonuc] = []
    grup_klinik = 'Fıkra (5) Devam Reçete —Klinik şart'
    grup_yolu = 'Fıkra (5) Devam Reçete —Tedavi yolu (a∨b)'
    grup_yetki = 'Fıkra (5) Devam Reçete —Hekim Endo/IH VEYA Rapor Endo/IH'
    grup_kombi = 'Fıkra (5)(ç) — Kombi yasağı'

    sartlar.extend(_y5_ortak_klinik_atomlari(ilac_sonuc, grup_klinik, grup_yolu))

    # Yetki: hekim Endo/IH VEYA rapor Endo/IH (paralel-yol yetki kalıbı)
    sartlar.append(atom_hekim_brans_uygun(
        ilac_sonuc, Y5_DEVAM_IZINLI, grup=grup_yetki))
    sartlar.append(atom_uzman_raporu_brans(
        ilac_sonuc, Y5_DEVAM_IZINLI, grup=grup_yetki))

    sartlar.extend(_y5_kombi_yasak_atomlari(ilac_sonuc, grup_kombi))
    return sartlar


def y5_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y5: Eksenatid (Byetta/Bydureon) — alt-dispatcher ile ilk vs devam.

    Mutually exclusive yapı (paralel-OR değil): hasta_ilac_gecmisi'nde
    BYETTA varsa devam yolu; yoksa ilk reçete yolu kontrol edilir. SUT
    4.2.38(5)/c lafzı ilk/devam ayrımını açıkça yapıyor (kullanıcı kuralı
    2026-05-25).
    """
    if _y5_alt_dispatcher(ilac_sonuc) == 'ilk':
        return _y5_ilk_kontrol(ilac_sonuc)
    return _y5_devam_kontrol(ilac_sonuc)


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y7 — Glarjin+Liksisenatid (Soliqua, Fıkra 7)
# Formül: Y7.1 ∧ Y7.2 ∧ Y7.3 ∧ Y7.4 ∧ Y7.5 ∧ Y7.6 ∧ Y7.7 ∧ KY7.1 ∧ KY7.2
# ═══════════════════════════════════════════════════════════════════════

Y7_IZINLI = {'endokrin', 'ic'}


def y7_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y7: Glarjin+Liksisenatid kombi (Soliqua)."""
    sartlar: List[SartSonuc] = []
    grup_hasta = 'Fıkra (7) — Hasta şartları'
    grup_klinik = 'Fıkra (7) — Klinik şart'
    grup_altyapi = 'Fıkra (7) — Altyapı (Met + diyet/egzersiz)'
    grup_yetki = 'Fıkra (7) — Reçete yetkisi'
    grup_kombi = 'Fıkra (7) — Kombi yasağı'

    # Y7.1 Tip 2 DM + yetişkin
    sartlar.append(atom_tip2_dm_var(ilac_sonuc, grup_hasta))
    sartlar.append(atom_yetiskin_18ust(ilac_sonuc, grup_hasta))
    # Y7.2 BMI > 35
    sartlar.append(atom_bmi_35_ustu(ilac_sonuc, grup_hasta))
    # Y7.3 Akut pankreatit YOK (NEG)
    sartlar.append(atom_akut_pankreatit_yok_neg(ilac_sonuc, grup_hasta))

    # Y7.4 Yetersiz glisemik kontrol
    sartlar.append(atom_yetersiz_glisemik_kontrol(ilac_sonuc, grup_klinik))

    # Y7.5 Met altyapısı + diyet/egzersiz
    metin = _rapor_metni(ilac_sonuc)
    met_var = (_hasta_ilac_gecmisi_iceriyor(ilac_sonuc, METFORMIN)
               or _diger_kalemler_iceriyor(ilac_sonuc, METFORMIN)
               or 'metformin' in metin)
    diyet = bool(re.search(r'diyet|egzersiz|ya[şs]am\s*tarz', metin))
    if met_var and diyet:
        sartlar.append(SartSonuc(
            ad='Metformin + diyet/egzersiz altyapısı', durum=SartDurumu.VAR,
            neden='Met kullanım + diyet/egzersiz rapor lafzı',
            kaynak='hasta_ilac+rapor', grup=grup_altyapi))
    elif met_var:
        sartlar.append(SartSonuc(
            ad='Metformin + diyet/egzersiz altyapısı',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Met var, ancak diyet/egzersiz lafzı raporda yok — bilgi',
            kaynak='rapor', grup=grup_altyapi, sartli_atom=True))
    else:
        sartlar.append(SartSonuc(
            ad='Metformin + diyet/egzersiz altyapısı',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Met kullanım kanıtı bulunamadı (başka eczane bilinmiyor)',
            kaynak='hasta_ilac+rapor', grup=grup_altyapi, sartli_atom=True))

    # Y7.6 1 yıl endo SK rapor → endo heyette + bilgi süre
    sartlar.append(atom_heyet_endokrinolog(ilac_sonuc, grup_yetki))
    sartlar.append(SartSonuc(
        ad='Rapor süresi 1 yıl', durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Süre kontrolü manuel — bilgi atom',
        kaynak='rapor', grup='Fıkra (7) — Rapor süresi (bilgi)',
        sartli_atom=True))

    # Y7.7 Reçete hekimi ∈ {Endo, IH}
    sartlar.append(atom_hekim_brans_uygun(ilac_sonuc, Y7_IZINLI, grup=grup_yetki))

    # KY7.1 DPP-4 YOK
    if _diger_kalemler_iceriyor(ilac_sonuc, DPP4):
        sartlar.append(SartSonuc(
            ad='Aynı reçetede DPP-4 YOK', durum=SartDurumu.YOK,
            neden='SUT 7: Soliqua + DPP-4 birlikte ödenmez',
            kaynak='recete_ilaclari', grup=grup_kombi))
    else:
        sartlar.append(SartSonuc(
            ad='Aynı reçetede DPP-4 YOK', durum=SartDurumu.VAR,
            neden='Reçete DPP-4 içermiyor',
            kaynak='recete_ilaclari', grup=grup_kombi))

    # KY7.2 aktif tedavi sırasında pankreatit YOK
    if re.search(r'(?:tedavi.{0,15}pankreatit|pankreatit.{0,15}geli[şs])', metin):
        sartlar.append(SartSonuc(
            ad='Aktif tedavi sırasında pankreatit YOK', durum=SartDurumu.YOK,
            neden='Rapor: aktif tedavi sırasında pankreatit',
            kaynak='rapor', grup=grup_kombi))
    else:
        sartlar.append(SartSonuc(
            ad='Aktif tedavi sırasında pankreatit YOK', durum=SartDurumu.VAR,
            neden='Rapor sessiz — pankreatit gelişim belirtilmemiş',
            kaynak='rapor', grup=grup_kombi))

    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y8 — Empa+Lina kombi (Glyxambi, Fıkra 8)
# Formül: Y8.1 ∧ Y8.2 ∧ Y8.3 ∧ (Y8.4 ∨ Y8.5) ∧ KY8.1 ∧ KY8.2 ∧ KY8.3
# (KY8.1/2/3 çapraz kombi içinde işlenir — burada placeholder VAR koy)
# ═══════════════════════════════════════════════════════════════════════

Y8_IZINLI = {'endokrin', 'ic'}


def y8_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y8: Empa+Lina kombi (Glyxambi).

    PARALEL-YOL kalıbı (2026-05-25, üst-VEYA çifti):
      Y8_UYGUN ⇔ Y8.1 ∧ Y8.2 ∧
                 ( [ Y8.4 ] ∨ [ Y8.5 ∧ Y8.3 ] )
                 ∧ KY8.1 ∧ KY8.2 ∧ KY8.3
    """
    sartlar: List[SartSonuc] = []
    grup_altyapi = 'Fıkra (8) — Önceki tedavi altyapısı'
    grup_raporsuz = '‖Y8‖ Raporsuz Yol — Hekim Endo/IH'
    grup_raporsuz_bilgi = '‖Y8‖ Raporsuz Yol — Klinik şart hekim sorumluluğu (bilgi)'
    grup_raporlu = '‖Y8‖ Raporlu Yol — Rapor Endo/IH + Klinik şart'

    # Y8.1 Önceki Met/Sulfo (hep gerekli)
    sartlar.append(atom_onceden_met_veya_sulfo_y8(ilac_sonuc, grup_altyapi))
    # Y8.2 Önceki Empa/Lina (hep gerekli)
    sartlar.append(atom_onceden_empa_veya_lina_y8(ilac_sonuc, grup_altyapi))

    # RAPORSUZ YOL
    hekim_atomu = atom_hekim_brans_uygun(ilac_sonuc, Y8_IZINLI, grup=grup_raporsuz)
    hekim_atomu.veya_grubu = False
    sartlar.append(hekim_atomu)
    sartlar.append(SartSonuc(
        ad='Yetersiz glisemik kontrol — raporsuz yolda hekim sorumluluğunda',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Endo/IH uzmanı raporsuz yazma yetkisine sahip; klinik şart '
              'hekim sorumluluğunda (eczacı/sistem doğrulayamaz)',
        kaynak='hekim_sorumluluk', grup=grup_raporsuz_bilgi,
        sartli_atom=True))

    # RAPORLU YOL
    rapor_atomu = atom_uzman_raporu_brans(ilac_sonuc, Y8_IZINLI, grup=grup_raporlu)
    rapor_atomu.veya_grubu = False
    sartlar.append(rapor_atomu)
    klinik_atomu = atom_yetersiz_glisemik_kontrol(ilac_sonuc, grup_raporlu)
    klinik_atomu.veya_grubu = False
    sartlar.append(klinik_atomu)
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y_KY — SGLT-2 / Kalp Yetmezliği (SUT 4.2.74-1)
# Formül: (KY1a ∨ KY1b) ∧ KY2 ∧ KY3 ∧ KY4 ∧ KY5 ∧ KY6 ∧ KY7
# ═══════════════════════════════════════════════════════════════════════

def y_ky_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y_KY: Dapa/Empa Kalp Yetmezliği endikasyonu (SUT 4.2.74-1)."""
    sartlar: List[SartSonuc] = []
    grup_kytedavi = 'SUT 4.2.74(1) — Standart KY tedavi VEYA gerekçe'
    grup_klinik = 'SUT 4.2.74(1) — KY klinik'
    grup_yetki = 'SUT 4.2.74(1) — Rapor + heyet'

    # KY2 KY endikasyonu
    teshisler = ilac_sonuc.get('recete_teshisleri') or []
    teshis_str = norm_tr_upper(' '.join(teshisler))
    metin = _rapor_metni(ilac_sonuc)
    if re.search(r'\bI50(\.\d+)?\b', teshis_str):
        sartlar.append(SartSonuc(
            ad='Kronik KY endikasyonu', durum=SartDurumu.VAR,
            neden='ICD I50.x bulundu', kaynak='teshis', grup=grup_klinik))
    elif re.search(r'(kalp\s*yetersizli|kalp\s*yetmezli|hf\s*ref|kkb)', metin):
        sartlar.append(SartSonuc(
            ad='Kronik KY endikasyonu', durum=SartDurumu.VAR,
            neden='Rapor lafzı: kalp yetersizliği', kaynak='rapor',
            grup=grup_klinik))
    else:
        sartlar.append(SartSonuc(
            ad='Kronik KY endikasyonu', durum=SartDurumu.YOK,
            neden='ICD I50.x ve rapor KY lafzı yok',
            kaynak='teshis+rapor', grup=grup_klinik))

    # KY3 EF ≤ 40
    sartlar.append(atom_ef_40_alti(ilac_sonuc, grup_klinik))
    # KY4 NYHA II-IV
    sartlar.append(atom_nyha_2_4(ilac_sonuc, grup_klinik))
    # KY1a/b/c — standart KY tedavi VEYA gerekçe (paralel-OR, ≥1 yeterli)
    sartlar.append(atom_standart_ky_tedavi_kullaniyor(ilac_sonuc, grup_kytedavi))
    sartlar.append(atom_standart_ky_tedavi_rapor_lafzi(ilac_sonuc, grup_kytedavi))
    sartlar.append(atom_ky_kullanilamama_gerekce(ilac_sonuc, grup_kytedavi))
    # KY5 eGFR
    sartlar.append(atom_egfr_uygun(ilac_sonuc, grup_klinik))
    # KY7 Kardiyolog heyette
    sartlar.append(atom_heyet_kardiyolog(ilac_sonuc, grup_yetki))
    # KY6 SK rapor (heyet listesi var ise VAR)
    if ilac_sonuc.get('heyet_doktorlari'):
        sartlar.append(SartSonuc(
            ad='Sağlık kurulu raporu (1 yıl süreli)', durum=SartDurumu.VAR,
            neden='Heyet listesi mevcut',
            kaynak='rapor_heyet', grup=grup_yetki))
    else:
        sartlar.append(SartSonuc(
            ad='Sağlık kurulu raporu (1 yıl süreli)',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Heyet listesi alınamadı', kaynak='rapor_heyet',
            grup=grup_yetki, sartli_atom=True))

    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y_KBH — SGLT-2 / Kronik Böbrek Hastalığı (SUT 4.2.74-2)
# Formül: KBH1 ∧ KBH2 ∧ KBH3 ∧ (KBH4a ∨ KBH4b) ∧ KBH5 ∧ KBH6 ∧ KBH7
# ═══════════════════════════════════════════════════════════════════════

def y_kbh_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y_KBH: Dapa/Empa Kronik Böbrek Hastalığı endikasyonu (SUT 4.2.74-2)."""
    sartlar: List[SartSonuc] = []
    grup_klinik = 'SUT 4.2.74(2) — KBH klinik'
    grup_protein = 'SUT 4.2.74(2) — Proteinüri (ACR∨PCR)'
    grup_yetki = 'SUT 4.2.74(2) — Rapor + heyet'

    # KBH1
    sartlar.append(atom_kbh_var(ilac_sonuc, grup_klinik))
    # KBH2 RAAS-İ
    sartlar.append(atom_raas_kullaniyor(ilac_sonuc, grup_klinik))
    # KBH3 persistan ≥3 ay
    sartlar.append(atom_proteinuri_persistan_3ay(ilac_sonuc, grup_klinik))
    # KBH4a/b ACR ∨ PCR
    sartlar.append(atom_acr_uygun(ilac_sonuc, grup_protein))
    sartlar.append(atom_pcr_uygun(ilac_sonuc, grup_protein))
    # KBH5 eGFR
    sartlar.append(atom_egfr_uygun(ilac_sonuc, grup_klinik))
    # KBH7 nefrolog heyette
    sartlar.append(atom_heyet_nefrolog(ilac_sonuc, grup_yetki))
    # KBH6 SK rapor
    if ilac_sonuc.get('heyet_doktorlari'):
        sartlar.append(SartSonuc(
            ad='Sağlık kurulu raporu', durum=SartDurumu.VAR,
            neden='Heyet listesi mevcut',
            kaynak='rapor_heyet', grup=grup_yetki))
    else:
        sartlar.append(SartSonuc(
            ad='Sağlık kurulu raporu',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Heyet listesi alınamadı', kaynak='rapor_heyet',
            grup=grup_yetki, sartli_atom=True))

    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# Çapraz kombi yasakları (reçete bütünü)
# ═══════════════════════════════════════════════════════════════════════

def _diger_kalemler_arama_metni(ilac_sonuc: Dict) -> str:
    """Aynı reçetedeki DİĞER kalemlerin TR→ASCII upper-case birleşik metni."""
    diger = ilac_sonuc.get('recete_ilaclari') or []
    parcalar: List[str] = []
    for kalem in diger:
        if isinstance(kalem, dict):
            parcalar.append(norm_tr_upper(str(kalem.get('ad') or '')))
            parcalar.append(norm_tr_upper(str(kalem.get('etkin_madde') or '')))
        else:
            parcalar.append(norm_tr_upper(str(kalem)))
    return ' '.join(parcalar)


def capraz_kombi_yasak(ilac_sonuc: Dict, aktif_yolak: str) -> List[SartSonuc]:
    """Reçete bütününde çapraz kombi yasaklarını uygula.

    SUT 4(ç), 5(ç), 7, 8 kombi yasakları:
      - DPP-4 + GLP-1 birlikte → ödenmez
      - Y8 (empa+lina) + diğer DPP-4 / SGLT-2 / GLP-1 → ödenmez
      - Y5 (eksenatid) + DPP-4 → ödenmez
      - Y7 (glarjin+liks) + DPP-4 → ödenmez

    UYGUN_DEĞİL'e götürecek bir çakışma varsa SartDurumu.YOK ile döner.
    """
    sartlar: List[SartSonuc] = []
    diger_metin = _diger_kalemler_arama_metni(ilac_sonuc)
    if not diger_metin.strip():
        return sartlar

    var_dpp4 = _iceriyor(diger_metin, DPP4)
    var_sglt2 = _iceriyor(diger_metin, SGLT2)
    var_glp1 = (_iceriyor(diger_metin, GLP1_EKSENATID)
                or _iceriyor(diger_metin, GLP1_DIGER))

    # DPP-4 + GLP-1
    if aktif_yolak == 'Y4' and var_glp1:
        sartlar.append(SartSonuc(
            ad='Kombi yasağı: DPP-4 + GLP-1',
            durum=SartDurumu.YOK,
            neden='SUT 4(ç): DPP-4 ile GLP-1 analoğu birlikte ödenmez',
            kaynak='diger_kalemler',
            grup='Çapraz kombi yasağı',
        ))

    # Y5 eksenatid + DPP-4
    if aktif_yolak == 'Y5' and var_dpp4:
        sartlar.append(SartSonuc(
            ad='Kombi yasağı: Eksenatid + DPP-4',
            durum=SartDurumu.YOK,
            neden='SUT 5(ç): Eksenatid DPP-4 ile birlikte ödenmez',
            kaynak='diger_kalemler',
            grup='Çapraz kombi yasağı',
        ))

    # Y7 Soliqua + DPP-4
    if aktif_yolak == 'Y7' and var_dpp4:
        sartlar.append(SartSonuc(
            ad='Kombi yasağı: Glarjin+Liksisenatid + DPP-4',
            durum=SartDurumu.YOK,
            neden='SUT 7: Soliqua (GLP-1) DPP-4 ile birlikte ödenmez',
            kaynak='diger_kalemler',
            grup='Çapraz kombi yasağı',
        ))

    # Y8 Glyxambi + diğer DPP-4 (lina hariç) / SGLT-2 (empa hariç) / GLP-1
    if aktif_yolak == 'Y8':
        # Lina ve empa Y8'in kendi bileşenleri — diğer kalemde TEKRAR yoksa OK
        # diğer kalemde LINAGLIPTIN tek başına varsa "diğer DPP-4" sayılır mı?
        # SUT: "diğer DPP-4 antagonistleri" → lina hariç DPP-4 demek değil,
        # lina dahil herhangi bir DPP-4 demek. Glyxambi zaten lina içeriyor, ek
        # DPP-4 ekleyince doz aşımı / dup tedavi → ödenmez.
        if var_dpp4:
            sartlar.append(SartSonuc(
                ad='Kombi yasağı: Glyxambi + diğer DPP-4',
                durum=SartDurumu.YOK,
                neden='SUT 8: Empa+Lina kombi DPP-4 ile birlikte ödenmez',
                kaynak='diger_kalemler',
                grup='Çapraz kombi yasağı',
            ))
        if var_sglt2:
            sartlar.append(SartSonuc(
                ad='Kombi yasağı: Glyxambi + diğer SGLT-2',
                durum=SartDurumu.YOK,
                neden='SUT 8: Empa+Lina kombi diğer SGLT-2 ile birlikte ödenmez',
                kaynak='diger_kalemler',
                grup='Çapraz kombi yasağı',
            ))
        if var_glp1:
            sartlar.append(SartSonuc(
                ad='Kombi yasağı: Glyxambi + GLP-1',
                durum=SartDurumu.YOK,
                neden='SUT 8: Empa+Lina kombi GLP-1 ile birlikte ödenmez',
                kaynak='diger_kalemler',
                grup='Çapraz kombi yasağı',
            ))

    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# Genel sonuç hesaplama (CLAUDE.md disiplini)
# ═══════════════════════════════════════════════════════════════════════

_PARALEL_MARKER_RE = re.compile(r'‖([^‖]+)‖')


def _paralel_yolak_marker(grup_adi: str) -> str:
    """Grup adında `‖<yolak>‖` marker'ı varsa yolak kodunu döndür, yoksa ''.

    Konvansiyon: ‖Y4‖ Raporsuz Yol  ↔  ‖Y4‖ Raporlu Yol  → aynı çift
    (bkz. docs/sut/SUT_4_2_38_DIYABET_ANALIZ.md §3b)
    """
    if not grup_adi:
        return ''
    m = _PARALEL_MARKER_RE.search(grup_adi)
    return m.group(1) if m else ''


def _grup_degerlendir(grup_sartlar: List[SartSonuc]) -> Tuple[str, bool]:
    """Tek bir grubun durumunu hesapla.

    Döner: ('var'|'yok'|'ke', sadece_sartli_ke_mi)
    """
    veya = any(s.veya_grubu for s in grup_sartlar)
    durumlar = [s.durum for s in grup_sartlar]

    if veya:
        if SartDurumu.VAR in durumlar:
            return 'var', True
        if all(d == SartDurumu.YOK for d in durumlar):
            return 'yok', False
        # KE var
        sadece_sartli = all(s.sartli_atom for s in grup_sartlar
                            if s.durum == SartDurumu.KONTROL_EDILEMEDI)
        return 'ke', sadece_sartli
    # AND
    if SartDurumu.YOK in durumlar:
        return 'yok', False
    if all(d == SartDurumu.VAR for d in durumlar):
        return 'var', True
    sadece_sartli = all(s.sartli_atom for s in grup_sartlar
                        if s.durum == SartDurumu.KONTROL_EDILEMEDI)
    return 'ke', sadece_sartli


def _ust_or_birlestir(a: str, b: str) -> str:
    """Üst-VEYA çiftinin sonucu (paralel-yol kalıbı, bkz. §3b tablo).

    a, b ∈ {'var','yok','ke'}.
    VAR/* → VAR; YOK/YOK → YOK; aksi (KE içeren) → KE
    """
    if a == 'var' or b == 'var':
        return 'var'
    if a == 'yok' and b == 'yok':
        return 'yok'
    return 'ke'


def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    """SartSonuc listesinden genel sonucu hesapla.

    Mantık (CLAUDE.md disiplini):
      - Bir grupta veya_grubu=True ise → grup içinde ≥1 VAR yeterli; hepsi YOK ise grup YOK
      - Bir grupta veya_grubu=False ise → AND (hepsi VAR olmalı; YOK varsa grup YOK)
      - Şartlı atomlar (sartli_atom=True) KE iken diğer her şey VAR → SARTLI_UYGUN
      - Bir grup bile YOK varsa → UYGUN_DEGIL
      - KE varsa ve diğerleri VAR → ŞÜPHELİ (MANUEL_KONTROL ya da KONTROL_EDILEMEDI)

    PARALEL-YOL kalıbı (§3b):
      - Grup adında ‖<yolak>‖ marker'ı taşıyan gruplar üst-VEYA çifti olarak
        birleştirilir. Çiftin biri VAR ise üst-VEYA VAR. İkisi de YOK ise YOK.
        Aksi KE.
    """
    # Grup bazlı topla
    gruplar: Dict[str, List[SartSonuc]] = {}
    for s in sartlar:
        gruplar.setdefault(s.grup, []).append(s)

    # Marker'lı grupları yolak kodlarına göre kümelendir
    paralel_gruplar: Dict[str, List[Tuple[str, bool]]] = {}
    normal_grup_sonuclari: List[Tuple[str, bool]] = []

    for grup_adi, grup_sartlar in gruplar.items():
        if '(bilgi)' in (grup_adi or ''):
            continue
        marker = _paralel_yolak_marker(grup_adi)
        durum, sartli = _grup_degerlendir(grup_sartlar)
        if marker:
            paralel_gruplar.setdefault(marker, []).append((durum, sartli))
        else:
            normal_grup_sonuclari.append((durum, sartli))

    grup_sonuclari: List[str] = []
    sadece_sartli_ke = True

    # Normal gruplar
    for durum, sartli in normal_grup_sonuclari:
        grup_sonuclari.append(durum)
        if durum == 'yok':
            sadece_sartli_ke = False
        elif durum == 'ke' and not sartli:
            sadece_sartli_ke = False

    # Paralel-yol grupları (üst-VEYA çiftleri)
    for marker, durum_listesi in paralel_gruplar.items():
        # Çift olabilir (Raporsuz + Raporlu) veya tek (raporsuz/raporlu yok)
        # Soldan sağa fold ile üst-OR birleştir
        birlesik_durum = durum_listesi[0][0]
        for d, _s in durum_listesi[1:]:
            birlesik_durum = _ust_or_birlestir(birlesik_durum, d)
        # sartli_ke bayrağı: paralel grupta KE varsa, KE üreten tüm atomlar
        # sartli_atom=True ise birleşik şartlı sayılır
        birlesik_sartli = all(s for d, s in durum_listesi if d == 'ke')
        grup_sonuclari.append(birlesik_durum)
        if birlesik_durum == 'yok':
            sadece_sartli_ke = False
        elif birlesik_durum == 'ke' and not birlesik_sartli:
            sadece_sartli_ke = False

    if 'yok' in grup_sonuclari:
        return KontrolSonucu.UYGUN_DEGIL
    if 'ke' in grup_sonuclari:
        if sadece_sartli_ke:
            return KontrolSonucu.SARTLI_UYGUN
        return KontrolSonucu.KONTROL_EDILEMEDI
    return KontrolSonucu.UYGUN


def _mesaj_uret(sonuc: KontrolSonucu, yolak: str,
                 sartlar: List[SartSonuc]) -> str:
    """Genel sonuç mesajı (insan-okur)."""
    var_sartlar = [s for s in sartlar if s.durum == SartDurumu.VAR]
    yok_sartlar = [s for s in sartlar if s.durum == SartDurumu.YOK]
    ke_sartlar = [s for s in sartlar if s.durum == SartDurumu.KONTROL_EDILEMEDI]

    parcalar: List[str] = [f"SUT 4.2.38 / Yolak {yolak}"]
    if sonuc == KontrolSonucu.UYGUN:
        parcalar.append("UYGUN — tüm şartlar sağlandı")
    elif sonuc == KontrolSonucu.SARTLI_UYGUN:
        parcalar.append("ŞARTLI UYGUN — hesaplanabilir tüm şartlar VAR; "
                        f"{len(ke_sartlar)} şart manuel doğrulama gerektiriyor")
    elif sonuc == KontrolSonucu.UYGUN_DEGIL:
        nedenler = '; '.join(s.ad for s in yok_sartlar[:3])
        parcalar.append(f"UYGUN DEĞİL — {nedenler}")
    elif sonuc == KontrolSonucu.KONTROL_EDILEMEDI:
        parcalar.append(f"ŞÜPHELİ — {len(ke_sartlar)} şart kontrol edilemedi")
    return ' | '.join(parcalar)


# ═══════════════════════════════════════════════════════════════════════
# ANA ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════

YOLAK_FN_MAP = {
    'Y1':  y1_kontrol,
    'Y2':  y2_kontrol,
    'Y3':  y3_kontrol,
    'Y3b': y3b_kontrol,
    'Y4':  y4_kontrol,
    'Y5':  y5_kontrol,
    'Y6':  y6_kontrol,
    'Y7':  y7_kontrol,
    'Y8':  y8_kontrol,
    'Y9_KAPSAM_DISI': y9_kapsam_disi_kontrol,
    'Y_KY':  y_ky_kontrol,
    'Y_KBH': y_kbh_kontrol,
}


# ═══════════════════════════════════════════════════════════════════════
# DİĞER YOLAKLAR — GUI accordion paneli için metadata + lazy hesap
# ═══════════════════════════════════════════════════════════════════════

DIYABET_YOLAK_METADATA: Dict[str, Dict[str, str]] = {
    'Y1':            {'ad': 'Met / Sulfo / Akarboz / İnsan ins.', 'sut': '4.2.38 (1)'},
    'Y2':            {'ad': 'Repaglinid / Nateglinid (Glinid)',    'sut': '4.2.38 (2)'},
    'Y3':            {'ad': 'Analog İnsülin / Pioglitazon (TZD)',  'sut': '4.2.38 (3)'},
    'Y3b':           {'ad': 'Kombi Degludek+Aspart (Ryzodeg)',     'sut': '4.2.38 (3b)'},
    'Y4':            {'ad': 'DPP-4 (+kombi)',                       'sut': '4.2.38 (4)'},
    'Y5':            {'ad': 'Eksenatid',                            'sut': '4.2.38 (5)'},
    'Y6':            {'ad': 'SGLT-2 (DM endikasyonu)',              'sut': '4.2.38 (6)'},
    'Y7':            {'ad': 'Kombi Glarjin+Liksisenatid (Soliqua)','sut': '4.2.38 (7)'},
    'Y8':            {'ad': 'Kombi Empa+Lina (Glyxambi)',          'sut': '4.2.38 (8)'},
    'Y9_KAPSAM_DISI':{'ad': 'Diğer GLP-1 (lira/sema/dula/tirze)',  'sut': 'Kapsam dışı'},
    'Y_KY':          {'ad': 'SGLT-2 (KY endikasyonu)',             'sut': '4.2.74 (1)'},
    'Y_KBH':         {'ad': 'SGLT-2 (KBH endikasyonu)',            'sut': '4.2.74 (2)'},
}


def _dia_eleme_nedeni(yolak_kod: str, aktif_kod: str, ilac_sonuc: Dict) -> str:
    """Diyabet pasif yolak için kısa eleme nedeni."""
    m = _arama_metni(ilac_sonuc)
    if yolak_kod == 'Y1' and not (_iceriyor(m, METFORMIN) or _iceriyor(m, SULFONILURE)
                                    or _iceriyor(m, AKARBOZ) or _iceriyor(m, INSAN_INSULIN)):
        return 'Reçete ilacı Met/Sulfo/Akarboz/İnsan insülin grubunda değil'
    if yolak_kod == 'Y2' and not _iceriyor(m, GLINID):
        return 'Reçete ilacı Repaglinid/Nateglinid değil'
    if yolak_kod == 'Y3' and not (_iceriyor(m, ANALOG_INSULIN) or _iceriyor(m, TZD)):
        return 'Reçete ilacı Analog insülin/Pioglitazon değil'
    if yolak_kod == 'Y3b' and not _iceriyor(m, KOMBI_DEGLUDEK_ASPART):
        return 'Reçete ilacı Degludek+Aspart kombi (Ryzodeg) değil'
    if yolak_kod == 'Y4' and not _iceriyor(m, DPP4):
        return 'Reçete ilacı DPP-4 grubunda değil'
    if yolak_kod == 'Y5' and not _iceriyor(m, GLP1_EKSENATID):
        return 'Reçete ilacı Eksenatid değil'
    if yolak_kod == 'Y6' and not _iceriyor(m, SGLT2):
        return 'Reçete ilacı SGLT-2 grubunda değil'
    if yolak_kod == 'Y7' and not _iceriyor(m, KOMBI_GLARJIN_LIKSISENATID):
        return 'Reçete ilacı Glarjin+Liksisenatid kombi (Soliqua) değil'
    if yolak_kod == 'Y8' and not _iceriyor(m, KOMBI_EMPA_LINA):
        return 'Reçete ilacı Empa+Lina kombi (Glyxambi) değil'
    if yolak_kod == 'Y9_KAPSAM_DISI' and not _iceriyor(m, GLP1_DIGER):
        return 'Reçete ilacı diğer GLP-1 (lira/sema/dula/tirze) değil'
    if yolak_kod in ('Y_KY', 'Y_KBH') and not _iceriyor(m, SGLT2):
        return 'Reçete ilacı SGLT-2 (dapa/empa) değil — 4.2.74 kapsamı'
    if yolak_kod == 'Y_KY' and aktif_kod in ('Y_KBH', 'Y6'):
        return 'Aktif rapor KBH/DM endikasyonu — KY ibareleri öncelikli değil'
    if yolak_kod == 'Y_KBH' and aktif_kod in ('Y_KY', 'Y6'):
        return 'Aktif rapor KY/DM endikasyonu — KBH ibareleri öncelikli değil'
    return 'Dispatcher önceliği başka yolağa verdi'


def _dia_diger_yolaklar(aktif_kod: str, ilac_sonuc: Dict) -> List[Dict]:
    """Aktif olmayan tüm yolaklar için metadata listesi (GUI accordion)."""
    if aktif_kod not in DIYABET_YOLAK_METADATA:
        return []
    return [{
        'kod': kod,
        'ad': meta['ad'],
        'sut': meta['sut'],
        'eleme_nedeni': _dia_eleme_nedeni(kod, aktif_kod, ilac_sonuc),
    } for kod, meta in DIYABET_YOLAK_METADATA.items() if kod != aktif_kod]


def diyabet_yolak_hesapla(ilac_sonuc: Dict, yolak_kodu: str) -> KontrolRaporu:
    """Spesifik bir diyabet yolağını dispatcher bypass'le çalıştır (lazy).

    GUI accordion paneli pasif yolak başlığına tıklandığında çağırır."""
    yolak_fn = YOLAK_FN_MAP.get(yolak_kodu)
    if not yolak_fn:
        return KontrolRaporu(
            sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
            mesaj=f'Bilinmeyen yolak: {yolak_kodu}',
            sut_kurali='SUT 4.2.38')
    sartlar = yolak_fn(ilac_sonuc)
    sartlar.extend(capraz_kombi_yasak(ilac_sonuc, yolak_kodu))
    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak_kodu, sartlar)
    return KontrolRaporu(
        sonuc=sonuc, mesaj=mesaj,
        sut_kurali=f'SUT 4.2.38 / Yolak {yolak_kodu} (manuel)',
        sartlar=sartlar,
        detaylar={'yolak': yolak_kodu, 'manuel_yolak': True})


def diyabet_kontrol_4_2_38(ilac_sonuc: Dict) -> KontrolRaporu:
    """SUT 4.2.38 ana kontrol fonksiyonu.

    Akış:
      1. Etken madde → yolak belirle (dispatcher)
      2. Yolak fonksiyonu çalıştır → SartSonuc[]
      3. Çapraz kombi yasaklarını ekle
      4. Genel sonuç hesapla (UYGUN / ŞARTLI_UYGUN / ŞÜPHELİ / UYGUN_DEĞİL)
    """
    yolak = yolak_belirle(ilac_sonuc)
    if not yolak:
        return KontrolRaporu(
            sonuc=KontrolSonucu.ATLANDI,
            mesaj='SUT 4.2.38 kapsamı dışı — diyabet ilacı tespit edilemedi',
            sut_kurali='SUT 4.2.38',
        )

    yolak_fn = YOLAK_FN_MAP.get(yolak)
    sartlar = yolak_fn(ilac_sonuc) if yolak_fn else []

    # Çapraz kombi yasakları
    sartlar.extend(capraz_kombi_yasak(ilac_sonuc, yolak))

    # ── DİĞER RAPOR BYPASS — atomları otomatik tarayıp bypass uygula ─────
    # Atom adında "metformin", "sülfonilüre" veya "glisemik" geçen ve durumu
    # VAR olmayan atomlar için hastanın geçmiş raporlarında ibare aranır;
    # bulunursa atom VAR + bypass_kaynak olarak işaretlenir. Tüm atomlar
    # sonra _genel_sonuc'a girer ve UYGUN dönerse sonuç DIGER_RAPOR_UYGUN'a
    # yükseltilir (sonuc_bypass_uygula_genel altta).
    bypass_basariyla_denendi = False
    try:
        from recete_kontrol.diger_rapor_bypass import (
            atomlari_otomatik_bypass, sonuc_bypass_uygula_genel,
            IBARELER_DIYABET_GLISEMIK)
        atomlari_otomatik_bypass(
            sartlar, ilac_sonuc,
            ad_anahtar_kelimeleri=('metformin', 'sülfonilüre', 'sulfonilure',
                                    'glisemik'),
            ibareler=IBARELER_DIYABET_GLISEMIK,
            kategori='DIYABET')
        bypass_basariyla_denendi = True
    except Exception as e:
        # Bypass opsiyonel — başarısızlığı kontrolü etkilemez
        import logging as _lg
        _lg.getLogger(__name__).debug("Diyabet bypass atlandı: %s", e)

    # ── METFORMİN/SÜLFONİLÜRE klinik şartı DEMOTE: KE → YOK ──────────────
    # Kullanıcı kuralı 2026-05-24: SUT 4.2.38 lafzı "metformin ve
    # sülfonilürelerin maksimum tolere edilebilir dozlarında yeterli
    # glisemik kontrol sağlanamamıştır" şartını NET olarak istiyor. Aktif
    # rapor sessiz olabilir → bypass Botanik EOS + MEDULA cache'i tarar.
    # Bypass'tan sonra atom hâlâ VAR olamamışsa (hiçbir raporda ibare yok)
    # klinik şart KANITLANMIŞ YOKLUK demektir → şart YOK → UYGUN_DEGIL.
    # Sessizlik=KE örtük kabul yasağı (CLAUDE.md §2.5) burada uygulanmaz
    # çünkü tüm rapor kaynakları taranmıştır.
    # Sadece bypass başarıyla denendiyse demote uygulanır (EOS/import hatası
    # durumunda KE kalır, ŞÜPHELİ döner — güvenli mod).
    if bypass_basariyla_denendi and (ilac_sonuc.get('hasta_tc') or '').strip():
        _DEMOTE_ANAHTAR = ('metformin', 'sülfonilüre', 'sulfonilure')
        for _s in sartlar:
            if _s.durum != SartDurumu.KONTROL_EDILEMEDI:
                continue
            _ad_n = norm_tr_lower(_s.ad or '')
            if not any(k in _ad_n for k in _DEMOTE_ANAHTAR):
                continue
            _eski_neden = _s.neden or ''
            _s.durum = SartDurumu.YOK
            _s.neden = (
                f'{_eski_neden} | Aktif rapor + Botanik EOS + MEDULA cache '
                f'tarandı; klinik şart ibaresi hiçbir raporda bulunamadı '
                f'→ şart YOK (SUT 4.2.38 klinik şartı sağlanmıyor)'
            ) if _eski_neden else (
                'Aktif rapor + Botanik EOS + MEDULA cache tarandı; klinik '
                'şart ibaresi hiçbir raporda bulunamadı → şart YOK '
                '(SUT 4.2.38 klinik şartı sağlanmıyor)'
            )
            _s.sartli_atom = False  # artık ŞÜPHELİ değil, kesin YOK

    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)

    rapor = KontrolRaporu(
        sonuc=sonuc,
        mesaj=mesaj,
        sut_kurali=f'SUT 4.2.38 / Yolak {yolak}',
        sartlar=sartlar,
        detaylar={'yolak': yolak},
    )
    # Diğer yolaklar metadata (GUI accordion paneli için)
    try:
        rapor.detaylar['diger_yolaklar'] = _dia_diger_yolaklar(yolak, ilac_sonuc)
        rapor.detaylar['aktif_yolak_meta'] = DIYABET_YOLAK_METADATA.get(
            yolak, {'ad': yolak, 'sut': '?'})
        rapor.detaylar['kontrol_modulu'] = 'diyabet'
    except Exception:
        pass
    try:
        from recete_kontrol.diger_rapor_bypass import sonuc_bypass_uygula_genel
        sonuc_bypass_uygula_genel(rapor, sartlar)
    except Exception:
        pass
    return rapor
