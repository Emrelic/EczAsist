"""SUT 4.2.28.A — Statin "eski rapora istinaden" kontrolü.

Statin raporu açıklamalarında doktor sıkça eski bir rapora atıfta bulunur:
    "16.02.2024 raporuna istinaden Ldl:194 mg/dl..."
    "Önceki rapor 12345 idame tedavisidir"
    "Devam raporu, 04.02.2024"

Bu modül:
  1. Rapor açıklamasında eski rapor referanslarını (tarih veya rapor no) bulur
  2. Botanik EOS'tan o referansa karşılık gelen raporu çeker
  3. Eski rapor için kontrol_statin() çağırarak SUT uygunluğunu değerlendirir
  4. Sonucu yeni satırın verdict'ine yansıtır

Kapsam: SADECE STATİN. Diğer SUT kontrolleri bu modülü kullanmaz.

DB: SADECE SELECT (botanik_db.py engelliyor). RaporAna tablosu okunur.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# 1. PATTERN TESPİTİ (rap_ack içinde tarih / rapor no)
# ─────────────────────────────────────────────────────────────────────

# Anahtar kelimeler — varlığı tarihi/numarayı daha güvenilir kılar
ANAHTAR_KELIMELER = (
    "istinaden", "dayanılarak", "dayanilarak",
    "yenilen", "yenileme",
    "önceki rapor", "onceki rapor", "bir önceki", "bir onceki",
    "eski rapor", "eski raporu",
    "idame tedavi", "idame tedavidir", "idame",
    "devam raporu", "devam tedavi", "devamı", "devami",
    "tarihli rapor", "tarihli rapora", "tarihli raporu",
    "tarihli",  # "16.02.2024 tarihli ..." — tarih referansının güçlü sinyali
)

# Tarih: dd.mm.yyyy / dd/mm/yyyy / dd-mm-yyyy (yıl 2 veya 4 hane)
_TARIH_RE = re.compile(r"\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})\b")

# Rapor numarası: "Rapor No: 12345", "Rap.No 12345", "R.No=12345"
_RAPOR_NO_RE = re.compile(
    r"(?:rapor\s*no|rap\.?\s*no|r\.?\s*no|"
    r"rapor\s*numara[sı]?|rapor\s*#)"
    r"\s*[:.\-=]?\s*(\d{4,15})",
    re.IGNORECASE,
)

# False-positive: "Ekleme=04/07/2025 10:16" sistem timestamp
_EKLEME_RE = re.compile(
    r"\(?\s*ekleme\s*[=:]\s*\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}"
    r"(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?\)?",
    re.IGNORECASE,
)


def eski_rapor_referanslarini_bul(
    rap_ack: str,
    mevcut_rapor_tarihleri: Optional[List[date]] = None,
) -> List[Dict[str, Any]]:
    """Rapor açıklamasında eski rapor referansı (tarih VEYA rapor no) ara.

    KURAL: Sadece "idame", "devam raporu", "tarihli rapor", "eski rapor",
    "istinaden" gibi anahtar kelimelerle birlikte geçen tarih/numara
    eski rapor referansı sayılır. Sadece tarih varsa (örn. "LDL: 142
    18.03.2025") referans olarak DÖNDÜRÜLMEZ — bunlar genelde reçete
    açıklamasında geçen ölçüm/inceleme tarihleridir.

    Returns:
        [
          {"tip": "tarih", "deger": date(2024,2,16), "raw": "16.02.2024",
           "anahtar_var": True},
          {"tip": "no",    "deger": "12345", "raw": "Rapor No: 12345",
           "anahtar_var": True},
        ]
        veya boş liste (anahtar kelime hiç yoksa)
    """
    if not rap_ack:
        return []

    metin = str(rap_ack)
    metin_lower = metin.lower()

    # 1. False-positive: "Ekleme=DD/MM/YYYY HH:MM" kalıplarını çıkar
    temiz = _EKLEME_RE.sub(" ", metin)

    # 2. Anahtar kelime varlığı — KISA-DEVRE: yoksa hiç tarih aramayalım,
    # çünkü kullanıcının net kuralı: SADECE idame/devam/istinaden/tarihli/
    # eski rapor ifadesi varsa eski rapora bakılsın.
    anahtar_var = any(k in metin_lower for k in ANAHTAR_KELIMELER)
    if not anahtar_var:
        # Kelime başına yakın bir tarih de yoksa (yakin_sinyal kontrolü için
        # gevşek check — aşağıda her tarih için ayrıca yapılır), hiç referans
        # döndürme.
        # Ek hızlı kontrol: temizde tarih yoksa zaten boş döner; gerek yok.
        return []

    referanslar: List[Dict[str, Any]] = []
    seen_tarih = set()
    seen_no = set()

    mevcut_set = set()
    if mevcut_rapor_tarihleri:
        for d in mevcut_rapor_tarihleri:
            if isinstance(d, datetime):
                d = d.date()
            if isinstance(d, date):
                mevcut_set.add(d)

    bugun = date.today()

    # 3. Tarih ara
    temiz_lower = temiz.lower()
    for m in _TARIH_RE.finditer(temiz):
        try:
            gun = int(m.group(1))
            ay = int(m.group(2))
            yil = int(m.group(3))
            if yil < 100:
                yil += 2000 if yil < 50 else 1900
            if not (1 <= ay <= 12 and 1 <= gun <= 31):
                continue
            d = date(yil, ay, gun)
        except (ValueError, OverflowError):
            continue
        # Sınır kontrolü: 1990 öncesi veya gelecek tarih → atla
        if d.year < 1990 or d > bugun:
            continue
        # Mevcut raporun kendi tarihi ile eşleşiyorsa atla
        if d in mevcut_set:
            continue
        if d in seen_tarih:
            continue
        seen_tarih.add(d)

        # Bu tarihin yakın çevresinde (sağında 30, solunda 30 karakter)
        # "tarihli" / "rapor" / "istinaden" gibi sinyal var mı? Olduğunda
        # tarihin eski rapor referansı olduğu kesinleşir.
        c_alt = max(0, m.start() - 30)
        c_ust = min(len(temiz_lower), m.end() + 30)
        cevre = temiz_lower[c_alt:c_ust]
        yakin_sinyal = any(s in cevre for s in (
            "tarihli", "rapor", "istinaden", "idame", "devam", "yenilen"
        ))

        referanslar.append({
            "tip": "tarih",
            "deger": d,
            "raw": m.group(0),
            "anahtar_var": anahtar_var or yakin_sinyal,
            "yakin_sinyal": yakin_sinyal,
        })

    # 4. Rapor numarası ara
    for m in _RAPOR_NO_RE.finditer(temiz):
        no = m.group(1).strip()
        if no in seen_no:
            continue
        seen_no.add(no)
        referanslar.append({
            "tip": "no",
            "deger": no,
            "raw": m.group(0),
            "anahtar_var": anahtar_var,
        })

    return referanslar


# ─────────────────────────────────────────────────────────────────────
# 2. BOTANİK EOS SORGUSU (eski rapor verilerini çek)
# ─────────────────────────────────────────────────────────────────────

def eski_rapor_eos_sorgula(
    db,
    musteri_id: int,
    referanslar: List[Dict[str, Any]],
    tolerans_gun: int = 3,
    haric_rapor_ana_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Verilen referanslar için Botanik EOS'tan eski rapor(ları) getir.

    Args:
        db: BotanikDb instance (sorgu_calistir metodu olan)
        musteri_id: hastanın MusteriId'si
        referanslar: eski_rapor_referanslarini_bul() çıktısı
        tolerans_gun: tarih için ± kaç gün tolerans
        haric_rapor_ana_id: bu rapor ID'sini SONUÇTAN hariç tut (yeni raporun
                            kendisi olabilir)

    Returns:
        [{rapor_id, rapor_no, takip_no, rapor_tarihi, aciklamalar,
          _icd_listesi, _rapor_kodlari, _referans_tip, _referans_deger}, ...]
    """
    if not db or not musteri_id or not referanslar:
        return []

    bulunan: Dict[Any, Dict[str, Any]] = {}  # rapor_id → dict

    tarihler = [r["deger"] for r in referanslar if r["tip"] == "tarih"]
    numaralar = [r["deger"] for r in referanslar if r["tip"] == "no"]

    sql_select = """
    SELECT
        ra.RaporAnaId             AS rapor_id,
        ra.RaporAnaRaporNo        AS rapor_no,
        ra.RaporAnaRaporTakipNo   AS takip_no,
        ra.RaporAnaRaporTarihi    AS rapor_tarihi,
        ra.RaporAnaAciklamalar    AS aciklamalar,
        ra.RaporAnaMusteriId      AS musteri_id
    FROM RaporAna ra
    """

    # 1. Tarih bazlı sorgular (her tarih için ±tolerans)
    for d in tarihler:
        d_alt = (d - timedelta(days=tolerans_gun)).isoformat()
        d_ust = (d + timedelta(days=tolerans_gun)).isoformat()
        sql = (
            sql_select
            + " WHERE ra.RaporAnaMusteriId = ?"
            + "   AND ra.RaporAnaRaporTarihi BETWEEN ? AND ?"
        )
        try:
            rows = db.sorgu_calistir(
                sql, (int(musteri_id), d_alt, d_ust))
        except Exception as e:
            logger.warning("Eski rapor tarih sorgusu fail (%s): %s", d, e)
            continue
        for r in rows or []:
            rid = r.get("rapor_id")
            if not rid or rid == haric_rapor_ana_id:
                continue
            if rid not in bulunan:
                rec = dict(r)
                rec["_referans_tip"] = "tarih"
                rec["_referans_deger"] = d.isoformat()
                bulunan[rid] = rec

    # 2. Rapor numarası bazlı sorgular
    for no in numaralar:
        sql = (
            sql_select
            + " WHERE ra.RaporAnaMusteriId = ?"
            + "   AND (LTRIM(RTRIM(CAST(ra.RaporAnaRaporNo AS VARCHAR(50)))) = ?"
            + "        OR LTRIM(RTRIM(CAST(ra.RaporAnaRaporTakipNo AS VARCHAR(50)))) = ?)"
        )
        try:
            rows = db.sorgu_calistir(
                sql, (int(musteri_id), str(no), str(no)))
        except Exception as e:
            logger.warning("Eski rapor no sorgusu fail (%s): %s", no, e)
            continue
        for r in rows or []:
            rid = r.get("rapor_id")
            if not rid or rid == haric_rapor_ana_id:
                continue
            if rid not in bulunan:
                rec = dict(r)
                rec["_referans_tip"] = "no"
                rec["_referans_deger"] = no
                bulunan[rid] = rec

    if not bulunan:
        return []

    # 3. ICD ve rapor kodlarını da getir (LDL/risk faktörü tespiti için)
    ids = list(bulunan.keys())
    ph = ",".join("?" * len(ids))
    sql_icd = f"""
    SELECT
        rrki.RRKIRaporAnaId    AS rapor_id,
        i.ICDKodu              AS icd_kodu,
        i.ICDAciklamasi        AS icd_aciklamasi,
        rk.RaporKodu           AS rapor_kodu,
        rk.RaporKodAciklama    AS rapor_kod_aciklama
    FROM RaporRaporKodlariICD rrki
    LEFT JOIN ICD i           ON i.ICDId       = rrki.RRKIICDId
    LEFT JOIN RaporKodlari rk ON rk.RaporKodId = rrki.RRKIRaporKodId
    WHERE rrki.RRKIRaporAnaId IN ({ph})
      AND (rrki.RRKISilme IS NULL OR rrki.RRKISilme = 0)
    """
    try:
        icd_rows = db.sorgu_calistir(sql_icd, tuple(ids))
    except Exception as e:
        logger.warning("Eski rapor ICD sorgusu fail: %s", e)
        icd_rows = []

    for ir in icd_rows or []:
        rid = ir.get("rapor_id")
        if rid not in bulunan:
            continue
        r = bulunan[rid]
        r.setdefault("_icd_listesi", [])
        r.setdefault("_rapor_kodlari", [])
        kod = (ir.get("icd_kodu") or "").strip()
        ack = (ir.get("icd_aciklamasi") or "").strip()
        if kod and ack:
            r["_icd_listesi"].append(f"{kod} {ack}")
        elif kod:
            r["_icd_listesi"].append(kod)
        rkod = (ir.get("rapor_kodu") or "").strip()
        if rkod:
            r["_rapor_kodlari"].append(rkod)

    # Tekilleştir
    for r in bulunan.values():
        r["_icd_listesi"] = list(dict.fromkeys(r.get("_icd_listesi", [])))
        r["_rapor_kodlari"] = list(dict.fromkeys(r.get("_rapor_kodlari", [])))

    return list(bulunan.values())


# ─────────────────────────────────────────────────────────────────────
# 3. ESKİ RAPOR İÇİN STATİN KONTROLÜ ÇALIŞTIR
# ─────────────────────────────────────────────────────────────────────

def _eski_rapor_ilac_sonuc_olustur(eski_rapor: Dict[str, Any],
                                    yeni_ilac_adi: str) -> Dict[str, Any]:
    """Eski rapor için kontrol_statin'in beklediği ilac_sonuc dict'i üret."""
    rapor_aciklamalari = []
    ack = (eski_rapor.get("aciklamalar") or "").strip()
    if ack:
        rapor_aciklamalari.append(ack)

    icd_listesi = eski_rapor.get("_icd_listesi", []) or []
    rapor_kodlari = eski_rapor.get("_rapor_kodlari", []) or []
    ilk_rapor_kodu = rapor_kodlari[0] if rapor_kodlari else ""

    return {
        "ilac_adi": yeni_ilac_adi or "",
        "rapor_kodu": ilk_rapor_kodu,
        "rapor_kodu_aciklama": "",
        "recete_teshisleri": list(icd_listesi),
        "rapor_aciklamalari": rapor_aciklamalari,
        "recete_aciklamalari": [],
        "mesaj_metni": "",
    }


def _ref_ozet(ref: Dict[str, Any]) -> str:
    """Referansı kısa string'e çevir: '16.02.2024' veya 'No:12345'."""
    if ref.get("tip") == "tarih":
        d = ref.get("deger")
        if isinstance(d, date):
            return d.strftime("%d.%m.%Y")
        return str(d)
    return f"No:{ref.get('deger', '?')}"


def _eski_rapor_ozet(rapor: Dict[str, Any]) -> str:
    """Eski raporu kısa string'e çevir: '16.02.2024' veya '16.02.2024 No:12345'."""
    rt = rapor.get("rapor_tarihi")
    if isinstance(rt, datetime):
        rt = rt.date()
    if isinstance(rt, date):
        rt_str = rt.strftime("%d.%m.%Y")
    elif isinstance(rt, str) and rt:
        rt_str = rt[:10]
    else:
        rt_str = "?"
    rn = (rapor.get("rapor_no") or "")
    if rn:
        return f"{rt_str} No:{rn}"
    return rt_str


def eski_rapor_statin_kontrol_calistir(
    db,
    musteri_id: int,
    rap_ack: str,
    yeni_ilac_adi: str,
    yeni_rapor_ana_id: Optional[int] = None,
    yeni_rapor_tarihi: Optional[date] = None,
    tolerans_gun: int = 3,
) -> Dict[str, Any]:
    """Bir statin satırı için 'eski rapora istinaden' kontrolünü tek seferde
    çalıştır.

    Returns:
        {
            "referans_var":        bool,
            "referanslar":         List[Dict],
            "bulunan_raporlar":    List[Dict],
            "eski_rapor_sonuclari": List[Dict],
            "final_durum":         "yok" | "uygun" | "uygun_degil" | "supheli"
                                    | "bulunamadi",
            "mesaj":               str (verdict_detay'a eklenecek özet),
        }
    """
    # Lazy import — circular dependency engellemek için
    from recete_kontrol.sut_kontrolleri import kontrol_statin
    from recete_kontrol.base_kontrol import KontrolSonucu

    sonuc: Dict[str, Any] = {
        "referans_var": False,
        "referanslar": [],
        "bulunan_raporlar": [],
        "eski_rapor_sonuclari": [],
        "final_durum": "yok",
        "mesaj": "",
    }

    mevcut_tarihler = [yeni_rapor_tarihi] if yeni_rapor_tarihi else []
    referanslar = eski_rapor_referanslarini_bul(rap_ack, mevcut_tarihler)
    if not referanslar:
        return sonuc

    sonuc["referans_var"] = True
    sonuc["referanslar"] = referanslar

    bulunan = eski_rapor_eos_sorgula(
        db, musteri_id, referanslar,
        tolerans_gun=tolerans_gun,
        haric_rapor_ana_id=yeni_rapor_ana_id,
    )
    sonuc["bulunan_raporlar"] = bulunan

    if not bulunan:
        ref_ozet = ", ".join(_ref_ozet(r) for r in referanslar[:3])
        sonuc["final_durum"] = "bulunamadi"
        sonuc["mesaj"] = (
            f"[ESKİ RAPOR {ref_ozet}] BULUNAMADI — "
            f"Ek Medula denetimi gerekir"
        )
        return sonuc

    # Her eski rapor için statin kontrolü çalıştır
    en_kritik = "uygun"  # uygun < supheli < uygun_degil (en_kritik)
    detay_satirlari: List[str] = []

    for eski in bulunan:
        eski_ilac_sonuc = _eski_rapor_ilac_sonuc_olustur(eski, yeni_ilac_adi)
        try:
            rapor = kontrol_statin(eski_ilac_sonuc)
        except Exception as e:
            logger.warning("Eski rapor statin kontrol hatası "
                            "(rapor_id=%s): %s", eski.get("rapor_id"), e)
            durum = "supheli"
            etiket = "ŞÜPHELİ (hata)"
            mesaj = f"Hata: {e}"
        else:
            if rapor.sonuc == KontrolSonucu.UYGUN:
                durum, etiket = "uygun", "UYGUN"
            elif rapor.sonuc == KontrolSonucu.UYGUN_DEGIL:
                durum, etiket = "uygun_degil", "UYGUN DEĞİL"
            else:
                durum, etiket = "supheli", "ŞÜPHELİ"
            mesaj = rapor.mesaj or ""

        detay_satirlari.append(
            f"[ESKİ RAPOR {_eski_rapor_ozet(eski)}] {etiket}"
            + (f" — {mesaj}" if mesaj else "")
        )
        sonuc["eski_rapor_sonuclari"].append({
            "rapor_id": eski.get("rapor_id"),
            "rapor_no": eski.get("rapor_no"),
            "rapor_tarihi": eski.get("rapor_tarihi"),
            "durum": durum,
            "etiket": etiket,
            "mesaj": mesaj,
        })

        # En kritik durum: uygun_degil > supheli > uygun
        if durum == "uygun_degil":
            en_kritik = "uygun_degil"
        elif durum == "supheli" and en_kritik != "uygun_degil":
            en_kritik = "supheli"

    sonuc["final_durum"] = en_kritik
    sonuc["mesaj"] = " | ".join(detay_satirlari)
    return sonuc
