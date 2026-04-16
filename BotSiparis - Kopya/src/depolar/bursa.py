"""
Bursa Ecza Koop deposu sorgulama modülü
"""
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base_depo import BaseDepo
from ..utils import logger, DEPOLAR


class BursaDepo(BaseDepo):
    """Bursa Ecza Koop deposu sorgulama class'ı"""

    def __init__(self):
        config = DEPOLAR["bursa"]
        super().__init__(config["name"], config["url"], config["elements"])

    def login(self, username, password):
        """Bursa Ecza Koop portalına giriş yap"""
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

            current_url = self.driver.current_url.lower()
            if "portal" in current_url and "logon" not in current_url:
                logger.info(f"{self.name}: Giriş başarılı!")
                return True

            logger.warning(f"{self.name}: Giriş başarısız - hala login sayfasında!")
            return False
        except Exception as e:
            logger.error(f"{self.name}: Giriş hatası: {e}")
            return False

    def _switch_to_order_iframe(self):
        """İçteki sipariş iframe'ine geçiş yap"""
        wait = WebDriverWait(self.driver, 8)
        wait.until(EC.frame_to_be_available_and_switch_to_it("contentAreaFrame"))
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe")))

    def _reset_to_default(self):
        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass

    def search_barcode(self, barcode):
        """Bursa Ecza Koop'ta barkod ara"""
        try:
            self.switch_to_tab()
            logger.info(f"{self.name}: Barkod aranıyor: {barcode}")

            try:
                self._switch_to_order_iframe()
                search_input = WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((
                        By.XPATH,
                        "//input[contains(@placeholder, 'Kelime') or contains(@placeholder, 'Barkod') or contains(@placeholder, 'Karekod')]"
                    ))
                )
                logger.info(f"{self.name}: ✓ Arama kutusu bulundu")
            except Exception as e:
                logger.error(f"{self.name}: ❌ Arama kutusu bulunamadı: {e}")
                self._reset_to_default()
                return False

            search_input.clear()
            search_input.send_keys(barcode)
            search_input.send_keys(Keys.ENTER)
            time.sleep(2)
            self._reset_to_default()
            logger.info(f"{self.name}: ✓ Barkod arandı: {barcode}")
            return True
        except Exception as e:
            logger.error(f"{self.name}: ❌ Barkod arama hatası: {e}")
            self._reset_to_default()
            return False

    def check_stock_status(self):
        """Bursa Ecza Koop'ta stok durumunu kontrol et

        Returns:
            dict: {
                "stok_var": bool,
                "mesaj": str,
                "detay": str,
                "sart": str or None,
                "satis_kosullari": list
            }
        """
        try:
            self.switch_to_tab()

            try:
                self._switch_to_order_iframe()
            except Exception as e:
                logger.info(f"{self.name}: iframe geçişi başarısız: {e}")

            # Satış koşullarını ve şart bilgisini al
            satis_kosullari = self.get_satis_kosullari()
            en_iyi_mf = self.get_en_iyi_mf()
            sart = en_iyi_mf["oran"] if en_iyi_mf else None

            if sart:
                logger.info(f"{self.name}: 📦 Mal fazlası bulundu: {sart}")

            page_source = self.driver.page_source
            page_source_lower = page_source.lower()
            result = None

            try:
                stokta_yok_elements = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Stokta Yok')]")
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
            except Exception:
                pass

            if not result:
                try:
                    yok_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Yok Liste')]")
                    for btn in yok_buttons:
                        if btn.is_displayed():
                            result = {
                                "stok_var": False,
                                "mesaj": "Stokta Yok",
                                "detay": "Yok listeme ekle butonu görünüyor",
                                "sart": sart,
                                "satis_kosullari": satis_kosullari
                            }
                            break
                except Exception:
                    pass

            if not result and ("limitiniz 0" in page_source_lower or "limitiniz 0 adet" in page_source_lower):
                result = {
                    "stok_var": False,
                    "mesaj": "Stokta Yok",
                    "detay": "Ürün limiti 0 adet",
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            if not result and ("malzeme için lütfen" in page_source_lower or "satış elemanınız ile" in page_source_lower):
                result = {
                    "stok_var": False,
                    "mesaj": "Depoyu Ara",
                    "detay": "Satış elemanı ile iletişim gerekli",
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            if not result:
                try:
                    sepete_ekle = self.driver.find_elements(
                        By.XPATH,
                        "//button[contains(text(), 'Sepete Ekle')] | "
                        "//input[@type='button' and contains(@value, 'Sepete Ekle')]"
                    )
                    for btn in sepete_ekle:
                        if btn.is_displayed() and btn.is_enabled():
                            result = {
                                "stok_var": True,
                                "mesaj": "Stokta Var",
                                "detay": "Sepete Ekle butonu mevcut",
                                "sart": sart,
                                "satis_kosullari": satis_kosullari
                            }
                            break
                except Exception:
                    pass

            if not result:
                # Siparişe Ekle butonu Bursa'da da kullanılıyor
                try:
                    siparis_buttons = self.driver.find_elements(
                        By.XPATH,
                        "//button[contains(text(), 'Siparişe') and contains(text(), 'Ekle')]"
                    )
                    for btn in siparis_buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            lower_text = btn.text.lower()
                            if "yok" not in lower_text:
                                result = {
                                    "stok_var": True,
                                    "mesaj": "Stokta Var",
                                    "detay": "Siparişe Ekle butonu aktif",
                                    "sart": sart,
                                    "satis_kosullari": satis_kosullari
                                }
                                break
                except Exception:
                    pass

            if not result:
                # Adet girişi aktifse stokta var say
                try:
                    adet_inputs = self.driver.find_elements(
                        By.XPATH,
                        "//input[contains(@placeholder, 'Adet') or contains(@id, 'adet')]"
                    )
                    for adet_input in adet_inputs:
                        if adet_input.is_displayed() and adet_input.is_enabled():
                            logger.info(f"{self.name}: ✓ Adet alanı aktif - STOKTA VAR")
                            result = {
                                "stok_var": True,
                                "mesaj": "Stokta Var",
                                "detay": "Adet girilebiliyor",
                                "sart": sart,
                                "satis_kosullari": satis_kosullari
                            }
                            break
                except Exception:
                    pass

            if not result:
                if "stokta" in page_source_lower and "stokta yok" not in page_source_lower:
                    result = {
                        "stok_var": True,
                        "mesaj": "Stokta Var",
                        "detay": "Stokta yazısı görünüyor",
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }

            if not result:
                logger.warning(f"{self.name}: ⚠ Durum belirlenemedi")
                result = {
                    "stok_var": False,
                    "mesaj": "Belirsiz",
                    "detay": "Durum belirlenemedi",
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            return result
        except Exception as e:
            logger.error(f"{self.name}: Stok kontrolü hatası: {e}")
            return {
                "stok_var": False,
                "mesaj": "Hata",
                "detay": str(e),
                "sart": None,
                "satis_kosullari": []
            }
        finally:
            self._reset_to_default()

    def prepare_order_quantity_area(self):
        """Adet alanı için iframe'e geç"""
        try:
            self.switch_to_tab()
            self._switch_to_order_iframe()
        except Exception as e:
            logger.debug(f"{self.name}: Adet alanı iframe geçiş hatası: {e}")

    def cleanup_order_quantity_area(self):
        """Iframe'den çık"""
        self._reset_to_default()

    def get_product_name(self):
        """Bursa Ecza Koop'tan ürün adını al

        Returns:
            str: Ürün adı veya None
        """
        try:
            self.switch_to_tab()

            try:
                self._switch_to_order_iframe()
            except:
                pass

            product_name = None

            # 1. Yöntem: product-name div'i (Vue.js uygulaması içinde - İskoop ile aynı)
            try:
                product_name_elem = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "div.product-name"
                )
                product_name = product_name_elem.text.strip()
                if product_name:
                    logger.info(f"{self.name}: Ürün adı bulundu: {product_name}")
            except:
                pass

            # 2. Yöntem: Sayfa başlığı
            if not product_name:
                try:
                    title = self.driver.title
                    if title and "-" in title:
                        product_name = title.split("-")[-1].strip()
                        if product_name:
                            logger.info(f"{self.name}: Ürün adı bulundu (title): {product_name}")
                except:
                    pass

            self._reset_to_default()
            return product_name

        except Exception as e:
            logger.error(f"{self.name}: Ürün adı alma hatası: {e}")
            self._reset_to_default()
            return None

    def _click_kdv_checkbox(self):
        """KDV ile göster checkbox'ını işaretle (eğer işaretli değilse)

        HTML yapısı (Vue.js/Vuetify):
        <div class="v-input--checkbox">
          <input aria-checked="false" role="checkbox" type="checkbox">
          <label>KDV ile göster</label>
        </div>

        Returns:
            bool: İşlem başarılı mı
        """
        try:
            # Vuetify checkbox yapısı - label'ı bul ve tıkla
            kdv_selectors = [
                # Label'a tıklama (en güvenilir)
                "//label[contains(text(), 'KDV ile göster')]",
                # Input'un parent container'ına tıklama
                "//input[@role='checkbox']/ancestor::div[contains(@class, 'v-input--checkbox')]",
                # Checkbox input (aria-checked ile kontrol)
                "//input[@role='checkbox' and @aria-checked='false']",
                # Genel checkbox arama
                "//input[@type='checkbox']",
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
                                    logger.info(f"{self.name}: ✓ KDV ile göster checkbox'ı işaretlendi")
                                else:
                                    logger.info(f"{self.name}: ✓ KDV ile göster checkbox'ı zaten işaretli")
                                return True
                except Exception as e:
                    logger.debug(f"{self.name}: KDV selector hatası ({selector}): {e}")
                    continue

            logger.warning(f"{self.name}: KDV ile göster checkbox'ı bulunamadı")
            return False

        except Exception as e:
            logger.debug(f"{self.name}: KDV checkbox hatası: {e}")
            return False

    def _get_genel_toplam(self):
        """Genel Toplam değerini oku (KDV dahil fiyat)

        HTML yapısı (Vue.js):
        <div class="normal-bold">
          <div class="label text-right">Genel Toplam</div>
          <div class="value text-right"> ₺ 17,15 </div>
        </div>

        Returns:
            float: Genel Toplam fiyat veya 0.0
        """
        try:
            genel_toplam_selectors = [
                # Ana selector: normal-bold class'ı içindeki value
                "//div[contains(@class, 'normal-bold')]//div[contains(@class, 'value')]",
                # Genel Toplam label'ının kardeş elementi
                "//div[contains(@class, 'label') and contains(text(), 'Genel Toplam')]/following-sibling::div[contains(@class, 'value')]",
                # Parent'tan geçerek
                "//div[contains(text(), 'Genel Toplam')]/parent::div//div[contains(@class, 'value')]",
                # selling-detail içinde
                "//div[contains(@class, 'selling-detail')]//div[contains(text(), 'Genel Toplam')]/following-sibling::div",
                # Fallback
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
                                    logger.info(f"{self.name}: ✓ Genel Toplam bulundu: {fiyat} TL (KDV dahil)")
                                    return fiyat
                            except ValueError:
                                continue
                except Exception as e:
                    logger.debug(f"{self.name}: Genel Toplam selector hatası ({selector}): {e}")
                    continue

            logger.warning(f"{self.name}: Genel Toplam bulunamadı")
            return 0.0

        except Exception as e:
            logger.debug(f"{self.name}: Genel Toplam okuma hatası: {e}")
            return 0.0

    def _parse_barem_label(self, label_text):
        """Barem label'ını parse et

        Args:
            label_text: "MF'siz", "5 + 1", "10 + 3" gibi

        Returns:
            tuple: (min_adet, mf)
        """
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
        """Bursa Ecza Koop'tan satış koşulları tablosunu oku (MF, iskonto vb.)

        YENİ MANTIK (İskoop ile aynı):
        1. "KDV ile göster" checkbox'ını işaretle
        2. Her barem için Genel Toplam'dan KDV dahil fiyatı oku
        3. Barem seçimi yoksa tek fiyat döndür

        Returns:
            list: [{"sart": str, "birim_fiyat": float, "min_adet": int, "mf": int, "kampanya": str}, ...]
        """
        try:
            # NOT: Bu metod check_stock_status içinden çağrıldığında
            # zaten iframe içindeyiz, tekrar geçiş yapmıyoruz

            kosullar = []

            # 1. KDV ile göster checkbox'ını işaretle
            self._click_kdv_checkbox()
            time.sleep(0.3)

            # 2. Barem kartlarını bul
            # HTML yapısı (Vue.js/Vuetify):
            # <div class="barem-container v-card v-card--link v-sheet theme--light">
            #   <div class="v-card__text">
            #     <div class="label"> MF'siz </div>
            #     <div class="price"><span class="barem-price">₺ 15,59</span></div>
            #   </div>
            # </div>
            barem_bulundu = False

            barem_card_selectors = [
                # Ana selector: barem-container class'ı (en spesifik)
                "div.barem-container",
                ".barem-container",
                # Vuetify v-card yapısı
                "div.barem-container.v-card",
                # barem-ve-vadeler içindeki kartlar
                ".barem-ve-vadeler .v-card",
                # Fallback
                "[class*='barem-container']",
            ]

            barem_cards = []
            for selector in barem_card_selectors:
                try:
                    barem_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if barem_cards:
                        logger.info(f"{self.name}: Barem kartları bulundu ({selector}): {len(barem_cards)} adet")
                        break
                except:
                    continue

            # Barem kartları bulunduysa işle
            # YENİ MANTIK: Sadece MF'siz fiyatı oku, diğerlerini hesapla
            # Çünkü barem kartına tıklayınca miktar değişiyor ve Genel Toplam = miktar × birim fiyat oluyor
            birim_fiyat_mfsiz = 0.0
            barem_listesi = []  # [(label_text, min_adet, mf, card), ...]

            if barem_cards:
                barem_bulundu = True

                # Önce tüm barem kartlarının bilgilerini topla
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

                    except Exception as e:
                        logger.debug(f"{self.name}: Barem kart parse hatası: {e}")
                        continue

                # MF'siz kartı bul ve tıkla, Genel Toplam'ı oku
                mfsiz_card = None
                for label_text, min_adet, mf, card in barem_listesi:
                    if mf == 0:  # MF'siz
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
                    logger.info(f"{self.name}: MF'siz birim fiyat (Genel Toplam): {birim_fiyat_mfsiz} TL (KDV dahil)")

                # Eğer MF'siz bulunamadıysa, mevcut Genel Toplam'ı oku
                if birim_fiyat_mfsiz <= 0:
                    birim_fiyat_mfsiz = self._get_genel_toplam()
                    logger.info(f"{self.name}: MF'siz bulunamadı, mevcut Genel Toplam: {birim_fiyat_mfsiz} TL")

                # Tüm baremlerin fiyatlarını hesapla
                if birim_fiyat_mfsiz > 0:
                    for label_text, min_adet, mf, card in barem_listesi:
                        if mf == 0:
                            # MF'siz - doğrudan birim fiyat
                            fiyat = birim_fiyat_mfsiz
                        else:
                            # MF'li - hesapla: birim_fiyat × min_adet / (min_adet + mf)
                            fiyat = birim_fiyat_mfsiz * min_adet / (min_adet + mf)

                        kosullar.append({
                            "sart": f"{min_adet}+{mf}" if mf > 0 else "1",
                            "birim_fiyat": round(fiyat, 2),
                            "min_adet": min_adet,
                            "mf": mf,
                            "kampanya": label_text,
                            "kdv_dahil": True
                        })
                        logger.info(f"{self.name}: Barem '{label_text}': {fiyat:.2f} TL (KDV dahil, hesaplandı)")

            # Barem bulunamadıysa, sadece Genel Toplam'ı oku
            if not kosullar:
                logger.info(f"{self.name}: Barem bulunamadı, Genel Toplam okunuyor...")
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
                    logger.info(f"{self.name}: Genel Toplam (MF'siz): {genel_toplam} TL (KDV dahil)")

            if kosullar:
                logger.info(f"{self.name}: {len(kosullar)} satış koşulu bulundu")
                for k in kosullar:
                    logger.debug(f"  - {k['kampanya']}: {k['birim_fiyat']} TL (KDV dahil)")

            return kosullar

        except Exception as e:
            logger.error(f"{self.name}: Satış koşulları okuma hatası: {e}")
            import traceback
            logger.error(f"{self.name}: Detay: {traceback.format_exc()}")
            return []

    def get_en_iyi_mf(self):
        """En iyi mal fazlası koşulunu döndür

        Returns:
            dict: {"min_adet": int, "mf": int, "oran": str} veya None
        """
        kosullar = self.get_satis_kosullari()

        if not kosullar:
            return None

        # MF > 0 olan koşulları filtrele
        mf_kosullar = [k for k in kosullar if k.get("mf", 0) > 0]

        if not mf_kosullar:
            return None

        # En düşük min_adet ile en yüksek MF oranını bul
        en_iyi = max(mf_kosullar, key=lambda x: x["mf"] / x["min_adet"] if x["min_adet"] > 0 else 0)

        return {
            "min_adet": en_iyi["min_adet"],
            "mf": en_iyi["mf"],
            "oran": f"{en_iyi['min_adet']}+{en_iyi['mf']}"
        }
