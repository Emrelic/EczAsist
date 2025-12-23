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
    botanik_windows = []  # Tüm BotanikEOS pencereleri

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    # Önce TÜM BotanikEOS pencerelerini topla
    def collect_botanik(hwnd, lparam):
        title = _get_window_text(hwnd)
        if title and 'BotanikEOS' in title:
            botanik_windows.append((hwnd, title))
        return True

    user32.EnumWindows(WNDENUMPROC(collect_botanik), 0)

    if not botanik_windows:
        logger.debug("BotanikEOS penceresi bulunamadı")
        return None, None

    logger.debug(f"Bulunan BotanikEOS pencereleri: {len(botanik_windows)}")

    # Her BotanikEOS penceresinde "Kasa Kapatma" child'ını ara
    for bot_hwnd, bot_title in botanik_windows:
        found_kasa = None

        def find_kasa_child(hwnd, lparam):
            nonlocal found_kasa
            title = _get_window_text(hwnd)
            # Sadece "Kasa Kapatma" (bizim programımız "Kasa Kapatma - Günlük Mutabakat")
            if title == 'Kasa Kapatma':
                found_kasa = hwnd
                return False
            return True

        user32.EnumChildWindows(bot_hwnd, WNDENUMPROC(find_kasa_child), 0)

        if found_kasa:
            botanik_h = bot_hwnd
            kasa_h = found_kasa
            logger.debug(f"Kasa Kapatma bulundu: BotanikEOS='{bot_title}', Kasa handle={found_kasa}")
            break

    if kasa_h is None:
        logger.debug("Hiçbir BotanikEOS penceresinde 'Kasa Kapatma' child'ı bulunamadı")

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


def botanik_baslangic_kupurlerini_cek() -> Optional[Dict[str, int]]:
    """
    Botanik EOS Kasa Kapatma penceresinden başlangıç kasası küpür adetlerini çeker

    Returns:
        Dict with keys: 200, 100, 50, 20, 10, 5, 1, 0.5 (küpür değerleri)
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

        logger.info(f"Küpür çekme - BotanikEOS: {botanik_h}, Kasa Kapatma: {kasa_h}")

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

        # Edit kontrolleri topla (position ile)
        edit_controls = []

        for i in range(children.Length):
            elem = children.GetElement(i)
            try:
                ctrl_type = elem.CurrentControlType
                # ControlType.Edit = 50004
                if ctrl_type == 50004:
                    rect = elem.CurrentBoundingRectangle
                    x, y = rect.left, rect.top

                    # Value al
                    try:
                        vp = elem.GetCurrentPattern(10002)  # UIA_ValuePatternId
                        if vp:
                            value_pattern = vp.QueryInterface(IUIAutomationValuePattern)
                            text = value_pattern.CurrentValue
                            if text is not None:
                                edit_controls.append({
                                    'x': x,
                                    'y': y,
                                    'value': str(text).strip()
                                })
                                logger.debug(f"Edit control: x={x}, y={y}, value='{text}'")
                    except:
                        # Name'den dene
                        name = elem.CurrentName
                        if name:
                            edit_controls.append({
                                'x': x,
                                'y': y,
                                'value': str(name).strip()
                            })
            except:
                continue

        logger.info(f"Toplam {len(edit_controls)} Edit control bulundu")

        if len(edit_controls) < 8:
            logger.warning(f"Yeterli Edit control bulunamadı: {len(edit_controls)}")
            return None

        # X koordinatına göre iki sütuna ayır
        # Sol sütun: 200, 100, 50, 20, 10, 5 (6 adet)
        # Sağ sütun: 1, 0.5 (2 adet)

        # X değerlerini analiz et
        x_values = sorted(set(ec['x'] for ec in edit_controls))

        if len(x_values) < 2:
            logger.warning("İki sütun bulunamadı")
            return None

        # İlk iki benzersiz X değeri (sol ve sağ sütun)
        left_x = x_values[0]
        right_x = x_values[1] if len(x_values) > 1 else x_values[0]

        # Tolerans ile sütunlara ayır
        tolerance = 50
        left_column = [ec for ec in edit_controls if abs(ec['x'] - left_x) < tolerance]
        right_column = [ec for ec in edit_controls if abs(ec['x'] - right_x) < tolerance and ec not in left_column]

        # Y'ye göre sırala
        left_column.sort(key=lambda e: e['y'])
        right_column.sort(key=lambda e: e['y'])

        logger.info(f"Sol sütun: {len(left_column)}, Sağ sütun: {len(right_column)}")

        # Küpür değerleri eşle
        # Sol sütun: 200, 100, 50, 20, 10, 5
        # Sağ sütun: 1, 0.5
        left_denominations = [200, 100, 50, 20, 10, 5]
        right_denominations = [1, 0.5]

        kupurler = {}

        for i, denom in enumerate(left_denominations):
            if i < len(left_column):
                try:
                    val = int(float(left_column[i]['value'].replace(',', '.')))
                    kupurler[denom] = val
                    logger.info(f"Küpür {denom} TL: {val} adet")
                except:
                    kupurler[denom] = 0
            else:
                kupurler[denom] = 0

        for i, denom in enumerate(right_denominations):
            if i < len(right_column):
                try:
                    val = int(float(right_column[i]['value'].replace(',', '.')))
                    kupurler[denom] = val
                    logger.info(f"Küpür {denom} TL: {val} adet")
                except:
                    kupurler[denom] = 0
            else:
                kupurler[denom] = 0

        return kupurler

    except ImportError as e:
        logger.error(f"Gerekli modül yüklü değil: {e}")
        return None
    except Exception as e:
        logger.error(f"Botanik küpür çekme hatası: {e}")
        import traceback
        traceback.print_exc()
        return None


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
