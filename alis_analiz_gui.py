"""
Alis Analiz Raporu GUI
Fatura bazli alis analizi - stok ve satis oranlamalari
tksheet ile hucre bazli renklendirme
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
from datetime import datetime, date, timedelta
from tkcalendar import DateEntry
import csv

# tksheet import - kurulu degilse uyari ver
try:
    from tksheet import Sheet
    TKSHEET_AVAILABLE = True
except ImportError:
    TKSHEET_AVAILABLE = False

logger = logging.getLogger(__name__)

# Renk tanimlari
RENK_BEYAZ = "#FFFFFF"      # Bu ay bitiyor
RENK_SARI = "#FFFF99"       # 1 aya sarkiyor
RENK_TURUNCU = "#FFCC66"    # 2 aya sarkiyor
RENK_KIRMIZI = "#FF9999"    # 3 aya sarkiyor
RENK_MOR = "#CC99FF"        # 4+ aya sarkiyor


class AlisAnalizGUI:
    """Alis Analiz Raporu Penceresi"""

    def __init__(self, parent):
        self.parent = parent
        self.parent.title("Alis Analiz Raporu")
        self.parent.geometry("1920x900")

        self.db = None
        self.veriler = []
        self.filtrelenmis_veriler = []
        self.depolar = []
        self.tablo_verileri = []  # Sheet icin veri listesi

        # tksheet kontrolu
        if not TKSHEET_AVAILABLE:
            messagebox.showerror("Hata", "tksheet kutuphanesi kurulu degil!\npip install tksheet")
            return

        self._arayuz_olustur()
        self._baglanti_kur()

    def _arayuz_olustur(self):
        """Ana arayuzu olustur"""
        # Ana frame
        main_frame = ttk.Frame(self.parent, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Ust panel - Filtreler
        self._filtre_panel_olustur(main_frame)

        # Orta panel - Tablo
        self._tablo_olustur(main_frame)

        # Alt panel - Status bar
        self._status_bar_olustur(main_frame)

    def _filtre_panel_olustur(self, parent):
        """Filtre panelini olustur"""
        filtre_frame = ttk.LabelFrame(parent, text="Filtreler", padding=5)
        filtre_frame.pack(fill=tk.X, pady=(0, 5))

        # Satir 1 - Tarih ve Depo
        row1 = ttk.Frame(filtre_frame)
        row1.pack(fill=tk.X, pady=2)

        # Baslangic Tarihi
        ttk.Label(row1, text="Baslangic:").pack(side=tk.LEFT, padx=(0, 5))
        self.baslangic_tarih = DateEntry(
            row1, width=12, date_pattern='dd.mm.yyyy',
            year=datetime.now().year, month=1, day=1
        )
        self.baslangic_tarih.pack(side=tk.LEFT, padx=(0, 15))

        # Bitis Tarihi
        ttk.Label(row1, text="Bitis:").pack(side=tk.LEFT, padx=(0, 5))
        self.bitis_tarih = DateEntry(
            row1, width=12, date_pattern='dd.mm.yyyy'
        )
        self.bitis_tarih.pack(side=tk.LEFT, padx=(0, 15))

        # Depo
        ttk.Label(row1, text="Depo:").pack(side=tk.LEFT, padx=(0, 5))
        self.depo_combo = ttk.Combobox(row1, width=25, state="readonly")
        self.depo_combo['values'] = ["Tumu"]
        self.depo_combo.set("Tumu")
        self.depo_combo.pack(side=tk.LEFT, padx=(0, 15))

        # Urun Adi
        ttk.Label(row1, text="Urun Adi:").pack(side=tk.LEFT, padx=(0, 5))
        self.urun_adi_entry = ttk.Entry(row1, width=25)
        self.urun_adi_entry.pack(side=tk.LEFT, padx=(0, 15))

        # Satir 2 - Ayarlar
        row2 = ttk.Frame(filtre_frame)
        row2.pack(fill=tk.X, pady=2)

        # Ortalama hesabi icin kac ay
        ttk.Label(row2, text="Ortalama (Ay):").pack(side=tk.LEFT, padx=(0, 5))
        self.ortalama_ay_combo = ttk.Combobox(row2, width=4, state="readonly")
        self.ortalama_ay_combo['values'] = ["3", "6", "12", "24"]
        self.ortalama_ay_combo.set("6")
        self.ortalama_ay_combo.pack(side=tk.LEFT, padx=(0, 10))

        # Mevduat Faizi
        ttk.Label(row2, text="Faiz (%):").pack(side=tk.LEFT, padx=(0, 5))
        self.faiz_entry = ttk.Entry(row2, width=5)
        self.faiz_entry.insert(0, "45")
        self.faiz_entry.pack(side=tk.LEFT, padx=(0, 10))

        # Depo Vadesi
        ttk.Label(row2, text="Depo Vade (Gun):").pack(side=tk.LEFT, padx=(0, 5))
        self.depo_vade_entry = ttk.Entry(row2, width=4)
        self.depo_vade_entry.insert(0, "75")
        self.depo_vade_entry.pack(side=tk.LEFT, padx=(0, 10))

        # Zam Tarihi
        ttk.Label(row2, text="Zam Tarihi:").pack(side=tk.LEFT, padx=(0, 5))
        self.zam_tarihi = DateEntry(row2, width=10, date_pattern='dd.mm.yyyy')
        self.zam_tarihi.set_date(datetime.now() + timedelta(days=365))
        self.zam_tarihi.pack(side=tk.LEFT, padx=(0, 10))

        # Beklenen Zam Orani
        ttk.Label(row2, text="Zam (%):").pack(side=tk.LEFT, padx=(0, 5))
        self.zam_orani_entry = ttk.Entry(row2, width=4)
        self.zam_orani_entry.insert(0, "0")
        self.zam_orani_entry.pack(side=tk.LEFT, padx=(0, 10))

        # Limit
        ttk.Label(row2, text="Limit:").pack(side=tk.LEFT, padx=(0, 5))
        self.limit_combo = ttk.Combobox(row2, width=6, state="readonly")
        self.limit_combo['values'] = ["1000", "2000", "5000", "10000", "Tumu"]
        self.limit_combo.set("5000")
        self.limit_combo.pack(side=tk.LEFT, padx=(0, 10))

        # Sorgula butonu
        ttk.Button(row2, text="Sorgula", command=self.sorgula, width=10).pack(side=tk.LEFT, padx=(0, 8))

        # Excel Aktar
        ttk.Button(row2, text="Excel Aktar", command=self.excel_aktar, width=10).pack(side=tk.LEFT, padx=(0, 8))

        # Satir 3 - Tablo filtresi
        row3 = ttk.Frame(filtre_frame)
        row3.pack(fill=tk.X, pady=2)

        ttk.Label(row3, text="Tablo Filtresi:").pack(side=tk.LEFT, padx=(0, 5))
        self.tablo_filtre_entry = ttk.Entry(row3, width=30)
        self.tablo_filtre_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.tablo_filtre_entry.bind('<KeyRelease>', self._tablo_filtrele)

        ttk.Button(row3, text="Temizle", command=self._filtreleri_temizle, width=10).pack(side=tk.LEFT)

    def _tablo_olustur(self, parent):
        """Tabloyu olustur - tksheet kullanarak"""
        tablo_frame = ttk.Frame(parent)
        tablo_frame.pack(fill=tk.BOTH, expand=True)

        # Sutun basliklari - yeni siralama
        self.column_headers = [
            "Tarih",        # 0 - Fatura tarihi
            "Fatura No",    # 1 - Fatura numarasi
            "Depo",         # 2 - Depo
            "Urun Adi",     # 3 - Urun adi
            "Ay.Ort",       # 4 - Aylik ortalama
            "Stok",         # 5 - Stok miktari (GRUP 1)
            "Stok Ay",      # 6 - Stok kac ay (GRUP 1)
            "Adet",         # 7 - Alinan adet (GRUP 2)
            "MF",           # 8 - Mal fazlasi (GRUP 2)
            "Alim Ay",      # 9 - Alim kac aylik (GRUP 2)
            "B.Fiyat",      # 10 - Birim fiyat
            "Toplam",       # 11 - Toplam tutar
            "Kalan",        # 12 - Ay sonuna siparis gereken
            "Uygun",        # 13 - Uygun mu
            "Toplam Ay",    # 14 - Stok+alim+mf kac ay (GRUP 2)
            "NPV-",         # 15 - NPV MFsiz
            "NPV+",         # 16 - NPV MFli
            "Avantaj",      # 17 - MF avantaj
            "G.Stok",       # 18 - Guncel stok
        ]

        # Sutun genislikleri - 1920px ekrana sigacak sekilde
        # Tarih, FaturaNo, Depo, UrunAdi, Ay.Ort, Stok, StokAy, Adet, MF, AlimAy, B.Fiyat, Toplam, Kalan, Uygun, ToplamAy, NPV-, NPV+, Avantaj, G.Stok
        self.column_widths = [90, 105, 145, 320, 75, 70, 75, 65, 55, 75, 95, 110, 70, 65, 85, 90, 90, 95, 75]

        # tksheet olustur
        self.sheet = Sheet(
            tablo_frame,
            headers=self.column_headers,
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            height=600,
            width=1880
        )
        self.sheet.pack(fill=tk.BOTH, expand=True)

        # Sutun genisliklerini ayarla
        for i, width in enumerate(self.column_widths):
            self.sheet.column_width(column=i, width=width)

        # Cift tiklama eventi
        self.sheet.extra_bindings([("cell_select", self._hucre_secildi)])
        self.sheet.extra_bindings([("double_click", self._cift_tiklama)])

        # Siralanabilir yap
        self.sheet.enable_bindings((
            "single_select",
            "column_select",
            "row_select",
            "column_width_resize",
            "arrowkeys",
            "copy",
            "rc_select",
        ))

        # Baslik tiklamasi ile siralama
        self.sheet.extra_bindings([("column_header_select", self._baslik_tiklandi)])

        # Siralama durumu
        self.sort_column = None
        self.sort_reverse = False

    def _status_bar_olustur(self, parent):
        """Status bar olustur"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(5, 0))

        self.status_label = ttk.Label(status_frame, text="Hazir")
        self.status_label.pack(side=tk.LEFT)

        self.toplam_label = ttk.Label(status_frame, text="")
        self.toplam_label.pack(side=tk.RIGHT)

    def _baglanti_kur(self):
        """Veritabani baglantisi kur"""
        try:
            from botanik_db import BotanikDB
            self.db = BotanikDB()
            if self.db.baglan():
                self.status_label.config(text="Veritabanina baglandi")
                self._depolari_yukle()
            else:
                self.status_label.config(text="Baglanti hatasi!")
        except Exception as e:
            logger.error(f"DB baglanti hatasi: {e}")
            self.status_label.config(text=f"Hata: {e}")

    def _depolari_yukle(self):
        """Depolari combo'ya yukle"""
        try:
            self.depolar = self.db.depo_listesi_getir()
            depo_listesi = ["Tumu"] + [d['DepoAdi'] for d in self.depolar]
            self.depo_combo['values'] = depo_listesi
        except Exception as e:
            logger.error(f"Depo yukleme hatasi: {e}")

    def _depo_id_bul(self, depo_adi):
        """Depo adina gore ID bul"""
        if depo_adi == "Tumu":
            return None
        for d in self.depolar:
            if d['DepoAdi'] == depo_adi:
                return d['DepoId']
        return None

    def sorgula(self):
        """Sorgu calistir"""
        self.status_label.config(text="Sorgulaniyor...")
        self.parent.update()

        # Parametreleri al
        baslangic = self.baslangic_tarih.get_date()
        bitis = self.bitis_tarih.get_date()
        depo_adi = self.depo_combo.get()
        depo_id = self._depo_id_bul(depo_adi)
        urun_adi = self.urun_adi_entry.get().strip() or None
        ortalama_ay = int(self.ortalama_ay_combo.get())

        limit_str = self.limit_combo.get()
        limit = 99999 if limit_str == "Tumu" else int(limit_str)

        # Thread ile sorgula
        def _sorgula():
            try:
                self.veriler = self.db.alis_analiz_getir(
                    baslangic_tarih=baslangic,
                    bitis_tarih=bitis,
                    ortalama_ay=ortalama_ay,
                    depo_id=depo_id,
                    urun_adi=urun_adi,
                    limit=limit
                )
                self.parent.after(0, self._veriyi_tabloya_yukle)
            except Exception as e:
                logger.error(f"Sorgu hatasi: {e}")
                self.parent.after(0, lambda: messagebox.showerror("Hata", str(e)))

        threading.Thread(target=_sorgula, daemon=True).start()

    def _renk_belirle(self, stok_gun: float, kalan_gun: int) -> str:
        """
        Stok durumuna gore renk belirle
        stok_gun: Stogun kac gun yetecegi
        kalan_gun: Ay sonuna kalan gun sayisi
        """
        if stok_gun <= kalan_gun:
            return RENK_BEYAZ   # Bu ay bitiyor
        elif stok_gun <= kalan_gun + 30:
            return RENK_SARI   # 1 aya sarkiyor
        elif stok_gun <= kalan_gun + 60:
            return RENK_TURUNCU  # 2 aya sarkiyor
        elif stok_gun <= kalan_gun + 90:
            return RENK_KIRMIZI  # 3 aya sarkiyor
        else:
            return RENK_MOR    # 4+ aya sarkiyor

    def _veriyi_tabloya_yukle(self):
        """Veriyi tabloya yukle"""
        # Tabloyu temizle
        self.sheet.set_sheet_data([])

        # Filtre parametrelerini al
        try:
            faiz_yillik = float(self.faiz_entry.get() or 45)
        except:
            faiz_yillik = 45
        try:
            depo_vade = int(self.depo_vade_entry.get() or 75)
        except:
            depo_vade = 75
        try:
            zam_orani = float(self.zam_orani_entry.get() or 0)
        except:
            zam_orani = 0
        zam_tarihi = self.zam_tarihi.get_date()

        toplam_tutar = 0
        toplam_adet = 0
        self.tablo_verileri = []

        # Renklendirme bilgileri icin listeler
        self.renk_bilgileri = []  # Her satir icin renk bilgisi

        for veri in self.veriler:
            # Degerleri al
            adet = veri.get('Adet', 0) or 0
            mf = veri.get('MF', 0) or 0
            birim_fiyat = float(veri.get('BirimFiyat', 0) or 0)
            maliyet = float(veri.get('Maliyet', 0) or 0)
            if maliyet <= 0:
                maliyet = birim_fiyat
            toplam = float(veri.get('ToplamTutar', 0) or 0)
            onceki_stok = veri.get('FaturaOncesiStok', 0) or 0
            aylik_ort = float(veri.get('AylikOrtalama', 0) or 0)
            kalan_gun = veri.get('KalanGun', 15) or 15
            guncel_stok = veri.get('GuncelStok', 0) or 0

            toplam_tutar += toplam
            toplam_adet += adet

            # Tarih formatlama
            tarih = veri.get('Tarih')
            if tarih:
                if isinstance(tarih, (datetime, date)):
                    tarih_str = tarih.strftime("%d.%m.%Y")
                else:
                    tarih_str = str(tarih)[:10]
            else:
                tarih_str = "-"

            # Kalan miktar hesapla (ay sonuna kadar siparis gereken)
            kalan_miktar = self._uygun_alim_hesapla(kalan_gun, aylik_ort, onceki_stok)

            # Toplam stok (onceki + alinan + MF)
            toplam_stok = onceki_stok + adet + mf

            # Gunluk sarf
            gunluk_sarf = aylik_ort / 30 if aylik_ort > 0 else 0

            # GRUP 1: Stok miktari ve stok ay icin gun hesabi
            onceki_stok_gun = onceki_stok / gunluk_sarf if gunluk_sarf > 0 else 0

            # GRUP 2: Toplam (stok + alim + mf) icin gun hesabi
            toplam_stok_gun = toplam_stok / gunluk_sarf if gunluk_sarf > 0 else 0

            # Stok ay hesapla (ay cinsinden)
            if aylik_ort > 0:
                stok_ay_deger = onceki_stok / aylik_ort
                alim_ay_deger = adet / aylik_ort
                toplam_ay_deger = toplam_stok / aylik_ort
            else:
                stok_ay_deger = 0
                alim_ay_deger = 0
                toplam_ay_deger = 0

            # Uygunluk kontrolu
            uygun_mu = "Evet" if (adet + mf) <= kalan_miktar * 1.2 else "Hayir"

            # Renkleri hesapla
            # GRUP 1: Sadece mevcut stok icin (sutun 4, 5)
            renk_grup1 = self._renk_belirle(onceki_stok_gun, kalan_gun)

            # GRUP 2: Toplam (stok + alim + mf) icin (sutun 6, 7, 10, 14)
            renk_grup2 = self._renk_belirle(toplam_stok_gun, kalan_gun)

            # NPV hesapla
            npv_mfsiz, npv_mfli, mf_avantaj = self._npv_hesapla(
                alinan=adet,
                mf=mf,
                maliyet=maliyet,
                aylik_ort=aylik_ort,
                faiz_yillik=faiz_yillik,
                depo_vade=depo_vade,
                fatura_tarihi=tarih if isinstance(tarih, date) else None,
                zam_tarihi=zam_tarihi,
                zam_orani=zam_orani,
                mevcut_stok=onceki_stok,
                kalan_gun=kalan_gun
            )

            # Satir verisi - yeni sutun sirasi
            satir = [
                tarih_str,                                          # 0. Tarih
                veri.get('FaturaNo', ''),                           # 1. Fatura No
                veri.get('Depo', '') or '-',                        # 2. Depo
                veri.get('UrunAdi', ''),                            # 3. Urun Adi
                f"{aylik_ort:.1f}",                                 # 4. Aylik Ortalama
                onceki_stok,                                        # 5. Stok (GRUP 1)
                f"{stok_ay_deger:.1f}" if stok_ay_deger > 0 else "-",  # 6. Stok Ay (GRUP 1)
                adet,                                               # 7. Adet (GRUP 2)
                mf if mf > 0 else "-",                              # 8. MF (GRUP 2)
                f"{alim_ay_deger:.1f}" if alim_ay_deger > 0 else "-",  # 9. Alim Ay (GRUP 2)
                f"{birim_fiyat:.2f}",                               # 10. Birim Fiyat
                f"{toplam:.2f}",                                    # 11. Toplam
                kalan_miktar,                                       # 12. Kalan
                uygun_mu,                                           # 13. Uygun
                f"{toplam_ay_deger:.1f}" if toplam_ay_deger > 0 else "-",  # 14. Toplam Ay (GRUP 2)
                f"{npv_mfsiz:.0f}" if npv_mfsiz > 0 else "-",       # 15. NPV-
                f"{npv_mfli:.0f}" if npv_mfli > 0 else "-",         # 16. NPV+
                f"{mf_avantaj:+.0f}" if mf_avantaj != 0 else "-",   # 17. Avantaj
                guncel_stok,                                        # 18. Guncel Stok
            ]

            self.tablo_verileri.append(satir)

            # Renk bilgisini kaydet
            self.renk_bilgileri.append({
                'grup1': renk_grup1,  # Sutun 4, 5 icin
                'grup2': renk_grup2,  # Sutun 6, 7, 10, 14 icin
            })

        # Veriyi tabloya yukle
        self.sheet.set_sheet_data(self.tablo_verileri)

        # Hucre bazli renklendirme uygula
        self._renklendirme_uygula()

        self.filtrelenmis_veriler = self.veriler.copy()
        self.status_label.config(text=f"{len(self.veriler)} kayit yuklendi")
        self.toplam_label.config(text=f"Toplam: {toplam_adet:,} adet | {toplam_tutar:,.2f} TL")

    def _renklendirme_uygula(self):
        """Hucre bazli renklendirme uygula"""
        # Grup 1 sutunlari: 5 (Stok), 6 (Stok Ay)
        # Grup 2 sutunlari: 7 (Adet), 8 (MF), 9 (Alim Ay), 14 (Toplam Ay)

        grup1_sutunlar = [5, 6]
        grup2_sutunlar = [7, 8, 9, 14]

        for row_idx, renk_info in enumerate(self.renk_bilgileri):
            # Grup 1 renklendirmesi
            renk_grup1 = renk_info['grup1']
            if renk_grup1 != RENK_BEYAZ:
                for col_idx in grup1_sutunlar:
                    self.sheet.highlight_cells(
                        row=row_idx,
                        column=col_idx,
                        bg=renk_grup1
                    )

            # Grup 2 renklendirmesi
            renk_grup2 = renk_info['grup2']
            if renk_grup2 != RENK_BEYAZ:
                for col_idx in grup2_sutunlar:
                    self.sheet.highlight_cells(
                        row=row_idx,
                        column=col_idx,
                        bg=renk_grup2
                    )

    def _baslik_tiklandi(self, event):
        """Baslik tiklandiginda siralama yap"""
        if event.column is None:
            return

        col = event.column
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        # Veriyi sirala
        self._siralama_yap(col)

    def _siralama_yap(self, col):
        """Sutuna gore siralama yap"""
        if not self.tablo_verileri:
            return

        # Renk bilgileri ile birlikte sirala
        combined = list(zip(self.tablo_verileri, self.renk_bilgileri))

        # Siralama fonksiyonu
        def sort_key(item):
            val = item[0][col]
            # Sayisal deger kontrolu
            if isinstance(val, (int, float)):
                return val
            try:
                # String ise sayi olarak cevir
                cleaned = str(val).replace(',', '.').replace('-', '0').replace('+', '')
                return float(cleaned)
            except:
                return str(val).lower()

        combined.sort(key=sort_key, reverse=self.sort_reverse)

        # Ayir
        self.tablo_verileri = [item[0] for item in combined]
        self.renk_bilgileri = [item[1] for item in combined]

        # Tabloyu guncelle
        self.sheet.set_sheet_data(self.tablo_verileri)

        # Renklendirmeyi tekrar uygula
        self._renklendirme_uygula()

    def _tablo_filtrele(self, event=None):
        """Tablo ici filtreleme"""
        filtre = self.tablo_filtre_entry.get().lower().strip()

        if not filtre:
            # Filtre bossa tum veriyi goster
            self.sheet.set_sheet_data(self.tablo_verileri)
            self._renklendirme_uygula()
            return

        # Filtreli veri
        filtreli_veriler = []
        filtreli_renkler = []

        for idx, satir in enumerate(self.tablo_verileri):
            # Satirdaki herhangi bir deger filtre ile eslesiyorsa
            if any(filtre in str(v).lower() for v in satir):
                filtreli_veriler.append(satir)
                filtreli_renkler.append(self.renk_bilgileri[idx])

        # Gecici olarak renk bilgilerini guncelle
        temp_renkler = self.renk_bilgileri
        self.renk_bilgileri = filtreli_renkler

        # Filtreli veriyi goster
        self.sheet.set_sheet_data(filtreli_veriler)
        self._renklendirme_uygula()

        # Renk bilgilerini geri al
        self.renk_bilgileri = temp_renkler

    def _filtreleri_temizle(self):
        """Filtreleri temizle"""
        self.tablo_filtre_entry.delete(0, tk.END)
        self.sheet.set_sheet_data(self.tablo_verileri)
        self._renklendirme_uygula()

    def _hucre_secildi(self, event):
        """Hucre secildiginde"""
        pass

    def _cift_tiklama(self, event):
        """Cift tiklama ile detay goster"""
        if event.row is None or event.row < 0:
            return

        row_idx = event.row
        if row_idx >= len(self.tablo_verileri):
            return

        vals = self.tablo_verileri[row_idx]
        self._detay_goster(vals)

    def _detay_goster(self, vals):
        """Detay popup goster"""
        # Sutunlar: Tarih(0), FaturaNo(1), Depo(2), UrunAdi(3), AylikOrt(4), Stok(5), StokAy(6),
        # Adet(7), MF(8), AlimAy(9), BirimFiyat(10), Toplam(11),
        # Kalan(12), Uygun(13), ToplamAy(14), NPV-(15), NPV+(16), Avantaj(17), GuncelStok(18)
        detay = f"""
====================================
        ALIS DETAYI
====================================

> Tarih: {vals[0]}
> Fatura No: {vals[1]}
> Depo: {vals[2]}

------------------------------------
URUN BILGILERI
------------------------------------
> Urun Adi: {vals[3]}
> Alinan Adet: {vals[7]}
> MF (Bedava): {vals[8]}

------------------------------------
STOK ANALIZI
------------------------------------
> Aylik Ortalama: {vals[4]} adet/ay
> Fatura Aninda Stok: {vals[5]} adet
> Stok Kac Aylik: {vals[6]} ay
> Alinan Miktar: {vals[7]} adet
> Alim Kac Aylik: {vals[9]} ay
> Kalan (Siparis Gereken): {vals[12]} adet
> Uygun mu: {vals[13]}
> Toplam Stok Kac Ay: {vals[14]} ay
> Guncel Stok: {vals[18]} adet

------------------------------------
FIYAT BILGILERI
------------------------------------
> Birim Fiyat: {vals[10]} TL
> Toplam Tutar: {vals[11]} TL

------------------------------------
MF AVANTAJ ANALIZI
------------------------------------
> NPV MF'siz: {vals[15]} TL
> NPV MF'li: {vals[16]} TL
> MF Avantaj: {vals[17]} TL
        """
        messagebox.showinfo("Alis Detayi", detay.strip())

    def excel_aktar(self):
        """Excel'e aktar"""
        if not self.tablo_verileri:
            messagebox.showwarning("Uyari", "Aktarilacak veri yok!")
            return

        dosya = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Dosyasi", "*.csv"), ("Tum Dosyalar", "*.*")],
            initialfilename=f"alis_analiz_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        )

        if not dosya:
            return

        try:
            ortalama_ay = int(self.ortalama_ay_combo.get())

            with open(dosya, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')

                # Basliklar
                headers = [
                    "Tarih", "Fatura No", "Depo", "Urun Adi",
                    f"Aylik Ort ({ortalama_ay} Ay)", "Stok", "Stok Ay",
                    "Adet", "MF", "Alim Ay", "Birim Fiyat", "Toplam",
                    "Kalan", "Uygun", "Toplam Ay", "NPV-", "NPV+", "Avantaj",
                    "Guncel Stok"
                ]
                writer.writerow(headers)

                # Veriler
                for satir in self.tablo_verileri:
                    writer.writerow(satir)

            messagebox.showinfo("Basarili", f"{len(self.tablo_verileri)} kayit aktarildi:\n{dosya}")

        except Exception as e:
            logger.error(f"Excel aktarim hatasi: {e}")
            messagebox.showerror("Hata", f"Aktarim hatasi:\n{e}")

    def status_guncelle(self, mesaj):
        self.status_label.config(text=mesaj)

    def _uygun_alim_hesapla(self, kalan_gun: int, aylik_ort: float, onceki_stok: int) -> int:
        """
        Bu ay icin maksimum uygun alim miktari
        Prensip: Alinan stok o ay icinde harcanmali
        """
        if aylik_ort <= 0:
            return 0
        gunluk_sarf = aylik_ort / 30
        bu_ay_ihtiyac = kalan_gun * gunluk_sarf
        eksik = max(0, bu_ay_ihtiyac - onceki_stok)
        return int(eksik)

    def _npv_hesapla(self, alinan: int, mf: int, maliyet: float, aylik_ort: float,
                    faiz_yillik: float, depo_vade: int,
                    fatura_tarihi: date, zam_tarihi: date, zam_orani: float,
                    mevcut_stok: int = 0, kalan_gun: int = 15) -> tuple:
        """
        NPV hesaplama - MF Analiz modulu mantigi ile

        Mevcut stogu dikkate alarak:
        - Once mevcut stoktan harca
        - Sonra yeni alimdan harca
        - Mevcut stok kaybi hesapla

        Returns:
            (npv_mfsiz, npv_mfli, avantaj)
        """
        if mf == 0 or mf is None:
            return (0, 0, 0)

        if maliyet <= 0 or aylik_ort <= 0:
            return (0, 0, 0)

        aylik_faiz = (faiz_yillik / 100) / 12
        depo_vade_ay = depo_vade / 30

        toplam_gelen = alinan + mf

        # Ilk ay sarfi (kalan gune gore)
        gunluk_sarf = aylik_ort / 30
        ilk_ay_sarf = kalan_gun * gunluk_sarf

        # Zam ayi hesapla
        zam_ay_sonra = 999
        if zam_tarihi and fatura_tarihi and zam_orani > 0:
            if isinstance(fatura_tarihi, date):
                zam_ay_sonra = (zam_tarihi.year - fatura_tarihi.year) * 12 + \
                               (zam_tarihi.month - fatura_tarihi.month)

        # ===== MEVCUT STOK KAYBI HESAPLA =====
        # Mevcut stogu zaten toplu aldin - ayri ayri alsaydin ne oderdin?
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

        # Mevcut stok toplu alinmis kabul (sunk cost)
        npv_mevcut_toplu = mevcut_stok * maliyet
        mevcut_stok_kaybi = npv_mevcut_toplu - npv_mevcut_ayri

        # ===== YENI ALIM NPV HESAPLAMASI =====
        # Senaryo A: MF'siz - mevcut stok bittikten sonra her ay ihtiyac kadar al
        npv_mfsiz = 0
        kalan_ihtiyac = toplam_gelen

        # Mevcut stok ve yeni alimi birlikte simule et
        kalan_mevcut_sim = mevcut_stok
        ay = 0

        while kalan_ihtiyac > 0 and ay < 120:
            if ay == 0:
                bu_ay_sarf = ilk_ay_sarf
            else:
                bu_ay_sarf = aylik_ort

            # Once mevcut stoktan harca
            mevcut_kullanim = min(kalan_mevcut_sim, bu_ay_sarf)
            kalan_mevcut_sim -= mevcut_kullanim

            # Kalan sarfi yeni alimdan karsila
            yeni_kullanim = min(bu_ay_sarf - mevcut_kullanim, kalan_ihtiyac)

            if yeni_kullanim > 0:
                # Zam sonrasi mi?
                if zam_orani > 0 and ay >= zam_ay_sonra:
                    fiyat = maliyet * (1 + zam_orani / 100)
                else:
                    fiyat = maliyet

                # Bu ayki odemenin bugunku degeri
                odeme = yeni_kullanim * fiyat
                iskonto_faktor = (1 + aylik_faiz) ** (ay + 1 + depo_vade_ay)
                npv_mfsiz += odeme / iskonto_faktor

                kalan_ihtiyac -= yeni_kullanim

            ay += 1

        # Senaryo B: Toplu odeme (MF'li) - sadece alinan kadar odenir
        odenen_para = alinan * maliyet
        npv_mfli = odenen_para / ((1 + aylik_faiz) ** (1 + depo_vade_ay))

        # Yeni alim kazanci/kaybi
        yeni_alim_kazanc = npv_mfsiz - npv_mfli

        # Net kazanc = Yeni alim kazanci - Mevcut stok kaybi
        net_kazanc = yeni_alim_kazanc - mevcut_stok_kaybi

        return (round(npv_mfsiz, 2), round(npv_mfli, 2), round(net_kazanc, 2))


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    pencere = tk.Toplevel(root)
    app = AlisAnalizGUI(pencere)
    root.mainloop()
