#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Botanik Bot GUI - Reçete Grup Takip Sistemi
A: Raporlu, B: Normal, C: İş Yeri
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import json
from pathlib import Path
import logging
import winsound
from datetime import datetime
from botanik_bot import (
    BotanikBot,
    RaporTakip,
    tek_recete_isle,
    popup_kontrol_ve_kapat,
    recete_kaydi_bulunamadi_mi,
    medula_taskkill,
    medula_ac_ve_giris_yap,
    SistemselHataException,
    medula_yeniden_baslat_ve_giris_yap,
    sonraki_gruba_gec_islemi
)
from timing_settings import get_timing_settings
from database import get_database
from session_logger import SessionLogger
from medula_settings import get_medula_settings

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


class GrupDurumu:
    """Grup durumlarını JSON dosyasında sakla"""

    def __init__(self, dosya_yolu="grup_durumlari.json"):
        # Dosyayı script'in bulunduğu dizine kaydet (database.py gibi)
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.dosya_yolu = Path(script_dir) / dosya_yolu
        self.veriler = self.yukle()

    def yukle(self):
        """JSON dosyasından verileri yükle"""
        guncellendi = False
        if self.dosya_yolu.exists():
            try:
                with open(self.dosya_yolu, 'r', encoding='utf-8') as f:
                    veriler = json.load(f)

                    # Eski dosyaları yeni formata güncelle (backwards compatibility)
                    for grup in ["A", "B", "C"]:
                        if grup in veriler:
                            # Eksik alanları ekle
                            if "toplam_takipli_recete" not in veriler[grup]:
                                veriler[grup]["toplam_takipli_recete"] = 0
                                guncellendi = True
                            if "bitti_tarihi" not in veriler[grup]:
                                veriler[grup]["bitti_tarihi"] = None
                                guncellendi = True
                            if "bitti_recete_sayisi" not in veriler[grup]:
                                veriler[grup]["bitti_recete_sayisi"] = None
                                guncellendi = True

                    # aktif_mod alanı yoksa ekle
                    if "aktif_mod" not in veriler:
                        veriler["aktif_mod"] = None
                        guncellendi = True

                    # Eğer güncelleme yapıldıysa dosyaya kaydet
                    if guncellendi:
                        try:
                            temp_dosya = self.dosya_yolu.with_suffix('.tmp')
                            with open(temp_dosya, 'w', encoding='utf-8') as f:
                                json.dump(veriler, f, indent=2, ensure_ascii=False)
                            import shutil
                            shutil.move(str(temp_dosya), str(self.dosya_yolu))
                        except:
                            pass

                    return veriler
            except:
                pass

        # Varsayılan yapı
        return {
            "aktif_mod": None,  # "tumunu_kontrol", "A", "B", "C" veya None
            "A": {
                "son_recete": "",
                "toplam_recete": 0,
                "toplam_takip": 0,
                "toplam_takipli_recete": 0,
                "toplam_sure": 0.0,
                "bitti_tarihi": None,
                "bitti_recete_sayisi": None
            },
            "B": {
                "son_recete": "",
                "toplam_recete": 0,
                "toplam_takip": 0,
                "toplam_takipli_recete": 0,
                "toplam_sure": 0.0,
                "bitti_tarihi": None,
                "bitti_recete_sayisi": None
            },
            "C": {
                "son_recete": "",
                "toplam_recete": 0,
                "toplam_takip": 0,
                "toplam_takipli_recete": 0,
                "toplam_sure": 0.0,
                "bitti_tarihi": None,
                "bitti_recete_sayisi": None
            }
        }

    def kaydet(self):
        """Verileri JSON dosyasına kaydet"""
        try:
            # Dizin yoksa oluştur
            self.dosya_yolu.parent.mkdir(parents=True, exist_ok=True)

            # Dosya açıksa veya kullanımdaysa, geçici dosya kullan
            temp_dosya = self.dosya_yolu.with_suffix('.tmp')

            with open(temp_dosya, 'w', encoding='utf-8') as f:
                json.dump(self.veriler, f, indent=2, ensure_ascii=False)

            # Geçici dosyayı asıl dosyanın üzerine taşı
            import shutil
            shutil.move(str(temp_dosya), str(self.dosya_yolu))

        except PermissionError:
            # İzin hatası - sessizce devam et (critical değil)
            logger.debug(f"Grup durumları kaydetme izni yok (devam ediliyor)")
        except Exception as e:
            # Diğer hatalar
            logger.warning(f"Grup durumları kaydedilemedi: {e}")

    def son_recete_al(self, grup):
        """Grubun son reçete numarasını al"""
        return self.veriler.get(grup, {}).get("son_recete", "")

    def son_recete_guncelle(self, grup, recete_no):
        """Grubun son reçete numarasını güncelle"""
        if grup in self.veriler:
            self.veriler[grup]["son_recete"] = recete_no
            self.kaydet()

    def istatistik_guncelle(self, grup, recete_sayisi=0, takip_sayisi=0, takipli_recete_sayisi=0, sure=0.0):
        """Grup istatistiklerini güncelle"""
        if grup in self.veriler:
            # Eksik alanları güvenli şekilde handle et
            if "toplam_takipli_recete" not in self.veriler[grup]:
                self.veriler[grup]["toplam_takipli_recete"] = 0

            self.veriler[grup]["toplam_recete"] += recete_sayisi
            self.veriler[grup]["toplam_takip"] += takip_sayisi
            self.veriler[grup]["toplam_takipli_recete"] += takipli_recete_sayisi
            self.veriler[grup]["toplam_sure"] += sure
            self.kaydet()

    def istatistik_al(self, grup):
        """Grup istatistiklerini al"""
        return self.veriler.get(grup, {})

    def grup_sifirla(self, grup):
        """Grubu sıfırla (ay sonu) - BİTTİ bilgisini de temizler"""
        if grup in self.veriler:
            self.veriler[grup] = {
                "son_recete": "",
                "toplam_recete": 0,
                "toplam_takip": 0,
                "toplam_takipli_recete": 0,
                "toplam_sure": 0.0,
                "bitti_tarihi": None,
                "bitti_recete_sayisi": None
            }
            self.kaydet()

    def aktif_mod_ayarla(self, mod):
        """Aktif modu ayarla: "tumunu_kontrol", "A", "B", "C" veya None"""
        self.veriler["aktif_mod"] = mod
        self.kaydet()

    def aktif_mod_al(self):
        """Aktif modu al"""
        return self.veriler.get("aktif_mod", None)

    def bitti_bilgisi_ayarla(self, grup, tarih, recete_sayisi):
        """Grup bitiş bilgisini kaydet"""
        if grup in self.veriler:
            self.veriler[grup]["bitti_tarihi"] = tarih
            self.veriler[grup]["bitti_recete_sayisi"] = recete_sayisi
            self.kaydet()

    def bitti_bilgisi_al(self, grup):
        """Grup bitiş bilgisini al - (tarih, recete_sayisi) tuple döner"""
        if grup in self.veriler:
            tarih = self.veriler[grup].get("bitti_tarihi", None)
            sayisi = self.veriler[grup].get("bitti_recete_sayisi", None)
            return (tarih, sayisi)
        return (None, None)

    def bitti_bilgisi_temizle(self, grup):
        """Grup bitiş bilgisini temizle (yeni işlem başladığında)"""
        if grup in self.veriler:
            self.veriler[grup]["bitti_tarihi"] = None
            self.veriler[grup]["bitti_recete_sayisi"] = None
            self.kaydet()


