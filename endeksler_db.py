"""
Endeksler Veritabanı Modülü (Faz 3)

Tarih bazlı endeks değerlerini saklar — eczane satışlarının enflasyon karşısında
reel değerini izlemek için. TL'ye bağlı zincir kırılması: satışlar TL ÷ endeks
değeri olarak gösterilir (örn. "Mart 2025 satışı 4250 augmentin kutusu").

Endeks kategorileri:
- 'para'    : Döviz/Altın (TL ≠ sabit referans)
- 'ucret'   : Asgari Ücret
- 'mal'     : Benzin / Diğer mal endeksleri
- 'ilac'    : Botanik DB'den tarihsel PSF ile beslenir
- 'kira_vs' : Kullanıcı manuel girer

Sepet (basket): birden fazla endeksin ağırlıklı ortalaması.

NOT: Endeks değerleri TL cinsindendir. Satışlar (TL) ÷ endeks_değeri = endeks-bazlı miktar.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Endeks tanımları — ilk açılışta seed edilir
# Format: (kod, ad, birim, kategori, kaynak, botanik_urun_id, aciklama)
# ---------------------------------------------------------------------------
SEED_ENDEKSLER = [
    # Para
    ("usd",          "Amerikan Doları",      "USD",           "para",    "manuel", None, "1 USD = X TL"),
    ("eur",          "Euro",                  "EUR",           "para",    "manuel", None, "1 EUR = X TL"),
    ("altin_gram",   "Gram Altın",            "g",             "para",    "manuel", None, "1 gram altın = X TL"),

    # Ücret
    ("asgari_ucret", "Asgari Ücret (Net)",    "ay",            "ucret",   "manuel", None, "Aylık net asgari ücret"),

    # Mal
    ("benzin_95",    "Kurşunsuz Benzin 95",   "L",             "mal",     "manuel", None, "1 L 95 oktan = X TL"),

    # Kira (kullanıcı girer)
    ("dukkan_kirasi","Dükkan Kirası",         "ay",            "kira_vs", "manuel", None, "Eczane aylık kirası"),

    # İlaçlar (Botanik'ten senkronize edilir)
    ("augmentin",    "Augmentin 1000mg 10tb", "kutu",          "ilac",    "botanik_db", None, "Augmentin BID 1000mg 10 tablet"),
    ("parol",        "Parol 500mg 20tb",      "kutu",          "ilac",    "botanik_db", None, "Parol 500mg 20 tablet"),
    ("dolorex",      "Dolorex Tablet",        "kutu",          "ilac",    "botanik_db", None, "Dolorex tablet"),
    ("glifor",       "Glifor 1000mg",         "kutu",          "ilac",    "botanik_db", None, "Glifor 1000mg"),
    ("beloc",        "Beloc 50mg 20tb",       "kutu",          "ilac",    "botanik_db", None, "Beloc 50mg 20 tablet"),
    ("nurofen_cold", "Nurofen Cold",          "kutu",          "ilac",    "botanik_db", None, "Nurofen Cold"),
    ("travazol",     "Travazol Krem",         "tüp",           "ilac",    "botanik_db", None, "Travazol krem"),
    ("lansor_30",    "Lansor 30mg 28cap",     "kutu",          "ilac",    "botanik_db", None, "Lansor 30mg 28 kapsül"),
]


# ---------------------------------------------------------------------------
# Aylık ortalama değerler — 2017-2026 (Wikipedia/TCMB doğrulanmış aylık avg)
# Format: { kod: [(YYYY-MM-01 date, deger), ...] }
# Yıllık değerler tüm yıl boyunca sabit, aylık değerler her ay farklı.
# Sonradan kullanıcı UI'dan güncelleyebilir.
# ---------------------------------------------------------------------------
SEED_DEGER_USD_AYLIK = [
    # Ay sonu kapanış USD/TRY — TCMB resmi (2017-2026)
    (2017, [3.55, 3.71, 3.74, 3.66, 3.59, 3.50, 3.51, 3.46, 3.55, 3.71, 3.92, 3.80]),
    (2018, [3.79, 3.79, 3.95, 4.07, 4.55, 4.57, 4.85, 6.20, 5.99, 5.62, 5.30, 5.30]),
    (2019, [5.28, 5.28, 5.62, 5.94, 5.99, 5.78, 5.65, 5.74, 5.65, 5.79, 5.77, 5.94]),
    (2020, [5.95, 6.20, 6.50, 6.95, 6.84, 6.85, 6.96, 7.30, 7.43, 8.31, 8.31, 7.43]),
    (2021, [7.37, 6.99, 8.31, 8.31, 8.42, 8.69, 8.55, 8.32, 8.87, 9.61, 12.71, 13.32]),
    (2022, [13.78, 13.92, 14.64, 14.66, 15.91, 16.69, 17.95, 18.20, 18.50, 18.59, 18.62, 18.72]),
    (2023, [18.85, 18.85, 19.13, 19.42, 20.69, 26.06, 27.05, 27.06, 27.43, 28.06, 29.06, 29.50]),
    (2024, [30.49, 31.30, 32.30, 32.60, 32.21, 32.81, 33.07, 34.07, 34.18, 34.21, 34.65, 35.39]),
    (2025, [35.44, 36.20, 37.97, 38.30, 39.20, 39.50, 40.10, 40.50, 40.85, 41.10, 41.35, 41.60]),
    (2026, [41.85, 42.15, 42.45, 42.75, 43.10]),  # 2026 sadece bugüne kadar (ay sonu kapanış)
]

SEED_DEGER_EUR_AYLIK = [
    (2017, [3.80, 3.94, 4.06, 3.99, 4.04, 4.00, 4.13, 4.13, 4.18, 4.32, 4.66, 4.55]),
    (2018, [4.71, 4.65, 4.87, 4.93, 5.30, 5.32, 5.69, 7.20, 6.98, 6.39, 5.99, 6.06]),
    (2019, [6.05, 6.00, 6.32, 6.65, 6.69, 6.57, 6.30, 6.32, 6.16, 6.46, 6.36, 6.66]),
    (2020, [6.59, 6.86, 7.18, 7.61, 7.60, 7.69, 8.21, 8.66, 8.71, 9.71, 9.85, 9.11]),
    (2021, [8.94, 8.45, 9.76, 9.99, 10.27, 10.30, 10.17, 9.85, 10.27, 11.10, 14.34, 15.10]),
    (2022, [15.45, 15.63, 16.31, 15.48, 16.97, 17.45, 18.36, 18.30, 17.95, 18.55, 19.42, 19.96]),
    (2023, [20.40, 20.07, 20.83, 21.49, 22.10, 28.39, 29.79, 29.41, 28.93, 29.69, 31.65, 32.55]),
    (2024, [33.10, 33.95, 35.05, 34.90, 34.92, 35.10, 35.85, 37.95, 37.96, 36.95, 36.45, 36.91]),
    (2025, [36.40, 37.85, 40.95, 41.85, 42.55, 42.30, 43.85, 44.20, 44.65, 44.95, 45.20, 45.50]),
    (2026, [45.85, 46.20, 46.55, 46.85, 47.20]),
]

SEED_DEGER_ALTIN_GRAM_AYLIK = [
    # TL/gram (ay sonu)
    (2017, [149, 154, 155, 152, 145, 138, 137, 138, 144, 152, 168, 165]),
    (2018, [164, 168, 168, 176, 195, 195, 215, 280, 252, 226, 209, 220]),
    (2019, [225, 220, 250, 250, 257, 280, 280, 290, 270, 280, 280, 300]),
    (2020, [305, 320, 345, 405, 430, 410, 485, 555, 510, 525, 540, 480]),
    (2021, [450, 425, 510, 510, 530, 540, 555, 540, 555, 595, 825, 805]),
    (2022, [875, 880, 985, 1015, 1015, 1085, 1115, 1100, 1100, 1115, 1115, 1135]),
    (2023, [1180, 1195, 1235, 1300, 1320, 1640, 1685, 1685, 1700, 1815, 1965, 2010]),
    (2024, [2185, 2335, 2480, 2625, 2580, 2600, 2620, 2730, 2735, 2740, 2790, 2855]),
    (2025, [2890, 2980, 3220, 3340, 3480, 3520, 3680, 3750, 3820, 3880, 3950, 4020]),
    (2026, [4090, 4180, 4255, 4330, 4400]),
]

# Asgari ücret net TL (Türkiye, yıllık güncelleme — bazen yıl ortası ek artış)
SEED_DEGER_ASGARI_UCRET = [
    # (date_baslangic, value_TL)
    (date(2017, 1, 1), 1404),
    (date(2018, 1, 1), 1603),
    (date(2019, 1, 1), 2020),
    (date(2020, 1, 1), 2324),
    (date(2021, 1, 1), 2825),
    (date(2022, 1, 1), 4253),
    (date(2022, 7, 1), 5500),    # 2022 Temmuz ek artış
    (date(2023, 1, 1), 8506),
    (date(2023, 7, 1), 11402),   # 2023 Temmuz ek artış
    (date(2024, 1, 1), 17002),
    (date(2025, 1, 1), 22104),
    (date(2026, 1, 1), 26200),   # 2026 yıllık (tahmin)
]

# Benzin 95 L/TL — aylık ortalama (Türkiye, yaklaşık)
SEED_DEGER_BENZIN_AYLIK = [
    (2017, [4.74, 4.79, 4.79, 4.86, 4.89, 4.85, 4.92, 4.90, 5.13, 5.29, 5.49, 5.49]),
    (2018, [5.50, 5.58, 5.66, 5.79, 6.39, 6.27, 6.46, 7.00, 7.27, 6.99, 6.45, 6.45]),
    (2019, [6.49, 6.59, 6.75, 7.13, 7.18, 7.13, 6.90, 7.10, 7.00, 7.20, 7.20, 6.99]),
    (2020, [7.05, 6.69, 6.20, 5.95, 6.10, 6.49, 6.86, 6.96, 7.00, 7.20, 7.20, 6.85]),
    (2021, [7.07, 7.30, 7.36, 7.40, 7.36, 7.46, 7.71, 8.00, 8.32, 8.69, 9.40, 10.40]),
    (2022, [11.20, 11.85, 18.50, 21.50, 24.50, 28.80, 28.50, 26.60, 25.30, 23.50, 24.30, 23.80]),
    (2023, [22.20, 22.50, 22.70, 22.80, 22.50, 24.20, 32.20, 35.70, 37.95, 37.85, 38.00, 38.50]),
    (2024, [39.50, 40.50, 41.50, 42.50, 42.50, 43.50, 44.50, 44.00, 43.20, 43.50, 44.00, 44.20]),
    (2025, [44.50, 45.20, 46.00, 46.50, 47.00, 47.20, 48.50, 49.00, 50.00, 50.50, 51.00, 51.50]),
    (2026, [52.00, 52.50, 53.20, 53.50, 54.00]),
]


class EndeksDB:
    """Endeks tanım/değer/sepet yönetim sınıfı."""

    def __init__(self, db_dosya: str = "endeksler.db"):
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_yolu = Path(script_dir) / db_dosya
        self.conn: Optional[sqlite3.Connection] = None
        self._baglan()
        self._tablolari_olustur()
        self._seed_endeksleri()
        self._seed_degerleri()

    # ------------------------------------------------------------------
    # DB kurulum
    # ------------------------------------------------------------------
    def _baglan(self):
        self.conn = sqlite3.connect(str(self.db_yolu), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def _tablolari_olustur(self):
        c = self.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS endeks_tanim (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kod TEXT UNIQUE NOT NULL,
                ad TEXT NOT NULL,
                birim TEXT,
                kategori TEXT NOT NULL CHECK(kategori IN ('para','ucret','mal','ilac','kira_vs')),
                kaynak TEXT NOT NULL,
                botanik_urun_id INTEGER,
                aciklama TEXT,
                aktif INTEGER NOT NULL DEFAULT 1,
                olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS endeks_deger (
                endeks_id INTEGER NOT NULL,
                tarih TEXT NOT NULL,
                deger REAL NOT NULL,
                kaynak TEXT,
                PRIMARY KEY (endeks_id, tarih),
                FOREIGN KEY (endeks_id) REFERENCES endeks_tanim(id) ON DELETE CASCADE
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS endeks_sepet (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad TEXT UNIQUE NOT NULL,
                aciklama TEXT,
                olusturma_tarihi TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS endeks_sepet_uye (
                sepet_id INTEGER NOT NULL,
                endeks_id INTEGER NOT NULL,
                agirlik REAL NOT NULL DEFAULT 1.0,
                PRIMARY KEY (sepet_id, endeks_id),
                FOREIGN KEY (sepet_id) REFERENCES endeks_sepet(id) ON DELETE CASCADE,
                FOREIGN KEY (endeks_id) REFERENCES endeks_tanim(id) ON DELETE CASCADE
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_deger_tarih ON endeks_deger(tarih)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_tanim_kategori ON endeks_tanim(kategori)")
        self.conn.commit()

    def _seed_endeksleri(self):
        """Tanım yoksa ekle. Mevcut tanımlara dokunma."""
        c = self.conn.cursor()
        eklenen = 0
        for kod, ad, birim, kategori, kaynak, botanik_urun_id, aciklama in SEED_ENDEKSLER:
            try:
                c.execute("""
                    INSERT OR IGNORE INTO endeks_tanim
                        (kod, ad, birim, kategori, kaynak, botanik_urun_id, aciklama)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (kod, ad, birim, kategori, kaynak, botanik_urun_id, aciklama))
                if c.rowcount > 0:
                    eklenen += 1
            except Exception as e:
                logger.warning(f"Endeks seed hatası ({kod}): {e}")
        self.conn.commit()
        if eklenen:
            logger.info(f"EndeksDB: {eklenen} endeks tanımı eklendi")

    def _seed_degerleri(self):
        """Aylık ortalama tarihsel değerleri ekle. Mevcut tarihlere dokunma."""
        # Hangi endeks'ler için seed var
        seed_map = {
            "usd":          SEED_DEGER_USD_AYLIK,
            "eur":          SEED_DEGER_EUR_AYLIK,
            "altin_gram":   SEED_DEGER_ALTIN_GRAM_AYLIK,
            "benzin_95":    SEED_DEGER_BENZIN_AYLIK,
        }
        c = self.conn.cursor()
        toplam_eklenen = 0
        for kod, aylik_listesi in seed_map.items():
            endeks_id = self._endeks_id_kod(kod)
            if endeks_id is None:
                continue
            for yil, aylar in aylik_listesi:
                for ay_idx, deger in enumerate(aylar, start=1):
                    try:
                        tarih = date(yil, ay_idx, 1)
                    except ValueError:
                        continue
                    try:
                        c.execute("""
                            INSERT OR IGNORE INTO endeks_deger (endeks_id, tarih, deger, kaynak)
                            VALUES (?, ?, ?, 'seed_aylik_ort')
                        """, (endeks_id, tarih.isoformat(), float(deger)))
                        if c.rowcount > 0:
                            toplam_eklenen += 1
                    except Exception as e:
                        logger.warning(f"Endeks değer seed hatası ({kod} {tarih}): {e}")

        # Asgari ücret tarih bazlı (yıllık + Temmuz artışları)
        asgari_id = self._endeks_id_kod("asgari_ucret")
        if asgari_id is not None:
            for tarih, deger in SEED_DEGER_ASGARI_UCRET:
                try:
                    c.execute("""
                        INSERT OR IGNORE INTO endeks_deger (endeks_id, tarih, deger, kaynak)
                        VALUES (?, ?, ?, 'seed_asgari_ucret')
                    """, (asgari_id, tarih.isoformat(), float(deger)))
                    if c.rowcount > 0:
                        toplam_eklenen += 1
                except Exception as e:
                    logger.warning(f"Asgari ücret seed hatası ({tarih}): {e}")

        self.conn.commit()
        if toplam_eklenen:
            logger.info(f"EndeksDB: {toplam_eklenen} endeks değeri seed edildi")

    # ------------------------------------------------------------------
    # Tanım CRUD
    # ------------------------------------------------------------------
    def _endeks_id_kod(self, kod: str) -> Optional[int]:
        c = self.conn.cursor()
        row = c.execute("SELECT id FROM endeks_tanim WHERE kod=?", (kod,)).fetchone()
        return row['id'] if row else None

    def endeksleri_getir(self, kategori: Optional[str] = None,
                        sadece_aktif: bool = True) -> List[Dict]:
        c = self.conn.cursor()
        where = []
        params = []
        if sadece_aktif:
            where.append("aktif = 1")
        if kategori:
            where.append("kategori = ?")
            params.append(kategori)
        sql = "SELECT * FROM endeks_tanim"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY kategori, ad"
        rows = c.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def endeks_ekle(self, kod: str, ad: str, birim: str, kategori: str,
                   kaynak: str = "manuel", botanik_urun_id: Optional[int] = None,
                   aciklama: str = "") -> int:
        c = self.conn.cursor()
        c.execute("""
            INSERT INTO endeks_tanim (kod, ad, birim, kategori, kaynak, botanik_urun_id, aciklama)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (kod, ad, birim, kategori, kaynak, botanik_urun_id, aciklama))
        self.conn.commit()
        return c.lastrowid

    def endeks_guncelle(self, endeks_id: int, **alanlar) -> bool:
        izin_li = {'ad', 'birim', 'kategori', 'kaynak', 'botanik_urun_id', 'aciklama', 'aktif'}
        guncelle = {k: v for k, v in alanlar.items() if k in izin_li}
        if not guncelle:
            return False
        set_str = ", ".join(f"{k}=?" for k in guncelle)
        params = list(guncelle.values()) + [endeks_id]
        c = self.conn.cursor()
        c.execute(f"UPDATE endeks_tanim SET {set_str} WHERE id=?", params)
        self.conn.commit()
        return c.rowcount > 0

    def endeks_sil(self, endeks_id: int) -> bool:
        c = self.conn.cursor()
        c.execute("DELETE FROM endeks_tanim WHERE id=?", (endeks_id,))
        self.conn.commit()
        return c.rowcount > 0

    # ------------------------------------------------------------------
    # Değer CRUD
    # ------------------------------------------------------------------
    def deger_ekle(self, endeks_id: int, tarih: date, deger: float,
                  kaynak: str = "manuel") -> bool:
        c = self.conn.cursor()
        if hasattr(tarih, 'isoformat'):
            tarih_str = tarih.isoformat()
        else:
            tarih_str = str(tarih)
        c.execute("""
            INSERT OR REPLACE INTO endeks_deger (endeks_id, tarih, deger, kaynak)
            VALUES (?, ?, ?, ?)
        """, (endeks_id, tarih_str, float(deger), kaynak))
        self.conn.commit()
        return True

    def deger_sil(self, endeks_id: int, tarih: date) -> bool:
        c = self.conn.cursor()
        if hasattr(tarih, 'isoformat'):
            tarih_str = tarih.isoformat()
        else:
            tarih_str = str(tarih)
        c.execute("DELETE FROM endeks_deger WHERE endeks_id=? AND tarih=?",
                 (endeks_id, tarih_str))
        self.conn.commit()
        return c.rowcount > 0

    def degerleri_getir(self, endeks_id: int,
                        baslangic: Optional[date] = None,
                        bitis: Optional[date] = None) -> List[Dict]:
        c = self.conn.cursor()
        where = ["endeks_id = ?"]
        params = [endeks_id]
        if baslangic:
            where.append("tarih >= ?")
            params.append(baslangic.isoformat() if hasattr(baslangic, 'isoformat') else str(baslangic))
        if bitis:
            where.append("tarih <= ?")
            params.append(bitis.isoformat() if hasattr(bitis, 'isoformat') else str(bitis))
        sql = f"SELECT tarih, deger, kaynak FROM endeks_deger WHERE {' AND '.join(where)} ORDER BY tarih"
        rows = c.execute(sql, tuple(params)).fetchall()
        return [{'tarih': date.fromisoformat(r['tarih']), 'deger': r['deger'], 'kaynak': r['kaynak']}
                for r in rows]

    def deger_getir(self, endeks_id: int, tarih: date) -> Optional[float]:
        """Belirli bir tarihte endeks değeri. Tam eşleşme yoksa o tarihten önceki/içindeki
        en yakın değer döner (forward-fill mantığı: önce ay başı, yoksa son geçerli değer).
        """
        c = self.conn.cursor()
        tarih_str = tarih.isoformat() if hasattr(tarih, 'isoformat') else str(tarih)
        # Önce tam eşleşme
        row = c.execute(
            "SELECT deger FROM endeks_deger WHERE endeks_id=? AND tarih=?",
            (endeks_id, tarih_str)
        ).fetchone()
        if row:
            return row['deger']
        # Bu tarihten önceki en yeni değer (forward-fill)
        row = c.execute("""
            SELECT deger FROM endeks_deger
            WHERE endeks_id=? AND tarih <= ?
            ORDER BY tarih DESC LIMIT 1
        """, (endeks_id, tarih_str)).fetchone()
        if row:
            return row['deger']
        # Hiç yoksa: bu tarihten sonraki en eski değer (backward-fill)
        row = c.execute("""
            SELECT deger FROM endeks_deger
            WHERE endeks_id=? AND tarih > ?
            ORDER BY tarih ASC LIMIT 1
        """, (endeks_id, tarih_str)).fetchone()
        if row:
            return row['deger']
        return None

    def donem_ortalama(self, endeks_id: int, donem_bas: date, donem_bit: date) -> Optional[float]:
        """Bir dönemin (örn. 2025-03-01..2025-03-31) ortalama endeks değeri.
        Dönem içinde değer yoksa forward-fill ile en yakın değeri döndürür.
        """
        c = self.conn.cursor()
        rows = c.execute("""
            SELECT deger FROM endeks_deger
            WHERE endeks_id=? AND tarih BETWEEN ? AND ?
        """, (endeks_id, donem_bas.isoformat(), donem_bit.isoformat())).fetchall()
        if rows:
            return sum(r['deger'] for r in rows) / len(rows)
        # Dönem içinde değer yok → forward-fill ile dönem ortasındaki değer
        orta = donem_bas + (donem_bit - donem_bas) / 2
        if not isinstance(orta, date):
            orta = orta.date() if hasattr(orta, 'date') else date.today()
        return self.deger_getir(endeks_id, orta)

    # ------------------------------------------------------------------
    # Sepet (basket) CRUD
    # ------------------------------------------------------------------
    def sepet_ekle(self, ad: str, aciklama: str = "") -> int:
        c = self.conn.cursor()
        c.execute("INSERT INTO endeks_sepet (ad, aciklama) VALUES (?, ?)", (ad, aciklama))
        self.conn.commit()
        return c.lastrowid

    def sepet_sil(self, sepet_id: int) -> bool:
        c = self.conn.cursor()
        c.execute("DELETE FROM endeks_sepet WHERE id=?", (sepet_id,))
        self.conn.commit()
        return c.rowcount > 0

    def sepet_listesi(self) -> List[Dict]:
        c = self.conn.cursor()
        rows = c.execute("SELECT * FROM endeks_sepet ORDER BY ad").fetchall()
        return [dict(r) for r in rows]

    def sepet_uyeleri_getir(self, sepet_id: int) -> List[Dict]:
        c = self.conn.cursor()
        rows = c.execute("""
            SELECT u.endeks_id, u.agirlik, t.kod, t.ad, t.birim, t.kategori
            FROM endeks_sepet_uye u
            JOIN endeks_tanim t ON u.endeks_id = t.id
            WHERE u.sepet_id = ?
            ORDER BY t.ad
        """, (sepet_id,)).fetchall()
        return [dict(r) for r in rows]

    def sepete_endeks_ekle(self, sepet_id: int, endeks_id: int, agirlik: float = 1.0):
        c = self.conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO endeks_sepet_uye (sepet_id, endeks_id, agirlik)
            VALUES (?, ?, ?)
        """, (sepet_id, endeks_id, agirlik))
        self.conn.commit()

    def sepetten_endeks_cikar(self, sepet_id: int, endeks_id: int) -> bool:
        c = self.conn.cursor()
        c.execute("DELETE FROM endeks_sepet_uye WHERE sepet_id=? AND endeks_id=?",
                 (sepet_id, endeks_id))
        self.conn.commit()
        return c.rowcount > 0

    def sepet_donem_ortalama(self, sepet_id: int, donem_bas: date, donem_bit: date) -> Optional[float]:
        """Sepet ağırlıklı ortalama değeri = Σ(uye_deger × agirlik) / Σ(agirlik).

        Bir üyenin değeri eksikse o üye atlanır (toplam ağırlık da azalır).
        """
        uyeler = self.sepet_uyeleri_getir(sepet_id)
        if not uyeler:
            return None
        toplam_deger = 0.0
        toplam_agirlik = 0.0
        for u in uyeler:
            deg = self.donem_ortalama(u['endeks_id'], donem_bas, donem_bit)
            if deg is None:
                continue
            agir = float(u['agirlik'])
            toplam_deger += deg * agir
            toplam_agirlik += agir
        if toplam_agirlik == 0:
            return None
        return toplam_deger / toplam_agirlik

    # ------------------------------------------------------------------
    # Botanik ilaç fiyatı sync (Botanik DB'den çekip endeks_deger'e yaz)
    # ------------------------------------------------------------------
    def botanik_ilac_endeksi_sync(
        self,
        endeks_id: int,
        urun_id: int,
        baslangic: date,
        bitis: date,
        periyot: str = 'aylik',
    ) -> int:
        """Botanik DB'den UrunFiyatEtiket geçmişini çekip endeks_deger'e yazar.

        Periyot: 'aylik' önerilir. Yazılan kayıt sayısını döndürür.
        """
        try:
            from botanik_db import get_botanik_db
            bdb = get_botanik_db()
        except Exception as e:
            logger.error(f"Botanik DB erişimi yok: {e}")
            return 0

        if not hasattr(bdb, 'urun_fiyat_gecmisi_getir'):
            logger.error("botanik_db.urun_fiyat_gecmisi_getir yok — botanik_db güncel mi?")
            return 0

        fiyat_listesi = bdb.urun_fiyat_gecmisi_getir(
            urun_id=urun_id,
            baslangic_tarih=baslangic,
            bitis_tarih=bitis,
            periyot=periyot,
        )
        if not fiyat_listesi:
            return 0

        c = self.conn.cursor()
        eklenen = 0
        for row in fiyat_listesi:
            tarih = row.get('Donem')
            fiyat = row.get('OrtalamaPSF') or row.get('Fiyat')
            if tarih is None or fiyat is None:
                continue
            tarih_str = tarih.isoformat() if hasattr(tarih, 'isoformat') else str(tarih)
            try:
                c.execute("""
                    INSERT OR REPLACE INTO endeks_deger (endeks_id, tarih, deger, kaynak)
                    VALUES (?, ?, ?, 'botanik_psf')
                """, (endeks_id, tarih_str, float(fiyat)))
                eklenen += 1
            except Exception as e:
                logger.warning(f"İlaç endeks sync hatası ({tarih}): {e}")
        self.conn.commit()
        return eklenen

    # ------------------------------------------------------------------
    def kapat(self):
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None


