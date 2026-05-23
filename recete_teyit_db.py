"""Reçete teyit kayıt katmanı (sut_kontrol.db).

Aylık Reçete Kontrol modülünde kullanıcı tam ekran şema penceresinde
otomatik kontrol sonucunu (UYGUN / UYGUN_DEGIL / SUPHELI) gözden geçirip
TEYİT eder. Bu modül teyitleri SQLite'a yazar/okur.

Şema:
    recete_teyit(
        ri_id          PRIMARY KEY,   -- aylık modülün satır kimliği
        hasta_tc       TEXT,
        recete_no      TEXT,
        ilac_adi       TEXT,
        sut_kategorisi TEXT,
        kullanici      TEXT,
        tarih          TEXT,          -- ISO datetime
        teyit_sonucu   TEXT,          -- UYGUN / UYGUN_DEGIL / SUPHELI
        otomatik_sonuc TEXT,          -- buton anındaki otomatik 'verdict'
        not_metni      TEXT
    )

Tek satır = bir reçete kalemi. Tekrar teyit "üzerine yaz" mantığıyla
INSERT OR REPLACE ile son durumu saklar.
"""
from __future__ import annotations

import os
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_DOSYA_ADI = "sut_kontrol.db"
_TABLO = "recete_teyit"

TEYIT_UYGUN = "UYGUN"
TEYIT_UYGUN_DEGIL = "UYGUN_DEGIL"
TEYIT_SUPHELI = "SUPHELI"
# Diğer rapor bypass etiketi — aktif raporda eksik şart hastanın geçmiş
# raporundan tamamlandı; eczacı kontrol edip "bypass'i kabul ediyorum"
# diye manuel işaretleyebilir (otomatik kontrol verdict'ine ek olarak).
TEYIT_DIGER_RAPOR = "DIGER_RAPOR_UYGUN"

GECERLI_SONUCLAR = {TEYIT_UYGUN, TEYIT_UYGUN_DEGIL, TEYIT_SUPHELI,
                     TEYIT_DIGER_RAPOR}


def _db_yolu() -> Path:
    """sut_kontrol.db yolunu döndür (script dizini)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return Path(script_dir) / _DB_DOSYA_ADI


_conn: sqlite3.Connection | None = None


# AI Kontrol sütunları (Faz 1 — kullanıcı isteği 2026-05-21)
# AI butonunun ürettiği sonuç + açıklama bu sütunlara yazılır.
_AI_SUTUNLARI = [
    ("ai_sonuc",     "TEXT"),   # UYGUN / UYGUN_DEGIL / SUPHELI / KE / vs.
    ("ai_aciklama",  "TEXT"),   # AI'ın özet+detay açıklama metni
    ("ai_model",     "TEXT"),   # claude-sonnet-4-6 / claude-opus-4-7
    ("ai_tarih",     "TEXT"),   # AI çağrı tarihi (ISO)
    ("ai_guven",     "REAL"),   # 0.0–1.0
    ("ai_sut_ref",   "TEXT"),   # SUT madde referansı
]


def _ai_sutunlari_ekle(conn: sqlite3.Connection) -> None:
    """Mevcut tabloya AI sütunlarını ekle (yoksa)."""
    try:
        cur = conn.execute(f"PRAGMA table_info({_TABLO})")
        mevcut = {row[1] for row in cur.fetchall()}
        for ad, tip in _AI_SUTUNLARI:
            if ad not in mevcut:
                conn.execute(f"ALTER TABLE {_TABLO} ADD COLUMN {ad} {tip}")
        conn.commit()
    except Exception as e:
        logger.warning("AI sütun migration: %s", e)


def _baglanti() -> sqlite3.Connection:
    """Lazy connection — ilk çağrıda tabloyu da oluşturur."""
    global _conn
    if _conn is not None:
        return _conn
    try:
        _conn = sqlite3.connect(str(_db_yolu()), check_same_thread=False)
        _conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_TABLO} (
                ri_id          TEXT PRIMARY KEY,
                hasta_tc       TEXT,
                recete_no      TEXT,
                ilac_adi       TEXT,
                sut_kategorisi TEXT,
                kullanici      TEXT,
                tarih          TEXT,
                teyit_sonucu   TEXT,
                otomatik_sonuc TEXT,
                not_metni      TEXT
            )
            """
        )
        _conn.commit()
        _ai_sutunlari_ekle(_conn)
        logger.info("recete_teyit DB hazır: %s", _db_yolu())
    except Exception as e:
        logger.error("recete_teyit DB açılamadı: %s", e)
        raise
    return _conn


