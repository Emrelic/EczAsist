"""
Alliance deposu sorgulama modülü
"""
import time
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .base_depo import BaseDepo
from ..utils import logger, DEPOLAR


class AllianceDepo(BaseDepo):
    """Alliance deposu sorgulama class'ı"""

    def __init__(self):
        config = DEPOLAR["alliance"]
        super().__init__(config["name"], config["url"], config["elements"])

    def login(self, eczane_kodu, username, password):
        """Alliance'a giriş yap

        Args:
            eczane_kodu: Eczane kodu
            username: Kullanıcı adı
            password: Şifre

        Returns:
            bool: Giriş başarılı mı
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Giriş yapılıyor...")

            # Eczane Kodu
            eczane_input = self.wait_for_element(By.ID, "pharmacyCode")
            if not eczane_input:
                return False

            eczane_input.clear()
            eczane_input.send_keys(eczane_kodu)
            time.sleep(1.5)  # Eczane kodu girince kullanıcı adı alanının açılması için bekle

            # Kullanıcı adı (readonly olabilir, JavaScript ile kaldırmalıyız)
            username_input = self.driver.find_element(By.ID, "Customer_username")

            # readonly attribute'ü kaldır
            self.driver.execute_script("arguments[0].removeAttribute('readonly')", username_input)

            username_input.clear()
            username_input.send_keys(username)
            time.sleep(0.5)

            # Şifre
            password_input = self.driver.find_element(By.ID, "Customer_password")
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(0.5)

            # Giriş butonuna tıkla
            password_input.send_keys(Keys.ENTER)
            logger.debug(f"{self.name}: ENTER gönderildi, sayfa yükleniyor...")

            # Giriş kontrolü - sayfa yüklenmesini bekle
            time.sleep(2.5)

            # Çoklu oturum kontrolü - "Aktif Oturumları Kapat" butonu var mı?
            try:
                logger.debug(f"{self.name}: Çoklu oturum kontrolü yapılıyor...")
                close_sessions_button = self.wait_for_element(
                    By.XPATH,
                    "//a[contains(text(), 'Aktif Oturumları Kapat')]",
                    timeout=3
                )

                if close_sessions_button:
                    logger.info(f"{self.name}: ⚠️ Çoklu oturum uyarısı algılandı!")

                    # 1. tıklama
                    logger.debug(f"{self.name}: 'Aktif Oturumları Kapat' - 1. tıklama")
                    close_sessions_button.click()
                    time.sleep(0.5)

                    # 2. tıklama (elementi yeniden bul - stale element hatası olmasın)
                    try:
                        logger.debug(f"{self.name}: 'Aktif Oturumları Kapat' - 2. tıklama")
                        close_sessions_button = self.driver.find_element(By.XPATH,
                            "//a[contains(text(), 'Aktif Oturumları Kapat')]")
                        close_sessions_button.click()
                        logger.info(f"{self.name}: ✓ Aktif oturumlar kapatma isteği gönderildi (2 kez)")
                    except Exception as e:
                        logger.warning(f"{self.name}: 2. tıklama başarısız (büyük ihtimalle sayfa değişti): {e}")

                    # Ana sayfanın yüklenmesini bekle
                    logger.debug(f"{self.name}: Ana sayfa yüklenene kadar bekleniyor...")
                    time.sleep(5)  # 4 → 5 saniye (daha fazla süre)

                    # "Sipariş Ver" butonunu bekle ve tıkla
                    logger.debug(f"{self.name}: 'Sipariş Ver' butonu aranıyor...")
                    siparis_ver_link = None

                    # Birden fazla XPath dene
                    xpaths = [
                        "//a[contains(@href, '/Sales/QuickOrder')]",
                        "//a[contains(text(), 'Sipariş Ver')]",
                        "//a[contains(., 'Sipariş Ver')]",
                        "//a[@href='/Sales/QuickOrder']"
                    ]

                    for xpath in xpaths:
                        try:
                            siparis_ver_link = self.wait_for_element(By.XPATH, xpath, timeout=5)
                            if siparis_ver_link:
                                logger.debug(f"{self.name}: 'Sipariş Ver' bulundu (XPath: {xpath})")
                                break
                        except:
                            continue

                    if siparis_ver_link:
                        logger.info(f"{self.name}: ✓ 'Sipariş Ver' butonu bulundu, tıklanıyor...")
                        try:
                            # Önce normal tıklama dene
                            siparis_ver_link.click()
                            logger.debug(f"{self.name}: Normal tıklama başarılı")
                        except Exception as click_err:
                            # Normal tıklama çalışmazsa JavaScript ile tıkla
                            logger.debug(f"{self.name}: Normal tıklama başarısız, JavaScript deneniyor: {click_err}")
                            self.driver.execute_script("arguments[0].click();", siparis_ver_link)
                            logger.debug(f"{self.name}: JavaScript tıklama başarılı")

                        time.sleep(2)
                        logger.debug(f"{self.name}: 'Sipariş Ver' sayfası yükleniyor...")

                        # Popup'ı kapat (çoklu oturum sonrası)
                        try:
                            logger.debug(f"{self.name}: Popup kontrol ediliyor (çoklu oturum sonrası)...")
                            close_buttons = self.driver.find_elements(By.CLASS_NAME, "modal-v2close")
                            for btn in close_buttons:
                                if btn.is_displayed():
                                    btn.click()
                                    time.sleep(0.3)
                            self.driver.execute_script("""
                                var modals = document.querySelectorAll('.modal-v2, .modal-v2area');
                                modals.forEach(function(modal) { modal.style.display = 'none'; });
                            """)
                        except:
                            pass
                    else:
                        logger.warning(f"{self.name}: 'Sipariş Ver' butonu bulunamadı, direkt URL'ye gidiliyor")
                        self.driver.get(self.url)  # self.url zaten /Sales/QuickOrder
                        time.sleep(2)

                        # Popup'ı kapat (çoklu oturum - direkt URL)
                        try:
                            logger.debug(f"{self.name}: Popup kontrol ediliyor (çoklu oturum - direkt URL)...")
                            close_buttons = self.driver.find_elements(By.CLASS_NAME, "modal-v2close")
                            for btn in close_buttons:
                                if btn.is_displayed():
                                    btn.click()
                                    time.sleep(0.3)
                            self.driver.execute_script("""
                                var modals = document.querySelectorAll('.modal-v2, .modal-v2area');
                                modals.forEach(function(modal) { modal.style.display = 'none'; });
                            """)
                        except:
                            pass
                else:
                    logger.debug(f"{self.name}: Çoklu oturum butonu bulunamadı (normal akış)")

            except Exception as close_ex:
                # Çoklu oturum uyarısı yok (timeout veya element yok) - normal akış
                logger.debug(f"{self.name}: Çoklu oturum uyarısı yok (normal giriş)")

                # Şifre kaydetme popup'ını kapat (eğer açıldıysa)
                try:
                    self.driver.execute_script("""
                        // Chrome'un şifre kaydetme popup'ını kapat
                        var savePasswordButton = document.querySelector('button[aria-label*="Hiçbir zaman"]');
                        if (savePasswordButton) savePasswordButton.click();
                    """)
                except:
                    pass

                # "Sipariş Ver" sayfasına git (normal akış)
                logger.debug(f"{self.name}: 'Sipariş Ver' sayfasına gidiliyor (normal akış)...")
                siparis_ver_link = None

                # Birden fazla XPath dene
                xpaths = [
                    "//a[contains(@href, '/Sales/QuickOrder')]",
                    "//a[contains(text(), 'Sipariş Ver')]",
                    "//a[contains(., 'Sipariş Ver')]",
                    "//a[@href='/Sales/QuickOrder']"
                ]

                for xpath in xpaths:
                    try:
                        siparis_ver_link = self.wait_for_element(By.XPATH, xpath, timeout=3)
                        if siparis_ver_link:
                            logger.debug(f"{self.name}: 'Sipariş Ver' bulundu (normal akış - XPath: {xpath})")
                            break
                    except:
                        continue

                if siparis_ver_link:
                    logger.info(f"{self.name}: ✓ 'Sipariş Ver' butonu bulundu, tıklanıyor...")
                    try:
                        siparis_ver_link.click()
                        logger.debug(f"{self.name}: Normal tıklama başarılı")
                    except Exception as click_err:
                        logger.debug(f"{self.name}: Normal tıklama başarısız, JavaScript deneniyor: {click_err}")
                        self.driver.execute_script("arguments[0].click();", siparis_ver_link)
                        logger.debug(f"{self.name}: JavaScript tıklama başarılı")

                    time.sleep(2)

                    # Popup'ı kapat (normal akış)
                    try:
                        logger.debug(f"{self.name}: Popup kontrol ediliyor (normal akış)...")
                        close_buttons = self.driver.find_elements(By.CLASS_NAME, "modal-v2close")
                        for btn in close_buttons:
                            if btn.is_displayed():
                                btn.click()
                                time.sleep(0.3)
                        self.driver.execute_script("""
                            var modals = document.querySelectorAll('.modal-v2, .modal-v2area');
                            modals.forEach(function(modal) { modal.style.display = 'none'; });
                        """)
                    except:
                        pass
                else:
                    # Buton bulunamadıysa direkt URL'ye git
                    logger.warning(f"{self.name}: 'Sipariş Ver' butonu bulunamadı, direkt URL'ye gidiliyor")
                    self.driver.get(self.url)  # self.url zaten /Sales/QuickOrder
                    time.sleep(2)

                    # Popup'ı kapat (direkt URL)
                    try:
                        logger.debug(f"{self.name}: Popup kontrol ediliyor (direkt URL)...")
                        close_buttons = self.driver.find_elements(By.CLASS_NAME, "modal-v2close")
                        for btn in close_buttons:
                            if btn.is_displayed():
                                btn.click()
                                time.sleep(0.3)
                        self.driver.execute_script("""
                            var modals = document.querySelectorAll('.modal-v2, .modal-v2area');
                            modals.forEach(function(modal) { modal.style.display = 'none'; });
                        """)
                    except:
                        pass

            # Popup'ları kapat (E-posta doğrulama, Onaylanmamış firma siparişi vs.)
            logger.debug(f"{self.name}: Popup'lar kontrol ediliyor...")
            try:
                # Yöntem 0: "Onaylanmamış firma siparişi" popup'ını kapat (Hayır butonu)
                hayir_buttons = self.driver.find_elements(By.XPATH,
                    "//button[contains(text(), 'Hayır')] | //a[contains(text(), 'Hayır')]")
                for btn in hayir_buttons:
                    try:
                        if btn.is_displayed():
                            btn.click()
                            logger.info(f"{self.name}: 'Onaylanmamış firma siparişi' popup'ı kapatıldı (Hayır)")
                            time.sleep(0.5)
                            break
                    except:
                        pass

                # Yöntem 1: modal-v2close butonunu bul ve tıkla
                close_buttons = self.driver.find_elements(By.CLASS_NAME, "modal-v2close")
                if close_buttons:
                    logger.info(f"{self.name}: E-posta/kampanya popup'ı bulundu, kapatılıyor...")
                    for btn in close_buttons:
                        try:
                            if btn.is_displayed():
                                btn.click()
                                time.sleep(0.5)
                                logger.debug(f"{self.name}: Popup kapatma butonu tıklandı")
                        except:
                            pass

                # Yöntem 2: JavaScript ile tüm modal'ları kapat
                self.driver.execute_script("""
                    // "Hayır" butonunu bul ve tıkla (Onaylanmamış firma siparişi popup'ı)
                    var hayirBtn = document.querySelector('button.swal2-deny, button.swal2-cancel');
                    if (hayirBtn && hayirBtn.offsetParent !== null) {
                        hayirBtn.click();
                    }

                    // Tüm modal-v2 ve modal-v2area'ları gizle
                    var modals = document.querySelectorAll('.modal-v2, .modal-v2area');
                    modals.forEach(function(modal) {
                        modal.style.display = 'none';
                    });

                    // SweetAlert2 popup'ları kapat
                    var swalContainers = document.querySelectorAll('.swal2-container');
                    swalContainers.forEach(function(container) {
                        container.remove();
                    });

                    // Bootstrap modal'ları da kapat
                    if (typeof $.fn.modal !== 'undefined') {
                        $('.modal').modal('hide');
                    }
                """)
                logger.debug(f"{self.name}: JavaScript ile modal'lar kapatıldı")
                time.sleep(0.5)
            except Exception as popup_err:
                logger.debug(f"{self.name}: Popup kapatma sırasında hata (sorun değil): {popup_err}")

            # SON KONTROL: Arama kutusu var mı? (giriş başarılı kontrolü)
            logger.debug(f"{self.name}: Giriş doğrulaması yapılıyor (searchText)...")
            search_box = self.wait_for_element(By.ID, "searchText", timeout=8)

            if search_box:
                logger.info(f"{self.name}: ✅ Giriş başarılı! (Arama kutusu bulundu)")
                return True

            # Hala login sayfasında mıyız kontrol et
            try:
                login_form = self.driver.find_element(By.ID, "pharmacyCode")
                if login_form:
                    logger.error(f"{self.name}: ❌ Giriş başarısız - hala login sayfasında!")
                    return False
            except:
                pass

            # Arama kutusu yoksa ama login formu da yoksa - belirsiz durum
            logger.warning(f"{self.name}: ⚠️ Giriş durumu belirsiz (arama kutusu bulunamadı)")
            return False

        except Exception as e:
            logger.error(f"{self.name}: Giriş hatası: {e}")
            return False

    def search_barcode(self, barcode):
        """Alliance'da barkod ara

        Args:
            barcode: Aranacak barkod

        Returns:
            bool: Arama başarılı mı (ürün bulunduysa True)
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Önce doğru tab'a geç
                self.switch_to_tab()

                # Session geçerli mi kontrol et
                try:
                    _ = self.driver.current_url
                except Exception as session_err:
                    logger.warning(f"{self.name}: Session geçersiz, yeniden bağlanılıyor... ({session_err})")
                    # Tab'ı yeniden oluştur
                    self.tab_handle = None
                    self.switch_to_tab()
                    time.sleep(1)
                    continue

                logger.info(f"{self.name}: Barkod aranıyor: {barcode} (deneme {attempt + 1}/{max_retries})")

                # Popup'ları kapat (e-posta, kampanya vb.)
                try:
                    self._close_popups()
                except Exception as popup_err:
                    logger.debug(f"{self.name}: Popup kapatma sırasında hata (görmezden geliniyor): {popup_err}")

                # Ana frame'e dön (iframe içinde kalmış olabiliriz)
                try:
                    self.driver.switch_to.default_content()
                except Exception:
                    pass

                # Arama kutusunu bul
                search_input = self.wait_for_element(By.ID, self.elements["search_input"], timeout=5)
                if not search_input:
                    # Arama kutusu bulunamadı - sayfa yenilenmeye çalışılacak
                    if attempt < max_retries - 1:
                        logger.warning(f"{self.name}: Arama kutusu bulunamadı, sayfa yenileniyor...")
                        self.driver.get(self.url)
                        time.sleep(2)
                        continue
                    return False

                # Arama kutusunu temizle ve barkodu yaz
                try:
                    search_input.click()
                except Exception:
                    # Element tıklanabilir değilse JavaScript ile focus yap
                    self.driver.execute_script("arguments[0].focus();", search_input)

                search_input.clear()
                time.sleep(0.3)
                search_input.send_keys(barcode)
                search_input.send_keys(Keys.ENTER)

                # Sonuçların yüklenmesi için bekle
                time.sleep(2)

                # DOĞRULAMA: "Ürün Bulunamadı" mesajı var mı kontrol et
                try:
                    searched_items = self.driver.find_element(By.ID, "searchedItems")
                    items_text = searched_items.text.strip()

                    if "ürün bulunamadı" in items_text.lower():
                        logger.info(f"{self.name}: Ürün bulunamadı: {barcode}")
                        return False

                    # searchedItems içinde ürün satırı var mı kontrol et
                    # Barkod, satırın data-itemstring veya title attribute'unda bulunur
                    try:
                        rows = searched_items.find_elements(By.TAG_NAME, "tr")
                        if not rows:
                            logger.warning(f"{self.name}: searchedItems boş, ürün bulunamadı")
                            return False

                        # İlk satırda barkod var mı kontrol et (title attribute veya data attribute)
                        first_row = rows[0]
                        row_html = first_row.get_attribute("outerHTML")
                        if barcode in row_html:
                            logger.info(f"{self.name}: Barkod doğrulandı (satır verisi): {barcode}")
                        else:
                            # Satır var ama barkod eşleşmiyor - eski veri olabilir
                            logger.warning(f"{self.name}: Barkod satır verisinde bulunamadı: {barcode}")
                            return False
                    except Exception as e:
                        logger.debug(f"{self.name}: Satır doğrulama hatası (görmezden geliniyor): {e}")

                except:
                    pass

                return True

            except Exception as e:
                error_msg = str(e).lower()
                # Session veya frame hataları için yeniden deneme
                if any(x in error_msg for x in ["invalid session", "target frame detached", "no such window", "session deleted"]):
                    logger.warning(f"{self.name}: Session/frame hatası, yeniden deneniyor... ({e})")
                    if attempt < max_retries - 1:
                        # Tab'ı sıfırla
                        self.tab_handle = None
                        time.sleep(1)
                        continue
                logger.error(f"{self.name}: Barkod arama hatası: {e}")
                return False

        logger.error(f"{self.name}: Barkod arama {max_retries} denemede başarısız oldu")
        return False

    def _close_popups(self):
        """Alliance sayfasındaki popup'ları kapat"""
        try:
            # Yöntem 0: "Onaylanmamış firma siparişi" popup'ını kapat (Hayır butonu)
            try:
                hayir_buttons = self.driver.find_elements(By.XPATH,
                    "//button[contains(text(), 'Hayır')] | //a[contains(text(), 'Hayır')]")
                for btn in hayir_buttons:
                    try:
                        if btn.is_displayed():
                            btn.click()
                            logger.info(f"{self.name}: 'Onaylanmamış firma siparişi' popup'ı kapatıldı (Hayır)")
                            time.sleep(0.3)
                            break
                    except:
                        pass
            except:
                pass

            # Yöntem 1: modal-v2close butonlarını kapat
            close_buttons = self.driver.find_elements(By.CLASS_NAME, "modal-v2close")
            for btn in close_buttons:
                try:
                    if btn.is_displayed():
                        btn.click()
                        time.sleep(0.3)
                except:
                    pass

            # Yöntem 2: JavaScript ile tüm modal'ları kapat
            self.driver.execute_script("""
                // "Hayır" butonunu bul ve tıkla (Onaylanmamış firma siparişi popup'ı)
                var hayirBtn = document.querySelector('button.swal2-deny, button.swal2-cancel, button[class*="cancel"]');
                if (hayirBtn && hayirBtn.offsetParent !== null) {
                    hayirBtn.click();
                }

                // Modal-v2 popup'ları kapat
                var modals = document.querySelectorAll('.modal-v2, .modal-v2area');
                modals.forEach(function(modal) {
                    modal.style.display = 'none';
                });

                // SweetAlert2 popup'ları kapat
                var swalContainers = document.querySelectorAll('.swal2-container');
                swalContainers.forEach(function(container) {
                    container.remove();
                });

                // Bootstrap modal'ları da kapat
                try {
                    if (typeof $.fn.modal !== 'undefined') {
                        $('.modal').modal('hide');
                    }
                } catch(e) {}

                // Overlay'leri kaldır
                var overlays = document.querySelectorAll('.modal-backdrop, .overlay, .swal2-backdrop-show');
                overlays.forEach(function(overlay) {
                    overlay.remove();
                });
            """)
        except Exception as e:
            logger.debug(f"{self.name}: Popup kapatma hatası: {e}")

    def get_product_name(self):
        """Alliance'dan ürün adını al

        Returns:
            str: Ürün adı veya None
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            product_name = None

            # 1. Yöntem: #itemTitle elementi (en güvenilir)
            # Format: "8680881254680 - URODAY 3 GR 1 SASE"
            try:
                item_title = self.driver.find_element(By.ID, "itemTitle")
                full_text = item_title.text.strip()
                if full_text and " - " in full_text:
                    # Barkodu ayır, sadece ürün adını al
                    product_name = full_text.split(" - ", 1)[1].strip()
                    if product_name:
                        logger.info(f"{self.name}: Ürün adı bulundu (itemTitle): {product_name}")
                        return product_name
            except:
                pass

            # 2. Yöntem: panel-item-title class'ı
            try:
                panel_title = self.driver.find_element(By.CSS_SELECTOR, ".panel-item-title")
                full_text = panel_title.text.strip()
                if full_text and " - " in full_text:
                    product_name = full_text.split(" - ", 1)[1].strip()
                    if product_name:
                        logger.info(f"{self.name}: Ürün adı bulundu (panel-item-title): {product_name}")
                        return product_name
            except:
                pass

            # 3. Yöntem: Sayfa başlığından (title tag)
            try:
                title = self.driver.title
                # Başlık formatları:
                # "Alliance Healthcare - ÜRÜN ADI" veya "ÜRÜN ADI - Alliance Healthcare"
                if " - " in title:
                    parts = title.split(" - ")
                    # Depo adını içermeyen parçayı bul
                    for part in parts:
                        part = part.strip()
                        # Depo adı değilse ürün adı olarak kullan
                        if part and "alliance" not in part.lower() and "healthcare" not in part.lower():
                            logger.info(f"{self.name}: Ürün adı bulundu (title): {part}")
                            return part
            except:
                pass

            logger.warning(f"{self.name}: Ürün adı bulunamadı")
            return None

        except Exception as e:
            logger.error(f"{self.name}: Ürün adı alma hatası: {e}")
            return None

    def get_depo_price(self):
        """Alliance'dan Genel Toplam fiyatını al (KDV dahil)

        Returns:
            float or None: Depocu fiyatı (TL, KDV dahil)
        """
        try:
            self.switch_to_tab()
            time.sleep(0.5)

            import re

            # Yöntem 1: Genel Toplam'dan oku (en güvenilir)
            try:
                genel_toplam = self.driver.find_element(By.ID, "calculeted_grosstotal")
                genel_toplam_text = genel_toplam.text.strip()
                if not genel_toplam_text:
                    genel_toplam_text = genel_toplam.get_attribute("textContent").strip()

                if genel_toplam_text:
                    genel_toplam_clean = genel_toplam_text.replace(".", "").replace(",", ".")
                    price = float(genel_toplam_clean)
                    logger.info(f"{self.name}: Depocu fiyat (Genel Toplam): {price} TL")
                    return price
            except Exception as e:
                logger.debug(f"{self.name}: Genel Toplam okunamadı: {e}")

            # Yöntem 2: Net Tutar + KDV Toplamı
            try:
                net_tutar_elem = self.driver.find_element(By.ID, "calculeted_nettotal")
                kdv_toplam_elem = self.driver.find_element(By.ID, "calculeted_taxtotal")

                net_tutar_text = net_tutar_elem.text.strip() or net_tutar_elem.get_attribute("textContent").strip()
                kdv_toplam_text = kdv_toplam_elem.text.strip() or kdv_toplam_elem.get_attribute("textContent").strip()

                if net_tutar_text and kdv_toplam_text:
                    net_tutar = float(net_tutar_text.replace(".", "").replace(",", "."))
                    kdv_toplam = float(kdv_toplam_text.replace(".", "").replace(",", "."))
                    price = net_tutar + kdv_toplam
                    logger.info(f"{self.name}: Depocu fiyat (Net+KDV): {net_tutar} + {kdv_toplam} = {price} TL")
                    return price
            except Exception as e:
                logger.debug(f"{self.name}: Net Tutar + KDV hesaplanamadı: {e}")

            # Yöntem 3: "Vergi Dahil Depocu Satış Fiyatı" etiketi (fallback)
            try:
                price_label = self.driver.find_element(
                    By.XPATH,
                    "//div[contains(text(), 'Vergi Dahil Depocu Satış Fiyatı')]"
                )
                parent = price_label.find_element(By.XPATH, "..")
                price_element = parent.find_element(By.CSS_SELECTOR, ".text-right")

                price_text = price_element.text.strip()
                price_match = re.search(r'(\d+),(\d+)', price_text)
                if price_match:
                    price = float(f"{price_match.group(1)}.{price_match.group(2)}")
                    logger.info(f"{self.name}: Depocu fiyat (Vergi Dahil etiket): {price} TL")
                    return price
            except Exception as e:
                logger.debug(f"{self.name}: Vergi Dahil etiket bulunamadı: {e}")

            logger.warning(f"{self.name}: Depocu fiyatı hiçbir yöntemle okunamadı")
            return None

        except Exception as e:
            logger.error(f"{self.name}: Fiyat okuma hatası: {e}")
            return None

    def get_satis_kosullari(self):
        """Alliance'dan satış koşulları tablosunu oku (MF, iskonto vb.)

        Returns:
            list: [{"vade": int, "min_adet": int, "mf": int, "iskonto_kurum": str,
                    "iskonto_ticari": str, "birim_fiyat": float}, ...]
        """
        try:
            self.switch_to_tab()
            kosullar = []

            # Önce normal (1 adet) fiyatını "Genel Toplam"dan oku
            # Bu KDV dahil fiyat - Alliance doğru KDV oranıyla hesaplayıp veriyor
            normal_fiyat_kdv_dahil = None

            # Adet Giriniz alanına 1 yaz (genelde zaten 1 geliyor)
            try:
                adet_input = self.driver.find_element(By.ID, "txt_adet")
                if adet_input:
                    adet_input.clear()
                    adet_input.send_keys("1")
                    time.sleep(0.5)
            except Exception as e:
                logger.debug(f"{self.name}: Adet input bulunamadı: {e}")

            # Yöntem 1: Genel Toplam değerini oku (KDV dahil)
            try:
                genel_toplam = self.driver.find_element(By.ID, "calculeted_grosstotal")
                # Önce .text dene, boşsa textContent dene
                genel_toplam_text = genel_toplam.text.strip()
                if not genel_toplam_text:
                    genel_toplam_text = genel_toplam.get_attribute("textContent").strip()
                if not genel_toplam_text:
                    genel_toplam_text = genel_toplam.get_attribute("innerText").strip()

                if genel_toplam_text:
                    # Türkçe format: "632,01" veya "188,5" → float
                    genel_toplam_clean = genel_toplam_text.replace(".", "").replace(",", ".")
                    normal_fiyat_kdv_dahil = float(genel_toplam_clean)
                    logger.info(f"{self.name}: Genel Toplam (KDV dahil): {normal_fiyat_kdv_dahil} TL")
                else:
                    logger.warning(f"{self.name}: Genel Toplam elementi bulundu ama içi boş")
            except Exception as e:
                logger.warning(f"{self.name}: Genel Toplam elementi okunamadı: {e}")

            # Yöntem 2: Genel Toplam boşsa, Net Tutar + KDV Toplamı'ndan hesapla
            if not normal_fiyat_kdv_dahil:
                try:
                    net_tutar_elem = self.driver.find_element(By.ID, "calculeted_nettotal")
                    kdv_toplam_elem = self.driver.find_element(By.ID, "calculeted_taxtotal")

                    net_tutar_text = net_tutar_elem.text.strip() or net_tutar_elem.get_attribute("textContent").strip()
                    kdv_toplam_text = kdv_toplam_elem.text.strip() or kdv_toplam_elem.get_attribute("textContent").strip()

                    if net_tutar_text and kdv_toplam_text:
                        net_tutar = float(net_tutar_text.replace(".", "").replace(",", "."))
                        kdv_toplam = float(kdv_toplam_text.replace(".", "").replace(",", "."))
                        normal_fiyat_kdv_dahil = net_tutar + kdv_toplam
                        logger.info(f"{self.name}: Net Tutar + KDV = {net_tutar} + {kdv_toplam} = {normal_fiyat_kdv_dahil} TL")
                except Exception as e:
                    logger.warning(f"{self.name}: Net Tutar + KDV hesaplanamadı: {e}")

            # tblKampanyalar tablosundaki satırları bul
            rows = self.driver.find_elements(By.CSS_SELECTOR, "#tblKampanyalar tbody tr")

            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 7:
                        # Sıra: Radio, Vade, Min Adet, MF, Kurum İsk, Ticari İsk, Birim Fiyat
                        vade = cells[1].text.strip()
                        min_adet = cells[2].text.strip()
                        mf = cells[3].text.strip()
                        iskonto_kurum = cells[4].text.strip()
                        iskonto_ticari = cells[5].text.strip()
                        birim_fiyat = cells[6].text.strip()

                        min_adet_int = int(min_adet) if min_adet.isdigit() else 1
                        mf_int = int(mf) if mf.isdigit() else 0

                        # KDV dahil fiyatı belirle - HER ZAMAN Genel Toplam'dan hesapla
                        if normal_fiyat_kdv_dahil:
                            if mf_int > 0 and min_adet_int > 0:
                                # MF'li satır: 1 adet fiyatından hesapla
                                # Formül: tek_adet_fiyat × min_adet / (min_adet + mf)
                                birim_fiyat_kdv_dahil = normal_fiyat_kdv_dahil * min_adet_int / (min_adet_int + mf_int)
                                logger.debug(f"{self.name}: MF {min_adet_int}+{mf_int}: {normal_fiyat_kdv_dahil} × {min_adet_int}/{min_adet_int + mf_int} = {birim_fiyat_kdv_dahil:.2f}")
                            else:
                                # Normal satır: Genel Toplam'dan okunan fiyatı kullan
                                birim_fiyat_kdv_dahil = normal_fiyat_kdv_dahil
                        else:
                            # Fallback: Genel Toplam okunamadıysa tablodaki fiyatı kullan
                            # KDV oranı bilinmiyor, tahmini hesapla (log'a uyarı yaz)
                            birim_fiyat_clean = birim_fiyat.replace(".", "").replace(",", ".") if birim_fiyat else "0"
                            birim_fiyat_float = float(birim_fiyat_clean)
                            # Genel Toplam okunamadığında KDV eklemiyoruz - zaten KDV dahil olabilir
                            birim_fiyat_kdv_dahil = birim_fiyat_float
                            logger.warning(f"{self.name}: Genel Toplam okunamadı, tablodaki fiyat kullanılıyor: {birim_fiyat_kdv_dahil}")

                        kosullar.append({
                            "sart": f"{min_adet_int}+{mf_int}" if mf_int > 0 else "1",
                            "vade": int(vade) if vade.isdigit() else 0,
                            "min_adet": min_adet_int,
                            "mf": mf_int,
                            "iskonto_kurum": iskonto_kurum if iskonto_kurum else "-",
                            "iskonto_ticari": iskonto_ticari if iskonto_ticari and iskonto_ticari != "\xa0" else "-",
                            "birim_fiyat": round(birim_fiyat_kdv_dahil, 2)  # KDV DAHİL fiyat
                        })
                except Exception as e:
                    logger.debug(f"{self.name}: Satır parse hatası: {e}")
                    continue

            logger.info(f"{self.name}: {len(kosullar)} satış koşulu bulundu")
            return kosullar

        except Exception as e:
            logger.error(f"{self.name}: Satış koşulları okuma hatası: {e}")
            return []

    def get_en_iyi_mf(self):
        """En iyi mal fazlası koşulunu döndür

        Returns:
            dict: {"min_adet": int, "mf": int, "oran": str} veya None
        """
        kosullar = self.get_satis_kosullari()

        # MF > 0 olan koşulları filtrele
        mf_kosullar = [k for k in kosullar if k["mf"] > 0]

        if not mf_kosullar:
            return None

        # En düşük min_adet ile en yüksek MF oranını bul
        # Oran = MF / min_adet
        en_iyi = max(mf_kosullar, key=lambda x: x["mf"] / x["min_adet"] if x["min_adet"] > 0 else 0)

        return {
            "min_adet": en_iyi["min_adet"],
            "mf": en_iyi["mf"],
            "oran": f"{en_iyi['min_adet']}+{en_iyi['mf']}"
        }

    def check_stock_status(self):
        """Alliance'da stok durumunu kontrol et ve fiyat al

        Öncelik sırası:
        1. "Sepete Ekle" butonu → STOKTA VAR
        2. "Şube satış görevlisi" mesajı → ÖZEL DURUM (Depoyu Ara)
        3. "Bakiye Al" veya "Bakiye Güncelle" → STOKTA YOK
        4. "İstek listenizde mevcut" → STOKTA YOK
        5. "Ürün Stokta Yok" → STOKTA YOK

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

            time.sleep(2)  # Sayfanın yüklenmesi için bekle

            # Her durumda fiyatı almaya çalış
            depo_price = self.get_depo_price()

            # Satış koşullarını ve şart bilgisini al
            satis_kosullari = self.get_satis_kosullari()
            en_iyi_mf = self.get_en_iyi_mf()
            sart = en_iyi_mf["oran"] if en_iyi_mf else None

            if sart:
                logger.info(f"{self.name}: 📦 Mal fazlası bulundu: {sart}")

            # Sayfa içeriğini al
            page_source = self.driver.page_source.lower()

            # 1. ÖNCELİK: "Sepete Ekle" butonu var mı? → STOKTA VAR
            # Not: Alliance'da bu buton <a id="addToChartButton">
            try:
                # Önce ID ile ara (en kesin yol)
                sepete_ekle = self.driver.find_element(By.ID, "addToChartButton")
                if sepete_ekle.is_displayed():
                    logger.info(f"{self.name}: ✓ 'Sepete Ekle' butonu bulundu (ID) - STOKTA VAR")
                    return {
                        "stok_var": True,
                        "mesaj": "Stokta Var",
                        "detay": "Sepete Ekle butonu mevcut",
                        "fiyat": depo_price,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except:
                # ID ile bulunamadıysa, XPath ile ara (yedek)
                try:
                    sepete_ekle = self.driver.find_element(By.XPATH,
                        "//button[contains(text(), 'Sepete Ekle')] | "
                        "//a[contains(text(), 'Sepete Ekle')] | "
                        "//input[@type='button' and contains(@value, 'Sepete Ekle')]")
                    if sepete_ekle.is_displayed():
                        logger.info(f"{self.name}: ✓ 'Sepete Ekle' butonu bulundu (XPath) - STOKTA VAR")
                        return {
                            "stok_var": True,
                            "mesaj": "Stokta Var",
                            "detay": "Sepete Ekle butonu mevcut",
                            "fiyat": depo_price,
                            "sart": sart,
                            "satis_kosullari": satis_kosullari
                        }
                except Exception as e:
                    # Buton yoksa devam et
                    logger.debug(f"{self.name}: 'Sepete Ekle' butonu bulunamadı: {e}")
                    pass

            # 2. "Şube satış görevlinizle iletişime geçiniz" → ÖZEL DURUM
            if "şube satış görevlinizle iletişime geçiniz" in page_source or \
               "lütfen şube satış görevlinizle" in page_source or \
               "şube satış görevlisi" in page_source:
                logger.info(f"{self.name}: ⚠ Özel Durum - Depoyu Ara (Telefoncu)")
                return {
                    "stok_var": False,
                    "mesaj": "Depoyu Ara",
                    "detay": "Şube satış görevlisi ile iletişime geçilmeli",
                    "fiyat": depo_price,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # 3. "Bakiye Al" veya "Bakiye Güncelle" butonu → STOKTA YOK
            if "bakiye al" in page_source or "bakiye güncelle" in page_source:
                logger.info(f"{self.name}: ✗ Bakiye Al/Güncelle - STOKTA YOK")
                return {
                    "stok_var": False,
                    "mesaj": "Stokta Yok",
                    "detay": "Bakiye Al/Güncelle durumu",
                    "fiyat": depo_price,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # 4. "İstek listenizde zaten mevcut" → STOKTA YOK
            if "istek listenizde" in page_source or "istek listenizde zaten mevcut" in page_source:
                logger.info(f"{self.name}: ✗ İstek listesi - STOKTA YOK")
                return {
                    "stok_var": False,
                    "mesaj": "Stokta Yok",
                    "detay": "İstek listesinde (Bakiye Al gerekli)",
                    "fiyat": depo_price,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # 5. "Ürün Stokta Yok" mesajı → STOKTA YOK
            if "ürün stokta yok" in page_source:
                logger.info(f"{self.name}: ✗ 'Ürün Stokta Yok' mesajı")
                return {
                    "stok_var": False,
                    "mesaj": "Stokta Yok",
                    "detay": "Ürün Stokta Yok mesajı",
                    "fiyat": depo_price,
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
