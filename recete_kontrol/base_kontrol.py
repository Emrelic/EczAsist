# -*- coding: utf-8 -*-
"""
Base Kontrol Sınıfı

Tüm ilaç grubu kontrol sınıfları bu sınıftan türetilir.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class KontrolSonucu(Enum):
    """Kontrol sonuç durumları"""
    UYGUN = "uygun"           # SUT'a uygun
    UYGUN_DEGIL = "uygun_degil"  # SUT'a uygun değil
    KONTROL_EDILEMEDI = "kontrol_edilemedi"  # Kontrol yapılamadı (eksik veri vb.) — UI'da ŞÜPHELİ
    SARTLI_UYGUN = "sartli_uygun"  # YENİ: tüm hesaplanabilir şartlar UYGUN, sadece
                                    # 'şartlı atom'lar KE (örn. 6 ay ara, rapor süresi).
                                    # "X şartıyla uygun" — pipeline verisi gelirse netleşir.
    MANUEL_KONTROL = "manuel_kontrol"  # Sistem otomatik karar veremiyor, insan göz atmalı (örn. aile hekimi + 24 ay belirsiz)
    ATLANDI = "atlandi"       # Bu reçete için kontrol gerekmiyor


class SartDurumu(Enum):
    """Tek bir SUT şartının kontrol sonucu (CLAUDE.md disiplini).

    VAR: şart kaynaklarda bulundu ve uygun.
    YOK: şart arandı, sağlanmadığı NET.
    KONTROL_EDILEMEDI: metin parse'ı / kaynak veri ile sorgulanamadı; manuel doğrulama gerekli.
    NA: bu sınıf/akış için şart geçerli değil (raporlamada gizlenir).
    """
    VAR = "var"
    YOK = "yok"
    KONTROL_EDILEMEDI = "kontrol_edilemedi"
    NA = "na"


@dataclass
class SartSonuc:
    """Tek bir SUT şartının değerlendirme kaydı.

    ad: insan-okur şart adı (ör: "Endokrin/iç hast. uzmanı veya raporu").
    durum: SartDurumu.
    neden: kısa açıklama (ör: "Doktor branşı: aile hekimliği — yetkili değil").
    kaynak: bilgiyi nereden çıkardık (ör: "doktor_branş", "rapor_metni", "ICD").
    grup: aynı SUT alt-maddesine ait şartları ortak başlık altında topla
        (ör: "Risk faktörü (≥1)", "Kontrendikasyon", "Varfarin yolu (a)").
        GUI atomik şart paneli `grup` alanına göre başlıklı render eder.
        Boşsa varsayılan/grupsuz şart.
    veya_grubu: aynı `grup` içindeki şartlar VEYA mantığında mı (≥1 sağlanırsa
        grup VAR sayılır)? False ise AND mantığı (hepsi sağlanmalı). Grup
        başlığında "(≥1 olmalı)" / "(hepsi)" işareti için kullanılır.
    """
    ad: str
    durum: SartDurumu
    neden: str = ""
    kaynak: str = ""
    grup: str = ""
    veya_grubu: bool = False
    # Atom kutusunun İÇİNDE mini liste olarak gösterilecek alt detaylar
    # (render `_klasik_blok_ciz` tarafından ✓/✗ satırları olarak çizilir;
    # matematik etkilenmez — yalnızca görsel zenginleştirme).
    # Format: [(ad, "var"|"yok"|"kontrol_edilemedi"), ...]
    alt_liste: Optional[List[Tuple[str, str]]] = None
    # YENİ: 'şartlı atom' işareti. True ise: bu atomun durumu KE iken diğer
    # tüm hesaplanabilir şartlar VAR olunca genel sonuç ŞARTLI_UYGUN olur
    # ("[atom adı] sağlandığı varsayımıyla uygun"). Yetersiz pipeline verisi
    # (örn. hasta satış geçmişi, rapor süresi metnine girmemiş) için
    # kullanılır — eczacı manuel doğruladığında kesin UYGUN olur.
    sartli_atom: bool = False


@dataclass
class KontrolRaporu:
    """Bir kontrol işleminin sonuç raporu"""
    sonuc: KontrolSonucu
    mesaj: str
    detaylar: Optional[Dict] = None
    uyari: Optional[str] = None
    sut_kurali: Optional[str] = None      # Hangi SUT kuralına bakıldı (ör: "SUT 4.2.2 Psikiyatri")
    aranan_ibare: Optional[str] = None    # Metinde aranan ibare (ör: "uzman raporu (psikiyatri/nöroloji)")
    bulunan_metin: Optional[str] = None   # Metinde bulunan eşleşme (ör: "psikiyatri uzmanı tarafından...")
    sartlar: List[SartSonuc] = field(default_factory=list)  # Şart-bazlı yapısal rapor (CLAUDE.md disiplini)


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
