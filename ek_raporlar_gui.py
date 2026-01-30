"""
Botanik Bot - Ek Raporlar Modülü
Çeşitli veritabanı sorgularına erişim sağlayan ana menü
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class EkRaporlarGUI:
    """Ek Raporlar ana menü penceresi"""

    # Rapor tanımları
    RAPOR_TANIMLARI = {
        "tum_hareketler": {
            "baslik": "Tüm Hareketler",
            "icon": "📦",
            "aciklama": "Giriş, çıkış, takas, reçete - tüm stok hareketleri",
            "renk": "#4CAF50",
            "hover": "#388E3C"
        },
        "stok_analiz": {
            "baslik": "Stok Analiz",
            "icon": "📊",
            "aciklama": "Stok, sarf, miad analizi - bitiş tahminleri",
            "renk": "#2196F3",
            "hover": "#1976D2"
        },
        "stok_durumu": {
            "baslik": "Stok Durumu",
            "icon": "🏪",
            "aciklama": "Güncel stok miktarları ve değerleri",
            "renk": "#607D8B",
            "hover": "#455A64",
            "aktif": False  # Henüz geliştirme aşamasında
        },
        "satis_raporu": {
            "baslik": "Satış Raporu",
            "icon": "💰",
            "aciklama": "Dönemsel satış analizleri",
            "renk": "#FF9800",
            "hover": "#F57C00",
            "aktif": False
        },
        "alis_raporu": {
            "baslik": "Alış Raporu",
            "icon": "🛒",
            "aciklama": "Dönemsel alış analizleri",
            "renk": "#9C27B0",
            "hover": "#7B1FA2",
            "aktif": False
        },
        "recete_analiz": {
            "baslik": "Reçete Analizi",
            "icon": "📋",
            "aciklama": "Reçete bazlı detaylı analizler",
            "renk": "#00BCD4",
            "hover": "#0097A7",
            "aktif": False
        },
        "depo_analiz": {
            "baslik": "Depo Analizi",
            "icon": "🏭",
            "aciklama": "Depo bazlı alış analizleri",
            "renk": "#795548",
            "hover": "#5D4037",
            "aktif": False
        },
        "alis_analiz": {
            "baslik": "Alış Analizi",
            "icon": "🛍️",
            "aciklama": "Fatura bazlı alış ve stok oranlamaları",
            "renk": "#E91E63",
            "hover": "#C2185B",
            "aktif": True
        },
        "stok_hareket_analiz": {
            "baslik": "Stok Hareket Analiz",
            "icon": "📈",
            "aciklama": "Eşdeğer bazlı aylık hareket analizi ve raporlama",
            "renk": "#3F51B5",
            "hover": "#303F9F",
            "aktif": True
        },
        "uretici_firma_rapor": {
            "baslik": "Uretici Firma Raporu",
            "icon": "F",
            "aciklama": "Uretici firma ve depo bazli alis faturalari",
            "renk": "#009688",
            "hover": "#00796B",
            "aktif": True
        }
    }

    def __init__(self, root: tk.Toplevel, ana_menu_callback: Optional[Callable] = None):
        """
        Args:
            root: Tkinter Toplevel penceresi
            ana_menu_callback: Ana menüye dönüş callback'i
        """
        self.root = root
        self.ana_menu_callback = ana_menu_callback

        self.root.title("Ek Raporlar - Botanik Veritabanı Sorguları")

        # Pencere boyutları
        pencere_genislik = 800
        pencere_yukseklik = 700

        # Ekranın ortasına yerleştir
        ekran_genislik = self.root.winfo_screenwidth()
        ekran_yukseklik = self.root.winfo_screenheight()
        x = (ekran_genislik - pencere_genislik) // 2
        y = (ekran_yukseklik - pencere_yukseklik) // 2

        self.root.geometry(f"{pencere_genislik}x{pencere_yukseklik}+{x}+{y}")
        self.root.resizable(False, False)

        # Renk şeması
        self.bg_color = '#1A237E'  # Koyu mavi
        self.header_color = '#0D1642'
        self.fg_color = 'white'
        self.card_bg = '#283593'

        self.root.configure(bg=self.bg_color)

        self.arayuz_olustur()

    def arayuz_olustur(self):
        """Ana arayüzü oluştur"""
        # Header
        self.header_olustur()

        # İçerik
        self.icerik_olustur()

        # Footer
        self.footer_olustur()

    def header_olustur(self):
        """Üst başlık alanı"""
        header_frame = tk.Frame(self.root, bg=self.header_color, height=70)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)

        # Başlık
        baslik = tk.Label(
            header_frame,
            text="📈 Ek Raporlar",
            font=("Arial", 18, "bold"),
            bg=self.header_color,
            fg=self.fg_color
        )
        baslik.pack(side="left", padx=20, pady=15)

        alt_baslik = tk.Label(
            header_frame,
            text="Botanik EOS Veritabanı Sorguları",
            font=("Arial", 10),
            bg=self.header_color,
            fg='#90CAF9'
        )
        alt_baslik.pack(side="left", padx=10, pady=20)

        # Geri butonu
        geri_btn = tk.Button(
            header_frame,
            text="← Ana Menü",
            font=("Arial", 10),
            bg='#455A64',
            fg='white',
            activebackground='#37474F',
            activeforeground='white',
            cursor='hand2',
            bd=0,
            padx=15,
            pady=8,
            command=self.ana_menuye_don
        )
        geri_btn.pack(side="right", padx=20, pady=15)

    def icerik_olustur(self):
        """Ana içerik alanı - rapor butonları"""
        content_frame = tk.Frame(self.root, bg=self.bg_color, padx=30, pady=20)
        content_frame.pack(fill="both", expand=True)

        # Açıklama
        aciklama = tk.Label(
            content_frame,
            text="Bir rapor seçin:",
            font=("Arial", 12),
            bg=self.bg_color,
            fg=self.fg_color
        )
        aciklama.pack(pady=(0, 15))

        # Grid frame
        grid_frame = tk.Frame(content_frame, bg=self.bg_color)
        grid_frame.pack(fill="both", expand=True)

        for i in range(3):
            grid_frame.columnconfigure(i, weight=1)

        # Rapor butonlarını oluştur
        rapor_listesi = list(self.RAPOR_TANIMLARI.keys())

        row = 0
        col = 0

        for rapor_key in rapor_listesi:
            rapor = self.RAPOR_TANIMLARI[rapor_key]
            aktif = rapor.get("aktif", True)

            self.rapor_karti_olustur(
                grid_frame,
                row, col,
                rapor_key,
                rapor["baslik"],
                rapor["icon"],
                rapor["aciklama"],
                rapor["renk"],
                rapor["hover"],
                aktif
            )

            col += 1
            if col >= 3:
                col = 0
                row += 1

    def rapor_karti_olustur(self, parent, row, col, rapor_key, baslik, icon, aciklama, renk, hover_renk, aktif):
        """Tek bir rapor kartı oluştur"""
        kart = tk.Frame(
            parent,
            bg=renk if aktif else '#555555',
            padx=3,
            pady=3,
            cursor='hand2' if aktif else 'arrow'
        )
        kart.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')

        ic_frame = tk.Frame(kart, bg=renk if aktif else '#555555', padx=15, pady=20)
        ic_frame.pack(fill="both", expand=True)

        # Icon
        icon_label = tk.Label(
            ic_frame,
            text=icon,
            font=("Arial", 28),
            bg=renk if aktif else '#555555',
            fg='white' if aktif else '#888888'
        )
        icon_label.pack()

        # Başlık
        baslik_label = tk.Label(
            ic_frame,
            text=baslik,
            font=("Arial", 11, "bold"),
            bg=renk if aktif else '#555555',
            fg='white' if aktif else '#888888'
        )
        baslik_label.pack(pady=(8, 4))

        # Açıklama
        aciklama_label = tk.Label(
            ic_frame,
            text=aciklama,
            font=("Arial", 8),
            bg=renk if aktif else '#555555',
            fg='#E0E0E0' if aktif else '#666666',
            wraplength=180
        )
        aciklama_label.pack()

        # Aktif değilse "Yakında" etiketi
        if not aktif:
            yakinda_label = tk.Label(
                ic_frame,
                text="🔜 Yakında",
                font=("Arial", 9),
                bg='#555555',
                fg='#FFC107'
            )
            yakinda_label.pack(pady=(8, 0))

        # Event binding
        if aktif:
            widgets = [kart, ic_frame, icon_label, baslik_label, aciklama_label]
            for widget in widgets:
                widget.bind('<Enter>', lambda e, k=kart, r=hover_renk: self._kart_hover_in(k, r))
                widget.bind('<Leave>', lambda e, k=kart, r=renk: self._kart_hover_out(k, r))
                widget.bind('<Button-1>', lambda e, m=rapor_key: self.rapor_ac(m))

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
        footer_frame = tk.Frame(self.root, bg=self.header_color, height=35)
        footer_frame.pack(fill="x", side="bottom")
        footer_frame.pack_propagate(False)

        bilgi = tk.Label(
            footer_frame,
            text="Veritabanı: eczane_test | Bağlantı: localhost",
            font=("Arial", 9),
            bg=self.header_color,
            fg='#90CAF9'
        )
        bilgi.pack(pady=8)

    def rapor_ac(self, rapor_key: str):
        """Seçilen raporu aç"""
        logger.info(f"Rapor açılıyor: {rapor_key}")

        if rapor_key == "tum_hareketler":
            self.tum_hareketler_ac()
        elif rapor_key == "stok_analiz":
            self.stok_analiz_ac()
        elif rapor_key == "stok_durumu":
            self.stok_durumu_ac()
        elif rapor_key == "satis_raporu":
            self.satis_raporu_ac()
        elif rapor_key == "alis_raporu":
            self.alis_raporu_ac()
        elif rapor_key == "recete_analiz":
            self.recete_analiz_ac()
        elif rapor_key == "depo_analiz":
            self.depo_analiz_ac()
        elif rapor_key == "alis_analiz":
            self.alis_analiz_ac()
        elif rapor_key == "stok_hareket_analiz":
            self.stok_hareket_analiz_ac()
        elif rapor_key == "uretici_firma_rapor":
            self.uretici_firma_rapor_ac()

    def tum_hareketler_ac(self):
        """Tüm Hareketler raporunu aç"""
        try:
            from tum_hareketler_gui import TumHareketlerGUI

            rapor_pencere = tk.Toplevel(self.root)
            app = TumHareketlerGUI(rapor_pencere)

        except ImportError as e:
            logger.error(f"Tüm Hareketler import hatası: {e}")
            messagebox.showerror("Hata", f"Tüm Hareketler modülü yüklenemedi:\n{e}")
        except Exception as e:
            logger.error(f"Tüm Hareketler açma hatası: {e}")
            messagebox.showerror("Hata", f"Rapor açılamadı:\n{e}")

    def stok_analiz_ac(self):
        """Stok Analiz raporunu aç"""
        try:
            from stok_analiz_gui import StokAnalizGUI

            rapor_pencere = tk.Toplevel(self.root)
            app = StokAnalizGUI(rapor_pencere)

        except ImportError as e:
            logger.error(f"Stok Analiz import hatası: {e}")
            messagebox.showerror("Hata", f"Stok Analiz modülü yüklenemedi:\n{e}")
        except Exception as e:
            logger.error(f"Stok Analiz açma hatası: {e}")
            messagebox.showerror("Hata", f"Rapor açılamadı:\n{e}")

    def stok_durumu_ac(self):
        """Stok Durumu raporunu aç"""
        messagebox.showinfo("Bilgi", "Stok Durumu raporu henüz geliştirme aşamasında.")

    def satis_raporu_ac(self):
        """Satış Raporu'nu aç"""
        messagebox.showinfo("Bilgi", "Satış Raporu henüz geliştirme aşamasında.")

    def alis_raporu_ac(self):
        """Alış Raporu'nu aç"""
        messagebox.showinfo("Bilgi", "Alış Raporu henüz geliştirme aşamasında.")

    def recete_analiz_ac(self):
        """Reçete Analizi'ni aç"""
        messagebox.showinfo("Bilgi", "Reçete Analizi henüz geliştirme aşamasında.")

    def depo_analiz_ac(self):
        """Depo Analizi'ni aç"""
        messagebox.showinfo("Bilgi", "Depo Analizi henüz geliştirme aşamasında.")

    def alis_analiz_ac(self):
        """Alış Analizi raporunu aç"""
        try:
            from alis_analiz_gui import AlisAnalizGUI

            rapor_pencere = tk.Toplevel(self.root)
            app = AlisAnalizGUI(rapor_pencere)

        except ImportError as e:
            logger.error(f"Alış Analiz import hatası: {e}")
            messagebox.showerror("Hata", f"Alış Analiz modülü yüklenemedi:\n{e}")
        except Exception as e:
            logger.error(f"Alış Analiz açma hatası: {e}")
            messagebox.showerror("Hata", f"Rapor açılamadı:\n{e}")

    def stok_hareket_analiz_ac(self):
        """Stok Hareket Analiz raporunu aç"""
        try:
            from stok_hareket_analiz_gui import StokHareketAnalizGUI

            rapor_pencere = tk.Toplevel(self.root)
            app = StokHareketAnalizGUI(rapor_pencere)

        except ImportError as e:
            logger.error(f"Stok Hareket Analiz import hatası: {e}")
            messagebox.showerror("Hata", f"Stok Hareket Analiz modülü yüklenemedi:\n{e}")
        except Exception as e:
            logger.error(f"Stok Hareket Analiz açma hatası: {e}")
            messagebox.showerror("Hata", f"Rapor açılamadı:\n{e}")

    def uretici_firma_rapor_ac(self):
        """Uretici Firma Raporu'nu ac"""
        try:
            from uretici_firma_rapor_gui import UreticiFirmaRaporGUI

            rapor_pencere = tk.Toplevel(self.root)
            app = UreticiFirmaRaporGUI(rapor_pencere)

        except ImportError as e:
            logger.error(f"Uretici Firma Rapor import hatasi: {e}")
            messagebox.showerror("Hata", f"Uretici Firma Rapor modulu yuklenemedi:\n{e}")
        except Exception as e:
            logger.error(f"Uretici Firma Rapor acma hatasi: {e}")
            messagebox.showerror("Hata", f"Rapor acilamadi:\n{e}")

    def ana_menuye_don(self):
        """Ana menüye dön"""
        self.root.destroy()
        if self.ana_menu_callback:
            self.ana_menu_callback()


# Test
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()

    pencere = tk.Toplevel(root)
    app = EkRaporlarGUI(pencere)

    root.mainloop()
