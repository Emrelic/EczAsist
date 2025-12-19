#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Botanik Takip Sistemi - Ana Başlatma Dosyası
Giriş ekranı ile başlar, başarılı girişte ana menüyü açar
"""

import logging
import sys
import os

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def uygulama_baslat():
    """Uygulamayı başlat"""
    try:
        logger.info("=" * 50)
        logger.info("Botanik Takip Sistemi başlatılıyor...")
        logger.info("=" * 50)

        # Giriş penceresini import et
        from giris_penceresi import GirisPenceresi
        from ana_menu import AnaMenu

        def giris_basarili(kullanici):
            """Giriş başarılı olduğunda ana menüyü aç"""
            logger.info(f"Giriş başarılı: {kullanici['kullanici_adi']} ({kullanici['profil']})")

            # Ana menüyü başlat
            ana_menu = AnaMenu(kullanici)
            ana_menu.calistir()

        # Giriş penceresini göster
        giris = GirisPenceresi(on_giris_basarili=giris_basarili)
        giris.calistir()

    except ImportError as e:
        logger.error(f"Modül import hatası: {e}")
        print(f"\nHATA: Gerekli modül bulunamadı: {e}")
        print("Lütfen tüm dosyaların mevcut olduğundan emin olun.")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Uygulama başlatma hatası: {e}", exc_info=True)
        print(f"\nHATA: Uygulama başlatılamadı: {e}")
        sys.exit(1)


def eski_sistem_baslat():
    """Eski sistemi başlat (giriş olmadan direkt botanik_gui)"""
    try:
        import tkinter as tk
        from botanik_gui import BotanikGUI

        logger.info("Eski sistem başlatılıyor (giriş atlandı)...")

        root = tk.Tk()
        app = BotanikGUI(root)
        root.mainloop()

    except Exception as e:
        logger.error(f"Eski sistem başlatma hatası: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Komut satırı argümanlarını kontrol et
    if len(sys.argv) > 1:
        if sys.argv[1] == "--eski" or sys.argv[1] == "-e":
            # Eski sistemi başlat (giriş ekranı olmadan)
            eski_sistem_baslat()
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("""
Botanik Takip Sistemi v2.0

Kullanım:
  python main.py           : Normal başlatma (giriş ekranı ile)
  python main.py --eski    : Eski sistem (giriş olmadan direkt ilaç takip)
  python main.py --help    : Bu yardım mesajı

Varsayılan Admin Bilgileri:
  Kullanıcı: admin
  Şifre: admin123 (ilk girişte değiştirmeniz önerilir)
            """)
        else:
            print(f"Bilinmeyen argüman: {sys.argv[1]}")
            print("Yardım için: python main.py --help")
    else:
        # Normal başlatma
        uygulama_baslat()
