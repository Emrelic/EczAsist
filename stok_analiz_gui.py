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

    # Kolon tip haritası — sıralama ve filtre operatörü seçimi için
    TEXT_COLS = {"UrunTipi", "UrunAdi", "PartiNo"}
    DATE_COLS = {"EnYakinMiad"}

    OPERATORLER_METIN = [
        ("icerir", "İçerir"),
        ("icermez", "İçermez"),
        ("baslar", "İle başlar"),
        ("biter", "İle biter"),
        ("esit", "Eşit"),
        ("esit_degil", "Eşit değil"),
    ]
    OPERATORLER_SAYI = [
        ("=", "= (Eşit)"),
        ("!=", "!= (Eşit değil)"),
        (">", "> (Büyük)"),
        (">=", ">= (Büyük eşit)"),
        ("<", "< (Küçük)"),
        ("<=", "<= (Küçük eşit)"),
        ("arasinda", "Arasında (min - max)"),
    ]

    def __init__(self, parent):
        self.parent = parent
        self.parent.title("Stok Analiz Raporu")
        self.parent.geometry("1600x800")

        self.db = None
        self.veriler = []
        self.tablo_satirlari = []  # hesaplanmış satırlar: [{'values', 'tags', 'toplam_mal', 'fazla_maliyet'}]
        self.filtrelenmis_veriler = []
        self.ayarlar = self.DEFAULT_AYARLAR.copy()

        # Sıralama durumu (col_id string)
        self.sort_column = None
        self.sort_reverse = False

        # Kolon filtreleri: {col_id: {'kosullar': [...], 'liste': set or None}}
        self.kolon_filtreleri = {}
        self._aktif_filtre_popup = None

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
        # Baz Ay değişince — yeni sorgu yapma, mevcut master veriden tabloyu yeniden hesapla
        self.baz_ay_combo.bind('<<ComboboxSelected>>', lambda e: self._baz_ay_degisti())

        ttk.Label(row2, text="Fazla Stok (Ay):").pack(side=tk.LEFT, padx=(0, 5))
        self.fazla_stok_entry = ttk.Entry(row2, width=5)
        self.fazla_stok_entry.insert(0, "6")
        self.fazla_stok_entry.pack(side=tk.LEFT, padx=(0, 15))
        # Fazla Stok değişince anında yeniden hesapla (FocusOut + Enter)
        self.fazla_stok_entry.bind('<FocusOut>', lambda e: self._baz_ay_degisti())
        self.fazla_stok_entry.bind('<Return>', lambda e: self._baz_ay_degisti())

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
        # Başlık sağ-tık → kolon filtre popup'ı
        self.tree.bind('<Button-3>', self._baslik_sag_tiklandi)

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

    def _baz_ay_degisti(self):
        """Baz Ay / Fazla Stok ayarı değişti → veriyi yeniden sorgulamadan satırları yeniden hesapla"""
        if not self.veriler:
            return
        self._satirlari_yeniden_hesapla()

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
        """Yeni veri geldi — filtreleri/sıralamayı sıfırla, satırları hesapla, tabloya bas"""
        self.kolon_filtreleri.clear()
        self.sort_column = None
        self.sort_reverse = False
        self._satirlari_yeniden_hesapla()

    def _ayarlari_al(self):
        """Mevcut Baz Ay + Fazla Stok ayarlarını oku"""
        try:
            fazla_stok_ay = int(self.fazla_stok_entry.get())
        except Exception:
            fazla_stok_ay = 6
        try:
            baz_ay = int(self.baz_ay_combo.get())
        except Exception:
            baz_ay = 6
        return baz_ay, fazla_stok_ay

    def _satirlari_yeniden_hesapla(self):
        """Master self.veriler → self.tablo_satirlari (Baz Ay/Fazla Stok değişince çağrılır)"""
        baz_ay, fazla_stok_ay = self._ayarlari_al()
        self.tablo_satirlari = [
            self._hesapla_satir(veri, baz_ay, fazla_stok_ay) for veri in self.veriler
        ]
        self.filtrelenmis_veriler = self.veriler.copy()
        self._tablo_yenile()

    def _hesapla_satir(self, veri, baz_ay, fazla_stok_ay):
        """Tek bir DB kaydından (dict) tablo satırı dict üret"""
        stok = veri.get('Stok', 0) or 0
        maliyet = float(veri.get('Maliyet', 0) or 0)
        toplam_mal = float(veri.get('ToplamMaliyet', 0) or 0)

        ort_key = f'OrtAy{baz_ay}'
        ort_aylik = float(veri.get(ort_key, 0) or 0)

        parti_no = veri.get('PartiNo')
        onceki_partiler = veri.get('OncekiPartilerToplam', 0) or 0

        # FIFO bazlı bitiş günü
        if ort_aylik > 0:
            gunluk_satis = ort_aylik / 30.0
            onceki_bitis_gunu = onceki_partiler / gunluk_satis if onceki_partiler > 0 else 0
            bu_parti_bitis = stok / gunluk_satis
            stok_bitis_gunu = int(onceki_bitis_gunu + bu_parti_bitis)
        else:
            stok_bitis_gunu = None

        # Fazla stok maliyeti
        if ort_aylik > 0:
            gereken_stok = ort_aylik * fazla_stok_ay
            fazla_adet = max(0, stok - gereken_stok)
            fazla_maliyet = fazla_adet * maliyet
        else:
            fazla_maliyet = 0

        # Miad
        miad = veri.get('EnYakinMiad')
        if miad:
            if isinstance(miad, (datetime, date)):
                miad_str = miad.strftime("%d.%m.%Y")
            else:
                miad_str = str(miad)[:10]
        else:
            miad_str = "-"

        miada_gun = veri.get('MiadaKacGun')
        if miada_gun and stok_bitis_gunu and stok_bitis_gunu > 0:
            kac_kez_biter = miada_gun / stok_bitis_gunu
        else:
            kac_kez_biter = None

        # Renk tag'i
        tags = ()
        if miada_gun is not None:
            if miada_gun <= 30:
                tags = ('miad_kritik',)
            elif miada_gun <= 90:
                tags = ('miad_uyari',)
        if fazla_maliyet > 0 and not tags:
            tags = ('fazla_stok',)

        parti_str = f"P{parti_no}" if parti_no else "-"

        values = (
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
        )

        return {
            'values': values,
            'tags': tags,
            'toplam_mal': toplam_mal,
            'fazla_maliyet': fazla_maliyet,
        }

    def _tablo_yenile(self):
        """Master satırlar → filtre + sıralama → Treeview render (tek render path)"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        indeksler = self._filtre_indeksleri_hesapla()

        if self.sort_column:
            try:
                col_idx = next(i for i, c in enumerate(self.columns) if c[0] == self.sort_column)
                indeksler.sort(
                    key=lambda i: self._sort_key(
                        self.sort_column, self.tablo_satirlari[i]['values'][col_idx]
                    ),
                    reverse=self.sort_reverse,
                )
            except Exception as e:
                logger.error(f"Sıralama hatası: {e}")

        toplam_maliyet = 0.0
        toplam_fazla = 0.0
        for i in indeksler:
            satir = self.tablo_satirlari[i]
            self.tree.insert('', 'end', values=satir['values'], tags=satir['tags'])
            toplam_maliyet += satir['toplam_mal']
            toplam_fazla += satir['fazla_maliyet']

        toplam = len(self.tablo_satirlari)
        gosterilen = len(indeksler)
        if gosterilen == toplam:
            self.status_label.config(text=f"{toplam} ürün yüklendi")
        else:
            self.status_label.config(text=f"{gosterilen} / {toplam} ürün gösteriliyor")
        self.toplam_label.config(
            text=f"Toplam Maliyet: {toplam_maliyet:,.2f} TL | Fazla Stok: {toplam_fazla:,.2f} TL"
        )
        self._baslik_filtre_isaretleri_guncelle()

    def _filtre_indeksleri_hesapla(self):
        """Master satırlara kolon filtresi + serbest metin filtresi uygulayarak indeksleri dön"""
        try:
            metin = self.tablo_filtre_entry.get().lower().strip()
        except Exception:
            metin = ""

        # Kolon filtrelerini idx'e çevir (lookup hızı için)
        kolon_idx = {}
        for col_id in self.kolon_filtreleri:
            for j, (cid, _) in enumerate(self.columns):
                if cid == col_id:
                    kolon_idx[col_id] = j
                    break

        indeksler = []
        for i, satir in enumerate(self.tablo_satirlari):
            values = satir['values']
            gec = True
            for col_id, idx in kolon_idx.items():
                if not self._kolon_satir_uygun_mu(col_id, values[idx]):
                    gec = False
                    break
            if gec and metin:
                if not any(metin in str(v).lower() for v in values):
                    gec = False
            if gec:
                indeksler.append(i)
        return indeksler

    def _siralama_yap(self, col):
        """Sütuna göre sıralama (sol-tık başlık) — veri-bazlı, filtreyi korur"""
        if self.sort_column == col:
            if self.sort_reverse:
                # Üçüncü tıkla sıralamayı kapat
                self.sort_column = None
                self.sort_reverse = False
            else:
                self.sort_reverse = True
        else:
            self.sort_column = col
            self.sort_reverse = False
        self._tablo_yenile()

    def _tablo_filtrele(self, event=None):
        """Serbest metin filtresi değişti → tabloyu yenile"""
        self._tablo_yenile()

    def _filtreleri_temizle(self):
        """Tüm filtreleri ve sıralamayı temizle"""
        try:
            self.tablo_filtre_entry.delete(0, tk.END)
        except Exception:
            pass
        self.kolon_filtreleri.clear()
        self.sort_column = None
        self.sort_reverse = False
        self._tablo_yenile()

    # ----- KOLON FİLTRESİ: sıralama anahtarı + operatör mantığı -----

    def _sort_key(self, col_id, val):
        """Hücre değerini sıralama/karşılaştırma için tip-aware anahtara çevir"""
        if col_id in self.DATE_COLS:
            try:
                parts = str(val).split('.')
                return datetime(int(parts[2]), int(parts[1]), int(parts[0]))
            except Exception:
                return datetime.min
        if col_id in self.TEXT_COLS:
            return str(val).lower()
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

    def _kolon_operatorleri(self, col_id):
        """Kolon tipine göre operatör listesini dön"""
        if col_id in self.TEXT_COLS:
            return self.OPERATORLER_METIN
        # Sayı + tarih için aynı op set; tarih _sort_key ile datetime'a parse edilir
        return self.OPERATORLER_SAYI

    def _kosul_uygun_mu(self, col_id, val_str, op, dgr):
        """Bir hücrenin tek koşulu geçip geçmediğini test et"""
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
            if op == 'arasinda':
                v = self._sort_key(col_id, val_str)
                d1 = self._sort_key(col_id, dgr[0])
                d2 = self._sort_key(col_id, dgr[1])
                lo, hi = (d1, d2) if d1 <= d2 else (d2, d1)
                return lo <= v <= hi
            if op in ('=', '!=', '>', '>=', '<', '<='):
                v = self._sort_key(col_id, val_str)
                d = self._sort_key(col_id, dgr)
                if op == '=':  return v == d
                if op == '!=': return v != d
                if op == '>':  return v > d
                if op == '>=': return v >= d
                if op == '<':  return v < d
                if op == '<=': return v <= d
        except Exception:
            return True  # karşılaştırma başarısızsa satırı gizleme
        return True

    def _kolon_satir_uygun_mu(self, col_id, val):
        """Bu kolonun tüm filtre kurallarını geç mi?"""
        f = self.kolon_filtreleri.get(col_id)
        if not f:
            return True
        val_str = str(val)
        izin = f.get('liste')
        if izin is not None and val_str not in izin:
            return False
        for k in f.get('kosullar', []):
            if not self._kosul_uygun_mu(col_id, val_str, k['op'], k['deger']):
                return False
        return True

    def _baslik_filtre_isaretleri_guncelle(self):
        """Aktif sıralama/filtre olan başlıklara işaret koy"""
        for col_id, _ in self.columns:
            header = self.column_headers.get(col_id, col_id)
            if col_id == self.sort_column:
                header += " ▼" if self.sort_reverse else " ▲"
            if col_id in self.kolon_filtreleri:
                header += " *"
            try:
                self.tree.heading(col_id, text=header)
            except Exception:
                pass

    # ----- KOLON FİLTRESİ: popup -----

    def _baslik_sag_tiklandi(self, event):
        """Başlık sağ-tık → filtre popup'ı"""
        try:
            region = self.tree.identify_region(event.x, event.y)
        except Exception:
            return
        if region != "heading":
            return
        col_str = self.tree.identify_column(event.x)  # '#1', '#2', ...
        try:
            col_idx = int(col_str.replace('#', '')) - 1
        except Exception:
            return
        if not (0 <= col_idx < len(self.columns)):
            return
        col_id = self.columns[col_idx][0]
        self._filtre_popup_ac(col_id)

    def _filtre_popup_ac(self, col_id):
        """Detaylı filtre popup'ı: koşul (operatör+değer) + benzersiz değer listesi"""
        if self._aktif_filtre_popup is not None:
            try:
                if self._aktif_filtre_popup.winfo_exists():
                    self._aktif_filtre_popup.destroy()
            except Exception:
                pass
            self._aktif_filtre_popup = None

        if not self.tablo_satirlari:
            return

        col_idx = next(i for i, c in enumerate(self.columns) if c[0] == col_id)
        baslik = self.column_headers.get(col_id, col_id)

        popup = tk.Toplevel(self.parent)
        popup.title(f"Filtre: {baslik}")
        popup.transient(self.parent)
        popup.resizable(False, True)
        self._aktif_filtre_popup = popup

        try:
            x = self.parent.winfo_pointerx() - 30
            y = self.parent.winfo_pointery() + 10
            popup.geometry(f"340x520+{x}+{y}")
        except Exception:
            popup.geometry("340x520")

        mevcut = self.kolon_filtreleri.get(col_id, {})
        kosullar = list(mevcut.get('kosullar', []))  # mutable kopya

        # ----- KOŞUL FİLTRESİ -----
        kosul_frame = ttk.LabelFrame(popup, text="Koşul Filtresi", padding=4)
        kosul_frame.pack(fill=tk.X, padx=4, pady=(4, 2))

        op_secenekleri = self._kolon_operatorleri(col_id)
        op_etiket_kod = {etiket: kod for kod, etiket in op_secenekleri}
        op_var = tk.StringVar(value=op_secenekleri[0][1])

        op_row = ttk.Frame(kosul_frame)
        op_row.pack(fill=tk.X)
        op_combo = ttk.Combobox(op_row, textvariable=op_var, state="readonly", width=22,
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

        aktif_row = ttk.Frame(kosul_frame)
        aktif_row.pack(fill=tk.X, pady=(2, 0))
        ttk.Label(aktif_row, text="Aktif koşullar (AND):").pack(anchor="w")
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

        deger1_entry.bind("<Return>", lambda e: _kosul_ekle())
        deger2_entry.bind("<Return>", lambda e: _kosul_ekle())

        # ----- DEĞER LİSTESİ -----
        liste_frame = ttk.LabelFrame(popup, text="Veya değerleri seç", padding=4)
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

        # Benzersiz değerler — diğer kolon filtreleri uygulanmış satırlardan
        diger_kolonlar = [c for c in self.kolon_filtreleri if c != col_id]
        diger_idx = {}
        for c in diger_kolonlar:
            for j, (cid, _) in enumerate(self.columns):
                if cid == c:
                    diger_idx[c] = j
                    break

        gorulmus = set()
        benzersiz = []
        for satir in self.tablo_satirlari:
            values = satir['values']
            gec = True
            for c, j in diger_idx.items():
                if not self._kolon_satir_uygun_mu(c, values[j]):
                    gec = False
                    break
            if not gec:
                continue
            v = str(values[col_idx])
            if v not in gorulmus:
                gorulmus.add(v)
                benzersiz.append(v)
        try:
            benzersiz.sort(key=lambda v: self._sort_key(col_id, v))
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

        ttk.Checkbutton(inner, text="(Tümünü Seç)", variable=tumu_var,
                        command=tumu_toggle).pack(anchor="w", padx=2)
        ttk.Separator(inner, orient="horizontal").pack(fill=tk.X, padx=2, pady=1)

        cb_widgets = []
        for val in benzersiz:
            v = tk.BooleanVar(value=val in aktif_liste)
            deger_vars[val] = v
            text = val if val and val.strip() else "(Boş)"
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
                   command=lambda: self._kolon_filtre_kaldir(col_id, popup)).pack(side=tk.LEFT)
        ttk.Button(btn, text="İptal", width=8, command=popup.destroy).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(btn, text="Uygula", width=8,
                   command=lambda: self._kolon_filtre_uygula(
                       col_id, kosullar, deger_vars, set(benzersiz), popup
                   )).pack(side=tk.RIGHT)

        popup.focus_set()
        deger1_entry.focus_set()

    def _kolon_filtre_uygula(self, col_id, kosullar, deger_vars, tum_degerler, popup):
        """Popup'tan koşul + liste filtresini uygula"""
        secili = {v for v, var in deger_vars.items() if var.get()}
        if len(secili) >= len(tum_degerler) or len(secili) == 0:
            liste = None
        else:
            liste = secili

        if not kosullar and liste is None:
            self.kolon_filtreleri.pop(col_id, None)
        else:
            self.kolon_filtreleri[col_id] = {'kosullar': kosullar, 'liste': liste}

        try:
            popup.destroy()
        except Exception:
            pass
        self._aktif_filtre_popup = None
        self._tablo_yenile()

    def _kolon_filtre_kaldir(self, col_id, popup=None):
        """Bu kolonun filtresini ve sıralamasını kaldır"""
        self.kolon_filtreleri.pop(col_id, None)
        if self.sort_column == col_id:
            self.sort_column = None
            self.sort_reverse = False
        if popup:
            try:
                popup.destroy()
            except Exception:
                pass
            self._aktif_filtre_popup = None
        self._tablo_yenile()

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
