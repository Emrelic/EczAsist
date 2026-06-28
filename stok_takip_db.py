"""
Stok Takip Modülü — Yerel Veritabanı Katmanı

Bu modül BOTANIK EOS'tan TAMAMEN BAĞIMSIZ, kendi yerel stok defterini tutar.
Stok hareketleri (ekle / düş) yerel SQLite (stok_takip.db) içine yazılır.

Botanik EOS ile tek ilişki: ürün KARTLARININ (ad / barkod) salt-okuma ile
çekilmesidir (BotanikDB üzerinden, sadece SELECT). EOS stoğuna/verisine
ASLA yazılmaz, EOS stoğu bu modülün stoğunu etkilemez.

Karekod (datamatrix) GS1 formatında çözülür:
    01 -> GTIN (14, sabit)
    21 -> Seri No (değişken)
    17 -> Son Kullanma / Miad (6, YYMMDD)
    10 -> Parti / Lot (değişken)
Değişken alanlar GS1 spesifikasyonu gereği FNC1 (GS, ASCII 29) ile sonlanır.
"""

import os
import re
import sqlite3
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_SCRIPT_DIR, "stok_takip.db")

# GS1 FNC1 ayırıcı (Group Separator)
_GS = "\x1d"
# Sabit uzunluklu AI'ler (drug datamatrix için ilgili olanlar + yaygınlar)
_SABIT_AI = {"01": 14, "17": 6, "11": 6, "15": 6, "13": 6, "00": 18}
# Değişken uzunluklu AI'ler (GS ile veya string sonunda biter)
_DEGISKEN_AI = {"10", "21", "240", "30", "8200", "37"}


