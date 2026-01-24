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


def _click_element_by_coords(x: int, y: int) -> bool:
    """Verilen koordinatlara mouse click yapar"""
    try:
        import time
        user32 = ctypes.windll.user32
        user32.SetCursorPos(x, y)
        time.sleep(0.1)
        user32.mouse_event(0x0002, 0, 0, 0, 0)  # Left down
        time.sleep(0.05)
        user32.mouse_event(0x0004, 0, 0, 0, 0)  # Left up
        return True
    except Exception as e:
        logger.error(f"Mouse click hatası: {e}")
        return False


def _click_uia_element(elem) -> bool:
    """UI Automation element'ine tıklar"""
    try:
        import time
        rect = elem.CurrentBoundingRectangle
        center_x = rect.left + (rect.right - rect.left) // 2
        center_y = rect.top + (rect.bottom - rect.top) // 2
        logger.debug(f"Element tıklama: ({center_x}, {center_y})")
        return _click_element_by_coords(center_x, center_y)
    except Exception as e:
        logger.error(f"UIA element tıklama hatası: {e}")
        return False


def _find_botanik_eos_handle():
    """BotanikEOS ana pencere handle'ını bul"""
    user32 = ctypes.windll.user32
    botanik_h = None

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def find_botanik(hwnd, lparam):
        nonlocal botanik_h
        title = _get_window_text(hwnd)
        if title and 'BotanikEOS' in title and 'Kasa Kapatma' not in title:
            botanik_h = hwnd
            logger.debug(f"BotanikEOS penceresi bulundu: handle={hwnd}, title='{title}'")
            return False
        return True

    user32.EnumWindows(WNDENUMPROC(find_botanik), 0)
    return botanik_h


