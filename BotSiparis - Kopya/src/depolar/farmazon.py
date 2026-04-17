"""
Farmazon deposu sorgulama modülü
"""
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .base_depo import BaseDepo
from ..utils import logger, DEPOLAR


class FarmazonDepo(BaseDepo):
    """Farmazon deposu sorgulama class'ı"""

    def __init__(self):
        config = DEPOLAR["farmazon"]
        super().__init__(config["name"], config["url"], config["elements"])

    def login(self, username, password):
        """Farmazon'a giriş yap

        Args:
            username: Kullanıcı adı / E-posta / GLN
            password: Şifre

        Returns:
            bool: Giriş başarılı mı
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Giriş yapılıyor...")

            # Kullanıcı adı
            username_input = self.wait_for_element(By.NAME, self.elements["username_input"])
            if not username_input:
                logger.error(f"{self.name}: Kullanıcı adı alanı bulunamadı!")
                return False

            username_input.clear()
            username_input.send_keys(username)
            time.sleep(0.5)

            # Şifre
            password_input = self.driver.find_element(By.NAME, self.elements["password_input"])
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(0.5)

            # Giriş butonuna tıkla (Enter tuşu ile)
            password_input.send_keys(Keys.ENTER)

            # Giriş kontrolü - yönlendirme olana kadar bekle
            time.sleep(3)

            # Şifre kaydetme popup'ını kapat (eğer açıldıysa)
            try:
                self.driver.execute_script("""
                    // Chrome'un şifre kaydetme popup'ını kapat
                    var savePasswordButton = document.querySelector('button[aria-label*="Hiçbir zaman"]');
                    if (savePasswordButton) savePasswordButton.click();
                """)
            except:
                pass

            # Login başarılı mı kontrol et
            # Eğer hala login sayfasındaysak başarısız demektir
            current_url = self.driver.current_url
            if "login" in current_url.lower():
                logger.warning(f"{self.name}: Giriş başarısız - hala login sayfasında!")
                return False

            # "Satış Bilgileriniz Eksik!" (KEP Adresi) modalını kapat
            try:
                time.sleep(1)  # Modal'ın açılması için bekle
                self.driver.execute_script("""
                    // KEP adresi modalını kapat
                    var closeBtn = document.querySelector('button.close-btn[data-cy="modal-close"]');
                    if (closeBtn) {
                        closeBtn.click();
                        console.log('KEP modal kapatıldı');
                    }
                    // Alternatif: Modal overlay'e tıkla
                    var overlay = document.querySelector('.modal-overlay');
                    if (overlay) overlay.click();
                """)
                logger.debug(f"{self.name}: KEP modalı kapatıldı (varsa)")
            except Exception as e:
                logger.debug(f"{self.name}: KEP modal kapatma: {e}")

            logger.info(f"{self.name}: Giriş başarılı!")
            return True

        except Exception as e:
            logger.error(f"{self.name}: Giriş hatası: {e}")
            return False

    def search_barcode(self, barcode):
        """Farmazon'da barkod ara

        Args:
            barcode: Aranacak barkod

        Returns:
            bool: Arama başarılı mı
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Barkod aranıyor: {barcode}")

            # Farmazon'da arama kutusunu bul
            # Ana sayfada: input[name="q"] veya input[data-testid="header-search-input"]
            search_selectors = [
                (By.NAME, "q"),  # En güvenilir
                (By.CSS_SELECTOR, "input[data-testid='header-search-input']"),
                (By.CSS_SELECTOR, "input[placeholder*='Ürün adı, barkod']"),
            ]

            search_input = None
            for selector_type, selector_value in search_selectors:
                try:
                    search_input = self.wait_for_element(selector_type, selector_value, timeout=5)
                    if search_input:
                        logger.debug(f"{self.name}: Arama kutusu bulundu: {selector_value}")
                        break
                except:
                    continue

            if not search_input:
                logger.warning(f"{self.name}: Arama kutusu bulunamadı!")
                return False

            # Arama kutusunu temizle ve barkodu yaz
            search_input.clear()
            search_input.send_keys(barcode)
            time.sleep(1)  # Butonun aktif olması için bekle (0.5'ten 1'e çıkardık)

            # "Ara" butonuna tıkla (Enter yerine)
            try:
                # Ara butonu: turuncu submit butonu
                ara_button_selectors = [
                    (By.CSS_SELECTOR, "button[data-testid='header-search-submit-btn']"),
                    (By.XPATH, "//button[contains(text(), 'Ara')]"),
                    (By.CSS_SELECTOR, ".header-search-submit"),
                    (By.CSS_SELECTOR, "button[type='submit']"),
                ]

                ara_button = None
                for selector_type, selector_value in ara_button_selectors:
                    try:
                        # Butonun hem var olmasını hem de clickable olmasını bekle
                        from selenium.webdriver.support.ui import WebDriverWait
                        from selenium.webdriver.support import expected_conditions as EC

                        ara_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((selector_type, selector_value))
                        )
                        if ara_button:
                            logger.debug(f"{self.name}: Ara butonu bulundu ve aktif: {selector_value}")
                            break
                    except:
                        continue

                if ara_button:
                    # JavaScript ile tıkla (daha güvenilir)
                    self.driver.execute_script("arguments[0].click();", ara_button)
                    logger.info(f"{self.name}: ✓ 'Ara' butonuna tıklandı (JavaScript)")
                    time.sleep(2.5)  # Sonuçların yüklenmesi için bekle
                    logger.info(f"{self.name}: ✓ Arama sonuçları bekleniyor...")
                else:
                    # Fallback: Enter tuşu
                    logger.warning(f"{self.name}: Ara butonu bulunamadı, Enter kullanılıyor")
                    search_input.send_keys(Keys.ENTER)
                    time.sleep(2)

            except Exception as e:
                logger.warning(f"{self.name}: Ara butonuna tıklama hatası: {e}, Enter kullanılıyor")
                search_input.send_keys(Keys.ENTER)
                time.sleep(2)

            return True
        except Exception as e:
            logger.error(f"{self.name}: Barkod arama hatası: {e}")
            return False

    def find_cheapest_product_and_click(self):
        """Arama sonuçlarında en ucuz ürünü bulup tıkla

        Returns:
            bool: Başarılı ise True
        """
        try:
            self.switch_to_tab()
            time.sleep(1.5)  # Sonuçların yüklenmesini bekle

            import re

            # Ürün kartlarını ve fiyatlarını bul
            # Ürün kartları genellikle bir link veya div içinde
            try:
                # Tüm fiyatları içeren elementleri bul
                price_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'TL')]")

                product_cards = []

                for elem in price_elements:
                    text = elem.text.strip()
                    # Fiyat formatı: "899,78 TL" veya "695,00 TL"
                    price_match = re.search(r'(\d+),(\d+)\s*TL', text)

                    if price_match:
                        price = float(f"{price_match.group(1)}.{price_match.group(2)}")

                        # Bu elementin ait olduğu ürün kartını bul (parent veya ancestor)
                        try:
                            # Fiyatın üstündeki tıklanabilir elementi bul
                            parent = elem
                            for _ in range(5):  # 5 seviye yukarı çık
                                parent = parent.find_element(By.XPATH, "..")
                                # Tıklanabilir bir element mi?
                                tag_name = parent.tag_name.lower()
                                if tag_name in ['a', 'button'] or parent.get_attribute('onclick'):
                                    product_cards.append({
                                        'price': price,
                                        'element': parent
                                    })
                                    logger.debug(f"{self.name}: Ürün bulundu: {price} TL")
                                    break
                        except:
                            continue

                if not product_cards:
                    logger.warning(f"{self.name}: Ürün kartları bulunamadı")
                    return False

                # Fiyata göre sırala (ucuzdan pahalıya)
                product_cards.sort(key=lambda x: x['price'])

                # En ucuz ürün
                cheapest = product_cards[0]
                logger.info(f"{self.name}: En ucuz ürün: {cheapest['price']} TL")

                # En ucuz ürüne tıkla
                cheapest['element'].click()
                logger.info(f"{self.name}: ✓ En ucuz ürüne tıklandı: {cheapest['price']} TL")
                time.sleep(2)  # Sayfa yüklensin
                return True

            except Exception as e:
                logger.warning(f"{self.name}: Ürün kartları bulma hatası: {e}")
                return False

        except Exception as e:
            logger.error(f"{self.name}: En ucuz ürün bulma hatası: {e}")
            return False

    def apply_filters(self):
        """Filtreleri uygula: 9.4+ Puan ve 8 Aydan Uzun Miad

        Returns:
            bool: En az bir filtre uygulandıysa True
        """
        try:
            self.switch_to_tab()
            time.sleep(1)

            filters_applied = False

            # "9.4'ten Yüksek Puanlılar" checkbox'ını bul ve işaretle
            try:
                high_rating_checkbox = self.driver.find_element(By.XPATH, "//label[contains(text(), '9.4')]")
                if high_rating_checkbox:
                    high_rating_checkbox.click()
                    logger.info(f"{self.name}: ✓ Yüksek puan filtresi uygulandı")
                    filters_applied = True
                    time.sleep(1.5)  # Filtrenin uygulanmasını bekle
            except:
                logger.debug(f"{self.name}: Yüksek puan filtresi bulunamadı")

            # "Miadı 8 Aydan Uzunlar" checkbox'ını bul ve işaretle
            try:
                long_expiry_checkbox = self.driver.find_element(By.XPATH, "//label[contains(text(), '8 Aydan')]")
                if long_expiry_checkbox:
                    long_expiry_checkbox.click()
                    logger.info(f"{self.name}: ✓ 8 aydan uzun miad filtresi uygulandı")
                    filters_applied = True
                    time.sleep(1.5)  # Filtrenin uygulanmasını bekle
            except:
                logger.debug(f"{self.name}: 8 aydan uzun miad filtresi bulunamadı")

            if not filters_applied:
                logger.info(f"{self.name}: Hiçbir filtre bulunamadı, filtresiz devam ediliyor")

            return filters_applied

        except Exception as e:
            logger.warning(f"{self.name}: Filtre uygulama hatası: {e}")
            return False

    def get_cheapest_price(self):
        """Filtrelenmiş sonuçlarda en ucuz fiyatı al

        Returns:
            float or None: En ucuz fiyat (TL)
        """
        try:
            self.switch_to_tab()
            time.sleep(1)

            import re
            page_source = self.driver.page_source

            # Fiyat regex: "XX,XX TL" formatı
            price_pattern = r'(\d+),(\d+)\s*TL'
            matches = re.findall(price_pattern, page_source)

            if not matches:
                return None

            # Fiyatları float'a çevir
            prices = []
            for match in matches:
                try:
                    price = float(f"{match[0]}.{match[1]}")
                    prices.append(price)
                except:
                    continue

            if prices:
                min_price = min(prices)
                logger.info(f"{self.name}: Filtrelenmiş en ucuz fiyat: {min_price} TL")
                return min_price

            return None

        except Exception as e:
            logger.error(f"{self.name}: Fiyat okuma hatası: {e}")
            return None

    def _get_psf_price(self):
        """Sayfadan PSF (Perakende Satış Fiyatı) değerini oku

        Returns:
            float or None: PSF fiyatı (TL)
        """
        try:
            page_source = self.driver.page_source

            # PSF formatı: "PSF: 1.213,90 TL" veya "PSF: 1213,90 TL"
            psf_match = re.search(r'PSF[:\s]*(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\s*TL', page_source)
            if psf_match:
                psf_price = float(psf_match.group(1).replace(".", "") + "." + psf_match.group(2))
                logger.debug(f"{self.name}: PSF fiyatı: {psf_price} TL")
                return psf_price

            return None
        except Exception as e:
            logger.debug(f"{self.name}: PSF okuma hatası: {e}")
            return None

    def _get_price_with_long_expiry(self):
        """Detay sayfasına gidip 8 aydan uzun miatlı en ucuz fiyatı al

        Returns:
            tuple: (float or None, float or None) - (en ucuz fiyat, PSF fiyatı)
        """
        try:
            self.switch_to_tab()
            import re

            # 1. Arama sonuçlarından ilk ürüne tıkla (detay sayfasına git)
            # Farmazon'da ürün kartına veya fiyata tıklanabilir
            product_selectors = [
                "a[href*='/productlistings/']",  # Ürün detay linki
                ".product-card a",               # Ürün kartı linki
                "div.price",                     # Fiyat elementi (tıklanabilir)
            ]

            clicked = False
            for selector in product_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        # İlk tıklanabilir elementi bul
                        for elem in elements:
                            try:
                                elem.click()
                                clicked = True
                                logger.info(f"{self.name}: Ürün detay sayfasına tıklandı ({selector})")
                                break
                            except:
                                continue
                    if clicked:
                        break
                except:
                    continue

            if not clicked:
                logger.warning(f"{self.name}: Ürün detay sayfasına tıklanamadı, arama sonuçlarından fiyat alınıyor")
                return self.get_cheapest_price_from_results()

            # Detay sayfasının yüklenmesini bekle
            time.sleep(2)

            # 2. "8 Aydan Uzun Miat" filtresini seç
            # Screenshot'ta görünen buton: "8 Aydan Uzun Miat 18"
            filter_selectors = [
                "//button[contains(text(), '8 Aydan Uzun')]",
                "//span[contains(text(), '8 Aydan Uzun')]/..",
                "//div[contains(text(), '8 Aydan Uzun')]",
                "[data-filter*='expiry']",
                "button:contains('8 Aydan')",
            ]

            filter_clicked = False
            for selector in filter_selectors:
                try:
                    if selector.startswith("//"):
                        # XPath
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        # CSS
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    if elements:
                        for elem in elements:
                            try:
                                # Element görünür mü kontrol et
                                if elem.is_displayed():
                                    elem.click()
                                    filter_clicked = True
                                    logger.info(f"{self.name}: '8 Aydan Uzun Miat' filtresi seçildi")
                                    time.sleep(1)  # Filtrenin uygulanmasını bekle
                                    break
                            except:
                                continue
                    if filter_clicked:
                        break
                except:
                    continue

            if not filter_clicked:
                logger.warning(f"{self.name}: '8 Aydan Uzun Miat' filtresi bulunamadı, tüm ilanlardan fiyat alınıyor")

            # 3. Filtrelenmiş listeden en ucuz fiyatı oku
            # Satıcı listesindeki fiyatları oku (PSF fiyatını hariç tut)
            time.sleep(1)

            prices = []

            # Yöntem 1: Satıcı kartlarındaki fiyatları oku
            # Her satıcı kartında fiyat var: "295,00 TL", "295,57 TL" gibi
            try:
                # Satıcı fiyat elementlerini bul - sağ taraftaki liste
                price_selectors = [
                    "div.price-area span",      # Fiyat alanı
                    ".listing-price",           # Liste fiyatı
                    ".seller-price",            # Satıcı fiyatı
                    "[class*='price']:not(.psf) span",  # PSF olmayan fiyatlar
                ]

                for selector in price_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            text = elem.text.strip()
                            if text and "TL" in text:
                                price_match = re.search(r'(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})', text)
                                if price_match:
                                    price_str = price_match.group(1).replace(".", "") + "." + price_match.group(2)
                                    price = float(price_str)
                                    if 1 <= price <= 50000:  # Makul aralık (PSF genelde yüksek)
                                        prices.append(price)
                                        logger.debug(f"{self.name}: Satıcı fiyatı: {price} TL")
                        if prices:
                            break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"{self.name}: Selector ile fiyat okuma hatası: {e}")

            # Yöntem 2: Regex ile sayfadan fiyatları çek (PSF hariç)
            if not prices:
                page_source = self.driver.page_source

                # PSF fiyatını bul ve hariç tut
                psf_match = re.search(r'PSF[:\s]*(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\s*TL', page_source)
                psf_price = None
                if psf_match:
                    psf_price = float(psf_match.group(1).replace(".", "") + "." + psf_match.group(2))
                    logger.debug(f"{self.name}: PSF fiyatı (hariç tutulacak): {psf_price} TL")

                # Tüm fiyatları bul
                price_pattern = r'(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\s*TL'
                matches = re.findall(price_pattern, page_source)

                for match in matches:
                    try:
                        price_str = match[0].replace(".", "") + "." + match[1]
                        price = float(price_str)
                        # PSF fiyatını ve çok yüksek/düşük fiyatları hariç tut
                        if psf_price and abs(price - psf_price) < 0.01:
                            continue  # PSF fiyatı, atla
                        if 1 <= price <= 50000:
                            prices.append(price)
                    except:
                        continue

            # PSF fiyatını al (pahalılık kontrolü için)
            psf_price = self._get_psf_price()

            if prices:
                min_price = min(prices)
                logger.info(f"{self.name}: Detay sayfasından {len(prices)} satıcı fiyatı bulundu, en ucuz (8+ ay miat): {min_price} TL, PSF: {psf_price} TL")
                return min_price, psf_price

            logger.warning(f"{self.name}: Detay sayfasında satıcı fiyatı bulunamadı")
            return None, psf_price

        except Exception as e:
            logger.error(f"{self.name}: Uzun miat fiyat okuma hatası: {e}")
            return None, None

    def get_cheapest_price_from_results(self):
        """Arama sonuçları sayfasından en ucuz fiyatı al (tıklamadan)

        Returns:
            float or None: En ucuz fiyat (TL)
        """
        try:
            self.switch_to_tab()
            time.sleep(2)  # Sayfanın tam yüklenmesi için bekle

            import re
            prices = []

            # Farklı selector'ları dene (Farmazon sayfası değişebilir)
            price_selectors = [
                "div.price",            # Login sonrası format
                ".text-price",          # Genel arama formatı
                ".productitem .price",  # Eski format
                "[class*='price']",     # Genel price class'ı
            ]

            for selector in price_selectors:
                try:
                    price_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if price_elements:
                        logger.debug(f"{self.name}: {len(price_elements)} adet '{selector}' elementi bulundu")

                        for elem in price_elements:
                            try:
                                text = elem.text.strip()
                                if not text:
                                    continue

                                # "194,00 TL'den başlayan" veya "80,00 TL" formatı
                                price_match = re.search(r'(\d+),(\d+)\s*TL', text)

                                if price_match:
                                    price = float(f"{price_match.group(1)}.{price_match.group(2)}")
                                    # Makul fiyat aralığında mı kontrol et
                                    if 1 <= price <= 100000:
                                        prices.append(price)
                                        logger.debug(f"{self.name}: Fiyat bulundu: {price} TL")
                            except Exception as e:
                                logger.debug(f"{self.name}: Element okuma hatası: {e}")
                                continue

                        if prices:
                            break  # Fiyat bulundu, diğer selector'ları deneme
                except:
                    continue

            if prices:
                min_price = min(prices)
                logger.info(f"{self.name}: Toplam {len(prices)} fiyat bulundu, en ucuz: {min_price} TL")
                return min_price
            else:
                logger.warning(f"{self.name}: Hiç fiyat bulunamadı")
                return None

        except Exception as e:
            logger.error(f"{self.name}: Fiyat okuma hatası: {e}")
            return None

    def _check_pahali(self, fiyat, psf):
        """Fiyatın PSF'ye göre pahalı olup olmadığını kontrol et

        Formül: fiyat × (1 + eşik/100) > PSF ise PAHALI

        Args:
            fiyat: Farmazon fiyatı
            psf: PSF (Perakende Satış Fiyatı)

        Returns:
            bool: Pahalı ise True
        """
        import os
        if not fiyat or not psf:
            return False

        try:
            esik = float(os.getenv("FARMAZON_PAHALI_ESIK", "10"))
            esik_carpan = 1 + (esik / 100)

            # fiyat × (1 + eşik) > PSF ise pahalı
            pahali = (fiyat * esik_carpan) > psf

            if pahali:
                logger.warning(f"{self.name}: PAHALI! Fiyat: {fiyat} TL × {esik_carpan} = {fiyat * esik_carpan:.2f} TL > PSF: {psf} TL")
            else:
                logger.debug(f"{self.name}: Fiyat uygun. Fiyat: {fiyat} TL × {esik_carpan} = {fiyat * esik_carpan:.2f} TL <= PSF: {psf} TL")

            return pahali
        except Exception as e:
            logger.error(f"{self.name}: Pahalılık kontrolü hatası: {e}")
            return False

    def check_stock_status(self):
        """Farmazon'da stok durumunu kontrol et ve en ucuz fiyatı bul

        NOT: Farmazon online marketplace olduğu için MF sistemi yoktur.
        Sadece satıcılardan gelen fiyatlar listelenir.

        Returns:
            dict: {"stok_var": bool, "mesaj": str, "detay": str, "fiyat": float, "sart": None, "satis_kosullari": [], "pahali": bool}
        """
        try:
            import os
            # Önce doğru tab'a geç
            self.switch_to_tab()

            # Farmazon'da MF yok, satis_kosullari boş
            satis_kosullari = self.get_satis_kosullari()
            sart = None

            page_source = self.driver.page_source

            # "'den başlayan" metni var mı?
            if "'den başlayan" in page_source or "den başlayan" in page_source:
                logger.info(f"{self.name}: Ürünler listelendi, stokta VAR")

                # Uzun miat ayarı açık mı?
                uzun_miat_enabled = os.getenv("FARMAZON_UZUN_MIAT", "true").lower() == "true"

                final_price = None
                psf_price = None

                if uzun_miat_enabled:
                    # Detay sayfasına git ve 8 aydan uzun miatlı fiyatı al (PSF ile birlikte)
                    final_price, psf_price = self._get_price_with_long_expiry()
                else:
                    # Direkt en ucuz fiyatı al (filtre yok)
                    final_price = self.get_cheapest_price_from_results()
                    # PSF'yi ayrıca al
                    psf_price = self._get_psf_price()

                if final_price:
                    # Pahalılık kontrolü yap
                    pahali = self._check_pahali(final_price, psf_price)

                    if pahali:
                        logger.warning(f"{self.name}: ⚠ PAHALI - Fiyat: {final_price} TL, PSF: {psf_price} TL")
                        return {
                            "stok_var": False,  # Pahalı = yok hükmünde
                            "mesaj": "Pahalı",
                            "detay": f"Fiyat: {final_price} TL > PSF: {psf_price} TL (eşik aşıldı)",
                            "fiyat": final_price,
                            "psf": psf_price,
                            "sart": sart,
                            "satis_kosullari": satis_kosullari,
                            "pahali": True
                        }

                    logger.info(f"{self.name}: ✓ En ucuz fiyat: {final_price} TL")
                    # Normal fiyatı satis_kosullari'na ekle
                    satis_kosullari = [{
                        "sart": "1",
                        "birim_fiyat": final_price,  # birim_fiyat olmalı (GUI için)
                        "fiyat": final_price,
                        "min_adet": 1,
                        "mf": 0,
                        "kampanya": "En ucuz satıcı (8+ ay miat)" if uzun_miat_enabled else "En ucuz satıcı"
                    }]
                    return {
                        "stok_var": True,
                        "mesaj": "Stokta Var",  # Fiyat değil, durum mesajı
                        "detay": f"En ucuz: {final_price} TL",
                        "fiyat": final_price,
                        "psf": psf_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari,
                        "pahali": False
                    }
                else:
                    logger.warning(f"{self.name}: Fiyat okunamadı")
                    return {
                        "stok_var": True,
                        "mesaj": "Var",
                        "detay": "Fiyat okunamadı",
                        "fiyat": None,
                        "psf": psf_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari,
                        "pahali": False
                    }

            # "Ürün bulunamadı" kontrolü
            no_result_indicators = [
                "ürün bulunamadı",
                "sonuç bulunamadı",
                "arama sonucu bulunamadı",
                "ürün yok"
            ]

            page_text_lower = page_source.lower()
            for indicator in no_result_indicators:
                if indicator in page_text_lower:
                    logger.info(f"{self.name}: '{indicator}' metni bulundu, stokta YOK")
                    return {
                        "stok_var": False,
                        "mesaj": "Yok",
                        "detay": f"'{indicator}' metni bulundu",
                        "fiyat": None,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari,
                        "pahali": False
                    }

            # Belirsiz durum
            logger.warning(f"{self.name}: Stok durumu belirsiz")
            return {
                "stok_var": False,
                "mesaj": "Belirsiz",
                "detay": "Ürün listesi tespit edilemedi",
                "fiyat": None,
                "sart": sart,
                "satis_kosullari": satis_kosullari,
                "pahali": False
            }

        except Exception as e:
            logger.error(f"{self.name}: Stok kontrol hatası: {e}")
            return {
                "stok_var": False,
                "mesaj": "Hata",
                "detay": str(e),
                "fiyat": None,
                "sart": None,
                "satis_kosullari": [],
                "pahali": False
            }

    def get_product_name(self):
        """Farmazon'dan ürün adını al

        Returns:
            str: Ürün adı veya None
        """
        try:
            self.switch_to_tab()

            # Farklı selector'ları dene (Farmazon sayfası değişebilir)
            name_selectors = [
                "div.name",                          # Login sonrası format
                '[data-testid="highlighted-name"]',  # Genel arama format
                ".product-name",                     # Alternatif
            ]

            for selector in name_selectors:
                try:
                    name_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if name_element:
                        product_name = name_element.text.strip()
                        if product_name:
                            logger.info(f"{self.name}: Ürün adı bulundu ({selector}): {product_name}")
                            return product_name
                except:
                    continue

            # Alternatif: img alt attribute'undan al
            try:
                img_element = self.driver.find_element(
                    By.CSS_SELECTOR, 'img[alt][src*="farmazon"]'
                )
                if img_element:
                    alt_text = img_element.get_attribute("alt")
                    if alt_text and alt_text.strip():
                        logger.info(f"{self.name}: Ürün adı bulundu (img alt): {alt_text.strip()}")
                        return alt_text.strip()
            except:
                pass

            # 3. Son çare: Sayfa başlığından al
            try:
                title = self.driver.title
                if title:
                    # "Ürün Adı | Farmazon" formatında olabilir
                    if "|" in title:
                        product_name = title.split("|")[0].strip()
                    elif "-" in title:
                        product_name = title.split("-")[0].strip()
                    else:
                        product_name = title.strip()

                    # "Farmazon" veya boş değilse kullan
                    if product_name and product_name.lower() != "farmazon":
                        logger.info(f"{self.name}: Ürün adı bulundu (title): {product_name}")
                        return product_name
            except:
                pass

            return None
        except Exception as e:
            logger.error(f"{self.name}: Ürün adı alma hatası: {e}")
            return None

    def get_satis_kosullari(self):
        """Farmazon'dan satış koşulları

        NOT: Farmazon online marketplace olduğu için MF sistemi yoktur.
        Bu metod her zaman boş liste döndürür.

        Returns:
            list: Boş liste (Farmazon'da MF yok)
        """
        # Farmazon'da mal fazlası sistemi yok
        # Sadece farklı satıcılardan gelen fiyatlar var
        return []

    def get_en_iyi_mf(self):
        """En iyi mal fazlası koşulunu döndür

        NOT: Farmazon'da MF sistemi yok, her zaman None döner.

        Returns:
            None
        """
        return None
