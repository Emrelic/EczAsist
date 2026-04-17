"""
Depo Manager - Merkezi depo yönetim sınıfı
Paralel arama + kalıcı oturum desteği
"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .alliance import AllianceDepo
from .selcuk import SelcukDepo
from .sancak import SancakDepo
from .iskoop import IskoopDepo
from .farmazon import FarmazonDepo

logger = logging.getLogger(__name__)

# Depo sınıfları ve login argüman yapıları
DEPO_CLASSES = {
    "selcuk": {
        "class": SelcukDepo,
        "login_args": ["hesap_kodu", "username", "password"]
    },
    "alliance": {
        "class": AllianceDepo,
        "login_args": ["eczane_kodu", "username", "password"]
    },
    "sancak": {
        "class": SancakDepo,
        "login_args": ["username", "password"]
    },
    "iskoop": {
        "class": IskoopDepo,
        "login_args": ["username", "password"]
    },
    "farmazon": {
        "class": FarmazonDepo,
        "login_args": ["username", "password"]
    }
}


class DepoManager:
    """Merkezi depo yönetim sınıfı

    Tek Chrome instance üzerinde her depo ayrı sekmede çalışır.
    Oturumlar kalıcıdır - ilk aramayla açılır, close_all() ile kapanır.
    """

    def __init__(self, ayarlar_getter):
        """
        Args:
            ayarlar_getter: callable - medula_settings'den depo_ayarlari dict'ini döndürür
        """
        self._ayarlar_getter = ayarlar_getter
        self._depolar = {}           # {key: depo_instance}
        self._aktif_depolar = {}     # {key: depo_instance} (login olmuş)
        self._shared_driver = None   # Paylaşılan Chrome driver
        self._initialized = False
        self._lock = threading.Lock()

    def _get_ayarlar(self):
        """Depo ayarlarını al"""
        try:
            return self._ayarlar_getter()
        except Exception as e:
            logger.error(f"Depo ayarları alınamadı: {e}")
            return {}

    def _get_depo_siralama(self):
        """Depo sıralamasını al"""
        ayarlar = self._get_ayarlar()
        return ayarlar.get("depo_siralama", ["selcuk", "alliance", "sancak", "iskoop", "farmazon"])

    def _get_enabled_depolar(self):
        """Aktif (enabled) depoları döndür"""
        ayarlar = self._get_ayarlar()
        siralama = self._get_depo_siralama()

        enabled = []
        for key in siralama:
            depo_ayar = ayarlar.get(key, {})
            if depo_ayar.get("enabled", False):
                enabled.append(key)

        return enabled

    def init_all(self, progress_callback=None):
        """Tüm aktif depoları başlat ve login ol

        Args:
            progress_callback: callable(mesaj: str) - İlerleme mesajı gönderir

        Returns:
            dict: {depo_key: bool} - Her depo için login başarı durumu
        """
        ayarlar = self._get_ayarlar()
        enabled_depolar = self._get_enabled_depolar()

        if not enabled_depolar:
            logger.warning("Hiç aktif depo bulunamadı!")
            return {}

        results = {}

        def _log(mesaj):
            logger.info(mesaj)
            if progress_callback:
                try:
                    progress_callback(mesaj)
                except Exception:
                    pass

        _log(f"Depo tarayıcıları başlatılıyor ({len(enabled_depolar)} depo)...")

        # İlk depoyu başlat (driver oluşturulsun)
        ilk_depo_key = enabled_depolar[0]
        ilk_depo_info = DEPO_CLASSES.get(ilk_depo_key)
        if not ilk_depo_info:
            logger.error(f"Bilinmeyen depo: {ilk_depo_key}")
            return {}

        ilk_depo = ilk_depo_info["class"]()
        headless = ayarlar.get("headless", False)

        _log(f"Tarayıcı başlatılıyor ({ilk_depo_key})...")
        if not ilk_depo.init_driver(headless=headless):
            logger.error("Tarayıcı başlatılamadı!")
            return {}

        self._shared_driver = ilk_depo.driver
        self._depolar[ilk_depo_key] = ilk_depo

        # Diğer depoları başlat (shared driver ile yeni sekmeler)
        for key in enabled_depolar[1:]:
            depo_info = DEPO_CLASSES.get(key)
            if not depo_info:
                continue

            depo = depo_info["class"]()
            _log(f"Sekme açılıyor: {depo.name}...")
            if depo.init_driver(headless=headless, shared_driver=self._shared_driver):
                self._depolar[key] = depo
            else:
                logger.error(f"{key}: Sekme açılamadı!")

        # Login işlemleri (sıralı - her depo kendi sekmesine gidip login olur)
        for key in enabled_depolar:
            depo = self._depolar.get(key)
            if not depo:
                results[key] = False
                continue

            depo_ayar = ayarlar.get(key, {})
            depo_info = DEPO_CLASSES[key]

            _log(f"Giriş yapılıyor: {depo.name}...")

            # Sayfayı aç
            depo.open_page()

            # Login argümanlarını hazırla
            login_kwargs = {}
            for arg_name in depo_info["login_args"]:
                login_kwargs[arg_name] = depo_ayar.get(arg_name, "")

            # Login ol
            try:
                login_success = depo.login(**login_kwargs)
                results[key] = login_success

                if login_success:
                    self._aktif_depolar[key] = depo
                    _log(f"{depo.name}: Giriş başarılı!")
                else:
                    _log(f"{depo.name}: Giriş başarısız!")
            except Exception as e:
                logger.error(f"{key}: Login hatası: {e}")
                results[key] = False
                _log(f"{depo.name}: Giriş hatası - {str(e)[:50]}")

        self._initialized = True
        basarili = sum(1 for v in results.values() if v)
        _log(f"Depo başlatma tamamlandı: {basarili}/{len(enabled_depolar)} başarılı")

        return results

    def search_product(self, barkod, progress_callback=None):
        """Tek ürünü TÜM aktif depolarda PARALEL ara

        Args:
            barkod: Aranacak barkod
            progress_callback: callable(mesaj: str) - İlerleme mesajı

        Returns:
            dict: {depo_key: {stok_var, fiyat, sart, mesaj, satis_kosullari, urun_adi}}
        """
        if not self._aktif_depolar:
            logger.warning("Aktif depo yok! Önce init_all() çağrılmalı.")
            return {}

        results = {}

        def _search_single(key, depo):
            """Tek depoda arama yap (thread'de çalışır)"""
            try:
                logger.info(f"{depo.name}: {barkod} aranıyor...")
                result = depo.search_product(barkod)
                return key, result
            except Exception as e:
                logger.error(f"{key}: Arama hatası: {e}")
                return key, {
                    "stok_var": False,
                    "fiyat": 0,
                    "sart": "",
                    "mesaj": f"Hata: {str(e)[:30]}",
                    "satis_kosullari": [],
                    "urun_adi": ""
                }

        def _log(mesaj):
            if progress_callback:
                try:
                    progress_callback(mesaj)
                except Exception:
                    pass

        _log(f"Barkod aranıyor: {barkod} ({len(self._aktif_depolar)} depo)...")

        # NOT: Selenium driver thread-safe değil.
        # Shared driver kullanıldığında paralel arama yapılamaz.
        # Sıralı arama yapıyoruz ama her depo kendi sekmesine geçiyor.
        siralama = self._get_depo_siralama()

        for key in siralama:
            depo = self._aktif_depolar.get(key)
            if not depo:
                continue

            _log(f"{depo.name} aranıyor...")
            _, result = _search_single(key, depo)
            results[key] = result

            # Stok durumunu logla
            stok = "VAR" if result.get("stok_var") else "YOK"
            mesaj = result.get("mesaj", "")
            fiyat = result.get("fiyat", "")
            fiyat_str = f" - {fiyat} TL" if fiyat else ""
            _log(f"{depo.name}: {stok} {mesaj}{fiyat_str}")

        return results

    def is_initialized(self):
        """Tarayıcılar hala açık mı?"""
        if not self._initialized or not self._shared_driver:
            return False

        try:
            # Driver hala çalışıyor mu kontrol et
            _ = self._shared_driver.current_url
            return True
        except Exception:
            self._initialized = False
            return False

    def close_all(self):
        """Tüm tarayıcıları kapat"""
        logger.info("Depo tarayıcıları kapatılıyor...")

        self._aktif_depolar.clear()
        self._depolar.clear()

        if self._shared_driver:
            try:
                self._shared_driver.quit()
                logger.info("Tarayıcı kapatıldı")
            except Exception as e:
                logger.error(f"Tarayıcı kapatma hatası: {e}")

        self._shared_driver = None
        self._initialized = False

    def get_status(self):
        """Her deponun durumunu döndür

        Returns:
            dict: {depo_key: {"name": str, "initialized": bool, "logged_in": bool}}
        """
        ayarlar = self._get_ayarlar()
        enabled_depolar = self._get_enabled_depolar()
        status = {}

        for key in enabled_depolar:
            depo = self._depolar.get(key)
            depo_info = DEPO_CLASSES.get(key, {})
            depo_class = depo_info.get("class")

            name = depo.name if depo else (depo_class().name if depo_class else key)

            status[key] = {
                "name": name,
                "initialized": key in self._depolar,
                "logged_in": key in self._aktif_depolar
            }

        return status

    def get_depo(self, key):
        """Belirli bir depo instance'ını al

        Args:
            key: Depo anahtarı (selcuk, alliance, sancak, iskoop, farmazon)

        Returns:
            BaseDepo instance veya None
        """
        return self._aktif_depolar.get(key)
