"""
Botanik Bot - Kasa Wizard Sistemi
Adım adım kasa kapatma yönerge sistemi
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)


class KasaWizard:
    """Kasa Kapatma Wizard - Adım adım yönerge sistemi"""

    # Wizard adımları
    ADIMLAR = [
        {
            "numara": 1,
            "baslik": "Baslangic Kasasi Kontrolu",
            "aciklama": "Baslangic kasasinin dogru tutarda oldugundan emin olun.\nBir onceki gunden kalan kasa tutari asagida gosterilmektedir.",
            "alan": "baslangic_kasasi",
            "zorunlu": True
        },
        {
            "numara": 2,
            "baslik": "Aksam Kasa Sayimi",
            "aciklama": "Aksam kasayi sayarak kupurlerin adetlerini girin.\nHer kupuru dikkatlice sayiniz.",
            "alan": "sayim",
            "zorunlu": True
        },
        {
            "numara": 3,
            "baslik": "POS Raporlari",
            "aciklama": "POS cihazlarindan alinan gunluk raporlari girin.\nEczaciPOS ve Ingenico cihazlarinin tutarlarini ayri ayri giriniz.",
            "alan": "pos",
            "zorunlu": True
        },
        {
            "numara": 4,
            "baslik": "IBAN Raporlari",
            "aciklama": "IBAN'a atilan paralari girin.\nHer havale/EFT islemini ayri ayri giriniz.",
            "alan": "iban",
            "zorunlu": True
        },
        {
            "numara": 5,
            "baslik": "Girilmemis Masraflar",
            "aciklama": "Botanik sistemine girilmemis masraf var mi kontrol edin.\nEger varsa asagiya girin, yoksa 'YOK' isaretleyin.",
            "alan": "masraf",
            "zorunlu": False,
            "yok_secenegi": True
        },
        {
            "numara": 6,
            "baslik": "Alinan Paralar",
            "aciklama": "Gun ici kasadan alinan para var mi?\nEger varsa kimin ne icin aldigini aciklamayla birlikte girin.",
            "alan": "alinan",
            "zorunlu": False,
            "yok_secenegi": True
        },
        {
            "numara": 7,
            "baslik": "Silinen Recete Etkileri",
            "aciklama": "Onceki gunlerden silinen receteler nedeniyle hastaya para iade edildi mi?\nEger varsa tutarlari girin, yoksa 'YOK' isaretleyin.",
            "alan": "silinen",
            "zorunlu": False,
            "yok_secenegi": True
        },
        {
            "numara": 8,
            "baslik": "Botanik Verileri",
            "aciklama": "EOS programindan Nakit, POS ve IBAN toplamlarini girin.\nBu veriler mutabakat icin kullanilacaktir.",
            "alan": "botanik",
            "zorunlu": True
        },
        {
            "numara": 9,
            "baslik": "Fark Analizi",
            "aciklama": "Son Genel Toplam ile Botanik Toplam arasindaki farki kontrol edin.\nFark varsa nedenini arastirin.",
            "alan": "fark_analizi",
            "zorunlu": True
        },
        {
            "numara": 10,
            "baslik": "Ayrilan Para ve Ertesi Gun Kasasi",
            "aciklama": "Kasadan ayrilacak parayi ve ertesi gun baslangic kasasini belirleyin.\nSlider kullanarak kupurleri dagitiniz.",
            "alan": "ayrilan_para",
            "zorunlu": True
        }
    ]

    def __init__(self, parent, kasa_modul, on_complete=None):
        """
        parent: Ana pencere (Toplevel veya Tk)
        kasa_modul: KasaKapatmaModul instance
        on_complete: Wizard tamamlandığında çağrılacak callback
        """
        self.parent = parent
        self.kasa_modul = kasa_modul
        self.on_complete = on_complete
        self.mevcut_adim = 0
        self.adim_verileri = {}
        self.wizard_pencere = None
        self.yok_isaretlendi = {}

    def baslat(self):
        """Wizard'ı başlat"""
        self.mevcut_adim = 0
        self.adim_goster()

    def adim_goster(self):
        """Mevcut adımın penceresini göster"""
        if self.mevcut_adim >= len(self.ADIMLAR):
            self.wizard_tamamla()
            return

        adim = self.ADIMLAR[self.mevcut_adim]

        # Önceki pencereyi kapat
        if self.wizard_pencere and self.wizard_pencere.winfo_exists():
            self.wizard_pencere.destroy()

        # Yeni pencere oluştur
        self.wizard_pencere = tk.Toplevel(self.parent)
        self.wizard_pencere.title(f"Adim {adim['numara']}/10 - {adim['baslik']}")
        self.wizard_pencere.geometry("750x700")
        self.wizard_pencere.transient(self.parent)
        self.wizard_pencere.grab_set()
        self.wizard_pencere.configure(bg='#FAFAFA')

        # Pencereyi ortala
        self.wizard_pencere.update_idletasks()
        x = (self.wizard_pencere.winfo_screenwidth() - 750) // 2
        y = (self.wizard_pencere.winfo_screenheight() - 700) // 2
        self.wizard_pencere.geometry(f"750x700+{x}+{y}")

        # Kapatma engelle
        self.wizard_pencere.protocol("WM_DELETE_WINDOW", self.iptal_onayi)

        # İçerik oluştur
        self.adim_icerigi_olustur(adim)

    def adim_icerigi_olustur(self, adim):
        """Adım içeriğini oluştur"""
        # Üst bar - Adım numarası ve progress
        ust_frame = tk.Frame(self.wizard_pencere, bg='#1565C0', height=80)
        ust_frame.pack(fill="x")
        ust_frame.pack_propagate(False)

        # Progress bar
        progress_frame = tk.Frame(ust_frame, bg='#1565C0')
        progress_frame.pack(fill="x", padx=20, pady=10)

        for i in range(10):
            renk = '#4CAF50' if i < self.mevcut_adim else '#FFEB3B' if i == self.mevcut_adim else '#90CAF9'
            tk.Frame(progress_frame, bg=renk, width=55, height=8).pack(side="left", padx=2)

        # Başlık
        tk.Label(
            ust_frame,
            text=f"ADIM {adim['numara']}: {adim['baslik'].upper()}",
            font=("Arial", 14, "bold"),
            bg='#1565C0',
            fg='white'
        ).pack(pady=5)

        # Açıklama
        aciklama_frame = tk.Frame(self.wizard_pencere, bg='#E3F2FD', padx=20, pady=15)
        aciklama_frame.pack(fill="x")

        tk.Label(
            aciklama_frame,
            text=adim['aciklama'],
            font=("Arial", 10),
            bg='#E3F2FD',
            fg='#1565C0',
            justify='left',
            wraplength=650
        ).pack(anchor='w')

        # İçerik alanı
        icerik_frame = tk.Frame(self.wizard_pencere, bg='#FAFAFA')
        icerik_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Adıma göre içerik
        alan = adim['alan']
        if alan == 'baslangic_kasasi':
            self.baslangic_kasasi_icerigi(icerik_frame)
        elif alan == 'sayim':
            self.sayim_icerigi(icerik_frame)
        elif alan == 'pos':
            self.pos_icerigi(icerik_frame)
        elif alan == 'iban':
            self.iban_icerigi(icerik_frame)
        elif alan == 'masraf':
            self.masraf_icerigi(icerik_frame, adim.get('yok_secenegi', False))
        elif alan == 'alinan':
            self.alinan_icerigi(icerik_frame, adim.get('yok_secenegi', False))
        elif alan == 'silinen':
            self.silinen_icerigi(icerik_frame, adim.get('yok_secenegi', False))
        elif alan == 'botanik':
            self.botanik_icerigi(icerik_frame)
        elif alan == 'fark_analizi':
            self.fark_analizi_icerigi(icerik_frame)
        elif alan == 'ayrilan_para':
            self.ayrilan_para_icerigi(icerik_frame)

        # Alt butonlar
        self.alt_butonlar_olustur(adim)

    def alt_butonlar_olustur(self, adim):
        """Alt butonları oluştur"""
        buton_frame = tk.Frame(self.wizard_pencere, bg='#FAFAFA', pady=15)
        buton_frame.pack(fill="x", side="bottom")

        # İptal butonu (sol)
        tk.Button(
            buton_frame,
            text="Iptal",
            font=("Arial", 10),
            bg='#F44336',
            fg='white',
            width=10,
            cursor='hand2',
            command=self.iptal_onayi
        ).pack(side="left", padx=20)

        # Geri butonu
        if self.mevcut_adim > 0:
            tk.Button(
                buton_frame,
                text="< Geri",
                font=("Arial", 10, "bold"),
                bg='#9E9E9E',
                fg='white',
                width=10,
                cursor='hand2',
                command=self.onceki_adim
            ).pack(side="left", padx=5)

        # YOK butonu (opsiyonel adımlar için)
        if adim.get('yok_secenegi', False):
            tk.Button(
                buton_frame,
                text="YOK",
                font=("Arial", 10, "bold"),
                bg='#FF9800',
                fg='white',
                width=10,
                cursor='hand2',
                command=lambda: self.yok_isaretle(adim['alan'])
            ).pack(side="right", padx=5)

        # İleri/Tamamla butonu (sağ)
        buton_text = "Tamamla" if self.mevcut_adim == len(self.ADIMLAR) - 1 else "Ileri >"
        tk.Button(
            buton_frame,
            text=buton_text,
            font=("Arial", 11, "bold"),
            bg='#4CAF50',
            fg='white',
            width=12,
            cursor='hand2',
            command=self.sonraki_adim
        ).pack(side="right", padx=20)

    def baslangic_kasasi_icerigi(self, parent):
        """Başlangıç kasası adımı içeriği"""
        # Önceki gün verilerini göster
        onceki = self.kasa_modul.onceki_gun_verisi
        toplam = onceki.get("toplam", 0)
        kupurler = onceki.get("kupurler", {})

        # Toplam gösterimi
        toplam_frame = tk.Frame(parent, bg='#C8E6C9', padx=20, pady=15)
        toplam_frame.pack(fill="x", pady=10)

        tk.Label(
            toplam_frame,
            text="Onceki Gun Kasasi (Bugunun Baslangici):",
            font=("Arial", 12, "bold"),
            bg='#C8E6C9',
            fg='#1B5E20'
        ).pack(side="left")

        tk.Label(
            toplam_frame,
            text=f"{toplam:,.2f} TL",
            font=("Arial", 16, "bold"),
            bg='#C8E6C9',
            fg='#1B5E20'
        ).pack(side="right")

        # Küpür detayları
        if kupurler:
            detay_frame = tk.LabelFrame(parent, text="Kupur Detaylari", font=("Arial", 10, "bold"),
                                        bg='#FAFAFA', padx=10, pady=10)
            detay_frame.pack(fill="x", pady=10)

            for kupur in self.kasa_modul.KUPURLER:
                deger = kupur["deger"]
                adet = kupurler.get(str(deger), 0)
                if adet > 0:
                    row = tk.Frame(detay_frame, bg='#FAFAFA')
                    row.pack(fill="x", pady=2)
                    tk.Label(row, text=f"{kupur['aciklama']}:", font=("Arial", 9),
                            bg='#FAFAFA', width=15, anchor='w').pack(side="left")
                    tk.Label(row, text=f"{adet} adet", font=("Arial", 9),
                            bg='#FAFAFA', width=10).pack(side="left")
                    tk.Label(row, text=f"= {adet * deger:,.2f} TL", font=("Arial", 9, "bold"),
                            bg='#FAFAFA').pack(side="right")

        # Onay checkbox
        self.baslangic_onay_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            parent,
            text="Baslangic kasasi tutarinin dogru oldugunu onayliyorum",
            variable=self.baslangic_onay_var,
            font=("Arial", 10, "bold"),
            bg='#FAFAFA',
            activebackground='#FAFAFA',
            fg='#1565C0'
        ).pack(pady=20)

    def sayim_icerigi(self, parent):
        """Kasa sayımı adımı içeriği"""
        # Ana frame
        main_frame = tk.Frame(parent, bg='#FAFAFA')
        main_frame.pack(fill="both", expand=True)

        # Başlık
        header = tk.Frame(main_frame, bg='#A5D6A7')
        header.pack(fill="x", pady=(0, 5))
        tk.Label(header, text="Kupur", font=("Arial", 11, "bold"), bg='#A5D6A7', width=12).pack(side="left", padx=10, pady=5)
        tk.Label(header, text="Adet", font=("Arial", 11, "bold"), bg='#A5D6A7', width=10).pack(side="left", padx=10, pady=5)
        tk.Label(header, text="Toplam", font=("Arial", 11, "bold"), bg='#A5D6A7', width=15).pack(side="left", padx=10, pady=5)

        # Küpür satırları
        self.wizard_sayim_vars = {}
        self.wizard_sayim_labels = {}

        # Aktif küpürleri ayarlardan al
        aktif_kupurler = self.kasa_modul.ayarlar.get("aktif_kupurler", {})

        for kupur in self.kasa_modul.KUPURLER:
            deger = kupur["deger"]
            # Küpür key formatını doğru oluştur
            if isinstance(deger, float) and deger == int(deger):
                key = str(int(deger))
            else:
                key = str(deger)

            # Aktif mi kontrol et (varsayılan True)
            aktif = aktif_kupurler.get(key, True)

            if aktif:
                row = tk.Frame(main_frame, bg='#E8F5E9')
                row.pack(fill="x", pady=1)

                # Küpür etiketi - büyük ve vurgulu
                tk.Label(row, text=kupur["aciklama"], font=("Arial", 11, "bold"),
                        bg='#E8F5E9', fg='#1B5E20', width=12, anchor='w').pack(side="left", padx=10, pady=3)

                # Mevcut değeri al (varsa)
                mevcut_deger = "0"
                if hasattr(self.kasa_modul, 'sayim_vars') and deger in self.kasa_modul.sayim_vars:
                    mevcut = self.kasa_modul.sayim_vars.get(deger)
                    if mevcut:
                        mevcut_deger = mevcut.get()

                var = tk.StringVar(value=mevcut_deger)
                self.wizard_sayim_vars[deger] = var

                entry = tk.Entry(row, textvariable=var, font=("Arial", 11), width=8, justify='center')
                entry.pack(side="left", padx=10, pady=3)
                entry.bind('<KeyRelease>', lambda e, d=deger: self.sayim_toplam_guncelle(d))

                toplam_label = tk.Label(row, text="0,00 TL", font=("Arial", 11, "bold"),
                                       bg='#E8F5E9', fg='#1B5E20', width=15, anchor='e')
                toplam_label.pack(side="left", padx=10, pady=3)
                self.wizard_sayim_labels[deger] = toplam_label

                # İlk hesaplama
                self.sayim_toplam_guncelle(deger)

        # Genel toplam
        self.wizard_sayim_genel_label = tk.Label(
            main_frame,
            text="TOPLAM: 0,00 TL",
            font=("Arial", 14, "bold"),
            bg='#4CAF50',
            fg='white',
            padx=20,
            pady=10
        )
        self.wizard_sayim_genel_label.pack(fill="x", pady=(10, 5))
        self.sayim_genel_toplam_guncelle()

    def sayim_toplam_guncelle(self, deger):
        """Sayım satır toplamını güncelle"""
        try:
            var = self.wizard_sayim_vars.get(deger)
            if var:
                adet = int(var.get() or 0)
                toplam = adet * deger
                self.wizard_sayim_labels[deger].config(text=f"{toplam:,.2f} TL")
                self.sayim_genel_toplam_guncelle()
        except ValueError:
            pass

    def sayim_genel_toplam_guncelle(self):
        """Sayım genel toplamını güncelle"""
        toplam = 0
        for deger, var in self.wizard_sayim_vars.items():
            try:
                adet = int(var.get() or 0)
                toplam += adet * deger
            except ValueError:
                pass
        self.wizard_sayim_genel_label.config(text=f"TOPLAM: {toplam:,.2f} TL")

    def pos_icerigi(self, parent):
        """POS adımı içeriği"""
        # EczaciPOS
        eczaci_frame = tk.LabelFrame(parent, text="EczaciPOS", font=("Arial", 10, "bold"),
                                     bg='#E3F2FD', padx=10, pady=10)
        eczaci_frame.pack(fill="x", pady=5)

        self.wizard_pos_vars = []
        for i in range(4):
            row = tk.Frame(eczaci_frame, bg='#E3F2FD')
            row.pack(fill="x", pady=2)

            tk.Label(row, text=f"POS {i+1}:", font=("Arial", 10),
                    bg='#E3F2FD', width=10, anchor='w').pack(side="left")

            mevcut = self.kasa_modul.pos_vars[i].get() if i < len(self.kasa_modul.pos_vars) else "0"
            var = tk.StringVar(value=mevcut)
            self.wizard_pos_vars.append(var)

            entry = tk.Entry(row, textvariable=var, font=("Arial", 10), width=15, justify='right')
            entry.pack(side="left", padx=10)
            entry.bind('<KeyRelease>', lambda e: self.pos_toplam_guncelle())

        # Ingenico
        ingenico_frame = tk.LabelFrame(parent, text="Ingenico", font=("Arial", 10, "bold"),
                                       bg='#E3F2FD', padx=10, pady=10)
        ingenico_frame.pack(fill="x", pady=5)

        for i in range(4):
            row = tk.Frame(ingenico_frame, bg='#E3F2FD')
            row.pack(fill="x", pady=2)

            tk.Label(row, text=f"POS {i+1}:", font=("Arial", 10),
                    bg='#E3F2FD', width=10, anchor='w').pack(side="left")

            mevcut = self.kasa_modul.pos_vars[i+4].get() if i+4 < len(self.kasa_modul.pos_vars) else "0"
            var = tk.StringVar(value=mevcut)
            self.wizard_pos_vars.append(var)

            entry = tk.Entry(row, textvariable=var, font=("Arial", 10), width=15, justify='right')
            entry.pack(side="left", padx=10)
            entry.bind('<KeyRelease>', lambda e: self.pos_toplam_guncelle())

        # Toplam
        self.wizard_pos_toplam_label = tk.Label(
            parent,
            text="POS TOPLAM: 0,00 TL",
            font=("Arial", 12, "bold"),
            bg='#2196F3',
            fg='white',
            padx=20,
            pady=10
        )
        self.wizard_pos_toplam_label.pack(fill="x", pady=10)
        self.pos_toplam_guncelle()

    def pos_toplam_guncelle(self):
        """POS toplamını güncelle"""
        toplam = 0
        for var in self.wizard_pos_vars:
            try:
                deger = float(var.get().replace(",", ".") or 0)
                toplam += deger
            except ValueError:
                pass
        self.wizard_pos_toplam_label.config(text=f"POS TOPLAM: {toplam:,.2f} TL")

    def iban_icerigi(self, parent):
        """IBAN adımı içeriği"""
        iban_frame = tk.LabelFrame(parent, text="IBAN/Havale/EFT", font=("Arial", 10, "bold"),
                                   bg='#E0F7FA', padx=10, pady=10)
        iban_frame.pack(fill="x", pady=10)

        self.wizard_iban_vars = []
        for i in range(4):
            row = tk.Frame(iban_frame, bg='#E0F7FA')
            row.pack(fill="x", pady=3)

            tk.Label(row, text=f"IBAN {i+1}:", font=("Arial", 10),
                    bg='#E0F7FA', width=10, anchor='w').pack(side="left")

            mevcut = self.kasa_modul.iban_vars[i].get() if i < len(self.kasa_modul.iban_vars) else "0"
            var = tk.StringVar(value=mevcut)
            self.wizard_iban_vars.append(var)

            entry = tk.Entry(row, textvariable=var, font=("Arial", 10), width=15, justify='right')
            entry.pack(side="left", padx=10)
            entry.bind('<KeyRelease>', lambda e: self.iban_toplam_guncelle())

        # Toplam
        self.wizard_iban_toplam_label = tk.Label(
            parent,
            text="IBAN TOPLAM: 0,00 TL",
            font=("Arial", 12, "bold"),
            bg='#00796B',
            fg='white',
            padx=20,
            pady=10
        )
        self.wizard_iban_toplam_label.pack(fill="x", pady=10)
        self.iban_toplam_guncelle()

    def iban_toplam_guncelle(self):
        """IBAN toplamını güncelle"""
        toplam = 0
        for var in self.wizard_iban_vars:
            try:
                deger = float(var.get().replace(",", ".") or 0)
                toplam += deger
            except ValueError:
                pass
        self.wizard_iban_toplam_label.config(text=f"IBAN TOPLAM: {toplam:,.2f} TL")

    def masraf_icerigi(self, parent, yok_secenegi=False):
        """Masraf adımı içeriği"""
        uyari_frame = tk.Frame(parent, bg='#FFF3E0', padx=10, pady=10)
        uyari_frame.pack(fill="x", pady=5)

        tk.Label(
            uyari_frame,
            text="DIKKAT: Burada girilen masraflarin MUTLAKA Botanik sistemine de girilmesi gerekir!",
            font=("Arial", 9, "bold"),
            bg='#FFF3E0',
            fg='#E65100',
            wraplength=600
        ).pack()

        self.wizard_masraf_vars = []
        for i in range(4):
            row = tk.Frame(parent, bg='#FAFAFA')
            row.pack(fill="x", pady=3)

            tk.Label(row, text=f"Masraf {i+1}:", font=("Arial", 10),
                    bg='#FAFAFA', width=10, anchor='w').pack(side="left")

            mevcut_tutar = self.kasa_modul.masraf_vars[i][0].get() if i < len(self.kasa_modul.masraf_vars) else "0"
            mevcut_acik = self.kasa_modul.masraf_vars[i][1].get() if i < len(self.kasa_modul.masraf_vars) else ""

            tutar_var = tk.StringVar(value=mevcut_tutar)
            aciklama_var = tk.StringVar(value=mevcut_acik)
            self.wizard_masraf_vars.append((tutar_var, aciklama_var))

            tk.Entry(row, textvariable=tutar_var, font=("Arial", 10), width=12, justify='right').pack(side="left", padx=5)
            tk.Label(row, text="TL", font=("Arial", 9), bg='#FAFAFA').pack(side="left")
            tk.Label(row, text="Aciklama:", font=("Arial", 9), bg='#FAFAFA').pack(side="left", padx=5)
            tk.Entry(row, textvariable=aciklama_var, font=("Arial", 10), width=25).pack(side="left", padx=5)

    def alinan_icerigi(self, parent, yok_secenegi=False):
        """Alınan paralar adımı içeriği"""
        uyari_frame = tk.Frame(parent, bg='#FFEBEE', padx=10, pady=10)
        uyari_frame.pack(fill="x", pady=5)

        tk.Label(
            uyari_frame,
            text="ZORUNLU: Kim, ne icin aldigini MUTLAKA aciklama olarak yaziniz!",
            font=("Arial", 9, "bold"),
            bg='#FFEBEE',
            fg='#C62828',
            wraplength=600
        ).pack()

        self.wizard_alinan_vars = []
        for i in range(3):
            row = tk.Frame(parent, bg='#FAFAFA')
            row.pack(fill="x", pady=3)

            tk.Label(row, text=f"Alinan {i+1}:", font=("Arial", 10),
                    bg='#FAFAFA', width=10, anchor='w').pack(side="left")

            mevcut_tutar = self.kasa_modul.gun_ici_alinan_vars[i][0].get() if i < len(self.kasa_modul.gun_ici_alinan_vars) else "0"
            mevcut_acik = self.kasa_modul.gun_ici_alinan_vars[i][1].get() if i < len(self.kasa_modul.gun_ici_alinan_vars) else ""

            tutar_var = tk.StringVar(value=mevcut_tutar)
            aciklama_var = tk.StringVar(value=mevcut_acik)
            self.wizard_alinan_vars.append((tutar_var, aciklama_var))

            tk.Entry(row, textvariable=tutar_var, font=("Arial", 10), width=12, justify='right').pack(side="left", padx=5)
            tk.Label(row, text="TL", font=("Arial", 9), bg='#FAFAFA').pack(side="left")
            tk.Label(row, text="Aciklama:", font=("Arial", 9), bg='#FAFAFA').pack(side="left", padx=5)
            tk.Entry(row, textvariable=aciklama_var, font=("Arial", 10), width=25).pack(side="left", padx=5)

    def silinen_icerigi(self, parent, yok_secenegi=False):
        """Silinen reçete etkileri adımı içeriği"""
        info_frame = tk.Frame(parent, bg='#FCE4EC', padx=10, pady=10)
        info_frame.pack(fill="x", pady=5)

        tk.Label(
            info_frame,
            text="Onceki gunlerden silinen receteler nedeniyle hastaya iade edilen paralar",
            font=("Arial", 9),
            bg='#FCE4EC',
            fg='#AD1457'
        ).pack()

        self.wizard_silinen_vars = []
        for i in range(4):
            row = tk.Frame(parent, bg='#FAFAFA')
            row.pack(fill="x", pady=3)

            tk.Label(row, text=f"Silinen {i+1}:", font=("Arial", 10),
                    bg='#FAFAFA', width=10, anchor='w').pack(side="left")

            mevcut_tutar = self.kasa_modul.silinen_vars[i][0].get() if i < len(self.kasa_modul.silinen_vars) else "0"
            mevcut_acik = self.kasa_modul.silinen_vars[i][1].get() if i < len(self.kasa_modul.silinen_vars) else ""

            tutar_var = tk.StringVar(value=mevcut_tutar)
            aciklama_var = tk.StringVar(value=mevcut_acik)
            self.wizard_silinen_vars.append((tutar_var, aciklama_var))

            tk.Entry(row, textvariable=tutar_var, font=("Arial", 10), width=12, justify='right').pack(side="left", padx=5)
            tk.Label(row, text="TL", font=("Arial", 9), bg='#FAFAFA').pack(side="left")
            tk.Label(row, text="Aciklama:", font=("Arial", 9), bg='#FAFAFA').pack(side="left", padx=5)
            tk.Entry(row, textvariable=aciklama_var, font=("Arial", 10), width=25).pack(side="left", padx=5)

    def botanik_icerigi(self, parent):
        """Botanik verileri adımı içeriği"""
        info_frame = tk.Frame(parent, bg='#FFFDE7', padx=10, pady=10)
        info_frame.pack(fill="x", pady=5)

        tk.Label(
            info_frame,
            text="EOS programindan gunluk rapor alinarak asagidaki degerleri giriniz",
            font=("Arial", 10),
            bg='#FFFDE7',
            fg='#F57F17'
        ).pack()

        # Nakit
        nakit_row = tk.Frame(parent, bg='#FAFAFA')
        nakit_row.pack(fill="x", pady=10)
        tk.Label(nakit_row, text="Botanik Nakit:", font=("Arial", 11, "bold"),
                bg='#FAFAFA', width=15, anchor='w').pack(side="left")

        self.wizard_botanik_nakit = tk.StringVar(value=self.kasa_modul.botanik_nakit_var.get())
        tk.Entry(nakit_row, textvariable=self.wizard_botanik_nakit, font=("Arial", 12),
                width=15, justify='right').pack(side="left", padx=10)
        tk.Label(nakit_row, text="TL", font=("Arial", 11), bg='#FAFAFA').pack(side="left")

        # POS
        pos_row = tk.Frame(parent, bg='#FAFAFA')
        pos_row.pack(fill="x", pady=10)
        tk.Label(pos_row, text="Botanik POS:", font=("Arial", 11, "bold"),
                bg='#FAFAFA', width=15, anchor='w').pack(side="left")

        self.wizard_botanik_pos = tk.StringVar(value=self.kasa_modul.botanik_pos_var.get())
        tk.Entry(pos_row, textvariable=self.wizard_botanik_pos, font=("Arial", 12),
                width=15, justify='right').pack(side="left", padx=10)
        tk.Label(pos_row, text="TL", font=("Arial", 11), bg='#FAFAFA').pack(side="left")

        # IBAN
        iban_row = tk.Frame(parent, bg='#FAFAFA')
        iban_row.pack(fill="x", pady=10)
        tk.Label(iban_row, text="Botanik IBAN:", font=("Arial", 11, "bold"),
                bg='#FAFAFA', width=15, anchor='w').pack(side="left")

        self.wizard_botanik_iban = tk.StringVar(value=self.kasa_modul.botanik_iban_var.get())
        tk.Entry(iban_row, textvariable=self.wizard_botanik_iban, font=("Arial", 12),
                width=15, justify='right').pack(side="left", padx=10)
        tk.Label(iban_row, text="TL", font=("Arial", 11), bg='#FAFAFA').pack(side="left")

    def fark_analizi_icerigi(self, parent):
        """Fark analizi adımı içeriği"""
        # Hesaplamaları yap
        self.kasa_modul.hesaplari_guncelle()

        # Değerleri al
        son_genel = self.son_genel_toplam_hesapla()
        botanik_toplam = self.botanik_toplam_hesapla()
        fark = son_genel - botanik_toplam

        # Gösterim
        karsilastirma_frame = tk.Frame(parent, bg='#FAFAFA')
        karsilastirma_frame.pack(fill="both", expand=True, pady=10)

        # Sol - Kasa
        sol_frame = tk.Frame(karsilastirma_frame, bg='#E8F5E9', padx=20, pady=20)
        sol_frame.pack(side="left", fill="both", expand=True, padx=5)

        tk.Label(sol_frame, text="SON GENEL TOPLAM", font=("Arial", 11, "bold"),
                bg='#E8F5E9', fg='#1B5E20').pack()
        tk.Label(sol_frame, text=f"{son_genel:,.2f} TL", font=("Arial", 16, "bold"),
                bg='#E8F5E9', fg='#1B5E20').pack(pady=10)

        # Sağ - Botanik
        sag_frame = tk.Frame(karsilastirma_frame, bg='#FFFDE7', padx=20, pady=20)
        sag_frame.pack(side="left", fill="both", expand=True, padx=5)

        tk.Label(sag_frame, text="BOTANIK TOPLAM", font=("Arial", 11, "bold"),
                bg='#FFFDE7', fg='#F57F17').pack()
        tk.Label(sag_frame, text=f"{botanik_toplam:,.2f} TL", font=("Arial", 16, "bold"),
                bg='#FFFDE7', fg='#F57F17').pack(pady=10)

        # Fark
        fark_renk = '#4CAF50' if abs(fark) < 0.01 else '#F44336' if fark < 0 else '#FF9800'
        fark_text = f"+{fark:,.2f}" if fark > 0 else f"{fark:,.2f}"

        fark_frame = tk.Frame(parent, bg=fark_renk, padx=20, pady=15)
        fark_frame.pack(fill="x", pady=10)

        tk.Label(fark_frame, text="FARK:", font=("Arial", 14, "bold"),
                bg=fark_renk, fg='white').pack(side="left")
        tk.Label(fark_frame, text=f"{fark_text} TL", font=("Arial", 18, "bold"),
                bg=fark_renk, fg='white').pack(side="right")

        # Fark büyükse uyarı
        kabul_edilebilir = self.kasa_modul.ayarlar.get("kabul_edilebilir_fark", 10)
        if abs(fark) > kabul_edilebilir:
            uyari_frame = tk.Frame(parent, bg='#FFCDD2', padx=10, pady=10)
            uyari_frame.pack(fill="x", pady=10)

            tk.Label(
                uyari_frame,
                text=f"UYARI: Fark {kabul_edilebilir} TL'den fazla! Kontrol listesini inceleyin.",
                font=("Arial", 10, "bold"),
                bg='#FFCDD2',
                fg='#C62828'
            ).pack()

            tk.Button(
                uyari_frame,
                text="Kontrol Listesini Ac",
                font=("Arial", 10, "bold"),
                bg='#F44336',
                fg='white',
                cursor='hand2',
                command=lambda: self.kontrol_listesi_ac(fark)
            ).pack(pady=5)

        self.wizard_fark = fark

    def ayrilan_para_icerigi(self, parent):
        """Ayrılan para ve ertesi gün kasası adımı içeriği"""
        # Bu adım için para ayırma penceresini aç
        tk.Label(
            parent,
            text="Bu adimda kasadan ayrilacak parayi ve\nertesi gun baslangic kasasini belirlemelisiniz.",
            font=("Arial", 11),
            bg='#FAFAFA',
            justify='center'
        ).pack(pady=20)

        tk.Button(
            parent,
            text="PARA AYIRMA PENCERESINI AC",
            font=("Arial", 12, "bold"),
            bg='#3F51B5',
            fg='white',
            padx=30,
            pady=15,
            cursor='hand2',
            command=self.kasa_modul.para_ayirma_penceresi_ac
        ).pack(pady=20)

        # Durum göstergeleri
        durum_frame = tk.Frame(parent, bg='#FAFAFA')
        durum_frame.pack(fill="x", pady=20)

        if self.kasa_modul.ertesi_gun_belirlendi:
            tk.Label(
                durum_frame,
                text=f"Ertesi Gun Kasasi: {self.kasa_modul.ertesi_gun_toplam_data:,.2f} TL",
                font=("Arial", 11, "bold"),
                bg='#C8E6C9',
                fg='#1B5E20',
                padx=10,
                pady=5
            ).pack(fill="x", pady=5)
        else:
            tk.Label(
                durum_frame,
                text="Ertesi Gun Kasasi: BELIRLENMEDI",
                font=("Arial", 11),
                bg='#FFCDD2',
                fg='#C62828',
                padx=10,
                pady=5
            ).pack(fill="x", pady=5)

        if self.kasa_modul.ayrilan_para_belirlendi:
            tk.Label(
                durum_frame,
                text=f"Ayrilan Para: {self.kasa_modul.ayrilan_toplam_data:,.2f} TL",
                font=("Arial", 11, "bold"),
                bg='#FFE0B2',
                fg='#E65100',
                padx=10,
                pady=5
            ).pack(fill="x", pady=5)
        else:
            tk.Label(
                durum_frame,
                text="Ayrilan Para: BELIRLENMEDI",
                font=("Arial", 11),
                bg='#FFCDD2',
                fg='#C62828',
                padx=10,
                pady=5
            ).pack(fill="x", pady=5)

    def son_genel_toplam_hesapla(self):
        """Son genel toplamı hesapla"""
        nakit = sum(int(v.get() or 0) * d for d, v in self.kasa_modul.sayim_vars.items())
        pos = sum(self.kasa_modul.sayi_al(v) for v in self.kasa_modul.pos_vars)
        iban = sum(self.kasa_modul.sayi_al(v) for v in self.kasa_modul.iban_vars)
        masraf = sum(self.kasa_modul.sayi_al(t) for t, _ in self.kasa_modul.masraf_vars)
        silinen = sum(self.kasa_modul.sayi_al(t) for t, _ in self.kasa_modul.silinen_vars)
        alinan = sum(self.kasa_modul.sayi_al(t) for t, _ in self.kasa_modul.gun_ici_alinan_vars)

        genel = nakit + pos + iban
        son_genel = genel + masraf + silinen + alinan
        return son_genel

    def botanik_toplam_hesapla(self):
        """Botanik toplamını hesapla"""
        nakit = self.kasa_modul.sayi_al(self.kasa_modul.botanik_nakit_var)
        pos = self.kasa_modul.sayi_al(self.kasa_modul.botanik_pos_var)
        iban = self.kasa_modul.sayi_al(self.kasa_modul.botanik_iban_var)
        return nakit + pos + iban

    def kontrol_listesi_ac(self, fark):
        """Eksik/Fazla kontrol listesi penceresini aç"""
        from kasa_kontrol_listesi import KasaKontrolListesi
        kontrol = KasaKontrolListesi(self.wizard_pencere, fark)
        kontrol.goster()

    def yok_isaretle(self, alan):
        """Adımı 'YOK' olarak işaretle ve atla"""
        self.yok_isaretlendi[alan] = True
        self.sonraki_adim()

    def onceki_adim(self):
        """Önceki adıma dön"""
        if self.mevcut_adim > 0:
            self.mevcut_adim -= 1
            self.adim_goster()

    def sonraki_adim(self):
        """Sonraki adıma geç"""
        # Mevcut adımın verilerini kaydet
        if not self.adim_verilerini_kaydet():
            return

        self.mevcut_adim += 1
        self.adim_goster()

    def adim_verilerini_kaydet(self):
        """Mevcut adımın verilerini ana modüle kaydet"""
        adim = self.ADIMLAR[self.mevcut_adim]
        alan = adim['alan']

        try:
            if alan == 'baslangic_kasasi':
                if hasattr(self, 'baslangic_onay_var') and not self.baslangic_onay_var.get():
                    messagebox.showwarning("Onay Gerekli", "Lutfen baslangic kasasini onaylayin!")
                    return False

            elif alan == 'sayim':
                for deger, var in self.wizard_sayim_vars.items():
                    if deger in self.kasa_modul.sayim_vars:
                        self.kasa_modul.sayim_vars[deger].set(var.get())

            elif alan == 'pos':
                for i, var in enumerate(self.wizard_pos_vars):
                    if i < len(self.kasa_modul.pos_vars):
                        self.kasa_modul.pos_vars[i].set(var.get())

            elif alan == 'iban':
                for i, var in enumerate(self.wizard_iban_vars):
                    if i < len(self.kasa_modul.iban_vars):
                        self.kasa_modul.iban_vars[i].set(var.get())

            elif alan == 'masraf':
                if alan not in self.yok_isaretlendi:
                    for i, (tutar_var, acik_var) in enumerate(self.wizard_masraf_vars):
                        if i < len(self.kasa_modul.masraf_vars):
                            self.kasa_modul.masraf_vars[i][0].set(tutar_var.get())
                            self.kasa_modul.masraf_vars[i][1].set(acik_var.get())

            elif alan == 'alinan':
                if alan not in self.yok_isaretlendi:
                    for i, (tutar_var, acik_var) in enumerate(self.wizard_alinan_vars):
                        if i < len(self.kasa_modul.gun_ici_alinan_vars):
                            tutar = self.kasa_modul.sayi_al(tutar_var)
                            acik = acik_var.get().strip()
                            if tutar > 0 and not acik:
                                messagebox.showwarning("Aciklama Zorunlu",
                                    f"Alinan {i+1} icin aciklama girilmeli!")
                                return False
                            self.kasa_modul.gun_ici_alinan_vars[i][0].set(tutar_var.get())
                            self.kasa_modul.gun_ici_alinan_vars[i][1].set(acik_var.get())

            elif alan == 'silinen':
                if alan not in self.yok_isaretlendi:
                    for i, (tutar_var, acik_var) in enumerate(self.wizard_silinen_vars):
                        if i < len(self.kasa_modul.silinen_vars):
                            self.kasa_modul.silinen_vars[i][0].set(tutar_var.get())
                            self.kasa_modul.silinen_vars[i][1].set(acik_var.get())

            elif alan == 'botanik':
                self.kasa_modul.botanik_nakit_var.set(self.wizard_botanik_nakit.get())
                self.kasa_modul.botanik_pos_var.set(self.wizard_botanik_pos.get())
                self.kasa_modul.botanik_iban_var.set(self.wizard_botanik_iban.get())

            elif alan == 'ayrilan_para':
                if not self.kasa_modul.ertesi_gun_belirlendi:
                    messagebox.showwarning("Eksik",
                        "Ertesi gun kasasi belirlenmedi!\nLutfen para ayirma penceresini kullanin.")
                    return False

            # Ana modülün hesaplarını güncelle
            self.kasa_modul.hesaplari_guncelle()
            return True

        except Exception as e:
            logger.error(f"Adım verisi kaydetme hatası: {e}")
            messagebox.showerror("Hata", f"Veri kaydetme hatasi: {e}")
            return False

    def wizard_tamamla(self):
        """Wizard'ı tamamla"""
        if self.wizard_pencere and self.wizard_pencere.winfo_exists():
            self.wizard_pencere.destroy()

        messagebox.showinfo("Tamamlandi",
            "Kasa kapatma wizard'i tamamlandi!\n\n"
            "Simdi KAYDET butonuna basarak verileri kaydedebilirsiniz.")

        if self.on_complete:
            self.on_complete()

    def iptal_onayi(self):
        """İptal onayı iste"""
        if messagebox.askyesno("Iptal", "Wizard'i iptal etmek istiyor musunuz?\nGirilen veriler korunacaktir."):
            if self.wizard_pencere and self.wizard_pencere.winfo_exists():
                self.wizard_pencere.destroy()
