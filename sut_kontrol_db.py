"""
SUT Kontrol Matrisi — kalıcı saklama (oturum_raporlari.db)

İki tablo:
  - sut_kontrol_isaretleri: hücre bazlı renkli işaretleme
  - sut_kontrol_notlari   : satır bazlı not

Tüm operasyonlar lokal SQLite üzerinde. Botanik DB'ye DOKUNULMAZ.
"""

import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Oturum raporları DB'siyle aynı yer (var olan kullanıcı tablosuyla aynı dosya)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_YOLU = os.path.join(_SCRIPT_DIR, "oturum_raporlari.db")


# Geçerli durum (renk) değerleri
DURUMLAR = ("yesil", "kirmizi", "sari", "turuncu", "beyaz")
# Hex kodlarıyla eşleşme (UI tarafı için)
DURUM_RENK = {
    "yesil":   "#C8E6C9",  # uygun
    "kirmizi": "#FFCDD2",  # uygun değil
    "sari":    "#FFF9C4",  # incelemede
    "turuncu": "#FFE0B2",  # şüpheli
    "beyaz":   "#FFFFFF",  # beklemede / temizle
}
DURUM_AD = {
    "yesil":   "Uygun",
    "kirmizi": "Uygun değil",
    "sari":    "İncelemede",
    "turuncu": "Şüpheli",
    "beyaz":   "Beklemede",
}


