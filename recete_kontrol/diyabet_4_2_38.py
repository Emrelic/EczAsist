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
    'REPAGLINID', 'NOVONORM',
    'NATEGLINID', 'STARLIX',
}

TZD: Set[str] = {  # Pioglitazon
    'PIOGLITAZON', 'PIOGLITAZON HCL', 'ACTOS', 'GLUSTIN', 'PIONORM',
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


def _arama_metni(ilac_sonuc: Dict) -> str:
    """İlaç adı + etkin madde birleşik upper-case arama metni."""
    ilac_adi = (ilac_sonuc.get('ilac_adi') or '').upper()
    etkin_madde = (ilac_sonuc.get('etkin_madde') or '').upper()
    return f"{ilac_adi} {etkin_madde}"


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

    # 5. SGLT-2 + kombi (DPP-4 değilse)
    if _iceriyor(m, SGLT2):
        return 'Y6'

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
            neden='Hekim branşı bilinmiyor',
            kaynak='hekim_brans',
            grup=grup,
            veya_grubu=True,
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
        ilac_sonuc.get('rapor_doktor_uzmanligi')
        or ilac_sonuc.get('rapor_uzmanlik')
    )
    if not rapor_brans:
        # Rapor doktoru branşı bilinmiyor — uzman raporu varlığını test edelim
        rapor_metin = (ilac_sonuc.get('rapor_metni') or '').lower()
        if rapor_metin and any(b in rapor_metin for b in
                               ['uzman hekim', 'uzman dr', 'uzm. dr', 'uzm dr']):
            return SartSonuc(
                ad='Uzman hekim raporu',
                durum=SartDurumu.KONTROL_EDILEMEDI,
                neden='Rapor var ama düzenleyen hekim branşı sorgulanamıyor',
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

    `endo, IH, pediatri, kardiyo, aile hekimi` uzmanı reçete eder
    VEYA aynı branşlardan birinin uzman hekim raporu varsa tüm hekimler.
    """
    sartlar: List[SartSonuc] = []
    sartlar.append(atom_hekim_brans_uygun(ilac_sonuc, Y2_IZINLI,
                                          grup='Fıkra (2) — yetki (≥1)'))
    sartlar.append(atom_uzman_raporu_brans(ilac_sonuc, Y2_IZINLI,
                                            grup='Fıkra (2) — yetki (≥1)'))
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
    Bulunmazsa KE (klinik şart kanıtlanamadı).
    """
    metin = (ilac_sonuc.get('rapor_metni') or '').lower()
    if not metin:
        return SartSonuc(
            ad='Metformin/sülfonilüre max doz yetersiz glisemik kontrol',
            durum=SartDurumu.KONTROL_EDILEMEDI,
            neden='Rapor metni boş — klinik şart sorgulanamadı',
            kaynak='rapor_metni',
            grup=grup,
        )
    # Anahtar lafız desenleri
    pat_met = re.compile(r'metformin', re.IGNORECASE)
    pat_sulfo = re.compile(
        r'(?:s[uü]lfon[ıi]l[uü]re|gliklazid|glimepirid|glibenklamid|glipizid)',
        re.IGNORECASE)
    # "maksimum tolere edilebilir doz", "max tolere doz", "maksimum dozda", "max dozda"
    pat_max = re.compile(
        r'(?:maks?[ıi]?mum|max)\.?\s*(?:tolere\s*(?:edilebilir\s*)?)?\s*doz',
        re.IGNORECASE)
    pat_yet = re.compile(
        r'(?:yeterli\s*(?:glisemik\s*)?kontrol\s*sa[gğ]lanam|yetersiz\s*(?:glisemik\s*)?kontrol|'
        r'kontrol\s*sa[gğ]lanama|glisemik\s*regulasyon\s*sa[gğ]lanam)',
        re.IGNORECASE)
    var_met = bool(pat_met.search(metin))
    var_sulfo = bool(pat_sulfo.search(metin))
    var_max = bool(pat_max.search(metin))
    var_yet = bool(pat_yet.search(metin))
    if (var_met or var_sulfo) and var_max and var_yet:
        return SartSonuc(
            ad='Metformin/sülfonilüre max doz yetersiz glisemik kontrol',
            durum=SartDurumu.VAR,
            neden='Rapor lafzında "max doz" + "yetersiz kontrol" ibareleri bulundu',
            kaynak='rapor_metni',
            grup=grup,
        )
    if var_yet and (var_met or var_sulfo):
        # Max doz ibaresi yok ama yetersiz kontrol var — şartlı (KE)
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

    Şartlar:
      Y6.1 = Met VE/VEYA Sulfo max doz yetersiz glisemik kontrol
      Y6.2 = reçete hekimi ∈ {Endo, IH}
      Y6.3 = uzman raporu (Endo/IH)
      Y6_UYGUN ⇔ Y6.1 ∧ (Y6.2 ∨ Y6.3)
    """
    sartlar: List[SartSonuc] = []
    sartlar.append(atom_metformin_sulfo_max_yetersiz(
        ilac_sonuc, grup='Fıkra (6) — klinik şart'))
    sartlar.append(atom_hekim_brans_uygun(
        ilac_sonuc, Y6_IZINLI, grup='Fıkra (6) — yetki (≥1)'))
    sartlar.append(atom_uzman_raporu_brans(
        ilac_sonuc, Y6_IZINLI, grup='Fıkra (6) — yetki (≥1)'))
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# YOLAK Y9 — Kapsam dışı GLP-1 (lira/sema/dula/tirze)
# ═══════════════════════════════════════════════════════════════════════

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

    Y2'den tek farkı: Aile hekimi yetkili DEĞİL.
    """
    sartlar: List[SartSonuc] = []
    sartlar.append(atom_hekim_brans_uygun(
        ilac_sonuc, Y3_IZINLI, grup='Fıkra (3) — yetki (≥1)'))
    sartlar.append(atom_uzman_raporu_brans(
        ilac_sonuc, Y3_IZINLI, grup='Fıkra (3) — yetki (≥1)'))
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
    teshis_str = ' '.join(teshisler).upper() if teshisler else ''
    icd_kby = bool(re.search(r'\bN18\.?\d?\b', teshis_str))
    metin = (ilac_sonuc.get('rapor_metni') or '').lower()
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

    Şartlar:
      Y4.1 = Met VE/VEYA Sulfo max doz yetersiz
      Y4.2 = reçete hekimi ∈ {Endo, IH}
      Y4.3 = uzman raporu (Endo/IH)
      Y4.4 = (saksa 2.5mg) → KBY VAR
      Y4.5 = (alo 12.5mg) → KBY VAR
      KY4.1 = aynı reçetede GLP-1 analoğu YOK  (çapraz kombi'de işlenir)
    """
    sartlar: List[SartSonuc] = []
    sartlar.append(atom_metformin_sulfo_max_yetersiz(
        ilac_sonuc, grup='Fıkra (4) — klinik şart'))
    sartlar.append(atom_hekim_brans_uygun(
        ilac_sonuc, Y4_IZINLI, grup='Fıkra (4) — yetki (≥1)'))
    sartlar.append(atom_uzman_raporu_brans(
        ilac_sonuc, Y4_IZINLI, grup='Fıkra (4) — yetki (≥1)'))
    dusuk_doz = atom_dpp4_dusuk_doz_kby(ilac_sonuc)
    if dusuk_doz is not None:
        sartlar.append(dusuk_doz)
    return sartlar


# ═══════════════════════════════════════════════════════════════════════
# YOLAKLAR Y3b / Y5 / Y7 / Y8 — TODO (sonraki turda)
# ═══════════════════════════════════════════════════════════════════════

def y3b_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y3b: Degludek+Aspart (Ryzodeg) — TODO sonraki tur."""
    return [SartSonuc(
        ad='Y3b Degludek+Aspart kontrolü',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Bu yolak henüz implemente edilmedi — manuel doğrulama',
        kaynak='todo',
        grup='Fıkra (3b) — Ryzodeg',
        sartli_atom=True,
    )]


def y5_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y5: Eksenatid — TODO sonraki tur."""
    return [SartSonuc(
        ad='Y5 Eksenatid kontrolü',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Bu yolak henüz implemente edilmedi — manuel doğrulama',
        kaynak='todo',
        grup='Fıkra (5) — Eksenatid',
        sartli_atom=True,
    )]


def y7_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y7: Glarjin+Liksisenatid (Soliqua) — TODO sonraki tur."""
    return [SartSonuc(
        ad='Y7 Glarjin+Liksisenatid kontrolü',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Bu yolak henüz implemente edilmedi — manuel doğrulama',
        kaynak='todo',
        grup='Fıkra (7) — Soliqua',
        sartli_atom=True,
    )]


def y8_kontrol(ilac_sonuc: Dict) -> List[SartSonuc]:
    """Y8: Empa+Lina kombi (Glyxambi) — TODO sonraki tur."""
    return [SartSonuc(
        ad='Y8 Empa+Lina kombi kontrolü',
        durum=SartDurumu.KONTROL_EDILEMEDI,
        neden='Bu yolak henüz implemente edilmedi — manuel doğrulama',
        kaynak='todo',
        grup='Fıkra (8) — Glyxambi',
        sartli_atom=True,
    )]


# ═══════════════════════════════════════════════════════════════════════
# Çapraz kombi yasakları (reçete bütünü)
# ═══════════════════════════════════════════════════════════════════════

def _diger_kalemler_arama_metni(ilac_sonuc: Dict) -> str:
    """Aynı reçetedeki DİĞER kalemlerin upper-case birleşik metni."""
    diger = ilac_sonuc.get('recete_ilaclari') or []
    parcalar: List[str] = []
    for kalem in diger:
        if isinstance(kalem, dict):
            parcalar.append(str(kalem.get('ad') or '').upper())
            parcalar.append(str(kalem.get('etkin_madde') or '').upper())
        else:
            parcalar.append(str(kalem).upper())
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

def _genel_sonuc(sartlar: List[SartSonuc]) -> KontrolSonucu:
    """SartSonuc listesinden genel sonucu hesapla.

    Mantık (CLAUDE.md disiplini):
      - Bir grupta veya_grubu=True ise → grup içinde ≥1 VAR yeterli; hepsi YOK ise grup YOK
      - Bir grupta veya_grubu=False ise → AND (hepsi VAR olmalı; YOK varsa grup YOK)
      - Şartlı atomlar (sartli_atom=True) KE iken diğer her şey VAR → SARTLI_UYGUN
      - Bir grup bile YOK varsa → UYGUN_DEGIL
      - KE varsa ve diğerleri VAR → ŞÜPHELİ (MANUEL_KONTROL ya da KONTROL_EDILEMEDI)
    """
    # Grup bazlı topla
    gruplar: Dict[str, List[SartSonuc]] = {}
    for s in sartlar:
        gruplar.setdefault(s.grup, []).append(s)

    grup_sonuclari: List[str] = []  # 'var' / 'yok' / 'ke'
    sadece_sartli_ke = True

    for grup_adi, grup_sartlar in gruplar.items():
        veya = any(s.veya_grubu for s in grup_sartlar)
        durumlar = [s.durum for s in grup_sartlar]

        if veya:
            # OR — en az 1 VAR yeterli
            if SartDurumu.VAR in durumlar:
                grup_sonuclari.append('var')
            elif all(d == SartDurumu.YOK for d in durumlar):
                grup_sonuclari.append('yok')
                sadece_sartli_ke = False
            else:
                # KE'ler var
                grup_sonuclari.append('ke')
                if not all(s.sartli_atom for s in grup_sartlar
                           if s.durum == SartDurumu.KONTROL_EDILEMEDI):
                    sadece_sartli_ke = False
        else:
            # AND — hepsi VAR olmalı
            if SartDurumu.YOK in durumlar:
                grup_sonuclari.append('yok')
                sadece_sartli_ke = False
            elif all(d == SartDurumu.VAR for d in durumlar):
                grup_sonuclari.append('var')
            else:
                grup_sonuclari.append('ke')
                if not all(s.sartli_atom for s in grup_sartlar
                           if s.durum == SartDurumu.KONTROL_EDILEMEDI):
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
}


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
    except Exception as e:
        # Bypass opsiyonel — başarısızlığı kontrolü etkilemez
        import logging as _lg
        _lg.getLogger(__name__).debug("Diyabet bypass atlandı: %s", e)

    sonuc = _genel_sonuc(sartlar)
    mesaj = _mesaj_uret(sonuc, yolak, sartlar)

    rapor = KontrolRaporu(
        sonuc=sonuc,
        mesaj=mesaj,
        sut_kurali=f'SUT 4.2.38 / Yolak {yolak}',
        sartlar=sartlar,
        detaylar={'yolak': yolak},
    )
    try:
        from recete_kontrol.diger_rapor_bypass import sonuc_bypass_uygula_genel
        sonuc_bypass_uygula_genel(rapor, sartlar)
    except Exception:
        pass
    return rapor