class BotanikGUI:
    """Botanik Bot GUI"""

    def __init__(self, root):
        self.root = root
        self.root.title("Botanik Bot v3")

        # Ekran boyutlarını al
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Ekranı bölümle: Sol 4/5 (MEDULA), Sağ 1/5 (GUI + Konsol)
        # Sağdaki 1/5'i dikey olarak: Üst 2/3 (GUI), Alt 1/3 (Konsol)

        # GUI için boyutlar (ekranın sağ üst 1/5'i, dikey olarak 2/3)
        self.gui_width = int(screen_width * 1/5)
        self.gui_height = int(screen_height * 2/3)

        # GUI konumu (sağ üst köşe)
        gui_x = int(screen_width * 4/5)  # Sağdaki 1/5'in başlangıcı
        gui_y = 0  # Üst kenara bitişik

        self.root.geometry(f"{self.gui_width}x{self.gui_height}+{gui_x}+{gui_y}")
        self.root.resizable(False, False)

        # Ekran boyutlarını sakla (diğer pencereler için)
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Konsol penceresini arka plana gönder (küçültülmüş)
        self.konsolu_arkaya_gonder()

        # Renkler
        self.bg_color = '#2E7D32'  # Koyu yeşil
        self.root.configure(bg=self.bg_color)

        # Grup durumları
        self.grup_durumu = GrupDurumu()

        # Rapor takip (CSV)
        self.rapor_takip = RaporTakip()
        self.son_kopyalama_tarihi = None
        self.son_kopyalama_button = None

        # Bot
        self.bot = None
        self.automation_thread = None
        self.is_running = False
        self.stop_requested = False

        # Seçili grup
        self.secili_grup = tk.StringVar(value="")
        self.aktif_grup = None  # Şu anda çalışan grup (A/B/C)

        # Tümünü Kontrol Et (A→B→C) değişkenleri
        self.tumu_kontrol_aktif = False  # Tümünü kontrol modu aktif mi?
        self.tumu_kontrol_grup_sirasi = ["A", "B", "C"]  # Sıralı gruplar
        self.tumu_kontrol_mevcut_index = 0  # Şu anda hangi grup işleniyor (index)

        # Oturum istatistikleri
        self.oturum_recete = 0
        self.oturum_takip = 0
        self.oturum_takipli_recete = 0  # Takipli ilaç bulunan reçete sayısı
        self.oturum_baslangic = None
        self.oturum_sure_toplam = 0.0  # Toplam çalışma süresi (durdur/başlat arası)
        self.oturum_duraklatildi = False
        self.son_recete_sureleri = []  # Son 5 reçetenin süreleri (saniye)

        # Yeniden başlatma sayacı
        self.yeniden_baslatma_sayaci = 0
        self.taskkill_sayaci = 0  # Taskkill sayacı
        self.ardisik_basarisiz_deneme = 0  # Ardışık başarısız yeniden başlatma denemesi (max 3)

        # Aşama geçmişi
        self.log_gecmisi = []

        # Zamanlama ayarları
        self.timing = get_timing_settings()
        self.ayar_entry_widgets = {}  # Ayar entry widget'larını sakla
        self.ayar_kaydet_timer = None  # Debounce timer

        # MEDULA ayarları
        self.medula_settings = get_medula_settings()

        # Database ve oturum tracking
        self.database = get_database()
        self.aktif_oturum_id = None  # Aktif oturum ID
        self.session_logger = None  # Oturum log dosyası

        # CAPTCHA modu kaldırıldı - Botanik program kendi çözüyor

        self.create_widgets()
        self.load_grup_verileri()

        # Başlangıç logu
        self.log_ekle("Beklemede...")

        # MEDULA'yı başlangıçta sol %80'e yerleştir
        self.root.after(800, self.medula_pencere_ayarla)

        # Wizard kontrolü (ayarlar eksikse göster)
        self.root.after(1000, self.wizard_kontrol)

    def medula_pencere_ayarla(self):
        """MEDULA penceresini başlangıçta sol 4/5'e yerleştir"""
        try:
            import ctypes
            import win32gui
            import win32con
            from pywinauto import Desktop

            # MEDULA penceresini bul
            desktop = Desktop(backend="uia")
            windows = desktop.windows()

            medula_hwnd = None
            for window in windows:
                try:
                    if "MEDULA" in window.window_text():
                        medula_hwnd = window.handle
                        logger.info(f"MEDULA penceresi bulundu: {window.window_text()}")
                        break
                except:
                    pass

            if medula_hwnd is None:
                logger.debug("MEDULA penceresi bulunamadı (henüz açılmamış olabilir)")
                return

            # Ekran çözünürlüğünü al
            user32 = ctypes.windll.user32
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)

            # Sol 4/5 boyutlandırma (sağdaki 1/5 Botanik için ayrıldı)
            medula_x = 0
            medula_y = 0
            medula_width = int(screen_width * 4/5)
            medula_height = screen_height - 40  # Taskbar için boşluk

            # Mevcut pozisyonu logla
            try:
                eski_rect = win32gui.GetWindowRect(medula_hwnd)
                logger.info(f"MEDULA eski pozisyon: x={eski_rect[0]}, y={eski_rect[1]}, w={eski_rect[2]-eski_rect[0]}, h={eski_rect[3]-eski_rect[1]}")
            except:
                pass

            # Minimize veya Maximize ise restore et
            try:
                placement = win32gui.GetWindowPlacement(medula_hwnd)
                current_state = placement[1]

                # SW_SHOWMINIMIZED=2, SW_SHOWMAXIMIZED=3
                # Minimize veya maximize ise restore et
                if current_state == win32con.SW_SHOWMINIMIZED or current_state == win32con.SW_SHOWMAXIMIZED:
                    logger.info(f"MEDULA durumu: {'minimize' if current_state == 2 else 'maximize'}, restore ediliyor...")
                    win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                    time.sleep(0.5)  # Restore için bekle

                # Eğer -32000 koordinatlarında ise (minimize durumu), zorla restore et
                eski_rect = win32gui.GetWindowRect(medula_hwnd)
                if eski_rect[0] < -10000 or eski_rect[1] < -10000:
                    logger.info("MEDULA minimize koordinatlarda, zorla restore ediliyor...")
                    win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                    time.sleep(0.5)
                    # Pencereyi görünür yap
                    win32gui.ShowWindow(medula_hwnd, win32con.SW_SHOW)
                    time.sleep(0.3)
            except Exception as e:
                logger.warning(f"MEDULA restore işlemi hatası: {e}")
                # Yine de restore dene
                try:
                    win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                    time.sleep(0.5)
                except:
                    pass

            # Önce SetWindowPos ile yerleştir
            flags = win32con.SWP_SHOWWINDOW
            win32gui.SetWindowPos(
                medula_hwnd,
                win32con.HWND_TOP,
                medula_x, medula_y,
                medula_width, medula_height,
                flags
            )
            time.sleep(0.05)

            # Sonra MoveWindow ile kesinleştir
            win32gui.MoveWindow(medula_hwnd, medula_x, medula_y, medula_width, medula_height, True)
            time.sleep(0.05)

            # Yeni pozisyonu kontrol et ve logla
            try:
                yeni_rect = win32gui.GetWindowRect(medula_hwnd)
                gercek_x = yeni_rect[0]
                gercek_y = yeni_rect[1]
                gercek_w = yeni_rect[2] - yeni_rect[0]
                gercek_h = yeni_rect[3] - yeni_rect[1]

                logger.info(f"MEDULA yeni pozisyon: x={gercek_x}, y={gercek_y}, w={gercek_w}, h={gercek_h}")

                # Gerçekten yerleşti mi kontrol et
                if gercek_x <= 10 and gercek_w >= medula_width - 50:
                    logger.info(f"✓ MEDULA sol 4/5'e yerleştirildi")
                else:
                    logger.warning(f"⚠ MEDULA tam yerleşmedi, tekrar deneniyor...")
                    win32gui.MoveWindow(medula_hwnd, medula_x, medula_y, medula_width, medula_height, True)
            except Exception as e:
                logger.warning(f"MEDULA pozisyon kontrolü yapılamadı: {e}")

        except Exception as e:
            logger.debug(f"MEDULA pencere ayarlanamadı: {e}")

    def wizard_kontrol(self):
        """MEDULA ayarlarını kontrol et, eksikse wizard'ı göster"""
        try:
            # Ayarları kontrol et
            # Ayarların dolu olup olmadığını kontrol et
            if not self.medula_settings.kullanici_bilgileri_dolu_mu():
                logger.info("MEDULA ayarları eksik, wizard açılıyor...")

                from medula_wizard import wizard_goster

                # Wizard'ı göster
                sonuc = wizard_goster(self.root, self.medula_settings)

                if sonuc:
                    logger.info("✓ Wizard tamamlandı, ayarlar kaydedildi")
                    self.log_ekle("✓ MEDULA ayarları yapılandırıldı")
                else:
                    logger.warning("⚠ Wizard iptal edildi")
                    self.log_ekle("⚠ MEDULA ayarları yapılandırılmadı")
            else:
                logger.info("✓ MEDULA ayarları mevcut, wizard atlanıyor")

        except Exception as e:
            logger.error(f"Wizard kontrol hatası: {e}")

    def konsolu_arkaya_gonder(self):
        """Konsol penceresini GUI'nin arkasına gönder"""
        try:
            import ctypes
            import sys

            # Windows için konsol penceresini bul
            if sys.platform == "win32":
                # Daha uzun gecikme - GUI tamamen yüklendikten ve MEDULA yerleştikten sonra
                self.root.after(1200, self._konsolu_konumlandir)
        except Exception as e:
            logger.warning(f"Konsol konumlandırılamadı: {e}")

    def _konsolu_konumlandir(self):
        """Konsolu konumlandır (delayed)"""
        try:
            import ctypes
            import win32gui
            import win32con

            hwnd = ctypes.windll.kernel32.GetConsoleWindow()

            if hwnd:
                # Konsolu sağ alt 1/3'e yerleştir
                # Sağdaki 1/5'lik alanın alt 1/3'ü
                console_x = int(self.screen_width * 4/5)  # Sağdaki 1/5'in başlangıcı
                console_y = int(self.screen_height * 2/3)  # Dikeyin 2/3'ünden başla
                console_width = int(self.screen_width * 1/5)  # Genişlik: ekranın 1/5'i
                console_height = int(self.screen_height * 1/3)  # Yükseklik: ekranın 1/3'ü

                logger.info(f"Konsol yerleştirilecek: x={console_x}, y={console_y}, w={console_width}, h={console_height}")

                # Mevcut pozisyonu logla
                try:
                    eski_rect = win32gui.GetWindowRect(hwnd)
                    logger.info(f"Konsol eski pozisyon: x={eski_rect[0]}, y={eski_rect[1]}, w={eski_rect[2]-eski_rect[0]}, h={eski_rect[3]-eski_rect[1]}")
                except:
                    pass

                # Önce konsolu göster (minimize ise)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)  # Console'un restore olması için bekle

                # İlk olarak SetWindowPos ile yerleştir ve en üste getir
                flags = win32con.SWP_SHOWWINDOW
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOP,
                    console_x, console_y,
                    console_width, console_height,
                    flags
                )
                time.sleep(0.05)

                # Sonra MoveWindow ile kesin yerleştir
                win32gui.MoveWindow(hwnd, console_x, console_y, console_width, console_height, True)
                time.sleep(0.1)

                # Yeni pozisyonu kontrol et ve logla
                try:
                    yeni_rect = win32gui.GetWindowRect(hwnd)
                    gercek_x = yeni_rect[0]
                    gercek_y = yeni_rect[1]
                    gercek_w = yeni_rect[2] - yeni_rect[0]
                    gercek_h = yeni_rect[3] - yeni_rect[1]

                    logger.info(f"Konsol yeni pozisyon: x={gercek_x}, y={gercek_y}, w={gercek_w}, h={gercek_h}")

                    # Gerçekten sağa yerleşti mi kontrol et
                    if gercek_x < self.screen_width / 2:
                        logger.warning(f"⚠ Konsol sağa gitmedi, tekrar deneniyor...")
                        # Birkaç kez daha dene
                        for i in range(3):
                            win32gui.SetWindowPos(
                                hwnd,
                                win32con.HWND_TOP,
                                console_x, console_y,
                                console_width, console_height,
                                win32con.SWP_SHOWWINDOW
                            )
                            time.sleep(0.05)
                            win32gui.MoveWindow(hwnd, console_x, console_y, console_width, console_height, True)
                            time.sleep(0.1)

                            # Son pozisyonu kontrol et
                            son_rect = win32gui.GetWindowRect(hwnd)
                            if son_rect[0] >= self.screen_width / 2:
                                logger.info(f"✓ Konsol {i+1}. denemede yerleşti")
                                break

                        # Son durum
                        final_rect = win32gui.GetWindowRect(hwnd)
                        logger.info(f"Konsol son pozisyon: x={final_rect[0]}, y={final_rect[1]}")
                    else:
                        logger.info(f"✓ Konsol sağ alt 1/3'e yerleştirildi")
                except Exception as e:
                    logger.warning(f"Konsol pozisyon kontrolü yapılamadı: {e}")

                # GUI'yi öne al
                self.root.lift()
                self.root.focus_force()

            else:
                logger.debug("Konsol penceresi bulunamadı (pythonw ile çalışıyor olabilir)")
        except Exception as e:
            logger.error(f"Konsol konumlandırma hatası: {e}", exc_info=True)

    def tum_pencereleri_yerlestir(self):
        """
        Tüm pencereleri yerleştir:
        - MEDULA: Sol 4/5
        - GUI: Sağ üst 1/5, üstten 2/3
        - Konsol: Sağ alt 1/5, alttan 1/3
        """
        try:
            import win32gui
            import win32con
            import ctypes

            logger.info("🖼 Tüm pencereler yerleştiriliyor...")

            # 1. MEDULA penceresini yerleştir (Sol 4/5)
            if self.bot and self.bot.main_window:
                try:
                    medula_hwnd = self.bot.main_window.handle

                    medula_x = 0
                    medula_y = 0
                    medula_width = int(self.screen_width * 4/5)
                    medula_height = self.screen_height

                    logger.info(f"MEDULA yerleştirilecek: x={medula_x}, y={medula_y}, w={medula_width}, h={medula_height}")

                    # Restore (minimize ise)
                    win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                    time.sleep(0.1)

                    # Yerleştir
                    win32gui.SetWindowPos(
                        medula_hwnd,
                        win32con.HWND_TOP,
                        medula_x, medula_y,
                        medula_width, medula_height,
                        win32con.SWP_SHOWWINDOW
                    )
                    time.sleep(0.05)
                    win32gui.MoveWindow(medula_hwnd, medula_x, medula_y, medula_width, medula_height, True)

                    logger.info("✓ MEDULA sol 4/5'e yerleştirildi")
                except Exception as e:
                    logger.warning(f"MEDULA yerleştirilemedi: {e}")

            # 2. GUI penceresini yerleştir (Sağ üst 1/5, üstten 2/3)
            try:
                gui_x = int(self.screen_width * 4/5)
                gui_y = 0
                gui_width = int(self.screen_width * 1/5)
                gui_height = int(self.screen_height * 2/3)

                logger.info(f"GUI yerleştirilecek: x={gui_x}, y={gui_y}, w={gui_width}, h={gui_height}")

                self.root.geometry(f"{gui_width}x{gui_height}+{gui_x}+{gui_y}")
                self.root.update()

                logger.info("✓ GUI sağ üst 1/5'e yerleştirildi")
            except Exception as e:
                logger.warning(f"GUI yerleştirilemedi: {e}")

            # 3. Konsol penceresini yerleştir (Sağ alt 1/5, alttan 1/3)
            try:
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()

                if hwnd:
                    console_x = int(self.screen_width * 4/5)
                    console_y = int(self.screen_height * 2/3)
                    console_width = int(self.screen_width * 1/5)
                    console_height = int(self.screen_height * 1/3)

                    logger.info(f"Konsol yerleştirilecek: x={console_x}, y={console_y}, w={console_width}, h={console_height}")
                    logger.info(f"Ekran boyutu: {self.screen_width}x{self.screen_height}")

                    # Önce normal göster
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
                    time.sleep(0.3)

                    # Maximize'dan çık
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    time.sleep(0.3)

                    # 5 kez ısrarla dene - konsol inatçı olabiliyor
                    for deneme in range(5):
                        logger.info(f"Konsol yerleştirme deneme {deneme+1}/5...")

                        # 1. Yöntem: SetWindowPos
                        try:
                            win32gui.SetWindowPos(
                                hwnd,
                                win32con.HWND_TOP,
                                console_x, console_y,
                                console_width, console_height,
                                win32con.SWP_SHOWWINDOW | win32con.SWP_NOZORDER
                            )
                        except Exception as e:
                            logger.debug(f"SetWindowPos hatası: {e}")

                        time.sleep(0.2)

                        # 2. Yöntem: MoveWindow (daha güçlü)
                        try:
                            win32gui.MoveWindow(hwnd, console_x, console_y, console_width, console_height, True)
                        except Exception as e:
                            logger.debug(f"MoveWindow hatası: {e}")

                        time.sleep(0.3)

                        # Gerçek pozisyonu kontrol et
                        try:
                            rect = win32gui.GetWindowRect(hwnd)
                            gercek_x = rect[0]
                            gercek_y = rect[1]
                            gercek_w = rect[2] - rect[0]
                            gercek_h = rect[3] - rect[1]

                            logger.info(f"  → Gerçek pozisyon: x={gercek_x}, y={gercek_y}, w={gercek_w}, h={gercek_h}")

                            # Doğru yere yerleşti mi? (20 piksel tolerans)
                            x_dogru = abs(gercek_x - console_x) < 20
                            y_dogru = abs(gercek_y - console_y) < 20

                            if x_dogru and y_dogru:
                                logger.info(f"✓ Konsol sağ alt köşeye yerleştirildi ({deneme+1}. denemede)")
                                break
                            else:
                                logger.warning(f"  ✗ Henüz yerleşmedi (x fark: {gercek_x - console_x}, y fark: {gercek_y - console_y})")
                        except Exception as e:
                            logger.debug(f"Pozisyon kontrolü hatası: {e}")

                    # Son kontrol
                    try:
                        final_rect = win32gui.GetWindowRect(hwnd)
                        logger.info(f"Konsol son pozisyon: x={final_rect[0]}, y={final_rect[1]}, w={final_rect[2]-final_rect[0]}, h={final_rect[3]-final_rect[1]}")
                    except:
                        pass

                    logger.info("✓ Konsol yerleştirme tamamlandı")
                else:
                    logger.debug("Konsol penceresi bulunamadı")
            except Exception as e:
                logger.warning(f"Konsol yerleştirilemedi: {e}")
                import traceback
                traceback.print_exc()

            # GUI'yi öne al
            self.root.lift()
            self.root.focus_force()

            logger.info("✅ Tüm pencereler yerleştirildi")

        except Exception as e:
            logger.error(f"Pencere yerleştirme hatası: {e}", exc_info=True)

    def create_widgets(self):
        """Arayüzü oluştur"""
        # Ana container
        main_container = tk.Frame(self.root, bg=self.bg_color)
        main_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Başlık
        title_label = tk.Label(
            main_container,
            text="Botanik Bot v3",
            font=("Arial", 12, "bold"),
            bg=self.bg_color,
            fg="white"
        )
        title_label.pack(pady=(5, 5))

        # Sekmeler oluştur
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill="both", expand=True)

        # Ana sekme
        ana_sekme = tk.Frame(notebook, bg=self.bg_color)
        notebook.add(ana_sekme, text="  Ana  ")

        # Ayarlar sekmesi
        ayarlar_sekme = tk.Frame(notebook, bg='#E8F5E9')
        notebook.add(ayarlar_sekme, text="  ⚙ Ayarlar  ")

        # Ana sekme içeriği
        self.create_main_tab(ana_sekme)

        # Ayarlar sekmesi içeriği
        self.create_settings_tab(ayarlar_sekme)

    def create_main_tab(self, parent):
        """Ana sekme içeriğini oluştur"""
        main_frame = tk.Frame(parent, bg=self.bg_color, padx=5, pady=5)
        main_frame.pack(fill="both", expand=True)

        subtitle_label = tk.Label(
            main_frame,
            text="Grup seçin ve BAŞLAT'a basın",
            font=("Arial", 8),
            bg=self.bg_color,
            fg="white"
        )
        subtitle_label.pack(pady=(0, 5))

        # Gruplar frame
        groups_frame = tk.Frame(main_frame, bg=self.bg_color)
        groups_frame.pack(fill="x", pady=(0, 10))

        # 3 Grup (A, B, C)
        grup_isimleri = {
            "A": "Raporlu",
            "B": "Normal",
            "C": "İş Yeri"
        }

        self.grup_labels = {}
        self.grup_buttons = {}
        self.grup_x_buttons = {}
        self.grup_stat_labels = {}  # Aylık istatistik labelları
        self.grup_bitti_labels = {}  # ✅ BİTTİ bilgi labelları
        self.grup_frames = {}  # Grup frame'leri (renk değiştirmek için)

        for grup in ["A", "B", "C"]:
            # Grup container
            grup_outer = tk.Frame(groups_frame, bg=self.bg_color)
            grup_outer.pack(fill="x", pady=3)

            # Üst kısım - tıklanabilir
            grup_frame = tk.Frame(grup_outer, bg="#E8F5E9", relief="raised", bd=2, cursor="hand2")
            grup_frame.pack(fill="x")
            grup_frame.bind("<Button-1>", lambda e, g=grup: self.grup_secildi_click(g))

            # Frame'i kaydet (renk değiştirmek için)
            self.grup_frames[grup] = {
                'main': grup_frame,
                'widgets': []  # Alt widget'ları da saklayacağız
            }

            # Sol: Radio button + Grup adı
            left_frame = tk.Frame(grup_frame, bg="#E8F5E9")
            self.grup_frames[grup]['widgets'].append(left_frame)
            left_frame.pack(side="left", fill="y", padx=5, pady=5)
            left_frame.bind("<Button-1>", lambda e, g=grup: self.grup_secildi_click(g))

            radio = tk.Radiobutton(
                left_frame,
                text=f"{grup} ({grup_isimleri[grup]})",
                variable=self.secili_grup,
                value=grup,
                bg="#E8F5E9",
                fg="#1B5E20",
                font=("Arial", 9, "bold"),
                selectcolor="#81C784",
                command=lambda g=grup: self.grup_secildi(g)
            )
            radio.pack(anchor="w")
            self.grup_buttons[grup] = radio
            self.grup_frames[grup]['widgets'].append(radio)

            # Orta: Reçete numarası + X butonu container
            middle_frame = tk.Frame(grup_frame, bg="#E8F5E9")
            self.grup_frames[grup]['widgets'].append(middle_frame)
            middle_frame.pack(side="left", fill="both", expand=True, padx=5)
            middle_frame.bind("<Button-1>", lambda e, g=grup: self.grup_secildi_click(g))

            recete_label = tk.Label(
                middle_frame,
                text="—",
                font=("Arial", 10),
                bg="#E8F5E9",
                fg="#2E7D32",
                width=12,
                anchor="center"
            )
            recete_label.pack(side="left", fill="both", expand=True)
            recete_label.bind("<Button-1>", lambda e, g=grup: self.grup_secildi_click(g))
            self.grup_labels[grup] = recete_label
            self.grup_frames[grup]['widgets'].append(recete_label)

            # X butonu - reçete numarasının hemen yanında
            x_button = tk.Button(
                middle_frame,
                text="✕",
                font=("Arial", 9, "bold"),
                bg="#FFCDD2",
                fg="#C62828",
                width=2,
                height=1,
                relief="raised",
                bd=1,
                command=lambda g=grup: self.grup_sifirla(g)
            )
            x_button.pack(side="left", padx=(2, 0))
            self.grup_x_buttons[grup] = x_button

            # Alt kısım - Aylık istatistikler
            stat_label = tk.Label(
                grup_outer,
                text="Ay: Rç:0 | Takipli:0 | İlaç:0 | 0s 0ms",
                font=("Arial", 6),
                bg="#C8E6C9",
                fg="#1B5E20",
                anchor="w",
                padx=5,
                pady=1
            )
            stat_label.pack(fill="x")
            self.grup_stat_labels[grup] = stat_label

            # ✅ YENİ: BİTTİ bilgi label'ı (stat_label altında)
            bitti_label = tk.Label(
                grup_outer,
                text="",  # Başlangıçta boş
                font=("Arial", 7, "bold"),
                bg="#FFF9C4",  # Açık sarı arka plan
                fg="#F57F17",  # Koyu sarı yazı
                anchor="center",
                padx=5,
                pady=2
            )
            # Başlangıçta gizli (pack etmiyoruz, sadece kaydediyoruz)
            self.grup_bitti_labels[grup] = bitti_label

        # HEPSİNİ KONTROL ET butonu (C grubu altında)
        tumu_kontrol_frame = tk.Frame(groups_frame, bg=self.bg_color)
        tumu_kontrol_frame.pack(fill="x", pady=(10, 5))

        self.tumu_kontrol_button = tk.Button(
            tumu_kontrol_frame,
            text="🔄 HEPSİNİ KONTROL ET (A→B→C)",
            font=("Arial", 10, "bold"),
            bg="#1976D2",
            fg="white",
            activebackground="#1565C0",
            disabledforeground="#E0E0E0",
            height=2,
            relief="raised",
            bd=3,
            command=self.tumu_kontrol_et
        )
        self.tumu_kontrol_button.pack(fill="x", padx=5)

        # Başlat/Durdur butonları
        buttons_frame = tk.Frame(main_frame, bg=self.bg_color)
        buttons_frame.pack(fill="x", pady=(5, 10))

        self.start_button = tk.Button(
            buttons_frame,
            text="BAŞLAT",
            font=("Arial", 10, "bold"),
            bg="#388E3C",
            fg="white",
            activebackground="#2E7D32",
            disabledforeground="#E0E0E0",
            width=14,
            height=2,
            relief="raised",
            bd=2,
            command=self.basla
        )
        self.start_button.pack(side="left", padx=(0, 5), expand=True)

        self.stop_button = tk.Button(
            buttons_frame,
            text="DURDUR",
            font=("Arial", 10, "bold"),
            bg="#616161",
            fg="white",
            activebackground="#D32F2F",
            disabledforeground="#E0E0E0",
            width=14,
            height=2,
            relief="raised",
            bd=2,
            state="disabled",
            command=self.durdur
        )
        self.stop_button.pack(side="left", expand=True)

        # CAPTCHA butonu kaldırıldı - Botanik program kendi çözüyor

        # CSV Kopyala Butonları
        # CSV Kopyala Butonu (Başlat/Durdur'un hemen altında)
        csv_button = tk.Button(
            main_frame,
            text="📋 CSV Kopyala",
            font=("Arial", 9, "bold"),
            bg="#FFA726",
            fg="white",
            activebackground="#FB8C00",
            relief="raised",
            bd=2,
            command=self.csv_temizle_kopyala
        )
        csv_button.pack(fill="x", pady=(10, 5))

        # Son Kopyalamayı Tekrarla Butonu
        self.son_kopyalama_button = tk.Button(
            main_frame,
            text="📋 Son Kopyalama (---)",
            font=("Arial", 9, "bold"),
            bg="#FF9800",
            fg="white",
            activebackground="#F57C00",
            relief="raised",
            bd=2,
            command=self.csv_son_kopyalamayi_tekrarla
        )
        self.son_kopyalama_button.pack(fill="x", pady=(5, 5))

        # Görev Raporları Butonu
        report_btn_frame = tk.Frame(main_frame, bg=self.bg_color)
        report_btn_frame.pack(fill="x", pady=(0, 5))

        self.report_button = tk.Button(
            report_btn_frame,
            text="📊 Görev Raporları",
            font=("Arial", 9),
            bg="#1976D2",
            fg="white",
            activebackground="#1565C0",
            width=30,
            height=1,
            relief="raised",
            bd=1,
            command=self.gorev_raporlari_goster
        )
        self.report_button.pack()

        # İstatistikler
        stats_frame = tk.Frame(main_frame, bg=self.bg_color)
        stats_frame.pack(fill="x", pady=(0, 10))

        stats_title = tk.Label(
            stats_frame,
            text="Bu Oturum:",
            font=("Arial", 9, "bold"),
            bg=self.bg_color,
            fg="white"
        )
        stats_title.pack()

        self.stats_label = tk.Label(
            stats_frame,
            text="Rç:0 | Takipli:0 | İlaç:0 | R:0 | Süre:0s 0ms | Ort(5):-",
            font=("Arial", 8),
            bg="#C8E6C9",
            fg="#1B5E20",
            relief="sunken",
            bd=1,
            height=2
        )
        self.stats_label.pack(fill="x", pady=2)

        # Yeniden başlatma sayacı
        self.restart_label = tk.Label(
            stats_frame,
            text="Program 0 kez yeniden başlatıldı",
            font=("Arial", 7),
            bg="#FFF3E0",
            fg="#E65100",
            relief="sunken",
            bd=1,
            height=1
        )
        self.restart_label.pack(fill="x", pady=(2, 0))

        # Durum
        status_frame = tk.Frame(main_frame, bg=self.bg_color)
        status_frame.pack(fill="both", expand=True)

        status_title = tk.Label(
            status_frame,
            text="Durum:",
            font=("Arial", 8, "bold"),
            bg=self.bg_color,
            fg="white"
        )
        status_title.pack()

        self.status_label = tk.Label(
            status_frame,
            text="Hazır",
            font=("Arial", 8),
            bg="#A5D6A7",
            fg="#1B5E20",
            relief="sunken",
            bd=1,
            height=2
        )
        self.status_label.pack(fill="x", pady=2)

        # Log alanı
        log_title = tk.Label(
            status_frame,
            text="İşlem Logu:",
            font=("Arial", 7, "bold"),
            bg=self.bg_color,
            fg="white"
        )
        log_title.pack(pady=(5, 0))

        # ScrolledText ile kaydırılabilir log alanı
        self.log_text = scrolledtext.ScrolledText(
            status_frame,
            font=("Arial", 7),
            bg="#E8F5E9",
            fg="#2E7D32",
            relief="sunken",
            bd=1,
            height=10,
            wrap=tk.WORD,
            state="disabled"  # Kullanıcı yazamasın
        )
        self.log_text.pack(fill="both", expand=True)

        # Stats timer - başlangıçta KAPALI (BAŞLAT'a basınca açılacak)
        self.stats_timer_running = False

    def load_grup_verileri(self):
        """Başlangıçta grup verilerini yükle"""
        for grup in ["A", "B", "C"]:
            son_recete = self.grup_durumu.son_recete_al(grup)
            if son_recete:
                self.grup_labels[grup].config(text=son_recete)
            else:
                self.grup_labels[grup].config(text="—")

            # Aylık istatistikleri göster
            self.aylik_istatistik_guncelle(grup)

            # ✅ BİTTİ bilgisini göster
            self.bitti_bilgisi_guncelle(grup)

    def aylik_istatistik_guncelle(self, grup):
        """Grubun aylık istatistiklerini label'a yaz"""
        stats = self.grup_durumu.istatistik_al(grup)
        recete_sayi = stats.get("toplam_recete", 0)
        takip_sayi = stats.get("toplam_takip", 0)
        takipli_recete_sayi = stats.get("toplam_takipli_recete", 0)
        sure_saniye = stats.get("toplam_sure", 0.0)

        # Süreyi dakika/saat formatına çevir (milisaniye ile)
        milisaniye = int((sure_saniye * 1000) % 1000)
        if sure_saniye >= 3600:
            sure_saat = int(sure_saniye // 3600)
            sure_dk = int((sure_saniye % 3600) // 60)
            sure_text = f"{sure_saat}s{sure_dk}dk {milisaniye}ms"
        elif sure_saniye >= 60:
            sure_dk = int(sure_saniye // 60)
            sure_sn = int(sure_saniye % 60)
            sure_text = f"{sure_dk}dk {sure_sn}s {milisaniye}ms"
        else:
            sure_text = f"{int(sure_saniye)}s {milisaniye}ms"

        text = f"Ay: Rç:{recete_sayi} | Takipli:{takipli_recete_sayi} | İlaç:{takip_sayi} | {sure_text}"
        self.grup_stat_labels[grup].config(text=text)

    def bitti_bilgisi_guncelle(self, grup):
        """
        Grubun BİTTİ bilgisini label'a yaz ve göster/gizle

        Args:
            grup: Grup adı ("A", "B" veya "C")
        """
        tarih, sayisi = self.grup_durumu.bitti_bilgisi_al(grup)

        if tarih and sayisi is not None:
            # BİTTİ bilgisi var - göster
            text = f"✅ BİTTİ {tarih} | {sayisi} reçete"
            self.grup_bitti_labels[grup].config(text=text)
            self.grup_bitti_labels[grup].pack(fill="x", pady=(0, 2))  # Göster
        else:
            # BİTTİ bilgisi yok - gizle
            self.grup_bitti_labels[grup].pack_forget()

    def grup_secildi_click(self, grup):
        """Grup alanına tıklandığında (frame veya label tıklaması)"""
        # Radio button'ı seç
        self.secili_grup.set(grup)
        # Normal grup seçimi işlemini çalıştır
        self.grup_secildi(grup)

    def grup_secildi(self, grup):
        """Grup seçildiğinde"""
        logger.info(f"Grup {grup} seçildi")
        self.log_ekle(f"📁 Grup {grup} seçildi")

        # ✅ Aktif modu ayarla (sadece manuel seçimde, tumu_kontrol değilse)
        if not self.tumu_kontrol_aktif:
            self.grup_durumu.aktif_mod_ayarla(grup)
            logger.info(f"Aktif mod: {grup}")

        # Tüm grupların rengini normale çevir (açık yeşil)
        for g in ["A", "B", "C"]:
            if g in self.grup_frames:
                # Ana frame
                self.grup_frames[g]['main'].config(bg="#E8F5E9")
                # Alt widget'lar
                for widget in self.grup_frames[g]['widgets']:
                    try:
                        widget.config(bg="#E8F5E9")
                    except:
                        pass  # X butonu gibi bazı widget'larda bg olmayabilir

        # Seçili grubu mavi yap
        if grup in self.grup_frames:
            # Ana frame
            self.grup_frames[grup]['main'].config(bg="#BBDEFB")  # Açık mavi
            # Alt widget'lar
            for widget in self.grup_frames[grup]['widgets']:
                try:
                    widget.config(bg="#BBDEFB")
                except:
                    pass

        # Son reçete numarasını kontrol et
        son_recete = self.grup_durumu.son_recete_al(grup)

        if son_recete:
            # Son reçete var, otomatik aç
            self.log_ekle(f"📋 Son reçete: {son_recete}")
            self.log_ekle(f"🔍 Reçete açılıyor...")

            # Thread'de reçete açma işlemini başlat
            thread = threading.Thread(target=self.recete_ac, args=(grup, son_recete))
            thread.daemon = True
            thread.start()
        else:
            # İlk reçete - Yeni akış başlat
            self.log_ekle(f"ℹ İlk reçete - Otomatik başlatılıyor...")

            # Thread'de yeni akışı başlat
            thread = threading.Thread(target=self.ilk_recete_akisi, args=(grup,))
            thread.daemon = True
            thread.start()

    def medula_ac_ve_giris_5_deneme_yap(self):
        """
        MEDULA'yı açmayı 5 kere dener. Her denemede:
        1. Taskkill ile MEDULA'yı kapatır
        2. MEDULA'yı açıp giriş yapar

        Returns:
            bool: Başarılıysa True, 5 deneme de başarısız olursa False
        """
        MAX_DENEME = 5

        for deneme in range(1, MAX_DENEME + 1):
            self.root.after(0, lambda d=deneme: self.log_ekle(f"🔄 MEDULA açma denemesi {d}/{MAX_DENEME}"))

            # 1. Taskkill ile MEDULA'yı kapat
            self.root.after(0, lambda: self.log_ekle("📍 MEDULA kapatılıyor (taskkill)..."))
            if medula_taskkill():
                self.taskkill_sayaci += 1
                self.root.after(0, lambda: self.log_ekle(f"✓ MEDULA kapatıldı (Taskkill: {self.taskkill_sayaci})"))

                # Database'e kaydet
                if self.aktif_oturum_id:
                    self.database.artir(self.aktif_oturum_id, "taskkill_sayisi")
                    if self.session_logger:
                        self.session_logger.warning(f"Taskkill yapıldı (#{self.taskkill_sayaci})")
            else:
                self.root.after(0, lambda: self.log_ekle("⚠ Taskkill başarısız, devam ediliyor..."))

            # Taskkill sonrası bekleme
            time.sleep(2)

            # 2. MEDULA'yı aç ve giriş yap
            self.root.after(0, lambda: self.log_ekle("📍 MEDULA açılıyor ve giriş yapılıyor..."))

            try:
                if medula_ac_ve_giris_yap(self.medula_settings):
                    self.root.after(0, lambda: self.log_ekle("✓ MEDULA açıldı ve giriş yapıldı"))
                    time.sleep(3)

                    # Başarılı, bot'a bağlanmayı dene
                    if self.bot is None:
                        self.bot = BotanikBot()

                    if self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                        self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))
                        return True
                    else:
                        self.root.after(0, lambda: self.log_ekle("⚠ Bağlantı kurulamadı, yeniden denenecek..."))
                else:
                    self.root.after(0, lambda: self.log_ekle("⚠ MEDULA açılamadı veya giriş yapılamadı"))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ Hata: {err}"))

            # Son deneme değilse biraz bekle
            if deneme < MAX_DENEME:
                self.root.after(0, lambda: self.log_ekle("⏳ 3 saniye bekleniyor..."))
                time.sleep(3)

        # 5 deneme de başarısız
        self.root.after(0, lambda: self.log_ekle("❌ 5 deneme de başarısız oldu!"))
        return False

    def recete_ac(self, grup, recete_no):
        """Reçeteyi otomatik aç (thread'de çalışır)"""
        try:
            from botanik_bot import masaustu_medula_ac, medula_giris_yap

            # Bot yoksa oluştur ve bağlan
            if self.bot is None:
                self.bot = BotanikBot()

                # MEDULA'ya bağlanmayı dene
                if not self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                    # MEDULA açık değil, 5 kere deneyerek otomatik olarak aç ve giriş yap
                    self.root.after(0, lambda: self.log_ekle("⚠ MEDULA açık değil, otomatik başlatılıyor (5 deneme)..."))

                    if not self.medula_ac_ve_giris_5_deneme_yap():
                        self.root.after(0, lambda: self.log_ekle("❌ MEDULA açılamadı (5 deneme başarısız)"))
                        self.root.after(0, self.hata_sesi_calar)
                        return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))

            # Önce Reçete Sorgu'ya tıklamayı dene
            self.root.after(0, lambda: self.log_ekle("🔘 Reçete Sorgu..."))
            recete_sorgu_acildi = self.bot.recete_sorgu_ac()

            if not recete_sorgu_acildi:
                # Açılmadıysa Ana Sayfa'ya dön ve tekrar dene
                self.root.after(0, lambda: self.log_ekle("🏠 Ana Sayfa..."))
                ana_sayfa_acildi = self.bot.ana_sayfaya_don()

                if not ana_sayfa_acildi:
                    # Ana Sayfa butonu da bulunamadı, MEDULA sıkışmış - yeniden başlat
                    self.root.after(0, lambda: self.log_ekle("⚠ MEDULA sıkışmış, yeniden başlatılıyor..."))

                    # Bot bağlantısını sıfırla
                    self.bot = None

                    # MEDULA'yı yeniden başlat ve giriş yap (taskkill dahil)
                    if not self.medula_ac_ve_giris_5_deneme_yap():
                        self.root.after(0, lambda: self.log_ekle("❌ MEDULA yeniden başlatılamadı"))
                        self.root.after(0, self.hata_sesi_calar)
                        return

                    self.root.after(0, lambda: self.log_ekle("✓ MEDULA yeniden başlatıldı"))
                    time.sleep(1)

                    # Reçete Sorgu'ya tekrar tıkla
                    self.root.after(0, lambda: self.log_ekle("🔘 Reçete Sorgu (yeniden başlatma sonrası)..."))
                    recete_sorgu_acildi = self.bot.recete_sorgu_ac()
                else:
                    time.sleep(0.75)  # Güvenli hasta takibi için: 0.5 → 0.75
                    self.root.after(0, lambda: self.log_ekle("🔘 Reçete Sorgu (2. deneme)..."))
                    recete_sorgu_acildi = self.bot.recete_sorgu_ac()

                if not recete_sorgu_acildi:
                    self.root.after(0, lambda: self.log_ekle("❌ Reçete Sorgu açılamadı"))
                    return

            # Reçete Sorgu ekranı açıldı, kısa bekle
            time.sleep(0.75)  # Güvenli hasta takibi için: 0.5 → 0.75

            # Pencereyi yenile (reçete sorgu ekranı için)
            self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)

            # Reçete numarasını yaz
            self.root.after(0, lambda: self.log_ekle(f"✍ Numara yazılıyor: {recete_no}"))
            if not self.bot.recete_no_yaz(recete_no):
                self.root.after(0, lambda: self.log_ekle("❌ Numara yazılamadı"))
                return

            # Sorgula'ya tıkla
            self.root.after(0, lambda: self.log_ekle("🔍 Sorgula..."))
            if not self.bot.sorgula_butonuna_tikla():
                self.root.after(0, lambda: self.log_ekle("❌ Sorgula başarısız"))
                return

            # Sorgula sonrası popup kontrolü
            time.sleep(0.5)  # Popup için zaman tanı
            try:
                if popup_kontrol_ve_kapat():
                    self.root.after(0, lambda: self.log_ekle("✓ Sorgula sonrası popup kapatıldı"))
                    if self.session_logger:
                        self.session_logger.info("Sorgula sonrası popup kapatıldı")
            except Exception as e:
                logger.warning(f"Sorgula popup kontrol hatası: {e}")

            self.root.after(0, lambda: self.log_ekle(f"✅ Reçete açıldı: {recete_no}"))

            # Tüm pencereleri yerleştir
            self.root.after(0, lambda: self.log_ekle("🖼 Pencereler yerleştiriliyor..."))
            self.tum_pencereleri_yerlestir()
            time.sleep(0.5)

            self.root.after(0, lambda: self.log_ekle("▶ Otomatik olarak başlatılıyor..."))

            # 1 saniye bekle ve otomatik olarak başlat
            time.sleep(1)
            self.root.after(0, self.basla)

        except Exception as e:
            logger.error(f"Reçete açma hatası: {e}")
            self.root.after(0, lambda: self.log_ekle(f"❌ Hata: {e}"))

    def ilk_recete_akisi(self, grup):
        """
        İlk reçete için tam akış (masaüstü simgesi → giriş → reçete listesi → grup seçimi → ilk reçete)
        """
        try:
            from botanik_bot import (
                masaustu_medula_ac,
                medula_giris_yap,
                recete_listesi_ac,
                donem_sec,
                grup_butonuna_tikla,
                bulunamadi_mesaji_kontrol,
                ilk_recete_ac
            )
            from pywinauto import Desktop
            import win32gui
            import win32con

            self.root.after(0, lambda: self.log_ekle("🚀 Grup {} için tam akış başlatılıyor...".format(grup)))

            # MEDULA zaten açık mı kontrol et
            medula_zaten_acik = False
            medula_hwnd = None

            try:
                desktop = Desktop(backend="uia")
                for window in desktop.windows():
                    try:
                        if "MEDULA" in window.window_text() and "BotanikEOS" not in window.window_text():
                            medula_zaten_acik = True
                            medula_hwnd = window.handle
                            self.root.after(0, lambda: self.log_ekle("ℹ MEDULA zaten açık, restore ediliyor..."))
                            break
                    except:
                        pass
            except Exception as e:
                logger.debug(f"MEDULA kontrol hatası: {e}")

            # Eğer MEDULA açıksa, restore et ve giriş adımını atla
            if medula_zaten_acik and medula_hwnd:
                try:
                    # Minimize ise restore et
                    placement = win32gui.GetWindowPlacement(medula_hwnd)
                    current_state = placement[1]

                    if current_state == win32con.SW_SHOWMINIMIZED:
                        self.root.after(0, lambda: self.log_ekle("📍 MEDULA minimize durumda, restore ediliyor..."))
                        win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                        time.sleep(0.5)

                    # Koordinat kontrolü
                    rect = win32gui.GetWindowRect(medula_hwnd)
                    if rect[0] < -10000 or rect[1] < -10000:
                        self.root.after(0, lambda: self.log_ekle("📍 MEDULA gizli konumda, görünür yapılıyor..."))
                        win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                        time.sleep(0.3)
                        win32gui.ShowWindow(medula_hwnd, win32con.SW_SHOW)
                        time.sleep(0.3)

                    self.root.after(0, lambda: self.log_ekle("✓ MEDULA restore edildi"))
                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ MEDULA restore hatası: {err}"))

                # Bot'a bağlan
                self.root.after(0, lambda: self.log_ekle("🔌 MEDULA'ya bağlanılıyor..."))
                if self.bot is None:
                    self.bot = BotanikBot()

                if not self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA'ya bağlanılamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))
                time.sleep(1)

            else:
                # MEDULA açık değil, 5 kere deneyerek aç ve giriş yap
                self.root.after(0, lambda: self.log_ekle("⚠ MEDULA açık değil, otomatik başlatılıyor (5 deneme)..."))

                if not self.medula_ac_ve_giris_5_deneme_yap():
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA açılamadı (5 deneme başarısız)"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))
                time.sleep(1)  # Adım arası bekleme

            # 4. Reçete Listesi'ne tıkla
            self.root.after(0, lambda: self.log_ekle("📋 Reçete Listesi açılıyor..."))
            if not recete_listesi_ac(self.bot):
                self.root.after(0, lambda: self.log_ekle("❌ Reçete Listesi açılamadı"))
                self.root.after(0, self.hata_sesi_calar)
                return

            # Pencereyi yenile
            self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
            time.sleep(1)  # Adım arası bekleme

            # 5. Dönem seç (index=2, yani 3. sıradaki)
            self.root.after(0, lambda: self.log_ekle("📅 Dönem seçiliyor (3. sıra)..."))
            if not donem_sec(self.bot, index=2):
                self.root.after(0, lambda: self.log_ekle("❌ Dönem seçilemedi"))
                self.root.after(0, self.hata_sesi_calar)
                return

            # Pencereyi yenile
            self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
            time.sleep(1)  # Adım arası bekleme

            # 6. Grup butonuna tıkla
            self.root.after(0, lambda: self.log_ekle(f"📁 {grup} grubu sorgulanıyor..."))
            if not grup_butonuna_tikla(self.bot, grup):
                self.root.after(0, lambda: self.log_ekle(f"❌ {grup} grubu sorgulanamadı"))
                self.root.after(0, self.hata_sesi_calar)
                return

            # Pencereyi yenile
            self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
            time.sleep(1)  # Adım arası bekleme

            # 7. "Bulunamadı" mesajı kontrolü
            self.root.after(0, lambda: self.log_ekle("🔍 Reçete varlığı kontrol ediliyor..."))
            if bulunamadi_mesaji_kontrol(self.bot):
                # Mesaj var, 2. dönemi dene (index=1)
                self.root.after(0, lambda: self.log_ekle("⚠ 3. dönemde reçete yok, 2. dönem deneniyor..."))

                # Dönem seç (index=1, yani 2. sıradaki)
                if not donem_sec(self.bot, index=1):
                    self.root.after(0, lambda: self.log_ekle("❌ 2. dönem seçilemedi"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                # Pencereyi yenile
                self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
                time.sleep(1)

                # Grup butonuna tekrar tıkla
                self.root.after(0, lambda: self.log_ekle(f"📁 {grup} grubu (2. dönem) sorgulanıyor..."))
                if not grup_butonuna_tikla(self.bot, grup):
                    self.root.after(0, lambda: self.log_ekle(f"❌ {grup} grubu sorgulanamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                # Pencereyi yenile
                self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)
                time.sleep(1)

                # Tekrar kontrol et
                if bulunamadi_mesaji_kontrol(self.bot):
                    self.root.after(0, lambda: self.log_ekle("❌ 2. dönemde de reçete bulunamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

            # 8. İlk reçete aç
            self.root.after(0, lambda: self.log_ekle("🔘 İlk reçete açılıyor..."))
            if not ilk_recete_ac(self.bot):
                self.root.after(0, lambda: self.log_ekle("❌ İlk reçete açılamadı"))
                self.root.after(0, self.hata_sesi_calar)
                return

            # Pencereyi yenile
            self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)

            # İlk reçete açıldıktan sonra popup kontrolü
            time.sleep(0.5)  # Popup için zaman tanı
            try:
                if popup_kontrol_ve_kapat():
                    self.root.after(0, lambda: self.log_ekle("✓ İlk reçete popup kapatıldı"))
                    if self.session_logger:
                        self.session_logger.info("İlk reçete popup kapatıldı")
            except Exception as e:
                logger.warning(f"İlk reçete popup kontrol hatası: {e}")

            self.root.after(0, lambda: self.log_ekle("✅ İlk reçete başarıyla açıldı"))

            # Tüm pencereleri yerleştir
            self.root.after(0, lambda: self.log_ekle("🖼 Pencereler yerleştiriliyor..."))
            self.tum_pencereleri_yerlestir()
            time.sleep(0.5)

            self.root.after(0, lambda: self.log_ekle("▶ Otomatik olarak başlatılıyor..."))

            # 1 saniye bekle ve otomatik olarak başlat
            time.sleep(1)
            self.root.after(0, self.basla)

        except Exception as e:
            logger.error(f"İlk reçete akışı hatası: {e}", exc_info=True)
            self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Hata: {err}"))
            self.root.after(0, self.hata_sesi_calar)

    def grup_sifirla(self, grup):
        """X butonuna basıldığında grubu sıfırla"""
        self.grup_durumu.grup_sifirla(grup)
        self.grup_labels[grup].config(text="—")
        self.aylik_istatistik_guncelle(grup)  # Aylık istatistiği de güncelle
        self.log_ekle(f"Grup {grup} sıfırlandı")
        logger.info(f"Grup {grup} sıfırlandı")

    def csv_temizle_kopyala(self):
        """Kopyalanmamış + geçerli raporları SonRaporlar.csv olarak kaydet ve panoya kopyala"""
        try:
            from datetime import datetime
            import csv
            from pathlib import Path

            # Kopyalanmamış + geçerli raporları al
            raporlar, silinen_sayisi = self.rapor_takip.kopyalanmamis_raporlari_al()

            if not raporlar:
                if silinen_sayisi > 0:
                    self.log_ekle(f"ℹ️ {silinen_sayisi} geçmiş rapor atlandı, kopyalanacak yeni rapor yok")
                else:
                    self.log_ekle("ℹ️ Kopyalanacak yeni rapor yok")
                return

            # SonRaporlar.csv yolu
            son_raporlar_yolu = Path("SonRaporlar.csv")

            # CSV'ye yaz (Mesajlar format: Ad Soyad, Telefon, Rapor Tanısı, Bitiş Tarihi, Kayıt Tarihi)
            with open(son_raporlar_yolu, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = ['Ad Soyad', 'Telefon', 'Rapor Tanısı', 'Bitiş Tarihi', 'Kayıt Tarihi']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for rapor in raporlar:
                    writer.writerow({
                        'Ad Soyad': rapor['ad'],
                        'Telefon': rapor['telefon'],
                        'Rapor Tanısı': rapor['tani'],
                        'Bitiş Tarihi': rapor['bitis'],
                        'Kayıt Tarihi': rapor['kayit']
                    })

            # CSV içeriğini panoya kopyala
            with open(son_raporlar_yolu, 'r', encoding='utf-8-sig') as f:
                csv_icerik = f.read()

            self.root.clipboard_clear()
            self.root.clipboard_append(csv_icerik)
            self.root.update()

            # Kopyalanan raporları işaretle
            isaretlenen = self.rapor_takip.kopyalandi_isaretle(raporlar)

            # Bildirim
            if silinen_sayisi > 0:
                self.log_ekle(f"✓ {silinen_sayisi} geçmiş rapor atlandı")
            self.log_ekle(f"✓ {len(raporlar)} rapor panoya kopyalandı ve işaretlendi")

            # Son kopyalama tarihini güncelle
            self.son_kopyalama_tarihi = datetime.now()
            self._guncelle_son_kopyalama_butonu()

        except Exception as e:
            self.log_ekle(f"❌ CSV kopyalama hatası: {e}")
            logger.error(f"CSV kopyalama hatası: {e}")

    def csv_son_kopyalamayi_tekrarla(self):
        """SonRaporlar.csv dosyasını tekrar panoya kopyala"""
        try:
            from pathlib import Path

            son_raporlar_yolu = Path("SonRaporlar.csv")

            if not son_raporlar_yolu.exists():
                self.log_ekle("❌ SonRaporlar.csv dosyası bulunamadı. Önce normal kopyalama yapın.")
                return

            # Dosyayı oku ve panoya kopyala
            with open(son_raporlar_yolu, 'r', encoding='utf-8-sig') as f:
                csv_icerik = f.read()

            # Satır sayısını hesapla (header hariç)
            satir_sayisi = csv_icerik.count('\n') - 1
            if satir_sayisi < 0:
                satir_sayisi = 0

            self.root.clipboard_clear()
            self.root.clipboard_append(csv_icerik)
            self.root.update()

            self.log_ekle(f"✓ Son kopyalama ({satir_sayisi} rapor) tekrar panoya kopyalandı")

        except Exception as e:
            self.log_ekle(f"❌ Son kopyalama hatası: {e}")
            logger.error(f"Son kopyalama hatası: {e}")

    def _guncelle_son_kopyalama_butonu(self):
        """Son kopyalama butonunun metnini güncelle"""
        if self.son_kopyalama_button and self.son_kopyalama_tarihi:
            tarih_str = self.son_kopyalama_tarihi.strftime("%d/%m/%Y %H:%M")
            self.son_kopyalama_button.config(text=f"📋 Son Kopyalama ({tarih_str})")

    def hata_sesi_calar(self):
        """Hata durumunda 3 kez bip sesi çıkar"""
        def calar():
            try:
                for _ in range(3):
                    winsound.Beep(1000, 300)  # 1000Hz, 300ms
                    time.sleep(0.2)
            except:
                pass

        thread = threading.Thread(target=calar)
        thread.daemon = True
        thread.start()

    def log_ekle(self, mesaj):
        """Log alanına mesaj ekle ve otomatik kaydır"""
        self.log_gecmisi.append(mesaj)
        if len(self.log_gecmisi) > 100:  # Daha fazla log saklayalım
            self.log_gecmisi = self.log_gecmisi[-100:]

        # ScrolledText'e yaz
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert("1.0", "\n".join(self.log_gecmisi))
        self.log_text.config(state="disabled")

        # Otomatik kaydır (en alta)
        self.log_text.see(tk.END)

    def create_settings_tab(self, parent):
        """Ayarlar sekmesi içeriğini oluştur - İki alt sekme ile"""
        # Alt sekmeler için notebook oluştur
        settings_notebook = ttk.Notebook(parent)
        settings_notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # Giriş Ayarları sekmesi
        giris_tab = tk.Frame(settings_notebook, bg='#E3F2FD')
        settings_notebook.add(giris_tab, text="  🔐 Giriş Ayarları  ")

        # Timing Ayarları sekmesi
        timing_tab = tk.Frame(settings_notebook, bg='#E8F5E9')
        settings_notebook.add(timing_tab, text="  ⏱ Timing Ayarları  ")

        # İçerikleri oluştur
        self.create_giris_ayarlari_tab(giris_tab)
        self.create_timing_ayarlari_tab(timing_tab)

    def create_giris_ayarlari_tab(self, parent):
        """Giriş Ayarları sekmesi içeriğini oluştur"""
        # Ana frame
        main_frame = tk.Frame(parent, bg='#E3F2FD')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== MEDULA GİRİŞ BİLGİLERİ =====
        medula_frame = tk.LabelFrame(
            main_frame,
            text="🔐 MEDULA Giriş Bilgileri",
            font=("Arial", 11, "bold"),
            bg='#E3F2FD',
            fg='#0D47A1',
            padx=10,
            pady=10
        )
        medula_frame.pack(fill="x", pady=(0, 10))

        # Kullanıcı Seçimi
        tk.Label(
            medula_frame,
            text="👤 Kullanıcı Seç:",
            font=("Arial", 9, "bold"),
            bg='#E3F2FD',
            fg='#0D47A1'
        ).grid(row=0, column=0, sticky="w", padx=5, pady=8)

        kullanici_listesi = [k.get("ad", f"Kullanıcı {i+1}") for i, k in enumerate(self.medula_settings.get_kullanicilar())]
        aktif_index = self.medula_settings.get("aktif_kullanici", 0)

        self.kullanici_secim_var = tk.StringVar(value=kullanici_listesi[aktif_index] if kullanici_listesi else "Kullanıcı 1")
        self.kullanici_secim_combo = ttk.Combobox(
            medula_frame,
            textvariable=self.kullanici_secim_var,
            values=kullanici_listesi,
            state="readonly",
            font=("Arial", 9),
            width=27
        )
        self.kullanici_secim_combo.grid(row=0, column=1, padx=5, pady=8)
        self.kullanici_secim_combo.bind("<<ComboboxSelected>>", self.kullanici_secimi_degisti)

        # Ayırıcı
        tk.Label(
            medula_frame,
            text="─" * 50,
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#90CAF9'
        ).grid(row=1, column=0, columnspan=2, pady=5)

        # Kullanıcı Adı (Opsiyonel Etiket)
        tk.Label(
            medula_frame,
            text="Kullanıcı Etiketi:",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20'
        ).grid(row=2, column=0, sticky="w", padx=5, pady=5)

        self.medula_kullanici_ad_entry = tk.Entry(
            medula_frame,
            font=("Arial", 9),
            width=30
        )
        self.medula_kullanici_ad_entry.grid(row=2, column=1, padx=5, pady=5)

        # MEDULA Kullanıcı Index
        tk.Label(
            medula_frame,
            text="MEDULA Kullanıcı:",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20'
        ).grid(row=3, column=0, sticky="w", padx=5, pady=5)

        self.medula_index_var = tk.StringVar()
        self.medula_index_combo = ttk.Combobox(
            medula_frame,
            textvariable=self.medula_index_var,
            values=[
                "1. Kullanıcı (Index 0)",
                "2. Kullanıcı (Index 1)",
                "3. Kullanıcı (Index 2)",
                "4. Kullanıcı (Index 3)",
                "5. Kullanıcı (Index 4)",
                "6. Kullanıcı (Index 5)"
            ],
            state="readonly",
            font=("Arial", 9),
            width=27
        )
        self.medula_index_combo.grid(row=3, column=1, padx=5, pady=5)

        # Şifre
        tk.Label(
            medula_frame,
            text="Şifre:",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20'
        ).grid(row=4, column=0, sticky="w", padx=5, pady=5)

        self.medula_sifre_entry = tk.Entry(
            medula_frame,
            font=("Arial", 9),
            width=30,
            show="*"
        )
        self.medula_sifre_entry.grid(row=4, column=1, padx=5, pady=5)

        # Seçili kullanıcının bilgilerini yükle
        self.secili_kullanici_bilgilerini_yukle()

        # Kaydet Butonu
        tk.Button(
            medula_frame,
            text="💾 Kullanıcı Bilgilerini Kaydet",
            font=("Arial", 9, "bold"),
            bg='#1976D2',
            fg='white',
            width=30,
            command=self.medula_bilgilerini_kaydet
        ).grid(row=5, column=0, columnspan=2, pady=10)

        # Uyarı
        tk.Label(
            medula_frame,
            text="⚠ Bilgiler şifrelenmeden kaydedilir. Güvenli bir bilgisayarda kullanın.",
            font=("Arial", 6),
            bg='#E3F2FD',
            fg='#D32F2F'
        ).grid(row=6, column=0, columnspan=2)

        tk.Label(
            medula_frame,
            text="ℹ Her kullanıcı için farklı MEDULA hesabı kullanabilirsiniz.",
            font=("Arial", 7),
            bg='#E3F2FD',
            fg='#1565C0'
        ).grid(row=7, column=0, columnspan=2, pady=(0, 5))

        # Ayırıcı (Giriş Yöntemi için)
        tk.Label(
            medula_frame,
            text="─" * 50,
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#90CAF9'
        ).grid(row=8, column=0, columnspan=2, pady=5)

        # Giriş Yöntemi Seçimi
        tk.Label(
            medula_frame,
            text="🔐 Giriş Yöntemi:",
            font=("Arial", 9, "bold"),
            bg='#E3F2FD',
            fg='#0D47A1'
        ).grid(row=9, column=0, sticky="w", padx=5, pady=(5, 0))

        # Giriş yöntemi için frame
        giris_yontemi_frame = tk.Frame(medula_frame, bg='#E3F2FD')
        giris_yontemi_frame.grid(row=9, column=1, sticky="w", padx=5, pady=(5, 0))

        self.giris_yontemi_var = tk.StringVar(value=self.medula_settings.get("giris_yontemi", "indeks"))

        # İndeks radio button
        tk.Radiobutton(
            giris_yontemi_frame,
            text="İndeks ile (örn: 4. kullanıcı)",
            variable=self.giris_yontemi_var,
            value="indeks",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20',
            activebackground='#E3F2FD',
            command=self.giris_yontemi_degisti
        ).pack(anchor="w")

        # Kullanıcı adı radio button
        tk.Radiobutton(
            giris_yontemi_frame,
            text="Kullanıcı adı ile (örn: Ali Veli)",
            variable=self.giris_yontemi_var,
            value="kullanici_adi",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20',
            activebackground='#E3F2FD',
            command=self.giris_yontemi_degisti
        ).pack(anchor="w")

        # Kullanıcı Adı Girişi (sadece kullanici_adi seçiliyse aktif)
        tk.Label(
            medula_frame,
            text="MEDULA Kullanıcı Adı:",
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#1B5E20'
        ).grid(row=10, column=0, sticky="w", padx=5, pady=5)

        self.kullanici_adi_giris_entry = tk.Entry(
            medula_frame,
            font=("Arial", 9),
            width=30
        )
        self.kullanici_adi_giris_entry.grid(row=10, column=1, padx=5, pady=5)

        # Varsayılan değeri yükle
        kullanici_adi_giris = self.medula_settings.get("kullanici_adi_giris", "")
        if kullanici_adi_giris:
            self.kullanici_adi_giris_entry.insert(0, kullanici_adi_giris)

        # İlk durumu ayarla
        self.giris_yontemi_degisti()

        # Bilgi notu
        tk.Label(
            medula_frame,
            text="ℹ İndeks: Combobox'ta kaç kere DOWN tuşuna basılacağını belirler (0-5 arası)\nKullanıcı Adı: MEDULA giriş ekranında bu kullanıcı adı aranır",
            font=("Arial", 6),
            bg='#E3F2FD',
            fg='#616161',
            justify="left"
        ).grid(row=11, column=0, columnspan=2, pady=(0, 5))

        # Kaydet butonu (Giriş Yöntemi için)
        tk.Button(
            medula_frame,
            text="💾 Giriş Yöntemi Ayarlarını Kaydet",
            font=("Arial", 8, "bold"),
            bg='#1976D2',
            fg='white',
            width=35,
            command=self.giris_yontemi_ayarlarini_kaydet
        ).grid(row=12, column=0, columnspan=2, pady=5)

        # Ayırıcı (Telefon Kontrolü için)
        tk.Label(
            medula_frame,
            text="─" * 50,
            font=("Arial", 8),
            bg='#E3F2FD',
            fg='#90CAF9'
        ).grid(row=13, column=0, columnspan=2, pady=5)

        # Telefon Kontrolü Checkbox
        self.telefonsuz_atla_var = tk.BooleanVar(value=self.medula_settings.get("telefonsuz_atla", False))
        telefon_checkbox = tk.Checkbutton(
            medula_frame,
            text="📵 Telefon numarası olmayan hastaları atla",
            variable=self.telefonsuz_atla_var,
            font=("Arial", 9),
            bg='#E3F2FD',
            fg='#D32F2F',
            activebackground='#E3F2FD',
            command=self.telefon_ayarini_kaydet
        )
        telefon_checkbox.grid(row=14, column=0, columnspan=2, sticky="w", padx=5, pady=(5, 0))

        tk.Label(
            medula_frame,
            text="ℹ Telefon yoksa hasta işleme alınmadan direkt sonraki hastaya geçilir.",
            font=("Arial", 6),
            bg='#E3F2FD',
            fg='#616161'
        ).grid(row=15, column=0, columnspan=2, pady=(0, 5))

    def create_timing_ayarlari_tab(self, parent):
        """Timing Ayarları sekmesi içeriğini oluştur"""
        # Ana frame
        main_frame = tk.Frame(parent, bg='#E8F5E9')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # ===== ZAMANLAMA AYARLARI =====
        timing_title = tk.Label(
            main_frame,
            text="⏱ Zamanlama Ayarları",
            font=("Arial", 12, "bold"),
            bg='#E8F5E9',
            fg='#1B5E20'
        )
        timing_title.pack(pady=(10, 5))

        subtitle = tk.Label(
            main_frame,
            text="Her işlem için bekleme sürelerini ayarlayın (saniye)",
            font=("Arial", 8),
            bg='#E8F5E9',
            fg='#2E7D32'
        )
        subtitle.pack(pady=(0, 5))

        # Hızlı ayar butonları
        quick_frame = tk.Frame(main_frame, bg='#E8F5E9')
        quick_frame.pack(fill="x", pady=(0, 5))

        tk.Label(
            quick_frame,
            text="Hızlı:",
            font=("Arial", 8, "bold"),
            bg='#E8F5E9',
            fg='#1B5E20'
        ).pack(side="left", padx=(0, 5))

        hizli_butonlar = [
            ("Çok Hızlı (x0.5)", 0.5),
            ("Normal (x1.0)", 1.0),
            ("Yavaş (x1.5)", 1.5),
            ("Çok Yavaş (x2.0)", 2.0),
        ]

        for text, carpan in hizli_butonlar:
            btn = tk.Button(
                quick_frame,
                text=text,
                font=("Arial", 6),
                bg='#81C784',
                fg='white',
                width=11,
                height=1,
                command=lambda c=carpan: self.hizli_ayarla(c)
            )
            btn.pack(side="left", padx=1)

        # Optimize Mode Checkbox
        optimize_frame = tk.Frame(main_frame, bg='#E8F5E9')
        optimize_frame.pack(fill="x", pady=(5, 0))

        self.optimize_mode_var = tk.BooleanVar(value=False)
        optimize_checkbox = tk.Checkbutton(
            optimize_frame,
            text="🔧 Otomatik Optimize:",
            variable=self.optimize_mode_var,
            font=("Arial", 9, "bold"),
            bg='#E8F5E9',
            fg='#FF6F00',
            activebackground='#E8F5E9',
            command=self.optimize_mode_toggle
        )
        optimize_checkbox.pack(side="left", padx=5)

        # Çarpan label
        tk.Label(
            optimize_frame,
            text="Çarpan:",
            font=("Arial", 8),
            bg='#E8F5E9',
            fg='#424242'
        ).pack(side="left", padx=(5, 2))

        # Çarpan input (0.8 - 2.0 arası)
        self.optimize_multiplier_var = tk.StringVar(value="1.3")
        multiplier_spinbox = tk.Spinbox(
            optimize_frame,
            from_=0.8,
            to=2.0,
            increment=0.1,
            textvariable=self.optimize_multiplier_var,
            width=5,
            font=("Arial", 8),
            bg='white'
        )
        multiplier_spinbox.pack(side="left", padx=2)

        # Açıklama
        tk.Label(
            optimize_frame,
            text="x (0.8=-%20, 1.0=aynı, 1.3=+%30, 1.5=+%50)",
            font=("Arial", 7),
            bg='#E8F5E9',
            fg='#757575'
        ).pack(side="left", padx=(2, 5))

        # Optimize açıklama (ikinci satır)
        optimize_info_frame = tk.Frame(main_frame, bg='#E8F5E9')
        optimize_info_frame.pack(fill="x", pady=(0, 5))

        optimize_info = tk.Label(
            optimize_info_frame,
            text="(İlk çalıştırmada tüm süreler 3s başlar, sonra reel süre × çarpan ile otomatik ayarlanır)",
            font=("Arial", 7),
            bg='#E8F5E9',
            fg='#757575'
        )
        optimize_info.pack(side="left", padx=5)

        # Scrollable canvas (height belirtildi böylece scroll düzgün çalışır)
        canvas = tk.Canvas(main_frame, bg='#E8F5E9', highlightthickness=0, height=400)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#E8F5E9')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scroll desteği
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Kategorilere göre ayarları göster
        kategoriler = self.timing.kategori_listesi()

        for kategori_adi, ayarlar in kategoriler.items():
            # Kategori frame
            kategori_frame = tk.LabelFrame(
                scrollable_frame,
                text=kategori_adi,
                font=("Arial", 8, "bold"),
                bg='#C8E6C9',
                fg='#1B5E20',
                padx=5,
                pady=3
            )
            kategori_frame.pack(fill="x", padx=3, pady=3)

            # Her ayar için satır
            for ayar_key, ayar_label in ayarlar:
                row_frame = tk.Frame(kategori_frame, bg='#C8E6C9')
                row_frame.pack(fill="x", pady=1)

                # Label
                label = tk.Label(
                    row_frame,
                    text=ayar_label + ":",
                    font=("Arial", 7),
                    bg='#C8E6C9',
                    fg='#1B5E20',
                    width=18,
                    anchor="w"
                )
                label.pack(side="left", padx=(0, 5))

                # Entry
                entry_var = tk.StringVar(value=str(self.timing.get(ayar_key)))
                entry = tk.Entry(
                    row_frame,
                    textvariable=entry_var,
                    font=("Arial", 7),
                    width=8,
                    justify="right"
                )
                entry.pack(side="left", padx=(0, 3))

                # Entry değiştiğinde otomatik kaydet
                entry_var.trace_add("write", lambda *args, key=ayar_key, var=entry_var: self.ayar_degisti(key, var))

                self.ayar_entry_widgets[ayar_key] = entry_var

                # Birim
                tk.Label(
                    row_frame,
                    text="sn",
                    font=("Arial", 6),
                    bg='#C8E6C9',
                    fg='#2E7D32'
                ).pack(side="left")

                # İstatistik label
                stats = self.timing.istatistik_al(ayar_key)
                count = stats.get("count", 0)
                avg = self.timing.ortalama_al(ayar_key)

                if count > 0 and avg is not None:
                    stat_text = f"({count}x, ort:{avg:.3f}s)"
                else:
                    stat_text = "(0x, ort:-)"

                tk.Label(
                    row_frame,
                    text=stat_text,
                    font=("Arial", 7),
                    bg='#C8E6C9',
                    fg='#616161',
                    anchor="w"
                ).pack(side="left", padx=(3, 0))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Alt butonlar
        button_frame = tk.Frame(main_frame, bg='#E8F5E9')
        button_frame.pack(fill="x", pady=(5, 0))

        tk.Button(
            button_frame,
            text="Varsayılana Döndür",
            font=("Arial", 8),
            bg='#FFA726',
            fg='white',
            width=13,
            height=1,
            command=self.varsayilana_don
        ).pack(side="left", padx=(0, 3))

        tk.Button(
            button_frame,
            text="Şimdi Kaydet",
            font=("Arial", 8, "bold"),
            bg='#388E3C',
            fg='white',
            width=13,
            height=1,
            command=self.ayarlari_kaydet
        ).pack(side="left", padx=(0, 3))

        tk.Button(
            button_frame,
            text="İstatistik Sıfırla",
            font=("Arial", 8),
            bg='#D32F2F',
            fg='white',
            width=13,
            height=1,
            command=self.istatistikleri_sifirla
        ).pack(side="left")

        # Durum mesajı
        self.ayar_durum_label = tk.Label(
            main_frame,
            text="Ayarlar otomatik kaydedilir",
            font=("Arial", 6),
            bg='#E8F5E9',
            fg='#2E7D32'
        )
        self.ayar_durum_label.pack(pady=(3, 0))

    def ayar_degisti(self, key, var):
        """Bir ayar değiştiğinde otomatik kaydet (debounced)"""
        # Önce timer'ı iptal et
        if self.ayar_kaydet_timer:
            self.root.after_cancel(self.ayar_kaydet_timer)

        # Ayarı bellekte güncelle (henüz kaydetme)
        try:
            deger = float(var.get())
            if deger >= 0:
                self.timing.set(key, deger)
                self.ayar_durum_label.config(text="Değişiklik kaydediliyor...", fg='#F57F17')
                # 1 saniye sonra kaydet (debounce)
                self.ayar_kaydet_timer = self.root.after(1000, self._gercek_kaydet)
        except ValueError:
            pass  # Geçersiz değer girildi, sessizce yoksay

    def _gercek_kaydet(self):
        """Debounce sonrası gerçek kaydetme"""
        try:
            if self.timing.kaydet():
                self.ayar_durum_label.config(text="✓ Otomatik kaydedildi", fg='#1B5E20')
                self.root.after(2000, lambda: self.ayar_durum_label.config(text="Ayarlar otomatik kaydedilir", fg='#2E7D32'))
            else:
                self.ayar_durum_label.config(text="❌ Kaydetme hatası", fg='#C62828')
        except Exception as e:
            logger.error(f"Ayar kaydetme hatası: {e}")
            self.ayar_durum_label.config(text="❌ Kaydetme hatası", fg='#C62828')

    def hizli_ayarla(self, carpan):
        """Tüm değerleri çarpan ile güncelle"""
        for key, entry_var in self.ayar_entry_widgets.items():
            varsayilan = self.timing.varsayilan_ayarlar.get(key, 0.1)
            yeni_deger = round(varsayilan * carpan, 3)
            entry_var.set(str(yeni_deger))
        self.ayar_durum_label.config(text=f"✓ Tüm ayarlar {carpan}x olarak güncellendi", fg='#1B5E20')

    def optimize_mode_toggle(self):
        """Optimize mode checkbox'ı değiştiğinde"""
        if self.optimize_mode_var.get():
            # Çarpanı al
            try:
                multiplier = float(self.optimize_multiplier_var.get())
                if multiplier < 0.8 or multiplier > 2.0:
                    multiplier = 1.3
                    self.optimize_multiplier_var.set("1.3")
            except:
                multiplier = 1.3
                self.optimize_multiplier_var.set("1.3")

            # Optimize mode açıldı
            self.timing.optimize_mode_ac(multiplier)
            self.log_ekle(f"🚀 Otomatik optimize aktif - Çarpan: {multiplier}x - Tüm ayarlar 3s")
            logger.info(f"🚀 Otomatik optimize mode aktif - Çarpan: {multiplier}x")

            # GUI'deki entry'leri de güncelle
            for key, entry_var in self.ayar_entry_widgets.items():
                entry_var.set("3.0")
        else:
            # Optimize mode kapatıldı
            self.timing.optimize_mode_kapat()
            self.log_ekle("⏹ Otomatik optimize kapatıldı")
            logger.info("⏹ Otomatik optimize mode kapatıldı")

    def varsayilana_don(self):
        """Tüm değerleri varsayılana döndür"""
        for key, entry_var in self.ayar_entry_widgets.items():
            varsayilan = self.timing.varsayilan_ayarlar.get(key, 0.1)
            entry_var.set(str(varsayilan))
        self.ayar_durum_label.config(text="✓ Varsayılan değerler yüklendi", fg='#1B5E20')

    def ayarlari_kaydet(self):
        """Tüm ayarları manuel kaydet"""
        try:
            for key, entry_var in self.ayar_entry_widgets.items():
                try:
                    deger = float(entry_var.get())
                    if deger < 0:
                        raise ValueError("Negatif değer")
                    self.timing.set(key, deger)
                except ValueError:
                    self.ayar_durum_label.config(text=f"❌ Hata: {key} geçersiz", fg='#C62828')
                    return

            if self.timing.kaydet():
                self.ayar_durum_label.config(text="✓ Ayarlar kaydedildi", fg='#1B5E20')
                self.log_ekle("✓ Zamanlama ayarları güncellendi")
            else:
                self.ayar_durum_label.config(text="❌ Kaydetme hatası", fg='#C62828')
        except Exception as e:
            self.ayar_durum_label.config(text=f"❌ Hata: {e}", fg='#C62828')

    def istatistikleri_sifirla(self):
        """Tüm istatistikleri sıfırla"""
        from tkinter import messagebox
        cevap = messagebox.askyesno(
            "İstatistikleri Sıfırla",
            "Tüm sayfa yükleme istatistikleri silinecek. Emin misiniz?"
        )
        if cevap:
            self.timing.istatistik_sifirla()
            self.ayar_durum_label.config(text="✓ İstatistikler sıfırlandı", fg='#1B5E20')
            self.log_ekle("✓ Sayfa yükleme istatistikleri sıfırlandı")
            # Ayarlar sekmesini yenile (istatistikleri güncellemek için)
            messagebox.showinfo("Bilgi", "İstatistikler sıfırlandı. Ayarlar sekmesi kapanıp açılırsa güncel değerler görünecektir.")

    def kullanici_secimi_degisti(self, event=None):
        """Kullanıcı seçimi değiştiğinde form alanlarını güncelle"""
        self.secili_kullanici_bilgilerini_yukle()

    def secili_kullanici_bilgilerini_yukle(self):
        """Seçili kullanıcının bilgilerini form alanlarına yükle"""
        # Seçili kullanıcı index'ini bul
        secili_ad = self.kullanici_secim_var.get()
        kullanicilar = self.medula_settings.get_kullanicilar()

        secili_index = 0
        for i, k in enumerate(kullanicilar):
            if k.get("ad") == secili_ad:
                secili_index = i
                break

        # Kullanıcı bilgilerini al
        kullanici = self.medula_settings.get_kullanici(secili_index)

        if kullanici:
            # Form alanlarını temizle ve yeni değerleri yükle
            self.medula_kullanici_ad_entry.delete(0, tk.END)
            self.medula_kullanici_ad_entry.insert(0, kullanici.get("ad", ""))

            # MEDULA Index combobox'ını ayarla
            medula_index = kullanici.get("kullanici_index", 0)
            if medula_index == 0:
                self.medula_index_var.set("1. Kullanıcı (Index 0)")
            elif medula_index == 1:
                self.medula_index_var.set("2. Kullanıcı (Index 1)")
            elif medula_index == 2:
                self.medula_index_var.set("3. Kullanıcı (Index 2)")
            elif medula_index == 3:
                self.medula_index_var.set("4. Kullanıcı (Index 3)")
            elif medula_index == 4:
                self.medula_index_var.set("5. Kullanıcı (Index 4)")
            elif medula_index == 5:
                self.medula_index_var.set("6. Kullanıcı (Index 5)")

            # Şifreyi yükle
            self.medula_sifre_entry.delete(0, tk.END)
            self.medula_sifre_entry.insert(0, kullanici.get("sifre", ""))

    def medula_bilgilerini_kaydet(self):
        """Seçili kullanıcının MEDULA bilgilerini kaydet"""
        # Formdaki değerleri al
        kullanici_ad = self.medula_kullanici_ad_entry.get().strip()
        sifre = self.medula_sifre_entry.get().strip()

        # MEDULA index'i parse et
        medula_index_str = self.medula_index_var.get()
        if "Index 0" in medula_index_str:
            medula_index = 0
        elif "Index 1" in medula_index_str:
            medula_index = 1
        elif "Index 2" in medula_index_str:
            medula_index = 2
        elif "Index 3" in medula_index_str:
            medula_index = 3
        elif "Index 4" in medula_index_str:
            medula_index = 4
        elif "Index 5" in medula_index_str:
            medula_index = 5
        else:
            messagebox.showwarning("Uyarı", "Lütfen MEDULA kullanıcısını seçin!")
            return

        if not sifre:
            messagebox.showwarning("Uyarı", "Şifre boş olamaz!")
            return

        # Seçili kullanıcı index'ini bul
        secili_ad = self.kullanici_secim_var.get()
        kullanicilar = self.medula_settings.get_kullanicilar()

        secili_index = 0
        for i, k in enumerate(kullanicilar):
            if k.get("ad") == secili_ad:
                secili_index = i
                break

        # Kullanıcı bilgilerini güncelle
        self.medula_settings.update_kullanici(
            secili_index,
            ad=kullanici_ad if kullanici_ad else None,
            kullanici_index=medula_index,
            sifre=sifre
        )

        # Aktif kullanıcıyı ayarla
        self.medula_settings.set_aktif_kullanici(secili_index)

        # Kaydet
        if self.medula_settings.kaydet():
            # Combobox'ı güncelle (kullanıcı adı değiştiyse)
            if kullanici_ad:
                kullanici_listesi = [k.get("ad", f"Kullanıcı {i+1}") for i, k in enumerate(self.medula_settings.get_kullanicilar())]
                self.kullanici_secim_combo['values'] = kullanici_listesi
                self.kullanici_secim_var.set(kullanici_ad)

            messagebox.showinfo("Başarılı", f"{kullanici_ad if kullanici_ad else secili_ad} bilgileri kaydedildi!")
            self.log_ekle(f"✓ {kullanici_ad if kullanici_ad else secili_ad} MEDULA bilgileri güncellendi")
        else:
            messagebox.showerror("Hata", "Kaydetme başarısız!")
            self.log_ekle("❌ MEDULA bilgileri kaydedilemedi")

    def giris_yontemi_degisti(self):
        """Giriş yöntemi değiştiğinde kullanıcı adı entry'sini aktif/pasif yap"""
        yontem = self.giris_yontemi_var.get()
        if yontem == "kullanici_adi":
            self.kullanici_adi_giris_entry.config(state="normal")
        else:
            self.kullanici_adi_giris_entry.config(state="disabled")

    def giris_yontemi_ayarlarini_kaydet(self):
        """Giriş yöntemi ayarlarını kaydet"""
        yontem = self.giris_yontemi_var.get()
        kullanici_adi = self.kullanici_adi_giris_entry.get().strip()

        # Kullanıcı adı yöntemi seçiliyse ama ad girilmemişse uyar
        if yontem == "kullanici_adi" and not kullanici_adi:
            messagebox.showwarning("Uyarı", "Kullanıcı adı ile giriş seçiliyse MEDULA Kullanıcı Adı alanını doldurmalısınız!")
            return

        # Ayarları güncelle
        self.medula_settings.set("giris_yontemi", yontem)
        self.medula_settings.set("kullanici_adi_giris", kullanici_adi)

        if self.medula_settings.kaydet():
            yontem_text = "İndeks" if yontem == "indeks" else f"Kullanıcı Adı ({kullanici_adi})"
            messagebox.showinfo("Başarılı", f"Giriş yöntemi kaydedildi: {yontem_text}")
            self.log_ekle(f"✓ Giriş yöntemi: {yontem_text}")
            logger.info(f"✓ Giriş yöntemi ayarı: {yontem_text}")
        else:
            messagebox.showerror("Hata", "Ayar kaydedilemedi!")
            self.log_ekle("❌ Giriş yöntemi kaydedilemedi")

    def telefon_ayarini_kaydet(self):
        """Telefon kontrolü ayarını kaydet"""
        telefonsuz_atla = self.telefonsuz_atla_var.get()
        self.medula_settings.set("telefonsuz_atla", telefonsuz_atla)

        if self.medula_settings.kaydet():
            durum = "AÇIK" if telefonsuz_atla else "KAPALI"
            self.log_ekle(f"✓ Telefon kontrolü: {durum}")
            logger.info(f"✓ Telefon kontrolü ayarı: {durum}")
        else:
            self.log_ekle("❌ Ayar kaydedilemedi")

    def basla(self):
        """Başlat butonuna basıldığında"""
        logger.info(f"basla() çağrıldı: is_running={self.is_running}, secili_grup={self.secili_grup.get()}")

        if self.is_running:
            logger.warning("Başlatma iptal: is_running=True")
            return

        secili = self.secili_grup.get()
        if not secili:
            self.log_ekle("❌ Lütfen bir grup seçin!")
            logger.warning("Başlatma iptal: grup seçilmemiş")
            return

        # UI güncelle
        self.is_running = True
        self.stop_requested = False
        self.aktif_grup = secili  # Aktif grubu sakla
        self.ardisik_basarisiz_deneme = 0  # Yeni başlatmada sayacı sıfırla

        # İlk kez başlatılıyorsa sıfırla, duraklatılmışsa devam et
        if not self.oturum_duraklatildi:
            self.oturum_recete = 0
            self.oturum_takip = 0
            self.oturum_takipli_recete = 0
            self.oturum_sure_toplam = 0.0
            self.son_recete_sureleri = []  # Son 5 reçete sürelerini sıfırla

            # ✅ YENİ: BİTTİ bilgisini temizle (yeni işlem başlıyor)
            self.grup_durumu.bitti_bilgisi_temizle(secili)
            self.root.after(0, lambda g=secili: self.bitti_bilgisi_guncelle(g))  # GUI'yi güncelle

            # Yeni oturum başlat (database + log dosyası)
            son_recete = self.grup_durumu.son_recete_al(secili)
            self.aktif_oturum_id = self.database.yeni_oturum_baslat(secili, son_recete)
            self.session_logger = SessionLogger(self.aktif_oturum_id, secili)
            self.log_ekle(f"📝 Yeni oturum başlatıldı (ID: {self.aktif_oturum_id})")
            self.session_logger.info(f"Grup {secili} için yeni oturum başlatıldı")

        self.oturum_baslangic = time.time()
        self.oturum_duraklatildi = False

        self.start_button.config(state="disabled", bg="#616161")
        self.stop_button.config(state="normal", bg="#D32F2F", fg="white")
        self.status_label.config(text="Çalışıyor...", bg="#FFEB3B", fg="#F57F17")

        self.log_ekle(f"▶ Grup {secili} başlatıldı")

        # Süre sayacını başlat
        self.start_stats_timer()

        # Thread başlat
        self.automation_thread = threading.Thread(target=self.otomasyonu_calistir, args=(secili,))
        self.automation_thread.daemon = True
        self.automation_thread.start()

    def tumu_kontrol_et(self):
        """HEPSİNİ KONTROL ET butonuna basıldığında (A→B→C sırayla)"""
        logger.info("tumu_kontrol_et() çağrıldı")

        # Çalışıyorsa engelle
        if self.is_running:
            self.log_ekle("❌ Sistem zaten çalışıyor! Önce durdurun.")
            logger.warning("Tümünü kontrol iptal: is_running=True")
            return

        # ✅ YENİ: Hafızayı SİLME! Sadece aktif modu ayarla
        self.grup_durumu.aktif_mod_ayarla("tumunu_kontrol")
        logger.info("Aktif mod: tumunu_kontrol")

        # Tümünü kontrol modunu aktif et
        self.tumu_kontrol_aktif = True
        self.tumu_kontrol_mevcut_index = 0  # A grubundan başla

        # A grubunu seç
        ilk_grup = self.tumu_kontrol_grup_sirasi[0]  # "A"
        self.secili_grup.set(ilk_grup)
        self.grup_buttons[ilk_grup].invoke()  # Radio button'ı seç

        self.log_ekle(f"🚀 TÜMÜNÜ KONTROL ET BAŞLATILDI: A → B → C")
        self.log_ekle(f"📍 Başlangıç: Grup {ilk_grup} (kaldığı yerden devam)")

        # NOT: basla() çağırmaya gerek yok, çünkü grup_buttons[ilk_grup].invoke()
        # zaten grup_secildi() → ilk_recete_akisi() → basla() akışını tetikliyor

    def durdur(self):
        """Durdur butonuna basıldığında"""
        if not self.is_running:
            return

        # Süreyi kaydet
        if self.oturum_baslangic:
            self.oturum_sure_toplam += (time.time() - self.oturum_baslangic)
            self.oturum_baslangic = None

        self.oturum_duraklatildi = True
        self.stop_requested = True
        self.aktif_grup = None  # Manuel durdurma - otomatik başlatmayı engelle
        self.tumu_kontrol_aktif = False  # Tümünü kontrol modunu iptal et
        self.stop_button.config(state="disabled", bg="#616161")
        self.status_label.config(text="Durduruluyor...", bg="#FFF9C4", fg="#F9A825")
        self.log_ekle("⏸ Durdurma isteği gönderildi")

        # Süre sayacını durdur
        self.stats_timer_running = False

    def otomatik_yeniden_baslat(self):
        """
        Gelişmiş otomatik yeniden başlatma: Ana Sayfa → Taskkill → Yeniden aç → Login

        Returns:
            bool: Başarılıysa True, başarısızsa False
        """
        try:
            if not self.aktif_grup:
                logger.warning("Aktif grup bulunamadı, yeniden başlatma iptal")
                self.root.after(0, self.reset_ui)
                return False

            # Sayacı artır ve güncelle
            self.yeniden_baslatma_sayaci += 1
            self.root.after(0, lambda: self.restart_label.config(
                text=f"Program {self.yeniden_baslatma_sayaci} kez yeniden başlatıldı"
            ))

            # Database'e kaydet
            if self.aktif_oturum_id:
                self.database.artir(self.aktif_oturum_id, "yeniden_baslatma_sayisi")
                if self.session_logger:
                    self.session_logger.info(f"Yeniden başlatma #{self.yeniden_baslatma_sayaci}")

            self.root.after(0, lambda: self.log_ekle(f"🔄 Otomatik yeniden başlatma #{self.yeniden_baslatma_sayaci}: Grup {self.aktif_grup}"))

            # 1. Adım: 3 sefer "Ana Sayfa" butonuna bas
            self.root.after(0, lambda: self.log_ekle("📍 1. Deneme: Ana Sayfa butonuna basılıyor..."))
            baglanti_basarili = False

            try:
                from pywinauto import Desktop
                desktop = Desktop(backend="uia")

                for deneme in range(1, 4):
                    try:
                        # Ana Sayfa butonunu bul
                        medula_window = desktop.window(title_re=".*MEDULA.*")
                        ana_sayfa_btn = medula_window.child_window(title="Ana Sayfa", control_type="Button")

                        if ana_sayfa_btn.exists(timeout=2):
                            ana_sayfa_btn.click()
                            self.root.after(0, lambda d=deneme: self.log_ekle(f"✓ Ana Sayfa butonu tıklandı ({d}/3)"))
                            time.sleep(1)

                            # Bağlantıyı kontrol et
                            if self.bot and self.bot.baglanti_kur("MEDULA", ilk_baglanti=False):
                                baglanti_basarili = True
                                self.root.after(0, lambda: self.log_ekle("✓ Bağlantı yeniden kuruldu!"))
                                break
                        else:
                            self.root.after(0, lambda d=deneme: self.log_ekle(f"⚠ Ana Sayfa butonu bulunamadı ({d}/3)"))
                    except Exception as e:
                        self.root.after(0, lambda d=deneme, err=str(e): self.log_ekle(f"⚠ Deneme {d}/3 başarısız: {err}"))

                    if deneme < 3:
                        time.sleep(1)
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ MEDULA penceresi bulunamadı: {err}"))

            # 2. Adım: Bağlantı kurulamadıysa taskkill → yeniden aç → login (5 kere dene)
            if not baglanti_basarili:
                self.root.after(0, lambda: self.log_ekle("⚠ 3 deneme başarısız, MEDULA yeniden açılıyor (5 deneme)..."))

                MAX_DENEME = 5
                yeniden_acma_basarili = False

                for deneme in range(1, MAX_DENEME + 1):
                    self.root.after(0, lambda d=deneme: self.log_ekle(f"🔄 Yeniden açma denemesi {d}/{MAX_DENEME}"))

                    # Taskkill
                    self.root.after(0, lambda: self.log_ekle("📍 MEDULA kapatılıyor (taskkill)..."))
                    if medula_taskkill():
                        self.taskkill_sayaci += 1
                        self.root.after(0, lambda: self.log_ekle(f"✓ MEDULA kapatıldı (Taskkill: {self.taskkill_sayaci})"))

                        # Database'e kaydet
                        if self.aktif_oturum_id:
                            self.database.artir(self.aktif_oturum_id, "taskkill_sayisi")
                            if self.session_logger:
                                self.session_logger.warning(f"Taskkill yapıldı (#{self.taskkill_sayaci})")
                    else:
                        self.root.after(0, lambda: self.log_ekle("⚠ Taskkill başarısız, devam ediliyor..."))

                    # Taskkill sonrası ek bekleme (taskkill fonksiyonu içinde 5 sn bekliyor, buradan ek 2 sn)
                    time.sleep(2)

                    # MEDULA'yı aç ve giriş yap
                    self.root.after(0, lambda: self.log_ekle("📍 MEDULA açılıyor ve giriş yapılıyor..."))
                    try:
                        if medula_ac_ve_giris_yap(self.medula_settings):
                            self.root.after(0, lambda: self.log_ekle("✓ MEDULA açıldı ve giriş yapıldı"))
                            time.sleep(5)  # Botanik kendi CAPTCHA'yı çözüyor, bekleme süresi

                            # Bot'a yeniden bağlan
                            if not self.bot:
                                self.bot = BotanikBot()

                            if self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))
                                yeniden_acma_basarili = True
                                break  # Başarılı, döngüden çık
                            else:
                                self.root.after(0, lambda: self.log_ekle("⚠ MEDULA'ya bağlanılamadı, yeniden denenecek..."))
                        else:
                            self.root.after(0, lambda: self.log_ekle("⚠ MEDULA açılamadı veya giriş yapılamadı, yeniden denenecek..."))
                    except Exception as e:
                        self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ MEDULA açma/giriş hatası: {err}"))

                    # Son deneme değilse biraz bekle
                    if deneme < MAX_DENEME:
                        self.root.after(0, lambda: self.log_ekle("⏳ 3 saniye bekleniyor..."))
                        time.sleep(3)

                # 5 deneme sonucu kontrol et
                if not yeniden_acma_basarili:
                    self.root.after(0, lambda: self.log_ekle("❌ 5 deneme de başarısız oldu!"))
                    return False  # Başarısız

            # 3. Adım: GUI'deki grup butonuna bas
            self.root.after(0, lambda: self.log_ekle(f"📍 Grup {self.aktif_grup} seçiliyor..."))
            time.sleep(1)

            # Grup butonunu bul ve tıkla
            if self.aktif_grup in self.grup_buttons:
                self.grup_buttons[self.aktif_grup].invoke()
                self.root.after(0, lambda: self.log_ekle(f"✓ Grup {self.aktif_grup} seçildi"))
            else:
                self.root.after(0, lambda: self.log_ekle(f"⚠ Grup {self.aktif_grup} butonu bulunamadı"))
                return False  # Başarısız

            time.sleep(1)

            # 4. Adım: SON REÇETEYE GİT (Kaldığı yerden devam)
            son_recete = self.grup_durumu.son_recete_al(self.aktif_grup)
            if son_recete:
                self.root.after(0, lambda: self.log_ekle(f"📍 Son reçeteye gidiliyor: {son_recete}"))
                try:
                    # Reçete Sorgu'ya git
                    if self.bot.recete_sorgu_ac():
                        self.root.after(0, lambda: self.log_ekle("✓ Reçete Sorgu açıldı"))
                        time.sleep(1)

                        # Reçete numarasını yaz
                        if self.bot.recete_no_yaz(son_recete):
                            self.root.after(0, lambda: self.log_ekle(f"✓ Reçete No yazıldı: {son_recete}"))
                            time.sleep(0.5)

                            # Sorgula butonuna bas
                            if self.bot.sorgula_butonuna_tikla():
                                self.root.after(0, lambda: self.log_ekle("✓ Sorgula butonuna basıldı"))
                                time.sleep(2)  # Reçetenin açılmasını bekle

                                self.root.after(0, lambda: self.log_ekle(f"✅ Kaldığı yerden devam ediliyor: {son_recete}"))

                                # 5. Adım: Başlat butonuna bas (devam için)
                                self.root.after(0, lambda: self.log_ekle("📍 Başlat butonuna basılıyor..."))
                                time.sleep(1)
                                self.root.after(0, self.basla)
                                self.root.after(0, lambda: self.log_ekle("✓ Otomatik yeniden başlatıldı (kaldığı yerden devam)"))

                                # Başarılı yeniden başlatma - sayacı sıfırla
                                self.ardisik_basarisiz_deneme = 0
                                return True  # Başarılı
                            else:
                                self.root.after(0, lambda: self.log_ekle("⚠ Sorgula butonuna basılamadı"))
                        else:
                            self.root.after(0, lambda: self.log_ekle("⚠ Reçete No yazılamadı"))
                    else:
                        self.root.after(0, lambda: self.log_ekle("⚠ Reçete Sorgu açılamadı"))
                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ Reçete bulma hatası: {err}"))
                    logger.error(f"Reçete bulma hatası: {e}", exc_info=True)

                # Reçete bulunamazsa normal başlat
                self.root.after(0, lambda: self.log_ekle("⚠ Son reçete bulunamadı, gruptan başlatılıyor"))

            # 5. Adım: Başlat butonuna bas (normal başlatma veya fallback)
            self.root.after(0, lambda: self.log_ekle("📍 Başlat butonuna basılıyor..."))
            time.sleep(1)
            self.root.after(0, self.basla)
            self.root.after(0, lambda: self.log_ekle("✓ Otomatik yeniden başlatıldı"))

            # Başarılı yeniden başlatma - sayacı sıfırla
            self.ardisik_basarisiz_deneme = 0
            return True  # Başarılı

        except Exception as e:
            logger.error(f"Otomatik yeniden başlatma hatası: {e}", exc_info=True)
            self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Yeniden başlatma hatası: {err}"))
            return False  # Başarısız

    def otomasyonu_calistir(self, grup):
        """Ana otomasyon döngüsü"""
        try:
            # Bot yoksa oluştur ve bağlan
            if self.bot is None:
                self.bot = BotanikBot()
                if not self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA'ya bağlanılamadı"))
                    self.root.after(0, self.hata_sesi_calar)
                    return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))
            else:
                # Bot zaten var, pencereyi yenile
                self.bot.baglanti_kur("MEDULA", ilk_baglanti=False)

            # Reçete zaten açık (grup seçiminde açıldı)
            self.root.after(0, lambda: self.log_ekle("▶ Reçete takibi başlıyor..."))

            time.sleep(0.75)  # Güvenli hasta takibi için: 0.5 → 0.75

            # Reçete döngüsü
            recete_sira = 1
            oturum_sure_toplam = 0.0

            try:
                while not self.stop_requested:
                    recete_baslangic = time.time()

                    self.root.after(0, lambda r=recete_sira: self.log_ekle(f"📋 Reçete {r} işleniyor..."))

                    # Popup kontrolü (reçete açılmadan önce)
                    try:
                        if popup_kontrol_ve_kapat():
                            self.root.after(0, lambda: self.log_ekle("✓ Popup kapatıldı"))
                            if self.session_logger:
                                self.session_logger.info("Popup tespit edilip kapatıldı")
                    except Exception as e:
                        logger.warning(f"Popup kontrol hatası: {e}")

                    # Reçete numarasını oku
                    medula_recete_no = self.bot.recete_no_oku()
                    if medula_recete_no:
                        # Grup label'ını güncelle
                        self.root.after(0, lambda no=medula_recete_no: self.grup_labels[grup].config(text=no))
                        # Hafızaya kaydet
                        self.grup_durumu.son_recete_guncelle(grup, medula_recete_no)
                        self.root.after(0, lambda no=medula_recete_no: self.log_ekle(f"🏷 No: {no}"))

                    # Görev tamamlandı mı kontrol et (reçete bulunamadı mesajı)
                    try:
                        if recete_kaydi_bulunamadi_mi(self.bot):
                            self.root.after(0, lambda: self.log_ekle("🎯 Görev tamamlandı! 'Reçete kaydı bulunamadı' mesajı tespit edildi"))

                            # ✅ YENİ: Popup'ı kapat (grup geçişinden önce!)
                            try:
                                logger.info("🔄 Görev tamamlama popup'ı kapatılıyor...")
                                popup_kapatildi = popup_kontrol_ve_kapat()
                                if popup_kapatildi:
                                    self.root.after(0, lambda: self.log_ekle("✓ Popup kapatıldı"))
                                    logger.info("✓ Popup başarıyla kapatıldı")
                                time.sleep(0.5)  # Popup'ın tamamen kapanması için bekle
                            except Exception as popup_err:
                                logger.warning(f"Popup kapatma hatası (devam ediliyor): {popup_err}")

                            if self.session_logger:
                                self.session_logger.basari("Görev başarıyla tamamlandı")

                            # ✅ YENİ: BİTTİ bilgisini kaydet
                            from datetime import datetime
                            bugun = datetime.now().strftime("%Y-%m-%d")
                            self.grup_durumu.bitti_bilgisi_ayarla(grup, bugun, self.oturum_recete)
                            self.root.after(0, lambda g=grup: self.bitti_bilgisi_guncelle(g))  # GUI'yi güncelle
                            logger.info(f"✅ Grup {grup} BİTTİ: {bugun}, {self.oturum_recete} reçete")

                            # Database'i güncelle ve oturumu bitir
                            if self.aktif_oturum_id:
                                ortalama_sure = oturum_sure_toplam / self.oturum_recete if self.oturum_recete > 0 else 0
                                self.database.oturum_guncelle(
                                    self.aktif_oturum_id,
                                    toplam_recete=self.oturum_recete,
                                    toplam_takip=self.oturum_takip,
                                    ortalama_recete_suresi=ortalama_sure
                                )
                                son_recete = self.grup_durumu.son_recete_al(grup)
                                self.database.oturum_bitir(self.aktif_oturum_id, bitis_recete=son_recete)

                                if self.session_logger:
                                    self.session_logger.ozet_yaz(
                                        self.oturum_recete,
                                        self.oturum_takip,
                                        ortalama_sure,
                                        self.yeniden_baslatma_sayaci,
                                        self.taskkill_sayaci
                                    )
                                    self.session_logger.kapat()

                            # TÜMÜNÜ KONTROL ET modu kontrolü
                            if self.tumu_kontrol_aktif:
                                # Mevcut grubu tamamlandı, sonrakine geç
                                self.tumu_kontrol_mevcut_index += 1

                                if self.tumu_kontrol_mevcut_index < len(self.tumu_kontrol_grup_sirasi):
                                    # Sonraki grup var
                                    sonraki_grup = self.tumu_kontrol_grup_sirasi[self.tumu_kontrol_mevcut_index]
                                    self.root.after(0, lambda g=grup, sg=sonraki_grup:
                                        self.log_ekle(f"✅ Grup {g} tamamlandı! → Sıradaki: Grup {sg}"))

                                    # Oturumu bitir (mevcut grup için)
                                    if self.session_logger:
                                        self.session_logger.ozet_yaz(
                                            self.oturum_recete,
                                            self.oturum_takip,
                                            ortalama_sure,
                                            self.yeniden_baslatma_sayaci,
                                            self.taskkill_sayaci
                                        )
                                        self.session_logger.kapat()
                                        self.session_logger = None

                                    # Sonraki gruba geçiş işlemi
                                    def sonraki_gruba_gec():
                                        try:
                                            self.root.after(0, lambda sg=sonraki_grup: self.log_ekle(f"🔄 {sg} grubuna geçiliyor..."))
                                            logger.info(f"🔄 Sonraki gruba geçiliyor: {sonraki_grup}")

                                            # Grup geçiş işlemini yap (Geri Dön → Dönem → Grup → İlk reçete)
                                            if sonraki_gruba_gec_islemi(self.bot, sonraki_grup):
                                                self.root.after(0, lambda sg=sonraki_grup: self.log_ekle(f"✅ {sg} grubuna geçildi"))

                                                # UI durumunu güncelle
                                                self.is_running = False
                                                self.oturum_duraklatildi = False
                                                self.secili_grup.set(sonraki_grup)
                                                self.aktif_grup = sonraki_grup

                                                # Yeni oturum başlat
                                                self.oturum_recete = 0
                                                self.oturum_takip = 0
                                                self.oturum_takipli_recete = 0
                                                self.oturum_sure_toplam = 0.0
                                                self.son_recete_sureleri = []

                                                # Database ve logger
                                                son_recete = self.grup_durumu.son_recete_al(sonraki_grup)
                                                self.aktif_oturum_id = self.database.yeni_oturum_baslat(sonraki_grup, son_recete)
                                                self.session_logger = SessionLogger(self.aktif_oturum_id, sonraki_grup)
                                                self.root.after(0, lambda: self.log_ekle(f"📝 Yeni oturum başlatıldı (ID: {self.aktif_oturum_id})"))

                                                # Grup rengini güncelle
                                                for g in ["A", "B", "C"]:
                                                    if g in self.grup_frames:
                                                        bg_color = "#BBDEFB" if g == sonraki_grup else "#E8F5E9"
                                                        self.grup_frames[g]['main'].config(bg=bg_color)
                                                        for widget in self.grup_frames[g]['widgets']:
                                                            try:
                                                                widget.config(bg=bg_color)
                                                            except:
                                                                pass

                                                # İşleme başla
                                                self.root.after(500, lambda: self.basla())
                                            else:
                                                raise Exception("Grup geçişi başarısız")

                                        except Exception as e:
                                            # Hata - taskkill + yeniden başlat
                                            logger.error(f"Grup geçişi hatası: {e}")
                                            self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Grup geçişi hatası: {err}"))
                                            self.root.after(0, lambda: self.log_ekle("🔄 MEDULA yeniden başlatılıyor..."))

                                            # Taskkill
                                            if medula_taskkill():
                                                self.root.after(0, lambda: self.log_ekle("✓ MEDULA kapatıldı"))
                                                self.taskkill_sayaci += 1
                                                time.sleep(3)
                                            else:
                                                self.root.after(0, lambda: self.log_ekle("⚠ Taskkill başarısız"))

                                            # Yeniden başlat ve giriş yap
                                            if medula_yeniden_baslat_ve_giris_yap(self.bot):
                                                self.root.after(0, lambda: self.log_ekle("✅ MEDULA yeniden başlatıldı"))
                                                self.yeniden_baslatma_sayaci += 1

                                                # Sonraki gruba tekrar geç
                                                self.root.after(0, lambda: self.log_ekle(f"🔄 {sonraki_grup} grubuna tekrar geçiliyor..."))
                                                try:
                                                    if sonraki_gruba_gec_islemi(self.bot, sonraki_grup):
                                                        self.root.after(0, lambda sg=sonraki_grup: self.log_ekle(f"✅ {sg} grubuna geçildi"))
                                                        # UI güncelle ve başlat
                                                        self.is_running = False
                                                        self.oturum_duraklatildi = False
                                                        self.secili_grup.set(sonraki_grup)
                                                        self.aktif_grup = sonraki_grup
                                                        self.oturum_recete = 0
                                                        self.oturum_takip = 0
                                                        self.oturum_takipli_recete = 0
                                                        self.oturum_sure_toplam = 0.0
                                                        self.son_recete_sureleri = []
                                                        son_recete = self.grup_durumu.son_recete_al(sonraki_grup)
                                                        self.aktif_oturum_id = self.database.yeni_oturum_baslat(sonraki_grup, son_recete)
                                                        self.session_logger = SessionLogger(self.aktif_oturum_id, sonraki_grup)
                                                        self.root.after(500, lambda: self.basla())
                                                    else:
                                                        raise Exception("2. deneme de başarısız")
                                                except Exception as e2:
                                                    logger.error(f"2. deneme de başarısız: {e2}")
                                                    self.root.after(0, lambda: self.log_ekle("❌ Grup geçişi 2. deneme de başarısız!"))
                                                    self.root.after(0, self.reset_ui)
                                            else:
                                                self.root.after(0, lambda: self.log_ekle("❌ MEDULA yeniden başlatılamadı!"))
                                                self.root.after(0, self.reset_ui)

                                    self.root.after(0, sonraki_gruba_gec)

                                    break  # Mevcut grup thread'ini bitir
                                else:
                                    # Tüm gruplar tamamlandı
                                    self.tumu_kontrol_aktif = False
                                    self.root.after(0, lambda: self.log_ekle("🎉 TÜMÜ TAMAMLANDI! A, B, C gruplarının hepsi kontrol edildi."))
                                    self.root.after(0, lambda: self.gorev_tamamlandi_raporu(grup, self.oturum_recete, self.oturum_takip))
                                    break
                            else:
                                # Normal mod - sadece raporu göster
                                self.root.after(0, lambda: self.gorev_tamamlandi_raporu(grup, self.oturum_recete, self.oturum_takip))
                                break
                    except Exception as e:
                        logger.warning(f"Görev tamamlama kontrolü hatası: {e}")

                    # Tek reçete işle
                    try:
                        basari, medula_no, takip_adet, hata_nedeni = tek_recete_isle(self.bot, recete_sira, self.rapor_takip)
                    except SistemselHataException as e:
                        # ✅ Sistemsel hata yakalandı!
                        self.root.after(0, lambda: self.log_ekle("⚠️ SİSTEMSEL HATA TESPİT EDİLDİ!"))
                        logger.error(f"Sistemsel hata: {e}")

                        # MEDULA'yı yeniden başlat
                        self.root.after(0, lambda: self.log_ekle("🔄 MEDULA yeniden başlatılıyor..."))
                        if medula_yeniden_baslat_ve_giris_yap(self.bot):
                            self.root.after(0, lambda: self.log_ekle("✅ MEDULA başarıyla yeniden başlatıldı"))

                            # Aktif modu kontrol et ve devam et
                            aktif_mod = self.grup_durumu.aktif_mod_al()
                            self.root.after(0, lambda m=aktif_mod: self.log_ekle(f"📍 Aktif mod: {m}"))

                            if aktif_mod == "tumunu_kontrol":
                                # Tümünü kontrol et modunu yeniden aktif et
                                self.tumu_kontrol_aktif = True
                                self.root.after(0, lambda: self.log_ekle("🔄 Tümünü kontrol et modu devam ediyor..."))

                            # Kaldığı yerden devam et (reçete zaten açık, işlemi tekrarla)
                            continue
                        else:
                            self.root.after(0, lambda: self.log_ekle("❌ MEDULA yeniden başlatılamadı!"))
                            break

                    # Popup kontrolü (reçete işlendikten sonra)
                    try:
                        if popup_kontrol_ve_kapat():
                            self.root.after(0, lambda: self.log_ekle("✓ Popup kapatıldı"))
                            if self.session_logger:
                                self.session_logger.info("Popup tespit edilip kapatıldı")
                    except Exception as e:
                        logger.warning(f"Popup kontrol hatası: {e}")

                    recete_sure = time.time() - recete_baslangic
                    oturum_sure_toplam += recete_sure

                    if basari:
                        self.oturum_recete += 1
                        self.oturum_takip += takip_adet

                        # Takipli ilaç varsa takipli reçete sayacını artır
                        if takip_adet > 0:
                            self.oturum_takipli_recete += 1

                        # Son 5 reçete süresini sakla
                        self.son_recete_sureleri.append(recete_sure)
                        if len(self.son_recete_sureleri) > 5:
                            self.son_recete_sureleri.pop(0)  # En eskiyi sil

                        # Süreyi formatla (saniye.milisaniye)
                        sure_sn = int(recete_sure)
                        sure_ms = int((recete_sure * 1000) % 1000)

                        self.root.after(0, lambda r=recete_sira, t=takip_adet, s=sure_sn, ms=sure_ms:
                                       self.log_ekle(f"✅ Reçete {r} | {t} ilaç takip | {s}.{ms:03d}s"))

                        # İstatistikleri güncelle
                        takipli_recete = 1 if takip_adet > 0 else 0
                        self.grup_durumu.istatistik_guncelle(grup, 1, takip_adet, takipli_recete, recete_sure)

                        # Aylık istatistik labelını güncelle
                        self.root.after(0, lambda g=grup: self.aylik_istatistik_guncelle(g))

                        # Database'e kaydet (her reçete sonrası)
                        if self.aktif_oturum_id:
                            ortalama_sure = oturum_sure_toplam / self.oturum_recete if self.oturum_recete > 0 else 0
                            self.database.oturum_guncelle(
                                self.aktif_oturum_id,
                                toplam_recete=self.oturum_recete,
                                toplam_takip=self.oturum_takip,
                                ortalama_recete_suresi=ortalama_sure
                            )

                        recete_sira += 1
                    else:
                        # Hata nedenini loga yaz
                        if hata_nedeni:
                            self.root.after(0, lambda h=hata_nedeni: self.log_ekle(f"❌ Program Durdu: {h}"))
                        else:
                            self.root.after(0, lambda: self.log_ekle("⚠ Reçete işlenemedi veya son reçete"))
                        break

                    if self.stop_requested:
                        break

            except SistemselHataException as e:
                # ✅ Döngü dışında sistemsel hata (genel catch)
                self.root.after(0, lambda: self.log_ekle("⚠️ SİSTEMSEL HATA (DÖNGÜ DIŞI)"))
                logger.error(f"Sistemsel hata (döngü dışı): {e}")
                # Yeniden başlatma zaten tek_recete_isle içinde yapılıyor
                pass

            # Normal sonlanma (son reçete veya break)
            # Görev sonu kontrolü
            gorev_tamamlandi = False
            try:
                # Global import kullan (local import kaldırıldı - scope hatası önlendi)
                if self.bot and recete_kaydi_bulunamadi_mi(self.bot):
                    gorev_tamamlandi = True
                    self.root.after(0, lambda: self.log_ekle("🎯 Görev tamamlandı! 'Reçete kaydı bulunamadı' mesajı tespit edildi"))
            except Exception as e:
                logger.warning(f"Görev tamamlama kontrolü hatası: {e}")

            # Otomatik yeniden başlatma kontrolü
            if self.aktif_grup and not self.stop_requested and not gorev_tamamlandi:
                # Hata veya beklenmeyen durma - otomatik yeniden başlat
                self.is_running = False
                self.ardisik_basarisiz_deneme += 1

                if self.ardisik_basarisiz_deneme >= 3:
                    self.root.after(0, lambda: self.log_ekle("❌ 3 DENEME BAŞARISIZ! Sistem durduruluyor..."))
                    self.root.after(0, lambda: messagebox.showerror(
                        "Yeniden Başlatma Başarısız",
                        f"3 deneme sonrası MEDULA yeniden başlatılamadı.\n\n"
                        f"Lütfen MEDULA'yı manuel olarak kontrol edin ve tekrar deneyin."
                    ))
                    self.root.after(0, self.reset_ui)
                    return

                self.root.after(0, lambda d=self.ardisik_basarisiz_deneme: self.log_ekle(f"⏳ 2 saniye sonra otomatik yeniden başlatılacak... (Deneme {d}/3)"))
                time.sleep(2)

                # Yeniden başlat
                def yeniden_baslat_ve_kontrol():
                    basarili = self.otomatik_yeniden_baslat()
                    if not basarili:
                        self.root.after(0, lambda: self.log_ekle(f"⚠ Yeniden başlatma başarısız (Deneme {self.ardisik_basarisiz_deneme}/3)"))

                recovery_thread = threading.Thread(target=yeniden_baslat_ve_kontrol)
                recovery_thread.daemon = True
                recovery_thread.start()
            else:
                # Manuel durdurma, aktif grup yok veya görev tamamlandı - UI'yi resetle
                self.root.after(0, self.reset_ui)

        except Exception as e:
            logger.error(f"Otomasyon hatası: {e}", exc_info=True)
            self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Hata: {err}"))
            self.root.after(0, self.hata_sesi_calar)

            # 1. ADIM: Görev sonu kontrolü (Reçete kaydı bulunamadı mesajı)
            gorev_tamamlandi = False
            try:
                # Global import kullan (local import kaldırıldı - scope hatası önlendi)
                if self.bot and recete_kaydi_bulunamadi_mi(self.bot):
                    gorev_tamamlandi = True
                    self.root.after(0, lambda: self.log_ekle("🎯 Görev tamamlandı! 'Reçete kaydı bulunamadı' mesajı tespit edildi"))
                    if self.session_logger:
                        self.session_logger.basari("Görev başarıyla tamamlandı (hata sonrası kontrol)")

                    # Database'i güncelle ve oturumu bitir
                    if self.aktif_oturum_id:
                        son_recete = self.grup_durumu.son_recete_al(grup) if grup else None
                        self.database.oturum_bitir(self.aktif_oturum_id, bitis_recete=son_recete)

                        if self.session_logger:
                            self.session_logger.ozet_yaz(
                                self.oturum_recete,
                                self.oturum_takip,
                                0.0,
                                self.yeniden_baslatma_sayaci,
                                self.taskkill_sayaci
                            )
                            self.session_logger.kapat()

                    # Görev tamamlama raporu göster
                    self.root.after(0, lambda: self.gorev_tamamlandi_raporu(grup, self.oturum_recete, self.oturum_takip))
                    self.root.after(0, self.reset_ui)
                    return
            except Exception as kontrol_hatasi:
                logger.warning(f"Görev tamamlama kontrolü hatası: {kontrol_hatasi}")

            # 2. ADIM: Görev sonu değilse, otomatik yeniden başlatma yap
            otomatik_baslatilacak = self.aktif_grup and not self.stop_requested and not gorev_tamamlandi

            if otomatik_baslatilacak:
                # Ardışık başarısız deneme sayısını kontrol et
                if self.ardisik_basarisiz_deneme >= 3:
                    self.root.after(0, lambda: self.log_ekle("❌ 3 DENEME BAŞARISIZ! Sistem durduruluyor..."))
                    self.root.after(0, lambda: messagebox.showerror(
                        "Yeniden Başlatma Başarısız",
                        f"3 deneme sonrası MEDULA yeniden başlatılamadı.\n\n"
                        f"Lütfen MEDULA'yı manuel olarak kontrol edin ve tekrar deneyin.\n\n"
                        f"Yeniden Başlatma: {self.yeniden_baslatma_sayaci}\n"
                        f"Taskkill: {self.taskkill_sayaci}"
                    ))

                    if self.session_logger:
                        self.session_logger.hata(f"3 deneme başarısız! Sistem durdu.")

                    # UI'yi resetle
                    self.root.after(0, self.reset_ui)
                    return

                # Otomatik yeniden başlatılacak
                self.is_running = False
                self.ardisik_basarisiz_deneme += 1
                self.root.after(0, lambda d=self.ardisik_basarisiz_deneme: self.log_ekle(f"⏳ 2 saniye sonra otomatik yeniden başlatılacak... (Deneme {d}/3)"))
                time.sleep(2)

                # Yeniden başlat ve sonucu kontrol et
                def yeniden_baslat_ve_kontrol():
                    basarili = self.otomatik_yeniden_baslat()
                    if not basarili:
                        # Başarısız oldu, tekrar kontrol edilecek (exception handler'a geri dönecek)
                        self.root.after(0, lambda: self.log_ekle(f"⚠ Yeniden başlatma başarısız (Deneme {self.ardisik_basarisiz_deneme}/3)"))
                        if self.ardisik_basarisiz_deneme < 3:
                            self.root.after(0, lambda: self.log_ekle("🔄 Yeniden denenecek..."))
                    # Başarılı ise `ardisik_basarisiz_deneme` zaten 0'lanmış

                recovery_thread = threading.Thread(target=yeniden_baslat_ve_kontrol)
                recovery_thread.daemon = True
                recovery_thread.start()
            else:
                # Manuel durdurma, aktif grup yok veya görev tamamlandı - UI'yi resetle
                self.root.after(0, self.reset_ui)

    def reset_ui(self):
        """UI'yi sıfırla"""
        self.is_running = False
        self.stop_requested = False
        self.aktif_grup = None  # Aktif grubu temizle
        self.tumu_kontrol_aktif = False  # Tümünü kontrol modunu sıfırla
        self.ardisik_basarisiz_deneme = 0  # Ardışık deneme sayacını sıfırla

        self.start_button.config(state="normal", bg="#388E3C", fg="white")
        self.stop_button.config(state="disabled", bg="#616161")
        self.status_label.config(text="Hazır", bg="#A5D6A7", fg="#1B5E20")

        # İstatistik timer'ını durdur
        self.stats_timer_running = False

        self.log_ekle("⏹ Durduruldu")

    def start_stats_timer(self):
        """İstatistik timer'ını başlat"""
        if not self.stats_timer_running:
            self.stats_timer_running = True
            self._stats_timer_tick()

    def _stats_timer_tick(self):
        """Stats timer tick"""
        if not self.stats_timer_running:
            return

        self.update_stats_display()
        self.root.after(200, self._stats_timer_tick)  # 200ms için daha akıcı milisaniye güncellemesi

    def update_stats_display(self):
        """İstatistikleri güncelle"""
        # Toplam süre = Daha önce biriken + Şu anki çalışma süresi
        sure_toplam = self.oturum_sure_toplam
        if self.oturum_baslangic:
            sure_toplam += (time.time() - self.oturum_baslangic)

        # Saniye ve milisaniye hesapla
        sure = int(sure_toplam)
        milisaniye = int((sure_toplam * 1000) % 1000)

        # Süre formatını oluştur (milisaniye ile)
        if sure >= 60:
            dk = sure // 60
            sn = sure % 60
            sure_text = f"{dk}dk {sn}s {milisaniye}ms"
        else:
            sure_text = f"{sure}s {milisaniye}ms"

        # Son 5 reçetenin ortalama süresini hesapla
        if len(self.son_recete_sureleri) > 0:
            ortalama_sure = sum(self.son_recete_sureleri) / len(self.son_recete_sureleri)
            ort_text = f"{ortalama_sure:.1f}s"
        else:
            ort_text = "-"

        text = f"Rç:{self.oturum_recete} | Takipli:{self.oturum_takipli_recete} | İlaç:{self.oturum_takip} | R:{self.rapor_takip.toplam_kayit} | Süre:{sure_text} | Ort(5):{ort_text}"
        self.stats_label.config(text=text)

    # captcha_devam_et fonksiyonu kaldırıldı - artık gerekli değil

    def gorev_tamamlandi_raporu(self, grup, toplam_recete, toplam_takip):
        """Görev tamamlandığında rapor göster"""
        try:
            from tkinter import messagebox

            # Oturum bilgilerini al
            ortalama_sure = 0
            if self.aktif_oturum_id:
                oturum = self.database.oturum_getir(self.aktif_oturum_id)
                if oturum:
                    ortalama_sure = oturum.get("ortalama_recete_suresi", 0)

            rapor = f"""
╔════════════════════════════════════════════╗
║          🎯 GÖREV TAMAMLANDI! 🎯          ║
╚════════════════════════════════════════════╝

✓ Grup: {grup}
✓ Toplam Reçete: {toplam_recete}
✓ Toplam Takip: {toplam_takip}
✓ Ortalama Süre: {ortalama_sure:.2f} saniye
✓ Yeniden Başlatma: {self.yeniden_baslatma_sayaci} kez
✓ Taskkill: {self.taskkill_sayaci} kez

Tüm reçeteler başarıyla işlendi!
            """

            messagebox.showinfo("Görev Tamamlandı", rapor)
            self.log_ekle("🎯 Görev tamamlama raporu gösterildi")

        except Exception as e:
            logger.error(f"Rapor gösterme hatası: {e}")

    def gorev_raporlari_goster(self):
        """Görev raporları penceresini aç"""
        try:
            from tkinter import Toplevel, ttk

            # Yeni pencere
            rapor_pencere = Toplevel(self.root)
            rapor_pencere.title("Görev Raporları")
            rapor_pencere.geometry("900x500")

            # Treeview (tablo)
            columns = ("ID", "Grup", "Başlangıç", "Bitiş", "Reçete", "Takip", "Y.Başlatma", "Taskkill", "Ort.Süre", "Durum")
            tree = ttk.Treeview(rapor_pencere, columns=columns, show="headings", height=20)

            # Başlıklar
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=90, anchor="center")

            # Scrollbar
            scrollbar = ttk.Scrollbar(rapor_pencere, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            # Verileri yükle
            oturumlar = self.database.tum_oturumlari_getir(limit=100)
            for oturum in oturumlar:
                tree.insert("", "end", values=(
                    oturum['id'],
                    oturum['grup'],
                    oturum['baslangic_zamani'],
                    oturum['bitis_zamani'] or "-",
                    oturum['toplam_recete'],
                    oturum['toplam_takip'],
                    oturum['yeniden_baslatma_sayisi'],
                    oturum['taskkill_sayisi'],
                    f"{oturum['ortalama_recete_suresi']:.2f}s",
                    oturum['durum']
                ))

            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            self.log_ekle("📊 Görev raporları açıldı")
        except Exception as e:
            logger.error(f"Görev raporları hatası: {e}", exc_info=True)
            self.log_ekle(f"❌ Raporlar açılamadı: {e}")

    def on_closing(self):
        """Pencere kapatma"""
        if self.is_running:
            self.durdur()
            if self.automation_thread and self.automation_thread.is_alive():
                self.automation_thread.join(timeout=2)

        # Aktif oturumu bitir
        if self.aktif_oturum_id:
            son_recete = self.grup_durumu.son_recete_al(self.aktif_grup) if self.aktif_grup else None
            self.database.oturum_bitir(self.aktif_oturum_id, son_recete)

            if self.session_logger:
                self.session_logger.ozet_yaz(
                    self.oturum_recete,
                    self.oturum_takip,
                    sum(self.son_recete_sureleri) / len(self.son_recete_sureleri) if self.son_recete_sureleri else 0,
                    self.yeniden_baslatma_sayaci,
                    self.taskkill_sayaci
                )
                self.session_logger.kapat()

        # Database bağlantısını kapat
        try:
            if self.database:
                self.database.kapat()
        except Exception as e:
            logger.error(f"Database kapatma hatası: {e}")

        self.stats_timer_running = False
        self.root.destroy()


def main():
    """Ana fonksiyon"""
    root = tk.Tk()
    app = BotanikGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
