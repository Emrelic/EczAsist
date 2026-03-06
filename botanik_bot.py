"""
Botanik Medulla Reçete Takip Botu
Bu bot, Medulla programında otomatik reçete işlemleri yapar.
"""

import time
import threading
from pywinauto import Application, timings
from pywinauto.findwindows import ElementNotFoundError
from pywinauto.keyboard import send_keys
import logging
import ctypes
from ctypes import wintypes
import win32gui
import win32con
import subprocess
import csv
from pathlib import Path
from datetime import datetime
from timing_settings import get_timing_settings

# ===== WINDOWS HOOK POPUP WATCHER =====
# Event-driven popup detection - yeni pencere açıldığında tetiklenir
# CPU kullanmadan bekler, popup fırlayınca otomatik kapatır

# Windows Hook sabitleri
EVENT_OBJECT_CREATE = 0x8000
EVENT_OBJECT_SHOW = 0x8002
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

# Callback tipi tanımı
WINEVENTPROC = ctypes.WINFUNCTYPE(
    None,
    wintypes.HANDLE,  # hWinEventHook
    wintypes.DWORD,   # event
    wintypes.HWND,    # hwnd
    wintypes.LONG,    # idObject
    wintypes.LONG,    # idChild
    wintypes.DWORD,   # idEventThread
    wintypes.DWORD    # dwmsEventTime
)

# Kapatılacak popup tanımları - YENİ POPUP'LAR BURAYA EKLENİR
# Inspect bilgileri: 9 Aralık 2025
POPUP_PATTERNS = [
    {
        # UYARIDIR... / Genel Muayene popup
        # Title: "UYARIDIR...", Class: WindowsForms10.Window.8.app.0.134c08f_r8_ad1
        "name": "UYARIDIR",
        "title_contains": "UYARIDIR",
        "close_methods": [
            {"type": "auto_id", "value": "Close"},
            {"type": "name", "value": "Kapat"},
            {"type": "esc_key"}
        ]
    },
    {
        # REÇETE İÇİN NOT paneli
        # Title element: AutomationId="lblNotBaslik", Name="REÇETE İÇİN NOT"
        # Kapat butonu: AutomationId="btnReceteNotuPanelKapat", Name="KAPAT"
        "name": "REÇETE İÇİN NOT",
        "title_contains": "REÇETE İÇİN NOT",
        "close_methods": [
            {"type": "auto_id", "value": "btnReceteNotuPanelKapat"},
            {"type": "name", "value": "KAPAT"},
            {"type": "esc_key"}
        ]
    },
    {
        # LABA/LAMA ve İlaç Çakışması Dialog'ları
        # ClassName: #32770 (Windows Dialog), Title: boş
        # Çarpı butonu: AutomationId="Close", Name="Kapat"
        # Tamam butonu: AutomationId="2", Name="Tamam"
        "name": "Dialog (#32770)",
        "title_contains": None,  # Boş başlık
        "class_name": "#32770",  # Windows Dialog class
        "close_methods": [
            {"type": "auto_id", "value": "Close"},
            {"type": "name", "value": "Kapat"},
            {"type": "auto_id", "value": "2"},  # Tamam butonu
            {"type": "name", "value": "Tamam"},
            {"type": "esc_key"}
        ]
    },
    {
        # Genel WinForms Popup (fallback)
        "name": "Genel WinForms Popup",
        "title_contains": None,
        "class_contains": "WindowsForms10.Window",
        "close_methods": [
            {"type": "name", "value": "Kapat"},
            {"type": "name", "value": "KAPAT"},
            {"type": "name", "value": "Tamam"},
            {"type": "name", "value": "OK"},
            {"type": "name", "value": "Evet"},
            {"type": "name", "value": "Hayır"},
            {"type": "esc_key"}
        ]
    }
]


class PopupWatcher:
    """
    Windows Hook tabanlı event-driven popup watcher.

    Popup açıldığında otomatik tetiklenir, CPU kullanmadan bekler.
    Popup kapatılınca log yazar, program kaldığı yerden devam eder.
    """

    def __init__(self, bot_instance=None):
        self.bot = bot_instance
        self.running = False
        self.thread = None
        self.hook = None
        self._callback = None  # prevent garbage collection
        self._kapatilan_popup_sayisi = 0
        self._son_popup_zamani = None

        # Logger
        self.logger = logging.getLogger("PopupWatcher")

    def start(self):
        """Popup watcher thread'ini başlat"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_hook_loop, daemon=True)
        self.thread.start()
        self.logger.info("🔔 Popup Watcher başlatıldı (event-driven)")

    def stop(self):
        """Popup watcher'ı durdur"""
        self.running = False
        if self.hook:
            ctypes.windll.user32.UnhookWinEvent(self.hook)
            self.hook = None

    def _run_hook_loop(self):
        """Windows event hook döngüsü"""
        try:
            # Callback fonksiyonunu tanımla
            self._callback = WINEVENTPROC(self._win_event_callback)

            # Hook'u kur - EVENT_OBJECT_SHOW yakalayacağız
            self.hook = ctypes.windll.user32.SetWinEventHook(
                EVENT_OBJECT_SHOW,  # min event
                EVENT_OBJECT_SHOW,  # max event
                None,               # hmodWinEventProc
                self._callback,     # callback
                0,                  # idProcess (0 = tümü)
                0,                  # idThread (0 = tümü)
                WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
            )

            if not self.hook:
                self.logger.error("Windows hook kurulamadı!")
                return

            self.logger.debug("Windows hook kuruldu, popup'lar izleniyor...")

            # Message loop - hook'un çalışması için gerekli
            msg = wintypes.MSG()
            while self.running:
                # GetMessage yerine PeekMessage kullanarak non-blocking döngü
                if ctypes.windll.user32.PeekMessageW(
                    ctypes.byref(msg), None, 0, 0, 1  # PM_REMOVE
                ):
                    ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                    ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
                else:
                    # Mesaj yoksa kısa bekle (CPU kullanımı minimize)
                    time.sleep(0.1)

        except Exception as e:
            self.logger.error(f"Popup watcher hatası: {type(e).__name__}: {e}")
        finally:
            if self.hook:
                ctypes.windll.user32.UnhookWinEvent(self.hook)
                self.hook = None

    def _win_event_callback(self, hWinEventHook, event, hwnd, idObject, idChild,
                            idEventThread, dwmsEventTime):
        """Windows event callback - pencere gösterildiğinde tetiklenir"""
        if not hwnd or idObject != 0:  # OBJID_WINDOW = 0
            return

        try:
            # ===== SADECE TOP-LEVEL POPUP PENCERELERI YAKALA =====
            # Ana pencere içindeki label-tarzı popup'lar değil, gerçek popup'lar

            # 1. Pencere görünür mü?
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return

            # 2. Top-level pencere mi? (Parent = None veya Desktop)
            parent = ctypes.windll.user32.GetParent(hwnd)
            if parent:
                # Parent varsa ve Desktop değilse, bu bir child window (label olabilir)
                # Desktop hwnd = 0 veya GetDesktopWindow()
                desktop = ctypes.windll.user32.GetDesktopWindow()
                if parent != desktop and parent != 0:
                    return  # Child window, popup değil

            # 3. Pencere stili kontrol - WS_POPUP veya WS_OVERLAPPED mi?
            GWL_STYLE = -16
            WS_POPUP = 0x80000000
            WS_CHILD = 0x40000000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)

            # Child window ise atla (ana pencere içi element)
            if style & WS_CHILD:
                return

            # Pencere başlığını al
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return

            buffer = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
            window_title = buffer.value

            if not window_title:
                return

            # Class name al
            class_buffer = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, class_buffer, 256)
            class_name = class_buffer.value

            # Popup pattern kontrolü
            for pattern in POPUP_PATTERNS:
                if self._matches_pattern(window_title, class_name, pattern):
                    # Popup bulundu! Kapatmayı dene
                    self.logger.info(f"🔔 Popup tespit edildi: '{window_title}' ({pattern['name']})")

                    # Kısa bir gecikme (pencere tam açılsın)
                    time.sleep(0.2)

                    # Popup'ı kapat
                    if self._close_popup(hwnd, window_title, pattern):
                        self._kapatilan_popup_sayisi += 1
                        self._son_popup_zamani = datetime.now()
                        self.logger.info(f"✅ Popup kapatıldı: '{window_title}' "
                                        f"(Toplam: {self._kapatilan_popup_sayisi})")
                    break

        except Exception as e:
            # Callback hataları sessizce geç (çok sık tetiklenir)
            pass

    def _matches_pattern(self, window_title, class_name, pattern):
        """Pencere pattern'e uyuyor mu kontrol et"""
        # ===== ÖNEMLİ PENCERELER - ASLA KAPATILMAZ =====
        # Bu pencereler popup değil, program için gerekli pencereler

        # 1. Ana pencere (MEDULA)
        if "MEDULA" in window_title:
            return False

        # 2. Medula giriş penceresi (BotanikEOS)
        if "BotanikEOS" in window_title:
            return False

        # 3. Hasta ilaç listesi penceresi (Y butonuna basınca açılır)
        if "İlaç Listesi" in window_title:
            return False

        # 4. Reçete penceresi
        if "Reçete" in window_title and "NOT" not in window_title:
            return False

        # title_contains kontrolü
        title_check = pattern.get("title_contains")
        if title_check is not None:
            # Belirli bir başlık arıyoruz
            if title_check not in window_title:
                return False
        elif pattern.get("class_name") == "#32770":
            # #32770 Dialog için boş/kısa başlık bekliyoruz
            # LABA/LAMA ve İlaç Çakışması dialog'ları başlıksız
            if len(window_title) > 20:  # Uzun başlık = ana pencere
                return False

        # class_name tam eşleşme kontrolü (#32770 gibi)
        if pattern.get("class_name"):
            if class_name != pattern["class_name"]:
                return False
            return True  # class_name eşleşti, popup bulundu

        # class_contains kısmi eşleşme kontrolü
        if pattern.get("class_contains"):
            if pattern["class_contains"] not in class_name:
                return False

        return True

    def _close_popup(self, hwnd, window_title, pattern):
        """Popup'ı kapat"""
        from pywinauto import Desktop

        try:
            desktop = Desktop(backend="uia")
            window = desktop.window(handle=hwnd)

            if not window.exists(timeout=0.3):
                return False

            # Kapatma metodlarını dene
            for method in pattern.get("close_methods", []):
                try:
                    if method["type"] == "auto_id":
                        btn = window.child_window(auto_id=method["value"], control_type="Button")
                        if btn.exists(timeout=0.2):
                            self._click_button(btn)
                            return True

                    elif method["type"] == "name":
                        btn = window.child_window(title=method["value"], control_type="Button")
                        if btn.exists(timeout=0.2):
                            self._click_button(btn)
                            return True

                    elif method["type"] == "esc_key":
                        window.set_focus()
                        from pywinauto.keyboard import send_keys
                        send_keys("{ESC}")
                        time.sleep(0.2)
                        # Pencere hala açık mı?
                        if not win32gui.IsWindow(hwnd):
                            return True

                except Exception:
                    continue

            return False

        except Exception as e:
            self.logger.debug(f"Popup kapatma hatası: {type(e).__name__}")
            return False

    def _click_button(self, btn):
        """Butona tıkla (invoke, click, click_input sırasıyla dene)"""
        try:
            btn.invoke()
        except Exception:
            try:
                btn.click()
            except Exception:
                btn.click_input()
        time.sleep(0.2)


# Global popup watcher instance (bot dışında da erişilebilir)
_popup_watcher = None

def get_popup_watcher():
    """Global popup watcher instance'ını al veya oluştur"""
    global _popup_watcher
    if _popup_watcher is None:
        _popup_watcher = PopupWatcher()
    return _popup_watcher

# pywinauto hızlandırma - tüm internal timing'leri 2'ye böl
# Bu, pywinauto'nun kendi bekleme sürelerini optimize eder (element bulma vs.)
timings.Timings.fast()

# Logging ayarları - Saat:Dakika:Saniye:Milisaniye formatı
class MillisecondFormatter(logging.Formatter):
    """Milisaniye + önceki satırdan geçen süre içeren özel formatter"""
    _last_time = None

    def formatTime(self, record, datefmt=None):
        from datetime import datetime
        ct = datetime.fromtimestamp(record.created)
        s = ct.strftime("%H:%M:%S")
        s = f"{s}.{int(record.msecs):03d}"

        # Önceki satırdan geçen süreyi hesapla (her zaman saniye cinsinden)
        if MillisecondFormatter._last_time is not None:
            delta = record.created - MillisecondFormatter._last_time
            s = f"{s} (+{delta:.2f}s)"
        else:
            s = f"{s} (start)"

        MillisecondFormatter._last_time = record.created
        return s

# Root logger'ı temizle ve yeniden yapılandır
root_logger = logging.getLogger()
# Eski handler'ları kaldır
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Console handler oluştur
console_handler = logging.StreamHandler()
console_handler.setFormatter(MillisecondFormatter('%(asctime)s: %(message)s'))

# Dosya handler oluştur (TÜM logları kaydet - Y butonu, konsol, vs)
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
debug_log_path = os.path.join(script_dir, 'botanik_debug.log')
file_handler = logging.FileHandler(debug_log_path, mode='a', encoding='utf-8')
file_handler.setFormatter(MillisecondFormatter('%(asctime)s: %(message)s'))

# Root logger'ı yapılandır
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)  # Dosyaya da yaz

logger = logging.getLogger(__name__)


# ==================== CUSTOM EXCEPTIONS ====================
class SistemselHataException(Exception):
    """MEDULA'da sistemsel hata oluştuğunda fırlatılan exception"""
    pass


class RaporTakip:
    """
    Hasta rapor bilgilerini CSV dosyasına kaydeder.

    CSV Formatı:
    Ad Soyad,Telefon,Rapor Tanısı,Bitiş Tarihi,Kayıt Tarihi,Grup,Kopyalandı

    Her rapor ayrı bir satır olarak kaydedilir.
    Bir hastanın birden fazla raporu varsa, hasta bilgileri her satırda tekrar eder.
    """

    def __init__(self, dosya_yolu="rapor_takip.csv"):
        """
        RaporTakip sınıfını başlatır ve CSV dosyasını hazırlar.

        Args:
            dosya_yolu: CSV dosyasının yolu (varsayılan: rapor_takip.csv)
        """
        # Dosyayı script'in bulunduğu dizine kaydet
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.dosya_yolu = Path(script_dir) / dosya_yolu
        self.toplam_kayit = 0  # Bu oturum boyunca kaydedilen toplam rapor sayısı
        self.mevcut_kayitlar = set()  # CSV'deki tüm kayıtların hash'leri (tekrar önleme için)
        self._dosyayi_baslat()

    def _dosyayi_baslat(self):
        """CSV dosyasını oluşturur ve header ekler (eğer dosya yoksa).
        Varsa mevcut kayıtları okuyup belleğe yükler (tekrar önlemek için)."""
        if not self.dosya_yolu.exists():
            try:
                with open(self.dosya_yolu, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Ad Soyad', 'Telefon', 'Rapor Tanısı', 'Bitiş Tarihi', 'Kayıt Tarihi', 'Grup', 'Kopyalandı'])
                logger.info(f"✓ Rapor takip dosyası oluşturuldu: {self.dosya_yolu}")
            except Exception as e:
                logger.error(f"CSV dosyası oluşturma hatası: {e}")
        else:
            # Dosya var, önce eski formattaysa güncelle
            self._eski_csv_guncelle()
            # Sonra mevcut kayıtları oku (tekrar kontrolü için)
            self._mevcut_kayitlari_yukle()

    def _eski_csv_guncelle(self):
        """Eski CSV dosyalarına 'Grup' ve 'Kopyalandı' sütunlarını ekle (migration)"""
        try:
            with open(self.dosya_yolu, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames

                if not header:
                    return

                # Eksik sütunları tespit et
                guncellemeler = []
                if 'Grup' not in header:
                    guncellemeler.append('Grup')
                if 'Kopyalandı' not in header:
                    guncellemeler.append('Kopyalandı')

                # Güncelleme gerekli mi?
                if not guncellemeler:
                    return  # Zaten güncel

                # Eski format - tüm satırları oku
                satirlar = list(reader)

            # Yeni header oluştur (Grup'u Kayıt Tarihi'nden sonra, Kopyalandı'yı sona ekle)
            if 'Kayıt Tarihi' in header:
                kayit_index = header.index('Kayıt Tarihi')
                yeni_header = list(header[:kayit_index+1])
                if 'Grup' in guncellemeler:
                    yeni_header.append('Grup')
                yeni_header.extend([h for h in header[kayit_index+1:] if h != 'Grup'])
                if 'Kopyalandı' in guncellemeler:
                    yeni_header.append('Kopyalandı')
            else:
                yeni_header = list(header) + guncellemeler

            # Yeni formatta yaz
            with open(self.dosya_yolu, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=yeni_header)
                writer.writeheader()

                for row in satirlar:
                    if 'Grup' not in row:
                        row['Grup'] = ''  # Boş olarak ekle
                    if 'Kopyalandı' not in row:
                        row['Kopyalandı'] = ''  # Boş olarak ekle
                    writer.writerow(row)

            logger.info(f"  ℹ️ CSV dosyası yeni formata güncellendi ({', '.join(guncellemeler)} sütunu eklendi)")

        except Exception as e:
            logger.debug(f"CSV güncelleme hatası (normal olabilir): {e}")

    def _mevcut_kayitlari_yukle(self):
        """CSV'den tüm kayıtları okuyup belleğe yükler (tekrar önlemek için)."""
        try:
            with open(self.dosya_yolu, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Kontrol anahtarı: ad+telefon+tanı+bitiş tarihi (kayıt tarihi dahil DEĞİL)
                    kayit_anahtari = f"{row['Ad Soyad']}|{row['Telefon']}|{row['Rapor Tanısı']}|{row['Bitiş Tarihi']}"
                    self.mevcut_kayitlar.add(kayit_anahtari)

            if self.mevcut_kayitlar:
                logger.info(f"  ℹ️ {len(self.mevcut_kayitlar)} mevcut kayıt yüklendi (tekrar önleme için)")
        except Exception as e:
            logger.debug(f"Mevcut kayıtlar yüklenemedi: {e}")

    def rapor_ekle(self, ad_soyad, telefon, tani, bitis_tarihi, grup=""):
        """
        Tek bir rapor kaydı ekler.
        Aynı (ad+telefon+tanı+bitiş tarihi) kombinasyonu daha önce eklenmişse atlar.

        Args:
            ad_soyad: Hasta adı soyadı
            telefon: Telefon numarası (temizlenmiş format)
            tani: Rapor tanısı
            bitis_tarihi: Rapor bitiş tarihi (DD/MM/YYYY formatında)

        Returns:
            bool: Başarılıysa True, tekrar ise False
        """
        try:
            # Benzersiz anahtar oluştur (tekrar kontrolü için)
            # NOT: Kayıt tarihi anahtara DAHİL DEĞİL - aynı rapor hangi gün olursa olsun bir kez yazılır
            kayit_anahtari = f"{ad_soyad}|{telefon}|{tani}|{bitis_tarihi}"

            # Bu kayıt daha önce eklenmiş mi?
            if kayit_anahtari in self.mevcut_kayitlar:
                logger.debug(f"  ⏭ Atlandı (daha önce eklendi): {ad_soyad} - {tani[:30]}...")
                return False

            kayit_tarihi = datetime.now().strftime("%d/%m/%Y")

            with open(self.dosya_yolu, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow([ad_soyad, telefon, tani, bitis_tarihi, kayit_tarihi, grup, ""])

            # Bu anahtarı kaydet (tekrar yazılmasın)
            self.mevcut_kayitlar.add(kayit_anahtari)
            self.toplam_kayit += 1
            return True
        except Exception as e:
            logger.error(f"Rapor ekleme hatası: {e}")
            return False

    def toplu_rapor_ekle(self, ad_soyad, telefon, raporlar_listesi, grup=""):
        """
        Aynı hasta için birden fazla rapor ekler.
        Aynı bitiş tarihine sahip raporları birleştirip tanıları yan yana dizer.

        Args:
            ad_soyad: Hasta adı soyadı
            telefon: Telefon numarası (temizlenmiş format)
            raporlar_listesi: [{"tani": str, "bitis_tarihi": str}, ...] formatında rapor listesi

        Returns:
            int: Kaydedilen rapor sayısı
        """
        # Aynı bitiş tarihine sahip raporları grupla
        from collections import defaultdict
        tarih_gruplari = defaultdict(list)

        for rapor in raporlar_listesi:
            tarih_gruplari[rapor["bitis_tarihi"]].append(rapor["tani"])

        # Her tarih için birleştirilmiş rapor oluştur
        kayit_sayisi = 0
        atlanan_sayisi = 0

        for bitis_tarihi, tanilar in tarih_gruplari.items():
            # Tanıları " + " ile birleştir
            birlesik_tani = " + ".join(tanilar)

            if self.rapor_ekle(ad_soyad, telefon, birlesik_tani, bitis_tarihi, grup):
                kayit_sayisi += 1
            else:
                atlanan_sayisi += 1

        if kayit_sayisi > 0:
            logger.info(f"  ✓ {kayit_sayisi} satır ({len(raporlar_listesi)} rapor) CSV'ye kaydedildi")

        if atlanan_sayisi > 0:
            logger.info(f"  ⏭ {atlanan_sayisi} satır atlandı (tekrar)")

        return kayit_sayisi

    def kopyalanmamis_raporlari_al(self):
        """
        Henüz kopyalanmamış (Kopyalandı sütunu boş) ve tarihi geçmemiş raporları döndürür.

        Returns:
            tuple: (gecerli_raporlar_listesi, silinen_sayisi)
                   gecerli_raporlar_listesi: [{ad, telefon, tani, bitis, kayit}, ...]
                   silinen_sayisi: Tarihi geçmiş rapor sayısı
        """
        try:
            bugun = datetime.now().date()
            gecerli_raporlar = []
            silinen_sayisi = 0

            with open(self.dosya_yolu, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    try:
                        # Tarihi kontrol et
                        bitis_str = row['Bitiş Tarihi']
                        bitis_tarihi = datetime.strptime(bitis_str, "%d/%m/%Y").date()

                        if bitis_tarihi < bugun:
                            silinen_sayisi += 1
                            continue

                        # Kopyalandı mı kontrol et
                        kopyalandi = row.get('Kopyalandı', '').strip()
                        if not kopyalandi:
                            gecerli_raporlar.append({
                                'ad': row['Ad Soyad'],
                                'telefon': row['Telefon'],
                                'tani': row['Rapor Tanısı'],
                                'bitis': row['Bitiş Tarihi'],
                                'kayit': row['Kayıt Tarihi']
                            })
                    except Exception as e:
                        logger.debug(f"Satır parse hatası: {e}")
                        continue

            return gecerli_raporlar, silinen_sayisi

        except Exception as e:
            logger.error(f"Kopyalanmamış raporlar okunurken hata: {e}")
            return [], 0

    def kopyalandi_isaretle(self, raporlar_listesi):
        """
        Verilen raporların Kopyalandı sütununa bugünün tarihini yazar.
        Atomic write kullanılarak data loss önlenir.

        Args:
            raporlar_listesi: [{ad, telefon, tani, bitis, kayit}, ...] formatında rapor listesi

        Returns:
            int: İşaretlenen rapor sayısı
        """
        import tempfile
        import shutil

        try:
            bugun = datetime.now().strftime("%d/%m/%Y")
            isaretlenen_sayisi = 0

            # Tüm raporları oku
            tum_satirlar = []
            with open(self.dosya_yolu, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames

                for row in reader:
                    tum_satirlar.append(row)

            # İşaretlenecek raporların anahtarlarını oluştur
            isaretlenecekler = set()
            for rapor in raporlar_listesi:
                anahtar = f"{rapor['ad']}|{rapor['telefon']}|{rapor['tani']}|{rapor['bitis']}"
                isaretlenecekler.add(anahtar)

            # Kopyalandı sütununu güncelle
            for row in tum_satirlar:
                anahtar = f"{row['Ad Soyad']}|{row['Telefon']}|{row['Rapor Tanısı']}|{row['Bitiş Tarihi']}"
                if anahtar in isaretlenecekler:
                    row['Kopyalandı'] = bugun
                    isaretlenen_sayisi += 1

            # ATOMIC WRITE: Önce temp dosyaya yaz, sonra rename et
            temp_fd, temp_path = tempfile.mkstemp(suffix='.csv', dir=self.dosya_yolu.parent, text=True)
            try:
                with os.fdopen(temp_fd, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=header)
                    writer.writeheader()
                    writer.writerows(tum_satirlar)

                # Atomic rename (Windows'ta replace kullan)
                shutil.move(temp_path, self.dosya_yolu)
                logger.debug(f"✓ CSV atomik olarak güncellendi: {isaretlenen_sayisi} rapor işaretlendi")

            except Exception as write_error:
                # Hata durumunda temp dosyayı sil
                try:
                    os.unlink(temp_path)
                except OSError as e:
                    logger.debug(f"Temp dosya silme hatası (non-critical): {e}")
                raise write_error

            return isaretlenen_sayisi

        except Exception as e:
            logger.error(f"Kopyalandı işaretleme hatası: {e}")
            return 0


class BotanikBot:
    """Medulla programı için otomasyon botu"""

    def __init__(self):
        self.app = None
        self.main_window = None
        # Element cache sistemi - performans için
        self._element_cache = {}
        self._cache_enabled = True
        # Zamanlama ayarları
        self.timing = get_timing_settings()
        # Pencere handle cache - performans optimizasyonu (BotTak7'den)
        self.medula_hwnd = None  # Pencere handle'ı
        self.medula_pid = None   # Process ID

        # ===== İNSAN DAVRANIŞI MODU =====
        self._insan_davranisi_ayarlar = self._insan_davranisi_yukle()
        self._insan_modu_aktif = self._insan_modu_kontrol()

        # Oturum başında mod seçimi (hibrit yaklaşım)
        if self._insan_modu_aktif:
            logger.info("🧠 İnsan Davranışı Modu: AKTİF")
            self.timed_sleep = self._insan_modlu_sleep
            # Thread'leri başlat (dikkat bozucu, yorgunluk)
            self._dikkat_bozucu_thread = None
            self._yorgunluk_thread = None
            self._duraklama_aktif = False  # Dikkat bozucu duraklama durumu
            self._dinlenme_aktif = False   # Yorgunluk dinlenme durumu
            self._insan_threadleri_baslat()
        else:
            logger.info("⚡ Yalın Mod: AKTİF (maksimum hız)")
            self.timed_sleep = self._yalin_sleep

        # ===== POPUP WATCHER BAŞLAT =====
        # Event-driven popup detection - CPU kullanmadan popup'ları yakalar
        self.popup_watcher = get_popup_watcher()
        self.popup_watcher.bot = self  # Bot referansı
        self.popup_watcher.start()

    def _insan_davranisi_yukle(self):
        """İnsan davranışı ayarlarını JSON'dan yükle"""
        import json
        try:
            with open("insan_davranisi_settings.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.warning(f"İnsan davranışı ayarları yüklenemedi: {e}")
            return {}

    def _insan_modu_kontrol(self):
        """Herhangi bir insan davranışı özelliği aktif mi?"""
        if not self._insan_davranisi_ayarlar:
            return False

        return (
            self._insan_davranisi_ayarlar.get("ritim_bozucu", {}).get("aktif", False) or
            self._insan_davranisi_ayarlar.get("dikkat_bozucu", {}).get("aktif", False) or
            self._insan_davranisi_ayarlar.get("yorgunluk", {}).get("aktif", False) or
            self._insan_davranisi_ayarlar.get("hata_durumunda_bekle", {}).get("aktif", False) or
            self._insan_davranisi_ayarlar.get("textbox_122", {}).get("yazmayi_devre_disi_birak", False) or
            self._insan_davranisi_ayarlar.get("textbox_122", {}).get("ozel_deger_kullan", False)
        )

    def _yalin_sleep(self, key, default=0.1):
        """
        Ayarlı bekleme süresi + istatistik kaydı

        Args:
            key (str): Timing ayar anahtarı
            default (float): Varsayılan süre (bulunamazsa)
        """
        start_time = time.time()
        sleep_duration = self.timing.get(key, default)
        time.sleep(sleep_duration)
        actual_duration = time.time() - start_time

        # İstatistik kaydet
        self.timing.kayit_ekle(key, actual_duration)

    def _insan_modlu_sleep(self, key, default=0.1):
        """
        İnsan davranışı modunda bekleme süresi

        Özellikler:
        - Ritim bozucu: Her adıma random süre ekler
        - Dikkat bozucu: Periyodik duraklamalar (thread ile)
        - Yorgunluk: Uzun dinlenme araları (thread ile)
        """
        import random

        start_time = time.time()
        sleep_duration = self.timing.get(key, default)

        # ===== RİTİM BOZUCU =====
        ritim_ayar = self._insan_davranisi_ayarlar.get("ritim_bozucu", {})
        if ritim_ayar.get("aktif", False):
            max_ms = ritim_ayar.get("max_ms", 3000)
            ek_sure = random.randint(0, max_ms) / 1000.0  # ms → saniye
            sleep_duration += ek_sure

        # ===== DİKKAT BOZUCU DURAKLAMA KONTROLÜ =====
        # Thread tarafından _duraklama_aktif=True yapılınca bekle
        while self._duraklama_aktif:
            time.sleep(0.1)

        # ===== YORGUNLUK DİNLENME KONTROLÜ =====
        # Thread tarafından _dinlenme_aktif=True yapılınca bekle
        while self._dinlenme_aktif:
            time.sleep(0.1)

        # Normal bekleme
        time.sleep(sleep_duration)
        actual_duration = time.time() - start_time

        # İstatistik kaydet
        self.timing.kayit_ekle(key, actual_duration)

    def _insan_threadleri_baslat(self):
        """Dikkat bozucu ve yorgunluk thread'lerini başlat"""
        import threading
        import random

        # ===== DİKKAT BOZUCU THREAD =====
        dikkat_ayar = self._insan_davranisi_ayarlar.get("dikkat_bozucu", {})
        if dikkat_ayar.get("aktif", False):
            def dikkat_bozucu_dongusu():
                aralik_max = dikkat_ayar.get("aralik_max_ms", 100000)
                duraklama_max = dikkat_ayar.get("duraklama_max_ms", 10000)

                while True:
                    try:
                        # Random aralık bekle
                        aralik = random.randint(0, aralik_max) / 1000.0
                        time.sleep(aralik)

                        # Duraklama başlat
                        duraklama = random.randint(0, duraklama_max) / 1000.0
                        logger.debug(f"👀 Dikkat bozucu: {duraklama:.1f}s duraklama")
                        self._duraklama_aktif = True
                        time.sleep(duraklama)
                        self._duraklama_aktif = False
                    except Exception:
                        break

            self._dikkat_bozucu_thread = threading.Thread(target=dikkat_bozucu_dongusu, daemon=True)
            self._dikkat_bozucu_thread.start()
            logger.info("  → Dikkat bozucu thread başlatıldı")

        # ===== YORGUNLUK THREAD =====
        yorgunluk_ayar = self._insan_davranisi_ayarlar.get("yorgunluk", {})
        if yorgunluk_ayar.get("aktif", False):
            def yorgunluk_dongusu():
                calisma_min = yorgunluk_ayar.get("calisma_min_ms", 1200000)
                calisma_max = yorgunluk_ayar.get("calisma_max_ms", 1800000)
                dinlenme_min = yorgunluk_ayar.get("dinlenme_min_ms", 300000)
                dinlenme_max = yorgunluk_ayar.get("dinlenme_max_ms", 480000)

                while True:
                    try:
                        # Random çalışma süresi
                        calisma = random.randint(calisma_min, calisma_max) / 1000.0
                        time.sleep(calisma)

                        # Dinlenme başlat
                        dinlenme = random.randint(dinlenme_min, dinlenme_max) / 1000.0
                        logger.info(f"😴 Yorgunluk modu: {dinlenme/60:.1f} dakika dinlenme başlıyor...")
                        self._dinlenme_aktif = True
                        time.sleep(dinlenme)
                        self._dinlenme_aktif = False
                        logger.info("😊 Dinlenme bitti, çalışmaya devam...")
                    except Exception:
                        break

            self._yorgunluk_thread = threading.Thread(target=yorgunluk_dongusu, daemon=True)
            self._yorgunluk_thread.start()
            logger.info("  → Yorgunluk thread başlatıldı")

    def retry_with_popup_check(self, operation_func, operation_name, max_retries=5, critical=True):
        """
        UI element bulma/tıklama işlemini dene, başarısız olursa:
        1. KRİTİK POPUP kontrolü (UYARIDIR + REÇETE İÇİN NOT)
        2. Genel popup kontrolü
        3. LABA/LAMA penceresi kontrolü
        4. Popup kapatıldıysa TEKRAR DENE (taskkill YAPMADAN!)
        5. Hala olmazsa ve critical=True ise SistemselHataException fırlat

        ÖNEMLİ: Popup kapatıldığında program kaldığı yerden devam eder.
        Taskkill ile yeniden başlatma SADECE popup kontrolü sonrası da başarısızsa yapılır.

        Args:
            operation_func: Çalıştırılacak fonksiyon (parametresiz)
            operation_name: İşlem adı (log için)
            max_retries: Maksimum deneme sayısı (varsayılan: 5)
            critical: True ise başarısızlıkta SistemselHataException fırlatır,
                     False ise sadece False döner ve devam eder

        Returns:
            bool: Başarılıysa True, başarısızsa False

        Raises:
            SistemselHataException: MEDULA'da sistemsel hata tespit edilirse (sadece critical=True ise)
        """
        popup_kapatildi_toplam = 0  # Kapatılan popup sayısı

        for deneme in range(1, max_retries + 1):
            try:
                # ÖNEMLİ: Her denemeden önce sistemsel hata kontrolü yap
                if sistemsel_hata_kontrol():
                    logger.error("⚠️ Sistemsel hata tespit edildi, MEDULA yeniden başlatılacak...")
                    raise SistemselHataException("Yazılımsal veya sistemsel bir hata oluştu")

                # İşlemi çalıştır
                sonuc = operation_func()
                if sonuc:
                    if deneme > 1:
                        logger.info(f"✓ {operation_name} başarılı ({deneme}. denemede)")
                    return True

                # Başarısız oldu
                if deneme < max_retries:
                    logger.warning(f"⚠ {operation_name} başarısız (Deneme {deneme}/{max_retries})")

                    # Sistemsel hata kontrolü (başarısız işlem sonrası)
                    if sistemsel_hata_kontrol():
                        logger.error("⚠️ Sistemsel hata tespit edildi, MEDULA yeniden başlatılacak...")
                        raise SistemselHataException("Yazılımsal veya sistemsel bir hata oluştu")

                    # ★ KRİTİK POPUP KONTROLÜ (UYARIDIR + REÇETE İÇİN NOT) ★
                    try:
                        if self.kritik_popup_kontrol_ve_kapat():
                            popup_kapatildi_toplam += 1
                            logger.info(f"✓ Kritik popup kapatıldı, {operation_name} tekrar deneniyor...")
                            self.timed_sleep("retry_after_popup", 0.5)
                    except Exception as e:
                        logger.debug(f"Kritik popup kontrol hatası: {type(e).__name__}")

                    # Genel popup kontrolü
                    try:
                        if popup_kontrol_ve_kapat():
                            popup_kapatildi_toplam += 1
                            logger.info(f"✓ Popup kapatıldı, {operation_name} tekrar deneniyor...")
                            self.timed_sleep("retry_after_popup", 0.3)
                    except Exception as e:
                        logger.debug(f"Popup kontrol hatası: {type(e).__name__}")

                    # 2. denemede LABA/LAMA penceresi kontrolü yap (Giriş butonuna BASMA!)
                    if deneme == 2:
                        logger.warning("🔄 LABA/LAMA penceresi kontrolü yapılıyor...")
                        try:
                            if self.laba_lama_uyarisini_kapat(max_bekleme=2.0):
                                popup_kapatildi_toplam += 1
                                logger.info("✓ LABA/LAMA penceresi kapatıldı")
                                self.timed_sleep("retry_after_popup", 0.5)
                        except Exception as e:
                            logger.debug(f"LABA/LAMA kontrol hatası: {type(e).__name__}")

                    # Pencereyi yenile
                    try:
                        self.baglanti_kur("MEDULA", ilk_baglanti=False)
                        self.timed_sleep("retry_after_reconnect", 0.3)
                    except Exception as e:
                        logger.warning(f"Reconnect başarısız: {type(e).__name__}: {e}")

                else:
                    # ★ SON DENEME - POPUP KONTROLÜ VE EKSTRA ŞANS ★
                    logger.warning(f"⚠ {operation_name} {max_retries} denemede başarısız, son popup kontrolü yapılıyor...")

                    # Son kez kritik popup kontrolü
                    popup_kapatildi = False
                    try:
                        if self.kritik_popup_kontrol_ve_kapat():
                            popup_kapatildi = True
                            popup_kapatildi_toplam += 1
                            logger.info("✓ Son denemede kritik popup kapatıldı!")
                    except Exception:
                        pass

                    try:
                        if popup_kontrol_ve_kapat():
                            popup_kapatildi = True
                            popup_kapatildi_toplam += 1
                            logger.info("✓ Son denemede popup kapatıldı!")
                    except Exception:
                        pass

                    # Popup kapatıldıysa BİR KEZ DAHA DENE (taskkill YAPMADAN!)
                    if popup_kapatildi:
                        logger.info(f"🔄 Popup kapatıldı, {operation_name} SON BİR KEZ deneniyor...")
                        self.timed_sleep("retry_after_popup", 0.5)
                        try:
                            self.baglanti_kur("MEDULA", ilk_baglanti=False)
                            sonuc = operation_func()
                            if sonuc:
                                logger.info(f"✅ {operation_name} başarılı (popup kapatıldıktan sonra)")
                                return True
                        except Exception as e:
                            logger.warning(f"Son deneme hatası: {type(e).__name__}")

                    # Gerçekten tüm denemeler başarısız
                    logger.error(f"❌ {operation_name} başarısız ({max_retries} deneme + {popup_kapatildi_toplam} popup kapatıldı)")

                    if critical:
                        # Kritik işlem - ANCAK ŞİMDİ MEDULA'yı yeniden başlat
                        logger.warning("🔄 MEDULA yeniden başlatılıyor (popup kontrolü sonrası da başarısız)...")
                        raise SistemselHataException(f"{operation_name} tüm denemeler + popup kontrolü sonrası başarısız")
                    else:
                        # Kritik değil - sadece False dön ve devam et
                        logger.warning(f"⚠️ {operation_name} başarısız ama kritik değil, devam ediliyor...")
                        return False

            except SistemselHataException:
                # Sistemsel hata exception'ını yukarıya fırlat
                raise
            except Exception as e:
                if deneme < max_retries:
                    logger.warning(f"⚠ {operation_name} hata (Deneme {deneme}/{max_retries}): {type(e).__name__}: {e}")

                    # Hata sonrası da kritik popup kontrolü
                    try:
                        if self.kritik_popup_kontrol_ve_kapat():
                            popup_kapatildi_toplam += 1
                            logger.info("✓ Hata sonrası popup kapatıldı")
                    except Exception:
                        pass

                    self.timed_sleep("retry_after_error", 0.3)
                else:
                    logger.error(f"❌ {operation_name} hata ({max_retries} deneme): {type(e).__name__}: {e}")

                    # Son denemede de popup kontrolü
                    try:
                        if self.kritik_popup_kontrol_ve_kapat():
                            popup_kapatildi_toplam += 1
                            logger.info("✓ Son hata sonrası popup kapatıldı, bir kez daha deneniyor...")
                            self.timed_sleep("retry_after_popup", 0.5)
                            try:
                                sonuc = operation_func()
                                if sonuc:
                                    logger.info(f"✅ {operation_name} başarılı (hata sonrası popup kapatıldı)")
                                    return True
                            except Exception:
                                pass
                    except Exception:
                        pass

                    if critical:
                        raise SistemselHataException(f"{operation_name} tüm denemeler başarısız")
                    else:
                        logger.warning(f"⚠️ {operation_name} başarısız ama kritik değil, devam ediliyor...")
                        return False

        return False

    def recete_notu_panelini_kapat(self):
        """
        Reçete Notu panelini kapat (ilaç butonunun üzerini kapatıyorsa)

        UIElementInspector bilgileri (4 Aralık 2025):
        - Panel Başlığı: Name="REÇETE İÇİN NOT", AutomationId="lblNotBaslik"
        - Kapat Butonu: Name="KAPAT", AutomationId="btnReceteNotuPanelKapat"

        Returns:
            bool: Panel bulunup kapatıldıysa True, panel yoksa veya kapatılamadıysa False
        """
        try:
            logger.debug("🔍 Reçete notu paneli kontrol ediliyor...")

            # Önce panel başlığını ara (lblNotBaslik veya "REÇETE İÇİN NOT")
            panel_var = False

            # Method 1: AutomationId ile ara
            try:
                panel_baslik = self.main_window.child_window(
                    auto_id="lblNotBaslik",
                    control_type="Text"
                )
                if panel_baslik.exists(timeout=0.3):
                    panel_var = True
                    logger.info("📝 Reçete notu paneli tespit edildi (AutomationId)")
            except Exception as e:
                logger.debug(f"Panel AutomationId arama hatası: {type(e).__name__}")

            # Method 2: Name ile ara
            if not panel_var:
                try:
                    panel_baslik = self.main_window.child_window(
                        title="REÇETE İÇİN NOT",
                        control_type="Text"
                    )
                    if panel_baslik.exists(timeout=0.3):
                        panel_var = True
                        logger.info("📝 Reçete notu paneli tespit edildi (Name)")
                except Exception as e:
                    logger.debug(f"Panel Name arama hatası: {type(e).__name__}")

            if not panel_var:
                logger.debug("  → Reçete notu paneli yok")
                return False

            # Panel var, KAPAT butonunu bul ve tıkla
            logger.info("📝 Reçete notu paneli kapatılıyor...")

            # Method 1: AutomationId ile kapat butonunu bul
            try:
                kapat_btn = self.main_window.child_window(
                    auto_id="btnReceteNotuPanelKapat",
                    control_type="Button"
                )
                if kapat_btn.exists(timeout=0.3):
                    try:
                        kapat_btn.invoke()
                    except Exception:
                        try:
                            kapat_btn.click()
                        except Exception:
                            kapat_btn.click_input()
                    logger.info("✓ Reçete notu paneli kapatıldı (AutomationId)")
                    time.sleep(0.2)
                    return True
            except Exception as e:
                logger.debug(f"Kapat butonu AutomationId hatası: {type(e).__name__}")

            # Method 2: Name ile kapat butonunu bul
            try:
                kapat_btn = self.main_window.child_window(
                    title="KAPAT",
                    control_type="Button"
                )
                if kapat_btn.exists(timeout=0.3):
                    try:
                        kapat_btn.invoke()
                    except Exception:
                        try:
                            kapat_btn.click()
                        except Exception:
                            kapat_btn.click_input()
                    logger.info("✓ Reçete notu paneli kapatıldı (Name)")
                    time.sleep(0.2)
                    return True
            except Exception as e:
                logger.debug(f"Kapat butonu Name hatası: {type(e).__name__}")

            # Method 3: descendants ile ara
            try:
                kapat_btns = self.main_window.descendants(
                    auto_id="btnReceteNotuPanelKapat",
                    control_type="Button"
                )
                if kapat_btns and len(kapat_btns) > 0:
                    try:
                        kapat_btns[0].invoke()
                    except Exception:
                        try:
                            kapat_btns[0].click()
                        except Exception:
                            kapat_btns[0].click_input()
                    logger.info("✓ Reçete notu paneli kapatıldı (descendants)")
                    time.sleep(0.2)
                    return True
            except Exception as e:
                logger.debug(f"Kapat butonu descendants hatası: {type(e).__name__}")

            logger.warning("⚠ Reçete notu paneli tespit edildi ama kapatılamadı")
            return False

        except Exception as e:
            logger.debug(f"Reçete notu paneli kontrol hatası: {type(e).__name__}: {e}")
            return False

    def uyaridir_popup_kapat(self):
        """
        "UYARIDIR..." popup penceresini kapat.

        UIElementInspector bilgileri (9 Aralık 2025):
        - WindowTitle: "UYARIDIR..."
        - ClassName: WindowsForms10.Window.8.app.0.134c08f_r8_ad1
        - Kapat butonu: Name="Kapat", AutomationId="Close"

        Bu popup İlaç, Rapor, Sonraki, Y butonlarını engelleyebilir.
        Popup kapatılarak program kaldığı yerden devam eder.

        Returns:
            bool: Popup bulunup kapatıldıysa True, popup yoksa False
        """
        try:
            from pywinauto import Desktop

            desktop = Desktop(backend="uia")
            windows = desktop.windows()

            for window in windows:
                try:
                    window_text = window.window_text()

                    # "UYARIDIR" içeren pencere mi?
                    if window_text and "UYARIDIR" in window_text:
                        logger.info(f"⚠️ UYARIDIR popup tespit edildi: '{window_text}'")

                        # Method 1: AutomationId="Close" ile kapat
                        try:
                            kapat_btn = window.child_window(auto_id="Close", control_type="Button")
                            if kapat_btn.exists(timeout=0.3):
                                try:
                                    kapat_btn.invoke()
                                except Exception:
                                    try:
                                        kapat_btn.click()
                                    except Exception:
                                        kapat_btn.click_input()
                                logger.info("✅ UYARIDIR popup kapatıldı (AutomationId=Close)")
                                self.timed_sleep("popup_kapat", 0.3)
                                return True
                        except Exception as e:
                            logger.debug(f"Close butonu AutomationId hatası: {type(e).__name__}")

                        # Method 2: Name="Kapat" ile kapat
                        try:
                            kapat_btn = window.child_window(title="Kapat", control_type="Button")
                            if kapat_btn.exists(timeout=0.3):
                                try:
                                    kapat_btn.invoke()
                                except Exception:
                                    try:
                                        kapat_btn.click()
                                    except Exception:
                                        kapat_btn.click_input()
                                logger.info("✅ UYARIDIR popup kapatıldı (Name=Kapat)")
                                self.timed_sleep("popup_kapat", 0.3)
                                return True
                        except Exception as e:
                            logger.debug(f"Kapat butonu Name hatası: {type(e).__name__}")

                        # Method 3: ESC tuşu ile kapat
                        try:
                            window.set_focus()
                            from pywinauto.keyboard import send_keys
                            send_keys("{ESC}")
                            logger.info("✅ UYARIDIR popup kapatıldı (ESC)")
                            self.timed_sleep("popup_kapat", 0.3)
                            return True
                        except Exception as e:
                            logger.debug(f"ESC ile kapatma hatası: {type(e).__name__}")

                except Exception as e:
                    continue

            return False

        except Exception as e:
            logger.debug(f"UYARIDIR popup kontrol hatası: {type(e).__name__}")
            return False

    def kritik_popup_kontrol_ve_kapat(self):
        """
        İlaç/Rapor/Sonraki/Y butonlarını engelleyen kritik popup'ları kontrol et ve kapat.

        Kontrol edilen popup'lar:
        1. "UYARIDIR..." - AutomationId="Close" veya Name="Kapat"
        2. "REÇETE İÇİN NOT" - AutomationId="btnReceteNotuPanelKapat" veya Name="KAPAT"

        Bu fonksiyon retry_with_popup_check içinde çağrılır.
        Popup kapatılırsa program kaldığı yerden devam eder (taskkill YAPMADAN).

        Returns:
            bool: En az bir popup kapatıldıysa True
        """
        kapatilan = False

        # 1. UYARIDIR popup kontrolü
        if self.uyaridir_popup_kapat():
            kapatilan = True
            logger.info("🔄 UYARIDIR popup kapatıldı, devam ediliyor...")

        # 2. REÇETE İÇİN NOT panel kontrolü
        if self.recete_notu_panelini_kapat():
            kapatilan = True
            logger.info("🔄 Reçete notu paneli kapatıldı, devam ediliyor...")

        return kapatilan

    def baglanti_kur(self, pencere_basligi="MEDULA", ilk_baglanti=False):
        """
        Medulla programına bağlan (handle cache ile optimize edilmiş - BotTak7'den)

        Args:
            pencere_basligi (str): Medulla penceresinin başlığı (MEDULA)
            ilk_baglanti (bool): İlk bağlantı mı? (pencere yerleştirme için)

        Returns:
            bool: Bağlantı başarılı ise True
        """
        try:
            # ✨ YENİ: Cache'lenmiş handle varsa ve pencere hala açıksa, direkt kullan (çok daha hızlı!)
            if self.medula_hwnd and not ilk_baglanti:
                try:
                    # Pencere hala açık mı kontrol et
                    if win32gui.IsWindow(self.medula_hwnd):
                        from pywinauto import Desktop
                        desktop = Desktop(backend="uia")
                        # Handle ile direkt bağlan (5-10x daha hızlı!)
                        self.main_window = desktop.window(handle=self.medula_hwnd)
                        logger.debug("✓ Cache'lenmiş pencere kullanıldı (hızlı)")
                        return True
                    else:
                        # Pencere kapalı, cache'i temizle
                        logger.debug("Cache'lenmiş pencere kapalı, yeniden aranacak")
                        self.medula_hwnd = None
                        self.medula_pid = None
                except Exception as e:
                    logger.debug(f"Cache'lenmiş pencere kullanılamadı: {e}")
                    self.medula_hwnd = None
                    self.medula_pid = None

            if ilk_baglanti:
                logger.debug(f"'{pencere_basligi}' aranıyor...")

            # Mevcut pencereye bağlan
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")

            # Önce pencereyi bul (UIAWrapper olarak)
            medula_hwnd = None
            for window in desktop.windows():
                try:
                    if pencere_basligi in window.window_text():
                        medula_hwnd = window.handle
                        break
                except Exception as e:
                    logger.debug(f"Pencere kontrolü hatası (devam ediliyor): {e}")

            if medula_hwnd is None:
                raise ElementNotFoundError(f"'{pencere_basligi}' bulunamadı")

            # WindowSpecification olarak al (child_window() için gerekli!)
            self.main_window = desktop.window(handle=medula_hwnd)

            # ✨ YENİ: Handle ve PID'yi cache'e kaydet (gelecekte hızlı bağlantı için)
            try:
                self.medula_hwnd = self.main_window.handle
                self.medula_pid = self.main_window.process_id()
                logger.debug(f"Pencere handle cache'lendi: {self.medula_hwnd}")
            except Exception as e:
                logger.debug(f"Handle cache'leme hatası (normal): {e}")

            if ilk_baglanti:
                logger.info("✓ MEDULA'ya bağlandı")

            # Pencereyi yerleştir (ayara göre - sadece ilk bağlantıda)
            if ilk_baglanti:
                try:
                    from medula_settings import get_medula_settings
                    medula_settings = get_medula_settings()
                    yerlesim = medula_settings.get("pencere_yerlesimi", "standart")

                    # Ekran çözünürlüğünü al
                    user32 = ctypes.windll.user32
                    screen_width = user32.GetSystemMetrics(0)
                    screen_height = user32.GetSystemMetrics(1)

                    # Yerleşim ayarına göre genişlik belirle
                    if yerlesim == "genis_medula":
                        # Geniş MEDULA: %80
                        medula_width = int(screen_width * 0.80)
                        logger.info(f"  Geniş MEDULA modu: %80 ({medula_width}px)")
                    else:
                        # Standart: %60
                        medula_width = int(screen_width * 0.60)
                        logger.info(f"  Standart mod: %60 ({medula_width}px)")

                    medula_x = 0  # Sola tam dayalı
                    medula_y = 0  # Üstten başla
                    medula_height = screen_height - 40  # Taskbar için alttan boşluk

                    # Pencere handle'ını al
                    medula_hwnd = self.main_window.handle

                    # Eğer maximize ise önce restore et
                    try:
                        placement = win32gui.GetWindowPlacement(medula_hwnd)
                        if placement[1] == win32con.SW_SHOWMAXIMIZED:
                            win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                            self.timed_sleep("pencere_restore")
                    except Exception as e:
                        logger.debug(f"Pencere restore hatası: {type(e).__name__}: {e}")

                    # Pencereyi direkt MoveWindow ile yerleştir
                    win32gui.MoveWindow(medula_hwnd, medula_x, medula_y, medula_width, medula_height, True)
                    self.timed_sleep("pencere_move")

                    # İkinci kez ayarla (bazı programlar ilk seferde tam oturmuyor)
                    win32gui.MoveWindow(medula_hwnd, medula_x, medula_y, medula_width, medula_height, True)

                    oran = "4/5" if yerlesim == "genis_medula" else "3/5"
                    logger.info(f"✓ MEDULA sol {oran}'e yerleşti ({medula_width}x{medula_height})")

                except Exception as e:
                    logger.error(f"Pencere boyutlandırılamadı: {e}", exc_info=True)

            return True

        except ElementNotFoundError:
            logger.error(f"'{pencere_basligi}' penceresi bulunamadı!")
            logger.info("Lütfen Medulla programının açık olduğundan emin olun.")
            return False
        except Exception as e:
            logger.error(f"Bağlantı hatası: {e}")
            return False

    def _get_cached_element(self, cache_key):
        """
        Cache'den element al

        Args:
            cache_key (str): Cache anahtarı

        Returns:
            Element veya None
        """
        if not self._cache_enabled:
            return None

        if cache_key in self._element_cache:
            try:
                element = self._element_cache[cache_key]
                # Element hala geçerli mi kontrol et
                _ = element.window_text()
                return element
            except Exception as e:
                # Element artık geçersiz, cache'den sil
                logger.debug(f"Cache element geçersiz ({cache_key}): {type(e).__name__}")
                del self._element_cache[cache_key]
                return None
        return None

    def _cache_element(self, cache_key, element):
        """
        Elementi cache'e ekle

        Args:
            cache_key (str): Cache anahtarı
            element: Cache'lenecek element
        """
        if self._cache_enabled and element is not None:
            self._element_cache[cache_key] = element

    def _clear_cache(self):
        """Tüm cache'i temizle"""
        self._element_cache.clear()
        logger.debug("🗑️ Element cache temizlendi")

    def _clear_cache_key(self, cache_key):
        """Belirli bir cache anahtarını temizle"""
        if cache_key in self._element_cache:
            del self._element_cache[cache_key]

    def ilac_butonuna_tikla(self):
        """
        İlaç butonuna tıkla (CACHE KAPALI - web kontrolü değişken)
        OPTIMIZE: child_window() ile direkt arama (hızlı), fallback ile güvenli

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.debug("İlaç butonu aranıyor...")

            # OPTIMIZE: Önce child_window() ile hızlı arama
            try:
                ilac_button = self.main_window.child_window(
                    auto_id="f:buttonIlacListesi",
                    control_type="Button"
                )
                if ilac_button.exists(timeout=0.5):  # Timeout artırıldı: 0.2 → 0.5
                    ilac_button.click_input()
                    logger.info("✓ İlaç butonuna tıklandı (Method 1: auto_id)")
                    self.timed_sleep("ilac_butonu")
                    return True
                else:
                    logger.debug("Method 1 (auto_id) başarısız: Element bulunamadı")
            except Exception as e:
                logger.debug(f"Method 1 (auto_id) hatası: {type(e).__name__}: {e}")

            # OPTIMIZE: Title ile hızlı arama
            try:
                ilac_button = self.main_window.child_window(
                    title="İlaç",
                    control_type="Button"
                )
                if ilac_button.exists(timeout=0.5):  # Timeout artırıldı: 0.2 → 0.5
                    try:
                        ilac_button.invoke()
                    except Exception as e1:
                        logger.debug(f"invoke() başarısız: {e1}, click() deneniyor")
                        try:
                            ilac_button.click()
                        except Exception as e2:
                            logger.debug(f"click() başarısız: {e2}, click_input() deneniyor")
                            ilac_button.click_input()

                    logger.info("✓ İlaç butonuna tıklandı (Method 2: title)")
                    self.timed_sleep("ilac_butonu")
                    return True
                else:
                    logger.debug("Method 2 (title) başarısız: Element bulunamadı")
            except Exception as e:
                logger.debug(f"Method 2 (title) hatası: {type(e).__name__}: {e}")

            # FALLBACK: Eski yöntem (descendants) - daha yavaş ama güvenli
            try:
                ilac_button = self.main_window.descendants(auto_id="f:buttonIlacListesi", control_type="Button")
                if ilac_button and len(ilac_button) > 0:
                    ilac_button[0].click_input()
                    logger.info("✓ İlaç butonuna tıklandı (Method 3: descendants auto_id)")
                    self.timed_sleep("ilac_butonu")
                    return True
                else:
                    logger.debug(f"Method 3 (descendants auto_id) başarısız: {len(ilac_button) if ilac_button else 0} element bulundu")
            except Exception as e:
                logger.debug(f"Method 3 (descendants auto_id) hatası: {type(e).__name__}: {e}")

            # FALLBACK: Name ile ara
            try:
                ilac_button = self.main_window.descendants(title="İlaç", control_type="Button")
                if ilac_button and len(ilac_button) > 0:
                    try:
                        ilac_button[0].invoke()
                    except Exception as e1:
                        logger.debug(f"invoke() başarısız: {e1}, click() deneniyor")
                        try:
                            ilac_button[0].click()
                        except Exception as e2:
                            logger.debug(f"click() başarısız: {e2}, click_input() deneniyor")
                            ilac_button[0].click_input()

                    logger.info("✓ İlaç butonuna tıklandı (Method 4: descendants title)")
                    self.timed_sleep("ilac_butonu")
                    return True
                else:
                    logger.debug(f"Method 4 (descendants title) başarısız: {len(ilac_button) if ilac_button else 0} element bulundu")
            except Exception as e:
                logger.debug(f"Method 4 (descendants title) hatası: {type(e).__name__}: {e}")

            logger.error("❌ İlaç butonu bulunamadı - Tüm 4 method başarısız oldu")
            return False

        except Exception as e:
            logger.error(f"❌ İlaç butonu hatası: {e}")
            return False

    def ilac_ekrani_yuklendi_mi(self, max_bekleme=3):
        """
        "Kullanılan İlaç Listesi" ekranının yüklenip yüklenmediğini kontrol et

        Args:
            max_bekleme: Maksimum bekleme süresi (saniye)

        Returns:
            bool: Ekran yüklendi ise True
        """
        try:
            baslangic = time.time()
            check_interval = 0.2  # Optimizasyon: Daha sık kontrol et

            while time.time() - baslangic < max_bekleme:
                # "Kullanılan İlaç Listesi" yazısını ara
                texts = self.main_window.descendants(control_type="Text")
                for text in texts:
                    try:
                        text_value = text.window_text()
                        if "Kullanılan İlaç Listesi" in text_value or "Kullanilan İlaç Listesi" in text_value:
                            gecen_sure = time.time() - baslangic
                            logger.info(f"✓ İlaç ekranı yüklendi ({gecen_sure:.2f}s)")
                            return True
                    except Exception as e:
                        logger.debug(f"İlaç ekranı kontrolü hatası: {type(e).__name__}")

                # Optimizasyon: Sabit kısa interval ile bekle
                time.sleep(check_interval)

            logger.warning("⚠️ İlaç ekranı yüklenemedi")
            return False

        except Exception as e:
            logger.error(f"Ekran kontrol hatası: {e}")
            return False

    def recete_not_penceresini_kapat(self, max_bekleme=0.1):  # Hızlandırıldı: 0.2 → 0.1
        """
        "REÇETE İÇİN NOT" penceresi varsa Kapat butonuna bas

        Args:
            max_bekleme: Maksimum bekleme süresi (saniye)

        Returns:
            bool: Pencere kapatıldıysa True, bulunamadıysa False
        """
        try:
            baslangic = time.time()
            anahtar = "REÇETE İÇİN NOT"

            def kapat_butonunu_bul_ve_tikla(kok):
                if kok is None:
                    return False
                try:
                    buttons = kok.descendants(title="KAPAT", control_type="Button")
                except Exception:
                    buttons = []
                for btn in buttons:
                    try:
                        try:
                            btn.invoke()
                        except Exception:
                            try:
                                btn.click()
                            except Exception:
                                btn.click_input()
                        logger.info("✓ REÇETE İÇİN NOT kapatıldı")
                        self.timed_sleep("popup_kapat")
                        return True
                    except Exception:
                        continue
                return False

            # Önce mevcut ana pencerede ara
            if self.main_window:
                try:
                    texts = self.main_window.descendants(control_type="Text")
                except Exception:
                    texts = []

                for text in texts:
                    try:
                        icerik = text.window_text() or ""
                    except Exception:
                        continue

                    if anahtar in icerik:
                        hedef = text
                        # Önce bulunduğu konteynerde ara
                        if kapat_butonunu_bul_ve_tikla(hedef.parent()):
                            return True
                        # 3 seviye yukarı çıkarak tekrar dene
                        ata = hedef.parent()
                        for _ in range(3):
                            try:
                                ata = ata.parent()
                            except Exception:
                                ata = None
                            if kapat_butonunu_bul_ve_tikla(ata):
                                return True
                        # Ana pencerede tekrar dene
                        if kapat_butonunu_bul_ve_tikla(self.main_window):
                            return True
                        # Hedef bulundu ama kapatılamadıysa tekrar arama yapma
                        return False

            # Gerekiyorsa kısa bir Desktop taraması yap
            kalan = max_bekleme - (time.time() - baslangic)
            if kalan <= 0:
                return False

            from pywinauto import Desktop
            try:
                windows = Desktop(backend="uia").windows()
            except Exception:
                return False

            for window in windows:
                try:
                    texts = window.descendants(control_type="Text")
                except Exception:
                    continue

                hedef_bulundu = False
                for text in texts:
                    try:
                        if anahtar in (text.window_text() or ""):
                            hedef_bulundu = True
                            break
                    except Exception:
                        continue

                if not hedef_bulundu:
                    continue

                if kapat_butonunu_bul_ve_tikla(window):
                    return True

            return False

        except Exception as e:
            logger.error(f"REÇETE İÇİN NOT kapatma hatası: {e}")
            return False

    def uyari_penceresini_kapat(self, max_bekleme=0.1):
        """
        "UYARIDIR" veya "GENEL MUAYENE TANISI" içeren uyarı pencerelerini "Kapat" butonuna tıklayarak kapat

        Args:
            max_bekleme: Maksimum bekleme süresi (saniye)

        Returns:
            bool: Pencere kapatıldıysa True, bulunamadıysa False
        """
        try:
            baslangic = time.time()
            anahtar_ifadeler = ["UYARIDIR", "GENEL MUAYENE TANISI VARDIR", "ICD EKLEME GEREKLİ"]

            def kapat_butonunu_bul_ve_tikla(kok):
                if kok is None:
                    return False
                try:
                    # "Kapat" butonunu ara
                    buttons = kok.descendants(title="Kapat", control_type="Button")
                except Exception:
                    buttons = []
                for btn in buttons:
                    try:
                        try:
                            btn.invoke()
                        except Exception:
                            try:
                                btn.click()
                            except Exception:
                                btn.click_input()
                        logger.info("✓ Uyarı penceresi kapatıldı")
                        self.timed_sleep("uyari_kapat")
                        return True
                    except Exception:
                        continue
                return False

            # Önce mevcut ana pencerede ara
            if self.main_window:
                try:
                    texts = self.main_window.descendants(control_type="Text")
                except Exception:
                    texts = []

                for text in texts:
                    try:
                        icerik = (text.window_text() or "").upper()
                    except Exception:
                        continue

                    # Anahtar ifadelerden birini içeriyorsa
                    if any(anahtar.upper() in icerik for anahtar in anahtar_ifadeler):
                        hedef = text
                        # Önce bulunduğu konteynerde ara
                        if kapat_butonunu_bul_ve_tikla(hedef.parent()):
                            return True
                        # Desktop taraması yap (WindowsForms penceresi için)
                        from pywinauto import Desktop
                        try:
                            windows = Desktop(backend="uia").windows()
                        except Exception:
                            return False

                        for window in windows:
                            try:
                                # WindowsForms class kontrolü
                                class_name = window.class_name()
                                if "WindowsForms10.Window" not in class_name:
                                    continue
                            except Exception as e:
                                logger.debug(f"class_name kontrolü hatası: {type(e).__name__}")
                                continue

                            # Pencere başlığında "UYARIDIR" var mı?
                            try:
                                window_text = window.window_text()
                                if "UYARI" not in window_text.upper():
                                    continue
                                logger.debug(f"  ✓ Genel Muayene penceresi bulundu (başlık: {window_text})")
                            except Exception as e:
                                logger.debug(f"window_text kontrolü hatası: {type(e).__name__}")
                                continue

                            # Kapat butonunu bul
                            try:
                                all_buttons = window.descendants(control_type="Button")
                                kapat_buttons = [
                                    btn for btn in all_buttons
                                    if (text := btn.window_text()) and "KAPAT" in text.upper()
                                ]
                                logger.debug(f"  → {len(kapat_buttons)} Kapat butonu bulundu")
                            except Exception:
                                kapat_buttons = []

                            if not kapat_buttons:
                                # Kapat butonu yoksa window.close() dene
                                try:
                                    window.close()
                                    logger.info("✓ Genel Muayene uyarısı kapatıldı (close)")
                                    self.timed_sleep("uyari_kapat")
                                    return True
                                except Exception as e:
                                    logger.debug(f"window.close() hatası: {type(e).__name__}")
                                continue

                            logger.info(f"⚠ Genel Muayene uyarısı bulundu! Kapatılıyor...")

                            for btn in kapat_buttons:
                                try:
                                    try:
                                        btn.invoke()
                                    except Exception:
                                        try:
                                            btn.click()
                                        except Exception:
                                            btn.click_input()
                                    logger.info("✓ Genel Muayene uyarısı kapatıldı")
                                    self.timed_sleep("uyari_kapat")
                                    return True
                                except Exception:
                                    continue

                        return False

            return False

        except Exception as e:
            logger.error(f"Genel Muayene uyarısı kapatma hatası: {e}")
            return False

    def laba_lama_uyarisini_kapat(self, max_bekleme=1.5, detayli_log=True):
        """
        LABA/LAMA uyarısını kapat - Sıralı yöntemler

        inspect.exe bilgileri (2025-12-01):
        - Pencere: class="#32770", WindowTitle="MEDULA 2.1.201.0 botan  (T)"
        - Tamam butonu: Name="Tamam", AutomationId="2", ClassName="Button"
        - Kapat (X) butonu: Name="Kapat", AutomationId="Close"

        Kapatma sırası:
        1. 3x ESC tuşu
        2. ENTER tuşu (ESC işe yaramazsa)
        3. Tamam butonu (ENTER işe yaramazsa)
        4. X (Kapat) butonu (Tamam işe yaramazsa)

        Args:
            max_bekleme: Maksimum bekleme süresi (saniye)
            detayli_log: Detaylı debug logları yaz (varsayılan True)

        Returns:
            bool: Uyarı kapatıldı ise True
        """
        try:
            from pywinauto import Desktop

            def laba_lama_penceresi_bul():
                """#32770 class'lı LABA/LAMA penceresi bul"""
                try:
                    desktop = Desktop(backend="uia")
                    windows = desktop.windows()

                    for window in windows:
                        try:
                            class_name = window.class_name()
                            if class_name != "#32770":
                                continue

                            # LABA/LAMA içeriği kontrol et
                            laba_ifadeler = ("LABA", "LAMA")
                            try:
                                texts = window.descendants()
                                for text in texts:
                                    try:
                                        text_content = text.window_text() or ""
                                        if any(ifade in text_content.upper() for ifade in laba_ifadeler):
                                            return window
                                    except Exception:
                                        continue
                            except Exception:
                                pass
                        except Exception:
                            continue
                except Exception:
                    pass
                return None

            if detayli_log:
                logger.debug(f"🔍 LABA/LAMA uyarısı kontrol ediliyor...")

            # Önce LABA/LAMA penceresi var mı kontrol et
            laba_pencere = laba_lama_penceresi_bul()
            if not laba_pencere:
                if detayli_log:
                    logger.debug("LABA/LAMA penceresi bulunamadı")
                return False  # Pencere yoksa False döndür

            logger.info("⚠ LABA/LAMA penceresi tespit edildi!")

            # YÖNTEM 1: 3x ESC tuşu
            logger.info("1️⃣ LABA/LAMA - 3x ESC gönderiliyor...")
            try:
                for i in range(3):
                    send_keys("{ESC}")
                    time.sleep(0.15)
                logger.info("✓ 3x ESC gönderildi")
                time.sleep(0.3)

                # Pencere kapandı mı kontrol et
                if not laba_lama_penceresi_bul():
                    logger.info("✓ LABA/LAMA kapatıldı (ESC ile)")
                    self.timed_sleep("laba_uyari")
                    return True
            except Exception as e:
                logger.debug(f"ESC hatası: {type(e).__name__}")

            # YÖNTEM 2: ENTER tuşu
            logger.info("2️⃣ LABA/LAMA - ENTER gönderiliyor...")
            try:
                laba_pencere = laba_lama_penceresi_bul()
                if laba_pencere:
                    try:
                        laba_pencere.set_focus()
                    except Exception:
                        pass
                    time.sleep(0.1)
                send_keys("{ENTER}")
                logger.info("✓ ENTER gönderildi")
                time.sleep(0.3)

                # Pencere kapandı mı kontrol et
                if not laba_lama_penceresi_bul():
                    logger.info("✓ LABA/LAMA kapatıldı (ENTER ile)")
                    self.timed_sleep("laba_uyari")
                    return True
            except Exception as e:
                logger.debug(f"ENTER hatası: {type(e).__name__}")

            # YÖNTEM 3: Tamam butonu (AutomationId="2")
            logger.info("3️⃣ LABA/LAMA - Tamam butonu aranıyor...")
            try:
                laba_pencere = laba_lama_penceresi_bul()
                if laba_pencere:
                    tamam_btn = laba_pencere.child_window(auto_id="2", control_type="Button")
                    if tamam_btn.exists(timeout=0.2):
                        try:
                            tamam_btn.click_input()
                        except Exception:
                            tamam_btn.click()
                        logger.info("✓ LABA/LAMA kapatıldı (Tamam butonu)")
                        self.timed_sleep("laba_uyari")
                        return True
            except Exception as e:
                logger.debug(f"Tamam butonu hatası: {type(e).__name__}")

            # YÖNTEM 4: X (Kapat) butonu (AutomationId="Close")
            logger.info("4️⃣ LABA/LAMA - X (Kapat) butonu aranıyor...")
            try:
                laba_pencere = laba_lama_penceresi_bul()
                if laba_pencere:
                    kapat_btn = laba_pencere.child_window(auto_id="Close", control_type="Button")
                    if kapat_btn.exists(timeout=0.2):
                        try:
                            kapat_btn.click_input()
                        except Exception:
                            kapat_btn.click()
                        logger.info("✓ LABA/LAMA kapatıldı (X butonu)")
                        self.timed_sleep("laba_uyari")
                        return True
            except Exception as e:
                logger.debug(f"Kapat butonu hatası: {type(e).__name__}")

            # Hiçbir yöntem işe yaramadı
            logger.warning("⚠ LABA/LAMA penceresi kapatılamadı (tüm yöntemler denendi)")
            return False

        except Exception as e:
            logger.error(f"LABA/LAMA uyarısı kontrol hatası: {e}", exc_info=True)
            return False

    def ilac_cakismasi_uyarisini_kapat(self, max_bekleme=1.5, detayli_log=True):
        """
        SADECE İlaç Çakışması uyarısını "Kapat" butonuna tıklayarak kapat
        inspect.exe'den: class="#32770", Kapat düğmesi

        Args:
            max_bekleme: Maksimum bekleme süresi (saniye)
            detayli_log: Detaylı debug logları yaz (varsayılan True)

        Returns:
            bool: Uyarı kapatıldı ise True
        """
        try:
            from pywinauto import Desktop

            if detayli_log:
                logger.debug(f"🔍 İlaç Çakışması uyarısı aranıyor (max {max_bekleme}s)...")

            baslangic = time.time()
            # İlaç Çakışması uyarısı için anahtar ifadeler
            ilac_cakismasi_ifadeler = ("İLAÇ ÇAKIŞMASI", "ILAC CAKISMASI", "ÇAKIŞMA")

            desktop = Desktop(backend="uia")

            while time.time() - baslangic < max_bekleme:
                try:
                    windows = desktop.windows()
                except Exception:
                    windows = []

                for window in windows:
                    try:
                        # class="#32770" kontrolü
                        class_name = window.class_name()
                        if class_name != "#32770":
                            continue
                    except Exception as e:
                        logger.debug(f"İlaç Çakışması class_name kontrolü hatası: {type(e).__name__}")
                        continue

                    # İçerikte İlaç Çakışması ifadesi var mı?
                    try:
                        texts = window.descendants()
                        ilac_cakismasi_bulundu = any(
                            any(ifade in (text.window_text() or "").upper() for ifade in ilac_cakismasi_ifadeler)
                            for text in texts
                        )
                        if not ilac_cakismasi_bulundu:
                            continue
                    except Exception as e:
                        logger.debug(f"İlaç Çakışması içerik kontrolü hatası: {type(e).__name__}")
                        continue

                    if detayli_log:
                        logger.debug(f"  ✓ İlaç Çakışması penceresi bulundu (class=#32770)")

                    logger.info(f"⚠ İlaç Çakışması uyarısı bulundu! Kapatılıyor...")

                    # OPTIMIZE: Önce child_window() ile TAMAM butonunu ara (inspect.exe'ye göre "Tamam" var)
                    try:
                        tamam_btn = window.child_window(title_re=".*[Tt][Aa][Mm][Aa][Mm].*", control_type="Button")
                        if tamam_btn.exists(timeout=0.3):
                            try:
                                tamam_btn.invoke()
                            except Exception as e:
                                logger.debug(f"İlaç Çakışması tamam_btn.invoke() hatası: {type(e).__name__}")
                                try:
                                    tamam_btn.click()
                                except Exception as e2:
                                    logger.debug(f"İlaç Çakışması tamam_btn.click() hatası: {type(e2).__name__}")
                                    tamam_btn.click_input()
                            logger.info(f"✓ İlaç Çakışması uyarısı kapatıldı (Tamam hızlı)")
                            self.timed_sleep("ilac_cakismasi_uyari")
                            return True
                    except Exception as e:
                        logger.debug(f"İlaç Çakışması TAMAM butonu arama hatası: {type(e).__name__}")

                    # OPTIMIZE: Alternatif - KAPAT butonu ara
                    try:
                        kapat_btn = window.child_window(title_re=".*[Kk][Aa][Pp][Aa][Tt].*", control_type="Button")
                        if kapat_btn.exists(timeout=0.3):
                            try:
                                kapat_btn.invoke()
                            except Exception as e:
                                logger.debug(f"İlaç Çakışması kapat_btn.invoke() hatası: {type(e).__name__}")
                                try:
                                    kapat_btn.click()
                                except Exception as e2:
                                    logger.debug(f"İlaç Çakışması kapat_btn.click() hatası: {type(e2).__name__}")
                                    kapat_btn.click_input()
                            logger.info(f"✓ İlaç Çakışması uyarısı kapatıldı (Kapat hızlı)")
                            self.timed_sleep("ilac_cakismasi_uyari")
                            return True
                    except Exception as e:
                        logger.debug(f"İlaç Çakışması KAPAT butonu arama hatası: {type(e).__name__}")

                    # FALLBACK: descendants() ile TAMAM veya KAPAT ara
                    try:
                        all_buttons = window.descendants(control_type="Button")
                        kapat_buttons = [
                            btn for btn in all_buttons
                            if (text := btn.window_text()) and (
                                "TAMAM" in text.upper() or
                                "KAPAT" in text.upper() or
                                "OK" in text.upper()
                            )
                        ]
                        if detayli_log:
                            logger.debug(f"  → {len(kapat_buttons)} Tamam/Kapat butonu bulundu (fallback)")

                        if kapat_buttons:
                            for btn in kapat_buttons:
                                try:
                                    try:
                                        btn.invoke()
                                    except Exception:
                                        try:
                                            btn.click()
                                        except Exception:
                                            btn.click_input()
                                    logger.info(f"✓ İlaç Çakışması uyarısı kapatıldı (Tamam/Kapat fallback)")
                                    self.timed_sleep("ilac_cakismasi_uyari")
                                    return True
                                except Exception:
                                    continue
                    except Exception:
                        pass

                    # Son çare: Pencereyi direkt kapat
                    if detayli_log:
                        logger.debug(f"  ⚠ Tamam/Kapat butonu bulunamadı, pencereyi kapatmaya çalışıyor...")
                    try:
                        window.close()
                        logger.info(f"✓ İlaç Çakışması uyarısı kapatıldı (close)")
                        self.timed_sleep("ilac_cakismasi_uyari")
                        return True
                    except Exception as e:
                        logger.debug(f"window.close() hatası (İlaç Çakışması): {type(e).__name__}")

                self.timed_sleep("popup_kapat")

            return False

        except Exception as e:
            logger.error(f"İlaç Çakışması uyarısı kontrol hatası: {e}", exc_info=True)
            return False

    def y_tusuna_tikla(self):
        """
        Y tuşuna tıkla (CACHE destekli) - OPTIMIZE: AutomationId ile arama

        UIElementInspector bilgileri (2 Aralık 2025):
        - Name: "Y"
        - AutomationId: "btnPrint"
        - ControlType: Button
        - ClassName: WindowsForms10.Window.b.app.0.134c08f_r8_ad1

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            # Önce cache'den kontrol et
            cached_button = self._get_cached_element("y_button")
            if cached_button:
                try:
                    cached_button.invoke()
                    logger.info("✓ Y butonuna tıklandı (cache)")
                    self.timed_sleep("y_butonu")
                    return True
                except Exception as e:
                    logger.debug(f"Cache'den Y butonu invoke() hatası: {type(e).__name__}")
                    self._clear_cache_key("y_button")

            # YÖNTEM 1: AutomationId ile arama (EN HIZLI - WinForms butonu)
            try:
                y_button = self.main_window.child_window(auto_id="btnPrint", control_type="Button")
                if y_button.exists(timeout=0.2):
                    self._cache_element("y_button", y_button)  # Cache'e ekle
                    try:
                        y_button.invoke()
                        logger.info("✓ Y butonuna tıklandı (AutomationId)")
                    except Exception as e:
                        logger.debug(f"Y butonu invoke() hatası: {type(e).__name__}")
                        try:
                            y_button.click()
                            logger.info("✓ Y butonuna tıklandı (click)")
                        except Exception as e2:
                            logger.debug(f"Y butonu click() hatası: {type(e2).__name__}")
                            y_button.click_input()
                            logger.info("✓ Y butonuna tıklandı (click_input)")

                    self.timed_sleep("y_butonu")
                    return True
            except Exception as e:
                logger.debug(f"Y butonu AutomationId arama hatası: {type(e).__name__}")

            # YÖNTEM 2: Name ile arama (FALLBACK)
            try:
                y_button = self.main_window.child_window(title="Y", control_type="Button")
                if y_button.exists(timeout=0.3):
                    self._cache_element("y_button", y_button)
                    try:
                        y_button.invoke()
                        logger.info("✓ Y butonuna tıklandı (Name)")
                    except Exception as e:
                        logger.debug(f"Y butonu Name invoke() hatası: {type(e).__name__}")
                        y_button.click_input()
                        logger.info("✓ Y butonuna tıklandı (Name click)")
                    self.timed_sleep("y_butonu")
                    return True
            except Exception as e:
                logger.debug(f"Y butonu Name arama hatası: {type(e).__name__}")

            # YÖNTEM 3: descendants() ile AutomationId araması (SON ÇARE)
            try:
                y_buttons = self.main_window.descendants(auto_id="btnPrint", control_type="Button")
                if y_buttons and len(y_buttons) > 0:
                    self._cache_element("y_button", y_buttons[0])
                    try:
                        y_buttons[0].invoke()
                        logger.info("✓ Y butonuna tıklandı (descendants)")
                    except Exception as e:
                        logger.debug(f"Y butonu descendants invoke() hatası: {type(e).__name__}")
                        try:
                            y_buttons[0].click()
                            logger.info("✓ Y butonuna tıklandı (descendants click)")
                        except Exception as e2:
                            logger.debug(f"Y butonu descendants click() hatası: {type(e2).__name__}")
                            y_buttons[0].click_input()
                            logger.info("✓ Y butonuna tıklandı (descendants click_input)")

                    self.timed_sleep("y_butonu")
                    return True
                else:
                    logger.warning("⚠️ Y butonu bulunamadı, ENTER tuşu gönderiliyor (laba/lama popup fallback)...")
                    try:
                        send_keys("{ENTER}")
                        self.timed_sleep("y_butonu")
                        logger.info("✓ ENTER tuşu gönderildi (Y butonu yerine)")
                        return True
                    except Exception as enter_err:
                        logger.error(f"ENTER tuşu gönderme hatası: {enter_err}")
                        return False
            except Exception as e:
                logger.error(f"Y butonu hatası: {e}")
                logger.warning("⚠️ Y butonu arama hatası, ENTER tuşu gönderiliyor...")
                try:
                    send_keys("{ENTER}")
                    self.timed_sleep("y_butonu")
                    logger.info("✓ ENTER tuşu gönderildi (Y butonu yerine)")
                    return True
                except Exception as enter_err:
                    logger.error(f"ENTER tuşu gönderme hatası: {enter_err}")
                    return False

        except Exception as e:
            logger.error(f"Y tıklama hatası: {e}")
            logger.warning("⚠️ Y butonu işlemi başarısız, ENTER tuşu gönderiliyor...")
            try:
                send_keys("{ENTER}")
                self.timed_sleep("y_butonu")
                logger.info("✓ ENTER tuşu gönderildi (Y butonu yerine)")
                return True
            except Exception as enter_err:
                logger.error(f"ENTER tuşu gönderme hatası: {enter_err}")
                return False

    def yeni_pencereyi_bul(self, pencere_basligi_iceren="İlaç Listesi"):
        """
        Yeni açılan pencereyi bul ve bağlan

        Args:
            pencere_basligi_iceren (str): Pencere başlığında aranacak kelime

        Returns:
            bool: Pencere bulundu ise True
        """
        try:
            from pywinauto import Desktop
            windows = Desktop(backend="uia").windows()

            for window in windows:
                try:
                    window_title = window.window_text()
                    if pencere_basligi_iceren in window_title:
                        self.main_window = window
                        return True
                except Exception as e:
                    logger.debug(f"Pencere başlığı kontrolü hatası: {type(e).__name__}")

            logger.warning(f"❌ '{pencere_basligi_iceren}' bulunamadı")
            return False

        except Exception as e:
            logger.error(f"Pencere arama hatası: {e}")
            return False

    def bizden_alinanlarin_sec_tusuna_tikla(self):
        """
        Bizden Alınmayanları Seç butonuna tıkla - OPTIMIZE: descendants() ile doğrudan arama

        Inspect.exe bilgileri (27 Kasım 2025):
        - AutomationId: "btnRaporlulariSec"
        - Name: "Bizden\nAlınmayanları Seç" (çok satırlı)
        - ControlType: Button
        - FrameworkId: "WinForm"
        - IsInvokePatternAvailable: true

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            # YÖNTEM 1: descendants() ile AutomationId araması (EN HIZLI - child_window hep başarısız)
            try:
                bizden_buttons = self.main_window.descendants(
                    auto_id="btnRaporlulariSec",
                    control_type="Button"
                )
                if bizden_buttons and len(bizden_buttons) > 0:
                    try:
                        bizden_buttons[0].invoke()
                        logger.info("✓ Alınmayanları seç (AutomationId)")
                        return True
                    except Exception:
                        bizden_buttons[0].click_input()
                        logger.info("✓ Alınmayanları seç (click)")
                        return True
            except Exception as e:
                logger.debug(f"descendants AutomationId hatası: {type(e).__name__}")

            # Eski FALLBACK: descendants() ile text arama (en son çare)
            try:
                buttons = self.main_window.descendants(control_type="Button")
                bizden_button = None

                for btn in buttons:
                    try:
                        btn_text = btn.window_text()
                        if "Alınmayanları Seç" in btn_text or "Alınanları Seç" in btn_text:
                            bizden_button = [btn]
                            break
                    except Exception as e:
                        logger.debug(f"Buton text kontrolü hatası: {type(e).__name__}")
                if bizden_button and len(bizden_button) > 0:
                    try:
                        bizden_button[0].invoke()
                    except Exception as e:
                        logger.debug(f"Bizden alınanlar fallback invoke() hatası: {type(e).__name__}")
                        try:
                            bizden_button[0].click()
                        except Exception as e2:
                            logger.debug(f"Bizden alınanlar fallback click() hatası: {type(e2).__name__}")
                            bizden_button[0].click_input()

                    logger.info("✓ Alınmayanları seç (fallback)")
                    return True
                else:
                    logger.warning("❌ Alınmayanları seç yok")
                    return False
            except Exception as e:
                logger.error(f"Buton arama hatası: {e}")
                return False

        except Exception as e:
            logger.error(f"Tıklama hatası: {e}")
            return False

    def textboxlara_122_yaz(self):
        """
        İlaç Listesi penceresindeki iki textbox'a "122" yaz

        KOORDİNAT KULLANMAZ - pywinauto native metodları kullanır
        Her çözünürlük ve pencere konumunda çalışır.

        UIElementInspector bilgileri (9 Aralık 2025):
        - Textbox 1 (- gün): ClassName: WindowsForms10.EDIT.app.0.134c08f_r8_ad1, ~27x14 boyut
        - Textbox 2 (+ gün): ClassName: WindowsForms10.EDIT.app.0.134c08f_r8_ad1, ~27x14 boyut
        - WindowTitle: "... İlaç Listesi" (hasta adı + İlaç Listesi)
        - AutomationId'ler DİNAMİK (her seferinde değişir)

        Tespit Yöntemi:
        1. İlaç Listesi penceresini bul
        2. ClassName içinde "EDIT" olan küçük Edit kontrollerini bul
        3. Y koordinatına göre sırala (üstten alta)
        4. İlk ikisine sırayla yaz (native click/type_keys ile)

        Returns:
            bool: Her iki textbox'a da yazma başarılı ise True
        """
        from pywinauto.keyboard import send_keys
        from pywinauto import Desktop

        try:
            # ===== TEXTBOX 122 AYARLARI KONTROLÜ =====
            textbox_ayar = self._insan_davranisi_ayarlar.get("textbox_122", {}) if self._insan_modu_aktif else {}

            # Yazma devre dışı mı?
            if textbox_ayar.get("yazmayi_devre_disi_birak", False):
                logger.info("📝 Textbox yazma devre dışı (ayarlardan)")
                return True

            # Özel değer kullan mı?
            if textbox_ayar.get("ozel_deger_kullan", False):
                deger_1 = textbox_ayar.get("deger_1", "122")
                deger_2 = textbox_ayar.get("deger_2", "122")
                logger.info(f"📝 Textbox'lara özel değerler yazılıyor: '{deger_1}' ve '{deger_2}'")
            else:
                deger_1 = "122"
                deger_2 = "122"
                logger.info("📝 Textbox'lara 122 yazılıyor (koordinatsız)...")

            # ===== İLAÇ LİSTESİ PENCERESİNİ DESKTOP'TAN BUL =====
            ilac_listesi_window = None
            try:
                windows = Desktop(backend="uia").windows()
                for window in windows:
                    try:
                        window_title = window.window_text()
                        if "İlaç Listesi" in window_title:
                            ilac_listesi_window = window
                            logger.info(f"  → İlaç Listesi penceresi: {window_title}")
                            break
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"  Desktop arama hatası: {type(e).__name__}")

            if not ilac_listesi_window:
                logger.warning("❌ İlaç Listesi penceresi bulunamadı, main_window kullanılıyor")
                ilac_listesi_window = self.main_window

            # ===== EDİT KONTROLLERİNİ BUL (SADECE KÜÇÜK OLANLAR) =====
            # ClassName içinde "EDIT" olanları bul - bu daha güvenilir
            edit_controls = []
            try:
                all_edits = ilac_listesi_window.descendants(control_type="Edit")
                for edit in all_edits:
                    try:
                        # ClassName kontrolü - WindowsForms10.EDIT içermeli
                        class_name = ""
                        try:
                            class_name = edit.element_info.class_name or ""
                        except Exception:
                            pass

                        if "EDIT" not in class_name.upper():
                            continue

                        # Boyut kontrolü - küçük textbox'lar (width < 80, height < 40)
                        rect = edit.rectangle()
                        width = rect.width()
                        height = rect.height()

                        if width > 80 or height > 40:
                            continue

                        # Bu bir hedef textbox
                        edit_controls.append({
                            'element': edit,
                            'top': rect.top,
                            'width': width,
                            'height': height,
                            'class_name': class_name
                        })
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"  Edit arama hatası: {type(e).__name__}")

            if not edit_controls:
                logger.warning("❌ EDIT textbox bulunamadı")
                return False

            logger.info(f"  → {len(edit_controls)} küçük EDIT textbox bulundu")

            # ===== Y KOORDİNATINA GÖRE SIRALA (üstten alta) =====
            edit_controls.sort(key=lambda x: x['top'])

            # Log: Bulunan textbox'lar
            for i, info in enumerate(edit_controls[:4]):  # İlk 4'ü göster
                logger.info(f"    Edit[{i}]: Y={info['top']}, size=({info['width']}x{info['height']})")

            # ===== İLK İKİ TEXTBOX'A NATIVE METODLARLA YAZ =====
            basarili = 0
            degerleri = [deger_1, deger_2]

            for i in range(min(2, len(edit_controls))):
                edit_info = edit_controls[i]
                edit_element = edit_info['element']
                yazilacak_deger = degerleri[i]

                logger.info(f"  → Textbox {i+1} (Y:{edit_info['top']}) yazılıyor...")

                try:
                    # YÖNTEM 1: Native set_focus + type_keys (koordinatsız)
                    try:
                        edit_element.set_focus()
                        time.sleep(0.1)
                        edit_element.type_keys("^a", with_spaces=True)  # Ctrl+A ile seç
                        time.sleep(0.05)
                        edit_element.type_keys(yazilacak_deger, with_spaces=True)
                        time.sleep(0.1)
                        basarili += 1
                        logger.info(f"  ✓ Textbox {i+1}: '{yazilacak_deger}' yazıldı (native)")
                        continue
                    except Exception as e1:
                        logger.debug(f"    Native type_keys hatası: {type(e1).__name__}")

                    # YÖNTEM 2: click_input + send_keys (relative click)
                    try:
                        edit_element.click_input()
                        time.sleep(0.1)
                        send_keys("^a")
                        time.sleep(0.05)
                        send_keys(yazilacak_deger)
                        time.sleep(0.1)
                        basarili += 1
                        logger.info(f"  ✓ Textbox {i+1}: '{yazilacak_deger}' yazıldı (click_input)")
                        continue
                    except Exception as e2:
                        logger.debug(f"    click_input hatası: {type(e2).__name__}")

                    # YÖNTEM 3: set_edit_text (WinForms için)
                    try:
                        # Önce mevcut metni temizle
                        edit_element.set_edit_text("")
                        time.sleep(0.05)
                        edit_element.set_edit_text(yazilacak_deger)
                        time.sleep(0.1)
                        basarili += 1
                        logger.info(f"  ✓ Textbox {i+1}: '{yazilacak_deger}' yazıldı (set_edit_text)")
                        continue
                    except Exception as e3:
                        logger.debug(f"    set_edit_text hatası: {type(e3).__name__}")

                except Exception as e:
                    logger.warning(f"  ❌ Textbox {i+1} hatası: {type(e).__name__}: {e}")

            # ===== SONUÇ DEĞERLENDİRME =====
            if basarili >= 2:
                logger.info(f"✓ Her iki textbox'a '{deger_1}'/'{deger_2}' yazıldı")
                return True
            elif basarili == 1:
                # Sadece biri yazıldı, TAB ile diğerine geç
                logger.warning(f"⚠ Sadece {basarili}/2 textbox'a yazıldı, TAB deneniyor...")
                try:
                    send_keys("{TAB}")
                    time.sleep(0.1)
                    send_keys("^a")
                    time.sleep(0.05)
                    send_keys(deger_2)
                    time.sleep(0.1)
                    logger.info(f"  ✓ Textbox 2: '{deger_2}' yazıldı (TAB ile)")
                    return True
                except Exception:
                    pass
            else:
                # Hiçbiri yazılamadı, TAB yöntemi dene
                logger.warning("⚠ Native yöntemler başarısız, TAB yöntemi deneniyor...")
                if len(edit_controls) >= 1:
                    return self._textbox_122_native_tab(edit_controls[0]['element'], deger_1, deger_2)

            logger.error("❌ Textbox'lara yazılamadı")
            return False

        except Exception as e:
            logger.error(f"Textbox yazma hatası: {type(e).__name__}: {e}")
            return False

    def _textbox_122_native_tab(self, ilk_edit_element, deger_1="122", deger_2="122"):
        """
        TAB tuşu ile iki textbox'a değer yaz (native element kullanarak)
        KOORDİNAT KULLANMAZ
        """
        from pywinauto.keyboard import send_keys

        try:
            logger.info("  → TAB yöntemi (native): İlk textbox'a odaklanılıyor...")

            # İlk textbox'a odaklan
            try:
                ilk_edit_element.set_focus()
                time.sleep(0.1)
            except Exception:
                ilk_edit_element.click_input()
                time.sleep(0.1)

            # İlk textbox'a değer yaz
            send_keys("^a")
            time.sleep(0.05)
            send_keys(deger_1)
            time.sleep(0.1)
            logger.info(f"  ✓ Textbox 1: '{deger_1}' yazıldı")

            # TAB ile ikinci textbox'a geç
            send_keys("{TAB}")
            time.sleep(0.1)

            # İkinci textbox'a değer yaz
            send_keys("^a")
            time.sleep(0.05)
            send_keys(deger_2)
            time.sleep(0.1)
            logger.info(f"  ✓ Textbox 2: '{deger_2}' yazıldı (TAB ile)")

            return True

        except Exception as e:
            logger.error(f"TAB yöntemi (native) hatası: {type(e).__name__}: {e}")
            return False

    def _textboxlara_122_yaz_eski(self):
        """
        ESKİ KOORDİNAT TABANLI YÖNTEM - KULLANILMIYOR
        Farklı çözünürlük/pencere konumunda çalışmaz!
        """
        from pywinauto.keyboard import send_keys
        from pywinauto import Desktop
        import ctypes

        try:
            # ===== TEXTBOX 122 AYARLARI KONTROLÜ =====
            textbox_ayar = self._insan_davranisi_ayarlar.get("textbox_122", {}) if self._insan_modu_aktif else {}

            # Yazma devre dışı mı?
            if textbox_ayar.get("yazmayi_devre_disi_birak", False):
                logger.info("📝 Textbox yazma devre dışı (ayarlardan)")
                return True

            # Özel değer kullan mı?
            if textbox_ayar.get("ozel_deger_kullan", False):
                deger_1 = textbox_ayar.get("deger_1", "122")
                deger_2 = textbox_ayar.get("deger_2", "122")
                logger.info(f"📝 Textbox'lara özel değerler yazılıyor: '{deger_1}' ve '{deger_2}'")
            else:
                deger_1 = "122"
                deger_2 = "122"
                logger.info("📝 Textbox'lara 122 yazılıyor...")

            # ===== İLAÇ LİSTESİ PENCERESİNİ DESKTOP'TAN BUL =====
            ilac_listesi_window = None
            try:
                windows = Desktop(backend="uia").windows()
                for window in windows:
                    try:
                        window_title = window.window_text()
                        if "İlaç Listesi" in window_title:
                            ilac_listesi_window = window
                            logger.info(f"  → İlaç Listesi penceresi: {window_title}")
                            break
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"  Desktop arama hatası: {type(e).__name__}")

            if not ilac_listesi_window:
                logger.warning("❌ İlaç Listesi penceresi bulunamadı, main_window kullanılıyor")
                ilac_listesi_window = self.main_window

            # ===== EDİT KONTROLLERİNİ BUL VE KOORDİNATLARI HEMEN KAYDET =====
            edit_controls = ilac_listesi_window.descendants(control_type="Edit")

            if not edit_controls:
                logger.warning("❌ Edit kontrolleri bulunamadı")
                return False

            logger.info(f"  → {len(edit_controls)} Edit kontrolü bulundu")

            # ===== TÜM EDİT BİLGİLERİNİ HEMEN TOPLA VE SABİT KOORDİNATLARI KAYDET =====
            # (rectangle() çağrısı bir kez yapılıp kaydediliyor)
            # BOYUT FİLTRESİ: Sadece küçük sayısal giriş kutularını al (width < 60, height < 30)
            # Bu sayede ComboBox'ların Edit kısımları ve büyük metin alanları filtrelenir
            edit_bilgileri = []
            for idx, edit in enumerate(edit_controls):
                try:
                    rect = edit.rectangle()
                    # Koordinatları HEMEN sayısal değer olarak kaydet
                    left = int(rect.left)
                    top = int(rect.top)
                    width = int(rect.width())
                    height = int(rect.height())
                    center_x = left + (width // 2)
                    center_y = top + (height // 2)

                    text = ""
                    try:
                        text = edit.window_text() if hasattr(edit, 'window_text') else ""
                    except Exception:
                        pass

                    logger.info(f"    Edit[{idx}]: Y={top}, size=({width}x{height}), center=({center_x},{center_y}), text='{text}'")

                    # BOYUT FİLTRESİ: Sadece küçük textbox'ları kabul et
                    # İkinci textbox: 27x14 boyutunda (inspect.exe raporundan)
                    # Büyük Edit'ler (ComboBox Edit, metin alanları) genellikle > 60 width
                    if width > 80 or height > 40:
                        logger.info(f"      → Atlandı (çok büyük: {width}x{height})")
                        continue

                    bilgi = {
                        'idx': idx,
                        'top': top,
                        'left': left,
                        'width': width,
                        'height': height,
                        'center_x': center_x,
                        'center_y': center_y,
                        'text': text
                    }
                    edit_bilgileri.append(bilgi)
                except Exception as e:
                    logger.debug(f"Edit[{idx}] bilgi hatası: {type(e).__name__}")

            if len(edit_bilgileri) < 2:
                logger.warning(f"❌ Boyut filtresi sonrası yeterli Edit yok: {len(edit_bilgileri)}")
                # Fallback: Boyut filtresi olmadan tekrar dene
                logger.info("  → Fallback: Boyut filtresi kaldırılarak tekrar deneniyor...")
                edit_bilgileri_fallback = []
                for idx, edit in enumerate(edit_controls):
                    try:
                        rect = edit.rectangle()
                        left = int(rect.left)
                        top = int(rect.top)
                        width = int(rect.width())
                        height = int(rect.height())
                        center_x = left + (width // 2)
                        center_y = top + (height // 2)
                        text = ""
                        try:
                            text = edit.window_text() if hasattr(edit, 'window_text') else ""
                        except Exception:
                            pass
                        bilgi = {
                            'idx': idx, 'top': top, 'left': left, 'width': width, 'height': height,
                            'center_x': center_x, 'center_y': center_y, 'text': text
                        }
                        edit_bilgileri_fallback.append(bilgi)
                    except Exception:
                        pass

                if len(edit_bilgileri_fallback) >= 1:
                    # Y'ye göre sırala ve TAB yöntemi kullan
                    edit_bilgileri_fallback.sort(key=lambda x: x['top'])
                    logger.info(f"  → Fallback: {len(edit_bilgileri_fallback)} Edit bulundu, TAB yöntemi kullanılacak")
                    return self._textbox_122_tab_yontemi_v2(edit_bilgileri_fallback[0], deger_1, deger_2)

                if len(edit_bilgileri) == 1:
                    return self._textbox_122_tab_yontemi_v2(edit_bilgileri[0], deger_1, deger_2)
                return False

            # ===== Y KOORDİNATINA GÖRE SIRALA =====
            edit_bilgileri.sort(key=lambda x: x['top'])

            # ===== FARKLI KOORDİNATLARI OLAN İLK 2 EDİT'İ SEÇ =====
            # (Aynı koordinatta olanları atla)
            secilen_editler = []
            kullanilan_koordinatlar = set()

            for bilgi in edit_bilgileri:
                koordinat_key = (bilgi['center_x'], bilgi['center_y'])
                if koordinat_key not in kullanilan_koordinatlar:
                    secilen_editler.append(bilgi)
                    kullanilan_koordinatlar.add(koordinat_key)
                    if len(secilen_editler) >= 2:
                        break

            logger.info(f"  → {len(secilen_editler)} farklı koordinatta Edit seçildi")

            for i, bilgi in enumerate(secilen_editler):
                logger.info(f"    Seçilen Edit {i+1}: Y={bilgi['top']}, size=({bilgi['width']}x{bilgi['height']}), center=({bilgi['center_x']},{bilgi['center_y']})")

            if len(secilen_editler) < 2:
                logger.warning("⚠ İki farklı koordinatta Edit bulunamadı, TAB yöntemi kullanılacak")
                return self._textbox_122_tab_yontemi_v2(secilen_editler[0] if secilen_editler else edit_bilgileri[0], deger_1, deger_2)

            # İki Edit'in Y koordinatları farklı mı kontrol et
            y1 = secilen_editler[0]['top']
            y2 = secilen_editler[1]['top']
            logger.info(f"  → Y koordinatları: {y1} vs {y2} (fark: {abs(y1-y2)} piksel)")

            if abs(y1 - y2) < 10:
                logger.warning(f"⚠ İki Edit'in Y koordinatları çok yakın: {y1} vs {y2}")
                return self._textbox_122_tab_yontemi_v2(secilen_editler[0], deger_1, deger_2)

            # ===== HER İKİ TEXTBOX'A SABİT KOORDİNATLAR İLE TIKLA VE YAZ =====
            basarili = 0
            for i, bilgi in enumerate(secilen_editler[:2]):
                center_x = bilgi['center_x']
                center_y = bilgi['center_y']
                logger.info(f"  → Textbox {i+1} (Y:{bilgi['top']}) tıklanıyor: ({center_x}, {center_y})")

                try:
                    # Fare pozisyonunu ayarla
                    ctypes.windll.user32.SetCursorPos(center_x, center_y)
                    time.sleep(0.1)  # OPT: 0.2 → 0.1

                    # Sol tık
                    ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
                    time.sleep(0.03)  # OPT: 0.05 → 0.03
                    ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
                    time.sleep(0.15)  # OPT: 0.3 → 0.15

                    # Tüm metni seç ve yaz
                    send_keys("^a")
                    time.sleep(0.08)  # OPT: 0.15 → 0.08
                    yazilacak_deger = deger_1 if i == 0 else deger_2
                    send_keys(yazilacak_deger)
                    time.sleep(0.15)  # OPT: 0.3 → 0.15

                    logger.info(f"  ✓ Textbox {i+1}: '{yazilacak_deger}' yazıldı (koordinat: {center_x},{center_y})")
                    basarili += 1

                except Exception as e:
                    logger.warning(f"  ❌ Textbox {i+1} hatası: {type(e).__name__}: {e}")

            if basarili >= 2:
                logger.info(f"✓ Her iki textbox'a '{deger_1}'/'{deger_2}' yazıldı")
                return True
            elif basarili >= 1:
                logger.warning(f"⚠ Sadece {basarili}/2 textbox'a yazıldı, TAB deneniyor...")
                try:
                    send_keys("{TAB}")
                    time.sleep(0.15)  # OPT: 0.25 → 0.15
                    send_keys("^a")
                    time.sleep(0.08)  # OPT: 0.15 → 0.08
                    send_keys(deger_2)
                    time.sleep(0.1)  # OPT: 0.2 → 0.1
                    logger.info(f"  ✓ Textbox 2: '{deger_2}' yazıldı (TAB ile)")
                    return True
                except Exception:
                    pass
                return True
            else:
                logger.error("❌ Hiçbir textbox'a yazılamadı")
                return False

        except Exception as e:
            logger.error(f"Textbox yazma hatası: {e}")
            return False

    def _textbox_122_tab_yontemi(self, ilk_edit_tuple):
        """TAB tuşu ile iki textbox'a 122 yaz"""
        from pywinauto.keyboard import send_keys
        import ctypes

        try:
            y_pos, rect, edit, handle = ilk_edit_tuple
            center_x = rect.left + (rect.width() // 2)
            center_y = rect.top + (rect.height() // 2)

            logger.info(f"  → TAB yöntemi: İlk textbox (Y:{y_pos})")

            # İlk textbox'a tıkla
            ctypes.windll.user32.SetCursorPos(center_x, center_y)
            time.sleep(0.15)
            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
            time.sleep(0.03)
            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
            time.sleep(0.25)

            # İlk textbox'a 122 yaz
            send_keys("^a")
            time.sleep(0.1)
            send_keys("122")
            time.sleep(0.25)
            logger.info("  ✓ Textbox 1: 122 yazıldı")

            # TAB ile ikinci textbox'a geç
            send_keys("{TAB}")
            time.sleep(0.25)

            # İkinci textbox'a 122 yaz
            send_keys("^a")
            time.sleep(0.1)
            send_keys("122")
            time.sleep(0.2)
            logger.info("  ✓ Textbox 2: 122 yazıldı (TAB ile)")

            return True

        except Exception as e:
            logger.error(f"TAB yöntemi hatası: {e}")
            return False

    def _textbox_122_tab_yontemi_v2(self, ilk_edit_bilgi, deger_1="122", deger_2="122"):
        """TAB tuşu ile iki textbox'a değer yaz (dict format)"""
        from pywinauto.keyboard import send_keys
        import ctypes

        try:
            center_x = ilk_edit_bilgi['center_x']
            center_y = ilk_edit_bilgi['center_y']

            logger.info(f"  → TAB yöntemi v2: İlk textbox (Y:{ilk_edit_bilgi['top']})")

            # İlk textbox'a tıkla
            ctypes.windll.user32.SetCursorPos(center_x, center_y)
            time.sleep(0.1)  # OPT: 0.2 → 0.1
            ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
            time.sleep(0.03)  # OPT: 0.05 → 0.03
            ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
            time.sleep(0.15)  # OPT: 0.3 → 0.15

            # İlk textbox'a değer yaz
            send_keys("^a")
            time.sleep(0.08)  # OPT: 0.15 → 0.08
            send_keys(deger_1)
            time.sleep(0.15)  # OPT: 0.3 → 0.15
            logger.info(f"  ✓ Textbox 1: '{deger_1}' yazıldı")

            # TAB ile ikinci textbox'a geç
            send_keys("{TAB}")
            time.sleep(0.15)  # OPT: 0.3 → 0.15

            # İkinci textbox'a değer yaz
            send_keys("^a")
            time.sleep(0.08)  # OPT: 0.15 → 0.08
            send_keys(deger_2)
            time.sleep(0.12)  # OPT: 0.25 → 0.12
            logger.info(f"  ✓ Textbox 2: '{deger_2}' yazıldı (TAB ile)")

            return True

        except Exception as e:
            logger.error(f"TAB yöntemi v2 hatası: {e}")
            return False

    def ilac_secimi_ve_takip_et(self):
        """
        Yeni ilaç seçimi akışı - checkbox kontrolü YOK

        Adımlar:
        1. Textbox'lara "122" yaz
        2. "Bizden Alınmayanları Seç" butonuna tıkla
        3. "Seçim satır 1"e sağ tıkla
        4. "Takip Et" menü öğesine tıkla

        Returns:
            tuple: (bool: başarılı mı, int: takip edilen ilaç sayısı)
        """
        try:
            # 1. Textbox'lara "122" yaz
            if not self.textboxlara_122_yaz():
                logger.warning("⚠ Textbox'lara yazılamadı, devam ediliyor...")

            time.sleep(0.1)  # Kısa bekleme

            # 2. "Bizden Alınmayanları Seç" butonuna tıkla
            if not self.bizden_alinanlarin_sec_tusuna_tikla():
                logger.error("❌ Bizden Alınmayanları Seç butonu tıklanamadı")
                return (False, 0)

            time.sleep(0.3)  # Seçim için kısa bekleme

            # 3-4. Sağ tıkla ve "Takip Et"
            if not self.ilk_ilaca_sag_tik_ve_takip_et():
                logger.error("❌ Takip Et tıklanamadı")
                return (False, 0)

            # Takip edilen ilaç sayısını say
            try:
                cells = self.main_window.descendants(control_type="DataItem")
                takip_sayisi = sum(1 for cell in cells if "Seçim satır" in cell.window_text())
            except Exception:
                takip_sayisi = 1

            logger.info(f"✓ İlaç seçimi ve takip tamamlandı ({takip_sayisi} ilaç)")
            return (True, takip_sayisi)

        except Exception as e:
            logger.error(f"İlaç seçimi hatası: {e}")
            return (False, 0)

    def ilac_secili_mi_kontrol(self):
        """
        İlaçlardan herhangi biri seçili mi kontrol et

        Returns:
            tuple: (bool: En az 1 ilaç seçili ise True, int: seçili ilaç sayısı)
        """
        try:
            # Tüm DataItem'ları bul
            cells = self.main_window.descendants(control_type="DataItem")

            secili_sayisi = 0
            toplam_ilac = 0

            for cell in cells:
                try:
                    cell_name = cell.window_text()
                    if "Seçim satır" in cell_name:
                        toplam_ilac += 1

                        # Farklı yöntemlerle seçilim kontrolü
                        secili = False

                        # Yöntem 1: Value özelliğini kontrol et
                        try:
                            value = cell.legacy_properties().get('Value', '')
                            if value == "Seçili":
                                secili = True
                        except Exception as e:
                            logger.debug(f"Operation failed: {type(e).__name__}")

                        # Yöntem 2: Toggle state
                        try:
                            toggle_state = cell.get_toggle_state()
                            if toggle_state == 1:
                                secili = True
                        except Exception as e:
                            logger.debug(f"Operation failed: {type(e).__name__}")

                        if secili:
                            secili_sayisi += 1

                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            logger.info(f"→ {secili_sayisi}/{toplam_ilac} ilaç seçili")

            return (secili_sayisi > 0, secili_sayisi)

        except Exception as e:
            logger.error(f"İlaç seçilim kontrolü hatası: {e}")
            return (False, 0)

    def ilk_ilaca_sag_tik_ve_takip_et(self):
        """
        İlk ilaca (Seçim satır 1) sağ tıkla ve "Takip Et" seç

        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            logger.info("İlk ilaca sağ tıklama yapılıyor...")

            # "Seçim satır 1" hücresini bul
            cells = self.main_window.descendants(control_type="DataItem")

            ilk_ilac = None
            for cell in cells:
                try:
                    cell_name = cell.window_text()
                    if "Seçim satır 1" in cell_name:
                        ilk_ilac = cell
                        logger.info(f"İlk ilaç bulundu: {cell_name}")
                        break
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            if ilk_ilac is None:
                logger.error("İlk ilaç bulunamadı")
                return False

            # Sağ tık yap
            ilk_ilac.click_input(button='right')
            self.timed_sleep("sag_tik")

            # "Takip Et" menü öğesini bul ve tıkla
            try:
                # Menü öğelerini bul
                menu_items = self.main_window.descendants(control_type="MenuItem")

                for item in menu_items:
                    try:
                        item_name = item.window_text()
                        if "Takip Et" in item_name:
                            item.click_input()
                            logger.info("✓ Takip Et tıklandı")
                            self.timed_sleep("takip_et")
                            return True
                    except Exception as e:
                        logger.debug(f"Operation failed: {type(e).__name__}")

                logger.error("❌ Takip Et bulunamadı")
                return False

            except Exception as e:
                logger.error(f"Menü öğesi arama hatası: {e}")
                return False

        except Exception as e:
            logger.error(f"Sağ tıklama hatası: {e}")
            return False

    def ilac_listesi_penceresini_kapat(self):
        """
        İlaç Listesi penceresini kapat - Geliştirilmiş WindowsForms pencere kapatma

        UIElementInspector bilgileri (1 Aralık 2025):
        - WindowTitle: "... İlaç Listesi" (hasta adı + İlaç Listesi)
        - WindowClassName: WindowsForms10.Window.8.app.0.134c08f_r8_ad1
        - Close Button: AutomationId="Close", Name="Kapat", ControlType=Button
        - BoundingRect: Tüm pencere boyutu (başlık çubuğu close butonu)

        Returns:
            bool: Kapatma başarılı ise True
        """
        from pywinauto.keyboard import send_keys

        try:
            logger.info("🔍 İlaç Listesi penceresi kapatılıyor...")

            # YÖNTEM 1: Pencereyi doğrudan close() ile kapat (EN ETKİLİ - WindowsForms için)
            try:
                window_title = self.main_window.window_text()
                if "İlaç Listesi" in window_title:
                    logger.info(f"  → Pencere bulundu: {window_title}")
                    self.main_window.close()
                    logger.info("✓ Pencere kapatıldı (close())")
                    self.timed_sleep("kapat_butonu")
                    return True
            except Exception as close_err:
                logger.debug(f"close() hatası: {type(close_err).__name__}: {close_err}")

            # YÖNTEM 2: Alt+F4 ile kapat (WindowsForms pencereleri için etkili)
            try:
                self.main_window.set_focus()
                time.sleep(0.1)
                send_keys("%{F4}")  # Alt+F4
                logger.info("✓ Pencere kapatıldı (Alt+F4)")
                self.timed_sleep("kapat_butonu")
                return True
            except Exception as altf4_err:
                logger.debug(f"Alt+F4 hatası: {type(altf4_err).__name__}")

            # YÖNTEM 3: ESC tuşu ile kapat (dialog pencereleri için)
            try:
                self.main_window.set_focus()
                time.sleep(0.1)
                send_keys("{ESC}")
                logger.info("✓ Pencere kapatıldı (ESC)")
                self.timed_sleep("kapat_butonu")
                return True
            except Exception as esc_err:
                logger.debug(f"ESC hatası: {type(esc_err).__name__}")

            # YÖNTEM 4: child_window() ile AutomationId araması
            try:
                kapat_btn = self.main_window.child_window(
                    auto_id="Close",
                    control_type="Button"
                )
                if kapat_btn.exists(timeout=0.2):
                    try:
                        kapat_btn.invoke()
                        logger.info("✓ Pencere kapatıldı (child_window)")
                        self.timed_sleep("kapat_butonu")
                        return True
                    except Exception as inv_err:
                        logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                        try:
                            kapat_btn.click_input()
                            logger.info("✓ Pencere kapatıldı (click_input)")
                            self.timed_sleep("kapat_butonu")
                            return True
                        except Exception as clk_err:
                            logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"child_window AutomationId hatası: {type(e).__name__}")

            # YÖNTEM 5: child_window() ile Name araması (FALLBACK)
            try:
                kapat_btn = self.main_window.child_window(
                    title="Kapat",
                    control_type="Button"
                )
                if kapat_btn.exists(timeout=0.2):
                    try:
                        kapat_btn.invoke()
                        logger.info("✓ Pencere kapatıldı (Name)")
                        self.timed_sleep("kapat_butonu")
                        return True
                    except Exception as inv_err:
                        logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                        try:
                            kapat_btn.click_input()
                            logger.info("✓ Pencere kapatıldı (click_input - Name)")
                            self.timed_sleep("kapat_butonu")
                            return True
                        except Exception as clk_err:
                            logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"child_window Name hatası: {type(e).__name__}")

            # YÖNTEM 6: descendants() ile son çare (spesifik AutomationId ile)
            logger.warning("Kapat: önceki yöntemler başarısız, descendants() deneniyor...")
            try:
                kapat_buttons = self.main_window.descendants(
                    auto_id="Close",
                    control_type="Button"
                )
                if kapat_buttons and len(kapat_buttons) > 0:
                    try:
                        kapat_buttons[0].invoke()
                        logger.info("✓ Pencere kapatıldı (descendants)")
                        self.timed_sleep("kapat_butonu")
                        return True
                    except Exception:
                        kapat_buttons[0].click_input()
                        logger.info("✓ Pencere kapatıldı (descendants click)")
                        self.timed_sleep("kapat_butonu")
                        return True
            except Exception as e:
                logger.debug(f"descendants() hatası: {type(e).__name__}")

            # YÖNTEM 7: Desktop'tan İlaç Listesi penceresini bul ve kapat
            try:
                from pywinauto import Desktop
                logger.info("  → Desktop'tan İlaç Listesi penceresi aranıyor...")
                windows = Desktop(backend="uia").windows()
                for win in windows:
                    try:
                        win_title = win.window_text()
                        if "İlaç Listesi" in win_title:
                            logger.info(f"  → İlaç Listesi bulundu: {win_title}")
                            win.close()
                            logger.info("✓ Pencere kapatıldı (Desktop search)")
                            self.timed_sleep("kapat_butonu")
                            return True
                    except Exception as win_err:
                        logger.debug(f"Window kontrol hatası: {type(win_err).__name__}")
            except Exception as desktop_err:
                logger.debug(f"Desktop search hatası: {type(desktop_err).__name__}")

            logger.warning("❌ İlaç Listesi penceresi kapatılamadı")
            return False

        except Exception as e:
            logger.error(f"Pencere kapatma hatası: {e}")
            return False

    def geri_don_butonuna_tikla(self):
        """
        Ana Medula ekranında Geri Dön butonuna tıkla - OPTIMIZE: child_window() ile doğrudan arama

        Inspect.exe bilgileri (27 Kasım 2025):
        - AutomationId: "form1:buttonGeriDon"
        - Name: "Geri Dön"
        - ControlType: Button
        - IsInvokePatternAvailable: true

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            # YÖNTEM 1: child_window() ile AutomationId araması (EN HIZLI)
            try:
                geri_don_btn = self.main_window.child_window(
                    auto_id="form1:buttonGeriDon",
                    control_type="Button"
                )
                if geri_don_btn.exists(timeout=0.5):  # Timeout artırıldı: 0.2 → 0.5
                    try:
                        geri_don_btn.invoke()
                        logger.info("✓ Geri Dön tıklandı (child_window)")
                        self.timed_sleep("geri_don_butonu")
                        return True
                    except Exception as inv_err:
                        logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                        try:
                            geri_don_btn.click_input()
                            logger.info("✓ Geri Dön tıklandı (click_input)")
                            self.timed_sleep("geri_don_butonu")
                            return True
                        except Exception as clk_err:
                            logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"child_window AutomationId hatası: {type(e).__name__}")

            # YÖNTEM 2: child_window() ile Name araması (FALLBACK)
            try:
                geri_don_btn = self.main_window.child_window(
                    title="Geri Dön",
                    control_type="Button"
                )
                if geri_don_btn.exists(timeout=0.5):  # Timeout artırıldı: 0.2 → 0.5
                    try:
                        geri_don_btn.invoke()
                        logger.info("✓ Geri Dön tıklandı (Name)")
                        self.timed_sleep("geri_don_butonu")
                        return True
                    except Exception as inv_err:
                        logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                        try:
                            geri_don_btn.click_input()
                            logger.info("✓ Geri Dön tıklandı (click_input - Name)")
                            self.timed_sleep("geri_don_butonu")
                            return True
                        except Exception as clk_err:
                            logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"child_window Name hatası: {type(e).__name__}")

            # YÖNTEM 3: descendants() ile son çare (spesifik AutomationId ile)
            logger.warning("Geri Dön: child_window() başarısız, descendants() deneniyor...")
            try:
                geri_don_buttons = self.main_window.descendants(
                    auto_id="form1:buttonGeriDon",
                    control_type="Button"
                )
                if geri_don_buttons and len(geri_don_buttons) > 0:
                    try:
                        geri_don_buttons[0].invoke()
                        logger.info("✓ Geri Dön tıklandı (descendants)")
                        self.timed_sleep("geri_don_butonu")
                        return True
                    except Exception:
                        geri_don_buttons[0].click_input()
                        logger.info("✓ Geri Dön tıklandı (descendants click)")
                        self.timed_sleep("geri_don_butonu")
                        return True
            except Exception as e:
                logger.debug(f"descendants() hatası: {type(e).__name__}")

            logger.warning("❌ Geri Dön bulunamadı")
            return False

        except Exception as e:
            logger.error(f"Geri Dön butonuna tıklama hatası: {e}")
            return False

    def sonra_butonuna_tikla(self):
        """
        SONRA > butonuna tıklayarak bir sonraki reçeteye geç - OPTIMIZE: child_window() ile doğrudan arama

        Inspect.exe bilgileri (27 Kasım 2025):
        - AutomationId: "btnSonraki"
        - Name: "Sonra >"
        - ControlType: Button
        - FrameworkId: "WinForm"
        - IsInvokePatternAvailable: true

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            # YÖNTEM 1: child_window() ile AutomationId araması (EN HIZLI)
            try:
                sonra_btn = self.main_window.child_window(
                    auto_id="btnSonraki",
                    control_type="Button"
                )
                if sonra_btn.exists(timeout=0.5):  # Timeout artırıldı: 0.2 → 0.5
                    try:
                        sonra_btn.invoke()
                        logger.info("✓ SONRA > Sonraki reçete (child_window)")
                        self.timed_sleep("sonra_butonu")
                        return True
                    except Exception as inv_err:
                        logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                        try:
                            sonra_btn.click_input()
                            logger.info("✓ SONRA > Sonraki reçete (click_input)")
                            self.timed_sleep("sonra_butonu")
                            return True
                        except Exception as clk_err:
                            logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"child_window AutomationId hatası: {type(e).__name__}")

            # YÖNTEM 2: child_window() ile Name araması (FALLBACK)
            try:
                sonra_btn = self.main_window.child_window(
                    title="Sonra >",
                    control_type="Button"
                )
                if sonra_btn.exists(timeout=0.5):  # Timeout artırıldı: 0.2 → 0.5
                    try:
                        sonra_btn.invoke()
                        logger.info("✓ SONRA > Sonraki reçete (Name)")
                        self.timed_sleep("sonra_butonu")
                        return True
                    except Exception as inv_err:
                        logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                        try:
                            sonra_btn.click_input()
                            logger.info("✓ SONRA > Sonraki reçete (click_input - Name)")
                            self.timed_sleep("sonra_butonu")
                            return True
                        except Exception as clk_err:
                            logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"child_window Name hatası: {type(e).__name__}")

            # YÖNTEM 3: descendants() ile son çare (spesifik AutomationId ile)
            logger.warning("SONRA: child_window() başarısız, descendants() deneniyor...")
            try:
                sonra_buttons = self.main_window.descendants(
                    auto_id="btnSonraki",
                    control_type="Button"
                )
                if sonra_buttons and len(sonra_buttons) > 0:
                    try:
                        sonra_buttons[0].invoke()
                        logger.info("✓ SONRA > Sonraki reçete (descendants)")
                        self.timed_sleep("sonra_butonu")
                        return True
                    except Exception:
                        sonra_buttons[0].click_input()
                        logger.info("✓ SONRA > Sonraki reçete (descendants click)")
                        self.timed_sleep("sonra_butonu")
                        return True
            except Exception as e:
                logger.debug(f"descendants() hatası: {type(e).__name__}")

            logger.warning("❌ SONRA yok (Son reçete)")
            return False

        except Exception as e:
            logger.error(f"SONRA butonuna tıklama hatası: {e}")
            return False

    def recete_no_ve_kontrol_birlesik(self, max_deneme=3, bekleme_suresi=0.3):
        """
        OPTİMİZE: Reçete numarası okuma + Kayıt kontrolü TEK TARAMADA

        Eski yöntem (2 ayrı tarama):
        - recete_no_oku() → descendants(Text) → ~1-3 saniye
        - recete_kaydi_var_mi() → descendants(Text) → ~1-3 saniye
        TOPLAM: 2-6 saniye

        Yeni yöntem (tek tarama):
        - TEK descendants(Text) çağrısı → ~1-3 saniye
        - Aynı anda hem reçete no hem uyarı kontrolü
        KAZANÇ: %50 hız artışı

        Returns:
            tuple: (recete_no: str veya None, kayit_var: bool)
                   recete_no = None ve kayit_var = False → "Reçete kaydı bulunamadı"
        """
        for deneme in range(max_deneme):
            try:
                # TEK TARAMA - hem reçete no hem uyarı kontrolü
                texts = self.main_window.descendants(control_type="Text")

                recete_no = None
                kayit_hatasi = False

                for text in texts:
                    try:
                        text_value = text.window_text()
                        if not text_value:
                            continue

                        # 1. UYARI KONTROLÜ
                        if "Reçete kaydı bulunamadı" in text_value:
                            logger.warning(f"⚠️ '{text_value}'")
                            kayit_hatasi = True
                            continue

                        if "Sistem hatası" in text_value:
                            logger.error(f"❌ MEDULA HATA: '{text_value}'")
                            kayit_hatasi = True
                            continue

                        # 2. REÇETE NUMARASI KONTROLÜ
                        if recete_no is None and 6 <= len(text_value) <= 9:
                            cleaned = text_value.replace('-', '').replace('_', '')
                            if cleaned.isalnum() and any(c.isdigit() for c in text_value) and any(c.isalpha() for c in text_value):
                                recete_no = text_value

                    except Exception:
                        continue

                # Sonuç
                if kayit_hatasi:
                    return (None, False)  # Kayıt yok

                if recete_no:
                    if deneme == 0:
                        logger.info(f"✓ Reçete No: {recete_no}")
                    else:
                        logger.info(f"✓ Reçete No: {recete_no} ({deneme+1}. denemede)")
                    return (recete_no, True)

                # Bu denemede bulunamadı
                if deneme < max_deneme - 1:
                    logger.debug(f"Reçete no henüz yüklenmedi ({deneme + 1}/{max_deneme})")
                    time.sleep(bekleme_suresi)

            except Exception as e:
                logger.debug(f"Birleşik tarama denemesi {deneme + 1} hatası: {type(e).__name__}")
                if deneme < max_deneme - 1:
                    time.sleep(bekleme_suresi)

        logger.warning("⚠️ Reçete numarası okunamadı")
        return (None, True)  # Kayıt var ama no okunamadı

    def recete_sayfasi_hizli_tarama(self, max_deneme=2, bekleme_suresi=0.2):
        """
        ULTRA OPTİMİZE: Container-based + Tek Tarama ile TÜM VERİLERİ TOPLA

        İyileştirmeler:
        1. pnlMedulaBaslik container'ı içinde HEDEFLI arama (telefon + reçete bilgisi)
        2. Direkt child_window() ile buton araması (descendants yerine)
        3. Tek geçişte tüm verileri toplama

        Eski yöntem: ~3-4 saniye (ayrı ayrı taramalar)
        Yeni yöntem: ~0.5-1 saniye (hedefli container arama)

        KAZANIM: %70-80 hız artışı

        Returns:
            dict: {
                'recete_no': str veya None,
                'kayit_var': bool,
                'telefon_var': bool,
                'telefon_degeri': str veya None,
                'ilac_butonu': element veya None (tıklama için hazır referans)
            }
        """
        import re
        telefon_pattern = re.compile(r'(\+90|0)?[\s\-\(]?[1-9]\d{2}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}')

        # Telefon alanları AutomationId'leri
        telefon_alan_idleri = [
            "lblMusteriTelefonu",
            "lblYanCariTelefonu",
            "lblIlaciAlanTelefonu",
            "lblAlanYanCariTel"
        ]

        for deneme in range(max_deneme):
            try:
                recete_no = None
                kayit_hatasi = False
                telefon_var = False
                telefon_degeri = None
                ilac_butonu = None

                # ═══════════════════════════════════════════════════════════════
                # ADIM 1: pnlMedulaBaslik CONTAINER içinde HEDEFLI ARAMA
                # Bu container telefon + reçete bilgisini içerir
                # ═══════════════════════════════════════════════════════════════
                try:
                    baslik_panel = self.main_window.child_window(
                        auto_id="pnlMedulaBaslik",
                        control_type="Pane"
                    )

                    if baslik_panel.exists(timeout=0.3):
                        # Sadece bu container içindeki elementleri tara (çok daha hızlı!)
                        panel_elements = baslik_panel.descendants()

                        for elem in panel_elements:
                            try:
                                text_value = None
                                auto_id = None

                                try:
                                    text_value = elem.window_text()
                                    if text_value:
                                        text_value = text_value.strip()
                                except Exception:
                                    pass

                                try:
                                    auto_id = elem.element_info.automation_id
                                except Exception:
                                    pass

                                if not text_value:
                                    continue

                                # TELEFON KONTROLÜ (AutomationId ile - en hızlı)
                                if not telefon_var and auto_id and auto_id in telefon_alan_idleri:
                                    if len(text_value) >= 7:
                                        temiz = text_value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                                        if temiz and any(c.isdigit() for c in temiz):
                                            telefon_var = True
                                            telefon_degeri = text_value
                                            logger.debug(f"✓ Telefon bulundu ({auto_id}): {text_value}")

                                # KAYIT HATASI KONTROLÜ
                                if "Reçete kaydı bulunamadı" in text_value:
                                    logger.warning(f"⚠️ '{text_value}'")
                                    kayit_hatasi = True

                                if "Sistem hatası" in text_value:
                                    logger.error(f"❌ MEDULA HATA: '{text_value}'")
                                    kayit_hatasi = True

                                # REÇETE NUMARASI KONTROLÜ (işlem nolu pattern)
                                if recete_no is None and "işlemnolu" in text_value:
                                    # "3HYAKH4 işlemnolu reçete KAYITLI..." formatı
                                    parts = text_value.split()
                                    if parts and len(parts[0]) >= 6 and len(parts[0]) <= 9:
                                        cleaned = parts[0].replace('-', '').replace('_', '')
                                        if cleaned.isalnum() and any(c.isdigit() for c in parts[0]) and any(c.isalpha() for c in parts[0]):
                                            recete_no = parts[0]

                                # Alternatif reçete no pattern (direkt 6-9 karakter alfanumerik)
                                if recete_no is None and 6 <= len(text_value) <= 9:
                                    cleaned = text_value.replace('-', '').replace('_', '')
                                    if cleaned.isalnum() and any(c.isdigit() for c in text_value) and any(c.isalpha() for c in text_value):
                                        # İşlem nolu olmayan ama formata uyan
                                        recete_no = text_value

                            except Exception:
                                continue
                    else:
                        logger.debug("pnlMedulaBaslik container bulunamadı, fallback yapılıyor...")

                except Exception as e:
                    logger.debug(f"Container arama hatası: {type(e).__name__}")

                # ═══════════════════════════════════════════════════════════════
                # ADIM 2: İLAÇ BUTONU - child_window ile HIZLI ARAMA
                # descendants() yerine direkt arama
                # ═══════════════════════════════════════════════════════════════
                try:
                    ilac_btn = self.main_window.child_window(
                        auto_id="f:buttonIlacListesi",
                        control_type="Button"
                    )
                    if ilac_btn.exists(timeout=0.2):
                        ilac_butonu = ilac_btn
                        logger.debug("✓ İlaç butonu referansı alındı")
                except Exception:
                    # Fallback: title ile ara
                    try:
                        ilac_btn = self.main_window.child_window(
                            title="İlaç",
                            control_type="Button"
                        )
                        if ilac_btn.exists(timeout=0.2):
                            ilac_butonu = ilac_btn
                            logger.debug("✓ İlaç butonu referansı alındı (title)")
                    except Exception:
                        pass

                # ═══════════════════════════════════════════════════════════════
                # SONUÇ DEĞERLENDİRMESİ
                # ═══════════════════════════════════════════════════════════════
                if kayit_hatasi:
                    return {
                        'recete_no': None,
                        'kayit_var': False,
                        'telefon_var': telefon_var,
                        'telefon_degeri': telefon_degeri,
                        'ilac_butonu': None
                    }

                if recete_no:
                    if deneme == 0:
                        logger.info(f"✓ Reçete No: {recete_no}" + (f", Tel: {telefon_degeri}" if telefon_var else ", Tel: YOK"))
                    else:
                        logger.info(f"✓ Reçete No: {recete_no} ({deneme+1}. denemede)")

                    return {
                        'recete_no': recete_no,
                        'kayit_var': True,
                        'telefon_var': telefon_var,
                        'telefon_degeri': telefon_degeri,
                        'ilac_butonu': ilac_butonu
                    }

                # Bu denemede bulunamadı - kısa bekle
                if deneme < max_deneme - 1:
                    logger.debug(f"Reçete no henüz yüklenmedi ({deneme + 1}/{max_deneme})")
                    time.sleep(bekleme_suresi)

            except Exception as e:
                logger.debug(f"Hızlı tarama denemesi {deneme + 1} hatası: {type(e).__name__}")
                if deneme < max_deneme - 1:
                    time.sleep(bekleme_suresi)

        # Fallback: Eski yönteme geç
        logger.debug("Hızlı tarama başarısız, standart yönteme geçiliyor...")
        return None  # None döndüğünde eski fonksiyon çağrılacak

    def recete_telefon_kontrol_birlesik(self, max_deneme=3, bekleme_suresi=0.3):
        """
        SÜPER OPTİMİZE: Reçete No + Telefon Kontrolü + Kayıt Kontrolü TEK TARAMADA

        Eski yöntem (3 ayrı tarama):
        - recete_no_ve_kontrol_birlesik() → descendants(Text) → ~1.3 saniye
        - telefon_numarasi_kontrol() → descendants(auto_id) x4 + descendants(Text) → ~1.7 saniye
        TOPLAM: ~3 saniye

        Yeni yöntem (tek tarama):
        - TEK descendants() çağrısı ile HER ŞEY
        - Reçete no, telefon, kayıt hatası aynı anda kontrol
        KAZANIM: %50-60 hız artışı (~1.5 saniye)

        Returns:
            dict: {
                'recete_no': str veya None,
                'kayit_var': bool,
                'telefon_var': bool,
                'telefon_degeri': str veya None
            }
        """
        import re
        # Türkiye telefon numarası pattern'i
        telefon_pattern = re.compile(r'(\+90|0)?[\s\-\(]?[1-9]\d{2}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}')

        # Telefon alanları AutomationId'leri
        telefon_alan_idleri = [
            "lblMusteriTelefonu",
            "lblYanCariTelefonu",
            "lblIlaciAlanTelefonu",
            "lblAlanYanCariTel"
        ]

        for deneme in range(max_deneme):
            try:
                # TEK TARAMA - tüm elementleri al (tip kısıtlaması yok = daha kapsamlı)
                all_elements = self.main_window.descendants()

                recete_no = None
                kayit_hatasi = False
                telefon_var = False
                telefon_degeri = None

                for elem in all_elements:
                    try:
                        # Element bilgilerini al
                        text_value = None
                        auto_id = None

                        try:
                            text_value = elem.window_text()
                            if text_value:
                                text_value = text_value.strip()
                        except Exception:
                            pass

                        try:
                            auto_id = elem.element_info.automation_id
                        except Exception:
                            pass

                        if not text_value:
                            continue

                        # 1. TELEFON KONTROLÜ (AutomationId ile)
                        if not telefon_var and auto_id and auto_id in telefon_alan_idleri:
                            if len(text_value) >= 7:
                                temiz = text_value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                                if temiz and any(c.isdigit() for c in temiz):
                                    telefon_var = True
                                    telefon_degeri = text_value
                                    logger.info(f"✓ Telefon bulundu ({auto_id}): {text_value}")

                        # 2. KAYIT HATASI KONTROLÜ
                        if "Reçete kaydı bulunamadı" in text_value:
                            logger.warning(f"⚠️ '{text_value}'")
                            kayit_hatasi = True

                        if "Sistem hatası" in text_value:
                            logger.error(f"❌ MEDULA HATA: '{text_value}'")
                            kayit_hatasi = True

                        # 3. REÇETE NUMARASI KONTROLÜ
                        if recete_no is None and 6 <= len(text_value) <= 9:
                            cleaned = text_value.replace('-', '').replace('_', '')
                            if cleaned.isalnum() and any(c.isdigit() for c in text_value) and any(c.isalpha() for c in text_value):
                                recete_no = text_value

                        # 4. TELEFON PATTERN KONTROLÜ (AutomationId bulunamadıysa)
                        if not telefon_var and auto_id and "Tel" in auto_id:
                            if len(text_value) >= 7 and telefon_pattern.search(text_value):
                                telefon_var = True
                                telefon_degeri = text_value
                                logger.info(f"✓ Telefon bulundu (pattern, {auto_id}): {text_value}")

                    except Exception:
                        continue

                # Sonuç değerlendirmesi
                if kayit_hatasi:
                    return {
                        'recete_no': None,
                        'kayit_var': False,
                        'telefon_var': telefon_var,
                        'telefon_degeri': telefon_degeri
                    }

                if recete_no:
                    if deneme == 0:
                        logger.info(f"✓ Reçete No: {recete_no}")
                    else:
                        logger.info(f"✓ Reçete No: {recete_no} ({deneme+1}. denemede)")

                    if not telefon_var:
                        logger.info("⚠ Telefon bulunamadı")

                    return {
                        'recete_no': recete_no,
                        'kayit_var': True,
                        'telefon_var': telefon_var,
                        'telefon_degeri': telefon_degeri
                    }

                # Bu denemede reçete no bulunamadı
                if deneme < max_deneme - 1:
                    logger.debug(f"Reçete no henüz yüklenmedi ({deneme + 1}/{max_deneme})")
                    time.sleep(bekleme_suresi)

            except Exception as e:
                logger.debug(f"Birleşik tarama denemesi {deneme + 1} hatası: {type(e).__name__}")
                if deneme < max_deneme - 1:
                    time.sleep(bekleme_suresi)

        logger.warning("⚠️ Reçete numarası okunamadı")
        return {
            'recete_no': None,
            'kayit_var': True,  # Kayıt var ama no okunamadı
            'telefon_var': telefon_var,
            'telefon_degeri': telefon_degeri
        }

    def recete_no_oku(self, max_deneme=3, bekleme_suresi=0.3):
        """
        Ekrandaki reçete numarasını oku (örn: 3HKE0T4)

        OPTİMİZE: Tek text taraması yapılıyor (önceden iki kez yapılıyordu)
        Bekleme süresi: 0.5 → 0.3, deneme sayısı: 5 → 3

        Args:
            max_deneme: Maksimum deneme sayısı (varsayılan: 3)
            bekleme_suresi: Her deneme arasında bekleme süresi (varsayılan: 0.3 saniye)

        Returns:
            str: Reçete numarası, bulunamazsa None
        """
        import time

        for deneme in range(max_deneme):
            try:
                # Text kontrollerini ara (TEK TARAMA - optimize edildi)
                texts = self.main_window.descendants(control_type="Text")

                for text in texts:
                    try:
                        text_value = text.window_text()

                        # Reçete numarası formatı: 6-9 karakter, alfanumerik
                        if text_value and 6 <= len(text_value) <= 9:
                            # Sadece harf, rakam ve belki tire içermeli
                            cleaned = text_value.replace('-', '').replace('_', '')
                            if cleaned.isalnum() and any(c.isdigit() for c in text_value) and any(c.isalpha() for c in text_value):
                                if deneme == 0:
                                    logger.info(f"✓ Reçete No: {text_value}")
                                else:
                                    logger.info(f"✓ Reçete No: {text_value} ({deneme+1}. denemede)")
                                return text_value
                    except Exception as e:
                        logger.debug(f"Text okuma hatası: {type(e).__name__}")

                # Bu denemede bulunamadı
                if deneme < max_deneme - 1:
                    logger.debug(f"Reçete no henüz yüklenmedi ({deneme + 1}/{max_deneme})")
                    time.sleep(bekleme_suresi)

            except Exception as e:
                logger.debug(f"Reçete no okuma denemesi {deneme + 1} hatası: {type(e).__name__}")
                if deneme < max_deneme - 1:
                    time.sleep(bekleme_suresi)

        logger.warning("⚠️ Reçete numarası okunamadı")
        return None

    def telefon_numarasi_kontrol(self):
        """
        Reçetede telefon numarası var mı kontrol et (4 farklı alan)

        Kontrol edilen alanlar:
        1. lblMusteriTelefonu - Müşteri telefonu
        2. lblYanCariTelefonu - Yan cari telefonu
        3. lblIlaciAlanTelefonu - İlacı alan telefonu
        4. lblAlanYanCariTel - Alan yan cari telefonu

        Returns:
            bool: En az bir alanda telefon varsa True, hiçbirinde yoksa False
        """
        try:
            telefon_alanlari = [
                "lblMusteriTelefonu",
                "lblYanCariTelefonu",
                "lblIlaciAlanTelefonu",
                "lblAlanYanCariTel"
            ]

            logger.debug("📞 Telefon kontrolü başlatılıyor...")

            # Sayfanın yüklenmesini bekle
            self.timed_sleep("adim_arasi_bekleme", 0.3)  # Sayfa yüklenme bekleme

            bulunan_telefon_sayisi = 0
            control_types = ["Text", "Edit", "Static"]  # Farklı element tiplerini dene

            for alan_id in telefon_alanlari:
                telefon_text = ""
                bulunan_elem_tipi = None

                logger.debug(f"Alan kontrol: {alan_id}")

                try:
                    # Farklı control type'ları dene
                    for ctrl_type in control_types:
                        try:
                            telefon_elems = self.main_window.descendants(auto_id=alan_id, control_type=ctrl_type)
                            logger.debug(f"{ctrl_type}: {len(telefon_elems) if telefon_elems else 0} sonuç")

                            if telefon_elems and len(telefon_elems) > 0:
                                telefon_elem = telefon_elems[0]
                                bulunan_elem_tipi = ctrl_type

                                # window_text() ile telefon numarasını al
                                try:
                                    raw_text = telefon_elem.window_text()
                                    telefon_text = raw_text.strip() if raw_text else ""
                                    logger.debug(f"window_text(): '{telefon_text}'")
                                except Exception as e1:
                                    logger.debug(f"window_text() hatası: {type(e1).__name__}")
                                    try:
                                        raw_name = telefon_elem.element_info.name
                                        telefon_text = raw_name.strip() if raw_name else ""
                                        logger.debug(f"element_info.name: '{telefon_text}'")
                                    except Exception as e2:
                                        logger.debug(f"element_info.name hatası: {type(e2).__name__}")
                                        telefon_text = ""

                                if telefon_text:  # Telefon bulundu, daha fazla type denemeye gerek yok
                                    logger.debug(f"Değer bulundu: {alan_id}")
                                    break
                        except Exception as e:
                            logger.debug(f"{ctrl_type} arama hatası: {type(e).__name__}")
                            continue

                    # Control type bulunamazsa, type kısıtlaması olmadan dene
                    if not telefon_text:
                        logger.debug(f"Tip kısıtlaması olmadan deneniyor...")
                        try:
                            telefon_elems = self.main_window.descendants(auto_id=alan_id)
                            logger.debug(f"Tip kısıtlamasız: {len(telefon_elems) if telefon_elems else 0} sonuç")

                            if telefon_elems and len(telefon_elems) > 0:
                                telefon_elem = telefon_elems[0]
                                bulunan_elem_tipi = "Typeless"

                                try:
                                    raw_text = telefon_elem.window_text()
                                    telefon_text = raw_text.strip() if raw_text else ""
                                    logger.debug(f"window_text(): '{telefon_text}'")
                                except Exception as e1:
                                    logger.debug(f"window_text() hatası: {type(e1).__name__}")
                                    try:
                                        raw_name = telefon_elem.element_info.name
                                        telefon_text = raw_name.strip() if raw_name else ""
                                        logger.debug(f"element_info.name: '{telefon_text}'")
                                    except Exception as e2:
                                        logger.debug(f"element_info.name hatası: {type(e2).__name__}")
                                        telefon_text = ""
                        except Exception as e:
                            logger.debug(f"Tip kısıtlamasız arama hatası: {type(e).__name__}")

                    logger.debug(f"{alan_id}: '{telefon_text}' (len={len(telefon_text)}, tip={bulunan_elem_tipi})")

                    # Telefon varsa (boş değilse ve geçerli uzunlukta)
                    # Telefon numaraları genellikle en az 7 karakter (bazı formatlar için)
                    if telefon_text and len(telefon_text) >= 7:
                        # Sadece rakam, boşluk, tire, parantez içeriyorsa geçerli telefon
                        temiz_telefon = telefon_text.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                        logger.debug(f"Temizlenmiş: '{temiz_telefon}'")

                        if temiz_telefon and any(c.isdigit() for c in temiz_telefon):
                            bulunan_telefon_sayisi += 1
                            logger.info(f"✓ Telefon bulundu ({alan_id}): {telefon_text}")
                            return True  # EN AZ BİR TELEFON VARSA HEMEN TRUE DÖN
                        else:
                            logger.debug(f"Geçersiz format (rakam yok)")
                    else:
                        logger.debug(f"BOŞ veya çok kısa")

                except Exception as e:
                    logger.debug(f"  ❌ {alan_id} kontrol hatası: {e}")
                    import traceback
                    traceback.print_exc()
                    continue

            # Auto_ID ile bulunamadıysa, alternatif: Tüm text elementlerini tara
            if bulunan_telefon_sayisi == 0:
                logger.debug("Alternatif arama başlatılıyor...")

                try:
                    import re
                    # Türkiye telefon numarası pattern'i (çeşitli formatlar)
                    telefon_pattern = re.compile(r'(\+90|0)?[\s\-\(]?[1-9]\d{2}[\s\-\)]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}')

                    # Tüm text elementlerini al
                    all_texts = self.main_window.descendants(control_type="Text")
                    logger.debug(f"Toplam {len(all_texts)} Text elementi bulundu")

                    # Önce auto_id'li elementleri kontrol et
                    for text_elem in all_texts:
                        try:
                            auto_id = None
                            try:
                                auto_id = text_elem.element_info.automation_id
                            except Exception as e:
                                logger.debug(f"Operation failed: {type(e).__name__}")

                            if auto_id and "Tel" in auto_id:
                                try:
                                    raw_text = text_elem.window_text()
                                    text_value = raw_text.strip() if raw_text else ""
                                except Exception as e:
                                    logger.debug(f"Fourth attempt failed: {type(e).__name__}")
                                    try:
                                        raw_name = text_elem.element_info.name
                                        text_value = raw_name.strip() if raw_name else ""
                                    except Exception as e:
                                        logger.debug(f"Text value read failed: {type(e).__name__}")
                                        text_value = ""

                                logger.debug(f"Tel ID: {auto_id} = '{text_value}'")

                                if text_value and len(text_value) >= 7:
                                    # Pattern kontrolü
                                    if telefon_pattern.search(text_value) or any(c.isdigit() for c in text_value):
                                        logger.info(f"✓ Telefon bulundu (alt. arama): {text_value}")
                                        return True
                        except Exception as e:
                            logger.debug(f"Operation failed, continuing: {type(e).__name__}")
                            continue

                    # Hala bulunamadıysa, tüm text değerlerini pattern ile kontrol et
                    logger.debug("Pattern tabanlı arama yapılıyor...")
                    for text_elem in all_texts[:100]:  # İlk 100 elementi kontrol et (performans için)
                        try:
                            try:
                                raw_text = text_elem.window_text()
                                text_value = raw_text.strip() if raw_text else ""
                            except Exception as e:
                                logger.debug(f"Third attempt failed: {type(e).__name__}")
                                try:
                                    raw_name = text_elem.element_info.name
                                    text_value = raw_name.strip() if raw_name else ""
                                except Exception as e:
                                    logger.debug(f"Text value read failed: {type(e).__name__}")
                                    text_value = ""

                            if text_value and telefon_pattern.search(text_value):
                                logger.info(f"✓ Telefon bulundu (pattern arama): {text_value}")
                                return True
                        except Exception as e:
                            logger.debug(f"Operation failed, continuing: {type(e).__name__}")
                            continue

                except Exception as e:
                    logger.debug(f"Alternatif arama hatası: {e}")

            # Hiçbir alanda telefon yok
            logger.info(f"⚠ Telefon bulunamadı ({bulunan_telefon_sayisi}/4 alan dolu)")
            return False

        except Exception as e:
            logger.error(f"❌ Telefon kontrolü HATA: {e}")
            import traceback
            traceback.print_exc()
            # Hata durumunda telefon var kabul et (güvenli taraf)
            logger.warning(f"⚠ HATA durumu: Telefon VAR kabul ediliyor (güvenli taraf)")
            return True

    def recete_kaydi_var_mi_kontrol(self):
        """
        Ekranda "Reçete kaydı bulunamadı" veya "Sistem hatası" uyarısı var mı kontrol et

        Returns:
            bool: Reçete kaydı VARSA True, YOKSA (uyarı varsa) False
        """
        try:
            # Tüm text elementlerini ara
            texts = self.main_window.descendants(control_type="Text")

            for text in texts:
                try:
                    text_value = text.window_text()
                    # "Reçete kaydı bulunamadı" kontrolü
                    if "Reçete kaydı bulunamadı" in text_value or "Recete kaydı bulunamadı" in text_value:
                        logger.warning(f"⚠️ '{text_value}'")
                        return False
                    # "Sistem hatası" kontrolü
                    if "Sistem hatası" in text_value or "Sistem hatasi" in text_value:
                        logger.error(f"❌ MEDULA HATA: '{text_value}'")
                        return False
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            return True

        except Exception as e:
            logger.error(f"Kontrol hatası: {e}")
            # Hata durumunda güvenli tarafta kalalım ve devam edelim
            return True

    def recete_kaydi_var_mi_kontrol_hizli(self):
        """
        HIZLI: Sadece outputText class'lı elementte "Reçete kaydı bulunamadı" ara

        UIElementInspector bilgileri (2 Aralık 2025):
        - Name: "Reçete kaydı bulunamadı."
        - TagName: SPAN
        - HTML Class: outputText
        - CSS Selector: .outputText

        Returns:
            bool: Reçete kaydı VARSA True, YOKSA (uyarı varsa) False
        """
        try:
            # HIZLI: Sadece outputText class'lı SPAN elementlerinde ara
            spans = self.main_window.descendants(control_type="Text")

            # İlk 10 elementi kontrol et (uyarı genellikle üstte)
            for i, span in enumerate(spans[:10]):
                try:
                    text_value = span.window_text()
                    if "Reçete kaydı bulunamadı" in text_value:
                        logger.warning(f"⚠️ '{text_value}'")
                        return False
                    if "Sistem hatası" in text_value:
                        logger.error(f"❌ MEDULA HATA: '{text_value}'")
                        return False
                except Exception:
                    continue

            return True

        except Exception as e:
            logger.debug(f"Hızlı kontrol hatası: {type(e).__name__}")
            return True  # Hata durumunda devam et

    def recete_sorgu_ac(self):
        """
        Reçete Sorgu butonuna tıkla - SADECE DOĞRU buton!

        DİKKAT: e-Reçete Sorgu (form1:menuHtmlCommandExButton11) KULLANILMAMALI!
        Sadece Reçete Sorgu (form1:menuHtmlCommandExButton51) kullanılmalı!

        Inspect.exe (30 Kasım 2025):
        - DOĞRU: AutomationId="form1:menuHtmlCommandExButton51_MOUSE", Name="    Reçete Sorgu"
        - YANLIŞ: AutomationId="form1:menuHtmlCommandExButton11_MOUSE", Name="    e-Reçete Sorgu"

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.info("🔍 Reçete Sorgu butonu aranıyor...")

            # ÖNEMLİ: Cache'i KULLANMA! Her seferinde yeni ara.
            self._clear_cache_key("recete_sorgu_button")

            # YÖNTEM 1: AutomationId ile ara (en güvenilir)
            recete_sorgu_ids = [
                "form1:menuHtmlCommandExButton51_MOUSE",
                "form1:menuHtmlCommandExButton51"
            ]
            for auto_id in recete_sorgu_ids:
                for ctrl_type in ["Button", "Image"]:
                    try:
                        sorgu_btn = self.main_window.child_window(
                            auto_id=auto_id,
                            control_type=ctrl_type
                        )
                        if sorgu_btn.exists(timeout=1.5):
                            logger.info(f"📍 Buton bulundu: {auto_id} ({ctrl_type})")
                            try:
                                sorgu_btn.invoke()
                                logger.info(f"✓ Reçete Sorgu butonu tıklandı (invoke)")
                                self.timed_sleep("recete_sorgu")
                                return True
                            except Exception as inv_err:
                                logger.debug(f"invoke() hatası: {inv_err}")
                                try:
                                    sorgu_btn.click_input()
                                    logger.info(f"✓ Reçete Sorgu butonu tıklandı (click_input)")
                                    self.timed_sleep("recete_sorgu")
                                    return True
                                except Exception as clk_err:
                                    logger.warning(f"click_input() hatası: {clk_err}")
                    except Exception as e:
                        logger.debug(f"AutomationId {auto_id} ({ctrl_type}) hatası: {e}")

            # YÖNTEM 2: Name ile ara - TAM EŞLEŞMEyle!
            # DOĞRU: "    Reçete Sorgu" (4 boşluk + Reçete Sorgu)
            # YANLIŞ: "    e-Reçete Sorgu" (4 boşluk + e-Reçete Sorgu)
            logger.info("🔍 AutomationId bulunamadı, Name ile aranıyor...")
            dogru_name = "    Reçete Sorgu"  # 4 boşluk + Reçete Sorgu (TAM EŞLEŞMEYİ!)

            for ctrl_type in ["Button", "Image"]:
                try:
                    sorgu_btn = self.main_window.child_window(
                        title=dogru_name,  # TAM EŞLEŞMEyle! (title_re değil!)
                        control_type=ctrl_type
                    )
                    if sorgu_btn.exists(timeout=1.5):
                        # Doğrulama: e-Reçete Sorgu olmadığından emin ol
                        btn_name = sorgu_btn.window_text()
                        if "e-Reçete" in btn_name or "e-reçete" in btn_name.lower():
                            logger.warning(f"⚠ YANLIŞ BUTON TESPİT EDİLDİ: {btn_name} - ATLANIY0R!")
                            continue

                        logger.info(f"📍 Name ile bulundu: '{btn_name}' ({ctrl_type})")
                        try:
                            sorgu_btn.invoke()
                            logger.info(f"✓ Reçete Sorgu butonu tıklandı (Name invoke)")
                            self.timed_sleep("recete_sorgu")
                            return True
                        except Exception:
                            try:
                                sorgu_btn.click_input()
                                logger.info(f"✓ Reçete Sorgu butonu tıklandı (Name click_input)")
                                self.timed_sleep("recete_sorgu")
                                return True
                            except Exception as e:
                                logger.warning(f"Name click hatası: {e}")
                except Exception as e:
                    logger.debug(f"Name '{dogru_name}' ({ctrl_type}) hatası: {e}")

            logger.error("❌ Reçete Sorgu butonu bulunamadı!")
            logger.error("   Denenenen ID'ler: form1:menuHtmlCommandExButton51_MOUSE")
            logger.error("   Denenenen Name: '    Reçete Sorgu'")
            return False

        except Exception as e:
            logger.error(f"Reçete Sorgu butonu hatası: {e}")
            return False

    def recete_sorgu_ac_kademeli(self):
        """
        Reçete Sorgu butonunu KADEMELİ KURTARMA ile aç

        Kurtarma Aşamaları:
        1. Normal arama (recete_sorgu_ac)
        2. Bulunamazsa → Geri Dön butonuna bas + tekrar ara
        3. Hala bulunamazsa → Çıkış + 3x Giriş + tekrar ara
        4. Hala bulunamazsa → False döner (üst seviye taskkill yapacak)

        Returns:
            bool: Reçete Sorgu butonu başarıyla tıklandıysa True
        """
        # ═══════════════════════════════════════════════════════════════
        # AŞAMA 1: Normal arama
        # ═══════════════════════════════════════════════════════════════
        logger.info("🔍 [1/4] Reçete Sorgu butonu aranıyor...")
        if self.recete_sorgu_ac():
            return True

        logger.warning("⚠ Reçete Sorgu butonu bulunamadı, kurtarma başlatılıyor...")

        # ═══════════════════════════════════════════════════════════════
        # AŞAMA 2: Geri Dön butonuna bas + tekrar ara
        # ═══════════════════════════════════════════════════════════════
        logger.info("🔄 [2/4] Geri Dön butonuna basılıyor...")
        try:
            if self.geri_don_butonuna_tikla():
                logger.info("✓ Geri Dön butonu tıklandı")
                time.sleep(1)  # Sayfa yüklenmesi için bekle

                # Tekrar Reçete Sorgu ara
                logger.info("🔍 Reçete Sorgu tekrar aranıyor...")
                if self.recete_sorgu_ac():
                    logger.info("✓ Reçete Sorgu bulundu (Geri Dön sonrası)")
                    return True
            else:
                logger.warning("⚠ Geri Dön butonu bulunamadı")
        except Exception as e:
            logger.warning(f"Geri Dön hatası: {type(e).__name__}")

        # ═══════════════════════════════════════════════════════════════
        # AŞAMA 3: Çıkış + 3x Giriş + tekrar ara
        # ═══════════════════════════════════════════════════════════════
        logger.info("🔄 [3/4] Çıkış + 3x Giriş yapılıyor...")
        try:
            # Çıkış butonuna bas
            if self.cikis_butonu_var_mi():
                logger.info("  → Çıkış Yap butonuna basılıyor...")
                if self.cikis_butonuna_tikla():
                    logger.info("  ✓ Çıkış yapıldı")
                    time.sleep(1)
                else:
                    logger.warning("  ⚠ Çıkış butonu tıklanamadı")
            else:
                logger.info("  → Çıkış butonu yok (muhtemelen giriş ekranında)")

            # 3 kez Giriş butonuna bas
            for i in range(3):
                logger.info(f"  → Giriş butonuna basılıyor ({i+1}/3)...")
                if self.ana_sayfaya_don():
                    logger.info(f"  ✓ Giriş butonu tıklandı ({i+1}/3)")
                    time.sleep(0.5)
                else:
                    logger.warning(f"  ⚠ Giriş butonu tıklanamadı ({i+1}/3)")
                    break

            # Son giriş sonrası biraz bekle
            time.sleep(1)

            # Pencereyi yenile
            try:
                self.baglanti_kur("MEDULA", ilk_baglanti=False)
            except Exception:
                pass

            # Tekrar Reçete Sorgu ara
            logger.info("🔍 Reçete Sorgu tekrar aranıyor...")
            if self.recete_sorgu_ac():
                logger.info("✓ Reçete Sorgu bulundu (Çıkış + Giriş sonrası)")
                return True

        except Exception as e:
            logger.warning(f"Çıkış + Giriş hatası: {type(e).__name__}")

        # ═══════════════════════════════════════════════════════════════
        # AŞAMA 4: Tüm kurtarma denemeleri başarısız
        # ═══════════════════════════════════════════════════════════════
        logger.error("❌ [4/4] Reçete Sorgu butonu tüm denemelerde bulunamadı!")
        logger.error("   → Üst seviye taskkill + yeniden başlatma gerekli")
        return False

    def ana_sayfaya_don(self):
        """
        Giriş butonuna tıkla (MEDULA oturumunu yenilemek için) - OPTIMIZE: child_window() ile doğrudan arama

        NOT: Sol menüde "Ana Sayfa" butonu yok. Oturum yenilemek için üst paneldeki
        "Giriş" butonu kullanılıyor.

        Inspect.exe bilgileri (28 Kasım 2025):
        - AutomationId: "btnMedulayaGirisYap"
        - Name: "Giriş"
        - ControlType: Button
        - FrameworkId: "WinForm"
        - IsInvokePatternAvailable: true

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.debug("Giriş butonu aranıyor (oturum yenileme)...")

            # Önce cache'den kontrol et
            cached_button = self._get_cached_element("giris_button")
            if cached_button:
                try:
                    cached_button.invoke()
                    logger.info("✓ Giriş butonu tıklandı (cache)")
                    self.timed_sleep("ana_sayfa")
                    return True
                except Exception as e:
                    logger.debug(f"Cache giris_button invoke failed: {type(e).__name__}")
                    self._clear_cache_key("giris_button")

            # YÖNTEM 1: child_window() ile AutomationId araması (EN HIZLI)
            try:
                giris_btn = self.main_window.child_window(
                    auto_id="btnMedulayaGirisYap",
                    control_type="Button"
                )
                if giris_btn.exists(timeout=0.2):
                    self._cache_element("giris_button", giris_btn)
                    try:
                        giris_btn.invoke()
                        logger.info("✓ Giriş butonu tıklandı (child_window)")
                        self.timed_sleep("ana_sayfa")
                        return True
                    except Exception as inv_err:
                        logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                        try:
                            giris_btn.click_input()
                            logger.info("✓ Giriş butonu tıklandı (click_input)")
                            self.timed_sleep("ana_sayfa")
                            return True
                        except Exception as clk_err:
                            logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"child_window AutomationId hatası: {type(e).__name__}")

            # YÖNTEM 2: child_window() ile Name araması (FALLBACK)
            try:
                giris_btn = self.main_window.child_window(
                    title="Giriş",
                    control_type="Button"
                )
                if giris_btn.exists(timeout=0.2):
                    self._cache_element("giris_button", giris_btn)
                    try:
                        giris_btn.invoke()
                        logger.info("✓ Giriş butonu tıklandı (Name)")
                        self.timed_sleep("ana_sayfa")
                        return True
                    except Exception as inv_err:
                        logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                        try:
                            giris_btn.click_input()
                            logger.info("✓ Giriş butonu tıklandı (click_input - Name)")
                            self.timed_sleep("ana_sayfa")
                            return True
                        except Exception as clk_err:
                            logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"child_window Name hatası: {type(e).__name__}")

            # YÖNTEM 3: descendants() ile son çare
            logger.warning("Giriş: child_window() başarısız, descendants() deneniyor...")
            try:
                giris_buttons = self.main_window.descendants(
                    auto_id="btnMedulayaGirisYap",
                    control_type="Button"
                )
                if giris_buttons and len(giris_buttons) > 0:
                    self._cache_element("giris_button", giris_buttons[0])
                    try:
                        giris_buttons[0].invoke()
                        logger.info("✓ Giriş butonu tıklandı (descendants)")
                        self.timed_sleep("ana_sayfa")
                        return True
                    except Exception:
                        giris_buttons[0].click_input()
                        logger.info("✓ Giriş butonu tıklandı (descendants click)")
                        self.timed_sleep("ana_sayfa")
                        return True
            except Exception as e:
                logger.debug(f"descendants() hatası: {type(e).__name__}")

            # YÖNTEM 4: PyAutoGUI ile koordinat tıklama (SON ÇARE)
            # Inspect.exe (29 Kasım 2025): Giriş butonu X: 161, Y: 182, W: 55, H: 23 (pencere koordinatları)
            logger.warning("Giriş: UIA yöntemleri başarısız, PyAutoGUI koordinat tıklama deneniyor...")
            try:
                import pyautogui
                # Pencere konumunu al
                window_rect = self.main_window.rectangle()
                # Buton koordinatları (pencere içi) - inspect.exe bilgilerinden
                btn_x_offset = 161 + 27  # Buton merkezi (X + Width/2)
                btn_y_offset = 182 + 11  # Buton merkezi (Y + Height/2)
                # Ekran koordinatlarına çevir
                click_x = window_rect.left + btn_x_offset
                click_y = window_rect.top + btn_y_offset

                pyautogui.click(click_x, click_y)
                logger.info(f"✓ Giriş butonu tıklandı (PyAutoGUI koordinat: {click_x}, {click_y})")
                self.timed_sleep("ana_sayfa")
                return True
            except Exception as e:
                logger.error(f"PyAutoGUI koordinat tıklama hatası: {e}")

            logger.error("❌ Giriş butonu bulunamadı")
            return False

        except Exception as e:
            logger.error(f"Giriş butonu hatası: {e}")
            return False

    def cikis_butonuna_tikla(self):
        """
        Çıkış Yap butonuna tıkla - oturumu sonlandırmak için

        Inspect.exe (2025-12-12):
        - Name: "    Çıkış Yap" (4 boşluk + Çıkış Yap)
        - AutomationId: form1:menuHtmlCommandExButton231_MOUSE
        - Konum: X: 11, Y: 678, Width: 165, Height: 20

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.debug("Çıkış Yap butonu aranıyor...")

            # YÖNTEM 1: AutomationId ile ara (güncel ID)
            cikis_auto_ids = [
                "form1:menuHtmlCommandExButton231_MOUSE",  # Yeni ID (2025-12-12)
                "form1:menuHtmlCommandExButton01_MOUSE"    # Eski ID (fallback)
            ]

            for cikis_auto_id in cikis_auto_ids:
                for ctrl_type in ["Button", "Image"]:
                    try:
                        cikis_btn = self.main_window.child_window(
                            auto_id=cikis_auto_id,
                            control_type=ctrl_type
                        )
                        if cikis_btn.exists(timeout=0.3):
                            try:
                                cikis_btn.invoke()
                                logger.info(f"✓ Çıkış Yap butonu tıklandı ({ctrl_type}, {cikis_auto_id})")
                                time.sleep(1)  # Çıkış işlemi için bekle
                                return True
                            except Exception as inv_err:
                                logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                                try:
                                    cikis_btn.click_input()
                                    logger.info(f"✓ Çıkış Yap butonu tıklandı (click_input {ctrl_type})")
                                    time.sleep(1)
                                    return True
                                except Exception as clk_err:
                                    logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
                    except Exception as e:
                        logger.debug(f"child_window {cikis_auto_id} ({ctrl_type}) hatası: {type(e).__name__}")

            # YÖNTEM 2: Name ile ara (4 boşluk + Çıkış Yap)
            cikis_name = "    Çıkış Yap"
            for ctrl_type in ["Button", "Image"]:
                try:
                    cikis_btn = self.main_window.child_window(
                        title=cikis_name,
                        control_type=ctrl_type
                    )
                    if cikis_btn.exists(timeout=0.3):
                        try:
                            cikis_btn.invoke()
                            logger.info(f"✓ Çıkış Yap butonu tıklandı (Name {ctrl_type})")
                            time.sleep(1)
                            return True
                        except Exception:
                            try:
                                cikis_btn.click_input()
                                logger.info(f"✓ Çıkış Yap butonu tıklandı (Name click_input)")
                                time.sleep(1)
                                return True
                            except Exception:
                                pass
                except Exception as e:
                    logger.debug(f"Name '{cikis_name}' ({ctrl_type}) hatası: {type(e).__name__}")

            logger.debug("Çıkış Yap butonu bulunamadı (muhtemelen zaten giriş ekranında)")
            return False

        except Exception as e:
            logger.debug(f"Çıkış butonu hatası: {e}")
            return False

    def cikis_butonu_var_mi(self):
        """
        Çıkış Yap butonunun mevcut olup olmadığını kontrol et

        Returns:
            bool: Buton varsa True
        """
        try:
            # Güncel ve eski AutomationId'ler
            cikis_auto_ids = [
                "form1:menuHtmlCommandExButton231_MOUSE",  # Yeni ID (2025-12-12)
                "form1:menuHtmlCommandExButton01_MOUSE"    # Eski ID (fallback)
            ]

            for cikis_auto_id in cikis_auto_ids:
                for ctrl_type in ["Button", "Image"]:
                    try:
                        cikis_btn = self.main_window.child_window(
                            auto_id=cikis_auto_id,
                            control_type=ctrl_type
                        )
                        if cikis_btn.exists(timeout=0.2):
                            logger.debug(f"✓ Çıkış Yap butonu mevcut ({cikis_auto_id})")
                            return True
                    except Exception:
                        pass

            # Name ile de kontrol et
            try:
                cikis_btn = self.main_window.child_window(
                    title="    Çıkış Yap",
                    control_type="Button"
                )
                if cikis_btn.exists(timeout=0.2):
                    logger.debug("✓ Çıkış Yap butonu mevcut (Name)")
                    return True
            except Exception:
                pass

            logger.debug("Çıkış Yap butonu mevcut değil")
            return False

        except Exception:
            return False

    def giris_butonuna_tikla(self):
        """
        Ana penceredeki WinForms 'Giriş' butonuna tıkla

        Inspect.exe (2025-12-10):
        - Name: "Giriş"
        - AutomationId: btnMedulayaGirisYap
        - ClassName: WindowsForms10.Window.b.app.0.134c08f_r8_ad1
        - ControlType: Button

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.debug("WinForms Giriş butonu aranıyor...")

            # AutomationId ile ara (en güvenilir)
            giris_auto_id = "btnMedulayaGirisYap"

            try:
                giris_btn = self.main_window.child_window(
                    auto_id=giris_auto_id,
                    control_type="Button"
                )
                if giris_btn.exists(timeout=0.5):
                    try:
                        giris_btn.invoke()
                        logger.info("✓ WinForms Giriş butonu tıklandı (invoke)")
                        self.timed_sleep("giris_butonu", 0.5)
                        return True
                    except Exception as inv_err:
                        logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                        try:
                            giris_btn.click_input()
                            logger.info("✓ WinForms Giriş butonu tıklandı (click_input)")
                            self.timed_sleep("giris_butonu", 0.5)
                            return True
                        except Exception as clk_err:
                            logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"AutomationId ile arama hatası: {type(e).__name__}")

            # Name ile ara (yedek)
            try:
                giris_btn = self.main_window.child_window(
                    title="Giriş",
                    control_type="Button"
                )
                if giris_btn.exists(timeout=0.3):
                    giris_btn.click_input()
                    logger.info("✓ WinForms Giriş butonu tıklandı (Name ile)")
                    self.timed_sleep("giris_butonu", 0.5)
                    return True
            except Exception as e:
                logger.debug(f"Name ile arama hatası: {type(e).__name__}")

            logger.warning("WinForms Giriş butonu bulunamadı")
            return False

        except Exception as e:
            logger.error(f"Giriş butonu hatası: {e}")
            return False

    def recete_listesi_butonuna_tikla(self):
        """
        Web sayfasındaki 'Reçete Listesi' butonuna tıkla

        Inspect.exe (2025-12-10):
        - Name: "    Reçete Listesi"
        - AutomationId: form1:menuHtmlCommandExButton31_MOUSE
        - ControlType: Button

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.debug("Reçete Listesi butonu aranıyor...")

            # AutomationId ile ara
            recete_auto_id = "form1:menuHtmlCommandExButton31_MOUSE"

            for ctrl_type in ["Button", "Image"]:
                try:
                    recete_btn = self.main_window.child_window(
                        auto_id=recete_auto_id,
                        control_type=ctrl_type
                    )
                    if recete_btn.exists(timeout=0.3):
                        try:
                            recete_btn.invoke()
                            logger.info(f"✓ Reçete Listesi butonu tıklandı ({ctrl_type})")
                            self.timed_sleep("recete_listesi_butonu", 0.5)
                            return True
                        except Exception as inv_err:
                            logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                            try:
                                recete_btn.click_input()
                                logger.info(f"✓ Reçete Listesi butonu tıklandı (click_input {ctrl_type})")
                                self.timed_sleep("recete_listesi_butonu", 0.5)
                                return True
                            except Exception as clk_err:
                                logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
                except Exception as e:
                    logger.debug(f"child_window {recete_auto_id} ({ctrl_type}) hatası: {type(e).__name__}")

            # Name ile ara (yedek - boşluklu isim)
            try:
                buttons = self.main_window.descendants(control_type="Button")
                for btn in buttons:
                    try:
                        btn_name = btn.window_text()
                        if "Reçete Listesi" in btn_name and "Günlük" not in btn_name:
                            btn.click_input()
                            logger.info("✓ Reçete Listesi butonu tıklandı (Name ile)")
                            self.timed_sleep("recete_listesi_butonu", 0.5)
                            return True
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"Name ile arama hatası: {type(e).__name__}")

            logger.warning("Reçete Listesi butonu bulunamadı")
            return False

        except Exception as e:
            logger.error(f"Reçete Listesi butonu hatası: {e}")
            return False

    def oturum_yenile(self):
        """
        MEDULA oturumunu yenile - ComboBox bulunamadığında çağrılır

        Akış:
        1. Giriş butonuna bas (WinForms)
        2. Çıkış Yap butonuna bas (Web)
        3. Giriş butonuna tekrar bas
        4. Reçete Listesi butonuna bas

        Returns:
            bool: Yenileme başarılı ise True
        """
        try:
            logger.info("🔄 MEDULA oturumu yenileniyor...")

            # Adım 1: Giriş butonuna bas
            logger.info("  [1/4] Giriş butonuna basılıyor...")
            if not self.giris_butonuna_tikla():
                logger.warning("  Giriş butonu tıklanamadı, devam ediliyor...")

            time.sleep(0.5)

            # Adım 2: Çıkış Yap butonuna bas
            logger.info("  [2/4] Çıkış Yap butonuna basılıyor...")
            if not self.cikis_butonuna_tikla():
                logger.warning("  Çıkış Yap butonu tıklanamadı (muhtemelen zaten giriş ekranında)")

            time.sleep(0.5)

            # Adım 3: Giriş butonuna tekrar bas
            logger.info("  [3/4] Giriş butonuna tekrar basılıyor...")
            if not self.giris_butonuna_tikla():
                logger.error("  Giriş butonu tıklanamadı!")
                return False

            # Ana sayfanın yüklenmesini bekle
            time.sleep(2.0)

            # Adım 4: Reçete Listesi butonuna bas
            logger.info("  [4/4] Reçete Listesi butonuna basılıyor...")
            if not self.recete_listesi_butonuna_tikla():
                logger.error("  Reçete Listesi butonu tıklanamadı!")
                return False

            # Reçete listesi sayfasının yüklenmesini bekle
            time.sleep(1.5)

            logger.info("✅ Oturum yenileme tamamlandı!")
            return True

        except Exception as e:
            logger.error(f"❌ Oturum yenileme hatası: {e}")
            return False

    def baska_eczane_uyarisi_var_mi(self):
        """
        "XXXX nolu reçete başka bir eczaneye aittir" uyarısını kontrol et.

        UIElementInspector bilgileri (2 Aralık 2025):
        - Name: "3IBOCLD nolu reçete başka bir eczaneye aittir."
        - ControlType: Text
        - TagName: SPAN
        - HTML Class: outputText

        Returns:
            bool: Uyarı varsa True, yoksa False
        """
        try:
            # SPAN elementi içinde "başka bir eczaneye aittir" metnini ara
            ie_server = self.main_window.child_window(class_name="Internet Explorer_Server")
            if not ie_server.exists(timeout=0.2):
                return False

            # Tüm Text elementlerini kontrol et
            text_elements = ie_server.descendants(control_type="Text")
            for elem in text_elements:
                try:
                    text = elem.window_text()
                    if text and "başka bir eczaneye aittir" in text:
                        logger.warning(f"⚠️ Başka eczane uyarısı tespit edildi: {text}")
                        return True
                except Exception:
                    continue

            return False
        except Exception as e:
            logger.debug(f"Başka eczane kontrolü hatası: {type(e).__name__}")
            return False

    def medula_oturumu_yenile(self):
        """
        MEDULA oturumunu yenile - Çıkış + 3x Giriş

        Akış:
        1. Çıkış Yap butonu var mı kontrol et
        2. Varsa Çıkış Yap butonuna bas (oturumu sonlandır)
        3. 3 kez Giriş butonuna bas (yeni oturum başlat / Ana Sayfa'ya dön)

        Returns:
            bool: İşlem başarılı ise True
        """
        try:
            logger.info("🔄 Medula oturumu yenileniyor...")

            # 1. Önce Çıkış Yap butonu var mı kontrol et
            if self.cikis_butonu_var_mi():
                logger.info("📍 Çıkış Yap butonu bulundu - önce çıkış yapılıyor...")
                if self.cikis_butonuna_tikla():
                    logger.info("✓ Çıkış yapıldı")
                    time.sleep(1)  # Çıkış sonrası bekle
                else:
                    logger.warning("⚠ Çıkış butonu tıklanamadı, devam ediliyor...")

            # 2. 3 kez Giriş butonuna bas
            logger.info("📍 3 kez Giriş butonuna basılıyor...")
            basarili_tiklamalar = 0
            for i in range(3):
                logger.debug(f"Giriş tıklaması {i+1}/3...")
                if self.ana_sayfaya_don():
                    basarili_tiklamalar += 1
                    time.sleep(2)  # 2 saniye bekle
                else:
                    logger.warning(f"⚠ {i+1}. Giriş tıklaması başarısız")
                    time.sleep(1)  # Hata durumunda 1 saniye bekle

            if basarili_tiklamalar > 0:
                logger.info(f"✓ Medula oturumu yenilendi ({basarili_tiklamalar}/3 başarılı)")
                return True
            else:
                logger.warning("❌ Medula oturumu yenilenemedi (hiçbir tıklama başarılı olmadı)")
                return False

        except Exception as e:
            logger.error(f"Medula oturumu yenileme hatası: {e}")
            return False

    def recete_no_yaz(self, recete_no):
        """
        Reçete numarasını giriş alanına yaz - SADECE DOĞRU AutomationId ile!

        DİKKAT: form1:textSmartDeger (e-Reçete Sorgu) KULLANILMAMALI!
        Sadece form1:text2 (Reçete Sorgu) kullanılmalı!

        Args:
            recete_no (str): Yazılacak reçete numarası

        Returns:
            bool: Yazma başarılı ise True
        """
        try:
            logger.info(f"Reçete numarası yazılıyor: {recete_no}")

            # Önce pencereyi yenile (sayfa değişmiş olabilir)
            self.baglanti_kur("MEDULA", ilk_baglanti=False)

            # DOĞRU: form1:text2 (Reçete Sorgu sayfası)
            # YANLIŞ: form1:textSmartDeger (e-Reçete Sorgu sayfası) KULLANILMAMALI!
            recete_auto_id = "form1:text2"

            try:
                # child_window() kullan (descendants() auto_id desteklemiyor!)
                edit = self.main_window.child_window(auto_id=recete_auto_id, control_type="Edit")
                if edit.exists(timeout=2.0):
                    logger.info(f"📍 Edit alanı bulundu: {recete_auto_id}")

                    # Focus'u al
                    edit.set_focus()
                    self.timed_sleep("text_focus")

                    # Önce temizle
                    try:
                        edit.set_edit_text("")
                        self.timed_sleep("text_clear")
                    except Exception as e:
                        logger.debug(f"Temizleme hatası: {type(e).__name__}")

                    # Yeni değeri yaz
                    edit.set_edit_text(recete_no)
                    self.timed_sleep("text_write")

                    logger.info(f"✓ Reçete numarası yazıldı: {recete_no}")
                    return True
                else:
                    logger.warning(f"⚠ Edit alanı bulunamadı: {recete_auto_id}")

            except Exception as e:
                logger.debug(f"AutomationId {recete_auto_id} ile yazılamadı: {type(e).__name__}")

            # FALLBACK YÖNTEMLERİ KALDIRILDI!
            # İlk boş edit alanını bulma, koordinat tıklama gibi yöntemler
            # yanlış ekranda (e-Reçete Sorgu) yanlış alana yazabilir!

            logger.error(f"❌ Reçete numarası alanı bulunamadı! ({recete_auto_id})")
            logger.error("   Muhtemel sebep: Reçete Sorgu sayfasında değil (e-Reçete Sorgu olabilir!)")
            return False

        except Exception as e:
            logger.error(f"Reçete numarası yazma hatası: {e}")
            return False

    def sorgula_butonuna_tikla(self):
        """
        Sorgula butonuna tıkla - SADECE DOĞRU AutomationId ile!

        DİKKAT: form1:buttonSorgula (e-Reçete Sorgu) KULLANILMAMALI!
        Sadece form1:buttonReceteNoSorgula (Reçete Sorgu) kullanılmalı!

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.info("🔍 Sorgula butonu aranıyor...")

            # Önce pencereyi yenile (sayfa değişmiş olabilir)
            self.baglanti_kur("MEDULA", ilk_baglanti=False)

            # Cache'i temizle
            self._clear_cache_key("sorgula_button")

            # DOĞRU: form1:buttonReceteNoSorgula (Reçete Sorgu sayfası)
            # YANLIŞ: form1:buttonSorgula (e-Reçete Sorgu sayfası) KULLANILMAMALI!
            sorgula_auto_ids = [
                "form1:buttonReceteNoSorgula",
            ]

            for auto_id in sorgula_auto_ids:
                try:
                    sorgula_btn = self.main_window.child_window(
                        auto_id=auto_id,
                        control_type="Button"
                    )
                    if sorgula_btn.exists(timeout=1.0):
                        try:
                            sorgula_btn.invoke()
                            logger.info(f"✓ Sorgula butonu tıklandı ({auto_id})")
                            self.timed_sleep("sorgula_butonu")
                            return True
                        except Exception as inv_err:
                            logger.debug(f"invoke() hatası: {type(inv_err).__name__}")
                            try:
                                sorgula_btn.click_input()
                                logger.info(f"✓ Sorgula butonu tıklandı (click_input: {auto_id})")
                                self.timed_sleep("sorgula_butonu")
                                return True
                            except Exception as clk_err:
                                logger.debug(f"click_input() hatası: {type(clk_err).__name__}")
                except Exception as e:
                    logger.debug(f"child_window {auto_id} hatası: {type(e).__name__}")

            # FALLBACK YÖNTEMLERİ KALDIRILDI!
            # Name="Sorgula" araması, descendants(), koordinat tıklama yanlış butona tıklayabilir.
            # e-Reçete Sorgu sayfasındaki buttonSorgula ile karışabilir!

            logger.error("❌ Sorgula butonu bulunamadı! (form1:buttonReceteNoSorgula)")
            logger.error("   Muhtemel sebep: Reçete Sorgu sayfasında değil (e-Reçete Sorgu olabilir!)")
            return False

        except Exception as e:
            logger.error(f"Sorgula butonu hatası: {e}")
            return False

    def recete_bilgilerini_al(self):
        """
        Ekrandaki reçete bilgilerini al

        ⚠️ NOT IMPLEMENTED YET
        Bu fonksiyon henüz tamamlanmamıştır.

        Returns:
            None: Fonksiyon implement edilmediği için her zaman None döner
        """
        logger.warning("⚠️ recete_bilgilerini_al() henüz implement edilmedi")
        # TODO: Reçete bilgilerini okuma işlemi implement edilecek
        return None

    def rapor_butonuna_tikla(self):
        """
        Rapor butonuna tıkla - Geliştirilmiş web butonu tıklama

        UIElementInspector bilgileri (1 Aralık 2025):
        - Name: "Rapor"
        - HTML Id: "f:buttonRaporListesi"
        - ControlType: Button
        - WindowClassName: Internet Explorer_Server
        - BoundingRectangle: {l:656 t:203 r:731 b:222}

        NOT: Bu buton Reçete Ana Sayfasında (ReceteListe.jsp) bulunur.
        Geri Dön butonuna tıklandıktan SONRA bu sayfaya geçilir ve buton görünür olur.

        Returns:
            bool: Tıklama başarılı ise True
        """
        try:
            logger.info("🔍 Rapor butonu aranıyor...")

            # Pencereye odaklan (hızlı, hata olsa bile devam)
            try:
                self.main_window.set_focus()
            except Exception:
                pass

            # YÖNTEM 1: child_window() ile hızlı arama (timeout artırıldı: 0.2 → 0.8)
            try:
                rapor_btn = self.main_window.child_window(
                    auto_id="f:buttonRaporListesi",
                    control_type="Button"
                )
                if rapor_btn.exists(timeout=0.8):
                    logger.info("  ✓ Rapor butonu bulundu (child_window AutomationId)")
                    try:
                        rapor_btn.invoke()
                        logger.info("✅ Rapor butonu tıklandı (invoke)")
                        self.timed_sleep("rapor_button_wait", 0.1)
                        return True
                    except Exception:
                        rapor_btn.click_input()
                        logger.info("✅ Rapor butonu tıklandı (click_input)")
                        self.timed_sleep("rapor_button_wait", 0.1)
                        return True
            except Exception as e:
                logger.debug(f"  child_window AutomationId hatası: {type(e).__name__}")

            # YÖNTEM 2: child_window() ile Name araması (timeout artırıldı: 0.2 → 0.8)
            try:
                rapor_btn = self.main_window.child_window(
                    title="Rapor",
                    control_type="Button"
                )
                if rapor_btn.exists(timeout=0.8):
                    logger.info("  ✓ Rapor butonu bulundu (child_window Name)")
                    try:
                        rapor_btn.invoke()
                        logger.info("✅ Rapor butonu tıklandı (invoke - Name)")
                        self.timed_sleep("rapor_button_wait", 0.1)
                        return True
                    except Exception:
                        rapor_btn.click_input()
                        logger.info("✅ Rapor butonu tıklandı (click_input - Name)")
                        self.timed_sleep("rapor_button_wait", 0.1)
                        return True
            except Exception as e:
                logger.debug(f"  child_window Name hatası: {type(e).__name__}")

            # YÖNTEM 3: descendants() ile AutomationId araması (YAVAŞ FALLBACK)
            try:
                rapor_buttons = self.main_window.descendants(
                    auto_id="f:buttonRaporListesi",
                    control_type="Button"
                )
                if rapor_buttons and len(rapor_buttons) > 0:
                    logger.info("  ✓ Rapor butonu bulundu (descendants AutomationId)")
                    try:
                        rapor_buttons[0].invoke()
                        logger.info("✅ Rapor butonu tıklandı (invoke)")
                        self.timed_sleep("rapor_button_wait", 0.1)
                        return True
                    except Exception as inv_err:
                        logger.debug(f"  invoke() hatası: {type(inv_err).__name__}")
                        try:
                            rapor_buttons[0].click_input()
                            logger.info("✅ Rapor butonu tıklandı (click_input)")
                            self.timed_sleep("rapor_button_wait", 0.1)
                            return True
                        except Exception as clk_err:
                            logger.warning(f"  click_input() hatası: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"  descendants() AutomationId hatası: {type(e).__name__}")

            # YÖNTEM 4: descendants() ile Name araması (FALLBACK)
            try:
                rapor_buttons = self.main_window.descendants(
                    title="Rapor",
                    control_type="Button"
                )
                if rapor_buttons and len(rapor_buttons) > 0:
                    logger.info("  ✓ Rapor butonu bulundu (descendants Name)")
                    try:
                        rapor_buttons[0].invoke()
                        logger.info("✅ Rapor butonu tıklandı (invoke - Name)")
                        self.timed_sleep("rapor_button_wait", 0.1)
                        return True
                    except Exception as inv_err:
                        try:
                            rapor_buttons[0].click_input()
                            logger.info("✅ Rapor butonu tıklandı (click_input - Name)")
                            self.timed_sleep("rapor_button_wait", 0.1)
                            return True
                        except Exception as clk_err:
                            logger.warning(f"  Tüm tıklama yöntemleri başarısız: {type(clk_err).__name__}")
            except Exception as e:
                logger.debug(f"  descendants() Name hatası: {type(e).__name__}")

            # YÖNTEM 3: Tüm butonları listele ve "Rapor" içereni bul (FALLBACK)
            try:
                logger.info("  → Tüm butonlar arasında 'Rapor' aranıyor...")
                all_buttons = self.main_window.descendants(control_type="Button")
                logger.info(f"  → Toplam {len(all_buttons)} buton bulundu")
                for btn in all_buttons:
                    try:
                        btn_name = btn.window_text()
                        if btn_name and "Rapor" in btn_name:
                            logger.info(f"  ✓ Rapor butonu bulundu: '{btn_name}'")
                            try:
                                btn.invoke()
                                logger.info("✅ Rapor butonu tıklandı (text search)")
                                self.timed_sleep("rapor_button_wait", 0.1)
                                return True
                            except Exception:
                                btn.click_input()
                                logger.info("✅ Rapor butonu tıklandı (click_input - text search)")
                                self.timed_sleep("rapor_button_wait", 0.1)
                                return True
                    except Exception as btn_err:
                        continue
            except Exception as e:
                logger.debug(f"  Buton arama hatası: {type(e).__name__}")

            # YÖNTEM 4: from_point() ile koordinattan element bul (koordinat tıklama DEĞİL!)
            # Butonun koordinatını kullanarak elementi bulup invoke() yapar
            # UIElementInspector (1 Aralık 2025): Ekran={l:656 t:203 r:731 b:222}, Width=75, Height=19
            # ÖNEMLİ: Bu koordinatlar IE_Server penceresine göre relative!
            logger.warning("  UIA aramaları başarısız, from_point() deneniyor...")
            try:
                from pywinauto import Desktop
                desktop = Desktop(backend="uia")

                # Önce IE_Server penceresini bul ve onun koordinatlarını al
                ie_server_rect = None
                try:
                    ie_server = self.main_window.child_window(class_name="Internet Explorer_Server")
                    if ie_server.exists(timeout=0.2):
                        ie_server_rect = ie_server.rectangle()
                        logger.info(f"  → IE_Server rect: left={ie_server_rect.left}, top={ie_server_rect.top}")
                except Exception:
                    pass

                # IE_Server bulunamadıysa ana pencereyi kullan
                if ie_server_rect:
                    base_rect = ie_server_rect
                else:
                    base_rect = self.main_window.rectangle()
                    logger.info(f"  → Ana pencere rect: left={base_rect.left}, top={base_rect.top}")

                # Buton merkez koordinatı (pencere içi relative)
                btn_center_x = 289 + 37  # X + Width/2 = 326
                btn_center_y = 76 + 9    # Y + Height/2 = 85

                # Ekran koordinatına çevir
                screen_x = base_rect.left + btn_center_x
                screen_y = base_rect.top + btn_center_y

                logger.info(f"  → from_point() koordinatı: ({screen_x}, {screen_y})")

                # Koordinattan element bul
                element = desktop.from_point(screen_x, screen_y)
                if element:
                    elem_name = element.window_text() if hasattr(element, 'window_text') else ''
                    logger.info(f"  ✓ Element bulundu: '{elem_name}'")

                    # Rapor butonu mu kontrol et
                    if "Rapor" in elem_name or elem_name == "":
                        try:
                            element.invoke()
                            logger.info("✅ Rapor butonu tıklandı (from_point + invoke)")
                            self.timed_sleep("rapor_button_wait", 0.1)
                            return True
                        except Exception as inv_err:
                            logger.debug(f"  invoke hatası: {type(inv_err).__name__}")
                            try:
                                element.click_input()
                                logger.info("✅ Rapor butonu tıklandı (from_point + click_input)")
                                self.timed_sleep("rapor_button_wait", 0.1)
                                return True
                            except Exception as clk_err:
                                logger.warning(f"  click_input hatası: {type(clk_err).__name__}")
            except Exception as fp_err:
                logger.debug(f"  from_point() hatası: {type(fp_err).__name__}: {fp_err}")

            # YÖNTEM 5: Keyboard navigation - TAB ile butona git, ENTER bas (SON ÇARE)
            logger.warning("  from_point() başarısız, keyboard navigation deneniyor...")
            try:
                from pywinauto.keyboard import send_keys
                # Önce pencereye odaklan
                self.main_window.set_focus()
                self.timed_sleep("adim_arasi_bekleme", 0.3)

                # Sayfadaki butonlara TAB ile git
                # Rapor butonu genellikle ilk butonlardan biri
                for tab_count in range(10):  # Maksimum 10 TAB
                    send_keys("{TAB}")
                    time.sleep(0.1)

                    # Aktif elementin adını kontrol et
                    try:
                        focused = self.main_window.get_focus()
                        if focused:
                            focused_name = focused.window_text()
                            logger.debug(f"  TAB {tab_count+1}: '{focused_name}'")
                            if "Rapor" in focused_name:
                                logger.info(f"  ✓ Rapor butonuna TAB ile ulaşıldı ({tab_count+1} TAB)")
                                send_keys("{ENTER}")
                                logger.info("✅ Rapor butonu tıklandı (TAB + ENTER)")
                                self.timed_sleep("rapor_button_wait", 0.1)
                                return True
                    except Exception:
                        continue

                logger.warning("  TAB ile Rapor butonuna ulaşılamadı")
            except Exception as kb_err:
                logger.debug(f"  Keyboard navigation hatası: {type(kb_err).__name__}")

            # Hiçbir yöntem çalışmadı
            logger.error("❌ Rapor butonu bulunamadı veya tıklanamadı!")
            return False

        except Exception as e:
            logger.error(f"❌ Rapor butonuna tıklama hatası: {e}", exc_info=True)
            return False

    def rapor_listesini_topla(self):
        """
        Rapor listesi penceresini açar ve hasta rapor bilgilerini toplar.

        Tablo yapısı (HTML'den):
        - Hak Sahibi Bilgileri: TC, Ad/Soyad, Cinsiyet, Doğum Tarihi
        - Raporlar tablosu: Rapor Takip No | Rapor No | Başlangıç | Bitiş | Kayıt Şekli | Tanı

        Returns:
            dict: {
                'ad_soyad': str,
                'telefon': str,
                'raporlar': [{'tani': str, 'bitis_tarihi': str}, ...]
            }
            None: Veri toplanamadıysa
        """
        try:
            # Rapor butonuna tıkla (retry_with_popup_check ile - REÇETE NOTU vb. popup kontrolü)
            logger.info("🔵 Rapor butonuna tıklanıyor...")
            rapor_btn_basarili = self.retry_with_popup_check(
                lambda: self.rapor_butonuna_tikla(),
                "Rapor butonu",
                max_retries=5,
                critical=False  # Rapor butonu başarısız olursa None döner, sistemsel hata fırlatma
            )
            if not rapor_btn_basarili:
                logger.warning("⚠️ Rapor butonuna tıklanamadı")
                return None

            logger.info("✓ Rapor butonuna tıklandı")

            # Rapor listesi sayfasının yüklenmesini bekle (RaporListe.jsp)
            # Bekleme süresi artırıldı çünkü sayfa tamamen yeniden yükleniyor
            rapor_pencere_acik = False
            max_bekle = 5  # maksimum 5 saniye bekle
            for bekle_idx in range(max_bekle * 2):  # 0.5 saniye aralıklarla kontrol
                self.timed_sleep("rapor_pencere_acilis", 0.5)

                # ★ Her döngüde kritik popup kontrolü (REÇETE NOTU dahil) ★
                try:
                    if self.kritik_popup_kontrol_ve_kapat():
                        logger.info("✓ Rapor bekleme sırasında kritik popup kapatıldı")
                except Exception:
                    pass

                try:
                    all_texts = self.main_window.descendants(control_type="Text")
                    for t in all_texts[:100]:  # İlk 100 text'e bak
                        try:
                            text = t.window_text()
                            # "Rapor Listesi" başlığı veya "Hak Sahibi Bilgileri" rapor sayfası işareti
                            if "Rapor Listesi" in text:
                                rapor_pencere_acik = True
                                logger.info(f"✓ Rapor Listesi sayfası yüklendi ({(bekle_idx+1)*0.5:.1f}s)")
                                break
                            # Alternatif: 9 haneli rapor takip numarası var mı?
                            if text.isdigit() and len(text) == 9:
                                rapor_pencere_acik = True
                                logger.info(f"✓ Rapor verisi tespit edildi ({(bekle_idx+1)*0.5:.1f}s)")
                                break
                        except Exception as text_err:
                            logger.debug(f"Text okuma hatası: {type(text_err).__name__}")
                            continue
                    if rapor_pencere_acik:
                        break
                except Exception as desc_err:
                    logger.debug(f"Descendants hatası: {type(desc_err).__name__}")

            if not rapor_pencere_acik:
                logger.warning("⚠️ Rapor Listesi sayfası yüklenemedi, yine de okumayı deneyelim...")

            # Telefon numarasını ana pencereden al
            telefon = self.telefon_numarasi_oku()
            logger.info(f"📞 Telefon: {telefon}")

            # Hasta adını "Hak Sahibi Bilgileri" bölümünden al
            ad_soyad = self._hak_sahibi_adini_oku()
            logger.info(f"👤 Hasta adı: {ad_soyad}")

            # Rapor tablosunu bul ve verileri topla
            raporlar = []
            try:
                # YENİ YAKLAŞIM: Rapor tablosundaki satırları doğrudan Text elementlerinden bul
                # HTML'deki rapor tablosu ID pattern'i: form1:tableExRaporTeshisList:X:textYY
                # Satır elementleri: text14 (RaporTakipNo), text99 (RaporNo), text98 (Başlangıç), text97 (Bitiş), text96 (Tanı)

                all_texts = self.main_window.descendants(control_type="Text")
                logger.info(f"🔍 Toplam {len(all_texts)} Text elementi bulundu")

                # Önce "Rapor Listesi" sayfasında mıyız kontrol et
                rapor_listesi_sayfasi = False
                for t in all_texts[:100]:
                    try:
                        text = t.window_text()
                        if "Rapor Listesi" in text or "Hak Sahibi Bilgileri" in text:
                            rapor_listesi_sayfasi = True
                            logger.info(f"✓ Rapor Listesi sayfası tespit edildi")
                            break
                    except Exception as text_err:
                        logger.debug(f"Rapor listesi text okuma hatası: {type(text_err).__name__}")
                        continue

                if not rapor_listesi_sayfasi:
                    logger.warning("⚠️ Rapor Listesi sayfası bulunamadı")

                # Rapor satırlarını topla - Her satır için: RaporTakipNo, RaporNo, Başlangıç, Bitiş, KayıtŞekli, Tanı
                # Pattern: Ardışık Text elementleri içinde rapor verisi ara
                rapor_satir_verileri = []
                current_row = []

                for t in all_texts:
                    try:
                        text = t.window_text().strip()
                        if not text:
                            continue

                        # Rapor satırı pattern'i: 9 haneli sayı ile başlayan satırlar (Rapor Takip No)
                        if text.isdigit() and len(text) == 9:
                            # Yeni rapor satırı başlangıcı
                            if current_row and len(current_row) >= 4:
                                rapor_satir_verileri.append(current_row)
                            current_row = [text]
                        elif current_row:
                            # Mevcut satıra ekle (6-7 hücrelik tablo)
                            if len(current_row) < 8:
                                current_row.append(text)
                    except Exception as row_err:
                        logger.debug(f"Rapor satır okuma hatası: {type(row_err).__name__}")
                        continue

                # Son satırı ekle
                if current_row and len(current_row) >= 4:
                    rapor_satir_verileri.append(current_row)

                logger.info(f"📊 {len(rapor_satir_verileri)} potansiyel rapor satırı bulundu")

                # Her satırı parse et
                for row_idx, row_data in enumerate(rapor_satir_verileri):
                    try:
                        logger.info(f"  🔍 Satır {row_idx+1}: {row_data}")
                        rapor = self._parse_rapor_satiri_v2(row_data)
                        if rapor:
                            raporlar.append(rapor)
                            logger.info(f"  ✓ Rapor {len(raporlar)}: {rapor['tani'][:50]}... | {rapor['bitis_tarihi']}")
                    except Exception as row_err:
                        logger.debug(f"Satır okuma hatası: {row_err}")

                # Eğer yeni yöntem başarısız olduysa, eski yöntemi dene
                if not raporlar:
                    logger.info("🔄 Alternatif yöntem deneniyor (Table aramasi)...")
                    raporlar = self._rapor_tablosu_eski_yontem()

            except Exception as e:
                logger.error(f"Rapor tablosu okuma hatası: {e}")

            # Rapor sayfasından çıkış - Sonraki butonu ile bir sonraki reçeteye geç
            # NOT: Geri Dön yerine Sonraki butonuna basılıyor (kullanıcı talebi)
            try:
                sonraki_clicked = False
                buttons = self.main_window.descendants(control_type="Button")
                for btn in buttons:
                    try:
                        btn_text = btn.window_text()
                        # Sonraki veya SONRA butonu ara
                        if "Sonraki" in btn_text or "SONRA" in btn_text or btn_text == ">":
                            btn.click_input()
                            sonraki_clicked = True
                            logger.info("✓ Rapor sayfasından Sonraki butonu ile çıkıldı")
                            break
                    except Exception as btn_err:
                        logger.debug(f"Sonraki butonu hatası: {type(btn_err).__name__}")
                        continue

                if not sonraki_clicked:
                    # NOT: Rapor sayfası ESC ile kapanmaz!
                    # Sonraki butonu bulunamadıysa sadece uyarı ver
                    logger.warning("⚠️ Sonraki butonu bulunamadı, rapor sayfası açık kalabilir")

                self.timed_sleep("pencere_kapatma", 0.5)
            except Exception as e:
                logger.debug(f"Rapor sayfası kapatma hatası: {e}")

            # Veri döndür
            if raporlar:
                logger.info(f"✅ Toplam {len(raporlar)} rapor toplandı - Hasta: {ad_soyad}")
                return {
                    'ad_soyad': ad_soyad,
                    'telefon': telefon,
                    'raporlar': raporlar,
                    'sonraki_basildi': sonraki_clicked  # Sonraki butonu basıldı mı?
                }
            else:
                logger.warning(f"⚠️ Hiç rapor verisi toplanamadı - Hasta: {ad_soyad}, Telefon: {telefon}")
                logger.warning(f"   Tablo sayısı: {len(tables) if 'tables' in locals() else 'bilinmiyor'}")
                return {
                    'ad_soyad': ad_soyad,
                    'telefon': telefon,
                    'raporlar': [],
                    'sonraki_basildi': sonraki_clicked  # Sonraki butonu basıldı mı?
                }

        except Exception as e:
            logger.error(f"❌ Rapor toplama hatası: {e}", exc_info=True)
            # NOT: Rapor sayfası ESC ile kapanmaz, sadece hata logla
            return None

    def _hak_sahibi_adini_oku(self):
        """Hak Sahibi Bilgileri bölümünden hasta adını okur."""
        try:
            # Tüm Text elemanlarını tara
            all_texts = self.main_window.descendants(control_type="Text")

            # Ad ve soyad için aday değerleri topla
            ad_aday = None
            soyad_aday = None

            for i, elem in enumerate(all_texts):
                try:
                    text = elem.window_text().strip()

                    # "Adı / Soyadı" label'ından sonraki değerleri ara
                    if "Adı" in text and "Soyadı" in text:
                        # Sonraki 2-3 Text elemanı ad ve soyad olabilir
                        for j in range(1, 5):
                            if i + j < len(all_texts):
                                next_text = all_texts[i + j].window_text().strip()
                                # Boş değil, ":" değil, ve kısa bir kelime ise
                                if next_text and next_text != ":" and len(next_text) < 30:
                                    # Sayı veya özel karakter içermiyorsa
                                    if next_text.replace(" ", "").isalpha():
                                        if not ad_aday:
                                            ad_aday = next_text
                                        elif not soyad_aday:
                                            soyad_aday = next_text
                                            break
                        if ad_aday and soyad_aday:
                            break
                except Exception:
                    continue

            if ad_aday and soyad_aday:
                ad_soyad = f"{ad_aday} {soyad_aday}"
                logger.info(f"📝 Hasta adı bulundu: {ad_soyad}")
                return ad_soyad

            logger.debug("Hasta adı bulunamadı, 'Bilinmeyen' kullanılacak")
            return "Bilinmeyen"

        except Exception as e:
            logger.debug(f"Hak sahibi adı okuma hatası: {e}")
            return "Bilinmeyen"

    def _parse_rapor_satiri(self, cell_values):
        """
        Rapor tablosu satırını parse eder.

        Esnek parsing: Farklı tablo formatlarını destekler
        Minimum gereksinim: Tarih ve tanı olması
        """
        if not cell_values or len(cell_values) < 2:
            return None

        # Geçersiz satırları filtrele (uyarı mesajları, header vs.)
        text_combined = " ".join(cell_values)
        invalid_patterns = [
            "Hak sahibi bilgileri", "güncel değil", "SGK Sosyal", "Müstehaklık",
            "T.C. Kimlik", "Cinsiyeti", "Rapor Takip No", "Başlangıç Tarihi",
            "Bitiş Tarihi", "Kayıt Şekli", "Adı / Soyadı", "başvurunuz", "Telefon"
        ]
        if any(pattern.lower() in text_combined.lower() for pattern in invalid_patterns):
            return None

        # Geçerli rapor tarihlerini bul (2020 ve sonrası)
        tarihler = []
        tarih_indexler = []
        for idx, val in enumerate(cell_values):
            if self._is_tarih(val):
                yil = int(val.split("/")[2])
                if yil >= 2020:
                    tarihler.append(val)
                    tarih_indexler.append(idx)

        if not tarihler:
            return None

        # DEBUG: Tarih bulunan satırları logla
        logger.info(f"    📅 Tarihli satır: {cell_values[:4]}...")

        # Bitiş tarihi: İkinci tarih (veya tek varsa o)
        if len(tarihler) >= 2:
            bitis_tarihi = tarihler[1]
            son_tarih_idx = tarih_indexler[1]
        else:
            bitis_tarihi = tarihler[0]
            son_tarih_idx = tarih_indexler[0]

        # Tanı: ICD kodu pattern'ine uyan ilk değeri bul
        # Veya uzun metin (hastalık açıklaması) olabilir
        tani = None
        for val in cell_values:
            # ICD pattern: "XX.XX - Hastalık" veya "XX.XX.X - Hastalık"
            if " - " in val and len(val) > 10:
                # İlk kısım sayı/nokta içermeli
                first_part = val.split(" - ")[0].strip()
                if any(c.isdigit() for c in first_part[:5]):
                    # Elektronik Rapor değilse tanı olarak al
                    if "Elektronik" not in val and "İmzalı" not in val:
                        tani = val
                        break

        # Eğer ICD formatında bulamadıysak, en uzun metni tanı olarak al
        if not tani:
            for val in cell_values:
                # Tarih değilse ve uzunsa tanı olabilir
                if not self._is_tarih(val) and len(val) > 15 and not val.isdigit():
                    if "Elektronik" not in val and "İmzalı" not in val:
                        tani = val
                        break

        if not tani:
            logger.debug(f"    ❌ Tanı bulunamadı: {cell_values}")
            return None

        return {
            'tani': tani,
            'bitis_tarihi': bitis_tarihi
        }

    def _is_tarih(self, val):
        """Değerin DD/MM/YYYY formatında tarih olup olmadığını kontrol eder."""
        if not val or "/" not in val:
            return False
        parts = val.split("/")
        if len(parts) != 3:
            return False
        try:
            gun, ay, yil = parts
            return (len(gun) == 2 and len(ay) == 2 and len(yil) == 4 and
                    gun.isdigit() and ay.isdigit() and yil.isdigit())
        except Exception:
            return False

    def _parse_rapor_satiri_v2(self, row_data):
        """
        Yeni rapor satırı parse fonksiyonu.

        row_data yapısı (HTML'den alınan sıra):
        [0] RaporTakipNo (9 haneli sayı, örn: 500640940)
        [1] RaporNo (7 haneli sayı, örn: 1469653)
        [2] Başlangıç Tarihi (DD/MM/YYYY)
        [3] Bitiş Tarihi (DD/MM/YYYY)
        [4] Kayıt Şekli (Elektronik İmzalı Rapor)
        [5] Tanı (07.01.3 - Diabetes Insipitus(E23.2))
        """
        if not row_data or len(row_data) < 4:
            return None

        try:
            # row_data: ['500640940', '1469653', '14/04/2025', '13/04/2027', 'Elektronik İmzalı Rapor', '07.01.3 - Diabetes Insipitus(E23.2)']

            # Bitiş tarihi bul (tarih formatındaki değerlerden ikincisi)
            tarihler = [v for v in row_data if self._is_tarih(v)]
            if len(tarihler) >= 2:
                bitis_tarihi = tarihler[1]  # İkinci tarih = bitiş tarihi
            elif len(tarihler) == 1:
                bitis_tarihi = tarihler[0]
            else:
                logger.debug(f"  ❌ Tarih bulunamadı: {row_data}")
                return None

            # Tanı bul - ICD kodu pattern'i: XX.XX - Hastalık veya XX.XX.X - Hastalık
            tani = None
            for val in row_data:
                # ICD pattern kontrolü
                if " - " in val and len(val) > 10:
                    first_part = val.split(" - ")[0].strip()
                    # İlk kısım sayı/nokta içermeli (örn: 07.01.3, 20.02)
                    if any(c.isdigit() for c in first_part[:5]):
                        if "Elektronik" not in val and "İmzalı" not in val:
                            tani = val
                            break

            # ICD formatı yoksa, uzun metin ara
            if not tani:
                for val in row_data:
                    if not self._is_tarih(val) and len(val) > 15 and not val.isdigit():
                        if "Elektronik" not in val and "İmzalı" not in val and "Rapor" not in val:
                            tani = val
                            break

            if not tani:
                logger.debug(f"  ❌ Tanı bulunamadı: {row_data}")
                return None

            # Bitiş tarihinin güncelliğini kontrol et (geçmemiş olmalı)
            from datetime import datetime
            try:
                bitis_date = datetime.strptime(bitis_tarihi, "%d/%m/%Y")
                if bitis_date < datetime.now():
                    logger.debug(f"  ⏰ Süresi geçmiş rapor: {bitis_tarihi}")
                    # Süresi geçmiş raporları da kaydet ama işaretle
                    pass
            except ValueError as date_err:
                logger.debug(f"Tarih parse hatası ({bitis_tarihi}): {date_err}")

            return {
                'tani': tani,
                'bitis_tarihi': bitis_tarihi
            }

        except Exception as e:
            logger.debug(f"  ❌ Parse hatası: {e}")
            return None

    def _rapor_tablosu_eski_yontem(self):
        """Eski tablo arama yöntemi (fallback)"""
        raporlar = []
        try:
            # Table elementlerini bul
            tables = self.main_window.descendants(control_type="Table")
            logger.info(f"  📊 Eski yöntem: {len(tables)} Table bulundu")

            for table_idx, table in enumerate(tables):
                try:
                    # Tablonun içindeki tüm Text'leri al
                    texts = table.descendants(control_type="Text")
                    text_values = [t.window_text().strip() for t in texts if t.window_text().strip()]

                    # "Rapor Takip No" header'ı var mı kontrol et (doğru tablo mu?)
                    if not any("Rapor Takip" in v or "Tanı" in v for v in text_values[:20]):
                        continue

                    logger.info(f"  ✓ Rapor tablosu bulundu (Tablo {table_idx+1})")

                    # Text değerlerini grupla (9 haneli sayı = yeni satır başlangıcı)
                    current_row = []
                    for val in text_values:
                        if val.isdigit() and len(val) == 9:
                            if current_row and len(current_row) >= 4:
                                rapor = self._parse_rapor_satiri_v2(current_row)
                                if rapor:
                                    raporlar.append(rapor)
                            current_row = [val]
                        elif current_row and len(current_row) < 8:
                            current_row.append(val)

                    # Son satır
                    if current_row and len(current_row) >= 4:
                        rapor = self._parse_rapor_satiri_v2(current_row)
                        if rapor:
                            raporlar.append(rapor)

                    if raporlar:
                        break

                except Exception as table_err:
                    logger.debug(f"  Tablo okuma hatası: {table_err}")

        except Exception as e:
            logger.debug(f"  Eski yöntem hatası: {e}")

        return raporlar

    def hasta_ad_soyad_oku(self):
        """Ana pencereden hasta ad soyad okur"""
        try:
            texts = self.main_window.descendants(control_type="Text")
            for text in texts:
                try:
                    text_value = text.window_text()
                    if text_value and len(text_value.split()) >= 2 and len(text_value) > 5:
                        return text_value.strip()
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")
        except Exception as e:
            logger.debug(f"Operation failed: {type(e).__name__}")
        return "Bilinmeyen"

    def telefon_numarasi_oku(self):
        """Ana pencereden telefon numarası okur"""
        try:
            # Önce lblMusteriTelefonu alanını kontrol et (en güvenilir)
            texts = self.main_window.descendants(control_type="Text")
            for text in texts:
                try:
                    auto_id = text.automation_id() if hasattr(text, 'automation_id') else None
                    if auto_id and 'Telefon' in auto_id:
                        text_value = text.window_text()
                        if text_value:
                            # "C:(544) 611 1522" gibi formatları temizle
                            clean_phone = text_value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace("C:", "").replace("c:", "")
                            if clean_phone.isdigit() and len(clean_phone) >= 10:
                                logger.debug(f"Telefon bulundu (auto_id): {auto_id} = {clean_phone}")
                                return clean_phone
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            # Alternatif: Edit kontrollerinden ara
            edits = self.main_window.descendants(control_type="Edit")
            for edit in edits:
                try:
                    edit_value = edit.window_text()
                    if edit_value:
                        clean_phone = edit_value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace("C:", "").replace("c:", "")
                        if clean_phone.isdigit() and len(clean_phone) >= 10:
                            logger.debug(f"Telefon bulundu (Edit): {clean_phone}")
                            return clean_phone
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")
        except Exception as e:
            logger.debug(f"Operation failed: {type(e).__name__}")
        return ""

    def tesis_numarasi_oku(self):
        """
        Reçete sayfasından tesis numarasını oku.
        HTML Element: INPUT id="f:t33", class="inputText"

        UI Automation bu elementin AutomationId'sini görmüyor (boş).
        MSHTML COM ile Internet Explorer_Server'dan HTML DOM'a erişerek okur.

        Returns:
            str: Tesis numarası veya "" (boş string)
        """
        try:
            # MSHTML COM ile HTML DOM'a eriş
            import win32com.client
            import pythoncom

            # Internet Explorer_Server window handle'ını bul
            ie_server = self.main_window.child_window(class_name="Internet Explorer_Server")
            if not ie_server.exists(timeout=0.5):
                logger.debug("Tesis okuma: Internet Explorer_Server bulunamadı")
                return ""

            hwnd = ie_server.handle

            # WM_HTML_GETOBJECT mesajı ile IHTMLDocument2 al
            msg = win32gui.RegisterWindowMessage("WM_HTML_GETOBJECT")
            result = ctypes.c_long(0)
            retval = ctypes.windll.user32.SendMessageTimeoutW(
                hwnd, msg, 0, 0,
                0x0002,  # SMTO_ABORTIFHUNG
                2000,    # 2 saniye timeout
                ctypes.byref(result)
            )

            if not retval or result.value == 0:
                logger.debug("Tesis okuma: WM_HTML_GETOBJECT başarısız")
                return ""

            # IID_IDispatch GUID bytes
            iid_bytes = bytes(pythoncom.IID_IDispatch)
            guid = (ctypes.c_byte * 16)(*iid_bytes)

            ptr = ctypes.c_void_p()
            hr = ctypes.oledll.oleacc.ObjectFromLresult(
                result.value,
                ctypes.byref(guid),
                0,
                ctypes.byref(ptr)
            )

            if hr != 0 or not ptr.value:
                logger.warning(f"Tesis okuma: ObjectFromLresult başarısız (hr=0x{hr:08X})")
                return ""

            # IDispatch pointer'ından COM object oluştur
            doc_dispatch = pythoncom.ObjectFromAddress(ptr.value, pythoncom.IID_IDispatch)
            html_doc = win32com.client.Dispatch(doc_dispatch)

            # getElementById ile f:t33 elementini bul
            elem = html_doc.getElementById("f:t33")
            if elem:
                deger = elem.value
                if deger:
                    deger = str(deger).strip()
                    logger.info(f"Tesis numarası: {deger}")
                    return deger
                else:
                    logger.debug("Tesis okuma: f:t33 değeri boş")
                    return ""
            else:
                logger.warning("Tesis okuma: f:t33 elementi bulunamadı")
                return ""

        except Exception as e:
            logger.error(f"Tesis numarası okuma hatası: {type(e).__name__}: {e}")
            return ""

    def tum_butonlari_listele(self):
        """Debug için penceredeki tüm butonları listele"""
        try:
            logger.info("Penceredeki tüm butonlar listeleniyor...")
            buttons = self.main_window.descendants(control_type="Button")

            if buttons and len(buttons) > 0:
                logger.info(f"Toplam {len(buttons)} buton bulundu:")
                for i, btn in enumerate(buttons, 1):
                    try:
                        btn_name = btn.window_text()
                        if btn_name:
                            logger.info(f"  {i}. Buton: '{btn_name}'")
                    except Exception as e:
                        logger.debug(f"Operation failed: {type(e).__name__}")
            else:
                logger.warning("Hiç buton bulunamadı")
        except Exception as e:
            logger.error(f"Buton listeleme hatası: {e}")

    def pencere_bilgilerini_goster(self):
        """Debug için pencere bilgilerini göster"""
        try:
            if self.main_window:
                logger.info("Pencere Bilgileri:")
                logger.info(f"  Başlık: {self.main_window.window_text()}")
                logger.info(f"  Class: {self.main_window.class_name()}")
                self.main_window.print_control_identifiers()
        except Exception as e:
            logger.error(f"Bilgi gösterme hatası: {e}")


def tek_recete_isle(bot, recete_sira_no, rapor_takip, grup="", session_logger=None, stop_check=None, onceden_okunan_recete_no=None, onceki_recete_no=None, fonksiyon_ayarlari=None):
    """
    Tek bir reçete için tüm işlemleri yap

    Args:
        bot: BotanikBot instance
        recete_sira_no: Reçete sıra numarası (1, 2, 3...)
        rapor_takip: RaporTakip instance (CSV kaydı için)
        grup: Grup bilgisi (A, B, C, GK) (varsayılan: "")
        session_logger: SessionLogger instance (oturum logları için, opsiyonel)
        stop_check: Durdurma kontrolü için callback fonksiyonu (True dönerse işlem durur)
        onceden_okunan_recete_no: GUI'de zaten okunan reçete numarası (tekrar okumayı önler)
        onceki_recete_no: Bir önceki işlenen reçete numarası (ardışık aynı reçete kontrolü için)
        fonksiyon_ayarlari: Dict - hangi fonksiyonların aktif olduğu
            - ilac_takip_aktif: bool
            - rapor_toplama_aktif: bool
            - rapor_kontrol_aktif: bool

    Returns:
        tuple: (başarı durumu: bool, medula reçete no: str veya None, takip sayısı: int, hata nedeni: str veya None)
    """
    # Varsayılan fonksiyon ayarları
    if fonksiyon_ayarlari is None:
        fonksiyon_ayarlari = {
            "ilac_takip_aktif": True,
            "rapor_toplama_aktif": True,
            "rapor_kontrol_aktif": True
        }

    ilac_takip_aktif = fonksiyon_ayarlari.get("ilac_takip_aktif", True)
    rapor_toplama_aktif = fonksiyon_ayarlari.get("rapor_toplama_aktif", True)
    rapor_kontrol_aktif = fonksiyon_ayarlari.get("rapor_kontrol_aktif", True)

    # Durdurma kontrolü helper fonksiyonu
    def should_stop():
        """Stop_check callback varsa kontrol et, True dönerse durulmalı"""
        if stop_check and callable(stop_check):
            return stop_check()
        return False
    recete_baslangic = time.time()
    adim_sureleri = []

    def log_sure(ad, baslangic, timing_key=None):
        """Bir adımın süresini kaydet ve yazdır."""
        sure = time.time() - baslangic
        adim_sureleri.append((ad, sure))
        logger.info(f"⏱ {ad}: {sure:.2f}s")

        # Timing istatistiğine kaydet
        if timing_key:
            from timing_settings import get_timing_settings
            timing = get_timing_settings()
            timing.kayit_ekle(timing_key, sure)

        return sure

    medula_recete_no = None
    takip_sayisi = 0  # Takip edilen ilaç sayısı
    baslik_loglandi = False

    def log_recete_baslik(no_degeri=None):
        """Üst başlıkta Reçete sıra ve numarasını göster."""
        nonlocal baslik_loglandi
        if baslik_loglandi:
            return
        no_text = no_degeri if no_degeri else (medula_recete_no if medula_recete_no else "-")
        logger.info(f"📋 REÇETE {recete_sira_no} | No: {no_text}")
        baslik_loglandi = True

    # DURDURMA KONTROLÜ - başlangıçta
    if should_stop():
        logger.info("⏸ İşlem durduruldu (kullanıcı talebi)")
        return (False, None, 0, "Kullanıcı tarafından durduruldu")

    # OPTİMİZE: Ardışık aynı reçete kontrolü (SONRA basınca aynı reçete gelirse = "Reçete kaydı bulunamadı")
    # Sadece aynı reçete numarası geldiğinde hızlı kontrol yap, farklıysa atla
    if onceki_recete_no and onceden_okunan_recete_no and onceki_recete_no == onceden_okunan_recete_no:
        # Aynı reçete numarası → "Reçete kaydı bulunamadı" uyarısı var mı kontrol et
        adim_baslangic = time.time()
        recete_kaydi_var = bot.recete_kaydi_var_mi_kontrol_hizli()
        log_sure("Reçete kontrolü (aynı no)", adim_baslangic, "recete_kontrol")
        if not recete_kaydi_var:
            logger.error("❌ Reçete kaydı yok (ardışık aynı numara)")
            log_recete_baslik()
            return (False, medula_recete_no, takip_sayisi, "Reçete kaydı bulunamadı")

    # Reçete notu ve uyarı kontrolü KALDIRILDI - retry mekanizması gerektiğinde yapacak

    # ===== BİRLEŞİK KONTROL: TESİS + TELEFON + AYNI REÇETE (TEK DÖNGÜ) =====
    # 1) Yasaklı tesis → atla
    # 2) Telefon yok → atla
    # 3) SONRA basıldıktan sonra aynı reçete geldi mi → son reçete kontrolü
    from medula_settings import get_medula_settings
    medula_settings = get_medula_settings()
    telefonsuz_atla = medula_settings.get("telefonsuz_atla", False)
    yasakli_tesisler = medula_settings.get("yasakli_tesis_numaralari", [])
    tesis_kontrolu_aktif = (grup == "B" and len(yasakli_tesisler) > 0)

    # Kontrol gerekiyor mu?
    if tesis_kontrolu_aktif or telefonsuz_atla:
        atlanan_sayisi = 0
        max_atlama = 50  # Sonsuz döngü koruması
        onceki_loop_recete = onceden_okunan_recete_no  # İlk reçete no (varsa)
        loop_hizli_sonuc = None  # Önceki iterasyondan kalan hızlı tarama sonucu

        while atlanan_sayisi < max_atlama:
            if should_stop():
                return (False, None, 0, "Kullanıcı tarafından durduruldu")

            atlama_nedeni = None
            current_recete = None

            # 1) TESİS KONTROLÜ (hızlı - tek element MSHTML okuma)
            if tesis_kontrolu_aktif:
                adim_baslangic = time.time()
                tesis_no = bot.tesis_numarasi_oku()
                log_sure("Tesis no okuma", adim_baslangic, "tesis_kontrol")

                if tesis_no and tesis_no in yasakli_tesisler:
                    atlama_nedeni = f"yasaklı tesis: {tesis_no}"

            # 2) TELEFON KONTROLÜ + REÇETE NO (tek hızlı taramada ikisi birden)
            if not atlama_nedeni and telefonsuz_atla:
                adim_baslangic = time.time()
                hizli_sonuc = bot.recete_sayfasi_hizli_tarama(max_deneme=2, bekleme_suresi=0.15)
                if hizli_sonuc:
                    telefon_var = hizli_sonuc['telefon_var']
                    current_recete = hizli_sonuc.get('recete_no')
                    loop_hizli_sonuc = hizli_sonuc
                    log_sure("Telefon+Reçete kontrolü (hızlı)", adim_baslangic, "telefon_kontrol")
                else:
                    birlesik_sonuc = bot.recete_telefon_kontrol_birlesik(max_deneme=2, bekleme_suresi=0.2)
                    telefon_var = birlesik_sonuc['telefon_var']
                    current_recete = birlesik_sonuc.get('recete_no')
                    log_sure("Telefon+Reçete kontrolü (fallback)", adim_baslangic, "telefon_kontrol")

                if not telefon_var:
                    atlama_nedeni = "telefon yok"

            # 3) AYNI REÇETE KONTROLÜ (son reçeteye gelindi mi?)
            # Telefon kontrolünden gelen reçete no ile karşılaştır - ek okuma yok
            if not atlama_nedeni and onceki_loop_recete and current_recete:
                if onceki_loop_recete == current_recete:
                    # Aynı reçete - doğrulama: 0.5s bekle + tekrar oku
                    time.sleep(0.5)
                    dogrulama = bot.recete_sayfasi_hizli_tarama(max_deneme=2, bekleme_suresi=0.2)
                    dogrulama_recete = dogrulama.get('recete_no') if dogrulama else None

                    if dogrulama_recete and onceki_loop_recete == dogrulama_recete:
                        if not bot.recete_kaydi_var_mi_kontrol_hizli():
                            logger.error("❌ Reçete kaydı bulunamadı (son reçete)")
                            return (False, None, takip_sayisi, "Reçete kaydı bulunamadı")
                    else:
                        current_recete = dogrulama_recete

            # Her şey OK - döngüden çık
            if not atlama_nedeni:
                if atlanan_sayisi > 0:
                    logger.info(f"✓ {atlanan_sayisi} reçete atlandı, devam ediliyor")
                break

            # SONRA butonuna bas
            atlanan_sayisi += 1
            logger.info(f"⏭ Reçete atlanıyor ({atlama_nedeni}) [{atlanan_sayisi}]")

            adim_baslangic = time.time()
            sonra = bot.retry_with_popup_check(
                lambda: bot.sonra_butonuna_tikla(),
                "SONRA butonu",
                max_retries=5
            )
            log_sure("Sonra butonu (atlama)", adim_baslangic, "sonra_butonu")
            if not sonra:
                return (False, None, takip_sayisi, f"SONRA butonu başarısız ({atlama_nedeni})")

            # Sayfanın yüklenmesi için kısa bekleme
            time.sleep(0.4)

            onceki_loop_recete = current_recete or onceki_loop_recete
            # onceden_okunan_recete_no artık geçersiz (yeni sayfadayız)
            onceden_okunan_recete_no = None
        else:
            # max_atlama'ya ulaşıldı
            logger.error(f"❌ {max_atlama} ardışık reçete atlandı, durduruluyor")
            return (False, None, takip_sayisi, f"{max_atlama} ardışık reçete atlandı")

    # İlaç butonu referansı (hızlı taramadan alınacak)
    ilac_butonu_ref = None

    # Reçete numarası zaten GUI'de okunmuşsa tekrar okuma (performans optimizasyonu)
    if onceden_okunan_recete_no:
        medula_recete_no = onceden_okunan_recete_no
    else:
        # ★ ULTRA OPTİMİZE: CONTAINER-BASED HIZLI TARAMA ★
        # Reçete no + telefon + ilaç butonu referansı TEK TARAMADA
        adim_baslangic = time.time()

        # Önce hızlı tarama dene (container-based, ~0.5-1 saniye)
        hizli_sonuc = bot.recete_sayfasi_hizli_tarama(max_deneme=2, bekleme_suresi=0.15)

        if hizli_sonuc:
            # Hızlı tarama başarılı
            medula_recete_no = hizli_sonuc['recete_no']
            kayit_var = hizli_sonuc['kayit_var']
            telefon_var = hizli_sonuc['telefon_var']
            ilac_butonu_ref = hizli_sonuc.get('ilac_butonu')
            log_sure("Reçete+Telefon+Buton (hızlı)", adim_baslangic, "recete_kontrol")
        else:
            # Fallback: Eski yöntem (~1.5 saniye)
            birlesik_sonuc = bot.recete_telefon_kontrol_birlesik()
            medula_recete_no = birlesik_sonuc['recete_no']
            kayit_var = birlesik_sonuc['kayit_var']
            telefon_var = birlesik_sonuc['telefon_var']
            log_sure("Reçete+Telefon kontrolü (fallback)", adim_baslangic, "recete_kontrol")

        # Kayıt yok kontrolü
        if not kayit_var:
            logger.error("❌ Reçete kaydı bulunamadı")
            log_recete_baslik()
            return (False, medula_recete_no, takip_sayisi, "Reçete kaydı bulunamadı")

    log_recete_baslik(medula_recete_no)

    # DURDURMA KONTROLÜ - telefon kontrolünden sonra
    if should_stop():
        logger.info("⏸ İşlem durduruldu (kullanıcı talebi)")
        return (False, medula_recete_no, 0, "Kullanıcı tarafından durduruldu")

    # Genel muayene uyarısı kontrolü (reçete açıldıktan hemen sonra)
    try:
        if bot.uyari_penceresini_kapat(max_bekleme=0.5):
            logger.info("✓ Genel muayene uyarısı kapatıldı")
    except Exception as e:
        logger.debug(f"Uyarı kontrol hatası: {e}")

    # ===== İLAÇ TAKİP PASİFSE ATLA =====
    # İlaç takip aktif değilse, direkt rapor toplama/kontrol kısmına geç
    if not ilac_takip_aktif:
        logger.info("⏭ İlaç takip pasif, atlanıyor...")

        # Sadece rapor işlemleri yap
        sonraki_zaten_basildi = False

        # Rapor toplama (aktifse)
        if rapor_toplama_aktif and rapor_takip:
            try:
                if session_logger:
                    session_logger.info("🔵 Rapor toplama başlatılıyor...")
                rapor_verileri = bot.rapor_listesini_topla()
                if rapor_verileri:
                    sonraki_zaten_basildi = rapor_verileri.get('sonraki_basildi', False)
                    if rapor_verileri.get('raporlar'):
                        ad_soyad = rapor_verileri.get('ad_soyad', 'Bilinmeyen')
                        telefon = rapor_verileri.get('telefon', '')
                        raporlar = rapor_verileri.get('raporlar', [])
                        rapor_takip.toplu_rapor_ekle(ad_soyad, telefon, raporlar, grup)
                        logger.info(f"✓ Hasta raporları kaydedildi: {ad_soyad}")
            except Exception as e:
                logger.warning(f"Rapor kaydetme hatası: {e}")

        # Rapor kontrol (aktifse)
        if rapor_kontrol_aktif:
            try:
                from recete_kontrol import get_kontrol_motoru
                kontrol_motoru = get_kontrol_motoru()
                recete_verisi = {'recete_no': medula_recete_no, 'grup': grup}
                sonuclar = kontrol_motoru.recete_kontrol_et(recete_verisi)
                for kontrol_adi, rapor in sonuclar.items():
                    if kontrol_adi != '_genel':
                        logger.info(f"[Kontrol] {kontrol_adi}: {rapor.mesaj}")
            except ImportError:
                pass
            except Exception as e:
                logger.warning(f"Rapor kontrol hatası: {e}")

        # Sonraki reçeteye geç
        if not sonraki_zaten_basildi:
            sonra = bot.retry_with_popup_check(
                lambda: bot.sonra_butonuna_tikla(),
                "SONRA butonu",
                max_retries=5
            )
            if not sonra:
                return (False, medula_recete_no, 0, "SONRA butonu başarısız")

        return (True, medula_recete_no, 0, None)

    # ===== İLAÇ TAKİP (AKTİF) =====
    # İlaç butonuna tıkla (5 deneme + popup kontrolü)
    # ★ OPTİMİZASYON: Eğer hızlı taramadan referans varsa direkt kullan ★
    adim_baslangic = time.time()
    ilac_butonu = False

    if ilac_butonu_ref:
        # Referans var - direkt tıkla (arama atlanıyor = ~1-2 saniye kazanç)
        try:
            if ilac_butonu_ref.exists(timeout=0.2):
                ilac_butonu_ref.click_input()
                ilac_butonu = True
                logger.info("✓ İlaç butonuna tıklandı (referans ile - hızlı)")
                bot.timed_sleep("ilac_butonu")
        except Exception as e:
            logger.debug(f"Referans tıklama hatası: {type(e).__name__}, fallback yapılıyor...")

    # Referans yoksa veya başarısız olduysa normal yöntemi dene
    if not ilac_butonu:
        ilac_butonu = bot.retry_with_popup_check(
            lambda: bot.ilac_butonuna_tikla(),
            "İlaç butonu",
            max_retries=5
        )

    log_sure("İlaç butonu", adim_baslangic, "ilac_butonu")
    if not ilac_butonu:
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi, "İlaç butonu başarısız")

    # "Kullanılan İlaç Listesi" ekranının yüklenmesini bekle (5 saniye - yavaş bağlantı için artırıldı)
    adim_baslangic = time.time()
    ilac_ekrani = bot.ilac_ekrani_yuklendi_mi(max_bekleme=5)
    log_sure("İlaç ekranı yükleme", adim_baslangic, "ilac_ekran_bekleme")
    if not ilac_ekrani:
        logger.error("❌ İlaç ekranı yüklenemedi")
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi, "İlaç ekranı yüklenemedi")

    # DURDURMA KONTROLÜ - ilaç ekranı sonrası
    if should_stop():
        logger.info("⏸ İşlem durduruldu (kullanıcı talebi)")
        return (False, medula_recete_no, 0, "Kullanıcı tarafından durduruldu")

    # Y butonuna tıkla (retry_with_popup_check ile - REÇETE NOTU vb. popup kontrolü)
    ana_pencere = bot.main_window
    adim_baslangic = time.time()
    y_butonu = bot.retry_with_popup_check(
        lambda: bot.y_tusuna_tikla(),
        "Y butonu",
        max_retries=5,
        critical=False  # Y butonu başarısız olursa devam et, aşağıda tekrar denenir
    )
    log_sure("Y butonu", adim_baslangic, "y_butonu")

    # İlaç Listesi penceresini akıllı bekleme ile bul (max 1 saniye)
    # ÖNEMLİ: Y'ye tıklama başarılı dönse bile, popup yüzünden İlaç Listesi çıkmayabilir!
    adim_baslangic = time.time()
    ilac_penceresi_bulundu = False
    max_bekleme = 1.0  # Maksimum 1 saniye bekle
    bekleme_baslangic = time.time()

    while time.time() - bekleme_baslangic < max_bekleme:
        ilac_penceresi_bulundu = bot.yeni_pencereyi_bul("İlaç Listesi")
        if ilac_penceresi_bulundu:
            break  # BULUNDU! Hemen devam et
        time.sleep(bot.timing.get("pencere_bulma"))

    log_sure("İlaç penceresi bulma", adim_baslangic, "pencere_bulma")

    # İlaç Listesi bulunamadıysa kritik popup kontrolü yap (REÇETE NOTU dahil)
    # ===== POPUP WATCHER VARKEN BU KISIM NADIREN ÇALIŞIR =====
    # Windows Hook popup watcher otomatik olarak popup'ları kapatır
    if not ilac_penceresi_bulundu:
        # ★ ÖNCELİKLE KRİTİK POPUP KONTROLÜ (REÇETE NOTU + UYARIDIR) ★
        logger.info("⚠ İlaç Listesi bulunamadı → Kritik popup kontrolü yapılıyor...")
        try:
            if bot.kritik_popup_kontrol_ve_kapat():
                logger.info("✓ Kritik popup kapatıldı (REÇETE NOTU veya UYARIDIR)")
                time.sleep(0.3)
        except Exception as e:
            logger.debug(f"Kritik popup kontrol hatası: {type(e).__name__}")

        # Ardından ESC tuşları ile diğer popup'ları kapat
        logger.info("⚠ 3x ESC tuşuna basılıyor (LABA/LAMA uyarısı kapatma)")
        for i in range(3):
            send_keys("{ESC}")
            time.sleep(0.1)  # ESC'ler arası kısa bekleme (OPT: 0.15 → 0.1)
        logger.info("✓ 3x ESC tuşuna basıldı")
        time.sleep(bot.timing.get("esc_sonrasi_bekleme", 0.3))  # OPT: 0.5 → timing

        # Y butonuna tekrar tıkla (popup kontrolü ile)
        logger.info("🔄 Y tuşuna tekrar basılıyor...")
        adim_baslangic = time.time()
        y_butonu = bot.retry_with_popup_check(
            lambda: bot.y_tusuna_tikla(),
            "Y butonu (ESC sonrası)",
            max_retries=3,
            critical=False
        )
        log_sure("Y butonu (ESC sonrası)", adim_baslangic, "y_butonu")

        # İlaç Listesi penceresini tekrar ara
        bekleme_baslangic = time.time()
        max_bekleme = 0.8  # OPT: 1.0 → 0.8

        while time.time() - bekleme_baslangic < max_bekleme:
            ilac_penceresi_bulundu = bot.yeni_pencereyi_bul("İlaç Listesi")
            if ilac_penceresi_bulundu:
                logger.info("✓ İlaç Listesi bulundu (ESC + Y sonrası)")
                break
            time.sleep(bot.timing.get("pencere_bulma"))

        log_sure("İlaç penceresi bulma (ESC sonrası)", adim_baslangic, "pencere_bulma")

    # İlaç Listesi hala bulunamadıysa ENTER tuşu ile popup kapat (2. deneme)
    if not ilac_penceresi_bulundu:
        # ★ TEKRAR KRİTİK POPUP KONTROLÜ ★
        try:
            if bot.kritik_popup_kontrol_ve_kapat():
                logger.info("✓ Kritik popup kapatıldı (2. kontrol)")
                time.sleep(0.3)
        except Exception:
            pass

        logger.info("⚠ İlaç Listesi hala bulunamadı → ENTER basılıyor...")
        time.sleep(bot.timing.get("enter_oncesi_bekleme", 0.5))  # OPT: 1.0 → timing
        send_keys("{ENTER}")
        logger.info("✓ ENTER tuşuna basıldı (1. deneme)")

        # İlaç Listesi penceresini tekrar ara
        adim_baslangic = time.time()
        bekleme_baslangic = time.time()
        max_bekleme = 0.8  # OPT: 1.0 → 0.8

        while time.time() - bekleme_baslangic < max_bekleme:
            ilac_penceresi_bulundu = bot.yeni_pencereyi_bul("İlaç Listesi")
            if ilac_penceresi_bulundu:
                logger.info("✓ İlaç Listesi bulundu (ENTER sonrası)")
                break
            time.sleep(bot.timing.get("pencere_bulma"))

        log_sure("İlaç penceresi bulma (ENTER sonrası)", adim_baslangic, "pencere_bulma")

    # Hala bulunamadıysa ENTER tuşu ile popup kapat (3. deneme)
    if not ilac_penceresi_bulundu:
        # ★ SON KRİTİK POPUP KONTROLÜ ★
        try:
            if bot.kritik_popup_kontrol_ve_kapat():
                logger.info("✓ Kritik popup kapatıldı (3. kontrol)")
                time.sleep(0.3)
        except Exception:
            pass

        logger.info("⚠ İlaç Listesi hala bulunamadı → tekrar ENTER basılıyor...")
        time.sleep(bot.timing.get("enter_oncesi_bekleme", 0.5))  # OPT: 1.0 → timing
        send_keys("{ENTER}")
        logger.info("✓ ENTER tuşuna basıldı (2. deneme)")

        # Y butonuna tekrar tıkla (popup kontrolü ile)
        time.sleep(bot.timing.get("laba_sonrasi_bekleme"))
        adim_baslangic = time.time()
        y_butonu = bot.retry_with_popup_check(
            lambda: bot.y_tusuna_tikla(),
            "Y butonu (2. ENTER sonrası)",
            max_retries=3,
            critical=False
        )
        log_sure("Y butonu (2. ENTER sonrası)", adim_baslangic, "y_ikinci_deneme")

        # İlaç Listesi penceresini tekrar ara
        adim_baslangic = time.time()
        bekleme_baslangic = time.time()
        max_bekleme = 1.0

        while time.time() - bekleme_baslangic < max_bekleme:
            ilac_penceresi_bulundu = bot.yeni_pencereyi_bul("İlaç Listesi")
            if ilac_penceresi_bulundu:
                logger.info("✓ İlaç Listesi bulundu (2. ENTER + Y sonrası)")
                break
            time.sleep(bot.timing.get("pencere_bulma"))

        log_sure("İlaç penceresi bulma (2. deneme)", adim_baslangic, "pencere_bulma")

    # Hala bulunamadıysa gerçek hata
    if not ilac_penceresi_bulundu:
        logger.error("❌ İlaç Listesi penceresi bulunamadı (2x ENTER + Y sonrası bile)")
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi, "İlaç Listesi penceresi bulunamadı")

    # ===== YENİ AKIŞ: Textbox'lara 122 yaz =====
    adim_baslangic = time.time()
    bot.textboxlara_122_yaz()
    log_sure("Textbox 122 yazma", adim_baslangic, "textbox_yazma")

    # "Bizden Alınmayanları Seç" butonunu ara
    adim_baslangic = time.time()
    alinmayan_secildi = bot.bizden_alinanlarin_sec_tusuna_tikla()
    log_sure("Alınmayanları Seç", adim_baslangic, "alinmayanlari_sec")

    # Eğer buton bulunamadıysa → LABA/LAMA veya İlaç Çakışması uyarısı var olabilir
    if not alinmayan_secildi:
        logger.info("⚠ Bizden Alınmayanları Seç bulunamadı → LABA/LAMA kontrolü yapılıyor...")

        # 1. LABA/LAMA kontrol ve kapat
        laba_baslangic = time.time()
        laba_kapatildi = bot.laba_lama_uyarisini_kapat(max_bekleme=1.5)
        log_sure("LABA/LAMA kontrol", laba_baslangic, "laba_uyari")

        # 2. LABA/LAMA kapatıldıysa, İlaç Çakışması kontrol ve kapat
        ilac_cakismasi_kapatildi = False
        if laba_kapatildi:
            logger.info("⚠ LABA/LAMA kapatıldı → İlaç Çakışması kontrolü yapılıyor...")
            ilac_baslangic = time.time()
            ilac_cakismasi_kapatildi = bot.ilac_cakismasi_uyarisini_kapat(max_bekleme=1.5)
            log_sure("İlaç Çakışması kontrol (LABA sonrası)", ilac_baslangic, "ilac_cakismasi_uyari")

        # 3. Herhangi bir popup kapatıldıysa İlaç Listesi penceresini tekrar bul
        if laba_kapatildi or ilac_cakismasi_kapatildi:
            time.sleep(bot.timing.get("laba_sonrasi_bekleme"))

            # İlaç Listesi penceresini tekrar bul
            adim_baslangic = time.time()
            ilac_penceresi_bulundu = bot.yeni_pencereyi_bul("İlaç Listesi")
            log_sure("İlaç penceresi 2. bulma", adim_baslangic, "pencere_bulma")

            if ilac_penceresi_bulundu:
                # Tekrar "Bizden Alınmayanları Seç" butonunu ara
                adim_baslangic = time.time()
                alinmayan_secildi = bot.bizden_alinanlarin_sec_tusuna_tikla()
                log_sure("Alınmayanları Seç (2. deneme)", adim_baslangic, "alinmayanlari_sec")

        # Hala bulanamadıysa hata
        if not alinmayan_secildi:
            logger.error("❌ Bizden Alınmayanları Seç butonu bulunamadı (2 deneme)")
            log_recete_baslik()
            return (False, medula_recete_no, takip_sayisi, "Bizden Alınmayanları Seç butonu bulunamadı")

    # ===== YENİ AKIŞ: Checkbox kontrolü YOK - direkt sağ tıkla ve Takip Et =====
    # DURDURMA KONTROLÜ
    if should_stop():
        logger.info("⏸ İşlem durduruldu (kullanıcı talebi)")
        return (False, medula_recete_no, 0, "Kullanıcı tarafından durduruldu")

    # Kısa bekleme - seçim işleminin tamamlanması için
    adim_baslangic = time.time()
    time.sleep(0.3)

    # Direkt sağ tıkla ve "Takip Et" - checkbox kontrolü YOK
    takip_basarili = bot.ilk_ilaca_sag_tik_ve_takip_et()

    if takip_basarili:
        # Takip edilen ilaç sayısını say
        try:
            cells = bot.main_window.descendants(control_type="DataItem")
            takip_sayisi = sum(1 for cell in cells if "Seçim satır" in cell.window_text())
            logger.info(f"✓ {takip_sayisi} ilaç takip edildi")
        except Exception as e:
            logger.debug(f"Takip sayısı alınamadı: {type(e).__name__}")
            takip_sayisi = 1
    else:
        logger.warning("⚠ Takip Et başarısız - pencere kapatılıyor")
        takip_sayisi = 0

    log_sure("İlaç seçimi ve takip", adim_baslangic, "ilac_secim_bekleme")

    # İlaç Listesi penceresini kapat
    adim_baslangic = time.time()
    bot.ilac_listesi_penceresini_kapat()
    log_sure("İlaç penceresi kapatma", adim_baslangic, "kapat_butonu")

    # Ana Medula penceresine geri dön (main_window'u geri yükle)
    bot.main_window = ana_pencere

    # MEDULA penceresine odaklan ve hazır olmasını bekle
    try:
        bot.main_window.set_focus()
        time.sleep(0.5)  # Pencere odaklanması için bekle
        logger.info(f"✓ MEDULA penceresine geri dönüldü: {bot.main_window.window_text()}")
    except Exception as focus_err:
        logger.warning(f"⚠ MEDULA odaklama hatası: {type(focus_err).__name__}, yeniden bağlanılıyor...")
        # Yeniden bağlan
        if not bot.baglanti_kur("MEDULA"):
            logger.error("❌ MEDULA'ya yeniden bağlanılamadı")
        else:
            logger.info("✓ MEDULA'ya yeniden bağlanıldı")

    # DURDURMA KONTROLÜ - geri dön'den önce
    if should_stop():
        logger.info("⏸ İşlem durduruldu (kullanıcı talebi)")
        return (False, medula_recete_no, takip_sayisi, "Kullanıcı tarafından durduruldu")

    # Geri Dön butonuna tıkla (İlaç Listesi → Reçete Ana Sayfasına geçiş)
    adim_baslangic = time.time()
    geri_don = bot.geri_don_butonuna_tikla()
    log_sure("Geri Dön butonu", adim_baslangic, "geri_don_butonu")
    if not geri_don:
        log_recete_baslik()
        return (False, medula_recete_no, takip_sayisi, "Geri Dön butonu başarısız")

    # ÖNEMLİ: Rapor toplama işlemi Geri Dön'den SONRA yapılmalı!
    # Çünkü Rapor butonu (f:buttonRaporListesi) Reçete Ana Sayfasında (ReceteListe.jsp) bulunur.
    # Geri Dön'e tıklandıktan sonra bu sayfaya geçilir ve Rapor butonu görünür olur.
    # Rapor toplama sonrası Sonraki butonuna basılıp basılmadığını takip et
    sonraki_zaten_basildi = False

    if rapor_takip:
        try:
            if session_logger:
                session_logger.info("🔵 Rapor toplama başlatılıyor (Reçete Ana Sayfasında)...")

            adim_baslangic = time.time()
            rapor_verileri = bot.rapor_listesini_topla()
            log_sure("Rapor toplama", adim_baslangic, "rapor_toplama")

            if rapor_verileri:
                # Sonraki butonu basılmış mı kontrol et
                sonraki_zaten_basildi = rapor_verileri.get('sonraki_basildi', False)

                if rapor_verileri.get('raporlar'):
                    ad_soyad = rapor_verileri.get('ad_soyad', 'Bilinmeyen')
                    telefon = rapor_verileri.get('telefon', '')
                    raporlar = rapor_verileri.get('raporlar', [])

                    # Raporları CSV'ye kaydet
                    rapor_takip.toplu_rapor_ekle(ad_soyad, telefon, raporlar, grup)
                    logger.info(f"✓ Hasta raporları kaydedildi: {ad_soyad}")
                    if session_logger:
                        session_logger.basari(f"✅ {len(raporlar)} rapor CSV'ye kaydedildi - {ad_soyad} ({telefon})")
                else:
                    logger.info("Bu hastada rapor bulunamadı")
                    if session_logger:
                        session_logger.warning(f"⚠️ Rapor bulunamadı - {rapor_verileri.get('ad_soyad', 'Bilinmeyen')}")
            else:
                logger.info("Rapor okuma başarısız")
                if session_logger:
                    session_logger.warning("⚠️ Rapor okuma başarısız (rapor butonu tıklanamadı)")
        except Exception as e:
            logger.warning(f"Rapor kaydetme hatası (devam ediliyor): {e}")
            if session_logger:
                session_logger.error(f"❌ Rapor kaydetme hatası: {e}")

    # SONRA butonuna tıkla - SADECE rapor toplarken basılmadıysa (5 deneme)
    if sonraki_zaten_basildi:
        logger.info("✓ Sonraki butonu rapor sayfasından zaten basıldı, atlanıyor...")
    else:
        adim_baslangic = time.time()
        sonra = bot.retry_with_popup_check(
            lambda: bot.sonra_butonuna_tikla(),
            "SONRA butonu",
            max_retries=5
        )
        log_sure("Sonra butonu", adim_baslangic, "sonra_butonu")
        if not sonra:
            log_recete_baslik()
            return (False, medula_recete_no, takip_sayisi, "SONRA butonu başarısız")

    # Toplam reçete süresi
    toplam_sure = time.time() - recete_baslangic
    if toplam_sure >= 60:
        dakika = int(toplam_sure // 60)
        saniye = int(toplam_sure % 60)
        logger.info(f"🕐 TOPLAM: {dakika}dk {saniye}s")
    else:
        logger.info(f"🕐 TOPLAM: {toplam_sure:.2f}s")

    return (True, medula_recete_no, takip_sayisi, None)


def console_pencereyi_ayarla():
    """
    Console penceresini yerleştir (ayara göre):
    - Standart: 2. dilim (%60-%80 arası)
    - Geniş MEDULA: GUI arkasında (%80-%100, HWND_BOTTOM)
    """
    try:
        from medula_settings import get_medula_settings
        medula_settings = get_medula_settings()
        yerlesim = medula_settings.get("pencere_yerlesimi", "standart")

        logger.info(f"🔵 Konsol konumlandırma başlatılıyor... (mod: {yerlesim})")

        # Ekran çözünürlüğünü al
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        logger.info(f"  Ekran boyutu: {screen_width}x{screen_height}")

        # Yerleşim ayarına göre konum belirle
        if yerlesim == "genis_medula":
            # Geniş MEDULA: Konsol GUI arkasında (%80-%100)
            console_x = int(screen_width * 0.80)  # %80'den başla
            console_y = 0
            console_width = int(screen_width * 0.20)  # %20
            console_height = screen_height - 40
            arkada = True
            logger.info(f"  Geniş MEDULA modu: Konsol GUI arkasına yerleştirilecek")
        else:
            # Standart: 2. dilim (%60-%80 arası)
            console_x = int(screen_width * 0.60)  # %60'tan başla
            console_y = 0
            console_width = int(screen_width * 0.20)  # Ekranın %20'si
            console_height = screen_height - 40
            arkada = False

        logger.info(f"  Konsol konumu: x={console_x}, y={console_y}, w={console_width}, h={console_height}")

        # Console penceresini al
        logger.info("  Konsol penceresi handle alınıyor...")
        kernel32 = ctypes.windll.kernel32
        console_hwnd = kernel32.GetConsoleWindow()

        if console_hwnd:
            logger.info(f"  ✓ Konsol penceresi bulundu (hwnd={console_hwnd})")

            # Console buffer boyutunu artır (daha fazla geçmiş tutmak için)
            try:
                subprocess.run('mode con: lines=9999', shell=True, capture_output=True)
            except Exception as e:
                logger.debug(f"  Mode con hatası: {type(e).__name__}")

            # Pencereyi görünür yap (minimize ise restore et)
            logger.info("  Konsol penceresi restore ediliyor...")
            win32gui.ShowWindow(console_hwnd, win32con.SW_RESTORE)
            time.sleep(0.09)

            # SetWindowPos ile yerleştir
            if arkada:
                # GUI arkasına yerleştir (HWND_BOTTOM)
                logger.info(f"  SetWindowPos ile GUI arkasına konumlandırılıyor...")
                win32gui.SetWindowPos(
                    console_hwnd,
                    win32con.HWND_BOTTOM,
                    console_x, console_y,
                    console_width, console_height,
                    win32con.SWP_SHOWWINDOW
                )
            else:
                # Önde yerleştir (HWND_TOP)
                logger.info(f"  SetWindowPos ile konumlandırılıyor...")
                win32gui.SetWindowPos(
                    console_hwnd,
                    win32con.HWND_TOP,
                    console_x, console_y,
                    console_width, console_height,
                    win32con.SWP_SHOWWINDOW
                )
            time.sleep(0.045)

            # MoveWindow ile kesin yerleştir
            logger.info("  MoveWindow ile kesin konumlandırılıyor...")
            win32gui.MoveWindow(console_hwnd, console_x, console_y, console_width, console_height, True)
            time.sleep(0.045)

            # Doğrulama: gerçek pozisyonu kontrol et
            try:
                gercek_rect = win32gui.GetWindowRect(console_hwnd)
                logger.info(f"  ✓ Konsol yerleştirildi: x={gercek_rect[0]}, y={gercek_rect[1]}, w={gercek_rect[2]-gercek_rect[0]}, h={gercek_rect[3]-gercek_rect[1]}")
            except Exception as e:
                logger.debug(f"  Pozisyon doğrulama hatası: {e}")

            if arkada:
                logger.info(f"✅ Konsol GUI arkasına yerleştirildi!")
            else:
                logger.info(f"✅ Konsol 2. dilime yerleştirildi!")
        else:
            logger.warning("❌ Konsol penceresi bulunamadı (hwnd=0)")

    except Exception as e:
        logger.error(f"❌ Konsol konumlandırma hatası: {e}", exc_info=True)


def main():
    """Ana fonksiyon - Reçete döngüsü"""
    program_baslangic = time.time()

    logger.info("=" * 40)
    logger.info("Botanik Bot Başlatılıyor...")
    logger.info("=" * 40)

    # Bot oluştur
    bot = BotanikBot()

    # Rapor takip sistemi oluştur ve bot'a ekle
    try:
        bot.rapor_takip = RaporTakip()
        logger.info("✓ Rapor takip sistemi başlatıldı")
    except Exception as e:
        logger.warning(f"Rapor takip sistemi başlatılamadı: {e}")
        bot.rapor_takip = None

    # Medulla'ya bağlan (ilk bağlantı - pencere yerleştirme ile)
    if not bot.baglanti_kur("MEDULA", ilk_baglanti=True):
        logger.error("❌ MEDULA bulunamadı")
        return

    # Medula yerleştirildikten SONRA console'u yerleştir
    console_pencereyi_ayarla()

    # Reçete döngüsü - SONRA butonu olduğu sürece devam et
    recete_sayisi = 0
    basarili_receteler = 0
    son_islenen_recete = None  # Son başarıyla işlenen reçete numarası (taskkill sonrası devam için)

    while True:
        recete_sayisi += 1
        logger.info("=" * 40)

        try:
            # Tek reçete işle
            basari, medula_no, takip_sayisi, hata_nedeni = tek_recete_isle(bot, recete_sayisi, bot.rapor_takip)
            logger.info("=" * 40)
            if not basari:
                # Reçete kaydı bulunamadı veya SONRA butonu bulunamadı - döngüden çık
                break
            else:
                basarili_receteler += 1
                # Son başarılı reçete numarasını kaydet
                if medula_no:
                    son_islenen_recete = medula_no

        except SistemselHataException as e:
            # Sistemsel hata tespit edildi
            logger.error(f"⚠️ Sistemsel hata yakalandı: {e}")

            # ===== HATA DURUMUNDA BEKLE KONTROLÜ =====
            hata_bekle_aktif = False
            if hasattr(bot, '_insan_davranisi_ayarlar') and bot._insan_davranisi_ayarlar:
                hata_bekle_aktif = bot._insan_davranisi_ayarlar.get("hata_durumunda_bekle", {}).get("aktif", False)

            if hata_bekle_aktif:
                # Hata durumunda bekle modu aktif - otomatik yeniden başlatma YAPMA
                logger.warning("=" * 60)
                logger.warning("⏸️ HATA DURUMUNDA BEKLE MODU AKTİF")
                logger.warning("Otomatik yeniden başlatma devre dışı.")
                logger.warning("Lütfen hatayı manuel olarak düzeltin ve botu yeniden başlatın.")
                logger.warning("=" * 60)
                break

            # MEDULA'yı yeniden başlat ve giriş yap (grup bilgisini ve son reçeteyi kullan)
            # son_islenen_recete ile kaldığı reçeteden devam edecek
            if medula_yeniden_baslat_ve_giris_yap(bot, grup, son_islenen_recete):
                # Başarıyla yeniden başlatıldı - aynı reçeteden devam et
                if son_islenen_recete:
                    logger.info(f"🔄 Kaldığı reçeteden devam ediliyor: {son_islenen_recete}")
                else:
                    logger.info(f"🔄 Reçete {recete_sayisi} tekrar işlenecek...")
                    recete_sayisi -= 1  # Sayaç geri alınıyor, çünkü while döngüsü başında tekrar artacak
                time.sleep(2)
                continue
            else:
                # Yeniden başlatma başarısız - programdan çık
                logger.error("❌ MEDULA yeniden başlatılamadı, program sonlandırılıyor")
                break

    toplam_sure = time.time() - program_baslangic
    ortalama_sure = toplam_sure / basarili_receteler if basarili_receteler > 0 else 0

    # Süre formatı
    if toplam_sure >= 60:
        t_dk = int(toplam_sure // 60)
        t_sn = int(toplam_sure % 60)
        toplam_str = f"{t_dk}dk {t_sn}s"
    else:
        toplam_str = f"{toplam_sure:.1f}s"

    if ortalama_sure >= 60:
        o_dk = int(ortalama_sure // 60)
        o_sn = int(ortalama_sure % 60)
        ortalama_str = f"{o_dk}dk {o_sn}s"
    else:
        ortalama_str = f"{ortalama_sure:.1f}s"

    logger.info("=" * 40)
    logger.info(f"✓ Tamamlandı: {basarili_receteler} reçete")
    logger.info(f"🕐 Toplam: {toplam_str}")
    logger.info(f"📊 Ortalama: {ortalama_str}/reçete")
    logger.info("=" * 40)


# ==================== YARDIMCI FONKSİYONLAR ====================

def popup_kontrol_ve_kapat():
    """
    Popup/dialog pencerelerini otomatik algıla ve kapat

    Returns:
        bool: Popup kapatıldıysa True
    """
    try:
        from pywinauto import Desktop

        desktop = Desktop(backend="uia")
        windows = desktop.windows()

        for window in windows:
            try:
                # Sadece görünür pencerelere bak
                if not window.is_visible():
                    continue

                # Dialog/Modal pencere mi?
                window_text = window.window_text()

                # Boş başlık veya çok kısa başlıklı pencereler genelde popup
                if not window_text or len(window_text) < 3:
                    continue

                # Küçük pencereler (popup olabilir)
                try:
                    rect = window.rectangle()
                    width = rect.width()
                    height = rect.height()

                    # Çok büyük pencereler ana penceredir, skip
                    if width > 800 or height > 600:
                        continue

                    # Çok küçük pencereler de anlamsız
                    if width < 100 or height < 50:
                        continue
                except Exception as e:
                    logger.debug(f"Window size check failed: {type(e).__name__}")
                    continue

                # Pencere içinde "Tamam", "OK", "Kapat", "X", "Evet", "Hayır" gibi butonlar ara
                kapat_butonlari = ["Tamam", "OK", "Kapat", "İptal", "Evet", "Hayır", "Close", "Cancel"]

                for buton_text in kapat_butonlari:
                    try:
                        buton = window.child_window(title=buton_text, control_type="Button")
                        if buton.exists(timeout=0.2):
                            logger.info(f"✓ Popup tespit edildi: '{window_text}', kapatılıyor...")
                            buton.click()
                            time.sleep(0.3)
                            return True
                    except Exception as e:
                        logger.debug(f"Operation failed: {type(e).__name__}")

                # X (Close) butonu ara
                try:
                    close_button = window.child_window(title="Close", control_type="Button")
                    if close_button.exists(timeout=0.2):
                        logger.info(f"✓ Popup tespit edildi (X): '{window_text}', kapatılıyor...")
                        close_button.click()
                        time.sleep(0.3)
                        return True
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            except Exception as e:
                continue

        return False
    except Exception as e:
        logger.debug(f"Popup kontrol hatası: {e}")
        return False


def sistemsel_hata_kontrol():
    """
    MEDULA penceresinde "Yazılımsal veya sistemsel bir hata oluştu." label'ını kontrol et

    Returns:
        bool: Sistemsel hata tespit edildiyse True
    """
    try:
        from pywinauto import Desktop

        desktop = Desktop(backend="uia")
        windows = desktop.windows()

        for window in windows:
            try:
                # MEDULA penceresi mi?
                window_text = window.window_text()
                if not window_text or "MEDULA" not in window_text:
                    continue

                # Pencere görünür mü?
                if not window.is_visible():
                    continue

                # "Yazılımsal veya sistemsel bir hata oluştu." text elementini ara
                try:
                    # Name veya title ile ara
                    hata_text = window.child_window(
                        title_re=".*[Yy]azılımsal veya sistemsel.*hata.*",
                        control_type="Text"
                    )
                    if hata_text.exists(timeout=0.3):
                        logger.error("❌ SİSTEMSEL HATA TESPİT EDİLDİ: 'Yazılımsal veya sistemsel bir hata oluştu.'")
                        return True
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

                # Alternatif: Tüm text elementlerini tara
                try:
                    texts = window.descendants(control_type="Text")
                    for text in texts:
                        raw_content = text.window_text()
                        text_content = raw_content.lower() if raw_content else ""
                        if "yazılımsal" in text_content and "sistemsel" in text_content and "hata" in text_content:
                            logger.error(f"❌ SİSTEMSEL HATA TESPİT EDİLDİ: '{raw_content}'")
                            return True
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            except Exception as e:
                continue

        return False
    except Exception as e:
        logger.debug(f"Sistemsel hata kontrol hatası: {e}")
        return False


def recete_kaydi_bulunamadi_mi(bot):
    """
    "Reçete kaydı bulunamadı" mesajını kontrol et

    OPTİMİZE: Desktop().windows() taraması kaldırıldı (çok yavaştı!)
    Sadece bot.main_window'da arama yapılıyor.

    Args:
        bot (BotanikBot): Bot instance

    Returns:
        bool: Mesaj varsa True (görev bitti)
    """
    try:
        if not bot.main_window:
            return False

        # YÖNTEM 1: child_window ile hızlı arama (0.2s timeout)
        try:
            text_element = bot.main_window.child_window(title_re=".*Reçete kaydı bulunamadı.*", control_type="Text")
            if text_element.exists(timeout=0.2):
                logger.info("✓ 'Reçete kaydı bulunamadı' mesajı tespit edildi - Görev tamamlandı!")
                return True
        except Exception as e:
            logger.debug(f"child_window arama hatası: {type(e).__name__}")

        # YÖNTEM 2: descendants ile ana pencerede arama (Desktop taraması YOK - optimize)
        try:
            texts = bot.main_window.descendants(control_type="Text")
            for text in texts:
                try:
                    raw_text = text.window_text()
                    if raw_text and "bulunamadı" in raw_text.lower():
                        logger.info(f"✓ Görev bitişi mesajı: '{raw_text}'")
                        return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"descendants arama hatası: {type(e).__name__}")

        return False
    except Exception as e:
        logger.debug(f"Görev bitişi kontrolü hatası: {type(e).__name__}")
        return False


def medula_taskkill():
    """
    MEDULA programını zorla kapat (taskkill)
    SADECE BotanikMedula.exe kapatılır (BotanikEczane.exe KAPANMAZ)

    Returns:
        bool: Başarılıysa True
    """
    try:
        import subprocess

        # SADECE BotanikMedula.exe'yi kapat
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "BotanikMedula.exe"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            logger.info("✓ BotanikMedula.exe kapatıldı (taskkill)")
            time.sleep(2)  # Programın tamamen kapanması için bekle
            return True
        else:
            logger.warning("⚠ Taskkill başarısız: BotanikMedula.exe bulunamadı")
            return False
    except Exception as e:
        logger.error(f"❌ Taskkill hatası: {e}")
        return False


def medula_yeniden_baslat_ve_giris_yap(bot, grup="A", son_recete=None):
    """
    Sistemsel hata durumunda MEDULA'yı yeniden başlatır ve giriş yapar

    Args:
        bot: BotanikBot instance
        grup: Hangi gruba gidileceği ("A", "B" veya "C")
        son_recete: Son işlenen reçete numarası (varsa bu reçeteden devam edilir)

    Returns:
        bool: Başarılıysa True

    Raises:
        Exception: Yeniden başlatma başarısız olursa
    """
    try:
        from medula_settings import get_medula_settings
        from timing_settings import get_timing_settings

        timing = get_timing_settings()

        logger.info("=" * 60)
        logger.error("🔄 SİSTEMSEL HATA - MEDULA YENİDEN BAŞLATILIYOR...")
        logger.info("=" * 60)

        # 1. MEDULA'yı kapat
        logger.info("1️⃣ MEDULA kapatılıyor...")
        medula_taskkill()
        time.sleep(3)  # Programın tamamen kapanması için ekstra bekleme

        # 2. Ayarları yükle
        medula_settings = get_medula_settings()

        # 3. MEDULA'yı aç ve giriş yap
        logger.info("2️⃣ MEDULA açılıyor ve giriş yapılıyor...")
        if not medula_ac_ve_giris_yap(medula_settings):
            logger.error("❌ MEDULA açma/giriş başarısız")
            return False

        # 4. Bot'un bağlantısını yenile
        logger.info("3️⃣ Bot bağlantısı yenileniyor...")
        # Cache'i temizle
        bot.medula_hwnd = None
        bot.medula_pid = None

        # Yeni bağlantı kur
        if not bot.baglanti_kur("MEDULA", ilk_baglanti=False):
            logger.error("❌ Bot bağlantısı kurulamadı")
            return False

        # 5. Ana sayfaya git
        logger.info("⏳ Ana sayfa yüklenmesi bekleniyor...")
        time.sleep(timing.get("ana_sayfa"))

        # 6. Reçete Listesi'ne git
        logger.info("4️⃣ Reçete Listesi açılıyor...")
        try:
            if not recete_listesi_ac(bot):
                logger.error("❌ Reçete Listesi açılamadı")
                return False
        except SistemselHataException as e:
            logger.error(f"⚠️ Reçete Listesi açma sırasında sistemsel hata: {e}")
            logger.warning("🔄 MEDULA bir kez daha yeniden başlatılacak...")
            # Recursive call - kendini bir kez daha çağır (son_recete ile)
            return medula_yeniden_baslat_ve_giris_yap(bot, grup, son_recete)

        # 7. Dönem seç (index=2)
        logger.info("5️⃣ Dönem seçiliyor...")
        if not donem_sec(bot, index=2):
            logger.warning("⚠ Dönem 2 seçilemedi, dönem 1 deneniyor...")
            if not donem_sec(bot, index=1):
                logger.error("❌ Dönem seçimi başarısız")
                return False

        # 8. Grup seç
        logger.info(f"6️⃣ Grup {grup} seçiliyor...")
        if not grup_butonuna_tikla(bot, grup):
            logger.error(f"❌ Grup {grup} seçimi başarısız")
            return False

        # Pencereyi yenile
        bot.baglanti_kur("MEDULA", ilk_baglanti=False)

        # 8.5. Reçete bulunamadı kontrolü
        logger.info("🔍 Reçete varlığı kontrol ediliyor...")
        if bulunamadi_mesaji_kontrol(bot):
            logger.warning(f"⚠ Grup {grup}'da bu dönem için reçete bulunamadı")

            # Farklı dönemler dene
            donem_bulundu = False
            for donem_index in [1, 0]:  # Dönem 2 (index 1), Dönem 1 (index 0) dene
                logger.info(f"🔄 Dönem {donem_index + 1} deneniyor...")

                # Dönem seç
                if not donem_sec(bot, index=donem_index):
                    logger.warning(f"⚠ Dönem {donem_index + 1} seçilemedi")
                    continue

                # Grup seç
                if not grup_butonuna_tikla(bot, grup):
                    logger.error(f"❌ Grup {grup} seçimi başarısız")
                    continue

                # Pencereyi yenile
                bot.baglanti_kur("MEDULA", ilk_baglanti=False)

                # Tekrar kontrol et
                if not bulunamadi_mesaji_kontrol(bot):
                    logger.info(f"✅ Dönem {donem_index + 1}'de reçete bulundu!")
                    donem_bulundu = True
                    break
                else:
                    logger.warning(f"⚠ Dönem {donem_index + 1}'de de reçete bulunamadı")

            if not donem_bulundu:
                # Farklı grupları dene
                logger.warning(f"⚠ Grup {grup}'da hiçbir dönemde reçete bulunamadı, diğer gruplar deneniyor...")
                for alternatif_grup in ["A", "B", "C"]:
                    if alternatif_grup == grup:
                        continue

                    logger.info(f"🔄 Grup {alternatif_grup} deneniyor...")

                    # Dönem seç (index=2)
                    if not donem_sec(bot, index=2):
                        if not donem_sec(bot, index=1):
                            continue

                    # Grup seç
                    if not grup_butonuna_tikla(bot, alternatif_grup):
                        continue

                    # Pencereyi yenile
                    bot.baglanti_kur("MEDULA", ilk_baglanti=False)

                    # Kontrol et
                    if not bulunamadi_mesaji_kontrol(bot):
                        logger.info(f"✅ Grup {alternatif_grup}'da reçete bulundu!")
                        grup = alternatif_grup  # Grubu güncelle
                        donem_bulundu = True
                        break

                if not donem_bulundu:
                    logger.error("❌ Hiçbir grup ve dönemde reçete bulunamadı")
                    return False

        # 9. Son reçeteye git (varsa) veya ilk reçeteyi aç
        if son_recete:
            logger.info(f"7️⃣ Son reçeteye gidiliyor: {son_recete}")
            # Reçete Sorgu sayfasını aç (KADEMELİ KURTARMA ile)
            if not bot.recete_sorgu_ac_kademeli():
                logger.warning("⚠ Reçete Sorgu açılamadı (kademeli kurtarma sonrası), ilk reçete açılıyor...")
                if not ilk_recete_ac(bot):
                    logger.error("❌ İlk reçete açılamadı")
                    return False
            else:
                # Reçete numarasını yaz
                time.sleep(0.5)
                if not bot.recete_no_yaz(son_recete):
                    logger.warning(f"⚠ Reçete numarası yazılamadı: {son_recete}")
                    if not ilk_recete_ac(bot):
                        logger.error("❌ İlk reçete açılamadı")
                        return False
                else:
                    # Sorgula butonuna tıkla
                    time.sleep(0.3)
                    if not bot.sorgula_butonuna_tikla():
                        logger.warning("⚠ Sorgula butonu tıklanamadı, ilk reçete açılıyor...")
                        if not ilk_recete_ac(bot):
                            logger.error("❌ İlk reçete açılamadı")
                            return False
                    else:
                        # Sorgulama başarılı - şimdi listedeki ilk reçeteyi aç
                        logger.info(f"✓ Reçete sorgulandı: {son_recete}")
                        time.sleep(0.5)  # Sorgu sonucunun yüklenmesi için bekle
                        if not ilk_recete_ac(bot):
                            logger.error("❌ Sorgulanan reçete açılamadı")
                            return False
                        logger.info(f"✓ Kaldığı reçete açıldı: {son_recete}")
        else:
            logger.info("7️⃣ İlk reçete açılıyor...")
            if not ilk_recete_ac(bot):
                logger.error("❌ İlk reçete açılamadı")
                return False

        logger.info("=" * 60)
        logger.info(f"✅ MEDULA BAŞARIYLA YENİDEN BAŞLATILDI - GRUP {grup}")
        if son_recete:
            logger.info(f"📍 Kaldığı yerden devam: {son_recete}")
        logger.info("=" * 60)
        time.sleep(2)  # Kullanıcının mesajı görmesi için

        return True

    except Exception as e:
        logger.error(f"❌ MEDULA yeniden başlatma hatası: {e}")
        import traceback
        traceback.print_exc()
        return False


def masaustu_medula_ac(medula_settings):
    """
    MEDULA programını exe dosyasından direkt çalıştır

    Args:
        medula_settings: MedulaSettings instance

    Returns:
        bool: Başarılıysa True
    """
    try:
        import os
        from timing_settings import get_timing_settings

        timing = get_timing_settings()

        # Ayarlardan exe yolunu al
        exe_path = medula_settings.get("medula_exe_path", "")

        if not exe_path or not os.path.exists(exe_path):
            logger.error(f"MEDULA .exe dosyası bulunamadı: {exe_path}")
            return False

        logger.info(f"MEDULA programi baslatiliyor: {exe_path}")

        # Subprocess ile exe'yi çalıştır ve process referansını sakla
        try:
            process = subprocess.Popen([exe_path])
            logger.info(f"✓ MEDULA programi baslatildi (PID: {process.pid})")
        except FileNotFoundError:
            logger.error(f"❌ Dosya bulunamadı: {exe_path}")
            return False
        except PermissionError:
            logger.error(f"❌ Dosya çalıştırma yetkisi yok: {exe_path}")
            return False
        except Exception as e:
            logger.error(f"❌ Process başlatma hatası: {e}")
            return False

        logger.info("MEDULA giris penceresi bekleniyor...")
        time.sleep(timing.get("masaustu_simge_bekleme"))

        return True

    except Exception as e:
        logger.error(f"MEDULA programi baslatilamadi: {e}")
        return False


def medula_giris_yap(medula_settings):
    """
    MEDULA giriş penceresine kullanıcı adı ve şifre girerek giriş yap

    Args:
        medula_settings: MedulaSettings instance

    Returns:
        bool: Başarılıysa True
    """
    try:
        from pywinauto import Desktop
        import pyautogui
        from timing_settings import get_timing_settings

        timing = get_timing_settings()

        logger.info("⏳ MEDULA giriş penceresi bekleniyor...")
        time.sleep(timing.get("giris_pencere_bekleme"))

        # Aktif kullanıcının bilgilerini al
        aktif_kullanici = medula_settings.get_aktif_kullanici()
        if not aktif_kullanici:
            logger.error("❌ Aktif kullanıcı bulunamadı!")
            return False

        kullanici_index = aktif_kullanici.get("kullanici_index", 0)
        sifre = aktif_kullanici.get("sifre")
        kullanici_ad = aktif_kullanici.get("ad", "Kullanıcı")

        if sifre is None or sifre == "":
            logger.error(f"❌ {kullanici_ad} için şifre ayarlanmamış!")
            return False

        # Giriş yöntemi kontrolü
        giris_yontemi = medula_settings.get("giris_yontemi", "indeks")
        kullanici_adi_giris = medula_settings.get("kullanici_adi_giris", "")

        if giris_yontemi == "indeks":
            logger.info(f"🔐 {kullanici_ad} ile giriş yapılıyor (İndeks yöntemi - MEDULA Index: {kullanici_index})")
        else:
            logger.info(f"🔐 {kullanici_ad} ile giriş yapılıyor (Kullanıcı Adı yöntemi - MEDULA Kullanıcı: {kullanici_adi_giris})")

        desktop = Desktop(backend="uia")

        # Giriş penceresini bul
        giris_window = None
        for window in desktop.windows():
            try:
                if "MEDULA" in window.window_text():
                    giris_window = window
                    break
            except Exception as e:
                logger.debug(f"Operation failed: {type(e).__name__}")

        if not giris_window:
            logger.error("❌ MEDULA giriş penceresi bulunamadı")
            return False

        logger.info("✓ Giriş penceresi bulundu")

        # ComboBox'tan kullanıcı seç
        try:
            logger.debug("Kullanici combobox aranıyor...")

            # Tüm UI elementlerini döngüyle tara ve ComboBox bul
            all_controls = giris_window.descendants()
            combobox = None

            for ctrl in all_controls:
                try:
                    if "COMBOBOX" in ctrl.class_name().upper():
                        combobox = ctrl
                        logger.info(f"Combobox bulundu: {ctrl.class_name()}")
                        break
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            if combobox:
                # ComboBox'ın koordinatlarını al
                rect = combobox.rectangle()
                x_center = (rect.left + rect.right) // 2
                y_center = (rect.top + rect.bottom) // 2

                logger.info(f"Combobox koordinatlari: x={x_center}, y={y_center}")

                # Koordinata tıkla
                logger.info("Combobox'a tıklanıyor...")
                pyautogui.click(x_center, y_center)
                time.sleep(0.5)

                # Giriş yöntemine göre kullanıcı seçimi
                if giris_yontemi == "kullanici_adi":
                    # Kullanıcı adı ile arama
                    if kullanici_adi_giris:
                        logger.info(f"Kullanıcı adı yazılıyor: {kullanici_adi_giris}")
                        pyautogui.typewrite(kullanici_adi_giris, interval=0.1)
                        time.sleep(0.3)
                        logger.info("Enter ile seçiliyor...")
                        pyautogui.press("enter")
                        time.sleep(timing.get("kullanici_secim"))
                        logger.info(f"Kullanıcı seçildi (ad: {kullanici_adi_giris})")
                    else:
                        logger.warning("Kullanıcı adı girilmemiş, varsayılan kullanıcı seçilecek")
                        pyautogui.press("enter")
                        time.sleep(timing.get("kullanici_secim"))
                else:
                    # İndeks ile seçim (mevcut yöntem)
                    if kullanici_index > 0:
                        logger.info(f"{kullanici_index} kere DOWN tuşuna basılıyor...")
                        for i in range(kullanici_index):
                            pyautogui.press('down')
                            time.sleep(0.2)
                    else:
                        logger.info("Index 0, birinci kullanici secilecek")

                    # Enter ile seç
                    logger.info("Enter basilarak kullanici seciliyor...")
                    pyautogui.press("enter")
                    time.sleep(timing.get("kullanici_secim"))
                    logger.info(f"Kullanici secildi (index: {kullanici_index})")
            else:
                logger.warning("Combobox bulunamadı!")

        except Exception as e:
            logger.error(f"ComboBox islemi basarisiz: {e}")
            import traceback
            traceback.print_exc()

        # Şifre textbox'ına geç ve yaz
        try:
            logger.info("Sifre kutusuna geciliyor...")

            # Şifre textbox'ını bul
            sifre_textbox = None
            all_controls = giris_window.descendants()

            for ctrl in all_controls:
                try:
                    # Şifre kutusunu automation_id veya class_name ile bul
                    if (hasattr(ctrl, 'automation_id') and ctrl.automation_id() == "txtSifre") or \
                       ("EDIT" in ctrl.class_name().upper() and ctrl != combobox):
                        sifre_textbox = ctrl
                        logger.info(f"Sifre textbox bulundu: {ctrl.class_name()}")
                        break
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            if sifre_textbox:
                # Şifre textbox'ının koordinatlarını al
                rect = sifre_textbox.rectangle()
                x_center = (rect.left + rect.right) // 2
                y_center = (rect.top + rect.bottom) // 2

                logger.info(f"Sifre textbox koordinatlari: x={x_center}, y={y_center}")

                # Koordinata tıkla
                logger.info("Sifre kutusuna tıklanıyor...")
                pyautogui.click(x_center, y_center)
                time.sleep(0.5)
            else:
                # Bulunamazsa TAB ile dene
                logger.warning("Sifre textbox koordinat ile bulunamadi, TAB ile denenecek")
                pyautogui.press("tab")
                time.sleep(0.3)

            # Şifreyi clipboard ile yapıştır
            logger.info("Sifre clipboard'a kopyalanıyor...")
            import pyperclip
            pyperclip.copy(sifre)
            time.sleep(0.2)

            logger.info("Sifre yapıştırılıyor...")
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(timing.get("sifre_yazma"))
            logger.info("Sifre girildi")

            # ENTER tuşuna bas
            logger.info("Enter basilıyor...")
            pyautogui.press("enter")
            time.sleep(timing.get("giris_butonu"))
            time.sleep(timing.get("giris_sonrasi_bekleme"))
            logger.info("Giris yapildi, ana sayfa yukleniyor...")
            return True

        except Exception as e:
            logger.error(f"Sifre girisi basarisiz: {e}")
            import traceback
            traceback.print_exc()
            return False

    except Exception as e:
        logger.error(f"MEDULA giris hatasi: {e}")
        import traceback
        traceback.print_exc()
        return False


def recete_listesi_ac(bot):
    """
    MEDULA ana sayfasında "Reçete Listesi" butonuna tıkla

    Args:
        bot: BotanikBot instance

    Returns:
        bool: Başarılıysa True
    """
    try:
        from timing_settings import get_timing_settings

        timing = get_timing_settings()

        if not bot or not bot.main_window:
            logger.error("❌ Bot bağlantısı yok")
            return False

        # Ana sayfanın yüklenmesi için biraz bekle
        logger.info("⏳ Ana sayfa yüklenmesi bekleniyor (2 saniye)...")
        time.sleep(2.0)

        logger.debug("Reçete Listesi butonu aranıyor...")

        # "Reçete Listesi" butonunu bul - Tüm butonları tara
        try:
            logger.debug("Tüm butonlar taranıyor...")
            all_buttons = bot.main_window.descendants(control_type="Button")
            logger.debug(f"Toplam {len(all_buttons)} buton bulundu")

            # Debug: İlk 20 butonun metinlerini logla
            for i, btn in enumerate(all_buttons[:20]):
                try:
                    btn_text = btn.window_text()
                    if btn_text:
                        logger.info(f"  Buton {i+1}: '{btn_text}'")
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            # Şimdi gerçekten Reçete Listesi'ni ara
            for btn in all_buttons:
                try:
                    btn_text = btn.window_text()
                    if btn_text and "Reçete" in btn_text and "Listesi" in btn_text:
                        logger.info(f"✓ Reçete Listesi butonu bulundu: '{btn_text}'")
                        btn.click_input()
                        logger.info("✓ Reçete Listesi butonuna tıklandı")
                        time.sleep(timing.get("recete_listesi_butonu"))
                        time.sleep(timing.get("recete_listesi_acilma"))
                        return True
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            logger.warning("Buton text'inde bulunamadı, AutomationId ile denenecek...")
        except Exception as e:
            logger.debug(f"Buton tarama hatası: {e}")

        # Alternatif: AutomationId ile ara
        try:
            recete_listesi_btn = bot.main_window.descendants(auto_id="form1:menuHtmlCommandExButton31_MOUSE", control_type="Button")
            if recete_listesi_btn and len(recete_listesi_btn) > 0:
                recete_listesi_btn[0].click_input()
                logger.info("✓ Reçete Listesi butonuna tıklandı (AutomationId)")
                time.sleep(timing.get("recete_listesi_butonu"))
                time.sleep(timing.get("recete_listesi_acilma"))
                return True
        except Exception as e:
            logger.debug(f"AutomationId ile bulunamadı: {e}")

        # Son deneme: Title ile ara
        try:
            recete_listesi_btn = bot.main_window.descendants(title_re=".*Reçete Listesi.*", control_type="Button")
            if recete_listesi_btn and len(recete_listesi_btn) > 0:
                recete_listesi_btn[0].click_input()
                logger.info("✓ Reçete Listesi butonuna tıklandı (Title)")
                time.sleep(timing.get("recete_listesi_butonu"))
                time.sleep(timing.get("recete_listesi_acilma"))
                return True
        except Exception as e:
            logger.debug(f"Title ile bulunamadı: {e}")

        logger.error("❌ Reçete Listesi butonu bulunamadı - MEDULA yeniden başlatılacak")
        raise SistemselHataException("Reçete Listesi butonu bulunamadı - MEDULA takıldı olabilir")
    except Exception as e:
        logger.error(f"❌ Reçete Listesi açma hatası: {e} - MEDULA yeniden başlatılacak")
        raise SistemselHataException(f"Reçete Listesi açma hatası: {e}")


def donem_sec(bot, index=2, recovery_attempted=False):
    """
    Dönem seçme combobox'ında belirtilen index'i seç (0-based)

    Args:
        bot: BotanikBot instance
        index: Seçilecek item indexi (varsayılan: 2 = 3. sıradaki item)
        recovery_attempted: Oturum yenileme denendi mi? (iç kullanım)

    Returns:
        bool: Başarılıysa True
    """
    try:
        import pyautogui
        from timing_settings import get_timing_settings

        timing = get_timing_settings()

        if not bot or not bot.main_window:
            logger.error("❌ Bot bağlantısı yok")
            return False

        logger.info(f"🔘 Dönem seçiliyor (index={index})...")

        # Dönem combobox'ını bul ve koordinat ile tıkla
        try:
            # Tüm ComboBox'ları bul
            all_combos = bot.main_window.descendants(control_type="ComboBox")

            logger.info(f"Toplam {len(all_combos)} ComboBox bulundu")

            # ComboBox'ları logla
            for i, combo in enumerate(all_combos):
                try:
                    combo_text = combo.window_text()
                    logger.debug(f"ComboBox[{i}]: {combo_text}")
                except Exception as e:
                    logger.debug(f"ComboBox[{i}]: (text okunamadı - {type(e).__name__})")

            donem_combobox = None

            # Dönem combobox'ı genellikle 2. sırada (index=1)
            if len(all_combos) >= 2:
                donem_combobox = all_combos[1]  # İkinci ComboBox (index=1)
                logger.info("İkinci ComboBox (index=1) dönem olarak seçildi")
            elif len(all_combos) == 1:
                donem_combobox = all_combos[0]  # Tek ComboBox varsa onu kullan
                logger.info("Tek ComboBox bulundu, o kullanılıyor")
            else:
                logger.error("Hiç ComboBox bulunamadı")

                # ===== RECOVERY MEKANİZMASI =====
                if not recovery_attempted:
                    logger.warning("🔄 Oturum yenileme deneniyor...")
                    if bot.oturum_yenile():
                        logger.info("✓ Oturum yenilendi, tekrar deneniyor...")
                        # Bağlantıyı yenile
                        bot.baglanti_kur("MEDULA", ilk_baglanti=False)
                        time.sleep(1.0)
                        # Recursive çağrı - recovery_attempted=True ile
                        return donem_sec(bot, index, recovery_attempted=True)
                    else:
                        logger.error("❌ Oturum yenileme başarısız! MEDULA yeniden başlatılacak...")
                        raise SistemselHataException("Oturum yenileme başarısız - ComboBox bulunamadı")
                else:
                    # Recovery denendi ama hala ComboBox yok - taskkill gerekli
                    logger.error("❌ Recovery sonrası da ComboBox bulunamadı! MEDULA yeniden başlatılacak...")
                    raise SistemselHataException("Recovery sonrası ComboBox bulunamadı")

            if donem_combobox:
                # ComboBox'ın koordinatlarını al
                rect = donem_combobox.rectangle()
                x_center = (rect.left + rect.right) // 2
                y_center = (rect.top + rect.bottom) // 2

                logger.info(f"Dönem ComboBox koordinatları: x={x_center}, y={y_center}")

                # Koordinata tıkla
                logger.info("Dönem ComboBox'a tıklanıyor...")
                pyautogui.click(x_center, y_center)
                time.sleep(timing.get("donem_combobox_tiklama"))

                # Önce HOME tuşu ile en başa dön (önceki seçim hangi itemdeyse sıfırlansın)
                logger.info("HOME tuşu ile en başa dönülüyor...")
                pyautogui.press('home')
                time.sleep(0.3)

                # Index kadar DOWN tuşuna bas
                if index > 0:
                    logger.info(f"{index} kere DOWN tuşuna basılıyor...")
                    for i in range(index):
                        pyautogui.press('down')
                        time.sleep(0.2)
                else:
                    logger.info("Index 0, birinci dönem seçilecek")

                # Enter ile seç
                logger.info("Enter basılarak dönem seçiliyor...")
                pyautogui.press("enter")
                time.sleep(timing.get("donem_secim"))
                logger.info(f"✓ Dönem seçildi (index: {index})")
                return True
            else:
                logger.error("❌ Dönem ComboBox bulunamadı")
                return False

        except Exception as e:
            logger.error(f"❌ Dönem seçimi hatası: {e}")
            import traceback
            traceback.print_exc()
            return False
    except Exception as e:
        logger.error(f"❌ Dönem seçme hatası: {e}")
        return False


def grup_butonuna_tikla(bot, grup):
    """
    A/B/C grup butonuna tıkla

    Args:
        bot: BotanikBot instance
        grup: "A", "B" veya "C"

    Returns:
        bool: Başarılıysa True
    """
    try:
        from timing_settings import get_timing_settings

        timing = get_timing_settings()

        if not bot or not bot.main_window:
            logger.error("❌ Bot bağlantısı yok")
            return False

        logger.debug(f"{grup} grubu butonu aranıyor...")

        # Grup butonunu bul ve tıkla
        grup_mapping = {
            "A": "A",
            "B": "B",
            "C": "C Sıralı"
        }

        grup_text = grup_mapping.get(grup.upper())
        if not grup_text:
            logger.error(f"❌ Geçersiz grup: {grup}")
            return False

        try:
            # Text elementi bul
            grup_elements = bot.main_window.descendants(title=grup_text, control_type="Text")
            if grup_elements and len(grup_elements) > 0:
                # Text elementinin parent'ına tıkla (DataItem veya başka bir container olabilir)
                try:
                    # Text'in kendisine tıklayalım
                    grup_elements[0].click_input()
                    logger.info(f"✓ {grup} grubu butonuna tıklandı")
                    time.sleep(timing.get("grup_butonu_tiklama"))
                    time.sleep(timing.get("grup_sorgulama"))
                    return True
                except Exception as e:
                    logger.debug(f"Grup button click failed: {type(e).__name__}")
                    # Parent'a tıklamayı dene
                    parent = grup_elements[0].parent()
                    parent.click_input()
                    logger.info(f"✓ {grup} grubu butonuna tıklandı (parent)")
                    time.sleep(timing.get("grup_butonu_tiklama"))
                    time.sleep(timing.get("grup_sorgulama"))
                    return True
        except Exception as e:
            logger.debug(f"Text elementi ile bulunamadı: {e}")

        logger.error(f"❌ {grup} grubu butonu bulunamadı")
        return False
    except Exception as e:
        logger.error(f"❌ Grup butonu tıklama hatası: {e}")
        return False


def bulunamadi_mesaji_kontrol(bot):
    """
    "Bu döneme ait sonlandırılmamış reçete bulunamadı" mesajını kontrol et

    Args:
        bot: BotanikBot instance

    Returns:
        bool: Mesaj varsa True
    """
    try:
        from timing_settings import get_timing_settings

        timing = get_timing_settings()

        if not bot or not bot.main_window:
            logger.error("❌ Bot bağlantısı yok")
            return False

        logger.debug("🔍 'Bu döneme ait sonlandırılmamış reçete bulunamadı' mesajı aranıyor...")

        time.sleep(timing.get("bulunamadi_mesaji_kontrol"))

        # "Bu döneme ait sonlandırılmamış reçete bulunamadı" text elementini ara
        try:
            text_elements = bot.main_window.descendants(control_type="Text")
            for text in text_elements:
                try:
                    text_value = text.window_text()
                    if "Bu döneme ait sonlandırılmamış reçete bulunamadı" in text_value:
                        logger.info("✓ 'Bu döneme ait sonlandırılmamış reçete bulunamadı' mesajı bulundu")
                        return True
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")
        except Exception as e:
            logger.debug(f"Text element araması hatası: {e}")

        logger.debug("ℹ 'Bu döneme ait sonlandırılmamış reçete bulunamadı' mesajı bulunamadı")
        return False
    except Exception as e:
        logger.error(f"❌ Bulunamadı mesajı kontrolü hatası: {e}")
        return False


def ilk_recete_ac(bot):
    """
    "Son İşlem Tarihi" labelinin orta noktasından 26 piksel aşağıya tıklayarak ilk reçeteyi aç

    Args:
        bot: BotanikBot instance

    Returns:
        bool: Başarılıysa True
    """
    try:
        import pyautogui
        from timing_settings import get_timing_settings

        timing = get_timing_settings()

        if not bot or not bot.main_window:
            logger.error("❌ Bot bağlantısı yok")
            return False

        logger.info("🔘 İlk reçete açılıyor...")

        # "Son İşlem Tarihi" veya "Son İşl.Tar." labelini bul
        try:
            # Tüm Text elementlerini tara
            all_texts = bot.main_window.descendants(control_type="Text")

            son_islem_label = None

            for text_elem in all_texts:
                try:
                    text_value = text_elem.window_text()
                    if text_value and "Son İşl" in text_value:
                        son_islem_label = text_elem
                        logger.info(f"✓ Label bulundu: '{text_value}'")
                        break
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            if son_islem_label:
                # Koordinatları al
                rect = son_islem_label.rectangle()

                # Orta noktayı hesapla
                center_x = (rect.left + rect.right) // 2
                center_y = (rect.top + rect.bottom) // 2

                # 25 piksel aşağıya tıkla
                click_x = center_x
                click_y = center_y + 25

                logger.info(f"✓ Son İşlem Tarihi koordinatları: ({center_x}, {center_y})")
                logger.info(f"🖱 İlk reçete tıklanıyor: ({click_x}, {click_y})")

                # Çift tıkla (reçete açmak için genellikle çift tıklama gerekir)
                pyautogui.doubleClick(click_x, click_y)
                time.sleep(timing.get("ilk_recete_tiklama"))
                time.sleep(timing.get("recete_acilma"))

                logger.info("✓ İlk reçete açıldı")
                return True
            else:
                logger.error("❌ 'Son İşlem Tarihi' label bulunamadı")

                # Alternatif: İlk ListItem'ı dene
                logger.debug("Alternatif yöntem: İlk ListItem aranıyor...")
                list_items = bot.main_window.descendants(control_type="ListItem")

                if list_items and len(list_items) > 0:
                    first_item = list_items[0]
                    rect = first_item.rectangle()
                    center_x = (rect.left + rect.right) // 2
                    center_y = (rect.top + rect.bottom) // 2

                    logger.info(f"✓ İlk ListItem bulundu, çift tıklanıyor: ({center_x}, {center_y})")
                    pyautogui.doubleClick(center_x, center_y)
                    time.sleep(timing.get("ilk_recete_tiklama"))
                    time.sleep(timing.get("recete_acilma"))
                    return True
                else:
                    logger.error("❌ ListItem de bulunamadı")
                    return False

        except Exception as e:
            logger.error(f"❌ İlk reçete açma hatası: {e}")
            import traceback
            traceback.print_exc()
            return False
    except Exception as e:
        logger.error(f"❌ İlk reçete açma hatası: {e}")
        return False


def sonraki_gruba_gec_islemi(bot, sonraki_grup, son_recete=None):
    """
    Grup bittiğinde (Reçete kaydı bulunamadı) sonraki gruba geçiş işlemini yapar

    Akış:
    1. Geri Dön butonuna bas → Reçete Sorgu Ekranı'na dön
    2. Eğer son_recete VARSA:
       - Reçete Sorgu'ya git → Numara yaz → Sorgula (kaldığı yerden devam)
    3. Eğer son_recete YOKSA:
       - Dönem seç → Grup seç → İlk reçeteyi aç (en baştan başla)

    Args:
        bot: BotanikBot instance
        sonraki_grup: "A", "B" veya "C"
        son_recete: Hafızadaki son reçete numarası (varsa)

    Returns:
        bool: Başarılıysa True

    Raises:
        Exception: Herhangi bir adım başarısız olursa
    """
    try:
        from timing_settings import get_timing_settings

        timing = get_timing_settings()

        if not bot or not bot.main_window:
            logger.error("❌ Bot bağlantısı yok")
            raise Exception("Bot bağlantısı yok")

        logger.info("=" * 60)
        logger.info(f"🔄 GRUP GEÇİŞİ: {sonraki_grup} grubuna geçiliyor...")
        logger.info("=" * 60)

        # 1. Geri Dön butonuna bas
        logger.info("1️⃣ Geri Dön butonuna basılıyor...")
        if not bot.geri_don_butonuna_tikla():
            logger.error("❌ Geri Dön butonu başarısız")
            raise Exception("Geri Dön butonu başarısız")

        logger.info("✓ Reçete Sorgu Ekranı'na dönüldü")
        time.sleep(timing.get("adim_arasi_bekleme"))

        # Pencereyi yenile
        bot.baglanti_kur("MEDULA", ilk_baglanti=False)

        # ===== SON REÇETE KONTROLÜ =====
        if son_recete:
            # Hafızada reçete var - kaldığı yerden devam et
            logger.info(f"📍 Hafızada reçete var: {son_recete} - Kaldığı yerden devam ediliyor...")

            # 2. Reçete Sorgu'ya git (KADEMELİ KURTARMA ile)
            logger.info("2️⃣ Reçete Sorgu açılıyor...")
            if not bot.recete_sorgu_ac_kademeli():
                logger.error("❌ Reçete Sorgu açılamadı (kademeli kurtarma sonrası)")
                raise Exception("Reçete Sorgu açılamadı")

            logger.info("✓ Reçete Sorgu açıldı")
            time.sleep(timing.get("adim_arasi_bekleme"))

            # Pencereyi yenile
            bot.baglanti_kur("MEDULA", ilk_baglanti=False)

            # 3. Reçete numarası yaz
            logger.info(f"3️⃣ Reçete numarası yazılıyor: {son_recete}")
            if not bot.recete_no_yaz(son_recete):
                logger.error(f"❌ Reçete numarası yazılamadı: {son_recete}")
                raise Exception(f"Reçete numarası yazılamadı: {son_recete}")

            logger.info(f"✓ Reçete numarası yazıldı: {son_recete}")
            time.sleep(0.3)

            # 4. Sorgula butonuna tıkla
            logger.info("4️⃣ Sorgula butonuna tıklanıyor...")
            if not bot.sorgula_butonuna_tikla():
                logger.error("❌ Sorgula butonu başarısız")
                raise Exception("Sorgula butonu başarısız")

            logger.info(f"✓ Reçete açıldı: {son_recete}")

        else:
            # Hafızada reçete yok - en baştan başla
            logger.info("📍 Hafızada reçete yok - En baştan başlanıyor...")

            # 2. Dönem seç (önce index=2, bulunamadıysa index=1)
            logger.info("2️⃣ Dönem seçiliyor (index=2)...")
            if not donem_sec(bot, index=2):
                logger.error("❌ Dönem seçimi başarısız")
                raise Exception("Dönem seçimi başarısız")

            logger.info("✓ Dönem seçildi")
            time.sleep(timing.get("adim_arasi_bekleme"))

            # Pencereyi yenile
            bot.baglanti_kur("MEDULA", ilk_baglanti=False)

            # 3. Grup seç
            logger.info(f"3️⃣ {sonraki_grup} grubu seçiliyor...")
            if not grup_butonuna_tikla(bot, sonraki_grup):
                logger.error(f"❌ {sonraki_grup} grubu seçimi başarısız")
                raise Exception(f"{sonraki_grup} grubu seçimi başarısız")

            logger.info(f"✓ {sonraki_grup} grubu seçildi ve sorgulandı")
            time.sleep(timing.get("adim_arasi_bekleme"))

            # Pencereyi yenile
            bot.baglanti_kur("MEDULA", ilk_baglanti=False)

            # 4. "Bulunamadı" mesajı kontrolü
            logger.info("4️⃣ Reçete varlığı kontrol ediliyor...")
            if bulunamadi_mesaji_kontrol(bot):
                # Mesaj var, 2. dönemi dene (index=1)
                logger.info("⚠ 3. dönemde reçete yok, 2. dönem deneniyor...")

                # Dönem seç (index=1, yani 2. sıradaki)
                if not donem_sec(bot, index=1):
                    logger.error("❌ 2. dönem seçimi başarısız")
                    raise Exception("2. dönem seçimi başarısız")

                logger.info("✓ 2. dönem seçildi")
                time.sleep(timing.get("adim_arasi_bekleme"))

                # Pencereyi yenile
                bot.baglanti_kur("MEDULA", ilk_baglanti=False)

                # Grup seç (tekrar)
                logger.info(f"📁 {sonraki_grup} grubu (2. dönem) seçiliyor...")
                if not grup_butonuna_tikla(bot, sonraki_grup):
                    logger.error(f"❌ {sonraki_grup} grubu (2. dönem) seçimi başarısız")
                    raise Exception(f"{sonraki_grup} grubu (2. dönem) seçimi başarısız")

                logger.info(f"✓ {sonraki_grup} grubu (2. dönem) seçildi")
                time.sleep(timing.get("adim_arasi_bekleme"))

                # Pencereyi yenile
                bot.baglanti_kur("MEDULA", ilk_baglanti=False)

                # Tekrar kontrol et
                if bulunamadi_mesaji_kontrol(bot):
                    logger.error("❌ 2. dönemde de reçete bulunamadı")
                    raise Exception("2. dönemde de reçete bulunamadı")

            # 5. İlk reçeteyi aç
            logger.info("5️⃣ İlk reçete açılıyor...")
            if not ilk_recete_ac(bot):
                logger.error("❌ İlk reçete açılamadı")
                raise Exception("İlk reçete açılamadı")

            logger.info("✓ İlk reçete açıldı")

        # Pencereyi yenile
        bot.baglanti_kur("MEDULA", ilk_baglanti=False)

        # İlk reçete açıldıktan sonra popup kontrolü
        time.sleep(0.5)
        try:
            if popup_kontrol_ve_kapat():
                logger.info("✓ İlk reçete popup kapatıldı")
        except Exception as e:
            logger.warning(f"Popup kontrol hatası: {e}")

        logger.info("=" * 60)
        logger.info(f"✅ GRUP GEÇİŞİ BAŞARILI: {sonraki_grup} grubuna geçildi")
        logger.info("=" * 60)

        return True

    except Exception as e:
        logger.error(f"❌ Grup geçişi hatası: {e}")
        import traceback
        traceback.print_exc()
        raise


def medula_ac_ve_giris_yap(medula_settings):
    """
    Masaüstünden MEDULA'yı aç ve giriş yap

    Args:
        medula_settings: MEDULA ayarları instance'ı

    Returns:
        bool: Başarılıysa True
    """
    try:
        from pywinauto import Desktop
        import pyautogui

        # 1. MEDULA'yı exe path ile başlat
        logger.info("📍 MEDULA EXE başlatılıyor...")
        import subprocess

        desktop = Desktop(backend="uia")

        medula_exe = medula_settings.get("medula_exe_path")
        if not medula_exe or medula_exe == "":
            logger.error("❌ MEDULA exe path ayarlanmamış!")
            return False

        try:
            subprocess.Popen([medula_exe])
            logger.info(f"✓ MEDULA başlatıldı: {medula_exe}")
            time.sleep(8)  # MEDULA'nın açılması için bekle (5 → 8 saniye, taskkill sonrası daha fazla zaman gerekir)
        except Exception as e:
            logger.error(f"❌ MEDULA başlatılamadı: {e}")
            return False

        # 2. Giriş penceresini bekle
        logger.info("⏳ MEDULA giriş penceresi bekleniyor...")
        time.sleep(5)  # Giriş penceresi için ek bekleme (3 → 5 saniye)

        # 3. Aktif kullanıcının bilgilerini al
        aktif_kullanici = medula_settings.get_aktif_kullanici()
        if not aktif_kullanici:
            logger.error("❌ Aktif kullanıcı bulunamadı!")
            return False

        kullanici_index = aktif_kullanici.get("kullanici_index", 0)
        sifre = aktif_kullanici.get("sifre")
        kullanici_ad = aktif_kullanici.get("ad", "Kullanıcı")

        if not sifre:
            logger.error(f"❌ {kullanici_ad} için şifre ayarlanmamış!")
            return False

        # Giriş yöntemi kontrolü
        giris_yontemi = medula_settings.get("giris_yontemi", "indeks")
        kullanici_adi_giris = medula_settings.get("kullanici_adi_giris", "")

        if giris_yontemi == "indeks":
            logger.info(f"🔐 {kullanici_ad} ile giriş yapılıyor (İndeks yöntemi - MEDULA Index: {kullanici_index})")
        else:
            logger.info(f"🔐 {kullanici_ad} ile giriş yapılıyor (Kullanıcı Adı yöntemi - MEDULA Kullanıcı: {kullanici_adi_giris})")

        # Giriş penceresini bul
        try:
            giris_window = None
            for window in desktop.windows():
                window_text = window.window_text()
                # BotanikEOS penceresini bul (giriş ekranı)
                if "BotanikEOS" in window_text or "MEDULA" in window_text:
                    giris_window = window
                    logger.info(f"✓ Pencere bulundu: {window_text}")
                    break

            if not giris_window:
                logger.error("❌ MEDULA giriş penceresi bulunamadı")
                return False

            logger.info("✓ Giriş penceresi bulundu")

            # Giriş penceresini aktif hale getir ve odaklan
            try:
                giris_window.set_focus()
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"Pencere focus hatası (devam ediliyor): {e}")

            # YÖNTEM 1: AutomationId ile doğrudan elementleri bul (inspect.exe bilgileri)
            # ComboBox: cmbKullanicilar, Şifre: txtSifre, Giriş: btnGirisYap
            kullanici_combo = None
            sifre_textbox = None
            giris_button = None

            try:
                # ComboBox'ı bul (AutomationId: cmbKullanicilar)
                kullanici_combo = giris_window.child_window(auto_id="cmbKullanicilar", control_type="ComboBox")
                if kullanici_combo.exists(timeout=2):
                    logger.info("✓ Kullanıcı ComboBox bulundu (cmbKullanicilar)")
                else:
                    kullanici_combo = None
                    logger.warning("⚠ ComboBox AutomationId ile bulunamadı")
            except Exception as e:
                logger.debug(f"ComboBox arama hatası: {e}")
                kullanici_combo = None

            try:
                # Şifre TextBox'ı bul (AutomationId: txtSifre)
                sifre_textbox = giris_window.child_window(auto_id="txtSifre", control_type="Edit")
                if sifre_textbox.exists(timeout=2):
                    logger.info("✓ Şifre TextBox bulundu (txtSifre)")
                else:
                    sifre_textbox = None
                    logger.warning("⚠ Şifre TextBox AutomationId ile bulunamadı")
            except Exception as e:
                logger.debug(f"Şifre TextBox arama hatası: {e}")
                sifre_textbox = None

            try:
                # Giriş butonu bul (AutomationId: btnGirisYap)
                giris_button = giris_window.child_window(auto_id="btnGirisYap", control_type="Button")
                if giris_button.exists(timeout=2):
                    logger.info("✓ Giriş butonu bulundu (btnGirisYap)")
                else:
                    giris_button = None
                    logger.warning("⚠ Giriş butonu AutomationId ile bulunamadı")
            except Exception as e:
                logger.debug(f"Giriş butonu arama hatası: {e}")
                giris_button = None

            # Eğer AutomationId ile bulamazsak, ClassName veya Name ile dene
            if not giris_button:
                try:
                    # Name="Giriş" ile dene
                    giris_button = giris_window.child_window(title="Giriş", control_type="Button")
                    if giris_button.exists(timeout=1):
                        logger.info("✓ Giriş butonu bulundu (Name='Giriş')")
                except Exception as e:
                    logger.debug(f"Giriş butonu Name ile arama hatası: {e}")

            # ComboBox işlemi (AutomationId ile bulunduysa)
            if kullanici_combo:
                try:
                    kullanici_combo.click_input()
                    time.sleep(0.3)

                    # Alt+Down ile dropdown'u aç
                    pyautogui.keyDown("alt")
                    pyautogui.press("down")
                    pyautogui.keyUp("alt")
                    time.sleep(0.5)

                    # Giriş yöntemine göre kullanıcı seçimi
                    if giris_yontemi == "kullanici_adi":
                        if kullanici_adi_giris:
                            logger.info(f"Kullanıcı adı yazılıyor: {kullanici_adi_giris}")
                            pyautogui.typewrite(kullanici_adi_giris, interval=0.1)
                            time.sleep(0.3)
                            pyautogui.press("enter")
                            time.sleep(0.5)
                            logger.info(f"✓ Kullanıcı seçildi (ad: {kullanici_adi_giris})")
                        else:
                            pyautogui.press("enter")
                            time.sleep(0.5)
                    else:
                        # İndeks ile seçim
                        logger.info(f"Combobox'tan {kullanici_ad} seçiliyor (Index: {kullanici_index})...")
                        for i in range(kullanici_index):
                            pyautogui.press("down")
                            time.sleep(0.1)
                        pyautogui.press("enter")
                        time.sleep(0.5)
                        logger.info(f"✓ {kullanici_ad} seçildi")
                except Exception as e:
                    logger.warning(f"⚠ ComboBox işlemi başarısız: {e}")
            else:
                # Fallback: Tab ile combobox'a git (eski yöntem)
                try:
                    pyautogui.press("tab")
                    time.sleep(0.3)
                    pyautogui.keyDown("alt")
                    pyautogui.press("down")
                    pyautogui.keyUp("alt")
                    time.sleep(0.5)

                    if giris_yontemi == "kullanici_adi":
                        if kullanici_adi_giris:
                            pyautogui.typewrite(kullanici_adi_giris, interval=0.1)
                            time.sleep(0.3)
                        pyautogui.press("enter")
                        time.sleep(0.5)
                    else:
                        for i in range(kullanici_index):
                            pyautogui.press("down")
                            time.sleep(0.1)
                        pyautogui.press("enter")
                        time.sleep(0.5)
                except Exception as e:
                    logger.warning(f"⚠ ComboBox fallback başarısız: {e}")

            # Şifre girişi (AutomationId ile bulunduysa)
            if sifre_textbox:
                try:
                    sifre_textbox.click_input()
                    time.sleep(0.3)
                    sifre_textbox.set_edit_text("")  # Temizle
                    time.sleep(0.2)
                    sifre_textbox.type_keys(sifre, with_spaces=True)
                    time.sleep(0.5)
                    logger.info("✓ Şifre girildi (AutomationId ile)")
                except Exception as e:
                    logger.warning(f"⚠ Şifre girişi AutomationId ile başarısız: {e}, PyAutoGUI deneniyor...")
                    # Fallback: PyAutoGUI ile şifre yaz
                    try:
                        sifre_textbox.click_input()
                        time.sleep(0.2)
                        pyautogui.hotkey('ctrl', 'a')
                        time.sleep(0.1)
                        pyautogui.press('backspace')
                        time.sleep(0.2)
                        pyautogui.write(sifre, interval=0.05)
                        time.sleep(0.5)
                        logger.info("✓ Şifre girildi (PyAutoGUI fallback)")
                    except Exception as e2:
                        logger.error(f"❌ Şifre girişi tamamen başarısız: {e2}")
            else:
                # Fallback: Tab ile şifre alanına git
                try:
                    pyautogui.press("tab")
                    time.sleep(0.2)
                    pyautogui.press("tab")
                    time.sleep(0.3)
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.1)
                    pyautogui.press('backspace')
                    time.sleep(0.2)
                    pyautogui.write(sifre, interval=0.05)
                    time.sleep(0.5)
                    logger.info("✓ Şifre girildi (Tab fallback)")
                except Exception as e:
                    logger.error(f"❌ Şifre girişi fallback başarısız: {e}")

            # Giriş butonu tıklama (AutomationId ile bulunduysa)
            if giris_button:
                try:
                    giris_button.click_input()
                    logger.info("✓ Giriş butonuna tıklandı (AutomationId ile)")
                    time.sleep(4)
                except Exception as e:
                    logger.warning(f"⚠ Giriş butonu tıklama başarısız: {e}, ENTER deneniyor...")
                    pyautogui.press("enter")
                    time.sleep(4)
            else:
                # Fallback: ENTER tuşuna bas
                logger.info("Giriş butonu bulunamadı, ENTER tuşu basılıyor...")
                pyautogui.press("enter")
                time.sleep(4)

            # Giriş başarılı mı kontrol et
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")

            # 5 saniye boyunca MEDULA ana penceresini bekle
            medula_bulundu = False
            for bekleme in range(10):  # 10 * 0.5 = 5 saniye
                for window in desktop.windows():
                    try:
                        window_text = window.window_text()
                        if "MEDULA" in window_text:
                            logger.info("✓ Giriş yapıldı - MEDULA ana penceresi açıldı")
                            medula_bulundu = True
                            return True
                    except Exception as e:
                        logger.debug(f"Operation failed: {type(e).__name__}")
                if medula_bulundu:
                    break
                time.sleep(0.5)

            # Giriş penceresi hala açıksa şifre yanlış demektir
            for window in desktop.windows():
                try:
                    if "MEDULA" in window.window_text():
                        logger.error("❌ Giriş başarısız - Şifre yanlış olabilir")
                        return False
                except Exception as e:
                    logger.debug(f"Operation failed: {type(e).__name__}")

            logger.warning("⚠ Giriş durumu belirsiz")
            return False

        except Exception as e:
            logger.error(f"❌ Giriş işlemi başarısız: {e}")
            return False

        return False
    except Exception as e:
        logger.error(f"❌ MEDULA açma/giriş hatası: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# REÇETE KONTROL FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════════════════

def recete_turu_oku(bot, max_deneme=3):
    """
    Reçete türünü oku (Normal, Yeşil, Kırmızı, vb.)

    Element bilgileri:
    - HTML Id: f:m4
    - Element Type: SELECT (dropdown)
    - CSS Selector: #f:m4
    - Değerler: Normal, Kırmızı, Turuncu, Mor, Yeşil

    Args:
        bot: BotanikBot instance
        max_deneme: Maksimum deneme sayısı

    Returns:
        str: Reçete türü (Normal, Yeşil, Kırmızı vb.) veya None
    """
    for deneme in range(max_deneme):
        try:
            # Yöntem 1: auto_id ile SELECT elementi bul
            try:
                select_element = bot.main_window.child_window(
                    auto_id="f:m4",
                    control_type="ComboBox"
                )
                if select_element.exists(timeout=0.5):
                    # Seçili değeri al
                    try:
                        secili_deger = select_element.selected_text()
                        if secili_deger:
                            logger.info(f"✓ Reçete türü okundu: {secili_deger}")
                            return secili_deger.strip()
                    except Exception:
                        pass

                    # Alternatif: window_text ile dene
                    try:
                        text = select_element.window_text()
                        if text:
                            logger.info(f"✓ Reçete türü okundu (window_text): {text}")
                            return text.strip()
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"ComboBox yöntemi başarısız: {e}")

            # Yöntem 2: descendants ile ara
            try:
                elements = bot.main_window.descendants(auto_id="f:m4")
                if elements and len(elements) > 0:
                    element = elements[0]

                    # selected_text dene
                    try:
                        secili_deger = element.selected_text()
                        if secili_deger:
                            logger.info(f"✓ Reçete türü okundu (descendants): {secili_deger}")
                            return secili_deger.strip()
                    except Exception:
                        pass

                    # window_text dene
                    try:
                        text = element.window_text()
                        if text:
                            # SELECT'te tüm seçenekler gelebilir, ilk satırı al
                            ilk_satir = text.split('\n')[0].strip()
                            if ilk_satir:
                                logger.info(f"✓ Reçete türü okundu (window_text): {ilk_satir}")
                                return ilk_satir
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"descendants yöntemi başarısız: {e}")

            # Yöntem 3: Tüm Text elementlerinden "Reçete Türü" label'ının yanındaki değeri bul
            try:
                texts = bot.main_window.descendants(control_type="Text")
                recete_turu_bulundu = False
                for text in texts:
                    try:
                        icerik = text.window_text() or ""
                        # "Normal", "Yeşil", "Kırmızı" gibi değerler
                        if icerik.strip() in ["Normal", "Yeşil", "Kırmızı", "Turuncu", "Mor"]:
                            logger.info(f"✓ Reçete türü okundu (Text scan): {icerik.strip()}")
                            return icerik.strip()
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"Text scan yöntemi başarısız: {e}")

            # Deneme başarısız, kısa bekle
            if deneme < max_deneme - 1:
                time.sleep(0.3)

        except Exception as e:
            logger.warning(f"Reçete türü okuma hatası (deneme {deneme + 1}): {e}")
            if deneme < max_deneme - 1:
                time.sleep(0.3)

    logger.warning("⚠ Reçete türü okunamadı")
    return None


def tek_recete_rapor_kontrol(bot, recete_sira_no, grup="", session_logger=None, stop_check=None,
                              onceden_okunan_recete_no=None, renkli_kontrol=None):
    """
    Tek bir reçete için SADECE rapor kontrol işlemi yap.
    (İlaç takip ve rapor toplama YOK - sadece renkli reçete kontrolü)

    Args:
        bot: BotanikBot instance
        recete_sira_no: Reçete sıra numarası (1, 2, 3...)
        grup: Grup bilgisi (A, B, C, GK)
        session_logger: SessionLogger instance
        stop_check: Durdurma kontrolü callback
        onceden_okunan_recete_no: Önceden okunan reçete numarası
        renkli_kontrol: RenkliReceteKontrol instance

    Returns:
        tuple: (başarı, medula_recete_no, sorun_var_mi, mesaj)
    """
    # Durdurma kontrolü
    def should_stop():
        if stop_check and callable(stop_check):
            return stop_check()
        return False

    if should_stop():
        logger.info("⏸ İşlem durduruldu (kullanıcı talebi)")
        return (False, None, False, "Kullanıcı tarafından durduruldu")

    medula_recete_no = None

    try:
        # 1. Reçete numarasını al
        if onceden_okunan_recete_no:
            medula_recete_no = onceden_okunan_recete_no
        else:
            # Hızlı tarama ile reçete no al
            hizli_sonuc = bot.recete_sayfasi_hizli_tarama(max_deneme=2, bekleme_suresi=0.15)
            if hizli_sonuc:
                medula_recete_no = hizli_sonuc.get('recete_no')
            else:
                # Fallback
                birlesik_sonuc = bot.recete_telefon_kontrol_birlesik(max_deneme=2, bekleme_suresi=0.2)
                medula_recete_no = birlesik_sonuc.get('recete_no')

        if not medula_recete_no:
            logger.warning(f"⚠ Reçete {recete_sira_no}: Numara okunamadı")
            return (False, None, False, "Reçete numarası okunamadı")

        logger.info(f"📋 REÇETE {recete_sira_no} | No: {medula_recete_no}")

        # 2. Reçete türünü oku
        recete_turu = recete_turu_oku(bot)

        if not recete_turu:
            logger.warning(f"⚠ Reçete {medula_recete_no}: Tür okunamadı, Normal kabul ediliyor")
            recete_turu = "Normal"

        logger.info(f"📝 Reçete türü: {recete_turu}")

        # 3. Renkli reçete kontrolü
        sorun_var = False
        mesaj = ""

        if renkli_kontrol:
            sorun_var, mesaj = renkli_kontrol.kontrol_et(medula_recete_no, recete_turu, grup)
            if sorun_var:
                logger.warning(f"⚠ {mesaj}")
        else:
            logger.debug("Renkli reçete kontrolü aktif değil")

        # 4. İlaç tablosu kontrolü (Msj ve Rapor kontrolü)
        if should_stop():
            return (True, medula_recete_no, sorun_var, "Durduruldu")

        try:
            ilac_rapor = tum_ilaclari_kontrol_et(bot, session_logger, stop_check)

            if ilac_rapor['msj_var_sayisi'] > 0:
                logger.info(f"⚠ Reçetede {ilac_rapor['msj_var_sayisi']} adet mesaj içeren ilaç var")
                # Mesaj detaylarını ekle
                for detay in ilac_rapor['detaylar']:
                    if detay['msj'] == 'var' and detay['mesaj_metni']:
                        if mesaj:
                            mesaj += f"\n• Satır {detay['satir']}: {detay['mesaj_metni'][:100]}..."
                        else:
                            mesaj = f"• Satır {detay['satir']}: {detay['mesaj_metni'][:100]}..."

            if ilac_rapor['sorunlu_sayisi'] > 0:
                sorun_var = True
                logger.warning(f"⚠ Reçetede {ilac_rapor['sorunlu_sayisi']} adet sorunlu ilaç var")

        except Exception as e:
            logger.error(f"İlaç tablosu kontrol hatası: {e}")

        # 5. Sonraki reçeteye geç
        if should_stop():
            return (True, medula_recete_no, sorun_var, "Durduruldu")

        sonra = bot.retry_with_popup_check(
            lambda: bot.sonra_butonuna_tikla(),
            "SONRA butonu",
            max_retries=5
        )

        if not sonra:
            logger.error(f"❌ Reçete {medula_recete_no}: SONRA butonu başarısız")
            return (False, medula_recete_no, sorun_var, "SONRA butonu başarısız")

        return (True, medula_recete_no, sorun_var, mesaj if sorun_var else "OK")

    except Exception as e:
        logger.error(f"❌ Reçete kontrol hatası: {e}")
        return (False, medula_recete_no, False, str(e))


# =============================================================================
# İLAÇ TABLOSU KONTROL FONKSİYONLARI
# =============================================================================

def ilac_tablosu_satir_sayisi_oku(bot, max_satir=20):
    """
    İlaç tablosundaki satır sayısını tespit et.

    Args:
        bot: BotanikBot instance
        max_satir: Maksimum kontrol edilecek satır sayısı

    Returns:
        int: Satır sayısı (0 ise tablo boş veya okunamadı)
    """
    try:
        satir_sayisi = 0

        for i in range(max_satir):
            # Her satırın checkbox'ını kontrol et
            checkbox_id = f"f:tbl1:{i}:checkbox7"

            try:
                element = bot.find_element_safe(checkbox_id, timeout=0.5)
                if element:
                    satir_sayisi += 1
                else:
                    break
            except:
                break

        logger.debug(f"İlaç tablosu satır sayısı: {satir_sayisi}")
        return satir_sayisi

    except Exception as e:
        logger.error(f"İlaç tablosu satır sayısı okuma hatası: {e}")
        return 0


def ilac_satiri_msj_oku(bot, satir_index):
    """
    Belirtilen satırdaki Msj sütununu oku.

    Args:
        bot: BotanikBot instance
        satir_index: Satır indexi (0'dan başlar)

    Returns:
        str: "var", "yok" veya None (okunamadı)
    """
    try:
        msj_id = f"f:tbl1:{satir_index}:t11"

        element = bot.find_element_safe(msj_id, timeout=1)
        if element:
            msj_deger = element.get_attribute("value") or element.text or element.get_attribute("innerText")
            if msj_deger:
                msj_deger = msj_deger.strip().lower()
                logger.debug(f"Satır {satir_index} Msj: {msj_deger}")
                return msj_deger

        # UI Automation ile dene
        try:
            from System.Windows.Automation import AutomationElement, PropertyCondition, AutomationProperty
            from System.Windows.Automation import TreeScope

            # Name property ile ara
            condition = PropertyCondition(AutomationElement.AutomationIdProperty, msj_id)
            elem = bot.root_element.FindFirst(TreeScope.Descendants, condition)
            if elem:
                name = elem.Current.Name
                if name:
                    logger.debug(f"Satır {satir_index} Msj (UIA): {name}")
                    return name.strip().lower()
        except:
            pass

        return None

    except Exception as e:
        logger.error(f"Msj okuma hatası (satır {satir_index}): {e}")
        return None


def ilac_satiri_rapor_kodu_oku(bot, satir_index):
    """
    Belirtilen satırdaki Rapor kodunu oku.

    Args:
        bot: BotanikBot instance
        satir_index: Satır indexi (0'dan başlar)

    Returns:
        str: Rapor kodu (örn: "04.05") veya None/boş (raporsuz)
    """
    try:
        rapor_id = f"f:tbl1:{satir_index}:t9"

        element = bot.find_element_safe(rapor_id, timeout=1)
        if element:
            rapor_kodu = element.get_attribute("value") or element.text or element.get_attribute("innerText")
            if rapor_kodu:
                rapor_kodu = rapor_kodu.strip()
                if rapor_kodu:
                    logger.debug(f"Satır {satir_index} Rapor kodu: {rapor_kodu}")
                    return rapor_kodu

        # UI Automation ile dene
        try:
            from System.Windows.Automation import AutomationElement, PropertyCondition
            from System.Windows.Automation import TreeScope

            condition = PropertyCondition(AutomationElement.AutomationIdProperty, rapor_id)
            elem = bot.root_element.FindFirst(TreeScope.Descendants, condition)
            if elem:
                name = elem.Current.Name
                if name and name.strip():
                    logger.debug(f"Satır {satir_index} Rapor kodu (UIA): {name}")
                    return name.strip()
        except:
            pass

        return None  # Raporsuz

    except Exception as e:
        logger.error(f"Rapor kodu okuma hatası (satır {satir_index}): {e}")
        return None


def ilac_satiri_checkbox_sec(bot, satir_index, sec=True):
    """
    Belirtilen satırdaki checkbox'ı seç veya kaldır.

    Args:
        bot: BotanikBot instance
        satir_index: Satır indexi (0'dan başlar)
        sec: True=seç, False=kaldır

    Returns:
        bool: Başarılı mı
    """
    try:
        checkbox_id = f"f:tbl1:{satir_index}:checkbox7"

        element = bot.find_element_safe(checkbox_id, timeout=2)
        if element:
            # Mevcut durumu kontrol et
            is_selected = element.is_selected() if hasattr(element, 'is_selected') else False

            if sec and not is_selected:
                element.click()
                logger.debug(f"Satır {satir_index} checkbox seçildi")
                return True
            elif not sec and is_selected:
                element.click()
                logger.debug(f"Satır {satir_index} checkbox kaldırıldı")
                return True
            else:
                logger.debug(f"Satır {satir_index} checkbox zaten istenen durumda")
                return True

        logger.warning(f"Satır {satir_index} checkbox bulunamadı")
        return False

    except Exception as e:
        logger.error(f"Checkbox seçme hatası (satır {satir_index}): {e}")
        return False


def ilac_bilgi_butonuna_tikla(bot):
    """
    İlaç Bilgi butonuna tıkla.

    Returns:
        bool: Başarılı mı
    """
    try:
        buton_id = "f:buttonIlacBilgiGorme"

        element = bot.find_element_safe(buton_id, timeout=2)
        if element:
            element.click()
            time.sleep(0.5)  # Pencerenin açılmasını bekle
            logger.debug("İlaç Bilgi butonuna tıklandı")
            return True

        # UI Automation ile dene - Name ile ara
        try:
            from System.Windows.Automation import AutomationElement, PropertyCondition
            from System.Windows.Automation import TreeScope

            condition = PropertyCondition(AutomationElement.NameProperty, "İlaç Bilgi")
            elem = bot.root_element.FindFirst(TreeScope.Descendants, condition)
            if elem:
                from System.Windows.Automation import InvokePattern
                pattern = elem.GetCurrentPattern(InvokePattern.Pattern)
                if pattern:
                    pattern.Invoke()
                    time.sleep(0.5)
                    logger.debug("İlaç Bilgi butonuna tıklandı (UIA)")
                    return True
        except:
            pass

        logger.warning("İlaç Bilgi butonu bulunamadı")
        return False

    except Exception as e:
        logger.error(f"İlaç Bilgi butonu tıklama hatası: {e}")
        return False


def ilac_bilgi_penceresi_mesaj_oku(bot):
    """
    İlaç Bilgi penceresindeki mesaj metnini oku.

    Returns:
        str: Mesaj metni veya None
    """
    try:
        mesaj_id = "form1:textarea1"

        element = bot.find_element_safe(mesaj_id, timeout=2)
        if element:
            mesaj = element.get_attribute("value") or element.text or element.get_attribute("innerText")
            if mesaj:
                logger.debug(f"İlaç mesajı okundu: {mesaj[:100]}...")
                return mesaj.strip()

        return None

    except Exception as e:
        logger.error(f"İlaç mesajı okuma hatası: {e}")
        return None


def ilac_bilgi_penceresi_raporlu_doz_oku(bot):
    """
    İlaç Bilgi penceresindeki Raporlu Maks. Kul. Doz değerini oku.

    Returns:
        dict: {'periyot': int, 'birim': str, 'carpan': int, 'doz': float} veya None
        Örnek: {'periyot': 1, 'birim': 'Günde', 'carpan': 1, 'doz': 1.0}
    """
    try:
        # "Raporlu Maks. Kul. Doz" label'ını bul ve değerini oku
        # Format: "1 Günde 1 x 1.0"

        from System.Windows.Automation import AutomationElement, PropertyCondition, TreeScope

        # Önce "Raporlu Maks. Kul. Doz" metnini bul
        condition = PropertyCondition(AutomationElement.NameProperty, "Raporlu Maks. Kul. Doz")
        label_elem = bot.root_element.FindFirst(TreeScope.Descendants, condition)

        if label_elem:
            # Label'dan sonraki değerleri topla
            # Genelde ":" dan sonra değerler geliyor
            # UI yapısında: 1, Günde, 1, x, 1.0 şeklinde ayrı elementler

            parent = TreeWalker.ContentViewWalker.GetParent(label_elem)
            if parent:
                children = parent.FindAll(TreeScope.Children, Condition.TrueCondition)

                doz_parts = []
                found_label = False
                for child in children:
                    name = child.Current.Name
                    if "Raporlu Maks" in str(name):
                        found_label = True
                        continue
                    if found_label and name and name.strip() not in [':', '']:
                        doz_parts.append(name.strip())

                if len(doz_parts) >= 4:
                    # Parse et: ['1', 'Günde', '1', 'x', '1.0']
                    try:
                        return {
                            'periyot': int(doz_parts[0]),
                            'birim': doz_parts[1],
                            'carpan': int(doz_parts[2]),
                            'doz': float(doz_parts[4].replace(',', '.')) if len(doz_parts) > 4 else float(doz_parts[3].replace(',', '.'))
                        }
                    except:
                        pass

        return None

    except Exception as e:
        logger.error(f"Raporlu doz okuma hatası: {e}")
        return None


def ilac_bilgi_penceresi_kapat(bot):
    """
    İlaç Bilgi penceresini kapat.

    Returns:
        bool: Başarılı mı
    """
    try:
        kapat_id = "form1:buttonKapat"

        element = bot.find_element_safe(kapat_id, timeout=2)
        if element:
            element.click()
            time.sleep(0.3)
            logger.debug("İlaç Bilgi penceresi kapatıldı")
            return True

        # UI Automation ile dene
        try:
            from System.Windows.Automation import AutomationElement, PropertyCondition
            from System.Windows.Automation import TreeScope

            condition = PropertyCondition(AutomationElement.NameProperty, "Kapat")
            elem = bot.root_element.FindFirst(TreeScope.Descendants, condition)
            if elem:
                from System.Windows.Automation import InvokePattern
                pattern = elem.GetCurrentPattern(InvokePattern.Pattern)
                if pattern:
                    pattern.Invoke()
                    time.sleep(0.3)
                    logger.debug("İlaç Bilgi penceresi kapatıldı (UIA)")
                    return True
        except:
            pass

        logger.warning("Kapat butonu bulunamadı")
        return False

    except Exception as e:
        logger.error(f"Pencere kapatma hatası: {e}")
        return False


def ilac_satiri_ilac_adi_oku(bot, satir_index):
    """
    Belirtilen satırdaki ilaç adını oku.

    Args:
        bot: BotanikBot instance
        satir_index: Satır indexi (0'dan başlar)

    Returns:
        str: İlaç adı (örn: "ATOR 20 MG.30 TB.") veya None
    """
    try:
        ilac_adi_id = f"f:tbl1:{satir_index}:t6"

        element = bot.find_element_safe(ilac_adi_id, timeout=1)
        if element:
            ilac_adi = element.get_attribute("value") or element.text or element.get_attribute("innerText")
            if ilac_adi:
                ilac_adi = ilac_adi.strip()
                logger.debug(f"Satır {satir_index} İlaç adı: {ilac_adi}")
                return ilac_adi

        # UI Automation ile dene
        try:
            from System.Windows.Automation import AutomationElement, PropertyCondition, TreeScope
            condition = PropertyCondition(AutomationElement.AutomationIdProperty, ilac_adi_id)
            elem = bot.root_element.FindFirst(TreeScope.Descendants, condition)
            if elem:
                name = elem.Current.Name
                if name:
                    logger.debug(f"Satır {satir_index} İlaç adı (UIA): {name}")
                    return name.strip()
        except:
            pass

        return None

    except Exception as e:
        logger.error(f"İlaç adı okuma hatası (satır {satir_index}): {e}")
        return None


def ilac_bilgi_etkin_madde_oku(bot):
    """
    İlaç Bilgi penceresindeki etkin madde adını oku.
    Element: form1:text35

    Returns:
        str: Etkin madde (örn: "ATORVASTATIN KALSIYUM") veya None
    """
    try:
        etkin_madde_id = "form1:text35"

        element = bot.find_element_safe(etkin_madde_id, timeout=2)
        if element:
            etkin_madde = element.get_attribute("value") or element.text or element.get_attribute("innerText")
            if etkin_madde:
                etkin_madde = etkin_madde.strip()
                logger.debug(f"Etkin madde: {etkin_madde}")
                return etkin_madde

        return None

    except Exception as e:
        logger.error(f"Etkin madde okuma hatası: {e}")
        return None


def ilac_bilgi_sgk_kodu_oku(bot):
    """
    İlaç Bilgi penceresindeki SGK kodunu oku.
    Element: form1:text2

    Returns:
        str: SGK kodu (örn: "SGKESD") veya None
    """
    try:
        sgk_kodu_id = "form1:text2"

        element = bot.find_element_safe(sgk_kodu_id, timeout=2)
        if element:
            sgk_kodu = element.get_attribute("value") or element.text or element.get_attribute("innerText")
            if sgk_kodu:
                sgk_kodu = sgk_kodu.strip()
                logger.debug(f"SGK kodu: {sgk_kodu}")
                return sgk_kodu

        return None

    except Exception as e:
        logger.error(f"SGK kodu okuma hatası: {e}")
        return None


def ilac_mesaj_basligi_oku(bot, mesaj_index=0):
    """
    İlaç Bilgi penceresindeki mesaj başlığını oku.
    Tıklanabilir mesaj listesindeki başlık (SUT maddesi içerir).
    Element: form1:tableExIlacMesajListesi:{index}:text19

    Args:
        bot: BotanikBot instance
        mesaj_index: Mesaj indexi (0'dan başlar)

    Returns:
        dict: {'baslik': str, 'sut_maddesi': str} veya None
        Örnek: {'baslik': '1028(4) - 4.2.28.A-Statinler...', 'sut_maddesi': '4.2.28.A'}
    """
    try:
        baslik_id = f"form1:tableExIlacMesajListesi:{mesaj_index}:text19"

        element = bot.find_element_safe(baslik_id, timeout=2)
        baslik_text = None
        if element:
            baslik_text = element.get_attribute("value") or element.text or element.get_attribute("innerText")

        if not baslik_text:
            # UI Automation ile dene
            try:
                from System.Windows.Automation import AutomationElement, PropertyCondition, TreeScope
                condition = PropertyCondition(AutomationElement.AutomationIdProperty, baslik_id)
                elem = bot.root_element.FindFirst(TreeScope.Descendants, condition)
                if elem:
                    baslik_text = elem.Current.Name
            except:
                pass

        if baslik_text:
            baslik_text = baslik_text.strip()
            logger.debug(f"Mesaj başlığı: {baslik_text}")

            # SUT maddesi çıkar: "1028(4) - 4.2.28.A-Statinler..." -> "4.2.28.A"
            sut_maddesi = None
            import re
            match = re.search(r'(\d+\.\d+\.\d+(?:\.[A-Z])?)', baslik_text)
            if match:
                sut_maddesi = match.group(1)

            return {
                'baslik': baslik_text,
                'sut_maddesi': sut_maddesi
            }

        return None

    except Exception as e:
        logger.error(f"Mesaj başlığı okuma hatası: {e}")
        return None


def ilac_mesaj_basligina_tikla(bot, mesaj_index=0):
    """
    İlaç Bilgi penceresindeki mesaj başlığına tıkla (mesaj metnini göstermek için).
    Element: form1:tableExIlacMesajListesi:{index}:text19

    Args:
        bot: BotanikBot instance
        mesaj_index: Mesaj indexi

    Returns:
        bool: Başarılı mı
    """
    try:
        baslik_id = f"form1:tableExIlacMesajListesi:{mesaj_index}:text19"

        element = bot.find_element_safe(baslik_id, timeout=2)
        if element:
            element.click()
            time.sleep(0.3)
            logger.debug(f"Mesaj başlığı {mesaj_index} tıklandı")
            return True

        return False

    except Exception as e:
        logger.error(f"Mesaj başlığı tıklama hatası: {e}")
        return False


def rapor_butonuna_tikla(bot):
    """
    İlaç Bilgi penceresindeki Rapor butonuna tıkla.
    Hastanın raporunu açar.
    Element: f:buttonRaporGoruntule

    Returns:
        bool: Başarılı mı
    """
    try:
        buton_id = "f:buttonRaporGoruntule"

        element = bot.find_element_safe(buton_id, timeout=2)
        if element:
            element.click()
            time.sleep(1)  # Rapor penceresinin açılmasını bekle
            logger.debug("Rapor butonuna tıklandı")
            return True

        # UI Automation ile dene
        try:
            from System.Windows.Automation import AutomationElement, PropertyCondition, TreeScope
            condition = PropertyCondition(AutomationElement.NameProperty, "Rapor")
            elem = bot.root_element.FindFirst(TreeScope.Descendants, condition)
            if elem:
                from System.Windows.Automation import InvokePattern
                pattern = elem.GetCurrentPattern(InvokePattern.Pattern)
                if pattern:
                    pattern.Invoke()
                    time.sleep(1)
                    logger.debug("Rapor butonuna tıklandı (UIA)")
                    return True
        except:
            pass

        logger.warning("Rapor butonu bulunamadı")
        return False

    except Exception as e:
        logger.error(f"Rapor butonu tıklama hatası: {e}")
        return False


def ilac_bilgi_ayaktan_doz_oku(bot):
    """
    İlaç Bilgi penceresindeki Ayaktan Maks. Kul. Doz değerini oku.
    Raporlu doz ile aynı yapıda ama farklı label.

    Returns:
        dict: {'periyot': int, 'birim': str, 'carpan': int, 'doz': float} veya None
    """
    try:
        from System.Windows.Automation import AutomationElement, PropertyCondition, TreeScope

        # "Ayaktan Maks. Kul. Doz" metnini bul
        condition = PropertyCondition(AutomationElement.NameProperty, "Ayaktan Maks. Kul. Doz")
        label_elem = bot.root_element.FindFirst(TreeScope.Descendants, condition)

        if label_elem:
            from System.Windows.Automation import TreeWalker, Condition

            parent = TreeWalker.ContentViewWalker.GetParent(label_elem)
            if parent:
                children = parent.FindAll(TreeScope.Children, Condition.TrueCondition)

                doz_parts = []
                found_label = False
                for child in children:
                    name = child.Current.Name
                    if "Ayaktan Maks" in str(name):
                        found_label = True
                        continue
                    if found_label and name and name.strip() not in [':', '']:
                        doz_parts.append(name.strip())

                if len(doz_parts) >= 4:
                    try:
                        return {
                            'periyot': int(doz_parts[0]),
                            'birim': doz_parts[1],
                            'carpan': int(doz_parts[2]),
                            'doz': float(doz_parts[4].replace(',', '.')) if len(doz_parts) > 4 else float(doz_parts[3].replace(',', '.'))
                        }
                    except:
                        pass

        return None

    except Exception as e:
        logger.error(f"Ayaktan doz okuma hatası: {e}")
        return None


def ilac_satiri_recete_doz_oku(bot, satir_index):
    """
    Reçetedeki ilaç dozunu oku.
    Adet / Periyot / Doz sütunundan okur.

    Args:
        bot: BotanikBot instance
        satir_index: Satır indexi

    Returns:
        dict: {'adet': int, 'periyot': int, 'birim': str, 'carpan': int, 'doz': float} veya None
    """
    try:
        # Doz bilgisi genelde şu formatta: "1, Adet" veya edit alanlarında
        # Periyot ve doz için farklı element ID'leri var

        # Periyot edit: f:tbl1:{satir}:edit1 vb.
        # Bu yapıyı daha detaylı incelememiz gerekebilir

        # Şimdilik basit bir yaklaşım - tablodaki text'leri okuyalım
        # Normalde "( Günde 2 x 1,000 Doz...)" gibi bir metin var

        # TODO: Daha detaylı element mapping gerekebilir

        return None

    except Exception as e:
        logger.error(f"Reçete doz okuma hatası (satır {satir_index}): {e}")
        return None


def _doz_karsilastir(ayaktan_doz, raporlu_doz):
    """
    Ayaktan (reçete) dozu ile raporlu maks dozu karşılaştır.
    Reçete dozu ≤ rapor dozu olmalı.

    Args:
        ayaktan_doz: {'periyot': int, 'birim': str, 'carpan': int, 'doz': float}
        raporlu_doz: Aynı format

    Returns:
        dict: {'uygun': bool, 'aciklama': str}
    """
    try:
        if not ayaktan_doz or not raporlu_doz:
            return {'uygun': True, 'aciklama': 'Doz bilgisi eksik, karşılaştırma yapılamadı'}

        # Günlük toplam doz hesapla: carpan * doz * periyot
        ayaktan_gunluk = ayaktan_doz['carpan'] * ayaktan_doz['doz'] * ayaktan_doz['periyot']
        raporlu_gunluk = raporlu_doz['carpan'] * raporlu_doz['doz'] * raporlu_doz['periyot']

        if ayaktan_gunluk <= raporlu_gunluk:
            return {
                'uygun': True,
                'aciklama': f'Doz uygun: reçete={ayaktan_gunluk:.1f} ≤ rapor={raporlu_gunluk:.1f}'
            }
        else:
            return {
                'uygun': False,
                'aciklama': f'DOZ AŞIMI: reçete={ayaktan_gunluk:.1f} > rapor={raporlu_gunluk:.1f}'
            }

    except Exception as e:
        logger.error(f"Doz karşılaştırma hatası: {e}")
        return {'uygun': True, 'aciklama': f'Karşılaştırma hatası: {e}'}


def ilac_kontrolu_yap(bot, satir_index, session_logger=None):
    """
    Tek bir ilaç satırı için kontrol yap.

    Args:
        bot: BotanikBot instance
        satir_index: Satır indexi
        session_logger: Oturum logger

    Returns:
        dict: Kontrol sonuçları
    """
    sonuc = {
        'satir': satir_index,
        'ilac_adi': None,
        'msj': None,
        'rapor_kodu': None,
        'raporlu': False,
        'etkin_madde': None,
        'sgk_kodu': None,
        'sut_maddesi': None,
        'mesaj_basligi': None,
        'mesaj_metni': None,
        'raporlu_doz': None,
        'ayaktan_doz': None,
        'doz_uygun': None,
        'doz_aciklama': None,
        'sorun_var': False,
        'sorun_aciklama': None
    }

    try:
        # 1. İlaç adını oku
        ilac_adi = ilac_satiri_ilac_adi_oku(bot, satir_index)
        sonuc['ilac_adi'] = ilac_adi

        # 2. Msj sütununu oku
        msj = ilac_satiri_msj_oku(bot, satir_index)
        sonuc['msj'] = msj

        # 3. Rapor kodunu oku
        rapor_kodu = ilac_satiri_rapor_kodu_oku(bot, satir_index)
        sonuc['rapor_kodu'] = rapor_kodu
        sonuc['raporlu'] = bool(rapor_kodu)

        # 4. Raporsuz VE msj="yok" ise atla
        if not sonuc['raporlu'] and msj != "var":
            logger.debug(f"Satır {satir_index}: Raporsuz ve Msj≠var, atlanıyor ({ilac_adi})")
            return sonuc

        # 5. Detaylı kontrol (raporlu VEYA msj="var")
        logger.info(f"🔍 Satır {satir_index}: {ilac_adi} | Rapor:{rapor_kodu} Msj:{msj}")

        # Checkbox'ı seç
        if not ilac_satiri_checkbox_sec(bot, satir_index, sec=True):
            logger.warning(f"Satır {satir_index} checkbox seçilemedi")
            return sonuc

        time.sleep(0.2)

        # İlaç Bilgi butonuna tıkla
        if not ilac_bilgi_butonuna_tikla(bot):
            logger.warning(f"İlaç Bilgi butonu tıklanamadı")
            ilac_satiri_checkbox_sec(bot, satir_index, sec=False)
            return sonuc

        time.sleep(0.5)

        try:
            # 5a. Etkin madde oku
            etkin_madde = ilac_bilgi_etkin_madde_oku(bot)
            sonuc['etkin_madde'] = etkin_madde
            if etkin_madde:
                logger.info(f"  Etkin madde: {etkin_madde}")

            # 5b. SGK kodu oku
            sgk_kodu = ilac_bilgi_sgk_kodu_oku(bot)
            sonuc['sgk_kodu'] = sgk_kodu

            # 5c. Mesaj başlığını oku (SUT maddesi)
            mesaj_basligi = ilac_mesaj_basligi_oku(bot, mesaj_index=0)
            if mesaj_basligi:
                sonuc['mesaj_basligi'] = mesaj_basligi['baslik']
                sonuc['sut_maddesi'] = mesaj_basligi.get('sut_maddesi')
                logger.info(f"  SUT maddesi: {sonuc['sut_maddesi']}")

                # Mesaj başlığına tıkla (mesaj metnini yüklemek için)
                ilac_mesaj_basligina_tikla(bot, mesaj_index=0)
                time.sleep(0.3)

            # 5d. Mesaj metnini oku
            mesaj = ilac_bilgi_penceresi_mesaj_oku(bot)
            sonuc['mesaj_metni'] = mesaj
            if mesaj:
                logger.info(f"  Mesaj: {mesaj[:100]}...")

            # 5e. Raporlu ilaç ise doz kontrolü
            if sonuc['raporlu']:
                raporlu_doz = ilac_bilgi_penceresi_raporlu_doz_oku(bot)
                sonuc['raporlu_doz'] = raporlu_doz
                if raporlu_doz:
                    logger.info(f"  Raporlu maks doz: {raporlu_doz['periyot']} {raporlu_doz['birim']} {raporlu_doz['carpan']} x {raporlu_doz['doz']}")

                # 5f. Ayaktan maks doz oku (reçete dozu yerine)
                ayaktan_doz = ilac_bilgi_ayaktan_doz_oku(bot)
                sonuc['ayaktan_doz'] = ayaktan_doz
                if ayaktan_doz:
                    logger.info(f"  Ayaktan maks doz: {ayaktan_doz['periyot']} {ayaktan_doz['birim']} {ayaktan_doz['carpan']} x {ayaktan_doz['doz']}")

                # 5g. Doz karşılaştır
                if raporlu_doz and ayaktan_doz:
                    doz_sonuc = _doz_karsilastir(ayaktan_doz, raporlu_doz)
                    sonuc['doz_uygun'] = doz_sonuc['uygun']
                    sonuc['doz_aciklama'] = doz_sonuc['aciklama']

                    if not doz_sonuc['uygun']:
                        sonuc['sorun_var'] = True
                        sonuc['sorun_aciklama'] = doz_sonuc['aciklama']
                        logger.warning(f"  ⚠️ {doz_sonuc['aciklama']}")
                    else:
                        logger.info(f"  ✓ {doz_sonuc['aciklama']}")

            # 5h. SUT kontrolü yap
            try:
                from recete_kontrol.sut_kontrolleri import sut_kontrol_yap
                sut_sonuc = sut_kontrol_yap(sonuc)
                if sut_sonuc:
                    sonuc['sut_kategori'] = sut_sonuc['kategori']
                    sonuc['sut_kategori_adi'] = sut_sonuc['kategori_adi']
                    sonuc['sut_kontrol_raporu'] = {
                        'sonuc': sut_sonuc['kontrol_raporu'].sonuc.value,
                        'mesaj': sut_sonuc['kontrol_raporu'].mesaj,
                        'uyari': sut_sonuc['kontrol_raporu'].uyari,
                        'detaylar': sut_sonuc['kontrol_raporu'].detaylar
                    }
            except Exception as e:
                logger.warning(f"  SUT kontrol hatası: {e}")

        finally:
            # Pencereyi kapat ve checkbox'ı kaldır
            ilac_bilgi_penceresi_kapat(bot)
            time.sleep(0.2)
            ilac_satiri_checkbox_sec(bot, satir_index, sec=False)

        return sonuc

    except Exception as e:
        logger.error(f"İlaç kontrolü hatası (satır {satir_index}): {e}")
        sonuc['sorun_var'] = True
        sonuc['sorun_aciklama'] = str(e)
        return sonuc


def tum_ilaclari_kontrol_et(bot, session_logger=None, stop_check=None):
    """
    Reçetedeki tüm ilaçları kontrol et.

    Args:
        bot: BotanikBot instance
        session_logger: Oturum logger
        stop_check: Durdurma kontrolü fonksiyonu

    Returns:
        dict: {
            'toplam_ilac': int,
            'kontrol_edilen': int,
            'msj_var_sayisi': int,
            'raporlu_sayisi': int,
            'sorunlu_sayisi': int,
            'detaylar': list[dict]
        }
    """
    rapor = {
        'toplam_ilac': 0,
        'kontrol_edilen': 0,
        'msj_var_sayisi': 0,
        'raporlu_sayisi': 0,
        'sorunlu_sayisi': 0,
        'doz_asimi_sayisi': 0,
        'detaylar': []
    }

    def should_stop():
        return stop_check and stop_check()

    try:
        # 1. Satır sayısını tespit et
        satir_sayisi = ilac_tablosu_satir_sayisi_oku(bot)
        rapor['toplam_ilac'] = satir_sayisi

        if satir_sayisi == 0:
            logger.warning("İlaç tablosunda satır bulunamadı")
            return rapor

        logger.info(f"📋 İlaç tablosunda {satir_sayisi} satır bulundu")

        # 2. Her satırı kontrol et
        for i in range(satir_sayisi):
            if should_stop():
                logger.info("Kontrol durduruldu")
                break

            sonuc = ilac_kontrolu_yap(bot, i, session_logger)
            rapor['detaylar'].append(sonuc)
            rapor['kontrol_edilen'] += 1

            if sonuc['msj'] == "var":
                rapor['msj_var_sayisi'] += 1

            if sonuc['raporlu']:
                rapor['raporlu_sayisi'] += 1

            if sonuc['sorun_var']:
                rapor['sorunlu_sayisi'] += 1

            if sonuc.get('doz_uygun') is False:
                rapor['doz_asimi_sayisi'] += 1

        # 3. Özet log
        logger.info(f"""
═══════════════════════════════════════════════════
İLAÇ KONTROL RAPORU
═══════════════════════════════════════════════════
Toplam İlaç     : {rapor['toplam_ilac']}
Kontrol Edilen  : {rapor['kontrol_edilen']}
Msj=var Sayısı  : {rapor['msj_var_sayisi']}
Raporlu İlaç    : {rapor['raporlu_sayisi']}
Doz Aşımı       : {rapor['doz_asimi_sayisi']}
Sorunlu         : {rapor['sorunlu_sayisi']}
═══════════════════════════════════════════════════
""")

        return rapor

    except Exception as e:
        logger.error(f"Tüm ilaçları kontrol hatası: {e}")
        return rapor


if __name__ == "__main__":
    main()