class SUTKontrolDB:
    """Lokal SQLite üzerinden SUT matris işaretleme + not yönetimi."""

    def __init__(self, db_yolu: str = _DB_YOLU):
        self.db_yolu = db_yolu
        self._tablolari_olustur()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.db_yolu)
        c.row_factory = sqlite3.Row
        return c

    def _tablolari_olustur(self):
        try:
            with self._conn() as c:
                c.execute("""
                    CREATE TABLE IF NOT EXISTS sut_kontrol_isaretleri (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rx_id INTEGER NOT NULL,
                        ri_id INTEGER NOT NULL,
                        kolon_adi TEXT NOT NULL,
                        durum TEXT NOT NULL,
                        kullanici_id INTEGER,
                        tarih TEXT NOT NULL,
                        UNIQUE(rx_id, ri_id, kolon_adi, kullanici_id)
                    )
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sut_isaret_rx
                    ON sut_kontrol_isaretleri(rx_id)
                """)
                c.execute("""
                    CREATE INDEX IF NOT EXISTS idx_sut_isaret_ri
                    ON sut_kontrol_isaretleri(ri_id)
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS sut_kontrol_notlari (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rx_id INTEGER NOT NULL,
                        ri_id INTEGER NOT NULL,
                        not_metin TEXT,
                        kullanici_id INTEGER,
                        tarih TEXT NOT NULL,
                        UNIQUE(rx_id, ri_id, kullanici_id)
                    )
                """)
                c.commit()
        except Exception as e:
            logger.error("SUT tabloları oluşturulamadı: %s", e)

    # ---------- İşaretleme ----------
    def isaret_koy(self, rx_id: int, ri_id: int, kolon_adi: str,
                    durum: str, kullanici_id: Optional[int] = None) -> bool:
        """
        Hücre işaretle. durum='beyaz' kayıt SİLER (sıfırlama).
        """
        if durum not in DURUMLAR:
            logger.warning("Geçersiz durum: %s", durum)
            return False
        try:
            with self._conn() as c:
                if durum == "beyaz":
                    c.execute("""
                        DELETE FROM sut_kontrol_isaretleri
                        WHERE rx_id=? AND ri_id=? AND kolon_adi=?
                          AND IFNULL(kullanici_id,0)=IFNULL(?,0)
                    """, (rx_id, ri_id, kolon_adi, kullanici_id))
                else:
                    tarih = datetime.now().isoformat(timespec="seconds")
                    c.execute("""
                        INSERT INTO sut_kontrol_isaretleri
                            (rx_id, ri_id, kolon_adi, durum, kullanici_id, tarih)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(rx_id, ri_id, kolon_adi, kullanici_id)
                        DO UPDATE SET durum=excluded.durum, tarih=excluded.tarih
                    """, (rx_id, ri_id, kolon_adi, durum, kullanici_id, tarih))
                c.commit()
            return True
        except Exception as e:
            logger.error("İşaret koyma hatası: %s", e)
            return False

    def isaretleri_getir(self, rx_id_list: List[int],
                          kullanici_id: Optional[int] = None,
                          tum_kullanicilar: bool = False
                          ) -> Dict[Tuple[int, int, str], str]:
        """
        Verilen RxId listesi için işaretleri tek dict olarak döner.
        Anahtar: (rx_id, ri_id, kolon_adi)  Değer: durum
        """
        if not rx_id_list:
            return {}
        try:
            with self._conn() as c:
                ph = ",".join("?" * len(rx_id_list))
                if tum_kullanicilar:
                    sql = f"""SELECT rx_id, ri_id, kolon_adi, durum, tarih
                              FROM sut_kontrol_isaretleri
                              WHERE rx_id IN ({ph})
                              ORDER BY tarih DESC"""
                    rows = c.execute(sql, rx_id_list).fetchall()
                else:
                    sql = f"""SELECT rx_id, ri_id, kolon_adi, durum, tarih
                              FROM sut_kontrol_isaretleri
                              WHERE rx_id IN ({ph})
                                AND IFNULL(kullanici_id,0)=IFNULL(?,0)"""
                    rows = c.execute(sql, [*rx_id_list, kullanici_id]).fetchall()
                # Tum kullanicilar modunda en yeni işaret kazanır (zaten ORDER BY var)
                sonuc = {}
                for r in rows:
                    anahtar = (r["rx_id"], r["ri_id"], r["kolon_adi"])
                    if anahtar not in sonuc:
                        sonuc[anahtar] = r["durum"]
                return sonuc
        except Exception as e:
            logger.error("İşaret okuma hatası: %s", e)
            return {}

    def isaret_temizle_satir(self, rx_id: int, ri_id: int,
                               kullanici_id: Optional[int] = None) -> int:
        """Bir satıra (RIId) ait tüm hücre işaretlerini temizle."""
        try:
            with self._conn() as c:
                cur = c.execute("""
                    DELETE FROM sut_kontrol_isaretleri
                    WHERE rx_id=? AND ri_id=?
                      AND IFNULL(kullanici_id,0)=IFNULL(?,0)
                """, (rx_id, ri_id, kullanici_id))
                c.commit()
                return cur.rowcount
        except Exception as e:
            logger.error("Satır temizleme hatası: %s", e)
            return 0

    # ---------- Not ----------
    def not_kaydet(self, rx_id: int, ri_id: int, not_metin: str,
                   kullanici_id: Optional[int] = None) -> bool:
        try:
            with self._conn() as c:
                tarih = datetime.now().isoformat(timespec="seconds")
                if not_metin and not_metin.strip():
                    c.execute("""
                        INSERT INTO sut_kontrol_notlari
                            (rx_id, ri_id, not_metin, kullanici_id, tarih)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(rx_id, ri_id, kullanici_id)
                        DO UPDATE SET not_metin=excluded.not_metin,
                                       tarih=excluded.tarih
                    """, (rx_id, ri_id, not_metin.strip(), kullanici_id, tarih))
                else:
                    # Boş not = sil
                    c.execute("""
                        DELETE FROM sut_kontrol_notlari
                        WHERE rx_id=? AND ri_id=?
                          AND IFNULL(kullanici_id,0)=IFNULL(?,0)
                    """, (rx_id, ri_id, kullanici_id))
                c.commit()
            return True
        except Exception as e:
            logger.error("Not kaydetme hatası: %s", e)
            return False

    def notlari_getir(self, rx_id_list: List[int],
                       kullanici_id: Optional[int] = None
                       ) -> Dict[Tuple[int, int], str]:
        """Verilen RxId'ler için (rx_id, ri_id) → not_metin sözlüğü."""
        if not rx_id_list:
            return {}
        try:
            with self._conn() as c:
                ph = ",".join("?" * len(rx_id_list))
                rows = c.execute(f"""
                    SELECT rx_id, ri_id, not_metin
                    FROM sut_kontrol_notlari
                    WHERE rx_id IN ({ph})
                      AND IFNULL(kullanici_id,0)=IFNULL(?,0)
                """, [*rx_id_list, kullanici_id]).fetchall()
                return {(r["rx_id"], r["ri_id"]): r["not_metin"] or ""
                        for r in rows}
        except Exception as e:
            logger.error("Not okuma hatası: %s", e)
            return {}

    # ---------- İstatistik ----------
    def ozet(self, kullanici_id: Optional[int] = None) -> Dict[str, int]:
        """Toplam işaret/not sayıları."""
        try:
            with self._conn() as c:
                if kullanici_id is not None:
                    isaret_sayim = c.execute("""
                        SELECT durum, COUNT(*) AS n
                        FROM sut_kontrol_isaretleri
                        WHERE IFNULL(kullanici_id,0)=?
                        GROUP BY durum
                    """, (kullanici_id,)).fetchall()
                    not_sayim = c.execute("""
                        SELECT COUNT(*) AS n FROM sut_kontrol_notlari
                        WHERE IFNULL(kullanici_id,0)=?
                    """, (kullanici_id,)).fetchone()
                else:
                    isaret_sayim = c.execute("""
                        SELECT durum, COUNT(*) AS n FROM sut_kontrol_isaretleri
                        GROUP BY durum
                    """).fetchall()
                    not_sayim = c.execute(
                        "SELECT COUNT(*) AS n FROM sut_kontrol_notlari"
                    ).fetchone()
                ozet = {r["durum"]: r["n"] for r in isaret_sayim}
                ozet["not"] = not_sayim["n"] if not_sayim else 0
                return ozet
        except Exception as e:
            logger.error("Özet hatası: %s", e)
            return {}


# Modül seviyesi singleton
_db: Optional[SUTKontrolDB] = None


def get_sut_db() -> SUTKontrolDB:
    global _db
    if _db is None:
        _db = SUTKontrolDB()
    return _db
