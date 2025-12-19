"""
Botanik Bot - Kullanıcı Yönetim Sistemi
Kullanıcı profilleri, şifreler ve yetkileri yönetir
"""

import sqlite3
import hashlib
import secrets
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class KullaniciYonetimi:
    """Kullanıcı ve yetki yönetim sistemi"""

    # Profil tipleri
    PROFILLER = {
        "admin": "Admin",
        "eczaci": "Eczacı",
        "kalfa": "Kalfa",
        "cirak": "Çırak",
        "stajyer": "Stajyer"
    }

    # Modüller (yetkilendirme için)
    MODULLER = {
        "ilac_takip": "İlaç Takip",
        "depo_ekstre": "Depo Ekstre Karşılaştırma",
        "kasa_takip": "Kasa Takibi",
        "rapor_kontrol": "Rapor Kontrol",
        "t_cetvel": "T Cetvel / Bilanço",
        "ek_raporlar": "Botanik Ek Raporlar",
        "mf_analiz": "MF Analiz Simülatörü",
        "kullanici_yonetimi": "Kullanıcı Yönetimi"
    }

    def __init__(self, db_dosya="oturum_raporlari.db"):
        """Veritabanı bağlantısını kur"""
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_yolu = Path(script_dir) / db_dosya

        self.baglanti_kur()
        self.tablolari_olustur()
        self.varsayilan_admin_olustur()

    def baglanti_kur(self):
        """Veritabanı bağlantısını kur"""
        try:
            self.conn = sqlite3.connect(str(self.db_yolu), check_same_thread=False)
            self.cursor = self.conn.cursor()
            logger.info(f"✓ Kullanıcı DB bağlantısı kuruldu")
        except Exception as e:
            logger.error(f"Kullanıcı DB bağlantı hatası: {e}")
            raise

    def tablolari_olustur(self):
        """Kullanıcı ve yetki tablolarını oluştur"""
        try:
            # Kullanıcılar tablosu
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS kullanicilar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kullanici_adi TEXT UNIQUE NOT NULL,
                    sifre_hash TEXT NOT NULL,
                    tuz TEXT NOT NULL,
                    ad_soyad TEXT,
                    profil TEXT NOT NULL DEFAULT 'stajyer',
                    aktif INTEGER DEFAULT 1,
                    olusturma_tarihi TEXT NOT NULL,
                    son_giris TEXT,
                    olusturan_id INTEGER,
                    FOREIGN KEY (olusturan_id) REFERENCES kullanicilar(id)
                )
            ''')

            # Yetkiler tablosu (kullanıcı-modül ilişkisi)
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS yetkiler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kullanici_id INTEGER NOT NULL,
                    modul TEXT NOT NULL,
                    yetkili INTEGER DEFAULT 1,
                    FOREIGN KEY (kullanici_id) REFERENCES kullanicilar(id),
                    UNIQUE(kullanici_id, modul)
                )
            ''')

            # Giriş logları tablosu
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS giris_loglari (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kullanici_id INTEGER,
                    kullanici_adi TEXT NOT NULL,
                    tarih TEXT NOT NULL,
                    basarili INTEGER NOT NULL,
                    ip_adresi TEXT,
                    detay TEXT,
                    FOREIGN KEY (kullanici_id) REFERENCES kullanicilar(id)
                )
            ''')

            # Sistem ayarları tablosu
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS sistem_ayarlari (
                    anahtar TEXT PRIMARY KEY,
                    deger TEXT NOT NULL
                )
            ''')

            self.conn.commit()
            logger.info("✓ Kullanıcı tabloları oluşturuldu")
        except Exception as e:
            logger.error(f"Tablo oluşturma hatası: {e}")
            raise

    def varsayilan_admin_olustur(self):
        """İlk kurulumda varsayılan admin kullanıcısını oluştur"""
        try:
            # Admin var mı kontrol et
            self.cursor.execute("SELECT id FROM kullanicilar WHERE kullanici_adi = 'admin'")
            if self.cursor.fetchone() is None:
                # Admin yok, oluştur
                self.kullanici_ekle(
                    kullanici_adi="admin",
                    sifre="admin123",
                    ad_soyad="Sistem Admin",
                    profil="admin",
                    olusturan_id=None  # Kendisi oluşturdu
                )
                logger.info("✓ Varsayılan admin kullanıcısı oluşturuldu (admin/admin123)")
        except Exception as e:
            logger.error(f"Varsayılan admin oluşturma hatası: {e}")

    def sifre_hashle(self, sifre, tuz=None):
        """Şifreyi hashle (SHA-256 + tuz)"""
        if tuz is None:
            tuz = secrets.token_hex(16)

        # SHA-256 ile hashle
        hash_obj = hashlib.sha256((sifre + tuz).encode('utf-8'))
        sifre_hash = hash_obj.hexdigest()

        return sifre_hash, tuz

    def sifre_dogrula(self, sifre, sifre_hash, tuz):
        """Şifreyi doğrula"""
        hesaplanan_hash, _ = self.sifre_hashle(sifre, tuz)
        return hesaplanan_hash == sifre_hash

    def sifre_gecerli_mi(self, sifre):
        """Şifre politikasını kontrol et (minimum 6 karakter)"""
        if len(sifre) < 6:
            return False, "Şifre en az 6 karakter olmalıdır"
        return True, ""

    def kullanici_ekle(self, kullanici_adi, sifre, ad_soyad=None, profil="stajyer", olusturan_id=None):
        """Yeni kullanıcı ekle"""
        try:
            # Şifre politikası kontrolü
            gecerli, mesaj = self.sifre_gecerli_mi(sifre)
            if not gecerli:
                return False, mesaj

            # Kullanıcı adı kontrolü
            self.cursor.execute("SELECT id FROM kullanicilar WHERE kullanici_adi = ?", (kullanici_adi,))
            if self.cursor.fetchone() is not None:
                return False, "Bu kullanıcı adı zaten kullanılıyor"

            # Şifreyi hashle
            sifre_hash, tuz = self.sifre_hashle(sifre)

            # Kullanıcıyı ekle
            olusturma_tarihi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.cursor.execute('''
                INSERT INTO kullanicilar (kullanici_adi, sifre_hash, tuz, ad_soyad, profil, olusturma_tarihi, olusturan_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (kullanici_adi, sifre_hash, tuz, ad_soyad, profil, olusturma_tarihi, olusturan_id))

            kullanici_id = self.cursor.lastrowid

            # Admin ise tüm modüllere yetki ver
            if profil == "admin":
                for modul in self.MODULLER.keys():
                    self.yetki_ver(kullanici_id, modul)

            self.conn.commit()
            logger.info(f"✓ Kullanıcı eklendi: {kullanici_adi} ({profil})")
            return True, kullanici_id

        except Exception as e:
            logger.error(f"Kullanıcı ekleme hatası: {e}")
            return False, str(e)

    def giris_yap(self, kullanici_adi, sifre):
        """Kullanıcı girişi yap"""
        try:
            # Kullanıcıyı bul
            self.cursor.execute('''
                SELECT id, sifre_hash, tuz, profil, aktif, ad_soyad
                FROM kullanicilar
                WHERE kullanici_adi = ?
            ''', (kullanici_adi,))

            sonuc = self.cursor.fetchone()

            if sonuc is None:
                self._giris_logla(None, kullanici_adi, False, "Kullanıcı bulunamadı")
                return False, "Kullanıcı adı veya şifre hatalı", None

            kullanici_id, sifre_hash, tuz, profil, aktif, ad_soyad = sonuc

            # Aktif mi kontrol et
            if not aktif:
                self._giris_logla(kullanici_id, kullanici_adi, False, "Hesap devre dışı")
                return False, "Bu hesap devre dışı bırakılmış", None

            # Şifre doğrula
            if not self.sifre_dogrula(sifre, sifre_hash, tuz):
                self._giris_logla(kullanici_id, kullanici_adi, False, "Yanlış şifre")
                return False, "Kullanıcı adı veya şifre hatalı", None

            # Giriş başarılı - son giriş tarihini güncelle
            son_giris = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute('''
                UPDATE kullanicilar SET son_giris = ? WHERE id = ?
            ''', (son_giris, kullanici_id))
            self.conn.commit()

            self._giris_logla(kullanici_id, kullanici_adi, True, "Başarılı giriş")

            # Kullanıcı bilgilerini döndür
            kullanici = {
                'id': kullanici_id,
                'kullanici_adi': kullanici_adi,
                'ad_soyad': ad_soyad,
                'profil': profil,
                'son_giris': son_giris
            }

            logger.info(f"✓ Giriş başarılı: {kullanici_adi} ({profil})")
            return True, "Giriş başarılı", kullanici

        except Exception as e:
            logger.error(f"Giriş hatası: {e}")
            return False, str(e), None

    def _giris_logla(self, kullanici_id, kullanici_adi, basarili, detay):
        """Giriş denemesini logla"""
        try:
            tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute('''
                INSERT INTO giris_loglari (kullanici_id, kullanici_adi, tarih, basarili, detay)
                VALUES (?, ?, ?, ?, ?)
            ''', (kullanici_id, kullanici_adi, tarih, 1 if basarili else 0, detay))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Giriş loglama hatası: {e}")

    def yetki_ver(self, kullanici_id, modul):
        """Kullanıcıya modül yetkisi ver"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO yetkiler (kullanici_id, modul, yetkili)
                VALUES (?, ?, 1)
            ''', (kullanici_id, modul))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Yetki verme hatası: {e}")
            return False

    def yetki_kaldir(self, kullanici_id, modul):
        """Kullanıcının modül yetkisini kaldır"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO yetkiler (kullanici_id, modul, yetkili)
                VALUES (?, ?, 0)
            ''', (kullanici_id, modul))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Yetki kaldırma hatası: {e}")
            return False

    def yetki_kontrol(self, kullanici_id, modul):
        """Kullanıcının modül yetkisi var mı kontrol et"""
        try:
            # Önce profili kontrol et - Admin her şeye erişebilir
            self.cursor.execute("SELECT profil FROM kullanicilar WHERE id = ?", (kullanici_id,))
            sonuc = self.cursor.fetchone()
            if sonuc and sonuc[0] == "admin":
                return True

            # Yetki tablosunu kontrol et
            self.cursor.execute('''
                SELECT yetkili FROM yetkiler
                WHERE kullanici_id = ? AND modul = ?
            ''', (kullanici_id, modul))

            sonuc = self.cursor.fetchone()
            if sonuc is None:
                return False  # Yetki tanımlanmamış

            return sonuc[0] == 1

        except Exception as e:
            logger.error(f"Yetki kontrol hatası: {e}")
            return False

    def kullanici_yetkilerini_al(self, kullanici_id):
        """Kullanıcının tüm yetkilerini al"""
        try:
            yetkiler = {}

            # Profil kontrolü
            self.cursor.execute("SELECT profil FROM kullanicilar WHERE id = ?", (kullanici_id,))
            sonuc = self.cursor.fetchone()

            if sonuc and sonuc[0] == "admin":
                # Admin tüm modüllere erişebilir
                for modul in self.MODULLER.keys():
                    yetkiler[modul] = True
                return yetkiler

            # Normal kullanıcı için yetkileri al
            for modul in self.MODULLER.keys():
                yetkiler[modul] = self.yetki_kontrol(kullanici_id, modul)

            return yetkiler

        except Exception as e:
            logger.error(f"Yetkileri alma hatası: {e}")
            return {}

    def kullanici_yetkilerini_guncelle(self, kullanici_id, yetkiler):
        """Kullanıcının tüm yetkilerini güncelle"""
        try:
            for modul, yetkili in yetkiler.items():
                if yetkili:
                    self.yetki_ver(kullanici_id, modul)
                else:
                    self.yetki_kaldir(kullanici_id, modul)
            return True
        except Exception as e:
            logger.error(f"Yetki güncelleme hatası: {e}")
            return False

    def tum_kullanicilari_al(self):
        """Tüm kullanıcıları listele"""
        try:
            self.cursor.execute('''
                SELECT id, kullanici_adi, ad_soyad, profil, aktif, olusturma_tarihi, son_giris
                FROM kullanicilar
                ORDER BY id
            ''')

            kullanicilar = []
            for row in self.cursor.fetchall():
                kullanicilar.append({
                    'id': row[0],
                    'kullanici_adi': row[1],
                    'ad_soyad': row[2],
                    'profil': row[3],
                    'aktif': row[4] == 1,
                    'olusturma_tarihi': row[5],
                    'son_giris': row[6]
                })

            return kullanicilar

        except Exception as e:
            logger.error(f"Kullanıcıları listeleme hatası: {e}")
            return []

    def kullanici_guncelle(self, kullanici_id, **kwargs):
        """Kullanıcı bilgilerini güncelle"""
        try:
            guncellenecek = []
            degerler = []

            for alan, deger in kwargs.items():
                if alan in ['ad_soyad', 'profil', 'aktif']:
                    guncellenecek.append(f"{alan} = ?")
                    degerler.append(deger)

            if not guncellenecek:
                return False, "Güncellenecek alan yok"

            degerler.append(kullanici_id)
            sorgu = f"UPDATE kullanicilar SET {', '.join(guncellenecek)} WHERE id = ?"

            self.cursor.execute(sorgu, degerler)
            self.conn.commit()

            return True, "Kullanıcı güncellendi"

        except Exception as e:
            logger.error(f"Kullanıcı güncelleme hatası: {e}")
            return False, str(e)

    def sifre_degistir(self, kullanici_id, yeni_sifre):
        """Kullanıcı şifresini değiştir"""
        try:
            # Şifre politikası kontrolü
            gecerli, mesaj = self.sifre_gecerli_mi(yeni_sifre)
            if not gecerli:
                return False, mesaj

            # Yeni şifreyi hashle
            sifre_hash, tuz = self.sifre_hashle(yeni_sifre)

            self.cursor.execute('''
                UPDATE kullanicilar SET sifre_hash = ?, tuz = ? WHERE id = ?
            ''', (sifre_hash, tuz, kullanici_id))

            self.conn.commit()
            logger.info(f"✓ Şifre değiştirildi: kullanici_id={kullanici_id}")
            return True, "Şifre başarıyla değiştirildi"

        except Exception as e:
            logger.error(f"Şifre değiştirme hatası: {e}")
            return False, str(e)

    def kullanici_sil(self, kullanici_id):
        """Kullanıcıyı sil (sadece devre dışı bırak)"""
        try:
            # Admin silinemesin
            self.cursor.execute("SELECT kullanici_adi FROM kullanicilar WHERE id = ?", (kullanici_id,))
            sonuc = self.cursor.fetchone()
            if sonuc and sonuc[0] == "admin":
                return False, "Admin kullanıcısı silinemez"

            # Kullanıcıyı devre dışı bırak
            self.cursor.execute("UPDATE kullanicilar SET aktif = 0 WHERE id = ?", (kullanici_id,))
            self.conn.commit()

            return True, "Kullanıcı devre dışı bırakıldı"

        except Exception as e:
            logger.error(f"Kullanıcı silme hatası: {e}")
            return False, str(e)

    def kullanici_aktiflestir(self, kullanici_id):
        """Devre dışı kullanıcıyı tekrar aktifleştir"""
        try:
            self.cursor.execute("UPDATE kullanicilar SET aktif = 1 WHERE id = ?", (kullanici_id,))
            self.conn.commit()
            return True, "Kullanıcı aktifleştirildi"
        except Exception as e:
            logger.error(f"Kullanıcı aktifleştirme hatası: {e}")
            return False, str(e)

    def sistem_ayari_al(self, anahtar, varsayilan=None):
        """Sistem ayarı al"""
        try:
            self.cursor.execute(
                "SELECT deger FROM sistem_ayarlari WHERE anahtar = ?",
                (anahtar,)
            )
            sonuc = self.cursor.fetchone()
            if sonuc:
                return sonuc[0]
            return varsayilan
        except Exception as e:
            logger.error(f"Sistem ayarı alma hatası: {e}")
            return varsayilan

    def sistem_ayari_kaydet(self, anahtar, deger):
        """Sistem ayarı kaydet"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO sistem_ayarlari (anahtar, deger)
                VALUES (?, ?)
            ''', (anahtar, str(deger)))
            self.conn.commit()
            logger.info(f"✓ Sistem ayarı kaydedildi: {anahtar}={deger}")
            return True
        except Exception as e:
            logger.error(f"Sistem ayarı kaydetme hatası: {e}")
            return False

    def sifresiz_kullanim_aktif_mi(self):
        """Şifresiz kullanım aktif mi kontrol et"""
        deger = self.sistem_ayari_al("sifresiz_kullanim", "0")
        return deger == "1"

    def sifresiz_kullanim_ayarla(self, aktif):
        """Şifresiz kullanım ayarını değiştir"""
        return self.sistem_ayari_kaydet("sifresiz_kullanim", "1" if aktif else "0")

    def sifresiz_giris_yap(self):
        """Şifresiz giriş yap (admin olarak)"""
        try:
            # Admin kullanıcısını al
            self.cursor.execute('''
                SELECT id, profil, ad_soyad
                FROM kullanicilar
                WHERE kullanici_adi = 'admin' AND aktif = 1
            ''')
            sonuc = self.cursor.fetchone()

            if sonuc:
                kullanici_id, profil, ad_soyad = sonuc

                # Son giriş tarihini güncelle
                son_giris = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.cursor.execute('''
                    UPDATE kullanicilar SET son_giris = ? WHERE id = ?
                ''', (son_giris, kullanici_id))
                self.conn.commit()

                self._giris_logla(kullanici_id, "admin", True, "Şifresiz giriş")

                kullanici = {
                    'id': kullanici_id,
                    'kullanici_adi': 'admin',
                    'ad_soyad': ad_soyad,
                    'profil': profil,
                    'son_giris': son_giris
                }

                logger.info("✓ Şifresiz giriş yapıldı (admin)")
                return True, "Şifresiz giriş başarılı", kullanici

            return False, "Admin kullanıcısı bulunamadı", None

        except Exception as e:
            logger.error(f"Şifresiz giriş hatası: {e}")
            return False, str(e), None

    def kapat(self):
        """Veritabanı bağlantısını kapat"""
        try:
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
                logger.info("✓ Kullanıcı DB bağlantısı kapatıldı")
        except Exception as e:
            logger.error(f"DB kapatma hatası: {e}")


# Global singleton
_kullanici_yonetimi = None

def get_kullanici_yonetimi():
    """Global KullaniciYonetimi instance'ını al"""
    global _kullanici_yonetimi
    if _kullanici_yonetimi is None:
        _kullanici_yonetimi = KullaniciYonetimi()
    return _kullanici_yonetimi
