"""
Ana GUI penceresi
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import win32gui
from ..utils import logger
from .settings_window import SettingsWindow
from .kiyas_window import KiyasmotoruWindow


def turkish_lower(s):
    """Turkish-safe lowercase conversion

    Python'un .lower() fonksiyonu Turkish karakterleri doğru işlemez:
    - İ (noktalı büyük i) → Python i̇ yapar (i + combining dot), doğrusu i
    - I (noktasız büyük i) → Python i yapar, doğrusu ı

    Bu fonksiyon önce Turkish büyük harfleri değiştirir, sonra lower() yapar.
    """
    if not s:
        return ""
    return s.replace('İ', 'i').replace('I', 'ı').lower()


class Tooltip:
    """Modern tooltip sistemi - Butonlara fare ile gelince aciklama gosterir"""

    def __init__(self, widget, text, bg="#1a1a2e", fg="#eee"):
        self.widget = widget
        self.text = text
        self.bg = bg
        self.fg = fg
        self.tooltip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_attributes("-topmost", True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tooltip,
            text=self.text,
            bg=self.bg,
            fg=self.fg,
            font=("Segoe UI", 9),
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=4
        )
        label.pack()

    def hide(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None


class MainWindow:
    """Ana GUI penceresi"""

    def __init__(self, controller):
        """
        Args:
            controller: Ana koordinasyon controller'ı
        """
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("Siparişçi")

        # Ürün listesi
        self.products = []
        self.quantity_edit = {"entry": None, "item": None}

        # Tarama durumu
        self.is_scanning = False
        self.is_paused = False
        self.pause_event = threading.Event()
        self.pause_event.set()  # Başlangıçta pause değil

        # Kıyas modu durumu
        self.kiyas_mode = False
        self.kiyas_scanning = False
        self.kiyas_thread = None
        self.kiyas_ilac_listesi = []
        self.kiyas_toplam = 0
        self.kiyas_current = 0
        self.kiyas_range = (0, 100)

        # Barkod yapıştır modu
        self.barkod_yapistir_mode = False

        # Tarama süresi tracking
        self.start_time = None
        self.pause_start_time = None
        self.elapsed_seconds = 0
        self.timer_job = None
        self.last_product_start_time = None  # Son ilaç başlangıç zamanı
        self.last_product_duration = 0  # Son ilaç süresi (saniye)

        # Kullanılabilir depoları al (checkbox seçili + kullanıcı bilgileri var)
        self.available_depolar = controller.get_available_depolar() if controller else {}

        # Pencere kapanırken depoları kapat
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # UI oluştur
        self.create_widgets()

        # GUI ilk açıldığında sağ tarafa konumlandır (%90 yükseklik)
        # Pencere render olduktan sonra konumlandır (after ile 100ms gecikme)
        self.root.after(100, self.position_initial)

        # NOT: Botanik Sipariş Yardımcısı konumlandırması artık eos_controller.py içinde yapılıyor
        # (_connect_to_siparis_window metodunda, bağlantı kurulduğunda otomatik)

        # İlaç listesini CSV'den yükle (autocomplete için)
        self.load_ilac_listesi()

    def create_widgets(self):
        """UI bileşenlerini oluştur"""

        # Acik tema renkleri (modern, sik)
        self.colors = {
            "bg_dark": "#f5f6fa",      # Acik gri arka plan
            "bg_medium": "#dcdde1",    # Orta gri
            "bg_light": "#ffffff",     # Beyaz
            "accent": "#e74c3c",       # Kirmizi vurgu
            "accent_hover": "#c0392b",
            "text": "#2c3e50",         # Koyu yazi
            "text_dim": "#7f8c8d",     # Soluk yazi
            "success": "#27ae60",      # Yesil
            "warning": "#f39c12",      # Turuncu
            "info": "#3498db"          # Mavi
        }

        # Ana pencere arka planı
        self.root.configure(bg=self.colors["bg_dark"])

        # Başlık frame - MODERN DARK
        title_frame = tk.Frame(self.root, bg=self.colors["bg_medium"], height=40)
        title_frame.pack(fill=tk.X)

        # Başlık metni (sol)
        title_label = tk.Label(
            title_frame,
            text="Siparişçi",
            font=("Segoe UI", 12, "bold"),
            bg=self.colors["bg_medium"],
            fg=self.colors["text"]
        )
        title_label.pack(side=tk.LEFT, pady=8, padx=15)

        # Yardım butonu - Soru işareti simgesi
        self.help_button = tk.Button(
            title_frame,
            text="?",
            command=self.show_help,
            bg=self.colors["info"],
            fg="white",
            font=("Segoe UI", 12, "bold"),
            width=2,
            height=1,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors["accent"],
            activeforeground="white"
        )
        self.help_button.pack(side=tk.RIGHT, pady=5, padx=5)
        Tooltip(self.help_button, "Kullanim Kilavuzu")

        # Ayarlar butonu (sağ üst) - Çark simgesi
        self.settings_button = tk.Button(
            title_frame,
            text="\u2699",
            command=self.open_settings,
            bg=self.colors["bg_light"],
            fg=self.colors["text"],
            font=("Segoe UI", 14),
            width=2,
            height=1,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors["accent"],
            activeforeground="white"
        )
        self.settings_button.pack(side=tk.RIGHT, pady=5, padx=10)
        Tooltip(self.settings_button, "Ayarlar - Depo bilgileri ve tercihler")

        # Barkod Yapıştır butonu - Clipboard simgesi
        self.barkod_yapistir_button = tk.Button(
            title_frame,
            text="📋",
            command=self.open_barkod_yapistir,
            bg="#9b59b6",  # Mor renk
            fg="white",
            font=("Segoe UI", 12),
            width=2,
            height=1,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors["accent"],
            activeforeground="white"
        )
        self.barkod_yapistir_button.pack(side=tk.RIGHT, pady=5, padx=5)
        Tooltip(self.barkod_yapistir_button, "Barkod Yapıştır - Çoklu barkod tarama")

        # Kıyas Motoru butonu - Terazi simgesi
        self.kiyas_button = tk.Button(
            title_frame,
            text="⚖",
            command=self.open_kiyas_motoru,
            bg=self.colors["info"],
            fg="white",
            font=("Segoe UI", 14),
            width=2,
            height=1,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors["accent"],
            activeforeground="white"
        )
        self.kiyas_button.pack(side=tk.RIGHT, pady=5, padx=5)
        Tooltip(self.kiyas_button, "Kıyas Motoru - Tüm ilaçları karşılaştır")

        # HTML Kaydet butonu - Disket simgesi
        self.html_save_button = tk.Button(
            title_frame,
            text="\U0001F4BE",
            command=self.save_html,
            bg=self.colors["warning"],
            fg="white",
            font=("Segoe UI", 12),
            width=2,
            height=1,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors["accent"],
            activeforeground="white"
        )
        self.html_save_button.pack(side=tk.RIGHT, pady=5, padx=5)
        Tooltip(self.html_save_button, "HTML olarak kaydet")

        # Tarama süresi label'ı
        self.timer_label = tk.Label(
            title_frame,
            text="Sure: 00:00",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["bg_medium"],
            fg=self.colors["info"],
            anchor="e"
        )
        self.timer_label.pack(side=tk.RIGHT, pady=5, padx=10)

        # Buton frame - DARK THEME
        button_frame = tk.Frame(self.root, bg=self.colors["bg_dark"])
        button_frame.pack(fill=tk.X, padx=10, pady=8)

        # SOL TARAF: Barkod arama alanı
        left_frame = tk.Frame(button_frame, bg=self.colors["bg_dark"])
        left_frame.pack(side=tk.LEFT, padx=3)

        tk.Label(
            left_frame,
            text="Ilac Ara:",
            font=("Segoe UI", 10),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"]
        ).pack(side=tk.LEFT, padx=3)

        self.barcode_entry = tk.Entry(
            left_frame,
            font=("Segoe UI", 11),
            width=42,
            bg=self.colors["bg_light"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            relief=tk.FLAT
        )
        self.barcode_entry.pack(side=tk.LEFT, padx=3, ipady=6)
        self.barcode_entry.bind("<Return>", self.on_entry_return)  # Enter'a basınca ara veya listeden seç
        self.barcode_entry.bind("<Control-v>", lambda e: self.root.after(50, self.quick_search_barcode))  # Ctrl+V sonrası ara
        self.barcode_entry.bind("<KeyRelease>", self.on_barcode_keyrelease)  # Yazarken autocomplete
        self.barcode_entry.bind("<Escape>", lambda e: self.hide_autocomplete())  # ESC ile kapat
        self.barcode_entry.bind("<FocusOut>", lambda e: self.root.after(200, self.hide_autocomplete))  # Focus kaybolunca kapat
        self.barcode_entry.bind("<Down>", self.on_entry_down)  # Down tuşu
        self.barcode_entry.bind("<Up>", self.on_entry_up)  # Up tuşu

        # Autocomplete listesi için
        self.autocomplete_window = None
        self.autocomplete_listbox = None
        self.ilac_listesi = {}  # {isim: barkod}
        self.selected_ilac_barkod = None  # Seçilen ilacın barkodu

        self.search_button = tk.Button(
            left_frame,
            text="ARA",
            command=self.quick_search_barcode,
            bg=self.colors["accent"],
            fg="white",
            font=("Segoe UI", 11, "bold"),
            width=8,
            height=1,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=self.colors["accent_hover"]
        )
        self.search_button.pack(side=tk.LEFT, padx=8)
        Tooltip(self.search_button, "Ilac veya barkod ile ara")

        # SAĞ TARAF: Ana butonlar (Kıyas modunda gizlenecek)
        self.right_frame = tk.Frame(button_frame, bg=self.colors["bg_dark"])
        self.right_frame.pack(side=tk.RIGHT, padx=3)

        # Hızlı Tarama butonu
        self.fast_scan_button = tk.Button(
            self.right_frame,
            text="Hizli Tarama",
            command=self.start_fast_scan,
            bg="#FF6B00",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            width=14,
            height=1,
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.fast_scan_button.pack(side=tk.LEFT, padx=3)
        Tooltip(self.fast_scan_button, "Hizli mod: Once tum verileri oku, sonra depolari tara")

        # Listeyi Sil butonu (her zaman görünür)
        self.clear_list_button = tk.Button(
            self.right_frame,
            text="Listeyi Sil",
            command=self.clear_scan_list,
            bg=self.colors["accent"],
            fg="white",
            font=("Segoe UI", 10, "bold"),
            width=12,
            height=1,
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.clear_list_button.pack(side=tk.LEFT, padx=3)

        # Durum frame (butonların altında)
        status_frame = tk.Frame(self.root, bg=self.colors["bg_light"], height=28)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

        # Durum label
        self.status_label = tk.Label(
            status_frame,
            text="Hazir",
            font=("Segoe UI", 9),
            fg=self.colors["text"],
            bg=self.colors["bg_light"],
            anchor="w",
            cursor="hand2"
        )
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)

        # Status label tıklama eventi
        self.status_label.bind("<Button-1>", self.on_status_label_click)

        # Son aranan barkod (hızlı arama için)
        self.last_searched_barcode = None

        # Filtre bar - Modern minimalist tasarım
        self.filter_frame = tk.Frame(self.root, bg=self.colors["bg_dark"])
        self.filter_frame.pack(fill=tk.X, padx=10, pady=(5, 2))

        # Filtre butonları container
        self.filter_var = tk.StringVar(value="all")
        self.all_products_backup = []  # Tüm ürünlerin yedeği
        self.filter_buttons = {}

        filter_configs = [
            ("⊛ Tümü", "all"),
            ("🔘 Var", "var"),
            ("📞 Ara", "ara"),
            ("◯ Yok", "yok")
        ]

        for text, value in filter_configs:
            btn = tk.Label(
                self.filter_frame,
                text=text,
                font=("Segoe UI", 9),
                bg=self.colors["bg_dark"],
                fg="#3498db" if value == "all" else "#7f8c8d",
                padx=12,
                pady=3,
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=1)
            btn.bind("<Button-1>", lambda e, v=value: self.apply_filter(v))
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg="#2c3e50"))
            btn.bind("<Leave>", lambda e, b=btn, v=value: b.config(
                fg="#3498db" if self.filter_var.get() == v else "#7f8c8d"
            ))
            self.filter_buttons[value] = btn

        # Ayraç
        tk.Label(self.filter_frame, text="│", fg="#bdc3c7", bg=self.colors["bg_dark"]).pack(side=tk.LEFT, padx=5)

        # Filtre sayacı
        self.filter_count_label = tk.Label(
            self.filter_frame,
            text="",
            font=("Segoe UI", 8),
            bg=self.colors["bg_dark"],
            fg="#95a5a6"
        )
        self.filter_count_label.pack(side=tk.LEFT)

        # Sağ taraf - Listeyi Sil butonu
        clear_btn = tk.Label(
            self.filter_frame,
            text="🗑 Temizle",
            font=("Segoe UI", 9),
            bg=self.colors["bg_dark"],
            fg="#e74c3c",
            padx=8,
            pady=3,
            cursor="hand2"
        )
        clear_btn.pack(side=tk.RIGHT, padx=5)
        clear_btn.bind("<Button-1>", lambda e: self.clear_product_list())
        clear_btn.bind("<Enter>", lambda e: clear_btn.config(fg="#c0392b"))
        clear_btn.bind("<Leave>", lambda e: clear_btn.config(fg="#e74c3c"))

        # Tablo frame
        table_frame = tk.Frame(self.root, bg=self.colors["bg_dark"])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Dinamik sütunlar oluştur (sadece kullanılabilir depoların sütunları)
        base_columns = ["Satır", "Ürün Adı", "Depocu", "Stok", "İht", "MinStk"]

        # Depo sütun mapping (key: depo adı, value: kısa ad)
        depo_column_map = {
            "alliance": "All",
            "selcuk": "Sel",
            "yusufpasa": "Ysf",
            "iskoop": "Koop",
            "bursa": "BEK",
            "farmazon": "Fz",
            "sancak": "San"
        }

        # Depo sırasını controller'dan al (DEPO_SIRALAMA ayarına göre)
        depo_order = self.controller.get_depo_order() if self.controller else list(depo_column_map.keys())

        # Sadece kullanılabilir depoların sütunlarını ekle (sıralı)
        depo_columns = []
        for depo_key in depo_order:
            if depo_key in self.available_depolar:
                depo_columns.append(depo_column_map[depo_key])

        # Final sütun listesi
        columns = base_columns + depo_columns + ["Sipariş Adet"]

        # Treeview için acik stil
        style = ttk.Style()
        style.theme_use("clam")

        # Treeview light theme
        style.configure(
            "Treeview",
            font=("Segoe UI", 9),
            rowheight=26,
            background="#ffffff",
            foreground="#2c3e50",
            fieldbackground="#ffffff"
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background="#3498db",
            foreground="white"
        )
        style.map(
            "Treeview",
            background=[("selected", "#3498db")],
            foreground=[("selected", "white")]
        )

        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", yscrollcommand=scrollbar.set)

        # Satir renkleri - alternating rows (zebra)
        self.tree.tag_configure("oddrow", background="#ffffff")
        self.tree.tag_configure("evenrow", background="#e8ecef")

        # Barkod yapıştır modu için stok durumu renkleri
        self.tree.tag_configure("in_stock", background="#d4edda")  # Yeşil - stokta var
        self.tree.tag_configure("no_stock", background="#f8d7da")  # Kırmızı - stokta yok

        # Depo sütunlarını sakla (sonra erişim için)
        self.depo_columns = depo_columns

        # Sütun başlıkları
        for column in columns:
            self.tree.heading(column, text=column)

        # Adaptif sütun ayarları
        self.column_weights = {
            "Satır": 1,
            "Ürün Adı": 4,
            "Depocu": 1,
            "Stok": 1,
            "İht": 1,
            "MinStk": 1,
            "Sipariş Adet": 1
        }

        # Depo sütunlarına weight ekle
        for depo_col in depo_columns:
            self.column_weights[depo_col] = 2

        self.column_min_widths = {
            "Satır": 40,
            "Ürün Adı": 150,
            "Depocu": 60,
            "Stok": 50,
            "İht": 45,
            "MinStk": 50,
            "Sipariş Adet": 75
        }

        # Depo sütunlarına min width ekle
        for depo_col in depo_columns:
            self.column_min_widths[depo_col] = 70

        for column in columns:
            anchor = "w"
            # Depo sütunları ve sayısal sütunları ortala
            if column in ["Satır", "Depocu", "Stok", "İht", "MinStk", "Sipariş Adet"] or column in depo_columns:
                anchor = "center"

            self.tree.column(column, anchor=anchor, stretch=True)

        # Not: Tkinter Treeview hücre bazlı renklendirme desteklemez
        # Bu yüzden emoji/simge kullanacağız

        self.tree.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.tree.yview)

        # Pencere boyutu değişince sütunları yeniden boyutlandır
        self.tree.bind("<Configure>", lambda e: self.adjust_tree_columns())
        self.root.bind("<Configure>", lambda e: self.adjust_tree_columns())
        self.adjust_tree_columns()

        # Tıklama olayları
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Satır seçimi event'i (aylık gidiş tablosu için)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_selected)

        # Depo hücrelerinde hover tooltip için
        self.tree.bind("<Motion>", self.on_tree_motion)
        self.tree.bind("<Leave>", self.on_tree_leave)
        self.depo_tooltip = None
        self.depo_tooltip_after_id = None
        self.load_depo_contact_info()

        # Depo Şartları tablosu (Aylık gidiş üstünde)
        sartlar_container = tk.Frame(self.root, height=140, bg=self.colors["bg_dark"])
        sartlar_container.pack(fill=tk.X, padx=10, pady=5)
        sartlar_container.pack_propagate(False)

        sartlar_frame = tk.Frame(sartlar_container, bg=self.colors["bg_dark"])
        sartlar_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            sartlar_frame,
            text="Depo Sartlari (MF):",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"]
        ).pack(anchor=tk.W)

        # Depo şartları tablosu için Treeview - Her depo için 2 sütun (Şart, Fiyat)
        # Tüm depo listesi (referans için)
        self.sartlar_depo_list = ["alliance", "selcuk", "yusufpasa", "iskoop", "bursa", "farmazon", "sancak"]
        self.sartlar_depo_names = {
            "alliance": "All",
            "selcuk": "Sel",
            "yusufpasa": "YP",
            "iskoop": "Koop",
            "bursa": "BEK",
            "farmazon": "Fz",
            "sancak": "San"
        }

        # Aktif depoları ve sıralamayı al (üst tabloyla aynı mantık)
        depo_order = self.controller.get_depo_order() if self.controller else self.sartlar_depo_list
        active_depo_list = [d for d in depo_order if d in self.available_depolar]

        # Eğer aktif depo yoksa, tüm depo listesini kullan (fallback)
        if not active_depo_list:
            logger.warning("Aktif depo listesi boş, tüm depolar kullanılacak")
            active_depo_list = self.sartlar_depo_list

        self.active_sartlar_depo_list = active_depo_list
        logger.info(f"Depo Şartları tablosu oluşturuluyor - {len(active_depo_list)} depo: {active_depo_list}")

        # Sütunları oluştur: Sadece aktif depolar için, sıralı şekilde
        sartlar_columns = []
        for depo_key in active_depo_list:
            sartlar_columns.append(f"{depo_key}_sart")
            sartlar_columns.append(f"{depo_key}_fiyat")

        # Treeview ve scrollbar için frame
        sartlar_tree_frame = tk.Frame(sartlar_frame, bg=self.colors["bg_dark"])
        sartlar_tree_frame.pack(fill=tk.BOTH, expand=True)

        self.sartlar_tree = ttk.Treeview(sartlar_tree_frame, columns=sartlar_columns, show="headings", height=5)

        # Scrollbar ekle
        sartlar_scrollbar = ttk.Scrollbar(sartlar_tree_frame, orient="vertical", command=self.sartlar_tree.yview)
        self.sartlar_tree.configure(yscrollcommand=sartlar_scrollbar.set)

        # Başlıkları ayarla (sadece aktif depolar)
        for depo_key in active_depo_list:
            depo_name = self.sartlar_depo_names.get(depo_key, depo_key)
            self.sartlar_tree.heading(f"{depo_key}_sart", text=f"{depo_name}")
            self.sartlar_tree.heading(f"{depo_key}_fiyat", text="Fiyat")
            self.sartlar_tree.column(f"{depo_key}_sart", width=70, anchor="center")
            self.sartlar_tree.column(f"{depo_key}_fiyat", width=70, anchor="center")

        self.sartlar_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sartlar_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Farmazon fiyat sütununa çift tıklama için bind
        self.sartlar_tree.bind("<Double-1>", self._on_sartlar_double_click)
        self.sartlar_fiyat_edit = {"entry": None, "item": None, "column": None}

        # Başlangıçta boş satır
        empty_values = ["-"] * len(sartlar_columns)
        self.sartlar_tree.insert("", tk.END, values=empty_values)

        # Sartlar frame referansını sakla
        self.sartlar_frame = sartlar_frame

        # Kıyas Kontrol Barı - İnce çizgi tarzında
        self.kiyas_bar = tk.Frame(self.root, bg="#0d1b2a", height=28)
        self.kiyas_bar.pack_propagate(False)

        # Sol: ⚖ KIYAS + Toplam
        tk.Label(self.kiyas_bar, text="⚖ KIYAS", font=("Segoe UI", 9, "bold"),
                 bg="#0d1b2a", fg="#e94560").pack(side=tk.LEFT, padx=(10,5), pady=2)

        self.kiyas_total_label = tk.Label(self.kiyas_bar, text="(0)", font=("Segoe UI", 8),
                                          bg="#0d1b2a", fg="#4ecca3")
        self.kiyas_total_label.pack(side=tk.LEFT, pady=2)

        # Separator
        tk.Frame(self.kiyas_bar, width=1, bg="#3d5a80").pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # Aralık: [__] → [__]
        tk.Label(self.kiyas_bar, text="Aralık:", font=("Segoe UI", 8), bg="#0d1b2a", fg="#778da9").pack(side=tk.LEFT, padx=(0,4))

        self.kiyas_start_entry = tk.Entry(self.kiyas_bar, font=("Segoe UI", 8), width=5,
                                          bg="#1b263b", fg="#e0e1dd", insertbackground="#e0e1dd",
                                          bd=0, highlightthickness=1, highlightbackground="#3d5a80")
        self.kiyas_start_entry.insert(0, "1")
        self.kiyas_start_entry.pack(side=tk.LEFT, pady=3)

        tk.Label(self.kiyas_bar, text="→", font=("Segoe UI", 9), bg="#0d1b2a", fg="#778da9").pack(side=tk.LEFT, padx=3)

        self.kiyas_end_entry = tk.Entry(self.kiyas_bar, font=("Segoe UI", 8), width=5,
                                        bg="#1b263b", fg="#e0e1dd", insertbackground="#e0e1dd",
                                        bd=0, highlightthickness=1, highlightbackground="#3d5a80")
        self.kiyas_end_entry.insert(0, "100")
        self.kiyas_end_entry.pack(side=tk.LEFT, pady=3)

        # Separator
        tk.Frame(self.kiyas_bar, width=1, bg="#3d5a80").pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        # Progress bar
        style = ttk.Style()
        style.configure("Kiyas.Horizontal.TProgressbar", thickness=8, troughcolor="#1b263b", background="#4ecca3")
        self.kiyas_progress_bar = ttk.Progressbar(self.kiyas_bar, mode='determinate', length=120,
                                                   style="Kiyas.Horizontal.TProgressbar")
        self.kiyas_progress_bar.pack(side=tk.LEFT, pady=5)

        self.kiyas_progress_label = tk.Label(self.kiyas_bar, text="", font=("Segoe UI", 8),
                                             bg="#0d1b2a", fg="#ffc107")
        self.kiyas_progress_label.pack(side=tk.LEFT, padx=6, pady=2)

        # Orta: Durum/ipucu yazısı (expand ile ortada kalır)
        self.kiyas_status_label = tk.Label(self.kiyas_bar, text="▶ Başlat'a tıklayın",
                                           font=("Segoe UI", 8, "italic"), bg="#0d1b2a", fg="#adb5bd")
        self.kiyas_status_label.pack(side=tk.LEFT, expand=True, pady=2)

        # Sağda: Butonlar
        self.kiyas_exit_button = tk.Label(
            self.kiyas_bar, text=" ✕ ", font=("Segoe UI", 9), bg="#415a77", fg="#e0e1dd",
            padx=2, pady=1, cursor="hand2"
        )
        self.kiyas_exit_button.pack(side=tk.RIGHT, padx=(2,10), pady=3)
        self.kiyas_exit_button.bind("<Button-1>", lambda e: self.exit_kiyas_mode())
        self.kiyas_exit_button.bind("<Enter>", lambda e: e.widget.config(bg="#e74c3c"))
        self.kiyas_exit_button.bind("<Leave>", lambda e: e.widget.config(bg="#415a77"))

        self.kiyas_stop_button = tk.Label(
            self.kiyas_bar, text=" ■ ", font=("Segoe UI", 9), bg="#415a77", fg="#778da9",
            padx=2, pady=1, cursor="hand2"
        )
        self.kiyas_stop_button.pack(side=tk.RIGHT, padx=2, pady=3)
        self.kiyas_stop_button.bind("<Button-1>", lambda e: self.stop_kiyas_scan())

        self.kiyas_start_button = tk.Label(
            self.kiyas_bar, text=" ▶ ", font=("Segoe UI", 9), bg="#27ae60", fg="white",
            padx=2, pady=1, cursor="hand2"
        )
        self.kiyas_start_button.pack(side=tk.RIGHT, padx=2, pady=3)
        self.kiyas_start_button.bind("<Button-1>", lambda e: self.start_kiyas_scan())
        self.kiyas_start_button.bind("<Enter>", lambda e: e.widget.config(bg="#2ecc71"))
        self.kiyas_start_button.bind("<Leave>", lambda e: e.widget.config(bg="#27ae60"))

        # Mevcut ilaç label (status bar'da gösterilecek)
        self.kiyas_current_label = None

        # Aylık gidiş tablosu (alt panel) - Kıyas modunda gizlenecek
        self.monthly_container = tk.Frame(self.root, height=85, bg=self.colors["bg_dark"])
        self.monthly_container.pack(fill=tk.X, padx=10, pady=5)
        self.monthly_container.pack_propagate(False)

        # Sol: Aylık gidiş tablosu
        monthly_frame = tk.Frame(self.monthly_container, bg=self.colors["bg_dark"])
        monthly_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(
            monthly_frame,
            text="Aylik Toplam Gidis:",
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["bg_dark"],
            fg=self.colors["text"]
        ).pack(anchor=tk.W)

        # Aylık gidiş tablosu için Treeview - SADECE TOP SATIRI
        # Dinamik ay sütunları (bugünden geriye 13 ay)
        from datetime import datetime

        today = datetime.now()
        monthly_columns = []

        # 12 ay önceden bugüne kadar (ters sıra: eski -> yeni)
        for i in range(12, -1, -1):  # 12, 11, 10, ..., 1, 0
            target_month = today.month - i
            target_year = today.year

            while target_month <= 0:
                target_month += 12
                target_year -= 1

            monthly_columns.append(f"{target_month:02d}.{target_year % 100:02d}")

        monthly_columns.extend(["Top", "Ort"])

        self.monthly_tree = ttk.Treeview(monthly_frame, columns=monthly_columns, show="headings", height=1)

        for col in monthly_columns:
            self.monthly_tree.heading(col, text=col)
            self.monthly_tree.column(col, width=50, anchor="center")

        self.monthly_tree.pack(fill=tk.BOTH, expand=True)

        # Çift tıklama event'i (sipariş adedi düzenleme için)
        self.monthly_tree.bind("<Double-1>", self.on_monthly_tree_double_click)

        # Başlangıçta boş satır ekle
        self.monthly_tree.insert("", tk.END, values=["-"] * 15)

        # Program açılışında Botanik EOS'a bağlanmayı dene (Sipariş penceresini aç)
        self.root.after(300, self.check_botanik_on_startup)

        # Program açılışında önceki tarama verilerini yükle (CSV'den)
        self.root.after(800, self.load_previous_scan_data)

        # Sağ: Bilgi paneli (Stok, Sipariş Adedi, Kaç Günde Bitecek)
        info_panel = tk.Frame(self.monthly_container, width=250, bg=self.colors["bg_medium"], relief=tk.FLAT)
        info_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        info_panel.pack_propagate(False)

        # Stok bilgisi
        stok_frame = tk.Frame(info_panel, bg=self.colors["bg_medium"])
        stok_frame.pack(anchor=tk.W, padx=10, pady=3)
        tk.Label(stok_frame, text="Stok:", font=("Segoe UI", 9, "bold"), bg=self.colors["bg_medium"], fg=self.colors["text"], width=12, anchor="w").pack(side=tk.LEFT)
        self.info_stok_label = tk.Label(stok_frame, text="-", font=("Segoe UI", 9), bg=self.colors["bg_medium"], fg=self.colors["text_dim"])
        self.info_stok_label.pack(side=tk.LEFT)

        # Sipariş adedi bilgisi (çift tıklanabilir)
        siparis_frame = tk.Frame(info_panel, bg=self.colors["bg_medium"])
        siparis_frame.pack(anchor=tk.W, padx=10, pady=3)
        tk.Label(siparis_frame, text="Siparis:", font=("Segoe UI", 9, "bold"), bg=self.colors["bg_medium"], fg=self.colors["text"], width=12, anchor="w").pack(side=tk.LEFT)
        self.info_siparis_label = tk.Label(siparis_frame, text="-", font=("Segoe UI", 9), bg=self.colors["bg_medium"], fg=self.colors["info"], cursor="hand2")
        self.info_siparis_label.pack(side=tk.LEFT)
        self.info_siparis_label.bind("<Double-1>", self.on_info_siparis_double_click)

        # Kaç günde bitecek bilgisi
        gun_frame = tk.Frame(info_panel, bg=self.colors["bg_medium"])
        gun_frame.pack(anchor=tk.W, padx=10, pady=3)
        tk.Label(gun_frame, text="Kac Gunde:", font=("Segoe UI", 9, "bold"), bg=self.colors["bg_medium"], fg=self.colors["text"], width=12, anchor="w").pack(side=tk.LEFT)
        self.info_gun_label = tk.Label(gun_frame, text="-", font=("Segoe UI", 9), bg=self.colors["bg_medium"], fg=self.colors["success"])
        self.info_gun_label.pack(side=tk.LEFT)

        # Seçili ürün bilgisi (güncellemeler için)
        self.selected_product = None

        # Açıklama frame
        info_frame = tk.Frame(self.root, bg=self.colors["bg_medium"])
        info_frame.pack(fill=tk.X, padx=10, pady=5)


    def open_settings(self):
        """Ayarlar penceresini aç"""
        SettingsWindow(self.root, main_window=self)

    def open_barkod_yapistir(self):
        """Clipboard'dan barkodları direkt tabloya ekle (dialog açmadan)"""
        try:
            # Clipboard'dan oku
            try:
                content = self.root.clipboard_get()
            except tk.TclError:
                messagebox.showwarning("Uyarı", "Clipboard boş veya okunamadı!")
                return

            if not content or not content.strip():
                messagebox.showwarning("Uyarı", "Clipboard boş!")
                return

            content = content.strip()

            # Barkodları parse et (virgül veya satır sonu ile ayrılmış)
            if "," in content:
                # Virgülle ayrılmış
                barcodes = [b.strip() for b in content.split(",") if b.strip()]
            else:
                # Alt alta
                barcodes = [b.strip() for b in content.split("\n") if b.strip()]

            # Sadece sayısal barkodları al (en az 8 karakter)
            valid_barcodes = [b for b in barcodes if b.replace(" ", "").isdigit() or len(b) >= 8]

            if not valid_barcodes:
                messagebox.showwarning("Uyarı", "Clipboard'da geçerli barkod bulunamadı!")
                return

            logger.info(f"Barkod yapıştır: {len(valid_barcodes)} barkod tabloya ekleniyor")

            # Listeyi temizle
            self.clear_product_list()

            # Barkodları tabloya ekle (Ürün Adı = barkod, taranmamış)
            self._add_barcodes_to_table(valid_barcodes)

            # Bilgi mesajı
            self.status_label.config(text=f"📋 {len(valid_barcodes)} barkod eklendi - Hızlı Tarama'ya basın")

        except Exception as e:
            logger.error(f"Barkod yapıştır hatası: {e}")
            messagebox.showerror("Hata", f"Barkod yapıştırma hatası: {e}")

    def _add_barcodes_to_table(self, barcodes):
        """Barkodları tabloya ekle (Ürün Adı = barkod, taranmamış)"""
        try:
            for i, barcode in enumerate(barcodes):
                # Satır verisi oluştur (mevcut sistemle uyumlu yapı)
                product_data = {
                    "row": i + 1,
                    "urun_adi": f"[{barcode}]",  # Barkod göster, taranınca değişecek
                    "depocu": "",
                    "stok": 0,
                    "iht": 0,
                    "minst": 0,
                    "barcode": barcode,
                    "siparis_adet": 0,
                    "taranmadi": True  # Henüz taranmadı işareti
                }

                # Depo sütunlarını boş bırak (mevcut format)
                for depo_key in self.depo_columns:
                    # depo_key örn: "Sel", "All" vs.
                    product_data[f"{depo_key.lower()}_durum"] = {
                        "stok_var": None,  # None = bilinmiyor
                        "mesaj": "-",
                        "fiyat": 0,
                        "sart": "",
                        "satis_kosullari": []
                    }

                # Zebra deseni için satır tag'i
                row_count = len(self.tree.get_children())
                row_tag = "evenrow" if row_count % 2 == 0 else "oddrow"

                # Treeview değerleri oluştur
                base_values = [
                    i + 1,  # Satır
                    f"[{barcode}]",  # Ürün Adı (barkod)
                    "",  # Depocu
                    0,  # Stok
                    0,  # MF (iht)
                    0   # MinStk
                ]
                depo_values = ["-"] * len(self.depo_columns)  # Henüz taranmadı
                values = base_values + depo_values + [0]  # Sipariş Adet

                # Satırı ekle
                item_id = self.tree.insert("", tk.END, values=values, tags=(row_tag,))

                # Listeye ekle (mevcut sistemle uyumlu)
                self.products.append({"item_id": item_id, "data": product_data})

            # Barkod yapıştır modunda olduğumuzu işaretle
            self.barkod_yapistir_mode = True

            # Status güncelle
            self.status_label.config(text=f"📋 {len(barcodes)} barkod eklendi - Taramayı başlat")
            logger.info(f"Barkod yapıştır: {len(barcodes)} barkod tabloya eklendi")

        except Exception as e:
            logger.error(f"Barkodları tabloya ekleme hatası: {e}")

    def _run_barkod_yapistir_scan(self):
        """Barkod yapıştır modunda tablodaki barkodları tara ve güncelle"""
        try:
            # Taranmamış ürünleri bul (yeni veri yapısı: product["data"]["taranmadi"])
            taranmamis = [p for p in self.products if p.get("data", {}).get("taranmadi", False)]
            if not taranmamis:
                messagebox.showinfo("Bilgi", "Taranacak barkod yok!")
                return

            # Depoların açık olup olmadığını kontrol et
            # Sadece dict boş mu diye değil, driver'ların canlı olup olmadığını da kontrol et
            depolar_canli = False
            if self.available_depolar:
                # En az bir deponun driver'ı canlı mı kontrol et
                for depo_key, depo in list(self.available_depolar.items()):
                    try:
                        if depo.driver and depo.driver.current_url:
                            depolar_canli = True
                            break
                    except Exception:
                        # Driver ölmüş, listeden çıkar
                        logger.warning(f"{depo_key}: Driver ölü, listeden çıkarılıyor")
                        del self.available_depolar[depo_key]

            if not depolar_canli:
                # Depolar açık değil veya ölmüş - yeniden aç
                self.available_depolar = {}  # Temizle
                self.status_label.config(text="⏳ Depolar açılıyor...")
                self.root.update()

                if not self._open_depolar_for_barkod_yapistir():
                    messagebox.showerror("Hata", "Depolar açılamadı!")
                    return

            # Controller'ın active_depolar'ını güncelle
            if self.controller and self.available_depolar:
                self.controller.active_depolar = self.available_depolar

            logger.info(f"Barkod yapıştır taraması başlıyor: {len(taranmamis)} barkod")

            # Tarama başlat
            self.is_scanning = True
            self.fast_scan_button.config(text="⏹ Durdur", bg=self.colors["warning"])
            self.status_label.config(text=f"📋 Barkod Taraması: 0/{len(taranmamis)}")

            # Thread'de tara
            def scan_thread():
                try:
                    for i, product in enumerate(taranmamis):
                        if not self.is_scanning:
                            break

                        # Pause kontrolü
                        self.pause_event.wait()

                        barcode = product["data"].get("barcode", "")

                        # Status güncelle
                        self.root.after(0, lambda idx=i, bc=barcode: self.status_label.config(
                            text=f"📋 Taranıyor: {bc} ({idx+1}/{len(taranmamis)})"
                        ))

                        # Bu barkodu tara (controller üzerinden)
                        if self.controller:
                            result = self.controller.search_barcode_all_depolar(barcode)
                            if result:
                                # Mevcut satırı güncelle
                                self.root.after(0, lambda r=result, p=product: self._update_barkod_row(r, p))
                            else:
                                # Sonuç bulunamadı
                                self.root.after(0, lambda p=product, bc=barcode: self._mark_barcode_not_found(p, bc))

                    # Tarama bitti
                    self.root.after(0, self._finish_barkod_yapistir_scan)

                except Exception as e:
                    logger.error(f"Barkod tarama thread hatası: {e}")
                    self.root.after(0, lambda: self.status_label.config(text=f"Hata: {e}"))

            import threading
            thread = threading.Thread(target=scan_thread, daemon=True)
            thread.start()

        except Exception as e:
            logger.error(f"Barkod tarama başlatma hatası: {e}")
            self.is_scanning = False

    def _update_barkod_row(self, result, product):
        """Barkod tarama sonucuyla mevcut satırı güncelle"""
        try:
            # Result formatı: {"barcode": str, "product_name": str, "depo_results": {...}}
            barcode = result.get("barcode", "")
            product_name = result.get("product_name", "")
            depo_results = result.get("depo_results", {})

            data = product["data"]
            item_id = product["item_id"]

            # Ürün adını ve barkodu güncelle
            if product_name:
                data["urun_adi"] = product_name
            else:
                data["urun_adi"] = f"[{barcode}]"
            data["barkod"] = barcode

            # Taranmadı işaretini kaldır
            data["taranmadi"] = False

            # Depo sonuçlarını güncelle (mevcut format)
            for depo_key, depo_data in depo_results.items():
                if depo_data:
                    # depo_key örn: "selcuk", "alliance" vs.
                    # GUI sütun adı örn: "Sel", "All" vs.
                    depo_col = depo_key[:3].capitalize()
                    if depo_col == "Yus":
                        depo_col = "Ysf"
                    elif depo_col == "Isk":
                        depo_col = "Kop"
                    elif depo_col == "Far":
                        depo_col = "Fz"

                    stok_var = depo_data.get("stok_var", False)
                    fiyat = depo_data.get("fiyat", 0) or 0
                    sart = depo_data.get("sart", "") or ""
                    satis_kosullari = depo_data.get("satis_kosullari", [])

                    # Mesaj formatla
                    if not stok_var:
                        mesaj = "YOK"
                    elif fiyat > 0:
                        mesaj = f"{fiyat:.2f}"
                        if sart:
                            mesaj += f" ({sart})"
                    else:
                        mesaj = "VAR"

                    durum_data = {
                        "stok_var": stok_var,
                        "mesaj": mesaj,
                        "fiyat": fiyat,
                        "sart": sart,
                        "satis_kosullari": satis_kosullari
                    }

                    # Hem kısa (GUI tablo için) hem uzun (Depo Şartları için) key kaydet
                    data[f"{depo_col.lower()}_durum"] = durum_data
                    data[f"{depo_key}_durum"] = durum_data

            # Treeview satırını güncelle
            self._refresh_barkod_row(product)

            # Efektif fiyat hesapla (stok bilgisi olmadan, sadece fiyat bazlı)
            if self.controller:
                try:
                    # Barkod yapıştır modunda stok/ort bilgisi yok, sadece fiyat bazlı hesapla
                    en_karli = self.controller.hesapla_en_karli_fiyat_basit(data)
                    if en_karli:
                        data["en_karli_sonuc"] = en_karli
                except Exception as e:
                    logger.debug(f"Efektif fiyat hesaplama hatası: {e}")

            # Depo Şartları tablosunu güncelle
            self.update_sartlar_table(product)

            logger.debug(f"Barkod satır güncellendi: {barcode} -> {data.get('urun_adi', '')}")

        except Exception as e:
            logger.error(f"Barkod satır güncelleme hatası: {e}")

    def _mark_barcode_not_found(self, product, barcode):
        """Bulunamayan barkodu işaretle"""
        try:
            data = product["data"]
            data["taranmadi"] = False
            data["urun_adi"] = f"[{barcode}] - Bulunamadı"

            # Tüm depoları "YOK" olarak işaretle
            for depo_col in self.depo_columns:
                durum_key = f"{depo_col.lower()}_durum"
                data[durum_key] = {
                    "stok_var": False,
                    "mesaj": "YOK",
                    "fiyat": 0,
                    "sart": "",
                    "satis_kosullari": []
                }

            self._refresh_barkod_row(product)

        except Exception as e:
            logger.error(f"Bulunamayan barkod işaretleme hatası: {e}")

    def _refresh_barkod_row(self, product):
        """Barkod satırını treeview'da güncelle"""
        try:
            data = product["data"]
            item_id = product["item_id"]

            # Treeview değerleri oluştur
            base_values = [
                data.get("row", 0),
                data.get("urun_adi", ""),
                data.get("depocu", ""),
                data.get("stok", 0),
                data.get("iht", 0),
                data.get("minst", 0)
            ]

            # Depo mesajları
            depo_values = []
            for depo_col in self.depo_columns:
                durum_key = f"{depo_col.lower()}_durum"
                durum = data.get(durum_key, {})
                mesaj = durum.get("mesaj", "-")
                depo_values.append(mesaj)

            values = base_values + depo_values + [data.get("siparis_adet", 0)]

            # Treeview'ı güncelle
            self.tree.item(item_id, values=values)

            # Renkleri güncelle (stok durumuna göre)
            any_stock = any(
                data.get(f"{dc.lower()}_durum", {}).get("stok_var", False)
                for dc in self.depo_columns
            )

            if any_stock:
                self.tree.item(item_id, tags=("in_stock",))
            else:
                self.tree.item(item_id, tags=("no_stock",))

        except Exception as e:
            logger.error(f"Barkod satır yenileme hatası: {e}")

    def _open_depolar_for_barkod_yapistir(self):
        """Barkod yapıştır için depoları otomatik aç (sadece ayarlarda aktif olanları)

        BROWSER_MODE=windows ise PARALEL açar (çok daha hızlı)
        BROWSER_MODE=tabs ise SIRAYLA açar (tek pencere)
        """
        try:
            import os
            import time
            from pathlib import Path
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from ..utils import HEADLESS
            from ..depolar import AllianceDepo, SelcukDepo, YusufPasaDepo, IskoopDepo, BursaDepo, SancakDepo, FarmazonDepo
            from dotenv import load_dotenv

            # .env dosyasını yükle
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            if env_path.exists():
                load_dotenv(env_path)

            # Depo sınıfları (Farmazon dahil)
            depo_classes = {
                "alliance": AllianceDepo,
                "selcuk": SelcukDepo,
                "yusufpasa": YusufPasaDepo,
                "iskoop": IskoopDepo,
                "bursa": BursaDepo,
                "sancak": SancakDepo,
                "farmazon": FarmazonDepo
            }

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
                "sancak": {
                    "username": os.getenv("SANCAK_USERNAME", ""),
                    "password": os.getenv("SANCAK_PASSWORD", "")
                },
                "farmazon": {
                    "username": os.getenv("FARMAZON_USERNAME", ""),
                    "password": os.getenv("FARMAZON_PASSWORD", "")
                }
            }

            # Tarayıcı modunu al
            browser_mode = os.getenv("BROWSER_MODE", "tabs")
            logger.info(f"Barkod yapıştır - Tarayıcı modu: {browser_mode}")

            # Aktif depoları belirle
            aktif_depolar = []
            for depo_name, depo_class in depo_classes.items():
                enabled_key = f"{depo_name.upper()}_ENABLED"
                is_enabled = os.getenv(enabled_key, "false").lower() == "true"

                if not is_enabled:
                    logger.info(f"{depo_name} ayarlarda kapalı, atlanıyor")
                    continue

                creds = credentials.get(depo_name, {})

                # Credential kontrolü
                has_credentials = False
                if depo_name == "alliance":
                    has_credentials = bool(creds.get("eczane_kodu") and creds.get("username") and creds.get("password"))
                elif depo_name == "selcuk":
                    has_credentials = bool(creds.get("hesap_kodu") and creds.get("username") and creds.get("password"))
                elif depo_name == "yusufpasa":
                    has_credentials = bool(creds.get("eczane_kodu") and creds.get("username") and creds.get("password"))
                elif depo_name in ["iskoop", "bursa", "sancak", "farmazon"]:
                    has_credentials = bool(creds.get("username") and creds.get("password"))

                if not has_credentials:
                    logger.info(f"{depo_name} için bilgiler eksik, atlanıyor")
                    continue

                aktif_depolar.append((depo_name, depo_class, creds))

            if not aktif_depolar:
                logger.warning("Hiçbir aktif depo bulunamadı!")
                return False

            # ========== PARALEL AÇMA (windows modu) ==========
            if browser_mode == "windows":
                logger.info(f"🚀 PARALEL DEPO AÇMA başlıyor - {len(aktif_depolar)} depo")
                self.status_label.config(text=f"⏳ {len(aktif_depolar)} depo paralel açılıyor...")
                self.root.update()

                def open_single_depo(depo_info):
                    """Tek bir depoyu aç ve giriş yap"""
                    depo_name, depo_class, creds = depo_info
                    try:
                        logger.info(f"[PARALEL] {depo_name} açılıyor...")
                        depo = depo_class()

                        if not depo.init_driver(headless=HEADLESS):
                            logger.error(f"[PARALEL] {depo_name} driver init başarısız")
                            return depo_name, None

                        if not depo.open_page():
                            logger.error(f"[PARALEL] {depo_name} sayfa açılamadı")
                            return depo_name, None

                        time.sleep(0.5)  # Sayfa yüklensin

                        # Login
                        if depo_name == "alliance":
                            depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                        elif depo_name == "selcuk":
                            depo.login(creds["hesap_kodu"], creds["username"], creds["password"])
                        elif depo_name == "yusufpasa":
                            depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                        elif depo_name in ["iskoop", "bursa", "sancak", "farmazon"]:
                            depo.login(creds["username"], creds["password"])

                        logger.info(f"[PARALEL] ✓ {depo_name} açıldı ve giriş yapıldı")
                        return depo_name, depo

                    except Exception as e:
                        logger.error(f"[PARALEL] {depo_name} açılırken hata: {e}")
                        return depo_name, None

                # Tüm depoları paralel aç
                acilan_depo_sayisi = 0
                with ThreadPoolExecutor(max_workers=len(aktif_depolar)) as executor:
                    futures = [executor.submit(open_single_depo, info) for info in aktif_depolar]

                    for future in as_completed(futures):
                        depo_name, depo = future.result()
                        if depo:
                            self.available_depolar[depo_name] = depo
                            acilan_depo_sayisi += 1
                            self.status_label.config(text=f"✓ {depo_name} açıldı ({acilan_depo_sayisi}/{len(aktif_depolar)})")
                            self.root.update()

                logger.info(f"🚀 PARALEL AÇMA TAMAMLANDI: {acilan_depo_sayisi}/{len(aktif_depolar)} depo")

            # ========== SIRAYLA AÇMA (tabs modu) ==========
            else:
                shared_driver = None
                first_depo = True
                acilan_depo_sayisi = 0

                for depo_name, depo_class, creds in aktif_depolar:
                    try:
                        self.status_label.config(text=f"⏳ {depo_name} açılıyor...")
                        self.root.update()

                        depo = depo_class()

                        if first_depo:
                            if not depo.init_driver(headless=HEADLESS):
                                continue
                            shared_driver = depo.driver
                            first_depo = False
                        else:
                            if not shared_driver:
                                continue
                            if not depo.init_driver(headless=HEADLESS, shared_driver=shared_driver):
                                continue

                        if not depo.open_page():
                            continue

                        time.sleep(1)

                        self.status_label.config(text=f"⏳ {depo_name} giriş yapılıyor...")
                        self.root.update()

                        # Login
                        if depo_name == "alliance":
                            depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                        elif depo_name == "selcuk":
                            depo.login(creds["hesap_kodu"], creds["username"], creds["password"])
                        elif depo_name == "yusufpasa":
                            depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                        elif depo_name in ["iskoop", "bursa", "sancak", "farmazon"]:
                            depo.login(creds["username"], creds["password"])

                        time.sleep(1)

                        self.available_depolar[depo_name] = depo
                        acilan_depo_sayisi += 1
                        logger.info(f"✓ {depo_name} açıldı")

                    except Exception as e:
                        logger.error(f"{depo_name} açılırken hata: {e}")
                        continue

            logger.info(f"Barkod yapıştır: {acilan_depo_sayisi} depo açıldı")
            self.status_label.config(text=f"✓ {acilan_depo_sayisi} depo hazır")

            return acilan_depo_sayisi > 0

        except Exception as e:
            logger.error(f"Barkod yapıştır depo açma hatası: {e}")
            return False

    def _finish_barkod_yapistir_scan(self):
        """Barkod yapıştır taramasını bitir"""
        self.is_scanning = False
        self.barkod_yapistir_mode = False  # Modu sıfırla
        self.fast_scan_button.config(text="⚡ Hızlı Tarama", bg="#FF6B00")
        self.status_label.config(text=f"✓ Barkod taraması tamamlandı: {len(self.products)} ürün")
        logger.info(f"Barkod yapıştır taraması tamamlandı: {len(self.products)} ürün")

    def open_kiyas_motoru(self):
        """Kıyas moduna geç/çık - toggle"""
        try:
            logger.info("Kıyas butonu tıklandı")

            if self.kiyas_mode:
                logger.info("Zaten kıyas modunda, çıkılıyor")
                self.exit_kiyas_mode()
                return

            # Kıyas moduna geç
            self.kiyas_mode = True
            logger.info("Kıyas modu = True")

            # CSV'den ilaç listesini yükle
            self._load_kiyas_ilac_listesi()
            logger.info(f"CSV yüklendi: {self.kiyas_toplam} ilaç")

            # Kıyas barını göster (filtreleme satırından sonra, tablonun üstünde)
            # Önce unpack et (eğer zaten pack edilmişse)
            self.kiyas_bar.pack_forget()
            # Filtre frame'in hemen altına pack et
            self.kiyas_bar.pack(fill=tk.X, padx=10, pady=5, after=self.filter_frame)
            logger.info("Kıyas barı pack edildi")

            # Bitiş değerini güncelle (max 100 veya toplam, min 1)
            max_end = max(1, min(100, self.kiyas_toplam))
            self.kiyas_end_entry.delete(0, tk.END)
            self.kiyas_end_entry.insert(0, str(max_end))
            logger.info(f"Bitiş değeri: {max_end}")

            # Toplam ilaç sayısını güncelle
            self.kiyas_total_label.config(text=f"({self.kiyas_toplam} ilaç)")
            self.kiyas_progress_label.config(text="")

            # Kıyas modunda gereksiz sütunları gizle (displaycolumns ile)
            # Mevcut tüm sütunları al
            all_columns = list(self.tree["columns"])
            # Gizlenecek sütunlar
            hide_columns = ["Stok", "İht", "MF", "MinStk"]
            # Görünecek sütunlar
            visible_columns = [col for col in all_columns if col not in hide_columns]
            # displaycolumns ayarla
            self.tree["displaycolumns"] = visible_columns
            logger.info(f"Görünen sütunlar: {visible_columns}")

            # Kıyas modunda gereksiz öğeleri gizle
            self.right_frame.pack_forget()  # Hızlı Tarama, Listeyi Sil
            self.monthly_container.pack_forget()  # Aylık Toplam Gidiş
            logger.info("Normal mod butonları ve aylık gidiş gizlendi")

            # Tabloyu temizle
            self.tree.delete(*self.tree.get_children())
            self.products.clear()
            logger.info("Tablo temizlendi")

            # GUI'yi sola al (depoları izlemek için)
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = self.root.winfo_width()
            window_height = screen_height - 50  # Taskbar için
            self.root.geometry(f"{window_width}x{window_height}+0+0")
            logger.info(f"GUI sola alındı: {window_width}x{window_height}+0+0")

            # Status güncelle (bar içindeki label)
            self.kiyas_status_label.config(text="▶ Başlat'a tıklayın")
            self.status_label.config(text="⚖ Kıyas Modu Aktif")

            logger.info("✓ Kıyas modu aktif edildi")

        except Exception as e:
            import traceback
            logger.error(f"Kıyas modu açılırken hata: {e}")
            logger.error(traceback.format_exc())
            messagebox.showerror("Hata", f"Kıyas modu açılamadı:\n{e}")

    def _set_kiyas_theme(self, dark=True):
        """Kıyas modu için tema değiştir"""
        if dark:
            # Koyu tema
            bg_dark = "#1a1a2e"
            bg_medium = "#16213e"
            bg_light = "#1f4068"
            text = "#eaeaea"
            text_dim = "#a0a0a0"
        else:
            # Normal açık tema
            bg_dark = "#f5f6fa"
            bg_medium = "#dcdde1"
            bg_light = "#ffffff"
            text = "#2c3e50"
            text_dim = "#7f8c8d"

        # Ana pencere ve frame'leri güncelle
        self.root.configure(bg=bg_dark)

        # Renkleri güncelle (sadece ana arka planlar)
        self.colors["bg_dark"] = bg_dark
        self.colors["bg_medium"] = bg_medium
        self.colors["bg_light"] = bg_light
        self.colors["text"] = text
        self.colors["text_dim"] = text_dim

    def show_help(self):
        """Kullanım kılavuzunu göster"""
        help_text = """
════════════════════════════════════════════════════════════
   BOTANIK SIPARIS YARDIMCISI - KULLANIM KILAVUZU v3.0
════════════════════════════════════════════════════════════

▶ ILK KURULUM
─────────────────────────────────────────────────────────────
1. Ayarlar butonuna (⚙) tiklayin
2. Kullanmak istediginiz depolari isaretleyin (checkbox)
3. Her depo icin kullanici adi ve sifre girin
4. Odeme tipini secin:
   • Vade: X. ayin Y. gunu (ornek: 1. ayin 15'i)
   • Kredi Karti: Hesap kesim ve odeme gunleri
5. Siparis ayarlarini yapin (gun sayisi, faiz orani vs.)
6. "Kaydet" butonuna basin

▶ HIZLI TARAMA (Turuncu Buton)
─────────────────────────────────────────────────────────────
1. Botanik EOS programinda Siparis ekranini acin
2. "⚡ Hizli Tarama" butonuna basin
3. Program otomatik olarak:
   • Botanik'ten ilac listesini okur
   • Tum depolarda stok ve fiyat kontrol eder
   • Siparis adedini hesaplar ve MF/Iht alanina yazar
   • Aciklama alanina depo bilgilerini yazar
   • Sonuclari tabloya yazar

4. Tarama sirasinda:
   • "Duraklat" ile bekletebilirsiniz
   • "Devam Et" ile devam edebilirsiniz
   • Kapatip "Onceki Taramayi Yukle" ile devam edebilirsiniz

▶ SIPARIS ADEDI HESAPLAMA MANTIGI
─────────────────────────────────────────────────────────────
Program siparis adedini su kurallara gore hesaplar:

KURAL 1: MF/Iht Dolu
  MF > 0 ise → Siparis = MF degeri

KURAL 2: MF Bos (MinStk ve Ort Karsilastirmasi)
  Hedef1 = MinStk + 1   (MinStk varsa)
  Hedef2 = Ort x Gun / 30  (yuvarlama kurallariyla)
  Hedef  = max(Hedef1, Hedef2)  ← buyuk olan
  Siparis = Hedef - Mevcut Stok

YUVARLAMA KURALLARI (Ort tabanlı hesap icin):
  • Ort < 0.1     → 0 (yilda 1-2 adet, stokta tutma)
  • Ort 0.1-0.5   → Kac ayda satildigina bak:
                    - 3+ farkli ayda satis → 1 adet bulundur
                    - 2 veya daha az ayda → 0 (toplu satis)
  • Ort >= 0.5    → Yukari yuvarla (en az 1)

ORNEKLER:
  • MinStk=1, Ort=8, Stok=0:
    Hedef1=2, Hedef2=8 → Hedef=8 → Siparis=8 adet

  • MinStk=10, Ort=3, Stok=2:
    Hedef1=11, Hedef2=3 → Hedef=11 → Siparis=9 adet

  • MinStk=0, Ort=0.33 (yilda 4 adet, 4 farkli ayda):
    3+ ayda satis var → Hedef2=1 → Siparis=1 adet

  • MinStk=0, Ort=0.33 (yilda 4 adet, tek seferde):
    1 ayda satis → Hedef2=0 → Siparis=0 (stokta tutma)

▶ TABLO GORUNUMU
─────────────────────────────────────────────────────────────
Sutunlar:
  • Sira    : Botanik'teki satir numarasi
  • Urun    : Ilac adi (varsa MF bilgisi: ★(10+1) gibi)
  • Fiyat   : Alliance depocu fiyati
  • Stk     : Mevcut stok
  • Mf      : Mal fazlasi / Ihtiyac
  • Min     : Minimum stok
  • All/Sel/Ysf/Koop/BEK/Fz/San : Depo durumlari
  • Adet    : Hesaplanan siparis adedi

Depo Sembolleri:
  ★  : En karli depo (en dusuk efektif fiyat)
  🔘 : Stokta var
  ◯  : Stokta yok
  📞 : Depoyu arayin (temsilciye ulasin)
  Pahali : Farmazon fiyati PSF'den yuksek

Satir Renkleri:
  Yesil      : Tum depolarda stok var
  Acik Yesil : Bazi depolarda var
  Sari       : Depo temsilcisini arayin
  Kirmizi    : Hicbir depoda stok yok

▶ SIPARIS VERME
─────────────────────────────────────────────────────────────
Tarama sirasinda program otomatik olarak:
  • MF/Iht alanina siparis adedini yazar
  • Aciklama alanina depo bilgilerini yazar
  • Botanik'te siparis vermeye hazir hale getirir

NOT: Artik manuel "Siparis Et" butonu yok. Tarama
sirasinda her urun icin otomatik yaziliyor.

▶ KIYASLAMA MODU
─────────────────────────────────────────────────────────────
1. Tabloda bir urun secin
2. "Kiyasla" butonuna basin
3. Yeni pencerede detayli fiyat karsilastirmasi gorun:
   • Her deponun fiyati ve MF secenekleri
   • Efektif fiyatlar (vade faizi dahil)
   • En karli secenekler yildizli gosterilir

▶ AYARLAR DETAYI
─────────────────────────────────────────────────────────────
DEPO AYARLARI (Her depo icin ayri):
  • Aktif/Pasif checkbox: Depoyu taramaya dahil et/etme
  • Kullanici Adi / Sifre: Depo giris bilgileri
  • Odeme Tipi:
    - Vade: X. ayin Y. gunu odeme
    - Kredi Karti: Hesap kesim ve odeme gunleri
  • Depo Siralama: Surukleme ile oncelik siralamasi

SIPARIS AYARLARI:
  • Kac Gunluk Siparis (Varsayilan: 30)
    Ort x Bu_Gun / 30 formuluyle hedef stok hesaplanir
    Ornek: Ort=10, Gun=45 → Hedef = 10 x 45 / 30 = 15

  • Aylik Faiz Orani (Varsayilan: %4)
    Efektif fiyat hesabinda kullanilir
    Vade ne kadar uzunsa, finansal maliyet o kadar artar

  • Efektif Fiyat Goster (Varsayilan: Acik)
    Vade faizi dahil edilmis fiyati gosterir
    Kapatilirsa sadece birim fiyat gosterilir

  • Fiyatlari Goster (Varsayilan: Acik)
    Botanik aciklamasina fiyat bilgisi yazar
    Ornek: "Fz:250,00 All Sel"

  • MF Ozelligi (Varsayilan: Acik)
    Mal fazlasi bilgilerini gosterir
    Aciklamada (10+2) gibi gosterilir

FARMAZON OZEL AYARLARI:
  • Kargo Ucreti (Varsayilan: 140 TL)
    Siparis maliyetine birim basi kargo eklenir

  • Maks. Stok Suresi (Varsayilan: 6 ay)
    Kargo optimizasyonu icin maksimum stok suresi

  • 8 Aydan Uzun Miat (Varsayilan: Acik)
    Acik: Sadece 8+ ay miatli urunleri al
    Kapali: Tum miatlari kabul et

  • Pahalilik Esigi (Varsayilan: %10)
    Fiyat > PSF x (1 + Esik) ise "Pahali" olarak isaretlenir

TARAYICI MODU:
  • Tek Pencere (Sekmeler): Daha az RAM kullanir
  • Ayri Pencereler: Paralel calisir, daha hizli

ECZANE BILGILERI:
  • Eczaci Adi, Eczane Adi, Telefonlar
  • WhatsApp mesajlarinda kullanilir

▶ HTML RAPOR
─────────────────────────────────────────────────────────────
1. "Kaydet" butonuna (💾) basin
2. HTML rapor otomatik olusturulur ve tarayicida acilir
3. Raporda:
   • Tum urunler ve depo fiyatlari
   • Efektif fiyat karsilastirmasi
   • En karli depolar yildizli
   • Depo basligina tikla = siparis sayfasini ac
   • Barkoda tikla = panoya kopyala

▶ KISAYOLLAR
─────────────────────────────────────────────────────────────
  Enter       : Arama yap
  Ctrl+V      : Yapistir ve ara
  Cift tikla  : Siparis adedini duzenle
  Ctrl+Click  : Coklu secim
  ?           : Bu yardim penceresini ac
  ⚙           : Ayarlar penceresini ac

▶ BOTANIK ACIKLAMA FORMATI
─────────────────────────────────────────────────────────────
Aciklama alani su formatta yazilir:
  [Fiyat] [Stoklu Depolar] (MF) [Ara]

Ornekler:
  • "Fz:250,00 All Sel (10+2)"
    Fz fiyati 250 TL, Alliance ve Selcuk'ta var, 10+2 MF

  • "All:180,50/200,00 Koop BEK"
    All fiyati 180.50/200 TL, Koop ve BEK'te var

  • "Fz Pahali"
    Farmazon'da var ama PSF'den pahali, baska depo yok

  • "Ara(Sel Ysf)"
    Selcuk ve Yusuf Pasa temsilcilerini arayin

▶ DESTEKLENEN DEPOLAR
─────────────────────────────────────────────────────────────
  All  : Alliance Healthcare
  Sel  : Selcuk Ecza
  Ysf  : Yusuf Pasa Ecza
  Koop : Istanbul Ecza Koop
  BEK  : Bursa Ecza Koop
  Fz   : Farmazon (Pazar yeri)
  San  : Sancak Ecza

▶ SORUN GIDERME
─────────────────────────────────────────────────────────────
• "Botanik bulunamadi": Siparis Yardimcisi acik olmali
• Depo hatasi: Giris bilgilerini kontrol edin
• Yavas tarama: "Ayri Pencereler" modunu deneyin
• Log dosyalari: logs/ klasorunde detayli bilgi

════════════════════════════════════════════════════════════
        """

        # Yardım penceresi oluştur
        help_window = tk.Toplevel(self.root)
        help_window.title("Kullanim Kilavuzu")
        help_window.geometry("700x700")
        help_window.configure(bg="#f5f6fa")
        help_window.transient(self.root)

        # Başlık
        title_label = tk.Label(
            help_window,
            text="Kullanim Kilavuzu",
            font=("Segoe UI", 14, "bold"),
            bg="#3498db",
            fg="white",
            pady=10
        )
        title_label.pack(fill=tk.X)

        # Text widget
        text_frame = tk.Frame(help_window, bg="#f5f6fa")
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_widget = tk.Text(
            text_frame,
            font=("Consolas", 10),
            bg="#ffffff",
            fg="#2c3e50",
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            padx=10,
            pady=10
        )
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(tk.END, help_text)
        text_widget.config(state=tk.DISABLED)
        scrollbar.config(command=text_widget.yview)

        # Kapat butonu
        close_btn = tk.Button(
            help_window,
            text="Kapat",
            command=help_window.destroy,
            bg="#3498db",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            width=15,
            relief=tk.FLAT,
            cursor="hand2"
        )
        close_btn.pack(pady=10)

    def refresh_ui(self):
        """Ayarlar değiştiğinde UI'yi yeniden oluştur (sütunları güncelle)"""
        try:
            # Kullanılabilir depoları yeniden hesapla
            self.available_depolar = self.controller.get_available_depolar() if self.controller else {}

            # Seçili ürünü kaydet (refresh sonrası yeniden seçmek için)
            old_selected_product = self.selected_product

            # Eski ürünleri kaydet (yeniden eklemek için)
            old_products = self.products.copy()

            # Eski tree widget'ını bul ve parent'ını al
            tree_parent = self.tree.master

            # Eski tree ve scrollbar'ı yok et
            scrollbar = None
            for widget in tree_parent.winfo_children():
                if isinstance(widget, ttk.Scrollbar):
                    scrollbar = widget
                    scrollbar.destroy()
                elif isinstance(widget, ttk.Treeview):
                    widget.destroy()

            # Yeni scrollbar oluştur
            scrollbar = ttk.Scrollbar(tree_parent)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Dinamik sütunlar oluştur (sadece kullanılabilir depoların sütunları)
            base_columns = ["Satır", "Ürün Adı", "Depocu", "Stok", "MF", "MinStk"]

            # Depo sütun mapping
            depo_column_map = {
                "alliance": "All",
                "selcuk": "Sel",
                "yusufpasa": "Ysf",
                "iskoop": "Koop",
                "bursa": "BEK",
                "farmazon": "Fz",
                "sancak": "San"
            }

            # Depo sırasını ayarlardan al
            depo_order = self.controller.get_depo_order() if self.controller else ["alliance", "selcuk", "yusufpasa", "iskoop", "bursa", "farmazon", "sancak"]

            # Sadece kullanılabilir depoların sütunlarını ekle (ayarlardaki sırayla)
            depo_columns = []
            for depo_key in depo_order:
                if depo_key in self.available_depolar:
                    depo_columns.append(depo_column_map[depo_key])

            # Final sütun listesi
            columns = base_columns + depo_columns + ["Sipariş Adet"]
            self.tree = ttk.Treeview(tree_parent, columns=columns, show="headings", yscrollcommand=scrollbar.set)

            # Depo sütunlarını sakla
            self.depo_columns = depo_columns

            # Sütun başlıkları
            for column in columns:
                self.tree.heading(column, text=column)

            # Adaptif sütun ayarları
            self.column_weights = {
                "Satır": 1,
                "Ürün Adı": 4,
                "Depocu": 1,
                "Stok": 1,
                "MF": 1,
                "MinStk": 1,
                "Sipariş Adet": 1
            }

            # Depo sütunlarına weight ekle
            for depo_col in depo_columns:
                self.column_weights[depo_col] = 2

            self.column_min_widths = {
                "Satır": 50,
                "Ürün Adı": 180,
                "Depocu": 70,
                "Stok": 70,
                "MF": 60,
                "MinStk": 60,
                "Sipariş Adet": 90
            }

            # Depo sütunlarına min width ekle
            for depo_col in depo_columns:
                self.column_min_widths[depo_col] = 90

            for column in columns:
                anchor = "w"
                if column in ["Satır", "Depocu", "Stok", "MF", "MinStk", "Sipariş Adet"] or column in depo_columns:
                    anchor = "center"
                self.tree.column(column, anchor=anchor, stretch=True)

            self.tree.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=self.tree.yview)

            # Event binding'leri yeniden ekle
            self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
            self.tree.bind("<Double-1>", self.on_tree_double_click)
            self.tree.bind("<Configure>", lambda e: self.adjust_tree_columns())

            # Sütun genişliklerini ayarla
            self.adjust_tree_columns()

            # Ürünleri yeniden ekle
            self.products = []
            for product_info in old_products:
                self.add_product_row(product_info["data"])

            logger.info(f"UI yenilendi - {len(self.available_depolar)} depo aktif")
            self.status_label.config(text=f"✅ Ayarlar güncellendi - {len(self.available_depolar)} depo aktif")

            # Eski seçili ürünü yeniden seç (aylık gidiş ve şartlar tablosunu yeniden yüklemek için)
            if old_selected_product:
                # Satır numarasını bul (satir_no veya row alanı)
                old_row_num = old_selected_product.get("data", {}).get("satir_no") or old_selected_product.get("data", {}).get("row")
                if old_row_num:
                    # Yeni tree'de bu satır numarasını bul
                    for item in self.tree.get_children():
                        values = self.tree.item(item)["values"]
                        if values and values[0] == old_row_num:
                            # Bulundu! Yeniden seç
                            self.tree.selection_set(item)
                            self.tree.focus(item)
                            self.tree.see(item)
                            self.selected_product = old_selected_product
                            logger.info(f"Seçili ürün (Satır {old_row_num}) yeniden seçildi")
                            break

            # Şartlar tablosunu yenile (bu içinde seçili öğe için tabloları da günceller)
            self.refresh_sartlar_table()

        except Exception as e:
            logger.error(f"UI yenileme hatası: {e}")
            from tkinter import messagebox
            messagebox.showerror("Hata", f"UI güncellenirken hata: {e}")

    def refresh_sartlar_table(self):
        """Şartlar tablosunu sadece aktif depolarla yeniden oluştur"""
        try:
            # Depo sırasını ayarlardan al
            depo_order = self.controller.get_depo_order() if self.controller else self.sartlar_depo_list

            # Aktif depo listesini sıralı şekilde oluştur
            active_depo_list = [d for d in depo_order if d in self.available_depolar]

            # Eski tabloyu temizle
            sartlar_tree_parent = self.sartlar_tree.master

            # Eski scrollbar ve tree'yi yok et
            for widget in sartlar_tree_parent.winfo_children():
                widget.destroy()

            # Yeni sütunları oluştur
            sartlar_columns = []
            for depo_key in active_depo_list:
                sartlar_columns.append(f"{depo_key}_sart")
                sartlar_columns.append(f"{depo_key}_fiyat")

            # Yeni Treeview oluştur
            self.sartlar_tree = ttk.Treeview(sartlar_tree_parent, columns=sartlar_columns, show="headings", height=5)

            # Scrollbar ekle
            sartlar_scrollbar = ttk.Scrollbar(sartlar_tree_parent, orient="vertical", command=self.sartlar_tree.yview)
            self.sartlar_tree.configure(yscrollcommand=sartlar_scrollbar.set)

            # Başlıkları ayarla
            for depo_key in active_depo_list:
                depo_name = self.sartlar_depo_names.get(depo_key, depo_key)
                self.sartlar_tree.heading(f"{depo_key}_sart", text=f"{depo_name}")
                self.sartlar_tree.heading(f"{depo_key}_fiyat", text="Fiyat")
                self.sartlar_tree.column(f"{depo_key}_sart", width=70, anchor="center")
                self.sartlar_tree.column(f"{depo_key}_fiyat", width=70, anchor="center")

            self.sartlar_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sartlar_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # Boş satır ekle
            empty_values = ["-"] * len(sartlar_columns)
            self.sartlar_tree.insert("", tk.END, values=empty_values)

            # Aktif depo listesini sakla (update_sartlar_table için)
            self.active_sartlar_depo_list = active_depo_list

            logger.info(f"Şartlar tablosu yenilendi - {len(active_depo_list)} depo aktif")

            # Eğer ana tabloda seçili bir öğe varsa, şartları ve aylık gidişi güncelle
            try:
                selected = self.tree.selection()
                if selected:
                    # Seçili öğenin verisini al ve tabloları güncelle
                    self.on_row_selected(None)
                    logger.debug("Seçili öğe için şartlar ve aylık gidiş tabloları güncellendi")
            except Exception as e:
                logger.debug(f"Seçili öğe tabloları güncellenemedi: {e}")

        except Exception as e:
            logger.error(f"Şartlar tablosu yenileme hatası: {e}")

    def on_new_depots_enabled(self, newly_enabled_depots):
        """Ayarlardan yeni depolar açıldığında çağrılır

        Tarama devam ediyorsa bu depoların pencerelerini açar ve taramaya dahil eder.

        Args:
            newly_enabled_depots: Yeni açılan depo isimleri listesi (örn: ["sancak", "selcuk"])
        """
        if not newly_enabled_depots:
            return

        logger.info(f"🆕 Yeni açılan depolar: {newly_enabled_depots}")

        # Tarama devam ediyor mu kontrol et (normal veya kıyas)
        scan_in_progress = self.is_scanning or self.kiyas_scanning

        if not scan_in_progress:
            logger.info("Aktif tarama yok, sadece UI güncellendi")
            return

        # Yeni depoları aç ve available_depolar'a ekle
        try:
            import os
            from pathlib import Path
            from dotenv import load_dotenv

            # .env'yi yeniden yükle
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            load_dotenv(env_path, override=True)

            # Depo class mapping
            from ..depolar.selcuk import SelcukDepo
            from ..depolar.sancak import SancakDepo
            from ..depolar.alliance import AllianceDepo
            from ..depolar.yusufpasa import YusufpasaDepo
            from ..depolar.iskoop import IskoopDepo
            from ..depolar.bursa import BursaDepo
            from ..depolar.farmazon import FarmazonDepo

            depo_class_map = {
                "selcuk": SelcukDepo,
                "sancak": SancakDepo,
                "alliance": AllianceDepo,
                "yusufpasa": YusufpasaDepo,
                "iskoop": IskoopDepo,
                "bursa": BursaDepo,
                "farmazon": FarmazonDepo,
            }

            # Tarayıcı modunu kontrol et
            browser_mode = os.environ.get("BROWSER_MODE", "tabs")

            for depo_name in newly_enabled_depots:
                if depo_name not in depo_class_map:
                    logger.warning(f"Bilinmeyen depo: {depo_name}")
                    continue

                if depo_name in self.available_depolar:
                    logger.info(f"{depo_name} zaten açık")
                    continue

                try:
                    # Depo instance oluştur
                    depo_class = depo_class_map[depo_name]
                    depo = depo_class()

                    # Tarayıcıyı aç
                    logger.info(f"🌐 {depo_name} tarayıcısı açılıyor...")

                    if browser_mode == "windows":
                        # Ayrı pencere
                        depo.open_browser()
                    else:
                        # Mevcut tarayıcıda yeni sekme
                        if self.available_depolar:
                            # İlk deponun driver'ını kullan
                            first_depo = list(self.available_depolar.values())[0]
                            if first_depo.driver:
                                depo.driver = first_depo.driver
                                depo.driver.execute_script("window.open('');")
                                depo.driver.switch_to.window(depo.driver.window_handles[-1])
                                depo.driver.get(depo.url)
                                depo.tab_index = len(depo.driver.window_handles) - 1
                        else:
                            depo.open_browser()

                    # Giriş yap
                    username_key = f"{depo_name.upper()}_USERNAME"
                    password_key = f"{depo_name.upper()}_PASSWORD"
                    username = os.environ.get(username_key, "")
                    password = os.environ.get(password_key, "")

                    if username and password:
                        if depo.login(username, password):
                            logger.info(f"✅ {depo_name} giriş başarılı")
                            self.available_depolar[depo_name] = depo
                            self.status_label.config(text=f"✅ {depo_name} taramaya eklendi")
                        else:
                            logger.error(f"❌ {depo_name} giriş başarısız")
                    else:
                        logger.warning(f"⚠️ {depo_name} kullanıcı bilgileri eksik")

                except Exception as e:
                    logger.error(f"❌ {depo_name} açılırken hata: {e}")

            logger.info(f"Aktif depolar: {list(self.available_depolar.keys())}")

        except Exception as e:
            logger.error(f"Yeni depolar açılırken hata: {e}")

    def start_fast_scan(self):
        """Hızlı taramayı başlat / Duraklat / Devam Et"""
        # Tarama çalışıyorsa - duraklat/devam et
        if self.is_scanning and hasattr(self, 'is_fast_scan_mode') and self.is_fast_scan_mode:
            if self.is_paused:
                # Devam et
                self.is_paused = False
                self.pause_event.set()
                self.fast_scan_button.config(text="Duraklat", bg="#E67E22")
                self.status_label.config(text="Hızlı tarama devam ediyor...")
                logger.info("Hızlı tarama devam ettiriliyor...")
            else:
                # Duraklat
                self.is_paused = True
                self.pause_event.clear()
                self.fast_scan_button.config(text="Devam Et", bg="#FF6B00")
                self.status_label.config(text="Hızlı tarama duraklatıldı")
                logger.info("Hızlı tarama duraklatıldı")
            return

        # Başka bir tarama çalışıyorsa
        if self.is_scanning:
            messagebox.showwarning("Uyarı", "Zaten bir tarama devam ediyor!")
            return

        # Devam modu mu kontrol et (buton metnine bak)
        button_text = self.fast_scan_button.cget("text")
        is_continue_mode = "Devam" in button_text

        # Hızlı tarama başlat
        self.is_scanning = True
        self.is_fast_scan_mode = True
        self.is_paused = False
        self.pause_event.set()

        # Butonları güncelle
        self.fast_scan_button.config(text="Duraklat", bg="#E67E22", state=tk.NORMAL)

        if is_continue_mode:
            # DEVAM MODU: Önce Botanik ile senkronize ol
            self.status_label.config(text="Botanik ile senkronize ediliyor...")
            logger.info("DEVAM MODU: Botanik senkronizasyonu başlıyor...")

            # Tabloyu ve ürünleri TEMİZLEME (devam modunda mevcut veriler korunacak)
            # Timer'ı başlat
            import time
            self.start_time = time.time()
            self.elapsed_seconds = 0
            self.update_timer()

            # Arka planda senkronize et ve taramaya devam et
            thread = threading.Thread(target=self._run_continue_scan_with_sync, daemon=True)
            thread.start()
        else:
            # YENİ TARAMA: Tabloyu ve listeyi temizle
            self.status_label.config(text="Hızlı tarama başlıyor...")
            logger.info("HIZLI TARAMA başlatılıyor...")

            self.tree.delete(*self.tree.get_children())
            self.products = []
            self.all_products_backup = []

            # CSV'leri temizle
            if self.controller:
                self.controller.clear_monthly_sales_csv()
                import os
                mf_enabled = os.getenv("MF_ENABLED", "true").lower() == "true"
                if mf_enabled:
                    self.controller.clear_mf_csv()
                # Önceki tarama JSON'unu temizle
                try:
                    if self.controller.scan_results_file.exists():
                        self.controller.scan_results_file.unlink()
                except Exception as e:
                    logger.warning(f"Tarama JSON temizlenemedi: {e}")

            # Timer'ı başlat
            import time
            self.start_time = time.time()
            self.elapsed_seconds = 0
            self.update_timer()

            # Arka planda hızlı tarama yap
            thread = threading.Thread(target=self._run_fast_scan, daemon=True)
            thread.start()

    def _sync_with_botanik(self):
        """Botanik'teki mevcut ürünlerle GUI listesini senkronize et

        Manuel sipariş verilen ürünler Botanik'ten silinmiş olacak.
        Bu fonksiyon GUI'den bu ürünleri kaldırır.

        Returns:
            int: Kaldırılan ürün sayısı
        """
        try:
            # Botanik'e bağlan
            if not self.controller.botanik.connect():
                logger.error("Botanik'e bağlanılamadı, senkronizasyon atlanıyor")
                return 0

            # Botanik'teki mevcut ürün isimlerini al
            botanik_names = self.controller.botanik.get_all_product_names_fast()

            if not botanik_names:
                logger.warning("Botanik'ten ürün isimleri okunamadı, senkronizasyon atlanıyor")
                return 0

            logger.info(f"Botanik'te {len(botanik_names)} ürün bulundu")

            # GUI'deki ürünleri kontrol et
            items_to_remove = []
            for item_id in self.tree.get_children():
                values = self.tree.item(item_id, "values")
                if values:
                    # Ürün adı 2. sütunda (index 1)
                    gui_product_name = turkish_lower(str(values[1]).strip()) if len(values) > 1 else ""

                    if gui_product_name and gui_product_name not in botanik_names:
                        items_to_remove.append(item_id)
                        logger.info(f"  ❌ '{values[1]}' Botanik'te yok, kaldırılacak")

            # Ürünleri GUI'den kaldır
            removed_count = 0
            for item_id in items_to_remove:
                try:
                    # products listesinden de kaldır
                    values = self.tree.item(item_id, "values")
                    product_name = turkish_lower(str(values[1]).strip()) if len(values) > 1 else ""

                    self.products = [p for p in self.products
                                     if turkish_lower(p.get("data", {}).get("urun_adi", "").strip()) != product_name]

                    # Treeview'den kaldır
                    self.tree.delete(item_id)
                    removed_count += 1
                except Exception as e:
                    logger.warning(f"Ürün kaldırılırken hata: {e}")

            if removed_count > 0:
                logger.info(f"✓ {removed_count} ürün Botanik'te bulunamadığı için kaldırıldı")
            else:
                logger.info("✓ Tüm ürünler Botanik'te mevcut, kaldırılacak ürün yok")

            return removed_count

        except Exception as e:
            logger.error(f"Botanik senkronizasyonu hatası: {e}")
            return 0

    def _run_continue_scan_with_sync(self):
        """Senkronizasyon yaparak devam et

        Kullanıcı manuel sipariş verdikten sonra, o ürünler Botanik'ten silinmiş olur.
        Veya Botanik'e yeni ürünler eklenmiş olabilir.

        Bu fonksiyon:
        1. Botanik'teki güncel ürün listesini okur
        2. GUI'deki ürünlerle karşılaştırır
        3. Botanik'te olmayan ürünleri GUI'den kaldırır
        4. Botanik'te olup GUI'de olmayan ürünleri tarar ve ekler
        5. last_scan.json'u günceller
        """
        try:
            import time

            # 1. Önce Botanik ile senkronize ol
            self.root.after(0, lambda: self.status_label.config(text="Botanik ile senkronize ediliyor..."))

            # Akıllı sync: önce son ürünü kontrol et
            sync_needed, removed_count, rows_to_scan = self._smart_sync_with_botanik()

            # GUI'yi güncelle
            remaining_count = len(self.tree.get_children())

            if removed_count > 0:
                # Ürünler silindi - last_scan.json'u güncelle
                try:
                    if self.controller and hasattr(self.controller, 'products'):
                        self.controller.products = [
                            p for p in self.controller.products
                            if any(
                                turkish_lower(p.get("urun_adi", "").strip()) ==
                                turkish_lower(str(self.tree.item(item_id, "values")[1]).strip())
                                for item_id in self.tree.get_children()
                                if len(self.tree.item(item_id, "values")) > 1
                            )
                        ]
                        self.controller.save_scan_results()
                        logger.info(f"✓ last_scan.json güncellendi: {len(self.controller.products)} ürün")
                except Exception as e:
                    logger.warning(f"last_scan.json güncellenemedi: {e}")

            # Taranacak satır var mı?
            if rows_to_scan:
                count = len(rows_to_scan)
                botanik_total = max(rows_to_scan)  # En büyük satır no = toplam
                first_row = min(rows_to_scan)  # İlk taranacak satır
                self.root.after(0, lambda: self.status_label.config(
                    text=f"{remaining_count}/{botanik_total} - Taranıyor..."))
                logger.info(f"🔍 {count} satır taranacak: {rows_to_scan[:5]}... (toplam {botanik_total})")

                time.sleep(0.5)

                # Sadece bu satırları tara (botanik_total'ı da gönder)
                result = self.controller.run_fast_scan_for_rows(rows_to_scan, botanik_total)

                if result:
                    new_count = len(self.tree.get_children()) - remaining_count
                    if removed_count > 0:
                        final_msg = f"✓ {removed_count} silindi, {new_count} eklendi"
                    else:
                        final_msg = f"✓ {new_count} yeni ürün eklendi"
                else:
                    final_msg = f"✓ {removed_count} silindi, tarama başarısız"
            else:
                if removed_count > 0:
                    final_msg = f"✓ {removed_count} ürün silindi, {remaining_count} kaldı"
                else:
                    final_msg = "✓ Tüm ürünler güncel"
                logger.info(final_msg)

            self.root.after(0, lambda msg=final_msg: self.status_label.config(text=msg))

            # Kısa bekleme (kullanıcı mesajı görsün)
            time.sleep(2)

        except Exception as e:
            logger.error(f"Senkronizasyon hatası: {e}")
            self.root.after(0, lambda: messagebox.showerror("Hata", f"Senkronizasyon sırasında hata: {e}"))
        finally:
            # Timer'ı durdur
            if self.timer_job:
                self.root.after_cancel(self.timer_job)
                self.timer_job = None

            # Butonları eski haline getir
            def reset_buttons():
                self.is_scanning = False
                self.is_fast_scan_mode = False
                # Hala ürün varsa devam butonu olarak kalsın
                remaining = len(self.tree.get_children())
                if remaining > 0:
                    self.fast_scan_button.config(text="⚡ Taramaya Devam Et", bg="#FF9800", state=tk.NORMAL)
                else:
                    self.fast_scan_button.config(text="Taramayi Baslat", bg=self.colors["success"], state=tk.NORMAL)
                self.status_label.config(text=f"Senkronizasyon tamamlandı - {remaining} ürün")

            self.root.after(0, reset_buttons)

    def _smart_sync_with_botanik(self):
        """Akıllı senkronizasyon - Önce sayıları karşılaştır, sonra son ürünü kontrol et

        OPTİMİZE Mantık:
        1. GUI'deki ürün sayısını ve son ürünü al
        2. Botanik'teki toplam satır sayısını al (çok hızlı - "X Kalem" label'dan)
        3. Sayılar eşitse:
           - Sadece son satırın ürün adını oku (tek satır okuma)
           - Eşleşirse → Senkron, sonraki satırlardan devam et
           - Eşleşmezse → Tam sync gerekli
        4. Sayılar farklıysa → Tam sync gerekli

        Returns:
            tuple: (sync_gerekli_mi, silinen_sayısı, taranacak_satırlar)
        """
        try:
            # Botanik'e bağlan
            if not self.controller.botanik.connect():
                logger.error("Botanik'e bağlanılamadı")
                return False, 0, []

            # GUI'deki ürün sayısı
            gui_items = self.tree.get_children()
            gui_count = len(gui_items)

            if gui_count == 0:
                logger.info("GUI boş, tam tarama gerekli")
                return False, 0, []

            # GUI'deki son ürünü bul
            last_item_id = gui_items[-1]
            last_values = self.tree.item(last_item_id, "values")

            if not last_values or len(last_values) < 2:
                logger.warning("Son ürün bilgisi okunamadı")
                return False, 0, []

            gui_last_row = int(last_values[0])  # İlk sütun = satır no
            gui_last_name = turkish_lower(str(last_values[1]).strip())  # İkinci sütun = ürün adı

            logger.info(f"GUI: {gui_count} ürün, son satır {gui_last_row} - '{gui_last_name}'")

            # HIZLI: Botanik'teki toplam satır sayısını al (scroll yapmadan "X Kalem" label'dan)
            botanik_total = self.controller.botanik.get_total_row_count(refresh=True)

            if botanik_total is None:
                logger.warning("Botanik satır sayısı okunamadı, tam sync yapılacak")
                botanik_products = self.controller.botanik.get_all_product_names_with_rows()
                return self._full_sync_with_botanik(botanik_products)

            logger.info(f"Botanik: {botanik_total} ürün (hızlı okuma)")

            # SAYILARI KARŞILAŞTIR
            if gui_count == botanik_total:
                # Sayılar eşit! Sadece son ürün adını kontrol et (çok hızlı)
                logger.info(f"✓ Sayılar eşit ({gui_count}={botanik_total}), son ürün kontrol ediliyor...")

                # Botanik'te gui_last_row satırındaki ürün adını oku (tek satır)
                botanik_last_name = self.controller.botanik.get_product_name_at_row(gui_last_row)

                if botanik_last_name is None:
                    logger.warning(f"Botanik satır {gui_last_row} okunamadı, tam sync yapılacak")
                    botanik_products = self.controller.botanik.get_all_product_names_with_rows()
                    return self._full_sync_with_botanik(botanik_products)

                # İsimler eşleşiyor mu?
                if gui_last_name == botanik_last_name:
                    # MÜKEMMEL! Satırlar senkron, hiç tarama gerekmez
                    logger.info(f"✅ Son ürünler eşleşiyor: '{gui_last_name}' = '{botanik_last_name}'")
                    logger.info("✅ Satırlar tamamen senkron, yeni ürün yok")
                    return False, 0, []
                else:
                    # Sayılar eşit ama isimler farklı - bu garip durum
                    # Belki bir ürün silinip yerine başkası gelmiş
                    logger.warning(f"⚠ Sayılar eşit ama isimler farklı: GUI='{gui_last_name}', Botanik='{botanik_last_name}'")
                    logger.info("Tam senkronizasyon yapılacak...")
                    botanik_products = self.controller.botanik.get_all_product_names_with_rows()
                    return self._full_sync_with_botanik(botanik_products)

            elif botanik_total > gui_count:
                # Botanik'te daha fazla ürün var - yeni ürünler eklenmiş
                logger.info(f"➕ Botanik'te {botanik_total - gui_count} yeni ürün var")

                # Önce son ürünlerin eşleşip eşleşmediğini kontrol et
                botanik_last_name = self.controller.botanik.get_product_name_at_row(gui_last_row)

                if botanik_last_name and gui_last_name == botanik_last_name:
                    # Son ürünler eşleşiyor, sadece sonraki satırları tara
                    logger.info(f"✓ Son ürünler eşleşiyor, satır {gui_last_row + 1}'den devam edilecek")
                    next_rows = list(range(gui_last_row + 1, botanik_total + 1))
                    logger.info(f"➕ {len(next_rows)} yeni satır taranacak: {next_rows[:5]}...")
                    return False, 0, next_rows
                else:
                    # Son ürünler eşleşmiyor, tam sync gerekli
                    logger.warning(f"⚠ Son ürünler eşleşmiyor: GUI='{gui_last_name}', Botanik='{botanik_last_name}'")
                    logger.info("Tam senkronizasyon yapılacak...")
                    botanik_products = self.controller.botanik.get_all_product_names_with_rows()
                    return self._full_sync_with_botanik(botanik_products)

            else:
                # Botanik'te daha az ürün var - bazı ürünler silinmiş (okunmuş)
                logger.info(f"❌ Botanik'te {gui_count - botanik_total} ürün eksik (sipariş verilmiş)")
                logger.info("Tam senkronizasyon yapılacak...")
                botanik_products = self.controller.botanik.get_all_product_names_with_rows()
                return self._full_sync_with_botanik(botanik_products)

        except Exception as e:
            logger.error(f"Akıllı sync hatası: {e}")
            return False, 0, []

    def _full_sync_with_botanik(self, botanik_products):
        """Tam senkronizasyon - satır uyumsuzluğu varsa çağrılır

        Bu fonksiyon:
        1. GUI'de olup Botanik'te olmayan ürünleri siler
        2. Kalan ürünlerin satır numaralarını Botanik ile eşleştirir
        3. Botanik'te olup GUI'de olmayan ürünleri taranmak üzere döndürür

        Args:
            botanik_products: {isim: satır_no} dictionary

        Returns:
            tuple: (sync_yapıldı, silinen_sayısı, taranacak_satırlar)
        """
        try:
            botanik_names = set(botanik_products.keys())

            # GUI'deki ürün isimlerini al
            gui_names = set()
            for item_id in self.tree.get_children():
                values = self.tree.item(item_id, "values")
                if values and len(values) > 1:
                    gui_names.add(turkish_lower(str(values[1]).strip()))

            # 1. GUI'de olup Botanik'te olmayan ürünleri bul (silinecek)
            items_to_remove = []
            for item_id in self.tree.get_children():
                values = self.tree.item(item_id, "values")
                if values and len(values) > 1:
                    gui_product_name = turkish_lower(str(values[1]).strip())
                    if gui_product_name and gui_product_name not in botanik_names:
                        items_to_remove.append(item_id)
                        logger.info(f"  ❌ '{values[1]}' Botanik'te yok, silinecek")

            # 2. Botanik'te olup GUI'de olmayan ürünlerin satır numaralarını bul
            missing_rows = []
            for name, row_num in botanik_products.items():
                if name not in gui_names:
                    missing_rows.append(row_num)
                    logger.info(f"  ➕ Satır {row_num}: '{name}' taranacak")

            # 3. Ürünleri GUI'den sil
            removed_count = 0
            for item_id in items_to_remove:
                try:
                    values = self.tree.item(item_id, "values")
                    product_name = turkish_lower(str(values[1]).strip()) if len(values) > 1 else ""

                    self.products = [p for p in self.products
                                     if turkish_lower(p.get("data", {}).get("urun_adi", "").strip()) != product_name]

                    self.tree.delete(item_id)
                    removed_count += 1
                except Exception as e:
                    logger.warning(f"Ürün silinirken hata: {e}")

            if removed_count > 0:
                logger.info(f"✓ {removed_count} ürün silindi")

            # 4. KALAN ÜRÜNLERİN SATIR NUMARALARINI BOTANİK İLE EŞLEŞTİR
            updated_count = 0
            for item_id in self.tree.get_children():
                try:
                    values = list(self.tree.item(item_id, "values"))
                    if not values or len(values) < 2:
                        continue

                    gui_product_name = turkish_lower(str(values[1]).strip())
                    if not gui_product_name:
                        continue

                    botanik_row = botanik_products.get(gui_product_name)
                    if botanik_row is None:
                        continue

                    # Mevcut satır numarasını güvenli şekilde al
                    try:
                        current_row = int(values[0]) if values[0] else 0
                    except (ValueError, TypeError):
                        current_row = 0

                    # Satır numarası farklıysa güncelle
                    if current_row != botanik_row:
                        values[0] = str(botanik_row)  # TreeView için string
                        self.tree.item(item_id, values=tuple(values))

                        # products listesindeki satır numarasını da güncelle
                        for p in self.products:
                            # Farklı veri yapılarını destekle
                            urun_adi = ""
                            if isinstance(p, dict):
                                if "data" in p and isinstance(p["data"], dict):
                                    urun_adi = p["data"].get("urun_adi", "")
                                else:
                                    urun_adi = p.get("urun_adi", "")

                            if urun_adi and turkish_lower(str(urun_adi).strip()) == gui_product_name:
                                if "data" in p and isinstance(p["data"], dict):
                                    p["data"]["satir_no"] = botanik_row
                                    p["data"]["row"] = botanik_row
                                else:
                                    p["satir_no"] = botanik_row
                                    p["row"] = botanik_row
                                break

                        updated_count += 1
                        logger.debug(f"  ↔ '{values[1]}' satır {current_row} → {botanik_row}")
                except Exception as e:
                    logger.warning(f"Satır numarası güncellenirken hata: {e}")

            if updated_count > 0:
                logger.info(f"✓ {updated_count} ürünün satır numarası güncellendi")

            # 5. TreeView'ü satır numarasına göre sırala
            self._sort_treeview_by_row()

            missing_rows.sort()
            return True, removed_count, missing_rows

        except Exception as e:
            logger.error(f"Tam sync hatası: {e}")
            return False, 0, []

    def _sort_treeview_by_row(self):
        """TreeView'ü satır numarasına göre sırala (küçükten büyüğe)"""
        try:
            # Tüm item'ları ve satır numaralarını al
            items_with_rows = []
            for item_id in self.tree.get_children():
                values = self.tree.item(item_id, "values")
                if values:
                    try:
                        row_num = int(values[0]) if values[0] else 999999
                    except (ValueError, TypeError):
                        row_num = 999999
                    items_with_rows.append((row_num, item_id))

            # Satır numarasına göre sırala
            items_with_rows.sort(key=lambda x: x[0])

            # TreeView'ü yeniden sırala
            for idx, (row_num, item_id) in enumerate(items_with_rows):
                self.tree.move(item_id, '', idx)

            logger.debug(f"TreeView {len(items_with_rows)} satır sıralandı")

        except Exception as e:
            logger.warning(f"TreeView sıralama hatası: {e}")

    def _run_fast_scan(self):
        """Hızlı taramayı arka planda çalıştır"""
        try:
            result = self.controller.run_fast_scan()
            if result:
                logger.info("Hızlı tarama başarıyla tamamlandı")
            else:
                logger.warning("Hızlı tarama başlatılamadı")
        except Exception as e:
            logger.error(f"Hızlı tarama hatası: {e}")
            self.root.after(0, lambda: messagebox.showerror("Hata", f"Hızlı tarama sırasında hata: {e}"))
        finally:
            # Timer'ı durdur
            if self.timer_job:
                self.root.after_cancel(self.timer_job)
                self.timer_job = None

            # Butonları eski haline getir
            def reset_buttons():
                self.is_scanning = False
                self.is_fast_scan_mode = False
                self.fast_scan_button.config(text="Hizli Tarama", bg="#FF6B00", state=tk.NORMAL)
                self.fast_scan_button.config(text="Taramayi Baslat", bg=self.colors["success"], state=tk.NORMAL)
                self.status_label.config(text="Hızlı tarama tamamlandı")

            self.root.after(0, reset_buttons)

    def update_timer(self):
        """Timer'ı her saniye güncelle"""
        if self.is_scanning and not self.is_paused:
            import time
            self.elapsed_seconds = int(time.time() - self.start_time)
            minutes = self.elapsed_seconds // 60
            seconds = self.elapsed_seconds % 60

            # Son ilaç süresi varsa ekle
            if self.last_product_duration > 0:
                self.timer_label.config(
                    text=f"Süre: {minutes:02d}:{seconds:02d}  |  Son İlaç: {self.last_product_duration:.1f}s"
                )
            else:
                self.timer_label.config(text=f"Süre: {minutes:02d}:{seconds:02d}")

            # 1 saniye sonra tekrar çağır
            self.timer_job = self.root.after(1000, self.update_timer)
        elif self.is_paused:
            # Duraklatıldıysa timer'ı tekrar çağır ama süreyi güncelleme
            self.timer_job = self.root.after(1000, self.update_timer)

    def _run_scan(self):
        """Taramayı arka planda çalıştır"""
        scan_completed_successfully = False
        try:
            # Devam modunu kontrol et
            continue_scan = getattr(self, 'is_continue_scan', False)
            result = self.controller.run(continue_scan=continue_scan)
            if result:
                scan_completed_successfully = True  # Hatasız tamamlandı
            else:
                # Botanik bağlanamadı gibi durumlarda
                logger.warning("Tarama başlatılamadı (controller.run False döndü)")
        except Exception as e:
            logger.error(f"Tarama hatası: {e}")
            self.root.after(0, lambda: messagebox.showerror("Hata", f"Tarama sırasında hata: {e}"))
        finally:
            # Timer'ı durdur
            if self.timer_job:
                self.root.after_cancel(self.timer_job)
                self.timer_job = None

            # Tarama bitti, durumu sıfırla
            self.is_scanning = False
            self.is_paused = False
            self.pause_event.set()
            self.root.after(0, lambda: self.fast_scan_button.config(text="⚡ Hızlı Tarama", bg="#FF6B00", state=tk.NORMAL))

            # Depo pencerelerini açık bırak (birleştirme session'ları bozuyor)
            # Not: merge_browser_windows_to_tabs() artık çağrılmıyor çünkü
            # farklı Chrome instance'ları arasında cookie paylaşılmadığı için
            # depolardan çıkış yapılıyordu.
            if scan_completed_successfully:
                logger.info("Tarama başarıyla tamamlandı, depolar açık kalacak...")

            # Final süreyi göster
            final_time = self.timer_label.cget("text")
            self.root.after(0, lambda: self.status_label.config(text=f"Tarama tamamlandı - {final_time}"))

            # Pencereleri sipariş verme konumuna getir
            if scan_completed_successfully:
                try:
                    logger.info("Tarama tamamlandı, pencereler sipariş konumuna getiriliyor...")

                    # Botanik Sipariş Yardımcısı'nı sol üst köşeye
                    if self.controller and self.controller.botanik:
                        self.controller.botanik.position_for_ordering()

                    # GUI'yi sol alt köşeye
                    time.sleep(0.2)  # Botanik konumlandıktan sonra
                    self.position_for_ordering()

                except Exception as e:
                    logger.error(f"Pencere konumlandırma hatası: {e}")

    def on_tree_click(self, event):
        """Tablo tıklama olayı"""
        try:
            import pyperclip
            import time

            # Tıklanan hücreyi bul
            region = self.tree.identify("region", event.x, event.y)
            if region != "cell":
                return

            # Tıklanan satır ve sütunu al
            item = self.tree.identify_row(event.y)
            column = self.tree.identify_column(event.x)

            if not item or not column:
                return

            # Sütun numarasını al (1'den başlar)
            col_num = int(column[1:]) - 1

            # Dinamik sütun listesi
            base_columns = ["Satır", "Ürün Adı", "Depocu", "Stok", "MF", "MinStk"]
            all_columns = base_columns + self.depo_columns + ["Sipariş Adet"]
            col_name = all_columns[col_num] if col_num < len(all_columns) else None

            if not col_name:
                return

            # Satır değerlerini al
            values = list(self.tree.item(item, "values"))
            urun_adi = values[1]  # Ürün adı (sütun 0=satır, 1=ürün adı)

            # Barkod bilgisini products listesinden al
            barkod = None
            for product in self.products:
                if product["item_id"] == item:
                    barkod = product["data"].get("barkod", "-")
                    break

            # ÜRÜN ADI sütununa tıklandıysa → Barkodu panoya kopyala
            if col_name == "Ürün Adı":
                if barkod and barkod != "-":
                    pyperclip.copy(barkod)
                    self.status_label.config(text=f"📋 Barkod kopyalandı: {urun_adi} - {barkod}")
                    logger.info(f"Barkod kopyalandı: {barkod}")
                else:
                    self.status_label.config(text=f"⚠️ Bu ürün için barkod bulunamadı!")

            # DEPO sütunlarına tıklandıysa → O depoda ürünü ara ve browser'ı öne çıkar
            elif col_name in self.depo_columns:
                # Tıklanan depo hücresini güncelle (duruma göre farklı simge)
                current_val = values[col_num]
                if current_val == "🔘":  # VAR ise → ✅ (yeşil tik - açıldı/sipariş verildi)
                    values[col_num] = "✅"
                else:  # ARA veya YOK ise → ☑ (siyah tik - kontrol edildi)
                    values[col_num] = "☑"
                self.tree.item(item, values=values)

                if not barkod or barkod == "-":
                    messagebox.showwarning("Uyarı", "Bu ürün için barkod bulunamadı!")
                    return

                depo_map = {
                    "All": "alliance",
                    "Sel": "selcuk",
                    "Ysf": "yusufpasa",
                    "Koop": "iskoop",
                    "BEK": "bursa",
                    "Fz": "farmazon",
                    "San": "sancak"
                }
                depo_key = depo_map.get(col_name)

                if not depo_key:
                    return

                # Controller'dan depo al
                if self.controller and depo_key in self.controller.depolar:
                    depo = self.controller.depolar[depo_key]

                    # Depo açık mı kontrol et
                    if not depo.driver:
                        self.status_label.config(text=f"⚠️ {col_name} deposu açık değil! Önce tarama yapın.")
                        return

                    # Depo browser'ını öne çıkar ve ürünü ara
                    try:
                        # GUI'yi güncelle - işlem başlıyor
                        self.status_label.config(text=f"⏳ {col_name} deposunda aranıyor...")
                        self.root.update()  # GUI'yi hemen güncelle (donma olmasın)

                        # Önce tab'a geç (browser'ı aktif yap)
                        depo.switch_to_tab()
                        time.sleep(0.2)

                        # Barkod araması yap (önce ara, sonra öne çıkar)
                        if depo.search_barcode(barkod):
                            logger.info(f"{col_name} deposunda arama başarılı: {barkod}")

                            # Browser'ı MUTLAKA öne çıkar (kullanıcı görebilsin)
                            brought_to_front = False
                            if hasattr(depo, "focus_browser"):
                                try:
                                    # Ana pencereyi sola kaydır (eğer sağdaysa)
                                    self.move_window_to_left()

                                    # Status'u güncelle: Browser öne getiriliyor...
                                    self.status_label.config(text=f"⏳ {col_name} browser'ı öne getiriliyor...")
                                    self.root.update()  # GUI'yi hemen güncelle

                                    brought_to_front = depo.focus_browser()
                                    time.sleep(0.5)  # Browser'ın öne gelmesi için bekleme

                                    if brought_to_front:
                                        logger.info(f"✓ {col_name} browser penceresi öne çıkarıldı")
                                    else:
                                        logger.warning(f"⚠ {col_name} browser öne çıkarılamadı")
                                except Exception as e:
                                    logger.warning(f"{col_name} focus_browser hatası: {e}")

                            # Sipariş adedini depo ekranına yaz
                            product = self.get_product_by_item(item)
                            siparis_adet = None
                            if product:
                                siparis_adet = product.get("siparis_adet")

                            # Final status mesajı (browser durumunu belirt)
                            if brought_to_front:
                                if siparis_adet and siparis_adet > 0:
                                    depo_success = depo.set_order_quantity(siparis_adet)

                                    if depo_success:
                                        self.status_label.config(text=f"✅ {col_name}: {urun_adi} - Adet: {siparis_adet} [Depo ✓]")
                                    else:
                                        self.status_label.config(text=f"✅ {col_name}: {urun_adi} [Browser AÇIK]")
                                else:
                                    self.status_label.config(text=f"✅ {col_name}: {urun_adi} [Browser AÇIK]")
                            else:
                                # Browser öne çıkarılamadı - UYARI VER
                                if siparis_adet and siparis_adet > 0:
                                    if depo.set_order_quantity(siparis_adet):
                                        self.status_label.config(text=f"⚠️ {col_name}: {urun_adi} - Adet: {siparis_adet} [Manuel browser kontrolü gerekli]")
                                    else:
                                        self.status_label.config(text=f"⚠️ {col_name}: {urun_adi} [Manuel browser kontrolü gerekli]")
                                else:
                                    self.status_label.config(text=f"⚠️ {col_name}: {urun_adi} [Manuel browser kontrolü gerekli]")
                        else:
                            self.status_label.config(text=f"❌ {col_name} deposunda arama başarısız!")
                    except Exception as e:
                        self.status_label.config(text=f"❌ {col_name} deposu kapalı veya hata: {str(e)[:50]}")
                        logger.error(f"Depo arama hatası: {e}")
                else:
                    self.status_label.config(text=f"⚠️ {col_name} deposu bulunamadı!")

        except Exception as e:
            logger.error(f"Tıklama olayı hatası: {e}")

    def on_status_label_click(self, event):
        """Status label'a tıklandığında - depo ismine tıklanırsa o depoya git"""
        try:
            # Son aranan barkod var mı?
            if not self.last_searched_barcode:
                return

            # Status label'daki metni al
            status_text = self.status_label.cget("text")

            # Depo isimlerini tespit et (kısaltılmış)
            depo_names = ["All", "Sel", "Ysf", "Koop", "BEK", "Fz", "San"]

            # Hangi depo adına tıklandı?
            clicked_depo = None
            for depo_name in depo_names:
                if depo_name in status_text:
                    # Depo adının pozisyonunu bul
                    start_idx = status_text.find(depo_name)
                    if start_idx != -1:
                        # Tıklanan x pozisyonundan depo adını tahmin et
                        # (Basit yaklaşım: depo adının yakınında mı?)
                        # Label font genişliği: ~7 piksel/karakter
                        label_text = self.status_label.cget("text")
                        char_width = 7  # Ortalama karakter genişliği
                        char_position = event.x // char_width

                        # Depo adının başlangıç pozisyonu
                        depo_start = start_idx
                        depo_end = start_idx + len(depo_name)

                        # Tıklama bu depo adı aralığında mı?
                        if depo_start <= char_position <= depo_end + 10:  # +10 tolerans
                            clicked_depo = depo_name
                            break

            if not clicked_depo:
                # Alternatif: Metinden ilk depo adını al
                for depo_name in depo_names:
                    if depo_name in status_text:
                        clicked_depo = depo_name
                        break

            if not clicked_depo:
                return

            # Depo mapping
            depo_map = {
                "All": "alliance",
                "Sel": "selcuk",
                "Ysf": "yusufpasa",
                "Koop": "iskoop",
                "BEK": "bursa",
                "Fz": "farmazon",
                "San": "sancak"
            }
            depo_key = depo_map[clicked_depo]

            # Controller'dan depo al
            if self.controller and depo_key in self.controller.depolar:
                depo = self.controller.depolar[depo_key]

                # Depo açık mı kontrol et
                if not depo.driver:
                    self.status_label.config(text=f"⚠️ {clicked_depo} deposu açık değil!")
                    return

                # Depo tab'ına geç ve ürünü ara
                try:
                    import time
                    depo.switch_to_tab()
                    time.sleep(0.3)
                    if depo.search_barcode(self.last_searched_barcode):
                        self.status_label.config(text=f"🔍 {clicked_depo} deposunda gösteriliyor: {self.last_searched_barcode}")
                        logger.info(f"{clicked_depo} deposuna gidildi: {self.last_searched_barcode}")
                    else:
                        self.status_label.config(text=f"❌ {clicked_depo} deposunda arama başarısız!")
                except Exception as e:
                    self.status_label.config(text=f"❌ Hata: {str(e)[:50]}")
                    logger.error(f"Depo tıklama hatası: {e}")
            else:
                self.status_label.config(text=f"⚠️ {clicked_depo} deposu bulunamadı!")

        except Exception as e:
            logger.error(f"Status label tıklama hatası: {e}")

    def move_window_to_left(self):
        """Ana pencereyi sola kaydır ve en üste getir"""
        try:
            logger.info("⬅ move_window_to_left() çağrıldı - GUI sol tarafa taşınıyor...")

            # Mevcut pencere pozisyonunu al
            geometry = self.root.geometry()
            # Geometry formatı: "WIDTHxHEIGHT+X+Y"
            parts = geometry.split('+')
            if len(parts) < 3:
                logger.warning(f"Geometry formatı geçersiz: {geometry}")
                return

            current_x = int(parts[1])
            current_y = int(parts[2])

            # Pencere boyutlarını al
            window_info = parts[0].split('x')
            window_width = int(window_info[0])
            window_height = int(window_info[1])

            logger.debug(f"Mevcut pozisyon: {current_x}, {current_y} | Boyut: {window_width}x{window_height}")

            # DAIMA sola kaydır (x = 0) - Koşul kaldırıldı
            new_x = 0
            new_y = current_y
            self.root.geometry(f"{window_width}x{window_height}+{new_x}+{new_y}")
            logger.info(f"✓ Ana pencere sola kaydırıldı: {current_x} -> {new_x}")

            # Ana pencereyi en üste getir
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(100, lambda: self.root.attributes('-topmost', False))
            logger.info(f"✓ Ana pencere en üste getirildi")

        except Exception as e:
            logger.error(f"Pencere sola kaydırma hatası: {e}")

    def position_initial(self):
        """GUI penceresini program başlangıcında konumlandır

        Sağ taraf: %50 genişlik, %90 yükseklik (taskbar hariç çalışma alanı)
        """
        try:
            logger.info("GUI penceresi konumlandırılıyor (başlangıç - sağ taraf)...")

            import pyautogui
            import win32api
            import win32con
            screen_width, screen_height = pyautogui.size()
            logger.debug(f"Ekran boyutu: {screen_width}x{screen_height}")

            # Taskbar yüksekliğini hesapla
            taskbar_height = 40
            try:
                work_area = win32api.SystemParametersInfo(win32con.SPI_GETWORKAREA)
                taskbar_height = screen_height - work_area[3]
                logger.debug(f"Taskbar yüksekliği: {taskbar_height}px")
            except:
                logger.debug("Taskbar yüksekliği varsayılan olarak 40px kullanılıyor")

            # Çalışma alanı yüksekliği (taskbar hariç)
            usable_height = screen_height - taskbar_height

            # Hedef boyutlar: %50 genişlik, %100 yükseklik (taskbar hariç) - 40px
            window_width = screen_width // 2
            window_height = usable_height - 40

            # Konum: Sağ taraf (ekranın sağ yarısı)
            x_position = screen_width // 2
            y_position = 0  # Üstten başla

            logger.debug(f"Hedef konum: ({x_position}, {y_position}), Boyut: {window_width}x{window_height}")

            # tkinter geometry kullan
            self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
            self.root.update_idletasks()

            # Windows API ile de konumlandır
            try:
                hwnd = self.root.winfo_id()
                logger.debug(f"GUI hwnd: {hwnd}")

                SWP_NOZORDER = 0x0004
                SWP_SHOWWINDOW = 0x0040
                flags = SWP_NOZORDER | SWP_SHOWWINDOW

                result = win32gui.SetWindowPos(
                    hwnd,
                    0,
                    x_position,
                    y_position,
                    window_width,
                    window_height,
                    flags
                )

                if result:
                    logger.debug(f"SetWindowPos başarılı")
                else:
                    logger.debug(f"SetWindowPos sonucu: {result}")
            except Exception as win_err:
                logger.debug(f"Windows API konumlandırma hatası (önemli değil): {win_err}")

            # En üste getir
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(100, lambda: self.root.attributes('-topmost', False))

            logger.info(f"✓ GUI konumlandırıldı: Sağ taraf ({window_width}x{window_height})")
            return True

        except Exception as e:
            logger.error(f"GUI başlangıç konumlandırma hatası: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def position_for_ordering(self):
        """GUI penceresini sipariş verme için ideal konuma getir

        Sol taraf: %50 genişlik, %90 yükseklik (taskbar hariç çalışma alanı)
        """
        try:
            logger.info("GUI penceresi konumlandırılıyor (sol alt)...")

            # Ekran boyutlarını al - pyautogui kullan (daha güvenilir)
            import pyautogui
            import win32api
            import win32con
            screen_width, screen_height = pyautogui.size()
            logger.debug(f"Ekran boyutu: {screen_width}x{screen_height}")

            # Taskbar yüksekliğini hesapla (genelde ~40px ama sistemden al)
            taskbar_height = 40  # Varsayılan
            try:
                # SPI_GETWORKAREA ile çalışma alanını al (taskbar hariç)
                work_area = win32api.SystemParametersInfo(win32con.SPI_GETWORKAREA)
                taskbar_height = screen_height - work_area[3]  # work_area[3] = bottom
                logger.debug(f"Taskbar yüksekliği: {taskbar_height}px")
            except:
                logger.debug("Taskbar yüksekliği varsayılan olarak 40px kullanılıyor")

            # Çalışma alanı yüksekliği (taskbar hariç)
            usable_height = screen_height - taskbar_height

            # Hedef boyutlar: %50 genişlik, %100 yükseklik (taskbar hariç) - 40px
            window_width = screen_width // 2
            window_height = usable_height - 40

            # Konum: Sol taraf, üstten başla
            x_position = 0
            y_position = 0

            logger.debug(f"Hedef konum: ({x_position}, {y_position}), Boyut: {window_width}x{window_height}")

            # tkinter geometry kullan - daha güvenilir
            self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")

            # Biraz bekle ve tekrar ayarla (bazen ilk seferde tutmuyor)
            self.root.update_idletasks()

            # Windows API ile de konumlandır (çift garanti)
            try:
                hwnd = self.root.winfo_id()
                logger.debug(f"GUI hwnd: {hwnd}")

                SWP_NOZORDER = 0x0004
                SWP_SHOWWINDOW = 0x0040
                flags = SWP_NOZORDER | SWP_SHOWWINDOW

                result = win32gui.SetWindowPos(
                    hwnd,
                    0,
                    x_position,
                    y_position,
                    window_width,
                    window_height,
                    flags
                )

                if result:
                    logger.debug(f"SetWindowPos başarılı")
                else:
                    logger.debug(f"SetWindowPos sonucu: {result}")
            except Exception as win_err:
                logger.debug(f"Windows API konumlandırma hatası (önemli değil): {win_err}")

            # En üste getir
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(100, lambda: self.root.attributes('-topmost', False))

            logger.info(f"✓ GUI konumlandırıldı: Sol alt ({window_width}x{window_height})")
            return True

        except Exception as e:
            logger.error(f"GUI konumlandırma hatası: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def position_botanik_on_startup(self):
        """GUI ilk açıldığında Botanik Sipariş Yardımcısı'nı konumlandır

        Sol üst köşe: %50 genişlik, %50 yükseklik
        """
        try:
            # Controller ve Botanik bağlı mı kontrol et
            if not self.controller or not self.controller.botanik:
                logger.debug("Botanik henüz bağlanmamış, konumlandırma atlanıyor")
                return False

            logger.info("Botanik Sipariş Yardımcısı konumlandırılıyor (program başlangıcı)...")

            # Botanik'in kendi position_for_ordering metodunu çağır
            self.controller.botanik.position_for_ordering()

            return True

        except Exception as e:
            logger.warning(f"Botanik başlangıç konumlandırma hatası: {e}")
            return False

    def add_product_row(self, product_data):
        """Tabloya ürün satırı ekle

        Args:
            product_data: Ürün bilgileri dictionary
        """
        try:
            # NOT: İşlem süresi artık controller tarafından güncelleniyor (bir sonraki ilaca geçiş süresi)

            row = product_data["row"]
            urun_adi = product_data["urun_adi"] or "-"
            stok = product_data["stok"]
            mf = product_data["mf"]
            minstk = product_data["minstk"]

            # En karlı şartı ürün adının başına ekle - SADECE AYAR AÇIKSA
            import os
            mf_enabled = os.getenv("MF_ENABLED", "true").lower() == "true"

            # En karlı sonucu kontrol et
            en_karli_sonuc = product_data.get("en_karli_sonuc")
            en_karli_sart = None
            if en_karli_sonuc and mf_enabled:
                en_karli = en_karli_sonuc.get("en_karli", {})
                sart = en_karli.get("sart", "1")
                if sart and sart != "1":
                    # MF'li şart varsa yıldızlı göster
                    en_karli_sart = f"★({sart})"
                    urun_adi = f"{en_karli_sart} {urun_adi}"

            # En karlı şart yoksa ve MF bilgisi varsa eski sistemi kullan
            if not en_karli_sart and mf_enabled:
                mf_info = product_data.get("mf_info")
                if mf_info and mf_info.get("adet") and mf_info.get("mf"):
                    adet = mf_info.get("adet")
                    mf_val = mf_info.get("mf")
                    urun_adi = f"({adet}+{mf_val}) {urun_adi}"

            # En karlı depo(lar)ı tespit et
            en_karli_depolar = set()
            en_karli_sonuc = product_data.get("en_karli_sonuc")
            if en_karli_sonuc:
                en_karliler = en_karli_sonuc.get("en_karliler", [])
                for s in en_karliler:
                    en_karli_depolar.add(s.get("depo"))

            # Depo kısa isim → key mapping
            depo_col_to_key = {
                "All": "alliance",
                "Sel": "selcuk",
                "Ysf": "yusufpasa",
                "Koop": "iskoop",
                "BEK": "bursa",
                "Fz": "farmazon",
                "San": "sancak"
            }

            # Depo mesajlarını kısalt
            def format_depo_mesaj(mesaj, is_en_karli=False, pahali=False):
                """Depo mesajını kısalt"""
                if not mesaj or mesaj == "-":
                    return "-"
                # Pahalı kontrolü (Farmazon için)
                if pahali or mesaj.lower() == "pahalı":
                    return "Pahalı"  # PAHALI - PSF'den yüksek
                mesaj_lower = mesaj.lower()
                if "stokta var" in mesaj_lower:
                    if is_en_karli:
                        return "★"  # EN KARLI - Yıldız
                    return "🔘"  # VAR - Radio butonu
                elif "depoyu ara" in mesaj_lower:
                    return "📞"  # ARA - Telefon ahizesi
                elif "stokta yok" in mesaj_lower or "belirsiz" in mesaj_lower:
                    return "◯"   # YOK - Büyük boş daire
                else:
                    return mesaj

            # Alliance'dan depocu fiyatı (Türkçe format virgül ile)
            alliance_durum = product_data.get("alliance_durum", {})
            depocu_fiyat = alliance_durum.get("fiyat")
            if depocu_fiyat is not None:
                depocu_str = f"{depocu_fiyat:.2f}".replace(".", ",")
            else:
                depocu_str = "-"

            # Sipariş adedi
            siparis_adet = product_data.get("siparis_adet", "-")

            # Base sütun değerleri
            base_values = [row, urun_adi, depocu_str, stok, mf, minstk]

            # Depo sütun mapping (sadece kullanılabilir depoların mesajları)
            depo_data_map = {
                "All": product_data.get("alliance_durum", {}),
                "Sel": product_data.get("selcuk_durum", {}),
                "Ysf": product_data.get("yusufpasa_durum", {}),
                "Koop": product_data.get("iskoop_durum", {}),
                "BEK": product_data.get("bursa_durum", {}),
                "Fz": product_data.get("farmazon_durum", {}),
                "San": product_data.get("sancak_durum", {})
            }

            # Sadece kullanılabilir depoların mesajlarını ekle
            depo_values = []
            for depo_col in self.depo_columns:
                depo_durum = depo_data_map.get(depo_col, {})
                depo_key = depo_col_to_key.get(depo_col)
                is_en_karli = depo_key in en_karli_depolar
                # Farmazon için pahalılık kontrolü
                pahali = depo_durum.get("pahali", False) if depo_key == "farmazon" else False
                depo_mesaj = format_depo_mesaj(depo_durum.get("mesaj", "-"), is_en_karli, pahali)
                depo_values.append(depo_mesaj)

            # Final değerler
            values = base_values + depo_values + [siparis_adet]

            # Zebra deseni için satır numarasına göre tag
            row_count = len(self.tree.get_children())
            row_tag = "evenrow" if row_count % 2 == 0 else "oddrow"

            # Satırı ekle
            item_id = self.tree.insert("", tk.END, values=values, tags=(row_tag,))

            # Kaydet
            self.products.append({"item_id": item_id, "data": product_data})

            # Her yeni satır eklendiğinde, o satıra otomatik kaydır (kullanıcı görebilsin)
            self.tree.see(item_id)

            # İlk satır ise tablonun en üstüne kaydır
            if len(self.products) == 1:
                self.tree.yview_moveto(0)

            # YENİ: En son eklenen satırı seçili hale getir ve alt panelleri güncelle
            self.tree.selection_set(item_id)
            self.selected_product = {"item_id": item_id, "data": product_data}
            self.update_monthly_table_from_product(product_data)

        except Exception as e:
            logger.error(f"Satır eklenirken hata: {e}")

    def update_status(self, message):
        """Durum mesajını güncelle"""
        self.root.after(0, lambda: self.status_label.config(text=message))

    def show_scanned_product(self, product_data, idx, total):
        """Taranan ürün bilgisini tabloya ekle ve göster"""
        try:
            # Verileri al
            row_num = product_data.get('row', idx)
            urun_adi = product_data.get('urun_adi', '-')
            stok = product_data.get('stok', 0)
            mf = product_data.get('mf', 0)
            minstk = product_data.get('minstk', 0)
            ort = product_data.get('ort', 0)
            siparis = product_data.get('siparis_adet', 0)

            # Ana tablo değerleri: Satır, Ürün Adı, Depocu, Stok, MF, MinStk, [Depolar...], Sipariş
            base_values = [
                row_num,
                urun_adi[:40] if urun_adi else "-",
                "",  # Depocu - henüz bilinmiyor
                stok,
                mf,
                minstk
            ]

            # Depo sütunları - henüz taranmadı
            depo_values = ["-"] * len(self.depo_columns)

            # Final değerler
            values = base_values + depo_values + [siparis]

            # Zebra deseni
            row_count = len(self.tree.get_children())
            row_tag = "evenrow" if row_count % 2 == 0 else "oddrow"

            # Tabloya ekle
            item_id = self.tree.insert("", tk.END, values=values, tags=(row_tag,))

            # products listesine ekle
            self.products.append({"item_id": item_id, "data": product_data})

            # Yeni satıra kaydır
            self.tree.see(item_id)

            # Seç ve alt paneli güncelle
            self.tree.selection_set(item_id)
            self.selected_product = {"item_id": item_id, "data": product_data}

            # Aylık tabloyu güncelle (tüm verilerle)
            monthly_sales = product_data.get("monthly_sales", {})
            logger.info(f"[GUI] show_scanned_product: monthly_sales keys = {list(monthly_sales.keys())[:5] if monthly_sales else 'BOŞ'}")
            logger.info(f"[GUI] show_scanned_product: Ort = {monthly_sales.get('Ort', 'YOK')}, Top = {monthly_sales.get('Top', 'YOK')}")
            self.update_monthly_table_from_product(product_data)

            # Status güncelle
            status_text = f"[{idx}/{total}] {urun_adi[:25] if urun_adi else '-'} | Stk:{stok} Ort:{ort:.1f} Sip:{siparis}"
            self.status_label.config(text=status_text)

        except Exception as e:
            logger.error(f"show_scanned_product hatası: {e}")

    def show_scanned_product_with_depo(self, product_data, idx, total):
        """Taranan ürün bilgisini DEPO SONUÇLARIYLA BİRLİKTE tabloya ekle"""
        try:
            # Verileri al
            row_num = product_data.get('row', idx)
            urun_adi = product_data.get('urun_adi', '-')
            stok = product_data.get('stok', 0)
            mf = product_data.get('mf', 0)
            minstk = product_data.get('minstk', 0)
            ort = product_data.get('ort', 0)
            siparis = product_data.get('siparis_adet', 0)

            # En karlı depoyu bul
            en_karli = product_data.get("en_karli_sonuc", {})
            depocu = en_karli.get("depo_adi", "") if en_karli else ""

            # Depo sütun mapping
            depo_col_to_key = {
                "All": "alliance", "Sel": "selcuk", "Ysf": "yusufpasa",
                "Koop": "iskoop", "BEK": "bursa", "Fz": "farmazon", "San": "sancak"
            }

            # Helper: Depo mesajını formatla (normal taramadaki simgelerle)
            def format_depo_mesaj(mesaj, is_en_karli=False):
                if not mesaj or mesaj == "-":
                    return "-"
                mesaj_lower = mesaj.lower()
                if "stokta var" in mesaj_lower or mesaj == "VAR":
                    if is_en_karli:
                        return "★"  # EN KARLI - Yıldız
                    return "🔘"  # VAR - Radio butonu
                elif "depoyu ara" in mesaj_lower:
                    return "📞"  # ARA - Telefon ahizesi
                elif "stokta yok" in mesaj_lower or mesaj == "YOK" or "belirsiz" in mesaj_lower:
                    return "◯"   # YOK - Büyük boş daire
                else:
                    # Bilinmeyen mesaj - olduğu gibi göster
                    if is_en_karli:
                        return f"★ {mesaj}"
                    return mesaj

            # En karlı depoları belirle
            en_karli_depolar = []
            if en_karli:
                en_karli_depolar = [en_karli.get("depo_key")]

            # Depo değerlerini oluştur
            depo_values = []
            for depo_col in self.depo_columns:
                depo_key = depo_col_to_key.get(depo_col)
                depo_durum = product_data.get(f"{depo_key}_durum", {})
                is_en_karli = depo_key in en_karli_depolar
                mesaj = depo_durum.get("mesaj", "-") if depo_durum else "-"
                depo_values.append(format_depo_mesaj(mesaj, is_en_karli))

            # Ana tablo değerleri
            base_values = [
                row_num,
                urun_adi[:40] if urun_adi else "-",
                depocu[:10] if depocu else "",
                stok,
                mf,
                minstk
            ]

            # Final değerler
            values = base_values + depo_values + [siparis]

            # Zebra deseni
            row_count = len(self.tree.get_children())
            row_tag = "evenrow" if row_count % 2 == 0 else "oddrow"

            # Tabloya ekle
            item_id = self.tree.insert("", tk.END, values=values, tags=(row_tag,))

            # products listesine ekle
            self.products.append({"item_id": item_id, "data": product_data})

            # Yeni satıra kaydır
            self.tree.see(item_id)

            # Seç ve alt panelleri güncelle
            self.tree.selection_set(item_id)
            self.selected_product = {"item_id": item_id, "data": product_data}

            # Aylık tabloyu güncelle
            self.update_monthly_table_from_product(product_data)

            # Şartlar tablosunu güncelle
            self.update_sartlar_table({"item_id": item_id, "data": product_data})

            # Status güncelle
            depo_info = f" [{depocu}]" if depocu else ""
            status_text = f"[{idx}/{total}] {urun_adi[:20] if urun_adi else '-'}{depo_info} | Stk:{stok} Ort:{ort:.1f} Sip:{siparis}"
            self.status_label.config(text=status_text)

        except Exception as e:
            logger.error(f"show_scanned_product_with_depo hatası: {e}")

    def _update_monthly_with_ort(self, product_data):
        """Hızlı tarama için aylık tabloyu Ort değeri ile güncelle"""
        try:
            # Mevcut satırları temizle
            for item in self.monthly_tree.get_children():
                self.monthly_tree.delete(item)

            ort = product_data.get('ort', 0)
            stok = product_data.get('stok', 0)
            siparis = product_data.get('siparis_adet', 0)

            # Sütun sayısı kadar boş değer + Top ve Ort
            col_count = len(self.monthly_tree["columns"])
            values = ["-"] * (col_count - 2) + ["-", f"{ort:.1f}"]

            self.monthly_tree.insert("", tk.END, values=values)

            # Info panelini güncelle
            if hasattr(self, 'info_stok_label'):
                self.info_stok_label.config(text=str(stok))
            if hasattr(self, 'info_siparis_label'):
                self.info_siparis_label.config(text=str(siparis) if siparis else "-")

            # Kaç günde bitecek
            if hasattr(self, 'info_gun_label'):
                if ort > 0 and stok > 0:
                    gun = int(stok * 30 / ort)
                    self.info_gun_label.config(text=f"{gun} gün")
                else:
                    self.info_gun_label.config(text="-")

        except Exception as e:
            logger.debug(f"_update_monthly_with_ort hatası: {e}")

    def on_tree_double_click(self, event):
        """Sipariş Adet hücresi düzenleme"""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)

        if not item or not column:
            return

        # Dinamik sütun listesi (tıklama olayıyla aynı mantık)
        col_num = int(column[1:]) - 1
        base_columns = ["Satır", "Ürün Adı", "Depocu", "Stok", "MF", "MinStk"]
        all_columns = base_columns + self.depo_columns + ["Sipariş Adet"]
        col_name = all_columns[col_num] if col_num < len(all_columns) else None

        if col_name != "Sipariş Adet":
            return

        self.start_quantity_edit(item, column)

    def load_depo_contact_info(self):
        """Depo iletişim bilgilerini .env'den yükle"""
        import os
        self.depo_contacts = {
            "All": {
                "name": "Alliance Healthcare",
                "yetkili": os.getenv("ALLIANCE_YETKILI", ""),
                "cep": os.getenv("ALLIANCE_CEP", ""),
                "sabit": os.getenv("ALLIANCE_SABIT", ""),
                "iade": os.getenv("ALLIANCE_IADE", "")
            },
            "Sel": {
                "name": "Selçuk Ecza",
                "yetkili": os.getenv("SELCUK_YETKILI", ""),
                "cep": os.getenv("SELCUK_CEP", ""),
                "sabit": os.getenv("SELCUK_SABIT", ""),
                "iade": os.getenv("SELCUK_IADE", "")
            },
            "Ysf": {
                "name": "Yusuf Paşa",
                "yetkili": os.getenv("YUSUFPASA_YETKILI", ""),
                "cep": os.getenv("YUSUFPASA_CEP", ""),
                "sabit": os.getenv("YUSUFPASA_SABIT", ""),
                "iade": os.getenv("YUSUFPASA_IADE", "")
            },
            "Koop": {
                "name": "İstanbul Ecza Koop",
                "yetkili": os.getenv("ISKOOP_YETKILI", ""),
                "cep": os.getenv("ISKOOP_CEP", ""),
                "sabit": os.getenv("ISKOOP_SABIT", ""),
                "iade": os.getenv("ISKOOP_IADE", "")
            },
            "BEK": {
                "name": "Bursa Ecza Koop",
                "yetkili": os.getenv("BURSA_YETKILI", ""),
                "cep": os.getenv("BURSA_CEP", ""),
                "sabit": os.getenv("BURSA_SABIT", ""),
                "iade": os.getenv("BURSA_IADE", "")
            },
            "Fz": {
                "name": "Farmazon",
                "yetkili": os.getenv("FARMAZON_YETKILI", ""),
                "cep": os.getenv("FARMAZON_CEP", ""),
                "sabit": os.getenv("FARMAZON_SABIT", ""),
                "iade": os.getenv("FARMAZON_IADE", "")
            },
            "San": {
                "name": "Sancak Ecza",
                "yetkili": os.getenv("SANCAK_YETKILI", ""),
                "cep": os.getenv("SANCAK_CEP", ""),
                "sabit": os.getenv("SANCAK_SABIT", ""),
                "iade": os.getenv("SANCAK_IADE", "")
            }
        }

    def on_tree_motion(self, event):
        """Fare hareketi - depo hücresi üzerinde bekleyince tooltip göster"""
        # Önceki zamanlayıcıyı iptal et
        if self.depo_tooltip_after_id:
            self.root.after_cancel(self.depo_tooltip_after_id)
            self.depo_tooltip_after_id = None

        # Mevcut tooltip'i gizle
        self.hide_depo_tooltip()

        # Hangi hücre üzerinde olduğumuzu bul
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item or not column:
            return

        col_num = int(column[1:]) - 1
        base_columns = ["Satır", "Ürün Adı", "Depocu", "Stok", "MF", "MinStk"]
        all_columns = base_columns + self.depo_columns + ["Sipariş Adet"]
        col_name = all_columns[col_num] if col_num < len(all_columns) else None

        # Sadece depo sütunlarında tooltip göster
        if col_name in self.depo_columns:
            # 500ms sonra tooltip göster
            self.depo_tooltip_after_id = self.root.after(
                500, lambda: self.show_depo_tooltip(event, col_name)
            )

    def on_tree_leave(self, event):
        """Fare tablodan çıkınca tooltip gizle"""
        if self.depo_tooltip_after_id:
            self.root.after_cancel(self.depo_tooltip_after_id)
            self.depo_tooltip_after_id = None
        self.hide_depo_tooltip()

    def show_depo_tooltip(self, event, depo_col):
        """Depo iletişim bilgilerini tooltip olarak göster"""
        contact = self.depo_contacts.get(depo_col, {})
        if not contact:
            return

        # Tooltip içeriği oluştur
        lines = [f"📦 {contact.get('name', depo_col)}"]
        if contact.get('yetkili'):
            lines.append(f"👤 {contact['yetkili']}")
        if contact.get('cep'):
            lines.append(f"📱 {contact['cep']}")
        if contact.get('sabit'):
            lines.append(f"☎️ {contact['sabit']}")
        if contact.get('iade'):
            lines.append(f"↩️ İade: {contact['iade']}")

        # Sadece depo adı varsa tooltip gösterme
        if len(lines) <= 1:
            return

        text = "\n".join(lines)

        # Tooltip penceresi oluştur
        self.depo_tooltip = tk.Toplevel(self.root)
        self.depo_tooltip.wm_overrideredirect(True)
        self.depo_tooltip.wm_attributes("-topmost", True)

        # Fare konumuna göre pozisyon
        x = event.x_root + 15
        y = event.y_root + 10
        self.depo_tooltip.wm_geometry(f"+{x}+{y}")

        # Tooltip içeriği
        frame = tk.Frame(self.depo_tooltip, bg="#2c3e50", bd=1, relief=tk.SOLID)
        frame.pack(fill=tk.BOTH, expand=True)

        label = tk.Label(
            frame,
            text=text,
            font=("Segoe UI", 9),
            bg="#2c3e50",
            fg="#ecf0f1",
            justify=tk.LEFT,
            padx=8,
            pady=5
        )
        label.pack()

    def hide_depo_tooltip(self):
        """Depo tooltip'ini gizle"""
        if self.depo_tooltip:
            self.depo_tooltip.destroy()
            self.depo_tooltip = None

    def clear_product_list(self):
        """Listeyi temizle"""
        # Tabloyu temizle
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.products = []
        self.all_products_backup = []
        self.selected_product = None

        # Aylık tabloyu temizle
        for item in self.monthly_tree.get_children():
            self.monthly_tree.delete(item)
        self.monthly_tree.insert("", tk.END, values=["-"] * 15)

        # Info panelini sıfırla
        if hasattr(self, 'info_stok_label'):
            self.info_stok_label.config(text="-")
        if hasattr(self, 'info_siparis_label'):
            self.info_siparis_label.config(text="-")
        if hasattr(self, 'info_gun_label'):
            self.info_gun_label.config(text="-")

        # Filtreyi sıfırla
        self.filter_var.set("all")
        for key, btn in self.filter_buttons.items():
            if key == "all":
                btn.config(fg="#3498db", font=("Segoe UI", 9, "bold"))
            else:
                btn.config(fg="#7f8c8d", font=("Segoe UI", 9))

        # Sayacı sıfırla
        self.filter_count_label.config(text="")

        # Status güncelle
        self.status_label.config(text="🗑 Liste temizlendi")

    def apply_filter(self, filter_type):
        """Listeyi VAR/ARA/YOK durumuna göre filtrele"""
        self.filter_var.set(filter_type)

        # Buton renklerini güncelle
        for key, btn in self.filter_buttons.items():
            if key == filter_type:
                btn.config(fg="#3498db", font=("Segoe UI", 9, "bold"))
            else:
                btn.config(fg="#7f8c8d", font=("Segoe UI", 9))

        # Eğer ilk kez filtreleme yapılıyorsa, mevcut ürünleri yedekle
        if not self.all_products_backup and self.products:
            self.all_products_backup = self.products.copy()

        # Kullanılacak kaynak
        source = self.all_products_backup if self.all_products_backup else self.products

        # Tabloyu temizle
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.products = []

        # Filtreye göre ürünleri ekle
        filtered_count = 0
        total_count = len(source)

        for product_info in source:
            product_data = product_info["data"]

            # Depo durumlarını kontrol et
            has_var = False
            has_ara = False
            has_yok = False
            has_any_data = False

            for depo_key in ["alliance", "selcuk", "yusufpasa", "iskoop", "bursa", "farmazon", "sancak"]:
                depo_durum = product_data.get(f"{depo_key}_durum", {})
                if depo_durum:
                    mesaj = depo_durum.get("mesaj", "").lower()
                    if mesaj and mesaj != "-":
                        has_any_data = True
                        if "stokta var" in mesaj:
                            has_var = True
                        elif "depoyu ara" in mesaj:
                            has_ara = True
                        elif "stokta yok" in mesaj or "belirsiz" in mesaj:
                            has_yok = True

            # Filtre kontrolü
            show = False
            if filter_type == "all":
                show = True
            elif filter_type == "var" and has_var:
                show = True
            elif filter_type == "ara" and has_ara:
                show = True
            elif filter_type == "yok":
                # Sadece YOK olanlar (hiç VAR ve ARA yok) veya hiç veri yoksa
                if has_yok and not has_var and not has_ara:
                    show = True
                elif not has_any_data:
                    show = True  # Tarama yarım kalmışsa YOK olarak say

            if show:
                filtered_count += 1
                self.add_product_row(product_data)

        # Sayacı güncelle
        if filter_type == "all":
            self.filter_count_label.config(text=f"{total_count} ürün")
        else:
            self.filter_count_label.config(text=f"{filtered_count}/{total_count}")

    def start_quantity_edit(self, item, column):
        """Treeview hücresinde Entry oluştur"""
        bbox = self.tree.bbox(item, column)
        if not bbox:
            return

        x, y, width, height = bbox
        current_value = self.tree.set(item, "Sipariş Adet")

        if self.quantity_edit["entry"]:
            self.cancel_quantity_edit()

        entry = tk.Entry(self.tree, font=("Arial", 10))
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, current_value)
        entry.focus()
        entry.select_range(0, tk.END)

        entry.bind("<Return>", lambda e, ent=entry: self.save_quantity_edit(item, ent.get(), ent))
        entry.bind("<Escape>", lambda e: self.cancel_quantity_edit())
        entry.bind("<FocusOut>", lambda e, ent=entry: self.save_quantity_edit(item, ent.get(), ent))

        self.quantity_edit["entry"] = entry
        self.quantity_edit["item"] = item

    def save_quantity_edit(self, item, value, entry=None):
        """Yeni sipariş adetini kaydet"""
        if entry is None:
            entry = self.quantity_edit.get("entry")
        if not entry:
            return

        try:
            new_value = int(value)
            if new_value < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Uyarı", "Sipariş adedi sayı olmalı!")
            return

        self.tree.set(item, "Sipariş Adet", new_value)
        product = self.get_product_by_item(item)
        if product:
            product["siparis_adet"] = new_value
            # data içinde de güncelle
            if "data" in product:
                product["data"]["siparis_adet"] = new_value

        # Eğer düzenlenen satır seçili satırsa, alt paneli de güncelle
        if self.selected_product and self.selected_product.get("item_id") == item:
            self.info_siparis_label.config(text=str(new_value) if new_value else "-")
            self.update_days_calculation()

        self.status_label.config(text=f"✏️ Sipariş adedi güncellendi: {new_value}")
        self.cancel_quantity_edit()

    def cancel_quantity_edit(self):
        """Düzenleme girişini kapat"""
        entry = self.quantity_edit.get("entry")
        if entry:
            entry.destroy()
        self.quantity_edit = {"entry": None, "item": None}

    def get_product_by_item(self, item_id):
        """Tree item id'sinden ürün bilgisine eriş"""
        for info in self.products:
            if info.get("item_id") == item_id:
                return info.get("data")
        return None

    def adjust_tree_columns(self):
        """Pencere genişliğine göre sütunları ölçeklendir"""
        try:
            if not hasattr(self, "tree") or not hasattr(self, "column_weights"):
                return

            tree_width = self.tree.winfo_width()
            if tree_width <= 0:
                tree_width = self.root.winfo_width() - 40
            if tree_width <= 0:
                return

            total_weight = sum(self.column_weights.values())
            for column, weight in self.column_weights.items():
                min_width = self.column_min_widths.get(column, 60)
                calculated = int(tree_width * (weight / total_weight))
                new_width = max(min_width, calculated)
                self.tree.column(column, width=new_width)
        except Exception as e:
            logger.debug(f"Sütun boyutları ayarlanamadı: {e}")

    def place_orders(self):
        """Seçili ürünler için sipariş ver (seçili yoksa tümünü sipariş eder)"""
        try:
            # Tablodan seçili ürünleri al
            selected_items = self.tree.selection()

            # Eğer hiçbir şey seçili değilse, TÜM ürünleri al
            if not selected_items:
                selected_items = self.tree.get_children()
                logger.info("Hiçbir ürün seçili değil, TÜM ürünler sipariş edilecek")
            else:
                logger.info(f"{len(selected_items)} seçili ürün sipariş edilecek")

            # Seçili ürünlerin bilgilerini topla
            selected_products = []
            for item in selected_items:
                values = self.tree.item(item, "values")
                row_num = int(values[0])

                # Controller'dan ürünü bul
                product = None
                for p in self.products:
                    # self.products formatı: {"item_id": ..., "data": product_data}
                    product_data = p.get("data", p)  # Hem eski hem yeni format için
                    if product_data.get("row") == row_num:
                        product = product_data
                        break

                if not product:
                    continue

                # En az bir depoda stok varsa
                if (product.get("alliance_durum", {}).get("stok_var") or
                    product.get("selcuk_durum", {}).get("stok_var") or
                    product.get("yusufpasa_durum", {}).get("stok_var") or
                    product.get("iskoop_durum", {}).get("stok_var") or
                    product.get("bursa_durum", {}).get("stok_var") or
                    product.get("sancak_durum", {}).get("stok_var")):

                    siparis_adet = product.get("siparis_adet")
                    if siparis_adet and siparis_adet > 0:
                        selected_products.append(product)
                        logger.debug(f"Sipariş: Ürün eklendi - {product.get('urun_adi', 'Bilinmeyen')}, Adet: {siparis_adet}")

            if not selected_products:
                messagebox.showwarning("Uyarı", "Seçili ürünlerden sipariş verilebilecek ürün yok!\n\n"
                                               "Sipariş vermek için:\n"
                                               "• Sipariş Adet > 0 olmalı\n"
                                               "• En az bir depoda stokta olmalı")
                return

            # Onay al
            msg = f"{len(selected_products)} ürün için sipariş verilecek. Onaylıyor musunuz?"
            if not messagebox.askyesno("Sipariş Onayı", msg):
                return

            # Sipariş ver
            self.status_label.config(text="Sipariş veriliyor...")

            thread = threading.Thread(target=self._place_orders_thread, args=(selected_products,), daemon=True)
            thread.start()

        except Exception as e:
            logger.error(f"Sipariş verme hatası: {e}")
            messagebox.showerror("Hata", f"Sipariş verilirken hata: {e}")

    def _place_orders_thread(self, products):
        """Sipariş verme işlemini arka planda çalıştır"""
        try:
            self.controller.place_orders(products)
            self.root.after(0, lambda: messagebox.showinfo("Başarılı", "Siparişler başarıyla verildi!"))
        except Exception as e:
            logger.error(f"Sipariş hatası: {e}")
            self.root.after(0, lambda: messagebox.showerror("Hata", f"Sipariş hatası: {e}"))
        finally:
            self.root.after(0, lambda: self.status_label.config(text="Hazır"))

    def load_ilac_listesi(self):
        """CSV'den ilaç listesini yükle"""
        try:
            import csv
            from pathlib import Path
            csv_path = Path(__file__).resolve().parent.parent / "Tüm İlaç Listesi.csv"
            if csv_path.exists():
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        ilac_adi = row.get('İlaç Adı', '').strip()
                        barkod = row.get('Barkod', '').strip()
                        if ilac_adi and barkod:
                            self.ilac_listesi[ilac_adi] = barkod
                logger.info(f"İlaç listesi yüklendi: {len(self.ilac_listesi)} ilaç")
        except Exception as e:
            logger.warning(f"İlaç listesi yüklenemedi: {e}")

    def on_barcode_keyrelease(self, event):
        """İlaç alanına yazarken autocomplete göster"""
        # Özel tuşları ignore et
        if event.keysym in ['Return', 'Escape', 'Up', 'Down', 'Left', 'Right', 'Tab']:
            return

        value = self.barcode_entry.get().strip()

        # Boşsa autocomplete gösterme
        if not value:
            self.hide_autocomplete()
            return

        # Sayısal ise (tam barkod) autocomplete gösterme
        if value.isdigit() and len(value) >= 10:
            self.hide_autocomplete()
            return

        # İlaç ismi arıyoruz - en az 2 karakter gerekli
        if len(value) < 2:
            self.hide_autocomplete()
            return

        # Eşleşen ilaçları bul (akıllı arama: boşluklarla ayrılmış kelimeler)
        matches = []
        search_words = value.lower().split()  # "APRA 20" → ["apra", "20"]

        for ilac_adi in self.ilac_listesi.keys():
            ilac_lower = ilac_adi.lower()
            # Tüm kelimelerin ilaç adında olup olmadığını kontrol et
            if all(word in ilac_lower for word in search_words):
                matches.append(ilac_adi)
                if len(matches) >= 15:  # Maksimum 15 öneri
                    break

        if matches:
            self.current_listbox_index = -1  # Reset index
            self.show_autocomplete(matches)
        else:
            self.hide_autocomplete()

    def show_autocomplete(self, matches):
        """Autocomplete listesini göster"""
        # Mevcut pencere varsa güncelle
        if not self.autocomplete_window:
            # Yeni pencere oluştur
            self.autocomplete_window = tk.Toplevel(self.root)
            self.autocomplete_window.wm_overrideredirect(True)  # Başlık çubuğu yok

            # Listbox oluştur
            self.autocomplete_listbox = tk.Listbox(
                self.autocomplete_window,
                font=("Arial", 11),
                height=min(len(matches), 15),
                exportselection=False,
                activestyle='dotbox'
            )
            self.autocomplete_listbox.pack(fill=tk.BOTH, expand=True)

            # Tıklanınca veya Enter'a basınca seç
            self.autocomplete_listbox.bind("<<ListboxSelect>>", lambda e: None)  # Sadece hover için
            self.autocomplete_listbox.bind("<Return>", self.on_autocomplete_select)
            self.autocomplete_listbox.bind("<ButtonRelease-1>", self.on_autocomplete_click)

            # Ok tuşları ile listede gezinme
            self.autocomplete_listbox.bind("<Up>", self.on_listbox_navigate)
            self.autocomplete_listbox.bind("<Down>", self.on_listbox_navigate)

            # Entry'den ok tuşlarıyla listeye geçiş
            self.barcode_entry.bind("<Down>", lambda e: self.move_to_autocomplete_list())

        # Listeyi güncelle
        self.autocomplete_listbox.delete(0, tk.END)
        for match in matches:
            self.autocomplete_listbox.insert(tk.END, match)

        # Konumlandır (entry'nin altına)
        x = self.barcode_entry.winfo_rootx()
        y = self.barcode_entry.winfo_rooty() + self.barcode_entry.winfo_height()
        width = self.barcode_entry.winfo_width()  # Entry genişliğinde
        height = min(len(matches) * 25 + 10, 400)  # Dinamik yükseklik, max 400px
        self.autocomplete_window.geometry(f"{width}x{height}+{x}+{y}")

    def on_entry_return(self, event):
        """Entry'de Enter tuşu - liste varsa ilk öğeyi seç, yoksa ara"""
        if self.autocomplete_listbox and self.autocomplete_listbox.size() > 0:
            # Liste varsa ilk öğeyi seç
            self.autocomplete_listbox.selection_clear(0, tk.END)
            self.autocomplete_listbox.selection_set(0)
            self.on_autocomplete_select(event)
        else:
            # Liste yoksa ara
            self.quick_search_barcode()

    def on_entry_down(self, event):
        """Entry'de Down tuşu - listede aşağı git"""
        if self.autocomplete_listbox and self.autocomplete_listbox.size() > 0:
            if not hasattr(self, 'current_listbox_index'):
                self.current_listbox_index = -1

            self.current_listbox_index = min(self.current_listbox_index + 1, self.autocomplete_listbox.size() - 1)
            self.highlight_listbox_item(self.current_listbox_index)
            return "break"

    def on_entry_up(self, event):
        """Entry'de Up tuşu - listede yukarı git"""
        if self.autocomplete_listbox and self.autocomplete_listbox.size() > 0:
            if not hasattr(self, 'current_listbox_index'):
                self.current_listbox_index = 0

            self.current_listbox_index = max(self.current_listbox_index - 1, 0)
            self.highlight_listbox_item(self.current_listbox_index)
            return "break"

    def highlight_listbox_item(self, index):
        """Listbox'ta bir öğeyi highlight et"""
        if self.autocomplete_listbox:
            self.autocomplete_listbox.selection_clear(0, tk.END)
            self.autocomplete_listbox.selection_set(index)
            self.autocomplete_listbox.activate(index)
            self.autocomplete_listbox.see(index)
            # Focus'u entry'de tut
            self.barcode_entry.focus_set()

    def on_listbox_navigate(self, event):
        """Listbox'ta ok tuşları ile gezinme"""
        if not self.autocomplete_listbox:
            return "break"

        current = self.autocomplete_listbox.curselection()
        if not current:
            new_index = 0
        else:
            current_index = current[0]
            size = self.autocomplete_listbox.size()

            if event.keysym == 'Down':
                new_index = min(current_index + 1, size - 1)
            elif event.keysym == 'Up':
                new_index = max(current_index - 1, 0)
            else:
                return "break"

        # Seçimi güncelle
        self.autocomplete_listbox.selection_clear(0, tk.END)
        self.autocomplete_listbox.selection_set(new_index)
        self.autocomplete_listbox.selection_anchor(new_index)  # Anchor'u da güncelle
        self.autocomplete_listbox.activate(new_index)
        self.autocomplete_listbox.see(new_index)

        return "break"  # Varsayılan davranışı engelle

    def hide_autocomplete(self):
        """Autocomplete listesini gizle"""
        if self.autocomplete_window:
            self.autocomplete_window.destroy()
            self.autocomplete_window = None
            self.autocomplete_listbox = None

    def on_autocomplete_click(self, event):
        """Mouse ile tıklandığında"""
        if self.autocomplete_listbox:
            # Mouse tıklamasından sonra seçimi al
            self.root.after(50, lambda: self.on_autocomplete_select(event))

    def on_autocomplete_select(self, event):
        """Autocomplete'ten bir ilaç seçildiğinde (Enter veya mouse)"""
        if self.autocomplete_listbox:
            selection = self.autocomplete_listbox.curselection()
            if selection:
                ilac_adi = self.autocomplete_listbox.get(selection[0])
                barkod = self.ilac_listesi.get(ilac_adi)
                if barkod:
                    logger.info(f"✓ Listeden seçildi: '{ilac_adi}' → Barkod: {barkod}")

                    # Autocomplete'i kapat
                    self.hide_autocomplete()

                    # Entry'yi güncelle
                    self.barcode_entry.focus_set()  # Focus'u entry'ye ver
                    self.barcode_entry.delete(0, tk.END)
                    self.barcode_entry.update()  # Force update
                    self.barcode_entry.insert(0, ilac_adi)
                    self.barcode_entry.update()  # Force update
                    self.barcode_entry.icursor(tk.END)

                    # Barkodu sakla ve ara
                    self.selected_ilac_barkod = barkod
                    logger.info(f"  Entry güncellendi: '{self.barcode_entry.get()}'")
                    logger.info(f"  Barkod saklandı: {self.selected_ilac_barkod}")

                    # Arama yap
                    self.root.after(200, self.quick_search_barcode)

    def quick_search_barcode(self):
        """İlaç adı veya barkod ile hızlı arama yap (tüm depolarda)"""
        # Autocomplete penceresini kapat
        self.hide_autocomplete()

        try:
            import time
            import os
            from pathlib import Path
            from dotenv import load_dotenv

            entry_value = self.barcode_entry.get().strip()

            if not entry_value:
                self.status_label.config(text="⚠️ İlaç adı veya barkod girin!")
                return

            # Eğer autocomplete'ten seçildiyse barkod kullan
            if hasattr(self, 'selected_ilac_barkod') and self.selected_ilac_barkod:
                barcode = self.selected_ilac_barkod
                logger.info(f"✅ BARKOD İLE ARAMA: Autocomplete'ten → '{entry_value}' → Barkod: {barcode}")
                self.selected_ilac_barkod = None  # Resetle
            # Entry'de ilaç adı varsa barkoda çevir (tam eşleşme)
            elif entry_value in self.ilac_listesi:
                barcode = self.ilac_listesi[entry_value]
                logger.info(f"✅ BARKOD İLE ARAMA: İlaç adından → '{entry_value}' → Barkod: {barcode}")
            # Sayısal ise direkt barkod
            elif entry_value.isdigit():
                barcode = entry_value
                logger.info(f"✅ BARKOD İLE ARAMA: Direkt barkod → {barcode}")
            # Eşleşme yok, hata
            else:
                logger.warning(f"❌ İlaç bulunamadı ve sayısal değil: {entry_value}")
                self.status_label.config(text=f"⚠️ İlaç bulunamadı: {entry_value}")
                return

            if not barcode:
                self.status_label.config(text="⚠️ Barkod bulunamadı!")
                return

            # Controller kontrolü
            if not self.controller or not hasattr(self.controller, 'depolar'):
                messagebox.showwarning("Uyarı", "Sistem başlatılamadı!")
                return

            # Kullanılabilir depo var mı?
            if not self.available_depolar:
                messagebox.showwarning(
                    "Uyarı",
                    "Kullanılabilir depo yok!\n\n"
                    "Lütfen Ayarlar'dan:\n"
                    "1. En az bir deponun checkbox'ını işaretleyin\n"
                    "2. O depo için kullanıcı bilgilerini girin"
                )
                return

            # Depolar açık mı kontrol et (sadece kullanılabilir depolar)
            depolar_kapali = all(not depo.driver for depo in self.available_depolar.values())

            if depolar_kapali:
                # Kullanıcıya sor
                cevap = messagebox.askyesno(
                    "Depolar Kapalı",
                    "Depo pencereleri kapalı. Şimdi açılsın mı?\n\n"
                    "(Bu işlem 10-15 saniye sürebilir)\n\n"
                    "NOT: Depolar açılırken pencere yanıt vermeyebilir."
                )

                if not cevap:
                    return

                # Depoları aç
                self.status_label.config(text="⏳ Depolar açılıyor...")
                self.root.update()  # GUI'yi güncelle
                logger.info("Hızlı arama için depolar açılıyor...")

                # .env dosyasını yükle
                env_path = Path(__file__).resolve().parent.parent.parent / ".env"
                if env_path.exists():
                    load_dotenv(env_path)

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

                # Depoları başlat (sadece kullanılabilir depoları)
                from ..utils import HEADLESS

                # Tarayıcı modunu al (tabs = tek pencere sekmeler, windows = ayrı pencereler)
                browser_mode = os.getenv("BROWSER_MODE", "tabs")
                logger.info(f"Tarayıcı modu: {browser_mode}")

                shared_driver = None
                first_depo = True

                for idx, (depo_name, depo) in enumerate(self.available_depolar.items()):
                    # Önce credentials kontrolü - yoksa atla
                    creds = credentials.get(depo_name, {})

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

                    try:
                        self.status_label.config(text=f"⏳ {depo.name} açılıyor...")
                        self.root.update()  # GUI'yi güncelle

                        if browser_mode == "windows":
                            # Ayrı pencere modu - her depo kendi driver'ını alır
                            if not depo.init_driver(headless=HEADLESS):
                                logger.error(f"{depo.name} başlatılamadı!")
                                continue
                        else:
                            # Sekme modu (varsayılan) - ilk depo driver oluşturur, diğerleri paylaşır
                            if first_depo:
                                if not depo.init_driver(headless=HEADLESS):
                                    logger.error(f"{depo.name} başlatılamadı!")
                                    continue
                                shared_driver = depo.driver
                                first_depo = False
                            else:
                                if not shared_driver:
                                    logger.error(f"Paylaşılan driver yok, {depo.name} başlatılamadı!")
                                    continue
                                if not depo.init_driver(headless=HEADLESS, shared_driver=shared_driver):
                                    logger.error(f"{depo.name} tab'ı açılamadı!")
                                    continue

                        if not depo.open_page():
                            logger.error(f"{depo.name} sayfası açılamadı!")
                            continue

                        time.sleep(2)

                        # Otomatik giriş yap
                        logger.info(f"{depo.name}: Otomatik giriş yapılıyor...")

                        if depo_name == "alliance":
                            depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                        elif depo_name == "selcuk":
                            depo.login(creds["hesap_kodu"], creds["username"], creds["password"])
                        elif depo_name == "yusufpasa":
                            depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                        elif depo_name in ["iskoop", "bursa", "farmazon", "sancak"]:
                            depo.login(creds["username"], creds["password"])

                        time.sleep(2)

                    except Exception as e:
                        logger.error(f"{depo.name} açılırken hata: {e}")

                self.status_label.config(text="✅ Depolar açıldı!")
                self.root.update()
                logger.info("Depolar açıldı, arama başlıyor...")
                time.sleep(0.5)

            results = []
            product_name = None  # Ürün adı için

            # Önce CSV'den ürün adını bul
            try:
                import csv
                csv_path = Path(__file__).resolve().parent.parent / "Tüm İlaç Listesi.csv"
                if csv_path.exists():
                    with open(csv_path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if row.get('Barkod', '').strip() == barcode:
                                product_name = row.get('İlaç Adı', '').strip()
                                logger.info(f"CSV'den ürün adı bulundu: {product_name}")
                                break
            except Exception as e:
                logger.warning(f"CSV'den ürün adı okunamadı: {e}")

            # Durum çubuğunda ilaç adı ve barkod göster
            if product_name:
                self.status_label.config(text=f"🔍 Aranıyor: {product_name} (Barkod: {barcode})")
            else:
                self.status_label.config(text=f"🔍 Aranıyor: Barkod {barcode}")
            self.root.update()  # GUI'yi zorla güncelle
            logger.info(f"Hızlı arama: {product_name if product_name else barcode} ({barcode})")

            # Depo durumlarını sakla
            depo_durumlar = {}

            # Her depoda ara (sadece kullanılabilir depoları)
            for depo_name, depo in self.available_depolar.items():
                try:
                    # Depo açık mı?
                    if not depo.driver:
                        results.append(f"{depo.name}: Kapalı")
                        logger.info(f"{depo.name}: Kapalı (driver yok)")
                        depo_durumlar[f"{depo_name}_durum"] = {
                            "stok_var": False,
                            "mesaj": "Kapalı",
                            "detay": "Depo açık değil"
                        }
                        continue

                    # Depo tab'ına geç
                    logger.info(f"{depo.name}: Tab'a geçiliyor...")
                    depo.switch_to_tab()
                    time.sleep(0.5)

                    # Barkodu ara
                    logger.info(f"{depo.name}: Barkod aranıyor: {barcode}")
                    if depo.search_barcode(barcode):
                        # Ürün adını al (henüz alınmadıysa veya "Barkod: XXX" ise)
                        if not product_name or product_name.startswith("Barkod:"):
                            try:
                                # Depo'da get_product_name metodu varsa kullan
                                if hasattr(depo, 'get_product_name'):
                                    temp_name = depo.get_product_name()
                                    if temp_name and not temp_name.startswith("Barkod:"):
                                        product_name = temp_name
                                        logger.info(f"{depo.name}: Ürün adı alındı: {product_name}")
                            except Exception as e:
                                logger.warning(f"{depo.name}: Ürün adı alma hatası: {e}")

                        # Stok durumunu kontrol et
                        stok_durum = depo.check_stock_status()
                        depo_durumlar[f"{depo_name}_durum"] = stok_durum

                        if stok_durum["stok_var"]:
                            results.append(f"{depo.name}: ✅VAR")
                            logger.info(f"{depo.name}: ✅ Stokta var")
                        else:
                            results.append(f"{depo.name}: ❌YOK")
                            logger.info(f"{depo.name}: ❌ Stokta yok")
                    else:
                        results.append(f"{depo.name}: ⚠️ARAMA HATASI")
                        logger.warning(f"{depo.name}: ⚠️ Arama başarısız")
                        depo_durumlar[f"{depo_name}_durum"] = {
                            "stok_var": False,
                            "mesaj": "Arama Hatası",
                            "detay": "Barkod araması başarısız"
                        }

                except Exception as e:
                    results.append(f"{depo.name}: HATA")
                    logger.error(f"{depo.name} arama hatası: {e}")
                    depo_durumlar[f"{depo_name}_durum"] = {
                        "stok_var": False,
                        "mesaj": "Hata",
                        "detay": str(e)
                    }

            # Sonuçları göster
            if not product_name:
                # Ürün adı alınamamışsa barkodu kullan
                product_name = f"Barkod: {barcode}"

            result_text = f"{product_name} → " + " | ".join(results)

            self.status_label.config(text=f"📊 {result_text}")
            self.root.update()  # GUI'yi zorla güncelle

            # Ürün adı bulunamadıysa fallback
            if not product_name:
                product_name = f"Barkod: {barcode}"
                logger.warning(f"Ürün adı bulunamadı, fallback kullanıldı: {product_name}")

            # Açıklama metnini oluştur (controller'daki mantık ile)
            fake_product = {
                "row": len(self.products) + 1,
                "urun_adi": product_name,
                "barkod": barcode,
                "stok": 0,
                "mf": 0,
                "minstk": 0,
                "siparis_adet": 0
            }
            fake_product.update(depo_durumlar)

            # Açıklama metnini oluştur
            aciklama = self.controller._build_aciklama_text(fake_product)
            fake_product["aciklama_ozeti"] = aciklama

            # Listeye ekle
            self.add_product_row(fake_product)

            # Son aranan barkodu sakla
            self.last_searched_barcode = barcode
            logger.info(f"Arama sonuçları: {result_text}")

            # Barkod alanını temizle
            self.barcode_entry.delete(0, tk.END)
            self.barcode_entry.focus()  # Focus'u geri ver

            # GUI'yi en üste getir
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(100, lambda: self.root.attributes('-topmost', False))
            logger.info("✓ GUI penceresi en üste getirildi")

        except Exception as e:
            logger.error(f"Hızlı arama hatası: {e}")
            self.status_label.config(text=f"❌ Arama hatası: {str(e)[:50]}")

    def _search_single_depo(self, depo_name, depo, barcode):
        """Tek bir depoda barkod ara (paralel arama için)"""
        import time
        import threading
        logger.debug(f"[Thread-{threading.current_thread().name}] {depo_name} aranıyor: {barcode}")
        try:
            if not depo.driver:
                return depo_name, {
                    "stok_var": False,
                    "mesaj": "Kapalı",
                    "fiyat": None,
                    "satis_kosullari": []
                }

            # Barkodu ara
            if depo.search_barcode(barcode):
                stok_durum = depo.check_stock_status()
                return depo_name, stok_durum
            else:
                return depo_name, {
                    "stok_var": False,
                    "mesaj": "Bulunamadı",
                    "fiyat": None,
                    "satis_kosullari": []
                }

        except Exception as e:
            return depo_name, {
                "stok_var": False,
                "mesaj": "Hata",
                "detay": str(e),
                "fiyat": None,
                "satis_kosullari": []
            }

    def search_barcode_kiyas(self, barcode, ilac_adi=None):
        """Kıyas Motoru için barkod ara - Botanik olmadan, GUI tablosuna eklemeden

        Args:
            barcode: Aranacak barkod
            ilac_adi: İlaç adı (opsiyonel)

        Returns:
            dict: Depo sonuçları veya None
        """
        import time
        import os
        from concurrent.futures import ThreadPoolExecutor, as_completed

        try:
            if not barcode:
                return None

            # Kullanılabilir depo var mı?
            if not self.available_depolar:
                return None

            results = {}
            product_name = ilac_adi

            # Tarayıcı modunu kontrol et
            browser_mode = os.getenv("BROWSER_MODE", "tabs")

            if browser_mode == "windows":
                # PARALEL ARAMA - Ayrı pencereler modunda
                # Tüm depolarda aynı anda ara
                logger.info(f"🚀 PARALEL ARAMA başlıyor - {len(self.available_depolar)} depo")
                with ThreadPoolExecutor(max_workers=len(self.available_depolar)) as executor:
                    futures = {}
                    for depo_name, depo in self.available_depolar.items():
                        if depo.driver:
                            future = executor.submit(self._search_single_depo, depo_name, depo, barcode)
                            futures[future] = depo_name
                        else:
                            results[depo_name] = {
                                "stok_var": False,
                                "mesaj": "Kapalı",
                                "fiyat": None,
                                "satis_kosullari": []
                            }

                    # Sonuçları topla
                    for future in as_completed(futures):
                        depo_name, result = future.result()
                        results[depo_name] = result

            else:
                # SIRAYLA ARAMA - Sekme modunda (tek pencere)
                for depo_name, depo in self.available_depolar.items():
                    try:
                        if not depo.driver:
                            results[depo_name] = {
                                "stok_var": False,
                                "mesaj": "Kapalı",
                                "fiyat": None,
                                "satis_kosullari": []
                            }
                            continue

                        # Depo tab'ına geç
                        depo.switch_to_tab()
                        time.sleep(0.3)

                        # Barkodu ara
                        if depo.search_barcode(barcode):
                            if not product_name and hasattr(depo, 'get_product_name'):
                                try:
                                    temp_name = depo.get_product_name()
                                    if temp_name:
                                        product_name = temp_name
                                except:
                                    pass

                            stok_durum = depo.check_stock_status()
                            results[depo_name] = stok_durum
                        else:
                            results[depo_name] = {
                                "stok_var": False,
                                "mesaj": "Bulunamadı",
                                "fiyat": None,
                                "satis_kosullari": []
                            }

                    except Exception as e:
                        results[depo_name] = {
                            "stok_var": False,
                            "mesaj": "Hata",
                            "detay": str(e),
                            "fiyat": None,
                            "satis_kosullari": []
                        }

            return {
                "barkod": barcode,
                "ilac_adi": product_name or f"Barkod: {barcode}",
                "depolar": results
            }

        except Exception as e:
            logger.error(f"Kıyas arama hatası: {e}")
            return None

    def save_html(self):
        """TÜM ürünleri HTML dosyası olarak kaydet"""
        try:
            from tkinter import filedialog
            from datetime import datetime
            import os

            # TÜM ürünleri al
            selected_items = self.tree.get_children()
            if not selected_items:
                messagebox.showwarning("Uyarı", "Kaydedilecek ürün yok!")
                return

            logger.info(f"HTML kaydetme: {len(selected_items)} ürün")

            # Ürün bilgilerini topla
            selected_products = []
            for idx, item in enumerate(selected_items, 1):
                values = self.tree.item(item, "values")
                row_num = int(values[0])

                # Controller'dan ürünü bul
                product = None
                for p in self.products:
                    product_data = p.get("data", p)
                    if product_data.get("row") == row_num:
                        product = product_data
                        break

                if product:
                    selected_products.append(product)

            if not selected_products:
                messagebox.showwarning("Uyarı", "Kaydedilecek ürün bulunamadı!")
                return

            # Eczane bilgilerini al
            eczane_info = {
                "eczaci_adi": os.getenv("ECZACI_ADI", ""),
                "eczane_adi": os.getenv("ECZANE_ADI", ""),
                "eczane_telefonu": os.getenv("ECZANE_TELEFONU", ""),
                "eczaci_telefonu": os.getenv("ECZACI_TELEFONU", "")
            }

            # HTML dosyası oluştur
            from ..utils.html_generator import create_html_file
            html_file = create_html_file(selected_products, eczane_info)

            # Kaydetme yeri sor
            tarih = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"siparis_listesi_{tarih}.html"

            save_path = filedialog.asksaveasfilename(
                title="HTML Dosyasını Kaydet",
                defaultextension=".html",
                initialfile=default_filename,
                filetypes=[("HTML Dosyası", "*.html"), ("Tüm Dosyalar", "*.*")]
            )

            if save_path:
                # Geçici dosyayı kayıt yerine kopyala
                import shutil
                shutil.copy(html_file, save_path)

                # Geçici dosyayı sil
                try:
                    os.remove(html_file)
                except:
                    pass

                logger.info(f"HTML dosyası kaydedildi: {save_path}")
                messagebox.showinfo("Başarılı", f"HTML dosyası kaydedildi!\n\n{save_path}")
            else:
                # İptal edildi, geçici dosyayı sil
                try:
                    os.remove(html_file)
                except:
                    pass

        except Exception as e:
            logger.error(f"HTML kaydetme hatası: {e}")
            messagebox.showerror("Hata", f"HTML kaydedilemedi:\n{e}")

    def bring_to_front(self):
        """GUI penceresini en öne getir"""
        try:
            logger.info("GUI penceresi en öne getiriliyor...")
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(200, lambda: self.root.attributes('-topmost', False))
            self.root.focus_force()
            logger.info("✓ GUI penceresi en öne getirildi")
        except Exception as e:
            logger.error(f"GUI penceresi en öne getirilemedi: {e}")

    # ==================== KIYAS MODU FONKSİYONLARI ====================

    def _load_kiyas_ilac_listesi(self):
        """CSV dosyasından ilaç listesini yükle"""
        import csv as csv_module
        import os.path

        try:
            # __file__ üzerinden src klasörünü bul
            gui_dir = os.path.dirname(os.path.abspath(__file__))
            src_dir = os.path.dirname(gui_dir)

            # Olası CSV yolları
            possible_paths = [
                os.path.join(src_dir, "Tüm İlaç ListesiTam.csv"),
                r"C:\Users\fmazi\Documents\BotSiparis\src\Tüm İlaç ListesiTam.csv",
            ]

            csv_path = None
            for p in possible_paths:
                if os.path.exists(p):
                    csv_path = p
                    logger.info(f"CSV bulundu: {p}")
                    break

            if csv_path:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv_module.DictReader(f)
                    self.kiyas_ilac_listesi = list(reader)
                    self.kiyas_toplam = len(self.kiyas_ilac_listesi)
                    logger.info(f"Kıyas için {self.kiyas_toplam} ilaç yüklendi")
            else:
                logger.warning(f"CSV dosyası bulunamadı! Denenen: {possible_paths}")
                messagebox.showwarning("Uyarı", f"İlaç listesi CSV dosyası bulunamadı!\n\nAranan: {src_dir}")
                self.kiyas_ilac_listesi = []
                self.kiyas_toplam = 0
        except Exception as e:
            logger.error(f"Kıyas CSV yüklenirken hata: {e}")
            messagebox.showerror("Hata", f"CSV yüklenemedi: {e}")
            self.kiyas_ilac_listesi = []
            self.kiyas_toplam = 0

    def _open_depolar_for_kiyas(self):
        """Kıyas için depoları otomatik aç"""
        try:
            import os
            from pathlib import Path
            from ..utils import HEADLESS
            from dotenv import load_dotenv

            # .env dosyasını yükle
            env_path = Path(__file__).resolve().parent.parent.parent / ".env"
            if env_path.exists():
                load_dotenv(env_path)

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

            # Tarayıcı modunu al (tabs = tek pencere sekmeler, windows = ayrı pencereler)
            browser_mode = os.getenv("BROWSER_MODE", "tabs")
            logger.info(f"Tarayıcı modu: {browser_mode}")

            shared_driver = None
            first_depo = True
            acilan_depo_sayisi = 0

            logger.info(f"Aktif depolar: {list(self.available_depolar.keys())}")

            for depo_name, depo in self.available_depolar.items():
                creds = credentials.get(depo_name, {})
                logger.info(f"{depo_name} credentials: {bool(creds)}")

                has_credentials = False
                if depo_name == "alliance":
                    has_credentials = bool(creds.get("eczane_kodu") and creds.get("username") and creds.get("password"))
                elif depo_name == "selcuk":
                    has_credentials = bool(creds.get("hesap_kodu") and creds.get("username") and creds.get("password"))
                elif depo_name == "yusufpasa":
                    has_credentials = bool(creds.get("eczane_kodu") and creds.get("username") and creds.get("password"))
                elif depo_name in ["iskoop", "bursa", "farmazon", "sancak"]:
                    has_credentials = bool(creds.get("username") and creds.get("password"))

                logger.info(f"{depo_name} has_credentials: {has_credentials}")

                if not has_credentials:
                    logger.warning(f"{depo_name} için bilgiler eksik, atlanıyor")
                    continue

                try:
                    self.kiyas_status_label.config(text=f"⏳ {depo.name} açılıyor...")
                    self.root.update()

                    if browser_mode == "windows":
                        # Ayrı pencere modu - her depo kendi driver'ını alır
                        if not depo.init_driver(headless=HEADLESS):
                            continue
                    else:
                        # Sekme modu (varsayılan) - ilk depo driver oluşturur, diğerleri paylaşır
                        if first_depo:
                            if not depo.init_driver(headless=HEADLESS):
                                continue
                            shared_driver = depo.driver
                            first_depo = False
                        else:
                            if not shared_driver:
                                continue
                            if not depo.init_driver(headless=HEADLESS, shared_driver=shared_driver):
                                continue

                    if not depo.open_page():
                        continue

                    import time
                    time.sleep(2)

                    self.kiyas_status_label.config(text=f"⏳ {depo.name} giriş...")
                    self.root.update()

                    if depo_name == "alliance":
                        depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                    elif depo_name == "selcuk":
                        depo.login(creds["hesap_kodu"], creds["username"], creds["password"])
                    elif depo_name == "yusufpasa":
                        depo.login(creds["eczane_kodu"], creds["username"], creds["password"])
                    elif depo_name in ["iskoop", "bursa", "farmazon", "sancak"]:
                        depo.login(creds["username"], creds["password"])

                    time.sleep(2)
                    acilan_depo_sayisi += 1

                except Exception as e:
                    logger.error(f"{depo.name} açılırken hata: {e}")

            return acilan_depo_sayisi > 0

        except Exception as e:
            logger.error(f"Depo açma hatası: {e}")
            return False

    def start_kiyas_scan(self):
        """Kıyas taramasını başlat"""
        if self.kiyas_scanning:
            return

        # Önce ilaç listesi yüklü mü kontrol et
        if self.kiyas_toplam == 0:
            messagebox.showwarning("Uyarı", "İlaç listesi yüklenemedi!\nCSV dosyasını kontrol edin.")
            return

        # Aralık değerlerini al
        try:
            start_idx = int(self.kiyas_start_entry.get()) - 1  # 0-indexed
            end_idx = int(self.kiyas_end_entry.get())

            if start_idx < 0:
                start_idx = 0
            if end_idx > self.kiyas_toplam:
                end_idx = self.kiyas_toplam
            if start_idx >= end_idx:
                messagebox.showwarning("Uyarı", f"Başlangıç ({start_idx+1}), bitişten ({end_idx}) küçük olmalı!")
                return

            self.kiyas_range = (start_idx, end_idx)
            total_to_scan = end_idx - start_idx

        except ValueError:
            messagebox.showerror("Hata", "Lütfen geçerli sayılar girin!")
            return

        if not self.available_depolar:
            messagebox.showwarning("Uyarı", "Aktif depo yok! Önce ayarlardan depoları etkinleştirin.")
            return

        # En az bir depo açık mı?
        acik_depo = False
        for depo_name, depo in self.available_depolar.items():
            if depo.driver:
                acik_depo = True
                break

        if not acik_depo:
            self.kiyas_status_label.config(text="⏳ Depolar açılıyor...")
            self.kiyas_progress_label.config(text="")
            self.root.update()

            if not self._open_depolar_for_kiyas():
                self.kiyas_status_label.config(text="▶ Başlat'a tıklayın")
                messagebox.showwarning("Uyarı", "Hiçbir depo açılamadı!")
                return

        # Tabloyu temizle
        self.tree.delete(*self.tree.get_children())
        self.products.clear()

        # Arayüzü güncelle
        self.kiyas_scanning = True
        self.kiyas_current = 0
        self.kiyas_status_label.config(text="⏳ Taranıyor...")
        # Label butonların görünümünü değiştir (disabled görüntüsü)
        self.kiyas_start_button.config(bg="#555", fg="#888")
        self.kiyas_stop_button.config(bg="#e74c3c", fg="white")
        self.kiyas_exit_button.config(bg="#555", fg="#888")
        self.kiyas_start_entry.config(state=tk.DISABLED)
        self.kiyas_end_entry.config(state=tk.DISABLED)

        # Progress bar ayarla
        self.kiyas_progress_bar["maximum"] = total_to_scan
        self.kiyas_progress_bar["value"] = 0

        # Thread ile taramayı başlat
        self.kiyas_thread = threading.Thread(target=self._run_kiyas_scan, daemon=True)
        self.kiyas_thread.start()

    def _run_kiyas_scan(self):
        """Kıyas taramasını arka planda çalıştır"""
        import time
        start_idx, end_idx = self.kiyas_range
        total_to_scan = end_idx - start_idx

        try:
            for idx, i in enumerate(range(start_idx, end_idx)):
                if not self.kiyas_scanning:
                    break

                # Satır numarası HER ZAMAN 1'den başlar (idx + 1)
                row_number = idx + 1

                ilac = self.kiyas_ilac_listesi[i]
                ilac_adi = ilac.get("İlaç Adı", "")
                barkod = ilac.get("Barkod", "")

                scanned_count = idx + 1
                self.kiyas_current = scanned_count

                # İlerlemeyi güncelle
                self.root.after(0, self._update_kiyas_progress, scanned_count, total_to_scan, ilac_adi, barkod)

                # Depolarda ara
                try:
                    result = self.search_barcode_kiyas(barkod, ilac_adi)
                    if result:
                        depolar = result.get("depolar", {})

                        product_data = {
                            "row": row_number,
                            "urun_adi": ilac_adi,
                            "barkod": barkod,
                            "stok": 0,
                            "mf": 0,
                            "minstk": 0,
                            "siparis_adet": 0
                        }

                        for depo_name, depo_info in depolar.items():
                            product_data[f"{depo_name}_durum"] = depo_info

                        stokta_var = [d.upper() for d, info in depolar.items() if info.get("stok_var")]
                        if stokta_var:
                            product_data["aciklama_ozeti"] = f"✅ {', '.join(stokta_var)}"
                        else:
                            product_data["aciklama_ozeti"] = "❌ Stok yok"

                        self.root.after(0, self.add_product_row, product_data)

                        # Rastgele bekleme (6-8 saniye) - robot algılamasını önlemek için
                        import random
                        delay = random.uniform(6, 8)
                        time.sleep(delay)

                except Exception as e:
                    logger.error(f"Kıyas arama hatası ({barkod}): {e}")

            # Tamamlandı
            self.root.after(0, self._kiyas_scan_completed)

        except Exception as e:
            logger.error(f"Kıyas tarama hatası: {e}")
            self.root.after(0, self._kiyas_scan_completed)

    def _update_kiyas_progress(self, current, total, ilac_adi, barkod):
        """Kıyas ilerleme bilgisini güncelle"""
        percentage = (current / total) * 100 if total > 0 else 0
        self.kiyas_progress_bar["value"] = current
        self.kiyas_progress_bar["maximum"] = total
        self.kiyas_progress_label.config(text=f"{current}/{total}")
        self.status_label.config(text=f"⚖ {ilac_adi[:50]} ({barkod})")

    def _kiyas_scan_completed(self):
        """Kıyas taraması tamamlandığında"""
        self.kiyas_scanning = False
        # Label butonları normale döndür
        self.kiyas_start_button.config(bg="#27ae60", fg="white")
        self.kiyas_stop_button.config(bg="#415a77", fg="#778da9")
        self.kiyas_exit_button.config(bg="#415a77", fg="#e0e1dd")
        self.kiyas_start_entry.config(state=tk.NORMAL)
        self.kiyas_end_entry.config(state=tk.NORMAL)

        self.kiyas_status_label.config(text="✅ Tamamlandı")
        self.kiyas_progress_label.config(text=f"{self.kiyas_current} ilaç")
        self.status_label.config(text="⚖ Kıyas Tamamlandı")

    def stop_kiyas_scan(self):
        """Kıyas taramasını durdur"""
        if not self.kiyas_scanning:
            return
        self.kiyas_scanning = False
        self.kiyas_status_label.config(text="⏹ Durduruldu - Devam için ▶")
        self.kiyas_progress_label.config(text="")
        # Label butonları normale döndür
        self.kiyas_start_button.config(bg="#27ae60", fg="white")
        self.kiyas_stop_button.config(bg="#415a77", fg="#778da9")
        self.kiyas_exit_button.config(bg="#415a77", fg="#e0e1dd")
        self.kiyas_start_entry.config(state=tk.NORMAL)
        self.kiyas_end_entry.config(state=tk.NORMAL)
        self.status_label.config(text="⚖ Kıyas Durduruldu")

    def exit_kiyas_mode(self):
        """Kıyas modundan çık"""
        if self.kiyas_scanning:
            if not messagebox.askyesno("Onay", "Kıyas devam ediyor. Çıkmak istiyor musunuz?"):
                return
            self.kiyas_scanning = False

        # Kıyas modundan çık
        self.kiyas_mode = False

        # Kıyas barını gizle
        self.kiyas_bar.pack_forget()

        # Normal mod butonlarını ve aylık gidişi tekrar göster
        self.right_frame.pack(side=tk.RIGHT, padx=3)  # Hızlı Tarama, Listeyi Sil
        self.monthly_container.pack(fill=tk.X, padx=10, pady=5)  # Aylık Toplam Gidiş
        logger.info("Normal mod butonları ve aylık gidiş gösterildi")

        # Tüm sütunları geri getir (displaycolumns'u sıfırla)
        self.tree["displaycolumns"] = list(self.tree["columns"])

        # Label butonlarını ve entry'leri resetle
        self.kiyas_start_button.config(bg="#27ae60", fg="white")
        self.kiyas_stop_button.config(bg="#415a77", fg="#778da9")
        self.kiyas_exit_button.config(bg="#415a77", fg="#e0e1dd")
        self.kiyas_start_entry.config(state=tk.NORMAL)
        self.kiyas_end_entry.config(state=tk.NORMAL)
        self.kiyas_progress_bar["value"] = 0
        self.kiyas_progress_label.config(text="")
        self.kiyas_status_label.config(text="▶ Başlat'a tıklayın")

        # Tabloyu temizle
        self.tree.delete(*self.tree.get_children())
        self.products.clear()

        self.status_label.config(text="Hazır")

        # GUI'yi sağ tarafa geri al
        self.position_initial()
        logger.info("GUI sağ tarafa geri alındı")

    # ==================== PENCERE KAPAMA ====================

    def on_closing(self):
        """Pencere kapatılırken depoları temizle"""
        try:
            logger.info("GUI kapatılıyor, depolar kapatılıyor...")

            # Botanik Sipariş Yardımcısı'nı tam yüksekliğe ayarla (taskbar hariç)
            # GENİŞLİK AYNI KALIR, sadece yükseklik artar
            if self.controller and self.controller.botanik:
                try:
                    logger.info("Botanik Sipariş Yardımcısı tam yüksekliğe ayarlanıyor...")
                    import pyautogui
                    import win32gui
                    screen_width, screen_height = pyautogui.size()

                    hwnd = self.controller.botanik.main_window.handle

                    # Mevcut pencere boyutlarını al
                    rect = win32gui.GetWindowRect(hwnd)
                    current_width = rect[2] - rect[0]  # right - left
                    current_x = rect[0]

                    logger.debug(f"Mevcut Botanik genişliği: {current_width}, x konumu: {current_x}")

                    # Taskbar yüksekliğini hesapla (genelde ~40px ama sistemden al)
                    import win32api
                    import win32con
                    taskbar_height = 40  # Varsayılan
                    try:
                        # SPI_GETWORKAREA ile çalışma alanını al (taskbar hariç)
                        work_area = win32api.SystemParametersInfo(win32con.SPI_GETWORKAREA)
                        taskbar_height = screen_height - work_area[3]  # work_area[3] = bottom
                    except:
                        pass

                    # Pencere boyutları: Mevcut genişlik korunur, yükseklik tam (taskbar hariç)
                    window_width = current_width  # GENİŞLİK AYNI KALIR
                    window_height = screen_height - taskbar_height

                    SWP_NOZORDER = 0x0004
                    SWP_SHOWWINDOW = 0x0040
                    flags = SWP_NOZORDER | SWP_SHOWWINDOW

                    win32gui.SetWindowPos(
                        hwnd,
                        0,
                        current_x,  # x konumu da aynı kalır
                        0,  # y = 0 (üst kenar)
                        window_width,
                        window_height,
                        flags
                    )

                    logger.info(f"✓ Botanik Sipariş Yardımcısı yüksekliği artırıldı: {window_width}x{window_height}")
                except Exception as e:
                    logger.warning(f"Botanik boyutlandırma hatası: {e}")

            # Depoları kapat
            if self.controller and hasattr(self.controller, 'depolar'):
                for depo in self.controller.depolar.values():
                    try:
                        depo.close()
                        logger.info(f"{depo.name} kapatıldı")
                    except Exception as e:
                        logger.warning(f"{depo.name} kapatılırken hata: {e}")

            # Pencereyi kapat
            self.root.destroy()

        except Exception as e:
            logger.error(f"Kapatma hatası: {e}")
            self.root.destroy()

    def update_monthly_table_from_product(self, product_data):
        """Ürün verisinden alt panelleri güncelle (tarama sırasında kullanılır - CSV'ye gerek yok)"""
        try:
            monthly_sales = product_data.get("monthly_sales", {})

            # Alt tabloyu güncelle
            for item in self.monthly_tree.get_children():
                self.monthly_tree.delete(item)

            if not monthly_sales:
                # Boş göster
                col_count = len(self.monthly_tree["columns"])
                self.monthly_tree.insert("", tk.END, values=["-"] * col_count)
                self.info_stok_label.config(text="-")
                self.info_siparis_label.config(text="-")
                self.info_gun_label.config(text="-")
                return

            # Sütun sırası - DİNAMİK
            from datetime import datetime

            today = datetime.now()
            columns = []

            # 12 ay önceden bugüne kadar (ters sıra: eski -> yeni)
            for i in range(12, -1, -1):
                target_month = today.month - i
                target_year = today.year

                while target_month <= 0:
                    target_month += 12
                    target_year -= 1

                columns.append(f"{target_month:02d}.{target_year % 100:02d}")

            columns.extend(["Top", "Ort"])

            # Top satırı değerleri
            top_values = [monthly_sales.get(col, "-") for col in columns]
            self.monthly_tree.insert("", tk.END, values=top_values)

            # Bilgi panelini güncelle
            stok = product_data.get("stok", 0)
            siparis_adet = product_data.get("siparis_adet", 0)

            self.info_stok_label.config(text=str(stok))
            self.info_siparis_label.config(text=str(siparis_adet) if siparis_adet else "-")

            # Kaç günde bitecek hesapla
            ort_str = monthly_sales.get("Ort", "0")
            try:
                ort = float(ort_str.replace(",", ".")) if ort_str and ort_str != "-" else 0
            except:
                ort = 0

            if ort <= 0:
                self.info_gun_label.config(text="Gidiş yok")
            else:
                toplam_ilaç = stok + siparis_adet
                gun = (toplam_ilaç * 30) / ort
                self.info_gun_label.config(text=f"{gun:.1f} gün")

        except Exception as e:
            logger.error(f"Alt panel güncelleme hatası: {e}")

    def on_row_selected(self, event):
        """Üst tabloda satır seçildiğinde aylık gidiş tablosunu güncelle (CSV'den oku - HIZLI)"""
        try:
            # Seçili satırları al
            selected_items = self.tree.selection()
            if not selected_items:
                # Hiçbir satır seçili değilse alt tabloyu temizle
                for item in self.monthly_tree.get_children():
                    self.monthly_tree.delete(item)
                self.monthly_tree.insert("", tk.END, values=["-"] * 15)
                self.selected_product = None
                self.info_stok_label.config(text="-")
                self.info_siparis_label.config(text="-")
                self.info_gun_label.config(text="-")
                return

            # İlk seçili satırı al
            item_id = selected_items[0]

            # Bu satırın bilgilerini bul
            product_data = None
            for product in self.products:
                if product["item_id"] == item_id:
                    product_data = product
                    break

            if not product_data:
                return

            # Seçili ürünü kaydet
            self.selected_product = product_data

            row_num = product_data["data"].get("row")

            # Controller kontrolü
            if not self.controller:
                self.update_sartlar_table(product_data)
                return

            # Önce product_data içinde monthly_sales var mı kontrol et (hızlı tarama modunda dolu gelir)
            monthly_sales = product_data["data"].get("monthly_sales", {})

            # Eğer product_data'da yoksa CSV'den oku
            if not monthly_sales:
                monthly_sales = self.controller.get_monthly_sales_from_csv(row_num)

            # Efektif fiyatları güncel verilerle yeniden hesapla
            if monthly_sales:
                ort_str = monthly_sales.get("Ort", "0")
                try:
                    aylik_satis = float(str(ort_str).replace(",", "."))
                except:
                    aylik_satis = 1

                # Güncel aylık satış değerini product_data'ya ekle
                product_data["data"]["ort"] = aylik_satis
                product_data["data"]["monthly_sales"] = monthly_sales

                # En karlı seçeneği güncel verilerle yeniden hesapla
                en_karli_sonuc = self.controller.bul_en_karli_secenek(product_data["data"])
                if en_karli_sonuc:
                    product_data["data"]["en_karli_sonuc"] = en_karli_sonuc

            # Depo şartları tablosunu güncelle (güncel efektif fiyatlarla)
            self.update_sartlar_table(product_data)

            if not monthly_sales:
                # CSV'de yoksa boş göster
                for item in self.monthly_tree.get_children():
                    self.monthly_tree.delete(item)
                # Dinamik sütun sayısı (13 ay + Top + Ort = 15)
                col_count = len(self.monthly_tree["columns"])
                self.monthly_tree.insert("", tk.END, values=["-"] * col_count)
                self.info_stok_label.config(text="-")
                self.info_siparis_label.config(text="-")
                self.info_gun_label.config(text="-")
                return

            # Alt tabloyu güncelle (SADECE TOP SATIRI)
            for item in self.monthly_tree.get_children():
                self.monthly_tree.delete(item)

            # Sütun sırası - DİNAMİK
            from datetime import datetime

            today = datetime.now()
            columns = []

            # 12 ay önceden bugüne kadar (ters sıra: eski -> yeni)
            for i in range(12, -1, -1):
                target_month = today.month - i
                target_year = today.year

                while target_month <= 0:
                    target_month += 12
                    target_year -= 1

                columns.append(f"{target_month:02d}.{target_year % 100:02d}")

            columns.extend(["Top", "Ort"])

            # Top satırı değerleri
            top_values = [monthly_sales.get(col, "-") for col in columns]
            self.monthly_tree.insert("", tk.END, values=top_values)

            # Bilgi panelini güncelle
            stok = product_data["data"].get("stok", 0)
            siparis_adet = product_data["data"].get("siparis_adet", 0)

            self.info_stok_label.config(text=str(stok))
            self.info_siparis_label.config(text=str(siparis_adet) if siparis_adet else "-")

            # Kaç günde bitecek hesapla
            self.update_days_calculation()

        except Exception as e:
            logger.error(f"Aylık gidiş tablosu güncellenirken hata: {e}")

    def update_sartlar_table(self, product_data):
        """Depo şartları tablosunu güncelle (MF bilgileri)

        Yapı: Her depo için 2 sütun (Şart, Fiyat)
        1. satır: Normal fiyat (MF=0)
        2+ satırlar: MF'li şartlar
        En karlı şart ★ ile işaretlenir
        """
        try:
            # Tabloyu temizle
            for item in self.sartlar_tree.get_children():
                self.sartlar_tree.delete(item)

            data = product_data.get("data", {})

            # En karlı seçenekleri belirle
            en_karli_kombinasyonlar = set()  # (depo_key, sart) tuple'ları
            efektif_fiyatlar = {}  # (depo_key, sart) -> efektif_birim
            en_karli_sonuc = data.get("en_karli_sonuc")
            if en_karli_sonuc:
                en_karliler = en_karli_sonuc.get("en_karliler", [])
                for s in en_karliler:
                    depo = s.get("depo")
                    sart = s.get("sart", "1")
                    en_karli_kombinasyonlar.add((depo, sart))

                # Tüm seçeneklerin efektif fiyatlarını al
                tum_secenekler = en_karli_sonuc.get("tum_secenekler", [])
                for s in tum_secenekler:
                    depo = s.get("depo")
                    sart = s.get("sart", "1")
                    efektif_birim = s.get("efektif_birim")
                    if efektif_birim:
                        efektif_fiyatlar[(depo, sart)] = efektif_birim

            # Efektif fiyat gösterme ayarını kontrol et
            import os
            show_efektif = os.getenv("SHOW_EFEKTIF_FIYAT", "true").lower() == "true"

            # Debug: Gelen veriyi logla
            logger.debug(f"update_sartlar_table - data keys: {list(data.keys())}")

            # Her depo için şartları topla
            # NOT: KDV oranı artık her kosul içinden okunuyor (sayfadan alınıyor)
            # Format: {depo_key: [{"sart": "-", "fiyat": "88,77"}, {"sart": "8+1", "fiyat": "78,90"}, ...]}
            depo_sartlar = {}
            max_rows = 1  # En az 1 satır (normal fiyat)

            # Aktif depo listesini kullan (refresh sonrası güncellenen liste)
            active_list = getattr(self, 'active_sartlar_depo_list', None) or self.sartlar_depo_list

            logger.debug(f"Depo Şartları güncelleniyor - active_list: {active_list}")

            for depo_key in active_list:
                durum = data.get(f"{depo_key}_durum", {})
                stok_var = durum.get("stok_var", False)
                satis_kosullari = durum.get("satis_kosullari", [])

                logger.debug(f"  {depo_key}: stok_var={stok_var}, satis_kosullari={len(satis_kosullari)} adet")

                depo_sartlar[depo_key] = []

                # Stokta yoksa MF gösterme
                if not stok_var:
                    depo_sartlar[depo_key].append({"sart": "-", "fiyat": "-"})
                elif satis_kosullari:
                    # İlk satır: Normal fiyat (MF=0 olan veya ilk kayıt)
                    normal_fiyat = None
                    mf_sartlar = []

                    for kosul in satis_kosullari:
                        mf = kosul.get("mf", 0)
                        min_adet = kosul.get("min_adet", 1)
                        birim_fiyat = kosul.get("birim_fiyat", 0)
                        # KDV oranını kosuldan al (varsayılan %10)
                        kosul_kdv = kosul.get("kdv_orani", 10)
                        kdv_carpani = 1 + (kosul_kdv / 100)  # %10 -> 1.10, %8 -> 1.08

                        # kdv_dahil bayrağını kontrol et (yeni İskoop/BEK mantığı)
                        # Eğer depo KDV dahil fiyat gönderiyorsa (kdv_dahil=True) tekrar KDV ekleme
                        if kosul.get("kdv_dahil", False):
                            kdv_dahil = birim_fiyat  # KDV zaten dahil
                        elif depo_key in ("selcuk", "yusufpasa", "alliance", "sancak", "farmazon"):
                            kdv_dahil = birim_fiyat  # Bu depolar zaten KDV dahil fiyat veriyor
                        else:
                            kdv_dahil = birim_fiyat * kdv_carpani
                        fiyat_str = f"{kdv_dahil:.2f}".replace(".", ",")

                        if mf == 0 and normal_fiyat is None:
                            # Farmazon için özel format: optimum adet göster
                            if depo_key == "farmazon" and en_karli_sonuc:
                                tum_secenekler = en_karli_sonuc.get("tum_secenekler", [])
                                for s in tum_secenekler:
                                    if s.get("depo") == "farmazon":
                                        optimum_adet = s.get("optimum_adet", 1)
                                        efektif_birim = s.get("efektif_birim")
                                        sart_key = s.get("sart", "1")

                                        # Şart: 9(1) formatı
                                        if optimum_adet and optimum_adet > 1:
                                            sart_display = f"{optimum_adet}(1)"
                                        else:
                                            sart_display = "1"

                                        is_en_karli = (depo_key, sart_key) in en_karli_kombinasyonlar
                                        if is_en_karli:
                                            sart_display = f"★{sart_display}"

                                        # Fiyat + efektif fiyat
                                        fiyat_display = fiyat_str
                                        if show_efektif and efektif_birim:
                                            efektif_str = f"{efektif_birim:.2f}".replace(".", ",")
                                            fiyat_display = f"{fiyat_str}({efektif_str})"
                                        if is_en_karli:
                                            fiyat_display = f"★{fiyat_display}"

                                        normal_fiyat = {"sart": sart_display, "fiyat": fiyat_display}
                                        break
                                else:
                                    # Farmazon tum_secenekler'de yoksa normal göster
                                    normal_fiyat = {"sart": "1", "fiyat": fiyat_str}
                            else:
                                # Normal fiyat (1 adetlik) - şart olarak "1" yaz
                                sart_display = "1"
                                is_en_karli = (depo_key, "1") in en_karli_kombinasyonlar
                                # En karlı mı kontrol et
                                if is_en_karli:
                                    sart_display = "★1"
                                # Efektif fiyat ekle (ayar açıksa)
                                fiyat_display = fiyat_str
                                if show_efektif and (depo_key, "1") in efektif_fiyatlar:
                                    efektif = efektif_fiyatlar[(depo_key, "1")]
                                    efektif_str = f"{efektif:.2f}".replace(".", ",")
                                    fiyat_display = f"{fiyat_str}({efektif_str})"
                                # En karlı ise fiyata da yıldız ekle
                                if is_en_karli:
                                    fiyat_display = f"★{fiyat_display}"
                                normal_fiyat = {"sart": sart_display, "fiyat": fiyat_display}
                        elif mf > 0:
                            # MF'li şart
                            sart_str = f"{min_adet}+{mf}"
                            sart_display = sart_str
                            is_en_karli = (depo_key, sart_str) in en_karli_kombinasyonlar
                            # En karlı mı kontrol et
                            if is_en_karli:
                                sart_display = f"★{sart_str}"
                            # Efektif fiyat ekle (ayar açıksa)
                            fiyat_display = fiyat_str
                            if show_efektif and (depo_key, sart_str) in efektif_fiyatlar:
                                efektif = efektif_fiyatlar[(depo_key, sart_str)]
                                efektif_str = f"{efektif:.2f}".replace(".", ",")
                                fiyat_display = f"{fiyat_str}({efektif_str})"
                            # En karlı ise fiyata da yıldız ekle
                            if is_en_karli:
                                fiyat_display = f"★{fiyat_display}"
                            mf_sartlar.append({"sart": sart_display, "fiyat": fiyat_display})

                    # Normal fiyat yoksa ilk kaydı kullan
                    if normal_fiyat is None and satis_kosullari:
                        ilk = satis_kosullari[0]
                        birim_fiyat = ilk.get("birim_fiyat", 0)
                        min_adet = ilk.get("min_adet", 1)
                        # KDV oranını kosuldan al
                        ilk_kdv = ilk.get("kdv_orani", 10)
                        ilk_kdv_carpani = 1 + (ilk_kdv / 100)
                        # kdv_dahil bayrağını kontrol et (yeni İskoop/BEK mantığı)
                        if ilk.get("kdv_dahil", False):
                            kdv_dahil = birim_fiyat  # KDV zaten dahil
                        elif depo_key in ("selcuk", "yusufpasa", "alliance", "sancak", "farmazon"):
                            kdv_dahil = birim_fiyat  # Bu depolar zaten KDV dahil
                        else:
                            kdv_dahil = birim_fiyat * ilk_kdv_carpani
                        sart_display = str(min_adet)
                        sart_key = str(min_adet)
                        is_en_karli = (depo_key, sart_key) in en_karli_kombinasyonlar
                        # En karlı mı kontrol et
                        if is_en_karli:
                            sart_display = f"★{min_adet}"
                        # Efektif fiyat ekle (ayar açıksa)
                        fiyat_str = f"{kdv_dahil:.2f}".replace(".", ",")
                        fiyat_display = fiyat_str
                        if show_efektif and (depo_key, sart_key) in efektif_fiyatlar:
                            efektif = efektif_fiyatlar[(depo_key, sart_key)]
                            efektif_str = f"{efektif:.2f}".replace(".", ",")
                            fiyat_display = f"{fiyat_str}({efektif_str})"
                        # En karlı ise fiyata da yıldız ekle
                        if is_en_karli:
                            fiyat_display = f"★{fiyat_display}"
                        normal_fiyat = {"sart": sart_display, "fiyat": fiyat_display}

                    if normal_fiyat:
                        depo_sartlar[depo_key].append(normal_fiyat)

                    depo_sartlar[depo_key].extend(mf_sartlar)

                    # Maksimum satır sayısını güncelle
                    if len(depo_sartlar[depo_key]) > max_rows:
                        max_rows = len(depo_sartlar[depo_key])
                else:
                    # Şart bilgisi yok - sadece fiyat varsa göster
                    fiyat = durum.get("fiyat")
                    if fiyat:
                        fiyat_str = f"{fiyat:.2f}".replace(".", ",")

                        # Farmazon için özel format: optimum adet ve efektif fiyat
                        if depo_key == "farmazon" and en_karli_sonuc:
                            tum_secenekler = en_karli_sonuc.get("tum_secenekler", [])
                            for s in tum_secenekler:
                                if s.get("depo") == "farmazon":
                                    optimum_adet = s.get("optimum_adet", s.get("min_adet", 1))
                                    efektif_birim = s.get("efektif_birim")
                                    sart_key = s.get("sart", "1")

                                    # Şart: 9(1) formatı - 9 adet alırsan 1 tanesinin fiyatı
                                    if optimum_adet and optimum_adet > 1:
                                        sart_display = f"{optimum_adet}(1)"
                                    else:
                                        sart_display = "1"

                                    # En karlı mı kontrol et
                                    is_en_karli = (depo_key, sart_key) in en_karli_kombinasyonlar
                                    if is_en_karli:
                                        sart_display = f"★{sart_display}"

                                    # Fiyat: normal (efektif) formatı
                                    fiyat_display = fiyat_str
                                    if show_efektif and efektif_birim:
                                        efektif_str = f"{efektif_birim:.2f}".replace(".", ",")
                                        fiyat_display = f"{fiyat_str}({efektif_str})"
                                    if is_en_karli:
                                        fiyat_display = f"★{fiyat_display}"

                                    depo_sartlar[depo_key].append({"sart": sart_display, "fiyat": fiyat_display})
                                    break
                            else:
                                # Farmazon efektif hesabı yoksa normal göster
                                depo_sartlar[depo_key].append({"sart": "-", "fiyat": fiyat_str})
                        else:
                            depo_sartlar[depo_key].append({"sart": "-", "fiyat": fiyat_str})
                    else:
                        depo_sartlar[depo_key].append({"sart": "-", "fiyat": "-"})

            # Satırları oluştur
            for row_idx in range(max_rows):
                row_values = []
                for depo_key in active_list:
                    sartlar = depo_sartlar.get(depo_key, [])
                    if row_idx < len(sartlar):
                        row_values.append(sartlar[row_idx]["sart"])
                        row_values.append(sartlar[row_idx]["fiyat"])
                    else:
                        row_values.append("")
                        row_values.append("")

                self.sartlar_tree.insert("", tk.END, values=row_values)

            # Hiç satır yoksa boş göster
            if max_rows == 0:
                empty_values = ["-"] * (len(active_list) * 2)
                self.sartlar_tree.insert("", tk.END, values=empty_values)

        except Exception as e:
            logger.error(f"Depo şartları tablosu güncellenirken hata: {e}")
            active_list = getattr(self, 'active_sartlar_depo_list', None) or self.sartlar_depo_list
            empty_values = ["-"] * (len(active_list) * 2)
            self.sartlar_tree.insert("", tk.END, values=empty_values)

    def _on_sartlar_double_click(self, event):
        """Depo Şartları tablosunda çift tıklama - sadece Farmazon fiyat sütunu düzenlenebilir"""
        try:
            # Tıklanan hücreyi bul
            region = self.sartlar_tree.identify("region", event.x, event.y)
            if region != "cell":
                return

            column = self.sartlar_tree.identify_column(event.x)
            item = self.sartlar_tree.identify_row(event.y)

            if not column or not item:
                return

            # Sütun indeksini al (#1, #2, ... formatında)
            col_idx = int(column.replace("#", "")) - 1

            # Aktif depo listesini al
            active_list = getattr(self, 'active_sartlar_depo_list', None) or self.sartlar_depo_list

            # Farmazon fiyat sütununun indeksini bul
            # Her depo için 2 sütun var: sart, fiyat
            farmazon_idx = None
            for i, depo_key in enumerate(active_list):
                if depo_key == "farmazon":
                    farmazon_idx = i * 2 + 1  # fiyat sütunu (0: sart, 1: fiyat)
                    break

            if farmazon_idx is None or col_idx != farmazon_idx:
                return  # Sadece Farmazon fiyat sütunu düzenlenebilir

            # Mevcut değeri al
            values = self.sartlar_tree.item(item, "values")
            current_value = values[col_idx] if col_idx < len(values) else ""

            # Yıldız ve parantez içi efektif fiyatı temizle
            clean_value = str(current_value).replace("★", "").strip()
            if "(" in clean_value:
                clean_value = clean_value.split("(")[0].strip()

            # Hücre koordinatlarını al
            bbox = self.sartlar_tree.bbox(item, column)
            if not bbox:
                return

            x, y, width, height = bbox

            # Mevcut edit varsa kapat
            if self.sartlar_fiyat_edit["entry"]:
                self.sartlar_fiyat_edit["entry"].destroy()

            # Entry oluştur
            entry = tk.Entry(self.sartlar_tree, font=("Segoe UI", 9), justify="center")
            entry.place(x=x, y=y, width=width, height=height)
            entry.insert(0, clean_value.replace(",", "."))  # Virgülü noktaya çevir
            entry.select_range(0, tk.END)
            entry.focus_set()

            # Kaydet
            self.sartlar_fiyat_edit = {"entry": entry, "item": item, "column": col_idx}

            # Enter ve Escape bind
            entry.bind("<Return>", self._on_sartlar_fiyat_enter)
            entry.bind("<Escape>", self._on_sartlar_fiyat_escape)
            entry.bind("<FocusOut>", self._on_sartlar_fiyat_escape)

        except Exception as e:
            logger.error(f"Depo şartları çift tıklama hatası: {e}")

    def _on_sartlar_fiyat_escape(self, event):
        """Farmazon fiyat düzenleme iptal"""
        if self.sartlar_fiyat_edit["entry"]:
            self.sartlar_fiyat_edit["entry"].destroy()
            self.sartlar_fiyat_edit = {"entry": None, "item": None, "column": None}

    def _on_sartlar_fiyat_enter(self, event):
        """Farmazon fiyat düzenleme onay - optimum adet hesapla ve en karlıyı bul"""
        try:
            entry = self.sartlar_fiyat_edit["entry"]
            item = self.sartlar_fiyat_edit["item"]
            col_idx = self.sartlar_fiyat_edit["column"]

            if not entry or not item:
                return

            # Girilen fiyatı al
            new_value = entry.get().strip().replace(",", ".")
            try:
                yeni_fiyat = float(new_value)
            except ValueError:
                logger.warning(f"Geçersiz fiyat: {new_value}")
                self._on_sartlar_fiyat_escape(event)
                return

            # Entry'yi kapat
            entry.destroy()
            self.sartlar_fiyat_edit = {"entry": None, "item": None, "column": None}

            # Seçili ürün var mı?
            if not self.selected_product:
                logger.warning("Seçili ürün yok")
                return

            product_data = self.selected_product["data"]

            # Aylık satış ve ayarları al
            import os
            kargo_toplam = float(os.getenv("FARMAZON_KARGO", "140"))
            farmazon_max_ay = int(os.getenv("FARMAZON_MAX_AY", "6"))
            faiz_orani = float(os.getenv("FAIZ_ORANI", "3.5"))

            # Aylık satış
            aylik_satis = product_data.get("ort", 0)
            if aylik_satis <= 0:
                aylik_satis = 0.5  # Minimum değer

            # Vade aylarını hesapla
            vade_aylari = {}
            if self.controller:
                vade_aylari = self.controller._hesapla_vade_aylari()

            farmazon_vade = vade_aylari.get("farmazon", 0)

            # Max sipariş adedi
            max_siparis = max(1, int(aylik_satis * farmazon_max_ay))

            # Optimum adedi bul (en düşük efektif birim fiyat)
            en_iyi_adet = 1
            en_iyi_efektif = float('inf')

            for test_adet in range(1, max_siparis + 1):
                # Birim kargo
                birim_kargo = kargo_toplam / test_adet
                fiyat_kargo_dahil = yeni_fiyat + birim_kargo

                # Kaç ay stokta kalacak
                stok_suresi_ay = test_adet / aylik_satis if aylik_satis > 0 else farmazon_max_ay

                # Finansman maliyeti (bileşik faiz)
                # Ortalama stokta kalma süresi = stok_suresi_ay / 2
                ortalama_stok_suresi = stok_suresi_ay / 2
                toplam_bekleme = farmazon_vade + ortalama_stok_suresi

                # Aylık faiz oranı
                aylik_faiz = faiz_orani / 100
                finansman_carpani = (1 + aylik_faiz) ** toplam_bekleme

                efektif_birim = fiyat_kargo_dahil * finansman_carpani

                if efektif_birim < en_iyi_efektif:
                    en_iyi_efektif = efektif_birim
                    en_iyi_adet = test_adet

            logger.info(f"Farmazon manuel fiyat: {yeni_fiyat} TL, Optimum adet: {en_iyi_adet}, Efektif: {en_iyi_efektif:.2f} TL")

            # Şimdi tüm depolarla karşılaştır
            en_karli_sonuc = product_data.get("en_karli_sonuc", {})
            tum_secenekler = en_karli_sonuc.get("tum_secenekler", []) if en_karli_sonuc else []

            # Farmazon'u güncelle veya ekle
            farmazon_bulundu = False
            for s in tum_secenekler:
                if s.get("depo") == "farmazon":
                    s["efektif_birim"] = en_iyi_efektif
                    s["optimum_adet"] = en_iyi_adet
                    s["birim_fiyat"] = yeni_fiyat
                    s["manuel_fiyat"] = True
                    farmazon_bulundu = True
                    break

            if not farmazon_bulundu:
                tum_secenekler.append({
                    "depo": "farmazon",
                    "sart": "1",
                    "efektif_birim": en_iyi_efektif,
                    "optimum_adet": en_iyi_adet,
                    "birim_fiyat": yeni_fiyat,
                    "manuel_fiyat": True
                })

            # En karlıyı bul (en düşük efektif_birim)
            en_karli = None
            en_dusuk = float('inf')
            for s in tum_secenekler:
                efektif = s.get("efektif_birim", float('inf'))
                if efektif and efektif < en_dusuk:
                    en_dusuk = efektif
                    en_karli = s

            # En karlı kombinasyonları güncelle (5 kuruş tolerans)
            en_karliler = []
            for s in tum_secenekler:
                efektif = s.get("efektif_birim", float('inf'))
                if efektif and abs(efektif - en_dusuk) <= 0.05:
                    en_karliler.append(s)

            # Product data'yı güncelle
            if en_karli_sonuc:
                en_karli_sonuc["en_karli"] = en_karli
                en_karli_sonuc["en_karliler"] = en_karliler
                en_karli_sonuc["tum_secenekler"] = tum_secenekler
                if en_karli:
                    en_karli_sonuc["depo_adi"] = {
                        "farmazon": "Farmazon", "alliance": "Alliance", "selcuk": "Selçuk",
                        "yusufpasa": "Yusuf Paşa", "iskoop": "İskoop", "bursa": "BEK", "sancak": "Sancak"
                    }.get(en_karli.get("depo"), "")
                    en_karli_sonuc["depo_key"] = en_karli.get("depo")
            else:
                product_data["en_karli_sonuc"] = {
                    "en_karli": en_karli,
                    "en_karliler": en_karliler,
                    "tum_secenekler": tum_secenekler,
                    "depo_adi": "Farmazon" if en_karli and en_karli.get("depo") == "farmazon" else "",
                    "depo_key": en_karli.get("depo") if en_karli else ""
                }

            # Farmazon durum bilgisini güncelle
            farmazon_durum = product_data.get("farmazon_durum", {})
            if farmazon_durum:
                farmazon_durum["fiyat"] = yeni_fiyat
                farmazon_durum["manuel_fiyat"] = True
                # satis_kosullari varsa güncelle
                if farmazon_durum.get("satis_kosullari"):
                    for kosul in farmazon_durum["satis_kosullari"]:
                        kosul["birim_fiyat"] = yeni_fiyat

            # Tabloyu yeniden çiz
            self.update_sartlar_table(self.selected_product)

            # Ana tablodaki Depocu sütununu güncelle
            if en_karli:
                depo_adi = {
                    "farmazon": "Farmazon", "alliance": "Alliance", "selcuk": "Selçuk",
                    "yusufpasa": "Yusuf Paşa", "iskoop": "İskoop", "bursa": "BEK", "sancak": "Sancak"
                }.get(en_karli.get("depo"), "")

                item_id = self.selected_product.get("item_id")
                if item_id:
                    current_values = list(self.tree.item(item_id, "values"))
                    # Depocu sütunu index 2
                    if len(current_values) > 2:
                        current_values[2] = depo_adi[:10]
                        self.tree.item(item_id, values=current_values)

            # Botanik açıklamasını güncelle
            if self.controller and en_karli:
                aciklama_ozeti = self.controller._build_aciklama_efektif(product_data)
                product_data["aciklama_ozeti"] = aciklama_ozeti

                row = product_data.get("row")
                if row and aciklama_ozeti:
                    try:
                        self.controller.botanik.set_aciklama_value(row, aciklama_ozeti, skip_scroll=True)
                        logger.info(f"✓ Satır {row}: Açıklama güncellendi: {aciklama_ozeti}")
                    except Exception as e:
                        logger.error(f"Açıklama güncelleme hatası: {e}")

            logger.info(f"✓ Farmazon fiyat güncellendi: {yeni_fiyat} TL, Optimum: {en_iyi_adet} adet, En karlı: {en_karli.get('depo') if en_karli else 'Yok'}")

        except Exception as e:
            logger.error(f"Farmazon fiyat güncelleme hatası: {e}")
            import traceback
            traceback.print_exc()

    def update_days_calculation(self):
        """Kaç günde biteceğini hesapla ve güncelle"""
        try:
            if not self.selected_product:
                self.info_gun_label.config(text="-")
                return

            stok = self.selected_product["data"].get("stok", 0)
            siparis_adet = self.selected_product["data"].get("siparis_adet", 0)
            row_num = self.selected_product["data"].get("row")

            # CSV'den aylık ortalamayı al
            monthly_sales = self.controller.get_monthly_sales_from_csv(row_num)
            ort_str = monthly_sales.get("Ort", "0")

            # Virgülü noktaya çevir ve float'a parse et
            try:
                ort = float(ort_str.replace(",", ".")) if ort_str and ort_str != "-" else 0
            except:
                ort = 0

            if ort <= 0:
                self.info_gun_label.config(text="Gidiş yok")
                return

            # Hesapla: (Stok + Sipariş Adedi) * 30 / Aylık Ort
            toplam_ilaç = stok + siparis_adet
            gun = (toplam_ilaç * 30) / ort

            self.info_gun_label.config(text=f"{gun:.1f} gün")

        except Exception as e:
            logger.error(f"Gün hesaplama hatası: {e}")
            self.info_gun_label.config(text="-")

    def on_monthly_tree_double_click(self, event):
        """Alt tabloda çift tıklama - şimdilik kullanılmıyor (tüm tablo read-only)"""
        pass

    def on_info_siparis_double_click(self, event):
        """Info panelinde sipariş adedine çift tıklama - düzenleme başlat"""
        try:
            if not self.selected_product:
                return

            # Mevcut değer
            current_value = self.selected_product["data"].get("siparis_adet", 0)

            # Popup dialog
            from tkinter import simpledialog
            new_value = simpledialog.askinteger(
                "Sipariş Adedi Düzenle",
                "Yeni sipariş adedi:",
                initialvalue=current_value,
                minvalue=0,
                parent=self.root
            )

            if new_value is None:
                return  # İptal edildi

            # Değeri güncelle
            self.update_siparis_adet(new_value)

        except Exception as e:
            logger.error(f"Sipariş adedi düzenleme hatası: {e}")

    def update_siparis_adet(self, new_value):
        """Sipariş adedini güncelle (hem üst tabloda hem alt panelde)"""
        try:
            if not self.selected_product:
                return

            # Product data'da güncelle
            self.selected_product["data"]["siparis_adet"] = new_value

            # Üst tabloda güncelle
            item_id = self.selected_product["item_id"]
            values = list(self.tree.item(item_id, "values"))
            values[-1] = new_value  # Son sütun = Sipariş Adet
            self.tree.item(item_id, values=values)

            # Alt panelde güncelle
            self.info_siparis_label.config(text=str(new_value) if new_value else "-")

            # Günü yeniden hesapla
            self.update_days_calculation()

            logger.info(f"Sipariş adedi güncellendi: {new_value}")

        except Exception as e:
            logger.error(f"Sipariş adedi güncelleme hatası: {e}")

    def clear_scan_list(self):
        """Tarama listesini temizle (JSON, CSV ve GUI)"""
        from tkinter import messagebox
        try:
            # Onay iste
            result = messagebox.askyesno(
                "Listeyi Sil",
                "Tüm tarama verileri silinecek. Emin misiniz?",
                icon='warning'
            )

            if not result:
                return

            logger.info("🗑️ Tarama listesi temizleniyor...")

            # 1. Tabloyu temizle
            self.tree.delete(*self.tree.get_children())
            self.products = []

            # 2. Controller listesini temizle
            if self.controller:
                self.controller.products = []

                # 3. JSON dosyasını sil
                try:
                    if self.controller.scan_results_file.exists():
                        self.controller.scan_results_file.unlink()
                        logger.info("✓ Tarama JSON'u silindi")
                except Exception as e:
                    logger.warning(f"JSON silinemedi: {e}")

                # 4. CSV dosyalarını sil
                self.controller.clear_monthly_sales_csv()
                import os
                mf_enabled = os.getenv("MF_ENABLED", "true").lower() == "true"
                if mf_enabled:
                    self.controller.clear_mf_csv()

            # 5. Listeyi Sil butonu artık her zaman görünür

            # 6. "Hızlı Tarama" butonunu normale döndür
            self.fast_scan_button.config(text="⚡ Hızlı Tarama", bg="#FF6B00")

            # 7. Alt paneli temizle
            for item in self.monthly_tree.get_children():
                self.monthly_tree.delete(item)
            col_count = len(self.monthly_tree["columns"])
            self.monthly_tree.insert("", tk.END, values=["-"] * col_count)
            self.info_stok_label.config(text="-")
            self.info_siparis_label.config(text="-")
            self.info_gun_label.config(text="-")

            self.status_label.config(text="Liste temizlendi")
            logger.info("✓ Tarama listesi tamamen temizlendi")

        except Exception as e:
            logger.error(f"Liste temizleme hatası: {e}")
            messagebox.showerror("Hata", f"Liste temizlenirken hata: {e}")

    def check_botanik_on_startup(self):
        """Program açılışında Botanik EOS'a bağlanmayı dene (Sipariş penceresini kontrol et)"""
        try:
            if not self.controller or not self.controller.botanik:
                return

            logger.info("Program açılışında Botanik EOS kontrol ediliyor...")
            self.status_label.config(text="Botanik EOS kontrol ediliyor...")

            # Arka planda kontrol et (GUI donmasın)
            def check_in_background():
                try:
                    # Botanik EOS'a bağlanmayı dene
                    result = self.controller.botanik.connect()

                    if result:
                        # Başarılı - Sipariş penceresi açık veya açıldı
                        self.root.after(0, lambda: self.status_label.config(text="Hazır - Botanik EOS bağlı"))
                        logger.info("✓ Botanik EOS'a başarıyla bağlanıldı (Sipariş penceresi açık)")

                        # GUI penceresini en öne getir
                        import time
                        time.sleep(0.5)  # Sipariş penceresi tamamen açılsın
                        self.root.after(0, self.bring_to_front)
                    else:
                        # Başarısız - Botanik EOS açık değil veya Sipariş penceresi kapalı
                        self.root.after(0, lambda: self.status_label.config(text="Hazır - Botanik EOS'u açın"))
                        logger.warning("⚠ Botanik EOS bulunamadı veya Sipariş penceresi kapalı")

                        # Kullanıcıya uyarı göster
                        self.root.after(0, lambda: messagebox.showwarning(
                            "Botanik EOS Uyarısı",
                            "Botanik EOS programı açık değil veya Sipariş ekranı kapalı!\n\n"
                            "Lütfen:\n"
                            "1. Botanik EOS programını açın\n"
                            "2. 'Botanikte Sipariş' menüsünden Sipariş ekranını açın\n"
                            "3. 'Hızlı Tarama' butonuna basın\n\n"
                            "Not: Program, Hızlı Tarama başlattığınızda otomatik olarak\n"
                            "Sipariş ekranını açmayı deneyecektir."
                        ))
                except Exception as e:
                    logger.error(f"Botanik EOS kontrol hatası: {e}")
                    self.root.after(0, lambda: self.status_label.config(text="Hazır"))

            # Thread'de çalıştır
            import threading
            check_thread = threading.Thread(target=check_in_background, daemon=True)
            check_thread.start()

        except Exception as e:
            logger.error(f"Botanik startup kontrolü hatası: {e}")
            self.status_label.config(text="Hazır")

    def load_previous_scan_data(self):
        """Önceki tarama verilerini yükle (program açılışında)"""
        try:
            if not self.controller:
                return

            # Controller'dan önceki tarama sonuçlarını al
            products = self.controller.load_scan_results()

            if not products:
                logger.info("Önceki tarama verisi yok, boş ekranla başlanıyor")
                return

            logger.info(f"Önceki tarama yükleniyor: {len(products)} ürün")

            # Controller'ın products listesini güncelle
            self.controller.products = products.copy()

            # Her ürünü GUI'ye ekle
            for product in products:
                self.add_product_row(product)

            # "Hızlı Tarama" butonunu "Taramaya Devam Et" olarak değiştir
            self.fast_scan_button.config(text="⚡ Taramaya Devam Et", bg="#FF9800")

            # Listeyi Sil butonu zaten her zaman görünür

            self.status_label.config(text=f"Önceki tarama yüklendi - {len(products)} ürün (Devam edilebilir)")
            logger.info(f"✓ Önceki tarama başarıyla yüklendi: {len(products)} ürün")

        except Exception as e:
            logger.error(f"Önceki tarama yüklenirken hata: {e}")
            self.status_label.config(text="Önceki tarama yüklenemedi")

    def run(self):
        """GUI'yi çalıştır"""
        self.root.mainloop()
