"""
Botanik Bot - SQLite Database Yöneticisi
Oturum raporlarını saklar ve sorgular
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BotanikDatabase:
    """Oturum raporları için SQLite database yöneticisi"""

    def __init__(self, db_dosya="oturum_raporlari.db"):
        # Dosyayı script'in bulunduğu dizine kaydet
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_yolu = Path(script_dir) / db_dosya

        # Database'i oluştur/aç
        self.baglanti_kur()
        self.tabloları_olustur()

    def baglanti_kur(self):
        """Database bağlantısını kur"""
        try:
            self.conn = sqlite3.connect(str(self.db_yolu))
            self.cursor = self.conn.cursor()
            logger.info(f"✓ Database bağlantısı kuruldu: {self.db_yolu}")
        except Exception as e:
            logger.error(f"Database bağlantı hatası: {e}")
            raise

    def tabloları_olustur(self):
        """Gerekli tabloları oluştur"""
        try:
            # Oturumlar tablosu
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS oturumlar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    baslangic_zamani TEXT NOT NULL,
                    bitis_zamani TEXT,
                    grup TEXT NOT NULL,
                    baslangic_recete TEXT,
                    bitis_recete TEXT,
                    toplam_recete INTEGER DEFAULT 0,
                    toplam_takip INTEGER DEFAULT 0,
                    yeniden_baslatma_sayisi INTEGER DEFAULT 0,
                    taskkill_sayisi INTEGER DEFAULT 0,
                    ortalama_recete_suresi REAL DEFAULT 0.0,
                    durum TEXT DEFAULT 'aktif'
                )
            ''')

            self.conn.commit()
            logger.info("✓ Database tabloları oluşturuldu")
        except Exception as e:
            logger.error(f"Tablo oluşturma hatası: {e}")
            raise

    def yeni_oturum_baslat(self, grup, baslangic_recete=None):
        """Yeni oturum başlat"""
        try:
            baslangic_zamani = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.cursor.execute('''
                INSERT INTO oturumlar (
                    baslangic_zamani, grup, baslangic_recete, durum
                ) VALUES (?, ?, ?, 'aktif')
            ''', (baslangic_zamani, grup, baslangic_recete))

            self.conn.commit()
            oturum_id = self.cursor.lastrowid
            logger.info(f"✓ Yeni oturum başlatıldı: ID={oturum_id}, Grup={grup}")
            return oturum_id
        except Exception as e:
            logger.error(f"Oturum başlatma hatası: {e}")
            return None

    def oturum_guncelle(self, oturum_id, **kwargs):
        """Oturumu güncelle"""
        try:
            guncellenecek_alanlar = []
            degerler = []

            for alan, deger in kwargs.items():
                if alan in ['bitis_zamani', 'bitis_recete', 'toplam_recete', 'toplam_takip',
                           'yeniden_baslatma_sayisi', 'taskkill_sayisi', 'ortalama_recete_suresi', 'durum']:
                    guncellenecek_alanlar.append(f"{alan} = ?")
                    degerler.append(deger)

            if not guncellenecek_alanlar:
                return False

            degerler.append(oturum_id)
            sorgu = f"UPDATE oturumlar SET {', '.join(guncellenecek_alanlar)} WHERE id = ?"

            self.cursor.execute(sorgu, degerler)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Oturum güncelleme hatası: {e}")
            return False

    def oturum_bitir(self, oturum_id, bitis_recete=None):
        """Oturumu bitir"""
        try:
            bitis_zamani = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            guncelleme = {
                'bitis_zamani': bitis_zamani,
                'durum': 'tamamlandi'
            }

            if bitis_recete:
                guncelleme['bitis_recete'] = bitis_recete

            return self.oturum_guncelle(oturum_id, **guncelleme)
        except Exception as e:
            logger.error(f"Oturum bitirme hatası: {e}")
            return False

    def artir(self, oturum_id, alan, miktar=1):
        """Belirtilen alanı artır (yeniden_baslatma_sayisi, taskkill_sayisi, vb.)"""
        try:
            if alan in ['toplam_recete', 'toplam_takip', 'yeniden_baslatma_sayisi', 'taskkill_sayisi']:
                self.cursor.execute(f'''
                    UPDATE oturumlar
                    SET {alan} = {alan} + ?
                    WHERE id = ?
                ''', (miktar, oturum_id))

                self.conn.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Artırma hatası: {e}")
            return False

    def oturum_getir(self, oturum_id):
        """Belirli bir oturumu ID'ye göre getir"""
        try:
            self.cursor.execute('''
                SELECT * FROM oturumlar
                WHERE id = ?
            ''', (oturum_id,))

            row = self.cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
        except Exception as e:
            logger.error(f"Oturum getirme hatası: {e}")
            return None

    def aktif_oturum_al(self, grup=None):
        """Aktif oturumu al"""
        try:
            if grup:
                self.cursor.execute('''
                    SELECT * FROM oturumlar
                    WHERE durum = 'aktif' AND grup = ?
                    ORDER BY id DESC LIMIT 1
                ''', (grup,))
            else:
                self.cursor.execute('''
                    SELECT * FROM oturumlar
                    WHERE durum = 'aktif'
                    ORDER BY id DESC LIMIT 1
                ''')

            row = self.cursor.fetchone()
            if row:
                return self._row_to_dict(row)
            return None
        except Exception as e:
            logger.error(f"Aktif oturum alma hatası: {e}")
            return None

    def tum_oturumlari_getir(self, limit=100):
        """Tüm oturumları getir (en yeniden eskiye)"""
        try:
            self.cursor.execute('''
                SELECT * FROM oturumlar
                ORDER BY id DESC
                LIMIT ?
            ''', (limit,))

            rows = self.cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Oturumları getirme hatası: {e}")
            return []

    def grup_oturumlari_getir(self, grup, limit=100):
        """Belirli bir grubun oturumlarını getir"""
        try:
            self.cursor.execute('''
                SELECT * FROM oturumlar
                WHERE grup = ?
                ORDER BY id DESC
                LIMIT ?
            ''', (grup, limit))

            rows = self.cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Grup oturumları getirme hatası: {e}")
            return []

    def _row_to_dict(self, row):
        """SQLite row'u dictionary'e çevir"""
        if not row:
            return None

        return {
            'id': row[0],
            'baslangic_zamani': row[1],
            'bitis_zamani': row[2],
            'grup': row[3],
            'baslangic_recete': row[4],
            'bitis_recete': row[5],
            'toplam_recete': row[6],
            'toplam_takip': row[7],
            'yeniden_baslatma_sayisi': row[8],
            'taskkill_sayisi': row[9],
            'ortalama_recete_suresi': row[10],
            'durum': row[11]
        }

    def kapat(self):
        """Database bağlantısını kapat"""
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
                logger.info("✓ Database bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"Database kapatma hatası: {e}")


# Global singleton
_database = None

def get_database():
    """Global Database instance'ını al"""
    global _database
    if _database is None:
        _database = BotanikDatabase()
    return _database
