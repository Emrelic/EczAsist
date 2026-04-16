"""
İstanbul Ecza Koop deposu sorgulama modülü
"""
import time
import re
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .base_depo import BaseDepo
from .depo_config import DEPOLAR

logger = logging.getLogger(__name__)


class IskoopDepo(BaseDepo):
    """İstanbul Ecza Koop deposu sorgulama class'ı"""

    def __init__(self):
        config = DEPOLAR["iskoop"]
        super().__init__(config["name"], config["url"], config["elements"])

    def login(self, username, password):
        """İstanbul Ecza Koop'a giriş yap"""
        try:
            self.switch_to_tab()

            logger.info(f"{self.name}: Giriş yapılıyor...")

            username_input = self.wait_for_element(By.ID, "logonuidfield")
            if not username_input:
                logger.error(f"{self.name}: Kullanıcı adı alanı bulunamadı!")
                return False

            username_input.click()
            time.sleep(0.3)

            username_input.clear()
            username_input.send_keys(username)
            time.sleep(0.5)

            password_input = self.driver.find_element(By.ID, "logonpassfield")
            password_input.click()
            time.sleep(0.3)

            password_input.clear()
            password_input.send_keys(password)
            time.sleep(0.5)

            password_input.send_keys(Keys.ENTER)
            time.sleep(4)

            try:
                current_url = self.driver.current_url
                if "portal" in current_url and "logon" not in current_url.lower():
                    logger.info(f"{self.name}: Giriş başarılı!")
                    return True
                else:
                    logger.warning(f"{self.name}: Giriş başarısız - hala login sayfasında!")
                    return False
            except:
                logger.warning(f"{self.name}: Giriş durumu belirlenemedi!")
                return False

        except Exception as e:
            logger.error(f"{self.name}: Giriş hatası: {e}")
            return False

    def search_barcode(self, barcode):
        """İskoop'ta barkod ara"""
        try:
            self.switch_to_tab()

            logger.info(f"{self.name}: Barkod aranıyor: {barcode}")

            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            search_input = None

            try:
                wait = WebDriverWait(self.driver, 8)
                wait.until(EC.frame_to_be_available_and_switch_to_it("contentAreaFrame"))
                wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe")))

                search_input = wait.until(EC.presence_of_element_located((
                    By.XPATH,
                    "//input[contains(@placeholder, 'Kelime') or contains(@placeholder, 'Barkod') or contains(@placeholder, 'Karekod')]"
                )))
                logger.info(f"{self.name}: Arama kutusu bulundu")

            except Exception as e:
                logger.error(f"{self.name}: iframe'e geçiş veya arama kutusu bulma hatası: {e}")
                search_input = None

            if not search_input:
                try:
                    self.driver.switch_to.default_content()
                except:
                    pass
                return False

            try:
                search_input.clear()
                search_input.send_keys(barcode)
                search_input.send_keys(Keys.ENTER)
                logger.info(f"{self.name}: Barkod arandı: {barcode}")

                time.sleep(2)

                try:
                    self.driver.switch_to.default_content()
                except:
                    pass

                return True

            except Exception as e:
                logger.error(f"{self.name}: Arama hatası: {e}")
                try:
                    self.driver.switch_to.default_content()
                except:
                    pass
                return False

        except Exception as e:
            logger.error(f"{self.name}: Barkod arama hatası: {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False

    def check_stock_status(self):
        """İskoop'ta stok durumunu kontrol et"""
        try:
            self.switch_to_tab()

            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            try:
                wait = WebDriverWait(self.driver, 5)
                wait.until(EC.frame_to_be_available_and_switch_to_it("contentAreaFrame"))
                wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe")))
            except Exception:
                pass

            satis_kosullari = self.get_satis_kosullari()
            en_iyi_mf = self.get_en_iyi_mf()
            sart = en_iyi_mf["oran"] if en_iyi_mf else None

            page_source = self.driver.page_source
            page_source_lower = page_source.lower()

            result = None

            # 1. "Stokta Yok" kontrolü
            try:
                stokta_yok_elements = self.driver.find_elements(
                    By.XPATH, "//*[contains(text(), 'Stokta Yok')]")
                for elem in stokta_yok_elements:
                    if elem.is_displayed():
                        result = {
                            "stok_var": False,
                            "mesaj": "Stokta Yok",
                            "detay": "Stokta Yok yazısı görünüyor",
                            "sart": sart,
                            "satis_kosullari": satis_kosullari
                        }
                        break
            except:
                pass

            # 2. "Yok Listeme Ekle" butonu
            if not result:
                try:
                    yok_liste_buttons = self.driver.find_elements(
                        By.XPATH, "//button[contains(text(), 'Yok Liste')]")
                    for btn in yok_liste_buttons:
                        if btn.is_displayed():
                            result = {
                                "stok_var": False,
                                "mesaj": "Stokta Yok",
                                "detay": "Yok listeme ekle butonu görünüyor",
                                "sart": sart,
                                "satis_kosullari": satis_kosullari
                            }
                            break
                except:
                    pass

            # 3. "Limitiniz 0 adet" kontrolü
            if not result:
                if "limitiniz 0 adet" in page_source_lower or "limitiniz 0" in page_source_lower:
                    result = {
                        "stok_var": False,
                        "mesaj": "Stokta Yok",
                        "detay": "Ürün limiti 0 adet",
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }

            # 4. "Satış elemanınız ile" kontrolü
            if not result:
                if "malzeme için lütfen" in page_source_lower or "satış elemanınız ile" in page_source_lower:
                    result = {
                        "stok_var": False,
                        "mesaj": "Depoyu Ara",
                        "detay": "Satış elemanı ile görüşülmeli",
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }

            # 5. "Stokta" yazısı (pozitif durum)
            if not result:
                try:
                    stokta_elements = self.driver.find_elements(
                        By.XPATH, "//*[contains(text(), 'Stokta') and not(contains(text(), 'Yok'))]")
                    for elem in stokta_elements:
                        if elem.is_displayed() and elem.text.strip() == "Stokta":
                            result = {
                                "stok_var": True,
                                "mesaj": "Stokta Var",
                                "detay": "Stokta yazısı mevcut",
                                "sart": sart,
                                "satis_kosullari": satis_kosullari
                            }
                            break
                except:
                    pass

            # 6. "Siparişe Ekle" butonu
            if not result:
                try:
                    siparis_buttons = self.driver.find_elements(
                        By.XPATH, "//button[contains(text(), 'Siparişe') and contains(text(), 'Ekle')]")
                    for btn in siparis_buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            if "yok" not in btn.text.lower():
                                result = {
                                    "stok_var": True,
                                    "mesaj": "Stokta Var",
                                    "detay": "Siparişe ekle butonu aktif",
                                    "sart": sart,
                                    "satis_kosullari": satis_kosullari
                                }
                                break
                except:
                    pass

            # 7. Genel "stokta yok" metin kontrolü
            if not result:
                if "stokta yok" in page_source_lower or "tükendi" in page_source_lower:
                    result = {
                        "stok_var": False,
                        "mesaj": "Stokta Yok",
                        "detay": "Ürün tükendi",
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }

            # 8. Ürün bulunamadı
            if not result:
                if "bulunamadı" in page_source_lower or "sonuç yok" in page_source_lower:
                    result = {
                        "stok_var": False,
                        "mesaj": "Stokta Yok",
                        "detay": "Ürün bulunamadı",
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }

            # 9. Varsayılan
            if not result:
                result = {
                    "stok_var": False,
                    "mesaj": "Belirsiz",
                    "detay": "Stok durumu tespit edilemedi",
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # Ana frame'e dön
            try:
                self.driver.switch_to.default_content()
            except:
                pass

            return result

        except Exception as e:
            logger.error(f"{self.name}: Stok kontrolü hatası: {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return {
                "stok_var": False,
                "mesaj": "Hata",
                "detay": str(e),
                "sart": None,
                "satis_kosullari": []
            }

    def prepare_order_quantity_area(self):
        """Sipariş adet alanı için iframe'e geç"""
        try:
            self.switch_to_tab()
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            wait = WebDriverWait(self.driver, 5)
            wait.until(EC.frame_to_be_available_and_switch_to_it("contentAreaFrame"))
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe")))
        except Exception:
            pass

    def cleanup_order_quantity_area(self):
        """Iframe'den çık"""
        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass

    def get_product_name(self):
        """İskoop'tan ürün adını al"""
        try:
            self.switch_to_tab()

            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            try:
                wait = WebDriverWait(self.driver, 5)
                wait.until(EC.frame_to_be_available_and_switch_to_it("contentAreaFrame"))
                wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe")))
            except:
                pass

            product_name = None

            try:
                product_name_elem = self.driver.find_element(By.CSS_SELECTOR, "div.product-name")
                product_name = product_name_elem.text.strip()
                if product_name:
                    logger.info(f"{self.name}: Ürün adı bulundu: {product_name}")
            except:
                pass

            try:
                self.driver.switch_to.default_content()
            except:
                pass

            return product_name

        except Exception as e:
            logger.error(f"{self.name}: Ürün adı alma hatası: {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return None

    def _click_kdv_checkbox(self):
        """KDV ile göster checkbox'ını işaretle"""
        try:
            kdv_selectors = [
                "//label[contains(text(), 'KDV ile göster')]",
                "//input[@role='checkbox']/ancestor::div[contains(@class, 'v-input--checkbox')]",
                "//input[@role='checkbox' and @aria-checked='false']",
            ]

            for selector in kdv_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        elem_text = elem.text.strip() if elem.text else ""
                        if "KDV" in elem_text or elem.tag_name == "input":
                            if elem.is_displayed():
                                is_checked = elem.get_attribute("aria-checked") == "true"
                                if not is_checked:
                                    elem.click()
                                    time.sleep(0.5)
                                return True
                except Exception:
                    continue

            return False

        except Exception:
            return False

    def _get_genel_toplam(self):
        """Genel Toplam değerini oku (KDV dahil fiyat)"""
        try:
            genel_toplam_selectors = [
                "//div[contains(@class, 'normal-bold')]//div[contains(@class, 'value')]",
                "//div[contains(@class, 'label') and contains(text(), 'Genel Toplam')]/following-sibling::div[contains(@class, 'value')]",
                "//div[contains(text(), 'Genel Toplam')]/parent::div//div[contains(@class, 'value')]",
                "//*[contains(text(), 'Genel Toplam')]/following-sibling::*",
            ]

            for selector in genel_toplam_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if text and ("₺" in text or text.replace(",", "").replace(".", "").replace(" ", "").isdigit()):
                            price_clean = text.replace("₺", "").replace(" ", "").strip()
                            price_clean = price_clean.replace(".", "").replace(",", ".")
                            try:
                                fiyat = float(price_clean)
                                if fiyat > 0:
                                    logger.info(f"{self.name}: Genel Toplam: {fiyat} TL (KDV dahil)")
                                    return fiyat
                            except ValueError:
                                continue
                except Exception:
                    continue

            return 0.0

        except Exception:
            return 0.0

    def _parse_barem_label(self, label_text):
        """Barem label'ını parse et"""
        min_adet = 1
        mf = 0

        if "+" in label_text:
            parts = label_text.replace(" ", "").split("+")
            if len(parts) == 2:
                try:
                    min_adet = int(parts[0])
                    mf = int(parts[1])
                except ValueError:
                    pass

        return min_adet, mf

    def get_satis_kosullari(self):
        """İskoop'tan satış koşulları tablosunu oku"""
        try:
            kosullar = []

            self._click_kdv_checkbox()
            time.sleep(0.3)

            # Barem kartlarını bul
            barem_card_selectors = [
                "div.barem-container",
                ".barem-container",
                ".barem-ve-vadeler .v-card",
                "[class*='barem-container']",
            ]

            barem_cards = []
            for selector in barem_card_selectors:
                try:
                    barem_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if barem_cards:
                        break
                except:
                    continue

            birim_fiyat_mfsiz = 0.0
            barem_listesi = []

            if barem_cards:
                for card in barem_cards:
                    try:
                        card_text = card.text.strip()
                        if not card_text:
                            continue

                        lines = card_text.split('\n')
                        label_text = lines[0].strip() if lines else ""
                        if not label_text:
                            continue

                        min_adet, mf = self._parse_barem_label(label_text)
                        barem_listesi.append((label_text, min_adet, mf, card))
                    except Exception:
                        continue

                # MF'siz kartı bul ve tıkla
                mfsiz_card = None
                for label_text, min_adet, mf, card in barem_listesi:
                    if mf == 0:
                        mfsiz_card = card
                        break

                if mfsiz_card:
                    try:
                        mfsiz_card.click()
                        time.sleep(0.5)
                    except:
                        try:
                            self.driver.execute_script("arguments[0].click();", mfsiz_card)
                            time.sleep(0.5)
                        except:
                            pass

                    birim_fiyat_mfsiz = self._get_genel_toplam()

                if birim_fiyat_mfsiz <= 0:
                    birim_fiyat_mfsiz = self._get_genel_toplam()

                if birim_fiyat_mfsiz > 0:
                    for label_text, min_adet, mf, card in barem_listesi:
                        if mf == 0:
                            fiyat = birim_fiyat_mfsiz
                        else:
                            fiyat = birim_fiyat_mfsiz * min_adet / (min_adet + mf)

                        kosullar.append({
                            "sart": f"{min_adet}+{mf}" if mf > 0 else "1",
                            "birim_fiyat": round(fiyat, 2),
                            "min_adet": min_adet,
                            "mf": mf,
                            "kampanya": label_text,
                            "kdv_dahil": True
                        })

            # Barem bulunamadıysa Genel Toplam'ı oku
            if not kosullar:
                genel_toplam = self._get_genel_toplam()
                if genel_toplam > 0:
                    kosullar.append({
                        "sart": "1",
                        "birim_fiyat": round(genel_toplam, 2),
                        "min_adet": 1,
                        "mf": 0,
                        "kampanya": "Normal",
                        "kdv_dahil": True
                    })

            return kosullar

        except Exception as e:
            logger.error(f"{self.name}: Satış koşulları okuma hatası: {e}")
            return []

    def get_en_iyi_mf(self):
        """En iyi mal fazlası koşulunu döndür"""
        kosullar = self.get_satis_kosullari()

        if not kosullar:
            return None

        mf_kosullar = [k for k in kosullar if k.get("mf", 0) > 0]

        if not mf_kosullar:
            return None

        en_iyi = max(mf_kosullar, key=lambda x: x["mf"] / x["min_adet"] if x["min_adet"] > 0 else 0)

        return {
            "min_adet": en_iyi["min_adet"],
            "mf": en_iyi["mf"],
            "oran": f"{en_iyi['min_adet']}+{en_iyi['mf']}"
        }
