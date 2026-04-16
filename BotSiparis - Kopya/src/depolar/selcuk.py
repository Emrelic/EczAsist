"""
Selçuk deposu sorgulama modülü
"""
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from .base_depo import BaseDepo
from ..utils import logger, DEPOLAR


class SelcukDepo(BaseDepo):
    """Selçuk deposu sorgulama class'ı"""

    def __init__(self):
        config = DEPOLAR["selcuk"]
        super().__init__(config["name"], config["url"], config["elements"])

    def login(self, hesap_kodu, username, password):
        """Selçuk'a giriş yap

        Args:
            hesap_kodu: Hesap kodu
            username: Kullanıcı adı
            password: Şifre

        Returns:
            bool: Giriş başarılı mı
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Giriş yapılıyor...")

            # Hesap Kodu
            hesap_input = self.wait_for_element(By.ID, "txtEczaneKodu")
            if not hesap_input:
                return False

            hesap_input.clear()
            hesap_input.send_keys(hesap_kodu)
            time.sleep(0.3)

            # Kullanıcı adı
            username_input = self.driver.find_element(By.ID, "txtKullaniciAdi")
            username_input.clear()
            username_input.send_keys(username)
            time.sleep(0.3)

            # Şifre
            password_input = self.driver.find_element(By.ID, "txtSifre")
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
        """Selçuk'ta barkod ara

        Args:
            barcode: Aranacak barkod

        Returns:
            bool: Arama başarılı mı
        """
        try:
            # Önce doğru tab'a geç
            self.switch_to_tab()

            logger.info(f"{self.name}: Barkod aranıyor: {barcode}")

            # Arama kutusunu bul
            search_input = self.wait_for_element(By.ID, self.elements["search_input"])
            if not search_input:
                return False

            # ÖNCEKİ SONUÇLARI TEMİZLE: Önce boş bir arama yap veya sayfayı yenile
            # Arama kutusunu seç ve içeriği tamamen temizle
            search_input.click()
            search_input.clear()
            time.sleep(0.3)

            # Yeni barkodu yaz
            search_input.send_keys(barcode)
            search_input.send_keys(Keys.ENTER)

            # Sonuçların yüklenmesi için bekle - sayfanın güncellenmesini bekle
            # lblBaslik'ın barkodu içermesini veya boş kalmasını (ürün yok) bekle
            max_wait = 5  # maksimum 5 saniye bekle
            wait_interval = 0.5
            waited = 0

            while waited < max_wait:
                time.sleep(wait_interval)
                waited += wait_interval

                try:
                    lbl_baslik = self.driver.find_element(By.ID, "lblBaslik")
                    baslik_text = lbl_baslik.text.strip()

                    # Barkod bulundu - başarılı
                    if barcode in baslik_text:
                        logger.info(f"{self.name}: Barkod doğrulandı: {barcode}")
                        return True

                    # lblBaslik var ama farklı içerik - henüz güncellenmemiş, bekle
                    # (önceki aramanın sonucu hala görünüyor olabilir)
                    if baslik_text and barcode not in baslik_text:
                        logger.debug(f"{self.name}: lblBaslik henüz güncellenmedi, bekleniyor... ({baslik_text})")
                        continue

                except Exception as e:
                    logger.debug(f"{self.name}: lblBaslik kontrolü hatası: {e}")

            # Timeout - son durumu kontrol et
            try:
                lbl_baslik = self.driver.find_element(By.ID, "lblBaslik")
                baslik_text = lbl_baslik.text.strip()

                if barcode in baslik_text:
                    logger.info(f"{self.name}: Barkod doğrulandı (timeout sonrası): {barcode}")
                    return True

                if not baslik_text:
                    logger.info(f"{self.name}: lblBaslik boş - ürün bulunamadı")
                    return False

                # Hala farklı barkod - ürün bulunamadı olarak işaretle
                logger.warning(f"{self.name}: Barkod doğrulaması zaman aşımı - beklenen: {barcode}, ekranda: {baslik_text}")
                return False

            except Exception as e:
                logger.info(f"{self.name}: lblBaslik elementi bulunamadı - ürün yok")
                return False
        except Exception as e:
            logger.error(f"{self.name}: Barkod arama hatası: {e}")
            return False

    def get_product_name(self):
        """Selçuk'tan ürün adını al

        Returns:
            str: Ürün adı veya None
        """
        try:
            self.switch_to_tab()

            product_name = None

            # 1. Yöntem: #lblBaslik elementi
            # Format: "8699514355717 - HAMETAN %5.35 30 GR KR."
            try:
                lbl_baslik = self.driver.find_element(By.ID, "lblBaslik")
                full_text = lbl_baslik.text.strip()
                if full_text and " - " in full_text:
                    # Barkodu ayır, sadece ürün adını al
                    product_name = full_text.split(" - ", 1)[1].strip()
                    if product_name:
                        logger.info(f"{self.name}: Ürün adı bulundu (#lblBaslik): {product_name}")
                        return product_name
            except:
                pass

            # 2. Yöntem: Arama sonuç tablosundaki ilk satır
            try:
                first_row = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "table tbody tr td.col-xs-9"
                )
                product_name = first_row.text.strip()
                if product_name:
                    logger.info(f"{self.name}: Ürün adı bulundu (tablo): {product_name}")
                    return product_name
            except:
                pass

            logger.warning(f"{self.name}: Ürün adı bulunamadı")
            return None

        except Exception as e:
            logger.error(f"{self.name}: Ürün adı alma hatası: {e}")
            return None

    def get_depocu_fiyat_ve_iskonto(self):
        """Selçuk'tan Depocu Fiyatı ve Kurum İskonto bilgisini oku

        Returns:
            tuple: (depocu_fiyat, kurum_isk_yuzde) veya (None, None)
        """
        try:
            self.switch_to_tab()

            depocu_fiyat = None
            kurum_isk = None

            # Tüm row'ları tara
            rows = self.driver.find_elements(By.CSS_SELECTOR, ".row .col-xs-12")

            for row in rows:
                try:
                    divs = row.find_elements(By.TAG_NAME, "div")
                    if len(divs) >= 2:
                        label = divs[0].text.strip().lower()
                        value = divs[1].text.strip()

                        if "depocu fiyat" in label:
                            # Format: 2,030.41 veya 2.030,41
                            value_clean = value.replace(",", "").replace(".", "").strip()
                            if value_clean:
                                # Son 2 hane kuruş
                                if len(value_clean) > 2:
                                    depocu_fiyat = float(value_clean[:-2] + "." + value_clean[-2:])
                                else:
                                    depocu_fiyat = float(value_clean)
                            logger.debug(f"{self.name}: Depocu Fiyatı: {depocu_fiyat}")

                        elif "kurum" in label and "isk" in label:
                            kurum_isk = float(value.replace(",", ".")) if value else 0
                            logger.debug(f"{self.name}: Kurum İsk: {kurum_isk}%")

                except Exception as e:
                    continue

            return depocu_fiyat, kurum_isk

        except Exception as e:
            logger.error(f"{self.name}: Depocu fiyat/iskonto okuma hatası: {e}")
            return None, None

    def get_net_tutar_hesapla(self):
        """Selçuk'ta 1 adet için Net Tutar hesapla

        Mikt. alanına 1 yazıp Hesapla butonuna basarak net tutarı alır.

        Returns:
            float: Net tutar veya None
        """
        try:
            self.switch_to_tab()

            # Miktar alanını bul ve 1 yaz
            miktar_input = self.wait_for_element(By.ID, "txtMiktar")
            if not miktar_input:
                logger.warning(f"{self.name}: txtMiktar alanı bulunamadı")
                return None

            logger.debug(f"{self.name}: Miktar alanı bulundu, '1' yazılıyor...")
            miktar_input.clear()
            time.sleep(0.1)
            miktar_input.send_keys("1")
            time.sleep(0.3)

            # Hesapla butonuna tıkla
            try:
                hesapla_btn = self.driver.find_element(By.ID, "aHesapla")

                # Buton görünür değilse scroll yap
                if not hesapla_btn.is_displayed():
                    logger.debug(f"{self.name}: Hesapla butonu görünmüyor, scroll yapılıyor...")
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", hesapla_btn)
                    time.sleep(0.2)

                logger.debug(f"{self.name}: Hesapla butonuna tıklanıyor...")
                hesapla_btn.click()
            except Exception as btn_err:
                logger.error(f"{self.name}: Hesapla butonu tıklanamadı: {btn_err}")
                return None

            time.sleep(0.8)  # Hesaplama için bekle

            # Net Tutar'ı oku
            try:
                net_tutar_elem = self.driver.find_element(By.ID, "spnNetTutar")
                net_tutar_text = net_tutar_elem.text.strip()
                logger.debug(f"{self.name}: spnNetTutar değeri: '{net_tutar_text}'")
            except Exception as elem_err:
                logger.error(f"{self.name}: spnNetTutar elementi bulunamadı: {elem_err}")
                return None

            if net_tutar_text:
                # Format tespiti:
                # - "87.50" veya "1608.09" → nokta ondalık (İngilizce)
                # - "87,50" veya "1.608,09" → virgül ondalık (Türkçe)

                # Virgül varsa Türkçe format
                if "," in net_tutar_text:
                    # Türkçe: "1.608,09" → binlik nokta, ondalık virgül
                    net_tutar_text_clean = net_tutar_text.replace(".", "").replace(",", ".")
                else:
                    # İngilizce: "1608.09" veya "87.50" → ondalık nokta
                    net_tutar_text_clean = net_tutar_text

                try:
                    net_tutar = float(net_tutar_text_clean)
                    logger.info(f"{self.name}: ✓ Net Tutar (1 adet): {net_tutar:.2f} TL (ham: '{net_tutar_text}')")
                    return net_tutar
                except ValueError as ve:
                    logger.error(f"{self.name}: Net tutar parse hatası: '{net_tutar_text}' -> '{net_tutar_text_clean}' - {ve}")
                    return None
            else:
                logger.warning(f"{self.name}: spnNetTutar boş döndü")
                return None

        except Exception as e:
            logger.error(f"{self.name}: Net tutar hesaplama hatası: {e}")
            return None

    def get_mf_bilgisi(self):
        """Selçuk'tan MF (Mal Fazlası) bilgisini oku

        Kampanya tablosundaki MF şartlarını okur (örn: 5+1, 10+3)

        Returns:
            list: [{"min_adet": int, "mf": int}, ...] veya boş liste
        """
        try:
            self.switch_to_tab()
            mf_listesi = []

            # Sayfanın yüklenmesi için kısa bekle
            time.sleep(0.3)

            # Kampanya tablosundaki satırları bul
            rows = self.driver.find_elements(By.CSS_SELECTOR, "#tblKampanyalar tbody tr")
            logger.debug(f"{self.name}: Kampanya tablosunda {len(rows)} satır bulundu")

            for row in rows:
                try:
                    # Tüm span'ları bul (nested table içindekiler dahil)
                    spans = row.find_elements(By.TAG_NAME, "span")
                    logger.debug(f"{self.name}: Satırda {len(spans)} span bulundu")

                    for span in spans:
                        text = span.text.strip()
                        logger.debug(f"{self.name}: Span text: '{text}'")

                        # MF formatı: "7+1", "5+1", "10+3" vb.
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
                except Exception as row_err:
                    logger.debug(f"{self.name}: Satır okuma hatası: {row_err}")
                    continue

            # Tekrar eden kayıtları kaldır
            unique_mf = []
            seen = set()
            for item in mf_listesi:
                key = (item["min_adet"], item["mf"])
                if key not in seen:
                    seen.add(key)
                    unique_mf.append(item)

            if unique_mf:
                logger.info(f"{self.name}: ✓ Toplam {len(unique_mf)} MF şartı bulundu: {unique_mf}")
            else:
                logger.info(f"{self.name}: MF şartı bulunamadı")

            return unique_mf

        except Exception as e:
            logger.error(f"{self.name}: MF bilgisi okuma hatası: {e}")
            return []

    def hesapla_birim_fiyat(self, net_tutar, mf_bilgisi):
        """MF durumuna göre birim fiyat hesapla

        Normal ürün: Birim Fiyat = Net Tutar
        7+1 kampanyalı: Birim Fiyat = Net Tutar × 7 / 8

        Args:
            net_tutar: 1 adet için net tutar
            mf_bilgisi: MF şartları listesi

        Returns:
            float: Hesaplanmış birim fiyat
        """
        if not net_tutar:
            return None

        if not mf_bilgisi:
            # MF yok, direkt net tutar
            return net_tutar

        # İlk MF şartını kullan (genelde en düşük adetli olan)
        ilk_mf = mf_bilgisi[0]
        min_adet = ilk_mf["min_adet"]
        mf = ilk_mf["mf"]

        # Birim fiyat = Net Tutar × min_adet / (min_adet + mf)
        toplam_adet = min_adet + mf
        birim_fiyat = (net_tutar * min_adet) / toplam_adet

        logger.info(f"{self.name}: Birim fiyat hesaplandı: {net_tutar} × {min_adet} / {toplam_adet} = {birim_fiyat:.2f}")

        return birim_fiyat

    def get_satis_kosullari(self):
        """Selçuk'tan satış koşulları tablosunu oku (MF, fiyat vb.)

        YENİ YÖNTEM:
        1. ÖNCE MF bilgisini oku (HESAPLA'dan önce!)
        2. Mikt. alanına 1 yaz, Hesapla'ya bas
        3. spnNetTutar'dan net tutarı oku
        4. MF varsa: birim_fiyat = net_tutar × min_adet / (min_adet + mf)
        5. MF yoksa: birim_fiyat = net_tutar

        Returns:
            list: [{"min_adet": int, "mf": int, "birim_fiyat": float}, ...]
        """
        try:
            self.switch_to_tab()
            kosullar = []

            # 1. ÖNCE MF bilgisini al (HESAPLA'ya basmadan önce!)
            mf_bilgisi = self.get_mf_bilgisi()
            logger.info(f"{self.name}: MF bilgisi okundu: {mf_bilgisi}")

            # 2. Net Tutar'ı hesapla (1 adet için)
            net_tutar = self.get_net_tutar_hesapla()

            if not net_tutar:
                logger.warning(f"{self.name}: Net tutar alınamadı, eski yönteme geçiliyor")
                return self._get_satis_kosullari_eski()

            logger.info(f"{self.name}: Net Tutar: {net_tutar}")

            # 3. Birim fiyat hesapla
            if mf_bilgisi:
                # MF var - önce normal fiyatı ekle
                kosullar.append({
                    "min_adet": 1,
                    "mf": 0,
                    "birim_fiyat": net_tutar,
                    "vade": 0
                })
                logger.info(f"{self.name}: Normal fiyat (MF yok): {net_tutar:.2f}")

                # Her MF şartı için birim fiyat hesapla
                for mf_item in mf_bilgisi:
                    min_adet = mf_item["min_adet"]
                    mf = mf_item["mf"]
                    toplam_adet = min_adet + mf

                    # Birim fiyat = Net Tutar × min_adet / toplam_adet
                    birim_fiyat = (net_tutar * min_adet) / toplam_adet

                    kosullar.append({
                        "min_adet": min_adet,
                        "mf": mf,
                        "birim_fiyat": birim_fiyat,
                        "vade": 0
                    })

                    logger.info(f"{self.name}: MF {min_adet}+{mf} birim fiyat: {net_tutar} × {min_adet} / {toplam_adet} = {birim_fiyat:.2f}")
            else:
                # MF yok - direkt net tutar
                kosullar.append({
                    "min_adet": 1,
                    "mf": 0,
                    "birim_fiyat": net_tutar,
                    "vade": 0
                })
                logger.info(f"{self.name}: MF yok, birim fiyat: {net_tutar}")

            logger.info(f"{self.name}: {len(kosullar)} satış koşulu bulundu: {kosullar}")
            return kosullar

        except Exception as e:
            logger.error(f"{self.name}: Satış koşulları okuma hatası: {e}")
            return []

    def _get_satis_kosullari_eski(self):
        """Eski yöntem - fallback olarak kullanılır"""
        try:
            kosullar = []
            depocu_fiyat, kurum_isk = self.get_depocu_fiyat_ve_iskonto()

            if depocu_fiyat and kurum_isk is not None:
                normal_fiyat = depocu_fiyat * (1 - kurum_isk / 100)
                kosullar.append({
                    "min_adet": 1,
                    "mf": 0,
                    "birim_fiyat": normal_fiyat,
                    "vade": 0
                })

            return kosullar
        except:
            return []

    def check_stock_status(self):
        """Selçuk'ta stok durumunu kontrol et

        Öncelik sırası:
        1. "Siparişe Ekle" butonu → STOKTA VAR
        2. "Lütfen Satış Temsilcinizle Görüşünüz!" → ÖZEL DURUM (Depoyu Ara)
        3. "Şu An Stokta Bulunmamaktadır!" → STOKTA YOK

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

            # Satış koşullarını al (zaten Alliance formatında)
            satis_kosullari = self.get_satis_kosullari()

            # İlk fiyatı al
            fiyat = satis_kosullari[0]["birim_fiyat"] if satis_kosullari else None

            # En iyi MF şartını bul
            sart = None
            mf_kosullar = [k for k in satis_kosullari if k["mf"] > 0]
            if mf_kosullar:
                en_iyi = max(mf_kosullar, key=lambda x: x["mf"] / x["min_adet"] if x["min_adet"] > 0 else 0)
                sart = f"{en_iyi['min_adet']}+{en_iyi['mf']}"
                logger.info(f"{self.name}: 📦 Mal fazlası bulundu: {sart}")

            # Sayfa içeriğini al
            page_source = self.driver.page_source
            page_source_lower = page_source.lower()

            # 1. ÖNCELİK: "Siparişe Ekle" butonu kontrolü → STOKTA VAR
            try:
                siparise_ekle = self.driver.find_element(By.ID, "aSiparisEkle")
                element_classes = siparise_ekle.get_attribute("class") or ""
                element_text = siparise_ekle.text.strip()

                if "disabled" not in element_classes.lower() and "siparişe ekle" in element_text.lower():
                    logger.info(f"{self.name}: ✓ 'Siparişe Ekle' butonu aktif - STOKTA VAR")
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

            # 2. "Lütfen Satış Temsilcinizle Görüşünüz!" → ÖZEL DURUM
            if "lütfen satış temsilcinizle görüşünüz" in page_source_lower or \
               "satış temsilcinizle görüşünüz" in page_source_lower or \
               "internet üzerinden satılmamaktadır" in page_source_lower:
                logger.info(f"{self.name}: ⚠ Özel Durum - Depoyu Ara (Satış Temsilcisi)")
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
                logger.info(f"{self.name}: ✗ 'Şu An Stokta Bulunmamaktadır!' - STOKTA YOK")
                return {
                    "stok_var": False,
                    "mesaj": "Stokta Yok",
                    "detay": "Şu An Stokta Bulunmamaktadır!",
                    "fiyat": fiyat,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # Ek kontroller
            if "sipariş verilemez" in page_source_lower:
                logger.info(f"{self.name}: ✗ Sipariş verilemez - STOKTA YOK")
                return {
                    "stok_var": False,
                    "mesaj": "Stokta Yok",
                    "detay": "Sipariş verilemez",
                    "fiyat": fiyat,
                    "sart": sart,
                    "satis_kosullari": satis_kosullari
                }

            # Hiçbir durum tespit edilemedi
            logger.warning(f"{self.name}: ⚠ Durum belirlenemedi")
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
