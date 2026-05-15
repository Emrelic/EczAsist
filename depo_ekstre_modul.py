#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Botanik Bot - Depo Ekstre Karşılaştırma Modülü
botanik_gui.py'deki ekstre sekmesinin birebir aynısı - bağımsız pencere olarak
Accordion paneller, filtre ayarları, Excel export dahil
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import json
import os
from datetime import datetime
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class DepoEkstreModul:
    """Depo Ekstre Karşılaştırma - botanik_gui.py sekmesiyle birebir aynı"""

    def __init__(self, root: tk.Toplevel = None, ana_menu_callback: Optional[Callable] = None):
        """
        Args:
            root: Tkinter Toplevel penceresi
            ana_menu_callback: Ana menüye dönüş callback'i
        """
        self.ana_menu_callback = ana_menu_callback

        # Root pencere
        if root is None:
            self.root = tk.Tk()
        else:
            self.root = root

        self.root.title("📊 Depo Ekstre Karşılaştırma - Botanik Bot")

        # Pencere boyutları
        pencere_genislik = 800
        pencere_yukseklik = 600

        ekran_genislik = self.root.winfo_screenwidth()
        ekran_yukseklik = self.root.winfo_screenheight()
        x = (ekran_genislik - pencere_genislik) // 2
        y = (ekran_yukseklik - pencere_yukseklik) // 2

        self.root.geometry(f"{pencere_genislik}x{pencere_yukseklik}+{x}+{y}")
        self.root.resizable(True, True)
        self.root.minsize(700, 500)

        # Renkler
        self.bg_color = '#E3F2FD'
        self.root.configure(bg=self.bg_color)

        # Dosya yolları
        self.ekstre_dosya1_path = tk.StringVar(value="")
        self.ekstre_dosya2_path = tk.StringVar(value="")

        # Filtre ayarları
        self.ekstre_filtreler = self._ekstre_filtre_yukle()

        # Depo Excel şablonları (Selçuk varsayılan, Sancak vb. eklenebilir)
        self.depo_sablonlari_data = self._depo_sablon_yukle()
        self.aktif_depo_sablon = tk.StringVar(
            value=self.depo_sablonlari_data.get('aktif_sablon', 'Selçuk Ecza (Varsayılan)')
        )

        # Sonuçlar
        self.ekstre_sonuclar = None

        # Manuel eşleştirme ve iptal için veri listeleri
        self.manuel_eslestirilenler = []  # [(depo_fatura, depo_kayit, eczane_fatura, eczane_kayit), ...]
        self.manuel_iptal_edilenler_depo = []  # [(fatura, kayit), ...]
        self.manuel_iptal_edilenler_eczane = []  # [(fatura, kayit), ...]
        # Manuel eklenenler: tek tarafta olan satırı diğer tarafa da ekleyerek eşleştirme
        # {'orijinal': 'depo'/'eczane', 'fatura': str, 'kayit': dict, 'aciklama': str}
        self.manuel_eklenenler = []
        self.tutar_duzeltme_delta_depo = 0  # Tutar düzeltmelerinin net etkisi
        self.tutar_duzeltme_delta_eczane = 0

        # Seçili satırlar (manuel eşleştirme için - çoklu seçim destekli)
        self.secili_depo_satirlar = []  # [(fatura, kayit), ...]
        self.secili_eczane_satirlar = []  # [(fatura, kayit), ...]
        self._secili_depo_items = []  # treeview item id'leri
        self._secili_eczane_items = []  # treeview item id'leri

        # Sonuç penceresi referansları (güncellemeler için)
        self._sonuc_pencere = None
        self._sonuc_widgets = {}

        # Pencere kapatma
        self.root.protocol("WM_DELETE_WINDOW", self._kapat)

        # Arayüzü oluştur (sekmedeki create_ekstre_tab ile aynı)
        self._arayuz_olustur()

    def _arayuz_olustur(self):
        """Ana arayüzü oluştur - create_ekstre_tab ile birebir aynı"""
        main_frame = tk.Frame(self.root, bg=self.bg_color, padx=10, pady=10)
        main_frame.pack(fill="both", expand=True)

        # Ana Menü butonu (üstte)
        if self.ana_menu_callback:
            nav_frame = tk.Frame(main_frame, bg=self.bg_color)
            nav_frame.pack(fill="x", pady=(0, 10))

            ana_menu_btn = tk.Button(
                nav_frame,
                text="← Ana Menü",
                font=("Arial", 10),
                bg='#455A64',
                fg='white',
                activebackground='#37474F',
                activeforeground='white',
                cursor='hand2',
                bd=0,
                padx=15,
                pady=5,
                command=self._ana_menuye_don
            )
            ana_menu_btn.pack(side="left")

        # Başlık
        title = tk.Label(
            main_frame,
            text="📊 Depo Ekstre Karşılaştırma",
            font=("Arial", 14, "bold"),
            bg=self.bg_color,
            fg='#1565C0'
        )
        title.pack(pady=(5, 2))

        subtitle = tk.Label(
            main_frame,
            text="Depo ekstresi ile Eczane otomasyonunu karşılaştırın",
            font=("Arial", 9),
            bg=self.bg_color,
            fg='#1976D2'
        )
        subtitle.pack(pady=(0, 15))

        # Dosya seçim alanları - yan yana
        files_frame = tk.Frame(main_frame, bg=self.bg_color)
        files_frame.pack(fill="x", pady=5)
        files_frame.columnconfigure(0, weight=1)
        files_frame.columnconfigure(1, weight=1)

        # Dosya 1 - DEPO EKSTRESİ (Sol)
        file1_frame = tk.LabelFrame(
            files_frame,
            text="📁 DEPO EKSTRESİ",
            font=("Arial", 10, "bold"),
            bg='#BBDEFB',
            fg='#0D47A1',
            padx=10,
            pady=10
        )
        file1_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)

        self.drop_area1 = tk.Label(
            file1_frame,
            text="📥 Depo Excel dosyasını\nburaya sürükleyin\nveya tıklayarak seçin",
            font=("Arial", 10),
            bg='#E3F2FD',
            fg='#1565C0',
            relief="groove",
            bd=2,
            height=4,
            cursor="hand2"
        )
        self.drop_area1.pack(fill="x", pady=5)
        self.drop_area1.bind("<Button-1>", lambda e: self.ekstre_dosya_sec(1))

        self.file1_label = tk.Label(
            file1_frame,
            textvariable=self.ekstre_dosya1_path,
            font=("Arial", 8),
            bg='#BBDEFB',
            fg='#0D47A1',
            wraplength=250
        )
        self.file1_label.pack(fill="x")

        # Depo Excel format şablonu seçici
        sablon_row = tk.Frame(file1_frame, bg='#BBDEFB')
        sablon_row.pack(fill="x", pady=(6, 0))
        tk.Label(
            sablon_row, text="📋 Format:", font=("Arial", 8, "bold"),
            bg='#BBDEFB', fg='#0D47A1'
        ).pack(side="left")
        self.depo_sablon_combo = ttk.Combobox(
            sablon_row, textvariable=self.aktif_depo_sablon,
            values=list(self.depo_sablonlari_data.get('sablonlar', {}).keys()),
            state="readonly", font=("Arial", 8), width=24
        )
        self.depo_sablon_combo.pack(side="left", padx=4)
        self.depo_sablon_combo.bind(
            "<<ComboboxSelected>>",
            lambda e: self._depo_sablon_aktif_kaydet()
        )
        tk.Button(
            sablon_row, text="⚙️", font=("Arial", 8), bg='#FF9800', fg='white',
            cursor="hand2", bd=1, padx=4, command=self.depo_sablon_ayarlari_ac
        ).pack(side="left", padx=2)

        # Dosya 2 - ECZANE OTOMASYONU (Sağ)
        file2_frame = tk.LabelFrame(
            files_frame,
            text="📁 ECZANE OTOMASYONU",
            font=("Arial", 10, "bold"),
            bg='#BBDEFB',
            fg='#0D47A1',
            padx=10,
            pady=10
        )
        file2_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)

        self.drop_area2 = tk.Label(
            file2_frame,
            text="📥 Eczane Excel dosyasını\nburaya sürükleyin\nveya tıklayarak seçin",
            font=("Arial", 10),
            bg='#E3F2FD',
            fg='#1565C0',
            relief="groove",
            bd=2,
            height=4,
            cursor="hand2"
        )
        self.drop_area2.pack(fill="x", pady=5)
        self.drop_area2.bind("<Button-1>", lambda e: self.ekstre_dosya_sec(2))

        self.file2_label = tk.Label(
            file2_frame,
            textvariable=self.ekstre_dosya2_path,
            font=("Arial", 8),
            bg='#BBDEFB',
            fg='#0D47A1',
            wraplength=250
        )
        self.file2_label.pack(fill="x")

        # Butonlar ana frame
        button_main_frame = tk.Frame(main_frame, bg=self.bg_color)
        button_main_frame.pack(fill="x", pady=15)

        # Butonları ortalamak için iç frame
        button_center_frame = tk.Frame(button_main_frame, bg=self.bg_color)
        button_center_frame.pack(expand=True)

        # Karşılaştır butonu (büyük, ortada)
        self.karsilastir_btn = tk.Button(
            button_center_frame,
            text="🔍 KARŞILAŞTIR",
            font=("Arial", 14, "bold"),
            bg='#1976D2',
            fg='white',
            width=20,
            height=2,
            cursor="hand2",
            activebackground='#1565C0',
            activeforeground='white',
            relief="raised",
            bd=3,
            command=self._karsilastir_btn_tikla
        )
        self.karsilastir_btn.pack(side="left", padx=10)

        # Ayarlar butonu (yanında, küçük)
        self.ekstre_ayarlar_btn = tk.Button(
            button_center_frame,
            text="⚙️ Filtre\nAyarları",
            font=("Arial", 10, "bold"),
            bg='#FF9800',
            fg='white',
            width=10,
            height=2,
            cursor="hand2",
            activebackground='#F57C00',
            activeforeground='white',
            relief="raised",
            bd=2,
            command=self.ekstre_filtre_ayarlari_ac
        )
        self.ekstre_ayarlar_btn.pack(side="left", padx=10)

        # Aktif filtre bilgisi göster
        self._ekstre_filtre_bilgi_label = tk.Label(
            button_main_frame,
            text="",
            font=("Arial", 9),
            bg=self.bg_color,
            fg='#E65100'
        )
        self._ekstre_filtre_bilgi_label.pack(pady=(5, 0))
        self._ekstre_filtre_bilgi_guncelle()

        # Renk açıklamaları
        legend_frame = tk.LabelFrame(
            main_frame,
            text="🎨 Renk Kodları",
            font=("Arial", 9, "bold"),
            bg=self.bg_color,
            fg='#1565C0',
            padx=10,
            pady=5
        )
        legend_frame.pack(fill="x", pady=10)

        legends = [
            ("🟢 YEŞİL", "Fatura No + Tutar eşleşiyor", "#C8E6C9"),
            ("🟡 SARI", "Tutar eşleşiyor, Fatura No eşleşmiyor", "#FFF9C4"),
            ("🟠 TURUNCU", "Fatura No eşleşiyor, Tutar eşleşmiyor", "#FFE0B2"),
            ("🔴 KIRMIZI", "İkisi de eşleşmiyor", "#FFCDD2"),
        ]

        for text, desc, color in legends:
            row = tk.Frame(legend_frame, bg=self.bg_color)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=text, font=("Arial", 9, "bold"), bg=color, width=12).pack(side="left", padx=5)
            tk.Label(row, text=desc, font=("Arial", 8), bg=self.bg_color, fg='#333').pack(side="left", padx=5)

        # Sürükle-bırak desteği
        self.root.after(100, self._setup_drag_drop)

    def _ekstre_filtre_bilgi_guncelle(self):
        """Aktif filtre sayısını göster"""
        if not hasattr(self, '_ekstre_filtre_bilgi_label'):
            return
        depo_sayisi = sum(len(v) for v in self.ekstre_filtreler.get('depo', {}).values())
        eczane_sayisi = sum(len(v) for v in self.ekstre_filtreler.get('eczane', {}).values())

        if depo_sayisi > 0 or eczane_sayisi > 0:
            text = f"⚠️ Aktif filtre: Depo({depo_sayisi}) | Eczane({eczane_sayisi})"
            self._ekstre_filtre_bilgi_label.config(text=text, fg='#E65100')
        else:
            self._ekstre_filtre_bilgi_label.config(text="✓ Filtre yok - tüm satırlar dahil", fg='#388E3C')

    def _ekstre_filtre_yukle(self):
        """Kaydedilmiş filtre ayarlarını yükle"""
        filtre_dosya = os.path.join(os.path.dirname(__file__), 'ekstre_filtre_ayarlari.json')
        varsayilan = {
            'depo': {},
            'eczane': {},
            'hatirla': True
        }
        try:
            if os.path.exists(filtre_dosya):
                with open(filtre_dosya, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Filtre ayarları yüklenemedi: {e}")
        return varsayilan

    def _ekstre_filtre_kaydet(self):
        """Filtre ayarlarını kaydet"""
        filtre_dosya = os.path.join(os.path.dirname(__file__), 'ekstre_filtre_ayarlari.json')
        try:
            with open(filtre_dosya, 'w', encoding='utf-8') as f:
                json.dump(self.ekstre_filtreler, f, ensure_ascii=False, indent=2)
            logger.info("Filtre ayarları kaydedildi")
        except Exception as e:
            logger.error(f"Filtre ayarları kaydedilemedi: {e}")

    # ========== DEPO EXCEL ŞABLON SİSTEMİ ==========

    def _depo_sablon_dosya_yolu(self):
        return os.path.join(os.path.dirname(__file__), 'depo_excel_sablonlari.json')

    def _depo_sablon_yukle(self):
        """Depo Excel şablonlarını JSON'dan yükle"""
        varsayilan = {
            "aktif_sablon": "Selçuk Ecza (Varsayılan)",
            "sablonlar": {
                "Selçuk Ecza (Varsayılan)": {
                    "aciklama": "Sistem varsayılanı",
                    "header_satir": 0,
                    "veri_baslangic_offset": 0,
                    "sutunlar": {
                        "fatura_no": "Fatura No", "tarih": "Fatura Tarihi",
                        "fatura_tutari": "Fatura Tutarı", "borc": "",
                        "alacak": "İade/Çık Tut", "tip": "Tipi",
                        "aciklama": "İlgili Adı"
                    },
                    "fatura_no_regex": "",
                    "duzenlenebilir": False
                }
            }
        }
        try:
            yol = self._depo_sablon_dosya_yolu()
            if os.path.exists(yol):
                with open(yol, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Depo şablonları yüklenemedi: {e}")
        return varsayilan

    def _depo_sablon_kaydet(self):
        """Şablonları JSON'a kaydet"""
        try:
            with open(self._depo_sablon_dosya_yolu(), 'w', encoding='utf-8') as f:
                json.dump(self.depo_sablonlari_data, f, ensure_ascii=False, indent=2)
            logger.info("Depo şablonları kaydedildi")
        except Exception as e:
            logger.error(f"Depo şablonları kaydedilemedi: {e}")

    def _depo_sablon_aktif_kaydet(self):
        self.depo_sablonlari_data['aktif_sablon'] = self.aktif_depo_sablon.get()
        self._depo_sablon_kaydet()

    def _depo_sablon_combo_yenile(self):
        if hasattr(self, 'depo_sablon_combo'):
            self.depo_sablon_combo['values'] = list(
                self.depo_sablonlari_data.get('sablonlar', {}).keys()
            )

    def _excel_oku_guvenli(self, dosya_yolu, header_satir=0):
        """
        Excel okuma — openpyxl bozuk styles.xml hatasında raw XML fallback.
        Sancak gibi bozuk xlsx dosyalarını da okuyabilir.
        """
        import pandas as pd
        try:
            return pd.read_excel(dosya_yolu, header=header_satir)
        except (TypeError, ValueError) as e:
            logger.warning(f"Standart Excel okuma başarısız ({e}), raw XML fallback deneniyor")
            return self._xlsx_raw_xml_oku(dosya_yolu, header_satir)

    def _xlsx_raw_xml_oku(self, dosya_yolu, header_satir=0):
        """Bozuk xlsx için ham XML parser (inlineStr + sharedStrings desteği)"""
        import zipfile
        import pandas as pd
        from xml.etree import ElementTree as ET

        ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        ns_t = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

        with zipfile.ZipFile(dosya_yolu) as z:
            shared = []
            if 'xl/sharedStrings.xml' in z.namelist():
                ss_root = ET.fromstring(z.read('xl/sharedStrings.xml').decode('utf-8'))
                for si in ss_root.findall(f'{ns_t}si'):
                    shared.append(''.join(t.text or '' for t in si.iter(f'{ns_t}t')))
            sheet_path = next(
                (n for n in z.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')),
                'xl/worksheets/sheet1.xml'
            )
            sheet = ET.fromstring(z.read(sheet_path).decode('utf-8'))

        def col_idx(ref):
            letters = ''.join(c for c in ref if c.isalpha())
            n = 0
            for c in letters:
                n = n * 26 + (ord(c.upper()) - ord('A') + 1)
            return n - 1

        rows = []
        for row in sheet.iter(f'{ns_t}row'):
            row_data = {}
            for c in row.findall(f'{ns_t}c'):
                ref = c.get('r', '')
                t = c.get('t', '')
                val = ''
                if t == 'inlineStr':
                    isn = c.find(f'{ns_t}is')
                    if isn is not None:
                        val = ''.join((tt.text or '') for tt in isn.iter(f'{ns_t}t'))
                elif t == 's':
                    v = c.find(f'{ns_t}v')
                    if v is not None and v.text:
                        try:
                            val = shared[int(v.text)]
                        except Exception:
                            val = v.text
                else:
                    v = c.find(f'{ns_t}v')
                    val = v.text if v is not None else ''
                row_data[col_idx(ref)] = val
            rows.append(row_data)

        if not rows:
            return pd.DataFrame()
        max_col = max((max(r.keys()) for r in rows if r), default=0) + 1
        matrix = [[r.get(i, '') for i in range(max_col)] for r in rows]

        if header_satir >= len(matrix):
            return pd.DataFrame(matrix)
        headers = [str(h) if h not in (None, '') else f'col{i}' for i, h in enumerate(matrix[header_satir])]
        data = matrix[header_satir + 1:]
        df = pd.DataFrame(data, columns=headers)
        # Sayısal kolonları çevir (TR format: 1.234,56 → 1234.56; ASCII format korunur)
        def _sayi_cevir(s):
            s = str(s).strip()
            if not s:
                return s
            if ',' in s:
                # Türkçe sayı: noktalar binlik, virgül ondalık
                s = s.replace('.', '').replace(',', '.')
            try:
                return float(s)
            except Exception:
                return s
        for col in df.columns:
            converted = df[col].apply(_sayi_cevir)
            if converted.apply(lambda x: isinstance(x, float)).any():
                df[col] = converted
        return df

    def _depo_sablon_uygula(self, df, sablon):
        """
        Şablonu DataFrame'e uygular: sütun adlarını sistem alanlarına eşler,
        fatura_no için regex ile çıkarım yapar. Yeni DataFrame döner.
        """
        import pandas as pd
        import re

        sutunlar = sablon.get('sutunlar', {})
        offset = sablon.get('veri_baslangic_offset', 0)
        if offset > 0 and len(df) > offset:
            df = df.iloc[offset:].reset_index(drop=True)

        yeni = pd.DataFrame()
        # Standart sistem alanları → şablonda tanımlanan kaynak sütunları
        alan_map = {
            'fatura_no': 'Fatura No',
            'tarih': 'Tarih',
            'fatura_tutari': 'Fatura Tutarı',
            'borc': 'Borç',
            'alacak': 'İade',
            'tip': 'Tip',
            'aciklama': 'Açıklama',
        }
        for sistem_alan, hedef_kolon in alan_map.items():
            kaynak = sutunlar.get(sistem_alan, '')
            if kaynak and kaynak in df.columns:
                yeni[hedef_kolon] = df[kaynak]
            else:
                # Kaynak tanımsız → NaN bırak; '' verirsek pd.notna True döner ve float('') patlar
                yeni[hedef_kolon] = float('nan')

        # Fatura Tutarı öncelikli; yoksa Borç kullan (eşleştirme tek alan üzerinden gider)
        def _bos_mu(seri):
            try:
                # NaN-only float kolonları: astype(str) NaN'leri string yapmaz, isna() ile yakala
                if seri.isna().all():
                    return True
                return seri.fillna('').astype(str).str.strip().replace('nan', '').eq('').all()
            except Exception:
                return True
        if _bos_mu(yeni['Fatura Tutarı']) and not _bos_mu(yeni['Borç']):
            yeni['Fatura Tutarı'] = yeni['Borç']

        # Fatura no regex çıkarımı (Sancak: Açıklama'dan kod)
        regex = sablon.get('fatura_no_regex', '')
        if regex:
            try:
                pat = re.compile(regex)
                yeni['Fatura No'] = yeni['Fatura No'].astype(str).apply(
                    lambda s: (pat.search(s).group(1) if pat.search(s) and pat.search(s).groups()
                               else (pat.search(s).group(0) if pat.search(s) else s))
                )
            except Exception as e:
                logger.error(f"Fatura no regex hatası: {e}")
        return yeni

    def depo_sablon_ayarlari_ac(self):
        """Depo Excel şablon yönetim penceresi"""
        pencere = tk.Toplevel(self.root)
        pencere.title("📋 Depo Excel Format Şablonları")
        pencere.geometry("700x500")
        pencere.configure(bg='#ECEFF1')

        tk.Label(
            pencere, text="📋 Depo Excel Format Şablonları",
            font=("Arial", 13, "bold"), bg='#ECEFF1', fg='#1565C0'
        ).pack(pady=10)
        tk.Label(
            pencere,
            text="Farklı depoların Excel formatlarını şablon olarak kaydedip kullanabilirsiniz.",
            font=("Arial", 9), bg='#ECEFF1', fg='#37474F'
        ).pack(pady=(0, 10))

        list_frame = tk.Frame(pencere, bg='#ECEFF1')
        list_frame.pack(fill="both", expand=True, padx=20, pady=5)

        listbox = tk.Listbox(list_frame, font=("Arial", 10), height=10)
        listbox.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(list_frame, command=listbox.yview)
        sb.pack(side="right", fill="y")
        listbox.config(yscrollcommand=sb.set)

        def listele():
            listbox.delete(0, tk.END)
            for ad in self.depo_sablonlari_data.get('sablonlar', {}).keys():
                isaret = "★ " if ad == self.aktif_depo_sablon.get() else "   "
                listbox.insert(tk.END, f"{isaret}{ad}")
        listele()

        def secili_ad():
            sel = listbox.curselection()
            if not sel:
                return None
            return listbox.get(sel[0]).replace("★ ", "").strip()

        def yeni_sablon():
            self._sablon_duzenle_pencere(None, listele)

        def duzenle():
            ad = secili_ad()
            if not ad:
                messagebox.showinfo("Bilgi", "Önce bir şablon seçin")
                return
            self._sablon_duzenle_pencere(ad, listele)

        def sil():
            ad = secili_ad()
            if not ad:
                return
            sablon = self.depo_sablonlari_data['sablonlar'].get(ad, {})
            if not sablon.get('duzenlenebilir', True):
                messagebox.showwarning("Uyarı", f"'{ad}' varsayılan şablondur, silinemez.")
                return
            if messagebox.askyesno("Sil", f"'{ad}' şablonunu silmek istiyor musunuz?"):
                del self.depo_sablonlari_data['sablonlar'][ad]
                if self.aktif_depo_sablon.get() == ad:
                    self.aktif_depo_sablon.set("Selçuk Ecza (Varsayılan)")
                self._depo_sablon_kaydet()
                self._depo_sablon_combo_yenile()
                listele()

        def aktif_yap():
            ad = secili_ad()
            if not ad:
                return
            self.aktif_depo_sablon.set(ad)
            self._depo_sablon_aktif_kaydet()
            listele()

        btn_frame = tk.Frame(pencere, bg='#ECEFF1')
        btn_frame.pack(fill="x", padx=20, pady=10)
        for txt, cmd, color in [
            ("➕ Yeni Şablon", yeni_sablon, '#388E3C'),
            ("✏️ Düzenle", duzenle, '#1976D2'),
            ("⭐ Aktif Yap", aktif_yap, '#F57C00'),
            ("🗑️ Sil", sil, '#D32F2F'),
            ("Kapat", pencere.destroy, '#455A64'),
        ]:
            tk.Button(btn_frame, text=txt, command=cmd, font=("Arial", 9, "bold"),
                      bg=color, fg='white', padx=10, pady=5, cursor="hand2"
                      ).pack(side="left", padx=4)

    def _sablon_duzenle_pencere(self, sablon_adi, refresh_callback):
        """Şablon ekleme/düzenleme penceresi — örnek Excel'den sütun seçimi"""
        import pandas as pd

        is_yeni = sablon_adi is None
        mevcut = {} if is_yeni else self.depo_sablonlari_data['sablonlar'].get(sablon_adi, {})

        win = tk.Toplevel(self.root)
        win.title(f"{'Yeni' if is_yeni else 'Düzenle'} — Depo Excel Şablonu")
        win.geometry("650x600")
        win.configure(bg='#FAFAFA')

        # Şablon adı
        tk.Label(win, text="Şablon Adı:", font=("Arial", 10, "bold"),
                 bg='#FAFAFA').pack(anchor="w", padx=15, pady=(10, 2))
        ad_var = tk.StringVar(value=sablon_adi or "")
        tk.Entry(win, textvariable=ad_var, font=("Arial", 10), width=50
                 ).pack(anchor="w", padx=15)

        # Header satır numarası
        hr_frame = tk.Frame(win, bg='#FAFAFA')
        hr_frame.pack(anchor="w", padx=15, pady=(10, 2), fill="x")
        tk.Label(hr_frame, text="Başlık satırı (0=ilk satır):",
                 font=("Arial", 10, "bold"), bg='#FAFAFA').pack(side="left")
        header_var = tk.IntVar(value=mevcut.get('header_satir', 0))
        tk.Spinbox(hr_frame, from_=0, to=20, textvariable=header_var,
                   width=5, font=("Arial", 10)).pack(side="left", padx=5)

        offset_frame = tk.Frame(win, bg='#FAFAFA')
        offset_frame.pack(anchor="w", padx=15, pady=2, fill="x")
        tk.Label(offset_frame, text="Veri başlangıç offset (atlanacak satır):",
                 font=("Arial", 10, "bold"), bg='#FAFAFA').pack(side="left")
        offset_var = tk.IntVar(value=mevcut.get('veri_baslangic_offset', 0))
        tk.Spinbox(offset_frame, from_=0, to=20, textvariable=offset_var,
                   width=5, font=("Arial", 10)).pack(side="left", padx=5)

        # Örnek Excel yükleme + sütun listesi
        kolon_listesi = tk.StringVar(value="(Örnek Excel yükleyin)")
        sutunlar_state = {'liste': []}

        # Sistem alanları için combobox'lar
        sis_frame = tk.LabelFrame(
            win, text="🔗 Sistem Alanı → Excel Sütunu Eşlemesi",
            font=("Arial", 10, "bold"), bg='#FAFAFA', fg='#1565C0', padx=10, pady=10
        )
        sis_frame.pack(fill="x", padx=15, pady=10)

        alan_widgets = {}
        sistem_alanlari = [
            ('fatura_no', 'Fatura No (zorunlu)'),
            ('tarih', 'Fatura Tarihi'),
            ('fatura_tutari', 'Fatura Tutarı'),
            ('borc', 'Borç'),
            ('alacak', 'Alacak / İade'),
            ('tip', 'İşlem Tipi / Tür'),
            ('aciklama', 'Açıklama'),
        ]
        mevcut_sutunlar = mevcut.get('sutunlar', {})
        for i, (alan, etiket) in enumerate(sistem_alanlari):
            tk.Label(sis_frame, text=etiket + ":", font=("Arial", 9),
                     bg='#FAFAFA').grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar(value=mevcut_sutunlar.get(alan, ''))
            cb = ttk.Combobox(sis_frame, textvariable=v, width=35,
                              font=("Arial", 9))
            cb.grid(row=i, column=1, sticky="w", padx=8, pady=3)
            alan_widgets[alan] = (v, cb)

        # Fatura no regex
        rg_frame = tk.Frame(win, bg='#FAFAFA')
        rg_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(rg_frame, text="Fatura No Regex (boş = sütunu olduğu gibi al):",
                 font=("Arial", 9, "bold"), bg='#FAFAFA').pack(anchor="w")
        regex_var = tk.StringVar(value=mevcut.get('fatura_no_regex', ''))
        tk.Entry(rg_frame, textvariable=regex_var, font=("Consolas", 9),
                 width=60).pack(anchor="w", pady=2)
        tk.Label(rg_frame,
                 text='Örn: ^([A-Za-z0-9]+)  →  "SNC2026000106127-ECZ..." → "SNC2026000106127"',
                 font=("Arial", 8), bg='#FAFAFA', fg='#666').pack(anchor="w")

        def ornek_yukle():
            yol = filedialog.askopenfilename(
                title="Örnek Excel Seç",
                filetypes=[("Excel", "*.xlsx *.xls")]
            )
            if not yol:
                return
            try:
                df = self._excel_oku_guvenli(yol, header_satir=header_var.get())
                kolonlar = [str(c) for c in df.columns]
                sutunlar_state['liste'] = kolonlar
                kolon_listesi.set(f"✓ {len(kolonlar)} sütun bulundu: " + ", ".join(kolonlar[:6]) + ("..." if len(kolonlar) > 6 else ""))
                for v, cb in alan_widgets.values():
                    cb['values'] = [''] + kolonlar
            except Exception as e:
                messagebox.showerror("Hata", f"Excel okunamadı: {e}")

        oy_frame = tk.Frame(win, bg='#FAFAFA')
        oy_frame.pack(fill="x", padx=15, pady=5)
        tk.Button(oy_frame, text="📂 Örnek Excel Yükle (sütun adlarını çek)",
                  command=ornek_yukle, font=("Arial", 9, "bold"),
                  bg='#1976D2', fg='white', cursor="hand2", padx=10, pady=4
                  ).pack(side="left")
        tk.Label(oy_frame, textvariable=kolon_listesi, font=("Arial", 8),
                 bg='#FAFAFA', fg='#388E3C', wraplength=400, justify="left"
                 ).pack(side="left", padx=10)

        def kaydet():
            yeni_ad = ad_var.get().strip()
            if not yeni_ad:
                messagebox.showwarning("Uyarı", "Şablon adı boş olamaz")
                return
            if not alan_widgets['fatura_no'][0].get():
                messagebox.showwarning("Uyarı", "Fatura No sütunu zorunludur")
                return
            yeni_sablon = {
                "aciklama": mevcut.get('aciklama', ''),
                "header_satir": header_var.get(),
                "veri_baslangic_offset": offset_var.get(),
                "sutunlar": {alan: v.get() for alan, (v, _) in alan_widgets.items()},
                "fatura_no_regex": regex_var.get(),
                "duzenlenebilir": True
            }
            # Eski adı sil (yeniden adlandırma)
            if not is_yeni and yeni_ad != sablon_adi:
                self.depo_sablonlari_data['sablonlar'].pop(sablon_adi, None)
            self.depo_sablonlari_data['sablonlar'][yeni_ad] = yeni_sablon
            self._depo_sablon_kaydet()
            self._depo_sablon_combo_yenile()
            if refresh_callback:
                refresh_callback()
            messagebox.showinfo("Kaydedildi", f"'{yeni_ad}' şablonu kaydedildi")
            win.destroy()

        btn_frame = tk.Frame(win, bg='#FAFAFA')
        btn_frame.pack(side="bottom", fill="x", padx=15, pady=10)
        tk.Button(btn_frame, text="💾 Kaydet", command=kaydet,
                  font=("Arial", 10, "bold"), bg='#388E3C', fg='white',
                  padx=20, pady=6, cursor="hand2").pack(side="right", padx=5)
        tk.Button(btn_frame, text="İptal", command=win.destroy,
                  font=("Arial", 10), bg='#757575', fg='white',
                  padx=15, pady=6, cursor="hand2").pack(side="right")

    # ========== /DEPO EXCEL ŞABLON SİSTEMİ ==========

    def ekstre_filtre_ayarlari_ac(self):
        """Filtre ayarları penceresini aç"""
        import pandas as pd

        dosya1 = self.ekstre_dosya1_path.get()
        dosya2 = self.ekstre_dosya2_path.get()

        if not dosya1 and not dosya2:
            messagebox.showinfo("Bilgi", "Önce en az bir Excel dosyası yükleyin.\nBöylece sütunları ve değerleri görebilirsiniz.")
            return

        ayar_pencere = tk.Toplevel(self.root)
        ayar_pencere.title("⚙️ Ekstre Filtre Ayarları")
        ayar_pencere.geometry("800x600")
        ayar_pencere.configure(bg='#ECEFF1')
        ayar_pencere.transient(self.root)
        ayar_pencere.grab_set()

        ayar_pencere.update_idletasks()
        x = (ayar_pencere.winfo_screenwidth() - 800) // 2
        y = (ayar_pencere.winfo_screenheight() - 600) // 2
        ayar_pencere.geometry(f"800x600+{x}+{y}")

        main_frame = tk.Frame(ayar_pencere, bg='#ECEFF1')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(
            main_frame,
            text="⚙️ Satır Filtreleme Ayarları",
            font=("Arial", 14, "bold"),
            bg='#ECEFF1',
            fg='#1565C0'
        ).pack(pady=(0, 5))

        tk.Label(
            main_frame,
            text="İşaretlenen değerlere sahip satırlar karşılaştırmada dikkate alınmayacak",
            font=("Arial", 9),
            bg='#ECEFF1',
            fg='#666'
        ).pack(pady=(0, 10))

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True, pady=5)

        self._filtre_checkboxes = {'depo': {}, 'eczane': {}}

        if dosya1:
            depo_frame = tk.Frame(notebook, bg='#E3F2FD')
            notebook.add(depo_frame, text="📦 DEPO EKSTRESİ")
            self._filtre_sekme_olustur(depo_frame, dosya1, 'depo')

        if dosya2:
            eczane_frame = tk.Frame(notebook, bg='#E8F5E9')
            notebook.add(eczane_frame, text="🏪 ECZANE OTOMASYONU")
            self._filtre_sekme_olustur(eczane_frame, dosya2, 'eczane')

        btn_frame = tk.Frame(main_frame, bg='#ECEFF1')
        btn_frame.pack(fill="x", pady=10)

        self._hatirla_var = tk.BooleanVar(value=self.ekstre_filtreler.get('hatirla', True))
        tk.Checkbutton(
            btn_frame,
            text="Ayarları hatırla",
            variable=self._hatirla_var,
            bg='#ECEFF1',
            font=("Arial", 10)
        ).pack(side="left", padx=10)

        tk.Button(
            btn_frame,
            text="💾 Kaydet ve Kapat",
            font=("Arial", 11, "bold"),
            bg='#4CAF50',
            fg='white',
            width=18,
            cursor="hand2",
            command=lambda: self._filtre_kaydet_ve_kapat(ayar_pencere)
        ).pack(side="right", padx=5)

        tk.Button(
            btn_frame,
            text="❌ İptal",
            font=("Arial", 10),
            bg='#f44336',
            fg='white',
            width=10,
            cursor="hand2",
            command=ayar_pencere.destroy
        ).pack(side="right", padx=5)

        tk.Button(
            btn_frame,
            text="🗑️ Tümünü Temizle",
            font=("Arial", 10),
            bg='#FF9800',
            fg='white',
            width=14,
            cursor="hand2",
            command=self._filtre_tumunu_temizle
        ).pack(side="right", padx=5)

    def _filtre_sekme_olustur(self, parent, dosya_yolu, kaynak):
        """Bir Excel dosyası için filtre sekmesi oluştur"""
        import pandas as pd

        try:
            df = pd.read_excel(dosya_yolu)
        except Exception as e:
            tk.Label(parent, text=f"Dosya okunamadı: {e}", bg='#FFCDD2').pack(pady=20)
            return

        canvas = tk.Canvas(parent, bg=parent.cget('bg'), highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=parent.cget('bg'))

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        mevcut_filtreler = self.ekstre_filtreler.get(kaynak, {})

        for col in df.columns:
            benzersiz = df[col].dropna().astype(str).unique()
            benzersiz = sorted([v for v in benzersiz if v and v != 'nan'])

            if len(benzersiz) == 0 or len(benzersiz) > 50:
                continue

            col_frame = tk.LabelFrame(
                scroll_frame,
                text=f"📋 {col} ({len(benzersiz)} değer)",
                font=("Arial", 10, "bold"),
                bg=parent.cget('bg'),
                padx=5,
                pady=5
            )
            col_frame.pack(fill="x", padx=5, pady=5)

            self._filtre_checkboxes[kaynak][col] = {}
            secili_degerler = mevcut_filtreler.get(col, [])

            row_frame = None
            for i, deger in enumerate(benzersiz):
                if i % 4 == 0:
                    row_frame = tk.Frame(col_frame, bg=parent.cget('bg'))
                    row_frame.pack(fill="x", pady=1)

                var = tk.BooleanVar(value=(deger in secili_degerler))
                self._filtre_checkboxes[kaynak][col][deger] = var

                cb = tk.Checkbutton(
                    row_frame,
                    text=deger[:25] + "..." if len(deger) > 25 else deger,
                    variable=var,
                    bg=parent.cget('bg'),
                    font=("Arial", 9),
                    anchor="w",
                    width=20
                )
                cb.pack(side="left", padx=2)

    def _filtre_kaydet_ve_kapat(self, pencere):
        """Filtre ayarlarını kaydet ve pencereyi kapat"""
        for kaynak in ['depo', 'eczane']:
            self.ekstre_filtreler[kaynak] = {}
            if kaynak in self._filtre_checkboxes:
                for col, degerler in self._filtre_checkboxes[kaynak].items():
                    secili = [d for d, var in degerler.items() if var.get()]
                    if secili:
                        self.ekstre_filtreler[kaynak][col] = secili

        self.ekstre_filtreler['hatirla'] = self._hatirla_var.get()

        if self._hatirla_var.get():
            self._ekstre_filtre_kaydet()

        depo_filtre_sayisi = sum(len(v) for v in self.ekstre_filtreler.get('depo', {}).values())
        eczane_filtre_sayisi = sum(len(v) for v in self.ekstre_filtreler.get('eczane', {}).values())

        if depo_filtre_sayisi > 0 or eczane_filtre_sayisi > 0:
            messagebox.showinfo(
                "Filtreler Kaydedildi",
                f"Depo: {depo_filtre_sayisi} değer filtrelenecek\n"
                f"Eczane: {eczane_filtre_sayisi} değer filtrelenecek"
            )

        self._ekstre_filtre_bilgi_guncelle()
        pencere.destroy()

    def _filtre_tumunu_temizle(self):
        """Tüm filtreleri temizle"""
        for kaynak in ['depo', 'eczane']:
            if kaynak in self._filtre_checkboxes:
                for col, degerler in self._filtre_checkboxes[kaynak].items():
                    for var in degerler.values():
                        var.set(False)

    def _setup_drag_drop(self):
        """Sürükle-bırak desteğini ayarla - her alan için ayrı"""
        try:
            import windnd

            def decode_file_path(raw):
                """Dosya yolunu decode et"""
                if isinstance(raw, bytes):
                    for encoding in ['cp1254', 'utf-8', 'latin-1', 'cp1252']:
                        try:
                            return raw.decode(encoding)
                        except UnicodeDecodeError:
                            continue
                    return raw.decode('utf-8', errors='replace')
                return raw

            def validate_excel(file_path):
                """Excel dosyası mı kontrol et"""
                if not file_path.lower().endswith(('.xlsx', '.xls')):
                    messagebox.showwarning("Uyarı", "Lütfen Excel dosyası (.xlsx, .xls) seçin!")
                    return False
                return True

            def _lift_self():
                # Drop sonrası Windows focus'u Explorer/ana_menu'ye veriyor — modül penceresini geri öne al
                try:
                    self.root.lift()
                    self.root.focus_force()
                    self.root.attributes('-topmost', True)
                    self.root.after(200, lambda: self.root.attributes('-topmost', False))
                except Exception:
                    pass

            # DEPO alanı için drop handler
            def handle_drop_depo(files):
                if not files:
                    _lift_self()
                    return
                try:
                    file_path = decode_file_path(files[0])
                    if validate_excel(file_path):
                        self.ekstre_dosya1_path.set(file_path)
                        self.drop_area1.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                except Exception as e:
                    logger.error(f"Depo drop hatası: {e}")
                finally:
                    _lift_self()

            # ECZANE alanı için drop handler
            def handle_drop_eczane(files):
                if not files:
                    _lift_self()
                    return
                try:
                    file_path = decode_file_path(files[0])
                    if validate_excel(file_path):
                        self.ekstre_dosya2_path.set(file_path)
                        self.drop_area2.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                except Exception as e:
                    logger.error(f"Eczane drop hatası: {e}")
                finally:
                    _lift_self()

            # Her alan için ayrı hook
            windnd.hook_dropfiles(self.drop_area1, func=handle_drop_depo)
            windnd.hook_dropfiles(self.drop_area2, func=handle_drop_eczane)
            logger.info("Sürükle-bırak desteği aktif (alan bazlı)")
        except ImportError:
            logger.info("windnd bulunamadı - sürükle-bırak için tıklama kullanılacak")
        except Exception as e:
            logger.error(f"Sürükle-bırak kurulumu hatası: {e}")

    def ekstre_dosya_sec(self, dosya_no):
        """Dosya seçme dialogu aç"""
        dosya_yolu = filedialog.askopenfilename(
            title=f"{'Depo Ekstresi' if dosya_no == 1 else 'Eczane Otomasyonu'} Seçin",
            filetypes=[
                ("Excel Dosyaları", "*.xlsx *.xls"),
                ("Tüm Dosyalar", "*.*")
            ]
        )
        if dosya_yolu:
            if dosya_no == 1:
                self.ekstre_dosya1_path.set(dosya_yolu)
                self.drop_area1.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
            else:
                self.ekstre_dosya2_path.set(dosya_yolu)
                self.drop_area2.config(text="✅ Dosya yüklendi", bg='#C8E6C9')

    def _diag_log(self, mesaj):
        """Her durumda depo_ekstre_hata.log'a yaz — tanı için"""
        try:
            log_yolu = os.path.join(os.path.dirname(__file__), "depo_ekstre_hata.log")
            with open(log_yolu, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} {mesaj}\n")
        except Exception:
            pass

    def _karsilastir_btn_tikla(self):
        """KARŞILAŞTIR butonu wrapper — basıldığında görsel + log onayı verir, sonra normal akışı başlatır"""
        self._diag_log("[BUTON] KARŞILAŞTIR tıklandı ✓")
        try:
            self.ekstre_karsilastir_pencere_ac()
        except Exception as e:
            import traceback
            self._diag_log(f"[BUTON] wrapper-dışı HATA: {e}\n{traceback.format_exc()}")
            messagebox.showerror("Hata", f"Karşılaştırma çağrısı patladı:\n{e}")

    def ekstre_karsilastir_pencere_ac(self):
        """Büyük karşılaştırma penceresini aç"""
        import pandas as pd

        self._diag_log("="*60)
        self._diag_log("[karsilastir] GİRİŞ")

        dosya1 = self.ekstre_dosya1_path.get()
        dosya2 = self.ekstre_dosya2_path.get()
        self._diag_log(f"[karsilastir] dosya1='{dosya1}'")
        self._diag_log(f"[karsilastir] dosya2='{dosya2}'")

        if not dosya1 or not dosya2:
            self._diag_log("[karsilastir] DOSYA EKSİK — uyarı gösteriliyor")
            messagebox.showwarning("Uyarı", "Lütfen her iki Excel dosyasını da seçin!")
            return

        try:
            # Aktif depo şablonunu uygula
            sablon_adi = self.aktif_depo_sablon.get()
            sablon = self.depo_sablonlari_data.get('sablonlar', {}).get(sablon_adi, {})
            header_satir = sablon.get('header_satir', 0)
            self._diag_log(f"[karsilastir] aktif_sablon='{sablon_adi}' header_satir={header_satir}")
            self._diag_log(f"[karsilastir] sablon.sutunlar={sablon.get('sutunlar', {})}")

            df_depo_raw = self._excel_oku_guvenli(dosya1, header_satir=header_satir)
            self._diag_log(f"[karsilastir] DEPO ham kolonlar: {list(df_depo_raw.columns)}")
            self._diag_log(f"[karsilastir] DEPO ham satır: {len(df_depo_raw)}")

            if sablon and sablon.get('sutunlar'):
                df_depo = self._depo_sablon_uygula(df_depo_raw, sablon)
                logger.info(f"Depo şablonu uygulandı: '{sablon_adi}' (header={header_satir})")
                self._diag_log(f"[karsilastir] DEPO şablon-sonrası kolonlar: {list(df_depo.columns)}")
                self._diag_log(f"[karsilastir] DEPO şablon-sonrası satır: {len(df_depo)}")
            else:
                df_depo = df_depo_raw
                self._diag_log("[karsilastir] DEPO şablonsuz (sutunlar tanımsız)")

            df_eczane = pd.read_excel(dosya2)
            self._diag_log(f"[karsilastir] ECZANE kolonlar: {list(df_eczane.columns)}")
            self._diag_log(f"[karsilastir] ECZANE satır: {len(df_eczane)}")

            self._diag_log("[karsilastir] _ekstre_sonuc_penceresi_olustur çağrılıyor")
            self._ekstre_sonuc_penceresi_olustur(df_depo, df_eczane, dosya1, dosya2)
            self._diag_log("[karsilastir] BAŞARILI — sonuç penceresi açıldı")

        except PermissionError as e:
            dosya_adi = dosya1 if 'DEPO' in str(e).upper() else dosya2
            dosya_adi = dosya_adi.split('\\')[-1] if '\\' in dosya_adi else dosya_adi.split('/')[-1]
            messagebox.showerror(
                "Dosya Erişim Hatası",
                f"❌ Dosya okunamıyor: {dosya_adi}\n\n"
                f"Muhtemel sebepler:\n"
                f"• Dosya şu anda Excel'de açık durumda\n"
                f"• Dosya başka bir program tarafından kullanılıyor\n\n"
                f"✅ Çözüm: Excel dosyasını kapatın ve tekrar deneyin"
            )
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self._diag_log(f"[karsilastir] HATA: {e}")
            self._diag_log(f"[karsilastir] traceback:\n{tb_str}")
            # Sonuç penceresi yarı yolda kaldıysa kapat — yoksa altında messagebox saklanır, GUI donmuş görünür
            if getattr(self, '_sonuc_pencere', None) is not None:
                try:
                    self._sonuc_pencere.destroy()
                except Exception:
                    pass
                self._sonuc_pencere = None
            messagebox.showerror("Hata", f"Dosya okuma hatası:\n\n{str(e)}\n\nDetay: depo_ekstre_hata.log")
            logger.error(f"Ekstre dosya okuma hatası: {e}", exc_info=True)

    def _ekstre_sonuc_penceresi_olustur(self, df_depo, df_eczane, dosya1_yol, dosya2_yol):
        """Büyük karşılaştırma sonuç penceresi - ACCORDION PANELLER İLE"""
        import pandas as pd

        pencere = tk.Toplevel(self.root)
        pencere.title("📊 Depo Ekstre Karşılaştırma Sonuçları")
        pencere.configure(bg='#ECEFF1')

        window_width = 1000
        window_height = 800

        screen_width = pencere.winfo_screenwidth()
        screen_height = pencere.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        pencere.geometry(f"{window_width}x{window_height}+{x}+{y}")
        pencere.minsize(950, 700)

        # Pencere referansını sakla
        self._sonuc_pencere = pencere

        # Manuel işlem listelerini temizle (yeni karşılaştırma için)
        self.manuel_eslestirilenler = []
        self.manuel_iptal_edilenler_depo = []
        self.manuel_iptal_edilenler_eczane = []
        self.manuel_eklenenler = []
        self.tutar_duzeltme_delta_depo = 0
        self.tutar_duzeltme_delta_eczane = 0
        self.secili_depo_satirlar = []
        self.secili_eczane_satirlar = []
        self._secili_depo_items = []
        self._secili_eczane_items = []
        self._sonuc_widgets = {}

        # Sütun eşleştirmeleri
        depo_fatura_col = self._bul_sutun(df_depo, [
            'Evrak No', 'EvrakNo', 'EVRAK NO', 'Fatura No', 'FaturaNo', 'FATURA NO',
            'Belge No', 'BelgeNo', 'BELGE NO', 'Fiş No', 'FişNo', 'FİŞ NO'
        ])
        depo_borc_col = self._bul_sutun(df_depo, [
            'Borc', 'Borç', 'BORC', 'BORÇ', 'Tutar', 'TUTAR',
            'Borç Tutar', 'BorçTutar', 'BORÇ TUTAR', 'Toplam', 'TOPLAM',
            'Fatura Tutarı', 'FaturaTutarı', 'FATURA TUTARI', 'Net Tutar', 'NET TUTAR'
        ])
        depo_alacak_col = self._bul_sutun(df_depo, [
            'Alacak', 'ALACAK', 'Alacak Tutar', 'AlacakTutar', 'ALACAK TUTAR',
            'İade', 'IADE', 'İade Tutar', 'İadeTutar', 'İADE TUTAR',
            'Çıkış', 'ÇIKIŞ', 'Çıkış Tutar', 'ÇıkışTutar', 'ÇIKIŞ TUTAR',
            'Cikis', 'CIKIS', 'Cıkış', 'CIKIŞ'
        ])

        eczane_fatura_col = self._bul_sutun(df_eczane, [
            'Fatura No', 'FaturaNo', 'FATURA NO', 'Evrak No', 'EvrakNo', 'EVRAK NO',
            'Belge No', 'BelgeNo', 'BELGE NO', 'Fiş No', 'FişNo', 'FİŞ NO'
        ])
        eczane_borc_col = self._bul_sutun(df_eczane, [
            'Fatura Tutarı', 'FaturaTutarı', 'FATURA TUTARI', 'Fatura Tutar',
            'Tutar', 'TUTAR', 'Borç', 'Borc', 'BORÇ', 'BORC',
            'Toplam', 'TOPLAM', 'Net Tutar', 'NET TUTAR', 'Toplam Tutar', 'TOPLAM TUTAR'
        ])
        eczane_alacak_col = self._bul_sutun(df_eczane, [
            'İade/Çık Tut', 'Iade/Cik Tut', 'İade Tutarı', 'İade/Çıkış Tut',
            'İade', 'IADE', 'İade Tutar', 'İadeTutar', 'İADE TUTAR', 'Alacak', 'ALACAK',
            'Çıkış', 'ÇIKIŞ', 'Çıkış Tutar', 'ÇıkışTutar', 'ÇIKIŞ TUTAR',
            'Cikis', 'CIKIS', 'Cıkış', 'CIKIŞ'
        ])

        depo_tarih_col = self._bul_sutun(df_depo, [
            'Tarih', 'TARİH', 'Fatura Tarihi', 'FaturaTarihi', 'FATURA TARİHİ',
            'Evrak Tarihi', 'EvrakTarihi', 'EVRAK TARİHİ', 'İşlem Tarihi', 'İşlemTarihi'
        ])
        eczane_tarih_col = self._bul_sutun(df_eczane, [
            'Tarih', 'TARİH', 'Fatura Tarihi', 'FaturaTarihi', 'FATURA TARİHİ',
            'Evrak Tarihi', 'EvrakTarihi', 'EVRAK TARİHİ', 'İşlem Tarihi', 'İşlemTarihi'
        ])

        depo_tip_col = self._bul_sutun(df_depo, [
            'Tip', 'TİP', 'Tür', 'TÜR', 'İşlem Tipi', 'İşlemTipi', 'İŞLEM TİPİ',
            'Fiş Tipi', 'FişTipi', 'FİŞ TİPİ', 'Evrak Tipi', 'EvrakTipi'
        ])
        eczane_tip_col = self._bul_sutun(df_eczane, [
            'Tip', 'TİP', 'Tür', 'TÜR', 'İşlem Tipi', 'İşlemTipi', 'İŞLEM TİPİ',
            'Fiş Tipi', 'FişTipi', 'FİŞ TİPİ', 'Evrak Tipi', 'EvrakTipi'
        ])

        # Sütun kontrolü ve bilgi
        logger.info(f"DEPO sütunları: Fatura={depo_fatura_col}, Borç={depo_borc_col}, Alacak={depo_alacak_col}")
        logger.info(f"ECZANE sütunları: Fatura={eczane_fatura_col}, Borç={eczane_borc_col}, Alacak={eczane_alacak_col}")
        self._diag_log(f"[sonuc_pencere] DEPO eşleme: Fatura={depo_fatura_col} Borç={depo_borc_col} Alacak={depo_alacak_col} Tarih={depo_tarih_col} Tip={depo_tip_col}")
        self._diag_log(f"[sonuc_pencere] ECZANE eşleme: Fatura={eczane_fatura_col} Borç={eczane_borc_col} Alacak={eczane_alacak_col} Tarih={eczane_tarih_col} Tip={eczane_tip_col}")

        hatalar = []
        if not depo_fatura_col:
            hatalar.append(f"DEPO'da Fatura No sütunu bulunamadı.\nMevcut sütunlar: {', '.join(df_depo.columns)}")
        if not depo_borc_col:
            hatalar.append(f"DEPO'da Borç/Tutar sütunu bulunamadı.\nMevcut sütunlar: {', '.join(df_depo.columns)}")
        if not eczane_fatura_col:
            hatalar.append(f"ECZANE'de Fatura No sütunu bulunamadı.\nMevcut sütunlar: {', '.join(df_eczane.columns)}")
        if not eczane_borc_col:
            hatalar.append(f"ECZANE'de Fatura Tutarı sütunu bulunamadı.\nMevcut sütunlar: {', '.join(df_eczane.columns)}")

        # Alacak sütunu bulunamadıysa uyarı
        if not depo_alacak_col:
            logger.warning(f"DEPO'da Alacak/Çıkış sütunu bulunamadı. Çıkış faturaları 0 tutar gösterebilir. Mevcut sütunlar: {list(df_depo.columns)}")
        if not eczane_alacak_col:
            logger.warning(f"ECZANE'de Alacak/Çıkış sütunu bulunamadı. Çıkış faturaları 0 tutar gösterebilir. Mevcut sütunlar: {list(df_eczane.columns)}")

        if hatalar:
            self._diag_log(f"[sonuc_pencere] SÜTUN HATALARI: {hatalar}")
            messagebox.showerror("Sütun Bulunamadı", "\n\n".join(hatalar))
            if not depo_fatura_col or not eczane_fatura_col:
                pencere.destroy()
                self._sonuc_pencere = None
                return

        # Filtre fonksiyonu
        def satir_filtreli_mi(row, kaynak):
            filtreler = self.ekstre_filtreler.get(kaynak, {})
            for col, degerler in filtreler.items():
                if col in row.index:
                    satir_degeri = str(row[col]).strip() if pd.notna(row[col]) else ""
                    if satir_degeri in degerler:
                        return True
            return False

        depo_filtreli = 0
        eczane_filtreli = 0
        filtrelenen_depo_satirlar = []
        filtrelenen_eczane_satirlar = []

        # Tekrar eden fatura numaralarını ayrı key ile sakla
        def benzersiz_fatura_ekle(data_dict, fatura, kayit):
            if fatura not in data_dict:
                data_dict[fatura] = kayit
            else:
                counter = 2
                while f"{fatura} ({counter})" in data_dict:
                    counter += 1
                data_dict[f"{fatura} ({counter})"] = kayit
                logger.warning(f"Tekrar eden fatura no: '{fatura}' → '{fatura} ({counter})' olarak eklendi")

        # Verileri hazırla
        faturasiz_depo_sayac = 0
        faturasiz_eczane_sayac = 0

        depo_data = {}
        for _, row in df_depo.iterrows():
            if satir_filtreli_mi(row, 'depo'):
                depo_filtreli += 1
                fatura = str(row[depo_fatura_col]).strip() if pd.notna(row[depo_fatura_col]) else ""
                borc = float(row[depo_borc_col]) if depo_borc_col and pd.notna(row[depo_borc_col]) else 0
                alacak = float(row[depo_alacak_col]) if depo_alacak_col and pd.notna(row[depo_alacak_col]) else 0
                tarih = str(row[depo_tarih_col]).strip() if depo_tarih_col and pd.notna(row[depo_tarih_col]) else ""
                tip = str(row[depo_tip_col]).strip() if depo_tip_col and pd.notna(row[depo_tip_col]) else ""
                filtrelenen_depo_satirlar.append((fatura, {'borc': borc, 'alacak': alacak, 'tarih': tarih, 'tip': tip}))
                continue

            fatura = str(row[depo_fatura_col]).strip() if pd.notna(row[depo_fatura_col]) else ""
            borc = float(row[depo_borc_col]) if depo_borc_col and pd.notna(row[depo_borc_col]) else 0
            alacak = float(row[depo_alacak_col]) if depo_alacak_col and pd.notna(row[depo_alacak_col]) else 0
            tarih = str(row[depo_tarih_col]).strip() if depo_tarih_col and pd.notna(row[depo_tarih_col]) else ""
            tip = str(row[depo_tip_col]).strip() if depo_tip_col and pd.notna(row[depo_tip_col]) else ""
            tutar_var = abs(borc) > 0.01 or abs(alacak) > 0.01
            tarih_var = tarih and tarih != 'nan'
            fatura_var = fatura and fatura != 'nan'

            if not fatura_var:
                if not tarih_var or not tutar_var:
                    # Fatura no, tarih veya tutar yok → alt toplam/başlık satırı, atla
                    continue
                # Tarih ve tutar var ama fatura no yok → numara ata
                faturasiz_depo_sayac += 1
                fatura = f"[Faturasız-D{faturasiz_depo_sayac}]"

            benzersiz_fatura_ekle(depo_data, fatura, {'borc': borc, 'alacak': alacak, 'tarih': tarih, 'tip': tip, 'row': row})

        eczane_data = {}
        for _, row in df_eczane.iterrows():
            if satir_filtreli_mi(row, 'eczane'):
                eczane_filtreli += 1
                fatura = str(row[eczane_fatura_col]).strip() if pd.notna(row[eczane_fatura_col]) else ""
                borc = float(row[eczane_borc_col]) if eczane_borc_col and pd.notna(row[eczane_borc_col]) else 0
                alacak = float(row[eczane_alacak_col]) if eczane_alacak_col and pd.notna(row[eczane_alacak_col]) else 0
                tarih = str(row[eczane_tarih_col]).strip() if eczane_tarih_col and pd.notna(row[eczane_tarih_col]) else ""
                tip = str(row[eczane_tip_col]).strip() if eczane_tip_col and pd.notna(row[eczane_tip_col]) else ""
                filtrelenen_eczane_satirlar.append((fatura, {'borc': borc, 'alacak': alacak, 'tarih': tarih, 'tip': tip}))
                continue

            fatura = str(row[eczane_fatura_col]).strip() if pd.notna(row[eczane_fatura_col]) else ""
            borc = float(row[eczane_borc_col]) if eczane_borc_col and pd.notna(row[eczane_borc_col]) else 0
            alacak = float(row[eczane_alacak_col]) if eczane_alacak_col and pd.notna(row[eczane_alacak_col]) else 0
            tarih = str(row[eczane_tarih_col]).strip() if eczane_tarih_col and pd.notna(row[eczane_tarih_col]) else ""
            tip = str(row[eczane_tip_col]).strip() if eczane_tip_col and pd.notna(row[eczane_tip_col]) else ""
            tutar_var = abs(borc) > 0.01 or abs(alacak) > 0.01
            tarih_var = tarih and tarih != 'nan'
            fatura_var = fatura and fatura != 'nan'

            if not fatura_var:
                if not tarih_var or not tutar_var:
                    # Fatura no, tarih veya tutar yok → alt toplam/başlık satırı, atla
                    continue
                # Tarih ve tutar var ama fatura no yok → numara ata
                faturasiz_eczane_sayac += 1
                fatura = f"[Faturasız-E{faturasiz_eczane_sayac}]"

            benzersiz_fatura_ekle(eczane_data, fatura, {'borc': borc, 'alacak': alacak, 'tarih': tarih, 'tip': tip, 'row': row})

        # Karşılaştırma
        tum_faturalar = set(depo_data.keys()) | set(eczane_data.keys())

        yesil_satirlar = []
        sari_satirlar = []
        turuncu_satirlar = []
        kirmizi_depo = []
        kirmizi_eczane = []

        # Net tutar hesaplama fonksiyonu - borç veya alacak hangisi doluysa onu al
        def get_net_tutar(kayit):
            borc = kayit.get('borc', 0) or 0
            alacak = kayit.get('alacak', 0) or 0
            return borc if abs(borc) > 0.01 else abs(alacak)

        eslesen_faturalar = set()
        for fatura in tum_faturalar:
            depo_kayit = depo_data.get(fatura)
            eczane_kayit = eczane_data.get(fatura)

            if depo_kayit and eczane_kayit:
                eslesen_faturalar.add(fatura)

                # Net tutarları al - borç/alacak farkı gözetmeksizin
                depo_tutar = get_net_tutar(depo_kayit)
                eczane_tutar = get_net_tutar(eczane_kayit)
                tutar_esit = abs(depo_tutar - eczane_tutar) < 0.01

                if tutar_esit:
                    yesil_satirlar.append((fatura, depo_kayit, eczane_kayit))
                else:
                    turuncu_satirlar.append((fatura, depo_kayit, eczane_kayit))

        # Tutar bazlı eşleştirme
        eslesmeyen_depo = {f: d for f, d in depo_data.items() if f not in eslesen_faturalar}
        eslesmeyen_eczane = {f: d for f, d in eczane_data.items() if f not in eslesen_faturalar}

        tutar_eslesen_depo = set()
        tutar_eslesen_eczane = set()

        def parse_tarih(tarih_str):
            if not tarih_str or tarih_str == '' or tarih_str == 'nan':
                return pd.Timestamp('1900-01-01')
            try:
                return pd.to_datetime(tarih_str)
            except Exception:
                return pd.Timestamp('1900-01-01')

        for depo_fatura, depo_kayit in eslesmeyen_depo.items():
            if depo_fatura in tutar_eslesen_depo:
                continue

            # Net tutarı al - borç/alacak farkı gözetmeksizin
            depo_tutar = get_net_tutar(depo_kayit)
            depo_tarih = parse_tarih(depo_kayit.get('tarih', ''))

            adaylar = []
            for eczane_fatura, eczane_kayit in eslesmeyen_eczane.items():
                if eczane_fatura in tutar_eslesen_eczane:
                    continue

                # Net tutarı al - borç/alacak farkı gözetmeksizin
                eczane_tutar = get_net_tutar(eczane_kayit)

                if abs(depo_tutar - eczane_tutar) < 0.01 and depo_tutar > 0:
                    eczane_tarih = parse_tarih(eczane_kayit.get('tarih', ''))
                    tarih_fark = abs((depo_tarih - eczane_tarih).days)
                    adaylar.append((tarih_fark, eczane_fatura, eczane_kayit))

            if adaylar:
                adaylar.sort(key=lambda x: x[0])
                en_yakin_tarih_fark, en_yakin_fatura, en_yakin_kayit = adaylar[0]
                sari_satirlar.append((depo_fatura, en_yakin_fatura, depo_kayit, en_yakin_kayit))
                tutar_eslesen_depo.add(depo_fatura)
                tutar_eslesen_eczane.add(en_yakin_fatura)

        for depo_fatura, depo_kayit in eslesmeyen_depo.items():
            if depo_fatura not in tutar_eslesen_depo:
                kirmizi_depo.append((depo_fatura, depo_kayit))

        for eczane_fatura, eczane_kayit in eslesmeyen_eczane.items():
            if eczane_fatura not in tutar_eslesen_eczane:
                kirmizi_eczane.append((eczane_fatura, eczane_kayit))

        # === ANA PENCERE İÇERİĞİ ===
        main_frame = tk.Frame(pencere, bg='#ECEFF1')
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Başlık
        header_frame = tk.Frame(main_frame, bg='#ECEFF1')
        header_frame.pack(fill="x", pady=(0, 5))

        tk.Label(
            header_frame,
            text="📊 DEPO - ECZANE EKSTRE KARŞILAŞTIRMA",
            font=("Arial", 14, "bold"),
            bg='#ECEFF1',
            fg='#1565C0'
        ).pack()

        # Borç özeti
        borc_frame = tk.Frame(header_frame, bg='#ECEFF1')
        borc_frame.pack(fill="x", pady=(5, 5))

        depo_toplam_borc = sum(kayit['borc'] for kayit in depo_data.values())
        depo_toplam_alacak = sum(kayit['alacak'] for kayit in depo_data.values())
        depo_net_borc = depo_toplam_borc - depo_toplam_alacak

        depo_borc_frame = tk.Frame(borc_frame, bg='#E3F2FD', relief="raised", bd=1)
        depo_borc_frame.pack(side="left", fill="both", expand=True, padx=3)

        tk.Label(
            depo_borc_frame,
            text="📦 Depo Excel'e Göre - Depoya Ödenmesi Gereken",
            font=("Arial", 9, "bold"),
            bg='#E3F2FD',
            fg='#01579B'
        ).pack(pady=(3, 0))

        depo_toplam_label = tk.Label(
            depo_borc_frame,
            text=f"{depo_net_borc:,.2f} ₺",
            font=("Arial", 12, "bold"),
            bg='#E3F2FD',
            fg='#01579B'
        )
        depo_toplam_label.pack(pady=(0, 3))

        eczane_toplam_borc = sum(kayit['borc'] for kayit in eczane_data.values())
        eczane_toplam_alacak = sum(kayit['alacak'] for kayit in eczane_data.values())
        eczane_net_borc = eczane_toplam_borc - eczane_toplam_alacak

        eczane_borc_frame = tk.Frame(borc_frame, bg='#E8F5E9', relief="raised", bd=1)
        eczane_borc_frame.pack(side="left", fill="both", expand=True, padx=3)

        tk.Label(
            eczane_borc_frame,
            text="🏥 Eczane Programına Göre - Depoya Ödenmesi Gereken",
            font=("Arial", 9, "bold"),
            bg='#E8F5E9',
            fg='#1B5E20'
        ).pack(pady=(3, 0))

        eczane_toplam_label = tk.Label(
            eczane_borc_frame,
            text=f"{eczane_net_borc:,.2f} ₺",
            font=("Arial", 12, "bold"),
            bg='#E8F5E9',
            fg='#1B5E20'
        )
        eczane_toplam_label.pack(pady=(0, 3))

        # Toplam label referanslarını sakla
        self._sonuc_widgets['depo_toplam_label'] = depo_toplam_label
        self._sonuc_widgets['eczane_toplam_label'] = eczane_toplam_label
        self._sonuc_widgets['orijinal_depo_toplam'] = depo_net_borc
        self._sonuc_widgets['orijinal_eczane_toplam'] = eczane_net_borc

        if depo_filtreli > 0 or eczane_filtreli > 0:
            tk.Label(
                header_frame,
                text=f"⚙️ Filtre uygulandı: Depo'dan {depo_filtreli}, Eczane'den {eczane_filtreli} satır atlandı",
                font=("Arial", 9),
                bg='#FFF3E0',
                fg='#E65100',
                padx=10,
                pady=3
            ).pack(pady=(5, 0))

        # === SCROLLABLE CANVAS ===
        canvas_container = tk.Frame(main_frame, bg='#ECEFF1')
        canvas_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(canvas_container, bg='#ECEFF1', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#ECEFF1')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # === ACCORDION PANEL FONKSİYONU ===
        def create_accordion_panel(parent, title, bg_color, fg_color, content_builder):
            """Genişleyebilen panel oluştur"""
            panel_frame = tk.Frame(parent, bg='#ECEFF1')
            panel_frame.pack(fill="x", pady=2)

            header_fr = tk.Frame(panel_frame, bg=bg_color, cursor="hand2", relief="raised", bd=2)
            header_fr.pack(fill="x")

            is_expanded = tk.BooleanVar(value=False)
            arrow_label = tk.Label(header_fr, text="▶", bg=bg_color, fg=fg_color, font=("Arial", 12, "bold"))
            arrow_label.pack(side="left", padx=5)

            title_label = tk.Label(header_fr, text=title, bg=bg_color, fg=fg_color,
                                  font=("Arial", 10, "bold"), anchor="w")
            title_label.pack(side="left", fill="x", expand=True, padx=5, pady=5)

            content_fr = tk.Frame(panel_frame, bg=bg_color, relief="sunken", bd=2)

            def toggle():
                if is_expanded.get():
                    content_fr.pack_forget()
                    arrow_label.config(text="▶")
                    is_expanded.set(False)
                else:
                    content_fr.pack(fill="both", expand=True, padx=2, pady=2)
                    arrow_label.config(text="▼")
                    is_expanded.set(True)
                    if not content_fr.winfo_children():
                        content_builder(content_fr)

            header_fr.bind("<Button-1>", lambda e: toggle())
            arrow_label.bind("<Button-1>", lambda e: toggle())
            title_label.bind("<Button-1>", lambda e: toggle())

            return panel_frame

        # === PANEL BUILDER FONKSİYONLARI ===
        def build_tum_kayitlar(content_frame):
            """Tüm kayıtları konsolide görünüm olarak göster"""
            toplam_kayit = len(yesil_satirlar) + len(sari_satirlar) + len(turuncu_satirlar) + len(kirmizi_eczane) + len(kirmizi_depo)

            tk.Label(
                content_frame,
                text=f"📋 Toplam {toplam_kayit} kayıt | 🟢 {len(yesil_satirlar)} | 🟡 {len(sari_satirlar)} | 🟠 {len(turuncu_satirlar)} | 🔴 {len(kirmizi_eczane) + len(kirmizi_depo)}",
                bg='#E3F2FD',
                font=("Arial", 10, "bold"),
                fg='#1565C0',
                padx=10,
                pady=5
            ).pack(fill="x", pady=5)

            tree_container = tk.Frame(content_frame, bg='white')
            tree_container.pack(fill="both", expand=True, pady=5)

            # Üst başlık
            hdr = tk.Frame(tree_container, bg='white')
            hdr.pack(fill="x")
            tk.Label(hdr, text="📦 DEPO TARAFI", font=("Arial", 10, "bold"), bg='#B3E5FC', fg='#01579B', relief="raised", bd=1, padx=3, pady=3).pack(side="left", fill="both", expand=True)
            tk.Label(hdr, text="║", font=("Arial", 11, "bold"), bg='white', width=2).pack(side="left")
            tk.Label(hdr, text="🏥 ECZANE TARAFI", font=("Arial", 10, "bold"), bg='#C8E6C9', fg='#1B5E20', relief="raised", bd=1, padx=3, pady=3).pack(side="left", fill="both", expand=True)

            tree_fr = tk.Frame(tree_container, bg='white')
            tree_fr.pack(fill="both", expand=True)

            tree = ttk.Treeview(
                tree_fr,
                columns=("depo_fatura", "depo_tarih", "depo_tip", "depo_tutar", "sep", "eczane_fatura", "eczane_tarih", "eczane_tip", "eczane_tutar"),
                show="headings",
                height=15
            )
            for col, text, width in [
                ("depo_fatura", "Fatura No", 140), ("depo_tarih", "Tarih", 100), ("depo_tip", "Tip", 90), ("depo_tutar", "Tutar", 110),
                ("sep", "║", 15),
                ("eczane_fatura", "Fatura No", 140), ("eczane_tarih", "Tarih", 100), ("eczane_tip", "Tip", 90), ("eczane_tutar", "Tutar", 150)
            ]:
                tree.heading(col, text=text)
                tree.column(col, width=width, minwidth=width, anchor="e" if "tutar" in col else ("center" if col in ["sep", "depo_tarih", "eczane_tarih", "depo_tip", "eczane_tip"] else "w"), stretch=(col == "eczane_tutar"))

            tree_scroll = ttk.Scrollbar(tree_fr, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=tree_scroll.set)
            tree.pack(side="left", fill="both", expand=True)
            tree_scroll.pack(side="right", fill="y")

            for fatura, depo, eczane in yesil_satirlar:
                depo_tutar = self._format_tutar(depo, goster_tip=True)
                eczane_tutar = self._format_tutar(eczane, goster_tip=True)
                tree.insert("", "end", values=(fatura, depo.get('tarih', ''), depo.get('tip', ''), depo_tutar, "║", fatura, eczane.get('tarih', ''), eczane.get('tip', ''), eczane_tutar), tags=('yesil',))

            for depo_f, eczane_f, depo, eczane in sari_satirlar:
                depo_tutar = self._format_tutar(depo, goster_tip=True)
                eczane_tutar = self._format_tutar(eczane, goster_tip=True)
                tree.insert("", "end", values=(depo_f, depo.get('tarih', ''), depo.get('tip', ''), depo_tutar, "║", eczane_f, eczane.get('tarih', ''), eczane.get('tip', ''), eczane_tutar), tags=('sari',))

            for fatura, depo, eczane in turuncu_satirlar:
                depo_tutar = self._format_tutar(depo, goster_tip=True)
                eczane_tutar = self._format_tutar(eczane, goster_tip=True)
                tree.insert("", "end", values=(fatura, depo.get('tarih', ''), depo.get('tip', ''), depo_tutar, "║", fatura, eczane.get('tarih', ''), eczane.get('tip', ''), eczane_tutar), tags=('turuncu',))

            for fatura, kayit in kirmizi_eczane:
                eczane_tutar = self._format_tutar(kayit, goster_tip=True)
                tree.insert("", "end", values=("", "", "", "", "║", fatura, kayit.get('tarih', ''), kayit.get('tip', ''), eczane_tutar), tags=('kirmizi',))

            for fatura, kayit in kirmizi_depo:
                depo_tutar = self._format_tutar(kayit, goster_tip=True)
                tree.insert("", "end", values=(fatura, kayit.get('tarih', ''), kayit.get('tip', ''), depo_tutar, "║", "", "", "", ""), tags=('kirmizi',))

            tree.tag_configure('yesil', background='#C8E6C9')
            tree.tag_configure('sari', background='#FFF9C4')
            tree.tag_configure('turuncu', background='#FFE0B2')
            tree.tag_configure('kirmizi', background='#FFCDD2')

        def build_yesil_panel(cf):
            self._build_standart_panel(cf, yesil_satirlar, 'yesil', '#E8F5E9', '#C8E6C9', 'fatura_esit')

        def build_sari_panel(cf):
            self._build_standart_panel(cf, sari_satirlar, 'sari', '#FFFDE7', '#FFF9C4', 'fatura_farkli')

        def build_turuncu_panel(cf):
            self._build_standart_panel(cf, turuncu_satirlar, 'turuncu', '#FFF3E0', '#FFE0B2', 'fatura_esit')

        def build_kirmizi_panel(cf):
            self._build_kirmizi_panel(cf, kirmizi_depo, kirmizi_eczane)

        def build_toplam_panel(cf):
            self._build_toplam_panel(cf, yesil_satirlar, sari_satirlar, turuncu_satirlar, kirmizi_depo, kirmizi_eczane)

        def build_filtrelenen_panel(cf):
            self._build_filtrelenen_panel(cf, filtrelenen_depo_satirlar, filtrelenen_eczane_satirlar)

        def build_manuel_eslestirme_panel(cf):
            self._build_manuel_eslestirme_panel(cf)

        def build_manuel_iptal_panel(cf):
            self._build_manuel_iptal_panel(cf)

        def build_manuel_eklenenler_panel(cf):
            self._build_manuel_eklenenler_panel(cf)

        # === ACCORDION PANELLERİ OLUŞTUR ===
        tum_kayitlar_count = len(yesil_satirlar) + len(sari_satirlar) + len(turuncu_satirlar) + len(kirmizi_eczane) + len(kirmizi_depo)
        create_accordion_panel(scrollable_frame, f"📊 TÜM KAYITLAR - KONSOLİDE GÖRÜNÜM ({tum_kayitlar_count} kayıt)", "#E3F2FD", "#0D47A1", build_tum_kayitlar)
        create_accordion_panel(scrollable_frame, f"🟢 TAM EŞLEŞENLER (Fatura No + Tutar) - {len(yesil_satirlar)} kayıt", "#E8F5E9", "#2E7D32", build_yesil_panel)
        create_accordion_panel(scrollable_frame, f"🟡 TUTAR EŞLEŞENLER (Fatura No Farklı) - {len(sari_satirlar)} kayıt", "#FFFDE7", "#F9A825", build_sari_panel)
        create_accordion_panel(scrollable_frame, f"🟠 FATURA NO EŞLEŞENLER (Tutar Farklı) - {len(turuncu_satirlar)} kayıt", "#FFF3E0", "#E65100", build_turuncu_panel)
        create_accordion_panel(scrollable_frame, f"🔴 EŞLEŞMEYENLER - {len(kirmizi_eczane) + len(kirmizi_depo)} kayıt (Eczane: {len(kirmizi_eczane)}, Depo: {len(kirmizi_depo)})", "#FFEBEE", "#C62828", build_kirmizi_panel)

        # Manuel işlem panelleri
        create_accordion_panel(scrollable_frame, "🔗 MANUEL EŞLEŞTİRİLENLER", "#E8EAF6", "#3F51B5", build_manuel_eslestirme_panel)
        create_accordion_panel(scrollable_frame, "➕ MANUEL EKLENENLER", "#E0F2F1", "#00695C", build_manuel_eklenenler_panel)
        create_accordion_panel(scrollable_frame, "❌ MANUEL İPTAL EDİLENLER", "#FCE4EC", "#C2185B", build_manuel_iptal_panel)

        create_accordion_panel(scrollable_frame, "📊 TOPLAMLAR", "#E3F2FD", "#1565C0", build_toplam_panel)

        if filtrelenen_depo_satirlar or filtrelenen_eczane_satirlar:
            create_accordion_panel(scrollable_frame, f"⚙️ FİLTRELENEN SATIRLAR - {len(filtrelenen_depo_satirlar) + len(filtrelenen_eczane_satirlar)} kayıt", "#F5F5F5", "#757575", build_filtrelenen_panel)

        # Sonuçları sakla
        self.ekstre_sonuclar = {
            'yesil': yesil_satirlar,
            'sari': sari_satirlar,
            'turuncu': turuncu_satirlar,
            'kirmizi_eczane': kirmizi_eczane,
            'kirmizi_depo': kirmizi_depo,
            'df_depo': df_depo,
            'df_eczane': df_eczane
        }

        # Butonlar
        button_frame = tk.Frame(main_frame, bg='#ECEFF1')
        button_frame.pack(fill="x", pady=5)

        tk.Button(
            button_frame,
            text="📥 Excel'e Aktar",
            font=("Arial", 11, "bold"),
            bg='#388E3C',
            fg='white',
            width=20,
            cursor="hand2",
            command=lambda: self.ekstre_sonuc_excel_aktar(pencere)
        ).pack(side="left", padx=10)

        tk.Button(
            button_frame,
            text="❌ Kapat",
            font=("Arial", 11),
            bg='#757575',
            fg='white',
            width=15,
            cursor="hand2",
            command=pencere.destroy
        ).pack(side="right", padx=10)

    def _build_standart_panel(self, content_frame, satirlar, kategori, bg_color, row_color, tip):
        """Yeşil, Sarı, Turuncu panelleri için standart treeview"""
        tree_container = tk.Frame(content_frame, bg=bg_color)
        tree_container.pack(fill="both", expand=True, pady=5)

        # Turuncu panel için bilgi etiketi
        if kategori == 'turuncu':
            info_frame = tk.Frame(tree_container, bg=bg_color)
            info_frame.pack(fill="x", pady=(0, 5))
            tk.Label(
                info_frame,
                text="💡 Sağ tıklayarak: Tutarı Düzelt veya İptal Et (eşleşme yeşile geçer)",
                font=("Arial", 9),
                bg=bg_color,
                fg='#E65100'
            ).pack(side="left", padx=5)

        hdr = tk.Frame(tree_container, bg=bg_color)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📦 DEPO TARAFI", font=("Arial", 10, "bold"), bg='#B3E5FC', fg='#01579B', relief="raised", bd=1, padx=3, pady=3).pack(side="left", fill="both", expand=True)
        tk.Label(hdr, text="║", font=("Arial", 11, "bold"), bg=bg_color, width=2).pack(side="left")
        tk.Label(hdr, text="🏥 ECZANE TARAFI", font=("Arial", 10, "bold"), bg='#C8E6C9', fg='#1B5E20', relief="raised", bd=1, padx=3, pady=3).pack(side="left", fill="both", expand=True)

        tree_fr = tk.Frame(tree_container, bg=bg_color)
        tree_fr.pack(fill="both", expand=True)

        tree = ttk.Treeview(tree_fr, columns=("depo_fatura", "depo_tarih", "depo_tip", "depo_tutar", "sep", "eczane_fatura", "eczane_tarih", "eczane_tip", "eczane_tutar"), show="headings", height=10)
        for col, text, width in [("depo_fatura", "Fatura No", 140), ("depo_tarih", "Tarih", 100), ("depo_tip", "Tip", 90), ("depo_tutar", "Tutar", 110), ("sep", "║", 15), ("eczane_fatura", "Fatura No", 140), ("eczane_tarih", "Tarih", 100), ("eczane_tip", "Tip", 90), ("eczane_tutar", "Tutar", 150)]:
            tree.heading(col, text=text)
            tree.column(col, width=width, minwidth=width, anchor="e" if "tutar" in col else ("center" if col in ["sep", "depo_tarih", "eczane_tarih", "depo_tip", "eczane_tip"] else "w"), stretch=(col == "eczane_tutar"))

        tree_scroll = ttk.Scrollbar(tree_fr, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # Turuncu panel için item data dictionary
        if kategori == 'turuncu':
            self._turuncu_item_data = {}

        if tip == 'fatura_esit':
            for fatura, depo, eczane in satirlar:
                depo_tutar = self._format_tutar(depo, goster_tip=True)
                eczane_tutar = self._format_tutar(eczane, goster_tip=True)
                item_id = tree.insert("", "end", values=(fatura, depo.get('tarih', ''), depo.get('tip', ''), depo_tutar, "║", fatura, eczane.get('tarih', ''), eczane.get('tip', ''), eczane_tutar), tags=(kategori,))
                # Turuncu için veri sakla
                if kategori == 'turuncu':
                    self._turuncu_item_data[item_id] = {'fatura': fatura, 'depo': depo.copy(), 'eczane': eczane.copy()}
        else:  # fatura_farkli (sarı)
            for depo_f, eczane_f, depo, eczane in satirlar:
                depo_tutar = self._format_tutar(depo, goster_tip=True)
                eczane_tutar = self._format_tutar(eczane, goster_tip=True)
                tree.insert("", "end", values=(depo_f, depo.get('tarih', ''), depo.get('tip', ''), depo_tutar, "║", eczane_f, eczane.get('tarih', ''), eczane.get('tip', ''), eczane_tutar), tags=(kategori,))

        tree.tag_configure(kategori, background=row_color)

        # Turuncu panel için sağ tıklama menüsü
        if kategori == 'turuncu':
            context_menu = tk.Menu(tree, tearoff=0)
            context_menu.add_command(label="✏️ Depo Tutarını Düzelt", command=lambda: self._turuncu_tutar_duzelt(tree, 'depo'))
            context_menu.add_command(label="✏️ Eczane Tutarını Düzelt", command=lambda: self._turuncu_tutar_duzelt(tree, 'eczane'))
            context_menu.add_separator()
            context_menu.add_command(label="❌ Bu Satırı İptal Et", command=lambda: self._turuncu_satir_iptal(tree))

            def show_context_menu(event):
                item = tree.identify_row(event.y)
                if item:
                    tree.selection_set(item)
                    context_menu.post(event.x_root, event.y_root)

            tree.bind("<Button-3>", show_context_menu)
            self._turuncu_tree = tree

    def _turuncu_tutar_duzelt(self, tree, kaynak):
        """Turuncu paneldeki satırın tutarını düzelt"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Uyarı", "Lütfen bir satır seçin!")
            return

        item_id = selection[0]
        if item_id not in self._turuncu_item_data:
            messagebox.showwarning("Uyarı", "Bu satır için veri bulunamadı!")
            return

        item_data = self._turuncu_item_data[item_id]
        fatura = item_data['fatura']
        kayit = item_data[kaynak]

        # Mevcut tutarı al
        mevcut_tutar, tip = self._get_tutar(kayit)

        # Düzenleme penceresi
        duzelt_pencere = tk.Toplevel(self._sonuc_pencere or self.root)
        duzelt_pencere.title(f"✏️ {'Depo' if kaynak == 'depo' else 'Eczane'} Tutarını Düzelt")
        duzelt_pencere.geometry("350x200")
        duzelt_pencere.configure(bg='#ECEFF1')
        duzelt_pencere.transient(self._sonuc_pencere or self.root)
        duzelt_pencere.grab_set()

        # Ortala
        duzelt_pencere.update_idletasks()
        x = (duzelt_pencere.winfo_screenwidth() - 350) // 2
        y = (duzelt_pencere.winfo_screenheight() - 200) // 2
        duzelt_pencere.geometry(f"350x200+{x}+{y}")

        tk.Label(
            duzelt_pencere,
            text=f"{'📦 Depo' if kaynak == 'depo' else '🏥 Eczane'} - Fatura: {fatura}",
            font=("Arial", 11, "bold"),
            bg='#ECEFF1',
            fg='#E65100'
        ).pack(pady=10)

        tk.Label(
            duzelt_pencere,
            text=f"Mevcut Tutar: {mevcut_tutar:,.2f} ₺",
            font=("Arial", 10),
            bg='#ECEFF1'
        ).pack(pady=5)

        tk.Label(
            duzelt_pencere,
            text="Yeni Tutar:",
            font=("Arial", 10),
            bg='#ECEFF1'
        ).pack(pady=(10, 0))

        tutar_entry = tk.Entry(duzelt_pencere, font=("Arial", 12), width=20, justify="right")
        tutar_entry.pack(pady=5)
        tutar_entry.insert(0, f"{mevcut_tutar:.2f}")
        tutar_entry.select_range(0, tk.END)
        tutar_entry.focus()

        def kaydet():
            try:
                yeni_tutar_str = tutar_entry.get().replace(",", ".").replace(" ", "").replace("₺", "")
                yeni_tutar = float(yeni_tutar_str)

                # Kayıt güncelle + genel toplam delta hesapla
                if tip == 'B':
                    kayit['borc'] = yeni_tutar
                    delta = yeni_tutar - mevcut_tutar
                else:
                    kayit['alacak'] = yeni_tutar
                    delta = -(yeni_tutar - mevcut_tutar)
                if kaynak == 'depo':
                    self.tutar_duzeltme_delta_depo += delta
                else:
                    self.tutar_duzeltme_delta_eczane += delta

                # Tree güncelle
                values = list(tree.item(item_id, 'values'))
                yeni_tutar_formatted = self._format_tutar(kayit, goster_tip=True)
                if kaynak == 'depo':
                    values[3] = yeni_tutar_formatted
                else:
                    values[8] = yeni_tutar_formatted
                tree.item(item_id, values=values)

                # Tutarlar eşit mi kontrol et - eşitse yeşile çevir
                depo_tutar = self._get_tutar(item_data['depo'])[0]
                eczane_tutar = self._get_tutar(item_data['eczane'])[0]
                if abs(depo_tutar - eczane_tutar) < 0.01:
                    tree.item(item_id, tags=('yesil',))
                    tree.tag_configure('yesil', background='#C8E6C9')
                    messagebox.showinfo("Başarılı", f"Tutar güncellendi: {yeni_tutar:,.2f} ₺\n\n✅ Tutarlar eşleşti! Satır yeşile döndü.")
                else:
                    messagebox.showinfo("Başarılı", f"Tutar güncellendi: {yeni_tutar:,.2f} ₺")

                self._toplamlari_guncelle()
                duzelt_pencere.destroy()

            except ValueError:
                messagebox.showerror("Hata", "Geçerli bir tutar girin!")

        btn_frame = tk.Frame(duzelt_pencere, bg='#ECEFF1')
        btn_frame.pack(pady=15)

        tk.Button(btn_frame, text="💾 Kaydet", font=("Arial", 10, "bold"), bg='#4CAF50', fg='white', width=10, command=kaydet).pack(side="left", padx=5)
        tk.Button(btn_frame, text="❌ İptal", font=("Arial", 10), bg='#f44336', fg='white', width=10, command=duzelt_pencere.destroy).pack(side="left", padx=5)

    def _turuncu_satir_iptal(self, tree):
        """Turuncu paneldeki satırı iptal et"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Uyarı", "Lütfen bir satır seçin!")
            return

        item_id = selection[0]
        if item_id not in self._turuncu_item_data:
            return

        item_data = self._turuncu_item_data[item_id]
        fatura = item_data['fatura']
        depo_tutar = self._get_tutar(item_data['depo'])[0]
        eczane_tutar = self._get_tutar(item_data['eczane'])[0]

        # Onay al
        if not messagebox.askyesno("İptal Onayı",
                                   f"Bu satırı iptal etmek istiyor musunuz?\n\n"
                                   f"Fatura: {fatura}\n"
                                   f"📦 Depo: {depo_tutar:,.2f} ₺\n"
                                   f"🏥 Eczane: {eczane_tutar:,.2f} ₺\n\n"
                                   f"Her iki taraf da iptal listesine eklenecektir."):
            return

        # Her iki tarafı da iptal listesine ekle
        self.manuel_iptal_edilenler_depo.append((fatura, item_data['depo'].copy()))
        self.manuel_iptal_edilenler_eczane.append((fatura, item_data['eczane'].copy()))

        # Tree'den sil
        tree.delete(item_id)
        del self._turuncu_item_data[item_id]

        # Sonuçları güncelle
        self._sonuclari_guncelle()

        messagebox.showinfo("Başarılı", f"Satır iptal edildi: {fatura}")

    def _build_kirmizi_panel(self, content_frame, kirmizi_depo, kirmizi_eczane):
        """Kırmızı panel - İKİ AYRI TREEVIEW ile depo ve eczane ayrı"""
        main_container = tk.Frame(content_frame, bg='#FFEBEE')
        main_container.pack(fill="both", expand=True, pady=5)

        # Bilgi ve buton çubuğu
        info_frame = tk.Frame(main_container, bg='#FFEBEE')
        info_frame.pack(fill="x", pady=(0, 10))

        tk.Label(
            info_frame,
            text="💡 Her iki taraftan bir veya birden fazla satır seçin, sonra 'Manuel Eşleştir' butonuna tıklayın",
            font=("Arial", 9),
            bg='#FFEBEE',
            fg='#C62828'
        ).pack(side="left", padx=5)

        # Manuel Eşleştir butonu
        self._manuel_eslestir_btn = tk.Button(
            info_frame,
            text="🔗 Manuel Eşleştir",
            font=("Arial", 10, "bold"),
            bg='#9E9E9E',
            fg='white',
            state='disabled',
            cursor="hand2",
            command=self._kirmizi_manuel_eslestir
        )
        self._manuel_eslestir_btn.pack(side="right", padx=5)

        # Seçim durumu etiketi
        self._kirmizi_secim_label = tk.Label(
            info_frame,
            text="Seçim: Depo(-) | Eczane(-)",
            font=("Arial", 9, "bold"),
            bg='#FFEBEE',
            fg='#757575'
        )
        self._kirmizi_secim_label.pack(side="right", padx=10)

        # İki panel yan yana
        panels_frame = tk.Frame(main_container, bg='#FFEBEE')
        panels_frame.pack(fill="both", expand=True)
        panels_frame.columnconfigure(0, weight=1)
        panels_frame.columnconfigure(1, weight=1)

        # === SOL PANEL: DEPO ===
        depo_frame = tk.LabelFrame(
            panels_frame,
            text=f"📦 DEPO'DA OLUP EŞLEŞMEYENLER ({len(kirmizi_depo)} adet)",
            font=("Arial", 10, "bold"),
            bg='#FFCDD2',
            fg='#B71C1C',
            padx=5,
            pady=5
        )
        depo_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 3), pady=2)

        depo_tree = ttk.Treeview(
            depo_frame,
            columns=("fatura", "tarih", "tip", "tutar"),
            show="headings",
            height=8,
            selectmode="extended"
        )
        for col, text, width in [("fatura", "Fatura No", 120), ("tarih", "Tarih", 80), ("tip", "Tip", 60), ("tutar", "Tutar", 100)]:
            depo_tree.heading(col, text=text)
            depo_tree.column(col, width=width, anchor="e" if col == "tutar" else "w")

        depo_scroll = ttk.Scrollbar(depo_frame, orient="vertical", command=depo_tree.yview)
        depo_tree.configure(yscrollcommand=depo_scroll.set)
        depo_tree.pack(side="left", fill="both", expand=True)
        depo_scroll.pack(side="right", fill="y")

        # Depo verileri
        self._kirmizi_depo_data = {}
        for fatura, kayit in kirmizi_depo:
            tutar = self._format_tutar(kayit, goster_tip=True)
            item_id = depo_tree.insert("", "end", values=(fatura, kayit.get('tarih', ''), kayit.get('tip', ''), tutar))
            self._kirmizi_depo_data[item_id] = {'fatura': fatura, 'kayit': kayit.copy()}

        # Depo seçim toplamı label
        self._depo_secim_toplam_label = tk.Label(
            depo_frame,
            text="",
            font=("Arial", 9, "bold"),
            bg='#FFCDD2',
            fg='#1A237E'
        )
        self._depo_secim_toplam_label.pack(fill="x", pady=(3, 0))

        # Depo seçim olayı (çoklu seçim)
        def depo_secildi(event):
            selection = depo_tree.selection()
            if selection:
                self._secili_depo_items = list(selection)
                self.secili_depo_satirlar = []
                toplam = 0
                for item_id in selection:
                    data = self._kirmizi_depo_data.get(item_id)
                    if data:
                        self.secili_depo_satirlar.append((data['fatura'], data['kayit']))
                        toplam += self._get_tutar(data['kayit'])[0]
                if len(selection) > 1:
                    self._depo_secim_toplam_label.config(text=f"Seçili: {len(selection)} satır | Toplam: {toplam:,.2f} ₺")
                elif len(selection) == 1:
                    self._depo_secim_toplam_label.config(text=f"Seçili: 1 satır | Toplam: {toplam:,.2f} ₺")
                else:
                    self._depo_secim_toplam_label.config(text="")
                self._kirmizi_secim_guncelle()
            else:
                self.secili_depo_satirlar = []
                self._secili_depo_items = []
                self._depo_secim_toplam_label.config(text="")
                self._kirmizi_secim_guncelle()

        depo_tree.bind("<<TreeviewSelect>>", depo_secildi)

        # Depo sağ tıklama menüsü
        depo_menu = tk.Menu(depo_tree, tearoff=0)
        depo_menu.add_command(label="🔗 Manuel Eşleştir", command=self._kirmizi_manuel_eslestir)
        depo_menu.add_command(label="🔗 Tutarı Karşı Tarafla Eşitle ve Eşleştir", command=lambda: self._tutari_esitle_ve_eslestir('depo'))
        depo_menu.add_separator()
        depo_menu.add_command(label="🔍 İade Fatura Detay Karşılaştır", command=lambda: self._iade_fatura_detay_ac(depo_tree))
        depo_menu.add_separator()
        depo_menu.add_command(label="✏️ Tutarı Düzelt", command=lambda: self._kirmizi_tutar_duzelt(depo_tree, 'depo'))
        depo_menu.add_separator()
        depo_menu.add_command(label="➕ Eczane'ye de Ekle ve Eşleştir", command=lambda: self._diger_tarafa_ekle(depo_tree, 'depo'))
        depo_menu.add_separator()
        depo_menu.add_command(label="❌ İptal Et", command=lambda: self._kirmizi_satir_iptal(depo_tree, 'depo'))

        def depo_context_menu(event):
            item = depo_tree.identify_row(event.y)
            if item:
                # Sağ tıklanan satır zaten seçili ise mevcut çoklu seçimi koru
                if item not in depo_tree.selection():
                    depo_tree.selection_set(item)
                depo_menu.post(event.x_root, event.y_root)

        depo_tree.bind("<Button-3>", depo_context_menu)
        self._kirmizi_depo_tree = depo_tree

        # === SAĞ PANEL: ECZANE ===
        eczane_frame = tk.LabelFrame(
            panels_frame,
            text=f"🏥 ECZANE'DE OLUP EŞLEŞMEYENLER ({len(kirmizi_eczane)} adet)",
            font=("Arial", 10, "bold"),
            bg='#F8BBD0',
            fg='#880E4F',
            padx=5,
            pady=5
        )
        eczane_frame.grid(row=0, column=1, sticky="nsew", padx=(3, 0), pady=2)

        eczane_tree = ttk.Treeview(
            eczane_frame,
            columns=("fatura", "tarih", "tip", "tutar"),
            show="headings",
            height=8,
            selectmode="extended"
        )
        for col, text, width in [("fatura", "Fatura No", 120), ("tarih", "Tarih", 80), ("tip", "Tip", 60), ("tutar", "Tutar", 100)]:
            eczane_tree.heading(col, text=text)
            eczane_tree.column(col, width=width, anchor="e" if col == "tutar" else "w")

        eczane_scroll = ttk.Scrollbar(eczane_frame, orient="vertical", command=eczane_tree.yview)
        eczane_tree.configure(yscrollcommand=eczane_scroll.set)
        eczane_tree.pack(side="left", fill="both", expand=True)
        eczane_scroll.pack(side="right", fill="y")

        # Eczane verileri
        self._kirmizi_eczane_data = {}
        for fatura, kayit in kirmizi_eczane:
            tutar = self._format_tutar(kayit, goster_tip=True)
            item_id = eczane_tree.insert("", "end", values=(fatura, kayit.get('tarih', ''), kayit.get('tip', ''), tutar))
            self._kirmizi_eczane_data[item_id] = {'fatura': fatura, 'kayit': kayit.copy()}

        # Eczane seçim toplamı label
        self._eczane_secim_toplam_label = tk.Label(
            eczane_frame,
            text="",
            font=("Arial", 9, "bold"),
            bg='#F8BBD0',
            fg='#1A237E'
        )
        self._eczane_secim_toplam_label.pack(fill="x", pady=(3, 0))

        # Eczane seçim olayı (çoklu seçim)
        def eczane_secildi(event):
            selection = eczane_tree.selection()
            if selection:
                self._secili_eczane_items = list(selection)
                self.secili_eczane_satirlar = []
                toplam = 0
                for item_id in selection:
                    data = self._kirmizi_eczane_data.get(item_id)
                    if data:
                        self.secili_eczane_satirlar.append((data['fatura'], data['kayit']))
                        toplam += self._get_tutar(data['kayit'])[0]
                if len(selection) > 1:
                    self._eczane_secim_toplam_label.config(text=f"Seçili: {len(selection)} satır | Toplam: {toplam:,.2f} ₺")
                elif len(selection) == 1:
                    self._eczane_secim_toplam_label.config(text=f"Seçili: 1 satır | Toplam: {toplam:,.2f} ₺")
                else:
                    self._eczane_secim_toplam_label.config(text="")
                self._kirmizi_secim_guncelle()
            else:
                self.secili_eczane_satirlar = []
                self._secili_eczane_items = []
                self._eczane_secim_toplam_label.config(text="")
                self._kirmizi_secim_guncelle()

        eczane_tree.bind("<<TreeviewSelect>>", eczane_secildi)

        # Eczane sağ tıklama menüsü
        eczane_menu = tk.Menu(eczane_tree, tearoff=0)
        eczane_menu.add_command(label="🔗 Manuel Eşleştir", command=self._kirmizi_manuel_eslestir)
        eczane_menu.add_command(label="🔗 Tutarı Karşı Tarafla Eşitle ve Eşleştir", command=lambda: self._tutari_esitle_ve_eslestir('eczane'))
        eczane_menu.add_separator()
        eczane_menu.add_command(label="🔍 İade Fatura Detay Karşılaştır", command=lambda: self._iade_fatura_detay_ac(eczane_tree))
        eczane_menu.add_separator()
        eczane_menu.add_command(label="✏️ Tutarı Düzelt", command=lambda: self._kirmizi_tutar_duzelt(eczane_tree, 'eczane'))
        eczane_menu.add_separator()
        eczane_menu.add_command(label="➕ Depo'ya da Ekle ve Eşleştir", command=lambda: self._diger_tarafa_ekle(eczane_tree, 'eczane'))
        eczane_menu.add_separator()
        eczane_menu.add_command(label="❌ İptal Et", command=lambda: self._kirmizi_satir_iptal(eczane_tree, 'eczane'))

        def eczane_context_menu(event):
            item = eczane_tree.identify_row(event.y)
            if item:
                # Sağ tıklanan satır zaten seçili ise mevcut çoklu seçimi koru
                if item not in eczane_tree.selection():
                    eczane_tree.selection_set(item)
                eczane_menu.post(event.x_root, event.y_root)

        eczane_tree.bind("<Button-3>", eczane_context_menu)
        self._kirmizi_eczane_tree = eczane_tree

    def _kirmizi_secim_guncelle(self):
        """Kırmızı panel seçim durumunu güncelle (çoklu seçim destekli)"""
        depo_satirlar = getattr(self, 'secili_depo_satirlar', [])
        eczane_satirlar = getattr(self, 'secili_eczane_satirlar', [])
        depo_secili = len(depo_satirlar) > 0
        eczane_secili = len(eczane_satirlar) > 0

        if depo_secili and eczane_secili:
            depo_bilgi = f"{len(depo_satirlar)} satır" if len(depo_satirlar) > 1 else depo_satirlar[0][0]
            eczane_bilgi = f"{len(eczane_satirlar)} satır" if len(eczane_satirlar) > 1 else eczane_satirlar[0][0]
            self._kirmizi_secim_label.config(
                text=f"Seçim: Depo({depo_bilgi}) | Eczane({eczane_bilgi})",
                fg='#2E7D32'
            )
            self._manuel_eslestir_btn.config(state='normal', bg='#4CAF50')
        elif depo_secili:
            depo_bilgi = f"{len(depo_satirlar)} satır" if len(depo_satirlar) > 1 else depo_satirlar[0][0]
            self._kirmizi_secim_label.config(
                text=f"Seçim: Depo({depo_bilgi}) | Eczane(-)",
                fg='#1565C0'
            )
            self._manuel_eslestir_btn.config(state='disabled', bg='#9E9E9E')
        elif eczane_secili:
            eczane_bilgi = f"{len(eczane_satirlar)} satır" if len(eczane_satirlar) > 1 else eczane_satirlar[0][0]
            self._kirmizi_secim_label.config(
                text=f"Seçim: Depo(-) | Eczane({eczane_bilgi})",
                fg='#1565C0'
            )
            self._manuel_eslestir_btn.config(state='disabled', bg='#9E9E9E')
        else:
            self._kirmizi_secim_label.config(
                text="Seçim: Depo(-) | Eczane(-)",
                fg='#757575'
            )
            self._manuel_eslestir_btn.config(state='disabled', bg='#9E9E9E')

    def _kirmizi_tutar_duzelt(self, tree, kaynak):
        """Kırmızı paneldeki satırın tutarını düzelt"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Uyarı", "Lütfen bir satır seçin!")
            return

        item_id = selection[0]
        if kaynak == 'depo':
            data = self._kirmizi_depo_data.get(item_id)
        else:
            data = self._kirmizi_eczane_data.get(item_id)

        if not data:
            messagebox.showwarning("Uyarı", "Bu satır için veri bulunamadı!")
            return

        fatura = data['fatura']
        kayit = data['kayit']
        mevcut_tutar, tip = self._get_tutar(kayit)

        # Düzenleme penceresi
        duzelt_pencere = tk.Toplevel(self._sonuc_pencere or self.root)
        duzelt_pencere.title("✏️ Tutarı Düzelt")
        duzelt_pencere.geometry("350x200")
        duzelt_pencere.configure(bg='#ECEFF1')
        duzelt_pencere.transient(self._sonuc_pencere or self.root)
        duzelt_pencere.grab_set()

        duzelt_pencere.update_idletasks()
        x = (duzelt_pencere.winfo_screenwidth() - 350) // 2
        y = (duzelt_pencere.winfo_screenheight() - 200) // 2
        duzelt_pencere.geometry(f"350x200+{x}+{y}")

        tk.Label(
            duzelt_pencere,
            text=f"{'📦 Depo' if kaynak == 'depo' else '🏥 Eczane'} - Fatura: {fatura}",
            font=("Arial", 11, "bold"),
            bg='#ECEFF1',
            fg='#1565C0'
        ).pack(pady=10)

        tk.Label(duzelt_pencere, text=f"Mevcut Tutar: {mevcut_tutar:,.2f} ₺", font=("Arial", 10), bg='#ECEFF1').pack(pady=5)
        tk.Label(duzelt_pencere, text="Yeni Tutar:", font=("Arial", 10), bg='#ECEFF1').pack(pady=(10, 0))

        tutar_entry = tk.Entry(duzelt_pencere, font=("Arial", 12), width=20, justify="right")
        tutar_entry.pack(pady=5)
        tutar_entry.insert(0, f"{mevcut_tutar:.2f}")
        tutar_entry.select_range(0, tk.END)
        tutar_entry.focus()

        def kaydet():
            try:
                yeni_tutar_str = tutar_entry.get().replace(",", ".").replace(" ", "").replace("₺", "")
                yeni_tutar = float(yeni_tutar_str)

                if tip == 'B':
                    kayit['borc'] = yeni_tutar
                    delta = yeni_tutar - mevcut_tutar
                else:
                    kayit['alacak'] = yeni_tutar
                    delta = -(yeni_tutar - mevcut_tutar)
                if kaynak == 'depo':
                    self.tutar_duzeltme_delta_depo += delta
                else:
                    self.tutar_duzeltme_delta_eczane += delta

                # Tree güncelle
                values = list(tree.item(item_id, 'values'))
                values[3] = self._format_tutar(kayit, goster_tip=True)
                tree.item(item_id, values=values)

                self._toplamlari_guncelle()
                duzelt_pencere.destroy()
                messagebox.showinfo("Başarılı", f"Tutar güncellendi: {yeni_tutar:,.2f} ₺")

            except ValueError:
                messagebox.showerror("Hata", "Geçerli bir tutar girin!")

        btn_frame = tk.Frame(duzelt_pencere, bg='#ECEFF1')
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="💾 Kaydet", font=("Arial", 10, "bold"), bg='#4CAF50', fg='white', width=10, command=kaydet).pack(side="left", padx=5)
        tk.Button(btn_frame, text="❌ İptal", font=("Arial", 10), bg='#f44336', fg='white', width=10, command=duzelt_pencere.destroy).pack(side="left", padx=5)

    def _kirmizi_satir_iptal(self, tree, kaynak):
        """Kırmızı paneldeki satırı iptal et"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Uyarı", "Lütfen bir satır seçin!")
            return

        item_id = selection[0]
        if kaynak == 'depo':
            data = self._kirmizi_depo_data.get(item_id)
        else:
            data = self._kirmizi_eczane_data.get(item_id)

        if not data:
            return

        fatura = data['fatura']
        kayit = data['kayit']
        tutar = self._get_tutar(kayit)[0]

        if not messagebox.askyesno("İptal Onayı",
                                   f"Bu satırı iptal etmek istiyor musunuz?\n\n"
                                   f"{'📦 Depo' if kaynak == 'depo' else '🏥 Eczane'}: {fatura}\n"
                                   f"Tutar: {tutar:,.2f} ₺"):
            return

        # İptal listesine ekle
        if kaynak == 'depo':
            self.manuel_iptal_edilenler_depo.append((fatura, kayit.copy()))
            del self._kirmizi_depo_data[item_id]
            # Seçimi temizle
            secili_items = getattr(self, '_secili_depo_items', [])
            if item_id in secili_items:
                secili_items.remove(item_id)
                self.secili_depo_satirlar = [(d['fatura'], d['kayit']) for iid in secili_items if (d := self._kirmizi_depo_data.get(iid))]
        else:
            self.manuel_iptal_edilenler_eczane.append((fatura, kayit.copy()))
            del self._kirmizi_eczane_data[item_id]
            # Seçimi temizle
            secili_items = getattr(self, '_secili_eczane_items', [])
            if item_id in secili_items:
                secili_items.remove(item_id)
                self.secili_eczane_satirlar = [(d['fatura'], d['kayit']) for iid in secili_items if (d := self._kirmizi_eczane_data.get(iid))]

        tree.delete(item_id)
        self._kirmizi_secim_guncelle()
        self._sonuclari_guncelle()
        messagebox.showinfo("Başarılı", f"Satır iptal edildi: {fatura}")

    def _kirmizi_manuel_eslestir(self):
        """Seçili depo ve eczane satırlarını manuel eşleştir (çoklu seçim destekli)"""
        depo_satirlar = getattr(self, 'secili_depo_satirlar', [])
        eczane_satirlar = getattr(self, 'secili_eczane_satirlar', [])

        if not depo_satirlar or not eczane_satirlar:
            messagebox.showwarning("Uyarı", "Lütfen hem Depo hem Eczane tarafından en az birer satır seçin!")
            return

        # Toplamları hesapla
        depo_toplam = sum(self._get_tutar(k)[0] for _, k in depo_satirlar)
        eczane_toplam = sum(self._get_tutar(k)[0] for _, k in eczane_satirlar)
        fark = abs(depo_toplam - eczane_toplam)

        # Onay mesajı oluştur
        mesaj = f"Aşağıdaki satırları manuel eşleştirmek istiyor musunuz?\n\n"
        mesaj += f"📦 DEPO ({len(depo_satirlar)} satır):\n"
        for fatura, kayit in depo_satirlar:
            tutar = self._get_tutar(kayit)[0]
            mesaj += f"  • {fatura} - {tutar:,.2f} ₺\n"
        mesaj += f"  Toplam: {depo_toplam:,.2f} ₺\n\n"

        mesaj += f"🏥 ECZANE ({len(eczane_satirlar)} satır):\n"
        for fatura, kayit in eczane_satirlar:
            tutar = self._get_tutar(kayit)[0]
            mesaj += f"  • {fatura} - {tutar:,.2f} ₺\n"
        mesaj += f"  Toplam: {eczane_toplam:,.2f} ₺\n"

        if fark > 0.01:
            mesaj += f"\n⚠️ Tutar farkı: {fark:,.2f} ₺"

        if not messagebox.askyesno("Manuel Eşleştirme Onayı", mesaj):
            return

        # Manuel eşleştirme listesine grup olarak ekle
        # Yeni format: dict with 'depo' and 'eczane' lists
        grup = {
            'depo': [(f, k.copy()) for f, k in depo_satirlar],
            'eczane': [(f, k.copy()) for f, k in eczane_satirlar],
            'depo_toplam': depo_toplam,
            'eczane_toplam': eczane_toplam
        }
        self.manuel_eslestirilenler.append(grup)

        # Tree'lerden seçili satırları sil
        depo_items = getattr(self, '_secili_depo_items', [])
        for item_id in depo_items:
            try:
                self._kirmizi_depo_tree.delete(item_id)
                if item_id in self._kirmizi_depo_data:
                    del self._kirmizi_depo_data[item_id]
            except:
                pass

        eczane_items = getattr(self, '_secili_eczane_items', [])
        for item_id in eczane_items:
            try:
                self._kirmizi_eczane_tree.delete(item_id)
                if item_id in self._kirmizi_eczane_data:
                    del self._kirmizi_eczane_data[item_id]
            except:
                pass

        # Seçimleri temizle
        self.secili_depo_satirlar = []
        self.secili_eczane_satirlar = []
        self._secili_depo_items = []
        self._secili_eczane_items = []
        if hasattr(self, '_depo_secim_toplam_label'):
            self._depo_secim_toplam_label.config(text="")
        if hasattr(self, '_eczane_secim_toplam_label'):
            self._eczane_secim_toplam_label.config(text="")
        self._kirmizi_secim_guncelle()

        self._sonuclari_guncelle()

        depo_bilgi = ", ".join(f for f, _ in grup['depo'])
        eczane_bilgi = ", ".join(f for f, _ in grup['eczane'])
        messagebox.showinfo("Başarılı",
                           f"Manuel eşleştirme yapıldı!\n\n"
                           f"📦 Depo: {depo_bilgi}\n"
                           f"🏥 Eczane: {eczane_bilgi}\n\n"
                           f"Depo Toplam: {depo_toplam:,.2f} ₺\n"
                           f"Eczane Toplam: {eczane_toplam:,.2f} ₺")

    def _tutari_esitle_ve_eslestir(self, duzeltilecek_taraf):
        """
        Sağ tıklanan tarafın tutarını karşı taraftaki seçili satırın tutarına eşitleyip eşleştir.
        duzeltilecek_taraf: 'depo' veya 'eczane' - tutarı değiştirilecek taraf
        """
        depo_satirlar = getattr(self, 'secili_depo_satirlar', [])
        eczane_satirlar = getattr(self, 'secili_eczane_satirlar', [])

        if not depo_satirlar or not eczane_satirlar:
            messagebox.showwarning("Uyarı",
                                   "Bu işlem için her iki taraftan da birer satır seçili olmalıdır!\n\n"
                                   "Önce bir taraftan satır seçin, sonra diğer taraftan da satır seçin,\n"
                                   "ardından düzeltilecek taraftaki satıra sağ tıklayın.")
            return

        if len(depo_satirlar) != 1 or len(eczane_satirlar) != 1:
            messagebox.showwarning("Uyarı", "Bu işlem için her iki taraftan yalnızca birer satır seçili olmalıdır!")
            return

        depo_fatura, depo_kayit = depo_satirlar[0]
        eczane_fatura, eczane_kayit = eczane_satirlar[0]

        depo_tutar, depo_tip = self._get_tutar(depo_kayit)
        eczane_tutar, eczane_tip = self._get_tutar(eczane_kayit)

        if duzeltilecek_taraf == 'eczane':
            # Eczane tutarı depo tutarına eşitlenecek
            referans_tutar = depo_tutar
            eski_tutar = eczane_tutar
            duzeltilen_ad = "🏥 Eczane"
            referans_ad = "📦 Depo"
            duzeltilen_fatura = eczane_fatura
            referans_fatura = depo_fatura
        else:
            # Depo tutarı eczane tutarına eşitlenecek
            referans_tutar = eczane_tutar
            eski_tutar = depo_tutar
            duzeltilen_ad = "📦 Depo"
            referans_ad = "🏥 Eczane"
            duzeltilen_fatura = depo_fatura
            referans_fatura = eczane_fatura

        fark = abs(eski_tutar - referans_tutar)

        mesaj = (
            f"{duzeltilen_ad} tarafındaki tutarı {referans_ad} tarafına eşitleyip eşleştirmek istiyor musunuz?\n\n"
            f"{referans_ad}: {referans_fatura} → {referans_tutar:,.2f} ₺ (referans)\n"
            f"{duzeltilen_ad}: {duzeltilen_fatura} → {eski_tutar:,.2f} ₺ → {referans_tutar:,.2f} ₺\n\n"
            f"Tutar farkı: {fark:,.2f} ₺\n\n"
            f"İşlem: Tutar eşitlenecek ve iki satır manuel eşleştirme olarak kaydedilecek."
        )

        if not messagebox.askyesno("Tutarı Eşitle ve Eşleştir", mesaj):
            return

        # Tutarı düzelt
        if duzeltilecek_taraf == 'eczane':
            if eczane_tip == 'B':
                delta = referans_tutar - eski_tutar
                eczane_kayit['borc'] = referans_tutar
            else:
                delta = -(referans_tutar - eski_tutar)
                eczane_kayit['alacak'] = referans_tutar
            self.tutar_duzeltme_delta_eczane += delta
        else:
            if depo_tip == 'B':
                delta = referans_tutar - eski_tutar
                depo_kayit['borc'] = referans_tutar
            else:
                delta = -(referans_tutar - eski_tutar)
                depo_kayit['alacak'] = referans_tutar
            self.tutar_duzeltme_delta_depo += delta

        # Manuel eşleştirme olarak kaydet
        grup = {
            'depo': [(depo_fatura, depo_kayit.copy())],
            'eczane': [(eczane_fatura, eczane_kayit.copy())],
            'depo_toplam': self._get_tutar(depo_kayit)[0],
            'eczane_toplam': self._get_tutar(eczane_kayit)[0]
        }
        self.manuel_eslestirilenler.append(grup)

        # Her iki tree'den satırları sil
        depo_items = getattr(self, '_secili_depo_items', [])
        for item_id in depo_items:
            try:
                self._kirmizi_depo_tree.delete(item_id)
                if item_id in self._kirmizi_depo_data:
                    del self._kirmizi_depo_data[item_id]
            except:
                pass

        eczane_items = getattr(self, '_secili_eczane_items', [])
        for item_id in eczane_items:
            try:
                self._kirmizi_eczane_tree.delete(item_id)
                if item_id in self._kirmizi_eczane_data:
                    del self._kirmizi_eczane_data[item_id]
            except:
                pass

        # Seçimleri temizle
        self.secili_depo_satirlar = []
        self.secili_eczane_satirlar = []
        self._secili_depo_items = []
        self._secili_eczane_items = []
        if hasattr(self, '_depo_secim_toplam_label'):
            self._depo_secim_toplam_label.config(text="")
        if hasattr(self, '_eczane_secim_toplam_label'):
            self._eczane_secim_toplam_label.config(text="")
        self._kirmizi_secim_guncelle()

        self._sonuclari_guncelle()

        messagebox.showinfo("Başarılı",
                           f"Tutar eşitlendi ve eşleştirme yapıldı!\n\n"
                           f"📦 Depo: {depo_fatura} → {self._get_tutar(depo_kayit)[0]:,.2f} ₺\n"
                           f"🏥 Eczane: {eczane_fatura} → {self._get_tutar(eczane_kayit)[0]:,.2f} ₺\n\n"
                           f"Düzeltme: {fark:,.2f} ₺ fark giderildi")

    def _diger_tarafa_ekle(self, tree, orijinal_kaynak):
        """Seçili satırı diğer tarafa da ekleyerek eşleştir"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Uyarı", "Lütfen bir satır seçin!")
            return

        item_id = selection[0]
        if orijinal_kaynak == 'depo':
            data = self._kirmizi_depo_data.get(item_id)
            diger_taraf = 'Eczane'
            diger_taraf_kisa = 'eczane'
        else:
            data = self._kirmizi_eczane_data.get(item_id)
            diger_taraf = 'Depo'
            diger_taraf_kisa = 'depo'

        if not data:
            messagebox.showwarning("Uyarı", "Bu satır için veri bulunamadı!")
            return

        fatura = data['fatura']
        kayit = data['kayit']
        tutar = self._get_tutar(kayit)[0]

        # Onay al
        orijinal_ad = "📦 Depo" if orijinal_kaynak == 'depo' else "🏥 Eczane"
        diger_ad = "🏥 Eczane" if orijinal_kaynak == 'depo' else "📦 Depo"

        mesaj = f"Bu satırı {diger_taraf}'ya da ekleyerek eşleştirmek istiyor musunuz?\n\n"
        mesaj += f"Fatura: {fatura}\n"
        mesaj += f"Tutar: {tutar:,.2f} ₺\n\n"
        mesaj += f"Orijinal: {orijinal_ad}'da var\n"
        mesaj += f"Eklenecek: {diger_ad}'ya manuel eklenecek\n\n"
        mesaj += f"Bu işlem sonucunda satır 'Manuel Eklenenler' bölümüne taşınacak\n"
        mesaj += f"ve her iki tarafın toplamına dahil edilecektir."

        if not messagebox.askyesno("Manuel Ekleme Onayı", mesaj):
            return

        # Manuel eklenenler listesine ekle
        self.manuel_eklenenler.append({
            'orijinal': orijinal_kaynak,
            'eklenen': diger_taraf_kisa,
            'fatura': fatura,
            'kayit': kayit.copy(),
            'aciklama': f"{orijinal_ad}'da vardı → {diger_ad}'ya manuel eklendi"
        })

        # Tree'den satırı sil
        tree.delete(item_id)
        if orijinal_kaynak == 'depo':
            if item_id in self._kirmizi_depo_data:
                del self._kirmizi_depo_data[item_id]
            # Seçimi temizle
            secili_items = getattr(self, '_secili_depo_items', [])
            if item_id in secili_items:
                secili_items.remove(item_id)
                self.secili_depo_satirlar = [(d['fatura'], d['kayit']) for iid in secili_items if (d := self._kirmizi_depo_data.get(iid))]
        else:
            if item_id in self._kirmizi_eczane_data:
                del self._kirmizi_eczane_data[item_id]
            # Seçimi temizle
            secili_items = getattr(self, '_secili_eczane_items', [])
            if item_id in secili_items:
                secili_items.remove(item_id)
                self.secili_eczane_satirlar = [(d['fatura'], d['kayit']) for iid in secili_items if (d := self._kirmizi_eczane_data.get(iid))]

        self._kirmizi_secim_guncelle()
        self._sonuclari_guncelle()

        messagebox.showinfo("Başarılı",
                           f"Manuel ekleme yapıldı!\n\n"
                           f"Fatura: {fatura}\n"
                           f"Tutar: {tutar:,.2f} ₺\n\n"
                           f"{orijinal_ad}'da vardı → {diger_ad}'ya eklendi")

    def _sonuclari_guncelle(self):
        """Manuel işlemlerden sonra sonuçları ve toplamları güncelle"""
        if not self.ekstre_sonuclar:
            return

        # Manuel eşleştirme panelini güncelle veya rebuild et
        if self.manuel_eslestirilenler:
            if hasattr(self, '_manuel_eslestirme_tree') and self._manuel_eslestirme_tree:
                self._manuel_eslestirme_panel_guncelle()
            elif hasattr(self, '_eslestirme_content_frame') and self._eslestirme_content_frame:
                # Panel açılmış ama tree oluşturulmamış (boş listeliydi) - rebuild et
                for widget in self._eslestirme_content_frame.winfo_children():
                    widget.destroy()
                self._build_manuel_eslestirme_panel(self._eslestirme_content_frame)

        # Manuel eklenenler panelini güncelle veya rebuild et
        if self.manuel_eklenenler:
            if hasattr(self, '_manuel_eklenenler_tree') and self._manuel_eklenenler_tree:
                self._manuel_eklenenler_panel_guncelle()
            elif hasattr(self, '_eklenenler_content_frame') and self._eklenenler_content_frame:
                # Panel açılmış ama tree oluşturulmamış - rebuild et
                for widget in self._eklenenler_content_frame.winfo_children():
                    widget.destroy()
                self._build_manuel_eklenenler_panel(self._eklenenler_content_frame)

        # İptal panelini güncelle veya rebuild et
        if self.manuel_iptal_edilenler_depo or self.manuel_iptal_edilenler_eczane:
            if hasattr(self, '_iptal_tree') and self._iptal_tree:
                self._iptal_panel_guncelle()
            elif hasattr(self, '_iptal_content_frame') and self._iptal_content_frame:
                # Panel açılmış ama tree oluşturulmamış - rebuild et
                for widget in self._iptal_content_frame.winfo_children():
                    widget.destroy()
                self._build_manuel_iptal_panel(self._iptal_content_frame)

        # Toplam labellarını güncelle
        self._toplamlari_guncelle()

    def _toplamlari_guncelle(self):
        """Başlıktaki toplam etiketlerini güncelle"""
        if not hasattr(self, '_sonuc_widgets') or not self._sonuc_widgets:
            return

        # Manuel iptal edilenlerin tutarını hesapla (bunlar toplamdan düşülecek)
        # Borç kaydı iptal edildi → toplamdan düş (pozitif değer)
        # Alacak kaydı (iade) iptal edildi → toplama geri ekle (negatif değer, yani çıkarılınca artar)
        iptal_depo_tutar = 0
        for _, k in self.manuel_iptal_edilenler_depo:
            tutar, tip = self._get_tutar(k)
            iptal_depo_tutar += tutar if tip == 'B' else -tutar
        iptal_eczane_tutar = 0
        for _, k in self.manuel_iptal_edilenler_eczane:
            tutar, tip = self._get_tutar(k)
            iptal_eczane_tutar += tutar if tip == 'B' else -tutar

        # Manuel eklenenlerin tutarını hesapla (bunlar diğer tarafa eklenecek)
        # Borç kaydı → diğer tarafa artı olarak eklenir
        # Alacak kaydı (iade) → diğer taraftan düşülür (negatif etki)
        eklenen_depoya = 0  # Eczane'de vardı, Depo'ya eklendi
        eklenen_eczaneye = 0  # Depo'da vardı, Eczane'ye eklendi
        for item in self.manuel_eklenenler:
            tutar, tip = self._get_tutar(item['kayit'])
            # Alacak (iade) kaydı ise negatif etki yapar
            etki = tutar if tip == 'B' else -tutar
            if item['orijinal'] == 'depo':
                # Depo'da vardı → Eczane'ye eklendi
                eklenen_eczaneye += etki
            else:
                # Eczane'de vardı → Depo'ya eklendi
                eklenen_depoya += etki

        # Tutar düzeltme deltalarını al
        duzeltme_depo = getattr(self, 'tutar_duzeltme_delta_depo', 0)
        duzeltme_eczane = getattr(self, 'tutar_duzeltme_delta_eczane', 0)

        # Orijinal toplamları al, iptal edilenleri çıkar, manuel eklenenleri ekle, düzeltmeleri uygula
        if 'depo_toplam_label' in self._sonuc_widgets:
            orijinal_depo = self._sonuc_widgets.get('orijinal_depo_toplam', 0)
            yeni_depo = orijinal_depo - iptal_depo_tutar + eklenen_depoya + duzeltme_depo
            self._sonuc_widgets['depo_toplam_label'].config(text=f"{yeni_depo:,.2f} ₺")

        if 'eczane_toplam_label' in self._sonuc_widgets:
            orijinal_eczane = self._sonuc_widgets.get('orijinal_eczane_toplam', 0)
            yeni_eczane = orijinal_eczane - iptal_eczane_tutar + eklenen_eczaneye + duzeltme_eczane
            self._sonuc_widgets['eczane_toplam_label'].config(text=f"{yeni_eczane:,.2f} ₺")

    def _build_toplam_panel(self, content_frame, yesil_satirlar, sari_satirlar, turuncu_satirlar, kirmizi_depo, kirmizi_eczane):
        """Toplamlar paneli"""
        # Doğru tutar hesaplama - borç veya alacak hangisi doluysa onu al
        def get_tutar(kayit):
            borc = kayit.get('borc', 0) or 0
            alacak = kayit.get('alacak', 0) or 0
            return borc if abs(borc) > 0.01 else abs(alacak)

        yesil_tutar = sum(get_tutar(d) for _, d, _ in yesil_satirlar)
        sari_tutar = sum(get_tutar(d) for _, _, d, _ in sari_satirlar)
        turuncu_depo_tutar = sum(get_tutar(d) for _, d, _ in turuncu_satirlar)
        turuncu_eczane_tutar = sum(get_tutar(e) for _, _, e in turuncu_satirlar)
        kirmizi_eczane_tutar = sum(get_tutar(k) for _, k in kirmizi_eczane)
        kirmizi_depo_tutar = sum(get_tutar(k) for _, k in kirmizi_depo)

        tree_fr = tk.Frame(content_frame, bg='#E3F2FD')
        tree_fr.pack(fill="both", expand=True, padx=5, pady=5)

        tree = ttk.Treeview(tree_fr, columns=("kategori", "kayit", "tutar"), show="headings", height=6)
        tree.heading("kategori", text="Kategori")
        tree.heading("kayit", text="Kayıt Sayısı")
        tree.heading("tutar", text="Toplam Tutar")
        tree.column("kategori", width=350)
        tree.column("kayit", width=120, anchor="center")
        tree.column("tutar", width=200, anchor="e")

        tree.insert("", "end", values=("🟢 Fatura No + Tutar Eşleşiyor", len(yesil_satirlar), f"{yesil_tutar:,.2f} ₺"), tags=('yesil',))
        tree.insert("", "end", values=("🟡 Tutar Eşleşiyor - Fatura No Eşleşmiyor", len(sari_satirlar), f"{sari_tutar:,.2f} ₺"), tags=('sari',))
        tree.insert("", "end", values=(f"🟠 Fatura No Eşleşiyor - Tutar Eşleşmiyor (Fark: {turuncu_depo_tutar - turuncu_eczane_tutar:,.2f} ₺)", len(turuncu_satirlar), f"Depo: {turuncu_depo_tutar:,.2f} / Eczane: {turuncu_eczane_tutar:,.2f} ₺"), tags=('turuncu',))
        tree.insert("", "end", values=("🔴 Eczane'de Var - Eşleşmiyor", len(kirmizi_eczane), f"{kirmizi_eczane_tutar:,.2f} ₺"), tags=('kirmizi',))
        tree.insert("", "end", values=("🔴 Depo'da Var - Eşleşmiyor", len(kirmizi_depo), f"{kirmizi_depo_tutar:,.2f} ₺"), tags=('kirmizi',))

        tree.tag_configure('yesil', background='#C8E6C9')
        tree.tag_configure('sari', background='#FFF9C4')
        tree.tag_configure('turuncu', background='#FFE0B2')
        tree.tag_configure('kirmizi', background='#FFCDD2')
        tree.pack(fill="both", expand=True)

    def _build_filtrelenen_panel(self, content_frame, filtrelenen_depo, filtrelenen_eczane):
        """Filtrelenen satırlar paneli"""
        tree_container = tk.Frame(content_frame, bg='#F5F5F5')
        tree_container.pack(fill="both", expand=True, pady=5)

        hdr = tk.Frame(tree_container, bg='white')
        hdr.pack(fill="x")
        tk.Label(hdr, text="📦 DEPO TARAFI", font=("Arial", 10, "bold"), bg='#B3E5FC', fg='#01579B', relief="raised", bd=1, padx=3, pady=3).pack(side="left", fill="both", expand=True)
        tk.Label(hdr, text="║", font=("Arial", 10, "bold"), bg='white', width=2).pack(side="left")
        tk.Label(hdr, text="🏥 ECZANE TARAFI", font=("Arial", 10, "bold"), bg='#C8E6C9', fg='#1B5E20', relief="raised", bd=1, padx=3, pady=3).pack(side="left", fill="both", expand=True)

        tree_fr = tk.Frame(tree_container, bg='#F5F5F5')
        tree_fr.pack(fill="both", expand=True)

        tree = ttk.Treeview(tree_fr, columns=("depo_fatura", "depo_tarih", "depo_tip", "depo_tutar", "sep", "eczane_fatura", "eczane_tarih", "eczane_tip", "eczane_tutar"), show="headings", height=10)
        for col, text, width in [("depo_fatura", "Fatura No", 140), ("depo_tarih", "Tarih", 100), ("depo_tip", "Tip", 90), ("depo_tutar", "Tutar", 110), ("sep", "║", 15), ("eczane_fatura", "Fatura No", 140), ("eczane_tarih", "Tarih", 100), ("eczane_tip", "Tip", 90), ("eczane_tutar", "Tutar", 150)]:
            tree.heading(col, text=text)
            tree.column(col, width=width, minwidth=width, anchor="e" if "tutar" in col else ("center" if col in ["sep", "depo_tarih", "eczane_tarih", "depo_tip", "eczane_tip"] else "w"), stretch=(col == "eczane_tutar"))

        tree_scroll = ttk.Scrollbar(tree_fr, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        for fatura, kayit in filtrelenen_depo:
            tutar = kayit['borc'] if abs(kayit['borc']) > 0.01 else abs(kayit['alacak'])
            tree.insert("", "end", values=(fatura, kayit.get('tarih', ''), kayit.get('tip', ''), f"{tutar:,.2f} ₺", "║", "", "", "", ""), tags=('filtrelenen',))

        for fatura, kayit in filtrelenen_eczane:
            tutar = kayit['borc'] if abs(kayit['borc']) > 0.01 else abs(kayit['alacak'])
            tree.insert("", "end", values=("", "", "", "", "║", fatura, kayit.get('tarih', ''), kayit.get('tip', ''), f"{tutar:,.2f} ₺"), tags=('filtrelenen',))

        tree.tag_configure('filtrelenen', background='#E0E0E0')

    def _build_manuel_eslestirme_panel(self, content_frame):
        """Manuel eşleştirilenler paneli"""
        # Content frame referansını sakla (rebuild için)
        self._eslestirme_content_frame = content_frame

        tree_container = tk.Frame(content_frame, bg='#E8EAF6')
        tree_container.pack(fill="both", expand=True, pady=5)

        # Bilgi etiketi
        info_label = tk.Label(
            tree_container,
            text=f"🔗 Manuel olarak eşleştirilen kayıtlar ({len(self.manuel_eslestirilenler)} adet)",
            font=("Arial", 10, "bold"),
            bg='#E8EAF6',
            fg='#3F51B5'
        )
        info_label.pack(pady=5)
        self._manuel_eslestirme_info_label = info_label

        if not self.manuel_eslestirilenler:
            self._eslestirme_bos_label = tk.Label(
                tree_container,
                text="Henüz manuel eşleştirme yapılmadı.\n\n"
                     "Eşleşmeyenler bölümünden satırlara sağ tıklayarak\n"
                     "manuel eşleştirme yapabilirsiniz.",
                font=("Arial", 10),
                bg='#E8EAF6',
                fg='#5C6BC0',
                justify="center"
            )
            self._eslestirme_bos_label.pack(pady=20)
            self._manuel_eslestirme_tree = None
            return

        hdr = tk.Frame(tree_container, bg='#E8EAF6')
        hdr.pack(fill="x")
        tk.Label(hdr, text="📦 DEPO TARAFI", font=("Arial", 10, "bold"), bg='#B3E5FC', fg='#01579B', relief="raised", bd=1, padx=3, pady=3).pack(side="left", fill="both", expand=True)
        tk.Label(hdr, text="↔", font=("Arial", 11, "bold"), bg='#E8EAF6', width=2).pack(side="left")
        tk.Label(hdr, text="🏥 ECZANE TARAFI", font=("Arial", 10, "bold"), bg='#C8E6C9', fg='#1B5E20', relief="raised", bd=1, padx=3, pady=3).pack(side="left", fill="both", expand=True)

        tree_fr = tk.Frame(tree_container, bg='#E8EAF6')
        tree_fr.pack(fill="both", expand=True)

        tree = ttk.Treeview(tree_fr, columns=("depo_fatura", "depo_tutar", "sep", "eczane_fatura", "eczane_tutar", "fark"), show="headings", height=10)
        for col, text, width in [("depo_fatura", "Depo Fatura No", 150), ("depo_tutar", "Depo Tutar", 120), ("sep", "↔", 20), ("eczane_fatura", "Eczane Fatura No", 150), ("eczane_tutar", "Eczane Tutar", 120), ("fark", "Fark", 100)]:
            tree.heading(col, text=text)
            tree.column(col, width=width, minwidth=width, anchor="e" if "tutar" in col or col == "fark" else ("center" if col == "sep" else "w"))

        tree_scroll = ttk.Scrollbar(tree_fr, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        toplam_depo = 0
        toplam_eczane = 0

        for idx, grup in enumerate(self.manuel_eslestirilenler):
            # Eski format uyumluluğu: tuple ise dict'e çevir
            if isinstance(grup, tuple):
                grup = {
                    'depo': [(grup[0], grup[1])],
                    'eczane': [(grup[2], grup[3])],
                    'depo_toplam': self._get_tutar(grup[1])[0],
                    'eczane_toplam': self._get_tutar(grup[3])[0]
                }
                self.manuel_eslestirilenler[idx] = grup

            depo_satirlari = grup['depo']
            eczane_satirlari = grup['eczane']
            grup_depo_toplam = grup['depo_toplam']
            grup_eczane_toplam = grup['eczane_toplam']
            toplam_depo += grup_depo_toplam
            toplam_eczane += grup_eczane_toplam

            coklu_grup = len(depo_satirlari) > 1 or len(eczane_satirlari) > 1

            if coklu_grup:
                # Çoklu eşleşme: önce alt toplam satırı (ana satır rengi), sonra detaylar
                fark = grup_depo_toplam - grup_eczane_toplam
                tree.insert("", "end", values=(
                    f"▸ TOPLAM ({len(depo_satirlari)} satır)",
                    f"{grup_depo_toplam:,.2f} ₺",
                    "↔",
                    f"▸ TOPLAM ({len(eczane_satirlari)} satır)",
                    f"{grup_eczane_toplam:,.2f} ₺",
                    f"{fark:,.2f} ₺" if abs(fark) > 0.01 else "✓"
                ), tags=('ana_satir',))

                # Detay satırları alt toplam satırının altında
                max_satirlar = max(len(depo_satirlari), len(eczane_satirlari))
                for i in range(max_satirlar):
                    d_fatura = depo_satirlari[i][0] if i < len(depo_satirlari) else ""
                    d_tutar = f"{self._get_tutar(depo_satirlari[i][1])[0]:,.2f} ₺" if i < len(depo_satirlari) else ""
                    e_fatura = eczane_satirlari[i][0] if i < len(eczane_satirlari) else ""
                    e_tutar = f"{self._get_tutar(eczane_satirlari[i][1])[0]:,.2f} ₺" if i < len(eczane_satirlari) else ""

                    tree.insert("", "end", values=(
                        f"    {d_fatura}" if d_fatura else "",
                        d_tutar,
                        "",
                        f"    {e_fatura}" if e_fatura else "",
                        e_tutar,
                        ""
                    ), tags=('detay',))
            else:
                # Tekli eşleşme (1:1) - ana satır rengiyle göster
                d_fatura = depo_satirlari[0][0]
                d_tutar = self._get_tutar(depo_satirlari[0][1])[0]
                e_fatura = eczane_satirlari[0][0]
                e_tutar = self._get_tutar(eczane_satirlari[0][1])[0]
                fark = d_tutar - e_tutar

                tree.insert("", "end", values=(
                    d_fatura,
                    f"{d_tutar:,.2f} ₺",
                    "↔",
                    e_fatura,
                    f"{e_tutar:,.2f} ₺",
                    f"{fark:,.2f} ₺" if abs(fark) > 0.01 else "✓"
                ), tags=('ana_satir',))

        # Ana satır rengi: tekli satırlar ve alt toplam satırları aynı renk
        tree.tag_configure('ana_satir', background='#C5CAE9')
        # Detay satırları: farklı, daha açık renk
        tree.tag_configure('detay', background='#E8EAF6')

        # Genel toplam satırı
        toplam_fark = toplam_depo - toplam_eczane
        tk.Label(
            tree_container,
            text=f"Toplam: Depo {toplam_depo:,.2f} ₺ | Eczane {toplam_eczane:,.2f} ₺ | Fark: {toplam_fark:,.2f} ₺",
            font=("Arial", 10, "bold"),
            bg='#E8EAF6',
            fg='#1A237E'
        ).pack(pady=5)

        self._manuel_eslestirme_tree = tree

    def _build_manuel_iptal_panel(self, content_frame):
        """Manuel iptal edilenler paneli"""
        # Content frame referansını sakla (rebuild için)
        self._iptal_content_frame = content_frame

        tree_container = tk.Frame(content_frame, bg='#FCE4EC')
        tree_container.pack(fill="both", expand=True, pady=5)

        toplam_iptal = len(self.manuel_iptal_edilenler_depo) + len(self.manuel_iptal_edilenler_eczane)

        # Bilgi etiketi
        info_label = tk.Label(
            tree_container,
            text=f"❌ Manuel olarak iptal edilen kayıtlar ({toplam_iptal} adet)",
            font=("Arial", 10, "bold"),
            bg='#FCE4EC',
            fg='#C2185B'
        )
        info_label.pack(pady=5)
        self._iptal_info_label = info_label

        if not self.manuel_iptal_edilenler_depo and not self.manuel_iptal_edilenler_eczane:
            self._iptal_bos_label = tk.Label(
                tree_container,
                text="Henüz manuel iptal yapılmadı.\n\n"
                     "Eşleşmeyenler bölümünden satırlara sağ tıklayarak\n"
                     "satır iptal edebilirsiniz.",
                font=("Arial", 10),
                bg='#FCE4EC',
                fg='#D81B60',
                justify="center"
            )
            self._iptal_bos_label.pack(pady=20)
            # Tree'yi yine de oluştur (güncellemeler için) ama gizle
            self._iptal_tree = None
            return

        hdr = tk.Frame(tree_container, bg='#FCE4EC')
        hdr.pack(fill="x")
        tk.Label(hdr, text="📦 DEPO İPTAL EDİLENLER", font=("Arial", 10, "bold"), bg='#FFCDD2', fg='#B71C1C', relief="raised", bd=1, padx=3, pady=3).pack(side="left", fill="both", expand=True)
        tk.Label(hdr, text="║", font=("Arial", 11, "bold"), bg='#FCE4EC', width=2).pack(side="left")
        tk.Label(hdr, text="🏥 ECZANE İPTAL EDİLENLER", font=("Arial", 10, "bold"), bg='#FFCDD2', fg='#B71C1C', relief="raised", bd=1, padx=3, pady=3).pack(side="left", fill="both", expand=True)

        tree_fr = tk.Frame(tree_container, bg='#FCE4EC')
        tree_fr.pack(fill="both", expand=True)

        tree = ttk.Treeview(tree_fr, columns=("depo_fatura", "depo_tutar", "sep", "eczane_fatura", "eczane_tutar"), show="headings", height=8)
        for col, text, width in [("depo_fatura", "Fatura No", 150), ("depo_tutar", "Tutar", 120), ("sep", "║", 20), ("eczane_fatura", "Fatura No", 150), ("eczane_tutar", "Tutar", 120)]:
            tree.heading(col, text=text)
            tree.column(col, width=width, minwidth=width, anchor="e" if "tutar" in col else ("center" if col == "sep" else "w"))

        tree_scroll = ttk.Scrollbar(tree_fr, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        toplam_depo_iptal = 0
        toplam_eczane_iptal = 0

        # Depo iptal edilenler
        for fatura, kayit in self.manuel_iptal_edilenler_depo:
            tutar = self._get_tutar(kayit)[0]
            toplam_depo_iptal += tutar
            tree.insert("", "end", values=(fatura, f"{tutar:,.2f} ₺", "║", "", ""), tags=('iptal_depo',))

        # Eczane iptal edilenler
        for fatura, kayit in self.manuel_iptal_edilenler_eczane:
            tutar = self._get_tutar(kayit)[0]
            toplam_eczane_iptal += tutar
            tree.insert("", "end", values=("", "", "║", fatura, f"{tutar:,.2f} ₺"), tags=('iptal_eczane',))

        tree.tag_configure('iptal_depo', background='#FFCDD2')
        tree.tag_configure('iptal_eczane', background='#F8BBD9')

        # Toplam satırı
        tk.Label(
            tree_container,
            text=f"İptal Toplamı: Depo {toplam_depo_iptal:,.2f} ₺ | Eczane {toplam_eczane_iptal:,.2f} ₺",
            font=("Arial", 10, "bold"),
            bg='#FCE4EC',
            fg='#880E4F'
        ).pack(pady=5)

        self._iptal_tree = tree

    def _build_manuel_eklenenler_panel(self, content_frame):
        """Manuel eklenenler paneli - tek tarafta olup diğer tarafa manuel eklenenler"""
        # Content frame referansını sakla (rebuild için)
        self._eklenenler_content_frame = content_frame

        tree_container = tk.Frame(content_frame, bg='#E0F2F1')
        tree_container.pack(fill="both", expand=True, pady=5)

        # Bilgi etiketi
        info_label = tk.Label(
            tree_container,
            text=f"➕ Diğer tarafa manuel eklenerek eşleştirilen kayıtlar ({len(self.manuel_eklenenler)} adet)",
            font=("Arial", 10, "bold"),
            bg='#E0F2F1',
            fg='#00695C'
        )
        info_label.pack(pady=5)
        self._manuel_eklenenler_info_label = info_label

        if not self.manuel_eklenenler:
            self._eklenenler_bos_label = tk.Label(
                tree_container,
                text="Henüz manuel ekleme yapılmadı.\n\n"
                     "Eşleşmeyenler bölümünden bir satıra sağ tıklayarak\n"
                     "'Eczane'ye de Ekle ve Eşleştir' veya 'Depo'ya da Ekle ve Eşleştir'\n"
                     "seçeneklerini kullanabilirsiniz.",
                font=("Arial", 10),
                bg='#E0F2F1',
                fg='#00897B',
                justify="center"
            )
            self._eklenenler_bos_label.pack(pady=20)
            self._manuel_eklenenler_tree = None
            return

        tree_fr = tk.Frame(tree_container, bg='#E0F2F1')
        tree_fr.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            tree_fr,
            columns=("fatura", "tutar", "orijinal", "eklenen", "aciklama"),
            show="headings",
            height=8
        )
        for col, text, width in [
            ("fatura", "Fatura No", 120),
            ("tutar", "Tutar", 100),
            ("orijinal", "Orijinal", 80),
            ("eklenen", "Eklenen", 80),
            ("aciklama", "Açıklama", 250)
        ]:
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="e" if col == "tutar" else "w")

        tree_scroll = ttk.Scrollbar(tree_fr, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        toplam_tutar = 0

        for item in self.manuel_eklenenler:
            fatura = item['fatura']
            kayit = item['kayit']
            orijinal = "📦 Depo" if item['orijinal'] == 'depo' else "🏥 Eczane"
            eklenen = "🏥 Eczane" if item['eklenen'] == 'eczane' else "📦 Depo"
            aciklama = item.get('aciklama', '')
            tutar = self._get_tutar(kayit)[0]
            toplam_tutar += tutar

            tree.insert("", "end", values=(
                fatura,
                f"{tutar:,.2f} ₺",
                orijinal,
                eklenen,
                aciklama
            ), tags=('eklenen',))

        tree.tag_configure('eklenen', background='#B2DFDB')

        # Toplam satırı
        tk.Label(
            tree_container,
            text=f"Manuel Eklenen Toplam: {toplam_tutar:,.2f} ₺ (Her iki tarafa da eklendi)",
            font=("Arial", 10, "bold"),
            bg='#E0F2F1',
            fg='#004D40'
        ).pack(pady=5)

        self._manuel_eklenenler_tree = tree

    def _manuel_eklenenler_panel_guncelle(self):
        """Manuel eklenenler panelini güncelle"""
        if hasattr(self, '_manuel_eklenenler_tree') and self._manuel_eklenenler_tree:
            # Mevcut tree'yi temizle
            for item_id in self._manuel_eklenenler_tree.get_children():
                self._manuel_eklenenler_tree.delete(item_id)

            # Yeni verileri ekle
            for item in self.manuel_eklenenler:
                fatura = item['fatura']
                kayit = item['kayit']
                orijinal = "📦 Depo" if item['orijinal'] == 'depo' else "🏥 Eczane"
                eklenen = "🏥 Eczane" if item['eklenen'] == 'eczane' else "📦 Depo"
                aciklama = item.get('aciklama', '')
                tutar = self._get_tutar(kayit)[0]

                self._manuel_eklenenler_tree.insert("", "end", values=(
                    fatura,
                    f"{tutar:,.2f} ₺",
                    orijinal,
                    eklenen,
                    aciklama
                ), tags=('eklenen',))

        # Info label güncelle
        if hasattr(self, '_manuel_eklenenler_info_label'):
            self._manuel_eklenenler_info_label.config(
                text=f"➕ Diğer tarafa manuel eklenerek eşleştirilen kayıtlar ({len(self.manuel_eklenenler)} adet)"
            )

    def _manuel_eslestirme_panel_guncelle(self):
        """Manuel eşleştirme panelini güncelle (çoklu eşleşme destekli)"""
        if hasattr(self, '_manuel_eslestirme_tree') and self._manuel_eslestirme_tree:
            # Rebuild: panel'i tamamen yeniden oluştur (tag_configure'ler tree oluşturulurken yapılmalı)
            if hasattr(self, '_eslestirme_content_frame') and self._eslestirme_content_frame:
                for widget in self._eslestirme_content_frame.winfo_children():
                    widget.destroy()
                self._manuel_eslestirme_tree = None
                self._build_manuel_eslestirme_panel(self._eslestirme_content_frame)
                return

        # Info label güncelle
        if hasattr(self, '_manuel_eslestirme_info_label'):
            self._manuel_eslestirme_info_label.config(
                text=f"🔗 Manuel olarak eşleştirilen kayıtlar ({len(self.manuel_eslestirilenler)} adet)"
            )

    def _iptal_panel_guncelle(self):
        """İptal panelini güncelle"""
        if hasattr(self, '_iptal_tree') and self._iptal_tree:
            # Mevcut tree'yi temizle
            for item in self._iptal_tree.get_children():
                self._iptal_tree.delete(item)

            # Depo iptal edilenler
            for fatura, kayit in self.manuel_iptal_edilenler_depo:
                tutar = self._get_tutar(kayit)[0]
                self._iptal_tree.insert("", "end", values=(fatura, f"{tutar:,.2f} ₺", "║", "", ""), tags=('iptal_depo',))

            # Eczane iptal edilenler
            for fatura, kayit in self.manuel_iptal_edilenler_eczane:
                tutar = self._get_tutar(kayit)[0]
                self._iptal_tree.insert("", "end", values=("", "", "║", fatura, f"{tutar:,.2f} ₺"), tags=('iptal_eczane',))

        # Info label güncelle
        if hasattr(self, '_iptal_info_label'):
            toplam_iptal = len(self.manuel_iptal_edilenler_depo) + len(self.manuel_iptal_edilenler_eczane)
            self._iptal_info_label.config(
                text=f"❌ Manuel olarak iptal edilen kayıtlar ({toplam_iptal} adet)"
            )

    def _get_tutar(self, kayit):
        """Kayıttan doğru tutarı al - borç veya alacak"""
        borc = kayit.get('borc', 0) or 0
        alacak = kayit.get('alacak', 0) or 0
        if abs(borc) > 0.01:
            return borc, 'B'  # Borç (giriş)
        elif abs(alacak) > 0.01:
            return alacak, 'A'  # Alacak (çıkış)
        return 0, '-'

    def _format_tutar(self, kayit, goster_tip=False):
        """Kayıttan tutarı formatla - borç/alacak durumuna göre"""
        tutar, tip = self._get_tutar(kayit)
        if goster_tip:
            tip_str = "(B)" if tip == 'B' else "(A)" if tip == 'A' else ""
            return f"{tutar:,.2f} ₺ {tip_str}"
        return f"{tutar:,.2f} ₺"

    def _bul_sutun(self, df, alternatifler):
        """DataFrame'de sütun bul — tamamen boş kolonu atla (şablon kaynağı tanımsız bırakılmış olabilir)"""
        def _kolon_bos_mu(col_name):
            try:
                seri = df[col_name]
                # NaN-only float kolonları: astype(str) NaN'leri string yapmaz, isna() ile yakala
                if seri.isna().all():
                    return True
                return seri.fillna('').astype(str).str.strip().replace('nan', '').eq('').all()
            except Exception:
                return False
        for alt in alternatifler:
            if alt in df.columns and not _kolon_bos_mu(alt):
                return alt
        for alt in alternatifler:
            alt_lower = alt.lower().replace(" ", "").replace("_", "").replace("/", "")
            for col in df.columns:
                col_lower = col.lower().replace(" ", "").replace("_", "").replace("/", "")
                if (alt_lower in col_lower or col_lower in alt_lower) and not _kolon_bos_mu(col):
                    return col
        return None

    def ekstre_sonuc_excel_aktar(self, pencere):
        """Karşılaştırma sonuçlarını Excel'e aktar"""
        import pandas as pd

        if not self.ekstre_sonuclar:
            messagebox.showwarning("Uyarı", "Önce karşılaştırma yapın!")
            return

        dosya_yolu = filedialog.asksaveasfilename(
            title="Sonuçları Kaydet",
            defaultextension=".xlsx",
            filetypes=[("Excel Dosyası", "*.xlsx")],
            initialfile=f"ekstre_karsilastirma_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        if not dosya_yolu:
            return

        try:
            sonuclar = self.ekstre_sonuclar

            with pd.ExcelWriter(dosya_yolu, engine='openpyxl') as writer:
                if sonuclar['yesil']:
                    yesil_data = [{'Fatura No': f, 'Depo Borç': d['borc'], 'Eczane Borç': e['borc'], 'Durum': 'Tam Eşleşme'} for f, d, e in sonuclar['yesil']]
                    pd.DataFrame(yesil_data).to_excel(writer, sheet_name='Yeşil-Tam Eşleşme', index=False)

                if sonuclar['sari']:
                    sari_data = [{'Depo Fatura': df, 'Eczane Fatura': ef, 'Tutar': d['borc'], 'Durum': 'Tutar Eşleşiyor'} for df, ef, d, e in sonuclar['sari']]
                    pd.DataFrame(sari_data).to_excel(writer, sheet_name='Sarı-Tutar Eşleşme', index=False)

                if sonuclar['turuncu']:
                    turuncu_data = [{'Fatura No': f, 'Depo Borç': d['borc'], 'Eczane Borç': e['borc'], 'Fark': d['borc'] - e['borc']} for f, d, e in sonuclar['turuncu']]
                    pd.DataFrame(turuncu_data).to_excel(writer, sheet_name='Turuncu-Fatura Eşleşme', index=False)

                if sonuclar['kirmizi_eczane']:
                    ke_data = [{'Fatura No': f, 'Borç': k['borc'], 'Alacak': k['alacak']} for f, k in sonuclar['kirmizi_eczane']]
                    pd.DataFrame(ke_data).to_excel(writer, sheet_name='Eczanede Var-Depoda Yok', index=False)

                if sonuclar['kirmizi_depo']:
                    kd_data = [{'Fatura No': f, 'Borç': k['borc'], 'Alacak': k['alacak']} for f, k in sonuclar['kirmizi_depo']]
                    pd.DataFrame(kd_data).to_excel(writer, sheet_name='Depoda Var-Eczanede Yok', index=False)

                ozet_data = {'Kategori': ['Tam Eşleşen', 'Tutar Eşleşen', 'Tutar Farklı', 'Eczanede Var', 'Depoda Var'], 'Kayıt Sayısı': [len(sonuclar['yesil']), len(sonuclar['sari']), len(sonuclar['turuncu']), len(sonuclar['kirmizi_eczane']), len(sonuclar['kirmizi_depo'])]}
                pd.DataFrame(ozet_data).to_excel(writer, sheet_name='Özet', index=False)

            messagebox.showinfo("Başarılı", f"Sonuçlar kaydedildi:\n{dosya_yolu}")

        except Exception as e:
            logger.error(f"Excel export hatası: {e}")
            messagebox.showerror("Hata", f"Excel'e aktarma hatası:\n{e}")

    # =========================================================================
    # İADE FATURA DETAY KARŞILAŞTIRMA
    # =========================================================================

    def _iade_fatura_detay_ac(self, tree):
        """Seçili satır(lar)ın iade faturası detayını karşılaştırma penceresini aç (çoklu seçim destekli)"""
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Uyarı", "Lütfen en az bir satır seçin!")
            return

        # Seçili satırların bilgilerini topla
        secili_faturalar = []
        for item_id in selection:
            if tree == getattr(self, '_kirmizi_depo_tree', None):
                data = self._kirmizi_depo_data.get(item_id)
            elif tree == getattr(self, '_kirmizi_eczane_tree', None):
                data = self._kirmizi_eczane_data.get(item_id)
            else:
                data = None

            if data:
                secili_faturalar.append({
                    'fatura_no': data['fatura'],
                    'tarih': data['kayit'].get('tarih', ''),
                    'tutar': self._get_tutar(data['kayit'])[0]
                })

        if not secili_faturalar:
            messagebox.showwarning("Uyarı", "Satır verisi bulunamadı!")
            return

        # Başlık bilgisi
        if len(secili_faturalar) == 1:
            baslik_text = (
                f"Fatura: {secili_faturalar[0]['fatura_no']} | "
                f"Tarih: {secili_faturalar[0]['tarih']} | "
                f"Tutar: {secili_faturalar[0]['tutar']:,.2f} ₺"
            )
            pencere_baslik = f"🔍 İade Fatura Detay - {secili_faturalar[0]['fatura_no']}"
        else:
            toplam_tutar = sum(f['tutar'] for f in secili_faturalar)
            fatura_nolar = ", ".join(f['fatura_no'] for f in secili_faturalar)
            baslik_text = (
                f"{len(secili_faturalar)} Fatura: {fatura_nolar} | "
                f"Toplam: {toplam_tutar:,.2f} ₺"
            )
            pencere_baslik = f"🔍 İade Fatura Detay - {len(secili_faturalar)} Fatura (Konsolide)"

        # Yeni pencere oluştur
        pencere = tk.Toplevel(self._sonuc_pencere or self.root)
        pencere.title(pencere_baslik)
        pencere.geometry("1400x850")
        pencere.configure(bg='#ECEFF1')
        pencere.transient(self._sonuc_pencere or self.root)

        pencere.update_idletasks()
        x = (pencere.winfo_screenwidth() - 1400) // 2
        y = max(10, (pencere.winfo_screenheight() - 850) // 2)
        pencere.geometry(f"1400x850+{x}+{y}")

        # Başlık
        baslik_frame = tk.Frame(pencere, bg='#1565C0', pady=8)
        baslik_frame.pack(fill="x")
        tk.Label(
            baslik_frame, text=f"🔍 İade Fatura Detay Karşılaştırma | {baslik_text}",
            font=("Arial", 11, "bold"), bg='#1565C0', fg='white'
        ).pack()

        # === ANA İÇERİK: PanedWindow ile üst (paneller) ve alt (sonuçlar) ===
        paned = tk.PanedWindow(pencere, orient=tk.VERTICAL, bg='#ECEFF1', sashwidth=6, sashrelief="raised")
        paned.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        # --- ÜST KISIM: İki panel yan yana ---
        panels_frame = tk.Frame(paned, bg='#ECEFF1')
        panels_frame.columnconfigure(0, weight=1)
        panels_frame.columnconfigure(1, weight=1)
        panels_frame.rowconfigure(0, weight=1)
        paned.add(panels_frame, minsize=200)

        # === SOL PANEL: DEPO (metin yapıştırma / HTML yükleme) ===
        depo_frame = tk.LabelFrame(
            panels_frame, text="📦 DEPO TARAFI (Yapıştır / HTML Yükle)",
            font=("Arial", 11, "bold"), bg='#E3F2FD', fg='#0D47A1', padx=8, pady=8
        )
        depo_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        depo_ust_frame = tk.Frame(depo_frame, bg='#E3F2FD')
        depo_ust_frame.pack(fill="x", pady=(0, 5))

        tk.Label(
            depo_ust_frame,
            text="Metin yapıştırın veya HTML fatura yükleyin:",
            font=("Arial", 9), bg='#E3F2FD', fg='#1565C0', justify="left"
        ).pack(side="left", anchor="w")

        tk.Button(
            depo_ust_frame, text="📂 HTML Fatura Yükle",
            font=("Arial", 9, "bold"), bg='#1565C0', fg='white', cursor="hand2",
            padx=8, pady=2,
            command=lambda: self._html_fatura_yukle(depo_text, depo_info_label)
        ).pack(side="right", padx=(5, 0))

        # Text + scrollbar düzgün layout: frame içinde
        depo_text_frame = tk.Frame(depo_frame, bg='#E3F2FD')
        depo_text_frame.pack(fill="both", expand=True)

        depo_text = tk.Text(depo_text_frame, font=("Consolas", 9), wrap="none", height=12, bg='white', fg='#212121')
        depo_text_scroll_y = ttk.Scrollbar(depo_text_frame, orient="vertical", command=depo_text.yview)
        depo_text_scroll_x = ttk.Scrollbar(depo_text_frame, orient="horizontal", command=depo_text.xview)
        depo_text.configure(yscrollcommand=depo_text_scroll_y.set, xscrollcommand=depo_text_scroll_x.set)

        depo_text_scroll_y.pack(side="right", fill="y")
        depo_text_scroll_x.pack(side="bottom", fill="x")
        depo_text.pack(side="left", fill="both", expand=True)

        # Depo parse bilgi label
        depo_info_label = tk.Label(
            depo_frame, text="", font=("Arial", 9, "bold"), bg='#E3F2FD', fg='#0D47A1'
        )
        depo_info_label.pack(anchor="w", pady=(3, 0))

        # === SAĞ PANEL: BOTANİK (otomatik - çoklu fatura) ===
        botanik_frame = tk.LabelFrame(
            panels_frame, text="🏥 BOTANİK TARAFI (Otomatik)",
            font=("Arial", 11, "bold"), bg='#E8F5E9', fg='#1B5E20', padx=8, pady=8
        )
        botanik_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        botanik_info_label = tk.Label(
            botanik_frame, text="Botanik veritabanından iade faturaları yükleniyor...",
            font=("Arial", 9), bg='#E8F5E9', fg='#2E7D32'
        )
        botanik_info_label.pack(anchor="w", pady=(0, 5))

        # Botanik tree + scrollbar düzgün layout
        botanik_tree_frame = tk.Frame(botanik_frame, bg='#E8F5E9')
        botanik_tree_frame.pack(fill="both", expand=True)

        botanik_tree = ttk.Treeview(
            botanik_tree_frame,
            columns=("fatura", "urun", "barkod", "miktar", "birim_fiyat", "toplam"),
            show="headings", height=12
        )
        for col, text, width, anchor in [
            ("fatura", "Fatura", 90, "w"),
            ("urun", "Ürün Adı", 220, "w"),
            ("barkod", "Barkod", 110, "w"),
            ("miktar", "Miktar", 50, "center"),
            ("birim_fiyat", "Birim Fiyat", 90, "e"),
            ("toplam", "Toplam Tutar", 100, "e")
        ]:
            botanik_tree.heading(col, text=text)
            botanik_tree.column(col, width=width, anchor=anchor)

        botanik_scroll = ttk.Scrollbar(botanik_tree_frame, orient="vertical", command=botanik_tree.yview)
        botanik_tree.configure(yscrollcommand=botanik_scroll.set)
        botanik_scroll.pack(side="right", fill="y")
        botanik_tree.pack(side="left", fill="both", expand=True)

        # Botanik verilerini tüm seçili faturalar için yükle (konsolide)
        self._botanik_iade_satirlari = []
        self._botanik_iade_konsolide_yukle(secili_faturalar, botanik_tree, botanik_info_label)

        # --- ALT KISIM: Butonlar + Sonuç alanı ---
        alt_frame = tk.Frame(paned, bg='#ECEFF1')
        paned.add(alt_frame, minsize=150)

        # Buton çubuğu
        buton_frame = tk.Frame(alt_frame, bg='#ECEFF1', pady=5)
        buton_frame.pack(fill="x")

        tk.Button(
            buton_frame, text="🔍 KARŞILAŞTIR", font=("Arial", 12, "bold"),
            bg='#4CAF50', fg='white', cursor="hand2", padx=20, pady=5,
            command=lambda: self._iade_fatura_karsilastir(pencere, depo_text, None, None)
        ).pack(side="left", padx=10)

        tk.Button(
            buton_frame, text="🔄 Botanik'ten Yeniden Yükle", font=("Arial", 10),
            bg='#2196F3', fg='white', cursor="hand2",
            command=lambda: self._botanik_iade_konsolide_yukle(secili_faturalar, botanik_tree, botanik_info_label)
        ).pack(side="left", padx=10)

        # Sonuç alanı
        sonuc_frame = tk.LabelFrame(
            alt_frame, text="📊 Karşılaştırma Sonuçları",
            font=("Arial", 11, "bold"), bg='#FFF3E0', fg='#E65100', padx=8, pady=8
        )
        sonuc_frame.pack(fill="both", expand=True, pady=(0, 5))

        self._iade_sonuc_frame = sonuc_frame
        self._iade_sonuc_tree = None

        tk.Label(
            sonuc_frame,
            text="Depo bilgilerini yapıştırın veya HTML yükleyin, sonra 'KARŞILAŞTIR' butonuna basın.",
            font=("Arial", 10), bg='#FFF3E0', fg='#F57C00', justify="center"
        ).pack(pady=20)

    def _botanik_iade_konsolide_yukle(self, secili_faturalar, tree, info_label):
        """Birden fazla fatura için Botanik'ten iade detaylarını konsolide yükle"""
        try:
            from botanik_db import BotanikDB
            db = BotanikDB()
            if not db.baglan():
                info_label.config(text="❌ Veritabanına bağlanılamadı!")
                return

            # Tree temizle
            for item in tree.get_children():
                tree.delete(item)

            tum_satirlar = []
            toplam = 0
            fatura_sayilari = {}

            for fatura_bilgi in secili_faturalar:
                fatura_no = fatura_bilgi['fatura_no']
                tarih = fatura_bilgi['tarih']

                results = db.iade_fatura_detay_getir(fatura_no=fatura_no, fatura_tarihi=tarih)

                if results:
                    fatura_sayilari[fatura_no] = len(results)
                    for r in results:
                        miktar = float(r.get('Miktar', 0) or 0)
                        birim_fiyat = float(r.get('BirimFiyat', 0) or 0)
                        toplam_tutar = float(r.get('ToplamTutar', 0) or 0)
                        urun_adi = r.get('UrunAdi', '')
                        barkod = r.get('Barkod', '') or ''
                        etiket_fiyat = float(r.get('EtiketFiyat', 0) or 0)

                        toplam += abs(toplam_tutar)

                        tree.insert("", "end", values=(
                            fatura_no,
                            urun_adi, barkod, miktar,
                            f"{abs(birim_fiyat):,.2f} ₺",
                            f"{abs(toplam_tutar):,.2f} ₺"
                        ))

                        tum_satirlar.append({
                            'fatura_no': fatura_no,
                            'urun_adi': urun_adi,
                            'barkod': barkod,
                            'miktar': abs(miktar),
                            'birim_fiyat': abs(birim_fiyat),
                            'toplam_tutar': abs(toplam_tutar),
                            'etiket_fiyat': etiket_fiyat,
                            'kaynak': r.get('Kaynak', '')
                        })
                else:
                    fatura_sayilari[fatura_no] = 0

            db.kapat()

            if not tum_satirlar:
                info_label.config(text=f"⚠️ Seçili faturalar için iade detayı bulunamadı")
            else:
                fatura_ozet = " + ".join(f"{no}({sayi})" for no, sayi in fatura_sayilari.items())
                info_label.config(
                    text=f"✅ {len(tum_satirlar)} kalem | {len(fatura_sayilari)} fatura [{fatura_ozet}] | Toplam: {toplam:,.2f} ₺"
                )

            self._botanik_iade_satirlari = tum_satirlar

        except Exception as e:
            logger.error(f"Botanik iade fatura yükleme hatası: {e}")
            info_label.config(text=f"❌ Hata: {e}")

    def _html_fatura_yukle(self, depo_text_widget, info_label):
        """HTML fatura dosyası seç ve parse et"""
        from tkinter import filedialog
        parent_pencere = depo_text_widget.winfo_toplevel()
        dosya = filedialog.askopenfilename(
            title="İade Fatura HTML Dosyası Seçin",
            filetypes=[("HTML dosyaları", "*.html *.htm"), ("Tüm dosyalar", "*.*")],
            initialdir=os.path.expanduser("~/Downloads"),
            parent=parent_pencere
        )
        if not dosya:
            return

        try:
            # Encoding dene
            for enc in ['utf-8', 'cp1254', 'latin-1']:
                try:
                    with open(dosya, 'r', encoding=enc) as f:
                        html_icerik = f.read()
                    break
                except UnicodeDecodeError:
                    continue
            else:
                messagebox.showerror("Hata", "Dosya okunamadı (encoding hatası)", parent=parent_pencere)
                return

            satirlar = self._html_fatura_parse(html_icerik)
            if not satirlar:
                messagebox.showwarning("Uyarı", "HTML dosyasında ürün satırı bulunamadı!", parent=parent_pencere)
                return

            # Parse edilen verileri _depo_html_satirlari olarak sakla
            self._depo_html_satirlari = satirlar

            # Text widget'a formatlanmış özet yaz
            depo_text_widget.delete("1.0", tk.END)

            # Fatura meta bilgisi varsa başa yaz
            meta = getattr(self, '_html_fatura_meta', {})
            if meta:
                depo_text_widget.insert(tk.END,
                    f"FATURA: {meta.get('no', '?')} | "
                    f"TARİH: {meta.get('tarih', '?')} | "
                    f"TİP: {meta.get('tip', '?')} | "
                    f"TOPLAM: {meta.get('odenecek', '?')} TL\n"
                    f"{'─' * 100}\n"
                )

            # Sütun başlıkları
            baslik = f"{'Barkod':<15} {'Ürün Adı':<38} {'Etiket':>10} {'KDV%':>5} {'Depocu':>10} {'K.İsk%':>6} {'Net Fyt':>10} {'Adet':>5} {'Tutar':>12}"
            depo_text_widget.insert(tk.END, baslik + "\n")
            depo_text_widget.insert(tk.END, "─" * len(baslik) + "\n")

            toplam = 0
            for s in satirlar:
                tutar = s.get('tutar', 0) or 0
                toplam += tutar
                barkod = s.get('barkod', '') or ''
                etiket = f"{s['etiket_fiyat']:,.2f}" if s.get('etiket_fiyat') else "-"
                kdv = f"{s['kdv_orani']:.0f}" if s.get('kdv_orani') is not None else "-"
                depocu = f"{s['depocu_fiyat']:,.2f}" if s.get('depocu_fiyat') else "-"
                kurum = f"{s['kurum_iskonto']:.1f}" if s.get('kurum_iskonto') is not None else "-"
                net = f"{s['net_fiyat']:,.2f}" if s.get('net_fiyat') else "-"
                satir = f"{barkod:<15} {s['urun_adi']:<38} {etiket:>10} {kdv:>5} {depocu:>10} {kurum:>6} {net:>10} {s['miktar']:>5} {tutar:>12,.2f}"
                depo_text_widget.insert(tk.END, satir + "\n")

            depo_text_widget.insert(tk.END, f"{'─' * len(baslik)}\n")
            depo_text_widget.insert(tk.END, f"{'TOPLAM':>89} {toplam:>12,.2f}\n")

            info_label.config(
                text=f"✅ HTML fatura yüklendi: {len(satirlar)} kalem | Toplam: {toplam:,.2f} ₺ | {os.path.basename(dosya)}"
            )

        except Exception as e:
            logger.error(f"HTML fatura yükleme hatası: {e}", exc_info=True)
            messagebox.showerror("Hata", f"HTML fatura parse edilemedi:\n{e}", parent=parent_pencere)

    def _html_fatura_parse(self, html_icerik):
        """
        Selçuk Ecza HTML fatura formatını parse et.
        Sütunlar: Barkod, Ürün Adı, Etiket Fyt, KDV%, Ecz.Kar%, Depocu Fyt,
                   Kurum İsk, Satış İsk, Net Fyt, Miktar (alınan+bedava), Tutar
        """
        import re
        import json

        satirlar = []

        # Fatura meta bilgisi (QR JSON)
        qr_match = re.search(r'id="qrvalue"[^>]*>(.*?)</div>', html_icerik, re.DOTALL)
        if qr_match:
            try:
                self._html_fatura_meta = json.loads(qr_match.group(1).strip())
            except json.JSONDecodeError:
                self._html_fatura_meta = {}
        else:
            self._html_fatura_meta = {}

        def temizle_sayi(s):
            """Türkçe/Amerikan sayı formatını float'a çevir"""
            s = s.strip().replace(' ', '').replace('\xa0', '')
            if not s or s == '-':
                return None
            # Türkçe: 1.650,61 → 1650.61
            if ',' in s and '.' in s:
                last_comma = s.rfind(',')
                last_dot = s.rfind('.')
                if last_comma > last_dot:
                    s = s.replace('.', '').replace(',', '.')
                else:
                    s = s.replace(',', '')
            elif ',' in s:
                s = s.replace(',', '.')
            s = s.replace('₺', '').replace('TL', '').strip()
            try:
                return abs(float(s))
            except ValueError:
                return None

        # Ürün satırlarını bul: <tr><td>13-haneli-barkod</td>...
        rows = re.findall(r'<tr><td[^>]*>(\d{13})</td>(.*?)</tr>', html_icerik, re.DOTALL)

        for barkod, rest in rows:
            # Tüm td hücrelerini al
            cells = re.findall(r'<td[^>]*>(.*?)</td>', rest, re.DOTALL)
            cleaned = [re.sub(r'<[^>]+>', '', c).strip().replace('\n', ' ').replace('\t', '') for c in cells]
            cleaned = [' '.join(c.split()) for c in cleaned]  # Çoklu boşlukları teke indir

            if len(cleaned) < 9:
                continue

            # Sütun sırası: 0:ÜrünAdı, 1:EtiketFyt, 2:KDV%, 3:EczKar%, 4:DepocuFyt,
            #               5:KurumIsk, 6:SatışIsk, 7:NetFyt, 8:Miktar(a+b), 9:Tutar
            urun_adi = cleaned[0]
            etiket_fiyat = temizle_sayi(cleaned[1])
            kdv_orani = temizle_sayi(cleaned[2])
            depocu_fiyat = temizle_sayi(cleaned[4])
            kurum_iskonto = temizle_sayi(cleaned[5]) if cleaned[5] else None
            net_fiyat = temizle_sayi(cleaned[7])

            # Miktar: "4 + 2,00" veya "1 + 0,00" formatı
            miktar = 1
            miktar_raw = cleaned[8] if len(cleaned) > 8 else ""
            if '+' in miktar_raw:
                try:
                    parcalar = miktar_raw.split('+')
                    miktar = sum(abs(float(p.strip().replace(',', '.'))) for p in parcalar)
                    miktar = int(miktar)
                except ValueError:
                    miktar = 1
            elif miktar_raw:
                try:
                    miktar = int(float(miktar_raw.replace(',', '.')))
                except ValueError:
                    miktar = 1

            tutar = temizle_sayi(cleaned[9]) if len(cleaned) > 9 else None

            satirlar.append({
                'urun_adi': urun_adi,
                'barkod': barkod,
                'etiket_fiyat': etiket_fiyat,
                'kdv_orani': kdv_orani,
                'depocu_fiyat': depocu_fiyat,
                'kurum_iskonto': kurum_iskonto,
                'net_fiyat': net_fiyat,
                'miktar': miktar,
                'tutar': tutar,
            })

        return satirlar

    def _depo_metin_parse(self, metin):
        """
        Depo sisteminden yapıştırılan iade fatura metnini parse et.
        Tab-separated format beklenir.
        """
        satirlar = []
        lines = metin.strip().split('\n')
        if not lines:
            return satirlar

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Tab ile ayır
            parts = line.split('\t')
            if len(parts) < 2:
                # Tab yoksa birden fazla boşlukla dene
                parts = [p for p in line.split('  ') if p.strip()]

            if len(parts) < 3:
                continue

            # Başlık satırını ve fatura ayırıcı satırları atla
            ilk_hucre = parts[0].strip().upper()
            if ilk_hucre in ['ÜRÜN ADI', 'URUN ADI', 'ÜRÜN', 'FATURA', 'ADI', '', 'ÜRÜN ADI']:
                continue
            # Tek kelimelik satırları atla (fatura numarası vs.)
            if len(parts) <= 2 and not any(c.isdigit() and '.' in parts[-1] for c in parts[-1] if c.isdigit()):
                # Tek hücrede sadece metin varsa muhtemelen fatura başlığı
                all_alpha = all(not p.strip() or not any(c.isdigit() for c in p.strip()) for p in parts)
                if all_alpha:
                    continue

            # Ürün adı ilk sütun
            urun_adi = parts[0].strip()
            if not urun_adi:
                continue

            # Sayısal değerleri bul
            def temizle_sayi(s):
                """Sayısal değeri temizle: -1,650.61 → 1650.61"""
                s = s.strip().replace(' ', '')
                # Türkçe format: 1.650,61 veya Amerikan format: 1,650.61
                if ',' in s and '.' in s:
                    # Hangisi son: o ondalık ayıracı
                    last_comma = s.rfind(',')
                    last_dot = s.rfind('.')
                    if last_comma > last_dot:
                        # Türkçe: 1.650,61
                        s = s.replace('.', '').replace(',', '.')
                    else:
                        # Amerikan: 1,650.61
                        s = s.replace(',', '')
                elif ',' in s:
                    s = s.replace(',', '.')

                s = s.replace('₺', '').replace('TL', '').strip()
                try:
                    return abs(float(s))
                except ValueError:
                    return None

            # Miktarı bul: "-1 + 0" veya "-2 + 0" formatı
            miktar = None
            miktar_idx = None
            for i, part in enumerate(parts):
                part_clean = part.strip()
                if '+' in part_clean and any(c.isdigit() for c in part_clean):
                    # "-1 + 0" formatı
                    try:
                        parcalar = part_clean.split('+')
                        m = sum(abs(int(p.strip())) for p in parcalar)
                        miktar = m
                        miktar_idx = i
                        break
                    except ValueError:
                        pass

            # Tutarı bul: son sütun genellikle tutar
            tutar = None
            for i in range(len(parts) - 1, -1, -1):
                val = temizle_sayi(parts[i])
                if val is not None and val > 0:
                    tutar = val
                    break

            # Etiket fiyatı: ikinci sütun genelde etiket fiyatı
            etiket_fiyat = None
            if len(parts) > 1:
                etiket_fiyat = temizle_sayi(parts[1])

            # Net fiyat: "Net Fyt" sütunu (genelde 8. sütun, 0-indexed: 7)
            net_fiyat = None
            # Depocu fiyat sütunu (genelde 6. sütun, 0-indexed: 5)
            depocu_fiyat = None

            # Sütun indexlerine göre parse (standart Selçuk Ecza formatı)
            # 0: Ürün Adı, 1: Etiket Fyt, 2: KDV, 3: Ecz.Kar., 4: Depocu Fyt,
            # 5: Kurum Isk, 6: Satış Isk, 7: Net Fyt, 8: Miktarı, 9: Tutarı
            kdv_orani = None
            kurum_iskonto = None

            if len(parts) >= 10:
                # Tam format: Ürün, Etiket, KDV, Ecz.Kar, Depocu, Kurum Isk, Satış Isk, Net Fyt, Miktar, Tutar
                kdv_orani = temizle_sayi(parts[2])
                depocu_fiyat = temizle_sayi(parts[4])
                kurum_iskonto = temizle_sayi(parts[5])
                net_fiyat = temizle_sayi(parts[7])
            elif len(parts) == 9:
                # Satış Isk boş olduğunda 9 parça: Ürün, Etiket, KDV, Ecz.Kar, Depocu, Kurum Isk, Net Fyt, Miktar, Tutar
                kdv_orani = temizle_sayi(parts[2])
                depocu_fiyat = temizle_sayi(parts[4])
                kurum_iskonto = temizle_sayi(parts[5])
                net_fiyat = temizle_sayi(parts[6])

            # Miktar bulunamadıysa ve tutar/net_fiyat varsa hesapla
            if miktar is None and tutar and net_fiyat and net_fiyat > 0:
                miktar = round(tutar / net_fiyat)

            if miktar is None:
                miktar = 1  # Default

            satirlar.append({
                'urun_adi': urun_adi,
                'etiket_fiyat': etiket_fiyat,
                'kdv_orani': kdv_orani,
                'depocu_fiyat': depocu_fiyat,
                'kurum_iskonto': kurum_iskonto,
                'net_fiyat': net_fiyat,
                'miktar': miktar,
                'tutar': tutar,
                'barkod': None  # Depo formatında barkod yok
            })

        return satirlar

    def _ilac_ismi_normalize(self, isim):
        """İlaç ismini karşılaştırma için normalize et"""
        if not isim:
            return ""
        # Büyük harf, gereksiz boşluklar temizle
        s = isim.upper().strip()
        # Noktalama temizle
        for ch in ['.', ',', '(', ')', '/', '-', "'", '"']:
            s = s.replace(ch, ' ')
        # Çoklu boşlukları teke indir
        s = ' '.join(s.split())
        return s

    def _ilac_ismi_benzerlik(self, isim1, isim2):
        """İki ilaç isminin benzerlik skoru (0-1)"""
        n1 = self._ilac_ismi_normalize(isim1)
        n2 = self._ilac_ismi_normalize(isim2)

        if n1 == n2:
            return 1.0

        # Kelime bazlı karşılaştırma
        words1 = set(n1.split())
        words2 = set(n2.split())

        if not words1 or not words2:
            return 0.0

        ortak = words1 & words2
        toplam = words1 | words2

        return len(ortak) / len(toplam)

    def _iade_fatura_karsilastir(self, pencere, depo_text_widget, _unused1, _unused2):
        """İade fatura detaylarını karşılaştır ve sonuçları göster (konsolide)"""
        try:
            # HTML'den yüklenen veriler varsa onları kullan
            depo_satirlari = getattr(self, '_depo_html_satirlari', None)

            if not depo_satirlari:
                # Text widget'tan parse et
                depo_metin = depo_text_widget.get("1.0", tk.END)
                if not depo_metin.strip():
                    messagebox.showwarning("Uyarı",
                                           "Lütfen depo iade fatura bilgilerini yapıştırın\nveya HTML fatura yükleyin!",
                                           parent=pencere)
                    return

                depo_satirlari = self._depo_metin_parse(depo_metin)
                if not depo_satirlari:
                    messagebox.showwarning("Uyarı",
                                           "Depo metni parse edilemedi!\n\n"
                                           "Beklenen format (tab veya çift boşluk):\n"
                                           "Ürün Adı  Etiket Fyt  KDV  ...  Miktarı  Tutarı\n\n"
                                           "Veya '📂 HTML Fatura Yükle' butonunu kullanın.",
                                           parent=pencere)
                    return

            logger.info(f"Karşılaştırma: {len(depo_satirlari)} depo satırı")

            # Botanik verilerini al
            botanik_satirlari = getattr(self, '_botanik_iade_satirlari', [])
            logger.info(f"Botanik: {len(botanik_satirlari)} satır")

            if botanik_satirlari:
                # Eşleştirme yap
                eslesme_sonuclari = self._iade_satirlari_eslestir(depo_satirlari, botanik_satirlari)
                # Sonuçları göster
                self._iade_sonuclari_goster(eslesme_sonuclari, depo_satirlari, botanik_satirlari)
            else:
                # Botanik verisi yok - sadece depo parse sonuçlarını göster
                self._depo_parse_sonuclari_goster(depo_satirlari)

        except Exception as e:
            import traceback
            hata_detay = traceback.format_exc()
            logger.error(f"Karşılaştırma hatası: {hata_detay}")
            # Hata detayını dosyaya yaz
            try:
                with open("depo_ekstre_hata.log", "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\n{datetime.now()}\n{hata_detay}\n")
            except Exception:
                pass
            messagebox.showerror("Hata",
                                 f"Karşılaştırma sırasında hata oluştu:\n\n{e}\n\n"
                                 f"Detay: depo_ekstre_hata.log dosyasına yazıldı.",
                                 parent=pencere)

    def _depo_parse_sonuclari_goster(self, depo_satirlari):
        """Botanik verisi yokken sadece depo parse sonuçlarını formatlanmış tablo olarak göster"""
        # Sonuç frame temizle
        for widget in self._iade_sonuc_frame.winfo_children():
            widget.destroy()

        tree_container = tk.Frame(self._iade_sonuc_frame, bg='#FFF3E0')
        tree_container.pack(fill="both", expand=True)

        toplam_tutar = sum(d.get('tutar', 0) or 0 for d in depo_satirlari)
        ozet = (
            f"📦 Depo Faturası: {len(depo_satirlari)} kalem | "
            f"Toplam: {toplam_tutar:,.2f} ₺ | "
            f"⚠️ Botanik verisi yüklenmedi - sadece depo tarafı gösteriliyor"
        )
        tk.Label(
            tree_container, text=ozet,
            font=("Arial", 10, "bold"), bg='#FFF3E0', fg='#E65100'
        ).pack(pady=5)

        tree_fr = tk.Frame(tree_container, bg='#FFF3E0')
        tree_fr.pack(fill="both", expand=True)

        columns = ("no", "urun", "miktar", "etiket_fyt", "net_fyt", "tutar", "kdv", "kurum_isk")
        tree = ttk.Treeview(tree_fr, columns=columns, show="headings", height=14)

        for col, text, width, anchor in [
            ("no", "#", 35, "center"),
            ("urun", "Ürün Adı", 280, "w"),
            ("miktar", "Miktar", 55, "center"),
            ("etiket_fyt", "Etiket Fyt", 95, "e"),
            ("net_fyt", "Net Fyt", 95, "e"),
            ("tutar", "Tutar", 100, "e"),
            ("kdv", "KDV %", 55, "center"),
            ("kurum_isk", "Kurum İsk %", 75, "center"),
        ]:
            tree.heading(col, text=text)
            tree.column(col, width=width, minwidth=width, anchor=anchor)

        tree_scroll = ttk.Scrollbar(tree_fr, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        for i, d in enumerate(depo_satirlari, 1):
            etiket = f"{d['etiket_fiyat']:,.2f}" if d.get('etiket_fiyat') else "-"
            net = f"{d['net_fiyat']:,.2f}" if d.get('net_fiyat') else "-"
            tutar = f"{d['tutar']:,.2f}" if d.get('tutar') else "-"
            kdv = f"{d['kdv_orani']:.0f}" if d.get('kdv_orani') is not None else "-"
            kurum = f"{d['kurum_iskonto']:.1f}" if d.get('kurum_iskonto') is not None else "-"

            tree.insert("", "end", values=(
                i, d['urun_adi'], d['miktar'], etiket, net, tutar, kdv, kurum
            ))

        # Alt toplam satırı
        tk.Label(
            tree_container,
            text=f"Toplam: {len(depo_satirlari)} kalem | {toplam_tutar:,.2f} ₺",
            font=("Arial", 10, "bold"), bg='#FFF3E0', fg='#BF360C'
        ).pack(pady=(3, 5))

    def _iade_satirlari_eslestir(self, depo_satirlari, botanik_satirlari):
        """
        Depo ve Botanik satırlarını eşleştir.
        Öncelik: Barkod > İlaç ismi benzerliği
        Aynı isimli birden fazla satırda miktar+tutar yakınlığı da dikkate alınır.
        """
        eslesmeler = []
        kullanilan_botanik = set()
        kullanilan_depo = set()

        # Tüm olası eşleşmeleri skorla
        adaylar = []
        for d_idx, depo in enumerate(depo_satirlari):
            for b_idx, botanik in enumerate(botanik_satirlari):
                skor = 0.0

                # Barkod eşleşmesi
                if depo.get('barkod') and botanik.get('barkod'):
                    if depo['barkod'] == botanik['barkod']:
                        skor = 1.0

                # İsim benzerliği
                if skor < 1.0:
                    skor = self._ilac_ismi_benzerlik(depo['urun_adi'], botanik['urun_adi'])

                if skor >= 0.4:
                    # Miktar eşleşmesi bonus (aynı isimli çoklu satırları doğru eşleştirmek için)
                    d_miktar = int(depo.get('miktar', 0) or 0)
                    b_miktar = int(botanik.get('miktar', 0) or 0)
                    d_tutar = float(depo.get('tutar', 0) or 0)
                    b_tutar = float(botanik.get('toplam_tutar', 0) or 0)

                    miktar_bonus = 0.05 if d_miktar == b_miktar else 0
                    tutar_bonus = 0.03 if abs(d_tutar - b_tutar) < 1.0 else 0

                    adaylar.append({
                        'depo_idx': d_idx,
                        'botanik_idx': b_idx,
                        'skor': skor + miktar_bonus + tutar_bonus,
                        'benzerlik': skor
                    })

        # En yüksek skordan başlayarak eşleştir (greedy)
        adaylar.sort(key=lambda x: x['skor'], reverse=True)

        for aday in adaylar:
            d_idx = aday['depo_idx']
            b_idx = aday['botanik_idx']

            if d_idx in kullanilan_depo or b_idx in kullanilan_botanik:
                continue

            eslesmeler.append({
                'depo_idx': d_idx,
                'botanik_idx': b_idx,
                'depo': depo_satirlari[d_idx],
                'botanik': botanik_satirlari[b_idx],
                'benzerlik': aday['benzerlik']
            })
            kullanilan_depo.add(d_idx)
            kullanilan_botanik.add(b_idx)

        # Eşleşmeyenler
        eslesmeyen_depo = [
            (i, depo_satirlari[i]) for i in range(len(depo_satirlari))
            if i not in kullanilan_depo
        ]
        eslesmeyen_botanik = [
            (i, botanik_satirlari[i]) for i in range(len(botanik_satirlari))
            if i not in kullanilan_botanik
        ]

        return {
            'eslesmeler': eslesmeler,
            'eslesmeyen_depo': eslesmeyen_depo,
            'eslesmeyen_botanik': eslesmeyen_botanik
        }

    def _iade_sonuclari_goster(self, sonuclar, depo_satirlari, botanik_satirlari):
        """İade karşılaştırma sonuçlarını göster"""
        # Sonuç frame'i temizle
        for widget in self._iade_sonuc_frame.winfo_children():
            widget.destroy()

        eslesmeler = sonuclar['eslesmeler']
        eslesmeyen_depo = sonuclar['eslesmeyen_depo']
        eslesmeyen_botanik = sonuclar['eslesmeyen_botanik']

        # Kategorize et
        tam_tutan = []       # Miktar + Tutar tutuyor
        kurus_fark = []      # Miktar tutuyor, tutar 1 kuruş fark
        tutar_farkli = []    # Miktar tutuyor ama tutar farklı
        miktar_farkli = []   # Miktar tutmuyor

        for eslesme in eslesmeler:
            depo = eslesme['depo']
            botanik = eslesme['botanik']

            d_miktar = int(depo.get('miktar', 0) or 0)
            b_miktar = int(botanik.get('miktar', 0) or 0)
            d_tutar = float(depo.get('tutar', 0) or 0)
            b_tutar = float(botanik.get('toplam_tutar', 0) or 0)
            tutar_fark = abs(d_tutar - b_tutar)

            miktar_esit = (d_miktar == b_miktar)

            if miktar_esit and tutar_fark <= 0.001:
                tam_tutan.append(eslesme)
            elif miktar_esit and tutar_fark <= 0.05:
                kurus_fark.append(eslesme)
            elif miktar_esit:
                tutar_farkli.append(eslesme)
            else:
                miktar_farkli.append(eslesme)

        # === SONUÇ TREE ===
        tree_container = tk.Frame(self._iade_sonuc_frame, bg='#FFF3E0')
        tree_container.pack(fill="both", expand=True)

        # Özet
        ozet_text = (
            f"🟢 Tam Tutan: {len(tam_tutan)} | "
            f"🟡 Kuruş Fark: {len(kurus_fark)} | "
            f"🟠 Tutar Farklı: {len(tutar_farkli)} | "
            f"🔴 Miktar Farklı: {len(miktar_farkli)} | "
            f"❌ Depo'da Fazla: {len(eslesmeyen_depo)} | "
            f"❌ Botanik'te Fazla: {len(eslesmeyen_botanik)}"
        )
        tk.Label(
            tree_container, text=ozet_text,
            font=("Arial", 9, "bold"), bg='#FFF3E0', fg='#E65100'
        ).pack(pady=5)

        # Depo ve Botanik toplamları
        depo_toplam = sum(float(d.get('tutar', 0) or 0) for d in depo_satirlari)
        botanik_toplam = sum(float(b.get('toplam_tutar', 0) or 0) for b in botanik_satirlari)
        fark = abs(depo_toplam - botanik_toplam)

        toplam_text = (
            f"Depo Toplam: {depo_toplam:,.2f} ₺ | "
            f"Botanik Toplam: {botanik_toplam:,.2f} ₺ | "
            f"Fark: {fark:,.2f} ₺"
        )
        tk.Label(
            tree_container, text=toplam_text,
            font=("Arial", 10, "bold"), bg='#FFF3E0', fg='#BF360C'
        ).pack(pady=(0, 5))

        tree_fr = tk.Frame(tree_container, bg='#FFF3E0')
        tree_fr.pack(fill="both", expand=True)

        columns = ("durum", "depo_urun", "d_miktar", "d_birim", "d_tutar",
                    "kdv_dahil", "sep", "b_urun", "b_miktar", "b_birim", "b_tutar", "duzeltme")
        tree = ttk.Treeview(tree_fr, columns=columns, show="headings", height=12)

        col_specs = [
            ("durum", "Durum", 40, "center"),
            ("depo_urun", "Depo Ürün", 200, "w"),
            ("d_miktar", "Adet", 45, "center"),
            ("d_birim", "Net Fyt", 85, "e"),
            ("d_tutar", "Tutar", 95, "e"),
            ("kdv_dahil", "KDV Dahil Birim", 100, "e"),
            ("sep", "↔", 20, "center"),
            ("b_urun", "Botanik Ürün", 200, "w"),
            ("b_miktar", "Adet", 45, "center"),
            ("b_birim", "Birim Fyt", 85, "e"),
            ("b_tutar", "Tutar", 95, "e"),
            ("duzeltme", "Düzeltme", 200, "w"),
        ]
        for col, text, width, anchor in col_specs:
            tree.heading(col, text=text)
            tree.column(col, width=width, minwidth=width, anchor=anchor)

        tree_scroll = ttk.Scrollbar(tree_fr, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # KDV dahil birim fiyat hesaplama: (tutar / miktar) × (1 + KDV%/100)
        def kdv_dahil_birim(d):
            """Fatura tutarını adet sayısına böl, KDV ekle → Botanik birim fiyatı"""
            tutar = float(d.get('tutar', 0) or 0)
            miktar = max(int(d.get('miktar', 1) or 1), 1)
            kdv = d.get('kdv_orani')
            birim_kdvsiz = tutar / miktar
            kdv_oran = float(kdv) if kdv is not None else 10.0
            return birim_kdvsiz * (1 + kdv_oran / 100)

        def fmt_kdv_dahil(d):
            return f"{kdv_dahil_birim(d):,.2f}"

        # 1. Tam tutan satırlar
        for eslesme in tam_tutan:
            d = eslesme['depo']
            b = eslesme['botanik']
            tree.insert("", "end", values=(
                "🟢", d['urun_adi'],
                d['miktar'], f"{d.get('net_fiyat') or float(d.get('tutar', 0) or 0) / max(d['miktar'], 1):,.2f}",
                f"{float(d.get('tutar', 0) or 0):,.2f}",
                fmt_kdv_dahil(d),
                "↔",
                b['urun_adi'], b['miktar'],
                f"{float(b['birim_fiyat']):,.2f}", f"{float(b['toplam_tutar']):,.2f}",
                "✓ Tutuyor"
            ), tags=('tutan',))

        # 2. Kuruş fark satırlar
        for eslesme in kurus_fark:
            d = eslesme['depo']
            b = eslesme['botanik']
            fark_tutar = float(d.get('tutar', 0) or 0) - float(b.get('toplam_tutar', 0) or 0)
            tree.insert("", "end", values=(
                "🟡", d['urun_adi'],
                d['miktar'], f"{d.get('net_fiyat') or float(d.get('tutar', 0) or 0) / max(d['miktar'], 1):,.2f}",
                f"{float(d.get('tutar', 0) or 0):,.2f}",
                fmt_kdv_dahil(d),
                "↔",
                b['urun_adi'], b['miktar'],
                f"{float(b['birim_fiyat']):,.2f}", f"{float(b['toplam_tutar']):,.2f}",
                f"~{fark_tutar:+,.2f} ₺ kuruş fark"
            ), tags=('kurus',))

        # 3. Tutar farklı satırlar
        for eslesme in tutar_farkli:
            d = eslesme['depo']
            b = eslesme['botanik']
            d_tutar = float(d.get('tutar', 0) or 0)
            b_tutar = float(b.get('toplam_tutar', 0) or 0)
            fark_tutar = d_tutar - b_tutar

            kdv_birim = kdv_dahil_birim(d)
            duzeltme = f"Birim→{kdv_birim:,.2f} Toplam→{d_tutar:,.2f}"

            tree.insert("", "end", values=(
                "🟠", d['urun_adi'],
                d['miktar'], f"{d.get('net_fiyat') or d_tutar / max(d['miktar'], 1):,.2f}",
                f"{d_tutar:,.2f}",
                fmt_kdv_dahil(d),
                "↔",
                b['urun_adi'], b['miktar'],
                f"{float(b['birim_fiyat']):,.2f}", f"{b_tutar:,.2f}",
                duzeltme
            ), tags=('tutar_farkli',))

        # 4. Miktar farklı satırlar
        for eslesme in miktar_farkli:
            d = eslesme['depo']
            b = eslesme['botanik']
            d_tutar = float(d.get('tutar', 0) or 0)
            b_tutar = float(b.get('toplam_tutar', 0) or 0)

            kdv_birim = kdv_dahil_birim(d)
            duzeltme = f"Adet→{d['miktar']} Birim→{kdv_birim:,.2f} Toplam→{d_tutar:,.2f}"

            tree.insert("", "end", values=(
                "🔴", d['urun_adi'],
                d['miktar'], f"{d.get('net_fiyat') or d_tutar / max(d['miktar'], 1):,.2f}",
                f"{d_tutar:,.2f}",
                fmt_kdv_dahil(d),
                "↔",
                b['urun_adi'], b['miktar'],
                f"{float(b['birim_fiyat']):,.2f}", f"{b_tutar:,.2f}",
                duzeltme
            ), tags=('miktar_farkli',))

        # 5. Depo'da var Botanik'te yok
        for idx, depo in eslesmeyen_depo:
            d_tutar = float(depo.get('tutar', 0) or 0)
            kdv_birim = kdv_dahil_birim(depo)
            tree.insert("", "end", values=(
                "❌", depo['urun_adi'],
                depo['miktar'], f"{depo.get('net_fiyat') or d_tutar / max(depo['miktar'], 1):,.2f}",
                f"{d_tutar:,.2f}",
                fmt_kdv_dahil(depo),
                "",
                "— BOTANİK'TE YOK —", "", "", "",
                f"Ekle: {depo['miktar']} ad. {kdv_birim:,.2f} ₺"
            ), tags=('depo_fazla',))

        # 6. Botanik'te var Depo'da yok
        for idx, botanik in eslesmeyen_botanik:
            tree.insert("", "end", values=(
                "❌", "— DEPO'DA YOK —",
                "", "", "", "",
                "",
                botanik['urun_adi'], botanik['miktar'],
                f"{float(botanik['birim_fiyat']):,.2f}", f"{float(botanik['toplam_tutar']):,.2f}",
                "Botanik'ten çıkar"
            ), tags=('botanik_fazla',))

        # Renkler
        tree.tag_configure('tutan', background='#C8E6C9')
        tree.tag_configure('kurus', background='#FFF9C4')
        tree.tag_configure('tutar_farkli', background='#FFE0B2')
        tree.tag_configure('miktar_farkli', background='#FFCDD2')
        tree.tag_configure('depo_fazla', background='#E1BEE7')
        tree.tag_configure('botanik_fazla', background='#B3E5FC')

        self._iade_sonuc_tree = tree

    def _ana_menuye_don(self):
        """Ana menüye dön"""
        self.root.destroy()
        if self.ana_menu_callback:
            self.ana_menu_callback()

    def _kapat(self):
        """Pencereyi kapat"""
        self.root.destroy()
        if self.ana_menu_callback:
            self.ana_menu_callback()

    def calistir(self):
        """Mainloop başlat"""
        self.root.mainloop()


# Test
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    pencere = tk.Toplevel(root)
    app = DepoEkstreModul(pencere)
    root.mainloop()
