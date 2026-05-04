"""
Botanik Bot - Giriş Penceresi
Kullanıcı adı ve şifre ile sisteme giriş
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from kullanici_yonetimi import get_kullanici_yonetimi

logger = logging.getLogger(__name__)


class GirisPenceresi:
    """Kullanıcı giriş penceresi"""

    def __init__(self, on_giris_basarili=None):
        """
        Args:
            on_giris_basarili: Giriş başarılı olduğunda çağrılacak callback
                               Parametre olarak kullanıcı bilgilerini alır
        """
        self.on_giris_basarili = on_giris_basarili
        self.kullanici_yonetimi = get_kullanici_yonetimi()
        self.giris_yapan_kullanici = None

        # Şifresiz kullanım kontrolü
        if self.kullanici_yonetimi.sifresiz_kullanim_aktif_mi():
            # Şifresiz giriş yap ve direkt ana menüye git
            basarili, mesaj, kullanici = self.kullanici_yonetimi.sifresiz_giris_yap()
            if basarili:
                self.giris_yapan_kullanici = kullanici
                logger.info("✓ Şifresiz giriş yapıldı")
                if self.on_giris_basarili:
                    self.on_giris_basarili(kullanici)
                return  # Pencere oluşturma, direkt çık
            else:
                logger.warning(f"Şifresiz giriş başarısız: {mesaj}")
                # Normal giriş penceresini göster

        self.root = tk.Tk()
        self.root.title("Eczasist - Giriş")
        try:
            from eczasist_ikon import ikon_uygula
            ikon_uygula(self.root)
        except Exception:
            pass

        # Pencere boyutları
        # NOT: Yukseklik form icerigine gore (baslik + subtitle + form_frame
        # icindeki kullanici/sifre alanlari + checkbox + hata + buton + version)
        # ~480 px gerekiyor; 350 idi ve sifre alani+buton kirpiliyordu.
        pencere_genislik = 420
        pencere_yukseklik = 500

        # Ekranın ortasına yerleştir
        ekran_genislik = self.root.winfo_screenwidth()
        ekran_yukseklik = self.root.winfo_screenheight()
        x = (ekran_genislik - pencere_genislik) // 2
        y = (ekran_yukseklik - pencere_yukseklik) // 2

        self.root.geometry(f"{pencere_genislik}x{pencere_yukseklik}+{x}+{y}")
        self.root.resizable(False, False)

        # Renk şeması
        self.bg_color = '#1565C0'  # Koyu mavi
        self.fg_color = 'white'
        self.entry_bg = 'white'
        self.button_bg = '#4CAF50'  # Yeşil
        self.button_fg = 'white'

        self.root.configure(bg=self.bg_color)

        # Enter tuşu ile giriş
        self.root.bind('<Return>', lambda e: self.giris_yap())

        # Pencere kapatılırsa
        self.root.protocol("WM_DELETE_WINDOW", self.kapat)

        self.arayuz_olustur()

    def arayuz_olustur(self):
        """Giriş arayüzünü oluştur"""
        # Ana frame
        main_frame = tk.Frame(self.root, bg=self.bg_color, padx=30, pady=30)
        main_frame.pack(fill="both", expand=True)

        # Logo/Başlık alanı
        logo_frame = tk.Frame(main_frame, bg=self.bg_color)
        logo_frame.pack(fill="x", pady=(0, 20))

        # Başlık
        title_label = tk.Label(
            logo_frame,
            text="🏥 Botanik Takip Sistemi",
            font=("Arial", 18, "bold"),
            bg=self.bg_color,
            fg=self.fg_color
        )
        title_label.pack()

        # Alt başlık
        subtitle_label = tk.Label(
            logo_frame,
            text="Eczane Yönetim Platformu",
            font=("Arial", 10),
            bg=self.bg_color,
            fg='#B3E5FC'
        )
        subtitle_label.pack(pady=(5, 0))

        # Giriş formu frame
        form_frame = tk.Frame(main_frame, bg='white', padx=25, pady=25)
        form_frame.pack(fill="both", expand=True)

        # Giriş başlığı
        giris_label = tk.Label(
            form_frame,
            text="Giriş Yap",
            font=("Arial", 14, "bold"),
            bg='white',
            fg='#333333'
        )
        giris_label.pack(pady=(0, 15))

        # Kullanıcı adı
        kullanici_frame = tk.Frame(form_frame, bg='white')
        kullanici_frame.pack(fill="x", pady=(0, 10))

        kullanici_label = tk.Label(
            kullanici_frame,
            text="👤 Kullanıcı Adı",
            font=("Arial", 10),
            bg='white',
            fg='#555555',
            anchor='w'
        )
        kullanici_label.pack(fill="x")

        self.kullanici_entry = ttk.Entry(
            kullanici_frame,
            font=("Arial", 12)
        )
        self.kullanici_entry.pack(fill="x", pady=(5, 0), ipady=5)

        # Şifre
        sifre_frame = tk.Frame(form_frame, bg='white')
        sifre_frame.pack(fill="x", pady=(0, 15))

        sifre_label = tk.Label(
            sifre_frame,
            text="🔒 Şifre",
            font=("Arial", 10),
            bg='white',
            fg='#555555',
            anchor='w'
        )
        sifre_label.pack(fill="x")

        self.sifre_entry = ttk.Entry(
            sifre_frame,
            font=("Arial", 12),
            show="●"
        )
        self.sifre_entry.pack(fill="x", pady=(5, 0), ipady=5)

        # Şifreyi göster checkbox
        self.sifre_goster_var = tk.BooleanVar(value=False)
        sifre_goster_cb = tk.Checkbutton(
            sifre_frame,
            text="Şifreyi göster",
            variable=self.sifre_goster_var,
            command=self.sifre_goster_toggle,
            bg='white',
            fg='#666666',
            font=("Arial", 8),
            activebackground='white'
        )
        sifre_goster_cb.pack(anchor='w', pady=(5, 0))

        # Hata mesajı label
        self.hata_label = tk.Label(
            form_frame,
            text="",
            font=("Arial", 9),
            bg='white',
            fg='#F44336'
        )
        self.hata_label.pack(fill="x", pady=(0, 10))

        # Giriş butonu
        self.giris_button = tk.Button(
            form_frame,
            text="GİRİŞ YAP",
            font=("Arial", 12, "bold"),
            bg=self.button_bg,
            fg=self.button_fg,
            activebackground='#388E3C',
            activeforeground='white',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=10,
            command=self.giris_yap
        )
        self.giris_button.pack(fill="x")

        # Versiyon bilgisi
        version_label = tk.Label(
            main_frame,
            text="v1.0 | © 2024 Botanik Eczane",
            font=("Arial", 8),
            bg=self.bg_color,
            fg='#B3E5FC'
        )
        version_label.pack(pady=(10, 0))

        # Focus kullanıcı adına
        self.kullanici_entry.focus_set()

    def sifre_goster_toggle(self):
        """Şifreyi göster/gizle"""
        if self.sifre_goster_var.get():
            self.sifre_entry.config(show="")
        else:
            self.sifre_entry.config(show="●")

    def giris_yap(self):
        """Giriş işlemini gerçekleştir"""
        kullanici_adi = self.kullanici_entry.get().strip()
        sifre = self.sifre_entry.get()

        # Boş kontrol
        if not kullanici_adi:
            self.hata_goster("Kullanıcı adı giriniz")
            self.kullanici_entry.focus_set()
            return

        if not sifre:
            self.hata_goster("Şifre giriniz")
            self.sifre_entry.focus_set()
            return

        # Giriş denemesi
        basarili, mesaj, kullanici = self.kullanici_yonetimi.giris_yap(kullanici_adi, sifre)

        if basarili:
            self.giris_yapan_kullanici = kullanici
            logger.info(f"✓ Giriş başarılı: {kullanici_adi}")

            # Callback çağır
            if self.on_giris_basarili:
                self.root.destroy()
                self.on_giris_basarili(kullanici)
        else:
            self.hata_goster(mesaj)
            self.sifre_entry.delete(0, tk.END)
            self.sifre_entry.focus_set()

    def hata_goster(self, mesaj):
        """Hata mesajını göster"""
        self.hata_label.config(text=mesaj)

    def kapat(self):
        """Pencereyi kapat"""
        self.root.destroy()

    def calistir(self):
        """Pencereyi çalıştır"""
        # Şifresiz kullanımda root oluşturulmamış olabilir
        if hasattr(self, 'root') and self.root:
            self.root.mainloop()


def giris_penceresi_goster(on_giris_basarili=None):
    """Giriş penceresini göster ve başarılı girişte callback çağır"""
    pencere = GirisPenceresi(on_giris_basarili)
    pencere.calistir()
    return pencere.giris_yapan_kullanici


if __name__ == "__main__":
    # Test
    def giris_callback(kullanici):
        print(f"Giriş yapan: {kullanici}")

    giris_penceresi_goster(giris_callback)
