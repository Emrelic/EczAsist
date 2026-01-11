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
        self.parent.geometry("1650x800")

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
        ttk.Label(row2, text="Ortalama Hesabi (Ay):").pack(side=tk.LEFT, padx=(0, 5))
        self.ortalama_ay_combo = ttk.Combobox(row2, width=5, state="readonly")
        self.ortalama_ay_combo['values'] = ["3", "6", "12", "24"]
        self.ortalama_ay_combo.set("6")
        self.ortalama_ay_combo.pack(side=tk.LEFT, padx=(0, 15))

        # Limit
        ttk.Label(row2, text="Limit:").pack(side=tk.LEFT, padx=(0, 5))
        self.limit_combo = ttk.Combobox(row2, width=8, state="readonly")
        self.limit_combo['values'] = ["1000", "2000", "5000", "10000", "Tumu"]
        self.limit_combo.set("5000")
        self.limit_combo.pack(side=tk.LEFT, padx=(0, 15))

        # Sorgula butonu
        ttk.Button(row2, text="Sorgula", command=self.sorgula, width=12).pack(side=tk.LEFT, padx=(0, 10))

        # Excel Aktar
        ttk.Button(row2, text="Excel Aktar", command=self.excel_aktar, width=12).pack(side=tk.LEFT, padx=(0, 10))

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

        # Sutunlar
        self.columns = [
            ("FaturaNo", 100),
            ("Tarih", 85),
            ("Depo", 120),
            ("UrunAdi", 250),
            ("Adet", 50),
            ("MF", 40),
            ("BirimFiyat", 80),
            ("Maliyet", 80),
            ("ToplamTutar", 95),
            ("FaturaVade", 85),
            ("FaturaOncesiStok", 85),
            ("AylikOrtalama", 85),
            ("OncesiStokAy", 85),
            ("AlinanAy", 75),
        ]

        self.column_headers = {
            "FaturaNo": "Fatura No",
            "Tarih": "Tarih",
            "Depo": "Depo",
            "UrunAdi": "Urun Adi",
            "Adet": "Adet",
            "MF": "MF",
            "BirimFiyat": "Birim Fiyat",
            "Maliyet": "Maliyet",
            "ToplamTutar": "Toplam Tutar",
            "FaturaVade": "Fatura Vade",
            "FaturaOncesiStok": "Onceki Stok",
            "AylikOrtalama": "Aylik Ort.",
            "OncesiStokAy": "Onceki (Ay)",
            "AlinanAy": "Alinan (Ay)",
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

        # Renk tagleri
        self.tree.tag_configure('stok_yok', background='#ffcccc')     # Kirmizi - stok yokken siparis
        self.tree.tag_configure('stok_az', background='#ffffcc')      # Sari - stok azken siparis
        self.tree.tag_configure('stok_fazla', background='#ccffcc')   # Yesil - stok fazlayken siparis

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

        toplam_tutar = 0
        toplam_adet = 0

        for veri in self.veriler:
            # Degerleri al
            adet = veri.get('Adet', 0) or 0
            birim_fiyat = float(veri.get('BirimFiyat', 0) or 0)
            maliyet = float(veri.get('Maliyet', 0) or 0)
            toplam = float(veri.get('ToplamTutar', 0) or 0)
            onceki_stok = veri.get('FaturaOncesiStok', 0) or 0
            aylik_ort = float(veri.get('AylikOrtalama', 0) or 0)

            # Onceki stok kac aylik
            if aylik_ort > 0:
                onceki_stok_ay = onceki_stok / aylik_ort
            else:
                onceki_stok_ay = None

            # Alinan miktar kac aylik
            if aylik_ort > 0:
                alinan_ay = adet / aylik_ort
            else:
                alinan_ay = None

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

            # Tag belirleme (onceki stok durumuna gore)
            tags = ()
            if onceki_stok_ay is not None:
                if onceki_stok_ay <= 0:
                    tags = ('stok_yok',)  # Stok yokken siparis - kirmizi
                elif onceki_stok_ay < 2:
                    tags = ('stok_az',)   # Stok 2 aydan azken siparis - sari
                elif onceki_stok_ay > 6:
                    tags = ('stok_fazla',)  # Stok 6 aydan fazlayken siparis - yesil

            # Satir ekle
            self.tree.insert('', 'end', values=(
                veri.get('FaturaNo', ''),
                tarih_str,
                veri.get('Depo', '') or '-',
                veri.get('UrunAdi', ''),
                adet,
                veri.get('MF', '') or '-',
                f"{birim_fiyat:.2f}",
                f"{maliyet:.2f}",
                f"{toplam:.2f}",
                vade_str,
                onceki_stok,
                f"{aylik_ort:.1f}",
                f"{onceki_stok_ay:.1f}" if onceki_stok_ay is not None else "-",
                f"{alinan_ay:.1f}" if alinan_ay is not None else "-",
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

            with open(dosya, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')

                # Basliklar
                headers = [
                    "Fatura No", "Tarih", "Depo", "Urun Adi", "Adet", "MF",
                    "Birim Fiyat", "Maliyet", "Toplam Tutar", "Fatura Vade",
                    "Fatura Oncesi Stok", f"Aylik Ortalama ({ortalama_ay} Ay)",
                    "Onceki Stok (Ay)", "Alinan (Ay)"
                ]
                writer.writerow(headers)

                for veri in self.veriler:
                    adet = veri.get('Adet', 0) or 0
                    birim_fiyat = float(veri.get('BirimFiyat', 0) or 0)
                    maliyet = float(veri.get('Maliyet', 0) or 0)
                    toplam = float(veri.get('ToplamTutar', 0) or 0)
                    onceki_stok = veri.get('FaturaOncesiStok', 0) or 0
                    aylik_ort = float(veri.get('AylikOrtalama', 0) or 0)

                    onceki_stok_ay = onceki_stok / aylik_ort if aylik_ort > 0 else ''
                    alinan_ay = adet / aylik_ort if aylik_ort > 0 else ''

                    tarih = veri.get('Tarih')
                    if tarih and isinstance(tarih, (datetime, date)):
                        tarih = tarih.strftime("%d.%m.%Y")

                    vade = veri.get('FaturaVade')
                    if vade and isinstance(vade, (datetime, date)):
                        vade = vade.strftime("%d.%m.%Y")

                    writer.writerow([
                        veri.get('FaturaNo', ''),
                        tarih or '',
                        veri.get('Depo', '') or '',
                        veri.get('UrunAdi', ''),
                        adet,
                        veri.get('MF', '') or '',
                        birim_fiyat,
                        maliyet,
                        toplam,
                        vade or '',
                        onceki_stok,
                        aylik_ort,
                        onceki_stok_ay,
                        alinan_ay
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
> Adet: {vals[4]}
> MF: {vals[5]}

------------------------------------
FIYAT BILGILERI
------------------------------------
> Birim Fiyat: {vals[6]} TL
> Maliyet: {vals[7]} TL
> Toplam Tutar: {vals[8]} TL
> Fatura Vade: {vals[9]}

------------------------------------
STOK ANALIZI
------------------------------------
> Fatura Oncesi Stok: {vals[10]} adet
> Aylik Ortalama Satis: {vals[11]} adet/ay
> Onceki Stok: {vals[12]} aylik
> Alinan Miktar: {vals[13]} aylik
            """
            messagebox.showinfo("Alis Detayi", detay.strip())

    def status_guncelle(self, mesaj):
        self.status_label.config(text=mesaj)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    pencere = tk.Toplevel(root)
    app = AlisAnalizGUI(pencere)
    root.mainloop()
