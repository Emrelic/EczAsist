"""
Botanik Bot - Tüm Hareketler Raporu
Giriş, çıkış, takas, reçete - tüm stok hareketlerini görüntüler
Gelişmiş filtreleme ve sıralama özellikleri
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict
import threading

# tkcalendar için
try:
    from tkcalendar import DateEntry
    TKCALENDAR_AVAILABLE = True
except ImportError:
    TKCALENDAR_AVAILABLE = False

logger = logging.getLogger(__name__)


class TumHareketlerGUI:
    """Tüm Hareketler rapor penceresi - Gelişmiş UI"""

    # Hareket tipleri
    HAREKET_TIPLERI = {
        "TUMU": "Tümü",
        "FATURA_GIRIS": "Fatura Girişi (Alım)",
        "FATURA_CIKIS": "Fatura Çıkışı (Satış)",
        "RECETE_SATIS": "Reçeteli Satış",
        "ELDEN_SATIS": "Parakende (Elden) Satış",
        "TAKAS_GIRIS": "Takas Girişi",
        "TAKAS_CIKIS": "Takas Çıkışı",
        "IADE": "İade"
    }

    # Yön seçenekleri
    YON_SECENEKLERI = ["Tümü", "GIRIS", "CIKIS"]

    def __init__(self, root: tk.Toplevel):
        self.root = root
        self.root.title("Tüm Hareketler Raporu")
        self.root.state('zoomed')

        # Renk şeması
        self.bg_color = '#F5F5F5'
        self.header_color = '#1565C0'
        self.filter_bg = '#E3F2FD'
        self.fg_color = 'white'

        self.root.configure(bg=self.bg_color)

        # Veritabanı ve veri
        self.db = None
        self.veriler = []
        self.filtrelenmis_veriler = []

        # Sıralama durumu
        self.siralama_sutun = None
        self.siralama_ters = False

        # Sütun filtre değerleri
        self.sutun_filtreler = {}

        self.arayuz_olustur()
        self.root.after(100, self.baslangic_verileri_yukle)

    def arayuz_olustur(self):
        """Ana arayüzü oluştur"""
        self.header_olustur()
        self.filtre_paneli_olustur()
        self.tablo_alani_olustur()
        self.status_bar_olustur()

    def header_olustur(self):
        """Üst başlık"""
        header = tk.Frame(self.root, bg=self.header_color, height=55)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header, text="📦 Tüm Hareketler Raporu",
            font=("Segoe UI", 14, "bold"), bg=self.header_color, fg=self.fg_color
        ).pack(side="left", padx=15, pady=12)

        # Butonlar
        btn_style = {'font': ("Segoe UI", 9), 'cursor': 'hand2', 'bd': 0, 'padx': 12, 'pady': 4}

        tk.Button(header, text="✕ Kapat", bg='#C62828', fg='white',
                  activebackground='#B71C1C', command=self.root.destroy, **btn_style
                  ).pack(side="right", padx=10, pady=12)

        tk.Button(header, text="📥 Excel", bg='#2E7D32', fg='white',
                  activebackground='#1B5E20', command=self.excel_aktar, **btn_style
                  ).pack(side="right", padx=5, pady=12)

    def filtre_paneli_olustur(self):
        """Gelişmiş filtre paneli"""
        # Ana filtre frame
        ana_filtre = tk.Frame(self.root, bg=self.filter_bg)
        ana_filtre.pack(fill="x", padx=5, pady=5)

        # === SATIR 1: Tarih ve Hareket Tipi ===
        satir1 = tk.Frame(ana_filtre, bg=self.filter_bg)
        satir1.pack(fill="x", pady=5, padx=10)

        # Tarih seçiciler
        self._filtre_label(satir1, "Başlangıç:").pack(side="left")
        if TKCALENDAR_AVAILABLE:
            self.baslangic_tarih = DateEntry(
                satir1, width=12, date_pattern='dd.mm.yyyy',
                background='#1565C0', foreground='white', headersbackground='#1565C0',
                selectbackground='#1976D2', selectforeground='white',
                normalbackground='white', normalforeground='black',
                weekendbackground='#FFCDD2', weekendforeground='black',
                locale='tr_TR'
            )
            self.baslangic_tarih.set_date(datetime.now() - timedelta(days=7))
        else:
            self.baslangic_tarih = ttk.Entry(satir1, width=12)
            self.baslangic_tarih.insert(0, (datetime.now() - timedelta(days=7)).strftime("%d.%m.%Y"))
        self.baslangic_tarih.pack(side="left", padx=(5, 15))

        self._filtre_label(satir1, "Bitiş:").pack(side="left")
        if TKCALENDAR_AVAILABLE:
            self.bitis_tarih = DateEntry(
                satir1, width=12, date_pattern='dd.mm.yyyy',
                background='#1565C0', foreground='white', headersbackground='#1565C0',
                selectbackground='#1976D2', selectforeground='white',
                normalbackground='white', normalforeground='black',
                weekendbackground='#FFCDD2', weekendforeground='black',
                locale='tr_TR'
            )
            self.bitis_tarih.set_date(datetime.now())
        else:
            self.bitis_tarih = ttk.Entry(satir1, width=12)
            self.bitis_tarih.insert(0, datetime.now().strftime("%d.%m.%Y"))
        self.bitis_tarih.pack(side="left", padx=(5, 20))

        # Hızlı tarih butonları
        tk.Button(satir1, text="Bugün", font=("Segoe UI", 8), bg='#90CAF9',
                  command=lambda: self._hizli_tarih(0), bd=0, padx=8
                  ).pack(side="left", padx=2)
        tk.Button(satir1, text="7 Gün", font=("Segoe UI", 8), bg='#90CAF9',
                  command=lambda: self._hizli_tarih(7), bd=0, padx=8
                  ).pack(side="left", padx=2)
        tk.Button(satir1, text="30 Gün", font=("Segoe UI", 8), bg='#90CAF9',
                  command=lambda: self._hizli_tarih(30), bd=0, padx=8
                  ).pack(side="left", padx=2)
        tk.Button(satir1, text="Bu Ay", font=("Segoe UI", 8), bg='#90CAF9',
                  command=self._bu_ay, bd=0, padx=8
                  ).pack(side="left", padx=2)

        # Hareket tipi ve Yön
        self._filtre_label(satir1, "Hareket:").pack(side="left", padx=(20, 5))
        self.hareket_tipi = ttk.Combobox(satir1, values=list(self.HAREKET_TIPLERI.values()),
                                         width=18, state="readonly")
        self.hareket_tipi.set("Tümü")
        self.hareket_tipi.pack(side="left", padx=(0, 15))

        self._filtre_label(satir1, "Yön:").pack(side="left")
        self.yon_filtre = ttk.Combobox(satir1, values=self.YON_SECENEKLERI, width=8, state="readonly")
        self.yon_filtre.set("Tümü")
        self.yon_filtre.pack(side="left", padx=(5, 0))

        # Limit (sağ tarafta)
        self._filtre_label(satir1, "Limit:").pack(side="right", padx=(10, 5))
        self.limit_var = tk.StringVar(value="1000")
        ttk.Combobox(satir1, textvariable=self.limit_var, values=["100", "500", "1000", "5000", "10000"],
                     width=7, state="readonly").pack(side="right")

        # === SATIR 2: Metin filtreleri ===
        satir2 = tk.Frame(ana_filtre, bg=self.filter_bg)
        satir2.pack(fill="x", pady=5, padx=10)

        self._filtre_label(satir2, "Ürün Adı:").pack(side="left")
        self.urun_ara = ttk.Entry(satir2, width=25)
        self.urun_ara.pack(side="left", padx=(5, 15))
        self.urun_ara.bind('<Return>', lambda e: self.sorgula())

        self._filtre_label(satir2, "Hasta/İlgili:").pack(side="left")
        self.hasta_ara = ttk.Entry(satir2, width=20)
        self.hasta_ara.pack(side="left", padx=(5, 15))
        self.hasta_ara.bind('<Return>', lambda e: self.sorgula())

        self._filtre_label(satir2, "Doktor:").pack(side="left")
        self.doktor_ara = ttk.Entry(satir2, width=15)
        self.doktor_ara.pack(side="left", padx=(5, 15))
        self.doktor_ara.bind('<Return>', lambda e: self.sorgula())

        self._filtre_label(satir2, "Depo:").pack(side="left")
        self.depo_ara = ttk.Entry(satir2, width=15)
        self.depo_ara.pack(side="left", padx=(5, 15))
        self.depo_ara.bind('<Return>', lambda e: self.sorgula())

        # Butonlar
        tk.Button(satir2, text="🔍 Sorgula", font=("Segoe UI", 10, "bold"),
                  bg='#1565C0', fg='white', activebackground='#0D47A1',
                  cursor='hand2', bd=0, padx=20, pady=3, command=self.sorgula
                  ).pack(side="left", padx=(20, 5))

        tk.Button(satir2, text="🗑 Temizle", font=("Segoe UI", 9),
                  bg='#757575', fg='white', activebackground='#616161',
                  cursor='hand2', bd=0, padx=12, pady=3, command=self.filtreleri_temizle
                  ).pack(side="left", padx=5)

        # Tablo filtre alanı bilgisi
        self.aktif_filtre_label = tk.Label(
            satir2, text="", font=("Segoe UI", 8, "italic"),
            bg=self.filter_bg, fg='#1565C0'
        )
        self.aktif_filtre_label.pack(side="right", padx=10)

    def _filtre_label(self, parent, text):
        return tk.Label(parent, text=text, font=("Segoe UI", 9), bg=self.filter_bg)

    def _hizli_tarih(self, gun):
        """Hızlı tarih seçimi"""
        bitis = datetime.now()
        baslangic = bitis - timedelta(days=gun)
        if TKCALENDAR_AVAILABLE:
            self.baslangic_tarih.set_date(baslangic)
            self.bitis_tarih.set_date(bitis)
        else:
            self.baslangic_tarih.delete(0, tk.END)
            self.baslangic_tarih.insert(0, baslangic.strftime("%d.%m.%Y"))
            self.bitis_tarih.delete(0, tk.END)
            self.bitis_tarih.insert(0, bitis.strftime("%d.%m.%Y"))

    def _bu_ay(self):
        """Bu ayın başından bugüne"""
        bugun = datetime.now()
        ay_basi = bugun.replace(day=1)
        if TKCALENDAR_AVAILABLE:
            self.baslangic_tarih.set_date(ay_basi)
            self.bitis_tarih.set_date(bugun)
        else:
            self.baslangic_tarih.delete(0, tk.END)
            self.baslangic_tarih.insert(0, ay_basi.strftime("%d.%m.%Y"))
            self.bitis_tarih.delete(0, tk.END)
            self.bitis_tarih.insert(0, bugun.strftime("%d.%m.%Y"))

    def tablo_alani_olustur(self):
        """Tablo alanı - filtre satırı ile"""
        tablo_container = tk.Frame(self.root, bg=self.bg_color)
        tablo_container.pack(fill="both", expand=True, padx=5, pady=5)

        # Sütun tanımları - TÜM ALANLAR
        self.columns = [
            ("Tarih", 80), ("HareketTipi", 95), ("Yon", 45), ("Ilgili", 110),
            ("UrunAdi", 200), ("Adet", 45), ("EtiketFiyat", 70), ("BirimFiyat", 70),
            ("Tutar", 80), ("Maliyet", 70), ("HastaAdi", 110), ("DoktorAdi", 100),
            ("TesisAdi", 100), ("KurumAdi", 90), ("DepoAdi", 90), ("EczaneAdi", 90),
            ("IskontoKamu", 55), ("IskontoEczane", 55), ("IskontoTicari", 55),
            ("FiyatFarki", 65), ("Iskonto", 55), ("VadeTarihi", 80), ("BelgeNo", 95)
        ]

        self.column_headers = {
            "Tarih": "Tarih", "HareketTipi": "Hareket", "Yon": "Yön", "Ilgili": "İlgili",
            "UrunAdi": "Ürün Adı", "Adet": "Adet", "EtiketFiyat": "Etiket", "BirimFiyat": "Birim",
            "Tutar": "Tutar", "Maliyet": "Maliyet", "HastaAdi": "Hasta", "DoktorAdi": "Doktor",
            "TesisAdi": "Tesis", "KurumAdi": "Kurum", "DepoAdi": "Depo", "EczaneAdi": "Eczane",
            "IskontoKamu": "İsk.K", "IskontoEczane": "İsk.E", "IskontoTicari": "İsk.T",
            "FiyatFarki": "Fyt.Fark", "Iskonto": "İskonto", "VadeTarihi": "Vade", "BelgeNo": "Belge No"
        }

        # === Sütun başlık filtre satırı ===
        filtre_satir = tk.Frame(tablo_container, bg='#BBDEFB')
        filtre_satir.pack(fill="x")

        self.sutun_filtre_entries = {}
        for col_name, width in self.columns:
            frame = tk.Frame(filtre_satir, bg='#BBDEFB', width=width)
            frame.pack(side="left", padx=1)
            frame.pack_propagate(False)

            entry = ttk.Entry(frame, width=width // 10)
            entry.pack(fill="x", padx=1, pady=2)
            entry.bind('<KeyRelease>', lambda e, c=col_name: self._sutun_filtrele(c))
            self.sutun_filtre_entries[col_name] = entry

        # Scrollbar için boşluk
        tk.Frame(filtre_satir, bg='#BBDEFB', width=20).pack(side="left")

        # === Treeview ===
        tree_frame = tk.Frame(tablo_container, bg=self.bg_color)
        tree_frame.pack(fill="both", expand=True)

        col_names = [c[0] for c in self.columns]
        self.tree = ttk.Treeview(tree_frame, columns=col_names, show="headings", height=20)

        # Sütun ayarları
        for col_name, width in self.columns:
            header_text = self.column_headers.get(col_name, col_name)
            self.tree.heading(col_name, text=header_text,
                              command=lambda c=col_name: self.sutun_sirala(c))
            anchor = 'center' if col_name in ['Adet', 'EtiketFiyat', 'BirimFiyat', 'Tutar', 'Yon'] else 'w'
            self.tree.column(col_name, width=width, anchor=anchor, minwidth=40)

        # Scrollbar
        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        # Satır renkleri
        self.tree.tag_configure('giris', background='#E8F5E9')
        self.tree.tag_configure('cikis', background='#FFEBEE')
        self.tree.tag_configure('selected', background='#BBDEFB')

        # Events
        self.tree.bind('<Double-1>', self.detay_goster)

    def sutun_sirala(self, column):
        """Sütuna göre sırala - toggle asc/desc"""
        if self.siralama_sutun == column:
            self.siralama_ters = not self.siralama_ters
        else:
            self.siralama_sutun = column
            self.siralama_ters = False

        # Başlıkları güncelle
        for col_name, _ in self.columns:
            header_text = self.column_headers.get(col_name, col_name)
            if col_name == column:
                arrow = " ▼" if self.siralama_ters else " ▲"
                header_text += arrow
            self.tree.heading(col_name, text=header_text)

        # Sıralama yap
        self._veriyi_tabloya_yukle()

    def _sutun_filtrele(self, column):
        """Sütun bazlı filtreleme"""
        # Aktif filtreleri güncelle
        aktif_filtreler = []
        for col, entry in self.sutun_filtre_entries.items():
            val = entry.get().strip()
            if val:
                self.sutun_filtreler[col] = val.lower()
                aktif_filtreler.append(f"{self.column_headers.get(col, col)}: {val}")
            else:
                self.sutun_filtreler.pop(col, None)

        # Aktif filtre bilgisi
        if aktif_filtreler:
            self.aktif_filtre_label.config(text=f"Tablo filtreleri: {', '.join(aktif_filtreler)}")
        else:
            self.aktif_filtre_label.config(text="")

        # Tabloyu yenile
        self._veriyi_tabloya_yukle()

    def status_bar_olustur(self):
        """Alt durum çubuğu"""
        status = tk.Frame(self.root, bg='#263238', height=28)
        status.pack(fill="x", side="bottom")
        status.pack_propagate(False)

        self.status_label = tk.Label(status, text="Hazır", font=("Segoe UI", 8),
                                     bg='#263238', fg='white')
        self.status_label.pack(side="left", padx=10, pady=4)

        self.kayit_sayisi_label = tk.Label(status, text="Kayıt: 0 / 0", font=("Segoe UI", 8),
                                           bg='#263238', fg='#90CAF9')
        self.kayit_sayisi_label.pack(side="right", padx=10, pady=4)

        # Toplam tutar
        self.toplam_tutar_label = tk.Label(status, text="Toplam: 0.00 TL", font=("Segoe UI", 8),
                                           bg='#263238', fg='#81C784')
        self.toplam_tutar_label.pack(side="right", padx=20, pady=4)

    def baslangic_verileri_yukle(self):
        self.sorgula()

    def sorgula(self):
        """Veritabanından sorgu"""
        self.status_guncelle("Sorgulanıyor...")
        self.root.update()
        threading.Thread(target=self._sorgula_thread, daemon=True).start()

    def _sorgula_thread(self):
        try:
            from botanik_db import BotanikDB

            if not self.db:
                self.db = BotanikDB()
                if not self.db.baglan():
                    self.root.after(0, lambda: messagebox.showerror("Hata", "Veritabanına bağlanılamadı!"))
                    return

            # Filtreleri al
            baslangic = self._tarih_al(self.baslangic_tarih)
            bitis = self._tarih_al(self.bitis_tarih)

            hareket_tipi = None
            secili_tip = self.hareket_tipi.get()
            for key, value in self.HAREKET_TIPLERI.items():
                if value == secili_tip and key != "TUMU":
                    hareket_tipi = key
                    break

            urun_adi = self.urun_ara.get().strip() or None
            limit = int(self.limit_var.get())

            # Sorgu
            self.veriler = self.db.tum_hareketler_getir(
                baslangic_tarih=baslangic,
                bitis_tarih=bitis,
                hareket_tipi=hareket_tipi,
                urun_adi=urun_adi,
                limit=limit
            )

            # Ek filtreler (yön, hasta, doktor, depo)
            yon = self.yon_filtre.get()
            hasta = self.hasta_ara.get().strip().lower()
            doktor = self.doktor_ara.get().strip().lower()
            depo = self.depo_ara.get().strip().lower()

            if yon != "Tümü" or hasta or doktor or depo:
                filtreli = []
                for v in self.veriler:
                    if yon != "Tümü" and v.get('Yon') != yon:
                        continue
                    if hasta:
                        hasta_adi = (v.get('HastaAdi') or '').lower()
                        ilgili = (v.get('Ilgili') or '').lower()
                        if hasta not in hasta_adi and hasta not in ilgili:
                            continue
                    if doktor and doktor not in (v.get('DoktorAdi') or '').lower():
                        continue
                    if depo and depo not in (v.get('Ilgili') or '').lower():
                        continue
                    filtreli.append(v)
                self.veriler = filtreli

            self.root.after(0, self._veriyi_tabloya_yukle)

        except Exception as e:
            logger.error(f"Sorgu hatası: {e}")
            self.root.after(0, lambda: messagebox.showerror("Hata", f"Sorgu hatası:\n{e}"))
            self.root.after(0, lambda: self.status_guncelle("Hata!"))

    def _tarih_al(self, widget) -> Optional[date]:
        """Tarih widget'ından date al"""
        try:
            if TKCALENDAR_AVAILABLE and hasattr(widget, 'get_date'):
                return widget.get_date()
            else:
                return datetime.strptime(widget.get().strip(), "%d.%m.%Y").date()
        except:
            return None

    def _veriyi_tabloya_yukle(self):
        """Veriyi tabloya yükle (filtreleme ve sıralama ile)"""
        # Temizle
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Sütun filtrelerini uygula
        self.filtrelenmis_veriler = []
        for veri in self.veriler:
            uygun = True
            for col, filtre_val in self.sutun_filtreler.items():
                hucre_val = str(veri.get(col, '') or '').lower()
                if filtre_val not in hucre_val:
                    uygun = False
                    break
            if uygun:
                self.filtrelenmis_veriler.append(veri)

        # Sıralama
        if self.siralama_sutun:
            def sort_key(v):
                val = v.get(self.siralama_sutun, '')
                if val is None:
                    return ''
                if isinstance(val, (int, float)):
                    return val
                if isinstance(val, (datetime, date)):
                    return val
                return str(val).lower()

            self.filtrelenmis_veriler.sort(key=sort_key, reverse=self.siralama_ters)

        # Tabloya ekle
        toplam_tutar = 0
        for veri in self.filtrelenmis_veriler:
            tarih = veri.get('Tarih', '')
            if isinstance(tarih, (datetime, date)):
                tarih = tarih.strftime("%d.%m.%Y")

            vade = veri.get('VadeTarihi', '')
            if isinstance(vade, (datetime, date)):
                vade = vade.strftime("%d.%m.%Y")
            elif vade is None:
                vade = ''

            # Sayısal değerler
            etiket = veri.get('EtiketFiyat', 0) or 0
            birim = veri.get('BirimFiyat', 0) or 0
            tutar = veri.get('Tutar', 0) or 0
            maliyet = veri.get('Maliyet', 0) or 0
            isk_kamu = veri.get('IskontoKamu', 0) or 0
            isk_eczane = veri.get('IskontoEczane', 0) or 0
            isk_ticari = veri.get('IskontoTicari', 0) or 0
            fiyat_farki = veri.get('FiyatFarki', 0) or 0
            iskonto = veri.get('Iskonto', 0) or 0
            toplam_tutar += tutar

            values = (
                tarih,
                veri.get('HareketTipi', ''),
                veri.get('Yon', ''),
                veri.get('Ilgili', '') or '',
                veri.get('UrunAdi', ''),
                veri.get('Adet', 0),
                f"{etiket:,.2f}",
                f"{birim:,.2f}",
                f"{tutar:,.2f}",
                f"{maliyet:,.2f}" if maliyet else '',
                veri.get('HastaAdi', '') or '',
                veri.get('DoktorAdi', '') or '',
                veri.get('TesisAdi', '') or '',
                veri.get('KurumAdi', '') or '',
                veri.get('DepoAdi', '') or '',
                veri.get('EczaneAdi', '') or '',
                f"{isk_kamu:.1f}" if isk_kamu else '',
                f"{isk_eczane:.1f}" if isk_eczane else '',
                f"{isk_ticari:.1f}" if isk_ticari else '',
                f"{fiyat_farki:,.2f}" if fiyat_farki else '',
                f"{iskonto:.1f}" if iskonto else '',
                vade,
                veri.get('BelgeNo', '')
            )

            tag = 'giris' if veri.get('Yon') == 'GIRIS' else 'cikis'
            self.tree.insert('', 'end', values=values, tags=(tag,))

        # Durum güncelle
        self.kayit_sayisi_label.config(
            text=f"Kayıt: {len(self.filtrelenmis_veriler)} / {len(self.veriler)}"
        )
        self.toplam_tutar_label.config(text=f"Toplam: {toplam_tutar:,.2f} TL")
        self.status_guncelle(f"{len(self.filtrelenmis_veriler)} kayıt gösteriliyor")

    def filtreleri_temizle(self):
        """Tüm filtreleri temizle"""
        self._hizli_tarih(7)
        self.hareket_tipi.set("Tümü")
        self.yon_filtre.set("Tümü")
        self.urun_ara.delete(0, tk.END)
        self.hasta_ara.delete(0, tk.END)
        self.doktor_ara.delete(0, tk.END)
        self.depo_ara.delete(0, tk.END)
        self.limit_var.set("1000")

        # Sütun filtrelerini temizle
        for entry in self.sutun_filtre_entries.values():
            entry.delete(0, tk.END)
        self.sutun_filtreler.clear()
        self.aktif_filtre_label.config(text="")

        # Sıralamayı sıfırla
        self.siralama_sutun = None
        self.siralama_ters = False
        for col_name, _ in self.columns:
            self.tree.heading(col_name, text=self.column_headers.get(col_name, col_name))

    def excel_aktar(self):
        """Excel'e aktar"""
        veriler = self.filtrelenmis_veriler if self.filtrelenmis_veriler else self.veriler
        if not veriler:
            messagebox.showwarning("Uyarı", "Aktarılacak veri yok!")
            return

        try:
            import csv
            dosya = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Dosyası", "*.csv")],
                initialfilename=f"hareketler_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            )

            if dosya:
                with open(dosya, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f, delimiter=';')
                    writer.writerow([self.column_headers.get(c[0], c[0]) for c in self.columns])

                    for veri in veriler:
                        tarih = veri.get('Tarih', '')
                        if isinstance(tarih, (datetime, date)):
                            tarih = tarih.strftime("%d.%m.%Y")
                        vade = veri.get('VadeTarihi', '')
                        if isinstance(vade, (datetime, date)):
                            vade = vade.strftime("%d.%m.%Y")

                        writer.writerow([
                            tarih, veri.get('HareketTipi', ''), veri.get('Yon', ''),
                            veri.get('Ilgili', '') or '', veri.get('UrunAdi', ''),
                            veri.get('Adet', 0), veri.get('EtiketFiyat', 0) or 0,
                            veri.get('BirimFiyat', 0) or 0, veri.get('Tutar', 0) or 0,
                            veri.get('Maliyet', 0) or 0,
                            veri.get('HastaAdi', '') or '', veri.get('DoktorAdi', '') or '',
                            veri.get('TesisAdi', '') or '', veri.get('KurumAdi', '') or '',
                            veri.get('DepoAdi', '') or '', veri.get('EczaneAdi', '') or '',
                            veri.get('IskontoKamu', 0) or 0, veri.get('IskontoEczane', 0) or 0,
                            veri.get('IskontoTicari', 0) or 0, veri.get('FiyatFarki', 0) or 0,
                            veri.get('Iskonto', 0) or 0, vade, veri.get('BelgeNo', '')
                        ])

                messagebox.showinfo("Başarılı", f"{len(veriler)} kayıt aktarıldı:\n{dosya}")

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
           HAREKET DETAYI
