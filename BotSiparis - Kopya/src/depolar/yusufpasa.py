"""
Yusuf Paşa deposu sorgulama modülü
"""
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .base_depo import BaseDepo
from ..utils import logger, DEPOLAR


class YusufPasaDepo(BaseDepo):
    """Yusuf Paşa deposu sorgulama class'ı"""

    def __init__(self):
        config = DEPOLAR["yusufpasa"]
        super().__init__(config["name"], config["url"], config["elements"])

    def login(self, eczane_kodu, username, password):
        """Yusuf Paşa'ya giriş yap

        Args:
            eczane_kodu: Eczane kodu
            username: Kullanıcı adı
            password: Parola

        Returns:
            bool: Giriş başarılı mı
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Giriş yapılıyor...")

            # Eczane Kodu
            eczane_input = self.wait_for_element(By.NAME, "Eczane_Kodu")
            if not eczane_input:
                return False

            eczane_input.clear()
            eczane_input.send_keys(eczane_kodu)
            time.sleep(0.3)

            # Kullanıcı adı
            username_input = self.driver.find_element(By.NAME, "kullanici_adi")
            username_input.clear()
            username_input.send_keys(username)
            time.sleep(0.3)

            # Parola
            password_input = self.driver.find_element(By.NAME, "sifre")
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(0.3)

            # Giriş butonuna tıkla
            password_input.send_keys(Keys.ENTER)

            # Giriş kontrolü
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

            # Arama alanı yüklenmişse giriş başarılıdır
            search_box = self.wait_for_element(By.ID, self.elements["search_input"], timeout=15)
            if search_box:
                logger.info(f"{self.name}: Giriş başarılı!")
                return True

            logger.warning(f"{self.name}: Giriş başarısız! Arama kutusu bulunamadı.")
            return False

        except Exception as e:
            logger.error(f"{self.name}: Giriş hatası: {e}")
            return False

    def search_barcode(self, barcode):
        """Yusuf Paşa'da barkod ara

        Args:
            barcode: Aranacak barkod

        Returns:
            bool: Arama başarılı mı (ürün bulunduysa True)
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Barkod aranıyor: {barcode}")

            # Arama kutusunu bul
            search_input = self.wait_for_element(By.ID, self.elements["search_input"])
            if not search_input:
                return False

            # Arama kutusunu temizle ve barkodu yaz
            search_input.click()
            search_input.clear()
            time.sleep(0.3)
            search_input.send_keys(barcode)

            # Enter tuşuna bas veya arama butonuna tıkla
            search_input.send_keys(Keys.ENTER)

            # Sonuçların yüklenmesi için bekle
            time.sleep(2)

            # DOĞRULAMA: "Kayit yok !" mesajı var mı kontrol et
            try:
                page_source = self.driver.page_source
                if "kayit yok" in page_source.lower() or "kayıt yok" in page_source.lower():
                    logger.info(f"{self.name}: Ürün bulunamadı (Kayit yok): {barcode}")
                    return False
            except:
                pass

            return True
        except Exception as e:
            logger.error(f"{self.name}: Barkod arama hatası: {e}")
            return False

    def check_stock_status(self):
        """Yusuf Paşa'da stok durumunu kontrol et

        Öncelik sırası:
        1. "Sepete Ekle" butonu → STOKTA VAR
        2. "Lütfen Satış Temsilcinizle Görüşün." → ÖZEL DURUM (Depoyu Ara)
        3. "Şu An Stokta Bulunmamaktadır" → STOKTA YOK

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
            # Önce doğru tab'a geç
            self.switch_to_tab()

            time.sleep(2)  # Sayfanın yüklenmesi için bekle

            # Satış koşullarını ve şart bilgisini al
            satis_kosullari = self.get_satis_kosullari()
            en_iyi_mf = self.get_en_iyi_mf()
            sart = en_iyi_mf["oran"] if en_iyi_mf else None

            if sart:
                logger.info(f"{self.name}: 📦 Mal fazlası bulundu: {sart}")

            # Sayfa içeriğini al
            page_source = self.driver.page_source
            page_source_lower = page_source.lower()

            # 1. ÖNCELİK: "Sepete Ekle" butonu var mı? → STOKTA VAR
            try:
                sepete_ekle = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Sepete Ekle') or contains(@value, 'Sepete Ekle') or contains(@title, 'Sepete Ekle')] | //input[@type='button' and contains(@value, 'Sepete Ekle')]")
                if sepete_ekle.is_displayed():
                    logger.info(f"{self.name}: ✓ 'Sepete Ekle' butonu bulundu - STOKTA VAR")
                    return {
                        "stok_var": True,
                        "mesaj": "Stokta Var",
                        "detay": "Sepete Ekle butonu mevcut",
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except:
                # Buton yoksa devam et
                pass

            # 2. "Lütfen Satış Temsilcinizle Görüşün." → ÖZEL DURUM
            if "lütfen satış temsilcinizle görüşün" in page_source_lower or \
               "satış temsilcinizle görüşün" in page_source_lower or \
               "satış temsilciniz" in page_source_lower:
                logger.info(f"{self.name}: ⚠ Özel Durum - Depoyu Ara (Satış Temsilcisi)")
                return {
                    "stok_var": False,
                    "mesaj": "Depoyu Ara",
                    "detay": "Satış temsilcisi ile görüşülmeli",
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # 3. "Şu An Stokta Bulunmamaktadır" → STOKTA YOK
            if "şu an stokta bulunmamaktadır" in page_source_lower or \
               "stokta bulunmamaktadır" in page_source_lower or \
               "bulunmamaktadır" in page_source_lower:
                logger.info(f"{self.name}: ✗ 'Şu An Stokta Bulunmamaktadır' - STOKTA YOK")
                return {
                    "stok_var": False,
                    "mesaj": "Stokta Yok",
                    "detay": "Şu An Stokta Bulunmamaktadır",
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # Hiçbir durum tespit edilemedi - Varsayılan
            logger.warning(f"{self.name}: ⚠ Durum belirlenemedi")
            return {
                "stok_var": False,
                "mesaj": "Belirsiz",
                "detay": "Durum belirlenemedi",
                "sart": sart,
                "satis_kosullari": satis_kosullari
            }

        except Exception as e:
            logger.error(f"{self.name}: Stok kontrolü hatası: {e}")
            return {
                "stok_var": False,
                "mesaj": "Hata",
                "detay": str(e),
                "sart": None,
                "satis_kosullari": []
            }

    def set_order_quantity(self, quantity):
        """Yusuf Paşa'da sipariş miktarını ayarla

        Args:
            quantity: Sipariş adedi

        Returns:
            bool: İşlem başarılı mı
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Sipariş adedi ayarlanıyor: {quantity}")
            time.sleep(0.5)  # Sayfanın tam yüklenmesi için bekle

            # Yusuf Paşa'da "OrderQuantity" ID'li input alanını bul
            input_field = None

            # Önce ID ile direkt dene (en güvenilir)
            try:
                input_field = self.driver.find_element(By.ID, "OrderQuantity")
                if input_field.is_displayed() and input_field.is_enabled():
                    logger.debug(f"{self.name}: OrderQuantity input field bulundu (ID)")
                else:
                    input_field = None
            except Exception as e:
                logger.debug(f"{self.name}: OrderQuantity ID ile bulunamadı: {e}")

            # ID ile bulunamadıysa alternatif yollar dene
            if not input_field:
                xpaths = [
                    # 1. Name attribute'u ile
                    "//input[@name='OrderQuantity']",
                    # 2. Tablodaki düzenlenebilir input alanı
                    "//table//input[@type='text' and not(@readonly)]",
                    # 3. Form içindeki ilk düzenlenebilir input
                    "//form//input[@type='text' and not(@readonly)]"
                ]

                for xpath in xpaths:
                    try:
                        elements = self.driver.find_elements(By.XPATH, xpath)
                        for elem in elements:
                            if elem.is_displayed() and elem.is_enabled():
                                input_field = elem
                                logger.debug(f"{self.name}: Input field bulundu: {xpath}")
                                break
                        if input_field:
                            break
                    except Exception as e:
                        logger.debug(f"{self.name}: XPath başarısız ({xpath}): {e}")
                        continue

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

    def get_product_name(self):
        """Yusuf Paşa'dan ürün adını al

        Returns:
            str: Ürün adı veya None
        """
        try:
            self.switch_to_tab()

            # 1. Yöntem: ItemProperties JavaScript dizisinden al
            try:
                result = self.driver.execute_script("""
                    if (typeof ItemProperties !== 'undefined' && ItemProperties[1]) {
                        return ItemProperties[1].trim();
                    }
                    return null;
                """)
                if result:
                    logger.info(f"{self.name}: Ürün adı bulundu (ItemProperties): {result}")
                    return result
            except:
                pass

            # 2. Yöntem: Ürün başlığı (örn: "VIRENTE 0,5 MG 30 TB")
            try:
                product_headers = self.driver.find_elements(By.XPATH, "//td[contains(@colspan, '')]//b | //th[contains(@colspan, '')]")
                for header in product_headers:
                    text = header.text.strip()
                    if text and any(unit in text.upper() for unit in ['MG', 'ML', 'TB', 'TABLET', 'KAPSÜL', 'FLK', 'AMP']):
                        logger.info(f"{self.name}: Ürün adı bulundu: {text}")
                        return text
            except:
                pass

            # 3. Yöntem: Sayfa başlığı
            try:
                title = self.driver.title
                if title and "-" in title:
                    parts = title.split("-")
                    if len(parts) > 1:
                        product_name = parts[-1].strip()
                        if product_name:
                            logger.info(f"{self.name}: Ürün adı bulundu (title): {product_name}")
                            return product_name
            except:
                pass

            logger.warning(f"{self.name}: Ürün adı bulunamadı")
            return None

        except Exception as e:
            logger.error(f"{self.name}: Ürün adı alma hatası: {e}")
            return None

    def get_item_properties(self):
        """Yusuf Paşa'dan ItemProperties JavaScript dizisini oku

        ItemProperties yapısı:
        [0] = ProductID
        [1] = Ürün Adı ('VIRENTE 0,5 MG 30 TB')
        [2] = Satış Fiyatı KDV dahil (2030.41)
        [3] = Liste Fiyatı (2601.43)
        [4] = KDV oranı (10)

        Returns:
            dict: {"urun_adi": str, "satis_fiyati": float, "liste_fiyati": float, "kdv_orani": float}
        """
        try:
            self.switch_to_tab()

            # JavaScript'ten ItemProperties dizisini al
            try:
                result = self.driver.execute_script("""
                    if (typeof ItemProperties !== 'undefined') {
                        return {
                            urun_adi: ItemProperties[1],
                            satis_fiyati: ItemProperties[2],
                            liste_fiyati: ItemProperties[3],
                            kdv_orani: ItemProperties[4]
                        };
                    }
                    return null;
                """)
                if result:
                    logger.info(f"{self.name}: ItemProperties bulundu: Liste={result['liste_fiyati']}, Satış={result['satis_fiyati']}")
                    return result
            except Exception as e:
                logger.debug(f"{self.name}: ItemProperties JavaScript hatası: {e}")

            # Alternatif: HiddenPrice input'undan al
            try:
                hidden_price = self.driver.find_element(By.ID, "HiddenPrice")
                if hidden_price:
                    fiyat_text = hidden_price.get_attribute("value")
                    if fiyat_text:
                        fiyat = float(fiyat_text.replace(".", "").replace(",", "."))
                        logger.info(f"{self.name}: HiddenPrice bulundu: {fiyat}")
                        return {"liste_fiyati": fiyat, "satis_fiyati": None, "kdv_orani": 10}
            except:
                pass

            return None
        except Exception as e:
            logger.error(f"{self.name}: ItemProperties okuma hatası: {e}")
            return None

    def get_satis_kosullari(self):
        """Yusuf Paşa'dan satış koşulları tablosunu oku (MF, iskonto vb.)

        Kampanya tablosu yapısı (id="oTable"):
        | Kampanya | Vade | Miktar | MF | Oran | Ödeme Tarihi | Bitiş Tarihi |
        |----------|------|--------|-----|------|--------------|--------------|
        | Kurum İskontosu (colspan=2) | 1 (colspan=2) | %6,00 | | |
        | MF* (radio) | 90 | 1 | | %0,00 | 26.2.2026 | |
        | NOBEL ILAC (radio) | 90 | 7 | +1 | %14,29 | 26.2.2026 | 30.11.2025 |

        Fiyat hesabı:
        - Normal (MF yok): Satış Fiyatı × 1.10 (KDV) × (1 - Kurum İskontosu/100)
        - MF'li: Normal fiyat × min_adet / (min_adet + mf)

        Returns:
            list: [{"sart": str, "fiyat": float, "min_adet": int, "mf": int}, ...]
        """
        try:
            self.switch_to_tab()
            kosullar = []

            # ItemProperties'den fiyat bilgilerini al
            item_props = self.get_item_properties()

            if item_props:
                satis_fiyati = item_props.get("satis_fiyati")  # Satış Fiyatı (KDV hariç)
                liste_fiyati = item_props.get("liste_fiyati")  # Liste Fiyatı (KDV hariç)
                kdv_orani = item_props.get("kdv_orani", 10) / 100  # 10 -> 0.10
            else:
                satis_fiyati = None
                liste_fiyati = None
                kdv_orani = 0.10

            KDV_CARPANI = 1 + kdv_orani  # 1.10

            # Kampanya tablosunu bul (id="oTable" ve "Kampanya" başlığı içeren)
            kampanya_table = None

            # Önce id="oTable" dene
            try:
                tables = self.driver.find_elements(By.ID, "oTable")
                for table in tables:
                    table_text = table.text.lower()
                    if "kampanya" in table_text and "mf" in table_text:
                        kampanya_table = table
                        logger.debug(f"{self.name}: Kampanya tablosu bulundu (oTable)")
                        break
            except:
                pass

            # Alternatif: tüm tablolarda ara
            if not kampanya_table:
                tables = self.driver.find_elements(By.TAG_NAME, "table")
                for table in tables:
                    # Başlık hücrelerini kontrol et
                    headers = table.find_elements(By.CSS_SELECTOR, "td span.dstyle, th")
                    header_texts = [h.text.strip().lower() for h in headers]
                    if any("kampanya" in h for h in header_texts) and any("mf" in h for h in header_texts):
                        kampanya_table = table
                        logger.debug(f"{self.name}: Kampanya tablosu bulundu (dstyle)")
                        break

            # Önce Kurum İskontosu'nu bul
            kurum_iskonto_yuzde = 0
            mf_satirlari = []

            if kampanya_table:
                rows = kampanya_table.find_elements(By.TAG_NAME, "tr")

                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 3:
                        continue

                    try:
                        row_text = row.text.strip().lower()
                        has_radio = len(row.find_elements(By.CSS_SELECTOR, "input[type='radio']")) > 0

                        # İskonto satırı (radio button YOK)
                        # Kurum İskontosu veya Ürün İskontosu olabilir
                        # Türkçe karakter sorunları için: iskonto, ıskonto, skonto
                        if not has_radio and ("iskonto" in row_text or "skonto" in row_text):
                            # Oran sütununu bul - colspan kullanıldığı için farklı index olabilir
                            for cell in cells:
                                cell_text = cell.text.strip()
                                if "%" in cell_text:
                                    oran_match = re.search(r'%?([\d,\.]+)', cell_text)
                                    if oran_match:
                                        kurum_iskonto_yuzde = float(oran_match.group(1).replace(",", "."))
                                        logger.info(f"{self.name}: İskonto bulundu: %{kurum_iskonto_yuzde} (satır: {row_text[:30]}...)")
                                        break

                        # MF satırları (radio button VAR)
                        elif has_radio:
                            mf_satirlari.append((row, cells))

                    except Exception as e:
                        logger.debug(f"{self.name}: Satır parse hatası: {e}")
                        continue

            # Normal fiyatı sayfadan oku (hesaplamak yerine)
            # 1. Sipariş Miktarı input'una 1 yaz (OrderQuantity)
            # 2. KDV Dahil Tutar değerini oku (SubTotal)
            normal_fiyat = None
            try:
                # Sipariş Miktarı input'unu bul
                siparis_input = self.driver.find_element(By.ID, "OrderQuantity")
                if siparis_input:
                    siparis_input.clear()
                    siparis_input.send_keys("1")
                    siparis_input.send_keys(Keys.TAB)  # Hesaplamayı tetikle
                    time.sleep(0.5)  # Hesaplamanın tamamlanmasını bekle

                    # KDV Dahil Tutar değerini oku (SubTotal input)
                    try:
                        kdv_dahil_element = self.driver.find_element(By.ID, "SubTotal")
                        kdv_dahil_text = kdv_dahil_element.get_attribute("value") or kdv_dahil_element.text
                        kdv_dahil_text = kdv_dahil_text.strip()
                        if kdv_dahil_text:
                            # Yusufpaşa nokta (.) ondalık ayracı kullanıyor
                            # "90.19" → 90.19, "1234.56" → 1234.56
                            # Virgül varsa Türkçe format: "1.234,56" → 1234.56
                            if "," in kdv_dahil_text:
                                kdv_dahil_text = kdv_dahil_text.replace(".", "").replace(",", ".")
                            # Virgül yoksa nokta ondalık: "90.19" → 90.19
                            normal_fiyat = float(kdv_dahil_text)
                            logger.info(f"{self.name}: KDV Dahil Tutar (sayfadan): {normal_fiyat} TL")
                    except Exception as e:
                        logger.debug(f"{self.name}: SubTotal bulunamadı: {e}")
            except Exception as e:
                logger.debug(f"{self.name}: OrderQuantity input bulunamadı: {e}")

            # Sayfadan okuyamadıysak, hesapla (yedek)
            if not normal_fiyat and satis_fiyati:
                iskonto_carpani = 1 - (kurum_iskonto_yuzde / 100) if kurum_iskonto_yuzde > 0 else 1
                normal_fiyat = satis_fiyati * KDV_CARPANI * iskonto_carpani
                logger.info(f"{self.name}: Normal fiyat (hesaplanan): {satis_fiyati} × {KDV_CARPANI} × {iskonto_carpani} = {normal_fiyat:.2f}")

            if normal_fiyat:
                kosullar.append({
                    "sart": "1",
                    "birim_fiyat": round(normal_fiyat, 2),
                    "min_adet": 1,
                    "mf": 0,
                    "kampanya": "Normal",
                    "kurum_iskonto": kurum_iskonto_yuzde
                })

            # MF satırlarını işle
            for row, cells in mf_satirlari:
                try:
                    # cells[0] = Kampanya (radio + label)
                    # cells[1] = Vade
                    # cells[2] = Miktar
                    # cells[3] = MF
                    # cells[4] = Oran (ek iskonto)

                    kampanya = cells[0].text.strip() if len(cells) > 0 else ""
                    miktar_text = cells[2].text.strip() if len(cells) > 2 else ""
                    mf_text = cells[3].text.strip() if len(cells) > 3 else ""
                    oran_text = cells[4].text.strip() if len(cells) > 4 else ""

                    # Miktar parse
                    min_adet = 1
                    if miktar_text:
                        miktar_match = re.search(r'(\d+)', miktar_text)
                        if miktar_match:
                            min_adet = int(miktar_match.group(1))

                    # MF parse ("+1" gibi)
                    mf = 0
                    if mf_text:
                        mf_match = re.search(r'\+?(\d+)', mf_text)
                        if mf_match:
                            mf = int(mf_match.group(1))

                    # Ek iskonto parse ("%14,29" gibi)
                    ek_iskonto_yuzde = 0
                    if oran_text:
                        oran_match = re.search(r'%?([\d,\.]+)', oran_text)
                        if oran_match:
                            ek_iskonto_yuzde = float(oran_match.group(1).replace(",", "."))

                    # Sadece MF > 0 olanları ekle
                    if mf > 0 and min_adet > 0:
                        # MF'li fiyat hesapla: 1 adet fiyatından hareketle
                        # Formül: tek_adet_fiyat × min / (min + mf)
                        # NOT: "Oran" sütunundaki %9,09 gibi değerler MF'nin yüzde karşılığıdır,
                        # ek iskonto DEĞİLDİR! (10+1 = 1/11 = %9.09)
                        # Bu yüzden ek_iskonto_yuzde UYGULANMAMALI
                        if normal_fiyat:
                            efektif_fiyat = normal_fiyat * min_adet / (min_adet + mf)
                            logger.debug(f"{self.name}: MF {min_adet}+{mf}: {normal_fiyat} × {min_adet}/{min_adet + mf} = {efektif_fiyat:.2f}")
                        else:
                            efektif_fiyat = 0

                        sart_str = f"{min_adet}+{mf}"
                        kosullar.append({
                            "sart": sart_str,
                            "birim_fiyat": round(efektif_fiyat, 2),
                            "min_adet": min_adet,
                            "mf": mf,
                            "kampanya": kampanya,
                            "kurum_iskonto": kurum_iskonto_yuzde,
                            "ek_iskonto": ek_iskonto_yuzde
                        })
                        logger.info(f"{self.name}: MF koşulu: {sart_str}, fiyat: {efektif_fiyat:.2f}")

                except Exception as e:
                    logger.debug(f"{self.name}: MF satır parse hatası: {e}")
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
