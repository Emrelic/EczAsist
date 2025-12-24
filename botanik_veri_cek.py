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
    AutomationId kullanarak txttl200, txttl100, vb. alanlardan değer okur

    Returns:
        Dict with keys: 200, 100, 50, 20, 10, 5, 1, 0.5 (küpür değerleri)
        None if window not found or error
    """
    try:
        import comtypes
        import comtypes.client

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

        return kupurler

    except ImportError as e:
        logger.error(f"Gerekli modül yüklü değil: {e}")
        return None
    except Exception as e:
        logger.error(f"Botanik küpür çekme hatası: {e}")
        import traceback
        traceback.print_exc()
        return None


def botanik_baslangic_kasasina_yaz(kupurler: Dict[float, int]) -> Tuple[bool, str]:
    """
    Botanik EOS 'Başlangıç Kasası' penceresine küpür değerlerini yazar ve kaydeder

    Args:
        kupurler: Dict with keys like 200, 100, 50, 20, 10, 5, 1, 0.5 (küpür değerleri)
                  ve values olarak adet sayıları

    Returns:
        Tuple[bool, str]: (başarılı mı, mesaj)
    """
    try:
        import comtypes
        from comtypes.client import CreateObject

        # COM başlat
        comtypes.CoInitialize()

        # UI Automation
        UIA_E_ELEMENTNOTAVAILABLE = -2147220991

        uia = CreateObject("{ff48dba4-60ef-4201-aa87-54103eef594e}")

        # Pattern IDs
        UIA_ValuePatternId = 10002
        UIA_InvokePatternId = 10000

        # TreeScope
        TreeScope_Descendants = 4

        # Başlangıç Kasası penceresini bul
        baslangic_h = _find_baslangic_kasasi_handle()

        if baslangic_h is None:
            return False, "Botanik 'Başlangıç Kasası' penceresi bulunamadı!\n\nLütfen Botanik'te Başlangıç Kasası sayfasını açın."

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
            try:
                ip = kaydet_btn.GetCurrentPattern(UIA_InvokePatternId)
                if ip:
                    from comtypes.gen.UIAutomationClient import IUIAutomationInvokePattern
                    invoke_pattern = ip.QueryInterface(IUIAutomationInvokePattern)
                    invoke_pattern.Invoke()
                    logger.info("Kaydet butonuna basıldı")
                else:
                    # Alternatif: tıklama
                    import time
                    time.sleep(0.2)
                    # SetFocus ve Enter tuşu
                    kaydet_btn.SetFocus()
                    import ctypes
                    ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)  # Enter key down
                    ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)  # Enter key up
            except Exception as e:
                logger.warning(f"Kaydet butonuna basılamadı: {e}")
                return True, f"{yazilan_sayac} değer yazıldı.\n\nKaydet butonuna manuel basmanız gerekiyor."
        else:
            return True, f"{yazilan_sayac} değer yazıldı.\n\nKaydet butonuna manuel basmanız gerekiyor."

        toplam = sum(k * v for k, v in kupurler.items())
        return True, f"Başlangıç kasası Botanik'e işlendi!\n\n{yazilan_sayac} küpür değeri yazıldı.\nToplam: {toplam:,.2f} TL"

    except ImportError as e:
        logger.error(f"Gerekli modül yüklü değil: {e}")
        return False, f"Gerekli modül yüklü değil: {e}"
    except Exception as e:
        logger.error(f"Botanik'e yazma hatası: {e}")
        import traceback
        traceback.print_exc()
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
