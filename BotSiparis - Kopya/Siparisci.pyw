"""
Botanik Sipariş Yardımcısı - Ana Giriş Noktası
"""
import sys
from src.controller import MainController
from src.gui.main_window import MainWindow
from src.utils import logger


def main():
    """Ana fonksiyon"""
    try:
        logger.info("=" * 60)
        logger.info("Botanik Sipariş Yardımcısı başlatılıyor...")
        logger.info("=" * 60)

        # Controller oluştur
        controller = MainController()

        # GUI oluştur
        gui = MainWindow(controller)
        controller.gui = gui
        controller.botanik.gui = gui  # Botanik controller'a da GUI referansını ekle

        logger.info("GUI başlatılıyor...")

        # GUI'yi çalıştır
        gui.run()

    except KeyboardInterrupt:
        logger.info("Program kullanıcı tarafından durduruldu")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
