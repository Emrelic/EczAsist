"""
Botanik Bot - MEDULA Ayarları Yöneticisi
MEDULA giriş bilgileri ve UI element tanımlamaları
"""

import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MedulaSettings:
    """MEDULA giriş bilgileri ve element ayarları"""

    def __init__(self, dosya_yolu="medula_settings.json"):
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.dosya_yolu = Path(script_dir) / dosya_yolu

        # Varsayılan ayarlar
        self.varsayilan_ayarlar = {
            # Çok Kullanıcılı Sistem
            "kullanicilar": [
                {
                    "ad": "Kullanıcı 1",
                    "kullanici_index": 0,  # MEDULA Combobox'taki sıra
                    "sifre": ""
                },
                {
                    "ad": "Kullanıcı 2",
                    "kullanici_index": 1,
                    "sifre": ""
                },
                {
                    "ad": "Kullanıcı 3",
                    "kullanici_index": 2,
                    "sifre": ""
                }
            ],
            "aktif_kullanici": 0,  # Hangi kullanıcı aktif (0, 1, 2)

            # MEDULA Program Yolu (SABİT)
            "medula_exe_path": r"C:\BotanikEczane\BotanikMedula.exe",

            # UI Element Tanımlamaları (Varsayılan)
            "giris_pencere_title": "BotanikEOS 2.1.199.0 (T)",
            "giris_pencere_automation_id": "SifreSorForm",

            # Kullanıcı Adı ComboBox
            "kullanici_combobox_class": "WindowsForms10.COMBOBOX.app.0.134c08f_r8_ad1",
            "kullanici_dropdown_button_name": "Kapat",

            # Şifre TextBox
            "sifre_textbox_automation_id": "txtSifre",
            "sifre_textbox_class": "WindowsForms10.EDIT.app.0.134c08f_r8_ad1",

            # Process
            "medula_process_name": "BotanikEczane.exe",

            # Giriş Butonu
            "giris_button_name": "Giriş",
        }

        self.ayarlar = self.yukle()

    def yukle(self):
        """Ayarları JSON dosyasından yükle"""
        if self.dosya_yolu.exists():
            try:
                with open(self.dosya_yolu, 'r', encoding='utf-8') as f:
                    yuklu_ayarlar = json.load(f)

                # ESKİ FORMAT'TAN YENİ FORMAT'A MİGRASYON
                # Eğer eski format kullanılıyorsa (kullanici_index ve sifre varsa)
                if "kullanici_index" in yuklu_ayarlar and "kullanicilar" not in yuklu_ayarlar:
                    logger.info("⚙ Eski ayar formatı tespit edildi, yeni formata dönüştürülüyor...")

                    # Eski bilgileri al
                    eski_index = yuklu_ayarlar.get("kullanici_index", 0)
                    eski_sifre = yuklu_ayarlar.get("sifre", "")

                    # Yeni yapıyı oluştur
                    yuklu_ayarlar["kullanicilar"] = [
                        {
                            "ad": "Kullanıcı 1",
                            "kullanici_index": eski_index,
                            "sifre": eski_sifre
                        },
                        {
                            "ad": "Kullanıcı 2",
                            "kullanici_index": 1,
                            "sifre": ""
                        },
                        {
                            "ad": "Kullanıcı 3",
                            "kullanici_index": 2,
                            "sifre": ""
                        }
                    ]
                    yuklu_ayarlar["aktif_kullanici"] = 0  # İlk kullanıcı aktif

                    # Eski anahtarları temizle
                    yuklu_ayarlar.pop("kullanici_index", None)
                    yuklu_ayarlar.pop("sifre", None)
                    yuklu_ayarlar.pop("kullanici_adi", None)

                    # Hemen kaydet
                    self.ayarlar = yuklu_ayarlar
                    self.kaydet()
                    logger.info("✓ Ayarlar yeni formata dönüştürüldü ve kaydedildi")

                # Yeni eklenen ayarları da ekle (varsa)
                for key, value in self.varsayilan_ayarlar.items():
                    if key not in yuklu_ayarlar:
                        yuklu_ayarlar[key] = value

                logger.info("✓ MEDULA ayarları yüklendi")
                return yuklu_ayarlar
            except Exception as e:
                logger.error(f"MEDULA ayar yükleme hatası: {e}")
                return self.varsayilan_ayarlar.copy()
        else:
            logger.info("⚠ MEDULA ayar dosyası bulunamadı, varsayılan ayarlar kullanılıyor")
            return self.varsayilan_ayarlar.copy()

    def kaydet(self):
        """Ayarları JSON dosyasına kaydet"""
        try:
            with open(self.dosya_yolu, 'w', encoding='utf-8') as f:
                json.dump(self.ayarlar, f, indent=2, ensure_ascii=False)
            logger.info("✓ MEDULA ayarları kaydedildi")
            return True
        except Exception as e:
            logger.error(f"MEDULA ayar kaydetme hatası: {e}")
            return False

    def get(self, anahtar, varsayilan=None):
        """Bir ayar değerini al"""
        return self.ayarlar.get(anahtar, varsayilan)

    def set(self, anahtar, deger):
        """Bir ayar değerini güncelle"""
        self.ayarlar[anahtar] = deger
        return True

    def kullanici_bilgileri_dolu_mu(self):
        """Aktif kullanıcının bilgileri dolu mu?"""
        kullanici = self.get_aktif_kullanici()
        if kullanici:
            return bool(kullanici.get("sifre"))
        return False

    def masaustu_path_dolu_mu(self):
        """Masaüstü MEDULA path'i girilmiş mi?"""
        return bool(self.ayarlar.get("masaustu_medula_path"))

    # ===== KULLANICI YÖNETİMİ =====

    def get_kullanicilar(self):
        """Tüm kullanıcıları getir"""
        return self.ayarlar.get("kullanicilar", [])

    def get_aktif_kullanici(self):
        """Aktif kullanıcının bilgilerini getir"""
        kullanicilar = self.get_kullanicilar()
        aktif_index = self.ayarlar.get("aktif_kullanici", 0)

        if 0 <= aktif_index < len(kullanicilar):
            return kullanicilar[aktif_index]
        elif len(kullanicilar) > 0:
            return kullanicilar[0]
        return None

    def set_aktif_kullanici(self, index):
        """Aktif kullanıcıyı ayarla (0, 1, 2)"""
        kullanicilar = self.get_kullanicilar()
        if 0 <= index < len(kullanicilar):
            self.ayarlar["aktif_kullanici"] = index
            return True
        return False

    def get_kullanici(self, index):
        """Belirli bir kullanıcıyı getir"""
        kullanicilar = self.get_kullanicilar()
        if 0 <= index < len(kullanicilar):
            return kullanicilar[index]
        return None

    def update_kullanici(self, index, ad=None, kullanici_index=None, sifre=None):
        """Kullanıcı bilgilerini güncelle"""
        kullanicilar = self.get_kullanicilar()

        if 0 <= index < len(kullanicilar):
            if ad is not None:
                kullanicilar[index]["ad"] = ad
            if kullanici_index is not None:
                kullanicilar[index]["kullanici_index"] = kullanici_index
            if sifre is not None:
                kullanicilar[index]["sifre"] = sifre

            self.ayarlar["kullanicilar"] = kullanicilar
            return True
        return False


# Global singleton
_medula_settings = None

def get_medula_settings():
    """Global MedulaSettings instance'ını al"""
    global _medula_settings
    if _medula_settings is None:
        _medula_settings = MedulaSettings()
    return _medula_settings