═══════════════════════════════════════

▸ Tarih: {vals[0]}
▸ Hareket Tipi: {vals[1]}
▸ Yön: {vals[2]}
▸ İlgili/Firma: {vals[3]}
▸ Belge No: {vals[22]}

───────────────────────────────────────
ÜRÜN BİLGİLERİ
───────────────────────────────────────
▸ Ürün Adı: {vals[4]}
▸ Adet: {vals[5]}
▸ Etiket Fiyat: {vals[6]} TL
▸ Birim Fiyat: {vals[7]} TL
▸ Tutar: {vals[8]} TL
▸ Maliyet: {vals[9]} TL
▸ Vade Tarihi: {vals[21]}

───────────────────────────────────────
İSKONTO BİLGİLERİ
───────────────────────────────────────
▸ İskonto Kamu: %{vals[16]}
▸ İskonto Eczane: %{vals[17]}
▸ İskonto Ticari: %{vals[18]}
▸ Fiyat Farkı: {vals[19]} TL
▸ İskonto: {vals[20]} TL

───────────────────────────────────────
REÇETE/SATIŞ BİLGİLERİ
───────────────────────────────────────
▸ Hasta Adı: {vals[10]}
▸ Doktor: {vals[11]}
▸ Tesis: {vals[12]}
▸ Kurum: {vals[13]}

───────────────────────────────────────
DEPO/ECZANE BİLGİLERİ
───────────────────────────────────────
▸ Depo: {vals[14]}
▸ Eczane: {vals[15]}
            """
            messagebox.showinfo("Hareket Detayı", detay.strip())

    def status_guncelle(self, mesaj):
        self.status_label.config(text=mesaj)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    pencere = tk.Toplevel(root)
    app = TumHareketlerGUI(pencere)
    root.mainloop()
