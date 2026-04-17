"""
Sancak Ecza deposu sorgulama modülü
"""
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from .base_depo import BaseDepo
from ..utils import logger, DEPOLAR


class SancakDepo(BaseDepo):
    """Sancak Ecza deposu sorgulama class'ı"""

    def __init__(self):
        config = DEPOLAR["sancak"]
        super().__init__(config["name"], config["url"], config["elements"])

    def login(self, username, password):
        """Sancak Ecza'ya giriş yap

        Args:
            username: GLN ya da TC Numarası
            password: Parola

        Returns:
            bool: Giriş başarılı mı
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Giriş yapılıyor...")

            # GLN/TC Numarası
            username_input = self.wait_for_element(By.ID, "Customer_username")
            if not username_input:
                return False

            username_input.clear()
            username_input.send_keys(username)
            time.sleep(0.5)

            # Parola
            password_input = self.driver.find_element(By.ID, "Customer_password")
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(0.5)

            # Giriş butonuna tıkla veya Enter tuşu
            password_input.send_keys(Keys.ENTER)

            # Giriş kontrolü - arama kutusunun yüklenmesini bekle
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

            # Giriş başarılı mı kontrol et
            # Giriş olduktan sonra URL değişecek: /Home/MainPage
            current_url = self.driver.current_url.lower()

            # 1. Yöntem: URL kontrolü - /home/mainpage varsa başarılı
            if "/home/mainpage" in current_url:
                logger.info(f"{self.name}: Giriş başarılı! (URL: {current_url})")
                return True

            # 2. Yöntem: Arama kutusu varsa giriş başarılı (id="search")
            try:
                search_box = self.driver.find_element(By.ID, "search")
                if search_box and search_box.is_displayed():
                    logger.info(f"{self.name}: Giriş başarılı! (Arama kutusu bulundu)")
                    return True
            except:
                pass

            # 3. Yöntem: Sepetim butonu varsa giriş başarılı
            try:
                sepet_button = self.driver.find_element(By.XPATH,
                    "//a[contains(text(), 'Sepetim')] | //button[contains(text(), 'Sepetim')]")
                if sepet_button and sepet_button.is_displayed():
                    logger.info(f"{self.name}: Giriş başarılı! (Sepetim butonu bulundu)")
                    return True
            except:
                pass

            # Hala login formunda mıyız?
            try:
                login_form = self.driver.find_element(By.ID, "Customer_username")
                if login_form.is_displayed():
                    logger.warning(f"{self.name}: Giriş başarısız - hala login sayfasında!")
                    return False
            except:
                # Login formu yoksa giriş başarılı olmuş olabilir
                logger.info(f"{self.name}: Giriş başarılı (login formu kayboldu)")
                return True

            return False

        except Exception as e:
            logger.error(f"{self.name}: Giriş hatası: {e}")
            return False

    def search_barcode(self, barcode):
        """Sancak Ecza'da barkod ara

        Args:
            barcode: Aranacak barkod

        Returns:
            bool: Arama başarılı mı
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Barkod aranıyor: {barcode}")

            # ÖNCELİKLE: Önceki ürün popup'ını kapat (varsa)
            try:
                # 1. Yöntem: × (çarpı) butonunu bul ve tıkla
                close_button = self.driver.find_element(By.XPATH,
                    "//button[contains(@class, 'close')] | //span[contains(@class, 'close')] | //a[contains(text(), '×')]")
                close_button.click()
                logger.debug(f"{self.name}: Önceki popup kapatıldı (× butonu)")
                time.sleep(0.3)
            except:
                pass

            # 2. Yöntem: ESC tuşu ile kapat (yedek)
            try:
                actions = ActionChains(self.driver)
                actions.send_keys(Keys.ESCAPE).perform()
                logger.debug(f"{self.name}: ESC tuşu ile popup kapatıldı")
                time.sleep(0.15)  # 0.3 → 0.15 (HIZLANDIRILDI)
            except:
                pass

            # 3. Yöntem: "Stoğa Ürün Girişi Yapıldı" popup'ını kapat (Hayır butonu)
            try:
                hayir_button = self.driver.find_element(By.XPATH,
                    "//button[contains(@class, 'btn-gray') and contains(@class, 'cancel') and contains(text(), 'Hayır')]")
                if hayir_button.is_displayed():
                    hayir_button.click()
                    logger.info(f"{self.name}: 'Stoğa Ürün Girişi' popup'ı kapatıldı (Hayır butonu)")
                    time.sleep(0.3)
            except:
                pass

            # Arama kutusunu bul
            search_input = self.wait_for_element(By.ID, self.elements["search_input"])
            if not search_input:
                return False

            # Arama kutusunu temizle ve barkodu yaz
            search_input.clear()
            search_input.send_keys(barcode)
            search_input.send_keys(Keys.ENTER)

            # Sonuçların yüklenmesi için bekle
            time.sleep(1)  # 2 → 1 (HIZLANDIRILDI)

            return True
        except Exception as e:
            logger.error(f"{self.name}: Barkod arama hatası: {e}")
            return False

    def get_product_name(self):
        """Sancak Ecza'dan ürün adını al

        Returns:
            str: Ürün adı veya None
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            product_name = None

            # 1. Yöntem: #search-detay popup içindeki .urun-adi h2
            try:
                urun_adi = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "#search-detay .urun-adi h2"
                )
                product_name = urun_adi.text.strip()
                if product_name and len(product_name) > 0:
                    logger.info(f"{self.name}: Ürün adı bulundu (.urun-adi h2): {product_name}")
                    return product_name
            except:
                pass

            # 2. Yöntem: Arama sonuç tablosundaki ürün adı
            try:
                item_name = self.driver.find_element(
                    By.CSS_SELECTOR,
                    ".item-name-td span[data-popup='true']"
                )
                product_name = item_name.text.strip()
                if product_name and len(product_name) > 0:
                    logger.info(f"{self.name}: Ürün adı bulundu (item-name-td): {product_name}")
                    return product_name
            except:
                pass

            # 3. Yöntem: h2 başlığı (genel)
            try:
                h2_element = self.driver.find_element(By.CSS_SELECTOR, ".urun-adi h2, h2")
                product_name = h2_element.text.strip()
                if product_name and len(product_name) > 0:
                    logger.info(f"{self.name}: Ürün adı bulundu (h2): {product_name}")
                    return product_name
            except:
                pass

            logger.warning(f"{self.name}: Ürün adı bulunamadı")
            return None

        except Exception as e:
            logger.error(f"{self.name}: Ürün adı alma hatası: {e}")
            return None

    def get_depo_price(self):
        """Sancak Ecza'dan KDV Dahil Birim Fiyatını al (popup panelinden)

        ÖNEMLİ: Önce 1+0 (tek adet) seçeneğini seç, sonra fiyatı oku.
        Popup tam yüklenene kadar bekle (fiyat stabilize olmalı).

        Returns:
            float or None: KDV Dahil Birim Fiyatı (TL) - 1 adet için
        """
        try:
            self.switch_to_tab()

            # Popup'ın yüklenmesini bekle
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            try:
                WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".siparis-detay-bilgiler .afternetprice"))
                )
            except:
                logger.debug(f"{self.name}: .afternetprice elementi için bekleme zaman aşımı")

            # ÖNCELİK 1: "1+0" seçeneğini bul ve tıkla
            # Bu sayede her zaman 1 adetlik fiyatı alırız
            try:
                # "1+0" metnini içeren span'ı bul
                adet_boxes = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "#search-detay .adetler .table-adet, .siparis-detay-modal .adetler .table-adet"
                )

                found_1_0 = False
                for box in adet_boxes:
                    try:
                        text = box.text.strip()
                        style = box.get_attribute("style") or ""

                        # hidden span'ları atla
                        if "hidden" in style.lower():
                            continue

                        # "1+0" seçeneğini bul
                        if text == "1+0" or text == "1":
                            if "active" not in (box.get_attribute("class") or ""):
                                box.click()
                                time.sleep(0.3)  # Tıklama sonrası kısa bekleme

                                # JavaScript ile de tıkla (daha güvenilir)
                                try:
                                    self.driver.execute_script("arguments[0].click();", box)
                                except:
                                    pass

                                logger.info(f"{self.name}: '1+0' seçeneği tıklandı")
                                found_1_0 = True
                            else:
                                logger.debug(f"{self.name}: '1+0' zaten aktif")
                                found_1_0 = True
                            break
                    except:
                        continue

                if not found_1_0:
                    # 1+0 badge'i yok, ManuelAdet input'unu kullan
                    logger.info(f"{self.name}: '1+0' badge yok, ManuelAdet input kullanılıyor")
                    try:
                        # Önce input'u bul
                        manuel_input = self.driver.find_element(
                            By.CSS_SELECTOR,
                            "#search-detay .manuel-adet input[name='ManuelAdet'], "
                            ".siparis-detay-modal .manuel-adet input[name='ManuelAdet'], "
                            "input[name='ManuelAdet']"
                        )

                        # Temizle ve 1 yaz
                        manuel_input.clear()
                        manuel_input.send_keys("1")
                        manuel_input.send_keys(Keys.TAB)  # Focus'u kaybettir, fiyat güncellensin

                        logger.info(f"{self.name}: ManuelAdet = 1 ayarlandı (send_keys)")
                        time.sleep(1.0)  # Fiyat güncellemesi için bekle
                    except Exception as e:
                        logger.debug(f"{self.name}: ManuelAdet input bulunamadı: {e}")

                        # Son çare: Sayısal input alanını bul
                        try:
                            num_input = self.driver.find_element(
                                By.CSS_SELECTOR,
                                "#search-detay input[type='number'], "
                                ".siparis-detay-modal input[type='number']"
                            )
                            num_input.clear()
                            num_input.send_keys("1")
                            num_input.send_keys(Keys.TAB)
                            logger.info(f"{self.name}: Sayısal input = 1 ayarlandı")
                            time.sleep(1.0)
                        except Exception as e2:
                            logger.debug(f"{self.name}: Sayısal input da bulunamadı: {e2}")

            except Exception as e:
                logger.debug(f"{self.name}: Adet-box tıklanamadı: {e}")

            # Fiyatın stabilize olmasını bekle (popup tam yüklensin, fiyat güncellenmeli)
            time.sleep(1.0)

            # ÖNCELİK 1: Popup içindeki .siparis-detay-bilgiler .afternetprice span'ı
            # Bu her zaman doğru KDV Dahil Birim Fiyatını gösterir (MF seçimine bağlı değil)
            try:
                # #search-detay .siparis-detay-bilgiler içindeki afternetprice (en güvenilir)
                afternetprice = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "#search-detay .siparis-detay-bilgiler .afternetprice"
                )
                price_text = afternetprice.text.strip()
                if price_text:
                    price_text = price_text.replace("₺", "").strip()
                    price_text = price_text.replace(".", "").replace(",", ".")
                    price = float(price_text)
                    if 1 <= price <= 50000:
                        logger.info(f"{self.name}: KDV Dahil Birim Fiyat (#search-detay .siparis-detay-bilgiler .afternetprice): {price} TL")
                        return price
            except Exception as e:
                logger.debug(f"{self.name}: #search-detay .siparis-detay-bilgiler .afternetprice bulunamadı: {e}")

            # ÖNCELİK 2: .siparis-detay-bilgiler .afternetprice (yedek)
            try:
                afternetprice = self.driver.find_element(
                    By.CSS_SELECTOR,
                    ".siparis-detay-bilgiler .afternetprice"
                )
                price_text = afternetprice.text.strip()
                if price_text:
                    price_text = price_text.replace("₺", "").strip()
                    price_text = price_text.replace(".", "").replace(",", ".")
                    price = float(price_text)
                    if 1 <= price <= 50000:
                        logger.info(f"{self.name}: KDV Dahil Birim Fiyat (.siparis-detay-bilgiler .afternetprice): {price} TL")
                        return price
            except Exception as e:
                logger.debug(f"{self.name}: .siparis-detay-bilgiler .afternetprice bulunamadı: {e}")

            # ÖNCELİK 3: Popup içindeki .grosstotal span'ı (yedek - KDV Dahil Genel Toplam)
            try:
                grosstotal = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "#search-detay .grosstotal, .siparis-detay-bilgiler .grosstotal"
                )
                price_text = grosstotal.text.strip()
                if price_text:
                    price_text = price_text.replace("₺", "").strip()
                    price_text = price_text.replace(".", "").replace(",", ".")
                    price = float(price_text)
                    if 1 <= price <= 50000:
                        logger.info(f"{self.name}: KDV Dahil Birim Fiyat (.grosstotal): {price} TL")
                        return price
            except Exception as e:
                logger.debug(f"{self.name}: .grosstotal bulunamadı: {e}")

            # ÖNCELİK 4: Depocu Fiyatı + KDV hesapla (son çare)
            try:
                sales_price = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "#search-detay .sales-price, .siparis-detay-bilgiler .sales-price"
                )
                price_text = sales_price.text.strip()
                if price_text:
                    price_text = price_text.replace("₺", "").strip()
                    price_text = price_text.replace(".", "").replace(",", ".")
                    depocu_fiyat = float(price_text)
                    # %10 KDV ekle (varsayılan)
                    kdv_dahil = depocu_fiyat * 1.10
                    if 1 <= kdv_dahil <= 50000:
                        logger.info(f"{self.name}: KDV Dahil Birim Fiyat (Depocu {depocu_fiyat} + %10 KDV): {kdv_dahil:.2f} TL")
                        return round(kdv_dahil, 2)
            except Exception as e:
                logger.debug(f"{self.name}: .sales-price bulunamadı: {e}")

            logger.debug(f"{self.name}: KDV Dahil fiyat bulunamadı")
            return None

        except Exception as e:
            logger.error(f"{self.name}: Fiyat okuma hatası: {e}")
            return None

    def check_stock_status(self):
        """Sancak Ecza'da stok durumunu kontrol et

        Öncelik sırası:
        1. "Sepete Ekle" butonu → STOKTA VAR
        2. "Bakiye Al" butonu → STOKTA YOK
        3. "Satış Temsilciniz" mesajı → DEPOYU ARA
        4. Yeşil/Kırmızı nokta kontrolleri (yedek)

        Returns:
            dict: {
                "stok_var": bool,
                "mesaj": str,
                "detay": str,
                "fiyat": float or None,
                "sart": str or None,
                "satis_kosullari": list
            }
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            # ÖNCELİKLE: Önceki popup'ı kapat (varsa)
            try:
                close_button = self.driver.find_element(By.XPATH,
                    "//button[contains(@class, 'close')] | //span[contains(@class, 'close')] | //a[contains(text(), '×')]")
                close_button.click()
                logger.debug(f"{self.name}: Önceki popup kapatıldı")
                time.sleep(0.15)
            except:
                pass

            # ESC tuşu ile kapat (yedek)
            try:
                actions = ActionChains(self.driver)
                actions.send_keys(Keys.ESCAPE).perform()
                time.sleep(0.15)
            except:
                pass

            # Arama sonucundaki ilk satıra tıkla (YENİ popup açılsın)
            try:
                first_row = self.driver.find_element(By.XPATH,
                    "//table//tbody//tr[1] | //div[contains(@class, 'product-item')][1] | //div[@class='product-row'][1]")
                first_row.click()
                logger.debug(f"{self.name}: İlk satıra tıklandı, YENİ popup açılıyor...")
                time.sleep(1)
            except Exception as e:
                logger.warning(f"{self.name}: İlk satıra tıklanamadı: {e}")
                pass

            time.sleep(0.3)

            # Satış koşullarını al (içinde get_depo_price çağrılıyor)
            # NOT: get_depo_price ayrıca çağırmıyoruz çünkü get_satis_kosullari zaten çağırıyor
            satis_kosullari = self.get_satis_kosullari()

            # Fiyatı satış koşullarından al (1 adetlik fiyat)
            depo_price = None
            if satis_kosullari:
                # İlk koşul (1 adet) fiyatını al
                for k in satis_kosullari:
                    if k.get("mf", 0) == 0:
                        depo_price = k.get("birim_fiyat")
                        break
                if depo_price is None and satis_kosullari:
                    depo_price = satis_kosullari[0].get("birim_fiyat")

            # Önceden alınmış satis_kosullari'nı kullan (tekrar sorgu yapma)
            en_iyi_mf = self.get_en_iyi_mf(satis_kosullari)
            sart = en_iyi_mf["oran"] if en_iyi_mf else None

            if sart:
                logger.info(f"{self.name}: 📦 Mal fazlası bulundu: {sart}")

            # Sayfa içeriğini al (YENİ popup açıldıktan sonra)
            page_source = self.driver.page_source

            # POPUP içindeki butonları kontrol et
            # 1. ÖNCELİK: "Bakiye Al" butonu (POPUP içinde) → STOKTA YOK
            try:
                bakiye_al = self.driver.find_element(By.XPATH,
                    "//div[contains(@class, 'siparis-detay-modal') or @id='search-detay']//button[contains(@class, 'addbackorder') and contains(@style, 'display: block')]")
                if bakiye_al and bakiye_al.is_displayed():
                    logger.info(f"{self.name}: ✗ 'Bakiye Al' butonu bulundu (popup içinde) - STOKTA YOK")
                    return {
                        "stok_var": False,
                        "mesaj": "Stokta Yok",
                        "detay": "Bakiye Al butonu mevcut (popup)",
                        "fiyat": depo_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except Exception as e:
                logger.debug(f"{self.name}: 'Bakiye Al' butonu bulunamadı: {e}")
                pass

            # 2. "Sepete Ekle" butonu (POPUP içinde) → STOKTA VAR
            try:
                sepete_ekle = self.driver.find_element(By.XPATH,
                    "//div[contains(@class, 'siparis-detay-modal') or @id='search-detay']//button[contains(@class, 'addtobasket') and contains(@style, 'display: block')]")
                if sepete_ekle and sepete_ekle.is_displayed():
                    logger.info(f"{self.name}: ✓ 'Sepete Ekle' butonu bulundu (popup içinde) - STOKTA VAR")
                    return {
                        "stok_var": True,
                        "mesaj": "Stokta Var",
                        "detay": "Sepete Ekle butonu mevcut (popup)",
                        "fiyat": depo_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except Exception as e:
                logger.debug(f"{self.name}: 'Sepete Ekle' butonu bulunamadı: {e}")
                pass

            # 3. "Satış Temsilciniz" mesajı → DEPOYU ARA
            if "Lütfen Satış Temsilciniz İle Görüşün" in page_source or \
               "Satış Temsilciniz" in page_source or \
               "satış temsilciniz" in page_source.lower():
                logger.info(f"{self.name}: ⚠ 'Satış Temsilciniz' mesajı - DEPOYU ARA")
                return {
                    "stok_var": False,
                    "mesaj": "Depoyu Ara",
                    "detay": "Satış temsilcisi ile görüşülmeli",
                    "fiyat": depo_price,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # 4. Yeşil nokta kontrolü (yedek) → STOKTA VAR
            try:
                green_badge = self.driver.find_element(By.CSS_SELECTOR,
                    "span.badge-sm.active")
                if green_badge:
                    logger.info(f"{self.name}: ✓ Yeşil nokta bulundu (yedek kontrol) - STOKTA VAR")
                    return {
                        "stok_var": True,
                        "mesaj": "Stokta Var",
                        "detay": "Yeşil nokta (badge-sm active)",
                        "fiyat": depo_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except Exception as e:
                logger.debug(f"{self.name}: Yeşil nokta bulunamadı: {e}")
                pass

            # 5. Kırmızı nokta kontrolü (yedek) → STOKTA YOK
            try:
                red_badge = self.driver.find_element(By.CSS_SELECTOR,
                    "span.badge-sm:not(.active)")
                if red_badge:
                    logger.info(f"{self.name}: ✗ Kırmızı nokta bulundu (yedek kontrol) - STOKTA YOK")
                    return {
                        "stok_var": False,
                        "mesaj": "Stokta Yok",
                        "detay": "Kırmızı nokta (badge-sm)",
                        "fiyat": depo_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except Exception as e:
                logger.debug(f"{self.name}: Kırmızı nokta bulunamadı: {e}")
                pass

            # 6. "Ürün bulunamadı" mesajı
            if "ürün bulunamadı" in page_source.lower() or \
               "sonuç bulunamadı" in page_source.lower() or \
               "kayıt bulunamadı" in page_source.lower():
                logger.info(f"{self.name}: ✗ Ürün bulunamadı")
                return {
                    "stok_var": False,
                    "mesaj": "Ürün Bulunamadı",
                    "detay": "Ürün bulunamadı mesajı",
                    "fiyat": None,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # Hiçbir durum tespit edilemedi - Varsayılan
            logger.warning(f"{self.name}: ⚠ Durum belirlenemedi")
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

    def set_order_quantity(self, quantity):
        """Sancak Ecza'da sipariş miktarını ayarla (popup içinde)

        Args:
            quantity: Sipariş adedi

        Returns:
            bool: İşlem başarılı mı
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Sipariş adedi ayarlanıyor: {quantity}")
            time.sleep(0.5)  # Popup'ın açılması için bekle

            # Popup içindeki adet input alanını bul
            # Sancak'ta popup açıldığında ortada bir input var
            input_field = None

            # Yöntem 1: Popup içindeki visible input (type='number' veya visible text input)
            try:
                # Popup modal içindeki input'ları bul
                popup_inputs = self.driver.find_elements(By.XPATH,
                    "//div[contains(@class, 'modal') and contains(@style, 'display: block')]//input[@type='number'] | "
                    "//div[contains(@class, 'modal') and contains(@style, 'display: block')]//input[@type='text']")

                for inp in popup_inputs:
                    if inp.is_displayed() and inp.is_enabled():
                        # Placeholder'ı kontrol et
                        placeholder = inp.get_attribute("placeholder") or ""
                        name = inp.get_attribute("name") or ""

                        # Manuel adet veya quantity içeren input
                        if "adet" in placeholder.lower() or "manuel" in name.lower() or "quantity" in name.lower():
                            input_field = inp
                            logger.debug(f"{self.name}: Adet input'u bulundu (popup modal)")
                            break

                # Hala bulunamadıysa ilk visible input'u al
                if not input_field and popup_inputs:
                    for inp in popup_inputs:
                        if inp.is_displayed() and inp.is_enabled():
                            input_field = inp
                            logger.debug(f"{self.name}: İlk visible input alındı")
                            break

            except Exception as e:
                logger.debug(f"{self.name}: Modal input bulunamadı: {e}")

            # Yöntem 2: Sayfa içindeki en son (en üstte) görünen input
            if not input_field:
                try:
                    all_inputs = self.driver.find_elements(By.XPATH,
                        "//input[@type='number' or @type='text']")

                    # Visible ve enabled olanları filtrele
                    visible_inputs = []
                    for inp in all_inputs:
                        try:
                            if inp.is_displayed() and inp.is_enabled():
                                visible_inputs.append(inp)
                        except:
                            pass

                    # En son eklenen (popup içindeki) visible input
                    if visible_inputs:
                        input_field = visible_inputs[-1]
                        logger.debug(f"{self.name}: Son visible input alındı")

                except Exception as e:
                    logger.debug(f"{self.name}: Visible input bulunamadı: {e}")

            # Yöntem 3: JavaScript ile aktif element
            if not input_field:
                try:
                    active_element = self.driver.execute_script("return document.activeElement")
                    if active_element and active_element.tag_name == "input":
                        input_field = active_element
                        logger.debug(f"{self.name}: Aktif element input alındı")
                except Exception as e:
                    logger.debug(f"{self.name}: Aktif element alınamadı: {e}")

            if not input_field:
                logger.warning(f"{self.name}: Sipariş miktar alanı bulunamadı")
                return False

            # Elementi görünür hale getir (scroll) - sayfanın altında kalmasın
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_field)
                time.sleep(0.3)
                logger.debug(f"{self.name}: Element scroll ile görünür hale getirildi")
            except Exception as e:
                logger.debug(f"{self.name}: Scroll yapılamadı: {e}")

            # Input alanına değer yaz
            try:
                # JavaScript ile değer yaz (daha güvenilir)
                self.driver.execute_script("""
                    arguments[0].value = '';
                    arguments[0].value = arguments[1];
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, input_field, str(quantity))

                logger.info(f"{self.name}: ✓ Sipariş adedi {quantity} olarak ayarlandı (JavaScript)")
                return True

            except Exception as e:
                # JavaScript başarısız olursa, klasik yöntem dene
                logger.debug(f"{self.name}: JavaScript başarısız, klasik yöntem deneniyor: {e}")

                input_field.click()
                time.sleep(0.1)
                input_field.send_keys(Keys.CONTROL, "a")
                input_field.send_keys(Keys.DELETE)
                input_field.send_keys(str(quantity))

                logger.info(f"{self.name}: ✓ Sipariş adedi {quantity} olarak ayarlandı (Send keys)")
                return True

        except Exception as e:
            logger.error(f"{self.name}: Sipariş adedi ayarlanırken hata: {e}")
            return False

    def get_satis_kosullari(self):
        """Sancak Ecza'dan satış koşulları tablosunu oku (MF, iskonto vb.)

        Sancak yapısı:
        - Popup panel: #search-detay içinde
        - MF seçenekleri: div.adetler içindeki span.table-adet
        - MF formatı: "1+0" (MF yok), "7+1" (7 al 1 bedava)
        - Fiyat: .afternetprice veya .grosstotal (KDV dahil fiyat)
        - KDV oranı: tooltip'te "(%10)" formatında

        Returns:
            list: [{"sart": str, "birim_fiyat": float, "min_adet": int, "mf": int, "kdv_orani": float}, ...]
        """
        try:
            kosullar = []
            mf_secenekleri = []  # Sadece MF seçeneklerini topla, fiyat sonra hesaplanacak

            # Popup panel içindeki MF badge'lerini bul
            # #search-detay .adetler içindeki span.table-adet elementleri
            try:
                # Popup içindeki adetler div'ini bul
                adetler_div = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "#search-detay .adetler, .siparis-detay-modal .adetler"
                )

                # Tüm table-adet span'larını bul
                mf_spans = adetler_div.find_elements(
                    By.CSS_SELECTOR,
                    "span.table-adet"
                )

                for span in mf_spans:
                    try:
                        # Görünür olmayan (visibility: hidden) span'ları atla
                        style = span.get_attribute("style") or ""
                        if "hidden" in style.lower():
                            continue

                        # Span text'i al (örn: "1+0", "7+1")
                        mf_text = span.text.strip()
                        if not mf_text or "+" not in mf_text:
                            continue

                        # MF'yi parse et: "7+1" -> min_adet=7, mf=1
                        parts = mf_text.replace(" ", "").split("+")
                        if len(parts) != 2:
                            continue

                        try:
                            min_adet = int(parts[0])
                            mf = int(parts[1])
                        except ValueError:
                            continue

                        # KDV oranını tooltip'ten al
                        tooltip = span.get_attribute("data-original-title") or ""
                        kdv_orani = 10  # varsayılan %10

                        if tooltip:
                            # KDV oranını parse et: "(%10)" veya "(%8)" veya "(%1)"
                            kdv_match = re.search(r'\(%(\d+)\)', tooltip)
                            if kdv_match:
                                kdv_orani = int(kdv_match.group(1))

                        # MF seçeneğini kaydet (fiyat sonra hesaplanacak)
                        mf_secenekleri.append({
                            "min_adet": min_adet,
                            "mf": mf,
                            "kdv_orani": kdv_orani
                        })

                    except Exception as e:
                        logger.debug(f"{self.name}: MF span parse hatası: {e}")
                        continue

            except Exception as e:
                logger.debug(f"{self.name}: Adetler div bulunamadı: {e}")

            # KDV Dahil Birim Fiyatını al (1 adetlik fiyat) - get_depo_price() güvenilir kaynak
            birim_fiyat = self.get_depo_price()

            if birim_fiyat and birim_fiyat > 0:
                logger.info(f"{self.name}: Birim fiyat (.afternetprice): {birim_fiyat} TL")

                # 1. "1" satırını ekle (tek birim fiyatı)
                kosullar.append({
                    "sart": "1",
                    "birim_fiyat": round(birim_fiyat, 2),
                    "min_adet": 1,
                    "mf": 0,
                    "kdv_orani": 10
                })

                # 2. MF seçenekleri için fiyatları birim fiyattan hesapla
                # Örn: 7+1 = 7 birim öde, 8 birim al -> birim fiyat = (7 * birim_fiyat) / 8
                for mf_opt in mf_secenekleri:
                    min_adet = mf_opt["min_adet"]
                    mf = mf_opt["mf"]
                    kdv_orani = mf_opt.get("kdv_orani", 10)

                    # 1+0 zaten eklendi, tekrar ekleme
                    if min_adet == 1 and mf == 0:
                        continue

                    if mf > 0:
                        # MF var: Ödenen adet × birim fiyat / toplam adet
                        toplam_adet = min_adet + mf
                        odenen_adet = min_adet
                        hesaplanan_birim = (odenen_adet * birim_fiyat) / toplam_adet
                    else:
                        # MF yok: Direkt birim fiyat
                        hesaplanan_birim = birim_fiyat

                    kosullar.append({
                        "sart": f"{min_adet}+{mf}" if mf > 0 else str(min_adet),
                        "birim_fiyat": round(hesaplanan_birim, 2),
                        "min_adet": min_adet,
                        "mf": mf,
                        "kdv_orani": kdv_orani
                    })
                    logger.debug(f"{self.name}: {min_adet}+{mf} hesaplandı: {hesaplanan_birim:.2f} TL")

            if kosullar:
                logger.info(f"{self.name}: {len(kosullar)} satış koşulu bulundu")
                for k in kosullar:
                    logger.debug(f"  - {k['sart']}: {k['birim_fiyat']} TL")

            return kosullar

        except Exception as e:
            logger.error(f"{self.name}: Satış koşulları okuma hatası: {e}")
            return []

    def get_en_iyi_mf(self, kosullar=None):
        """En iyi mal fazlası koşulunu döndür

        Args:
            kosullar: Önceden alınmış satış koşulları (opsiyonel)

        Returns:
            dict: {"min_adet": int, "mf": int, "oran": str} veya None
        """
        if kosullar is None:
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
