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
            # Giriş Bilgileri
            "kullanici_index": 0,  # Combobox'taki sıra (0=birinci, 1=ikinci, ...)
            "sifre": "",

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
        """Kullanıcı index ve şifre girilmiş mi?"""
        return (self.ayarlar.get("kullanici_index") is not None) and bool(self.ayarlar.get("sifre"))

    def masaustu_path_dolu_mu(self):
        """Masaüstü MEDULA path'i girilmiş mi?"""
        return bool(self.ayarlar.get("masaustu_medula_path"))


# Global singleton
_medula_settings = None

def get_medula_settings():
    """Global MedulaSettings instance'ını al"""
    global _medula_settings
    if _medula_settings is None:
        _medula_settings = MedulaSettings()
    return _medula_settings
