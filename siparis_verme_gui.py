"""
Sipariş Verme Modülü GUI - v2
Stok hareket analizi bazlı sipariş hazırlama sistemi
Eşdeğer gruplu görünüm, manuel giriş, MF/Zam analizi
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import calendar
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from tkcalendar import DateEntry

logger = logging.getLogger(__name__)


class SiparisVermeGUI:
    """Sipariş Verme Modülü Penceresi - v2"""

    VARSAYILAN_URUN_TIPLERI = ['İLAÇ', 'PASİF İLAÇ', 'SERUMLAR']

    # Renkler
    RENK_GRUP_BASLIK = '#5C6BC0'  # İndigo
    RENK_GRUP_ICERIK = '#E8EAF6'  # Açık indigo
    RENK_ALT_TOPLAM = '#9FA8DA'   # Orta indigo
    RENK_SIPARIS_GEREK = '#FFCDD2'  # Açık kırmızı
    RENK_YETERLI = '#C8E6C9'       # Açık yeşil
    RENK_TEK_SATIR = '#FFFFFF'     # Beyaz

    def __init__(self, parent):
        self.parent = parent
        self.parent.title("Sipariş Verme Modülü")
        self.parent.geometry("1700x950")

        self.db = None
        self.tum_veriler = []           # Tüm işlenmiş veriler
        self.gorunen_veriler = []       # Filtrelenmiş görünen veriler
        self.kesin_siparis_listesi = [] # Kesinleşmiş siparişler
        self.secili_urun = None         # Detay paneli için seçili ürün

        # Parametre değişkenleri
        self.sene_sayisi = tk.IntVar(value=1)
        self.ay_sayisi = tk.IntVar(value=6)
        self.beklenen_zam_orani = tk.DoubleVar(value=0.0)

        # Checkbox değişkenleri
        self.hedef_tarih_aktif = tk.BooleanVar(value=False)
        self.min_stok_aktif = tk.BooleanVar(value=True)
        self.zam_aktif = tk.BooleanVar(value=False)
        self.yeterlileri_gizle = tk.BooleanVar(value=False)

        # Faiz parametreleri
        self.mevduat_faizi = tk.DoubleVar(value=45.0)  # Yıllık %
        self.kredi_faizi = tk.DoubleVar(value=55.0)    # Yıllık %
        self.faiz_turu = tk.StringVar(value="mevduat") # "mevduat" veya "kredi"
        self.depo_vadesi = tk.IntVar(value=75)         # Gün

        # Ürün tipi seçimi
        self.urun_tipi_vars = {}
        self.urun_tipleri_listesi = []

        # Dinamik sütunlar
        self.aktif_sutunlar = []
        self.aktif_basliklar = {}

        # Manuel giriş değerleri {urun_id: miktar}
        self.manuel_miktarlar = {}
        self.manuel_mf_girisler = {}  # {urun_id: "5+1"}

        self._arayuz_olustur()
        self._baglanti_kur()

    def _arayuz_olustur(self):
        """Ana arayüzü oluştur"""
        main_frame = ttk.Frame(self.parent, padding=3)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Üst panel - Parametreler (2 satır)
        self._parametre_panel_olustur(main_frame)

        # Orta bölüm - Ana DataGrid + Detay Paneli
        self._orta_bolum_olustur(main_frame)

        # Alt bölüm - Kesin Sipariş Listesi
        self._kesin_liste_olustur(main_frame)

        # Status bar
        self._status_bar_olustur(main_frame)

    def _parametre_panel_olustur(self, parent):
        """Parametre panelini oluştur - 3 satır okunabilir tasarım"""
        param_frame = tk.Frame(parent, bg='#ECEFF1', relief='raised', bd=1)
        param_frame.pack(fill=tk.X, pady=(0, 5))

        # ═══════════════════════════════════════════════════════════
        # SATIR 1: Veri Parametreleri
        # ═══════════════════════════════════════════════════════════
        row1 = tk.Frame(param_frame, bg='#ECEFF1')
        row1.pack(fill=tk.X, padx=10, pady=(8, 4))

        # Grup 1: Hareket Süresi
        grp1 = tk.LabelFrame(row1, text="Hareket Süresi", font=('Arial', 9, 'bold'),
                             bg='#E3F2FD', fg='#1565C0', padx=8, pady=4)
        grp1.pack(side=tk.LEFT, padx=(0, 10))

        sene_combo = ttk.Combobox(grp1, textvariable=self.sene_sayisi, width=4, state="readonly",
                                   font=('Arial', 10))
        sene_combo['values'] = [1, 2, 3]
        sene_combo.pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(grp1, text="yıl", font=('Arial', 10), bg='#E3F2FD').pack(side=tk.LEFT)

        # Grup 2: Aylık Gidiş Hesaplama
        grp2 = tk.LabelFrame(row1, text="Aylık Gidiş", font=('Arial', 9, 'bold'),
                             bg='#E3F2FD', fg='#1565C0', padx=8, pady=4)
        grp2.pack(side=tk.LEFT, padx=(0, 10))

        ay_combo = ttk.Combobox(grp2, textvariable=self.ay_sayisi, width=4, state="readonly",
                                 font=('Arial', 10))
        ay_combo['values'] = [3, 6, 9, 12]
        ay_combo.pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(grp2, text="ay ort.", font=('Arial', 10), bg='#E3F2FD').pack(side=tk.LEFT)

        # Grup 3: Ürün Tipi
        grp3 = tk.LabelFrame(row1, text="Ürün Tipi", font=('Arial', 9, 'bold'),
                             bg='#E3F2FD', fg='#1565C0', padx=8, pady=4)
        grp3.pack(side=tk.LEFT, padx=(0, 10))

        self.urun_tipi_menubutton = tk.Menubutton(
            grp3, text="Seçiniz...", relief=tk.RAISED, width=14, font=('Arial', 10), bg='white'
        )
        self.urun_tipi_menu = tk.Menu(self.urun_tipi_menubutton, tearoff=0, font=('Arial', 10))
        self.urun_tipi_menubutton["menu"] = self.urun_tipi_menu
        self.urun_tipi_menubutton.pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(grp3, text="Tümü", command=self._tum_tipleri_sec, font=('Arial', 9),
                  bg='#BBDEFB', width=5).pack(side=tk.LEFT, padx=2)
        tk.Button(grp3, text="Varsayılan", command=self._varsayilan_tipleri_sec, font=('Arial', 9),
                  bg='#BBDEFB', width=8).pack(side=tk.LEFT)

        # Grup 4: Hedef Tarih
        grp4 = tk.LabelFrame(row1, text="Hedef Tarih", font=('Arial', 9, 'bold'),
                             bg='#E8F5E9', fg='#2E7D32', padx=8, pady=4)
        grp4.pack(side=tk.LEFT, padx=(0, 10))

        self.hedef_check = tk.Checkbutton(
            grp4, text="Aktif", variable=self.hedef_tarih_aktif,
            bg='#E8F5E9', font=('Arial', 10), activebackground='#E8F5E9'
        )
        self.hedef_check.pack(side=tk.LEFT, padx=(0, 5))

        bugun = datetime.now()
        ay_son_gun = calendar.monthrange(bugun.year, bugun.month)[1]
        self.hedef_tarih_entry = DateEntry(
            grp4, width=11, background='#1976D2', foreground='white',
            borderwidth=1, date_pattern='yyyy-mm-dd', font=('Arial', 10),
            year=bugun.year, month=bugun.month, day=ay_son_gun
        )
        self.hedef_tarih_entry.pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(grp4, text="Ay Sonu", command=self._ay_sonu_sec, font=('Arial', 9),
                  bg='#A5D6A7', width=7).pack(side=tk.LEFT)

        # Sağda VERİLERİ GETİR butonu
        self.getir_btn = tk.Button(
            row1, text="VERİLERİ GETİR", command=self.verileri_getir,
            bg='#1976D2', fg='white', font=('Arial', 11, 'bold'),
            relief='raised', bd=2, padx=15, pady=5
        )
        self.getir_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # ═══════════════════════════════════════════════════════════
        # SATIR 2: Optimizasyon Parametreleri
        # ═══════════════════════════════════════════════════════════
        row2 = tk.Frame(param_frame, bg='#ECEFF1')
        row2.pack(fill=tk.X, padx=10, pady=4)

        # Grup 5: Zam Beklentisi
        grp5 = tk.LabelFrame(row2, text="Zam Beklentisi", font=('Arial', 9, 'bold'),
                             bg='#FFF3E0', fg='#E65100', padx=8, pady=4)
        grp5.pack(side=tk.LEFT, padx=(0, 10))

        self.zam_check = tk.Checkbutton(
            grp5, text="Aktif", variable=self.zam_aktif,
            bg='#FFF3E0', font=('Arial', 10), activebackground='#FFF3E0'
        )
        self.zam_check.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(grp5, text="Oran %", font=('Arial', 10), bg='#FFF3E0').pack(side=tk.LEFT)
        zam_entry = ttk.Entry(grp5, textvariable=self.beklenen_zam_orani, width=5, font=('Arial', 10))
        zam_entry.pack(side=tk.LEFT, padx=(3, 10))

        tk.Label(grp5, text="Tarih:", font=('Arial', 10), bg='#FFF3E0').pack(side=tk.LEFT)
        self.zam_tarih_entry = DateEntry(
            grp5, width=11, background='#E65100', foreground='white',
            borderwidth=1, date_pattern='yyyy-mm-dd', font=('Arial', 10)
        )
        self.zam_tarih_entry.pack(side=tk.LEFT, padx=(3, 0))

        # Grup 6: Min Stok
        grp6 = tk.LabelFrame(row2, text="Minimum Stok", font=('Arial', 9, 'bold'),
                             bg='#F3E5F5', fg='#7B1FA2', padx=8, pady=4)
        grp6.pack(side=tk.LEFT, padx=(0, 10))

        self.min_check = tk.Checkbutton(
            grp6, text="Dikkate Al", variable=self.min_stok_aktif,
            bg='#F3E5F5', font=('Arial', 10), activebackground='#F3E5F5'
        )
        self.min_check.pack(side=tk.LEFT)

        # Grup 7: Faiz Parametreleri
        grp7 = tk.LabelFrame(row2, text="Faiz Parametreleri", font=('Arial', 9, 'bold'),
                             bg='#E0F7FA', fg='#00838F', padx=8, pady=4)
        grp7.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(grp7, text="Mevduat %", font=('Arial', 10), bg='#E0F7FA').pack(side=tk.LEFT)
        mevduat_entry = ttk.Entry(grp7, textvariable=self.mevduat_faizi, width=5, font=('Arial', 10))
        mevduat_entry.pack(side=tk.LEFT, padx=(3, 10))

        tk.Label(grp7, text="Kredi %", font=('Arial', 10), bg='#E0F7FA').pack(side=tk.LEFT)
        kredi_entry = ttk.Entry(grp7, textvariable=self.kredi_faizi, width=5, font=('Arial', 10))
        kredi_entry.pack(side=tk.LEFT, padx=(3, 10))

        # Faiz türü seçimi
        tk.Radiobutton(
            grp7, text="Mevduat", variable=self.faiz_turu, value="mevduat",
            bg='#E0F7FA', font=('Arial', 10), activebackground='#E0F7FA'
        ).pack(side=tk.LEFT, padx=(5, 0))
        tk.Radiobutton(
            grp7, text="Kredi", variable=self.faiz_turu, value="kredi",
            bg='#E0F7FA', font=('Arial', 10), activebackground='#E0F7FA'
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(grp7, text="Vade (gün):", font=('Arial', 10), bg='#E0F7FA').pack(side=tk.LEFT)
        vade_entry = ttk.Entry(grp7, textvariable=self.depo_vadesi, width=4, font=('Arial', 10))
        vade_entry.pack(side=tk.LEFT, padx=(3, 0))

        # Sağda bilgi etiketi
        self.hesaplama_label = tk.Label(
            row2, text="", font=('Arial', 10, 'bold'), bg='#ECEFF1', fg='#1565C0'
        )
        self.hesaplama_label.pack(side=tk.RIGHT, padx=10)

        # ═══════════════════════════════════════════════════════════
        # SATIR 3: İşlem Butonları
        # ═══════════════════════════════════════════════════════════
        row3 = tk.Frame(param_frame, bg='#ECEFF1')
        row3.pack(fill=tk.X, padx=10, pady=(4, 8))

        # Yeterlileri Gizle Toggle
        self.gizle_btn = tk.Button(
            row3, text="Yeterlileri Gizle: KAPALI", command=self._toggle_yeterlileri_gizle,
            bg='#78909C', fg='white', font=('Arial', 10, 'bold'),
            relief='raised', bd=2, padx=12, pady=3
        )
        self.gizle_btn.pack(side=tk.LEFT, padx=(0, 15))

        # Toplu işlem butonları
        tk.Button(
            row3, text="Tüm Önerileri Manuel'e Kopyala", command=self._tum_onerileri_kopyala,
            bg='#7B1FA2', fg='white', font=('Arial', 10), relief='raised', bd=2, padx=10, pady=3
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            row3, text="Seçilileri Kesin Listeye Ekle", command=self._secilileri_kesin_listeye_ekle,
            bg='#388E3C', fg='white', font=('Arial', 10), relief='raised', bd=2, padx=10, pady=3
        ).pack(side=tk.LEFT, padx=(0, 10))

        # Excel butonu
        self.excel_btn = tk.Button(
            row3, text="EXCEL'E AKTAR", command=self.excel_aktar,
            bg='#FF6F00', fg='white', font=('Arial', 10, 'bold'),
            relief='raised', bd=2, padx=12, pady=3
        )
        self.excel_btn.pack(side=tk.RIGHT)

    def _orta_bolum_olustur(self, parent):
        """Orta bölüm - Ana DataGrid + Detay Paneli"""
        # PanedWindow ile bölünebilir
        self.orta_paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, sashwidth=4, bg='#90A4AE')
        self.orta_paned.pack(fill=tk.BOTH, expand=True, pady=(0, 3))

        # Sol: Ana DataGrid
        self._ana_grid_olustur()

        # Sağ: Detay Paneli
        self._detay_panel_olustur()

    def _ana_grid_olustur(self):
        """Ana DataGrid - gruplu görünüm (genişletilmiş)"""
        grid_frame = tk.Frame(self.orta_paned, bg='#FAFAFA', relief='sunken', bd=1)
        self.orta_paned.add(grid_frame, minsize=1000, width=1400)

        # Başlık
        header = tk.Frame(grid_frame, bg='#1976D2', height=26)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="📊 STOK VE SİPARİŞ ANALİZİ", bg='#1976D2', fg='white',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=10)

        # Treeview için frame
        tree_container = tk.Frame(grid_frame, bg='#FAFAFA')
        tree_container.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Sütun tanımları
        self.ana_sutunlar = [
            ("Tur", "", 25),
            ("UrunAdi", "Ürün Adı", 220),
            ("Stok", "Stok", 45),
            ("Min", "Min", 35),
            ("Sart1", "Şart1", 50),
            ("Sart2", "Şart2", 50),
            ("Sart3", "Şart3", 50),
        ]

        # Aylık sütunlar dinamik eklenecek
        self.aylik_sutunlar = []

        self.son_sutunlar = [
            ("AylikOrt", "Aylık", 55),
            ("GunlukOrt", "Gün", 45),
            ("AyBitis", "AyBitiş", 55),
            ("Oneri", "ÖNERİ", 65),
            ("OneriAy", "ÖneriAy", 60),
            ("YeniAyBitis", "YeniBitiş", 65),
            ("Manuel", "Manuel", 55),
            ("MF", "MF", 50),
        ]

        # Treeview
        self.ana_tree = ttk.Treeview(tree_container, show='headings', selectmode='extended')

        # Scrollbarlar
        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.ana_tree.yview)
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.ana_tree.xview)
        self.ana_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid yerleşimi
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        self.ana_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        # Treeview stil ayarları - daha büyük font
        style = ttk.Style()
        style.configure('Siparis.Treeview', font=('Arial', 10), rowheight=28)
        style.configure('Siparis.Treeview.Heading', font=('Arial', 10, 'bold'))
        self.ana_tree.configure(style='Siparis.Treeview')

        # Tag'ler - sipariş gerektiren satırlar bold ve vurgulu
        self.ana_tree.tag_configure('grup_baslik', background=self.RENK_GRUP_BASLIK, foreground='white',
                                     font=('Arial', 10, 'bold'))
        self.ana_tree.tag_configure('grup_satir', background=self.RENK_GRUP_ICERIK,
                                     font=('Arial', 10))
        self.ana_tree.tag_configure('grup_satir_siparis', background='#FFCDD2',
                                     font=('Arial', 11, 'bold'))
        self.ana_tree.tag_configure('alt_toplam', background=self.RENK_ALT_TOPLAM, foreground='#1A237E',
                                     font=('Arial', 10, 'bold'))
        self.ana_tree.tag_configure('tek_satir', background=self.RENK_TEK_SATIR,
                                     font=('Arial', 10))
        self.ana_tree.tag_configure('tek_satir_siparis', background='#FFCDD2',
                                     font=('Arial', 11, 'bold'))

        # Seçim olayı
        self.ana_tree.bind('<<TreeviewSelect>>', self._satir_secildi)
        self.ana_tree.bind('<Double-1>', self._satir_cift_tiklandi)

    def _detay_panel_olustur(self):
        """Sağ taraftaki detay paneli - daraltılmış"""
        detay_frame = tk.Frame(self.orta_paned, bg='#F5F5F5', relief='sunken', bd=1)
        self.orta_paned.add(detay_frame, minsize=220, width=280)

        # Başlık
        header = tk.Frame(detay_frame, bg='#5C6BC0', height=26)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="📝 İLAÇ DETAY", bg='#5C6BC0', fg='white',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=10)

        # İçerik
        self.detay_content = tk.Frame(detay_frame, bg='#F5F5F5')
        self.detay_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Placeholder
        self.detay_placeholder = tk.Label(
            self.detay_content,
            text="Detay görmek için\nbir ilaç satırı seçin",
            bg='#F5F5F5', fg='#9E9E9E', font=('Arial', 11, 'italic'),
            justify='center'
        )
        self.detay_placeholder.pack(expand=True)

    def _kesin_liste_olustur(self, parent):
        """Alt kısımdaki kesin sipariş listesi - depo bilgileri ile"""
        kesin_frame = tk.Frame(parent, bg='#FAFAFA', relief='sunken', bd=1, height=200)
        kesin_frame.pack(fill=tk.X, pady=(0, 3))
        kesin_frame.pack_propagate(False)

        # Başlık
        header = tk.Frame(kesin_frame, bg='#388E3C', height=30)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="✓ KESİNLEŞMİŞ SİPARİŞ LİSTESİ", bg='#388E3C', fg='white',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=10)

        # Depolarda Ara butonu
        self.depo_ara_btn = tk.Button(
            header, text="🔍 DEPOLARDA ARA", command=self._depolarda_ara,
            bg='#1565C0', fg='white', font=('Arial', 9, 'bold'), relief='raised', padx=10
        )
        self.depo_ara_btn.pack(side=tk.LEFT, padx=20, pady=2)

        # Durum etiketi
        self.depo_durum_label = tk.Label(header, text="", bg='#388E3C', fg='yellow',
                                          font=('Arial', 9))
        self.depo_durum_label.pack(side=tk.LEFT, padx=10)

        tk.Button(header, text="Listeyi Temizle", command=self._kesin_listeyi_temizle,
                 bg='#C62828', fg='white', font=('Arial', 8), relief='flat', padx=5
                 ).pack(side=tk.RIGHT, padx=5, pady=2)

        tk.Button(header, text="Excel'e Aktar", command=self._kesin_listeyi_excel_aktar,
                 bg='#FF6F00', fg='white', font=('Arial', 8), relief='flat', padx=5
                 ).pack(side=tk.RIGHT, padx=2, pady=2)

        # Treeview
        tree_frame = tk.Frame(kesin_frame, bg='#FAFAFA')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Depo sütunları ile genişletilmiş sütunlar
        columns = [
            ("UrunAdi", "Ürün Adı", 250),
            ("Barkod", "Barkod", 100),
            ("Miktar", "Miktar", 55),
            ("MF", "MF", 50),
            ("Toplam", "Toplam", 55),
            ("Selcuk", "Selçuk", 80),
            ("Alliance", "Alliance", 80),
            ("Sancak", "Sancak", 80),
            ("Iskoop", "İskoop", 80),
            ("Farmazon", "Farmazon", 80),
        ]

        self.kesin_tree = ttk.Treeview(tree_frame, columns=[c[0] for c in columns],
                                       show='headings', height=6)
        for col_id, baslik, width in columns:
            self.kesin_tree.heading(col_id, text=baslik)
            self.kesin_tree.column(col_id, width=width, minwidth=40)

        # Depo sütunları için renkli tag'ler
        self.kesin_tree.tag_configure('stok_var', background='#C8E6C9')  # Yeşil
        self.kesin_tree.tag_configure('stok_yok', background='#FFCDD2')  # Kırmızı
        self.kesin_tree.tag_configure('mf_var', background='#B3E5FC')    # Mavi

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.kesin_tree.yview)
        self.kesin_tree.configure(yscrollcommand=vsb.set)

        self.kesin_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    def _status_bar_olustur(self, parent):
        """Status bar"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X)

        self.status_label = ttk.Label(status_frame, text="Hazır", font=('Arial', 9))
        self.status_label.pack(side=tk.LEFT)

        self.kayit_label = ttk.Label(status_frame, text="", font=('Arial', 9))
        self.kayit_label.pack(side=tk.RIGHT)

    # ═══════════════════════════════════════════════════════════════════════
    # VERİTABANI İŞLEMLERİ
    # ═══════════════════════════════════════════════════════════════════════

    def _baglanti_kur(self):
        """Veritabanı bağlantısı kur"""
        try:
            from botanik_db import BotanikDB
            self.db = BotanikDB()
            if self.db.baglan():
                self.status_label.config(text="Veritabanı bağlantısı başarılı")
                self._urun_tiplerini_yukle()
            else:
                self.status_label.config(text="Veritabanı bağlantı hatası!")
        except Exception as e:
            logger.error(f"Veritabanı bağlantı hatası: {e}")
            self.status_label.config(text=f"Hata: {e}")

    def _urun_tiplerini_yukle(self):
        """Ürün tiplerini yükle"""
        try:
            if self.db:
                tipler = self.db.urun_tipleri_getir()
                self.urun_tipleri_listesi = [t['UrunTipAdi'] for t in tipler]

                self.urun_tipi_menu.delete(0, tk.END)
                self.urun_tipi_vars.clear()

                for tip_adi in self.urun_tipleri_listesi:
                    varsayilan = tip_adi in self.VARSAYILAN_URUN_TIPLERI
                    var = tk.BooleanVar(value=varsayilan)
                    self.urun_tipi_vars[tip_adi] = var
                    self.urun_tipi_menu.add_checkbutton(
                        label=tip_adi, variable=var,
                        command=self._urun_tipi_secim_guncelle
                    )
                self._urun_tipi_secim_guncelle()
        except Exception as e:
            logger.error(f"Ürün tipleri yükleme hatası: {e}")

    def _urun_tipi_secim_guncelle(self):
        """Seçili ürün tiplerini göster"""
        secili = [t for t, v in self.urun_tipi_vars.items() if v.get()]
        toplam = len(self.urun_tipi_vars)

        if len(secili) == 0:
            self.urun_tipi_menubutton.config(text="Hiçbiri")
        elif len(secili) == toplam:
            self.urun_tipi_menubutton.config(text="Tümü")
        elif len(secili) <= 2:
            self.urun_tipi_menubutton.config(text=", ".join(secili[:2]))
        else:
            self.urun_tipi_menubutton.config(text=f"{len(secili)} tip")

    def _tum_tipleri_sec(self):
        for v in self.urun_tipi_vars.values():
            v.set(True)
        self._urun_tipi_secim_guncelle()

    def _varsayilan_tipleri_sec(self):
        for t, v in self.urun_tipi_vars.items():
            v.set(t in self.VARSAYILAN_URUN_TIPLERI)
        self._urun_tipi_secim_guncelle()

    def _ay_sonu_sec(self):
        bugun = datetime.now()
        ay_son_gun = calendar.monthrange(bugun.year, bugun.month)[1]
        self.hedef_tarih_entry.set_date(date(bugun.year, bugun.month, ay_son_gun))

    def _aktif_faiz_getir(self):
        """Seçili faiz türüne göre aktif faiz oranını döndür"""
        if self.faiz_turu.get() == "mevduat":
            return self.mevduat_faizi.get()
        else:
            return self.kredi_faizi.get()

    def _depocu_fiyat_hesapla(self, psf, iskonto_kamu) -> float:
        """
        Depocu fiyatı (bize geliş fiyatı) hesapla.

        Formül: PSF × 0.71 × 1.10 × (1 - IskontoKamu/100)

        Args:
            psf: Perakende Satış Fiyatı (UrunFiyatEtiket)
            iskonto_kamu: Kamu iskonto yüzdesi (UrunIskontoKamu)

        Returns:
            Depocu fiyatı (KDV dahil, iskontolu)
        """
        # Decimal tipini float'a çevir
        psf = float(psf) if psf else 0
        iskonto_kamu = float(iskonto_kamu) if iskonto_kamu else 0

        if psf <= 0:
            return 0

        depocu_kdv_haric = psf * 0.71
        depocu_kdv_dahil = depocu_kdv_haric * 1.10
        depocu_iskontolu = depocu_kdv_dahil * (1 - iskonto_kamu / 100)

        return round(depocu_iskontolu, 2)

    # ═══════════════════════════════════════════════════════════════════════
    # NPV HESAPLAMA FONKSİYONLARI
    # ═══════════════════════════════════════════════════════════════════════

    def _npv_hesapla(self, alinan: int, mf: int, maliyet: float, aylik_ort: float,
                    faiz_yillik: float, depo_vade: int,
                    fatura_tarihi: date, zam_tarihi: date, zam_orani: float,
                    mevcut_stok: int = 0, kalan_gun: int = 15) -> tuple:
        """
        NPV hesaplama - MF'li vs MF'siz alım karşılaştırması

        Returns:
            (npv_mfsiz, npv_mfli, net_kazanc)
        """
        if alinan <= 0 or maliyet <= 0 or aylik_ort <= 0:
            return (0, 0, 0)

        aylik_faiz = (faiz_yillik / 100) / 12
        depo_vade_ay = depo_vade / 30

        toplam_gelen = alinan + (mf or 0)

        # İlk ay sarfı (kalan güne göre)
        gunluk_sarf = aylik_ort / 30
        ilk_ay_sarf = kalan_gun * gunluk_sarf

        # Zam ayı hesapla
        zam_ay_sonra = 999
        if zam_tarihi and fatura_tarihi and zam_orani > 0:
            if isinstance(fatura_tarihi, date):
                zam_ay_sonra = (zam_tarihi.year - fatura_tarihi.year) * 12 + \
                               (zam_tarihi.month - fatura_tarihi.month)

        # ===== MEVCUT STOK KAYBI HESAPLA =====
        npv_mevcut_ayri = 0
        kalan_mevcut = mevcut_stok
        ay = 0

        while kalan_mevcut > 0 and ay < 120:
            if ay == 0:
                bu_ay = min(ilk_ay_sarf, kalan_mevcut)
            else:
                bu_ay = min(aylik_ort, kalan_mevcut)

            if bu_ay > 0:
                if zam_orani > 0 and ay >= zam_ay_sonra:
                    fiyat = maliyet * (1 + zam_orani / 100)
                else:
                    fiyat = maliyet
                npv_mevcut_ayri += (bu_ay * fiyat) / ((1 + aylik_faiz) ** (ay + 1 + depo_vade_ay))
                kalan_mevcut -= bu_ay

            ay += 1

        npv_mevcut_toplu = mevcut_stok * maliyet
        mevcut_stok_kaybi = npv_mevcut_toplu - npv_mevcut_ayri

        # ===== YENİ ALIM NPV HESAPLAMASI =====
        # Senaryo A: MF'siz - her ay ihtiyaç kadar al
        npv_mfsiz = 0
        kalan_ihtiyac = toplam_gelen
        kalan_mevcut_sim = mevcut_stok
        ay = 0

        while kalan_ihtiyac > 0 and ay < 120:
            if ay == 0:
                bu_ay_sarf = ilk_ay_sarf
            else:
                bu_ay_sarf = aylik_ort

            # Önce mevcut stoktan harca
            mevcut_kullanim = min(kalan_mevcut_sim, bu_ay_sarf)
            kalan_mevcut_sim -= mevcut_kullanim

            # Kalan sarfı yeni alımdan karşıla
            yeni_kullanim = min(bu_ay_sarf - mevcut_kullanim, kalan_ihtiyac)

            if yeni_kullanim > 0:
                if zam_orani > 0 and ay >= zam_ay_sonra:
                    fiyat = maliyet * (1 + zam_orani / 100)
                else:
                    fiyat = maliyet

                odeme = yeni_kullanim * fiyat
                iskonto_faktor = (1 + aylik_faiz) ** (ay + 1 + depo_vade_ay)
                npv_mfsiz += odeme / iskonto_faktor

                kalan_ihtiyac -= yeni_kullanim

            ay += 1

        # Senaryo B: Toplu ödeme (MF'li) - sadece alınan kadar ödenir
        odenen_para = alinan * maliyet
        npv_mfli = odenen_para / ((1 + aylik_faiz) ** (1 + depo_vade_ay))

        # Net kazanç
        yeni_alim_kazanc = npv_mfsiz - npv_mfli
        net_kazanc = yeni_alim_kazanc - mevcut_stok_kaybi

        return (round(npv_mfsiz, 2), round(npv_mfli, 2), round(net_kazanc, 2))

    def _zam_oncesi_optimum_hesapla(self, maliyet: float, aylik_ort: float,
                                     mevcut_stok: int, zam_tarihi: date, zam_orani: float,
                                     faiz_yillik: float, depo_vade: int) -> dict:
        """
        Zam öncesi optimum alım miktarını hesapla.

        Mantık: Belli bir süre boyunca harcanacak miktarlar için
        aylık mı yoksa toplu mu almak daha avantajlı?
        Her iki senaryonun NPV'sini (bugünkü değer) hesapla ve karşılaştır.

        Karar Noktaları:
        - verimlilik: Maksimum ROI (Kazanç/Yatırım) noktası
        - pareto: %80 kazanca ulaşılan nokta (Pareto prensibi)
        - optimum: Maksimum mutlak kazanç noktası (Pik)
        - maksimum: Karlılığın sıfıra düştüğü nokta (Sınır)

        Returns:
            {
                'verimlilik': int,        # Maksimum ROI noktası
                'verimlilik_roi': float,  # ROI yüzdesi
                'verimlilik_kazanc': float,
                'pareto': int,            # %80 kazanç noktası
                'pareto_kazanc': float,
                'optimum': int,           # Maksimum kazanç noktası
                'kazanc_optimum': float,
                'maksimum': int,          # Sınır (karlılık sıfır)
                'kazanc_maksimum': float
            }
        """
        bos_sonuc = {
            'verimlilik': 0, 'verimlilik_roi': 0, 'verimlilik_kazanc': 0,
            'pareto': 0, 'pareto_kazanc': 0,
            'optimum': 0, 'kazanc_optimum': 0,
            'maksimum': 0, 'kazanc_maksimum': 0
        }

        if not zam_tarihi or zam_orani <= 0 or aylik_ort <= 0:
            return bos_sonuc

        bugun = date.today()
        zam_gun = (zam_tarihi - bugun).days
        if zam_gun <= 0:
            return bos_sonuc

        # Gün bazlı faiz hesabı (smooth hesaplama için)
        aylik_faiz = (faiz_yillik / 100) / 12
        gunluk_faiz = (1 + aylik_faiz) ** (1/30) - 1
        gunluk_sarf = aylik_ort / 30

        # 12 aya kadar test et
        max_test = int(aylik_ort * 12)
        if max_test < 10:
            max_test = 100

        # Tüm miktarlar için kazanç hesapla
        kazanclar = []
        for test_miktar in range(0, max_test + 1):
            if test_miktar == 0:
                kazanclar.append(0)
                continue

            kalan_mevcut = mevcut_stok
            kalan_yeni = test_miktar
            npv_aylik = 0

            gun = 0
            while kalan_yeni > 0 and gun < 720:
                harcanan = gunluk_sarf
                mevcut_harcanan = min(kalan_mevcut, harcanan)
                kalan_mevcut -= mevcut_harcanan
                yeni_harcanan = min(harcanan - mevcut_harcanan, kalan_yeni)

                if yeni_harcanan > 0:
                    if gun < zam_gun:
                        fiyat = maliyet
                    else:
                        fiyat = maliyet * (1 + zam_orani / 100)

                    # Gün bazlı iskonto
                    odeme_gun = gun + 30 + depo_vade
                    odeme = yeni_harcanan * fiyat
                    iskonto = (1 + gunluk_faiz) ** odeme_gun
                    npv_aylik += odeme / iskonto
                    kalan_yeni -= yeni_harcanan
                gun += 1

            # Toplu alım NPV
            npv_toplu = (test_miktar * maliyet) / ((1 + gunluk_faiz) ** (30 + depo_vade))
            kazanc = npv_aylik - npv_toplu
            kazanclar.append(kazanc)

        # ===== KARAR NOKTALARI =====

        # 1. OPTİMUM (Pik) - Maksimum kazanç
        optimum_miktar = 0
        en_iyi_kazanc = 0
        for i, k in enumerate(kazanclar):
            if k > en_iyi_kazanc:
                en_iyi_kazanc = k
                optimum_miktar = i

        # 2. MAKSİMUM (Sınır) - Son pozitif kazanç noktası
        maksimum_miktar = 0
        for i, k in enumerate(kazanclar):
            if k > 0:
                maksimum_miktar = i

        # 3. PARETO (%80) - %80 kazanca ulaşılan ilk nokta
        hedef_80 = en_iyi_kazanc * 0.80
        pareto_miktar = 0
        pareto_kazanc = 0
        for i, k in enumerate(kazanclar):
            if k >= hedef_80:
                pareto_miktar = i
                pareto_kazanc = k
                break

        # 4. VERİMLİLİK (Max ROI) - Kazanç/Yatırım maksimum
        verimlilik_miktar = 0
        verimlilik_roi = 0
        verimlilik_kazanc = 0
        for i, k in enumerate(kazanclar):
            if i > 0 and k > 0:
                yatirim = i * maliyet
                roi = (k / yatirim) * 100
                if roi > verimlilik_roi:
                    verimlilik_roi = roi
                    verimlilik_miktar = i
                    verimlilik_kazanc = k

        return {
            'verimlilik': verimlilik_miktar,
            'verimlilik_roi': round(verimlilik_roi, 1),
            'verimlilik_kazanc': round(verimlilik_kazanc, 2),
            'pareto': pareto_miktar,
            'pareto_kazanc': round(pareto_kazanc, 2),
            'optimum': optimum_miktar,
            'kazanc_optimum': round(en_iyi_kazanc, 2),
            'maksimum': maksimum_miktar,
            'kazanc_maksimum': round(kazanclar[maksimum_miktar] if maksimum_miktar > 0 else 0, 2)
        }

    def _mf_optimum_hesapla(self, mf_sart: str, maliyet: float, aylik_ort: float,
                            mevcut_stok: int, faiz_yillik: float, depo_vade: int,
                            hedef_gun: int) -> dict:
        """
        MF şartına göre optimum alım miktarını hesapla.

        Örnek: 5+1 şartı için:
        - 5 al 1 bedava = 6 ürün için 5 ürün parası
        - Ama 6 ay stok tutmak faiz maliyeti
        - Hangisi karlı?

        Returns:
            {
                'mfli_al': bool,       # MF'li almak karlı mı?
                'alinan': int,         # Alınacak miktar
                'bedava': int,         # Bedava gelecek
                'toplam': int,         # Toplam stok
                'kazanc': float,       # Net kazanç/kayıp
                'oneri': str           # "5+1 al" veya "2+0 al (MF'siz)"
            }
        """
        if not mf_sart or '+' not in mf_sart:
            return {'mfli_al': False, 'alinan': 0, 'bedava': 0, 'toplam': 0, 'kazanc': 0, 'oneri': ''}

        try:
            parcalar = mf_sart.split('+')
            mf_alinan = int(parcalar[0])
            mf_bedava = int(parcalar[1])
        except:
            return {'mfli_al': False, 'alinan': 0, 'bedava': 0, 'toplam': 0, 'kazanc': 0, 'oneri': ''}

        if mf_alinan <= 0 or mf_bedava <= 0 or maliyet <= 0 or aylik_ort <= 0:
            return {'mfli_al': False, 'alinan': 0, 'bedava': 0, 'toplam': 0, 'kazanc': 0, 'oneri': ''}

        gunluk_sarf = aylik_ort / 30
        hedef_ihtiyac = max(0, int(gunluk_sarf * hedef_gun) - mevcut_stok)

        # Hedef ihtiyacı karşılayacak MF'siz miktar
        mfsiz_miktar = hedef_ihtiyac

        # MF'li alım için kaç set gerekiyor?
        mf_toplam = mf_alinan + mf_bedava
        set_sayisi = max(1, (hedef_ihtiyac + mf_toplam - 1) // mf_toplam)
        mfli_alinan = set_sayisi * mf_alinan
        mfli_bedava = set_sayisi * mf_bedava
        mfli_toplam = mfli_alinan + mfli_bedava

        # NPV karşılaştırması
        bugun = date.today()
        kalan_gun = hedef_gun

        # MF'siz NPV
        npv_mfsiz, _, _ = self._npv_hesapla(
            alinan=mfsiz_miktar, mf=0, maliyet=maliyet, aylik_ort=aylik_ort,
            faiz_yillik=faiz_yillik, depo_vade=depo_vade,
            fatura_tarihi=bugun, zam_tarihi=None, zam_orani=0,
            mevcut_stok=mevcut_stok, kalan_gun=kalan_gun
        )

        # MF'li NPV
        _, npv_mfli, _ = self._npv_hesapla(
            alinan=mfli_alinan, mf=mfli_bedava, maliyet=maliyet, aylik_ort=aylik_ort,
            faiz_yillik=faiz_yillik, depo_vade=depo_vade,
            fatura_tarihi=bugun, zam_tarihi=None, zam_orani=0,
            mevcut_stok=mevcut_stok, kalan_gun=kalan_gun
        )

        # Kazanç hesapla (pozitif = MF'li karlı)
        kazanc = npv_mfsiz - npv_mfli

        if kazanc > 0:
            return {
                'mfli_al': True,
                'alinan': mfli_alinan,
                'bedava': mfli_bedava,
                'toplam': mfli_toplam,
                'kazanc': round(kazanc, 2),
                'oneri': f"{mfli_alinan}+{mfli_bedava} al ({kazanc:.0f}₺ karlı)"
            }
        else:
            return {
                'mfli_al': False,
                'alinan': mfsiz_miktar,
                'bedava': 0,
                'toplam': mfsiz_miktar,
                'kazanc': round(kazanc, 2),
                'oneri': f"{mfsiz_miktar}+0 al (MF'siz daha karlı)"
            }

    def _hedef_gun_hesapla(self):
        """Hedef tarihe kalan gün sayısı"""
        try:
            if self.hedef_tarih_aktif.get():
                hedef = self.hedef_tarih_entry.get_date()
            else:
                # Ay sonu
                bugun = datetime.now()
                ay_son_gun = calendar.monthrange(bugun.year, bugun.month)[1]
                hedef = date(bugun.year, bugun.month, ay_son_gun)

            bugun = date.today()
            fark = (hedef - bugun).days
            return max(0, fark)
        except:
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # VERİ GETİRME
    # ═══════════════════════════════════════════════════════════════════════

    def verileri_getir(self):
        """Veritabanından verileri getir"""
        secili_tipler = [t for t, v in self.urun_tipi_vars.items() if v.get()]

        if not secili_tipler:
            messagebox.showwarning("Uyarı", "En az bir ürün tipi seçmelisiniz!")
            return

        self.status_label.config(text="Veriler getiriliyor...")
        self.parent.update()

        def sorgu_thread():
            try:
                from botanik_db import BotanikDB
                db = BotanikDB()
                if not db.baglan():
                    self.parent.after(0, lambda: messagebox.showerror("Hata", "Veritabanına bağlanılamadı!"))
                    return

                sene = self.sene_sayisi.get()
                ay = self.ay_sayisi.get()

                # Ana verileri getir
                veriler = self._verileri_getir_sql(db, sene, ay, secili_tipler)

                # MF şartlarını getir
                mf_sartlari = self._mf_sartlari_getir(db)

                db.kapat()

                # Verileri işle
                islenenmis = self._verileri_isle(veriler, mf_sartlari, ay)

                self.parent.after(0, lambda: self._veriler_yuklendi(islenenmis, ay))

            except Exception as e:
                logger.error(f"Sorgu hatası: {e}")
                import traceback
                traceback.print_exc()
                self.parent.after(0, lambda: self._sorgu_hatasi(str(e)))

        thread = threading.Thread(target=sorgu_thread)
        thread.start()

    def _verileri_getir_sql(self, db, sene_sayisi, ay_sayisi, urun_tipleri):
        """SQL sorgusu - X sene hareket görmüş + Y ay aylık dağılım"""
        bugun = datetime.now()

        # X sene içinde hareket görmüş ürünler için
        hareket_baslangic = (bugun - relativedelta(years=sene_sayisi)).strftime('%Y-%m-%d')

        # Y ay için aylık dağılım
        aylik_baslangic = (bugun - relativedelta(months=ay_sayisi)).replace(day=1).strftime('%Y-%m-%d')

        tipler_sql = ', '.join([f"'{t}'" for t in urun_tipleri])

        # Aylık CASE ifadeleri
        aylik_cases = []
        for i in range(ay_sayisi):
            ay_tarihi = bugun - relativedelta(months=i)
            ay_basi = ay_tarihi.replace(day=1)
            if i == 0:
                ay_sonu = bugun
            else:
                ay_sonu = (ay_basi + relativedelta(months=1)) - relativedelta(days=1)

            baslangic_str = ay_basi.strftime('%Y-%m-%d')
            bitis_str = ay_sonu.strftime('%Y-%m-%d')

            aylik_cases.append(f"""
                SUM(CASE WHEN Tarih >= '{baslangic_str}' AND Tarih <= '{bitis_str}' THEN Adet ELSE 0 END) as Ay_{i}
            """)

        aylik_kolonlar = ",\n".join(aylik_cases)

        sql = f"""
        ;WITH HareketliUrunler AS (
            -- Son X sene içinde hareket görmüş ürünler
            SELECT DISTINCT ri.RIUrunId as UrunId
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
            AND ra.RxKayitTarihi >= '{hareket_baslangic}'

            UNION

            SELECT DISTINCT ei.RIUrunId as UrunId
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
            AND ea.RxKayitTarihi >= '{hareket_baslangic}'
        ),
        CikisVerileri AS (
            SELECT ri.RIUrunId as UrunId, ri.RIAdet as Adet, CAST(ra.RxKayitTarihi as date) as Tarih
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
            AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
            AND ra.RxKayitTarihi >= '{aylik_baslangic}'

            UNION ALL

            SELECT ei.RIUrunId as UrunId, ei.RIAdet as Adet, CAST(ea.RxKayitTarihi as date) as Tarih
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
            AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
            AND ea.RxKayitTarihi >= '{aylik_baslangic}'
        ),
        UrunAylikOzet AS (
            SELECT UrunId, SUM(Adet) as ToplamCikis,
                {aylik_kolonlar}
            FROM CikisVerileri
            GROUP BY UrunId
        )

        SELECT
            u.UrunId,
            u.UrunAdi,
            COALESCE(ut.UrunTipAdi, 'Belirsiz') as UrunTipi,
            u.UrunEsdegerId as EsdegerId,
            -- Stok: Sadece İLAÇ(1) ve PASİF İLAÇ(16) için Karekod, diğerleri için EskiStok
            CASE
                WHEN u.UrunUrunTipId IN (1, 16) THEN
                    (SELECT COUNT(*) FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1)
                ELSE
                    (COALESCE(u.UrunStokDepo,0) + COALESCE(u.UrunStokRaf,0) + COALESCE(u.UrunStokAcik,0))
            END as Stok,
            COALESCE(u.UrunMinimum, 0) as MinStok,
            COALESCE(ao.ToplamCikis, 0) as ToplamCikis,
            -- Fiyat bilgileri (Depocu fiyat hesaplaması için)
            COALESCE(u.UrunFiyatEtiket, 0) as PSF,
            COALESCE(u.UrunIskontoKamu, 0) as IskontoKamu,
            -- Barkod (Barkod tablosundan ilk kayıt)
            (SELECT TOP 1 b.BarkodAdi FROM Barkod b WHERE b.BarkodUrunId = u.UrunId AND b.BarkodSilme = 0) as Barkod,
            {', '.join([f'COALESCE(ao.Ay_{i}, 0) as Ay_{i}' for i in range(ay_sayisi)])}
        FROM Urun u
        INNER JOIN HareketliUrunler hu ON u.UrunId = hu.UrunId
        LEFT JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
        LEFT JOIN UrunAylikOzet ao ON u.UrunId = ao.UrunId
        WHERE u.UrunSilme = 0
        AND ut.UrunTipAdi IN ({tipler_sql})
        ORDER BY u.UrunEsdegerId, u.UrunAdi
        """

        return db.sorgu_calistir(sql)

    def _mf_sartlari_getir(self, db):
        """Son 1 yılda alınan MF şartlarını getir (5+1 formatında)"""
        bugun = datetime.now()
        baslangic = (bugun - relativedelta(years=1)).strftime('%Y-%m-%d')

        sql = f"""
        SELECT
            fs.FSUrunId as UrunId,
            CAST(fs.FSUrunAdet as int) as Adet,
            CAST(fs.FSUrunMf as int) as MF,
            fg.FGFaturaTarihi as Tarih
        FROM FaturaSatir fs
        JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
        WHERE fg.FGSilme = 0
        AND fg.FGFaturaTarihi >= '{baslangic}'
        AND fs.FSUrunMf > 0
        ORDER BY fs.FSUrunId, fg.FGFaturaTarihi DESC
        """

        sonuclar = db.sorgu_calistir(sql)

        # Her ürün için en fazla 3 farklı şart
        mf_sartlari = {}
        for row in sonuclar:
            urun_id = row['UrunId']
            adet = row['Adet'] or 0
            mf = row['MF'] or 0

            if mf > 0:
                sart = f"{adet}+{mf}"
                if urun_id not in mf_sartlari:
                    mf_sartlari[urun_id] = []

                # Aynı şart yoksa ekle
                if sart not in mf_sartlari[urun_id] and len(mf_sartlari[urun_id]) < 3:
                    mf_sartlari[urun_id].append(sart)

        return mf_sartlari

    def _verileri_isle(self, veriler, mf_sartlari, ay_sayisi):
        """Verileri işle ve hesapla"""
        if not veriler:
            return []

        hedef_gun = self._hedef_gun_hesapla()
        min_stok_aktif = self.min_stok_aktif.get()
        zam_aktif = self.zam_aktif.get()
        zam_orani = self.beklenen_zam_orani.get() / 100 if zam_aktif else 0

        islenenmis = []

        for veri in veriler:
            urun_id = veri.get('UrunId')
            stok = veri.get('Stok', 0) or 0
            min_stok = veri.get('MinStok', 0) or 0
            toplam_cikis = veri.get('ToplamCikis', 0) or 0

            # Fiyat bilgileri
            psf = veri.get('PSF', 0) or 0
            iskonto_kamu = veri.get('IskontoKamu', 0) or 0
            depocu_fiyat = self._depocu_fiyat_hesapla(psf, iskonto_kamu)

            # Aylık ve günlük ortalama
            aylik_ort = toplam_cikis / ay_sayisi if ay_sayisi > 0 else 0
            gunluk_ort = aylik_ort / 30

            # Ay bitiş (stok kaç ay yeter)
            # KURAL 1: Stok=0 → Ay Bitiş=0 (stok yok)
            # KURAL 2: Stok>0 ve Gidiş=0 → Ay Bitiş=999 (sonsuz stok)
            # KURAL 3: Stok>0 ve Gidiş>0 → Normal hesaplama
            if stok == 0:
                ay_bitis = 0
            elif aylik_ort == 0:
                ay_bitis = 999  # Stok var ama gidiş yok = sonsuz
            else:
                ay_bitis = stok / aylik_ort

            # Temel ihtiyaç = hedef güne kadar gereken
            temel_ihtiyac = gunluk_ort * hedef_gun

            # Sipariş önerisi hesaplama
            oneri = max(0, temel_ihtiyac - stok)

            # Minimum stok kontrolü
            if min_stok_aktif and min_stok > 0 and stok < min_stok:
                min_eksik = min_stok - stok
                oneri = max(oneri, min_eksik)

            # Zam analizi (NPV bazlı)
            zam_oneri = None
            if zam_aktif and zam_orani > 0 and depocu_fiyat > 0:
                try:
                    zam_tarihi = self.zam_tarih_entry.get_date()
                    faiz = self._aktif_faiz_getir()
                    vade = self.depo_vadesi.get()

                    zam_oneri = self._zam_oncesi_optimum_hesapla(
                        maliyet=depocu_fiyat,
                        aylik_ort=aylik_ort,
                        mevcut_stok=stok,
                        zam_tarihi=zam_tarihi,
                        zam_orani=zam_orani * 100,  # Yüzde olarak
                        faiz_yillik=faiz,
                        depo_vade=vade
                    )

                    if zam_oneri and zam_oneri['pareto'] > 0:
                        # Pareto noktasını kullan (%80 kazanç, daha verimli sermaye kullanımı)
                        zam_bazli_oneri = max(0, zam_oneri['pareto'] - stok)
                        oneri = max(oneri, zam_bazli_oneri)
                except Exception as e:
                    logger.warning(f"Zam hesaplama hatası: {e}")

            # MF şartları
            sartlar = mf_sartlari.get(urun_id, [])

            esdeger_id = veri.get('EsdegerId')

            # Öneri kaç aylık stok?
            oneri_int = int(round(oneri, 0))
            if aylik_ort > 0:
                oneri_ay = oneri_int / aylik_ort
                yeni_ay_bitis = (stok + oneri_int) / aylik_ort
            else:
                oneri_ay = 0 if oneri_int == 0 else 999
                yeni_ay_bitis = 999 if stok > 0 or oneri_int > 0 else 0

            satir = {
                'UrunId': urun_id,
                'UrunAdi': veri.get('UrunAdi', ''),
                'UrunTipi': veri.get('UrunTipi', ''),
                'EsdegerId': esdeger_id,
                'Barkod': veri.get('Barkod', ''),
                'Stok': stok,
                'MinStok': min_stok,
                'ToplamCikis': toplam_cikis,
                'AylikOrt': round(aylik_ort, 1),
                'GunlukOrt': round(gunluk_ort, 2),
                'AyBitis': round(ay_bitis, 1) if ay_bitis < 100 else "∞",
                'HedefGun': hedef_gun,
                'Oneri': oneri_int,
                'OneriAy': round(oneri_ay, 1) if oneri_ay < 100 else "∞",
                'YeniAyBitis': round(yeni_ay_bitis, 1) if yeni_ay_bitis < 100 else "∞",
                'Manuel': self.manuel_miktarlar.get(urun_id, 0),
                'MF': self.manuel_mf_girisler.get(urun_id, ''),
                'Sart1': sartlar[0] if len(sartlar) > 0 else '',
                'Sart2': sartlar[1] if len(sartlar) > 1 else '',
                'Sart3': sartlar[2] if len(sartlar) > 2 else '',
                'ZamOneri': zam_oneri,  # Zam optimizasyon bilgisi
                'DepocuFiyat': depocu_fiyat,  # Bize geliş fiyatı
                'PSF': psf,  # Perakende satış fiyatı
            }

            # Aylık verileri ekle
            for i in range(ay_sayisi):
                satir[f'Ay_{i}'] = veri.get(f'Ay_{i}', 0) or 0

            islenenmis.append(satir)

        return islenenmis

    def _veriler_yuklendi(self, veriler, ay_sayisi):
        """Veriler yüklendiğinde UI güncelle"""
        self.tum_veriler = veriler

        # Sütunları güncelle
        self._sutunlari_guncelle(ay_sayisi)

        # Filtreleme uygula ve tabloyu güncelle
        self._filtreleme_uygula()

        # Bilgi güncelle
        hedef_gun = self._hedef_gun_hesapla()
        siparis_gereken = len([v for v in veriler if v.get('Oneri', 0) > 0])
        aktif_faiz = self._aktif_faiz_getir()
        faiz_tur = "M" if self.faiz_turu.get() == "mevduat" else "K"
        self.hesaplama_label.config(
            text=f"Hedef: {hedef_gun} gün | Faiz: %{aktif_faiz:.0f}({faiz_tur}) | {len(veriler)} ürün | {siparis_gereken} sipariş gerekli"
        )

        self.status_label.config(text="Veriler yüklendi")
        self.kayit_label.config(text=f"{len(veriler)} kayıt")

    def _sutunlari_guncelle(self, ay_sayisi):
        """Sütunları dinamik güncelle"""
        # Aylık sütunları oluştur
        bugun = datetime.now()
        self.aylik_sutunlar = []
        for i in range(ay_sayisi - 1, -1, -1):
            ay_tarihi = bugun - relativedelta(months=i)
            ay_adi = ay_tarihi.strftime('%b')[:3]
            self.aylik_sutunlar.append((f"Ay_{i}", ay_adi, 40))

        # Tüm sütunları birleştir
        tum_sutunlar = self.ana_sutunlar + self.aylik_sutunlar + self.son_sutunlar

        col_ids = [c[0] for c in tum_sutunlar]
        self.ana_tree['columns'] = col_ids

        for col_id, baslik, width in tum_sutunlar:
            self.ana_tree.heading(col_id, text=baslik)
            self.ana_tree.column(col_id, width=width, minwidth=25)

        self.aktif_sutunlar = tum_sutunlar

    def _filtreleme_uygula(self):
        """Yeterlileri gizle filtresini uygula ve tabloyu güncelle"""
        if not self.tum_veriler:
            self.gorunen_veriler = []
            self._tabloyu_guncelle()
            return

        if not self.yeterlileri_gizle.get():
            self.gorunen_veriler = self.tum_veriler
        else:
            # Eşdeğer gruplarını analiz et
            esdeger_gruplari = {}
            for veri in self.tum_veriler:
                eid = veri.get('EsdegerId') or 0
                if eid not in esdeger_gruplari:
                    esdeger_gruplari[eid] = []
                esdeger_gruplari[eid].append(veri)

            # Filtreleme
            gorunen = []
            for eid, urunler in esdeger_gruplari.items():
                grup_siparis_var = any(u.get('Oneri', 0) > 0 for u in urunler)

                if eid == 0:
                    # Eşdeğersiz - sadece sipariş gerekenleri göster
                    for u in urunler:
                        if u.get('Oneri', 0) > 0:
                            gorunen.append(u)
                else:
                    # Eşdeğerli grup - grupta herhangi biri sipariş gerektiriyorsa tümünü göster
                    if grup_siparis_var:
                        gorunen.extend(urunler)

            self.gorunen_veriler = gorunen

        self._tabloyu_guncelle()

    def _tabloyu_guncelle(self):
        """Ana tabloyu gruplu şekilde güncelle"""
        # Mevcut satırları temizle
        for item in self.ana_tree.get_children():
            self.ana_tree.delete(item)

        if not self.gorunen_veriler:
            return

        # Eşdeğer gruplarına ayır
        esdeger_gruplari = {}
        for veri in self.gorunen_veriler:
            eid = veri.get('EsdegerId') or 0
            if eid not in esdeger_gruplari:
                esdeger_gruplari[eid] = []
            esdeger_gruplari[eid].append(veri)

        # Grupları sırala (eşdeğersizler sona)
        sirali_gruplar = sorted(esdeger_gruplari.items(), key=lambda x: (x[0] == 0, x[0]))

        for eid, urunler in sirali_gruplar:
            if eid == 0:
                # Eşdeğersiz - tek satırlar
                for urun in urunler:
                    self._tek_satir_ekle(urun)
            elif len(urunler) == 1:
                # Tek ürünlü grup - tek satır olarak göster
                self._tek_satir_ekle(urunler[0])
            else:
                # Çoklu eşdeğer grubu
                self._grup_ekle(eid, urunler)

    def _grup_ekle(self, esdeger_id, urunler):
        """Eşdeğer grubu ekle - başlık + satırlar + alt toplam"""
        # Grup özet bilgileri
        grup_stok = sum(u.get('Stok', 0) for u in urunler)
        grup_oneri = sum(u.get('Oneri', 0) for u in urunler)
        grup_aylik = sum(u.get('AylikOrt', 0) for u in urunler)

        # Grup başlık satırı
        baslik_values = ['═'] + [f"══ GRUP #{esdeger_id} ══"] + [''] * (len(self.aktif_sutunlar) - 2)
        self.ana_tree.insert('', 'end', values=baslik_values, tags=('grup_baslik',))

        # Grup üyeleri
        for urun in urunler:
            values = self._satir_degerleri_olustur(urun, '├')
            tag = 'grup_satir_siparis' if urun.get('Oneri', 0) > 0 else 'grup_satir'
            self.ana_tree.insert('', 'end', iid=f"urun_{urun['UrunId']}", values=values, tags=(tag,))

        # Alt toplam satırı
        alt_values = ['└', f"─── TOPLAM ───", grup_stok, '', '', '', '']

        # Aylık toplamlar
        for col_id, _, _ in self.aylik_sutunlar:
            ay_toplam = sum(u.get(col_id, 0) for u in urunler)
            alt_values.append(ay_toplam)

        alt_values.extend([round(grup_aylik, 1), '', '', grup_oneri, '', '', '', ''])
        self.ana_tree.insert('', 'end', values=alt_values, tags=('alt_toplam',))

    def _tek_satir_ekle(self, urun):
        """Tek satır (eşdeğersiz) ekle"""
        values = self._satir_degerleri_olustur(urun, '●')
        tag = 'tek_satir_siparis' if urun.get('Oneri', 0) > 0 else 'tek_satir'
        self.ana_tree.insert('', 'end', iid=f"urun_{urun['UrunId']}", values=values, tags=(tag,))

    def _satir_degerleri_olustur(self, urun, tur_simge):
        """Satır değerlerini oluştur"""
        values = [
            tur_simge,
            urun.get('UrunAdi', ''),
            urun.get('Stok', 0),
            urun.get('MinStok', 0) or '',
            urun.get('Sart1', ''),
            urun.get('Sart2', ''),
            urun.get('Sart3', ''),
        ]

        # Aylık değerler
        for col_id, _, _ in self.aylik_sutunlar:
            values.append(urun.get(col_id, 0))

        # Öneri değerini vurgulu göster
        oneri_val = urun.get('Oneri', 0)
        oneri_gosterim = f"► {oneri_val}" if oneri_val > 0 else ""

        values.extend([
            urun.get('AylikOrt', 0),
            urun.get('GunlukOrt', 0),
            urun.get('AyBitis', ''),
            oneri_gosterim,
            urun.get('OneriAy', ''),
            urun.get('YeniAyBitis', ''),
            urun.get('Manuel', '') or '',
            urun.get('MF', ''),
        ])

        return values

    def _sorgu_hatasi(self, hata):
        self.status_label.config(text=f"Hata: {hata}")
        messagebox.showerror("Hata", hata)

    # ═══════════════════════════════════════════════════════════════════════
    # KULLANICI ETKİLEŞİMLERİ
    # ═══════════════════════════════════════════════════════════════════════

    def _toggle_yeterlileri_gizle(self):
        """Yeterlileri gizle toggle"""
        self.yeterlileri_gizle.set(not self.yeterlileri_gizle.get())

        if self.yeterlileri_gizle.get():
            self.gizle_btn.config(text="Yeterlileri Gizle: AÇIK", bg='#43A047')
        else:
            self.gizle_btn.config(text="Yeterlileri Gizle: KAPALI", bg='#78909C')

        self._filtreleme_uygula()

    def _satir_secildi(self, event):
        """Satır seçildiğinde detay panelini güncelle"""
        selection = self.ana_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        if item_id.startswith('urun_'):
            urun_id = int(item_id.replace('urun_', ''))
            urun = next((u for u in self.tum_veriler if u['UrunId'] == urun_id), None)
            if urun:
                self._detay_paneli_guncelle(urun)

    def _satir_cift_tiklandi(self, event):
        """Çift tıklama - öneriyi manuel'e kopyala"""
        selection = self.ana_tree.selection()
        if not selection:
            return

        item_id = selection[0]
        if item_id.startswith('urun_'):
            urun_id = int(item_id.replace('urun_', ''))
            urun = next((u for u in self.tum_veriler if u['UrunId'] == urun_id), None)
            if urun:
                oneri = urun.get('Oneri', 0)
                self.manuel_miktarlar[urun_id] = oneri
                urun['Manuel'] = oneri
                self._tabloyu_guncelle()
                self._detay_paneli_guncelle(urun)

    def _detay_paneli_guncelle(self, urun):
        """Detay panelini güncelle"""
        self.secili_urun = urun

        # Placeholder'ı kaldır
        for widget in self.detay_content.winfo_children():
            widget.destroy()

        # Ürün bilgileri
        info_frame = tk.LabelFrame(self.detay_content, text=urun.get('UrunAdi', ''), font=('Arial', 9, 'bold'))
        info_frame.pack(fill=tk.X, pady=(0, 5))

        # Bilgi satırları
        depocu_fiyat = urun.get('DepocuFiyat', 0)
        bilgiler = [
            ("Stok:", urun.get('Stok', 0)),
            ("Min Stok:", urun.get('MinStok', 0)),
            ("Aylık Ort:", urun.get('AylikOrt', 0)),
            ("Günlük Ort:", urun.get('GunlukOrt', 0)),
            ("Ay Bitiş:", urun.get('AyBitis', '')),
            ("Depocu Fiyat:", f"{depocu_fiyat:.2f} ₺" if depocu_fiyat > 0 else "Yok"),
            ("Öneri:", urun.get('Oneri', 0)),
        ]

        for label, value in bilgiler:
            row = tk.Frame(info_frame)
            row.pack(fill=tk.X, padx=5, pady=1)
            tk.Label(row, text=label, font=('Arial', 8), width=10, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=str(value), font=('Arial', 8, 'bold')).pack(side=tk.LEFT)

        # Zam Optimizasyonu Bilgisi (varsa)
        zam_oneri = urun.get('ZamOneri')
        if zam_oneri and (zam_oneri.get('optimum', 0) > 0 or zam_oneri.get('maksimum', 0) > 0):
            zam_frame = tk.LabelFrame(self.detay_content, text="Zam Optimizasyonu - Karar Noktaları", bg='#FFF3E0')
            zam_frame.pack(fill=tk.X, pady=5)

            stok = urun.get('Stok', 0)
            aylik_ort = urun.get('AylikOrt', 1) or 1

            # Karar noktaları bilgisi
            verimlilik = zam_oneri.get('verimlilik', 0)
            verimlilik_roi = zam_oneri.get('verimlilik_roi', 0)
            verimlilik_kazanc = zam_oneri.get('verimlilik_kazanc', 0)
            pareto = zam_oneri.get('pareto', 0)
            pareto_kazanc = zam_oneri.get('pareto_kazanc', 0)
            optimum = zam_oneri.get('optimum', 0)
            kazanc_optimum = zam_oneri.get('kazanc_optimum', 0)
            maksimum = zam_oneri.get('maksimum', 0)

            zam_bilgi = [
                ("Max Verimlilik:", f"{verimlilik} adet ({(stok+verimlilik)/aylik_ort:.1f} ay) = {verimlilik_kazanc:.0f}₺ [ROI: %{verimlilik_roi}]", '#2E7D32', verimlilik),
                ("Pareto (%80):", f"{pareto} adet ({(stok+pareto)/aylik_ort:.1f} ay) = {pareto_kazanc:.0f}₺", '#F57C00', pareto),
                ("Pik (Optimum):", f"{optimum} adet ({(stok+optimum)/aylik_ort:.1f} ay) = {kazanc_optimum:.0f}₺", '#1565C0', optimum),
                ("Sınır:", f"{maksimum} adet ({(stok+maksimum)/aylik_ort:.1f} ay)", '#C62828', maksimum),
            ]

            for label, value, color, miktar in zam_bilgi:
                row = tk.Frame(zam_frame, bg='#FFF3E0')
                row.pack(fill=tk.X, padx=5, pady=1)
                tk.Label(row, text=label, font=('Arial', 8), width=14, anchor='w', bg='#FFF3E0').pack(side=tk.LEFT)
                tk.Label(row, text=value, font=('Arial', 8, 'bold'), bg='#FFF3E0', fg=color).pack(side=tk.LEFT)
                # Seç butonu
                if miktar > 0 and miktar != maksimum:
                    tk.Button(
                        row, text="Seç", font=('Arial', 7), width=4,
                        bg=color, fg='white',
                        command=lambda m=miktar, u=urun: self._zam_miktari_sec(u, m)
                    ).pack(side=tk.RIGHT, padx=2)

        # MF Şartları
        sart_frame = tk.LabelFrame(self.detay_content, text="MF Şartları (Geçmiş)")
        sart_frame.pack(fill=tk.X, pady=5)

        sartlar = [urun.get('Sart1', ''), urun.get('Sart2', ''), urun.get('Sart3', '')]
        sart_text = "  |  ".join([s for s in sartlar if s]) or "Kayıt yok"
        tk.Label(sart_frame, text=sart_text, font=('Arial', 9)).pack(padx=5, pady=3)

        # MF şartlarını buton olarak ekle (tıklanınca hesapla)
        if any(sartlar):
            sart_btn_row = tk.Frame(sart_frame)
            sart_btn_row.pack(fill=tk.X, padx=5, pady=3)
            for sart in sartlar:
                if sart:
                    tk.Button(
                        sart_btn_row, text=f"Hesapla: {sart}",
                        command=lambda s=sart: self._mf_sart_hesapla(urun, s),
                        bg='#7B1FA2', fg='white', font=('Arial', 7)
                    ).pack(side=tk.LEFT, padx=2)

        # MF Analiz Sonucu (varsa)
        self.mf_sonuc_frame = tk.Frame(self.detay_content)
        self.mf_sonuc_frame.pack(fill=tk.X, pady=2)

        # Manuel Giriş
        manuel_frame = tk.LabelFrame(self.detay_content, text="Manuel Sipariş")
        manuel_frame.pack(fill=tk.X, pady=5)

        # Miktar girişi
        miktar_row = tk.Frame(manuel_frame)
        miktar_row.pack(fill=tk.X, padx=5, pady=3)

        tk.Label(miktar_row, text="Miktar:", font=('Arial', 9)).pack(side=tk.LEFT)

        self.manuel_entry = ttk.Entry(miktar_row, width=8)
        self.manuel_entry.pack(side=tk.LEFT, padx=5)
        self.manuel_entry.insert(0, str(urun.get('Manuel', '') or ''))

        tk.Button(miktar_row, text="-", width=2, command=lambda: self._manuel_azalt(urun)).pack(side=tk.LEFT, padx=1)
        tk.Button(miktar_row, text="+", width=2, command=lambda: self._manuel_artir(urun)).pack(side=tk.LEFT, padx=1)

        tk.Button(miktar_row, text="Öneriyi Al", command=lambda: self._oneriyi_al(urun),
                 bg='#7B1FA2', fg='white', font=('Arial', 8)).pack(side=tk.LEFT, padx=5)

        # MF Girişi
        mf_row = tk.Frame(manuel_frame)
        mf_row.pack(fill=tk.X, padx=5, pady=3)

        tk.Label(mf_row, text="MF:", font=('Arial', 9)).pack(side=tk.LEFT)

        self.mf_entry = ttk.Entry(mf_row, width=8)
        self.mf_entry.pack(side=tk.LEFT, padx=5)
        self.mf_entry.insert(0, urun.get('MF', ''))

        tk.Label(mf_row, text="(örn: 5+1)", font=('Arial', 8), fg='gray').pack(side=tk.LEFT)

        # MF Hesapla butonu
        tk.Button(mf_row, text="MF Hesapla", command=lambda: self._mf_manuel_hesapla(urun),
                 bg='#00796B', fg='white', font=('Arial', 7)).pack(side=tk.LEFT, padx=5)

        # Kaydet butonu
        tk.Button(manuel_frame, text="KAYDET", command=lambda: self._manuel_kaydet(urun),
                 bg='#1976D2', fg='white', font=('Arial', 9, 'bold')).pack(pady=5)

        # Kesin listeye ekle butonu
        tk.Button(self.detay_content, text="KESİN LİSTEYE EKLE", command=lambda: self._kesin_listeye_ekle(urun),
                 bg='#388E3C', fg='white', font=('Arial', 9, 'bold'), width=20).pack(pady=10)

    def _manuel_artir(self, urun):
        """Manuel miktarı artır"""
        try:
            mevcut = int(self.manuel_entry.get() or 0)
        except:
            mevcut = 0
        self.manuel_entry.delete(0, tk.END)
        self.manuel_entry.insert(0, str(mevcut + 1))

    def _manuel_azalt(self, urun):
        """Manuel miktarı azalt"""
        try:
            mevcut = int(self.manuel_entry.get() or 0)
        except:
            mevcut = 0
        self.manuel_entry.delete(0, tk.END)
        self.manuel_entry.insert(0, str(max(0, mevcut - 1)))

    def _oneriyi_al(self, urun):
        """Öneriyi manuel alana kopyala"""
        oneri = urun.get('Oneri', 0)
        self.manuel_entry.delete(0, tk.END)
        self.manuel_entry.insert(0, str(oneri))

    def _zam_miktari_sec(self, urun, miktar):
        """Zam optimizasyonu karar noktasından miktar seç"""
        stok = urun.get('Stok', 0)
        # Stoktan düşerek sipariş miktarını hesapla
        siparis = max(0, miktar - stok)
        self.manuel_entry.delete(0, tk.END)
        self.manuel_entry.insert(0, str(siparis))

    def _mf_sart_hesapla(self, urun, mf_sart):
        """Geçmiş MF şartını hesapla ve sonucu göster"""
        self._mf_hesapla_ve_goster(urun, mf_sart)

    def _mf_manuel_hesapla(self, urun):
        """Manuel girilen MF şartını hesapla"""
        mf_sart = self.mf_entry.get().strip()
        if not mf_sart or '+' not in mf_sart:
            messagebox.showwarning("Uyarı", "Lütfen geçerli bir MF şartı girin (örn: 5+1)")
            return
        self._mf_hesapla_ve_goster(urun, mf_sart)

    def _mf_hesapla_ve_goster(self, urun, mf_sart):
        """MF hesaplaması yap ve sonucu göster"""
        # Parametreleri al
        faiz = self._aktif_faiz_getir()
        vade = self.depo_vadesi.get()
        hedef_gun = self._hedef_gun_hesapla()
        aylik_ort = urun.get('AylikOrt', 0)
        stok = urun.get('Stok', 0)

        # Depocu fiyatı (bize geliş fiyatı)
        maliyet = urun.get('DepocuFiyat', 0)
        if maliyet <= 0:
            messagebox.showwarning("Uyarı", "Ürün fiyat bilgisi bulunamadı!")
            return

        # MF optimizasyonu hesapla
        sonuc = self._mf_optimum_hesapla(
            mf_sart=mf_sart,
            maliyet=maliyet,
            aylik_ort=aylik_ort,
            mevcut_stok=stok,
            faiz_yillik=faiz,
            depo_vade=vade,
            hedef_gun=hedef_gun
        )

        # Sonuç frame'ini temizle ve yeniden oluştur
        for widget in self.mf_sonuc_frame.winfo_children():
            widget.destroy()

        if sonuc and sonuc.get('oneri'):
            # Sonuç kutusu
            if sonuc['mfli_al']:
                bg_renk = '#E8F5E9'  # Yeşil - MF'li karlı
                fg_renk = '#2E7D32'
            else:
                bg_renk = '#FFEBEE'  # Kırmızı - MF'siz daha karlı
                fg_renk = '#C62828'

            sonuc_label = tk.LabelFrame(self.mf_sonuc_frame, text=f"MF Analizi: {mf_sart}", bg=bg_renk)
            sonuc_label.pack(fill=tk.X, pady=3)

            tk.Label(
                sonuc_label, text=sonuc['oneri'],
                font=('Arial', 9, 'bold'), bg=bg_renk, fg=fg_renk
            ).pack(padx=5, pady=3)

            # Detay bilgileri
            detay_text = f"Alınan: {sonuc['alinan']} | Bedava: {sonuc['bedava']} | Toplam: {sonuc['toplam']}"
            tk.Label(
                sonuc_label, text=detay_text,
                font=('Arial', 8), bg=bg_renk
            ).pack(padx=5, pady=1)

            # "Uygula" butonu
            tk.Button(
                sonuc_label, text="Bu Öneriyi Uygula",
                command=lambda: self._mf_oneri_uygula(urun, sonuc),
                bg='#1976D2', fg='white', font=('Arial', 8)
            ).pack(pady=3)

    def _mf_oneri_uygula(self, urun, sonuc):
        """MF önerisini manuel alanlara uygula"""
        self.manuel_entry.delete(0, tk.END)
        self.manuel_entry.insert(0, str(sonuc['alinan']))

        if sonuc['bedava'] > 0:
            self.mf_entry.delete(0, tk.END)
            self.mf_entry.insert(0, f"{sonuc['alinan']}+{sonuc['bedava']}")

        self.status_label.config(text=f"MF önerisi uygulandı: {sonuc['oneri']}")

    def _manuel_kaydet(self, urun):
        """Manuel girişleri kaydet"""
        try:
            miktar = int(self.manuel_entry.get() or 0)
        except:
            miktar = 0

        mf = self.mf_entry.get().strip()

        urun_id = urun['UrunId']
        self.manuel_miktarlar[urun_id] = miktar
        self.manuel_mf_girisler[urun_id] = mf

        urun['Manuel'] = miktar
        urun['MF'] = mf

        self._tabloyu_guncelle()
        self.status_label.config(text=f"{urun.get('UrunAdi', '')} güncellendi")

    def _kesin_listeye_ekle(self, urun):
        """Ürünü kesin listeye ekle"""
        try:
            miktar = int(self.manuel_entry.get() or 0)
        except:
            miktar = urun.get('Oneri', 0)

        if miktar <= 0:
            messagebox.showwarning("Uyarı", "Lütfen bir miktar girin!")
            return

        mf = self.mf_entry.get().strip()

        # MF'den toplam hesapla
        toplam = miktar
        if mf and '+' in mf:
            try:
                mf_ek = int(mf.split('+')[1])
                toplam = miktar + mf_ek
            except:
                pass

        # Kesin listeye ekle
        self.kesin_siparis_listesi.append({
            'UrunId': urun['UrunId'],
            'UrunAdi': urun.get('UrunAdi', ''),
            'Miktar': miktar,
            'MF': mf,
            'Toplam': toplam
        })

        self._kesin_liste_guncelle()
        self.status_label.config(text=f"{urun.get('UrunAdi', '')} kesin listeye eklendi")

    def _tum_onerileri_kopyala(self):
        """Tüm önerileri manuel alanlara kopyala"""
        for urun in self.tum_veriler:
            oneri = urun.get('Oneri', 0)
            if oneri > 0:
                urun_id = urun['UrunId']
                self.manuel_miktarlar[urun_id] = oneri
                urun['Manuel'] = oneri

        self._tabloyu_guncelle()
        self.status_label.config(text="Tüm öneriler manuel alanlara kopyalandı")

    def _secilileri_kesin_listeye_ekle(self):
        """Seçili satırları kesin listeye ekle"""
        selection = self.ana_tree.selection()
        eklenen = 0

        for item_id in selection:
            if item_id.startswith('urun_'):
                urun_id = int(item_id.replace('urun_', ''))
                urun = next((u for u in self.tum_veriler if u['UrunId'] == urun_id), None)
                if urun:
                    miktar = urun.get('Manuel', 0) or urun.get('Oneri', 0)
                    if miktar > 0:
                        mf = urun.get('MF', '')
                        toplam = miktar
                        if mf and '+' in mf:
                            try:
                                mf_ek = int(mf.split('+')[1])
                                toplam = miktar + mf_ek
                            except:
                                pass

                        self.kesin_siparis_listesi.append({
                            'UrunId': urun['UrunId'],
                            'UrunAdi': urun.get('UrunAdi', ''),
                            'Barkod': urun.get('Barkod', ''),
                            'Miktar': miktar,
                            'MF': mf,
                            'Toplam': toplam,
                            'Selcuk': '',
                            'Alliance': '',
                            'Sancak': '',
                            'Iskoop': '',
                            'Farmazon': ''
                        })
                        eklenen += 1

        self._kesin_liste_guncelle()
        self.status_label.config(text=f"{eklenen} ürün kesin listeye eklendi")

    def _kesin_liste_guncelle(self):
        """Kesin sipariş listesini güncelle"""
        for item in self.kesin_tree.get_children():
            self.kesin_tree.delete(item)

        for siparis in self.kesin_siparis_listesi:
            self.kesin_tree.insert('', 'end', values=(
                siparis.get('UrunAdi', ''),
                siparis.get('Barkod', ''),
                siparis.get('Miktar', 0),
                siparis.get('MF', ''),
                siparis.get('Toplam', 0),
                siparis.get('Selcuk', ''),
                siparis.get('Alliance', ''),
                siparis.get('Sancak', ''),
                siparis.get('Iskoop', ''),
                siparis.get('Farmazon', '')
            ))

    def _kesin_listeyi_temizle(self):
        """Kesin listeyi temizle"""
        if messagebox.askyesno("Onay", "Kesin sipariş listesi temizlensin mi?"):
            self.kesin_siparis_listesi = []
            self._kesin_liste_guncelle()

    def _kesin_listeyi_excel_aktar(self):
        """Kesin listeyi Excel'e aktar"""
        if not self.kesin_siparis_listesi:
            messagebox.showwarning("Uyarı", "Kesin sipariş listesi boş!")
            return

        dosya_yolu = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Dosyası", "*.xlsx")],
            title="Kesin Sipariş Listesini Kaydet"
        )

        if not dosya_yolu:
            return

        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Kesin Sipariş"

            headers = ["Ürün Adı", "Barkod", "Miktar", "MF", "Toplam", "Selçuk", "Alliance", "Sancak", "İskoop", "Farmazon"]
            for col, h in enumerate(headers, 1):
                ws.cell(row=1, column=col, value=h).font = Font(bold=True)

            for row_idx, siparis in enumerate(self.kesin_siparis_listesi, 2):
                ws.cell(row=row_idx, column=1, value=siparis.get('UrunAdi', ''))
                ws.cell(row=row_idx, column=2, value=siparis.get('Barkod', ''))
                ws.cell(row=row_idx, column=3, value=siparis.get('Miktar', 0))
                ws.cell(row=row_idx, column=4, value=siparis.get('MF', ''))
                ws.cell(row=row_idx, column=5, value=siparis.get('Toplam', 0))
                ws.cell(row=row_idx, column=6, value=siparis.get('Selcuk', ''))
                ws.cell(row=row_idx, column=7, value=siparis.get('Alliance', ''))
                ws.cell(row=row_idx, column=8, value=siparis.get('Sancak', ''))
                ws.cell(row=row_idx, column=9, value=siparis.get('Iskoop', ''))
                ws.cell(row=row_idx, column=10, value=siparis.get('Farmazon', ''))

            # Sütun genişliklerini ayarla
            ws.column_dimensions['A'].width = 40  # Ürün Adı
            ws.column_dimensions['B'].width = 15  # Barkod
            ws.column_dimensions['C'].width = 8   # Miktar
            ws.column_dimensions['D'].width = 8   # MF
            ws.column_dimensions['E'].width = 8   # Toplam
            ws.column_dimensions['F'].width = 12  # Selçuk
            ws.column_dimensions['G'].width = 12  # Alliance
            ws.column_dimensions['H'].width = 12  # Sancak
            ws.column_dimensions['I'].width = 12  # İskoop
            ws.column_dimensions['J'].width = 12  # Farmazon

            wb.save(dosya_yolu)
            messagebox.showinfo("Başarılı", f"Liste kaydedildi:\n{dosya_yolu}")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydetme hatası: {e}")

    def _depolarda_ara(self):
        """Kesin listedeki ürünleri depolarda ara"""
        if not self.kesin_siparis_listesi:
            messagebox.showwarning("Uyarı", "Kesin sipariş listesi boş!")
            return

        # Barkodu olmayan ürünleri kontrol et
        barkodlu_urunler = [s for s in self.kesin_siparis_listesi if s.get('Barkod')]
        if not barkodlu_urunler:
            messagebox.showwarning("Uyarı", "Listede barkodu olan ürün yok!")
            return

        # Butonları devre dışı bırak
        self.depo_ara_btn.config(state='disabled', text="Aranıyor...")
        self.depo_durum_label.config(text=f"0/{len(barkodlu_urunler)} ürün arandı")

        def arama_thread():
            try:
                # BotSiparis modüllerini import et
                import sys
                import os

                # BotSiparis kök klasörünü path'e ekle
                bot_root = os.path.join(os.path.dirname(__file__), "BotSiparis - Kopya")
                bot_src = os.path.join(bot_root, "src")

                # Hem kök hem src'yi path'e ekle (sıra önemli)
                for p in [bot_root, bot_src]:
                    if p not in sys.path:
                        sys.path.insert(0, p)

                from src.depolar.selcuk import SelcukDepo
                from src.depolar.alliance import AllianceDepo
                from src.depolar.sancak import SancakDepo
                from src.depolar.iskoop import IskoopDepo
                from src.depolar.farmazon import FarmazonDepo
                from dotenv import load_dotenv

                # .env dosyasını yükle
                env_path = os.path.join(os.path.dirname(__file__), "BotSiparis - Kopya", ".env")
                load_dotenv(env_path)

                # Depo sırası: Selçuk, Alliance, Sancak, İskoop, Farmazon
                depolar = []

                # Selçuk - login(hesap_kodu, username, password)
                if os.environ.get('SELCUK_ENABLED', 'false').lower() == 'true':
                    depolar.append({
                        'key': 'Selcuk',
                        'class': SelcukDepo,
                        'login_args': (
                            os.environ.get('SELCUK_HESAP_KODU'),
                            os.environ.get('SELCUK_USERNAME'),
                            os.environ.get('SELCUK_PASSWORD')
                        )
                    })

                # Alliance - login(eczane_kodu, username, password)
                if os.environ.get('ALLIANCE_ENABLED', 'false').lower() == 'true':
                    depolar.append({
                        'key': 'Alliance',
                        'class': AllianceDepo,
                        'login_args': (
                            os.environ.get('ALLIANCE_ECZANE_KODU'),
                            os.environ.get('ALLIANCE_USERNAME'),
                            os.environ.get('ALLIANCE_PASSWORD')
                        )
                    })

                # Sancak - login(username, password)
                if os.environ.get('SANCAK_ENABLED', 'false').lower() == 'true':
                    depolar.append({
                        'key': 'Sancak',
                        'class': SancakDepo,
                        'login_args': (
                            os.environ.get('SANCAK_USERNAME'),
                            os.environ.get('SANCAK_PASSWORD')
                        )
                    })

                # İskoop - login(username, password)
                if os.environ.get('ISKOOP_ENABLED', 'false').lower() == 'true':
                    depolar.append({
                        'key': 'Iskoop',
                        'class': IskoopDepo,
                        'login_args': (
                            os.environ.get('ISKOOP_USERNAME'),
                            os.environ.get('ISKOOP_PASSWORD')
                        )
                    })

                # Farmazon - login(username, password)
                if os.environ.get('FARMAZON_ENABLED', 'false').lower() == 'true':
                    depolar.append({
                        'key': 'Farmazon',
                        'class': FarmazonDepo,
                        'login_args': (
                            os.environ.get('FARMAZON_USERNAME'),
                            os.environ.get('FARMAZON_PASSWORD')
                        )
                    })

                if not depolar:
                    self.parent.after(0, lambda: messagebox.showwarning(
                        "Uyarı", "Hiçbir depo etkinleştirilmemiş!\n.env dosyasını kontrol edin."
                    ))
                    return

                # Her depo için driver başlat ve login ol
                aktif_depolar = []
                for depo_info in depolar:
                    try:
                        depo = depo_info['class']()
                        if depo.init_driver():
                            if depo.login(*depo_info['login_args']):
                                aktif_depolar.append({'key': depo_info['key'], 'depo': depo})
                                logger.info(f"{depo_info['key']} deposuna giriş başarılı")
                            else:
                                logger.warning(f"{depo_info['key']} deposuna giriş başarısız")
                    except Exception as e:
                        logger.error(f"{depo_info['key']} depo hatası: {e}")

                if not aktif_depolar:
                    self.parent.after(0, lambda: messagebox.showerror(
                        "Hata", "Hiçbir depoya giriş yapılamadı!"
                    ))
                    return

                # Her ürün için arama yap
                for idx, siparis in enumerate(self.kesin_siparis_listesi):
                    barkod = siparis.get('Barkod')
                    if not barkod:
                        continue

                    # Durum güncelle
                    self.parent.after(0, lambda i=idx, t=len(barkodlu_urunler):
                        self.depo_durum_label.config(text=f"{i+1}/{t} aranıyor...")
                    )

                    # Her depoda ara
                    for depo_bilgi in aktif_depolar:
                        depo_key = depo_bilgi['key']
                        depo = depo_bilgi['depo']

                        try:
                            # Barkodu ara
                            if depo.search_barcode(str(barkod)):
                                # Stok durumu kontrol et
                                sonuc = depo.check_stock_status()

                                if sonuc.get('stok_var'):
                                    # MF varsa göster
                                    mf_sart = sonuc.get('sart', '')
                                    if mf_sart:
                                        siparis[depo_key] = f"✓ {mf_sart}"
                                    else:
                                        siparis[depo_key] = "✓ Var"
                                elif sonuc.get('mesaj') == 'Depoyu Ara':
                                    siparis[depo_key] = "📞 Ara"
                                else:
                                    siparis[depo_key] = "✗ Yok"
                            else:
                                siparis[depo_key] = "- Yok"
                        except Exception as e:
                            logger.error(f"{depo_key} arama hatası ({barkod}): {e}")
                            siparis[depo_key] = "! Hata"

                    # Listeyi güncelle
                    self.parent.after(0, self._kesin_liste_guncelle)

                # Tarayıcıları kapat
                for depo_bilgi in aktif_depolar:
                    try:
                        depo_bilgi['depo'].close()
                    except:
                        pass

                # Tamamlandı
                self.parent.after(0, lambda: self._depo_arama_tamamlandi(len(barkodlu_urunler)))

            except Exception as e:
                logger.error(f"Depo arama hatası: {e}")
                self.parent.after(0, lambda: messagebox.showerror("Hata", f"Depo arama hatası:\n{e}"))
            finally:
                self.parent.after(0, lambda: self.depo_ara_btn.config(state='normal', text="🔍 DEPOLARDA ARA"))

        # Thread başlat
        thread = threading.Thread(target=arama_thread, daemon=True)
        thread.start()

    def _depo_arama_tamamlandi(self, toplam):
        """Depo araması tamamlandığında"""
        self.depo_durum_label.config(text=f"✓ {toplam} ürün arandı")
        self._kesin_liste_guncelle()

    def excel_aktar(self):
        """Ana tabloyu Excel'e aktar"""
        if not self.tum_veriler:
            messagebox.showwarning("Uyarı", "Aktarılacak veri yok!")
            return

        dosya_yolu = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel Dosyası", "*.xlsx")],
            title="Excel Olarak Kaydet"
        )

        if not dosya_yolu:
            return

        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "Sipariş Analizi"

            # Başlıklar
            headers = [c[1] for c in self.aktif_sutunlar]
            for col, h in enumerate(headers, 1):
                ws.cell(row=1, column=col, value=h).font = Font(bold=True)

            # Veriler
            for row_idx, veri in enumerate(self.tum_veriler, 2):
                col = 1
                for col_id, _, _ in self.aktif_sutunlar:
                    if col_id == 'Tur':
                        ws.cell(row=row_idx, column=col, value='')
                    else:
                        ws.cell(row=row_idx, column=col, value=veri.get(col_id, ''))
                    col += 1

            wb.save(dosya_yolu)
            messagebox.showinfo("Başarılı", f"Veriler aktarıldı:\n{dosya_yolu}")
        except Exception as e:
            messagebox.showerror("Hata", f"Aktarım hatası: {e}")


# Test
if __name__ == "__main__":
    root = tk.Tk()
    app = SiparisVermeGUI(root)
    root.mainloop()
