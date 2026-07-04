"""
Hasta İşlem Süresi Takip Modülü — Yerel Veritabanı Katmanı

Bir hasta ile ilgilenme süresini ölçen kronometre modülünün yerel SQLite
defteri (hasta_sure_takip.db). Botanik EOS'tan TAMAMEN BAĞIMSIZDIR; EOS'a
hiçbir şekilde bağlanmaz/yazmaz. Sadece kendi yerel verisini tutar.

Her "Bitir" bir işlem = bir hasta kaydı üretir:
    - hasta_adi   : opsiyonel (boş olabilir)
    - personel    : işlemi yapan (oturum açan) kullanıcı
    - baslangic   : ilk "Başlat" anı (ISO datetime)
    - bitis       : son "Bitir" anı (ISO datetime)
    - sure_saniye : NET ölçülen süre (duraklamalar hariç), saniye
    - ekleme_say  : hasta dönüp geldiğinde "Ekle" ile kaç kez süreye devam edildi
    - notu        : opsiyonel kısa not
    - tarih       : YYYY-MM-DD (gruplama/istatistik için)
"""

import os
import sqlite3
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH = os.path.join(_SCRIPT_DIR, "hasta_sure_takip.db")


class HastaSureDB:
    """Yerel hasta işlem süresi defteri (SQLite)."""

    def __init__(self, db_yolu: str = _DB_PATH):
        self.db_yolu = db_yolu
        self.conn = sqlite3.connect(self.db_yolu, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._tablolari_olustur()

    # ================================================================== ŞEMA
    def _tablolari_olustur(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS islem (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                hasta_adi   TEXT,
                personel    TEXT,
                baslangic   TEXT,            -- ISO datetime
                bitis       TEXT,            -- ISO datetime
                sure_saniye INTEGER NOT NULL DEFAULT 0,
                ekleme_say  INTEGER NOT NULL DEFAULT 0,
                notu        TEXT,
                kategori    TEXT,            -- ziyaretçi tipi (M/DP/MH/BADH...)
                recete      INTEGER NOT NULL DEFAULT 0,  -- reçete adedi (0,1,2..)
                perakende   INTEGER NOT NULL DEFAULT 0,  -- perakende adedi (0,1,2..)
                tarih       TEXT             -- YYYY-MM-DD
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS ix_islem_tarih ON islem(tarih)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_islem_personel ON islem(personel)")
        self.conn.commit()
        # Eski DB'ler için kolon migrasyonları (idempotent)
        self._kolon_ekle("islem", "kategori", "TEXT")
        self._kolon_ekle("islem", "recete", "INTEGER NOT NULL DEFAULT 0")
        self._kolon_ekle("islem", "perakende", "INTEGER NOT NULL DEFAULT 0")

    def _kolon_ekle(self, tablo, kolon, tanim):
        """Tabloda kolon yoksa ALTER ile ekle (idempotent migrasyon)."""
        cur = self.conn.cursor()
        cur.execute(f"PRAGMA table_info({tablo})")
        mevcut = [row[1] for row in cur.fetchall()]
        if kolon not in mevcut:
            cur.execute(f"ALTER TABLE {tablo} ADD COLUMN {kolon} {tanim}")
            self.conn.commit()

    # ============================================================ KAYIT / GÜNCELLE
    def islem_kaydet(self, hasta_adi, personel, baslangic_dt, bitis_dt,
                     sure_saniye, ekleme_say=0, notu="", kategori="",
                     recete=0, perakende=0):
        """
        Yeni bir işlem kaydı ekle. Döner: yeni kaydın id'si.

        baslangic_dt / bitis_dt: datetime nesnesi ya da ISO string olabilir.
        kategori: ziyaretçi tipi kısa kodu (M/DP/MH/BADH/AS/OZ/UNV/DH) ya da "".
        recete/perakende: adet (0,1,2..); bağımsız — bir hastada birden çok olabilir.
        """
        bas = self._iso(baslangic_dt)
        bit = self._iso(bitis_dt)
        tarih = (bit or bas or datetime.now().isoformat())[:10]
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO islem
                (hasta_adi, personel, baslangic, bitis, sure_saniye,
                 ekleme_say, notu, kategori, recete, perakende, tarih)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            (hasta_adi or "").strip(), (personel or "").strip(),
            bas, bit, int(round(sure_saniye or 0)),
            int(ekleme_say or 0), (notu or "").strip(),
            (kategori or "").strip(), max(0, int(recete or 0)),
            max(0, int(perakende or 0)), tarih,
        ))
        self.conn.commit()
        return cur.lastrowid

    def islem_guncelle(self, islem_id, bitis_dt, sure_saniye,
                       ekleme_say=None, hasta_adi=None, notu=None,
                       kategori=None, recete=None, perakende=None):
        """
        Var olan bir işlemi güncelle (hasta dönüp geldiğinde 'Ekle' + tekrar
        'Bitir' senaryosu). Yalnızca verilen alanlar güncellenir.
        """
        alanlar = ["bitis = ?", "sure_saniye = ?"]
        params = [self._iso(bitis_dt), int(round(sure_saniye or 0))]
        if ekleme_say is not None:
            alanlar.append("ekleme_say = ?")
            params.append(int(ekleme_say))
        if hasta_adi is not None:
            alanlar.append("hasta_adi = ?")
            params.append((hasta_adi or "").strip())
        if notu is not None:
            alanlar.append("notu = ?")
            params.append((notu or "").strip())
        if kategori is not None:
            alanlar.append("kategori = ?")
            params.append((kategori or "").strip())
        if recete is not None:
            alanlar.append("recete = ?")
            params.append(max(0, int(recete or 0)))
        if perakende is not None:
            alanlar.append("perakende = ?")
            params.append(max(0, int(perakende or 0)))
        params.append(islem_id)
        cur = self.conn.cursor()
        cur.execute(f"UPDATE islem SET {', '.join(alanlar)} WHERE id = ?", params)
        self.conn.commit()
        return cur.rowcount > 0

    def islem_sil(self, islem_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM islem WHERE id = ?", (islem_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def son_kayit(self):
        """En son kaydedilen işlemi (en büyük id) getir. Yoksa None."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, hasta_adi, personel, baslangic, bitis, sure_saniye,
                   ekleme_say, notu, kategori, recete, perakende, tarih
            FROM islem
            ORDER BY id DESC
            LIMIT 1
        """)
        r = cur.fetchone()
        return dict(r) if r else None

    @staticmethod
    def _iso(dt):
        if dt is None:
            return None
        if isinstance(dt, str):
            return dt
        try:
            return dt.isoformat(timespec="seconds")
        except Exception:
            return str(dt)

    # ============================================================ SORGULAR
    def son_islemler(self, limit=200, tarih=None, personel=None):
        """Son işlemleri (en yeni önce) getir. tarih='YYYY-MM-DD' ile filtre."""
        kosullar = []
        params = []
        if tarih:
            kosullar.append("tarih = ?")
            params.append(tarih)
        if personel:
            kosullar.append("personel = ?")
            params.append(personel)
        where = ("WHERE " + " AND ".join(kosullar)) if kosullar else ""
        params.append(int(limit))
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT id, hasta_adi, personel, baslangic, bitis, sure_saniye,
                   ekleme_say, notu, kategori, recete, perakende, tarih
            FROM islem
            {where}
            ORDER BY id DESC
            LIMIT ?
        """, params)
        return [dict(r) for r in cur.fetchall()]

    def gun_ozeti(self, tarih=None, personel=None):
        """
        Bir günün özeti: işlem adedi, toplam/ortalama/en uzun/en kısa süre.
        tarih None ise bugün. Döner: dict.
        """
        if tarih is None:
            tarih = datetime.now().strftime("%Y-%m-%d")
        kosullar = ["tarih = ?"]
        params = [tarih]
        if personel:
            kosullar.append("personel = ?")
            params.append(personel)
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT COUNT(*) AS adet,
                   IFNULL(SUM(sure_saniye), 0) AS toplam,
                   IFNULL(AVG(sure_saniye), 0) AS ortalama,
                   IFNULL(MAX(sure_saniye), 0) AS en_uzun,
                   IFNULL(MIN(sure_saniye), 0) AS en_kisa,
                   IFNULL(SUM(recete), 0) AS recete,
                   IFNULL(SUM(perakende), 0) AS perakende
            FROM islem
            WHERE {' AND '.join(kosullar)}
        """, params)
        r = cur.fetchone()
        return {
            "tarih": tarih,
            "adet": r["adet"],
            "toplam": int(r["toplam"]),
            "ortalama": int(round(r["ortalama"])) if r["adet"] else 0,
            "en_uzun": int(r["en_uzun"]),
            "en_kisa": int(r["en_kisa"]) if r["adet"] else 0,
            "recete": int(r["recete"]),
            "perakende": int(r["perakende"]),
        }

    def saatlik_dagilim(self, tarih=None, personel=None):
        """
        Bir günde saat (00-23) bazlı işlem adedi + ortalama süre.
        Döner: {saat: {'adet': n, 'ortalama': sn}} (sadece dolu saatler).
        baslangic saatine göre gruplanır.
        """
        if tarih is None:
            tarih = datetime.now().strftime("%Y-%m-%d")
        kosullar = ["tarih = ?"]
        params = [tarih]
        if personel:
            kosullar.append("personel = ?")
            params.append(personel)
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT substr(baslangic, 12, 2) AS saat,
                   COUNT(*) AS adet,
                   IFNULL(AVG(sure_saniye), 0) AS ortalama
            FROM islem
            WHERE {' AND '.join(kosullar)}
            GROUP BY saat
            ORDER BY saat
        """, params)
        sonuc = {}
        for r in cur.fetchall():
            s = r["saat"]
            if s is None:
                continue
            sonuc[s] = {"adet": r["adet"],
                        "ortalama": int(round(r["ortalama"]))}
        return sonuc

    def gunluk_seri(self, gun_sayisi=7, personel=None):
        """
        Son N günün günlük özeti (bugün dahil). Döner: [dict, ...] eskiden yeniye.
        Kayıt olmayan günler adet=0 ile doldurulur.
        """
        bugun = datetime.now().date()
        sonuc = []
        for i in range(gun_sayisi - 1, -1, -1):
            g = (bugun - timedelta(days=i)).strftime("%Y-%m-%d")
            sonuc.append(self.gun_ozeti(tarih=g, personel=personel))
        return sonuc

    def personel_ozeti(self, tarih=None):
        """Bir günde personel bazlı adet + ortalama + toplam süre."""
        if tarih is None:
            tarih = datetime.now().strftime("%Y-%m-%d")
        cur = self.conn.cursor()
        cur.execute("""
            SELECT IFNULL(NULLIF(personel, ''), '(belirsiz)') AS personel,
                   COUNT(*) AS adet,
                   IFNULL(SUM(sure_saniye), 0) AS toplam,
                   IFNULL(AVG(sure_saniye), 0) AS ortalama
            FROM islem
            WHERE tarih = ?
            GROUP BY personel
            ORDER BY adet DESC
        """, (tarih,))
        return [{"personel": r["personel"], "adet": r["adet"],
                 "toplam": int(r["toplam"]),
                 "ortalama": int(round(r["ortalama"]))}
                for r in cur.fetchall()]

    def kategori_ozeti(self, tarih=None, personel=None):
        """Bir günde kategori (ziyaretçi tipi) bazlı adet + ortalama süre."""
        if tarih is None:
            tarih = datetime.now().strftime("%Y-%m-%d")
        kosullar = ["tarih = ?"]
        params = [tarih]
        if personel:
            kosullar.append("personel = ?")
            params.append(personel)
        cur = self.conn.cursor()
        cur.execute(f"""
            SELECT IFNULL(NULLIF(kategori, ''), '(belirsiz)') AS kategori,
                   COUNT(*) AS adet,
                   IFNULL(AVG(sure_saniye), 0) AS ortalama
            FROM islem
            WHERE {' AND '.join(kosullar)}
            GROUP BY kategori
            ORDER BY adet DESC
        """, params)
        return [{"kategori": r["kategori"], "adet": r["adet"],
                 "ortalama": int(round(r["ortalama"]))}
                for r in cur.fetchall()]

    def kapat(self):
        try:
            self.conn.close()
        except Exception:
            pass


# ===================================================================== YARDIMCI
def sure_bicimle(saniye):
    """Saniyeyi okunur biçime çevir: 42sn -> '00:42', 3725sn -> '1:02:05'."""
    try:
        saniye = int(round(saniye or 0))
    except (TypeError, ValueError):
        saniye = 0
    if saniye < 0:
        saniye = 0
    saat, kalan = divmod(saniye, 3600)
    dakika, sn = divmod(kalan, 60)
    if saat:
        return f"{saat}:{dakika:02d}:{sn:02d}"
    return f"{dakika:02d}:{sn:02d}"
