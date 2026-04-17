"""
Sancak Ecza deposu sorgulama modülü
"""
import time
import re
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from .base_depo import BaseDepo
from .depo_config import DEPOLAR

logger = logging.getLogger(__name__)


class SancakDepo(BaseDepo):
    """Sancak Ecza deposu sorgulama class'ı"""

    def __init__(self):
        config = DEPOLAR["sancak"]
        super().__init__(config["name"], config["url"], config["elements"])

    def login(self, username, password):
        """Sancak Ecza'ya giriş yap"""
        try:
            self.switch_to_tab()

            logger.info(f"{self.name}: Giriş yapılıyor...")

            username_input = self.wait_for_element(By.ID, "Customer_username")
            if not username_input:
                return False

            username_input.clear()
            username_input.send_keys(username)
            time.sleep(0.5)

            password_input = self.driver.find_element(By.ID, "Customer_password")
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

            current_url = self.driver.current_url.lower()

            if "/home/mainpage" in current_url:
                logger.info(f"{self.name}: Giriş başarılı!")
                return True

            try:
                search_box = self.driver.find_element(By.ID, "search")
                if search_box and search_box.is_displayed():
                    logger.info(f"{self.name}: Giriş başarılı! (Arama kutusu bulundu)")
                    return True
            except:
                pass

            try:
                login_form = self.driver.find_element(By.ID, "Customer_username")
                if login_form.is_displayed():
                    logger.warning(f"{self.name}: Giriş başarısız - hala login sayfasında!")
                    return False
            except:
                logger.info(f"{self.name}: Giriş başarılı (login formu kayboldu)")
                return True

            return False

        except Exception as e:
            logger.error(f"{self.name}: Giriş hatası: {e}")
            return False

    def search_barcode(self, barcode):
        """Sancak Ecza'da barkod ara"""
        try:
            self.switch_to_tab()

            logger.info(f"{self.name}: Barkod aranıyor: {barcode}")

            # Önceki ürün popup'ını kapat (varsa)
            try:
                close_button = self.driver.find_element(By.XPATH,
                    "//button[contains(@class, 'close')] | //span[contains(@class, 'close')] | //a[contains(text(), '×')]")
                close_button.click()
                time.sleep(0.3)
            except:
                pass

            try:
                actions = ActionChains(self.driver)
                actions.send_keys(Keys.ESCAPE).perform()
                time.sleep(0.15)
            except:
                pass

            # "Stoğa Ürün Girişi Yapıldı" popup'ını kapat
            try:
                hayir_button = self.driver.find_element(By.XPATH,
                    "//button[contains(@class, 'btn-gray') and contains(@class, 'cancel') and contains(text(), 'Hayır')]")
                if hayir_button.is_displayed():
                    hayir_button.click()
                    time.sleep(0.3)
            except:
                pass

            search_input = self.wait_for_element(By.ID, self.elements["search_input"])
            if not search_input:
                return False

            search_input.clear()
            search_input.send_keys(barcode)
            search_input.send_keys(Keys.ENTER)

            time.sleep(1)

            return True
        except Exception as e:
            logger.error(f"{self.name}: Barkod arama hatası: {e}")
            return False

    def get_product_name(self):
        """Sancak Ecza'dan ürün adını al"""
        try:
            self.switch_to_tab()

            try:
                urun_adi = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "#search-detay .urun-adi h2"
                )
                product_name = urun_adi.text.strip()
                if product_name:
                    return product_name
            except:
                pass

            try:
                item_name = self.driver.find_element(
                    By.CSS_SELECTOR,
                    ".item-name-td span[data-popup='true']"
                )
                product_name = item_name.text.strip()
                if product_name:
                    return product_name
            except:
                pass

            return None

        except Exception as e:
            logger.error(f"{self.name}: Ürün adı alma hatası: {e}")
            return None

    def get_depo_price(self):
        """Sancak Ecza'dan KDV Dahil Birim Fiyatını al"""
        try:
            self.switch_to_tab()

            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            try:
                WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".siparis-detay-bilgiler .afternetprice"))
                )
            except:
                pass

            # "1+0" seçeneğini bul ve tıkla
            try:
                adet_boxes = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "#search-detay .adetler .table-adet, .siparis-detay-modal .adetler .table-adet"
                )

                found_1_0 = False
                for box in adet_boxes:
                    try:
                        text = box.text.strip()
                        style = box.get_attribute("style") or ""

                        if "hidden" in style.lower():
                            continue

                        if text == "1+0" or text == "1":
                            if "active" not in (box.get_attribute("class") or ""):
                                box.click()
                                time.sleep(0.3)
                                try:
                                    self.driver.execute_script("arguments[0].click();", box)
                                except:
                                    pass
                            found_1_0 = True
                            break
                    except:
                        continue

                if not found_1_0:
                    try:
                        manuel_input = self.driver.find_element(
                            By.CSS_SELECTOR,
                            "#search-detay .manuel-adet input[name='ManuelAdet'], "
                            ".siparis-detay-modal .manuel-adet input[name='ManuelAdet'], "
                            "input[name='ManuelAdet']"
                        )
                        manuel_input.clear()
                        manuel_input.send_keys("1")
                        manuel_input.send_keys(Keys.TAB)
                        time.sleep(1.0)
                    except Exception:
                        try:
                            num_input = self.driver.find_element(
                                By.CSS_SELECTOR,
                                "#search-detay input[type='number'], "
                                ".siparis-detay-modal input[type='number']"
                            )
                            num_input.clear()
                            num_input.send_keys("1")
                            num_input.send_keys(Keys.TAB)
                            time.sleep(1.0)
                        except Exception:
                            pass

            except Exception:
                pass

            time.sleep(1.0)

            # afternetprice span'ından oku
            for selector in [
                "#search-detay .siparis-detay-bilgiler .afternetprice",
                ".siparis-detay-bilgiler .afternetprice",
                "#search-detay .grosstotal, .siparis-detay-bilgiler .grosstotal"
            ]:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    price_text = elem.text.strip()
                    if price_text:
                        price_text = price_text.replace("₺", "").strip()
                        price_text = price_text.replace(".", "").replace(",", ".")
                        price = float(price_text)
                        if 1 <= price <= 50000:
                            logger.info(f"{self.name}: KDV Dahil Birim Fiyat: {price} TL")
                            return price
                except Exception:
                    continue

            return None

        except Exception as e:
            logger.error(f"{self.name}: Fiyat okuma hatası: {e}")
            return None

    def check_stock_status(self):
        """Sancak Ecza'da stok durumunu kontrol et"""
        try:
            self.switch_to_tab()

            # Önceki popup'ı kapat
            try:
                close_button = self.driver.find_element(By.XPATH,
                    "//button[contains(@class, 'close')] | //span[contains(@class, 'close')] | //a[contains(text(), '×')]")
                close_button.click()
                time.sleep(0.15)
            except:
                pass

            try:
                actions = ActionChains(self.driver)
                actions.send_keys(Keys.ESCAPE).perform()
                time.sleep(0.15)
            except:
                pass

            # İlk satıra tıkla (YENİ popup açılsın)
            try:
                first_row = self.driver.find_element(By.XPATH,
                    "//table//tbody//tr[1] | //div[contains(@class, 'product-item')][1] | //div[@class='product-row'][1]")
                first_row.click()
                time.sleep(1)
            except Exception:
                pass

            time.sleep(0.3)

            satis_kosullari = self.get_satis_kosullari()

            depo_price = None
            if satis_kosullari:
                for k in satis_kosullari:
                    if k.get("mf", 0) == 0:
                        depo_price = k.get("birim_fiyat")
                        break
                if depo_price is None and satis_kosullari:
                    depo_price = satis_kosullari[0].get("birim_fiyat")

            en_iyi_mf = self.get_en_iyi_mf(satis_kosullari)
            sart = en_iyi_mf["oran"] if en_iyi_mf else None

            page_source = self.driver.page_source

            # 1. "Bakiye Al" butonu (POPUP içinde) → STOKTA YOK
            try:
                bakiye_al = self.driver.find_element(By.XPATH,
                    "//div[contains(@class, 'siparis-detay-modal') or @id='search-detay']//button[contains(@class, 'addbackorder') and contains(@style, 'display: block')]")
                if bakiye_al and bakiye_al.is_displayed():
                    return {
                        "stok_var": False,
                        "mesaj": "Stokta Yok",
                        "detay": "Bakiye Al butonu mevcut (popup)",
                        "fiyat": depo_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except Exception:
                pass

            # 2. "Sepete Ekle" butonu (POPUP içinde) → STOKTA VAR
            try:
                sepete_ekle = self.driver.find_element(By.XPATH,
                    "//div[contains(@class, 'siparis-detay-modal') or @id='search-detay']//button[contains(@class, 'addtobasket') and contains(@style, 'display: block')]")
                if sepete_ekle and sepete_ekle.is_displayed():
                    return {
                        "stok_var": True,
                        "mesaj": "Stokta Var",
                        "detay": "Sepete Ekle butonu mevcut (popup)",
                        "fiyat": depo_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except Exception:
                pass

            # 3. "Satış Temsilciniz" mesajı → DEPOYU ARA
            if "Lütfen Satış Temsilciniz İle Görüşün" in page_source or \
               "satış temsilciniz" in page_source.lower():
                return {
                    "stok_var": False,
                    "mesaj": "Depoyu Ara",
                    "detay": "Satış temsilcisi ile görüşülmeli",
                    "fiyat": depo_price,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # 4. Yeşil nokta kontrolü
            try:
                green_badge = self.driver.find_element(By.CSS_SELECTOR, "span.badge-sm.active")
                if green_badge:
                    return {
                        "stok_var": True,
                        "mesaj": "Stokta Var",
                        "detay": "Yeşil nokta (badge-sm active)",
                        "fiyat": depo_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except Exception:
                pass

            # 5. Kırmızı nokta kontrolü
            try:
                red_badge = self.driver.find_element(By.CSS_SELECTOR, "span.badge-sm:not(.active)")
                if red_badge:
                    return {
                        "stok_var": False,
                        "mesaj": "Stokta Yok",
                        "detay": "Kırmızı nokta (badge-sm)",
                        "fiyat": depo_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except Exception:
                pass

            # 6. "Ürün bulunamadı"
            if "ürün bulunamadı" in page_source.lower() or \
               "sonuç bulunamadı" in page_source.lower():
                return {
                    "stok_var": False,
                    "mesaj": "Ürün Bulunamadı",
                    "detay": "Ürün bulunamadı mesajı",
                    "fiyat": None,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            logger.warning(f"{self.name}: Durum belirlenemedi")
            return {
                "stok_var": False,
                "mesaj": "Belirsiz",
                "detay": "Durum belirlenemedi",
                "fiyat": depo_price,
                "sart": sart,
                "satis_kosullari": satis_kosullari
            }

        except Exception as e:
            logger.error(f"{self.name}: Stok kontrolü hatası: {e}")
            return {
                "stok_var": False,
                "mesaj": "Hata",
                "detay": str(e),
                "fiyat": None,
                "sart": None,
                "satis_kosullari": []
            }

    def get_satis_kosullari(self):
        """Sancak Ecza'dan satış koşulları tablosunu oku"""
        try:
            kosullar = []
            mf_secenekleri = []

            # Popup panel içindeki MF badge'lerini bul
            try:
                adetler_div = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "#search-detay .adetler, .siparis-detay-modal .adetler"
                )

                mf_spans = adetler_div.find_elements(By.CSS_SELECTOR, "span.table-adet")

                for span in mf_spans:
                    try:
                        style = span.get_attribute("style") or ""
                        if "hidden" in style.lower():
                            continue

                        mf_text = span.text.strip()
                        if not mf_text or "+" not in mf_text:
                            continue

                        parts = mf_text.replace(" ", "").split("+")
                        if len(parts) != 2:
                            continue

                        try:
                            min_adet = int(parts[0])
                            mf = int(parts[1])
                        except ValueError:
                            continue

                        tooltip = span.get_attribute("data-original-title") or ""
                        kdv_orani = 10

                        if tooltip:
                            kdv_match = re.search(r'\(%(\d+)\)', tooltip)
                            if kdv_match:
                                kdv_orani = int(kdv_match.group(1))

                        mf_secenekleri.append({
                            "min_adet": min_adet,
                            "mf": mf,
                            "kdv_orani": kdv_orani
                        })

                    except Exception:
                        continue

            except Exception:
                pass

            birim_fiyat = self.get_depo_price()

            if birim_fiyat and birim_fiyat > 0:
                kosullar.append({
                    "sart": "1",
                    "birim_fiyat": round(birim_fiyat, 2),
                    "min_adet": 1,
                    "mf": 0,
                    "kdv_orani": 10
                })

                for mf_opt in mf_secenekleri:
                    min_adet = mf_opt["min_adet"]
                    mf = mf_opt["mf"]
                    kdv_orani = mf_opt.get("kdv_orani", 10)

                    if min_adet == 1 and mf == 0:
                        continue

                    if mf > 0:
                        toplam_adet = min_adet + mf
                        hesaplanan_birim = (min_adet * birim_fiyat) / toplam_adet
                    else:
                        hesaplanan_birim = birim_fiyat

                    kosullar.append({
                        "sart": f"{min_adet}+{mf}" if mf > 0 else str(min_adet),
                        "birim_fiyat": round(hesaplanan_birim, 2),
                        "min_adet": min_adet,
                        "mf": mf,
                        "kdv_orani": kdv_orani
                    })

            return kosullar

        except Exception as e:
            logger.error(f"{self.name}: Satış koşulları okuma hatası: {e}")
            return []

    def get_en_iyi_mf(self, kosullar=None):
        """En iyi mal fazlası koşulunu döndür"""
        if kosullar is None:
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

    def set_order_quantity(self, quantity):
        """Sancak Ecza'da sipariş miktarını ayarla (popup içinde)"""
        try:
            self.switch_to_tab()

            logger.info(f"{self.name}: Sipariş adedi ayarlanıyor: {quantity}")
            time.sleep(0.5)

            input_field = None

            # Yöntem 1: Popup içindeki visible input
            try:
                popup_inputs = self.driver.find_elements(By.XPATH,
                    "//div[contains(@class, 'modal') and contains(@style, 'display: block')]//input[@type='number'] | "
                    "//div[contains(@class, 'modal') and contains(@style, 'display: block')]//input[@type='text']")

                for inp in popup_inputs:
                    if inp.is_displayed() and inp.is_enabled():
                        placeholder = inp.get_attribute("placeholder") or ""
                        name = inp.get_attribute("name") or ""

                        if "adet" in placeholder.lower() or "manuel" in name.lower() or "quantity" in name.lower():
                            input_field = inp
                            break

                if not input_field and popup_inputs:
                    for inp in popup_inputs:
                        if inp.is_displayed() and inp.is_enabled():
                            input_field = inp
                            break
            except Exception:
                pass

            # Yöntem 2: Son görünen input
            if not input_field:
                try:
                    all_inputs = self.driver.find_elements(By.XPATH,
                        "//input[@type='number' or @type='text']")
                    visible_inputs = [inp for inp in all_inputs
                                     if inp.is_displayed() and inp.is_enabled()]
                    if visible_inputs:
                        input_field = visible_inputs[-1]
                except Exception:
                    pass

            if not input_field:
                logger.warning(f"{self.name}: Sipariş miktar alanı bulunamadı")
                return False

            try:
                self.driver.execute_script("""
                    arguments[0].value = '';
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, input_field, str(quantity))
                logger.info(f"{self.name}: Sipariş adedi {quantity} olarak ayarlandı")
                return True
            except Exception:
                input_field.click()
                time.sleep(0.1)
                input_field.send_keys(Keys.CONTROL, "a")
                input_field.send_keys(Keys.DELETE)
                input_field.send_keys(str(quantity))
                return True

        except Exception as e:
            logger.error(f"{self.name}: Sipariş adedi ayarlanırken hata: {e}")
            return False
