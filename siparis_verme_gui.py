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
        """Parametre panelini oluştur - 2 satır kompakt"""
        param_frame = tk.Frame(parent, bg='#ECEFF1', relief='raised', bd=1)
        param_frame.pack(fill=tk.X, pady=(0, 3))

        # ═══════════════════════════════════════════════════════════
        # SATIR 1: Temel Parametreler
        # ═══════════════════════════════════════════════════════════
        row1 = tk.Frame(param_frame, bg='#ECEFF1')
        row1.pack(fill=tk.X, padx=5, pady=3)

        # Grup 1: Hareket Süresi
        grp1 = tk.Frame(row1, bg='#E3F2FD', relief='groove', bd=1)
        grp1.pack(side=tk.LEFT, padx=(0, 5), pady=1)

        tk.Label(grp1, text="Hareket:", font=('Arial', 8, 'bold'), bg='#E3F2FD').pack(side=tk.LEFT, padx=(3, 2))
        sene_combo = ttk.Combobox(grp1, textvariable=self.sene_sayisi, width=2, state="readonly")
        sene_combo['values'] = [1, 2, 3]
        sene_combo.pack(side=tk.LEFT, padx=(0, 1))
        tk.Label(grp1, text="yıl", font=('Arial', 8), bg='#E3F2FD').pack(side=tk.LEFT, padx=(0, 3))

        # Grup 2: Aylık Gidiş
        grp2 = tk.Frame(row1, bg='#E3F2FD', relief='groove', bd=1)
        grp2.pack(side=tk.LEFT, padx=(0, 5), pady=1)

        tk.Label(grp2, text="Aylık:", font=('Arial', 8, 'bold'), bg='#E3F2FD').pack(side=tk.LEFT, padx=(3, 2))
        ay_combo = ttk.Combobox(grp2, textvariable=self.ay_sayisi, width=2, state="readonly")
        ay_combo['values'] = [3, 6, 9, 12]
        ay_combo.pack(side=tk.LEFT, padx=(0, 1))
        tk.Label(grp2, text="ay", font=('Arial', 8), bg='#E3F2FD').pack(side=tk.LEFT, padx=(0, 3))

        # Grup 3: Ürün Tipi
        grp3 = tk.Frame(row1, bg='#E3F2FD', relief='groove', bd=1)
        grp3.pack(side=tk.LEFT, padx=(0, 5), pady=1)

        tk.Label(grp3, text="Tip:", font=('Arial', 8, 'bold'), bg='#E3F2FD').pack(side=tk.LEFT, padx=(3, 2))
        self.urun_tipi_menubutton = tk.Menubutton(
            grp3, text="...", relief=tk.RAISED, width=12, font=('Arial', 7), bg='white'
        )
        self.urun_tipi_menu = tk.Menu(self.urun_tipi_menubutton, tearoff=0)
        self.urun_tipi_menubutton["menu"] = self.urun_tipi_menu
        self.urun_tipi_menubutton.pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(grp3, text="T", command=self._tum_tipleri_sec, width=2).pack(side=tk.LEFT, padx=1)
        ttk.Button(grp3, text="V", command=self._varsayilan_tipleri_sec, width=2).pack(side=tk.LEFT, padx=(0, 3))

        # Grup 4: Hedef Tarih
        grp4 = tk.Frame(row1, bg='#E8F5E9', relief='groove', bd=1)
        grp4.pack(side=tk.LEFT, padx=(0, 5), pady=1)

        self.hedef_check = tk.Checkbutton(
            grp4, text="Hedef:", variable=self.hedef_tarih_aktif,
            bg='#E8F5E9', font=('Arial', 8, 'bold'), activebackground='#E8F5E9'
        )
        self.hedef_check.pack(side=tk.LEFT, padx=(3, 2))

        bugun = datetime.now()
        ay_son_gun = calendar.monthrange(bugun.year, bugun.month)[1]
        self.hedef_tarih_entry = DateEntry(
            grp4, width=9, background='#1976D2', foreground='white',
            borderwidth=1, date_pattern='yyyy-mm-dd',
            year=bugun.year, month=bugun.month, day=ay_son_gun
        )
        self.hedef_tarih_entry.pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(grp4, text="AySonu", command=self._ay_sonu_sec, width=5).pack(side=tk.LEFT, padx=(0, 3))

        # Grup 5: Zam
        grp5 = tk.Frame(row1, bg='#FFF3E0', relief='groove', bd=1)
        grp5.pack(side=tk.LEFT, padx=(0, 5), pady=1)

        self.zam_check = tk.Checkbutton(
            grp5, text="Zam:", variable=self.zam_aktif,
            bg='#FFF3E0', font=('Arial', 8, 'bold'), activebackground='#FFF3E0'
        )
        self.zam_check.pack(side=tk.LEFT, padx=(3, 1))

        tk.Label(grp5, text="%", font=('Arial', 8), bg='#FFF3E0').pack(side=tk.LEFT)
        zam_entry = ttk.Entry(grp5, textvariable=self.beklenen_zam_orani, width=4)
        zam_entry.pack(side=tk.LEFT, padx=(0, 3))

        self.zam_tarih_entry = DateEntry(
            grp5, width=9, background='#E65100', foreground='white',
            borderwidth=1, date_pattern='yyyy-mm-dd'
        )
        self.zam_tarih_entry.pack(side=tk.LEFT, padx=(0, 3))

        # Grup 6: Min Stok
        grp6 = tk.Frame(row1, bg='#F3E5F5', relief='groove', bd=1)
        grp6.pack(side=tk.LEFT, padx=(0, 5), pady=1)

        self.min_check = tk.Checkbutton(
            grp6, text="Min.Stok", variable=self.min_stok_aktif,
            bg='#F3E5F5', font=('Arial', 8), activebackground='#F3E5F5'
        )
        self.min_check.pack(side=tk.LEFT, padx=3)

        # Butonlar
        btn_frame = tk.Frame(row1, bg='#ECEFF1')
        btn_frame.pack(side=tk.LEFT, padx=(10, 0), pady=1)

        self.getir_btn = tk.Button(
            btn_frame, text="VERİLERİ GETİR", command=self.verileri_getir,
            bg='#1976D2', fg='white', font=('Arial', 9, 'bold'),
            relief='raised', bd=2, padx=8
        )
        self.getir_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.excel_btn = tk.Button(
            btn_frame, text="EXCEL", command=self.excel_aktar,
            bg='#FF6F00', fg='white', font=('Arial', 9, 'bold'),
            relief='raised', bd=2, padx=6
        )
        self.excel_btn.pack(side=tk.LEFT)

        # Sağda bilgi etiketi
        self.hesaplama_label = tk.Label(
            row1, text="", font=('Arial', 9, 'bold'), bg='#ECEFF1', fg='#1565C0'
        )
        self.hesaplama_label.pack(side=tk.RIGHT, padx=5)

        # ═══════════════════════════════════════════════════════════
        # SATIR 2: Filtre ve Toggle
        # ═══════════════════════════════════════════════════════════
        row2 = tk.Frame(param_frame, bg='#ECEFF1')
        row2.pack(fill=tk.X, padx=5, pady=(0, 3))

        # Yeterlileri Gizle Toggle
        self.gizle_btn = tk.Button(
            row2, text="Yeterlileri Gizle: KAPALI", command=self._toggle_yeterlileri_gizle,
            bg='#78909C', fg='white', font=('Arial', 8, 'bold'),
            relief='raised', bd=2, padx=8
        )
        self.gizle_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Toplu işlem butonları
        tk.Button(
            row2, text="Tüm Önerileri Manuel'e Kopyala", command=self._tum_onerileri_kopyala,
            bg='#7B1FA2', fg='white', font=('Arial', 8), relief='raised', bd=1, padx=5
        ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(
            row2, text="Seçilileri Kesin Listeye Ekle", command=self._secilileri_kesin_listeye_ekle,
            bg='#388E3C', fg='white', font=('Arial', 8), relief='raised', bd=1, padx=5
        ).pack(side=tk.LEFT, padx=(0, 5))

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
        """Ana DataGrid - gruplu görünüm"""
        grid_frame = tk.Frame(self.orta_paned, bg='#FAFAFA', relief='sunken', bd=1)
        self.orta_paned.add(grid_frame, minsize=900, width=1200)

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
            ("AylikOrt", "Aylık", 50),
            ("GunlukOrt", "Gün", 40),
            ("AyBitis", "AyBitiş", 50),
            ("Oneri", "Öneri", 50),
            ("Manuel", "Manuel", 50),
            ("MF", "MF", 45),
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

        # Tag'ler
        self.ana_tree.tag_configure('grup_baslik', background=self.RENK_GRUP_BASLIK, foreground='white')
        self.ana_tree.tag_configure('grup_satir', background=self.RENK_GRUP_ICERIK)
        self.ana_tree.tag_configure('grup_satir_siparis', background='#FFCDD2')
        self.ana_tree.tag_configure('alt_toplam', background=self.RENK_ALT_TOPLAM, foreground='#1A237E')
        self.ana_tree.tag_configure('tek_satir', background=self.RENK_TEK_SATIR)
        self.ana_tree.tag_configure('tek_satir_siparis', background='#FFCDD2')

        # Seçim olayı
        self.ana_tree.bind('<<TreeviewSelect>>', self._satir_secildi)
        self.ana_tree.bind('<Double-1>', self._satir_cift_tiklandi)

    def _detay_panel_olustur(self):
        """Sağ taraftaki detay paneli"""
        detay_frame = tk.Frame(self.orta_paned, bg='#F5F5F5', relief='sunken', bd=1)
        self.orta_paned.add(detay_frame, minsize=280, width=350)

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
        """Alt kısımdaki kesin sipariş listesi"""
        kesin_frame = tk.Frame(parent, bg='#FAFAFA', relief='sunken', bd=1, height=150)
        kesin_frame.pack(fill=tk.X, pady=(0, 3))
        kesin_frame.pack_propagate(False)

        # Başlık
        header = tk.Frame(kesin_frame, bg='#388E3C', height=26)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="✓ KESİNLEŞMİŞ SİPARİŞ LİSTESİ", bg='#388E3C', fg='white',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=10)

        tk.Button(header, text="Listeyi Temizle", command=self._kesin_listeyi_temizle,
                 bg='#C62828', fg='white', font=('Arial', 8), relief='flat', padx=5
                 ).pack(side=tk.RIGHT, padx=5, pady=2)

        tk.Button(header, text="Excel'e Aktar", command=self._kesin_listeyi_excel_aktar,
                 bg='#FF6F00', fg='white', font=('Arial', 8), relief='flat', padx=5
                 ).pack(side=tk.RIGHT, padx=2, pady=2)

        # Treeview
        tree_frame = tk.Frame(kesin_frame, bg='#FAFAFA')
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        columns = [
            ("UrunAdi", "Ürün Adı", 300),
            ("Miktar", "Miktar", 70),
            ("MF", "MF", 60),
            ("Toplam", "Toplam", 70),
        ]

        self.kesin_tree = ttk.Treeview(tree_frame, columns=[c[0] for c in columns],
                                       show='headings', height=4)
        for col_id, baslik, width in columns:
            self.kesin_tree.heading(col_id, text=baslik)
            self.kesin_tree.column(col_id, width=width, minwidth=50)

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
            (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) as Stok,
            COALESCE(u.UrunMinimum, 0) as MinStok,
            COALESCE(ao.ToplamCikis, 0) as ToplamCikis,
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

            # Aylık ve günlük ortalama
            aylik_ort = toplam_cikis / ay_sayisi if ay_sayisi > 0 else 0
            gunluk_ort = aylik_ort / 30

            # Ay bitiş (stok kaç ay yeter)
            ay_bitis = stok / aylik_ort if aylik_ort > 0 else 999

            # Temel ihtiyaç = hedef güne kadar gereken
            temel_ihtiyac = gunluk_ort * hedef_gun

            # Sipariş önerisi hesaplama
            oneri = max(0, temel_ihtiyac - stok)

            # Minimum stok kontrolü
            if min_stok_aktif and min_stok > 0 and stok < min_stok:
                min_eksik = min_stok - stok
                oneri = max(oneri, min_eksik)

            # Zam analizi (basit)
            if zam_aktif and zam_orani > 0:
                # Zam karlılık hesabı - MF Analiz mantığı
                # Şimdilik basit: zam oranı kadar fazla al
                zam_karli_miktar = temel_ihtiyac * (1 + zam_orani)
                oneri = max(oneri, zam_karli_miktar - stok)

            # MF şartları
            sartlar = mf_sartlari.get(urun_id, [])

            esdeger_id = veri.get('EsdegerId')

            satir = {
                'UrunId': urun_id,
                'UrunAdi': veri.get('UrunAdi', ''),
                'UrunTipi': veri.get('UrunTipi', ''),
                'EsdegerId': esdeger_id,
                'Stok': stok,
                'MinStok': min_stok,
                'ToplamCikis': toplam_cikis,
                'AylikOrt': round(aylik_ort, 1),
                'GunlukOrt': round(gunluk_ort, 2),
                'AyBitis': round(ay_bitis, 1) if ay_bitis < 100 else ">99",
                'HedefGun': hedef_gun,
                'Oneri': int(round(oneri, 0)),
                'Manuel': self.manuel_miktarlar.get(urun_id, 0),
                'MF': self.manuel_mf_girisler.get(urun_id, ''),
                'Sart1': sartlar[0] if len(sartlar) > 0 else '',
                'Sart2': sartlar[1] if len(sartlar) > 1 else '',
                'Sart3': sartlar[2] if len(sartlar) > 2 else '',
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
        self.hesaplama_label.config(
            text=f"Hedef: {hedef_gun} gün | {len(veriler)} ürün | {siparis_gereken} sipariş gerekli"
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

        alt_values.extend([round(grup_aylik, 1), '', '', grup_oneri, '', ''])
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

        values.extend([
            urun.get('AylikOrt', 0),
            urun.get('GunlukOrt', 0),
            urun.get('AyBitis', ''),
            urun.get('Oneri', 0),
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
        bilgiler = [
            ("Stok:", urun.get('Stok', 0)),
            ("Min Stok:", urun.get('MinStok', 0)),
            ("Aylık Ort:", urun.get('AylikOrt', 0)),
            ("Günlük Ort:", urun.get('GunlukOrt', 0)),
            ("Ay Bitiş:", urun.get('AyBitis', '')),
            ("Öneri:", urun.get('Oneri', 0)),
        ]

        for label, value in bilgiler:
            row = tk.Frame(info_frame)
            row.pack(fill=tk.X, padx=5, pady=1)
            tk.Label(row, text=label, font=('Arial', 8), width=10, anchor='w').pack(side=tk.LEFT)
            tk.Label(row, text=str(value), font=('Arial', 8, 'bold')).pack(side=tk.LEFT)

        # MF Şartları
        sart_frame = tk.LabelFrame(self.detay_content, text="MF Şartları (Geçmiş)")
        sart_frame.pack(fill=tk.X, pady=5)

        sartlar = [urun.get('Sart1', ''), urun.get('Sart2', ''), urun.get('Sart3', '')]
        sart_text = "  |  ".join([s for s in sartlar if s]) or "Kayıt yok"
        tk.Label(sart_frame, text=sart_text, font=('Arial', 9)).pack(padx=5, pady=3)

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
                            'Miktar': miktar,
                            'MF': mf,
                            'Toplam': toplam
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
                siparis.get('Miktar', 0),
                siparis.get('MF', ''),
                siparis.get('Toplam', 0)
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

            headers = ["Ürün Adı", "Miktar", "MF", "Toplam"]
            for col, h in enumerate(headers, 1):
                ws.cell(row=1, column=col, value=h).font = Font(bold=True)

            for row_idx, siparis in enumerate(self.kesin_siparis_listesi, 2):
                ws.cell(row=row_idx, column=1, value=siparis.get('UrunAdi', ''))
                ws.cell(row=row_idx, column=2, value=siparis.get('Miktar', 0))
                ws.cell(row=row_idx, column=3, value=siparis.get('MF', ''))
                ws.cell(row=row_idx, column=4, value=siparis.get('Toplam', 0))

            wb.save(dosya_yolu)
            messagebox.showinfo("Başarılı", f"Liste kaydedildi:\n{dosya_yolu}")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydetme hatası: {e}")

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
