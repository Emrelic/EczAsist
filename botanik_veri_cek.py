"""
Botanik EOS Veri Çekme Modülü
Botanik EOS "Kasa Kapatma" penceresinden verileri otomatik çeker
COM UI Automation kullanarak WinForms child window'larına erişir
"""

import logging
import ctypes
from ctypes import wintypes
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

# Element isimleri (UI Automation Name)
ELEMENT_NAMES = {
    'baslangic': 'Islem Tutar4String satır 11',
    'pos': 'Islem Tutar4String satır 13',
    'nakit': 'Islem Tutar4String satır 14',
    'iban': 'Islem Tutar4String satır 15',
}

BOTANIK_EOS_TITLE_PATTERN = "BotanikEOS"


def _get_window_text(hwnd):
    """Win32 API ile pencere text'i al"""
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    if length > 0:
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value
    return ''


def _find_botanik_and_kasa_handles():
    """BotanikEOS ve Kasa Kapatma pencere handle'larını bul"""
    user32 = ctypes.windll.user32

    botanik_h = None
    kasa_h = None

    # BotanikEOS ana penceresini bul
    def get_botanik(hwnd, lparam):
        nonlocal botanik_h
        title = _get_window_text(hwnd)
        if BOTANIK_EOS_TITLE_PATTERN in title:
            botanik_h = hwnd
            return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(get_botanik), 0)

    if botanik_h is None:
        return None, None

    # BotanikEOS içinde Kasa Kapatma child penceresini bul
    def find_kasa(hwnd, lparam):
        nonlocal kasa_h
        title = _get_window_text(hwnd)
        if title == 'Kasa Kapatma':
            kasa_h = hwnd
            return False
        return True

    user32.EnumChildWindows(botanik_h, WNDENUMPROC(find_kasa), 0)

    return botanik_h, kasa_h


def botanik_verilerini_cek() -> Optional[Dict[str, float]]:
    """
    Botanik EOS Kasa Kapatma penceresinden verileri çeker
    COM UI Automation kullanır

    Returns:
        Dict with keys: baslangic, nakit, pos, iban
        None if window not found or error
    """
    try:
        import comtypes
        import comtypes.client

        # Pencere handle'larını bul
        botanik_h, kasa_h = _find_botanik_and_kasa_handles()

        if botanik_h is None:
            logger.warning("BotanikEOS penceresi bulunamadı")
            return None

        if kasa_h is None:
            logger.warning("Kasa Kapatma penceresi bulunamadı")
            return None

        logger.info(f"BotanikEOS handle: {botanik_h}, Kasa Kapatma handle: {kasa_h}")

        # UI Automation COM interface'i yükle
        comtypes.client.GetModule('UIAutomationCore.dll')
        from comtypes.gen.UIAutomationClient import (
            IUIAutomation, IUIAutomationValuePattern,
            TreeScope_Descendants
        )

        # UIA nesnesi oluştur
        uia = comtypes.client.CreateObject(
            '{ff48dba4-60ef-4201-aa87-54103eef594e}',
            interface=IUIAutomation
        )

        # Kasa Kapatma handle'ından element al
        kasa_elem = uia.ElementFromHandle(kasa_h)
        logger.info(f"Kasa Kapatma element alındı: {kasa_elem.CurrentName}")

        # Tüm child elementleri al
        condition = uia.CreateTrueCondition()
        children = kasa_elem.FindAll(TreeScope_Descendants, condition)
        logger.info(f"Toplam {children.Length} element bulundu")

        # Verileri çek
        veriler = {}

        for anahtar, element_name in ELEMENT_NAMES.items():
            veriler[anahtar] = 0.0

            for i in range(children.Length):
                elem = children.GetElement(i)
                name = elem.CurrentName

                if name and name == element_name:
                    # Value pattern ile değer al
                    try:
                        vp = elem.GetCurrentPattern(10002)  # UIA_ValuePatternId
                        if vp:
                            value_pattern = vp.QueryInterface(IUIAutomationValuePattern)
                            text = value_pattern.CurrentValue
                            if text:
                                deger = parse_turkish_number(str(text))
                                veriler[anahtar] = deger
                                logger.info(f"Botanik {anahtar}: '{text}' -> {deger}")
                    except Exception as e:
                        logger.debug(f"Value pattern hatası: {e}")
                    break

        return veriler

    except ImportError as e:
        logger.error(f"Gerekli modül yüklü değil: {e}")
        return None
    except Exception as e:
        logger.error(f"Botanik veri çekme hatası: {e}")
        import traceback
        traceback.print_exc()
        return None


def parse_turkish_number(text: str) -> float:
    """
    Türkçe sayı formatını float'a çevir
    Örnekler: "1.234,56" -> 1234.56, "1234,56" -> 1234.56, "1234" -> 1234.0
    """
    if not text:
        return 0.0

    try:
        # Boşlukları temizle
        text = text.strip()

        # TL, ₺ gibi sembolleri kaldır
        text = text.replace('TL', '').replace('₺', '').strip()

        # Binlik ayracı (nokta) kaldır
        text = text.replace('.', '')

        # Ondalık ayracı (virgül) noktaya çevir
        text = text.replace(',', '.')

        return float(text)
    except ValueError:
        logger.warning(f"Sayı dönüştürme hatası: '{text}'")
        return 0.0


