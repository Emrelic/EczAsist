"""
Botanik Bot - Zamanlama Ayarları Yöneticisi
Her işlem için bekleme sürelerini yönetir ve saklar
"""

import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class TimingSettings:
    """Zamanlama ayarlarını yöneten sınıf"""

    def __init__(self, dosya_yolu="timing_settings.json", istatistik_dosya="timing_stats.json"):
        # Dosyayı script'in bulunduğu dizine kaydet
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.dosya_yolu = Path(script_dir) / dosya_yolu
        self.istatistik_dosya = Path(script_dir) / istatistik_dosya

        # İstatistikler: {anahtar: {"count": 0, "total_time": 0.0}}
        self.istatistikler = self.istatistik_yukle()

        # Varsayılan ayarlar (saniye cinsinden)
        self.varsayilan_ayarlar = {
            # Pencere İşlemleri
            "pencere_restore": 0.225,           # Pencere restore edildiğinde
            "pencere_move": 0.075,              # Pencere taşındığında
            "pencere_bulma": 0.075,             # Yeni pencere aranırken

            # Buton Tıklamaları
            "ilac_butonu": 0.225,               # İlaç butonuna tıklama
            "y_butonu": 0.15,                   # Y butonuna tıklama
            "geri_don_butonu": 0.09,            # Geri Dön butonuna tıklama
            "sonra_butonu": 0.075,              # SONRA butonuna tıklama
            "kapat_butonu": 0.045,              # Pencere Kapat butonuna tıklama
            "takip_et": 0.09,                   # Takip Et tıklama

            # Sayfa Geçişleri
            "recete_sorgu": 0.375,              # Reçete Sorgu açma
            "ana_sayfa": 0.75,                  # Ana Sayfa'ya dönme
            "sorgula_butonu": 0.375,            # Sorgula butonuna tıklama

            # Veri Girişi
            "text_focus": 0.15,                 # Metin kutusuna focus
            "text_clear": 0.075,                # Metin temizleme
            "text_write": 0.15,                 # Metin yazma

            # Popup/Dialog İşlemleri
            "popup_kapat": 0.03,                # Popup kapatma (hızlı)
            "uyari_kapat": 0.03,                # Uyarı kapatma (hızlı)
            "laba_uyari": 0.075,                # LABA/LAMA uyarısı kapatma

            # Diğer İşlemler
            "ilac_ekran_bekleme": 0.15,         # İlaç ekranı yükleme kontrolü
            "ilac_secim_bekleme": 0.045,        # İlaç seçimi sonrası
            "sag_tik": 0.12,                    # Sağ tık menü açılması
            "genel_gecis": 0.045,               # Genel pencere geçişleri

            # LABA/LAMA ve Yeniden Deneme
            "laba_sonrasi_bekleme": 0.3,        # LABA kapatıldıktan sonra
            "y_ikinci_deneme": 0.225,           # Y butonu 2. deneme

            # Masaüstü İşlemleri
            "masaustu_simge_tiklama": 1.0,      # Masaüstü simgesine çift tıklama
            "masaustu_simge_bekleme": 3.0,      # Simge tıklandıktan sonra program açılmasını bekleme

            # MEDULA Giriş İşlemleri
            "giris_pencere_bekleme": 2.0,       # Giriş penceresinin açılmasını bekleme
            "kullanici_combobox_ac": 0.5,       # Kullanıcı combobox'ını açma
            "kullanici_secim": 0.5,             # Kullanıcı seçimi
            "sifre_yazma": 0.5,                 # Şifre yazma
            "giris_butonu": 1.0,                # Giriş butonuna tıklama
            "giris_sonrasi_bekleme": 5.0,       # Giriş sonrası ana sayfanın açılmasını bekleme

            # Reçete Listesi İşlemleri
            "recete_listesi_butonu": 1.0,       # Reçete Listesi butonuna tıklama
            "recete_listesi_acilma": 2.0,       # Reçete Listesi ekranının açılmasını bekleme
            "donem_combobox_tiklama": 0.5,      # Dönem combobox'ına tıklama
            "donem_secim": 1.0,                 # Dönem seçimi
            "grup_butonu_tiklama": 1.0,         # A/B/C grup butonuna tıklama
            "grup_sorgulama": 2.0,              # Grup sorgulama sonrası bekleme
            "bulunamadi_mesaji_kontrol": 1.0,   # "Bu döneme ait sonlandırılmamış reçete bulunamadı" mesajı kontrolü
            "ilk_recete_tiklama": 1.0,          # İlk reçeteye tıklama
            "recete_acilma": 2.0,               # Reçete ekranının açılmasını bekleme

            # Genel Adım Arası Bekleme
            "adim_arasi_bekleme": 1.0,          # Her adım arasında varsayılan bekleme (1 saniye)
        }

        self.ayarlar = self.yukle()

    def yukle(self):
        """Ayarları JSON dosyasından yükle"""
        if self.dosya_yolu.exists():
            try:
                with open(self.dosya_yolu, 'r', encoding='utf-8') as f:
                    yuklu_ayarlar = json.load(f)

                # Yeni eklenen ayarları da ekle (varsa)
                for key, value in self.varsayilan_ayarlar.items():
                    if key not in yuklu_ayarlar:
                        yuklu_ayarlar[key] = value

                logger.info("✓ Zamanlama ayarları yüklendi")
                return yuklu_ayarlar
            except Exception as e:
                logger.error(f"Ayar yükleme hatası: {e}")
                return self.varsayilan_ayarlar.copy()
        else:
            logger.info("⚠ Ayar dosyası bulunamadı, varsayılan ayarlar kullanılıyor")
            return self.varsayilan_ayarlar.copy()

    def kaydet(self):
        """Ayarları JSON dosyasına kaydet"""
        try:
            with open(self.dosya_yolu, 'w', encoding='utf-8') as f:
                json.dump(self.ayarlar, f, indent=2, ensure_ascii=False)
            logger.info("✓ Zamanlama ayarları kaydedildi")
            return True
        except Exception as e:
            logger.error(f"Ayar kaydetme hatası: {e}")
            return False

    def get(self, anahtar, varsayilan=0.1):
        """Bir ayar değerini al"""
        return self.ayarlar.get(anahtar, varsayilan)

    def set(self, anahtar, deger):
        """Bir ayar değerini güncelle"""
        if isinstance(deger, (int, float)) and deger >= 0:
            self.ayarlar[anahtar] = float(deger)
            return True
        return False

    def varsayilana_don(self):
        """Tüm ayarları varsayılana döndür"""
        self.ayarlar = self.varsayilan_ayarlar.copy()
        self.kaydet()
        logger.info("✓ Ayarlar varsayılana döndürüldü")

    def hepsini_carpanla_guncelle(self, carpan):
        """Tüm ayarları bir çarpan ile güncelle"""
        if isinstance(carpan, (int, float)) and carpan > 0:
            for key in self.ayarlar:
                self.ayarlar[key] = round(self.varsayilan_ayarlar[key] * carpan, 3)
            self.kaydet()
            logger.info(f"✓ Tüm ayarlar {carpan}x ile güncellendi")
            return True
        return False

    def kategori_listesi(self):
        """Ayarları kategorilere göre grupla"""
        return {
            "Pencere İşlemleri": [
                ("pencere_restore", "Pencere Restore"),
                ("pencere_move", "Pencere Taşıma"),
                ("pencere_bulma", "Pencere Bulma"),
            ],
            "Buton Tıklamaları": [
                ("ilac_butonu", "İlaç Butonu"),
                ("y_butonu", "Y Butonu"),
                ("geri_don_butonu", "Geri Dön"),
                ("sonra_butonu", "SONRA Butonu"),
                ("kapat_butonu", "Kapat Butonu"),
                ("takip_et", "Takip Et"),
            ],
            "Sayfa Geçişleri": [
                ("recete_sorgu", "Reçete Sorgu"),
                ("ana_sayfa", "Ana Sayfa"),
                ("sorgula_butonu", "Sorgula Butonu"),
            ],
            "Veri Girişi": [
                ("text_focus", "Metin Focus"),
                ("text_clear", "Metin Temizleme"),
                ("text_write", "Metin Yazma"),
            ],
            "Popup/Dialog": [
                ("popup_kapat", "Popup Kapat"),
                ("uyari_kapat", "Uyarı Kapat"),
                ("laba_uyari", "LABA/LAMA Uyarı"),
            ],
            "Masaüstü İşlemleri": [
                ("masaustu_simge_tiklama", "Simge Tıklama"),
                ("masaustu_simge_bekleme", "Simge Bekleme"),
            ],
            "MEDULA Giriş": [
                ("giris_pencere_bekleme", "Giriş Pencere"),
                ("kullanici_combobox_ac", "Kullanıcı Combobox Aç"),
                ("kullanici_secim", "Kullanıcı Seçim"),
                ("sifre_yazma", "Şifre Yazma"),
                ("giris_butonu", "Giriş Butonu"),
                ("giris_sonrasi_bekleme", "Giriş Sonrası"),
            ],
            "Reçete Listesi": [
                ("recete_listesi_butonu", "Liste Butonu"),
                ("recete_listesi_acilma", "Liste Açılma"),
                ("donem_combobox_tiklama", "Dönem Combobox"),
                ("donem_secim", "Dönem Seçim"),
                ("grup_butonu_tiklama", "Grup Butonu"),
                ("grup_sorgulama", "Grup Sorgulama"),
                ("bulunamadi_mesaji_kontrol", "Bulunamadı Mesaj"),
                ("ilk_recete_tiklama", "İlk Reçete Tıklama"),
                ("recete_acilma", "Reçete Açılma"),
            ],
            "Diğer İşlemler": [
                ("ilac_ekran_bekleme", "İlaç Ekran Kontrol"),
                ("ilac_secim_bekleme", "İlaç Seçim"),
                ("sag_tik", "Sağ Tık"),
                ("genel_gecis", "Genel Geçiş"),
                ("laba_sonrasi_bekleme", "LABA Sonrası"),
                ("y_ikinci_deneme", "Y 2. Deneme"),
                ("adim_arasi_bekleme", "Adım Arası Bekleme"),
            ],
        }

    def istatistik_yukle(self):
        """İstatistikleri JSON dosyasından yükle"""
        if self.istatistik_dosya.exists():
            try:
                with open(self.istatistik_dosya, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"İstatistik yükleme hatası: {e}")
                return {}
        return {}

    def istatistik_kaydet(self):
        """İstatistikleri JSON dosyasına kaydet"""
        try:
            with open(self.istatistik_dosya, 'w', encoding='utf-8') as f:
                json.dump(self.istatistikler, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"İstatistik kaydetme hatası: {e}")
            return False

    def kayit_ekle(self, anahtar, gercek_sure):
        """Bir işlem için gerçek süreyi kaydet"""
        if anahtar not in self.istatistikler:
            self.istatistikler[anahtar] = {"count": 0, "total_time": 0.0}

        self.istatistikler[anahtar]["count"] += 1
        self.istatistikler[anahtar]["total_time"] += gercek_sure

        # Her 10 kayıtta bir otomatik kaydet
        if self.istatistikler[anahtar]["count"] % 10 == 0:
            self.istatistik_kaydet()

    def ortalama_al(self, anahtar):
        """Bir işlem için ortalama süreyi hesapla"""
        if anahtar in self.istatistikler:
            stats = self.istatistikler[anahtar]
            if stats["count"] > 0:
                return stats["total_time"] / stats["count"]
        return None

    def istatistik_al(self, anahtar):
        """Bir işlem için tam istatistiği al"""
        return self.istatistikler.get(anahtar, {"count": 0, "total_time": 0.0})

    def istatistik_sifirla(self):
        """Tüm istatistikleri sıfırla"""
        self.istatistikler = {}
        self.istatistik_kaydet()
        logger.info("✓ İstatistikler sıfırlandı")


# Global singleton
_timing_settings = None

def get_timing_settings():
    """Global TimingSettings instance'ını al"""
    global _timing_settings
    if _timing_settings is None:
        _timing_settings = TimingSettings()
    return _timing_settings
