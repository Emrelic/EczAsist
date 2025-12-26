"""
Botanik Bot - Kasa Kapatma Modülü
Günlük kasa sayımı, POS, IBAN ve mutabakat işlemleri
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
    from kasa_kontrol_listesi import KasaKontrolListesi
    from kasa_whatsapp import KasaWhatsAppRapor, KasaWhatsAppPenceresi
    from kasa_yazici import KasaYazici, YaziciSecimPenceresi
    from kasa_gecmis import KasaGecmisiPenceresi
    from kasa_raporlama import KasaRaporlamaPenceresi
    from rapor_ayarlari import RaporAyarlariPenceresi
    from kasa_email import KasaEmailPenceresi, EmailAyarPenceresi
    from kasa_yardim import KasaYardimPenceresi
    YENI_MODULLER_YUKLENDI = True
except ImportError as e:
    logger.warning(f"Yeni modüller yüklenemedi: {e}")
    YENI_MODULLER_YUKLENDI = False

# Botanik veri çekme modülü
try:
    from botanik_veri_cek import botanik_verilerini_cek, botanik_penceresi_acik_mi, baslangic_kasasi_kontrol, botanik_baslangic_kupurlerini_cek
    BOTANIK_VERI_MODULU_YUKLENDI = True
except ImportError as e:
    logger.warning(f"Botanik veri çekme modülü yüklenemedi: {e}")
    BOTANIK_VERI_MODULU_YUKLENDI = False

# Kasa konfigurasyon ve API modulu
try:
    from kasa_config import config_yukle, makine_tipi_al, terminal_mi, ana_makine_ip_al, api_port_al, argumanlardan_config_al
    from kasa_api_client import KasaAPIClient
    KASA_API_MODULU_YUKLENDI = True
except ImportError as e:
    logger.warning(f"Kasa API modülü yüklenemedi: {e}")
    KASA_API_MODULU_YUKLENDI = False


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

        # Veritabanı bağlantısı (başlangıçta None)
        self.conn = None
        self.cursor = None

        # API Client (Terminal ve Ana makine icin)
        self.api_client = None
        self.terminal_modu = False
        self.ana_makine_api_modu = False  # Ana makine de API kullanacak
        self.api_server_thread = None

        if KASA_API_MODULU_YUKLENDI:
            config = argumanlardan_config_al()
            if config.get("makine_tipi") == "terminal":
                self.terminal_modu = True
                ip = config.get("ana_makine_ip", "127.0.0.1")
                port = config.get("api_port", 5000)
                self.api_client = KasaAPIClient(host=ip, port=port)
                logger.info(f"Terminal modu aktif - Ana Makine: {ip}:{port}")
            elif config.get("makine_tipi") == "ana_makine":
                # Ana makine modunda API server'ı başlat
                try:
                    from kasa_api_server import start_server_thread
                    port = config.get("api_port", 5000)
                    self.api_server_thread = start_server_thread(host='0.0.0.0', port=port)
                    logger.info(f"Ana makine: API Server başlatıldı - Port: {port}")
                    # Ana makine de API client kullanacak (tek merkezi DB için)
                    import time
                    time.sleep(0.5)  # Server'ın başlamasını bekle
                    self.api_client = KasaAPIClient(host='127.0.0.1', port=port)
                    self.ana_makine_api_modu = True  # Ana makine de API kullanıyor
                    logger.info(f"Ana makine: API Client oluşturuldu - localhost:{port}")
                except Exception as e:
                    logger.error(f"API Server başlatılamadı: {e}")
                    self.ana_makine_api_modu = False

        if root is None:
            self.root = tk.Tk()
        else:
            self.root = root

        # DPI Awareness - Windows ölçekleme sorununu çöz
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)  # System DPI aware
        except:
            pass  # Windows 7 veya hata durumunda atla

        # Pencere basligi (mod bazli)
        if self.terminal_modu:
            self.root.title("Kasa Kapatma - Terminal Modu")
        elif self.ana_makine_api_modu:
            self.root.title("Kasa Kapatma - Ana Makine (API)")
        else:
            self.root.title("Kasa Kapatma - Günlük Mutabakat")

        # Ekran boyutunu al ve pencereyi ayarla
        ekran_genislik = self.root.winfo_screenwidth()
        ekran_yukseklik = self.root.winfo_screenheight()

        # Pencere boyutunu ekrana göre ayarla (ekranın %95'i)
        pencere_genislik = int(ekran_genislik * 0.95)
        pencere_yukseklik = int(ekran_yukseklik * 0.90)

        # Pencereyi ortala
        x = (ekran_genislik - pencere_genislik) // 2
        y = (ekran_yukseklik - pencere_yukseklik) // 2 - 30

        self.root.geometry(f"{pencere_genislik}x{pencere_yukseklik}+{x}+{y}")
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
        self.baslangic_entry_list = []  # Tab navigasyonu için başlangıç kasası entry'leri
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
        self.kasa_tablo_acik = False

        # Yeni veri değişkenleri
        self.ertesi_gun_toplam_data = 0
        self.ertesi_gun_kupurler_data = {}
        self.ayrilan_toplam_data = 0
        self.ayrilan_kupurler_data = {}

        # Tab navigasyonu için entry listesi
        # Sıra: Sayım -> Masraf -> Silinen -> Alınan -> Botanik -> Sayım (tur)
        self.tab_order_entries = []

        # Manuel başlangıç kasası değişkenleri
        self.manuel_baslangic_aktif = False
        self.manuel_baslangic_tutar = 0
        self.manuel_baslangic_aciklama = ""

        # Sayım sırası alışveriş değişkenleri
        self.alisveris_tahsilat_var = tk.StringVar(value="0")
        self.alisveris_alinan_kupurler = {}  # {deger: adet}
        self.alisveris_para_ustu = 0
        self.alisveris_para_ustu_kupurler = {}  # {deger: adet}

        # Pencere kapatma
        self.root.protocol("WM_DELETE_WINDOW", self.kapat)

        # Önceki gün verisini yükle (son kapatmadaki ertesi_gun_kasasi değerleri)
        self.onceki_gun_verisi = self.onceki_gun_kasasi_yukle()

        self.arayuz_olustur()
        self.hesaplari_guncelle()

    def varsayilan_gorunum_ayarlari(self):
        """Varsayılan görünüm ayarlarını döndür"""
        return {
            "punto_boyutu": 11,           # Genel yazı boyutu (9-14)
            "baslik_yuksekligi": 100,     # Üst bar yüksekliği (70-140)
            "buton_yuksekligi": 3,        # Alt butonların yüksekliği (2-5)
            "tablo_satir_yuksekligi": 28, # Tablo satır yüksekliği (20-40)
            "hucre_padding": 3,           # Hücre iç boşluğu (1-8)
            "bolum_padding": 3,           # Bölüm iç boşluğu (2-8)
        }

    def ayarlari_yukle(self):
        """Kasa ayarlarını yükle"""
        # Varsayılan olarak pasif olan küpürler (kullanılmayanlar)
        pasif_kupurler = {5000, 2000, 1000, 500, 0.25, 0.10, 0.05}

        def varsayilan_aktiflik(deger):
            """Küpürün varsayılan aktiflik durumunu döndür"""
            return deger not in pasif_kupurler

        # Varsayılan görünüm ayarları
        varsayilan_gorunum = self.varsayilan_gorunum_ayarlari()

        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            ayar_dosyasi = Path(script_dir) / "kasa_ayarlari.json"

            if ayar_dosyasi.exists():
                with open(ayar_dosyasi, 'r', encoding='utf-8') as f:
                    ayarlar = json.load(f)
                # Eksik görünüm ayarlarını varsayılanlarla tamamla
                eksik_var = False
                for key, value in varsayilan_gorunum.items():
                    if key not in ayarlar:
                        ayarlar[key] = value
                        eksik_var = True
                # Eksik ayarlar varsa dosyaya kaydet
                if eksik_var:
                    with open(ayar_dosyasi, 'w', encoding='utf-8') as f:
                        json.dump(ayarlar, f, ensure_ascii=False, indent=2)
                return ayarlar
            else:
                # Varsayılan ayarlar - kullanılmayan küpürler pasif
                varsayilan = {
                    "aktif_kupurler": {
                        self.kupur_key(k["deger"]): varsayilan_aktiflik(k["deger"])
                        for k in self.KUPURLER
                    },
                    **varsayilan_gorunum
                }
                self.ayarlari_kaydet(varsayilan)
                return varsayilan
        except Exception as e:
            logger.error(f"Ayar yükleme hatası: {e}")
            return {
                "aktif_kupurler": {
                    self.kupur_key(k["deger"]): varsayilan_aktiflik(k["deger"])
                    for k in self.KUPURLER
                },
                **varsayilan_gorunum
            }

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

    # ===== GÖRÜNÜM AYARLARI YARDIMCI FONKSİYONLARI =====
    def get_punto(self, offset=0):
        """Punto boyutunu al (offset ile büyütme/küçültme)"""
        return self.ayarlar.get("punto_boyutu", 11) + offset

    def get_baslik_yuksekligi(self):
        """Başlık yüksekliğini al"""
        return self.ayarlar.get("baslik_yuksekligi", 100)

    def get_buton_yuksekligi(self):
        """Buton yüksekliğini al"""
        return self.ayarlar.get("buton_yuksekligi", 3)

    def get_tablo_satir_yuksekligi(self):
        """Tablo satır yüksekliğini al"""
        return self.ayarlar.get("tablo_satir_yuksekligi", 28)

    def get_hucre_padding(self):
        """Hücre padding değerini al"""
        return self.ayarlar.get("hucre_padding", 3)

    def get_bolum_padding(self):
        """Bölüm padding değerini al"""
        return self.ayarlar.get("bolum_padding", 3)

    def sebepleri_yukle(self):
        """Artı/Eksi sebeplerini JSON dosyasından yükle"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sebep_dosyasi = Path(script_dir) / "arti_eksi_sebepler.json"

            if sebep_dosyasi.exists():
                with open(sebep_dosyasi, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Sebep yükleme hatası: {e}")

        # Varsayılan sebepler
        return self.varsayilan_sebepler()

    def varsayilan_sebepler(self):
        """Varsayılan artı/eksi sebepleri"""
        return {
            "eksik": [
                ("Başlangıç kasası eksik", "Bir önceki gün başlangıç kasası eksik olabilir mi? Kontrol edilmeli."),
                ("Akşam kasası yanlış sayıldı", "Akşam kasası yanlış sayılmıştır."),
                ("Dünkü satış/POS işlenmedi", "Dün akşamdan yapılan satış, POS raporu vesaire işlenmemiştir."),
                ("Satış parası alınmadı", "Yapılan satışın parası alınmamıştır."),
                ("Veresiye işlenmedi", "Veresiye satış veresiye işlenmemiştir."),
                ("2. POS raporu unutuldu", "İkinci POS cihazı kullanılmış fakat raporu alınması unutulmuş."),
                ("Para alındı satış bugün", "Bir önceki gün satışın parası alınmış fakat satış bugün yapılmıştır."),
                ("Mükerrer satış kaydı", "Mükerrer satış kaydı işlenmiştir."),
                ("İndirim işlenmedi", "İndirim/iskonto sisteme işlenmemiştir."),
                ("Masraf işlenmedi", "Masraflar işlenmemiştir."),
                ("Silinmesi gereken reçete", "Silinmesi gereken fakat sistemde unutulmuş reçete varlığı."),
                ("Alınan para işlenmedi", "Gün içi eczacının aldığı para işlenmemiş veya yanlış işlenmiştir."),
                ("Kasadan para alındı", "Gün içi çeşitli sebeplerle kasadan para alınması."),
                ("Tedarikçi ödemesi", "Kasadan tedarikçi firmaya ödeme yapılmış fakat masraf işlenmemiştir."),
                ("Bozuk para sorunu", "Bozuk para kasadan başka yere konmuştur."),
                ("Emanet parekende satıldı", "Emanet verilmesi gereken ürün parekende satılarak işlenmiştir."),
                ("IBAN işlenmedi", "IBAN'a atılan para vardır ama IBAN olarak işlenmemiştir."),
                ("Komplike satış karışıklığı", "Birden fazla reçete ve tahsilatın düzgün yapılmaması."),
                ("Hasta borcu yok iddiası", "Hastanın borcu olmadığını iddia etmesi ve haklı olması."),
                ("Depo/personel ödemesi", "Cari hareketten nakit olarak işlenmiştir."),
                ("Takas işlenmedi", "Takas parası kasadan verilmiş ama kayıtlara işlenmemiştir."),
                ("Emanet satıldı para yok", "Emanetin satılması fakat para kasaya konmamıştır."),
                ("İskonto karışıklığı", "İskonto, yuvarlama ve ödeme seçenekleri birbirine karıştırılmıştır."),
                ("Geçmiş reçete sistemi bozdu", "Son işlem tarihi bugün olan geçmiş reçetelerin sistemi bozması.")
            ],
            "fazla": [
                ("Başlangıç kasası hatası", "Bir önceki gün başlangıç kasası doğru mu? Kontrol edilmeli."),
                ("Akşam kasası hatası", "Akşam kasası doğru sayılmış mı? Kontrol edilmeli."),
                ("Bekleyen satış var", "Satış ekranlarında bekleyen veya gün içi satışı unutulan ürün var mı?"),
                ("Veresiye tahsilatı", "İşlenmesi unutulan veresiye tahsilatı durumu var mı?"),
                ("Bozuk para eklendi", "Bozuk para eklenmiş ama kasadan bütün para alınması unutulmuş."),
                ("Kapora alındı", "Kapora alınmış kasaya konmuştur."),
                ("Majistral düşülmedi", "Majistral yapılıp sistemden düşülmemesi."),
                ("Strip/bez farkı", "Strip, bez farkı hastadan alınmış fakat işlenmemiş."),
                ("Takas parası", "Başka eczane ile takas yapılıp parası kasaya konmuş."),
                ("Fiş iptali", "Fiş iptali yapılmış olabilir mi?"),
                ("Aktarılmayan reçete", "Aktarılmayan reçete var mı?"),
                ("Para üstü eksik", "Para üstü eksik verilmiş olabilir mi?"),
                ("İade parası", "İade yapılmış parası kasadan verilmemiş."),
                ("Mal fazlası satışı", "Ölü karekod veya mal fazlası ürün satışı."),
                ("Dünkü satış parası bugün", "Bir önceki gün satışı, parası bugün alınmış.")
            ]
        }

    def sebepleri_kaydet(self, sebepler):
        """Artı/Eksi sebeplerini JSON dosyasına kaydet"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sebep_dosyasi = Path(script_dir) / "arti_eksi_sebepler.json"
            with open(sebep_dosyasi, 'w', encoding='utf-8') as f:
                json.dump(sebepler, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Sebep kaydetme hatası: {e}")
            return False

    def entry_fokus_secim(self, event):
        """Entry'ye tiklandiginda icerigi sec"""
        event.widget.select_range(0, tk.END)
        event.widget.icursor(tk.END)

    def tab_sonraki_entry(self, event):
        """Tab tuşuna basıldığında sıradaki entry'ye geç"""
        try:
            current_widget = event.widget

            # Başlangıç kasası entry'lerinde
            if current_widget in self.baslangic_entry_list:
                idx = self.baslangic_entry_list.index(current_widget)
                if idx == len(self.baslangic_entry_list) - 1:
                    # Son entry -> Akşam kasası (sayım) ilk entry'sine git
                    if self.tab_order_entries:
                        next_widget = self.tab_order_entries[0]
                        next_widget.focus_set()
                        next_widget.select_range(0, tk.END)
                        return "break"
                else:
                    # Sonraki başlangıç kasası entry'sine git
                    next_widget = self.baslangic_entry_list[idx + 1]
                    next_widget.focus_set()
                    next_widget.select_range(0, tk.END)
                    return "break"

            # Akşam kasası (sayım) ve diğer entry'lerde
            if current_widget in self.tab_order_entries:
                idx = self.tab_order_entries.index(current_widget)
                next_idx = (idx + 1) % len(self.tab_order_entries)
                next_widget = self.tab_order_entries[next_idx]
                next_widget.focus_set()
                next_widget.select_range(0, tk.END)
                return "break"  # Varsayılan Tab davranışını engelle
        except Exception as e:
            logger.debug(f"Tab navigasyon: {e}")
        return None

    def shift_tab_onceki_entry(self, event):
        """Shift+Tab tuşuna basıldığında önceki entry'ye geç"""
        try:
            current_widget = event.widget

            # Başlangıç kasası entry'lerinde
            if current_widget in self.baslangic_entry_list:
                idx = self.baslangic_entry_list.index(current_widget)
                if idx == 0:
                    # İlk entry -> Akşam kasası (sayım) son entry'sine git
                    if self.tab_order_entries:
                        prev_widget = self.tab_order_entries[-1]
                        prev_widget.focus_set()
                        prev_widget.select_range(0, tk.END)
                        return "break"
                else:
                    # Önceki başlangıç kasası entry'sine git
                    prev_widget = self.baslangic_entry_list[idx - 1]
                    prev_widget.focus_set()
                    prev_widget.select_range(0, tk.END)
                    return "break"

            # Akşam kasası (sayım) ve diğer entry'lerde
            if current_widget in self.tab_order_entries:
                idx = self.tab_order_entries.index(current_widget)
                if idx == 0:
                    # İlk entry -> Başlangıç kasası son entry'sine git
                    if self.baslangic_entry_list:
                        prev_widget = self.baslangic_entry_list[-1]
                        prev_widget.focus_set()
                        prev_widget.select_range(0, tk.END)
                        return "break"
                prev_idx = (idx - 1) % len(self.tab_order_entries)
                prev_widget = self.tab_order_entries[prev_idx]
                prev_widget.focus_set()
                prev_widget.select_range(0, tk.END)
                return "break"  # Varsayılan Shift+Tab davranışını engelle
        except Exception as e:
            logger.debug(f"Shift+Tab navigasyon: {e}")
        return None

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
        # Terminal modunda API bağlantısını kontrol et - YEREL DB KURMA
        if self.terminal_modu and self.api_client:
            success, result = self.api_client.baglanti_test()
            if success:
                logger.info("Terminal: Ana makineye bağlantı başarılı")
                logger.info("Terminal: Yerel veritabanı kullanılmayacak - tüm veriler API üzerinden")
                # Terminal modunda yerel DB bağlantısı kurmuyoruz
                # self.conn ve self.cursor None kalacak
                # Tüm okuma/yazma işlemleri API üzerinden yapılacak
                return
            else:
                logger.error(f"Terminal: Ana makineye bağlanılamadı - {result}")
                messagebox.showerror(
                    "Bağlantı Hatası",
                    f"Ana makineye bağlanılamadı!\n\n{result}\n\n"
                    "Lütfen ana makinenin çalıştığından emin olun.\n\n"
                    "Program yerel modda çalışacak."
                )
                # Bağlantı başarısız - terminal modunu kapat
                self.terminal_modu = False
                self.api_client = None

        # Ana makine API modunda da yerel DB kullanmıyoruz - tüm işlemler API üzerinden
        if self.ana_makine_api_modu and self.api_client:
            success, result = self.api_client.baglanti_test()
            if success:
                logger.info("Ana makine: API bağlantısı başarılı - tüm veriler API üzerinden")
                # Ana makine de API üzerinden çalışacak
                # self.conn ve self.cursor None kalacak
                return
            else:
                logger.error(f"Ana makine: API bağlantısı başarısız - {result}")
                self.ana_makine_api_modu = False
                self.api_client = None

        try:
            # Veritabanını AppData klasörüne kaydet (Program Files yazma izni sorunu için)
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            db_klasor = Path(appdata) / "BotanikKasa"
            db_klasor.mkdir(parents=True, exist_ok=True)
            self.db_yolu = db_klasor / "oturum_raporlari.db"

            # Eski konumda veritabanı varsa taşı
            script_dir = os.path.dirname(os.path.abspath(__file__))
            eski_db = Path(script_dir) / "oturum_raporlari.db"
            if eski_db.exists() and not self.db_yolu.exists():
                import shutil
                shutil.copy2(str(eski_db), str(self.db_yolu))
                logger.info(f"Veritabanı taşındı: {eski_db} -> {self.db_yolu}")
            self.conn = sqlite3.connect(str(self.db_yolu), check_same_thread=False)
            self.cursor = self.conn.cursor()
            logger.info(f"Veritabanı bağlantısı kuruldu: {self.db_yolu}")

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

            # Manuel başlangıç kasası bilgisi
            try:
                self.cursor.execute("ALTER TABLE kasa_kapatma ADD COLUMN manuel_baslangic_tutar REAL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

            try:
                self.cursor.execute("ALTER TABLE kasa_kapatma ADD COLUMN manuel_baslangic_aciklama TEXT")
            except sqlite3.OperationalError:
                pass

            self.conn.commit()
            logger.info("Kasa kapatma DB tabloları oluşturuldu")

        except Exception as e:
            import traceback
            hata_detay = traceback.format_exc()
            logger.error(f"Kasa DB hatası: {e}\n{hata_detay}")
            messagebox.showerror("Veritabanı Hatası", f"Veritabanı bağlantısı kurulamadı!\n\nHata: {e}\n\nYol: {self.db_yolu if hasattr(self, 'db_yolu') else 'bilinmiyor'}")

    def onceki_gun_kasasi_yukle(self):
        """Bir önceki kapatmadan ertesi gün kasasını yükle"""
        # API modu (Terminal veya Ana makine) - API üzerinden al
        if self.api_client:
            try:
                success, result = self.api_client.onceki_gun_kasasi_al()
                if success and result.get('success'):
                    data = result.get('data', {})
                    toplam = data.get('toplam', 0)
                    kupurler = data.get('kupurler', {})
                    logger.info(f"Önceki gün kasası API'den yüklendi: {toplam}")
                    return {"toplam": toplam, "kupurler": kupurler}
                else:
                    logger.warning("Önceki gün kasası API'den alınamadı")
                    return {"toplam": 0, "kupurler": {}}
            except Exception as e:
                logger.error(f"Terminal: Önceki gün kasası API hatası: {e}")
                return {"toplam": 0, "kupurler": {}}

        # Ana makine modunda yerel veritabanından al
        if self.cursor is None:
            return {"toplam": 0, "kupurler": {}}
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
        """Ana arayuzu olustur - Yeni numaralandırma ile"""
        # Ust bar
        self.ust_bar_olustur()

        # ===== SCROLL YAPISINI OLUŞTUR =====
        # Container frame
        container = tk.Frame(self.root, bg=self.bg_color)
        container.pack(fill="both", expand=True)

        # Canvas ve Scrollbar
        canvas = tk.Canvas(container, bg=self.bg_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)

        # Scrollbar sağda, canvas solda
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)

        # ===== ANA DÜZEN: Dikey bölümler =====
        ana_frame = tk.Frame(canvas, bg=self.bg_color)
        canvas_window = canvas.create_window((0, 0), window=ana_frame, anchor="nw")

        # Canvas boyutlandırma
        def configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)

        ana_frame.bind("<Configure>", configure_scroll)
        canvas.bind("<Configure>", configure_canvas_width)

        # Mouse wheel scroll
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        ana_frame.rowconfigure(0, weight=33)   # Üst: 6 eşit kare (1/3)
        ana_frame.rowconfigure(1, weight=60)   # Orta: 6+7 yan yana (kalan alan)
        ana_frame.rowconfigure(2, weight=7)    # En alt: Butonlar (8-13)
        ana_frame.columnconfigure(0, weight=1)

        # ========== ÜST KISIM: 6 EŞİT KARE YAN YANA ==========
        ust_frame = tk.Frame(ana_frame, bg=self.bg_color)
        ust_frame.grid(row=0, column=0, sticky='nsew', pady=(0, 3))

        # 6 eşit sütun (1, 2+2B, 2A, 3, 4, 5)
        for i in range(6):
            ust_frame.columnconfigure(i, weight=1, uniform="ustkolon")
        ust_frame.rowconfigure(0, weight=1)

        # 1) BAŞLANGIÇ KASASI
        self.sol_ust_frame = tk.Frame(ust_frame, bg=self.bg_color, relief='solid', bd=2)
        self.sol_ust_frame.grid(row=0, column=0, sticky='nsew', padx=2)

        # 2) AKŞAM KASA SAYIMI
        self.sag_ust_frame = tk.Frame(ust_frame, bg='#E8F5E9', relief='solid', bd=2)
        self.sag_ust_frame.grid(row=0, column=1, sticky='nsew', padx=2)

        # 2-A) SAYIM SIRASI ALIŞVERİŞ (ayrı sütun - 2'nin sağında)
        self.sag_alt_frame = tk.Frame(ust_frame, bg='#E8F5E9', relief='solid', bd=2)
        self.sag_alt_frame.grid(row=0, column=2, sticky='nsew', padx=2)

        # 3) POS VE IBAN
        self.sol_alt_frame = tk.Frame(ust_frame, bg=self.bg_color, relief='solid', bd=2)
        self.sol_alt_frame.grid(row=0, column=3, sticky='nsew', padx=2)

        # 4) DÜZELTMELER (4a, 4b, 4c)
        self.b_bolumu_frame = tk.Frame(ust_frame, bg='#ECEFF1', relief='solid', bd=2)
        self.b_bolumu_frame.grid(row=0, column=4, sticky='nsew', padx=2)

        # 5) BOTANİK EOS VERİLERİ
        self.botanik_frame = tk.Frame(ust_frame, bg=self.bg_color, relief='solid', bd=2)
        self.botanik_frame.grid(row=0, column=5, sticky='nsew', padx=2)

        # Bölümleri oluştur
        self.baslangic_kasasi_bolumu_olustur()  # 1)
        self.gun_sonu_sayim_bolumu_olustur()    # 2)
        self.alisveris_bolumu_olustur()         # 2-A)
        self.pos_bolumu_olustur()               # 3)
        self.iban_bolumu_olustur()
        self.birlesik_masraf_silinen_alinan_bolumu_olustur()  # 4)
        self.botanik_bolumu_olustur()           # 5)

        # ========== ORTA KISIM: 6 + 7 YAN YANA %50-%50 ==========
        orta_frame = tk.Frame(ana_frame, bg=self.bg_color)
        orta_frame.grid(row=1, column=0, sticky='nsew', pady=2)

        orta_frame.columnconfigure(0, weight=1, uniform="ortakolon")  # 6) Farklar
        orta_frame.columnconfigure(1, weight=1, uniform="ortakolon")  # 7) Ertesi gün
        orta_frame.rowconfigure(0, weight=1)

        # 6) Sayım Botanik Farklar Tablosu
        self.tablo_frame = tk.Frame(orta_frame, bg=self.bg_color, relief='solid', bd=2)
        self.tablo_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 2))

        # 7) Ertesi Gün / Ayrılan Para Tablosu
        self.para_ayirma_frame = tk.Frame(orta_frame, bg=self.bg_color, relief='solid', bd=2)
        self.para_ayirma_frame.grid(row=0, column=1, sticky='nsew', padx=(2, 0))

        # ========== EN ALT: BUTONLAR (8-13) ==========
        self.butonlar_frame = tk.Frame(ana_frame, bg='#ECEFF1')
        self.butonlar_frame.grid(row=2, column=0, sticky='sew', pady=(2, 0))

        # Bölümleri oluştur
        self.karsilastirma_tablosu_olustur()   # 6)
        self.kasa_tablosu_olustur()            # 7)
        self.alt_butonlar_olustur()            # 8-13)

        # Sayfa açıldığında Botanik verilerini çek (500ms gecikme ile UI yüklenmesini bekle)
        self.root.after(500, self.botanik_verilerini_otomatik_cek)

    def bozuk_para_bolumu_olustur(self):
        """2-B) Bozuk Para Ekleme bölümü"""
        frame = tk.LabelFrame(
            self.bozuk_para_frame,
            text="2-B) BOZUK PARA EKLEME",
            font=("Arial", 11, "bold"),
            bg='#E8F5E9',
            fg='#1B5E20',
            padx=3,
            pady=2
        )
        frame.pack(fill="both", expand=True)

        # Bozuk para ekleme alanı - basit tutar girişi
        row = tk.Frame(frame, bg='#E8F5E9')
        row.pack(fill="x", pady=2)

        tk.Label(row, text="Eklenen:", font=("Arial", 10),
                bg='#E8F5E9', fg='#333').pack(side="left", padx=3)

        self.bozuk_para_eklenen_var = tk.StringVar(value="0")
        entry = tk.Entry(row, textvariable=self.bozuk_para_eklenen_var,
                        font=("Arial", 10), width=10, justify='right')
        entry.pack(side="right", padx=3)
        entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
        entry.bind('<FocusIn>', self.entry_fokus_secim)

    def botanik_verilerini_otomatik_cek(self):
        """Botanik EOS'tan verileri otomatik çek ve ilgili alanlara yaz"""
        if not BOTANIK_VERI_MODULU_YUKLENDI:
            logger.info("Botanik veri modülü yüklenmedi, otomatik çekme atlanıyor")
            return

        try:
            # Botanik penceresi açık mı kontrol et
            if not botanik_penceresi_acik_mi():
                logger.info("Botanik 'Kasa Kapatma' penceresi açık değil")
                return

            # Verileri çek
            veriler = botanik_verilerini_cek()

            if not veriler:
                logger.warning("Botanik verileri çekilemedi")
                return

            # Botanik verilerini ilgili alanlara yaz
            botanik_nakit = veriler.get('nakit', 0)
            botanik_pos = veriler.get('pos', 0)
            botanik_iban = veriler.get('iban', 0)
            botanik_baslangic = veriler.get('baslangic', 0)

            # Botanik alanlarına yaz (2 ondalık basamak formatında)
            self.botanik_nakit_var.set(f"{botanik_nakit:.2f}")
            self.botanik_pos_var.set(f"{botanik_pos:.2f}")
            self.botanik_iban_var.set(f"{botanik_iban:.2f}")

            # Toplamları güncelle (alt toplam dahil)
            self.hesaplari_guncelle()

            logger.info(f"Botanik verileri çekildi: Nakit={botanik_nakit}, POS={botanik_pos}, IBAN={botanik_iban}")

            # Başlangıç kasası tutarsızlık kontrolü
            program_baslangic = self.get_float_value(self.baslangic_toplam_var.get())

            if botanik_baslangic > 0 and program_baslangic > 0:
                tutarli, mesaj = baslangic_kasasi_kontrol(botanik_baslangic, program_baslangic)

                if not tutarli:
                    # Uyarı göster
                    messagebox.showwarning("Başlangıç Kasası Uyarısı", mesaj)

        except Exception as e:
            logger.error(f"Botanik veri çekme hatası: {e}")

    def botanik_verilerini_yenile(self):
        """Botanik verilerini manuel olarak yenile (buton için)"""
        if not BOTANIK_VERI_MODULU_YUKLENDI:
            messagebox.showwarning("Modül Yok", "Botanik veri çekme modülü yüklenmedi!")
            return

        if not botanik_penceresi_acik_mi():
            messagebox.showwarning("Pencere Yok", "Botanik 'Kasa Kapatma' penceresi açık değil!")
            return

        self.botanik_verilerini_otomatik_cek()
        messagebox.showinfo("Başarılı", "Botanik verileri güncellendi!")

    def ust_bar_olustur(self):
        """Üst bar - başlık ve butonlar"""
        baslik_yuk = self.get_baslik_yuksekligi()
        punto = self.get_punto()

        top_bar = tk.Frame(self.root, bg=self.header_color, height=baslik_yuk)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)

        # Sol taraf - Ana Sayfa ve Ayarlar
        sol_frame = tk.Frame(top_bar, bg=self.header_color)
        sol_frame.pack(side="left", padx=10)

        # Buton padding hesapla (başlık yüksekliğine göre)
        btn_pady_ic = max(4, (baslik_yuk - 70) // 10)
        btn_pady_dis = max(8, (baslik_yuk - 70) // 5)

        if self.ana_menu_callback:
            ana_sayfa_btn = tk.Button(
                sol_frame,
                text="Ana Sayfa",
                font=("Arial", punto + 1, "bold"),
                bg="#0D47A1",
                fg="white",
                activebackground="#1565C0",
                cursor="hand2",
                bd=0,
                padx=12,
                pady=btn_pady_ic,
                command=self.ana_sayfaya_don
            )
            ana_sayfa_btn.pack(side="left", padx=5, pady=btn_pady_dis)

        ayarlar_btn = tk.Button(
            sol_frame,
            text="Ayarlar",
            font=("Arial", punto + 1, "bold"),
            bg="#0D47A1",
            fg="white",
            activebackground="#1565C0",
            cursor="hand2",
            bd=0,
            padx=12,
            pady=btn_pady_ic,
            command=self.ayarlar_penceresi_ac
        )
        ayarlar_btn.pack(side="left", padx=5, pady=btn_pady_dis)

        # Yardım butonu (Kullanım Kılavuzu + Geliştirme Notları)
        yardim_btn = tk.Button(
            sol_frame,
            text="Yardım",
            font=("Arial", punto + 1, "bold"),
            bg="#FF9800",
            fg="white",
            activebackground="#F57C00",
            cursor="hand2",
            bd=0,
            padx=12,
            pady=btn_pady_ic,
            command=self.yardim_penceresi_ac
        )
        yardim_btn.pack(side="left", padx=5, pady=btn_pady_dis)

        # Orta - Başlık
        title = tk.Label(
            top_bar,
            text="KASA KAPATMA / GÜNLÜK MUTABAKAT",
            font=("Arial", punto + 7, "bold"),
            bg=self.header_color,
            fg='white'
        )
        title.pack(side="left", expand=True)

        # Sağ taraf - Temizle ve Geçmiş Kayıtlar
        sag_frame = tk.Frame(top_bar, bg=self.header_color)
        sag_frame.pack(side="right", padx=10)

        # Özelleşmiş Rapor Gönder butonu (Rapor Ayarları'na göre)
        if YENI_MODULLER_YUKLENDI:
            rapor_gonder_btn = tk.Button(
                sag_frame,
                text="Özelleşmiş Rapor",
                font=("Arial", punto + 1, "bold"),
                bg='#1565C0',
                fg='white',
                activebackground='#0D47A1',
                cursor='hand2',
                bd=2,
                relief='solid',
                highlightthickness=0,
                padx=12,
                pady=btn_pady_ic,
                command=self.ozellesmis_rapor_gonder
            )
            rapor_gonder_btn.pack(side="left", padx=5, pady=btn_pady_dis)

        temizle_btn = tk.Button(
            sag_frame,
            text="Temizle",
            font=("Arial", punto + 1, "bold"),
            bg='#F44336',
            fg='white',
            activebackground='#D32F2F',
            cursor='hand2',
            bd=0,
            padx=12,
            pady=btn_pady_ic,
            command=self.temizle
        )
        temizle_btn.pack(side="left", padx=5, pady=btn_pady_dis)

        # Kayıtlar butonu (Geçmiş + Raporlar birleşik)
        kayitlar_btn = tk.Button(
            sag_frame,
            text="Kayıtlar",
            font=("Arial", punto + 1, "bold"),
            bg='#2196F3',
            fg='white',
            activebackground='#1976D2',
            cursor='hand2',
            bd=0,
            padx=12,
            pady=btn_pady_ic,
            command=self.kayitlar_penceresi_ac
        )
        kayitlar_btn.pack(side="left", padx=5, pady=btn_pady_dis)

        # Tarih/Saat
        self.tarih_label = tk.Label(
            sag_frame,
            text=datetime.now().strftime("%d.%m.%Y %H:%M"),
            font=("Arial", punto + 1),
            bg=self.header_color,
            fg='#B3E5FC'
        )
        self.tarih_label.pack(side="left", padx=10, pady=btn_pady_dis)

    def baslangic_kasasi_bolumu_olustur(self):
        """1) Başlangıç kasası bölümü - SOL ÜST"""
        frame = tk.LabelFrame(
            self.sol_ust_frame,
            text="1) BAŞLANGIÇ KASASI",
            font=("Arial", 11, "bold"),
            bg=self.section_colors['baslangic'],
            fg='#1B5E20',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True)
        self.baslangic_frame = frame  # Referansı sakla

        # Üst buton satırı - 3 eşit büyüklükte buton
        buton_frame = tk.Frame(frame, bg='#A5D6A7')
        buton_frame.pack(fill="x", pady=2)

        # Grid - Elle Gir küçük, diğerleri büyük
        buton_frame.columnconfigure(0, weight=2)  # Elle Gir - küçük
        buton_frame.columnconfigure(1, weight=4)  # Botanikten Çek - büyük
        buton_frame.columnconfigure(2, weight=4)  # Botaniğe Aktar - büyük

        # 1. Elle Gir butonu (küçük)
        self.manuel_baslangic_btn = tk.Button(
            buton_frame,
            text="✏ Elle",
            font=("Arial", 9, "bold"),
            bg='#FFE082',
            fg='#E65100',
            bd=2,
            relief='raised',
            takefocus=False,
            cursor='hand2',
            command=self.manuel_baslangic_penceresi_ac
        )
        self.manuel_baslangic_btn.grid(row=0, column=0, sticky='nsew', padx=2, pady=3)

        # 2. Botanikten Veri Çek butonu (büyük)
        self.botanikten_cek_btn = tk.Button(
            buton_frame,
            text="📥 Botanik'ten Çek",
            font=("Arial", 9, "bold"),
            bg='#2196F3',
            fg='white',
            bd=2,
            relief='raised',
            takefocus=False,
            cursor='hand2',
            command=self.botanikten_baslangic_kasasi_cek
        )
        self.botanikten_cek_btn.grid(row=0, column=1, sticky='nsew', padx=2, pady=3)

        # 3. Botaniğe Veri Aktar butonu (büyük)
        self.botanik_isle_btn = tk.Button(
            buton_frame,
            text="📤 Botanik'e Aktar",
            font=("Arial", 9, "bold"),
            bg='#1565C0',
            fg='white',
            bd=2,
            relief='raised',
            takefocus=False,
            cursor='hand2',
            command=self.ertesi_gun_kasasini_botanige_isle
        )
        self.botanik_isle_btn.grid(row=0, column=2, sticky='nsew', padx=2, pady=3)

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

        # ALT TOPLAM SATIRI (küpürlerden sonra)
        toplam_frame = tk.Frame(frame, bg='#2E7D32')
        toplam_frame.pack(fill="x", pady=(5, 2))

        tk.Label(
            toplam_frame,
            text="TOPLAM:",
            font=("Arial", 12, "bold"),
            bg='#2E7D32',
            fg='white'
        ).pack(side="left", padx=10, pady=5)

        baslangic_toplam = self.onceki_gun_verisi.get("toplam", 0)
        self.baslangic_toplam_var = tk.StringVar(value=f"{baslangic_toplam:,.2f}")

        self.baslangic_toplam_label = tk.Label(
            toplam_frame,
            textvariable=self.baslangic_toplam_var,
            font=("Arial", 14, "bold"),
            bg='#2E7D32',
            fg='white',
            width=12,
            anchor='e'
        )
        self.baslangic_toplam_label.pack(side="right", padx=10, pady=5)

    def baslangic_detay_toggle(self):
        """Başlangıç kasası detayını aç/kapa - artık kullanılmıyor (sabit görünüm)"""
        pass  # Sabit görünüm olduğu için toggle gerekmiyor

    def baslangic_detay_olustur_sabit(self):
        """Başlangıç kasası detay panelini oluştur - sabit görünüm, dolgun"""
        # Önceki içeriği temizle
        for widget in self.baslangic_detay_container.winfo_children():
            widget.destroy()

        punto = self.get_punto()
        hucre_pad = self.get_hucre_padding()

        # Başlık
        header = tk.Frame(self.baslangic_detay_container, bg='#2E7D32')
        header.pack(fill="x", pady=1)
        tk.Label(header, text="Küpür", font=("Arial", punto, "bold"), bg='#2E7D32', fg='white', width=8).pack(side="left", padx=hucre_pad, pady=hucre_pad)
        tk.Label(header, text="Adet", font=("Arial", punto, "bold"), bg='#2E7D32', fg='white', width=6).pack(side="left", padx=hucre_pad, pady=hucre_pad)
        tk.Label(header, text="Toplam", font=("Arial", punto, "bold"), bg='#2E7D32', fg='white', width=10).pack(side="left", padx=hucre_pad, pady=hucre_pad)

        # Küpür satırları
        for kupur in self.KUPURLER:
            if self.kupur_aktif_mi(kupur["deger"]):
                self.baslangic_kupur_satiri_olustur_sabit(kupur)

    def baslangic_detay_olustur(self):
        """Başlangıç kasası detay panelini oluştur - eski fonksiyon (uyumluluk için)"""
        self.baslangic_detay_olustur_sabit()

    def baslangic_kupur_satiri_olustur_sabit(self, kupur):
        """Başlangıç kasası küpür satırı - dolgun"""
        punto = self.get_punto()
        hucre_pad = self.get_hucre_padding()

        deger = kupur["deger"]
        row = tk.Frame(self.baslangic_detay_container, bg=self.section_colors['baslangic'])
        row.pack(fill="x", pady=1)

        tk.Label(
            row,
            text=kupur["aciklama"],
            font=("Arial", punto, "bold"),
            bg=self.section_colors['baslangic'],
            fg='#1B5E20',
            width=8,
            anchor='w'
        ).pack(side="left", padx=hucre_pad)

        # Adet entry
        var = self.baslangic_kupur_vars.get(deger)
        if var is None:
            var = tk.StringVar(value="0")
            self.baslangic_kupur_vars[deger] = var

        entry = tk.Entry(
            row,
            textvariable=var,
            font=("Arial", punto, "bold"),
            width=6,
            justify='center'
        )
        entry.pack(side="left", padx=hucre_pad)
        entry.bind('<FocusIn>', self.entry_fokus_secim)
        entry.bind('<Tab>', self.tab_sonraki_entry)
        entry.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
        self.baslangic_entry_list.append(entry)

        # Satır toplamı
        try:
            adet = int(var.get() or 0)
            toplam = adet * deger
        except ValueError:
            toplam = 0

        toplam_label = tk.Label(
            row,
            text=f"{toplam:,.2f}",
            font=("Arial", punto, "bold"),
            bg=self.section_colors['baslangic'],
            fg='#1565C0',
            width=10,
            anchor='e'
        )
        toplam_label.pack(side="left", padx=hucre_pad)

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
        # Manuel giriş aktifse onu kullan
        if self.manuel_baslangic_aktif:
            self.baslangic_toplam_var.set(f"{self.manuel_baslangic_tutar:,.2f}")
            self.hesaplari_guncelle()
            return

        toplam = 0
        for deger, var in self.baslangic_kupur_vars.items():
            try:
                adet = int(var.get() or 0)
                toplam += adet * deger
            except ValueError:
                pass
        self.baslangic_toplam_var.set(f"{toplam:,.2f}")
        self.hesaplari_guncelle()

    def botanikten_baslangic_kasasi_cek(self):
        """Botanik Kasa Kapatma penceresinden başlangıç kasası küpürlerini çek"""
        if not BOTANIK_VERI_MODULU_YUKLENDI:
            messagebox.showwarning("Uyarı", "Botanik veri çekme modülü yüklenemedi!")
            return

        try:
            # Küpürleri çek
            kupurler = botanik_baslangic_kupurlerini_cek()

            if kupurler is None:
                messagebox.showwarning(
                    "Uyarı",
                    "Botanik 'Kasa Kapatma' penceresi bulunamadı!\n\n"
                    "Lütfen Botanik EOS'ta 'Kasa Kapatma' penceresinin açık olduğundan emin olun."
                )
                return

            # Önizleme göster
            onizleme = "Botanik'ten çekilen küpür adetleri:\n\n"
            toplam = 0
            for deger in [200, 100, 50, 20, 10, 5, 1, 0.5]:
                adet = kupurler.get(deger, 0)
                tutar = adet * deger
                toplam += tutar
                onizleme += f"  {deger} TL x {adet} = {tutar:,.2f} TL\n"

            onizleme += f"\n{'─'*30}\n"
            onizleme += f"  TOPLAM: {toplam:,.2f} TL"

            onay = messagebox.askyesno(
                "Botanikten Çekilen Veriler",
                onizleme + "\n\nBu değerleri başlangıç kasasına aktarmak istiyor musunuz?",
                icon='question'
            )

            if not onay:
                return

            # Değerleri başlangıç kasası alanlarına yaz
            for deger, var in self.baslangic_kupur_vars.items():
                adet = kupurler.get(deger, 0)
                var.set(str(adet))

            # Manuel modu kapat (normal küpür moduna dön)
            self.manuel_baslangic_aktif = False
            self.manuel_baslangic_tutar = 0
            self.manuel_baslangic_aciklama = ""
            self.manuel_baslangic_btn.config(bg='#FFE082', fg='#E65100', text="✏ Elle")

            # Toplamı hesapla
            self.baslangic_toplam_hesapla()

            messagebox.showinfo(
                "Başarılı",
                f"Botanik'ten başlangıç kasası verileri aktarıldı.\n\nToplam: {toplam:,.2f} TL"
            )

            logger.info(f"Botanikten başlangıç kasası çekildi: {toplam} TL")

        except Exception as e:
            logger.error(f"Botanikten veri çekme hatası: {e}")
            messagebox.showerror("Hata", f"Veri çekme hatası:\n{str(e)}")

    def manuel_baslangic_penceresi_ac(self):
        """Manuel başlangıç kasası giriş penceresi"""
        pencere = tk.Toplevel(self.root)
        pencere.title("Manuel Başlangıç Kasası Girişi")
        pencere.geometry("450x380")
        pencere.transient(self.root)
        pencere.grab_set()
        pencere.configure(bg='#FFF8E1')
        pencere.resizable(False, False)

        # Başlık
        baslik_frame = tk.Frame(pencere, bg='#FF8F00', height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text="Manuel Başlangıç Kasası",
            font=("Arial", 13, "bold"),
            bg='#FF8F00',
            fg='white'
        ).pack(expand=True)

        # Uyarı
        uyari_frame = tk.Frame(pencere, bg='#FFECB3', pady=8)
        uyari_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(
            uyari_frame,
            text="⚠ DİKKAT: Bu işlem normal akışı bozar!\n"
                 "Sadece zorunlu durumlarda kullanınız.",
            font=("Arial", 9),
            bg='#FFECB3',
            fg='#E65100',
            justify='center'
        ).pack(pady=5)

        # Tutar girişi
        tutar_frame = tk.Frame(pencere, bg='#FFF8E1')
        tutar_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(
            tutar_frame,
            text="Başlangıç Kasası Tutarı (TL):",
            font=("Arial", 11, "bold"),
            bg='#FFF8E1',
            fg='#333'
        ).pack(anchor='w')

        tutar_var = tk.StringVar(value="0")
        tutar_entry = tk.Entry(
            tutar_frame,
            textvariable=tutar_var,
            font=("Arial", 14),
            width=20,
            justify='right'
        )
        tutar_entry.pack(fill="x", pady=5)
        tutar_entry.focus_set()
        tutar_entry.select_range(0, tk.END)

        # Açıklama girişi
        aciklama_frame = tk.Frame(pencere, bg='#FFF8E1')
        aciklama_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(
            aciklama_frame,
            text="Neden manuel giriş yapılıyor? (Zorunlu):",
            font=("Arial", 11, "bold"),
            bg='#FFF8E1',
            fg='#333'
        ).pack(anchor='w')

        aciklama_text = tk.Text(
            aciklama_frame,
            font=("Arial", 10),
            width=40,
            height=3,
            wrap='word'
        )
        aciklama_text.pack(fill="x", pady=5)

        # Butonlar
        buton_frame = tk.Frame(pencere, bg='#FFF8E1', pady=15)
        buton_frame.pack(fill="x")

        def iptal():
            pencere.destroy()

        def tamam():
            try:
                tutar_str = tutar_var.get().replace(",", ".").replace(" ", "")
                tutar = float(tutar_str)
            except ValueError:
                messagebox.showerror("Hata", "Geçerli bir tutar giriniz!", parent=pencere)
                return

            aciklama = aciklama_text.get("1.0", tk.END).strip()
            if not aciklama or len(aciklama) < 5:
                messagebox.showerror("Hata", "Lütfen neden manuel giriş yaptığınızı açıklayınız!\n(En az 5 karakter)", parent=pencere)
                return

            # Onay al
            onay = messagebox.askyesno(
                "Onay",
                f"Başlangıç kasası manuel olarak {tutar:,.2f} TL yapılacak.\n\n"
                f"Açıklama: {aciklama}\n\n"
                "Onaylıyor musunuz?",
                parent=pencere
            )

            if onay:
                self.manuel_baslangic_aktif = True
                self.manuel_baslangic_tutar = tutar
                self.manuel_baslangic_aciklama = aciklama

                # Küpür alanlarını devre dışı bırak görsel olarak
                self.baslangic_toplam_var.set(f"{tutar:,.2f}")

                # Butonu işaretli göster
                self.manuel_baslangic_btn.config(bg='#FF5722', fg='white', text="✓ Manuel")

                # Hesapları güncelle
                self.hesaplari_guncelle()

                logger.info(f"Manuel başlangıç kasası: {tutar} TL - {aciklama}")
                pencere.destroy()

                messagebox.showinfo(
                    "Başarılı",
                    f"Başlangıç kasası manuel olarak {tutar:,.2f} TL olarak ayarlandı.\n\n"
                    "Bu bilgi raporlarda saklanacaktır."
                )

        def sifirla():
            """Manuel girişi sıfırla, normal moda dön"""
            self.manuel_baslangic_aktif = False
            self.manuel_baslangic_tutar = 0
            self.manuel_baslangic_aciklama = ""
            self.manuel_baslangic_btn.config(bg='#FFE082', fg='#E65100', text="✏ Elle")
            self.baslangic_toplam_hesapla()
            pencere.destroy()
            messagebox.showinfo("Sıfırlandı", "Manuel giriş iptal edildi.\nNormal küpür hesabına dönüldü.")

        tk.Button(
            buton_frame,
            text="İptal",
            font=("Arial", 10),
            bg='#9E9E9E',
            fg='white',
            width=10,
            command=iptal
        ).pack(side="left", padx=20)

        if self.manuel_baslangic_aktif:
            tk.Button(
                buton_frame,
                text="Sıfırla",
                font=("Arial", 10),
                bg='#FF5722',
                fg='white',
                width=10,
                command=sifirla
            ).pack(side="left", padx=5)

        tk.Button(
            buton_frame,
            text="Kaydet",
            font=("Arial", 10, "bold"),
            bg='#4CAF50',
            fg='white',
            width=10,
            command=tamam
        ).pack(side="right", padx=20)

        # Mevcut değerleri yükle
        if self.manuel_baslangic_aktif:
            tutar_var.set(str(self.manuel_baslangic_tutar))
            aciklama_text.insert("1.0", self.manuel_baslangic_aciklama)

    def gun_sonu_sayim_bolumu_olustur(self):
        """2) Gün sonu kasa sayımı bölümü - SAĞ ÜST"""
        punto = self.get_punto()
        hucre_pad = self.get_hucre_padding()
        bolum_pad = self.get_bolum_padding()

        frame = tk.LabelFrame(
            self.sag_ust_frame,
            text="2) AKŞAM KASA SAYIMI",
            font=("Arial", punto, "bold"),
            bg=self.section_colors['sayim'],
            fg='#1B5E20',
            padx=bolum_pad,
            pady=bolum_pad
        )
        frame.pack(fill="both", expand=True)

        # Başlık
        header = tk.Frame(frame, bg='#2E7D32')
        header.pack(fill="x", pady=1)
        tk.Label(header, text="Küpür", font=("Arial", punto, "bold"), bg='#2E7D32', fg='white', width=7).pack(side="left", padx=hucre_pad, pady=hucre_pad)
        tk.Label(header, text="Adet", font=("Arial", punto, "bold"), bg='#2E7D32', fg='white', width=8).pack(side="left", padx=hucre_pad, pady=hucre_pad)
        tk.Label(header, text="Toplam", font=("Arial", punto, "bold"), bg='#2E7D32', fg='white', width=10).pack(side="left", padx=hucre_pad, pady=hucre_pad)

        # Küpür satırları
        for kupur in self.KUPURLER:
            if self.kupur_aktif_mi(kupur["deger"]):
                self.sayim_kupur_satiri_olustur(frame, kupur)

        # Sayım toplamı
        toplam_frame = tk.Frame(frame, bg=self.ara_toplam_bg)
        toplam_frame.pack(fill="x", pady=(2, 0))

        tk.Label(
            toplam_frame,
            text="SAYIM TOP:",
            font=("Arial", punto + 1, "bold"),
            bg=self.ara_toplam_bg,
            fg=self.ara_toplam_fg
        ).pack(side="left", padx=hucre_pad, pady=hucre_pad)

        self.sayim_toplam_label = tk.Label(
            toplam_frame,
            text="0,00 TL",
            font=("Arial", punto + 2, "bold"),
            bg=self.ara_toplam_bg,
            fg=self.ara_toplam_fg
        )
        self.sayim_toplam_label.pack(side="right", padx=hucre_pad, pady=hucre_pad)

    def sayim_kupur_satiri_olustur(self, parent, kupur):
        """Sayım küpür satırı - dolgun"""
        punto = self.get_punto()
        hucre_pad = self.get_hucre_padding()

        deger = kupur["deger"]
        row = tk.Frame(parent, bg=self.section_colors['sayim'])
        row.pack(fill="x", pady=1)

        tk.Label(
            row,
            text=kupur["aciklama"],
            font=("Arial", punto + 1, "bold"),
            bg=self.section_colors['sayim'],
            fg='#1B5E20',
            width=7,
            anchor='w'
        ).pack(side="left", padx=hucre_pad)

        # Adet frame (artı/eksi butonları ile)
        adet_frame = tk.Frame(row, bg=self.section_colors['sayim'])
        adet_frame.pack(side="left")

        tk.Button(
            adet_frame,
            text="-",
            font=("Arial", punto, "bold"),
            bg='#FFCDD2',
            fg='#C62828',
            width=2,
            bd=1,
            takefocus=False,
            command=lambda d=deger: self.sayim_adet_degistir(d, -1)
        ).pack(side="left")

        var = tk.StringVar(value="0")
        self.sayim_vars[deger] = var

        entry = tk.Entry(
            adet_frame,
            textvariable=var,
            font=("Arial", punto + 1, "bold"),
            width=6,
            justify='center'
        )
        entry.pack(side="left", padx=2)
        entry.bind('<KeyRelease>', lambda e, d=deger: self.sayim_satir_guncelle(d))
        entry.bind('<FocusIn>', self.entry_fokus_secim)
        entry.bind('<Tab>', self.tab_sonraki_entry)
        entry.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
        self.tab_order_entries.append(entry)

        tk.Button(
            adet_frame,
            text="+",
            font=("Arial", punto, "bold"),
            bg='#C8E6C9',
            fg='#2E7D32',
            width=2,
            bd=1,
            takefocus=False,
            command=lambda d=deger: self.sayim_adet_degistir(d, 1)
        ).pack(side="left")

        # Satır toplamı
        toplam_label = tk.Label(
            row,
            text="0,00",
            font=("Arial", punto + 1, "bold"),
            bg=self.section_colors['sayim'],
            fg='#1565C0',
            width=10,
            anchor='e'
        )
        toplam_label.pack(side="left", padx=hucre_pad)
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

    def alisveris_bolumu_olustur(self):
        """2-A) Sayım sırası alışveriş ve bozuk para ekleme bölümü - SAĞ ALT"""
        # Ana çerçeve
        main_frame = tk.LabelFrame(
            self.sag_alt_frame,
            text="2-A) SAYIM SIRASI ALIŞVERİŞ VE BOZUK PARA EKLEME",
            font=("Arial", 10, "bold"),
            bg='#FFF3E0',
            fg='#E65100',
            padx=3,
            pady=2
        )
        main_frame.pack(fill="both", expand=True)

        # Notebook (sekmeli yapı)
        style = ttk.Style()
        style.configure('Alisveris.TNotebook', background='#FFF3E0')
        style.configure('Alisveris.TNotebook.Tab', padding=[8, 3], font=('Arial', 9, 'bold'))

        self.alisveris_notebook = ttk.Notebook(main_frame, style='Alisveris.TNotebook')
        self.alisveris_notebook.pack(fill='both', expand=True)

        # === SEKME 1: ALIŞVERİŞ ===
        self.alisveris_sekmesi_olustur()

        # === SEKME 2: BOZUK PARA EKLEME ===
        self.bozuk_para_sekmesi_olustur()

    def alisveris_sekmesi_olustur(self):
        """Alışveriş sekmesi içeriği"""
        frame = tk.Frame(self.alisveris_notebook, bg='#FFF3E0')
        self.alisveris_notebook.add(frame, text='Alışveriş')

        # 1) Tahsilat tutarı
        tahsilat_frame = tk.Frame(frame, bg='#FFF3E0')
        tahsilat_frame.pack(fill="x", pady=2)

        tk.Label(tahsilat_frame, text="Tahsilat:", font=("Arial", 11, "bold"), bg='#FFF3E0', fg='#E65100').pack(side="left", padx=2)
        self.alisveris_tahsilat_entry = tk.Entry(tahsilat_frame, textvariable=self.alisveris_tahsilat_var, font=("Arial", 12, "bold"), width=10, justify='right', bg='#FFCC80')
        self.alisveris_tahsilat_entry.pack(side="right", padx=2)

        # 2) Alınan küpürler başlık
        tk.Label(frame, text="Müşteriden Alınan:", font=("Arial", 10, "bold"), bg='#FFF3E0', fg='#795548').pack(anchor='w', pady=(3, 1))

        # Küpür butonları
        kupurler = [200, 100, 50, 20, 10, 5, 1, 0.5]
        self.alisveris_kupur_btns = {}
        self.alisveris_kupur_labels = {}

        btn_frame1 = tk.Frame(frame, bg='#FFF3E0')
        btn_frame1.pack(fill="x", pady=1)
        btn_frame2 = tk.Frame(frame, bg='#FFF3E0')
        btn_frame2.pack(fill="x", pady=1)

        for i, kupur in enumerate(kupurler):
            parent_frame = btn_frame1 if i < 4 else btn_frame2
            kupur_container = tk.Frame(parent_frame, bg='#FFF3E0')
            kupur_container.pack(side="left", padx=1)

            kupur_text = f"{kupur:.0f}" if kupur >= 1 else "0,5"
            btn = tk.Button(kupur_container, text=kupur_text, font=("Arial", 9, "bold"), bg='#FFE0B2', fg='#E65100', width=3, bd=1, cursor='hand2', command=lambda k=kupur: self.alisveris_kupur_ekle(k))
            btn.pack(side="top")
            btn.bind('<Button-3>', lambda e, k=kupur: self.alisveris_kupur_azalt(k))
            self.alisveris_kupur_btns[kupur] = btn

            lbl = tk.Label(kupur_container, text="0", font=("Arial", 9), bg='#FFF3E0', fg='#795548', width=3)
            lbl.pack(side="top")
            self.alisveris_kupur_labels[kupur] = lbl

        # 3) Alınan toplam
        alinan_toplam_frame = tk.Frame(frame, bg='#FFE0B2')
        alinan_toplam_frame.pack(fill="x", pady=(3, 1))
        tk.Label(alinan_toplam_frame, text="Alınan:", font=("Arial", 10, "bold"), bg='#FFE0B2', fg='#E65100').pack(side="left", padx=3, pady=2)
        self.alisveris_alinan_label = tk.Label(alinan_toplam_frame, text="0 TL", font=("Arial", 11, "bold"), bg='#FFE0B2', fg='#E65100')
        self.alisveris_alinan_label.pack(side="right", padx=3, pady=2)

        # 4) Para Üstü Hesapla butonu
        tk.Button(frame, text="PARA ÜSTÜ HESAPLA", font=("Arial", 10, "bold"), bg='#2196F3', fg='white', bd=0, cursor='hand2', command=self.alisveris_para_ustu_hesapla).pack(fill="x", pady=3)

        # 5) Para üstü gösterimi
        para_ustu_frame = tk.Frame(frame, bg='#C8E6C9')
        para_ustu_frame.pack(fill="x", pady=1)
        tk.Label(para_ustu_frame, text="Para Üstü:", font=("Arial", 10, "bold"), bg='#C8E6C9', fg='#2E7D32').pack(side="left", padx=3, pady=2)
        self.alisveris_para_ustu_label = tk.Label(para_ustu_frame, text="0 TL", font=("Arial", 11, "bold"), bg='#C8E6C9', fg='#2E7D32')
        self.alisveris_para_ustu_label.pack(side="right", padx=3, pady=2)

        # 6) Para üstü küpür detayı
        self.alisveris_para_ustu_detay = tk.Label(frame, text="", font=("Arial", 9), bg='#FFF3E0', fg='#795548', wraplength=150, justify='left')
        self.alisveris_para_ustu_detay.pack(fill="x", pady=1)

        # 7) Butonlar - en dibe dayalı
        btn_frame = tk.Frame(frame, bg='#FFF3E0')
        btn_frame.pack(fill="x", side="bottom", pady=(5, 2))
        tk.Button(btn_frame, text="Temizle", font=("Arial", 10, "bold"), bg='#FFCDD2', fg='#C62828', bd=1, cursor='hand2', height=2, command=self.alisveris_temizle).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(btn_frame, text="Kasaya İşle", font=("Arial", 10, "bold"), bg='#4CAF50', fg='white', bd=1, cursor='hand2', height=2, command=self.alisveris_kasaya_isle).pack(side="right", padx=2, fill="x", expand=True)

    def bozuk_para_sekmesi_olustur(self):
        """Bozuk para ekleme sekmesi - YENİ TASARIM"""
        frame = tk.Frame(self.alisveris_notebook, bg='#E3F2FD')
        self.alisveris_notebook.add(frame, text='Bozuk Para')

        # Bozuk para değişkenleri
        self.bozuk_buyuk_kupurler = {}  # {deger: adet}
        self.bozuk_kucuk_kupurler = {}  # {deger: adet}
        self.bozuk_buyuk_labels = {}
        self.bozuk_kucuk_labels = {}
        self.bozuk_kucuk_entries = {}   # Textbox'lar
        self.bozuk_kucuk_btns = {}      # Butonlar
        self.bozuk_textbox_modu = False  # Textbox modunda mı?
        self.bozuk_ilk_tiklama_yapildi = False  # İlk tıklama yapıldı mı?

        # Üst başlık
        tk.Label(frame, text="Büyük küpürü bozuk paraya çevir", font=("Arial", 8), bg='#E3F2FD', fg='#1565C0').pack(pady=2)

        # Ana içerik - iki sütun
        content = tk.Frame(frame, bg='#E3F2FD')
        content.pack(fill='both', expand=True, padx=2)

        # SOL TARAF - Bozulacak büyük küpürler (200, 100, 50, 20, 10, 5)
        sol_frame = tk.LabelFrame(content, text="BOZULACAK", font=("Arial", 8, "bold"), bg='#BBDEFB', fg='#1565C0', padx=3, pady=2)
        sol_frame.pack(side='left', fill='both', expand=True, padx=(0, 2))

        buyuk_kupurler = [200, 100, 50, 20, 10, 5]
        for kupur in buyuk_kupurler:
            row = tk.Frame(sol_frame, bg='#BBDEFB')
            row.pack(fill='x', pady=1)

            btn = tk.Button(row, text=f"{kupur}", font=("Arial", 9, "bold"), bg='#90CAF9', fg='#0D47A1', width=4, cursor='hand2', command=lambda k=kupur: self.bozuk_buyuk_tikla(k))
            btn.pack(side='left', padx=2)
            btn.bind('<Button-3>', lambda e, k=kupur: self.bozuk_buyuk_azalt(k))

            lbl = tk.Label(row, text="0", font=("Arial", 9, "bold"), bg='#BBDEFB', fg='#1565C0', width=3)
            lbl.pack(side='right', padx=2)
            self.bozuk_buyuk_labels[kupur] = lbl
            self.bozuk_buyuk_kupurler[kupur] = 0

        # Bozulacak toplam
        self.bozuk_buyuk_toplam_label = tk.Label(sol_frame, text="TOPLAM: 0 TL", font=("Arial", 9, "bold"), bg='#64B5F6', fg='white')
        self.bozuk_buyuk_toplam_label.pack(fill='x', pady=(3, 1))

        # SAĞ TARAF - Bozuk paralar (100, 50, 20, 10, 5, 1, 0.50)
        self.bozuk_sag_frame = tk.LabelFrame(content, text="BOZUK PARA", font=("Arial", 8, "bold"), bg='#C8E6C9', fg='#2E7D32', padx=3, pady=2)
        self.bozuk_sag_frame.pack(side='right', fill='both', expand=True, padx=(2, 0))

        kucuk_kupurler = [100, 50, 20, 10, 5, 1, 0.50]
        for kupur in kucuk_kupurler:
            row = tk.Frame(self.bozuk_sag_frame, bg='#C8E6C9')
            row.pack(fill='x', pady=1)

            kupur_text = f"{kupur:.2f}" if kupur < 1 else f"{int(kupur)}"
            btn = tk.Button(row, text=kupur_text, font=("Arial", 8, "bold"), bg='#A5D6A7', fg='#1B5E20', width=4, cursor='hand2', command=lambda k=kupur: self.bozuk_kucuk_tikla(k))
            btn.pack(side='left', padx=2)
            btn.bind('<Button-3>', lambda e, k=kupur: self.bozuk_kucuk_azalt(k))
            self.bozuk_kucuk_btns[kupur] = btn

            # Adet label (başlangıçta görünür)
            lbl = tk.Label(row, text="0", font=("Arial", 9, "bold"), bg='#C8E6C9', fg='#2E7D32', width=5)
            lbl.pack(side='right', padx=2)
            self.bozuk_kucuk_labels[kupur] = lbl

            # Adet entry (başlangıçta gizli) - textbox modu için
            var = tk.StringVar(value="0")
            entry = tk.Entry(row, textvariable=var, font=("Arial", 9), width=5, justify='center')
            entry.bind('<KeyRelease>', lambda e, k=kupur: self.bozuk_entry_degisti(k))
            self.bozuk_kucuk_entries[kupur] = (entry, var)
            # Entry başlangıçta pack edilmez

            self.bozuk_kucuk_kupurler[kupur] = 0

        # Bozuk para toplam
        self.bozuk_kucuk_toplam_label = tk.Label(self.bozuk_sag_frame, text="TOPLAM: 0 TL", font=("Arial", 9, "bold"), bg='#66BB6A', fg='white')
        self.bozuk_kucuk_toplam_label.pack(fill='x', pady=(3, 1))

        # Alt butonlar
        alt_frame = tk.Frame(frame, bg='#E3F2FD')
        alt_frame.pack(fill='x', pady=3)

        tk.Button(alt_frame, text="Temizle", font=("Arial", 8), bg='#FFCDD2', fg='#C62828', cursor='hand2', command=self.bozuk_temizle).pack(side='left', padx=3)
        tk.Button(alt_frame, text="BOZDUR VE KASAYA EKLE", font=("Arial", 8, "bold"), bg='#4CAF50', fg='white', cursor='hand2', command=self.bozuk_kasaya_ekle).pack(side='right', padx=3)

    def bozuk_buyuk_tikla(self, kupur):
        """Bozulacak büyük küpüre tıklama"""
        self.bozuk_buyuk_kupurler[kupur] = self.bozuk_buyuk_kupurler.get(kupur, 0) + 1
        self.bozuk_buyuk_labels[kupur].config(text=str(self.bozuk_buyuk_kupurler[kupur]))
        self.bozuk_toplamlari_guncelle()

    def bozuk_buyuk_azalt(self, kupur):
        """Bozulacak büyük küpürü azalt (sağ tık)"""
        if self.bozuk_buyuk_kupurler.get(kupur, 0) > 0:
            self.bozuk_buyuk_kupurler[kupur] -= 1
            self.bozuk_buyuk_labels[kupur].config(text=str(self.bozuk_buyuk_kupurler[kupur]))
            self.bozuk_toplamlari_guncelle()

    def bozuk_kucuk_tikla(self, kupur):
        """Bozuk paraya tıklama - İlk tıklama otomatik, ikinci tıklama textbox modu"""
        buyuk_toplam = sum(k * a for k, a in self.bozuk_buyuk_kupurler.items())

        if buyuk_toplam <= 0:
            messagebox.showwarning("Uyarı", "Önce bozulacak küpür seçin!")
            return

        # Mevcut bozuk para toplamı
        mevcut_kucuk_toplam = sum(k * a for k, a in self.bozuk_kucuk_kupurler.items())
        kalan = buyuk_toplam - mevcut_kucuk_toplam

        # İlk tıklama mı?
        if not self.bozuk_ilk_tiklama_yapildi:
            # İlk tıklama - otomatik hesapla
            if kupur > kalan:
                messagebox.showwarning("Uyarı", f"Kalan tutar ({kalan:.2f} TL) bu küpür ({kupur} TL) için yetersiz!")
                return

            adet = int(kalan / kupur)
            if adet > 0:
                self.bozuk_kucuk_kupurler[kupur] = adet
                self.bozuk_kucuk_labels[kupur].config(text=str(adet))
                self.bozuk_ilk_tiklama_yapildi = True
        else:
            # İkinci tıklama - textbox moduna geç
            if not self.bozuk_textbox_modu:
                self.bozuk_textbox_moduna_gec()
            # Eğer zaten textbox modundaysa, tıklanan küpürün entry'sine fokusla
            if kupur in self.bozuk_kucuk_entries:
                entry, var = self.bozuk_kucuk_entries[kupur]
                entry.focus_set()
                entry.select_range(0, tk.END)

        self.bozuk_toplamlari_guncelle()

    def bozuk_textbox_moduna_gec(self):
        """Label'ları textbox'lara dönüştür"""
        self.bozuk_textbox_modu = True

        for kupur in self.bozuk_kucuk_kupurler:
            # Label'ı gizle
            self.bozuk_kucuk_labels[kupur].pack_forget()

            # Entry'yi göster
            entry, var = self.bozuk_kucuk_entries[kupur]
            var.set(str(self.bozuk_kucuk_kupurler[kupur]))
            entry.pack(side='right', padx=2)

    def bozuk_entry_degisti(self, kupur):
        """Textbox değeri değiştiğinde"""
        try:
            entry, var = self.bozuk_kucuk_entries[kupur]
            yeni_adet = int(var.get() or 0)
            if yeni_adet < 0:
                yeni_adet = 0
                var.set("0")

            self.bozuk_kucuk_kupurler[kupur] = yeni_adet
            self.bozuk_toplamlari_guncelle()

            # Aşım kontrolü
            buyuk_toplam = sum(k * a for k, a in self.bozuk_buyuk_kupurler.items())
            kucuk_toplam = sum(k * a for k, a in self.bozuk_kucuk_kupurler.items())

            if kucuk_toplam > buyuk_toplam:
                # Aşım uyarısı - entry'yi kırmızı yap
                entry.config(bg='#FFCDD2')
            else:
                entry.config(bg='white')

        except ValueError:
            pass

    def bozuk_kucuk_azalt(self, kupur):
        """Bozuk parayı azalt (sağ tık)"""
        if self.bozuk_kucuk_kupurler.get(kupur, 0) > 0:
            self.bozuk_kucuk_kupurler[kupur] -= 1
            self.bozuk_kucuk_labels[kupur].config(text=str(self.bozuk_kucuk_kupurler[kupur]))
            self.bozuk_toplamlari_guncelle()

    def bozuk_toplamlari_guncelle(self):
        """Bozuk para toplamlarını güncelle"""
        buyuk_toplam = sum(k * a for k, a in self.bozuk_buyuk_kupurler.items())
        kucuk_toplam = sum(k * a for k, a in self.bozuk_kucuk_kupurler.items())

        self.bozuk_buyuk_toplam_label.config(text=f"TOPLAM: {buyuk_toplam:,.0f} TL")

        # Eşleşme kontrolü ve aşım uyarısı
        if abs(buyuk_toplam - kucuk_toplam) < 0.01 and buyuk_toplam > 0:
            self.bozuk_kucuk_toplam_label.config(text=f"TOPLAM: {kucuk_toplam:,.2f} TL ✓", bg='#2E7D32')
        elif kucuk_toplam > buyuk_toplam:
            asim = kucuk_toplam - buyuk_toplam
            self.bozuk_kucuk_toplam_label.config(text=f"AŞIM: +{asim:,.2f} TL!", bg='#C62828')
        else:
            kalan = buyuk_toplam - kucuk_toplam
            if kalan > 0 and kucuk_toplam > 0:
                self.bozuk_kucuk_toplam_label.config(text=f"KALAN: {kalan:,.2f} TL", bg='#FF9800')
            else:
                self.bozuk_kucuk_toplam_label.config(text=f"TOPLAM: {kucuk_toplam:,.2f} TL", bg='#66BB6A')

    def bozuk_temizle(self):
        """Bozuk para verilerini temizle ve label moduna dön"""
        # Büyük küpürleri sıfırla
        for kupur in self.bozuk_buyuk_kupurler:
            self.bozuk_buyuk_kupurler[kupur] = 0
            self.bozuk_buyuk_labels[kupur].config(text="0")

        # Küçük küpürleri sıfırla
        for kupur in self.bozuk_kucuk_kupurler:
            self.bozuk_kucuk_kupurler[kupur] = 0
            self.bozuk_kucuk_labels[kupur].config(text="0")

            # Textbox modundan çık - entry'leri gizle, label'ları göster
            if self.bozuk_textbox_modu:
                entry, var = self.bozuk_kucuk_entries[kupur]
                entry.pack_forget()
                var.set("0")
                entry.config(bg='white')
                self.bozuk_kucuk_labels[kupur].pack(side='right', padx=2)

        # Mod bayraklarını sıfırla
        self.bozuk_textbox_modu = False
        self.bozuk_ilk_tiklama_yapildi = False

        self.bozuk_toplamlari_guncelle()

    def bozuk_kasaya_ekle(self):
        """Bozdurulan paraları kasaya işle"""
        buyuk_toplam = sum(k * a for k, a in self.bozuk_buyuk_kupurler.items())
        kucuk_toplam = sum(k * a for k, a in self.bozuk_kucuk_kupurler.items())

        if buyuk_toplam <= 0:
            messagebox.showwarning("Uyarı", "Bozulacak küpür seçilmedi!")
            return

        if abs(buyuk_toplam - kucuk_toplam) >= 0.01:
            messagebox.showwarning(
                "Uyarı",
                f"Toplamlar eşleşmiyor!\n\n"
                f"Bozulacak: {buyuk_toplam:,.0f} TL\n"
                f"Bozuk Para: {kucuk_toplam:,.2f} TL\n"
                f"Fark: {abs(buyuk_toplam - kucuk_toplam):,.2f} TL"
            )
            return

        # Kasadan büyük küpürleri çıkar
        for kupur, adet in self.bozuk_buyuk_kupurler.items():
            if adet > 0 and kupur in self.sayim_vars:
                try:
                    mevcut = int(self.sayim_vars[kupur].get() or 0)
                    if mevcut < adet:
                        messagebox.showerror("Hata", f"Kasada yeterli {kupur} TL yok!\nMevcut: {mevcut}, Gerekli: {adet}")
                        return
                except:
                    pass

        # İşlemi uygula
        # 1) Büyük küpürleri kasadan çıkar
        for kupur, adet in self.bozuk_buyuk_kupurler.items():
            if adet > 0 and kupur in self.sayim_vars:
                mevcut = int(self.sayim_vars[kupur].get() or 0)
                self.sayim_vars[kupur].set(str(mevcut - adet))

        # 2) Bozuk paraları kasaya ekle
        for kupur, adet in self.bozuk_kucuk_kupurler.items():
            if adet > 0 and kupur in self.sayim_vars:
                mevcut = int(self.sayim_vars[kupur].get() or 0)
                self.sayim_vars[kupur].set(str(mevcut + adet))

        # Küpür dökümü mesajı oluştur
        cikarilan_metin = ""
        for kupur in [200, 100, 50, 20, 10, 5]:
            adet = self.bozuk_buyuk_kupurler.get(kupur, 0)
            if adet > 0:
                cikarilan_metin += f"  {kupur} TL x {adet} = {kupur * adet:,.0f} TL\n"

        eklenen_metin = ""
        for kupur in [100, 50, 20, 10, 5, 1, 0.50]:
            adet = self.bozuk_kucuk_kupurler.get(kupur, 0)
            if adet > 0:
                kupur_str = f"{kupur:.2f}" if kupur < 1 else f"{int(kupur)}"
                eklenen_metin += f"  {kupur_str} TL x {adet} = {kupur * adet:,.2f} TL\n"

        # Hesapları güncelle
        self.hesaplari_guncelle()

        # Temizle
        self.bozuk_temizle()

        # Bilgi mesajı
        messagebox.showinfo(
            "BOZUM İŞLEMİ TAMAMLANDI",
            f"Para bozma işlemi kasaya işlendi!\n\n"
            f"{'='*35}\n"
            f"KASADAN ÇIKARILAN:\n{cikarilan_metin}\n"
            f"KASAYA EKLENEN:\n{eklenen_metin}\n"
            f"{'='*35}\n"
            f"TOPLAM: {buyuk_toplam:,.0f} TL"
        )

    def alisveris_kupur_ekle(self, kupur):
        """Müşteriden alınan küpürü ekle (sol tıklama)"""
        if kupur not in self.alisveris_alinan_kupurler:
            self.alisveris_alinan_kupurler[kupur] = 0
        self.alisveris_alinan_kupurler[kupur] += 1
        self.alisveris_kupur_labels[kupur].config(text=str(self.alisveris_alinan_kupurler[kupur]))
        self.alisveris_alinan_guncelle()

    def alisveris_kupur_azalt(self, kupur):
        """Müşteriden alınan küpürü azalt (sağ tıklama)"""
        if kupur in self.alisveris_alinan_kupurler and self.alisveris_alinan_kupurler[kupur] > 0:
            self.alisveris_alinan_kupurler[kupur] -= 1
            self.alisveris_kupur_labels[kupur].config(text=str(self.alisveris_alinan_kupurler[kupur]))
            self.alisveris_alinan_guncelle()

    def alisveris_alinan_guncelle(self):
        """Alınan toplam label'ını güncelle"""
        alinan_toplam = sum(k * a for k, a in self.alisveris_alinan_kupurler.items())
        if alinan_toplam == int(alinan_toplam):
            self.alisveris_alinan_label.config(text=f"{int(alinan_toplam)} TL")
        else:
            self.alisveris_alinan_label.config(text=f"{alinan_toplam:.1f} TL")

    def alisveris_para_ustu_hesapla(self):
        """Para Üstü Hesapla butonu - kasadaki küpürlerden verilecek parayı hesapla"""
        try:
            tahsilat_str = self.alisveris_tahsilat_var.get().replace(',', '.')
            tahsilat = float(tahsilat_str or 0)
        except ValueError:
            messagebox.showwarning("Uyarı", "Geçerli bir tahsilat tutarı girin!")
            return

        # Alınan toplam
        alinan_toplam = sum(k * a for k, a in self.alisveris_alinan_kupurler.items())

        if alinan_toplam == 0:
            messagebox.showwarning("Uyarı", "Müşteriden alınan küpür seçin!")
            return

        # Para üstü hesapla
        para_ustu = alinan_toplam - tahsilat
        self.alisveris_para_ustu = para_ustu

        if para_ustu < 0:
            self.alisveris_para_ustu_label.config(text=f"{para_ustu:.1f} TL", fg='#C62828')
            self.alisveris_para_ustu_detay.config(text="Yetersiz ödeme!", fg='#C62828')
            return
        elif abs(para_ustu) < 0.01:
            self.alisveris_para_ustu_label.config(text="0 TL", fg='#2E7D32')
            self.alisveris_para_ustu_detay.config(text="Tam ödeme", fg='#2E7D32')
            self.alisveris_para_ustu_kupurler = {}
            return

        # Para üstü göster
        if para_ustu == int(para_ustu):
            self.alisveris_para_ustu_label.config(text=f"{int(para_ustu)} TL", fg='#2E7D32')
        else:
            self.alisveris_para_ustu_label.config(text=f"{para_ustu:.1f} TL", fg='#2E7D32')

        # Para üstü için kasadan verilecek küpürleri hesapla
        self.alisveris_para_ustu_kupurler = {}
        kalan = para_ustu

        # Kasadaki küpürleri al (büyükten küçüğe, 50 kuruş dahil)
        kupurler = [200, 100, 50, 20, 10, 5, 1, 0.5]

        for kupur in kupurler:
            if kalan < 0.01:
                break

            # Kasadaki mevcut adet
            try:
                kasadaki = int(self.sayim_vars.get(kupur, tk.StringVar(value="0")).get() or 0)
            except (ValueError, AttributeError):
                kasadaki = 0

            # Kaç tane gerekli
            gerekli = int(kalan / kupur)
            kullanilacak = min(gerekli, kasadaki)

            if kullanilacak > 0:
                self.alisveris_para_ustu_kupurler[kupur] = kullanilacak
                kalan -= kullanilacak * kupur
                kalan = round(kalan, 2)  # Float hatasını önle

        # Detay göster
        if kalan >= 0.01:
            detay = f"Kasada yeterli küpür yok!\nEksik: {kalan:.1f} TL\nManuel düzeltme gerekli"
            self.alisveris_para_ustu_detay.config(text=detay, fg='#C62828')
        else:
            detay_list = []
            for k, a in sorted(self.alisveris_para_ustu_kupurler.items(), reverse=True):
                if k >= 1:
                    detay_list.append(f"{int(k)}x{a}")
                else:
                    detay_list.append(f"0,5x{a}")
            self.alisveris_para_ustu_detay.config(text=" + ".join(detay_list), fg='#2E7D32')

    def alisveris_temizle(self):
        """Alışveriş verilerini temizle"""
        self.alisveris_tahsilat_var.set("0")
        self.alisveris_alinan_kupurler = {}
        self.alisveris_para_ustu = 0
        self.alisveris_para_ustu_kupurler = {}

        for kupur, lbl in self.alisveris_kupur_labels.items():
            lbl.config(text="0")

        self.alisveris_alinan_label.config(text="0 TL")
        self.alisveris_para_ustu_label.config(text="0 TL", fg='#2E7D32')
        self.alisveris_para_ustu_detay.config(text="")

    def alisveris_kasaya_isle(self):
        """Alışverişi kasaya işle - küpürleri güncelle ve nakit artır"""
        try:
            tahsilat_str = self.alisveris_tahsilat_var.get().replace(',', '.')
            tahsilat = float(tahsilat_str or 0)
        except ValueError:
            messagebox.showwarning("Uyarı", "Geçerli bir tahsilat tutarı girin!")
            return

        # Para üstü hesaplanmış mı kontrol
        if not hasattr(self, 'alisveris_para_ustu_kupurler') or self.alisveris_para_ustu_kupurler is None:
            messagebox.showwarning("Uyarı", "Önce 'Para Üstü Hesapla' butonuna basın!")
            return

        # Para üstü kontrolü
        if self.alisveris_para_ustu < 0:
            messagebox.showwarning("Uyarı", "Yetersiz ödeme! İşlem yapılamaz.")
            return

        # Kasada yeterli küpür var mı tekrar kontrol
        kalan = self.alisveris_para_ustu
        for kupur in [200, 100, 50, 20, 10, 5, 1, 0.5]:
            try:
                kasadaki = int(self.sayim_vars.get(kupur, tk.StringVar(value="0")).get() or 0)
            except (ValueError, AttributeError):
                kasadaki = 0

            gerekli = int(kalan / kupur)
            kullanilacak = min(gerekli, kasadaki)
            kalan -= kullanilacak * kupur
            kalan = round(kalan, 2)

        if kalan >= 0.01:
            cevap = messagebox.askyesno(
                "Manuel Düzeltme Gerekli",
                f"Kasada yeterli küpür yok!\n"
                f"Eksik: {kalan:.1f} TL\n\n"
                f"Devam etmek istiyor musunuz?"
            )
            if not cevap:
                return

        # 1) Alınan küpürleri kasaya ekle
        for kupur, adet in self.alisveris_alinan_kupurler.items():
            if kupur in self.sayim_vars:
                try:
                    mevcut = int(self.sayim_vars[kupur].get() or 0)
                    self.sayim_vars[kupur].set(str(mevcut + adet))
                    self.sayim_satir_guncelle(kupur)
                except (ValueError, AttributeError):
                    pass

        # 2) Para üstü küpürlerini kasadan çıkar
        for kupur, adet in self.alisveris_para_ustu_kupurler.items():
            if kupur in self.sayim_vars:
                try:
                    mevcut = int(self.sayim_vars[kupur].get() or 0)
                    self.sayim_vars[kupur].set(str(max(0, mevcut - adet)))
                    self.sayim_satir_guncelle(kupur)
                except (ValueError, AttributeError):
                    pass

        # Botanik'e de işlensin mi sor
        botanik_cevap = messagebox.askyesno(
            "Botanik Nakit",
            f"Tahsilat tutarı ({tahsilat:.2f} TL) Botanik Nakit'e de eklensin mi?"
        )

        if botanik_cevap:
            # Botanik nakit değerini artır
            try:
                mevcut_botanik = float(self.botanik_nakit_var.get().replace(',', '.') or 0)
            except ValueError:
                mevcut_botanik = 0

            yeni_botanik = mevcut_botanik + tahsilat
            self.botanik_nakit_var.set(str(int(yeni_botanik) if yeni_botanik == int(yeni_botanik) else f"{yeni_botanik:.2f}"))
            self.hesaplari_guncelle()

        # Temizle ve bilgilendir
        self.alisveris_temizle()

        if botanik_cevap:
            messagebox.showinfo("Başarılı", f"Alışveriş kasaya ve Botanik'e işlendi!\nNakit artış: {tahsilat:.2f} TL")
        else:
            messagebox.showinfo("Başarılı", f"Alışveriş kasaya işlendi!\nNakit artış: {tahsilat:.2f} TL")

    def pos_bolumu_olustur(self):
        """3) POS ve IBAN raporları bölümü - SOL ALT"""
        punto = self.get_punto()
        hucre_pad = self.get_hucre_padding()
        bolum_pad = self.get_bolum_padding()

        frame = tk.LabelFrame(
            self.sol_alt_frame,
            text="3) POS VE IBAN",
            font=("Arial", punto, "bold"),
            bg=self.section_colors['pos'],
            fg='#0D47A1',
            padx=bolum_pad,
            pady=bolum_pad
        )
        frame.pack(fill="both", expand=True)

        # Üç sütunlu yapı
        columns_frame = tk.Frame(frame, bg=self.section_colors['pos'])
        columns_frame.pack(fill="both", expand=True, pady=1)

        # Sol sütun - EczacıPOS
        sol_frame = tk.Frame(columns_frame, bg=self.section_colors['pos'])
        sol_frame.pack(side="left", fill="both", expand=True, padx=1)

        tk.Label(sol_frame, text="EczPOS", font=("Arial", punto, "bold"),
                bg='#BBDEFB', fg='#0D47A1').pack(fill="x", pady=1)

        for i in range(4):
            row = tk.Frame(sol_frame, bg=self.section_colors['pos'])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{i+1}:", font=("Arial", punto - 1, "bold"),
                    bg=self.section_colors['pos'], fg=self.detay_fg, width=2, anchor='w').pack(side="left")
            var = tk.StringVar(value="0")
            self.pos_vars.append(var)
            entry = tk.Entry(row, textvariable=var, font=("Arial", punto), width=8, justify='right')
            entry.pack(side="right", padx=hucre_pad)
            entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
            entry.bind('<FocusIn>', self.entry_fokus_secim)
            entry.bind('<Tab>', self.tab_sonraki_entry)
            entry.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
            self.tab_order_entries.append(entry)

        # Orta sütun - Ingenico
        orta_frame = tk.Frame(columns_frame, bg=self.section_colors['pos'])
        orta_frame.pack(side="left", fill="both", expand=True, padx=1)

        tk.Label(orta_frame, text="Ingenico", font=("Arial", punto, "bold"),
                bg='#BBDEFB', fg='#0D47A1').pack(fill="x", pady=1)

        for i in range(4):
            row = tk.Frame(orta_frame, bg=self.section_colors['pos'])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{i+1}:", font=("Arial", punto - 1, "bold"),
                    bg=self.section_colors['pos'], fg=self.detay_fg, width=2, anchor='w').pack(side="left")
            var = tk.StringVar(value="0")
            self.pos_vars.append(var)
            entry = tk.Entry(row, textvariable=var, font=("Arial", punto), width=8, justify='right')
            entry.pack(side="right", padx=hucre_pad)
            entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
            entry.bind('<FocusIn>', self.entry_fokus_secim)
            entry.bind('<Tab>', self.tab_sonraki_entry)
            entry.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
            self.tab_order_entries.append(entry)

        # Sağ sütun - IBAN
        sag_frame = tk.Frame(columns_frame, bg='#E0F7FA')
        sag_frame.pack(side="left", fill="both", expand=True, padx=1)

        tk.Label(sag_frame, text="IBAN", font=("Arial", punto, "bold"),
                bg='#B2EBF2', fg='#00695C').pack(fill="x", pady=1)

        for i in range(4):
            row = tk.Frame(sag_frame, bg='#E0F7FA')
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{i+1}:", font=("Arial", punto - 1, "bold"),
                    bg='#E0F7FA', fg=self.detay_fg, width=2, anchor='w').pack(side="left")
            var = tk.StringVar(value="0")
            self.iban_vars.append(var)
            entry = tk.Entry(row, textvariable=var, font=("Arial", punto), width=8, justify='right')
            entry.pack(side="right", padx=hucre_pad)
            entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
            entry.bind('<FocusIn>', self.entry_fokus_secim)
            entry.bind('<Tab>', self.tab_sonraki_entry)
            entry.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
            self.tab_order_entries.append(entry)

        # Alt toplam satırı - POS ve IBAN toplamları yan yana, aynı hizada
        toplam_frame = tk.Frame(frame, bg='#FFD54F')  # Sari arka plan
        toplam_frame.pack(fill="x", pady=(1, 0))

        # POS Toplam (sol taraf - 2/3)
        pos_toplam_container = tk.Frame(toplam_frame, bg='#FFD54F')
        pos_toplam_container.pack(side="left", fill="x", expand=True)
        tk.Label(pos_toplam_container, text="POS TOP:", font=("Arial", punto, "bold"),
                bg='#FFD54F', fg='#0D47A1').pack(side="left", padx=hucre_pad, pady=hucre_pad)
        self.pos_toplam_label = tk.Label(pos_toplam_container, text="0,00", font=("Arial", punto + 1, "bold"),
                                         bg='#FFD54F', fg='#0D47A1')
        self.pos_toplam_label.pack(side="right", padx=hucre_pad, pady=hucre_pad)

        # IBAN Toplam (sag taraf - 1/3)
        iban_toplam_container = tk.Frame(toplam_frame, bg='#80DEEA')
        iban_toplam_container.pack(side="left", fill="x", expand=True)
        tk.Label(iban_toplam_container, text="IBAN:", font=("Arial", punto, "bold"),
                bg='#80DEEA', fg='#00695C').pack(side="left", padx=hucre_pad, pady=hucre_pad)
        self.iban_toplam_label = tk.Label(iban_toplam_container, text="0,00", font=("Arial", punto + 1, "bold"),
                                          bg='#80DEEA', fg='#00695C')
        self.iban_toplam_label.pack(side="right", padx=hucre_pad, pady=hucre_pad)

        # Eski label'lar icin uyumluluk (hesaplari_guncelle'de kullaniliyor)
        self.eczpos_toplam_label = tk.Label(frame)  # Gizli
        self.ingenico_toplam_label = tk.Label(frame)  # Gizli

    def iban_bolumu_olustur(self):
        """IBAN bölümü artık pos_bolumu_olustur içinde - bu fonksiyon boş"""
        pass  # IBAN artık POS ile birleştirildi

    def karsilastirma_tablosu_olustur(self):
        """6) Karşılaştırma tablosu - Sayım vs Botanik - dolgun tasarım"""
        punto = self.get_punto()
        hucre_pad = self.get_hucre_padding()
        bolum_pad = self.get_bolum_padding()

        # Ana container - tüm alanı kapla
        container = tk.Frame(self.tablo_frame, bg=self.bg_color)
        container.pack(fill="both", expand=True)

        # 6) Karşılaştırma Tablosu
        frame = tk.LabelFrame(
            container,
            text="6) SAYIM / BOTANİK KARŞILAŞTIRMA",
            font=("Arial", punto + 1, "bold"),
            bg='#FFFFFF',
            fg='#1A237E',
            bd=2,
            relief='groove',
            padx=bolum_pad,
            pady=bolum_pad
        )
        frame.pack(fill="both", expand=True)

        # Grid ile hizalı tablo - tüm alanı kapla
        tablo = tk.Frame(frame, bg='#FFFFFF')
        tablo.pack(fill="both", expand=True, pady=1)

        # Grid sütunlarını eşit genişlikte yay
        tablo.columnconfigure(0, weight=2)
        tablo.columnconfigure(1, weight=1)
        tablo.columnconfigure(2, weight=1)
        tablo.columnconfigure(3, weight=1)
        # Satırları da genişlet
        for i in range(5):
            tablo.rowconfigure(i, weight=1)

        # Başlık satırı - daha büyük ve vurgulu
        tk.Label(tablo, text="", font=("Arial", punto + 2, "bold"),
                bg='#5C6BC0', fg='white', padx=hucre_pad + 2, pady=hucre_pad).grid(row=0, column=0, sticky='nsew', padx=1, pady=1)
        tk.Label(tablo, text="SAYIM", font=("Arial", punto + 3, "bold"),
                bg='#2196F3', fg='white', padx=hucre_pad + 2, pady=hucre_pad).grid(row=0, column=1, sticky='nsew', padx=1, pady=1)
        tk.Label(tablo, text="BOTANİK", font=("Arial", punto + 3, "bold"),
                bg='#FF9800', fg='white', padx=hucre_pad + 2, pady=hucre_pad).grid(row=0, column=2, sticky='nsew', padx=1, pady=1)
        tk.Label(tablo, text="FARK", font=("Arial", punto + 3, "bold"),
                bg='#607D8B', fg='white', padx=hucre_pad + 2, pady=hucre_pad).grid(row=0, column=3, sticky='nsew', padx=1, pady=1)

        # Nakit satırı - daha büyük
        tk.Label(tablo, text="Düzeltilmiş Nakit", font=("Arial", punto + 1, "bold"),
                bg='#E8F5E9', fg='#2E7D32', padx=hucre_pad + 2, pady=hucre_pad, anchor='w').grid(row=1, column=0, sticky='nsew', padx=1, pady=1)
        self.duzeltilmis_nakit_label = tk.Label(tablo, text="0,00", font=("Arial", punto + 3, "bold"),
                bg='#BBDEFB', fg='#1565C0', padx=hucre_pad + 2, pady=hucre_pad, anchor='e')
        self.duzeltilmis_nakit_label.grid(row=1, column=1, sticky='nsew', padx=1, pady=1)
        self.botanik_nakit_gosterge = tk.Label(tablo, text="0,00", font=("Arial", punto + 3, "bold"),
                bg='#FFE0B2', fg='#E65100', padx=hucre_pad + 2, pady=hucre_pad, anchor='e')
        self.botanik_nakit_gosterge.grid(row=1, column=2, sticky='nsew', padx=1, pady=1)
        self.nakit_fark_label = tk.Label(tablo, text="0,00", font=("Arial", punto + 3, "bold"),
                bg='#ECEFF1', fg='#455A64', padx=hucre_pad + 2, pady=hucre_pad, anchor='e')
        self.nakit_fark_label.grid(row=1, column=3, sticky='nsew', padx=1, pady=1)

        # POS satırı - daha büyük
        tk.Label(tablo, text="POS Toplam", font=("Arial", punto + 1, "bold"),
                bg='#E3F2FD', fg='#1565C0', padx=hucre_pad + 2, pady=hucre_pad, anchor='w').grid(row=2, column=0, sticky='nsew', padx=1, pady=1)
        self.ozet_pos_label = tk.Label(tablo, text="0,00", font=("Arial", punto + 3, "bold"),
                bg='#BBDEFB', fg='#1565C0', padx=hucre_pad + 2, pady=hucre_pad, anchor='e')
        self.ozet_pos_label.grid(row=2, column=1, sticky='nsew', padx=1, pady=1)
        self.botanik_pos_gosterge = tk.Label(tablo, text="0,00", font=("Arial", punto + 3, "bold"),
                bg='#FFE0B2', fg='#E65100', padx=hucre_pad + 2, pady=hucre_pad, anchor='e')
        self.botanik_pos_gosterge.grid(row=2, column=2, sticky='nsew', padx=1, pady=1)
        self.pos_fark_label = tk.Label(tablo, text="0,00", font=("Arial", punto + 3, "bold"),
                bg='#ECEFF1', fg='#455A64', padx=hucre_pad + 2, pady=hucre_pad, anchor='e')
        self.pos_fark_label.grid(row=2, column=3, sticky='nsew', padx=1, pady=1)

        # IBAN satırı - daha büyük
        tk.Label(tablo, text="IBAN Toplam", font=("Arial", punto + 1, "bold"),
                bg='#E0F2F1', fg='#00695C', padx=hucre_pad + 2, pady=hucre_pad, anchor='w').grid(row=3, column=0, sticky='nsew', padx=1, pady=1)
        self.ozet_iban_label = tk.Label(tablo, text="0,00", font=("Arial", punto + 3, "bold"),
                bg='#BBDEFB', fg='#1565C0', padx=hucre_pad + 2, pady=hucre_pad, anchor='e')
        self.ozet_iban_label.grid(row=3, column=1, sticky='nsew', padx=1, pady=1)
        self.botanik_iban_gosterge = tk.Label(tablo, text="0,00", font=("Arial", punto + 3, "bold"),
                bg='#FFE0B2', fg='#E65100', padx=hucre_pad + 2, pady=hucre_pad, anchor='e')
        self.botanik_iban_gosterge.grid(row=3, column=2, sticky='nsew', padx=1, pady=1)
        self.iban_fark_label = tk.Label(tablo, text="0,00", font=("Arial", punto + 3, "bold"),
                bg='#ECEFF1', fg='#455A64', padx=hucre_pad + 2, pady=hucre_pad, anchor='e')
        self.iban_fark_label.grid(row=3, column=3, sticky='nsew', padx=1, pady=1)

        # GENEL TOPLAM satırı - en vurgulu
        tk.Label(tablo, text="GENEL TOPLAM", font=("Arial", punto + 3, "bold"),
                bg='#3F51B5', fg='white', padx=hucre_pad + 2, pady=hucre_pad + 2, anchor='w').grid(row=4, column=0, sticky='nsew', padx=1, pady=1)
        self.genel_toplam_label = tk.Label(tablo, text="0,00", font=("Arial", punto + 5, "bold"),
                bg='#42A5F5', fg='#FFEB3B', padx=hucre_pad + 2, pady=hucre_pad + 2, anchor='e')
        self.genel_toplam_label.grid(row=4, column=1, sticky='nsew', padx=1, pady=1)
        self.botanik_toplam_gosterge = tk.Label(tablo, text="0,00", font=("Arial", punto + 5, "bold"),
                bg='#E65100', fg='#FFEB3B', padx=hucre_pad + 2, pady=hucre_pad + 2, anchor='e')
        self.botanik_toplam_gosterge.grid(row=4, column=2, sticky='nsew', padx=1, pady=1)
        self.genel_fark_label = tk.Label(tablo, text="0,00", font=("Arial", punto + 5, "bold"),
                bg='#37474F', fg='#FFEB3B', padx=hucre_pad + 2, pady=hucre_pad + 2, anchor='e')
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

    def arti_eksi_popup_ac(self):
        """8) Artı/Eksi tutarsızlık sebepleri - büyük popup olarak açılır"""
        # Popup penceresi
        popup = tk.Toplevel(self.root)
        popup.title("8) ARTI/EKSİ TUTARSIZLIK SEBEPLERİ")
        popup.geometry("1200x700")
        popup.transient(self.root)
        popup.grab_set()
        popup.configure(bg='#FAFAFA')

        # Ekranı ortala
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() - 1200) // 2
        y = (popup.winfo_screenheight() - 700) // 2
        popup.geometry(f"1200x700+{x}+{y}")

        # Başlık
        baslik_frame = tk.Frame(popup, bg='#C62828', height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        # Fark değerini al
        try:
            fark_text = self.genel_fark_label.cget("text").replace(",", ".").replace(" TL", "").replace("+", "").strip()
            fark = float(fark_text) if fark_text else 0
        except (ValueError, AttributeError):
            fark = 0

        tk.Label(
            baslik_frame,
            text=f"8) ARTI/EKSİ TUTARSIZLIK SEBEPLERİ - Fark: {fark:,.2f} TL",
            font=("Arial", 16, "bold"),
            bg='#C62828',
            fg='white'
        ).pack(expand=True)

        # Ana içerik
        content = tk.Frame(popup, bg='#FAFAFA')
        content.pack(fill="both", expand=True, padx=10, pady=10)

        # Notebook (sekmeler)
        notebook = ttk.Notebook(content)
        notebook.pack(fill="both", expand=True)

        # Sekme 1: Kasa Açık (Eksik) Durumu
        eksik_frame = tk.Frame(notebook, bg='#FFEBEE')
        notebook.add(eksik_frame, text="  KASA AÇIK (EKSİK)  ")

        # Sekme 2: Kasa Fazla Durumu
        fazla_frame = tk.Frame(notebook, bg='#E8F5E9')
        notebook.add(fazla_frame, text="  KASA FAZLA  ")

        # Sebepleri JSON'dan yükle
        sebepler = self.sebepleri_yukle()
        eksik_sebepler = [(f"{i+1}) {s[0]}", s[1]) for i, s in enumerate(sebepler.get("eksik", []))]
        fazla_sebepler = [(f"{i+1}) {s[0]}", s[1]) for i, s in enumerate(sebepler.get("fazla", []))]

        # Eksik sekmesi - checkbox listesi
        self.popup_eksik_checkbox_olustur(eksik_frame, eksik_sebepler, '#FFEBEE')

        # Fazla sekmesi - checkbox listesi
        self.popup_fazla_checkbox_olustur(fazla_frame, fazla_sebepler, '#E8F5E9')

        # Alt butonlar
        kapat_frame = tk.Frame(popup, bg='#FAFAFA')
        kapat_frame.pack(fill="x", pady=10)

        # Düzenle butonu
        tk.Button(
            kapat_frame,
            text="SEBEPLERİ DÜZENLE",
            font=("Arial", 11, "bold"),
            bg='#FF9800',
            fg='white',
            width=18,
            height=2,
            cursor='hand2',
            command=lambda: self.sebep_duzenle_popup(popup)
        ).pack(side="left", padx=20)

        # Kapat butonu
        tk.Button(
            kapat_frame,
            text="KAPAT",
            font=("Arial", 12, "bold"),
            bg='#455A64',
            fg='white',
            width=15,
            height=2,
            cursor='hand2',
            command=popup.destroy
        ).pack(side="right", padx=20)

    def popup_eksik_checkbox_olustur(self, parent, sebepler, bg_color):
        """Popup için checkbox listesi oluştur - büyük ve okunabilir"""
        canvas = tk.Canvas(parent, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=bg_color)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scrollable.bind("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 4 sütunlu grid
        for i in range(4):
            scrollable.columnconfigure(i, weight=1)

        for i, (baslik, aciklama) in enumerate(sebepler):
            var = tk.BooleanVar(value=False)
            row = i // 4
            col = i % 4

            madde_frame = tk.Frame(scrollable, bg=bg_color, bd=1, relief='groove')
            madde_frame.grid(row=row, column=col, sticky='nsew', padx=3, pady=3)

            cb = tk.Checkbutton(
                madde_frame,
                text=baslik,
                variable=var,
                font=("Arial", 10, "bold"),
                bg=bg_color,
                fg='#C62828',
                activebackground=bg_color,
                anchor='w',
                padx=5,
                pady=3,
                selectcolor='white'
            )
            cb.pack(fill="x", anchor='w')
            cb.bind("<MouseWheel>", _on_mousewheel)

            aciklama_label = tk.Label(
                madde_frame,
                text=aciklama,
                font=("Arial", 9),
                bg=bg_color,
                fg='#555',
                anchor='w',
                wraplength=250,
                justify='left'
            )
            aciklama_label.pack(fill="x", anchor='w', padx=(25, 5), pady=(0, 5))
            aciklama_label.bind("<MouseWheel>", _on_mousewheel)

    def popup_fazla_checkbox_olustur(self, parent, sebepler, bg_color):
        """Popup için fazla checkbox listesi oluştur"""
        canvas = tk.Canvas(parent, bg=bg_color, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=bg_color)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<MouseWheel>", _on_mousewheel)
        scrollable.bind("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 4 sütunlu grid
        for i in range(4):
            scrollable.columnconfigure(i, weight=1)

        for i, (baslik, aciklama) in enumerate(sebepler):
            var = tk.BooleanVar(value=False)
            row = i // 4
            col = i % 4

            madde_frame = tk.Frame(scrollable, bg=bg_color, bd=1, relief='groove')
            madde_frame.grid(row=row, column=col, sticky='nsew', padx=3, pady=3)

            cb = tk.Checkbutton(
                madde_frame,
                text=baslik,
                variable=var,
                font=("Arial", 10, "bold"),
                bg=bg_color,
                fg='#2E7D32',
                activebackground=bg_color,
                anchor='w',
                padx=5,
                pady=3,
                selectcolor='white'
            )
            cb.pack(fill="x", anchor='w')
            cb.bind("<MouseWheel>", _on_mousewheel)

            aciklama_label = tk.Label(
                madde_frame,
                text=aciklama,
                font=("Arial", 9),
                bg=bg_color,
                fg='#555',
                anchor='w',
                wraplength=250,
                justify='left'
            )
            aciklama_label.pack(fill="x", anchor='w', padx=(25, 5), pady=(0, 5))
            aciklama_label.bind("<MouseWheel>", _on_mousewheel)

    def sebep_duzenle_popup(self, parent_popup):
        """Sebep düzenleme penceresi"""
        duzenle = tk.Toplevel(self.root)
        duzenle.title("Sebepleri Düzenle")
        duzenle.geometry("700x500")
        duzenle.transient(self.root)
        duzenle.grab_set()
        duzenle.configure(bg='#FAFAFA')

        # Ortala
        duzenle.update_idletasks()
        x = (duzenle.winfo_screenwidth() - 700) // 2
        y = (duzenle.winfo_screenheight() - 500) // 2
        duzenle.geometry(f"700x500+{x}+{y}")

        # Mevcut sebepleri yükle
        sebepler = self.sebepleri_yukle()
        eksik_list = list(sebepler.get("eksik", []))
        fazla_list = list(sebepler.get("fazla", []))

        # Başlık
        tk.Label(duzenle, text="SEBEP DÜZENLEME", font=("Arial", 14, "bold"),
                bg='#FAFAFA', fg='#333').pack(pady=10)

        # Notebook
        notebook = ttk.Notebook(duzenle)
        notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Eksik sekmesi
        eksik_frame = tk.Frame(notebook, bg='#FFEBEE')
        notebook.add(eksik_frame, text="  KASA EKSİK SEBEPLERİ  ")

        # Fazla sekmesi
        fazla_frame = tk.Frame(notebook, bg='#E8F5E9')
        notebook.add(fazla_frame, text="  KASA FAZLA SEBEPLERİ  ")

        def liste_olustur(parent, items, bg_color):
            """Listbox ve butonları oluştur"""
            container = tk.Frame(parent, bg=bg_color)
            container.pack(fill="both", expand=True, padx=5, pady=5)

            # Sol - Listbox
            list_frame = tk.Frame(container, bg=bg_color)
            list_frame.pack(side="left", fill="both", expand=True)

            scrollbar = tk.Scrollbar(list_frame)
            scrollbar.pack(side="right", fill="y")

            listbox = tk.Listbox(list_frame, font=("Arial", 10), height=15,
                                yscrollcommand=scrollbar.set, selectmode="single")
            listbox.pack(side="left", fill="both", expand=True)
            scrollbar.config(command=listbox.yview)

            # Listeyi doldur
            for i, (baslik, aciklama) in enumerate(items):
                listbox.insert(tk.END, f"{i+1}. {baslik}")

            # Sağ - Butonlar
            btn_frame = tk.Frame(container, bg=bg_color)
            btn_frame.pack(side="right", fill="y", padx=10)

            def ekle():
                dialog = tk.Toplevel(duzenle)
                dialog.title("Yeni Sebep Ekle")
                dialog.geometry("500x320")
                dialog.transient(duzenle)
                dialog.grab_set()

                tk.Label(dialog, text="Başlık:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10,0))
                baslik_entry = tk.Entry(dialog, font=("Arial", 10), width=60)
                baslik_entry.pack(padx=10, pady=5, fill="x")

                tk.Label(dialog, text="Açıklama:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10)
                aciklama_frame = tk.Frame(dialog)
                aciklama_frame.pack(padx=10, pady=5, fill="both", expand=True)

                aciklama_text = tk.Text(aciklama_frame, font=("Arial", 10), width=60, height=8, wrap="word")
                aciklama_scroll = tk.Scrollbar(aciklama_frame, command=aciklama_text.yview)
                aciklama_text.configure(yscrollcommand=aciklama_scroll.set)
                aciklama_scroll.pack(side="right", fill="y")
                aciklama_text.pack(side="left", fill="both", expand=True)

                def kaydet():
                    b = baslik_entry.get().strip()
                    a = aciklama_text.get("1.0", tk.END).strip()
                    if b:
                        items.append((b, a))
                        listbox.insert(tk.END, f"{len(items)}. {b}")
                        dialog.destroy()

                tk.Button(dialog, text="EKLE", font=("Arial", 10, "bold"),
                         bg="#4CAF50", fg="white", command=kaydet).pack(pady=15)

            def duzenle_secili():
                sel = listbox.curselection()
                if not sel:
                    messagebox.showwarning("Uyarı", "Lütfen bir sebep seçin!")
                    return
                idx = sel[0]
                baslik, aciklama = items[idx]

                dialog = tk.Toplevel(duzenle)
                dialog.title("Sebep Düzenle")
                dialog.geometry("500x320")
                dialog.transient(duzenle)
                dialog.grab_set()

                tk.Label(dialog, text="Başlık:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10, pady=(10,0))
                baslik_entry = tk.Entry(dialog, font=("Arial", 10), width=60)
                baslik_entry.insert(0, baslik)
                baslik_entry.pack(padx=10, pady=5, fill="x")

                tk.Label(dialog, text="Açıklama:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10)
                aciklama_frame = tk.Frame(dialog)
                aciklama_frame.pack(padx=10, pady=5, fill="both", expand=True)

                aciklama_text = tk.Text(aciklama_frame, font=("Arial", 10), width=60, height=8, wrap="word")
                aciklama_scroll = tk.Scrollbar(aciklama_frame, command=aciklama_text.yview)
                aciklama_text.configure(yscrollcommand=aciklama_scroll.set)
                aciklama_scroll.pack(side="right", fill="y")
                aciklama_text.pack(side="left", fill="both", expand=True)
                aciklama_text.insert("1.0", aciklama)

                def kaydet():
                    b = baslik_entry.get().strip()
                    a = aciklama_text.get("1.0", tk.END).strip()
                    if b:
                        items[idx] = (b, a)
                        listbox.delete(idx)
                        listbox.insert(idx, f"{idx+1}. {b}")
                        dialog.destroy()

                tk.Button(dialog, text="KAYDET", font=("Arial", 10, "bold"),
                         bg="#2196F3", fg="white", command=kaydet).pack(pady=15)

            def sil():
                sel = listbox.curselection()
                if not sel:
                    messagebox.showwarning("Uyarı", "Lütfen bir sebep seçin!")
                    return
                idx = sel[0]
                if messagebox.askyesno("Onay", "Bu sebebi silmek istediğinize emin misiniz?"):
                    items.pop(idx)
                    listbox.delete(0, tk.END)
                    for i, (b, a) in enumerate(items):
                        listbox.insert(tk.END, f"{i+1}. {b}")

            def yukari():
                sel = listbox.curselection()
                if not sel or sel[0] == 0:
                    return
                idx = sel[0]
                items[idx], items[idx-1] = items[idx-1], items[idx]
                listbox.delete(0, tk.END)
                for i, (b, a) in enumerate(items):
                    listbox.insert(tk.END, f"{i+1}. {b}")
                listbox.selection_set(idx-1)

            def asagi():
                sel = listbox.curselection()
                if not sel or sel[0] >= len(items)-1:
                    return
                idx = sel[0]
                items[idx], items[idx+1] = items[idx+1], items[idx]
                listbox.delete(0, tk.END)
                for i, (b, a) in enumerate(items):
                    listbox.insert(tk.END, f"{i+1}. {b}")
                listbox.selection_set(idx+1)

            tk.Button(btn_frame, text="EKLE", font=("Arial", 10, "bold"),
                     bg="#4CAF50", fg="white", width=10, command=ekle).pack(pady=5)
            tk.Button(btn_frame, text="DÜZENLE", font=("Arial", 10, "bold"),
                     bg="#2196F3", fg="white", width=10, command=duzenle_secili).pack(pady=5)
            tk.Button(btn_frame, text="SİL", font=("Arial", 10, "bold"),
                     bg="#F44336", fg="white", width=10, command=sil).pack(pady=5)
            tk.Label(btn_frame, text="", bg=bg_color).pack(pady=10)
            tk.Button(btn_frame, text="▲ YUKARI", font=("Arial", 10, "bold"),
                     bg="#9E9E9E", fg="white", width=10, command=yukari).pack(pady=5)
            tk.Button(btn_frame, text="▼ AŞAĞI", font=("Arial", 10, "bold"),
                     bg="#9E9E9E", fg="white", width=10, command=asagi).pack(pady=5)

            return listbox

        eksik_listbox = liste_olustur(eksik_frame, eksik_list, '#FFEBEE')
        fazla_listbox = liste_olustur(fazla_frame, fazla_list, '#E8F5E9')

        # Alt butonlar
        alt_frame = tk.Frame(duzenle, bg='#FAFAFA')
        alt_frame.pack(fill="x", pady=10)

        def kaydet_ve_kapat():
            yeni_sebepler = {
                "eksik": eksik_list,
                "fazla": fazla_list
            }
            if self.sebepleri_kaydet(yeni_sebepler):
                messagebox.showinfo("Başarılı", "Sebepler kaydedildi!\nDeğişiklikleri görmek için pencereyi yeniden açın.")
                duzenle.destroy()
            else:
                messagebox.showerror("Hata", "Sebepler kaydedilemedi!")

        def varsayilana_don():
            if messagebox.askyesno("Onay", "Tüm sebepler varsayılan değerlere dönecek. Emin misiniz?"):
                varsayilan = self.varsayilan_sebepler()
                eksik_list.clear()
                eksik_list.extend(varsayilan["eksik"])
                fazla_list.clear()
                fazla_list.extend(varsayilan["fazla"])
                # Listboxları güncelle
                eksik_listbox.delete(0, tk.END)
                for i, (b, a) in enumerate(eksik_list):
                    eksik_listbox.insert(tk.END, f"{i+1}. {b}")
                fazla_listbox.delete(0, tk.END)
                for i, (b, a) in enumerate(fazla_list):
                    fazla_listbox.insert(tk.END, f"{i+1}. {b}")

        tk.Button(alt_frame, text="VARSAYILANA DÖN", font=("Arial", 10, "bold"),
                 bg="#FF9800", fg="white", width=16, command=varsayilana_don).pack(side="left", padx=20)
        tk.Button(alt_frame, text="KAYDET VE KAPAT", font=("Arial", 11, "bold"),
                 bg="#4CAF50", fg="white", width=16, command=kaydet_ve_kapat).pack(side="right", padx=20)
        tk.Button(alt_frame, text="İPTAL", font=("Arial", 10, "bold"),
                 bg="#9E9E9E", fg="white", width=10, command=duzenle.destroy).pack(side="right", padx=5)

    def arti_eksi_listesi_olustur(self):
        """8) Artı/Eksi tutarsızlık sebepleri - ESKİ FONKSİYON (kullanılmıyor)"""
        # Bu fonksiyon artık kullanılmıyor, arti_eksi_popup_ac kullanılıyor
        pass

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
        """7) Ertesi gün kasası ve ayrılan para tablosu - basit ve düzgün"""
        # Ana frame
        frame = tk.LabelFrame(
            self.para_ayirma_frame,
            text="7) Ertesi Gün Kasası / Ayrılan Para",
            font=("Arial", 12, "bold"),
            bg='#E8EAF6',
            fg='#3F51B5',
            bd=2,
            relief='groove',
            padx=5,
            pady=3
        )
        frame.pack(fill="both", expand=True)

        # Alt kisim - Sadece etiketler (Yarinin Baslangic Kasasi ve Ayrilan Para)
        # Yükseklik artırıldı (9mm → 15mm, pady 8 → 18)
        alt_etiket_frame = tk.Frame(frame, bg='#E8EAF6')
        alt_etiket_frame.pack(fill="x", side="bottom", pady=(5, 1))

        # Üç öğeyi yan yana göstermek için grid kullan
        alt_etiket_frame.columnconfigure(0, weight=1, uniform="etiket")
        alt_etiket_frame.columnconfigure(1, weight=1, uniform="etiket")

        # Yarının Başlangıç Kasası etiketi - yeşil - yayılmış
        self.c_kalan_toplam_label = tk.Label(alt_etiket_frame, text="Yarının Başlangıç Kasası: 0 TL",
                                             font=("Arial", 16, "bold"), bg='#4CAF50', fg='white', pady=22, padx=8)
        self.c_kalan_toplam_label.grid(row=0, column=0, sticky='nsew', padx=(0, 1), pady=1)

        # Ayrılan Para etiketi - turuncu - yayılmış
        self.c_ayrilan_toplam_label = tk.Label(alt_etiket_frame, text="Ayrılan Para: 0 TL",
                                               font=("Arial", 16, "bold"), bg='#FF9800', fg='white', pady=22, padx=8)
        self.c_ayrilan_toplam_label.grid(row=0, column=1, sticky='nsew', padx=(1, 0), pady=1)

        # Ayrilan adet toplam - gizli (kod uyumlulugu icin)
        self.c_ayrilan_adet_toplam_label = tk.Label(frame, text="0")

        # Ust kisim - Tablo (toplam satiri pack edildikten sonra)
        tablo_frame = tk.Frame(frame, bg='#E8EAF6')
        tablo_frame.pack(fill="both", expand=True)

        # Grid sütun genişlikleri (başlık ve satırlar için ortak) - büyütüldü
        # 0:Küpür, 1:Sayım, 2:Kalan, 3:<buton, 4:slider, 5:>buton, 6:Ayrln, 7:Tutar
        col_widths = [70, 50, 50, 30, 140, 30, 50, 80]

        # Tablo basligi - grid ile hizalı
        header = tk.Frame(tablo_frame, bg='#3F51B5')
        header.pack(fill="x")

        for i, w in enumerate(col_widths):
            header.columnconfigure(i, minsize=w)

        tk.Label(header, text="Küpür", font=("Arial", 13, "bold"), bg='#3F51B5', fg='white', anchor='center').grid(row=0, column=0, sticky='ew', padx=2, pady=6)
        tk.Label(header, text="Sayım", font=("Arial", 13, "bold"), bg='#3F51B5', fg='white', anchor='center').grid(row=0, column=1, sticky='ew', padx=2, pady=6)
        tk.Label(header, text="Kalan", font=("Arial", 13, "bold"), bg='#4CAF50', fg='white', anchor='center').grid(row=0, column=2, sticky='ew', padx=2, pady=6)
        # AYIRMA başlığı 3 sütunu kapsar (< buton, slider, > buton)
        tk.Label(header, text="AYIRMA", font=("Arial", 13, "bold"), bg='#FF9800', fg='white', anchor='center').grid(row=0, column=3, columnspan=3, sticky='ew', padx=2, pady=6)
        tk.Label(header, text="Ayrln", font=("Arial", 13, "bold"), bg='#E65100', fg='white', anchor='center').grid(row=0, column=6, sticky='ew', padx=2, pady=6)
        tk.Label(header, text="Tutar", font=("Arial", 13, "bold"), bg='#E65100', fg='white', anchor='center').grid(row=0, column=7, sticky='ew', padx=2, pady=6)

        # Kupur listesi - scroll olmadan doğrudan frame
        self.kasa_scrollable = tk.Frame(tablo_frame, bg='#E8EAF6')
        self.kasa_scrollable.pack(fill="both", expand=True)

        # Degiskenler
        self.c_slider_vars = {}
        self.c_kalan_labels = {}
        self.c_ayrilan_labels = {}
        self.c_ayrilan_tl_labels = {}
        self.c_sayim_labels = {}
        self.c_sliders = {}

        # Kupur satirlari - grid ile hizalı
        for i, kupur in enumerate(self.KUPURLER):
            if self.kupur_aktif_mi(kupur["deger"]):
                deger = kupur["deger"]
                row_bg = '#F5F5F5' if i % 2 == 0 else '#ECEFF1'

                row = tk.Frame(self.kasa_scrollable, bg=row_bg)
                row.pack(fill="x", pady=1)

                # Grid sütun genişlikleri
                for col_i, w in enumerate(col_widths):
                    row.columnconfigure(col_i, minsize=w)

                # Kupur adi
                tk.Label(row, text=kupur["aciklama"], font=("Arial", 12, "bold"),
                        bg=row_bg, fg='#333', anchor='w').grid(row=0, column=0, sticky='ew', padx=1)

                # Sayim adedi
                sayim_adet = 0
                if deger in self.sayim_vars:
                    try:
                        sayim_adet = int(self.sayim_vars[deger].get() or 0)
                    except ValueError:
                        sayim_adet = 0

                sayim_label = tk.Label(row, text=str(sayim_adet), font=("Arial", 12, "bold"),
                                      bg='#E3F2FD', fg='#1565C0', anchor='center')
                sayim_label.grid(row=0, column=1, sticky='ew', padx=1)
                self.c_sayim_labels[deger] = sayim_label

                # Kalan label (yesil)
                kalan_label = tk.Label(row, text=str(sayim_adet), font=("Arial", 12, "bold"),
                                      bg='#C8E6C9', fg='#2E7D32', anchor='center')
                kalan_label.grid(row=0, column=2, sticky='ew', padx=1)
                self.c_kalan_labels[deger] = kalan_label

                # Slider degiskeni
                slider_var = tk.IntVar(value=0)
                self.c_slider_vars[deger] = slider_var

                # Sol buton <
                btn_sol = tk.Button(row, text="<", font=("Arial", 11, "bold"), bg='#4CAF50', fg='white',
                         width=2, command=lambda d=deger: self.c_kalana_ekle(d))
                btn_sol.grid(row=0, column=3, padx=1)

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
                slider.grid(row=0, column=4, padx=1)
                self.c_sliders[deger] = slider

                # Sag buton >
                btn_sag = tk.Button(row, text=">", font=("Arial", 11, "bold"), bg='#FF9800', fg='white',
                         width=2, command=lambda d=deger: self.c_ayrilana_ekle(d))
                btn_sag.grid(row=0, column=5, padx=1)

                # Ayrilan adet
                ayrilan_label = tk.Label(row, text="0", font=("Arial", 12, "bold"),
                                        bg='#FFE0B2', fg='#E65100', anchor='center')
                ayrilan_label.grid(row=0, column=6, sticky='ew', padx=1)
                self.c_ayrilan_labels[deger] = ayrilan_label

                # Ayrilan tutar TL
                ayrilan_tl_label = tk.Label(row, text="0 TL", font=("Arial", 12, "bold"),
                                           bg='#FFCCBC', fg='#BF360C', anchor='e')
                ayrilan_tl_label.grid(row=0, column=7, sticky='ew', padx=1)
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
        # 4 buton - eşit genişlikte
        butonlar = [
            ("8) Artı/Eksi Sebepler", '#C62828', self.arti_eksi_popup_ac),
            ("9) WhatsApp ve Email Gönder", '#25D366', self.rapor_gonder_tumu),
            ("10) Yazdır", '#2196F3', self.ayrilan_cikti_yazdir),
            ("11) Kaydet", '#1565C0', self.kaydet),
        ]

        # 4 sutun esit genislikte
        for i in range(4):
            self.butonlar_frame.columnconfigure(i, weight=1, uniform="butonkolon")

        buton_yuk = self.get_buton_yuksekligi()
        punto = self.get_punto()

        for i, (text, color, command) in enumerate(butonlar):
            btn = tk.Button(
                self.butonlar_frame,
                text=text,
                font=("Arial", punto + 1, "bold"),
                bg=color,
                fg='white',
                activebackground=color,
                cursor='hand2',
                bd=2,
                relief='raised',
                height=buton_yuk,
                command=command
            )
            btn.grid(row=0, column=i, sticky='ew', padx=2, pady=2)

    def ayrilan_cikti_yazdir(self):
        """Kasa raporu yazdır - ESC/POS termal yazıcı"""
        if not YENI_MODULLER_YUKLENDI:
            messagebox.showwarning("Uyarı", "Yazıcı modülü yüklenmedi")
            return

        try:
            # Kasa verilerini topla
            kasa_verileri = self.kasa_verilerini_topla()

            # Yazıcı oluştur
            yazici = KasaYazici(self.ayarlar)

            # Gün sonu raporu oluştur (metin - yedek için)
            rapor = yazici.gun_sonu_raporu_olustur(kasa_verileri)

            # Yazıcı seçim penceresi aç
            def yazdir_callback(secilen_yazici):
                yazici.yazici_adi = secilen_yazici
                # ESC/POS RAW modu kullan (Notepad değil!)
                if yazici.kasa_raporu_yazdir(kasa_verileri, secilen_yazici):
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
        self.tutarsizlik_penceresi.title("8) ARTI/EKSI TUTARSIZLIKLARI BUL")
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
            text=f"8) TUTARSIZLIK KONTROL LISTESI - Fark: {fark:,.2f} TL",
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

        # Küpür dökümü oluştur
        kupurler_metin = ""
        for kupur in self.KUPURLER:
            deger = kupur["deger"]
            adet = kalan_kupurler.get(str(deger), 0)
            if adet > 0:
                tutar = adet * deger
                kupurler_metin += f"  {kupur['ad']}: {adet} adet = {tutar:,.0f} TL\n"

        messagebox.showinfo(
            "ERTESİ GÜN KASASI BELİRLENDİ",
            f"İŞLEM BAŞARILI!\n"
            f"{'='*40}\n\n"
            f"Yarının başlangıç kasası belirlendi.\n\n"
            f"TOPLAM: {kalan_toplam:,.2f} TL\n\n"
            f"KÜPÜR DÖKÜMÜ:\n{kupurler_metin}\n"
            f"{'='*40}\n"
            f"Bu tutar yarın program açıldığında\n"
            f"başlangıç kasası olarak gelecektir."
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

        # Küpür dökümü oluştur
        kupurler_metin = ""
        for kupur in self.KUPURLER:
            deger = kupur["deger"]
            adet = ayrilan_kupurler.get(str(deger), 0)
            if adet > 0:
                tutar = adet * deger
                kupurler_metin += f"  {kupur['ad']}: {adet} adet = {tutar:,.0f} TL\n"

        # Uyarı penceresi göster
        messagebox.showinfo(
            "AYRILAN PARA BELİRLENDİ",
            f"İŞLEM BAŞARILI!\n"
            f"{'='*40}\n\n"
            f"Kasadan ayrılacak para belirlendi.\n\n"
            f"TOPLAM: {ayrilan_toplam:,.2f} TL\n\n"
            f"KÜPÜR DÖKÜMÜ:\n{kupurler_metin}\n"
            f"{'='*40}\n"
            f"Yazıcı bağlıysa etiket basılacak."
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

    def birlesik_masraf_silinen_alinan_bolumu_olustur(self):
        """4) DÜZELTMELER - 4a, 4b, 4c alt alta, her biri 2 satır"""
        punto = self.get_punto()
        hucre_pad = self.get_hucre_padding()
        bolum_pad = self.get_bolum_padding()

        # Ana LabelFrame
        ana_frame = tk.LabelFrame(
            self.b_bolumu_frame,
            text="4) DÜZELTMELER",
            font=("Arial", punto, "bold"),
            bg='#ECEFF1',
            fg='#37474F',
            padx=bolum_pad,
            pady=bolum_pad
        )
        ana_frame.pack(fill="both", expand=True, padx=1, pady=1)

        # ===== 4a) GİRİLMEMİŞ MASRAFLAR =====
        masraf_header = tk.Frame(ana_frame, bg=self.section_colors['masraf'])
        masraf_header.pack(fill="x", pady=(0, 1))
        tk.Label(masraf_header, text="4a) Girilmemiş Masraf", font=("Arial", punto - 2, "bold"),
                bg=self.section_colors['masraf'], fg='#E65100').pack(side="left", padx=hucre_pad)
        self.masraf_toplam_label = tk.Label(masraf_header, text="0,00", font=("Arial", punto - 2, "bold"),
                bg=self.section_colors['masraf'], fg='#E65100')
        self.masraf_toplam_label.pack(side="right", padx=hucre_pad)

        # Masraf satırları (3 satır ALT ALTA)
        for i in range(3):
            masraf_row = tk.Frame(ana_frame, bg=self.section_colors['masraf'])
            masraf_row.pack(fill="x", pady=1)
            tk.Label(masraf_row, text=f"M{i+1}:", font=("Arial", punto - 2),
                    bg=self.section_colors['masraf'], fg=self.detay_fg).pack(side="left", padx=hucre_pad)
            tutar_var = tk.StringVar(value="0")
            aciklama_var = tk.StringVar(value="")
            self.masraf_vars.append((tutar_var, aciklama_var))
            tutar_entry = tk.Entry(masraf_row, textvariable=tutar_var, font=("Arial", punto - 2), width=8, justify='right')
            tutar_entry.pack(side="left", padx=hucre_pad)
            tutar_entry.bind('<FocusOut>', lambda e, v=tutar_var: self.masraf_uyari_kontrol(v))
            tutar_entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
            tutar_entry.bind('<FocusIn>', self.entry_fokus_secim)
            tutar_entry.bind('<Tab>', self.tab_sonraki_entry)
            tutar_entry.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
            self.tab_order_entries.append(tutar_entry)
            aciklama_entry = tk.Entry(masraf_row, textvariable=aciklama_var, font=("Arial", punto - 3), width=12, takefocus=False)
            aciklama_entry.pack(side="left", padx=hucre_pad, fill="x", expand=True)

        # ===== 4b) SİLİNEN REÇETE ETKİSİ =====
        silinen_header = tk.Frame(ana_frame, bg=self.section_colors['silinen'])
        silinen_header.pack(fill="x", pady=(2, 1))
        tk.Label(silinen_header, text="4b) Silinen Reçete Etkisi", font=("Arial", punto - 2, "bold"),
                bg=self.section_colors['silinen'], fg='#AD1457').pack(side="left", padx=hucre_pad)
        self.silinen_toplam_label = tk.Label(silinen_header, text="0,00", font=("Arial", punto - 2, "bold"),
                bg=self.section_colors['silinen'], fg='#AD1457')
        self.silinen_toplam_label.pack(side="right", padx=hucre_pad)

        # Silinen satırları (3 satır ALT ALTA)
        for i in range(3):
            silinen_row = tk.Frame(ana_frame, bg=self.section_colors['silinen'])
            silinen_row.pack(fill="x", pady=1)
            tk.Label(silinen_row, text=f"S{i+1}:", font=("Arial", punto - 2),
                    bg=self.section_colors['silinen'], fg=self.detay_fg).pack(side="left", padx=hucre_pad)
            tutar_var = tk.StringVar(value="0")
            aciklama_var = tk.StringVar(value="")
            self.silinen_vars.append((tutar_var, aciklama_var))
            tutar_entry = tk.Entry(silinen_row, textvariable=tutar_var, font=("Arial", punto - 2), width=8, justify='right')
            tutar_entry.pack(side="left", padx=hucre_pad)
            tutar_entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
            tutar_entry.bind('<FocusIn>', self.entry_fokus_secim)
            tutar_entry.bind('<Tab>', self.tab_sonraki_entry)
            tutar_entry.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
            self.tab_order_entries.append(tutar_entry)
            aciklama_entry = tk.Entry(silinen_row, textvariable=aciklama_var, font=("Arial", punto - 3), width=12, takefocus=False)
            aciklama_entry.pack(side="left", padx=hucre_pad, fill="x", expand=True)

        # ===== 4c) GÜN İÇİ ALINMIŞ PARALAR =====
        alinan_header = tk.Frame(ana_frame, bg=self.section_colors['alinan'])
        alinan_header.pack(fill="x", pady=(2, 1))
        tk.Label(alinan_header, text="4c) Gün İçi Alınmış Paralar", font=("Arial", punto - 2, "bold"),
                bg=self.section_colors['alinan'], fg='#C62828').pack(side="left", padx=hucre_pad)
        self.alinan_toplam_label = tk.Label(alinan_header, text="0,00", font=("Arial", punto - 2, "bold"),
                bg=self.section_colors['alinan'], fg='#C62828')
        self.alinan_toplam_label.pack(side="right", padx=hucre_pad)

        # Alınan satırları (3 satır ALT ALTA)
        for i in range(3):
            alinan_row = tk.Frame(ana_frame, bg=self.section_colors['alinan'])
            alinan_row.pack(fill="x", pady=1)
            tk.Label(alinan_row, text=f"A{i+1}:", font=("Arial", punto - 2),
                    bg=self.section_colors['alinan'], fg=self.detay_fg).pack(side="left", padx=hucre_pad)
            tutar_var = tk.StringVar(value="0")
            aciklama_var = tk.StringVar(value="")
            self.gun_ici_alinan_vars.append((tutar_var, aciklama_var))
            tutar_entry = tk.Entry(alinan_row, textvariable=tutar_var, font=("Arial", punto - 2), width=8, justify='right')
            tutar_entry.pack(side="left", padx=hucre_pad)
            tutar_entry.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
            tutar_entry.bind('<FocusIn>', self.entry_fokus_secim)
            tutar_entry.bind('<Tab>', self.tab_sonraki_entry)
            tutar_entry.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
            self.tab_order_entries.append(tutar_entry)
            aciklama_entry = tk.Entry(alinan_row, textvariable=aciklama_var, font=("Arial", punto - 3), width=12, takefocus=False)
            aciklama_entry.pack(side="left", padx=hucre_pad, fill="x", expand=True)

        # ===== DÜZELTİLMİŞ NAKİT TOPLAMI - en dibe dayalı =====
        duzeltme_frame = tk.Frame(ana_frame, bg='#303F9F')
        duzeltme_frame.pack(fill="x", side="bottom", pady=(3, 0))

        # Düzeltilmiş Nakit Toplam satırı
        tk.Label(duzeltme_frame, text="DÜZELTİLMİŞ NAKİT:", font=("Arial", punto - 1, "bold"),
                bg='#303F9F', fg='white').pack(side="left", padx=hucre_pad, pady=hucre_pad)
        self.c_duzeltilmis_nakit_label = tk.Label(duzeltme_frame, text="0,00", font=("Arial", punto, "bold"),
                bg='#303F9F', fg='#FFEB3B')
        self.c_duzeltilmis_nakit_label.pack(side="right", padx=hucre_pad, pady=hucre_pad)

        # Gizli label'lar (hesaplari_guncelle için)
        self.c_nakit_toplam_label = tk.Label(ana_frame, text="0")
        self.c_masraf_label = tk.Label(ana_frame, text="0")
        self.c_silinen_label = tk.Label(ana_frame, text="0")
        self.c_alinan_label = tk.Label(ana_frame, text="0")

    def masraf_bolumu_olustur(self):
        """4) B Bolumu - Islenmemis masraflar - ESKİ FONKSİYON (kullanılmıyor)"""
        pass  # Artık birlesik_masraf_silinen_alinan_bolumu_olustur kullanılıyor

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
        """5) B Bolumu - Silinen recete etkileri - ESKİ FONKSİYON (kullanılmıyor)"""
        pass  # Artık birlesik_masraf_silinen_alinan_bolumu_olustur kullanılıyor

    def gun_ici_alinan_bolumu_olustur(self):
        """6) B Bolumu - Gun ici alinan paralar - ESKİ FONKSİYON (kullanılmıyor)"""
        pass  # Artık birlesik_masraf_silinen_alinan_bolumu_olustur kullanılıyor

    def b_ozet_bolumu_olustur(self):
        """B Bölümü özet - Formül açıklaması (SON GENEL TOPLAM artık A bölümünde yan yana)"""
        punto = self.get_punto()
        hucre_pad = self.get_hucre_padding()

        frame = tk.Frame(
            self.b_bolumu_frame,
            bg=self.section_colors['ozet'],
            padx=hucre_pad,
            pady=hucre_pad
        )
        frame.pack(fill="x", pady=2)

        # Formül açıklaması
        tk.Label(
            frame,
            text="SON GENEL = GENEL TOPLAM + Masraf + Silinen + Alınan",
            font=("Arial", punto - 2, "italic"),
            bg=self.section_colors['ozet'],
            fg='#666'
        ).pack(anchor='center')

    def botanik_bolumu_olustur(self):
        """8) Botanik EOS verileri"""
        punto = self.get_punto()
        hucre_pad = self.get_hucre_padding()
        bolum_pad = self.get_bolum_padding()

        frame = tk.LabelFrame(
            self.botanik_frame,
            text="5) BOTANİK EOS VERİLERİ",
            font=("Arial", punto, "bold"),
            bg=self.section_colors['botanik'],
            fg='#F57F17',
            padx=bolum_pad,
            pady=bolum_pad
        )
        frame.pack(fill="both", expand=True, pady=1)

        # Botanik Nakit
        nakit_frame = tk.Frame(frame, bg=self.section_colors['botanik'])
        nakit_frame.pack(fill="x", pady=1)
        tk.Label(nakit_frame, text="Nakit:", font=("Arial", punto + 1, "bold"),
                bg=self.section_colors['botanik'], width=6, anchor='w').pack(side="left")
        entry1 = tk.Entry(nakit_frame, textvariable=self.botanik_nakit_var, font=("Arial", punto + 1), width=12, justify='right')
        entry1.pack(side="right", padx=hucre_pad)
        entry1.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
        entry1.bind('<FocusIn>', self.entry_fokus_secim)
        entry1.bind('<Tab>', self.tab_sonraki_entry)
        entry1.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
        self.tab_order_entries.append(entry1)

        # Botanik POS
        pos_frame = tk.Frame(frame, bg=self.section_colors['botanik'])
        pos_frame.pack(fill="x", pady=1)
        tk.Label(pos_frame, text="POS:", font=("Arial", punto + 1, "bold"),
                bg=self.section_colors['botanik'], width=6, anchor='w').pack(side="left")
        entry2 = tk.Entry(pos_frame, textvariable=self.botanik_pos_var, font=("Arial", punto + 1), width=12, justify='right')
        entry2.pack(side="right", padx=hucre_pad)
        entry2.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
        entry2.bind('<FocusIn>', self.entry_fokus_secim)
        entry2.bind('<Tab>', self.tab_sonraki_entry)
        entry2.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
        self.tab_order_entries.append(entry2)

        # Botanik IBAN
        iban_frame = tk.Frame(frame, bg=self.section_colors['botanik'])
        iban_frame.pack(fill="x", pady=1)
        tk.Label(iban_frame, text="IBAN:", font=("Arial", punto + 1, "bold"),
                bg=self.section_colors['botanik'], width=6, anchor='w').pack(side="left")
        entry3 = tk.Entry(iban_frame, textvariable=self.botanik_iban_var, font=("Arial", punto + 1), width=12, justify='right')
        entry3.pack(side="right", padx=hucre_pad)
        entry3.bind('<KeyRelease>', lambda e: self.hesaplari_guncelle())
        entry3.bind('<FocusIn>', self.entry_fokus_secim)
        entry3.bind('<Tab>', self.tab_sonraki_entry)
        entry3.bind('<Shift-Tab>', self.shift_tab_onceki_entry)
        self.tab_order_entries.append(entry3)

        # Botanik Genel Toplam
        bot_toplam_frame = tk.Frame(frame, bg='#F57F17')
        bot_toplam_frame.pack(fill="x", pady=(2, 0))
        tk.Label(bot_toplam_frame, text="BOTANIK TOPLAM:", font=("Arial", punto + 1, "bold"),
                bg='#F57F17', fg='white').pack(side="left", padx=hucre_pad, pady=hucre_pad)
        self.botanik_toplam_label = tk.Label(bot_toplam_frame, text="0,00", font=("Arial", punto + 2, "bold"),
                                             bg='#F57F17', fg='white')
        self.botanik_toplam_label.pack(side="right", padx=hucre_pad, pady=hucre_pad)

        # Botanik'ten Veri Çek butonu
        yenile_btn = tk.Button(
            frame,
            text="Botanik'ten Çek",
            font=("Arial", punto, "bold"),
            bg='#4CAF50',
            fg='white',
            cursor='hand2',
            command=self.botanik_verilerini_yenile
        )
        yenile_btn.pack(fill="x", pady=(hucre_pad, 0))

    def duzeltilmis_nakit_bolumu_olustur(self):
        """7) Duzeltilmis nakit hesaplama bolumu - ESKİ FONKSİYON (kullanılmıyor)"""
        pass  # Artık birlesik_masraf_silinen_alinan_bolumu_olustur kullanılıyor

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

    def ertesi_gun_kasasini_botanige_isle(self):
        """Başlangıç Kasası verilerini Botanik'e aktar

        Eğer Kaydet'e basılmışsa (1. Başlangıç Kasası dolu ise) → oradan aktar
        Eğer Kaydet'e basılmamışsa ama 7) tabloda KALAN var ise → KALAN'dan aktar
        """
        try:
            aktarilacak_kupurler = {}
            kaynak = ""

            # Önce 1) Başlangıç Kasası bölümündeki değerleri kontrol et
            baslangic_toplam = 0
            if hasattr(self, 'baslangic_kupur_vars'):
                for deger in [200, 100, 50, 20, 10, 5, 1, 0.5]:
                    try:
                        if deger in self.baslangic_kupur_vars:
                            adet = int(self.baslangic_kupur_vars[deger].get() or 0)
                            if adet > 0:
                                aktarilacak_kupurler[deger] = adet
                                baslangic_toplam += adet * deger
                    except (ValueError, KeyError):
                        pass

            # Eğer Başlangıç Kasası'nda değer varsa oradan aktar
            if baslangic_toplam > 0:
                kaynak = "1) Başlangıç Kasası"
            else:
                # Başlangıç Kasası boşsa, 7) tablodaki KALAN sütunundan al
                aktarilacak_kupurler = {}
                if hasattr(self, 'c_slider_vars') and hasattr(self, 'sayim_vars'):
                    for deger in [200, 100, 50, 20, 10, 5, 1, 0.5]:
                        try:
                            # Sayım adedi
                            sayim_adet = 0
                            if deger in self.sayim_vars:
                                sayim_adet = int(self.sayim_vars[deger].get() or 0)

                            # Ayrılan adedi
                            ayrilan_adet = 0
                            if deger in self.c_slider_vars:
                                ayrilan_adet = self.c_slider_vars[deger].get()

                            # Kalan = Sayım - Ayrılan
                            kalan_adet = sayim_adet - ayrilan_adet

                            if kalan_adet > 0:
                                aktarilacak_kupurler[deger] = kalan_adet
                        except (ValueError, KeyError):
                            pass
                kaynak = "7) Ertesi Gün Kasası / Ayrılan Para tablosu (KALAN sütunu)"

            if not aktarilacak_kupurler:
                messagebox.showwarning(
                    "Uyarı",
                    "Aktarılacak değer bulunamadı!\n\n"
                    "Lütfen önce:\n"
                    "• Kaydet'e basarak başlangıç kasasını oluşturun, veya\n"
                    "• 7) tablosunda KALAN sütununda değer olduğundan emin olun."
                )
                return

            # Toplam hesapla
            toplam = sum(k * v for k, v in aktarilacak_kupurler.items())

            # Önce kullanıcıya bilgi ver
            sonuc = messagebox.askokcancel(
                "Botanik'e Başlangıç Kasası Verisi Aktar",
                f"Bu işlem, {kaynak} bölümündeki değerleri\n"
                f"Botanik 'Başlangıç Kasası' penceresine yazacak ve kaydedecektir.\n\n"
                f"Aktarılacak Toplam: {toplam:,.2f} TL\n\n"
                f"⚠️ Botanik programında 'Başlangıç Kasası' sayfasını açtığınızdan emin olun!\n\n"
                "Devam etmek istiyor musunuz?"
            )

            if not sonuc:
                return

            # Botanik'e yaz
            from botanik_veri_cek import botanik_baslangic_kasasina_yaz
            basarili, mesaj = botanik_baslangic_kasasina_yaz(aktarilacak_kupurler)

            if basarili:
                messagebox.showinfo("Başarılı", mesaj)
            else:
                messagebox.showerror("Hata", mesaj)

        except ImportError as e:
            messagebox.showerror("Hata", f"Botanik modülü yüklenemedi: {e}")
        except Exception as e:
            logger.error(f"Botanik'e işleme hatası: {e}")
            messagebox.showerror("Hata", f"İşlem hatası: {e}")

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
        # API modu kontrolü (Terminal veya Ana makine API modu)
        if self.api_client:
            # API client var, bağlantı testi yap
            success, _ = self.api_client.baglanti_test()
            if not success:
                messagebox.showerror("Hata", "API sunucusuna bağlantı yok!\nProgram yeniden başlatılmalı.")
                return
        elif self.cursor is None or self.conn is None:
            # API yok ve yerel DB de yok
            messagebox.showerror("Hata", "Veritabanı bağlantısı kurulamadı!\nProgram yeniden başlatılmalı.")
            return

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
                "manuel_baslangic": {
                    "aktif": self.manuel_baslangic_aktif,
                    "tutar": self.manuel_baslangic_tutar if self.manuel_baslangic_aktif else 0,
                    "aciklama": self.manuel_baslangic_aciklama if self.manuel_baslangic_aktif else ""
                }
            }

            # Manuel başlangıç değerleri
            manuel_tutar = self.manuel_baslangic_tutar if self.manuel_baslangic_aktif else 0
            manuel_aciklama = self.manuel_baslangic_aciklama if self.manuel_baslangic_aktif else ""

            # API modu (Terminal veya Ana makine) - API üzerinden kaydet
            if self.api_client:
                api_data = {
                    'tarih': tarih,
                    'saat': saat,
                    'baslangic_kasasi': baslangic_toplam,
                    'baslangic_kupurler_json': json.dumps(baslangic_kupurler, ensure_ascii=False),
                    'sayim_toplam': nakit_toplam,
                    'sayim_kupurler_json': json.dumps(sayim_kupurler, ensure_ascii=False),
                    'pos_toplam': pos_toplam,
                    'pos_detay_json': json.dumps([self.sayi_al(v) for v in self.pos_vars], ensure_ascii=False),
                    'iban_toplam': iban_toplam,
                    'iban_detay_json': json.dumps([self.sayi_al(v) for v in self.iban_vars], ensure_ascii=False),
                    'masraf_toplam': masraf_toplam,
                    'masraf_detay_json': json.dumps([(self.sayi_al(t), a.get()) for t, a in self.masraf_vars], ensure_ascii=False),
                    'silinen_etki_toplam': silinen_toplam,
                    'silinen_detay_json': json.dumps([(self.sayi_al(t), a.get()) for t, a in self.silinen_vars], ensure_ascii=False),
                    'alinan_para_toplam': alinan_toplam,
                    'alinan_detay_json': json.dumps([(self.sayi_al(t), a.get()) for t, a in self.gun_ici_alinan_vars], ensure_ascii=False),
                    'nakit_toplam': nakit_toplam,
                    'genel_toplam': genel_toplam,
                    'son_genel_toplam': son_genel_toplam,
                    'botanik_nakit': botanik_nakit,
                    'botanik_pos': botanik_pos,
                    'botanik_iban': botanik_iban,
                    'botanik_genel_toplam': botanik_toplam,
                    'fark': fark,
                    'ertesi_gun_kasasi': ertesi_gun_kasasi,
                    'ertesi_gun_kupurler_json': json.dumps(ertesi_gun_kupurler, ensure_ascii=False),
                    'ayrilan_para': ayrilan_para,
                    'ayrilan_kupurler_json': json.dumps(ayrilan_kupurler, ensure_ascii=False),
                    'manuel_baslangic_tutar': manuel_tutar,
                    'manuel_baslangic_aciklama': manuel_aciklama,
                    'detay_json': json.dumps(detay, ensure_ascii=False)
                }
                success, result = self.api_client.kasa_kaydet(api_data)
                if not success:
                    # Detaylı hata mesajı
                    if isinstance(result, dict):
                        hata_msg = result.get('error', str(result))
                        detay = result.get('detay', '')
                        if detay:
                            hata_msg += f"\n\nDetay:\n{detay[:500]}"
                    else:
                        hata_msg = str(result)
                    messagebox.showerror("API Hatası", f"Ana makineye kaydedilemedi!\n\n{hata_msg}")
                    logger.error(f"API kaydetme hatası: {result}")
                    return
                logger.info(f"Kasa verisi API üzerinden kaydedildi - {tarih}")
            else:
                # Fallback: API yoksa yerel veritabanına kaydet
                self.cursor.execute('''
                    INSERT INTO kasa_kapatma (
                        tarih, saat, baslangic_kasasi, baslangic_kupurler_json,
                        sayim_toplam, pos_toplam, iban_toplam,
                        masraf_toplam, silinen_etki_toplam, gun_ici_alinan_toplam,
                        nakit_toplam, genel_toplam, son_genel_toplam,
                        botanik_nakit, botanik_pos, botanik_iban, botanik_genel_toplam,
                        fark, ertesi_gun_kasasi, ertesi_gun_kupurler_json,
                        ayrilan_para, ayrilan_kupurler_json,
                        manuel_baslangic_tutar, manuel_baslangic_aciklama,
                        detay_json, olusturma_zamani
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tarih, saat, baslangic_toplam, json.dumps(baslangic_kupurler, ensure_ascii=False),
                    nakit_toplam, pos_toplam, iban_toplam,
                    masraf_toplam, silinen_toplam, alinan_toplam,
                    nakit_toplam, genel_toplam, son_genel_toplam,
                    botanik_nakit, botanik_pos, botanik_iban, botanik_toplam,
                    fark, ertesi_gun_kasasi, json.dumps(ertesi_gun_kupurler, ensure_ascii=False),
                    ayrilan_para, json.dumps(ayrilan_kupurler, ensure_ascii=False),
                    manuel_tutar, manuel_aciklama,
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

            # Başarılı kayıt sonrası formu temizle (onay sormadan)
            self.temizle_onaysiz()

        except Exception as e:
            logger.error(f"Kasa kaydetme hatası: {e}")
            messagebox.showerror("Hata", f"Kaydetme hatasi: {e}")

    def temizle(self):
        """Tüm alanları temizle (onay ile)"""
        if not messagebox.askyesno("Onay", "Tum alanlari temizlemek istiyor musunuz?"):
            return
        self.temizle_onaysiz()

    def temizle_onaysiz(self):
        """Tüm alanları temizle (onay sormadan - kayıt sonrası için)"""
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

        # Manuel başlangıç kasasını sıfırla
        self.manuel_baslangic_aktif = False
        self.manuel_baslangic_tutar = 0
        self.manuel_baslangic_aciklama = ""
        if hasattr(self, 'manuel_baslangic_btn'):
            self.manuel_baslangic_btn.config(bg='#FFE082', fg='#E65100', text="✏ Elle")

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

        # kasa_config.json'dan mevcut ayarları oku
        ag_config = {}
        if KASA_API_MODULU_YUKLENDI:
            ag_config = config_yukle()

        # Mevcut mod bilgisi
        mevcut_mod = ag_config.get("makine_tipi", "standalone")
        mod_aciklama = {
            "ana_makine": "Ana Makine (Sunucu)",
            "terminal": "Terminal (Client)",
            "standalone": "Bağımsız Çalışma"
        }

        mod_frame = tk.LabelFrame(ag_tab, text="Çalışma Modu (Kurulumda Belirlendi)", font=("Arial", 10, "bold"),
                                  bg='#FAFAFA', padx=10, pady=10)
        mod_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(
            mod_frame,
            text=f"Mevcut Mod: {mod_aciklama.get(mevcut_mod, mevcut_mod)}",
            font=("Arial", 11, "bold"),
            bg='#FAFAFA',
            fg='#1565C0'
        ).pack(anchor='w', pady=5)

        tk.Label(
            mod_frame,
            text="(Mod değişikliği için programı yeniden kurmanız gerekir)",
            font=("Arial", 9),
            bg='#FAFAFA',
            fg='#666'
        ).pack(anchor='w')

        # Sunucu ayarları
        sunucu_frame = tk.LabelFrame(ag_tab, text="Sunucu Bağlantı Ayarları", font=("Arial", 10, "bold"),
                                     bg='#FAFAFA', padx=10, pady=10)
        sunucu_frame.pack(fill="x", padx=10, pady=10)

        ip_row = tk.Frame(sunucu_frame, bg='#FAFAFA')
        ip_row.pack(fill="x", pady=2)
        tk.Label(ip_row, text="Ana Makine IP:", font=("Arial", 10),
                bg='#FAFAFA', width=15, anchor='w').pack(side="left")
        # kasa_config.json'dan IP'yi oku
        config_ip = ag_config.get("ana_makine_ip", "127.0.0.1")
        ip_var = tk.StringVar(value=config_ip)
        ip_entry = tk.Entry(ip_row, textvariable=ip_var, font=("Arial", 10), width=20)
        ip_entry.pack(side="left", padx=10)
        # Terminal modunda düzenlenebilir, ana makinede salt okunur
        if mevcut_mod == "ana_makine":
            ip_entry.config(state='readonly')

        port_row = tk.Frame(sunucu_frame, bg='#FAFAFA')
        port_row.pack(fill="x", pady=2)
        tk.Label(port_row, text="Port:", font=("Arial", 10),
                bg='#FAFAFA', width=15, anchor='w').pack(side="left")
        config_port = ag_config.get("api_port", 5000)
        port_var = tk.StringVar(value=str(config_port))
        port_entry = tk.Entry(port_row, textvariable=port_var, font=("Arial", 10), width=10)
        port_entry.pack(side="left", padx=10)

        # Bu makinenin IP adresi (Ana makine için önemli)
        def get_local_ip():
            import socket
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except:
                return "Bulunamadı"

        ip_bilgi_frame = tk.LabelFrame(ag_tab, text="Bu Makinenin Bilgileri", font=("Arial", 10, "bold"),
                                       bg='#E8F5E9', padx=10, pady=10)
        ip_bilgi_frame.pack(fill="x", padx=10, pady=10)

        bu_ip = get_local_ip()
        tk.Label(
            ip_bilgi_frame,
            text=f"Bu makinenin IP adresi: {bu_ip}",
            font=("Arial", 11, "bold"),
            bg='#E8F5E9',
            fg='#2E7D32'
        ).pack(anchor='w')

        if mevcut_mod == "ana_makine":
            tk.Label(
                ip_bilgi_frame,
                text=f"Terminal kurulumunda bu IP'yi kullanın: {bu_ip}",
                font=("Arial", 10),
                bg='#E8F5E9',
                fg='#1565C0'
            ).pack(anchor='w', pady=5)

        # Bağlantı durumu göster
        durum_frame = tk.LabelFrame(ag_tab, text="Bağlantı Durumu", font=("Arial", 10, "bold"),
                                    bg='#FAFAFA', padx=10, pady=10)
        durum_frame.pack(fill="x", padx=10, pady=10)

        durum_label = tk.Label(durum_frame, text="Kontrol ediliyor...", font=("Arial", 10), bg='#FAFAFA')
        durum_label.pack(anchor='w')

        def baglanti_kontrol():
            if self.api_client:
                success, result = self.api_client.baglanti_test()
                if success:
                    durum_label.config(text="✓ API Sunucusuna bağlı", fg='green')
                else:
                    durum_label.config(text=f"✗ Bağlantı hatası: {result}", fg='red')
            else:
                durum_label.config(text="API client yok (yerel mod)", fg='orange')

        baglanti_kontrol()

        btn_frame = tk.Frame(durum_frame, bg='#FAFAFA')
        btn_frame.pack(fill='x', pady=5)

        tk.Button(btn_frame, text="Bağlantıyı Test Et", font=("Arial", 10, "bold"),
                  bg='#4CAF50', fg='white', padx=15, pady=5,
                  command=baglanti_kontrol).pack(side='left', padx=5)

        def detayli_test():
            import socket
            test_sonuc = []

            # 1. Localhost testi
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex(('127.0.0.1', config_port))
                sock.close()
                if result == 0:
                    test_sonuc.append("✓ Localhost:5000 - AÇIK")
                else:
                    test_sonuc.append("✗ Localhost:5000 - KAPALI")
            except Exception as e:
                test_sonuc.append(f"✗ Localhost hatası: {e}")

            # 2. API testi
            if self.api_client:
                success, result = self.api_client.baglanti_test()
                if success:
                    test_sonuc.append(f"✓ API Sunucusu - BAĞLANDI")
                    if isinstance(result, tuple) and len(result) > 1:
                        test_sonuc.append(f"  DB: {result[1].get('db_path', 'bilinmiyor')}")
                else:
                    test_sonuc.append(f"✗ API Hatası: {result}")

            # 3. Config bilgisi
            test_sonuc.append(f"\nConfig: {mevcut_mod}")
            test_sonuc.append(f"Hedef IP: {config_ip}:{config_port}")

            messagebox.showinfo("Bağlantı Testi", "\n".join(test_sonuc))

        tk.Button(btn_frame, text="Detaylı Test", font=("Arial", 10),
                  bg='#2196F3', fg='white', padx=15, pady=5,
                  command=detayli_test).pack(side='left', padx=5)

        # Tab 5: Rapor Ayarları
        rapor_tab = tk.Frame(notebook, bg='#FAFAFA')
        notebook.add(rapor_tab, text="Rapor Ayarları")

        # Rapor ayarları açıklama
        rapor_aciklama = tk.Label(
            rapor_tab,
            text="WhatsApp ve Yazıcı raporlarında hangi bilgilerin\ngörüneceğini ayrıntılı olarak ayarlayabilirsiniz.",
            font=("Arial", 10),
            bg='#FAFAFA',
            fg='#666',
            justify='center'
        )
        rapor_aciklama.pack(pady=20)

        # Rapor ayarları butonu
        def rapor_ayarlarini_ac():
            if YENI_MODULLER_YUKLENDI:
                pencere = RaporAyarlariPenceresi(ayar_pencere)
                pencere.goster()

        tk.Button(
            rapor_tab,
            text="Rapor Ayarlarını Düzenle",
            font=("Arial", 12, "bold"),
            bg='#1565C0',
            fg='white',
            padx=30,
            pady=15,
            cursor='hand2',
            command=rapor_ayarlarini_ac
        ).pack(pady=20)

        # Bilgi kutusu
        bilgi_frame = tk.LabelFrame(
            rapor_tab,
            text="Ayarlanabilir Bölümler",
            font=("Arial", 10, "bold"),
            bg='#E3F2FD',
            padx=10,
            pady=10
        )
        bilgi_frame.pack(fill="x", padx=20, pady=10)

        bilgiler = [
            "• Başlangıç kasası (toplam/detay)",
            "• Gün sonu nakit sayım (toplam/detay)",
            "• POS raporları ve toplamları",
            "• IBAN verileri ve toplamları",
            "• Sayım-Botanik özet tablosu",
            "• Masraf, silinen, alınan paralar",
            "• Ertesi gün kasası ve ayrılan para",
        ]

        for bilgi in bilgiler:
            tk.Label(
                bilgi_frame,
                text=bilgi,
                font=("Arial", 9),
                bg='#E3F2FD',
                anchor='w'
            ).pack(anchor='w', pady=1)

        # Tab 6: Görünüm Ayarları
        gorunum_tab = tk.Frame(notebook, bg='#FAFAFA')
        notebook.add(gorunum_tab, text="Görünüm")

        # Başlık
        tk.Label(
            gorunum_tab,
            text="Ekran Düzeni Ayarları",
            font=("Arial", 12, "bold"),
            bg='#FAFAFA'
        ).pack(pady=10)

        tk.Label(
            gorunum_tab,
            text="Programın ekrana sığması için boyutları ayarlayın.\nDaha fazla küpür seçildiğinde değerleri küçültebilirsiniz.",
            font=("Arial", 9),
            bg='#FAFAFA',
            fg='#666',
            justify='center'
        ).pack(pady=5)

        # Görünüm ayarları frame
        gorunum_frame = tk.Frame(gorunum_tab, bg='#FAFAFA')
        gorunum_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Görünüm değişkenleri
        varsayilan = self.varsayilan_gorunum_ayarlari()

        punto_var = tk.IntVar(value=self.ayarlar.get("punto_boyutu", varsayilan["punto_boyutu"]))
        baslik_var = tk.IntVar(value=self.ayarlar.get("baslik_yuksekligi", varsayilan["baslik_yuksekligi"]))
        buton_var = tk.IntVar(value=self.ayarlar.get("buton_yuksekligi", varsayilan["buton_yuksekligi"]))
        tablo_var = tk.IntVar(value=self.ayarlar.get("tablo_satir_yuksekligi", varsayilan["tablo_satir_yuksekligi"]))
        hucre_var = tk.IntVar(value=self.ayarlar.get("hucre_padding", varsayilan["hucre_padding"]))
        bolum_var = tk.IntVar(value=self.ayarlar.get("bolum_padding", varsayilan["bolum_padding"]))

        def ayar_satiri_olustur(parent, label_text, variable, min_val, max_val, aciklama):
            """Slider ile ayar satırı oluştur"""
            row = tk.Frame(parent, bg='#FAFAFA')
            row.pack(fill="x", pady=5)

            tk.Label(row, text=label_text, font=("Arial", 10, "bold"),
                    bg='#FAFAFA', width=20, anchor='w').pack(side="left")

            # Değer label
            deger_label = tk.Label(row, text=str(variable.get()), font=("Arial", 10, "bold"),
                                   bg='#E3F2FD', width=4)
            deger_label.pack(side="right", padx=5)

            # Slider
            def slider_degisti(val):
                variable.set(int(float(val)))
                deger_label.config(text=str(int(float(val))))

            slider = tk.Scale(row, from_=min_val, to=max_val, orient="horizontal",
                             variable=variable, command=slider_degisti,
                             length=150, showvalue=False, bg='#FAFAFA',
                             highlightthickness=0, troughcolor='#BBDEFB')
            slider.pack(side="right", padx=5)

            # Açıklama
            tk.Label(row, text=aciklama, font=("Arial", 8),
                    bg='#FAFAFA', fg='#888').pack(side="right", padx=10)

        # Ayar satırları
        ayar_satiri_olustur(gorunum_frame, "Yazı Boyutu:", punto_var, 9, 14, "9=Küçük, 14=Büyük")
        ayar_satiri_olustur(gorunum_frame, "Başlık Yüksekliği:", baslik_var, 70, 140, "70=Kısa, 140=Uzun")
        ayar_satiri_olustur(gorunum_frame, "Alt Buton Yüksekliği:", buton_var, 2, 5, "2=Kısa, 5=Uzun")
        ayar_satiri_olustur(gorunum_frame, "Tablo Satır Yüks.:", tablo_var, 20, 40, "20=Sıkışık, 40=Geniş")
        ayar_satiri_olustur(gorunum_frame, "Hücre İç Boşluğu:", hucre_var, 1, 8, "1=Yok, 8=Geniş")
        ayar_satiri_olustur(gorunum_frame, "Bölüm İç Boşluğu:", bolum_var, 2, 8, "2=Sıkışık, 8=Geniş")

        # Varsayılana dön butonu
        def varsayilana_don():
            vars = self.varsayilan_gorunum_ayarlari()
            punto_var.set(vars["punto_boyutu"])
            baslik_var.set(vars["baslik_yuksekligi"])
            buton_var.set(vars["buton_yuksekligi"])
            tablo_var.set(vars["tablo_satir_yuksekligi"])
            hucre_var.set(vars["hucre_padding"])
            bolum_var.set(vars["bolum_padding"])

        tk.Button(
            gorunum_frame,
            text="Varsayılana Dön",
            font=("Arial", 10),
            bg='#FF9800',
            fg='white',
            padx=15,
            pady=5,
            cursor='hand2',
            command=varsayilana_don
        ).pack(pady=15)

        # İpucu
        ipucu_frame = tk.LabelFrame(gorunum_tab, text="İpucu", font=("Arial", 9, "bold"),
                                    bg='#FFF3E0', padx=10, pady=5)
        ipucu_frame.pack(fill="x", padx=20, pady=5)

        tk.Label(
            ipucu_frame,
            text="Çok küpür seçildiğinde ekrana sığdırmak için:\n• Yazı boyutunu 9-10 yapın\n• Başlık yüksekliğini 70-80 yapın\n• Tablo satır yüksekliğini 20-24 yapın",
            font=("Arial", 9),
            bg='#FFF3E0',
            fg='#E65100',
            justify='left'
        ).pack(anchor='w')

        # Buton frame
        btn_frame = tk.Frame(ayar_pencere, bg='#FAFAFA')
        btn_frame.pack(fill="x", pady=10, padx=20)

        def kaydet(mesaj_goster=True):
            # Tüm ayarları güncelle
            self.ayarlar["aktif_kupurler"] = {k: v.get() for k, v in checkbox_vars.items()}
            try:
                self.ayarlar["kabul_edilebilir_fark"] = float(fark_var.get())
            except ValueError:
                self.ayarlar["kabul_edilebilir_fark"] = 10
            self.ayarlar["whatsapp_numara"] = whatsapp_var.get()
            self.ayarlar["yazici_adi"] = yazici_var.get()

            # IP ve Port değişikliklerini kasa_config.json'a kaydet (terminal modunda)
            if KASA_API_MODULU_YUKLENDI and mevcut_mod == "terminal":
                from kasa_config import config_kaydet
                yeni_config = ag_config.copy()
                yeni_config["ana_makine_ip"] = ip_var.get()
                try:
                    yeni_config["api_port"] = int(port_var.get())
                except ValueError:
                    yeni_config["api_port"] = 5000
                config_kaydet(yeni_config)
                logger.info(f"Ağ ayarları güncellendi: {ip_var.get()}:{port_var.get()}")

            # Görünüm ayarlarını kaydet
            self.ayarlar["punto_boyutu"] = punto_var.get()
            self.ayarlar["baslik_yuksekligi"] = baslik_var.get()
            self.ayarlar["buton_yuksekligi"] = buton_var.get()
            self.ayarlar["tablo_satir_yuksekligi"] = tablo_var.get()
            self.ayarlar["hucre_padding"] = hucre_var.get()
            self.ayarlar["bolum_padding"] = bolum_var.get()

            self.ayarlari_kaydet()
            if mesaj_goster:
                messagebox.showinfo("Kaydedildi", "Ayarlar kaydedildi!")

        def kaydet_ve_uygula():
            # Önce kaydet (mesaj göstermeden)
            kaydet(mesaj_goster=False)
            # Pencereyi kapat
            ayar_pencere.destroy()
            # Arayüzü yeniden oluştur (ayarlar zaten self.ayarlar'da güncel)
            self.arayuzu_yenile(dosyadan_yukle=False)
            messagebox.showinfo("Uygulandı", "Ayarlar kaydedildi ve uygulandı!")

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

    def arayuzu_yenile(self, dosyadan_yukle=True):
        """Arayüzü yeniden oluştur

        Args:
            dosyadan_yukle: True ise ayarları dosyadan yükle, False ise mevcut self.ayarlar kullan
        """
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
        self.tab_order_entries = []
        self.baslangic_entry_list = []

        # Manuel başlangıç kasasını sıfırla
        self.manuel_baslangic_aktif = False
        self.manuel_baslangic_tutar = 0
        self.manuel_baslangic_aciklama = ""

        # Ayarları yeniden yükle (sadece dosyadan_yukle=True ise)
        if dosyadan_yukle:
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

    def raporlar_goster(self):
        """Raporlama penceresini göster"""
        if YENI_MODULLER_YUKLENDI:
            raporlar = KasaRaporlamaPenceresi(self.root, self.cursor, self.conn)
            raporlar.goster()
        else:
            messagebox.showwarning("Uyarı", "Raporlama modülü yüklenmedi")

    def gecmis_goster(self):
        """Geçmiş kayıtları göster"""
        if YENI_MODULLER_YUKLENDI:
            # Yeni gelişmiş geçmiş penceresi - API client varsa geç (terminal ve ana makine)
            gecmis = KasaGecmisiPenceresi(
                self.root, self.cursor, self.conn,
                api_client=self.api_client  # Hem terminal hem ana makine API modunda
            )
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

    def whatsapp_rapor_gonder(self):
        """WhatsApp ile kasa raporu gönder (standart format)"""
        if not YENI_MODULLER_YUKLENDI:
            messagebox.showwarning("Uyari", "WhatsApp modulu yuklenemedi!")
            return

        # Kasa verilerini topla
        kasa_verileri = self.kasa_verilerini_topla()

        # WhatsApp penceresi aç (standart rapor)
        pencere = KasaWhatsAppPenceresi(self.root, self.ayarlar, kasa_verileri, ozellesmis=False)
        pencere.goster()

    def ozellesmis_whatsapp_rapor_gonder(self):
        """WhatsApp ile özelleşmiş kasa raporu gönder (Rapor Ayarları'na göre)"""
        if not YENI_MODULLER_YUKLENDI:
            messagebox.showwarning("Uyari", "WhatsApp modulu yuklenemedi!")
            return

        # Kasa verilerini topla
        kasa_verileri = self.kasa_verilerini_topla()

        # WhatsApp penceresi aç (özelleşmiş rapor)
        pencere = KasaWhatsAppPenceresi(self.root, self.ayarlar, kasa_verileri, ozellesmis=True)
        pencere.goster()

    def email_rapor_gonder(self):
        """E-posta ile kasa raporu gönder"""
        if not YENI_MODULLER_YUKLENDI:
            messagebox.showwarning("Uyari", "E-posta modulu yuklenemedi!")
            return

        # Kasa verilerini topla
        kasa_verileri = self.kasa_verilerini_topla()

        # E-posta penceresi aç
        pencere = KasaEmailPenceresi(self.root, kasa_verileri)
        pencere.goster()

    def yardim_goster(self):
        """Yardım/Kullanım kılavuzu penceresini göster"""
        if not YENI_MODULLER_YUKLENDI:
            messagebox.showwarning("Uyari", "Yardım modulu yuklenemedi!")
            return

        # Yardım penceresi aç
        pencere = KasaYardimPenceresi(self.root)
        pencere.goster()

    def kasa_verilerini_topla(self):
        """Mevcut kasa verilerini dict olarak topla"""
        # Başlangıç kasası ve küpür detayları
        baslangic = sum(int(v.get() or 0) * d for d, v in self.baslangic_kupur_vars.items())
        baslangic_kupurler = {}
        for deger, var in self.baslangic_kupur_vars.items():
            adet = int(var.get() or 0)
            if adet > 0:
                baslangic_kupurler[f"{deger} TL"] = adet

        # Sayım ve küpür detayları
        nakit = sum(int(v.get() or 0) * d for d, v in self.sayim_vars.items())
        nakit_kupurler = {}
        for deger, var in self.sayim_vars.items():
            adet = int(var.get() or 0)
            if adet > 0:
                nakit_kupurler[f"{deger} TL"] = adet

        # POS - Eczacı POS (ilk 4) ve Ingenico (sonraki 4) ayrı ayrı
        eczaci_pos_listesi = [self.sayi_al(v) for v in self.pos_vars[:4]]
        eczaci_pos_toplam = sum(eczaci_pos_listesi)

        ingenico_listesi = [self.sayi_al(v) for v in self.pos_vars[4:8]]
        ingenico_toplam = sum(ingenico_listesi)

        pos = eczaci_pos_toplam + ingenico_toplam
        pos_listesi = eczaci_pos_listesi + ingenico_listesi

        # IBAN (4 satır)
        iban_listesi = [self.sayi_al(v) for v in self.iban_vars]
        iban = sum(iban_listesi)

        # Masraf, Silinen, Alınan - hem toplam hem liste
        masraf = sum(self.sayi_al(t) for t, _ in self.masraf_vars)
        masraf_listesi = []
        for t, _ in self.masraf_vars:
            tutar = self.sayi_al(t)
            if tutar > 0:
                masraf_listesi.append(tutar)

        silinen = sum(self.sayi_al(t) for t, _ in self.silinen_vars)
        silinen_listesi = []
        for t, _ in self.silinen_vars:
            tutar = self.sayi_al(t)
            if tutar > 0:
                silinen_listesi.append(tutar)

        alinan = sum(self.sayi_al(t) for t, _ in self.gun_ici_alinan_vars)
        alinan_listesi = []
        for t, _ in self.gun_ici_alinan_vars:
            tutar = self.sayi_al(t)
            if tutar > 0:
                alinan_listesi.append(tutar)

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
        ertesi_gun_kupurler = {}
        if hasattr(self, 'c_slider_vars'):
            for deger, slider_var in self.c_slider_vars.items():
                try:
                    sayim_adet = int(self.sayim_vars.get(deger, tk.StringVar(value="0")).get() or 0)
                    ayrilan_adet = slider_var.get()
                    kalan_adet = sayim_adet - ayrilan_adet
                    kalan_toplam += kalan_adet * deger
                    ayrilan_toplam += ayrilan_adet * deger
                    if kalan_adet > 0:
                        ertesi_gun_kupurler[f"{deger} TL"] = kalan_adet
                except (ValueError, KeyError):
                    pass

        # Ertesi gün kasası - 11. tablodaki kalan toplam
        ertesi_gun = kalan_toplam if kalan_toplam > 0 else nakit

        # Ayrılan para - 11. tablodaki ayrılan toplam
        ayrilan = ayrilan_toplam

        # Düzeltilmiş nakit hesapla
        duzeltilmis_nakit = nakit + masraf + silinen + alinan

        return {
            # 1) Başlangıç Kasası
            'baslangic_kasasi': baslangic,
            'baslangic_kupurler': baslangic_kupurler,

            # 2) Akşam Kasası (Gün Sonu Nakit)
            'nakit_toplam': nakit,
            'nakit_kupurler': nakit_kupurler,

            # 3) POS ve IBAN
            'pos_toplam': pos,
            'pos_listesi': pos_listesi,
            'eczaci_pos_listesi': eczaci_pos_listesi,
            'eczaci_pos_toplam': eczaci_pos_toplam,
            'ingenico_listesi': ingenico_listesi,
            'ingenico_toplam': ingenico_toplam,
            'iban_toplam': iban,
            'iban_listesi': iban_listesi,

            # 4) Düzeltmeler
            'masraf_toplam': masraf,
            'masraf_listesi': masraf_listesi,
            'silinen_toplam': silinen,
            'silinen_listesi': silinen_listesi,
            'alinan_toplam': alinan,
            'alinan_listesi': alinan_listesi,
            'duzeltilmis_nakit': duzeltilmis_nakit,

            # 5) Botanik
            'botanik_nakit': botanik_nakit,
            'botanik_pos': botanik_pos,
            'botanik_iban': botanik_iban,
            'botanik_toplam': botanik_toplam,

            # 6) Fark
            'genel_toplam': genel,
            'son_genel_toplam': son_genel,
            'fark': fark,

            # 7) Ertesi Gün Kasası
            'ertesi_gun_kasasi': ertesi_gun,
            'ertesi_gun_kupurler': ertesi_gun_kupurler,
            'ayrilan_para': ayrilan,

            'manuel_baslangic': {
                'aktif': self.manuel_baslangic_aktif,
                'tutar': self.manuel_baslangic_tutar if self.manuel_baslangic_aktif else 0,
                'aciklama': self.manuel_baslangic_aciklama if self.manuel_baslangic_aktif else ""
            }
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

    def yardim_penceresi_ac(self):
        """Yardım penceresi - Kullanım Kılavuzu + Geliştirme Notları birleşik"""
        pencere = tk.Toplevel(self.root)
        pencere.title("Yardım")
        pencere.geometry("700x500")
        pencere.resizable(True, True)
        pencere.configure(bg='#F5F5F5')
        pencere.transient(self.root)

        # Pencereyi ortala
        pencere.update_idletasks()
        x = (pencere.winfo_screenwidth() - 700) // 2
        y = (pencere.winfo_screenheight() - 500) // 2
        pencere.geometry(f"700x500+{x}+{y}")

        # Notebook (sekmeli yapı)
        notebook = ttk.Notebook(pencere)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # SEKME 1: Kullanım Kılavuzu
        if YENI_MODULLER_YUKLENDI:
            kilavuz_frame = tk.Frame(notebook, bg='#FFFFFF')
            notebook.add(kilavuz_frame, text='Kullanım Kılavuzu')

            # Yardım içeriğini göster
            try:
                yardim_pencere = KasaYardimPenceresi(kilavuz_frame, embed=True)
                yardim_pencere.icerik_olustur(kilavuz_frame)
            except Exception as e:
                tk.Label(kilavuz_frame, text=f"Kullanım kılavuzu yüklenemedi: {e}",
                        font=("Arial", 12), bg='#FFFFFF').pack(pady=20)

        # SEKME 2: Geliştirme Notları
        notlar_frame = tk.Frame(notebook, bg='#FFFFFF')
        notebook.add(notlar_frame, text='Geliştirme Notları')

        # Dosya butonları
        btn_frame = tk.Frame(notlar_frame, bg='#FFFFFF')
        btn_frame.pack(pady=20)

        script_dir = os.path.dirname(os.path.abspath(__file__))

        def ac_dosya(dosya_adi):
            dosya_yolu = Path(script_dir) / dosya_adi
            if dosya_yolu.exists():
                os.startfile(str(dosya_yolu))
            else:
                messagebox.showwarning("Dosya Bulunamadı", f"{dosya_adi} bulunamadı.")

        tk.Label(notlar_frame, text="Aşağıdaki dosyaları açabilirsiniz:",
                font=("Arial", 11), bg='#FFFFFF').pack(pady=10)

        tk.Button(btn_frame, text="Geliştirme Adımları", font=("Arial", 10, "bold"),
                 bg='#4CAF50', fg='white', padx=20, pady=10,
                 command=lambda: ac_dosya("GELISTIRME_VE_KURULUM_ADIMLARI.txt")).pack(side="left", padx=10)

        tk.Button(btn_frame, text="Kurulum Rehberi", font=("Arial", 10, "bold"),
                 bg='#2196F3', fg='white', padx=20, pady=10,
                 command=lambda: ac_dosya("KURULUM_REHBERI.txt")).pack(side="left", padx=10)

        # Kapat butonu
        tk.Button(pencere, text="Kapat", font=("Arial", 10, "bold"),
                 bg='#607D8B', fg='white', padx=30, pady=5,
                 command=pencere.destroy).pack(pady=10)

    def ozellesmis_rapor_gonder(self):
        """Rapor Ayarları'na göre özelleşmiş rapor gönder"""
        if not YENI_MODULLER_YUKLENDI:
            messagebox.showwarning("Uyarı", "Rapor modülleri yüklenemedi!")
            return

        from rapor_ayarlari import rapor_ayarlarini_yukle, RaporAyarlariPenceresi

        # Seçim penceresi
        secim = tk.Toplevel(self.root)
        secim.title("Özelleşmiş Rapor Gönder")
        secim.geometry("420x380")
        secim.resizable(False, False)
        secim.configure(bg='#F5F5F5')
        secim.transient(self.root)
        secim.grab_set()

        # Ortala
        secim.update_idletasks()
        x = (secim.winfo_screenwidth() - 420) // 2
        y = (secim.winfo_screenheight() - 380) // 2
        secim.geometry(f"420x380+{x}+{y}")

        # Başlık
        baslik_frame = tk.Frame(secim, bg='#1565C0', height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(baslik_frame, text="ÖZELLEŞMİŞ RAPOR", font=("Arial", 14, "bold"),
                bg='#1565C0', fg='white').pack(expand=True)

        # Açıklama
        tk.Label(secim, text="Rapor, 'Rapor Ayarları' menüsündeki\nseçimlere göre oluşturulacaktır.",
                font=("Arial", 10), bg='#F5F5F5', fg='#666', justify='center').pack(pady=15)

        # Mevcut ayarları göster
        ayarlar_frame = tk.LabelFrame(secim, text="Aktif Ayarlar Özeti", font=("Arial", 10, "bold"),
                                      bg='#E3F2FD', padx=10, pady=10)
        ayarlar_frame.pack(fill="x", padx=20, pady=5)

        try:
            rapor_ayarlari = rapor_ayarlarini_yukle()
            whatsapp_ayar = rapor_ayarlari.get("whatsapp", {})

            # Aktif ayar sayısı
            aktif_sayisi = sum(1 for v in whatsapp_ayar.values() if v)
            toplam_sayisi = len(whatsapp_ayar)

            ozet_text = f"WhatsApp: {aktif_sayisi}/{toplam_sayisi} bölüm aktif"
            tk.Label(ayarlar_frame, text=ozet_text, font=("Arial", 9), bg='#E3F2FD').pack(anchor='w')

            # Bazı önemli ayarları göster
            onemli_ayarlar = [
                ("baslangic_kasasi_toplam", "Başlangıç Kasası"),
                ("sayim_botanik_ozet", "Sayım-Botanik Özeti"),
                ("ertesi_gun_toplam", "Ertesi Gün Kasası"),
            ]
            for key, label in onemli_ayarlar:
                durum = "✓" if whatsapp_ayar.get(key, True) else "✗"
                renk = "#4CAF50" if whatsapp_ayar.get(key, True) else "#F44336"
                tk.Label(ayarlar_frame, text=f"  {durum} {label}", font=("Arial", 9), bg='#E3F2FD', fg=renk).pack(anchor='w')

        except Exception:
            tk.Label(ayarlar_frame, text="Ayarlar yüklenemedi", font=("Arial", 9), bg='#E3F2FD', fg='#F44336').pack(anchor='w')

        # Ayarları düzenle butonu
        def ayarlari_duzenle():
            pencere = RaporAyarlariPenceresi(secim)
            pencere.goster()

        tk.Button(secim, text="⚙ Rapor Ayarlarını Düzenle", font=("Arial", 9),
                 bg='#9E9E9E', fg='white', cursor='hand2',
                 command=ayarlari_duzenle).pack(pady=10)

        # Gönder butonları
        tk.Label(secim, text="Gönderim Yöntemi:", font=("Arial", 10, "bold"),
                bg='#F5F5F5').pack(pady=(10, 5))

        btn_frame = tk.Frame(secim, bg='#F5F5F5')
        btn_frame.pack(pady=5)

        def gonder_whatsapp():
            secim.destroy()
            self.ozellesmis_whatsapp_rapor_gonder()

        def gonder_email():
            secim.destroy()
            self.email_rapor_gonder()

        def gonder_ikisi():
            secim.destroy()
            self.ozellesmis_whatsapp_rapor_gonder()
            self.root.after(500, self.email_rapor_gonder)

        tk.Button(btn_frame, text="WhatsApp", font=("Arial", 10, "bold"),
                 bg='#25D366', fg='white', width=12, pady=5,
                 command=gonder_whatsapp).pack(side="left", padx=5)

        tk.Button(btn_frame, text="E-posta", font=("Arial", 10, "bold"),
                 bg='#667eea', fg='white', width=12, pady=5,
                 command=gonder_email).pack(side="left", padx=5)

        tk.Button(secim, text="Her İkisine Gönder", font=("Arial", 10, "bold"),
                 bg='#FF9800', fg='white', width=30, pady=8,
                 command=gonder_ikisi).pack(pady=10)

        tk.Button(secim, text="İptal", font=("Arial", 9),
                 bg='#757575', fg='white', width=10,
                 command=secim.destroy).pack(pady=5)

    def rapor_gonder_tumu(self):
        """WhatsApp ve E-posta ile birlikte rapor gönder - aşağıdaki buton için"""
        if not YENI_MODULLER_YUKLENDI:
            messagebox.showwarning("Uyarı", "Rapor modülleri yüklenemedi!")
            return

        # Seçim penceresi
        secim = tk.Toplevel(self.root)
        secim.title("Rapor Gönder")
        secim.geometry("350x200")
        secim.resizable(False, False)
        secim.configure(bg='#F5F5F5')
        secim.transient(self.root)
        secim.grab_set()

        # Ortala
        secim.update_idletasks()
        x = (secim.winfo_screenwidth() - 350) // 2
        y = (secim.winfo_screenheight() - 200) // 2
        secim.geometry(f"350x200+{x}+{y}")

        tk.Label(secim, text="Rapor Gönderme Seçenekleri", font=("Arial", 12, "bold"),
                bg='#F5F5F5').pack(pady=15)

        btn_frame = tk.Frame(secim, bg='#F5F5F5')
        btn_frame.pack(pady=10)

        def gonder_whatsapp():
            secim.destroy()
            self.whatsapp_rapor_gonder()

        def gonder_email():
            secim.destroy()
            self.email_rapor_gonder()

        def gonder_ikisi():
            secim.destroy()
            self.whatsapp_rapor_gonder()
            # Biraz bekle sonra email aç
            self.root.after(500, self.email_rapor_gonder)

        tk.Button(btn_frame, text="WhatsApp", font=("Arial", 10, "bold"),
                 bg='#25D366', fg='white', width=12, pady=5,
                 command=gonder_whatsapp).pack(side="left", padx=5)

        tk.Button(btn_frame, text="E-posta", font=("Arial", 10, "bold"),
                 bg='#667eea', fg='white', width=12, pady=5,
                 command=gonder_email).pack(side="left", padx=5)

        tk.Button(secim, text="Her İkisi", font=("Arial", 10, "bold"),
                 bg='#FF9800', fg='white', width=28, pady=8,
                 command=gonder_ikisi).pack(pady=10)

        tk.Button(secim, text="İptal", font=("Arial", 9),
                 bg='#9E9E9E', fg='white', width=10,
                 command=secim.destroy).pack(pady=5)

    def kayitlar_penceresi_ac(self):
        """Kayıtlar penceresi - Geçmiş Kayıtlar + Raporlar birleşik"""
        pencere = tk.Toplevel(self.root)
        pencere.title("Kayıtlar ve Raporlar")
        pencere.geometry("1000x650")
        pencere.resizable(True, True)
        pencere.configure(bg='#F5F5F5')
        pencere.transient(self.root)

        # Ortala
        pencere.update_idletasks()
        x = (pencere.winfo_screenwidth() - 1000) // 2
        y = (pencere.winfo_screenheight() - 650) // 2
        pencere.geometry(f"1000x650+{x}+{y}")

        # Notebook (sekmeli yapı)
        style = ttk.Style()
        style.configure('Kayitlar.TNotebook.Tab', font=('Arial', 10, 'bold'), padding=[15, 5])

        notebook = ttk.Notebook(pencere, style='Kayitlar.TNotebook')
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # SEKME 1: Geçmiş Kayıtlar
        gecmis_frame = tk.Frame(notebook, bg='#FFFFFF')
        notebook.add(gecmis_frame, text='Geçmiş Kayıtlar')
        self.gecmis_icerik_olustur(gecmis_frame)

        # SEKME 2: Raporlar
        raporlar_frame = tk.Frame(notebook, bg='#FFFFFF')
        notebook.add(raporlar_frame, text='Raporlar')
        self.raporlar_icerik_olustur(raporlar_frame)

        # Alt butonlar
        alt_frame = tk.Frame(pencere, bg='#F5F5F5')
        alt_frame.pack(fill='x', pady=10)

        tk.Button(alt_frame, text="Kapat", font=("Arial", 10, "bold"),
                 bg='#607D8B', fg='white', padx=30, pady=5,
                 command=pencere.destroy).pack()

    def gecmis_icerik_olustur(self, parent):
        """Geçmiş kayıtlar içeriğini oluştur"""
        try:
            # Treeview oluştur
            columns = ('ID', 'Tarih', 'Saat', 'Nakit', 'POS', 'IBAN', 'Genel', 'Son Genel', 'Botanik', 'Fark')
            tree = ttk.Treeview(parent, columns=columns, show='headings', height=20)

            tree.heading('ID', text='ID')
            tree.heading('Tarih', text='Tarih')
            tree.heading('Saat', text='Saat')
            tree.heading('Nakit', text='Nakit')
            tree.heading('POS', text='POS')
            tree.heading('IBAN', text='IBAN')
            tree.heading('Genel', text='Genel Top.')
            tree.heading('Son Genel', text='Son Gen.Top.')
            tree.heading('Botanik', text='Botanik Top.')
            tree.heading('Fark', text='Fark')

            tree.column('ID', width=40)
            tree.column('Tarih', width=100)
            tree.column('Saat', width=70)
            tree.column('Nakit', width=90)
            tree.column('POS', width=90)
            tree.column('IBAN', width=90)
            tree.column('Genel', width=100)
            tree.column('Son Genel', width=100)
            tree.column('Botanik', width=100)
            tree.column('Fark', width=90)

            # Scrollbar
            scrollbar = ttk.Scrollbar(parent, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            tree.pack(side='left', fill='both', expand=True, padx=5, pady=5)
            scrollbar.pack(side='right', fill='y', pady=5)

            # Verileri yükle
            self.cursor.execute('''
                SELECT id, tarih, saat, nakit_toplam, pos_toplam, iban_toplam,
                       genel_toplam, son_genel_toplam, botanik_genel_toplam, fark
                FROM kasa_kapatma
                ORDER BY id DESC
                LIMIT 100
            ''')
            kayitlar = self.cursor.fetchall()

            if not kayitlar:
                tk.Label(parent, text="Henüz kayıt bulunmuyor.",
                        font=("Arial", 12), bg='#FFFFFF').pack(pady=50)
                return

            for row in kayitlar:
                son_genel = row[7] if row[7] else row[6]
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
            logger.error(f"Geçmiş yükleme hatası: {e}")
            tk.Label(parent, text=f"Kayıtlar yüklenemedi: {e}",
                    font=("Arial", 11), bg='#FFFFFF', fg='red').pack(pady=50)

    def raporlar_icerik_olustur(self, parent):
        """Raporlar içeriğini oluştur"""
        # Başlık
        baslik_frame = tk.Frame(parent, bg='#1565C0')
        baslik_frame.pack(fill='x')
        tk.Label(baslik_frame, text="RAPOR OLUŞTURMA", font=("Arial", 14, "bold"),
                bg='#1565C0', fg='white', pady=10).pack()

        # İçerik alanı
        icerik = tk.Frame(parent, bg='#FFFFFF')
        icerik.pack(fill='both', expand=True, padx=20, pady=20)

        # Dönem seçimi
        donem_frame = tk.LabelFrame(icerik, text="Dönem Seçimi", font=("Arial", 11, "bold"),
                                   bg='#FFFFFF', padx=15, pady=10)
        donem_frame.pack(fill='x', pady=10)

        btn_frame1 = tk.Frame(donem_frame, bg='#FFFFFF')
        btn_frame1.pack(pady=10)

        tk.Button(btn_frame1, text="Bugün", font=("Arial", 10, "bold"),
                 bg='#4CAF50', fg='white', width=12, pady=8,
                 command=lambda: self.donem_raporu('bugun')).pack(side="left", padx=5)

        tk.Button(btn_frame1, text="Dün", font=("Arial", 10, "bold"),
                 bg='#8BC34A', fg='white', width=12, pady=8,
                 command=lambda: self.donem_raporu('dun')).pack(side="left", padx=5)

        tk.Button(btn_frame1, text="Bu Hafta", font=("Arial", 10, "bold"),
                 bg='#2196F3', fg='white', width=12, pady=8,
                 command=lambda: self.donem_raporu('hafta')).pack(side="left", padx=5)

        tk.Button(btn_frame1, text="Bu Ay", font=("Arial", 10, "bold"),
                 bg='#9C27B0', fg='white', width=12, pady=8,
                 command=lambda: self.donem_raporu('ay')).pack(side="left", padx=5)

        # Rapor türü seçimi
        tur_frame = tk.LabelFrame(icerik, text="Rapor Türü", font=("Arial", 11, "bold"),
                                 bg='#FFFFFF', padx=15, pady=10)
        tur_frame.pack(fill='x', pady=10)

        btn_frame2 = tk.Frame(tur_frame, bg='#FFFFFF')
        btn_frame2.pack(pady=10)

        tk.Button(btn_frame2, text="Özet Rapor", font=("Arial", 10, "bold"),
                 bg='#FF9800', fg='white', width=15, pady=8,
                 command=self.ozet_rapor_olustur).pack(side="left", padx=10)

        tk.Button(btn_frame2, text="Detaylı Rapor", font=("Arial", 10, "bold"),
                 bg='#E91E63', fg='white', width=15, pady=8,
                 command=self.detayli_rapor_olustur).pack(side="left", padx=10)

        tk.Button(btn_frame2, text="Karşılaştırma", font=("Arial", 10, "bold"),
                 bg='#607D8B', fg='white', width=15, pady=8,
                 command=self.karsilastirma_raporu).pack(side="left", padx=10)

        # Hızlı işlemler
        hizli_frame = tk.LabelFrame(icerik, text="Hızlı İşlemler", font=("Arial", 11, "bold"),
                                   bg='#FFFFFF', padx=15, pady=10)
        hizli_frame.pack(fill='x', pady=10)

        btn_frame3 = tk.Frame(hizli_frame, bg='#FFFFFF')
        btn_frame3.pack(pady=10)

        tk.Button(btn_frame3, text="Excel'e Aktar", font=("Arial", 10),
                 bg='#217346', fg='white', width=15, pady=5,
                 command=self.excel_aktar).pack(side="left", padx=10)

        tk.Button(btn_frame3, text="Yazdır", font=("Arial", 10),
                 bg='#795548', fg='white', width=15, pady=5,
                 command=self.rapor_yazdir).pack(side="left", padx=10)

    def donem_raporu(self, donem):
        """Dönem bazlı rapor"""
        donem_isimleri = {
            'bugun': 'Bugün',
            'dun': 'Dün',
            'hafta': 'Bu Hafta',
            'ay': 'Bu Ay'
        }
        # Mevcut raporlama penceresini aç
        if YENI_MODULLER_YUKLENDI:
            self.raporlar_goster()
        else:
            messagebox.showinfo("Rapor", f"{donem_isimleri.get(donem, donem)} raporu hazırlanıyor...")

    def ozet_rapor_olustur(self):
        """Özet rapor"""
        if YENI_MODULLER_YUKLENDI:
            self.raporlar_goster()
        else:
            messagebox.showinfo("Bilgi", "Özet rapor hazırlanıyor...")

    def detayli_rapor_olustur(self):
        """Detaylı rapor"""
        if YENI_MODULLER_YUKLENDI:
            self.raporlar_goster()
        else:
            messagebox.showinfo("Bilgi", "Detaylı rapor hazırlanıyor...")

    def karsilastirma_raporu(self):
        """Karşılaştırma raporu"""
        messagebox.showinfo("Bilgi", "Karşılaştırma raporu özelliği geliştirme aşamasında.")

    def excel_aktar(self):
        """Excel'e aktar"""
        try:
            from datetime import datetime
            import csv

            # Dosya kaydetme dialogu
            dosya_adi = f"kasa_raporu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            dosya_yolu = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Dosyası", "*.csv"), ("Tüm Dosyalar", "*.*")],
                initialfile=dosya_adi
            )

            if not dosya_yolu:
                return

            # Verileri al
            self.cursor.execute('''
                SELECT tarih, saat, nakit_toplam, pos_toplam, iban_toplam,
                       genel_toplam, son_genel_toplam, botanik_genel_toplam, fark
                FROM kasa_kapatma
                ORDER BY id DESC
                LIMIT 100
            ''')
            kayitlar = self.cursor.fetchall()

            # CSV yaz
            with open(dosya_yolu, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(['Tarih', 'Saat', 'Nakit', 'POS', 'IBAN', 'Genel Toplam', 'Son Genel', 'Botanik', 'Fark'])
                for kayit in kayitlar:
                    writer.writerow(kayit)

            messagebox.showinfo("Başarılı", f"Rapor kaydedildi:\n{dosya_yolu}")

        except Exception as e:
            messagebox.showerror("Hata", f"Excel aktarma hatası: {e}")

    def rapor_yazdir(self):
        """Rapor yazdır"""
        # Mevcut yazıcı fonksiyonunu çağır
        if hasattr(self, 'yazici_isle'):
            self.yazici_isle()
        else:
            messagebox.showinfo("Bilgi", "Yazdırma için 'Gün Sonu Kaydet' butonunu kullanın.")


def kasa_takip_ac(ana_menu_callback=None):
    """Kasa Takip modülünü aç"""
    modul = KasaKapatmaModul(ana_menu_callback=ana_menu_callback)
    modul.calistir()


if __name__ == "__main__":
    modul = KasaKapatmaModul()
    modul.calistir()