def botanik_penceresi_acik_mi() -> bool:
    """
    BotanikEOS ve Kasa Kapatma penceresi açık mı kontrol et
    """
    try:
        botanik_h, kasa_h = _find_botanik_and_kasa_handles()
        return botanik_h is not None and kasa_h is not None
    except Exception as e:
        logger.error(f"Pencere kontrol hatası: {e}")
        return False


def baslangic_kasasi_kontrol(botanik_baslangic: float, program_baslangic: float) -> Tuple[bool, str]:
    """
    Başlangıç kasası tutarsızlık kontrolü

    Args:
        botanik_baslangic: Botanik'ten okunan başlangıç kasası
        program_baslangic: Programdaki başlangıç kasası

    Returns:
        (tutarli_mi, mesaj)
    """
    fark = abs(botanik_baslangic - program_baslangic)

    if fark < 0.01:  # Eşit (küçük yuvarlama hataları için tolerans)
        return True, "Başlangıç kasası tutarlı"
    else:
        mesaj = (
            f"UYARI: Başlangıç kasası tutarsız!\n"
            f"Botanik: {botanik_baslangic:,.2f} TL\n"
            f"Program: {program_baslangic:,.2f} TL\n"
            f"Fark: {fark:,.2f} TL"
        )
        return False, mesaj


def kasa_kapatma_screenshot() -> Optional[str]:
    """
    Botanik EOS Kasa Kapatma penceresinin screenshot'ını al
    PIL ImageGrab ile basit ekran görüntüsü

    Returns:
        Screenshot dosya yolu veya None
    """
    try:
        import tempfile
        from datetime import datetime
        from PIL import ImageGrab
        import win32gui
        import time

        # Kasa Kapatma penceresinin handle'ını bul
        botanik_h, kasa_h = _find_botanik_and_kasa_handles()

        if kasa_h is None:
            logger.warning("Kasa Kapatma penceresi bulunamadı, screenshot alınamadı")
            return None

        try:
            import win32con

            # Ana pencereyi (BotanikEOS) restore et
            win32gui.ShowWindow(botanik_h, win32con.SW_RESTORE)
            time.sleep(0.3)

            # Ana pencereyi öne getir
            try:
                win32gui.SetForegroundWindow(botanik_h)
            except:
                pass

            time.sleep(0.5)  # Bekle

            # Pencere koordinatlarını al
            rect = win32gui.GetWindowRect(kasa_h)
            left, top, right, bottom = rect

            logger.info(f"Pencere rect: left={left}, top={top}, right={right}, bottom={bottom}")

            # Negatif koordinat kontrolü (minimize edilmiş pencere)
            if left < -10000 or top < -10000:
                logger.error("Pencere minimize edilmiş ve restore edilemedi")
                return None

            # Tüm ekranın screenshot'ını al
            full_screen = ImageGrab.grab()
            logger.info(f"Ekran boyutu: {full_screen.size}")

            # Pencere alanını kes
            img = full_screen.crop((left, top, right, bottom))
            logger.info(f"Crop boyutu: {img.size}")

            # Geçici dosyaya kaydet
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = tempfile.gettempdir()
            dosya_yolu = f"{temp_dir}\\botanik_kasa_{timestamp}.png"

            img.save(dosya_yolu, "PNG")
            logger.info(f"Screenshot kaydedildi: {dosya_yolu}")

            return dosya_yolu

        except Exception as e:
            logger.error(f"Screenshot hatası: {e}")
            import traceback
            traceback.print_exc()
            return None

    except ImportError as e:
        logger.error(f"Gerekli modül yüklü değil: {e}")
        return None
    except Exception as e:
        logger.error(f"Screenshot hatası: {e}")
        return None


def screenshot_clipboard_kopyala(dosya_yolu: str) -> bool:
    """
    Screenshot'ı clipboard'a resim olarak kopyala

    Args:
        dosya_yolu: PNG dosya yolu

    Returns:
        Başarılı mı
    """
    try:
        from PIL import Image
        import win32clipboard
        import io

        # Resmi aç
        img = Image.open(dosya_yolu)

        # BMP formatına çevir (clipboard için)
        output = io.BytesIO()
        img.convert("RGB").save(output, "BMP")
        bmp_data = output.getvalue()[14:]  # BMP header'ı atla

        # Clipboard'a kopyala
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp_data)
        win32clipboard.CloseClipboard()

        logger.info("Screenshot clipboard'a kopyalandı")
        return True

    except ImportError as e:
        logger.error(f"Gerekli modül yüklü değil: {e}")
        return False
    except Exception as e:
        logger.error(f"Clipboard kopyalama hatası: {e}")
        return False


# Test için
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("Botanik Kasa Kapatma penceresi kontrol ediliyor...")

    if botanik_penceresi_acik_mi():
        print("Pencere açık, veriler çekiliyor...")
        veriler = botanik_verilerini_cek()

        if veriler:
            print("\nÇekilen Veriler:")
            print(f"  Başlangıç Kasası: {veriler.get('baslangic', 0):,.2f} TL")
            print(f"  Nakit: {veriler.get('nakit', 0):,.2f} TL")
            print(f"  POS: {veriler.get('pos', 0):,.2f} TL")
            print(f"  IBAN: {veriler.get('iban', 0):,.2f} TL")
        else:
            print("Veriler çekilemedi!")
    else:
        print("Botanik 'Kasa Kapatma' penceresi açık değil!")
