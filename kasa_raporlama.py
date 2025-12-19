"""
Botanik Bot - Kasa Raporlama Modülü
Geçmiş kayıtlardan detaylı raporlar
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from datetime import datetime, timedelta
import calendar

logger = logging.getLogger(__name__)


class KasaRaporlamaPenceresi:
    """Kasa Raporlama Ana Penceresi"""

    def __init__(self, parent, db_cursor, db_conn):
        self.parent = parent
        self.cursor = db_cursor
        self.conn = db_conn
        self.pencere = None

    def goster(self):
        """Raporlama penceresini göster"""
        self.pencere = tk.Toplevel(self.parent)
        self.pencere.title("Kasa Raporlari")
        self.pencere.geometry("1000x700")
        self.pencere.transient(self.parent)
        self.pencere.configure(bg='#FAFAFA')

        # Pencereyi ortala
        self.pencere.update_idletasks()
        x = (self.pencere.winfo_screenwidth() - 1000) // 2
        y = (self.pencere.winfo_screenheight() - 700) // 2
        self.pencere.geometry(f"1000x700+{x}+{y}")

        # Başlık
        baslik_frame = tk.Frame(self.pencere, bg='#1565C0', height=50)
        baslik_frame.pack(fill="x")
        baslik_frame.pack_propagate(False)

        tk.Label(
            baslik_frame,
            text="KASA RAPORLARI",
            font=("Arial", 14, "bold"),
            bg='#1565C0',
            fg='white'
        ).pack(expand=True)

        # Notebook (sekmeler)
        self.notebook = ttk.Notebook(self.pencere)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Sekmeler
        self.gunluk_fark_sekmesi_olustur()
        self.aylik_ozet_sekmesi_olustur()
        self.filtreli_rapor_sekmesi_olustur()
        self.karsilastirma_sekmesi_olustur()

    # ==================== GÜNLÜK FARK RAPORU ====================
    def gunluk_fark_sekmesi_olustur(self):
        """Günlük artı/eksi fark dökümü"""
        frame = tk.Frame(self.notebook, bg='#FAFAFA')
        self.notebook.add(frame, text="Günlük Fark Dökümü")

        # Üst kontroller
        kontrol_frame = tk.Frame(frame, bg='#E3F2FD', pady=10)
        kontrol_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(kontrol_frame, text="Ay:", bg='#E3F2FD', font=("Arial", 10)).pack(side="left", padx=5)

        self.fark_ay_var = tk.StringVar()
        ay_combo = ttk.Combobox(kontrol_frame, textvariable=self.fark_ay_var, width=15, state="readonly")
        aylar = [(f"{i:02d} - {self.ay_adi(i)}", i) for i in range(1, 13)]
        ay_combo['values'] = [a[0] for a in aylar]
        ay_combo.current(datetime.now().month - 1)
        ay_combo.pack(side="left", padx=5)

        tk.Label(kontrol_frame, text="Yıl:", bg='#E3F2FD', font=("Arial", 10)).pack(side="left", padx=5)

        self.fark_yil_var = tk.StringVar(value=str(datetime.now().year))
        yil_combo = ttk.Combobox(kontrol_frame, textvariable=self.fark_yil_var, width=8, state="readonly")
        yil_combo['values'] = [str(y) for y in range(2020, datetime.now().year + 2)]
        yil_combo.current(yil_combo['values'].index(str(datetime.now().year)))
        yil_combo.pack(side="left", padx=5)

        tk.Button(
            kontrol_frame, text="Raporu Göster", font=("Arial", 10, "bold"),
            bg='#4CAF50', fg='white', padx=15,
            command=self.gunluk_fark_goster
        ).pack(side="left", padx=20)

        # Tablo
        tablo_frame = tk.Frame(frame, bg='#FAFAFA')
        tablo_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ('tarih', 'gun', 'sayim', 'botanik', 'fark', 'durum')
        self.fark_tree = ttk.Treeview(tablo_frame, columns=columns, show='headings', height=20)

        self.fark_tree.heading('tarih', text='Tarih')
        self.fark_tree.heading('gun', text='Gün')
        self.fark_tree.heading('sayim', text='Sayım Top.')
        self.fark_tree.heading('botanik', text='Botanik Top.')
        self.fark_tree.heading('fark', text='Fark')
        self.fark_tree.heading('durum', text='Durum')

        self.fark_tree.column('tarih', width=100, anchor='center')
        self.fark_tree.column('gun', width=60, anchor='center')
        self.fark_tree.column('sayim', width=120, anchor='e')
        self.fark_tree.column('botanik', width=120, anchor='e')
        self.fark_tree.column('fark', width=100, anchor='e')
        self.fark_tree.column('durum', width=80, anchor='center')

        # Tag renkleri
        self.fark_tree.tag_configure('pozitif', background='#C8E6C9')
        self.fark_tree.tag_configure('negatif', background='#FFCDD2')
        self.fark_tree.tag_configure('esit', background='#E3F2FD')

        scrollbar = ttk.Scrollbar(tablo_frame, orient="vertical", command=self.fark_tree.yview)
        self.fark_tree.configure(yscrollcommand=scrollbar.set)

        self.fark_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Özet
        self.fark_ozet_frame = tk.Frame(frame, bg='#E8F5E9', pady=10)
        self.fark_ozet_frame.pack(fill="x", padx=10, pady=5)

    def gunluk_fark_goster(self):
        """Günlük fark raporunu göster"""
        try:
            ay_str = self.fark_ay_var.get()
            ay = int(ay_str.split(" - ")[0])
            yil = int(self.fark_yil_var.get())

            # Tabloyu temizle
            self.fark_tree.delete(*self.fark_tree.get_children())

            # Verileri çek
            baslangic = f"{yil}-{ay:02d}-01"
            if ay == 12:
                bitis = f"{yil + 1}-01-01"
            else:
                bitis = f"{yil}-{ay + 1:02d}-01"

            self.cursor.execute('''
                SELECT tarih, son_genel_toplam, botanik_genel_toplam, fark
                FROM kasa_kapatma
                WHERE tarih >= ? AND tarih < ?
                ORDER BY tarih
            ''', (baslangic, bitis))

            rows = self.cursor.fetchall()

            toplam_fark = 0
            pozitif_gun = 0
            negatif_gun = 0
            esit_gun = 0

            gun_isimleri = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

            for row in rows:
                tarih = row[0]
                sayim = row[1] or 0
                botanik = row[2] or 0
                fark = row[3] or 0

                toplam_fark += fark

                # Tarih formatla
                try:
                    dt = datetime.strptime(tarih, "%Y-%m-%d")
                    tarih_gosterim = dt.strftime("%d.%m.%Y")
                    gun = gun_isimleri[dt.weekday()]
                except Exception:
                    tarih_gosterim = tarih
                    gun = "?"

                # Durum ve renk
                if abs(fark) < 0.01:
                    durum = "OK"
                    tag = 'esit'
                    esit_gun += 1
                elif fark > 0:
                    durum = "ARTI"
                    tag = 'pozitif'
                    pozitif_gun += 1
                else:
                    durum = "EKSI"
                    tag = 'negatif'
                    negatif_gun += 1

                fark_text = f"+{fark:,.0f}" if fark > 0 else f"{fark:,.0f}"

                self.fark_tree.insert('', 'end', values=(
                    tarih_gosterim, gun,
                    f"{sayim:,.0f}", f"{botanik:,.0f}",
                    fark_text, durum
                ), tags=(tag,))

            # Özet güncelle
            for widget in self.fark_ozet_frame.winfo_children():
                widget.destroy()

            tk.Label(
                self.fark_ozet_frame,
                text=f"Toplam {len(rows)} gün  |  ",
                font=("Arial", 10), bg='#E8F5E9'
            ).pack(side="left", padx=5)

            tk.Label(
                self.fark_ozet_frame,
                text=f"Artı: {pozitif_gun} gün  |  ",
                font=("Arial", 10, "bold"), bg='#E8F5E9', fg='#4CAF50'
            ).pack(side="left")

            tk.Label(
                self.fark_ozet_frame,
                text=f"Eksi: {negatif_gun} gün  |  ",
                font=("Arial", 10, "bold"), bg='#E8F5E9', fg='#F44336'
            ).pack(side="left")

            tk.Label(
                self.fark_ozet_frame,
                text=f"Eşit: {esit_gun} gün  |  ",
                font=("Arial", 10), bg='#E8F5E9', fg='#2196F3'
            ).pack(side="left")

            fark_renk = '#4CAF50' if toplam_fark >= 0 else '#F44336'
            fark_isaret = "+" if toplam_fark >= 0 else ""
            tk.Label(
                self.fark_ozet_frame,
                text=f"TOPLAM FARK: {fark_isaret}{toplam_fark:,.0f} TL",
                font=("Arial", 12, "bold"), bg='#E8F5E9', fg=fark_renk
            ).pack(side="right", padx=10)

        except Exception as e:
            logger.error(f"Günlük fark raporu hatası: {e}")
            messagebox.showerror("Hata", f"Rapor oluşturulamadı: {e}")

    # ==================== AYLIK ÖZET RAPORU ====================
    def aylik_ozet_sekmesi_olustur(self):
        """Aylık özet ve alınan paralar"""
        frame = tk.Frame(self.notebook, bg='#FAFAFA')
        self.notebook.add(frame, text="Aylık Özet")

        # Üst kontroller
        kontrol_frame = tk.Frame(frame, bg='#E3F2FD', pady=10)
        kontrol_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(kontrol_frame, text="Yıl:", bg='#E3F2FD', font=("Arial", 10)).pack(side="left", padx=5)

        self.ozet_yil_var = tk.StringVar(value=str(datetime.now().year))
        yil_combo = ttk.Combobox(kontrol_frame, textvariable=self.ozet_yil_var, width=8, state="readonly")
        yil_combo['values'] = [str(y) for y in range(2020, datetime.now().year + 2)]
        yil_combo.current(yil_combo['values'].index(str(datetime.now().year)))
        yil_combo.pack(side="left", padx=5)

        tk.Button(
            kontrol_frame, text="Yıllık Özet Göster", font=("Arial", 10, "bold"),
            bg='#2196F3', fg='white', padx=15,
            command=self.aylik_ozet_goster
        ).pack(side="left", padx=20)

        # İki panel yan yana
        icerik_frame = tk.Frame(frame, bg='#FAFAFA')
        icerik_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Sol panel - Aylık özet tablosu
        sol_frame = tk.LabelFrame(icerik_frame, text="Aylık Özet", font=("Arial", 10, "bold"), bg='#FAFAFA')
        sol_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        columns = ('ay', 'gun_sayisi', 'toplam_ciro', 'toplam_fark', 'ort_fark')
        self.ozet_tree = ttk.Treeview(sol_frame, columns=columns, show='headings', height=14)

        self.ozet_tree.heading('ay', text='Ay')
        self.ozet_tree.heading('gun_sayisi', text='Gün')
        self.ozet_tree.heading('toplam_ciro', text='Toplam Ciro')
        self.ozet_tree.heading('toplam_fark', text='Toplam Fark')
        self.ozet_tree.heading('ort_fark', text='Ort. Fark')

        self.ozet_tree.column('ay', width=100, anchor='w')
        self.ozet_tree.column('gun_sayisi', width=50, anchor='center')
        self.ozet_tree.column('toplam_ciro', width=120, anchor='e')
        self.ozet_tree.column('toplam_fark', width=100, anchor='e')
        self.ozet_tree.column('ort_fark', width=80, anchor='e')

        self.ozet_tree.tag_configure('pozitif', background='#C8E6C9')
        self.ozet_tree.tag_configure('negatif', background='#FFCDD2')

        self.ozet_tree.pack(fill="both", expand=True)

        # Sağ panel - Alınan paralar tablosu
        sag_frame = tk.LabelFrame(icerik_frame, text="Aylık Alınan Paralar", font=("Arial", 10, "bold"), bg='#FAFAFA')
        sag_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        columns2 = ('ay', 'alinan', 'masraf', 'silinen', 'net')
        self.alinan_tree = ttk.Treeview(sag_frame, columns=columns2, show='headings', height=14)

        self.alinan_tree.heading('ay', text='Ay')
        self.alinan_tree.heading('alinan', text='Alınan')
        self.alinan_tree.heading('masraf', text='Masraf')
        self.alinan_tree.heading('silinen', text='Silinen')
        self.alinan_tree.heading('net', text='Net')

        self.alinan_tree.column('ay', width=100, anchor='w')
        self.alinan_tree.column('alinan', width=90, anchor='e')
        self.alinan_tree.column('masraf', width=90, anchor='e')
        self.alinan_tree.column('silinen', width=90, anchor='e')
        self.alinan_tree.column('net', width=90, anchor='e')

        self.alinan_tree.pack(fill="both", expand=True)

        # Alt özet
        self.aylik_alt_ozet = tk.Frame(frame, bg='#FFF3E0', pady=10)
        self.aylik_alt_ozet.pack(fill="x", padx=10, pady=5)

    def aylik_ozet_goster(self):
        """Aylık özet raporunu göster"""
        try:
            yil = int(self.ozet_yil_var.get())

            # Tabloları temizle
            self.ozet_tree.delete(*self.ozet_tree.get_children())
            self.alinan_tree.delete(*self.alinan_tree.get_children())

            yillik_ciro = 0
            yillik_fark = 0
            yillik_alinan = 0
            yillik_masraf = 0
            yillik_silinen = 0

            for ay in range(1, 13):
                baslangic = f"{yil}-{ay:02d}-01"
                if ay == 12:
                    bitis = f"{yil + 1}-01-01"
                else:
                    bitis = f"{yil}-{ay + 1:02d}-01"

                # Aylık özet
                self.cursor.execute('''
                    SELECT
                        COUNT(*) as gun_sayisi,
                        SUM(son_genel_toplam) as toplam_ciro,
                        SUM(fark) as toplam_fark,
                        SUM(gun_ici_alinan_toplam) as alinan,
                        SUM(masraf_toplam) as masraf,
                        SUM(silinen_etki_toplam) as silinen
                    FROM kasa_kapatma
                    WHERE tarih >= ? AND tarih < ?
                ''', (baslangic, bitis))

                row = self.cursor.fetchone()
                gun_sayisi = row[0] or 0
                toplam_ciro = row[1] or 0
                toplam_fark = row[2] or 0
                alinan = row[3] or 0
                masraf = row[4] or 0
                silinen = row[5] or 0

                if gun_sayisi > 0:
                    ort_fark = toplam_fark / gun_sayisi
                    yillik_ciro += toplam_ciro
                    yillik_fark += toplam_fark
                    yillik_alinan += alinan
                    yillik_masraf += masraf
                    yillik_silinen += silinen

                    tag = 'pozitif' if toplam_fark >= 0 else 'negatif'
                    fark_text = f"+{toplam_fark:,.0f}" if toplam_fark >= 0 else f"{toplam_fark:,.0f}"
                    ort_text = f"+{ort_fark:,.0f}" if ort_fark >= 0 else f"{ort_fark:,.0f}"

                    self.ozet_tree.insert('', 'end', values=(
                        self.ay_adi(ay), gun_sayisi,
                        f"{toplam_ciro:,.0f}", fark_text, ort_text
                    ), tags=(tag,))

                    net = alinan - masraf - silinen
                    self.alinan_tree.insert('', 'end', values=(
                        self.ay_adi(ay),
                        f"{alinan:,.0f}", f"{masraf:,.0f}",
                        f"{silinen:,.0f}", f"{net:,.0f}"
                    ))

            # Alt özet
            for widget in self.aylik_alt_ozet.winfo_children():
                widget.destroy()

            tk.Label(
                self.aylik_alt_ozet,
                text=f"YILLIK CİRO: {yillik_ciro:,.0f} TL",
                font=("Arial", 11, "bold"), bg='#FFF3E0', fg='#E65100'
            ).pack(side="left", padx=15)

            fark_renk = '#4CAF50' if yillik_fark >= 0 else '#F44336'
            fark_isaret = "+" if yillik_fark >= 0 else ""
            tk.Label(
                self.aylik_alt_ozet,
                text=f"YILLIK FARK: {fark_isaret}{yillik_fark:,.0f} TL",
                font=("Arial", 11, "bold"), bg='#FFF3E0', fg=fark_renk
            ).pack(side="left", padx=15)

            yillik_net = yillik_alinan - yillik_masraf - yillik_silinen
            tk.Label(
                self.aylik_alt_ozet,
                text=f"YILLIK NET ALINAN: {yillik_net:,.0f} TL",
                font=("Arial", 11, "bold"), bg='#FFF3E0', fg='#1565C0'
            ).pack(side="right", padx=15)

        except Exception as e:
            logger.error(f"Aylık özet raporu hatası: {e}")
            messagebox.showerror("Hata", f"Rapor oluşturulamadı: {e}")

    # ==================== FİLTRELİ RAPOR ====================
    def filtreli_rapor_sekmesi_olustur(self):
        """Filtreli/parametreli rapor ekranı"""
        frame = tk.Frame(self.notebook, bg='#FAFAFA')
        self.notebook.add(frame, text="Filtreli Rapor")

        # Filtre paneli
        filtre_frame = tk.LabelFrame(frame, text="Filtre Seçenekleri", font=("Arial", 10, "bold"), bg='#E3F2FD', padx=15, pady=10)
        filtre_frame.pack(fill="x", padx=10, pady=10)

        # Satır 1: Tarih aralığı
        row1 = tk.Frame(filtre_frame, bg='#E3F2FD')
        row1.pack(fill="x", pady=5)

        tk.Label(row1, text="Başlangıç:", bg='#E3F2FD', font=("Arial", 10)).pack(side="left", padx=5)

        self.filtre_baslangic = tk.Entry(row1, width=12, font=("Arial", 10))
        self.filtre_baslangic.insert(0, (datetime.now() - timedelta(days=30)).strftime("%d.%m.%Y"))
        self.filtre_baslangic.pack(side="left", padx=5)

        tk.Label(row1, text="Bitiş:", bg='#E3F2FD', font=("Arial", 10)).pack(side="left", padx=15)

        self.filtre_bitis = tk.Entry(row1, width=12, font=("Arial", 10))
        self.filtre_bitis.insert(0, datetime.now().strftime("%d.%m.%Y"))
        self.filtre_bitis.pack(side="left", padx=5)

        # Satır 2: Fark filtresi
        row2 = tk.Frame(filtre_frame, bg='#E3F2FD')
        row2.pack(fill="x", pady=5)

        tk.Label(row2, text="Fark Durumu:", bg='#E3F2FD', font=("Arial", 10)).pack(side="left", padx=5)

        self.fark_filtre_var = tk.StringVar(value="Tümü")
        for text in ["Tümü", "Sadece Artı", "Sadece Eksi", "Sadece Eşit"]:
            tk.Radiobutton(
                row2, text=text, variable=self.fark_filtre_var, value=text,
                bg='#E3F2FD', font=("Arial", 9)
            ).pack(side="left", padx=10)

        # Satır 3: Min/Max fark
        row3 = tk.Frame(filtre_frame, bg='#E3F2FD')
        row3.pack(fill="x", pady=5)

        tk.Label(row3, text="Min Fark:", bg='#E3F2FD', font=("Arial", 10)).pack(side="left", padx=5)
        self.min_fark = tk.Entry(row3, width=10, font=("Arial", 10))
        self.min_fark.pack(side="left", padx=5)

        tk.Label(row3, text="Max Fark:", bg='#E3F2FD', font=("Arial", 10)).pack(side="left", padx=15)
        self.max_fark = tk.Entry(row3, width=10, font=("Arial", 10))
        self.max_fark.pack(side="left", padx=5)

        tk.Button(
            row3, text="FİLTRELE", font=("Arial", 10, "bold"),
            bg='#FF5722', fg='white', padx=20,
            command=self.filtreli_rapor_goster
        ).pack(side="right", padx=10)

        # Sonuç tablosu
        tablo_frame = tk.Frame(frame, bg='#FAFAFA')
        tablo_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ('tarih', 'gun', 'nakit', 'pos', 'iban', 'toplam', 'botanik', 'fark')
        self.filtre_tree = ttk.Treeview(tablo_frame, columns=columns, show='headings', height=15)

        self.filtre_tree.heading('tarih', text='Tarih')
        self.filtre_tree.heading('gun', text='Gün')
        self.filtre_tree.heading('nakit', text='Nakit')
        self.filtre_tree.heading('pos', text='POS')
        self.filtre_tree.heading('iban', text='IBAN')
        self.filtre_tree.heading('toplam', text='Toplam')
        self.filtre_tree.heading('botanik', text='Botanik')
        self.filtre_tree.heading('fark', text='Fark')

        for col in columns:
            self.filtre_tree.column(col, width=90, anchor='e' if col != 'tarih' and col != 'gun' else 'center')

        self.filtre_tree.tag_configure('pozitif', background='#C8E6C9')
        self.filtre_tree.tag_configure('negatif', background='#FFCDD2')
        self.filtre_tree.tag_configure('esit', background='#E3F2FD')

        scrollbar = ttk.Scrollbar(tablo_frame, orient="vertical", command=self.filtre_tree.yview)
        self.filtre_tree.configure(yscrollcommand=scrollbar.set)

        self.filtre_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Özet
        self.filtre_ozet = tk.Frame(frame, bg='#E8F5E9', pady=10)
        self.filtre_ozet.pack(fill="x", padx=10, pady=5)

    def filtreli_rapor_goster(self):
        """Filtreli raporu göster"""
        try:
            # Tarihleri parse et
            baslangic_str = self.filtre_baslangic.get().strip()
            bitis_str = self.filtre_bitis.get().strip()

            try:
                baslangic_dt = datetime.strptime(baslangic_str, "%d.%m.%Y")
                bitis_dt = datetime.strptime(bitis_str, "%d.%m.%Y")
                baslangic = baslangic_dt.strftime("%Y-%m-%d")
                bitis = bitis_dt.strftime("%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Hata", "Tarih formatı: GG.AA.YYYY")
                return

            # Tabloyu temizle
            self.filtre_tree.delete(*self.filtre_tree.get_children())

            # SQL sorgusu
            sql = '''
                SELECT tarih, nakit_toplam, pos_toplam, iban_toplam,
                       son_genel_toplam, botanik_genel_toplam, fark
                FROM kasa_kapatma
                WHERE tarih >= ? AND tarih <= ?
            '''
            params = [baslangic, bitis]

            # Fark filtresi
            fark_durumu = self.fark_filtre_var.get()
            if fark_durumu == "Sadece Artı":
                sql += " AND fark > 0"
            elif fark_durumu == "Sadece Eksi":
                sql += " AND fark < 0"
            elif fark_durumu == "Sadece Eşit":
                sql += " AND ABS(fark) < 0.01"

            # Min/Max fark
            min_fark = self.min_fark.get().strip()
            max_fark = self.max_fark.get().strip()
            if min_fark:
                try:
                    sql += " AND fark >= ?"
                    params.append(float(min_fark))
                except ValueError:
                    pass
            if max_fark:
                try:
                    sql += " AND fark <= ?"
                    params.append(float(max_fark))
                except ValueError:
                    pass

            sql += " ORDER BY tarih"

            self.cursor.execute(sql, params)
            rows = self.cursor.fetchall()

            toplam_fark = 0
            toplam_ciro = 0
            gun_isimleri = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

            for row in rows:
                tarih = row[0]
                nakit = row[1] or 0
                pos = row[2] or 0
                iban = row[3] or 0
                toplam = row[4] or 0
                botanik = row[5] or 0
                fark = row[6] or 0

                toplam_fark += fark
                toplam_ciro += toplam

                # Tarih formatla
                try:
                    dt = datetime.strptime(tarih, "%Y-%m-%d")
                    tarih_gosterim = dt.strftime("%d.%m.%Y")
                    gun = gun_isimleri[dt.weekday()]
                except Exception:
                    tarih_gosterim = tarih
                    gun = "?"

                # Tag
                if abs(fark) < 0.01:
                    tag = 'esit'
                elif fark > 0:
                    tag = 'pozitif'
                else:
                    tag = 'negatif'

                fark_text = f"+{fark:,.0f}" if fark > 0 else f"{fark:,.0f}"

                self.filtre_tree.insert('', 'end', values=(
                    tarih_gosterim, gun,
                    f"{nakit:,.0f}", f"{pos:,.0f}", f"{iban:,.0f}",
                    f"{toplam:,.0f}", f"{botanik:,.0f}", fark_text
                ), tags=(tag,))

            # Özet
            for widget in self.filtre_ozet.winfo_children():
                widget.destroy()

            tk.Label(
                self.filtre_ozet,
                text=f"Bulunan: {len(rows)} kayıt  |  Toplam Ciro: {toplam_ciro:,.0f} TL  |  ",
                font=("Arial", 10), bg='#E8F5E9'
            ).pack(side="left", padx=5)

            fark_renk = '#4CAF50' if toplam_fark >= 0 else '#F44336'
            fark_isaret = "+" if toplam_fark >= 0 else ""
            tk.Label(
                self.filtre_ozet,
                text=f"TOPLAM FARK: {fark_isaret}{toplam_fark:,.0f} TL",
                font=("Arial", 11, "bold"), bg='#E8F5E9', fg=fark_renk
            ).pack(side="right", padx=10)

        except Exception as e:
            logger.error(f"Filtreli rapor hatası: {e}")
            messagebox.showerror("Hata", f"Rapor oluşturulamadı: {e}")

    # ==================== KARŞILAŞTIRMA RAPORU ====================
    def karsilastirma_sekmesi_olustur(self):
        """Sayım vs Botanik karşılaştırma tablosu"""
        frame = tk.Frame(self.notebook, bg='#FAFAFA')
        self.notebook.add(frame, text="Karşılaştırma Tablosu")

        # Kontroller
        kontrol_frame = tk.Frame(frame, bg='#E3F2FD', pady=10)
        kontrol_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(kontrol_frame, text="Son kaç gün:", bg='#E3F2FD', font=("Arial", 10)).pack(side="left", padx=5)

        self.karsilastirma_gun = tk.Entry(kontrol_frame, width=5, font=("Arial", 10))
        self.karsilastirma_gun.insert(0, "30")
        self.karsilastirma_gun.pack(side="left", padx=5)

        tk.Button(
            kontrol_frame, text="Karşılaştır", font=("Arial", 10, "bold"),
            bg='#9C27B0', fg='white', padx=15,
            command=self.karsilastirma_goster
        ).pack(side="left", padx=20)

        # Tablo
        tablo_frame = tk.Frame(frame, bg='#FAFAFA')
        tablo_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ('tarih', 'nakit_s', 'nakit_b', 'nakit_f', 'pos_s', 'pos_b', 'pos_f', 'iban_s', 'iban_b', 'iban_f', 'genel_f')
        self.kars_tree = ttk.Treeview(tablo_frame, columns=columns, show='headings', height=18)

        self.kars_tree.heading('tarih', text='Tarih')
        self.kars_tree.heading('nakit_s', text='Nakit-S')
        self.kars_tree.heading('nakit_b', text='Nakit-B')
        self.kars_tree.heading('nakit_f', text='Fark')
        self.kars_tree.heading('pos_s', text='POS-S')
        self.kars_tree.heading('pos_b', text='POS-B')
        self.kars_tree.heading('pos_f', text='Fark')
        self.kars_tree.heading('iban_s', text='IBAN-S')
        self.kars_tree.heading('iban_b', text='IBAN-B')
        self.kars_tree.heading('iban_f', text='Fark')
        self.kars_tree.heading('genel_f', text='G.FARK')

        for col in columns:
            w = 70 if col != 'tarih' else 85
            self.kars_tree.column(col, width=w, anchor='e' if col != 'tarih' else 'center')

        self.kars_tree.tag_configure('hata', background='#FFCDD2')

        scrollbar = ttk.Scrollbar(tablo_frame, orient="vertical", command=self.kars_tree.yview)
        self.kars_tree.configure(yscrollcommand=scrollbar.set)

        self.kars_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def karsilastirma_goster(self):
        """Karşılaştırma tablosunu göster"""
        try:
            gun_sayisi = int(self.karsilastirma_gun.get() or 30)
            bitis = datetime.now().strftime("%Y-%m-%d")
            baslangic = (datetime.now() - timedelta(days=gun_sayisi)).strftime("%Y-%m-%d")

            self.kars_tree.delete(*self.kars_tree.get_children())

            self.cursor.execute('''
                SELECT tarih, nakit_toplam, botanik_nakit,
                       pos_toplam, botanik_pos,
                       iban_toplam, botanik_iban,
                       fark
                FROM kasa_kapatma
                WHERE tarih >= ? AND tarih <= ?
                ORDER BY tarih DESC
            ''', (baslangic, bitis))

            for row in self.cursor.fetchall():
                tarih = row[0]
                nakit_s = row[1] or 0
                nakit_b = row[2] or 0
                pos_s = row[3] or 0
                pos_b = row[4] or 0
                iban_s = row[5] or 0
                iban_b = row[6] or 0
                genel_fark = row[7] or 0

                nakit_f = nakit_s - nakit_b
                pos_f = pos_s - pos_b
                iban_f = iban_s - iban_b

                # Tarih formatla
                try:
                    dt = datetime.strptime(tarih, "%Y-%m-%d")
                    tarih_gosterim = dt.strftime("%d.%m")
                except Exception:
                    tarih_gosterim = tarih

                def fmt_fark(f):
                    if abs(f) < 0.01:
                        return "0"
                    return f"+{f:,.0f}" if f > 0 else f"{f:,.0f}"

                tag = 'hata' if abs(genel_fark) > 10 else ''

                self.kars_tree.insert('', 'end', values=(
                    tarih_gosterim,
                    f"{nakit_s:,.0f}", f"{nakit_b:,.0f}", fmt_fark(nakit_f),
                    f"{pos_s:,.0f}", f"{pos_b:,.0f}", fmt_fark(pos_f),
                    f"{iban_s:,.0f}", f"{iban_b:,.0f}", fmt_fark(iban_f),
                    fmt_fark(genel_fark)
                ), tags=(tag,) if tag else ())

        except Exception as e:
            logger.error(f"Karşılaştırma raporu hatası: {e}")
            messagebox.showerror("Hata", f"Rapor oluşturulamadı: {e}")

    def ay_adi(self, ay):
        """Ay numarasından Türkçe ay adı"""
        aylar = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
                 "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
        return aylar[ay] if 1 <= ay <= 12 else ""
