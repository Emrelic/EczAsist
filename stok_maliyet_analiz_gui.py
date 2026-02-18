"""
Stok Maliyet Analizi Modülü
Belirli bir tarihteki stok durumunu ve sonrasındaki fırsat maliyetini analiz eder.

Analiz Kapsamı:
1. Seçilen tarihteki envanter (parti parti maliyet)
2. Sonraki aylarda sarflar vs stok durumu
3. Fazla stoğun fırsat maliyeti (faiz kaybı)
4. MF ve zam avantajları (stok yapmanın getirisi)
5. Net maliyet/fayda özeti
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import calendar
from tkcalendar import DateEntry
import threading

logger = logging.getLogger(__name__)


class StokMaliyetAnalizGUI:
    """Stok Maliyet Analizi Modülü"""

    def __init__(self, parent, ana_menu_callback=None):
        self.parent = parent
        self.ana_menu_callback = ana_menu_callback

        self.parent.title("Stok Maliyet Analizi - Fırsat Maliyeti ve Avantaj Raporu")
        self.parent.geometry("1400x850")
        self.parent.configure(bg='#ECEFF1')

        # Veritabanı
        self.db = None
        self._db_baglan()

        # Değişkenler
        self.mevduat_faizi = tk.DoubleVar(value=40)
        self.analiz_ay_sayisi = tk.IntVar(value=6)

        # Analiz sonuçları
        self.analiz_sonuclari = []

        self._arayuz_olustur()

    def _db_baglan(self):
        """Veritabanına bağlan"""
        try:
            from botanik_db import BotanikDB
            self.db = BotanikDB()
            if not self.db.baglan():
                self.db = None
                logger.warning("Veritabanına bağlanılamadı")
        except Exception as e:
            logger.error(f"DB bağlantı hatası: {e}")
            self.db = None

    def _arayuz_olustur(self):
        """Ana arayüz"""
        # Başlık
        header = tk.Frame(self.parent, bg='#5D4037', height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="📊 Stok Maliyet Analizi - Fırsat Maliyeti ve Avantaj Raporu",
                bg='#5D4037', fg='white', font=('Arial', 14, 'bold')).pack(pady=12)

        # Ana içerik
        main_frame = tk.Frame(self.parent, bg='#ECEFF1', padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Üst panel - Parametreler
        self._parametre_panel_olustur(main_frame)

        # Orta panel - Sonuçlar (iki bölüm)
        sonuc_paned = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL, bg='#ECEFF1')
        sonuc_paned.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        # Sol: Ürün listesi
        self._urun_listesi_olustur(sonuc_paned)

        # Sağ: Detay analizi
        self._detay_panel_olustur(sonuc_paned)

    def _parametre_panel_olustur(self, parent):
        """Parametre giriş paneli"""
        param_frame = tk.Frame(parent, bg='#ECEFF1')
        param_frame.pack(fill=tk.X)

        # ═══ TARİH SEÇİMİ ═══
        tarih_frame = tk.LabelFrame(param_frame, text=" 📅 Analiz Tarihi ",
                                    font=('Arial', 10, 'bold'), bg='#FFF3E0', padx=10, pady=8)
        tarih_frame.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(tarih_frame, text="Başlangıç Tarihi:", font=('Arial', 10),
                bg='#FFF3E0').pack(side=tk.LEFT)
        self.tarih_entry = DateEntry(tarih_frame, width=12, background='#5D4037',
                                     foreground='white', borderwidth=1,
                                     date_pattern='yyyy-mm-dd', font=('Arial', 10))
        # Varsayılan: 6 ay önce
        varsayilan_tarih = date.today() - relativedelta(months=6)
        self.tarih_entry.set_date(varsayilan_tarih)
        self.tarih_entry.pack(side=tk.LEFT, padx=5)

        tk.Label(tarih_frame, text="Analiz Süresi:", font=('Arial', 10),
                bg='#FFF3E0').pack(side=tk.LEFT, padx=(15, 5))
        ay_combo = ttk.Combobox(tarih_frame, textvariable=self.analiz_ay_sayisi,
                                values=[3, 6, 9, 12], width=3, state='readonly', font=('Arial', 10))
        ay_combo.pack(side=tk.LEFT)
        tk.Label(tarih_frame, text="ay", font=('Arial', 10), bg='#FFF3E0').pack(side=tk.LEFT, padx=2)

        # ═══ FİNANSAL PARAMETRELER ═══
        finans_frame = tk.LabelFrame(param_frame, text=" 💰 Finansal ",
                                     font=('Arial', 10, 'bold'), bg='#E8F5E9', padx=10, pady=8)
        finans_frame.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(finans_frame, text="Yıllık Faiz %:", font=('Arial', 10),
                bg='#E8F5E9').pack(side=tk.LEFT)
        ttk.Entry(finans_frame, textvariable=self.mevduat_faizi, width=5,
                 font=('Arial', 10)).pack(side=tk.LEFT, padx=5)

        # ═══ FİLTRE ═══
        filtre_frame = tk.LabelFrame(param_frame, text=" 🔍 Filtre ",
                                     font=('Arial', 10, 'bold'), bg='#E3F2FD', padx=10, pady=8)
        filtre_frame.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(filtre_frame, text="Min Fırsat Maliyeti:", font=('Arial', 10),
                bg='#E3F2FD').pack(side=tk.LEFT)
        self.min_maliyet = tk.IntVar(value=50)
        ttk.Entry(filtre_frame, textvariable=self.min_maliyet, width=6,
                 font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        tk.Label(filtre_frame, text="₺", font=('Arial', 10), bg='#E3F2FD').pack(side=tk.LEFT)

        # ═══ BUTONLAR ═══
        btn_frame = tk.Frame(param_frame, bg='#ECEFF1')
        btn_frame.pack(side=tk.LEFT, padx=10)

        tk.Button(btn_frame, text="ANALİZ BAŞLAT", font=('Arial', 11, 'bold'),
                 bg='#5D4037', fg='white', padx=20, pady=8,
                 command=self._analiz_baslat).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="Excel'e Aktar", font=('Arial', 10),
                 bg='#2E7D32', fg='white', padx=10,
                 command=self._excel_aktar).pack(side=tk.LEFT, padx=5)

        # Durum etiketi
        self.durum_label = tk.Label(param_frame, text="Analiz için tarih seçip başlatın",
                                    font=('Arial', 9), bg='#ECEFF1', fg='#666')
        self.durum_label.pack(side=tk.RIGHT, padx=10)

    def _urun_listesi_olustur(self, parent):
        """Ürün listesi paneli"""
        liste_frame = tk.LabelFrame(parent, text=" Ürün Bazlı Özet ",
                                    font=('Arial', 10, 'bold'), bg='#ECEFF1', padx=5, pady=5)
        parent.add(liste_frame, minsize=500, width=550)

        # Tablo
        columns = [
            ("UrunAdi", "Ürün Adı", 200),
            ("Stok", "Stok", 50),
            ("AylikOrt", "Aylık", 50),
            ("StokAy", "Stok/Ay", 55),
            ("FirsatMaliyet", "Fırsat Mal.", 80),
            ("MFAvantaj", "MF Av.", 70),
            ("ZamAvantaj", "Zam Av.", 70),
            ("NetSonuc", "NET", 80),
        ]

        tree_frame = tk.Frame(liste_frame, bg='#ECEFF1')
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.sonuc_tree = ttk.Treeview(tree_frame, columns=[c[0] for c in columns],
                                        show='headings', height=20)

        for col_id, baslik, width in columns:
            self.sonuc_tree.heading(col_id, text=baslik)
            self.sonuc_tree.column(col_id, width=width, minwidth=40)

        # Renkli tag'ler
        self.sonuc_tree.tag_configure('karli', background='#C8E6C9')
        self.sonuc_tree.tag_configure('zarari', background='#FFCDD2')
        self.sonuc_tree.tag_configure('notr', background='#FFF9C4')

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.sonuc_tree.yview)
        self.sonuc_tree.configure(yscrollcommand=vsb.set)

        self.sonuc_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Seçim eventi
        self.sonuc_tree.bind('<<TreeviewSelect>>', self._urun_secildi)

        # Özet satırı
        ozet_frame = tk.Frame(liste_frame, bg='#5D4037', pady=5)
        ozet_frame.pack(fill=tk.X, pady=(5, 0))

        self.ozet_label = tk.Label(ozet_frame,
            text="Toplam: Fırsat Maliyeti: 0₺ | MF Avantajı: 0₺ | Zam Avantajı: 0₺ | NET: 0₺",
            font=('Arial', 10, 'bold'), bg='#5D4037', fg='white')
        self.ozet_label.pack()

    def _detay_panel_olustur(self, parent):
        """Detay analizi paneli"""
        detay_frame = tk.LabelFrame(parent, text=" Detaylı Analiz ",
                                    font=('Arial', 10, 'bold'), bg='#ECEFF1', padx=5, pady=5)
        parent.add(detay_frame, minsize=400)

        # Scrollable içerik
        canvas = tk.Canvas(detay_frame, bg='#ECEFF1', highlightthickness=0)
        scrollbar = ttk.Scrollbar(detay_frame, orient='vertical', command=canvas.yview)
        self.detay_icerik = tk.Frame(canvas, bg='#ECEFF1')

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        canvas.create_window((0, 0), window=self.detay_icerik, anchor='nw')
        self.detay_icerik.bind('<Configure>',
            lambda e: canvas.configure(scrollregion=canvas.bbox('all')))

        # Başlangıç mesajı
        tk.Label(self.detay_icerik, text="Soldaki listeden ürün seçin...",
                font=('Arial', 11), bg='#ECEFF1', fg='#666').pack(pady=50)

    def _analiz_baslat(self):
        """Analizi başlat"""
        if not self.db:
            messagebox.showerror("Hata", "Veritabanı bağlantısı yok!")
            return

        self.durum_label.config(text="Analiz yapılıyor...")
        self.parent.update()

        # Arka planda çalıştır
        threading.Thread(target=self._analiz_yap, daemon=True).start()

    def _analiz_yap(self):
        """Ana analiz fonksiyonu"""
        try:
            analiz_tarihi = self.tarih_entry.get_date()
            ay_sayisi = self.analiz_ay_sayisi.get()
            faiz_yillik = self.mevduat_faizi.get()
            min_maliyet = self.min_maliyet.get()

            # 1. O tarihteki stok durumunu ve sonraki dönemdeki verileri çek
            urunler = self._stok_verilerini_getir(analiz_tarihi, ay_sayisi)

            if not urunler:
                self.parent.after(0, lambda: self.durum_label.config(text="Veri bulunamadı!"))
                return

            # 2. Her ürün için analiz yap
            sonuclar = []
            for urun in urunler:
                analiz = self._urun_analiz_yap(urun, analiz_tarihi, ay_sayisi, faiz_yillik)
                if analiz and abs(analiz['firsat_maliyet']) >= min_maliyet:
                    sonuclar.append(analiz)

            # Fırsat maliyetine göre sırala (en yüksekten)
            sonuclar.sort(key=lambda x: x['firsat_maliyet'], reverse=True)

            self.analiz_sonuclari = sonuclar

            # Arayüzü güncelle
            self.parent.after(0, lambda: self._sonuclari_goster(sonuclar))

        except Exception as e:
            logger.error(f"Analiz hatası: {e}")
            self.parent.after(0, lambda: self.durum_label.config(text=f"Hata: {str(e)[:50]}"))

    def _stok_verilerini_getir(self, analiz_tarihi, ay_sayisi):
        """
        Belirli bir tarihteki stok durumu ve sonraki dönemdeki alım/satış verilerini getir.

        Stok hesabı: O tarihe kadar olan alımlar - O tarihe kadar olan sarflar
        """
        tarih_str = analiz_tarihi.strftime('%Y-%m-%d')
        bitis_tarihi = analiz_tarihi + relativedelta(months=ay_sayisi)
        bitis_str = bitis_tarihi.strftime('%Y-%m-%d')

        # Analiz döneminde hareketi olan ürünleri bul
        sql = f"""
        WITH UrunHareketleri AS (
            -- Alımlar (FaturaSatir)
            SELECT fs.FSUrunId as UrunId, 'ALIM' as Tip,
                   fg.FGFaturaTarihi as Tarih,
                   CAST(fs.FSUrunAdet as int) as Adet,
                   CAST(fs.FSUrunMf as int) as MF,
                   CAST(fs.FSUrunBirimFiyat as decimal(18,2)) as BirimFiyat
            FROM FaturaSatir fs
            JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
            WHERE fg.FGSilme = 0
            AND fg.FGFaturaTarihi >= DATEADD(year, -2, '{tarih_str}')
            AND fg.FGFaturaTarihi <= '{bitis_str}'

            UNION ALL

            -- Sarflar (ReceteIlaclari)
            SELECT ri.RIUrunId as UrunId, 'SARF' as Tip,
                   ra.RxKayitTarihi as Tarih,
                   CAST(ri.RIAdet as int) as Adet,
                   0 as MF,
                   0 as BirimFiyat
            FROM ReceteIlaclari ri
            JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
            WHERE ra.RxSilme = 0 AND ri.RISilme = 0
            AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
            AND ra.RxKayitTarihi >= DATEADD(year, -2, '{tarih_str}')
            AND ra.RxKayitTarihi <= '{bitis_str}'

            UNION ALL

            -- Sarflar (EldenIlaclari)
            SELECT ei.RIUrunId as UrunId, 'SARF' as Tip,
                   ea.RxKayitTarihi as Tarih,
                   CAST(ei.RIAdet as int) as Adet,
                   0 as MF,
                   0 as BirimFiyat
            FROM EldenIlaclari ei
            JOIN EldenAna ea ON ei.RIRxId = ea.RxId
            WHERE ea.RxSilme = 0 AND ei.RISilme = 0
            AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
            AND ea.RxKayitTarihi >= DATEADD(year, -2, '{tarih_str}')
            AND ea.RxKayitTarihi <= '{bitis_str}'
        )

        SELECT
            u.UrunId,
            u.UrunAdi,
            COALESCE(u.UrunFiyatEtiket, 0) as PSF,
            COALESCE(u.UrunIskontoKamu, 0) as Iskonto
        FROM Urun u
        WHERE u.UrunSilme = 0
        AND u.UrunUrunTipId IN (1, 2, 3, 16)
        AND EXISTS (
            SELECT 1 FROM UrunHareketleri h WHERE h.UrunId = u.UrunId
        )
        ORDER BY u.UrunAdi
        """

        return self.db.sorgu_calistir(sql)

    def _urun_analiz_yap(self, urun, analiz_tarihi, ay_sayisi, faiz_yillik):
        """
        Tek bir ürün için detaylı stok maliyet analizi.

        Returns:
            dict: Analiz sonuçları
        """
        urun_id = urun['UrunId']
        tarih_str = analiz_tarihi.strftime('%Y-%m-%d')

        # 1. Analiz tarihine kadar olan alımları getir (parti bilgisi için)
        sql_alimlar = f"""
        SELECT
            fg.FGFaturaTarihi as Tarih,
            CAST(fs.FSUrunAdet as int) as Adet,
            CAST(COALESCE(fs.FSUrunMf, 0) as int) as MF,
            CAST(fs.FSUrunBirimFiyat as decimal(18,2)) as BirimFiyat
        FROM FaturaSatir fs
        JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
        WHERE fs.FSUrunId = {urun_id}
        AND fg.FGSilme = 0
        AND fg.FGFaturaTarihi <= '{tarih_str}'
        ORDER BY fg.FGFaturaTarihi ASC
        """
        alimlar = self.db.sorgu_calistir(sql_alimlar) or []

        # 2. Analiz tarihine kadar olan sarfları getir
        sql_sarf_oncesi = f"""
        SELECT
            (SELECT COALESCE(SUM(ri.RIAdet), 0)
             FROM ReceteIlaclari ri
             JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
             WHERE ri.RIUrunId = {urun_id}
             AND ra.RxSilme = 0 AND ri.RISilme = 0
             AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
             AND CAST(ra.RxKayitTarihi as date) < '{tarih_str}')
            +
            (SELECT COALESCE(SUM(ei.RIAdet), 0)
             FROM EldenIlaclari ei
             JOIN EldenAna ea ON ei.RIRxId = ea.RxId
             WHERE ei.RIUrunId = {urun_id}
             AND ea.RxSilme = 0 AND ei.RISilme = 0
             AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
             AND CAST(ea.RxKayitTarihi as date) < '{tarih_str}')
        as ToplamSarf
        """
        sarf_oncesi = self.db.sorgu_calistir(sql_sarf_oncesi)
        toplam_sarf_oncesi = int(sarf_oncesi[0]['ToplamSarf'] or 0) if sarf_oncesi else 0

        # 3. Analiz tarihindeki stoğu hesapla (FIFO mantığı ile partiler)
        toplam_alim = sum(int(a['Adet'] or 0) + int(a['MF'] or 0) for a in alimlar)
        stok_analiz_tarihi = toplam_alim - toplam_sarf_oncesi

        if stok_analiz_tarihi <= 0:
            return None  # Stok yok, analiz gerekmez

        # 4. Partileri belirle (FIFO - önce alınan önce gider)
        partiler = []
        kalan_sarf = toplam_sarf_oncesi

        for alim in alimlar:
            adet = int(alim['Adet'] or 0)
            mf = int(alim['MF'] or 0)
            toplam_parti = adet + mf
            birim_fiyat = float(alim['BirimFiyat'] or 0)

            # MF'li alımlarda efektif birim fiyat
            if mf > 0 and adet > 0:
                efektif_fiyat = (adet * birim_fiyat) / toplam_parti
            else:
                efektif_fiyat = birim_fiyat

            # Bu partiden ne kadar kaldı?
            if kalan_sarf >= toplam_parti:
                kalan_sarf -= toplam_parti
                continue  # Bu parti tamamen tüketilmiş
            elif kalan_sarf > 0:
                kalan_adet = toplam_parti - kalan_sarf
                kalan_sarf = 0
            else:
                kalan_adet = toplam_parti

            if kalan_adet > 0:
                partiler.append({
                    'tarih': alim['Tarih'],
                    'adet': kalan_adet,
                    'mf': mf,
                    'birim_fiyat': efektif_fiyat,
                    'toplam_deger': kalan_adet * efektif_fiyat,
                    'orijinal_adet': adet,
                    'orijinal_mf': mf
                })

        if not partiler:
            return None

        # 5. Analiz dönemindeki aylık sarfları getir
        aylik_sarflar = []
        for i in range(ay_sayisi):
            ay_baslangic = analiz_tarihi + relativedelta(months=i)
            ay_bitis = ay_baslangic + relativedelta(months=1)

            sql_aylik = f"""
            SELECT
                (SELECT COALESCE(SUM(ri.RIAdet), 0)
                 FROM ReceteIlaclari ri
                 JOIN ReceteAna ra ON ri.RIRxId = ra.RxId
                 WHERE ri.RIUrunId = {urun_id}
                 AND ra.RxSilme = 0 AND ri.RISilme = 0
                 AND (ri.RIIade = 0 OR ri.RIIade IS NULL)
                 AND CAST(ra.RxKayitTarihi as date) >= '{ay_baslangic.strftime('%Y-%m-%d')}'
                 AND CAST(ra.RxKayitTarihi as date) < '{ay_bitis.strftime('%Y-%m-%d')}')
                +
                (SELECT COALESCE(SUM(ei.RIAdet), 0)
                 FROM EldenIlaclari ei
                 JOIN EldenAna ea ON ei.RIRxId = ea.RxId
                 WHERE ei.RIUrunId = {urun_id}
                 AND ea.RxSilme = 0 AND ei.RISilme = 0
                 AND (ei.RIIade = 0 OR ei.RIIade IS NULL)
                 AND CAST(ea.RxKayitTarihi as date) >= '{ay_baslangic.strftime('%Y-%m-%d')}'
                 AND CAST(ea.RxKayitTarihi as date) < '{ay_bitis.strftime('%Y-%m-%d')}')
            as AylikSarf
            """
            sonuc = self.db.sorgu_calistir(sql_aylik)
            sarf = int(sonuc[0]['AylikSarf'] or 0) if sonuc else 0
            aylik_sarflar.append({
                'ay': ay_baslangic.strftime('%Y-%m'),
                'ay_adi': ay_baslangic.strftime('%b %y'),
                'sarf': sarf
            })

        # 6. Analiz döneminde yeni alımları getir
        bitis_tarihi = analiz_tarihi + relativedelta(months=ay_sayisi)
        sql_yeni_alimlar = f"""
        SELECT
            fg.FGFaturaTarihi as Tarih,
            CAST(fs.FSUrunAdet as int) as Adet,
            CAST(COALESCE(fs.FSUrunMf, 0) as int) as MF,
            CAST(fs.FSUrunBirimFiyat as decimal(18,2)) as BirimFiyat
        FROM FaturaSatir fs
        JOIN FaturaGiris fg ON fs.FSFGId = fg.FGId
        WHERE fs.FSUrunId = {urun_id}
        AND fg.FGSilme = 0
        AND fg.FGFaturaTarihi > '{tarih_str}'
        AND fg.FGFaturaTarihi <= '{bitis_tarihi.strftime('%Y-%m-%d')}'
        ORDER BY fg.FGFaturaTarihi ASC
        """
        yeni_alimlar = self.db.sorgu_calistir(sql_yeni_alimlar) or []

        # 7. Fırsat maliyeti ve avantajları hesapla
        return self._maliyet_avantaj_hesapla(
            urun, partiler, aylik_sarflar, yeni_alimlar,
            stok_analiz_tarihi, faiz_yillik, analiz_tarihi
        )

    def _maliyet_avantaj_hesapla(self, urun, partiler, aylik_sarflar, yeni_alimlar,
                                  stok_baslangic, faiz_yillik, analiz_tarihi):
        """
        Fırsat maliyeti ve MF/Zam avantajlarını hesapla.
        """
        aylik_faiz = (faiz_yillik / 100) / 12

        # Toplam stok değeri
        stok_deger = sum(p['toplam_deger'] for p in partiler)
        ort_birim_fiyat = stok_deger / stok_baslangic if stok_baslangic > 0 else 0

        # Güncel fiyat (zam kontrolü için)
        psf = float(urun.get('PSF', 0) or 0)
        iskonto = float(urun.get('Iskonto', 0) or 0)
        guncel_depocu = psf * 0.71 * 1.10 * (1 - iskonto / 100) if psf > 0 else ort_birim_fiyat

        # Aylık ortalama sarf
        toplam_sarf = sum(a['sarf'] for a in aylik_sarflar)
        ay_sayisi = len(aylik_sarflar)
        aylik_ort = toplam_sarf / ay_sayisi if ay_sayisi > 0 else 0

        # Stok/Ay oranı
        stok_ay = stok_baslangic / aylik_ort if aylik_ort > 0 else 999

        # ═══════════════════════════════════════════════════════════════════
        # FIRSAT MALİYETİ HESABI (ay ay)
        # ═══════════════════════════════════════════════════════════════════
        firsat_maliyet_detay = []
        toplam_firsat_maliyet = 0
        kalan_stok = stok_baslangic

        for i, ay in enumerate(aylik_sarflar):
            sarf = ay['sarf']

            # Bu ay sonunda kalan stok
            yeni_kalan = kalan_stok - sarf
            if yeni_kalan < 0:
                yeni_kalan = 0

            # Fazla stok = Bu ay sarftan sonra kalan ve gelecek ay ihtiyacından fazla olan
            # Basitleştirilmiş: Kalan stok > aylık ortalama ise fazla
            fazla_stok = max(0, yeni_kalan - aylik_ort) if i < ay_sayisi - 1 else 0

            if fazla_stok > 0:
                fazla_deger = fazla_stok * ort_birim_fiyat
                ay_firsat_maliyet = fazla_deger * aylik_faiz

                firsat_maliyet_detay.append({
                    'ay': ay['ay_adi'],
                    'sarf': sarf,
                    'kalan': int(yeni_kalan),
                    'fazla': int(fazla_stok),
                    'fazla_deger': fazla_deger,
                    'firsat_maliyet': ay_firsat_maliyet
                })

                toplam_firsat_maliyet += ay_firsat_maliyet

            kalan_stok = yeni_kalan

        # ═══════════════════════════════════════════════════════════════════
        # MF AVANTAJI HESABI
        # ═══════════════════════════════════════════════════════════════════
        mf_avantaj = 0
        mf_detay = []

        for parti in partiler:
            if parti['orijinal_mf'] > 0:
                # MF'li alımda bedava gelen ürünlerin değeri
                bedava_adet = parti['orijinal_mf']
                # Bedava ürünlerin güncel değeri
                bedava_deger = bedava_adet * guncel_depocu

                mf_avantaj += bedava_deger
                mf_detay.append({
                    'tarih': parti['tarih'],
                    'mf': f"{parti['orijinal_adet']}+{parti['orijinal_mf']}",
                    'bedava': bedava_adet,
                    'avantaj': bedava_deger
                })

        # ═══════════════════════════════════════════════════════════════════
        # ZAM AVANTAJI HESABI
        # ═══════════════════════════════════════════════════════════════════
        zam_avantaj = 0
        zam_detay = []

        for parti in partiler:
            fiyat_farki = guncel_depocu - parti['birim_fiyat']
            if fiyat_farki > 0:
                # Ucuza alınmış (zam öncesi veya daha iyi fiyat)
                parti_avantaj = parti['adet'] * fiyat_farki
                zam_avantaj += parti_avantaj
                zam_detay.append({
                    'tarih': parti['tarih'],
                    'adet': parti['adet'],
                    'alis_fiyat': parti['birim_fiyat'],
                    'guncel_fiyat': guncel_depocu,
                    'fark': fiyat_farki,
                    'avantaj': parti_avantaj
                })

        # ═══════════════════════════════════════════════════════════════════
        # NET SONUÇ
        # ═══════════════════════════════════════════════════════════════════
        net_sonuc = -toplam_firsat_maliyet + mf_avantaj + zam_avantaj

        return {
            'urun': urun,
            'urun_adi': urun['UrunAdi'],
            'stok_baslangic': stok_baslangic,
            'aylik_ort': aylik_ort,
            'stok_ay': stok_ay,
            'stok_deger': stok_deger,
            'ort_birim_fiyat': ort_birim_fiyat,
            'guncel_fiyat': guncel_depocu,
            'partiler': partiler,
            'aylik_sarflar': aylik_sarflar,
            'firsat_maliyet': toplam_firsat_maliyet,
            'firsat_maliyet_detay': firsat_maliyet_detay,
            'mf_avantaj': mf_avantaj,
            'mf_detay': mf_detay,
            'zam_avantaj': zam_avantaj,
            'zam_detay': zam_detay,
            'net_sonuc': net_sonuc
        }

    def _sonuclari_goster(self, sonuclar):
        """Sonuçları tabloya yaz"""
        # Tabloyu temizle
        for item in self.sonuc_tree.get_children():
            self.sonuc_tree.delete(item)

        toplam_firsat = 0
        toplam_mf = 0
        toplam_zam = 0
        toplam_net = 0

        for s in sonuclar:
            net = s['net_sonuc']
            if net > 50:
                tag = 'karli'
            elif net < -50:
                tag = 'zarari'
            else:
                tag = 'notr'

            self.sonuc_tree.insert('', 'end', values=(
                s['urun_adi'][:30],
                int(s['stok_baslangic']),
                f"{s['aylik_ort']:.0f}",
                f"{s['stok_ay']:.1f}",
                f"-{s['firsat_maliyet']:.0f}₺",
                f"+{s['mf_avantaj']:.0f}₺",
                f"+{s['zam_avantaj']:.0f}₺",
                f"{'+' if net >= 0 else ''}{net:.0f}₺"
            ), tags=(tag,))

            toplam_firsat += s['firsat_maliyet']
            toplam_mf += s['mf_avantaj']
            toplam_zam += s['zam_avantaj']
            toplam_net += net

        # Özet güncelle
        self.ozet_label.config(
            text=f"Toplam: Fırsat Maliyeti: -{toplam_firsat:.0f}₺ | "
                 f"MF Avantajı: +{toplam_mf:.0f}₺ | "
                 f"Zam Avantajı: +{toplam_zam:.0f}₺ | "
                 f"NET: {'+' if toplam_net >= 0 else ''}{toplam_net:.0f}₺"
        )

        self.durum_label.config(text=f"Analiz tamamlandı: {len(sonuclar)} ürün")

    def _urun_secildi(self, event=None):
        """Listeden ürün seçildiğinde detayları göster"""
        secili = self.sonuc_tree.selection()
        if not secili:
            return

        idx = self.sonuc_tree.index(secili[0])
        if idx >= len(self.analiz_sonuclari):
            return

        sonuc = self.analiz_sonuclari[idx]
        self._detay_goster(sonuc)

    def _detay_goster(self, sonuc):
        """Detaylı analiz göster"""
        # Temizle
        for widget in self.detay_icerik.winfo_children():
            widget.destroy()

        # Başlık
        tk.Label(self.detay_icerik, text=sonuc['urun_adi'],
                font=('Arial', 12, 'bold'), bg='#ECEFF1', fg='#5D4037').pack(anchor='w', pady=(5, 10))

        # ═══════════════════════════════════════════════════════════════════
        # ENVANTER BİLGİSİ
        # ═══════════════════════════════════════════════════════════════════
        envanter_frame = tk.LabelFrame(self.detay_icerik, text=" 📦 Analiz Tarihindeki Envanter ",
                                       font=('Arial', 9, 'bold'), bg='#FFF3E0', padx=10, pady=8)
        envanter_frame.pack(fill=tk.X, pady=5)

        tk.Label(envanter_frame,
                text=f"Stok: {sonuc['stok_baslangic']} adet | "
                     f"Değer: {sonuc['stok_deger']:.0f}₺ | "
                     f"Ort. Birim: {sonuc['ort_birim_fiyat']:.2f}₺ | "
                     f"Güncel: {sonuc['guncel_fiyat']:.2f}₺",
                font=('Arial', 9), bg='#FFF3E0').pack(anchor='w')

        # Parti detayları
        if sonuc['partiler']:
            parti_text = "Partiler: "
            for p in sonuc['partiler'][:5]:  # İlk 5 parti
                mf_str = f" (MF {p['orijinal_adet']}+{p['orijinal_mf']})" if p['orijinal_mf'] > 0 else ""
                parti_text += f"{p['adet']} ad×{p['birim_fiyat']:.1f}₺{mf_str} | "
            tk.Label(envanter_frame, text=parti_text[:-3], font=('Arial', 8),
                    bg='#FFF3E0', fg='#666').pack(anchor='w')

        # ═══════════════════════════════════════════════════════════════════
        # AYLIK SARFLAR
        # ═══════════════════════════════════════════════════════════════════
        sarf_frame = tk.LabelFrame(self.detay_icerik, text=" 📉 Aylık Sarflar ",
                                   font=('Arial', 9, 'bold'), bg='#E3F2FD', padx=10, pady=8)
        sarf_frame.pack(fill=tk.X, pady=5)

        sarf_row = tk.Frame(sarf_frame, bg='#E3F2FD')
        sarf_row.pack(fill=tk.X)

        for ay in sonuc['aylik_sarflar']:
            tk.Label(sarf_row, text=f"{ay['ay_adi']}: {ay['sarf']}",
                    font=('Arial', 8), bg='#E3F2FD', width=10).pack(side=tk.LEFT)

        tk.Label(sarf_frame, text=f"Aylık Ortalama: {sonuc['aylik_ort']:.1f} | "
                                  f"Stok/Ay Oranı: {sonuc['stok_ay']:.1f}",
                font=('Arial', 9, 'bold'), bg='#E3F2FD').pack(anchor='w', pady=(5, 0))

        # ═══════════════════════════════════════════════════════════════════
        # FIRSAT MALİYETİ
        # ═══════════════════════════════════════════════════════════════════
        if sonuc['firsat_maliyet_detay']:
            firsat_frame = tk.LabelFrame(self.detay_icerik, text=" 💸 Fırsat Maliyeti (Fazla Stok Bedeli) ",
                                         font=('Arial', 9, 'bold'), bg='#FFCDD2', padx=10, pady=8)
            firsat_frame.pack(fill=tk.X, pady=5)

            # Başlık
            baslik = tk.Frame(firsat_frame, bg='#E57373')
            baslik.pack(fill=tk.X)
            for txt, w in [("Ay", 8), ("Sarf", 5), ("Kalan", 5), ("Fazla", 5), ("Değer", 8), ("F.Maliyet", 8)]:
                tk.Label(baslik, text=txt, font=('Arial', 8, 'bold'), bg='#E57373', fg='white',
                        width=w).pack(side=tk.LEFT)

            for d in sonuc['firsat_maliyet_detay']:
                row = tk.Frame(firsat_frame, bg='#FFCDD2')
                row.pack(fill=tk.X)
                tk.Label(row, text=d['ay'], font=('Arial', 8), bg='#FFCDD2', width=8).pack(side=tk.LEFT)
                tk.Label(row, text=str(d['sarf']), font=('Arial', 8), bg='#FFCDD2', width=5).pack(side=tk.LEFT)
                tk.Label(row, text=str(d['kalan']), font=('Arial', 8), bg='#FFCDD2', width=5).pack(side=tk.LEFT)
                tk.Label(row, text=str(d['fazla']), font=('Arial', 8), bg='#FFCDD2', width=5).pack(side=tk.LEFT)
                tk.Label(row, text=f"{d['fazla_deger']:.0f}₺", font=('Arial', 8), bg='#FFCDD2', width=8).pack(side=tk.LEFT)
                tk.Label(row, text=f"-{d['firsat_maliyet']:.0f}₺", font=('Arial', 8, 'bold'),
                        bg='#FFCDD2', fg='#C62828', width=8).pack(side=tk.LEFT)

            tk.Label(firsat_frame, text=f"TOPLAM FIRSAT MALİYETİ: -{sonuc['firsat_maliyet']:.0f}₺",
                    font=('Arial', 10, 'bold'), bg='#FFCDD2', fg='#B71C1C').pack(anchor='e', pady=(5, 0))

        # ═══════════════════════════════════════════════════════════════════
        # MF AVANTAJI
        # ═══════════════════════════════════════════════════════════════════
        if sonuc['mf_detay']:
            mf_frame = tk.LabelFrame(self.detay_icerik, text=" 🎁 MF Avantajı (Bedava Ürün Değeri) ",
                                     font=('Arial', 9, 'bold'), bg='#C8E6C9', padx=10, pady=8)
            mf_frame.pack(fill=tk.X, pady=5)

            for d in sonuc['mf_detay']:
                row = tk.Frame(mf_frame, bg='#C8E6C9')
                row.pack(fill=tk.X)
                tarih_str = d['tarih'].strftime('%d.%m.%y') if hasattr(d['tarih'], 'strftime') else str(d['tarih'])[:10]
                tk.Label(row, text=f"{tarih_str}: MF {d['mf']} → {d['bedava']} bedava = +{d['avantaj']:.0f}₺",
                        font=('Arial', 9), bg='#C8E6C9').pack(anchor='w')

            tk.Label(mf_frame, text=f"TOPLAM MF AVANTAJI: +{sonuc['mf_avantaj']:.0f}₺",
                    font=('Arial', 10, 'bold'), bg='#C8E6C9', fg='#1B5E20').pack(anchor='e', pady=(5, 0))

        # ═══════════════════════════════════════════════════════════════════
        # ZAM AVANTAJI
        # ═══════════════════════════════════════════════════════════════════
        if sonuc['zam_detay']:
            zam_frame = tk.LabelFrame(self.detay_icerik, text=" 📈 Zam Avantajı (Ucuza Alınmış) ",
                                      font=('Arial', 9, 'bold'), bg='#DCEDC8', padx=10, pady=8)
            zam_frame.pack(fill=tk.X, pady=5)

            for d in sonuc['zam_detay']:
                row = tk.Frame(zam_frame, bg='#DCEDC8')
                row.pack(fill=tk.X)
                tarih_str = d['tarih'].strftime('%d.%m.%y') if hasattr(d['tarih'], 'strftime') else str(d['tarih'])[:10]
                tk.Label(row, text=f"{tarih_str}: {d['adet']} ad × ({d['guncel_fiyat']:.1f}-{d['alis_fiyat']:.1f})₺ = +{d['avantaj']:.0f}₺",
                        font=('Arial', 9), bg='#DCEDC8').pack(anchor='w')

            tk.Label(zam_frame, text=f"TOPLAM ZAM AVANTAJI: +{sonuc['zam_avantaj']:.0f}₺",
                    font=('Arial', 10, 'bold'), bg='#DCEDC8', fg='#33691E').pack(anchor='e', pady=(5, 0))

        # ═══════════════════════════════════════════════════════════════════
        # NET SONUÇ
        # ═══════════════════════════════════════════════════════════════════
        net = sonuc['net_sonuc']
        net_bg = '#C8E6C9' if net >= 0 else '#FFCDD2'
        net_fg = '#1B5E20' if net >= 0 else '#B71C1C'
        sonuc_text = "STOK YAPMAK KARLI" if net >= 0 else "STOK YAPMAK ZARARLI"

        net_frame = tk.Frame(self.detay_icerik, bg=net_bg, pady=10)
        net_frame.pack(fill=tk.X, pady=10)

        tk.Label(net_frame, text=f"NET SONUÇ: {'+' if net >= 0 else ''}{net:.0f}₺",
                font=('Arial', 14, 'bold'), bg=net_bg, fg=net_fg).pack()
        tk.Label(net_frame, text=sonuc_text, font=('Arial', 11, 'bold'),
                bg=net_bg, fg=net_fg).pack()

        tk.Label(net_frame,
                text=f"Fırsat Mal: -{sonuc['firsat_maliyet']:.0f}₺ + MF Av: +{sonuc['mf_avantaj']:.0f}₺ + Zam Av: +{sonuc['zam_avantaj']:.0f}₺",
                font=('Arial', 9), bg=net_bg, fg='#555').pack(pady=(5, 0))

    def _excel_aktar(self):
        """Sonuçları Excel'e aktar"""
        if not self.analiz_sonuclari:
            messagebox.showwarning("Uyarı", "Önce analiz yapın!")
            return

        try:
            import pandas as pd
            from tkinter import filedialog

            # Dosya adı sor
            dosya = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel dosyası", "*.xlsx")],
                initialfile=f"stok_maliyet_analizi_{date.today().strftime('%Y%m%d')}.xlsx"
            )

            if not dosya:
                return

            # DataFrame oluştur
            data = []
            for s in self.analiz_sonuclari:
                data.append({
                    'Ürün Adı': s['urun_adi'],
                    'Stok (Adet)': s['stok_baslangic'],
                    'Stok Değeri (₺)': round(s['stok_deger'], 2),
                    'Aylık Ortalama': round(s['aylik_ort'], 1),
                    'Stok/Ay': round(s['stok_ay'], 1),
                    'Fırsat Maliyeti (₺)': round(-s['firsat_maliyet'], 2),
                    'MF Avantajı (₺)': round(s['mf_avantaj'], 2),
                    'Zam Avantajı (₺)': round(s['zam_avantaj'], 2),
                    'Net Sonuç (₺)': round(s['net_sonuc'], 2)
                })

            df = pd.DataFrame(data)
            df.to_excel(dosya, index=False)

            messagebox.showinfo("Başarılı", f"Excel dosyası kaydedildi:\n{dosya}")

        except ImportError:
            messagebox.showerror("Hata", "pandas ve openpyxl modülleri gerekli!\npip install pandas openpyxl")
        except Exception as e:
            messagebox.showerror("Hata", f"Excel aktarım hatası: {e}")


def main():
    """Test için bağımsız çalıştırma"""
    root = tk.Tk()
    app = StokMaliyetAnalizGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
