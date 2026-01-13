"""
Alis Analiz Raporu GUI
Fatura bazli alis analizi - stok ve satis oranlamalari
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
from datetime import datetime, date, timedelta
from tkcalendar import DateEntry
import csv

logger = logging.getLogger(__name__)


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

        # Siralama durumu
        self.sort_column = None
        self.sort_reverse = False

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
        self.zam_tarihi.set_date(datetime.now() + timedelta(days=365))  # 1 yil sonra varsayilan
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
        """Tabloyu olustur"""
        tablo_frame = ttk.Frame(parent)
        tablo_frame.pack(fill=tk.BOTH, expand=True)

        # Sutunlar - Stok ve Alim aylari yanyana
        self.columns = [
            ("FaturaNo", 90),
            ("Tarih", 75),
            ("Depo", 100),
            ("UrunAdi", 180),
            ("OncekiStok", 55),   # Eski stok miktari
            ("StokAy", 50),       # Eski stok kac ay yetecek
            ("Adet", 45),         # Alinan miktar
            ("AlimAy", 50),       # Alim sonrasi toplam kac ay yetecek
            ("MF", 35),
            ("AylikOrt", 55),
            ("BirimFiyat", 65),
            ("Maliyet", 65),
            ("ToplamTutar", 75),
            ("Vade", 75),
            ("KalanGun", 50),
            ("UygunAlim", 55),
            ("ToplamStok", 60),
            ("NPV_MFsiz", 70),
            ("NPV_MFli", 70),
            ("MF_Avantaj", 75),
        ]

        self.column_headers = {
            "FaturaNo": "Fatura No",
            "Tarih": "Tarih",
            "Depo": "Depo",
            "UrunAdi": "Urun Adi",
            "OncekiStok": "Stok",
            "StokAy": "Stok Ay",
            "Adet": "Adet",
            "AlimAy": "Alim Ay",
            "MF": "MF",
            "AylikOrt": "Ay.Ort",
            "BirimFiyat": "B.Fiyat",
            "Maliyet": "Maliyet",
            "ToplamTutar": "Toplam",
            "Vade": "Vade",
            "KalanGun": "Kalan",
            "UygunAlim": "Uygun",
            "ToplamStok": "Toplam",
            "NPV_MFsiz": "NPV-",
            "NPV_MFli": "NPV+",
            "MF_Avantaj": "Avantaj",
        }

        # Treeview
        col_ids = [c[0] for c in self.columns]
        self.tree = ttk.Treeview(tablo_frame, columns=col_ids, show='headings', height=25)

        # Sutun basliklarini ayarla
        for col_id, width in self.columns:
            header_text = self.column_headers.get(col_id, col_id)
            self.tree.heading(col_id, text=header_text, command=lambda c=col_id: self._siralama_yap(c))
            self.tree.column(col_id, width=width, minwidth=40)

        # Scrollbarlar
        vsb = ttk.Scrollbar(tablo_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tablo_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        tablo_frame.columnconfigure(0, weight=1)
        tablo_frame.rowconfigure(0, weight=1)

        # Cift tiklama
        self.tree.bind('<Double-1>', self.detay_goster)

        # Renk tagleri - Stok durumu icin
        self.tree.tag_configure('stok_normal', background='#ffffff')   # Beyaz - bu ay bitiyor
        self.tree.tag_configure('stok_sari', background='#FFFF99')     # Sari - 1 aya sarkiyor
        self.tree.tag_configure('stok_turuncu', background='#FFCC66')  # Turuncu - 2 aya sarkiyor
        self.tree.tag_configure('stok_kirmizi', background='#FF9999')  # Kirmizi - 3 aya sarkiyor
        self.tree.tag_configure('stok_mor', background='#CC99FF')      # Mor - 4+ aya sarkiyor
        # MF Avantaj icin
        self.tree.tag_configure('mf_avantajli', foreground='#008800')  # Yesil yazi - avantaj var
        self.tree.tag_configure('mf_dezavantajli', foreground='#CC0000')  # Kirmizi yazi - dezavantaj

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

    def _veriyi_tabloya_yukle(self):
        """Veriyi tabloya yukle"""
        # Tabloyu temizle
        for item in self.tree.get_children():
            self.tree.delete(item)

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

            # Stok ay cinsinden
            if aylik_ort > 0:
                stok_ay = onceki_stok / aylik_ort
            else:
                stok_ay = 0

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

            # Vade formatlama
            vade = veri.get('FaturaVade')
            if vade:
                if isinstance(vade, (datetime, date)):
                    vade_str = vade.strftime("%d.%m.%Y")
                else:
                    vade_str = str(vade)[:10]
            else:
                vade_str = "-"

            # Uygun alim hesapla
            uygun_alim = self._uygun_alim_hesapla(kalan_gun, aylik_ort, onceki_stok)

            # Toplam stok (onceki + alinan + MF)
            toplam_stok = onceki_stok + adet + mf

            # Stok gun hesapla (gunluk sarfa gore)
            gunluk_sarf = aylik_ort / 30 if aylik_ort > 0 else 0
            onceki_stok_gun = onceki_stok / gunluk_sarf if gunluk_sarf > 0 else 0
            toplam_stok_gun = toplam_stok / gunluk_sarf if gunluk_sarf > 0 else 0

            # Stok ay hesapla (ay cinsinden)
            # stok_ay: Mevcut stok kac ay yetecek
            # alim_ay: Alim sonrasi toplam kac ay yetecek
            if aylik_ort > 0:
                stok_ay_deger = onceki_stok / aylik_ort
                alim_ay_deger = toplam_stok / aylik_ort
            else:
                stok_ay_deger = 0
                alim_ay_deger = 0

            # Renk belirleme - SADECE toplam stok (stok + alinan + MF) icin
            # Alim sonrasi toplam stok kac ay yetecek - ona gore renklendir
            toplam_stok_renk = self._stok_renk_belirle(toplam_stok_gun, kalan_gun)

            # NPV hesapla (sadece MF varsa)
            npv_mfsiz, npv_mfli, mf_avantaj = self._npv_hesapla(
                alinan=adet,
                mf=mf,
                maliyet=maliyet,
                aylik_ort=aylik_ort,
                faiz_yillik=faiz_yillik,
                depo_vade=depo_vade,
                fatura_tarihi=tarih if isinstance(tarih, date) else None,
                zam_tarihi=zam_tarihi,
                zam_orani=zam_orani
            )

            # Satir rengi: Toplam stok (stok + alinan) kac ay yetecegine gore
            if toplam_stok_renk != 'stok_normal':
                tags = (toplam_stok_renk,)
            else:
                tags = ()

            # Satir ekle - yeni sutun sirasi
            # FaturaNo, Tarih, Depo, UrunAdi, OncekiStok, StokAy, Adet, AlimAy, MF, AylikOrt,
            # BirimFiyat, Maliyet, ToplamTutar, Vade, KalanGun, UygunAlim, ToplamStok,
            # NPV_MFsiz, NPV_MFli, MF_Avantaj
            self.tree.insert('', 'end', values=(
                veri.get('FaturaNo', ''),
                tarih_str,
                veri.get('Depo', '') or '-',
                veri.get('UrunAdi', ''),
                onceki_stok,                                    # Stok miktari
                f"{stok_ay_deger:.1f}" if stok_ay_deger > 0 else "-",  # Stok kac ay
                adet,                                           # Alinan miktar
                f"{alim_ay_deger:.1f}" if alim_ay_deger > 0 else "-",  # Alim sonrasi kac ay
                str(mf) if mf > 0 else '-',
                f"{aylik_ort:.1f}",
                f"{birim_fiyat:.2f}",
                f"{maliyet:.2f}",
                f"{toplam:.2f}",
                vade_str,
                kalan_gun,
                uygun_alim,
                toplam_stok,
                f"{npv_mfsiz:.0f}" if npv_mfsiz > 0 else "-",
                f"{npv_mfli:.0f}" if npv_mfli > 0 else "-",
                f"{mf_avantaj:+.0f}" if mf_avantaj != 0 else "-",
            ), tags=tags)

        self.filtrelenmis_veriler = self.veriler.copy()
        self.status_label.config(text=f"{len(self.veriler)} kayit yuklendi")
        self.toplam_label.config(text=f"Toplam: {toplam_adet:,} adet | {toplam_tutar:,.2f} TL")

    def _siralama_yap(self, col):
        """Sutuna gore siralama yap"""
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        # Veriyi al
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]

        # Sayisal mi kontrol et
        try:
            items = [(float(val.replace(',', '.').replace('-', '0') or 0), item) for val, item in items]
            numeric = True
        except:
            numeric = False

        # Sirala
        items.sort(key=lambda x: x[0], reverse=self.sort_reverse)

        # Yeniden sirala
        for index, (val, item) in enumerate(items):
            self.tree.move(item, '', index)

        # Baslik guncelle
        for c, _ in self.columns:
            header = self.column_headers.get(c, c)
            if c == col:
                header += " v" if self.sort_reverse else " ^"
            self.tree.heading(c, text=header)

    def _tablo_filtrele(self, event=None):
        """Tablo ici filtreleme"""
        filtre = self.tablo_filtre_entry.get().lower().strip()

        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            # Tum degerlerde ara
            match = any(filtre in str(v).lower() for v in values)
            if match:
                self.tree.reattach(item, '', 'end')
            else:
                self.tree.detach(item)

    def _filtreleri_temizle(self):
        """Filtreleri temizle"""
        self.tablo_filtre_entry.delete(0, tk.END)
        self._veriyi_tabloya_yukle()

    def excel_aktar(self):
        """Excel'e aktar"""
        if not self.veriler:
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

            with open(dosya, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')

                # Basliklar - yeni sutun sirasi
                headers = [
                    "Fatura No", "Tarih", "Depo", "Urun Adi",
                    "Stok", "Stok Ay",  # Mevcut stok ve kac ay yetecegi
                    "Adet", "Alim Ay",  # Alinan ve alim sonrasi kac ay
                    "MF", f"Aylik Ort ({ortalama_ay} Ay)",
                    "Birim Fiyat", "Maliyet", "Toplam Tutar", "Fatura Vade",
                    "Kalan Gun", "Uygun Alim", "Toplam Stok",
                    "NPV MFsiz", "NPV MFli", "MF Avantaj"
                ]
                writer.writerow(headers)

                for veri in self.veriler:
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

                    # Stok ay ve alim ay hesapla
                    toplam_stok = onceki_stok + adet + mf
                    stok_ay = onceki_stok / aylik_ort if aylik_ort > 0 else ''
                    alim_ay = toplam_stok / aylik_ort if aylik_ort > 0 else ''
                    uygun_alim = self._uygun_alim_hesapla(kalan_gun, aylik_ort, onceki_stok)

                    tarih = veri.get('Tarih')
                    if tarih and isinstance(tarih, (datetime, date)):
                        tarih_str = tarih.strftime("%d.%m.%Y")
                    else:
                        tarih_str = str(tarih) if tarih else ''

                    vade = veri.get('FaturaVade')
                    if vade and isinstance(vade, (datetime, date)):
                        vade = vade.strftime("%d.%m.%Y")

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
                        zam_orani=zam_orani
                    )

                    writer.writerow([
                        veri.get('FaturaNo', ''),
                        tarih_str,
                        veri.get('Depo', '') or '',
                        veri.get('UrunAdi', ''),
                        onceki_stok,  # Stok
                        round(stok_ay, 2) if isinstance(stok_ay, float) else stok_ay,  # Stok Ay
                        adet,  # Adet
                        round(alim_ay, 2) if isinstance(alim_ay, float) else alim_ay,  # Alim Ay
                        mf if mf > 0 else '',
                        aylik_ort,
                        birim_fiyat,
                        maliyet,
                        toplam,
                        vade or '',
                        kalan_gun,
                        uygun_alim,
                        toplam_stok,
                        npv_mfsiz if npv_mfsiz > 0 else '',
                        npv_mfli if npv_mfli > 0 else '',
                        mf_avantaj if mf_avantaj != 0 else ''
                    ])

            messagebox.showinfo("Basarili", f"{len(self.veriler)} kayit aktarildi:\n{dosya}")

        except Exception as e:
            logger.error(f"Excel aktarim hatasi: {e}")
            messagebox.showerror("Hata", f"Aktarim hatasi:\n{e}")

    def detay_goster(self, event):
        """Cift tiklama ile detay"""
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0])['values']
            # Sutunlar: FaturaNo(0), Tarih(1), Depo(2), UrunAdi(3), OncekiStok(4), StokAy(5),
            # Adet(6), AlimAy(7), MF(8), AylikOrt(9), BirimFiyat(10), Maliyet(11),
            # ToplamTutar(12), Vade(13), KalanGun(14), UygunAlim(15), ToplamStok(16),
            # NPV_MFsiz(17), NPV_MFli(18), MF_Avantaj(19)
            detay = f"""
====================================
        ALIS DETAYI
====================================

> Fatura No: {vals[0]}
> Tarih: {vals[1]}
> Depo: {vals[2]}

------------------------------------
URUN BILGILERI
------------------------------------
> Urun Adi: {vals[3]}
> Alinan Adet: {vals[6]}
> MF (Bedava): {vals[8]}

------------------------------------
STOK ANALIZI
------------------------------------
> Mevcut Stok: {vals[4]} adet
> Stok Kac Ay: {vals[5]} ay
> Alinan Miktar: {vals[6]} adet
> Alim Sonrasi Kac Ay: {vals[7]} ay
> Aylik Ortalama: {vals[9]} adet/ay
> Ay Sonuna Kalan: {vals[14]} gun
> Uygun Alim: {vals[15]} adet
> Toplam Stok: {vals[16]} adet

------------------------------------
FIYAT BILGILERI
------------------------------------
> Birim Fiyat: {vals[10]} TL
> Maliyet: {vals[11]} TL
> Toplam Tutar: {vals[12]} TL
> Fatura Vade: {vals[13]}

------------------------------------
MF AVANTAJ ANALIZI
------------------------------------
> NPV MF'siz: {vals[17]} TL
> NPV MF'li: {vals[18]} TL
> MF Avantaj: {vals[19]} TL
            """
            messagebox.showinfo("Alis Detayi", detay.strip())

    def status_guncelle(self, mesaj):
        self.status_label.config(text=mesaj)

    def _stok_renk_belirle(self, stok_gun: float, kalan_gun: int) -> str:
        """
        Stok durumuna gore renk belirle
        stok_gun: Mevcut stogun kac gun yetecegi
        kalan_gun: Ay sonuna kalan gun sayisi

        Returns:
            Tag ismi (stok_normal, stok_sari, stok_turuncu, stok_kirmizi, stok_mor)
        """
        if stok_gun <= kalan_gun:
            return 'stok_normal'  # Bu ay bitiyor - normal
        elif stok_gun <= kalan_gun + 30:
            return 'stok_sari'    # 1 aya sarkiyor
        elif stok_gun <= kalan_gun + 60:
            return 'stok_turuncu' # 2 aya sarkiyor
        elif stok_gun <= kalan_gun + 90:
            return 'stok_kirmizi' # 3 aya sarkiyor
        else:
            return 'stok_mor'     # 4+ aya sarkiyor

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
                    fatura_tarihi: date, zam_tarihi: date, zam_orani: float) -> tuple:
        """
        NPV hesaplama - MF Analiz modulunden adapte

        Returns:
            (npv_mfsiz, npv_mfli, avantaj)
        """
        # MF yoksa hesaplama gereksiz
        if mf == 0 or mf is None:
            return (0, 0, 0)

        if maliyet <= 0 or aylik_ort <= 0:
            return (0, 0, 0)

        aylik_faiz = (faiz_yillik / 100) / 12
        depo_vade_ay = depo_vade / 30

        toplam_gelen = alinan + mf

        # NPV MF'siz: Her ay ihtiyac kadar al
        npv_mfsiz = 0
        kalan_ihtiyac = toplam_gelen
        ay = 0

        while kalan_ihtiyac > 0 and ay < 24:
            bu_ay_sarf = min(aylik_ort, kalan_ihtiyac)

            # Zam kontrolu
            if zam_tarihi and fatura_tarihi and zam_orani > 0:
                if isinstance(fatura_tarihi, date):
                    zam_ay = (zam_tarihi.year - fatura_tarihi.year) * 12 + \
                             (zam_tarihi.month - fatura_tarihi.month)
                    fiyat = maliyet * (1 + zam_orani/100) if ay >= zam_ay else maliyet
                else:
                    fiyat = maliyet
            else:
                fiyat = maliyet

            odeme = bu_ay_sarf * fiyat
            iskonto = (1 + aylik_faiz) ** (ay + 1 + depo_vade_ay)
            npv_mfsiz += odeme / iskonto

            kalan_ihtiyac -= bu_ay_sarf
            ay += 1

        # NPV MF'li: Bugun toplu al - sadece alinan kadar odenir, MF bedava
        odenen_para = alinan * maliyet
        npv_mfli = odenen_para / ((1 + aylik_faiz) ** (1 + depo_vade_ay))

        # Avantaj = MF'siz - MF'li (pozitif = MF karli)
        avantaj = npv_mfsiz - npv_mfli

        return (round(npv_mfsiz, 2), round(npv_mfli, 2), round(avantaj, 2))


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    pencere = tk.Toplevel(root)
    app = AlisAnalizGUI(pencere)
    root.mainloop()
