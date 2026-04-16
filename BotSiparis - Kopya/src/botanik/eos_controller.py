"""
Botanik EOS otomasyon modülü
"""
import time
from datetime import datetime
import pyperclip
import win32gui
from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError
from ..utils import logger, BOTANIK_ELEMENTS


def turkish_lower(s):
    """Turkish-safe lowercase conversion

    Python'un .lower() fonksiyonu Turkish karakterleri doğru işlemez:
    - İ (noktalı büyük i) → Python i̇ yapar (i + combining dot), doğrusu i
    - I (noktasız büyük i) → Python i yapar, doğrusu ı

    Bu fonksiyon önce Turkish büyük harfleri değiştirir, sonra lower() yapar.
    """
    if not s:
        return ""
    return s.replace('İ', 'i').replace('I', 'ı').lower()


class BotanikEOSController:
    """Botanik EOS uygulamasını kontrol eder"""

    def __init__(self):
        self.app = None
        self.main_window = None
        self.gun_sayisi = 30  # Varsayılan (controller tarafından güncellenecek)
        self.gui = None  # GUI referansı (pause kontrolü için)
        self.cached_total_rows = None
        self.table_prepared = False
        self.date_sorted = False  # Cache: Tarih sıralama yapıldı mı?
        self.current_row_cache = None  # Cache: Şu anda hangi satırdayız (hızlı scroll için)

    def connect(self):
        """Açık olan Botanik EOS uygulamasına bağlan

        Eğer zaten bağlıysa tekrar bağlanmaz (browser gibi sürekli bağlı kalır).
        """
        # Zaten bağlıysa ve pencere hala açıksa tekrar bağlanma
        if self.app and self.main_window:
            try:
                # Pencere hala var mı kontrol et
                if self.main_window.exists(timeout=0.5):
                    logger.debug("✓ Sipariş Yardımcısı zaten bağlı (yeniden bağlanmaya gerek yok)")
                    return True
            except:
                # Bağlantı kopmuş, yeniden bağlanacak
                logger.info("Sipariş Yardımcısı bağlantısı kopmuş, yeniden bağlanılıyor...")
                pass

        # İlk bağlantı veya bağlantı kopmuşsa yeniden bağlan
        logger.info("Botanik EOS'a bağlanılıyor...")
        if self._connect_to_siparis_window():
            return True

        logger.warning("Sipariş Yardımcısı penceresi bulunamadı veya açılamadı, 'Botanikte Sipariş' butonuna basılacak...")
        if self._open_siparis_helper_from_toolbar():
            logger.info("Sipariş Yardımcısı açılması için yeniden bağlanılıyor...")
            time.sleep(1.5)
            if self._connect_to_siparis_window():
                return True

        logger.error("Botanik EOS bulunamadı! Lütfen uygulamayı açın.")
        return False

    def _connect_to_siparis_window(self):
        """Sipariş Yardımcısı penceresine bağlanmayı dener"""
        try:
            # "Sipariş Yardımcısı" penceresine bağlan
            self.app = Application(backend="uia").connect(title="Sipariş Yardımcısı")
            self.main_window = self.app.window(title="Sipariş Yardımcısı")

            logger.info("Botanik EOS'a başarıyla bağlanıldı")

            # Program ilk açıldığında Sipariş Yardımcısı'nı sol üst köşeye konumlandır
            # Daha uzun bekle ve birkaç kez dene
            time.sleep(0.5)  # 0.2 → 0.5 saniye (pencere tamamen yüklensin)

            for attempt in range(3):
                try:
                    self.position_for_ordering()
                    logger.info("✓ Sipariş Yardımcısı başlangıçta konumlandırıldı")
                    break
                except Exception as e:
                    if attempt < 2:
                        logger.debug(f"Konumlandırma denemesi {attempt + 1} başarısız, tekrar deneniyor: {e}")
                        time.sleep(0.3)
                    else:
                        logger.warning(f"Konumlandırma başarısız oldu (3 deneme): {e}")

            return True
        except ElementNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Botanik EOS'a bağlanırken hata: {e}")
            return False

    def _open_siparis_helper_from_toolbar(self):
        """BotanikEOS ana ekranındaki 'Botanikte Sipariş' butonuna bas"""
        try:
            botanik_app = Application(backend="uia").connect(title_re=r"^BotanikEOS.*")
            botanik_window = botanik_app.window(title_re=r"^BotanikEOS.*")
        except ElementNotFoundError:
            logger.error("BotanikEOS ana penceresi bulunamadı, 'Botanikte Sipariş' butonuna erişilemiyor.")
            return False
        except Exception as e:
            logger.error(f"BotanikEOS ana penceresine bağlanılırken hata: {e}")
            return False

        try:
            botanik_window.set_focus()
        except Exception:
            pass

        button = None

        # Yöntem 1: Doğrudan "Sipariş" ismini ara (en hızlı ve güvenilir - inspect'ten aldık)
        button_titles = [
            "Sipariş",           # Inspect'ten gelen tam isim
            "Botanikte Sipariş", # Alternatif isimler
            "Botanikte\nSipariş",
            "Sipariş ",
            "Sipariş\n"
        ]

        for title in button_titles:
            try:
                spec = botanik_window.child_window(title=title, control_type="Button")
                if spec.exists(timeout=0.8):
                    button = spec.wrapper_object()
                    logger.debug(f"'Sipariş' butonu bulundu (title='{title}')")
                    break
            except Exception as e:
                logger.debug(f"Buton araması başarısız (title='{title}'): {e}")
                continue

        # Yöntem 2: Tüm butonları tara ve isimle eşleştir
        if not button:
            try:
                logger.debug("Tüm butonlar taranıyor...")
                buttons = botanik_window.descendants(control_type="Button")
                for btn in buttons:
                    try:
                        text = btn.window_text()
                    except Exception:
                        continue

                    if text is None:
                        continue
                    text_clean = text.replace("\n", " ").strip()

                    if not text_clean:
                        continue

                    # "Botanikte Sipariş" veya sadece "Sipariş"
                    if "Botanikte" in text_clean and "Sipariş" in text_clean:
                        button = btn
                        logger.debug(f"'Sipariş' butonu bulundu (text='{text_clean}')")
                        break

                    if text_clean == "Sipariş":
                        button = btn
                        logger.debug(f"'Sipariş' butonu bulundu (text='{text_clean}')")
                        break
            except Exception as e:
                logger.debug(f"'Botanikte Sipariş' butonu aranırken hata: {e}")

        # Yöntem 3: ToolBar içinde ara (ToolStrip1 içindeki buton)
        if not button:
            try:
                logger.debug("ToolBar içinde 'Sipariş' butonu aranıyor...")
                toolbars = botanik_window.descendants(control_type="ToolBar")
                for toolbar in toolbars:
                    try:
                        toolbar_buttons = toolbar.descendants(control_type="Button")
                        for btn in toolbar_buttons:
                            text = btn.window_text()
                            if text and "Sipariş" in text.replace("\n", " "):
                                button = btn
                                logger.debug(f"'Sipariş' butonu ToolBar'da bulundu (text='{text}')")
                                break
                        if button:
                            break
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"ToolBar araması başarısız: {e}")

        # Yöntem 4: Pozisyona göre ara (son çare - Inspect'ten pozisyon: 124, 52)
        if not button:
            try:
                logger.debug("Pozisyona göre buton aranıyor (124, 52 civarı)...")
                buttons = botanik_window.descendants(control_type="Button")
                for btn in buttons:
                    try:
                        rect = btn.rectangle()
                        # Pozisyon yaklaşık (124, 52) civarında mı? (tolerans: 60 piksel)
                        if abs(rect.left - 124) < 60 and abs(rect.top - 52) < 60:
                            text = btn.window_text()
                            if text and "Sipariş" in text:
                                button = btn
                                logger.debug(f"'Sipariş' butonu bulundu (pozisyon: {rect.left}, {rect.top})")
                                break
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"Pozisyona göre arama başarısız: {e}")

        if not button:
            logger.error("'Sipariş' butonu bulunamadı (4 yöntem denendi).")
            return False

        try:
            button.click_input()
            logger.info("✓ 'Sipariş' butonuna tıklandı.")
            return True
        except Exception as e:
            logger.error(f"'Sipariş' butonuna tıklanamadı: {e}")
            return False

    def click_yoklar_button(self):
        """Yoklar butonuna tıkla (opsiyonel - normal sipariş için kullanılmaz)"""
        try:
            logger.info("Yoklar butonuna tıklanıyor...")
            yoklar_btn = self.main_window.child_window(title=BOTANIK_ELEMENTS["yoklar_button"], control_type="Button")
            yoklar_btn.click_input()
            time.sleep(1)  # Listenin yüklenmesi için bekle
            logger.info("Yoklar listesi açıldı")
            return True
        except Exception as e:
            logger.error(f"Yoklar butonuna tıklanırken hata: {e}")
            return False

    def _get_visible_top_row(self):
        """Görünür olan en üst satırın numarasını al"""
        try:
            all_rows = self.main_window.descendants(control_type="DataItem")
            visible_rows = []

            for item in all_rows:
                try:
                    text = item.window_text()  # BAŞTA BOŞLUK OLMAMALI - .strip() YOK!
                    # BÜYÜK/KÜÇÜK HARF DUYARLI: "Satır {num}" formatı (büyük S)
                    # Regex ile kontrol: ^Satır \d+$ (sayıyla bitmeli, başta boşluk RED)
                    import re
                    match = re.match(r'^Satır (\d+)$', text)
                    if match:
                        row_num = int(match.group(1))
                        # Y kontrol et - SADECE ÜST TABLO
                        try:
                            rect = item.rectangle()
                            if rect.top < 400:
                                visible_rows.append(row_num)
                        except:
                            # Rectangle alınamazsa yine de ekle
                            visible_rows.append(row_num)
                except:
                    continue

            return min(visible_rows) if visible_rows else None
        except Exception as e:
            logger.debug(f"Görünür satır kontrolü yapılamadı: {e}")
            return None

    def scroll_table_to_top(self):
        """Tabloyu en başa kaydır - Satır 1'in görünür olmasını sağla

        Ctrl+Home tuşu kullanarak tabloyu en üste kaydırır.
        """
        try:
            logger.info("Tablo başa kaydırılıyor (Ctrl+Home metodu)...")

            # Mevcut durumu kontrol et
            current_top = self._get_visible_top_row()
            if current_top == 1:
                logger.info("✓ Tablo zaten en üstte (Satır 1 görünüyor)!")
                return True

            if current_top:
                logger.info(f"Şu anda görünür en üst satır: Satır {current_top}")

            # Pencereyi öne getir
            self.main_window.set_focus()
            time.sleep(0.3)

            # İlk hücreyi bul ve focus yap
            data_items = self.main_window.descendants(control_type="DataItem")
            if not data_items:
                logger.warning("DataItem bulunamadı!")
                return False

            first_cell = data_items[0]
            first_cell.set_focus()
            time.sleep(0.2)

            # Ctrl+Home gönder (3 kez)
            logger.info("Ctrl+Home gönderiliyor...")
            for i in range(3):
                first_cell.type_keys("^{HOME}")
                time.sleep(0.3)

            # Kontrol et
            time.sleep(0.5)
            final_top = self._get_visible_top_row()
            if final_top == 1:
                logger.info("✓ Tablo başarıyla en üste kaydırıldı (Satır 1 görünüyor)!")
                return True
            else:
                logger.warning(f"Scroll sonrası görünür satır: {final_top}")
                return False

        except Exception as e:
            logger.error(f"Tablo başa kaydırılırken hata: {e}")
            return False

    def get_total_row_count(self, refresh=False):
        """Alt çubuktan toplam satır sayısını oku

        Returns:
            int: Toplam satır sayısı (örn: 33)
        """
        if not refresh and self.cached_total_rows is not None:
            return self.cached_total_rows

        try:
            kalem_elem = None
            try:
                kalem_elem = self.main_window.child_window(title_re=r".*Kalem$", control_type="Text")
                if kalem_elem.exists(timeout=0.5):
                    kalem_elem = kalem_elem.wrapper_object()
                else:
                    kalem_elem = None
            except Exception:
                kalem_elem = None

            text_candidates = []
            if kalem_elem:
                text_candidates.append(kalem_elem.window_text())
            else:
                all_texts = self.main_window.descendants(control_type="Text")
                for elem in all_texts:
                    try:
                        text_candidates.append(elem.window_text())
                    except Exception:
                        continue

            for text in text_candidates:
                if not text or "Kalem" not in text:
                    continue
                try:
                    count_str = text.replace("Kalem", "").strip()
                    total_count = int(count_str)
                    self.cached_total_rows = total_count
                    logger.info(f"📊 Toplam satır sayısı: {total_count} ('{text}' elementinden okundu)")
                    return total_count
                except ValueError:
                    continue

            logger.warning("Toplam satır sayısı okunamadı, varsayılan tarama yapılacak")
            return None
        except Exception as e:
            logger.warning(f"Toplam satır sayısı okunamadı: {e}")
            return None

    def get_row_numbers(self):
        """Tablodaki satır numaralarını al

        Toplam satır sayısı biliniyorsa (242 Kalem gibi), direkt range(1, 243) döndürür.
        Bilinmiyorsa eski scroll yöntemiyle tarar.

        Returns:
            list: Satır numaraları listesi (örn: [1, 2, 3, ..., 242])
        """
        try:
            # Önce toplam satır sayısını oku
            expected_total = self.get_total_row_count()

            # ✅ EĞER TOPLAM SATIR SAYISI BİLİNİYORSA, DİREKT DÖNDÜR!
            if expected_total:
                logger.info(f"✅ Toplam satır sayısı biliniyor: {expected_total}")
                logger.info(f"📋 Satır listesi oluşturuluyor: [1, 2, 3, ..., {expected_total}]")
                return list(range(1, expected_total + 1))

            # ⚠️ TOPLAM SATIR SAYISI BİLİNMİYORSA, ESKİ SCROLL YÖNTEMİNİ KULLAN
            logger.warning("⚠️ Toplam satır sayısı bilinmiyor, scroll ile taranacak...")

            # Önce tablonun başına git
            self.scroll_table_to_top()

            all_row_numbers = set()
            no_new_count = 0  # Kaç iterasyon yeni satır bulunamadı
            max_no_new = 5  # 5 kez yeni satır bulunamazsa dur
            max_iterations = 300  # Sonsuz döngü önlemi
            iteration = 0

            logger.debug(f"Satır numaraları taranıyor... (Beklenen: {expected_total if expected_total else '?'})")

            while iteration < max_iterations:
                # Pause kontrolü - Duraklatıldıysa bekle
                if self.gui and hasattr(self.gui, 'pause_event'):
                    self.gui.pause_event.wait()

                last_count = len(all_row_numbers)

                # Görünen "Stok satır X" elementlerini bul
                all_items = self.main_window.descendants(control_type="DataItem")

                for item in all_items:
                    try:
                        title = item.window_text()
                        # "Stok satır 22" formatından satır numarasını çıkar
                        if title.startswith("Stok satır "):
                            row_num_str = title.replace("Stok satır ", "")
                            row_num = int(row_num_str)
                            all_row_numbers.add(row_num)
                    except:
                        continue

                # Yeni satır bulunduysa counter'ı sıfırla
                if len(all_row_numbers) > last_count:
                    no_new_count = 0
                    yeni_satir_sayisi = len(all_row_numbers) - last_count
                    logger.debug(f"Iteration {iteration}: {len(all_row_numbers)} satır bulundu (+{yeni_satir_sayisi} yeni)")
                else:
                    no_new_count += 1
                    logger.debug(f"Iteration {iteration}: Yeni satır yok ({no_new_count}/{max_no_new}) - Toplam: {len(all_row_numbers)}")

                # Eğer beklenen sayıya ulaştıysak dur
                if expected_total and len(all_row_numbers) >= expected_total:
                    logger.debug(f"Beklenen {expected_total} satıra ulaşıldı, tarama sonlandırılıyor")
                    break

                # max_no_new kez üst üste yeni satır bulunamazsa dur
                if no_new_count >= max_no_new:
                    logger.debug(f"{max_no_new} kez yeni satır bulunamadı, tarama sonlandırılıyor")
                    break

                # EKRANI SCROLL ET: En yüksek satır numarasına git
                if all_row_numbers:
                    # Bulunan en yüksek satırı al
                    max_row = max(all_row_numbers)
                    try:
                        # O satırın Stok hücresine focus et - bu ekranı scroll ettirir
                        cell_name = f"Stok satır {max_row}"
                        cell = self.main_window.child_window(title=cell_name, control_type="DataItem", found_index=0)
                        if cell.exists(timeout=0.5):
                            cell.set_focus()
                            time.sleep(0.1)
                    except:
                        pass

                # Sonra DOWN ile biraz daha aşağı in
                if all_items:
                    all_items[0].type_keys("{DOWN}{DOWN}{DOWN}")  # 3 satır aşağı
                    time.sleep(0.2)

                iteration += 1

            # Eğer beklenen sayıya ulaşamadıysak, END tuşuyla sona git ve tekrar tara
            if expected_total and len(all_row_numbers) < expected_total:
                logger.warning(f"⚠️ İlk taramada sadece {len(all_row_numbers)}/{expected_total} satır bulundu")
                logger.info("🔄 Ctrl+End ile sona gidip tekrar taranıyor...")

                # Sona git
                retry_items = self.main_window.descendants(control_type="DataItem")
                if retry_items:
                    retry_items[0].set_focus()
                    retry_items[0].type_keys("^{END}")  # Ctrl+End
                    time.sleep(0.5)

                # Son satırları tekrar tara
                all_items = self.main_window.descendants(control_type="DataItem")
                for item in all_items:
                    try:
                        title = item.window_text()
                        if title.startswith("Stok satır "):
                            row_num_str = title.replace("Stok satır ", "")
                            row_num = int(row_num_str)
                            all_row_numbers.add(row_num)
                    except:
                        continue

                logger.info(f"🔄 İkinci tarama sonrası: {len(all_row_numbers)} satır")

            # Sıralı liste olarak döndür
            sorted_rows = sorted(list(all_row_numbers))
            logger.info(f"✅ Toplam {len(sorted_rows)} satır bulundu: {sorted_rows[:5]}...{sorted_rows[-5:] if len(sorted_rows) > 5 else sorted_rows}")

            # KONTROL: Beklenen sayıyla karşılaştır
            if expected_total:
                if len(sorted_rows) < expected_total:
                    logger.warning(f"⚠️ UYARI: Sadece {len(sorted_rows)} satır bulundu, {expected_total} bekleniyordu!")
                    logger.warning(f"   Eksik satırlar: {expected_total - len(sorted_rows)} adet")
                elif len(sorted_rows) == expected_total:
                    logger.info(f"✓ Tüm satırlar başarıyla tarandı! ({len(sorted_rows)}/{expected_total})")
                else:
                    logger.info(f"✓ Beklenen sayıdan fazla satır bulundu: {len(sorted_rows)}/{expected_total}")

            # Başa geri dön (işleme baştan başlayacak)
            logger.debug("Tablo başa kaydırılıyor...")
            self.scroll_table_to_top()

            return sorted_rows

        except Exception as e:
            logger.warning(f"Satır numaraları alınırken hata: {e}")
            return []

    def get_all_product_names_with_rows(self):
        """Botanik'teki tüm ürün isimlerini ve satır numaralarını hızlıca oku

        Bu fonksiyon devam taraması sırasında GUI listesiyle karşılaştırma için kullanılır.
        Sadece isim ve satır numarası okunur - barkod, depo araması vs. YAPILMAZ.

        NOT: BotTak8'deki "Günü Gelenler Kopyala" mantığı kullanılıyor.
        - Page Down ile scroll yapılıyor
        - Her scroll'da sadece görünen satırlar okunuyor
        - Son scroll'da tüm satırlar okunuyor (atlama yok)

        Returns:
            dict: {ürün_adı_lowercase: satır_numarası} dictionary
        """
        try:
            import pyautogui

            if not self.main_window:
                logger.warning("main_window bulunamadı, ürün isimleri okunamıyor")
                return {}

            # Toplam satır sayısını al
            total_rows = self.get_total_row_count(refresh=True)
            if not total_rows:
                logger.warning("Toplam satır sayısı okunamadı")
                return {}

            logger.info(f"🔍 Botanik'ten {total_rows} ürün ismi okunuyor (hızlı sync)...")

            # Tablonun başına git
            self.scroll_table_to_top()
            time.sleep(0.3)

            # {isim: satır_no} dictionary
            product_rows = {}
            okunan_satirlar = set()

            # İlk satıra focus ver (scroll için gerekli)
            try:
                first_cell = self.main_window.child_window(title="Stok satır 1", control_type="DataItem", found_index=0)
                if first_cell.exists(timeout=0.5):
                    first_cell.click_input()
                    time.sleep(0.1)
            except:
                pass

            # Scroll ile oku (BotTak8 mantığı)
            scroll_sayisi = 0
            max_scroll = 150  # Daha fazla scroll izni
            no_new_count = 0  # Yeni satır bulunamayan scroll sayısı

            while scroll_sayisi < max_scroll:
                # Görünen "Ürün Adı" elementlerini bul
                try:
                    all_items = self.main_window.descendants(control_type="DataItem")
                except:
                    all_items = []

                # Bu scroll'da görünen satırları topla
                gorunen_satirlar = []
                for item in all_items:
                    try:
                        title = item.window_text()
                        if title and title.startswith("Ürün Adı satır "):
                            satir_no = int(title.replace("Ürün Adı satır ", ""))
                            gorunen_satirlar.append((satir_no, item))
                    except:
                        continue

                # Sırala
                gorunen_satirlar.sort(key=lambda x: x[0])

                # Tablonun sonuna yaklaştık mı? (son satır görünüyorsa atlama yapma)
                max_gorunen = max([s for s, _ in gorunen_satirlar]) if gorunen_satirlar else 0
                son_scrollda_miyiz = max_gorunen >= total_rows

                # Son scroll'da değilsek son 2 satırı atla (kısmen görünebilir)
                if son_scrollda_miyiz:
                    guvenli_satirlar = gorunen_satirlar  # Hiç atlama
                else:
                    guvenli_satirlar = gorunen_satirlar[:-2] if len(gorunen_satirlar) > 2 else gorunen_satirlar

                yeni_okunan = 0
                for satir_no, item in guvenli_satirlar:
                    if satir_no in okunan_satirlar:
                        continue

                    try:
                        # Sadece ürün adını oku
                        try:
                            value = item.legacy_properties().get('Value', '')
                        except:
                            value = ""

                        if value and value.strip() and value != "-":
                            product_rows[turkish_lower(value.strip())] = satir_no
                            okunan_satirlar.add(satir_no)
                            yeni_okunan += 1
                    except:
                        pass

                # Tüm satırlar okunduysa dur
                if len(okunan_satirlar) >= total_rows:
                    break

                # Yeni satır okunmadıysa sayacı artır
                if yeni_okunan == 0:
                    no_new_count += 1
                    if no_new_count >= 5:  # 5 scroll boyunca yeni satır yoksa dur
                        logger.info(f"   → 5 scroll yeni satır yok, durduruluyor")
                        break
                else:
                    no_new_count = 0

                # Page Down
                pyautogui.press('pagedown')
                time.sleep(0.15)
                scroll_sayisi += 1

            logger.info(f"✓ Botanik'ten {len(product_rows)} ürün ismi okundu ({scroll_sayisi} scroll)")
            return product_rows

        except Exception as e:
            logger.error(f"Hızlı ürün ismi okuma hatası: {e}")
            return {}

    def get_all_product_names_fast(self):
        """Botanik'teki tüm ürün isimlerini hızlıca oku (sadece isimler seti)

        Returns:
            set: Botanik'te mevcut ürün isimleri seti (küçük harfe çevrilmiş)
        """
        product_rows = self.get_all_product_names_with_rows()
        return set(product_rows.keys())

    def get_product_name_at_row(self, row_num):
        """Belirli bir satırdaki ürün adını oku (Page Down ile scroll)

        Bu fonksiyon sadece belirli bir satırı okur, tüm listeyi taramaz.
        Sync kontrolü için kullanılır: GUI'deki son satır ile Botanik'teki
        aynı satır numarasının ürün adı eşleşiyor mu kontrolü yapar.

        Args:
            row_num: Okunacak satır numarası (1'den başlar)

        Returns:
            str or None: Ürün adı (lowercase) veya bulunamazsa None
        """
        try:
            import pyautogui

            if not self.main_window:
                logger.warning("main_window bulunamadı, satır okunamıyor")
                return None

            logger.info(f"🔍 Botanik satır {row_num} ürün adı okunuyor...")

            # Tablonun başına git
            self.scroll_table_to_top()
            time.sleep(0.2)

            # İlk satıra focus ver
            try:
                first_cell = self.main_window.child_window(title="Stok satır 1", control_type="DataItem", found_index=0)
                if first_cell.exists(timeout=0.3):
                    first_cell.click_input()
                    time.sleep(0.1)
            except:
                pass

            # Page Down ile hedef satıra ulaşana kadar scroll
            scroll_sayisi = 0
            max_scroll = 50

            while scroll_sayisi < max_scroll:
                # Hedef satırı ara
                try:
                    urun_adi_element = self.main_window.child_window(
                        title=f"Ürün Adı satır {row_num}",
                        control_type="DataItem"
                    )

                    if urun_adi_element.exists(timeout=0.3):
                        # Element bulundu, değerini oku
                        try:
                            value = urun_adi_element.legacy_properties().get('Value', '')
                        except Exception:
                            value = ""

                        if value and str(value).strip() and str(value).strip() != "-":
                            product_name = turkish_lower(str(value).strip())
                            logger.info(f"✓ Satır {row_num} ürün adı: '{product_name}' ({scroll_sayisi} scroll)")
                            return product_name
                        else:
                            logger.warning(f"Satır {row_num} ürün adı boş veya geçersiz: '{value}'")
                            return None
                except Exception:
                    pass

                # Page Down ile scroll
                pyautogui.press('pagedown')
                time.sleep(0.12)
                scroll_sayisi += 1

            logger.warning(f"Satır {row_num} bulunamadı ({max_scroll} scroll yapıldı)")
            return None

        except Exception as e:
            logger.error(f"get_product_name_at_row hatası: {e}")
            return None

    def _find_date_header(self):
        """Tarih sütunu başlığını bul"""
        if not self.main_window:
            logger.warning("main_window bulunamadı, tarih başlığı aranamıyor")
            return None

        search_variants = [
            # Inspect32'de görülen format: Control Type = Header
            {"title": "Tarih", "control_type": "Header"},
            {"title": "Tarih", "control_type": "HeaderItem"},
            {"title_re": ".*Tarih.*", "control_type": "Header"},
            {"title_re": ".*Tarih.*", "control_type": "HeaderItem"},
            {"title": "Tarih", "control_type": "Text"},
            {"title_re": ".*Tarih.*", "control_type": "Text"},
            {"best_match": "Tarih"},
        ]

        for idx, params in enumerate(search_variants):
            try:
                logger.debug(f"Tarih başlığı aranıyor ({idx+1}/{len(search_variants)}): {params}")
                header = self.main_window.child_window(**params)
                if header.exists(timeout=0.5):
                    logger.info(f"✓ Tarih başlığı bulundu: {params}")
                    return header
            except Exception as e:
                logger.debug(f"  Arama başarısız: {e}")
                continue

        # Daha geniş arama: HeaderItem
        logger.debug("Geniş arama başlıyor: HeaderItem descendants...")
        try:
            headers = self.main_window.descendants(control_type="HeaderItem")
            logger.debug(f"  {len(headers)} HeaderItem bulundu")
            for header in headers:
                try:
                    text = header.window_text()
                    if text and "tarih" in text.lower():
                        logger.info(f"✓ Tarih başlığı descendants'da bulundu: '{text}'")
                        return header
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"  HeaderItem descendants hatası: {e}")
            pass

        # Daha geniş arama: Header control type
        logger.debug("Geniş arama başlıyor: Header descendants...")
        try:
            headers = self.main_window.descendants(control_type="Header")
            logger.debug(f"  {len(headers)} Header bulundu")
            for header in headers:
                try:
                    text = header.window_text()
                    if text and "tarih" in text.lower():
                        logger.info(f"✓ Tarih başlığı Header descendants'da bulundu: '{text}'")
                        return header
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"  Header descendants hatası: {e}")
            pass

        logger.error("❌ Tarih sütunu başlığı bulunamadı! Hiçbir yöntem çalışmadı.")
        return None

    def _click_date_header(self, header_spec):
        """Tarih başlığına farklı yöntemlerle tıkla"""
        try:
            header = header_spec.wrapper_object()
            # Başlık bilgilerini logla
            try:
                header_name = header.window_text()
                header_rect = header.rectangle()
                logger.info(f"Tarih başlığına tıklanıyor: '{header_name}' @ ({header_rect.left}, {header_rect.top})")
            except:
                logger.info("Tarih başlığına tıklanıyor (bilgiler okunamadı)")
        except Exception as e:
            logger.warning(f"Tarih başlığı erişilemedi: {e}")
            return False

        # 1. ÖNCELİK: click_input (gerçek mouse tıklaması)
        try:
            header.click_input()
            time.sleep(0.15)  # 0.3 → 0.15 (HIZLANDIRILDI)
            logger.info("✓ Tarih başlığına click_input ile tıklandı.")
            return True
        except Exception as e:
            logger.debug(f"click_input başarısız: {e}")

        # 2. invoke() (DefaultAction)
        try:
            header.invoke()
            time.sleep(0.2)
            logger.debug("✓ Tarih başlığının default action'ı çağrıldı.")
            return True
        except Exception as e:
            logger.debug(f"Tarih başlığı default action çalışmadı: {e}")

        # 3. Koordinat ile mouse tıklama
        try:
            rect = header.rectangle()
            from pywinauto import mouse
            midpoint = (rect.left + rect.width() // 2, rect.top + rect.height() // 2)
            mouse.click(button='left', coords=midpoint)
            time.sleep(0.2)
            logger.debug("Tarih başlığına koordinat ile tıklandı.")
            return True
        except Exception as e:
            logger.debug(f"Tarih başlığı koordinat tıklaması başarısız: {e}")

        try:
            filter_btn = header.child_window(title_re=".*ColumnFilterButton", control_type="Button")
            if filter_btn and filter_btn.exists(timeout=0.2):
                filter_btn.click_input()
                time.sleep(0.2)
                logger.debug("Tarih başlığının filtre düğmesine tıklandı.")
                return True
        except Exception as e:
            logger.debug(f"Tarih başlığı filtre düğmesi tıklanamadı: {e}")

        return False

    def _parse_date_text(self, text):
        """Tarih hücre değerini datetime'a çevir"""
        if not text:
            return None

        normalized = str(text).strip()
        if not normalized:
            return None

        normalized = normalized.replace('-', '.').replace('/', '.')
        candidates = [normalized]

        # Saat bilgisi varsa sadece tarih kısmını da dene
        if " " in normalized:
            candidates.append(normalized.split()[0])

        formats = [
            "%d.%m.%Y %H:%M:%S",
            "%d.%m.%Y %H:%M",
            "%d.%m.%Y",
            "%d.%m.%y %H:%M:%S",
            "%d.%m.%y %H:%M",
            "%d.%m.%y",
        ]

        for candidate in candidates:
            for fmt in formats:
                try:
                    return datetime.strptime(candidate, fmt)
                except ValueError:
                    continue

        logger.debug(f"Tarih formatı parse edilemedi: {text}")
        return None

    def _collect_top_dates(self, limit=2):
        """İlk birkaç satırdaki tarih değerlerini oku"""
        tarih_pattern = BOTANIK_ELEMENTS.get("tarih")
        if not tarih_pattern:
            return []

        dates = []
        for row in range(1, limit + 1):
            try:
                self.ensure_column_cell_visible(row, tarih_pattern)
                value = self.get_cell_value(row, tarih_pattern)
                parsed = self._parse_date_text(value)
                if parsed:
                    dates.append(parsed)
            except Exception:
                continue
        return dates

    def ensure_date_sorted(self):
        """Tarih sütununu küçükten büyüğe sıralı hale getir

        Strateji:
        1. İlk DefAction'ı oku (tıklamadan)
        2. "Büyükten Küçüğe Sırala" ise → ZATEN DOĞRU, hiç tıklama!
        3. Değilse → 1. tıklama yap
        4. DefAction kontrol et, doğruysa bitir
        5. Hala yanlışsa → 2. tıklama yap
        6. Son kontrol

        NOT: "Büyükten Küçüğe Sırala" yazıyorsa → Liste KÜÇÜKTEN BÜYÜĞE sıralıdır!
        """
        try:
            header = self._find_date_header()
            if not header:
                logger.warning("Tarih sütunu başlığı bulunamadı, mevcut sıralama kullanılacak.")
                return False

            # 1. İLK DURUM: Tıklamadan DefAction'ı kontrol et
            header_obj = header.wrapper_object()
            initial_def_action = header_obj.legacy_properties().get('DefaultAction', '')
            logger.info(f"📋 İlk DefAction: '{initial_def_action}'")

            # Eğer zaten "Büyükten Küçüğe Sırala" ise → liste küçükten büyüğe sıralı, OK!
            if initial_def_action == "Büyükten Küçüğe Sırala":
                logger.info(f"✓ Tarih sütunu ZATEN küçükten büyüğe sıralı! (Tıklama yapılmadı)")
                return True

            # 2. Yanlışsa 1. TIKLAMA yap
            logger.info("Tarih doğru sıralı değil, 1. tıklama yapılıyor...")
            if not self._click_date_header(header):
                logger.warning("Tarih başlığına 1. tıklama başarısız.")
                return False

            time.sleep(0.5)

            # 3. 1. tıklama sonrası DefAction kontrol et
            header_obj = header.wrapper_object()
            def_action_after_1 = header_obj.legacy_properties().get('DefaultAction', '')
            logger.info(f"📋 1. tıklama sonrası DefAction: '{def_action_after_1}'")

            # "Büyükten Küçüğe Sırala" ise → liste küçükten büyüğe sıralı, OK!
            if def_action_after_1 == "Büyükten Küçüğe Sırala":
                logger.info(f"✓ Tarih sütunu 1. tıklama ile küçükten büyüğe sıralandı!")
                return True

            # 4. Hala yanlışsa 2. TIKLAMA yap
            logger.info(f"Hala doğru değil (DefAction: '{def_action_after_1}'), 2. tıklama yapılıyor...")
            if not self._click_date_header(header):
                logger.warning("Tarih başlığına 2. tıklama başarısız.")
                return False

            time.sleep(0.5)

            # 5. SON KONTROL
            header_obj = header.wrapper_object()
            final_def_action = header_obj.legacy_properties().get('DefaultAction', '')
            logger.info(f"📋 2. tıklama sonrası DefAction: '{final_def_action}'")

            # "Büyükten Küçüğe Sırala" ise → OK!
            if final_def_action == "Büyükten Küçüğe Sırala":
                logger.info(f"✓ Tarih sütunu 2. tıklama ile küçükten büyüğe sıralandı!")
                return True

            # Hala düzelmediyse
            logger.warning(f"❌ Tarih sütunu düzeltilemedi (DefAction: '{final_def_action}')")
            return False

        except Exception as e:
            logger.warning(f"Tarih sütunu ayarlanırken hata: {e}")
            return False

    def prepare_table_for_scan(self):
        """Tabloyu tarama için hazırla (ilk satıra git, tarih sıralama ve satır sayısı okuma)"""
        # Önce tabloyu en başa kaydır
        logger.info("Tablo hazırlığı: ilk satıra kaydırılıyor...")
        self.scroll_table_to_top()

        # Tarih sıralama: Sadece ilk kez yap (cache)
        if not self.date_sorted:
            logger.info("Tablo hazırlığı: tarih sütunu kontrol ediliyor...")
            if self.ensure_date_sorted():
                self.date_sorted = True  # Başarılıysa cache'le
                logger.info("✓ Tarih sıralama tamamlandı ve cache'lendi")
            else:
                logger.warning("Tarih sıralama başarısız, bir dahaki sefer tekrar denenecek")
        else:
            logger.info("Tarih sıralama atlandı (zaten yapılmış)")

        logger.info("Tablo hazırlığı: toplam satır sayısı okunuyor...")
        self.get_total_row_count(refresh=True)
        self.table_prepared = True

    def ensure_row_visible(self, row_num):
        """Satırı görünür hale getir - ARTIK KULLANILMIYOR, BOŞ FONKSIYON

        Args:
            row_num: Satır numarası

        Not: Bu fonksiyon artık hiçbir şey yapmıyor.
             Scroll işlemi click_depo_personel_cell() içinde yapılıyor.
        """
        # STOK SÜTUNUNA GİTME! Gereksiz!
        # Sadece pass (hiçbir şey yapma)
        return True

    def ensure_column_cell_visible(self, row_num, column_pattern):
        """Belirli sütun hücresini görünür hale getir"""
        if not column_pattern:
            return self.ensure_row_visible(row_num)

        cell_name = None
        try:
            cell_name = column_pattern.format(row=row_num)
            spec = self.main_window.child_window(title=cell_name, control_type="DataItem", found_index=0)
            cell = spec.wrapper_object()
            cell.set_focus()
            time.sleep(0.15)  # 0.1'den 0.15'e artırıldı - scroll'un tamamlanması için
            return True
        except Exception as e:
            logger.debug(f"{cell_name or column_pattern} görünür yapılırken hata: {e}")
            return self.ensure_row_visible(row_num)

    def get_cell_value(self, row_num, column_pattern):
        """Belirli satır ve sütundaki değeri oku

        Args:
            row_num: Satır numarası (1'den başlar)
            column_pattern: Sütun ismi pattern'i (örn: "Stok satır {row}")
        """
        try:
            cell_name = column_pattern.format(row=row_num)
            cell = self.main_window.child_window(title=cell_name, control_type="DataItem", found_index=0)

            # Value özelliğini oku
            try:
                # İlk önce legacy_properties ile dene
                value = cell.legacy_properties().get('Value', '')
                if value and str(value).strip():
                    return str(value).strip()
            except:
                pass

            # Alternatif: window_text()
            try:
                value = cell.window_text()
                if value and value != cell_name and str(value).strip():
                    return str(value).strip()
            except:
                pass

            # Son çare: get_value()
            try:
                value = cell.get_value()
                if value and str(value).strip():
                    return str(value).strip()
            except:
                pass

            # Boş değer (bu normal, MinStk vs. boş olabilir)
            return ""
        except Exception as e:
            logger.debug(f"Hücre değeri okunamadı ({cell_name}): {e}")
            return ""  # Hata durumunda da boş string döndür (None değil)

    def get_aciklama_value(self, row_num):
        """Açıklama hücresinin mevcut değerini oku

        Args:
            row_num: Satır numarası

        Returns:
            str: Mevcut açıklama değeri (boşsa "")
        """
        return self.get_cell_value(row_num, BOTANIK_ELEMENTS["aciklama"])

    def click_depo_personel_cell(self, row_num, fast_mode=False):
        """Depo/Personel hücresine tıkla (barkodu panoya kopyalar)

        Args:
            row_num: Satır numarası (1'den başlar)
            fast_mode: True ise hızlı mod (daha az deneme, daha kısa bekleme)
        """
        try:
            cell_name = BOTANIK_ELEMENTS["depo_personel"].format(row=row_num)
            logger.debug(f"Depo/Personel hücresine tıklanıyor: {cell_name}")

            # Hücreyi bul - timeout kısa tut
            try:
                cell = self.main_window.child_window(title=cell_name, control_type="DataItem", found_index=0)
                if not cell.exists(timeout=0.5):  # 2 → 0.5 saniye
                    logger.error(f"Satır {row_num}: Depo/Personel hücresi bulunamadı")
                    return None
            except Exception as e:
                logger.error(f"Satır {row_num}: Depo/Personel hücresi bulunamadı: {e}")
                return None

            # Focus (hızlı modda atla)
            if not fast_mode:
                try:
                    cell.set_focus()
                    time.sleep(0.1)
                except:
                    pass

            # Deneme sayısı ve bekleme (hızlı modda azalt)
            max_attempts = 2 if fast_mode else 3
            click_wait = 0.2 if fast_mode else 0.3

            for attempt in range(max_attempts):
                try:
                    # İlk denemede clipboard temizle
                    if attempt == 0:
                        try:
                            pyperclip.copy("")
                        except:
                            pass

                    # Tıkla
                    cell.click_input(button='left')
                    time.sleep(click_wait)

                    # Barkodu al
                    try:
                        barcode = pyperclip.paste().strip()
                        if barcode and barcode != "":
                            self.current_row_cache = row_num
                            return barcode
                    except Exception as clipboard_err:
                        logger.warning(f"Satır {row_num}: Clipboard hatası (deneme {attempt + 1})")
                        continue

                    if attempt < max_attempts - 1:
                        time.sleep(0.1)

                except Exception as click_err:
                    logger.warning(f"Satır {row_num}: Click hatası (deneme {attempt + 1})")
                    if attempt < max_attempts - 1:
                        time.sleep(0.1)
                        continue

            logger.warning(f"Satır {row_num}: Barkod kopyalanamadı")
            return None
        except Exception as e:
            logger.error(f"Depo/Personel tıklama hatası (satır {row_num}): {e}")
            return None

    def set_mf_value(self, row_num, mf_adet):
        """MF/İht hücresine değer yaz

        Args:
            row_num: Satır numarası
            mf_adet: Yazılacak MF adedi
        """
        try:
            logger.debug(f"[set_mf_value] Satır {row_num} için MF={mf_adet} yazılacak")

            # ensure_row_visible KALDIRILDI - Stok sütununa gitmesin!

            cell_name = BOTANIK_ELEMENTS["mf_iht"].format(row=row_num)
            logger.debug(f"[set_mf_value] Element arıyor: {cell_name}")

            # Hücreyi bul
            cell = self.main_window.child_window(title=cell_name, control_type="DataItem", found_index=0)

            # Element var mı kontrol et
            if not cell.exists(timeout=2):
                logger.error(f"[set_mf_value] Element bulunamadı: {cell_name}")
                return False

            # Y kontrolü KALDIRILDI - Tablo scroll edildiğinde yanlış sonuç veriyor
            # Eski kod: rect.top >= 400 ise atlıyordu ama scroll ile pozisyon değişiyor

            logger.debug(f"[set_mf_value] Element bulundu, double-click yapılıyor...")
            cell.double_click_input()  # Düzenleme moduna gir
            time.sleep(0.1)

            # Mevcut değeri temizle ve yeni değeri yaz
            # DOWN tuşu kullan (ENTER yerine) - sonraki satıra geçer, popup açmaz
            logger.debug(f"[set_mf_value] Değer yazılıyor: {mf_adet}")
            cell.type_keys("^a{BACKSPACE}" + str(mf_adet) + "{DOWN}")
            time.sleep(0.05)

            logger.info(f"[set_mf_value] ✓ Satır {row_num}: MF/İht = {mf_adet} yazıldı")
            return True
        except Exception as e:
            logger.error(f"[set_mf_value] ✗ MF/İht yazılırken hata (satır {row_num}): {e}", exc_info=True)
            return False

    def set_adet_value(self, row_num, adet):
        """ADET hücresine değer yaz

        Args:
            row_num: Satır numarası (1'den başlar)
            adet: Yazılacak adet
        """
        try:
            # ensure_row_visible KALDIRILDI - Stok sütununa gitmesin!

            cell_name = BOTANIK_ELEMENTS["adet"].format(row=row_num)
            logger.debug(f"ADET hücresine {adet} yazılıyor: {cell_name}")

            cell = self.main_window.child_window(title=cell_name, control_type="DataItem", found_index=0)
            cell.double_click_input()  # Düzenleme moduna gir
            time.sleep(0.2)

            # Mevcut değeri temizle ve yeni değeri yaz
            cell.type_keys("^a")  # Ctrl+A (tümünü seç)
            cell.type_keys(str(adet))
            cell.type_keys("{ENTER}")  # Enter ile kaydet

            logger.info(f"Satır {row_num}: ADET = {adet} yazıldı")
            return True
        except Exception as e:
            logger.error(f"ADET yazılırken hata (satır {row_num}): {e}")
            return False

    def set_aciklama_value(self, row_num, text, skip_scroll=False):
        """Açıklama hücresine özet bilgi yaz

        Args:
            row_num: Satır numarası
            text: Yazılacak açıklama (boşsa sadece tire yazılır - eski bilgileri temizler)
            skip_scroll: Sıralı okumada True yapılırsa scroll atlanır (HIZLANDIRMA)
        """
        try:
            # Botanik EOS penceresini öne getir (GUI'ye yanlış tuş girişi olmasın)
            try:
                self.main_window.set_focus()
                time.sleep(0.1)  # Focus geçişi için bekle
            except Exception as e:
                logger.debug(f"Botanik pencere focus hatası: {e}")

            # ÖNEMLİ: Önce satırı görünür hale getir (scroll yap) - SADECE GEREKLİYSE
            if not skip_scroll:
                scroll_result = self.scroll_to_row(row_num)
                if not scroll_result.get("success"):
                    logger.error(f"Scroll başarısız: {scroll_result.get('scroll_info')}")
                    return False
            else:
                logger.debug(f"⚡ Scroll ATLANDI (sıralı okuma) - Satır {row_num}")

            # Açıklama hücresini bul
            cell_name = BOTANIK_ELEMENTS["aciklama"].format(row=row_num)
            logger.debug(f"Açıklama hücresi güncelleniyor: {cell_name} -> '{text}'")

            cell = self.main_window.child_window(title=cell_name, control_type="DataItem", found_index=0)
            if not cell.exists(timeout=2):
                logger.error(f"Açıklama hücresi bulunamadı: {cell_name}")
                return False

            cell.double_click_input()
            time.sleep(0.05)  # 0.1 → 0.05 azaltıldı (hızlandırma)

            # Mevcut değeri temizle ve yeni değeri yaz - CLIPBOARD KULLANMA (kilitleniyor!)
            if text == " ":
                # Sadece boşluk karakteri (depo yok anlamında)
                cell.type_keys("^a{BACKSPACE}{ }{DOWN}")
            elif text and text.strip():
                # Metin varsa direkt type_keys ile yaz (clipboard yerine)
                # TÜM özel karakterleri escape et (virgül ve nokta da dahil)
                escaped_text = (text
                    .replace('{', '{{').replace('}', '}}')
                    .replace('+', '{+}').replace('^', '{^}')
                    .replace('%', '{%}').replace('~', '{~}')
                    .replace('(', '{(}').replace(')', '{)}')
                    .replace(',', '{,}').replace('.', '{.}')
                    .replace(' ', '{ }')  # Boşluk da escape et
                )
                # DOWN (aşağı ok) kullan - doğal şekilde alt satıra geç
                cell.type_keys(f"^a{{BACKSPACE}}{escaped_text}{{DOWN}}")
            else:
                # Boş string veya "-" ise tire yaz
                cell.type_keys("^a{BACKSPACE}-{DOWN}")

            time.sleep(0.05)  # DOWN çok hızlı - 0.1 → 0.05 (DAHA DA HIZLANDIRILDI)

            logger.info(f"Satır {row_num}: Açıklama -> '{text if text else '-'}'")
            return True
        except Exception as e:
            logger.error(f"Açıklama yazılırken hata (satır {row_num}): {e}")
            return False

    def get_monthly_top_row(self, row_num):
        """Sadece Top satırını oku (hızlı versiyon - CSV için)

        Args:
            row_num: Satır numarası (main tablodaki satır)

        Returns:
            dict: {"11.24": "10", "12.24": "17", ..., "Top": "183", "Ort": "14,1"}
            veya {} (hata durumunda)
        """
        try:
            logger.info(f"[MONTHLY] Satır {row_num}: get_monthly_top_row başladı")

            # Tüm DataItem elementlerini al (depth sınırlaması kaldırıldı)
            all_items = self.main_window.descendants(control_type="DataItem")
            logger.info(f"[MONTHLY] Satır {row_num}: {len(all_items)} DataItem bulundu (tüm derinlikler)")

            # Sütun isimleri - DİNAMİK HESAPLAMA (bugünden geriye 13 ay)
            from datetime import datetime

            today = datetime.now()
            columns = []

            # 12 ay önceden bugüne kadar (ters sıra: eski -> yeni)
            for i in range(12, -1, -1):  # 12, 11, 10, ..., 1, 0
                # Manuel ay hesaplama (dateutil olmadan)
                target_month = today.month - i
                target_year = today.year

                # Yıl geçişi düzelt
                while target_month <= 0:
                    target_month += 12
                    target_year -= 1

                # Format: "11.24"
                columns.append(f"{target_month:02d}.{target_year % 100:02d}")

            # Top ve Ort ekle
            columns.extend(["Top", "Ort"])

            logger.debug(f"[MONTHLY] Satır {row_num}: Dinamik sütunlar: {columns[:3]}...{columns[-5:]}")

            result = {}

            # Alt paneldeki (y >= 400) elementleri filtrele ve Top satırını bul
            panel_elements = {}  # {(col, row): element}
            top_panel_row = None
            alt_panel_titles = []  # Debug için

            for item in all_items:
                try:
                    title = item.window_text()
                    rect = item.rectangle()

                    # Sadece alt panel (y >= 400)
                    if rect.top < 400:
                        continue

                    # Debug için title'ları topla
                    if title and "satır" in title.lower():
                        alt_panel_titles.append(title)

                    # "Top satır N" veya "Top. satır N" formatında mı?
                    if title.startswith("Top satır ") or title.startswith("Top. satır "):
                        # "Top satır 3" veya "Top. satır 3" -> 3
                        panel_row = int(title.replace("Top satır ", "").replace("Top. satır ", ""))
                        if top_panel_row is None or panel_row > top_panel_row:
                            top_panel_row = panel_row  # En büyük numaralı Top satırı
                            logger.debug(f"[MONTHLY] Satır {row_num}: Top/Top. satırı bulundu: '{title}' -> panel_row={panel_row}")

                    # Sütun elementlerini sakla
                    for col_name in columns:
                        if title == f"{col_name} satır 1" or title == f"{col_name} satır 2" or title == f"{col_name} satır 3":
                            panel_row = int(title.split(" satır ")[-1])
                            panel_elements[(col_name, panel_row)] = item
                except:
                    continue

            # Debug: Alt paneldeki tüm title'ları logla
            if alt_panel_titles:
                logger.info(f"[MONTHLY] Satır {row_num}: Alt paneldeki elementler (ilk 20): {alt_panel_titles[:20]}")

            # Top satırını bulduksa, değerleri oku
            if top_panel_row:
                logger.info(f"[MONTHLY] Satır {row_num}: Top satırı bulundu (panel satır {top_panel_row})")
                for col_name in columns:
                    elem = panel_elements.get((col_name, top_panel_row))
                    if elem:
                        try:
                            cell_value = elem.legacy_properties().get('Value', '')
                        except:
                            try:
                                cell_value = elem.get_value()
                            except:
                                cell_value = ""
                        result[col_name] = cell_value if cell_value else "-"
                    else:
                        result[col_name] = "-"

                logger.info(f"[MONTHLY] Satır {row_num}: ✓ Top satırı okundu - {len(result)} sütun")
                return result

            logger.warning(f"[MONTHLY] Satır {row_num}: Top satırı BULUNAMADI! Alt paneldeki elementler kontrol edin:")
            if alt_panel_titles:
                logger.warning(f"[MONTHLY] Satır {row_num}: Bulunan elementler (ilk 30): {alt_panel_titles[:30]}")
            else:
                logger.warning(f"[MONTHLY] Satır {row_num}: ALT PANELDE HİÇ ELEMENT YOK! (y >= 400)")
            return {}

        except Exception as e:
            logger.error(f"[MONTHLY] Top satırı okunamadı (satır {row_num}): {e}", exc_info=True)
            return {}

    def get_monthly_sales_data(self, row_num):
        """Aylık gidiş tablosunun tamamını oku (Rx, Per, Top satırları)

        Args:
            row_num: Satır numarası (main tablodaki satır)

        Returns:
            dict: {
                "rx": {"11.24": "8", "12.24": "15", ..., "Top": "161", "Ort": "12,4"},
                "per": {"11.24": "2", "12.24": "2", ..., "Top": "22", "Ort": "1,7"},
                "top": {"11.24": "10", "12.24": "17", ..., "Top": "183", "Ort": "14,1"}
            }
            veya None (hata durumunda)
        """
        try:
            # Önce satırı tıkla (alt panel açılsın)
            stok_elem = self.main_window.child_window(title=f"Stok satır {row_num}", control_type="DataItem", found_index=0)

            # Y kontrolü - ÜST TABLO mu?
            if stok_elem.exists(timeout=0.5):
                try:
                    rect = stok_elem.rectangle()
                    if rect.top >= 400:
                        logger.warning(f"UYARI: Stok satır {row_num} alt tabloda (y={rect.top})")
                        return None
                except AttributeError:
                    pass

            stok_elem.click_input()
            time.sleep(0.2)

            # Sütun isimleri (screenshot'tan)
            columns = ["11.24", "12.24", "01.25", "02.25", "03.25", "04.25", "05.25",
                      "06.25", "07.25", "08.25", "09.25", "10.25", "11.25", "Top", "Ort"]

            result = {
                "rx": {},
                "per": {},
                "top": {}
            }

            # Her satır için (panel satır 1, 2, 3)
            for panel_row in [1, 2, 3]:
                # Satır tipini belirle
                try:
                    tip_elem = self.main_window.child_window(
                        title=f"tip satır {panel_row}",
                        control_type="DataItem",
                        found_index=0
                    )
                    if not tip_elem.exists(timeout=0.1):
                        continue

                    # Value'den satır tipini al (Rx, Per, Top.)
                    try:
                        tip_value = tip_elem.legacy_properties().get('Value', '')
                    except:
                        try:
                            tip_value = tip_elem.get_value()
                        except:
                            tip_value = ""

                    if not tip_value:
                        continue

                    # Satır anahtarını belirle
                    row_key = None
                    if tip_value == "Rx":
                        row_key = "rx"
                    elif tip_value == "Per":
                        row_key = "per"
                    elif tip_value == "Top.":
                        row_key = "top"
                    else:
                        continue

                    # Bu satır için tüm sütunları oku
                    for col_name in columns:
                        try:
                            cell_elem = self.main_window.child_window(
                                title=f"{col_name} satır {panel_row}",
                                control_type="DataItem",
                                found_index=0
                            )

                            if not cell_elem.exists(timeout=0.05):
                                result[row_key][col_name] = "-"
                                continue

                            # Değeri oku
                            try:
                                cell_value = cell_elem.legacy_properties().get('Value', '')
                            except:
                                try:
                                    cell_value = cell_elem.get_value()
                                except:
                                    cell_value = ""

                            result[row_key][col_name] = cell_value if cell_value else "-"
                        except:
                            result[row_key][col_name] = "-"

                except Exception as e:
                    logger.debug(f"Panel satır {panel_row} okunamadı: {e}")
                    continue

            logger.info(f"Satır {row_num}: Aylık gidiş tablosu okundu")
            return result

        except Exception as e:
            logger.error(f"Aylık gidiş tablosu okunamadı (satır {row_num}): {e}")
            return None

    def get_ort_value_from_panel(self, row_num):
        """Alt panelden Top satırı Ort değerini oku

        Not: Alt panelde 2-3 satır olabilir (Rx, Per, Top veya sadece Rx+Top veya Per+Top)
        Her durumda SON satır = Top satırıdır. Top satırının Ort değeri aylık toplam ortalamadır.

        Args:
            row_num: Satır numarası (main tablodaki satır, alt panel satırı değil!)

        Returns:
            float: Top satırı Ort (aylık ortalama) değeri veya 0
        """
        try:
            # Alt panelde Ort satır 1, 2, 3 olabilir (en yükseği Top satırıdır)
            # Tersden dene: 3, 2, 1 (en yüksek numaralı = Top)
            ort_text = None
            found_panel_row = None

            for panel_row in [3, 2, 1]:
                try:
                    ort_elem = self.main_window.child_window(
                        title=f"Ort satır {panel_row}",
                        control_type="DataItem",
                        found_index=0
                    )

                    # Elementin görünür olup olmadığını kontrol et - HIZLANDIRILDI
                    if ort_elem.exists(timeout=0.05):
                        # Bu satırın Top satırı olup olmadığını kontrol et
                        # Up elementinde "Top satır X" olmalı
                        try:
                            # Aynı satırdaki bir element bul (Top hücresi)
                            top_elem = self.main_window.child_window(
                                title=f"Top satır {panel_row}",
                                control_type="DataItem",
                                found_index=0
                            )
                            if top_elem.exists(timeout=0.05):
                                # Top satırını bulduk! Şimdi Ort değerini oku
                                found_panel_row = panel_row

                                # Value özelliğinden değeri al - çeşitli yöntemlerle dene
                                # Yöntem 1: legacy_properties (en güvenilir)
                                try:
                                    ort_text = ort_elem.legacy_properties().get('Value', '')
                                    if ort_text:
                                        logger.debug(f"Top.Ort değeri legacy_properties ile okundu: {ort_text}")
                                        break
                                except:
                                    pass

                                # Yöntem 2: texts() metodu
                                try:
                                    texts_list = ort_elem.texts()
                                    if texts_list and len(texts_list) > 0:
                                        for text in texts_list:
                                            if text and text != f"Ort satır {panel_row}" and text.strip():
                                                ort_text = text
                                                logger.debug(f"Top.Ort değeri texts() ile okundu: {ort_text}")
                                                break
                                    if ort_text:
                                        break
                                except:
                                    pass

                                # Yöntem 3: get_value()
                                try:
                                    ort_text = ort_elem.get_value()
                                    if ort_text:
                                        logger.debug(f"Top.Ort değeri get_value ile okundu: {ort_text}")
                                        break
                                except:
                                    pass

                                break
                        except:
                            # Top elementi yok, bu satır Top değil
                            continue
                except:
                    # Bu panel satırı yok, bir sonrakini dene
                    continue

            # Ort değerini parse et
            if ort_text:
                # Virgülü noktaya çevir
                ort_text = str(ort_text).replace(',', '.')
                try:
                    ort_value = float(ort_text)
                    logger.info(f"Satır {row_num}: Top satırı Ort (panel satır {found_panel_row}) = {ort_value}")
                    return ort_value
                except ValueError:
                    logger.warning(f"Top.Ort değeri parse edilemedi: {ort_text}")
                    return 0

            logger.warning(f"Satır {row_num}: Top satırı Ort değeri okunamadı")
            return 0

        except Exception as e:
            logger.warning(f"Top.Ort değeri okunamadı (satır {row_num}): {e}")
            return 0

    def _get_ort_from_cache(self, row_num, item_cache):
        """Cache'den Top satırı Ort değerini oku (HIZLI MOD)

        Args:
            row_num: Ana tablo satır numarası (log için)
            item_cache: {element_title: element} dictionary

        Returns:
            float: Top satırı Ort değeri veya 0
        """
        try:
            # En yüksek panel satırı = Top satırı (3, 2, 1 sırasıyla dene)
            for panel_row in [3, 2, 1]:
                ort_key = f"Ort satır {panel_row}"
                top_key = f"Top satır {panel_row}"

                # Hem Ort hem Top varsa bu Top satırıdır
                if ort_key in item_cache and top_key in item_cache:
                    ort_elem = item_cache[ort_key]

                    # Değeri oku - çeşitli yöntemlerle
                    ort_text = None

                    # Yöntem 1: legacy_properties
                    try:
                        ort_text = ort_elem.legacy_properties().get('Value', '')
                        if ort_text:
                            break
                    except:
                        pass

                    # Yöntem 2: texts()
                    try:
                        texts_list = ort_elem.texts()
                        if texts_list:
                            for text in texts_list:
                                if text and text != ort_key and text.strip():
                                    ort_text = text
                                    break
                        if ort_text:
                            break
                    except:
                        pass

                    # Yöntem 3: get_value()
                    try:
                        ort_text = ort_elem.get_value()
                        if ort_text:
                            break
                    except:
                        pass

                    break

            # Parse et
            if ort_text:
                ort_text = str(ort_text).replace(',', '.')
                try:
                    ort_value = float(ort_text)
                    logger.debug(f"Satır {row_num}: Ort (cache) = {ort_value}")
                    return ort_value
                except ValueError:
                    pass

            return 0

        except Exception as e:
            logger.debug(f"Ort cache okuma hatası: {e}")
            return 0

    def _get_monthly_from_cache(self, row_num, item_cache):
        """Cache'den aylık satış verilerini oku (HIZLI MOD)

        Args:
            row_num: Ana tablo satır numarası (log için)
            item_cache: {element_title: element} dictionary

        Returns:
            dict: {"12.24": "15", "01.25": "20", ..., "Top": "180", "Ort": "14.5"}
        """
        try:
            from datetime import datetime

            # Debug: Cache'deki "satır" içeren key'leri logla
            satir_keys = [k for k in item_cache.keys() if "satır" in k.lower()]
            if satir_keys:
                logger.info(f"  [CACHE] Satır {row_num}: 'satır' içeren key'ler (ilk 15): {satir_keys[:15]}")

            # Dinamik sütun isimleri (12 ay + Top + Ort)
            today = datetime.now()
            columns = []

            for i in range(12, -1, -1):
                target_month = today.month - i
                target_year = today.year
                while target_month <= 0:
                    target_month += 12
                    target_year -= 1
                columns.append(f"{target_month:02d}.{target_year % 100:02d}")

            columns.extend(["Top", "Ort"])

            # Top satır numarasını bul (1, 2 veya 3 - en yüksek olan)
            # "Top satır X" veya "Top. satır X" formatı olabilir
            top_panel_row = None
            for panel_row in [3, 2, 1]:
                top_key1 = f"Top satır {panel_row}"
                top_key2 = f"Top. satır {panel_row}"
                if top_key1 in item_cache:
                    top_panel_row = panel_row
                    logger.info(f"  [CACHE] Top satırı bulundu: '{top_key1}'")
                    break
                elif top_key2 in item_cache:
                    top_panel_row = panel_row
                    logger.info(f"  [CACHE] Top satırı bulundu: '{top_key2}'")
                    break

            if not top_panel_row:
                logger.warning(f"  [CACHE] Satır {row_num}: Top satırı bulunamadı!")
                return {}

            # Her sütun için değeri oku
            result = {}
            for col_name in columns:
                cell_key = f"{col_name} satır {top_panel_row}"
                if cell_key in item_cache:
                    elem = item_cache[cell_key]
                    try:
                        cell_value = elem.legacy_properties().get('Value', '')
                    except:
                        try:
                            cell_value = elem.get_value()
                        except:
                            cell_value = ""
                    result[col_name] = cell_value if cell_value else "-"
                else:
                    result[col_name] = "-"

            logger.info(f"  [CACHE] Satır {row_num}: Aylık veriler okundu - Ort={result.get('Ort', '-')}, Top={result.get('Top', '-')}")
            return result

        except Exception as e:
            logger.error(f"Monthly cache okuma hatası: {e}")
            return {}

    def get_product_data(self, row_num):
        """Bir satırdaki tüm ürün verilerini al

        Returns:
            dict: Ürün bilgileri (stok, ürün_adı, mf, minstk, ort, barkod)
        """
        try:
            data = {
                "row": row_num,
                "stok": self.get_cell_value(row_num, BOTANIK_ELEMENTS["stok"]),
                "urun_adi": self.get_cell_value(row_num, BOTANIK_ELEMENTS["urun_adi"]),
                "mf": self.get_cell_value(row_num, BOTANIK_ELEMENTS["mf_iht"]),
                "minstk": self.get_cell_value(row_num, BOTANIK_ELEMENTS["minstk"]),
                "ort": 0,  # Varsayılan
                "barkod": None
            }

            # Değerleri int'e çevir (boş veya geçersiz ise 0)
            try:
                data["stok"] = int(data["stok"]) if data["stok"] else 0
            except (ValueError, TypeError):
                data["stok"] = 0

            try:
                data["mf"] = int(data["mf"]) if data["mf"] else 0
            except (ValueError, TypeError):
                data["mf"] = 0

            try:
                # MinStk boş veya 0 ise → Ort kullanılacak
                data["minstk"] = int(data["minstk"]) if data["minstk"] else 0
            except (ValueError, TypeError):
                data["minstk"] = 0  # Parse edilemezse 0 kabul et

            # HER ZAMAN alt panelden Ort değerini oku (MF=0 olduğu için zaten filtrelenmiş)
            # MinStk varsa MinStk kullanılacak, yoksa Ort kullanılacak
            # AYRICA aylık gidiş tablosunu da oku (CSV'ye kaydedilecek)
            try:
                # Satıra tıkla (alt panel açılsın)
                stok_elem = self.main_window.child_window(title=f"Stok satır {row_num}", control_type="DataItem", found_index=0)
                stok_elem.click_input()
                time.sleep(0.15)  # Alt panelin açılması için gerekli bekleme süresi

                # Alt panelden Ort değerini oku
                data["ort"] = self.get_ort_value_from_panel(row_num)

                # Aylık gidiş tablosunu da oku (sadece Top satırı)
                data["monthly_sales"] = self.get_monthly_top_row(row_num)

                # MF (Mal Fazlası) bilgisini de oku - SADECE AYAR AÇIKSA
                import os
                mf_enabled = os.getenv("MF_ENABLED", "true").lower() == "true"
                if mf_enabled:
                    data["mf_info"] = self.get_mf_info(row_num)
                else:
                    data["mf_info"] = None  # MF özelliği kapalı
            except Exception as e:
                logger.warning(f"Satır {row_num}: Alt panel açılamadı, Ort=0 kullanılacak. Hata: {str(e)[:100]}")
                data["ort"] = 0  # Alt panel açılamazsa 0 kullan
                data["monthly_sales"] = {}  # Aylık gidiş bilgisi yok
                data["mf_info"] = None  # MF bilgisi yok

            return data
        except Exception as e:
            logger.error(f"Ürün verisi alınırken hata (satır {row_num}): {e}")
            return None

    def get_barcode_from_row(self, row_num):
        """Satırdan barkod al (Depo/Personel sütununa tıklayarak)

        Args:
            row_num: Satır numarası

        Returns:
            str: Barkod
        """
        return self.click_depo_personel_cell(row_num)

    def _count_sales_months(self, monthly_sales):
        """Kaç farklı ayda satış olduğunu hesapla

        Args:
            monthly_sales: Aylık satış verisi dict (örn: {"01.25": 3, "02.25": 0, ...})

        Returns:
            int: Satış olan ay sayısı
        """
        if not monthly_sales:
            return 0

        count = 0
        for key, value in monthly_sales.items():
            # Top ve Ort gibi özet alanları atla
            if key in ("Top", "Ort"):
                continue

            # Değeri sayıya çevir ve 0'dan büyükse say
            try:
                val = float(str(value).replace(",", ".")) if value and value != "-" else 0
                if val > 0:
                    count += 1
            except (ValueError, TypeError):
                continue

        return count

    def calculate_order_quantity(self, product):
        """Sipariş adedini hesapla

        Mantık:
        1. MF > 0 → Sipariş = MF
        2. MF = 0 → Hedef = max(MinStk + 1, Ort × Gün ÷ 30)
                    Sipariş = Hedef - Mevcut Stok

        Yuvarlama kuralları (Ort tabanlı hedef için):
        - Ort < 0.1 → 0 (çok nadir satış, bulundurma)
        - 0.1 <= Ort < 0.5 → 3+ ayda satış varsa 1, değilse 0
        - Ort >= 0.5 → En az 1 (yukarı yuvarla)

        Args:
            product: Ürün bilgileri

        Returns:
            int: Sipariş adedi
        """
        try:
            import math

            mf = product.get("mf", 0)
            stok = product.get("stok", 0)
            minstk = product.get("minstk", 0)
            ort = product.get("ort", 0)
            monthly_sales = product.get("monthly_sales", {})

            # 1. MF doluysa direkt onu kullan
            if mf > 0:
                logger.debug(f"Kural 1: MF={mf}, sipariş adedi = {mf}")
                return mf

            # 2. MF=0 → MinStk ve Ort'tan büyük olanı kullan
            hedef1 = 0  # MinStk tabanlı hedef
            hedef2 = 0  # Ort tabanlı hedef

            # Hedef1: MinStk + 1
            if minstk > 0:
                hedef1 = minstk + 1
                logger.debug(f"Hedef1 (MinStk): MinStk={minstk} → Hedef1={hedef1}")

            # Hedef2: Ort × Gün ÷ 30 (yuvarlama kurallarıyla)
            if ort > 0:
                raw_hedef = (ort * self.gun_sayisi) / 30

                # Yuvarlama kuralları
                if ort < 0.1:
                    # Çok nadir satış (yılda 1-2 adet), bulundurma
                    hedef2 = 0
                    logger.debug(f"Hedef2 (Ort): Ort={ort} < 0.1 → Hedef2=0 (çok nadir)")
                elif ort < 0.5:
                    # Nadir satış, kaç ayda satıldığına bak
                    satis_ay_sayisi = self._count_sales_months(monthly_sales)
                    if satis_ay_sayisi >= 3:
                        # 3+ farklı ayda satış var, düzenli talep, 1 adet bulundur
                        hedef2 = 1
                        logger.debug(f"Hedef2 (Ort): Ort={ort}, {satis_ay_sayisi} ayda satış → Hedef2=1 (dağılmış talep)")
                    else:
                        # 2 veya daha az ayda satış, muhtemelen toplu satış
                        hedef2 = 0
                        logger.debug(f"Hedef2 (Ort): Ort={ort}, {satis_ay_sayisi} ayda satış → Hedef2=0 (toplu satış)")
                else:
                    # Normal satış, yukarı yuvarla
                    hedef2 = math.ceil(raw_hedef)
                    logger.debug(f"Hedef2 (Ort): Ort={ort}, Gün={self.gun_sayisi} → Raw={raw_hedef:.2f} → Hedef2={hedef2}")

            # İkisinden büyük olanı al
            hedef = max(hedef1, hedef2)

            if hedef > 0:
                siparis_adet = hedef - stok
                siparis_adet = max(siparis_adet, 0)
                logger.info(f"Kural 2: MF=0, Hedef1(MinStk)={hedef1}, Hedef2(Ort)={hedef2} → Hedef={hedef}, Stok={stok}, Sipariş={siparis_adet}")
                return siparis_adet

            # Hiçbir kriter yok, sipariş verme
            logger.debug(f"Kural 0: MF=0, Hedef1=0, Hedef2=0 → Sipariş verilmeyecek")
            return 0

        except Exception as e:
            logger.error(f"Sipariş adedi hesaplanırken hata: {e}")
            return 0

    def get_all_products(self, filter_mf_zero=False, skip_mf_write=False, on_product=None, start_from_row=None):
        """Sipariş listesindeki tüm ürünleri al

        Args:
            filter_mf_zero: True ise sadece MF=0 olan ürünleri al
            skip_mf_write: True ise MF hesaplama ve yazma işlemini atla (sadece oku)
            on_product: Her ürün okunduğunda çağrılacak callback (product, idx, total)
            start_from_row: Belirtilirse bu satırdan itibaren taramaya başlar (yarım tarama devam)

        Returns:
            list: Ürün bilgileri listesi
        """
        products = []

        if not self.table_prepared:
            if not self.ensure_date_sorted():
                logger.info("Tarih sütunu varsayılan sıralamada kaldı, mevcut listeyle devam edilecek.")
            else:
                self.table_prepared = True

        # Satır numaralarını dinamik olarak al (scroll ederek tüm satırları bulur)
        row_numbers = self.get_row_numbers()

        if not row_numbers:
            logger.warning("Hiç satır bulunamadı!")
            return []

        total_rows = len(row_numbers)
        logger.info(f"Toplam {total_rows} satır bulundu")
        if filter_mf_zero:
            logger.info("Sadece MF=0 olan ürünler işlenecek...")
        logger.info(f"Satır numaraları: {row_numbers[:5]}...{row_numbers[-5:] if total_rows > 5 else row_numbers}")

        # Yarım tarama devamı - başlangıç satırını ayarla
        if start_from_row:
            # start_from_row'dan SONRAKI satırlardan başla
            row_numbers = [r for r in row_numbers if r > start_from_row]
            logger.info(f"DEVAM: Satır {start_from_row}'dan sonraki {len(row_numbers)} satır taranacak")
            if not row_numbers:
                logger.info("Devam edilecek satır kalmadı, tarama tamamlanmış")
                return []

        # Tekrar başa dön (veya devam satırına)
        if start_from_row and row_numbers:
            self.scroll_to_row(row_numbers[0])  # İlk satıra git
        else:
            self.scroll_table_to_top()

        for idx, row_num in enumerate(row_numbers, 1):
            try:
                # Pause kontrolü - Duraklatıldıysa bekle
                if self.gui and hasattr(self.gui, 'pause_event'):
                    self.gui.pause_event.wait()

                logger.info(f"[{idx}/{total_rows}] Satır {row_num} okunuyor...")

                # Ürün verilerini al (ensure_row_visible KALDIRILDI - gereksiz!)
                product_data = self.get_product_data(row_num)
                if not product_data:
                    logger.warning(f"Satır {row_num} verileri okunamadı, atlanıyor...")
                    continue

                # MF=0 filtresi
                if filter_mf_zero and product_data.get("mf", 0) > 0:
                    logger.info(f"⊘ Satır {row_num}: MF={product_data['mf']} (dolu), atlanıyor...")
                    continue

                # MF yazma işlemi (skip_mf_write=False ise)
                if not skip_mf_write:
                    # MF=0 olanlar için hesapla ve yaz, MF dolu olanlar için mevcut değeri kullan
                    current_mf = product_data.get("mf", 0)

                    if current_mf == 0:
                        # MF boş, hesapla ve yaz
                        siparis_adet = self.calculate_order_quantity(product_data)
                        product_data["siparis_adet"] = siparis_adet

                        logger.info(f"→ Satır {row_num}: Hesaplanan sipariş adedi = {siparis_adet}")

                        # HEMEN MF alanına yaz (barkod almadan ÖNCE!)
                        if siparis_adet > 0:
                            logger.info(f"→ MF alanına {siparis_adet} yazılıyor (Satır {row_num})...")
                            if self.set_mf_value(row_num, siparis_adet):
                                logger.info(f"✓ MF alanına BAŞARIYLA yazıldı!")
                            else:
                                logger.error(f"✗ MF alanına YAZILAMADI!")
                        else:
                            logger.info(f"⊘ Sipariş adedi 0, MF'ye yazılmadı")
                    else:
                        # MF dolu, mevcut değeri kullan (tekrar hesaplama ve yazma)
                        product_data["siparis_adet"] = current_mf
                        logger.info(f"⊘ Satır {row_num}: MF={current_mf} (dolu), tekrar hesaplanmadı")
                else:
                    # MF yazma atlandı, sadece mevcut değeri kullan
                    product_data["siparis_adet"] = product_data.get("mf", 0)

                # Sonra barkodu al
                barcode = self.click_depo_personel_cell(row_num)
                product_data["barkod"] = barcode

                # Ürünü listeye ekle
                products.append(product_data)

                if on_product:
                    try:
                        on_product(product_data, idx, total_rows)
                    except Exception as callback_error:
                        logger.error(f"on_product callback hatası: {callback_error}")

                if barcode:
                    logger.info(f"✓ Satır {row_num}: {product_data['urun_adi']} - MF={product_data['mf']} - Barkod: {barcode}")
                else:
                    logger.warning(f"⚠ Satır {row_num}: {product_data['urun_adi']} - MF={product_data['mf']} - Barkod alınamadı")

                # SATIR SONU: DOWN tuşu artık gerekmiyor
                # Çünkü click_depo_personel_cell() içinde gerekirse scroll yapılıyor

                # HIZLANDIRILDI: 0.05 → 0.02
                time.sleep(0.02)  # Minimal bekleme

            except Exception as e:
                logger.error(f"Satır {row_num} işlenirken hata: {e}")
                continue

        logger.info(f"\n=== ÜRÜN OKUMA TAMAMLANDI ===")
        logger.info(f"Toplam {len(row_numbers)} satır tarandı")
        logger.info(f"Toplam {len(products)} ürün listeye eklendi")
        logger.info(f"=================================\n")
        return products

    def get_all_yoklar(self):
        """Yoklar listesindeki tüm ürünleri al (geriye uyumluluk için)

        Returns:
            list: Ürün bilgileri listesi
        """
        return self.get_all_products(filter_mf_zero=False)

    def get_visible_row_range(self):
        """Sipariş Yardımcısı'nda şu anda görünür olan satırların min-max numaralarını bul

        Optimized: Binary search benzeri yöntemle hızlıca min/max bulur.

        Returns:
            tuple: (min_row, max_row) veya (None, None) bulamazsa
        """
        try:
            # Önce birkaç örnek satırı kontrol et (1, 10, 20, 30... 200'e kadar)
            # Geniş aralık - 200 satıra kadar destek
            sample_rows = [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 120, 150, 200]
            visible_samples = []

            # Tüm DataItem'ları bir kez al (optimizasyon)
            try:
                all_items = self.main_window.descendants(control_type="DataItem")
            except:
                all_items = []

            for row in sample_rows:
                # Manuel case-sensitive kontrol
                for item in all_items:
                    try:
                        text = item.window_text()  # BAŞTA BOŞLUK OLMAMALI - .strip() YOK!
                        # BÜYÜK/KÜÇÜK HARF DUYARLI: Tam olarak "Satır {row}" - başta boşluk RED
                        if text == f"Satır {row}":
                            # Y kontrol et - SADECE ÜST TABLO
                            rect = item.rectangle()
                            if rect.top < 400:
                                visible_samples.append(row)
                                break  # Bu satır bulundu, bir sonrakine geç
                    except:
                        continue

            if not visible_samples:
                logger.warning("Görünür satır bulunamadı (sample)")
                return None, None

            # Min/max tahmin et
            estimated_min = min(visible_samples)
            estimated_max = max(visible_samples)

            # Kesin min'i bul (geriye doğru ara)
            min_row = estimated_min
            for row in range(estimated_min - 1, 0, -1):
                # Manuel case-sensitive kontrol
                found = False
                for item in all_items:
                    try:
                        text = item.window_text()  # BAŞTA BOŞLUK OLMAMALI - .strip() YOK!
                        if text == f"Satır {row}":  # Exact match - başta boşluk RED
                            rect = item.rectangle()
                            if rect.top < 400:
                                min_row = row
                                found = True
                                break
                            else:
                                # Alt tabloya geçtik, dur
                                return min_row, estimated_max
                    except:
                        continue

                if not found:
                    break  # Bu satır bulunamadı, dur

            # Kesin max'ı bul (ileriye doğru ara)
            max_row = estimated_max
            for row in range(estimated_max + 1, min(estimated_max + 50, 250)):
                # Manuel case-sensitive kontrol
                found = False
                for item in all_items:
                    try:
                        text = item.window_text()  # BAŞTA BOŞLUK OLMAMALI - .strip() YOK!
                        if text == f"Satır {row}":  # Exact match - başta boşluk RED
                            rect = item.rectangle()
                            if rect.top < 400:
                                max_row = row
                                found = True
                                break
                            else:
                                # Alt tabloya geçtik, dur
                                return min_row, max_row
                    except:
                        continue

                if not found:
                    break  # Bu satır bulunamadı, dur

            logger.debug(f"Görünür satır aralığı: {min_row} - {max_row}")
            return min_row, max_row

        except Exception as e:
            logger.warning(f"Görünür satır aralığı bulma hatası: {e}")
            return None, None

    def get_current_row(self):
        """Sipariş Yardımcısı'nda şu anda hangi satırda olduğumuzu tespit et

        "Satır X" elemanlarından "seçili" (selected) state olanı bulur.
        SADECE ÜST TABLO (y < 400) kontrol edilir.

        Returns:
            int: Mevcut satır numarası (1'den başlar), bulunamazsa None
        """
        try:
            # Tüm DataItem'ları al
            try:
                all_items = self.main_window.descendants(control_type="DataItem")
            except:
                return None

            # Focused veya selected state olan satırı bul
            for row in range(1, 201):  # 200 satıra kadar destek
                # Manuel case-sensitive kontrol
                for item in all_items:
                    try:
                        text = item.window_text()  # BAŞTA BOŞLUK OLMAMALI - .strip() YOK!
                        if text == f"Satır {row}":  # Exact match - başta boşluk RED
                            # SADECE ÜST TABLO (y < 400)
                            try:
                                rect = item.rectangle()
                                if rect.top >= 400:
                                    # Alt tablo, atla
                                    continue
                            except:
                                continue

                            # State'i kontrol et - pywinauto'da is_selected() veya has_state()
                            try:
                                # Daha basit: is_selected() metodu (varsa)
                                if hasattr(item, 'is_selected') and item.is_selected():
                                    logger.debug(f"Mevcut satır tespit edildi: {row} (selected state, üst tablo)")
                                    return row
                            except:
                                pass

                    except:
                        continue

            # Hiçbir focused satır bulunamadıysa None dön
            logger.debug("Mevcut satır tespit edilemedi (hiçbir satır selected değil)")
            return None

        except Exception as e:
            logger.warning(f"Mevcut satır tespiti hatası: {e}")
            return None

    def scroll_to_row(self, row_num):
        """Sipariş Yardımcısı'nda belirli satırı görünür hale getir (scroll yap)

        HIZLI Akıllı scroll: Cache'lenmiş mevcut satırdan direkt gider.

        Args:
            row_num: GUI'deki satır numarası (1'den başlar)

        Returns:
            dict: {
                "success": bool,
                "visible_range": (min, max),  # Görünür satır aralığı
                "current_row": int,            # Mevcut satır
                "target_row": int,             # Hedef satır
                "distance": int,               # Scroll mesafesi (pozitif=aşağı, negatif=yukarı)
                "scroll_info": str             # İnsan okunabilir scroll bilgisi
            }
        """
        try:
            # 0. ÇOK ÖNEMLİ: Botanik penceresini öne getir
            try:
                logger.debug("Botanik penceresi öne getiriliyor (scroll için)...")
                self.main_window.set_focus()
                time.sleep(0.2)  # Pencere aktif olması için bekle
            except Exception as focus_err:
                logger.warning(f"Botanik focus hatası (devam ediliyor): {focus_err}")

            # 1. Önce satır zaten görünür mü kontrol et
            # ÖNEMLİ: Manuel case-sensitive kontrol (pywinauto regex case-insensitive olabilir)
            logger.info(f"🔍 SCROLL TO ROW {row_num} - Başlangıç kontrolü...")

            row_element = None
            found_similar = []  # Benzer satırları da kaydet (debug için)

            try:
                # Tüm DataItem'ları al ve manuel filtrele
                all_items = self.main_window.descendants(control_type="DataItem")
                logger.debug(f"   → Toplam {len(all_items)} DataItem bulundu")

                for item in all_items:
                    try:
                        text = item.window_text()  # BAŞTA BOŞLUK OLMAMALI - .strip() YOK!

                        # DEBUG: "Satır" içeren tüm elementleri logla
                        if "atır" in text or "row" in text.lower():
                            rect = item.rectangle()
                            # repr() ile başta/sonda boşluk görünsün
                            logger.debug(f"   → Bulunan element: {repr(text)} @ y={rect.top}")
                            found_similar.append((text, rect.top))

                        # BÜYÜK/KÜÇÜK HARF DUYARLI kontrol: Tam olarak "Satır {row_num}" - başta boşluk RED
                        if text == f"Satır {row_num}":
                            # Y koordinatı kontrol et - SADECE ÜST TABLO (y < 400)
                            rect = item.rectangle()
                            if rect.top < 400:
                                row_element = item
                                self.current_row_cache = row_num  # Cache'i güncelle
                                logger.info(f"✅ Satır {row_num} ZATEN GÖRÜNÜR (üst tablo, y={rect.top}) - SCROLL GEREKSİZ")

                                # Görünür aralığı al
                                min_row, max_row = self.get_visible_row_range()

                                return {
                                    "success": True,
                                    "visible_range": (min_row, max_row),
                                    "current_row": row_num,
                                    "target_row": row_num,
                                    "distance": 0,
                                    "scroll_info": f"Zaten görünür (Satır {min_row}-{max_row})"
                                }
                            else:
                                logger.warning(f"⚠️ 'Satır {row_num}' bulundu AMA ALT TABLODA (y={rect.top}), RED edildi")
                    except:
                        continue

                # Eğer bulunamadıysa benzer satırları göster
                if found_similar:
                    logger.debug(f"   → 'Satır {row_num}' bulunamadı. Benzer elementler:")
                    for text, y in found_similar[:10]:  # İlk 10 tanesini göster
                        logger.debug(f"      • {repr(text)} @ y={y}")

            except Exception as e:
                logger.debug(f"Manuel arama hatası: {e}")
                pass

            logger.info(f"❌ Satır {row_num} görünür değil, SCROLL gerekli...")

            # 2. HIZLI: Cache'den mevcut satırı al
            current_row = self.current_row_cache

            if current_row is None:
                # Cache yoksa tespit et
                logger.info("   → Cache boş, mevcut satır tespit ediliyor...")
                current_row = self.get_current_row()

                if current_row is None:
                    # Hala bulunamadıysa görünür aralığı al
                    logger.info("   → Mevcut satır bulunamadı, görünür aralık tespit ediliyor...")
                    min_row, max_row = self.get_visible_row_range()
                    if min_row:
                        current_row = min_row
                        logger.info(f"   → Görünür aralık: Satır {min_row}-{max_row}, başlangıç: {current_row}")
                    else:
                        logger.error("❌ Mevcut satır ve görünür aralık bulunamadı - SCROLL BAŞARISIZ")
                        return {
                            "success": False,
                            "visible_range": (None, None),
                            "current_row": None,
                            "target_row": row_num,
                            "distance": 0,
                            "scroll_info": "Görünür satır bulunamadı"
                        }

                # Cache'i güncelle
                self.current_row_cache = current_row
                logger.info(f"   → Cache güncellendi: Satır {current_row}")
            else:
                logger.info(f"   → Cache'den mevcut satır: Satır {current_row}")

            # Görünür aralığı da göster (bilgilendirme için)
            min_row, max_row = self.get_visible_row_range()
            if min_row and max_row:
                logger.info(f"   → Görünür aralık: Satır {min_row}-{max_row}")

            # 3. Mesafe hesapla ve yön belirle
            distance = row_num - current_row

            if distance == 0:
                logger.info(f"✅ Zaten hedef satırdayız (Satır {row_num})")
                return {
                    "success": True,
                    "visible_range": (min_row, max_row) if (min_row and max_row) else (None, None),
                    "current_row": current_row,
                    "target_row": row_num,
                    "distance": 0,
                    "scroll_info": f"Zaten görünür (Satır {min_row}-{max_row})" if min_row else "Zaten görünür"
                }

            direction = "AŞAĞI ⬇️" if distance > 0 else "YUKARI ⬆️"
            direction_text = "aşağı" if distance > 0 else "yukarı"
            abs_distance = abs(distance)

            logger.info(f"📏 Scroll: Satır {current_row} → Satır {row_num}")
            logger.info(f"   → Yön: {direction}")
            logger.info(f"   → Mesafe: {abs_distance} satır")

            # Scroll bilgisini hazırla (GUI için)
            scroll_info = f"Satır {min_row if min_row else '?'}-{max_row if max_row else '?'} görünür, {abs_distance} satır {direction_text}"

            # 4. HIZLI SCROLL: Mevcut satırdan direkt hedef satıra git
            if distance < 0:
                # YUKARI GİT (distance negatif)
                steps = abs(distance)

                # Her PageUp yaklaşık 10 satır
                PAGE_SIZE = 10
                page_ups = steps // PAGE_SIZE
                remaining = steps % PAGE_SIZE

                logger.info(f"⬆️ SCROLL YUKARI: {steps} satır")
                if page_ups > 0:
                    logger.info(f"   → {page_ups} × PageUp tuşu (~{page_ups * PAGE_SIZE} satır)")
                    for i in range(page_ups):
                        self.main_window.type_keys("{PGUP}")
                        time.sleep(0.05)

                if remaining > 0:
                    logger.info(f"   → {remaining} × Up tuşu (ince ayar)")
                    for i in range(remaining):
                        self.main_window.type_keys("{UP}")
                        time.sleep(0.02)

            elif distance > 0:
                # AŞAĞI GİT (distance pozitif)
                steps = distance

                # Her PageDown yaklaşık 10 satır
                PAGE_SIZE = 10
                page_downs = steps // PAGE_SIZE
                remaining = steps % PAGE_SIZE

                logger.info(f"⬇️ SCROLL AŞAĞI: {steps} satır")
                if page_downs > 0:
                    logger.info(f"   → {page_downs} × PageDown tuşu (~{page_downs * PAGE_SIZE} satır)")
                    for i in range(page_downs):
                        self.main_window.type_keys("{PGDN}")
                        time.sleep(0.05)

                if remaining > 0:
                    logger.info(f"   → {remaining} × Down tuşu (ince ayar)")
                    for i in range(remaining):
                        self.main_window.type_keys("{DOWN}")
                        time.sleep(0.02)

            # 5. Biraz bekle ve doğrula
            time.sleep(0.2)

            # 6. Satır görünür mü kontrol et - Manuel case-sensitive kontrol
            logger.info(f"🔍 Doğrulama: Satır {row_num} görünür mü kontrol ediliyor...")
            try:
                all_items = self.main_window.descendants(control_type="DataItem")
                verification_found = []

                for item in all_items:
                    try:
                        text = item.window_text()  # BAŞTA BOŞLUK OLMAMALI - .strip() YOK!

                        # DEBUG: "Satır" içeren tüm elementleri tekrar logla
                        if "atır" in text or "row" in text.lower():
                            rect = item.rectangle()
                            verification_found.append((text, rect.top))

                        if text == f"Satır {row_num}":  # Exact match - başta boşluk RED
                            # Y koordinatı kontrol et
                            rect = item.rectangle()
                            if rect.top < 400:
                                # Cache'i güncelle (başarılı scroll)
                                self.current_row_cache = row_num
                                logger.info(f"✅ SCROLL BAŞARILI! Satır {row_num} görünür (y={rect.top})")
                                logger.info(f"   → Cache güncellendi: Satır {row_num}")

                                # Scroll sonrası görünür aralığı al
                                new_min, new_max = self.get_visible_row_range()

                                return {
                                    "success": True,
                                    "visible_range": (new_min, new_max),
                                    "current_row": current_row,
                                    "target_row": row_num,
                                    "distance": distance,
                                    "scroll_info": scroll_info
                                }
                            else:
                                logger.error(f"❌ 'Satır {row_num}' bulundu ama ALT TABLODA (y={rect.top})!")
                    except:
                        continue

                # Hiç bulunamadı - benzer satırları göster
                logger.error(f"❌ SCROLL BAŞARISIZ! Satır {row_num} hala görünmüyor")
                if verification_found:
                    logger.debug(f"   → Scroll sonrası bulunan elementler:")
                    for text, y in verification_found[:10]:
                        logger.debug(f"      • {repr(text)} @ y={y}")

                return {
                    "success": False,
                    "visible_range": (min_row, max_row) if (min_row and max_row) else (None, None),
                    "current_row": current_row,
                    "target_row": row_num,
                    "distance": distance,
                    "scroll_info": scroll_info + " - BAŞARISIZ"
                }
            except Exception as e:
                logger.error(f"❌ Scroll doğrulama hatası: {e}")
                return {
                    "success": False,
                    "visible_range": (None, None),
                    "current_row": current_row if 'current_row' in locals() else None,
                    "target_row": row_num,
                    "distance": distance if 'distance' in locals() else 0,
                    "scroll_info": "Doğrulama hatası"
                }

        except Exception as e:
            logger.warning(f"Satır {row_num} scroll hatası: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return {
                "success": False,
                "visible_range": (None, None),
                "current_row": None,
                "target_row": row_num,
                "distance": 0,
                "scroll_info": "Scroll hatası"
            }

    def set_order_quantity_in_siparis_yardimcisi(self, row_num, quantity):
        """Botanik EOS Sipariş Yardımcısı'nda belirli satırın Adet alanına değer yaz

        Açıklama ve MF/İht alanlarıyla aynı yöntemi kullanır.

        Args:
            row_num: GUI'deki satır numarası (1'den başlar)
            quantity: Sipariş adedi

        Returns:
            bool: İşlem başarılı mı
        """
        try:
            # Botanik EOS penceresini öne getir (GUI'ye yanlış tuş girişi olmasın)
            try:
                self.main_window.set_focus()
                time.sleep(0.1)  # Focus geçişi için bekle
            except Exception as e:
                logger.debug(f"Botanik pencere focus hatası: {e}")

            # ÖNEMLİ: Önce satırı görünür hale getir (scroll yap)
            scroll_result = self.scroll_to_row(row_num)
            if not scroll_result.get("success"):
                logger.error(f"Scroll başarısız: {scroll_result.get('scroll_info')}")
                return False

            # Adet hücresini bul
            cell_name = BOTANIK_ELEMENTS["adet"].format(row=row_num)
            logger.debug(f"Botanik EOS: Adet hücresi güncelleniyor: {cell_name} -> {quantity}")

            # Hücreyi bul - title ile
            cell = self.main_window.child_window(title=cell_name, control_type="DataItem", found_index=0)
            if not cell.exists(timeout=2):
                logger.error(f"Adet hücresi bulunamadı: {cell_name}")
                return False

            # Çift tıkla (edit moduna geç)
            cell.double_click_input()
            time.sleep(0.05)

            # İçeriği temizle ve değeri yaz - klavye ile
            cell.type_keys(f"^a{{BACKSPACE}}{quantity}{{ENTER}}")
            time.sleep(0.3)  # ENTER'ın GUI'ye gitmemesi için bekle

            logger.info(f"✓ Botanik EOS: Satır {row_num} Adet -> {quantity}")
            return True

        except Exception as e:
            logger.error(f"Botanik EOS: Adet yazma hatası (satır {row_num}): {e}")
            return False

    def position_for_ordering(self):
        """Sipariş Yardımcısı penceresini sipariş verme için ideal konuma getir

        Sol üst köşe: %50 genişlik, %90 yükseklik (taskbar hariç)
        """
        try:
            logger.info("Sipariş Yardımcısı penceresi konumlandırılıyor (sol üst)...")

            # Pencere handle'ını al
            hwnd = self.main_window.handle
            logger.debug(f"Sipariş Yardımcısı hwnd: {hwnd}")

            # Ekran boyutlarını al
            import pyautogui
            import win32api
            import win32con
            screen_width, screen_height = pyautogui.size()

            # Taskbar yüksekliğini hesapla
            taskbar_height = 40
            try:
                work_area = win32api.SystemParametersInfo(win32con.SPI_GETWORKAREA)
                taskbar_height = screen_height - work_area[3]
            except:
                pass

            # Çalışma alanı yüksekliği (taskbar hariç)
            usable_height = screen_height - taskbar_height

            # Hedef boyutlar: %50 genişlik, %90 yükseklik
            window_width = screen_width // 2
            window_height = int(usable_height * 0.9)

            # Konum: Sol üst (0, 0)
            x_position = 0
            y_position = 0

            # Windows API ile pencereyi konumlandır
            # SetWindowPos(hwnd, hwndInsertAfter, x, y, width, height, flags)
            # SWP_NOZORDER = 0x0004 (Z-order değiştirme)
            # SWP_SHOWWINDOW = 0x0040 (Pencereyi göster)
            SWP_NOZORDER = 0x0004
            SWP_SHOWWINDOW = 0x0040
            flags = SWP_NOZORDER | SWP_SHOWWINDOW

            result = win32gui.SetWindowPos(
                hwnd,
                0,  # hwndInsertAfter (0 = no change)
                x_position,
                y_position,
                window_width,
                window_height,
                flags
            )

            if result:
                logger.info(f"✓ Sipariş Yardımcısı konumlandırıldı: Sol üst ({window_width}x{window_height})")
            else:
                logger.warning(f"SetWindowPos sonucu: {result}")

            return True

        except Exception as e:
            logger.error(f"Sipariş Yardımcısı konumlandırma hatası: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def get_mf_info(self, row_num):
        """Ürünün MF (Mal Fazlası) bilgisini oku

        Args:
            row_num: Satır numarası (main tablodaki satır)

        Returns:
            dict: {"adet": 10, "mf": 2} veya None (MF yoksa veya hata durumunda)
        """
        try:
            # NOT: Bu metod get_product_data() içinden çağrılıyor
            # Satıra zaten tıklanmış durumda, alt panel açık
            # Tekrar tıklamaya gerek yok, sadece biraz bekle
            time.sleep(0.02)  # DAHA DA HIZLANDIRILDI: 0.05 → 0.02

            # OPTIMIZASYON 2: depth=1 ile sadece direkt children'ı al (daha hızlı)
            # Alt panel zaten açık, binlerce elementi taramaya gerek yok
            all_items = self.main_window.descendants(control_type="DataItem", depth=4)

            # Alt paneldeki (y >= 400) Adet ve MF elementlerini filtrele
            adet_elements = {}  # {panel_row: element}
            mf_elements = {}    # {panel_row: element}

            for item in all_items:
                try:
                    title = item.window_text()
                    rect = item.rectangle()

                    # Sadece alt paneldekiler (y >= 400)
                    if rect.top < 400:
                        continue

                    # "Adet satır N" formatında mı?
                    if title.startswith("Adet satır "):
                        try:
                            panel_row = int(title.replace("Adet satır ", ""))
                            adet_elements[panel_row] = item
                        except:
                            continue

                    # "MF satır N" formatında mı?
                    elif title.startswith("MF satır "):
                        try:
                            panel_row = int(title.replace("MF satır ", ""))
                            mf_elements[panel_row] = item
                        except:
                            continue
                except:
                    continue

            # Alım Şartları tablosundaki tüm satırları tara
            # En yüksek MF oranını bul
            best_ratio = 0.0
            best_adet = 0
            best_mf = 0

            # Sadece ilk 4 satırı tara (yeterli ve hızlı)
            for panel_row in range(1, 5):
                try:
                    # Adet elementi var mı?
                    adet_elem = adet_elements.get(panel_row)
                    if not adet_elem:
                        break  # Artık satır yok

                    # Adet değerini oku
                    try:
                        adet_value = adet_elem.legacy_properties().get('Value', '')
                    except:
                        try:
                            adet_value = adet_elem.get_value()
                        except:
                            adet_value = ""

                    if not adet_value or adet_value == "0":
                        continue

                    # MF elementi var mı?
                    mf_elem = mf_elements.get(panel_row)
                    if not mf_elem:
                        continue

                    # MF değerini oku
                    try:
                        mf_value = mf_elem.legacy_properties().get('Value', '')
                    except:
                        try:
                            mf_value = mf_elem.get_value()
                        except:
                            mf_value = ""

                    if not mf_value or mf_value == "0":
                        continue

                    # Integer'a çevir
                    try:
                        adet_int = int(adet_value.replace(",", "").replace(".", ""))
                        mf_int = int(mf_value.replace(",", "").replace(".", ""))
                    except ValueError:
                        continue

                    # Oran hesapla
                    if adet_int > 0 and mf_int > 0:
                        ratio = mf_int / adet_int

                        # En yüksek oran mı?
                        if ratio > best_ratio:
                            best_ratio = ratio
                            best_adet = adet_int
                            best_mf = mf_int

                except Exception as e:
                    continue

            # En iyi oran varsa döndür
            if best_adet > 0 and best_mf > 0:
                logger.info(f"Satır {row_num}: En iyi MF = {best_adet}+{best_mf} (Oran: {best_ratio:.2%})")
                return {"adet": best_adet, "mf": best_mf}
            else:
                return None

        except Exception as e:
            logger.error(f"Satır {row_num} MF bilgisi okuma hatası: {e}")
            return None

    # ========== HIZLI TARAMA MODU ==========

    def get_all_products_data_only(self, on_product_read=None, start_depo_search=None):
        """HIZLI MOD: Tüm ürün verilerini tek seferde oku (MF yazma yok)

        Bu fonksiyon sadece veri okur:
        - Ürün adı, barkod, stok, MF vs.
        - Hiçbir şey yazmaz (MF dahil)
        - TEK TIKLAMA: Depo/Personel tıklayınca hem barkod hem alt panel açılır

        Args:
            on_product_read: Her ürün okunduğunda çağrılacak callback(product_data, idx, total)
            start_depo_search: Barkod alınır alınmaz çağrılacak callback(barcode) - Future döner

        Returns:
            list: Ürün bilgileri listesi
        """
        products = []

        if not self.table_prepared:
            if not self.ensure_date_sorted():
                logger.info("Tarih sütunu varsayılan sıralamada kaldı")
            else:
                self.table_prepared = True

        # Satır numaralarını al
        row_numbers = self.get_row_numbers()

        if not row_numbers:
            logger.warning("Hiç satır bulunamadı!")
            return []

        total_rows = len(row_numbers)
        logger.info(f"HIZLI MOD: Toplam {total_rows} satır okunacak (tek tıklama)")

        # Başa dön
        self.scroll_table_to_top()

        for idx, row_num in enumerate(row_numbers, 1):
            try:
                row_start = time.time()

                # Pause kontrolü
                if self.gui and hasattr(self.gui, 'pause_event'):
                    self.gui.pause_event.wait()

                # GUI status güncelle
                if self.gui:
                    self.gui.root.after(0, lambda i=idx, t=total_rows:
                        self.gui.update_status(f"Botanik okunuyor: {i}/{t}"))

                logger.info(f"[{idx}/{total_rows}] Satır {row_num} okunuyor...")

                # 1. ÖNCE Depo/Personel'e tıkla → Barkod AL (depo araması başlasın)
                t1 = time.time()
                barcode = self.click_depo_personel_cell(row_num, fast_mode=True)
                t1_dur = time.time() - t1
                logger.info(f"  [SÜRE] Barkod alma: {t1_dur:.2f}s - {barcode or 'YOK'}")

                # 2. Barkod varsa HEMEN depo aramasını başlat (paralel çalışacak)
                depo_future = None
                if barcode and start_depo_search:
                    try:
                        depo_future = start_depo_search(barcode)
                        logger.info(f"  [PARALEL] Depo araması başlatıldı: {barcode}")
                    except Exception as e:
                        logger.debug(f"Depo araması başlatılamadı: {e}")

                # 3. Temel sütunları oku (depo araması arka planda devam ediyor)
                t2 = time.time()
                product_data = self._get_product_data_fast(row_num)
                t2_dur = time.time() - t2
                logger.info(f"  [SÜRE] Temel veri okuma: {t2_dur:.2f}s")

                if not product_data:
                    logger.warning(f"Satır {row_num} okunamadı, atlanıyor...")
                    continue

                product_data["barkod"] = barcode

                # 4. Alt panel açıldı - TÜM VERİLERİ TEK SEFERDE OKU (cache ile)
                t3 = time.time()
                time.sleep(0.05)  # Alt panelin açılması için minimal bekleme

                # Tüm DataItem'ları BİR KERE al
                all_items = self.main_window.descendants(control_type="DataItem")

                # Cache oluştur
                item_cache = {}
                for item in all_items:
                    try:
                        title = item.window_text()
                        item_cache[title] = item
                    except:
                        pass
                t3_dur = time.time() - t3
                logger.info(f"  [SÜRE] Element cache: {t3_dur:.2f}s ({len(item_cache)} element)")

                # Aylık satış verilerini cache'den oku (Ort dahil)
                t4 = time.time()
                try:
                    monthly_data = self._get_monthly_from_cache(row_num, item_cache)
                    product_data["monthly_sales"] = monthly_data

                    # Ort değerini monthly_sales'den al
                    ort_str = monthly_data.get("Ort", "0")
                    ort_str = str(ort_str).replace(',', '.')
                    try:
                        product_data["ort"] = float(ort_str)
                    except:
                        product_data["ort"] = 0
                except:
                    product_data["monthly_sales"] = {}
                    product_data["ort"] = 0
                t4_dur = time.time() - t4
                logger.info(f"  [SÜRE] Aylık veriler (cache): {t4_dur:.2f}s")

                # MF bilgisi - hızlı modda atla
                product_data["mf_info"] = None

                # 5. Sipariş adedi hesapla
                current_mf = product_data.get("mf", 0)
                if current_mf == 0:
                    siparis_adet = self.calculate_order_quantity(product_data)
                    product_data["siparis_adet"] = siparis_adet
                else:
                    product_data["siparis_adet"] = current_mf

                # 6. DEPO SONUÇLARINI AL (bu sırada tamamlanmış olmalı)
                if depo_future:
                    t5 = time.time()
                    try:
                        depo_results = depo_future.result(timeout=10)  # Max 10sn bekle
                        # Depo sonuçlarını product_data'ya ekle
                        if depo_results:
                            product_data.update(depo_results)
                        t5_dur = time.time() - t5
                        logger.info(f"  [SÜRE] Depo sonuçları alma: {t5_dur:.2f}s")
                    except Exception as e:
                        logger.warning(f"  Depo sonuçları alınamadı: {e}")

                # Listeye ekle
                products.append(product_data)

                # GUI callback - ürün bilgilerini anlık göster
                if on_product_read:
                    try:
                        on_product_read(product_data, idx, total_rows)
                    except Exception as cb_err:
                        logger.debug(f"Callback hatası: {cb_err}")

                row_total = time.time() - row_start
                logger.info(f"  [SÜRE] SATIR TOPLAM: {row_total:.2f}s - {product_data.get('urun_adi', '-')[:25]} - Barkod: {barcode or 'YOK'}")

                # Sonraki satırın görünür olması için Alt Ok tuşuna bas
                try:
                    from pywinauto.keyboard import send_keys
                    send_keys("{DOWN}")
                    time.sleep(0.05)  # Kısa bekleme
                except Exception as key_err:
                    logger.debug(f"Down tuşu gönderilemedi: {key_err}")

            except Exception as e:
                logger.error(f"Satır {row_num} hatası: {e}")
                continue

        logger.info(f"\nHIZLI MOD: {len(products)} ürün okundu")
        return products

    def _get_product_data_fast(self, row_num):
        """HIZLI MOD: Temel ürün verilerini al (tıklama yapmadan)

        Sadece temel sütunları okur, tıklama yapmaz.
        """
        try:
            data = {"row": row_num, "ort": 0, "barkod": None, "monthly_sales": {}, "mf_info": None}

            # Her sütunu ayrı ayrı oku ve süresini logla
            t_stok = time.time()
            data["stok"] = self.get_cell_value(row_num, BOTANIK_ELEMENTS["stok"])
            logger.debug(f"    stok okuma: {time.time()-t_stok:.2f}s")

            t_urun = time.time()
            data["urun_adi"] = self.get_cell_value(row_num, BOTANIK_ELEMENTS["urun_adi"])
            logger.debug(f"    urun_adi okuma: {time.time()-t_urun:.2f}s")

            t_mf = time.time()
            data["mf"] = self.get_cell_value(row_num, BOTANIK_ELEMENTS["mf_iht"])
            logger.debug(f"    mf okuma: {time.time()-t_mf:.2f}s")

            t_minstk = time.time()
            data["minstk"] = self.get_cell_value(row_num, BOTANIK_ELEMENTS["minstk"])
            logger.debug(f"    minstk okuma: {time.time()-t_minstk:.2f}s")

            # Değerleri int'e çevir
            try:
                data["stok"] = int(data["stok"]) if data["stok"] else 0
            except (ValueError, TypeError):
                data["stok"] = 0

            try:
                data["mf"] = int(data["mf"]) if data["mf"] else 0
            except (ValueError, TypeError):
                data["mf"] = 0

            try:
                data["minstk"] = int(data["minstk"]) if data["minstk"] else 0
            except (ValueError, TypeError):
                data["minstk"] = 0

            return data
        except Exception as e:
            logger.error(f"Hızlı veri okuma hatası (satır {row_num}): {e}")
            return None
