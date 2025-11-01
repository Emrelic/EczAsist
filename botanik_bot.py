"""
Botanik Medulla Reçete Takip Botu
Bu bot, Medulla programında otomatik reçete işlemleri yapar.
"""

import time
from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError
import logging
import ctypes
import win32gui
import win32con
import subprocess
from timing_settings import get_timing_settings

# Logging ayarları - Kısa format
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class BotanikBot:
    """Medulla programı için otomasyon botu"""

    def __init__(self):
        self.app = None
        self.main_window = None
        # Element cache sistemi - performans için
        self._element_cache = {}
        self._cache_enabled = True
        # Zamanlama ayarları
        self.timing = get_timing_settings()

    def timed_sleep(self, key, default=0.1):
        """
        Ayarlı bekleme süresi + istatistik kaydı

        Args:
            key (str): Timing ayar anahtarı
            default (float): Varsayılan süre (bulunamazsa)
        """
        start_time = time.time()
        sleep_duration = self.timing.get(key, default)
        time.sleep(sleep_duration)
        actual_duration = time.time() - start_time

        # İstatistik kaydet
        self.timing.kayit_ekle(key, actual_duration)

    def baglanti_kur(self, pencere_basligi="MEDULA", ilk_baglanti=False):
        """
        Medulla programına bağlan

        Args:
            pencere_basligi (str): Medulla penceresinin başlığı
            ilk_baglanti (bool): İlk bağlantı mı? (pencere yerleştirme için)

        Returns:
            bool: Bağlantı başarılı ise True
        """
        try:
            if ilk_baglanti:
                logger.info(f"'{pencere_basligi}' aranıyor...")

            # Mevcut pencereye bağlan (birden fazla varsa ilkini al)
            from pywinauto import Desktop
            windows = Desktop(backend="uia").windows()

            medula_window = None
            for window in windows:
                try:
                    if pencere_basligi in window.window_text():
                        medula_window = window
                        break
                except:
                    pass

            if medula_window is None:
                raise ElementNotFoundError(f"'{pencere_basligi}' bulunamadı")

            self.main_window = medula_window

            if ilk_baglanti:
                logger.info("✓ MEDULA'ya bağlandı")

            # Pencereyi sol %80'e yerleştir (sadece ilk bağlantıda)
            if ilk_baglanti:
                try:
                    # Ekran çözünürlüğünü al
                    user32 = ctypes.windll.user32
                    screen_width = user32.GetSystemMetrics(0)
                    screen_height = user32.GetSystemMetrics(1)

                    # Sol %80 boyutlandırma - sola tam dayalı
                    medula_x = 0  # Sola tam dayalı
                    medula_y = 0  # Üstten başla
                    medula_width = int(screen_width * 0.8)  # Genişlik %80
                    medula_height = screen_height - 40  # Taskbar için alttan boşluk

                    # Pencere handle'ını al
                    medula_hwnd = self.main_window.handle

                    # Eğer maximize ise önce restore et
                    try:
                        placement = win32gui.GetWindowPlacement(medula_hwnd)
                        if placement[1] == win32con.SW_SHOWMAXIMIZED:
                            win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                            time.sleep(self.timing.get("pencere_restore"))
                    except:
                        pass

                    # Pencereyi direkt MoveWindow ile yerleştir
                    win32gui.MoveWindow(medula_hwnd, medula_x, medula_y, medula_width, medula_height, True)
                    time.sleep(self.timing.get("pencere_move"))

                    # İkinci kez ayarla (bazı programlar ilk seferde tam oturmuyor)
                    win32gui.MoveWindow(medula_hwnd, medula_x, medula_y, medula_width, medula_height, True)

                    logger.info(f"✓ MEDULA sol %80'e yerleşti ({medula_width}x{medula_height})")

                except Exception as e:
                    logger.error(f"Pencere boyutlandırılamadı: {e}", exc_info=True)

            return True

        except ElementNotFoundError:
            logger.error(f"'{pencere_basligi}' penceresi bulunamadı!")
            logger.info("Lütfen Medulla programının açık olduğundan emin olun.")
            return False
        except Exception as e:
            logger.error(f"Bağlantı hatası: {e}")
            return False

    def _get_cached_element(self, cache_key):
        """
        Cache'den element al

        Args:
            cache_key (str): Cache anahtarı

        Returns:
            Element veya None
        """
        if not self._cache_enabled:
            return None

        if cache_key in self._element_cache:
            try:
                element = self._element_cache[cache_key]
                # Element hala geçerli mi kontrol et
                _ = element.window_text()
                return element
            except:
                # Element artık geçersiz, cache'den sil
                del self._element_cache[cache_key]
                return None
        return None

    def _cache_element(self, cache_key, element):
        """
        Elementi cache'e ekle

        Args:
            cache_key (str): Cache anahtarı
            element: Cache'lenecek element
        """
        if self._cache_enabled and element is not None:
            self._element_cache[cache_key] = element

    def _clear_cache(self):
        """Tüm cache'i temizle"""
        self._element_cache.clear()
        logger.debug("🗑️ Element cache temizlendi")

    def _clear_cache_key(self, cache_key):
        """Belirli bir cache anahtarını temizle"""
        if cache_key in self._element_cache:
            del self._element_cache[cache_key]

    def ilac_butonuna_tikla(self):
        """
        İlaç butonuna tıkla (CACHE KAPALI - web kontrolü değişken)

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.info("İlaç butonu aranıyor...")

            # İlaç butonu web kontrolü - cache'leme (referans değişiyor)

            # Tüm butonları bul
            try:
                # AutomationId ile ara (OPTIMIZE: control_type eklendi, f: öneki eklendi)
                ilac_button = self.main_window.descendants(auto_id="f:buttonIlacListesi", control_type="Button")
                if ilac_button and len(ilac_button) > 0:
                    # Web kontrolü - CACHE YOK
                    ilac_button[0].click_input()
                    logger.info("✓ İlaç butonuna tıklandı")
                    time.sleep(self.timing.get("ilac_butonu"))
                    return True
            except Exception as e:
                pass

            # Alternatif: Name ile ara (OPTIMIZE: control_type eklendi)
            try:
                ilac_button = self.main_window.descendants(title="İlaç", control_type="Button")
                if ilac_button and len(ilac_button) > 0:
                    # Web kontrolü - CACHE YOK
                    # Farklı tıklama yöntemlerini dene
                    try:
                        ilac_button[0].invoke()
                    except:
                        try:
                            ilac_button[0].click()
                        except:
                            ilac_button[0].click_input()

                    logger.info("✓ İlaç butonuna tıklandı")
                    time.sleep(self.timing.get("ilac_butonu"))
                    return True
            except Exception as e2:
                pass

            logger.error("❌ İlaç butonu bulunamadı")
            return False

        except Exception as e:
            logger.error(f"❌ İlaç butonu hatası: {e}")
            return False

    def ilac_ekrani_yuklendi_mi(self, max_bekleme=3):
        """
        "Kullanılan İlaç Listesi" ekranının yüklenip yüklenmediğini kontrol et

        Args:
            max_bekleme: Maksimum bekleme süresi (saniye)

        Returns:
            bool: Ekran yüklendi ise True
        """
        try:
            baslangic = time.time()
            while time.time() - baslangic < max_bekleme:
                # "Kullanılan İlaç Listesi" yazısını ara
                texts = self.main_window.descendants(control_type="Text")
                for text in texts:
                    try:
                        text_value = text.window_text()
                        if "Kullanılan İlaç Listesi" in text_value or "Kullanilan İlaç Listesi" in text_value:
                            logger.info("✓ İlaç ekranı yüklendi")
                            return True
                    except:
                        pass

                time.sleep(self.timing.get("ilac_ekran_bekleme"))

            logger.warning("⚠️ İlaç ekranı yüklenemedi")
            return False

        except Exception as e:
            logger.error(f"Ekran kontrol hatası: {e}")
            return False

    def recete_not_penceresini_kapat(self, max_bekleme=0.1):  # Hızlandırıldı: 0.2 → 0.1
        """
        "REÇETE İÇİN NOT" penceresi varsa Kapat butonuna bas

        Args:
            max_bekleme: Maksimum bekleme süresi (saniye)

        Returns:
            bool: Pencere kapatıldıysa True, bulunamadıysa False
        """
        try:
            baslangic = time.time()
            anahtar = "REÇETE İÇİN NOT"

            def kapat_butonunu_bul_ve_tikla(kok):
                if kok is None:
                    return False
                try:
                    buttons = kok.descendants(title="KAPAT", control_type="Button")
                except Exception:
                    buttons = []
                for btn in buttons:
                    try:
                        try:
                            btn.invoke()
                        except Exception:
                            try:
                                btn.click()
                            except Exception:
                                btn.click_input()
                        logger.info("✓ REÇETE İÇİN NOT kapatıldı")
                        time.sleep(self.timing.get("popup_kapat"))
                        return True
                    except Exception:
                        continue
                return False

            # Önce mevcut ana pencerede ara
            if self.main_window:
                try:
                    texts = self.main_window.descendants(control_type="Text")
                except Exception:
                    texts = []

                for text in texts:
                    try:
                        icerik = text.window_text() or ""
                    except Exception:
                        continue

                    if anahtar in icerik:
                        hedef = text
                        # Önce bulunduğu konteynerde ara
                        if kapat_butonunu_bul_ve_tikla(hedef.parent()):
                            return True
                        # 3 seviye yukarı çıkarak tekrar dene
                        ata = hedef.parent()
                        for _ in range(3):
                            try:
                                ata = ata.parent()
                            except Exception:
                                ata = None
                            if kapat_butonunu_bul_ve_tikla(ata):
                                return True
                        # Ana pencerede tekrar dene
                        if kapat_butonunu_bul_ve_tikla(self.main_window):
                            return True
                        # Hedef bulundu ama kapatılamadıysa tekrar arama yapma
                        return False

            # Gerekiyorsa kısa bir Desktop taraması yap
            kalan = max_bekleme - (time.time() - baslangic)
            if kalan <= 0:
                return False

            from pywinauto import Desktop
            try:
                windows = Desktop(backend="uia").windows()
            except Exception:
                return False

            for window in windows:
                try:
                    texts = window.descendants(control_type="Text")
                except Exception:
                    continue

                hedef_bulundu = False
                for text in texts:
                    try:
                        if anahtar in (text.window_text() or ""):
                            hedef_bulundu = True
                            break
                    except Exception:
                        continue

                if not hedef_bulundu:
                    continue

                if kapat_butonunu_bul_ve_tikla(window):
                    return True

            return False

        except Exception as e:
            logger.error(f"REÇETE İÇİN NOT kapatma hatası: {e}")
            return False

    def uyari_penceresini_kapat(self, max_bekleme=0.1):
        """
        "UYARIDIR" veya "GENEL MUAYENE TANISI" içeren uyarı pencerelerini "Kapat" butonuna tıklayarak kapat

        Args:
            max_bekleme: Maksimum bekleme süresi (saniye)

        Returns:
            bool: Pencere kapatıldıysa True, bulunamadıysa False
        """
        try:
            baslangic = time.time()
            anahtar_ifadeler = ["UYARIDIR", "GENEL MUAYENE TANISI VARDIR", "ICD EKLEME GEREKLİ"]

            def kapat_butonunu_bul_ve_tikla(kok):
                if kok is None:
                    return False
                try:
                    # "Kapat" butonunu ara
                    buttons = kok.descendants(title="Kapat", control_type="Button")
                except Exception:
                    buttons = []
                for btn in buttons:
                    try:
                        try:
                            btn.invoke()
                        except Exception:
                            try:
                                btn.click()
                            except Exception:
                                btn.click_input()
                        logger.info("✓ Uyarı penceresi kapatıldı")
                        time.sleep(self.timing.get("uyari_kapat"))
                        return True
                    except Exception:
                        continue
                return False

            # Önce mevcut ana pencerede ara
            if self.main_window:
                try:
                    texts = self.main_window.descendants(control_type="Text")
                except Exception:
                    texts = []

                for text in texts:
                    try:
                        icerik = (text.window_text() or "").upper()
                    except Exception:
                        continue

                    # Anahtar ifadelerden birini içeriyorsa
                    if any(anahtar.upper() in icerik for anahtar in anahtar_ifadeler):
                        hedef = text
                        # Önce bulunduğu konteynerde ara
                        if kapat_butonunu_bul_ve_tikla(hedef.parent()):
                            return True
                        # 3 seviye yukarı çıkarak tekrar dene
                        ata = hedef.parent()
                        for _ in range(3):
                            try:
                                ata = ata.parent()
                            except Exception:
                                ata = None
                            if kapat_butonunu_bul_ve_tikla(ata):
                                return True
                        # Ana pencerede tekrar dene
                        if kapat_butonunu_bul_ve_tikla(self.main_window):
                            return True
                        # Hedef bulundu ama kapatılamadıysa tekrar arama yapma
                        return False

            # Gerekiyorsa kısa bir Desktop taraması yap
            kalan = max_bekleme - (time.time() - baslangic)
            if kalan <= 0:
                return False

            from pywinauto import Desktop
            try:
                windows = Desktop(backend="uia").windows()
            except Exception:
                return False

            for window in windows:
                try:
                    texts = window.descendants(control_type="Text")
                except Exception:
                    continue

                hedef_bulundu = False
                for text in texts:
                    try:
                        icerik = (text.window_text() or "").upper()
                        if any(anahtar.upper() in icerik for anahtar in anahtar_ifadeler):
                            hedef_bulundu = True
                            break
                    except Exception:
                        continue

                if not hedef_bulundu:
                    continue

                if kapat_butonunu_bul_ve_tikla(window):
                    return True

            return False

        except Exception as e:
            logger.error(f"Uyarı penceresi kapatma hatası: {e}")
            return False

    def laba_lama_uyarisini_kapat(self, max_bekleme=1.5, detayli_log=True):
        """
        LABA/LAMA ve İlaç Çakışması uyarılarını "Tamam" butonuna tıklayarak kapat

        Args:
            max_bekleme: Maksimum bekleme süresi (saniye)
            detayli_log: Detaylı debug logları yaz (varsayılan True)

        Returns:
            bool: Uyarı kapatıldı ise True
        """
        try:
            from pywinauto import Desktop

            if detayli_log:
                logger.debug(f"🔍 LABA/LAMA uyarısı aranıyor (max {max_bekleme}s)...")

            baslangic = time.time()
            # LABA/LAMA ve İlaç Çakışması uyarıları için anahtar ifadeler
            laba_ifadeler = ("LABA-LAMA", "LABA / LAMA", "LABA/LAMA")
            ilac_cakismasi_ifadeler = ("İLAÇ ÇAKIŞMASI", "ILAC CAKISMASI", "ÇAKIŞMASI VARDIR", "CAKISMASI VARDIR")

            desktop = Desktop(backend="uia")

            while time.time() - baslangic < max_bekleme:
                try:
                    windows = desktop.windows()
                except Exception:
                    windows = []

                for window in windows:
                    try:
                        # Tüm butonları al
                        all_buttons = window.descendants(control_type="Button")
                        # "Tamam" veya "Taman" içerenleri filtrele (büyük/küçük harf duyarsız)
                        buttons = [
                            btn for btn in all_buttons
                            if btn.window_text() and "TAMA" in btn.window_text().upper()
                        ]
                        if detayli_log and buttons:
                            logger.debug(f"  → {len(buttons)} TAMA* butonu bulundu: {[btn.window_text() for btn in buttons]}")
                    except Exception:
                        buttons = []

                    if not buttons:
                        continue

                    try:
                        # Tüm elementleri kontrol et (sadece Text değil)
                        texts = window.descendants()
                    except Exception:
                        texts = []

                    # LABA/LAMA uyarısını kontrol et
                    laba_bulundu = any(
                        (text.window_text() or "").upper().find(ifade) >= 0
                        for text in texts
                        for ifade in laba_ifadeler
                    )

                    # İlaç çakışması uyarısını kontrol et
                    ilac_cakismasi_bulundu = any(
                        (text.window_text() or "").upper().find(ifade) >= 0
                        for text in texts
                        for ifade in ilac_cakismasi_ifadeler
                    )

                    # Her iki uyarıdan birini bulduysa kapat
                    if not (laba_bulundu or ilac_cakismasi_bulundu):
                        continue

                    # Hangi uyarı bulunduğunu belirle
                    uyari_tipi = "LABA/LAMA" if laba_bulundu else "İlaç Çakışması"
                    logger.info(f"⚠ {uyari_tipi} uyarısı bulundu! Kapatılıyor...")

                    for btn in buttons:
                        try:
                            try:
                                btn.invoke()
                            except Exception:
                                try:
                                    btn.click()
                                except Exception:
                                    btn.click_input()
                            logger.info(f"✓ {uyari_tipi} uyarısı kapatıldı")
                            time.sleep(self.timing.get("laba_uyari"))
                            return True
                        except Exception:
                            continue

                time.sleep(self.timing.get("popup_kapat"))

            return False

        except Exception as e:
            logger.error(f"Popup uyarısı kontrol hatası: {e}", exc_info=True)
            return False

    def y_tusuna_tikla(self):
        """
        Y tuşuna tıkla (CACHE destekli)

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            # Önce cache'den kontrol et
            cached_button = self._get_cached_element("y_button")
            if cached_button:
                try:
                    cached_button.invoke()
                    logger.info("✓ Y butonuna tıklandı (cache)")
                    time.sleep(self.timing.get("y_butonu"))
                    return True
                except:
                    self._clear_cache_key("y_button")

            # Name ile Y butonunu ara (OPTIMIZE: control_type eklendi)
            try:
                y_button = self.main_window.descendants(title="Y", control_type="Button")
                if y_button and len(y_button) > 0:
                    self._cache_element("y_button", y_button[0])  # Cache'e ekle
                    # Farklı tıklama yöntemlerini dene
                    try:
                        # Yöntem 1: Invoke pattern
                        y_button[0].invoke()
                        logger.info("✓ Y butonuna tıklandı")
                    except:
                        try:
                            y_button[0].click()
                            logger.info("✓ Y butonuna tıklandı")
                        except:
                            y_button[0].click_input()
                            logger.info("✓ Y butonuna tıklandı")

                    time.sleep(self.timing.get("y_butonu"))
                    return True
                else:
                    logger.warning("❌ Y butonu yok")
                    return False
            except Exception as e:
                logger.error(f"Y butonu hatası: {e}")
                return False

        except Exception as e:
            logger.error(f"Y tıklama hatası: {e}")
            return False

    def yeni_pencereyi_bul(self, pencere_basligi_iceren="İlaç Listesi"):
        """
        Yeni açılan pencereyi bul ve bağlan

        Args:
            pencere_basligi_iceren (str): Pencere başlığında aranacak kelime

        Returns:
            bool: Pencere bulundu ise True
        """
        try:
            from pywinauto import Desktop
            windows = Desktop(backend="uia").windows()

            for window in windows:
                try:
                    window_title = window.window_text()
                    if pencere_basligi_iceren in window_title:
                        self.main_window = window
                        return True
                except:
                    pass

            logger.warning(f"❌ '{pencere_basligi_iceren}' bulunamadı")
            return False

        except Exception as e:
            logger.error(f"Pencere arama hatası: {e}")
            return False

    def bizden_alinanlarin_sec_tusuna_tikla(self):
        """
        Bizden Alınmayanları Seç butonuna tıkla

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            # Name ile butonu ara (kısmi eşleşme kullan)
            try:
                # Tüm butonları al ve "Alınmayanları Seç" içereni bul
                buttons = self.main_window.descendants(control_type="Button")
                bizden_button = None

                for btn in buttons:
                    try:
                        btn_text = btn.window_text()
                        if "Alınmayanları Seç" in btn_text or "Alınanları Seç" in btn_text:
                            bizden_button = [btn]
                            break
                    except:
                        pass
                if bizden_button and len(bizden_button) > 0:
                    # Farklı tıklama yöntemlerini dene
                    try:
                        bizden_button[0].invoke()
                    except:
                        try:
                            bizden_button[0].click()
                        except:
                            bizden_button[0].click_input()

                    logger.info("✓ Alınmayanları seç")
                    return True
                else:
                    logger.warning("❌ Alınmayanları seç yok")
                    return False
            except Exception as e:
                logger.error(f"Buton arama hatası: {e}")
                return False

        except Exception as e:
            logger.error(f"Tıklama hatası: {e}")
            return False

    def ilac_secili_mi_kontrol(self):
        """
        İlaçlardan herhangi biri seçili mi kontrol et

        Returns:
            tuple: (bool: En az 1 ilaç seçili ise True, int: seçili ilaç sayısı)
        """
        try:
            # Tüm DataItem'ları bul
            cells = self.main_window.descendants(control_type="DataItem")

            secili_sayisi = 0
            toplam_ilac = 0

            for cell in cells:
                try:
                    cell_name = cell.window_text()
                    if "Seçim satır" in cell_name:
                        toplam_ilac += 1

                        # Farklı yöntemlerle seçilim kontrolü
                        secili = False

                        # Yöntem 1: Value özelliğini kontrol et
                        try:
                            value = cell.legacy_properties().get('Value', '')
                            if value == "Seçili":
                                secili = True
                        except:
                            pass

                        # Yöntem 2: Toggle state
                        try:
                            toggle_state = cell.get_toggle_state()
                            if toggle_state == 1:
                                secili = True
                        except:
                            pass

                        if secili:
                            secili_sayisi += 1

                except:
                    pass

            logger.info(f"→ {secili_sayisi}/{toplam_ilac} ilaç seçili")

            return (secili_sayisi > 0, secili_sayisi)

        except Exception as e:
            logger.error(f"İlaç seçilim kontrolü hatası: {e}")
            return (False, 0)

    def ilk_ilaca_sag_tik_ve_takip_et(self):
        """
        İlk ilaca (Seçim satır 1) sağ tıkla ve "Takip Et" seç

        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            logger.info("İlk ilaca sağ tıklama yapılıyor...")

            # "Seçim satır 1" hücresini bul
            cells = self.main_window.descendants(control_type="DataItem")

            ilk_ilac = None
            for cell in cells:
                try:
                    cell_name = cell.window_text()
                    if "Seçim satır 1" in cell_name:
                        ilk_ilac = cell
                        logger.info(f"İlk ilaç bulundu: {cell_name}")
                        break
                except:
                    pass

            if ilk_ilac is None:
                logger.error("İlk ilaç bulunamadı")
                return False

            # Sağ tık yap
            ilk_ilac.click_input(button='right')
            time.sleep(self.timing.get("sag_tik"))

            # "Takip Et" menü öğesini bul ve tıkla
            try:
                # Menü öğelerini bul
                menu_items = self.main_window.descendants(control_type="MenuItem")

                for item in menu_items:
                    try:
                        item_name = item.window_text()
                        if "Takip Et" in item_name:
                            item.click_input()
                            logger.info("✓ Takip Et tıklandı")
                            time.sleep(self.timing.get("takip_et"))
                            return True
                    except:
                        pass

                logger.error("❌ Takip Et bulunamadı")
                return False

            except Exception as e:
                logger.error(f"Menü öğesi arama hatası: {e}")
                return False

        except Exception as e:
            logger.error(f"Sağ tıklama hatası: {e}")
            return False

    def ilac_listesi_penceresini_kapat(self):
        """
        İlaç Listesi penceresini kapat

        Returns:
            bool: Kapatma başarılı ise True
        """
        try:
            # "Kapat" butonunu bul
            buttons = self.main_window.descendants(control_type="Button")

            for btn in buttons:
                try:
                    btn_name = btn.window_text()
                    if btn_name == "Kapat":
                        btn.click_input()
                        logger.info("✓ Pencere kapatıldı")
                        time.sleep(self.timing.get("kapat_butonu"))
                        return True
                except:
                    pass

            logger.warning("❌ Kapat butonu yok")
            return False

        except Exception as e:
            logger.error(f"Pencere kapatma hatası: {e}")
            return False

    def geri_don_butonuna_tikla(self):
        """
        Ana Medula ekranında Geri Dön butonuna tıkla (Web kontrolü - CACHE YOK)

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            # Web kontrolü - sayfa yenileniyor, cache güvenli değil

            # Geri Dön butonunu bul
            buttons = self.main_window.descendants(control_type="Button")

            for btn in buttons:
                try:
                    btn_name = btn.window_text()
                    if "Geri Dön" in btn_name or "Geri Don" in btn_name:
                        # Web kontrolü - CACHE YOK
                        # Tıklama yöntemleri
                        try:
                            btn.invoke()
                        except:
                            try:
                                btn.click()
                            except:
                                btn.click_input()

                        logger.info("✓ Geri Dön tıklandı")
                        time.sleep(self.timing.get("geri_don_butonu"))
                        return True
                except:
                    pass

            logger.warning("❌ Geri Dön bulunamadı")
            return False

        except Exception as e:
            logger.error(f"Geri Dön butonuna tıklama hatası: {e}")
            return False

    def sonra_butonuna_tikla(self):
        """
        SONRA > butonuna tıklayarak bir sonraki reçeteye geç (Web kontrolü - CACHE YOK)

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            # Web kontrolü - sayfa yenileniyor, cache güvenli değil

            # SONRA butonunu bul
            buttons = self.main_window.descendants(control_type="Button")

            for btn in buttons:
                try:
                    btn_name = btn.window_text()
                    if "Sonra" in btn_name and ">" in btn_name:
                        # Web kontrolü - CACHE YOK
                        # Tıklama yöntemleri
                        try:
                            btn.invoke()
                        except:
                            try:
                                btn.click()
                            except:
                                btn.click_input()

                        logger.info("✓ SONRA > Sonraki reçete")
                        time.sleep(self.timing.get("sonra_butonu"))
                        return True
                except:
                    pass

            logger.warning("❌ SONRA yok (Son reçete)")
            return False

        except Exception as e:
            logger.error(f"SONRA butonuna tıklama hatası: {e}")
            return False

    def recete_no_oku(self):
        """
        Ekrandaki reçete numarasını oku (örn: 3HKE0T4)
        Inspect'e göre Window 0x1C0D14 ve Name özelliğinden alınır

        Returns:
            str: Reçete numarası, bulunamazsa None
        """
        try:
            # Önce spesifik window ID ile dene
            try:
                # Text kontrollerini ara, Name özelliği içinde reçete numarası olan
                texts = self.main_window.descendants(control_type="Text")

                for text in texts:
                    try:
                        # Name özelliğini al
                        name_prop = text.window_text()

                        # Reçete numarası formatı: 6-8 karakter, alfanumerik
                        if name_prop and 6 <= len(name_prop) <= 9:
                            # Sadece harf, rakam içermeli
                            if name_prop.replace('-', '').replace('_', '').isalnum():
                                # En az 1 harf ve 1 rakam olmalı
                                if any(c.isdigit() for c in name_prop) and any(c.isalpha() for c in name_prop):
                                    logger.info(f"✓ Reçete No: {name_prop}")
                                    return name_prop
                    except:
                        pass

            except Exception as e:
                logger.debug(f"ID ile arama başarısız: {e}")

            # Alternatif: Tüm text elementlerini tara
            texts = self.main_window.descendants(control_type="Text")

            for text in texts:
                try:
                    text_value = text.window_text()
                    # Reçete numarası genellikle 7 karakterli alfanumerik kod (örn: 3HKE0T4)
                    if text_value and 6 <= len(text_value) <= 9:
                        # Sadece harf, rakam ve belki tire içermeli
                        cleaned = text_value.replace('-', '').replace('_', '')
                        if cleaned.isalnum() and any(c.isdigit() for c in text_value) and any(c.isalpha() for c in text_value):
                            logger.info(f"✓ Reçete No: {text_value}")
                            return text_value
                except:
                    pass

            logger.warning("⚠️ Reçete numarası okunamadı")
            return None

        except Exception as e:
            logger.error(f"Reçete no okuma hatası: {e}")
            return None

    def recete_kaydi_var_mi_kontrol(self):
        """
        Ekranda "Reçete kaydı bulunamadı" veya "Sistem hatası" uyarısı var mı kontrol et

        Returns:
            bool: Reçete kaydı VARSA True, YOKSA (uyarı varsa) False
        """
        try:
            # Tüm text elementlerini ara
            texts = self.main_window.descendants(control_type="Text")

            for text in texts:
                try:
                    text_value = text.window_text()
                    # "Reçete kaydı bulunamadı" kontrolü
                    if "Reçete kaydı bulunamadı" in text_value or "Recete kaydı bulunamadı" in text_value:
                        logger.warning(f"⚠️ '{text_value}'")
                        return False
                    # "Sistem hatası" kontrolü
                    if "Sistem hatası" in text_value or "Sistem hatasi" in text_value:
                        logger.error(f"❌ MEDULA HATA: '{text_value}'")
                        return False
                except:
                    pass

            return True

        except Exception as e:
            logger.error(f"Kontrol hatası: {e}")
            # Hata durumunda güvenli tarafta kalalım ve devam edelim
            return True

    def recete_sorgu_ac(self):
        """
        Reçete Sorgu butonuna tıkla (CACHE destekli)

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.info("Reçete Sorgu butonu aranıyor...")

            # Önce cache'den kontrol et
            cached_button = self._get_cached_element("recete_sorgu_button")
            if cached_button:
                try:
                    cached_button.invoke()
                    logger.info("✓ Reçete Sorgu butonu tıklandı (cache)")
                    time.sleep(self.timing.get("recete_sorgu"))
                    return True
                except:
                    self._clear_cache_key("recete_sorgu_button")

            # Yöntem 1: AutomationId ile ara (OPTIMIZE: control_type eklendi)
            try:
                sorgu_button = self.main_window.descendants(auto_id="form1:menuHtmlCommandExButton51_MOUSE", control_type="Button")
                if sorgu_button and len(sorgu_button) > 0:
                    self._cache_element("recete_sorgu_button", sorgu_button[0])  # Cache'e ekle
                    try:
                        sorgu_button[0].invoke()
                    except:
                        try:
                            sorgu_button[0].click()
                        except:
                            sorgu_button[0].click_input()

                    logger.info("✓ Reçete Sorgu butonu tıklandı (AutomationId)")
                    time.sleep(self.timing.get("recete_sorgu"))
                    return True
            except Exception as e:
                logger.debug(f"AutomationId ile bulunamadı: {e}")

            # Yöntem 2: Name ile ara (Control Type 50000)
            try:
                buttons = self.main_window.descendants(control_type="Button")
                for btn in buttons:
                    try:
                        btn_name = btn.window_text()
                        # TAM EŞLEŞİK kontrolü - "e-Reçete Sorgu" gibi yanlış butonları atla
                        if btn_name:
                            btn_name_stripped = btn_name.strip()
                            # Sadece "Reçete Sorgu" veya "Recete Sorgu" olanları al
                            # "e-Reçete Sorgu", "E-Reçete Sorgu" vb. HARİÇ
                            if btn_name_stripped == "Reçete Sorgu" or btn_name_stripped == "Recete Sorgu":
                                self._cache_element("recete_sorgu_button", btn)  # Cache'e ekle
                                try:
                                    btn.invoke()
                                except:
                                    try:
                                        btn.click()
                                    except:
                                        btn.click_input()

                                logger.info("✓ Reçete Sorgu butonu tıklandı (Name)")
                                time.sleep(self.timing.get("recete_sorgu"))
                                return True
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Name ile bulunamadı: {e}")

            # Yöntem 3: Tüm kontrolleri tara
            try:
                all_controls = self.main_window.descendants()
                for ctrl in all_controls:
                    try:
                        ctrl_name = ctrl.window_text()
                        # TAM EŞLEŞİK kontrolü - "e-Reçete Sorgu" gibi yanlış butonları atla
                        if ctrl_name:
                            ctrl_name_stripped = ctrl_name.strip()
                            # Sadece "Reçete Sorgu" veya "Recete Sorgu" olanları al
                            if ctrl_name_stripped == "Reçete Sorgu" or ctrl_name_stripped == "Recete Sorgu":
                                self._cache_element("recete_sorgu_button", ctrl)  # Cache'e ekle
                                try:
                                    ctrl.invoke()
                                except:
                                    try:
                                        ctrl.click()
                                    except:
                                        ctrl.click_input()

                                logger.info("✓ Reçete Sorgu butonu tıklandı (Tüm kontroller)")
                                time.sleep(self.timing.get("recete_sorgu"))
                                return True
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Tüm kontroller ile bulunamadı: {e}")

            logger.error("❌ Reçete Sorgu butonu bulunamadı (tüm yöntemler denendi)")
            return False

        except Exception as e:
            logger.error(f"Reçete Sorgu butonu hatası: {e}")
            return False

    def ana_sayfaya_don(self):
        """
        Ana Sayfa butonuna tıkla (Reçete içindeyken sol menü çıkması için) (CACHE destekli)

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.info("Ana Sayfa butonu aranıyor...")

            # Önce cache'den kontrol et
            cached_button = self._get_cached_element("ana_sayfa_button")
            if cached_button:
                try:
                    cached_button.invoke()
                    logger.info("✓ Ana Sayfa butonu tıklandı (cache)")
                    time.sleep(self.timing.get("ana_sayfa"))
                    return True
                except:
                    self._clear_cache_key("ana_sayfa_button")

            # Yöntem 1: AutomationId ile ara (OPTIMIZE: control_type eklendi, f: öneki eklendi)
            try:
                ana_sayfa_button = self.main_window.descendants(auto_id="f:buttonAnaSayfa", control_type="Button")
                if ana_sayfa_button and len(ana_sayfa_button) > 0:
                    self._cache_element("ana_sayfa_button", ana_sayfa_button[0])  # Cache'e ekle
                    try:
                        ana_sayfa_button[0].invoke()
                    except:
                        try:
                            ana_sayfa_button[0].click()
                        except:
                            ana_sayfa_button[0].click_input()

                    logger.info("✓ Ana Sayfa butonu tıklandı (AutomationId)")
                    time.sleep(self.timing.get("ana_sayfa"))
                    return True
            except Exception as e:
                logger.debug(f"AutomationId ile bulunamadı: {e}")

            # Yöntem 2: Name ile ara
            try:
                buttons = self.main_window.descendants(control_type="Button")
                for btn in buttons:
                    try:
                        btn_name = btn.window_text()
                        if btn_name and btn_name.strip() == "Ana Sayfa":
                            self._cache_element("ana_sayfa_button", btn)  # Cache'e ekle
                            try:
                                btn.invoke()
                            except:
                                try:
                                    btn.click()
                                except:
                                    btn.click_input()

                            logger.info("✓ Ana Sayfa butonu tıklandı (Name)")
                            time.sleep(self.timing.get("ana_sayfa"))
                            return True
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Name ile bulunamadı: {e}")

            logger.error("❌ Ana Sayfa butonu bulunamadı")
            return False

        except Exception as e:
            logger.error(f"Ana Sayfa butonu hatası: {e}")
            return False

    def recete_no_yaz(self, recete_no):
        """
        Reçete numarasını giriş alanına yaz

        Args:
            recete_no (str): Yazılacak reçete numarası

        Returns:
            bool: Yazma başarılı ise True
        """
        try:
            logger.info(f"Reçete numarası yazılıyor: {recete_no}")

            # Yöntem 1: AutomationId ile spesifik alanı bul (form1:text2) (OPTIMIZE: control_type eklendi)
            try:
                recete_no_field = self.main_window.descendants(auto_id="form1:text2", control_type="Edit")
                if recete_no_field and len(recete_no_field) > 0:
                    edit = recete_no_field[0]

                    # Focus'u al
                    edit.set_focus()
                    time.sleep(self.timing.get("text_focus"))

                    # Önce temizle
                    try:
                        edit.set_edit_text("")
                        time.sleep(self.timing.get("text_clear"))
                    except:
                        pass

                    # Yeni değeri yaz
                    edit.set_edit_text(recete_no)
                    time.sleep(self.timing.get("text_write"))

                    # Kontrol et
                    try:
                        current_value = edit.get_value()
                        if current_value == recete_no:
                            logger.info(f"✓ Reçete numarası yazıldı (AutomationId): {recete_no}")
                            return True
                    except:
                        pass

                    # Alternatif kontrol
                    try:
                        current_text = edit.window_text()
                        if current_text == recete_no:
                            logger.info(f"✓ Reçete numarası yazıldı (AutomationId): {recete_no}")
                            return True
                    except:
                        pass

                    # Yazma işlemi yapıldı ama doğrulama yapılamadı
                    logger.info(f"✓ Reçete numarası yazıldı (AutomationId, doğrulama yok): {recete_no}")
                    return True

            except Exception as e:
                logger.debug(f"AutomationId ile yazılamadı: {e}")

            # Yöntem 2: Control Type 50004 (Edit control) - İLK BOŞ edit alanını bul
            try:
                edit_controls = self.main_window.descendants(control_type="Edit")

                # İlk BOŞ edit alanını bul (TC kimlik dolu, reçete numarası boş)
                for i, edit in enumerate(edit_controls):
                    try:
                        # Mevcut değeri kontrol et
                        current_value = ""
                        try:
                            current_value = edit.get_value() or ""
                        except:
                            try:
                                current_value = edit.window_text() or ""
                            except:
                                pass

                        # BOŞ değilse atla
                        if current_value.strip():
                            continue

                        # Boş bulundu, buraya yaz
                        edit.set_focus()
                        time.sleep(self.timing.get("text_focus"))

                        # Temizle
                        edit.set_edit_text("")
                        time.sleep(self.timing.get("text_clear"))

                        # Yeni değeri yaz
                        edit.set_edit_text(recete_no)
                        time.sleep(self.timing.get("text_write"))

                        # Kontrol et
                        try:
                            current_value = edit.get_value()
                        except:
                            try:
                                current_value = edit.window_text()
                            except:
                                pass

                        if current_value == recete_no:
                            logger.info(f"✓ Reçete numarası yazıldı (İlk boş Edit): {recete_no}")
                            return True
                    except:
                        continue

                logger.error("❌ Reçete numarası alanı bulunamadı")
                return False

            except Exception as e:
                logger.error(f"Edit kontrol hatası: {e}")
                return False

        except Exception as e:
            logger.error(f"Reçete numarası yazma hatası: {e}")
            return False

    def sorgula_butonuna_tikla(self):
        """
        Sorgula butonuna tıkla (ÜSTTEKİ Reçete Numarası yanındaki) (CACHE destekli)

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.info("Sorgula butonu aranıyor...")

            # Önce cache'den kontrol et
            cached_button = self._get_cached_element("sorgula_button")
            if cached_button:
                try:
                    cached_button.invoke()
                    logger.info("✓ Sorgula butonu tıklandı (cache)")
                    time.sleep(self.timing.get("sorgula_butonu"))
                    return True
                except:
                    self._clear_cache_key("sorgula_button")

            # Yöntem 1: AutomationId ile ara (EN DOĞRUSU) (OPTIMIZE: control_type eklendi)
            try:
                sorgula_button = self.main_window.descendants(auto_id="form1:buttonReceteNoSorgula", control_type="Button")
                if sorgula_button and len(sorgula_button) > 0:
                    self._cache_element("sorgula_button", sorgula_button[0])  # Cache'e ekle
                    try:
                        sorgula_button[0].invoke()
                    except:
                        try:
                            sorgula_button[0].click()
                        except:
                            sorgula_button[0].click_input()

                    logger.info("✓ Sorgula butonu tıklandı (AutomationId)")
                    time.sleep(self.timing.get("sorgula_butonu"))
                    return True
            except Exception as e:
                logger.debug(f"AutomationId ile bulunamadı: {e}")

            # Yöntem 2: Name="Sorgula" + İLK buton (en üstteki)
            try:
                buttons = self.main_window.descendants(control_type="Button")
                for btn in buttons:
                    try:
                        btn_name = btn.window_text()
                        if btn_name and btn_name.strip() == "Sorgula":
                            self._cache_element("sorgula_button", btn)  # Cache'e ekle
                            # İLK "Sorgula" butonunu bul (en üstteki)
                            try:
                                btn.invoke()
                            except:
                                try:
                                    btn.click()
                                except:
                                    btn.click_input()

                            logger.info("✓ Sorgula butonu tıklandı (İlk Sorgula)")
                            time.sleep(self.timing.get("sorgula_butonu"))
                            return True
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Name ile bulunamadı: {e}")

            logger.error("❌ Sorgula butonu bulunamadı (tüm yöntemler denendi)")
            return False

        except Exception as e:
            logger.error(f"Sorgula butonu hatası: {e}")
            return False

    def recete_bilgilerini_al(self):
        """
        Ekrandaki reçete bilgilerini al
        (Gelecekte geliştirilecek)
        """
        logger.info("Reçete bilgileri alınıyor...")
        # TODO: Reçete bilgilerini okuma işlemi
        pass

    def tum_butonlari_listele(self):
        """Debug için penceredeki tüm butonları listele"""
        try:
            logger.info("Penceredeki tüm butonlar listeleniyor...")
            buttons = self.main_window.descendants(control_type="Button")

            if buttons and len(buttons) > 0:
                logger.info(f"Toplam {len(buttons)} buton bulundu:")
                for i, btn in enumerate(buttons, 1):
                    try:
                        btn_name = btn.window_text()
                        if btn_name:
                            logger.info(f"  {i}. Buton: '{btn_name}'")
                    except:
                        pass
            else:
                logger.warning("Hiç buton bulunamadı")
        except Exception as e:
            logger.error(f"Buton listeleme hatası: {e}")

    def pencere_bilgilerini_goster(self):
        """Debug için pencere bilgilerini göster"""
        try:
            if self.main_window:
                logger.info("Pencere Bilgileri:")
                logger.info(f"  Başlık: {self.main_window.window_text()}")
                logger.info(f"  Class: {self.main_window.class_name()}")
                self.main_window.print_control_identifiers()
        except Exception as e:
            logger.error(f"Bilgi gösterme hatası: {e}")


def tek_recete_isle(bot, recete_sira_no):
    """
    Tek bir reçete için tüm işlemleri yap

    Args:
        bot: BotanikBot instance
        recete_sira_no: Reçete sıra numarası (1, 2, 3...)

    Returns:
        tuple: (başarı durumu: bool, medula reçete no: str veya None, takip sayısı: int)
    """
    recete_baslangic = time.time()
    adim_sureleri = []

    def log_sure(ad, baslangic):
        """Bir adımın süresini kaydet ve yazdır."""
        sure = time.time() - baslangic
        adim_sureleri.append((ad, sure))
        logger.info(f"⏱ {ad}: {sure:.2f}s")
        return sure

    medula_recete_no = None
    takip_sayisi = 0  # Takip edilen ilaç sayısı
    baslik_loglandi = False

    def log_recete_baslik(no_degeri=None):
        """Üst başlıkta Reçete sıra ve numarasını göster."""
        nonlocal baslik_loglandi
        if baslik_loglandi:
            return
        no_text = no_degeri if no_degeri else (medula_recete_no if medula_recete_no else "-")
        logger.info(f"📋 REÇETE {recete_sira_no} | No: {no_text}")
        baslik_loglandi = True

    # ÖNEMLİ: Her reçete işlemi başlamadan önce "Reçete kaydı bulunamadı" kontrolü yap
    adim_baslangic = time.time()
    recete_kaydi_var = bot.recete_kaydi_var_mi_kontrol()
    log_sure("Reçete kontrolü", adim_baslangic)
    if not recete_kaydi_var:
        logger.error("❌ Reçete kaydı yok")
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi)

    # REÇETE İÇİN NOT penceresi varsa kapat
    adim_baslangic = time.time()
    if bot.recete_not_penceresini_kapat():
        log_sure("Reçete notu kapatma", adim_baslangic)
    else:
        log_sure("Reçete notu kontrol", adim_baslangic)

    # UYARIDIR (Genel muayene tanısı) penceresi varsa kapat
    adim_baslangic = time.time()
    if bot.uyari_penceresini_kapat():
        log_sure("Uyarı penceresi kapatma", adim_baslangic)
    else:
        log_sure("Uyarı penceresi kontrol", adim_baslangic)

    medula_recete_no = bot.recete_no_oku()
    log_recete_baslik(medula_recete_no)

    # İlaç butonuna tıkla
    adim_baslangic = time.time()
    ilac_butonu = bot.ilac_butonuna_tikla()
    log_sure("İlaç butonu", adim_baslangic)
    if not ilac_butonu:
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi)

    # "Kullanılan İlaç Listesi" ekranının yüklenmesini bekle
    adim_baslangic = time.time()
    ilac_ekrani = bot.ilac_ekrani_yuklendi_mi(max_bekleme=3)
    log_sure("İlaç ekranı yükleme", adim_baslangic)
    if not ilac_ekrani:
        logger.error("❌ İlaç ekranı yüklenemedi")
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi)

    # Y butonuna tıkla
    ana_pencere = bot.main_window
    adim_baslangic = time.time()
    y_butonu = bot.y_tusuna_tikla()
    log_sure("Y butonu", adim_baslangic)
    if not y_butonu:
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi)

    # İlaç Listesi penceresini akıllı bekleme ile bul (max 1 saniye)
    adim_baslangic = time.time()
    ilac_penceresi_bulundu = False
    max_bekleme = 1.0  # Maksimum 1 saniye bekle
    bekleme_baslangic = time.time()

    while time.time() - bekleme_baslangic < max_bekleme:
        ilac_penceresi_bulundu = bot.yeni_pencereyi_bul("İlaç Listesi")
        if ilac_penceresi_bulundu:
            break  # BULUNDU! Hemen devam et
        time.sleep(bot.timing.get("pencere_bulma"))

    log_sure("İlaç penceresi bulma", adim_baslangic)

    # İlaç Listesi bulunamadıysa → LABA/LAMA veya başka uyarı penceresi açıktır
    if not ilac_penceresi_bulundu:
        logger.info("⚠ İlaç Listesi bulunamadı → LABA/LAMA/Uyarı kontrolü yapılıyor...")
        laba_baslangic = time.time()
        laba_kapatildi = bot.laba_lama_uyarisini_kapat(max_bekleme=1.5, detayli_log=True)
        log_sure("LABA/LAMA kontrol", laba_baslangic)

        if laba_kapatildi:
            # Uyarı kapatıldı, tekrar Y butonuna bas
            time.sleep(bot.timing.get("laba_sonrasi_bekleme"))
            adim_baslangic = time.time()
            y_butonu_2 = bot.y_tusuna_tikla()
            log_sure("Y butonu (2. deneme)", adim_baslangic)

            if y_butonu_2:
                time.sleep(bot.timing.get("y_ikinci_deneme"))
                adim_baslangic = time.time()
                ilac_penceresi_bulundu = bot.yeni_pencereyi_bul("İlaç Listesi")
                log_sure("İlaç penceresi 2. bulma", adim_baslangic)

    # Hala bulunamadıysa gerçekten hata
    if not ilac_penceresi_bulundu:
        logger.error("❌ İlaç Listesi penceresi bulunamadı")
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi)

    # "Bizden Alınmayanları Seç" butonunu ara
    adim_baslangic = time.time()
    alinmayan_secildi = bot.bizden_alinanlarin_sec_tusuna_tikla()
    log_sure("Alınmayanları Seç", adim_baslangic)

    # Eğer buton bulunamadıysa → LABA/LAMA uyarısı var olabilir
    if not alinmayan_secildi:
        logger.info("⚠ Bizden Alınmayanları Seç bulunamadı → LABA/LAMA kontrolü yapılıyor...")
        laba_baslangic = time.time()
        laba_kapatildi = bot.laba_lama_uyarisini_kapat(max_bekleme=1.5)
        log_sure("LABA/LAMA kontrol", laba_baslangic)

        if laba_kapatildi:
            # LABA/LAMA kapatıldı, tekrar dene
            time.sleep(bot.timing.get("laba_sonrasi_bekleme"))

            # İlaç Listesi penceresini tekrar bul
            adim_baslangic = time.time()
            ilac_penceresi_bulundu = bot.yeni_pencereyi_bul("İlaç Listesi")
            log_sure("İlaç penceresi 2. bulma", adim_baslangic)

            if ilac_penceresi_bulundu:
                # Tekrar "Bizden Alınmayanları Seç" butonunu ara
                adim_baslangic = time.time()
                alinmayan_secildi = bot.bizden_alinanlarin_sec_tusuna_tikla()
                log_sure("Alınmayanları Seç (2. deneme)", adim_baslangic)

        # Hala bulanamadıysa hata
        if not alinmayan_secildi:
            logger.error("❌ Bizden Alınmayanları Seç butonu bulunamadı (2 deneme)")
            log_recete_baslik()
            return (False, medula_recete_no, takip_sayisi)

    # İlaçların seçilmesini bekle - maksimum 0.6 saniye, ama seçili ilaç bulunca devam et
    adim_baslangic = time.time()
    ilac_var = False
    pencere_kapandi = False

    # Kısa bir süre bekleyip tek taramada seçili satır arıyoruz
    time.sleep(bot.timing.get("ilac_secim_bekleme"))
    cells = bot.main_window.descendants(control_type="DataItem")
    for cell in cells:
        try:
            cell_name = cell.window_text()
            if "Seçim satır" in cell_name:
                try:
                    value = cell.legacy_properties().get('Value', '')
                    if value == "Seçili":
                        ilac_var = True
                        logger.info(f"✓ Seçili ilaç var")
                        break
                except:
                    pass
        except:
            pass

    if ilac_var:
        bot.ilk_ilaca_sag_tik_ve_takip_et()
        # Takip edilen ilaç sayısını al
        var_mi, takip_sayisi = bot.ilac_secili_mi_kontrol()
    else:
        var_mi, takip_sayisi = bot.ilac_secili_mi_kontrol()
        if var_mi:
            bot.ilk_ilaca_sag_tik_ve_takip_et()
        else:
            logger.info("✗ Seçili ilaç yok")
            logger.info("→ Takip Et atlandı")
            kapatma_baslangic = time.time()
            bot.ilac_listesi_penceresini_kapat()
            log_sure("İlaç penceresi kapatma", kapatma_baslangic)
            pencere_kapandi = True

    log_sure("İlaç seçimi", adim_baslangic)

    # Her iki durumda da İlaç Listesi penceresini kapat
    if not pencere_kapandi:
        adim_baslangic = time.time()
        bot.ilac_listesi_penceresini_kapat()
        log_sure("İlaç penceresi kapatma", adim_baslangic)

    # Ana Medula penceresine geri dön (main_window'u geri yükle)
    bot.main_window = ana_pencere
    time.sleep(bot.timing.get("genel_gecis"))

    # Geri Dön butonuna tıkla
    adim_baslangic = time.time()
    geri_don = bot.geri_don_butonuna_tikla()
    log_sure("Geri Dön butonu", adim_baslangic)
    if not geri_don:
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi)

    # SONRA butonuna tıklayarak bir sonraki reçeteye geç
    adim_baslangic = time.time()
    sonra = bot.sonra_butonuna_tikla()
    log_sure("Sonra butonu", adim_baslangic)
    if not sonra:
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi)

    # Toplam reçete süresi
    toplam_sure = time.time() - recete_baslangic
    if toplam_sure >= 60:
        dakika = int(toplam_sure // 60)
        saniye = int(toplam_sure % 60)
        logger.info(f"🕐 TOPLAM: {dakika}dk {saniye}s")
    else:
        logger.info(f"🕐 TOPLAM: {toplam_sure:.2f}s")

    return (True, medula_recete_no, takip_sayisi)


def console_pencereyi_ayarla():
    """Console penceresini sağ alt 1/5'e yerleştir ve buffer ayarla"""
    try:
        # Ekran çözünürlüğünü al
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)

        # Sağ alt 1/5 hesapla (alt 1/3 yükseklik, sağ 1/5 genişlik)
        console_width = int(screen_width * 1/5)
        console_height = int(screen_height * 1/3)
        console_x = int(screen_width * 4/5)  # Sol 4/5'ten sonra başla
        console_y = int(screen_height * 2/3)  # Üst 2/3'ten sonra başla

        # Console penceresini al
        kernel32 = ctypes.windll.kernel32
        console_hwnd = kernel32.GetConsoleWindow()

        if console_hwnd:
            # Console buffer boyutunu artır (daha fazla geçmiş tutmak için)
            try:
                # Buffer yüksekliğini 9999 satıra ayarla (scroll için)
                subprocess.run('mode con: lines=9999', shell=True, capture_output=True)
            except:
                pass

            # Pencereyi görünür yap (minimize ise restore et)
            win32gui.ShowWindow(console_hwnd, win32con.SW_RESTORE)
            time.sleep(0.09)  # Console için sabit

            # Önce SetWindowPos ile sağ tarafa taşı ve en üste getir
            flags = win32con.SWP_SHOWWINDOW
            win32gui.SetWindowPos(
                console_hwnd,
                win32con.HWND_TOP,
                console_x, console_y,
                console_width, console_height,
                flags
            )
            time.sleep(0.045)  # Console için sabit

            # Sonra MoveWindow ile kesin yerleştir
            win32gui.MoveWindow(console_hwnd, console_x, console_y, console_width, console_height, True)
            time.sleep(0.045)  # Console için sabit

            # Kontrol et - gerçekten yerleşti mi?
            rect = win32gui.GetWindowRect(console_hwnd)

            # Eğer hala sol taraftaysa (x < screen_width/2), hata ver
            if rect[0] < screen_width / 2:
                logger.error(f"❌ Console sağa gitmedi: x={rect[0]}")
            else:
                logger.info(f"✓ Console sağ alt 1/5'e yerleşti")
        else:
            logger.warning("❌ Console bulunamadı")

    except Exception as e:
        logger.error(f"Console ayarlanamadı: {e}", exc_info=True)


