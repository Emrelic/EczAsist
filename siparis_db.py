"""
Siparis Calismalari - SQLite Database Yoneticisi
Siparis oturumlarini ve kesin siparisleri kalici olarak saklar
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class SiparisDatabase:
    """Siparis calismalari icin SQLite database yoneticisi"""

    def __init__(self, db_dosya="siparis_calismalari.db"):
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_yolu = Path(script_dir) / db_dosya

        self.conn = None
        self.cursor = None
        self.baglanti_kur()
        self.tablolari_olustur()

    def baglanti_kur(self):
        """Database baglantisini kur"""
        try:
            self.conn = sqlite3.connect(str(self.db_yolu), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # Dict-like erişim
            self.cursor = self.conn.cursor()
            logger.info(f"Siparis DB baglantisi kuruldu: {self.db_yolu}")
        except Exception as e:
            logger.error(f"Siparis DB baglanti hatasi: {e}")
            raise

    def tablolari_olustur(self):
        """Gerekli tablolari olustur"""
        try:
            # Siparis calismalari (oturumlar)
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS siparis_calismalari (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ad TEXT NOT NULL,
                    olusturma_tarihi TEXT NOT NULL,
                    son_guncelleme TEXT NOT NULL,
                    durum TEXT DEFAULT 'aktif',
                    notlar TEXT,
                    parametreler TEXT
                )
            ''')

            # Kesin siparisler
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS kesin_siparisler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    calisma_id INTEGER NOT NULL,
                    urun_id INTEGER,
                    urun_adi TEXT NOT NULL,
                    barkod TEXT,
                    miktar INTEGER NOT NULL,
                    mf TEXT,
                    toplam INTEGER,
                    stok INTEGER,
                    aylik_ort REAL,
                    depo_bilgileri TEXT,
                    ekleme_tarihi TEXT NOT NULL,
                    FOREIGN KEY (calisma_id) REFERENCES siparis_calismalari(id)
                )
            ''')

            # Minimum stok analiz sonuclari
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS min_stok_analiz (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    urun_id INTEGER NOT NULL UNIQUE,
                    urun_adi TEXT NOT NULL,
                    stok INTEGER,
                    mevcut_min INTEGER,
                    aylik_ort REAL,
                    talep_sayisi INTEGER,
                    ort_parti REAL,
                    cv REAL,
                    adi REAL,
                    sinif TEXT,
                    min_bilimsel INTEGER,
                    min_finansal INTEGER,
                    min_onerilen INTEGER,
                    aciklama TEXT,
                    hesaplama_tarihi TEXT NOT NULL,
                    uygulanma_tarihi TEXT
                )
            ''')

            # Reçete ile sipariş tablosu
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS recete_ile_siparis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    urun_id INTEGER NOT NULL UNIQUE,
                    urun_adi TEXT NOT NULL,
                    ekleme_tarihi TEXT NOT NULL
                )
            ''')

            self.conn.commit()

            # Bitiş tarihi sütunu yoksa ekle
            try:
                self.cursor.execute("ALTER TABLE siparis_calismalari ADD COLUMN bitis_tarihi TEXT")
                self.conn.commit()
            except:
                pass  # Sütun zaten var

            logger.info("Siparis DB tablolari olusturuldu")
        except Exception as e:
            logger.error(f"Tablo olusturma hatasi: {e}")
            raise

    def yeni_calisma_olustur(self, ad=None, parametreler=None):
        """
        Yeni siparis calismasi olustur

        Args:
            ad: Calisma adi (None ise otomatik olusturulur)
            parametreler: dict - Calisma parametreleri (ay sayisi, faiz vb.)

        Returns:
            int: Yeni calisma ID
        """
        try:
            simdi = datetime.now()
            if ad is None:
                ad = simdi.strftime("%d.%m.%Y Siparis Calismasi")

            tarih_str = simdi.strftime("%Y-%m-%d %H:%M:%S")
            param_json = json.dumps(parametreler) if parametreler else None

            self.cursor.execute('''
                INSERT INTO siparis_calismalari (ad, olusturma_tarihi, son_guncelleme, durum, parametreler)
                VALUES (?, ?, ?, 'aktif', ?)
            ''', (ad, tarih_str, tarih_str, param_json))

            self.conn.commit()
            calisma_id = self.cursor.lastrowid
            logger.info(f"Yeni siparis calismasi olusturuldu: ID={calisma_id}, Ad={ad}")
            return calisma_id
        except Exception as e:
            logger.error(f"Calisma olusturma hatasi: {e}")
            return None

    def aktif_calisma_getir(self):
        """
        En son aktif calismayi getir

        Returns:
            dict veya None
        """
        try:
            self.cursor.execute('''
                SELECT * FROM siparis_calismalari
                WHERE durum = 'aktif'
                ORDER BY son_guncelleme DESC
                LIMIT 1
            ''')
            row = self.cursor.fetchone()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Aktif calisma getirme hatasi: {e}")
            return None

    def calisma_listesi_getir(self, limit=20):
        """
        Son calismalari listele

        Returns:
            list of dict
        """
        try:
            self.cursor.execute('''
                SELECT c.*,
                       (SELECT COUNT(*) FROM kesin_siparisler WHERE calisma_id = c.id) as siparis_sayisi
                FROM siparis_calismalari c
                ORDER BY c.son_guncelleme DESC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Calisma listesi hatasi: {e}")
            return []

    def calisma_guncelle(self, calisma_id, **kwargs):
        """Calisma bilgilerini guncelle"""
        try:
            kwargs['son_guncelleme'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            set_parts = []
            values = []
            for key, value in kwargs.items():
                set_parts.append(f"{key} = ?")
                values.append(value)

            values.append(calisma_id)

            sql = f"UPDATE siparis_calismalari SET {', '.join(set_parts)} WHERE id = ?"
            self.cursor.execute(sql, values)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Calisma guncelleme hatasi: {e}")
            return False

    def calisma_kapat(self, calisma_id):
        """Calismayi kapat (tamamlandi olarak isaretle, bitis tarihi ekle)"""
        bitis = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self.calisma_guncelle(calisma_id, durum='tamamlandi', bitis_tarihi=bitis)

    def calisma_istatistik_getir(self, calisma_id):
        """
        Çalışmanın istatistiklerini getir

        Returns:
            dict: kalem_sayisi, toplam_kutu, toplam_tutar
        """
        try:
            self.cursor.execute('''
                SELECT
                    COUNT(*) as kalem_sayisi,
                    COALESCE(SUM(toplam), 0) as toplam_kutu,
                    COALESCE(SUM(miktar * COALESCE(
                        (SELECT u.UrunFiyatEtiket * 0.71 * 1.10 FROM Urun u WHERE u.UrunId = kesin_siparisler.urun_id),
                        0
                    )), 0) as toplam_tutar
                FROM kesin_siparisler
                WHERE calisma_id = ?
            ''', (calisma_id,))
            row = self.cursor.fetchone()
            if row:
                return {
                    'kalem_sayisi': row[0] or 0,
                    'toplam_kutu': row[1] or 0,
                    'toplam_tutar': 0  # Basit hesap - fiyat bilgisi ayrı veritabanında
                }
            return {'kalem_sayisi': 0, 'toplam_kutu': 0, 'toplam_tutar': 0}
        except Exception as e:
            logger.error(f"Istatistik getirme hatasi: {e}")
            return {'kalem_sayisi': 0, 'toplam_kutu': 0, 'toplam_tutar': 0}

    def arsiv_listesi_getir(self, limit=50):
        """
        Tamamlanmış çalışmaları istatistiklerle getir

        Returns:
            list of dict
        """
        try:
            self.cursor.execute('''
                SELECT
                    c.id, c.ad, c.olusturma_tarihi, c.bitis_tarihi, c.durum,
                    (SELECT COUNT(*) FROM kesin_siparisler WHERE calisma_id = c.id) as kalem,
                    (SELECT COALESCE(SUM(toplam), 0) FROM kesin_siparisler WHERE calisma_id = c.id) as kutu
                FROM siparis_calismalari c
                ORDER BY c.olusturma_tarihi DESC
                LIMIT ?
            ''', (limit,))
            return [dict(zip(['id', 'ad', 'olusturma_tarihi', 'bitis_tarihi', 'durum', 'kalem', 'kutu'], row))
                    for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Arsiv listesi hatasi: {e}")
            return []

    def calisma_sil(self, calisma_id):
        """Calisma ve siparislerini sil"""
        try:
            self.cursor.execute('DELETE FROM kesin_siparisler WHERE calisma_id = ?', (calisma_id,))
            self.cursor.execute('DELETE FROM siparis_calismalari WHERE id = ?', (calisma_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Calisma silme hatasi: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # KESIN SIPARIS ISLEMLERI
    # ═══════════════════════════════════════════════════════════════════════

    def siparis_ekle(self, calisma_id, siparis_data):
        """
        Kesin siparise yeni urun ekle

        Args:
            calisma_id: Calisma ID
            siparis_data: dict - UrunId, UrunAdi, Barkod, Miktar, MF, Toplam, Stok, AylikOrt, DepoSonuclari

        Returns:
            int: Yeni siparis ID veya None
        """
        try:
            depo_json = json.dumps(siparis_data.get('DepoSonuclari', {})) if siparis_data.get('DepoSonuclari') else None
            tarih_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.cursor.execute('''
                INSERT INTO kesin_siparisler
                (calisma_id, urun_id, urun_adi, barkod, miktar, mf, toplam, stok, aylik_ort, depo_bilgileri, ekleme_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                calisma_id,
                siparis_data.get('UrunId'),
                siparis_data.get('UrunAdi', ''),
                siparis_data.get('Barkod', ''),
                siparis_data.get('Miktar', 0),
                siparis_data.get('MF', ''),
                siparis_data.get('Toplam', 0),
                siparis_data.get('Stok', 0),
                siparis_data.get('AylikOrt', 0),
                depo_json,
                tarih_str
            ))

            self.conn.commit()

            # Calisma son guncelleme tarihini guncelle
            self.calisma_guncelle(calisma_id)

            return self.cursor.lastrowid
        except Exception as e:
            logger.error(f"Siparis ekleme hatasi: {e}")
            return None

    def siparis_guncelle(self, siparis_id, **kwargs):
        """Siparis bilgilerini guncelle"""
        try:
            set_parts = []
            values = []
            for key, value in kwargs.items():
                set_parts.append(f"{key} = ?")
                values.append(value)

            values.append(siparis_id)

            sql = f"UPDATE kesin_siparisler SET {', '.join(set_parts)} WHERE id = ?"
            self.cursor.execute(sql, values)
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Siparis guncelleme hatasi: {e}")
            return False

    def siparis_sil(self, siparis_id):
        """Tek bir siparisi sil"""
        try:
            self.cursor.execute('DELETE FROM kesin_siparisler WHERE id = ?', (siparis_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Siparis silme hatasi: {e}")
            return False

    def calisma_siparisleri_getir(self, calisma_id):
        """
        Bir calismaya ait tum siparisleri getir

        Returns:
            list of dict
        """
        try:
            self.cursor.execute('''
                SELECT * FROM kesin_siparisler
                WHERE calisma_id = ?
                ORDER BY ekleme_tarihi ASC
            ''', (calisma_id,))

            siparisler = []
            for row in self.cursor.fetchall():
                siparis = dict(row)
                # Depo bilgilerini JSON'dan coz
                if siparis.get('depo_bilgileri'):
                    try:
                        siparis['DepoSonuclari'] = json.loads(siparis['depo_bilgileri'])
                    except:
                        siparis['DepoSonuclari'] = {}
                siparisler.append(siparis)

            return siparisler
        except Exception as e:
            logger.error(f"Siparisler getirme hatasi: {e}")
            return []

    def calisma_siparislerini_temizle(self, calisma_id):
        """Bir calismanin tum siparislerini sil"""
        try:
            self.cursor.execute('DELETE FROM kesin_siparisler WHERE calisma_id = ?', (calisma_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Siparisler temizleme hatasi: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # MINIMUM STOK ANALIZ ISLEMLERI
    # ═══════════════════════════════════════════════════════════════════════

    def min_stok_kaydet(self, analiz_data):
        """
        Minimum stok analiz sonucunu kaydet (UPSERT)

        Args:
            analiz_data: dict - UrunId, UrunAdi, Stok, MevcutMin, AylikOrt, vb.

        Returns:
            bool: Basarili mi
        """
        try:
            tarih_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.cursor.execute('''
                INSERT OR REPLACE INTO min_stok_analiz
                (urun_id, urun_adi, stok, mevcut_min, aylik_ort, talep_sayisi,
                 ort_parti, cv, adi, sinif, min_bilimsel, min_finansal,
                 min_onerilen, aciklama, hesaplama_tarihi)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                analiz_data.get('UrunId'),
                analiz_data.get('UrunAdi', ''),
                analiz_data.get('Stok', 0),
                analiz_data.get('MevcutMin', 0),
                analiz_data.get('AylikOrt', 0),
                analiz_data.get('TalepSayisi', 0),
                analiz_data.get('OrtParti', 0),
                analiz_data.get('CV', 0),
                analiz_data.get('ADI', 0),
                analiz_data.get('Sinif', ''),
                analiz_data.get('MinBilimsel', 0),
                analiz_data.get('MinFinansal', 0),
                analiz_data.get('MinOnerilen', 0),
                analiz_data.get('Aciklama', ''),
                tarih_str
            ))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Min stok kaydetme hatasi: {e}")
            return False

    def min_stok_toplu_kaydet(self, analiz_listesi, progress_callback=None):
        """
        Birden fazla min stok analizini toplu kaydet

        Args:
            analiz_listesi: list of dict
            progress_callback: (current, total) callback

        Returns:
            tuple: (basarili, hata)
        """
        basarili = 0
        hata = 0
        toplam = len(analiz_listesi)

        for i, analiz in enumerate(analiz_listesi):
            if progress_callback and i % 100 == 0:
                progress_callback(i, toplam)

            if self.min_stok_kaydet(analiz):
                basarili += 1
            else:
                hata += 1

        if progress_callback:
            progress_callback(toplam, toplam)

        return (basarili, hata)

    def min_stok_listesi_getir(self, sadece_degisiklik=False):
        """
        Kayitli min stok analizlerini getir

        Args:
            sadece_degisiklik: True ise sadece mevcut != onerilen olanlari getir

        Returns:
            list of dict
        """
        try:
            if sadece_degisiklik:
                self.cursor.execute('''
                    SELECT * FROM min_stok_analiz
                    WHERE mevcut_min != min_onerilen
                    ORDER BY urun_adi
                ''')
            else:
                self.cursor.execute('''
                    SELECT * FROM min_stok_analiz
                    ORDER BY urun_adi
                ''')

            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Min stok listesi hatasi: {e}")
            return []

    def min_stok_urun_getir(self, urun_id):
        """Tek bir urunun min stok analizini getir"""
        try:
            self.cursor.execute('''
                SELECT * FROM min_stok_analiz WHERE urun_id = ?
            ''', (urun_id,))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Min stok urun getirme hatasi: {e}")
            return None

    def min_stok_temizle(self):
        """Tum min stok kayitlarini sil"""
        try:
            self.cursor.execute('DELETE FROM min_stok_analiz')
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Min stok temizleme hatasi: {e}")
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # REÇETE İLE SİPARİŞ İŞLEMLERİ
    # ═══════════════════════════════════════════════════════════════════════

    def recete_ile_siparis_ekle(self, urun_id, urun_adi):
        """
        İlacı reçete ile sipariş listesine ekle (UPSERT)

        Args:
            urun_id: Ürün ID
            urun_adi: Ürün adı

        Returns:
            bool: Başarılı mı
        """
        try:
            tarih_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute('''
                INSERT OR REPLACE INTO recete_ile_siparis (urun_id, urun_adi, ekleme_tarihi)
                VALUES (?, ?, ?)
            ''', (urun_id, urun_adi, tarih_str))
            self.conn.commit()
            logger.info(f"Reçete ile sipariş eklendi: {urun_adi} (ID={urun_id})")
            return True
        except Exception as e:
            logger.error(f"Reçete ile sipariş ekleme hatası: {e}")
            return False

    def recete_ile_siparis_sil(self, urun_id):
        """İlacı reçete ile sipariş listesinden çıkar"""
        try:
            self.cursor.execute('DELETE FROM recete_ile_siparis WHERE urun_id = ?', (urun_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Reçete ile sipariş silme hatası: {e}")
            return False

    def recete_ile_siparis_listesi_getir(self):
        """
        Reçete ile sipariş listesindeki tüm ilaçları getir

        Returns:
            list of dict
        """
        try:
            self.cursor.execute('SELECT * FROM recete_ile_siparis ORDER BY urun_adi')
            return [dict(row) for row in self.cursor.fetchall()]
        except Exception as e:
            logger.error(f"Reçete ile sipariş listesi hatası: {e}")
            return []

    def recete_ile_siparis_mi(self, urun_id):
        """Ürünün reçete ile sipariş listesinde olup olmadığını kontrol et"""
        try:
            self.cursor.execute('SELECT 1 FROM recete_ile_siparis WHERE urun_id = ?', (urun_id,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Reçete ile sipariş kontrol hatası: {e}")
            return False

    def kapat(self):
        """Database baglantisini kapat"""
        if self.conn:
            self.conn.close()
            logger.info("Siparis DB baglantisi kapatildi")


# Singleton instance
_instance = None

def get_siparis_db():
    """Singleton siparis database instance'i getir"""
    global _instance
    if _instance is None:
        _instance = SiparisDatabase()
    return _instance