def teyit_kaydet(
    ri_id: str,
    teyit_sonucu: str,
    *,
    hasta_tc: str = "",
    recete_no: str = "",
    ilac_adi: str = "",
    sut_kategorisi: str = "",
    kullanici: str = "",
    otomatik_sonuc: str = "",
    not_metni: str = "",
) -> bool:
    """Bir reçete kalemi için teyit kaydet (üzerine yazar).

    Returns: başarı → True
    """
    if not ri_id:
        logger.warning("teyit_kaydet: ri_id boş")
        return False
    if teyit_sonucu not in GECERLI_SONUCLAR:
        logger.warning("teyit_kaydet: geçersiz sonuç '%s'", teyit_sonucu)
        return False
    try:
        conn = _baglanti()
        conn.execute(
            f"""
            INSERT OR REPLACE INTO {_TABLO}
                (ri_id, hasta_tc, recete_no, ilac_adi, sut_kategorisi,
                 kullanici, tarih, teyit_sonucu, otomatik_sonuc, not_metni)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(ri_id),
                str(hasta_tc or ""),
                str(recete_no or ""),
                str(ilac_adi or ""),
                str(sut_kategorisi or ""),
                str(kullanici or ""),
                datetime.now().isoformat(timespec="seconds"),
                teyit_sonucu,
                str(otomatik_sonuc or ""),
                str(not_metni or ""),
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("teyit_kaydet hatası: %s", e)
        return False


def teyit_oku(ri_id: str) -> dict | None:
    """Tek bir ri_id için son teyit kaydını döndür (yoksa None)."""
    if not ri_id:
        return None
    try:
        conn = _baglanti()
        cur = conn.execute(
            f"SELECT ri_id, hasta_tc, recete_no, ilac_adi, sut_kategorisi, "
            f"kullanici, tarih, teyit_sonucu, otomatik_sonuc, not_metni "
            f"FROM {_TABLO} WHERE ri_id=?",
            (str(ri_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "ri_id": row[0],
            "hasta_tc": row[1],
            "recete_no": row[2],
            "ilac_adi": row[3],
            "sut_kategorisi": row[4],
            "kullanici": row[5],
            "tarih": row[6],
            "teyit_sonucu": row[7],
            "otomatik_sonuc": row[8],
            "not_metni": row[9],
        }
    except Exception as e:
        logger.error("teyit_oku hatası: %s", e)
        return None


def teyit_haritasi(ri_idler: list[str] | None = None) -> dict[str, str]:
    """Birden fazla ri_id için teyit_sonucu eşlemesi döndür.

    ri_idler verilmezse TÜM kayıtları döndürür.
    Returns: {ri_id: teyit_sonucu}
    """
    try:
        conn = _baglanti()
        if ri_idler is None:
            cur = conn.execute(
                f"SELECT ri_id, teyit_sonucu FROM {_TABLO}"
            )
        else:
            if not ri_idler:
                return {}
            placeholders = ",".join("?" for _ in ri_idler)
            cur = conn.execute(
                f"SELECT ri_id, teyit_sonucu FROM {_TABLO} "
                f"WHERE ri_id IN ({placeholders})",
                tuple(str(x) for x in ri_idler),
            )
        return {str(r[0]): r[1] for r in cur.fetchall() if r[1]}
    except Exception as e:
        logger.error("teyit_haritasi hatası: %s", e)
        return {}


def teyit_sil(ri_id: str) -> bool:
    """Bir teyit kaydını sil."""
    if not ri_id:
        return False
    try:
        conn = _baglanti()
        conn.execute(f"DELETE FROM {_TABLO} WHERE ri_id=?", (str(ri_id),))
        conn.commit()
        return True
    except Exception as e:
        logger.error("teyit_sil hatası: %s", e)
        return False


# Rozet ve etiket yardımcıları
ROZET = {
    TEYIT_UYGUN: "✓",
    TEYIT_UYGUN_DEGIL: "✗",
    TEYIT_SUPHELI: "?",
    TEYIT_DIGER_RAPOR: "ℹ",
}

ETIKET = {
    TEYIT_UYGUN: "UYGUN (teyit)",
    TEYIT_UYGUN_DEGIL: "UYGUN DEĞİL (teyit)",
    TEYIT_SUPHELI: "ŞÜPHELİ (teyit)",
    TEYIT_DIGER_RAPOR: "DİĞER RAPOR UYGUN (teyit)",
}


def rozet(teyit_sonucu: str | None) -> str:
    if not teyit_sonucu:
        return ""
    return ROZET.get(teyit_sonucu, "")


# ──────────────────────────────────────────────────────────────────────
# AI Kontrol sonucu yazma/okuma (Faz 1)
# ──────────────────────────────────────────────────────────────────────

def ai_sonuc_kaydet(
    ri_id: str,
    *,
    ai_sonuc: str,
    ai_aciklama: str = "",
    ai_model: str = "",
    ai_guven: float = 0.0,
    ai_sut_ref: str = "",
    hasta_tc: str = "",
    recete_no: str = "",
    ilac_adi: str = "",
    kullanici: str = "",
) -> bool:
    """AI kontrol sonucunu kaydet (mevcut kaydı koruyup AI alanlarını günceller)."""
    if not ri_id:
        return False
    try:
        conn = _baglanti()
        # UPSERT: kayıt yoksa oluştur, varsa AI alanlarını güncelle
        conn.execute(
            f"""
            INSERT INTO {_TABLO}
              (ri_id, hasta_tc, recete_no, ilac_adi, kullanici, tarih,
               ai_sonuc, ai_aciklama, ai_model, ai_tarih, ai_guven, ai_sut_ref)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ri_id) DO UPDATE SET
              ai_sonuc=excluded.ai_sonuc,
              ai_aciklama=excluded.ai_aciklama,
              ai_model=excluded.ai_model,
              ai_tarih=excluded.ai_tarih,
              ai_guven=excluded.ai_guven,
              ai_sut_ref=excluded.ai_sut_ref
            """,
            (
                str(ri_id),
                str(hasta_tc or ""),
                str(recete_no or ""),
                str(ilac_adi or ""),
                str(kullanici or ""),
                datetime.now().isoformat(timespec="seconds"),
                str(ai_sonuc or ""),
                str(ai_aciklama or "")[:50000],
                str(ai_model or ""),
                datetime.now().isoformat(timespec="seconds"),
                float(ai_guven or 0.0),
                str(ai_sut_ref or ""),
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error("ai_sonuc_kaydet hatası: %s", e)
        return False


def ai_sonuc_oku(ri_id: str) -> dict | None:
    """Bir ri_id için kayıtlı AI sonucunu döndür."""
    if not ri_id:
        return None
    try:
        conn = _baglanti()
        cur = conn.execute(
            f"""SELECT ai_sonuc, ai_aciklama, ai_model, ai_tarih,
                       ai_guven, ai_sut_ref
                FROM {_TABLO} WHERE ri_id=?""",
            (str(ri_id),),
        )
        row = cur.fetchone()
        if not row or not row[0]:
            return None
        return {
            "ai_sonuc": row[0],
            "ai_aciklama": row[1] or "",
            "ai_model": row[2] or "",
            "ai_tarih": row[3] or "",
            "ai_guven": row[4] or 0.0,
            "ai_sut_ref": row[5] or "",
        }
    except Exception as e:
        logger.error("ai_sonuc_oku hatası: %s", e)
        return None


def ai_sonuc_haritasi(ri_idler: list[str] | None = None) -> dict[str, dict]:
    """Birden fazla ri_id için AI sonucu haritası döndür."""
    try:
        conn = _baglanti()
        if ri_idler is None:
            cur = conn.execute(
                f"""SELECT ri_id, ai_sonuc, ai_aciklama, ai_model,
                           ai_tarih, ai_guven, ai_sut_ref
                    FROM {_TABLO}
                    WHERE ai_sonuc IS NOT NULL AND ai_sonuc <> ''"""
            )
        else:
            if not ri_idler:
                return {}
            placeholders = ",".join("?" for _ in ri_idler)
            cur = conn.execute(
                f"""SELECT ri_id, ai_sonuc, ai_aciklama, ai_model,
                           ai_tarih, ai_guven, ai_sut_ref
                    FROM {_TABLO}
                    WHERE ri_id IN ({placeholders})
                      AND ai_sonuc IS NOT NULL AND ai_sonuc <> ''""",
                tuple(str(x) for x in ri_idler),
            )
        return {
            str(r[0]): {
                "ai_sonuc": r[1],
                "ai_aciklama": r[2] or "",
                "ai_model": r[3] or "",
                "ai_tarih": r[4] or "",
                "ai_guven": r[5] or 0.0,
                "ai_sut_ref": r[6] or "",
            }
            for r in cur.fetchall() if r[1]
        }
    except Exception as e:
        logger.error("ai_sonuc_haritasi hatası: %s", e)
        return {}