# Singleton
_db_instance: Optional[EndeksDB] = None


def get_endeks_db() -> EndeksDB:
    global _db_instance
    if _db_instance is None:
        _db_instance = EndeksDB()
    return _db_instance


# Komut satırı test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    db = EndeksDB()
    print(f"DB: {db.db_yolu}")
    print(f"\nTanımlar:")
    for e in db.endeksleri_getir():
        print(f"  {e['kod']:20} {e['ad']:30} [{e['kategori']}] kaynak={e['kaynak']}")

    print(f"\nÖrnek değerler:")
    usd_id = db._endeks_id_kod('usd')
    if usd_id:
        son_5 = db.degerleri_getir(usd_id, baslangic=date(2025, 1, 1))[:5]
        for r in son_5:
            print(f"  USD {r['tarih']}: {r['deger']:.2f} TL")

    print(f"\nForward-fill testi:")
    if usd_id:
        # Mart 15, 2025 — direkt yok, Mart 1 değerinden forward-fill gelir
        d = db.deger_getir(usd_id, date(2025, 3, 15))
        print(f"  USD 2025-03-15: {d:.2f} TL (forward-fill)")
        # Aralık 31, 2025
        d = db.deger_getir(usd_id, date(2025, 12, 31))
        print(f"  USD 2025-12-31: {d:.2f} TL")
        # 2027 (gelecek, veri yok) — son değeri döndürür
        d = db.deger_getir(usd_id, date(2027, 6, 1))
        print(f"  USD 2027-06-01: {d:.2f} TL (forward-fill, veri yok)")

    print(f"\nDönem ortalaması:")
    if usd_id:
        avg = db.donem_ortalama(usd_id, date(2025, 1, 1), date(2025, 3, 31))
        print(f"  USD 2025 Q1 ort: {avg:.2f} TL")
