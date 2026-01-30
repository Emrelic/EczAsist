"""
Üretici Firma / Depo Alış Raporu GUI
Tarih, üretici firma ve depo bazlı fatura sorgulama
Fatura bazlı veya satır bazlı görüntüleme
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
from datetime import datetime, date, timedelta
from tkcalendar import DateEntry
import csv

# tksheet import
try:
    from tksheet import Sheet
    TKSHEET_AVAILABLE = True
except ImportError:
    TKSHEET_AVAILABLE = False

logger = logging.getLogger(__name__)


class UreticiFirmaRaporGUI:
    """Üretici Firma / Depo Alış Raporu Penceresi"""

    def __init__(self, parent):
        self.parent = parent
        self.parent.title("Üretici Firma / Depo Alış Raporu")
        self.parent.geometry("1600x800")

        self.db = None
        self.veriler = []
        self.firmalar = []
        self.depolar = []
        self.gorunum_modu = tk.StringVar(value="satir")  # "fatura" veya "satir"

        # tksheet kontrolü
        if not TKSHEET_AVAILABLE:
            messagebox.showerror("Hata", "tksheet kütüphanesi kurulu değil!\npip install tksheet")
            return

        self._arayuz_olustur()
        self._baglanti_kur()

    def _arayuz_olustur(self):
        """Ana arayüzü oluştur"""
        main_frame = ttk.Frame(self.parent, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Üst panel - Filtreler
        self._filtre_panel_olustur(main_frame)

        # Orta panel - Tablo
        self._tablo_olustur(main_frame)

        # Alt panel - Status bar
        self._status_bar_olustur(main_frame)

    def _filtre_panel_olustur(self, parent):
        """Filtre panelini oluştur"""
        filtre_frame = ttk.LabelFrame(parent, text="Filtreler", padding=5)
        filtre_frame.pack(fill=tk.X, pady=(0, 5))

        # Satır 1 - Tarih, Firma, Depo
        row1 = ttk.Frame(filtre_frame)
        row1.pack(fill=tk.X, pady=2)

        # Başlangıç Tarihi
        ttk.Label(row1, text="Başlangıç:").pack(side=tk.LEFT, padx=(0, 5))
        self.baslangic_tarih = DateEntry(
            row1, width=12, date_pattern='dd.mm.yyyy',
            year=datetime.now().year, month=1, day=1
        )
        self.baslangic_tarih.pack(side=tk.LEFT, padx=(0, 15))

        # Bitiş Tarihi
        ttk.Label(row1, text="Bitiş:").pack(side=tk.LEFT, padx=(0, 5))
        self.bitis_tarih = DateEntry(
            row1, width=12, date_pattern='dd.mm.yyyy'
        )
        self.bitis_tarih.pack(side=tk.LEFT, padx=(0, 15))

        # Üretici Firma
        ttk.Label(row1, text="Üretici Firma:").pack(side=tk.LEFT, padx=(0, 5))
        self.firma_combo = ttk.Combobox(row1, width=30, state="readonly")
        self.firma_combo['values'] = ["Tümü"]
        self.firma_combo.set("Tümü")
        self.firma_combo.pack(side=tk.LEFT, padx=(0, 15))

        # Depo
        ttk.Label(row1, text="Depo:").pack(side=tk.LEFT, padx=(0, 5))
        self.depo_combo = ttk.Combobox(row1, width=25, state="readonly")
        self.depo_combo['values'] = ["Tümü"]
        self.depo_combo.set("Tümü")
        self.depo_combo.pack(side=tk.LEFT, padx=(0, 15))

        # Satır 2 - Görünüm ve diğer ayarlar
        row2 = ttk.Frame(filtre_frame)
        row2.pack(fill=tk.X, pady=2)

        # Görünüm modu
        ttk.Label(row2, text="Görünüm:").pack(side=tk.LEFT, padx=(0, 5))

        ttk.Radiobutton(
            row2, text="Satır Bazlı",
            variable=self.gorunum_modu, value="satir"
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Radiobutton(
            row2, text="Fatura Bazlı",
            variable=self.gorunum_modu, value="fatura"
        ).pack(side=tk.LEFT, padx=(0, 20))

        # Silinmiş faturaları dahil et
        self.silinen_dahil = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            row2, text="Silinmiş faturaları dahil et",
            variable=self.silinen_dahil
        ).pack(side=tk.LEFT, padx=(0, 20))

        # Ürün adı filtresi
        ttk.Label(row2, text="Ürün Adı:").pack(side=tk.LEFT, padx=(0, 5))
        self.urun_adi_entry = ttk.Entry(row2, width=25)
        self.urun_adi_entry.pack(side=tk.LEFT, padx=(0, 15))

        # Sorgula butonu
        ttk.Button(row2, text="Sorgula", command=self.sorgula, width=12).pack(side=tk.LEFT, padx=(0, 8))

        # Excel Aktar
        ttk.Button(row2, text="Excel Aktar", command=self.excel_aktar, width=12).pack(side=tk.LEFT, padx=(0, 8))

        # Satır 3 - Tablo filtresi ve özet
        row3 = ttk.Frame(filtre_frame)
        row3.pack(fill=tk.X, pady=2)

        ttk.Label(row3, text="Tablo Filtresi:").pack(side=tk.LEFT, padx=(0, 5))
        self.tablo_filtre_entry = ttk.Entry(row3, width=30)
        self.tablo_filtre_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.tablo_filtre_entry.bind('<KeyRelease>', self._tablo_filtrele)

        ttk.Button(row3, text="Temizle", command=self._filtreleri_temizle, width=10).pack(side=tk.LEFT, padx=(0, 20))

        # Özet label
        self.ozet_label = ttk.Label(row3, text="", font=("Arial", 10, "bold"))
        self.ozet_label.pack(side=tk.RIGHT, padx=10)

    def _tablo_olustur(self, parent):
        """Tabloyu oluştur - tksheet kullanarak"""
        tablo_frame = ttk.Frame(parent)
        tablo_frame.pack(fill=tk.BOTH, expand=True)

        # Varsayılan sütun başlıkları (satır bazlı)
        self.satir_headers = [
            "Tarih", "Fatura No", "Depo", "Üretici Firma", "Ürün Adı",
            "Adet", "Birim Fiyat", "Maliyet", "Toplam Tutar", "Silme"
        ]

        self.fatura_headers = [
            "Tarih", "Fatura No", "Depo", "Kalem Sayısı", "Toplam Adet",
            "Toplam Tutar", "Silme"
        ]

        # tksheet oluştur
        self.sheet = Sheet(
            tablo_frame,
            headers=self.satir_headers,
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            height=600,
            width=1580
        )
        self.sheet.pack(fill=tk.BOTH, expand=True)

        # Sheet ayarları
        self.sheet.enable_bindings((
            "single_select", "row_select", "column_select",
            "drag_select", "select_all", "column_width_resize",
            "double_click_column_resize", "copy", "cut", "paste",
            "delete", "undo", "edit_cell"
        ))

        # Sütun genişlikleri
        self._sutun_genisliklerini_ayarla()

    def _sutun_genisliklerini_ayarla(self):
        """Görünüm moduna göre sütun genişliklerini ayarla"""
        if self.gorunum_modu.get() == "satir":
            widths = [90, 120, 150, 180, 350, 70, 100, 100, 120, 60]
        else:
            widths = [90, 150, 200, 100, 100, 150, 60]

        for i, w in enumerate(widths):
            try:
                self.sheet.column_width(i, width=w)
            except:
                pass

    def _status_bar_olustur(self, parent):
        """Status bar oluştur"""
        self.status_frame = ttk.Frame(parent)
        self.status_frame.pack(fill=tk.X, pady=(5, 0))

        self.status_label = ttk.Label(self.status_frame, text="Hazır")
        self.status_label.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(self.status_frame, mode='indeterminate', length=200)
        self.progress.pack(side=tk.RIGHT)

    def _baglanti_kur(self):
        """Veritabanı bağlantısını kur ve comboları doldur"""
        try:
            from botanik_db import BotanikDB
            self.db = BotanikDB(production=True)
            if self.db.baglan():
                self._status_guncelle("Veritabanı bağlantısı kuruldu")
                self._firmalari_yukle()
                self._depolari_yukle()
            else:
                self._status_guncelle("Veritabanı bağlantısı kurulamadı!")
        except Exception as e:
            logger.error(f"Bağlantı hatası: {e}")
            self._status_guncelle(f"Hata: {e}")

    def _firmalari_yukle(self):
        """Üretici firmaları yükle"""
        try:
            sql = """
                SELECT DISTINCT f.FirmaId, f.FirmaAdi
                FROM Firma f
                JOIN Urun u ON u.UrunFirmaId = f.FirmaId
                WHERE f.FirmaSilme = 0 AND u.UrunSilme = 0
                ORDER BY f.FirmaAdi
            """
            sonuclar = self.db.sorgu_calistir(sql)
            self.firmalar = [(None, "Tümü")] + [(r['FirmaId'], r['FirmaAdi']) for r in sonuclar]
            self.firma_combo['values'] = [f[1] for f in self.firmalar]
            self.firma_combo.set("Tümü")
            self._status_guncelle(f"{len(self.firmalar)-1} firma yüklendi")
        except Exception as e:
            logger.error(f"Firma yükleme hatası: {e}")

    def _depolari_yukle(self):
        """Depoları yükle"""
        try:
            sql = """
                SELECT DISTINCT d.DepoId, d.DepoAdi
                FROM Depo d
                JOIN FaturaGiris fg ON fg.FGIlgiliId = d.DepoId
                WHERE d.DepoSilme = 0
                ORDER BY d.DepoAdi
            """
            sonuclar = self.db.sorgu_calistir(sql)
            self.depolar = [(None, "Tümü")] + [(r['DepoId'], r['DepoAdi']) for r in sonuclar]
            self.depo_combo['values'] = [d[1] for d in self.depolar]
            self.depo_combo.set("Tümü")
        except Exception as e:
            logger.error(f"Depo yükleme hatası: {e}")

    def sorgula(self):
        """Verileri sorgula"""
        if not self.db:
            messagebox.showerror("Hata", "Veritabanı bağlantısı yok!")
            return

        # Thread ile sorgu
        self.progress.start()
        self._status_guncelle("Sorgulanıyor...")

        thread = threading.Thread(target=self._sorgu_thread)
        thread.daemon = True
        thread.start()

    def _sorgu_thread(self):
        """Sorgu thread'i"""
        try:
            # Tarih aralığı
            baslangic = self.baslangic_tarih.get_date().strftime('%Y-%m-%d')
            bitis = self.bitis_tarih.get_date().strftime('%Y-%m-%d')

            # Firma filtresi
            firma_idx = self.firma_combo.current()
            firma_id = self.firmalar[firma_idx][0] if firma_idx > 0 else None

            # Depo filtresi
            depo_idx = self.depo_combo.current()
            depo_id = self.depolar[depo_idx][0] if depo_idx > 0 else None

            # Ürün adı filtresi
            urun_adi = self.urun_adi_entry.get().strip()

            # Silinmiş faturaları dahil et
            silinen_dahil = self.silinen_dahil.get()

            # Görünüm modu
            gorunum = self.gorunum_modu.get()

            if gorunum == "satir":
                self._satir_bazli_sorgu(baslangic, bitis, firma_id, depo_id, urun_adi, silinen_dahil)
            else:
                self._fatura_bazli_sorgu(baslangic, bitis, firma_id, depo_id, urun_adi, silinen_dahil)

        except Exception as e:
            logger.error(f"Sorgu hatası: {e}")
            self.parent.after(0, lambda: messagebox.showerror("Hata", f"Sorgu hatası:\n{e}"))
        finally:
            self.parent.after(0, self.progress.stop)

    def _satir_bazli_sorgu(self, baslangic, bitis, firma_id, depo_id, urun_adi, silinen_dahil):
        """Satır bazlı sorgu"""
        where_kosullari = [
            f"fg.FGFaturaTarihi >= '{baslangic}'",
            f"fg.FGFaturaTarihi <= '{bitis}'"
        ]

        if not silinen_dahil:
            where_kosullari.append("fg.FGSilme = 0")

        if firma_id:
            where_kosullari.append(f"u.UrunFirmaId = {firma_id}")

        if depo_id:
            where_kosullari.append(f"fg.FGIlgiliId = {depo_id}")

        if urun_adi:
            urun_adi_temiz = urun_adi.replace("'", "''")
            where_kosullari.append(f"u.UrunAdi LIKE '%{urun_adi_temiz}%'")

        where_str = " AND ".join(where_kosullari)

        sql = f"""
            SELECT
                fg.FGFaturaTarihi as Tarih,
                fg.FGFaturaNo as FaturaNo,
                d.DepoAdi,
                f.FirmaAdi,
                u.UrunAdi,
                fs.FSUrunAdet as Adet,
                fs.FSBirimFiyat as BirimFiyat,
                fs.FSMaliyet as Maliyet,
                fs.FSUrunAdet * ISNULL(fs.FSMaliyet, fs.FSBirimFiyat) as ToplamTutar,
                CASE WHEN fg.FGSilme = 1 THEN 'Evet' ELSE '' END as Silme
            FROM FaturaGiris fg
            JOIN FaturaSatir fs ON fg.FGId = fs.FSFGId
            JOIN Urun u ON fs.FSUrunId = u.UrunId
            LEFT JOIN Depo d ON fg.FGIlgiliId = d.DepoId
            LEFT JOIN Firma f ON u.UrunFirmaId = f.FirmaId
            WHERE {where_str}
            ORDER BY fg.FGFaturaTarihi DESC, fg.FGFaturaNo, u.UrunAdi
        """

        sonuclar = self.db.sorgu_calistir(sql)
        self.veriler = sonuclar

        # Tablo verilerini oluştur
        tablo_verileri = []
        toplam_adet = 0
        toplam_tutar = 0

        for r in sonuclar:
            tarih = str(r['Tarih'])[:10] if r['Tarih'] else ''
            birim_fiyat = r['BirimFiyat'] if r['BirimFiyat'] else 0
            maliyet = r['Maliyet'] if r['Maliyet'] else 0
            tutar = r['ToplamTutar'] if r['ToplamTutar'] else 0
            adet = r['Adet'] if r['Adet'] else 0

            toplam_adet += adet
            toplam_tutar += tutar

            tablo_verileri.append([
                tarih,
                r['FaturaNo'] or '',
                r['DepoAdi'] or '',
                r['FirmaAdi'] or '',
                r['UrunAdi'] or '',
                adet,
                f"{birim_fiyat:,.2f}",
                f"{maliyet:,.2f}",
                f"{tutar:,.2f}",
                r['Silme'] or ''
            ])

        # GUI'yi güncelle
        self.parent.after(0, lambda: self._tabloyu_guncelle(
            tablo_verileri,
            self.satir_headers,
            f"Toplam: {len(sonuclar)} satır | {toplam_adet:,.0f} adet | {toplam_tutar:,.2f} TL"
        ))

    def _fatura_bazli_sorgu(self, baslangic, bitis, firma_id, depo_id, urun_adi, silinen_dahil):
        """Fatura bazlı sorgu"""
        where_kosullari = [
            f"fg.FGFaturaTarihi >= '{baslangic}'",
            f"fg.FGFaturaTarihi <= '{bitis}'"
        ]

        if not silinen_dahil:
            where_kosullari.append("fg.FGSilme = 0")

        if firma_id:
            where_kosullari.append(f"u.UrunFirmaId = {firma_id}")

        if depo_id:
            where_kosullari.append(f"fg.FGIlgiliId = {depo_id}")

        if urun_adi:
            urun_adi_temiz = urun_adi.replace("'", "''")
            where_kosullari.append(f"u.UrunAdi LIKE '%{urun_adi_temiz}%'")

        where_str = " AND ".join(where_kosullari)

        sql = f"""
            SELECT
                fg.FGFaturaTarihi as Tarih,
                fg.FGFaturaNo as FaturaNo,
                d.DepoAdi,
                COUNT(DISTINCT fs.FSId) as KalemSayisi,
                SUM(fs.FSUrunAdet) as ToplamAdet,
                SUM(fs.FSUrunAdet * ISNULL(fs.FSMaliyet, fs.FSBirimFiyat)) as ToplamTutar,
                MAX(CASE WHEN fg.FGSilme = 1 THEN 'Evet' ELSE '' END) as Silme
            FROM FaturaGiris fg
            JOIN FaturaSatir fs ON fg.FGId = fs.FSFGId
            JOIN Urun u ON fs.FSUrunId = u.UrunId
            LEFT JOIN Depo d ON fg.FGIlgiliId = d.DepoId
            WHERE {where_str}
            GROUP BY fg.FGId, fg.FGFaturaTarihi, fg.FGFaturaNo, d.DepoAdi
            ORDER BY fg.FGFaturaTarihi DESC, fg.FGFaturaNo
        """

        sonuclar = self.db.sorgu_calistir(sql)
        self.veriler = sonuclar

        # Tablo verilerini oluştur
        tablo_verileri = []
        toplam_adet = 0
        toplam_tutar = 0

        for r in sonuclar:
            tarih = str(r['Tarih'])[:10] if r['Tarih'] else ''
            adet = r['ToplamAdet'] if r['ToplamAdet'] else 0
            tutar = r['ToplamTutar'] if r['ToplamTutar'] else 0

            toplam_adet += adet
            toplam_tutar += tutar

            tablo_verileri.append([
                tarih,
                r['FaturaNo'] or '',
                r['DepoAdi'] or '',
                r['KalemSayisi'] or 0,
                adet,
                f"{tutar:,.2f}",
                r['Silme'] or ''
            ])

        # GUI'yi güncelle
        self.parent.after(0, lambda: self._tabloyu_guncelle(
            tablo_verileri,
            self.fatura_headers,
            f"Toplam: {len(sonuclar)} fatura | {toplam_adet:,.0f} adet | {toplam_tutar:,.2f} TL"
        ))

    def _tabloyu_guncelle(self, veriler, basliklar, ozet_text):
        """Tabloyu güncelle"""
        self.sheet.headers(basliklar)
        self.sheet.set_sheet_data(veriler)
        self._sutun_genisliklerini_ayarla()
        self.ozet_label.config(text=ozet_text)
        self._status_guncelle(f"{len(veriler)} kayıt listelendi")

    def _tablo_filtrele(self, event=None):
        """Tablo içi filtreleme"""
        filtre = self.tablo_filtre_entry.get().lower().strip()

        if not filtre:
            # Filtreyi kaldır, tüm veriyi göster
            if hasattr(self, '_tam_veri'):
                self.sheet.set_sheet_data(self._tam_veri)
            return

        # İlk filtrelemede tam veriyi sakla
        if not hasattr(self, '_tam_veri') or not self._tam_veri:
            self._tam_veri = self.sheet.get_sheet_data()

        # Filtrele
        filtrelenmis = []
        for satir in self._tam_veri:
            for hucre in satir:
                if filtre in str(hucre).lower():
                    filtrelenmis.append(satir)
                    break

        self.sheet.set_sheet_data(filtrelenmis)
        self._status_guncelle(f"{len(filtrelenmis)} / {len(self._tam_veri)} kayıt gösteriliyor")

    def _filtreleri_temizle(self):
        """Tablo filtresini temizle"""
        self.tablo_filtre_entry.delete(0, tk.END)
        if hasattr(self, '_tam_veri') and self._tam_veri:
            self.sheet.set_sheet_data(self._tam_veri)
            self._status_guncelle(f"{len(self._tam_veri)} kayıt listelendi")

    def excel_aktar(self):
        """Veriyi Excel/CSV olarak aktar"""
        if not self.veriler:
            messagebox.showwarning("Uyarı", "Aktarılacak veri yok!")
            return

        dosya = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV dosyası", "*.csv"), ("Tüm dosyalar", "*.*")],
            title="Excel/CSV Olarak Kaydet"
        )

        if not dosya:
            return

        try:
            with open(dosya, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')

                # Başlıklar
                if self.gorunum_modu.get() == "satir":
                    writer.writerow(self.satir_headers)
                else:
                    writer.writerow(self.fatura_headers)

                # Veriler
                sheet_data = self.sheet.get_sheet_data()
                for satir in sheet_data:
                    writer.writerow(satir)

            messagebox.showinfo("Başarılı", f"Veriler kaydedildi:\n{dosya}")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydetme hatası:\n{e}")

    def _status_guncelle(self, mesaj):
        """Status bar güncelle"""
        self.status_label.config(text=mesaj)


# Test
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    pencere = tk.Toplevel(root)
    app = UreticiFirmaRaporGUI(pencere)
    root.mainloop()
