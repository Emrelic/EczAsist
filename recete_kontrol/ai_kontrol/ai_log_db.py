"""AI Kontrol Çağrı Logu (yerel SQLite).

Her AI çağrısı (paket gönderim + cevap) burada loglanır:
    • Geriye dönük denetim (\"Bu reçete neden böyle denetlendi?\")
    • Maliyet takibi (input/output/cached token + USD maliyet)
    • Hata teşhisi (timeout, rate-limit, JSON parse hatası)

CLAUDE.md uyum: yerel SQLite — Botanik EOS'a YAZMA YOK.

Şema:
    ai_cagri_log(
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        tarih           TEXT,    -- ISO datetime
        ri_id           TEXT,    -- aylık modül satır kimliği (varsa)
        hasta_tc_hash   TEXT,    -- anonimleştirilmiş TC (SHA-256[:16])
        recete_no       TEXT,
        ilac_kodu       TEXT,
        ilac_adi        TEXT,
        sut_madde       TEXT,
        model           TEXT,
        input_tokens    INTEGER,
        output_tokens   INTEGER,
        cached_input_tokens INTEGER,
        cache_write_tokens  INTEGER,
        maliyet_usd     REAL,
        latency_ms      INTEGER,
        sonuc_etiketi   TEXT,    -- UYGUN / UYGUN_DEGIL / SUPHELI / KE / YETERSIZ_VERI
        guven_skoru     REAL,
        prompt_hash     TEXT,    -- prompt SHA-256[:16] (duplicate tespit)
        cevap_text      TEXT,    -- AI'ın ham cevabı (JSON string)
        hata            TEXT     -- hata mesajı (varsa)
    )
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DB_DOSYA_ADI = "ai_kontrol_log.db"
_TABLO = "ai_cagri_log"

_conn: sqlite3.Connection | None = None


def _db_yolu() -> Path:
    """Log DB yolunu döndür (proje kökü)."""
    proje_kok = Path(__file__).resolve().parents[2]
    return proje_kok / _DB_DOSYA_ADI


def _baglanti() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    _conn = sqlite3.connect(str(_db_yolu()), check_same_thread=False)
    _conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_TABLO} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            ri_id TEXT,
            hasta_tc_hash TEXT,
            recete_no TEXT,
            ilac_kodu TEXT,
            ilac_adi TEXT,
            sut_madde TEXT,
            model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cached_input_tokens INTEGER,
            cache_write_tokens INTEGER,
            maliyet_usd REAL,
            latency_ms INTEGER,
            sonuc_etiketi TEXT,
            guven_skoru REAL,
            prompt_hash TEXT,
            cevap_text TEXT,
            hata TEXT
        )
        """
    )
    _conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{_TABLO}_tarih ON {_TABLO}(tarih)"
    )
    _conn.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{_TABLO}_recete ON {_TABLO}(recete_no)"
    )
    _conn.commit()
    return _conn


def tc_hash(tc: str | int) -> str:
    """TC'yi SHA-256[:16] hex hash olarak döndür (anonimleştirme)."""
    if tc is None:
        return ""
    h = hashlib.sha256(str(tc).encode("utf-8")).hexdigest()
    return h[:16]


