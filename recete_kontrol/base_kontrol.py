# -*- coding: utf-8 -*-
"""
Base Kontrol Sınıfı

Tüm ilaç grubu kontrol sınıfları bu sınıftan türetilir.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class KontrolSonucu(Enum):
    """Kontrol sonuç durumları"""
    UYGUN = "uygun"           # SUT'a uygun
    UYGUN_DEGIL = "uygun_degil"  # SUT'a uygun değil
    KONTROL_EDILEMEDI = "kontrol_edilemedi"  # Kontrol yapılamadı (eksik veri vb.)
    ATLANDI = "atlandi"       # Bu reçete için kontrol gerekmiyor


@dataclass
class KontrolRaporu:
    """Bir kontrol işleminin sonuç raporu"""
    sonuc: KontrolSonucu
    mesaj: str
    detaylar: Optional[Dict] = None
    uyari: Optional[str] = None


class BaseKontrol(ABC):
    """
    İlaç grubu kontrol sınıfları için temel sınıf.

    Her yeni ilaç grubu kontrolü bu sınıftan türetilmeli ve
    kontrol_et metodunu implement etmelidir.
    """

    # Alt sınıflar bu değerleri override etmeli
    GRUP_ADI: str = "Bilinmeyen"
    ACIKLAMA: str = ""
    ILAC_KODLARI: List[str] = []  # Bu gruba ait ilaç kodları

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.GRUP_ADI}")

    @abstractmethod
    def kontrol_et(self, recete_verisi: Dict) -> KontrolRaporu:
        """
        Reçeteyi kontrol et ve rapor döndür.

        Args:
            recete_verisi: Reçete bilgileri dict olarak
                - recete_no: str
                - hasta_adi: str
                - ilaclar: List[Dict] - her ilaç için {ad, kod, miktar, ...}
                - raporlar: List[Dict] - hasta raporları
                - grup: str (A/B/C/GK)

        Returns:
            KontrolRaporu: Kontrol sonucu
        """
        pass

    def bu_gruba_ait_mi(self, ilac_kodu: str) -> bool:
        """
        Verilen ilaç kodunun bu gruba ait olup olmadığını kontrol et.

        Args:
            ilac_kodu: İlaç barkod/kodu

        Returns:
            bool: Bu gruba aitse True
        """
        return ilac_kodu in self.ILAC_KODLARI

    def gruba_ait_ilaclari_bul(self, ilaclar: List[Dict]) -> List[Dict]:
        """
        İlaç listesinden bu gruba ait olanları filtrele.

        Args:
            ilaclar: Tüm ilaç listesi

        Returns:
            List[Dict]: Bu gruba ait ilaçlar
        """
        return [
            ilac for ilac in ilaclar
            if self.bu_gruba_ait_mi(ilac.get('kod', ''))
        ]

    def log_sonuc(self, recete_no: str, rapor: KontrolRaporu):
        """Kontrol sonucunu logla"""
        if rapor.sonuc == KontrolSonucu.UYGUN:
            self.logger.info(f"✓ [{self.GRUP_ADI}] Reçete {recete_no}: {rapor.mesaj}")
        elif rapor.sonuc == KontrolSonucu.UYGUN_DEGIL:
            self.logger.warning(f"✗ [{self.GRUP_ADI}] Reçete {recete_no}: {rapor.mesaj}")
        elif rapor.sonuc == KontrolSonucu.ATLANDI:
            self.logger.debug(f"- [{self.GRUP_ADI}] Reçete {recete_no}: {rapor.mesaj}")
        else:
            self.logger.error(f"? [{self.GRUP_ADI}] Reçete {recete_no}: {rapor.mesaj}")
