"""
Botanik Bot - Oturum Log Dosyası Yöneticisi
Her oturumun loglarını ayrı txt dosyasına kaydeder
"""

from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SessionLogger:
    """Oturum loglarını dosyaya yazan sınıf"""

    def __init__(self, oturum_id, grup, log_klasoru="oturum_loglari"):
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_klasoru = Path(script_dir) / log_klasoru

        # Log klasörünü oluştur
        self.log_klasoru.mkdir(exist_ok=True)

        # Oturum bilgileri
        self.oturum_id = oturum_id
        self.grup = grup
        self.baslangic_zamani = datetime.now()

        # Log dosyası adı: oturum_1_GrupA_20250102_143025.txt
        timestamp = self.baslangic_zamani.strftime("%Y%m%d_%H%M%S")
        dosya_adi = f"oturum_{oturum_id}_Grup{grup}_{timestamp}.txt"
        self.log_dosya = self.log_klasoru / dosya_adi

        # Başlık yaz
        self.baslik_yaz()

    def baslik_yaz(self):
        """Log dosyasının başlığını yaz"""
        try:
            with open(self.log_dosya, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write(f"BOTANIK BOT - OTURUM LOGU\n")
                f.write("=" * 80 + "\n")
                f.write(f"Oturum ID: {self.oturum_id}\n")
                f.write(f"Grup: {self.grup}\n")
                f.write(f"Başlangıç: {self.baslangic_zamani.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
            logger.info(f"✓ Oturum log dosyası oluşturuldu: {self.log_dosya.name}")
        except Exception as e:
            logger.error(f"Log dosyası başlık yazma hatası: {e}")

    def yaz(self, mesaj, seviye="INFO"):
        """Log dosyasına mesaj yaz"""
        try:
            zaman = datetime.now().strftime("%H:%M:%S")
            satir = f"[{zaman}] [{seviye}] {mesaj}\n"

            with open(self.log_dosya, 'a', encoding='utf-8') as f:
                f.write(satir)
        except Exception as e:
            logger.error(f"Log yazma hatası: {e}")

    def info(self, mesaj):
        """INFO seviyesinde log yaz"""
        self.yaz(mesaj, "INFO")

    def warning(self, mesaj):
        """WARNING seviyesinde log yaz"""
        self.yaz(mesaj, "WARNING")

    def error(self, mesaj):
        """ERROR seviyesinde log yaz"""
        self.yaz(mesaj, "ERROR")

    def basari(self, mesaj):
        """BAŞARI seviyesinde log yaz"""
        self.yaz(mesaj, "BAŞARI")

    def ozet_yaz(self, toplam_recete, toplam_takip, toplam_sure, yeniden_baslatma, taskkill):
        """Oturum sonu özet yaz"""
        try:
            bitis_zamani = datetime.now()
            sure_fark = bitis_zamani - self.baslangic_zamani

            # Dakika ve saniyeye çevir
            toplam_saniye = sure_fark.total_seconds()
            dakika = int(toplam_saniye // 60)
            saniye = int(toplam_saniye % 60)

            with open(self.log_dosya, 'a', encoding='utf-8') as f:
                f.write("\n" + "=" * 80 + "\n")
                f.write("OTURUM ÖZETİ\n")
                f.write("=" * 80 + "\n")
                f.write(f"Bitiş: {bitis_zamani.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Toplam Süre: {dakika} dakika {saniye} saniye\n")
                f.write(f"Toplam Reçete: {toplam_recete}\n")
                f.write(f"Toplam Takip: {toplam_takip}\n")
                f.write(f"Ortalama Reçete Süresi: {toplam_sure:.2f} saniye\n")
                f.write(f"Yeniden Başlatma: {yeniden_baslatma} kez\n")
                f.write(f"Taskkill: {taskkill} kez\n")
                f.write("=" * 80 + "\n")

            logger.info(f"✓ Oturum özeti yazıldı: {self.log_dosya.name}")
        except Exception as e:
            logger.error(f"Özet yazma hatası: {e}")

    def kapat(self):
        """Log dosyasını kapat (son satır ekle)"""
        try:
            with open(self.log_dosya, 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.now().strftime('%H:%M:%S')}] Oturum log dosyası kapatıldı.\n")
        except Exception as e:
            logger.error(f"Log kapatma hatası: {e}")
