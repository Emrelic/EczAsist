"""Resmî SUT lafzını AI paketine gömme.

Kaynak: docs/sut/SUT_tam_metin.txt — mevzuat.gov.tr'den indirilen resmî
Sağlık Uygulama Tebliği (MevzuatNo=17229). CLAUDE.md §11: SUT lafzı
ezberden türetilmez, resmî metinden okunur. Bu modül aynı prensibi AI
kontrolüne taşır: ilacın ATC koduna göre ilgili SUT maddesi tespit edilir
ve maddenin TAM METNİ pakete `sut_lafzi` alanı olarak eklenir — AI şart
analizini hafızasındaki (muhtemelen eski) SUT yerine bu güncel resmî
lafza göre yapar.

Güncelleme: resmî metin değişince CLAUDE.md'deki curl+pdftotext komutuyla
SUT_tam_metin.txt yenilenir; bu modül otomatik yeni metni kullanır.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_SUT_TXT = Path(__file__).resolve().parents[2] / "docs" / "sut" / "SUT_tam_metin.txt"

# Madde metni üst sınırı (karakter) — 4.2.14 gibi dev maddelerde paket şişmesin
MAX_MADDE_KARAKTER = 24000

# ─── ATC öneki → SUT maddesi ────────────────────────────────────────────────
# Prompt'taki eşleme tablosunun makine hâli. EN UZUN önek kazanır.
# Sadece ana tebliğ maddeleri (EK-4/F liste ilaçları ayrı yapıda — dahil değil).
ATC_MADDE_HARITASI: Dict[str, str] = {
    # Hepatit (4.2.13): nükleoz(t)id analogları + HCV DAA + interferonlar
    "J05AF": "4.2.13",   # lamivudin/entekavir/tenofovir (TDF + alafenamid)
    "J05AP": "4.2.13",   # HCV antiviralleri
    "L03AB": "4.2.13",   # interferonlar
    # Diyabet
    "A10": "4.2.38",
    # Lipid düşürücüler
    "C10": "4.2.28",
    # Antitrombotikler
    "B01AC04": "4.2.15.A",   # klopidogrel
    "B01AC23": "4.2.15.B",   # silostazol
    "B01AC22": "4.2.15.Ç",   # prasugrel
    "B01AC24": "4.2.15.E",   # tikagrelor
    "B01AF": "4.2.15.D",     # apiksaban/rivaroksaban/edoksaban (YOAK)
    "B01AE07": "4.2.15.D",   # dabigatran
    # Parenteral demir
    "B03AC": "4.2.41",
    # ESA + fosfor bağlayıcılar
    "B03XA": "4.2.9.A",
    "V03AE02": "4.2.9.B",    # sevelamer
    "V03AE03": "4.2.9.B",    # lantanyum
    # Göz
    "S01E": "4.2.11",        # glokom
    "S01LA": "4.2.33",       # anti-VEGF
    # Kadın hormonları
    "G03": "4.2.29",
    # Biyolojikler / immünsüpresifler
    "L04AA13": "4.2.1.A",    # leflunomid
    "L04AB": "4.2.1.C",      # anti-TNF
    # İmmünglobulin + palivizumab
    "J06BA": "4.2.12",
    "J06BD01": "4.2.20",
    # Nöroloji
    "N03": "4.2.25",         # antiepileptik
    "N02CC": "4.2.19",       # triptanlar
    "N04": "4.2.36",         # parkinson
    # Antifungal
    "J02A": "4.2.23",
    # Alerji aşısı
    "V01AA": "4.2.3",
    # Orlistat
    "A08AB01": "4.2.18",
    # Topikal kalsinörin inhibitörleri
    "D11AH01": "4.2.58",
    "D11AH02": "4.2.58",
    # Solunum
    "R03": "4.2.24",
    # Osteoporoz
    "M05B": "4.2.17",
    "H05AA": "4.2.17",       # teriparatid
    # DMAH
    "B01AB": "4.2.7",
    # Grip aşısı
    "J07BB": "2.4.3",
}


def madde_no_bul(atc_kodu: str) -> Optional[str]:
    """ATC kodundan SUT maddesini tespit et (en uzun önek eşleşmesi)."""
    atc = (atc_kodu or "").strip().upper().replace(" ", "")
    if not atc:
        return None
    en_iyi = None
    for onek, madde in ATC_MADDE_HARITASI.items():
        if atc.startswith(onek):
            if en_iyi is None or len(onek) > len(en_iyi[0]):
                en_iyi = (onek, madde)
    return en_iyi[1] if en_iyi else None


def _baslik_deseni(madde: str) -> re.Pattern:
    """'4.2.13' → satır başında '4.2.13' ile başlayan başlık deseni."""
    esc = re.escape(madde)
    return re.compile(rf"^\s{{0,12}}{esc}(?![\d])", re.MULTILINE)


# Madde başlığı satırı: "      4.2.13 - Hepatit tedavisi",
# "      4.2.15.E-Tikagrelor;", "      4.2.13.3.2.A.1- ..." vb.
_BASLIK_SATIR = re.compile(
    r"^\s{0,12}(\d+(?:\.\d+)+(?:\.[A-ZÇĞİÖŞÜ](?:-\d+)?)*)\s*[-–\.\s]",
    re.MULTILINE)


def _altinda_mi(baslik: str, madde: str) -> bool:
    """`baslik` madde'nin kendisi ya da alt maddesi mi?

    '4.2.13.1' ⊂ '4.2.13';  '4.2.15.D-1' ⊂ '4.2.15.D';  '4.2.14' ⊄ '4.2.13'.
    """
    return (baslik == madde
            or baslik.startswith(madde + ".")
            or baslik.startswith(madde + "-"))


def madde_metni_al(madde: str) -> Optional[str]:
    """Resmî SUT metninden maddenin tam lafzını (alt maddeleri DAHİL) çıkar.

    Başlıktan başlar; madde ağacının DIŞINDAKİ ilk başlıkta durur.
    Dosya yoksa/başlık bulunamazsa None.
    """
    try:
        metin = _SUT_TXT.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        logger.warning("SUT metni okunamadı (%s): %s", _SUT_TXT, e)
        return None

    m = _baslik_deseni(madde).search(metin)
    if not m:
        logger.info("SUT maddesi başlığı bulunamadı: %s", madde)
        return None
    bas = m.start()

    son = len(metin)
    for m2 in _BASLIK_SATIR.finditer(metin, m.end()):
        if not _altinda_mi(m2.group(1), madde):
            son = m2.start()
            break

    govde = metin[bas:son].strip()
    if len(govde) > MAX_MADDE_KARAKTER:
        govde = (govde[:MAX_MADDE_KARAKTER]
                 + "\n\n[... madde metni uzunluk sınırından KESİLDİ — "
                   "kesilen kısımdaki şartlar için KONTROL_EDILEMEDI de ...]")
    return govde


def paket_icin_sut_lafzi(atc_kodu: str) -> Optional[Dict[str, Any]]:
    """Paketin `sut_lafzi` alanı: {"madde", "kaynak", "metin"} ya da None."""
    madde = madde_no_bul(atc_kodu)
    if not madde:
        return None
    metin = madde_metni_al(madde)
    if not metin:
        return None
    return {
        "madde": madde,
        "kaynak": ("Resmî SUT — mevzuat.gov.tr (Sağlık Uygulama Tebliği, "
                   "MevzuatNo 17229; yerel kopya docs/sut/SUT_tam_metin.txt)"),
        "metin": metin,
    }