def main():
    """Ana fonksiyon - Reçete döngüsü"""
    program_baslangic = time.time()

    logger.info("=" * 40)
    logger.info("Botanik Bot Başlatılıyor...")
    logger.info("=" * 40)

    # Bot oluştur
    bot = BotanikBot()

    # Medulla'ya bağlan (ilk bağlantı - pencere yerleştirme ile)
    if not bot.baglanti_kur("MEDULA", ilk_baglanti=True):
        logger.error("❌ MEDULA bulunamadı")
        return

    # Medula yerleştirildikten SONRA console'u yerleştir
    console_pencereyi_ayarla()

    # Reçete döngüsü - SONRA butonu olduğu sürece devam et
    recete_sayisi = 0
    basarili_receteler = 0

    while True:
        recete_sayisi += 1
        logger.info("=" * 40)

        # Tek reçete işle
        basari, medula_no = tek_recete_isle(bot, recete_sayisi)
        logger.info("=" * 40)
        if not basari:
            # Reçete kaydı bulunamadı veya SONRA butonu bulunamadı - döngüden çık
            break
        else:
            basarili_receteler += 1

    toplam_sure = time.time() - program_baslangic
    ortalama_sure = toplam_sure / basarili_receteler if basarili_receteler > 0 else 0

    # Süre formatı
    if toplam_sure >= 60:
        t_dk = int(toplam_sure // 60)
        t_sn = int(toplam_sure % 60)
        toplam_str = f"{t_dk}dk {t_sn}s"
    else:
        toplam_str = f"{toplam_sure:.1f}s"

    if ortalama_sure >= 60:
        o_dk = int(ortalama_sure // 60)
        o_sn = int(ortalama_sure % 60)
        ortalama_str = f"{o_dk}dk {o_sn}s"
    else:
        ortalama_str = f"{ortalama_sure:.1f}s"

    logger.info("=" * 40)
    logger.info(f"✓ Tamamlandı: {basarili_receteler} reçete")
    logger.info(f"🕐 Toplam: {toplam_str}")
    logger.info(f"📊 Ortalama: {ortalama_str}/reçete")
    logger.info("=" * 40)


if __name__ == "__main__":
    main()
