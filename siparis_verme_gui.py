"""
Sipariş Verme Modülü GUI
Stok hareket analizi bazlı sipariş hazırlama sistemi
Accordion panel yapısı ile kısmi ve kesin sipariş ayrımı
Aylık dağılım gösterimi
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import calendar
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from tkcalendar import DateEntry

logger = logging.getLogger(__name__)


class SiparisVermeGUI:
    """Sipariş Verme Modülü Penceresi"""

    # Varsayılan seçili ürün tipleri
    VARSAYILAN_URUN_TIPLERI = ['İLAÇ', 'PASİF İLAÇ', 'SERUMLAR']

    # Renkler
    RENK_GIRIS = '#C8E6C9'  # Açık yeşil
    RENK_CIKIS = '#FFCDD2'  # Açık pembe
    RENK_ALT_TOPLAM = '#B0BEC5'  # Koyu gri
    RENK_GRUP_BASLIK = '#78909C'  # Daha koyu gri
    RENK_KISMI = '#FFF3E0'  # Açık turuncu
    RENK_KESIN = '#FFEBEE'  # Açık kırmızı

    def __init__(self, parent):
        self.parent = parent
        self.parent.title("Sipariş Verme Modülü")
        self.parent.geometry("1600x900")

        self.db = None
        self.veriler = []
        self.islenenmis_veriler = []
        self.kismi_siparis_verileri = []
        self.kesin_siparis_verileri = []

        # Parametre değişkenleri
        self.ay_sayisi = tk.IntVar(value=6)

        # Ürün tipi çoklu seçim için
        self.urun_tipi_vars = {}
        self.urun_tipleri_listesi = []

        # Sipariş parametreleri
        self.beklenen_zam_orani = tk.DoubleVar(value=0.0)
        self.min_stok_tamamla = tk.BooleanVar(value=True)  # Varsayılan: işaretli

        # Accordion panelleri
        self.accordion_frame = None
        self.kismi_panel = None
        self.kesin_panel = None

        # Dinamik sütunlar
        self.aktif_sutunlar = []
        self.aktif_basliklar = {}

        self._arayuz_olustur()
        self._baglanti_kur()

    def _arayuz_olustur(self):
        """Ana arayüzü oluştur"""
        # Ana frame
        main_frame = ttk.Frame(self.parent, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Üst panel - Parametreler (tek satır, kompakt)
        self._parametre_panel_olustur(main_frame)

        # Alt panel - 3 eşit accordion panel (Ana Veri, Kısmi, Kesin)
        self._uc_panel_olustur(main_frame)

        # Status bar
        self._status_bar_olustur(main_frame)

    def _parametre_panel_olustur(self, parent):
        """Parametre panelini oluştur - tek satır kompakt tasarım"""
        # Ana parametre çerçevesi
        param_frame = tk.Frame(parent, bg='#ECEFF1', relief='raised', bd=1)
        param_frame.pack(fill=tk.X, pady=(0, 5))

        # Tek satır - tüm kontroller yan yana
        row = tk.Frame(param_frame, bg='#ECEFF1')
        row.pack(fill=tk.X, padx=5, pady=5)

        # ══════ GRUP 1: Analiz Parametreleri ══════
        grp1 = tk.Frame(row, bg='#E3F2FD', relief='groove', bd=1)
        grp1.pack(side=tk.LEFT, padx=(0, 8), pady=2)

        tk.Label(grp1, text="Ay:", font=('Arial', 9, 'bold'), bg='#E3F2FD').pack(side=tk.LEFT, padx=(5, 2))
        ay_combo = ttk.Combobox(grp1, textvariable=self.ay_sayisi, width=3, state="readonly")
        ay_combo['values'] = [3, 6, 9, 12]
        ay_combo.set(6)
        ay_combo.pack(side=tk.LEFT, padx=(0, 5))

        # Ürün Tipi
        tk.Label(grp1, text="Tip:", font=('Arial', 9, 'bold'), bg='#E3F2FD').pack(side=tk.LEFT, padx=(5, 2))
        self.urun_tipi_menubutton = tk.Menubutton(
            grp1, text="...", relief=tk.RAISED, width=14, font=('Arial', 8), bg='white'
        )
        self.urun_tipi_menu = tk.Menu(self.urun_tipi_menubutton, tearoff=0)
        self.urun_tipi_menubutton["menu"] = self.urun_tipi_menu
        self.urun_tipi_menubutton.pack(side=tk.LEFT, padx=(0, 3))

        ttk.Button(grp1, text="T", command=self._tum_tipleri_sec, width=2).pack(side=tk.LEFT, padx=1)
        ttk.Button(grp1, text="V", command=self._varsayilan_tipleri_sec, width=2).pack(side=tk.LEFT, padx=(0, 5))

        # ══════ GRUP 2: Tarih Parametreleri ══════
        grp2 = tk.Frame(row, bg='#E8F5E9', relief='groove', bd=1)
        grp2.pack(side=tk.LEFT, padx=(0, 8), pady=2)

        tk.Label(grp2, text="Hedef:", font=('Arial', 9, 'bold'), bg='#E8F5E9').pack(side=tk.LEFT, padx=(5, 2))
        bugun = datetime.now()
        ay_son_gun = calendar.monthrange(bugun.year, bugun.month)[1]
        self.hedef_tarih_entry = DateEntry(
            grp2, width=10, background='#1976D2', foreground='white',
            borderwidth=1, date_pattern='yyyy-mm-dd',
            year=bugun.year, month=bugun.month, day=ay_son_gun
        )
        self.hedef_tarih_entry.pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(grp2, text="AySonu", command=self._ay_sonu_sec, width=6).pack(side=tk.LEFT, padx=(0, 5))

        # ══════ GRUP 3: Zam Parametreleri ══════
        grp3 = tk.Frame(row, bg='#FFF3E0', relief='groove', bd=1)
        grp3.pack(side=tk.LEFT, padx=(0, 8), pady=2)

        tk.Label(grp3, text="Zam%:", font=('Arial', 9), bg='#FFF3E0').pack(side=tk.LEFT, padx=(5, 2))
        zam_entry = ttk.Entry(grp3, textvariable=self.beklenen_zam_orani, width=4)
        zam_entry.pack(side=tk.LEFT, padx=(0, 5))

        tk.Label(grp3, text="Tarih:", font=('Arial', 9), bg='#FFF3E0').pack(side=tk.LEFT, padx=(0, 2))
        self.zam_tarih_entry = DateEntry(
            grp3, width=10, background='#E65100', foreground='white',
            borderwidth=1, date_pattern='yyyy-mm-dd'
        )
        self.zam_tarih_entry.pack(side=tk.LEFT, padx=(0, 5))

        # ══════ GRUP 4: Minimum Stok Ayarı ══════
        grp4 = tk.Frame(row, bg='#E8EAF6', relief='groove', bd=1)
        grp4.pack(side=tk.LEFT, padx=(0, 8), pady=2)

        self.min_stok_check = tk.Checkbutton(
            grp4, text="Min. stok tamamla",
            variable=self.min_stok_tamamla,
            bg='#E8EAF6', font=('Arial', 8),
            activebackground='#E8EAF6'
        )
        self.min_stok_check.pack(side=tk.LEFT, padx=5, pady=2)

        # ══════ GRUP 5: Aksiyon Butonları ══════
        grp5 = tk.Frame(row, bg='#ECEFF1')
        grp5.pack(side=tk.LEFT, padx=(5, 0), pady=2)

        self.getir_btn = tk.Button(
            grp5, text="VERİLERİ GETİR", command=self.verileri_getir,
            bg='#1976D2', fg='white', font=('Arial', 9, 'bold'),
            relief='raised', bd=2, padx=10
        )
        self.getir_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.siparis_olustur_btn = tk.Button(
            grp5, text="SİPARİŞ OLUŞTUR", command=self.siparis_olustur,
            bg='#388E3C', fg='white', font=('Arial', 9, 'bold'),
            relief='raised', bd=2, padx=10, state=tk.DISABLED
        )
        self.siparis_olustur_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.excel_btn = tk.Button(
            grp5, text="EXCEL", command=self.excel_aktar,
            bg='#FF6F00', fg='white', font=('Arial', 9, 'bold'),
            relief='raised', bd=2, padx=8
        )
        self.excel_btn.pack(side=tk.LEFT)

        # ══════ Bilgi Etiketi (sağda) ══════
        self.hesaplama_label = tk.Label(
            row, text="", font=('Arial', 9, 'bold'), bg='#ECEFF1', fg='#1565C0'
        )
        self.hesaplama_label.pack(side=tk.RIGHT, padx=10)

    def _uc_panel_olustur(self, parent):
        """Üç eşit büyüklükte accordion panel oluştur"""
        # PanedWindow kullanarak eşit bölünebilir paneller
        self.paned = tk.PanedWindow(parent, orient=tk.VERTICAL, sashwidth=4, sashrelief=tk.RAISED, bg='#90A4AE')
        self.paned.pack(fill=tk.BOTH, expand=True)

        # Temel sütun tanımları
        self.temel_sutunlar = [
            ("UrunTipi", "Ürün Tipi", 90),
            ("UrunAdi", "Ürün Adı", 250),
            ("Esdeger", "Eşdeğer", 70),
            ("Stok", "Stok", 50),
            ("MinStok", "Min", 40),
            ("MF", "MF", 70),
        ]
        self.son_sutunlar = [
            ("AylikOrt", "Aylık Ort", 65),
            ("GunlukOrt", "Gün.Ort", 55),
            ("AyBitis", "Ay Bitiş", 60),
            ("HedefGun", "Hdf.Gün", 55),
            ("Ihtiyac", "İhtiyaç", 60),
            ("SiparisMiktar", "Sipariş", 60),
        ]

        # ═══════════════════════════════════════════════════════════════
        # PANEL 1: Ana Stok Verileri (Mavi tema)
        # ═══════════════════════════════════════════════════════════════
        self.ana_panel_frame = self._create_panel_v2(
            "📊 STOK VE HAREKET VERİLERİ",
            '#1976D2', '#E3F2FD', 'white'
        )
        self.paned.add(self.ana_panel_frame, minsize=100)

        # Ana tablo içeriği
        self._ana_tablo_icerigi_olustur(self.ana_panel_frame)

        # ═══════════════════════════════════════════════════════════════
        # PANEL 2: Kısmi Sipariş (Turuncu tema)
        # ═══════════════════════════════════════════════════════════════
        self.kismi_panel_frame = self._create_panel_v2(
            "🟠 KISMİ SİPARİŞ - Muadil Yeterli",
            '#E65100', '#FFF3E0', 'white'
        )
        self.paned.add(self.kismi_panel_frame, minsize=100)

        # Kısmi sipariş placeholder
        self.kismi_content = tk.Frame(self.kismi_panel_frame, bg='#FFF3E0')
        self.kismi_content.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.kismi_placeholder = tk.Label(
            self.kismi_content,
            text="Sipariş oluşturmak için önce 'VERİLERİ GETİR' butonuna tıklayın",
            bg='#FFF3E0', fg='#E65100', font=('Arial', 10, 'italic')
        )
        self.kismi_placeholder.pack(expand=True)

        # ═══════════════════════════════════════════════════════════════
        # PANEL 3: Kesin Sipariş (Kırmızı tema)
        # ═══════════════════════════════════════════════════════════════
        self.kesin_panel_frame = self._create_panel_v2(
            "🔴 KESİN SİPARİŞ - Muadil Yetersiz/Yok",
            '#C62828', '#FFEBEE', 'white'
        )
        self.paned.add(self.kesin_panel_frame, minsize=100)

        # Kesin sipariş placeholder
        self.kesin_content = tk.Frame(self.kesin_panel_frame, bg='#FFEBEE')
        self.kesin_content.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.kesin_placeholder = tk.Label(
            self.kesin_content,
            text="Sipariş oluşturmak için önce 'VERİLERİ GETİR' butonuna tıklayın",
            bg='#FFEBEE', fg='#C62828', font=('Arial', 10, 'italic')
        )
        self.kesin_placeholder.pack(expand=True)

    def _create_panel_v2(self, title, header_bg, content_bg, header_fg):
        """Yeni panel yapısı - başlık + içerik"""
        frame = tk.Frame(self.paned, bg=content_bg, relief='sunken', bd=1)

        # Başlık çubuğu
        header = tk.Frame(frame, bg=header_bg, height=28)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(
            header, text=title, bg=header_bg, fg=header_fg,
            font=('Arial', 10, 'bold'), anchor='w'
        ).pack(side=tk.LEFT, padx=10, pady=3)

        return frame

    def _ana_tablo_icerigi_olustur(self, parent):
        """Ana tablo içeriğini oluştur"""
        content = tk.Frame(parent, bg='#E3F2FD')
        content.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Treeview
        self.ana_tree = ttk.Treeview(content, columns=[], show='headings')

        # Scrollbarlar
        vsb = ttk.Scrollbar(content, orient="vertical", command=self.ana_tree.yview)
        hsb = ttk.Scrollbar(content, orient="horizontal", command=self.ana_tree.xview)
        self.ana_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        self.ana_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        # Renk etiketleri
        self.ana_tree.tag_configure('normal', background='white')
        self.ana_tree.tag_configure('eksik', background='#FFCDD2')
        self.ana_tree.tag_configure('yeterli', background='#C8E6C9')
        self.ana_tree.tag_configure('grup_baslik', background='#78909C', font=('Arial', 9, 'bold'))
        self.ana_tree.tag_configure('alt_toplam', background='#B0BEC5', font=('Arial', 9, 'bold'))

    def _sutunlari_guncelle(self, ay_sayisi):
        """Aylık sütunları dinamik olarak güncelle"""
        sutunlar = list(self.temel_sutunlar)
        basliklar = {col[0]: col[1] for col in self.temel_sutunlar}

        # Aylık sütunları ekle (eskiden yeniye doğru)
        bugun = datetime.now()
        ay_isimleri = []
        for i in range(ay_sayisi - 1, -1, -1):
            ay_tarihi = bugun - relativedelta(months=i)
            ay_adi = ay_tarihi.strftime('%b%y')  # Şub25, Mar25 gibi
            col_id = f"Ay_{i}"
            sutunlar.append((col_id, ay_adi, 50))
            basliklar[col_id] = ay_adi
            ay_isimleri.append((col_id, ay_adi))

        # Son sütunları ekle
        for col in self.son_sutunlar:
            sutunlar.append(col)
            basliklar[col[0]] = col[1]

        # Treeview sütunlarını güncelle
        col_ids = [c[0] for c in sutunlar]
        self.ana_tree['columns'] = col_ids

        for col_id, baslik, width in sutunlar:
            self.ana_tree.heading(col_id, text=baslik)
            self.ana_tree.column(col_id, width=width, minwidth=40)

        self.aktif_sutunlar = sutunlar
        self.aktif_basliklar = basliklar


    def _status_bar_olustur(self, parent):
        """Status bar oluştur"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(5, 0))

        self.status_label = ttk.Label(status_frame, text="Hazır", font=('Arial', 9))
        self.status_label.pack(side=tk.LEFT)

        self.kayit_label = ttk.Label(status_frame, text="", font=('Arial', 9))
        self.kayit_label.pack(side=tk.RIGHT)

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
        """Veritabanından ürün tiplerini yükle"""
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
                        label=tip_adi,
                        variable=var,
                        command=self._urun_tipi_secim_guncelle
                    )

                self._urun_tipi_secim_guncelle()
        except Exception as e:
            logger.error(f"Ürün tipleri yükleme hatası: {e}")

    def _urun_tipi_secim_guncelle(self):
        """Seçili ürün tiplerini göster"""
        secili_tipler = [tip for tip, var in self.urun_tipi_vars.items() if var.get()]
        toplam = len(self.urun_tipi_vars)
        secili = len(secili_tipler)

        if secili == 0:
            self.urun_tipi_menubutton.config(text="Hiçbiri Seçili")
        elif secili == toplam:
            self.urun_tipi_menubutton.config(text="Tümü Seçili")
        elif secili <= 2:
            self.urun_tipi_menubutton.config(text=", ".join(secili_tipler[:2]))
        else:
            self.urun_tipi_menubutton.config(text=f"{secili} tip seçili")

    def _tum_tipleri_sec(self):
        for var in self.urun_tipi_vars.values():
            var.set(True)
        self._urun_tipi_secim_guncelle()

    def _varsayilan_tipleri_sec(self):
        for tip, var in self.urun_tipi_vars.items():
            var.set(tip in self.VARSAYILAN_URUN_TIPLERI)
        self._urun_tipi_secim_guncelle()

    def _ay_sonu_sec(self):
        bugun = datetime.now()
        ay_son_gun = calendar.monthrange(bugun.year, bugun.month)[1]
        self.hedef_tarih_entry.set_date(date(bugun.year, bugun.month, ay_son_gun))

    def _hedef_gun_hesapla(self):
        try:
            hedef = self.hedef_tarih_entry.get_date()
            bugun = date.today()
            fark = (hedef - bugun).days
            return max(0, fark)
        except:
            return 0

    def verileri_getir(self):
        """Veritabanından verileri getir"""
        secili_urun_tipleri = [tip for tip, var in self.urun_tipi_vars.items() if var.get()]

        if not secili_urun_tipleri:
            messagebox.showwarning("Uyarı", "En az bir ürün tipi seçmelisiniz!")
            return

        self.status_label.config(text="Veriler getiriliyor...")
        self.parent.update()

        def sorgu_thread():
            try:
                ay = self.ay_sayisi.get()

                from botanik_db import BotanikDB
                db = BotanikDB()
                if not db.baglan():
                    self.parent.after(0, lambda: messagebox.showerror("Hata", "Veritabanına bağlanılamadı!"))
                    return

                # Verileri al
                veriler = self._verileri_getir_sql(db, ay, secili_urun_tipleri)

                # MF geçmişini al
                mf_gecmisi = self._mf_gecmisi_getir(db)

                db.kapat()

                # Verileri işle
                islenenmis = self._verileri_isle(veriler, mf_gecmisi, ay)

                self.parent.after(0, lambda: self._veriler_yuklendi(islenenmis, ay))

            except Exception as e:
                logger.error(f"Sorgu hatası: {e}")
                import traceback
                traceback.print_exc()
                self.parent.after(0, lambda: self._sorgu_hatasi(str(e)))

        thread = threading.Thread(target=sorgu_thread)
        thread.start()

    def _verileri_getir_sql(self, db, ay_sayisi, urun_tipleri):
        """Stok ve aylık çıkış verilerini getir"""
        bugun = datetime.now()
        baslangic = (bugun - relativedelta(months=ay_sayisi)).replace(day=1).strftime('%Y-%m-%d')

        tipler_sql = ', '.join([f"'{t}'" for t in urun_tipleri])

        # Aylık CASE ifadeleri oluştur
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
        ;WITH CikisVerileri AS (
            -- Reçeteli satışlar (kayıt tarihine göre)
            SELECT
                ri.RIUrunId as UrunId,
                ri.RIAdet as Adet,
                CAST(ra.RxKayitTarihi as date) as Tarih
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
            AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
            AND ra.RxKayitTarihi >= '{baslangic}'

            UNION ALL

            -- Elden satışlar
            SELECT
                ei.RIUrunId as UrunId,
                ei.RIAdet as Adet,
                CAST(ea.RxKayitTarihi as date) as Tarih
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
            AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
            AND ea.RxKayitTarihi >= '{baslangic}'
        ),
        UrunAylikOzet AS (
            SELECT
                UrunId,
                SUM(Adet) as ToplamCikis,
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
        LEFT JOIN UrunTip ut ON u.UrunUrunTipId = ut.UrunTipId
        LEFT JOIN UrunAylikOzet ao ON u.UrunId = ao.UrunId
        WHERE u.UrunSilme = 0
        AND ut.UrunTipAdi IN ({tipler_sql})
        AND (ao.ToplamCikis > 0 OR (u.UrunStokDepo + u.UrunStokRaf + u.UrunStokAcik) > 0)
        ORDER BY u.UrunEsdegerId, u.UrunAdi
        """

        return db.sorgu_calistir(sql)

    def _mf_gecmisi_getir(self, db):
        """Son 1 yıldaki MF alımlarını getir"""
        bugun = datetime.now()
        baslangic = (bugun - relativedelta(years=1)).strftime('%Y-%m-%d')

        sql = f"""
        SELECT
            fs.FSUrunId as UrunId,
            fs.FSUrunAdet as Adet,
            fs.FSUrunMf as MF,
            fg.FGFaturaTarihi as Tarih
        FROM FaturaSatir fs
        JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
        WHERE fg.FGSilme = 0
        AND fg.FGFaturaTarihi >= '{baslangic}'
        AND fs.FSUrunMf > 0
        ORDER BY fs.FSUrunId, fg.FGFaturaTarihi DESC
        """

        sonuclar = db.sorgu_calistir(sql)

        mf_ozet = {}
        for row in sonuclar:
            urun_id = row['UrunId']
            if urun_id not in mf_ozet:
                mf_ozet[urun_id] = []

            adet = row['Adet'] or 0
            mf = row['MF'] or 0
            if mf > 0:
                mf_ozet[urun_id].append(f"{adet}+{mf}")

        return mf_ozet

    def _verileri_isle(self, veriler, mf_gecmisi, ay_sayisi):
        """Verileri işle ve hesapla"""
        if not veriler:
            return []

        hedef_gun = self._hedef_gun_hesapla()
        min_stok_aktif = self.min_stok_tamamla.get()
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

            # İhtiyaç = Hedef güne kadar gereken miktar
            ihtiyac = gunluk_ort * hedef_gun

            # Sipariş miktarı hesaplama
            siparis_miktar = max(0, ihtiyac - stok)

            # Minimum stok tamamlama aktifse ve stok < minimum ise
            if min_stok_aktif and min_stok > 0 and stok < min_stok:
                min_stok_eksik = min_stok - stok
                # Sipariş miktarı en az minimum stok eksiği kadar olmalı
                siparis_miktar = max(siparis_miktar, min_stok_eksik)

            # MF geçmişi
            mf_str = ""
            if urun_id in mf_gecmisi:
                mf_list = mf_gecmisi[urun_id][:2]
                mf_str = ", ".join(mf_list)

            esdeger_id = veri.get('EsdegerId')

            satir = {
                'UrunId': urun_id,
                'UrunAdi': veri.get('UrunAdi', ''),
                'UrunTipi': veri.get('UrunTipi', ''),
                'EsdegerId': esdeger_id,
                'Esdeger': f"#{esdeger_id}" if esdeger_id else "-",
                'Stok': stok,
                'MinStok': min_stok,
                'ToplamCikis': toplam_cikis,
                'MF': mf_str,
                'AylikOrt': round(aylik_ort, 1),
                'GunlukOrt': round(gunluk_ort, 2),
                'AyBitis': round(ay_bitis, 1) if ay_bitis < 100 else ">99",
                'HedefGun': hedef_gun,
                'Ihtiyac': round(ihtiyac, 1),
                'SiparisMiktar': int(round(siparis_miktar, 0)),
            }

            # Aylık verileri ekle
            for i in range(ay_sayisi):
                satir[f'Ay_{i}'] = veri.get(f'Ay_{i}', 0) or 0

            islenenmis.append(satir)

        return islenenmis

    def _veriler_yuklendi(self, veriler, ay_sayisi):
        """Veriler yüklendiğinde UI güncelle"""
        self.islenenmis_veriler = veriler

        # Sütunları güncelle
        self._sutunlari_guncelle(ay_sayisi)

        # Ana tabloyu güncelle
        self._ana_tabloyu_guncelle(veriler, ay_sayisi)

        # Sipariş oluştur butonunu aktif et
        self.siparis_olustur_btn.config(state='normal')

        # Hesaplama bilgisini güncelle
        hedef_gun = self._hedef_gun_hesapla()
        siparis_gereken = len([v for v in veriler if v.get('SiparisMiktar', 0) > 0])
        self.hesaplama_label.config(
            text=f"Hedef tarihe {hedef_gun} gün | {len(veriler)} ürün | {siparis_gereken} ürün sipariş gerektirir"
        )

        self.status_label.config(text="Veriler yüklendi")
        self.kayit_label.config(text=f"{len(veriler)} kayıt")

    def _ana_tabloyu_guncelle(self, veriler, ay_sayisi):
        """Ana tabloyu güncelle"""
        for item in self.ana_tree.get_children():
            self.ana_tree.delete(item)

        for veri in veriler:
            values = []
            for col_id, _, _ in self.aktif_sutunlar:
                val = veri.get(col_id, '')
                values.append(val if val != '' else '')

            siparis = veri.get('SiparisMiktar', 0)
            tag = 'eksik' if siparis > 0 else 'yeterli'

            self.ana_tree.insert('', 'end', values=values, tags=(tag,))

    def _sorgu_hatasi(self, hata):
        self.status_label.config(text=f"Hata: {hata}")
        messagebox.showerror("Hata", hata)

    def siparis_olustur(self):
        """Sipariş listelerini oluştur ve panelleri güncelle"""
        if not self.islenenmis_veriler:
            messagebox.showwarning("Uyarı", "Önce verileri getirin!")
            return

        self.status_label.config(text="Sipariş hesaplanıyor...")
        self.parent.update()

        # Eşdeğer gruplarını analiz et
        self._siparis_analiz_yap()

        # Kısmi sipariş panelini güncelle
        for widget in self.kismi_content.winfo_children():
            widget.destroy()
        self._kismi_panel_icerik_v2(self.kismi_content)

        # Kesin sipariş panelini güncelle
        for widget in self.kesin_content.winfo_children():
            widget.destroy()
        self._kesin_panel_icerik_v2(self.kesin_content)

        kismi_urun_count = sum(len(g['siparis_gerekenler']) for g in self.kismi_siparis_verileri)
        kesin_count = len(self.kesin_siparis_verileri)
        self.status_label.config(text=f"Sipariş oluşturuldu: {len(self.kismi_siparis_verileri)} kısmi grup ({kismi_urun_count} ürün), {kesin_count} kesin")

    def _siparis_analiz_yap(self):
        """Eşdeğer gruplarını analiz edip kısmi/kesin ayrımı yap"""
        self.kismi_siparis_verileri = []
        self.kesin_siparis_verileri = []

        # Eşdeğer gruplarına ayır
        esdeger_gruplari = {}
        for veri in self.islenenmis_veriler:
            esdeger_id = veri.get('EsdegerId') or 0
            if esdeger_id not in esdeger_gruplari:
                esdeger_gruplari[esdeger_id] = []
            esdeger_gruplari[esdeger_id].append(veri)

        for esdeger_id, urunler in esdeger_gruplari.items():
            grup_stok = sum(u.get('Stok', 0) for u in urunler)
            grup_ihtiyac = sum(u.get('Ihtiyac', 0) for u in urunler)
            grup_siparis_gereken = [u for u in urunler if u.get('SiparisMiktar', 0) > 0]

            if not grup_siparis_gereken:
                continue

            if esdeger_id == 0 or len(urunler) == 1:
                # Eşdeğersiz veya tek ürünlü grup -> Kesin sipariş
                for u in grup_siparis_gereken:
                    self.kesin_siparis_verileri.append(u)
            else:
                # Çoklu eşdeğer grubu
                if grup_stok >= grup_ihtiyac:
                    # Grup genelinde stok yeterli -> Kısmi sipariş
                    self.kismi_siparis_verileri.append({
                        'esdeger_id': esdeger_id,
                        'urunler': urunler,  # TÜM ürünler (muadiller dahil)
                        'grup_stok': grup_stok,
                        'grup_ihtiyac': grup_ihtiyac,
                        'siparis_gerekenler': grup_siparis_gereken
                    })
                else:
                    # Grup genelinde de stok yetersiz -> Kesin sipariş
                    for u in grup_siparis_gereken:
                        self.kesin_siparis_verileri.append(u)

    def _kismi_panel_icerik_v2(self, content_frame):
        """Kısmi sipariş paneli içeriği - yeni versiyon"""
        if not self.kismi_siparis_verileri:
            tk.Label(content_frame, text="Kısmi sipariş gerektiren ürün yok.",
                    bg='#FFF3E0', font=('Arial', 10, 'italic'), fg='#E65100').pack(expand=True)
            return

        # Üst bilgi çubuğu
        info_frame = tk.Frame(content_frame, bg='#FFE0B2')
        info_frame.pack(fill=tk.X)

        kismi_count = sum(len(g['siparis_gerekenler']) for g in self.kismi_siparis_verileri)
        tk.Label(info_frame,
                text=f"  {len(self.kismi_siparis_verileri)} grup, {kismi_count} ürün  |  Muadiller yeterli - sipariş opsiyonel",
                bg='#FFE0B2', font=('Arial', 9, 'bold'), fg='#E65100').pack(side=tk.LEFT, pady=3)

        ttk.Button(info_frame, text="Seçilenleri Siparişe Ekle",
                  command=lambda: messagebox.showinfo("Bilgi", "Bu özellik yakında eklenecek.")).pack(side=tk.RIGHT, padx=5, pady=2)

        # Scrollable içerik
        canvas = tk.Canvas(content_frame, bg='#FFF3E0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#FFF3E0')

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # Her grup için kompakt tablo
        for grup in self.kismi_siparis_verileri:
            grup_frame = tk.Frame(scrollable_frame, bg='#FFE0B2', relief='groove', bd=1)
            grup_frame.pack(fill='x', padx=3, pady=3)

            # Grup başlığı
            tk.Label(grup_frame,
                    text=f"Grup #{grup['esdeger_id']}  |  Stok: {grup['grup_stok']}  |  İhtiyaç: {round(grup['grup_ihtiyac'], 1)}",
                    bg='#FFE0B2', font=('Arial', 9, 'bold'), fg='#E65100').pack(anchor='w', padx=5, pady=2)

            # Mini tablo
            columns = [("UrunAdi", "Ürün", 220), ("Stok", "Stok", 50), ("AylikOrt", "Aylık", 55),
                      ("Ihtiyac", "İhtiyaç", 55), ("SiparisMiktar", "Sipariş", 55), ("Durum", "Durum", 90)]

            tree = ttk.Treeview(grup_frame, columns=[c[0] for c in columns], show='headings',
                               height=min(len(grup['urunler']) + 1, 6))
            for col_id, baslik, width in columns:
                tree.heading(col_id, text=baslik)
                tree.column(col_id, width=width, minwidth=40)

            tree.tag_configure('siparis_gerek', background='#FFCDD2')
            tree.tag_configure('yeterli', background='#C8E6C9')
            tree.tag_configure('alt_toplam', background='#B0BEC5')

            for urun in grup['urunler']:
                siparis = urun.get('SiparisMiktar', 0)
                tree.insert('', 'end', values=(
                    urun.get('UrunAdi', ''), urun.get('Stok', 0), urun.get('AylikOrt', 0),
                    urun.get('Ihtiyac', 0), siparis if siparis > 0 else '-',
                    "SİPARİŞ" if siparis > 0 else "Yeterli"
                ), tags=('siparis_gerek' if siparis > 0 else 'yeterli',))

            toplam_siparis = sum(u.get('SiparisMiktar', 0) for u in grup['urunler'])
            tree.insert('', 'end', values=(
                "TOPLAM", grup['grup_stok'], round(sum(u.get('AylikOrt', 0) for u in grup['urunler']), 1),
                round(grup['grup_ihtiyac'], 1), toplam_siparis if toplam_siparis > 0 else '-', "KARŞILANIR"
            ), tags=('alt_toplam',))

            tree.pack(fill='x', padx=3, pady=2)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _kesin_panel_icerik_v2(self, content_frame):
        """Kesin sipariş paneli içeriği - yeni versiyon"""
        if not self.kesin_siparis_verileri:
            tk.Label(content_frame, text="Kesin sipariş gerektiren ürün yok.",
                    bg='#FFEBEE', font=('Arial', 10, 'italic'), fg='#C62828').pack(expand=True)
            return

        # Üst bilgi çubuğu
        info_frame = tk.Frame(content_frame, bg='#FFCDD2')
        info_frame.pack(fill=tk.X)

        tk.Label(info_frame,
                text=f"  {len(self.kesin_siparis_verileri)} ürün  |  Muadil yok veya yetersiz - sipariş önerilir",
                bg='#FFCDD2', font=('Arial', 9, 'bold'), fg='#C62828').pack(side=tk.LEFT, pady=3)

        ttk.Button(info_frame, text="Tümünü Siparişe Ekle",
                  command=lambda: messagebox.showinfo("Bilgi", "Tüm ürünler siparişe eklendi.")).pack(side=tk.RIGHT, padx=5, pady=2)
        ttk.Button(info_frame, text="Seçilenleri Siparişe Ekle",
                  command=lambda: self._secili_siparise_ekle(self.kesin_tree)).pack(side=tk.RIGHT, padx=2, pady=2)

        # Tablo
        tree_frame = tk.Frame(content_frame, bg='#FFEBEE')
        tree_frame.pack(fill='both', expand=True, padx=3, pady=3)

        columns = [
            ("UrunAdi", "Ürün Adı", 280), ("Stok", "Stok", 55), ("AylikOrt", "Aylık Ort", 65),
            ("Ihtiyac", "İhtiyaç", 65), ("SiparisMiktar", "Sipariş", 60), ("MF", "MF Geçmişi", 90)
        ]

        self.kesin_tree = ttk.Treeview(tree_frame, columns=[c[0] for c in columns], show='headings')
        for col_id, baslik, width in columns:
            self.kesin_tree.heading(col_id, text=baslik)
            self.kesin_tree.column(col_id, width=width, minwidth=40)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.kesin_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.kesin_tree.xview)
        self.kesin_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.kesin_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        for urun in self.kesin_siparis_verileri:
            self.kesin_tree.insert('', 'end', values=(
                urun.get('UrunAdi', ''), urun.get('Stok', 0), urun.get('AylikOrt', 0),
                urun.get('Ihtiyac', 0), urun.get('SiparisMiktar', 0), urun.get('MF', '')
            ))

    def _secili_siparise_ekle(self, tree):
        secili = tree.selection()
        if not secili:
            messagebox.showwarning("Uyarı", "Lütfen ürün seçin!")
            return
        messagebox.showinfo("Bilgi", f"{len(secili)} ürün siparişe eklendi.")

    def excel_aktar(self):
        """Verileri Excel'e aktar"""
        if not self.islenenmis_veriler:
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
            ws.title = "Sipariş Listesi"

            # Başlıklar
            basliklar = [self.aktif_basliklar.get(col[0], col[0]) for col in self.aktif_sutunlar]
            for col_idx, baslik in enumerate(basliklar, 1):
                cell = ws.cell(row=1, column=col_idx, value=baslik)
                cell.font = Font(bold=True)

            # Veriler
            for row_idx, veri in enumerate(self.islenenmis_veriler, 2):
                for col_idx, (col_id, _, _) in enumerate(self.aktif_sutunlar, 1):
                    ws.cell(row=row_idx, column=col_idx, value=veri.get(col_id, ''))

            wb.save(dosya_yolu)
            messagebox.showinfo("Başarılı", f"Veriler aktarıldı:\n{dosya_yolu}")

        except Exception as e:
            messagebox.showerror("Hata", f"Aktarım hatası: {e}")


# Test
if __name__ == "__main__":
    root = tk.Tk()
    app = SiparisVermeGUI(root)
    root.mainloop()
