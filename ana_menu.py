"""
Botanik Bot - Ana Menü Penceresi
Tüm modüllere erişim sağlayan ana giriş ekranı
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import os
from datetime import datetime

from kullanici_yonetimi import get_kullanici_yonetimi, KullaniciYonetimi

# Tema yönetimi merkezi modül
try:
    from tema_yonetimi import get_tema, TEMALAR
    TEMA_YUKLENDI = True
except ImportError:
    TEMA_YUKLENDI = False
    # Fallback tema tanımları
    TEMALAR = {
        "koyu": {
            "ad": "Koyu Tema", "icon": "🌙",
            "bg": "#1E3A5F", "header_bg": "#0D2137", "card_bg": "#2C4A6E",
            "fg": "#FFFFFF", "fg_secondary": "#87CEEB", "border": "#3D5A80",
            "success": "#4CAF50", "warning": "#FF9800", "error": "#F44336",
        },
        "acik": {
            "ad": "Açık Tema", "icon": "☀️",
            "bg": "#F5F5F5", "header_bg": "#1976D2", "card_bg": "#FFFFFF",
            "fg": "#212121", "fg_secondary": "#757575", "border": "#E0E0E0",
            "success": "#388E3C", "warning": "#F57C00", "error": "#D32F2F",
        }
    }

logger = logging.getLogger(__name__)


class AnaMenu:
    """Ana menü penceresi - modüllere erişim"""

    # Modül tanımları (buton sırası, icon, renk)
    MODUL_TANIMLARI = {
        "ilac_takip": {
            "baslik": "İlaç Takip",
            "icon": "💊",
            "aciklama": "İlaç ve reçete takip sistemi",
            "renk": "#4CAF50",  # Yeşil
            "hover": "#388E3C"
        },
        "depo_ekstre": {
            "baslik": "Depo Ekstre",
            "icon": "📊",
            "aciklama": "Depo ekstre karşılaştırma",
            "renk": "#2196F3",  # Mavi
            "hover": "#1976D2"
        },
        "kasa_takip": {
            "baslik": "Kasa Takibi",
            "icon": "💰",
            "aciklama": "Günlük kasa takip sistemi",
            "renk": "#FF9800",  # Turuncu
            "hover": "#F57C00"
        },
        "rapor_kontrol": {
            "baslik": "Rapor Kontrol",
            "icon": "📋",
            "aciklama": "Ay sonu rapor kontrol modülü",
            "renk": "#9C27B0",  # Mor
            "hover": "#7B1FA2"
        },
        "t_cetvel": {
            "baslik": "T Cetvel / Bilanço",
            "icon": "📑",
            "aciklama": "T cetvel ve bilanço işlemleri",
            "renk": "#607D8B",  # Gri-mavi
            "hover": "#455A64"
        },
        "ek_raporlar": {
            "baslik": "Ek Raporlar",
            "icon": "📈",
            "aciklama": "Botanik ek raporlar menüsü",
            "renk": "#00BCD4",  # Cyan
            "hover": "#0097A7"
        },
        "mf_analiz": {
            "baslik": "MF Analiz",
            "icon": "🔬",
            "aciklama": "MF analiz simülatörü",
            "renk": "#795548",  # Kahverengi
            "hover": "#5D4037"
        },
        "mf_hizli": {
            "baslik": "MF Hızlı Hesap",
            "icon": "⚡",
            "aciklama": "NPV bazlı MF karlılık hesaplama",
            "renk": "#673AB7",  # Mor
            "hover": "#512DA8"
        },
        "kullanici_yonetimi": {
            "baslik": "Kullanıcı Yönetimi",
            "icon": "👥",
            "aciklama": "Kullanıcı ve yetki yönetimi",
            "renk": "#F44336",  # Kırmızı
            "hover": "#D32F2F"
        },
        "siparis_verme": {
            "baslik": "Sipariş Verme",
            "icon": "🛒",
            "aciklama": "Stok analizi ve sipariş hazırlama",
            "renk": "#009688",  # Teal
            "hover": "#00796B"
        },
        "min_stok_analiz": {
            "baslik": "Min Stok Analizi",
            "icon": "📊",
            "aciklama": "Bilimsel minimum stok hesaplama",
            "renk": "#E91E63",  # Pembe
            "hover": "#C2185B"
        },
        "stok_maliyet_analiz": {
            "baslik": "Stok Maliyet Analizi",
            "icon": "💰",
            "aciklama": "Geriye dönük stok fırsat maliyeti raporu",
            "renk": "#5D4037",  # Koyu Kahve
            "hover": "#4E342E"
        },
        "prim_raporlama": {
            "baslik": "Prim Raporlama",
            "icon": "🏆",
            "aciklama": "Personel prim raporlama ve analiz",
            "renk": "#FF6F00",  # Amber
            "hover": "#E65100"
        }
    }

    def __init__(self, kullanici):
        """
        Args:
            kullanici: Giriş yapan kullanıcı bilgileri (dict)
        """
        self.kullanici = kullanici
        self.kullanici_yonetimi = get_kullanici_yonetimi()
        self.yetkiler = self.kullanici_yonetimi.kullanici_yetkilerini_al(kullanici['id'])

        self.root = tk.Tk()
        self.root.title(f"Botanik Takip Sistemi - {kullanici.get('ad_soyad', kullanici['kullanici_adi'])}")

        # Pencere boyutları
        pencere_genislik = 900
        pencere_yukseklik = 750

        # Ekranın ortasına yerleştir
        ekran_genislik = self.root.winfo_screenwidth()
        ekran_yukseklik = self.root.winfo_screenheight()
        x = (ekran_genislik - pencere_genislik) // 2
        y = (ekran_yukseklik - pencere_yukseklik) // 2

        self.root.geometry(f"{pencere_genislik}x{pencere_yukseklik}+{x}+{y}")
        self.root.resizable(False, False)

        # Tema yükle
        if TEMA_YUKLENDI:
            tema_yonetici = get_tema()
            self.aktif_tema = tema_yonetici.aktif_tema
            tema_yonetici.ttk_stili_uygula()
        else:
            self.aktif_tema = "koyu"
        self._tema_uygula()

        # Pencere kapatılırsa
        self.root.protocol("WM_DELETE_WINDOW", self.cikis_yap)

        self.arayuz_olustur()

    def _tema_uygula(self):
        """Aktif temayı uygula"""
        tema = TEMALAR.get(self.aktif_tema, TEMALAR["koyu"])
        self.bg_color = tema["bg"]
        self.header_color = tema["header_bg"]
        self.fg_color = tema["fg"]
        self.card_bg = tema["card_bg"]
        self.fg_secondary = tema["fg_secondary"]
        self.root.configure(bg=self.bg_color)

    def tema_degistir(self):
        """Tema değiştir (toggle)"""
        # Mevcut temayı değiştir
        if TEMA_YUKLENDI:
            tema_yonetici = get_tema()
            self.aktif_tema = tema_yonetici.degistir()
        else:
            self.aktif_tema = "acik" if self.aktif_tema == "koyu" else "koyu"

        # Kullanıcıya bilgi ver ve yeniden başlatma öner
        tema = TEMALAR[self.aktif_tema]
        messagebox.showinfo(
            "Tema Değiştirildi",
            f"{tema['icon']} {tema['ad']} seçildi.\n\n"
            "Değişikliğin tam olarak uygulanması için\n"
            "programı yeniden başlatmanız önerilir."
        )

    def arayuz_olustur(self):
        """Ana menü arayüzünü oluştur"""
        # Header
        self.header_olustur()

        # Ana içerik
        self.icerik_olustur()

        # Footer
        self.footer_olustur()

    def header_olustur(self):
        """Üst başlık alanı"""
        header_frame = tk.Frame(self.root, bg=self.header_color, height=80)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        # Sol: Logo ve başlık
        sol_frame = tk.Frame(header_frame, bg=self.header_color)
        sol_frame.pack(side="left", padx=20, pady=15)

        baslik = tk.Label(
            sol_frame,
            text="🏥 Botanik Takip Sistemi",
            font=("Arial", 20, "bold"),
            bg=self.header_color,
            fg=self.fg_color
        )
        baslik.pack(anchor='w')

        alt_baslik = tk.Label(
            sol_frame,
            text="Eczane Yönetim Platformu",
            font=("Arial", 10),
            bg=self.header_color,
            fg=self.fg_secondary
        )
        alt_baslik.pack(anchor='w')

        # Sağ: Kullanıcı bilgisi ve çıkış
        sag_frame = tk.Frame(header_frame, bg=self.header_color)
        sag_frame.pack(side="right", padx=20, pady=15)

        # Kullanıcı bilgisi
        kullanici_adi = self.kullanici.get('ad_soyad') or self.kullanici['kullanici_adi']
        profil = KullaniciYonetimi.PROFILLER.get(self.kullanici['profil'], self.kullanici['profil'])

        kullanici_label = tk.Label(
            sag_frame,
            text=f"👤 {kullanici_adi}",
            font=("Arial", 11, "bold"),
            bg=self.header_color,
            fg=self.fg_color
        )
        kullanici_label.pack(anchor='e')

        profil_label = tk.Label(
            sag_frame,
            text=f"({profil})",
            font=("Arial", 9),
            bg=self.header_color,
            fg=self.fg_secondary
        )
        profil_label.pack(anchor='e')

        # Butonlar için frame
        btn_frame = tk.Frame(sag_frame, bg=self.header_color)
        btn_frame.pack(anchor='e', pady=(10, 0))

        # Tema değiştir butonu
        tema = TEMALAR.get(self.aktif_tema, TEMALAR["koyu"])
        diger_tema = "acik" if self.aktif_tema == "koyu" else "koyu"
        diger_tema_bilgi = TEMALAR[diger_tema]

        tema_btn = tk.Button(
            btn_frame,
            text=f"{diger_tema_bilgi['icon']} {diger_tema_bilgi['ad']}",
            font=("Arial", 9),
            bg='#FF9800',
            fg='white',
            activebackground='#F57C00',
            activeforeground='white',
            cursor='hand2',
            bd=1,
            relief='raised',
            padx=10,
            pady=4,
            command=self.tema_degistir
        )
        tema_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Çıkış butonu
        cikis_btn = tk.Button(
            btn_frame,
            text="🚪 Çıkış",
            font=("Arial", 9),
            bg='#C62828',
            fg='white',
            activebackground='#B71C1C',
            activeforeground='white',
            cursor='hand2',
            bd=0,
            padx=15,
            pady=5,
            command=self.cikis_yap
        )
        cikis_btn.pack(side=tk.LEFT)

    def icerik_olustur(self):
        """Ana içerik alanı - modül butonları"""
        # İçerik frame
        content_frame = tk.Frame(self.root, bg=self.bg_color, padx=30, pady=20)
        content_frame.pack(fill="both", expand=True)

        # Üst satır - Başlık ve Tema butonu
        ust_satir = tk.Frame(content_frame, bg=self.bg_color)
        ust_satir.pack(fill="x", pady=(0, 20))

        # Başlık (solda)
        baslik = tk.Label(
            ust_satir,
            text="Modül Seçin",
            font=("Arial", 14, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        )
        baslik.pack(side="left")

        # Tema değiştir butonu (sağda, büyük ve belirgin)
        tema = TEMALAR.get(self.aktif_tema, TEMALAR["koyu"])
        diger_tema = "acik" if self.aktif_tema == "koyu" else "koyu"
        diger_tema_bilgi = TEMALAR[diger_tema]

        tema_btn_buyuk = tk.Button(
            ust_satir,
            text=f"  {diger_tema_bilgi['icon']}  {diger_tema_bilgi['ad']}  ",
            font=("Arial", 11, "bold"),
            bg='#FF9800',
            fg='white',
            activebackground='#F57C00',
            activeforeground='white',
            cursor='hand2',
            bd=2,
            relief='raised',
            padx=15,
            pady=8,
            command=self.tema_degistir
        )
        tema_btn_buyuk.pack(side="right")

        # Grid frame for buttons
        grid_frame = tk.Frame(content_frame, bg=self.bg_color)
        grid_frame.pack(fill="both", expand=True)

        # Grid ayarları için weight
        for i in range(4):
            grid_frame.columnconfigure(i, weight=1)

        # Modül butonlarını oluştur
        modul_listesi = [
            "ilac_takip", "depo_ekstre", "kasa_takip", "rapor_kontrol",
            "t_cetvel", "ek_raporlar", "mf_analiz", "mf_hizli",
            "siparis_verme", "min_stok_analiz", "stok_maliyet_analiz", "prim_raporlama", "kullanici_yonetimi"
        ]

        row = 0
        col = 0

        for modul_key in modul_listesi:
            modul = self.MODUL_TANIMLARI.get(modul_key, {})
            yetkili = self.yetkiler.get(modul_key, False)

            # Modül kartı oluştur
            self.modul_karti_olustur(
                grid_frame,
                row, col,
                modul_key,
                modul.get("baslik", modul_key),
                modul.get("icon", "📦"),
                modul.get("aciklama", ""),
                modul.get("renk", "#666666"),
                modul.get("hover", "#555555"),
                yetkili
            )

            col += 1
            if col >= 4:
                col = 0
                row += 1

    def modul_karti_olustur(self, parent, row, col, modul_key, baslik, icon, aciklama, renk, hover_renk, yetkili):
        """Tek bir modül kartı oluştur"""
        # Kart frame
        kart = tk.Frame(
            parent,
            bg=renk if yetkili else '#555555',
            padx=3,
            pady=3,
            cursor='hand2' if yetkili else 'arrow'
        )
        kart.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')

        # İç frame
        ic_frame = tk.Frame(kart, bg=renk if yetkili else '#555555', padx=15, pady=20)
        ic_frame.pack(fill="both", expand=True)

        # Icon
        icon_label = tk.Label(
            ic_frame,
            text=icon,
            font=("Arial", 32),
            bg=renk if yetkili else '#555555',
            fg='white' if yetkili else '#888888'
        )
        icon_label.pack()

        # Başlık
        baslik_label = tk.Label(
            ic_frame,
            text=baslik,
            font=("Arial", 12, "bold"),
            bg=renk if yetkili else '#555555',
            fg='white' if yetkili else '#888888'
        )
        baslik_label.pack(pady=(10, 5))

        # Açıklama
        aciklama_label = tk.Label(
            ic_frame,
            text=aciklama,
            font=("Arial", 8),
            bg=renk if yetkili else '#555555',
            fg='#E0E0E0' if yetkili else '#666666',
            wraplength=150
        )
        aciklama_label.pack()

        # Yetki yoksa kilit göster
        if not yetkili:
            kilit_label = tk.Label(
                ic_frame,
                text="🔒",
                font=("Arial", 14),
                bg='#555555',
                fg='#888888'
            )
            kilit_label.pack(pady=(10, 0))

        # Event binding (sadece yetkili modüller için)
        if yetkili:
            widgets = [kart, ic_frame, icon_label, baslik_label, aciklama_label]
            for widget in widgets:
                widget.bind('<Enter>', lambda e, k=kart, r=hover_renk: self._kart_hover_in(k, r))
                widget.bind('<Leave>', lambda e, k=kart, r=renk: self._kart_hover_out(k, r))
                widget.bind('<Button-1>', lambda e, m=modul_key: self.modul_ac(m))

    def _kart_hover_in(self, kart, renk):
        """Mouse hover in"""
        kart.config(bg=renk)
        for child in kart.winfo_children():
            child.config(bg=renk)
            for subchild in child.winfo_children():
                subchild.config(bg=renk)

    def _kart_hover_out(self, kart, renk):
        """Mouse hover out"""
        kart.config(bg=renk)
        for child in kart.winfo_children():
            child.config(bg=renk)
            for subchild in child.winfo_children():
                subchild.config(bg=renk)

    def footer_olustur(self):
        """Alt bilgi alanı"""
        footer_frame = tk.Frame(self.root, bg=self.header_color, height=40)
        footer_frame.pack(fill="x", side="bottom")
        footer_frame.pack_propagate(False)

        # Sol: Tarih/saat
        tarih_label = tk.Label(
            footer_frame,
            text=f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            font=("Arial", 9),
            bg=self.header_color,
            fg='#87CEEB'
        )
        tarih_label.pack(side="left", padx=20, pady=10)

        # Sağ: Versiyon
        version_label = tk.Label(
            footer_frame,
            text="v2.0 | Botanik Eczane Takip Sistemi",
            font=("Arial", 9),
            bg=self.header_color,
            fg='#87CEEB'
        )
        version_label.pack(side="right", padx=20, pady=10)

    def modul_ac(self, modul_key):
        """Seçilen modülü aç"""
        logger.info(f"Modül açılıyor: {modul_key}")

        if modul_key == "ilac_takip":
            self.ilac_takip_ac()
        elif modul_key == "depo_ekstre":
            self.depo_ekstre_ac()
        elif modul_key == "kasa_takip":
            self.kasa_takip_ac()
        elif modul_key == "rapor_kontrol":
            self.rapor_kontrol_ac()
        elif modul_key == "t_cetvel":
            self.t_cetvel_ac()
        elif modul_key == "ek_raporlar":
            self.ek_raporlar_ac()
        elif modul_key == "mf_analiz":
            self.mf_analiz_ac()
        elif modul_key == "mf_hizli":
            self.mf_hizli_ac()
        elif modul_key == "siparis_verme":
            self.siparis_verme_ac()
        elif modul_key == "min_stok_analiz":
            self.min_stok_analiz_ac()
        elif modul_key == "stok_maliyet_analiz":
            self.stok_maliyet_analiz_ac()
        elif modul_key == "prim_raporlama":
            self.prim_raporlama_ac()
        elif modul_key == "kullanici_yonetimi":
            self.kullanici_yonetimi_ac()

    def ilac_takip_ac(self):
        """İlaç Takip modülünü aç"""
        try:
            # Ana menüyü gizle
            self.root.withdraw()

            # Mevcut botanik_gui'yi çalıştır
            from botanik_gui import BotanikGUI

            # Yeni pencere oluştur
            ilac_root = tk.Toplevel()

            # Ana menüye dönüş callback'i
            def ana_menuye_don():
                self.root.deiconify()

            # Pencere kapatma
            ilac_root.protocol("WM_DELETE_WINDOW", lambda: self._modul_kapat_ve_don(ilac_root))

            # BotanikGUI'yi callback ile başlat
            app = BotanikGUI(ilac_root, ana_menu_callback=ana_menuye_don)

        except Exception as e:
            logger.error(f"İlaç Takip açma hatası: {e}")
            messagebox.showerror("Hata", f"İlaç Takip modülü açılamadı:\n{e}")
            self.root.deiconify()

    def depo_ekstre_ac(self):
        """Depo Ekstre modülünü aç"""
        try:
            self.root.withdraw()

            from depo_ekstre_modul import DepoEkstreModul

            # Yeni pencere oluştur
            ekstre_root = tk.Toplevel()

            # Ana menüye dönüş callback'i
            def ana_menuye_don():
                self.root.deiconify()

            # Pencere kapatma
            ekstre_root.protocol("WM_DELETE_WINDOW", lambda: self._modul_kapat_ve_don(ekstre_root))

            # DepoEkstreModul'u callback ile başlat
            app = DepoEkstreModul(ekstre_root, ana_menu_callback=ana_menuye_don)

        except ImportError as e:
            logger.error(f"Depo Ekstre import hatası: {e}")
            messagebox.showinfo("Bilgi", "Depo Ekstre modülü yüklenemedi.\nİlaç Takip modülündeki Ekstre sekmesini kullanabilirsiniz.")
            self.root.deiconify()
        except Exception as e:
            logger.error(f"Depo Ekstre açma hatası: {e}")
            messagebox.showerror("Hata", f"Depo Ekstre modülü açılamadı:\n{e}")
            self.root.deiconify()

    def kasa_takip_ac(self):
        """Kasa Takip modülünü aç"""
        try:
            self.root.withdraw()

            from kasa_takip_modul import KasaKapatmaModul

            # Yeni pencere oluştur
            kasa_root = tk.Toplevel()

            # Ana menüye dönüş callback'i
            def ana_menuye_don():
                self.root.deiconify()

            # Pencere kapatma
            kasa_root.protocol("WM_DELETE_WINDOW", lambda: self._modul_kapat_ve_don(kasa_root))

            # KasaKapatmaModul'u callback ile başlat
            app = KasaKapatmaModul(kasa_root, ana_menu_callback=ana_menuye_don)

        except ImportError as e:
            logger.error(f"Kasa Takip import hatası: {e}")
            messagebox.showerror("Hata", "Kasa Takip modülü yüklenemedi.")
            self.root.deiconify()
        except Exception as e:
            logger.error(f"Kasa Takip açma hatası: {e}")
            messagebox.showerror("Hata", f"Kasa Takip modülü açılamadı:\n{e}")
            self.root.deiconify()

    def rapor_kontrol_ac(self):
        """Rapor Kontrol modülünü aç"""
        messagebox.showinfo("Bilgi", "Rapor Kontrol modülü henüz geliştirme aşamasında.")
        # TODO: Rapor kontrol modülü eklenecek

    def t_cetvel_ac(self):
        """T Cetvel modülünü aç"""
        messagebox.showinfo("Bilgi", "T Cetvel / Bilanço modülü henüz geliştirme aşamasında.")
        # TODO: T cetvel modülü eklenecek

    def ek_raporlar_ac(self):
        """Ek Raporlar modülünü aç"""
        try:
            self.root.withdraw()

            from ek_raporlar_gui import EkRaporlarGUI

            # Yeni pencere oluştur
            ek_root = tk.Toplevel()

            # Ana menüye dönüş callback'i
            def ana_menuye_don():
                self.root.deiconify()

            # Pencere kapatma
            ek_root.protocol("WM_DELETE_WINDOW", lambda: self._modul_kapat_ve_don(ek_root))

            # EkRaporlarGUI'yi başlat
            app = EkRaporlarGUI(ek_root, ana_menu_callback=ana_menuye_don)

        except ImportError as e:
            logger.error(f"Ek Raporlar import hatası: {e}")
            messagebox.showerror("Hata", f"Ek Raporlar modülü yüklenemedi:\n{e}")
            self.root.deiconify()
        except Exception as e:
            logger.error(f"Ek Raporlar açma hatası: {e}")
            messagebox.showerror("Hata", f"Ek Raporlar modülü açılamadı:\n{e}")
            self.root.deiconify()

    def mf_analiz_ac(self):
        """MF Analiz modülünü aç"""
        try:
            self.root.withdraw()

            from nf_analiz_gui import NFAnalizGUI

            # Yeni pencere oluştur
            mf_root = tk.Toplevel()
            mf_root.title("MF Analiz - Nakit Fiyat Simulasyonu")
            mf_root.state('zoomed')

            # Ana menüye dönüş callback'i
            def ana_menuye_don():
                self.root.deiconify()

            # Pencere kapatma
            mf_root.protocol("WM_DELETE_WINDOW", lambda: self._modul_kapat_ve_don(mf_root))

            # NFAnalizGUI'yi başlat
            app = NFAnalizGUI(mf_root)

        except ImportError as e:
            logger.error(f"MF Analiz import hatası: {e}")
            messagebox.showerror("Hata", "MF Analiz modülü yüklenemedi.")
            self.root.deiconify()
        except Exception as e:
            logger.error(f"MF Analiz açma hatası: {e}")
            messagebox.showerror("Hata", f"MF Analiz modülü açılamadı:\n{e}")
            self.root.deiconify()

    def mf_hizli_ac(self):
        """MF Hızlı Hesaplama modülünü aç"""
        try:
            self.root.withdraw()

            from mf_hizli_hesaplama_gui import MFHizliHesaplamaGUI

            # Yeni pencere oluştur
            mf_root = tk.Toplevel()
            mf_root.title("MF Hızlı Hesaplama - NPV Bazlı Karlılık Analizi")

            # Ana menüye dönüş callback'i
            def ana_menuye_don():
                self.root.deiconify()

            # Pencere kapatma
            mf_root.protocol("WM_DELETE_WINDOW", lambda: self._modul_kapat_ve_don(mf_root))

            # MFHizliHesaplamaGUI'yi başlat
            app = MFHizliHesaplamaGUI(mf_root, ana_menu_callback=ana_menuye_don)

        except ImportError as e:
            logger.error(f"MF Hızlı Hesaplama import hatası: {e}")
            messagebox.showerror("Hata", "MF Hızlı Hesaplama modülü yüklenemedi.")
            self.root.deiconify()
        except Exception as e:
            logger.error(f"MF Hızlı Hesaplama açma hatası: {e}")
            messagebox.showerror("Hata", f"MF Hızlı Hesaplama modülü açılamadı:\n{e}")
            self.root.deiconify()

    def siparis_verme_ac(self):
        """Sipariş Verme modülünü aç"""
        try:
            self.root.withdraw()

            from siparis_verme_gui import SiparisVermeGUI

            # Yeni pencere oluştur
            siparis_root = tk.Toplevel()
            siparis_root.title("Sipariş Verme Modülü")
            siparis_root.state('zoomed')

            # Ana menüye dönüş callback'i
            def ana_menuye_don():
                self.root.deiconify()

            # Pencere kapatma
            siparis_root.protocol("WM_DELETE_WINDOW", lambda: self._modul_kapat_ve_don(siparis_root))

            # SiparisVermeGUI'yi başlat
            app = SiparisVermeGUI(siparis_root)

        except ImportError as e:
            logger.error(f"Sipariş Verme import hatası: {e}")
            messagebox.showerror("Hata", "Sipariş Verme modülü yüklenemedi.")
            self.root.deiconify()
        except Exception as e:
            logger.error(f"Sipariş Verme açma hatası: {e}")
            messagebox.showerror("Hata", f"Sipariş Verme modülü açılamadı:\n{e}")
            self.root.deiconify()

    def min_stok_analiz_ac(self):
        """Minimum Stok Analizi modülünü aç"""
        try:
            self.root.withdraw()

            from min_stok_analiz_gui import MinStokAnalizGUI

            # Yeni pencere oluştur
            analiz_root = tk.Toplevel()
            analiz_root.title("Minimum Stok Analizi")
            analiz_root.state('zoomed')

            # Ana menüye dönüş callback'i
            def ana_menuye_don():
                self.root.deiconify()

            # Pencere kapatma
            analiz_root.protocol("WM_DELETE_WINDOW", lambda: self._modul_kapat_ve_don(analiz_root))

            # MinStokAnalizGUI'yi başlat
            app = MinStokAnalizGUI(analiz_root, ana_menu_callback=ana_menuye_don)

        except ImportError as e:
            logger.error(f"Min Stok Analiz import hatası: {e}")
            messagebox.showerror("Hata", "Minimum Stok Analizi modülü yüklenemedi.")
            self.root.deiconify()
        except Exception as e:
            logger.error(f"Min Stok Analiz açma hatası: {e}")
            messagebox.showerror("Hata", f"Minimum Stok Analizi modülü açılamadı:\n{e}")
            self.root.deiconify()

    def prim_raporlama_ac(self):
        """Prim Raporlama modülünü aç"""
        try:
            self.root.withdraw()

            from prim_raporlama_gui import PrimRaporlamaGUI

            prim_root = tk.Toplevel()
            prim_root.title("Prim Raporlama")
            prim_root.state('zoomed')

            def ana_menuye_don():
                self.root.deiconify()

            prim_root.protocol("WM_DELETE_WINDOW", lambda: self._modul_kapat_ve_don(prim_root))

            app = PrimRaporlamaGUI(prim_root, ana_menu_callback=ana_menuye_don)

        except ImportError as e:
            logger.error(f"Prim Raporlama import hatası: {e}")
            messagebox.showerror("Hata", "Prim Raporlama modülü yüklenemedi.")
            self.root.deiconify()
        except Exception as e:
            logger.error(f"Prim Raporlama açma hatası: {e}")
            messagebox.showerror("Hata", f"Prim Raporlama modülü açılamadı:\n{e}")
            self.root.deiconify()

    def stok_maliyet_analiz_ac(self):
        """Stok Maliyet Analizi modülünü aç"""
        try:
            self.root.withdraw()

            from stok_maliyet_analiz_gui import StokMaliyetAnalizGUI

            # Yeni pencere oluştur
            analiz_root = tk.Toplevel()
            analiz_root.title("Stok Maliyet Analizi")
            analiz_root.state('zoomed')

            # Ana menüye dönüş callback'i
            def ana_menuye_don():
                self.root.deiconify()

            # Pencere kapatma
            analiz_root.protocol("WM_DELETE_WINDOW", lambda: self._modul_kapat_ve_don(analiz_root))

            # StokMaliyetAnalizGUI'yi başlat
            app = StokMaliyetAnalizGUI(analiz_root, ana_menu_callback=ana_menuye_don)

        except ImportError as e:
            logger.error(f"Stok Maliyet Analiz import hatası: {e}")
            messagebox.showerror("Hata", "Stok Maliyet Analizi modülü yüklenemedi.")
            self.root.deiconify()
        except Exception as e:
            logger.error(f"Stok Maliyet Analiz açma hatası: {e}")
            messagebox.showerror("Hata", f"Stok Maliyet Analizi modülü açılamadı:\n{e}")
            self.root.deiconify()

    def kullanici_yonetimi_ac(self):
        """Kullanıcı Yönetimi modülünü aç"""
        try:
            from kullanici_yonetimi_gui import KullaniciYonetimiPenceresi

            yonetim_pencere = KullaniciYonetimiPenceresi(self.root, self.kullanici)

        except ImportError:
            messagebox.showerror("Hata", "Kullanıcı yönetimi modülü bulunamadı.")
        except Exception as e:
            logger.error(f"Kullanıcı Yönetimi açma hatası: {e}")
            messagebox.showerror("Hata", f"Kullanıcı Yönetimi açılamadı:\n{e}")

    def _modul_kapat(self, pencere):
        """Modül penceresini kapat ve ana menüyü göster"""
        pencere.destroy()
        self.root.deiconify()

    def _modul_kapat_ve_don(self, pencere):
        """Modül penceresini kapat ve ana menüyü göster (X butonuyla kapatırken)"""
        pencere.destroy()
        self.root.deiconify()

    def _ana_menu_goster_if_closed(self, event, pencere):
        """Pencere tamamen kapandıysa ana menüyü göster"""
        if event.widget == pencere:
            self.root.deiconify()

    def cikis_yap(self):
        """Sistemden çıkış yap"""
        if messagebox.askyesno("Çıkış", "Sistemden çıkmak istediğinize emin misiniz?"):
            logger.info(f"Kullanıcı çıkış yaptı: {self.kullanici['kullanici_adi']}")
            self.root.destroy()

    def calistir(self):
        """Pencereyi çalıştır"""
        self.root.mainloop()


def ana_menu_goster(kullanici):
    """Ana menüyü göster"""
    menu = AnaMenu(kullanici)
    menu.calistir()


if __name__ == "__main__":
    # Test
    test_kullanici = {
        'id': 1,
        'kullanici_adi': 'admin',
        'ad_soyad': 'Test Admin',
        'profil': 'admin'
    }
    ana_menu_goster(test_kullanici)
