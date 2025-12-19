"""
Botanik Bot - Depo Ekstre Karşılaştırma Modülü
Ayrı pencere olarak çalışan bağımsız modül
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
from datetime import datetime
import json
import os

logger = logging.getLogger(__name__)


class DepoEkstreModul:
    """Depo Ekstre Karşılaştırma - Bağımsız Modül"""

    def __init__(self, root=None, ana_menu_callback=None):
        """
        Args:
            root: Tkinter root veya Toplevel pencere (None ise yeni oluşturulur)
            ana_menu_callback: Ana menüye dönüş callback fonksiyonu
        """
        self.ana_menu_callback = ana_menu_callback

        # Root pencere
        if root is None:
            self.root = tk.Tk()
            self.root.title("Depo Ekstre Karşılaştırma")
        else:
            self.root = root
            self.root.title("Depo Ekstre Karşılaştırma")

        # Pencere boyutları - Orta boy, ekran ortasında
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
        self.bg_color = '#E3F2FD'  # Açık mavi
        self.root.configure(bg=self.bg_color)

        # Dosya yolları
        self.ekstre_dosya1_path = tk.StringVar(value="")
        self.ekstre_dosya2_path = tk.StringVar(value="")

        # Filtre ayarları
        self.ekstre_filtreler = self._ekstre_filtre_yukle()

        # Pencere kapatma
        self.root.protocol("WM_DELETE_WINDOW", self.kapat)

        self.arayuz_olustur()

    def arayuz_olustur(self):
        """Ana arayüzü oluştur"""
        # Ana frame
        main_frame = tk.Frame(self.root, bg=self.bg_color, padx=15, pady=10)
        main_frame.pack(fill="both", expand=True)

        # Üst bar - Ana Sayfa butonu
        if self.ana_menu_callback:
            top_bar = tk.Frame(main_frame, bg=self.bg_color)
            top_bar.pack(fill="x", pady=(0, 10))

            ana_sayfa_btn = tk.Button(
                top_bar,
                text="🏠 Ana Sayfa",
                font=("Arial", 10, "bold"),
                bg="#1565C0",
                fg="white",
                activebackground="#0D47A1",
                activeforeground="white",
                cursor="hand2",
                bd=0,
                padx=15,
                pady=5,
                command=self.ana_sayfaya_don
            )
            ana_sayfa_btn.pack(side="left")

        # Başlık
        title_frame = tk.Frame(main_frame, bg=self.bg_color)
        title_frame.pack(fill="x", pady=(0, 10))

        title = tk.Label(
            title_frame,
            text="📊 Depo Ekstre Karşılaştırma",
            font=("Arial", 18, "bold"),
            bg=self.bg_color,
            fg='#1565C0'
        )
        title.pack()

        subtitle = tk.Label(
            title_frame,
            text="Depo ekstresi ile Eczane otomasyonunu karşılaştırın",
            font=("Arial", 10),
            bg=self.bg_color,
            fg='#1976D2'
        )
        subtitle.pack(pady=(5, 0))

        # Dosya seçim alanları - yan yana
        files_frame = tk.Frame(main_frame, bg=self.bg_color)
        files_frame.pack(fill="x", pady=15)
        files_frame.columnconfigure(0, weight=1)
        files_frame.columnconfigure(1, weight=1)

        # Dosya 1 - DEPO EKSTRESİ (Sol)
        file1_frame = tk.LabelFrame(
            files_frame,
            text="📁 DEPO EKSTRESİ",
            font=("Arial", 11, "bold"),
            bg='#BBDEFB',
            fg='#0D47A1',
            padx=15,
            pady=15
        )
        file1_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=5)

        self.drop_area1 = tk.Label(
            file1_frame,
            text="📥 Depo Excel dosyasını\nburaya sürükleyin\nveya tıklayarak seçin",
            font=("Arial", 11),
            bg='#E3F2FD',
            fg='#1565C0',
            relief="groove",
            bd=2,
            height=5,
            cursor="hand2"
        )
        self.drop_area1.pack(fill="x", pady=5)
        self.drop_area1.bind("<Button-1>", lambda e: self.dosya_sec(1))

        self.file1_label = tk.Label(
            file1_frame,
            textvariable=self.ekstre_dosya1_path,
            font=("Arial", 9),
            bg='#BBDEFB',
            fg='#0D47A1',
            wraplength=300
        )
        self.file1_label.pack(fill="x")

        # Dosya 2 - ECZANE OTOMASYONU (Sağ)
        file2_frame = tk.LabelFrame(
            files_frame,
            text="📁 ECZANE OTOMASYONU",
            font=("Arial", 11, "bold"),
            bg='#BBDEFB',
            fg='#0D47A1',
            padx=15,
            pady=15
        )
        file2_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=5)

        self.drop_area2 = tk.Label(
            file2_frame,
            text="📥 Eczane Excel dosyasını\nburaya sürükleyin\nveya tıklayarak seçin",
            font=("Arial", 11),
            bg='#E3F2FD',
            fg='#1565C0',
            relief="groove",
            bd=2,
            height=5,
            cursor="hand2"
        )
        self.drop_area2.pack(fill="x", pady=5)
        self.drop_area2.bind("<Button-1>", lambda e: self.dosya_sec(2))

        self.file2_label = tk.Label(
            file2_frame,
            textvariable=self.ekstre_dosya2_path,
            font=("Arial", 9),
            bg='#BBDEFB',
            fg='#0D47A1',
            wraplength=300
        )
        self.file2_label.pack(fill="x")

        # Butonlar
        button_frame = tk.Frame(main_frame, bg=self.bg_color)
        button_frame.pack(fill="x", pady=20)

        # Butonları ortalamak için iç frame
        button_center = tk.Frame(button_frame, bg=self.bg_color)
        button_center.pack(expand=True)

        # Karşılaştır butonu
        self.karsilastir_btn = tk.Button(
            button_center,
            text="🔍 KARŞILAŞTIR",
            font=("Arial", 14, "bold"),
            bg='#1976D2',
            fg='white',
            width=18,
            height=2,
            cursor="hand2",
            activebackground='#1565C0',
            activeforeground='white',
            relief="raised",
            bd=3,
            command=self.karsilastir
        )
        self.karsilastir_btn.pack(side="left", padx=10)

        # Ayarlar butonu
        self.ayarlar_btn = tk.Button(
            button_center,
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
            command=self.filtre_ayarlari_ac
        )
        self.ayarlar_btn.pack(side="left", padx=10)

        # Temizle butonu
        self.temizle_btn = tk.Button(
            button_center,
            text="🗑️ Temizle",
            font=("Arial", 10, "bold"),
            bg='#F44336',
            fg='white',
            width=10,
            height=2,
            cursor="hand2",
            activebackground='#D32F2F',
            activeforeground='white',
            relief="raised",
            bd=2,
            command=self.temizle
        )
        self.temizle_btn.pack(side="left", padx=10)

        # Filtre bilgisi
        self._filtre_bilgi_label = tk.Label(
            button_frame,
            text="",
            font=("Arial", 10),
            bg=self.bg_color,
            fg='#E65100'
        )
        self._filtre_bilgi_label.pack(pady=(10, 0))
        self._filtre_bilgi_guncelle()

        # Renk açıklamaları
        legend_frame = tk.LabelFrame(
            main_frame,
            text="🎨 Renk Kodları",
            font=("Arial", 10, "bold"),
            bg=self.bg_color,
            fg='#1565C0',
            padx=15,
            pady=10
        )
        legend_frame.pack(fill="x", pady=10)

        legends = [
            ("🟢 YEŞİL", "Fatura No + Tutar eşleşiyor", "#C8E6C9"),
            ("🟡 SARI", "Tutar eşleşiyor, Fatura No eşleşmiyor", "#FFF9C4"),
            ("🟠 TURUNCU", "Fatura No eşleşiyor, Tutar eşleşmiyor", "#FFE0B2"),
            ("🔴 KIRMIZI", "İkisi de eşleşmiyor", "#FFCDD2"),
        ]

        legend_inner = tk.Frame(legend_frame, bg=self.bg_color)
        legend_inner.pack()

        for text, desc, color in legends:
            row = tk.Frame(legend_inner, bg=self.bg_color)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=text, font=("Arial", 10, "bold"), bg=color, width=12, padx=5).pack(side="left", padx=5)
            tk.Label(row, text=desc, font=("Arial", 9), bg=self.bg_color, fg='#333').pack(side="left", padx=5)

        # Sürükle-bırak desteği
        self.root.after(100, self._setup_drag_drop)

    def ana_sayfaya_don(self):
        """Ana sayfaya dön"""
        if self.ana_menu_callback:
            self.root.destroy()
            self.ana_menu_callback()
        else:
            self.root.destroy()

    def kapat(self):
        """Pencereyi kapat"""
        if self.ana_menu_callback:
            self.root.destroy()
            self.ana_menu_callback()
        else:
            self.root.destroy()

    def dosya_sec(self, dosya_no):
        """Dosya seçme dialogu"""
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

    def temizle(self):
        """Dosya seçimlerini temizle"""
        self.ekstre_dosya1_path.set("")
        self.ekstre_dosya2_path.set("")
        self.drop_area1.config(
            text="📥 Depo Excel dosyasını\nburaya sürükleyin\nveya tıklayarak seçin",
            bg='#E3F2FD'
        )
        self.drop_area2.config(
            text="📥 Eczane Excel dosyasını\nburaya sürükleyin\nveya tıklayarak seçin",
            bg='#E3F2FD'
        )

    def _ekstre_filtre_yukle(self):
        """Filtre ayarlarını yükle"""
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
        except Exception as e:
            logger.error(f"Filtre kaydetme hatası: {e}")

    def _filtre_bilgi_guncelle(self):
        """Filtre bilgisini güncelle"""
        depo_sayisi = sum(len(v) for v in self.ekstre_filtreler.get('depo', {}).values())
        eczane_sayisi = sum(len(v) for v in self.ekstre_filtreler.get('eczane', {}).values())

        if depo_sayisi > 0 or eczane_sayisi > 0:
            text = f"⚠️ Aktif filtre: Depo({depo_sayisi}) | Eczane({eczane_sayisi})"
            self._filtre_bilgi_label.config(text=text, fg='#E65100')
        else:
            self._filtre_bilgi_label.config(text="✓ Filtre yok - tüm satırlar dahil", fg='#388E3C')

    def filtre_ayarlari_ac(self):
        """Filtre ayarları penceresini aç"""
        dosya1 = self.ekstre_dosya1_path.get()
        dosya2 = self.ekstre_dosya2_path.get()

        if not dosya1 and not dosya2:
            messagebox.showinfo("Bilgi", "Önce en az bir Excel dosyası yükleyin.")
            return

        # Mevcut botanik_gui'deki filtre ayarları penceresini kullanabiliriz
        # veya basit bir versiyon gösterebiliriz
        messagebox.showinfo("Bilgi", "Filtre ayarları için ana İlaç Takip modülündeki Ekstre sekmesini kullanın.")

    def _setup_drag_drop(self):
        """Sürükle-bırak desteği"""
        try:
            import windnd

            def handle_drop(files):
                if not files:
                    return
                try:
                    raw = files[0]
                    if isinstance(raw, bytes):
                        for encoding in ['cp1254', 'utf-8', 'latin-1', 'cp1252']:
                            try:
                                file_path = raw.decode(encoding)
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            file_path = raw.decode('utf-8', errors='replace')
                    else:
                        file_path = raw

                    if not file_path.lower().endswith(('.xlsx', '.xls')):
                        messagebox.showwarning("Uyarı", "Lütfen Excel dosyası seçin!")
                        return

                    if not self.ekstre_dosya1_path.get():
                        self.ekstre_dosya1_path.set(file_path)
                        self.drop_area1.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                    elif not self.ekstre_dosya2_path.get():
                        self.ekstre_dosya2_path.set(file_path)
                        self.drop_area2.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                    else:
                        secim = messagebox.askyesnocancel(
                            "Dosya Seçimi",
                            "Hangi alana yüklensin?\n\nEvet = Depo\nHayır = Eczane"
                        )
                        if secim is True:
                            self.ekstre_dosya1_path.set(file_path)
                            self.drop_area1.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                        elif secim is False:
                            self.ekstre_dosya2_path.set(file_path)
                            self.drop_area2.config(text="✅ Dosya yüklendi", bg='#C8E6C9')
                except Exception as e:
                    logger.error(f"Drop hatası: {e}")

            windnd.hook_dropfiles(self.root, func=handle_drop)
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Drag-drop kurulum hatası: {e}")

    def karsilastir(self):
        """Karşılaştırma işlemini başlat"""
        import pandas as pd

        dosya1 = self.ekstre_dosya1_path.get()
        dosya2 = self.ekstre_dosya2_path.get()

        if not dosya1 or not dosya2:
            messagebox.showwarning("Uyarı", "Lütfen her iki Excel dosyasını da seçin!")
            return

        try:
            # Excel dosyalarını oku
            df_depo = pd.read_excel(dosya1)
            df_eczane = pd.read_excel(dosya2)

            # Sonuç penceresini aç
            self._sonuc_penceresi_olustur(df_depo, df_eczane, dosya1, dosya2)

        except PermissionError:
            messagebox.showerror(
                "Dosya Erişim Hatası",
                "Dosya okunamıyor. Excel'de açık olabilir.\nLütfen dosyayı kapatıp tekrar deneyin."
            )
        except Exception as e:
            messagebox.showerror("Hata", f"Dosya okuma hatası: {str(e)}")
            logger.error(f"Ekstre okuma hatası: {e}")

    def _bul_sutun(self, df, alternatifler):
        """DataFrame'de sütun bul"""
        for alt in alternatifler:
            if alt in df.columns:
                return alt
        # Kısmi eşleşme
        for alt in alternatifler:
            alt_lower = alt.lower().replace(" ", "").replace("_", "").replace("/", "")
            for col in df.columns:
                col_lower = col.lower().replace(" ", "").replace("_", "").replace("/", "")
                if alt_lower in col_lower or col_lower in alt_lower:
                    return col
        return None

    def _sonuc_penceresi_olustur(self, df_depo, df_eczane, dosya1_yol, dosya2_yol):
        """Karşılaştırma sonuç penceresi"""
        import pandas as pd

        # Yeni pencere
        pencere = tk.Toplevel(self.root)
        pencere.title("📊 Karşılaştırma Sonuçları")
        pencere.configure(bg='#ECEFF1')

        window_width = 1000
        window_height = 700

        screen_width = pencere.winfo_screenwidth()
        screen_height = pencere.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        pencere.geometry(f"{window_width}x{window_height}+{x}+{y}")
        pencere.minsize(900, 600)

        # Sütunları bul
        depo_fatura_col = self._bul_sutun(df_depo, ['Evrak No', 'Fatura No', 'EVRAK NO', 'FATURA NO'])
        depo_borc_col = self._bul_sutun(df_depo, ['Borc', 'Borç', 'BORC', 'BORÇ', 'Tutar', 'TUTAR'])
        depo_alacak_col = self._bul_sutun(df_depo, ['Alacak', 'ALACAK'])

        eczane_fatura_col = self._bul_sutun(df_eczane, ['Fatura No', 'FaturaNo', 'FATURA NO', 'Evrak No'])
        eczane_borc_col = self._bul_sutun(df_eczane, ['Fatura Tutarı', 'Tutar', 'TUTAR', 'Borç', 'Borc'])
        eczane_alacak_col = self._bul_sutun(df_eczane, ['İade/Çık Tut', 'İade', 'Alacak', 'ALACAK'])

        # Sütun bulunamadı kontrolü
        hatalar = []
        if not depo_fatura_col:
            hatalar.append(f"DEPO'da Fatura No sütunu bulunamadı.\nSütunlar: {', '.join(df_depo.columns)}")
        if not depo_borc_col:
            hatalar.append(f"DEPO'da Borç/Tutar sütunu bulunamadı.")
        if not eczane_fatura_col:
            hatalar.append(f"ECZANE'de Fatura No sütunu bulunamadı.\nSütunlar: {', '.join(df_eczane.columns)}")
        if not eczane_borc_col:
            hatalar.append(f"ECZANE'de Fatura Tutarı sütunu bulunamadı.")

        if hatalar:
            messagebox.showerror("Sütun Bulunamadı", "\n\n".join(hatalar))
            if not depo_fatura_col or not eczane_fatura_col:
                pencere.destroy()
                return

        # Verileri hazırla
        depo_data = {}
        for _, row in df_depo.iterrows():
            fatura = str(row[depo_fatura_col]).strip() if pd.notna(row[depo_fatura_col]) else ""
            if fatura and fatura != 'nan':
                borc = float(row[depo_borc_col]) if depo_borc_col and pd.notna(row[depo_borc_col]) else 0
                alacak = float(row[depo_alacak_col]) if depo_alacak_col and pd.notna(row[depo_alacak_col]) else 0
                depo_data[fatura] = {'borc': borc, 'alacak': alacak}

        eczane_data = {}
        for _, row in df_eczane.iterrows():
            fatura = str(row[eczane_fatura_col]).strip() if pd.notna(row[eczane_fatura_col]) else ""
            if fatura and fatura != 'nan':
                borc = float(row[eczane_borc_col]) if eczane_borc_col and pd.notna(row[eczane_borc_col]) else 0
                alacak = float(row[eczane_alacak_col]) if eczane_alacak_col and pd.notna(row[eczane_alacak_col]) else 0
                eczane_data[fatura] = {'borc': borc, 'alacak': alacak}

        # Karşılaştırma
        tum_faturalar = set(depo_data.keys()) | set(eczane_data.keys())

        yesil_satirlar = []
        turuncu_satirlar = []
        kirmizi_depo = []
        kirmizi_eczane = []

        for fatura in tum_faturalar:
            depo_kayit = depo_data.get(fatura)
            eczane_kayit = eczane_data.get(fatura)

            if depo_kayit and eczane_kayit:
                # İkisi de var
                tutar_esit = abs(depo_kayit['borc'] - eczane_kayit['borc']) < 0.01
                if tutar_esit:
                    yesil_satirlar.append((fatura, depo_kayit, eczane_kayit))
                else:
                    turuncu_satirlar.append((fatura, depo_kayit, eczane_kayit))
            elif depo_kayit:
                kirmizi_depo.append((fatura, depo_kayit))
            elif eczane_kayit:
                kirmizi_eczane.append((fatura, eczane_kayit))

        # Ana frame
        main_frame = tk.Frame(pencere, bg='#ECEFF1')
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Başlık
        tk.Label(
            main_frame,
            text="📊 KARŞILAŞTIRMA SONUÇLARI",
            font=("Arial", 16, "bold"),
            bg='#ECEFF1',
            fg='#1565C0'
        ).pack(pady=(0, 10))

        # Özet bilgi
        ozet_frame = tk.Frame(main_frame, bg='#ECEFF1')
        ozet_frame.pack(fill="x", pady=10)

        ozet_text = f"🟢 Tam Eşleşen: {len(yesil_satirlar)} | 🟠 Tutar Farklı: {len(turuncu_satirlar)} | 🔴 Eşleşmeyen: {len(kirmizi_depo) + len(kirmizi_eczane)}"
        tk.Label(
            ozet_frame,
            text=ozet_text,
            font=("Arial", 12, "bold"),
            bg='#E3F2FD',
            fg='#1565C0',
            padx=20,
            pady=10
        ).pack(fill="x")

        # Borç özeti
        depo_toplam = sum(k['borc'] for k in depo_data.values())
        eczane_toplam = sum(k['borc'] for k in eczane_data.values())
        fark = depo_toplam - eczane_toplam

        borc_text = f"Depo Toplam: {depo_toplam:,.2f} ₺ | Eczane Toplam: {eczane_toplam:,.2f} ₺ | Fark: {fark:,.2f} ₺"
        tk.Label(
            ozet_frame,
            text=borc_text,
            font=("Arial", 11),
            bg='#FFF9C4' if abs(fark) > 0.01 else '#C8E6C9',
            fg='#333',
            padx=20,
            pady=8
        ).pack(fill="x", pady=(5, 0))

        # Treeview
        tree_frame = tk.Frame(main_frame, bg='#ECEFF1')
        tree_frame.pack(fill="both", expand=True, pady=10)

        columns = ('durum', 'fatura', 'depo_tutar', 'eczane_tutar', 'fark')
        tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)

        tree.heading('durum', text='Durum')
        tree.heading('fatura', text='Fatura No')
        tree.heading('depo_tutar', text='Depo Tutar')
        tree.heading('eczane_tutar', text='Eczane Tutar')
        tree.heading('fark', text='Fark')

        tree.column('durum', width=80, anchor='center')
        tree.column('fatura', width=200, anchor='w')
        tree.column('depo_tutar', width=150, anchor='e')
        tree.column('eczane_tutar', width=150, anchor='e')
        tree.column('fark', width=150, anchor='e')

        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Verileri ekle
        for fatura, depo, eczane in yesil_satirlar:
            tree.insert('', 'end', values=(
                '🟢', fatura, f"{depo['borc']:,.2f} ₺", f"{eczane['borc']:,.2f} ₺", "0.00 ₺"
            ), tags=('yesil',))

        for fatura, depo, eczane in turuncu_satirlar:
            fark = depo['borc'] - eczane['borc']
            tree.insert('', 'end', values=(
                '🟠', fatura, f"{depo['borc']:,.2f} ₺", f"{eczane['borc']:,.2f} ₺", f"{fark:,.2f} ₺"
            ), tags=('turuncu',))

        for fatura, kayit in kirmizi_depo:
            tree.insert('', 'end', values=(
                '🔴', fatura, f"{kayit['borc']:,.2f} ₺", "-", f"{kayit['borc']:,.2f} ₺"
            ), tags=('kirmizi',))

        for fatura, kayit in kirmizi_eczane:
            tree.insert('', 'end', values=(
                '🔴', fatura, "-", f"{kayit['borc']:,.2f} ₺", f"-{kayit['borc']:,.2f} ₺"
            ), tags=('kirmizi',))

        # Renk ayarları
        tree.tag_configure('yesil', background='#C8E6C9')
        tree.tag_configure('turuncu', background='#FFE0B2')
        tree.tag_configure('kirmizi', background='#FFCDD2')

        # Kapat butonu
        tk.Button(
            main_frame,
            text="✖ Kapat",
            font=("Arial", 11, "bold"),
            bg='#F44336',
            fg='white',
            cursor='hand2',
            bd=0,
            padx=20,
            pady=8,
            command=pencere.destroy
        ).pack(pady=10)

    def calistir(self):
        """Pencereyi çalıştır"""
        self.root.mainloop()


def depo_ekstre_ac(ana_menu_callback=None):
    """Depo Ekstre modülünü aç"""
    modul = DepoEkstreModul(ana_menu_callback=ana_menu_callback)
    modul.calistir()


if __name__ == "__main__":
    # Test
    modul = DepoEkstreModul()
    modul.calistir()
