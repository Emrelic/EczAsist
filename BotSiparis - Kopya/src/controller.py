"""
Ana koordinasyon controller
"""
import time
import math
import os
import csv
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from .botanik.eos_controller import BotanikEOSController
from .depolar.alliance import AllianceDepo
from .depolar.selcuk import SelcukDepo
from .depolar.yusufpasa import YusufPasaDepo
from .depolar.iskoop import IskoopDepo
from .depolar.bursa import BursaDepo
from .depolar.farmazon import FarmazonDepo
from .depolar.sancak import SancakDepo
from .utils import logger, HEADLESS


class MainController:
    """Ana koordinasyon controller'ı"""

    # Varsayılan depo sırası
    DEFAULT_DEPO_ORDER = ["alliance", "selcuk", "yusufpasa", "iskoop", "bursa", "farmazon", "sancak"]

    def __init__(self, gui_window=None):
        self.gui = gui_window
        self.botanik = BotanikEOSController()
        self.depolar = {
            "alliance": AllianceDepo(),
            "selcuk": SelcukDepo(),
            "yusufpasa": YusufPasaDepo(),
            "iskoop": IskoopDepo(),
            "bursa": BursaDepo(),
            "farmazon": FarmazonDepo(),
            "sancak": SancakDepo()
        }
        self.products = []
        self.active_depolar = {}
        self.last_product_start_time = None  # İlaç arası geçiş süresi için

        # .env dosyasını yükle
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        # Gün sayısını oku (varsayılan 30)
        self.gun_sayisi = int(os.getenv("GUN_SAYISI", "30"))

        # Aylık faiz oranını oku (varsayılan %4)
        aylik_faiz_str = os.getenv("AYLIK_FAIZ", "4").replace(",", ".")
        self.aylik_faiz = float(aylik_faiz_str) / 100  # Yüzde → ondalık

        # Botanik controller'a gün sayısını ve GUI'yi aktar
        self.botanik.gun_sayisi = self.gun_sayisi
        self.botanik.gui = self.gui

        # Aylık gidiş CSV dosyası
        self.csv_file = Path(__file__).resolve().parent.parent / "data" / "monthly_sales.csv"
        self.csv_file.parent.mkdir(exist_ok=True)  # data klasörünü oluştur

        # MF (Mal Fazlası) CSV dosyası
        self.mf_csv_file = Path(__file__).resolve().parent.parent / "data" / "mf_cache.csv"

        # Tarama sonuçları JSON dosyası (program açılışında yüklemek için)
        self.scan_results_file = Path(__file__).resolve().parent.parent / "data" / "last_scan.json"

    def get_depo_order(self):
        """Depo sırasını .env'den oku veya varsayılanı kullan

        Returns:
            list: Sıralı depo key listesi ["alliance", "selcuk", ...]
        """
        order_str = os.getenv("DEPO_SIRALAMA", "")
        if order_str:
            # Virgülle ayrılmış listeyi parse et
            order = [d.strip() for d in order_str.split(",") if d.strip()]
            # Geçerli depoları filtrele
            valid_order = [d for d in order if d in self.depolar]
            # Eksik depoları sona ekle
            for d in self.DEFAULT_DEPO_ORDER:
                if d not in valid_order:
                    valid_order.append(d)
            return valid_order
        return self.DEFAULT_DEPO_ORDER.copy()

    def get_available_depolar(self):
        """Kullanılabilir depoları döndür (checkbox seçili + kullanıcı bilgileri var)
        Sıralama DEPO_SIRALAMA ayarına göre yapılır.

        Returns:
            dict: {depo_key: depo_obj} formatında kullanılabilir depolar (sıralı)
        """
        available = {}

        # Depo sırasını al
        depo_order = self.get_depo_order()

        for depo_name in depo_order:
            depo = self.depolar.get(depo_name)
            if not depo:
                continue
            # Depo ayarlardan aktif mi?
            enabled_key = f"{depo_name.upper()}_ENABLED"
            is_enabled = os.getenv(enabled_key, "true").lower() == "true"

            if not is_enabled:
                continue

            # Kullanıcı bilgileri var mı?
            has_credentials = False
            if depo_name == "alliance":
                has_credentials = bool(
                    os.getenv("ALLIANCE_ECZANE_KODU") and
                    os.getenv("ALLIANCE_USERNAME") and
                    os.getenv("ALLIANCE_PASSWORD")
                )
            elif depo_name == "selcuk":
                has_credentials = bool(
                    os.getenv("SELCUK_HESAP_KODU") and
                    os.getenv("SELCUK_USERNAME") and
                    os.getenv("SELCUK_PASSWORD")
                )
            elif depo_name == "yusufpasa":
                has_credentials = bool(
                    os.getenv("YUSUFPASA_ECZANE_KODU") and
                    os.getenv("YUSUFPASA_USERNAME") and
                    os.getenv("YUSUFPASA_PASSWORD")
                )
            elif depo_name == "iskoop":
                has_credentials = bool(
                    os.getenv("ISKOOP_USERNAME") and
                    os.getenv("ISKOOP_PASSWORD")
                )
            elif depo_name == "bursa":
                has_credentials = bool(
                    os.getenv("BURSA_USERNAME") and
                    os.getenv("BURSA_PASSWORD")
                )
            elif depo_name == "farmazon":
                has_credentials = bool(
                    os.getenv("FARMAZON_USERNAME") and
                    os.getenv("FARMAZON_PASSWORD")
                )
            elif depo_name == "sancak":
                has_credentials = bool(
                    os.getenv("SANCAK_USERNAME") and
                    os.getenv("SANCAK_PASSWORD")
                )

            if has_credentials:
                available[depo_name] = depo

        return available

    def run(self, continue_scan=False):
        """Ana işlem akışı

        Args:
            continue_scan: True ise yarım kalmış taramaya devam et
        """
        try:
            start_from_row = None

            # Devam etme modunda - önceki taramayı yükle
            if continue_scan:
                import json
                if self.scan_results_file.exists():
                    with open(self.scan_results_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    start_from_row = data.get("last_scanned_row", 0)
                    logger.info(f"DEVAM MODU: Satır {start_from_row}'dan sonrası taranacak")
                    # Önceki ürünleri yükle (GUI'de zaten yüklü olacak)
                    self.products = data.get("products", [])
                else:
                    logger.warning("Devam edilecek tarama yok, sıfırdan başlanıyor")
                    continue_scan = False

            # Sıfırdan başlama modunda - ürün listesini sıfırla
            if not continue_scan:
                self.products = []
                self.last_product_start_time = None  # Süre hesabını sıfırla
            else:
                # Devam modunda süre hesabını sıfırlama
                self.last_product_start_time = None

            # 1. Botanik EOS'a bağlan
            if self.gui:
                self.gui.update_status("Botanik EOS'a bağlanılıyor...")

            if not self.botanik.connect():
                logger.error("Botanik EOS'a bağlanılamadı!")
                if self.gui:
                    from tkinter import messagebox
                    self.gui.root.after(0, lambda: messagebox.showerror(
                        "Botanik EOS Bulunamadı",
                        "Botanik EOS programı açık değil!\n\n"
                        "Lütfen:\n"
                        "1. Botanik EOS programını açın\n"
                        "2. Sipariş ekranına gidin\n"
                        "3. Tekrar 'Taramayı Başlat' butonuna basın"
                    ))
                    self.gui.update_status("Botanik EOS bulunamadı - Lütfen Botanik'i açın")
                return False

            # Depo kullanıcı bilgilerini oku
            credentials = {
                "alliance": {
                    "eczane_kodu": os.getenv("ALLIANCE_ECZANE_KODU", ""),
                    "username": os.getenv("ALLIANCE_USERNAME", ""),
                    "password": os.getenv("ALLIANCE_PASSWORD", "")
                },
                "selcuk": {
                    "hesap_kodu": os.getenv("SELCUK_HESAP_KODU", ""),
                    "username": os.getenv("SELCUK_USERNAME", ""),
                    "password": os.getenv("SELCUK_PASSWORD", "")
                },
                "yusufpasa": {
                    "eczane_kodu": os.getenv("YUSUFPASA_ECZANE_KODU", ""),
                    "username": os.getenv("YUSUFPASA_USERNAME", ""),
                    "password": os.getenv("YUSUFPASA_PASSWORD", "")
                },
                "iskoop": {
                    "username": os.getenv("ISKOOP_USERNAME", ""),
                    "password": os.getenv("ISKOOP_PASSWORD", "")
                },
                "bursa": {
                    "username": os.getenv("BURSA_USERNAME", ""),
                    "password": os.getenv("BURSA_PASSWORD", "")
                },
                "farmazon": {
                    "username": os.getenv("FARMAZON_USERNAME", ""),
                    "password": os.getenv("FARMAZON_PASSWORD", "")
                },
                "sancak": {
                    "username": os.getenv("SANCAK_USERNAME", ""),
                    "password": os.getenv("SANCAK_PASSWORD", "")
                }
            }

            # 2. Depoları başlat
            if self.gui:
                self.gui.update_status("Depolar açılıyor...")
            self._init_depolar(credentials)

            # Depolar açıldı, GUI'yi en üste getir (sağ tarafta kalacak)
            if self.gui:
                logger.info("Depolar açıldı, GUI en üste getiriliyor...")
                self.gui.root.lift()
                self.gui.root.attributes('-topmost', True)
                self.gui.root.after(100, lambda: self.gui.root.attributes('-topmost', False))

            # Botanik tablosunu hazırla (depolar açıldıktan sonra)
            if self.gui:
                self.gui.update_status("Botanik tablosu hazırlanıyor...")
            self.botanik.prepare_table_for_scan()

            # 3. Tüm sipariş listesini oku (MF hesapla) ve ürünleri anında işle
            if self.gui:
                self.gui.update_status("Sipariş listesi okunuyor ve MF hesaplanıyor...")

            products = self.botanik.get_all_products(
                filter_mf_zero=False,
                skip_mf_write=False,
                on_product=self._process_product,
                start_from_row=start_from_row  # Yarım tarama devam
            )
            logger.info(f"Toplam {len(products)} ürün okundu ve MF alanları güncellendi")

            if not products:
                logger.info("Hiç ürün bulunamadı")
                return True

            logger.info("\n✅ Sipariş listesi okundu, depolar eş zamanlı sorgulandı\n")

            # 4. Depoları açık tut (GUI'den manuel arama için)
            logger.info("Tarama tamamlandı! Depolar açık kalacak...")
            if self.gui:
                self.gui.update_status(f"Tarama tamamlandı - {len(self.products)} ürün")

            return True

        except Exception as e:
            logger.error(f"Ana işlem hatası: {e}")
            return False

    def _is_driver_alive(self, depo):
        """Driver'ın gerçekten çalışıp çalışmadığını kontrol et"""
        if not depo.driver:
            return False
        try:
            # Basit bir komut çalıştırmayı dene
            depo.driver.current_url
            return True
        except Exception:
            return False

    def _init_depolar(self, credentials):
        """Depoları başlat ve otomatik giriş yap

        BROWSER_MODE=windows ise PARALEL açar (çok daha hızlı)
        Akıllı mod: Zaten açık olan depoları kapatmaz, sadece giriş kontrolü yapar.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self.active_depolar = {}
        browser_mode = os.getenv("BROWSER_MODE", "tabs")

        # Önce tüm depoların driver durumunu kontrol et ve zombie driver'ları temizle
        logger.info("Mevcut driver durumları kontrol ediliyor...")
        for depo_name, depo in self.depolar.items():
            if depo.driver:
                if not self._is_driver_alive(depo):
                    logger.warning(f"{depo.name}: Zombie driver tespit edildi, temizleniyor...")
                    try:
                        depo.driver.quit()
                    except:
                        pass
                    depo.driver = None
                    depo.tab_handle = None

        # Açılacak depoları belirle
        depolar_to_open = []
        expected_depo_count = 0  # Açılması beklenen depo sayısı

        for depo_name, depo in self.depolar.items():
            creds = credentials.get(depo_name, {})

            # Depo checkbox ile devre dışı bırakılmış mı?
            enabled_key = f"{depo_name.upper()}_ENABLED"
            is_enabled = os.getenv(enabled_key, "true").lower() == "true"

            if not is_enabled:
                logger.info(f"{depo.name}: Ayarlardan devre dışı bırakılmış, atlanıyor...")
                if depo.driver:
                    try:
                        depo.close()
                        logger.info(f"{depo.name}: Browser kapatıldı (devre dışı)")
                    except:
                        pass
                continue

            # Gerekli kullanıcı bilgileri var mı?
            has_credentials = False
            if depo_name == "alliance":
                has_credentials = bool(creds.get("eczane_kodu") and creds.get("username") and creds.get("password"))
            elif depo_name == "selcuk":
                has_credentials = bool(creds.get("hesap_kodu") and creds.get("username") and creds.get("password"))
            elif depo_name == "yusufpasa":
                has_credentials = bool(creds.get("eczane_kodu") and creds.get("username") and creds.get("password"))
            elif depo_name in ["iskoop", "bursa", "farmazon", "sancak"]:
                has_credentials = bool(creds.get("username") and creds.get("password"))

            if not has_credentials:
                logger.info(f"{depo.name}: Kullanıcı bilgileri girilmemiş, atlanıyor...")
                continue

            # Bu depo açılması gereken bir depo
            expected_depo_count += 1

            # Browser zaten açık ve giriş yapılmış mı?
            if depo.driver and self._is_driver_alive(depo):
                try:
                    depo.switch_to_tab()
                    current_url = depo.driver.current_url
                    logger.info(f"{depo.name}: Browser zaten açık (URL: {current_url[:50]}...)")

                    login_indicators = ["login", "giris", "signin", "oturum", "Customer_username"]
                    page_source = depo.driver.page_source[:5000].lower()
                    is_on_login_page = any(ind.lower() in current_url.lower() or ind.lower() in page_source for ind in login_indicators)

                    if not is_on_login_page:
                        logger.info(f"{depo.name}: ✓ Zaten giriş yapılmış, devam ediliyor...")
                        self.active_depolar[depo_name] = depo
                        continue
                    else:
                        logger.info(f"{depo.name}: Login sayfasında, yeniden giriş gerekli...")
                except Exception as e:
                    logger.warning(f"{depo.name}: Browser kontrolü başarısız ({e}), yeniden açılacak...")
                    try:
                        depo.driver.quit()
                    except:
                        pass
                    depo.driver = None
                    depo.tab_handle = None

            depolar_to_open.append((depo_name, depo, creds))

        logger.info(f"Toplam {expected_depo_count} depo açılması gerekiyor, {len(self.active_depolar)} zaten açık, {len(depolar_to_open)} yeni açılacak")

        if not depolar_to_open:
            logger.info("Tüm depolar zaten açık veya hiç aktif depo yok")
            return

        # ========== PARALEL AÇMA (windows modu) ==========
        if browser_mode == "windows" and len(depolar_to_open) > 1:
            logger.info(f"🚀 PARALEL DEPO AÇMA başlıyor - {len(depolar_to_open)} depo")

            if self.gui:
                self.gui.update_status(f"⏳ {len(depolar_to_open)} depo paralel açılıyor...")

            def open_single_depo(info):
                """Tek bir depoyu aç ve giriş yap"""
                depo_name, depo, creds = info
                try:
                    logger.info(f"[PARALEL] {depo.name}: Açılıyor...")

                    if not depo.init_driver(headless=HEADLESS):
                        logger.error(f"[PARALEL] {depo.name} başlatılamadı!")
                        return depo_name, None

                    if not depo.open_page():
                        logger.error(f"[PARALEL] {depo.name} sayfası açılamadı!")
                        return depo_name, None

                    time.sleep(0.5)

                    # Login
                    login_success = False
                    if depo_name == "alliance":
                        login_success = depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                    elif depo_name == "selcuk":
                        login_success = depo.login(creds["hesap_kodu"], creds["username"], creds["password"])
                    elif depo_name == "yusufpasa":
                        login_success = depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                    elif depo_name in ["iskoop", "bursa", "farmazon", "sancak"]:
                        login_success = depo.login(creds["username"], creds["password"])

                    if login_success:
                        logger.info(f"[PARALEL] ✓ {depo.name}: Giriş başarılı!")
                        return depo_name, depo
                    else:
                        logger.warning(f"[PARALEL] ✗ {depo.name}: Giriş başarısız!")
                        return depo_name, None

                except Exception as e:
                    logger.error(f"[PARALEL] {depo.name} açılırken hata: {e}")
                    return depo_name, None

            # Tüm depoları paralel aç
            with ThreadPoolExecutor(max_workers=len(depolar_to_open)) as executor:
                futures = [executor.submit(open_single_depo, info) for info in depolar_to_open]

                for future in as_completed(futures):
                    depo_name, depo = future.result()
                    if depo:
                        self.active_depolar[depo_name] = depo
                        if self.gui:
                            self.gui.update_status(f"✓ {depo.name} açıldı ({len(self.active_depolar)}/{len(depolar_to_open)})")

            logger.info(f"🚀 PARALEL AÇMA TAMAMLANDI: {len(self.active_depolar)}/{len(depolar_to_open)} depo")

            # Başarısız depoları tespit et ve yeniden dene
            failed_depolar = [(name, depo, creds) for name, depo, creds in depolar_to_open if name not in self.active_depolar]
            if failed_depolar:
                logger.warning(f"⚠️ {len(failed_depolar)} depo açılamadı, sırayla yeniden deneniyor...")
                if self.gui:
                    self.gui.update_status(f"⚠️ {len(failed_depolar)} depo yeniden deneniyor...")

                for depo_name, depo, creds in failed_depolar:
                    try:
                        logger.info(f"[RETRY] {depo.name}: Yeniden açılıyor...")
                        # Önceki driver'ı temizle
                        if depo.driver:
                            try:
                                depo.driver.quit()
                            except:
                                pass
                            depo.driver = None
                            depo.tab_handle = None

                        if not depo.init_driver(headless=HEADLESS):
                            logger.error(f"[RETRY] {depo.name} başlatılamadı!")
                            continue

                        if not depo.open_page():
                            logger.error(f"[RETRY] {depo.name} sayfası açılamadı!")
                            continue

                        time.sleep(1)

                        login_success = False
                        if depo_name == "alliance":
                            login_success = depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                        elif depo_name == "selcuk":
                            login_success = depo.login(creds["hesap_kodu"], creds["username"], creds["password"])
                        elif depo_name == "yusufpasa":
                            login_success = depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                        elif depo_name in ["iskoop", "bursa", "farmazon", "sancak"]:
                            login_success = depo.login(creds["username"], creds["password"])

                        if login_success:
                            logger.info(f"[RETRY] ✓ {depo.name}: Giriş başarılı!")
                            self.active_depolar[depo_name] = depo
                        else:
                            logger.error(f"[RETRY] ✗ {depo.name}: Giriş başarısız!")

                    except Exception as e:
                        logger.error(f"[RETRY] {depo.name} açılırken hata: {e}")

                logger.info(f"🔄 YENİDEN DENEME TAMAMLANDI: {len(self.active_depolar)}/{len(depolar_to_open)} depo")

        # ========== SIRAYLA AÇMA (tabs modu veya tek depo) ==========
        else:
            for depo_name, depo, creds in depolar_to_open:
                try:
                    if self.gui:
                        self.gui.update_status(f"⏳ {depo.name} açılıyor...")

                    logger.info(f"{depo.name}: Yeni browser açılıyor...")
                    if not depo.init_driver(headless=HEADLESS):
                        logger.error(f"{depo.name} başlatılamadı!")
                        continue

                    if not depo.open_page():
                        logger.error(f"{depo.name} sayfası açılamadı!")
                        continue

                    time.sleep(1)

                    logger.info(f"{depo.name}: Otomatik giriş yapılıyor...")
                    login_success = False
                    if depo_name == "alliance":
                        login_success = depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                    elif depo_name == "selcuk":
                        login_success = depo.login(creds["hesap_kodu"], creds["username"], creds["password"])
                    elif depo_name == "yusufpasa":
                        login_success = depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                    elif depo_name in ["iskoop", "bursa", "farmazon", "sancak"]:
                        login_success = depo.login(creds["username"], creds["password"])

                    if login_success:
                        logger.info(f"{depo.name}: ✓ Giriş başarılı!")
                        self.active_depolar[depo_name] = depo
                    else:
                        logger.warning(f"{depo.name}: ✗ Giriş başarısız!")

                    time.sleep(1)

                except Exception as e:
                    logger.error(f"{depo.name} açılırken hata: {e}")
                    continue

        # Son kontrol: Beklenen sayıda depo açıldı mı?
        if expected_depo_count > 0:
            opened_count = len(self.active_depolar)
            if opened_count < expected_depo_count:
                missing_count = expected_depo_count - opened_count
                logger.error(f"⚠️ DİKKAT: {missing_count} depo açılamadı! (Açılan: {opened_count}/{expected_depo_count})")
                if self.gui:
                    self.gui.update_status(f"⚠️ {missing_count} depo açılamadı! ({opened_count}/{expected_depo_count})")
                    # Kullanıcıya uyarı göster
                    from tkinter import messagebox
                    self.gui.root.after(500, lambda: messagebox.showwarning(
                        "Depo Uyarısı",
                        f"{missing_count} depo açılamadı!\n\n"
                        f"Açılan: {opened_count} / Beklenen: {expected_depo_count}\n\n"
                        f"Lütfen ayarları kontrol edin veya programı yeniden başlatın."
                    ))
            else:
                logger.info(f"✓ Tüm depolar başarıyla açıldı: {opened_count}/{expected_depo_count}")
                if self.gui:
                    self.gui.update_status(f"✓ {opened_count} depo hazır")

        # Depolar açıldıktan sonra GUI penceresini öne getir
        if self.gui:
            try:
                logger.info("Depolar açıldı, GUI penceresi öne getiriliyor...")
                self.gui.root.lift()
                self.gui.root.attributes('-topmost', True)
                self.gui.root.after(200, lambda: self.gui.root.attributes('-topmost', False))
                logger.info("✓ GUI penceresi en üste getirildi")
            except Exception as e:
                logger.error(f"GUI penceresi öne getirilemedi: {e}")

    def merge_browser_windows_to_tabs(self):
        """Tarama bittikten sonra tüm depo pencerelerini tek pencerede sekmelere birleştir"""
        try:
            logger.info("Depo pencereleri tek pencerede birleştiriliyor...")

            # İlk açık depoyu bul (ana browser olacak)
            main_depo = None
            main_driver = None
            for depo_name, depo in self.active_depolar.items():
                if depo.driver:
                    main_depo = depo
                    main_driver = depo.driver
                    logger.info(f"{depo.name} ana browser olarak seçildi")
                    break

            if not main_driver:
                logger.warning("Ana browser bulunamadı, birleştirme iptal edildi")
                return False

            # Diğer depoları ana browser'a tab olarak taşı
            for depo_name, depo in self.active_depolar.items():
                if depo == main_depo:
                    continue

                if not depo.driver:
                    continue

                try:
                    # Bu deponun mevcut URL'sini al
                    depo.switch_to_tab()
                    current_url = depo.driver.current_url

                    # Ana browser'da yeni tab aç ve bu URL'i yükle
                    main_driver.execute_script("window.open('');")
                    new_tab = main_driver.window_handles[-1]
                    main_driver.switch_to.window(new_tab)
                    main_driver.get(current_url)

                    # Eski depo driver'ını kapat ve yeni tab'ı ata
                    old_driver = depo.driver
                    depo.driver = main_driver
                    depo.tab_handle = new_tab

                    # Eski browser'ı kapat (eğer başka tab yoksa)
                    try:
                        if old_driver != main_driver:
                            old_driver.quit()
                    except:
                        pass

                    logger.info(f"{depo.name} ana browser'a tab olarak eklendi")
                    time.sleep(0.5)

                except Exception as e:
                    logger.error(f"{depo.name} birleştirilemedi: {e}")

            logger.info("✓ Tüm depolar tek pencerede birleştirildi!")
            return True

        except Exception as e:
            logger.error(f"Browser birleştirme hatası: {e}")
            return False

    def separate_browser_windows(self):
        """Birleştirilmiş sekmeleri tekrar ayrı pencerelere çıkar (hız için)"""
        try:
            logger.info("Sekmeler ayrı pencerelere çıkarılıyor (hız için)...")

            # Tüm depoları kontrol et
            depolar_to_separate = []
            main_driver = None

            # Hangi depoların aynı driver'ı paylaştığını bul
            driver_groups = {}
            for depo_name, depo in self.active_depolar.items():
                if depo.driver:
                    driver_id = id(depo.driver)
                    if driver_id not in driver_groups:
                        driver_groups[driver_id] = []
                    driver_groups[driver_id].append(depo)

            # Eğer hiçbir driver grubu yoksa veya zaten hepsi ayrıysa
            if len(driver_groups) == len(self.active_depolar):
                logger.info("Tüm depolar zaten ayrı pencerelerde")
                return True

            # Her grup için (aynı driver'ı paylaşan depolar)
            for driver_id, depo_group in driver_groups.items():
                if len(depo_group) <= 1:
                    # Zaten ayrı
                    continue

                # İlk depo ana driver'ı tutar, diğerleri yeni pencere alır
                main_depo = depo_group[0]
                main_driver = main_depo.driver

                for depo in depo_group[1:]:
                    try:
                        # Yeni driver başlat
                        from selenium import webdriver
                        from selenium.webdriver.chrome.service import Service
                        from webdriver_manager.chrome import ChromeDriverManager

                        options = webdriver.ChromeOptions()
                        options.add_argument('--disable-blink-features=AutomationControlled')
                        options.add_argument('--disable-notifications')
                        options.add_argument('--disable-infobars')
                        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])

                        prefs = {
                            "credentials_enable_service": False,
                            "profile.password_manager_enabled": False,
                        }
                        options.add_experimental_option("prefs", prefs)

                        service = Service(ChromeDriverManager().install())
                        new_driver = webdriver.Chrome(service=service, options=options)

                        # Ekranın sağ yarısına yerleştir
                        try:
                            import pyautogui
                            screen_width, screen_height = pyautogui.size()
                            window_width = screen_width // 2
                            window_height = screen_height
                            x_position = screen_width // 2
                            y_position = 0
                            new_driver.set_window_size(window_width, window_height)
                            new_driver.set_window_position(x_position, y_position)
                        except:
                            pass

                        # Mevcut URL'i yeni pencerede aç
                        depo.switch_to_tab()
                        current_url = depo.driver.current_url

                        # Yeni driver'a geç
                        depo.driver = new_driver
                        depo.tab_handle = new_driver.current_window_handle
                        depo.driver.get(current_url)

                        logger.info(f"{depo.name} yeni pencereye taşındı")
                        time.sleep(0.5)

                    except Exception as e:
                        logger.error(f"{depo.name} ayrılamadı: {e}")

            logger.info("✓ Sekmeler ayrı pencerelere çıkarıldı!")
            return True

        except Exception as e:
            logger.error(f"Pencere ayırma hatası: {e}")
            return False

    def _process_product(self, product, idx=None, total=None):
        """Botanikten okunan ürünü anında depolarda sorgula ve sonuçları yaz"""
        try:
            # Önceki ilacın gerçek süresini hesapla (bir sonraki ilaca geçiş süresi)
            if hasattr(self, 'last_product_start_time') and self.last_product_start_time:
                real_duration = time.time() - self.last_product_start_time
                logger.info(f"Önceki ilaç toplam süresi: {real_duration:.1f}s")
                # GUI'deki timer'ı güncelle
                if self.gui:
                    self.gui.last_product_duration = real_duration

            # İşlem başlangıç zamanını kaydet
            start_time = time.time()
            self.last_product_start_time = start_time

            # Pause kontrolü
            if self.gui and hasattr(self.gui, 'pause_event'):
                self.gui.pause_event.wait()

            if self.gui and idx and total:
                self.gui.update_status(f"Ürün {idx}/{total} sorgulanıyor: {product.get('urun_adi', '-')}")

            if idx and total:
                logger.info(f"\n--- Ürün {idx}/{total}: {product.get('urun_adi')} ---")
            else:
                logger.info(f"\n--- Ürün: {product.get('urun_adi')} ---")

            if not product.get("barkod"):
                logger.warning("Bu ürün için barkod bulunamadı, atlanıyor...")
                return

            # Her depoda sorgula
            self._query_depolar(product)

            # En karlı seçeneği hesapla ve product'a ekle
            en_karli_sonuc = self.bul_en_karli_secenek(product)
            if en_karli_sonuc:
                product["en_karli_sonuc"] = en_karli_sonuc
                en_karli = en_karli_sonuc.get("en_karli", {})
                logger.info(f"En karlı: {en_karli.get('depo')} {en_karli.get('sart')} = {en_karli.get('efektif_birim')} TL/ad")

            # Botanik açıklama alanını güncelle (kullanıcının manuel notunu koru)
            depo_aciklama = self._build_aciklama_text(product)
            try:
                # Mevcut açıklamayı oku
                mevcut_aciklama = self.botanik.get_aciklama_value(product["row"])
                # Kullanıcının manuel notunu ayır
                user_aciklama = self._extract_user_aciklama(mevcut_aciklama)
                # Birleştir
                aciklama_ozeti = self._build_full_aciklama(depo_aciklama, user_aciklama)
                product["aciklama_ozeti"] = aciklama_ozeti

                # Sıralı okumada scroll'u atla (HIZLANDIRMA)
                if not self.botanik.set_aciklama_value(product["row"], aciklama_ozeti or "", skip_scroll=True):
                    logger.warning(f"Satır {product['row']}: Açıklama yazılamadı")
            except Exception as e:
                logger.error(f"Satır {product['row']}: Açıklama güncellenirken hata: {e}")

            # GUI'ye eklemeden hemen önce süreyi hesapla (en doğru süre)
            duration = time.time() - start_time
            product["processing_duration"] = duration

            # GUI'de göster
            if self.gui:
                self.gui.add_product_row(product)

            # Controller içinde kaydet
            self.products.append(product)

            # Tarama sonuçlarını JSON'a kaydet (anlık - program kapansa bile kaybolmasın)
            self.save_scan_results()

            # Aylık gidiş bilgisini CSV'ye kaydet
            self.save_monthly_sales_to_csv(product)

            # MF bilgisini CSV'ye kaydet - SADECE AYAR AÇIKSA
            mf_enabled = os.getenv("MF_ENABLED", "true").lower() == "true"
            if mf_enabled:
                self.save_mf_to_csv(product)

            # Rastgele bekleme (6-8 saniye) - robot algılamasını önlemek için
            import random
            delay = random.uniform(6, 8)
            logger.debug(f"Sonraki ürün için {delay:.1f} saniye bekleniyor...")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Ürün işlenirken hata: {e}")

    def _query_depolar(self, product):
        """Ürünü tüm depolarda paralel sorgula"""
        barcode = product["barkod"]
        target_depolar = self.active_depolar or self.depolar

        if not target_depolar:
            logger.warning("Aktif depo bulunamadı, sorgu atlanıyor")
            return

        def worker(depo_key, depo_obj):
            try:
                logger.info(f"{depo_obj.name} sorgulanıyor...")

                if depo_obj.search_barcode(barcode):
                    stok_durum = depo_obj.check_stock_status()

                    # Depodan ürün adını al (listede yoksa kullanılacak)
                    if hasattr(depo_obj, 'get_product_name'):
                        try:
                            depo_urun_adi = depo_obj.get_product_name()
                            if depo_urun_adi:
                                stok_durum["urun_adi"] = depo_urun_adi
                        except Exception as name_err:
                            logger.debug(f"{depo_obj.name}: Ürün adı alınamadı: {name_err}")

                    if stok_durum["stok_var"]:
                        logger.info(f"{depo_obj.name}: ✓ STOKTA VAR")
                    else:
                        logger.info(f"{depo_obj.name}: ✗ Stokta yok - {stok_durum['mesaj']}")
                    return depo_key, stok_durum
                else:
                    return depo_key, {
                        "stok_var": False,
                        "mesaj": "Arama hatası",
                        "detay": "Barkod aranamadı"
                    }
            except Exception as e:
                logger.error(f"{depo_obj.name} sorgulanırken hata: {e}")
                return depo_key, {
                    "stok_var": False,
                    "mesaj": "Hata",
                    "detay": str(e)
                }

        with ThreadPoolExecutor(max_workers=len(target_depolar)) as executor:
            futures = [
                executor.submit(worker, depo_key, depo)
                for depo_key, depo in target_depolar.items()
            ]
            for future in as_completed(futures):
                try:
                    depo_key, stok_durum = future.result()
                    product[f"{depo_key}_durum"] = stok_durum

                    # Ürün adı boş/bilinmiyorsa depodan gelen adı kullan
                    current_name = product.get("urun_adi", "")
                    if (not current_name or current_name in ["?", "-", ""]) and stok_durum.get("urun_adi"):
                        product["urun_adi"] = stok_durum["urun_adi"]
                        logger.info(f"Ürün adı depodan alındı ({depo_key}): {stok_durum['urun_adi']}")

                except Exception as future_error:
                    logger.error(f"Depo sonucu alınamadı: {future_error}")

    def search_barcode_all_depolar(self, barcode):
        """Tek bir barkodu tüm depolarda ara ve sonuçları döndür

        Args:
            barcode: Aranacak barkod

        Returns:
            dict: {"barcode": str, "product_name": str, "depo_results": {...}}
        """
        try:
            target_depolar = self.active_depolar or self.depolar
            if not target_depolar:
                logger.warning("Aktif depo bulunamadı")
                return None

            result = {
                "barcode": barcode,
                "product_name": "",
                "depo_results": {}
            }

            # Geçersiz ürün adları listesi (sayfa UI elementleri)
            GECERSIZ_URUN_ADLARI = [
                "hızlı sipariş", "ürün ara", "sipariş ver", "sipariş",
                "ana sayfa", "anasayfa", "kategoriler", "sepet",
                "alliance healthcare", "selçuk ecza", "yusuf paşa",
                "farmazon", "iskoop", "bursa ecza", "sancak"
            ]

            def worker(depo_key, depo_obj):
                try:
                    logger.info(f"{depo_obj.name}: Barkod aranıyor: {barcode}")

                    if depo_obj.search_barcode(barcode):
                        stok_durum = depo_obj.check_stock_status()

                        # Fiyat ve şartları al
                        fiyat = stok_durum.get("fiyat", 0) or 0
                        sart = stok_durum.get("sart", "") or ""
                        stok_var = stok_durum.get("stok_var", False)
                        satis_kosullari = stok_durum.get("satis_kosullari", [])

                        # Ürün adı al
                        # - Stok varsa: tüm depolardan al
                        # - Stok yoksa: sadece Farmazon'dan al (Farmazon'da ilan olmasa bile ürün adı görünür)
                        urun_adi = ""
                        if hasattr(depo_obj, 'get_product_name'):
                            # Stok varsa veya Farmazon ise ürün adını almayı dene
                            if stok_var or depo_key == "farmazon":
                                try:
                                    urun_adi = depo_obj.get_product_name() or ""
                                    # Geçersiz ürün adlarını filtrele
                                    if urun_adi and urun_adi.lower().strip() in GECERSIZ_URUN_ADLARI:
                                        logger.warning(f"{depo_obj.name}: Geçersiz ürün adı filtrelendi: {urun_adi}")
                                        urun_adi = ""
                                except:
                                    pass

                        return depo_key, {
                            "stok_var": stok_var,
                            "fiyat": fiyat,
                            "sart": sart,
                            "urun_adi": urun_adi,
                            "satis_kosullari": satis_kosullari
                        }
                    else:
                        return depo_key, None

                except Exception as e:
                    logger.error(f"{depo_obj.name} barkod arama hatası: {e}")
                    return depo_key, None

            # Paralel sorgula
            with ThreadPoolExecutor(max_workers=len(target_depolar)) as executor:
                futures = [
                    executor.submit(worker, depo_key, depo)
                    for depo_key, depo in target_depolar.items()
                ]
                for future in as_completed(futures):
                    try:
                        depo_key, depo_result = future.result()
                        if depo_result:
                            result["depo_results"][depo_key] = depo_result

                    except Exception as e:
                        logger.error(f"Depo sonucu alınamadı: {e}")

                # İlk bulunan ürün adını kullan (hangi depodan gelirse gelsin)
                for depo_key, depo_result in result["depo_results"].items():
                    if depo_result and depo_result.get("urun_adi"):
                        result["product_name"] = depo_result["urun_adi"]
                        logger.info(f"Ürün adı '{depo_key}' deposundan alındı: {depo_result['urun_adi']}")
                        break

            logger.info(f"Barkod {barcode}: {len(result['depo_results'])} depoda bulundu")
            return result if result["depo_results"] else None

        except Exception as e:
            logger.error(f"search_barcode_all_depolar hatası: {e}")
            return None

    # Depo açıklama formatı ayırıcı karakteri
    ACIKLAMA_SEPARATOR = "§"

    def _extract_user_aciklama(self, mevcut_aciklama):
        """Mevcut açıklamadan kullanıcının manuel yazdığı kısmı ayır

        Açıklama formatı: "[Kullanıcı notu] § [Depo bilgisi]"
        veya sadece "[Depo bilgisi]" (kullanıcı notu yoksa)

        Args:
            mevcut_aciklama: Mevcut açıklama değeri

        Returns:
            str: Kullanıcının manuel yazdığı kısım (yoksa "")
        """
        if not mevcut_aciklama or not mevcut_aciklama.strip():
            return ""

        mevcut = mevcut_aciklama.strip()

        # Bizim formatımızı tanıyan başlangıçlar
        # Tüm depo kısaltmaları: Fz, Al, Se, Yu, Ys, İs, Ko, Bu, Sa
        bizim_format_baslangiclar = [
            "Fz:", "Fz ", "Fz(", "Fz Pahalı",
            "Al ", "Al(",
            "Se ", "Se(",
            "Yu ", "Yu(", "Ys ", "Ys(",
            "İs ", "İs(", "Ko ", "Ko(",
            "Bu ", "Bu(",
            "Sa ", "Sa(",
            "Ara(", "(", "-"
        ]

        def is_bizim_format(text):
            """Verilen metnin bizim formatımız olup olmadığını kontrol et"""
            if not text or not text.strip():
                return True  # Boş = bizim format (depo yok)
            text = text.strip()
            if text == " " or text == "-":
                return True
            for baslangic in bizim_format_baslangiclar:
                if text.startswith(baslangic):
                    return True
            return False

        # Separator varsa, sol kısmı kontrol et
        if self.ACIKLAMA_SEPARATOR in mevcut:
            parts = mevcut.split(self.ACIKLAMA_SEPARATOR, 1)
            user_part = parts[0].strip()
            # Sol kısım bizim formatımızsa, kullanıcı notu yok
            if is_bizim_format(user_part):
                logger.debug(f"[Açıklama] '{user_part}' bizim formatımız, kullanıcı notu yok")
                return ""
            logger.debug(f"[Açıklama] Kullanıcı notu bulundu: '{user_part}'")
            return user_part

        # Separator yoksa, tamamının bizim formatımız olup olmadığını kontrol et
        if is_bizim_format(mevcut):
            return ""

        # Hiçbiri değilse, tamamı kullanıcı notu (eski format, separator yok)
        return mevcut

    def _build_full_aciklama(self, depo_aciklama, user_aciklama):
        """Kullanıcı notu ve depo açıklamasını birleştir

        Args:
            depo_aciklama: Depo bilgisi açıklaması
            user_aciklama: Kullanıcının manuel yazdığı not

        Returns:
            str: Birleştirilmiş açıklama
        """
        if user_aciklama and user_aciklama.strip():
            if depo_aciklama and depo_aciklama.strip():
                return f"{user_aciklama} {self.ACIKLAMA_SEPARATOR} {depo_aciklama}"
            else:
                return user_aciklama
        else:
            return depo_aciklama if depo_aciklama else " "

    def _build_aciklama_text(self, product):
        """Depo sonuçlarını kısa açıklama formatına çevir

        Format:
        - Fiyatlar AÇIK: Fz:80,00/120,00 All, Sel, Yus
        - Fiyatlar KAPALI: Fz, All, Sel, Yus

        - Fz:80,00 - Farmazon fiyatı (opsiyonel)
        - /120,00 - Depocu fiyatı (Alliance'dan, opsiyonel)
        - All, Sel, Yus - Stokta olan depolar (Farmazon hariç)
        - Ara (depo1, depo2) - Depoyu ara durumundakiler
        """
        # Fiyatları göster ayarı
        show_prices = os.getenv("SHOW_PRICES", "true").lower() == "true"

        var_list = []
        ara_list = []
        farmazon_fiyat = None
        farmazon_pahali = False  # Farmazon pahalı mı?
        depo_price = None
        alliance_sart = None  # Alliance'dan gelen şart bilgisi (10+1 gibi)

        # Sadece kullanılabilir depoların bilgilerini kullan
        available_depolar = self.get_available_depolar()

        for depo_key, depo in available_depolar.items():
            durum = product.get(f"{depo_key}_durum")
            if not durum:
                continue

            depo_name = (depo.name or depo_key).strip()
            # 2 harfli kısaltma kullan (alan tasarrufu için)
            short_name = depo_name[:2].strip() if depo_name else depo_key[:2].upper()
            if not short_name:
                short_name = depo_key[:2].upper()

            # Alliance'dan depocu fiyatını ve şart bilgisini al (stok durumundan bağımsız)
            if depo_key == "alliance":
                if durum.get("fiyat") is not None:
                    depo_price = durum.get("fiyat")
                if durum.get("sart"):
                    alliance_sart = durum.get("sart")
                    logger.debug(f"Alliance şart bilgisi: {alliance_sart}")

            # Farmazon pahalı kontrolü
            if depo_key == "farmazon" and durum.get("pahali"):
                farmazon_pahali = True
                farmazon_fiyat = durum.get("fiyat")  # Fiyatı da sakla (göstermek için)
                continue  # Pahalı Farmazon'u var_list'e ekleme

            if durum.get("stok_var"):
                # Farmazon fiyatını sakla ama listeye ekleme
                if depo_key == "farmazon":
                    farmazon_fiyat = durum.get("fiyat")
                    continue  # Farmazon'u var_list'e ekleme
                else:
                    # Diğer depolar için sadece isim ekle
                    var_list.append(short_name)
                continue

            # Ara durumu
            mesaj = str(durum.get("mesaj", "")).lower()
            if "depoyu ara" in mesaj:
                ara_list.append(short_name)

        # Formatı oluştur
        parts = []

        # Farmazon pahalı ve alternatif yoksa "Fz Pahalı" yaz
        if farmazon_pahali and not var_list:
            # Diğer depolarda stok yok, sadece Farmazon var ama pahalı
            return "Fz Pahalı"

        # Fiyatları göster ayarına göre format
        if show_prices:
            # FİYATLAR GÖSTER AÇIK: Fz:270,00/300,40 All, Sel, Bur (10+2) Ara(...)
            if farmazon_fiyat:
                # Noktalı virgülü virgüle çevir (Türkçe format)
                fz_price_str = f"{farmazon_fiyat:.2f}".replace(".", ",")

                if depo_price:
                    # Alliance fiyatı da varsa ekle
                    depo_price_str = f"{depo_price:.2f}".replace(".", ",")
                    parts.append(f"Fz:{fz_price_str}/{depo_price_str}")
                else:
                    # Sadece Farmazon fiyatı
                    parts.append(f"Fz:{fz_price_str}")

            # Depo adlarını ekle (virgülsüz, boşlukla ayır - alan tasarrufu)
            if var_list:
                parts.append(' '.join(var_list))

            # Şart/MF bilgisini ekle (depo listesinden sonra, ara'dan önce) - SADECE AYAR AÇIKSA
            mf_enabled = os.getenv("MF_ENABLED", "true").lower() == "true"
            if mf_enabled:
                # Öncelik: Alliance şart > mf_info
                if alliance_sart:
                    parts.append(f"({alliance_sart})")
                else:
                    mf_info = product.get("mf_info")
                    if mf_info and mf_info.get("adet") and mf_info.get("mf"):
                        adet = mf_info.get("adet")
                        mf_val = mf_info.get("mf")
                        parts.append(f"({adet}+{mf_val})")

            # Ara durumu (virgülsüz)
            if ara_list:
                parts.append(f"Ara({' '.join(ara_list)})")
        else:
            # FİYATLAR GÖSTER KAPALI: Fz, All, Sel, Bur (10+2) Ara(...) (sadece isimler)
            # Farmazon varsa "Fz" ekle (fiyatsız)
            if farmazon_fiyat:
                var_list.insert(0, "Fz")  # En başa ekle

            # Depo adlarını ekle (virgülsüz, boşlukla ayır - alan tasarrufu)
            if var_list:
                parts.append(' '.join(var_list))

            # Şart/MF bilgisini ekle (depo listesinden sonra, ara'dan önce) - SADECE AYAR AÇIKSA
            mf_enabled = os.getenv("MF_ENABLED", "true").lower() == "true"
            if mf_enabled:
                # Öncelik: Alliance şart > mf_info
                if alliance_sart:
                    parts.append(f"({alliance_sart})")
                else:
                    mf_info = product.get("mf_info")
                    if mf_info and mf_info.get("adet") and mf_info.get("mf"):
                        adet = mf_info.get("adet")
                        mf_val = mf_info.get("mf")
                        parts.append(f"({adet}+{mf_val})")

            # Ara durumu (virgülsüz)
            if ara_list:
                parts.append(f"Ara({' '.join(ara_list)})")

        # Eğer hiçbir bilgi yoksa, boşluk koy (depo yok anlamında)
        result = ' '.join(parts)
        if not result or result.strip() == "":
            return " "  # Boşluk (hiçbir depoda stok yok)

        return result

    def _build_aciklama_efektif(self, product):
        """Efektif değer bazlı açıklama formatı (hızlı tarama için)

        Format: Al(10+2) Se(5+1) Ara(Ys)
        - Efektif değeri en düşük olan + 5 kuruş içindekiler şartlarıyla
        - Ara durumundaki depolar
        - Stokta yok olanlar yazılmaz

        Args:
            product: Ürün bilgileri (en_karli_sonuc dahil)

        Returns:
            str: Açıklama metni
        """
        parts = []
        ara_list = []

        # Depo kısaltmaları
        depo_kisaltma = {
            "alliance": "Al",
            "selcuk": "Se",
            "yusufpasa": "Ys",
            "iskoop": "Ko",
            "bursa": "Bu",
            "farmazon": "Fz",
            "sancak": "Sa"
        }

        # En karlı sonuçları al
        en_karli_sonuc = product.get("en_karli_sonuc")

        if en_karli_sonuc:
            tum_secenekler = en_karli_sonuc.get("tum_secenekler", [])
            en_karli = en_karli_sonuc.get("en_karli")

            if en_karli and tum_secenekler:
                en_dusuk_efektif = en_karli.get("efektif_birim", 0)

                # 5 kuruş tolerans içindekileri bul
                for secenek in tum_secenekler:
                    efektif = secenek.get("efektif_birim", 0)
                    fark = abs(efektif - en_dusuk_efektif)

                    if fark <= 0.05:  # 5 kuruş tolerans
                        depo_key = secenek.get("depo", "")
                        sart = secenek.get("sart", "")
                        kisaltma = depo_kisaltma.get(depo_key, depo_key[:2].capitalize())

                        # Farmazon için optimum adet göster
                        if depo_key == "farmazon":
                            optimum_adet = secenek.get("optimum_adet", secenek.get("min_adet", 1))
                            if optimum_adet and optimum_adet > 1:
                                parts.append(f"{kisaltma}({optimum_adet})")
                            else:
                                parts.append(kisaltma)
                        elif sart and sart != "1":
                            parts.append(f"{kisaltma}({sart})")
                        else:
                            parts.append(kisaltma)

        # Ara durumundaki depoları bul
        available_depolar = self.get_available_depolar()
        for depo_key in available_depolar:
            durum = product.get(f"{depo_key}_durum")
            if not durum:
                continue

            mesaj = str(durum.get("mesaj", "")).lower()
            if "depoyu ara" in mesaj:
                kisaltma = depo_kisaltma.get(depo_key, depo_key[:2].capitalize())
                ara_list.append(kisaltma)

        # Ara listesini ekle
        if ara_list:
            parts.append(f"Ara({' '.join(ara_list)})")

        # Sonuç
        result = ' '.join(parts)
        if not result or result.strip() == "":
            return " "  # Boşluk (hiçbir depoda stok yok)

        return result

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

    def _calculate_order_quantity(self, product):
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

    def place_orders(self, products):
        """Seçili ürünler için sipariş ver (Adet alanına yazar)

        Not: MF alanı tarama sırasında zaten doldurulmuştur

        Args:
            products: Sipariş verilecek ürünler listesi
        """
        try:
            logger.info(f"{len(products)} ürün için sipariş veriliyor...")

            for idx, product in enumerate(products, 1):
                row_num = product["row"]
                siparis_adet = product.get("siparis_adet", 0)

                if siparis_adet <= 0:
                    logger.warning(f"Ürün {idx}: Sipariş adedi 0, atlanıyor...")
                    continue

                logger.info(f"Ürün {idx}/{len(products)}: Satır {row_num}, Sipariş Adedi: {siparis_adet}")

                # ADET alanına yaz (sipariş ver)
                # Not: MF alanı zaten dolu (tarama sırasında yazıldı)
                if self.botanik.set_adet_value(row_num, siparis_adet):
                    logger.info(f"✓ Sipariş verildi: Satır {row_num}, Adet {siparis_adet}")
                    logger.info(f"→ MF sıfırlandı, ürün Botanik'ten kaldırıldı")
                else:
                    logger.error(f"✗ Sipariş verilemedi: Satır {row_num}")

                time.sleep(0.3)  # Her sipariş arasında kısa bekleme

            logger.info("Tüm siparişler tamamlandı!")
            return True

        except Exception as e:
            logger.error(f"Sipariş verme hatası: {e}")
            return False

    def save_monthly_sales_to_csv(self, product):
        """Ürünün aylık gidiş bilgisini CSV'ye kaydet"""
        try:
            monthly_sales = product.get("monthly_sales", {})
            row_num = product.get("row", "?")

            logger.debug(f"[CSV] Satır {row_num}: save_monthly_sales_to_csv çağrıldı. monthly_sales={list(monthly_sales.keys()) if monthly_sales else 'BOŞ'}")

            if not monthly_sales:
                logger.warning(f"[CSV] Satır {row_num}: monthly_sales boş, CSV'ye yazılmıyor!")
                return  # Bilgi yoksa kaydetme

            urun_adi = product.get("urun_adi", "")

            # Sütun sırası - DİNAMİK HESAPLAMA (bugünden geriye 13 ay)
            from datetime import datetime

            today = datetime.now()
            month_columns = []

            # 12 ay önceden bugüne kadar (ters sıra: eski -> yeni)
            for i in range(12, -1, -1):  # 12, 11, 10, ..., 1, 0
                # Manuel ay hesaplama
                target_month = today.month - i
                target_year = today.year

                # Yıl geçişi düzelt
                while target_month <= 0:
                    target_month += 12
                    target_year -= 1

                # Format: "11.24"
                month_columns.append(f"{target_month:02d}.{target_year % 100:02d}")

            # Final sütun listesi
            columns = ["row", "urun_adi"] + month_columns + ["Top", "Ort"]

            # CSV dosyası yoksa başlık satırını yaz
            file_exists = self.csv_file.exists()

            with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)

                if not file_exists:
                    writer.writeheader()

                # Satırı yaz
                row_data = {
                    "row": row_num,
                    "urun_adi": urun_adi
                }
                for col in columns[2:]:  # 11.24'ten başla
                    row_data[col] = monthly_sales.get(col, "-")

                writer.writerow(row_data)

            logger.info(f"✓ [CSV] Satır {row_num}: Aylık gidiş CSV'ye YAZILDI ({self.csv_file.name})")

        except Exception as e:
            logger.error(f"Aylık gidiş CSV'ye kaydedilemedi: {e}", exc_info=True)

    def get_monthly_sales_from_csv(self, row_num):
        """CSV'den ürünün aylık gidiş bilgisini oku

        Args:
            row_num: Satır numarası

        Returns:
            dict: {"11.24": "10", "12.24": "17", ..., "Top": "183", "Ort": "14,1"}
            veya {} (bulunamazsa)
        """
        try:
            if not self.csv_file.exists():
                return {}

            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row.get("row", 0)) == row_num:
                        # row ve urun_adi hariç tüm sütunları döndür
                        result = {k: v for k, v in row.items() if k not in ["row", "urun_adi"]}
                        return result

            return {}

        except Exception as e:
            logger.error(f"Aylık gidiş CSV'den okunamadı: {e}")
            return {}

    def clear_monthly_sales_csv(self):
        """Aylık gidiş CSV dosyasını temizle (yeni tarama başlarken)"""
        try:
            if self.csv_file.exists():
                self.csv_file.unlink()
                logger.info("Aylık gidiş CSV temizlendi")
        except Exception as e:
            logger.error(f"Aylık gidiş CSV temizlenemedi: {e}")

    def save_mf_to_csv(self, product):
        """Ürünün MF bilgisini CSV'ye kaydet

        Args:
            product: Ürün dictionary'si (mf_info içermeli)
        """
        try:
            mf_info = product.get("mf_info")
            if not mf_info:
                return  # MF bilgisi yoksa kaydetme

            row_num = product.get("row")
            urun_adi = product.get("urun_adi", "")
            adet = mf_info.get("adet", 0)
            mf = mf_info.get("mf", 0)

            # Sütunlar
            columns = ["row", "urun_adi", "best_adet", "best_mf"]

            # CSV dosyası yoksa başlık satırını yaz
            file_exists = self.mf_csv_file.exists()

            with open(self.mf_csv_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)

                if not file_exists:
                    writer.writeheader()

                # Satırı yaz
                row_data = {
                    "row": row_num,
                    "urun_adi": urun_adi,
                    "best_adet": adet,
                    "best_mf": mf
                }
                writer.writerow(row_data)

            logger.debug(f"Satır {row_num}: MF bilgisi CSV'ye kaydedildi ({adet}+{mf})")

        except Exception as e:
            logger.error(f"MF CSV'ye kaydedilemedi: {e}")

    def get_mf_from_csv(self, row_num):
        """CSV'den ürünün MF bilgisini oku

        Args:
            row_num: Satır numarası

        Returns:
            dict: {"adet": 10, "mf": 2} veya None (bulunamazsa)
        """
        try:
            if not self.mf_csv_file.exists():
                return None

            with open(self.mf_csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if int(row.get("row", 0)) == row_num:
                        adet = int(row.get("best_adet", 0))
                        mf = int(row.get("best_mf", 0))
                        if adet > 0 and mf > 0:
                            return {"adet": adet, "mf": mf}
                        return None

            return None

        except Exception as e:
            logger.error(f"MF CSV'den okunamadı: {e}")
            return None

    def clear_mf_csv(self):
        """MF CSV dosyasını temizle (yeni tarama başlarken)"""
        try:
            if self.mf_csv_file.exists():
                self.mf_csv_file.unlink()
                logger.info("MF CSV temizlendi")
        except Exception as e:
            logger.error(f"MF CSV temizlenemedi: {e}")

    def save_scan_results(self):
        """Tarama sonuçlarını JSON'a kaydet (program kapansa bile veriler kaybolmasın)"""
        try:
            import json
            # Son taranan satır numarasını bul
            last_row = 0
            if self.products:
                last_row = max(p.get("row", 0) for p in self.products)

            # Sadece gerekli alanları kaydet (dosya boyutu için)
            data = {
                "products": self.products,
                "scan_time": time.time(),
                "last_scanned_row": last_row  # Yarım tarama için
            }
            with open(self.scan_results_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Tarama sonuçları kaydedildi: {len(self.products)} ürün, son satır: {last_row}")
        except Exception as e:
            logger.error(f"Tarama sonuçları kaydedilemedi: {e}")

    def load_scan_results(self):
        """Önceki tarama sonuçlarını JSON'dan yükle

        Returns:
            list: Ürün listesi veya [] (dosya yoksa)
        """
        try:
            import json
            if not self.scan_results_file.exists():
                return []

            with open(self.scan_results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            products = data.get("products", [])
            logger.info(f"Önceki tarama yüklendi: {len(products)} ürün")
            return products
        except Exception as e:
            logger.error(f"Tarama sonuçları yüklenemedi: {e}")
            return []

    def _hesapla_vade_aylari(self):
        """Her depo için ödeme tarihine kaç ay kaldığını hesapla

        İki ödeme tipi desteklenir:
        1. Vade: Ayarlardaki VADE_AY ve VADE_GUN değerlerinden hesaplanır
        2. Kredi Kartı: Hesap kesim ve ödeme günlerine göre hesaplanır

        Vade Örneği:
        - Bugün 15 Mart, Vade: 1 ay sonra 7'si -> Ödeme: 7 Nisan -> ~23 gün -> ~0.77 ay

        Kredi Kartı Örneği:
        - Bugün 10 Aralık, Kesim: 28, Ödeme: 7
        - Bugün <= 28, yani bu ayın kesimi geçerli
        - Ödeme: Sonraki ayın 7'si (7 Ocak) -> 28 gün -> ~0.93 ay

        - Bugün 29 Aralık, Kesim: 28, Ödeme: 7
        - Bugün > 28, yani sonraki ayın kesimi geçerli
        - Ödeme: 2 ay sonraki 7'si (7 Şubat) -> ~40 gün -> ~1.33 ay

        Returns:
            dict: {"alliance": float, "selcuk": float, ...} - ay cinsinden vade
        """
        from datetime import datetime
        import calendar

        bugun = datetime.now()
        depolar = ["alliance", "selcuk", "yusufpasa", "iskoop", "bursa", "farmazon", "sancak"]
        vade_aylari = {}

        for depo in depolar:
            try:
                odeme_tipi = os.getenv(f"{depo.upper()}_ODEME_TIPI", "vade")

                if odeme_tipi == "kredi_karti":
                    # KREDİ KARTI HESABI
                    kk_kesim = int(os.getenv(f"{depo.upper()}_KK_KESIM", "28"))
                    kk_odeme = int(os.getenv(f"{depo.upper()}_KK_ODEME", "7"))

                    if bugun.day <= kk_kesim:
                        # Bu ayın kesimi henüz geçmedi, sonraki ayın ödeme günü
                        hedef_ay = bugun.month + 1
                        hedef_yil = bugun.year
                    else:
                        # Bu ayın kesimi geçti, 2 ay sonraki ödeme günü
                        hedef_ay = bugun.month + 2
                        hedef_yil = bugun.year

                    # Ay taşmasını kontrol et
                    while hedef_ay > 12:
                        hedef_ay -= 12
                        hedef_yil += 1

                    # Hedef ayın son gününü bul
                    son_gun = calendar.monthrange(hedef_yil, hedef_ay)[1]
                    odeme_gun = min(kk_odeme, son_gun)

                    odeme_tarihi = datetime(hedef_yil, hedef_ay, odeme_gun)
                    gun_farki = (odeme_tarihi - bugun).days
                    ay_farki = gun_farki / 30.0

                    vade_aylari[depo] = round(ay_farki, 2)
                    logger.debug(f"[VADE-KK] {depo}: Kesim:{kk_kesim} Ödeme:{kk_odeme} -> {odeme_tarihi.strftime('%d.%m.%Y')} -> {gun_farki} gün -> {ay_farki:.2f} ay")

                else:
                    # NORMAL VADE HESABI
                    vade_ay = int(os.getenv(f"{depo.upper()}_VADE_AY", "1"))
                    vade_gun = int(os.getenv(f"{depo.upper()}_VADE_GUN", "15"))

                    # Ödeme tarihi: Bu aydan vade_ay sonraki ayın vade_gun'ü
                    hedef_ay = bugun.month + vade_ay
                    hedef_yil = bugun.year

                    # Ay taşmasını kontrol et
                    while hedef_ay > 12:
                        hedef_ay -= 12
                        hedef_yil += 1

                    # Hedef ayın son gününü bul (28, 29, 30, 31)
                    son_gun = calendar.monthrange(hedef_yil, hedef_ay)[1]
                    odeme_gun = min(vade_gun, son_gun)

                    odeme_tarihi = datetime(hedef_yil, hedef_ay, odeme_gun)
                    gun_farki = (odeme_tarihi - bugun).days
                    ay_farki = gun_farki / 30.0

                    vade_aylari[depo] = round(ay_farki, 2)
                    logger.debug(f"[VADE] {depo}: {vade_ay} ay sonra {vade_gun}'i -> {odeme_tarihi.strftime('%d.%m.%Y')} -> {gun_farki} gün -> {ay_farki:.2f} ay")

            except Exception as e:
                logger.warning(f"[VADE] {depo} vade hesaplama hatası: {e}, varsayılan 1 ay kullanılıyor")
                vade_aylari[depo] = 1.0

        return vade_aylari

    def hesapla_efektif_maliyet(self, birim_fiyat, min_adet, mf, vade_ay, aylik_satis, mevcut_stok=0):
        """Bir alım seçeneği için efektif birim maliyeti hesapla

        Formül (mevcut stok dahil):
        1. Toplam adet = min_adet + mf (bedava)
        2. Toplam ödeme = birim_fiyat × min_adet
        3. Mevcut stok bitme süresi = mevcut_stok / aylık_satış (ay)
        4. Yeni parti satış başlangıcı = mevcut_stok_bitme
        5. Yeni parti satış sonu = başlangıç + toplam_adet / aylık_satış
        6. Ortalama satış tarihi = (başlangıç + son) / 2
        7. Net finansal süre = ortalama_satış - vade (ödeme sonrası para bağlı)
        8. Finansal maliyet = toplam_ödeme × net_süre × aylık_faiz
        9. Efektif toplam = toplam_ödeme + finansal_maliyet
        10. Efektif birim = efektif_toplam / toplam_adet

        Args:
            birim_fiyat: KDV dahil birim fiyat (TL)
            min_adet: Minimum alım adedi
            mf: Mal fazlası (bedava adet)
            vade_ay: Ödeme vadesi (ay cinsinden)
            aylik_satis: Aylık ortalama satış adedi
            mevcut_stok: Eldeki mevcut stok (varsayılan 0)

        Returns:
            dict: {"efektif_birim": float, "toplam_adet": int, "finansal_maliyet": float, ...}
        """
        try:
            if aylik_satis <= 0:
                aylik_satis = 1  # Sıfıra bölme önlemi

            toplam_adet = min_adet + mf
            # birim_fiyat MF'li seçeneklerde zaten indirimli (toplam_odeme/toplam_adet)
            # Bu yüzden toplam ödeme = birim_fiyat × toplam_adet
            toplam_odeme = birim_fiyat * toplam_adet

            # Mevcut stok bitme süresi (ay)
            # Negatif stok varsa 0 kabul et (eksik stok = hemen satılır)
            mevcut_stok_safe = max(mevcut_stok, 0)
            mevcut_stok_bitme = mevcut_stok_safe / aylik_satis

            # Yeni parti satış tarihleri
            satis_baslangic = mevcut_stok_bitme  # Mevcut stok bittikten sonra başlar
            satis_son = satis_baslangic + (toplam_adet / aylik_satis)
            ortalama_satis = (satis_baslangic + satis_son) / 2

            # Net finansal süre (para ödeme sonrası ne kadar bağlı)
            # Ödeme: vade_ay sonra, Para geri dönüşü: ortalama_satis sonra
            net_sure = ortalama_satis - vade_ay

            # Finansal maliyet - BİLEŞİK FAİZ
            # (1 + r)^n - 1 formülü hem pozitif hem negatif net_sure için çalışır
            # Pozitif net_sure: maliyet (para bağlı kaldığı için)
            # Negatif net_sure: avantaj (parayı ödemeden önce kazandık)
            finansal_maliyet = toplam_odeme * ((1 + self.aylik_faiz) ** net_sure - 1)

            # Efektif toplam ve birim
            efektif_toplam = toplam_odeme + finansal_maliyet
            efektif_birim = efektif_toplam / toplam_adet

            result = {
                "efektif_birim": round(efektif_birim, 2),
                "toplam_adet": toplam_adet,
                "toplam_odeme": round(toplam_odeme, 2),
                "finansal_maliyet": round(finansal_maliyet, 2),
                "mevcut_stok_bitme_ay": round(mevcut_stok_bitme, 1),
                "satis_baslangic_ay": round(satis_baslangic, 1),
                "satis_son_ay": round(satis_son, 1),
                "ortalama_satis_ay": round(ortalama_satis, 1),
                "net_sure_ay": round(net_sure, 1)
            }
            logger.info(f"[HESAP-BİLEŞİK] Fiyat:{birim_fiyat:.2f} Vade:{vade_ay}ay OrtSatış:{ortalama_satis:.2f}ay Net:{net_sure:.2f}ay FinMaliyet:{finansal_maliyet:.2f} Efektif:{efektif_birim:.2f}")
            return result
        except Exception as e:
            logger.error(f"Efektif maliyet hesaplama hatası: {e}")
            return None

    def bul_en_karli_secenek(self, product):
        """Bir ürün için tüm depolardaki tüm seçenekleri karşılaştır ve en karlısını bul

        Args:
            product: Ürün bilgileri (depo durumları dahil)

        Returns:
            dict: {
                "depo": str,  # En karlı depo key'i
                "secenek": dict,  # En karlı seçenek bilgisi
                "efektif_birim": float,  # En düşük efektif birim maliyet
                "tum_secenekler": list  # Tüm seçenekler (karşılaştırma için)
            }
        """
        try:
            # Aylık satış bilgisini al
            aylik_satis = product.get("ort", 0)
            if aylik_satis <= 0:
                # monthly_sales'den Ort değerini dene
                monthly_sales = product.get("monthly_sales", {})
                ort_str = monthly_sales.get("Ort", "0")
                try:
                    aylik_satis = float(str(ort_str).replace(",", "."))
                except:
                    aylik_satis = 1

            # Mevcut stok bilgisini al
            mevcut_stok = product.get("stok", 0)
            if mevcut_stok is None:
                mevcut_stok = 0
            # String ise int'e çevir
            try:
                mevcut_stok = int(float(str(mevcut_stok).replace(",", ".")))
            except:
                mevcut_stok = 0
            logger.info(f"[EFEKTİF] Stok: {mevcut_stok}, Aylık satış: {aylik_satis}, Faiz: {self.aylik_faiz}")

            tum_secenekler = []
            available_depolar = self.get_available_depolar()

            # Depo vade bilgilerini oku (ay cinsinden)
            depo_vadeleri = self._hesapla_vade_aylari()

            for depo_key in available_depolar:
                durum = product.get(f"{depo_key}_durum", {})
                if not durum or not durum.get("stok_var"):
                    continue

                satis_kosullari = durum.get("satis_kosullari", [])
                vade_ay = depo_vadeleri.get(depo_key, 1)  # Ay cinsinden vade

                # Farmazon için MF yok, sadece birim fiyat + kargo
                # Optimum adet: Kargo avantajı vs finansal maliyet dengesini bul
                if depo_key == "farmazon":
                    fiyat = durum.get("fiyat")
                    if fiyat and fiyat > 0:
                        kargo_toplam = float(os.getenv("FARMAZON_KARGO", "140"))

                        # Minimum sipariş: 1 adet
                        # Maksimum sipariş: Ayarlardan (varsayılan 6 ay)
                        min_siparis = 1
                        farmazon_max_ay = int(os.getenv("FARMAZON_MAX_AY", "6"))
                        max_siparis = max(1, int(aylik_satis * farmazon_max_ay))

                        # Optimum adedi bul: en düşük efektif fiyatı veren
                        en_iyi_adet = min_siparis
                        en_iyi_efektif = None
                        en_iyi_sonuc = None

                        for test_adet in range(min_siparis, max_siparis + 1):
                            birim_kargo = kargo_toplam / test_adet
                            fiyat_kargo_dahil = fiyat + birim_kargo

                            efektif = self.hesapla_efektif_maliyet(
                                birim_fiyat=fiyat_kargo_dahil,
                                min_adet=test_adet,
                                mf=0,
                                vade_ay=vade_ay,
                                aylik_satis=aylik_satis,
                                mevcut_stok=mevcut_stok
                            )

                            if efektif:
                                efektif_birim = efektif.get("efektif_birim", float('inf'))
                                if en_iyi_efektif is None or efektif_birim < en_iyi_efektif:
                                    en_iyi_efektif = efektif_birim
                                    en_iyi_adet = test_adet
                                    en_iyi_sonuc = efektif
                                    en_iyi_birim_kargo = birim_kargo
                                    en_iyi_fiyat_kargo_dahil = fiyat_kargo_dahil

                        if en_iyi_sonuc:
                            logger.info(f"[FARMAZON-OPTİMUM] Fiyat:{fiyat:.2f} + Kargo:{en_iyi_birim_kargo:.2f} ({kargo_toplam}/{en_iyi_adet} adet) = {en_iyi_fiyat_kargo_dahil:.2f} -> Efektif:{en_iyi_efektif:.2f}")

                            tum_secenekler.append({
                                "depo": depo_key,
                                "sart": str(en_iyi_adet),  # Optimum adet
                                "birim_fiyat": fiyat,  # Orijinal fiyat (gösterim için)
                                "birim_fiyat_kargo_dahil": en_iyi_fiyat_kargo_dahil,
                                "birim_kargo": round(en_iyi_birim_kargo, 2),
                                "min_adet": en_iyi_adet,
                                "mf": 0,
                                "vade_ay": vade_ay,
                                "optimum_adet": en_iyi_adet,
                                **en_iyi_sonuc
                            })
                    continue

                # Diğer depolar için satış koşullarını değerlendir
                if not satis_kosullari:
                    # Satış koşulları yoksa, durum'daki fiyatı kullan
                    fiyat = durum.get("fiyat")
                    if fiyat and fiyat > 0:
                        efektif = self.hesapla_efektif_maliyet(
                            birim_fiyat=fiyat,
                            min_adet=1,
                            mf=0,
                            vade_ay=vade_ay,
                            aylik_satis=aylik_satis,
                            mevcut_stok=mevcut_stok
                        )
                        if efektif:
                            tum_secenekler.append({
                                "depo": depo_key,
                                "sart": "1",
                                "birim_fiyat": fiyat,
                                "min_adet": 1,
                                "mf": 0,
                                "vade_ay": vade_ay,
                                **efektif
                            })
                else:
                    for kosul in satis_kosullari:
                        birim_fiyat = kosul.get("birim_fiyat", 0)
                        min_adet = kosul.get("min_adet", 1)
                        mf = kosul.get("mf", 0)
                        # sart yoksa min_adet ve mf'den oluştur (Selçuk gibi depolar için)
                        sart = kosul.get("sart") or (f"{min_adet}+{mf}" if mf > 0 else "1")

                        if birim_fiyat <= 0:
                            continue

                        # İskoop ve Bursa KDV hariç fiyat veriyor, hesaplamada KDV dahil olmalı
                        # Diğer depolar (selcuk, alliance, yusufpasa, sancak) zaten KDV dahil veriyor
                        fiyat_kdv_dahil = birim_fiyat
                        if depo_key in ("iskoop", "bursa"):
                            kdv_orani = kosul.get("kdv_orani", 10)
                            fiyat_kdv_dahil = birim_fiyat * (1 + kdv_orani / 100)

                        efektif = self.hesapla_efektif_maliyet(
                            birim_fiyat=fiyat_kdv_dahil,
                            min_adet=min_adet,
                            mf=mf,
                            vade_ay=vade_ay,
                            aylik_satis=aylik_satis,
                            mevcut_stok=mevcut_stok
                        )
                        if efektif:
                            tum_secenekler.append({
                                "depo": depo_key,
                                "sart": sart,
                                "birim_fiyat": round(fiyat_kdv_dahil, 2),  # KDV dahil fiyat
                                "min_adet": min_adet,
                                "mf": mf,
                                "vade_ay": vade_ay,
                                **efektif
                            })

            if not tum_secenekler:
                return None

            # En düşük efektif birim maliyeti bul
            tum_secenekler.sort(key=lambda x: x["efektif_birim"])
            en_karli = tum_secenekler[0]

            # Eşit veya çok yakın olanları da işaretle (%1 tolerans)
            tolerans = 0.01
            en_karliler = []
            for s in tum_secenekler:
                fark = abs(s["efektif_birim"] - en_karli["efektif_birim"]) / en_karli["efektif_birim"]
                if fark <= tolerans:
                    en_karliler.append(s)

            return {
                "en_karli": en_karli,
                "en_karliler": en_karliler,  # Eşit olanlar dahil
                "tum_secenekler": tum_secenekler
            }

        except Exception as e:
            logger.error(f"En karlı seçenek bulma hatası: {e}")
            return None

    def hesapla_en_karli_fiyat_basit(self, product):
        """Barkod yapıştır modu için basitleştirilmiş efektif fiyat hesaplama

        Stok ve aylık satış bilgisi olmadan, sadece vade farkına göre karşılaştırma yapar.
        Efektif fiyat = birim_fiyat * (1 + faiz)^(-vade)  (bugünkü değer)

        Bu formül: "Bu fiyatı vade sonunda ödeyeceğim, bugünkü değeri nedir?" sorusunu yanıtlar.
        Uzun vadeli ödemeler daha avantajlıdır (bugünkü değeri düşük).

        NOT: Bu fonksiyon normal tarama efektif hesabını BOZMAZ.
        Sadece barkod yapıştır modunda stok/ort bilgisi olmadığında kullanılır.

        Args:
            product: Ürün bilgileri (depo durumları dahil)

        Returns:
            dict: en_karli, en_karliler, tum_secenekler
        """
        try:
            tum_secenekler = []

            # Depo vade bilgilerini oku (ay cinsinden)
            depo_vadeleri = self._hesapla_vade_aylari()

            # Tüm depoları kontrol et
            all_depolar = ["alliance", "selcuk", "yusufpasa", "iskoop", "bursa", "farmazon", "sancak"]

            for depo_key in all_depolar:
                durum = product.get(f"{depo_key}_durum", {})
                if not durum or not durum.get("stok_var"):
                    continue

                satis_kosullari = durum.get("satis_kosullari", [])
                vade_ay = depo_vadeleri.get(depo_key, 1)

                # Vade faktörü: uzun vade = düşük bugünkü değer
                vade_faktoru = (1 + self.aylik_faiz) ** (-vade_ay)

                def hesapla_basit_efektif(birim_fiyat, min_adet, mf, sart, kdv_dahil=True):
                    """Basit efektif hesapla"""
                    if birim_fiyat <= 0:
                        return None

                    fiyat_kdv_dahil = birim_fiyat
                    if not kdv_dahil and depo_key in ("iskoop", "bursa"):
                        kdv_orani = 10  # Varsayılan KDV
                        fiyat_kdv_dahil = birim_fiyat * (1 + kdv_orani / 100)

                    # Bugünkü değer = fiyat * (1+r)^(-vade)
                    efektif_birim = fiyat_kdv_dahil * vade_faktoru

                    return {
                        "depo": depo_key,
                        "sart": sart,
                        "birim_fiyat": round(fiyat_kdv_dahil, 2),
                        "min_adet": min_adet,
                        "mf": mf,
                        "vade_ay": vade_ay,
                        "efektif_birim": round(efektif_birim, 2),
                        "vade_faktoru": round(vade_faktoru, 4)
                    }

                # Satış koşulları varsa
                if satis_kosullari:
                    for kosul in satis_kosullari:
                        birim_fiyat = kosul.get("birim_fiyat", 0)
                        min_adet = kosul.get("min_adet", 1)
                        mf = kosul.get("mf", 0)
                        sart = kosul.get("sart") or (f"{min_adet}+{mf}" if mf > 0 else "1")

                        # İskoop/Bursa KDV hariç
                        kdv_dahil = depo_key not in ("iskoop", "bursa")

                        result = hesapla_basit_efektif(birim_fiyat, min_adet, mf, sart, kdv_dahil)
                        if result:
                            tum_secenekler.append(result)
                else:
                    # Satış koşulları yok, durum'daki fiyatı kullan
                    fiyat = durum.get("fiyat", 0)
                    if fiyat and fiyat > 0:
                        # Farmazon ve diğerleri genelde KDV dahil
                        result = hesapla_basit_efektif(fiyat, 1, 0, "1", True)
                        if result:
                            tum_secenekler.append(result)

            if not tum_secenekler:
                return None

            # En düşük efektif birim maliyeti bul
            tum_secenekler.sort(key=lambda x: x["efektif_birim"])
            en_karli = tum_secenekler[0]

            # Eşit veya çok yakın olanları da işaretle (%1 tolerans)
            tolerans = 0.01
            en_karliler = []
            for s in tum_secenekler:
                if en_karli["efektif_birim"] > 0:
                    fark = abs(s["efektif_birim"] - en_karli["efektif_birim"]) / en_karli["efektif_birim"]
                    if fark <= tolerans:
                        en_karliler.append(s)

            logger.debug(f"[BASIT-EFEKTİF] {len(tum_secenekler)} seçenek, en karlı: {en_karli['depo']} {en_karli['efektif_birim']} TL")

            return {
                "en_karli": en_karli,
                "en_karliler": en_karliler,
                "tum_secenekler": tum_secenekler
            }

        except Exception as e:
            logger.error(f"Basit efektif fiyat hesaplama hatası: {e}")
            return None

    # ========== HIZLI TARAMA MODU ==========

    def run_fast_scan(self):
        """Hızlı tarama modu - 2 aşamalı:
        1. Depolar açılır + Botanik'ten oku + Depolarda tara + GUI'ye yaz (eş zamanlı)
        2. Sonuçları toplu olarak Botanik'e yaz
        """
        try:
            self.products = []
            logger.info("=" * 60)
            logger.info("HIZLI TARAMA MODU BAŞLATILIYOR")
            logger.info("=" * 60)

            # 1. Botanik EOS'a bağlan
            if self.gui:
                self.gui.update_status("Botanik EOS'a bağlanılıyor...")

            if not self.botanik.connect():
                logger.error("Botanik EOS'a bağlanılamadı!")
                if self.gui:
                    from tkinter import messagebox
                    self.gui.root.after(0, lambda: messagebox.showerror(
                        "Botanik EOS Bulunamadı",
                        "Botanik EOS programı açık değil!\n\n"
                        "Lütfen Botanik EOS'u açın ve tekrar deneyin."
                    ))
                return False

            # 2. DEPOLARI ÖNCE AÇ
            if self.gui:
                self.gui.update_status("Depolar açılıyor...")
            logger.info("\n" + "=" * 50)
            logger.info("DEPOLAR AÇILIYOR...")
            logger.info("=" * 50)

            credentials = {
                "alliance": {
                    "eczane_kodu": os.getenv("ALLIANCE_ECZANE_KODU", ""),
                    "username": os.getenv("ALLIANCE_USERNAME", ""),
                    "password": os.getenv("ALLIANCE_PASSWORD", "")
                },
                "selcuk": {
                    "hesap_kodu": os.getenv("SELCUK_HESAP_KODU", ""),
                    "username": os.getenv("SELCUK_USERNAME", ""),
                    "password": os.getenv("SELCUK_PASSWORD", "")
                },
                "yusufpasa": {
                    "eczane_kodu": os.getenv("YUSUFPASA_ECZANE_KODU", ""),
                    "username": os.getenv("YUSUFPASA_USERNAME", ""),
                    "password": os.getenv("YUSUFPASA_PASSWORD", "")
                },
                "iskoop": {
                    "username": os.getenv("ISKOOP_USERNAME", ""),
                    "password": os.getenv("ISKOOP_PASSWORD", "")
                },
                "bursa": {
                    "username": os.getenv("BURSA_USERNAME", ""),
                    "password": os.getenv("BURSA_PASSWORD", "")
                },
                "farmazon": {
                    "username": os.getenv("FARMAZON_USERNAME", ""),
                    "password": os.getenv("FARMAZON_PASSWORD", "")
                },
                "sancak": {
                    "username": os.getenv("SANCAK_USERNAME", ""),
                    "password": os.getenv("SANCAK_PASSWORD", "")
                }
            }

            # Depoları başlat (arka planda açılacak)
            self._init_depolar(credentials)

            # Botanik tablosunu hazırla
            if self.gui:
                self.gui.update_status("Botanik tablosu hazırlanıyor...")
            self.botanik.prepare_table_for_scan()

            # ========== AŞAMA 1: BOTANİK OKU + DEPO TARA + GUI YAZ (PARALEL) ==========
            if self.gui:
                self.gui.update_status("AŞAMA 1/2: Botanik okunuyor + Depolar taranıyor...")
            logger.info("\n" + "=" * 50)
            logger.info("AŞAMA 1: Botanik oku + Depo tara PARALEL + GUI yaz")
            logger.info("=" * 50)

            # Depo araması için executor (paralel çalışacak)
            from concurrent.futures import ThreadPoolExecutor
            depo_executor = ThreadPoolExecutor(max_workers=1)

            # Callback: Barkod alınır alınmaz depo aramasını başlat
            def start_depo_search(barcode):
                """Depo aramasını arka planda başlat, Future döner"""
                def search_all_depots():
                    results = {}
                    target_depolar = self.active_depolar or self.depolar

                    # Tüm depoları paralel sorgula
                    with ThreadPoolExecutor(max_workers=len(target_depolar)) as executor:
                        futures = {}
                        for depo_key, depo in target_depolar.items():
                            futures[executor.submit(depo.search_product, barcode)] = depo_key

                        for future in as_completed(futures):
                            depo_key = futures[future]
                            try:
                                result = future.result(timeout=8)
                                results[f"{depo_key}_durum"] = result
                            except Exception as e:
                                results[f"{depo_key}_durum"] = {
                                    "stok_var": False,
                                    "mesaj": f"Hata: {str(e)[:20]}",
                                    "fiyat": 0,
                                    "sart": "",
                                    "satis_kosullari": []
                                }
                    return results

                return depo_executor.submit(search_all_depots)

            # Callback: Tüm veriler okunduğunda GUI'ye yaz ve Botanik'e kaydet
            def on_product_read(product_data, idx, total):
                # En karlı seçeneği hesapla (depo sonuçları product_data'da)
                en_karli_sonuc = self.bul_en_karli_secenek(product_data)
                if en_karli_sonuc:
                    product_data["en_karli_sonuc"] = en_karli_sonuc

                # Efektif bazlı açıklama metnini oluştur (Al(10+2) Se(5+1) Ara(Ys) formatı)
                aciklama_ozeti = self._build_aciklama_efektif(product_data)
                product_data["aciklama_ozeti"] = aciklama_ozeti

                # CSV'lere kaydet
                self.save_monthly_sales_to_csv(product_data)
                mf_enabled = os.getenv("MF_ENABLED", "true").lower() == "true"
                if mf_enabled:
                    self.save_mf_to_csv(product_data)

                # Controller products listesine ekle
                self.products.append(product_data)

                # GUI'ye yaz (depo sonuçlarıyla birlikte)
                if self.gui:
                    self.gui.root.after(0, lambda p=product_data.copy(), i=idx, t=total:
                        self.gui.show_scanned_product_with_depo(p, i, t))

                # Botanik'e HEMEN yaz (MF/İhtiyaç + Açıklama)
                row = product_data.get("row")
                if row:
                    # 1. MF/İhtiyaç alanına sipariş adedini yaz
                    siparis_adet = product_data.get("siparis_adet", 0)
                    if siparis_adet > 0:
                        try:
                            self.botanik.set_mf_value(row, siparis_adet)
                            logger.info(f"✓ Satır {row}: MF/İht yazıldı: {siparis_adet}")
                        except Exception as e:
                            logger.error(f"Satır {row}: MF/İht yazma hatası: {e}")

                    # 2. Açıklamayı yaz (kullanıcının manuel notunu koru)
                    try:
                        # Mevcut açıklamayı oku
                        mevcut_aciklama = self.botanik.get_aciklama_value(row)
                        # Kullanıcının manuel notunu ayır
                        user_aciklama = self._extract_user_aciklama(mevcut_aciklama)
                        # Birleştir
                        full_aciklama = self._build_full_aciklama(aciklama_ozeti, user_aciklama)
                        product_data["aciklama_ozeti"] = full_aciklama

                        self.botanik.set_aciklama_value(row, full_aciklama, skip_scroll=True)
                        logger.info(f"✓ Satır {row}: Açıklama yazıldı: {full_aciklama}")
                    except Exception as e:
                        logger.error(f"Satır {row}: Açıklama yazma hatası: {e}")

            # Botanik'ten oku (barkod alınca depo araması paralel başlar)
            all_products = self.botanik.get_all_products_data_only(
                on_product_read=on_product_read,
                start_depo_search=start_depo_search
            )

            # Executor'u kapat
            depo_executor.shutdown(wait=False)

            if not all_products:
                logger.warning("Hiç ürün bulunamadı!")
                if self.gui:
                    self.gui.update_status("Ürün bulunamadı")
                return False

            logger.info(f"Toplam {len(all_products)} ürün işlendi")

            # JSON'a kaydet
            self.save_scan_results()

            # Tamamlandı
            if self.gui:
                self.gui.update_status(f"HIZLI TARAMA TAMAMLANDI - {len(self.products)} ürün")
            logger.info("\n" + "=" * 60)
            logger.info("HIZLI TARAMA TAMAMLANDI!")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"Hızlı tarama hatası: {e}")
            if self.gui:
                self.gui.update_status(f"Hata: {e}")
            return False

    def run_fast_scan_for_rows(self, rows_to_scan, botanik_total=None):
        """Sadece belirli satırları tara - BOTANİK'E YAZMA YOK

        Bu fonksiyon sync işlemi sırasında kullanılır.
        Sadece verilen satır numaraları taranır.
        Botanik'e hiçbir şey yazılmaz (MF, açıklama vs.)

        Args:
            rows_to_scan: Taranacak satır numaraları listesi [36, 37, 38, 39]
            botanik_total: Botanik'teki toplam satır sayısı (status için)

        Returns:
            bool: Başarılı ise True
        """
        try:
            if not rows_to_scan:
                logger.info("Taranacak satır yok")
                return True

            logger.info("=" * 60)
            logger.info(f"SEÇİCİ TARAMA: Sadece {len(rows_to_scan)} satır")
            logger.info(f"Satırlar: {sorted(rows_to_scan)}")
            logger.info("=" * 60)

            # 1. Botanik EOS'a bağlan
            if not self.botanik.connect():
                logger.error("Botanik EOS'a bağlanılamadı!")
                return False

            # 2. Depolar açık mı kontrol et (driver'lar geçerli mi?)
            def are_depots_valid():
                """Depoların gerçekten açık ve çalışır durumda olup olmadığını kontrol et"""
                target = self.active_depolar or self.depolar
                if not target:
                    return False
                # En az bir deponun driver'ı geçerli mi?
                for depo_key, depo in target.items():
                    try:
                        if hasattr(depo, 'driver') and depo.driver is not None:
                            # Driver'ın gerçekten çalışıp çalışmadığını test et
                            _ = depo.driver.current_url
                            return True  # En az bir çalışan depo var
                    except Exception:
                        continue
                return False

            if not are_depots_valid():
                logger.info("Depolar kapalı veya geçersiz, yeniden açılıyor...")
                if self.gui:
                    self.gui.update_status("Depolar açılıyor...")

                credentials = {
                    "alliance": {
                        "eczane_kodu": os.getenv("ALLIANCE_ECZANE_KODU", ""),
                        "username": os.getenv("ALLIANCE_USERNAME", ""),
                        "password": os.getenv("ALLIANCE_PASSWORD", "")
                    },
                    "selcuk": {
                        "hesap_kodu": os.getenv("SELCUK_HESAP_KODU", ""),
                        "username": os.getenv("SELCUK_USERNAME", ""),
                        "password": os.getenv("SELCUK_PASSWORD", "")
                    },
                    "yusufpasa": {
                        "eczane_kodu": os.getenv("YUSUFPASA_ECZANE_KODU", ""),
                        "username": os.getenv("YUSUFPASA_USERNAME", ""),
                        "password": os.getenv("YUSUFPASA_PASSWORD", "")
                    },
                    "iskoop": {
                        "username": os.getenv("ISKOOP_USERNAME", ""),
                        "password": os.getenv("ISKOOP_PASSWORD", "")
                    },
                    "bursa": {
                        "username": os.getenv("BURSA_USERNAME", ""),
                        "password": os.getenv("BURSA_PASSWORD", "")
                    },
                    "farmazon": {
                        "username": os.getenv("FARMAZON_USERNAME", ""),
                        "password": os.getenv("FARMAZON_PASSWORD", "")
                    },
                    "sancak": {
                        "username": os.getenv("SANCAK_USERNAME", ""),
                        "password": os.getenv("SANCAK_PASSWORD", "")
                    }
                }
                self._init_depolar(credentials)

            # Depo araması için fonksiyon
            def search_all_depots(barcode):
                """Tüm depolarda barkod ara"""
                results = {}
                target_depolar = self.active_depolar or self.depolar

                if not target_depolar:
                    return results

                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=len(target_depolar)) as executor:
                    futures = {}
                    for depo_key, depo in target_depolar.items():
                        futures[executor.submit(depo.search_product, barcode)] = depo_key

                    for future in as_completed(futures):
                        depo_key = futures[future]
                        try:
                            result = future.result(timeout=8)
                            results[f"{depo_key}_durum"] = result
                        except Exception as e:
                            results[f"{depo_key}_durum"] = {
                                "stok_var": False,
                                "mesaj": f"Hata: {str(e)[:20]}",
                                "fiyat": 0,
                                "sart": "",
                                "satis_kosullari": []
                            }
                return results

            # Satırları sırala (küçükten büyüğe)
            rows_to_scan = sorted(rows_to_scan)
            taranan_count = 0
            total = len(rows_to_scan)

            # botanik_total bilinmiyorsa hesapla
            if botanik_total is None:
                botanik_total = max(rows_to_scan) if rows_to_scan else total

            for idx, row_num in enumerate(rows_to_scan, 1):
                try:
                    if self.gui:
                        # Status: "23/34 - Taranıyor..." formatında göster
                        self.gui.update_status(f"{row_num}/{botanik_total} - Taranıyor...")

                    logger.info(f"[{idx}/{total}] Satır {row_num} taranıyor...")

                    # 1. Ürün verilerini oku
                    product_data = self.botanik.get_product_data(row_num)
                    if not product_data:
                        logger.warning(f"Satır {row_num} verileri okunamadı")
                        continue

                    # 2. Barkod al
                    barcode = self.botanik.click_depo_personel_cell(row_num)
                    product_data["barkod"] = barcode

                    if not barcode:
                        logger.warning(f"Satır {row_num}: Barkod alınamadı")
                        continue

                    # 3. Depolarda ara
                    depo_results = search_all_depots(barcode)
                    product_data.update(depo_results)

                    # 4. En karlı seçeneği hesapla
                    en_karli_sonuc = self.bul_en_karli_secenek(product_data)
                    if en_karli_sonuc:
                        product_data["en_karli_sonuc"] = en_karli_sonuc

                    # 5. Açıklama metnini oluştur (sadece GUI için)
                    aciklama_ozeti = self._build_aciklama_efektif(product_data)
                    product_data["aciklama_ozeti"] = aciklama_ozeti

                    # 6. CSV'lere kaydet
                    self.save_monthly_sales_to_csv(product_data)
                    mf_enabled = os.getenv("MF_ENABLED", "true").lower() == "true"
                    if mf_enabled:
                        self.save_mf_to_csv(product_data)

                    # 7. Controller products listesine ekle
                    self.products.append(product_data)

                    # 8. GUI'ye yaz (satır numarası Botanik ile aynı!)
                    if self.gui:
                        self.gui.root.after(0, lambda p=product_data.copy():
                            self.gui.show_scanned_product_with_depo(p, p.get("row"), total))

                    # BOTANİK'E YAZMA YOK - sadece okuma

                    taranan_count += 1
                    logger.info(f"  ✓ Satır {row_num}: {product_data.get('urun_adi')}")

                except Exception as e:
                    logger.error(f"Satır {row_num} taranırken hata: {e}")
                    continue

            # JSON'a kaydet
            self.save_scan_results()

            logger.info(f"✓ Seçici tarama: {taranan_count}/{total} ürün eklendi")

            if self.gui:
                self.gui.update_status(f"✓ {taranan_count} yeni ürün eklendi")

            return taranan_count > 0

        except Exception as e:
            logger.error(f"Seçici tarama hatası: {e}")
            if self.gui:
                self.gui.update_status(f"Hata: {e}")
            return False
