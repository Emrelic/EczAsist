"""
Stok Analiz Raporu GUI
2017'den beri tüm ilaçların stok, sarf, miad analizi
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import logging
from datetime import datetime, date
from decimal import Decimal
import csv

logger = logging.getLogger(__name__)


class StokAnalizGUI:
    """Stok Analiz Raporu Penceresi"""

    # Varsayılan ayarlar
    DEFAULT_AYARLAR = {
        'sarf_periyotlari': [3, 6, 12, 24],  # Gösterilecek sarf periyotları (ay)
        'hesap_baz_ay': 6,  # Bitiş hesabı için baz alınacak ay
        'fazla_stok_ay': 6,  # Kaç aylık fazla stok hesaplanacak
    }

    def __init__(self, parent):
        self.parent = parent
        self.parent.title("Stok Analiz Raporu")
        self.parent.geometry("1600x800")

        self.db = None
        self.veriler = []
        self.filtrelenmis_veriler = []
        self.ayarlar = self.DEFAULT_AYARLAR.copy()

        # Sıralama durumu
        self.sort_column = None
        self.sort_reverse = False

        self._arayuz_olustur()
        self._baglanti_kur()

    def _arayuz_olustur(self):
        """Ana arayüzü oluştur"""
        # Ana frame
        main_frame = ttk.Frame(self.parent, padding=5)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Üst panel - Filtreler ve Ayarlar
        self._filtre_panel_olustur(main_frame)

        # Orta panel - Tablo
        self._tablo_olustur(main_frame)

        # Alt panel - Status bar
        self._status_bar_olustur(main_frame)

    def _filtre_panel_olustur(self, parent):
        """Filtre panelini oluştur"""
        filtre_frame = ttk.LabelFrame(parent, text="Filtreler ve Ayarlar", padding=5)
        filtre_frame.pack(fill=tk.X, pady=(0, 5))

        # Satır 1 - Temel filtreler
        row1 = ttk.Frame(filtre_frame)
        row1.pack(fill=tk.X, pady=2)

        # Ürün Tipi
        ttk.Label(row1, text="Ürün Tipi:").pack(side=tk.LEFT, padx=(0, 5))
        self.urun_tipi_combo = ttk.Combobox(row1, width=20, state="readonly")
        self.urun_tipi_combo.pack(side=tk.LEFT, padx=(0, 15))
        self.urun_tipi_combo['values'] = ["Tümü"]
        self.urun_tipi_combo.set("Tümü")

        # Ürün Adı
        ttk.Label(row1, text="Ürün Adı:").pack(side=tk.LEFT, padx=(0, 5))
        self.urun_adi_entry = ttk.Entry(row1, width=25)
        self.urun_adi_entry.pack(side=tk.LEFT, padx=(0, 15))

        # Sadece Stoklu
        self.sadece_stoklu_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1, text="Sadece Stoklu", variable=self.sadece_stoklu_var).pack(side=tk.LEFT, padx=(0, 15))

        # İlaçları Parti Bazlı Ayır
        self.parti_ayir_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="İlaçları Parti Bazlı Ayır (Miad)", variable=self.parti_ayir_var).pack(side=tk.LEFT, padx=(0, 15))

        # Sorgula butonu
        ttk.Button(row1, text="Sorgula", command=self.sorgula, width=12).pack(side=tk.LEFT, padx=(0, 10))

        # Excel Aktar
        ttk.Button(row1, text="Excel Aktar", command=self.excel_aktar, width=12).pack(side=tk.LEFT, padx=(0, 10))

        # Satır 2 - Ayarlar
        row2 = ttk.Frame(filtre_frame)
        row2.pack(fill=tk.X, pady=2)

        ttk.Label(row2, text="Bitiş Hesabı Baz Ay:").pack(side=tk.LEFT, padx=(0, 5))
        self.baz_ay_combo = ttk.Combobox(row2, width=5, state="readonly")
        self.baz_ay_combo['values'] = ["3", "6", "12", "24"]
        self.baz_ay_combo.set("6")
        self.baz_ay_combo.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(row2, text="Fazla Stok (Ay):").pack(side=tk.LEFT, padx=(0, 5))
        self.fazla_stok_entry = ttk.Entry(row2, width=5)
        self.fazla_stok_entry.insert(0, "6")
        self.fazla_stok_entry.pack(side=tk.LEFT, padx=(0, 15))

        # Limit
        ttk.Label(row2, text="Limit:").pack(side=tk.LEFT, padx=(0, 5))
        self.limit_combo = ttk.Combobox(row2, width=8, state="readonly")
        self.limit_combo['values'] = ["1000", "2000", "5000", "10000", "Tümü"]
        self.limit_combo.set("5000")
        self.limit_combo.pack(side=tk.LEFT, padx=(0, 15))

        # Satır 3 - Kolon filtreleri
        row3 = ttk.Frame(filtre_frame)
        row3.pack(fill=tk.X, pady=2)

        ttk.Label(row3, text="Tablo Filtresi:").pack(side=tk.LEFT, padx=(0, 5))
        self.tablo_filtre_entry = ttk.Entry(row3, width=30)
        self.tablo_filtre_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.tablo_filtre_entry.bind('<KeyRelease>', self._tablo_filtrele)

        ttk.Button(row3, text="Temizle", command=self._filtreleri_temizle, width=10).pack(side=tk.LEFT)

    def _tablo_olustur(self, parent):
        """Tabloyu oluştur"""
        tablo_frame = ttk.Frame(parent)
        tablo_frame.pack(fill=tk.BOTH, expand=True)

        # Sütunlar
        self.columns = [
            ("UrunTipi", 100),
            ("UrunAdi", 250),
            ("PartiNo", 40),
            ("Stok", 50),
            ("Sarf3", 55),
            ("Sarf6", 55),
            ("Sarf12", 55),
            ("Sarf24", 55),
            ("OrtAy3", 55),
            ("OrtAy6", 55),
            ("OrtAy12", 55),
            ("OrtAy24", 55),
            ("EtiketFiyat", 75),
            ("Maliyet", 70),
            ("ToplamMaliyet", 90),
            ("EnYakinMiad", 85),
            ("MiadaKacGun", 70),
            ("StokBitisGunu", 80),
            ("MiadaKacKezBiter", 85),
            ("FazlaStokMaliyet", 95),
        ]

        self.column_headers = {
            "UrunTipi": "Ürün Tipi",
            "UrunAdi": "Ürün Adı",
            "PartiNo": "Parti",
            "Stok": "Stok",
            "Sarf3": "3 Ay",
            "Sarf6": "6 Ay",
            "Sarf12": "12 Ay",
            "Sarf24": "24 Ay",
            "OrtAy3": "Ort 3",
            "OrtAy6": "Ort 6",
            "OrtAy12": "Ort 12",
            "OrtAy24": "Ort 24",
            "EtiketFiyat": "Etiket",
            "Maliyet": "Maliyet",
            "ToplamMaliyet": "Top.Maliyet",
            "EnYakinMiad": "Miad",
            "MiadaKacGun": "Miada Gün",
            "StokBitisGunu": "Bitiş Gün",
            "MiadaKacKezBiter": "Kaç Kez Biter",
            "FazlaStokMaliyet": "Fazla Stok TL",
        }

        # Treeview
        col_ids = [c[0] for c in self.columns]
        self.tree = ttk.Treeview(tablo_frame, columns=col_ids, show='headings', height=25)

        # Sütun başlıklarını ayarla
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

        # Çift tıklama
        self.tree.bind('<Double-1>', self.detay_goster)

        # Renk tagleri
        self.tree.tag_configure('miad_kritik', background='#ffcccc')  # Kırmızı - miad 30 gün içinde
        self.tree.tag_configure('miad_uyari', background='#ffffcc')   # Sarı - miad 90 gün içinde
        self.tree.tag_configure('fazla_stok', background='#ccffcc')   # Yeşil - fazla stok var

    def _status_bar_olustur(self, parent):
        """Status bar oluştur"""
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill=tk.X, pady=(5, 0))

        self.status_label = ttk.Label(status_frame, text="Hazır")
        self.status_label.pack(side=tk.LEFT)

        self.toplam_label = ttk.Label(status_frame, text="")
        self.toplam_label.pack(side=tk.RIGHT)

    def _baglanti_kur(self):
        """Veritabanı bağlantısı kur"""
        try:
            from botanik_db import BotanikDB
            self.db = BotanikDB()
            if self.db.baglan():
                self.status_label.config(text="Veritabanına bağlandı")
                self._urun_tiplerini_yukle()
            else:
                self.status_label.config(text="Bağlantı hatası!")
        except Exception as e:
            logger.error(f"DB bağlantı hatası: {e}")
            self.status_label.config(text=f"Hata: {e}")

    def _urun_tiplerini_yukle(self):
        """Ürün tiplerini combo'ya yükle"""
        try:
            tipler = self.db.urun_tipleri_getir()
            tip_listesi = ["Tümü"] + [t['UrunTipAdi'] for t in tipler]
            self.urun_tipi_combo['values'] = tip_listesi
        except Exception as e:
            logger.error(f"Ürün tipleri yükleme hatası: {e}")

    def sorgula(self):
        """Sorgu çalıştır"""
        self.status_label.config(text="Sorgulanıyor...")
        self.parent.update()

        # Parametreleri al
        urun_tipi = self.urun_tipi_combo.get()
        if urun_tipi == "Tümü":
            urun_tipi = None

        urun_adi = self.urun_adi_entry.get().strip() or None
        sadece_stoklu = self.sadece_stoklu_var.get()
        parti_ayir = self.parti_ayir_var.get()

        limit_str = self.limit_combo.get()
        limit = 99999 if limit_str == "Tümü" else int(limit_str)

        # Thread ile sorgula
        def _sorgula():
            try:
                if parti_ayir:
                    # Parti bazlı sorgu (İlaçlar miad bazında ayrılır)
                    self.veriler = self.db.stok_analiz_parti_getir(
                        urun_tipi=urun_tipi,
                        urun_adi=urun_adi,
                        sadece_stoklu=sadece_stoklu,
                        limit=limit
                    )
                else:
                    # Normal sorgu
                    self.veriler = self.db.stok_analiz_getir(
                        urun_tipi=urun_tipi,
                        urun_adi=urun_adi,
                        sadece_stoklu=sadece_stoklu,
                        limit=limit
                    )
                self.parent.after(0, self._veriyi_tabloya_yukle)
            except Exception as e:
                logger.error(f"Sorgu hatası: {e}")
                self.parent.after(0, lambda: messagebox.showerror("Hata", str(e)))

        threading.Thread(target=_sorgula, daemon=True).start()

    def _veriyi_tabloya_yukle(self):
        """Veriyi tabloya yükle"""
        # Tabloyu temizle
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Ayarları al
        try:
            fazla_stok_ay = int(self.fazla_stok_entry.get())
        except:
            fazla_stok_ay = 6

        baz_ay = int(self.baz_ay_combo.get())
        parti_ayir = self.parti_ayir_var.get()

        toplam_maliyet = 0
        toplam_fazla = 0

        for veri in self.veriler:
            # Değerleri formatla
            stok = veri.get('Stok', 0) or 0
            maliyet = float(veri.get('Maliyet', 0) or 0)
            toplam_mal = float(veri.get('ToplamMaliyet', 0) or 0)

            # Baz aya göre ortalama
            ort_key = f'OrtAy{baz_ay}'
            ort_aylik = float(veri.get(ort_key, 0) or 0)

            # Parti bilgisi
            parti_no = veri.get('PartiNo')
            onceki_partiler = veri.get('OncekiPartilerToplam', 0) or 0

            # FIFO bazlı bitiş günü hesabı
            if ort_aylik > 0:
                gunluk_satis = ort_aylik / 30.0
                # Önceki partilerin bitmesi için gereken gün
                onceki_bitis_gunu = onceki_partiler / gunluk_satis if onceki_partiler > 0 else 0
                # Bu partinin bitmesi için gereken gün (öncekiler bittikten sonra)
                bu_parti_bitis = stok / gunluk_satis
                # Toplam bitiş günü
                stok_bitis_gunu = int(onceki_bitis_gunu + bu_parti_bitis)
            else:
                stok_bitis_gunu = None

            # Fazla stok maliyet hesabı
            if ort_aylik > 0:
                gereken_stok = ort_aylik * fazla_stok_ay
                fazla_adet = max(0, stok - gereken_stok)
                fazla_maliyet = fazla_adet * maliyet
            else:
                fazla_maliyet = 0

            toplam_maliyet += toplam_mal
            toplam_fazla += fazla_maliyet

            # Miad formatlama
            miad = veri.get('EnYakinMiad')
            if miad:
                if isinstance(miad, (datetime, date)):
                    miad_str = miad.strftime("%d.%m.%Y")
                else:
                    miad_str = str(miad)[:10]
            else:
                miad_str = "-"

            # Miada kaç kez biter hesabı (FIFO bazlı)
            miada_gun = veri.get('MiadaKacGun')
            if miada_gun and stok_bitis_gunu and stok_bitis_gunu > 0:
                kac_kez_biter = miada_gun / stok_bitis_gunu
            else:
                kac_kez_biter = None

            # Tag belirleme
            tags = ()
            if miada_gun is not None:
                if miada_gun <= 30:
                    tags = ('miad_kritik',)
                elif miada_gun <= 90:
                    tags = ('miad_uyari',)

            if fazla_maliyet > 0:
                tags = ('fazla_stok',) if not tags else tags

            # Parti numarası gösterimi
            parti_str = f"P{parti_no}" if parti_no else "-"

            # Satır ekle
            self.tree.insert('', 'end', values=(
                veri.get('UrunTipi', ''),
                veri.get('UrunAdi', ''),
                parti_str,
                stok,
                veri.get('Sarf3', 0) or 0,
                veri.get('Sarf6', 0) or 0,
                veri.get('Sarf12', 0) or 0,
                veri.get('Sarf24', 0) or 0,
                f"{veri.get('OrtAy3', 0) or 0:.1f}",
                f"{veri.get('OrtAy6', 0) or 0:.1f}",
                f"{veri.get('OrtAy12', 0) or 0:.1f}",
                f"{veri.get('OrtAy24', 0) or 0:.1f}",
                f"{float(veri.get('EtiketFiyat', 0) or 0):.2f}",
                f"{maliyet:.2f}",
                f"{toplam_mal:.2f}",
                miad_str,
                miada_gun if miada_gun else '-',
                stok_bitis_gunu if stok_bitis_gunu else '-',
                f"{kac_kez_biter:.1f}" if kac_kez_biter else '-',
                f"{fazla_maliyet:.2f}",
            ), tags=tags)

        self.filtrelenmis_veriler = self.veriler.copy()
        self.status_label.config(text=f"{len(self.veriler)} ürün yüklendi")
        self.toplam_label.config(text=f"Toplam Maliyet: {toplam_maliyet:,.2f} TL | Fazla Stok: {toplam_fazla:,.2f} TL")

    def _siralama_yap(self, col):
        """Sütuna göre sıralama yap"""
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        # Veriyi al
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children('')]

        # Sayısal mı kontrol et
        try:
            items = [(float(val.replace(',', '.').replace('-', '0') or 0), item) for val, item in items]
            numeric = True
        except:
            numeric = False

        # Sırala
        items.sort(key=lambda x: x[0], reverse=self.sort_reverse)

        # Yeniden sırala
        for index, (val, item) in enumerate(items):
            self.tree.move(item, '', index)

        # Başlık güncelle
        for c, _ in self.columns:
            header = self.column_headers.get(c, c)
            if c == col:
                header += " ▼" if self.sort_reverse else " ▲"
            self.tree.heading(c, text=header)

    def _tablo_filtrele(self, event=None):
        """Tablo içi filtreleme"""
        filtre = self.tablo_filtre_entry.get().lower().strip()

        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            # Tüm değerlerde ara
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
            messagebox.showwarning("Uyarı", "Aktarılacak veri yok!")
            return

        dosya = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Dosyası", "*.csv"), ("Tüm Dosyalar", "*.*")],
            initialfilename=f"stok_analiz_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        )

        if not dosya:
            return

        try:
            # Ayarları al
            try:
                fazla_stok_ay = int(self.fazla_stok_entry.get())
            except:
                fazla_stok_ay = 6

            baz_ay = int(self.baz_ay_combo.get())

            with open(dosya, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')

                # Başlıklar
                headers = [
                    "Ürün Tipi", "Ürün Adı", "Stok",
                    "Sarf 3 Ay", "Sarf 6 Ay", "Sarf 12 Ay", "Sarf 24 Ay",
                    "Ort 3 Ay", "Ort 6 Ay", "Ort 12 Ay", "Ort 24 Ay",
                    "Etiket Fiyat", "Maliyet", "Toplam Maliyet",
                    "En Yakın Miad", "Miada Kaç Gün", "Stok Bitiş Günü",
                    "Miada Kaç Kez Biter", "Fazla Stok Maliyeti"
                ]
                writer.writerow(headers)

                for veri in self.veriler:
                    stok = veri.get('Stok', 0) or 0
                    maliyet = float(veri.get('Maliyet', 0) or 0)

                    ort_key = f'OrtAy{baz_ay}'
                    ort_aylik = float(veri.get(ort_key, 0) or 0)

                    if ort_aylik > 0:
                        gereken_stok = ort_aylik * fazla_stok_ay
                        fazla_adet = max(0, stok - gereken_stok)
                        fazla_maliyet = fazla_adet * maliyet
                    else:
                        fazla_maliyet = 0

                    miad = veri.get('EnYakinMiad')
                    if miad and isinstance(miad, (datetime, date)):
                        miad = miad.strftime("%d.%m.%Y")

                    writer.writerow([
                        veri.get('UrunTipi', ''),
                        veri.get('UrunAdi', ''),
                        stok,
                        veri.get('Sarf3', 0) or 0,
                        veri.get('Sarf6', 0) or 0,
                        veri.get('Sarf12', 0) or 0,
                        veri.get('Sarf24', 0) or 0,
                        veri.get('OrtAy3', 0) or 0,
                        veri.get('OrtAy6', 0) or 0,
                        veri.get('OrtAy12', 0) or 0,
                        veri.get('OrtAy24', 0) or 0,
                        veri.get('EtiketFiyat', 0) or 0,
                        maliyet,
                        veri.get('ToplamMaliyet', 0) or 0,
                        miad or '',
                        veri.get('MiadaKacGun', '') or '',
                        veri.get('StokBitisGunu', '') or '',
                        veri.get('MiadaKacKezBiter', '') or '',
                        fazla_maliyet
                    ])

            messagebox.showinfo("Başarılı", f"{len(self.veriler)} kayıt aktarıldı:\n{dosya}")

        except Exception as e:
            logger.error(f"Excel aktarım hatası: {e}")
            messagebox.showerror("Hata", f"Aktarım hatası:\n{e}")

    def detay_goster(self, event):
        """Çift tıklama ile detay"""
        sel = self.tree.selection()
        if sel:
            vals = self.tree.item(sel[0])['values']
            detay = f"""
═══════════════════════════════════════
           STOK DETAYI
═══════════════════════════════════════

▸ Ürün Tipi: {vals[0]}
▸ Ürün Adı: {vals[1]}
▸ Mevcut Stok: {vals[2]}

───────────────────────────────────────
SARF BİLGİLERİ (Son Dönem Satışlar)
───────────────────────────────────────
▸ Son 3 Ay: {vals[3]} adet
▸ Son 6 Ay: {vals[4]} adet
▸ Son 12 Ay: {vals[5]} adet
▸ Son 24 Ay: {vals[6]} adet

───────────────────────────────────────
AYLIK ORTALAMALAR
───────────────────────────────────────
▸ 3 Aylık Ort: {vals[7]} adet/ay
▸ 6 Aylık Ort: {vals[8]} adet/ay
▸ 12 Aylık Ort: {vals[9]} adet/ay
▸ 24 Aylık Ort: {vals[10]} adet/ay

───────────────────────────────────────
FİYAT BİLGİLERİ
───────────────────────────────────────
▸ Etiket Fiyat: {vals[11]} TL
▸ Birim Maliyet: {vals[12]} TL
▸ Toplam Maliyet: {vals[13]} TL

───────────────────────────────────────
MİAD VE TAHMİNLER
───────────────────────────────────────
▸ En Yakın Miad: {vals[14]}
▸ Miada Kalan Gün: {vals[15]}
▸ Stok Bitiş (Gün): {vals[16]}
▸ Miada Kadar Kaç Kez Biter: {vals[17]}

───────────────────────────────────────
FAZLA STOK
───────────────────────────────────────
▸ Fazla Stok Maliyeti: {vals[18]} TL
            """
            messagebox.showinfo("Stok Detayı", detay.strip())

    def status_guncelle(self, mesaj):
        self.status_label.config(text=mesaj)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    pencere = tk.Toplevel(root)
    app = StokAnalizGUI(pencere)
    root.mainloop()