class StokTakipDB:
    """Yerel stok defteri (SQLite). Botanik EOS'tan bağımsız."""

    def __init__(self, botanik_db=None, db_yolu: str = _DB_PATH):
        self.db_yolu = db_yolu
        self.conn = sqlite3.connect(self.db_yolu, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._bdb = botanik_db  # BotanikDB (lazy)
        self._tablolari_olustur()

    # ================================================================== ŞEMA
    def _tablolari_olustur(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stok_kalem (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                urun_id     INTEGER,
                barkod      TEXT,
                urun_adi    TEXT NOT NULL,
                seri_no     TEXT,
                parti_no    TEXT,
                miad        TEXT,            -- ISO YYYY-MM-DD (NULL olabilir)
                karekod_ham TEXT,
                adet        INTEGER NOT NULL DEFAULT 1,
                durum       INTEGER NOT NULL DEFAULT 1,   -- 1=stokta, 0=çıktı
                giris_tarih TEXT,
                cikis_tarih TEXT,
                ekleyen     TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stok_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                yon       TEXT,              -- GIRIS / CIKIS
                urun_id   INTEGER,
                barkod    TEXT,
                urun_adi  TEXT,
                seri_no   TEXT,
                parti_no  TEXT,
                miad      TEXT,
                adet      INTEGER,
                zaman     TEXT,
                kullanici TEXT,
                aciklama  TEXT
            )
        """)
        # Yerel ürün kartı tablosu — Botanik'ten BİR KEZ aktarılır, sonra
        # tüm okutmalar/aramalar bu yerel tablodan yapılır (EOS'a bağlanmadan).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS urun_kart (
                barkod       TEXT PRIMARY KEY,
                urun_id      INTEGER,
                urun_adi     TEXT,
                etiket_fiyat REAL,
                guncelleme   TEXT
            )
        """)
        # Aktif (stokta) bir seri no iki kez bulunamaz — çift okutma koruması
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_stok_aktif_seri
            ON stok_kalem(seri_no)
            WHERE seri_no IS NOT NULL AND durum = 1
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS ix_stok_aktif
            ON stok_kalem(durum, urun_adi)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS ix_urun_kart_ad ON urun_kart(urun_adi)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS ix_urun_kart_uid ON urun_kart(urun_id)
        """)
        self.conn.commit()

    # ====================================================== YEREL ÜRÜN KARTLARI
    def kart_sayisi(self) -> int:
        """Yerel veritabanındaki ürün kartı (barkod) sayısı."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM urun_kart")
        return cur.fetchone()["c"]

    def kartlari_botanikten_aktar(self) -> int:
        """
        Botanik EOS'tan TÜM ürün kartlarını yerel urun_kart tablosuna aktar.
        Botanik'e yalnızca bu işlemde (salt-okuma) bağlanılır; tek seferlik /
        periyodik tazeleme amaçlıdır. Mevcut yerel kartlar yenilenir.

        Thread-güvenli olması için kendi BotanikDB bağlantısını açıp kapatır.
        Döner: aktarılan kart (barkod) sayısı.
        """
        from botanik_db import BotanikDB
        bdb = BotanikDB()
        if not bdb.baglan():
            raise RuntimeError("Botanik EOS bağlantısı kurulamadı.")
        try:
            rows = bdb.tum_urun_kartlari()
        finally:
            bdb.kapat()

        simdi = datetime.now().isoformat(timespec="seconds")
        veriler = []
        for r in rows:
            barkod = r.get("Barkod")
            if barkod is None:
                continue
            barkod = str(barkod).strip()
            if not barkod:
                continue
            veriler.append((barkod, r.get("UrunId"), r.get("UrunAdi"),
                            r.get("EtiketFiyat"), simdi))

        cur = self.conn.cursor()
        cur.execute("DELETE FROM urun_kart")
        cur.executemany("""
            INSERT OR REPLACE INTO urun_kart
                (barkod, urun_id, urun_adi, etiket_fiyat, guncelleme)
            VALUES (?, ?, ?, ?, ?)
        """, veriler)
        self.conn.commit()
        logger.info("Yerel ürün kartı aktarımı: %d kart", len(veriler))
        return len(veriler)

    def urun_karti_barkoddan(self, barkod: str) -> Optional[Dict]:
        """Barkod/GTIN ile YEREL ürün kartı (urun_kart tablosu)."""
        if not barkod:
            return None
        b = str(barkod).strip()
        if not b:
            return None
        adaylar = {b, b.lstrip("0")}
        if len(b) == 14 and b.startswith("0"):
            adaylar.add(b[1:])
        if len(b) == 13:
            adaylar.add("0" + b)
        adaylar = [a for a in adaylar if a]
        if not adaylar:
            return None
        ph = ",".join("?" for _ in adaylar)
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT urun_id, urun_adi, barkod, etiket_fiyat
            FROM urun_kart WHERE barkod IN ({ph}) LIMIT 1
        """, adaylar)
        r = cur.fetchone()
        if not r:
            return None
        return {"UrunId": r["urun_id"], "UrunAdi": r["urun_adi"],
                "Barkod": r["barkod"], "EtiketFiyat": r["etiket_fiyat"]}

    def urun_karti_ara(self, ad: str, limit: int = 100) -> List[Dict]:
        """İsimle YEREL ürün kartı araması (urun_kart tablosu)."""
        if not ad or not ad.strip():
            return []
        cur = self.conn.cursor()
        cur.execute("""
            SELECT urun_id, urun_adi, MIN(barkod) AS barkod
            FROM urun_kart
            WHERE urun_adi LIKE ?
            GROUP BY urun_id, urun_adi
            ORDER BY urun_adi
            LIMIT ?
        """, (f"%{ad.strip()}%", int(limit)))
        return [{"UrunId": r["urun_id"], "UrunAdi": r["urun_adi"],
                 "Barkod": r["barkod"]} for r in cur.fetchall()]

    # ============================================================ GS1 ÇÖZÜCÜ
    @staticmethod
    def _miad_coz(yymmdd: str) -> Optional[str]:
        """YYMMDD -> ISO YYYY-MM-DD. GG=00 ise ayın son günü."""
        if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
            return None
        yil = 2000 + int(yymmdd[0:2])
        ay = int(yymmdd[2:4])
        gun = int(yymmdd[4:6])
        if not (1 <= ay <= 12):
            return None
        if gun == 0:
            # Ayın son günü
            if ay == 12:
                son = date(yil, 12, 31)
            else:
                son = date(yil, ay + 1, 1)
                son = date(son.year, son.month, 1)
                from datetime import timedelta
                son = son - timedelta(days=1)
            gun = son.day
        try:
            return date(yil, ay, gun).isoformat()
        except ValueError:
            return None

    @classmethod
    def karekod_coz(cls, ham: str) -> Dict:
        """
        Ham datamatrix/barkod girdisini çöz.

        Döner: {
            'tip': 'karekod' | 'barkod' | 'isim',
            'gtin', 'barkod', 'seri_no', 'parti_no', 'miad', 'ham'
        }
        - 'karekod': GS1 AI'leri bulundu (01/17/21/10)
        - 'barkod' : sadece rakamlardan oluşan düz barkod (8-14 hane)
        - 'isim'   : yukarıdakilere uymayan serbest metin
        """
        sonuc = {"tip": "isim", "gtin": None, "barkod": None,
                 "seri_no": None, "parti_no": None, "miad": None, "ham": ham}
        if ham is None:
            return sonuc
        s = ham.strip()
        if not s:
            return sonuc

        # Semboloji ön eki (]d2, ]C1, ]Q3 ...) temizle
        if len(s) >= 3 and s[0] == "]":
            s = s[3:]

        # Parantezli insan-okur biçim: (01)... (21)... -> GS ile ayrılmış hale getir
        if "(" in s and ")" in s:
            s = re.sub(r"\((\d{2,4})\)", lambda m: _GS + m.group(1), s)
            s = s.lstrip(_GS)

        ai_var = cls._ai_ayristir(s)
        if ai_var and ("01" in ai_var or "17" in ai_var or "21" in ai_var):
            gtin = ai_var.get("01")
            barkod = None
            if gtin:
                barkod = gtin.lstrip("0") or gtin
                # 14 -> 13 (EAN13) için baştaki tek 0'ı düşür
                if len(gtin) == 14 and gtin.startswith("0"):
                    barkod = gtin[1:]
            sonuc.update({
                "tip": "karekod",
                "gtin": gtin,
                "barkod": barkod,
                "seri_no": ai_var.get("21"),
                "parti_no": ai_var.get("10"),
                "miad": cls._miad_coz(ai_var.get("17", "")) if ai_var.get("17") else None,
            })
            return sonuc

        # Düz barkod? (sadece rakam, 8-14 hane)
        temiz = s.replace(_GS, "").strip()
        if temiz.isdigit() and 8 <= len(temiz) <= 14:
            sonuc.update({"tip": "barkod", "barkod": temiz, "gtin": temiz})
            return sonuc

        # Serbest metin (isim araması)
        sonuc["ham"] = temiz
        return sonuc

    @staticmethod
    def _gecerli_tarih6(seg: str) -> bool:
        """6 haneli YYMMDD geçerli mi (ay 1-12, gün 0-31)?"""
        if len(seg) != 6 or not seg.isdigit():
            return False
        ay = int(seg[2:4])
        gun = int(seg[4:6])
        return 1 <= ay <= 12 and 0 <= gun <= 31

    @classmethod
    def _sonraki_sabit_ai(cls, s: str, j: int) -> int:
        """
        GS ayırıcı yokken, bir değişken alanın (genelde 21=seri) bittiği konumu bul.

        TR ilaç datamatrix'inde değişken seri alanından sonra daima 17=miad gelir.
        Yanlış sınır (seri içindeki rastgele rakamlar) riskini en aza indirmek için
        SADECE güçlü sınırlar aranır:
          - "17" + geçerli YYMMDD tarih  (seri -> miad sınırı; asıl ayraç)
          - "01" + 14 hane GTIN          (nadir: arka arkaya birleşik kod)
        Bulunamazsa string sonu döner (alan sona kadar uzanır — örn. son parti).
        """
        n = len(s)
        k = j
        while k <= n - 2:
            ai = s[k:k + 2]
            if ai == "17":
                seg = s[k + 2:k + 8]
                if cls._gecerli_tarih6(seg):
                    return k
            elif ai == "01":
                seg = s[k + 2:k + 16]
                if len(seg) == 14 and seg.isdigit():
                    return k
            k += 1
        return n

    @classmethod
    def _ai_ayristir(cls, s: str) -> Dict[str, str]:
        """
        GS1 element string'ini AI->değer sözlüğüne çevir.

        Değişken alanlar (21 seri, 10 parti) önce FNC1/GS (ASCII 29) ile,
        ayırıcı yoksa bir sonraki sabit-AI sınırı (örn. 17=miad) ile sonlandırılır.
        Böylece okuyucu GS göndermese bile miad ve parti doğru ayrışır.
        """
        result: Dict[str, str] = {}
        i = 0
        n = len(s)
        guvenlik = 0
        while i < n and guvenlik < 100:
            guvenlik += 1
            if s[i] == _GS:
                i += 1
                continue
            ai = s[i:i + 2]
            if not ai.isdigit():
                # AI değil -> çözümlenemez (muhtemelen düz barkod / metin)
                return {}
            if ai in _SABIT_AI:
                uzunluk = _SABIT_AI[ai]
                deger = s[i + 2:i + 2 + uzunluk]
                result[ai] = deger
                i = i + 2 + uzunluk
            else:
                # Değişken (veya bilinmeyen) AI: GS'e, yoksa sonraki sabit AI'ye kadar
                j = i + 2
                gs = s.find(_GS, j)
                son = gs if gs != -1 else cls._sonraki_sabit_ai(s, j)
                result[ai] = s[j:son]
                i = son
        return result

    # ============================================================ STOK EKLE
    def stok_ekle(self, kalem: Dict, kullanici: str = "") -> Tuple[bool, str]:
        """
        Bir kalemi stoğa ekle.

        kalem: {urun_id, barkod, urun_adi, seri_no, parti_no, miad, adet,
                karekod_ham}
        """
        urun_adi = (kalem.get("urun_adi") or "").strip()
        if not urun_adi:
            return False, "Ürün adı boş — eklenemez."
        adet = int(kalem.get("adet") or 1)
        if adet <= 0:
            return False, "Adet 0'dan büyük olmalı."
        seri_no = kalem.get("seri_no") or None
        simdi = datetime.now().isoformat(timespec="seconds")

        cur = self.conn.cursor()
        # Aynı seri zaten stokta mı?
        if seri_no:
            cur.execute(
                "SELECT id FROM stok_kalem WHERE seri_no = ? AND durum = 1",
                (seri_no,))
            if cur.fetchone():
                return False, f"Bu karekod (seri: {seri_no}) zaten stokta."
        try:
            cur.execute("""
                INSERT INTO stok_kalem
                    (urun_id, barkod, urun_adi, seri_no, parti_no, miad,
                     karekod_ham, adet, durum, giris_tarih, ekleyen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                kalem.get("urun_id"), kalem.get("barkod"), urun_adi,
                seri_no, kalem.get("parti_no"), kalem.get("miad"),
                kalem.get("karekod_ham"), adet, simdi, kullanici,
            ))
            kalem_id = cur.lastrowid
            self._logla(cur, "GIRIS", kalem, adet, kullanici, simdi)
            self.conn.commit()
            return True, f"Eklendi (kalem #{kalem_id})."
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False, f"Bu karekod (seri: {seri_no}) zaten stokta."
        except Exception as e:
            self.conn.rollback()
            logger.error("stok_ekle hatası: %s", e)
            return False, f"Hata: {e}"

    # ============================================================ STOK DÜŞ
    def stok_dus_seri(self, seri_no: str, kullanici: str = "") -> Tuple[bool, str]:
        """Belirli bir seri no'lu kalemi stoktan düş."""
        if not seri_no:
            return False, "Seri no boş."
        cur = self.conn.cursor()
        cur.execute("""
            SELECT * FROM stok_kalem WHERE seri_no = ? AND durum = 1
        """, (seri_no,))
        row = cur.fetchone()
        if not row:
            return False, f"Stokta bu seri yok: {seri_no}"
        simdi = datetime.now().isoformat(timespec="seconds")
        cur.execute(
            "UPDATE stok_kalem SET durum = 0, cikis_tarih = ? WHERE id = ?",
            (simdi, row["id"]))
        self._logla(cur, "CIKIS", dict(row), row["adet"], kullanici, simdi)
        self.conn.commit()
        return True, f"Düşüldü: {row['urun_adi']} (seri {seri_no})"

    def stok_dus_parti(self, urun_id, barkod, parti_no, miad, adet,
                       kullanici: str = "") -> Tuple[bool, str]:
        """
        Belirli ürün + parti + miad için 'adet' kadar stoktan düş.
        (Karekod okutulmadan, kullanıcı parti seçtiğinde kullanılır.)
        """
        adet = int(adet)
        if adet <= 0:
            return False, "Adet 0'dan büyük olmalı."
        kosul, params = self._parti_kosulu(urun_id, barkod, parti_no, miad)
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT id, adet, urun_id, barkod, urun_adi, seri_no, parti_no, miad
            FROM stok_kalem
            WHERE durum = 1 AND {kosul}
            ORDER BY id
        """, params)
        rows = cur.fetchall()
        mevcut = sum(r["adet"] for r in rows)
        if mevcut < adet:
            return False, f"Yetersiz stok (mevcut {mevcut}, istenen {adet})."

        simdi = datetime.now().isoformat(timespec="seconds")
        kalan = adet
        for r in rows:
            if kalan <= 0:
                break
            if r["adet"] <= kalan:
                cur.execute(
                    "UPDATE stok_kalem SET durum = 0, cikis_tarih = ? WHERE id = ?",
                    (simdi, r["id"]))
                self._logla(cur, "CIKIS", dict(r), r["adet"], kullanici, simdi)
                kalan -= r["adet"]
            else:
                cur.execute(
                    "UPDATE stok_kalem SET adet = adet - ? WHERE id = ?",
                    (kalan, r["id"]))
                self._logla(cur, "CIKIS", dict(r), kalan, kullanici, simdi)
                kalan = 0
        self.conn.commit()
        ad = rows[0]["urun_adi"] if rows else ""
        return True, f"Düşüldü: {ad} ({adet} adet)"

    def _parti_kosulu(self, urun_id, barkod, parti_no, miad):
        """Parti eşleştirme WHERE koşulu (NULL-güvenli)."""
        kosullar = []
        params = []
        if urun_id is not None:
            kosullar.append("urun_id IS ?")
            params.append(urun_id)
        elif barkod:
            kosullar.append("barkod = ?")
            params.append(barkod)
        else:
            kosullar.append("1=1")
        kosullar.append("IFNULL(parti_no,'') = IFNULL(?,'')")
        params.append(parti_no)
        kosullar.append("IFNULL(miad,'') = IFNULL(?,'')")
        params.append(miad)
        return " AND ".join(kosullar), tuple(params)

    def _logla(self, cur, yon, kalem, adet, kullanici, zaman):
        cur.execute("""
            INSERT INTO stok_log
                (yon, urun_id, barkod, urun_adi, seri_no, parti_no, miad,
                 adet, zaman, kullanici, aciklama)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            yon, kalem.get("urun_id"), kalem.get("barkod"),
            kalem.get("urun_adi"), kalem.get("seri_no"),
            kalem.get("parti_no"), kalem.get("miad"),
            adet, zaman, kullanici, "",
        ))

    # ============================================================ PARTİ LİSTE
    def parti_listesi(self, urun_id=None, barkod=None) -> List[Dict]:
        """Bir ürünün stoktaki partileri (çıkış için seçim)."""
        kosullar = ["durum = 1"]
        params = []
        if urun_id is not None:
            kosullar.append("urun_id IS ?")
            params.append(urun_id)
        elif barkod:
            kosullar.append("barkod = ?")
            params.append(barkod)
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT urun_id, barkod, urun_adi,
                   parti_no, miad, SUM(adet) AS toplam
            FROM stok_kalem
            WHERE {' AND '.join(kosullar)}
            GROUP BY urun_id, barkod, urun_adi, parti_no, miad
            ORDER BY IFNULL(miad,'9999-99-99'), parti_no
        """, params)
        return [dict(r) for r in cur.fetchall()]

    # ============================================================ GÖRÜNÜMLER
    def _filtre_kosul(self, filtre):
        if filtre and filtre.strip():
            return " AND urun_adi LIKE ?", (f"%{filtre.strip()}%",)
        return "", tuple()

    def stok_barkod_bazli(self, filtre: str = "") -> List[Dict]:
        """Her ürün tek satır: toplam adet + en yakın miad."""
        ek, params = self._filtre_kosul(filtre)
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT urun_id, barkod, urun_adi,
                   SUM(adet) AS toplam,
                   MIN(miad) AS en_yakin_miad,
                   COUNT(DISTINCT IFNULL(parti_no,'') || '|' || IFNULL(miad,'')) AS parti_sayisi
            FROM stok_kalem
            WHERE durum = 1{ek}
            GROUP BY urun_id, barkod, urun_adi
            ORDER BY urun_adi
        """, params)
        return [dict(r) for r in cur.fetchall()]

    def stok_miad_bazli(self, filtre: str = "") -> List[Dict]:
        """Her ayrı parti+miad bir satır."""
        ek, params = self._filtre_kosul(filtre)
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT urun_id, barkod, urun_adi, parti_no, miad,
                   SUM(adet) AS toplam
            FROM stok_kalem
            WHERE durum = 1{ek}
            GROUP BY urun_id, barkod, urun_adi, parti_no, miad
            ORDER BY urun_adi, IFNULL(miad,'9999-99-99')
        """, params)
        return [dict(r) for r in cur.fetchall()]

    def stok_karekod_bazli(self, filtre: str = "") -> List[Dict]:
        """Her karekod (seri) ayrı satır."""
        ek, params = self._filtre_kosul(filtre)
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT id, urun_id, barkod, urun_adi, seri_no, parti_no, miad,
                   adet, giris_tarih
            FROM stok_kalem
            WHERE durum = 1{ek}
            ORDER BY urun_adi, IFNULL(miad,'9999-99-99'), id
        """, params)
        return [dict(r) for r in cur.fetchall()]

    def kapat(self):
        try:
            self.conn.close()
        except Exception:
            pass
