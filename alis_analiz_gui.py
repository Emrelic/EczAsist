"""
Alis Analiz Raporu GUI
Fatura bazli alis analizi - stok ve satis oranlamalari
tksheet ile hucre bazli renklendirme
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
import calendar
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

# Sutun grubu renk paleti - basliklara farkli pastel ton
HEADER_GRUP_1 = "#B3E5FC"   # Alim oncesi stok (mavi)
HEADER_GRUP_2 = "#FFF59D"   # Alim miktari (sari)
HEADER_GRUP_3 = "#FFCC80"   # Toplam durum (turuncu)
HEADER_GRUP_4 = "#A5D6A7"   # Guncel stok (yesil)


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
        self.urun_tipleri = []
        self.tur_vars = {}  # tip adi -> tk.BooleanVar
        self.tablo_verileri = []  # MASTER veri (yuklendikten sonra degismez)
        self.renk_bilgileri = []  # MASTER renk listesi (parallel)
        self.kolon_filtreleri = {}  # {col_idx: set_of_allowed_string_values}
        self._aktif_filtre_popup = None

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

        # Tur (multi-select dropdown) - DB baglandiktan sonra doldurulur
        ttk.Label(row1, text="Tur:").pack(side=tk.LEFT, padx=(0, 5))
        self.tur_button = ttk.Button(row1, text="Tumu  v", width=18,
                                      command=self._tur_dropdown_ac)
        self.tur_button.pack(side=tk.LEFT, padx=(0, 10))
        self._tur_popup = None

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
            "Tip",          # 4 - Urun tipi (Ilac/Medikal/Itriyat...)
            "Ay.Ort",       # 5 - Aylik ortalama (fatura tarihindeki)
            "Stok",         # 6 - Stok miktari (GRUP 1)
            "Stok Ay",      # 7 - Stok kac ay (GRUP 1)
            "Adet",         # 8 - Alinan adet (GRUP 2)
            "MF",           # 9 - Mal fazlasi (GRUP 2)
            "Alim Ay",      # 10 - Alim kac aylik (GRUP 2)
            "B.Fiyat",      # 11 - Birim fiyat
            "Toplam",       # 12 - Toplam tutar
            "Kalan",        # 13 - Ay sonuna siparis gereken
            "Uygun",        # 14 - Uygun mu
            "Toplam Ay",    # 15 - Stok+alim+mf kac ay (GRUP 2)
            "NPV-",         # 16 - NPV MFsiz
            "NPV+",         # 17 - NPV MFli
            "Avantaj",      # 18 - MF avantaj
            "G.Stok",       # 19 - Guncel stok (GRUP 3)
            "G.Ay.Ort",     # 20 - Guncel aylik ortalama (GRUP 3)
            "Bitis",        # 21 - Guncel stok kac ay yetecek (GRUP 3)
        ]

        # Sutun genislikleri (otomatik daraltma sonrasi tek ekrana sigar)
        self.column_widths = [78, 95, 125, 270, 70, 65, 60, 60, 55, 50, 60, 78, 95, 58, 58, 70, 75, 75, 78, 65, 70, 65]

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

        # Sol tik baslik: siralama toggle / Sag tik baslik: detayli filtre popup
        self.sheet.extra_bindings([("column_select", self._baslik_tiklandi)])
        try:
            self.sheet.CH.bind("<Button-3>", self._baslik_sag_tiklandi)
        except Exception as e:
            logger.error(f"Header sag tik bind hatasi: {e}")

        # Siralama durumu
        self.sort_column = None
        self.sort_reverse = False

        # Sutun gruplari icin baslik renklendirmesi
        self._baslik_gruplarini_renklendir()

    def _kolonlari_otomatik_sigdir(self):
        """Sutunlari icerige gore daralt; toplam viewport'u asarsa orantili kucult."""
        try:
            self.sheet.update_idletasks()
            viewport = self.sheet.winfo_width()
            if viewport < 100:
                # Sheet henuz cizilmemis, biraz sonra tekrar dene
                self.parent.after(100, self._kolonlari_otomatik_sigdir)
                return
            # Y scrollbar payi
            viewport -= 25

            # 1) Icerige gore auto-fit
            self.sheet.set_all_column_widths(width=None)

            # 1a) Belirli sutunlara max cap (uzun metinlerin tabloyu sismesini onler)
            kolon_max = {
                2: 130,   # Depo
                3: 210,   # Urun Adi
                4: 95,    # Tip
            }
            for col_idx, mx in kolon_max.items():
                try:
                    if self.sheet.column_width(column=col_idx) > mx:
                        self.sheet.column_width(column=col_idx, width=mx)
                except Exception:
                    pass

            # 2) Toplam vs viewport
            n = len(self.column_headers)
            widths = [self.sheet.column_width(column=i) for i in range(n)]
            toplam = sum(widths)

            # 3) Asiyorsa min genislik koruyarak orantili kucult
            if toplam > viewport:
                min_genislik = 35
                sabit_yer = min_genislik * n
                esnek_viewport = max(0, viewport - sabit_yer)
                esnek_toplam = max(1, toplam - sabit_yer)
                for i, w in enumerate(widths):
                    w_esnek = max(0, w - min_genislik)
                    yeni = min_genislik + int(w_esnek * esnek_viewport / esnek_toplam)
                    self.sheet.column_width(column=i, width=yeni)

            # Header grup renklerini tekrar uygula (auto-fit hilight'i etkileyebilir)
            self._baslik_gruplarini_renklendir()
        except Exception as e:
            logger.error(f"Otomatik sutun sigdirma hatasi: {e}")

    def _baslik_gruplarini_renklendir(self):
        """4 mantiksal grubun basliklarini farkli pastel tonlarla isaretle"""
        try:
            # Grup 1 - Alim oncesi stok: Stok(6), Stok Ay(7)
            self.sheet.span(slice(6, 8), header=True, table=False).highlight(bg=HEADER_GRUP_1)
            # Grup 2 - Alim miktari: Adet(8), MF(9), Alim Ay(10)
            self.sheet.span(slice(8, 11), header=True, table=False).highlight(bg=HEADER_GRUP_2)
            # Grup 3 - Toplam durum: Kalan(13), Uygun(14), Toplam Ay(15)
            self.sheet.span(slice(13, 16), header=True, table=False).highlight(bg=HEADER_GRUP_3)
            # Grup 4 - Guncel stok: G.Stok(19), G.Ay.Ort(20), Bitis(21)
            self.sheet.span(slice(19, 22), header=True, table=False).highlight(bg=HEADER_GRUP_4)
        except Exception as e:
            logger.error(f"Baslik grup renklendirme hatasi: {e}")

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

        # Urun tiplerini yukle (popup acildiginda checkbox olusturulacak)
        try:
            self.urun_tipleri = self.db.urun_tipleri_getir()
            self.tur_vars = {}
            for tip in self.urun_tipleri:
                tip_adi = tip['UrunTipAdi']
                self.tur_vars[tip_adi] = tk.BooleanVar(value=True)  # varsayilan hepsi
            self._tur_label_guncelle()
        except Exception as e:
            logger.error(f"Urun tipi yukleme hatasi: {e}")

    def _tur_label_guncelle(self):
        """Tur button label'ini secime gore guncelle"""
        if not self.tur_vars:
            self.tur_button.config(text="Tumu  v")
            return
        secili = [t for t, v in self.tur_vars.items() if v.get()]
        toplam = len(self.tur_vars)
        if len(secili) == 0:
            text = "Hicbiri  v"
        elif len(secili) == toplam:
            text = "Tumu  v"
        elif len(secili) == 1:
            text = f"{secili[0]}  v"
        elif len(secili) == 2:
            text = f"{secili[0]}, {secili[1]}  v"
        else:
            text = f"{len(secili)} tur  v"
        self.tur_button.config(text=text)

    def _tur_dropdown_ac(self):
        """Tur secimi popup'unu ac"""
        # Zaten acik ise kapat
        if self._tur_popup is not None and self._tur_popup.winfo_exists():
            self._tur_popup.destroy()
            self._tur_popup = None
            return

        if not self.tur_vars:
            return

        popup = tk.Toplevel(self.parent)
        popup.title("Tur Sec")
        popup.transient(self.parent)
        popup.resizable(False, False)
        self._tur_popup = popup

        # Konum: butonun hemen altinda
        try:
            x = self.tur_button.winfo_rootx()
            y = self.tur_button.winfo_rooty() + self.tur_button.winfo_height()
            popup.geometry(f"+{x}+{y}")
        except Exception:
            pass

        # Hizli secim butonlari
        ust = ttk.Frame(popup, padding=(8, 6, 8, 4))
        ust.pack(fill=tk.X)
        ttk.Button(ust, text="Tumunu Sec", width=12,
                   command=lambda: self._tur_hepsi_sec(True)).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(ust, text="Hicbiri", width=10,
                   command=lambda: self._tur_hepsi_sec(False)).pack(side=tk.LEFT)

        ttk.Separator(popup, orient="horizontal").pack(fill=tk.X, padx=4)

        # Checkbox listesi
        liste = ttk.Frame(popup, padding=(8, 4, 8, 4))
        liste.pack(fill=tk.BOTH, expand=True)
        for tip_adi, var in self.tur_vars.items():
            ttk.Checkbutton(liste, text=tip_adi, variable=var,
                            command=self._tur_label_guncelle).pack(anchor="w", pady=1)

        ttk.Separator(popup, orient="horizontal").pack(fill=tk.X, padx=4)

        # Kapat butonu
        alt = ttk.Frame(popup, padding=(8, 4, 8, 8))
        alt.pack(fill=tk.X)
        ttk.Button(alt, text="Kapat", command=popup.destroy).pack(side=tk.RIGHT)

        # Popup disinda tiklayinca kapansin
        popup.bind("<FocusOut>", lambda e: self._tur_popup_kapat_kontrol())
        popup.focus_set()

    def _tur_popup_kapat_kontrol(self):
        """Popup focus kaybedince kapatma kontrolu (alt pencerelere takilmasin)"""
        # Kapatmadan once kisa bekleme - alt widget'lara odak gecisi olabilir
        if self._tur_popup is None:
            return
        try:
            focus = self._tur_popup.focus_displayof()
            if focus is None or not str(focus).startswith(str(self._tur_popup)):
                self._tur_popup.destroy()
                self._tur_popup = None
        except Exception:
            pass

    def _tur_hepsi_sec(self, deger: bool):
        """Tum tipleri sec/temizle"""
        for var in self.tur_vars.values():
            var.set(deger)
        self._tur_label_guncelle()

    def _secili_turleri_al(self):
        """Secili turleri liste olarak dondur. Hepsi secili veya hicbiri secili = None (filtre yok)"""
        if not self.tur_vars:
            return None
        secili = [t for t, v in self.tur_vars.items() if v.get()]
        if not secili or len(secili) == len(self.tur_vars):
            return None
        return secili

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

        urun_tipleri = self._secili_turleri_al()

        # Thread ile sorgula
        def _sorgula():
            try:
                self.veriler = self.db.alis_analiz_getir(
                    baslangic_tarih=baslangic,
                    bitis_tarih=bitis,
                    ortalama_ay=ortalama_ay,
                    depo_id=depo_id,
                    urun_adi=urun_adi,
                    urun_tipleri=urun_tipleri,
                    limit=limit
                )
                # Bos sonuc + DB hatasi varsa kullaniciya goster (sessiz hata tanilama)
                son_hata = getattr(self.db, 'son_sorgu_hatasi', None)
                if not self.veriler and son_hata:
                    self.parent.after(0, lambda: messagebox.showerror(
                        "SQL Hatasi", f"Sorgu hatali calisti:\n\n{son_hata}"))
                    self.parent.after(0, lambda: self.status_label.config(
                        text=f"SQL Hatasi: {son_hata[:80]}"))
                    return
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

        # G.Stok grubu icin: bugunden bu ay sonuna kalan gun
        bugun = date.today()
        ay_son_gun = calendar.monthrange(bugun.year, bugun.month)[1]
        guncel_kalan_gun = ay_son_gun - bugun.day

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
            guncel_aylik_ort = float(veri.get('GuncelAylikOrtalama', 0) or 0)
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
            # GRUP 1: Sadece mevcut stok icin (sutun 5, 6)
            renk_grup1 = self._renk_belirle(onceki_stok_gun, kalan_gun)

            # GRUP 2: Toplam (stok + alim + mf) icin (sutun 7, 8, 9, 14)
            renk_grup2 = self._renk_belirle(toplam_stok_gun, kalan_gun)

            # GRUP 3: Guncel stok icin (sutun 18, 19, 20) - bugunden bu ay sonuna referans
            guncel_gunluk_sarf = guncel_aylik_ort / 30 if guncel_aylik_ort > 0 else 0
            guncel_stok_gun = guncel_stok / guncel_gunluk_sarf if guncel_gunluk_sarf > 0 else 0
            guncel_bitis_ay = guncel_stok / guncel_aylik_ort if guncel_aylik_ort > 0 else 0
            renk_grup3 = self._renk_belirle(guncel_stok_gun, guncel_kalan_gun)

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
                veri.get('UrunTipi', '') or 'Belirsiz',             # 4. Tip
                f"{aylik_ort:.1f}",                                 # 5. Aylik Ortalama
                onceki_stok,                                        # 6. Stok (GRUP 1)
                f"{stok_ay_deger:.1f}" if stok_ay_deger > 0 else "-",  # 7. Stok Ay (GRUP 1)
                adet,                                               # 8. Adet (GRUP 2)
                mf if mf > 0 else "-",                              # 9. MF (GRUP 2)
                f"{alim_ay_deger:.1f}" if alim_ay_deger > 0 else "-",  # 10. Alim Ay (GRUP 2)
                f"{birim_fiyat:.2f}",                               # 11. Birim Fiyat
                f"{toplam:.2f}",                                    # 12. Toplam
                kalan_miktar,                                       # 13. Kalan
                uygun_mu,                                           # 14. Uygun
                f"{toplam_ay_deger:.1f}" if toplam_ay_deger > 0 else "-",  # 15. Toplam Ay (GRUP 2)
                f"{npv_mfsiz:.0f}" if npv_mfsiz > 0 else "-",       # 16. NPV-
                f"{npv_mfli:.0f}" if npv_mfli > 0 else "-",         # 17. NPV+
                f"{mf_avantaj:+.0f}" if mf_avantaj != 0 else "-",   # 18. Avantaj
                guncel_stok,                                        # 19. Guncel Stok
                f"{guncel_aylik_ort:.1f}",                          # 20. Guncel Aylik Ortalama
                f"{guncel_bitis_ay:.1f}" if guncel_bitis_ay > 0 else "-",  # 21. Bitis (kac ay)
            ]

            self.tablo_verileri.append(satir)

            # Renk bilgisini kaydet
            self.renk_bilgileri.append({
                'grup1': renk_grup1,  # Sutun 6, 7 icin
                'grup2': renk_grup2,  # Sutun 8, 9, 10, 15 icin
                'grup3': renk_grup3,  # Sutun 19, 20, 21 icin
            })

        # Yeni veri geldi → onceki filtre/siralamayi sifirla
        self.kolon_filtreleri.clear()
        self.sort_column = None
        self.sort_reverse = False

        # Master veriyi sheet'e ilk basim
        self.sheet.set_sheet_data(self.tablo_verileri)

        # Hucre bazli renklendirme uygula (master)
        self._renklendirme_uygula()

        # Sutunlari icerige gore daralt + viewport'a sigdir
        self._kolonlari_otomatik_sigdir()

        # Baslik isaretlerini guncelle (filtre yok, isaretsiz olacak)
        self._baslik_filtre_isaretleri_guncelle()

        self.filtrelenmis_veriler = self.veriler.copy()
        self.status_label.config(text=f"{len(self.veriler)} kayit yuklendi")
        self.toplam_label.config(text=f"Toplam: {toplam_adet:,} adet | {toplam_tutar:,.2f} TL")

    def _renklendirme_uygula(self, renkler=None):
        """Hucre bazli renklendirme uygula. renkler=None ise master listesini kullanir."""
        if renkler is None:
            renkler = self.renk_bilgileri
        grup1_sutunlar = [6, 7]
        grup2_sutunlar = [8, 9, 10, 15]
        grup3_sutunlar = [19, 20, 21]

        for row_idx, renk_info in enumerate(renkler):
            renk_grup1 = renk_info.get('grup1', RENK_BEYAZ)
            if renk_grup1 != RENK_BEYAZ:
                for col_idx in grup1_sutunlar:
                    self.sheet.highlight_cells(row=row_idx, column=col_idx, bg=renk_grup1)
            renk_grup2 = renk_info.get('grup2', RENK_BEYAZ)
            if renk_grup2 != RENK_BEYAZ:
                for col_idx in grup2_sutunlar:
                    self.sheet.highlight_cells(row=row_idx, column=col_idx, bg=renk_grup2)
            renk_grup3 = renk_info.get('grup3', RENK_BEYAZ)
            if renk_grup3 != RENK_BEYAZ:
                for col_idx in grup3_sutunlar:
                    self.sheet.highlight_cells(row=row_idx, column=col_idx, bg=renk_grup3)

    def _baslik_tiklandi(self, event):
        """Baslik sol tikla → siralama toggle (artan/azalan/iptal)"""
        col = None
        try:
            col = event.column if event.column is not None else None
        except Exception:
            pass
        if col is None:
            try:
                col = event['selected'].column
            except Exception:
                pass
        if col is None:
            try:
                secili = self.sheet.get_selected_columns()
                if secili:
                    col = next(iter(secili))
            except Exception:
                pass
        if col is None:
            return
        # 3-asamali toggle: yok → artan → azalan → yok
        if self.sort_column != col:
            self.sort_column = col
            self.sort_reverse = False
        elif not self.sort_reverse:
            self.sort_reverse = True
        else:
            self.sort_column = None
            self.sort_reverse = False
        self._tablo_yenile()

    def _baslik_sag_tiklandi(self, event):
        """Baslik sag tikla → detayli filtre popup'i"""
        try:
            col = self.sheet.identify_column(event)
        except Exception:
            col = None
        if col is None or col < 0:
            return
        self._filtre_popup_ac(col)

    # Sutun tip haritasi - dogru siralama key'i secmek icin
    DATE_COLS = {0}                  # Tarih
    TEXT_COLS = {1, 2, 3, 4, 14}     # Fatura No, Depo, Urun Adi, Tip, Uygun

    def _sort_key(self, col, val):
        """Bir hucre degerini siralama icin ayiklanmis anahtara cevir"""
        # Tarih
        if col in self.DATE_COLS:
            try:
                parts = str(val).split('.')
                return datetime(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception:
                return datetime.min
        # Metin
        if col in self.TEXT_COLS:
            return str(val).lower()
        # Sayisal
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        if s in ('', '-'):
            return 0.0
        try:
            s = s.lstrip('+').replace(' ', '').replace(',', '.')
            if s.count('.') > 1:
                parts = s.rsplit('.', 1)
                s = parts[0].replace('.', '') + '.' + parts[1]
            return float(s)
        except Exception:
            return 0.0

    # Operator paletleri
    OPERATORLER_METIN = [
        ("icerir", "Icerir"),
        ("icermez", "Icermez"),
        ("baslar", "Ile baslar"),
        ("biter", "Ile biter"),
        ("esit", "Esit"),
        ("esit_degil", "Esit degil"),
    ]
    OPERATORLER_SAYI = [
        ("=", "= (Esit)"),
        ("!=", "!= (Esit degil)"),
        (">", "> (Buyuk)"),
        (">=", ">= (Buyuk esit)"),
        ("<", "< (Kucuk)"),
        ("<=", "<= (Kucuk esit)"),
        ("arasinda", "Arasinda (min - max)"),
    ]

    def _kolon_operatorleri(self, col):
        """Kolon tipine gore operator listesini don"""
        if col in self.TEXT_COLS:
            return self.OPERATORLER_METIN
        # Sayi VE tarih icin ayni op set; tarih _sort_key ile datetime'a parse edilir
        return self.OPERATORLER_SAYI

    def _kosul_uygun_mu(self, col, val_str, op, dgr):
        """Bir hucrenin tek kosulu gecip gecmedigini test et"""
        try:
            if op == 'icerir':
                return str(dgr).lower() in val_str.lower()
            if op == 'icermez':
                return str(dgr).lower() not in val_str.lower()
            if op == 'baslar':
                return val_str.lower().startswith(str(dgr).lower())
            if op == 'biter':
                return val_str.lower().endswith(str(dgr).lower())
            if op == 'esit':
                return val_str.strip().lower() == str(dgr).strip().lower()
            if op == 'esit_degil':
                return val_str.strip().lower() != str(dgr).strip().lower()
            # Sayi/tarih ops - _sort_key tip-aware donusum yapar
            if op == 'arasinda':
                v = self._sort_key(col, val_str)
                d1 = self._sort_key(col, dgr[0])
                d2 = self._sort_key(col, dgr[1])
                lo, hi = (d1, d2) if d1 <= d2 else (d2, d1)
                return lo <= v <= hi
            if op in ('=', '!=', '>', '>=', '<', '<='):
                v = self._sort_key(col, val_str)
                d = self._sort_key(col, dgr)
                if op == '=':  return v == d
                if op == '!=': return v != d
                if op == '>':  return v > d
                if op == '>=': return v >= d
                if op == '<':  return v < d
                if op == '<=': return v <= d
        except Exception:
            return True  # Karsilastirma basarisiz → satiri hidden yapma
        return True

    def _kolon_satir_uygun_mu(self, col, val):
        """Bu kolonun tum filtre kurallarini gec mi?"""
        f = self.kolon_filtreleri.get(col)
        if not f:
            return True
        val_str = str(val)
        # Liste filtresi
        izin = f.get('liste')
        if izin is not None and val_str not in izin:
            return False
        # Kosul filtreleri (AND)
        for k in f.get('kosullar', []):
            if not self._kosul_uygun_mu(col, val_str, k['op'], k['deger']):
                return False
        return True

    def _filtre_indeksleri_hesapla(self):
        """Master'a kolon filtresi + serbest metin filtresi uygulayarak indeksleri don"""
        try:
            metin = self.tablo_filtre_entry.get().lower().strip()
        except Exception:
            metin = ""
        indeksler = []
        for idx, satir in enumerate(self.tablo_verileri):
            gec = True
            for col in self.kolon_filtreleri:
                if not self._kolon_satir_uygun_mu(col, satir[col]):
                    gec = False
                    break
            if gec and metin:
                if not any(metin in str(v).lower() for v in satir):
                    gec = False
            if gec:
                indeksler.append(idx)
        return indeksler

    def _set_sheet_data_korunarak(self, data):
        """set_sheet_data + sutun genislikleri ve grup baslik renklerini koruma"""
        n = len(self.column_headers)
        try:
            widths = [self.sheet.column_width(column=i) for i in range(n)]
        except Exception:
            widths = None
        self.sheet.set_sheet_data(data)
        if widths:
            for i, w in enumerate(widths):
                try:
                    self.sheet.column_width(column=i, width=w)
                except Exception:
                    pass
        self._baslik_gruplarini_renklendir()

    def _baslik_filtre_isaretleri_guncelle(self):
        """Aktif siralama/filtre olan basliklara isaret koy"""
        yeni = list(self.column_headers)
        for col in self.kolon_filtreleri:
            yeni[col] = yeni[col] + " *"
        if self.sort_column is not None and 0 <= self.sort_column < len(yeni):
            ok = " v" if self.sort_reverse else " ^"
            yeni[self.sort_column] = yeni[self.sort_column] + ok
        try:
            self.sheet.headers(yeni, redraw=True)
            self._baslik_gruplarini_renklendir()
        except Exception as e:
            logger.error(f"Baslik isaret guncelleme hatasi: {e}")

    def _tablo_yenile(self):
        """Master + filtre + siralama -> sheet'e basar (tek render path)"""
        if not self.tablo_verileri:
            return
        # 1) Filtrelenmis indeksler
        indeksler = self._filtre_indeksleri_hesapla()
        # 2) Sirala
        if self.sort_column is not None and 0 <= self.sort_column < len(self.column_headers):
            col = self.sort_column
            indeksler.sort(
                key=lambda i: self._sort_key(col, self.tablo_verileri[i][col]),
                reverse=self.sort_reverse
            )
        # 3) Goster
        gorunen = [self.tablo_verileri[i] for i in indeksler]
        gorunen_renkler = [self.renk_bilgileri[i] for i in indeksler]
        self._set_sheet_data_korunarak(gorunen)
        self._renklendirme_uygula(gorunen_renkler)
        self._baslik_filtre_isaretleri_guncelle()
        # Status
        try:
            self.status_label.config(
                text=f"{len(gorunen)} / {len(self.tablo_verileri)} kayit gosteriliyor"
            )
        except Exception:
            pass

    def _filtre_popup_ac(self, col):
        """Detayli filtre popup'i: kosul (operator+deger) + benzersiz deger listesi"""
        if self._aktif_filtre_popup is not None:
            try:
                if self._aktif_filtre_popup.winfo_exists():
                    self._aktif_filtre_popup.destroy()
            except Exception:
                pass
            self._aktif_filtre_popup = None

        if not self.tablo_verileri:
            return

        popup = tk.Toplevel(self.parent)
        popup.title(f"Filtre: {self.column_headers[col].strip(' *^v')}")
        popup.transient(self.parent)
        popup.resizable(False, True)
        self._aktif_filtre_popup = popup

        try:
            x = self.parent.winfo_pointerx() - 30
            y = self.parent.winfo_pointery() + 10
            popup.geometry(f"340x520+{x}+{y}")
        except Exception:
            popup.geometry("340x520")

        # Mevcut filtre durumu (kopya - iptal'de master degismez)
        mevcut = self.kolon_filtreleri.get(col, {})
        kosullar = list(mevcut.get('kosullar', []))  # mutable copy

        # ----- KOSUL FILTRESI -----
        kosul_frame = ttk.LabelFrame(popup, text="Kosul Filtresi", padding=4)
        kosul_frame.pack(fill=tk.X, padx=4, pady=(4, 2))

        op_secenekleri = self._kolon_operatorleri(col)
        op_etiket_kod = {etiket: kod for kod, etiket in op_secenekleri}
        op_var = tk.StringVar(value=op_secenekleri[0][1])

        op_row = ttk.Frame(kosul_frame)
        op_row.pack(fill=tk.X)
        op_combo = ttk.Combobox(op_row, textvariable=op_var, state="readonly", width=18,
                                 values=[etiket for _, etiket in op_secenekleri])
        op_combo.pack(side=tk.LEFT, padx=(0, 4))

        deger_row = ttk.Frame(kosul_frame)
        deger_row.pack(fill=tk.X, pady=(2, 2))
        deger1_entry = ttk.Entry(deger_row, width=14)
        deger1_entry.pack(side=tk.LEFT, padx=(0, 4))
        ile_lbl = ttk.Label(deger_row, text=" - ")
        deger2_entry = ttk.Entry(deger_row, width=14)

        def _op_degisti(*_):
            kod = op_etiket_kod.get(op_var.get())
            if kod == 'arasinda':
                ile_lbl.pack(side=tk.LEFT)
                deger2_entry.pack(side=tk.LEFT, padx=(0, 4))
            else:
                ile_lbl.pack_forget()
                deger2_entry.pack_forget()
        op_var.trace("w", _op_degisti)

        # Aktif kosullar listesi (Listbox)
        aktif_row = ttk.Frame(kosul_frame)
        aktif_row.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(aktif_row, text="Aktif kosullar (AND):").pack(anchor="w")
        kosul_listbox = tk.Listbox(aktif_row, height=4)
        kosul_listbox.pack(fill=tk.X, pady=(2, 0))

        def _kosullari_listele():
            kosul_listbox.delete(0, tk.END)
            for k in kosullar:
                etiket = next((e for kd, e in op_secenekleri if kd == k['op']), k['op'])
                d = k['deger']
                if isinstance(d, (list, tuple)):
                    metin = f"{etiket}: {d[0]} - {d[1]}"
                else:
                    metin = f"{etiket}: {d}"
                kosul_listbox.insert(tk.END, metin)
        _kosullari_listele()

        def _kosul_ekle():
            kod = op_etiket_kod.get(op_var.get())
            if not kod:
                return
            if kod == 'arasinda':
                d1 = deger1_entry.get().strip()
                d2 = deger2_entry.get().strip()
                if not d1 or not d2:
                    return
                kosullar.append({'op': kod, 'deger': (d1, d2)})
            else:
                d = deger1_entry.get().strip()
                if not d:
                    return
                kosullar.append({'op': kod, 'deger': d})
            deger1_entry.delete(0, tk.END)
            deger2_entry.delete(0, tk.END)
            _kosullari_listele()

        def _kosul_sil():
            sec = kosul_listbox.curselection()
            if not sec:
                return
            del kosullar[sec[0]]
            _kosullari_listele()

        btn_row = ttk.Frame(kosul_frame)
        btn_row.pack(fill=tk.X, pady=(2, 0))
        ttk.Button(btn_row, text="+ Ekle", width=10, command=_kosul_ekle).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="- Sil", width=10, command=_kosul_sil).pack(side=tk.LEFT, padx=(4, 0))

        # Enter ile koşul ekle
        deger1_entry.bind("<Return>", lambda e: _kosul_ekle())
        deger2_entry.bind("<Return>", lambda e: _kosul_ekle())

        # ----- DEGER LISTESI -----
        liste_frame = ttk.LabelFrame(popup, text="Veya degerleri sec", padding=4)
        liste_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        arama_row = ttk.Frame(liste_frame)
        arama_row.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(arama_row, text="Ara:").pack(side=tk.LEFT)
        arama_entry = ttk.Entry(arama_row)
        arama_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        list_holder = ttk.Frame(liste_frame)
        list_holder.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(list_holder, highlightthickness=0)
        sb = ttk.Scrollbar(list_holder, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Benzersiz degerler (diger kolon filtrelerinden gecirilmis)
        diger_kolonlar = [c for c in self.kolon_filtreleri if c != col]
        gorulmus = set()
        benzersiz = []
        for satir in self.tablo_verileri:
            gec = True
            for c in diger_kolonlar:
                if not self._kolon_satir_uygun_mu(c, satir[c]):
                    gec = False
                    break
            if not gec:
                continue
            v = str(satir[col])
            if v not in gorulmus:
                gorulmus.add(v)
                benzersiz.append(v)
        try:
            benzersiz.sort(key=lambda v: self._sort_key(col, v))
        except Exception:
            benzersiz.sort()

        aktif_liste = mevcut.get('liste')
        if aktif_liste is None:
            aktif_liste = set(benzersiz)

        deger_vars = {}
        tumu_var = tk.BooleanVar(value=len(aktif_liste) >= len(benzersiz))

        def tumu_toggle():
            v = tumu_var.get()
            for var in deger_vars.values():
                var.set(v)

        ttk.Checkbutton(inner, text="(Tumunu Sec)", variable=tumu_var,
                        command=tumu_toggle).pack(anchor="w", padx=2)
        ttk.Separator(inner, orient="horizontal").pack(fill=tk.X, padx=2, pady=1)

        cb_widgets = []
        for val in benzersiz:
            v = tk.BooleanVar(value=val in aktif_liste)
            deger_vars[val] = v
            text = val if val and val.strip() else "(Bos)"
            cb = ttk.Checkbutton(inner, text=text, variable=v)
            cb.pack(anchor="w", padx=2)
            cb_widgets.append((val, cb))

        inner.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_wheel(e):
            try:
                canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
            except Exception:
                pass
        canvas.bind("<MouseWheel>", _on_wheel)
        inner.bind("<MouseWheel>", _on_wheel)
        for _, cb in cb_widgets:
            cb.bind("<MouseWheel>", _on_wheel)

        def _arama_filtrele(*_):
            q = arama_entry.get().lower()
            for val, cb in cb_widgets:
                if q in val.lower():
                    cb.pack(anchor="w", padx=2)
                else:
                    cb.pack_forget()
            inner.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
        arama_entry.bind("<KeyRelease>", _arama_filtrele)

        # ----- BUTONLAR -----
        btn = ttk.Frame(popup, padding=4)
        btn.pack(fill=tk.X)
        ttk.Button(btn, text="Filtreyi Temizle", width=16,
                   command=lambda: self._kolon_filtre_kaldir(col, popup)).pack(side=tk.LEFT)
        ttk.Button(btn, text="Iptal", width=8, command=popup.destroy).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(btn, text="Uygula", width=8,
                   command=lambda: self._kolon_filtre_uygula(
                       col, kosullar, deger_vars, set(benzersiz), popup
                   )).pack(side=tk.RIGHT)

        popup.focus_set()
        deger1_entry.focus_set()

    def _kolon_filtre_uygula(self, col, kosullar, deger_vars, tum_degerler, popup):
        """Popup'tan kosullar + liste filtresini uygula"""
        secili = {v for v, var in deger_vars.items() if var.get()}
        # Liste: tumu seciliyse None (filtre yok), degilse set
        if len(secili) >= len(tum_degerler):
            liste = None
        elif len(secili) == 0:
            # Hicbiri secili = "hicbir satir gec" demek; ama mantikli olmasi icin None say
            liste = None
        else:
            liste = secili

        # Hic kosul yok ve liste tam ise filtreyi kaldir
        if not kosullar and liste is None:
            self.kolon_filtreleri.pop(col, None)
        else:
            self.kolon_filtreleri[col] = {'kosullar': kosullar, 'liste': liste}

        try:
            popup.destroy()
        except Exception:
            pass
        self._tablo_yenile()

    def _kolon_filtre_kaldir(self, col, popup=None):
        """Bu kolonun filtresini ve siralamasini kaldir"""
        self.kolon_filtreleri.pop(col, None)
        if self.sort_column == col:
            self.sort_column = None
            self.sort_reverse = False
        if popup:
            try:
                popup.destroy()
            except Exception:
                pass
        self._tablo_yenile()

    def _tablo_filtrele(self, event=None):
        """Serbest metin filtresi degisti -> tabloyu yenile"""
        self._tablo_yenile()

    def _filtreleri_temizle(self):
        """Tum filtreleri ve siralamayi temizle"""
        try:
            self.tablo_filtre_entry.delete(0, tk.END)
        except Exception:
            pass
        self.kolon_filtreleri.clear()
        self.sort_column = None
        self.sort_reverse = False
        self._tablo_yenile()

    def _hucre_secildi(self, event):
        """Hucre secildiginde"""
        pass

    def _cift_tiklama(self, event):
        """Cift tiklama ile detay goster (gorunen satirdan oku)"""
        if event.row is None or event.row < 0:
            return
        try:
            vals = self.sheet.get_row_data(event.row)
        except Exception:
            return
        if not vals:
            return
        self._detay_goster(vals)

    def _detay_goster(self, vals):
        """Detay popup goster"""
        # Sutunlar: Tarih(0), FaturaNo(1), Depo(2), UrunAdi(3), Tip(4), AylikOrt(5),
        # Stok(6), StokAy(7), Adet(8), MF(9), AlimAy(10), BirimFiyat(11), Toplam(12),
        # Kalan(13), Uygun(14), ToplamAy(15), NPV-(16), NPV+(17), Avantaj(18),
        # GuncelStok(19), GAyOrt(20), Bitis(21)
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
> Tip: {vals[4]}
> Alinan Adet: {vals[8]}
> MF (Bedava): {vals[9]}

------------------------------------
STOK ANALIZI (Fatura Tarihi)
------------------------------------
> Aylik Ortalama (fatura ani): {vals[5]} adet/ay
> Fatura Aninda Stok: {vals[6]} adet
> Stok Kac Aylik: {vals[7]} ay
> Alinan Miktar: {vals[8]} adet
> Alim Kac Aylik: {vals[10]} ay
> Kalan (Siparis Gereken): {vals[13]} adet
> Uygun mu: {vals[14]}
> Toplam Stok Kac Ay: {vals[15]} ay

------------------------------------
GUNCEL STOK ANALIZI (Bugun)
------------------------------------
> Guncel Stok: {vals[19]} adet
> Guncel Aylik Ortalama: {vals[20]} adet/ay
> Tahmini Bitis: {vals[21]} ay

------------------------------------
FIYAT BILGILERI
------------------------------------
> Birim Fiyat: {vals[11]} TL
> Toplam Tutar: {vals[12]} TL

------------------------------------
MF AVANTAJ ANALIZI
------------------------------------
> NPV MF'siz: {vals[16]} TL
> NPV MF'li: {vals[17]} TL
> MF Avantaj: {vals[18]} TL
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
                    "Tarih", "Fatura No", "Depo", "Urun Adi", "Tip",
                    f"Aylik Ort ({ortalama_ay} Ay)", "Stok", "Stok Ay",
                    "Adet", "MF", "Alim Ay", "Birim Fiyat", "Toplam",
                    "Kalan", "Uygun", "Toplam Ay", "NPV-", "NPV+", "Avantaj",
                    "Guncel Stok", f"Guncel Aylik Ort ({ortalama_ay} Ay)", "Bitis (Ay)"
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
