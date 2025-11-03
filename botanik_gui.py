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
from botanik_bot import BotanikBot, tek_recete_isle
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
        self.dosya_yolu = Path(dosya_yolu)
        self.veriler = self.yukle()

    def yukle(self):
        """JSON dosyasından verileri yükle"""
        if self.dosya_yolu.exists():
            try:
                with open(self.dosya_yolu, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        # Varsayılan yapı
        return {
            "A": {"son_recete": "", "toplam_recete": 0, "toplam_takip": 0, "toplam_sure": 0.0},
            "B": {"son_recete": "", "toplam_recete": 0, "toplam_takip": 0, "toplam_sure": 0.0},
            "C": {"son_recete": "", "toplam_recete": 0, "toplam_takip": 0, "toplam_sure": 0.0}
        }

    def kaydet(self):
        """Verileri JSON dosyasına kaydet"""
        try:
            with open(self.dosya_yolu, 'w', encoding='utf-8') as f:
                json.dump(self.veriler, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Grup durumları kaydedilemedi: {e}")

    def son_recete_al(self, grup):
        """Grubun son reçete numarasını al"""
        return self.veriler.get(grup, {}).get("son_recete", "")

    def son_recete_guncelle(self, grup, recete_no):
        """Grubun son reçete numarasını güncelle"""
        if grup in self.veriler:
            self.veriler[grup]["son_recete"] = recete_no
            self.kaydet()

    def istatistik_guncelle(self, grup, recete_sayisi=0, takip_sayisi=0, sure=0.0):
        """Grup istatistiklerini güncelle"""
        if grup in self.veriler:
            self.veriler[grup]["toplam_recete"] += recete_sayisi
            self.veriler[grup]["toplam_takip"] += takip_sayisi
            self.veriler[grup]["toplam_sure"] += sure
            self.kaydet()

    def istatistik_al(self, grup):
        """Grup istatistiklerini al"""
        return self.veriler.get(grup, {})

    def grup_sifirla(self, grup):
        """Grubu sıfırla (ay sonu)"""
        if grup in self.veriler:
            self.veriler[grup] = {
                "son_recete": "",
                "toplam_recete": 0,
                "toplam_takip": 0,
                "toplam_sure": 0.0
            }
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

        # Bot
        self.bot = None
        self.automation_thread = None
        self.is_running = False
        self.stop_requested = False

        # Seçili grup
        self.secili_grup = tk.StringVar(value="")
        self.aktif_grup = None  # Şu anda çalışan grup (A/B/C)

        # Oturum istatistikleri
        self.oturum_recete = 0
        self.oturum_takip = 0
        self.oturum_baslangic = None
        self.oturum_sure_toplam = 0.0  # Toplam çalışma süresi (durdur/başlat arası)
        self.oturum_duraklatildi = False
        self.son_recete_sureleri = []  # Son 5 reçetenin süreleri (saniye)

        # Yeniden başlatma sayacı
        self.yeniden_baslatma_sayaci = 0
        self.taskkill_sayaci = 0  # Taskkill sayacı

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

        # CAPTCHA modu
        self.captcha_bekleniyor = False

        self.create_widgets()
        self.load_grup_verileri()

        # Başlangıç logu
        self.log_ekle("Beklemede...")

        # MEDULA'yı başlangıçta sol %80'e yerleştir
        self.root.after(800, self.medula_pencere_ayarla)

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

            # Maximize ise restore et
            try:
                placement = win32gui.GetWindowPlacement(medula_hwnd)
                if placement[1] == win32con.SW_SHOWMAXIMIZED:
                    win32gui.ShowWindow(medula_hwnd, win32con.SW_RESTORE)
                    time.sleep(0.3)  # Güvenli hasta takibi için: 0.2 → 0.3
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
                text="Ay: Reçete:0 | İlaç:0 | 0s 0ms",
                font=("Arial", 6),
                bg="#C8E6C9",
                fg="#1B5E20",
                anchor="w",
                padx=5,
                pady=1
            )
            stat_label.pack(fill="x")
            self.grup_stat_labels[grup] = stat_label

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

        # CAPTCHA Devam Et Butonu (başlangıçta gizli)
        self.captcha_button = tk.Button(
            buttons_frame,
            text="CAPTCHA Girdim\nDevam Et ▶",
            font=("Arial", 9, "bold"),
            bg="#FF9800",
            fg="white",
            activebackground="#F57C00",
            width=14,
            height=2,
            relief="raised",
            bd=2,
            command=self.captcha_devam_et
        )
        # Başlangıçta gizli

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
            text="Reçete:0 | İlaç:0 | Süre:0s 0ms | Ort(5):-",
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

    def aylik_istatistik_guncelle(self, grup):
        """Grubun aylık istatistiklerini label'a yaz"""
        stats = self.grup_durumu.istatistik_al(grup)
        recete_sayi = stats.get("toplam_recete", 0)
        takip_sayi = stats.get("toplam_takip", 0)
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

        text = f"Ay: Reçete:{recete_sayi} | İlaç:{takip_sayi} | {sure_text}"
        self.grup_stat_labels[grup].config(text=text)

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
            # İlk reçete
            self.log_ekle(f"ℹ İlk reçete - Elle açın")

    def recete_ac(self, grup, recete_no):
        """Reçeteyi otomatik aç (thread'de çalışır)"""
        try:
            # Bot yoksa oluştur ve bağlan
            if self.bot is None:
                self.bot = BotanikBot()
                if not self.bot.baglanti_kur("MEDULA", ilk_baglanti=True):
                    self.root.after(0, lambda: self.log_ekle("❌ MEDULA'ya bağlanılamadı"))
                    return

                self.root.after(0, lambda: self.log_ekle("✓ MEDULA'ya bağlandı"))

            # Önce Reçete Sorgu'ya tıklamayı dene
            self.root.after(0, lambda: self.log_ekle("🔘 Reçete Sorgu..."))
            recete_sorgu_acildi = self.bot.recete_sorgu_ac()

            if not recete_sorgu_acildi:
                # Açılmadıysa Ana Sayfa'ya dön ve tekrar dene
                self.root.after(0, lambda: self.log_ekle("🏠 Ana Sayfa..."))
                if self.bot.ana_sayfaya_don():
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

            self.root.after(0, lambda: self.log_ekle(f"✅ Reçete açıldı: {recete_no}"))
            self.root.after(0, lambda: self.log_ekle("▶ BAŞLAT'a basın"))

        except Exception as e:
            logger.error(f"Reçete açma hatası: {e}")
            self.root.after(0, lambda: self.log_ekle(f"❌ Hata: {e}"))

    def grup_sifirla(self, grup):
        """X butonuna basıldığında grubu sıfırla"""
        self.grup_durumu.grup_sifirla(grup)
        self.grup_labels[grup].config(text="—")
        self.aylik_istatistik_guncelle(grup)  # Aylık istatistiği de güncelle
        self.log_ekle(f"Grup {grup} sıfırlandı")
        logger.info(f"Grup {grup} sıfırlandı")

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
        """Ayarlar sekmesi içeriğini oluştur"""
        # Ana frame
        main_frame = tk.Frame(parent, bg='#E8F5E9')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Başlık
        title = tk.Label(
            main_frame,
            text="⏱ Zamanlama Ayarları",
            font=("Arial", 12, "bold"),
            bg='#E8F5E9',
            fg='#1B5E20'
        )
        title.pack(pady=(0, 5))

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

        # Scrollable canvas
        canvas = tk.Canvas(main_frame, bg='#E8F5E9', highlightthickness=0)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#E8F5E9')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

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
                    font=("Arial", 5),
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

        # İlk kez başlatılıyorsa sıfırla, duraklatılmışsa devam et
        if not self.oturum_duraklatildi:
            self.oturum_recete = 0
            self.oturum_takip = 0
            self.oturum_sure_toplam = 0.0
            self.son_recete_sureleri = []  # Son 5 reçete sürelerini sıfırla

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
        self.stop_button.config(state="disabled", bg="#616161")
        self.status_label.config(text="Durduruluyor...", bg="#FFF9C4", fg="#F9A825")
        self.log_ekle("⏸ Durdurma isteği gönderildi")

        # Süre sayacını durdur
        self.stats_timer_running = False

    def otomatik_yeniden_baslat(self):
        """Hata durumunda otomatik yeniden başlatma"""
        try:
            if not self.aktif_grup:
                logger.warning("Aktif grup bulunamadı, yeniden başlatma iptal")
                self.root.after(0, self.reset_ui)
                return

            # Sayacı artır ve güncelle
            self.yeniden_baslatma_sayaci += 1
            self.root.after(0, lambda: self.restart_label.config(
                text=f"Program {self.yeniden_baslatma_sayaci} kez yeniden başlatıldı"
            ))

            self.root.after(0, lambda: self.log_ekle(f"🔄 Otomatik yeniden başlatma #{self.yeniden_baslatma_sayaci}: Grup {self.aktif_grup}"))

            # 1. MEDULA Giriş butonuna 2 kere bas
            self.root.after(0, lambda: self.log_ekle("📍 MEDULA Giriş butonuna basılıyor..."))

            try:
                from pywinauto import Desktop
                desktop = Desktop(backend="uia")

                # Giriş butonunu bul ve bas (1. kez)
                try:
                    giris_btn = desktop.window(title_re=".*MEDULA.*").child_window(auto_id="btnMedulayaGirisYap", control_type="Button")
                    if giris_btn.exists():
                        giris_btn.click()
                        self.root.after(0, lambda: self.log_ekle("✓ Giriş butonu 1. tıklama"))
                        time.sleep(1)

                        # 2. kez bas
                        giris_btn.click()
                        self.root.after(0, lambda: self.log_ekle("✓ Giriş butonu 2. tıklama"))
                        time.sleep(1)
                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ Giriş butonu bulunamadı: {err}"))
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_ekle(f"⚠ MEDULA penceresi bulunamadı: {err}"))

            # 2. GUI'deki grup butonuna bas
            self.root.after(0, lambda: self.log_ekle(f"📍 Grup {self.aktif_grup} butonuna basılıyor..."))
            time.sleep(1)

            # Grup butonunu bul ve tıkla
            if self.aktif_grup in self.grup_buttons:
                self.grup_buttons[self.aktif_grup].invoke()
                self.root.after(0, lambda: self.log_ekle(f"✓ Grup {self.aktif_grup} seçildi"))
            else:
                self.root.after(0, lambda: self.log_ekle(f"⚠ Grup {self.aktif_grup} butonu bulunamadı"))
                self.root.after(0, self.reset_ui)
                return

            time.sleep(1)

            # 3. Başlat butonuna bas
            self.root.after(0, lambda: self.log_ekle("📍 Başlat butonuna basılıyor..."))
            self.root.after(0, lambda: logger.info(f"DEBUG: is_running={self.is_running}, aktif_grup={self.aktif_grup}"))
            time.sleep(1)
            self.root.after(0, self.basla)
            self.root.after(0, lambda: self.log_ekle("✓ Otomatik yeniden başlatıldı"))

        except Exception as e:
            logger.error(f"Otomatik yeniden başlatma hatası: {e}", exc_info=True)
            self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Yeniden başlatma hatası: {err}"))
            self.root.after(0, self.reset_ui)

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

            while not self.stop_requested:
                recete_baslangic = time.time()

                self.root.after(0, lambda r=recete_sira: self.log_ekle(f"📋 Reçete {r} işleniyor..."))

                # Reçete numarasını oku
                medula_recete_no = self.bot.recete_no_oku()
                if medula_recete_no:
                    # Grup label'ını güncelle
                    self.root.after(0, lambda no=medula_recete_no: self.grup_labels[grup].config(text=no))
                    # Hafızaya kaydet
                    self.grup_durumu.son_recete_guncelle(grup, medula_recete_no)
                    self.root.after(0, lambda no=medula_recete_no: self.log_ekle(f"🏷 No: {no}"))

                # Tek reçete işle
                basari, medula_no, takip_adet = tek_recete_isle(self.bot, recete_sira)

                recete_sure = time.time() - recete_baslangic
                oturum_sure_toplam += recete_sure

                if basari:
                    self.oturum_recete += 1
                    self.oturum_takip += takip_adet

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
                    self.grup_durumu.istatistik_guncelle(grup, 1, takip_adet, recete_sure)

                    # Aylık istatistik labelını güncelle
                    self.root.after(0, lambda g=grup: self.aylik_istatistik_guncelle(g))

                    recete_sira += 1
                else:
                    self.root.after(0, lambda: self.log_ekle("⚠ Reçete işlenemedi veya son reçete"))
                    break

                if self.stop_requested:
                    break

            # Normal sonlanma (son reçete veya break)
            # Otomatik yeniden başlatma kontrolü
            if self.aktif_grup and not self.stop_requested:
                # Hata veya beklenmeyen durma - otomatik yeniden başlat
                self.is_running = False
                self.root.after(0, lambda: self.log_ekle("⏳ 2 saniye sonra otomatik yeniden başlatılacak..."))
                time.sleep(2)

                # Yeni thread'de yeniden başlat
                recovery_thread = threading.Thread(target=self.otomatik_yeniden_baslat)
                recovery_thread.daemon = True
                recovery_thread.start()
            else:
                # Manuel durdurma veya aktif grup yok - UI'yi resetle
                self.root.after(0, self.reset_ui)

        except Exception as e:
            logger.error(f"Otomasyon hatası: {e}", exc_info=True)
            self.root.after(0, lambda err=str(e): self.log_ekle(f"❌ Hata: {err}"))
            self.root.after(0, self.hata_sesi_calar)

            # Otomatik yeniden başlatma yapılacak mı kontrol et
            otomatik_baslatilacak = self.aktif_grup and not self.stop_requested

            if otomatik_baslatilacak:
                # Otomatik yeniden başlatılacak - sadece flag temizle
                self.is_running = False
                self.root.after(0, lambda: self.log_ekle("⏳ 2 saniye sonra otomatik yeniden başlatılacak..."))
                time.sleep(2)

                # Yeni thread'de yeniden başlat
                recovery_thread = threading.Thread(target=self.otomatik_yeniden_baslat)
                recovery_thread.daemon = True
                recovery_thread.start()
            else:
                # Manuel durdurma veya aktif grup yok - UI'yi resetle
                self.root.after(0, self.reset_ui)

    def reset_ui(self):
        """UI'yi sıfırla"""
        self.is_running = False
        self.stop_requested = False
        self.aktif_grup = None  # Aktif grubu temizle

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

        text = f"Reçete:{self.oturum_recete} | İlaç:{self.oturum_takip} | Süre:{sure_text} | Ort(5):{ort_text}"
        self.stats_label.config(text=text)

    def captcha_devam_et(self):
        """CAPTCHA girildikten sonra devam et"""
        self.captcha_bekleniyor = False
        self.captcha_button.pack_forget()  # Butonu gizle
        self.log_ekle("✓ CAPTCHA girişi tamamlandı, devam ediliyor...")
        if self.session_logger:
            self.session_logger.info("CAPTCHA girişi kullanıcı tarafından tamamlandı")

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
