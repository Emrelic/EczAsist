"""
Selçuk deposu sorgulama modülü
"""
import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .base_depo import BaseDepo
from .depo_config import DEPOLAR

logger = logging.getLogger(__name__)


class SelcukDepo(BaseDepo):
    """Selçuk deposu sorgulama class'ı"""

    def __init__(self):
        config = DEPOLAR["selcuk"]
        super().__init__(config["name"], config["url"], config["elements"])

    def login(self, hesap_kodu, username, password):
        """Selçuk'a giriş yap"""
        try:
            self.switch_to_tab()

            logger.info(f"{self.name}: Giriş yapılıyor...")

            hesap_input = self.wait_for_element(By.ID, "txtEczaneKodu")
            if not hesap_input:
                return False

            hesap_input.clear()
            hesap_input.send_keys(hesap_kodu)
            time.sleep(0.3)

            username_input = self.driver.find_element(By.ID, "txtKullaniciAdi")
            username_input.clear()
            username_input.send_keys(username)
            time.sleep(0.3)

            password_input = self.driver.find_element(By.ID, "txtSifre")
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(0.3)

            password_input.send_keys(Keys.ENTER)
            time.sleep(3)

            try:
                self.driver.execute_script("""
                    var savePasswordButton = document.querySelector('button[aria-label*="Hiçbir zaman"]');
                    if (savePasswordButton) savePasswordButton.click();
                """)
            except:
                pass

            if "hizlisiparis" in self.driver.current_url:
                logger.info(f"{self.name}: Giriş başarılı!")
                return True
            else:
                logger.warning(f"{self.name}: Giriş başarısız!")
                return False

        except Exception as e:
            logger.error(f"{self.name}: Giriş hatası: {e}")
            return False

    def search_barcode(self, barcode):
        """Selçuk'ta barkod ara"""
        try:
            self.switch_to_tab()

            logger.info(f"{self.name}: Barkod aranıyor: {barcode}")

            search_input = self.wait_for_element(By.ID, self.elements["search_input"])
            if not search_input:
                return False

            search_input.click()
            search_input.clear()
            time.sleep(0.3)

            search_input.send_keys(barcode)
            search_input.send_keys(Keys.ENTER)

            max_wait = 5
            wait_interval = 0.5
            waited = 0

            while waited < max_wait:
                time.sleep(wait_interval)
                waited += wait_interval

                try:
                    lbl_baslik = self.driver.find_element(By.ID, "lblBaslik")
                    baslik_text = lbl_baslik.text.strip()

                    if barcode in baslik_text:
                        logger.info(f"{self.name}: Barkod doğrulandı: {barcode}")
                        return True

                    if baslik_text and barcode not in baslik_text:
                        logger.debug(f"{self.name}: lblBaslik henüz güncellenmedi, bekleniyor...")
                        continue

                except Exception as e:
                    logger.debug(f"{self.name}: lblBaslik kontrolü hatası: {e}")

            # Timeout - son durumu kontrol et
            try:
                lbl_baslik = self.driver.find_element(By.ID, "lblBaslik")
                baslik_text = lbl_baslik.text.strip()

                if barcode in baslik_text:
                    return True

                if not baslik_text:
                    logger.info(f"{self.name}: lblBaslik boş - ürün bulunamadı")
                    return False

                logger.warning(f"{self.name}: Barkod doğrulaması zaman aşımı")
                return False

            except Exception as e:
                logger.info(f"{self.name}: lblBaslik elementi bulunamadı - ürün yok")
                return False
        except Exception as e:
            logger.error(f"{self.name}: Barkod arama hatası: {e}")
            return False

    def get_product_name(self):
        """Selçuk'tan ürün adını al"""
        try:
            self.switch_to_tab()

            try:
                lbl_baslik = self.driver.find_element(By.ID, "lblBaslik")
                full_text = lbl_baslik.text.strip()
                if full_text and " - " in full_text:
                    product_name = full_text.split(" - ", 1)[1].strip()
                    if product_name:
                        return product_name
            except:
                pass

            return None

        except Exception as e:
            logger.error(f"{self.name}: Ürün adı alma hatası: {e}")
            return None

    def get_net_tutar_hesapla(self):
        """Selçuk'ta 1 adet için Net Tutar hesapla"""
        try:
            self.switch_to_tab()

            miktar_input = self.wait_for_element(By.ID, "txtMiktar")
            if not miktar_input:
                return None

            miktar_input.clear()
            time.sleep(0.1)
            miktar_input.send_keys("1")
            time.sleep(0.3)

            try:
                hesapla_btn = self.driver.find_element(By.ID, "aHesapla")
                if not hesapla_btn.is_displayed():
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", hesapla_btn)
                    time.sleep(0.2)
                hesapla_btn.click()
            except Exception as btn_err:
                logger.error(f"{self.name}: Hesapla butonu tıklanamadı: {btn_err}")
                return None

            time.sleep(0.8)

            try:
                net_tutar_elem = self.driver.find_element(By.ID, "spnNetTutar")
                net_tutar_text = net_tutar_elem.text.strip()
            except Exception as elem_err:
                logger.error(f"{self.name}: spnNetTutar elementi bulunamadı: {elem_err}")
                return None

            if net_tutar_text:
                if "," in net_tutar_text:
                    net_tutar_text_clean = net_tutar_text.replace(".", "").replace(",", ".")
                else:
                    net_tutar_text_clean = net_tutar_text

                try:
                    net_tutar = float(net_tutar_text_clean)
                    logger.info(f"{self.name}: Net Tutar (1 adet): {net_tutar:.2f} TL")
                    return net_tutar
                except ValueError as ve:
                    logger.error(f"{self.name}: Net tutar parse hatası: '{net_tutar_text}' - {ve}")
                    return None
            else:
                logger.warning(f"{self.name}: spnNetTutar boş döndü")
                return None

        except Exception as e:
            logger.error(f"{self.name}: Net tutar hesaplama hatası: {e}")
            return None

    def get_mf_bilgisi(self):
        """Selçuk'tan MF (Mal Fazlası) bilgisini oku"""
        try:
            self.switch_to_tab()
            mf_listesi = []

            time.sleep(0.3)

            rows = self.driver.find_elements(By.CSS_SELECTOR, "#tblKampanyalar tbody tr")

            for row in rows:
                try:
                    spans = row.find_elements(By.TAG_NAME, "span")
                    for span in spans:
                        text = span.text.strip()
                        if "+" in text and len(text) <= 10:
                            parts = text.split("+")
                            if len(parts) == 2:
                                try:
                                    min_adet = int(parts[0].strip())
                                    mf = int(parts[1].strip())
                                    if min_adet > 0 and mf > 0:
                                        mf_listesi.append({
                                            "min_adet": min_adet,
                                            "mf": mf
                                        })
                                        logger.info(f"{self.name}: MF bulundu: {min_adet}+{mf}")
                                except ValueError:
                                    continue
                except Exception:
                    continue

            # Tekrar eden kayıtları kaldır
            unique_mf = []
            seen = set()
            for item in mf_listesi:
                key = (item["min_adet"], item["mf"])
                if key not in seen:
                    seen.add(key)
                    unique_mf.append(item)

            return unique_mf

        except Exception as e:
            logger.error(f"{self.name}: MF bilgisi okuma hatası: {e}")
            return []

    def get_satis_kosullari(self):
        """Selçuk'tan satış koşulları tablosunu oku"""
        try:
            self.switch_to_tab()
            kosullar = []

            # 1. ÖNCE MF bilgisini al (HESAPLA'ya basmadan önce!)
            mf_bilgisi = self.get_mf_bilgisi()

            # 2. Net Tutar'ı hesapla (1 adet için)
            net_tutar = self.get_net_tutar_hesapla()

            if not net_tutar:
                logger.warning(f"{self.name}: Net tutar alınamadı")
                return []

            # 3. Birim fiyat hesapla
            if mf_bilgisi:
                kosullar.append({
                    "min_adet": 1,
                    "mf": 0,
                    "birim_fiyat": net_tutar,
                    "vade": 0
                })

                for mf_item in mf_bilgisi:
                    min_adet = mf_item["min_adet"]
                    mf = mf_item["mf"]
                    toplam_adet = min_adet + mf
                    birim_fiyat = (net_tutar * min_adet) / toplam_adet

                    kosullar.append({
                        "min_adet": min_adet,
                        "mf": mf,
                        "birim_fiyat": birim_fiyat,
                        "vade": 0
                    })
            else:
                kosullar.append({
                    "min_adet": 1,
                    "mf": 0,
                    "birim_fiyat": net_tutar,
                    "vade": 0
                })

            logger.info(f"{self.name}: {len(kosullar)} satış koşulu bulundu")
            return kosullar

        except Exception as e:
            logger.error(f"{self.name}: Satış koşulları okuma hatası: {e}")
            return []

    def check_stock_status(self):
        """Selçuk'ta stok durumunu kontrol et"""
        try:
            self.switch_to_tab()

            time.sleep(2)

            satis_kosullari = self.get_satis_kosullari()
            fiyat = satis_kosullari[0]["birim_fiyat"] if satis_kosullari else None

            sart = None
            mf_kosullar = [k for k in satis_kosullari if k["mf"] > 0]
            if mf_kosullar:
                en_iyi = max(mf_kosullar, key=lambda x: x["mf"] / x["min_adet"] if x["min_adet"] > 0 else 0)
                sart = f"{en_iyi['min_adet']}+{en_iyi['mf']}"

            page_source = self.driver.page_source
            page_source_lower = page_source.lower()

            # 1. "Siparişe Ekle" butonu kontrolü
            try:
                siparise_ekle = self.driver.find_element(By.ID, "aSiparisEkle")
                element_classes = siparise_ekle.get_attribute("class") or ""
                element_text = siparise_ekle.text.strip()

                if "disabled" not in element_classes.lower() and "siparişe ekle" in element_text.lower():
                    logger.info(f"{self.name}: 'Siparişe Ekle' butonu aktif - STOKTA VAR")
                    return {
                        "stok_var": True,
                        "mesaj": "Stokta Var",
                        "detay": "Siparişe Ekle butonu aktif",
                        "fiyat": fiyat,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }
            except:
                pass

            # 2. "Satış Temsilcinizle Görüşünüz" → ÖZEL DURUM
            if "lütfen satış temsilcinizle görüşünüz" in page_source_lower or \
               "internet üzerinden satılmamaktadır" in page_source_lower:
                return {
                    "stok_var": False,
                    "mesaj": "Depoyu Ara",
                    "detay": "Satış temsilcisi ile görüşülmeli",
                    "fiyat": fiyat,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # 3. "Şu An Stokta Bulunmamaktadır!" → STOKTA YOK
            if "şu an stokta bulunmamaktadır" in page_source_lower or \
               "stokta bulunmamaktadır" in page_source_lower:
                return {
                    "stok_var": False,
                    "mesaj": "Stokta Yok",
                    "detay": "Şu An Stokta Bulunmamaktadır!",
                    "fiyat": fiyat,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # 4. "Sipariş verilemez"
            if "sipariş verilemez" in page_source_lower:
                return {
                    "stok_var": False,
                    "mesaj": "Stokta Yok",
                    "detay": "Sipariş verilemez",
                    "fiyat": fiyat,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            logger.warning(f"{self.name}: Durum belirlenemedi")
            return {
                "stok_var": False,
                "mesaj": "Belirsiz",
                "detay": "Durum belirlenemedi",
                "fiyat": fiyat,
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
