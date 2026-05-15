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

GECERLI_SONUCLAR = {TEYIT_UYGUN, TEYIT_UYGUN_DEGIL, TEYIT_SUPHELI}


def _db_yolu() -> Path:
    """sut_kontrol.db yolunu döndür (script dizini)."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return Path(script_dir) / _DB_DOSYA_ADI


_conn: sqlite3.Connection | None = None


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
}

ETIKET = {
    TEYIT_UYGUN: "UYGUN (teyit)",
    TEYIT_UYGUN_DEGIL: "UYGUN DEĞİL (teyit)",
    TEYIT_SUPHELI: "ŞÜPHELİ (teyit)",
}


def rozet(teyit_sonucu: str | None) -> str:
    if not teyit_sonucu:
        return ""
    return ROZET.get(teyit_sonucu, "")
