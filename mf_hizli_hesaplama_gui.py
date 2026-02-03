"""
MF Hızlı Hesaplama Modülü
NPV bazlı MF karlılık analizi - Zam ve stok maliyeti dahil
Veritabanından ilaç verisi çekme destekli
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import calendar
from tkcalendar import DateEntry
import threading

logger = logging.getLogger(__name__)


class MFHizliHesaplamaGUI:
    """MF Hızlı Hesaplama Modülü - Bağımsız Pencere"""

    def __init__(self, parent, ana_menu_callback=None):
        self.parent = parent
        self.ana_menu_callback = ana_menu_callback

        self.parent.title("MF Hızlı Hesaplama - NPV Bazlı Karlılık Analizi")
        self.parent.state('zoomed')  # Tam ekran
        self.parent.configure(bg='#ECEFF1')

        # Veritabanı
        self.db = None
        self.db_durum = "Bağlanılıyor..."
        self._db_baglan()

        # İlaç cache (autocomplete için)
        self.ilac_listesi = []
        self.ilac_yukleme_durumu = "Bekliyor..."
        self.secili_ilac = None  # Seçilen ilaç bilgileri

        # Değişkenler
        self.ilac_adi = tk.StringVar(value="")
        self.stok = tk.IntVar(value=0)
        self.aylik_ort = tk.DoubleVar(value=30)
        self.maliyet = tk.DoubleVar(value=100)
        self.alim_str = tk.StringVar(value="30")  # "100" veya "100+30" formatında (mal+mf)

        self.zam_aktif = tk.BooleanVar(value=False)
        self.zam_orani = tk.DoubleVar(value=20)
        self.mevduat_faizi = tk.DoubleVar(value=40)
        self.kredi_faizi = tk.DoubleVar(value=50)
        self.faiz_turu = tk.StringVar(value="mevduat")
        self.depo_vadesi = tk.IntVar(value=75)
        self.ay_sayisi = tk.IntVar(value=6)  # Aylık gidiş hesaplama için ay sayısı
        self.hareket_yili = tk.IntVar(value=2)  # Muadil filtresi: son N yılda hareketi olanlar

        # MF şartları
        self.mf_entries = []
        self.gecmis_mf_sartlari = []  # Veritabanından gelen geçmiş MF şartları

        self._arayuz_olustur()

        # İlaç listesini yükle (arka planda)
        self.parent.after(100, self._ilac_listesi_yukle)

    def _db_baglan(self):
        """Veritabanına bağlan"""
        try:
            from botanik_db import BotanikDB
            self.db = BotanikDB()
            if self.db.baglan():
                self.db_durum = "Bağlı ✓"
                logger.info("Veritabanına bağlandı")
            else:
                self.db = None
                self.db_durum = "Bağlantı başarısız!"
                logger.warning("Veritabanına bağlanılamadı")
        except ImportError as e:
            logger.error(f"botanik_db modülü bulunamadı: {e}")
            self.db = None
            self.db_durum = "Modül bulunamadı!"
        except Exception as e:
            logger.error(f"DB bağlantı hatası: {e}")
            self.db = None
            self.db_durum = f"Hata: {str(e)[:30]}"

    def _ilac_listesi_yukle(self):
        """İlaç listesini veritabanından yükle (arka planda)"""
        # Durum etiketi güncelle
        self._durum_guncelle()

        if not self.db:
            self.ilac_yukleme_durumu = "DB bağlantısı yok!"
            self._durum_guncelle()
            return

        self.ilac_yukleme_durumu = "Yükleniyor..."
        self._durum_guncelle()

        def yukle():
            try:
                # Son 2 yılda hareketi olan ilaçları getir
                # Stok: İlaçlar (tip 1,16) için karekod tablosundan, diğerleri için normal stok
                sql = """
                SELECT DISTINCT
                    u.UrunId,
                    u.UrunAdi,
                    CASE WHEN u.UrunUrunTipId IN (1, 16) THEN
                        (SELECT COUNT(*) FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1)
                    ELSE (COALESCE(u.UrunStokDepo,0) + COALESCE(u.UrunStokRaf,0) + COALESCE(u.UrunStokAcik,0))
                    END AS Stok,
                    u.UrunFiyatKamu AS KamuFiyat,
                    u.UrunFiyatEtiket AS PSF,
                    u.UrunIskontoKamu AS IskontoYuzde,
                    u.UrunIskontoYedek AS DepocuKDVHaric
                FROM Urun u
                WHERE u.UrunSilme = 0
                AND u.UrunUrunTipId IN (1, 2, 3, 16)
                ORDER BY u.UrunAdi
                """
                sonuc = self.db.sorgu_calistir(sql)
                if sonuc:
                    self.ilac_listesi = sonuc
                    self.ilac_yukleme_durumu = f"{len(sonuc)} ilaç yüklendi ✓"
                    logger.info(f"✓ {len(sonuc)} ilaç yüklendi")
                else:
                    self.ilac_yukleme_durumu = "Sonuç yok (0 ilaç)"
                    logger.warning("İlaç listesi boş döndü")
            except Exception as e:
                self.ilac_yukleme_durumu = f"Hata: {str(e)[:30]}"
                logger.error(f"İlaç listesi yükleme hatası: {e}")

            # Ana thread'de durum etiketini güncelle
            self.parent.after(0, self._durum_guncelle)

        threading.Thread(target=yukle, daemon=True).start()

    def _durum_guncelle(self):
        """Durum etiketini güncelle"""
        if hasattr(self, 'durum_label'):
            # Kısa format
            db_kisa = "✓" if "Bağlı" in self.db_durum else "✗"
            ilac_kisa = self.ilac_yukleme_durumu.split()[0] if self.ilac_yukleme_durumu else "-"
            self.durum_label.config(text=f"DB:{db_kisa} | {ilac_kisa}")

    def _arayuz_olustur(self):
        """Ana arayüz - Sol'da parametreler+muadiller, sağda sonuçlar+nakit akış"""
        # Başlık
        header = tk.Frame(self.parent, bg='#1976D2', height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="📊 MF Hızlı Hesaplama - NPV Bazlı Karlılık Analizi",
                bg='#1976D2', fg='white', font=('Arial', 14, 'bold')).pack(pady=12)

        # Ana içerik
        main_frame = tk.Frame(self.parent, bg='#ECEFF1', padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ═══ SOL TARAF: Parametreler + Muadiller ═══
        sol_frame = tk.Frame(main_frame, bg='#ECEFF1', width=630)
        sol_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        sol_frame.pack_propagate(False)

        # Parametreler (sol üst)
        self._parametre_panel_olustur(sol_frame)

        # Muadil İlaçlar Tablosu (sol alt)
        self._muadil_panel_olustur(sol_frame)

        # ═══ SAĞ TARAF: MF Sonuçları + Nakit Akış ═══
        sag_frame = tk.Frame(main_frame, bg='#ECEFF1')
        sag_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # MF Sonuçları (sağ üst)
        self._sonuc_panel_olustur(sag_frame)

        # Nakit Akış Tablosu (sağ alt)
        self._nakit_akis_panel_olustur(sag_frame)

    def _parametre_panel_olustur(self, parent):
        """Parametre giriş paneli - Kompakt"""
        param_frame = tk.LabelFrame(parent, text="Parametreler", font=('Arial', 10, 'bold'),
                                    bg='#ECEFF1', padx=8, pady=5)
        param_frame.pack(fill=tk.X, pady=(0, 5))

        # ═══ İLAÇ ARAMA ═══
        arama_frame = tk.LabelFrame(param_frame, text="İlaç Ara", font=('Arial', 9, 'bold'),
                                    bg='#FFF9C4', padx=5, pady=3)
        arama_frame.pack(fill=tk.X, pady=(0, 5))

        # Combobox ile autocomplete
        self.ilac_combo = ttk.Combobox(arama_frame, width=30, font=('Arial', 9))
        self.ilac_combo.pack(fill=tk.X, padx=2, pady=2)
        self.ilac_combo.bind('<KeyRelease>', self._ilac_ara_combo)
        self.ilac_combo.bind('<<ComboboxSelected>>', self._ilac_secildi_combo)

        # Durum ve seçilen ilaç bilgisi tek satırda
        durum_row = tk.Frame(arama_frame, bg='#FFF9C4')
        durum_row.pack(fill=tk.X)
        self.durum_label = tk.Label(durum_row, text="DB: Bağlanılıyor...",
                                    font=('Arial', 7), bg='#FFF9C4', fg='#1565C0')
        self.durum_label.pack(side=tk.LEFT)
        self.secili_ilac_label = tk.Label(durum_row, text="",
                                          font=('Arial', 7), bg='#FFF9C4', fg='#2E7D32')
        self.secili_ilac_label.pack(side=tk.RIGHT)

        # ═══ İLAÇ BİLGİLERİ (Kompakt - 2 satır) ═══
        ilac_frame = tk.LabelFrame(param_frame, text="Stok/Fiyat/Sipariş", font=('Arial', 9, 'bold'),
                                   bg='#E3F2FD', padx=5, pady=3)
        ilac_frame.pack(fill=tk.X, pady=(0, 5))

        # Satır 1: Stok ve Aylık
        row1 = tk.Frame(ilac_frame, bg='#E3F2FD')
        row1.pack(fill=tk.X, pady=1)
        tk.Label(row1, text="Stok:", font=('Arial', 9), bg='#E3F2FD', width=5, anchor='w').pack(side=tk.LEFT)
        self.stok_entry = ttk.Entry(row1, textvariable=self.stok, width=6, font=('Arial', 9))
        self.stok_entry.pack(side=tk.LEFT)
        tk.Label(row1, text="Aylık:", font=('Arial', 9), bg='#E3F2FD', width=5, anchor='e').pack(side=tk.LEFT, padx=(10,0))
        self.aylik_entry = ttk.Entry(row1, textvariable=self.aylik_ort, width=6, font=('Arial', 9))
        self.aylik_entry.pack(side=tk.LEFT)

        # Satır 2: Fiyat
        row2 = tk.Frame(ilac_frame, bg='#E3F2FD')
        row2.pack(fill=tk.X, pady=1)
        tk.Label(row2, text="Fiyat:", font=('Arial', 9), bg='#E3F2FD', width=5, anchor='w').pack(side=tk.LEFT)
        self.maliyet_entry = ttk.Entry(row2, textvariable=self.maliyet, width=6, font=('Arial', 9))
        self.maliyet_entry.pack(side=tk.LEFT)
        tk.Label(row2, text="TL (Depocu)", font=('Arial', 7), bg='#E3F2FD', fg='gray').pack(side=tk.LEFT, padx=(5,0))

        # Satır 3: Ay sayısı ayarı
        row3 = tk.Frame(ilac_frame, bg='#E3F2FD')
        row3.pack(fill=tk.X, pady=1)
        tk.Label(row3, text="Ay:", font=('Arial', 9), bg='#E3F2FD', width=5, anchor='w').pack(side=tk.LEFT)
        self.ay_combo = ttk.Combobox(row3, textvariable=self.ay_sayisi,
                                     values=[3, 4, 6, 8, 12, 24], width=3, state='readonly', font=('Arial', 9))
        self.ay_combo.pack(side=tk.LEFT)
        self.ay_combo.set(6)
        self.ay_combo.bind('<<ComboboxSelected>>', self._ay_sayisi_degisti)
        tk.Label(row3, text="(Aylık gidiş hesabı)", font=('Arial', 7), bg='#E3F2FD', fg='gray').pack(side=tk.LEFT, padx=(5,0))

        # Grup toplam aylık gidiş etiketi
        row4 = tk.Frame(ilac_frame, bg='#E3F2FD')
        row4.pack(fill=tk.X, pady=1)
        tk.Label(row4, text="Grup:", font=('Arial', 9), bg='#E3F2FD', width=5, anchor='w').pack(side=tk.LEFT)
        self.grup_aylik_label = tk.Label(row4, text="-", font=('Arial', 9, 'bold'), bg='#E3F2FD', fg='#1565C0')
        self.grup_aylik_label.pack(side=tk.LEFT)
        tk.Label(row4, text="(Tüm muadiller)", font=('Arial', 7), bg='#E3F2FD', fg='gray').pack(side=tk.LEFT, padx=(5,0))

        # ═══ FAİZ PARAMETRELERİ (Kompakt) ═══
        faiz_frame = tk.LabelFrame(param_frame, text="Faiz", font=('Arial', 9, 'bold'),
                                   bg='#E0F7FA', padx=5, pady=3)
        faiz_frame.pack(fill=tk.X, pady=(0, 5))

        # Satır 1: Mevduat ve Kredi
        row_f1 = tk.Frame(faiz_frame, bg='#E0F7FA')
        row_f1.pack(fill=tk.X, pady=1)
        tk.Label(row_f1, text="Mevd%:", font=('Arial', 9), bg='#E0F7FA', width=6, anchor='w').pack(side=tk.LEFT)
        ttk.Entry(row_f1, textvariable=self.mevduat_faizi, width=4, font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Label(row_f1, text="Kredi%:", font=('Arial', 9), bg='#E0F7FA', width=6, anchor='e').pack(side=tk.LEFT, padx=(5,0))
        ttk.Entry(row_f1, textvariable=self.kredi_faizi, width=4, font=('Arial', 9)).pack(side=tk.LEFT)

        # Satır 2: Seçim ve vade
        row_f2 = tk.Frame(faiz_frame, bg='#E0F7FA')
        row_f2.pack(fill=tk.X, pady=1)
        tk.Radiobutton(row_f2, text="Mevd", variable=self.faiz_turu, value="mevduat",
                      bg='#E0F7FA', font=('Arial', 8)).pack(side=tk.LEFT)
        tk.Radiobutton(row_f2, text="Kredi", variable=self.faiz_turu, value="kredi",
                      bg='#E0F7FA', font=('Arial', 8)).pack(side=tk.LEFT)
        tk.Label(row_f2, text="Vade:", font=('Arial', 9), bg='#E0F7FA').pack(side=tk.LEFT, padx=(5,0))
        ttk.Entry(row_f2, textvariable=self.depo_vadesi, width=3, font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Label(row_f2, text="g", font=('Arial', 8), bg='#E0F7FA').pack(side=tk.LEFT)

        # ═══ ZAM BEKLENTİSİ (Kompakt) ═══
        zam_frame = tk.LabelFrame(param_frame, text="Zam", font=('Arial', 9, 'bold'),
                                  bg='#FFF3E0', padx=5, pady=3)
        zam_frame.pack(fill=tk.X, pady=(0, 5))

        row_z1 = tk.Frame(zam_frame, bg='#FFF3E0')
        row_z1.pack(fill=tk.X, pady=1)
        tk.Checkbutton(row_z1, text="Aktif", variable=self.zam_aktif,
                      bg='#FFF3E0', font=('Arial', 9),
                      command=self._zam_degisti).pack(side=tk.LEFT)
        tk.Label(row_z1, text="%", font=('Arial', 9), bg='#FFF3E0').pack(side=tk.LEFT, padx=(10,0))
        ttk.Entry(row_z1, textvariable=self.zam_orani, width=4, font=('Arial', 9)).pack(side=tk.LEFT)

        row_z2 = tk.Frame(zam_frame, bg='#FFF3E0')
        row_z2.pack(fill=tk.X, pady=1)
        tk.Label(row_z2, text="Tarih:", font=('Arial', 9), bg='#FFF3E0').pack(side=tk.LEFT)
        self.zam_tarih_entry = DateEntry(row_z2, width=10, background='#E65100', foreground='white',
                                         borderwidth=1, date_pattern='yyyy-mm-dd', font=('Arial', 9))
        self.zam_tarih_entry.pack(side=tk.LEFT, padx=3)

        # ═══ MF ŞARTLARI ═══
        mf_frame = tk.LabelFrame(param_frame, text="MF Şartları", font=('Arial', 9, 'bold'),
                                 bg='#E8F5E9', padx=5, pady=3)
        mf_frame.pack(fill=tk.X, pady=(0, 5))

        # MF'siz ve geçmiş MF aynı satırda
        mf_row1 = tk.Frame(mf_frame, bg='#E8F5E9')
        mf_row1.pack(fill=tk.X, pady=1)
        self.mfsiz_var = tk.BooleanVar(value=True)
        tk.Checkbutton(mf_row1, text="MF'siz", variable=self.mfsiz_var,
                      bg='#E8F5E9', font=('Arial', 9, 'bold'), fg='#1565C0').pack(side=tk.LEFT)

        self.gecmis_mf_frame = tk.Frame(mf_frame, bg='#E8F5E9')
        self.gecmis_mf_frame.pack(fill=tk.X)
        self.gecmis_mf_label = tk.Label(self.gecmis_mf_frame, text="Geçmiş: -",
                                        font=('Arial', 8), bg='#E8F5E9', fg='#666')
        self.gecmis_mf_label.pack(anchor='w')

        # Manuel MF girişi (varsayılan boş - veritabanından gelecek)
        mf_giris_frame = tk.Frame(mf_frame, bg='#E8F5E9')
        mf_giris_frame.pack(fill=tk.X, pady=2)

        self.mf_entries = []
        for i in range(5):
            entry = ttk.Entry(mf_giris_frame, width=7, font=('Arial', 9))
            entry.pack(side=tk.LEFT, padx=1)
            # Varsayılan değer yok - veritabanından veya manuel girilecek
            self.mf_entries.append(entry)

        # Butonlar - İki ayrı fonksiyon
        buton_frame = tk.Frame(param_frame, bg='#ECEFF1')
        buton_frame.pack(fill=tk.X, pady=8)

        # MF KARŞILAŞTIR butonu
        tk.Button(buton_frame, text="MF KARŞILAŞTIR", font=('Arial', 10, 'bold'),
                 bg='#1565C0', fg='white', padx=10, pady=5,
                 command=self._mf_karsilastir).pack(side=tk.LEFT, padx=2)

        # NAKİT AKIŞ: Alım girişi + buton birlikte
        nakit_frame = tk.Frame(buton_frame, bg='#388E3C', padx=3, pady=3)
        nakit_frame.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        # Alım girişi (mal+mf formatında: "100" veya "100+30")
        tk.Label(nakit_frame, text="Alım:", font=('Arial', 9), bg='#388E3C', fg='white').pack(side=tk.LEFT, padx=(2,2))
        self.alim_entry = tk.Entry(nakit_frame, textvariable=self.alim_str, width=8,
                                   font=('Arial', 10, 'bold'), justify='center')
        self.alim_entry.pack(side=tk.LEFT, padx=2)

        # NAKİT AKIŞ butonu
        tk.Button(nakit_frame, text="NAKİT AKIŞ →", font=('Arial', 10, 'bold'),
                 bg='#2E7D32', fg='white', padx=8, pady=2,
                 command=self._nakit_akis_goster).pack(side=tk.LEFT, padx=2)

    def _ilac_ara_combo(self, event=None):
        """İlaç arama - Combobox ile kelime bazlı arama"""
        # Özel tuşlarda arama yapma
        if event and event.keysym in ('Down', 'Up', 'Return', 'Escape', 'Tab'):
            return

        # Mevcut arama timer'ı iptal et
        if hasattr(self, '_arama_timer') and self._arama_timer:
            self.parent.after_cancel(self._arama_timer)

        # 150ms bekle (kullanıcı yazmayı bitirsin)
        self._arama_timer = self.parent.after(150, self._ilac_ara_delayed)

    def _ilac_ara_delayed(self):
        """Geciktirilmiş arama - typing bitene kadar bekle"""
        self._arama_timer = None

        # Cursor pozisyonunu kaydet
        try:
            cursor_pos = self.ilac_combo.index(tk.INSERT)
        except:
            cursor_pos = tk.END

        aranan = self.ilac_combo.get().strip().upper()

        if len(aranan) < 2:
            self.ilac_combo['values'] = []
            return

        # İlaç listesi boşsa uyar
        if not self.ilac_listesi:
            return

        # Kelime bazlı arama: "amok 1000 tab" -> ["AMOK", "1000", "TAB"]
        kelimeler = aranan.split()

        # Eşleşen ilaçları bul (tüm kelimeler ilaç adında olmalı)
        eslesen = []
        for ilac in self.ilac_listesi:
            ilac_adi = ilac.get('UrunAdi', '').upper()
            # Tüm kelimelerin ilaç adında geçip geçmediğini kontrol et
            hepsi_var = all(kelime in ilac_adi for kelime in kelimeler)
            if hepsi_var:
                eslesen.append(ilac['UrunAdi'])
                if len(eslesen) >= 20:  # Max 20 öneri
                    break

        # Combobox değerlerini güncelle (sadece farklıysa)
        mevcut = list(self.ilac_combo['values'])
        if eslesen != mevcut:
            self.ilac_combo['values'] = eslesen

        # Focus ve cursor pozisyonunu koru
        self.parent.after(10, lambda: self._cursor_koru(cursor_pos))

    def _cursor_koru(self, pozisyon):
        """Combobox'ta cursor pozisyonunu koru"""
        try:
            if self.ilac_combo.focus_get() != self.ilac_combo:
                self.ilac_combo.focus_set()
            self.ilac_combo.icursor(pozisyon)
        except:
            pass

    def _ilac_secildi_combo(self, event=None):
        """Combobox'tan ilaç seçildi"""
        secili_adi = self.ilac_combo.get()
        logger.info(f"İlaç seçildi: '{secili_adi}'")

        if not secili_adi:
            logger.warning("Seçili ilaç adı boş")
            return

        if not self.ilac_listesi:
            logger.warning("İlaç listesi henüz yüklenmedi!")
            return

        # İlaç bilgilerini bul
        bulunan = None
        for ilac in self.ilac_listesi:
            if ilac['UrunAdi'] == secili_adi:
                bulunan = ilac
                break

        if bulunan:
            logger.info(f"İlaç bulundu: UrunId={bulunan.get('UrunId')}")
            self._ilac_bilgilerini_doldur(bulunan)
        else:
            logger.warning(f"İlaç listesinde bulunamadı: '{secili_adi}'")

    def _ilac_bilgilerini_doldur(self, ilac):
        """Seçilen ilacın bilgilerini form alanlarına doldur"""
        logger.info(f"İlaç bilgileri dolduruluyor: {ilac.get('UrunAdi', 'N/A')}")
        self.secili_ilac = ilac

        # Combobox'ı güncelle
        self.ilac_combo.set(ilac['UrunAdi'])

        # Stok
        stok = ilac.get('Stok', 0) or 0
        self.stok.set(int(stok))

        # Depocu fiyat hesapla:
        # Öncelik 1: UrunIskontoYedek (KDV hariç depocu fiyatı) varsa kullan
        # Öncelik 2: PSF üzerinden hesapla
        depocu_kdv_haric = float(ilac.get('DepocuKDVHaric', 0) or 0)
        psf = float(ilac.get('PSF', 0) or 0)
        iskonto_yuzde = float(ilac.get('IskontoYuzde', 0) or 0)

        if depocu_kdv_haric > 0:
            # Doğrudan KDV hariç depocu fiyatı var, sadece KDV ekle
            depocu = depocu_kdv_haric * 1.10
            self.maliyet.set(round(depocu, 2))
            logger.info(f"Depocu fiyat (UrunIskontoYedek): {depocu_kdv_haric} × 1.10 = {depocu:.2f}")
        elif psf > 0:
            # PSF üzerinden hesapla: PSF × 0.71 × 1.10 × (1 - İskonto/100)
            depocu = psf * 0.71 * 1.10 * (1 - iskonto_yuzde / 100)
            self.maliyet.set(round(depocu, 2))
            logger.info(f"Depocu fiyat (PSF hesap): {psf} × 0.71 × 1.10 × (1-{iskonto_yuzde}/100) = {depocu:.2f}")
        else:
            self.maliyet.set(0)

        logger.info(f"Stok={stok}, PSF={psf}, DepocuKDVHaric={depocu_kdv_haric}, Depocu={self.maliyet.get()}")

        # Seçilen ilaç bilgisi etiketi (kısa)
        self.secili_ilac_label.config(
            text=f"✓ S:{stok} F:{self.maliyet.get():.0f}₺",
            fg='#2E7D32'
        )

        # Aylık satış ve MF şartlarını getir
        urun_id = ilac.get('UrunId')
        logger.info(f"UrunId={urun_id}, DB bağlı={self.db is not None}")

        if self.db and urun_id:
            logger.info(f"İlaç detayları getiriliyor: UrunId={urun_id}")
            self._ilac_detay_getir(urun_id)
            # Muadil ilaçların aylık gidişlerini getir
            logger.info(f"Muadil verileri getiriliyor: UrunId={urun_id}")
            self._muadil_verileri_getir(urun_id)
        else:
            logger.warning(f"DB veya UrunId eksik: db={self.db}, urun_id={urun_id}")

    def _ay_sayisi_degisti(self, event=None):
        """Ay sayısı değiştiğinde muadil verilerini yeniden yükle"""
        if self.secili_ilac and self.secili_ilac.get('UrunId'):
            # İlaç detaylarını yeniden getir
            self._ilac_detay_getir(self.secili_ilac['UrunId'])
            # Muadil verilerini yeniden getir
            self._muadil_verileri_getir(self.secili_ilac['UrunId'])

    def _hareket_yili_degisti(self, event=None):
        """Hareket yılı filtresi değiştiğinde muadil verilerini yeniden yükle"""
        if self.secili_ilac and self.secili_ilac.get('UrunId'):
            self._muadil_verileri_getir(self.secili_ilac['UrunId'])

    def _ilac_detay_getir(self, urun_id):
        """İlacın aylık satış ve MF şartlarını getir"""
        # Thread-safe: değeri thread başlamadan önce al
        ay_sayisi = self.ay_sayisi.get()

        def getir():
            # Thread için ayrı DB bağlantısı oluştur
            try:
                from botanik_db import BotanikDB
                thread_db = BotanikDB()
                if not thread_db.baglan():
                    logger.error("Thread DB bağlantısı kurulamadı")
                    return
            except Exception as e:
                logger.error(f"Thread DB oluşturma hatası: {e}")
                return

            try:
                bugun = date.today()
                baslangic = (bugun - relativedelta(months=ay_sayisi)).strftime('%Y-%m-%d')

                # ═══════════════════════════════════════════════════════════════════
                # AYLIK SATIŞ: ReceteIlaclari + EldenIlaclari tablolarından
                # ═══════════════════════════════════════════════════════════════════
                sql_satis = f"""
                SELECT
                    (SELECT COALESCE(SUM(ri.RIAdet), 0)
                     FROM ReceteIlaclari ri
                     JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
                     WHERE ri.RIUrunId = {urun_id}
                     AND ra.RxSilme = 0 AND ri.RISilme = 0
                     AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
                     AND CAST(ra.RxKayitTarihi as date) >= '{baslangic}')
                    +
                    (SELECT COALESCE(SUM(ei.RIAdet), 0)
                     FROM EldenIlaclari ei
                     JOIN EldenAna ea ON ei.RIRxId = ea.RxId
                     WHERE ei.RIUrunId = {urun_id}
                     AND ea.RxSilme = 0 AND ei.RISilme = 0
                     AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
                     AND CAST(ea.RxKayitTarihi as date) >= '{baslangic}')
                AS ToplamCikis
                """
                sonuc = thread_db.sorgu_calistir(sql_satis)
                logger.info(f"Aylık satış sorgusu: UrunId={urun_id}, Sonuç={sonuc}")

                if sonuc and sonuc[0].get('ToplamCikis'):
                    toplam_cikis = float(sonuc[0]['ToplamCikis'])

                    # Efektif ay sayısı hesaplama (siparis_verme_gui ile aynı yöntem)
                    ay_basi = bugun.replace(day=1)
                    bu_ay_gecen_gun = (bugun - ay_basi).days + 1
                    efektif_ay_sayisi = (ay_sayisi - 1) + (bu_ay_gecen_gun / 30)
                    aylik_ort = toplam_cikis / efektif_ay_sayisi if efektif_ay_sayisi > 0 else 0

                    logger.info(f"Hesaplama: Toplam={toplam_cikis}, Efektif Ay={efektif_ay_sayisi:.2f}, Aylık Ort={aylik_ort:.1f}")

                    # Aylık gidişi güncelle ve önerilen siparişi hesapla
                    def guncelle(ao=aylik_ort):
                        self.aylik_ort.set(round(ao, 1))
                        self._onerilen_siparis_hesapla()
                    self.parent.after(0, guncelle)
                else:
                    logger.warning(f"Aylık satış verisi bulunamadı: UrunId={urun_id}")
                    self.parent.after(0, lambda: self.aylik_ort.set(0))

                # ═══════════════════════════════════════════════════════════════════
                # SON 1 YIL MF ALIMLARI: FaturaSatir + FaturaGiris tablolarından
                # ═══════════════════════════════════════════════════════════════════
                mf_baslangic = (bugun - relativedelta(years=1)).strftime('%Y-%m-%d')
                sql_mf = f"""
                SELECT DISTINCT
                    CAST(fs.FSUrunAdet as int) as Adet,
                    CAST(COALESCE(fs.FSUrunMf, 0) as int) as MF,
                    fg.FGFaturaTarihi as Tarih
                FROM FaturaSatir fs
                JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
                WHERE fs.FSUrunId = {urun_id}
                AND fg.FGSilme = 0
                AND CAST(fg.FGFaturaTarihi as date) >= '{mf_baslangic}'
                AND fs.FSUrunMf IS NOT NULL
                AND fs.FSUrunMf > 0
                ORDER BY fg.FGFaturaTarihi DESC
                """
                mf_sonuc = thread_db.sorgu_calistir(sql_mf)
                logger.info(f"MF sorgusu: UrunId={urun_id}, Sonuç sayısı={len(mf_sonuc) if mf_sonuc else 0}")
                if mf_sonuc:
                    # Benzersiz MF şartlarını bul (Adet+MF formatında)
                    mf_dict = {}
                    for m in mf_sonuc:
                        adet = int(m['Adet'] or 0)
                        bedava = int(m['MF'] or 0)
                        if adet > 0 and bedava > 0:
                            mf_key = f"{adet}+{bedava}"
                            if mf_key not in mf_dict:
                                mf_dict[mf_key] = m['Tarih']

                    if mf_dict:
                        mf_sartlar = list(mf_dict.keys())[:5]  # Max 5 şart
                        mf_text = ", ".join(mf_sartlar)
                        self.parent.after(0, lambda txt=mf_text: self.gecmis_mf_label.config(
                            text=f"Geçmiş MF: {txt}",
                            fg='#2E7D32'
                        ))

                        # MF entry'lerini güncelle (closure fix)
                        def mf_guncelle(sartlar=mf_sartlar):
                            for i, entry in enumerate(self.mf_entries):
                                entry.delete(0, tk.END)
                                if i < len(sartlar):
                                    entry.insert(0, sartlar[i])
                        self.parent.after(0, mf_guncelle)
                    else:
                        self.parent.after(0, lambda: self.gecmis_mf_label.config(
                            text="Geçmiş MF: Kayıt yok",
                            fg='#666'
                        ))
                else:
                    self.parent.after(0, lambda: self.gecmis_mf_label.config(
                        text="Geçmiş MF: Kayıt yok",
                        fg='#666'
                    ))

            except Exception as e:
                logger.error(f"İlaç detay getirme hatası: {e}")
            finally:
                # Thread DB bağlantısını kapat
                try:
                    thread_db.kapat()
                except:
                    pass

        threading.Thread(target=getir, daemon=True).start()

    def _ay_sonu_siparis_hesapla(self, aylik_ort):
        """Ay sonuna kadar gereken miktarı hesapla (temel hesaplama)"""
        try:
            bugun = date.today()
            ay_son_gun = calendar.monthrange(bugun.year, bugun.month)[1]
            kalan_gun = ay_son_gun - bugun.day

            stok = self.stok.get()
            gunluk_ort = aylik_ort / 30 if aylik_ort > 0 else 0
            ay_sonu_ihtiyac = gunluk_ort * kalan_gun
            siparis_oneri = max(0, ay_sonu_ihtiyac - stok)

            self.parent.after(0, lambda s=siparis_oneri: self._alim_guncelle(int(s), 0))
        except Exception as e:
            logger.error(f"Ay sonu sipariş hesaplama hatası: {e}")

    def _alim_parse(self, alim_str):
        """Alım stringini parse et: '100' veya '100+30' formatı
        Returns: (mal_adet, mf_adet) tuple
        """
        try:
            alim = alim_str.strip()
            if '+' in alim:
                parcalar = alim.split('+')
                mal = int(parcalar[0].strip())
                mf = int(parcalar[1].strip())
                return (mal, mf)
            else:
                return (int(alim), 0)
        except:
            return (0, 0)

    def _alim_guncelle(self, mal, mf=0):
        """Alım miktarını güncelle (mal+mf formatında)"""
        if mf > 0:
            self.alim_str.set(f"{mal}+{mf}")
        else:
            self.alim_str.set(str(mal))

    def _zam_degisti(self):
        """Zam checkbox değiştiğinde önerilen siparişi yeniden hesapla"""
        self._onerilen_siparis_hesapla()

    def _onerilen_siparis_hesapla(self):
        """Zam ve MF durumuna göre önerilen sipariş miktarını hesapla"""
        try:
            stok = self.stok.get()
            aylik_ort = self.aylik_ort.get()
            maliyet = self.maliyet.get()
            faiz = self._aktif_faiz_getir()
            depo_vade = self.depo_vadesi.get()
            zam_aktif = self.zam_aktif.get()
            zam_orani = self.zam_orani.get() if zam_aktif else 0

            if aylik_ort <= 0 or maliyet <= 0:
                self._alim_guncelle(0, 0)
                return

            bugun = date.today()
            gunluk_sarf = aylik_ort / 30

            # Zam aktifse -> Zam öncesi optimum hesapla
            if zam_aktif and zam_orani > 0:
                zam_tarihi = self.zam_tarih_entry.get_date()
                zam_gun = max(0, (zam_tarihi - bugun).days)

                if zam_gun > 0:
                    # Zam öncesi optimum (pareto noktası) hesapla
                    sonuc = self._zam_karar_noktalari_hesapla(
                        stok, aylik_ort, maliyet, faiz, depo_vade, zam_gun, zam_orani
                    )
                    if sonuc and sonuc.get('pareto') and sonuc['pareto'].get('miktar', 0) > 0:
                        oneri = sonuc['pareto']['miktar']
                        self._alim_guncelle(int(oneri), 0)
                        return
                    elif sonuc and sonuc.get('tepe') and sonuc['tepe'].get('miktar', 0) > 0:
                        oneri = sonuc['tepe']['miktar']
                        self._alim_guncelle(int(oneri), 0)
                        return

            # Zam yoksa -> Ay sonuna kadar ihtiyaç
            ay_son_gun = calendar.monthrange(bugun.year, bugun.month)[1]
            kalan_gun = ay_son_gun - bugun.day
            ay_sonu_ihtiyac = gunluk_sarf * kalan_gun
            siparis_oneri = max(0, ay_sonu_ihtiyac - stok)

            self._alim_guncelle(int(siparis_oneri), 0)

        except Exception as e:
            logger.error(f"Önerilen sipariş hesaplama hatası: {e}")

    def _muadil_panel_olustur(self, parent):
        """Muadil ilaçlar aylık gidiş tablosu paneli"""
        self.muadil_frame = tk.LabelFrame(parent, text="Muadil İlaçlar - Aylık Gidiş (Tıkla Seç)",
                                          font=('Arial', 11, 'bold'),
                                          bg='#ECEFF1', padx=8, pady=8)
        self.muadil_frame.pack(fill=tk.BOTH, expand=True)

        # Üst butonlar ve filtreler
        buton_frame = tk.Frame(self.muadil_frame, bg='#ECEFF1')
        buton_frame.pack(fill=tk.X, pady=(0, 8))

        tk.Button(buton_frame, text="Grup Toplamını Kullan", font=('Arial', 10, 'bold'),
                 bg='#1976D2', fg='white', padx=10, pady=3,
                 command=self._grup_toplami_kullan).pack(side=tk.LEFT, padx=2)

        # Hareket yılı filtresi (sağ tarafta)
        filtre_frame = tk.Frame(buton_frame, bg='#ECEFF1')
        filtre_frame.pack(side=tk.RIGHT)

        tk.Label(filtre_frame, text="Son", font=('Arial', 9), bg='#ECEFF1').pack(side=tk.LEFT)
        self.hareket_yili_combo = ttk.Combobox(filtre_frame, textvariable=self.hareket_yili,
                                                values=[1, 2, 3, 5], width=3, state='readonly', font=('Arial', 9))
        self.hareket_yili_combo.pack(side=tk.LEFT, padx=2)
        self.hareket_yili_combo.set(2)
        self.hareket_yili_combo.bind('<<ComboboxSelected>>', self._hareket_yili_degisti)
        tk.Label(filtre_frame, text="yılda hareketi olanlar", font=('Arial', 9), bg='#ECEFF1').pack(side=tk.LEFT)

        # Scrollable tablo için canvas
        self.muadil_canvas = tk.Canvas(self.muadil_frame, bg='#ECEFF1', highlightthickness=0)
        self.muadil_scrollbar_y = ttk.Scrollbar(self.muadil_frame, orient='vertical',
                                                 command=self.muadil_canvas.yview)
        self.muadil_scrollbar_x = ttk.Scrollbar(self.muadil_frame, orient='horizontal',
                                                 command=self.muadil_canvas.xview)
        self.muadil_table_frame = tk.Frame(self.muadil_canvas, bg='#ECEFF1')

        self.muadil_canvas.configure(yscrollcommand=self.muadil_scrollbar_y.set,
                                     xscrollcommand=self.muadil_scrollbar_x.set)
        self.muadil_scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.muadil_scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.muadil_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.muadil_canvas_window = self.muadil_canvas.create_window((0, 0),
                                                                      window=self.muadil_table_frame, anchor='nw')

        self.muadil_table_frame.bind('<Configure>',
            lambda e: self.muadil_canvas.configure(scrollregion=self.muadil_canvas.bbox('all')))

        # Başlangıç mesajı
        tk.Label(self.muadil_table_frame, text="İlaç seçince muadiller görünecek...",
                font=('Arial', 11), bg='#ECEFF1', fg='#999').pack(pady=30)

    def _grup_toplami_kullan(self):
        """Tüm muadillerin toplam stok ve aylık gidişini kullan"""
        if not hasattr(self, 'muadil_veriler') or not self.muadil_veriler:
            messagebox.showwarning("Uyarı", "Önce bir ilaç seçin!")
            return

        # Toplam stok ve aylık gidiş hesapla
        toplam_stok = sum(v['Stok'] for v in self.muadil_veriler)
        toplam_ort = sum(v['AylikOrt'] for v in self.muadil_veriler)

        # Form alanlarına yaz
        self.stok.set(toplam_stok)
        self.aylik_ort.set(round(toplam_ort, 1))

        # Önerilen sipariş hesapla
        self._onerilen_siparis_hesapla()

        # Seçilen ilaç bilgisi etiketi
        self.secili_ilac_label.config(
            text=f"✓ GRUP TOPLAMI S:{toplam_stok}",
            fg='#1565C0'
        )

        # Tüm seçimleri kaldır
        for v in self.muadil_veriler:
            v['Secili'] = False

        # Tabloyu yeniden çiz
        ay_sayisi = self.ay_sayisi.get()
        self._muadil_tablo_doldur(self.muadil_veriler, ay_sayisi)

    def _muadil_verileri_getir(self, urun_id):
        """Seçilen ilacın muadillerinin aylık gidiş verilerini getir"""
        logger.info(f"_muadil_verileri_getir çağrıldı: UrunId={urun_id}")

        # Thread-safe: değerleri thread başlamadan önce al
        ay_sayisi = self.ay_sayisi.get()
        hareket_yili = self.hareket_yili.get()

        def getir():
            # Thread için ayrı DB bağlantısı oluştur
            try:
                from botanik_db import BotanikDB
                thread_db = BotanikDB()
                if not thread_db.baglan():
                    logger.error("Muadil thread DB bağlantısı kurulamadı")
                    self.parent.after(0, lambda: self._muadil_tablo_temizle("DB bağlantı hatası"))
                    return
            except Exception as e:
                logger.error(f"Muadil thread DB oluşturma hatası: {e}")
                self.parent.after(0, lambda: self._muadil_tablo_temizle("DB hatası"))
                return

            try:
                logger.info(f"Muadil veriler thread başladı: UrunId={urun_id}, AySayisi={ay_sayisi}, HareketYili={hareket_yili}")
                bugun = date.today()
                hareket_baslangic = (bugun - relativedelta(years=hareket_yili)).strftime('%Y-%m-%d')

                # Önce ilacın eşdeğer grubunu bul
                sql_esdeger = f"""
                SELECT UrunEsdegerId FROM Urun WHERE UrunId = {urun_id} AND UrunSilme = 0
                """
                sonuc = thread_db.sorgu_calistir(sql_esdeger)
                logger.info(f"Eşdeğer sorgu sonucu: {sonuc}")

                if not sonuc or not sonuc[0]['UrunEsdegerId']:
                    logger.warning(f"Eşdeğer grup bulunamadı: UrunId={urun_id}")
                    self.parent.after(0, lambda: self._muadil_tablo_temizle("Eşdeğer grup bulunamadı"))
                    return

                esdeger_id = sonuc[0]['UrunEsdegerId']
                logger.info(f"EsdegerId={esdeger_id}")

                # Aynı gruptaki son N yılda hareketi olan ilaçları getir
                sql_muadiller = f"""
                SELECT
                    u.UrunId,
                    u.UrunAdi,
                    CASE WHEN u.UrunUrunTipId IN (1, 16) THEN
                        (SELECT COUNT(*) FROM Karekod kk WHERE kk.KKUrunId = u.UrunId AND kk.KKDurum = 1)
                    ELSE (COALESCE(u.UrunStokDepo,0) + COALESCE(u.UrunStokRaf,0) + COALESCE(u.UrunStokAcik,0))
                    END AS Stok
                FROM Urun u
                WHERE u.UrunEsdegerId = {esdeger_id}
                AND u.UrunSilme = 0
                AND (
                    -- Son N yılda reçete satışı olan
                    EXISTS (
                        SELECT 1 FROM ReceteIlaclari ri
                        JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
                        WHERE ri.RIUrunId = u.UrunId
                        AND ra.RxSilme = 0 AND ri.RISilme = 0
                        AND CAST(ra.RxKayitTarihi as date) >= '{hareket_baslangic}'
                    )
                    OR
                    -- Veya elden satışı olan
                    EXISTS (
                        SELECT 1 FROM EldenIlaclari ei
                        JOIN EldenAna ea ON ei.RIRxId = ea.RxId
                        WHERE ei.RIUrunId = u.UrunId
                        AND ea.RxSilme = 0 AND ei.RISilme = 0
                        AND CAST(ea.RxKayitTarihi as date) >= '{hareket_baslangic}'
                    )
                    OR
                    -- Veya seçili ilaç ise (her zaman göster)
                    u.UrunId = {urun_id}
                )
                ORDER BY u.UrunAdi
                """
                muadiller = thread_db.sorgu_calistir(sql_muadiller)
                logger.info(f"Muadil sayısı (son {hareket_yili} yıl): {len(muadiller) if muadiller else 0}")

                if not muadiller:
                    logger.warning(f"Muadil ilaç bulunamadı: EsdegerId={esdeger_id}")
                    self.parent.after(0, lambda: self._muadil_tablo_temizle("Muadil ilaç bulunamadı"))
                    return

                # Her muadil için aylık satış verilerini hesapla
                muadil_veriler = []
                for muadil in muadiller:
                    m_id = muadil['UrunId']
                    m_adi = muadil['UrunAdi']
                    m_stok = int(muadil['Stok'] or 0)

                    # Son N ayın aylık çıkışları
                    aylik_cikislar = []
                    toplam = 0

                    for i in range(ay_sayisi):
                        ay_baslangic = (bugun - relativedelta(months=i)).replace(day=1)
                        if i == 0:
                            ay_bitis = bugun
                        else:
                            ay_bitis = (ay_baslangic + relativedelta(months=1)) - relativedelta(days=1)

                        baslangic_str = ay_baslangic.strftime('%Y-%m-%d')
                        bitis_str = (ay_bitis + relativedelta(days=1)).strftime('%Y-%m-%d')

                        sql_aylik = f"""
                        SELECT
                            (SELECT COALESCE(SUM(ri.RIAdet), 0)
                             FROM ReceteIlaclari ri
                             JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
                             WHERE ri.RIUrunId = {m_id}
                             AND ra.RxSilme = 0 AND ri.RISilme = 0
                             AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
                             AND CAST(ra.RxKayitTarihi as date) >= '{baslangic_str}'
                             AND CAST(ra.RxKayitTarihi as date) < '{bitis_str}')
                            +
                            (SELECT COALESCE(SUM(ei.RIAdet), 0)
                             FROM EldenIlaclari ei
                             JOIN EldenAna ea ON ei.RIRxId = ea.RxId
                             WHERE ei.RIUrunId = {m_id}
                             AND ea.RxSilme = 0 AND ei.RISilme = 0
                             AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
                             AND CAST(ea.RxKayitTarihi as date) >= '{baslangic_str}'
                             AND CAST(ea.RxKayitTarihi as date) < '{bitis_str}')
                        AS AylikCikis
                        """
                        aylik_sonuc = thread_db.sorgu_calistir(sql_aylik)
                        cikis = int(aylik_sonuc[0]['AylikCikis'] or 0) if aylik_sonuc else 0
                        aylik_cikislar.append(cikis)
                        toplam += cikis

                    # Aylık ortalama (efektif ay sayısı ile - bu ay tam değil)
                    ay_basi = bugun.replace(day=1)
                    bu_ay_gecen_gun = (bugun - ay_basi).days + 1
                    efektif_ay_sayisi = (ay_sayisi - 1) + (bu_ay_gecen_gun / 30)
                    aylik_ort = toplam / efektif_ay_sayisi if efektif_ay_sayisi > 0 else 0

                    muadil_veriler.append({
                        'UrunId': m_id,
                        'UrunAdi': m_adi,
                        'Stok': m_stok,
                        'AylikCikislar': aylik_cikislar,  # [Bu ay, -1 ay, -2 ay, ...]
                        'Toplam': toplam,
                        'AylikOrt': aylik_ort,
                        'Secili': m_id == urun_id
                    })

                # Tabloya göster (lambda closure fix: değişkenleri parametre olarak geç)
                logger.info(f"Muadil tablo dolduruluyor: {len(muadil_veriler)} ilaç")
                self.parent.after(0, lambda mv=muadil_veriler, ay=ay_sayisi: self._muadil_tablo_doldur(mv, ay))

            except Exception as e:
                logger.error(f"Muadil verileri getirme hatası: {e}")
                import traceback
                traceback.print_exc()
                self.parent.after(0, lambda err=str(e)[:30]: self._muadil_tablo_temizle(f"Hata: {err}"))
            finally:
                # Thread DB bağlantısını kapat
                try:
                    thread_db.kapat()
                except:
                    pass

        threading.Thread(target=getir, daemon=True).start()

    def _muadil_tablo_temizle(self, mesaj=""):
        """Muadil tablosunu temizle"""
        for widget in self.muadil_table_frame.winfo_children():
            widget.destroy()
        if mesaj:
            tk.Label(self.muadil_table_frame, text=mesaj,
                    font=('Arial', 11), bg='#ECEFF1', fg='#999').pack(pady=30)

    def _muadil_tablo_doldur(self, veriler, ay_sayisi):
        """Muadil aylık gidiş tablosunu doldur - Tıklanabilir satırlar"""
        # Temizle
        for widget in self.muadil_table_frame.winfo_children():
            widget.destroy()

        if not veriler:
            tk.Label(self.muadil_table_frame, text="Veri yok",
                    font=('Arial', 11), bg='#ECEFF1', fg='#999').pack(pady=30)
            return

        # Muadil verilerini sakla (tıklama için)
        self.muadil_veriler = veriler

        bugun = date.today()

        # Başlık satırı
        baslik_frame = tk.Frame(self.muadil_table_frame, bg='#1565C0')
        baslik_frame.pack(fill=tk.X)

        # Sabit sütunlar
        tk.Label(baslik_frame, text="İlaç (tıkla seç)", font=('Arial', 10, 'bold'),
                width=25, bg='#1565C0', fg='white', anchor='w', padx=5).pack(side=tk.LEFT)
        tk.Label(baslik_frame, text="Stok", font=('Arial', 10, 'bold'),
                width=6, bg='#1565C0', fg='white').pack(side=tk.LEFT)

        # Ay sütunları (son N ay)
        for i in range(ay_sayisi):  # Max 6 ay göster
            ay_tarihi = bugun - relativedelta(months=i)
            ay_adi = ay_tarihi.strftime("%b")
            tk.Label(baslik_frame, text=ay_adi, font=('Arial', 10, 'bold'),
                    width=5, bg='#1565C0', fg='white').pack(side=tk.LEFT)

        tk.Label(baslik_frame, text="Top", font=('Arial', 10, 'bold'),
                width=6, bg='#1565C0', fg='white').pack(side=tk.LEFT)
        tk.Label(baslik_frame, text="Ort", font=('Arial', 10, 'bold'),
                width=6, bg='#1565C0', fg='white').pack(side=tk.LEFT)

        # Veri satırları
        toplam_stok = 0
        toplam_satis = 0
        toplam_ort = 0
        self.muadil_rows = []  # Satırları sakla (seçim için)

        for idx, veri in enumerate(veriler):
            row_bg = '#C8E6C9' if veri['Secili'] else '#ECEFF1'
            row = tk.Frame(self.muadil_table_frame, bg=row_bg)
            row.pack(fill=tk.X)

            # Satırı tıklanabilir yap
            row.bind('<Button-1>', lambda e, i=idx: self._muadil_satir_secildi(i))
            row.bind('<Enter>', lambda e, r=row: r.config(bg='#BBDEFB') if not veriler[self.muadil_rows.index(r) if r in self.muadil_rows else 0].get('Secili') else None)
            row.bind('<Leave>', lambda e, r=row, i=idx: r.config(bg='#C8E6C9' if veriler[i]['Secili'] else '#ECEFF1'))

            self.muadil_rows.append(row)

            # İlaç adı (kısaltılmış)
            ilac_adi = veri['UrunAdi'][:28] + ".." if len(veri['UrunAdi']) > 30 else veri['UrunAdi']
            lbl_adi = tk.Label(row, text=ilac_adi, font=('Arial', 9, 'bold' if veri['Secili'] else 'normal'),
                    width=25, bg=row_bg, anchor='w', cursor='hand2', padx=5)
            lbl_adi.pack(side=tk.LEFT)
            lbl_adi.bind('<Button-1>', lambda e, i=idx: self._muadil_satir_secildi(i))

            # Stok
            lbl_stok = tk.Label(row, text=str(veri['Stok']), font=('Arial', 9),
                    width=6, bg=row_bg, cursor='hand2')
            lbl_stok.pack(side=tk.LEFT)
            lbl_stok.bind('<Button-1>', lambda e, i=idx: self._muadil_satir_secildi(i))

            # Aylık çıkışlar
            for j in range(ay_sayisi):
                cikis = veri['AylikCikislar'][j] if j < len(veri['AylikCikislar']) else 0
                lbl_cikis = tk.Label(row, text=str(cikis), font=('Arial', 9),
                        width=5, bg=row_bg, cursor='hand2')
                lbl_cikis.pack(side=tk.LEFT)
                lbl_cikis.bind('<Button-1>', lambda e, i=idx: self._muadil_satir_secildi(i))

            # Toplam
            lbl_top = tk.Label(row, text=str(veri['Toplam']), font=('Arial', 9, 'bold'),
                    width=6, bg=row_bg, cursor='hand2')
            lbl_top.pack(side=tk.LEFT)
            lbl_top.bind('<Button-1>', lambda e, i=idx: self._muadil_satir_secildi(i))

            # Aylık ortalama
            lbl_ort = tk.Label(row, text=f"{veri['AylikOrt']:.0f}", font=('Arial', 9, 'bold'),
                    width=6, bg=row_bg, cursor='hand2', fg='#1565C0')
            lbl_ort.pack(side=tk.LEFT)
            lbl_ort.bind('<Button-1>', lambda e, i=idx: self._muadil_satir_secildi(i))

            toplam_stok += veri['Stok']
            toplam_satis += veri['Toplam']
            toplam_ort += veri['AylikOrt']

        # Toplam satırı
        toplam_row = tk.Frame(self.muadil_table_frame, bg='#1976D2')
        toplam_row.pack(fill=tk.X, pady=(3, 0))

        tk.Label(toplam_row, text="TOPLAM", font=('Arial', 10, 'bold'),
                width=25, bg='#1976D2', fg='white', anchor='w', padx=5).pack(side=tk.LEFT)
        tk.Label(toplam_row, text=str(toplam_stok), font=('Arial', 10, 'bold'),
                width=6, bg='#1976D2', fg='white').pack(side=tk.LEFT)

        # Boşluk (ay sütunları için)
        for i in range(ay_sayisi):
            tk.Label(toplam_row, text="", width=5, bg='#1976D2').pack(side=tk.LEFT)

        tk.Label(toplam_row, text=str(toplam_satis), font=('Arial', 10, 'bold'),
                width=6, bg='#1976D2', fg='white').pack(side=tk.LEFT)
        tk.Label(toplam_row, text=f"{toplam_ort:.0f}", font=('Arial', 10, 'bold'),
                width=6, bg='#1976D2', fg='#FFEB3B').pack(side=tk.LEFT)

        # Grup toplam aylık gidişi güncelle
        self.grup_aylik_label.config(text=f"{toplam_ort:.0f} ad/ay (Stok: {toplam_stok})")

    def _muadil_satir_secildi(self, idx):
        """Muadil tablosunda bir satır seçildi - değerleri form alanlarına yaz"""
        if not hasattr(self, 'muadil_veriler') or idx >= len(self.muadil_veriler):
            return

        veri = self.muadil_veriler[idx]

        # Seçili satırı güncelle
        for i, v in enumerate(self.muadil_veriler):
            v['Secili'] = (i == idx)

        # Form alanlarını güncelle
        self.stok.set(veri['Stok'])
        self.aylik_ort.set(round(veri['AylikOrt'], 1))

        # NOT: Önerilen sipariş, fiyat geldikten sonra _ilac_fiyat_getir içinde hesaplanacak

        # Seçilen ilaç bilgisi etiketi
        self.secili_ilac_label.config(
            text=f"✓ {veri['UrunAdi'][:15]}.. S:{veri['Stok']}",
            fg='#2E7D32'
        )

        # Combobox'ı da güncelle
        self.ilac_combo.set(veri['UrunAdi'])

        # İlacın fiyat bilgisini getir (veritabanından)
        if self.db:
            self._ilac_fiyat_getir(veri['UrunId'])

        # Tabloyu yeniden çiz (seçimi göstermek için)
        ay_sayisi = self.ay_sayisi.get()
        self._muadil_tablo_doldur(self.muadil_veriler, ay_sayisi)

    def _ilac_fiyat_getir(self, urun_id):
        """İlacın depocu fiyatını veritabanından getir (thread-safe)"""
        def getir():
            # Thread için ayrı DB bağlantısı oluştur
            try:
                from botanik_db import BotanikDB
                thread_db = BotanikDB()
                if not thread_db.baglan():
                    logger.error("Fiyat thread DB bağlantısı kurulamadı")
                    return
            except Exception as e:
                logger.error(f"Fiyat thread DB oluşturma hatası: {e}")
                return

            try:
                sql = f"""
                SELECT
                    u.UrunFiyatEtiket AS PSF,
                    u.UrunIskontoKamu AS IskontoYuzde,
                    u.UrunIskontoYedek AS DepocuKDVHaric
                FROM Urun u
                WHERE u.UrunId = {urun_id}
                """
                sonuc = thread_db.sorgu_calistir(sql)
                if sonuc:
                    depocu_kdv_haric = float(sonuc[0].get('DepocuKDVHaric', 0) or 0)
                    psf = float(sonuc[0].get('PSF', 0) or 0)
                    iskonto_yuzde = float(sonuc[0].get('IskontoYuzde', 0) or 0)

                    if depocu_kdv_haric > 0:
                        # Doğrudan KDV hariç depocu fiyatı var
                        depocu = depocu_kdv_haric * 1.10
                    elif psf > 0:
                        # PSF üzerinden hesapla
                        depocu = psf * 0.71 * 1.10 * (1 - iskonto_yuzde / 100)
                    else:
                        depocu = 0

                    if depocu > 0:
                        # Fiyatı güncelle ve ardından önerilen siparişi hesapla
                        def guncelle():
                            self.maliyet.set(round(depocu, 2))
                            self._onerilen_siparis_hesapla()
                        self.parent.after(0, guncelle)
                    else:
                        logger.warning(f"Depocu fiyat hesaplanamadı: UrunId={urun_id}")
            except Exception as e:
                logger.error(f"İlaç fiyat getirme hatası: {e}")
            finally:
                try:
                    thread_db.kapat()
                except:
                    pass

        threading.Thread(target=getir, daemon=True).start()

    def _sonuc_panel_olustur(self, parent):
        """Sonuç paneli - MF Karşılaştırma"""
        sonuc_frame = tk.LabelFrame(parent, text="MF Karşılaştırma", font=('Arial', 11, 'bold'),
                                    bg='#ECEFF1', padx=10, pady=10)
        sonuc_frame.pack(fill=tk.X, pady=(0, 5))

        # Bilgi satırı
        self.bilgi_label = tk.Label(sonuc_frame, text="İlaç seçin veya parametreleri girin, HESAPLA'ya basın",
                                   font=('Arial', 10), bg='#ECEFF1', fg='#555')
        self.bilgi_label.pack(anchor='w', pady=(0, 10))

        # Stok fazlalığı uyarısı
        self.fazla_frame = tk.Frame(sonuc_frame, bg='#FFCDD2')
        self.fazla_label = tk.Label(self.fazla_frame, text="", font=('Arial', 9, 'bold'),
                                   bg='#FFCDD2', fg='#C62828')
        self.fazla_label.pack(anchor='w', padx=5, pady=3)

        # Sonuç tablosu
        self.sonuc_table_frame = tk.Frame(sonuc_frame, bg='#ECEFF1')
        self.sonuc_table_frame.pack(fill=tk.BOTH, expand=True)

        # Başlangıç mesajı
        tk.Label(self.sonuc_table_frame, text="Sonuçlar burada görünecek...",
                font=('Arial', 11), bg='#ECEFF1', fg='#999').pack(pady=50)

    def _nakit_akis_panel_olustur(self, parent):
        """Nakit Akış Tablosu paneli - Ay be ay karşılaştırma"""
        self.nakit_frame = tk.LabelFrame(parent, text="Nakit Akış Analizi (Ay be Ay)",
                                         font=('Arial', 11, 'bold'),
                                         bg='#ECEFF1', padx=5, pady=10)
        self.nakit_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollable tablo için canvas
        self.nakit_canvas = tk.Canvas(self.nakit_frame, bg='#ECEFF1', highlightthickness=0)
        self.nakit_scrollbar = ttk.Scrollbar(self.nakit_frame, orient='vertical',
                                              command=self.nakit_canvas.yview)
        self.nakit_table_frame = tk.Frame(self.nakit_canvas, bg='#ECEFF1')

        self.nakit_canvas.configure(yscrollcommand=self.nakit_scrollbar.set)
        self.nakit_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.nakit_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.nakit_canvas_window = self.nakit_canvas.create_window((0, 0), window=self.nakit_table_frame, anchor='nw')

        # Canvas resize binding
        self.nakit_table_frame.bind('<Configure>',
            lambda e: self.nakit_canvas.configure(scrollregion=self.nakit_canvas.bbox('all')))
        self.nakit_canvas.bind('<Configure>',
            lambda e: self.nakit_canvas.itemconfig(self.nakit_canvas_window, width=e.width))

        # Başlangıç mesajı
        tk.Label(self.nakit_table_frame, text="Hesapla'ya basın...",
                font=('Arial', 10), bg='#ECEFF1', fg='#999').pack(pady=30)

    def _nakit_akis_tablosu_doldur(self, stok, aylik_ort, maliyet, faiz_yillik, depo_vade,
                                    siparis_miktar, mf_al=0, mf_bedava=0, zam_gun=0, zam_orani=0):
        """
        Nakit akış tablosunu doldur - 12 aylık karşılaştırma

        ÖNEMLİ: Ödeme zamanlaması takvimsel hesaplanır.
        - Bu ay yapılan sipariş → sonraki ayın 1'inde senet → +75 gün sonra ödeme
        - Yani Şubat siparişinin ödemesi Mayıs'ta yapılır (~90 gün sonra)
        - İlk 2-3 ay "Ödeme" sütunu 0 gösterir (henüz vade dolmadı)
        """
        # Temizle
        for widget in self.nakit_table_frame.winfo_children():
            widget.destroy()

        if aylik_ort <= 0 or maliyet <= 0:
            tk.Label(self.nakit_table_frame, text="Geçerli değerler girin",
                    font=('Arial', 10), bg='#ECEFF1', fg='#C62828').pack(pady=30)
            return

        # Hesaplama parametreleri
        aylik_faiz = (faiz_yillik / 100) / 12
        gunluk_faiz = (1 + aylik_faiz) ** (1/30) - 1
        bugun = date.today()

        # Toplu alım miktarı
        toplam_toplu = mf_al + mf_bedava if mf_al > 0 else siparis_miktar
        toplu_odeme_tutari = mf_al * maliyet if mf_al > 0 else siparis_miktar * maliyet

        # Mevcut stok fazlalığı hesapla (MF Karşılaştır ile tutarlılık için)
        stok_fazlaligi = self._mevcut_stok_fazlaligi_hesapla(stok, aylik_ort, maliyet, faiz_yillik, depo_vade)
        fazla_maliyet = stok_fazlaligi['fazla_maliyet']
        fazla_adet = stok_fazlaligi['fazla_adet']

        # ═══════════════════════════════════════════════════════════════════
        # STOK BİTİŞ TARİHİ HESAPLA (GÜN HASSASİYETİNDE)
        # ═══════════════════════════════════════════════════════════════════

        toplam_stok_baslangic = stok + toplam_toplu
        gunluk_sarf = aylik_ort / 30 if aylik_ort > 0 else 0

        if gunluk_sarf > 0 and toplam_stok_baslangic > 0:
            bitis_gun_sayisi = int(toplam_stok_baslangic / gunluk_sarf)
            bitis_tarihi = bugun + timedelta(days=bitis_gun_sayisi)
        else:
            bitis_gun_sayisi = 30
            bitis_tarihi = bugun + timedelta(days=30)

        # Toplu alım ödeme tarihi
        toplu_odeme_gun = self._odeme_gun_hesapla(0, depo_vade)
        toplu_odeme_tarihi = bugun + timedelta(days=toplu_odeme_gun)
        toplu_odeme_ayi = (toplu_odeme_tarihi.year - bugun.year) * 12 + (toplu_odeme_tarihi.month - bugun.month)

        # ═══════════════════════════════════════════════════════════════════
        # 1. AŞAMA: Önce TÜM siparişleri ve ödeme tarihlerini hesapla
        # ═══════════════════════════════════════════════════════════════════

        # Stok bitiş tarihine kadar olan dönemleri hesapla
        stok_donemler = []
        ay_index = 0
        donem_baslangic = bugun

        while donem_baslangic <= bitis_tarihi and ay_index < 24:
            ay_tarihi = bugun + relativedelta(months=ay_index)

            if ay_index == 0:
                ay_bas = bugun
            else:
                ay_bas = date(ay_tarihi.year, ay_tarihi.month, 1)

            ay_son_gun = calendar.monthrange(ay_tarihi.year, ay_tarihi.month)[1]
            ay_son = date(ay_tarihi.year, ay_tarihi.month, ay_son_gun)

            if ay_son > bitis_tarihi:
                ay_son = bitis_tarihi

            gun_sayisi = (ay_son - ay_bas).days + 1
            tuketim = gunluk_sarf * gun_sayisi

            stok_donemler.append({
                'ay_index': ay_index,
                'ay_tarihi': ay_tarihi,
                'ay_bas': ay_bas,
                'ay_son': ay_son,
                'gun_sayisi': gun_sayisi,
                'tuketim': tuketim
            })

            if ay_son >= bitis_tarihi:
                break

            ay_index += 1
            donem_baslangic = ay_son + timedelta(days=1)

        # Normal senaryo siparişleri hesapla (stok bitiş tarihine kadar)
        normal_siparisler = []
        normal_kalan_mevcut = stok

        for donem in stok_donemler:
            ay_index = donem['ay_index']
            ay_tarihi = donem['ay_tarihi']
            tuketim = donem['tuketim']

            # Mevcut stoktan karşılanan
            mevcut_kullanim = min(normal_kalan_mevcut, tuketim)
            normal_kalan_mevcut -= mevcut_kullanim

            # Bu dönem sipariş edilmesi gereken
            siparis = tuketim - mevcut_kullanim
            if siparis > 0:
                # Zam kontrolü
                gun_offset = (donem['ay_bas'] - bugun).days
                if zam_orani > 0 and gun_offset >= zam_gun:
                    tutar = siparis * maliyet * (1 + zam_orani / 100)
                else:
                    tutar = siparis * maliyet

                # Ödeme tarihi hesapla (takvimsel)
                senet_tarihi = self._senet_tarihi_bul(ay_tarihi)
                odeme_tarihi = senet_tarihi + timedelta(days=depo_vade)
                odeme_gun = (odeme_tarihi - bugun).days
                odeme_ayi = (odeme_tarihi.year - bugun.year) * 12 + (odeme_tarihi.month - bugun.month)

                normal_siparisler.append({
                    'siparis_ayi': ay_index,
                    'siparis': siparis,
                    'tutar': tutar,
                    'odeme_ayi': odeme_ayi,
                    'odeme_gun': odeme_gun,
                    'odeme_tarihi': odeme_tarihi
                })

        # ═══════════════════════════════════════════════════════════════════
        # 2. AŞAMA: Tüm ödemeleri kapsayacak şekilde dönemleri genişlet
        # ═══════════════════════════════════════════════════════════════════

        # Normal senaryonun son ödeme tarihi
        if normal_siparisler:
            normal_son_odeme = max(s['odeme_tarihi'] for s in normal_siparisler)
        else:
            normal_son_odeme = bitis_tarihi

        # Gösterilecek son tarih: Tüm ödemelerin bittiği tarih
        son_tarih = max(bitis_tarihi, toplu_odeme_tarihi, normal_son_odeme)

        # Tüm dönemleri oluştur (stok bitişinden sonra da devam et, ödeme aylarını göstermek için)
        aylik_donemler = []
        ay_index = 0

        while ay_index < 24:
            ay_tarihi = bugun + relativedelta(months=ay_index)

            if ay_index == 0:
                ay_bas = bugun
            else:
                ay_bas = date(ay_tarihi.year, ay_tarihi.month, 1)

            ay_son_gun = calendar.monthrange(ay_tarihi.year, ay_tarihi.month)[1]
            ay_son = date(ay_tarihi.year, ay_tarihi.month, ay_son_gun)

            # Bu dönemde stok kullanımı var mı?
            stok_aktif = ay_bas <= bitis_tarihi

            # Bu ay için tüketim (stok varsa)
            if stok_aktif:
                # stok_donemler'den al (daha önce hesaplandı)
                stok_donem = next((d for d in stok_donemler if d['ay_index'] == ay_index), None)
                if stok_donem:
                    tuketim = stok_donem['tuketim']
                    gun_sayisi = stok_donem['gun_sayisi']
                    ay_son = stok_donem['ay_son']  # Stok bitiş tarihine göre kısaltılmış olabilir
                else:
                    tuketim = 0
                    gun_sayisi = (ay_son - ay_bas).days + 1
            else:
                tuketim = 0
                gun_sayisi = (ay_son - ay_bas).days + 1

            aylik_donemler.append({
                'ay_index': ay_index,
                'ay_tarihi': ay_tarihi,
                'ay_bas': ay_bas,
                'ay_son': ay_son,
                'gun_sayisi': gun_sayisi,
                'tuketim': tuketim,
                'stok_aktif': stok_aktif
            })

            # Son ödeme tarihini geçtiyse dur
            if ay_son >= son_tarih:
                break

            ay_index += 1

        # ═══════════════════════════════════════════════════════════════════
        # BAŞLIK SATIRLARI
        # ═══════════════════════════════════════════════════════════════════

        # Üst başlık: Grup isimleri
        ust_baslik = tk.Frame(self.nakit_table_frame, bg='#0D47A1')
        ust_baslik.pack(fill=tk.X)

        tk.Label(ust_baslik, text="", width=10, bg='#0D47A1').pack(side=tk.LEFT)  # Ay + Tüketim
        tk.Label(ust_baslik, text="──── AY BE AY ALIM ────", font=('Arial', 9, 'bold'),
                width=24, bg='#0D47A1', fg='#BBDEFB').pack(side=tk.LEFT)
        tk.Label(ust_baslik, text="──── TOPLU ALIM (MF/Zam) ────", font=('Arial', 9, 'bold'),
                width=24, bg='#0D47A1', fg='#C8E6C9').pack(side=tk.LEFT)
        tk.Label(ust_baslik, text="", width=7, bg='#0D47A1').pack(side=tk.LEFT)

        # Alt başlık: Sütun isimleri
        alt_baslik = tk.Frame(self.nakit_table_frame, bg='#1565C0')
        alt_baslik.pack(fill=tk.X, pady=(0, 2))

        basliklar = [
            ("Ay", 6), ("Tüketim", 5),
            ("Sipariş", 5), ("Öd.Ayı", 5), ("Ödeme", 7), ("NPV", 6),
            ("Kullanım", 6), ("Kalan", 5), ("Ödeme", 7), ("NPV", 6),
            ("AVANTAJ", 7)
        ]
        for baslik, w in basliklar:
            tk.Label(alt_baslik, text=baslik, font=('Arial', 8, 'bold'),
                    width=w, bg='#1565C0', fg='white', anchor='center').pack(side=tk.LEFT, padx=0)

        # ═══════════════════════════════════════════════════════════════════
        # 3. AŞAMA: Her dönem için tabloyu doldur (tüm ödemeler bitene kadar)
        # ═══════════════════════════════════════════════════════════════════

        # Toplu senaryo stok takibi
        toplu_kalan_mevcut = stok
        toplu_kalan_yeni = toplam_toplu

        toplam_normal_npv = 0
        toplam_toplu_npv = 0

        # Stok bitiş bilgisi başlıkta göster
        bitis_bilgi = tk.Frame(self.nakit_table_frame, bg='#FFF3E0')
        bitis_bilgi.pack(fill=tk.X, pady=(0, 3))
        tk.Label(bitis_bilgi,
                text=f"📅 Stok Bitiş: {bitis_tarihi.strftime('%d %b %Y')} ({bitis_gun_sayisi} gün) | Toplam: {toplam_stok_baslangic:.0f} adet",
                font=('Arial', 9), bg='#FFF3E0', fg='#E65100').pack(pady=2)

        for donem in aylik_donemler:
            ay_index = donem['ay_index']
            ay_tarihi = donem['ay_tarihi']
            sarf = donem['tuketim']  # Bu dönemin tüketimi (son ay kısmi olabilir)
            gun_sayisi = donem['gun_sayisi']

            # Stok aktif mi?
            stok_aktif = donem.get('stok_aktif', True)

            # Bu dönemin siparişi
            bu_ayin_siparisi = next((s for s in normal_siparisler if s['siparis_ayi'] == ay_index), None)
            normal_siparis = bu_ayin_siparisi['siparis'] if bu_ayin_siparisi else 0

            # Bu ayda ÖDENEN tutar (önceki dönemlerin siparişlerinin ödemeleri)
            bu_ayda_odenen = sum(s['tutar'] for s in normal_siparisler if s['odeme_ayi'] == ay_index)

            # Bu dönemde toplu ödeme var mı?
            toplu_odeme_bu_ay = (ay_index == toplu_odeme_ayi)

            # Boş satırları atla: stok aktif değilse VE ödeme yoksa
            if not stok_aktif and bu_ayda_odenen == 0 and not toplu_odeme_bu_ay:
                continue

            # Ay adı (son ay ise tarih aralığı göster)
            if stok_aktif and donem['ay_son'] == bitis_tarihi and gun_sayisi < 28:
                ay_adi = f"{ay_tarihi.strftime('%b')}({gun_sayisi}g)"
            else:
                ay_adi = ay_tarihi.strftime("%b %y")

            # ─────────────────────────────────────────────────────────────
            # NORMAL SENARYO: Bu dönemde yapılan sipariş ve ödeme
            # ─────────────────────────────────────────────────────────────

            # Bu ayda ödenen tutarların NPV'si
            bu_ayda_odenen_npv = 0
            for s in normal_siparisler:
                if s['odeme_ayi'] == ay_index:
                    npv = s['tutar'] / ((1 + gunluk_faiz) ** s['odeme_gun'])
                    bu_ayda_odenen_npv += npv
                    toplam_normal_npv += npv

            # ─────────────────────────────────────────────────────────────
            # TOPLU SENARYO: Stok kullanımı ve ödeme
            # ─────────────────────────────────────────────────────────────

            # Önce mevcut stoktan, sonra yeni stoktan tüket
            toplu_mevcut_kullanim = min(toplu_kalan_mevcut, sarf)
            toplu_kalan_mevcut -= toplu_mevcut_kullanim

            toplu_yeni_kullanim = min(toplu_kalan_yeni, sarf - toplu_mevcut_kullanim)
            toplu_kalan_yeni -= toplu_yeni_kullanim

            toplu_kullanim = toplu_mevcut_kullanim + toplu_yeni_kullanim

            # Toplu ödeme: Sadece ödeme ayında göster
            toplu_ay_odeme = 0
            toplu_ay_npv = 0

            if ay_index == toplu_odeme_ayi:
                toplu_ay_odeme = toplu_odeme_tutari
                toplu_ay_npv = toplu_odeme_tutari / ((1 + gunluk_faiz) ** toplu_odeme_gun)
                toplam_toplu_npv += toplu_ay_npv

            # ─────────────────────────────────────────────────────────────
            # FARK (bu aydaki nakit çıkışı farkı - NPV bazlı)
            # ─────────────────────────────────────────────────────────────
            # NOT: Fırsat maliyeti KALDIRILDI çünkü NPV zaten paranın zaman
            # değerini hesaba katıyor. Fırsat maliyeti eklemek çift sayım olur.
            # ─────────────────────────────────────────────────────────────
            fark = bu_ayda_odenen_npv - toplu_ay_npv

            # ─────────────────────────────────────────────────────────────
            # SATIR ÇİZ
            # ─────────────────────────────────────────────────────────────
            toplam_kalan = toplu_kalan_mevcut + toplu_kalan_yeni

            # Satır rengi belirleme
            if not stok_aktif:
                # Stok bittikten sonraki dönemler (sadece ödeme göstermek için)
                if ay_index == toplu_odeme_ayi:
                    row_bg = '#FFECB3'  # Toplu ödeme ayı
                elif bu_ayda_odenen > 0:
                    row_bg = '#E3F2FD'  # Normal ödeme ayı
                else:
                    row_bg = '#F5F5F5'  # Boş dönem (gri)
            elif ay_index == toplu_odeme_ayi:
                row_bg = '#FFECB3'  # Toplu ödeme ayı
            elif bu_ayda_odenen > 0:
                row_bg = '#E3F2FD'  # Normal ödeme ayı
            elif fark > 0:
                row_bg = '#C8E6C9'  # Toplu avantajlı
            elif fark < 0:
                row_bg = '#FFCDD2'  # Normal avantajlı
            else:
                row_bg = '#ECEFF1'

            row = tk.Frame(self.nakit_table_frame, bg=row_bg)
            row.pack(fill=tk.X, pady=0)

            # Ay ve Tüketim
            tk.Label(row, text=ay_adi, font=('Arial', 8), width=6, bg=row_bg, anchor='w').pack(side=tk.LEFT, padx=0)
            # Tüketim: Stok aktif değilse "-" göster
            tuketim_text = f"{sarf:.0f}" if stok_aktif and sarf > 0 else "-"
            tk.Label(row, text=tuketim_text, font=('Arial', 8), width=5, bg=row_bg,
                    fg='#666' if not stok_aktif else 'black').pack(side=tk.LEFT, padx=0)

            # ── AY BE AY ALIM ──
            # Sipariş miktarı
            tk.Label(row, text=f"{normal_siparis:.0f}" if normal_siparis > 0 else "-",
                    font=('Arial', 8), width=5, bg=row_bg).pack(side=tk.LEFT, padx=0)

            # Siparişin ödeme ayı (Öd.Ayı)
            if bu_ayin_siparisi and normal_siparis > 0:
                odeme_ay_tarihi = bugun + relativedelta(months=bu_ayin_siparisi['odeme_ayi'])
                odeme_ay_adi = odeme_ay_tarihi.strftime("%b")
                tk.Label(row, text=odeme_ay_adi, font=('Arial', 8), width=5, bg=row_bg, fg='#666').pack(side=tk.LEFT, padx=0)
            else:
                tk.Label(row, text="-", font=('Arial', 8), width=5, bg=row_bg).pack(side=tk.LEFT, padx=0)

            # Bu ayda ödenen tutar (nominal)
            tk.Label(row, text=f"{bu_ayda_odenen:.0f}" if bu_ayda_odenen > 0 else "-",
                    font=('Arial', 8), width=7, bg=row_bg).pack(side=tk.LEFT, padx=0)

            # Bu ayda ödenen tutar (NPV)
            tk.Label(row, text=f"{bu_ayda_odenen_npv:.0f}" if bu_ayda_odenen_npv > 0 else "-",
                    font=('Arial', 8), width=6, bg=row_bg, fg='#1565C0').pack(side=tk.LEFT, padx=0)

            # ── TOPLU ALIM ──
            # Kullanım ve Kalan: Stok aktif değilse "-" göster
            kullanim_text = f"{toplu_kullanim:.0f}" if stok_aktif and toplu_kullanim > 0 else "-"
            kalan_text = f"{toplam_kalan:.0f}" if stok_aktif else "-"
            tk.Label(row, text=kullanim_text,
                    font=('Arial', 8), width=6, bg=row_bg, fg='#666' if not stok_aktif else 'black').pack(side=tk.LEFT, padx=0)
            tk.Label(row, text=kalan_text,
                    font=('Arial', 8), width=5, bg=row_bg, fg='#666').pack(side=tk.LEFT, padx=0)

            # Toplu ödeme (nominal)
            tk.Label(row, text=f"{toplu_ay_odeme:.0f}" if toplu_ay_odeme > 0 else "-",
                    font=('Arial', 8), width=7, bg=row_bg).pack(side=tk.LEFT, padx=0)

            # Toplu ödeme (NPV)
            tk.Label(row, text=f"{toplu_ay_npv:.0f}" if toplu_ay_npv > 0 else "-",
                    font=('Arial', 8), width=6, bg=row_bg, fg='#2E7D32').pack(side=tk.LEFT, padx=0)

            # AVANTAJ (pozitif = toplu avantajlı, NPV bazlı)
            if abs(fark) > 0.5:  # Küçük farkları gösterme
                fark_renk = '#2E7D32' if fark > 0 else '#C62828'
                fark_text = f"{fark:+.0f}"
            else:
                fark_renk = '#666'
                fark_text = "-"
            tk.Label(row, text=fark_text, font=('Arial', 8, 'bold'),
                    width=7, bg=row_bg, fg=fark_renk).pack(side=tk.LEFT, padx=0)

        # ═══════════════════════════════════════════════════════════════════
        # ÖZET SATIRLARI
        # ═══════════════════════════════════════════════════════════════════

        # NPV karşılaştırması + Fazla stok fırsat maliyeti (MF Karşılaştır ile tutarlı)
        toplam_fark_saf = toplam_normal_npv - toplam_toplu_npv
        toplam_fark = toplam_fark_saf - fazla_maliyet  # Fazla stok maliyeti düşülür

        # Özet çerçevesi
        ozet_frame = tk.Frame(self.nakit_table_frame, bg='#E3F2FD')
        ozet_frame.pack(fill=tk.X, pady=(8, 0))

        # Satır 1: Ay be ay toplam
        row1 = tk.Frame(ozet_frame, bg='#E3F2FD')
        row1.pack(fill=tk.X, pady=1)
        tk.Label(row1, text="Ay Be Ay Alım Toplam NPV:", font=('Arial', 9),
                width=28, bg='#E3F2FD', anchor='w').pack(side=tk.LEFT)
        tk.Label(row1, text=f"{toplam_normal_npv:,.0f} TL", font=('Arial', 9, 'bold'),
                bg='#E3F2FD', fg='#1565C0').pack(side=tk.LEFT)

        # Satır 2: Toplu alım toplam
        row2 = tk.Frame(ozet_frame, bg='#E3F2FD')
        row2.pack(fill=tk.X, pady=1)
        tk.Label(row2, text="Toplu Alım Toplam NPV:", font=('Arial', 9),
                width=28, bg='#E3F2FD', anchor='w').pack(side=tk.LEFT)
        tk.Label(row2, text=f"{toplam_toplu_npv:,.0f} TL", font=('Arial', 9, 'bold'),
                bg='#E3F2FD', fg='#2E7D32').pack(side=tk.LEFT)

        # Satır 3: Mevcut stok fırsat maliyeti (varsa)
        if fazla_maliyet > 0:
            row3 = tk.Frame(ozet_frame, bg='#FFEBEE')
            row3.pack(fill=tk.X, pady=1)
            tk.Label(row3, text=f"Mevcut Stok Fırsat Maliyeti ({fazla_adet} ad):", font=('Arial', 9),
                    width=28, bg='#FFEBEE', anchor='w').pack(side=tk.LEFT)
            tk.Label(row3, text=f"-{fazla_maliyet:,.0f} TL", font=('Arial', 9, 'bold'),
                    bg='#FFEBEE', fg='#C62828').pack(side=tk.LEFT)

        # Satır 4: Net Avantaj
        sonuc_frame = tk.Frame(self.nakit_table_frame, bg='#FFF3E0')
        sonuc_frame.pack(fill=tk.X, pady=(5, 0))

        if toplam_fark > 0:
            sonuc_text = f"★ TOPLU ALIM {toplam_fark:,.0f} TL AVANTAJLI"
            sonuc_renk = '#2E7D32'
            aciklama = "Bugün toplu alım yaparak tasarruf sağlarsınız"
        else:
            sonuc_text = f"★ AY BE AY ALIM {-toplam_fark:,.0f} TL AVANTAJLI"
            sonuc_renk = '#C62828'
            aciklama = "Toplu alım yerine ihtiyaç oldukça alım yapın"

        tk.Label(sonuc_frame, text=sonuc_text, font=('Arial', 11, 'bold'),
                bg='#FFF3E0', fg=sonuc_renk).pack(pady=5)
        tk.Label(sonuc_frame, text=aciklama, font=('Arial', 9),
                bg='#FFF3E0', fg='#666').pack()

        # Parametreler özeti
        param_frame = tk.Frame(self.nakit_table_frame, bg='#ECEFF1')
        param_frame.pack(fill=tk.X, pady=(5, 0))

        mf_text = f"{mf_al}+{mf_bedava}" if mf_bedava > 0 else f"{mf_al} adet (MF'siz)"
        tk.Label(param_frame,
                text=f"Alım: {mf_text} | Ödeme: {toplu_odeme_ayi+1}. ay ({toplu_odeme_gun} gün sonra) | Mevcut stok: {stok}",
                font=('Arial', 8), bg='#ECEFF1', fg='#666').pack(pady=2)

    def _aktif_faiz_getir(self):
        """Seçili faiz oranını döndür"""
        if self.faiz_turu.get() == "mevduat":
            return self.mevduat_faizi.get()
        return self.kredi_faizi.get()

    def _mevcut_stok_fazlaligi_hesapla(self, mevcut_stok, aylik_ort, maliyet, faiz_yillik, depo_vade):
        """Mevcut stoğun ay sonuna sarkma maliyetini hesapla"""
        bugun = date.today()
        ay_son_gun = calendar.monthrange(bugun.year, bugun.month)[1]
        ay_sonuna_kalan = ay_son_gun - bugun.day

        if ay_sonuna_kalan <= 0 or aylik_ort <= 0:
            return {'fazla_adet': 0, 'fazla_maliyet': 0, 'ay_sonu_gun': 0}

        gunluk_sarf = aylik_ort / 30
        ay_sonu_ihtiyac = gunluk_sarf * ay_sonuna_kalan
        fazla_adet = max(0, mevcut_stok - ay_sonu_ihtiyac)

        if fazla_adet <= 0:
            return {'fazla_adet': 0, 'fazla_maliyet': 0, 'ay_sonu_gun': ay_sonuna_kalan}

        aylik_faiz = (faiz_yillik / 100) / 12
        fazla_maliyet = fazla_adet * maliyet * aylik_faiz

        return {
            'fazla_adet': int(fazla_adet),
            'fazla_maliyet': round(fazla_maliyet, 2),
            'ay_sonu_gun': ay_sonuna_kalan
        }

    def _senet_tarihi_bul(self, tarih):
        """
        Verilen alım tarihi için senet tarihini hesapla.
        CLAUDE.md prensibi: Ay içi alımlar → sonraki ayın 1'inde senet kesilir

        Örnek: 15 Şubat alımı → 1 Mart senet
        """
        if tarih.month == 12:
            return date(tarih.year + 1, 1, 1)
        else:
            return date(tarih.year, tarih.month + 1, 1)

    def _odeme_tarihi_bul(self, tarih, depo_vade=75):
        """
        Verilen alım tarihi için ödeme tarihini hesapla.
        CLAUDE.md prensibi: Senet tarihinden 75 gün sonra ödeme

        Örnek: 15 Şubat alımı → 1 Mart senet → 15 Mayıs civarı ödeme
        """
        senet = self._senet_tarihi_bul(tarih)
        return senet + timedelta(days=depo_vade)

    def _odeme_gun_hesapla(self, gun_offset, depo_vade=75):
        """
        Bugünden gun_offset gün sonraki alım için kaç gün sonra ödeme yapılacağını hesapla.
        Tam takvimsel hesaplama.

        Args:
            gun_offset: Bugünden kaç gün sonra alım yapılacak
            depo_vade: Senet sonrası kaç gün (varsayılan 75)

        Returns:
            int: Bugünden kaç gün sonra ödeme yapılacak
        """
        bugun = date.today()
        alim_tarihi = bugun + timedelta(days=gun_offset)
        odeme_tarihi = self._odeme_tarihi_bul(alim_tarihi, depo_vade)
        return (odeme_tarihi - bugun).days

    def _npv_mf_hesapla(self, alinan, bedava, maliyet, aylik_ort, mevcut_stok,
                        faiz_yillik, depo_vade, zam_gun=0, zam_orani=0):
        """MF alımı için detaylı NPV hesabı"""
        if alinan <= 0 or maliyet <= 0 or aylik_ort <= 0:
            return {'npv_toplu': 0, 'npv_aylik': 0, 'kazanc': 0, 'stok_ay': 0, 'zam_kazanc': 0}

        toplam_gelen = alinan + bedava
        toplam_stok = mevcut_stok + toplam_gelen

        aylik_faiz = (faiz_yillik / 100) / 12
        gunluk_faiz = (1 + aylik_faiz) ** (1/30) - 1
        gunluk_sarf = aylik_ort / 30

        stok_ay = toplam_stok / aylik_ort if aylik_ort > 0 else 0

        # SENARYO A: Ay be ay alım
        npv_aylik = 0
        kalan_mevcut = mevcut_stok
        kalan_yeni = toplam_gelen

        gun = 0
        while kalan_yeni > 0 and gun < 720:
            harcanan = gunluk_sarf
            mevcut_harcanan = min(kalan_mevcut, harcanan)
            kalan_mevcut -= mevcut_harcanan
            yeni_harcanan = min(harcanan - mevcut_harcanan, kalan_yeni)

            if yeni_harcanan > 0:
                if zam_orani > 0 and gun >= zam_gun:
                    fiyat = maliyet * (1 + zam_orani / 100)
                else:
                    fiyat = maliyet

                # TAKVİMSEL HESAPLAMA: Ay sonunda senet, depo vadesi sonra ödeme
                # Örnek: 15 Şubat alımı → 1 Mart senet → +75 gün → 15 Mayıs ödeme
                odeme_gun = self._odeme_gun_hesapla(gun, depo_vade)
                odeme = yeni_harcanan * fiyat
                iskonto = (1 + gunluk_faiz) ** odeme_gun
                npv_aylik += odeme / iskonto
                kalan_yeni -= yeni_harcanan
            gun += 1

        # SENARYO B: Toplu alım - TAKVİMSEL HESAPLAMA
        # Bugün alım → bu ayın sonunda senet → +depo_vade gün sonra ödeme
        toplu_odeme_gun = self._odeme_gun_hesapla(0, depo_vade)
        npv_toplu = (alinan * maliyet) / ((1 + gunluk_faiz) ** toplu_odeme_gun)

        # Zam kazancı
        zam_kazanc = 0
        if zam_orani > 0 and zam_gun > 0:
            zam_oncesi_tuketim = min(toplam_stok, zam_gun * gunluk_sarf)
            zam_sonrasi_miktar = max(0, toplam_stok - zam_oncesi_tuketim)

            if zam_sonrasi_miktar > 0:
                zam_fark = maliyet * (zam_orani / 100)
                ort_satis_gun = zam_gun + (zam_sonrasi_miktar / gunluk_sarf / 2) if gunluk_sarf > 0 else zam_gun
                iskonto = (1 + gunluk_faiz) ** ort_satis_gun
                zam_kazanc = (zam_sonrasi_miktar * zam_fark) / iskonto

        kazanc = npv_aylik - npv_toplu + zam_kazanc

        return {
            'npv_toplu': round(npv_toplu, 2),
            'npv_aylik': round(npv_aylik, 2),
            'kazanc': round(kazanc, 2),
            'stok_ay': round(stok_ay, 1),
            'zam_kazanc': round(zam_kazanc, 2)
        }

    def _zam_karar_noktalari_hesapla(self, stok, aylik_ort, maliyet, faiz, depo_vade, zam_gun, zam_orani):
        """
        Zam öncesi alım için Pareto ve Tepe noktalarını hesapla

        Returns:
            dict: {'pareto': {...}, 'tepe': {...}}
        """
        if zam_gun <= 0 or zam_orani <= 0 or aylik_ort <= 0:
            return {}

        gunluk_sarf = aylik_ort / 30
        # Zam tarihine kadar tüketilebilecek miktar
        zam_oncesi_tuketim = zam_gun * gunluk_sarf

        # Farklı miktarlar için kar hesapla
        sonuclar = []
        max_miktar = int(aylik_ort * 6)  # Max 6 aylık

        for miktar in range(int(gunluk_sarf), max_miktar + 1, max(1, int(gunluk_sarf / 2))):
            npv_sonuc = self._npv_mf_hesapla(
                alinan=miktar, bedava=0, maliyet=maliyet, aylik_ort=aylik_ort,
                mevcut_stok=stok, faiz_yillik=faiz, depo_vade=depo_vade,
                zam_gun=zam_gun, zam_orani=zam_orani
            )
            yatirim = miktar * maliyet
            roi = (npv_sonuc['kazanc'] / yatirim * 100) if yatirim > 0 else 0
            sonuclar.append({
                'miktar': miktar,
                'kar': npv_sonuc['kazanc'],
                'roi': roi
            })

        if not sonuclar:
            return {}

        # Tepe noktası: Maksimum kar
        tepe = max(sonuclar, key=lambda x: x['kar'])

        # Pareto noktası: Tepe karının %80'ine ulaşan en düşük miktar
        pareto = None
        if tepe['kar'] > 0:
            hedef_kar = tepe['kar'] * 0.8
            for s in sorted(sonuclar, key=lambda x: x['miktar']):
                if s['kar'] >= hedef_kar:
                    pareto = s
                    break

        return {
            'pareto': pareto,
            'tepe': tepe if tepe['kar'] > 0 else None
        }

    def _kritik_noktalar_hesapla(self, stok, aylik_ort, maliyet, faiz, depo_vade, zam_gun, zam_orani):
        """
        ROI bazlı kritik noktaları hesapla (5 kritik nokta).

        Returns:
            dict: kritik noktalar veya None
        """
        if aylik_ort <= 0 or maliyet <= 0:
            return None

        # Zam yoksa basit hesaplama (MF için)
        if zam_gun <= 0 or zam_orani <= 0:
            return None

        aylik_faiz = (faiz / 100) / 12
        gunluk_faiz = (1 + aylik_faiz) ** (1/30) - 1
        gunluk_sarf = aylik_ort / 30

        max_miktar = int(aylik_ort * 12)
        if max_miktar < 50:
            max_miktar = 200

        miktarlar, kazanclar, roi_ler = [], [], []

        for test_miktar in range(0, max_miktar + 1):
            if test_miktar == 0:
                miktarlar.append(0)
                kazanclar.append(0)
                roi_ler.append(0)
                continue

            # NPV hesabı
            kalan_mevcut = stok
            kalan_yeni = test_miktar
            npv_aylik = 0

            gun = 0
            while kalan_yeni > 0 and gun < 720:
                harcanan = gunluk_sarf
                mevcut_harcanan = min(kalan_mevcut, harcanan)
                kalan_mevcut -= mevcut_harcanan
                yeni_harcanan = min(harcanan - mevcut_harcanan, kalan_yeni)

                if yeni_harcanan > 0:
                    fiyat = maliyet if gun < zam_gun else maliyet * (1 + zam_orani / 100)
                    # TAKVİMSEL HESAPLAMA
                    odeme_gun = self._odeme_gun_hesapla(gun, depo_vade)
                    iskonto = (1 + gunluk_faiz) ** odeme_gun
                    npv_aylik += (yeni_harcanan * fiyat) / iskonto
                    kalan_yeni -= yeni_harcanan
                gun += 1

            # TAKVİMSEL HESAPLAMA
            toplu_odeme_gun = self._odeme_gun_hesapla(0, depo_vade)
            npv_toplu = (test_miktar * maliyet) / ((1 + gunluk_faiz) ** toplu_odeme_gun)
            kazanc = npv_aylik - npv_toplu
            yatirim = test_miktar * maliyet

            miktarlar.append(test_miktar)
            kazanclar.append(kazanc)
            roi = (kazanc / yatirim * 100) if yatirim > 0 else 0
            roi_ler.append(roi)

        if not miktarlar:
            return None

        # Kritik noktaları bul
        # 1. Max ROI noktası
        max_roi_idx = 1
        max_roi_val = roi_ler[1] if len(roi_ler) > 1 else 0
        for i in range(2, len(roi_ler)):
            if roi_ler[i] > max_roi_val:
                max_roi_val = roi_ler[i]
                max_roi_idx = i

        # 2. Yarım ROI (eğim azalması) noktası
        yarim_roi_idx = max_roi_idx
        for i in range(max_roi_idx, len(roi_ler)):
            if roi_ler[i] <= max_roi_val / 2:
                yarim_roi_idx = i
                break

        # 3. Sıfır ROI (negatife dönüş) noktası
        sifir_roi_idx = len(roi_ler) - 1
        for i in range(max_roi_idx, len(roi_ler)):
            if roi_ler[i] <= 0:
                sifir_roi_idx = i
                break

        # 4. Optimum (tepe kazanç) noktası
        optimum_idx = 1
        max_kazanc = kazanclar[1] if len(kazanclar) > 1 else 0
        for i in range(2, len(kazanclar)):
            if kazanclar[i] > max_kazanc:
                max_kazanc = kazanclar[i]
                optimum_idx = i

        # 5. Pareto (%80 kazanç) noktası
        pareto_hedef = kazanclar[optimum_idx] * 0.80 if optimum_idx < len(kazanclar) else 0
        pareto_idx = 0
        for i, k in enumerate(kazanclar):
            if k >= pareto_hedef:
                pareto_idx = i
                break

        return {
            'max_roi': {'m': miktarlar[max_roi_idx], 'k': kazanclar[max_roi_idx], 'r': roi_ler[max_roi_idx]},
            'yarim_roi': {'m': miktarlar[yarim_roi_idx], 'k': kazanclar[yarim_roi_idx], 'r': roi_ler[yarim_roi_idx]},
            'pareto': {'m': miktarlar[pareto_idx], 'k': kazanclar[pareto_idx], 'r': roi_ler[pareto_idx]},
            'optimum': {'m': miktarlar[optimum_idx], 'k': kazanclar[optimum_idx], 'r': roi_ler[optimum_idx]},
            'sifir_roi': {'m': miktarlar[sifir_roi_idx], 'k': kazanclar[sifir_roi_idx], 'r': roi_ler[sifir_roi_idx]},
            'miktarlar': miktarlar,
            'kazanclar': kazanclar,
            'roi_ler': roi_ler
        }

    def _bolge_analizi_hesapla(self, toplam_miktar, kritik_noktalar):
        """
        Verilen miktar için hangi bölgede olduğunu hesapla.

        Bölgeler:
        1. Sıfır - Maks ROI arası (Verimli Başlangıç) - B1
        2. Maks ROI - Eğim Azalması arası (Azalan Verim) - B2
        3. Eğim Azalması - Pareto arası (Dengeli) - B3
        4. Pareto - Tepe arası (Agresif) - B4
        5. Tepe - Negatif Dönüş arası (Riskli) - B5
        6. Negatif Dönüş sonrası (Zarar) - B6

        Returns:
            dict: bolge_no, bolge_adi, renk, aciklama
        """
        if not kritik_noktalar:
            return {'bolge_no': 0, 'bolge_adi': '-', 'renk': '#757575', 'aciklama': 'Zam analizi yok'}

        kn = kritik_noktalar
        max_roi_m = kn['max_roi']['m']
        yarim_roi_m = kn['yarim_roi']['m']
        pareto_m = kn['pareto']['m']
        optimum_m = kn['optimum']['m']
        sifir_roi_m = kn['sifir_roi']['m']

        if toplam_miktar <= 0:
            return {'bolge_no': 0, 'bolge_adi': '-', 'renk': '#757575', 'aciklama': 'Miktar yok'}
        elif toplam_miktar <= max_roi_m:
            return {'bolge_no': 1, 'bolge_adi': 'B1', 'renk': '#4CAF50',
                    'aciklama': f'Verimli (0-{max_roi_m})'}
        elif toplam_miktar <= yarim_roi_m:
            return {'bolge_no': 2, 'bolge_adi': 'B2', 'renk': '#8BC34A',
                    'aciklama': f'Azalan Verim ({max_roi_m}-{yarim_roi_m})'}
        elif toplam_miktar <= pareto_m:
            return {'bolge_no': 3, 'bolge_adi': 'B3', 'renk': '#FFC107',
                    'aciklama': f'Dengeli ({yarim_roi_m}-{pareto_m})'}
        elif toplam_miktar <= optimum_m:
            return {'bolge_no': 4, 'bolge_adi': 'B4', 'renk': '#FF9800',
                    'aciklama': f'Agresif ({pareto_m}-{optimum_m})'}
        elif toplam_miktar <= sifir_roi_m:
            return {'bolge_no': 5, 'bolge_adi': 'B5', 'renk': '#FF5722',
                    'aciklama': f'Riskli ({optimum_m}-{sifir_roi_m})'}
        else:
            return {'bolge_no': 6, 'bolge_adi': 'B6', 'renk': '#F44336',
                    'aciklama': f'Zarar ({sifir_roi_m}+)'}

    def _mf_karsilastir(self):
        """MF Karşılaştırma - Tüm MF oranlarını hesapla, en iyiyi bul"""
        # Parametreleri al
        try:
            stok = self.stok.get()
            aylik_ort = self.aylik_ort.get()
            maliyet = self.maliyet.get()
            faiz = self._aktif_faiz_getir()
            depo_vade = self.depo_vadesi.get()

            # Alım miktarı (sadece mal kısmı - MF karşılaştırma için baz miktar)
            alim_mal, _ = self._alim_parse(self.alim_str.get())
            siparis_miktar = alim_mal if alim_mal > 0 else int(aylik_ort)  # Yoksa aylık gidiş kadar

            zam_aktif = self.zam_aktif.get()
            zam_orani = self.zam_orani.get() if zam_aktif else 0
            zam_tarihi = self.zam_tarih_entry.get_date() if zam_aktif else None

            zam_gun = 0
            if zam_tarihi and zam_orani > 0:
                zam_gun = max(0, (zam_tarihi - date.today()).days)

        except Exception as e:
            messagebox.showerror("Hata", f"Parametre hatası: {e}")
            return

        if maliyet <= 0 or aylik_ort <= 0:
            messagebox.showwarning("Uyarı", "Depocu fiyat ve aylık gidiş 0'dan büyük olmalı!")
            return

        # MF listesi oluştur
        mf_listesi = []
        for entry in self.mf_entries:
            mf_text = entry.get().strip()
            if mf_text and '+' in mf_text:
                mf_listesi.append(mf_text)

        if not mf_listesi and not self.mfsiz_var.get():
            messagebox.showwarning("Uyarı", "En az bir MF şartı girin veya MF'siz seçeneğini işaretleyin!")
            return

        # Mevcut stok fazlalığı
        stok_fazlaligi = self._mevcut_stok_fazlaligi_hesapla(stok, aylik_ort, maliyet, faiz, depo_vade)
        fazla_adet = stok_fazlaligi['fazla_adet']
        fazla_maliyet = stok_fazlaligi['fazla_maliyet']

        # İlaç adı
        ilac_adi = self.ilac_combo.get().strip() or "Manuel Giriş"

        # Bilgi satırını güncelle
        bilgi_text = f"{ilac_adi} | Stok: {stok} | Baz: {siparis_miktar} ad | Aylık: {aylik_ort:.0f} | Maliyet: {maliyet:.0f}₺"
        if zam_gun > 0:
            bilgi_text += f" | Zam: {zam_gun}g %{zam_orani:.0f}"
        self.bilgi_label.config(text=bilgi_text)

        # Fazla stok uyarısı
        if fazla_adet > 0:
            self.fazla_frame.pack(fill=tk.X, pady=(0, 5))
            self.fazla_label.config(text=f"⚠ Mevcut Stok Fazlası: {fazla_adet} ad. → -{fazla_maliyet:.0f}₺ fırsat maliyeti (kar hesabına dahil)")
        else:
            self.fazla_frame.pack_forget()

        # Kritik noktaları hesapla (bölge analizi için)
        kritik_noktalar = None
        if zam_gun > 0 and zam_orani > 0:
            kritik_noktalar = self._kritik_noktalar_hesapla(
                stok, aylik_ort, maliyet, faiz, depo_vade, zam_gun, zam_orani
            )

        # Sonuç tablosunu temizle
        for widget in self.sonuc_table_frame.winfo_children():
            widget.destroy()

        # Baslik satiri
        baslik_row = tk.Frame(self.sonuc_table_frame, bg='#1976D2')
        baslik_row.pack(fill=tk.X)

        basliklar = [("MF Sarti", 10), ("Al", 5), ("Bed", 4), ("Top", 5),
                    ("StokAy", 5), ("Net Kar", 9), ("ROI %", 7), ("Bölge", 5)]

        for baslik, w in basliklar:
            tk.Label(baslik_row, text=baslik, font=('Arial', 9, 'bold'), width=w,
                    bg='#1976D2', fg='white').pack(side=tk.LEFT, padx=1)

        # Sonuçları hesapla
        sonuclar = []

        # MF'siz alım
        if self.mfsiz_var.get():
            npv_sonuc = self._npv_mf_hesapla(
                alinan=siparis_miktar, bedava=0, maliyet=maliyet, aylik_ort=aylik_ort,
                mevcut_stok=stok, faiz_yillik=faiz, depo_vade=depo_vade,
                zam_gun=zam_gun, zam_orani=zam_orani
            )
            # Fazla stok fırsat maliyeti: Mevcut fazla stoğun bizi mevduat faizinden mahrum bırakması
            # Bu maliyet toplu alım yaptığımızda stok daha uzun süre elimizde kalacağı için eklenir
            net_kar = npv_sonuc['kazanc'] - fazla_maliyet
            yatirim = siparis_miktar * maliyet
            roi = (net_kar / yatirim * 100) if yatirim > 0 else 0

            birim_av = net_kar / siparis_miktar if siparis_miktar > 0 else 0
            sonuclar.append({
                'mf': "MF'siz", 'al': siparis_miktar, 'bedava': 0,
                'toplam': siparis_miktar, 'stok_ay': npv_sonuc['stok_ay'],
                'kar': net_kar, 'roi': roi, 'birim_av': birim_av,
                'is_referans': True
            })

        # MF'li alımlar
        for mf_sart in mf_listesi:
            try:
                parcalar = mf_sart.split('+')
                mf_al = int(parcalar[0])
                mf_bedava = int(parcalar[1])

                set_sayisi = siparis_miktar // mf_al
                if set_sayisi == 0:
                    set_sayisi = 1

                al = set_sayisi * mf_al
                bedava = set_sayisi * mf_bedava
                toplam = al + bedava

                npv_sonuc = self._npv_mf_hesapla(
                    alinan=al, bedava=bedava, maliyet=maliyet, aylik_ort=aylik_ort,
                    mevcut_stok=stok, faiz_yillik=faiz, depo_vade=depo_vade,
                    zam_gun=zam_gun, zam_orani=zam_orani
                )

                # Fazla stok fırsat maliyeti eklendi
                net_kar = npv_sonuc['kazanc'] - fazla_maliyet
                yatirim = al * maliyet
                roi = (net_kar / yatirim * 100) if yatirim > 0 else 0
                birim_av = net_kar / toplam if toplam > 0 else 0  # Birim avantaj

                sonuclar.append({
                    'mf': mf_sart, 'al': al, 'bedava': bedava,
                    'toplam': toplam, 'stok_ay': npv_sonuc['stok_ay'],
                    'kar': net_kar, 'roi': roi, 'birim_av': birim_av,
                    'is_referans': False
                })
            except:
                continue

        # ROI'ye göre sırala
        sonuclar.sort(key=lambda x: x['roi'], reverse=True)

        # Sonuçları göster
        for i, s in enumerate(sonuclar):
            if s['is_referans']:
                renk = '#BBDEFB'
            elif s['roi'] > 0:
                renk = '#A5D6A7'
            else:
                renk = '#FFCDD2'

            row = tk.Frame(self.sonuc_table_frame, bg=renk)
            row.pack(fill=tk.X)

            # MF Şartı
            mf_text = s['mf']
            if i == 0:
                mf_text += " ★"
            tk.Label(row, text=mf_text, font=('Arial', 9, 'bold' if i == 0 else 'normal'),
                    width=10, bg=renk, anchor='w').pack(side=tk.LEFT, padx=1)

            tk.Label(row, text=str(s['al']), font=('Arial', 9), width=5, bg=renk).pack(side=tk.LEFT, padx=1)
            tk.Label(row, text=str(s['bedava']), font=('Arial', 9), width=4, bg=renk).pack(side=tk.LEFT, padx=1)
            tk.Label(row, text=str(s['toplam']), font=('Arial', 9), width=5, bg=renk).pack(side=tk.LEFT, padx=1)
            tk.Label(row, text=f"{s['stok_ay']:.1f}", font=('Arial', 9), width=5, bg=renk).pack(side=tk.LEFT, padx=1)

            kar_renk = 'green' if s['kar'] > 0 else ('red' if s['kar'] < 0 else 'black')
            tk.Label(row, text=f"{s['kar']:.0f}TL", font=('Arial', 9, 'bold'),
                    width=9, bg=renk, fg=kar_renk).pack(side=tk.LEFT, padx=1)
            tk.Label(row, text=f"%{s['roi']:.1f}", font=('Arial', 9, 'bold'),
                    width=7, bg=renk, fg=kar_renk).pack(side=tk.LEFT, padx=1)

            # Bölge analizi (Zam varsa göster)
            bolge = self._bolge_analizi_hesapla(s['toplam'], kritik_noktalar)
            bolge_label = tk.Label(row, text=bolge['bolge_adi'], font=('Arial', 9, 'bold'),
                                   width=5, bg=bolge['renk'], fg='white')
            bolge_label.pack(side=tk.LEFT, padx=1)

            # Tooltip için bölge açıklaması
            def show_tooltip(event, aciklama=bolge['aciklama']):
                tooltip = tk.Toplevel()
                tooltip.wm_overrideredirect(True)
                tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                label = tk.Label(tooltip, text=aciklama, bg='#333', fg='white',
                                font=('Arial', 9), padx=5, pady=2)
                label.pack()
                tooltip.after(2000, tooltip.destroy)
                bolge_label._tooltip = tooltip

            def hide_tooltip(event):
                if hasattr(bolge_label, '_tooltip'):
                    try:
                        bolge_label._tooltip.destroy()
                    except:
                        pass

            bolge_label.bind('<Enter>', show_tooltip)
            bolge_label.bind('<Leave>', hide_tooltip)

        # ═══════════════════════════════════════════════════════════════════
        # KAPSAMLI ÖNERİ SİSTEMİ
        # ═══════════════════════════════════════════════════════════════════
        if sonuclar:
            # Tüm seçenekleri topla
            tum_secenekler = []

            # 1. MF'siz Ay be Ay (referans)
            referans = next((s for s in sonuclar if s['is_referans']), None)
            if referans:
                tum_secenekler.append({
                    'ad': "MF'siz Ay be Ay",
                    'miktar': referans['toplam'],
                    'kar': referans['kar'],
                    'roi': referans['roi'],
                    'tip': 'referans'
                })

            # 2. En Karlı MF (MF'siz hariç)
            mf_li_sonuclar = [s for s in sonuclar if not s['is_referans']]
            if mf_li_sonuclar:
                max_kar_mf = max(mf_li_sonuclar, key=lambda x: x['kar'])
                tum_secenekler.append({
                    'ad': f"MF {max_kar_mf['mf']}",
                    'miktar': max_kar_mf['toplam'],
                    'kar': max_kar_mf['kar'],
                    'roi': max_kar_mf['roi'],
                    'tip': 'mf'
                })

            # 3. Zam Pareto ve Tepe (zam aktifse)
            if zam_gun > 0 and zam_orani > 0:
                # Pareto ve Tepe noktalarını hesapla
                zam_sonuclari = self._zam_karar_noktalari_hesapla(
                    stok, aylik_ort, maliyet, faiz, depo_vade, zam_gun, zam_orani
                )
                if zam_sonuclari.get('pareto'):
                    tum_secenekler.append({
                        'ad': "Zam Pareto (%80)",
                        'miktar': zam_sonuclari['pareto']['miktar'],
                        'kar': zam_sonuclari['pareto']['kar'],
                        'roi': zam_sonuclari['pareto']['roi'],
                        'tip': 'zam_pareto'
                    })
                if zam_sonuclari.get('tepe'):
                    tum_secenekler.append({
                        'ad': "Zam Tepe (Max)",
                        'miktar': zam_sonuclari['tepe']['miktar'],
                        'kar': zam_sonuclari['tepe']['kar'],
                        'roi': zam_sonuclari['tepe']['roi'],
                        'tip': 'zam_tepe'
                    })

            # En karlı seçeneği bul
            en_karli = max(tum_secenekler, key=lambda x: x['kar']) if tum_secenekler else None

            # ═══════════════════════════════════════════════════════════════════
            # ÖNERİ KUTUSU (En üstte)
            # ═══════════════════════════════════════════════════════════════════
            if en_karli and en_karli['kar'] > 0:
                oneri_frame = tk.Frame(self.sonuc_table_frame, bg='#1B5E20', pady=3)
                oneri_frame.pack(fill=tk.X, pady=(10, 5))

                tk.Label(oneri_frame, text=f"★ ÖNERİ: {en_karli['ad']}",
                        font=('Arial', 11, 'bold'), bg='#1B5E20', fg='white').pack(side=tk.LEFT, padx=10)
                tk.Label(oneri_frame, text=f"Miktar: {en_karli['miktar']} ad | Kar: +{en_karli['kar']:.0f} TL | ROI: %{en_karli['roi']:.1f}",
                        font=('Arial', 10), bg='#1B5E20', fg='#A5D6A7').pack(side=tk.LEFT, padx=5)

            # ═══════════════════════════════════════════════════════════════════
            # TÜM SEÇENEKLERİN KARŞILAŞTIRMASI
            # ═══════════════════════════════════════════════════════════════════
            ozet_frame = tk.Frame(self.sonuc_table_frame, bg='#E8F5E9', pady=5)
            ozet_frame.pack(fill=tk.X, pady=5)

            tk.Label(ozet_frame, text="Seçenek Karşılaştırması:",
                    font=('Arial', 9, 'bold'), bg='#E8F5E9', fg='#1B5E20').pack(anchor='w', padx=10)

            for i, secenek in enumerate(sorted(tum_secenekler, key=lambda x: x['kar'], reverse=True)):
                is_best = (en_karli and secenek['ad'] == en_karli['ad'])
                row_bg = '#C8E6C9' if is_best else '#E8F5E9'
                row = tk.Frame(ozet_frame, bg=row_bg)
                row.pack(fill=tk.X, padx=10, pady=1)

                yildiz = "★ " if is_best else f"{i+1}. "
                kar_text = f"+{secenek['kar']:.0f}" if secenek['kar'] > 0 else f"{secenek['kar']:.0f}"

                tk.Label(row, text=f"{yildiz}{secenek['ad']}:",
                        font=('Arial', 9, 'bold' if is_best else 'normal'),
                        width=18, bg=row_bg, anchor='w').pack(side=tk.LEFT)
                tk.Label(row, text=f"{secenek['miktar']} ad → {kar_text} TL",
                        font=('Arial', 9, 'bold' if is_best else 'normal'),
                        bg=row_bg, fg='#1B5E20' if secenek['kar'] > 0 else '#C62828').pack(side=tk.LEFT)

            # Açıklama
            aciklama_row = tk.Frame(ozet_frame, bg='#FFF3E0')
            aciklama_row.pack(fill=tk.X, padx=10, pady=(5, 2))
            tk.Label(aciklama_row, text="Pareto: %80 kazanca ulaşan miktar | Tepe: Max mutlak kazanç",
                    font=('Arial', 7, 'italic'), bg='#FFF3E0', fg='#E65100').pack(anchor='w')

            # ROI ve Kar karşılaştırması
            max_roi_mf = sonuclar[0]  # Zaten ROI'ye göre sıralı
            max_kar_mf = max(sonuclar, key=lambda x: x['kar'])

            # ═══════════════════════════════════════════════════════════════════
            # EN İYİ MF'İ ALIM ALANINA YAZ
            # Kullanıcı "Nakit Akış" butonuna basınca bu değer kullanılır
            # ═══════════════════════════════════════════════════════════════════
            best_mf = max_roi_mf
            if best_mf['bedava'] > 0:
                self._alim_guncelle(best_mf['al'], best_mf['bedava'])
            else:
                self._alim_guncelle(best_mf['al'], 0)

    def _nakit_akis_goster(self):
        """Nakit Akış Göster - Alım alanındaki değere göre nakit akış tablosu"""
        # Parametreleri al
        try:
            stok = self.stok.get()
            aylik_ort = self.aylik_ort.get()
            maliyet = self.maliyet.get()
            faiz = self._aktif_faiz_getir()
            depo_vade = self.depo_vadesi.get()

            # Alım stringini parse et (mal+mf formatı)
            alim_mal, alim_mf = self._alim_parse(self.alim_str.get())

            zam_aktif = self.zam_aktif.get()
            zam_orani = self.zam_orani.get() if zam_aktif else 0
            zam_tarihi = self.zam_tarih_entry.get_date() if zam_aktif else None

            zam_gun = 0
            if zam_tarihi and zam_orani > 0:
                zam_gun = max(0, (zam_tarihi - date.today()).days)

        except Exception as e:
            messagebox.showerror("Hata", f"Parametre hatası: {e}")
            return

        if maliyet <= 0 or aylik_ort <= 0:
            messagebox.showwarning("Uyarı", "Depocu fiyat ve aylık gidiş 0'dan büyük olmalı!")
            return

        # Alım 0 olabilir - mevcut stokla devam senaryosu

        # Nakit akış tablosunu doldur
        self._nakit_akis_tablosu_doldur(
            stok=stok,
            aylik_ort=aylik_ort,
            maliyet=maliyet,
            faiz_yillik=faiz,
            depo_vade=depo_vade,
            siparis_miktar=alim_mal,
            mf_al=alim_mal,
            mf_bedava=alim_mf,
            zam_gun=zam_gun,
            zam_orani=zam_orani
        )


def mf_hizli_hesaplama_ac(parent=None, ana_menu_callback=None):
    """MF Hızlı Hesaplama modülünü aç"""
    if parent is None:
        root = tk.Tk()
        app = MFHizliHesaplamaGUI(root)
        root.mainloop()
    else:
        app = MFHizliHesaplamaGUI(parent, ana_menu_callback)
    return app


if __name__ == "__main__":
    mf_hizli_hesaplama_ac()
