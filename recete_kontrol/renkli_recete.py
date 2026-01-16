# -*- coding: utf-8 -*-
"""
Renkli Reçete Kontrol Modülü

Yeşil/Kırmızı reçetelerin renkli reçete sistemine işlenip işlenmediğini kontrol eder.
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Kayıt dosyası
RENKLI_LISTE_DOSYA = Path(__file__).parent.parent / "renkli_recete_listesi.json"


@dataclass
class RenkliReceteKontrolRaporu:
    """Renkli reçete kontrol sonuç raporu"""
    toplam_kontrol: int = 0
    normal_recete: int = 0
    renkli_recete: int = 0
    islenenmis: int = 0  # PDF'de bulunan
    islenmemis: int = 0  # PDF'de bulunmayan
    islenmemis_liste: List[Dict] = field(default_factory=list)  # İşlenmemiş reçeteler

    def ozet_al(self) -> str:
        """Rapor özeti"""
        lines = [
            "=" * 50,
            "RENKLİ REÇETE KONTROL RAPORU",
            "=" * 50,
            f"Toplam Kontrol Edilen: {self.toplam_kontrol}",
            f"Normal Reçete: {self.normal_recete}",
            f"Renkli Reçete (Yeşil/Kırmızı): {self.renkli_recete}",
            f"  - İşlenmiş: {self.islenenmis}",
            f"  - İşlenmemiş: {self.islenmemis}",
            "=" * 50
        ]

        if self.islenmemis_liste:
            lines.append("\nİŞLENMEMİŞ REÇETELER:")
            lines.append("-" * 50)
            for item in self.islenmemis_liste:
                lines.append(f"  • {item['recete_no']} - {item['tur']} - Grup: {item.get('grup', '?')}")

        return "\n".join(lines)


class RenkliReceteKontrol:
    """
    Renkli reçete kontrol sınıfı.

    PDF'den yüklenen reçete listesi ile Medula'daki reçeteleri karşılaştırır.
    """

    def __init__(self):
        self.pdf_receteler: Set[str] = set()  # PDF'deki reçete numaraları (ikinci kısım)
        self.pdf_yuklu = False
        self.pdf_dosya_adi: Optional[str] = None
        self.yukleme_tarihi: Optional[datetime] = None

        # Kontrol raporu
        self.rapor = RenkliReceteKontrolRaporu()

        # Kaydedilmiş listeyi yükle
        self._dosyadan_yukle()

    def _dosyadan_yukle(self):
        """Kaydedilmiş listeyi dosyadan yükle"""
        try:
            if RENKLI_LISTE_DOSYA.exists():
                with open(RENKLI_LISTE_DOSYA, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.pdf_receteler = set(data.get('receteler', []))
                    self.pdf_yuklu = len(self.pdf_receteler) > 0
                    self.yukleme_tarihi = data.get('yukleme_tarihi')
                    logger.info(f"✓ Renkli reçete listesi dosyadan yüklendi: {len(self.pdf_receteler)} reçete")
        except Exception as e:
            logger.warning(f"Dosyadan yükleme hatası: {e}")

    def _dosyaya_kaydet(self):
        """Listeyi dosyaya kaydet"""
        try:
            data = {
                'receteler': list(self.pdf_receteler),
                'yukleme_tarihi': datetime.now().isoformat(),
                'sayi': len(self.pdf_receteler)
            }
            with open(RENKLI_LISTE_DOSYA, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✓ Renkli reçete listesi dosyaya kaydedildi: {len(self.pdf_receteler)} reçete")
        except Exception as e:
            logger.warning(f"Dosyaya kaydetme hatası: {e}")

    def liste_yukle(self, receteler: List[str]) -> Tuple[bool, str, int]:
        """
        Manuel olarak reçete listesi yükle (kopyala-yapıştır için)

        Args:
            receteler: Reçete numaraları listesi

        Returns:
            Tuple[bool, str, int]: (başarı, mesaj, yüklenen sayı)
        """
        self.pdf_receteler = set(receteler)
        self.pdf_yuklu = True
        self.yukleme_tarihi = datetime.now()
        self._dosyaya_kaydet()
        return (True, f"Yüklendi: {len(self.pdf_receteler)} reçete", len(self.pdf_receteler))

    def pdf_yukle(self, pdf_yolu: str) -> Tuple[bool, str, int]:
        """
        PDF'den renkli reçete listesini yükle.

        PDF formatı: "EBJMFHNF / 2KBNU50" - sadece ikinci kısım alınır (2KBNU50)

        Args:
            pdf_yolu: PDF dosya yolu

        Returns:
            Tuple[bool, str, int]: (başarı, mesaj, yüklenen sayı)
        """
        try:
            import pdfplumber
        except ImportError:
            return (False, "pdfplumber kütüphanesi yüklü değil. 'pip install pdfplumber' çalıştırın.", 0)

        try:
            self.pdf_receteler.clear()

            with pdfplumber.open(pdf_yolu) as pdf:
                for sayfa in pdf.pages:
                    # Tabloları çıkar
                    tablolar = sayfa.extract_tables()

                    for tablo in tablolar:
                        for satir in tablo:
                            if not satir:
                                continue

                            # Reçete No sütununu bul (genellikle 2. sütun, index 1)
                            for hucre in satir:
                                if hucre and "/" in str(hucre):
                                    # "EBJMFHNF / 2KBNU50" formatı
                                    parcalar = str(hucre).split("/")
                                    if len(parcalar) >= 2:
                                        ikinci_kisim = parcalar[1].strip()
                                        if ikinci_kisim and len(ikinci_kisim) >= 5:
                                            self.pdf_receteler.add(ikinci_kisim)

            self.pdf_yuklu = True
            self.pdf_dosya_adi = Path(pdf_yolu).name
            self.yukleme_tarihi = datetime.now()

            logger.info(f"✓ Renkli reçete PDF yüklendi: {len(self.pdf_receteler)} reçete")
            return (True, f"Yüklendi: {len(self.pdf_receteler)} reçete", len(self.pdf_receteler))

        except Exception as e:
            logger.error(f"PDF yükleme hatası: {e}")
            return (False, f"PDF yükleme hatası: {str(e)}", 0)

    def recete_pdf_de_var_mi(self, recete_no: str) -> bool:
        """
        Reçete numarasının PDF listesinde olup olmadığını kontrol et.

        Args:
            recete_no: Medula reçete numarası (örn: 2KBNU50)

        Returns:
            bool: PDF'de varsa True
        """
        if not recete_no:
            return False
        return recete_no.strip() in self.pdf_receteler

    def kontrol_et(self, recete_no: str, recete_turu: str, grup: str = "") -> Tuple[bool, str]:
        """
        Tek bir reçeteyi kontrol et.

        Args:
            recete_no: Medula reçete numarası
            recete_turu: Reçete türü (Normal, Yeşil, Kırmızı, vb.)
            grup: Grup bilgisi (A, B, C, GK)

        Returns:
            Tuple[bool, str]: (sorun_var_mi, mesaj)
                - sorun_var_mi: True ise işlenmemiş renkli reçete var
        """
        self.rapor.toplam_kontrol += 1

        # Normal reçete - kontrol gerekmez
        if recete_turu.lower() == "normal":
            self.rapor.normal_recete += 1
            logger.debug(f"✓ Normal reçete, atlanıyor: {recete_no}")
            return (False, "Normal reçete")

        # Yeşil veya Kırmızı reçete - kontrol gerekir
        if recete_turu.lower() in ["yeşil", "yesil", "kırmızı", "kirmizi"]:
            self.rapor.renkli_recete += 1

            # PDF yüklü değilse uyar
            if not self.pdf_yuklu:
                logger.warning(f"⚠ PDF yüklü değil, kontrol yapılamıyor: {recete_no}")
                return (False, "PDF yüklü değil")

            # PDF'de var mı kontrol et
            if self.recete_pdf_de_var_mi(recete_no):
                self.rapor.islenenmis += 1
                logger.info(f"✓ Renkli reçete sisteminde mevcut: {recete_no} ({recete_turu})")
                return (False, "İşlenmiş")
            else:
                self.rapor.islenmemis += 1
                self.rapor.islenmemis_liste.append({
                    'recete_no': recete_no,
                    'tur': recete_turu,
                    'grup': grup,
                    'tarih': datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                logger.warning(f"✗ Renkli reçete sistemine İŞLENMEMİŞ: {recete_no} ({recete_turu})")
                return (True, f"{recete_no} nolu reçete renkli reçete sistemine işlenmemiştir")

        # Diğer türler (Turuncu, Mor vb.) - şimdilik atla
        logger.debug(f"? Bilinmeyen reçete türü: {recete_turu}, atlanıyor: {recete_no}")
        return (False, f"Bilinmeyen tür: {recete_turu}")

    def rapor_al(self) -> RenkliReceteKontrolRaporu:
        """Kontrol raporunu al"""
        return self.rapor

    def rapor_sifirla(self):
        """Raporu sıfırla (yeni kontrol için)"""
        self.rapor = RenkliReceteKontrolRaporu()

    def rapor_ozeti_al(self) -> str:
        """Rapor özetini string olarak al"""
        return self.rapor.ozet_al()


# Singleton instance
_renkli_kontrol_instance: Optional[RenkliReceteKontrol] = None


def get_renkli_recete_kontrol() -> RenkliReceteKontrol:
    """Renkli reçete kontrol singleton instance'ını al"""
    global _renkli_kontrol_instance
    if _renkli_kontrol_instance is None:
        _renkli_kontrol_instance = RenkliReceteKontrol()
    return _renkli_kontrol_instance
