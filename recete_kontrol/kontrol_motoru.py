# -*- coding: utf-8 -*-
"""
Kontrol Motoru

Tüm reçete kontrol sınıflarını yönetir ve koordine eder.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime

from .base_kontrol import BaseKontrol, KontrolRaporu, KontrolSonucu

logger = logging.getLogger(__name__)


class KontrolMotoru:
    """
    Reçete kontrol motorü.

    - Kayıtlı kontrol sınıflarını yönetir
    - Kontrol edilen reçeteleri hafızada tutar
    - Sonuçları raporlar
    """

    def __init__(self, hafiza_dosyasi: str = "kontrol_edilenler.json"):
        # Kontrol sınıfları listesi
        self.kontrol_siniflari: List[BaseKontrol] = []

        # Kontrol edilen reçeteler hafızası
        script_dir = Path(__file__).parent.parent
        self.hafiza_dosyasi = script_dir / hafiza_dosyasi
        self.kontrol_edilenler: Set[str] = self._hafizayi_yukle()

        # Kayıtlı kontrol sınıflarını yükle
        self._kontrolleri_kaydet()

    def _kontrolleri_kaydet(self):
        """Mevcut kontrol sınıflarını kaydet"""
        # Şimdilik boş - yeni kontrol sınıfları eklendikçe buraya import edilecek
        # Örnek:
        # from .antibiyotik import AntibiyotikKontrol
        # self.kontrol_ekle(AntibiyotikKontrol())
        pass

    def kontrol_ekle(self, kontrol: BaseKontrol):
        """Yeni bir kontrol sınıfı ekle"""
        self.kontrol_siniflari.append(kontrol)
        logger.info(f"Kontrol sınıfı eklendi: {kontrol.GRUP_ADI}")

    def _hafizayi_yukle(self) -> Set[str]:
        """Kontrol edilen reçeteleri dosyadan yükle"""
        if self.hafiza_dosyasi.exists():
            try:
                with open(self.hafiza_dosyasi, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get('kontrol_edilenler', []))
            except Exception as e:
                logger.error(f"Hafıza yükleme hatası: {e}")
        return set()

    def _hafizayi_kaydet(self):
        """Kontrol edilen reçeteleri dosyaya kaydet"""
        try:
            data = {
                'son_guncelleme': datetime.now().isoformat(),
                'kontrol_edilenler': list(self.kontrol_edilenler)
            }
            with open(self.hafiza_dosyasi, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Hafıza kaydetme hatası: {e}")

    def daha_once_kontrol_edildi_mi(self, recete_no: str) -> bool:
        """
        Reçetenin daha önce kontrol edilip edilmediğini kontrol et.

        Args:
            recete_no: Reçete numarası

        Returns:
            bool: Daha önce kontrol edildiyse True
        """
        return recete_no in self.kontrol_edilenler

    def kontrol_edildi_isaretle(self, recete_no: str):
        """
        Reçeteyi kontrol edildi olarak işaretle.

        Args:
            recete_no: Reçete numarası
        """
        self.kontrol_edilenler.add(recete_no)
        self._hafizayi_kaydet()

    def recete_kontrol_et(self, recete_verisi: Dict, zorla: bool = False) -> Dict[str, KontrolRaporu]:
        """
        Reçeteyi tüm kayıtlı kontrol sınıflarıyla kontrol et.

        Args:
            recete_verisi: Reçete bilgileri
            zorla: True ise daha önce kontrol edilmiş olsa bile kontrol et

        Returns:
            Dict[str, KontrolRaporu]: Her kontrol sınıfı için sonuç
                Anahtar: Kontrol sınıfı adı
                Değer: KontrolRaporu
        """
        recete_no = recete_verisi.get('recete_no', '')

        # Daha önce kontrol edilmiş mi?
        if not zorla and self.daha_once_kontrol_edildi_mi(recete_no):
            logger.info(f"Reçete {recete_no} daha önce kontrol edilmiş, atlanıyor...")
            return {
                '_genel': KontrolRaporu(
                    sonuc=KontrolSonucu.ATLANDI,
                    mesaj="Daha önce kontrol edilmiş"
                )
            }

        # Kontrol sınıfı yoksa
        if not self.kontrol_siniflari:
            logger.debug(f"Kayıtlı kontrol sınıfı yok, reçete {recete_no} atlanıyor...")
            return {
                '_genel': KontrolRaporu(
                    sonuc=KontrolSonucu.ATLANDI,
                    mesaj="Kayıtlı kontrol sınıfı yok"
                )
            }

        # Tüm kontrolleri çalıştır
        sonuclar = {}
        for kontrol in self.kontrol_siniflari:
            try:
                rapor = kontrol.kontrol_et(recete_verisi)
                sonuclar[kontrol.GRUP_ADI] = rapor
                kontrol.log_sonuc(recete_no, rapor)
            except Exception as e:
                logger.error(f"Kontrol hatası ({kontrol.GRUP_ADI}): {e}")
                sonuclar[kontrol.GRUP_ADI] = KontrolRaporu(
                    sonuc=KontrolSonucu.KONTROL_EDILEMEDI,
                    mesaj=f"Hata: {str(e)}"
                )

        # Kontrol edildi olarak işaretle
        self.kontrol_edildi_isaretle(recete_no)

        return sonuclar

    def hafizayi_temizle(self):
        """Kontrol hafızasını temizle (ay sonu için)"""
        self.kontrol_edilenler.clear()
        self._hafizayi_kaydet()
        logger.info("Kontrol hafızası temizlendi")

    def istatistik_al(self) -> Dict:
        """Kontrol istatistiklerini al"""
        return {
            'toplam_kontrol_edilen': len(self.kontrol_edilenler),
            'kayitli_kontrol_sayisi': len(self.kontrol_siniflari),
            'kontrol_siniflari': [k.GRUP_ADI for k in self.kontrol_siniflari]
        }


# Singleton instance
_motor_instance: Optional[KontrolMotoru] = None


def get_kontrol_motoru() -> KontrolMotoru:
    """Kontrol motoru singleton instance'ını al"""
    global _motor_instance
    if _motor_instance is None:
        _motor_instance = KontrolMotoru()
    return _motor_instance
