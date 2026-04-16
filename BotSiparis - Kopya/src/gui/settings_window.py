"""
Ayarlar penceresi
"""
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import os


class SettingsWindow:
    """Ayarlar penceresi - Depo giriş bilgileri"""

    def __init__(self, parent, main_window=None):
        self.parent = parent
        self.main_window = main_window  # Ana GUI penceresi referansı
        self.window = tk.Toplevel(parent)
        self.window.title("Ayarlar")
        self.window.geometry("650x900")
        self.window.resizable(True, True)

        # .env dosya yolu
        self.env_path = Path(__file__).resolve().parent.parent.parent / ".env"

        # Mevcut değerleri yükle
        self.current_values = self.load_env_values()

        self.create_widgets()

        # Pencereyi merkeze al
        self.window.transient(parent)
        self.window.grab_set()

    def load_env_values(self):
        """Mevcut .env değerlerini oku"""
        values = {
            "ALLIANCE_ECZANE_KODU": "",
            "ALLIANCE_USERNAME": "",
            "ALLIANCE_PASSWORD": "",
            "ALLIANCE_ENABLED": "true",  # Varsayılan aktif
            "ALLIANCE_ODEME_TIPI": "vade",  # vade veya kredi_karti
            "ALLIANCE_VADE_AY": "1",  # Kaç ay sonra
            "ALLIANCE_VADE_GUN": "15",  # Ayın kaçıncı günü
            "ALLIANCE_KK_KESIM": "28",  # Kredi kartı hesap kesim günü
            "ALLIANCE_KK_ODEME": "7",  # Kredi kartı ödeme günü
            "SELCUK_HESAP_KODU": "",
            "SELCUK_USERNAME": "",
            "SELCUK_PASSWORD": "",
            "SELCUK_ENABLED": "true",  # Varsayılan aktif
            "SELCUK_ODEME_TIPI": "vade",
            "SELCUK_VADE_AY": "1",
            "SELCUK_VADE_GUN": "15",
            "SELCUK_KK_KESIM": "28",
            "SELCUK_KK_ODEME": "7",
            "YUSUFPASA_ECZANE_KODU": "",
            "YUSUFPASA_USERNAME": "",
            "YUSUFPASA_PASSWORD": "",
            "YUSUFPASA_ENABLED": "true",  # Varsayılan aktif
            "YUSUFPASA_ODEME_TIPI": "vade",
            "YUSUFPASA_VADE_AY": "1",
            "YUSUFPASA_VADE_GUN": "15",
            "YUSUFPASA_KK_KESIM": "28",
            "YUSUFPASA_KK_ODEME": "7",
            "ISKOOP_USERNAME": "",
            "ISKOOP_PASSWORD": "",
            "ISKOOP_ENABLED": "true",  # Varsayılan aktif
            "ISKOOP_ODEME_TIPI": "kredi_karti",  # Koop varsayılan kredi kartı
            "ISKOOP_VADE_AY": "1",
            "ISKOOP_VADE_GUN": "15",
            "ISKOOP_KK_KESIM": "28",
            "ISKOOP_KK_ODEME": "7",
            "BURSA_USERNAME": "",
            "BURSA_PASSWORD": "",
            "BURSA_ENABLED": "true",  # Varsayılan aktif
            "BURSA_ODEME_TIPI": "kredi_karti",  # Bursa varsayılan kredi kartı
            "BURSA_VADE_AY": "1",
            "BURSA_VADE_GUN": "15",
            "BURSA_KK_KESIM": "28",
            "BURSA_KK_ODEME": "7",
            "FARMAZON_USERNAME": "",
            "FARMAZON_PASSWORD": "",
            "FARMAZON_ENABLED": "true",  # Varsayılan aktif
            "FARMAZON_ODEME_TIPI": "kredi_karti",  # Farmazon varsayılan kredi kartı
            "FARMAZON_VADE_AY": "1",
            "FARMAZON_VADE_GUN": "15",
            "FARMAZON_KK_KESIM": "28",
            "FARMAZON_KK_ODEME": "7",
            "FARMAZON_KARGO": "140",  # Kargo ücreti (TL)
            "FARMAZON_MAX_AY": "6",  # Maksimum stok süresi (ay)
            "FARMAZON_UZUN_MIAT": "true",  # 8 aydan uzun miatlı ürünleri al (varsayılan açık)
            "FARMAZON_PAHALI_ESIK": "10",  # Pahalılık eşiği (%) - varsayılan %10
            "SANCAK_USERNAME": "",
            "SANCAK_PASSWORD": "",
            "SANCAK_ENABLED": "true",  # Varsayılan aktif
            "SANCAK_ODEME_TIPI": "vade",
            "SANCAK_VADE_AY": "1",
            "SANCAK_VADE_GUN": "15",
            "SANCAK_KK_KESIM": "28",
            "SANCAK_KK_ODEME": "7",
            "ECZACI_ADI": "",  # Eczacı adı
            "ECZANE_ADI": "",  # Eczane adı
            "ECZANE_TELEFONU": "",  # Eczane telefon numarası
            "ECZACI_TELEFONU": "",  # Eczacı telefon numarası
            "GUN_SAYISI": "30",  # Varsayılan 30 gün
            "AYLIK_FAIZ": "4",  # Varsayılan: %4 aylık faiz
            "SHOW_EFEKTIF_FIYAT": "true",  # Varsayılan: Efektif fiyatları göster
            "SHOW_PRICES": "true",  # Varsayılan: Fiyatları göster
            "MF_ENABLED": "true",  # Varsayılan: MF özelliği açık
            "DEBUG_LOGGING": "false",  # Varsayılan: Debug loglar kapalı
            "DEPO_SIRALAMA": "",  # Varsayılan: Boş (varsayılan sıra kullanılır)
            "BROWSER_MODE": "tabs",  # Varsayılan: Tek pencere sekmeler (tabs/windows)
        }

        if self.env_path.exists():
            try:
                with open(self.env_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            if key in values:
                                values[key] = value
            except Exception as e:
                print(f"Ayarlar yüklenirken hata: {e}")

        return values

    def create_widgets(self):
        """UI bileşenlerini oluştur"""

        # Başlık
        title_frame = tk.Frame(self.window, bg="#2C3E50", height=60)
        title_frame.pack(fill=tk.X)

        title_label = tk.Label(
            title_frame,
            text="Depo Giriş Bilgileri",
            font=("Arial", 14, "bold"),
            bg="#2C3E50",
            fg="white"
        )
        title_label.pack(pady=15)

        # Ana içerik frame (scrollable)
        main_frame = tk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Canvas ve scrollbar
        canvas = tk.Canvas(main_frame, bg="white")
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="white")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas ve scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # İçerik frame
        content_frame = tk.Frame(scrollable_frame, bg="white", padx=20, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Bilgi etiketi
        info_label = tk.Label(
            content_frame,
            text="Depo web sitelerine otomatik giriş için kullanıcı bilgilerinizi girin.\n"
                 "Bilgiler .env dosyasına kaydedilecektir.",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white",
            justify=tk.LEFT
        )
        info_label.pack(anchor=tk.W, pady=(0, 20))

        # Entry alanları ve checkbox'lar için değişkenler
        self.entries = {}
        self.checkboxes = {}
        self.odeme_tipi_vars = {}  # Ödeme tipi radio button'ları için
        self.vade_ay_combos = {}  # Vade ay combobox'ları için
        self.vade_gun_combos = {}  # Vade gün combobox'ları için
        self.kk_kesim_combos = {}  # Kredi kartı kesim günü combobox'ları için
        self.kk_odeme_combos = {}  # Kredi kartı ödeme günü combobox'ları için

        # Vade ay seçenekleri
        self.vade_ay_secenekleri = ["1", "2", "3"]  # Kaç ay sonra

        # Vade gün seçenekleri (1-28 arası - her ayda geçerli olsun)
        self.vade_gun_secenekleri = [str(i) for i in range(1, 29)]

        # Alliance
        self.create_depo_section(content_frame, "Alliance Healthcare", "ALLIANCE",
                                fields=[("Eczane Kodu", "ECZANE_KODU"), ("Kullanıcı Adı", "USERNAME"), ("Şifre", "PASSWORD"),
                                        ("Yetkili Adı", "YETKILI"), ("Cep Tel", "CEP"), ("Sabit Tel", "SABIT"), ("İade Bölümü", "IADE")])

        # Selçuk
        self.create_depo_section(content_frame, "Selçuk Ecza", "SELCUK",
                                fields=[("Hesap Kodu", "HESAP_KODU"), ("Kullanıcı Adı", "USERNAME"), ("Şifre", "PASSWORD"),
                                        ("Yetkili Adı", "YETKILI"), ("Cep Tel", "CEP"), ("Sabit Tel", "SABIT"), ("İade Bölümü", "IADE")])

        # Yusuf Paşa
        self.create_depo_section(content_frame, "Yusuf Paşa", "YUSUFPASA",
                                fields=[("Eczane Kodu", "ECZANE_KODU"), ("Kullanıcı Adı", "USERNAME"), ("Parola", "PASSWORD"),
                                        ("Yetkili Adı", "YETKILI"), ("Cep Tel", "CEP"), ("Sabit Tel", "SABIT"), ("İade Bölümü", "IADE")])

        # İstanbul Ecza Koop
        self.create_depo_section(content_frame, "İstanbul Ecza Koop", "ISKOOP",
                                fields=[("Kullanıcı Adı", "USERNAME"), ("Parola", "PASSWORD"),
                                        ("Yetkili Adı", "YETKILI"), ("Cep Tel", "CEP"), ("Sabit Tel", "SABIT"), ("İade Bölümü", "IADE")])

        # Bursa Ecza Koop
        self.create_depo_section(content_frame, "Bursa Ecza Koop", "BURSA",
                                fields=[("Kullanıcı Adı", "USERNAME"), ("Parola", "PASSWORD"),
                                        ("Yetkili Adı", "YETKILI"), ("Cep Tel", "CEP"), ("Sabit Tel", "SABIT"), ("İade Bölümü", "IADE")])

        # Farmazon
        self.create_depo_section(content_frame, "Farmazon", "FARMAZON",
                                fields=[("Kullanıcı Adı", "USERNAME"), ("Şifre", "PASSWORD"),
                                        ("Yetkili Adı", "YETKILI"), ("Cep Tel", "CEP"), ("Sabit Tel", "SABIT"), ("İade Bölümü", "IADE")])

        # Farmazon Kargo Ücreti (özel alan)
        farmazon_kargo_frame = tk.Frame(content_frame, bg="white")
        farmazon_kargo_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            farmazon_kargo_frame,
            text="Kargo Ücreti:",
            font=("Arial", 10),
            width=15,
            anchor=tk.W,
            bg="white"
        ).pack(side=tk.LEFT, padx=(30, 0))

        farmazon_kargo_entry = tk.Entry(farmazon_kargo_frame, font=("Arial", 10), width=10)
        farmazon_kargo_entry.pack(side=tk.LEFT, padx=10)
        farmazon_kargo_entry.insert(0, self.current_values.get("FARMAZON_KARGO", "140"))
        self.entries["FARMAZON_KARGO"] = farmazon_kargo_entry

        tk.Label(
            farmazon_kargo_frame,
            text="TL",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white"
        ).pack(side=tk.LEFT, padx=5)

        # Farmazon Maksimum Stok Süresi (özel alan)
        farmazon_max_frame = tk.Frame(content_frame, bg="white")
        farmazon_max_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            farmazon_max_frame,
            text="Maks. Stok Süresi:",
            font=("Arial", 10),
            width=15,
            anchor=tk.W,
            bg="white"
        ).pack(side=tk.LEFT, padx=(30, 0))

        farmazon_max_entry = tk.Entry(farmazon_max_frame, font=("Arial", 10), width=5)
        farmazon_max_entry.pack(side=tk.LEFT, padx=10)
        farmazon_max_entry.insert(0, self.current_values.get("FARMAZON_MAX_AY", "6"))
        self.entries["FARMAZON_MAX_AY"] = farmazon_max_entry

        tk.Label(
            farmazon_max_frame,
            text="ay (Kargo optimizasyonu için maks. alım)",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white"
        ).pack(side=tk.LEFT, padx=5)

        # Farmazon Uzun Miat checkbox
        farmazon_miat_frame = tk.Frame(content_frame, bg="white")
        farmazon_miat_frame.pack(fill=tk.X, pady=5)

        self.farmazon_uzun_miat_var = tk.BooleanVar(value=self.current_values.get("FARMAZON_UZUN_MIAT", "true").lower() == "true")
        farmazon_miat_cb = tk.Checkbutton(
            farmazon_miat_frame,
            text="8 Aydan Uzun Miatlı Ürünleri Al",
            variable=self.farmazon_uzun_miat_var,
            font=("Arial", 10),
            bg="white",
            activebackground="white"
        )
        farmazon_miat_cb.pack(side=tk.LEFT, padx=(30, 0))

        tk.Label(
            farmazon_miat_frame,
            text="(Kısa miatlı ucuz ürünleri atla)",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white"
        ).pack(side=tk.LEFT, padx=5)

        # Farmazon Pahalılık Eşiği (özel alan)
        farmazon_pahali_frame = tk.Frame(content_frame, bg="white")
        farmazon_pahali_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            farmazon_pahali_frame,
            text="Pahalılık Eşiği:",
            font=("Arial", 10),
            width=15,
            anchor=tk.W,
            bg="white"
        ).pack(side=tk.LEFT, padx=(30, 0))

        farmazon_pahali_entry = tk.Entry(farmazon_pahali_frame, font=("Arial", 10), width=5)
        farmazon_pahali_entry.pack(side=tk.LEFT, padx=10)
        farmazon_pahali_entry.insert(0, self.current_values.get("FARMAZON_PAHALI_ESIK", "10"))
        self.entries["FARMAZON_PAHALI_ESIK"] = farmazon_pahali_entry

        tk.Label(
            farmazon_pahali_frame,
            text="% (Fiyat×(1+eşik) > PSF ise 'Pahalı' uyarısı)",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white"
        ).pack(side=tk.LEFT, padx=5)

        # Sancak Ecza
        self.create_depo_section(content_frame, "Sancak Ecza", "SANCAK",
                                fields=[("GLN/TC Numarası", "USERNAME"), ("Parola", "PASSWORD"),
                                        ("Yetkili Adı", "YETKILI"), ("Cep Tel", "CEP"), ("Sabit Tel", "SABIT"), ("İade Bölümü", "IADE")])

        # Eczane Bilgileri
        eczane_label = tk.Label(
            content_frame,
            text="🏥 Eczane Bilgileri",
            font=("Arial", 11, "bold"),
            fg="#2C3E50",
            bg="white"
        )
        eczane_label.pack(anchor=tk.W, pady=(20, 5))

        # Separator
        separator_eczane = ttk.Separator(content_frame, orient=tk.HORIZONTAL)
        separator_eczane.pack(fill=tk.X, pady=(0, 10))

        # Eczacı Adı
        eczaci_adi_frame = tk.Frame(content_frame, bg="white")
        eczaci_adi_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            eczaci_adi_frame,
            text="Eczacı Adı:",
            font=("Arial", 10),
            width=15,
            anchor=tk.W,
            bg="white"
        ).pack(side=tk.LEFT)

        eczaci_adi_entry = tk.Entry(eczaci_adi_frame, font=("Arial", 10), width=40)
        eczaci_adi_entry.pack(side=tk.LEFT, padx=10)
        eczaci_adi_entry.insert(0, self.current_values.get("ECZACI_ADI", ""))
        self.entries["ECZACI_ADI"] = eczaci_adi_entry

        # Eczane Adı
        eczane_adi_frame = tk.Frame(content_frame, bg="white")
        eczane_adi_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            eczane_adi_frame,
            text="Eczane Adı:",
            font=("Arial", 10),
            width=15,
            anchor=tk.W,
            bg="white"
        ).pack(side=tk.LEFT)

        eczane_adi_entry = tk.Entry(eczane_adi_frame, font=("Arial", 10), width=40)
        eczane_adi_entry.pack(side=tk.LEFT, padx=10)
        eczane_adi_entry.insert(0, self.current_values.get("ECZANE_ADI", ""))
        self.entries["ECZANE_ADI"] = eczane_adi_entry

        # Eczane Telefonu
        eczane_tel_frame = tk.Frame(content_frame, bg="white")
        eczane_tel_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            eczane_tel_frame,
            text="Eczane Telefonu:",
            font=("Arial", 10),
            width=15,
            anchor=tk.W,
            bg="white"
        ).pack(side=tk.LEFT)

        eczane_tel_entry = tk.Entry(eczane_tel_frame, font=("Arial", 10), width=40)
        eczane_tel_entry.pack(side=tk.LEFT, padx=10)
        eczane_tel_entry.insert(0, self.current_values.get("ECZANE_TELEFONU", ""))
        self.entries["ECZANE_TELEFONU"] = eczane_tel_entry

        # Eczacı Telefonu
        eczaci_tel_frame = tk.Frame(content_frame, bg="white")
        eczaci_tel_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            eczaci_tel_frame,
            text="Eczacı Telefonu:",
            font=("Arial", 10),
            width=15,
            anchor=tk.W,
            bg="white"
        ).pack(side=tk.LEFT)

        eczaci_tel_entry = tk.Entry(eczaci_tel_frame, font=("Arial", 10), width=40)
        eczaci_tel_entry.pack(side=tk.LEFT, padx=10)
        eczaci_tel_entry.insert(0, self.current_values.get("ECZACI_TELEFONU", ""))
        self.entries["ECZACI_TELEFONU"] = eczaci_tel_entry

        # Sipariş Ayarları
        siparis_label = tk.Label(
            content_frame,
            text="⚙️ Sipariş Ayarları",
            font=("Arial", 11, "bold"),
            fg="#2C3E50",
            bg="white"
        )
        siparis_label.pack(anchor=tk.W, pady=(20, 5))

        # Separator
        separator = ttk.Separator(content_frame, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=(0, 10))

        # Gün sayısı input
        gun_frame = tk.Frame(content_frame, bg="white")
        gun_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            gun_frame,
            text="Kaç Günlük Sipariş:",
            font=("Arial", 10),
            width=15,
            anchor=tk.W,
            bg="white"
        ).pack(side=tk.LEFT)

        gun_entry = tk.Entry(gun_frame, font=("Arial", 10), width=10)
        gun_entry.pack(side=tk.LEFT, padx=10)
        gun_entry.insert(0, self.current_values.get("GUN_SAYISI", "30"))
        self.entries["GUN_SAYISI"] = gun_entry

        tk.Label(
            gun_frame,
            text="(Aylık ortalamaya göre hesaplanır)",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white"
        ).pack(side=tk.LEFT, padx=5)

        # Aylık Faiz Oranı input
        faiz_frame = tk.Frame(content_frame, bg="white")
        faiz_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            faiz_frame,
            text="Aylık Faiz Oranı:",
            font=("Arial", 10),
            width=15,
            anchor=tk.W,
            bg="white"
        ).pack(side=tk.LEFT)

        faiz_entry = tk.Entry(faiz_frame, font=("Arial", 10), width=10)
        faiz_entry.pack(side=tk.LEFT, padx=10)
        faiz_entry.insert(0, self.current_values.get("AYLIK_FAIZ", "4"))
        self.entries["AYLIK_FAIZ"] = faiz_entry

        tk.Label(
            faiz_frame,
            text="% (Efektif maliyet hesabı için)",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white"
        ).pack(side=tk.LEFT, padx=5)

        # Efektif Fiyat Göster checkbox
        efektif_frame = tk.Frame(content_frame, bg="white")
        efektif_frame.pack(fill=tk.X, pady=10)

        show_efektif_var = tk.BooleanVar()
        show_efektif_value = self.current_values.get("SHOW_EFEKTIF_FIYAT", "true").lower() == "true"
        show_efektif_var.set(show_efektif_value)
        self.checkboxes["SHOW_EFEKTIF_FIYAT"] = show_efektif_var

        show_efektif_cb = tk.Checkbutton(
            efektif_frame,
            text="Efektif Fiyat Göster (Finansal maliyet dahil hesaplanmış fiyat)",
            variable=show_efektif_var,
            bg="white",
            font=("Arial", 10)
        )
        show_efektif_cb.pack(anchor=tk.W)

        tk.Label(
            efektif_frame,
            text="• İşaretli: Fiyatların yanında parantez içinde efektif fiyat gösterilir\n• Örn: 520,84 (485,20) - stok, vade ve faize göre gerçek maliyet",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white",
            justify=tk.LEFT
        ).pack(anchor=tk.W, padx=25, pady=(5, 0))

        # Fiyatları Göster checkbox
        fiyat_frame = tk.Frame(content_frame, bg="white")
        fiyat_frame.pack(fill=tk.X, pady=10)

        show_prices_var = tk.BooleanVar()
        show_prices_value = self.current_values.get("SHOW_PRICES", "true").lower() == "true"
        show_prices_var.set(show_prices_value)
        self.checkboxes["SHOW_PRICES"] = show_prices_var

        show_prices_cb = tk.Checkbutton(
            fiyat_frame,
            text="Fiyatları Göster (Farmazon ve Alliance fiyatlarını Açıklama alanında göster)",
            variable=show_prices_var,
            bg="white",
            font=("Arial", 10)
        )
        show_prices_cb.pack(anchor=tk.W)

        tk.Label(
            fiyat_frame,
            text="• İşaretli: Fz:270,00/300,40 All, Sel, Bur\n• İşaretsiz: Fz, All, Sel, Bur",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white",
            justify=tk.LEFT
        ).pack(anchor=tk.W, padx=25, pady=(5, 0))

        # MF (Mal Fazlası) Özelliği checkbox
        mf_frame = tk.Frame(content_frame, bg="white")
        mf_frame.pack(fill=tk.X, pady=10)

        mf_enabled_var = tk.BooleanVar()
        mf_enabled_value = self.current_values.get("MF_ENABLED", "true").lower() == "true"
        mf_enabled_var.set(mf_enabled_value)
        self.checkboxes["MF_ENABLED"] = mf_enabled_var

        mf_enabled_cb = tk.Checkbutton(
            mf_frame,
            text="MF (Mal Fazlası) Özelliği (İlaçların toplu alım bonuslarını göster)",
            variable=mf_enabled_var,
            bg="white",
            font=("Arial", 10)
        )
        mf_enabled_cb.pack(anchor=tk.W)

        tk.Label(
            mf_frame,
            text="• İşaretli: Ürün adında (10+2) gösterir, daha yavaş tarama\n• İşaretsiz: MF bilgisi gösterilmez, daha hızlı tarama",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white",
            justify=tk.LEFT
        ).pack(anchor=tk.W, padx=25, pady=(5, 0))

        # Debug Logging checkbox
        debug_frame = tk.Frame(content_frame, bg="white")
        debug_frame.pack(fill=tk.X, pady=10)

        debug_logging_var = tk.BooleanVar()
        debug_logging_value = self.current_values.get("DEBUG_LOGGING", "false").lower() == "true"
        debug_logging_var.set(debug_logging_value)
        self.checkboxes["DEBUG_LOGGING"] = debug_logging_var

        debug_logging_cb = tk.Checkbutton(
            debug_frame,
            text="Debug Logları (Geliştirme/Hata ayıklama için detaylı loglar)",
            variable=debug_logging_var,
            bg="white",
            font=("Arial", 10)
        )
        debug_logging_cb.pack(anchor=tk.W)

        tk.Label(
            debug_frame,
            text="• İşaretli: Tüm DEBUG logları dosyaya yazılır (yavaş)\n• İşaretsiz: Sadece WARNING/ERROR loglar yazılır (hızlı - önerilen)",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white",
            justify=tk.LEFT
        ).pack(anchor=tk.W, padx=25, pady=(5, 0))

        # Tarayıcı Modu (Tek Pencere / Ayrı Pencereler)
        browser_frame = tk.Frame(content_frame, bg="white")
        browser_frame.pack(fill=tk.X, pady=10)

        tk.Label(
            browser_frame,
            text="Tarayıcı Modu:",
            font=("Arial", 10, "bold"),
            bg="white"
        ).pack(anchor=tk.W)

        browser_mode_var = tk.StringVar()
        browser_mode_value = self.current_values.get("BROWSER_MODE", "tabs")
        browser_mode_var.set(browser_mode_value)
        self.browser_mode_var = browser_mode_var

        radio_frame = tk.Frame(browser_frame, bg="white")
        radio_frame.pack(anchor=tk.W, padx=20, pady=5)

        tk.Radiobutton(
            radio_frame,
            text="Tek Pencere (Sekmeler)",
            variable=browser_mode_var,
            value="tabs",
            bg="white",
            font=("Arial", 10)
        ).pack(anchor=tk.W)

        tk.Label(
            radio_frame,
            text="Tüm depolar aynı tarayıcıda sekme olarak açılır (daha az kaynak kullanır)",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white"
        ).pack(anchor=tk.W, padx=20)

        tk.Radiobutton(
            radio_frame,
            text="Ayrı Pencereler",
            variable=browser_mode_var,
            value="windows",
            bg="white",
            font=("Arial", 10)
        ).pack(anchor=tk.W, pady=(10, 0))

        tk.Label(
            radio_frame,
            text="Her depo kendi penceresinde açılır (paralel çalışır, daha hızlı olabilir)",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white"
        ).pack(anchor=tk.W, padx=20)

        # Depo Sıralama Bölümü
        self.create_depo_siralama_section(content_frame)

        # Tehlikeli Bölge - Tüm Verileri Sıfırla (kaydırılabilir alanın içinde, en altta)
        danger_frame = tk.LabelFrame(
            content_frame,
            text="Tehlikeli Bölge",
            font=("Arial", 10, "bold"),
            fg="#C0392B",
            bg="#FADBD8",
            padx=10,
            pady=10
        )
        danger_frame.pack(fill=tk.X, pady=(20, 10))

        tk.Label(
            danger_frame,
            text="Bu işlem tüm ayarları ve verileri siler, geri alınamaz!",
            font=("Arial", 9),
            bg="#FADBD8",
            fg="#C0392B"
        ).pack(anchor=tk.W, pady=(0, 10))

        reset_all_button = tk.Button(
            danger_frame,
            text="Tüm Ayarları ve Datayı Sıfırla",
            command=self.tum_verileri_sifirla,
            bg="#C0392B",
            fg="white",
            activebackground="#A93226",
            activeforeground="white",
            font=("Arial", 10, "bold"),
            width=25,
            height=1
        )
        reset_all_button.pack(anchor=tk.W)

        tk.Label(
            danger_frame,
            text="(Programı başka birine verirken kullanın)",
            font=("Arial", 8),
            bg="#FADBD8",
            fg="#666666"
        ).pack(anchor=tk.W, pady=(5, 0))

        # Butonlar (sabit, en altta)
        button_frame = tk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=20, pady=20)

        save_button = tk.Button(
            button_frame,
            text="Kaydet",
            command=self.save_settings,
            bg="#27AE60",
            fg="white",
            font=("Arial", 11, "bold"),
            width=15,
            height=2
        )
        save_button.pack(side=tk.LEFT, padx=5)

        cancel_button = tk.Button(
            button_frame,
            text="İptal",
            command=self.window.destroy,
            bg="#95A5A6",
            fg="white",
            font=("Arial", 11, "bold"),
            width=15,
            height=2
        )
        cancel_button.pack(side=tk.LEFT, padx=5)

    def create_depo_section(self, parent, depo_name, prefix, fields):
        """Depo bilgileri için section oluştur

        Args:
            parent: Ana frame
            depo_name: Depo adı
            prefix: Env key prefix'i
            fields: [(label, field_key), ...] listesi
        """

        # Depo başlığı ve checkbox frame
        header_frame = tk.Frame(parent, bg="white")
        header_frame.pack(fill=tk.X, pady=(10, 5))

        # Checkbox (Bu depoyu kullan)
        enabled_var = tk.BooleanVar()
        enabled_key = f"{prefix}_ENABLED"
        enabled_value = self.current_values.get(enabled_key, "true").lower() == "true"
        enabled_var.set(enabled_value)
        self.checkboxes[enabled_key] = enabled_var

        checkbox = tk.Checkbutton(
            header_frame,
            text="",
            variable=enabled_var,
            bg="white",
            font=("Arial", 10)
        )
        checkbox.pack(side=tk.LEFT)

        # Depo başlığı
        depo_label = tk.Label(
            header_frame,
            text=f"📦 {depo_name}",
            font=("Arial", 11, "bold"),
            fg="#2C3E50",
            bg="white"
        )
        depo_label.pack(side=tk.LEFT, padx=(5, 0))

        # Separator
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=(0, 10))

        # Her alan için input oluştur
        for label_text, field_key in fields:
            field_frame = tk.Frame(parent, bg="white")
            field_frame.pack(fill=tk.X, pady=5)

            tk.Label(
                field_frame,
                text=f"{label_text}:",
                font=("Arial", 10),
                width=15,
                anchor=tk.W,
                bg="white"
            ).pack(side=tk.LEFT, padx=(30, 0))  # Sol padding artırıldı (checkbox için)

            # Şifre alanı mı kontrol et
            is_password = "PASSWORD" in field_key or "Parola" in label_text or "Şifre" in label_text

            # Şifre alanı için show="*"
            show_char = "*" if is_password else None

            entry = tk.Entry(field_frame, font=("Arial", 10), width=30, show=show_char)
            entry.pack(side=tk.LEFT, padx=10)

            # Mevcut değeri yükle
            env_key = f"{prefix}_{field_key}"
            entry.insert(0, self.current_values.get(env_key, ""))
            self.entries[env_key] = entry

            # Şifre alanıysa "Göster/Gizle" butonu ekle
            if is_password:
                toggle_btn = tk.Button(
                    field_frame,
                    text="👁",
                    font=("Arial", 12),
                    width=3,
                    height=1,
                    relief=tk.FLAT,
                    bg="#ECF0F1",
                    fg="#2C3E50",
                    cursor="hand2",
                    command=lambda e=entry: self.toggle_password_visibility(e)
                )
                toggle_btn.pack(side=tk.LEFT, padx=5)

                # Tooltip ekle (isteğe bağlı)
                tk.Label(
                    field_frame,
                    text="(Göster/Gizle)",
                    font=("Arial", 8),
                    fg="#95A5A6",
                    bg="white"
                ).pack(side=tk.LEFT, padx=2)

        # Ödeme Tipi seçimi (Vade veya Kredi Kartı)
        odeme_tipi_frame = tk.Frame(parent, bg="white")
        odeme_tipi_frame.pack(fill=tk.X, pady=5)

        tk.Label(
            odeme_tipi_frame,
            text="Ödeme Tipi:",
            font=("Arial", 10),
            width=15,
            anchor=tk.W,
            bg="white"
        ).pack(side=tk.LEFT, padx=(30, 0))

        odeme_tipi_key = f"{prefix}_ODEME_TIPI"
        current_odeme_tipi = self.current_values.get(odeme_tipi_key, "vade")

        odeme_tipi_var = tk.StringVar(value=current_odeme_tipi)
        self.odeme_tipi_vars[odeme_tipi_key] = odeme_tipi_var

        # Vade ve Kredi Kartı seçenekleri için frame'ler
        vade_secenekleri_frame = tk.Frame(parent, bg="white")
        kk_secenekleri_frame = tk.Frame(parent, bg="white")

        def toggle_odeme_secenekleri():
            if odeme_tipi_var.get() == "vade":
                vade_secenekleri_frame.pack(fill=tk.X, pady=2)
                kk_secenekleri_frame.pack_forget()
            else:
                vade_secenekleri_frame.pack_forget()
                kk_secenekleri_frame.pack(fill=tk.X, pady=2)

        vade_radio = tk.Radiobutton(
            odeme_tipi_frame,
            text="Vade",
            variable=odeme_tipi_var,
            value="vade",
            bg="white",
            font=("Arial", 10),
            command=toggle_odeme_secenekleri
        )
        vade_radio.pack(side=tk.LEFT, padx=(10, 5))

        kk_radio = tk.Radiobutton(
            odeme_tipi_frame,
            text="Kredi Kartı",
            variable=odeme_tipi_var,
            value="kredi_karti",
            bg="white",
            font=("Arial", 10),
            command=toggle_odeme_secenekleri
        )
        kk_radio.pack(side=tk.LEFT, padx=5)

        # VADE SEÇENEKLERİ
        tk.Label(
            vade_secenekleri_frame,
            text="",
            width=15,
            bg="white"
        ).pack(side=tk.LEFT, padx=(30, 0))

        # Kaç ay sonra
        vade_ay_key = f"{prefix}_VADE_AY"
        current_vade_ay = self.current_values.get(vade_ay_key, "1")

        vade_ay_combo = ttk.Combobox(
            vade_secenekleri_frame,
            values=self.vade_ay_secenekleri,
            state="readonly",
            font=("Arial", 10),
            width=3
        )
        vade_ay_combo.pack(side=tk.LEFT, padx=(10, 2))
        vade_ay_combo.set(current_vade_ay)
        self.vade_ay_combos[vade_ay_key] = vade_ay_combo

        tk.Label(
            vade_secenekleri_frame,
            text=". ayın",
            font=("Arial", 10),
            bg="white"
        ).pack(side=tk.LEFT, padx=(2, 5))

        # Ayın kaçıncı günü
        vade_gun_key = f"{prefix}_VADE_GUN"
        current_vade_gun = self.current_values.get(vade_gun_key, "15")

        vade_gun_combo = ttk.Combobox(
            vade_secenekleri_frame,
            values=self.vade_gun_secenekleri,
            state="readonly",
            font=("Arial", 10),
            width=3
        )
        vade_gun_combo.pack(side=tk.LEFT, padx=(5, 2))
        vade_gun_combo.set(current_vade_gun)
        self.vade_gun_combos[vade_gun_key] = vade_gun_combo

        tk.Label(
            vade_secenekleri_frame,
            text="'i",
            font=("Arial", 10),
            bg="white"
        ).pack(side=tk.LEFT, padx=(2, 10))

        # KREDİ KARTI SEÇENEKLERİ
        tk.Label(
            kk_secenekleri_frame,
            text="",
            width=15,
            bg="white"
        ).pack(side=tk.LEFT, padx=(30, 0))

        tk.Label(
            kk_secenekleri_frame,
            text="Kesim:",
            font=("Arial", 10),
            bg="white"
        ).pack(side=tk.LEFT, padx=(10, 2))

        kk_kesim_key = f"{prefix}_KK_KESIM"
        current_kk_kesim = self.current_values.get(kk_kesim_key, "28")

        kk_kesim_combo = ttk.Combobox(
            kk_secenekleri_frame,
            values=self.vade_gun_secenekleri,
            state="readonly",
            font=("Arial", 10),
            width=3
        )
        kk_kesim_combo.pack(side=tk.LEFT, padx=(2, 5))
        kk_kesim_combo.set(current_kk_kesim)
        self.kk_kesim_combos[kk_kesim_key] = kk_kesim_combo

        tk.Label(
            kk_secenekleri_frame,
            text="'i, Ödeme:",
            font=("Arial", 10),
            bg="white"
        ).pack(side=tk.LEFT, padx=(2, 2))

        kk_odeme_key = f"{prefix}_KK_ODEME"
        current_kk_odeme = self.current_values.get(kk_odeme_key, "7")

        kk_odeme_combo = ttk.Combobox(
            kk_secenekleri_frame,
            values=self.vade_gun_secenekleri,
            state="readonly",
            font=("Arial", 10),
            width=3
        )
        kk_odeme_combo.pack(side=tk.LEFT, padx=(2, 2))
        kk_odeme_combo.set(current_kk_odeme)
        self.kk_odeme_combos[kk_odeme_key] = kk_odeme_combo

        tk.Label(
            kk_secenekleri_frame,
            text="'si",
            font=("Arial", 10),
            bg="white"
        ).pack(side=tk.LEFT, padx=(2, 10))

        # Başlangıçta doğru seçeneği göster
        toggle_odeme_secenekleri()

    def toggle_password_visibility(self, entry):
        """Şifre görünürlüğünü değiştir (Göster/Gizle)"""
        if entry.cget("show") == "*":
            entry.config(show="")  # Şifreyi göster
        else:
            entry.config(show="*")  # Şifreyi gizle

    def create_depo_siralama_section(self, parent):
        """Depo sıralama bölümünü oluştur (yukarı/aşağı butonlarla)"""

        # Depo isim mapping
        self.depo_display_names = {
            "alliance": "Alliance Healthcare",
            "selcuk": "Selcuk Ecza",
            "yusufpasa": "Yusuf Pasa",
            "iskoop": "Istanbul Ecza Koop",
            "bursa": "Bursa Ecza Koop",
            "farmazon": "Farmazon",
            "sancak": "Sancak Ecza"
        }

        # Varsayılan sıralama
        default_order = ["alliance", "selcuk", "yusufpasa", "iskoop", "bursa", "farmazon", "sancak"]

        # Mevcut sıralamayı .env'den oku
        current_order_str = self.current_values.get("DEPO_SIRALAMA", "")
        if current_order_str:
            self.depo_order = [d.strip() for d in current_order_str.split(",") if d.strip() in default_order]
            # Eksik depoları ekle
            for d in default_order:
                if d not in self.depo_order:
                    self.depo_order.append(d)
        else:
            self.depo_order = default_order.copy()

        # Başlık
        siralama_label = tk.Label(
            parent,
            text="Depo Oncelik Sirasi",
            font=("Arial", 11, "bold"),
            fg="#2C3E50",
            bg="white"
        )
        siralama_label.pack(anchor=tk.W, pady=(20, 5))

        # Separator
        separator = ttk.Separator(parent, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, pady=(0, 10))

        # Açıklama
        tk.Label(
            parent,
            text="Depolari oncelik sirasina gore siralayin. Ustdeki depolar once sorgulanir.",
            font=("Arial", 9),
            fg="#7F8C8D",
            bg="white",
            justify=tk.LEFT
        ).pack(anchor=tk.W, pady=(0, 10))

        # Ana frame (listbox + butonlar)
        siralama_frame = tk.Frame(parent, bg="white")
        siralama_frame.pack(fill=tk.X, pady=5)

        # Listbox
        listbox_frame = tk.Frame(siralama_frame, bg="white")
        listbox_frame.pack(side=tk.LEFT, padx=(0, 10))

        self.depo_listbox = tk.Listbox(
            listbox_frame,
            font=("Arial", 10),
            width=30,
            height=7,
            selectmode=tk.SINGLE,
            bg="#f8f9fa",
            selectbackground="#3498DB",
            selectforeground="white",
            relief=tk.RIDGE
        )
        self.depo_listbox.pack(side=tk.LEFT)

        # Listbox'a depoları ekle
        for depo_key in self.depo_order:
            display_name = self.depo_display_names.get(depo_key, depo_key)
            self.depo_listbox.insert(tk.END, f"  {display_name}")

        # Scrollbar
        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.depo_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.depo_listbox.config(yscrollcommand=scrollbar.set)

        # Butonlar frame
        button_frame = tk.Frame(siralama_frame, bg="white")
        button_frame.pack(side=tk.LEFT, fill=tk.Y)

        # Yukarı butonu
        up_btn = tk.Button(
            button_frame,
            text="Yukari",
            command=self.move_depo_up,
            bg="#3498DB",
            fg="white",
            font=("Arial", 10, "bold"),
            width=10,
            height=1,
            cursor="hand2"
        )
        up_btn.pack(pady=5)

        # Aşağı butonu
        down_btn = tk.Button(
            button_frame,
            text="Asagi",
            command=self.move_depo_down,
            bg="#3498DB",
            fg="white",
            font=("Arial", 10, "bold"),
            width=10,
            height=1,
            cursor="hand2"
        )
        down_btn.pack(pady=5)

        # Sıfırla butonu
        reset_btn = tk.Button(
            button_frame,
            text="Sifirla",
            command=self.reset_depo_order,
            bg="#95A5A6",
            fg="white",
            font=("Arial", 10),
            width=10,
            height=1,
            cursor="hand2"
        )
        reset_btn.pack(pady=20)

        # Açıklama
        tk.Label(
            parent,
            text="1 = En yuksek oncelik (ilk sorgulanir)",
            font=("Arial", 9),
            fg="#27AE60",
            bg="white"
        ).pack(anchor=tk.W, pady=(5, 0))

    def move_depo_up(self):
        """Secili depoyu yukarı taşı"""
        selection = self.depo_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx == 0:
            return  # Zaten en üstte

        # Listbox'ta taşı
        item = self.depo_listbox.get(idx)
        self.depo_listbox.delete(idx)
        self.depo_listbox.insert(idx - 1, item)
        self.depo_listbox.selection_set(idx - 1)

        # Depo sıralamasını güncelle
        self.depo_order[idx], self.depo_order[idx - 1] = self.depo_order[idx - 1], self.depo_order[idx]

    def move_depo_down(self):
        """Secili depoyu aşağı taşı"""
        selection = self.depo_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx >= self.depo_listbox.size() - 1:
            return  # Zaten en altta

        # Listbox'ta taşı
        item = self.depo_listbox.get(idx)
        self.depo_listbox.delete(idx)
        self.depo_listbox.insert(idx + 1, item)
        self.depo_listbox.selection_set(idx + 1)

        # Depo sıralamasını güncelle
        self.depo_order[idx], self.depo_order[idx + 1] = self.depo_order[idx + 1], self.depo_order[idx]

    def reset_depo_order(self):
        """Depo sıralamasını varsayılana sıfırla"""
        default_order = ["alliance", "selcuk", "yusufpasa", "iskoop", "bursa", "farmazon", "sancak"]
        self.depo_order = default_order.copy()

        # Listbox'ı güncelle
        self.depo_listbox.delete(0, tk.END)
        for depo_key in self.depo_order:
            display_name = self.depo_display_names.get(depo_key, depo_key)
            self.depo_listbox.insert(tk.END, f"  {display_name}")

    def save_settings(self):
        """Ayarları .env dosyasına kaydet"""
        try:
            # Mevcut .env dosyasını oku (diğer ayarları korumak için)
            existing_lines = []
            if self.env_path.exists():
                with open(self.env_path, 'r', encoding='utf-8') as f:
                    existing_lines = f.readlines()

            # Önceki ENABLED değerlerini kaydet (yeni açılan depoları tespit için)
            old_enabled = {}
            for key in ["SELCUK_ENABLED", "SANCAK_ENABLED", "ALLIANCE_ENABLED",
                        "YUSUFPASA_ENABLED", "ISKOOP_ENABLED", "BURSA_ENABLED", "FARMAZON_ENABLED"]:
                old_enabled[key] = self.current_values.get(key, "false").lower() == "true"

            # Yeni değerleri hazırla (entry ve checkbox)
            new_values = {}

            # Entry'lerden değerleri al
            for key, entry in self.entries.items():
                new_values[key] = entry.get().strip()

            # Checkbox'lardan değerleri al
            for key, checkbox_var in self.checkboxes.items():
                new_values[key] = "true" if checkbox_var.get() else "false"

            # Ödeme tipi değerlerini al
            for key, var in self.odeme_tipi_vars.items():
                new_values[key] = var.get()

            # Vade ay combobox'lardan değerleri al
            for key, combo in self.vade_ay_combos.items():
                new_values[key] = combo.get()

            # Vade gün combobox'lardan değerleri al
            for key, combo in self.vade_gun_combos.items():
                new_values[key] = combo.get()

            # Kredi kartı kesim günü combobox'lardan değerleri al
            for key, combo in self.kk_kesim_combos.items():
                new_values[key] = combo.get()

            # Kredi kartı ödeme günü combobox'lardan değerleri al
            for key, combo in self.kk_odeme_combos.items():
                new_values[key] = combo.get()

            # Yeni açılan depoları tespit et
            newly_enabled_depots = []
            depo_key_map = {
                "SELCUK_ENABLED": "selcuk",
                "SANCAK_ENABLED": "sancak",
                "ALLIANCE_ENABLED": "alliance",
                "YUSUFPASA_ENABLED": "yusufpasa",
                "ISKOOP_ENABLED": "iskoop",
                "BURSA_ENABLED": "bursa",
                "FARMAZON_ENABLED": "farmazon"
            }
            for key, depo_name in depo_key_map.items():
                was_enabled = old_enabled.get(key, False)
                is_enabled = new_values.get(key, "false").lower() == "true"
                if is_enabled and not was_enabled:
                    newly_enabled_depots.append(depo_name)

            # Depo sıralamasını ekle
            if hasattr(self, 'depo_order') and self.depo_order:
                new_values["DEPO_SIRALAMA"] = ",".join(self.depo_order)

            # Tarayıcı modunu ekle
            if hasattr(self, 'browser_mode_var'):
                new_values["BROWSER_MODE"] = self.browser_mode_var.get()

            # Farmazon uzun miat ayarını ekle
            if hasattr(self, 'farmazon_uzun_miat_var'):
                new_values["FARMAZON_UZUN_MIAT"] = "true" if self.farmazon_uzun_miat_var.get() else "false"

            # Dosyayı güncelle
            updated_lines = []
            updated_keys = set()

            for line in existing_lines:
                stripped = line.strip()
                if '=' in stripped and not stripped.startswith('#'):
                    key = stripped.split('=', 1)[0].strip()
                    if key in new_values:
                        updated_lines.append(f"{key}={new_values[key]}\n")
                        updated_keys.add(key)
                    else:
                        updated_lines.append(line)
                else:
                    updated_lines.append(line)

            # Yeni eklenen keyler
            for key, value in new_values.items():
                if key not in updated_keys:
                    updated_lines.append(f"{key}={value}\n")

            # Dosyaya yaz
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.writelines(updated_lines)

            # .env dosyasını yeniden yükle (os.environ'e uygula)
            from dotenv import load_dotenv
            load_dotenv(self.env_path, override=True)

            # Ana pencereyi güncelle (sütunları yeniden oluştur)
            if self.main_window and hasattr(self.main_window, 'refresh_ui'):
                self.main_window.refresh_ui()

            # Yeni açılan depolar varsa ve tarama devam ediyorsa, depoları aç
            if newly_enabled_depots and self.main_window:
                if hasattr(self.main_window, 'on_new_depots_enabled'):
                    self.main_window.on_new_depots_enabled(newly_enabled_depots)

            messagebox.showinfo("Başarılı", "Ayarlar kaydedildi ve uygulandı!")
            self.window.destroy()

        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar kaydedilemedi: {e}")

    def tum_verileri_sifirla(self):
        """Tüm ayarları ve verileri sıfırla - 2 aşamalı onay"""
        # İlk onay
        ilk_onay = messagebox.askyesno(
            "Tüm Verileri Sıfırla",
            "DİKKAT!\n\n"
            "Bu işlem aşağıdaki TÜM verileri silecek:\n"
            "• Tüm depo giriş bilgileri\n"
            "• Eczane ve eczacı bilgileri\n"
            "• Sipariş ayarları\n"
            "• Tarama geçmişi\n"
            "• Aylık satış verileri\n\n"
            "Devam etmek istiyor musunuz?",
            icon='warning',
            parent=self.window
        )

        if not ilk_onay:
            return

        # İkinci onay - daha ciddi uyarı
        ikinci_onay = messagebox.askyesno(
            "SON UYARI",
            "⚠️ BU İŞLEM GERİ ALINAMAZ! ⚠️\n\n"
            "Tüm depo şifreleri, ayarlar ve\n"
            "veriler kalıcı olarak silinecek.\n\n"
            "Program arkadaşınıza verilmeye hazır\n"
            "hale gelecek.\n\n"
            "Silmek istediğinizden EMİN MİSİNİZ?",
            icon='warning',
            parent=self.window
        )

        if not ikinci_onay:
            return

        try:
            from src.utils import logger

            # Silinecek dosyalar
            base_dir = Path(__file__).resolve().parent.parent.parent
            silinecek_dosyalar = [
                base_dir / ".env",
                base_dir / "data" / "last_scan.json",
                base_dir / "data" / "monthly_sales.csv",
                base_dir / "data" / "ilaclistesi-altalta.txt",
                base_dir / "data" / "ilaclistesi-ayiracile.txt",
            ]

            silinen_sayisi = 0
            for dosya in silinecek_dosyalar:
                if dosya.exists():
                    dosya.unlink()
                    silinen_sayisi += 1
                    logger.info(f"Silindi: {dosya}")

            # logs klasöründeki dosyaları da sil (opsiyonel)
            logs_dir = base_dir / "logs"
            if logs_dir.exists():
                for log_file in logs_dir.glob("*.log"):
                    log_file.unlink()
                    silinen_sayisi += 1

            logger.info(f"Tüm veriler sıfırlandı. {silinen_sayisi} dosya silindi.")

            messagebox.showinfo(
                "Sıfırlama Tamamlandı",
                f"✓ Tüm veriler başarıyla silindi.\n\n"
                f"{silinen_sayisi} dosya silindi.\n\n"
                "Program artık yeni bir kullanıcıya\n"
                "verilmeye hazır.\n\n"
                "Programı yeniden başlatmanız önerilir.",
                parent=self.window
            )

            # Pencereyi kapat
            self.window.destroy()

        except Exception as e:
            logger.error(f"Veri sıfırlama hatası: {e}")
            messagebox.showerror(
                "Hata",
                f"Sıfırlama sırasında hata oluştu:\n{e}",
                parent=self.window
            )