def botanik_baslangic_kasasi_ac() -> Tuple[bool, str]:
    """
    Botanik EOS'ta Kasa menüsünden Başlangıç Kasası penceresini açar

    Returns:
        Tuple[bool, str]: (başarılı mı, mesaj)
    """
    try:
        import comtypes
        import comtypes.client
        import time

        # COM başlat
        comtypes.CoInitialize()

        # UI Automation interface'ini yükle
        comtypes.client.GetModule('UIAutomationCore.dll')
        from comtypes.gen.UIAutomationClient import IUIAutomation, TreeScope_Descendants, TreeScope_Children

        uia = comtypes.client.CreateObject(
            '{ff48dba4-60ef-4201-aa87-54103eef594e}',
            interface=IUIAutomation
        )

        # Önce Başlangıç Kasası penceresi zaten açık mı kontrol et
        baslangic_h = _find_baslangic_kasasi_handle()
        if baslangic_h:
            logger.info("Başlangıç Kasası penceresi zaten açık")
            return True, "Başlangıç Kasası penceresi zaten açık"

        # BotanikEOS ana penceresini bul
        botanik_h = _find_botanik_eos_handle()
        if not botanik_h:
            return False, "BotanikEOS penceresi bulunamadı!\n\nLütfen Botanik programını açın."

        logger.info(f"BotanikEOS handle: {botanik_h}")

        # EczaneMenu child penceresini bul
        user32 = ctypes.windll.user32
        eczane_menu_h = None
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def find_eczane_menu(hwnd, lparam):
            nonlocal eczane_menu_h
            title = _get_window_text(hwnd)
            if title == 'EczaneMenu':
                eczane_menu_h = hwnd
                return False
            return True

        user32.EnumChildWindows(botanik_h, WNDENUMPROC(find_eczane_menu), 0)

        if not eczane_menu_h:
            return False, "EczaneMenu penceresi bulunamadı!"

        logger.info(f"EczaneMenu handle: {eczane_menu_h}")

        # EczaneMenu element'ini al
        eczane_elem = uia.ElementFromHandle(eczane_menu_h)

        # Kasa menüsünü bul (Name="Kasa", ControlType=MenuItem)
        condition = uia.CreateTrueCondition()
        children = eczane_elem.FindAll(TreeScope_Descendants, condition)

        kasa_menu = None
        for i in range(children.Length):
            elem = children.GetElement(i)
            try:
                name = elem.CurrentName
                control_type = elem.CurrentControlType
                # MenuItem = 50011
                if name == "Kasa" and control_type == 50011:
                    kasa_menu = elem
                    logger.info("Kasa menüsü bulundu")
                    break
            except:
                continue

        if not kasa_menu:
            return False, "Kasa menüsü bulunamadı!"

        # Kasa menüsüne InvokePattern ile tıkla
        from comtypes.gen.UIAutomationClient import IUIAutomationInvokePattern
        try:
            ip = kasa_menu.GetCurrentPattern(10000)  # UIA_InvokePatternId
            if ip:
                invoke = ip.QueryInterface(IUIAutomationInvokePattern)
                invoke.Invoke()
                logger.info("Kasa menüsüne Invoke yapıldı")
            else:
                return False, "Kasa menüsü InvokePattern desteklemiyor!"
        except Exception as e:
            logger.error(f"Kasa menüsü Invoke hatası: {e}")
            return False, f"Kasa menüsüne tıklanamadı: {e}"

        time.sleep(0.5)  # Menünün açılmasını bekle

        # Başlangıç Kasası menü öğesini bul
        # Menü açıldıktan sonra yeniden tara
        children = eczane_elem.FindAll(TreeScope_Descendants, condition)

        baslangic_item = None
        for i in range(children.Length):
            elem = children.GetElement(i)
            try:
                name = elem.CurrentName
                control_type = elem.CurrentControlType
                if name == "Başlangıç Kasası" and control_type == 50011:
                    baslangic_item = elem
                    logger.info("Başlangıç Kasası menü öğesi bulundu")
                    break
            except:
                continue

        if not baslangic_item:
            # Menüyü kapat (Escape)
            ctypes.windll.user32.keybd_event(0x1B, 0, 0, 0)
            ctypes.windll.user32.keybd_event(0x1B, 0, 2, 0)
            return False, "Başlangıç Kasası menü öğesi bulunamadı!"

        # Başlangıç Kasası'na InvokePattern ile tıkla
        try:
            ip = baslangic_item.GetCurrentPattern(10000)
            if ip:
                invoke = ip.QueryInterface(IUIAutomationInvokePattern)
                invoke.Invoke()
                logger.info("Başlangıç Kasası'na Invoke yapıldı")
            else:
                return False, "Başlangıç Kasası InvokePattern desteklemiyor!"
        except Exception as e:
            logger.error(f"Başlangıç Kasası Invoke hatası: {e}")
            return False, f"Başlangıç Kasası menü öğesine tıklanamadı: {e}"

        # Pencerenin açılmasını bekle - birkaç deneme yap
        for attempt in range(5):
            time.sleep(0.5)
            baslangic_h = _find_baslangic_kasasi_handle()
            if baslangic_h:
                logger.info("Başlangıç Kasası penceresi başarıyla açıldı")
                return True, "Başlangıç Kasası penceresi açıldı"
            logger.debug(f"Pencere henüz açılmadı, deneme {attempt + 1}/5")

        return False, "Başlangıç Kasası penceresi açılamadı!"

    except Exception as e:
        logger.error(f"Başlangıç Kasası açma hatası: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Hata: {e}"


def botanik_baslangic_kasasi_kapat(kaydet: bool = False) -> Tuple[bool, str]:
    """
    Botanik Başlangıç Kasası penceresini kapatır

    Args:
        kaydet: True ise önce Kaydet'e basar, sonra kapatır

    Returns:
        Tuple[bool, str]: (başarılı mı, mesaj)
    """
    try:
        import comtypes
        import comtypes.client
        import time

        # COM başlat
        comtypes.CoInitialize()

        # UI Automation interface'ini yükle
        comtypes.client.GetModule('UIAutomationCore.dll')
        from comtypes.gen.UIAutomationClient import IUIAutomation, TreeScope_Descendants

        uia = comtypes.client.CreateObject(
            '{ff48dba4-60ef-4201-aa87-54103eef594e}',
            interface=IUIAutomation
        )

        # Başlangıç Kasası penceresini bul
        baslangic_h = _find_baslangic_kasasi_handle()
        if not baslangic_h:
            return True, "Başlangıç Kasası penceresi zaten kapalı"

        # Pencereyi öne getir - koordinatların doğru olması için gerekli
        user32 = ctypes.windll.user32
        SW_RESTORE = 9
        SW_SHOW = 5
        user32.ShowWindow(baslangic_h, SW_RESTORE)
        user32.SetForegroundWindow(baslangic_h)
        time.sleep(0.3)  # Pencerenin öne gelmesini bekle

        baslangic_elem = uia.ElementFromHandle(baslangic_h)
        condition = uia.CreateTrueCondition()
        children = baslangic_elem.FindAll(TreeScope_Descendants, condition)

        # Element'leri topla
        kaydet_btn = None
        kapat_btn = None

        for i in range(children.Length):
            elem = children.GetElement(i)
            try:
                automation_id = elem.CurrentAutomationId
                name = elem.CurrentName
                control_type = elem.CurrentControlType
                # Button = 50000
                if control_type == 50000:
                    if automation_id == 'btnKaydet' or name == 'Kaydet':
                        kaydet_btn = elem
                    if name == 'Kapat':  # Title bar close button
                        kapat_btn = elem
            except:
                continue

        # Kaydet gerekiyorsa
        if kaydet and kaydet_btn:
            logger.info("Kaydet butonuna basılıyor...")
            _click_uia_element(kaydet_btn)
            time.sleep(0.5)

        # Pencereyi WM_CLOSE ile kapat (daha güvenilir)
        WM_CLOSE = 0x0010
        logger.info("Pencere WM_CLOSE ile kapatılıyor...")
        user32.PostMessageW(baslangic_h, WM_CLOSE, 0, 0)
        time.sleep(0.3)

        # Pencere kapandı mı kontrol et
        baslangic_h = _find_baslangic_kasasi_handle()
        if not baslangic_h:
            return True, "Başlangıç Kasası penceresi kapatıldı"
        else:
            return False, "Pencere kapatılamadı"

    except Exception as e:
        logger.error(f"Başlangıç Kasası kapatma hatası: {e}")
        return False, f"Hata: {e}"


def _find_baslangic_kasasi_handle():
    """Başlangıç Kasası pencere handle'ını bul"""
    user32 = ctypes.windll.user32
    baslangic_h = None

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def find_baslangic(hwnd, lparam):
        nonlocal baslangic_h
        title = _get_window_text(hwnd)
        # "Başlangıç Kasası" penceresini ara
        if title and 'Başlangıç Kasası' in title:
            baslangic_h = hwnd
            logger.debug(f"Başlangıç Kasası penceresi bulundu: handle={hwnd}, title='{title}'")
            return False  # Aramayı durdur
        return True

    user32.EnumWindows(WNDENUMPROC(find_baslangic), 0)

    if baslangic_h is None:
        # BotanikEOS altında child olarak ara
        botanik_windows = []

        def collect_botanik(hwnd, lparam):
            title = _get_window_text(hwnd)
            if title and 'BotanikEOS' in title:
                botanik_windows.append((hwnd, title))
            return True

        user32.EnumWindows(WNDENUMPROC(collect_botanik), 0)

        for bot_hwnd, bot_title in botanik_windows:
            def find_child(hwnd, lparam):
                nonlocal baslangic_h
                title = _get_window_text(hwnd)
                if title and 'Başlangıç Kasası' in title:
                    baslangic_h = hwnd
                    return False
                return True

            user32.EnumChildWindows(bot_hwnd, WNDENUMPROC(find_child), 0)
            if baslangic_h:
                break

    return baslangic_h


def botanik_baslangic_kupurlerini_cek() -> Optional[Dict[str, int]]:
    """
    Botanik EOS 'Başlangıç Kasası' penceresinden küpür adetlerini çeker
    Pencereyi otomatik açar, değerleri okur ve kapatır.
    AutomationId kullanarak txttl200, txttl100, vb. alanlardan değer okur

    Returns:
        Dict with keys: 200, 100, 50, 20, 10, 5, 1, 0.5 (küpür değerleri)
        None if window not found or error
    """
    try:
        import comtypes
        import comtypes.client
        import time

        # 1. Önce pencereyi otomatik aç
        acildi, ac_mesaj = botanik_baslangic_kasasi_ac()
        if not acildi:
            logger.error(f"Başlangıç Kasası açılamadı: {ac_mesaj}")
            return None

        time.sleep(0.3)  # Pencere stabilize olsun

        # Başlangıç Kasası penceresini bul
        baslangic_h = _find_baslangic_kasasi_handle()

        if baslangic_h is None:
            logger.warning("Başlangıç Kasası penceresi bulunamadı")
            return None

        logger.info(f"Başlangıç Kasası handle: {baslangic_h}")

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

        # Başlangıç Kasası handle'ından element al
        baslangic_elem = uia.ElementFromHandle(baslangic_h)
        logger.info(f"Başlangıç Kasası element alındı: {baslangic_elem.CurrentName}")

        # Tüm child elementleri al
        condition = uia.CreateTrueCondition()
        children = baslangic_elem.FindAll(TreeScope_Descendants, condition)
        logger.info(f"Toplam {children.Length} element bulundu")

        # AutomationId -> Küpür değeri eşlemesi
        automation_id_map = {
            'txttl200': 200,
            'txttl100': 100,
            'txttl50': 50,
            'txttl20': 20,
            'txttl10': 10,
            'txttl5': 5,
            'txttl1': 1,
            'txtkr50': 0.5,  # 50 kuruş = 0.5 TL
        }

        kupurler = {200: 0, 100: 0, 50: 0, 20: 0, 10: 0, 5: 0, 1: 0, 0.5: 0}

        # Elementleri tara ve AutomationId ile eşleştir
        for i in range(children.Length):
            elem = children.GetElement(i)
            try:
                automation_id = elem.CurrentAutomationId
                if automation_id and automation_id in automation_id_map:
                    kupur_degeri = automation_id_map[automation_id]

                    # Child element'ten değeri al (parent Edit, child gerçek değer)
                    child_condition = uia.CreateTrueCondition()
                    child_elems = elem.FindAll(TreeScope_Descendants, child_condition)

                    value = None

                    # Önce child'lardan değer al
                    for j in range(child_elems.Length):
                        child = child_elems.GetElement(j)
                        try:
                            child_name = child.CurrentName
                            if child_name and child_name.strip():
                                value = child_name.strip()
                                break
                        except:
                            continue

                    # Child'dan alamadıysak parent'tan dene
                    if value is None:
                        try:
                            vp = elem.GetCurrentPattern(10002)  # UIA_ValuePatternId
                            if vp:
                                value_pattern = vp.QueryInterface(IUIAutomationValuePattern)
                                value = value_pattern.CurrentValue
                        except:
                            pass

                    # Değeri sayıya çevir
                    if value:
                        try:
                            val = int(float(str(value).replace(',', '.').strip()))
                            kupurler[kupur_degeri] = val
                            logger.info(f"Küpür {kupur_degeri} TL ({automation_id}): {val} adet")
                        except ValueError:
                            logger.debug(f"Değer dönüştürülemedi: {value}")

            except Exception as e:
                logger.debug(f"Element okuma hatası: {e}")
                continue

        # Sonuçları logla
        toplam = sum(k * v for k, v in kupurler.items())
        logger.info(f"Toplam küpür değeri: {toplam} TL")

        # 2. Pencereyi kapat (kaydet olmadan)
        botanik_baslangic_kasasi_kapat(kaydet=False)

        return kupurler

    except ImportError as e:
        logger.error(f"Gerekli modül yüklü değil: {e}")
        # Hata durumunda pencereyi kapat
        botanik_baslangic_kasasi_kapat(kaydet=False)
        return None
    except Exception as e:
        logger.error(f"Botanik küpür çekme hatası: {e}")
        import traceback
        traceback.print_exc()
        # Hata durumunda pencereyi kapat
        botanik_baslangic_kasasi_kapat(kaydet=False)
        return None


def botanik_baslangic_kasasina_yaz(kupurler: Dict[float, int]) -> Tuple[bool, str]:
    """
    Botanik EOS 'Başlangıç Kasası' penceresine küpür değerlerini yazar ve kaydeder
    Pencereyi otomatik açar, değerleri yazar, kaydeder ve kapatır.

    Args:
        kupurler: Dict with keys like 200, 100, 50, 20, 10, 5, 1, 0.5 (küpür değerleri)
                  ve values olarak adet sayıları

    Returns:
        Tuple[bool, str]: (başarılı mı, mesaj)
    """
    try:
        import comtypes
        import comtypes.client
        import time

        # 1. Önce pencereyi otomatik aç
        acildi, ac_mesaj = botanik_baslangic_kasasi_ac()
        if not acildi:
            return False, ac_mesaj

        time.sleep(0.3)  # Pencere stabilize olsun

        # COM başlat
        comtypes.CoInitialize()

        # UI Automation interface'ini yükle
        comtypes.client.GetModule('UIAutomationCore.dll')
        from comtypes.gen.UIAutomationClient import IUIAutomation

        uia = comtypes.client.CreateObject(
            '{ff48dba4-60ef-4201-aa87-54103eef594e}',
            interface=IUIAutomation
        )

        # Pattern IDs
        UIA_ValuePatternId = 10002
        UIA_InvokePatternId = 10000

        # TreeScope
        TreeScope_Descendants = 4

        # Başlangıç Kasası penceresini bul
        baslangic_h = _find_baslangic_kasasi_handle()

        if baslangic_h is None:
            return False, "Botanik 'Başlangıç Kasası' penceresi açılamadı!"

        logger.info(f"Başlangıç Kasası handle: {baslangic_h}")

        # Element al
        baslangic_elem = uia.ElementFromHandle(baslangic_h)
        logger.info(f"Başlangıç Kasası element alındı: {baslangic_elem.CurrentName}")

        # Tüm child elementleri al
        condition = uia.CreateTrueCondition()
        children = baslangic_elem.FindAll(TreeScope_Descendants, condition)

        # Küpür değeri -> AutomationId eşlemesi (tersine)
        kupur_to_automation = {
            200: 'txttl200',
            100: 'txttl100',
            50: 'txttl50',
            20: 'txttl20',
            10: 'txttl10',
            5: 'txttl5',
            1: 'txttl1',
            0.5: 'txtkr50',
        }

        # Elementleri dict'e topla
        element_map = {}
        kaydet_btn = None

        for i in range(children.Length):
            elem = children.GetElement(i)
            try:
                automation_id = elem.CurrentAutomationId
                if automation_id:
                    element_map[automation_id] = elem
                    if automation_id == 'btnKaydet':
                        kaydet_btn = elem
            except:
                continue

        # Değerleri yaz
        yazilan_sayac = 0
        for kupur_degeri, adet in kupurler.items():
            automation_id = kupur_to_automation.get(kupur_degeri)
            if automation_id and automation_id in element_map:
                elem = element_map[automation_id]
                try:
                    # ValuePattern ile değer yaz
                    vp = elem.GetCurrentPattern(UIA_ValuePatternId)
                    if vp:
                        from comtypes.gen.UIAutomationClient import IUIAutomationValuePattern
                        value_pattern = vp.QueryInterface(IUIAutomationValuePattern)
                        value_pattern.SetValue(str(int(adet)))
                        logger.info(f"Yazıldı: {kupur_degeri} TL ({automation_id}) = {adet} adet")
                        yazilan_sayac += 1
                except Exception as e:
                    logger.warning(f"Değer yazılamadı {automation_id}: {e}")

        if yazilan_sayac == 0:
            return False, "Hiçbir değer yazılamadı!"

        # Kaydet butonuna bas
        if kaydet_btn is None:
            # Manuel olarak bul
            for automation_id, elem in element_map.items():
                if 'kaydet' in automation_id.lower() or 'save' in automation_id.lower():
                    kaydet_btn = elem
                    break

        if kaydet_btn:
            kaydet_basarili = False

            # Yöntem 1: InvokePattern
            try:
                ip = kaydet_btn.GetCurrentPattern(UIA_InvokePatternId)
                if ip:
                    from comtypes.gen.UIAutomationClient import IUIAutomationInvokePattern
                    invoke_pattern = ip.QueryInterface(IUIAutomationInvokePattern)
                    invoke_pattern.Invoke()
                    logger.info("Kaydet butonuna basıldı (InvokePattern)")
                    kaydet_basarili = True
            except Exception as e:
                logger.warning(f"InvokePattern başarısız: {e}")

            # Yöntem 2: Doğrudan mouse click
            if not kaydet_basarili:
                try:
                    import time
                    time.sleep(0.3)

                    # Butonun koordinatlarını al
                    rect = kaydet_btn.CurrentBoundingRectangle
                    center_x = rect.left + (rect.right - rect.left) // 2
                    center_y = rect.top + (rect.bottom - rect.top) // 2

                    logger.info(f"Mouse click koordinatları: ({center_x}, {center_y})")

                    # Mouse'u hareket ettir ve tıkla
                    import ctypes
                    ctypes.windll.user32.SetCursorPos(center_x, center_y)
                    time.sleep(0.1)
                    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # Left down
                    time.sleep(0.05)
                    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # Left up

                    logger.info("Kaydet butonuna basıldı (mouse click)")
                    kaydet_basarili = True
                except Exception as e:
                    logger.warning(f"Mouse click başarısız: {e}")

            if not kaydet_basarili:
                # Pencereyi kapat
                botanik_baslangic_kasasi_kapat(kaydet=False)
                return True, f"{yazilan_sayac} değer yazıldı.\n\nKaydet butonuna manuel basmanız gerekiyor."
        else:
            # Pencereyi kapat
            botanik_baslangic_kasasi_kapat(kaydet=False)
            return True, f"{yazilan_sayac} değer yazıldı.\n\nKaydet butonuna manuel basmanız gerekiyor."

        # 3. Pencereyi kapat (başarılı olunca)
        time.sleep(0.3)
        botanik_baslangic_kasasi_kapat(kaydet=False)

        toplam = sum(k * v for k, v in kupurler.items())
        return True, f"Başlangıç kasası Botanik'e işlendi!\n\n{yazilan_sayac} küpür değeri yazıldı.\nToplam: {toplam:,.2f} TL"

    except ImportError as e:
        logger.error(f"Gerekli modül yüklü değil: {e}")
        # Hata durumunda pencereyi kapat
        botanik_baslangic_kasasi_kapat(kaydet=False)
        return False, f"Gerekli modül yüklü değil: {e}"
    except Exception as e:
        logger.error(f"Botanik'e yazma hatası: {e}")
        import traceback
        traceback.print_exc()
        # Hata durumunda pencereyi kapat
        botanik_baslangic_kasasi_kapat(kaydet=False)
        return False, f"Hata: {e}"


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
