"""
Depo sorgulama için base class
"""
import time
from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from ..utils import logger, WAIT_TIMEOUT


class BaseDepo(ABC):
    """Depo sorgulama için base class"""

    def __init__(self, name, url, elements):
        self.name = name
        self.url = url
        self.elements = elements
        self.driver = None
        self.tab_handle = None  # Bu deponun tab handle'ı

    def init_driver(self, headless=False, shared_driver=None):
        """Selenium WebDriver'ı başlat veya paylaşılan driver'ı kullan

        Args:
            headless: Headless modda çalıştır mı
            shared_driver: Paylaşılan driver varsa kullan (yeni tab açar)
        """
        try:
            if shared_driver:
                # Paylaşılan driver'ı kullan, yeni tab aç
                logger.info(f"{self.name}: Mevcut tarayıcıda yeni tab açılıyor...")
                self.driver = shared_driver

                # Yeni tab aç
                self.driver.execute_script("window.open('');")

                # Yeni tab'a geç
                self.tab_handle = self.driver.window_handles[-1]
                self.driver.switch_to.window(self.tab_handle)

                logger.info(f"{self.name}: Yeni tab açıldı (Tab {len(self.driver.window_handles)})")
                return True
            else:
                # Yeni driver başlat
                logger.info(f"{self.name}: Tarayıcı başlatılıyor...")
                options = webdriver.ChromeOptions()

                if headless:
                    options.add_argument('--headless')

                # Geçici profil kullan (şifre kaydetme popup'ı çıkmaz)
                import os
                import tempfile
                temp_profile = tempfile.mkdtemp()
                options.add_argument(f'--user-data-dir={temp_profile}')

                # Popup'ları ve bildirim isteklerini engelle
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_argument('--disable-notifications')
                options.add_argument('--disable-infobars')
                options.add_argument('--disable-save-password-bubble')
                options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
                options.add_experimental_option('useAutomationExtension', False)

                # Şifre yöneticisini tamamen kapat
                prefs = {
                    "credentials_enable_service": False,
                    "profile.password_manager_enabled": False,
                    "profile.default_content_setting_values.notifications": 2,  # Bildirimleri engelle
                }
                options.add_experimental_option("prefs", prefs)

                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)

                # Ekranın sağ yarısına yerleştir (%50 genişlik)
                try:
                    import pyautogui
                    screen_width, screen_height = pyautogui.size()

                    # Pencere boyutu: %50 genişlik, %100 yükseklik
                    window_width = screen_width // 2
                    window_height = screen_height

                    # Konum: Ekranın sağ yarısı
                    x_position = screen_width // 2
                    y_position = 0

                    self.driver.set_window_size(window_width, window_height)
                    self.driver.set_window_position(x_position, y_position)

                    logger.info(f"{self.name}: Pencere konumu: Sağ yarı ({window_width}x{window_height})")
                except Exception as e:
                    logger.warning(f"{self.name}: Pencere konumlandırılamadı, varsayılan kullanılıyor: {e}")
                    self.driver.maximize_window()

                # İlk tab'ın handle'ını kaydet
                self.tab_handle = self.driver.current_window_handle

                logger.info(f"{self.name}: Tarayıcı başlatıldı (Geçici profil: {temp_profile})")
                return True

        except Exception as e:
            logger.error(f"{self.name}: Tarayıcı başlatılırken hata: {e}")
            return False

    def switch_to_tab(self):
        """Bu deponun tab'ına geç, yoksa yeniden oluştur"""
        try:
            # Önce mevcut tab'ın hala açık olup olmadığını kontrol et
            if self.tab_handle and self.tab_handle in self.driver.window_handles:
                if self.driver.current_window_handle != self.tab_handle:
                    self.driver.switch_to.window(self.tab_handle)
                return True
            else:
                # Tab kapanmış veya erişilemez, yeni tab aç
                logger.warning(f"{self.name}: Tab erişilemez durumda, yeni tab açılıyor...")
                self.driver.switch_to.new_window('tab')
                self.tab_handle = self.driver.window_handles[-1]
                self.driver.switch_to.window(self.tab_handle)

                # Ana sayfaya git
                if hasattr(self, 'url'):
                    self.driver.get(self.url)
                    logger.info(f"{self.name}: Yeni tab açıldı ve ana sayfaya yönlendirildi")

                # Login durumunu resetle (yeni tab açıldığında login gerekecek)
                if hasattr(self, 'logged_in'):
                    self.logged_in = False
                    logger.info(f"{self.name}: Login durumu resetlendi, yeniden login gerekecek")

                return True
        except Exception as e:
            logger.error(f"{self.name}: Tab'a geçiş hatası: {e}")
            return False

    def focus_browser(self):
        """Tarayıcı penceresini öne getir ve bu deponun sekmesine geç"""
        if not self.driver:
            return False

        try:
            # Önce bu deponun sekmesine geç
            self.switch_to_tab()

            # Mevcut title'ı al (depo adını içerir)
            current_title = None
            try:
                current_title = self.driver.title
                logger.info(f"{self.name}: Mevcut title: {current_title}")
            except Exception:
                pass

            # Pencereyi bul ve öne getir
            import win32gui
            import win32con

            target_hwnd = None
            best_match_score = 0

            def enum_windows_callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd):
                    win_title = win32gui.GetWindowText(hwnd)
                    if not win_title:
                        return True

                    # Chrome penceresi mi?
                    if "chrome" not in win_title.lower():
                        return True

                    # Bu depo penceresi mi kontrol et
                    match_score = 0

                    # Tam title eşleşmesi (en yüksek öncelik)
                    if current_title and current_title.lower() in win_title.lower():
                        match_score = 100
                    # Depo adı eşleşmesi
                    elif self.name and self.name.lower() in win_title.lower():
                        match_score = 50
                    # Depo URL'inden ipucu (alliance, selcuk, yusufpasa vb)
                    elif self.url:
                        domain_hints = ["alliance", "selcuk", "yusufpasa", "iskoop", "bursa", "farmazon", "sancak"]
                        for hint in domain_hints:
                            if hint in self.url.lower() and hint in win_title.lower():
                                match_score = 30
                                break

                    if match_score > 0:
                        results.append((hwnd, match_score, win_title))

                return True

            results = []
            win32gui.EnumWindows(enum_windows_callback, results)

            # En yüksek skorlu pencereyi seç
            if results:
                results.sort(key=lambda x: x[1], reverse=True)
                target_hwnd, score, win_title = results[0]
                logger.info(f"{self.name}: Pencere bulundu (skor: {score}): {win_title}")

                # Pencere zaten en üstte mi?
                foreground_hwnd = win32gui.GetForegroundWindow()
                if target_hwnd == foreground_hwnd:
                    logger.info(f"{self.name}: ✓ Pencere zaten en üstte")
                    return True

                # Pencere minimize ise restore et
                if win32gui.IsIconic(target_hwnd):
                    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                    time.sleep(0.3)
                    logger.info(f"{self.name}: ✓ Minimize pencere restore edildi")

                # Pencereyi öne getir - Birden fazla yöntem dene
                success = False

                # Yöntem 1: SetForegroundWindow
                try:
                    win32gui.SetForegroundWindow(target_hwnd)
                    success = True
                    logger.info(f"{self.name}: ✓ SetForegroundWindow ile öne getirildi")
                except Exception as e:
                    logger.debug(f"{self.name}: SetForegroundWindow başarısız: {e}")

                # Yöntem 2: ShowWindow + SetFocus
                if not success:
                    try:
                        win32gui.ShowWindow(target_hwnd, win32con.SW_SHOW)
                        win32gui.SetFocus(target_hwnd)
                        success = True
                        logger.info(f"{self.name}: ✓ ShowWindow+SetFocus ile öne getirildi")
                    except Exception as e:
                        logger.debug(f"{self.name}: ShowWindow+SetFocus başarısız: {e}")

                # Yöntem 3: BringWindowToTop
                if not success:
                    try:
                        win32gui.BringWindowToTop(target_hwnd)
                        win32gui.ShowWindow(target_hwnd, win32con.SW_SHOW)
                        success = True
                        logger.info(f"{self.name}: ✓ BringWindowToTop ile öne getirildi")
                    except Exception as e:
                        logger.debug(f"{self.name}: BringWindowToTop başarısız: {e}")

                # Yöntem 4: pyautogui ile pencere aktivasyonu
                if not success:
                    try:
                        import pyautogui
                        windows = pyautogui.getWindowsWithTitle(win_title)
                        if windows:
                            windows[0].activate()
                            success = True
                            logger.info(f"{self.name}: ✓ pyautogui ile öne getirildi")
                    except Exception as e:
                        logger.debug(f"{self.name}: pyautogui başarısız: {e}")

                return success

            logger.warning(f"{self.name}: ⚠ Pencere bulunamadı")
            return False

        except Exception as e:
            logger.error(f"{self.name}: Focus browser hatası: {e}")
            return False

    def minimize_browser(self):
        """Tarayıcı penceresini minimize et"""
        if not self.driver:
            return False

        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            # Selenium ile minimize et
            self.driver.minimize_window()
            logger.debug(f"{self.name}: Pencere minimize edildi")
            return True
        except Exception as e:
            logger.debug(f"{self.name}: Minimize edilemedi: {e}")

            # Alternatif: pywinauto ile minimize et
            try:
                from pywinauto import Desktop

                desktop = Desktop(backend="uia")
                title_candidates = []
                try:
                    current_title = self.driver.title
                    if current_title:
                        title_candidates.append(current_title)
                except Exception:
                    pass

                if self.name:
                    title_candidates.append(self.name)

                for window in desktop.windows():
                    try:
                        win_title = window.window_text()
                        if not win_title:
                            continue

                        lowered = win_title.lower()
                        if any(title.lower() in lowered for title in title_candidates if title):
                            window.minimize()
                            logger.info(f"{self.name}: Pencere minimize edildi (pywinauto)")
                            return True
                    except Exception:
                        continue
            except Exception as e2:
                logger.debug(f"{self.name}: pywinauto ile minimize başarısız: {e2}")

            return False

    def open_page(self):
        """Depo sayfasını aç"""
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Sayfa açılıyor: {self.url}")
            self.driver.get(self.url)
            return True
        except Exception as e:
            logger.error(f"{self.name}: Sayfa açılırken hata: {e}")
            return False

    def wait_for_element(self, by, value, timeout=WAIT_TIMEOUT):
        """Element görünene kadar bekle"""
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            logger.warning(f"{self.name}: Element bulunamadı: {value}")
            return None

    @abstractmethod
    def search_barcode(self, barcode):
        """Barkod ara (her depo için özelleştirilecek)"""
        pass

    @abstractmethod
    def check_stock_status(self):
        """Stok durumunu kontrol et (her depo için özelleştirilecek)"""
        pass

    def search_product(self, barcode):
        """Barkodu ara ve stok durumunu döndür (hızlı tarama için)

        search_barcode() + check_stock_status() kombinasyonu.
        Tek çağrıda hem arama hem stok kontrolü yapar.

        Args:
            barcode: Aranacak barkod

        Returns:
            dict: {
                "stok_var": bool,
                "fiyat": float,
                "sart": str,
                "mesaj": str,
                "satis_kosullari": list,
                "urun_adi": str
            }
            veya hata durumunda varsayılan dict
        """
        try:
            # Tab'a geç
            self.switch_to_tab()

            # Barkodu ara
            if not self.search_barcode(barcode):
                return {
                    "stok_var": False,
                    "fiyat": 0,
                    "sart": "",
                    "mesaj": "Bulunamadı",
                    "satis_kosullari": [],
                    "urun_adi": ""
                }

            # Stok durumunu kontrol et
            stok_durum = self.check_stock_status()

            # Ürün adını almaya çalış
            if hasattr(self, 'get_product_name'):
                try:
                    urun_adi = self.get_product_name()
                    if urun_adi:
                        stok_durum["urun_adi"] = urun_adi
                except Exception:
                    pass

            return stok_durum

        except Exception as e:
            logger.error(f"{self.name}: search_product hatası: {e}")
            return {
                "stok_var": False,
                "fiyat": 0,
                "sart": "",
                "mesaj": f"Hata: {str(e)[:30]}",
                "satis_kosullari": [],
                "urun_adi": ""
            }

    def close(self):
        """Tarayıcıyı veya tab'ı kapat"""
        if self.driver:
            try:
                # Eğer birden fazla tab varsa, sadece bu tab'ı kapat
                if len(self.driver.window_handles) > 1:
                    self.switch_to_tab()
                    self.driver.close()
                    logger.info(f"{self.name}: Tab kapatıldı")
                else:
                    # Son tab ise driver'ı kapat
                    self.driver.quit()
                    logger.info(f"{self.name}: Tarayıcı kapatıldı")
            except Exception as e:
                logger.error(f"{self.name}: Kapatma hatası: {e}")

    def prepare_order_quantity_area(self):
        """Adet alanını bulmadan önce yapılacak özel işlemler (iframe vb)"""
        self.switch_to_tab()

    def cleanup_order_quantity_area(self):
        """Adet alanı yazıldıktan sonra yapılacak temizlik"""
        self.switch_to_tab()

    def set_order_quantity(self, quantity):
        """Sipariş sayfasındaki adet alanına verilen miktarı yaz"""
        try:
            self.prepare_order_quantity_area()

            xpaths = [
                "//input[@type='number']",
                "//input[contains(@placeholder, 'Adet')]",
                "//input[contains(@name, 'adet') or contains(@id, 'adet')]",
                "//input[contains(@placeholder, 'Miktar')]",
                "//input[contains(@name, 'miktar') or contains(@id, 'miktar')]",
                "//input[contains(translate(@name, 'QTY', 'qty'), 'qty') or contains(translate(@id, 'QTY', 'qty'), 'qty')]",
                "//input[contains(@title, 'Adet')]",
                "//input[contains(@title, 'Miktar')]"
            ]

            candidates = []
            for xpath in xpaths:
                try:
                    elems = self.driver.find_elements(By.XPATH, xpath)
                    for elem in elems:
                        if elem.is_displayed() and elem.is_enabled():
                            candidates.append(elem)
                except Exception:
                    continue

            if not candidates:
                logger.warning(f"{self.name}: Sipariş adet alanı bulunamadı")
                return False

            target = candidates[0]

            # Elementi görünür hale getir (scroll)
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
                time.sleep(0.3)
                logger.debug(f"{self.name}: Element scroll ile görünür hale getirildi")
            except Exception as e:
                logger.debug(f"{self.name}: Scroll yapılamadı: {e}")

            # JavaScript ile değer yaz (click'ten daha güvenilir)
            try:
                self.driver.execute_script("""
                    arguments[0].value = '';
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, target, str(quantity))
                logger.info(f"{self.name}: Sipariş adet alanına {quantity} yazıldı (JavaScript)")
                self.cleanup_order_quantity_area()
                return True
            except Exception as js_error:
                logger.debug(f"{self.name}: JavaScript başarısız, klasik yöntem deneniyor: {js_error}")

                # Yedek: Klasik click + send_keys yöntemi
                target.click()
                time.sleep(0.1)
                target.send_keys(Keys.CONTROL, "a")
                target.send_keys(Keys.DELETE)
                target.send_keys(str(quantity))
                logger.info(f"{self.name}: Sipariş adet alanına {quantity} yazıldı (Send keys)")
                self.cleanup_order_quantity_area()
                return True
        except Exception as e:
            logger.error(f"{self.name}: Sipariş adedi yazılırken hata: {e}")
            try:
                self.cleanup_order_quantity_area()
            except Exception:
                pass
            return False
