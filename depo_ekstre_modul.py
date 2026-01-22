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

        # Sonuçlar
        self.ekstre_sonuclar = None

        # Manuel eşleştirme ve iptal için veri listeleri
        self.manuel_eslestirilenler = []  # [(depo_fatura, depo_kayit, eczane_fatura, eczane_kayit), ...]
        self.manuel_iptal_edilenler_depo = []  # [(fatura, kayit), ...]
        self.manuel_iptal_edilenler_eczane = []  # [(fatura, kayit), ...]
        # Manuel eklenenler: tek tarafta olan satırı diğer tarafa da ekleyerek eşleştirme
        # {'orijinal': 'depo'/'eczane', 'fatura': str, 'kayit': dict, 'aciklama': str}
        self.manuel_eklenenler = []

        # Seçili satırlar (manuel eşleştirme için)
        self.secili_depo_satir = None  # (fatura, kayit)
        self.secili_eczane_satir = None  # (fatura, kayit)

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
            command=self.ekstre_karsilastir_pencere_ac
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

            # DEPO alanı için drop handler
            def handle_drop_depo(files):
                if not files:
                    return
                try:
                    file_path = decode_file_path(files[0])
                    if validate_excel(file_path):
                        self.ekstre_dosya1_path.set(file_path)
                        self.drop_area1.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                except Exception as e:
                    logger.error(f"Depo drop hatası: {e}")

            # ECZANE alanı için drop handler
            def handle_drop_eczane(files):
                if not files:
                    return
                try:
                    file_path = decode_file_path(files[0])
                    if validate_excel(file_path):
                        self.ekstre_dosya2_path.set(file_path)
                        self.drop_area2.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                except Exception as e:
                    logger.error(f"Eczane drop hatası: {e}")

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

    def ekstre_karsilastir_pencere_ac(self):
        """Büyük karşılaştırma penceresini aç"""
        import pandas as pd

        dosya1 = self.ekstre_dosya1_path.get()
        dosya2 = self.ekstre_dosya2_path.get()

        if not dosya1 or not dosya2:
            messagebox.showwarning("Uyarı", "Lütfen her iki Excel dosyasını da seçin!")
            return

        try:
            df_depo = pd.read_excel(dosya1)
            df_eczane = pd.read_excel(dosya2)
            self._ekstre_sonuc_penceresi_olustur(df_depo, df_eczane, dosya1, dosya2)

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
            messagebox.showerror("Hata", f"Dosya okuma hatası: {str(e)}")
            logger.error(f"Ekstre dosya okuma hatası: {e}")

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
        self.secili_depo_satir = None
        self.secili_eczane_satir = None
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
            messagebox.showerror("Sütun Bulunamadı", "\n\n".join(hatalar))
            if not depo_fatura_col or not eczane_fatura_col:
                pencere.destroy()
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

        # Verileri hazırla
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
            if fatura and fatura != 'nan':
                borc = float(row[depo_borc_col]) if depo_borc_col and pd.notna(row[depo_borc_col]) else 0
                alacak = float(row[depo_alacak_col]) if depo_alacak_col and pd.notna(row[depo_alacak_col]) else 0
                tarih = str(row[depo_tarih_col]).strip() if depo_tarih_col and pd.notna(row[depo_tarih_col]) else ""
                tip = str(row[depo_tip_col]).strip() if depo_tip_col and pd.notna(row[depo_tip_col]) else ""
                depo_data[fatura] = {'borc': borc, 'alacak': alacak, 'tarih': tarih, 'tip': tip, 'row': row}

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
            if fatura and fatura != 'nan':
                borc = float(row[eczane_borc_col]) if eczane_borc_col and pd.notna(row[eczane_borc_col]) else 0
                alacak = float(row[eczane_alacak_col]) if eczane_alacak_col and pd.notna(row[eczane_alacak_col]) else 0
                tarih = str(row[eczane_tarih_col]).strip() if eczane_tarih_col and pd.notna(row[eczane_tarih_col]) else ""
                tip = str(row[eczane_tip_col]).strip() if eczane_tip_col and pd.notna(row[eczane_tip_col]) else ""
                eczane_data[fatura] = {'borc': borc, 'alacak': alacak, 'tarih': tarih, 'tip': tip, 'row': row}

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

                # Kayıt güncelle
                if tip == 'B':
                    kayit['borc'] = yeni_tutar
                else:
                    kayit['alacak'] = yeni_tutar

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
            text="💡 Her iki taraftan birer satır seçin, sonra 'Manuel Eşleştir' butonuna tıklayın",
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
            selectmode="browse"
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

        # Depo seçim olayı
        def depo_secildi(event):
            selection = depo_tree.selection()
            if selection:
                item_id = selection[0]
                data = self._kirmizi_depo_data.get(item_id)
                if data:
                    self._secili_depo_item = item_id
                    self.secili_depo_satir = (data['fatura'], data['kayit'])
                    self._kirmizi_secim_guncelle()

        depo_tree.bind("<<TreeviewSelect>>", depo_secildi)

        # Depo sağ tıklama menüsü
        depo_menu = tk.Menu(depo_tree, tearoff=0)
        depo_menu.add_command(label="✏️ Tutarı Düzelt", command=lambda: self._kirmizi_tutar_duzelt(depo_tree, 'depo'))
        depo_menu.add_separator()
        depo_menu.add_command(label="➕ Eczane'ye de Ekle ve Eşleştir", command=lambda: self._diger_tarafa_ekle(depo_tree, 'depo'))
        depo_menu.add_separator()
        depo_menu.add_command(label="❌ İptal Et", command=lambda: self._kirmizi_satir_iptal(depo_tree, 'depo'))

        def depo_context_menu(event):
            item = depo_tree.identify_row(event.y)
            if item:
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
            selectmode="browse"
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

        # Eczane seçim olayı
        def eczane_secildi(event):
            selection = eczane_tree.selection()
            if selection:
                item_id = selection[0]
                data = self._kirmizi_eczane_data.get(item_id)
                if data:
                    self._secili_eczane_item = item_id
                    self.secili_eczane_satir = (data['fatura'], data['kayit'])
                    self._kirmizi_secim_guncelle()

        eczane_tree.bind("<<TreeviewSelect>>", eczane_secildi)

        # Eczane sağ tıklama menüsü
        eczane_menu = tk.Menu(eczane_tree, tearoff=0)
        eczane_menu.add_command(label="✏️ Tutarı Düzelt", command=lambda: self._kirmizi_tutar_duzelt(eczane_tree, 'eczane'))
        eczane_menu.add_separator()
        eczane_menu.add_command(label="➕ Depo'ya da Ekle ve Eşleştir", command=lambda: self._diger_tarafa_ekle(eczane_tree, 'eczane'))
        eczane_menu.add_separator()
        eczane_menu.add_command(label="❌ İptal Et", command=lambda: self._kirmizi_satir_iptal(eczane_tree, 'eczane'))

        def eczane_context_menu(event):
            item = eczane_tree.identify_row(event.y)
            if item:
                eczane_tree.selection_set(item)
                eczane_menu.post(event.x_root, event.y_root)

        eczane_tree.bind("<Button-3>", eczane_context_menu)
        self._kirmizi_eczane_tree = eczane_tree

    def _kirmizi_secim_guncelle(self):
        """Kırmızı panel seçim durumunu güncelle"""
        depo_secili = self.secili_depo_satir is not None
        eczane_secili = self.secili_eczane_satir is not None

        if depo_secili and eczane_secili:
            depo_fatura = self.secili_depo_satir[0]
            eczane_fatura = self.secili_eczane_satir[0]
            self._kirmizi_secim_label.config(
                text=f"Seçim: Depo({depo_fatura}) | Eczane({eczane_fatura})",
                fg='#2E7D32'
            )
            # Buton aktif
            self._manuel_eslestir_btn.config(state='normal', bg='#4CAF50')
        elif depo_secili:
            self._kirmizi_secim_label.config(
                text=f"Seçim: Depo({self.secili_depo_satir[0]}) | Eczane(-)",
                fg='#1565C0'
            )
            self._manuel_eslestir_btn.config(state='disabled', bg='#9E9E9E')
        elif eczane_secili:
            self._kirmizi_secim_label.config(
                text=f"Seçim: Depo(-) | Eczane({self.secili_eczane_satir[0]})",
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
                else:
                    kayit['alacak'] = yeni_tutar

                # Tree güncelle
                values = list(tree.item(item_id, 'values'))
                values[3] = self._format_tutar(kayit, goster_tip=True)
                tree.item(item_id, values=values)

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
            if hasattr(self, '_secili_depo_item') and self._secili_depo_item == item_id:
                self.secili_depo_satir = None
                self._secili_depo_item = None
        else:
            self.manuel_iptal_edilenler_eczane.append((fatura, kayit.copy()))
            del self._kirmizi_eczane_data[item_id]
            # Seçimi temizle
            if hasattr(self, '_secili_eczane_item') and self._secili_eczane_item == item_id:
                self.secili_eczane_satir = None
                self._secili_eczane_item = None

        tree.delete(item_id)
        self._kirmizi_secim_guncelle()
        self._sonuclari_guncelle()
        messagebox.showinfo("Başarılı", f"Satır iptal edildi: {fatura}")

    def _kirmizi_manuel_eslestir(self):
        """Seçili depo ve eczane satırlarını manuel eşleştir"""
        if self.secili_depo_satir is None or self.secili_eczane_satir is None:
            messagebox.showwarning("Uyarı", "Lütfen hem Depo hem Eczane tarafından birer satır seçin!")
            return

        depo_fatura, depo_kayit = self.secili_depo_satir
        eczane_fatura, eczane_kayit = self.secili_eczane_satir

        depo_tutar = self._get_tutar(depo_kayit)[0]
        eczane_tutar = self._get_tutar(eczane_kayit)[0]
        fark = abs(depo_tutar - eczane_tutar)

        mesaj = f"Aşağıdaki satırları manuel eşleştirmek istiyor musunuz?\n\n"
        mesaj += f"📦 Depo: {depo_fatura} - {depo_tutar:,.2f} ₺\n"
        mesaj += f"🏥 Eczane: {eczane_fatura} - {eczane_tutar:,.2f} ₺\n"
        if fark > 0.01:
            mesaj += f"\n⚠️ Tutar farkı: {fark:,.2f} ₺"

        if not messagebox.askyesno("Manuel Eşleştirme Onayı", mesaj):
            return

        # Manuel eşleştirme listesine ekle
        self.manuel_eslestirilenler.append((depo_fatura, depo_kayit.copy(), eczane_fatura, eczane_kayit.copy()))

        # Tree'lerden satırları sil
        if hasattr(self, '_secili_depo_item') and self._secili_depo_item:
            try:
                self._kirmizi_depo_tree.delete(self._secili_depo_item)
                if self._secili_depo_item in self._kirmizi_depo_data:
                    del self._kirmizi_depo_data[self._secili_depo_item]
            except:
                pass

        if hasattr(self, '_secili_eczane_item') and self._secili_eczane_item:
            try:
                self._kirmizi_eczane_tree.delete(self._secili_eczane_item)
                if self._secili_eczane_item in self._kirmizi_eczane_data:
                    del self._kirmizi_eczane_data[self._secili_eczane_item]
            except:
                pass

        # Seçimleri temizle
        self.secili_depo_satir = None
        self.secili_eczane_satir = None
        self._secili_depo_item = None
        self._secili_eczane_item = None
        self._kirmizi_secim_guncelle()

        self._sonuclari_guncelle()
        messagebox.showinfo("Başarılı", f"Manuel eşleştirme yapıldı!\n\n📦 {depo_fatura} ↔ 🏥 {eczane_fatura}")

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
            if hasattr(self, '_secili_depo_item') and self._secili_depo_item == item_id:
                self.secili_depo_satir = None
                self._secili_depo_item = None
        else:
            if item_id in self._kirmizi_eczane_data:
                del self._kirmizi_eczane_data[item_id]
            # Seçimi temizle
            if hasattr(self, '_secili_eczane_item') and self._secili_eczane_item == item_id:
                self.secili_eczane_satir = None
                self._secili_eczane_item = None

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
        iptal_depo_tutar = sum(self._get_tutar(k)[0] for _, k in self.manuel_iptal_edilenler_depo)
        iptal_eczane_tutar = sum(self._get_tutar(k)[0] for _, k in self.manuel_iptal_edilenler_eczane)

        # Manuel eklenenlerin tutarını hesapla (bunlar diğer tarafa eklenecek)
        # Orijinal 'depo' ise → Eczane'ye eklendi → Eczane toplamına ekle
        # Orijinal 'eczane' ise → Depo'ya eklendi → Depo toplamına ekle
        eklenen_depoya = 0  # Eczane'de vardı, Depo'ya eklendi
        eklenen_eczaneye = 0  # Depo'da vardı, Eczane'ye eklendi
        for item in self.manuel_eklenenler:
            tutar = self._get_tutar(item['kayit'])[0]
            if item['orijinal'] == 'depo':
                # Depo'da vardı → Eczane'ye eklendi
                eklenen_eczaneye += tutar
            else:
                # Eczane'de vardı → Depo'ya eklendi
                eklenen_depoya += tutar

        # Orijinal toplamları al, iptal edilenleri çıkar, manuel eklenenleri ekle
        if 'depo_toplam_label' in self._sonuc_widgets:
            orijinal_depo = self._sonuc_widgets.get('orijinal_depo_toplam', 0)
            yeni_depo = orijinal_depo - iptal_depo_tutar + eklenen_depoya
            self._sonuc_widgets['depo_toplam_label'].config(text=f"{yeni_depo:,.2f} ₺")

        if 'eczane_toplam_label' in self._sonuc_widgets:
            orijinal_eczane = self._sonuc_widgets.get('orijinal_eczane_toplam', 0)
            yeni_eczane = orijinal_eczane - iptal_eczane_tutar + eklenen_eczaneye
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

        tree = ttk.Treeview(tree_fr, columns=("depo_fatura", "depo_tutar", "sep", "eczane_fatura", "eczane_tutar", "fark"), show="headings", height=8)
        for col, text, width in [("depo_fatura", "Depo Fatura No", 150), ("depo_tutar", "Depo Tutar", 120), ("sep", "↔", 20), ("eczane_fatura", "Eczane Fatura No", 150), ("eczane_tutar", "Eczane Tutar", 120), ("fark", "Fark", 100)]:
            tree.heading(col, text=text)
            tree.column(col, width=width, minwidth=width, anchor="e" if "tutar" in col or col == "fark" else ("center" if col == "sep" else "w"))

        tree_scroll = ttk.Scrollbar(tree_fr, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        toplam_depo = 0
        toplam_eczane = 0

        for depo_fatura, depo_kayit, eczane_fatura, eczane_kayit in self.manuel_eslestirilenler:
            depo_tutar = self._get_tutar(depo_kayit)[0]
            eczane_tutar = self._get_tutar(eczane_kayit)[0]
            fark = depo_tutar - eczane_tutar
            toplam_depo += depo_tutar
            toplam_eczane += eczane_tutar

            tree.insert("", "end", values=(
                depo_fatura,
                f"{depo_tutar:,.2f} ₺",
                "↔",
                eczane_fatura,
                f"{eczane_tutar:,.2f} ₺",
                f"{fark:,.2f} ₺" if abs(fark) > 0.01 else "✓"
            ), tags=('eslesti',))

        tree.tag_configure('eslesti', background='#C5CAE9')

        # Toplam satırı
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
        """Manuel eşleştirme panelini güncelle"""
        if hasattr(self, '_manuel_eslestirme_tree') and self._manuel_eslestirme_tree:
            # Mevcut tree'yi temizle
            for item in self._manuel_eslestirme_tree.get_children():
                self._manuel_eslestirme_tree.delete(item)

            # Yeni verileri ekle
            for depo_fatura, depo_kayit, eczane_fatura, eczane_kayit in self.manuel_eslestirilenler:
                depo_tutar = self._get_tutar(depo_kayit)[0]
                eczane_tutar = self._get_tutar(eczane_kayit)[0]
                fark = depo_tutar - eczane_tutar

                self._manuel_eslestirme_tree.insert("", "end", values=(
                    depo_fatura,
                    f"{depo_tutar:,.2f} ₺",
                    "↔",
                    eczane_fatura,
                    f"{eczane_tutar:,.2f} ₺",
                    f"{fark:,.2f} ₺" if abs(fark) > 0.01 else "✓"
                ), tags=('eslesti',))

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
        """DataFrame'de sütun bul"""
        for alt in alternatifler:
            if alt in df.columns:
                return alt
        for alt in alternatifler:
            alt_lower = alt.lower().replace(" ", "").replace("_", "").replace("/", "")
            for col in df.columns:
                col_lower = col.lower().replace(" ", "").replace("_", "").replace("/", "")
                if alt_lower in col_lower or col_lower in alt_lower:
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
