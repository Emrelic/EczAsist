"""
Farmazon deposu sorgulama modülü
"""
import time
import re
import os
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .base_depo import BaseDepo
from .depo_config import DEPOLAR

logger = logging.getLogger(__name__)


class FarmazonDepo(BaseDepo):
    """Farmazon deposu sorgulama class'ı"""

    def __init__(self):
        config = DEPOLAR["farmazon"]
        super().__init__(config["name"], config["url"], config["elements"])

    def login(self, username, password):
        """Farmazon'a giriş yap"""
        try:
            self.switch_to_tab()

            logger.info(f"{self.name}: Giriş yapılıyor...")

            username_input = self.wait_for_element(By.NAME, self.elements["username_input"])
            if not username_input:
                logger.error(f"{self.name}: Kullanıcı adı alanı bulunamadı!")
                return False

            username_input.clear()
            username_input.send_keys(username)
            time.sleep(0.5)

            password_input = self.driver.find_element(By.NAME, self.elements["password_input"])
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(0.5)

            password_input.send_keys(Keys.ENTER)
            time.sleep(3)

            try:
                self.driver.execute_script("""
                    var savePasswordButton = document.querySelector('button[aria-label*="Hiçbir zaman"]');
                    if (savePasswordButton) savePasswordButton.click();
                """)
            except:
                pass

            current_url = self.driver.current_url
            if "login" in current_url.lower():
                logger.warning(f"{self.name}: Giriş başarısız - hala login sayfasında!")
                return False

            # "Satış Bilgileriniz Eksik!" modalını kapat
            try:
                time.sleep(1)
                self.driver.execute_script("""
                    var closeBtn = document.querySelector('button.close-btn[data-cy="modal-close"]');
                    if (closeBtn) closeBtn.click();
                    var overlay = document.querySelector('.modal-overlay');
                    if (overlay) overlay.click();
                """)
            except Exception:
                pass

            logger.info(f"{self.name}: Giriş başarılı!")
            return True

        except Exception as e:
            logger.error(f"{self.name}: Giriş hatası: {e}")
            return False

    def search_barcode(self, barcode):
        """Farmazon'da barkod ara"""
        try:
            self.switch_to_tab()

            logger.info(f"{self.name}: Barkod aranıyor: {barcode}")

            search_selectors = [
                (By.NAME, "q"),
                (By.CSS_SELECTOR, "input[data-testid='header-search-input']"),
                (By.CSS_SELECTOR, "input[placeholder*='Ürün adı, barkod']"),
            ]

            search_input = None
            for selector_type, selector_value in search_selectors:
                try:
                    search_input = self.wait_for_element(selector_type, selector_value, timeout=5)
                    if search_input:
                        break
                except:
                    continue

            if not search_input:
                logger.warning(f"{self.name}: Arama kutusu bulunamadı!")
                return False

            search_input.clear()
            search_input.send_keys(barcode)
            time.sleep(1)

            # "Ara" butonuna tıkla
            try:
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC

                ara_button_selectors = [
                    (By.CSS_SELECTOR, "button[data-testid='header-search-submit-btn']"),
                    (By.XPATH, "//button[contains(text(), 'Ara')]"),
                    (By.CSS_SELECTOR, "button[type='submit']"),
                ]

                ara_button = None
                for selector_type, selector_value in ara_button_selectors:
                    try:
                        ara_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((selector_type, selector_value))
                        )
                        if ara_button:
                            break
                    except:
                        continue

                if ara_button:
                    self.driver.execute_script("arguments[0].click();", ara_button)
                    time.sleep(2.5)
                else:
                    search_input.send_keys(Keys.ENTER)
                    time.sleep(2)

            except Exception:
                search_input.send_keys(Keys.ENTER)
                time.sleep(2)

            return True
        except Exception as e:
            logger.error(f"{self.name}: Barkod arama hatası: {e}")
            return False

    def _get_psf_price(self):
        """Sayfadan PSF değerini oku"""
        try:
            page_source = self.driver.page_source
            psf_match = re.search(r'PSF[:\s]*(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\s*TL', page_source)
            if psf_match:
                psf_price = float(psf_match.group(1).replace(".", "") + "." + psf_match.group(2))
                return psf_price
            return None
        except Exception:
            return None

    def _get_price_with_long_expiry(self):
        """Detay sayfasına gidip 8 aydan uzun miatlı en ucuz fiyatı al"""
        try:
            self.switch_to_tab()

            # Ürün detay sayfasına tıkla
            product_selectors = [
                "a[href*='/productlistings/']",
                ".product-card a",
                "div.price",
            ]

            clicked = False
            for selector in product_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        for elem in elements:
                            try:
                                elem.click()
                                clicked = True
                                break
                            except:
                                continue
                    if clicked:
                        break
                except:
                    continue

            if not clicked:
                return self.get_cheapest_price_from_results(), self._get_psf_price()

            time.sleep(2)

            # "8 Aydan Uzun Miat" filtresini seç
            filter_selectors = [
                "//button[contains(text(), '8 Aydan Uzun')]",
                "//span[contains(text(), '8 Aydan Uzun')]/..",
                "//div[contains(text(), '8 Aydan Uzun')]",
            ]

            for selector in filter_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        for elem in elements:
                            try:
                                if elem.is_displayed():
                                    elem.click()
                                    time.sleep(1)
                                    break
                            except:
                                continue
                        break
                except:
                    continue

            time.sleep(1)

            prices = []

            # Satıcı fiyatlarını oku
            price_selectors = [
                "div.price-area span",
                ".listing-price",
                ".seller-price",
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
                                if 1 <= price <= 50000:
                                    prices.append(price)
                    if prices:
                        break
                except:
                    continue

            # Regex ile sayfadan fiyatları çek
            if not prices:
                page_source = self.driver.page_source
                psf_match = re.search(r'PSF[:\s]*(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\s*TL', page_source)
                psf_price = None
                if psf_match:
                    psf_price = float(psf_match.group(1).replace(".", "") + "." + psf_match.group(2))

                price_pattern = r'(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\s*TL'
                matches = re.findall(price_pattern, page_source)

                for match in matches:
                    try:
                        price_str = match[0].replace(".", "") + "." + match[1]
                        price = float(price_str)
                        if psf_price and abs(price - psf_price) < 0.01:
                            continue
                        if 1 <= price <= 50000:
                            prices.append(price)
                    except:
                        continue

            psf_price = self._get_psf_price()

            if prices:
                min_price = min(prices)
                return min_price, psf_price

            return None, psf_price

        except Exception as e:
            logger.error(f"{self.name}: Uzun miat fiyat okuma hatası: {e}")
            return None, None

    def get_cheapest_price_from_results(self):
        """Arama sonuçları sayfasından en ucuz fiyatı al"""
        try:
            self.switch_to_tab()
            time.sleep(2)

            prices = []

            price_selectors = [
                "div.price",
                ".text-price",
                ".productitem .price",
                "[class*='price']",
            ]

            for selector in price_selectors:
                try:
                    price_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if price_elements:
                        for elem in price_elements:
                            try:
                                text = elem.text.strip()
                                if not text:
                                    continue

                                price_match = re.search(r'(\d+),(\d+)\s*TL', text)
                                if price_match:
                                    price = float(f"{price_match.group(1)}.{price_match.group(2)}")
                                    if 1 <= price <= 100000:
                                        prices.append(price)
                            except Exception:
                                continue

                        if prices:
                            break
                except:
                    continue

            if prices:
                return min(prices)
            return None

        except Exception as e:
            logger.error(f"{self.name}: Fiyat okuma hatası: {e}")
            return None

    def _check_pahali(self, fiyat, psf):
        """Fiyatın PSF'ye göre pahalı olup olmadığını kontrol et"""
        if not fiyat or not psf:
            return False

        try:
            esik = float(os.getenv("FARMAZON_PAHALI_ESIK", "10"))
            esik_carpan = 1 + (esik / 100)

            pahali = (fiyat * esik_carpan) > psf

            if pahali:
                logger.warning(f"{self.name}: PAHALI! Fiyat: {fiyat} TL x {esik_carpan} = {fiyat * esik_carpan:.2f} TL > PSF: {psf} TL")

            return pahali
        except Exception:
            return False

    def check_stock_status(self):
        """Farmazon'da stok durumunu kontrol et"""
        try:
            self.switch_to_tab()

            satis_kosullari = self.get_satis_kosullari()
            sart = None

            page_source = self.driver.page_source

            # "'den başlayan" metni var mı?
            if "'den başlayan" in page_source or "den başlayan" in page_source:
                logger.info(f"{self.name}: Ürünler listelendi, stokta VAR")

                uzun_miat_enabled = os.getenv("FARMAZON_UZUN_MIAT", "true").lower() == "true"

                final_price = None
                psf_price = None

                if uzun_miat_enabled:
                    final_price, psf_price = self._get_price_with_long_expiry()
                else:
                    final_price = self.get_cheapest_price_from_results()
                    psf_price = self._get_psf_price()

                if final_price:
                    pahali = self._check_pahali(final_price, psf_price)

                    if pahali:
                        return {
                            "stok_var": False,
                            "mesaj": "Pahalı",
                            "detay": f"Fiyat: {final_price} TL > PSF: {psf_price} TL",
                            "fiyat": final_price,
                            "psf": psf_price,
                            "sart": sart,
                            "satis_kosullari": satis_kosullari,
                            "pahali": True
                        }

                    satis_kosullari = [{
                        "sart": "1",
                        "birim_fiyat": final_price,
                        "fiyat": final_price,
                        "min_adet": 1,
                        "mf": 0,
                        "kampanya": "En ucuz satıcı (8+ ay miat)" if uzun_miat_enabled else "En ucuz satıcı"
                    }]
                    return {
                        "stok_var": True,
                        "mesaj": "Stokta Var",
                        "detay": f"En ucuz: {final_price} TL",
                        "fiyat": final_price,
                        "psf": psf_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari,
                        "pahali": False
                    }
                else:
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
                "ürün bulunamadı", "sonuç bulunamadı",
                "arama sonucu bulunamadı", "ürün yok"
            ]

            page_text_lower = page_source.lower()
            for indicator in no_result_indicators:
                if indicator in page_text_lower:
                    return {
                        "stok_var": False,
                        "mesaj": "Yok",
                        "detay": f"'{indicator}' metni bulundu",
                        "fiyat": None,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari,
                        "pahali": False
                    }

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
        """Farmazon'dan ürün adını al"""
        try:
            self.switch_to_tab()

            name_selectors = [
                "div.name",
                '[data-testid="highlighted-name"]',
                ".product-name",
            ]

            for selector in name_selectors:
                try:
                    name_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if name_element:
                        product_name = name_element.text.strip()
                        if product_name:
                            return product_name
                except:
                    continue

            # img alt attribute'undan al
            try:
                img_element = self.driver.find_element(
                    By.CSS_SELECTOR, 'img[alt][src*="farmazon"]')
                if img_element:
                    alt_text = img_element.get_attribute("alt")
                    if alt_text and alt_text.strip():
                        return alt_text.strip()
            except:
                pass

            return None
        except Exception as e:
            logger.error(f"{self.name}: Ürün adı alma hatası: {e}")
            return None

    def get_satis_kosullari(self):
        """Farmazon'dan satış koşulları (MF yok)"""
        return []

    def get_en_iyi_mf(self):
        """Farmazon'da MF yok"""
        return None
