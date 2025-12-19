"""
Botanik Bot - Kasa Kapatma Modülü
Günlük kasa sayımı, POS, IBAN ve mutabakat işlemleri
Yeniden tasarlanmış versiyon - Wizard destekli
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Yeni modülleri import et
try:
    from kasa_wizard import KasaWizard
    from kasa_kontrol_listesi import KasaKontrolListesi
    from kasa_whatsapp import KasaWhatsAppRapor, KasaWhatsAppPenceresi
    from kasa_yazici import KasaYazici, YaziciSecimPenceresi
    from kasa_gecmis import KasaGecmisiPenceresi
    YENI_MODULLER_YUKLENDI = True
except ImportError as e:
    logger.warning(f"Yeni modüller yüklenemedi: {e}")
    YENI_MODULLER_YUKLENDI = False


class KasaKapatmaModul:
    """Kasa Kapatma - Günlük Mutabakat Sistemi"""

    # Küpürler (büyükten küçüğe)
    KUPURLER = [
        {"deger": 5000, "aciklama": "5000 TL"},
        {"deger": 2000, "aciklama": "2000 TL"},
        {"deger": 1000, "aciklama": "1000 TL"},
        {"deger": 500, "aciklama": "500 TL"},
        {"deger": 200, "aciklama": "200 TL"},
        {"deger": 100, "aciklama": "100 TL"},
        {"deger": 50, "aciklama": "50 TL"},
        {"deger": 20, "aciklama": "20 TL"},
        {"deger": 10, "aciklama": "10 TL"},
        {"deger": 5, "aciklama": "5 TL"},
        {"deger": 1, "aciklama": "1 TL"},
        {"deger": 0.50, "aciklama": "50 Kr"},
        {"deger": 0.25, "aciklama": "25 Kr"},
        {"deger": 0.10, "aciklama": "10 Kr"},
        {"deger": 0.05, "aciklama": "5 Kr"},
    ]

    def __init__(self, root=None, ana_menu_callback=None):
        self.ana_menu_callback = ana_menu_callback

        if root is None:
            self.root = tk.Tk()
        else:
            self.root = root

        self.root.title("Kasa Kapatma - Günlük Mutabakat")

        # Tam ekran
        self.root.state('zoomed')
        self.root.resizable(True, True)

        # Renkler - Görsel Hiyerarşi
        self.bg_color = '#F5F5F5'
        self.header_color = '#1565C0'

        # Detay satırları renkleri (sönük)
        self.detay_bg = '#FAFAFA'
        self.detay_fg = '#666666'

        # Ara toplam renkleri (vurgulu)
        self.ara_toplam_bg = '#E3F2FD'
        self.ara_toplam_fg = '#1565C0'

        # Genel toplam renkleri (en vurgulu)
        self.genel_toplam_bg = '#6A1B9A'
        self.genel_toplam_fg = '#FFEB3B'

        # Son genel toplam (en büyük, en vurgulu)
        self.son_genel_bg = '#311B92'
        self.son_genel_fg = '#FFD600'

        # Bölüm renkleri
        self.section_colors = {
            'baslangic': '#E8F5E9',   # Açık yeşil
            'sayim': '#E8F5E9',       # Açık yeşil
            'pos': '#E3F2FD',         # Açık mavi
            'iban': '#E0F7FA',        # Açık cyan
            'masraf': '#FFF3E0',      # Açık turuncu
            'silinen': '#FCE4EC',     # Açık pembe
            'alinan': '#FFEBEE',      # Açık kırmızı
            'botanik': '#FFFDE7',     # Açık sarı
            'ozet': '#F3E5F5',        # Açık mor
        }

        self.root.configure(bg=self.bg_color)

        # Ayarları yükle
        self.ayarlar = self.ayarlari_yukle()

        # Veritabanı
        self.db_baglantisi_kur()

        # Değişkenler
        # Başlangıç kasası küpürleri
        self.baslangic_kupur_vars = {}
        self.baslangic_detay_acik = False
        self.baslangic_detay_frame = None

        # Gün sonu sayım küpürleri
        self.sayim_vars = {}
        self.sayim_toplam_labels = {}

        # POS ve IBAN
        self.pos_vars = []          # 8 POS alanı (4 EczacıPOS + 4 Ingenico)
        self.iban_vars = []         # 4 IBAN alanı

        # B Bölümü - Masraflar, Silinen, Alınan
        self.masraf_vars = []       # 4 masraf (tutar, açıklama)
        self.silinen_vars = []      # 4 silinen reçete (tutar, açıklama)
        self.gun_ici_alinan_vars = []  # 3 gün içi alınan (tutar, açıklama)

        # Botanik verileri
        self.botanik_nakit_var = tk.StringVar(value="0")
        self.botanik_pos_var = tk.StringVar(value="0")
        self.botanik_iban_var = tk.StringVar(value="0")

        # Para ayırma değişkenleri
        self.kalan_vars = {}          # Kasada kalan küpürler
        self.ayrilan_vars = {}        # Ayrılan küpürler
        self.slider_vars = {}         # Slider değerleri
        self.para_ayirma_penceresi = None
        self.ertesi_gun_belirlendi = False
        self.ayrilan_para_belirlendi = False

        # Wizard değişkenleri
        self.wizard = None
        self.wizard_aktif = False

        # Yeni veri değişkenleri
        self.ertesi_gun_toplam_data = 0
        self.ertesi_gun_kupurler_data = {}
        self.ayrilan_toplam_data = 0
        self.ayrilan_kupurler_data = {}

        # Pencere kapatma
        self.root.protocol("WM_DELETE_WINDOW", self.kapat)

        # Önceki gün verisini yükle (son kapatmadaki ertesi_gun_kasasi değerleri)
        self.onceki_gun_verisi = self.onceki_gun_kasasi_yukle()

        self.arayuz_olustur()
        self.hesaplari_guncelle()

        # Wizard modunu kontrol et ve gerekirse başlat
        if self.ayarlar.get("yonerge_aktif", False) and YENI_MODULLER_YUKLENDI:
            self.root.after(500, self.wizard_baslat)

    def ayarlari_yukle(self):
        """Kasa ayarlarını yükle"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            ayar_dosyasi = Path(script_dir) / "kasa_ayarlari.json"

            if ayar_dosyasi.exists():
                with open(ayar_dosyasi, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # Varsayılan ayarlar
                varsayilan = {
                    "aktif_kupurler": {str(k["deger"]): True for k in self.KUPURLER}
                }
                self.ayarlari_kaydet(varsayilan)
                return varsayilan
        except Exception as e:
            logger.error(f"Ayar yükleme hatası: {e}")
            return {"aktif_kupurler": {str(k["deger"]): True for k in self.KUPURLER}}

    def ayarlari_kaydet(self, ayarlar=None):
        """Kasa ayarlarını kaydet"""
        try:
            if ayarlar is None:
                ayarlar = self.ayarlar
            script_dir = os.path.dirname(os.path.abspath(__file__))
            ayar_dosyasi = Path(script_dir) / "kasa_ayarlari.json"
            with open(ayar_dosyasi, 'w', encoding='utf-8') as f:
                json.dump(ayarlar, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ayar kaydetme hatası: {e}")

    def entry_fokus_secim(self, event):
        """Entry'ye tiklandiginda icerigi sec"""
        event.widget.select_range(0, tk.END)
        event.widget.icursor(tk.END)

    def kupur_aktif_mi(self, deger):
        """Küpürün aktif olup olmadığını kontrol et"""
        aktif_kupurler = self.ayarlar.get("aktif_kupurler", {})
        # Tutarlı key formatı kullan
        key = self.kupur_key(deger)
        return aktif_kupurler.get(key, True)

    def kupur_key(self, deger):
        """Küpür değerini tutarlı string formatına çevir"""
        if isinstance(deger, float) and deger == int(deger):
            return str(int(deger))  # 5000.0 -> "5000"
        elif isinstance(deger, float):
            return str(deger)  # 0.5 -> "0.5"
        else:
            return str(deger)  # 5000 -> "5000"

    def db_baglantisi_kur(self):
        """Veritabanı bağlantısını kur ve tabloları oluştur"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_yolu = Path(script_dir) / "oturum_raporlari.db"
            self.conn = sqlite3.connect(str(self.db_yolu), check_same_thread=False)
            self.cursor = self.conn.cursor()

            # Kasa kapatma tablosu - güncellenmiş şema
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS kasa_kapatma (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tarih TEXT NOT NULL,
                    saat TEXT NOT NULL,
                    baslangic_kasasi REAL DEFAULT 0,
                    baslangic_kupurler_json TEXT,
                    sayim_toplam REAL DEFAULT 0,
                    pos_toplam REAL DEFAULT 0,
                    iban_toplam REAL DEFAULT 0,
                    masraf_toplam REAL DEFAULT 0,
                    silinen_etki_toplam REAL DEFAULT 0,
                    gun_ici_alinan_toplam REAL DEFAULT 0,
                    nakit_toplam REAL DEFAULT 0,
                    genel_toplam REAL DEFAULT 0,
                    son_genel_toplam REAL DEFAULT 0,
                    botanik_nakit REAL DEFAULT 0,
                    botanik_pos REAL DEFAULT 0,
                    botanik_iban REAL DEFAULT 0,
                    botanik_genel_toplam REAL DEFAULT 0,
                    fark REAL DEFAULT 0,
                    ertesi_gun_kasasi REAL DEFAULT 0,
                    ertesi_gun_kupurler_json TEXT,
                    detay_json TEXT,
                    olusturma_zamani TEXT NOT NULL
                )
            ''')

            # Yeni sütunları ekle (eğer yoksa)
            try:
                self.cursor.execute("ALTER TABLE kasa_kapatma ADD COLUMN baslangic_kupurler_json TEXT")
            except sqlite3.OperationalError:
                pass  # Sütun zaten var

            try:
                self.cursor.execute("ALTER TABLE kasa_kapatma ADD COLUMN ertesi_gun_kupurler_json TEXT")
            except sqlite3.OperationalError:
                pass

            try:
                self.cursor.execute("ALTER TABLE kasa_kapatma ADD COLUMN son_genel_toplam REAL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

            try:
                self.cursor.execute("ALTER TABLE kasa_kapatma ADD COLUMN ayrilan_para REAL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

            try:
                self.cursor.execute("ALTER TABLE kasa_kapatma ADD COLUMN ayrilan_kupurler_json TEXT")
            except sqlite3.OperationalError:
                pass

            self.conn.commit()
            logger.info("Kasa kapatma DB tabloları oluşturuldu")

        except Exception as e:
            logger.error(f"Kasa DB hatası: {e}")

    def onceki_gun_kasasi_yukle(self):
        """Bir önceki kapatmadan ertesi gün kasasını yükle"""
        try:
            self.cursor.execute('''
                SELECT ertesi_gun_kasasi, ertesi_gun_kupurler_json, detay_json
                FROM kasa_kapatma
                ORDER BY id DESC LIMIT 1
            ''')
            sonuc = self.cursor.fetchone()
            if sonuc:
                toplam = sonuc[0] if sonuc[0] else 0
                kupurler_json = sonuc[1] if sonuc[1] else None
                detay_json = sonuc[2] if sonuc[2] else None

                kupurler = {}
                if kupurler_json:
                    try:
                        kupurler = json.loads(kupurler_json)
                    except json.JSONDecodeError:
                        pass
                elif detay_json:
                    # Eski formatı destekle
                    try:
                        detay = json.loads(detay_json)
                        kupurler = detay.get("sayim", {})
                    except json.JSONDecodeError:
                        pass

                logger.info(f"Önceki gün kasası yüklendi: {toplam}")
                return {"toplam": toplam, "kupurler": kupurler}
            return {"toplam": 0, "kupurler": {}}
        except Exception as e:
            logger.error(f"Önceki gün kasası yükleme hatası: {e}")
            return {"toplam": 0, "kupurler": {}}

    def arayuz_olustur(self):
        """Ana arayuzu olustur - Sol %60 (A+B ustte, 9.tablo altta) | Sag %40 (10, 11, butonlar)"""
        # Ust bar
        self.ust_bar_olustur()

        # Ana container - tek ekrana sigacak
        self.scrollable_frame = tk.Frame(self.root, bg=self.bg_color)
        self.scrollable_frame.pack(fill="both", expand=True, padx=3, pady=2)

        # ANA YATAY DUZEN: Sol %60 | Sag %40
        ana_frame = tk.Frame(self.scrollable_frame, bg=self.bg_color)
        ana_frame.pack(fill="both", expand=True)

        # Grid yapilandirmasi - 2 sutun %60-%40
        ana_frame.columnconfigure(0, weight=60)  # Sol %60
        ana_frame.columnconfigure(1, weight=40)  # Sag %40
        ana_frame.rowconfigure(0, weight=1)

        # ===== SOL TARAF (%60) - A+B ustte, 9.tablo altta =====
        sol_taraf = tk.Frame(ana_frame, bg=self.bg_color)
        sol_taraf.grid(row=0, column=0, sticky='nsew', padx=(0, 3))

        # Sol taraf: Ust kisim (A+B yan yana) + Alt kisim (9.tablo)
        sol_taraf.rowconfigure(0, weight=75)  # A+B bolumu (%75)
        sol_taraf.rowconfigure(1, weight=25)  # 9) tablo (%25)
        sol_taraf.columnconfigure(0, weight=1)

        # UST KISIM - A ve B yan yana (her biri %30 toplam ekranin)
        ab_frame = tk.Frame(sol_taraf, bg=self.bg_color)
        ab_frame.grid(row=0, column=0, sticky='nsew')

        # A ve B esit genislikte
        ab_frame.columnconfigure(0, weight=1)  # A %50 (sol tarafin)
        ab_frame.columnconfigure(1, weight=1)  # B %50 (sol tarafin)
        ab_frame.rowconfigure(0, weight=1)

        # A Bolumu (%30 ekran) - 1, 2, 3 numarali tablolar
        self.a_bolumu_frame = tk.Frame(ab_frame, bg=self.bg_color)
        self.a_bolumu_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 2))

        # B Bolumu (%30 ekran) - 4, 5, 6, 7, 8 numarali tablolar
        self.b_bolumu_frame = tk.Frame(ab_frame, bg=self.bg_color)
        self.b_bolumu_frame.grid(row=0, column=1, sticky='nsew', padx=(2, 0))

        # A Bolumu icerigi (1, 2, 3)
        self.baslangic_kasasi_bolumu_olustur()  # 1)
        self.gun_sonu_sayim_bolumu_olustur()     # 2)
        self.pos_bolumu_olustur()               # 3) POS + IBAN
        self.iban_bolumu_olustur()

        # B Bolumu icerigi (4, 5, 6, 7, 8)
        self.masraf_bolumu_olustur()            # 4)
        self.silinen_bolumu_olustur()           # 5)
        self.gun_ici_alinan_bolumu_olustur()    # 6)
        self.duzeltilmis_nakit_bolumu_olustur() # 7)
        self.botanik_bolumu_olustur()           # 8)

        # ALT KISIM - 9) Karsilastirma tablosu (A+B altinda, tum sol %60 genislik)
        self.tablo_frame = tk.Frame(sol_taraf, bg=self.bg_color)
        self.tablo_frame.grid(row=1, column=0, sticky='nsew', pady=(3, 0))

        # ===== SAG TARAF (%40) - 10 (%40), 11 (%40), butonlar (%20) dikey =====
        sag_taraf = tk.Frame(ana_frame, bg=self.bg_color)
        sag_taraf.grid(row=0, column=1, sticky='nsew', padx=(3, 0))

        # Sag taraf dikey duzen: 10 (%40) + 11 (%40) + butonlar (%20)
        sag_taraf.rowconfigure(0, weight=40)   # 10) Arti/Eksi bolumu
        sag_taraf.rowconfigure(1, weight=40)   # 11) Kasa tablosu
        sag_taraf.rowconfigure(2, weight=20)   # Butonlar
        sag_taraf.columnconfigure(0, weight=1)

        # 10) Arti/Eksi sebepler alani (ust %40)
        self.sebepler_alan = tk.Frame(sag_taraf, bg=self.bg_color)
        self.sebepler_alan.grid(row=0, column=0, sticky='nsew', pady=(0, 2))

        # 11) Ertesi gun kasasi ve ayrilan paralar tablosu alani (orta %40)
        self.para_ayirma_frame = tk.Frame(sag_taraf, bg=self.bg_color)
        self.para_ayirma_frame.grid(row=1, column=0, sticky='nsew', pady=(2, 2))

        # Butonlar alani (alt %20) - alta yapisik
        self.butonlar_frame = tk.Frame(sag_taraf, bg='#ECEFF1')
        self.butonlar_frame.grid(row=2, column=0, sticky='sew', pady=(2, 0))

        # Bolumleri olustur
        self.karsilastirma_tablosu_olustur()   # 9) Botanik/Sayim farklari
        self.arti_eksi_listesi_olustur()       # 10) Sabit liste
        self.kasa_tablosu_olustur()            # 11) Kasa tablosu
        self.alt_butonlar_olustur()            # Butonlar

    def ust_bar_olustur(self):
        """Üst bar - başlık ve butonlar"""
        top_bar = tk.Frame(self.root, bg=self.header_color, height=60)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        # Sol taraf - Ana Sayfa ve Ayarlar
        sol_frame = tk.Frame(top_bar, bg=self.header_color)
        sol_frame.pack(side="left", padx=10)

        if self.ana_menu_callback:
            ana_sayfa_btn = tk.Button(
                sol_frame,
                text="Ana Sayfa",
                font=("Arial", 10, "bold"),
                bg="#0D47A1",
                fg="white",
                activebackground="#1565C0",
                cursor="hand2",
                bd=0,
                padx=15,
                pady=5,
                command=self.ana_sayfaya_don
            )
            ana_sayfa_btn.pack(side="left", padx=5, pady=12)

        ayarlar_btn = tk.Button(
            sol_frame,
            text="Ayarlar",
            font=("Arial", 10, "bold"),
            bg="#0D47A1",
            fg="white",
            activebackground="#1565C0",
            cursor="hand2",
            bd=0,
            padx=15,
            pady=5,
            command=self.ayarlar_penceresi_ac
        )
        ayarlar_btn.pack(side="left", padx=5, pady=12)

        # Wizard Başlat butonu
        if YENI_MODULLER_YUKLENDI:
            wizard_btn = tk.Button(
                sol_frame,
                text="Wizard Başlat",
                font=("Arial", 10, "bold"),
                bg="#FF9800",
                fg="white",
                activebackground="#F57C00",
                cursor="hand2",
                bd=0,
                padx=15,
                pady=5,
                command=self.wizard_baslat
            )
            wizard_btn.pack(side="left", padx=5, pady=12)

        # Kurulum Rehberi butonu
        rehber_btn = tk.Button(
            sol_frame,
            text="?",
            font=("Arial", 10, "bold"),
            bg="#607D8B",
            fg="white",
            activebackground="#455A64",
            cursor="hand2",
            bd=0,
            width=3,
            command=self.kurulum_rehberi_ac
        )
        rehber_btn.pack(side="left", padx=5, pady=12)

        # Orta - Başlık
        title = tk.Label(
            top_bar,
            text="KASA KAPATMA / GÜNLÜK MUTABAKAT",
            font=("Arial", 16, "bold"),
            bg=self.header_color,
            fg='white'
        )
        title.pack(side="left", expand=True)

        # Sağ taraf - Temizle ve Geçmiş Kayıtlar
        sag_frame = tk.Frame(top_bar, bg=self.header_color)
        sag_frame.pack(side="right", padx=10)

        # WhatsApp butonu
        if YENI_MODULLER_YUKLENDI:
            whatsapp_btn = tk.Button(
                sag_frame,
                text="WhatsApp",
                font=("Arial", 10, "bold"),
                bg='#25D366',
                fg='white',
                activebackground='#128C7E',
                cursor='hand2',
                bd=0,
                padx=15,
                pady=5,
                command=self.whatsapp_rapor_gonder
            )
            whatsapp_btn.pack(side="left", padx=5, pady=12)

        temizle_btn = tk.Button(
            sag_frame,
            text="Temizle",
            font=("Arial", 10, "bold"),
            bg='#F44336',
            fg='white',
            activebackground='#D32F2F',
            cursor='hand2',
            bd=0,
            padx=15,
            pady=5,
            command=self.temizle
        )
        temizle_btn.pack(side="left", padx=5, pady=12)

        gecmis_btn = tk.Button(
            sag_frame,
            text="Geçmiş Kayıtlar",
            font=("Arial", 10, "bold"),
            bg='#2196F3',
            fg='white',
            activebackground='#1976D2',
            cursor='hand2',
            bd=0,
            padx=15,
            pady=5,
            command=self.gecmis_goster
        )
        gecmis_btn.pack(side="left", padx=5, pady=12)

        # Tarih/Saat
        self.tarih_label = tk.Label(
            sag_frame,
            text=datetime.now().strftime("%d.%m.%Y %H:%M"),
            font=("Arial", 10),
            bg=self.header_color,
            fg='#B3E5FC'
        )
        self.tarih_label.pack(side="left", padx=10, pady=12)

    def baslangic_kasasi_bolumu_olustur(self):
        """1) Başlangıç kasası bölümü - sabit görünüm, dolgun"""
        frame = tk.LabelFrame(
            self.a_bolumu_frame,
            text="1) BAŞLANGIÇ KASASI",
            font=("Arial", 11, "bold"),
            bg=self.section_colors['baslangic'],
            fg='#1B5E20',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True, pady=2)

        # Toplam satırı
        toplam_frame = tk.Frame(frame, bg='#A5D6A7')
        toplam_frame.pack(fill="x", pady=2)

        tk.Label(
            toplam_frame,
            text="Başlangıç Kasası:",
            font=("Arial", 11, "bold"),
            bg='#A5D6A7',
            fg='#1B5E20'
        ).pack(side="left", padx=5, pady=3)

        # Toplam değeri
        baslangic_toplam = self.onceki_gun_verisi.get("toplam", 0)
        self.baslangic_toplam_var = tk.StringVar(value=f"{baslangic_toplam:,.2f}")

        self.baslangic_toplam_label = tk.Label(
            toplam_frame,
            textvariable=self.baslangic_toplam_var,
            font=("Arial", 13, "bold"),
            bg='#A5D6A7',
            fg='#1B5E20',
            width=12,
            anchor='e'
        )
        self.baslangic_toplam_label.pack(side="right", padx=5, pady=3)

        # Detay container - sabit görünür
        self.baslangic_detay_container = tk.Frame(frame, bg=self.section_colors['baslangic'])
        self.baslangic_detay_container.pack(fill="x", pady=2)

        # Küpür değişkenlerini oluştur
        onceki_kupurler = self.onceki_gun_verisi.get("kupurler", {})
        for kupur in self.KUPURLER:
            if self.kupur_aktif_mi(kupur["deger"]):
                var = tk.StringVar(value=str(onceki_kupurler.get(str(kupur["deger"]), 0)))
                self.baslangic_kupur_vars[kupur["deger"]] = var
                var.trace_add('write', lambda *args: self.baslangic_toplam_hesapla())

        # Detayı hemen oluştur (sabit görünüm)
        self.baslangic_detay_olustur_sabit()

    def baslangic_detay_toggle(self):
        """Başlangıç kasası detayını aç/kapa - artık kullanılmıyor (sabit görünüm)"""
        pass  # Sabit görünüm olduğu için toggle gerekmiyor

    def baslangic_detay_olustur_sabit(self):
        """Başlangıç kasası detay panelini oluştur - sabit görünüm, dolgun"""
        # Önceki içeriği temizle
        for widget in self.baslangic_detay_container.winfo_children():
            widget.destroy()

        # Başlık
        header = tk.Frame(self.baslangic_detay_container, bg='#C8E6C9')
        header.pack(fill="x", pady=2)
        tk.Label(header, text="Küpür", font=("Arial", 10, "bold"), bg='#C8E6C9', width=8).pack(side="left", padx=2)
        tk.Label(header, text="Adet", font=("Arial", 10, "bold"), bg='#C8E6C9', width=6).pack(side="left", padx=2)
        tk.Label(header, text="Toplam", font=("Arial", 10, "bold"), bg='#C8E6C9', width=10).pack(side="left", padx=2)

        # Küpür satırları
        for kupur in self.KUPURLER:
            if self.kupur_aktif_mi(kupur["deger"]):
                self.baslangic_kupur_satiri_olustur_sabit(kupur)

    def baslangic_detay_olustur(self):
        """Başlangıç kasası detay panelini oluştur - eski fonksiyon (uyumluluk için)"""
        self.baslangic_detay_olustur_sabit()

    def baslangic_kupur_satiri_olustur_sabit(self, kupur):
        """Başlangıç kasası küpür satırı - dolgun"""
        deger = kupur["deger"]
        row = tk.Frame(self.baslangic_detay_container, bg=self.section_colors['baslangic'])
        row.pack(fill="x", pady=1)

        tk.Label(
            row,
            text=kupur["aciklama"],
            font=("Arial", 10),
            bg=self.section_colors['baslangic'],
            fg=self.detay_fg,
            width=8,
            anchor='w'
        ).pack(side="left", padx=2)

        # Adet entry
        var = self.baslangic_kupur_vars.get(deger)
        if var is None:
            var = tk.StringVar(value="0")
            self.baslangic_kupur_vars[deger] = var

        entry = tk.Entry(
            row,
            textvariable=var,
            font=("Arial", 10),
            width=5,
            justify='center'
        )
        entry.pack(side="left", padx=3)
        entry.bind('<FocusIn>', self.entry_fokus_secim)

        # Satır toplamı
        try:
            adet = int(var.get() or 0)
            toplam = adet * deger
        except ValueError:
            toplam = 0

        toplam_label = tk.Label(
            row,
            text=f"{toplam:,.2f}",
            font=("Arial", 10),
            bg=self.section_colors['baslangic'],
            fg=self.detay_fg,
            width=10,
            anchor='e'
        )
        toplam_label.pack(side="left", padx=2)

        # Değişiklik izleme
        def guncelle(*args):
            try:
                adet = int(var.get() or 0)
                t = adet * deger
                toplam_label.config(text=f"{t:,.2f}")
            except ValueError:
                toplam_label.config(text="0.00")
            self.baslangic_toplam_hesapla()

        var.trace_add('write', guncelle)

    def baslangic_kupur_satiri_olustur(self, kupur):
        """Başlangıç kasası küpür satırı - eski fonksiyon (uyumluluk için)"""
        self.baslangic_kupur_satiri_olustur_sabit(kupur)

    def baslangic_toplam_hesapla(self):
        """Başlangıç kasası toplamını hesapla"""
        toplam = 0
        for deger, var in self.baslangic_kupur_vars.items():
            try:
                adet = int(var.get() or 0)
                toplam += adet * deger
            except ValueError:
                pass
        self.baslangic_toplam_var.set(f"{toplam:,.2f}")
        self.hesaplari_guncelle()

    def gun_sonu_sayim_bolumu_olustur(self):
        """2) Gün sonu kasa sayımı bölümü - dolgun"""
        frame = tk.LabelFrame(
            self.a_bolumu_frame,
            text="2) AKŞAM KASA SAYIMI",
            font=("Arial", 11, "bold"),
            bg=self.section_colors['sayim'],
            fg='#1B5E20',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True, pady=2)

        # Başlık
        header = tk.Frame(frame, bg='#A5D6A7')
        header.pack(fill="x", pady=2)
        tk.Label(header, text="Küpür", font=("Arial", 10, "bold"), bg='#A5D6A7', width=7).pack(side="left", padx=2)
        tk.Label(header, text="Adet", font=("Arial", 10, "bold"), bg='#A5D6A7', width=8).pack(side="left", padx=2)
        tk.Label(header, text="Toplam", font=("Arial", 10, "bold"), bg='#A5D6A7', width=10).pack(side="left", padx=2)

        # Küpür satırları
        for kupur in self.KUPURLER:
            if self.kupur_aktif_mi(kupur["deger"]):
                self.sayim_kupur_satiri_olustur(frame, kupur)

        # Sayım toplamı
        toplam_frame = tk.Frame(frame, bg=self.ara_toplam_bg)
        toplam_frame.pack(fill="x", pady=(3, 0))

        tk.Label(
            toplam_frame,
            text="SAYIM TOP:",
            font=("Arial", 11, "bold"),
            bg=self.ara_toplam_bg,
            fg=self.ara_toplam_fg
        ).pack(side="left", padx=5, pady=3)

        self.sayim_toplam_label = tk.Label(
            toplam_frame,
            text="0,00 TL",
            font=("Arial", 12, "bold"),
            bg=self.ara_toplam_bg,
            fg=self.ara_toplam_fg
        )
        self.sayim_toplam_label.pack(side="right", padx=5, pady=3)

    def sayim_kupur_satiri_olustur(self, parent, kupur):
        """Sayım küpür satırı - dolgun"""
        deger = kupur["deger"]
        row = tk.Frame(parent, bg=self.section_colors['sayim'])
        row.pack(fill="x", pady=1)

        tk.Label(
            row,
            text=kupur["aciklama"],
            font=("Arial", 10),
            bg=self.section_colors['sayim'],
            fg='#1B5E20',
            width=7,
            anchor='w'
        ).pack(side="left", padx=2)

        # Adet frame (artı/eksi butonları ile)
        adet_frame = tk.Frame(row, bg=self.section_colors['sayim'])
        adet_frame.pack(side="left")

        tk.Button(
            adet_frame,
            text="-",
            font=("Arial", 9, "bold"),
            bg='#FFCDD2',
            fg='#C62828',
            width=2,
            bd=0,
            command=lambda d=deger: self.sayim_adet_degistir(d, -1)
        ).pack(side="left")

        var = tk.StringVar(value="0")
        self.sayim_vars[deger] = var

        entry = tk.Entry(
            adet_frame,
            textvariable=var,
            font=("Arial", 10),
            width=5,
            justify='center'
        )
        entry.pack(side="left", padx=2)
        entry.bind('<KeyRelease>', lambda e, d=deger: self.sayim_satir_guncelle(d))
        entry.bind('<FocusIn>', self.entry_fokus_secim)

        tk.Button(
            adet_frame,
            text="+",
            font=("Arial", 9, "bold"),
            bg='#C8E6C9',
            fg='#2E7D32',
            width=2,
            bd=0,
            command=lambda d=deger: self.sayim_adet_degistir(d, 1)
        ).pack(side="left")

        # Satır toplamı
        toplam_label = tk.Label(
            row,
            text="0,00",
            font=("Arial", 10),
            bg=self.section_colors['sayim'],
            fg=self.detay_fg,
            width=10,
            anchor='e'
        )
        toplam_label.pack(side="left", padx=2)
        self.sayim_toplam_labels[deger] = toplam_label

    def sayim_adet_degistir(self, deger, miktar):
        """Sayım adetini değiştir"""
        try:
            mevcut = int(self.sayim_vars[deger].get() or 0)
            yeni = max(0, mevcut + miktar)
            self.sayim_vars[deger].set(str(yeni))
            self.sayim_satir_guncelle(deger)
        except ValueError:
            self.sayim_vars[deger].set("0")

    def sayim_satir_guncelle(self, deger):
        """Sayım satır toplamını güncelle"""
        try:
            adet = int(self.sayim_vars[deger].get() or 0)
            toplam = adet * deger
            self.sayim_toplam_labels[deger].config(text=f"{toplam:,.2f}")
        except ValueError:
            self.sayim_toplam_labels[deger].config(text="0,00")
        self.hesaplari_guncelle()

    def pos_bolumu_olustur(self):
        """3) POS ve IBAN raporları bölümü - kompakt üç sütun"""
        frame = tk.LabelFrame(
            self.a_bolumu_frame,
            text="3) POS VE IBAN",
            font=("Arial", 11, "bold"),
            bg=self.section_colors['pos'],
            fg='#0D47A1',
            padx=3,
            pady=2
        )
        frame.pack(fill="both", expand=True, pady=2)

        # Üç sütunlu yapı
        columns_frame = tk.Frame(frame, bg=self.section_colors['pos'])
        columns_frame.pack(fill="both", expand=True, pady=1)

        # Sol sütun - EczacıPOS
        sol_frame = tk.Frame(columns_frame, bg=self.section_colors['pos'])
        sol_frame.pack(side="left", fill="both", expand=True, padx=1)

        tk.Label(sol_frame, text="EczPOS", font=("Arial", 9, "bold"),
                bg='#BBDEFB', fg='#0D47A1').pack(fill="x", pady=1)

        for i in range(4):
            row = tk.Frame(sol_frame, bg=self.section_colors['pos'])
            row.pack(fill="x", pady=0)
            tk.Label(row, text=f"{i+1}:", font=("Arial", 8),
                    bg=self.section_colors['pos'], fg=self.detay_fg, width=2, anchor='w').pack(side="left")
            var = tk.StringVar(value="0")
            self.pos_vars.append(var)
            entry = tk.Entry(row, textvariable=var, font=("Arial", 9), width=7, justify='right')
            entry.pack(side="right", padx=1)
            entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
            entry.bind('<FocusIn>', self.entry_fokus_secim)

        # Orta sütun - Ingenico
        orta_frame = tk.Frame(columns_frame, bg=self.section_colors['pos'])
        orta_frame.pack(side="left", fill="both", expand=True, padx=1)

        tk.Label(orta_frame, text="Ingenico", font=("Arial", 9, "bold"),
                bg='#BBDEFB', fg='#0D47A1').pack(fill="x", pady=1)

        for i in range(4):
            row = tk.Frame(orta_frame, bg=self.section_colors['pos'])
            row.pack(fill="x", pady=0)
            tk.Label(row, text=f"{i+1}:", font=("Arial", 8),
                    bg=self.section_colors['pos'], fg=self.detay_fg, width=2, anchor='w').pack(side="left")
            var = tk.StringVar(value="0")
            self.pos_vars.append(var)
            entry = tk.Entry(row, textvariable=var, font=("Arial", 9), width=7, justify='right')
            entry.pack(side="right", padx=1)
            entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
            entry.bind('<FocusIn>', self.entry_fokus_secim)

        # Sağ sütun - IBAN
        sag_frame = tk.Frame(columns_frame, bg='#E0F7FA')
        sag_frame.pack(side="left", fill="both", expand=True, padx=1)

        tk.Label(sag_frame, text="IBAN", font=("Arial", 9, "bold"),
                bg='#B2EBF2', fg='#00695C').pack(fill="x", pady=1)

        for i in range(4):
            row = tk.Frame(sag_frame, bg='#E0F7FA')
            row.pack(fill="x", pady=0)
            tk.Label(row, text=f"{i+1}:", font=("Arial", 8),
                    bg='#E0F7FA', fg=self.detay_fg, width=2, anchor='w').pack(side="left")
            var = tk.StringVar(value="0")
            self.iban_vars.append(var)
            entry = tk.Entry(row, textvariable=var, font=("Arial", 9), width=7, justify='right')
            entry.pack(side="right", padx=1)
            entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
            entry.bind('<FocusIn>', self.entry_fokus_secim)

        # Alt toplam satırı - POS ve IBAN toplamları yan yana, aynı hizada
        toplam_frame = tk.Frame(frame, bg='#FFD54F')  # Sari arka plan
        toplam_frame.pack(fill="x", pady=(2, 0))

        # POS Toplam (sol taraf - 2/3)
        pos_toplam_container = tk.Frame(toplam_frame, bg='#FFD54F')
        pos_toplam_container.pack(side="left", fill="x", expand=True)
        tk.Label(pos_toplam_container, text="POS TOP:", font=("Arial", 9, "bold"),
                bg='#FFD54F', fg='#0D47A1').pack(side="left", padx=2, pady=2)
        self.pos_toplam_label = tk.Label(pos_toplam_container, text="0,00", font=("Arial", 10, "bold"),
                                         bg='#FFD54F', fg='#0D47A1')
        self.pos_toplam_label.pack(side="right", padx=2, pady=2)

        # IBAN Toplam (sag taraf - 1/3)
        iban_toplam_container = tk.Frame(toplam_frame, bg='#80DEEA')
        iban_toplam_container.pack(side="left", fill="x", expand=True)
        tk.Label(iban_toplam_container, text="IBAN:", font=("Arial", 9, "bold"),
                bg='#80DEEA', fg='#00695C').pack(side="left", padx=2, pady=2)
        self.iban_toplam_label = tk.Label(iban_toplam_container, text="0,00", font=("Arial", 10, "bold"),
                                          bg='#80DEEA', fg='#00695C')
        self.iban_toplam_label.pack(side="right", padx=2, pady=2)

        # Eski label'lar icin uyumluluk (hesaplari_guncelle'de kullaniliyor)
        self.eczpos_toplam_label = tk.Label(frame)  # Gizli
        self.ingenico_toplam_label = tk.Label(frame)  # Gizli

    def iban_bolumu_olustur(self):
        """IBAN bölümü artık pos_bolumu_olustur içinde - bu fonksiyon boş"""
        pass  # IBAN artık POS ile birleştirildi

    def karsilastirma_tablosu_olustur(self):
        """9) Karşılaştırma tablosu - Sayım vs Botanik - dolgun tasarım"""
        # Ana container - tüm alanı kapla
        container = tk.Frame(self.tablo_frame, bg=self.bg_color)
        container.pack(fill="both", expand=True)

        # 9) Karşılaştırma Tablosu
        frame = tk.LabelFrame(
            container,
            text="9) SAYIM / BOTANİK KARŞILAŞTIRMA",
            font=("Arial", 12, "bold"),
            bg='#FFFFFF',
            fg='#1A237E',
            bd=2,
            relief='groove',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True)

        # Grid ile hizalı tablo - tüm alanı kapla
        tablo = tk.Frame(frame, bg='#FFFFFF')
        tablo.pack(fill="both", expand=True, pady=2)

        # Grid sütunlarını eşit genişlikte yay
        tablo.columnconfigure(0, weight=2)
        tablo.columnconfigure(1, weight=1)
        tablo.columnconfigure(2, weight=1)
        tablo.columnconfigure(3, weight=1)
        # Satırları da genişlet
        for i in range(5):
            tablo.rowconfigure(i, weight=1)

        # Başlık satırı - daha büyük
        tk.Label(tablo, text="", font=("Arial", 11, "bold"),
                bg='#3949AB', fg='white', padx=5, pady=4).grid(row=0, column=0, sticky='nsew', padx=1, pady=1)
        tk.Label(tablo, text="SAYIM", font=("Arial", 12, "bold"),
                bg='#2196F3', fg='white', padx=5, pady=4).grid(row=0, column=1, sticky='nsew', padx=1, pady=1)
        tk.Label(tablo, text="BOTANIK", font=("Arial", 12, "bold"),
                bg='#FF9800', fg='white', padx=5, pady=4).grid(row=0, column=2, sticky='nsew', padx=1, pady=1)
        tk.Label(tablo, text="FARK", font=("Arial", 12, "bold"),
                bg='#607D8B', fg='white', padx=5, pady=4).grid(row=0, column=3, sticky='nsew', padx=1, pady=1)

        # Nakit satırı - daha büyük
        tk.Label(tablo, text="Düzeltilmiş Nakit", font=("Arial", 11, "bold"),
                bg='#E8F5E9', fg='#2E7D32', padx=5, pady=4, anchor='w').grid(row=1, column=0, sticky='nsew', padx=1, pady=1)
        self.duzeltilmis_nakit_label = tk.Label(tablo, text="0,00", font=("Arial", 13, "bold"),
                bg='#BBDEFB', fg='#1565C0', padx=5, pady=4, anchor='e')
        self.duzeltilmis_nakit_label.grid(row=1, column=1, sticky='nsew', padx=1, pady=1)
        self.botanik_nakit_gosterge = tk.Label(tablo, text="0,00", font=("Arial", 13, "bold"),
                bg='#FFE0B2', fg='#E65100', padx=5, pady=4, anchor='e')
        self.botanik_nakit_gosterge.grid(row=1, column=2, sticky='nsew', padx=1, pady=1)
        self.nakit_fark_label = tk.Label(tablo, text="0,00", font=("Arial", 13, "bold"),
                bg='#ECEFF1', fg='#455A64', padx=5, pady=4, anchor='e')
        self.nakit_fark_label.grid(row=1, column=3, sticky='nsew', padx=1, pady=1)

        # POS satırı - daha büyük
        tk.Label(tablo, text="POS Toplam", font=("Arial", 11, "bold"),
                bg='#E3F2FD', fg='#1565C0', padx=5, pady=4, anchor='w').grid(row=2, column=0, sticky='nsew', padx=1, pady=1)
        self.ozet_pos_label = tk.Label(tablo, text="0,00", font=("Arial", 13, "bold"),
                bg='#BBDEFB', fg='#1565C0', padx=5, pady=4, anchor='e')
        self.ozet_pos_label.grid(row=2, column=1, sticky='nsew', padx=1, pady=1)
        self.botanik_pos_gosterge = tk.Label(tablo, text="0,00", font=("Arial", 13, "bold"),
                bg='#FFE0B2', fg='#E65100', padx=5, pady=4, anchor='e')
        self.botanik_pos_gosterge.grid(row=2, column=2, sticky='nsew', padx=1, pady=1)
        self.pos_fark_label = tk.Label(tablo, text="0,00", font=("Arial", 13, "bold"),
                bg='#ECEFF1', fg='#455A64', padx=5, pady=4, anchor='e')
        self.pos_fark_label.grid(row=2, column=3, sticky='nsew', padx=1, pady=1)

        # IBAN satırı - daha büyük
        tk.Label(tablo, text="IBAN Toplam", font=("Arial", 11, "bold"),
                bg='#E0F2F1', fg='#00695C', padx=5, pady=4, anchor='w').grid(row=3, column=0, sticky='nsew', padx=1, pady=1)
        self.ozet_iban_label = tk.Label(tablo, text="0,00", font=("Arial", 13, "bold"),
                bg='#BBDEFB', fg='#1565C0', padx=5, pady=4, anchor='e')
        self.ozet_iban_label.grid(row=3, column=1, sticky='nsew', padx=1, pady=1)
        self.botanik_iban_gosterge = tk.Label(tablo, text="0,00", font=("Arial", 13, "bold"),
                bg='#FFE0B2', fg='#E65100', padx=5, pady=4, anchor='e')
        self.botanik_iban_gosterge.grid(row=3, column=2, sticky='nsew', padx=1, pady=1)
        self.iban_fark_label = tk.Label(tablo, text="0,00", font=("Arial", 13, "bold"),
                bg='#ECEFF1', fg='#455A64', padx=5, pady=4, anchor='e')
        self.iban_fark_label.grid(row=3, column=3, sticky='nsew', padx=1, pady=1)

        # GENEL TOPLAM satırı - en vurgulu
        tk.Label(tablo, text="GENEL TOPLAM", font=("Arial", 12, "bold"),
                bg='#1A237E', fg='white', padx=5, pady=5, anchor='w').grid(row=4, column=0, sticky='nsew', padx=1, pady=1)
        self.genel_toplam_label = tk.Label(tablo, text="0,00", font=("Arial", 14, "bold"),
                bg='#1565C0', fg='#FFEB3B', padx=5, pady=5, anchor='e')
        self.genel_toplam_label.grid(row=4, column=1, sticky='nsew', padx=1, pady=1)
        self.botanik_toplam_gosterge = tk.Label(tablo, text="0,00", font=("Arial", 14, "bold"),
                bg='#E65100', fg='#FFEB3B', padx=5, pady=5, anchor='e')
        self.botanik_toplam_gosterge.grid(row=4, column=2, sticky='nsew', padx=1, pady=1)
        self.genel_fark_label = tk.Label(tablo, text="0,00", font=("Arial", 14, "bold"),
                bg='#37474F', fg='#FFEB3B', padx=5, pady=5, anchor='e')
        self.genel_fark_label.grid(row=4, column=3, sticky='nsew', padx=1, pady=1)

        # Özet labellar için placeholder (hesaplari_guncelle'de kullanılıyor)
        self.ozet_nakit_label = self.duzeltilmis_nakit_label
        self.ozet_masraf_label = tk.Label(frame)  # Gizli placeholder
        self.ozet_silinen_label = tk.Label(frame)  # Gizli placeholder
        self.ozet_alinan_label = tk.Label(frame)  # Gizli placeholder
        self.son_genel_toplam_label = self.genel_toplam_label

        # Fark label - artık kullanılmıyor ama uyumluluk için gizli oluştur
        self.fark_label = tk.Label(frame, text="FARK: 0,00 TL")
        self.tolerans_label = tk.Label(frame)

    def arti_eksi_listesi_olustur(self):
        """10) Artı/Eksi tutarsızlık sebepleri - sabit checkbox listesi"""
        # Ana frame
        frame = tk.LabelFrame(
            self.sebepler_alan,
            text="10) ARTI/EKSİ TUTARSIZLIK SEBEPLERİ",
            font=("Arial", 11, "bold"),
            bg='#FFEBEE',
            fg='#C62828',
            bd=2,
            relief='groove',
            padx=3,
            pady=2
        )
        frame.pack(fill="both", expand=True)

        # Notebook (sekmeler) - sabit
        self.tutarsizlik_notebook = ttk.Notebook(frame)
        self.tutarsizlik_notebook.pack(fill="both", expand=True, padx=2, pady=2)

        # Sekme 1: Kasa Açık (Eksik) Durumu
        eksik_frame = tk.Frame(self.tutarsizlik_notebook, bg='#FFEBEE')
        self.tutarsizlik_notebook.add(eksik_frame, text=" KASA AÇIK ")

        # Sekme 2: Kasa Fazla Durumu
        fazla_frame = tk.Frame(self.tutarsizlik_notebook, bg='#E8F5E9')
        self.tutarsizlik_notebook.add(fazla_frame, text=" KASA FAZLA ")

        # Kasa Eksik (Açık) sebepleri - (başlık, açıklama) formatında
        eksik_sebepler = [
            ("1) Başlangıç kasası eksik", "Bir önceki gün başlangıç kasası eksik olabilir mi? Kontrol edilmeli."),
            ("2) Akşam kasası yanlış sayıldı", "Akşam kasası yanlış sayılmıştır."),
            ("3) Dünkü satış/POS işlenmedi", "Dün akşamdan yapılan satış, POS raporu vesaire işlenmemiştir."),
            ("4) Satış parası alınmadı", "Yapılan satışın parası alınmamıştır. Eksik çıkan tutar ölçüsünde raflar gezilerek satılan ürünler hatırlanmaya çalışılmalıdır."),
            ("5) Veresiye işlenmedi", "Veresiye satış veresiye işlenmemiştir. Veresiye işlemi yapılmadan tahsilat veya reçeteden hesaba atma işlemi bitirilmeden ikinci işe asla geçilmemelidir."),
            ("6) 2. POS raporu unutuldu", "İkinci POS cihazı kullanılmış fakat raporu alınması unutulmuş, işlenmemiştir."),
            ("7) Para alındı satış bugün", "Bir önceki gün satışın parası alınmış fakat satış bugün yapılmıştır. Satışı tamamlanmamış satışların parası ayrı bir kilitli poşet içinde ve not kağıdı ile birlikte kasanın yan tarafında muhafaza edilmelidir."),
            ("8) Mükerrer satış kaydı", "Mükerrer satış kaydı işlenmiştir. Aynı ürün iki kez satılıp bir kez parası kasaya konmuştur. Ayrı bilgisayarlara tekrar okutulan ürünlerin satışında dikkat edilmelidir."),
            ("9) İndirim işlenmedi", "İndirim/iskonto sisteme işlenmemiştir. İskonto tutarı 1 TL bile olsa işlenmeli ve önemsenmemelidir."),
            ("10) Masraf işlenmedi", "Masraflar işlenmemiştir. Masraf işlenmeden kasadan para almak kesinlikle yasaktır. Önce işlem yapılmalı sonra kasadan para alınmalıdır. Yemekçi bu iş için bekletilebilir."),
            ("11) Silinmesi gereken reçete", "Silinmesi gereken fakat sistemde unutulmuş reçete varlığı. Hastanın ödeme yüzünden almaktan vazgeçtiği ama silinmesi unutulmuş reçetelerin tespit edilip silinmesi gerekmektedir."),
            ("12) Alınan para işlenmedi", "Gün içi eczacının aldığı para işlenmemiş veya yanlış işlenmiştir. Eczacının para alması için eczacı ile bir personel parayı sayacak ve bir kağıda el yazısı ile yazılıp bütün paraların yanına konulacaktır."),
            ("13) Kasadan para alındı", "Gün içi çeşitli sebeplerle para lazım olup kasadan para alınması durumu kesinlikle yasaktır. Mecburi durumlarda bir kağıda alınan para yazılacak ve iki personel tarafından sayılıp kağıda el yazısı ile alınma sebebi ve miktarı yazılarak bütün paraların yanına konulacaktır."),
            ("14) Tedarikçi ödemesi", "Kasadan Tibtek, Sedat veya başka tedarikçi firmaya ödeme yapılmış fakat masraf işlenmemiştir. Masraf kaydı işlenmemiş paralar kasadan alınamazlar. Tahsilatçı kişinin bekletilmesinde beis yoktur."),
            ("15) Bozuk para sorunu", "Kasadan alınan bütün para bozduruluş ama bozuk para kasadan başka yere konmuştur. Bozuk paralar kutusundan anlık bozuk alınma veya bütünleme işlemleri bitirilmeden sonraki işe geçilmemelidir."),
            ("16) Emanet parekende satıldı", "Emanet verilmesi gereken ürün parekende satılarak sisteme işlenmiştir."),
            ("17) IBAN işlenmedi", "IBAN'a atılan para vardır ama unutulmuş, IBAN olarak işlenmemiştir. IBAN'a atılan paralar muhakkak IBAN seçeneği adı altında işlenecektir."),
            ("18) Komplike satış karışıklığı", "Komplike satışların kafa karıştırması: birden fazla reçete, perakende, ödenmeyen ilaç olan reçetede tahsilatın düzgün yapılmaması. İki üç reçetesi olan ve bu reçetelerde ödenmeyen ilaçların bulunduğu ve hastanın nakit ilaç almış olması gibi birden fazla parça içeren satışların çok dikkatli ve disiplinli yapılması gerekmektedir."),
            ("19) Hasta borcu yok iddiası", "Hastanın borcu olmadığını ve parayı daha önce ödediğini iddia etmesi ve haklı olması. Bu durumda WhatsApp Web'den ilgili durum eczacıya haber verilecek ve eczacının düşmesi sağlanacaktır."),
            ("20) Depo/personel ödemesi", "Depo veya personel ödemeler cari hareketten nakit olarak işlenmiştir. Bu hareketlerin varlığı kontrol edilmeli."),
            ("21) Takas işlenmedi", "Başka eczaneden alınan takasın parası kasadan verilmiş ama kayıtlara işlenmemiştir. Kasadan kayıt edilmeyen hiçbir para kasadan alınamaz."),
            ("22) Emanet satıldı para yok", "Emanetin parekendeye çevrilip satılması olmuş fakat para kasaya konmamıştır."),
            ("23) İskonto karışıklığı", "İskonto, yuvarlama ve ödeme seçenekleri birbirine karıştırılmıştır."),
            ("24) Geçmiş reçete sistemi bozdu", "Son işlem tarihi bugün olan geçmiş reçetelerin sistemi bozmuş olabilme ihtimali. Sistemsel bir hata olup uyanık olunacaktır.")
        ]

        # Kasa Fazla sebepleri - (başlık, açıklama) formatında
        fazla_sebepler = [
            ("1) Başlangıç kasası hatası", "Bir önceki gün başlangıç kasası doğru mu? Kontrol edilmeli."),
            ("2) Akşam kasası hatası", "Akşam kasası doğru sayılmış mı? Kontrol edilmeli."),
            ("3) Bekleyen satış var", "Satış ekranlarında bekleyen veya gün içi satışı unutulan ürün var mı?"),
            ("4) Veresiye tahsilatı", "İşlenmesi unutulan veresiye tahsilatı durumu var mı?"),
            ("5) Bozuk para eklendi", "Bozuk para eklenmiş ama kasadan bütün para alınması unutulmuş olabilir mi?"),
            ("6) Kapora alındı", "Kapora alınmış kasaya konmuştur. Ayrı bir yere not ile koyulması gerekir."),
            ("7) Majistral düşülmedi", "Majistral yapılıp sistemden düşülmemesi söz konusu mu?"),
            ("8) Strip/bez farkı", "Strip, bez, iğne ucu gibi fark parası hastadan alınmış fakat sisteme işlenmemiş olabilir mi?"),
            ("9) Takas parası", "Başka eczane ile takas yapılıp parası kasaya konmuş olabilir mi?"),
            ("10) Fiş iptali", "Fiş iptali yapılmış olabilir mi?"),
            ("11) Aktarılmayan reçete", "Aktarılmayan reçete var mı?"),
            ("12) Para üstü eksik", "Para üstü eksik verilmiş olabilir mi?"),
            ("13) İade parası", "İade yapılmış parası kasadan hastaya verilmemiş veya ayrılmamış olabilir mi?"),
            ("14) Mal fazlası satışı", "Ölü karekod veya mal fazlası ürün satışı yapılıp parası kasaya konmuş olabilir mi?"),
            ("15) Dünkü satış parası bugün", "Bir önceki gün satışı yapılmış fakat parası bugün alınmış, sisteme de düzgün işlenmemiş olabilir mi?")
        ]

        # Eksik sekmesi - scrollable checkbox listesi (aciklamali)
        self.eksik_checkboxlar = self.aciklamali_checkbox_listesi_olustur(eksik_frame, eksik_sebepler, '#FFEBEE')

        # Fazla sekmesi - scrollable checkbox listesi (aciklamali)
        self.fazla_checkboxlar = self.aciklamali_checkbox_listesi_olustur(fazla_frame, fazla_sebepler, '#E8F5E9')

    def aciklamali_checkbox_listesi_olustur(self, parent, sebepler, bg_color):
        """Aciklamali checkbox listesi olustur - 4 sutunlu (1-2-3-4, 5-6-7-8...) yapi, aciklamali"""
        # Scrollable frame
        canvas = tk.Canvas(parent, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=bg_color)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse scroll destegi
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scrollable.bind("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 4 sutunlu grid yapisi - esit genislik
        scrollable.columnconfigure(0, weight=1)
        scrollable.columnconfigure(1, weight=1)
        scrollable.columnconfigure(2, weight=1)
        scrollable.columnconfigure(3, weight=1)

        # Checkbox'lar - 4 sutunlu (1-2-3-4, 5-6-7-8...) aciklamali
        checkbox_vars = {}
        for i, (baslik, aciklama) in enumerate(sebepler):
            var = tk.BooleanVar(value=False)
            checkbox_vars[baslik] = var

            # Satir ve sutun hesapla (1-2-3-4 ayni satir, 5-6-7-8 ayni satir...)
            row = i // 4
            col = i % 4

            # Her madde icin frame
            madde_frame = tk.Frame(scrollable, bg=bg_color, bd=1, relief='groove')
            madde_frame.grid(row=row, column=col, sticky='nsew', padx=2, pady=2)

            # Checkbox - baslik
            cb = tk.Checkbutton(
                madde_frame,
                text=baslik,
                variable=var,
                font=("Arial", 8, "bold"),
                bg=bg_color,
                fg='#333',
                activebackground=bg_color,
                anchor='w',
                padx=2,
                pady=1,
                selectcolor='white'
            )
            cb.pack(fill="x", anchor='w')
            cb.bind("<MouseWheel>", _on_mousewheel)

            # Aciklama label
            aciklama_label = tk.Label(
                madde_frame,
                text=aciklama,
                font=("Arial", 7),
                bg=bg_color,
                fg='#555',
                anchor='w',
                wraplength=130,
                justify='left'
            )
            aciklama_label.pack(fill="x", anchor='w', padx=(18, 2), pady=(0, 2))
            aciklama_label.bind("<MouseWheel>", _on_mousewheel)

        return checkbox_vars

    def sabit_checkbox_listesi_olustur(self, parent, sebepler, bg_color):
        """Sabit checkbox listesi olustur - eski format icin uyumluluk"""
        # Scrollable frame
        canvas = tk.Canvas(parent, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=bg_color)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse scroll destegi
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Checkbox'lar
        checkbox_vars = {}
        for sebep in sebepler:
            var = tk.BooleanVar(value=False)
            checkbox_vars[sebep] = var

            cb = tk.Checkbutton(
                scrollable,
                text=sebep,
                variable=var,
                font=("Arial", 9),
                bg=bg_color,
                fg='#333',
                activebackground=bg_color,
                anchor='w',
                padx=2,
                pady=1,
                selectcolor='white'
            )
            cb.pack(fill="x", anchor='w')

        return checkbox_vars

    def kasa_tablosu_olustur(self):
        """11) Ertesi gün kasası ve ayrılan para tablosu - basit ve düzgün"""
        # Ana frame
        frame = tk.LabelFrame(
            self.para_ayirma_frame,
            text="11) Ertesi Gün Kasası / Ayrılan Para",
            font=("Arial", 11, "bold"),
            bg='#E8EAF6',
            fg='#3F51B5',
            bd=2,
            relief='groove',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True)

        # Alt kisim - Sadece etiketler (Yarinin Baslangic Kasasi ve Ayrilan Para)
        alt_etiket_frame = tk.Frame(frame, bg='#E8EAF6')
        alt_etiket_frame.pack(fill="x", side="bottom", pady=5)

        # İki etiketi eşit genişlikte yan yana göstermek için grid kullan
        alt_etiket_frame.columnconfigure(0, weight=1)
        alt_etiket_frame.columnconfigure(1, weight=1)

        # Yarının Başlangıç Kasası etiketi - yeşil
        self.c_kalan_toplam_label = tk.Label(alt_etiket_frame, text="Yarının Başlangıç Kasası: 0 TL",
                                             font=("Arial", 11, "bold"), bg='#4CAF50', fg='white', pady=8)
        self.c_kalan_toplam_label.grid(row=0, column=0, sticky='ew', padx=(0, 1))

        # Ayrılan Para etiketi - turuncu
        self.c_ayrilan_toplam_label = tk.Label(alt_etiket_frame, text="Ayrılan Para: 0 TL",
                                               font=("Arial", 11, "bold"), bg='#FF9800', fg='white', pady=8)
        self.c_ayrilan_toplam_label.grid(row=0, column=1, sticky='ew', padx=(1, 0))

        # Ayrilan adet toplam - gizli (kod uyumlulugu icin)
        self.c_ayrilan_adet_toplam_label = tk.Label(frame, text="0")

        # Ust kisim - Tablo (toplam satiri pack edildikten sonra)
        tablo_frame = tk.Frame(frame, bg='#E8EAF6')
        tablo_frame.pack(fill="both", expand=True)

        # Tablo basligi - pack ile hizali
        header = tk.Frame(tablo_frame, bg='#3F51B5')
        header.pack(fill="x")

        tk.Label(header, text="Küpür", font=("Arial", 9, "bold"), bg='#3F51B5', fg='white', width=7).pack(side="left", padx=1, pady=2)
        tk.Label(header, text="Sayım", font=("Arial", 9, "bold"), bg='#3F51B5', fg='white', width=5).pack(side="left", padx=1, pady=2)
        tk.Label(header, text="Kalan", font=("Arial", 9, "bold"), bg='#4CAF50', fg='white', width=5).pack(side="left", padx=1, pady=2)
        # AYIRMA frame - butonlar ve slider ile aynı genişlikte
        ayirma_frame = tk.Frame(header, bg='#FF9800')
        ayirma_frame.pack(side="left", padx=1, pady=2)
        # < butonu yeri (görünmez)
        tk.Frame(ayirma_frame, bg='#FF9800', width=24, height=1).pack(side="left")
        # AYIRMA yazısı (slider genişliğinde)
        tk.Label(ayirma_frame, text="AYIRMA", font=("Arial", 9, "bold"), bg='#FF9800', fg='white', width=18, anchor='center').pack(side="left")
        # > butonu yeri (görünmez)
        tk.Frame(ayirma_frame, bg='#FF9800', width=24, height=1).pack(side="left")
        # Ayrılan ve Tutar - tablo verileriyle aynı genişlik
        tk.Label(header, text="Ayrln", font=("Arial", 9, "bold"), bg='#E65100', fg='white', width=5).pack(side="left", padx=1, pady=2)
        tk.Label(header, text="Tutar", font=("Arial", 9, "bold"), bg='#E65100', fg='white', width=8).pack(side="left", padx=1, pady=2)

        # Scrollable kupur listesi
        canvas = tk.Canvas(tablo_frame, bg='#E8EAF6', highlightthickness=0)
        scrollbar = ttk.Scrollbar(tablo_frame, orient="vertical", command=canvas.yview)
        self.kasa_scrollable = tk.Frame(canvas, bg='#E8EAF6')

        self.kasa_scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.kasa_scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        self.kasa_scrollable.bind("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Degiskenler
        self.c_slider_vars = {}
        self.c_kalan_labels = {}
        self.c_ayrilan_labels = {}
        self.c_ayrilan_tl_labels = {}
        self.c_sayim_labels = {}
        self.c_sliders = {}

        # Kupur satirlari
        for i, kupur in enumerate(self.KUPURLER):
            if self.kupur_aktif_mi(kupur["deger"]):
                deger = kupur["deger"]
                row_bg = '#F5F5F5' if i % 2 == 0 else '#ECEFF1'

                row = tk.Frame(self.kasa_scrollable, bg=row_bg)
                row.pack(fill="x", pady=1)
                row.bind("<MouseWheel>", _on_mousewheel)

                # Kupur adi
                tk.Label(row, text=kupur["aciklama"], font=("Arial", 9, "bold"),
                        bg=row_bg, fg='#333', width=7, anchor='w').pack(side="left", padx=1)

                # Sayim adedi
                sayim_adet = 0
                if deger in self.sayim_vars:
                    try:
                        sayim_adet = int(self.sayim_vars[deger].get() or 0)
                    except ValueError:
                        sayim_adet = 0

                sayim_label = tk.Label(row, text=str(sayim_adet), font=("Arial", 9, "bold"),
                                      bg='#E3F2FD', fg='#1565C0', width=5)
                sayim_label.pack(side="left", padx=1)
                self.c_sayim_labels[deger] = sayim_label

                # Kalan label (yesil)
                kalan_label = tk.Label(row, text=str(sayim_adet), font=("Arial", 9, "bold"),
                                      bg='#C8E6C9', fg='#2E7D32', width=5)
                kalan_label.pack(side="left", padx=1)
                self.c_kalan_labels[deger] = kalan_label

                # Slider degiskeni
                slider_var = tk.IntVar(value=0)
                self.c_slider_vars[deger] = slider_var

                # Sol buton <
                tk.Button(row, text="<", font=("Arial", 8, "bold"), bg='#4CAF50', fg='white',
                         width=2, command=lambda d=deger: self.c_kalana_ekle(d)).pack(side="left", padx=1)

                # Slider (tk.Scale - daha iyi gorunum)
                slider = tk.Scale(
                    row,
                    from_=0,
                    to=max(1, sayim_adet),
                    orient='horizontal',
                    variable=slider_var,
                    length=130,
                    showvalue=False,
                    bg=row_bg,
                    highlightthickness=0,
                    troughcolor='#BBDEFB',
                    activebackground='#FF9800',
                    command=lambda val, d=deger: self.c_slider_degisti(d, val)
                )
                slider.pack(side="left", padx=1)
                slider.bind("<MouseWheel>", _on_mousewheel)
                self.c_sliders[deger] = slider

                # Sag buton >
                tk.Button(row, text=">", font=("Arial", 8, "bold"), bg='#FF9800', fg='white',
                         width=2, command=lambda d=deger: self.c_ayrilana_ekle(d)).pack(side="left", padx=1)

                # Ayrilan adet
                ayrilan_label = tk.Label(row, text="0", font=("Arial", 9, "bold"),
                                        bg='#FFE0B2', fg='#E65100', width=5)
                ayrilan_label.pack(side="left", padx=1)
                self.c_ayrilan_labels[deger] = ayrilan_label

                # Ayrilan tutar TL
                ayrilan_tl_label = tk.Label(row, text="0 TL", font=("Arial", 9, "bold"),
                                           bg='#FFCCBC', fg='#BF360C', width=8, anchor='e')
                ayrilan_tl_label.pack(side="left", padx=1)
                self.c_ayrilan_tl_labels[deger] = ayrilan_tl_label

        # Ilk hesaplama
        self.c_toplamlari_guncelle()

    def c_kalana_ekle(self, deger):
        """Ayrilandan bir adet cikarip kalana ekle"""
        if deger in self.c_slider_vars:
            mevcut = self.c_slider_vars[deger].get()
            if mevcut > 0:
                self.c_slider_vars[deger].set(mevcut - 1)
                self.c_slider_guncelle(deger)

    def c_ayrilana_ekle(self, deger):
        """Kalandan bir adet cikarip ayrilana ekle"""
        if deger in self.c_slider_vars:
            mevcut = self.c_slider_vars[deger].get()
            # Maksimum sayim adedini al
            max_adet = 0
            if deger in self.sayim_vars:
                try:
                    max_adet = int(self.sayim_vars[deger].get() or 0)
                except ValueError:
                    max_adet = 0
            if mevcut < max_adet:
                self.c_slider_vars[deger].set(mevcut + 1)
                self.c_slider_guncelle(deger)

    def alt_butonlar_olustur(self):
        """Alt butonlar - sag bolumun en altinda, numarali ve alta yapisik"""
        # Butonlar tum genisligi kaplayacak sekilde grid ile yerlestirilecek
        # 12-16 arasi numaralar - surec adimlari
        butonlar = [
            ("12) Ertesi Gun", '#4CAF50', self.ertesi_gun_kasasi_isle),
            ("13) Ayrilan", '#FF9800', self.ayrilan_para_isle),
            ("14) WhatsApp", '#25D366', self.whatsapp_rapor_gonder),
            ("15) Yazdir", '#2196F3', self.ayrilan_cikti_yazdir),
            ("16) KAYDET", '#1565C0', self.kaydet),
        ]

        # 5 sutun esit genislikte
        for i in range(5):
            self.butonlar_frame.columnconfigure(i, weight=1)

        for i, (text, color, command) in enumerate(butonlar):
            btn = tk.Button(
                self.butonlar_frame,
                text=text,
                font=("Arial", 10, "bold"),
                bg=color,
                fg='white',
                activebackground=color,
                cursor='hand2',
                bd=2,
                relief='raised',
                height=2,
                command=command
            )
            btn.grid(row=0, column=i, sticky='ew', padx=2, pady=3)

    def ayrilan_cikti_yazdir(self):
        """Kasa raporu yazdır"""
        if not YENI_MODULLER_YUKLENDI:
            messagebox.showwarning("Uyarı", "Yazıcı modülü yüklenmedi")
            return

        try:
            # Kasa verilerini topla
            kasa_verileri = self.kasa_verilerini_topla()

            # Yazıcı oluştur
            yazici = KasaYazici(self.ayarlar)

            # Gün sonu raporu oluştur
            rapor = yazici.gun_sonu_raporu_olustur(kasa_verileri)

            # Yazıcı seçim penceresi aç
            def yazdir_callback(secilen_yazici):
                yazici.yazici_adi = secilen_yazici
                if yazici.yazdir(rapor):
                    messagebox.showinfo("Başarılı", "Rapor yazıcıya gönderildi!")

            # Önce dosyaya kaydet (yedek)
            dosya_yolu = yazici.dosyaya_kaydet(rapor)
            if dosya_yolu:
                logger.info(f"Rapor dosyaya kaydedildi: {dosya_yolu}")

            # Yazıcı seç ve yazdır
            secim = YaziciSecimPenceresi(self.root, self.ayarlar, yazdir_callback)
            secim.goster()

        except Exception as e:
            logger.error(f"Yazdırma hatası: {e}")
            messagebox.showerror("Hata", f"Yazdırma hatası: {e}")

    def fark_kontrol_listesi_ac(self):
        """Fark sebepleri kontrol listesi - iki sekmeli pencere aç"""
        # Yeni pencere aç
        self.tutarsizlik_penceresi = tk.Toplevel(self.root)
        self.tutarsizlik_penceresi.title("10) ARTI/EKSI TUTARSIZLIKLARI BUL")
        self.tutarsizlik_penceresi.geometry("650x600")
        self.tutarsizlik_penceresi.transient(self.root)
        self.tutarsizlik_penceresi.configure(bg='#FAFAFA')

        # Pencereyi ortala
        self.tutarsizlik_penceresi.update_idletasks()
        x = (self.tutarsizlik_penceresi.winfo_screenwidth() - 650) // 2
        y = (self.tutarsizlik_penceresi.winfo_screenheight() - 600) // 2
        self.tutarsizlik_penceresi.geometry(f"650x600+{x}+{y}")

        # Fark değerini al
        try:
            fark_text = self.genel_fark_label.cget("text").replace(",", ".").replace(" TL", "").replace("+", "").strip()
            fark = float(fark_text) if fark_text else 0
        except ValueError:
            fark = 0

        # Başlık
        baslik_frame = tk.Frame(self.tutarsizlik_penceresi, bg='#1565C0', height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text=f"10) TUTARSIZLIK KONTROL LISTESI - Fark: {fark:,.2f} TL",
            font=("Arial", 14, "bold"),
            bg='#1565C0',
            fg='white'
        ).pack(expand=True)

        # Notebook (sekmeler)
        notebook = ttk.Notebook(self.tutarsizlik_penceresi)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Sekme 1: Kasa Açık (Eksik) Durumu
        eksik_frame = tk.Frame(notebook, bg='#FFEBEE')
        notebook.add(eksik_frame, text="  KASA AÇIK (Eksik)  ")

        # Sekme 2: Kasa Fazla Durumu
        fazla_frame = tk.Frame(notebook, bg='#E8F5E9')
        notebook.add(fazla_frame, text="  KASA FAZLA  ")

        # Kasa Eksik (Açık) sebepleri - detaylı liste
        eksik_sebepler = [
            "a) Bir önceki gün başlangıç kasası eksik olabilir mi - kontrol edilmeli",
            "b) Akşam kasası yanlış sayılmıştır",
            "c) Dün akşamdan yapılan satış, POS raporu vesaire işlenmemiştir",
            "d) Yapılan satışın parası alınmamıştır - eksik tutar ölçüsünde raflar gezilerek satılan ürünler hatırlanmalı",
            "e) Veresiye satış veresiye işlenmemiştir - veresiye işlemi bitmeden ikinci işe geçilmemeli",
            "f) İkinci POS cihazı kullanılmış fakat raporu alınması unutulmuş/işlenmemiştir",
            "g) Bir önceki gün satışın parası alınmış fakat satış bugün yapılmıştır - tamamlanmamış satışların parası ayrı kilitli poşette muhafaza edilmeli",
            "h) Mükerrer satış kaydı işlenmiştir - aynı ürün iki kez satılıp bir kez parası kasaya konmuştur",
            "i) İndirim/iskonto sisteme işlenmemiştir - 1 TL bile olsa işlenmelidir",
            "j) Masraflar işlenmemiştir - masraf işlenmeden kasadan para almak yasaktır",
            "k) Silinmesi gereken fakat sistemde unutulmuş reçete varlığı",
            "l) Gün içi eczacının aldığı para işlenmemiş veya yanlış işlenmiştir",
            "m) Gün içi çeşitli sebepler ile kasadan para alınması - iki kişi sayıp kağıda yazılmalı",
            "n) Kasadan Tibtek/Sedat veya tedarikçi firmaya ödeme yapılmış fakat masraf işlenmemiştir",
            "o) Kasadan alınan bütün para bozduruluş ama bozukla kasadan başka yere konmuştur",
            "p) Emanet verilmesi gereken ürün parekende satılarak sisteme işlenmiştir",
            "r) IBAN'a atılan para var ama unutulmuş, IBAN olarak işlenmemiştir",
            "s) Komplike satışlarda kafa karışıklığı - birden fazla reçete, ödenmeyen ilaç, nakit vb.",
            "t) Hastanın borcu olmadığını ve parayı daha önce ödediğini iddia etmesi - WhatsApp'tan eczacıya haber verilmeli",
            "u) Depo veya personel ödemeler cari hareketten nakit olarak işlenmiştir",
            "v) Başka eczaneden alınan takasın parası kasadan verilmiş ama kayıtlara işlenmemiştir",
            "y) Emanetin parekendeye çevrilip satılması olmuş fakat para kasaya konmamıştır",
            "z) İskonto, yuvarlama ve ödeme seçenekleri birbirine karıştırılmıştır",
            "aa) Son işlem tarihi bugün olan geçmiş reçetelerin sistemi bozması ihtimali"
        ]

        # Kasa Fazla sebepleri - detaylı liste
        fazla_sebepler = [
            "a) Bir önceki gün başlangıç kasası doğru mu - kontrol edilmeli",
            "b) Akşam kasası doğru sayılmış mı",
            "c) Satış ekranlarında bekleyen veya gün içi satışı unutulan ürün var mı",
            "d) İşlenmesi unutulan veresiye tahsilatı durumu var mı",
            "e) Bozuk para eklenmiş ama kasadan bütün para alınması unutulmuş olabilir mi",
            "f) Kapora alınmış kasaya konmuştur - ayrı bir yere not ile koyulması gerekir",
            "g) Majistral yapılıp sistemden düşülmemesi söz konusu mu",
            "h) Strip, bez, iğne ucu vb. farkı parası hastadan alınmış fakat sisteme işlenmemiş olabilir mi",
            "i) Başka eczane ile takas yapılıp parası kasaya konmuş olabilir mi",
            "j) Fiş iptali yapılmış olabilir mi",
            "k) Aktarılmayan reçete var mı",
            "l) Para üstü eksik verilmiş olabilir mi",
            "m) İade yapılmış parası kasadan hastaya verilmemiş veya ayrılmamış olabilir mi",
            "n) Ölü karekod veya mal fazlası ürün satışı yapılıp parası kasaya konmuş olabilir mi",
            "o) Bir önceki gün satışı yapılmış fakat parası bugün alınmış, sisteme de düzgün işlenmemiş olabilir mi"
        ]

        # Eksik sekmesi içeriği
        self.tutarsizlik_checkboxlari_olustur(eksik_frame, eksik_sebepler, '#F44336', "KASA AÇIK - Kontrol Listesi")

        # Fazla sekmesi içeriği
        self.tutarsizlik_checkboxlari_olustur(fazla_frame, fazla_sebepler, '#4CAF50', "KASA FAZLA - Kontrol Listesi")

        # Fark durumuna göre uygun sekmeyi aç
        if fark < 0:
            notebook.select(0)  # Kasa açık sekmesi
        else:
            notebook.select(1)  # Kasa fazla sekmesi

        # Alt butonlar
        btn_frame = tk.Frame(self.tutarsizlik_penceresi, bg='#FAFAFA')
        btn_frame.pack(fill="x", padx=10, pady=10)

        tk.Button(
            btn_frame,
            text="KAPAT",
            font=("Arial", 12, "bold"),
            bg='#9E9E9E',
            fg='white',
            activebackground='#757575',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=8,
            command=self.tutarsizlik_penceresi.destroy
        ).pack(side="right")

    def tutarsizlik_checkboxlari_olustur(self, parent, sebepler, baslik_renk, baslik_text):
        """Tutarsızlık checkbox listesi oluştur"""
        # Başlık
        tk.Label(
            parent,
            text=baslik_text,
            font=("Arial", 13, "bold"),
            bg=baslik_renk,
            fg='white',
            pady=8
        ).pack(fill="x")

        # Scrollable frame
        canvas = tk.Canvas(parent, bg=parent.cget('bg'), highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=parent.cget('bg'))

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse scroll desteği
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        # Checkbox'lar
        self.tutarsizlik_vars = {}
        for i, sebep in enumerate(sebepler):
            row = tk.Frame(scrollable, bg=parent.cget('bg'))
            row.pack(fill="x", pady=2, padx=5)

            var = tk.BooleanVar(value=False)
            self.tutarsizlik_vars[sebep] = var

            cb = tk.Checkbutton(
                row,
                text=sebep,
                variable=var,
                font=("Arial", 11),
                bg=parent.cget('bg'),
                fg='#333',
                activebackground=parent.cget('bg'),
                anchor='w',
                padx=5,
                pady=3,
                selectcolor='white'
            )
            cb.pack(fill="x", anchor='w')

        # Bilgi notu
        not_frame = tk.Frame(parent, bg='#FFF9C4')
        not_frame.pack(fill="x", padx=5, pady=5)
        tk.Label(
            not_frame,
            text="Not: İşaretlediğiniz maddeler raporda gösterilir",
            font=("Arial", 9, "italic"),
            bg='#FFF9C4',
            fg='#666',
            pady=3
        ).pack()

    def para_ayirma_butonu_olustur(self):
        """11) - Eski fonksiyon, artık kasa_tablosu_olustur kullanılıyor"""
        # Uyumluluk için durum labellarını oluştur
        self.ertesi_gun_durum_label = tk.Label(self.para_ayirma_frame, text="")
        self.ayrilan_para_durum_label = tk.Label(self.para_ayirma_frame, text="")
        self.kasa_tablo_acik = True  # Tablo artık her zaman açık

    def para_ayirma_tablosu_goster(self):
        """Eski fonksiyon - artik kasa_tablosu_olustur kullaniliyor"""
        pass  # Bu fonksiyon artik kullanilmiyor

    def c_slider_degisti(self, deger, val):
        """Slider suruklendiginde cagrilir - val string olarak gelir"""
        try:
            # Slider degerini integer'a cevir
            ayrilan = int(float(val))
            self.c_slider_vars[deger].set(ayrilan)
            self.c_slider_guncelle(deger)
        except (ValueError, KeyError):
            pass

    def c_slider_guncelle(self, deger):
        """C bolumu slider degistiginde guncelle - slider degeri ayrilan miktari"""
        try:
            sayim_adet = int(self.sayim_vars.get(deger, tk.StringVar(value="0")).get() or 0)
            ayrilan = self.c_slider_vars[deger].get()
            kalan = sayim_adet - ayrilan

            self.c_kalan_labels[deger].config(text=str(kalan))
            # Ayrilan adet label
            self.c_ayrilan_labels[deger].config(text=str(ayrilan))
            # Ayrilan tutar TL label
            ayrilan_tutar = ayrilan * deger
            if hasattr(self, 'c_ayrilan_tl_labels') and deger in self.c_ayrilan_tl_labels:
                self.c_ayrilan_tl_labels[deger].config(text=f"{ayrilan_tutar:,.0f} TL")
            self.c_toplamlari_guncelle()
        except (ValueError, KeyError):
            pass

    def c_entry_guncelle(self, deger):
        """Entry'den manuel deger girildiginde guncelle"""
        try:
            sayim_adet = int(self.sayim_vars.get(deger, tk.StringVar(value="0")).get() or 0)
            ayrilan = self.c_slider_vars[deger].get()

            # Ayrilan sayim adedinden buyuk olamaz
            if ayrilan > sayim_adet:
                ayrilan = sayim_adet
                self.c_slider_vars[deger].set(ayrilan)
            elif ayrilan < 0:
                ayrilan = 0
                self.c_slider_vars[deger].set(ayrilan)

            kalan = sayim_adet - ayrilan

            self.c_kalan_labels[deger].config(text=str(kalan))
            # Ayrilan adet label
            self.c_ayrilan_labels[deger].config(text=str(ayrilan))
            # Ayrilan tutar TL label
            ayrilan_tutar = ayrilan * deger
            if hasattr(self, 'c_ayrilan_tl_labels') and deger in self.c_ayrilan_tl_labels:
                self.c_ayrilan_tl_labels[deger].config(text=f"{ayrilan_tutar:,.0f} TL")
            self.c_toplamlari_guncelle()
        except (ValueError, KeyError):
            pass

    def c_toplamlari_guncelle(self):
        """C bolumu toplamlarini guncelle"""
        kalan_toplam = 0
        kalan_adet = 0
        ayrilan_toplam = 0
        ayrilan_adet = 0

        for deger, slider_var in self.c_slider_vars.items():
            try:
                sayim_adet = int(self.sayim_vars.get(deger, tk.StringVar(value="0")).get() or 0)
                ayrilan = slider_var.get()
                kalan = sayim_adet - ayrilan

                kalan_adet += kalan
                kalan_toplam += kalan * deger
                ayrilan_adet += ayrilan
                ayrilan_toplam += ayrilan * deger
            except (ValueError, KeyError):
                pass

        # Kalan toplam - Yarının Başlangıç Kasası etiketi
        self.c_kalan_toplam_label.config(text=f"Yarının Başlangıç Kasası: {kalan_toplam:,.0f} TL")
        # Ayrılan tutar toplam - Ayrılan Para etiketi
        self.c_ayrilan_toplam_label.config(text=f"Ayrılan Para: {ayrilan_toplam:,.0f} TL")

    def kasa_tablosu_guncelle(self):
        """11) tablosundaki sayim degerlerini 2. bolumden guncelle"""
        if not hasattr(self, 'c_sayim_labels'):
            return

        for deger in self.c_sayim_labels.keys():
            try:
                # 2. bolumden sayim adedini al
                sayim_adet = 0
                if deger in self.sayim_vars:
                    sayim_adet = int(self.sayim_vars[deger].get() or 0)

                # Sayim label guncelle
                if deger in self.c_sayim_labels:
                    self.c_sayim_labels[deger].config(text=str(sayim_adet))

                # Slider max degerini guncelle (ttk.Scale icin)
                if deger in self.c_sliders:
                    self.c_sliders[deger].config(to=max(1, sayim_adet))

                # Eger ayrilan sayim adedinden fazlaysa sifirla
                if deger in self.c_slider_vars:
                    mevcut_ayrilan = self.c_slider_vars[deger].get()
                    if mevcut_ayrilan > sayim_adet:
                        self.c_slider_vars[deger].set(0)

                # Kalan degeri guncelle (sayim - ayrilan)
                ayrilan = self.c_slider_vars.get(deger, tk.IntVar(value=0)).get()
                kalan = sayim_adet - ayrilan
                if deger in self.c_kalan_labels:
                    self.c_kalan_labels[deger].config(text=str(kalan))

                # Ayrilan adet ve tutar label'larini guncelle
                if deger in self.c_ayrilan_labels:
                    self.c_ayrilan_labels[deger].config(text=str(ayrilan))
                if hasattr(self, 'c_ayrilan_tl_labels') and deger in self.c_ayrilan_tl_labels:
                    ayrilan_tutar = ayrilan * deger
                    self.c_ayrilan_tl_labels[deger].config(text=f"{ayrilan_tutar:,.0f} TL")

            except (ValueError, KeyError):
                pass

        # Toplamlari guncelle
        self.c_toplamlari_guncelle()

    def c_ertesi_gun_belirle(self):
        """C bölümünden ertesi gün kasasını belirle"""
        kalan_kupurler = {}
        kalan_toplam = 0

        for deger, slider_var in self.c_slider_vars.items():
            kalan = slider_var.get()
            if kalan > 0:
                kalan_kupurler[str(deger)] = kalan
                kalan_toplam += kalan * deger

        self.ertesi_gun_belirlendi = True
        self.ertesi_gun_toplam_data = kalan_toplam
        self.ertesi_gun_kupurler_data = kalan_kupurler

        # Durum label'larını güncelle
        self.ertesi_gun_durum_label.config(
            text=f"Ertesi Gun: {kalan_toplam:,.2f} TL",
            fg='#4CAF50'
        )

        ayrilan_toplam = 0
        for deger, slider_var in self.c_slider_vars.items():
            sayim_adet = int(self.sayim_vars.get(deger, tk.StringVar(value="0")).get() or 0)
            ayrilan = sayim_adet - slider_var.get()
            ayrilan_toplam += ayrilan * deger

        self.ayrilan_para_durum_label.config(
            text=f"Ayrilan: {ayrilan_toplam:,.2f} TL",
            fg='#FF9800'
        )

        messagebox.showinfo("Basarili", f"Ertesi gun kasasi belirlendi:\n{kalan_toplam:,.2f} TL")

    def para_ayirma_penceresi_ac(self):
        """Para ayırma penceresini aç"""
        if self.para_ayirma_penceresi and self.para_ayirma_penceresi.winfo_exists():
            self.para_ayirma_penceresi.lift()
            return

        self.para_ayirma_penceresi = tk.Toplevel(self.root)
        self.para_ayirma_penceresi.title("Para Ayirma ve Ertesi Gun Kasasi")
        self.para_ayirma_penceresi.geometry("900x700")
        self.para_ayirma_penceresi.transient(self.root)
        self.para_ayirma_penceresi.configure(bg='#FAFAFA')

        # Başlık
        baslik_frame = tk.Frame(self.para_ayirma_penceresi, bg='#3F51B5', height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text="PARA AYIRMA VE ERTESİ GÜN KASASI BELİRLEME",
            font=("Arial", 14, "bold"),
            bg='#3F51B5',
            fg='white'
        ).pack(expand=True)

        # Ana içerik
        main_frame = tk.Frame(self.para_ayirma_penceresi, bg='#FAFAFA')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Scroll edilebilir alan
        canvas = tk.Canvas(main_frame, bg='#FAFAFA', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg='#FAFAFA')

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Başlık satırı
        header_frame = tk.Frame(scrollable, bg='#C5CAE9')
        header_frame.pack(fill="x", pady=(0, 5))

        tk.Label(header_frame, text="Küpür", font=("Arial", 10, "bold"), bg='#C5CAE9', width=10).pack(side="left", padx=5, pady=5)
        tk.Label(header_frame, text="Sayım", font=("Arial", 10, "bold"), bg='#C5CAE9', width=8).pack(side="left", padx=5, pady=5)
        tk.Label(header_frame, text="Kalan (Ertesi Gün)", font=("Arial", 10, "bold"), bg='#C5CAE9', width=15).pack(side="left", padx=5, pady=5)
        tk.Label(header_frame, text="Ayır", font=("Arial", 10, "bold"), bg='#C5CAE9', width=20).pack(side="left", padx=5, pady=5)
        tk.Label(header_frame, text="Ayrılan", font=("Arial", 10, "bold"), bg='#C5CAE9', width=10).pack(side="left", padx=5, pady=5)
        tk.Label(header_frame, text="Ayrılan TL", font=("Arial", 10, "bold"), bg='#C5CAE9', width=12).pack(side="left", padx=5, pady=5)

        # Küpür satırları
        self.slider_widgets = {}
        self.kalan_labels = {}
        self.ayrilan_labels = {}
        self.ayrilan_tl_labels = {}

        for kupur in self.KUPURLER:
            if self.kupur_aktif_mi(kupur["deger"]):
                self.para_ayirma_satiri_olustur(scrollable, kupur)

        # Toplam satırları
        ttk.Separator(scrollable, orient='horizontal').pack(fill="x", pady=10)

        # Toplam frame
        toplam_container = tk.Frame(scrollable, bg='#FAFAFA')
        toplam_container.pack(fill="x", pady=5)

        # Sol taraf - Kalan (Ertesi Gün) toplamı
        kalan_toplam_frame = tk.Frame(toplam_container, bg='#4CAF50')
        kalan_toplam_frame.pack(side="left", fill="x", expand=True, padx=5)

        tk.Label(kalan_toplam_frame, text="KALAN (ERTESİ GÜN KASASI):", font=("Arial", 11, "bold"),
                bg='#4CAF50', fg='white').pack(side="left", padx=10, pady=8)
        self.kalan_toplam_label = tk.Label(kalan_toplam_frame, text="0,00 TL", font=("Arial", 12, "bold"),
                                           bg='#4CAF50', fg='white')
        self.kalan_toplam_label.pack(side="right", padx=10, pady=8)

        # Sağ taraf - Ayrılan toplamı
        ayrilan_toplam_frame = tk.Frame(toplam_container, bg='#FF9800')
        ayrilan_toplam_frame.pack(side="left", fill="x", expand=True, padx=5)

        tk.Label(ayrilan_toplam_frame, text="AYRILAN PARA:", font=("Arial", 11, "bold"),
                bg='#FF9800', fg='white').pack(side="left", padx=10, pady=8)
        self.ayrilan_toplam_label = tk.Label(ayrilan_toplam_frame, text="0,00 TL", font=("Arial", 12, "bold"),
                                             bg='#FF9800', fg='white')
        self.ayrilan_toplam_label.pack(side="right", padx=10, pady=8)

        # Butonlar
        ttk.Separator(scrollable, orient='horizontal').pack(fill="x", pady=10)

        buton_frame = tk.Frame(scrollable, bg='#FAFAFA')
        buton_frame.pack(fill="x", pady=10)

        # Sol buton - Yarının başlangıç kasası yap
        self.ertesi_gun_btn = tk.Button(
            buton_frame,
            text="YARININ BAŞLANGIÇ KASASI YAP",
            font=("Arial", 11, "bold"),
            bg='#4CAF50',
            fg='white',
            activebackground='#388E3C',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=12,
            command=self.ertesi_gun_kasasi_belirle
        )
        self.ertesi_gun_btn.pack(side="left", padx=10)

        # Sağ buton - Ayrılan parayı ayır ve etiket bas
        self.ayrilan_para_btn = tk.Button(
            buton_frame,
            text="AYRILAN PARAYI AYIR VE ETİKET BAS",
            font=("Arial", 11, "bold"),
            bg='#FF9800',
            fg='white',
            activebackground='#F57C00',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=12,
            command=self.ayrilan_para_ayir_ve_bas
        )
        self.ayrilan_para_btn.pack(side="right", padx=10)

        # Kapat butonu
        tk.Button(
            buton_frame,
            text="KAPAT",
            font=("Arial", 10, "bold"),
            bg='#9E9E9E',
            fg='white',
            cursor='hand2',
            bd=0,
            padx=15,
            pady=8,
            command=self.para_ayirma_penceresi.destroy
        ).pack(side="bottom", pady=10)

        # Hesapları güncelle
        self.para_ayirma_hesapla()

    def para_ayirma_satiri_olustur(self, parent, kupur):
        """Para ayırma satırı oluştur - slider ile"""
        deger = kupur["deger"]

        row = tk.Frame(parent, bg='#FAFAFA')
        row.pack(fill="x", pady=2)

        # Küpür adı
        tk.Label(
            row,
            text=kupur["aciklama"],
            font=("Arial", 10),
            bg='#FAFAFA',
            width=10,
            anchor='w'
        ).pack(side="left", padx=5)

        # Sayım miktarı (gün sonu sayımından)
        try:
            sayim_adet = int(self.sayim_vars.get(deger, tk.StringVar(value="0")).get() or 0)
        except ValueError:
            sayim_adet = 0

        sayim_label = tk.Label(
            row,
            text=str(sayim_adet),
            font=("Arial", 10, "bold"),
            bg='#E3F2FD',
            width=8,
            anchor='center'
        )
        sayim_label.pack(side="left", padx=5)

        # Kalan miktar (ertesi gün kasası)
        kalan_var = tk.IntVar(value=sayim_adet)
        self.kalan_vars[deger] = kalan_var

        kalan_label = tk.Label(
            row,
            text=str(sayim_adet),
            font=("Arial", 10, "bold"),
            bg='#C8E6C9',
            fg='#1B5E20',
            width=15,
            anchor='center'
        )
        kalan_label.pack(side="left", padx=5)
        self.kalan_labels[deger] = kalan_label

        # Slider
        slider_var = tk.IntVar(value=0)
        self.slider_vars[deger] = slider_var

        slider = ttk.Scale(
            row,
            from_=0,
            to=sayim_adet,
            orient='horizontal',
            variable=slider_var,
            length=150,
            command=lambda val, d=deger: self.slider_degisti(d, val)
        )
        slider.pack(side="left", padx=5)
        self.slider_widgets[deger] = slider

        # Ayrılan miktar
        ayrilan_var = tk.IntVar(value=0)
        self.ayrilan_vars[deger] = ayrilan_var

        ayrilan_label = tk.Label(
            row,
            text="0",
            font=("Arial", 10, "bold"),
            bg='#FFE0B2',
            fg='#E65100',
            width=10,
            anchor='center'
        )
        ayrilan_label.pack(side="left", padx=5)
        self.ayrilan_labels[deger] = ayrilan_label

        # Ayrılan TL
        ayrilan_tl_label = tk.Label(
            row,
            text="0,00",
            font=("Arial", 10),
            bg='#FAFAFA',
            width=12,
            anchor='e'
        )
        ayrilan_tl_label.pack(side="left", padx=5)
        self.ayrilan_tl_labels[deger] = ayrilan_tl_label

        # Tümünü ayır butonu
        tk.Button(
            row,
            text=">>",
            font=("Arial", 9, "bold"),
            bg='#FF9800',
            fg='white',
            width=3,
            bd=0,
            cursor='hand2',
            command=lambda d=deger, s=sayim_adet: self.tumunu_ayir(d, s)
        ).pack(side="left", padx=2)

        # Tümünü geri al butonu
        tk.Button(
            row,
            text="<<",
            font=("Arial", 9, "bold"),
            bg='#4CAF50',
            fg='white',
            width=3,
            bd=0,
            cursor='hand2',
            command=lambda d=deger: self.tumunu_geri_al(d)
        ).pack(side="left", padx=2)

    def slider_degisti(self, deger, val):
        """Slider değeri değiştiğinde"""
        try:
            ayrilan = int(float(val))
            sayim_adet = int(self.sayim_vars.get(deger, tk.StringVar(value="0")).get() or 0)
            kalan = sayim_adet - ayrilan

            self.ayrilan_vars[deger].set(ayrilan)
            self.kalan_vars[deger].set(kalan)

            # Label'ları güncelle
            self.kalan_labels[deger].config(text=str(kalan))
            self.ayrilan_labels[deger].config(text=str(ayrilan))
            self.ayrilan_tl_labels[deger].config(text=f"{ayrilan * deger:,.2f}")

            self.para_ayirma_hesapla()
        except (ValueError, KeyError):
            pass

    def tumunu_ayir(self, deger, maksimum):
        """Tüm küpürleri ayır"""
        self.slider_vars[deger].set(maksimum)
        self.slider_degisti(deger, maksimum)

    def tumunu_geri_al(self, deger):
        """Tüm küpürleri geri al"""
        self.slider_vars[deger].set(0)
        self.slider_degisti(deger, 0)

    def para_ayirma_hesapla(self):
        """Para ayırma toplamlarını hesapla"""
        kalan_toplam = 0
        ayrilan_toplam = 0

        for deger in self.kalan_vars:
            kalan = self.kalan_vars[deger].get()
            ayrilan = self.ayrilan_vars[deger].get()
            kalan_toplam += kalan * deger
            ayrilan_toplam += ayrilan * deger

        self.kalan_toplam_label.config(text=f"{kalan_toplam:,.2f} TL")
        self.ayrilan_toplam_label.config(text=f"{ayrilan_toplam:,.2f} TL")

    def ertesi_gun_kasasi_belirle(self):
        """Ertesi gün kasasını belirle ve veritabanına kaydet"""
        # 11. tablodaki KALAN küpürleri topla (sayım - ayrılan)
        kalan_kupurler = {}
        kalan_toplam = 0

        for deger, slider_var in self.c_slider_vars.items():
            try:
                sayim_adet = int(self.sayim_vars.get(deger, tk.StringVar(value="0")).get() or 0)
                ayrilan = slider_var.get()
                kalan = sayim_adet - ayrilan
                if kalan > 0:
                    kalan_kupurler[str(deger)] = kalan
                    kalan_toplam += kalan * deger
            except (ValueError, KeyError):
                pass

        if kalan_toplam == 0:
            if not messagebox.askyesno("Onay", "Ertesi gün kasası 0 TL olarak belirlenecek. Devam etmek istiyor musunuz?"):
                return

        # Ertesi gün kasası verilerini sakla
        self.ertesi_gun_kupurler_data = kalan_kupurler
        self.ertesi_gun_toplam_data = kalan_toplam
        self.ertesi_gun_belirlendi = True

        # Butonları güncelle - tutarı göster
        self.ertesi_gun_btn.config(bg='#2E7D32', text=f"{kalan_toplam:,.0f} TL YARININ KASASI BELİRLENDİ")

        # Ana ekrandaki durum etiketini güncelle
        self.ertesi_gun_durum_label.config(
            text=f"Ertesi Gün Kasası: {kalan_toplam:,.2f} TL",
            fg='#2E7D32'
        )

        messagebox.showinfo(
            "Başarılı",
            f"Yarının başlangıç kasası belirlendi!\n\n"
            f"Toplam: {kalan_toplam:,.2f} TL\n\n"
            f"Bu değer program tekrar açıldığında başlangıç kasası olarak gelecektir."
        )

    def ayrilan_para_ayir_ve_bas(self):
        """Ayrılan parayı ayır ve termal yazıcıdan etiket bas"""
        # 11. tablodaki AYRILAN küpürleri topla (slider değeri)
        ayrilan_kupurler = {}
        ayrilan_toplam = 0

        for deger, slider_var in self.c_slider_vars.items():
            try:
                ayrilan = slider_var.get()
                if ayrilan > 0:
                    ayrilan_kupurler[str(deger)] = ayrilan
                    ayrilan_toplam += ayrilan * deger
            except (ValueError, KeyError):
                pass

        if ayrilan_toplam == 0:
            messagebox.showwarning("Uyarı", "Ayrılacak para yok!")
            return

        # Ayrılan para verilerini sakla
        self.ayrilan_kupurler_data = ayrilan_kupurler
        self.ayrilan_toplam_data = ayrilan_toplam
        self.ayrilan_para_belirlendi = True

        # Butonları güncelle - tutarı göster
        self.ayrilan_para_btn.config(bg='#E65100', text=f"{ayrilan_toplam:,.0f} TL AYRILAN PARA BELİRLENDİ")

        # Ana ekrandaki durum etiketini güncelle
        self.ayrilan_para_durum_label.config(
            text=f"Ayrılan Para: {ayrilan_toplam:,.2f} TL",
            fg='#E65100'
        )

        # Termal yazıcıdan etiket bas
        self.termal_etiket_bas(ayrilan_kupurler, ayrilan_toplam)

    def termal_etiket_bas(self, kupurler, toplam):
        """Termal yazıcıdan etiket bas"""
        try:
            tarih = datetime.now().strftime("%d.%m.%Y")
            saat = datetime.now().strftime("%H:%M")

            # Etiket içeriği oluştur
            etiket_metni = []
            etiket_metni.append("=" * 32)
            etiket_metni.append("    AYRILAN PARA ETİKETİ")
            etiket_metni.append("=" * 32)
            etiket_metni.append(f"Tarih: {tarih}  Saat: {saat}")
            etiket_metni.append("-" * 32)
            etiket_metni.append(f"TOPLAM: {toplam:,.2f} TL")
            etiket_metni.append("-" * 32)
            etiket_metni.append("KUPUR DOKUMU:")

            for kupur in self.KUPURLER:
                deger = kupur["deger"]
                adet = kupurler.get(str(deger), 0)
                if adet > 0:
                    tutar = adet * deger
                    etiket_metni.append(f"  {kupur['aciklama']:8} x {adet:3} = {tutar:>10,.2f}")

            etiket_metni.append("-" * 32)

            # Kasa özeti ekle
            try:
                nakit = sum(int(self.sayim_vars.get(d, tk.StringVar(value="0")).get() or 0) * d for d in self.sayim_vars)
                pos = sum(self.sayi_al(v) for v in self.pos_vars)
                iban = sum(self.sayi_al(v) for v in self.iban_vars)
                genel = nakit + pos + iban

                etiket_metni.append("KASA OZETI:")
                etiket_metni.append(f"  Nakit: {nakit:>15,.2f} TL")
                etiket_metni.append(f"  POS:   {pos:>15,.2f} TL")
                etiket_metni.append(f"  IBAN:  {iban:>15,.2f} TL")
                etiket_metni.append(f"  GENEL: {genel:>15,.2f} TL")
            except Exception:
                pass

            etiket_metni.append("=" * 32)
            etiket_metni.append("")

            # Dosyaya yaz (termal yazıcı için)
            etiket_dosyasi = Path(os.path.dirname(os.path.abspath(__file__))) / "ayrilan_para_etiket.txt"
            with open(etiket_dosyasi, 'w', encoding='utf-8') as f:
                f.write('\n'.join(etiket_metni))

            # Termal yazıcıya gönder
            try:
                import subprocess
                # Windows'ta varsayılan yazıcıya gönder
                subprocess.run(['notepad', '/p', str(etiket_dosyasi)], check=False)
                logger.info(f"Ayrilan para etiketi basildi: {toplam:,.2f} TL")
            except Exception as e:
                logger.warning(f"Yazici hatasi: {e}")
                # Yazıcı yoksa dosyayı aç
                try:
                    os.startfile(str(etiket_dosyasi))
                except Exception:
                    pass

            messagebox.showinfo(
                "Etiket Basildi",
                f"Ayrilan para etiketi basildi!\n\n"
                f"Toplam: {toplam:,.2f} TL\n\n"
                f"Etiket dosyasi: {etiket_dosyasi}"
            )

        except Exception as e:
            logger.error(f"Etiket basma hatasi: {e}")
            messagebox.showerror("Hata", f"Etiket basma hatasi: {e}")

    def masraf_bolumu_olustur(self):
        """4) B Bolumu - Islenmemis masraflar"""
        frame = tk.LabelFrame(
            self.b_bolumu_frame,
            text="4) İŞLENMEMİŞ MASRAFLAR",
            font=("Arial", 11, "bold"),
            bg=self.section_colors['masraf'],
            fg='#E65100',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True, pady=2)

        for i in range(3):
            row = tk.Frame(frame, bg=self.section_colors['masraf'])
            row.pack(fill="x", pady=1)

            tk.Label(row, text=f"M{i+1}:", font=("Arial", 10),
                    bg=self.section_colors['masraf'], fg=self.detay_fg, width=4, anchor='w').pack(side="left")

            tutar_var = tk.StringVar(value="0")
            aciklama_var = tk.StringVar(value="")
            self.masraf_vars.append((tutar_var, aciklama_var))

            tutar_entry = tk.Entry(row, textvariable=tutar_var, font=("Arial", 10), width=10, justify='right')
            tutar_entry.pack(side="left", padx=2)
            tutar_entry.bind('<FocusOut>', lambda e, v=tutar_var: self.masraf_uyari_kontrol(v))
            tutar_entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())

            aciklama_entry = tk.Entry(row, textvariable=aciklama_var, font=("Arial", 9), width=12)
            aciklama_entry.pack(side="left", padx=2)

        # Masraf Toplam
        toplam_frame = tk.Frame(frame, bg=self.ara_toplam_bg)
        toplam_frame.pack(fill="x", pady=(2, 0))

        tk.Label(
            toplam_frame,
            text="MASRAF TOPLAM:",
            font=("Arial", 10, "bold"),
            bg=self.ara_toplam_bg,
            fg=self.ara_toplam_fg
        ).pack(side="left", padx=5, pady=2)

        self.masraf_toplam_label = tk.Label(
            toplam_frame,
            text="0,00",
            font=("Arial", 11, "bold"),
            bg=self.ara_toplam_bg,
            fg=self.ara_toplam_fg
        )
        self.masraf_toplam_label.pack(side="right", padx=5, pady=2)

    def masraf_uyari_kontrol(self, var):
        """Masraf girişi uyarısı"""
        try:
            deger = float(var.get().replace(",", ".") or 0)
            if deger > 0:
                onay = messagebox.askyesno(
                    "Masraf Uyarisi - DIKKAT!",
                    "ONEMLI UYARI!\n\n"
                    "Lutfen masraflari Botanik EOS programina isleyin ve boylece "
                    "buraya veri girmeye gerek kalmasin.\n\n"
                    "Istenen durum: Burada islenmemis bir masrafin kalmamis olmasidir.\n\n"
                    "Eger bir sebepten EOS'a islenemiyorsa, mecburi hallerde "
                    "kasayi tutturabilmek icin buraya veri girilebilir.\n\n"
                    "Bu masrafi buraya girmeyi onayliyor musunuz?"
                )
                if not onay:
                    var.set("0")
                    self.hesaplari_guncelle()
        except ValueError:
            pass

    def silinen_bolumu_olustur(self):
        """5) B Bolumu - Silinen recete etkileri"""
        frame = tk.LabelFrame(
            self.b_bolumu_frame,
            text="5) SİLİNEN REÇETE ETKİSİ",
            font=("Arial", 11, "bold"),
            bg=self.section_colors['silinen'],
            fg='#AD1457',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True, pady=2)

        for i in range(3):
            row = tk.Frame(frame, bg=self.section_colors['silinen'])
            row.pack(fill="x", pady=1)

            tk.Label(row, text=f"S{i+1}:", font=("Arial", 10),
                    bg=self.section_colors['silinen'], fg=self.detay_fg, width=4, anchor='w').pack(side="left")

            tutar_var = tk.StringVar(value="0")
            aciklama_var = tk.StringVar(value="")
            self.silinen_vars.append((tutar_var, aciklama_var))

            tutar_entry = tk.Entry(row, textvariable=tutar_var, font=("Arial", 10), width=10, justify='right')
            tutar_entry.pack(side="left", padx=2)
            tutar_entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())

            aciklama_entry = tk.Entry(row, textvariable=aciklama_var, font=("Arial", 9), width=12)
            aciklama_entry.pack(side="left", padx=2)

        # Silinen Toplam
        toplam_frame = tk.Frame(frame, bg=self.ara_toplam_bg)
        toplam_frame.pack(fill="x", pady=(2, 0))

        tk.Label(
            toplam_frame,
            text="SİLİNEN TOPLAM:",
            font=("Arial", 10, "bold"),
            bg=self.ara_toplam_bg,
            fg=self.ara_toplam_fg
        ).pack(side="left", padx=5, pady=2)

        self.silinen_toplam_label = tk.Label(
            toplam_frame,
            text="0,00",
            font=("Arial", 11, "bold"),
            bg=self.ara_toplam_bg,
            fg=self.ara_toplam_fg
        )
        self.silinen_toplam_label.pack(side="right", padx=5, pady=2)

    def gun_ici_alinan_bolumu_olustur(self):
        """6) B Bolumu - Gun ici alinan paralar"""
        frame = tk.LabelFrame(
            self.b_bolumu_frame,
            text="6) ALINAN PARALAR",
            font=("Arial", 11, "bold"),
            bg=self.section_colors['alinan'],
            fg='#C62828',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True, pady=2)

        for i in range(3):
            row = tk.Frame(frame, bg=self.section_colors['alinan'])
            row.pack(fill="x", pady=1)

            tk.Label(row, text=f"A{i+1}:", font=("Arial", 10),
                    bg=self.section_colors['alinan'], fg=self.detay_fg, width=4, anchor='w').pack(side="left")

            tutar_var = tk.StringVar(value="0")
            aciklama_var = tk.StringVar(value="")
            self.gun_ici_alinan_vars.append((tutar_var, aciklama_var))

            tutar_entry = tk.Entry(row, textvariable=tutar_var, font=("Arial", 10), width=10, justify='right')
            tutar_entry.pack(side="left", padx=2)
            tutar_entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())

            aciklama_entry = tk.Entry(row, textvariable=aciklama_var, font=("Arial", 9), width=12)
            aciklama_entry.pack(side="left", padx=2)

        # Alinan Toplam
        toplam_frame = tk.Frame(frame, bg=self.ara_toplam_bg)
        toplam_frame.pack(fill="x", pady=(2, 0))

        tk.Label(
            toplam_frame,
            text="ALINAN TOPLAM:",
            font=("Arial", 10, "bold"),
            bg=self.ara_toplam_bg,
            fg=self.ara_toplam_fg
        ).pack(side="left", padx=5, pady=2)

        self.alinan_toplam_label = tk.Label(
            toplam_frame,
            text="0,00",
            font=("Arial", 11, "bold"),
            bg=self.ara_toplam_bg,
            fg=self.ara_toplam_fg
        )
        self.alinan_toplam_label.pack(side="right", padx=5, pady=2)

    def b_ozet_bolumu_olustur(self):
        """B Bölümü özet - Formül açıklaması (SON GENEL TOPLAM artık A bölümünde yan yana)"""
        frame = tk.Frame(
            self.b_bolumu_frame,
            bg=self.section_colors['ozet'],
            padx=10,
            pady=5
        )
        frame.pack(fill="x", pady=5)

        # Formül açıklaması
        tk.Label(
            frame,
            text="SON GENEL = GENEL TOPLAM + Masraf + Silinen + Alınan",
            font=("Arial", 9, "italic"),
            bg=self.section_colors['ozet'],
            fg='#666'
        ).pack(anchor='center')

    def botanik_bolumu_olustur(self):
        """8) B Bolumu - Botanik EOS verileri"""
        frame = tk.LabelFrame(
            self.b_bolumu_frame,
            text="8) BOTANİK EOS VERİLERİ",
            font=("Arial", 11, "bold"),
            bg=self.section_colors['botanik'],
            fg='#F57F17',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True, pady=2)

        # Botanik Nakit
        nakit_frame = tk.Frame(frame, bg=self.section_colors['botanik'])
        nakit_frame.pack(fill="x", pady=1)
        tk.Label(nakit_frame, text="Nakit:", font=("Arial", 10, "bold"),
                bg=self.section_colors['botanik'], width=6, anchor='w').pack(side="left")
        entry1 = tk.Entry(nakit_frame, textvariable=self.botanik_nakit_var, font=("Arial", 10), width=12, justify='right')
        entry1.pack(side="right", padx=5)
        entry1.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
        entry1.bind('<FocusIn>', self.entry_fokus_secim)

        # Botanik POS
        pos_frame = tk.Frame(frame, bg=self.section_colors['botanik'])
        pos_frame.pack(fill="x", pady=1)
        tk.Label(pos_frame, text="POS:", font=("Arial", 10, "bold"),
                bg=self.section_colors['botanik'], width=6, anchor='w').pack(side="left")
        entry2 = tk.Entry(pos_frame, textvariable=self.botanik_pos_var, font=("Arial", 10), width=12, justify='right')
        entry2.pack(side="right", padx=5)
        entry2.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
        entry2.bind('<FocusIn>', self.entry_fokus_secim)

        # Botanik IBAN
        iban_frame = tk.Frame(frame, bg=self.section_colors['botanik'])
        iban_frame.pack(fill="x", pady=1)
        tk.Label(iban_frame, text="IBAN:", font=("Arial", 10, "bold"),
                bg=self.section_colors['botanik'], width=6, anchor='w').pack(side="left")
        entry3 = tk.Entry(iban_frame, textvariable=self.botanik_iban_var, font=("Arial", 10), width=12, justify='right')
        entry3.pack(side="right", padx=5)
        entry3.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
        entry3.bind('<FocusIn>', self.entry_fokus_secim)

        # Botanik Genel Toplam
        bot_toplam_frame = tk.Frame(frame, bg='#F57F17')
        bot_toplam_frame.pack(fill="x", pady=(2, 0))
        tk.Label(bot_toplam_frame, text="BOTANIK TOPLAM:", font=("Arial", 10, "bold"),
                bg='#F57F17', fg='white').pack(side="left", padx=5, pady=2)
        self.botanik_toplam_label = tk.Label(bot_toplam_frame, text="0,00", font=("Arial", 11, "bold"),
                                             bg='#F57F17', fg='white')
        self.botanik_toplam_label.pack(side="right", padx=5, pady=2)

    def duzeltilmis_nakit_bolumu_olustur(self):
        """7) Duzeltilmis nakit hesaplama bolumu"""
        frame = tk.LabelFrame(
            self.b_bolumu_frame,
            text="7) DÜZELTİLMİŞ NAKİT",
            font=("Arial", 11, "bold"),
            bg='#E8EAF6',
            fg='#303F9F',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True, pady=2)

        # Kasa Sayim Toplami (Aksam sayimi)
        row1 = tk.Frame(frame, bg='#E8EAF6')
        row1.pack(fill="x", pady=1)
        tk.Label(row1, text="Sayım:", font=("Arial", 10),
                bg='#E8EAF6', fg='#333', anchor='w').pack(side="left", padx=5)
        self.c_nakit_toplam_label = tk.Label(row1, text="0,00", font=("Arial", 10, "bold"),
                bg='#E8EAF6', fg='#1565C0', anchor='e')
        self.c_nakit_toplam_label.pack(side="right", padx=5)

        # Girilmemis Masraflar (+)
        row2 = tk.Frame(frame, bg='#FFF3E0')
        row2.pack(fill="x", pady=1)
        tk.Label(row2, text="(+) Masraf:", font=("Arial", 10),
                bg='#FFF3E0', fg='#E65100', anchor='w').pack(side="left", padx=5)
        self.c_masraf_label = tk.Label(row2, text="0,00", font=("Arial", 10, "bold"),
                bg='#FFF3E0', fg='#E65100', anchor='e')
        self.c_masraf_label.pack(side="right", padx=5)

        # Silinen Recete Etkisi (+)
        row3 = tk.Frame(frame, bg='#FCE4EC')
        row3.pack(fill="x", pady=1)
        tk.Label(row3, text="(+) Silinen:", font=("Arial", 10),
                bg='#FCE4EC', fg='#AD1457', anchor='w').pack(side="left", padx=5)
        self.c_silinen_label = tk.Label(row3, text="0,00", font=("Arial", 10, "bold"),
                bg='#FCE4EC', fg='#AD1457', anchor='e')
        self.c_silinen_label.pack(side="right", padx=5)

        # Alinan Paralar (+)
        row4 = tk.Frame(frame, bg='#FFEBEE')
        row4.pack(fill="x", pady=1)
        tk.Label(row4, text="(+) Alınan:", font=("Arial", 10),
                bg='#FFEBEE', fg='#C62828', anchor='w').pack(side="left", padx=5)
        self.c_alinan_label = tk.Label(row4, text="0,00", font=("Arial", 10, "bold"),
                bg='#FFEBEE', fg='#C62828', anchor='e')
        self.c_alinan_label.pack(side="right", padx=5)

        # Duzeltilmis Nakit Genel Toplami
        row5 = tk.Frame(frame, bg='#303F9F')
        row5.pack(fill="x", pady=(2, 0))
        tk.Label(row5, text="DÜZELTİLMİŞ NAKİT:", font=("Arial", 10, "bold"),
                bg='#303F9F', fg='white', anchor='w').pack(side="left", padx=5, pady=2)
        self.c_duzeltilmis_nakit_label = tk.Label(row5, text="0,00", font=("Arial", 11, "bold"),
                bg='#303F9F', fg='#FFEB3B', anchor='e')
        self.c_duzeltilmis_nakit_label.pack(side="right", padx=5, pady=2)

    def islem_butonlari_olustur(self):
        """12-16) - Eski fonksiyon, artık alt_butonlar_olustur kullanılıyor"""
        pass  # Butonlar artık alt_butonlar_olustur'da

    def ayrilan_para_isle(self):
        """12) Ayrılan parayı belirle ve işle"""
        # Önce kasa tablosunu aç
        if not self.kasa_tablo_acik:
            self.para_ayirma_tablosu_goster()
        messagebox.showinfo("Ayrılan Para", "Kasa sayım tablosundan ayrılan parayı belirleyip işleyebilirsiniz.")

    def ertesi_gun_kasasi_isle(self):
        """13) Ertesi gün kasasını belirle ve işle"""
        # Önce kasa tablosunu aç
        if not self.kasa_tablo_acik:
            self.para_ayirma_tablosu_goster()
        messagebox.showinfo("Ertesi Gün Kasası", "Kasa sayım tablosundan ertesi gün kasasını belirleyip işleyebilirsiniz.")

    def ayrilan_para_yazdir(self):
        """15) Ayrılan para çıktısı yazdır"""
        try:
            from kasa_yazici import ayrilan_para_yazdir
            ayrilan_para = self.ayrilan_para_durum_label.cget("text")
            if "Belirlenmedi" in ayrilan_para:
                messagebox.showwarning("Uyarı", "Önce ayrılan parayı belirleyin!")
                return
            ayrilan_para_yazdir(self.ayarlar, self.root)
        except ImportError:
            messagebox.showerror("Hata", "Yazıcı modülü bulunamadı!")
        except Exception as e:
            messagebox.showerror("Hata", f"Yazdırma hatası: {e}")

    def alt_kaydet_olustur(self):
        """Alt kaydet butonu - artık alt_butonlar_olustur kullanılıyor"""
        pass  # Kaydet butonu artık alt_butonlar_olustur'da

    def sayi_al(self, var):
        """StringVar'dan güvenli sayı al"""
        try:
            deger = var.get().replace(",", ".").replace(" ", "").strip()
            return float(deger) if deger else 0
        except ValueError:
            return 0

    def hesaplari_guncelle(self):
        """Tüm hesapları güncelle"""
        # Sayım toplamı (NAKİT TOPLAM = Sadece gün sonu sayımı)
        nakit_toplam = 0
        for deger, var in self.sayim_vars.items():
            try:
                adet = int(var.get() or 0)
                nakit_toplam += adet * deger
            except ValueError:
                pass
        self.sayim_toplam_label.config(text=f"{nakit_toplam:,.2f} TL")

        # POS toplamları - EczPOS (ilk 4), Ingenico (sonraki 4)
        eczpos_toplam = sum(self.sayi_al(var) for var in self.pos_vars[:4])
        ingenico_toplam = sum(self.sayi_al(var) for var in self.pos_vars[4:8])
        pos_toplam = eczpos_toplam + ingenico_toplam

        # Her bir POS tipinin toplamını güncelle
        if hasattr(self, 'eczpos_toplam_label'):
            self.eczpos_toplam_label.config(text=f"{eczpos_toplam:,.2f} TL")
        if hasattr(self, 'ingenico_toplam_label'):
            self.ingenico_toplam_label.config(text=f"{ingenico_toplam:,.2f} TL")
        self.pos_toplam_label.config(text=f"{pos_toplam:,.2f} TL")

        # IBAN toplamı
        iban_toplam = sum(self.sayi_al(var) for var in self.iban_vars)
        self.iban_toplam_label.config(text=f"{iban_toplam:,.2f} TL")

        # Masraf toplamı
        masraf_toplam = sum(self.sayi_al(tutar_var) for tutar_var, _ in self.masraf_vars)
        self.masraf_toplam_label.config(text=f"{masraf_toplam:,.2f} TL")

        # Silinen reçete toplamı
        silinen_toplam = sum(self.sayi_al(tutar_var) for tutar_var, _ in self.silinen_vars)
        self.silinen_toplam_label.config(text=f"{silinen_toplam:,.2f} TL")

        # Gün içi alınan toplamı
        alinan_toplam = sum(self.sayi_al(tutar_var) for tutar_var, _ in self.gun_ici_alinan_vars)
        self.alinan_toplam_label.config(text=f"{alinan_toplam:,.2f} TL")

        # Özet güncelle
        self.ozet_nakit_label.config(text=f"{nakit_toplam:,.2f} TL")
        self.ozet_pos_label.config(text=f"{pos_toplam:,.2f} TL")
        self.ozet_iban_label.config(text=f"{iban_toplam:,.2f} TL")

        # GENEL TOPLAM = NAKİT + POS + IBAN
        genel_toplam = nakit_toplam + pos_toplam + iban_toplam
        self.genel_toplam_label.config(text=f"{genel_toplam:,.2f} TL")

        # A bölümü özetindeki ek kalem label'larını güncelle
        self.ozet_masraf_label.config(text=f"{masraf_toplam:,.2f} TL")
        self.ozet_silinen_label.config(text=f"{silinen_toplam:,.2f} TL")
        self.ozet_alinan_label.config(text=f"{alinan_toplam:,.2f} TL")

        # Düzeltilmiş Nakit = Kasa Sayımı + Masraf + Silinen + Alınan
        # (Kasadan çıkan paralar eklenerek botanikle karşılaştırılabilir hale getiriliyor)
        duzeltilmis_nakit = nakit_toplam + masraf_toplam + silinen_toplam + alinan_toplam
        self.duzeltilmis_nakit_label.config(text=f"{duzeltilmis_nakit:,.2f} TL")

        # 7. bölümdeki düzeltilmiş nakit hesaplama label'larını güncelle
        self.c_nakit_toplam_label.config(text=f"{nakit_toplam:,.2f}")
        self.c_masraf_label.config(text=f"{masraf_toplam:,.2f}")
        self.c_silinen_label.config(text=f"{silinen_toplam:,.2f}")
        self.c_alinan_label.config(text=f"{alinan_toplam:,.2f}")
        self.c_duzeltilmis_nakit_label.config(text=f"{duzeltilmis_nakit:,.2f}")

        # Botanik toplamları
        botanik_nakit = self.sayi_al(self.botanik_nakit_var)
        botanik_pos = self.sayi_al(self.botanik_pos_var)
        botanik_iban = self.sayi_al(self.botanik_iban_var)
        botanik_toplam = botanik_nakit + botanik_pos + botanik_iban
        self.botanik_toplam_label.config(text=f"{botanik_toplam:,.2f} TL")

        # Karşılaştırma tablosu - Botanik değerlerini güncelle
        self.botanik_nakit_gosterge.config(text=f"{botanik_nakit:,.2f} TL")
        self.botanik_pos_gosterge.config(text=f"{botanik_pos:,.2f} TL")
        self.botanik_iban_gosterge.config(text=f"{botanik_iban:,.2f} TL")
        self.botanik_toplam_gosterge.config(text=f"{botanik_toplam:,.2f} TL")

        # Fark hesaplamaları
        nakit_fark = duzeltilmis_nakit - botanik_nakit
        pos_fark = pos_toplam - botanik_pos
        iban_fark = iban_toplam - botanik_iban

        # Genel toplam (düzeltilmiş nakit + pos + iban)
        genel_toplam_duzeltilmis = duzeltilmis_nakit + pos_toplam + iban_toplam
        self.genel_toplam_label.config(text=f"{genel_toplam_duzeltilmis:,.2f} TL")
        genel_fark = genel_toplam_duzeltilmis - botanik_toplam

        # Fark label'larını güncelle ve renkleri ayarla
        def fark_formatla(fark_degeri, label):
            if abs(fark_degeri) < 0.01:
                renk = '#9E9E9E'  # Gri - fark yok
                metin = "0,00 TL"
            elif fark_degeri > 0:
                renk = '#4CAF50'  # Yeşil - artı (fazla)
                metin = f"+{fark_degeri:,.2f} TL"
            else:
                renk = '#F44336'  # Kırmızı - eksi (eksik)
                metin = f"{fark_degeri:,.2f} TL"
            label.config(text=metin)
            return renk

        fark_formatla(nakit_fark, self.nakit_fark_label)
        fark_formatla(pos_fark, self.pos_fark_label)
        fark_formatla(iban_fark, self.iban_fark_label)
        genel_renk = fark_formatla(genel_fark, self.genel_fark_label)

        # Fark label güncelle (9. bölümdeki)
        fark_text = f"FARK: {genel_fark:+,.2f} TL"
        tolerans = self.ayarlar.get("kabul_edilebilir_fark", 10.0)

        if abs(genel_fark) <= tolerans:
            # Tolerans dahilinde - yeşil
            self.fark_label.config(text=fark_text, bg='#4CAF50', fg='white')
            self.genel_fark_label.config(bg='#4CAF50', fg='white')
        else:
            # Tolerans aşıldı - kırmızı
            self.fark_label.config(text=fark_text, bg='#F44336', fg='white')
            self.genel_fark_label.config(bg='#F44336', fg='white')

        # Fark durumuna gore 10) bolumunde uygun sekmeyi sec
        if hasattr(self, 'tutarsizlik_notebook'):
            if genel_fark < 0:
                self.tutarsizlik_notebook.select(0)  # Kasa acik
            else:
                self.tutarsizlik_notebook.select(1)  # Kasa fazla

        # 11) Ertesi Gun Kasasi tablosunu guncelle (2. bolumden veri al)
        self.kasa_tablosu_guncelle()

    def gun_ici_alinan_kontrol(self):
        """Gün içi alınan paralar için açıklama zorunluluk kontrolü"""
        eksik_aciklama = []
        for i, (tutar_var, aciklama_var) in enumerate(self.gun_ici_alinan_vars):
            tutar = self.sayi_al(tutar_var)
            aciklama = aciklama_var.get().strip()
            if tutar > 0 and not aciklama:
                eksik_aciklama.append(f"Alinan {i+1}")

        if eksik_aciklama:
            messagebox.showwarning(
                "Eksik Aciklama",
                f"Gun ici alinan paralar icin aciklama zorunludur!\n\n"
                f"Eksik olan satirlar: {', '.join(eksik_aciklama)}\n\n"
                f"Lutfen kim neden aldigini belirtin."
            )
            return False
        return True

    def kaydet(self):
        """Kasa kapatma verilerini kaydet"""
        # Gün içi alınan açıklama kontrolü
        if not self.gun_ici_alinan_kontrol():
            return

        try:
            tarih = datetime.now().strftime("%Y-%m-%d")
            saat = datetime.now().strftime("%H:%M:%S")
            olusturma_zamani = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Başlangıç kasası
            baslangic_kupurler = {str(d): int(v.get() or 0) for d, v in self.baslangic_kupur_vars.items()}
            baslangic_toplam = sum(int(v.get() or 0) * d for d, v in self.baslangic_kupur_vars.items())

            # Sayım
            sayim_kupurler = {str(d): int(v.get() or 0) for d, v in self.sayim_vars.items()}
            nakit_toplam = sum(int(v.get() or 0) * d for d, v in self.sayim_vars.items())

            # POS ve IBAN
            pos_toplam = sum(self.sayi_al(var) for var in self.pos_vars)
            iban_toplam = sum(self.sayi_al(var) for var in self.iban_vars)

            # Masraf, Silinen, Alınan
            masraf_toplam = sum(self.sayi_al(t) for t, _ in self.masraf_vars)
            silinen_toplam = sum(self.sayi_al(t) for t, _ in self.silinen_vars)
            alinan_toplam = sum(self.sayi_al(t) for t, _ in self.gun_ici_alinan_vars)

            # Toplamlar
            genel_toplam = nakit_toplam + pos_toplam + iban_toplam
            son_genel_toplam = genel_toplam + masraf_toplam + silinen_toplam + alinan_toplam

            # Botanik
            botanik_nakit = self.sayi_al(self.botanik_nakit_var)
            botanik_pos = self.sayi_al(self.botanik_pos_var)
            botanik_iban = self.sayi_al(self.botanik_iban_var)
            botanik_toplam = botanik_nakit + botanik_pos + botanik_iban

            # Fark
            fark = son_genel_toplam - botanik_toplam

            # 11. tablodaki KALAN ve AYRILAN değerlerini hesapla
            kalan_kupurler = {}
            kalan_toplam = 0
            ayrilan_kupurler = {}
            ayrilan_toplam = 0

            if hasattr(self, 'c_slider_vars'):
                for deger, slider_var in self.c_slider_vars.items():
                    try:
                        sayim_adet = int(self.sayim_vars.get(deger, tk.StringVar(value="0")).get() or 0)
                        ayrilan_adet = slider_var.get()
                        kalan_adet = sayim_adet - ayrilan_adet

                        if kalan_adet > 0:
                            kalan_kupurler[str(deger)] = kalan_adet
                            kalan_toplam += kalan_adet * deger
                        if ayrilan_adet > 0:
                            ayrilan_kupurler[str(deger)] = ayrilan_adet
                            ayrilan_toplam += ayrilan_adet * deger
                    except (ValueError, KeyError):
                        pass

            # Ertesi gün kasası - 11. tablodaki kalan (slider ayarlanmamışsa sayım değerleri)
            if kalan_toplam > 0:
                ertesi_gun_kasasi = kalan_toplam
                ertesi_gun_kupurler = kalan_kupurler
            else:
                ertesi_gun_kasasi = nakit_toplam
                ertesi_gun_kupurler = sayim_kupurler

            # Ayrılan para - 11. tablodaki ayrılan
            ayrilan_para = ayrilan_toplam

            # Detay JSON
            detay = {
                "baslangic_kupurler": baslangic_kupurler,
                "sayim_kupurler": sayim_kupurler,
                "pos": [self.sayi_al(v) for v in self.pos_vars],
                "iban": [self.sayi_al(v) for v in self.iban_vars],
                "masraflar": [(self.sayi_al(t), a.get()) for t, a in self.masraf_vars],
                "silinen": [(self.sayi_al(t), a.get()) for t, a in self.silinen_vars],
                "gun_ici_alinan": [(self.sayi_al(t), a.get()) for t, a in self.gun_ici_alinan_vars],
                "ayrilan_kupurler": ayrilan_kupurler,
                "ertesi_gun_kupurler": ertesi_gun_kupurler,
            }

            self.cursor.execute('''
                INSERT INTO kasa_kapatma (
                    tarih, saat, baslangic_kasasi, baslangic_kupurler_json,
                    sayim_toplam, pos_toplam, iban_toplam,
                    masraf_toplam, silinen_etki_toplam, gun_ici_alinan_toplam,
                    nakit_toplam, genel_toplam, son_genel_toplam,
                    botanik_nakit, botanik_pos, botanik_iban, botanik_genel_toplam,
                    fark, ertesi_gun_kasasi, ertesi_gun_kupurler_json,
                    ayrilan_para, ayrilan_kupurler_json,
                    detay_json, olusturma_zamani
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tarih, saat, baslangic_toplam, json.dumps(baslangic_kupurler, ensure_ascii=False),
                nakit_toplam, pos_toplam, iban_toplam,
                masraf_toplam, silinen_toplam, alinan_toplam,
                nakit_toplam, genel_toplam, son_genel_toplam,
                botanik_nakit, botanik_pos, botanik_iban, botanik_toplam,
                fark, ertesi_gun_kasasi, json.dumps(ertesi_gun_kupurler, ensure_ascii=False),
                ayrilan_para, json.dumps(ayrilan_kupurler, ensure_ascii=False),
                json.dumps(detay, ensure_ascii=False), olusturma_zamani
            ))
            self.conn.commit()

            messagebox.showinfo(
                "Kaydedildi",
                f"Kasa kapatma kaydedildi!\n\n"
                f"Tarih: {tarih} {saat}\n"
                f"Son Genel Toplam: {son_genel_toplam:,.2f} TL\n"
                f"Botanik Toplam: {botanik_toplam:,.2f} TL\n"
                f"Fark: {fark:,.2f} TL\n\n"
                f"Ertesi Gün Kasası: {ertesi_gun_kasasi:,.2f} TL\n"
                f"Ayrılan Para: {ayrilan_para:,.2f} TL"
            )
            logger.info(f"Kasa kapatma kaydedildi: {tarih} {saat}")

        except Exception as e:
            logger.error(f"Kasa kaydetme hatası: {e}")
            messagebox.showerror("Hata", f"Kaydetme hatasi: {e}")

    def temizle(self):
        """Tüm alanları temizle"""
        if not messagebox.askyesno("Onay", "Tum alanlari temizlemek istiyor musunuz?"):
            return

        # Sayım
        for var in self.sayim_vars.values():
            var.set("0")

        # POS ve IBAN
        for var in self.pos_vars:
            var.set("0")
        for var in self.iban_vars:
            var.set("0")

        # Masraf, silinen, gün içi
        for tutar, aciklama in self.masraf_vars:
            tutar.set("0")
            aciklama.set("")
        for tutar, aciklama in self.silinen_vars:
            tutar.set("0")
            aciklama.set("")
        for tutar, aciklama in self.gun_ici_alinan_vars:
            tutar.set("0")
            aciklama.set("")

        # Botanik
        self.botanik_nakit_var.set("0")
        self.botanik_pos_var.set("0")
        self.botanik_iban_var.set("0")

        # 11. tablodaki slider'ları sıfırla
        if hasattr(self, 'c_slider_vars'):
            for slider_var in self.c_slider_vars.values():
                slider_var.set(0)

        # Ertesi gün ve ayrılan para durumlarını sıfırla
        self.ertesi_gun_belirlendi = False
        self.ayrilan_para_belirlendi = False
        self.ertesi_gun_toplam_data = 0
        self.ertesi_gun_kupurler_data = {}
        self.ayrilan_toplam_data = 0
        self.ayrilan_kupurler_data = {}

        # Önceki kayıttan başlangıç kasasını yükle
        onceki_veri = self.onceki_gun_kasasi_yukle()
        if onceki_veri and onceki_veri.get("toplam", 0) > 0:
            kupurler = onceki_veri.get("kupurler", {})
            for deger_str, adet in kupurler.items():
                try:
                    deger = float(deger_str)
                    if deger == int(deger):
                        deger = int(deger)
                    if deger in self.baslangic_kupur_vars:
                        self.baslangic_kupur_vars[deger].set(str(adet))
                except (ValueError, KeyError):
                    pass
        else:
            # Başlangıç kasasını temizle
            for var in self.baslangic_kupur_vars.values():
                var.set("0")

        self.baslangic_toplam_hesapla()
        self.hesaplari_guncelle()
        self.kasa_tablosu_guncelle()

    def ayarlar_penceresi_ac(self):
        """Ayarlar penceresini aç"""
        ayar_pencere = tk.Toplevel(self.root)
        ayar_pencere.title("Kasa Ayarlari")
        ayar_pencere.geometry("550x750")
        ayar_pencere.transient(self.root)
        ayar_pencere.grab_set()
        ayar_pencere.configure(bg='#FAFAFA')

        # Notebook (Tab) yapısı
        notebook = ttk.Notebook(ayar_pencere)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab 1: Küpürler
        kupur_tab = tk.Frame(notebook, bg='#FAFAFA')
        notebook.add(kupur_tab, text="Küpürler")

        tk.Label(
            kupur_tab,
            text="Aktif Küpürler",
            font=("Arial", 12, "bold"),
            bg='#FAFAFA'
        ).pack(pady=10)

        tk.Label(
            kupur_tab,
            text="Başlangıç kasası ve gün sonu sayımında\ngösterilecek küpürleri seçin:",
            font=("Arial", 10),
            bg='#FAFAFA'
        ).pack(pady=5)

        # Checkbox frame with scroll
        canvas_frame = tk.Frame(kupur_tab, bg='#FAFAFA')
        canvas_frame.pack(fill="both", expand=True, padx=20, pady=10)

        canvas = tk.Canvas(canvas_frame, bg='#FAFAFA', highlightthickness=0, height=300)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        check_frame = tk.Frame(canvas, bg='#FAFAFA')

        check_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=check_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        checkbox_vars = {}
        for kupur in self.KUPURLER:
            deger = kupur["deger"]
            key = self.kupur_key(deger)
            aktif = self.ayarlar.get("aktif_kupurler", {}).get(key, True)
            var = tk.BooleanVar(value=aktif)
            checkbox_vars[key] = var

            cb = tk.Checkbutton(
                check_frame,
                text=kupur["aciklama"],
                variable=var,
                font=("Arial", 11),
                bg='#FAFAFA',
                activebackground='#FAFAFA'
            )
            cb.pack(anchor='w', pady=2)

        # Tab 2: Genel Ayarlar
        genel_tab = tk.Frame(notebook, bg='#FAFAFA')
        notebook.add(genel_tab, text="Genel")

        # Yönerge (Wizard) ayarı
        yonerge_frame = tk.LabelFrame(genel_tab, text="Kasa İşleme Yönergesi", font=("Arial", 10, "bold"),
                                      bg='#FAFAFA', padx=10, pady=10)
        yonerge_frame.pack(fill="x", padx=10, pady=10)

        yonerge_var = tk.BooleanVar(value=self.ayarlar.get("yonerge_aktif", False))
        tk.Checkbutton(
            yonerge_frame,
            text="Kasa işleme yönergesini kullan (Wizard modu)",
            variable=yonerge_var,
            font=("Arial", 10),
            bg='#FAFAFA'
        ).pack(anchor='w')

        tk.Label(
            yonerge_frame,
            text="Aktif olursa adım adım rehberli veri girişi yapılır",
            font=("Arial", 9),
            bg='#FAFAFA',
            fg='#666'
        ).pack(anchor='w')

        # Kabul edilebilir fark ayarı
        fark_frame = tk.LabelFrame(genel_tab, text="Fark Toleransı", font=("Arial", 10, "bold"),
                                   bg='#FAFAFA', padx=10, pady=10)
        fark_frame.pack(fill="x", padx=10, pady=10)

        fark_row = tk.Frame(fark_frame, bg='#FAFAFA')
        fark_row.pack(fill="x")

        tk.Label(fark_row, text="Kabul edilebilir fark:", font=("Arial", 10),
                bg='#FAFAFA').pack(side="left")

        fark_var = tk.StringVar(value=str(self.ayarlar.get("kabul_edilebilir_fark", 10)))
        tk.Entry(fark_row, textvariable=fark_var, font=("Arial", 10), width=10).pack(side="left", padx=10)
        tk.Label(fark_row, text="TL", font=("Arial", 10), bg='#FAFAFA').pack(side="left")

        tk.Label(
            fark_frame,
            text="Bu tutardan fazla fark olduğunda kontrol listesi açılır",
            font=("Arial", 9),
            bg='#FAFAFA',
            fg='#666'
        ).pack(anchor='w', pady=5)

        # Tab 3: WhatsApp ve Yazıcı
        iletisim_tab = tk.Frame(notebook, bg='#FAFAFA')
        notebook.add(iletisim_tab, text="İletişim")

        # WhatsApp ayarı
        whatsapp_frame = tk.LabelFrame(iletisim_tab, text="WhatsApp Ayarları", font=("Arial", 10, "bold"),
                                       bg='#FAFAFA', padx=10, pady=10)
        whatsapp_frame.pack(fill="x", padx=10, pady=10)

        whatsapp_row = tk.Frame(whatsapp_frame, bg='#FAFAFA')
        whatsapp_row.pack(fill="x")

        tk.Label(whatsapp_row, text="WhatsApp No:", font=("Arial", 10),
                bg='#FAFAFA').pack(side="left")

        whatsapp_var = tk.StringVar(value=self.ayarlar.get("whatsapp_numara", ""))
        tk.Entry(whatsapp_row, textvariable=whatsapp_var, font=("Arial", 10), width=20).pack(side="left", padx=10)

        tk.Label(
            whatsapp_frame,
            text="Örnek: 905551234567 (Ülke kodu ile)",
            font=("Arial", 9),
            bg='#FAFAFA',
            fg='#666'
        ).pack(anchor='w', pady=5)

        # Yazıcı ayarı
        yazici_frame = tk.LabelFrame(iletisim_tab, text="Yazıcı Ayarları", font=("Arial", 10, "bold"),
                                     bg='#FAFAFA', padx=10, pady=10)
        yazici_frame.pack(fill="x", padx=10, pady=10)

        yazici_row = tk.Frame(yazici_frame, bg='#FAFAFA')
        yazici_row.pack(fill="x")

        tk.Label(yazici_row, text="Yazıcı:", font=("Arial", 10),
                bg='#FAFAFA').pack(side="left")

        yazici_var = tk.StringVar(value=self.ayarlar.get("yazici_adi", ""))
        yazici_entry = tk.Entry(yazici_row, textvariable=yazici_var, font=("Arial", 10), width=25)
        yazici_entry.pack(side="left", padx=10)

        def yazici_sec():
            if YENI_MODULLER_YUKLENDI:
                def on_select(secilen):
                    yazici_var.set(secilen)
                pencere = YaziciSecimPenceresi(ayar_pencere, self.ayarlar, on_select)
                pencere.goster()

        tk.Button(yazici_row, text="Seç...", font=("Arial", 9),
                 command=yazici_sec).pack(side="left")

        # Tab 4: Ağ Ayarları
        ag_tab = tk.Frame(notebook, bg='#FAFAFA')
        notebook.add(ag_tab, text="Ağ/Sunucu")

        # Ana makine modu
        mod_frame = tk.LabelFrame(ag_tab, text="Çalışma Modu", font=("Arial", 10, "bold"),
                                  bg='#FAFAFA', padx=10, pady=10)
        mod_frame.pack(fill="x", padx=10, pady=10)

        ana_makine_var = tk.BooleanVar(value=self.ayarlar.get("ana_makine_modu", True))
        tk.Radiobutton(
            mod_frame,
            text="Ana Makine (Sunucu) - Veritabanı burada tutulur",
            variable=ana_makine_var,
            value=True,
            font=("Arial", 10),
            bg='#FAFAFA'
        ).pack(anchor='w')

        tk.Radiobutton(
            mod_frame,
            text="Terminal - Ana makineye bağlanır",
            variable=ana_makine_var,
            value=False,
            font=("Arial", 10),
            bg='#FAFAFA'
        ).pack(anchor='w')

        # Sunucu ayarları
        sunucu_frame = tk.LabelFrame(ag_tab, text="Sunucu Bağlantı Ayarları", font=("Arial", 10, "bold"),
                                     bg='#FAFAFA', padx=10, pady=10)
        sunucu_frame.pack(fill="x", padx=10, pady=10)

        ip_row = tk.Frame(sunucu_frame, bg='#FAFAFA')
        ip_row.pack(fill="x", pady=2)
        tk.Label(ip_row, text="Ana Makine IP:", font=("Arial", 10),
                bg='#FAFAFA', width=15, anchor='w').pack(side="left")
        ip_var = tk.StringVar(value=self.ayarlar.get("ana_makine_ip", "192.168.1.100"))
        tk.Entry(ip_row, textvariable=ip_var, font=("Arial", 10), width=20).pack(side="left", padx=10)

        port_row = tk.Frame(sunucu_frame, bg='#FAFAFA')
        port_row.pack(fill="x", pady=2)
        tk.Label(port_row, text="Port:", font=("Arial", 10),
                bg='#FAFAFA', width=15, anchor='w').pack(side="left")
        port_var = tk.StringVar(value=str(self.ayarlar.get("ana_makine_port", 5000)))
        tk.Entry(port_row, textvariable=port_var, font=("Arial", 10), width=10).pack(side="left", padx=10)

        # Buton frame
        btn_frame = tk.Frame(ayar_pencere, bg='#FAFAFA')
        btn_frame.pack(fill="x", pady=10, padx=20)

        def kaydet():
            # Tüm ayarları güncelle
            self.ayarlar["aktif_kupurler"] = {k: v.get() for k, v in checkbox_vars.items()}
            self.ayarlar["yonerge_aktif"] = yonerge_var.get()
            try:
                self.ayarlar["kabul_edilebilir_fark"] = float(fark_var.get())
            except ValueError:
                self.ayarlar["kabul_edilebilir_fark"] = 10
            self.ayarlar["whatsapp_numara"] = whatsapp_var.get()
            self.ayarlar["yazici_adi"] = yazici_var.get()
            self.ayarlar["ana_makine_modu"] = ana_makine_var.get()
            self.ayarlar["ana_makine_ip"] = ip_var.get()
            try:
                self.ayarlar["ana_makine_port"] = int(port_var.get())
            except ValueError:
                self.ayarlar["ana_makine_port"] = 5000
            self.ayarlari_kaydet()
            messagebox.showinfo("Kaydedildi", "Ayarlar kaydedildi!")

        def kaydet_ve_uygula():
            kaydet()
            ayar_pencere.destroy()
            # Arayüzü yeniden oluştur
            self.arayuzu_yenile()

        tk.Button(
            btn_frame,
            text="Kaydet",
            font=("Arial", 11, "bold"),
            bg='#2196F3',
            fg='white',
            width=12,
            command=kaydet
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="Kaydet ve Uygula",
            font=("Arial", 11, "bold"),
            bg='#4CAF50',
            fg='white',
            width=15,
            command=kaydet_ve_uygula
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame,
            text="Kapat",
            font=("Arial", 11),
            bg='#9E9E9E',
            fg='white',
            width=10,
            command=ayar_pencere.destroy
        ).pack(side="right", padx=5)

    def arayuzu_yenile(self):
        """Arayüzü yeniden oluştur"""
        # Mevcut değerleri sakla
        sakla_pos = [v.get() for v in self.pos_vars]
        sakla_iban = [v.get() for v in self.iban_vars]
        sakla_botanik = (self.botanik_nakit_var.get(), self.botanik_pos_var.get(), self.botanik_iban_var.get())

        # Ana frame'i temizle
        for widget in self.root.winfo_children():
            widget.destroy()

        # Değişkenleri sıfırla
        self.baslangic_kupur_vars = {}
        self.sayim_vars = {}
        self.sayim_toplam_labels = {}
        self.pos_vars = []
        self.iban_vars = []
        self.masraf_vars = []
        self.silinen_vars = []
        self.gun_ici_alinan_vars = []
        self.botanik_nakit_var = tk.StringVar(value="0")
        self.botanik_pos_var = tk.StringVar(value="0")
        self.botanik_iban_var = tk.StringVar(value="0")
        self.baslangic_detay_acik = False

        # Ayarları yeniden yükle
        self.ayarlar = self.ayarlari_yukle()

        # Arayüzü yeniden oluştur
        self.arayuz_olustur()

        # Saklanan değerleri geri yükle
        for i, var in enumerate(self.pos_vars):
            if i < len(sakla_pos):
                var.set(sakla_pos[i])
        for i, var in enumerate(self.iban_vars):
            if i < len(sakla_iban):
                var.set(sakla_iban[i])
        self.botanik_nakit_var.set(sakla_botanik[0])
        self.botanik_pos_var.set(sakla_botanik[1])
        self.botanik_iban_var.set(sakla_botanik[2])

        self.hesaplari_guncelle()

    def gecmis_goster(self):
        """Geçmiş kayıtları göster"""
        if YENI_MODULLER_YUKLENDI:
            # Yeni gelişmiş geçmiş penceresi
            gecmis = KasaGecmisiPenceresi(self.root, self.cursor, self.conn)
            gecmis.goster()
        else:
            # Eski basit treeview
            gecmis_pencere = tk.Toplevel(self.root)
            gecmis_pencere.title("Gecmis Kasa Kapatma Kayitlari")
            gecmis_pencere.geometry("1200x600")
            gecmis_pencere.transient(self.root)

            # Treeview
            columns = ('id', 'tarih', 'saat', 'nakit', 'pos', 'iban', 'genel', 'son_genel', 'botanik', 'fark')
            tree = ttk.Treeview(gecmis_pencere, columns=columns, show='headings', height=20)

            tree.heading('id', text='ID')
            tree.heading('tarih', text='Tarih')
            tree.heading('saat', text='Saat')
            tree.heading('nakit', text='Nakit')
            tree.heading('pos', text='POS')
            tree.heading('iban', text='IBAN')
            tree.heading('genel', text='Genel Top.')
            tree.heading('son_genel', text='Son Gen.Top.')
            tree.heading('botanik', text='Botanik Top.')
            tree.heading('fark', text='Fark')

            tree.column('id', width=40)
            tree.column('tarih', width=100)
            tree.column('saat', width=80)
            tree.column('nakit', width=100)
            tree.column('pos', width=100)
            tree.column('iban', width=100)
            tree.column('genel', width=110)
            tree.column('son_genel', width=110)
            tree.column('botanik', width=110)
            tree.column('fark', width=100)

            scrollbar = ttk.Scrollbar(gecmis_pencere, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)
            scrollbar.pack(side="right", fill="y", pady=10)

            # Verileri yükle
            try:
                self.cursor.execute('''
                    SELECT id, tarih, saat, nakit_toplam, pos_toplam, iban_toplam,
                           genel_toplam, son_genel_toplam, botanik_genel_toplam, fark
                    FROM kasa_kapatma
                    ORDER BY id DESC
                    LIMIT 100
                ''')
                for row in self.cursor.fetchall():
                    son_genel = row[7] if row[7] else row[6]  # Eski kayıtlar için
                    tree.insert('', 'end', values=(
                        row[0],
                        row[1],
                        row[2],
                        f"{row[3]:,.2f}",
                        f"{row[4]:,.2f}",
                        f"{row[5]:,.2f}",
                        f"{row[6]:,.2f}",
                        f"{son_genel:,.2f}",
                        f"{row[8]:,.2f}",
                        f"{row[9]:,.2f}"
                    ))
            except Exception as e:
                logger.error(f"Gecmis yukleme hatasi: {e}")

    def ana_sayfaya_don(self):
        """Ana sayfaya dön"""
        if self.ana_menu_callback:
            self.root.destroy()
            self.ana_menu_callback()
        else:
            self.root.destroy()

    def kapat(self):
        """Pencereyi kapat"""
        if self.ana_menu_callback:
            self.root.destroy()
            self.ana_menu_callback()
        else:
            self.root.destroy()

    def calistir(self):
        """Pencereyi çalıştır"""
        self.root.mainloop()

    def wizard_baslat(self):
        """Wizard'ı başlat"""
        if not YENI_MODULLER_YUKLENDI:
            messagebox.showwarning("Uyari", "Wizard modulu yuklenemedi!")
            return

        if self.wizard_aktif:
            messagebox.showinfo("Bilgi", "Wizard zaten calisıyor!")
            return

        self.wizard_aktif = True
        self.wizard = KasaWizard(self.root, self, on_complete=self.wizard_tamamlandi)
        self.wizard.baslat()

    def wizard_tamamlandi(self):
        """Wizard tamamlandığında çağrılır"""
        self.wizard_aktif = False
        self.hesaplari_guncelle()

    def whatsapp_rapor_gonder(self):
        """WhatsApp ile kasa raporu gönder"""
        if not YENI_MODULLER_YUKLENDI:
            messagebox.showwarning("Uyari", "WhatsApp modulu yuklenemedi!")
            return

        # Kasa verilerini topla
        kasa_verileri = self.kasa_verilerini_topla()

        # WhatsApp penceresi aç
        pencere = KasaWhatsAppPenceresi(self.root, self.ayarlar, kasa_verileri)
        pencere.goster()

    def kasa_verilerini_topla(self):
        """Mevcut kasa verilerini dict olarak topla"""
        # Başlangıç kasası
        baslangic = sum(int(v.get() or 0) * d for d, v in self.baslangic_kupur_vars.items())

        # Sayım
        nakit = sum(int(v.get() or 0) * d for d, v in self.sayim_vars.items())

        # POS ve IBAN
        pos = sum(self.sayi_al(v) for v in self.pos_vars)
        iban = sum(self.sayi_al(v) for v in self.iban_vars)

        # Masraf, Silinen, Alınan
        masraf = sum(self.sayi_al(t) for t, _ in self.masraf_vars)
        silinen = sum(self.sayi_al(t) for t, _ in self.silinen_vars)
        alinan = sum(self.sayi_al(t) for t, _ in self.gun_ici_alinan_vars)

        # Toplamlar
        genel = nakit + pos + iban
        son_genel = genel + masraf + silinen + alinan

        # Botanik
        botanik_nakit = self.sayi_al(self.botanik_nakit_var)
        botanik_pos = self.sayi_al(self.botanik_pos_var)
        botanik_iban = self.sayi_al(self.botanik_iban_var)
        botanik_toplam = botanik_nakit + botanik_pos + botanik_iban

        # Fark
        fark = son_genel - botanik_toplam

        # 11. tablodaki KALAN ve AYRILAN değerlerini hesapla
        kalan_toplam = 0
        ayrilan_toplam = 0
        if hasattr(self, 'c_slider_vars'):
            for deger, slider_var in self.c_slider_vars.items():
                try:
                    sayim_adet = int(self.sayim_vars.get(deger, tk.StringVar(value="0")).get() or 0)
                    ayrilan_adet = slider_var.get()
                    kalan_adet = sayim_adet - ayrilan_adet
                    kalan_toplam += kalan_adet * deger
                    ayrilan_toplam += ayrilan_adet * deger
                except (ValueError, KeyError):
                    pass

        # Ertesi gün kasası - 11. tablodaki kalan toplam
        ertesi_gun = kalan_toplam if kalan_toplam > 0 else nakit

        # Ayrılan para - 11. tablodaki ayrılan toplam
        ayrilan = ayrilan_toplam

        return {
            'baslangic_kasasi': baslangic,
            'nakit_toplam': nakit,
            'pos_toplam': pos,
            'iban_toplam': iban,
            'masraf_toplam': masraf,
            'silinen_toplam': silinen,
            'alinan_toplam': alinan,
            'genel_toplam': genel,
            'son_genel_toplam': son_genel,
            'botanik_nakit': botanik_nakit,
            'botanik_pos': botanik_pos,
            'botanik_iban': botanik_iban,
            'botanik_toplam': botanik_toplam,
            'fark': fark,
            'ertesi_gun_kasasi': ertesi_gun,
            'ayrilan_para': ayrilan
        }

    def fark_kontrol_penceresi_ac(self):
        """Fark kontrol listesi penceresini aç"""
        if not YENI_MODULLER_YUKLENDI:
            return

        # Farkı hesapla
        kasa_verileri = self.kasa_verilerini_topla()
        fark = kasa_verileri['fark']

        if abs(fark) < 0.01:
            messagebox.showinfo("Bilgi", "Kasa tuttu! Fark yok.")
            return

        kontrol = KasaKontrolListesi(self.root, fark)
        kontrol.goster()

    def kurulum_rehberi_ac(self):
        """Kurulum rehberi dosyalarını seç ve aç"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))

            # Seçim penceresi oluştur
            secim_pencere = tk.Toplevel(self.root)
            secim_pencere.title("Rehber Seç")
            secim_pencere.geometry("400x200")
            secim_pencere.resizable(False, False)
            secim_pencere.configure(bg='#F5F5F5')
            secim_pencere.transient(self.root)
            secim_pencere.grab_set()

            # Pencereyi ortala
            secim_pencere.update_idletasks()
            x = (secim_pencere.winfo_screenwidth() - 400) // 2
            y = (secim_pencere.winfo_screenheight() - 200) // 2
            secim_pencere.geometry(f"400x200+{x}+{y}")

            tk.Label(
                secim_pencere,
                text="Hangi rehberi açmak istiyorsunuz?",
                font=("Arial", 12, "bold"),
                bg='#F5F5F5'
            ).pack(pady=20)

            btn_frame = tk.Frame(secim_pencere, bg='#F5F5F5')
            btn_frame.pack(pady=10)

            def ac_dosya(dosya_adi):
                dosya_yolu = Path(script_dir) / dosya_adi
                if dosya_yolu.exists():
                    os.startfile(str(dosya_yolu))
                    secim_pencere.destroy()
                else:
                    messagebox.showwarning(
                        "Dosya Bulunamadi",
                        f"{dosya_adi} dosyasi bulunamadi.\n\nBeklenen konum: {dosya_yolu}"
                    )

            # Geliştirme Rehberi butonu
            tk.Button(
                btn_frame,
                text="📋 Geliştirme Adımları\n(Şimdi için)",
                font=("Arial", 10),
                bg='#4CAF50',
                fg='white',
                width=20,
                height=3,
                command=lambda: ac_dosya("GELISTIRME_VE_KURULUM_ADIMLARI.txt")
            ).pack(side="left", padx=10)

            # Kurulum Rehberi butonu
            tk.Button(
                btn_frame,
                text="📖 Kurulum Rehberi\n(Detaylı)",
                font=("Arial", 10),
                bg='#2196F3',
                fg='white',
                width=20,
                height=3,
                command=lambda: ac_dosya("KURULUM_REHBERI.txt")
            ).pack(side="left", padx=10)

        except Exception as e:
            logger.error(f"Rehber açma hatası: {e}")
            messagebox.showerror("Hata", f"Rehber acilamadi: {e}")


def kasa_takip_ac(ana_menu_callback=None):
    """Kasa Takip modülünü aç"""
    modul = KasaKapatmaModul(ana_menu_callback=ana_menu_callback)
    modul.calistir()


if __name__ == "__main__":
    modul = KasaKapatmaModul()
    modul.calistir()