def cagri_kaydet(
    *,
    ri_id: str = "",
    hasta_tc: str = "",
    recete_no: str = "",
    ilac_kodu: str = "",
    ilac_adi: str = "",
    sut_madde: str = "",
    model: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
    cache_write_tokens: int = 0,
    maliyet_usd: float = 0.0,
    latency_ms: int = 0,
    sonuc_etiketi: str = "",
    guven_skoru: float = 0.0,
    prompt_hash: str = "",
    cevap_text: str = "",
    hata: str = "",
) -> int:
    """Bir AI çağrı kaydını ekle, kayıt ID'sini döndür."""
    try:
        conn = _baglanti()
        cur = conn.execute(
            f"""
            INSERT INTO {_TABLO}
              (tarih, ri_id, hasta_tc_hash, recete_no, ilac_kodu, ilac_adi,
               sut_madde, model, input_tokens, output_tokens,
               cached_input_tokens, cache_write_tokens, maliyet_usd, latency_ms,
               sonuc_etiketi, guven_skoru, prompt_hash, cevap_text, hata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                str(ri_id or ""),
                tc_hash(hasta_tc) if hasta_tc else "",
                str(recete_no or ""),
                str(ilac_kodu or ""),
                str(ilac_adi or ""),
                str(sut_madde or ""),
                str(model or ""),
                int(input_tokens or 0),
                int(output_tokens or 0),
                int(cached_input_tokens or 0),
                int(cache_write_tokens or 0),
                float(maliyet_usd or 0.0),
                int(latency_ms or 0),
                str(sonuc_etiketi or ""),
                float(guven_skoru or 0.0),
                str(prompt_hash or ""),
                str(cevap_text or "")[:50000],
                str(hata or ""),
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)
    except Exception as e:
        logger.error("AI log kayıt hatası: %s", e)
        return 0


def gunluk_ozet(tarih_iso: str | None = None) -> Dict[str, Any]:
    """Belirli bir günün özetini döndür (tarih_iso = 'YYYY-MM-DD', None → bugün)."""
    if tarih_iso is None:
        tarih_iso = datetime.now().strftime("%Y-%m-%d")
    try:
        conn = _baglanti()
        cur = conn.execute(
            f"""
            SELECT
              COUNT(*) AS cagri_sayisi,
              COALESCE(SUM(input_tokens), 0),
              COALESCE(SUM(output_tokens), 0),
              COALESCE(SUM(cached_input_tokens), 0),
              COALESCE(SUM(maliyet_usd), 0.0),
              COALESCE(AVG(latency_ms), 0)
            FROM {_TABLO}
            WHERE substr(tarih, 1, 10) = ?
            """,
            (tarih_iso,),
        )
        row = cur.fetchone()
        return {
            "tarih": tarih_iso,
            "cagri_sayisi": int(row[0] or 0),
            "input_tokens": int(row[1] or 0),
            "output_tokens": int(row[2] or 0),
            "cached_tokens": int(row[3] or 0),
            "maliyet_usd": float(row[4] or 0.0),
            "ortalama_latency_ms": int(row[5] or 0),
        }
    except Exception as e:
        logger.error("gunluk_ozet hatası: %s", e)
        return {"tarih": tarih_iso, "cagri_sayisi": 0, "maliyet_usd": 0.0}


def bugunku_cagri_sayisi() -> int:
    """Bugün yapılmış AI çağrı sayısı (günlük limit kontrolü için)."""
    return gunluk_ozet().get("cagri_sayisi", 0)


def son_cagrilar(limit: int = 100) -> list[Dict[str, Any]]:
    """Son N AI çağrı kaydını döndür (en yeni önce).

    UI'da log görüntüleyici için: tarih, reçete, ilaç, model, sonuc, maliyet,
    latency, hata, tam cevap. cevap_text uzun olabilir (50K char limit).
    """
    try:
        conn = _baglanti()
        cur = conn.execute(
            f"""SELECT id, tarih, ri_id, hasta_tc_hash, recete_no, ilac_kodu,
                       ilac_adi, sut_madde, model, input_tokens, output_tokens,
                       cached_input_tokens, cache_write_tokens, maliyet_usd,
                       latency_ms, sonuc_etiketi, guven_skoru, prompt_hash,
                       cevap_text, hata
                FROM {_TABLO}
                ORDER BY id DESC
                LIMIT ?""",
            (int(limit),),
        )
        kolonlar = [d[0] for d in cur.description]
        return [dict(zip(kolonlar, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error("son_cagrilar hatası: %s", e)
        return []


def cagri_detay(kayit_id: int) -> Optional[Dict[str, Any]]:
    """Tek bir çağrı kaydını ID ile getir."""
    try:
        conn = _baglanti()
        cur = conn.execute(
            f"SELECT * FROM {_TABLO} WHERE id = ?", (int(kayit_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        kolonlar = [d[0] for d in cur.description]
        return dict(zip(kolonlar, row))
    except Exception as e:
        logger.error("cagri_detay hatası: %s", e)
        return None
